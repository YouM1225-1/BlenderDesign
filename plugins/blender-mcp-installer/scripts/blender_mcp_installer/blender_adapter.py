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
from dataclasses import dataclass, replace
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
_PATH_DISCOVERY_KEYS = {
    "binary_path",
    "version",
    "architecture",
    "user_resources",
    "config_root",
    "extensions_root",
}
_PATH_DISCOVERY_EXPRESSION = (
    "import bpy,json,platform;"
    "print('__BLENDER_MCP_INSTALLER__'+json.dumps({"
    "'binary_path':bpy.app.binary_path,'version':list(bpy.app.version),"
    "'architecture':platform.machine(),"
    "'user_resources':bpy.utils.resource_path('USER'),"
    "'config_root':bpy.utils.user_resource('CONFIG'),"
    "'extensions_root':bpy.utils.user_resource('EXTENSIONS')},sort_keys=True))"
)
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
    provenance: TreeImage | None
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
    device: int | None
    inode: int | None
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


def _open_directory_fd(path: Path, *, create_private: bool = False) -> int:
    _absolute(path, "directory")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            created = False
            try:
                before = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                if not create_private or os.fstat(fd).st_uid != os.getuid():
                    raise ValueError("path component is missing") from None
                os.mkdir(part, mode=0o700, dir_fd=fd)
                os.chmod(part, 0o700, dir_fd=fd, follow_symlinks=False)
                before = os.stat(part, dir_fd=fd, follow_symlinks=False)
                created = True
            if not stat.S_ISDIR(before.st_mode):
                raise ValueError("path component is not a directory")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                opened = os.fstat(child)
                if (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_mode) != (
                    before.st_dev,
                    before.st_ino,
                    before.st_uid,
                    before.st_mode,
                ):
                    raise ValueError("directory changed while opening")
                if created:
                    if opened.st_uid != os.getuid() or stat.S_IMODE(opened.st_mode) != 0o700:
                        raise ValueError("created directory has unsafe ownership or mode")
                    os.fsync(child)
                    os.fsync(fd)
                os.close(fd)
            except BaseException:
                os.close(child)
                raise
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _linked_file(path: Path, retained_parent: int, expected: os.stat_result) -> None:
    current_parent = _open_directory_fd(path.parent)
    try:
        retained = os.fstat(retained_parent)
        current = os.fstat(current_parent)
        linked = os.stat(path.name, dir_fd=current_parent, follow_symlinks=False)
        if (retained.st_dev, retained.st_ino) != (current.st_dev, current.st_ino) or any(
            getattr(linked, field) != getattr(expected, field)
            for field in ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
        ):
            raise ValueError("file path identity changed")
    finally:
        os.close(current_parent)


@contextmanager
def _open_executable(path: Path) -> Iterator[tuple[int, int, os.stat_result]]:
    _absolute(path, "Blender executable")
    parent_fd = _open_directory_fd(path.parent)
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
            yield fd, parent_fd, opened
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
        "PYTHONDONTWRITEBYTECODE": "1",
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


def _parse_probe(raw: str, expected_keys: set[str]) -> Mapping[str, object]:
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
    if type(value) is not dict or frozenset(value) not in {
        frozenset(expected_keys),
        frozenset(_DISCOVERY_KEYS),
    }:
        raise InstallerError("invalid Blender discovery output")
    return MappingProxyType({key: value[key] for key in expected_keys})


