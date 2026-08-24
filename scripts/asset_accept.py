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

import platform

from acceptance import check_registry as reg
from acceptance import evidence
from acceptance import stages
from acceptance.contract import Contract, load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import (
    AcceptanceFailure,
    create_private_directory,
    normalise_new_root,
)

ROOT = Path(__file__).resolve().parents[1]
_UNREADABLE_DIGEST = "0" * 64  # sha256 撞不出的哨兵值:标记"没能记录 digest"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    return parser.parse_args(argv)


def _acceptance_provenance() -> tuple[str, list[dict[str, str]]]:
    """规范 §7.4 的 `acceptance` 工具行:覆盖 acceptance/ 全部 .py/.json 加本 CLI。

    按名字匹配的 rglob 结果可能是目录(同名巧合)或悬空符号链接;用 is_file() 过滤掉,
    否则 read_bytes() 会因 IsADirectoryError/OSError 崩溃(调用方也兜底,但这里先避免)。
    """
    package = ROOT / "acceptance"
    entries = sorted(
        path for path in (
            list(package.rglob("*.py")) + list(package.rglob("*.json"))
            + [ROOT / "scripts" / "asset_accept.py"])
        if path.is_file())
    accumulator = hashlib.sha256()
    files: list[dict[str, str]] = []
    for path in entries:
        rel = path.relative_to(ROOT).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": rel, "sha256": file_hash})
        accumulator.update(f"{rel}\n{file_hash}\n".encode("utf-8"))
    return "acc-" + accumulator.hexdigest()[:12], files


def _input_digest(path: Path) -> str:
    """输入不存在、不可读或不是普通文件时返回哨兵值,使 provenance 形状恒定,判定交给
    R1 的 check。读取前先 lstat() 确认是普通文件——FIFO 等特殊文件必须在 read_bytes()
    之前拦下,否则在没有写入方时会无限阻塞在 I/O 等待里;一个 fail-closed 的验收工具
    永久挂起比崩溃更糟(它既不给结论也不释放)。
    """
    try:
        info = path.lstat()
    except OSError:
        return _UNREADABLE_DIGEST
    if not stat.S_ISREG(info.st_mode):
        return _UNREADABLE_DIGEST
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return _UNREADABLE_DIGEST


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
        input_digest = _input_digest(args.input)
        provenance = {
            "acceptance_files": files,
            "tools": [{"id": "acceptance", "version": version},
                      {"id": "python", "version": platform.python_version()}],
            "input_digest": input_digest,
        }
        contract = load_contract(args.contract, candidate_root=args.input.parent)
        # Task 8:9 条 coordinator-owned check(R0/R1/R5,规范 §7.1 中不依赖外部进程的部分)
        # 真实接入;其余 stage(R2-R4 与外部工具)由后续计划接入,维持 NotTested。
        collected: dict[str, list[Finding]] = {}
        collected.update(stages.run_r0(contract, tools_present=_present_tools(contract)))
        collected.update(stages.run_r1(contract, args.input))
        collected.update(stages.run_r5(
            contract, evidence_manifest=[], recomputed_digest=contract.digest))
        wired = set(collected)

        outcomes = []
        for spec in reg.CHECKS:
            if spec.id in contract.na_check_ids:
                terminal = None                  # aggregate 会先命中 N/A 分支
            elif spec.id in wired:
                terminal = None
            else:
                terminal = "NotTested"           # 未接入的 stage:规范 §2.4 的唯一产生点
            outcomes.append(aggregate(
                spec.id, collected.get(spec.id, []),
                contract=contract, tool_id="acceptance", tool_version=version,
                source_truncated=False, terminal=terminal))
        verdict = decide(contract=contract, outcomes=outcomes,
                         actual_files=set(), expected_files=set(),
                         achieved_grade="local-trusted", infra_failures=[])
    except AcceptanceFailure as exc:
        failure_code = exc.code
        error = str(exc)
    except Exception as exc:                      # noqa: BLE001 - fail-closed 兜底
        failure_code = "runner_internal_error"
        error = f"{type(exc).__name__}: {exc}"

    try:
        document = evidence.summary_document(
            contract=contract, verdict=verdict, achieved_grade="local-trusted",
            # P0 不渲染,故 platform_key 的后三段(engine/backend/vendor)填 none;
            # Plan B 接入 render_views 后由 gpu.init() 探测填真值(规范 §5.3)。
            platform_key=f"{platform.system().lower()}-{platform.machine().lower()}-none-none-none",
            started_at=started_at,
            completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
            evidence_manifest=[], runner_provenance=provenance,
            failure_code=failure_code, error=error)
        evidence.write_summary(root, document)
    except Exception as exc:                      # noqa: BLE001 - 连 summary 都造不出/写不出
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1
    status = "OK" if document["success"] else f"FAIL {document['failure_code']}"
    print(f"ASSET_ACCEPT_{status} {root / 'summary.json'}")
    return 0 if document["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
