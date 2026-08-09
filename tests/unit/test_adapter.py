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
    def __init__(self, results):
        self.results = results

    def call(self, method, params=None, timeout=None, *, deadline=None):
        return self.results[method]


class FakeDiscovery:
    def __init__(self, instances, partial=False, skipped=0):
        self.instances_ = instances
        self.last_scan = ScanStats(partial, skipped)
        self.invalidated = False
        self.invalidate_deadline = None

    def instances(self, force=False, deadline=None):
        return self.instances_

    def instances_with_stats(self, force=False, deadline=None):
        return self.instances(force=force, deadline=deadline), self.last_scan

    def find(self, instance_id, deadline=None):
        return next((item for item in self.instances_
                     if item.session["instance_id"] == instance_id), None)

    def find_with_stats(self, instance_id, deadline=None):
        return self.find(instance_id, deadline=deadline), self.last_scan

    def invalidate(self, deadline=None):
        self.invalidated = True
        self.invalidate_deadline = deadline
        return True


def inst(iid="gui-1-aa", state="connected", client=None, supported=True,
         warning=None, mismatch=False):
    return Instance({"instance_id": iid, "pid": 1, "blender_version": "5.2.0",
                     "bridge_version": "0.1.0"}, state, supported, warning,
                    client, mismatch)


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "logs")


def test_status_empty_returns_guidance():
    assert status_impl(FakeDiscovery([])) == {
        "ok": True, "guidance": GUIDANCE, "partial": False,
        "skipped_count": 0, "instances": []}


@pytest.mark.parametrize(("selector", "expected"), [
    ("gui-9-zz", []), (None, ["gui-1-aa"]),
])
def test_status_selector_filters_exact_snapshot(selector, expected):
    result = status_impl(FakeDiscovery([inst(client=FakeClient({"status": {
        "instance_id": "gui-1-aa", "scene_path": None, "scene_revision": 1}}))]), selector)
    assert [row["instance_id"] for row in result["instances"]] == expected


@pytest.mark.parametrize(("partial", "skipped"), [(True, 1), (True, 7), (False, 0)])
def test_status_surfaces_paired_scan_metadata(partial, skipped):
    result = status_impl(FakeDiscovery([], partial, skipped))
    assert (result["partial"], result["skipped_count"]) == (partial, skipped)


@pytest.mark.parametrize("state", ["disconnected", "busy"])
def test_status_nonconnected_snapshot_has_guidance(state):
    result = status_impl(FakeDiscovery([inst(state=state)]))
    assert result["guidance"] == GUIDANCE
    assert result["instances"][0]["bridge_state"] == state


def test_status_enriches_bridge_response():
    result = status_impl(FakeDiscovery([inst(client=FakeClient({"status": {
        "instance_id": "gui-1-aa", "scene_path": "/tmp/x.blend", "scene_revision": 4}}))]))
    assert result["instances"][0]["scene_path"] == "/tmp/x.blend"


@pytest.mark.parametrize("payload", [
    {"scene_path": [], "scene_revision": True},
    {"instance_id": "gui-other", "scene_path": None, "scene_revision": 1},
    {"instance_id": "gui-1-aa", "scene_path": None, "scene_revision": True},
])
def test_status_invalid_bridge_result_is_isolated(payload):
    discovery = FakeDiscovery([inst(client=FakeClient({"status": payload}))])
    result = status_impl(discovery)
    assert result["instances"][0]["bridge_state"] == "disconnected"
    assert discovery.invalidated


def test_status_busy_error_is_preserved():
    from server.core.bridge_client import BridgeError

    class Busy:
        def call(self, *args, **kwargs):
            raise BridgeError("BRIDGE_BUSY", "full", True)

    assert status_impl(FakeDiscovery([inst(client=Busy())]))["instances"][0]["bridge_state"] == "busy"


def test_status_passes_relative_and_absolute_deadlines():
    class Capture:
        timeout = None
        deadline = None

        def call(self, _method, _params=None, timeout=None, *, deadline=None):
            self.timeout, self.deadline = timeout, deadline
            return {"instance_id": "gui-1-aa", "scene_path": None, "scene_revision": 0}

    client = Capture()
    status_impl(FakeDiscovery([inst(client=client)]))
    assert 0 < client.timeout <= 2 and client.deadline is not None


def test_status_one_absolute_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class Slow:
        def call(self, *args, **kwargs):
            time.sleep(.4)
            return {}

    monkeypatch.setattr(adapter, "OVERALL_BUDGET", .1)
    started = time.monotonic()
    result = status_impl(FakeDiscovery([inst(client=Slow())]))
    assert time.monotonic() - started < .25
    assert result["instances"][0]["bridge_state"] == "disconnected"


