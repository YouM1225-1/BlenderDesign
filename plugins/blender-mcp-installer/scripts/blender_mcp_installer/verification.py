from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

from .blender_adapter import (
    BlenderState,
    load_extension_payload,
    probe_blender_lifecycle,
)
from .bundle import ReleaseManifest, StagedBundle
from .codex_adapter import ManagedProfile, desired_codex_values
from .filesystem import InstallerError, SafeRoot, TargetRef
from .model import ActiveSelector, InstallRoots, ReceiptStatus, parse_receipt
from .runtime import inspect_runtime


_SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
_WAIT_TIMEOUT = 2.0
_VERSION = re.compile(r"(?:codex-cli|uv|Blender|Python)\s+([0-9][A-Za-z0-9.+-]*)")


class Runner(Protocol):
    def __call__(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> object: ...


class MCPSession(Protocol):
    def initialize(self) -> object: ...

    def list_tools(self) -> Sequence[str]: ...

    def call_tool(self, name: str, arguments: Mapping[str, object]) -> object: ...

    def close(self) -> None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float) -> object: ...


class MCPProbe(Protocol):
    def start(self, command: Sequence[str], *, env: Mapping[str, str]) -> MCPSession: ...


@dataclass(frozen=True)
class HostCapabilities:
    platform_system: str
    platform_machine: str
    codex_version: str
    uv_version: str
    blender_version: str
    python_version: str
    blender_arches: tuple[str, ...]
    codex_mcp_get_json: bool
    codex_marketplace_add: bool
    codex_plugin_add: bool
    blender_bin: Path
    codex_bin: Path
    uv_bin: Path
    python_bin: Path
    env: Mapping[str, str]
    runner: Runner = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))

    @property
    def supported(self) -> bool:
        return (
            self.platform_system == "Darwin"
            and self.platform_machine == "arm64"
            and self.uv_version == "0.12.2"
            and re.fullmatch(r"3\.13\.\d+", self.python_version) is not None
            and re.fullmatch(r"5\.2\.\d+", self.blender_version) is not None
            and "arm64" in self.blender_arches
            and self.codex_mcp_get_json
            and self.codex_marketplace_add
            and self.codex_plugin_add
        )


class HostCapabilityError(InstallerError):
    def __init__(self, capabilities: HostCapabilities) -> None:
        super().__init__("unsupported host capabilities")
        self.capabilities = capabilities


@dataclass(frozen=True)
class InstallationInspection:
    runtime: bool
    extension_repository: bool
    extension_id: bool
    extension_version: bool
    extension_payload_digest: bool
    enablement: bool
    preferences: bool
    codex_policy: bool
    codex_namespace: bool
    codex_effective: bool
    active_generation: bool
    manifest_hash: bool
    recorded_blender_executable: bool
    host: HostCapabilities
    blender_executable: Path
    runtime_command: tuple[str, ...]
    expected_tools: tuple[str, ...]
    managed_targets: tuple[Path, ...]
    managed_images: tuple[str, ...]
    active_install_id: str | None

    @property
    def exact(self) -> bool:
        return all(
            (
                self.runtime,
                self.extension_repository,
                self.extension_id,
                self.extension_version,
                self.extension_payload_digest,
                self.enablement,
                self.preferences,
                self.codex_policy,
                self.codex_namespace,
                self.codex_effective,
                self.active_generation,
                self.manifest_hash,
                self.recorded_blender_executable,
            )
        )


@dataclass(frozen=True)
class VerificationResult:
    parsed_codex: bool
    effective_codex: bool
    mcp_catalog: bool
    blender_read_only: bool
    tool_count: int


def _absolute_executable(path: Path, label: str) -> Path:
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be an absolute lexical path")
    try:
        info = path.lstat()
    except OSError as exc:
        raise InstallerError("host capability probe failed") from exc
    if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
        raise InstallerError("host capability probe failed")
    return path


def _text(value: object) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InstallerError("host capability probe failed") from exc
    if type(value) is not str:
        raise InstallerError("host capability probe failed")
    return value


