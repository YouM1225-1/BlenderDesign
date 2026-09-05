import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from acceptance import check_registry as reg
from acceptance import contract as contract_module
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


def test_contract_fifo_is_rejected_without_blocking(tmp_path):
    fifo = tmp_path / "contract.json"
    os.mkfifo(fifo)
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from acceptance.contract import load_contract\n"
        "from acceptance.primitives import AcceptanceFailure\n"
        "try:\n"
        "    load_contract(Path(sys.argv[1]), candidate_root=Path(sys.argv[2]))\n"
        "except AcceptanceFailure as exc:\n"
        "    raise SystemExit(0 if exc.code == 'contract_invalid' else 3)\n"
        "raise SystemExit(2)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(fifo), str(tmp_path / "candidate")],
        cwd=repo_root, capture_output=True, text=True, timeout=2.0, check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_contract_read_has_an_explicit_size_cap(tmp_path, monkeypatch):
    raw = json.dumps(_valid()).encode("utf-8")
    path = tmp_path / "contract.json"
    path.write_bytes(raw)
    monkeypatch.setattr(contract_module, "_MAX_CONTRACT_BYTES", len(raw) - 1)
    with pytest.raises(AcceptanceFailure, match="size limit") as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_contract_requires_strict_utf8_without_bom(tmp_path, encoding):
    path = tmp_path / "contract.json"
    path.write_bytes(json.dumps(_valid()).encode(encoding))
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_huge_integer_token_is_contract_invalid(tmp_path):
    raw = json.dumps(_valid()).replace(
        '"max_triangles": 1000000', '"max_triangles": 1' + "0" * 5000)
    path = tmp_path / "contract.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("bad_budget", [None, True, 1, 1.0, "budget", []])
def test_budget_must_be_an_object(tmp_path, bad_budget):
    bad = _valid()
    bad["budget"] = bad_budget
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("bad_limit", [None, True, -1, 1.0, "1", [], {}])
def test_max_file_bytes_must_be_a_precise_nonnegative_integer(tmp_path, bad_limit):
    bad = _valid()
    bad["budget"]["max_file_bytes"] = bad_limit
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_max_file_bytes_is_required(tmp_path):
    bad = _valid()
    del bad["budget"]["max_file_bytes"]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_zero_max_file_bytes_is_valid(tmp_path):
    value = _valid()
    value["budget"]["max_file_bytes"] = 0
    contract = load_contract(_write(tmp_path, value), candidate_root=tmp_path / "candidate")
    assert contract.raw["budget"]["max_file_bytes"] == 0


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


def test_warning_allowlist_deleted_from_raw_is_rejected(tmp_path):
    """contract.raw 可变;warning_allowlist 被删后 allowlisted() 必须 fail-closed,不是裸
    KeyError——与上面三个属性同一形状的缺陷,提交 b14cfa6 修了那三个,漏了这一个方法。"""
    path = _write(tmp_path, _valid())
    contract = load_contract(path, candidate_root=tmp_path / "candidate")
    del contract.raw["warning_allowlist"]
    with pytest.raises(AcceptanceFailure) as caught:
        contract.allowlisted("foo", "bar", "baz", "1.0")
    assert caught.value.code == "contract_invalid"


def test_lone_surrogate_in_contract_is_rejected(tmp_path):
    """`\\ud800` 这样的孤立代理转义能穿过 read_text()+json.loads()(两者都不校验编码合法
    性),落地成一个 Python str 里的真实孤立代理码点。NFC 规范化对它是空操作,真正炸开
    的地方是 canonical.py 的 UTF-8/UTF-16 编码——UnicodeEncodeError 是 ValueError 的
    子类但不是 CanonicalError,此前会作为裸异常穿透 load_contract 的
    `except CanonicalError`,被上层误判为 runner_internal_error(优先级 14)而不是
    规范要求的 contract_invalid(优先级 0)。"""
    bad = _valid()
    bad["contract_id"] = "\ud800"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"
