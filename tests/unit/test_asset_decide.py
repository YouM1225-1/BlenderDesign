import json
from pathlib import Path

import pytest

from acceptance import check_registry as reg
from acceptance.contract import load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document

CHECK = "r2.material.slots_resolved"


def _contract(tmp_path: Path, allowlist: list[dict[str, str]] | None = None):
    value = valid_document(tmp_path)
    version = next(t["version"] for t in value["tools"] if t["id"] == "acceptance")
    value["warning_allowlist"] = [
        {**row, "tool_version": version} for row in (allowlist or [])
    ]
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "source")


def _warn(code: str = "empty_material_slot") -> Finding:
    return Finding(code=code, severity="warning", pointer=None, offset=None, detail=None)


def _err() -> Finding:
    return Finding(code="bad", severity="error", pointer=None, offset=None, detail=None)


def _identity(contract, check_id=CHECK):
    if check_id in contract.na_check_ids:
        return None, None
    version = next(
        t["version"] for t in contract.raw["tools"] if t["id"] == "acceptance"
    )
    return "acceptance", version


def _agg(contract, findings, **kw):
    tool_id, tool_version = _identity(contract)
    return aggregate(CHECK, findings, contract=contract, tool_id=tool_id,
                     tool_version=tool_version, source_truncated=False,
                     terminal=None, **kw)


def test_no_findings_is_pass(tmp_path):
    outcome = _agg(_contract(tmp_path), [])
    assert (outcome.raw_status, outcome.effective_status, outcome.accepted) == (
        "Pass", "Pass", False)


def test_error_finding_is_fail(tmp_path):
    outcome = _agg(_contract(tmp_path), [_err()])
    assert outcome.raw_status == "Fail" and outcome.effective_status == "Fail"


def test_unlisted_warning_is_fail(tmp_path):
    outcome = _agg(_contract(tmp_path), [_warn()])
    assert outcome.raw_status == "Warning" and outcome.effective_status == "Fail"


def test_all_warnings_allowlisted_is_pass_and_accepted(tmp_path):
    allow = [{"check_id": CHECK, "warning_code": "empty_material_slot",
              "tool_id": "acceptance", "tool_version": "acc-000000000000"}]
    outcome = _agg(_contract(tmp_path, allow), [_warn()])
    assert (outcome.raw_status, outcome.effective_status, outcome.accepted) == (
        "Pass", "Pass", True)
    assert outcome.findings[0].severity == "warning"
    assert outcome.findings[0].disposition == "AcceptedWarning"


def test_mixed_allowlisted_and_not_is_fail(tmp_path):
    allow = [{"check_id": CHECK, "warning_code": "empty_material_slot",
              "tool_id": "acceptance", "tool_version": "acc-000000000000"}]
    outcome = _agg(_contract(tmp_path, allow), [_warn(), _warn("packed_dependency")])
    assert outcome.raw_status == "Warning" and outcome.effective_status == "Fail"


def test_info_only_does_not_set_accepted(tmp_path):
    info = Finding(code="note", severity="info", pointer=None, offset=None, detail=None)
    outcome = _agg(_contract(tmp_path), [info])
    assert outcome.raw_status == "Pass" and outcome.accepted is False


def test_truncated_beats_error(tmp_path):
    contract = _contract(tmp_path)
    tool_id, tool_version = _identity(contract)
    outcome = aggregate(CHECK, [_err()], contract=contract,
                        tool_id=tool_id, tool_version=tool_version,
                        source_truncated=True, terminal=None)
    assert outcome.raw_status == "Truncated" and outcome.effective_status == "Fail"


@pytest.mark.parametrize("terminal", ["Crash", "Missing"])
def test_terminal_states_beat_findings(tmp_path, terminal):
    contract = _contract(tmp_path)
    tool_id, tool_version = _identity(contract)
    outcome = aggregate(CHECK, [], contract=contract, tool_id=tool_id,
                        tool_version=tool_version, source_truncated=False,
                        terminal=terminal)
    assert outcome.raw_status == terminal and outcome.effective_status == "Fail"


def test_not_applicable_cannot_hide_accidents(tmp_path):
    contract = _contract(tmp_path)
    na_id = contract.na_check_ids[0]
    with pytest.raises(AcceptanceFailure) as caught:
        aggregate(na_id, [_err()], contract=contract, tool_id=None,
                  tool_version=None, source_truncated=True,
                  terminal="Missing")
    assert caught.value.code == "forged_not_applicable"


