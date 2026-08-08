from server.core import versions
from server.core.capabilities import describe


def test_baseline_pinned():
    assert versions.BASELINE == {"version": "5.2.0", "platform": "macos-arm64"}


def test_check_matrix():
    assert versions.check("5.2.0") == (True, None)
    ok, warn = versions.check("5.2.3")
    assert ok is False and "5.2.3" in warn and "5.2.0" in warn
    ok, warn = versions.check("4.5.3")
    assert ok is False and "4.5.3" in warn and "5.2" in warn
    ok, warn = versions.check("6.0.0")
    assert ok is False and warn is not None


def test_gate_write_matrix():
    assert versions.gate_write("5.2.0") is None
    assert versions.gate_write("5.2.1") == "UNSUPPORTED_BLENDER_VERSION"
    assert versions.gate_write("4.5.3") == "UNSUPPORTED_BLENDER_VERSION"


def test_describe_capabilities_shape():
    d = describe("0.1.0", connected=[])
    assert d["phase"] == "phase0"
    assert d["ir_schema_version"] is None
    assert d["supported_operation_kinds"] == []
    assert d["baseline_blender"] == {"version": "5.2.0", "platform": "macos-arm64"}
    assert d["envelope_version"] == 1
    expected_tools = ["get_blender_status", "get_scene_summary",
                      "describe_capabilities"]
    assert d["supported_tools"] == expected_tools
    d["supported_tools"].append("mutated")
    assert describe("0.1.0", connected=[])["supported_tools"] == expected_tools
    assert d["connected_instances"] == []
