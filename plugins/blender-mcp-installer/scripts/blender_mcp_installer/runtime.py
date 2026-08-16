from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Iterator, Mapping, Sequence

from .bundle import ReleaseManifest, Runner, StagedBundle, validate_runtime_lock
from .codex_adapter import ManagedProfile
from .filesystem import InstallerError, StagedTree, TargetRef, capture_tree
from .model import ImageState, TreeImage


_INDEX = "https://pypi.org/simple"
_ENTRY_POINT = "blender-mcp = blmcp:main"
_MARKER = ".blender-mcp-runtime.json"
_LOCK_COPY = ".blender-mcp-runtime.lock"
_LAUNCHER = "bin/blender-mcp-managed"
_NAME = re.compile(r"[-_.]+")
_VERSION = re.compile(r"3\.13\.\d+\Z")
_MAX_MARKER = 1024 * 1024

_PROBE = r"""
import importlib.metadata as metadata
import importlib.util
import importlib
import json
import pathlib
import pkgutil
import sys

distributions = {}
for item in metadata.distributions():
    name = item.metadata.get("Name")
    if name:
        distributions[name.lower().replace("_", "-")] = item.version
points = [
    point for point in metadata.entry_points(group="console_scripts")
    if point.name == "blender-mcp" and point.dist.name.lower().replace("_", "-") == "blender-mcp"
]
if len(points) != 1:
    raise SystemExit(2)
spec = importlib.util.find_spec("blmcp")
if spec is None or spec.origin is None:
    raise SystemExit(2)
from mcp.server.fastmcp import FastMCP
import blmcp.tools as tools_package
mcp = FastMCP("blender-mcp-runtime-probe")
for _importer, module_name, _is_package in pkgutil.iter_modules(tools_package.__path__):
    if module_name.endswith("_toolcode") or module_name.startswith("_template_"):
        continue
    module = importlib.import_module(f"blmcp.tools.{module_name}")
    if hasattr(module, "register"):
        module.register(mcp)
print(json.dumps({
    "python_version": ".".join(map(str, sys.version_info[:3])),
    "distributions": dict(sorted(distributions.items())),
    "entry_point": f"{points[0].name} = {points[0].value}",
    "entry_point_path": str(pathlib.Path(sys.executable).with_name("blender-mcp")),
    "module_path": spec.origin,
    "tools": list(mcp._tool_manager._tools),
}, sort_keys=True))
""".strip()


def _absolute(path: Path, label: str) -> Path:
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be an absolute lexical path")
    return path


def _normalized(name: str) -> str:
    return _NAME.sub("-", name).lower()


def _profile_env(profile: ManagedProfile) -> dict[str, str]:
    if type(profile) is not ManagedProfile:
        raise ValueError("invalid managed profile")
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(profile.home),
        "BLENDER_USER_RESOURCES": str(profile.blender_user_resources),
        "BLENDER_USER_CONFIG": str(profile.blender_user_config),
        "BLENDER_USER_EXTENSIONS": str(profile.blender_user_extensions),
        "BLENDER_PATH": str(profile.blender_path),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }


def _install_env(profile: ManagedProfile) -> dict[str, str]:
    return {
        **_profile_env(profile),
        "UV_REQUIRE_HASHES": "1",
        "UV_NO_BUILD": "1",
        "UV_DEFAULT_INDEX": _INDEX,
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _launcher_source(environment: Mapping[str, str]) -> bytes:
    clean = dict(sorted(environment.items()))
    shell_environment = " ".join(f"{key}={shlex.quote(value)}" for key, value in clean.items())
    return (
        "#!/bin/sh\n"
        f"'''exec' /usr/bin/env -i {shell_environment} "
        '"${0%/*}/python" "$0" "$@"\n'
        "' '''\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        f"environment = {clean!r}\n"
        "entry_point = Path(__file__).with_name('blender-mcp')\n"
        "os.execve(str(entry_point), [str(entry_point), *sys.argv[1:]], environment)\n"
    ).encode()


@dataclass(frozen=True)
class RuntimeState:
    tree: TreeImage
    python_version: str | None
    distributions: Mapping[str, str]
    blender_mcp_version: str | None
    mcp_version: str | None
    tomlkit_version: str | None
    entry_point: str | None
    entry_point_path: Path | None
    module_path: Path | None
    launcher_path: Path | None
    launcher_environment: Mapping[str, str]
    tools: tuple[str, ...]
    exact: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "distributions", MappingProxyType(dict(self.distributions)))
        object.__setattr__(
            self, "launcher_environment", MappingProxyType(dict(self.launcher_environment))
        )