def _all_pass(contract):
    outcomes = []
    for spec in reg.CHECKS:
        tool_id, tool_version = _identity(contract, spec.id)
        outcomes.append(aggregate(
            spec.id, [], contract=contract, tool_id=tool_id,
            tool_version=tool_version, source_truncated=False, terminal=None))
    return outcomes


def test_all_pass_releases(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.success is True and verdict.failure_code is None


def test_single_failed_check_yields_check_failed(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    tool_id, tool_version = _identity(contract, outcomes[0].id)
    outcomes[0] = aggregate(outcomes[0].id, [_err()], contract=contract,
                            tool_id=tool_id, tool_version=tool_version,
                            source_truncated=False, terminal=None)
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.success is False
    assert verdict.failure_code == "check_failed"
    assert verdict.failed_check_ids == (outcomes[0].id,)


def test_infra_failure_outranks_check_failed(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    tool_id, tool_version = _identity(contract, outcomes[0].id)
    outcomes[0] = aggregate(outcomes[0].id, [_err()], contract=contract,
                            tool_id=tool_id, tool_version=tool_version,
                            source_truncated=False, terminal=None)
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted",
                     infra_failures=["hash_mismatch", "tool_crashed"])
    assert verdict.failure_code == "tool_crashed"   # 优先级更高者胜出


def test_file_set_mismatch_fails(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary", "extra"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "expected_set_mismatch"


def test_insufficient_isolation_fails(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted",
                     infra_failures=["isolation_insufficient"])
    assert verdict.failure_code == "isolation_insufficient"


def test_highest_priority_infra_family_wins(tmp_path):
    """规范 §7.2 规则 1:同时触发多个 infra family 时取优先级最高者。"""
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    tool_id, tool_version = _identity(contract, outcomes[0].id)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=tool_id,
                            tool_version=tool_version, source_truncated=False,
                            terminal="Crash")                   # 优先级 2
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted",
                     infra_failures=["isolation_insufficient"])
    assert verdict.failure_code == "tool_crashed"


def test_missing_outranks_truncated(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    tool_id, tool_version = _identity(contract, outcomes[0].id)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=tool_id,
                            tool_version=tool_version, source_truncated=True,
                            terminal=None)
    tool_id, tool_version = _identity(contract, outcomes[1].id)
    outcomes[1] = aggregate(outcomes[1].id, [], contract=contract, tool_id=tool_id,
                            tool_version=tool_version, source_truncated=False,
                            terminal="Missing")
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "evidence_missing"   # 优先级 9 高于 10


def test_forged_not_applicable_is_detected(tmp_path):
    """规范 §2.6 条款 6:子进程自称 N/A 但该 ID 不在合同 N/A 集内。"""
    contract = _contract(tmp_path)
    applicable = reg.checks_for_kind(contract.artifact_kind)[0].id
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[],
                     child_declared_na={applicable})
    assert verdict.failure_code == "forged_not_applicable"


def test_not_tested_without_any_failure_is_runner_error(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    tool_id, tool_version = _identity(contract, outcomes[0].id)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=tool_id,
                            tool_version=tool_version, source_truncated=False,
                            terminal="NotTested")
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "runner_internal_error"
    assert verdict.failed_check_ids == ()


def test_unknown_check_id_is_rejected(tmp_path):
    with pytest.raises(AcceptanceFailure) as caught:
        aggregate("r9.bogus.id", [], contract=_contract(tmp_path), tool_id=None,
                  tool_version=None, source_truncated=False, terminal=None)
    assert caught.value.code == "tool_output_invalid"


def test_zero_checks_is_rejected(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=[],
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "zero_checks_collected"


@pytest.mark.parametrize("bad_severity", ["CRITICAL", ""])
def test_invalid_severity_is_rejected(tmp_path, bad_severity):
    """fail-closed:非法 severity(非 error/warning/info)必须拒绝,不能被静默当通过。"""
    finding = Finding(code="x", severity=bad_severity, pointer=None, offset=None, detail=None)
    with pytest.raises(AcceptanceFailure) as caught:
        _agg(_contract(tmp_path), [finding])
    assert caught.value.code == "tool_output_invalid"


def test_invalid_required_isolation_grade_is_rejected(tmp_path):
    value = valid_document(tmp_path)
    value["required_isolation_grade"] = "totally-bogus-grade"
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "source")
    assert caught.value.code == "contract_invalid"