def _probe_blender(
    blender_bin: Path,
    env: Mapping[str, str],
    runner: Runner,
    *,
    factory_startup: bool = False,
) -> _Probe:
    clean = _profile_env(blender_bin, env)
    with _open_executable(blender_bin) as (_, parent_fd, selected):
        _, arch_output = _run(
            runner,
            ("/usr/bin/lipo", "-archs", str(blender_bin)),
            cwd=blender_bin.parent,
            env=clean,
            label="Blender architecture probe",
        )
        arches = _parse_arches(arch_output)
        _linked_file(blender_bin, parent_fd, selected)
        argv = [str(blender_bin), "--background"]
        if factory_startup:
            argv.append("--factory-startup")
        argv.extend(
            (
                "--python-expr",
                _PATH_DISCOVERY_EXPRESSION if factory_startup else _DISCOVERY_EXPRESSION,
            )
        )
        _, output = _run(
            runner,
            tuple(argv),
            cwd=blender_bin.parent,
            env=clean,
            label="Blender discovery",
        )
        values = _parse_probe(output, _PATH_DISCOVERY_KEYS if factory_startup else _DISCOVERY_KEYS)
        reported = Path(values["binary_path"]) if type(values["binary_path"]) is str else Path()
        if reported != blender_bin:
            raise InstallerError("Blender reported a different executable")
        try:
            _linked_file(reported, parent_fd, selected)
        except ValueError as exc:
            raise InstallerError("Blender executable identity changed") from exc
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
    probe = _probe_blender(blender_bin, env, runner, factory_startup=True)
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
    parent_fd = _open_directory_fd(path.parent)
    try:
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_size > maximum
        ):
            raise ValueError("unsafe regular file")
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
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
            linked = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if any(
                (
                    getattr(opened, field) != getattr(after, field)
                    or getattr(after, field) != getattr(linked, field)
                )
                for field in (
                    "st_dev",
                    "st_ino",
                    "st_uid",
                    "st_mode",
                    "st_size",
                    "st_mtime_ns",
                )
            ):
                raise ValueError("file changed while reading")
            return b"".join(chunks)
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)


