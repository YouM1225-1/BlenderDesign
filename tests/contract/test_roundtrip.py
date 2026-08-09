"""端到端（Server core → UDS → 真 bridge/core）。工具形状按 spec §6 断言。"""
from server.core.discovery import Discovery
from server.mcp.adapter import GUIDANCE, capabilities_impl, scene_summary_impl, status_impl
from tests.contract.fake_bridge import live_bridge


def test_status_roundtrip_shape(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        out = status_impl(Discovery(run))
        assert out["ok"] is True and out["guidance"] is None
        row = out["instances"][0]
        assert row["instance_id"] == s.instance_id
        assert row["bridge_state"] == "connected"
        assert row["mode"] == "gui"
        assert row["blender_supported"] is True
        assert row["scene_revision"] == 1


def test_no_instance_returns_guidance(tmp_path):
    out = status_impl(Discovery(tmp_path / "run"))
    assert out == {"ok": True, "guidance": GUIDANCE, "partial": False,
                   "skipped_count": 0, "instances": []}


def test_scene_summary_roundtrip_shape(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        out = scene_summary_impl(Discovery(run), s.instance_id)
        assert out["instance_id"] == s.instance_id
        assert out["scene_hash"] == "sha256:fake"
        assert out["scene_name"] == "Scene"
        assert out["units"] == {"system": "METRIC", "scale_length": 1.0}
        assert out["summary"]["managed_objects"] == []
        assert out["version_warning"] is None


def test_capabilities_offline_and_connected(tmp_path):
    out = capabilities_impl(Discovery(tmp_path / "run"))
    assert out["connected_instances"] == []          # 离线可答（§4.2）
    with live_bridge(tmp_path) as (s, reader, run):
        out2 = capabilities_impl(Discovery(run), include_instances=True)
        assert out2["connected_instances"][0]["instance_id"] == s.instance_id


def test_non_baseline_version_warning_attached(tmp_path):
    with live_bridge(tmp_path, blender_version="4.5.3") as (s, reader, run):
        out = scene_summary_impl(Discovery(run), s.instance_id)
        assert out["version_warning"] is not None and "4.5.3" in out["version_warning"]
