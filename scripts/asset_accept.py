#!/usr/bin/env python3
"""资产验收 coordinator(规范 §7)。P0 只支持 blend_native 与 interchange/glb。"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import stat
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import platform

from acceptance import check_registry as reg
from acceptance import toolchain
from acceptance.contract import Contract, load_contract
from acceptance.decide import Finding, Verdict, aggregate, decide
from acceptance.primitives import (
    AcceptanceFailure,
    write_json_exclusive,
    create_private_directory,
    normalise_new_root,
)

# Temporary legacy CLI helpers; Task 8 removes these with the CLI cutover.
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


ROOT = Path(__file__).resolve().parents[1]
_UNREADABLE_DIGEST = "0" * 64  # sha256 撞不出的哨兵值:标记"没能记录 digest"
# 规范 budget.max_file_bytes 的默认值(512 MiB)。_input_digest() 跑在 load_contract()
# 之前,拿不到每份合同各自的预算,故这里用一个固定硬上限,只为界住 provenance 摘要
# 自身的内存/IO,不替代 run_r1 的 size_within_limit(那才是真正的放行判定)。
_MAX_INPUT_DIGEST_BYTES = 512 * 1024 * 1024
_INPUT_DIGEST_CHUNK_BYTES = 1024 * 1024


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    return parser.parse_args(argv)


def _acceptance_provenance() -> tuple[str, list[dict[str, str]]]:
    """规范 §7.4 的 `acceptance` 工具行，复用 v2 的固定代码闭包。"""
    observed = toolchain.provenance(ROOT)
    files = [
        {"path": row["path"], "sha256": row["sha256"]}
        for row in observed["files"]
    ]
    return str(observed["version"]), files


def _input_digest(path: Path) -> InputResult:
    """安全打开一次输入并返回绑定到该 fd/inode 的摘要、大小与失败证据。

    有界流式读取,不做 `read_bytes()` 式的无界一次性读入(700 MiB 输入曾把峰值 RSS
    推到 724.7 MiB,且早于 load_contract()/run_r1 的 size_within_limit 之前跑完):
    - 只 open() 一次,带 O_NONBLOCK|O_NOFOLLOW——lstat() 确认是普通文件之后、open()
      之前存在一个 TOCTOU 窗口,路径可能被换成 FIFO;O_NOFOLLOW 挡符号链接换入,
      O_NONBLOCK 让换成 FIFO 也不会在 open()/read() 上无限阻塞(Task 8 堵过同一类
      挂起,这里堵的是同一个洞的另一条路径)。
    - fstat() 复核拿到的 fd 确实是 lstat() 看到的那个普通文件(设备号+inode 双 match),
      不是普通文件或身份对不上就当没读到。
    - 分块读取并增量喂给 SHA-256,任何时刻都只在内存里持有一个 chunk;一旦累计字节数
      越过硬上限立即停止并回哨兵值,不产出一个只覆盖前缀、可能被误认成真实摘要的哈希。
    """
    try:
        before = path.lstat()
    except OSError as exc:
        return InputResult(
            None, None,
            Finding("input_missing", "error", detail=f"cannot stat input: {exc}"),
        )
    if stat.S_ISLNK(before.st_mode):
        return InputResult(
            None, before.st_size,
            Finding("input_unreadable", "error", detail="input is a symlink"),
            Finding("input_is_symlink", "error", detail=str(path)),
        )
    if not stat.S_ISREG(before.st_mode):
        return InputResult(
            None, before.st_size,
            Finding("input_unreadable", "error", detail="input is not a regular file"),
            Finding("input_not_regular_file", "error", detail=str(path)),
        )
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        identity_finding = None
        try:
            current = path.lstat()
            if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
                identity_finding = Finding(
                    "input_identity_changed", "error", detail=str(path))
        except OSError:
            identity_finding = Finding("input_identity_changed", "error", detail=str(path))
        return InputResult(
            None, before.st_size,
            Finding("input_unreadable", "error", detail=f"cannot open input: {exc}"),
            identity_finding,
        )
    opened_size: int | None = None
    try:
        opened = os.fstat(descriptor)
        opened_size = opened.st_size
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            return InputResult(
                None, None,
                Finding("input_unreadable", "error", detail="input identity changed"),
                Finding("input_identity_changed", "error", detail=str(path)),
            )
        if opened.st_size > _MAX_INPUT_DIGEST_BYTES:
            return InputResult(
                None, opened.st_size,
                Finding(
                    "input_digest_too_large", "error",
                    detail=(f"{opened.st_size} bytes exceeds digest size limit "
                            f"{_MAX_INPUT_DIGEST_BYTES}"),
                ),
            )
        hasher = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, _INPUT_DIGEST_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_INPUT_DIGEST_BYTES:
                return InputResult(
                    None, total,
                    Finding(
                        "input_digest_too_large", "error",
                        detail=(f"input exceeded digest size limit "
                                f"{_MAX_INPUT_DIGEST_BYTES} while reading"),
                    ),
                )
            hasher.update(chunk)
        return InputResult(hasher.hexdigest(), total)
    except OSError as exc:
        return InputResult(
            None, opened_size,
            Finding("input_unreadable", "error", detail=f"cannot read input: {exc}"),
        )
    finally:
        os.close(descriptor)


def _present_tools(contract: Contract) -> set[str]:
    """按锁定表逐个探测:acceptance 自身恒在;其余看 path 是否为可执行文件。"""
    present = {"acceptance"}
    for tool in contract.raw["tools"]:
        path = Path(str(tool["path"]))
        if tool["id"] == "python" or (path.is_file() and os.access(path, os.X_OK)):
            present.add(str(tool["id"]))
    return present


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started_at = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        root = normalise_new_root(args.evidence_root, ROOT)
    except AcceptanceFailure as exc:
        print(f"ASSET_ACCEPT_FAIL {exc.code}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:          # noqa: BLE001 - root 尚未建立,写不出 summary
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1
    try:
        create_private_directory(root)
    except Exception as exc:                      # noqa: BLE001
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1

    contract = None
    verdict = None
    failure_code = None
    error = None
    provenance: dict[str, object] = {
        "acceptance_files": [],
        "tools": [{"id": "python", "version": platform.python_version()}],
        "input_digest": _UNREADABLE_DIGEST,
    }
    try:
        version, files = _acceptance_provenance()
        input_result = _input_digest(args.input)
        provenance = {
            "acceptance_files": files,
            "tools": [{"id": "acceptance", "version": version},
                      {"id": "python", "version": platform.python_version()}],
            "input_digest": input_result.digest or _UNREADABLE_DIGEST,
        }
        contract = load_contract(args.contract, candidate_root=args.input.parent)
        # Task 8:9 条 coordinator-owned check(R0/R1/R5,规范 §7.1 中不依赖外部进程的部分)
        # 真实接入;其余 stage(R2-R4 与外部工具)由后续计划接入,维持 NotTested。
        collected: dict[str, list[Finding]] = {}
        collected.update(run_r0(contract, tools_present=_present_tools(contract)))
        collected.update(run_r1(contract, input_result))
        # 规范 §2.5.1 与 §2.6 条款 1:R5 必须用同一算法对同一合同路径**重算** digest 再
        # 比对(TOCTOU 检查),不能拿 R0 时记下的 contract.digest 跟它自己比——那样构造
        # 上永远不可能失败。复算失败(例如合同在此期间被删除或改坏)按既有 fail-closed
        # 路径处理:load_contract 抛出的 AcceptanceFailure 会被下面统一的 except 捕获。
        recomputed_digest = load_contract(
            args.contract, candidate_root=args.input.parent).digest
        collected.update(run_r5(
            contract, evidence_manifest=[], recomputed_digest=recomputed_digest))
        wired = set(collected)

        # 终审第 2 条 / 规范 §7.2 表与 §7.4:锁定工具缺失是基础设施未能正常完成
        # (toolchain_mismatch,优先级 1),不是"资产被拒收"(check_failed)——验收机
        # 没装 Blender 不等于资产不合格。r0.contract.tools_locked 上的 error finding
        # 仍然保留作为证据,只是不让它的 Fail 落进 check_failed 的 failed_check_ids。
        infra_failures: list[str] = []
        if collected.get("r0.contract.tools_locked"):
            infra_failures.append("toolchain_mismatch")

        outcomes = []
        for spec in reg.CHECKS:
            if spec.id in contract.na_check_ids:
                terminal = None                  # aggregate 会先命中 N/A 分支
                tool_id = tool_version = None
            elif spec.id in wired:
                terminal = None
                tool_id, tool_version = "acceptance", version
            else:
                terminal = "NotTested"           # 未接入的 stage:规范 §2.4 的唯一产生点
                tool_id, tool_version = "acceptance", version
            outcomes.append(aggregate(
                spec.id, collected.get(spec.id, []),
                contract=contract, tool_id=tool_id, tool_version=tool_version,
                source_truncated=False, terminal=terminal))
        verdict = decide(contract=contract, outcomes=outcomes,
                         actual_files=set(), expected_files=set(),
                         achieved_grade="local-trusted", infra_failures=infra_failures)
    except AcceptanceFailure as exc:
        failure_code = exc.code
        error = str(exc)
    except Exception as exc:                      # noqa: BLE001 - fail-closed 兜底
        failure_code = "runner_internal_error"
        error = f"{type(exc).__name__}: {exc}"

    try:
        document = summary_document(
            contract=contract, verdict=verdict, achieved_grade="local-trusted",
            # P0 不渲染,故 platform_key 的后三段(engine/backend/vendor)填 none;
            # Plan B 接入 render_views 后由 gpu.init() 探测填真值(规范 §5.3)。
            platform_key=f"{platform.system().lower()}-{platform.machine().lower()}-none-none-none",
            started_at=started_at,
            completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
            evidence_manifest=[], runner_provenance=provenance,
            failure_code=failure_code, error=error)
        write_summary(root, document)
    except Exception as exc:                      # noqa: BLE001 - 连 summary 都造不出/写不出
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1
    status = "OK" if document["success"] else f"FAIL {document['failure_code']}"
    print(f"ASSET_ACCEPT_{status} {root / 'summary.json'}")
    return 0 if document["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