def _run(
    runner: Runner,
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    accepted: tuple[int, ...] = (0,),
) -> tuple[int, str]:
    try:
        completed = runner(tuple(argv), cwd=cwd, env=env)
        code = completed.returncode
        output = _text(completed.stdout)
        _text(completed.stderr)
    except InstallerError:
        raise
    except Exception as exc:
        raise InstallerError("host capability probe failed") from exc
    if type(code) is not int or code not in accepted or len(output.encode()) > 1024 * 1024:
        raise InstallerError("host capability probe failed")
    return code, output


def _version(output: str) -> str:
    lines = output.splitlines()
    match = None if not lines else _VERSION.fullmatch(lines[0].strip())
    if match is None:
        raise InstallerError("host capability probe failed")
    return match.group(1)


def _default_runner(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> object:
    return __import__("subprocess").run(
        argv,
        cwd=cwd,
        env=dict(env),
        stdin=__import__("subprocess").DEVNULL,
        capture_output=True,
        text=False,
        timeout=5.0,
        check=False,
    )


def probe_host(
    blender_bin: Path,
    codex_bin: Path,
    uv_bin: Path,
    python_bin: Path,
    env: Mapping[str, str],
    *,
    runner: Runner = _default_runner,
) -> HostCapabilities:
    binaries = tuple(
        _absolute_executable(path, label)
        for path, label in (
            (blender_bin, "Blender executable"),
            (codex_bin, "Codex executable"),
            (uv_bin, "uv executable"),
            (python_bin, "Python executable"),
        )
    )
    if not isinstance(env, Mapping) or any(
        type(key) is not str or type(value) is not str for key, value in env.items()
    ):
        raise ValueError("invalid host environment")
    clean = {
        "PATH": _SYSTEM_PATH,
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
    for key in ("HOME", "CODEX_HOME"):
        if key in env:
            clean[key] = env[key]
    versions = tuple(
        _version(_run(runner, (str(path), "--version"), cwd=path.parent, env=clean)[1])
        for path in (codex_bin, uv_bin, blender_bin, python_bin)
    )
    arches = tuple(
        _run(
            runner,
            ("/usr/bin/lipo", "-archs", str(blender_bin)),
            cwd=blender_bin.parent,
            env=clean,
        )[1].split()
    )
    if not arches or any(not re.fullmatch(r"[A-Za-z0-9_]+", item) for item in arches):
        raise InstallerError("host capability probe failed")

    def help_probe(args: tuple[str, ...], marker: str | None = None) -> bool:
        try:
            output = _run(runner, (str(codex_bin), *args), cwd=codex_bin.parent, env=clean)[1]
        except InstallerError:
            return False
        return marker is None or marker in output.split()

    capabilities = HostCapabilities(
        platform.system(),
        platform.machine(),
        versions[0],
        versions[1],
        versions[2],
        versions[3],
        arches,
        help_probe(("mcp", "get", "--help"), "--json"),
        help_probe(("plugin", "marketplace", "add", "--help")),
        help_probe(("plugin", "add", "--help")),
        *binaries,
        clean,
        runner,
    )
    if not capabilities.supported:
        raise HostCapabilityError(capabilities)
    return capabilities


def _file_image(path: Path) -> str:
    before = path.lstat()
    if before.st_uid != os.getuid() or not stat.S_ISREG(before.st_mode):
        raise InstallerError("managed target snapshot failed")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
    if any(getattr(before, key) != getattr(opened, key) for key in fields) or any(
        getattr(opened, key) != getattr(after, key) for key in fields
    ):
        raise InstallerError("managed target snapshot failed")
    return (
        f"f:{opened.st_dev}:{opened.st_ino}:{opened.st_uid}:{opened.st_mode}:"
        f"{opened.st_size}:{opened.st_mtime_ns}:{digest.hexdigest()}"
    )


def _tree_entries(path: Path, prefix: str = "") -> list[str]:
    before = path.lstat()
    if before.st_uid != os.getuid() or not stat.S_ISDIR(before.st_mode):
        raise InstallerError("managed target snapshot failed")
    try:
        names = sorted(item.name for item in os.scandir(path))
        result = [
            f"d:{prefix}:{before.st_dev}:{before.st_ino}:{before.st_uid}:"
            f"{before.st_mode}:{before.st_mtime_ns}"
        ]
        for name in names:
            child = path / name
            child_prefix = f"{prefix}/{name}" if prefix else name
            info = child.lstat()
            if stat.S_ISREG(info.st_mode):
                result.append(f"{child_prefix}:{_file_image(child)}")
            elif stat.S_ISDIR(info.st_mode):
                result.extend(_tree_entries(child, child_prefix))
            else:
                raise InstallerError("managed target snapshot failed")
        after = path.lstat()
        after_names = sorted(item.name for item in os.scandir(path))
    except OSError as exc:
        raise InstallerError("managed target snapshot failed") from exc
    fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_mtime_ns")
    if names != after_names or any(getattr(before, key) != getattr(after, key) for key in fields):
        raise InstallerError("managed target snapshot failed")
    return result


def _snapshot(paths: Sequence[Path]) -> tuple[str, ...]:
    result: list[str] = []
    try:
        for path in paths:
            if not path.exists() and not path.is_symlink():
                result.append("absent")
                continue
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                result.append(_file_image(path))
            elif stat.S_ISDIR(info.st_mode):
                raw = "\n".join(_tree_entries(path)).encode()
                result.append(f"t:{hashlib.sha256(raw).hexdigest()}")
            else:
                raise InstallerError("managed target snapshot failed")
    except InstallerError:
        raise
    except (OSError, ValueError) as exc:
        raise InstallerError("managed target snapshot failed") from exc
    return tuple(result)


def _managed_paths(roots: InstallRoots) -> tuple[Path, ...]:
    return (
        roots.runtime,
        roots.extension_target,
        roots.userpref_target,
        roots.codex_config,
        roots.active,
    )


def _read_regular(path: Path, maximum: int = 16 * 1024 * 1024) -> bytes:
    try:
        before = path.lstat()
        if before.st_uid != os.getuid() or not stat.S_ISREG(before.st_mode):
            raise InstallerError("installation inspection failed")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as exc:
        raise InstallerError("installation inspection failed") from exc
    try:
        opened = os.fstat(fd)
        chunks: list[bytes] = []
        size = 0
        while chunk := os.read(fd, min(1024 * 1024, maximum - size + 1)):
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise InstallerError("installation inspection failed")
        after = os.fstat(fd)
        linked = path.lstat()
    finally:
        os.close(fd)
    fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
    if any(getattr(before, key) != getattr(opened, key) for key in fields) or any(
        getattr(opened, key) != getattr(after, key) or getattr(after, key) != getattr(linked, key)
        for key in fields
    ):
        raise InstallerError("installation inspection failed")
    return b"".join(chunks)


def _codex_checks(raw: bytes, desired) -> tuple[bool, bool]:
    try:
        value = tomllib.loads(raw.decode("utf-8"))
        server = value["mcp_servers"]["blender"]
        env = server["env"]
        expected = desired.helper_dict()["server"]
        policy = type(server) is dict and all(
            type(server.get(key)) is type(item) and server.get(key) == item
            for key, item in expected.items()
        )
        policy = (
            policy
            and type(env) is dict
            and all(
                type(env.get(key)) is str and env.get(key) == item
                for key, item in desired.env.items()
            )
        )
        policy = policy and not any(key in server for key in ("disabled_tools", "tools"))
        namespaces = value["features"]["code_mode"]["direct_only_tool_namespaces"]
        namespace = type(namespaces) is list and namespaces.count("mcp__blender") == 1
        return policy, namespace
    except (KeyError, TypeError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False, False


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read_json(path: Path) -> object:
    try:
        return json.loads(
            _read_regular(path).decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InstallerError("installation inspection failed") from exc


def _effective(host: HostCapabilities, desired) -> bool:
    try:
        output = _run(
            host.runner,
            (str(host.codex_bin), "mcp", "get", "blender", "--json"),
            cwd=host.codex_bin.parent,
            env=host.env,
        )[1]
        value = json.loads(output, object_pairs_hook=_json_object)
        effective_env = value["env"]
        return (
            value.get("command") == desired.command
            and value.get("args") == list(desired.args)
            and value.get("enabled_tools") == list(desired.enabled_tools)
            and value.get("startup_timeout_sec") == desired.startup_timeout_sec
            and value.get("tool_timeout_sec") == desired.tool_timeout_sec
            and all(effective_env.get(key) == item for key, item in desired.env.items())
        )
    except (InstallerError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _inspect(
    bundle: StagedBundle,
    roots: InstallRoots,
    blender_state: BlenderState,
    host: HostCapabilities,
    images: tuple[str, ...],
) -> InstallationInspection:
    manifest: ReleaseManifest = bundle.manifest
    runtime_state = None
    if roots.data_root.exists():
        with SafeRoot.open(roots.data_root, os.getuid(), roots.data_root) as root:
            runtime_state = inspect_runtime(
                TargetRef(root, PurePath(roots.runtime.relative_to(roots.data_root))), manifest
            )
    expected_payload = load_extension_payload(bundle.extension_path)
    runtime = runtime_state is not None and runtime_state.exact
    extension_repository = blender_state.repository == manifest.extension["repository"]
    extension_id = blender_state.manifest_id == manifest.extension["id"]
    extension_version = blender_state.manifest_version == manifest.extension["version"]
    extension_payload_digest = (
        blender_state.canonical_payload_digest == expected_payload.canonical_digest
    )
    enablement = blender_state.enabled is True
    preferences = (
        blender_state.online_access is True
        and blender_state.host == "localhost"
        and blender_state.port == 9876
        and blender_state.autostart is True
    )
    profile = ManagedProfile(
        roots.home,
        blender_state.user_resources,
        blender_state.config_root,
        blender_state.extensions_root,
        blender_state.executable,
    )
    launcher = None if runtime_state is None else runtime_state.launcher_path
    desired = None if launcher is None else desired_codex_values(launcher, profile, manifest.tools)
    try:
        raw = _read_regular(roots.codex_config)
        codex_policy, codex_namespace = (
            (False, False) if desired is None else _codex_checks(raw, desired)
        )
    except (FileNotFoundError, InstallerError):
        codex_policy = codex_namespace = False
    codex_effective = False
    active_generation = False
    manifest_hash = False
    recorded_blender_executable = False
    active_install_id = None
    try:
        if roots.active.exists():
            active = ActiveSelector.from_dict(_read_json(roots.active))
            receipt = parse_receipt(_read_json(roots.receipts / active.receipt_basename), roots)
            active_generation = (
                receipt.status is ReceiptStatus.INSTALLED
                and receipt.install_id == active.install_id
                and receipt.generation == active.generation
            )
            expected_manifest_hash = hashlib.sha256(_read_regular(bundle.manifest_path)).hexdigest()
            manifest_hash = (
                receipt.bundle["version"] == manifest.bundle_version
                and receipt.bundle["manifest_sha256"] == expected_manifest_hash
            )
            recorded_blender_executable = (
                receipt.host["blender_executable"] == str(blender_state.executable)
                and receipt.host["blender_architecture"] == blender_state.reported_architecture
                and receipt.host["blender_version"] == blender_state.version
            )
            active_install_id = str(active.install_id)
    except (OSError, ValueError, InstallerError):
        pass
    if desired is not None and active_generation:
        codex_effective = _effective(host, desired)
    command = () if desired is None else (desired.command, *desired.args)
    return InstallationInspection(
        runtime,
        extension_repository,
        extension_id,
        extension_version,
        extension_payload_digest,
        enablement,
        preferences,
        codex_policy,
        codex_namespace,
        codex_effective,
        active_generation,
        manifest_hash,
        recorded_blender_executable,
        host,
        blender_state.executable,
        command,
        manifest.tools,
        _managed_paths(roots),
        images,
        active_install_id,
    )


def inspect_installation(
    bundle: StagedBundle,
    roots: InstallRoots,
    blender_state: BlenderState,
    host: HostCapabilities,
) -> InstallationInspection:
    paths = _managed_paths(roots)
    before = _snapshot(paths)
    inspection = None
    error = None
    try:
        inspection = _inspect(bundle, roots, blender_state, host, before)
    except InstallerError as exc:
        error = exc
    except Exception:
        error = InstallerError("installation inspection failed")
    try:
        changed = _snapshot(paths) != before
    except InstallerError:
        changed = True
    if changed:
        raise InstallerError("managed targets changed during inspection")
    if error is not None:
        raise error
    assert inspection is not None
    return inspection


def verify_live(
    bundle: StagedBundle,
    inspection: InstallationInspection,
    runtime_command: Sequence[str],
    codex_bin: Path,
    env: Mapping[str, str],
    mcp_probe: MCPProbe,
) -> VerificationResult:
    before = _snapshot(inspection.managed_targets)
    session: MCPSession | None = None
    error: InstallerError | None = None
    tool_count = 0
    try:
        command = tuple(runtime_command)
        if (
            command != inspection.runtime_command
            or not command
            or not Path(command[0]).is_absolute()
        ):
            raise InstallerError("managed runtime command mismatch")
        if codex_bin != inspection.host.codex_bin:
            raise InstallerError("Codex executable mismatch")
        if not inspection.exact or tuple(bundle.manifest.tools) != inspection.expected_tools:
            raise InstallerError("installation inspection is not exact")
        try:
            lifecycle = probe_blender_lifecycle(
                inspection.blender_executable, inspection.host.runner
            )
        except Exception as exc:
            raise InstallerError("selected Blender listener verification failed") from exc
        if (
            lifecycle.port_free
            or lifecycle.listener_pid is None
            or lifecycle.listener_pid not in lifecycle.matching_selected_pids
            or lifecycle.listener_executable != inspection.blender_executable
        ):
            raise InstallerError("selected Blender listener verification failed")
        try:
            session = mcp_probe.start(command, env=dict(env))
            initialized = session.initialize()
            if (
                type(initialized) is not dict
                or type(initialized.get("protocolVersion")) is not str
                or not initialized["protocolVersion"]
            ):
                raise ValueError("invalid initialize result")
        except Exception as exc:
            raise InstallerError("MCP handshake failed") from exc
        try:
            tools = tuple(session.list_tools())
        except Exception as exc:
            raise InstallerError("MCP catalog verification failed") from exc
        tool_count = len(tools)
        if tools != inspection.expected_tools:
            raise InstallerError("MCP catalog verification failed")
        try:
            result = session.call_tool("get_blendfile_summary_datablocks", {})
            if type(result) is not dict or result.get("isError") is True or "error" in result:
                raise ValueError("invalid tool result")
        except Exception as exc:
            raise InstallerError("Blender read-only verification failed") from exc
    except InstallerError as exc:
        error = exc
    except Exception:
        error = InstallerError("MCP verification failed")
    finally:
        cleanup_failed = False
        if session is not None:
            try:
                session.close()
            except Exception:
                cleanup_failed = True
            try:
                session.terminate()
            except Exception:
                cleanup_failed = True
            try:
                session.wait(_WAIT_TIMEOUT)
            except Exception:
                cleanup_failed = True
        try:
            changed = _snapshot(inspection.managed_targets) != before
        except InstallerError:
            changed = True
        if changed:
            error = InstallerError("managed targets changed during verification")
        elif cleanup_failed:
            error = InstallerError("MCP cleanup failed")
    if error is not None:
        raise error
    return VerificationResult(True, True, True, True, tool_count)
