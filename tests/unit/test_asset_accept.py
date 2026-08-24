import json
from pathlib import Path

from scripts import asset_accept
from tests.unit.test_asset_contract import _valid


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
    r1 = [c for c in summary["checks"] if c["id"].startswith("r1.")]
    assert all(c["effective_status"] == "Pass" for c in r1)
    # R2 起尚未接入 → NotTested → 整体仍 fail-closed
    assert summary["failure_code"] in {"check_failed", "runner_internal_error"}
