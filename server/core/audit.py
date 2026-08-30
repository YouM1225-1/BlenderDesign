"""JSONL 审计。spec §5.2：参数只记摘要。

小参数保持 canonical JSON SHA-256；超过 64 KiB、过深或不可编码的参数只记
固定 sentinel 摘要。日志字段有界且 fail-closed，避免审计本身成为资源逃逸点。
Phase 0 日志 schema 仍以固定空值保留 transaction_id/paths 兼容键。
"""
from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import math
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any, cast

AUDIT_LOCK_TIMEOUT = 1.0
PRIVATE_INIT_TIMEOUT = 0.1
MAX_AUDIT_PARAMS_BYTES = 64 * 1024
MAX_AUDIT_PARAMS_DEPTH = 64
MAX_AUDIT_PARAMS_ITEMS = 16 * 1024
MAX_AUDIT_FIELD_BYTES = 4096
MAX_AUDIT_REQUEST_ID_BITS = 4096
MAX_AUDIT_LINE_BYTES = 128 * 1024
_PARAMS_TRUNCATED_SENTINEL = b"\x00audit-params-truncated-v1\x00"
_PARAMS_UNENCODABLE_SENTINEL = b"\x00audit-params-unencodable-v1\x00"
PARAMS_TRUNCATED_DIGEST = hashlib.sha256(
    _PARAMS_TRUNCATED_SENTINEL).hexdigest()[:16]
PARAMS_UNENCODABLE_DIGEST = hashlib.sha256(
    _PARAMS_UNENCODABLE_SENTINEL).hexdigest()[:16]
_AUDIT_TEXT_CHUNK_CHARS = 1024


class _ParamsTruncated(Exception):
    pass


class _ParamsUnencodable(Exception):
    pass


def _private_directory_status(
        name: str | Path, path: Path, parent_fd: int | None,
        expected: tuple[int, int] | None = None) -> os.stat_result:
    try:
        current = (path.lstat() if parent_fd is None else
                   os.stat(name, dir_fd=parent_fd, follow_symlinks=False))
    except OSError as exc:
        raise PermissionError(f"private directory required: {path}") from exc
    mode = stat.S_IMODE(current.st_mode)
    if (not stat.S_ISDIR(current.st_mode) or current.st_uid != os.geteuid()
            or mode & ~0o700
            or (expected is not None
                and (current.st_dev, current.st_ino) != expected)):
        raise PermissionError(f"private directory required: {path}")
    return current


def _wait_private_directory_path(
        name: str | Path, path: Path, parent_fd: int | None,
        expected: tuple[int, int]) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    while True:
        current = _private_directory_status(name, path, parent_fd, expected)
        mode = stat.S_IMODE(current.st_mode)
        if mode == 0o700:
            return current
        if mode != 0:
            raise PermissionError(f"private directory required: {path}")
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)


def _initialize_private_directory(
        path: Path, parent_fd: int | None = None) -> os.stat_result:
    name: str | Path = path if parent_fd is None else path.name
    created = False
    try:
        if parent_fd is None:
            path.mkdir(mode=0o000, parents=False)
        else:
            os.mkdir(path.name, mode=0o000, dir_fd=parent_fd)
    except FileExistsError:
        before = _private_directory_status(name, path, parent_fd)
    except OSError as exc:
        raise PermissionError(f"private directory required: {path}") from exc
    else:
        created = True
        # POSIX mkdir returns no fd. A same-UID attacker replacing this node with
        # another exact mode-000 directory before the first capture remains a
        # creation -> first-capture threat boundary; 0500/0700 replacements fail.
        before = _private_directory_status(name, path, parent_fd)
        if stat.S_IMODE(before.st_mode) != 0:
            raise PermissionError(f"private directory required: {path}")
    expected = before.st_dev, before.st_ino
    if created:
        confirmed = _private_directory_status(name, path, parent_fd, expected)
        if stat.S_IMODE(confirmed.st_mode) != 0:
            raise PermissionError(f"private directory required: {path}")
        # macOS cannot open a mode-000 directory for fd-bound chmod. A replacement
        # landing in this finite final identity-check -> chmod pathname boundary may
        # receive the bootstrap mode; subsequent status/open checks still reject it.
        try:
            os.chmod(name, 0o700, dir_fd=parent_fd, follow_symlinks=False)
        except OSError as exc:
            raise PermissionError(f"private directory required: {path}") from exc
        before = _private_directory_status(name, path, parent_fd, expected)
        if stat.S_IMODE(before.st_mode) != 0o700:
            raise PermissionError(f"private directory required: {path}")
    else:
        before = _wait_private_directory_path(name, path, parent_fd, expected)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise PermissionError(f"private directory required: {path}") from exc
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.geteuid()
                or stat.S_IMODE(opened.st_mode) != 0o700
                or (opened.st_dev, opened.st_ino) != expected):
            raise PermissionError(f"private directory required: {path}")
        return opened
    finally:
        os.close(fd)