def _load_extension_payload(raw: bytes) -> PayloadIndex:
    entries: dict[str, PayloadEntry] = {}
    manifest_raw: bytes | None = None
    total_size = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for item in archive.infolist():
                raw_name = item.filename
                directory = item.is_dir()
                name = raw_name[:-1] if directory else raw_name
                components = name.split("/")
                if (
                    not name
                    or raw_name != name + ("/" if directory else "")
                    or any(not part or part in {".", ".."} for part in components)
                    or "\\" in raw_name
                ):
                    raise ValueError("unsafe extension archive entry")
                pure = PurePosixPath(name)
                if (
                    pure.is_absolute()
                    or pure.as_posix() != name
                    or name in entries
                    or item.file_size > _MAX_ARCHIVE
                    or total_size + item.file_size > _MAX_ARCHIVE
                ):
                    raise ValueError("unsafe extension archive entry")
                total_size += item.file_size
                unix_mode = item.external_attr >> 16
                mode = stat.S_IMODE(unix_mode)
                kind = "dir" if directory else "file"
                if (
                    item.create_system != 3
                    or (
                        kind == "dir"
                        and (stat.S_IFMT(unix_mode), mode, item.file_size)
                        != (stat.S_IFDIR, 0o755, 0)
                    )
                    or (kind == "file" and (stat.S_IFMT(unix_mode), mode) != (stat.S_IFREG, 0o644))
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
    if any(
        parent.as_posix() in entries and entries[parent.as_posix()].kind != "dir"
        for name in entries
        for parent in PurePosixPath(name).parents
        if parent != PurePosixPath(".")
    ):
        raise ValueError("extension archive path crosses a file")
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


def _compile_expression(payload: PayloadIndex) -> str:
    sources = tuple(
        entry.path
        for entry in payload.entries
        if entry.kind == "file" and entry.path.endswith(".py")
    )
    if not sources:
        raise ValueError("extension payload has no Python sources")
    return (
        "import importlib.util,os,pathlib,py_compile;"
        "r=pathlib.Path(os.environ['BLENDER_USER_EXTENSIONS'])/'user_default'/'mcp';"
        f"s={sources!r};"
        "[(lambda p,n:py_compile.compile(str(p),"
        "cfile=importlib.util.cache_from_source(str(p),optimization=''),"
        "dfile=n,doraise=True,optimize=0,"
        "invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH))(r/n,n) for n in s]"
    )


def _mapped_source(path: str, expected_files: set[str]) -> str | None:
    pure = PurePosixPath(path)
    if pure.parent.name != "__pycache__":
        return None
    match = _PYC.fullmatch(pure.name)
    if match is None:
        return None
    source = pure.parent.parent / f"{match.group('stem')}.py"
    return source.as_posix() if source.as_posix() in expected_files else None


def _mapped_pyc(path: str, expected_files: set[str]) -> bool:
    return _mapped_source(path, expected_files) is not None


def _provenance_extras(
    expected: Mapping[str, PayloadEntry], provenance: TreeImage | None
) -> tuple[dict[str, TreeEntry], set[str], set[str]]:
    if provenance is None:
        return {}, set(), set()
    if type(provenance) is not TreeImage or provenance.state is not ImageState.PRESENT:
        raise ValueError("invalid extension pyc provenance")
    expected_files = {path for path, entry in expected.items() if entry.kind == "file"}
    sources = {path for path in expected_files if path.endswith(".py")}
    extras = {entry.path: entry for entry in provenance.entries if entry.path not in expected}
    pyc = {
        path: source
        for path, entry in extras.items()
        if entry.kind == "file"
        and entry.uid == os.getuid()
        and entry.mode == 0o644
        and (source := _mapped_source(path, expected_files)) is not None
    }
    cache_dirs = {PurePosixPath(path).parent.as_posix() for path in pyc}
    if (
        len(pyc) != len(sources)
        or set(pyc.values()) != sources
        or set(extras) != set(pyc) | cache_dirs
        or any(
            extras[path].kind != "dir"
            or extras[path].uid != os.getuid()
            or extras[path].mode != 0o755
            for path in cache_dirs
        )
    ):
        raise ValueError("invalid extension pyc provenance")
    return extras, set(pyc), cache_dirs


def compare_extension_tree(
    expected_payload: PayloadIndex,
    current: TreeRef,
    provenance: TreeImage | None = None,
) -> ExtensionComparison:
    if type(expected_payload) is not PayloadIndex or type(current) is not TreeRef:
        raise ValueError("invalid extension comparison input")
    expected = {entry.path: entry for entry in expected_payload.entries}
    provenance_entries, provenance_pyc, provenance_dirs = _provenance_extras(expected, provenance)
    image = current.capture()
    if image.state is ImageState.ABSENT:
        return ExtensionComparison(
            expected_payload,
            provenance,
            current,
            image,
            tuple(sorted(set(expected) | set(provenance_entries))),
            (),
            (),
            (),
            (),
        )
    actual = {entry.path: entry for entry in image.entries}
    missing = tuple(sorted((set(expected) | set(provenance_entries)) - set(actual)))
    changed_payload = {
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
    }
    changed_provenance = {
        path
        for path in set(provenance_entries) & set(actual)
        if actual[path] != provenance_entries[path]
    }
    changed = tuple(sorted(changed_payload | changed_provenance))
    extras = set(actual) - set(expected)
    exact_provenance = {
        path
        for path in extras & set(provenance_entries)
        if actual[path] == provenance_entries[path]
    }
    pyc = exact_provenance & provenance_pyc
    disposable_dirs = exact_provenance & provenance_dirs
    foreign = tuple(sorted(extras - set(provenance_entries)))
    return ExtensionComparison(
        expected_payload,
        provenance,
        current,
        image,
        missing,
        changed,
        foreign,
        tuple(sorted(pyc)),
        tuple(sorted(disposable_dirs, key=lambda path: (-len(PurePosixPath(path).parts), path))),
    )


def prepare_extension_for_restore(
    comparison: ExtensionComparison, expected_image: TreeImage | None = None
) -> TreeImage:
    if (
        type(comparison) is not ExtensionComparison
        or not comparison.exact
        or (expected_image is not None and type(expected_image) is not TreeImage)
        or (
            (comparison.disposable_pyc or comparison.disposable_dirs)
            and expected_image != comparison.provenance
        )
    ):
        raise InstallerError("extension payload conflict")
    reference = comparison.current
    if reference.capture() != comparison.current_image:
        raise InstallerError("extension payload changed before cleanup")
    result = reference.capture()
    if expected_image is not None and result != expected_image:
        if (
            expected_image.state is not ImageState.PRESENT
            or expected_image.mtime_ns is None
            or (
                result.state,
                result.dev,
                result.ino,
                result.uid,
                result.mode,
                result.digest,
                result.entries,
            )
            != (
                expected_image.state,
                expected_image.dev,
                expected_image.ino,
                expected_image.uid,
                expected_image.mode,
                expected_image.digest,
                expected_image.entries,
            )
        ):
            raise InstallerError("extension payload conflict after cleanup")
        fd = reference.root.open_directory(reference.relative)
        try:
            info = os.fstat(fd)
            if (
                info.st_dev,
                info.st_ino,
                info.st_uid,
                stat.S_IMODE(info.st_mode),
                info.st_mtime_ns,
            ) != (result.dev, result.ino, result.uid, result.mode, result.mtime_ns):
                raise InstallerError("extension payload changed before metadata restore")
            os.utime(fd, ns=(info.st_atime_ns, expected_image.mtime_ns))
            os.fsync(fd)
        finally:
            os.close(fd)
        result = reference.capture()
        if result != expected_image:
            raise InstallerError("extension payload conflict after metadata restore")
    if not compare_extension_tree(comparison.expected, reference, comparison.provenance).exact:
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
        PayloadEntry(
            entry.path,
            entry.kind,
            entry.mode,
            0 if entry.kind == "dir" else entry.size,
            entry.sha256,
        )
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
    state: BlenderState, payload: PayloadIndex, provenance: TreeImage | None = None
) -> tuple[ExtensionComparison, TreeImage]:
    image, reference, root = _extension_snapshot(state.extensions_root)
    if reference is None or root is None:
        raise InstallerError("extension payload is absent")
    try:
        comparison = compare_extension_tree(payload, reference, provenance)
        return comparison, image
    finally:
        root.close()


