from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import tomllib
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from types import MappingProxyType
from typing import Iterator, Mapping, Protocol, Sequence

from .filesystem import InstallerError, SafeRoot, TreeRef, capture_file
from .model import BlenderPaths, FileImage, ImageState, TreeEntry, TreeImage


_SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
_MARKER = "__BLENDER_MCP_INSTALLER__"
_REPOSITORY = "user_default"
_EXTENSION_ID = "mcp"
_EXTENSION_VERSION = "1.0.0"
_HOST = "localhost"
_PORT = 9876
_MAX_OUTPUT = 1024 * 1024
_MAX_ARCHIVE = 64 * 1024 * 1024
_DISCOVERY_KEYS = {
    "binary_path",
    "version",
    "architecture",
    "user_resources",
    "config_root",
    "extensions_root",
    "repository",
    "enabled",
    "online_access",
    "host",
    "port",
    "autostart",
}
_DISCOVERY_EXPRESSION = (
    "import bpy,json,platform;"
    "m='bl_ext.user_default.mcp';a=bpy.context.preferences.addons;"
    "p=a[m].preferences if m in a else None;"
    "print('__BLENDER_MCP_INSTALLER__'+json.dumps({"
    "'binary_path':bpy.app.binary_path,'version':list(bpy.app.version),"
    "'architecture':platform.machine(),"
    "'user_resources':bpy.utils.resource_path('USER'),"
    "'config_root':bpy.utils.user_resource('CONFIG'),"
    "'extensions_root':bpy.utils.user_resource('EXTENSIONS'),"
    "'repository':'user_default','enabled':m in a,"
    "'online_access':bpy.context.preferences.system.use_online_access,"
    "'host':None if p is None else p.host,"
    "'port':None if p is None else p.port,"
    "'autostart':None if p is None else p.use_autostart},sort_keys=True))"
)
_PREFERENCES_EXPRESSION = (
    "import bpy;"
    "m='bl_ext.user_default.mcp';"
    "r={'FINISHED'} if m in bpy.context.preferences.addons else "
    "bpy.ops.preferences.addon_enable(module=m);assert r=={'FINISHED'},r;"
    "bpy.context.preferences.system.use_online_access=True;"
    "p=bpy.context.preferences.addons[m].preferences;"
    "p.host='localhost';p.port=9876;p.use_autostart=True;"
    "r=bpy.ops.wm.save_userpref();assert r=={'FINISHED'},r"
)
_PYC = re.compile(r"(?P<stem>[^.]+)(?:\.[A-Za-z0-9_-]+)*\.pyc\Z")


class Runner(Protocol):
    def __call__(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> object: ...


@dataclass(frozen=True)
class BlenderAuthorizations:
    allow_extension_install: bool
    allow_online_access: bool
    allow_localhost_bridge: bool
    approve_arbitrary_python: bool

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.allow_extension_install,
                self.allow_online_access,
                self.allow_localhost_bridge,
                self.approve_arbitrary_python,
            )
        ):
            raise ValueError("invalid Blender authorizations")

    @property
    def all_granted(self) -> bool:
        return all(
            (
                self.allow_extension_install,
                self.allow_online_access,
                self.allow_localhost_bridge,
                self.approve_arbitrary_python,
            )
        )


