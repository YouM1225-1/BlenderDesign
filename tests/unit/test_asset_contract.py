import json
from pathlib import Path

import pytest

from acceptance import check_registry as reg
from acceptance.contract import load_contract
from acceptance.primitives import AcceptanceFailure


def _valid(kind: str = "blend_native") -> dict[str, object]:
    checks = [
        {"id": c.id, "impl": c.impl, "order": c.order}
        for c in sorted(reg.checks_for_kind(kind), key=reg.sort_key)
    ]
    return {
        "schema_version": 1,
        "contract_id": "pilot-001",
        "artifact_kind": kind,
        "profile": "static_render",
        "required_isolation_grade": "local-trusted",
        "input": {"path": "asset.blend", "sha256": "0" * 64, "bytes": 1024},
        "export": None,
        "checks": checks,
        "na_check_ids": list(reg.na_check_ids(kind)),
        "warning_allowlist": [],
        "visual_thresholds": {"macos-arm64-workbench-metal-apple_m4":
                              {"fail": 0.016, "failpercent": 1.0}},
        "platform_blocklist": [],
        "texture_colorspace": {"base_color": "sRGB", "data": "Non-Color"},
        "tolerated_unknown_types": [],
        "validator_config_path": None,
        "budget": {"max_triangles": 1000000, "max_materials": 64, "max_images": 64,
                   "max_image_bytes": 33554432, "max_file_bytes": 536870912,
                   "vertex_split_ratio_max": 4.0},
        "projection": {"preserved": [], "transformed": [], "lost": []},
        "tools": [{"id": "blender", "version": "5.2.0", "sha256": "1" * 64,
                   "path": "/Applications/Blender.app/Contents/MacOS/Blender"}],
        "limits": {"cpu_seconds": 600, "address_space_bytes": 8589934592,
                   "open_files": 256, "file_size_bytes": 1073741824},
        "golden": None,
    }


def _write(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_contract_loads_and_has_stable_digest(tmp_path):
    path = _write(tmp_path, _valid())
    first = load_contract(path, candidate_root=tmp_path / "candidate")
    second = load_contract(path, candidate_root=tmp_path / "candidate")
    assert first.digest == second.digest
    assert first.artifact_kind == "blend_native"


def test_unknown_top_level_field_is_rejected(tmp_path):
    bad = _valid() | {"surprise": 1}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_na_set_must_equal_derived_set(tmp_path):
    bad = _valid()
    bad["na_check_ids"] = bad["na_check_ids"][:-1]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_checks_must_be_in_total_order(tmp_path):
    bad = _valid()
    checks = list(bad["checks"])
    checks[0], checks[1] = checks[1], checks[0]
    bad["checks"] = checks
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_contract_inside_candidate_root_is_rejected(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    path = _write(candidate, _valid())
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=candidate)
    assert caught.value.code == "contract_invalid"


def test_interchange_projection_union_must_be_p01_to_p14(tmp_path):
    value = _valid("interchange")
    value["export"] = {"format": "glb", "preset": {}}
    value["projection"] = {"preserved": ["p01_object_count"], "transformed": [], "lost": []}
    path = _write(tmp_path, value)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_missing_top_level_field_is_rejected(tmp_path):
    bad = _valid()
    del bad["contract_id"]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_invalid_artifact_kind_is_rejected(tmp_path):
    bad = _valid()
    bad["artifact_kind"] = "not_a_real_kind"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_invalid_profile_is_rejected(tmp_path):
    bad = _valid()
    bad["profile"] = "not_static_render"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_invalid_required_isolation_grade_is_rejected(tmp_path):
    bad = _valid()
    bad["required_isolation_grade"] = "not_a_real_grade"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_tools_entry_field_set_is_rejected(tmp_path):
    bad = _valid()
    bad["tools"] = [{"id": "blender", "version": "5.2.0"}]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_tools_sha256_wrong_length_is_rejected(tmp_path):
    bad = _valid()
    bad["tools"] = [{"id": "blender", "version": "5.2.0", "sha256": "abc",
                      "path": "/Applications/Blender.app/Contents/MacOS/Blender"}]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_projection_field_in_multiple_groups_is_rejected(tmp_path):
    bad = _valid()
    bad["projection"] = {"preserved": ["dup_field"], "transformed": ["dup_field"], "lost": []}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_candidate_root_equal_to_contract_path_is_rejected(tmp_path):
    path = _write(tmp_path, _valid())
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=path)
    assert caught.value.code == "contract_invalid"


