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


def path_is_within(path: Path, root: Path) -> bool:
    """Compare physical ownership; callers separately validate no-link access.

    Missing suffixes retain their exact spelling, so prospective roots work
    without guessing filesystem case or Unicode rules. Paths must be absolute.
    """
    def identity(value: Path) -> tuple[int, int, tuple[str, ...]]:
        suffix: tuple[str, ...] = ()
        while True:
            try:
                info = value.stat()
                return info.st_dev, info.st_ino, suffix
            except FileNotFoundError:
                if value.parent == value:
                    raise
                suffix = (value.name, *suffix)
                value = value.parent

    owner = identity(root)
    return any(identity(ancestor) == owner for ancestor in (path, *path.parents))


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
    if path_is_within(candidate, repo_root):
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
    def signal_group(sig: int) -> bool:
        deadline = time.monotonic() + 5.0
        while True:
            try:
                os.killpg(process.pid, sig)
                return True
            except ProcessLookupError:
                return False
            except PermissionError:
                # macOS can report EPERM for an unreaped, exiting group.
                # Reap our child, then require a successful signal or ESRCH;
                # persistent permission faults must still fail cleanup.
                if process.poll() is None or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)

    process.poll()
    if signal_group(signal.SIGTERM):
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass
    signal_group(signal.SIGKILL)
    process.wait(timeout=5.0)
    deadline = time.monotonic() + 5.0
    while signal_group(0):
        if time.monotonic() >= deadline:
            raise RuntimeError(f"process group {process.pid} survived cleanup")
        time.sleep(0.02)


def run_command(
    stage: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout: float,
    max_log_bytes: int = 2 * 1024 * 1024,
    limits: dict[str, int] | None = None,
    observation: dict[str, object] | None = None,
) -> int:
    import datetime
    import resource

    from acceptance.input_bundle import safe_open

    if timeout <= 0 or max_log_bytes <= 0:
        raise AcceptanceFailure("contract_invalid", "positive process budgets required")

    def constrain() -> None:
        def install(limit_id: int, requested: int) -> None:
            hard = resource.getrlimit(limit_id)[1]
            value = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
            resource.setrlimit(limit_id, (value, value))

        file_limit = max_log_bytes if limits is None else limits["file_size_bytes"]
        install(resource.RLIMIT_FSIZE, file_limit)
        if limits is not None:
            install(resource.RLIMIT_CPU, limits["cpu_seconds"])
            install(resource.RLIMIT_NOFILE, limits["open_files"])

    descriptor = safe_open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=descriptor,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            umask=0o077,
            preexec_fn=constrain,
        )
    finally:
        os.close(descriptor)
    if observation is not None:
        observation.update(
            started=True,
            pid=process.pid,
            started_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )

    def sample_rss() -> int:
        try:
            report = subprocess.run(
                ["/bin/ps", "-axo", "pid=,pgid=,rss="],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=True,
            )
            if len(report.stdout) > 2 * 1024 * 1024:
                raise AcceptanceFailure(
                    "runner_internal_error", "RSS process inventory exceeded budget"
                )
            total = 0
            for line in report.stdout.splitlines():
                _pid, group, rss = map(int, line.split())
                if group == process.pid:
                    total += rss * 1024
            return total
        except AcceptanceFailure:
            raise
        except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as exc:
            raise AcceptanceFailure(
                "runner_internal_error", f"RSS process inventory failed: {exc}"
            ) from exc

    deadline = time.monotonic() + timeout
    next_sample = 0.0
    peak, samples = 0, 0
    failure: AcceptanceFailure | None = None
    try:
        while process.poll() is None:
            if limits is not None and time.monotonic() >= next_sample:
                rss = sample_rss()
                samples += 1
                peak = max(peak, rss)
                next_sample = time.monotonic() + 0.1
                if rss > limits["rss_bytes"]:
                    raise AcceptanceFailure(
                        "resource_limit_exceeded",
                        f"{stage}: sampled group RSS exceeded budget",
                    )
            if log_path.stat().st_size >= max_log_bytes:
                raise AcceptanceFailure("evidence_truncated", f"{stage}: log budget reached")
            if time.monotonic() >= deadline:
                raise AcceptanceFailure("tool_crashed", f"{stage}: wall timeout")
            time.sleep(0.02)
        if log_path.stat().st_size >= max_log_bytes:
            raise AcceptanceFailure("evidence_truncated", f"{stage}: log budget reached")
        if group_exists(process.pid):
            raise AcceptanceFailure("tool_crashed", f"{stage}: process group leak")
        return process.returncode
    except AcceptanceFailure as exc:
        failure = exc
        raise
    finally:
        try:
            stop_group(process)
        except Exception as exc:
            detail = f"{stage}: process group cleanup failed: {exc}"
            code = "runner_internal_error"
            if failure is not None:
                code = failure.code
                detail = f"{failure}; {detail}"
            raise AcceptanceFailure(code, detail) from exc
        finally:
            if observation is not None:
                observation["exit_code"] = process.returncode
                observation["memory_sampling"] = {
                    "interval_seconds": 0.1,
                    "samples": samples,
                    "peak_observed_rss_bytes": peak,
                }


def require_zero(stage: str, returncode: int) -> None:
    if returncode != 0:
        raise AcceptanceFailure(
            f"{stage}_exit_nonzero", f"{stage} exited with status {returncode}")
