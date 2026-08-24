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
    assert summary["failure_code"] == "check_failed"
    assert summary["failed_check_ids"] == ["r1.input.digest_recorded"]
    assert all(c["raw_status"] == "NotTested"
               for c in summary["checks"]
               if c["id"].startswith(("r2.", "r3.", "r4.", "r5."))
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
