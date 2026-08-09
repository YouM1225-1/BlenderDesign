# tests/unit/test_adapter.py
import asyncio
import hashlib
import json
import threading
import time

import pytest
from server.core.audit import AuditLog
from server.core.discovery import Instance, ScanStats
from server.mcp.adapter import (GUIDANCE, ToolFailure, capabilities_impl,
                                scene_summary_impl, status_impl)


class FakeClient:
    def __init__(self, results: dict):
        self._r = results

    def call(self, method, params=None, timeout=None, *, deadline=None):
        return self._r[method]


class FakeDiscovery:
    def __init__(self, insts, partial=False, skipped=0):
        self._i = insts
        self.last_scan = ScanStats(partial=partial, skipped_count=skipped)
        self.invalidated = False
        self.invalidate_deadline = None

    def instances(self, force=False, deadline=None):
        return self._i

    def instances_with_stats(self, force=False, deadline=None):
        return self.instances(force=force, deadline=deadline), self.last_scan

    def find(self, instance_id, deadline=None):
        return next((i for i in self._i
                     if i.session["instance_id"] == instance_id), None)

    def find_with_stats(self, instance_id, deadline=None):
        return self.find(instance_id, deadline=deadline), self.last_scan

    def invalidate(self, deadline=None):
        self.invalidated = True
        self.invalidate_deadline = deadline
        return True


def make_inst(iid="gui-1-aa", state="connected", supported=True, warning=None,
              client=None, mismatch=False):
    return Instance(session={"instance_id": iid, "pid": 1, "blender_version": "5.2.0",
                             "bridge_version": "0.1.0"},
                    state=state, blender_supported=supported, version_warning=warning,
                    client=client, envelope_mismatch=mismatch)


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "logs")


def test_status_empty_returns_guidance():
    out = status_impl(FakeDiscovery([]))
    assert out == {"ok": True, "guidance": GUIDANCE, "partial": False,
                   "skipped_count": 0, "instances": []}


def test_status_surfaces_partial_metadata_at_top_level():
    # 复审 P2：partial 是顶层元数据，不再伪装成 id 为 __partial__ 的假实例
    out = status_impl(FakeDiscovery([], partial=True, skipped=7))
    assert out["partial"] is True and out["skipped_count"] == 7
    assert all(r["instance_id"] != "__partial__" for r in out["instances"])


def test_status_uses_stats_paired_with_its_instance_snapshot():
    d = FakeDiscovery([])
    d.instances_with_stats = lambda **_kwargs: ([], ScanStats(True, 3))
    out = status_impl(d)
    assert out["partial"] is True and out["skipped_count"] == 3


def test_status_selector_no_match_is_guidance_not_error():
    d = FakeDiscovery([make_inst(client=FakeClient({"status": {}}))])
    out = status_impl(d, instance_selector="gui-9-zz")
    assert out["ok"] is True and out["instances"] == [] and out["guidance"] == GUIDANCE


def test_status_disconnected_rows_still_return_guidance():
    out = status_impl(FakeDiscovery([make_inst(state="disconnected", client=None)]))
    assert out["instances"][0]["bridge_state"] == "disconnected"
    assert out["guidance"] == GUIDANCE


def test_status_enriches_from_bridge():
    c = FakeClient({"status": {"instance_id": "gui-1-aa", "scene_path": "/tmp/x.blend",
                               "scene_revision": 4}})
    out = status_impl(FakeDiscovery([make_inst(client=c)]))
    row = out["instances"][0]
    assert row["bridge_state"] == "connected"
    assert row["scene_path"] == "/tmp/x.blend" and row["scene_revision"] == 4
    assert row["blender_supported"] is True and row["version_warning"] is None


def test_status_per_instance_timeout_is_capped_at_method_budget():
    class CapturingClient:
        def __init__(self):
            self.timeout = None

        def call(self, method, params=None, timeout=None, *, deadline=None):
            self.timeout = timeout
            return {"instance_id": "gui-1-aa", "scene_path": None,
                    "scene_revision": 0}

    client = CapturingClient()
    status_impl(FakeDiscovery([make_inst(client=client)]))
    assert client.timeout is not None
    assert 0 < client.timeout <= 2.0


