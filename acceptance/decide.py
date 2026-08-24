"""规范 §2.5 与 §2.6 的唯一实现处。其他模块不得复制判定逻辑。"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from acceptance import check_registry as reg
from acceptance import failure_codes as fc
from acceptance.contract import Contract
from acceptance.primitives import AcceptanceFailure

_GRADE_ORDER = {"local-trusted": 0, "isolated": 1, "attested": 2}
_VALID_SEVERITIES = frozenset({"error", "warning", "info"})
_VALID_TERMINALS = frozenset({None, "Crash", "Missing", "NotTested"})


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str                 # "error" | "warning" | "info"
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
class Verdict:
    success: bool
    failure_code: str | None
    failed_check_ids: list[str] = field(default_factory=list)
    outcomes: tuple[CheckOutcome, ...] = ()


_SPEC_BY_ID = {spec.id: spec for spec in reg.CHECKS}
_VALID_ARTIFACT_KINDS = frozenset(spec.kind for spec in reg.CHECKS if spec.kind != "all")


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
    """规范 §2.5 第一步与第二步。terminal 为 coordinator 观测到的 Crash/Missing/NotTested。"""
    spec = _SPEC_BY_ID.get(check_id)
    if spec is None:
        raise AcceptanceFailure(
            "expected_set_mismatch", f"unknown check id: {check_id}")
    if terminal not in _VALID_TERMINALS:
        raise AcceptanceFailure(
            "tool_output_invalid", f"unknown terminal status: {terminal!r}")
    dispositioned: list[Finding] = []
    for item in findings:
        if item.severity not in _VALID_SEVERITIES:
            raise AcceptanceFailure(
                "tool_output_invalid",
                f"unknown finding severity: {item.severity!r}")
        accepted = (
            item.severity == "warning"
            and tool_id is not None
            and tool_version is not None
            and contract.allowlisted(check_id, item.code, tool_id, tool_version)
        )
        dispositioned.append(
            replace(item, disposition="AcceptedWarning" if accepted else None))

    accepted_flag = False
    if check_id in contract.na_check_ids:
        raw = "NotApplicableByContract"
    elif terminal == "Crash":
        raw = "Crash"
    elif terminal in ("Missing", "NotTested"):
        raw = terminal
    elif source_truncated:
        raw = "Truncated"
    elif any(f.severity == "error" for f in dispositioned):
        raw = "Fail"
    elif any(f.severity == "warning" and f.disposition is None for f in dispositioned):
        raw = "Warning"
    else:
        raw = "Pass"
        warnings = [f for f in dispositioned if f.severity == "warning"]
        accepted_flag = bool(warnings)

    if raw == "Pass":
        effective = "Pass"
    elif raw == "NotApplicableByContract":
        effective = "NotApplicable"
    else:
        effective = "Fail"

    return CheckOutcome(
        id=check_id, stage=spec.stage, raw_status=raw, effective_status=effective,
        accepted=accepted_flag, tool_id=tool_id, tool_version=tool_version,
        findings=tuple(dispositioned), source_truncated=source_truncated,
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
    """规范 §2.6 的十条放行条件。

    infra_failures 由 coordinator 在编排过程中累积(如 stale_result_file、hash_mismatch)。
    child_declared_na 是**子进程在其 result 里自称 N/A 的 check ID 集**,用于条款 6 的
    伪造检出;coordinator 解析 result 文件时填入(本计划尚无 result 解析,故默认空集,
    对应测试见 test_forged_not_applicable_is_detected)。
    """
    child_declared_na = child_declared_na or set()
    # 规范 §7.2 规则 1:**先把全部触发的 infra family 收齐,再取优先级最高的一个**。
    # 不能按源码书写顺序 early-return —— 那样 "isolation 不足 + 子进程崩溃" 会报
    # isolation_insufficient(优先级 12)而不是 tool_crashed(优先级 2)。
    for item in infra_failures:
        if item not in fc.INFRA_FAMILIES:
            raise AcceptanceFailure(
                "runner_internal_error", f"unknown infra failure family: {item!r}")
    triggered: list[str] = list(infra_failures)

    if achieved_grade not in _GRADE_ORDER:
        raise AcceptanceFailure("contract_invalid", f"unknown grade: {achieved_grade}")
    if contract.required_isolation_grade not in _GRADE_ORDER:
        raise AcceptanceFailure(
            "contract_invalid",
            f"unknown required_isolation_grade: {contract.required_isolation_grade}")
    if _GRADE_ORDER[achieved_grade] < _GRADE_ORDER[contract.required_isolation_grade]:
        triggered.append("isolation_insufficient")

    if contract.artifact_kind not in _VALID_ARTIFACT_KINDS:
        raise AcceptanceFailure(
            "contract_invalid", f"unknown artifact_kind: {contract.artifact_kind!r}")
    try:
        na_ids = set(contract.na_check_ids)
    except TypeError as exc:
        raise AcceptanceFailure(
            "contract_invalid", f"na_check_ids is not a set of hashable ids: {exc}") from exc
    if na_ids != set(reg.na_check_ids(contract.artifact_kind)):
        raise AcceptanceFailure(
            "contract_invalid",
            "na_check_ids does not match the derived not-applicable set for artifact_kind")

    expected_ids = {c.id for c in reg.checks_for_kind(contract.artifact_kind)}
    expected_ids |= na_ids
    actual_ids = [o.id for o in outcomes]
    if not actual_ids:
        triggered.append("zero_checks_collected")
    if (len(set(actual_ids)) != len(actual_ids)
            or set(actual_ids) != expected_ids
            or actual_files != expected_files):
        triggered.append("expected_set_mismatch")

    # 规范 §2.6 条款 6:子进程声明的 N/A 若不在合同 N/A 集内即为伪造。
    if set(child_declared_na) - na_ids:
        triggered.append("forged_not_applicable")

    # 规范 §2.6 条款 7:Crash/Missing/Truncated 一律阻断,不分 required。
    statuses = {o.raw_status for o in outcomes}
    if "Crash" in statuses:
        triggered.append("tool_crashed")
    if "Missing" in statuses:
        triggered.append("evidence_missing")
    if "Truncated" in statuses:
        triggered.append("evidence_truncated")

    if triggered:
        return Verdict(False, min(triggered, key=fc.family_priority), [], tuple(outcomes))

    # 只有"实际被评估过并被拒"的 check 进 failed_check_ids;NotTested 表示该 stage
    # 根本没跑,把它算作"资产被拒收"会与规范 §7.2 的第一分类冲突(见下)。
    failed = sorted(
        (o.id for o in outcomes
         if o.effective_status == "Fail" and o.raw_status in ("Fail", "Warning")),
        key=lambda i: reg.sort_key(_SPEC_BY_ID[i]),
    )
    if failed:
        return Verdict(False, "check_failed", failed, tuple(outcomes))

    # 无人失败却有 NotTested,说明 coordinator 没跑完自己的计划 —— fail-closed 兜底。
    if any(o.raw_status == "NotTested" for o in outcomes):
        return Verdict(False, "runner_internal_error", [], tuple(outcomes))

    return Verdict(True, None, [], tuple(outcomes))
