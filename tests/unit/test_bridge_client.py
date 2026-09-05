import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest
from bridge.core.lifecycle import BridgeSession
from protocol import envelope, framing
from server.core.bridge_client import BridgeClient, BridgeError
from tests.unit.test_lifecycle import FakeReader


@pytest.fixture
def live(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    t = threading.Thread(target=lambda: _pump(s), daemon=True)
    t.start()
    yield s
    s.stop()


def _pump(s):
    while not s.stopped:
        time.sleep(s.tick(50))


def _session_dict(s: BridgeSession) -> dict:
    return {"socket_path": str(s.socket_path), "token": s.token,
            "instance_id": s.instance_id}


def test_ping_result(live):
    c = BridgeClient(_session_dict(live))
    r = c.call("ping")
    assert r["instance_id"] == live.instance_id
    assert r["envelope_version"] == 1


def test_unavailable_when_socket_missing(tmp_path):
    c = BridgeClient({"socket_path": str(tmp_path / "no.sock"), "token": "t"})
    with pytest.raises(BridgeError) as ei:
        c.call("ping")
    assert ei.value.code == "BRIDGE_UNAVAILABLE" and ei.value.retryable


def test_unavailable_when_auth_rejected(live):
    c = BridgeClient({"socket_path": str(live.socket_path), "token": "wrong"})
    with pytest.raises(BridgeError) as ei:
        c.call("ping")
    assert ei.value.code == "BRIDGE_UNAVAILABLE"     # 对端静默断开的对外表现（§5）


@pytest.mark.parametrize("timeout", [0.0, -1.0])
def test_nonpositive_budget_times_out_before_connect(tmp_path, timeout):
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-zero-"))
    sock_path = socket_dir / "unused.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(sock_path))
    server.listen(1)
    server.settimeout(0.1)
    accepted = threading.Event()

    def accept_once():
        try:
            conn, _ = server.accept()
        except socket.timeout:
            return
        else:
            accepted.set()
            conn.close()

    worker = threading.Thread(target=accept_once, daemon=True)
    worker.start()
    started = time.monotonic()
    try:
        client = BridgeClient({"socket_path": str(sock_path), "token": "t"})
        with pytest.raises(BridgeError) as exc:
            client.call("ping", timeout=timeout)
        assert exc.value.code == envelope.BRIDGE_TIMEOUT
        assert time.monotonic() - started < 0.1
        worker.join(timeout=0.2)
        assert not worker.is_alive() and not accepted.is_set()
    finally:
        server.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


def test_error_frame_maps_to_bridge_error(live):
    c = BridgeClient(_session_dict(live))
    with pytest.raises(BridgeError) as ei:
        c.call("no_such_method")
    assert ei.value.code == "UNKNOWN_METHOD"


@pytest.mark.parametrize("poll", [False, True])
def test_slow_drip_respects_total_deadline(poll):
    # audit F-02：对端每 20ms 滴 1 字节。逐次 settimeout 会被无限续命；
    # 总 deadline 必须在 ~0.3s 止损（滴完整帧需 ~1.2s）
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-"))
    sock_path = socket_dir / "drip.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        while not buf.feed(conn.recv(65536)):
            pass
        resp = envelope.ok_frame("x", {"pong": True})
        try:
            for i in range(len(resp)):
                conn.send(resp[i:i + 1])
                time.sleep(0.02)
        except OSError:
            pass
        conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    c = BridgeClient({"socket_path": str(sock_path), "token": "t"})
    t0 = time.monotonic()
    with pytest.raises(BridgeError) as ei:
        c.call("ping", timeout=0.3, check_cancelled=(lambda: None) if poll else None)
    elapsed = time.monotonic() - t0
    try:
        assert ei.value.code == "BRIDGE_TIMEOUT"
        assert elapsed < 1.0
    finally:
        srv.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


def test_absolute_deadline_precedes_relative_timeout(live, monkeypatch):
    import server.core.bridge_client as client_module

    real_decode = client_module.envelope.decode_response

    def slow_decode(payload):
        time.sleep(0.25)
        return real_decode(payload)

    monkeypatch.setattr(client_module.envelope, "decode_response", slow_decode)
    started = time.monotonic()
    with pytest.raises(BridgeError) as exc:
        BridgeClient(_session_dict(live)).call(
            "ping", timeout=2.0, deadline=started + 0.2)
    assert exc.value.code == envelope.BRIDGE_TIMEOUT
    assert time.monotonic() - started < 0.6

    class Socket:
        def settimeout(self, timeout):
            if timeout < 0:
                raise ValueError(timeout)
            self.timeout = timeout

    monotonic = iter([10.0, 10.1])
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(monotonic))
    client = Socket()
    BridgeClient._set_deadline(client, 10.05)
    assert client.timeout == pytest.approx(0.05)
    monkeypatch.setattr(client_module.time, "monotonic", lambda: 10.1)
    with pytest.raises(BridgeError) as exc:
        BridgeClient._set_deadline(client, 10.05)
    assert exc.value.code == envelope.BRIDGE_TIMEOUT