def test_status_preserves_bridge_busy_state():
    from server.core.bridge_client import BridgeError

    class BusyClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            raise BridgeError("BRIDGE_BUSY", "queue full", retryable=True)

    out = status_impl(FakeDiscovery([make_inst(client=BusyClient())]))
    assert out["instances"][0]["bridge_state"] == "busy"


def test_status_nonbusy_failure_overrides_stale_busy_snapshot():
    from server.core.bridge_client import BridgeError

    class GoneClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            raise BridgeError("BRIDGE_UNAVAILABLE", "gone", retryable=True)

    discovery = FakeDiscovery([make_inst(state="busy", client=GoneClient())])
    out = status_impl(discovery)
    assert out["instances"][0]["bridge_state"] == "disconnected"
    assert out["guidance"] == GUIDANCE
    assert discovery.invalidated is True


def test_status_isolates_unexpected_client_failure():
    class BadClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            raise RuntimeError("private bridge detail")

    class GoodClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            return {"instance_id": "gui-2-deadbeef", "scene_path": None,
                    "scene_revision": 3}

    discovery = FakeDiscovery([
        make_inst(iid="gui-1-deadbeef", client=BadClient()),
        make_inst(iid="gui-2-deadbeef", client=GoodClient()),
    ])
    out = status_impl(discovery)
    rows = {row["instance_id"]: row for row in out["instances"]}
    assert rows["gui-1-deadbeef"]["bridge_state"] == "disconnected"
    assert rows["gui-2-deadbeef"]["bridge_state"] == "connected"
    assert out["partial"] is False
    assert discovery.invalidated is True


def test_status_isolates_malformed_client_payload():
    class BadClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            return {"instance_id": "gui-3-deadbeef", "scene_revision": 4}

    class GoodClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            return {"instance_id": "gui-4-deadbeef", "scene_path": None,
                    "scene_revision": 4}

    discovery = FakeDiscovery([
        make_inst(iid="gui-3-deadbeef", client=BadClient()),
        make_inst(iid="gui-4-deadbeef", client=GoodClient()),
    ])
    out = status_impl(discovery)
    rows = {row["instance_id"]: row for row in out["instances"]}
    assert rows["gui-3-deadbeef"]["bridge_state"] == "disconnected"
    assert rows["gui-4-deadbeef"]["bridge_state"] == "connected"
    assert out["partial"] is False
    assert discovery.invalidated is True


def test_status_rejects_cross_instance_payload_without_hiding_healthy_instance():
    class WrongInstanceClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            return {"instance_id": "gui-6-deadbeef", "scene_path": "/wrong.blend",
                    "scene_revision": 7}

    class GoodClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            return {"instance_id": "gui-6-deadbeef", "scene_path": None,
                    "scene_revision": 8}

    discovery = FakeDiscovery([
        make_inst(iid="gui-5-deadbeef", client=WrongInstanceClient()),
        make_inst(iid="gui-6-deadbeef", client=GoodClient()),
    ])
    out = status_impl(discovery)
    rows = {row["instance_id"]: row for row in out["instances"]}
    assert rows["gui-5-deadbeef"]["bridge_state"] == "disconnected"
    assert rows["gui-5-deadbeef"]["scene_path"] is None
    assert rows["gui-6-deadbeef"]["bridge_state"] == "connected"
    assert rows["gui-6-deadbeef"]["scene_revision"] == 8
    assert discovery.invalidated is True


def test_status_uses_one_end_to_end_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class SlowClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            time.sleep(0.4)  # 故意不尊重局部 timeout
            return {}

    class SlowDiscovery(FakeDiscovery):
        def instances(self, force=False, deadline=None):
            time.sleep(0.12)
            return self._i

    monkeypatch.setattr(adapter, "OVERALL_BUDGET", 0.2)
    d = SlowDiscovery([make_inst(client=SlowClient())])
    t0 = time.monotonic()
    out = status_impl(d)
    assert time.monotonic() - t0 < 0.3
    assert out["instances"][0]["bridge_state"] == "disconnected"
    assert d.invalidated is True