def _open_private_directory(
        name: str | Path, path: Path, expected: tuple[int, int],
        deadline: float | None, parent_fd: int | None = None) -> int:
    _check_deadline(deadline)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise PermissionError(f"private directory required: {path}") from exc
    try:
        _check_deadline(deadline)
        current = os.fstat(fd)
        if (not stat.S_ISDIR(current.st_mode) or current.st_uid != os.geteuid()
                or stat.S_IMODE(current.st_mode) != 0o700
                or (current.st_dev, current.st_ino) != expected):
            raise PermissionError(f"private directory required: {path}")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _wait_private_file(name: str, dir_fd: int, path: Path,
                       request_deadline: float | None = None) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    if request_deadline is not None:
        deadline = min(deadline, request_deadline)
    expected: tuple[int, int] | None = None
    while True:
        _check_deadline(request_deadline)
        st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        identity = st.st_dev, st.st_ino
        mode = stat.S_IMODE(st.st_mode)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o600 or (expected is not None and identity != expected)):
            raise PermissionError(f"private audit file required: {path}")
        if mode == 0o600:
            _check_deadline(request_deadline)
            return st
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private audit file required: {path}")
        time.sleep(0.005)


def _acquire_file_lock(fd: int, request_deadline: float | None = None) -> None:
    deadline = time.monotonic() + AUDIT_LOCK_TIMEOUT
    if request_deadline is not None:
        deadline = min(deadline, request_deadline)
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError("audit log lock timeout")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("audit log lock timeout") from exc
            time.sleep(min(0.01, remaining))


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("audit deadline expired")


def _require_text(name: str, value: object, deadline: float | None) -> None:
    _check_deadline(deadline)
    if type(value) is not str or len(value) > MAX_AUDIT_FIELD_BYTES:
        raise ValueError(f"invalid or oversized audit {name}")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"invalid or oversized audit {name}") from exc
    _check_deadline(deadline)
    if len(encoded) > MAX_AUDIT_FIELD_BYTES:
        raise ValueError(f"invalid or oversized audit {name}")