def test_call_sends_remaining_budget_to_bridge():
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-budget-"))
    sock_path = socket_dir / "budget.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(sock_path))
    server.listen(1)
    observed: list[int | None] = []

    def serve() -> None:
        conn, _ = server.accept()
        try:
            frames: list[bytes] = []
            buffer = framing.FrameBuffer()
            while not frames:
                frames = buffer.feed(conn.recv(65536))
            request = envelope.decode_request(frames[0])
            observed.append(request.budget_ms)
            conn.sendall(envelope.ok_frame(request.id, {}))
        finally:
            conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        result = BridgeClient({"socket_path": str(sock_path), "token": "t"}).call(
            "ping", timeout=0.2)
        assert result == {}
        assert observed and observed[0] is not None
        assert 0 < observed[0] <= 200
    finally:
        server.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


MISSING_VERSION = object()


@pytest.mark.parametrize("version,id_matches,expected", [
    (envelope.ENVELOPE_VERSION + 1, True, envelope.ENVELOPE_VERSION_MISMATCH),
    (True, True, envelope.BRIDGE_UNAVAILABLE),
    ("1", True, envelope.BRIDGE_UNAVAILABLE),
    (MISSING_VERSION, True, envelope.BRIDGE_UNAVAILABLE),
    (envelope.ENVELOPE_VERSION, False, envelope.BRIDGE_UNAVAILABLE),
])
def test_response_version_and_id_must_match_request(version, id_matches, expected):
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-"))
    sock_path = socket_dir / "mismatch.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        frames = []
        while not frames:
            frames = buf.feed(conn.recv(65536))
        req = envelope.decode_request(frames[0])
        body = {"id": req.id if id_matches else "wrong-id", "ok": True, "result": {}}
        if version is not MISSING_VERSION:
            body["v"] = version
        conn.sendall(framing.encode_frame(json.dumps(body).encode()))
        conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        client = BridgeClient({"socket_path": str(sock_path), "token": "t"})
        with pytest.raises(BridgeError) as ei:
            client.call("ping")
        assert ei.value.code == expected
        assert ei.value.retryable is (expected == envelope.BRIDGE_UNAVAILABLE)
    finally:
        srv.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


@pytest.mark.parametrize("response_cases", [
    [{"ok": "false", "result": {}}],
    [{"ok": False, "error": "not-an-object"}],
    [
        {"ok": True, "result": []},
        {"ok": True, "result": {}, "error": {"code": "X", "message": "x", "retryable": False}},
        {"ok": False, "error": {"code": "X", "message": "x", "retryable": False}, "result": {}},
        {"ok": True, "result": {}, "unexpected": None},
    ],
])
def test_malformed_response_shape_maps_to_bridge_unavailable(response_cases):
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-"))
    sock_path = socket_dir / "malformed.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        for response_fields in response_cases:
            conn, _ = srv.accept()
            buf = framing.FrameBuffer()
            frames = []
            while not frames:
                frames = buf.feed(conn.recv(65536))
            req = envelope.decode_request(frames[0])
            body = {"v": envelope.ENVELOPE_VERSION, "id": req.id, **response_fields}
            conn.sendall(framing.encode_frame(json.dumps(body).encode()))
            conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        client = BridgeClient({"socket_path": str(sock_path), "token": "t"})
        for _ in response_cases:
            with pytest.raises(BridgeError) as exc:
                client.call("ping")
            assert exc.value.code == envelope.BRIDGE_UNAVAILABLE
            assert exc.value.retryable is True
    finally:
        srv.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


