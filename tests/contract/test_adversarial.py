import json
import logging
import socket
import stat
import threading
import time

import pytest

from protocol import envelope, framing
from server.core.bridge_client import BridgeClient, BridgeError
from server.core.discovery import Discovery
from tests.contract.fake_bridge import live_bridge


def _client(s) -> BridgeClient:
    return BridgeClient({"socket_path": str(s.socket_path), "token": s.token})


def test_five_mib_payload_roundtrip(tmp_path):
    # 至少 5 MiB 的 scene-summary 响应走完整链路无截断（URS 验收）
    with live_bridge(tmp_path, n_collections=700_000) as (s, reader, run):
        result = _client(s).call("scene_summary", timeout=30.0)
        assert len(result["summary"]["collections"]) == 700_000
        assert len(envelope.ok_frame("size-check", result)) - 4 >= 5 * 1024 * 1024


def test_oversize_response_degrades_to_limit_error(tmp_path):
    with live_bridge(tmp_path, n_collections=2_200_000) as (s, reader, run):  # >16 MiB
        with pytest.raises(BridgeError) as exc_info:
            _client(s).call("scene_summary", timeout=30.0)
        assert exc_info.value.code == envelope.INTERNAL_LIMIT_EXCEEDED


def test_excluding_huge_collections_crops_before_frame_limit(tmp_path):
    # 2.2M names would exceed 16 MiB. false 必须贯穿 UDS params 并在 reader 源端跳过枚举。
    with live_bridge(tmp_path, n_collections=2_200_000) as (s, reader, run):
        result = _client(s).call(
            "scene_summary",
            {"include_collections": False, "include_managed_objects": False},
            timeout=5.0,
        )
        assert result["summary"]["collections"] == []
        assert result["summary"]["managed_objects"] == []


def test_reader_exception_maps_to_scene_query_failed(tmp_path):
    with live_bridge(tmp_path, raise_on_snapshot=RuntimeError("boom")) as (s, reader, run):
        with pytest.raises(BridgeError) as exc_info:
            _client(s).call("scene_summary")
        assert exc_info.value.code == envelope.SCENE_QUERY_FAILED
        assert "boom" not in str(exc_info.value)  # 异常文本不出境（§5）


def test_concurrent_clients_all_served(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        results, errors = [], []

        def one():
            try:
                results.append(_client(s).call("ping")["instance_id"])
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=one) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert all(not thread.is_alive() for thread in threads)
        assert not errors and results == [s.instance_id] * 8