def _check_params_shape(value: object, deadline: float | None) -> None:
    """Bound traversal before JSONEncoder sorts keys or walks a deep graph."""
    active: set[int] = set()
    items = 0
    encoded_bytes = 0

    def count_text(value: str) -> None:
        nonlocal encoded_bytes
        _check_deadline(deadline)
        if len(value) > MAX_AUDIT_PARAMS_BYTES - encoded_bytes:
            raise _ParamsTruncated
        for start in range(0, len(value), _AUDIT_TEXT_CHUNK_CHARS):
            _check_deadline(deadline)
            try:
                chunk = value[start:start + _AUDIT_TEXT_CHUNK_CHARS].encode("utf-8")
            except UnicodeEncodeError as exc:
                raise _ParamsUnencodable from exc
            if len(chunk) > MAX_AUDIT_PARAMS_BYTES - encoded_bytes:
                raise _ParamsTruncated
            encoded_bytes += len(chunk)
            _check_deadline(deadline)

    def visit(current: object, depth: int) -> None:
        nonlocal items
        _check_deadline(deadline)
        if depth > MAX_AUDIT_PARAMS_DEPTH:
            raise _ParamsUnencodable
        if type(current) is dict:
            mapping = cast(dict[object, object], current)
            if id(mapping) in active:
                raise _ParamsUnencodable
            items += len(mapping)
            if items > MAX_AUDIT_PARAMS_ITEMS:
                raise _ParamsTruncated
            active.add(id(mapping))
            try:
                for key, child in mapping.items():
                    if type(key) is not str:
                        raise _ParamsUnencodable
                    count_text(key)
                    visit(child, depth + 1)
            finally:
                active.discard(id(mapping))
        elif type(current) in (list, tuple):
            sequence = cast(list[object] | tuple[object, ...], current)
            if id(sequence) in active:
                raise _ParamsUnencodable
            items += len(sequence)
            if items > MAX_AUDIT_PARAMS_ITEMS:
                raise _ParamsTruncated
            active.add(id(sequence))
            try:
                for child in sequence:
                    visit(child, depth + 1)
            finally:
                active.discard(id(sequence))
        elif type(current) is str:
            count_text(current)
        elif type(current) is int:
            if current.bit_length() > MAX_AUDIT_PARAMS_BYTES * 3:
                raise _ParamsTruncated
        elif current is not None and type(current) not in (bool, float):
            raise _ParamsUnencodable

    visit(value, 0)


