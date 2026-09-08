from copy import deepcopy
from dataclasses import replace
import json

import pytest

from acceptance.contract import Contract, enforce_baseline, load_contract, validate_document
from acceptance.input_bundle import measure_file, source_digest, verify_bundle
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document, write_contract


def test_deep_immutable_snapshot_and_domain(tmp_path):
    document = valid_document(tmp_path)
    contract = write_contract(tmp_path, document)
    document["budget"]["max_files"] = 1
    assert contract.raw["budget"]["max_files"] == 1000
    with pytest.raises(TypeError):
        contract.raw["budget"]["max_files"] = 2
    with pytest.raises(AcceptanceFailure, match="digest"):
        replace(contract, digest="0" * 64)


@pytest.mark.parametrize(
    "mutation",
    [
        "v1",
        "bool_version",
        "wrong_nested_type",
        "tool_missing",
        "tool_duplicate",
        "hash_not_hex",
        "bool_budget",
        "unknown_nested",
        "old_impl",
        "input_digest",
        "forged_na",
        "native_opaque",
        "unknown_review",
        "coverage_allowance",
    ],
)
def test_closed_schema_rejects_specific_counterexample(tmp_path, mutation):
    value = valid_document(tmp_path)
    if mutation == "v1":
        value["schema_version"] = 1
    elif mutation == "bool_version":
        value["schema_version"] = True
    elif mutation == "wrong_nested_type":
        value["limits"] = "bad"
    elif mutation == "tool_missing":
        value["tools"] = []
    elif mutation == "tool_duplicate":
        value["tools"].append(dict(value["tools"][0]))
    elif mutation == "hash_not_hex":
        value["tools"][0]["sha256"] = "z" * 64
    elif mutation == "bool_budget":
        value["budget"]["max_files"] = True
    elif mutation == "unknown_nested":
        value["input"]["shadow"] = {}
    elif mutation == "old_impl":
        value["checks"][0]["impl"] = 0
    elif mutation == "input_digest":
        value["input"]["sha256"] = "0" * 64
    elif mutation == "forged_na":
        value["na_check_ids"] = []
    elif mutation == "native_opaque":
        value["native"] = {"anything": True}
    elif mutation == "unknown_review":
        value["review"]["approved"] = True
    elif mutation == "coverage_allowance":
        value["warning_allowlist"] = [
            {
                "check_id": "r2.inventory.coverage_complete",
                "warning_code": "unsupported_datablock_type",
                "tool_id": "blender",
                "tool_version": "Blender 5.2.0 LTS",
            }
        ]
    with pytest.raises(AcceptanceFailure):
        write_contract(tmp_path, value)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_strict_utf8_and_contract_size_cap(tmp_path, encoding):
    value = valid_document(tmp_path)
    path = tmp_path / "contract.json"
    path.write_bytes(json.dumps(value).encode(encoding))
    with pytest.raises(AcceptanceFailure):
        load_contract(path, candidate_root=tmp_path / "source")


def _baseline_inputs(tmp_path, value, constraints):
    baseline = {
        "schema_version": 2,
        "kind": "acceptance_policy_baseline",
        "constraints": constraints,
    }
    path = tmp_path / "source/baseline.json"
    path.write_text(json.dumps(baseline))
    value["input"]["files"].append(
        measure_file(path, 1048576, file_id="policy").descriptor("baseline.json")
    )
    value["input"]["sha256"] = source_digest(value["input"]["files"])
    value["policy_baseline"] = "policy"
    inputs = verify_bundle(tmp_path / "source", value["input"]["files"], max_file_bytes=1048576)
    return inputs


def test_declared_baseline_is_enforced_not_just_hashed(tmp_path):
    from acceptance.contract import _BASELINE_FIELDS

    value = valid_document(tmp_path)
    constraints = {key: deepcopy(value[key]) for key in _BASELINE_FIELDS}
    inputs = _baseline_inputs(tmp_path, value, constraints)
    contract = write_contract(tmp_path, value)
    enforce_baseline(contract, inputs)
    value["budget"]["max_files"] += 1
    changed = write_contract(tmp_path, value)
    with pytest.raises(AcceptanceFailure, match="baseline"):
        enforce_baseline(changed, inputs)


