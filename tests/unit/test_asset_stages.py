import json
from pathlib import Path

from acceptance import stages
from acceptance.contract import load_contract
from tests.unit.test_asset_contract import _valid


def _contract(tmp_path: Path):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(_valid()), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "candidate")


def test_r0_all_pass_when_tools_present(tmp_path):
    findings = stages.run_r0(_contract(tmp_path), tools_present={"blender"})
    assert set(findings) == {"r0.contract.schema_closed", "r0.contract.tools_locked",
                             "r0.contract.na_set_declared"}
    assert all(v == [] for v in findings.values())


def test_r0_reports_missing_tool(tmp_path):
    findings = stages.run_r0(_contract(tmp_path), tools_present=set())
    assert [f.code for f in findings["r0.contract.tools_locked"]] == ["tool_not_installed"]
    assert findings["r0.contract.tools_locked"][0].severity == "error"


def test_r1_passes_for_a_real_regular_file(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    asset = candidate / "asset.blend"
    asset.write_bytes(b"x" * 16)
    findings = stages.run_r1(_contract(tmp_path), asset)
    assert all(v == [] for v in findings.values())


def test_r1_rejects_a_symlink(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    real = candidate / "real.blend"
    real.write_bytes(b"x")
    link = candidate / "asset.blend"
    link.symlink_to(real)
    findings = stages.run_r1(_contract(tmp_path), link)
    assert [f.code for f in findings["r1.input.no_link_or_device"]] == ["input_is_symlink"]


def test_r1_rejects_oversized_input(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    asset = candidate / "asset.blend"
    asset.write_bytes(b"x" * 32)
    contract = _contract(tmp_path)
    contract.raw["budget"]["max_file_bytes"] = 16
    findings = stages.run_r1(contract, asset)
    assert [f.code for f in findings["r1.input.size_within_limit"]] == ["input_too_large"]


def test_r5_detects_digest_drift(tmp_path):
    contract = _contract(tmp_path)
    findings = stages.run_r5(contract, evidence_manifest=[], recomputed_digest="deadbeef")
    assert [f.code for f in findings["r5.contract.digest_stable"]] == ["contract_digest_drift"]


def test_r5_detects_hash_mismatch(tmp_path):
    contract = _contract(tmp_path)
    manifest = [{"id": "summary", "path": "summary.json", "bytes": 1,
                 "sha256": "a" * 64, "actual_sha256": "b" * 64}]
    findings = stages.run_r5(contract, evidence_manifest=manifest,
                             recomputed_digest=contract.digest)
    assert [f.code for f in findings["r5.evidence.hashes_match"]] == ["evidence_hash_drift"]