def test_status_uses_shared_eight_worker_pool():
    active = peak = 0
    lock = threading.Lock()

    class Tracking:
        def call(self, *args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(.01)
                return {"instance_id": "gui-1-aa", "scene_path": None, "scene_revision": 1}
            finally:
                with lock:
                    active -= 1

    statuses = [inst(iid=f"gui-{i}-aa", client=Tracking()) for i in range(1, 17)]
    threads = [threading.Thread(target=status_impl, args=(FakeDiscovery(statuses),)) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
    assert peak <= 8


def summary():
    return {"scene_hash": "sha256:x", "scene_name": "S", "scene_revision": 1,
            "scene_path": None, "units": {"system": "NONE", "scale_length": 1.0},
            "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                        "light_count": 0, "collections": ["C"], "managed_objects": []}}


def test_scene_summary_injects_server_fields():
    result = scene_summary_impl(FakeDiscovery([inst(client=FakeClient({"scene_summary": summary()}),
                                                   supported=False, warning="w")]), "gui-1-aa")
    assert result["instance_id"] == "gui-1-aa" and result["version_warning"] == "w"


@pytest.mark.parametrize(("instances", "partial", "code", "retryable"), [
    ([], False, "INSTANCE_NOT_FOUND", False),
    ([], True, "BRIDGE_UNAVAILABLE", True),
    ([inst(mismatch=True, warning="v")], False, "ENVELOPE_VERSION_MISMATCH", False),
    ([inst(state="disconnected")], False, "BRIDGE_UNAVAILABLE", True),
])
def test_scene_summary_error_mapping(instances, partial, code, retryable):
    with pytest.raises(ToolFailure) as raised:
        scene_summary_impl(FakeDiscovery(instances, partial), "gui-1-aa")
    assert (raised.value.code, raised.value.retryable) == (code, retryable)


def test_scene_summary_passes_absolute_deadline():
    class Capture(FakeClient):
        deadline = None

        def call(self, *args, deadline=None, **kwargs):
            self.deadline = deadline
            return summary()

    client = Capture({})
    scene_summary_impl(FakeDiscovery([inst(client=client)]), "gui-1-aa")
    assert client.deadline is not None


@pytest.mark.parametrize("mutate", [
    lambda value: value.pop("summary"),
    lambda value: value.update(summary=[]),
])
def test_scene_summary_rejects_malformed_payload(mutate):
    value = summary()
    mutate(value)
    with pytest.raises((KeyError, TypeError, ValueError)):
        scene_summary_impl(FakeDiscovery([inst(client=FakeClient({"scene_summary": value}))]), "gui-1-aa")


@pytest.mark.parametrize("include_instances", [False, True])
def test_capabilities_has_fixed_tool_order(include_instances):
    result = capabilities_impl(FakeDiscovery([inst(client=FakeClient({}))]), include_instances)
    assert result["supported_tools"] == ["get_blender_status", "get_scene_summary", "describe_capabilities"]


def test_capabilities_default_is_local():
    class Exploding:
        def instances_with_stats(self, **kwargs):
            raise AssertionError

    assert capabilities_impl(Exploding())["connected_instances"] == []


@pytest.mark.parametrize("skipped", [1, 2])
def test_capabilities_pairs_partial_metadata(skipped):
    result = capabilities_impl(FakeDiscovery([], partial=True, skipped=skipped), True)
    assert (result["instances_partial"], result["instances_skipped_count"]) == (True, skipped)


def _rows(tmp_path):
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.mark.asyncio
async def test_mcp_boundary_audits_success_and_unknown_arguments(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        assert not (await client.call_tool("get_blender_status", {})).is_error
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_blender_status", {"unexpected": 1})
    assert exc.value.code == -32602 and len(_rows(tmp_path)) == 2


@pytest.mark.asyncio
async def test_mcp_boundary_rejects_type_coercion(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("describe_capabilities", {"include_instances": "false"})
    assert exc.value.data == {"tool": "describe_capabilities", "argument": "include_instances"}
    assert _rows(tmp_path)[0]["error"] == "-32602"


@pytest.mark.asyncio
async def test_mcp_audits_argument_digest(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([inst(client=FakeClient({"scene_summary": summary()}))]), audit))
    arguments = {"instance_id": "gui-1-aa", "include_collections": False,
                 "include_managed_objects": False}
    async with Client(adapter.mcp) as client:
        assert not (await client.call_tool("get_scene_summary", arguments)).is_error
    assert _rows(tmp_path)[0]["params_digest"] == hashlib.sha256(
        json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


@pytest.mark.asyncio
async def test_mcp_output_failure_is_audited(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    monkeypatch.setattr(adapter, "status_impl", lambda *_args: {"ok": 1})
    async with Client(adapter.mcp) as client:
        assert (await client.call_tool("get_blender_status", {})).is_error
    assert _rows(tmp_path)[0]["ok"] is False


@pytest.mark.asyncio
async def test_mcp_audit_failure_is_fail_closed(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(audit, "record", lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_blender_status", {})
    assert exc.value.data == {"code": "AUDIT_UNAVAILABLE", "retryable": True}


@pytest.mark.asyncio
async def test_mcp_scene_error_has_domain_code(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([inst(state="disconnected")]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
    assert exc.value.data == {"code": "BRIDGE_UNAVAILABLE", "retryable": True}
    assert _rows(tmp_path)[0]["error"] == "BRIDGE_UNAVAILABLE"
