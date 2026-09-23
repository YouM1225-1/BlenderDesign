import datetime
import json
import resource
import signal
import stat
import subprocess
import sys

import pytest

from tests.unit.asset_v2_support import REPO, valid_document
from tests.unit.test_asset_v2_pipeline import mock_run, seal_fixture


def command(*args, preexec_fn=None):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts/asset_accept.py"), *map(str, args)],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=REPO.parent,
        preexec_fn=preexec_fn,
    )


def result(completed):
    assert len(completed.stdout.splitlines()) == 1
    return json.loads(completed.stdout)


def execute(tmp_path, value, *, evidence="evidence", input_root=None):
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps(value))
    return command(
        "run",
        "--contract",
        contract,
        "--input-root",
        input_root or tmp_path / "source",
        "--evidence-root",
        tmp_path / evidence,
        "--scratch-root",
        tmp_path / (evidence + "-scratch"),
    )


@pytest.mark.parametrize(("kind", "not_tested"), [("blend_native", 15), ("interchange", 31)])
def test_production_m1_cli_does_not_publish_mock_success(tmp_path, kind, not_tested):
    completed = execute(tmp_path, valid_document(tmp_path, kind))
    assert completed.returncode == 1
    assert result(completed)["state"] == "UNVERIFIED"
    path = tmp_path / "evidence/summary.json"
    summary = json.loads(path.read_text())
    assert summary["schema_version"] == 2 and summary["success"] is False
    assert sum(c["raw_status"] == "NotTested" for c in summary["checks"]) == not_tested
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_v1_rejected_and_failed_summary_survives(tmp_path):
    value = valid_document(tmp_path)
    value["schema_version"] = 1
    completed = execute(tmp_path, value)
    assert completed.returncode == 1
    assert result(completed)["failure_code"] == "contract_invalid"
    summary = json.loads((tmp_path / "evidence/summary.json").read_text())
    assert summary["failure_code"] == "contract_invalid" and summary["success"] is False


def test_summary_write_failure_keeps_machine_readable_primary_error(tmp_path):
    contract = tmp_path / "contract.json"
    contract.write_text("{}")

    def limit_child_file_size():
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))

    evidence = tmp_path / "evidence"
    completed = command(
        "run",
        "--contract",
        contract,
        "--input-root",
        tmp_path / "source",
        "--evidence-root",
        evidence,
        "--scratch-root",
        tmp_path / "scratch",
        preexec_fn=limit_child_file_size,
    )
    output = result(completed)
    assert completed.returncode == 1
    assert output["state"] == "UNVERIFIED"
    assert output["failure_code"] == "contract_invalid"
    assert "closed fields required" in output["error"]
    assert "File too large" in output["error"]
    assert "Traceback" not in completed.stderr
    assert evidence.is_dir()
    assert not (evidence / "summary.json").exists()


def test_reused_root_preserves_existing_files(tmp_path):
    value = valid_document(tmp_path)
    root = tmp_path / "evidence"
    root.mkdir()
    marker = root / "original"
    marker.write_text("preserve")
    completed = execute(tmp_path, value)
    assert completed.returncode == 1 and marker.read_text() == "preserve"
    assert result(completed)["failure_code"] == "reused_evidence_root"
    assert not (root / "summary.json").exists()


def test_missing_input_and_overlapping_roots_do_not_hang(tmp_path):
    value = valid_document(tmp_path)
    (tmp_path / "source/asset.blend").unlink()
    completed = execute(tmp_path, value)
    assert completed.returncode == 1
    assert result(completed)["state"] == "UNVERIFIED"
    assert json.loads((tmp_path / "evidence/summary.json").read_text())["success"] is False
    completed = execute(tmp_path, value, evidence="source/evidence")
    assert completed.returncode == 1
    assert result(completed)["failure_code"] == "contract_invalid"


def freeze(tmp_path, bundle, manifest):
    source = tmp_path / "asset.blend"
    source.write_bytes(b"frozen asset")
    sources = tmp_path / "sources.json"
    sources.write_text(
        json.dumps([{"id": "asset", "path": "asset.blend", "source": str(source)}])
    )
    return command(
        "freeze",
        "--sources",
        sources,
        "--bundle-root",
        bundle,
        "--manifest",
        manifest,
    )


def test_freeze_writes_an_outside_manifest_and_private_bundle(tmp_path):
    bundle, manifest = tmp_path / "bundle", tmp_path / "manifest.json"
    completed = freeze(tmp_path, bundle, manifest)
    assert completed.returncode == 0
    output = result(completed)
    assert json.loads(manifest.read_text()) == output
    assert output["schema_version"] == 2 and len(output["files"]) == 1
    assert (bundle / "asset.blend").read_bytes() == b"frozen asset"
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o600


def test_freeze_rejects_a_directly_embedded_manifest_before_bundle_creation(tmp_path):
    bundle = tmp_path / "bundle"
    completed = freeze(tmp_path, bundle, bundle / "manifest.json")
    assert completed.returncode == 1
    assert result(completed)["failure_code"] == "contract_invalid"
    assert not bundle.exists()


@pytest.mark.parametrize(("name", "alias"), [("Bundle", "bundle"), ("é", "e\u0301")])
def test_freeze_rejects_a_manifest_in_a_prospective_physical_alias(tmp_path, name, alias):
    probe = tmp_path / name
    probe.mkdir()
    other = tmp_path / alias
    if not other.exists() or not probe.samefile(other):
        pytest.skip("test filesystem does not support this directory alias")
    probe.rmdir()

    bundle, manifest = tmp_path / name, other / "manifest.json"
    completed = freeze(tmp_path, bundle, manifest)
    assert completed.returncode == 1
    assert result(completed)["failure_code"] == "contract_invalid"
    assert bundle.is_dir()
    assert not manifest.exists()


@pytest.mark.parametrize(("outcome", "returncode", "state"), [("approved", 0, "SHIP"), ("rejected", 1, "REJECTED")])
def test_review_exit_code_follows_the_sealed_state(tmp_path, outcome, returncode, state):
    setup = mock_run(tmp_path, require_review=True)
    pending = seal_fixture(tmp_path, setup)
    review = tmp_path / "review-input.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bindings": pending["bindings"],
                "records": [
                    {
                        "reviewer_id": "fixture-reviewer",
                        "outcome": outcome,
                        "reviewed_images": [],
                        "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                        "note": "CLI fixture only",
                    }
                ],
            }
        )
    )
    completed = command(
        "review",
        "--evidence-root",
        setup[3],
        "--delivery",
        setup[2].path,
        "--review",
        review,
    )
    assert completed.returncode == returncode
    assert result(completed)["state"] == state


def test_deliver_success_returns_json_and_exact_bytes(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup)["state"] == "SHIP"
    destination = tmp_path / "delivered.blend"
    completed = command(
        "deliver",
        "--evidence-root",
        setup[3],
        "--delivery",
        setup[2].path,
        "--destination",
        destination,
    )
    assert completed.returncode == 0
    assert result(completed)["D"] == setup[2].sha256
    assert destination.read_bytes() == setup[2].path.read_bytes()
