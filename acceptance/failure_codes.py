"""规范 §7.2 的 failure-code family,元组顺序即优先级(靠前者优先)。"""
from __future__ import annotations

FAILURE_FAMILIES: tuple[str, ...] = (
    "contract_invalid",
    "toolchain_mismatch",
    "tool_crashed",
    "tool_output_invalid",
    "stale_result_file",
    "zero_checks_collected",
    "expected_set_mismatch",
    "forged_not_applicable",
    "forged_disposition",
    "evidence_missing",
    "evidence_truncated",
    "hash_mismatch",
    "isolation_insufficient",
    "resource_limit_exceeded",
    "runner_internal_error",
    "check_failed",
)

INFRA_FAMILIES: tuple[str, ...] = tuple(f for f in FAILURE_FAMILIES if f != "check_failed")

_PRIORITY = {family: index for index, family in enumerate(FAILURE_FAMILIES)}


def family_priority(code: str) -> int:
    if code not in _PRIORITY:
        raise ValueError(f"unknown failure family: {code}")
    return _PRIORITY[code]
