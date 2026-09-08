from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from acceptance import check_registry as reg, failure_codes as fc
from acceptance.contract import Contract
from acceptance.primitives import AcceptanceFailure

_SPEC = {spec.id: spec for spec in reg.CHECKS}
_TERMINALS = {None, "Crash", "Missing", "NotTested"}


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    pointer: str | None = None
    offset: int | None = None
    detail: str | None = None
    disposition: str | None = None


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    id: str
    stage: str
    raw_status: str
    effective_status: str
    accepted: bool
    tool_id: str | None
    tool_version: str | None
    findings: tuple[Finding, ...]
    source_truncated: bool


@dataclass(frozen=True, slots=True)
class Gate:
    complete: bool
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class Verdict:
    success: bool
    failure_code: str | None
    failed_check_ids: tuple[str, ...] = ()
    outcomes: tuple[CheckOutcome, ...] = ()
    failed_gate_ids: tuple[str, ...] = ()
    gates: tuple[tuple[str, Gate], ...] = ()


def validate_finding(finding: Finding) -> None:
    if (
        type(finding) is not Finding
        or type(finding.code) is not str
        or not finding.code
        or finding.severity not in ("error", "warning", "info")
        or any(
            getattr(finding, key) is not None and type(getattr(finding, key)) is not str
            for key in ("pointer", "detail", "disposition")
        )
        or (
            finding.offset is not None
            and (type(finding.offset) is not int or finding.offset < 0)
        )
    ):
        raise AcceptanceFailure("tool_output_invalid", "invalid finding")


def aggregate(
    check_id: str,
    findings: list[Finding],
    *,
    contract: Contract,
    tool_id: str | None,
    tool_version: str | None,
    source_truncated: bool,
    terminal: str | None,
) -> CheckOutcome:
    if (
        type(check_id) is not str
        or (terminal is not None and type(terminal) is not str)
        or type(source_truncated) is not bool
        or check_id not in _SPEC
        or terminal not in _TERMINALS
    ):
        raise AcceptanceFailure("tool_output_invalid", "invalid aggregate identity/state")
    spec = _SPEC[check_id]
    if check_id in contract.na_check_ids:
        if (
            findings
            or terminal is not None
            or source_truncated
            or tool_id is not None
            or tool_version is not None
        ):
            raise AcceptanceFailure(
                "forged_not_applicable", "N/A cannot contain a job or its accident"
            )
        return CheckOutcome(
            check_id,
            spec.stage,
            "NotApplicableByContract",
            "NotApplicable",
            False,
            None,
            None,
            (),
            False,
        )
    tools = {tool["id"]: tool["version"] for tool in contract.raw["tools"]}
    if (
        type(tool_id) is not str
        or type(tool_version) is not str
        or tool_id not in tools
        or tool_version != tools[tool_id]
    ):
        raise AcceptanceFailure(
            "toolchain_mismatch", "outcome tool identity differs from contract"
        )
    normalized = []
    for finding in findings:
        validate_finding(finding)
        accepted = finding.severity == "warning" and contract.allowlisted(
            check_id, finding.code, tool_id, tool_version
        )
        disposition = "AcceptedWarning" if accepted else None
        if finding.disposition not in (None, disposition):
            raise AcceptanceFailure(
                "forged_disposition", "finding disposition is not policy-derived"
            )
        normalized.append(replace(finding, disposition=disposition))
    if terminal is not None:
        raw = terminal
    elif source_truncated:
        raw = "Truncated"
    elif any(finding.severity == "error" for finding in normalized):
        raw = "Fail"
    elif any(
        finding.severity == "warning" and finding.disposition is None
        for finding in normalized
    ):
        raw = "Warning"
    else:
        raw = "Pass"
    return CheckOutcome(
        check_id,
        spec.stage,
        raw,
        "Pass" if raw == "Pass" else "Fail",
        raw == "Pass" and any(finding.severity == "warning" for finding in normalized),
        tool_id,
        tool_version,
        tuple(normalized),
        source_truncated,
    )


