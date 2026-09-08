import json
from pathlib import Path

from acceptance import stages
from acceptance.contract import load_contract
from scripts import asset_accept
from tests.unit.asset_v2_support import valid_document


def _contract(tmp_path: Path, *, max_file_bytes: int | None = None):
    value = valid_document(tmp_path)
    if max_file_bytes is not None:
        value["budget"]["max_file_bytes"] = max_file_bytes
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "source")


def test_r0_all_pass_when_tools_present(tmp_path):
    findings = stages.run_r0(
        _contract(tmp_path), tools_present={"acceptance", "blender", "python"}
    )
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
    input_result = asset_accept._input_digest(asset)
    findings = stages.run_r1(_contract(tmp_path), input_result)
    assert all(v == [] for v in findings.values())
    assert input_result.digest is not None


def test_r1_rejects_a_symlink(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    real = candidate / "real.blend"
    real.write_bytes(b"x")
    link = candidate / "asset.blend"
    link.symlink_to(real)
    findings = stages.run_r1(_contract(tmp_path), asset_accept._input_digest(link))
    assert [f.code for f in findings["r1.input.no_link_or_device"]] == ["input_is_symlink"]
    assert findings["r1.input.digest_recorded"]


def test_r1_rejects_oversized_input(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    asset = candidate / "asset.blend"
    asset.write_bytes(b"x" * 128)
    contract = _contract(tmp_path, max_file_bytes=64)
    findings = stages.run_r1(contract, asset_accept._input_digest(asset))
    assert [f.code for f in findings["r1.input.size_within_limit"]] == ["input_too_large"]


def test_r5_all_pass_when_no_drift(tmp_path):
    contract = _contract(tmp_path)
    manifest = [{"id": "summary", "path": "summary.json", "bytes": 1,
                 "sha256": "a" * 64, "actual_sha256": "a" * 64}]
    findings = stages.run_r5(contract, evidence_manifest=manifest,
                             recomputed_digest=contract.digest)
    assert set(findings) == {"r5.evidence.manifest_closed", "r5.evidence.hashes_match",
                             "r5.contract.digest_stable"}
    assert all(v == [] for v in findings.values())


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
