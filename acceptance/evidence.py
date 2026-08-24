"""规范 §7.3 summary.json 的写入。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from acceptance.contract import Contract
from acceptance.decide import Verdict
from acceptance.primitives import write_json_exclusive


def summary_document(
    *,
    contract: Contract | None,
    verdict: Verdict | None,
    achieved_grade: str,
    platform_key: str,
    started_at: str,
    completed_at: str,
    evidence_manifest: list[dict[str, object]],
    runner_provenance: dict[str, Any],
    failure_code: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if verdict is not None:
        for outcome in verdict.outcomes:
            checks.append({
                "id": outcome.id,
                "stage": outcome.stage,
                "raw_status": outcome.raw_status,
                "effective_status": outcome.effective_status,
                "accepted": outcome.accepted,
                "tool_id": outcome.tool_id,
                "tool_version": outcome.tool_version,
                "findings": [
                    {"code": f.code, "severity": f.severity, "pointer": f.pointer,
                     "offset": f.offset, "disposition": f.disposition,
                     "detail": f.detail}
                    for f in outcome.findings
                ],
                "source_truncated": outcome.source_truncated,
                "detail": outcome.findings[0].detail if outcome.findings else None,
                "metrics": None,
            })
    success = bool(verdict is not None and verdict.success)
    return {
        "schema_version": 1,
        "kind": "asset_acceptance",
        "success": success,
        "contract_id": None if contract is None else contract.raw.get("contract_id"),
        "contract_digest": None if contract is None else contract.digest,
        "artifact_kind": None if contract is None else contract.artifact_kind,
        "required_isolation_grade": (
            None if contract is None else contract.required_isolation_grade),
        "achieved_isolation_grade": achieved_grade,
        "platform_key": platform_key,
        "started_at": started_at,
        "completed_at": completed_at,
        "stages": {},
        "checks": checks,
        "evidence_manifest": evidence_manifest,
        "advisories": [],
        "failure_code": (
            failure_code if verdict is None else verdict.failure_code),
        "failed_check_ids": [] if verdict is None else verdict.failed_check_ids,
        "error": error,
        "runner_provenance": runner_provenance,
    }


def write_summary(root: Path, document: dict[str, Any]) -> Path:
    path = root / "summary.json"
    write_json_exclusive(path, document)
    return path