def verify_blender_payload(
    state: BlenderState,
    expected_payload: PayloadIndex,
    provenance: TreeImage | None = None,
) -> None:
    try:
        manifest_id, manifest_version = _read_manifest(state.extension_root)
        comparison, _ = _current_comparison(state, expected_payload, provenance)
    except (OSError, ValueError, InstallerError) as exc:
        raise InstallerError("Blender file verification failed") from exc
    identity_only = False
    if (
        provenance is not None
        and not comparison.missing
        and comparison.changed
        and not comparison.foreign
    ):
        payload_paths = {entry.path for entry in expected_payload.entries}
        recorded = {
            entry.path: entry
            for entry in provenance.entries
            if entry.path not in payload_paths
        }
        actual = {entry.path: entry for entry in comparison.current_image.entries}
        identity_only = set(comparison.changed) <= set(recorded) and all(
            actual[path]
            == replace(
                recorded[path],
                dev=actual[path].dev,
                ino=actual[path].ino,
                mtime_ns=actual[path].mtime_ns,
            )
            for path in comparison.changed
        )
    if (
        manifest_id != expected_payload.manifest_id
        or manifest_version != expected_payload.manifest_version
        or not (comparison.exact or identity_only)
    ):
        raise InstallerError("Blender file verification failed")


def verify_blender_files(
    state: BlenderState,
    expected_payload: PayloadIndex,
    provenance: TreeImage | None = None,
) -> None:
    verify_blender_payload(state, expected_payload, provenance)
    if (
        state.repository != _REPOSITORY
        or not state.enabled
        or not state.online_access
        or state.host != _HOST
        or state.port != _PORT
        or state.autostart is not True
    ):
        raise InstallerError("Blender file verification failed")