def test_status_submit_overhead_stays_inside_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class SlowSubmitExecutor(adapter.ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            time.sleep(0.15)
            return super().submit(*args, **kwargs)

    class SlowClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            time.sleep(0.4)
            return {}

    monkeypatch.setattr(adapter, "OVERALL_BUDGET", 0.2)
    executor = SlowSubmitExecutor(max_workers=8)
    monkeypatch.setattr(adapter, "_STATUS_EXECUTOR", executor)
    try:
        started = time.monotonic()
        out = status_impl(FakeDiscovery([make_inst(client=SlowClient())]))
        assert time.monotonic() - started < 0.3
        assert out["instances"][0]["bridge_state"] == "disconnected"
    finally:
        executor.shutdown(wait=True)


def test_status_stops_submitting_instances_at_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class SlowSubmitExecutor(adapter.ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            time.sleep(0.03)
            return super().submit(*args, **kwargs)

    instances = [make_inst(iid=f"gui-{index + 1}-deadbeef",
                           client=FakeClient({"status": {}}))
                 for index in range(16)]
    monkeypatch.setattr(adapter, "OVERALL_BUDGET", 0.2)
    executor = SlowSubmitExecutor(max_workers=8)
    monkeypatch.setattr(adapter, "_STATUS_EXECUTOR", executor)
    try:
        started = time.monotonic()
        out = status_impl(FakeDiscovery(instances))
        assert time.monotonic() - started < 0.35
        assert out["partial"] is True and out["skipped_count"] > 0
    finally:
        executor.shutdown(wait=True)


def test_concurrent_status_calls_have_one_bounded_aggregation_pool():
    active = 0
    peak = 0
    counter_lock = threading.Lock()

    class TrackingClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            nonlocal active, peak
            with counter_lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.02)
                return {"scene_path": None, "scene_revision": 0}
            finally:
                with counter_lock:
                    active -= 1

    instances = [make_inst(iid=f"gui-{index + 1}-deadbeef", client=TrackingClient())
                 for index in range(16)]
    discovery = FakeDiscovery(instances)
    start = threading.Barrier(12)
    results = []

    def call_status():
        start.wait()
        results.append(status_impl(discovery))

    workers = [threading.Thread(target=call_status) for _ in range(12)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=4.0)

    assert all(not worker.is_alive() for worker in workers)
    assert len(results) == 12
    assert peak <= 8


def test_scene_summary_injects_server_fields():
    c = FakeClient({"scene_summary": {"scene_hash": "sha256:x", "scene_name": "S",
                                      "scene_revision": 1, "scene_path": None,
                                      "units": {"system": "NONE", "scale_length": 1.0},
                                      "summary": {"object_count": 0, "mesh_count": 0,
                                                  "camera_count": 0, "light_count": 0,
                                                  "collections": ["C"],
                                                  "managed_objects": []}}})
    out = scene_summary_impl(FakeDiscovery([make_inst(client=c, supported=False,
                                                      warning="w")]), "gui-1-aa")
    assert out["instance_id"] == "gui-1-aa"
    assert out["version_warning"] == "w"          # 非基线：只读放行 + 警告（§4.4）


def test_scene_summary_error_mapping():
    with pytest.raises(ToolFailure) as e1:
        scene_summary_impl(FakeDiscovery([]), "gui-9-zz")
    assert e1.value.code == "INSTANCE_NOT_FOUND"
    with pytest.raises(ToolFailure) as partial:
        scene_summary_impl(FakeDiscovery([], partial=True, skipped=1), "gui-9-zz")
    assert partial.value.code == "BRIDGE_UNAVAILABLE"
    assert partial.value.retryable is True
    with pytest.raises(ToolFailure) as e2:
        scene_summary_impl(FakeDiscovery([make_inst(client=None, mismatch=True,
                                                    warning="envelope v2 != v1")]),
                           "gui-1-aa")
    assert e2.value.code == "ENVELOPE_VERSION_MISMATCH"
    with pytest.raises(ToolFailure) as e3:
        scene_summary_impl(FakeDiscovery([make_inst(state="disconnected", client=None)]),
                           "gui-1-aa")
    assert e3.value.code == "BRIDGE_UNAVAILABLE" and e3.value.retryable is True


def test_scene_summary_uses_stats_paired_with_its_instance_snapshot():
    d = FakeDiscovery([])
    d.find_with_stats = lambda *_args, **_kwargs: (None, ScanStats(True, 1))
    with pytest.raises(ToolFailure) as exc:
        scene_summary_impl(d, "gui-9-zz")
    assert exc.value.code == "BRIDGE_UNAVAILABLE"


def test_scene_summary_uses_one_end_to_end_deadline(monkeypatch):
    import server.mcp.adapter as adapter
    from server.core.bridge_client import BridgeError

    class SlowClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            time.sleep(timeout if timeout is not None else 0.25)
            raise BridgeError("BRIDGE_TIMEOUT", method, retryable=True)

    class SlowDiscovery(FakeDiscovery):
        def find(self, instance_id, deadline=None):
            time.sleep(0.06)
            return self._i[0]

    monkeypatch.setattr(adapter, "SCENE_SUMMARY_BUDGET", 0.1)
    started = time.monotonic()
    with pytest.raises(ToolFailure) as exc:
        scene_summary_impl(SlowDiscovery([make_inst(client=SlowClient())]), "gui-1-aa")
    assert exc.value.code == "BRIDGE_TIMEOUT"
    assert time.monotonic() - started < 0.18


def test_scene_summary_preserves_busy_retryability():
    from server.core.bridge_client import BridgeError

    class BusyClient:
        def call(self, method, params=None, timeout=None, *, deadline=None):
            raise BridgeError("BRIDGE_BUSY", "queue full", retryable=True)

    with pytest.raises(ToolFailure) as exc:
        scene_summary_impl(FakeDiscovery([make_inst(client=BusyClient())]), "gui-1-aa")
    assert exc.value.code == "BRIDGE_BUSY" and exc.value.retryable is True


@pytest.mark.asyncio
async def test_scene_summary_server_admission_spans_sdk_conversion(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    two_entered = threading.Event()
    release_bodies = threading.Event()
    conversion_entered = threading.Event()
    release_conversion = threading.Event()
    lock = threading.Lock()
    body_calls = 0
    observed_calls = []
    controller_errors = []
    valid = {
        "instance_id": "gui-1-aa", "scene_name": "S", "scene_revision": 1,
        "scene_hash": "sha256:x", "scene_path": None, "version_warning": None,
        "units": {"system": "NONE", "scale_length": 1.0},
        "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                    "light_count": 0, "collections": [], "managed_objects": []},
    }

    def blocking_impl(*_args, **_kwargs):
        nonlocal body_calls
        with lock:
            body_calls += 1
            if body_calls == 2:
                two_entered.set()
        assert release_bodies.wait(2.0)
        return valid

    tool = adapter.mcp._tool_manager._tools["get_scene_summary"]
    metadata_cls = type(tool.fn_metadata)
    original_convert = metadata_cls.convert_result

    def blocking_convert(metadata, result):
        conversion_entered.set()
        assert release_conversion.wait(2.0)
        return original_convert(metadata, result)

    def control():
        if not two_entered.wait(1.0):
            controller_errors.append("two tool bodies did not enter")
        release_bodies.set()
        if not conversion_entered.wait(1.0):
            controller_errors.append("SDK conversion did not start")
        time.sleep(0.05)
        with lock:
            observed_calls.append(body_calls)
        release_conversion.set()

    monkeypatch.setattr(adapter, "scene_summary_impl", blocking_impl)
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    monkeypatch.setattr(adapter, "_SCENE_SUMMARY_ADMISSION",
                        threading.BoundedSemaphore(2))
    monkeypatch.setattr(metadata_cls, "convert_result", blocking_convert)
    controller = threading.Thread(target=control)
    controller.start()
    try:
        async with Client(adapter.mcp) as client:
            outcomes = await asyncio.gather(*(
                client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
                for _ in range(3)), return_exceptions=True)
            retry = await client.call_tool(
                "get_scene_summary", {"instance_id": "gui-1-aa"})
    finally:
        release_bodies.set()
        release_conversion.set()
        controller.join(timeout=2.0)
    errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    successes = [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]
    assert controller_errors == [] and observed_calls == [2]
    assert len(successes) == 2 and all(not result.is_error for result in successes)
    assert len(errors) == 1 and isinstance(errors[0], MCPError)
    assert errors[0].data == {"code": "BRIDGE_BUSY", "retryable": True}
    assert retry.is_error is False and body_calls == 3


@pytest.mark.asyncio
async def test_scene_summary_server_admission_releases_after_exception(audit,
                                                                       monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    calls = 0

    def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise RuntimeError("boom")
        return {
            "instance_id": "gui-1-aa", "scene_name": "S", "scene_revision": 1,
            "scene_hash": "sha256:x", "scene_path": None, "version_warning": None,
            "units": {"system": "NONE", "scale_length": 1.0},
            "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                        "light_count": 0, "collections": [], "managed_objects": []},
        }

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    monkeypatch.setattr(adapter, "scene_summary_impl", flaky)
    monkeypatch.setattr(adapter, "_SCENE_SUMMARY_ADMISSION",
                        threading.BoundedSemaphore(2))
    async with Client(adapter.mcp) as client:
        for _ in range(2):
            result = await client.call_tool(
                "get_scene_summary", {"instance_id": "gui-1-aa"})
            assert result.is_error is True
        result = await client.call_tool(
            "get_scene_summary", {"instance_id": "gui-1-aa"})
    assert result.is_error is False


def test_capabilities_is_local_by_default():
    import server.mcp.adapter as adapter

    tools = list(adapter.mcp._tool_manager._tools.values())
    assert [(tool.name, tool.description) for tool in tools] == [
        ("get_blender_status",
         "列出 Blender 实例、Bridge 连接状态与场景概况。无实例时返回引导文案。"),
        ("get_scene_summary",
         "返回指定实例的场景摘要：对象统计、单位、scene_hash 与受管对象清单。"),
        ("describe_capabilities",
         "返回本 Server 能力：支持的工具、IR 版本、Blender 基线。默认不连 Bridge。"),
    ]
    # 复审 F-07：默认不碰 Bridge——Blender 离线时也必须能回答
    class ExplodingDiscovery:
        last_scan = ScanStats()

        def instances(self, force=False, deadline=None):
            raise AssertionError("describe_capabilities 不得触碰 Bridge")

    out = capabilities_impl(ExplodingDiscovery())
    assert out["phase"] == "phase0" and out["connected_instances"] == []
    assert out["instances_partial"] is False and out["instances_skipped_count"] == 0


def test_capabilities_lists_connected_when_requested():
    out = capabilities_impl(FakeDiscovery([make_inst(client=FakeClient({}))],
                                                    partial=True, skipped=4),
                            include_instances=True)
    assert out["phase"] == "phase0"
    assert out["connected_instances"][0]["instance_id"] == "gui-1-aa"
    assert out["instances_partial"] is True and out["instances_skipped_count"] == 4


def test_capabilities_uses_stats_paired_with_its_instance_snapshot():
    d = FakeDiscovery([])
    d.instances_with_stats = lambda **_kwargs: ([], ScanStats(True, 2))
    out = capabilities_impl(d, include_instances=True)
    assert out["instances_partial"] is True and out["instances_skipped_count"] == 2


def _audit_rows(tmp_path):
    f = next((tmp_path / "logs").glob("server-*.jsonl"))
    return [json.loads(line) for line in f.read_text().splitlines()]


@pytest.mark.asyncio
async def test_mcp_boundary_audits_success_and_unknown_arguments(audit, tmp_path,
                                                                 monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_blender_status", {})
        assert result.is_error is False
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_blender_status", {"unexpected": 1})
        assert exc.value.code == -32602

    rows = _audit_rows(tmp_path)
    assert len(rows) == 2
    assert rows[0]["tool"] == "get_blender_status" and rows[0]["ok"] is True
    assert rows[1]["ok"] is False and rows[1]["error"] == "-32602"


@pytest.mark.asyncio
async def test_mcp_boundary_rejects_sdk_type_coercion(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool(
                "describe_capabilities", {"include_instances": "false"})
    assert exc.value.code == -32602
    assert exc.value.data == {
        "tool": "describe_capabilities", "argument": "include_instances"}
    row = _audit_rows(tmp_path)[0]
    assert row["ok"] is False and row["error"] == "-32602"


@pytest.mark.asyncio
async def test_audit_covers_all_scene_summary_arguments(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    c = FakeClient({"scene_summary": {
        "scene_hash": "sha256:x", "scene_name": "S", "scene_revision": 1,
        "scene_path": None, "units": {"system": "NONE", "scale_length": 1.0},
        "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                    "light_count": 0, "collections": [], "managed_objects": []}}})
    discovery = FakeDiscovery([make_inst(client=c)])
    monkeypatch.setattr(adapter, "_deps_cache", (discovery, audit))
    arguments = {"instance_id": "gui-1-aa", "include_collections": False,
                 "include_managed_objects": False}
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_scene_summary", arguments)
        assert result.is_error is False

    row = _audit_rows(tmp_path)[0]
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    assert row["params_digest"] == hashlib.sha256(canonical.encode()).hexdigest()[:16]


@pytest.mark.asyncio
async def test_output_validation_failure_is_audited(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    # Pydantic's default mode would coerce integer 1 to true despite the boolean schema.
    monkeypatch.setattr(adapter, "status_impl", lambda *_args, **_kwargs: {"ok": 1})
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_blender_status", {})
        assert result.is_error is True

    row = _audit_rows(tmp_path)[0]
    assert row["ok"] is False and row["error"] == "TOOL_ERROR"


@pytest.mark.asyncio
async def test_audit_failure_is_structured_and_fail_closed(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    def fail_record(*_args, **_kwargs):
        raise TimeoutError("audit deadline expired")

    monkeypatch.setattr(audit, "record", fail_record)
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_blender_status", {})
    assert exc.value.code == -32000
    assert exc.value.data == {"code": "AUDIT_UNAVAILABLE", "retryable": True}


@pytest.mark.asyncio
async def test_audit_initialization_failure_is_structured(monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    def fail_deps():
        raise PermissionError("private directory required: /sensitive/runtime")

    monkeypatch.setattr(adapter, "_deps", fail_deps)
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("describe_capabilities", {})
    assert exc.value.code == -32000
    assert exc.value.data == {"code": "AUDIT_UNAVAILABLE", "retryable": True}
    assert "/sensitive/runtime" not in str(exc.value)


@pytest.mark.asyncio
async def test_audit_postlude_receives_one_absolute_deadline(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    remaining = []

    def capture_record(*_args, deadline=None, **_kwargs):
        assert deadline is not None
        remaining.append(deadline - time.monotonic())

    monkeypatch.setattr(audit, "record", capture_record)
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_blender_status", {})
    assert result.is_error is False
    assert len(remaining) == 1
    assert 0 < remaining[0] <= adapter.AUDIT_LOCK_TIMEOUT


@pytest.mark.asyncio
async def test_scene_summary_mcp_error_has_domain_code_and_retryable(audit, tmp_path,
                                                                     monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    discovery = FakeDiscovery([make_inst(state="disconnected", client=None)])
    monkeypatch.setattr(adapter, "_deps_cache", (discovery, audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
    assert exc.value.code == -32000
    assert exc.value.data == {"code": "BRIDGE_UNAVAILABLE", "retryable": True}
    row = _audit_rows(tmp_path)[0]
    assert row["ok"] is False and row["error"] == "BRIDGE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scene_summary_rejects_malformed_bridge_payloads(audit, tmp_path,
                                                                monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    valid = {
        "scene_hash": "sha256:x", "scene_name": "S", "scene_revision": 1,
        "scene_path": None, "units": {"system": "NONE", "scale_length": 1.0},
        "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                    "light_count": 0, "collections": [], "managed_objects": []},
    }

    class MalformedClient:
        def __init__(self):
            pair_list = [[key, value] for key, value in valid["summary"].items()]
            self.results = [
                {"summary": {}},
                {**valid, "scene_revision": "1"},
                {**valid, "summary": pair_list},
            ]

        def call(self, *_args, **_kwargs):
            return self.results.pop(0)

    discovery = FakeDiscovery([make_inst(client=MalformedClient())])
    monkeypatch.setattr(adapter, "_deps_cache", (discovery, audit))
    async with Client(adapter.mcp) as client:
        for _ in range(3):
            with pytest.raises(MCPError) as exc:
                await client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
            assert exc.value.code == -32000
            assert exc.value.data == {"code": "BRIDGE_UNAVAILABLE", "retryable": True}

    assert discovery.invalidated is True
    assert [row["error"] for row in _audit_rows(tmp_path)] == [
        "BRIDGE_UNAVAILABLE", "BRIDGE_UNAVAILABLE", "BRIDGE_UNAVAILABLE"]