@dataclass(frozen=True)
class PayloadEntry:
    path: str
    kind: str
    mode: int
    size: int
    sha256: str | None

    def __post_init__(self) -> None:
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or self.kind not in {"file", "dir"}
            or type(self.mode) is not int
            or self.mode < 0
            or type(self.size) is not int
            or self.size < 0
        ):
            raise ValueError("invalid extension payload entry")
        if self.kind == "file":
            if type(self.sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
                raise ValueError("invalid extension payload hash")
        elif self.sha256 is not None or self.size != 0:
            raise ValueError("invalid extension directory entry")


@dataclass(frozen=True)
class PayloadIndex:
    entries: tuple[PayloadEntry, ...]
    canonical_digest: str
    manifest_id: str
    manifest_version: str

    def __post_init__(self) -> None:
        if type(self.entries) is not tuple or any(
            type(entry) is not PayloadEntry for entry in self.entries
        ):
            raise ValueError("invalid extension payload entries")
        paths = tuple(entry.path for entry in self.entries)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("extension payload entries are not uniquely sorted")
        if not re.fullmatch(
            r"[0-9a-f]{64}", self.canonical_digest
        ) or self.canonical_digest != _payload_digest(self.entries):
            raise ValueError("invalid extension payload digest")
        if self.manifest_id != _EXTENSION_ID or self.manifest_version != _EXTENSION_VERSION:
            raise ValueError("unexpected extension manifest identity")


@dataclass(frozen=True)
class ExtensionComparison:
    expected: PayloadIndex
    current: TreeRef
    current_image: TreeImage
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    foreign: tuple[str, ...]
    disposable_pyc: tuple[str, ...]
    disposable_dirs: tuple[str, ...]

    @property
    def exact(self) -> bool:
        return not (self.missing or self.changed or self.foreign)


@dataclass(frozen=True)
class BlenderState:
    executable: Path
    executable_arches: tuple[str, ...]
    reported_binary: Path
    reported_architecture: str
    version: str
    home: Path
    user_resources: Path
    config_root: Path
    userpref: Path
    extensions_root: Path
    repository: str
    extension_root: Path
    manifest_id: str | None
    manifest_version: str | None
    enabled: bool
    online_access: bool
    host: str | None
    port: int | None
    autostart: bool | None
    canonical_payload_digest: str | None

    def __post_init__(self) -> None:
        paths = (
            self.executable,
            self.reported_binary,
            self.home,
            self.user_resources,
            self.config_root,
            self.userpref,
            self.extensions_root,
            self.extension_root,
        )
        if any(
            not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts
            for path in paths
        ):
            raise ValueError("invalid Blender state path")
        if (
            self.reported_binary != self.executable
            or self.userpref != self.config_root / "userpref.blend"
            or self.extension_root != self.extensions_root / self.repository / _EXTENSION_ID
            or not self.config_root.is_relative_to(self.user_resources)
            or not self.extensions_root.is_relative_to(self.user_resources)
            or type(self.executable_arches) is not tuple
            or "arm64" not in self.executable_arches
            or self.reported_architecture != "arm64"
        ):
            raise ValueError("invalid Blender state identity")


@dataclass(frozen=True)
class BlenderLifecycle:
    matching_selected_pids: tuple[int, ...]
    listener_pid: int | None
    listener_executable: Path | None
    port_free: bool


@dataclass(frozen=True)
class BlenderChange:
    changed: bool
    stage_root: Path | None
    extension_path: Path
    userpref_path: Path
    extension_image: TreeImage
    userpref_image: FileImage
    staged_state: BlenderState
    unowned_paths: tuple[Path, ...]


@dataclass(frozen=True)
class _Probe:
    arches: tuple[str, ...]
    values: Mapping[str, object]


@dataclass(frozen=True)
class _LsofFile:
    fd: str
    device: int
    inode: int
    path: str


@dataclass(frozen=True)
class _LsofProcess:
    pid: int
    command: str
    uid: int
    files: tuple[_LsofFile, ...]


def _absolute(path: Path, label: str) -> Path:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or ".." in path.parts
        or "\0" in str(path)
    ):
        raise ValueError(f"{label} must be an absolute lexical path")
    return path


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Blender probe key")
        result[key] = value
    return result


def _text(value: object, label: str) -> str:
    if isinstance(value, bytes):
        try:
            result = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InstallerError(f"invalid {label} output") from exc
    elif isinstance(value, str):
        result = value
    else:
        raise InstallerError(f"invalid {label} output")
    if len(result.encode("utf-8")) > _MAX_OUTPUT:
        raise InstallerError(f"invalid {label} output")
    return result


def _run(
    runner: Runner,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    label: str,
    accepted: tuple[int, ...] = (0,),
) -> tuple[int, str]:
    try:
        completed = runner(argv, cwd=cwd, env=env)
        returncode = getattr(completed, "returncode")
        stdout = _text(getattr(completed, "stdout"), label)
    except InstallerError:
        raise
    except BaseException as exc:
        raise InstallerError(f"{label} failed") from exc
    if type(returncode) is not int or returncode not in accepted:
        raise InstallerError(f"{label} failed")
    return returncode, stdout


def _component_safe(path: Path, *, allow_missing: bool) -> None:
    _absolute(path, "path")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(path.parts[1:]):
            try:
                info = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                if allow_missing:
                    return
                raise ValueError("path component is missing") from None
            if stat.S_ISLNK(info.st_mode):
                raise ValueError("path contains a symlink")
            last = index == len(path.parts[1:]) - 1
            if last:
                return
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("path ancestor is not a directory")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
    finally:
        os.close(fd)


@contextmanager
def _open_executable(path: Path) -> Iterator[tuple[int, os.stat_result]]:
    _absolute(path, "Blender executable")
    _component_safe(path, allow_missing=False)
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or not before.st_mode & 0o111:
            raise ValueError("Blender executable must be a non-symlink executable file")
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                before.st_dev,
                before.st_ino,
                before.st_mode,
            ):
                raise ValueError("Blender executable changed while opening")
            yield fd, opened
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def _path_env(blender_bin: Path) -> str:
    return f"{blender_bin.parent}:{_SYSTEM_PATH}"


