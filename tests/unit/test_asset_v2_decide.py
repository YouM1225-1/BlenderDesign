from dataclasses import replace
from typing import cast

import pytest

from acceptance import check_registry as reg
from acceptance.decide import (
    CheckOutcome,
    Finding,
    Gate,
    aggregate,
    decide,
    decide_technical,
    technical_state,
)
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document, write_contract


def acceptance_version(contract):
    return next(t["version"] for t in contract.raw["tools"] if t["id"] == "acceptance")


def complete_outcomes(contract):
    version = acceptance_version(contract)
    return [
        aggregate(
            spec.id,
            [],
            contract=contract,
            tool_id=None if spec.id in contract.na_check_ids else "acceptance",
            tool_version=None if spec.id in contract.na_check_ids else version,
            source_truncated=False,
            terminal=None,
        )
        for spec in reg.CHECKS
    ]


def verdict(contract, outcomes):
    return decide(
        contract=contract,
        outcomes=outcomes,
        actual_files={"evidence"},
        expected_files={"evidence"},
        achieved_grade="local-trusted",
        infra_failures=[],
    )


@pytest.mark.parametrize(
    "change", ["unknown_raw", "wrong_stage", "truncated_pass", "accepted_alias"]
)
def test_internal_outcomes_do_not_bypass_parser(tmp_path, change):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    if change == "unknown_raw":
        outcomes[0] = replace(outcomes[0], raw_status="UnknownStatus")
    elif change == "wrong_stage":
        outcomes[0] = replace(outcomes[0], stage="R9")
    elif change == "truncated_pass":
        outcomes[0] = replace(outcomes[0], source_truncated=True)
    else:
        outcomes[0] = replace(outcomes[0], accepted=1)
    with pytest.raises(AcceptanceFailure, match="outcome"):
        verdict(contract, outcomes)


@pytest.mark.parametrize(
    ("field", "value"),
    (("id", []), ("raw_status", []), ("tool_id", [])),
)
def test_malformed_outcome_fields_have_typed_failure(tmp_path, field, value):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    outcomes[0] = replace(outcomes[0], **{field: value})

    with pytest.raises(AcceptanceFailure) as caught:
        verdict(contract, outcomes)

    assert caught.value.code == "tool_output_invalid"


def test_non_outcome_has_typed_failure(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    outcomes[0] = cast(CheckOutcome, object())

    with pytest.raises(AcceptanceFailure) as caught:
        verdict(contract, outcomes)

    assert caught.value.code == "tool_output_invalid"


@pytest.mark.parametrize(
    ("malformed", "expected_code"),
    (("check_id", "tool_output_invalid"), ("terminal", "tool_output_invalid"),
     ("tool_id", "toolchain_mismatch")),
)
def test_aggregate_unhashable_inputs_have_typed_failure(
    tmp_path, malformed, expected_code
):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    check_id = next(spec.id for spec in reg.CHECKS if spec.id not in contract.na_check_ids)
    version = acceptance_version(contract)
    values = {
        "check_id": check_id,
        "terminal": None,
        "tool_id": "acceptance",
    }
    values[malformed] = []

    with pytest.raises(AcceptanceFailure) as caught:
        aggregate(
            values["check_id"],
            [],
            contract=contract,
            tool_id=values["tool_id"],
            tool_version=version,
            source_truncated=False,
            terminal=values["terminal"],
        )

    assert caught.value.code == expected_code


def test_aggregate_valid_identity_passes(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    check_id = next(spec.id for spec in reg.CHECKS if spec.id not in contract.na_check_ids)
    outcome = aggregate(
        check_id,
        [],
        contract=contract,
        tool_id="acceptance",
        tool_version=acceptance_version(contract),
        source_truncated=False,
        terminal=None,
    )

    assert outcome.raw_status == "Pass"


def test_na_cannot_erase_accidents_and_fail_not_tested_is_unverified(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    with pytest.raises(AcceptanceFailure, match="N/A"):
        aggregate(
            contract.na_check_ids[0],
            [],
            contract=contract,
            tool_id=None,
            tool_version=None,
            source_truncated=False,
            terminal="Crash",
        )
    outcomes = complete_outcomes(contract)
    for index, terminal in ((0, None), (1, "NotTested")):
        original = outcomes[index]
        outcomes[index] = aggregate(
            original.id,
            [Finding("bad", "error")] if index == 0 else [],
            contract=contract,
            tool_id=original.tool_id,
            tool_version=original.tool_version,
            source_truncated=False,
            terminal=terminal,
        )
    result = verdict(contract, outcomes)
    assert not result.success and result.failure_code == "check_failed"
    assert technical_state(result) == "UNVERIFIED"
    assert outcomes[0].id in result.failed_check_ids


def test_required_gates_cannot_be_dropped_or_compensated(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    base = verdict(contract, complete_outcomes(contract))
    assert base.success
    assert (
        decide_technical(base, expected_gate_ids=("reference",), gates={}).failure_code
        == "expected_set_mismatch"
    )
    gate = Gate(False, (Finding("unsupported", "error"),))
    assert (
        decide_technical(
            base, expected_gate_ids=("reference",), gates={"reference": gate}
        ).failure_code
        == "runner_internal_error"
    )
    gate = Gate(True, (Finding("missing_part", "error"),))
    result = decide_technical(
        base, expected_gate_ids=("reference",), gates={"reference": gate}
    )
    assert not result.success and result.failure_code == "check_failed"
    assert result.failed_gate_ids == ("reference",)


def test_complete_failure_and_incomplete_gate_keeps_code_but_is_unverified(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    original = outcomes[0]
    outcomes[0] = aggregate(
        original.id,
        [Finding("bad", "error")],
        contract=contract,
        tool_id=original.tool_id,
        tool_version=original.tool_version,
        source_truncated=False,
        terminal=None,
    )
    result = decide_technical(
        verdict(contract, outcomes),
        expected_gate_ids=("reference",),
        gates={"reference": Gate(False)},
    )
    assert result.failure_code == "check_failed"
    assert technical_state(result) == "UNVERIFIED"
