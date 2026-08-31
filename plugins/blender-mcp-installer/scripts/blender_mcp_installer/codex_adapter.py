from __future__ import annotations

import hashlib
import json
import os
import selectors
import stat
import subprocess
import time
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Mapping, Sequence

from .filesystem import (
    FaultInjector,
    InstallerError,
    NoOpFaultInjector,
    RestoreState,
    StagedFile,
    TargetRef,
    capture_file,
    conditional_remove_file,
    conditional_swap_file,
    create_deterministic_stage,
    restore_file,
)
from .model import FileImage, ImageState


_SERVER_KEYS = (
    "command",
    "args",
    "omit_tools_from",
    "startup_timeout_sec",
    "tool_timeout_sec",
    "default_tools_approval_mode",
    "enabled_tools",
)
_FORBIDDEN_SERVER_KEYS = ("disabled_tools", "tools")
_ENV_KEYS = (
    "HOME",
    "BLENDER_USER_RESOURCES",
    "BLENDER_USER_CONFIG",
    "BLENDER_USER_EXTENSIONS",
    "BLENDER_PATH",
    "BLENDER_MCP_HOST",
    "BLENDER_MCP_PORT",
    "PYTHONNOUSERSITE",
    "PYTHONSAFEPATH",
)
_NAMESPACE = "mcp__blender"
_MAX_CONFIG = 16 * 1024 * 1024
_MAX_STDERR = 64 * 1024
_EFFECTIVE_TIMEOUT = 2.0
_TOOL_TIMEOUT_SEC = 150.0


def _absolute(path: Path, label: str) -> Path:
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be an absolute lexical path")
    return path


@dataclass(frozen=True)
class ManagedProfile:
    home: Path
    blender_user_resources: Path
    blender_user_config: Path
    blender_user_extensions: Path
    blender_path: Path

    def __post_init__(self) -> None:
        for name, value in (
            ("HOME", self.home),
            ("Blender user resources", self.blender_user_resources),
            ("Blender user config", self.blender_user_config),
            ("Blender user extensions", self.blender_user_extensions),
            ("Blender executable", self.blender_path),
        ):
            _absolute(value, name)
        if not self.blender_user_config.is_relative_to(
            self.blender_user_resources
        ) or not self.blender_user_extensions.is_relative_to(self.blender_user_resources):
            raise ValueError("Blender profile paths must descend from user resources")


@dataclass(frozen=True)
class ManagedCodexValues:
    command: str
    args: tuple[str, ...]
    omit_tools_from: tuple[str, ...]
    startup_timeout_sec: float
    tool_timeout_sec: float
    default_tools_approval_mode: str
    enabled_tools: tuple[str, ...]
    env: Mapping[str, str]
    direct_only_namespace: str

    def __post_init__(self) -> None:
        if not Path(self.command).is_absolute():
            raise ValueError("managed Codex command must be absolute")
        if self.args != () or self.omit_tools_from != ():
            raise ValueError("managed Codex argument policy is fixed")
        if (
            type(self.startup_timeout_sec) is not float
            or self.startup_timeout_sec != 20.0
            or type(self.tool_timeout_sec) is not float
            or self.tool_timeout_sec != _TOOL_TIMEOUT_SEC
            or self.default_tools_approval_mode != "approve"
        ):
            raise ValueError("managed Codex timeout/approval policy is fixed")
        if (
            type(self.enabled_tools) is not tuple
            or not self.enabled_tools
            or any(type(tool) is not str or not tool for tool in self.enabled_tools)
            or len(set(self.enabled_tools)) != len(self.enabled_tools)
        ):
            raise ValueError("managed Codex tools must be unique non-empty names")
        if set(self.env) != set(_ENV_KEYS) or any(
            type(key) is not str or type(value) is not str for key, value in self.env.items()
        ):
            raise ValueError("invalid managed Codex environment")
        if (
            self.env["BLENDER_MCP_HOST"] != "localhost"
            or self.env["BLENDER_MCP_PORT"] != "9876"
            or self.env["PYTHONNOUSERSITE"] != "1"
            or self.env["PYTHONSAFEPATH"] != "1"
            or self.direct_only_namespace != _NAMESPACE
        ):
            raise ValueError("invalid managed Codex fixed values")
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))

    def helper_dict(self) -> dict[str, object]:
        return {
            "server": {
                "command": self.command,
                "args": list(self.args),
                "omit_tools_from": list(self.omit_tools_from),
                "startup_timeout_sec": self.startup_timeout_sec,
                "tool_timeout_sec": self.tool_timeout_sec,
                "default_tools_approval_mode": self.default_tools_approval_mode,
                "enabled_tools": list(self.enabled_tools),
            },
            "env": dict(self.env),
            "forbidden_server_keys": list(_FORBIDDEN_SERVER_KEYS),
            "namespace": self.direct_only_namespace,
        }


@dataclass(frozen=True)
class ManagedCodexKeys:
    desired: ManagedCodexValues
    server_keys: tuple[str, ...] = _SERVER_KEYS
    env_keys: tuple[str, ...] = _ENV_KEYS
    forbidden_server_keys: tuple[str, ...] = _FORBIDDEN_SERVER_KEYS
    namespace: str = _NAMESPACE

    def __post_init__(self) -> None:
        if (
            type(self.desired) is not ManagedCodexValues
            or self.server_keys != _SERVER_KEYS
            or self.env_keys != _ENV_KEYS
            or self.forbidden_server_keys != _FORBIDDEN_SERVER_KEYS
            or self.namespace != _NAMESPACE
        ):
            raise ValueError("invalid managed Codex key metadata")

    def to_dict(self) -> dict[str, object]:
        return {
            "server_keys": list(self.server_keys),
            "env_keys": list(self.env_keys),
            "forbidden_server_keys": list(self.forbidden_server_keys),
            "namespace": self.namespace,
        }


@dataclass(frozen=True)
class CodexChange:
    current: FileImage
    stage: StagedFile
    post: FileImage
    managed_keys: ManagedCodexKeys
    changed: bool