def _profile_env(blender_bin: Path, env: Mapping[str, str]) -> dict[str, str]:
    if type(env) is not dict and not isinstance(env, Mapping):
        raise ValueError("invalid Blender environment")
    if any(type(key) is not str or type(value) is not str for key, value in env.items()):
        raise ValueError("invalid Blender environment")
    if "HOME" not in env:
        raise ValueError("HOME is required")
    home = _absolute(Path(env["HOME"]), "HOME")
    _component_safe(home, allow_missing=False)
    names = (
        "BLENDER_USER_RESOURCES",
        "BLENDER_USER_CONFIG",
        "BLENDER_USER_EXTENSIONS",
    )
    supplied = tuple(name in env for name in names)
    if any(supplied) and not all(supplied):
        raise ValueError("isolated Blender profiles require all three user paths")
    clean = {
        "HOME": str(home),
        "BLENDER_MCP_HOST": _HOST,
        "BLENDER_MCP_PORT": str(_PORT),
        "PATH": _path_env(blender_bin),
    }
    if all(supplied):
        resources, config, extensions = (Path(env[name]) for name in names)
        for path in (resources, config, extensions):
            _absolute(path, "Blender profile path")
            _component_safe(path, allow_missing=True)
        if not config.is_relative_to(resources) or not extensions.is_relative_to(resources):
            raise ValueError("Blender config and extensions must descend from resources")
        clean.update(dict(zip(names, map(str, (resources, config, extensions)), strict=True)))
    return clean


def _parse_arches(raw: str) -> tuple[str, ...]:
    arches = tuple(raw.split())
    if not arches or any(not re.fullmatch(r"[A-Za-z0-9_]+", item) for item in arches):
        raise InstallerError("invalid Blender architecture output")
    if "arm64" not in arches:
        raise InstallerError("Blender executable does not contain arm64")
    return arches