def test_failed_check_ids_sorted_by_registry_order(tmp_path):
    """按注册表 sort_key(stage, order, id)排序,不是字典序:dependency 字典序在前但 order 更大。"""
    contract = _contract(tmp_path)
    dependency_id = "r2.dependency.all_present"
    outcomes = _all_pass(contract)
    by_id = {o.id: i for i, o in enumerate(outcomes)}
    for check_id in (CHECK, dependency_id):
        tool_id, tool_version = _identity(contract, check_id)
        outcomes[by_id[check_id]] = aggregate(
            check_id, [_err()], contract=contract, tool_id=tool_id,
            tool_version=tool_version,
            source_truncated=False, terminal=None)
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "check_failed"
    assert verdict.failed_check_ids == (CHECK, dependency_id)


def test_duplicate_check_id_is_expected_set_mismatch(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    outcomes.append(outcomes[0])   # 重复 check id,而非未知 id
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "expected_set_mismatch"


def test_crash_outranks_missing(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    tool_id, tool_version = _identity(contract, outcomes[0].id)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=tool_id,
                            tool_version=tool_version, source_truncated=False,
                            terminal="Crash")
    tool_id, tool_version = _identity(contract, outcomes[1].id)
    outcomes[1] = aggregate(outcomes[1].id, [], contract=contract, tool_id=tool_id,
                            tool_version=tool_version, source_truncated=False,
                            terminal="Missing")
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "tool_crashed"   # 优先级 2 高于 evidence_missing 的 9


def test_invalid_terminal_is_rejected(tmp_path):
    """fail-closed:terminal 只能是 None/Crash/Missing/NotTested,非法值不能静默落到 Pass(与 severity 同款闭集校验)。"""
    with pytest.raises(AcceptanceFailure) as caught:
        aggregate(CHECK, [], contract=_contract(tmp_path), tool_id=None,
                  tool_version=None, source_truncated=False, terminal="Bogus")
    assert caught.value.code == "tool_output_invalid"


def test_invalid_infra_failure_family_is_rejected(tmp_path):
    """裸 ValueError 必须变成 AcceptanceFailure:coordinator 拼错 infra failure family 名字属于 runner 内部错误。"""
    contract = _contract(tmp_path)
    with pytest.raises(AcceptanceFailure) as caught:
        decide(contract=contract, outcomes=_all_pass(contract),
               actual_files={"summary"}, expected_files={"summary"},
               achieved_grade="local-trusted", infra_failures=["totally_bogus_family"])
    assert caught.value.code == "runner_internal_error"


def test_check_failed_cannot_be_declared_as_infra_failure(tmp_path):
    """check_failed 只能由 decide() 自己从真实 outcomes 算出,不能由 coordinator 声明。"""
    contract = _contract(tmp_path)
    with pytest.raises(AcceptanceFailure) as caught:
        decide(contract=contract, outcomes=_all_pass(contract),
               actual_files={"summary"}, expected_files={"summary"},
               achieved_grade="local-trusted", infra_failures=["check_failed"])
    assert caught.value.code == "runner_internal_error"


def test_valid_infra_families_work_normally(tmp_path):
    """确认合法的 infra family(如 stale_result_file)仍照常工作。"""
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                    actual_files={"summary"}, expected_files={"summary"},
                    achieved_grade="local-trusted", infra_failures=["stale_result_file"])
    assert verdict.failure_code == "stale_result_file"


def test_invalid_artifact_kind_is_rejected(tmp_path):
    value = valid_document(tmp_path)
    value["artifact_kind"] = "Bogus"
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "source")
    assert caught.value.code == "contract_invalid"


def test_na_check_ids_inconsistent_with_kind_is_rejected(tmp_path):
    value = valid_document(tmp_path)
    applicable_id = reg.checks_for_kind(value["artifact_kind"])[0].id
    value["na_check_ids"].append(applicable_id)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "source")
    assert caught.value.code == "contract_invalid"