def test_symlinked_candidate_root_bypass_is_rejected(tmp_path):
    real_candidate = tmp_path / "real_candidate"
    real_candidate.mkdir()
    link_candidate = tmp_path / "link_candidate"
    link_candidate.symlink_to(real_candidate, target_is_directory=True)
    _write(real_candidate, _valid())
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(link_candidate / "contract.json", candidate_root=link_candidate)
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("alias", [True, 1.0])
def test_schema_version_alias_value_is_rejected(tmp_path, alias):
    bad = _valid()
    bad["schema_version"] = alias
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_tools_non_dict_entry_is_rejected(tmp_path):
    bad = _valid()
    bad["tools"] = [5]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_projection_group_not_list_is_rejected(tmp_path):
    bad = _valid()
    bad["projection"] = {"preserved": 5, "transformed": [], "lost": []}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_projection_group_with_non_string_element_is_rejected(tmp_path):
    bad = _valid("interchange")
    bad["export"] = {"format": "glb", "preset": {}}
    bad["projection"] = {"preserved": ["p01_object_count", 5], "transformed": [], "lost": []}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_contract_file_not_found_is_rejected(tmp_path):
    nonexistent = tmp_path / "does_not_exist.json"
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(nonexistent, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_artifact_kind_list_is_rejected(tmp_path):
    bad = _valid()
    bad["artifact_kind"] = []
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_artifact_kind_dict_is_rejected(tmp_path):
    bad = _valid()
    bad["artifact_kind"] = {}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_warning_allowlist_not_list_is_rejected(tmp_path):
    bad = _valid()
    bad["warning_allowlist"] = None
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("not_list", [5, 1.5, True, {}])
def test_warning_allowlist_scalar_is_rejected(tmp_path, not_list):
    bad = _valid()
    bad["warning_allowlist"] = not_list
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_warning_allowlist_entry_non_dict_is_rejected(tmp_path):
    bad = _valid()
    bad["warning_allowlist"] = [5]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_warning_allowlist_entry_missing_key_is_rejected(tmp_path):
    bad = _valid()
    bad["warning_allowlist"] = [{"check_id": "foo", "warning_code": "bar", "tool_id": "baz"}]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_warning_allowlist_entry_extra_key_is_rejected(tmp_path):
    bad = _valid()
    bad["warning_allowlist"] = [{"check_id": "foo", "warning_code": "bar", "tool_id": "baz",
                                 "tool_version": "1.0", "extra": "field"}]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("key", ["check_id", "warning_code", "tool_id", "tool_version"])
def test_warning_allowlist_entry_non_string_value_is_rejected(tmp_path, key):
    bad = _valid()
    entry = {"check_id": "foo", "warning_code": "bar", "tool_id": "baz", "tool_version": "1.0"}
    entry[key] = 123
    bad["warning_allowlist"] = [entry]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_warning_allowlist_valid_entry_loads(tmp_path):
    good = _valid()
    good["warning_allowlist"] = [{"check_id": "foo", "warning_code": "bar", "tool_id": "baz",
                                   "tool_version": "1.0"}]
    path = _write(tmp_path, good)
    contract = load_contract(path, candidate_root=tmp_path / "candidate")
    assert contract.allowlisted("foo", "bar", "baz", "1.0")


def test_profile_non_string_is_rejected(tmp_path):
    bad = _valid()
    bad["profile"] = 123
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_required_isolation_grade_non_string_is_rejected(tmp_path):
    bad = _valid()
    bad["required_isolation_grade"] = 123
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_artifact_kind_deleted_from_raw_is_rejected(tmp_path):
    """contract.raw 可变,frozen=True 只冻结字段引用;artifact_kind 被删后读属性必须 fail-closed,不是裸 KeyError。"""
    path = _write(tmp_path, _valid())
    contract = load_contract(path, candidate_root=tmp_path / "candidate")
    del contract.raw["artifact_kind"]
    with pytest.raises(AcceptanceFailure) as caught:
        _ = contract.artifact_kind
    assert caught.value.code == "contract_invalid"


def test_na_check_ids_deleted_from_raw_is_rejected(tmp_path):
    """contract.raw 可变;na_check_ids 被删后读属性必须 fail-closed,不是裸 KeyError。"""
    path = _write(tmp_path, _valid())
    contract = load_contract(path, candidate_root=tmp_path / "candidate")
    del contract.raw["na_check_ids"]
    with pytest.raises(AcceptanceFailure) as caught:
        _ = contract.na_check_ids
    assert caught.value.code == "contract_invalid"


def test_required_isolation_grade_deleted_from_raw_is_rejected(tmp_path):
    """contract.raw 可变;required_isolation_grade 被删后读属性必须 fail-closed,不是裸 KeyError。"""
    path = _write(tmp_path, _valid())
    contract = load_contract(path, candidate_root=tmp_path / "candidate")
    del contract.raw["required_isolation_grade"]
    with pytest.raises(AcceptanceFailure) as caught:
        _ = contract.required_isolation_grade
    assert caught.value.code == "contract_invalid"