def _parse_probe(raw: str) -> Mapping[str, object]:
    lines = [line[len(_MARKER) :] for line in raw.splitlines() if line.startswith(_MARKER)]
    if len(lines) != 1:
        raise InstallerError("invalid Blender discovery output")
    try:
        value = json.loads(
            lines[0],
            object_pairs_hook=_json_object,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise InstallerError("invalid Blender discovery output") from exc
    if type(value) is not dict or set(value) != _DISCOVERY_KEYS:
        raise InstallerError("invalid Blender discovery output")
    return MappingProxyType(value)


def _probe_blender(blender_bin: Path, env: Mapping[str, str], runner: Runner) -> _Probe:
    clean = _profile_env(blender_bin, env)
    with _open_executable(blender_bin) as (_, selected):
        _, arch_output = _run(
            runner,
            ("/usr/bin/lipo", "-archs", str(blender_bin)),
            cwd=blender_bin.parent,
            env=clean,
            label="Blender architecture probe",
        )
        arches = _parse_arches(arch_output)
        _, output = _run(
            runner,
            (
                str(blender_bin),
                "--background",
                "--python-expr",
                _DISCOVERY_EXPRESSION,
            ),
            cwd=blender_bin.parent,
            env=clean,
            label="Blender discovery",
        )
        values = _parse_probe(output)
        reported = Path(values["binary_path"]) if type(values["binary_path"]) is str else Path()
        if reported != blender_bin:
            raise InstallerError("Blender reported a different executable")
        _component_safe(reported, allow_missing=False)
        linked = reported.stat(follow_symlinks=False)
        if (linked.st_dev, linked.st_ino) != (selected.st_dev, selected.st_ino):
            raise InstallerError("Blender executable identity changed")
    return _Probe(arches, values)


def _paths_from_probe(
    blender_bin: Path, env: Mapping[str, str], probe: _Probe
) -> tuple[Path, Path, Path, str, str]:
    values = probe.values
    version = values["version"]
    if (
        type(version) is not list
        or len(version) != 3
        or any(type(item) is not int or item < 0 for item in version)
        or not ((5, 2, 0) <= tuple(version) < (5, 3, 0))
    ):
        raise InstallerError("unsupported Blender version")
    architecture = values["architecture"]
    if architecture != "arm64":
        raise InstallerError("Blender reported an unsupported architecture")
    raw_paths = (values["user_resources"], values["config_root"], values["extensions_root"])
    if any(type(value) is not str for value in raw_paths):
        raise InstallerError("invalid Blender resource paths")
    resources, config, extensions = map(Path, raw_paths)
    try:
        for path in (resources, config, extensions):
            _absolute(path, "Blender resource path")
            _component_safe(path, allow_missing=True)
    except ValueError as exc:
        raise InstallerError("invalid Blender resource paths") from exc
    if not config.is_relative_to(resources) or not extensions.is_relative_to(resources):
        raise InstallerError("Blender resource path escaped its declared root")
    if "BLENDER_USER_RESOURCES" in env and (
        resources != Path(env["BLENDER_USER_RESOURCES"])
        or config != Path(env["BLENDER_USER_CONFIG"])
        or extensions != Path(env["BLENDER_USER_EXTENSIONS"])
    ):
        raise InstallerError("Blender reported a different isolated profile")
    return resources, config, extensions, ".".join(map(str, version)), architecture


def resolve_blender_paths(
    blender_bin: Path, env: Mapping[str, str], runner: Runner
) -> BlenderPaths:
    probe = _probe_blender(blender_bin, env, runner)
    resources, config, extensions, version, architecture = _paths_from_probe(
        blender_bin, env, probe
    )
    return BlenderPaths(blender_bin, architecture, version, resources, config, extensions)


def _payload_digest(entries: Sequence[PayloadEntry]) -> str:
    encoded = json.dumps(
        [
            {
                "path": entry.path,
                "kind": entry.kind,
                "mode": entry.mode,
                "size": entry.size,
                "sha256": entry.sha256,
            }
            for entry in entries
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_regular(path: Path, *, maximum: int) -> bytes:
    _absolute(path, "file")
    _component_safe(path, allow_missing=False)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or before.st_size > maximum:
        raise ValueError("unsafe regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ):
            raise ValueError("file changed while opening")
        chunks: list[bytes] = []
        size = 0
        while chunk := os.read(fd, min(1024 * 1024, maximum + 1 - size)):
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise ValueError("file is too large")
        after = os.fstat(fd)
        linked = path.stat(follow_symlinks=False)
        if any(
            (
                getattr(opened, field) != getattr(after, field)
                or getattr(after, field) != getattr(linked, field)
            )
            for field in ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
        ):
            raise ValueError("file changed while reading")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _load_extension_payload(raw: bytes) -> PayloadIndex:
    entries: dict[str, PayloadEntry] = {}
    manifest_raw: bytes | None = None
    total_size = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for item in archive.infolist():
                name = item.filename[:-1] if item.is_dir() else item.filename
                pure = PurePosixPath(name)
                if (
                    not name
                    or pure.is_absolute()
                    or any(part in {"", ".", ".."} for part in pure.parts)
                    or "\\" in name
                    or name in entries
                    or item.file_size > _MAX_ARCHIVE
                    or total_size + item.file_size > _MAX_ARCHIVE
                ):
                    raise ValueError("unsafe extension archive entry")
                total_size += item.file_size
                unix_mode = item.external_attr >> 16
                mode = stat.S_IMODE(unix_mode)
                kind = "dir" if item.is_dir() else "file"
                if (
                    mode == 0
                    or (kind == "dir" and unix_mode and not stat.S_ISDIR(unix_mode))
                    or (kind == "file" and unix_mode and not stat.S_ISREG(unix_mode))
                ):
                    raise ValueError("invalid extension archive mode")
                content = b"" if kind == "dir" else archive.read(item)
                entries[name] = PayloadEntry(
                    name,
                    kind,
                    mode,
                    0 if kind == "dir" else len(content),
                    None if kind == "dir" else hashlib.sha256(content).hexdigest(),
                )
                if name == "blender_manifest.toml" and kind == "file":
                    manifest_raw = content
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("invalid Blender extension ZIP") from exc
    if manifest_raw is None:
        raise ValueError("extension manifest is missing")
    try:
        manifest = tomllib.loads(manifest_raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("invalid extension manifest") from exc
    if manifest.get("id") != _EXTENSION_ID or manifest.get("version") != _EXTENSION_VERSION:
        raise ValueError("unexpected extension manifest identity")
    ordered = tuple(entries[path] for path in sorted(entries))
    return PayloadIndex(ordered, _payload_digest(ordered), _EXTENSION_ID, _EXTENSION_VERSION)


def load_extension_payload(extension_zip: Path) -> PayloadIndex:
    return _load_extension_payload(_read_regular(extension_zip, maximum=_MAX_ARCHIVE))


def _mapped_pyc(path: str, expected_files: set[str]) -> bool:
    pure = PurePosixPath(path)
    if pure.parent.name != "__pycache__":
        return False
    match = _PYC.fullmatch(pure.name)
    if match is None:
        return False
    source = pure.parent.parent / f"{match.group('stem')}.py"
    return source.as_posix() in expected_files


def compare_extension_tree(expected_payload: PayloadIndex, current: TreeRef) -> ExtensionComparison:
    if type(expected_payload) is not PayloadIndex or type(current) is not TreeRef:
        raise ValueError("invalid extension comparison input")
    image = current.capture()
    if image.state is ImageState.ABSENT:
        return ExtensionComparison(
            expected_payload,
            current,
            image,
            tuple(entry.path for entry in expected_payload.entries),
            (),
            (),
            (),
            (),
        )
    expected = {entry.path: entry for entry in expected_payload.entries}
    actual = {entry.path: entry for entry in image.entries}
    missing = tuple(sorted(set(expected) - set(actual)))
    changed = tuple(
        sorted(
            path
            for path in set(expected) & set(actual)
            if (
                actual[path].kind != expected[path].kind
                or actual[path].mode != expected[path].mode
                or (
                    expected[path].kind == "file"
                    and (
                        actual[path].size != expected[path].size
                        or actual[path].sha256 != expected[path].sha256
                    )
                )
            )
        )
    )
    expected_files = {path for path, entry in expected.items() if entry.kind == "file"}
    extras = set(actual) - set(expected)
    pyc = {
        path
        for path in extras
        if actual[path].kind == "file"
        and actual[path].uid == os.getuid()
        and _mapped_pyc(path, expected_files)
    }
    cache_dirs = {
        path
        for path in extras
        if actual[path].kind == "dir"
        and PurePosixPath(path).name == "__pycache__"
        and actual[path].uid == os.getuid()
    }
    used_cache_dirs = {PurePosixPath(path).parent.as_posix() for path in pyc}
    disposable_dirs = cache_dirs & used_cache_dirs
    foreign = tuple(sorted(extras - pyc - disposable_dirs))
    return ExtensionComparison(
        expected_payload,
        current,
        image,
        missing,
        changed,
        foreign,
        tuple(sorted(pyc)),
        tuple(sorted(disposable_dirs, key=lambda path: (-len(PurePosixPath(path).parts), path))),
    )


def _entry_matches(info: os.stat_result, entry: TreeEntry, digest: str | None = None) -> bool:
    return (
        info.st_dev == entry.dev
        and info.st_ino == entry.ino
        and info.st_uid == entry.uid
        and stat.S_IMODE(info.st_mode) == entry.mode
        and info.st_size == entry.size
        and info.st_mtime_ns == entry.mtime_ns
        and (digest is None or digest == entry.sha256)
    )


def prepare_extension_for_restore(comparison: ExtensionComparison) -> TreeImage:
    if type(comparison) is not ExtensionComparison or not comparison.exact:
        raise InstallerError("extension payload conflict")
    reference = comparison.current
    if reference.capture() != comparison.current_image:
        raise InstallerError("extension payload changed before cleanup")
    entries = {entry.path: entry for entry in comparison.current_image.entries}
    for path in comparison.disposable_pyc:
        relative = PurePath(*reference.relative.parts, *PurePosixPath(path).parts)
        parent_fd, name = reference.root.open_parent(relative)
        try:
            expected = entries[path]
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                info = os.fstat(fd)
                digest = hashlib.sha256()
                while chunk := os.read(fd, 1024 * 1024):
                    digest.update(chunk)
                if not _entry_matches(info, expected, digest.hexdigest()):
                    raise InstallerError("extension payload changed before cleanup")
            finally:
                os.close(fd)
            linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not _entry_matches(linked, expected):
                raise InstallerError("extension payload changed before cleanup")
            os.unlink(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    for path in comparison.disposable_dirs:
        relative = PurePath(*reference.relative.parts, *PurePosixPath(path).parts)
        parent_fd, name = reference.root.open_parent(relative)
        try:
            expected = entries[path]
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                not stat.S_ISDIR(info.st_mode)
                or info.st_dev != expected.dev
                or info.st_ino != expected.ino
                or info.st_uid != expected.uid
                or stat.S_IMODE(info.st_mode) != expected.mode
            ):
                raise InstallerError("extension cache directory changed before cleanup")
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                if os.listdir(fd):
                    raise InstallerError("extension cache directory is not empty")
            finally:
                os.close(fd)
            os.rmdir(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    result = reference.capture()
    if not compare_extension_tree(comparison.expected, reference).exact:
        raise InstallerError("extension payload conflict after cleanup")
    return result


def _tree_payload_digest(image: TreeImage) -> str | None:
    if image.state is ImageState.ABSENT:
        return None
    paths = {entry.path: entry for entry in image.entries}
    files = {path for path, entry in paths.items() if entry.kind == "file"}
    excluded_files = {path for path in files if _mapped_pyc(path, files)}
    excluded_dirs = {PurePosixPath(path).parent.as_posix() for path in excluded_files}
    payload = tuple(
        PayloadEntry(entry.path, entry.kind, entry.mode, entry.size, entry.sha256)
        for entry in image.entries
        if entry.path not in excluded_files and entry.path not in excluded_dirs
    )
    return _payload_digest(payload)


def _extension_snapshot(extensions_root: Path) -> tuple[TreeImage, TreeRef | None, SafeRoot | None]:
    if not extensions_root.exists():
        return TreeImage.absent(), None, None
    root = SafeRoot.open(extensions_root, os.getuid(), extensions_root)
    reference = TreeRef(root, PurePath(_REPOSITORY, _EXTENSION_ID))
    try:
        image = reference.capture()
    except BaseException:
        root.close()
        raise
    return image, reference, root


def _read_manifest(extension_root: Path) -> tuple[str | None, str | None]:
    manifest = extension_root / "blender_manifest.toml"
    if not manifest.exists():
        return None, None
    try:
        parsed = tomllib.loads(_read_regular(manifest, maximum=1024 * 1024).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InstallerError("invalid installed extension manifest") from exc
    identifier = parsed.get("id")
    version = parsed.get("version")
    if type(identifier) is not str or type(version) is not str:
        raise InstallerError("invalid installed extension manifest")
    return identifier, version


def _closed_probe_values(
    values: Mapping[str, object],
) -> tuple[str, bool, bool, str | None, int | None, bool | None]:
    repository = values["repository"]
    enabled = values["enabled"]
    online = values["online_access"]
    host = values["host"]
    port = values["port"]
    autostart = values["autostart"]
    if (
        type(repository) is not str
        or type(enabled) is not bool
        or type(online) is not bool
        or (host is not None and type(host) is not str)
        or (port is not None and (type(port) is not int or port < 0 or port > 65535))
        or (autostart is not None and type(autostart) is not bool)
    ):
        raise InstallerError("invalid Blender preference state")
    return repository, enabled, online, host, port, autostart


def inspect_blender(blender_bin: Path, env: Mapping[str, str], runner: Runner) -> BlenderState:
    probe = _probe_blender(blender_bin, env, runner)
    resources, config, extensions, version, architecture = _paths_from_probe(
        blender_bin, env, probe
    )
    repository, enabled, online, host, port, autostart = _closed_probe_values(probe.values)
    extension_root = extensions / repository / _EXTENSION_ID
    image, _, root = _extension_snapshot(extensions)
    try:
        manifest_id, manifest_version = (
            (None, None) if image.state is ImageState.ABSENT else _read_manifest(extension_root)
        )
        digest = _tree_payload_digest(image)
    finally:
        if root is not None:
            root.close()
    return BlenderState(
        blender_bin,
        probe.arches,
        Path(probe.values["binary_path"]),
        architecture,
        version,
        Path(env["HOME"]),
        resources,
        config,
        config / "userpref.blend",
        extensions,
        repository,
        extension_root,
        manifest_id,
        manifest_version,
        enabled,
        online,
        host,
        port,
        autostart,
        digest,
    )


def _current_comparison(
    state: BlenderState, payload: PayloadIndex
) -> tuple[ExtensionComparison, TreeImage]:
    image, reference, root = _extension_snapshot(state.extensions_root)
    if reference is None or root is None:
        raise InstallerError("extension payload is absent")
    try:
        comparison = compare_extension_tree(payload, reference)
        return comparison, image
    finally:
        root.close()


def verify_blender_files(state: BlenderState, expected_payload: PayloadIndex) -> None:
    try:
        manifest_id, manifest_version = _read_manifest(state.extension_root)
        comparison, _ = _current_comparison(state, expected_payload)
    except (OSError, ValueError, InstallerError) as exc:
        raise InstallerError("Blender file verification failed") from exc
    if (
        state.repository != _REPOSITORY
        or manifest_id != expected_payload.manifest_id
        or manifest_version != expected_payload.manifest_version
        or not comparison.exact
        or not state.enabled
        or not state.online_access
        or state.host != _HOST
        or state.port != _PORT
        or state.autostart is not True
    ):
        raise InstallerError("Blender file verification failed")


def _write_private(path: Path, raw: bytes, mode: int = 0o600) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.fchmod(fd, mode)
        offset = 0
        while offset < len(raw):
            offset += os.write(fd, raw[offset:])
        os.fsync(fd)
    finally:
        os.close(fd)


def _mkdirs_private(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    _component_safe(current, allow_missing=False)
    for item in reversed(missing):
        item.mkdir(mode=0o700)
        item.chmod(0o700)


def _capture_userpref(config: Path) -> FileImage:
    if not config.exists():
        return FileImage.absent()
    with SafeRoot.open(config, os.getuid(), config) as root:
        return capture_file(root, PurePath("userpref.blend"))


def _stage_env(state: BlenderState, stage: Path) -> dict[str, str]:
    resources = stage / "resources"
    return {
        "HOME": str(state.home),
        "BLENDER_USER_RESOURCES": str(resources),
        "BLENDER_USER_CONFIG": str(resources / "config"),
        "BLENDER_USER_EXTENSIONS": str(resources / "extensions"),
        "BLENDER_MCP_HOST": _HOST,
        "BLENDER_MCP_PORT": str(_PORT),
        "PATH": _path_env(state.executable),
    }


def _exact_state(state: BlenderState, payload: PayloadIndex) -> bool:
    if (
        state.repository != _REPOSITORY
        or state.manifest_id != payload.manifest_id
        or state.manifest_version != payload.manifest_version
        or state.canonical_payload_digest != payload.canonical_digest
        or not state.enabled
        or not state.online_access
        or state.host != _HOST
        or state.port != _PORT
        or state.autostart is not True
    ):
        return False
    try:
        comparison, _ = _current_comparison(state, payload)
    except InstallerError:
        return False
    return comparison.exact


def stage_blender_change(
    state: BlenderState,
    extension_zip: Path,
    install_stage: Path,
    authorizations: BlenderAuthorizations,
    runner: Runner,
) -> BlenderChange:
    if type(state) is not BlenderState or type(authorizations) is not BlenderAuthorizations:
        raise ValueError("invalid Blender staging input")
    if not authorizations.all_granted:
        raise ValueError("all four Blender authorizations are required")
    payload_raw = _read_regular(extension_zip, maximum=_MAX_ARCHIVE)
    payload = _load_extension_payload(payload_raw)
    if _exact_state(state, payload):
        image, _, root = _extension_snapshot(state.extensions_root)
        try:
            userpref = _capture_userpref(state.config_root)
        finally:
            if root is not None:
                root.close()
        return BlenderChange(
            False,
            None,
            state.extension_root,
            state.userpref,
            image,
            userpref,
            state,
            (),
        )
    _absolute(install_stage, "Blender install stage")
    if install_stage.exists():
        raise InstallerError("Blender install stage already exists")
    if install_stage.is_relative_to(state.user_resources) or state.user_resources.is_relative_to(
        install_stage
    ):
        raise ValueError("Blender install stage overlaps the live profile")
    resources = install_stage / "resources"
    config = resources / "config"
    extensions = resources / "extensions"
    _mkdirs_private(config)
    _mkdirs_private(extensions)
    staged_zip = install_stage / "mcp-1.0.0.zip"
    _write_private(staged_zip, payload_raw)
    pre_userpref = _capture_userpref(state.config_root)
    if pre_userpref.state is ImageState.PRESENT:
        pre_raw = _read_regular(state.userpref, maximum=64 * 1024 * 1024)
        if (
            _capture_userpref(state.config_root) != pre_userpref
            or len(pre_raw) != pre_userpref.size
            or hashlib.sha256(pre_raw).hexdigest() != pre_userpref.sha256
        ):
            raise InstallerError("Blender preferences changed before staging")
        _write_private(config / "userpref.blend", pre_raw, pre_userpref.mode)
    clean = _stage_env(state, install_stage)
    _run(
        runner,
        (str(state.executable), "--command", "extension", "validate", str(staged_zip)),
        cwd=state.executable.parent,
        env=clean,
        label="Blender extension validation",
    )
    _run(
        runner,
        (
            str(state.executable),
            "--command",
            "extension",
            "install-file",
            "--repo",
            _REPOSITORY,
            "--enable",
            str(staged_zip),
        ),
        cwd=state.executable.parent,
        env=clean,
        label="Blender extension installation",
    )
    _run(
        runner,
        (str(state.executable), "--background", "--python-expr", _PREFERENCES_EXPRESSION),
        cwd=state.executable.parent,
        env=clean,
        label="Blender preference staging",
    )
    staged_state = inspect_blender(state.executable, clean, runner)
    verify_blender_files(staged_state, payload)
    image, _, root = _extension_snapshot(staged_state.extensions_root)
    try:
        userpref = _capture_userpref(staged_state.config_root)
    finally:
        if root is not None:
            root.close()
    if userpref.state is not ImageState.PRESENT:
        raise InstallerError("staged Blender preferences are absent")
    compat = staged_state.extensions_root / ".cache/compat.dat"
    return BlenderChange(
        True,
        install_stage,
        staged_state.extension_root,
        staged_state.userpref,
        image,
        userpref,
        staged_state,
        (compat,) if compat.exists() else (),
    )


def _decimal(value: str, label: str) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise InstallerError(f"invalid lsof {label}")
    return int(value)


def _device(value: str) -> int:
    try:
        result = int(value, 16 if value.startswith("0x") else 10)
    except ValueError as exc:
        raise InstallerError("invalid lsof device") from exc
    if result < 0:
        raise InstallerError("invalid lsof device")
    return result


def _parse_lsof_processes(raw: str) -> tuple[_LsofProcess, ...]:
    processes: list[_LsofProcess] = []
    header: dict[str, str] | None = None
    files: list[_LsofFile] = []
    current: dict[str, str] | None = None

    def finish_file() -> None:
        nonlocal current
        if current is None:
            return
        if set(current) != {"f", "D", "i", "n"} or not current["f"] or not current["n"]:
            raise InstallerError("incomplete lsof file record")
        files.append(
            _LsofFile(
                current["f"],
                _device(current["D"]),
                _decimal(current["i"], "inode"),
                current["n"],
            )
        )
        current = None

    def finish_process() -> None:
        nonlocal header, files
        if header is None:
            return
        finish_file()
        if set(header) != {"p", "c", "u"} or not header["c"] or not files:
            raise InstallerError("incomplete lsof process record")
        processes.append(
            _LsofProcess(
                _decimal(header["p"], "PID"),
                header["c"],
                _decimal(header["u"], "UID"),
                tuple(files),
            )
        )
        header = None
        files = []

    if not raw or "\0" in raw:
        raise InstallerError("invalid lsof output")
    for line in raw.splitlines():
        if len(line) < 2 or line[0] not in "pcufDin":
            raise InstallerError("invalid lsof field")
        field, value = line[0], line[1:]
        if field == "p":
            finish_process()
            header = {"p": value}
        elif field == "f":
            if header is None:
                raise InstallerError("lsof file precedes process header")
            finish_file()
            current = {"f": value}
        elif field in {"c", "u"}:
            if header is None or current is not None or field in header:
                raise InstallerError("duplicate or misplaced lsof process field")
            header[field] = value
        else:
            if current is None or field in current:
                raise InstallerError("duplicate or misplaced lsof file field")
            current[field] = value
    finish_process()
    if not processes:
        raise InstallerError("invalid lsof output")
    return tuple(processes)


def _txt_output(pid: int, runner: Runner) -> tuple[_LsofProcess, ...]:
    _, output = _run(
        runner,
        ("/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "txt", "-FpcfDinu"),
        cwd=Path("/"),
        env={"PATH": _SYSTEM_PATH},
        label="Blender process probe",
    )
    processes = _parse_lsof_processes(output)
    if len(processes) != 1 or processes[0].pid != pid:
        raise InstallerError("ambiguous Blender process record")
    return processes


def _process_executable(
    process: _LsofProcess, selected_path: Path, selected: os.stat_result
) -> tuple[Path, bool]:
    if process.uid != os.getuid():
        raise InstallerError("Blender process belongs to another UID")
    candidates = [
        item
        for item in process.files
        if item.fd == "txt" and Path(item.path).name == selected_path.name
    ]
    if len(candidates) != 1:
        raise InstallerError("ambiguous Blender executable records")
    record = candidates[0]
    path = Path(record.path)
    try:
        _component_safe(path, allow_missing=False)
        info = path.stat(follow_symlinks=False)
    except (OSError, ValueError) as exc:
        raise InstallerError("invalid Blender executable record") from exc
    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (
        record.device,
        record.inode,
    ):
        raise InstallerError("Blender executable record identity mismatch")
    if path == selected_path and (record.device, record.inode) != (
        selected.st_dev,
        selected.st_ino,
    ):
        raise InstallerError("selected Blender executable identity mismatch")
    return path, path == selected_path and (record.device, record.inode) == (
        selected.st_dev,
        selected.st_ino,
    )


def probe_blender_lifecycle(blender_bin: Path, runner: Runner) -> BlenderLifecycle:
    with _open_executable(blender_bin) as (_, selected):
        code, output = _run(
            runner,
            ("/usr/bin/pgrep", "-x", "Blender"),
            cwd=Path("/"),
            env={"PATH": _SYSTEM_PATH},
            label="Blender process listing",
            accepted=(0, 1),
        )
        if code == 1:
            if output:
                raise InstallerError("invalid Blender process listing")
            pids: tuple[int, ...] = ()
        else:
            lines = output.splitlines()
            if not lines or any(not re.fullmatch(r"[1-9][0-9]*", line) for line in lines):
                raise InstallerError("invalid Blender process listing")
            pids = tuple(map(int, lines))
            if len(pids) != len(set(pids)):
                raise InstallerError("duplicate Blender process listing")
        matching: list[int] = []
        for pid in pids:
            process = _txt_output(pid, runner)[0]
            _, is_selected = _process_executable(process, blender_bin, selected)
            if is_selected:
                matching.append(pid)
        listener_code, listener_output = _run(
            runner,
            ("/usr/sbin/lsof", "-nP", "-iTCP:9876", "-sTCP:LISTEN", "-FpcfDinu"),
            cwd=Path("/"),
            env={"PATH": _SYSTEM_PATH},
            label="Blender listener probe",
            accepted=(0, 1),
        )
        if listener_code == 1:
            if listener_output:
                raise InstallerError("invalid Blender listener output")
            return BlenderLifecycle(tuple(matching), None, None, True)
        listeners = _parse_lsof_processes(listener_output)
        if len(listeners) != 1 or len(listeners[0].files) != 1:
            raise InstallerError("ambiguous Blender listener")
        listener = listeners[0]
        if listener.uid != os.getuid():
            raise InstallerError("Blender listener belongs to another UID")
        process = _txt_output(listener.pid, runner)[0]
        executable, _ = _process_executable(process, blender_bin, selected)
        return BlenderLifecycle(tuple(matching), listener.pid, executable, False)
