from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import selectors
import stat
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

from .blender_adapter import (
    BlenderState,
    inspect_blender,
    load_extension_payload,
    probe_blender_lifecycle,
    verify_blender_files,
)
from .bundle import ReleaseManifest, StagedBundle
from .codex_adapter import (
    ManagedProfile,
    desired_codex_values,
    verify_codex_effective,
    verify_codex_toml,
)
from .filesystem import InstallerError, SafeRoot, TargetRef
from .model import ActiveSelector, InstallRoots, ReceiptStatus, parse_receipt
from .runtime import verify_runtime


_SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
_WAIT_TIMEOUT = 2.0
_HOST_TIMEOUT = 5.0
_MAX_STDOUT = 1024 * 1024
_MAX_STDERR = 64 * 1024
_MCP_TIMEOUT = 30.0
_VERSION = re.compile(r"[0-9][A-Za-z0-9.+-]*")
_MCP_COMMAND_ENV = "_BLENDER_MCP_PROBE_COMMAND"
_MCP_HELPER = r"""
import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    return value


async def probe():
    command = json.loads(os.environ.pop("_BLENDER_MCP_PROBE_COMMAND"))
    params = StdioServerParameters(command=command[0], args=command[1:], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            called = await session.call_tool("get_blendfile_summary_datablocks", arguments={})
            return {
                "initialize": dump(initialized),
                "tools": [tool.name for tool in tools.tools],
                "call": dump(called),
            }


raw = json.dumps(asyncio.run(asyncio.wait_for(probe(), 25.0)), separators=(",", ":"))
if len(raw.encode("utf-8")) > 1024 * 1024:
    raise RuntimeError("probe result is too large")
print(raw)
"""


class Runner(Protocol):
    def __call__(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> object: ...


class MCPClient(Protocol):
    def initialize(self) -> object: ...

    def list_tools(self) -> Sequence[str]: ...

    def call_tool(self, name: str, arguments: Mapping[str, object]) -> object: ...


class MCPHandle(Protocol):
    def open_client(self) -> MCPClient: ...

    def close(self) -> None: ...

    def terminate(self) -> None: ...

    def wait(self, timeout: float) -> object: ...


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_WAIT_TIMEOUT)


class MCPProbe(Protocol):
    # spawn is atomic: failure means no child or owned descriptor exists.
    def spawn(self, command: Sequence[str], *, env: Mapping[str, str]) -> MCPHandle: ...


class _OfficialMCPClient:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self.result: dict[str, object] | None = None

    def _collect(self) -> dict[str, object]:
        if self.result is not None:
            return self.result
        try:
            stdout, _stderr = self.process.communicate(timeout=_MCP_TIMEOUT)
            if self.process.poll() != 0 or len(stdout) > _MAX_STDOUT:
                raise ValueError("probe process failed")
            value = json.loads(stdout.decode("utf-8"))
            if type(value) is not dict or set(value) != {"initialize", "tools", "call"}:
                raise ValueError("invalid probe result")
            if (
                type(value["initialize"]) is not dict
                or type(value["tools"]) is not list
                or any(type(name) is not str or not name for name in value["tools"])
                or type(value["call"]) is not dict
            ):
                raise ValueError("invalid probe result")
        except Exception as exc:
            try:
                _stop_process(self.process)
            except Exception:
                pass
            raise InstallerError("official MCP probe failed") from exc
        self.result = value
        return value

    def initialize(self) -> object:
        return self._collect()["initialize"]

    def list_tools(self) -> Sequence[str]:
        return tuple(self._collect()["tools"])

    def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        if name != "get_blendfile_summary_datablocks" or dict(arguments):
            raise InstallerError("official MCP probe call mismatch")
        return self._collect()["call"]


class _OfficialMCPHandle:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self.client = _OfficialMCPClient(process)

    def open_client(self) -> MCPClient:
        return self.client

    def close(self) -> None:
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                stream.close()

    def terminate(self) -> None:
        _stop_process(self.process)

    def wait(self, timeout: float) -> object:
        return self.process.wait(timeout=timeout)


