import json
import os
from pathlib import Path

import pytest

from scripts import asset_accept
from tests.unit.test_asset_contract import _valid


@pytest.fixture(autouse=True)
def _tools_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认让 `_valid()` 锁定的工具"已装",测试不再依赖这台机器 `/Applications` 下的
    真实内容(全局约束:默认 pytest 不得依赖 Blender)。审查发现:未打这个补丁之前,
    R0 的工具锁定 check 只在开发机恰好装了 Blender 时才 Pass——`ALL CHECKS PASSED`
    曾经是这台机器的属性,不是代码的属性。关心"工具缺失"路径本身的测试
    (见 `test_missing_tool_fails_r0_contract_tools_locked`)在测试体内再次
    monkeypatch 覆盖这个默认值。
    """
    monkeypatch.setattr(asset_accept, "_present_tools", lambda contract: {"acceptance", "blender"})


def _contract_file(tmp_path: Path) -> Path:
    # 合同必须位于候选输入目录**之外**(规范 §1 的合同权属条款,由 load_contract 强制)。
    # 因此输入放在 tmp_path/candidate/,合同留在 tmp_path/。
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(_valid()), encoding="utf-8")
    return path


def _input_path(tmp_path: Path) -> Path:
    candidate = tmp_path / "candidate"
    candidate.mkdir(exist_ok=True)
    return candidate / "asset.blend"


def _run(tmp_path: Path, *extra: str) -> tuple[int, dict[str, object]]:
    root = tmp_path / "evidence"
    code = asset_accept.main([
        "--contract", str(_contract_file(tmp_path)),
        "--input", str(_input_path(tmp_path)),
        "--evidence-root", str(root),
        *extra,
    ])
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    return code, summary


def test_missing_input_is_reported_not_crashed(tmp_path):
    code, summary = _run(tmp_path)
    assert code == 1
    assert summary["success"] is False
    # 输入不存在 → r1.input.digest_recorded 得一条 error finding → check_failed;
    # 其余未接入的 stage 是 NotTested,按 decide() 的定义**不进** failed_check_ids。
    # r0/r5 现已接入(Task 8),在此场景下恒为 Pass,故只断言成员而非整个列表。
    assert summary["failure_code"] == "check_failed"
    assert "r1.input.digest_recorded" in summary["failed_check_ids"]
    # 回归守卫:R2-R4 尚未接入,必须仍是 NotTested——防止将来某个任务过早把它们标成已测。
    assert all(c["raw_status"] == "NotTested"
               for c in summary["checks"]
               if c["id"].startswith(("r2.", "r3.", "r4."))
               and c["raw_status"] != "NotApplicableByContract")


def test_summary_matches_the_frozen_schema_shape(tmp_path):
    _, summary = _run(tmp_path)
    assert set(summary) == {
        "schema_version", "kind", "success", "contract_id", "contract_digest",
        "artifact_kind", "required_isolation_grade", "achieved_isolation_grade",
        "platform_key", "started_at", "completed_at", "stages", "checks",
        "evidence_manifest", "advisories", "failure_code", "failed_check_ids",
        "error", "runner_provenance",
    }
    assert set(summary["runner_provenance"]) == {
        "acceptance_files", "tools", "input_digest"}
    for check in summary["checks"]:
        assert set(check) == {
            "id", "stage", "raw_status", "effective_status", "accepted",
            "tool_id", "tool_version", "findings", "source_truncated",
            "detail", "metrics"}
    assert summary["schema_version"] == 1
    assert summary["kind"] == "asset_acceptance"


def test_reused_evidence_root_is_rejected_before_any_work(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    marker = root / "old.txt"
    marker.write_text("stale", encoding="utf-8")
    code = asset_accept.main([
        "--contract", str(_contract_file(tmp_path)),
        "--input", str(_input_path(tmp_path)),
        "--evidence-root", str(root),
    ])
    assert code == 1
    assert marker.read_text(encoding="utf-8") == "stale"
    assert not (root / "summary.json").exists()


def test_summary_is_private_regular_file(tmp_path):
    _, _ = _run(tmp_path)
    summary = tmp_path / "evidence" / "summary.json"
    assert summary.is_file()
    assert summary.stat().st_mode & 0o777 == 0o600


def test_evidence_root_parent_missing_is_reported_not_crashed(tmp_path):
    # 父目录不存在 → normalise_new_root 里 resolve(strict=True) 抛裸 FileNotFoundError;
    # 此时 root 从未建立,写不出 summary,正确行为是打印到 stderr 并返回 1(不是裸 traceback)。
    root = tmp_path / "no_such_parent" / "evidence"
    code = asset_accept.main([
        "--contract", str(_contract_file(tmp_path)),
        "--input", str(_input_path(tmp_path)),
        "--evidence-root", str(root),
    ])
    assert code == 1
    assert not root.parent.exists()


def test_provenance_crash_still_writes_fail_closed_summary(tmp_path, monkeypatch):
    # _acceptance_provenance() 崩溃时 create_private_directory 已成功;必须落一份
    # runner_internal_error 的 summary,而不是留下没有 summary 的孤儿 evidence 目录。
    def _boom() -> tuple[str, list[dict[str, str]]]:
        raise OSError("boom: acceptance/ unreadable")

    monkeypatch.setattr(asset_accept, "_acceptance_provenance", _boom)
    code, summary = _run(tmp_path)
    assert code == 1
    assert summary["success"] is False
    assert summary["failure_code"] == "runner_internal_error"
    assert "boom" in (summary["error"] or "")


def test_unreadable_input_is_reported_not_silently_passed(tmp_path):
    # chmod 000:is_file() 仍是 True,但内容读不出来;r1 必须报 error,不能悄悄 Pass
    # 掉一个实际没能记录 digest 的输入(旧 bug:raw_status Pass + digest 全 0)。
    input_path = _input_path(tmp_path)
    input_path.write_bytes(b"not actually a blend file")
    input_path.chmod(0o000)
    try:
        code, summary = _run(tmp_path)
    finally:
        input_path.chmod(0o600)
    assert code == 1
    assert summary["success"] is False
    assert summary["failure_code"] == "check_failed"
    assert summary["failed_check_ids"] == ["r1.input.digest_recorded"]
    assert summary["runner_provenance"]["input_digest"] == "0" * 64
    r1 = next(c for c in summary["checks"] if c["id"] == "r1.input.digest_recorded")
    assert r1["raw_status"] == "Fail"
    assert any(f["severity"] == "error" for f in r1["findings"])


def test_real_input_reaches_r2_not_tested_boundary(tmp_path):
    asset = _input_path(tmp_path)
    asset.write_bytes(b"BLENDER-fake")
    _, summary = _run(tmp_path)
    # 正向路径的全部价值都在这条断言里:9 条已接线的 coordinator-owned check
    # (R0×3 + R1×3 + R5×3)必须真的全绿,而不是只看 r1 就放过 r0/r5 可能的悄悄失败。
    wired = [c for c in summary["checks"] if c["id"].startswith(("r0.", "r1.", "r5."))]
    assert len(wired) == 9
    assert all(c["effective_status"] == "Pass" for c in wired)
    # R2 起尚未接入 → NotTested → 整体仍 fail-closed
    assert summary["failure_code"] in {"check_failed", "runner_internal_error"}


def test_missing_tool_fails_r0_contract_tools_locked(tmp_path, monkeypatch):
    # 与上面 autouse 的 `_tools_present` 相反:显式模拟"一个锁定工具都没装",证明
    # r0.contract.tools_locked 真的接到了 `_present_tools()` 的返回值上,而不是长期
    # 靠这台机器装了 Blender 侥幸 Pass——可移植性回归的判别力证明,构造过程不碰真实
    # /Applications。
    monkeypatch.setattr(asset_accept, "_present_tools", lambda contract: set())
    code, summary = _run(tmp_path)
    assert code == 1
    assert "r0.contract.tools_locked" in summary["failed_check_ids"]
    r0 = next(c for c in summary["checks"] if c["id"] == "r0.contract.tools_locked")
    assert r0["raw_status"] == "Fail"
    assert any(f["code"] == "tool_not_installed" for f in r0["findings"])


def test_input_fifo_is_reported_not_hung(tmp_path):
    # 回归测试(修复前会挂起):`_input_digest()` 曾经对 `--input` 做无条件
    # `read_bytes()`,发生在 run_r1 之前;指向一个没有写入方的 FIFO 会让 main()
    # 永久阻塞在不可中断的 I/O 等待里(实测 >30s,只能 kill -9)。修好之后
    # `_input_digest()` 先用 lstat() 确认是普通文件、非普通文件直接给哨兵值,
    # 判定交给对同一路径立即返回的 run_r1——这条测试能秒回就是修复本身的判别力
    # 证明(仓库已在 pyproject.toml 配置 pytest-timeout 全局 30s 兜底)。
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    fifo_path = candidate / "asset.blend"
    os.mkfifo(fifo_path)
    root = tmp_path / "evidence"
    code = asset_accept.main([
        "--contract", str(_contract_file(tmp_path)),
        "--input", str(fifo_path),
        "--evidence-root", str(root),
    ])
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert code == 1
    assert summary["success"] is False
    assert summary["runner_provenance"]["input_digest"] == "0" * 64
    assert summary["failure_code"] == "check_failed"
    assert "r1.input.no_link_or_device" in summary["failed_check_ids"]
    r1_link = next(c for c in summary["checks"] if c["id"] == "r1.input.no_link_or_device")
    assert r1_link["raw_status"] == "Fail"
    assert any(f["code"] == "input_not_regular_file" for f in r1_link["findings"])
