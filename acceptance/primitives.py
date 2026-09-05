from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from acceptance.strict_json import strict_json_loads as strict_json_loads
from smoke.process_registry import read_private_bytes, require_private_directory


class AcceptanceFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def normalise_new_root(path: Path, repo_root: Path) -> Path:
    """返回一个规范化的、尚不存在的、位于 repo_root 之外的绝对路径。"""
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    parent = candidate.parent.resolve(strict=True)
    candidate = parent / candidate.name
    try:
        candidate.lstat()
    except FileNotFoundError:
        pass
    else:
        raise AcceptanceFailure(
            "reused_evidence_root", f"evidence root already exists: {candidate}")
    if candidate == repo_root or repo_root in candidate.parents:
        raise AcceptanceFailure(
            "evidence_root_inside_candidate",
            "evidence root must be outside the candidate Git worktree",
        )
    return candidate


def create_private_directory(path: Path) -> None:
    os.mkdir(path, mode=0o700)
    os.chmod(path, 0o700, follow_symlinks=False)
    require_private_directory(path)


def clean_environment(
    uv: Path,
    blocked_prefixes: tuple[str, ...] = (
        "BLENDERCODEX_", "BLENDER_", "DYLD_", "GIT_", "LD_", "PYTHON", "UV_",
    ),
) -> dict[str, str]:
    clean = {
        key: value for key, value in os.environ.items()
        if key != "VIRTUAL_ENV" and not key.startswith(blocked_prefixes)
    }
    clean.update({
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_BIN": str(uv),
    })
    return clean


def file_evidence(path: Path, max_bytes: int) -> dict[str, object]:
    try:
        raw = read_private_bytes(path, time.monotonic() + 5.0, max_bytes)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AcceptanceFailure(
            "evidence_file_invalid", f"invalid evidence file {path}: {exc}") from exc
    return {"path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write_json_exclusive(path: Path, value: object) -> None:
    require_private_directory(path.parent)
    raw = (json.dumps(
        value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(raw)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def group_exists(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    return True


def stop_group(process: subprocess.Popen[bytes]) -> None:
    if group_exists(process.pid):
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass
    if group_exists(process.pid):
        os.killpg(process.pid, signal.SIGKILL)
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass


def run_command(
    stage: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout: float,
) -> int:
    """与 Phase 0 版本逐行一致,仅把写死的 ROOT 换成 cwd 形参。"""
    descriptor = os.open(
        log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=descriptor,
            stderr=subprocess.STDOUT, start_new_session=True, umask=0o077)
    finally:
        os.close(descriptor)
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stop_group(process)
        raise AcceptanceFailure(
            f"{stage}_timeout", f"{stage} exceeded {timeout:g} seconds") from exc
    except BaseException:
        stop_group(process)
        raise
    if group_exists(process.pid):
        stop_group(process)
        raise AcceptanceFailure(
            f"{stage}_process_group_leak", f"{stage} left a live process group")
    return returncode


def require_zero(stage: str, returncode: int) -> None:
    if returncode != 0:
        raise AcceptanceFailure(
            f"{stage}_exit_nonzero", f"{stage} exited with status {returncode}")