def _params_digest(params: dict[str, Any] | None,
                   deadline: float | None) -> str:
    """Hash canonical JSON incrementally; oversized/invalid values use fixed sentinels."""
    value = {} if params is None else params
    try:
        _check_params_shape(value, deadline)
        digest = hashlib.sha256()
        encoded_bytes = 0
        encoder = json.JSONEncoder(
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        for piece in encoder.iterencode(value):
            _check_deadline(deadline)
            if len(piece) > MAX_AUDIT_PARAMS_BYTES - encoded_bytes:
                raise _ParamsTruncated
            encoded = piece.encode("utf-8")
            if encoded_bytes + len(encoded) > MAX_AUDIT_PARAMS_BYTES:
                raise _ParamsTruncated
            digest.update(encoded)
            encoded_bytes += len(encoded)
            _check_deadline(deadline)
    except _ParamsTruncated:
        return PARAMS_TRUNCATED_DIGEST
    except (_ParamsUnencodable, OverflowError, RecursionError, RuntimeError,
            TypeError, UnicodeEncodeError, ValueError):
        return PARAMS_UNENCODABLE_DIGEST
    return digest.hexdigest()[:16]


class AuditLog:
    def __init__(self, logs_dir: Path) -> None:
        self._dir = logs_dir
        self._root = logs_dir.parent
        self._write_lock = threading.Lock()
        root = _initialize_private_directory(self._root)
        self._root_identity = root.st_dev, root.st_ino
        root_fd = _open_private_directory(
            self._root, self._root, self._root_identity, None)
        try:
            logs = _initialize_private_directory(logs_dir, root_fd)
        finally:
            os.close(root_fd)
        self._dir_identity = logs.st_dev, logs.st_ino

    def record(self, tool: str, request_id: str | int, ok: bool, duration_ms: float,
               instance_id: str | None = None, params: dict[str, Any] | None = None,
               error: str | None = None, deadline: float | None = None) -> None:
        _check_deadline(deadline)
        _require_text("tool", tool, deadline)
        if type(request_id) is str:
            _require_text("request_id", request_id, deadline)
        elif type(request_id) is not int \
                or request_id.bit_length() > MAX_AUDIT_REQUEST_ID_BITS:
            raise ValueError("invalid or oversized audit request_id")
        if instance_id is not None:
            _require_text("instance_id", instance_id, deadline)
        if error is not None:
            _require_text("error", error, deadline)
        if type(ok) is not bool:
            raise ValueError("invalid audit scalar field")
        if (type(duration_ms) not in (int, float)
                or not math.isfinite(duration_ms)):
            raise ValueError("invalid audit duration_ms")
        rounded_duration = round(duration_ms, 3)
        _check_deadline(deadline)
        now = datetime.datetime.now(datetime.UTC)
        digest = _params_digest(params, deadline)
        _check_deadline(deadline)
        row: dict[str, Any] = {
            "ts": now.isoformat(timespec="milliseconds"), "request_id": request_id,
            "tool": tool, "instance_id": instance_id, "transaction_id": None,
            "params_digest": digest, "ok": ok, "duration_ms": rounded_duration,
            "paths": [], "error": error,
        }
        path = self._dir / f"server-{now:%Y-%m-%d}.jsonl"
        line = json.dumps(row, ensure_ascii=False) + "\n"
        _check_deadline(deadline)
        try:
            line_bytes = len(line.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ValueError("invalid audit row encoding") from exc
        if line_bytes > MAX_AUDIT_LINE_BYTES:
            raise ValueError("audit row exceeds size limit")
        _check_deadline(deadline)
        # Middleware calls may run concurrently. O_APPEND protects each kernel write's
        # offset, but TextIOWrapper is not an API-level guarantee that one logical JSONL
        # record becomes exactly one write(2); serialize records within this logger.
        lock_timeout = AUDIT_LOCK_TIMEOUT
        if deadline is not None:
            lock_timeout = min(lock_timeout, max(0.0, deadline - time.monotonic()))
        if not self._write_lock.acquire(timeout=lock_timeout):
            raise TimeoutError("audit thread lock timeout")
        try:
            root_fd: int | None = None
            logs_fd: int | None = None
            fd: int | None = None
            try:
                root_fd = _open_private_directory(
                    self._root, self._root, self._root_identity, deadline)
                logs_fd = _open_private_directory(
                    self._dir.name, self._dir, self._dir_identity, deadline, root_fd)
                _check_deadline(deadline)
                flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
                created = True
                expected: tuple[int, int] | None = None
                try:
                    _check_deadline(deadline)
                    fd = os.open(path.name, flags | os.O_CREAT | os.O_EXCL, 0o600,
                                 dir_fd=logs_fd)
                    _check_deadline(deadline)
                except FileExistsError:
                    created = False
                    existing = _wait_private_file(path.name, logs_fd, path, deadline)
                    expected = existing.st_dev, existing.st_ino
                    _check_deadline(deadline)
                    fd = os.open(path.name, flags, dir_fd=logs_fd)
                    _check_deadline(deadline)
                # More than one Codex/MCP host process may share the runtime root.
                # Bounded advisory flock keeps records intact without letting an
                # external lock holder hang the MCP middleware forever.
                if created:
                    st = os.fstat(fd)
                    expected = st.st_dev, st.st_ino
                    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                            or stat.S_IMODE(st.st_mode) & ~0o600):
                        raise PermissionError(f"private audit file required: {path}")
                    _check_deadline(deadline)
                    os.fchmod(fd, 0o600)
                    _check_deadline(deadline)
                    st = os.fstat(fd)
                    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                            or stat.S_IMODE(st.st_mode) != 0o600
                            or (st.st_dev, st.st_ino) != expected):
                        raise PermissionError(f"private audit file required: {path}")
                _acquire_file_lock(fd, deadline)
                _check_deadline(deadline)
                st = os.fstat(fd)
                if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                        or stat.S_IMODE(st.st_mode) != 0o600
                        or (expected is not None
                            and (st.st_dev, st.st_ino) != expected)):
                    raise PermissionError(f"private audit file required: {path}")
                owned_fd = fd
                fd = None  # fdopen owns the descriptor from this point onward
                stream = os.fdopen(owned_fd, "a", encoding="utf-8")
                with stream as f:
                    _check_deadline(deadline)
                    f.write(line)
                # Regular-file I/O cannot be preempted once inside the kernel, but a
                # slow write/flush/close must not be reported as an in-budget audit.
                _check_deadline(deadline)
            finally:
                if fd is not None:
                    os.close(fd)
                if logs_fd is not None:
                    os.close(logs_fd)
                if root_fd is not None:
                    os.close(root_fd)
        finally:
            self._write_lock.release()