def test_permissions_at_rest(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        assert stat.S_IMODE(s.session_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(s.socket_path.stat().st_mode) == 0o600
        assert stat.S_IMODE((s.session_dir / "session.json").stat().st_mode) == 0o600


def test_tokenless_connection_closed_silently(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2.0)
            client.connect(str(s.socket_path))
            request = envelope.Request(id="x", token="", method="ping", params={})
            client.sendall(envelope.encode_request(request))
            assert client.recv(1) == b""  # 断开、无响应帧（§5）


def test_pipeline_busy_and_reply_frames_never_interleave(tmp_path):
    # 单连接流水线下 BUSY（I/O 入 outbox）与正常响应（tick 入 outbox）先后在途。
    with live_bridge(tmp_path) as (s, reader, run):
        s.pause_pump()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(15.0)
            client.connect(str(s.socket_path))
            request_count = 100  # 容量 64 → 至少 36 个 BUSY
            for _ in range(request_count):
                client.sendall(envelope.encode_request(envelope.Request.new(s.token, "ping", {})))
            time.sleep(0.3)
            s.resume_pump()
            buffer = framing.FrameBuffer()
            frames: list[bytes] = []
            while len(frames) < request_count:
                data = client.recv(65536)
                assert data, f"connection closed after {len(frames)} frames"
                frames.extend(buffer.feed(data))  # 抛异常 = 帧交错/损坏
        bodies = [json.loads(frame) for frame in frames]
        busy = [body for body in bodies
                if not body["ok"] and body["error"]["code"] == envelope.BRIDGE_BUSY]
        ok = [body for body in bodies if body["ok"]]
        assert len(busy) + len(ok) == request_count and busy and ok


def test_serialization_failure_becomes_scene_query_failed(tmp_path):
    # tick 护栏兜底：信封序列化失败 → 结构化错误帧，后续请求仍可服务。
    class Unserializable:
        pass

    with live_bridge(tmp_path) as (s, reader, run):
        original = reader.snapshot_steps

        def bad(**kwargs):
            snapshot = yield from original(**kwargs)
            return snapshot.__class__(**{**snapshot.__dict__, "scene_name": Unserializable()})

        reader.snapshot_steps = bad  # type: ignore[method-assign]
        try:
            with pytest.raises(BridgeError) as exc_info:
                _client(s).call("scene_summary")
            assert exc_info.value.code == envelope.SCENE_QUERY_FAILED
        finally:
            reader.snapshot_steps = original  # type: ignore[method-assign]
        assert _client(s).call("ping")["instance_id"] == s.instance_id


def test_unregister_recovers_n_connections(tmp_path):
    # 建立 N 条连接后 stop()，全部立即收到关闭而非超时（§3.7 第 4 步）。
    with live_bridge(tmp_path) as (s, reader, run):
        connections = []
        try:
            for _ in range(5):
                client = socket.socket(socket.AF_UNIX)
                client.settimeout(3.0)
                client.connect(str(s.socket_path))
                connections.append(client)
            time.sleep(0.3)  # 等 I/O accept 完，避免连接留在 backlog
            s.stop()
            for client in connections:
                assert client.recv(1) == b""
        finally:
            for client in connections:
                client.close()


def test_auth_failure_logged(tmp_path, caplog):
    # URS §10.1：「无 token 连接被拒并记日志」。
    with live_bridge(tmp_path) as (s, reader, run):
        with caplog.at_level(logging.INFO, logger="bcx.bridge"):
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(2.0)
                client.connect(str(s.socket_path))
                client.sendall(envelope.encode_request(envelope.Request.new("bad", "ping", {})))
                assert client.recv(1) == b""
        assert any("auth failed" in record.message for record in caplog.records)


def test_outbox_limit_drops_non_reading_client(tmp_path, monkeypatch):
    # MAX_OUTBOX 调小以免真搬 32 MiB；拒不读取客户端必须被断开且 tick 不受阻。
    from bridge.core import lifecycle

    monkeypatch.setattr(lifecycle, "MAX_OUTBOX", 256 * 1024)
    with live_bridge(tmp_path, n_collections=20_000) as (s, reader, run):
        with socket.socket(socket.AF_UNIX) as greedy:
            greedy.connect(str(s.socket_path))
            for _ in range(32):  # 32 × ~160 KiB 远超 256 KiB 上限
                greedy.sendall(envelope.encode_request(
                    envelope.Request.new(s.token, "scene_summary", {})))
            time.sleep(2.0)
            greedy.settimeout(20.0)
            dropped = False
            deadline = time.monotonic() + 20.0
            while time.monotonic() < deadline:
                try:
                    if greedy.recv(1 << 16) == b"":
                        dropped = True
                        break
                except ConnectionResetError:
                    dropped = True
                    break
        assert dropped, "拒不读取的客户端未被 outbox 上限断开"
        assert _client(s).call("ping")["instance_id"] == s.instance_id


def test_envelope_mismatch_reported_not_cleaned(tmp_path):
    # 手工 mini-bridge：ping 回 envelope_version=2。
    instance_id = f"gui-1-{tmp_path.stat().st_ino & 0xffffffff:08x}"
    runtime = tmp_path / "run"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    run = runtime / instance_id
    run.mkdir(mode=0o700)
    run.chmod(0o700)
    socket_dir = Discovery._fallback_dir(instance_id)
    assert socket_dir is not None
    socket_dir.mkdir(mode=0o700)
    socket_dir.chmod(0o700)
    socket_path = socket_dir / "bridge.sock"  # 短路径防 sun_path 104B
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(socket_path))
    server.listen(1)
    socket_path.chmod(0o600)
    dir_stat, socket_stat = socket_dir.stat(), socket_path.stat()

    def serve():
        try:
            with server.accept()[0] as connection:
                buffer = framing.FrameBuffer()
                frames: list[bytes] = []
                while not frames:
                    frames = buffer.feed(connection.recv(65536))
                request = envelope.decode_request(frames[0])
                connection.sendall(framing.encode_frame(json.dumps({
                    "v": 2, "id": request.id, "ok": True,
                    "result": {"instance_id": instance_id, "bridge_version": "9.9",
                               "blender_version": "5.2.0", "envelope_version": 2},
                }).encode()))
        except OSError:
            pass  # cleanup can close a still-blocked listener after an assertion failure

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    session_file = run / "session.json"
    session_file.write_text(json.dumps({
        "instance_id": instance_id, "token": "t", "pid": 1,  # pid 1 恒存活 → 不清理
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "9.9", "envelope_version": 2, "socket_external": True,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": dir_stat.st_dev, "socket_dir_ino": dir_stat.st_ino,
    }))
    session_file.chmod(0o600)
    try:
        instances = Discovery(runtime).instances()
        assert len(instances) == 1
        assert instances[0].envelope_mismatch is True
        assert instances[0].state == "disconnected"
        assert run.exists()  # 话不投机 ≠ 死实例（§4.3）
    finally:
        server.close()
        thread.join(timeout=1.0)
        assert not thread.is_alive()
        socket_path.unlink(missing_ok=True)
        socket_dir.rmdir()


def test_bridge_kill_then_restart_recovers(tmp_path):
    now = [0.0]
    discovery = Discovery(tmp_path / "run", ttl=1.0, clock=lambda: now[0])
    with live_bridge(tmp_path) as (s, reader, run):
        assert discovery.instances()[0].state == "connected"
    now[0] = 2.0
    assert discovery.instances() == []
    with live_bridge(tmp_path) as (s2, reader2, run2):
        now[0] = 4.0
        assert discovery.instances()[0].session["instance_id"] == s2.instance_id