def _absent_state(tree: TreeImage) -> RuntimeState:
    return RuntimeState(tree, None, {}, None, None, None, None, None, None, None, {}, (), False)


def _content_summary(tree: TreeImage) -> tuple[int, str]:
    entries = [
        {
            "path": entry.path,
            "kind": entry.kind,
            "mode": entry.mode,
            "size": entry.size if entry.kind == "file" else None,
            "sha256": entry.sha256,
        }
        for entry in tree.entries
        if entry.path != _MARKER
    ]
    raw = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return len(entries), hashlib.sha256(raw).hexdigest()


def _read_stable(path: Path, *, maximum: int | None = None) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        return _read_fd_stable(fd, maximum=maximum)
    finally:
        os.close(fd)


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_uid,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
    )


def _directory_identity(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_uid, info.st_mode)


def _validate_stage_root(
    stage: StagedTree,
    parent_fd: int,
    name: str,
    root_fd: int,
    parent_identity: tuple[int, ...],
    root_identity: tuple[int, ...],
) -> None:
    try:
        parent = os.fstat(parent_fd)
        root = os.fstat(root_fd)
        linked_parent = os.stat(stage.path.parent, follow_symlinks=False)
        linked_root = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        absolute_root = os.stat(stage.path, follow_symlinks=False)
    except OSError as exc:
        raise InstallerError("runtime stage identity changed") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or not stat.S_ISDIR(root.st_mode)
        or _directory_identity(parent) != parent_identity
        or _directory_identity(linked_parent) != parent_identity
        or _directory_identity(root) != root_identity
        or _directory_identity(linked_root) != root_identity
        or _directory_identity(absolute_root) != root_identity
    ):
        raise InstallerError("runtime stage identity changed")


def _read_fd_stable(fd: int, *, maximum: int | None = None) -> bytes:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink < 1:
        raise InstallerError("runtime input is not a regular file")
    if maximum is not None and before.st_size > maximum:
        raise InstallerError("runtime metadata is too large")
    raw = b""
    while len(raw) <= before.st_size:
        chunk = os.pread(fd, min(1024 * 1024, before.st_size - len(raw) + 1), len(raw))
        if not chunk:
            break
        raw += chunk
    if _identity(os.fstat(fd)) != _identity(before) or len(raw) != before.st_size:
        raise InstallerError("runtime input changed while reading")
    return raw


def _locked_distributions(raw: bytes) -> dict[str, str]:
    validate_runtime_lock(raw)
    result: dict[str, str] = {}
    current: list[str] = []
    for line in raw.decode().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        current.append(stripped[:-1].rstrip() if stripped.endswith("\\") else stripped)
        if stripped.endswith("\\"):
            continue
        requirement = " ".join(current).split()[0]
        name, version = requirement.split("==", 1)
        normalized = _normalized(name.split("[", 1)[0])
        if normalized in result:
            raise InstallerError("duplicate locked distribution")
        result[normalized] = version
        current = []
    return dict(sorted(result.items()))


def _expected_distributions(lock_raw: bytes, manifest: ReleaseManifest) -> dict[str, str]:
    result = _locked_distributions(lock_raw)
    result[_normalized(str(manifest.server["distribution"]))] = str(manifest.server["version"])
    return dict(sorted(result.items()))


@dataclass
class _RetainedInput:
    parent_fd: int
    name: str
    fd: int
    identity: tuple[int, ...]
    size: int
    sha256: str

    def close(self) -> None:
        os.close(self.fd)


def _validate_input(item: _RetainedInput) -> None:
    try:
        linked = os.stat(item.name, dir_fd=item.parent_fd, follow_symlinks=False)
        raw = _read_fd_stable(item.fd)
    except (FileNotFoundError, OSError, InstallerError) as exc:
        raise InstallerError("runtime installer input changed") from exc
    if (
        _identity(linked) != item.identity
        or _identity(os.fstat(item.fd)) != item.identity
        or len(raw) != item.size
        or hashlib.sha256(raw).hexdigest() != item.sha256
    ):
        raise InstallerError("runtime installer input changed")


def _validate_inputs(items: Sequence[_RetainedInput]) -> None:
    for item in items:
        _validate_input(item)


