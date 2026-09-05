# tests/unit/test_lifecycle.py
import json
import logging
import os
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from bridge.core.contracts import SceneSnapshot
from bridge.core.lifecycle import MAX_CONNECTIONS, BridgeSession
from protocol import envelope, framing
from server.core.bridge_client import BridgeClient


class FakeReader:
    def blender_version(self) -> str:
        return "5.2.0"

    def status_info(self):
        return (None, 0)

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        if False:
            yield
        return SceneSnapshot(
            scene_revision=0, scene_hash="sha256:e", scene_name="Scene", scene_path=None,
            units_system="NONE", units_scale_length=1.0, object_count=0, mesh_count=0,
            camera_count=0, light_count=0, collections=(),
        )


@pytest.fixture
def session(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    pump = threading.Thread(target=lambda: _pump(s), daemon=True)
    pump.start()
    yield s
    s.stop()


def _pump(s: BridgeSession) -> None:   # 测试里代替 Blender timer 驱动主线程 tick
    while not s.stopped:
        time.sleep(s.tick(budget_ms=50))


def _rpc(s: BridgeSession, method: str, token: str | None = None) -> dict:
    with socket.socket(socket.AF_UNIX) as c:
        c.settimeout(2.0)
        c.connect(str(s.socket_path))
        tok = s.token if token is None else token
        c.sendall(envelope.encode_request(envelope.Request.new(tok, method, {})))
        buf = framing.FrameBuffer()
        while True:
            data = c.recv(65536)
            if not data:
                return {"__closed__": True}
            frames = buf.feed(data)
            if frames:
                return json.loads(frames[0])


def _fd_bridge_roundtrip(runtime_root: str, high_fd: bool) -> None:
    import errno
    import resource

    descriptors: list[int] = []
    bridge = None
    pump = None
    stopped_cleanly = False
    pump_alive = False
    diagnostic_logger = logging.getLogger("bcx.bridge")
    diagnostics_disabled = diagnostic_logger.disabled
    diagnostic_logger.disabled = True
    try:
        if high_fd:
            target_fd = 1030
            required_limit = target_fd + 1 + 32  # directories, transport, selector and client
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            if hard_limit != resource.RLIM_INFINITY and hard_limit < required_limit:
                raise SystemExit(77)
            if soft_limit != resource.RLIM_INFINITY and soft_limit < required_limit:
                try:
                    resource.setrlimit(resource.RLIMIT_NOFILE,
                                       (required_limit, hard_limit))
                except (OSError, ValueError):
                    raise SystemExit(77) from None
            try:
                while not descriptors or descriptors[-1] < target_fd:
                    descriptors.append(os.open(os.devnull, os.O_RDONLY))
            except OSError as exc:
                if exc.errno == errno.EMFILE:
                    raise SystemExit(77) from None
                raise

        bridge = BridgeSession.start(Path(runtime_root), FakeReader(),
                                     blender_version="5.2.0")
        assert bridge._listener is not None
        if high_fd:
            assert bridge._listener.fileno() >= 1024
        else:
            assert bridge._listener.fileno() < 1024
        pump = threading.Thread(target=lambda: _pump(bridge), daemon=True)
        pump.start()

        client = BridgeClient({"socket_path": str(bridge.socket_path),
                               "token": bridge.token})
        assert client.call("ping", timeout=1.0)["instance_id"] == bridge.instance_id
    finally:
        try:
            if bridge is not None:
                stopped_cleanly = bridge.stop()
        finally:
            if pump is not None:
                pump.join(timeout=2.0)
                pump_alive = pump.is_alive()
            for descriptor in reversed(descriptors):
                os.close(descriptor)
            diagnostic_logger.disabled = diagnostics_disabled

    assert bridge is not None
    assert stopped_cleanly and not pump_alive
    assert not bridge.socket_path.exists()
    assert not bridge.session_dir.exists()
    assert not [thread for thread in threading.enumerate()
                if thread.name.startswith("bcx-")]


@pytest.mark.parametrize("high_fd,low_soft_limit", [(False, False), (True, False),
                                                  (True, True)],
                         ids=["low-fd", "high-fd", "high-fd-low-soft-limit"])
def test_bridge_roundtrip_with_high_numbered_descriptors_in_subprocess(
        tmp_path, high_fd, low_soft_limit):
    mode = "high" if high_fd else "low"
    code = (
        "from tests.unit.test_lifecycle import _fd_bridge_roundtrip; import sys; "
        "_fd_bridge_roundtrip(sys.argv[1], sys.argv[2] == 'high')"
    )
    if low_soft_limit:
        code = (
            "import resource\n"
            "soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)\n"
            "if hard != resource.RLIM_INFINITY and hard < 1063: raise SystemExit(77)\n"
            "resource.setrlimit(resource.RLIMIT_NOFILE, (1024, hard))\n"
        ) + code
    completed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), mode],
        capture_output=True, text=True, timeout=15.0,
    )
    if completed.returncode == 77:
        pytest.skip("OS resource limits cannot provide descriptor 1024")
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_start_creates_private_files(session, tmp_path):
    import bridge.core.lifecycle as lc

    assert lc.MAX_CONNECTIONS == 64
    assert lc.MAX_INBOUND_PENDING == 32 * 1024 * 1024
    assert lc.MAX_REQUEST_PAYLOAD == 64 * 1024
    assert lc.MAX_OUTBOX == 32 * 1024 * 1024
    assert lc.MAX_TOTAL_OUTBOX == 64 * 1024 * 1024
    d = session.session_dir
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE(session.socket_path.stat().st_mode) == 0o600
    sj = json.loads((d / "session.json").read_text())
    assert sj["instance_id"] == session.instance_id
    assert sj["socket_path"] == str(session.socket_path)
    assert sj["envelope_version"] == 1
    assert type(sj["socket_external"]) is bool
    assert all(type(sj[key]) is int for key in (
        "socket_dev", "socket_ino", "socket_dir_dev", "socket_dir_ino"))


