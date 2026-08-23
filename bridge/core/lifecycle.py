# bridge/core/lifecycle.py
"""会话生命周期与 I/O 线程。spec §2.2 权限表、§3.7 连接模型（单写者五规则）、§4.1 启动序列。"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import select
import socket
import stat as stat_mod
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from ._proto import envelope, framing
from .contracts import Clock, SceneReader
from .queue import QueueFull, TaskQueue
from .router import BridgeMeta, Router
from .session import SessionAuth, write_session_file

BRIDGE_VERSION = "0.1.0"
MAX_SUN_PATH = 100
MAX_OUTBOX = 32 * 1024 * 1024        # §3.7 规则 4：发送背压上限
MAX_TOTAL_OUTBOX = 64 * 1024 * 1024
MAX_CONNECTIONS = 64                 # unauthenticated/partial-frame memory bound
MAX_INBOUND_PENDING = 32 * 1024 * 1024
MAX_REQUEST_PAYLOAD = 64 * 1024
PRIVATE_INIT_TIMEOUT = 0.1
_diag = logging.getLogger("bcx.bridge")


class _MonotonicClock:
    def monotonic(self) -> float:
        return time.monotonic()


def _ensure_private_dir(path: Path) -> tuple[int, int]:
    """Race-safe create-or-validate for application-owned 0700 directories."""
    created = False
    try:
        path.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        pass
    else:
        created = True
    if created:
        os.chmod(path, 0o700, follow_symlinks=False)
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: tuple[int, int] | None = None
    while True:
        st = path.lstat()
        identity = st.st_dev, st.st_ino
        mode = stat_mod.S_IMODE(st.st_mode)
        if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            break
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)
    return st.st_dev, st.st_ino


def _wait_private_dir_at(name: str, parent_fd: int, path: Path) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: tuple[int, int] | None = None
    while True:
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity = st.st_dev, st.st_ino
        mode = stat_mod.S_IMODE(st.st_mode)
        if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            return st
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)


def _private_dir_identity(fd: int, path: Path,
                          expected: tuple[int, int] | None = None) -> tuple[int, int]:
    st = os.fstat(fd)
    identity = st.st_dev, st.st_ino
    if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat_mod.S_IMODE(st.st_mode) != 0o700
            or (expected is not None and identity != expected)):
        raise PermissionError(f"private directory required: {path}")
    return identity


class _Conn:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buf = framing.FrameBuffer()
        self.outbox: deque[bytes] = deque()   # 只由 I/O 线程消费（§3.7 规则 3）
        # Retained frame allocation, not unsent wire bytes: partial sends keep the
        # complete ``bytes`` object alive until popleft, so decrement only on pop.
        self.outbox_bytes = 0
        self.send_offset = 0                  # outbox[0] 的部分写偏移
        self.closing = False


class BridgeSession:
    def __init__(self, clock: Clock) -> None:  # 仅供 start() 使用；属性全部在此声明（mypy strict）
        self.stopped = False
        self.instance_id = ""
        self.token = ""
        self.session_dir = Path()
        self.socket_path = Path()
        self._socket_owned = False   # 仅当本实例成功 bind 后为真（复审 R-02）
        self._socket_identity: tuple[int, int] | None = None
        self._socket_parent_identity: tuple[int, int] | None = None
        self._session_identity: tuple[int, int] | None = None
        self._session_dir_identity: tuple[int, int] | None = None
        self._sock_tmpdir: Path | None = None
        self._clock = clock
        self._conns: dict[int, _Conn] = {}
        self._conns_lock = threading.Lock()
        self._pending_close: list[socket.socket] = []
        self._queue: TaskQueue | None = None
        self._auth: SessionAuth | None = None
        self._listener: socket.socket | None = None
        self._wake_r: socket.socket | None = None
        self._wake_w: socket.socket | None = None
        self._wake_lock = threading.Lock()
        self._wake_pending = False
        self._io: threading.Thread | None = None
        self._cleanup_lock = threading.Lock()
        self.cleanup_complete = False

    # ---------- 启动（session.json 最后发布；失败时仅回收 identity-bound 自有物） ----------
    @classmethod
    def start(cls, runtime_root: Path, reader: SceneReader, blender_version: str,
              clock: Clock | None = None) -> "BridgeSession":
        self = cls(clock or _MonotonicClock())
        root_fd: int | None = None
        run_fd: int | None = None
        session_fd: int | None = None
        try:
            runtime_root = Path(runtime_root)
            root_identity = _ensure_private_dir(runtime_root)
            dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
            root_fd = os.open(runtime_root, dir_flags)
            _private_dir_identity(root_fd, runtime_root, root_identity)
            run_created = False
            try:
                os.mkdir("run", mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                pass
            else:
                run_created = True
            if run_created:
                os.chmod("run", 0o700, dir_fd=root_fd, follow_symlinks=False)
            run_path = runtime_root / "run"
            run_stat = _wait_private_dir_at("run", root_fd, run_path)
            run_identity = run_stat.st_dev, run_stat.st_ino
            run_fd = os.open("run", dir_flags, dir_fd=root_fd)
            _private_dir_identity(run_fd, run_path, run_identity)
            self.instance_id = f"gui-{os.getpid()}-{secrets.token_hex(4)}"
            self.session_dir = run_path / self.instance_id
            os.mkdir(self.instance_id, mode=0o700, dir_fd=run_fd)  # exclusive leaf
            session_stat = os.stat(self.instance_id, dir_fd=run_fd,
                                   follow_symlinks=False)
            self._session_dir_identity = session_stat.st_dev, session_stat.st_ino
            os.chmod(self.instance_id, 0o700, dir_fd=run_fd, follow_symlinks=False)
            session_fd = os.open(self.instance_id, dir_flags, dir_fd=run_fd)
            _private_dir_identity(session_fd, self.session_dir,
                                  self._session_dir_identity)
            if not self._path_matches(self.session_dir, self._session_dir_identity,
                                      stat_mod.S_ISDIR):
                raise OSError("session directory changed during startup")

            self.token = SessionAuth.generate()
            self._auth = SessionAuth(self.token)
            self.socket_path, self._sock_tmpdir = self._resolve_socket_path(self.session_dir)
            if self._sock_tmpdir is not None:
                self._sock_tmpdir.mkdir(mode=0o700)
            socket_parent_stat = self.socket_path.parent.lstat()
            if (not stat_mod.S_ISDIR(socket_parent_stat.st_mode)
                    or socket_parent_stat.st_uid != os.geteuid()):
                raise OSError("socket parent is not a directory")
            socket_parent_identity = (socket_parent_stat.st_dev, socket_parent_stat.st_ino)
            self._socket_parent_identity = socket_parent_identity
            if (self._sock_tmpdir is None
                    and socket_parent_identity != self._session_dir_identity):
                raise OSError("session directory changed before bind")
            if self._sock_tmpdir is not None:
                os.chmod(self._sock_tmpdir, 0o700)
            if stat_mod.S_IMODE(self.socket_path.parent.stat().st_mode) != 0o700:
                raise PermissionError("private socket directory required")

            router = Router(reader, BridgeMeta(self.instance_id, os.getpid(),
                                               BRIDGE_VERSION, blender_version))
            self._queue = TaskQueue(router.handle, self._clock, diag=_diag)

            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener = listener
            listener.bind(str(self.socket_path))
            self._socket_owned = True   # bind 成功 = 本实例拥有该路径（复审 R-02）
            if not self._path_matches(self.socket_path.parent,
                                      self._socket_parent_identity, stat_mod.S_ISDIR):
                raise OSError("socket parent changed during bind")
            socket_stat = self.socket_path.lstat()
            if not stat_mod.S_ISSOCK(socket_stat.st_mode):
                raise OSError("bound socket path is not a socket")
            socket_identity = (socket_stat.st_dev, socket_stat.st_ino)
            self._socket_identity = socket_identity
            os.chmod(self.socket_path, 0o600)          # §2.2：bind 后立即收权限
            listener.listen(8)
            listener.setblocking(False)
            self._wake_r, self._wake_w = socket.socketpair()
            self._wake_r.setblocking(False)
            self._wake_w.setblocking(False)
            self._io = threading.Thread(target=self._io_loop, name="bcx-io", daemon=True)
            self._io.start()

            # 最后才发布：bind/listen/线程任一失败都不会留下被 Discovery
            # 长期误识别的「假会话」文件
            write_session_file(self.session_dir / "session.json", {
                "instance_id": self.instance_id, "token": self.token, "pid": os.getpid(),
                "socket_path": str(self.socket_path), "blender_version": blender_version,
                "bridge_version": BRIDGE_VERSION,
                "envelope_version": envelope.ENVELOPE_VERSION,
                "socket_external": self._sock_tmpdir is not None,
                "socket_dev": socket_identity[0],
                "socket_ino": socket_identity[1],
                "socket_dir_dev": socket_parent_identity[0],
                "socket_dir_ino": socket_parent_identity[1],
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }, dir_fd=session_fd)
            session_stat = os.stat("session.json", dir_fd=session_fd,
                                   follow_symlinks=False)
            if (not stat_mod.S_ISREG(session_stat.st_mode)
                    or stat_mod.S_IMODE(session_stat.st_mode) != 0o600):
                raise OSError("published session file is not private")
            self._session_identity = (session_stat.st_dev, session_stat.st_ino)
        except BaseException:
            # start() never returns ``self`` on failure, so retry one transient
            # cleanup failure here while the resource references are still reachable.
            if not self.stop() and not self.stop():
                _diag.error("startup cleanup remains incomplete after retry")
            raise
        finally:
            for fd in (session_fd, run_fd, root_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        # close(2) error state is platform-dependent; retrying may
                        # close a reused descriptor.  Do not turn a published, usable
                        # session into an orphaned startup failure.
                        _diag.exception("directory fd close failed")
        return self

    @staticmethod
    def _resolve_socket_path(session_dir: Path) -> tuple[Path, Path | None]:
        p = session_dir / "bridge.sock"
        if len(str(p).encode()) <= MAX_SUN_PATH:
            return p, None
        digest = hashlib.sha256(session_dir.name.encode()).hexdigest()[:16]
        short = Path("/tmp") / f"bcx-{digest}"  # nosec B108
        if len(str(short / "bridge.sock").encode()) > MAX_SUN_PATH:
            raise OSError("no short Unix socket path available")
        return short / "bridge.sock", short

    # ---------- 发送：唯一入口（§3.7 规则 3 单写者） ----------
    def send(self, conn: _Conn, frame: bytes) -> None:
        """任意线程可调；只入 outbox + 唤醒。对已断开连接静默丢弃（§3.6）。"""
        over_limit = False
        with self._conns_lock:
            if (self._conns.get(conn.sock.fileno()) is not conn or conn.closing):
                return
            total = sum(item.outbox_bytes for item in self._conns.values())
            if (conn.outbox_bytes + len(frame) > MAX_OUTBOX
                    or total + len(frame) > MAX_TOTAL_OUTBOX):
                conn.closing = True
                over_limit = True
            else:
                conn.outbox.append(frame)
                conn.outbox_bytes += len(frame)
        if over_limit:
            _diag.info("outbox limit exceeded, dropping connection")
        self._wake()

    def _wake(self) -> None:
        with self._wake_lock:
            if self._wake_pending or self._wake_w is None:
                return
            try:
                self._wake_w.send(b"x")
                self._wake_pending = True
            except BlockingIOError:
                self._wake_pending = True   # 已有字节占满缓冲区，同样会唤醒 select
            except OSError:
                pass

    def _drain_wake(self) -> None:
        assert self._wake_r is not None
        with self._wake_lock:
            try:
                while self._wake_r.recv(4096):
                    pass
            except OSError:
                pass
            self._wake_pending = False

    # ---------- I/O 线程（§3.7 五规则） ----------
    def _io_loop(self) -> None:
        # stop() may time out while this thread is finishing one iteration and then
        # close the listener/socketpair. Re-check the flag at the loop boundary so
        # the next iteration cannot spin forever on already-closed descriptors merely
        # because the wake byte was not observed by the previous select.
        while not self.stopped:
            try:
                if self._io_iterate():
                    return
            except Exception:                            # 规则 5：护栏，绝不带走线程
                _diag.exception("io loop iteration failed")

    def _io_iterate(self) -> bool:
        assert self._listener is not None and self._wake_r is not None
        self._retry_pending_closes()
        with self._conns_lock:
            closing = [c for c in self._conns.values() if c.closing]
        for conn in closing:
            self._drop(conn)
        with self._conns_lock:
            conns = [c for c in self._conns.values() if not c.closing]
            pending_close = bool(self._pending_close)
        rlist: list[socket.socket] = [self._wake_r]
        if not pending_close:
            rlist.insert(0, self._listener)
        rlist += [c.sock for c in conns]
        wlist = [c.sock for c in conns if c.outbox]
        ready_r, ready_w, _ = select.select(rlist, wlist, [], 1.0)
        if self._wake_r in ready_r:
            self._drain_wake()
            if self.stopped:
                return True
        if self._listener in ready_r:
            sock: socket.socket | None = None
            owned = False
            try:
                sock, _ = self._listener.accept()
                sock.setblocking(False)
                with self._conns_lock:
                    if len(self._conns) >= MAX_CONNECTIONS:
                        _diag.info("connection limit reached, dropping peer")
                    else:
                        self._conns[sock.fileno()] = _Conn(sock)
                        owned = True
            except Exception:
                _diag.exception("accept failed")
            finally:
                if sock is not None and not owned:
                    try:
                        sock.close()
                    except Exception:
                        _diag.exception("rejected connection close failed")
                        if sock.fileno() >= 0:
                            with self._conns_lock:
                                self._pending_close.append(sock)
        for conn in conns:
            if conn.sock in ready_w:
                self._flush(conn)
        for conn in conns:
            if conn.sock in ready_r:
                self._read(conn)
        self._enforce_backpressure(conns)
        return False

    def _enforce_backpressure(self, conns: list[_Conn]) -> None:
        """规则 4 由 I/O 线程执行——主线程绝不触碰 socket（规则 3 的结构性保证）。"""
        for conn in conns:
            with self._conns_lock:
                over = conn.outbox_bytes > MAX_OUTBOX
            if over:
                _diag.info("outbox limit exceeded, dropping connection")
                self._drop(conn)

    def _retry_pending_closes(self) -> None:
        with self._conns_lock:
            pending = list(getattr(self, "_pending_close", ()))
        for sock in pending:
            try:
                sock.close()
            except Exception:
                _diag.exception("pending connection close failed")
                if sock.fileno() >= 0:
                    continue
            with self._conns_lock:
                if sock in getattr(self, "_pending_close", ()):
                    self._pending_close.remove(sock)

    def _flush(self, conn: _Conn) -> None:
        try:
            while True:
                with self._conns_lock:       # outbox 的每次读写都持锁：send() 在另一
                    if not conn.outbox:      # 线程做 +=，单边持锁不构成互斥
                        return
                    head = conn.outbox[0]
                view = memoryview(head)[conn.send_offset:]
                sent = conn.sock.send(view)  # send_offset 只由 I/O 线程访问，无需锁
                if sent < len(view):
                    conn.send_offset += sent             # 部分写：偏移续写（规则 3）
                    return
                with self._conns_lock:
                    if not conn.outbox or conn.outbox[0] is not head:
                        return
                    conn.outbox.popleft()
                    conn.outbox_bytes -= len(head)
                conn.send_offset = 0
        except BlockingIOError:
            return
        except OSError:
            self._drop(conn)

    def _read(self, conn: _Conn) -> None:
        try:
            data = conn.sock.recv(65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._drop(conn)
            return
        try:
            frames = conn.buf.feed(data)
        except framing.FrameTooLarge:
            self._drop(conn)                             # 读端超限断开（§3.2）
            return
        with self._conns_lock:
            pending_bytes = sum(item.buf.pending for item in self._conns.values())
        if pending_bytes > MAX_INBOUND_PENDING:
            _diag.info("inbound pending limit exceeded, dropping connection")
            self._drop(conn)
            return
        for payload in frames:
            if not self._dispatch(conn, payload):
                break

    def _dispatch(self, conn: _Conn, payload: bytes) -> bool:
        assert self._auth is not None and self._queue is not None
        if len(payload) > MAX_REQUEST_PAYLOAD:
            _diag.info("request payload limit exceeded, closing connection")
            self._drop(conn)
            return False
        try:
            req = envelope.decode_request(payload)
        except ValueError:
            self._drop(conn)                             # 解码失败断开，不回帧（§5）
            return False
        if not self._auth.verify(req.token):
            _diag.info("auth failed, closing connection")  # §5.2 Bridge 诊断日志
            self._drop(conn)
            return False
        timeout = envelope.METHOD_TIMEOUTS.get(req.method, 2.0)
        deadline = self._clock.monotonic() + timeout
        try:
            self._queue.submit(req, lambda frame: self.send(conn, frame), deadline)
        except QueueFull:
            self.send(conn, envelope.error_frame(req.id, envelope.BRIDGE_BUSY,
                                                 "queue full", retryable=True))
        return True

    def _drop(self, conn: _Conn) -> None:
        with self._conns_lock:
            key = next((key for key, value in self._conns.items() if value is conn), None)
            conn.closing = True
            conn.outbox.clear()
            conn.outbox_bytes = 0
            conn.send_offset = 0
        try:
            conn.sock.close()
        except Exception:
            _diag.exception("connection close failed")
            if conn.sock.fileno() >= 0:
                return
        if key is not None:
            with self._conns_lock:
                if self._conns.get(key) is conn:
                    self._conns.pop(key)

    # ---------- 主线程 ----------
    def tick(self, budget_ms: int = 50) -> float:
        assert self._queue is not None
        return self._queue.tick(budget_ms)   # 主线程只跑队列：不碰 _conns、不碰 socket

    # ---------- 关闭（§3.7 10 步，幂等） ----------
    def stop(self, unregister_timer: Callable[[], None] | None = None,
             unregister_handlers: Callable[[], None] | None = None) -> bool:
        self.stopped = True                              # 1 置停止标志
        with self._cleanup_lock:
            if self.cleanup_complete:
                return True
            failed = False
            steps: list[Callable[[], object]] = [
                self._wake,                                  # 2 唤醒 select
                self._join_io,                               # 3 join I/O 线程
                self._close_all_conns,                       # 4 关闭活跃连接（含丢弃 outbox）
                self._close_listener,                        # 5 关监听与 socketpair
                unregister_timer or (lambda: None),          # 6 timer 注销（driver hook）
                unregister_handlers or (lambda: None),       # 7 handler 注销（driver hook）
                self._drain_queue,                           # 8 清空队列不回复
            ]
            for i, step in enumerate(steps, start=2):
                try:
                    if step() is False:
                        failed = True
                        _diag.warning("stop step %d incomplete", i)
                except Exception:
                    failed = True
                    _diag.exception("stop step %d failed, continuing", i)
            transport_closed = self._transport_closed()
            if transport_closed:
                for i, step in ((9, self._unlink_files), (10, self._remove_dirs)):
                    try:
                        if step() is False:
                            failed = True
                            _diag.warning("stop step %d incomplete", i)
                    except Exception:
                        failed = True
                        _diag.exception("stop step %d failed, continuing", i)
            else:
                failed = True
                _diag.warning("transport cleanup incomplete; retaining session paths")
            transport_closed = self._transport_closed()
            self.cleanup_complete = not failed and transport_closed
            return self.cleanup_complete

    def _transport_closed(self) -> bool:
        with self._conns_lock:
            no_connections = not self._conns
            no_pending = not getattr(self, "_pending_close", ())
        return (self._listener is None and self._wake_r is None
                and self._wake_w is None and no_connections and no_pending
                and (self._io is None or not self._io.is_alive()))

    def _join_io(self) -> None:
        if self._io is not None:
            self._io.join(timeout=2.0)

    def _drain_queue(self) -> None:
        if self._queue is not None:
            self._queue.drain()

    def _close_listener(self) -> None:
        failure: Exception | None = None
        for attribute in ("_listener", "_wake_r", "_wake_w"):
            sock = getattr(self, attribute)
            if sock is not None:
                try:
                    sock.close()
                except Exception as exc:
                    failure = failure or exc
                    _diag.exception("transport close failed")
                else:
                    setattr(self, attribute, None)
        if (self._io is not None and self._io is not threading.current_thread()
                and self._io.is_alive()):
            self._io.join(timeout=1.0)
            if self._io.is_alive():
                _diag.warning("I/O thread still alive after transport close")
                failure = failure or RuntimeError("I/O thread still alive")
        if self._io is not None and not self._io.is_alive():
            self._io = None
        if failure is not None:
            raise failure

    def _close_all_conns(self) -> None:
        with self._conns_lock:
            conns = list(self._conns.items())
        failure: Exception | None = None
        for key, c in conns:
            with self._conns_lock:
                c.closing = True
                c.outbox.clear()
                c.outbox_bytes = 0
                c.send_offset = 0
            try:
                c.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                c.sock.close()
            except Exception as exc:
                failure = failure or exc
                _diag.exception("connection close failed")
            else:
                with self._conns_lock:
                    if self._conns.get(key) is c:
                        self._conns.pop(key)
        if failure is not None:
            raise failure
        self._retry_pending_closes()

    def _unlink_files(self) -> bool:
        # 只删自己 bind 成功的 socket：EADDRINUSE 时该路径属于**别人**的活 listener，
        # 删掉即造成对方拒绝服务（复审 R-02 实测）
        complete = True
        if self._socket_owned:
            if self.socket_path == Path() or not self._path_matches(
                    self.socket_path.parent, self._socket_parent_identity,
                    stat_mod.S_ISDIR):
                return False
            if self._path_matches(self.socket_path, self._socket_identity,
                                  stat_mod.S_ISSOCK):
                # POSIX has no atomic final identity-check + unlink-by-path; this
                # bounds, but cannot eliminate, replacement after the final check.
                try:
                    self.socket_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    complete = False
            elif not self._path_absent(self.socket_path):
                complete = False
            if complete:
                self._socket_owned = False
        if not complete:
            # Preserve session metadata as retryable evidence whenever the owned
            # socket path was replaced or could not be removed safely.
            return False
        session_file = self.session_dir / "session.json"
        if self.session_dir != Path() \
                and self._path_matches(session_file, self._session_identity,
                                       stat_mod.S_ISREG):
            try:
                session_file.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                complete = False
        elif self.session_dir != Path() and not self._path_absent(session_file):
            complete = False
        return complete

    @staticmethod
    def _path_matches(path: Path, expected: tuple[int, int] | None,
                      kind: Callable[[int], bool]) -> bool:
        if expected is None:
            return False
        try:
            st = path.lstat()
        except OSError:
            return False
        return kind(st.st_mode) and (st.st_dev, st.st_ino) == expected

    @staticmethod
    def _path_absent(path: Path) -> bool:
        try:
            path.lstat()
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return False

    def _remove_dirs(self) -> bool:
        complete = True
        for d, expected in ((self._sock_tmpdir, self._socket_parent_identity),
                            (self.session_dir, self._session_dir_identity)):
            if d is None or d == Path():
                continue
            if self._path_matches(d, expected, stat_mod.S_ISDIR):
                try:
                    d.rmdir()
                except OSError:
                    complete = False
                    _diag.info("session dir not empty, left in place: %s", d)
            elif not self._path_absent(d):
                complete = False
        return complete
