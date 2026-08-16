from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Mapping, Sequence

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


def _read_stable(path: Path, *, maximum: int | None = None) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink < 1:
            raise InstallerError("runtime input is not a regular file")
        if maximum is not None and before.st_size > maximum:
            raise InstallerError("runtime metadata is too large")
        raw = b""
        while len(raw) <= before.st_size:
            chunk = os.read(fd, min(1024 * 1024, before.st_size - len(raw) + 1))
            if not chunk:
                break
            raw += chunk
        after = os.fstat(fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_uid,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
        ) or len(raw) != before.st_size:
            raise InstallerError("runtime input changed while reading")
        return raw
    finally:
        os.close(fd)


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


def _verify_bundle(bundle: StagedBundle) -> tuple[bytes, dict[str, str]]:
    if type(bundle) is not StagedBundle:
        raise ValueError("invalid staged bundle")
    _absolute(bundle.root, "staged bundle root")
    by_role = {artifact.role: artifact for artifact in bundle.manifest.artifacts}
    for role, path in (
        ("runtime_lock", bundle.runtime_lock_path),
        ("server_wheel", bundle.wheel_path),
    ):
        raw = _read_stable(path)
        artifact = by_role[role]
        if len(raw) != artifact.size or hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise InstallerError("bundle artifact changed")
        if role == "runtime_lock":
            lock_raw = raw
    return lock_raw, _expected_distributions(lock_raw, bundle.manifest)


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
    lock_raw, expected = _verify_bundle(bundle)
    env = _install_env(profile)
    wheel_env = dict(env)
    del wheel_env["UV_REQUIRE_HASHES"]
    runtime = stage.path
    commands = (
        (
            (str(uv_bin), "venv", "--relocatable", "--python", str(python_bin), str(runtime)),
            "runtime virtual environment creation",
            env,
        ),
        (
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
                str(bundle.runtime_lock_path),
            ),
            "locked runtime installation",
            env,
        ),
        (
            (
                str(uv_bin),
                "pip",
                "install",
                "--python",
                str(runtime / "bin/python"),
                "--no-deps",
                "--no-build",
                str(bundle.wheel_path),
            ),
            "official server installation",
            wheel_env,
        ),
    )
    for argv, label, command_env in commands:
        _run(runner, argv, cwd=runtime.parent, env=command_env, label=label)
    _materialize_links(runtime)
    metadata = _probe_runtime(runtime, expected, bundle.manifest.tools, profile, runner)
    launcher_environment = _profile_env(profile)
    launcher = runtime / _LAUNCHER
    _write_exclusive(launcher, _launcher_source(launcher_environment), 0o700)
    _write_exclusive(runtime / _LOCK_COPY, lock_raw, 0o600)
    entry_point_raw = _read_stable(runtime / PurePath(metadata["entry_point_relative"]))
    module_raw = _read_stable(runtime / PurePath(metadata["module_relative"]))
    marker = {
        "schema_version": 1,
        **metadata,
        "entry_point_sha256": hashlib.sha256(entry_point_raw).hexdigest(),
        "module_sha256": hashlib.sha256(module_raw).hexdigest(),
        "launcher_relative": _LAUNCHER,
        "launcher_sha256": hashlib.sha256(_launcher_source(launcher_environment)).hexdigest(),
        "launcher_environment": launcher_environment,
        "tools": list(bundle.manifest.tools),
    }
    _write_exclusive(
        runtime / _MARKER,
        (json.dumps(marker, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        0o600,
    )
    _sync_tree(runtime)
    image = stage.capture()
    if image.state is not ImageState.PRESENT:
        raise InstallerError("staged runtime is absent")
    return image


def _load_marker(runtime: Path) -> dict[str, object]:
    try:
        value = json.loads(_read_stable(runtime / _MARKER, maximum=_MAX_MARKER))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, InstallerError) as exc:
        raise InstallerError("invalid runtime metadata") from exc
    keys = {
        "schema_version",
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