@dataclass(frozen=True)
class OfficialMCPProbe:
    runtime_python: Path

    def __post_init__(self) -> None:
        _absolute_executable(self.runtime_python, "runtime Python")

    def spawn(self, command: Sequence[str], *, env: Mapping[str, str]) -> MCPHandle:
        argv = tuple(command)
        if (
            not argv
            or not Path(argv[0]).is_absolute()
            or any(type(item) is not str for item in argv)
            or any(type(key) is not str or type(value) is not str for key, value in env.items())
        ):
            raise ValueError("invalid official MCP probe input")
        clean = dict(env)
        clean[_MCP_COMMAND_ENV] = json.dumps(argv, separators=(",", ":"))
        try:
            process = subprocess.Popen(
                (str(self.runtime_python), "-I", "-c", _MCP_HELPER),
                cwd=Path(argv[0]).parent,
                env=clean,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            raise InstallerError("official MCP probe failed") from exc
        return _OfficialMCPHandle(process)


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
    roots: InstallRoots
    blender_state: BlenderState
    receipt_path: Path | None

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


def _safe_directory_path(path: Path) -> None:
    current = Path("/")
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise ValueError("unsafe host profile path") from exc
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("unsafe host profile path")


def _text(value: object, maximum: int) -> str:
    if isinstance(value, bytes):
        if len(value) > maximum:
            raise InstallerError("host capability probe failed")
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InstallerError("host capability probe failed") from exc
    if type(value) is not str or len(value.encode("utf-8")) > maximum:
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
        output = _text(completed.stdout, _MAX_STDOUT)
        _text(completed.stderr, _MAX_STDERR)
    except InstallerError:
        raise
    except Exception as exc:
        raise InstallerError("host capability probe failed") from exc
    if type(code) is not int or code not in accepted:
        raise InstallerError("host capability probe failed")
    return code, output


def _version(output: str, product: str) -> str:
    lines = output.splitlines()
    prefix = f"{product} "
    if not lines or not lines[0].strip().startswith(prefix):
        raise InstallerError("host capability probe failed")
    version = lines[0].strip()[len(prefix) :]
    if product == "Blender" and version.endswith(" LTS"):
        version = version.removesuffix(" LTS")
    if _VERSION.fullmatch(version) is None:
        raise InstallerError("host capability probe failed")
    return version


def _default_runner(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]) -> object:
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None and process.stderr is not None
        output = {"stdout": bytearray(), "stderr": bytearray()}
        limits = {"stdout": _MAX_STDOUT, "stderr": _MAX_STDERR}
        deadline = time.monotonic() + _HOST_TIMEOUT
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise InstallerError("host capability probe failed")
                events = selector.select(remaining)
                if not events:
                    raise InstallerError("host capability probe failed")
                for key, _ in events:
                    name = key.data
                    chunk = os.read(key.fd, min(64 * 1024, limits[name] - len(output[name]) + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        output[name].extend(chunk)
                        if len(output[name]) > limits[name]:
                            raise InstallerError("host capability probe failed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise InstallerError("host capability probe failed")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise InstallerError("host capability probe failed") from exc
        return subprocess.CompletedProcess(
            argv,
            returncode,
            bytes(output["stdout"]),
            bytes(output["stderr"]),
        )
    except OSError as exc:
        raise InstallerError("host capability probe failed") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        pass
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()


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
    if "HOME" not in env:
        raise ValueError("HOME is required")
    home = Path(env["HOME"])
    if not home.is_absolute() or ".." in home.parts:
        raise ValueError("HOME must be an absolute lexical path")
    _safe_directory_path(home)
    clean = {
        "PATH": _SYSTEM_PATH,
        "HOME": str(home),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
    if "CODEX_HOME" in env:
        codex_home = Path(env["CODEX_HOME"])
        if not codex_home.is_absolute() or ".." in codex_home.parts:
            raise ValueError("CODEX_HOME must be an absolute lexical path")
        _safe_directory_path(codex_home)
        clean["CODEX_HOME"] = str(codex_home)
    profile_names = (
        "BLENDER_USER_RESOURCES",
        "BLENDER_USER_CONFIG",
        "BLENDER_USER_EXTENSIONS",
    )
    supplied = tuple(name in env for name in profile_names)
    if any(supplied) and not all(supplied):
        raise ValueError("isolated Blender profiles require all three user paths")
    if all(supplied):
        resources, config, extensions = (Path(env[name]) for name in profile_names)
        if any(
            not path.is_absolute() or ".." in path.parts for path in (resources, config, extensions)
        ):
            raise ValueError("Blender profile paths must be absolute lexical paths")
        if not config.is_relative_to(resources) or not extensions.is_relative_to(resources):
            raise ValueError("Blender profile paths must descend from resources")
        for path in (resources, config, extensions):
            _safe_directory_path(path)
        clean.update(
            dict(zip(profile_names, map(str, (resources, config, extensions)), strict=True))
        )
    version_probes = (
        (codex_bin, "codex-cli"),
        (uv_bin, "uv"),
        (blender_bin, "Blender"),
        (python_bin, "Python"),
    )
    versions = tuple(
        _version(_run(runner, (str(path), "--version"), cwd=path.parent, env=clean)[1], product)
        for path, product in version_probes
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


def _managed_paths(roots: InstallRoots, receipt_path: Path | None) -> tuple[Path, ...]:
    paths = (
        roots.runtime,
        roots.extension_target,
        roots.userpref_target,
        roots.codex_config,
        roots.active,
    )
    return paths if receipt_path is None else (*paths, receipt_path)


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


def _read_json(path: Path, *, private: bool = False) -> object:
    try:
        if private and stat.S_IMODE(path.lstat().st_mode) != 0o600:
            raise InstallerError("installation inspection failed")
        return json.loads(
            _read_regular(path).decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InstallerError("installation inspection failed") from exc


def _active_receipt_path(roots: InstallRoots):
    try:
        active = ActiveSelector.from_dict(_read_json(roots.active, private=True))
        receipt_path = roots.receipts / active.receipt_basename
    except (OSError, ValueError, InstallerError) as exc:
        raise InstallerError("active installation inspection failed") from exc
    return active, receipt_path


def _active_receipt(roots: InstallRoots):
    active, receipt_path = _active_receipt_path(roots)
    try:
        receipt = parse_receipt(_read_json(receipt_path, private=True), roots)
    except (OSError, ValueError, InstallerError) as exc:
        raise InstallerError("active installation inspection failed") from exc
    return active, receipt, receipt_path


def _inspect(
    bundle: StagedBundle,
    roots: InstallRoots,
    blender_state: BlenderState,
    host: HostCapabilities,
    images: tuple[str, ...],
    receipt_path: Path | None,
) -> InstallationInspection:
    manifest: ReleaseManifest = bundle.manifest
    active = receipt = None
    if receipt_path is None:
        if roots.active.exists() or roots.active.is_symlink():
            raise InstallerError("active installation changed during inspection")
    else:
        active, receipt, current_receipt_path = _active_receipt(roots)
        if current_receipt_path != receipt_path:
            raise InstallerError("active installation inspection failed")
    try:
        current_blender = inspect_blender(host.blender_bin, host.env, host.runner)
    except (OSError, ValueError, InstallerError) as exc:
        raise InstallerError("Blender inspection failed") from exc
    profile = ManagedProfile(
        roots.home,
        current_blender.user_resources,
        current_blender.config_root,
        current_blender.extensions_root,
        current_blender.executable,
    )
    profile_matches = (
        roots.blender.executable == host.blender_bin == current_blender.executable
        and roots.blender.user_resources == current_blender.user_resources
        and roots.blender.user_config == current_blender.config_root
        and roots.blender.user_extensions == current_blender.extensions_root
        and roots.blender.architecture == current_blender.reported_architecture
        and roots.blender.version == current_blender.version
        and roots.home == current_blender.home
        and host.env.get("HOME") == str(roots.home)
        and host.env.get("CODEX_HOME") == str(roots.codex_home)
        and host.env.get("BLENDER_USER_RESOURCES") == str(current_blender.user_resources)
        and host.env.get("BLENDER_USER_CONFIG") == str(current_blender.config_root)
        and host.env.get("BLENDER_USER_EXTENSIONS") == str(current_blender.extensions_root)
    )
    runtime_state = None
    if roots.data_root.exists():
        try:
            with SafeRoot.open(roots.data_root, os.getuid(), roots.data_root) as root:
                runtime_state = verify_runtime(
                    TargetRef(root, PurePath(roots.runtime.relative_to(roots.data_root))),
                    manifest,
                    profile,
                    host.runner,
                )
        except (OSError, ValueError, InstallerError):
            runtime_state = None
    expected_payload = load_extension_payload(bundle.extension_path)
    try:
        verify_blender_files(current_blender, expected_payload)
        blender_files_exact = True
    except (OSError, ValueError, InstallerError):
        blender_files_exact = False
    runtime = runtime_state is not None and runtime_state.exact and profile_matches
    extension_repository = (
        current_blender.repository == manifest.extension["repository"] and blender_files_exact
    )
    extension_id = current_blender.manifest_id == manifest.extension["id"] and blender_files_exact
    extension_version = (
        current_blender.manifest_version == manifest.extension["version"] and blender_files_exact
    )
    extension_payload_digest = (
        current_blender.canonical_payload_digest == expected_payload.canonical_digest
        and blender_files_exact
    )
    enablement = current_blender.enabled is True and blender_files_exact
    preferences = (
        current_blender.online_access is True
        and current_blender.host == "localhost"
        and current_blender.port == 9876
        and current_blender.autostart is True
        and blender_files_exact
    )
    launcher = None if runtime_state is None else runtime_state.launcher_path
    desired = None if launcher is None else desired_codex_values(launcher, profile, manifest.tools)
    codex_policy = codex_namespace = parsed_verified = False
    try:
        raw = _read_regular(roots.codex_config)
        if desired is None:
            codex_policy = codex_namespace = False
        else:
            codex_policy, codex_namespace = _codex_checks(raw, desired)
            verify_codex_toml(raw, desired)
            parsed_verified = True
    except (FileNotFoundError, InstallerError):
        pass
    codex_policy = codex_policy and parsed_verified
    codex_namespace = codex_namespace and parsed_verified
    codex_effective = False
    active_generation = (
        receipt is not None
        and active is not None
        and receipt.status is ReceiptStatus.INSTALLED
        and receipt.install_id == active.install_id
        and receipt.generation == active.generation
    )
    manifest_hash = False
    if receipt is not None:
        expected_manifest_hash = hashlib.sha256(_read_regular(bundle.manifest_path)).hexdigest()
        manifest_hash = (
            receipt.bundle["version"] == manifest.bundle_version
            and receipt.bundle["manifest_sha256"] == expected_manifest_hash
        )
    recorded_blender_executable = (
        receipt is not None
        and profile_matches
        and blender_state.executable == current_blender.executable
        and blender_state.reported_binary == current_blender.reported_binary
        and receipt.host["blender_executable"] == str(current_blender.executable)
        and receipt.host["blender_architecture"] == current_blender.reported_architecture
        and receipt.host["blender_version"] == current_blender.version
        and receipt.host["codex_version"] == host.codex_version
        and receipt.host["uv_version"] == host.uv_version
        and receipt.host["python_version"] == host.python_version
    )
    if desired is not None and active_generation:
        try:
            verify_codex_effective(host.codex_bin, desired, host.env)
            codex_effective = True
        except (OSError, ValueError, InstallerError):
            codex_effective = False
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
        current_blender.executable,
        command,
        manifest.tools,
        _managed_paths(roots, receipt_path),
        images,
        None if active is None else str(active.install_id),
        roots,
        current_blender,
        receipt_path,
    )


def inspect_installation(
    bundle: StagedBundle,
    roots: InstallRoots,
    blender_state: BlenderState,
    host: HostCapabilities,
) -> InstallationInspection:
    if (
        type(bundle) is not StagedBundle
        or type(roots) is not InstallRoots
        or type(blender_state) is not BlenderState
        or type(host) is not HostCapabilities
    ):
        raise ValueError("invalid installation inspection input")
    base_paths = _managed_paths(roots, None)
    base_before = _snapshot(base_paths)
    paths = base_paths
    before = base_before
    receipt_path = None
    setup_error = None
    if base_before[-1] != "absent":
        try:
            _, receipt_path = _active_receipt_path(roots)
            paths = _managed_paths(roots, receipt_path)
            before = _snapshot(paths)
            if before[: len(base_paths)] != base_before:
                raise InstallerError("managed targets changed during inspection")
        except InstallerError as exc:
            setup_error = exc
    inspection = None
    error = setup_error
    if error is None:
        try:
            inspection = _inspect(bundle, roots, blender_state, host, before, receipt_path)
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


def _valid_initialize(value: object, manifest: ReleaseManifest) -> bool:
    if type(value) is not dict or set(value) != {
        "protocolVersion",
        "capabilities",
        "serverInfo",
    }:
        return False
    capabilities = value["capabilities"]
    server = value["serverInfo"]
    return (
        type(value["protocolVersion"]) is str
        and value["protocolVersion"] == "2025-06-18"
        and type(capabilities) is dict
        and set(capabilities) == {"tools"}
        and type(capabilities["tools"]) is dict
        and not capabilities["tools"]
        and type(server) is dict
        and set(server) == {"name", "version"}
        and type(server["name"]) is str
        and server["name"] == manifest.server["distribution"]
        and type(server["version"]) is str
        and server["version"] == manifest.server["version"]
    )


def verify_live(
    bundle: StagedBundle,
    inspection: InstallationInspection,
    runtime_command: Sequence[str],
    codex_bin: Path,
    env: Mapping[str, str],
    mcp_probe: MCPProbe,
) -> VerificationResult:
    if type(bundle) is not StagedBundle or type(inspection) is not InstallationInspection:
        raise ValueError("invalid live verification input")
    if type(inspection.roots) is not InstallRoots:
        raise InstallerError("invalid installation inspection")
    _, receipt_path = _active_receipt_path(inspection.roots)
    canonical_paths = _managed_paths(inspection.roots, receipt_path)
    if (
        inspection.managed_targets != canonical_paths
        or inspection.receipt_path != receipt_path
        or len(inspection.managed_images) != len(canonical_paths)
    ):
        raise InstallerError("invalid installation inspection")
    before = _snapshot(canonical_paths)
    if before != inspection.managed_images:
        raise InstallerError("stale installation inspection")
    handle: MCPHandle | None = None
    client: MCPClient | None = None
    error: InstallerError | None = None
    tool_count = 0
    try:
        fresh = inspect_installation(
            bundle,
            inspection.roots,
            inspection.blender_state,
            inspection.host,
        )
        if fresh.managed_targets != canonical_paths or fresh.managed_images != before:
            raise InstallerError("stale installation inspection")
        command = tuple(runtime_command)
        if command != fresh.runtime_command or not command or not Path(command[0]).is_absolute():
            raise InstallerError("managed runtime command mismatch")
        if codex_bin != fresh.host.codex_bin:
            raise InstallerError("Codex executable mismatch")
        if not fresh.exact or tuple(bundle.manifest.tools) != fresh.expected_tools:
            raise InstallerError("installation inspection is not exact")
        try:
            lifecycle = probe_blender_lifecycle(fresh.blender_executable, fresh.host.runner)
        except Exception as exc:
            raise InstallerError("selected Blender listener verification failed") from exc
        if (
            lifecycle.port_free
            or lifecycle.listener_pid is None
            or lifecycle.listener_pid not in lifecycle.matching_selected_pids
            or lifecycle.listener_executable != fresh.blender_executable
        ):
            raise InstallerError("selected Blender listener verification failed")
        try:
            handle = mcp_probe.spawn(command, env=dict(env))
        except Exception as exc:
            raise InstallerError("MCP spawn failed") from exc
        try:
            client = handle.open_client()
            initialized = client.initialize()
            if not _valid_initialize(initialized, bundle.manifest):
                raise ValueError("invalid initialize result")
        except Exception as exc:
            raise InstallerError("MCP handshake failed") from exc
        try:
            tools = tuple(client.list_tools())
        except Exception as exc:
            raise InstallerError("MCP catalog verification failed") from exc
        tool_count = len(tools)
        if tools != fresh.expected_tools:
            raise InstallerError("MCP catalog verification failed")
        try:
            result = client.call_tool("get_blendfile_summary_datablocks", {})
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
        if handle is not None:
            try:
                handle.close()
            except Exception:
                cleanup_failed = True
            try:
                handle.terminate()
            except Exception:
                cleanup_failed = True
            try:
                handle.wait(_WAIT_TIMEOUT)
            except Exception:
                cleanup_failed = True
        try:
            changed = _snapshot(canonical_paths) != before
        except InstallerError:
            changed = True
        if changed:
            error = InstallerError("managed targets changed during verification")
        elif cleanup_failed:
            error = InstallerError("MCP cleanup failed")
    if error is not None:
        raise error
    return VerificationResult(True, True, True, True, tool_count)