def decide(
    *,
    contract: Contract,
    outcomes: list[CheckOutcome],
    actual_files: set[str],
    expected_files: set[str],
    achieved_grade: str,
    infra_failures: list[str],
    child_declared_na: set[str] | None = None,
) -> Verdict:
    triggered = list(infra_failures)
    if any(code not in fc.INFRA_FAMILIES for code in triggered):
        raise AcceptanceFailure(
            "runner_internal_error", "unknown infrastructure failure family"
        )
    if (
        achieved_grade != "local-trusted"
        or contract.required_isolation_grade != "local-trusted"
    ):
        triggered.append("isolation_insufficient")
    for outcome in outcomes:
        if (
            type(outcome) is not CheckOutcome
            or type(outcome.id) is not str
            or type(outcome.raw_status) is not str
            or (outcome.tool_id is not None and type(outcome.tool_id) is not str)
            or (
                outcome.tool_version is not None
                and type(outcome.tool_version) is not str
            )
        ):
            raise AcceptanceFailure("tool_output_invalid", "unknown internal outcome")
    ids = [outcome.id for outcome in outcomes]
    if not ids:
        triggered.append("zero_checks_collected")
    if len(set(ids)) != len(ids) or set(ids) != set(_SPEC) or actual_files != expected_files:
        triggered.append("expected_set_mismatch")
    if child_declared_na:
        triggered.append("forged_not_applicable")
    incomplete = False
    for outcome in outcomes:
        if type(outcome.accepted) is not bool or type(outcome.findings) is not tuple:
            raise AcceptanceFailure("tool_output_invalid", "unknown internal outcome")
        rebuilt = aggregate(
            outcome.id,
            list(outcome.findings),
            contract=contract,
            tool_id=outcome.tool_id,
            tool_version=outcome.tool_version,
            source_truncated=outcome.source_truncated,
            terminal=outcome.raw_status if outcome.raw_status in _TERMINALS else None,
        )
        if outcome != rebuilt:
            raise AcceptanceFailure("tool_output_invalid", "inconsistent internal outcome")
        incomplete = incomplete or outcome.raw_status == "NotTested"
        failure = {
            "Crash": "tool_crashed",
            "Missing": "evidence_missing",
            "Truncated": "evidence_truncated",
        }.get(outcome.raw_status)
        if failure:
            triggered.append(failure)
    failed = tuple(
        sorted(
            (outcome.id for outcome in outcomes if outcome.raw_status in ("Fail", "Warning")),
            key=lambda key: reg.sort_key(_SPEC[key]),
        )
    )
    code = (
        min(triggered, key=fc.family_priority)
        if triggered
        else "check_failed"
        if failed
        else "runner_internal_error"
        if incomplete
        else None
    )
    return Verdict(code is None, code, failed, tuple(outcomes))


def decide_technical(
    base: Verdict, *, expected_gate_ids: tuple[str, ...], gates: Mapping[str, Gate]
) -> Verdict:
    triggered = [] if base.failure_code in (None, "check_failed") else [base.failure_code]
    if set(gates) != set(expected_gate_ids) or len(set(expected_gate_ids)) != len(
        expected_gate_ids
    ):
        triggered.append("expected_set_mismatch")
    failed = []
    incomplete = False
    for gate_id, gate in gates.items():
        if (
            type(gate) is not Gate
            or type(gate.complete) is not bool
            or type(gate.findings) is not tuple
        ):
            raise AcceptanceFailure("tool_output_invalid", "invalid internal gate")
        for finding in gate.findings:
            validate_finding(finding)
            if finding.disposition is not None:
                raise AcceptanceFailure(
                    "forged_disposition",
                    "gate finding has no implicit warning allowance",
                )
        incomplete = incomplete or not gate.complete
        if gate.complete and any(
            finding.severity in ("error", "warning") for finding in gate.findings
        ):
            failed.append(gate_id)
    code: str | None
    if triggered:
        code = min(triggered, key=fc.family_priority)
    else:
        code = (
            "check_failed"
            if base.failure_code == "check_failed" or failed
            else "runner_internal_error"
            if incomplete
            else None
        )
    return Verdict(
        code is None,
        code,
        base.failed_check_ids,
        base.outcomes,
        tuple(sorted(failed)),
        tuple(sorted(gates.items())),
    )


def technical_state(verdict: Verdict) -> str:
    if verdict.success:
        return "NEEDS_REVIEW"
    complete = all(
        outcome.raw_status in ("Pass", "Fail", "Warning", "NotApplicableByContract")
        for outcome in verdict.outcomes
    ) and all(gate.complete for _, gate in verdict.gates)
    return (
        "REJECTED"
        if complete and verdict.failure_code == "check_failed"
        else "UNVERIFIED"
    )
