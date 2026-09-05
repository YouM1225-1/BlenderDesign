"""coordinator 自算的三个 stage(规范 §7.1 中 writer == coordinator 且不依赖外部进程的部分)。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from acceptance.contract import Contract
from acceptance.decide import Finding


def _error(code: str, detail: str) -> Finding:
    return Finding(code=code, severity="error", detail=detail)


@dataclass(frozen=True, slots=True)
class InputResult:
    """一次安全打开得到的输入摘要、大小与失败证据。"""

    digest: str | None
    size: int | None
    digest_finding: Finding | None = None
    identity_finding: Finding | None = None


def run_r0(contract: Contract, *, tools_present: set[str]) -> dict[str, list[Finding]]:
    """schema 与 N/A 集在 load_contract 已强制,故此处只补工具存在性。"""
    missing = [tool["id"] for tool in contract.raw["tools"]
               if tool["id"] not in tools_present]
    return {
        "r0.contract.schema_closed": [],
        "r0.contract.tools_locked": [
            _error("tool_not_installed", f"locked tools not present: {sorted(missing)}")
        ] if missing else [],
        "r0.contract.na_set_declared": [],
    }


def run_r1(contract: Contract, input_result: InputResult) -> dict[str, list[Finding]]:
    """R1:只消费摘要读取时绑定到同一 fd/inode 的结果。"""
    digest_findings = [] if input_result.digest is not None else [
        input_result.digest_finding
        or _error("input_unreadable", "input digest was not completed")
    ]
    link_findings = (
        [] if input_result.identity_finding is None else [input_result.identity_finding]
    )
    size_findings: list[Finding] = []
    limit = contract.raw["budget"]["max_file_bytes"]
    if input_result.size is not None and input_result.size > limit:
        size_findings.append(
            _error("input_too_large", f"{input_result.size} bytes exceeds {limit}"))
    return {"r1.input.digest_recorded": digest_findings,
            "r1.input.no_link_or_device": link_findings,
            "r1.input.size_within_limit": size_findings}


def run_r5(
    contract: Contract,
    *,
    evidence_manifest: list[dict[str, Any]],
    recomputed_digest: str,
) -> dict[str, list[Finding]]:
    drift = [
        entry["id"] for entry in evidence_manifest
        if "actual_sha256" in entry and entry["actual_sha256"] != entry["sha256"]
    ]
    return {
        "r5.evidence.manifest_closed": [],
        "r5.evidence.hashes_match": [
            _error("evidence_hash_drift", f"hash drift on: {sorted(drift)}")
        ] if drift else [],
        "r5.contract.digest_stable": [
            _error("contract_digest_drift",
                   f"expected {contract.digest}, recomputed {recomputed_digest}")
        ] if recomputed_digest != contract.digest else [],
    }
