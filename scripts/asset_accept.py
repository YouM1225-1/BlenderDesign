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
    """输入不存在、不可读、不是普通文件、或超过硬上限时返回哨兵值,使 provenance 形状
    恒定,真正的放行判定交给 R1 的 check。

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
    except OSError:
        return _UNREADABLE_DIGEST
    if not stat.S_ISREG(before.st_mode):
        return _UNREADABLE_DIGEST
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return _UNREADABLE_DIGEST
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            return _UNREADABLE_DIGEST
        hasher = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, _INPUT_DIGEST_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_INPUT_DIGEST_BYTES:
                return _UNREADABLE_DIGEST
            hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return _UNREADABLE_DIGEST
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
        # 规范 §2.5.1 与 §2.6 条款 1:R5 必须用同一算法对同一合同路径**重算** digest 再
        # 比对(TOCTOU 检查),不能拿 R0 时记下的 contract.digest 跟它自己比——那样构造
        # 上永远不可能失败。复算失败(例如合同在此期间被删除或改坏)按既有 fail-closed
        # 路径处理:load_contract 抛出的 AcceptanceFailure 会被下面统一的 except 捕获。
        recomputed_digest = load_contract(
            args.contract, candidate_root=args.input.parent).digest
        collected.update(stages.run_r5(
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
                         achieved_grade="local-trusted", infra_failures=infra_failures)
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