def test_start_ignores_restrictive_umask(tmp_path):
    root = tmp_path / "runtime"
    previous_umask = os.umask(0o777)
    try:
        session = BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    finally:
        os.umask(previous_umask)
    try:
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE((root / "run").stat().st_mode) == 0o700
        assert stat.S_IMODE(session.session_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE((session.session_dir / "session.json").stat().st_mode) == 0o600
        assert stat.S_IMODE(session.socket_path.stat().st_mode) == 0o600
    finally:
        session.stop()


def test_concurrent_start_waits_for_restrictive_umask_chmod(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "runtime"
    chmod_entered = threading.Event()
    release_chmod = threading.Event()
    sessions = []
    errors = []
    real_chmod = lifecycle.os.chmod

    def delayed_root_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if Path(path) == root and dir_fd is None and not chmod_entered.is_set():
            chmod_entered.set()
            assert release_chmod.wait(1.0)
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    monkeypatch.setattr(lifecycle.os, "chmod", delayed_root_chmod)

    def start() -> None:
        try:
            sessions.append(BridgeSession.start(
                root, FakeReader(), blender_version="5.2.0"))
        except BaseException as exc:
            errors.append(exc)

    previous_umask = os.umask(0o777)
    try:
        worker_a = threading.Thread(target=start)
        worker_a.start()
        assert chmod_entered.wait(1.0)
        worker_b = threading.Thread(target=start)
        worker_b.start()
        time.sleep(0.02)
        release_chmod.set()
        worker_a.join(timeout=3.0)
        worker_b.join(timeout=3.0)
    finally:
        release_chmod.set()
        os.umask(previous_umask)
        for started in sessions:
            started.stop()
    assert not worker_a.is_alive() and not worker_b.is_alive()
    assert errors == [] and len(sessions) == 2


def test_start_rejects_wide_runtime_root_without_chmod(tmp_path):
    root = tmp_path / "wide-runtime"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(PermissionError, match="private directory"):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    assert stat.S_IMODE(root.stat().st_mode) == 0o755


def test_start_rejects_runtime_root_owned_by_other_uid(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "foreign-runtime"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    foreign_uid = os.geteuid() + 1
    monkeypatch.setattr(lifecycle.os, "geteuid", lambda: foreign_uid)

    with pytest.raises(PermissionError, match="private directory"):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")


def test_start_preserves_permissions_above_runtime_root(tmp_path):
    ancestor = tmp_path / "shared-ancestor"
    ancestor.mkdir(mode=0o755)
    ancestor.chmod(0o755)
    session = BridgeSession.start(
        ancestor / "runtime", FakeReader(), blender_version="5.2.0")
    try:
        assert stat.S_IMODE(ancestor.stat().st_mode) == 0o755
        assert stat.S_IMODE((ancestor / "runtime").stat().st_mode) == 0o700
    finally:
        session.stop()


def test_start_rejects_symlink_runtime_root(tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    root = tmp_path / "runtime-link"
    root.symlink_to(target, target_is_directory=True)
    with pytest.raises(PermissionError, match="private directory"):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    assert root.is_symlink() and target.exists()


def test_start_rejects_preexisting_session_leaf(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "runtime"
    run = root / "run"
    run.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    run.chmod(0o700)
    monkeypatch.setattr(lifecycle.secrets, "token_hex", lambda _n: "deadbeef")
    leaf = run / f"gui-{lifecycle.os.getpid()}-deadbeef"
    leaf.mkdir(mode=0o755)
    leaf.chmod(0o755)
    with pytest.raises(FileExistsError):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    assert leaf.exists() and stat.S_IMODE(leaf.stat().st_mode) == 0o755


def test_start_never_creates_session_through_replaced_run_path(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "runtime"
    run = root / "run"
    run.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    run.chmod(0o700)
    original_run = root / "run-original"
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    real_mkdir = lifecycle.os.mkdir
    swapped = False

    def swap_before_leaf(path, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and isinstance(path, str) and path.startswith("gui-"):
            run.rename(original_run)
            run.symlink_to(outside, target_is_directory=True)
            swapped = True
        return real_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(lifecycle.os, "mkdir", swap_before_leaf)
    try:
        with pytest.raises(OSError, match="session directory changed"):
            BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
        assert swapped
        assert list(outside.iterdir()) == []
    finally:
        if run.is_symlink():
            run.unlink()
        if original_run.exists():
            for child in original_run.iterdir():
                child.rmdir()
            original_run.rmdir()


def test_ping_roundtrip(session):
    body = _rpc(session, "ping")
    assert body["ok"] is True
    assert body["result"]["instance_id"] == session.instance_id


def test_peer_disconnect_cancels_started_continuation(tmp_path):
    started = threading.Event()
    closed = threading.Event()
    closed_on: list[threading.Thread] = []

    class EndlessReader(FakeReader):
        def snapshot_steps(self, *, include_collections=True,
                           include_managed_objects=True):
            try:
                while True:
                    started.set()
                    time.sleep(0.005)
                    yield
            finally:
                closed_on.append(threading.current_thread())
                closed.set()

    bridge = BridgeSession.start(tmp_path, EndlessReader(), blender_version="5.2.0")
    pump = threading.Thread(target=lambda: _pump(bridge), daemon=True)
    pump.start()
    client = socket.socket(socket.AF_UNIX)
    try:
        client.connect(str(bridge.socket_path))
        client.sendall(envelope.encode_request(
            envelope.Request.new(bridge.token, "scene_summary", {})))
        assert started.wait(1.0)
        client.close()
        assert closed.wait(1.0), "peer disconnect left scene continuation running"
        assert closed_on == [pump]
    finally:
        client.close()
        bridge.stop()
        pump.join(timeout=2.0)


def test_request_budget_clamps_bridge_continuation_deadline(tmp_path):
    started = threading.Event()
    closed = threading.Event()

    class EndlessReader(FakeReader):
        def snapshot_steps(self, *, include_collections=True,
                           include_managed_objects=True):
            try:
                while True:
                    started.set()
                    time.sleep(0.005)
                    yield
            finally:
                closed.set()

    bridge = BridgeSession.start(tmp_path, EndlessReader(), blender_version="5.2.0")
    pump = threading.Thread(target=lambda: _pump(bridge), daemon=True)
    pump.start()
    with socket.socket(socket.AF_UNIX) as client:
        try:
            client.connect(str(bridge.socket_path))
            client.sendall(envelope.encode_request(envelope.Request.new(
                bridge.token, "scene_summary", {}, budget_ms=40)))
            assert started.wait(1.0)
            assert closed.wait(1.0), "relative request budget was not enforced by bridge"
        finally:
            bridge.stop()
            pump.join(timeout=2.0)


def test_wrong_token_closed_without_response(session):
    assert _rpc(session, "ping", token="bad") == {"__closed__": True}


@pytest.mark.parametrize("first_kind", ["malformed", "bad-token"])
def test_rejected_frame_discards_same_recv_pipeline_tail(tmp_path, first_kind):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    valid = envelope.encode_request(envelope.Request.new(s.token, "ping", {}))
    first = (framing.encode_frame(b"{not-json") if first_kind == "malformed" else
             envelope.encode_request(envelope.Request.new("bad", "ping", {})))
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2.0)
            client.connect(str(s.socket_path))
            client.sendall(first + valid)
            assert client.recv(1) == b""
        assert s._queue is not None and s._queue.pending == 0
    finally:
        s.stop()


def test_half_header_does_not_wedge_other_connections(session):
    slow = socket.socket(socket.AF_UNIX)
    slow.connect(str(session.socket_path))
    slow.sendall(b"\x00\x00")            # 半个长度头，然后沉默
    try:
        assert _rpc(session, "ping")["ok"] is True   # 其余连接照常服务（§3.7 规则 1）
    finally:
        slow.close()


def test_partial_frame_connection_flood_is_capped_and_recovers(session):
    clients = []

    def connection_count():
        with session._conns_lock:
            return len(session._conns)

    def connect_client():
        deadline = time.monotonic() + 2.0
        while True:
            client = socket.socket(socket.AF_UNIX)
            client.settimeout(2.0)
            try:
                client.connect(str(session.socket_path))
                return client
            except ConnectionRefusedError:
                client.close()
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.005)

    try:
        for _ in range(MAX_CONNECTIONS):
            client = connect_client()
            client.sendall(b"\x01\x00\x00\x00" + b"x" * 1024)
            clients.append(client)

        deadline = time.monotonic() + 2.0
        while connection_count() < MAX_CONNECTIONS and time.monotonic() < deadline:
            time.sleep(0.005)
        assert connection_count() == MAX_CONNECTIONS

        overflow = connect_client()
        try:
            overflow.sendall(envelope.encode_request(
                envelope.Request.new(session.token, "ping", {})))
        except BrokenPipeError:
            pass
        assert overflow.recv(1) == b""
        overflow.close()
        assert connection_count() == MAX_CONNECTIONS

        clients.pop().close()
        deadline = time.monotonic() + 2.0
        while connection_count() >= MAX_CONNECTIONS and time.monotonic() < deadline:
            time.sleep(0.005)
        assert connection_count() < MAX_CONNECTIONS
        assert _rpc(session, "ping")["ok"] is True
    finally:
        for client in clients:
            client.close()


def test_global_inbound_pending_cap_drops_excess_partial_frame(session, monkeypatch):
    import bridge.core.lifecycle as lc

    monkeypatch.setattr(lc, "MAX_INBOUND_PENDING", 2048)
    first = socket.socket(socket.AF_UNIX)
    second = socket.socket(socket.AF_UNIX)
    try:
        first.settimeout(2.0)
        second.settimeout(2.0)
        first.connect(str(session.socket_path))
        second.connect(str(session.socket_path))
        partial = b"\x01\x00\x00\x00" + b"x" * 1500
        first.sendall(partial)
        second.sendall(partial)
        assert second.recv(1) == b""
        assert _rpc(session, "ping")["ok"] is True
    finally:
        first.close()
        second.close()


def test_oversized_request_payload_is_rejected_before_queueing(session, monkeypatch):
    import bridge.core.lifecycle as lc

    monkeypatch.setattr(lc, "MAX_REQUEST_PAYLOAD", 64)
    client = socket.socket(socket.AF_UNIX)
    try:
        client.settimeout(2.0)
        client.connect(str(session.socket_path))
        request = envelope.Request.new(session.token, "ping", {"blob": "x" * 100})
        client.sendall(envelope.encode_request(request))
        assert client.recv(1) == b""
        assert session._queue is not None and session._queue.pending == 0
    finally:
        client.close()


def test_accept_failure_closes_unowned_socket_and_retries_close(monkeypatch):
    import bridge.core.lifecycle as lc

    class FakeListener:
        def accept(self):
            return accepted, None

    class FakeWake:
        pass

    class FakeAccepted:
        def __init__(self):
            self.close_calls = 0

        def fileno(self):
            return 42

        def setblocking(self, _value):
            raise OSError("setblocking failed")

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("close failed")

    accepted = FakeAccepted()
    session = BridgeSession.__new__(BridgeSession)
    session._listener = FakeListener()
    session._wake_r = FakeWake()
    session._wake_w = None
    session._conns = {}
    session._conns_lock = threading.Lock()
    session._pending_close = []
    class FakeSelector:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def register(self, *_args):
            pass

        def select(self, **_kwargs):
            key = SimpleNamespace(fileobj=session._listener)
            return [(key, lc.selectors.EVENT_READ)]

    monkeypatch.setattr(lc.selectors, "DefaultSelector", FakeSelector)

    session._io_iterate()
    assert accepted.close_calls == 1 and session._conns == {}
    assert session._pending_close == [accepted]
    session._retry_pending_closes()
    assert accepted.close_calls == 2 and session._pending_close == []


def test_drop_retains_connection_when_close_fails_then_retries():
    import bridge.core.lifecycle as lc

    class FlakySocket:
        def __init__(self):
            self.close_calls = 0

        def fileno(self):
            return 7

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("close failed")

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {}
    session._pending_close = []
    session._listener = object()
    session._wake_r = object()
    conn = type("Conn", (), {"sock": FlakySocket(), "closing": False,
                              "outbox": deque([b"held"]), "outbox_bytes": 4,
                              "send_offset": 0})()
    session._conns[7] = conn

    session._drop(conn)
    assert session._conns[7] is conn and conn.closing is True
    assert conn.outbox_bytes == 0 and not conn.outbox
    class FakeSelector:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def register(self, *_args):
            pass

        def select(self, **_kwargs):
            return []

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(lc.selectors, "DefaultSelector", FakeSelector)
    try:
        session._io_iterate()
    finally:
        monkeypatch.undo()
    assert session._conns == {}


def test_send_rejects_old_connection_after_fd_key_reuse():
    class FakeSocket:
        def __init__(self, fd):
            self.fd = fd

        def fileno(self):
            return self.fd

    def conn(sock):
        return type("Conn", (), {"sock": sock, "closing": False,
                                  "outbox": [], "outbox_bytes": 0})()

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {}
    session._wake = lambda: pytest.fail("stale connection was woken")
    old = conn(FakeSocket(7))
    new = conn(FakeSocket(7))
    session._conns[7] = new

    session.send(old, b"stale")
    assert old.outbox == [] and new.outbox == []


def test_send_enforces_outbox_caps_without_touching_socket(monkeypatch, caplog):
    import bridge.core.lifecycle as lc

    class FakeSocket:
        def __init__(self, fd):
            self.fd = fd
            self.close_calls = 0

        def fileno(self):
            return self.fd

        def close(self):
            self.close_calls += 1

    def conn(fd, pending):
        payload = b"x" * pending
        return type("Conn", (), {"sock": FakeSocket(fd), "closing": False,
                                  "outbox": deque([payload]), "outbox_bytes": pending,
                                  "send_offset": 0})()

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    first, second = conn(1, 6), conn(2, 4)
    session._conns = {1: first, 2: second}
    wakes = []
    session._wake = lambda: wakes.append(True)

    with caplog.at_level(logging.INFO, logger="bcx.bridge"):
        monkeypatch.setattr(lc, "MAX_OUTBOX", 6)
        monkeypatch.setattr(lc, "MAX_TOTAL_OUTBOX", 100)
        session.send(first, b"x")
        assert first.closing is True and first.outbox_bytes == 6
        assert first.sock.close_calls == second.sock.close_calls == 0

        first, second = conn(1, 6), conn(2, 4)
        session._conns = {1: first, 2: second}
        monkeypatch.setattr(lc, "MAX_OUTBOX", 10)
        monkeypatch.setattr(lc, "MAX_TOTAL_OUTBOX", 10)
        session.send(second, b"x")
    assert second.closing is True and second.outbox_bytes == 4
    assert first.sock.close_calls == second.sock.close_calls == 0
    assert wakes == [True, True]
    assert sum("outbox limit exceeded" in record.message
               for record in caplog.records) == 2


def test_partial_flush_keeps_retained_frame_bytes_until_pop():
    class PartialSocket:
        def fileno(self):
            return 7

        def send(self, view):
            return min(3, len(view))

    conn = type("Conn", (), {"sock": PartialSocket(), "closing": False,
                              "outbox": deque([b"abcdef"]), "outbox_bytes": 6,
                              "send_offset": 0})()
    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {7: conn}

    session._flush(conn)
    assert conn.outbox_bytes == 6 and conn.send_offset == 3
    session._flush(conn)
    assert conn.outbox_bytes == 0 and conn.send_offset == 0 and not conn.outbox


def test_stop_is_idempotent_and_cleans_up(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    c = socket.socket(socket.AF_UNIX)
    c.connect(str(s.socket_path))
    s.stop()
    s.stop()                              # 幂等
    assert not s.socket_path.exists()
    assert not s.session_dir.exists()
    assert c.recv(1) == b""               # 活跃连接被关闭（§3.7 第 4 步）
    c.close()


def test_io_loop_rechecks_stop_between_iterations():
    """Late stop must not require observing the wake fd to terminate the loop."""
    s = BridgeSession.__new__(BridgeSession)
    s.stopped = False
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def iterate() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(1.0)
            return False
        return True  # lets the pre-fix implementation exit instead of leaking the test

    s._io_iterate = iterate  # type: ignore[method-assign]
    worker = threading.Thread(target=s._io_loop, daemon=True)
    worker.start()
    assert entered.wait(1.0)
    s.stopped = True
    release.set()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert calls == 1


def test_io_loop_exits_after_permanent_monitoring_failure(tmp_path, monkeypatch, caplog):
    import bridge.core.lifecycle as lc

    calls = 0

    def fail():
        nonlocal calls
        calls += 1
        raise OSError("permanent monitor failure")

    monkeypatch.setattr(lc.selectors, "DefaultSelector", fail)
    with caplog.at_level(logging.ERROR, logger="bcx.bridge"):
        session = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
        try:
            session._io.join(timeout=2.0)
            assert not session._io.is_alive()
            assert session.stopped
            assert calls == 1
            assert sum(record.message == "io loop iteration failed"
                       for record in caplog.records) == 1
        finally:
            assert session.stop()
    assert session.cleanup_complete and session._transport_closed()
    assert not session.socket_path.exists() and not session.session_dir.exists()


def test_transport_close_performs_final_io_thread_join():
    session = BridgeSession.__new__(BridgeSession)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    session._listener = listener
    session._wake_r = None
    session._wake_w = None

    def wait_for_close() -> None:
        while listener.fileno() != -1:
            time.sleep(0.005)

    session._io = threading.Thread(target=wait_for_close)
    session._io.start()
    session._close_listener()
    assert session._io is None


def test_transport_close_continues_after_individual_close_failure():
    events = []

    class FakeSocket:
        def __init__(self, name, fail=False):
            self.name = name
            self.fail = fail

        def close(self):
            events.append(self.name)
            if self.fail:
                raise OSError("close failed")

    session = BridgeSession.__new__(BridgeSession)
    session._listener = FakeSocket("listener", fail=True)
    session._wake_r = FakeSocket("wake-r")
    session._wake_w = FakeSocket("wake-w")
    session._io = None

    with pytest.raises(OSError, match="close failed"):
        session._close_listener()

    assert events == ["listener", "wake-r", "wake-w"]
    assert session._listener is not None
    assert session._wake_r is None and session._wake_w is None


def test_connection_close_continues_after_individual_close_failure():
    events = []

    class FakeSocket:
        def __init__(self, name, fail=False):
            self.name = name
            self.fail = fail

        def shutdown(self, _how):
            pass

        def close(self):
            events.append(self.name)
            if self.fail:
                raise OSError("close failed")

    class FakeConnection:
        def __init__(self, sock):
            self.sock = sock
            self.closing = False
            self.outbox = deque([b"pending"])
            self.outbox_bytes = len(self.outbox[0])
            self.send_offset = 0

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {
        1: FakeConnection(FakeSocket("first", fail=True)),
        2: FakeConnection(FakeSocket("second")),
    }

    with pytest.raises(OSError, match="close failed"):
        session._close_all_conns()

    assert events == ["first", "second"]
    assert list(session._conns) == [1]
    assert session._conns[1].outbox_bytes == 0


def test_stop_retries_failed_transport_close_and_then_becomes_idempotent():
    events: list[str] = []

    class FlakySocket:
        def __init__(self):
            self.calls = 0

        def close(self):
            self.calls += 1
            events.append(f"close-{self.calls}")
            if self.calls == 1:
                raise OSError("transient close failure")

    session = BridgeSession.__new__(BridgeSession)
    session.stopped = False
    session.cleanup_complete = False
    session._cleanup_lock = threading.Lock()
    session._conns_lock = threading.Lock()
    session._conns = {}
    session._listener = FlakySocket()
    session._wake_r = None
    session._wake_w = None
    session._io = None
    session._wake = lambda: events.append("wake")
    session._join_io = lambda: None
    session._close_all_conns = lambda: None
    session._drain_queue = lambda: None
    session._unlink_files = lambda: events.append("unlink")
    session._remove_dirs = lambda: events.append("rmdir")

    assert session.stop() is False
    assert session.stopped is True and session._listener is not None
    assert events == ["wake", "close-1"]

    assert session.stop() is True
    assert session._listener is None
    assert events == ["wake", "close-1", "wake", "close-2", "unlink", "rmdir"]

    assert session.stop() is True
    assert events[-1] == "rmdir" and events.count("close-2") == 1


def test_failed_transport_close_retains_published_paths_until_retry(tmp_path):
    session = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    listener = session._listener
    assert listener is not None

    class FirstCloseFailure:
        def __init__(self, inner):
            self.inner = inner
            self.close_calls = 0

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("transient close failure")
            self.inner.close()

    wrapped = FirstCloseFailure(listener)
    session._listener = wrapped
    assert session.stop() is False
    assert session.socket_path.exists()
    assert (session.session_dir / "session.json").exists()
    assert wrapped.inner.fileno() >= 0

    assert session.stop() is True
    assert wrapped.inner.fileno() == -1
    assert not session.socket_path.exists() and not session.session_dir.exists()


def test_sun_path_fallback(tmp_path):
    deep = tmp_path / ("x" * 90)          # 让默认 socket 路径必然超 100 字节
    s = BridgeSession.start(deep, FakeReader(), blender_version="5.2.0")
    fallback = s._sock_tmpdir
    assert fallback is not None
    original = fallback.with_name(fallback.name + "-original")
    blocker = s.session_dir / "foreign.txt"
    try:
        assert len(str(s.socket_path).encode()) <= 100
        assert s.session_dir.exists()     # session.json 仍在 runtime 根下
        fallback.rename(original)
        fallback.mkdir(mode=0o700)
        assert s.stop() is False
        assert fallback.exists()
        assert s.session_dir.exists()
        assert (s.session_dir / "session.json").exists()

        fallback.rmdir()
        original.rename(fallback)
        blocker.write_text("preserve")
        assert s.stop() is False
        assert not fallback.exists()
        blocker.unlink()
        assert s.stop() is True
    finally:
        blocker.unlink(missing_ok=True)
        if fallback.exists():
            fallback.rmdir()
        if original.exists():
            original.rename(fallback)
        s.stop()


def test_failed_start_leaves_no_artifacts(tmp_path, monkeypatch):
    # audit F-04：发布前任一步失败 → 无 session.json、无遗留目录、无泄漏线程
    import bridge.core.lifecycle as lc

    def boom(path, data, *, dir_fd=None):
        raise OSError("disk full")

    monkeypatch.setattr(lc, "write_session_file", boom)
    with pytest.raises(OSError):
        BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    time.sleep(0.2)
    assert list((tmp_path / "run").iterdir()) == []
    # 不用 active_count()：全套运行时其他用例的守护线程会造成假阳性——按名断言
    assert not any(t.name == "bcx-io" and t.is_alive() for t in threading.enumerate())


def test_socket_is_0600_before_listen_and_session_publish(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_socket = lc.socket.socket
    real_publish = lc.write_session_file
    events = []

    class OrderingSocket(real_socket):
        def listen(self, backlog):
            socket_path = Path(self.getsockname())
            assert stat.S_IMODE(socket_path.stat().st_mode) == 0o600
            assert not (socket_path.parent / "session.json").exists()
            events.append("listen")
            return super().listen(backlog)

    def checked_publish(path, data, *, dir_fd=None):
        assert events == ["listen"]
        assert stat.S_IMODE(Path(data["socket_path"]).stat().st_mode) == 0o600
        assert any(t.name == "bcx-io" and t.is_alive()
                   for t in threading.enumerate())
        events.append("publish")
        return real_publish(path, data, dir_fd=dir_fd)

    monkeypatch.setattr(lc.socket, "socket", OrderingSocket)
    monkeypatch.setattr(lc, "write_session_file", checked_publish)
    session = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    try:
        assert events == ["listen", "publish"]
    finally:
        session.stop()


def test_failed_listen_closes_listener_and_leaves_no_published_artifacts(
        tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_socket = lc.socket.socket
    closed = False

    class ListenFailureSocket(real_socket):
        def listen(self, backlog):
            raise OSError("listen failed")

        def close(self):
            nonlocal closed
            closed = True
            super().close()

    monkeypatch.setattr(lc.socket, "socket", ListenFailureSocket)
    with pytest.raises(OSError, match="listen failed"):
        BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")

    assert closed
    assert list((tmp_path / "run").iterdir()) == []


def test_failed_start_retries_transient_listener_close(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_socket = lc.socket.socket
    created = []

    class ListenAndFirstCloseFailureSocket(real_socket):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0
            created.append(self)

        def listen(self, backlog):
            raise OSError("listen failed")

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("transient close failure")
            super().close()

    monkeypatch.setattr(lc.socket, "socket", ListenAndFirstCloseFailureSocket)
    with pytest.raises(OSError, match="listen failed"):
        BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")

    assert len(created) == 1
    assert created[0].close_calls == 2 and created[0].fileno() == -1
    assert list((tmp_path / "run").iterdir()) == []


def test_directory_fd_close_error_does_not_orphan_started_session(
        tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_close = lc.os.close
    close_calls = 0

    def close_then_fail_once(fd):
        nonlocal close_calls
        close_calls += 1
        real_close(fd)
        if close_calls == 1:
            raise OSError("post-close failure")

    monkeypatch.setattr(lc.os, "close", close_then_fail_once)
    session = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    try:
        assert close_calls >= 3
        assert (session.session_dir / "session.json").exists()
        assert session._listener is not None and session._io is not None
    finally:
        session.stop()


def test_bind_conflict_preserves_foreign_socket(tmp_path, monkeypatch):
    # 复审 R-02：socket 路径已被别人的活 listener 占用 → 启动失败，
    # 但**绝不能**删掉对方的 socket 文件（会造成对方拒绝服务）
    # 短路径：pytest tmp_path 会撞 macOS sun_path 104 字节上限
    foreign = Path(tempfile.mkdtemp(prefix="bcx-fgn-")) / "bridge.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(foreign))
    srv.listen(1)
    monkeypatch.setattr(BridgeSession, "_resolve_socket_path",
                        staticmethod(lambda session_dir: (foreign, None)))
    try:
        with pytest.raises(OSError):
            BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
        assert foreign.exists(), "外部 socket 被误删——DoS"
        probe = socket.socket(socket.AF_UNIX)   # 对方仍可被连接
        probe.settimeout(2.0)
        probe.connect(str(foreign))
        probe.close()
    finally:
        srv.close()
        foreign.unlink(missing_ok=True)
        foreign.parent.rmdir()


def test_stop_preserves_socket_replacement_at_owned_path(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    fallback = s._sock_tmpdir
    original_socket = s.socket_path.with_name("original.sock")
    s.socket_path.rename(original_socket)
    replacement = socket.socket(socket.AF_UNIX)
    replacement.bind(str(s.socket_path))
    replacement.listen(1)
    try:
        assert s.stop() is False
        assert s.socket_path.exists()
        assert s.session_dir.exists()
        assert (s.session_dir / "session.json").exists()
        probe = socket.socket(socket.AF_UNIX)
        probe.settimeout(1.0)
        probe.connect(str(s.socket_path))
        probe.close()
    finally:
        replacement.close()
        s.socket_path.unlink(missing_ok=True)
        original_socket.unlink(missing_ok=True)
        if fallback is not None and fallback.exists():
            fallback.rmdir()


def test_stop_preserves_replacement_session_directory(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    original = s.session_dir.with_name(s.session_dir.name + "-original")
    s.session_dir.rename(original)
    s.session_dir.mkdir(mode=0o700)
    try:
        assert s.stop() is False
        assert s.session_dir.exists(), "stop removed a replacement directory"
        assert (original / "session.json").exists()
    finally:
        for directory in (s.session_dir, original):
            if directory.exists():
                for child in directory.iterdir():
                    child.unlink(missing_ok=True)
                directory.rmdir()


def test_stop_reports_unknown_session_child_as_cleanup_incomplete(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    unknown = s.session_dir / "foreign.txt"
    unknown.write_text("preserve")
    try:
        assert s.stop() is False
        assert s.cleanup_complete is False
        assert unknown.read_text() == "preserve"
        assert s.session_dir.exists()
    finally:
        unknown.unlink(missing_ok=True)
        s.session_dir.rmdir()


def test_stop_runs_driver_hooks_between_transport_and_final_cleanup():
    events: list[str] = []
    s = BridgeSession.__new__(BridgeSession)
    s.stopped = False
    s.cleanup_complete = False
    s._cleanup_lock = threading.Lock()
    s._conns_lock = threading.Lock()
    s._conns = {}
    s._listener = None
    s._wake_r = None
    s._wake_w = None
    s._io = None
    s._wake = lambda: events.append("wake")
    s._join_io = lambda: events.append("join")
    s._close_all_conns = lambda: events.append("connections")
    s._close_listener = lambda: events.append("listener")
    s._drain_queue = lambda: events.append("queue")
    s._unlink_files = lambda: events.append("files")
    s._remove_dirs = lambda: events.append("dirs")

    s.stop(lambda: events.append("timer"), lambda: events.append("handlers"))

    assert events == ["wake", "join", "connections", "listener", "timer",
                      "handlers", "queue", "files", "dirs"]


def test_wake_storm_is_nonblocking_and_coalesced(tmp_path, monkeypatch):
    release_io = threading.Event()
    monkeypatch.setattr(BridgeSession, "_io_loop", lambda _: release_io.wait(2.0))
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    done = threading.Event()

    def storm() -> None:
        for _ in range(100_000):
            s._wake()
        done.set()

    worker = threading.Thread(target=storm, daemon=True)
    try:
        worker.start()
        assert done.wait(1.0), "wake storm blocked on the socketpair"
        assert s._wake_w is not None and not s._wake_w.getblocking()
        assert s._wake_r is not None and s._wake_r.recv(4096) == b"x"
    finally:
        release_io.set()
        if not done.is_set() and s._wake_r is not None:
            s._wake_r.close()       # unblock the pre-fix blocking sender
        s.stop()
        worker.join(timeout=1.0)
