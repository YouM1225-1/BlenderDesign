import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from acceptance import failure_codes as fc
from acceptance.contract import load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import AcceptanceFailure, clean_environment, run_command
from tests.unit.asset_v2_support import REPO, valid_document, write_contract
from tests.unit.test_asset_v2_decide import complete_outcomes


def test_fifo_contract_remains_bounded(tmp_path):
    fifo = tmp_path / "contract.json"
    os.mkfifo(fifo)
    code = (
        "from pathlib import Path\nfrom acceptance.contract import load_contract\n"
        "from acceptance.primitives import AcceptanceFailure\nimport sys\n"
        "try: load_contract(Path(sys.argv[1]),candidate_root=Path(sys.argv[2]))\n"
        "except AcceptanceFailure: raise SystemExit(0)\nraise SystemExit(2)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, str(fifo), str(tmp_path / "source")],
        cwd=REPO,
        capture_output=True,
        timeout=2,
    )
    assert completed.returncode == 0


def test_contract_cap_and_parent_symlink_rejected(tmp_path, monkeypatch):
    import acceptance.contract as module

    value = valid_document(tmp_path)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(module, "_MAX_CONTRACT_BYTES", path.stat().st_size - 1)
    with pytest.raises(AcceptanceFailure):
        load_contract(path, candidate_root=tmp_path / "source")
    monkeypatch.setattr(module, "_MAX_CONTRACT_BYTES", 1048576)
    folder = tmp_path / "alias"
    folder.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AcceptanceFailure):
        load_contract(folder / "contract.json", candidate_root=tmp_path / "source")


@pytest.mark.parametrize("family", fc.INFRA_FAMILIES)
def test_every_infra_family_still_blocks_and_preserves_real_failures(tmp_path, family):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    original = outcomes[0]
    outcomes[0] = aggregate(
        original.id,
        [Finding("actual_failure", "error")],
        contract=contract,
        tool_id=original.tool_id,
        tool_version=original.tool_version,
        source_truncated=False,
        terminal=None,
    )
    result = decide(
        contract=contract,
        outcomes=outcomes,
        actual_files={"a"},
        expected_files={"a"},
        achieved_grade="local-trusted",
        infra_failures=[family],
    )
    assert result.failure_code == family and not result.success
    assert original.id in result.failed_check_ids


def test_allowed_warning_does_not_compensate_error(tmp_path):
    value = valid_document(tmp_path)
    check_id = "r2.material.slots_resolved"
    version = value["tools"][0]["version"]
    value["warning_allowlist"] = [
        {
            "check_id": check_id,
            "warning_code": "empty_material_slot",
            "tool_id": "python",
            "tool_version": version,
        }
    ]
    contract = write_contract(tmp_path, value)
    warning = Finding("empty_material_slot", "warning")
    passed = aggregate(
        check_id,
        [warning],
        contract=contract,
        tool_id="python",
        tool_version=version,
        source_truncated=False,
        terminal=None,
    )
    failed = aggregate(
        check_id,
        [warning, Finding("lost_used_material", "error")],
        contract=contract,
        tool_id="python",
        tool_version=version,
        source_truncated=False,
        terminal=None,
    )
    assert passed.raw_status == "Pass" and passed.accepted
    assert failed.raw_status == "Fail" and not failed.accepted


def test_sampled_rss_budget_is_observed_not_fake_address_space_limit(tmp_path):
    observed = {}
    limits = {"cpu_seconds": 10, "rss_bytes": 1, "open_files": 128, "file_size_bytes": 1048576}
    with pytest.raises(AcceptanceFailure) as caught:
        run_command(
            "rss-probe",
            [sys.executable, "-c", "import time; x=bytearray(10000000); time.sleep(2)"],
            cwd=tmp_path,
            env=clean_environment(Path(sys.executable)),
            log_path=tmp_path / "log",
            timeout=3,
            max_log_bytes=4096,
            limits=limits,
            observation=observed,
        )
    assert caught.value.code == "resource_limit_exceeded"
    assert observed["memory_sampling"]["samples"] >= 1
    assert observed["memory_sampling"]["peak_observed_rss_bytes"] > 1
