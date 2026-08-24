#!/usr/bin/env python3
"""资产验收 coordinator(规范 §7)。P0 只支持 blend_native 与 interchange/glb。"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import sys
from pathlib import Path

import platform

from acceptance import check_registry as reg
from acceptance import evidence
from acceptance.contract import load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import (
    AcceptanceFailure,
    create_private_directory,
    normalise_new_root,
)

ROOT = Path(__file__).resolve().parents[1]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    return parser.parse_args(argv)


def _acceptance_provenance() -> tuple[str, list[dict[str, str]]]:
    """规范 §7.4 的 `acceptance` 工具行:覆盖 acceptance/ 全部 .py/.json 加本 CLI。"""
    package = ROOT / "acceptance"
    entries = sorted(
        list(package.rglob("*.py")) + list(package.rglob("*.json"))
        + [ROOT / "scripts" / "asset_accept.py"])
    accumulator = hashlib.sha256()
    files: list[dict[str, str]] = []
    for path in entries:
        rel = path.relative_to(ROOT).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": rel, "sha256": file_hash})
        accumulator.update(f"{rel}\n{file_hash}\n".encode("utf-8"))
    return "acc-" + accumulator.hexdigest()[:12], files


def _input_digest(path: Path) -> str:
    """输入不存在时返回 64 个 0,使 provenance 形状恒定,判定交给 R1 的 check。"""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started_at = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        root = normalise_new_root(args.evidence_root, ROOT)
    except AcceptanceFailure as exc:
        print(f"ASSET_ACCEPT_FAIL {exc.code}: {exc}", file=sys.stderr)
        return 1
    try:
        create_private_directory(root)
    except Exception as exc:                      # noqa: BLE001
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1

    version, files = _acceptance_provenance()
    provenance = {
        "acceptance_files": files,
        "tools": [{"id": "acceptance", "version": version},
                  {"id": "python", "version": platform.python_version()}],
        "input_digest": _input_digest(args.input),
    }
    contract = None
    verdict = None
    failure_code = None
    error = None
    try:
        contract = load_contract(args.contract, candidate_root=args.input.parent)
        # P0 骨架:R1 的输入存在性是第一条真实判定,其余 stage 由后续计划接入。
        findings: list[Finding] = []
        if not args.input.is_file():
            findings.append(Finding(code="input_missing", severity="error",
                                    detail=f"input is not a regular file: {args.input}"))
        outcomes = []
        wired = {"r1.input.digest_recorded"}     # 本计划接入的唯一真实判定
        for spec in reg.CHECKS:
            if spec.id in contract.na_check_ids:
                terminal = None                  # aggregate 会先命中 N/A 分支
            elif spec.id in wired:
                terminal = None
            else:
                terminal = "NotTested"           # 未接入的 stage:规范 §2.4 的唯一产生点
            outcomes.append(aggregate(
                spec.id,
                findings if spec.id in wired else [],
                contract=contract, tool_id="acceptance",
                tool_version=version,
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

    document = evidence.summary_document(
        contract=contract, verdict=verdict, achieved_grade="local-trusted",
        # P0 不渲染,故 platform_key 的后三段(engine/backend/vendor)填 none;
        # Plan B 接入 render_views 后由 gpu.init() 探测填真值(规范 §5.3)。
        platform_key=f"{platform.system().lower()}-{platform.machine().lower()}-none-none-none",
        started_at=started_at,
        completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
        evidence_manifest=[], runner_provenance=provenance,
        failure_code=failure_code, error=error)
    try:
        evidence.write_summary(root, document)
    except Exception as exc:                      # noqa: BLE001 - 连 summary 都写不出
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1
    status = "OK" if document["success"] else f"FAIL {document['failure_code']}"
    print(f"ASSET_ACCEPT_{status} {root / 'summary.json'}")
    return 0 if document["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