def _create_private_directory(parent_fd: int, name: str) -> int:
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        os.fchmod(fd, 0o700)
        opened = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) != 0o700
            or (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_mode)
            != (linked.st_dev, linked.st_ino, linked.st_uid, linked.st_mode)
        ):
            raise ValueError("created private directory identity mismatch")
        os.fsync(fd)
        os.fsync(parent_fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _write_private_at(parent_fd: int, name: str, raw: bytes, mode: int = 0o600) -> None:
    if type(raw) is not bytes or type(mode) is not int or mode < 0 or mode > 0o777:
        raise ValueError("invalid private file")
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode,
        dir_fd=parent_fd,
    )
    try:
        os.fchmod(fd, mode)
        offset = 0
        while offset < len(raw):
            offset += os.write(fd, raw[offset:])
        os.fsync(fd)
        opened = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) != mode
            or any(
                getattr(opened, field) != getattr(linked, field)
                for field in ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
            )
        ):
            raise ValueError("created private file identity mismatch")
    finally:
        os.close(fd)
    os.fsync(parent_fd)


def _stage_is_linked(path: Path, parent_fd: int, stage_fd: int) -> None:
    current_parent = _open_directory_fd(path.parent)
    try:
        retained_parent = os.fstat(parent_fd)
        current = os.fstat(current_parent)
        retained = os.fstat(stage_fd)
        linked = os.stat(path.name, dir_fd=current_parent, follow_symlinks=False)
        if (
            (retained_parent.st_dev, retained_parent.st_ino) != (current.st_dev, current.st_ino)
            or not stat.S_ISDIR(linked.st_mode)
            or retained.st_uid != os.getuid()
            or stat.S_IMODE(retained.st_mode) != 0o700
            or (retained.st_dev, retained.st_ino, retained.st_uid, retained.st_mode)
            != (linked.st_dev, linked.st_ino, linked.st_uid, linked.st_mode)
        ):
            raise InstallerError("Blender install stage identity changed")
    except (OSError, ValueError) as exc:
        raise InstallerError("Blender install stage identity changed") from exc
    finally:
        os.close(current_parent)


def _fsync_file_at(parent_fd: int, name: str, uid: int) -> None:
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != uid:
        raise InstallerError("unsafe staged Blender file")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        if any(
            getattr(opened, field) != getattr(before, field)
            for field in ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
        ):
            raise InstallerError("staged Blender file changed while opening")
        os.fsync(fd)
        after = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if any(
            getattr(opened, field) != getattr(after, field)
            or getattr(after, field) != getattr(linked, field)
            for field in ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
        ):
            raise InstallerError("staged Blender file changed during fsync")
    finally:
        os.close(fd)