@pytest.mark.parametrize("stage", ["connect", "connecting", "send"])
def test_cancellation_interrupts_socket_stalls(stage, monkeypatch):
    import asyncio
    import errno

    import server.core.bridge_client as client_module

    cancelled_at = time.monotonic() + 0.1
    closed = []

    def check_cancelled():
        if time.monotonic() >= cancelled_at:
            raise asyncio.CancelledError()

    class StalledSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            closed.append(True)

        def settimeout(self, timeout):
            self.timeout = timeout

        def setblocking(self, blocking):
            self.timeout = None if blocking else 0

        def connect(self, _path):
            if stage == "connecting":
                raise BlockingIOError(errno.EINPROGRESS, "connecting")
            if stage == "connect":
                if self.timeout == 0:
                    raise BlockingIOError(errno.EAGAIN, "backlog full")
                time.sleep(min(self.timeout, 0.5))
                raise socket.timeout()

        def sendall(self, _data):
            time.sleep(min(self.timeout, 0.5))
            raise socket.timeout()

        def send(self, _data):
            time.sleep(min(self.timeout, 0.5))
            raise socket.timeout()

    class PendingSelector:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def register(self, *_args):
            pass

        def select(self, timeout):
            time.sleep(timeout)
            return []

    monkeypatch.setattr(client_module.selectors, "DefaultSelector", PendingSelector)
    monkeypatch.setattr(client_module.socket, "socket", lambda *_args: StalledSocket())
    client = BridgeClient({"socket_path": "unused", "token": "t"})
    with pytest.raises(asyncio.CancelledError):
        client.call("scene_summary", check_cancelled=check_cancelled)
    assert time.monotonic() - cancelled_at < 0.3
    assert closed == [True]


def test_polling_preserves_partial_send_and_receive_frames():
    sent = bytearray()
    response = envelope.ok_frame("request", {"pong": True})

    class FragmentedSocket:
        sends = 0
        receives = 0

        def settimeout(self, timeout):
            assert 0 < timeout <= 0.05

        def send(self, pending):
            self.sends += 1
            if self.sends == 2:
                raise socket.timeout()
            chunk = pending[:3]
            sent.extend(chunk)
            return len(chunk)

        def recv(self, _size):
            self.receives += 1
            if self.receives == 1:
                return response[:3]
            if self.receives == 2:
                raise socket.timeout()
            return response[3:]

    client = FragmentedSocket()
    deadline = time.monotonic() + 1
    BridgeClient._send(client, b"complete-request-frame", deadline, lambda: None)
    assert sent == b"complete-request-frame"
    payload = BridgeClient._receive(client, deadline, lambda: None)
    assert envelope.decode_response(payload)["result"] == {"pong": True}


@pytest.mark.parametrize("cancel", [False, True])
def test_real_full_uds_backlog_fails_or_remains_cancellable_and_deadline_bound(cancel):
    import asyncio
    import errno

    with tempfile.TemporaryDirectory(prefix="bcx-backlog-") as directory:
        path = str(Path(directory) / "bridge.sock")
        fillers = []
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(path)
            server.listen(1)
            try:
                # Linux can report EAGAIN; macOS can refuse excess UDS connections.
                for _ in range(10):
                    filler = socket.socket(socket.AF_UNIX)
                    fillers.append(filler)
                    filler.setblocking(False)
                    result = filler.connect_ex(path)
                    if result in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS,
                                  errno.ECONNREFUSED):
                        break
                    assert result == 0
                else:
                    pytest.fail("could not fill UDS backlog")
                started = time.monotonic()

                def check_cancelled():
                    if time.monotonic() - started >= 0.1:
                        raise asyncio.CancelledError()

                client = BridgeClient({"socket_path": path, "token": "t"})
                if result == errno.ECONNREFUSED:
                    with pytest.raises(BridgeError) as exc:
                        client.call("scene_summary", check_cancelled=check_cancelled if cancel else None)
                    assert exc.value.code == envelope.BRIDGE_UNAVAILABLE
                elif cancel:
                    with pytest.raises(asyncio.CancelledError):
                        client.call("scene_summary", check_cancelled=check_cancelled)
                else:
                    with pytest.raises(BridgeError) as exc:
                        client.call("scene_summary", timeout=0.15)
                    assert exc.value.code == envelope.BRIDGE_TIMEOUT
                assert time.monotonic() - started < 0.5
            finally:
                for filler in fillers:
                    filler.close()