@dataclass(frozen=True)
class EffectiveCodexState:
    command: str
    args: tuple[str, ...]
    env: Mapping[str, str]
    enabled_tools: tuple[str, ...]
    startup_timeout_sec: float
    tool_timeout_sec: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "env", MappingProxyType(dict(self.env)))


class RollbackState(str, Enum):
    RESTORING = "restoring"
    RESTORED = "restored"
    C1 = "semantic_staged"
    C2 = "semantic_swapped"
    C3 = "semantic_restoring"
    C4 = "semantic_restored"


@dataclass(frozen=True)
class RollbackResult:
    state: RollbackState
    current: FileImage
    rollback_stage: FileImage
    recovery: FileImage
    rollback_intended: FileImage | None
    rollback_displaced: FileImage | None
    restored: bool

    def __post_init__(self) -> None:
        if (
            any(
                type(image) is not FileImage
                for image in (self.current, self.rollback_stage, self.recovery)
            )
            or type(self.restored) is not bool
        ):
            raise ValueError("invalid Codex rollback result images")
        semantic = self.state in {
            RollbackState.C1,
            RollbackState.C2,
            RollbackState.C3,
            RollbackState.C4,
        }
        if semantic:
            if (
                self.rollback_intended is None
                or self.rollback_intended.state is not ImageState.PRESENT
                or (self.state is RollbackState.C1) != (self.rollback_displaced is None)
                or (
                    self.rollback_displaced is not None
                    and self.rollback_displaced.state is not ImageState.PRESENT
                )
                or self.restored != (self.state is RollbackState.C4)
            ):
                raise ValueError("invalid Codex semantic rollback result")
        elif (
            self.rollback_intended is not None
            or self.rollback_displaced is not None
            or self.restored != (self.state is RollbackState.RESTORED)
        ):
            raise ValueError("invalid Codex native rollback result")

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "current": self.current.to_dict(),
            "rollback_stage": self.rollback_stage.to_dict(),
            "recovery": self.recovery.to_dict(),
            "rollback_intended": (
                None if self.rollback_intended is None else self.rollback_intended.to_dict()
            ),
            "rollback_displaced": (
                None if self.rollback_displaced is None else self.rollback_displaced.to_dict()
            ),
            "restored": self.restored,
        }

    @classmethod
    def from_dict(cls, value: object) -> RollbackResult:
        keys = {
            "state",
            "current",
            "rollback_stage",
            "recovery",
            "rollback_intended",
            "rollback_displaced",
            "restored",
        }
        if type(value) is not dict or set(value) != keys:
            raise ValueError("invalid Codex rollback result")
        try:
            state = RollbackState(value["state"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Codex rollback state") from exc
        intended = value["rollback_intended"]
        displaced = value["rollback_displaced"]
        if type(value["restored"]) is not bool:
            raise ValueError("invalid Codex rollback completion")
        return cls(
            state,
            FileImage.from_dict(value["current"]),
            FileImage.from_dict(value["rollback_stage"]),
            FileImage.from_dict(value["recovery"]),
            None if intended is None else FileImage.from_dict(intended),
            None if displaced is None else FileImage.from_dict(displaced),
            value["restored"],
        )


@dataclass(frozen=True)
class CodexRollbackContext:
    target: TargetRef
    forward_stage: StagedFile
    rollback_stage: StagedFile
    state: RollbackState | None
    rollback_intended: FileImage | None
    rollback_displaced: FileImage | None
    journal: Callable[[RollbackResult], None]

    def __post_init__(self) -> None:
        if (
            type(self.target) is not TargetRef
            or type(self.forward_stage) is not StagedFile
            or type(self.rollback_stage) is not StagedFile
            or (self.state is not None and type(self.state) is not RollbackState)
            or not callable(self.journal)
        ):
            raise ValueError("invalid Codex rollback context")
        if (self.rollback_intended is None) != (self.state not in {RollbackState.C1}):
            if self.state not in {RollbackState.C2, RollbackState.C3, RollbackState.C4}:
                raise ValueError("invalid Codex rollback intended image")
        if self.state in {RollbackState.C2, RollbackState.C3, RollbackState.C4}:
            if self.rollback_intended is None or self.rollback_displaced is None:
                raise ValueError("incomplete Codex semantic rollback images")
        elif self.rollback_displaced is not None:
            raise ValueError("unexpected Codex rollback displaced image")


def desired_codex_values(
    managed_launcher: Path,
    profile: ManagedProfile,
    tools: Sequence[str],
) -> ManagedCodexValues:
    launcher = _absolute(managed_launcher, "managed launcher")
    catalog = tuple(tools)
    if not catalog or any(type(tool) is not str or not tool for tool in catalog):
        raise ValueError("managed tool catalog is empty or invalid")
    if len(catalog) != len(set(catalog)):
        raise ValueError("managed tool catalog contains duplicates")
    return ManagedCodexValues(
        command=str(launcher),
        args=(),
        omit_tools_from=(),
        startup_timeout_sec=20.0,
        tool_timeout_sec=_TOOL_TIMEOUT_SEC,
        default_tools_approval_mode="approve",
        enabled_tools=catalog,
        env={
            "HOME": str(profile.home),
            "BLENDER_USER_RESOURCES": str(profile.blender_user_resources),
            "BLENDER_USER_CONFIG": str(profile.blender_user_config),
            "BLENDER_USER_EXTENSIONS": str(profile.blender_user_extensions),
            "BLENDER_PATH": str(profile.blender_path),
            "BLENDER_MCP_HOST": "localhost",
            "BLENDER_MCP_PORT": "9876",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
        },
        direct_only_namespace=_NAMESPACE,
    )


_HELPER = r"""
import copy
import hashlib
import json
import os
import sys

import tomlkit

MISSING = object()
MAX_CONFIG = 16 * 1024 * 1024


def read_fd(fd):
    try:
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError:
        pass
    chunks = []
    size = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_CONFIG:
            raise ValueError("too large")
        chunks.append(chunk)
    return b"".join(chunks)


def parse(raw):
    return tomlkit.parse(raw.decode("utf-8")) if raw else tomlkit.document()


def table(parent, key, create):
    value = parent.get(key)
    if value is None:
        if not create:
            return None
        value = tomlkit.table()
        parent[key] = value
    if not hasattr(value, "get") or isinstance(value, list):
        raise ValueError("not a table")
    return value


def plain(value):
    return value.unwrap() if hasattr(value, "unwrap") else value


def assign(parent, key, value):
    item = tomlkit.item(value)
    old = parent.get(key)
    if old is not None and hasattr(old, "trivia"):
        item._trivia = copy.copy(old.trivia)
    parent[key] = item


def restore(parent, key, pre_parent):
    if pre_parent is None or key not in pre_parent:
        if key in parent:
            del parent[key]
    else:
        parent[key] = copy.deepcopy(pre_parent[key])


def merge_forward(current, desired):
    servers = table(current, "mcp_servers", True)
    server = table(servers, "blender", True)
    for key, value in desired["server"].items():
        assign(server, key, value)
    for key in desired["forbidden_server_keys"]:
        if key in server:
            del server[key]
    env = table(server, "env", True)
    for key, value in desired["env"].items():
        assign(env, key, value)
    features = table(current, "features", True)
    code_mode = table(features, "code_mode", True)
    namespaces = code_mode.get("direct_only_tool_namespaces")
    if namespaces is None:
        namespaces = tomlkit.array()
        code_mode["direct_only_tool_namespaces"] = namespaces
    if not isinstance(plain(namespaces), list) or any(
        type(item) is not str for item in plain(namespaces)
    ):
        raise ValueError("invalid namespace array")
    if plain(namespaces).count(desired["namespace"]) > 1:
        raise ValueError("duplicate managed namespace")
    if desired["namespace"] not in plain(namespaces):
        namespaces.append(desired["namespace"])


def get_tables(document, create):
    servers = table(document, "mcp_servers", create)
    server = None if servers is None else table(servers, "blender", create)
    env = None if server is None else table(server, "env", create)
    features = table(document, "features", create)
    code_mode = None if features is None else table(features, "code_mode", create)
    return servers, server, env, features, code_mode


def item_value(parent, key):
    return MISSING if parent is None or key not in parent else plain(parent[key])


def reconcile(parent, pre_parent, key, post):
    current = item_value(parent, key)
    pre = item_value(pre_parent, key)
    if current == post:
        restore(parent, key, pre_parent)
    elif current != pre:
        raise RuntimeError("managed_conflict")


def prune(document, servers, server, env, features, code_mode):
    if env is not None and not env and server is not None and "env" in server:
        del server["env"]
    if server is not None and not server and servers is not None and "blender" in servers:
        del servers["blender"]
    if servers is not None and not servers and "mcp_servers" in document:
        del document["mcp_servers"]
    if code_mode is not None and not code_mode and features is not None and "code_mode" in features:
        del features["code_mode"]
    if features is not None and not features and "features" in document:
        del document["features"]


def merge_rollback(current, pre, desired):
    servers, server, env, features, code_mode = get_tables(current, True)
    _, pre_server, pre_env, _, pre_code_mode = get_tables(pre, False)
    for key, post in desired["server"].items():
        reconcile(server, pre_server, key, post)
    for key in desired["forbidden_server_keys"]:
        reconcile(server, pre_server, key, MISSING)
    for key, post in desired["env"].items():
        reconcile(env, pre_env, key, post)
    namespace = desired["namespace"]
    current_namespaces = item_value(code_mode, "direct_only_tool_namespaces")
    pre_namespaces = item_value(pre_code_mode, "direct_only_tool_namespaces")
    if current_namespaces is not MISSING and (
        not isinstance(current_namespaces, list)
        or any(type(item) is not str for item in current_namespaces)
    ):
        raise RuntimeError("managed_conflict")
    pre_has = pre_namespaces is not MISSING and namespace in pre_namespaces
    current_has = current_namespaces is not MISSING and namespace in current_namespaces
    if (
        (pre_namespaces is not MISSING and pre_namespaces.count(namespace) > 1)
        or (current_namespaces is not MISSING and current_namespaces.count(namespace) > 1)
    ):
        raise RuntimeError("managed_conflict")
    if pre_has and not current_has:
        raise RuntimeError("managed_conflict")
    if not pre_has and current_has:
        namespaces = code_mode["direct_only_tool_namespaces"]
        del namespaces[plain(namespaces).index(namespace)]
        if not plain(namespaces):
            del code_mode["direct_only_tool_namespaces"]
    prune(current, servers, server, env, features, code_mode)


def write_stage(fd, raw):
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    offset = 0
    while offset < len(raw):
        offset += os.write(fd, raw[offset:])
    os.fchmod(fd, 0o600)
    os.fsync(fd)


request_fd = int(sys.argv[1])
request = json.loads(read_fd(request_fd).decode("utf-8"))
try:
    current_raw = read_fd(request["current_fd"]) if request["current_fd"] is not None else b""
    current = parse(current_raw)
    if request["mode"] == "forward":
        merge_forward(current, request["desired"])
    elif request["mode"] in {"rollback", "validate"}:
        pre_raw = read_fd(request["pre_fd"]) if request["pre_fd"] is not None else b""
        merge_rollback(current, parse(pre_raw), request["desired"])
    else:
        raise ValueError("mode")
    raw = tomlkit.dumps(current).encode("utf-8")
    if request["stage_fd"] is not None:
        write_stage(request["stage_fd"], raw)
    print(json.dumps({
        "changed": raw != current_raw,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
    }))
except RuntimeError as exc:
    if str(exc) == "managed_conflict":
        print('{"error":"managed_conflict"}')
        raise SystemExit(3)
    raise
finally:
    for key in ("current_fd", "pre_fd", "stage_fd"):
        fd = request.get(key)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
    try:
        os.close(request_fd)
    except OSError:
        pass
"""


def _write_all(fd: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        offset += os.write(fd, raw[offset:])


def _hash_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while chunk := os.read(fd, 1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _fd_image(fd: int, error: str = "Codex configuration input changed") -> FileImage:
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid():
            raise InstallerError(error)
        digest = _hash_fd(fd)
        after = os.fstat(fd)
    except OSError as exc:
        raise InstallerError(error) from exc
    fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_size", "st_mtime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise InstallerError(error)
    return FileImage(
        ImageState.PRESENT,
        after.st_dev,
        after.st_ino,
        after.st_uid,
        stat.S_IMODE(after.st_mode),
        after.st_size,
        after.st_mtime_ns,
        digest,
    )


def _open_validated_fd(fd: int | None, expected: FileImage) -> int | None:
    if expected.state is ImageState.ABSENT:
        if fd is not None:
            raise InstallerError("Codex configuration input changed")
        return None
    if fd is None:
        raise InstallerError("Codex configuration input changed")
    duplicate = os.dup(fd)
    try:
        if _fd_image(duplicate) != expected:
            raise InstallerError("Codex configuration input changed")
        return duplicate
    except BaseException:
        os.close(duplicate)
        raise


def _open_reference(reference: TargetRef, expected: FileImage) -> int | None:
    if expected.state is ImageState.ABSENT:
        return None
    parent_fd, name = reference.root.open_parent(reference.relative)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        if _fd_image(fd, "Codex rollback state conflict") != expected:
            raise InstallerError("Codex rollback state conflict")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _helper_request(
    stage: StagedFile,
    request: Mapping[str, object],
) -> int:
    parent_fd, _ = stage.root.open_parent(stage.relative)
    name = f"{stage.relative.name}.request"
    try:
        fd = os.open(
            name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, json.dumps(request, sort_keys=True, separators=(",", ":")).encode())
            os.fsync(fd)
            os.unlink(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
            os.lseek(fd, 0, os.SEEK_SET)
            return fd
        except BaseException:
            os.close(fd)
            try:
                os.unlink(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except FileNotFoundError:
                pass
            raise
    except FileExistsError as exc:
        raise InstallerError("Codex helper request already exists") from exc
    finally:
        os.close(parent_fd)


def _invoke_helper(
    anchor: StagedFile,
    request: Mapping[str, object],
    runtime_python: Path,
    inherited: tuple[int, ...],
) -> dict[str, object]:
    runtime_python = _absolute(runtime_python, "runtime Python")
    if not runtime_python.exists() or not os.access(runtime_python, os.X_OK):
        raise InstallerError("locked runtime Python is unavailable")
    request_fd = _helper_request(anchor, request)
    try:
        try:
            completed = subprocess.run(
                [str(runtime_python), "-I", "-B", "-c", _HELPER, str(request_fd)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                    "PYTHONNOUSERSITE": "1",
                    "PYTHONSAFEPATH": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                pass_fds=(request_fd, *inherited),
                check=False,
            )
        except OSError as exc:
            raise InstallerError("Codex configuration merge failed") from exc
        try:
            output = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            output = None
        if completed.returncode == 3 and output == {"error": "managed_conflict"}:
            raise InstallerError("Codex managed key conflict")
        if completed.returncode != 0 or type(output) is not dict:
            raise InstallerError("Codex configuration merge failed")
        return output
    finally:
        os.close(request_fd)


def _invoke_readonly_helper(
    request: Mapping[str, object],
    runtime_python: Path,
    inherited: tuple[int, ...],
) -> dict[str, object]:
    runtime_python = _absolute(runtime_python, "runtime Python")
    if not runtime_python.exists() or not os.access(runtime_python, os.X_OK):
        raise InstallerError("locked runtime Python is unavailable")
    request_fd, writer = os.pipe()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [str(runtime_python), "-I", "-B", "-c", _HELPER, str(request_fd)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "PYTHONNOUSERSITE": "1",
                "PYTHONSAFEPATH": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            pass_fds=(request_fd, *inherited),
        )
        os.close(request_fd)
        request_fd = -1
        _write_all(writer, json.dumps(request, sort_keys=True, separators=(",", ":")).encode())
        os.close(writer)
        writer = -1
        stdout, _stderr = process.communicate(timeout=_EFFECTIVE_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallerError("Codex configuration merge failed") from exc
    finally:
        if request_fd >= 0:
            os.close(request_fd)
        if writer >= 0:
            os.close(writer)
        cleanup_error: OSError | subprocess.TimeoutExpired | None = None
        if process is not None:
            try:
                running = process.poll() is None
            except OSError as exc:
                cleanup_error = exc
                running = False
            if running:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    cleanup_error = exc
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    except OSError as exc:
                        cleanup_error = cleanup_error or exc
                    try:
                        process.wait(timeout=0.25)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        cleanup_error = cleanup_error or exc
                except OSError as exc:
                    cleanup_error = cleanup_error or exc
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except OSError as exc:
                        cleanup_error = cleanup_error or exc
            if cleanup_error is not None:
                raise InstallerError("Codex configuration merge cleanup failed") from cleanup_error
    try:
        output = json.loads(stdout.decode("utf-8"))
    except (UnboundLocalError, UnicodeDecodeError, json.JSONDecodeError):
        output = None
    if process is None or (process.returncode == 3 and output == {"error": "managed_conflict"}):
        raise InstallerError("Codex managed key conflict")
    if process.returncode != 0 or type(output) is not dict:
        raise InstallerError("Codex configuration merge failed")
    return output


def _run_helper(
    mode: str,
    current_fd: int | None,
    pre_fd: int | None,
    desired: ManagedCodexValues,
    runtime_python: Path,
    stage: StagedFile,
) -> tuple[StagedFile, bool]:
    runtime_python = _absolute(runtime_python, "runtime Python")
    if not runtime_python.exists() or not os.access(runtime_python, os.X_OK):
        raise InstallerError("locked runtime Python is unavailable")
    if stage.capture() != stage.image or stage.image.state is not ImageState.PRESENT:
        raise InstallerError("Codex stage changed before merge")
    parent_fd, name = stage.root.open_parent(stage.relative)
    try:
        stage_fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        if _fd_image(stage_fd, "Codex stage changed before merge") != stage.image:
            raise InstallerError("Codex stage changed before merge")
        request = {
            "mode": mode,
            "current_fd": current_fd,
            "pre_fd": pre_fd,
            "stage_fd": stage_fd,
            "desired": desired.helper_dict(),
        }
        output = _invoke_helper(
            stage,
            request,
            runtime_python,
            tuple(fd for fd in (current_fd, pre_fd, stage_fd) if fd is not None),
        )
        if (
            set(output) != {"changed", "sha256", "size"}
            or type(output["changed"]) is not bool
            or type(output["sha256"]) is not str
            or type(output["size"]) is not int
        ):
            raise InstallerError("Codex configuration merge failed")
        descriptor = _fd_image(stage_fd, "Codex stage changed")
        try:
            refreshed = stage.refresh()
        except (OSError, ValueError) as exc:
            raise InstallerError("Codex stage changed") from exc
        if (
            refreshed.image.state is not ImageState.PRESENT
            or refreshed.image.mode != 0o600
            or refreshed.image != descriptor
            or (descriptor.dev, descriptor.ino, descriptor.uid)
            != (stage.image.dev, stage.image.ino, stage.image.uid)
            or refreshed.image.sha256 != output["sha256"]
            or refreshed.image.size != output["size"]
        ):
            raise InstallerError("Codex stage changed")
        return refreshed, output["changed"]
    finally:
        os.close(stage_fd)


def _validate_semantic_merge(
    source: TargetRef,
    source_image: FileImage,
    recovery: TargetRef,
    recovery_image: FileImage,
    desired: ManagedCodexValues,
    runtime_python: Path,
    _anchor: StagedFile,
    intended: FileImage,
) -> None:
    source_fd = _open_reference(source, source_image)
    assert source_fd is not None
    try:
        pre_fd = _open_reference(recovery, recovery_image)
        try:
            output = _invoke_readonly_helper(
                {
                    "mode": "validate",
                    "current_fd": source_fd,
                    "pre_fd": pre_fd,
                    "stage_fd": None,
                    "desired": desired.helper_dict(),
                },
                runtime_python,
                tuple(fd for fd in (source_fd, pre_fd) if fd is not None),
            )
            _revalidate_reference(source, source_image, source_fd)
            _revalidate_reference(recovery, recovery_image, pre_fd)
        finally:
            if pre_fd is not None:
                os.close(pre_fd)
    finally:
        os.close(source_fd)
    if (
        set(output) != {"changed", "sha256", "size"}
        or type(output["changed"]) is not bool
        or output["sha256"] != intended.sha256
        or output["size"] != intended.size
        or _capture(source) != source_image
        or _capture(recovery) != recovery_image
    ):
        raise InstallerError("Codex rollback state conflict")


def _preflight_merge(
    source: TargetRef,
    source_image: FileImage,
    recovery: TargetRef,
    recovery_image: FileImage,
    desired: ManagedCodexValues,
    runtime_python: Path,
    intended: FileImage | None,
) -> None:
    source_fd = _open_reference(source, source_image)
    if source_fd is None:
        raise InstallerError("Codex rollback state conflict")
    try:
        pre_fd = _open_reference(recovery, recovery_image)
        try:
            output = _invoke_readonly_helper(
                {
                    "mode": "validate",
                    "current_fd": source_fd,
                    "pre_fd": pre_fd,
                    "stage_fd": None,
                    "desired": desired.helper_dict(),
                },
                runtime_python,
                tuple(fd for fd in (source_fd, pre_fd) if fd is not None),
            )
            _revalidate_reference(source, source_image, source_fd)
            _revalidate_reference(recovery, recovery_image, pre_fd)
        finally:
            if pre_fd is not None:
                os.close(pre_fd)
    finally:
        os.close(source_fd)
    if (
        set(output) != {"changed", "sha256", "size"}
        or type(output["changed"]) is not bool
        or (intended is not None and output["sha256"] != intended.sha256)
        or (intended is not None and output["size"] != intended.size)
        or _capture(source) != source_image
        or _capture(recovery) != recovery_image
    ):
        raise InstallerError("Codex rollback state conflict")


def _revalidate_reference(
    reference: TargetRef,
    expected: FileImage,
    fd: int | None,
) -> None:
    actual = _capture(reference) if fd is None else _fd_image(fd, "Codex rollback state conflict")
    if actual != expected:
        raise InstallerError("Codex rollback state conflict")


def stage_codex_config(
    live_config_fd: int | None,
    current: FileImage,
    desired: ManagedCodexValues,
    runtime_python: Path,
    stage: StagedFile,
) -> CodexChange:
    current_fd = _open_validated_fd(live_config_fd, current)
    try:
        merged, changed = _run_helper("forward", current_fd, None, desired, runtime_python, stage)
        if current_fd is not None and _fd_image(current_fd) != current:
            raise InstallerError("Codex configuration input changed")
    finally:
        if current_fd is not None:
            os.close(current_fd)
    verify_codex_toml(_read_reference(merged), desired)
    return CodexChange(current, merged, merged.image, ManagedCodexKeys(desired), changed)


def _read_reference(reference: TargetRef) -> bytes:
    image = capture_file(reference.root, reference.relative)
    if image.state is not ImageState.PRESENT:
        raise InstallerError("Codex configuration is absent")
    fd = _open_reference(reference, image)
    assert fd is not None
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = b""
        while chunk := os.read(fd, 1024 * 1024):
            raw += chunk
            if len(raw) > _MAX_CONFIG:
                raise InstallerError("Codex configuration is invalid")
        if _fd_image(fd) != image:
            raise InstallerError("Codex configuration changed while reading")
        return raw
    finally:
        os.close(fd)


def _parse_toml(raw: bytes) -> dict[str, object]:
    try:
        text = raw.decode("utf-8")
        value = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InstallerError("Codex configuration is invalid") from exc
    if type(value) is not dict:
        raise InstallerError("Codex configuration is invalid")
    return value


def _table(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise InstallerError(f"{label} is invalid")
    return value


def verify_codex_toml(raw: bytes, desired: ManagedCodexValues) -> None:
    parsed = _parse_toml(raw)
    servers = _table(parsed.get("mcp_servers"), "Codex MCP configuration")
    server = _table(servers.get("blender"), "Codex Blender MCP configuration")
    expected_server = desired.helper_dict()["server"]
    assert isinstance(expected_server, dict)
    for key, expected in expected_server.items():
        actual = server.get(key, [] if key == "args" else None)
        if key in {"startup_timeout_sec", "tool_timeout_sec"}:
            matches = type(actual) is float and actual == expected
        else:
            matches = type(actual) is type(expected) and actual == expected
        if not matches:
            raise InstallerError("Codex managed configuration mismatch")
    if any(key in server for key in _FORBIDDEN_SERVER_KEYS):
        raise InstallerError("Codex managed configuration mismatch")
    env = _table(server.get("env"), "Codex Blender MCP environment")
    if any(env.get(key) != value for key, value in desired.env.items()):
        raise InstallerError("Codex managed configuration mismatch")
    features = _table(parsed.get("features"), "Codex features configuration")
    code_mode = _table(features.get("code_mode"), "Codex code-mode configuration")
    namespaces = code_mode.get("direct_only_tool_namespaces")
    if (
        type(namespaces) is not list
        or any(type(item) is not str for item in namespaces)
        or namespaces.count(desired.direct_only_namespace) != 1
    ):
        raise InstallerError("Codex managed configuration mismatch")


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def verify_codex_effective(
    codex_bin: Path,
    desired: ManagedCodexValues,
    env: Mapping[str, str],
) -> EffectiveCodexState:
    codex_bin = _absolute(codex_bin, "Codex executable")
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [str(codex_bin), "mcp", "get", "blender", "--json"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=dict(env),
        )
        assert process.stdout is not None and process.stderr is not None
        output = bytearray()
        stderr_size = 0
        deadline = time.monotonic() + _EFFECTIVE_TIMEOUT
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise InstallerError("effective Codex verification failed")
                events = selector.select(remaining)
                if not events:
                    raise InstallerError("effective Codex verification failed")
                for key, _ in events:
                    size = len(output) if key.data == "stdout" else stderr_size
                    limit = _MAX_CONFIG if key.data == "stdout" else _MAX_STDERR
                    chunk = os.read(key.fd, min(64 * 1024, limit - size + 1))
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif key.data == "stdout":
                        output.extend(chunk)
                        if len(output) > _MAX_CONFIG:
                            raise InstallerError("effective Codex verification failed")
                    else:
                        stderr_size += len(chunk)
                        if stderr_size > _MAX_STDERR:
                            raise InstallerError("effective Codex verification failed")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise InstallerError("effective Codex verification failed")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            raise InstallerError("effective Codex verification failed") from exc
    except OSError as exc:
        raise InstallerError("effective Codex verification failed") from exc
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
    if returncode != 0:
        raise InstallerError("effective Codex verification failed")
    try:
        value = json.loads(
            output.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InstallerError("effective Codex verification failed") from exc
    if type(value) is not dict:
        raise InstallerError("effective Codex verification failed")
    legacy_keys = {"command", "args", "env"}
    if "transport" in value:
        transport = value["transport"]
        transport_expected = {
            "type": "stdio",
            "command": desired.command,
            "args": list(desired.args),
            "env_vars": [],
            "cwd": None,
        }
        if (
            any(key in value for key in legacy_keys)
            or type(transport) is not dict
            or set(transport) != set(transport_expected) | {"env"}
            or any(
                type(transport.get(key)) is not type(wanted) or transport.get(key) != wanted
                for key, wanted in transport_expected.items()
            )
        ):
            raise InstallerError("effective Codex configuration mismatch")
        effective = transport
    else:
        effective = value
    effective_env = effective.get("env")
    outer_expected = {
        "enabled_tools": list(desired.enabled_tools),
        "startup_timeout_sec": desired.startup_timeout_sec,
        "tool_timeout_sec": desired.tool_timeout_sec,
    }
    effective_expected = {
        "command": desired.command,
        "args": list(desired.args),
    }
    if (
        any(
            type(value.get(key)) is not type(wanted) or value.get(key) != wanted
            for key, wanted in outer_expected.items()
        )
        or any(
            type(effective.get(key)) is not type(wanted) or effective.get(key) != wanted
            for key, wanted in effective_expected.items()
        )
        or type(effective_env) is not dict
        or any(effective_env.get(key) != wanted for key, wanted in desired.env.items())
        or any(type(key) is not str or type(item) is not str for key, item in effective_env.items())
    ):
        raise InstallerError("effective Codex configuration mismatch")
    return EffectiveCodexState(
        effective["command"],
        tuple(effective["args"]),
        effective_env,
        tuple(value["enabled_tools"]),
        value["startup_timeout_sec"],
        value["tool_timeout_sec"],
    )


def _capture(reference: TargetRef) -> FileImage:
    try:
        return capture_file(reference.root, reference.relative)
    except (OSError, ValueError) as exc:
        raise InstallerError("Codex rollback state conflict") from exc


def _result(
    state: RollbackState,
    context: CodexRollbackContext,
    recovery: TargetRef,
    intended: FileImage | None,
    displaced: FileImage | None,
    *,
    restored: bool,
) -> RollbackResult:
    return RollbackResult(
        state,
        _capture(context.target),
        _capture(context.rollback_stage),
        _capture(recovery),
        intended,
        displaced,
        restored,
    )


def _journal(context: CodexRollbackContext, result: RollbackResult) -> RollbackResult:
    context.journal(result)
    return result


def _native_rollback(
    context: CodexRollbackContext,
    recovery: TargetRef,
    pre: FileImage,
    installer_post: FileImage,
    fault: FaultInjector,
) -> RollbackResult:
    while True:
        state = restore_file(
            context.target,
            pre,
            installer_post,
            context.forward_stage,
            recovery,
            fault,
        )
        result = _result(
            RollbackState.RESTORED if state is RestoreState.RESTORED else RollbackState.RESTORING,
            context,
            recovery,
            None,
            None,
            restored=state is RestoreState.RESTORED,
        )
        _journal(context, result)
        if result.restored:
            return result


def _create_rollback_stage(context: CodexRollbackContext) -> StagedFile:
    created = create_deterministic_stage(
        context.rollback_stage.root,
        context.rollback_stage.relative.name,
        FileImage.absent(),
        NoOpFaultInjector(),
    )
    if not isinstance(created, StagedFile):
        raise InstallerError("Codex rollback state conflict")
    return created


def _semantic_c0(
    context: CodexRollbackContext,
    recovery: TargetRef,
    recovery_image: FileImage,
    keys: ManagedCodexKeys,
    runtime_python: Path,
    fault: FaultInjector,
) -> tuple[RollbackState, FileImage, None]:
    current_image = _capture(context.target)
    stage = _create_rollback_stage(context)
    current_fd = _open_reference(context.target, current_image)
    try:
        pre_fd = _open_reference(recovery, recovery_image)
        try:
            try:
                merged, _ = _run_helper(
                    "rollback", current_fd, pre_fd, keys.desired, runtime_python, stage
                )
                _revalidate_reference(context.target, current_image, current_fd)
                _revalidate_reference(recovery, recovery_image, pre_fd)
            except InstallerError:
                if stage.capture() == stage.image:
                    conditional_remove_file(
                        stage,
                        stage.image,
                        (
                            (context.target, current_image),
                            (recovery, recovery_image),
                        ),
                        NoOpFaultInjector(),
                    )
                raise
        finally:
            if pre_fd is not None:
                os.close(pre_fd)
    finally:
        if current_fd is not None:
            os.close(current_fd)
    result = _result(
        RollbackState.C1,
        context,
        recovery,
        merged.image,
        None,
        restored=False,
    )
    _journal(context, result)
    fault.hit("after_codex_semantic_stage_fsync")
    return RollbackState.C1, merged.image, None


def preflight_codex_rollback(
    current: CodexRollbackContext,
    protected_recovery: StagedFile,
    installer_post: FileImage,
    managed_keys: ManagedCodexKeys,
    runtime_python: Path,
) -> None:
    """Validate the exact Task 4 rollback row without changing durable state."""
    if (
        type(current) is not CodexRollbackContext
        or type(protected_recovery) is not StagedFile
        or type(installer_post) is not FileImage
        or installer_post.state is not ImageState.PRESENT
        or type(managed_keys) is not ManagedCodexKeys
    ):
        raise ValueError("invalid Codex rollback input")
    live = _capture(current.target)
    forward = _capture(current.forward_stage)
    rollback_stage = _capture(current.rollback_stage)
    recovery = _capture(protected_recovery)
    pre = protected_recovery.image
    absent = FileImage.absent()
    if forward != absent:
        raise InstallerError("Codex rollback state conflict")
    if current.state is None:
        if rollback_stage != absent or recovery != pre:
            raise InstallerError("Codex rollback state conflict")
        if live in {installer_post, pre}:
            return
        if live.state is not ImageState.PRESENT:
            raise InstallerError("Codex rollback state conflict")
        _preflight_merge(
            current.target,
            live,
            protected_recovery,
            recovery,
            managed_keys.desired,
            runtime_python,
            None,
        )
        return
    intended = current.rollback_intended
    displaced = current.rollback_displaced
    if current.state is RollbackState.C1:
        if intended is None or displaced is not None or recovery != pre:
            raise InstallerError("Codex rollback state conflict")
        if live.state is ImageState.PRESENT and rollback_stage == intended:
            _preflight_merge(
                current.target,
                live,
                protected_recovery,
                recovery,
                managed_keys.desired,
                runtime_python,
                intended,
            )
        elif live == intended and rollback_stage.state is ImageState.PRESENT:
            _preflight_merge(
                current.rollback_stage,
                rollback_stage,
                protected_recovery,
                recovery,
                managed_keys.desired,
                runtime_python,
                intended,
            )
        else:
            raise InstallerError("Codex rollback state conflict")
        return
    if current.state is RollbackState.C2:
        if (
            intended is None
            or displaced is None
            or (live, rollback_stage, recovery) != (intended, displaced, pre)
        ):
            raise InstallerError("Codex rollback state conflict")
        _preflight_merge(
            current.rollback_stage,
            displaced,
            protected_recovery,
            recovery,
            managed_keys.desired,
            runtime_python,
            intended,
        )
        return
    if current.state is RollbackState.C3:
        if (
            intended is None
            or displaced is None
            or live != intended
            or rollback_stage != absent
            or recovery not in {pre, absent}
        ):
            raise InstallerError("Codex rollback state conflict")
        return
    if current.state is RollbackState.C4:
        if (
            intended is None
            or displaced is None
            or (live, rollback_stage, recovery) != (intended, absent, absent)
        ):
            raise InstallerError("Codex rollback state conflict")
        return
    if current.state is RollbackState.RESTORING:
        if rollback_stage != absent or recovery not in {pre, installer_post, absent}:
            raise InstallerError("Codex rollback state conflict")
        return
    if current.state is RollbackState.RESTORED:
        if (live, rollback_stage, recovery) != (pre, absent, absent):
            raise InstallerError("Codex rollback state conflict")
        return
    raise InstallerError("Codex rollback state conflict")


def rollback_codex(
    current: CodexRollbackContext,
    protected_recovery: StagedFile,
    installer_post: FileImage,
    managed_keys: ManagedCodexKeys,
    runtime_python: Path,
    fault: FaultInjector,
) -> RollbackResult:
    if (
        type(current) is not CodexRollbackContext
        or type(protected_recovery) is not StagedFile
        or type(installer_post) is not FileImage
        or installer_post.state is not ImageState.PRESENT
        or type(managed_keys) is not ManagedCodexKeys
    ):
        raise ValueError("invalid Codex rollback input")
    recovery_image = _capture(protected_recovery)
    pre = protected_recovery.image
    live = _capture(current.target)
    semantic = current.state in {
        RollbackState.C1,
        RollbackState.C2,
        RollbackState.C3,
        RollbackState.C4,
    }
    allowed_recovery = (
        recovery_image == pre
        or (
            current.state in {RollbackState.RESTORING, RollbackState.RESTORED}
            and recovery_image in {installer_post, FileImage.absent()}
        )
        or (
            current.state in {RollbackState.C3, RollbackState.C4}
            and recovery_image == FileImage.absent()
        )
    )
    if not allowed_recovery:
        raise InstallerError("Codex rollback state conflict")
    if not semantic and (
        live == installer_post
        or (pre.state is ImageState.ABSENT and live == pre)
        or current.state in {RollbackState.RESTORING, RollbackState.RESTORED}
    ):
        return _native_rollback(current, protected_recovery, pre, installer_post, fault)
    state = current.state
    intended = current.rollback_intended
    displaced = current.rollback_displaced
    if state is None:
        existing_stage = _capture(current.rollback_stage)
        if existing_stage.state is ImageState.PRESENT:
            _validate_semantic_merge(
                current.target,
                live,
                protected_recovery,
                recovery_image,
                managed_keys.desired,
                runtime_python,
                current.rollback_stage,
                existing_stage,
            )
            intended = existing_stage
            result = _result(
                RollbackState.C1,
                current,
                protected_recovery,
                intended,
                None,
                restored=False,
            )
            _journal(current, result)
            fault.hit("after_codex_semantic_stage_fsync")
            state = RollbackState.C1
        else:
            state, intended, displaced = _semantic_c0(
                current,
                protected_recovery,
                recovery_image,
                managed_keys,
                runtime_python,
                fault,
            )
    assert intended is not None
    while True:
        live = _capture(current.target)
        stage = _capture(current.rollback_stage)
        recovery_image = _capture(protected_recovery)
        if state is RollbackState.C1:
            if stage == intended and recovery_image == pre:
                if live.state is not ImageState.PRESENT:
                    raise InstallerError("Codex rollback state conflict")
                _validate_semantic_merge(
                    current.target,
                    live,
                    protected_recovery,
                    recovery_image,
                    managed_keys.desired,
                    runtime_python,
                    current.rollback_stage,
                    intended,
                )
                try:
                    conditional_swap_file(
                        current.target,
                        live,
                        current.rollback_stage,
                        intended,
                        ((protected_recovery, pre),),
                        fault,
                    )
                except InstallerError as exc:
                    raise InstallerError("Codex rollback state conflict") from exc
                fault.hit("after_codex_semantic_swap")
                displaced = live
            elif live == intended and stage.state is ImageState.PRESENT and recovery_image == pre:
                _validate_semantic_merge(
                    current.rollback_stage,
                    stage,
                    protected_recovery,
                    recovery_image,
                    managed_keys.desired,
                    runtime_python,
                    current.rollback_stage,
                    intended,
                )
                displaced = stage
            else:
                raise InstallerError("Codex rollback state conflict")
            result = _result(
                RollbackState.C2,
                current,
                protected_recovery,
                intended,
                displaced,
                restored=False,
            )
            _journal(current, result)
            fault.hit("after_codex_semantic_receipt")
            state = RollbackState.C2
            continue
        if state is RollbackState.C2:
            if displaced is not None and (live, stage, recovery_image) == (
                intended,
                FileImage.absent(),
                pre,
            ):
                result = _result(
                    RollbackState.C3,
                    current,
                    protected_recovery,
                    intended,
                    displaced,
                    restored=False,
                )
                _journal(current, result)
                fault.hit("after_codex_semantic_displaced_cleanup")
                state = RollbackState.C3
                continue
            if displaced is None or (live, stage, recovery_image) != (intended, displaced, pre):
                raise InstallerError("Codex rollback state conflict")
            _validate_semantic_merge(
                current.rollback_stage,
                stage,
                protected_recovery,
                recovery_image,
                managed_keys.desired,
                runtime_python,
                current.rollback_stage,
                intended,
            )
            try:
                conditional_remove_file(
                    current.rollback_stage,
                    displaced,
                    (
                        (current.target, intended),
                        (protected_recovery, pre),
                    ),
                    NoOpFaultInjector(),
                )
            except InstallerError as exc:
                raise InstallerError("Codex rollback state conflict") from exc
            result = _result(
                RollbackState.C3,
                current,
                protected_recovery,
                intended,
                displaced,
                restored=False,
            )
            _journal(current, result)
            fault.hit("after_codex_semantic_displaced_cleanup")
            state = RollbackState.C3
            continue
        if state is RollbackState.C3:
            if (live, stage, recovery_image) == (
                intended,
                FileImage.absent(),
                FileImage.absent(),
            ):
                result = _result(
                    RollbackState.C4,
                    current,
                    protected_recovery,
                    intended,
                    displaced,
                    restored=True,
                )
                _journal(current, result)
                fault.hit("after_codex_semantic_recovery_cleanup")
                return result
            if (live, stage, recovery_image) != (intended, FileImage.absent(), pre):
                raise InstallerError("Codex rollback state conflict")
            if recovery_image.state is ImageState.PRESENT:
                try:
                    conditional_remove_file(
                        protected_recovery,
                        recovery_image,
                        (
                            (current.target, intended),
                            (current.rollback_stage, FileImage.absent()),
                        ),
                        NoOpFaultInjector(),
                    )
                except InstallerError as exc:
                    raise InstallerError("Codex rollback state conflict") from exc
            result = _result(
                RollbackState.C4,
                current,
                protected_recovery,
                intended,
                displaced,
                restored=True,
            )
            _journal(current, result)
            fault.hit("after_codex_semantic_recovery_cleanup")
            return result
        if state is RollbackState.C4:
            if (live, stage, recovery_image) != (
                intended,
                FileImage.absent(),
                FileImage.absent(),
            ):
                raise InstallerError("Codex rollback state conflict")
            return _result(
                RollbackState.C4,
                current,
                protected_recovery,
                intended,
                displaced,
                restored=True,
            )
        raise InstallerError("Codex rollback state conflict")