def _fsync_tree_at(parent_fd: int, name: str, uid: int) -> None:
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode) or before.st_uid != uid:
        raise InstallerError("unsafe staged Blender directory")
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_mode) != (
            before.st_dev,
            before.st_ino,
            before.st_uid,
            before.st_mode,
        ):
            raise InstallerError("staged Blender directory changed while opening")
        names = sorted(os.listdir(fd))
        for child in names:
            info = os.stat(child, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):
                _fsync_file_at(fd, child, uid)
            elif stat.S_ISDIR(info.st_mode):
                _fsync_tree_at(fd, child, uid)
            else:
                raise InstallerError("unsafe staged Blender tree entry")
        os.fsync(fd)
        after = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            names != sorted(os.listdir(fd))
            or (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_mode)
            != (after.st_dev, after.st_ino, after.st_uid, after.st_mode)
            or (after.st_dev, after.st_ino, after.st_uid, after.st_mode)
            != (linked.st_dev, linked.st_ino, linked.st_uid, linked.st_mode)
        ):
            raise InstallerError("staged Blender directory changed during fsync")
    finally:
        os.close(fd)


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
        "PYTHONDONTWRITEBYTECODE": "1",
    }


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
    _absolute(install_stage, "Blender install stage")
    if install_stage.is_relative_to(state.user_resources) or state.user_resources.is_relative_to(
        install_stage
    ):
        raise ValueError("Blender install stage overlaps the live profile")
    parent_fd = _open_directory_fd(install_stage.parent, create_private=True)
    try:
        parent_info = os.fstat(parent_fd)
        if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid():
            raise ValueError("Blender install stage parent must be current-UID-owned")
        try:
            os.stat(install_stage.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise InstallerError("Blender install stage already exists")
        stage_fd = _create_private_directory(parent_fd, install_stage.name)
        with SafeRoot(install_stage, os.getuid(), stage_fd) as stage_root:
            resources_fd = _create_private_directory(stage_root.fd, "resources")
            try:
                config_fd = _create_private_directory(resources_fd, "config")
                os.close(config_fd)
                extensions_fd = _create_private_directory(resources_fd, "extensions")
                os.close(extensions_fd)
            finally:
                os.close(resources_fd)
            staged_zip = install_stage / "mcp-1.0.0.zip"
            _write_private_at(stage_root.fd, staged_zip.name, payload_raw)
            staged_zip_image = capture_file(stage_root, PurePath(staged_zip.name))
            pre_userpref = _capture_userpref(state.config_root)
            if pre_userpref.state is ImageState.PRESENT:
                pre_raw = _read_regular(state.userpref, maximum=64 * 1024 * 1024)
                if (
                    _capture_userpref(state.config_root) != pre_userpref
                    or len(pre_raw) != pre_userpref.size
                    or hashlib.sha256(pre_raw).hexdigest() != pre_userpref.sha256
                ):
                    raise InstallerError("Blender preferences changed before staging")
                config_fd = stage_root.open_directory(PurePath("resources", "config"))
                try:
                    _write_private_at(config_fd, "userpref.blend", pre_raw, pre_userpref.mode)
                finally:
                    os.close(config_fd)
            clean = _stage_env(state, install_stage)
            with _open_executable(state.executable) as (
                _,
                executable_parent,
                executable_info,
            ):
                commands = (
                    (
                        (
                            str(state.executable),
                            "--command",
                            "extension",
                            "validate",
                            str(staged_zip),
                        ),
                        "Blender extension validation",
                    ),
                    (
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
                        "Blender extension installation",
                    ),
                    (
                        (
                            str(state.executable),
                            "--background",
                            "--python-expr",
                            _compile_expression(payload),
                        ),
                        "Blender extension bytecode compilation",
                    ),
                    (
                        (
                            str(state.executable),
                            "--background",
                            "--python-expr",
                            _PREFERENCES_EXPRESSION,
                        ),
                        "Blender preference staging",
                    ),
                )
                for argv, label in commands:
                    _linked_file(state.executable, executable_parent, executable_info)
                    _stage_is_linked(install_stage, parent_fd, stage_root.fd)
                    _run(
                        runner,
                        argv,
                        cwd=state.executable.parent,
                        env=clean,
                        label=label,
                    )
                    _stage_is_linked(install_stage, parent_fd, stage_root.fd)
            if capture_file(stage_root, PurePath(staged_zip.name)) != staged_zip_image:
                raise InstallerError("staged Blender ZIP changed during installation")
            extension_relative = PurePath("resources", "extensions", _REPOSITORY, _EXTENSION_ID)
            extension = TreeRef(stage_root, extension_relative)
            image = extension.capture()
            comparison = compare_extension_tree(payload, extension, image)
            if not comparison.exact:
                raise InstallerError("staged Blender extension changed before verification")
            staged_state = inspect_blender(state.executable, clean, runner)
            _stage_is_linked(install_stage, parent_fd, stage_root.fd)
            verify_blender_files(staged_state, payload, image)
            _stage_is_linked(install_stage, parent_fd, stage_root.fd)
            extension_parent, extension_name = stage_root.open_parent(extension_relative)
            try:
                _fsync_tree_at(extension_parent, extension_name, os.getuid())
                os.fsync(extension_parent)
            finally:
                os.close(extension_parent)
            extensions_fd = stage_root.open_directory(PurePath("resources", "extensions"))
            try:
                os.fsync(extensions_fd)
            finally:
                os.close(extensions_fd)
            userpref_relative = PurePath("resources", "config", "userpref.blend")
            userpref_before = capture_file(stage_root, userpref_relative)
            if userpref_before.state is not ImageState.PRESENT:
                raise InstallerError("staged Blender preferences are absent")
            config_fd, userpref_name = stage_root.open_parent(userpref_relative)
            try:
                _fsync_file_at(config_fd, userpref_name, os.getuid())
                os.fsync(config_fd)
            finally:
                os.close(config_fd)
            userpref = capture_file(stage_root, userpref_relative)
            if extension.capture() != image or userpref != userpref_before:
                raise InstallerError("staged Blender extension changed during fsync")
            _stage_is_linked(install_stage, parent_fd, stage_root.fd)
            compat_relative = PurePath("resources", "extensions", ".cache", "compat.dat")
            try:
                compat_parent, compat_name = stage_root.open_parent(compat_relative)
            except FileNotFoundError:
                compat_present = False
            else:
                try:
                    compat_info = os.stat(compat_name, dir_fd=compat_parent, follow_symlinks=False)
                    if not stat.S_ISREG(compat_info.st_mode) or compat_info.st_uid != os.getuid():
                        raise InstallerError("unsafe staged Blender compatibility cache")
                    compat_present = True
                except FileNotFoundError:
                    compat_present = False
                finally:
                    os.close(compat_parent)
    finally:
        os.close(parent_fd)
    if userpref.state is not ImageState.PRESENT:
        raise InstallerError("staged Blender preferences are absent")
    compat = staged_state.extensions_root / ".cache/compat.dat"
    return BlenderChange(
        staged_state.extension_root,
        staged_state.userpref,
        image,
        userpref,
        staged_state,
        (compat,) if compat_present else (),
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


def _parse_lsof(raw: str, *, listener: bool) -> tuple[_LsofProcess, ...]:
    if not raw or "\0" in raw or len(raw.encode("utf-8")) > _MAX_OUTPUT:
        raise InstallerError("invalid lsof output")
    lines = raw.splitlines()
    processes: list[_LsofProcess] = []
    index = 0
    while index < len(lines):
        if index + 3 > len(lines) or [line[:1] for line in lines[index : index + 3]] != [
            "p",
            "c",
            "u",
        ]:
            raise InstallerError("invalid lsof process record")
        pid_raw, command, uid_raw = (line[1:] for line in lines[index : index + 3])
        pid = _decimal(pid_raw, "PID")
        uid = _decimal(uid_raw, "UID")
        if pid == 0 or not command:
            raise InstallerError("invalid lsof process record")
        index += 3
        files: list[_LsofFile] = []
        while index < len(lines) and lines[index].startswith("f"):
            fd = lines[index][1:]
            if not fd:
                raise InstallerError("invalid lsof file descriptor")
            if listener:
                if index + 2 > len(lines) or lines[index + 1][:1] != "n":
                    raise InstallerError("invalid lsof listener record")
                path = lines[index + 1][1:]
                if (
                    not re.fullmatch(r"[0-9]+", fd)
                    or not path
                    or any(character.isspace() for character in path)
                    or not path.endswith(":9876")
                ):
                    raise InstallerError("invalid lsof listener record")
                files.append(_LsofFile(fd, None, None, path))
                index += 2
            else:
                if (
                    fd != "txt"
                    or index + 4 > len(lines)
                    or [line[:1] for line in lines[index + 1 : index + 4]] != ["D", "i", "n"]
                ):
                    raise InstallerError("invalid lsof txt record")
                device, inode, path = (line[1:] for line in lines[index + 1 : index + 4])
                if not path:
                    raise InstallerError("invalid lsof txt record")
                files.append(_LsofFile(fd, _device(device), _decimal(inode, "inode"), path))
                index += 4
        if not files:
            raise InstallerError("incomplete lsof process record")
        if index < len(lines) and not lines[index].startswith("p"):
            raise InstallerError("unknown or misplaced lsof field")
        processes.append(_LsofProcess(pid, command, uid, tuple(files)))
    return tuple(processes)


def _parse_lsof_txt(raw: str) -> tuple[_LsofProcess, ...]:
    return _parse_lsof(raw, listener=False)


def _parse_lsof_listener(raw: str) -> tuple[_LsofProcess, ...]:
    processes = _parse_lsof(raw, listener=True)
    if len(processes) != 1 or len(processes[0].files) != 1:
        raise InstallerError("ambiguous Blender listener")
    return processes


def _txt_output(pid: int, runner: Runner) -> tuple[_LsofProcess, ...]:
    _, output = _run(
        runner,
        ("/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "txt", "-FpcfDinu"),
        cwd=Path("/"),
        env={"PATH": _SYSTEM_PATH},
        label="Blender process probe",
    )
    processes = _parse_lsof_txt(output)
    if len(processes) != 1 or processes[0].pid != pid:
        raise InstallerError("ambiguous Blender process record")
    return processes


def _process_executable(
    process: _LsofProcess,
    selected_path: Path,
    selected: os.stat_result,
) -> tuple[Path, bool]:
    if process.uid != os.getuid():
        raise InstallerError("Blender process belongs to another UID")
    if any(
        item.path == str(selected_path)
        and (item.device, item.inode) == (selected.st_dev, selected.st_ino)
        for item in process.files[1:]
    ):
        raise InstallerError("ambiguous Blender executable records")
    # Darwin lsof emits the process's main executable as the first -d txt record,
    # followed by loaded libraries and dyld. The disposable parser probe guards this.
    record = process.files[0]
    if record.device is None or record.inode is None:
        raise InstallerError("invalid Blender executable record")
    path = Path(record.path)
    try:
        _absolute(path, "lsof executable")
        parent_fd = _open_directory_fd(path.parent)
        try:
            before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                info = os.fstat(fd)
            finally:
                os.close(fd)
            linked = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            _linked_file(path, parent_fd, info)
        finally:
            os.close(parent_fd)
    except (OSError, ValueError) as exc:
        raise InstallerError("invalid Blender executable record") from exc
    if (
        not stat.S_ISREG(info.st_mode)
        or not info.st_mode & 0o111
        or any(
            getattr(before, field) != getattr(info, field)
            or getattr(info, field) != getattr(linked, field)
            for field in ("st_dev", "st_ino", "st_uid", "st_mode")
        )
        or (info.st_dev, info.st_ino) != (record.device, record.inode)
    ):
        raise InstallerError("Blender executable record identity mismatch")
    selected_path_match = record.path == str(selected_path)
    if selected_path_match and (record.device, record.inode) != (
        selected.st_dev,
        selected.st_ino,
    ):
        raise InstallerError("selected Blender executable identity mismatch")
    return path, selected_path_match and (record.device, record.inode) == (
        selected.st_dev,
        selected.st_ino,
    )


def probe_blender_lifecycle(blender_bin: Path, runner: Runner) -> BlenderLifecycle:
    with _open_executable(blender_bin) as (_, selected_parent, selected):
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
            if process.command != "Blender":
                raise InstallerError("invalid Blender process command")
            _, is_selected = _process_executable(
                process,
                blender_bin,
                selected,
            )
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
            try:
                _linked_file(blender_bin, selected_parent, selected)
            except ValueError as exc:
                raise InstallerError("selected Blender executable identity changed") from exc
            return BlenderLifecycle(tuple(matching), None, None, True)
        listeners = _parse_lsof_listener(listener_output)
        if len(listeners) != 1:
            raise InstallerError("ambiguous Blender listener")
        listener = listeners[0]
        if listener.uid != os.getuid():
            raise InstallerError("Blender listener belongs to another UID")
        process = _txt_output(listener.pid, runner)[0]
        executable, _ = _process_executable(
            process,
            blender_bin,
            selected,
        )
        try:
            _linked_file(blender_bin, selected_parent, selected)
        except ValueError as exc:
            raise InstallerError("selected Blender executable identity changed") from exc
        return BlenderLifecycle(tuple(matching), listener.pid, executable, False)