@contextmanager
def _verified_bundle_inputs(
    bundle: StagedBundle,
) -> Iterator[tuple[dict[str, _RetainedInput], bytes, dict[str, str]]]:
    if type(bundle) is not StagedBundle:
        raise ValueError("invalid staged bundle")
    _absolute(bundle.root, "staged bundle root")
    by_role = {artifact.role: artifact for artifact in bundle.manifest.artifacts}
    root_fd = os.open(bundle.root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    opened: dict[str, _RetainedInput] = {}
    try:
        for role, name in (
            ("runtime_lock", bundle.runtime_lock_path.name),
            ("server_wheel", bundle.wheel_path.name),
        ):
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
            try:
                info = os.fstat(fd)
                raw = _read_fd_stable(fd)
                artifact = by_role[role]
                if len(raw) != artifact.size or hashlib.sha256(raw).hexdigest() != artifact.sha256:
                    raise InstallerError("bundle artifact changed")
                opened[role] = _RetainedInput(
                    root_fd,
                    name,
                    fd,
                    _identity(info),
                    artifact.size,
                    artifact.sha256,
                )
            except BaseException:
                os.close(fd)
                raise
        _validate_inputs(tuple(opened.values()))
        lock_raw = _read_fd_stable(opened["runtime_lock"].fd)
        yield opened, lock_raw, _expected_distributions(lock_raw, bundle.manifest)
    finally:
        for item in opened.values():
            item.close()
        os.close(root_fd)


def _copy_retained_input(
    source: _RetainedInput,
    stage_fd: int,
) -> _RetainedInput:
    _validate_input(source)
    fd = os.open(
        source.name,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=stage_fd,
    )
    try:
        copied = 0
        digest = hashlib.sha256()
        while chunk := os.pread(source.fd, 1024 * 1024, copied):
            offset = 0
            while offset < len(chunk):
                offset += os.write(fd, chunk[offset:])
            digest.update(chunk)
            copied += len(chunk)
        os.fchmod(fd, 0o600)
        os.fsync(fd)
        info = os.fstat(fd)
        if copied != source.size or digest.hexdigest() != source.sha256:
            raise InstallerError("runtime installer input changed")
        result = _RetainedInput(
            stage_fd,
            source.name,
            fd,
            _identity(info),
            source.size,
            source.sha256,
        )
        _validate_input(source)
        _validate_input(result)
        return result
    except BaseException:
        os.close(fd)
        raise


def _remove_private_inputs(stage_fd: int, inputs: Sequence[_RetainedInput]) -> None:
    for item in inputs:
        _validate_input(item)
    for item in inputs:
        os.unlink(item.name, dir_fd=stage_fd)
    os.fsync(stage_fd)
    for item in inputs:
        try:
            os.stat(item.name, dir_fd=stage_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise InstallerError("runtime installer input changed")


def _run(
    runner: Runner,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    label: str,
) -> str:
    try:
        completed = runner(argv, cwd=cwd, env=env)
    except Exception as exc:
        raise InstallerError(f"{label} failed") from exc
    if getattr(completed, "returncode", 0) != 0:
        raise InstallerError(f"{label} failed")
    stdout = getattr(completed, "stdout", "")
    if isinstance(stdout, bytes):
        try:
            return stdout.decode()
        except UnicodeDecodeError as exc:
            raise InstallerError(f"{label} failed") from exc
    if not isinstance(stdout, str):
        raise InstallerError(f"{label} failed")
    return stdout


def _run_with_inputs(
    runner: Runner,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    label: str,
    inputs: Sequence[_RetainedInput],
) -> str:
    _validate_inputs(inputs)
    result = _run(runner, argv, cwd=cwd, env=env, label=label)
    _validate_inputs(inputs)
    return result


def _parse_probe(
    raw: str,
    runtime: Path,
    expected: Mapping[str, str],
    tools: tuple[str, ...],
) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InstallerError("runtime metadata probe failed") from exc
    if type(value) is not dict or set(value) != {
        "python_version",
        "distributions",
        "entry_point",
        "entry_point_path",
        "module_path",
        "tools",
    }:
        raise InstallerError("runtime metadata probe failed")
    distributions = value["distributions"]
    if (
        type(value["python_version"]) is not str
        or not _VERSION.fullmatch(value["python_version"])
        or type(distributions) is not dict
        or any(
            type(key) is not str or type(version) is not str
            for key, version in distributions.items()
        )
        or dict(sorted((_normalized(key), version) for key, version in distributions.items()))
        != dict(expected)
        or value["entry_point"] != _ENTRY_POINT
        or type(value["tools"]) is not list
        or tuple(value["tools"]) != tools
    ):
        raise InstallerError("runtime metadata probe failed")
    entry_point = Path(value["entry_point_path"])
    module = Path(value["module_path"])
    if (
        not entry_point.is_absolute()
        or entry_point != runtime / "bin/blender-mcp"
        or not module.is_absolute()
        or not module.is_relative_to(runtime)
    ):
        raise InstallerError("runtime metadata probe failed")
    return {
        "python_version": value["python_version"],
        "distributions": dict(expected),
        "entry_point": _ENTRY_POINT,
        "entry_point_relative": "bin/blender-mcp",
        "module_relative": module.relative_to(runtime).as_posix(),
    }


def _probe_runtime(
    runtime: Path,
    expected: Mapping[str, str],
    tools: tuple[str, ...],
    profile: ManagedProfile,
    runner: Runner,
) -> dict[str, object]:
    stdout = _run(
        runner,
        (str(runtime / "bin/python"), "-I", "-c", _PROBE),
        cwd=runtime,
        env=_install_env(profile),
        label="runtime metadata probe",
    )
    return _parse_probe(stdout, runtime, expected, tools)


def _write_exclusive(path: Path, raw: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(fd, raw[offset:])
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)


def _materialize_links(runtime: Path) -> None:
    for path in sorted(runtime.rglob("*")):
        if not path.is_symlink():
            continue
        target = path.resolve(strict=True)
        info = target.stat()
        if not stat.S_ISREG(info.st_mode):
            raise InstallerError("runtime contains an unsafe link")
        raw = _read_stable(target)
        mode = stat.S_IMODE(info.st_mode)
        path.unlink()
        _write_exclusive(path, raw, mode)


def _sync_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_symlink():
            raise InstallerError("runtime contains an unsafe link")
        fd = os.open(child, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stage_runtime(
    bundle: StagedBundle,
    uv_bin: Path,
    python_bin: Path,
    profile: ManagedProfile,
    stage: StagedTree,
    runner: Runner,
) -> TreeImage:
    uv_bin = _absolute(uv_bin, "uv executable")
    python_bin = _absolute(python_bin, "Python executable")
    if (
        type(stage) is not StagedTree
        or stage.image.state is not ImageState.PRESENT
        or stage.capture() != stage.image
        or stage.image.entries
    ):
        raise InstallerError("runtime stage state conflict")
    runtime = stage.path
    parent_fd, stage_name = stage.root.open_parent(stage.relative)
    try:
        stage_fd = os.open(
            stage_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            parent_identity = _directory_identity(os.fstat(parent_fd))
            root_identity = _directory_identity(os.fstat(stage_fd))

            def check_stage() -> None:
                _validate_stage_root(
                    stage,
                    parent_fd,
                    stage_name,
                    stage_fd,
                    parent_identity,
                    root_identity,
                )

            check_stage()
            with _verified_bundle_inputs(bundle) as (bundle_inputs, lock_raw, expected):
                sources = tuple(bundle_inputs.values())
                env = _install_env(profile)
                wheel_env = dict(env)
                del wheel_env["UV_REQUIRE_HASHES"]
                _run_with_inputs(
                    runner,
                    (
                        str(uv_bin),
                        "venv",
                        "--relocatable",
                        "--python",
                        str(python_bin),
                        str(runtime),
                    ),
                    cwd=runtime.parent,
                    env=env,
                    label="runtime virtual environment creation",
                    inputs=sources,
                )
                check_stage()
                private_inputs: list[_RetainedInput] = []
                try:
                    for role in ("runtime_lock", "server_wheel"):
                        private_inputs.append(_copy_retained_input(bundle_inputs[role], stage_fd))
                    os.fsync(stage_fd)
                    bound = (*sources, *private_inputs)
                    check_stage()
                    _run_with_inputs(
                        runner,
                        (
                            str(uv_bin),
                            "pip",
                            "install",
                            "--python",
                            str(runtime / "bin/python"),
                            "--require-hashes",
                            "--only-binary",
                            ":all:",
                            "--no-deps",
                            "--default-index",
                            _INDEX,
                            "-r",
                            str(runtime / bundle.runtime_lock_path.name),
                        ),
                        cwd=runtime.parent,
                        env=env,
                        label="locked runtime installation",
                        inputs=bound,
                    )
                    check_stage()
                    _run_with_inputs(
                        runner,
                        (
                            str(uv_bin),
                            "pip",
                            "install",
                            "--python",
                            str(runtime / "bin/python"),
                            "--no-deps",
                            "--no-build",
                            str(runtime / bundle.wheel_path.name),
                        ),
                        cwd=runtime.parent,
                        env=wheel_env,
                        label="official server installation",
                        inputs=bound,
                    )
                    check_stage()
                    _remove_private_inputs(stage_fd, private_inputs)
                    check_stage()
                except BaseException:
                    try:
                        if private_inputs:
                            _remove_private_inputs(stage_fd, private_inputs)
                    except InstallerError:
                        pass
                    raise
                finally:
                    for item in private_inputs:
                        item.close()
            check_stage()
            _materialize_links(runtime)
            check_stage()
            metadata = _probe_runtime(runtime, expected, bundle.manifest.tools, profile, runner)
            check_stage()
            launcher_environment = _profile_env(profile)
            launcher = runtime / _LAUNCHER
            _write_exclusive(launcher, _launcher_source(launcher_environment), 0o700)
            _write_exclusive(runtime / _LOCK_COPY, lock_raw, 0o600)
            entry_point_raw = _read_stable(runtime / PurePath(metadata["entry_point_relative"]))
            module_raw = _read_stable(runtime / PurePath(metadata["module_relative"]))
            _sync_tree(runtime)
            check_stage()
            content_count, content_sha256 = _content_summary(stage.capture())
            check_stage()
            marker = {
                "schema_version": 1,
                **metadata,
                "content_count": content_count,
                "content_sha256": content_sha256,
                "entry_point_sha256": hashlib.sha256(entry_point_raw).hexdigest(),
                "module_sha256": hashlib.sha256(module_raw).hexdigest(),
                "launcher_relative": _LAUNCHER,
                "launcher_sha256": hashlib.sha256(
                    _launcher_source(launcher_environment)
                ).hexdigest(),
                "launcher_environment": launcher_environment,
                "tools": list(bundle.manifest.tools),
            }
            _write_exclusive(
                runtime / _MARKER,
                (json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n").encode(),
                0o600,
            )
            _sync_tree(runtime)
            check_stage()
            image = stage.capture()
            check_stage()
            if image.state is not ImageState.PRESENT:
                raise InstallerError("staged runtime is absent")
            return image
        finally:
            os.close(stage_fd)
    finally:
        os.close(parent_fd)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _load_marker(runtime: Path) -> dict[str, object]:
    path = runtime / _MARKER
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(fd)
            raw = _read_fd_stable(fd, maximum=_MAX_MARKER)
            linked = os.stat(path, follow_symlinks=False)
        finally:
            os.close(fd)
        value = json.loads(raw, object_pairs_hook=_unique_object)
        canonical = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or _identity(linked) != _identity(info)
            or raw != canonical
        ):
            raise InstallerError("invalid runtime metadata")
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError, InstallerError) as exc:
        raise InstallerError("invalid runtime metadata") from exc
    keys = {
        "schema_version",
        "content_count",
        "content_sha256",
        "python_version",
        "distributions",
        "entry_point",
        "entry_point_relative",
        "entry_point_sha256",
        "module_relative",
        "module_sha256",
        "launcher_relative",
        "launcher_sha256",
        "launcher_environment",
        "tools",
    }
    if type(value) is not dict or set(value) != keys or value["schema_version"] != 1:
        raise InstallerError("invalid runtime metadata")
    return value


def _state(runtime_root: TargetRef, manifest: ReleaseManifest, *, strict: bool) -> RuntimeState:
    tree = capture_tree(runtime_root.root, runtime_root.relative)
    if tree.state is ImageState.ABSENT:
        return _absent_state(tree)
    runtime = runtime_root.path
    try:
        marker = _load_marker(runtime)
        content_count, content_sha256 = _content_summary(tree)
        if (
            type(marker["content_count"]) is not int
            or marker["content_count"] != content_count
            or type(marker["content_sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", marker["content_sha256"])
            or marker["content_sha256"] != content_sha256
        ):
            raise InstallerError("runtime content changed")
        lock_raw = _read_stable(runtime / _LOCK_COPY)
        runtime_lock = next(
            artifact for artifact in manifest.artifacts if artifact.role == "runtime_lock"
        )
        if (
            len(lock_raw) != runtime_lock.size
            or hashlib.sha256(lock_raw).hexdigest() != runtime_lock.sha256
        ):
            raise InstallerError("invalid runtime lock")
        expected_distributions = _expected_distributions(lock_raw, manifest)
        distributions = marker["distributions"]
        environment = marker["launcher_environment"]
        tools = marker["tools"]
        if (
            type(marker["python_version"]) is not str
            or not _VERSION.fullmatch(marker["python_version"])
            or type(distributions) is not dict
            or any(
                type(key) is not str or type(value) is not str
                for key, value in distributions.items()
            )
            or marker["entry_point"] != _ENTRY_POINT
            or marker["entry_point_relative"] != "bin/blender-mcp"
            or marker["launcher_relative"] != _LAUNCHER
            or type(marker["module_relative"]) is not str
            or type(environment) is not dict
            or type(tools) is not list
            or tuple(tools) != manifest.tools
            or distributions != expected_distributions
        ):
            raise InstallerError("invalid runtime metadata")
        entry_point = runtime / PurePath(marker["entry_point_relative"])
        module = runtime / PurePath(marker["module_relative"])
        launcher = runtime / PurePath(marker["launcher_relative"])
        for relative, path in (
            (marker["entry_point_relative"], entry_point),
            (marker["module_relative"], module),
            (marker["launcher_relative"], launcher),
        ):
            pure = PurePath(relative)
            if pure.is_absolute() or ".." in pure.parts or not path.is_relative_to(runtime):
                raise InstallerError("invalid runtime metadata")
        entry_point_raw = _read_stable(entry_point)
        module_raw = _read_stable(module)
        if (
            hashlib.sha256(entry_point_raw).hexdigest() != marker["entry_point_sha256"]
            or hashlib.sha256(module_raw).hexdigest() != marker["module_sha256"]
            or not stat.S_IMODE(entry_point.stat(follow_symlinks=False).st_mode) & 0o100
        ):
            raise InstallerError("invalid official runtime entry point")
        launcher_raw = _read_stable(launcher)
        if (
            hashlib.sha256(launcher_raw).hexdigest() != marker["launcher_sha256"]
            or launcher_raw != _launcher_source(environment)
            or stat.S_IMODE(launcher.stat(follow_symlinks=False).st_mode) != 0o700
        ):
            raise InstallerError("invalid runtime launcher")
        expected_environment = _profile_env(
            ManagedProfile(
                home=Path(environment["HOME"]),
                blender_user_resources=Path(environment["BLENDER_USER_RESOURCES"]),
                blender_user_config=Path(environment["BLENDER_USER_CONFIG"]),
                blender_user_extensions=Path(environment["BLENDER_USER_EXTENSIONS"]),
                blender_path=Path(environment["BLENDER_PATH"]),
            )
        )
        if environment != expected_environment:
            raise InstallerError("invalid runtime launcher environment")
        expected_server = str(manifest.server["version"])
        state = RuntimeState(
            tree,
            marker["python_version"],
            distributions,
            distributions.get("blender-mcp"),
            distributions.get("mcp"),
            distributions.get("tomlkit"),
            marker["entry_point"],
            entry_point,
            module,
            launcher,
            environment,
            tuple(tools),
            distributions.get("blender-mcp") == expected_server
            and distributions.get("mcp") == str(manifest.server["mcp_sdk"])
            and distributions.get("tomlkit") == "0.13.3",
        )
        return state
    except (KeyError, TypeError, ValueError, OSError, InstallerError):
        if strict:
            raise InstallerError("runtime verification failed")
        return _absent_state(tree)


def inspect_runtime(runtime_root: TargetRef, manifest: ReleaseManifest) -> RuntimeState:
    if not isinstance(runtime_root, TargetRef) or type(manifest) is not ReleaseManifest:
        raise ValueError("invalid runtime inspection input")
    return _state(runtime_root, manifest, strict=False)


def verify_runtime(
    runtime_root: TargetRef,
    manifest: ReleaseManifest,
    profile: ManagedProfile,
    runner: Runner,
) -> RuntimeState:
    state = _state(runtime_root, manifest, strict=True)
    if not state.exact:
        raise InstallerError("runtime verification failed")
    expected = dict(state.distributions)
    probed = _probe_runtime(runtime_root.path, expected, state.tools, profile, runner)
    if (
        probed["python_version"] != state.python_version
        or probed["entry_point"] != state.entry_point
        or runtime_root.path / PurePath(probed["entry_point_relative"]) != state.entry_point_path
        or runtime_root.path / PurePath(probed["module_relative"]) != state.module_path
        or state.launcher_environment != _profile_env(profile)
    ):
        raise InstallerError("runtime verification failed")
    return state
