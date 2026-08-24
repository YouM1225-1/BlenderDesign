"""coordinator 自算的三个 stage(规范 §7.1 中 writer == coordinator 且不依赖外部进程的部分)。"""
from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from acceptance.contract import Contract
from acceptance.decide import Finding


def _error(code: str, detail: str) -> Finding:
    return Finding(code=code, severity="error", detail=detail)


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


def run_r1(contract: Contract, input_path: Path) -> dict[str, list[Finding]]:
    """R1:输入身份与预算(规范 §7.1)。

    lstat() 只证明路径存在与其类型,不证明内容可读(Task 7 修过同一陷阱:chmod 000 的
    文件 is_file()/lstat() 均成立,只有真正 open()/read() 才会因权限被拒)。故对确认为
    普通文件的路径额外尝试读取一字节;symlink/设备等已由下面的类型判定单独报告,不在此
    重复探测,避免对 FIFO 等特殊文件的读取造成阻塞。
    """
    digest_findings: list[Finding] = []
    link_findings: list[Finding] = []
    size_findings: list[Finding] = []
    try:
        info = input_path.lstat()
    except OSError as exc:
        digest_findings.append(_error("input_missing", f"cannot stat input: {exc}"))
        return {"r1.input.digest_recorded": digest_findings,
                "r1.input.no_link_or_device": link_findings,
                "r1.input.size_within_limit": size_findings}
    if stat.S_ISLNK(info.st_mode):
        link_findings.append(_error("input_is_symlink", str(input_path)))
    elif not stat.S_ISREG(info.st_mode):
        link_findings.append(_error("input_not_regular_file", str(input_path)))
    else:
        try:
            with input_path.open("rb") as handle:
                handle.read(1)
        except OSError as exc:
            digest_findings.append(_error("input_unreadable", f"cannot read input: {exc}"))
    limit = int(contract.raw["budget"]["max_file_bytes"])
    if info.st_size > limit:
        size_findings.append(
            _error("input_too_large", f"{info.st_size} bytes exceeds {limit}"))
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