@pytest.mark.parametrize("size_delta", [0, 1])
def test_baseline_bytes_must_match_frozen_descriptor_and_bound_file(tmp_path, size_delta):
    from acceptance.contract import _BASELINE_FIELDS

    value = valid_document(tmp_path)
    constraints = {key: deepcopy(value[key]) for key in _BASELINE_FIELDS}
    inputs = _baseline_inputs(tmp_path, value, constraints)
    contract = write_contract(tmp_path, value)
    enforce_baseline(contract, inputs)

    baseline_path = tmp_path / "source/baseline.json"
    original = baseline_path.read_bytes()
    baseline_path.write_bytes(b"x" * (len(original) + size_delta))
    with pytest.raises(AcceptanceFailure) as caught:
        enforce_baseline(contract, inputs)
    assert caught.value.code == "hash_mismatch"

    changed = measure_file(baseline_path, 1048576, file_id="policy")
    replaced = dict(inputs)
    replaced["policy"] = changed
    with pytest.raises(AcceptanceFailure) as caught:
        enforce_baseline(contract, replaced)
    assert caught.value.code == "hash_mismatch"


def test_baseline_distinguishes_boolean_from_integer(tmp_path):
    from acceptance.contract import _BASELINE_FIELDS

    value = valid_document(tmp_path)
    value["limits"]["open_files"] = 1
    constraints = {key: deepcopy(value[key]) for key in _BASELINE_FIELDS}
    constraints["limits"]["open_files"] = True
    inputs = _baseline_inputs(tmp_path, value, constraints)
    contract = write_contract(tmp_path, value)
    with pytest.raises(AcceptanceFailure, match="baseline"):
        enforce_baseline(contract, inputs)


def test_contract_path_dot_dot_spelling_cannot_bypass_candidate_ownership(tmp_path):
    value = valid_document(tmp_path)
    path = tmp_path / "source/contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    (tmp_path / "detour").mkdir()
    with pytest.raises(AcceptanceFailure, match=r"\.\."):
        load_contract(tmp_path / "detour/../source/contract.json", candidate_root=tmp_path / "source")


def test_candidate_root_symlink_cannot_bypass_candidate_ownership(tmp_path):
    value = valid_document(tmp_path)
    path = tmp_path / "source/contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    alias = tmp_path / "source-alias"
    alias.symlink_to(tmp_path / "source", target_is_directory=True)
    with pytest.raises(AcceptanceFailure, match="outside candidate"):
        load_contract(path, candidate_root=alias)


def test_prospective_candidate_root_need_not_exist(tmp_path):
    value = valid_document(tmp_path)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    contract = load_contract(path, candidate_root=tmp_path / "prospective-source")
    assert contract.artifact_kind == "blend_native"


def test_huge_timeout_is_typed_contract_failure_for_direct_and_loaded_validation(tmp_path):
    value = valid_document(tmp_path)
    value["limits"]["timeout_seconds"]["inspector"] = 10**400
    with pytest.raises(AcceptanceFailure) as direct:
        validate_document(value)
    assert direct.value.code == "contract_invalid"
    with pytest.raises(AcceptanceFailure) as constructed:
        Contract(value, "0" * 64)
    assert constructed.value.code == "contract_invalid"
    with pytest.raises(AcceptanceFailure) as loaded:
        write_contract(tmp_path, value)
    assert loaded.value.code == "contract_invalid"


@pytest.mark.parametrize(
    ("field", "bad_value"), [("main", []), ("tool_id", []), ("policy_baseline", {})]
)
def test_membership_identifiers_require_exact_shape(tmp_path, field, bad_value):
    value = valid_document(tmp_path)
    if field == "main":
        value["input"]["main"] = bad_value
    elif field == "tool_id":
        value["tools"][0]["id"] = bad_value
    else:
        value["policy_baseline"] = bad_value
    with pytest.raises(AcceptanceFailure) as direct:
        validate_document(value)
    assert direct.value.code == "contract_invalid"
    with pytest.raises(AcceptanceFailure) as loaded:
        write_contract(tmp_path, value)
    assert loaded.value.code == "contract_invalid"


@pytest.mark.parametrize(("name", "alias"), [("Candidate", "candidate"), ("é", "e\u0301")])
def test_contract_rejects_physical_candidate_alias(tmp_path, name, alias):
    value = valid_document(tmp_path)
    candidate, other = tmp_path / name, tmp_path / alias
    candidate.mkdir()
    if not other.exists() or not candidate.samefile(other):
        pytest.skip("test filesystem does not support this directory alias")
    path = candidate / "nested" / "contract.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(AcceptanceFailure, match="outside candidate") as caught:
        load_contract(path, candidate_root=other)
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("prospective", [False, True])
def test_contract_accepts_outside_nfd_candidate(tmp_path, prospective):
    value = valid_document(tmp_path)
    candidate = tmp_path / "e\u0301-candidate"
    if not prospective:
        candidate.mkdir()
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert load_contract(path, candidate_root=candidate).artifact_kind == "blend_native"
    assert candidate.exists() != prospective
