"""Real SDK stdio cancellation must retire synchronous UDS work before its deadline."""
import json
import threading
import time

from bridge.core.lifecycle import BridgeSession
from tests.contract.fake_bridge import FakeSceneReader
from tests.contract.test_server_process import (
    CODEX_PROTOCOL, INITIALIZED, _read_until, _send, _spawn, _stop,
)


def test_stdio_cancellation_closes_readers_and_releases_summary_slots(tmp_path):
    started = []
    closed = []

    class YieldingReader(FakeSceneReader):
        def snapshot_steps(self, **kwargs):
            call = len(started)
            started.append(call)
            try:
                if call >= 2:
                    return (yield from super().snapshot_steps(**kwargs))
                while True:
                    time.sleep(0.005)
                    yield
            finally:
                closed.append(call)

    session = BridgeSession.start(tmp_path, YieldingReader(), blender_version="5.2.0")
    stop = threading.Event()

    def pump():
        while not stop.is_set() and not session.stopped:
            time.sleep(session.tick(50))

    worker = threading.Thread(target=pump)
    worker.start()
    server = _spawn(tmp_path)

    def call(request_id):
        _send(server, {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                       "params": {"name": "get_scene_summary",
                                  "arguments": {"instance_id": session.instance_id}}})

    def audit_rows():
        return [json.loads(line) for path in (tmp_path / "logs").glob("*.jsonl")
                for line in path.read_text().splitlines()]

    try:
        _send(server, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"protocolVersion": CODEX_PROTOCOL, "capabilities": {},
                                  "clientInfo": {"name": "cancellation-test", "version": "1"}}})
        _read_until(server, 1, time.monotonic() + 5)
        _send(server, INITIALIZED)
        call(2)
        call(3)
        deadline = time.monotonic() + 2
        while len(started) < 2 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(started) == 2
        cancelled_at = time.monotonic()
        for request_id in (2, 3, 2, 3):  # duplicate notifications are harmless
            _send(server, {"jsonrpc": "2.0", "method": "notifications/cancelled",
                           "params": {"requestId": request_id, "reason": "test cancellation"}})
        deadline = cancelled_at + 2
        while (len(closed) < 2 or len(audit_rows()) < 2) and time.monotonic() < deadline:
            time.sleep(0.005)
        assert sorted(closed) == [0, 1], "cancelled readers retained until the method deadline"
        rows = audit_rows()
        assert sorted(row["request_id"] for row in rows) == [2, 3]
        assert all(row["ok"] is False and row["error"] == "CancelledError" for row in rows)
        call(4)
        response, _ = _read_until(server, 4, deadline)
        assert response["result"]["isError"] is False
        assert response["result"]["structuredContent"]["instance_id"] == session.instance_id
        # A late cancellation cannot add another audit or affect the next request.
        _send(server, {"jsonrpc": "2.0", "method": "notifications/cancelled",
                       "params": {"requestId": 4}})
        call(5)
        response, _ = _read_until(server, 5, time.monotonic() + 2)
        assert response["result"]["isError"] is False
        rows = audit_rows()
        assert sorted(row["request_id"] for row in rows) == [2, 3, 4, 5]
        assert sum(row["ok"] is True for row in rows) == 2
        # Graceful EOF must finish every SDK worker; killing a stuck process is a failure.
        server.stdin.close()
        assert server.wait(timeout=3) == 0
    finally:
        _stop(server)
        stop.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert session.stop()
        assert session._io is None or not session._io.is_alive()
