# server/core/discovery.py
"""实例发现。spec §4.3。

deadline 语义（2026-08-07 三轮审计 F-03 / R-03 / F-01 累积修订）——**有界，不是绝对**：
- deadline 在 `_scan()` 入口创建，覆盖枚举、stat、读取、解析、排序与 probe 全过程；
- 目录枚举用惰性 `os.scandir()` 并在预算/条数耗尽时**立即 break**——`sorted(iterdir())`
  会在循环体的 deadline 检查生效前把整个目录读完（实测 400 项 × 10 ms = 4.8 s）；
- `session.json` 以 `O_NOFOLLOW|O_NONBLOCK` 打开，并在**同一个 fd** 上 `fstat`、限长读取；
  FIFO/device/symlink、换入竞态、读取中扩容均被拒绝；每次 `next/open/fstat/read` 前重查预算；
- 常规文件 I/O 进入内核后仍不可由 monotonic clock 强制取消，因此保证限定为本机常规文件与
  有界系统调用序列，不宣称对失效网络文件系统或内核卡死提供绝对墙钟上界。
- probe worker 共享原 absolute deadline；真实 BridgeClient 等合作式 worker 在发布前静止，
  但任意不合作 Python 代码不可移植地抢占，明确不在该保证内。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import stat as stat_mod
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from protocol import envelope
from .bridge_client import BridgeClient, BridgeError
from .versions import check

_diag = logging.getLogger("bcx.server")
GRACE_SECONDS = 60.0
SCAN_DEADLINE = 2.5          # 全扫描默认预算，从 _scan() 入口起算
MAX_SCAN_ENTRIES = 256       # 单窗口枚举上限；cursor + backlog 跨调用公平推进
MAX_CANDIDATES = 16          # probe 上限：按 mtime 取**最新**（F-08：字典序会饿死活实例）
MAX_SESSION_BYTES = 64 * 1024
PROBE_TIMEOUT = 2.0
DirIdentity = tuple[int, int]
Entry = tuple[float, Path, DirIdentity]
INSTANCE_ID = re.compile(r"^gui-([1-9][0-9]*)-([0-9a-f]{8})$")
_DIR_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
_PRIVATE_INIT_LOCK = threading.Lock()


def _private_dir_identity(st: os.stat_result, path: Path,
                          expected: DirIdentity | None = None) -> DirIdentity:
    identity = st.st_dev, st.st_ino
    if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat_mod.S_IMODE(st.st_mode) != 0o700
            or (expected is not None and identity != expected)):
        raise PermissionError(f"private directory required: {path}")
    return identity


def _ensure_private_dir(path: Path) -> DirIdentity:
    with _PRIVATE_INIT_LOCK:
        created = False
        previous_umask = os.umask(0o077)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            created = True
        finally:
            os.umask(previous_umask)
        st = path.lstat()
        identity = _private_dir_identity(st, path)
        if not created:
            return identity
        fd = os.open(path, _DIR_FLAGS)
        try:
            _private_dir_identity(os.fstat(fd), path, identity)
            os.fchmod(fd, 0o700)
            _private_dir_identity(path.lstat(), path, identity)
            return identity
        finally:
            os.close(fd)


def _open_private_dir_at(name: str, parent_fd: int, path: Path) -> tuple[int, DirIdentity]:
    with _PRIVATE_INIT_LOCK:
        created = False
        previous_umask = os.umask(0o077)
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        else:
            created = True
        finally:
            os.umask(previous_umask)
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity = _private_dir_identity(st, path)
        fd = os.open(name, _DIR_FLAGS, dir_fd=parent_fd)
        try:
            _private_dir_identity(os.fstat(fd), path, identity)
            if created:
                os.fchmod(fd, 0o700)
            current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            _private_dir_identity(current, path, identity)
            return fd, identity
        except BaseException:
            os.close(fd)
            raise


@dataclass
class Instance:
    session: dict[str, Any]
    state: Literal["connected", "disconnected", "busy"]
    blender_supported: bool
    version_warning: str | None
    client: BridgeClient | None
    envelope_mismatch: bool = False


@dataclass
class ScanStats:
    """顶层 partial 元数据（F-06 P2：不再伪装成一个 id 为 __partial__ 的假实例）。"""
    partial: bool = False
    skipped_count: int = 0
    reasons: list[str] = field(default_factory=list)


def _mark_cleanup_incomplete(stats: ScanStats | None) -> None:
    if stats is None:
        return
    stats.partial = True
    stats.skipped_count += 1
    if "cleanup incomplete" not in stats.reasons:
        stats.reasons.append("cleanup incomplete")


def _mark_socket_identity_invalid(stats: ScanStats | None) -> None:
    if stats is None:
        return
    stats.partial = True
    stats.skipped_count += 1
    if "socket identity invalid" not in stats.reasons:
        stats.reasons.append("socket identity invalid")


def _mark_session_identity_replaced(stats: ScanStats | None) -> None:
    if stats is None:
        return
    stats.partial = True
    stats.skipped_count += 1
    if "session identity replaced" not in stats.reasons:
        stats.reasons.append("session identity replaced")


class _ProbeDeadline(Exception):
    pass


class _SocketIdentityInvalid(ValueError):
    pass


class Discovery:
    def __init__(self, run_dir: Path, ttl: float = 1.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._run = Path(run_dir)
        self._run_parent_identity = _ensure_private_dir(self._run.parent)
        parent_fd = os.open(self._run.parent, _DIR_FLAGS)
        run_fd: int | None = None
        try:
            _private_dir_identity(os.fstat(parent_fd), self._run.parent,
                                  self._run_parent_identity)
            run_fd, self._run_identity = _open_private_dir_at(
                self._run.name, parent_fd, self._run)
        finally:
            if run_fd is not None:
                os.close(run_fd)
            os.close(parent_fd)
        self._ttl = ttl
        self._clock = clock
        self._cache: list[Instance] | None = None
        self._cached_at = -1e9
        self._lock = threading.Lock()
        # A one-slot Queue coalesces repeated failures into one thread-safe,
        # non-blocking signal.  A scan consumes it only while holding the
        # discovery lock; invalidate() never waits for that lock, and a signal
        # arriving during a scan prevents that scan from publishing a cache.
        self._invalidations: queue.Queue[None] = queue.Queue(maxsize=1)
        self._scan_iter: Any = None
        self._scan_fd: int | None = None
        self._scan_identity: DirIdentity | None = None
        self._pending_entry: Any = None
        self._candidate_backlog: list[Entry] = []
        self._corrupt_first_seen: dict[DirIdentity, float] = {}
        self.last_scan = ScanStats()

    def __del__(self) -> None:
        # A paginated scandir(fd) cursor requires the caller-owned fd to remain
        # open. Close both if a short-lived Discovery is abandoned mid-window.
        try:
            self._close_scan_cursor()
        except Exception:
            pass

    def instances(self, force: bool = False,
                  deadline: float | None = None) -> list[Instance]:
        """deadline 为绝对 monotonic 时刻；None 时用 SCAN_DEADLINE 自建（F-02）。"""
        return self.instances_with_stats(force, deadline)[0]

    def instances_with_stats(
            self, force: bool = False,
            deadline: float | None = None) -> tuple[list[Instance], ScanStats]:
        """Atomically pair instances with the ScanStats snapshot that produced them."""
        if deadline is None:
            deadline = time.monotonic() + SCAN_DEADLINE
        remaining = deadline - time.monotonic()
        acquired = remaining > 0 and self._lock.acquire(timeout=remaining)
        if not acquired:
            stats = ScanStats(True, 1, ["discovery lock deadline"])
            return [], stats
        try:
            if self._take_invalidation():
                self._cache = None
                self._cached_at = -1e9
            cached = self._cache
            cached_at = self._cached_at
            if not force and cached is not None \
                    and self._clock() - cached_at < self._ttl:
                instances = cached
            else:
                instances = self._scan(deadline)
                if self._take_invalidation():
                    self._cache = None
                    self._cached_at = -1e9
                else:
                    self._cache = instances
                    self._cached_at = self._clock()
            stats = self.last_scan
            return instances, ScanStats(stats.partial, stats.skipped_count,
                                        list(stats.reasons))
        finally:
            self._lock.release()

    def invalidate(self, deadline: float | None = None) -> bool:
        """Bridge 失联后使下一次调用重新扫描，而不是复用 1s 旧缓存。"""
        # The signal is constant-time and does not wait for filesystem/probe
        # work.  The deadline is accepted for adapter call-site symmetry; no
        # blocking operation is needed for this notification.
        del deadline
        try:
            self._invalidations.put_nowait(None)
        except queue.Full:
            pass  # an outstanding signal already represents this invalidation
        return True

    def _take_invalidation(self) -> bool:
        """Consume at most one signal so a concurrent producer cannot extend a scan."""
        try:
            self._invalidations.get_nowait()
        except queue.Empty:
            return False
        return True

    def find(self, instance_id: str,
             deadline: float | None = None) -> Instance | None:
        return self.find_with_stats(instance_id, deadline)[0]

    def find_with_stats(
            self, instance_id: str,
            deadline: float | None = None) -> tuple[Instance | None, ScanStats]:
        instances, stats = self.instances_with_stats(deadline=deadline)
        for inst in instances:
            if inst.session["instance_id"] == instance_id:
                return inst, stats
        return None, stats

    # ---------- 扫描 ----------
    def _scan(self, deadline: float | None = None) -> list[Instance]:
        if deadline is None:
            deadline = time.monotonic() + SCAN_DEADLINE
        stats = ScanStats()
        self.last_scan = stats
        out: list[Instance] = []

        if time.monotonic() >= deadline:
            stats.partial = True
            stats.skipped_count = 1
            stats.reasons.append("run deadline")
            return out
        try:
            os.close(self._open_run_dir(deadline))
        except TimeoutError:
            stats.partial = True
            stats.skipped_count = 1
            stats.reasons.append("run deadline")
            return out
        except OSError:
            stats.partial = True
            stats.skipped_count = 1
            stats.reasons.append("run boundary")
            self._close_scan_cursor()
            self._candidate_backlog = []
            return out

        if self._candidate_backlog and not self._validate_scan_cursor(deadline, stats):
            return out
        from_backlog = bool(self._candidate_backlog)
        entries = self._candidate_backlog
        self._candidate_backlog = []
        if not entries:
            entries = self._enumerate(deadline, stats)
        if not entries:
            return out
        entries.sort(key=lambda e: e[0], reverse=True)          # mtime 新 → 旧
        if len(entries) > MAX_CANDIDATES:
            stats.partial = True
            stats.skipped_count += len(entries) - MAX_CANDIDATES
            stats.reasons.append("candidate cap")
            self._candidate_backlog = entries[MAX_CANDIDATES:]
            entries = entries[:MAX_CANDIDATES]
        if from_backlog and (self._scan_iter is not None
                             or self._pending_entry is not None):
            stats.partial = True
            stats.skipped_count += 1  # 未枚举尾部的保守下界
            stats.reasons.append("enumeration window")

        candidates: list[tuple[Path, dict[str, Any], DirIdentity]] = []
        for index, (_mtime, d, identity) in enumerate(entries):
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count += len(entries) - index
                stats.reasons.append("deadline during session read")
                self._candidate_backlog = entries[index:] + self._candidate_backlog
                break
            try:
                sess = self._read_session(d, identity, deadline, stats)
            except TimeoutError:
                stats.partial = True
                stats.skipped_count += len(entries) - index
                stats.reasons.append("deadline during session read")
                self._candidate_backlog = entries[index:] + self._candidate_backlog
                break
            if sess is not None:
                candidates.append((d, sess, identity))
        if not candidates:
            return out
        return out + self._probe_all(candidates, deadline, stats)

    def _open_run_dir(self, deadline: float | None = None) -> int:
        """Open the configured run directory through its identity-bound parent."""
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError
        parent_fd = os.open(self._run.parent, _DIR_FLAGS)
        try:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError
            _private_dir_identity(os.fstat(parent_fd), self._run.parent,
                                  self._run_parent_identity)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError
            run_fd = os.open(self._run.name, _DIR_FLAGS, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
        try:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError
            _private_dir_identity(os.fstat(run_fd), self._run,
                                  self._run_identity)
            return run_fd
        except BaseException:
            os.close(run_fd)
            raise

    def _close_scan_cursor(self) -> None:
        scan_iter, self._scan_iter = self._scan_iter, None
        scan_fd, self._scan_fd = self._scan_fd, None
        scan_identity, self._scan_identity = self._scan_identity, None
        owns_fd = False
        if scan_fd is not None and scan_identity is not None:
            try:
                current = os.fstat(scan_fd)
            except OSError:
                pass
            else:
                owns_fd = (current.st_dev, current.st_ino) == scan_identity
        if scan_iter is not None:
            try:
                scan_iter.close()
            except Exception:
                pass
        if owns_fd and scan_fd is not None:
            try:
                os.close(scan_fd)
            except OSError:
                pass
        self._pending_entry = None

    def _discard_scan_cursor(self) -> None:
        """Drop an unproven/reused fd without closing a possibly unrelated fd number."""
        scan_iter, self._scan_iter = self._scan_iter, None
        if scan_iter is not None:
            try:
                scan_iter.close()
            except Exception:
                pass
        self._scan_fd = None
        self._scan_identity = None
        self._pending_entry = None

    def _validate_scan_cursor(self, deadline: float, stats: ScanStats) -> bool:
        """Rebind the persisted cursor to the current run directory identity.

        The finite fstat checks reject closed or different-identity descriptor
        reuse.  POSIX exposes no portable per-open-file-description nonce, so a
        same-identity descriptor hijack after the final check is outside this
        private-cursor guarantee.
        """
        if self._scan_iter is None:
            return True
        if self._scan_fd is None:
            self._discard_scan_cursor()
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor replaced")
            return False
        if time.monotonic() >= deadline:
            self._close_scan_cursor()
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor deadline")
            return False
        current_fd: int | None = None
        try:
            cursor_stat = os.fstat(self._scan_fd)
        except OSError:
            self._discard_scan_cursor()
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor closed")
            return False
        cursor_identity = (cursor_stat.st_dev, cursor_stat.st_ino)
        cursor_owned = (self._scan_identity == cursor_identity
                        and cursor_identity == self._run_identity)
        try:
            current_fd = self._open_run_dir(deadline)
            current_stat = os.fstat(current_fd)
        except TimeoutError:
            (self._close_scan_cursor() if cursor_owned
             else self._discard_scan_cursor())
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor deadline")
            return False
        except OSError:
            (self._close_scan_cursor() if cursor_owned
             else self._discard_scan_cursor())
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor replaced")
            return False
        finally:
            if current_fd is not None:
                try:
                    os.close(current_fd)
                except OSError:
                    pass
        current_identity = (current_stat.st_dev, current_stat.st_ino)
        if (cursor_identity != self._run_identity
                or current_identity != self._run_identity
                or (self._scan_identity is not None
                    and self._scan_identity != cursor_identity)):
            (self._close_scan_cursor() if cursor_owned
             else self._discard_scan_cursor())
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor replaced")
            return False
        self._scan_identity = cursor_identity
        return True

    def _enumerate(self, deadline: float,
                   stats: ScanStats) -> list[Entry]:
        """惰性枚举 + 预算/条数双止损。绝不先 sorted() 全量物化（F-01）。"""
        found: list[Entry] = []
        seen = 0
        if not self._validate_scan_cursor(deadline, stats):
            return found
        if self._scan_iter is None:
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count = 1
                stats.reasons.append("enumeration deadline")
                return found
            try:
                self._scan_fd = self._open_run_dir(deadline)
                try:
                    self._scan_iter = os.scandir(self._scan_fd)
                    scan_stat = os.fstat(self._scan_fd)
                    self._scan_identity = (scan_stat.st_dev, scan_stat.st_ino)
                except BaseException:
                    os.close(self._scan_fd)
                    self._scan_fd = None
                    self._scan_identity = None
                    raise
            except TimeoutError:
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration deadline")
                return found
            except OSError:
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration error")
                return found
        while seen < MAX_SCAN_ENTRIES:
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count += 1  # 下界；不为精确计数继续枚举
                stats.reasons.append("enumeration deadline")
                break
            try:
                if self._pending_entry is not None:
                    entry, self._pending_entry = self._pending_entry, None
                else:
                    entry = next(self._scan_iter)
            except StopIteration:
                self._close_scan_cursor()
                break
            except OSError:
                self._close_scan_cursor()
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration error")
                break
            seen += 1
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError
                entry_stat = entry.stat(follow_symlinks=False)
                found.append((entry_stat.st_mtime, self._run / entry.name,
                              (entry_stat.st_dev, entry_stat.st_ino)))
            except TimeoutError:
                self._pending_entry = entry
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration deadline")
                break
            except OSError:
                stats.partial = True
                stats.skipped_count += 1
                if "entry error" not in stats.reasons:
                    stats.reasons.append("entry error")
                continue

        # ``next()`` itself is part of the per-window bound.  At an exact
        # boundary we conservatively report one extra partial round instead of
        # consuming a 257th entry merely to prove exhaustion.
        if seen >= MAX_SCAN_ENTRIES and self._scan_iter is not None:
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("enumeration window")
        return found

    def _read_session(self, d: Path, expected_identity: DirIdentity,
                      deadline: float,
                      stats: ScanStats | None = None) -> dict[str, Any] | None:
        """同一目录/file fd 完成 open/fstat/有界读取，拒绝换入竞态。"""
        dir_fd: int | None = None
        dir_identity: DirIdentity | None = None
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError
            # Bind the parent directory before opening its child.  Checking only
            # O_NOFOLLOW on ``d/session.json`` still follows a parent-directory
            # symlink swapped in after enumeration.
            dir_flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
            dir_fd = os.open(d, dir_flags)
            dir_stat = os.fstat(dir_fd)
            dir_identity = (dir_stat.st_dev, dir_stat.st_ino)
            if (dir_identity != expected_identity or dir_stat.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(dir_stat.st_mode) != 0o700):
                raise ValueError("session directory is not private or changed")
            if time.monotonic() >= deadline:
                raise TimeoutError
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            fd = os.open("session.json", flags, dir_fd=dir_fd)
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                st = os.fstat(fd)
                if (not stat_mod.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                        or stat_mod.S_IMODE(st.st_mode) != 0o600):
                    raise ValueError("session.json is not a private regular file")
                if st.st_size > MAX_SESSION_BYTES:
                    raise ValueError("session.json is too large")
                chunks: list[bytes] = []
                remaining = MAX_SESSION_BYTES + 1
                while remaining:
                    if time.monotonic() >= deadline:
                        raise TimeoutError
                    chunk = os.read(fd, min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
            finally:
                os.close(fd)
                os.close(dir_fd)
                dir_fd = None
            raw = b"".join(chunks)
            if len(raw) > MAX_SESSION_BYTES:
                raise ValueError("session.json grew beyond the size limit")
            data = json.loads(raw)
            required = {
                "instance_id": str, "token": str, "pid": int,
                "socket_path": str, "blender_version": str,
                "bridge_version": str, "envelope_version": int,
            }
            if not isinstance(data, dict) or any(
                    type(data.get(key)) is not kind for key, kind in required.items()):
                raise ValueError("invalid session schema")
            if data["instance_id"] != d.name:
                raise ValueError("instance_id does not match session directory")
            match = INSTANCE_ID.fullmatch(d.name)
            if match is None or int(match.group(1)) != data["pid"]:
                raise ValueError("instance_id pid does not match session pid")
            identity_fields = ("socket_dev", "socket_ino", "socket_dir_dev",
                               "socket_dir_ino")
            if ("socket_external" in data
                    and type(data["socket_external"]) is not bool):
                raise _SocketIdentityInvalid("invalid socket_external")
            if any(key in data and type(data[key]) is not int for key in identity_fields):
                raise _SocketIdentityInvalid("invalid socket identity")
            if any(key not in data for key in identity_fields):
                raise _SocketIdentityInvalid("missing socket identity")
            socket_path = Path(data["socket_path"])
            if data.get("socket_external") is True:
                fallback = Discovery._fallback_dir(d.name)
                if fallback is None or socket_path != fallback / "bridge.sock":
                    raise _SocketIdentityInvalid("invalid external socket path")
            elif socket_path != d / "bridge.sock":
                raise _SocketIdentityInvalid("invalid internal socket path")
            self._corrupt_first_seen.pop(expected_identity, None)
            return data
        except TimeoutError:
            if dir_fd is not None:
                os.close(dir_fd)
            raise
        except _SocketIdentityInvalid:
            if dir_fd is not None:
                os.close(dir_fd)
            _mark_socket_identity_invalid(stats)
            return None
        except (OSError, ValueError, RecursionError):
            if dir_fd is not None:
                os.close(dir_fd)
            try:
                if time.monotonic() >= deadline:
                    _mark_cleanup_incomplete(stats)
                    return None
                dst = d.stat(follow_symlinks=False)
                current_identity = (dst.st_dev, dst.st_ino)
                boundary_ok = (
                    stat_mod.S_ISDIR(dst.st_mode)
                    and current_identity == expected_identity
                    and dst.st_uid == os.geteuid()
                    and stat_mod.S_IMODE(dst.st_mode) == 0o700
                )
                if not boundary_ok:
                    _mark_session_identity_replaced(stats)
                elif time.monotonic() < deadline:
                    first_seen = self._corrupt_first_seen.setdefault(
                        expected_identity, self._clock())
                    expired = self._clock() - first_seen > GRACE_SECONDS
                    if not expired:
                        return None
                    _diag.info("cleaning corrupt session dir %s", d)
                    complete = Discovery._remove_session_dir(
                        d, expected_identity, deadline)
                    if complete:
                        self._corrupt_first_seen.pop(expected_identity, None)
                    if not complete:
                        _mark_cleanup_incomplete(stats)
            except OSError:
                _mark_cleanup_incomplete(stats)
            return None

    @staticmethod
    def _remove_session_dir(d: Path, expected_identity: DirIdentity,
                            deadline: float | None = None,
                            expected_socket: DirIdentity | None = None) -> bool:
        """Bounded stale cleanup; never recursively deletes a replaced directory."""
        dir_fd: int | None = None
        try:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
            dir_fd = os.open(d, flags)
            if deadline is not None and time.monotonic() >= deadline:
                return False
            st = os.fstat(dir_fd)
            if ((st.st_dev, st.st_ino) != expected_identity
                    or st.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(st.st_mode) != 0o700):
                return False
            # A valid session directory contains only these files.  Do not recurse:
            # arbitrary trees would turn discovery cleanup into an unbounded deadline
            # escape.  Unknown children intentionally leave the directory for review.
            for name in ("session.json", "session.json.tmp", "bridge.sock"):
                if deadline is not None and time.monotonic() >= deadline:
                    return False
                try:
                    child = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                    regular = name != "bridge.sock"
                    if (child.st_uid != os.geteuid()
                            or stat_mod.S_IMODE(child.st_mode) != 0o600
                            or (regular and not stat_mod.S_ISREG(child.st_mode))
                            or (not regular and not stat_mod.S_ISSOCK(child.st_mode))
                            or (not regular and expected_socket is not None
                                and (child.st_dev, child.st_ino) != expected_socket)):
                        return False
                    if deadline is not None and time.monotonic() >= deadline:
                        return False
                    os.unlink(name, dir_fd=dir_fd)
                except FileNotFoundError:
                    pass
                except IsADirectoryError:
                    return False
        except OSError:
            return False
        finally:
            if dir_fd is not None:
                os.close(dir_fd)
        try:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            st = d.stat(follow_symlinks=False)
            if ((not stat_mod.S_ISDIR(st.st_mode))
                    or (st.st_dev, st.st_ino) != expected_identity
                    or st.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(st.st_mode) != 0o700):
                return False
            if deadline is not None and time.monotonic() >= deadline:
                return False
            d.rmdir()
            return True
        except OSError:
            return False

    @staticmethod
    def _fallback_dir(instance_id: str) -> Path | None:
        digest = hashlib.sha256(instance_id.encode()).hexdigest()[:16]
        fallback = Path("/tmp") / f"bcx-{digest}"
        return fallback if len(str(fallback / "bridge.sock").encode()) <= 100 else None

    @staticmethod
    def _socket_identity_state(sess: dict[str, Any], deadline: float) -> str:
        """Return ok/missing/mismatch without connecting to an unbound path."""
        identity_fields = ("socket_dev", "socket_ino", "socket_dir_dev",
                           "socket_dir_ino")
        if any(key not in sess for key in identity_fields):
            return "mismatch"  # defensive fail-closed; _read_session rejects this schema
        path = Path(sess["socket_path"])
        try:
            if time.monotonic() >= deadline:
                raise _ProbeDeadline
            directory = path.parent.lstat()
            if time.monotonic() >= deadline:
                raise _ProbeDeadline
            sock = path.lstat()
        except FileNotFoundError:
            return "missing"
        except OSError:
            return "mismatch"
        if (not stat_mod.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
                or stat_mod.S_IMODE(directory.st_mode) != 0o700
                or (directory.st_dev, directory.st_ino)
                != (sess["socket_dir_dev"], sess["socket_dir_ino"])
                or not stat_mod.S_ISSOCK(sock.st_mode)
                or sock.st_uid != os.geteuid()
                or stat_mod.S_IMODE(sock.st_mode) != 0o600
                or (sock.st_dev, sock.st_ino)
                != (sess["socket_dev"], sess["socket_ino"])):
            return "mismatch"
        return "ok"

    @staticmethod
    def _remove_external_socket(d: Path, sess: dict[str, Any] | None,
                                deadline: float) -> bool:
        """Remove the identity-bound deterministic sun_path fallback, if one exists."""
        if sess is None:
            return True  # no complete metadata means no authority over a global fallback
        socket_path = Path(sess["socket_path"])
        actual_external = socket_path.parent != d
        if not actual_external:
            try:
                state = Discovery._socket_identity_state(sess, deadline)
            except _ProbeDeadline:
                return False
            return state in {"ok", "missing"}
        if sess.get("socket_external") is not True:
            return False  # old/untrusted metadata: retain session evidence
        fallback = Discovery._fallback_dir(d.name)
        if fallback is None or socket_path != fallback / "bridge.sock":
            return False
        expected_dir = (sess["socket_dir_dev"], sess["socket_dir_ino"])
        expected_socket: DirIdentity = (sess["socket_dev"], sess["socket_ino"])

        dir_fd: int | None = None
        observed_dir: DirIdentity | None = None
        try:
            if time.monotonic() >= deadline:
                return False
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
            dir_fd = os.open(fallback, flags)
            if time.monotonic() >= deadline:
                return False
            st = os.fstat(dir_fd)
            observed_dir = (st.st_dev, st.st_ino)
            if (st.st_uid != os.geteuid() or stat_mod.S_IMODE(st.st_mode) != 0o700
                    or observed_dir != expected_dir):
                return False
            if time.monotonic() >= deadline:
                return False
            try:
                socket_stat = os.stat(socket_path.name, dir_fd=dir_fd,
                                      follow_symlinks=False)
            except FileNotFoundError:
                socket_stat = None
            if socket_stat is not None:
                if (not stat_mod.S_ISSOCK(socket_stat.st_mode)
                        or socket_stat.st_uid != os.geteuid()
                        or stat_mod.S_IMODE(socket_stat.st_mode) != 0o600
                        or (socket_stat.st_dev, socket_stat.st_ino)
                        != expected_socket):
                    return False
                if time.monotonic() >= deadline:
                    return False
                try:
                    os.unlink(socket_path.name, dir_fd=dir_fd)
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            return True
        except OSError:
            return False
        finally:
            if dir_fd is not None:
                os.close(dir_fd)
        try:
            if time.monotonic() >= deadline:
                return False
            current = fallback.stat(follow_symlinks=False)
            if ((not stat_mod.S_ISDIR(current.st_mode))
                    or (current.st_dev, current.st_ino) != observed_dir
                    or current.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(current.st_mode) != 0o700):
                return False
            if time.monotonic() >= deadline:
                return False
            fallback.rmdir()  # unknown children make this fail closed
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def _probe_all(self, candidates: list[tuple[Path, dict[str, Any], DirIdentity]],
                   deadline: float, stats: ScanStats) -> list[Instance]:
        out: list[Instance] = []
        if time.monotonic() >= deadline:
            stats.partial = True
            stats.skipped_count += len(candidates)
            stats.reasons.append("probe deadline")
            return [self._make(sess, "disconnected", client=None,
                               note="probe skipped: deadline")
                    for _d, sess, _identity in candidates]
        ex = ThreadPoolExecutor(max_workers=8)
        try:
            futs = {ex.submit(self._probe, sess, deadline): (d, sess, identity)
                    for d, sess, identity in candidates}
            done, not_done = wait(futs, timeout=max(0.0, deadline - time.monotonic()))
            for f in sorted(done, key=lambda x: futs[x][0].name):   # 顺序确定
                d, sess, identity = futs[f]
                try:
                    inst = f.result()
                except _ProbeDeadline:
                    stats.partial = True
                    stats.skipped_count += 1
                    if "probe deadline" not in stats.reasons:
                        stats.reasons.append("probe deadline")
                    out.append(self._make(sess, "disconnected", client=None,
                                          note="probe skipped: deadline"))
                    continue
                except Exception as exc:  # 单个损坏候选不得击穿整次发现
                    _diag.info("session probe failed for %s: %s", d, exc)
                    out.append(self._make(sess, "disconnected", client=None,
                                          note="probe failed"))
                    continue
                if inst is None:
                    _diag.info("cleaning dead session dir %s", d)
                    complete = self._remove_external_socket(d, sess, deadline)
                    if complete:
                        expected_socket = (sess["socket_dev"], sess["socket_ino"])
                        complete = self._remove_session_dir(
                            d, identity, deadline, expected_socket)
                    if not complete:
                        _mark_cleanup_incomplete(stats)
                elif inst.session.get("__stale__"):
                    stats.partial = True
                    stats.skipped_count += 1
                    if "identity mismatch" not in stats.reasons:
                        stats.reasons.append("identity mismatch")
                    continue          # 握手身份不符：不计入也不清理（§4.3）
                else:
                    out.append(inst)
            for f in sorted(not_done, key=lambda x: futs[x][0].name):
                _d, sess, _identity = futs[f]    # 预算耗尽：如实标注，绝不清理
                stats.partial = True
                stats.skipped_count += 1
                out.append(self._make(sess, "disconnected", client=None,
                                      note="probe skipped: deadline"))
            if not_done and "probe deadline" not in stats.reasons:
                stats.reasons.append("probe deadline")
        finally:
            # BridgeClient and the in-module probe path honor the shared
            # absolute deadline. Waiting makes cooperative workers quiescent
            # before publication; arbitrary non-cooperative Python code remains
            # outside this guarantee and cannot be preempted portably.
            ex.shutdown(wait=True, cancel_futures=True)
        return out

    def _probe(self, sess: dict[str, Any], deadline: float) -> Instance | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _ProbeDeadline
        pid_alive = True
        try:
            os.kill(int(sess.get("pid", -1)), 0)
        except (OSError, ValueError):
            pid_alive = False
        if time.monotonic() >= deadline:
            raise _ProbeDeadline
        socket_state = self._socket_identity_state(sess, deadline)
        if socket_state == "mismatch":
            return self._make({**sess, "__stale__": True}, "disconnected", client=None)
        if socket_state == "missing":
            if not pid_alive:
                return None
            return self._make(sess, "disconnected", client=None)
        client = BridgeClient(sess)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _ProbeDeadline
        budget = min(PROBE_TIMEOUT, remaining)
        try:
            pong = client.call("ping", timeout=budget, deadline=deadline)
        except BridgeError as exc:
            if exc.code == envelope.BRIDGE_TIMEOUT and time.monotonic() >= deadline:
                raise _ProbeDeadline
            if exc.code == envelope.ENVELOPE_VERSION_MISMATCH:
                inst = self._make(sess, "disconnected", client=None)
                inst.envelope_mismatch = True
                inst.version_warning = str(exc)
                return inst
            if exc.code == envelope.BRIDGE_BUSY:
                return self._make(sess, "busy", client=client,
                                  note="bridge busy")
            if not pid_alive:
                return None       # 双条件成立 → 清理
            return self._make(sess, "disconnected", client=None)
        if pong.get("instance_id") != sess.get("instance_id"):
            return self._make({**sess, "__stale__": True}, "disconnected", client=None)
        pong_version = pong.get("envelope_version")
        if type(pong_version) is not int \
                or pong_version != envelope.ENVELOPE_VERSION:
            inst = self._make(sess, "disconnected", client=None)
            inst.envelope_mismatch = True
            inst.version_warning = (
                f"envelope v{pong_version} != v{envelope.ENVELOPE_VERSION}，"
                f"Server 与 Bridge 版本不匹配")
            return inst
        return self._make(sess, "connected", client=client)

    @staticmethod
    def _make(sess: dict[str, Any],
              state: Literal["connected", "disconnected", "busy"],
              client: BridgeClient | None,
              note: str | None = None) -> Instance:
        supported, warning = check(str(sess.get("blender_version", "")))
        if note is not None:
            warning = f"{warning}；{note}" if warning else note
        return Instance(session=sess, state=state, blender_supported=supported,
                        version_warning=warning, client=client)
