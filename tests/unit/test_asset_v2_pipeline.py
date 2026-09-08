from collections import defaultdict
import datetime
import hashlib
import json
import sys
import pytest
from acceptance import check_registry as reg
from acceptance.controller import run_jobs
from acceptance.decide import Finding, Gate
from acceptance.evidence import finalize_run, finish_review, deliver
from acceptance.input_bundle import measure_file
from acceptance.plan import FileSpec, JobSpec, assemble_plan
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import REPO, file_lock, valid_document, write_contract


def mock_run(
    tmp_path,
    *,
    require_review=False,
    invalid_geometry=False,
    artifact=False,
    forge=None,
    executable=None,
):
    document = valid_document(tmp_path)
    if executable is not None:
        document["tools"][0]["path"] = str(executable)
    worker = tmp_path / "fixture_worker.py"
    worker.write_text(
        "import argparse,sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(REPO)!r})\n"
        "from acceptance.worker_protocol import read_request,write_result\n"
        "p=argparse.ArgumentParser();p.add_argument('--request');a=p.parse_args()\n"
        "r=read_request(Path(a.request))\nrows=[]\n"
        "for check_id in r['parameters']['checks']:\n"
        "    findings=[]\n"
        "    if r['parameters']['invalid_geometry'] and check_id=='r2.geometry.validate_clean':\n"
        "        findings=[dict(code='invalid_geometry',severity='error',pointer='/mesh/0',detail='fixture')]\n"
        "    rows.append(dict(id=check_id,findings=findings,metrics={}))\n"
        "for output in r['outputs']:\n"
        "    (Path(r['output_root'])/output['path']).write_bytes(b'real fixture artifact')\n"
        "write_result(r,rows,{'fixture':'not-a-real-Blender-worker'})\n"
        "if r['parameters']['forge'] and r['outputs']:\n"
        "    import json\n"
        "    p=Path(r['output_root'])/'result.json'; p.chmod(0o600)\n"
        "    result=json.loads(p.read_text())\n"
        "    key=r['parameters']['forge']\n"
        "    result['artifacts'][0][key]=0 if key=='bytes' else '0'*64\n"
        "    p.write_text(json.dumps(result))\n"
    )
    document["tools"][0]["files"].append(file_lock(worker))
    if require_review:
        document["review"] = {
            "required": True,
            "reviewer_ids": ["fixture-reviewer"],
            "required_image_ids": [],
            "reason": "test harness authorization only",
        }
    contract = write_contract(tmp_path, document)
    by_writer = defaultdict(list)
    for spec in reg.checks_for_kind("blend_native"):
        if spec.writer != "coordinator":
            by_writer[spec.writer].append(spec.id)
    jobs = []
    for index, (writer, checks) in enumerate(by_writer.items()):
        blocking = () if writer == "inspector" else ("r2.geometry.validate_clean",)
        jobs.append(
            JobSpec(
                f"job-{index}",
                writer,
                "python",
                tuple(checks),
                ("asset",),
                (FileSpec("preview", "preview.bin", writer, "application/octet-stream", 1024),)
                if artifact and index == 0
                else (),
                {"checks": checks, "invalid_geometry": invalid_geometry, "forge": forge},
                blocking,
            )
        )
    plan = assemble_plan(contract, tuple(jobs), gate_ids=("reference",))
    source = measure_file(tmp_path / "source/asset.blend", 1024, file_id="asset")
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    run = run_jobs(
        contract,
        plan,
        run_id="mock-run",
        input_files={"asset": source},
        scratch_root=tmp_path / "scratch",
        evidence_root=evidence,
        commands={writer: (str(executable or sys.executable), str(worker)) for writer in by_writer},
    )
    return contract, plan, source, evidence, run


def seal_fixture(tmp_path, setup, *, gates=None):
    contract, plan, source, evidence, run = setup
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=tmp_path / "contract.json",
        source_root=tmp_path / "source",
        evidence_root=evidence,
        delivery=source,
        coordinator_findings={"r4.visual.all_views_rendered": []},
        gates={"reference": Gate(True)} if gates is None else gates,
    )


def test_mock_full_chain_is_closed_and_delivery_is_exact(tmp_path):
    setup = mock_run(tmp_path)
    result = seal_fixture(tmp_path, setup)
    assert result["state"] == "SHIP"
    contract, plan, source, evidence, run = setup
    manifest = json.loads((evidence / "evidence-manifest.json").read_text())
    assert {row["id"] for row in manifest["files"]} == {f.id for f in plan.files}
    assert not {"summary.json", "evidence-manifest.json", "review.json", "completion.json"} & {
        r["path"] for r in manifest["files"]
    }
    assert all(
        record["pid"] and record["started_at"] and record["exit_code"] == 0 for record in run.jobs
    )
    receipt = deliver(evidence, delivery_path=source.path, destination=tmp_path / "delivered.blend")
    assert receipt["D"] == source.sha256
    assert (tmp_path / "delivered.blend").read_bytes() == source.path.read_bytes()


def test_missing_gate_cannot_make_technical_success(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup, gates={})["state"] == "UNVERIFIED"
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert summary["success"] is False


def test_review_does_not_rewrite_v_and_wrong_binding_cannot_seal(tmp_path):
    setup = mock_run(tmp_path, require_review=True)
    pending = seal_fixture(tmp_path, setup)
    assert pending["state"] == "NEEDS_REVIEW"
    evidence = setup[3]
    before = (evidence / "summary.json").read_bytes()
    assert not (evidence / "completion.json").exists()
    review = {
        "schema_version": 2,
        "bindings": pending["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_images": [],
                "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "note": "unit test only",
            }
        ],
    }
    bad = dict(review, bindings=review["bindings"] | {"V": "0" * 64})
    with pytest.raises(AcceptanceFailure):
        finish_review(evidence, delivery_path=setup[2].path, review=bad)
    complete = finish_review(evidence, delivery_path=setup[2].path, review=review)
    assert complete["state"] == "SHIP" and (evidence / "summary.json").read_bytes() == before


def test_finish_review_rejects_unknown_image_with_null_sha(tmp_path):
    setup = mock_run(tmp_path, require_review=True)
    pending = seal_fixture(tmp_path, setup)
    evidence = setup[3]
    before = (evidence / "summary.json").read_bytes()
    before_manifest = (evidence / "evidence-manifest.json").read_bytes()
    review = {
        "schema_version": 2,
        "bindings": pending["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_images": [{"id": "nonexistent-image", "sha256": None}],
                "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "note": "fixture malformed image",
            }
        ],
    }
    with pytest.raises(AcceptanceFailure) as caught:
        finish_review(evidence, delivery_path=setup[2].path, review=review)
    assert caught.value.code == "hash_mismatch"
    assert (evidence / "summary.json").read_bytes() == before
    assert (evidence / "evidence-manifest.json").read_bytes() == before_manifest
    assert (pending["bindings"]["E"], pending["bindings"]["V"]) == (
        hashlib.sha256(before_manifest).hexdigest(),
        hashlib.sha256(before).hexdigest(),
    )
    assert not (evidence / "review.json").exists()
    assert not (evidence / "completion.json").exists()


def test_safe_blocking_preserves_asset_failure_and_no_render_launch(tmp_path):
    setup = mock_run(tmp_path, invalid_geometry=True)
    result = seal_fixture(tmp_path, setup)
    assert result["state"] == "UNVERIFIED"
    assert setup[4].jobs[0]["started"] is True
    assert all(not record["started"] and record["blocked_by"] for record in setup[4].jobs[1:])
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert "r2.geometry.validate_clean" in summary["failed_check_ids"]
    assert summary["failure_code"] == "check_failed"
    closure = next(row for row in summary["checks"] if row["id"] == "r5.evidence.manifest_closed")
    assert closure["raw_status"] == "NotTested"


def test_received_payload_mutation_prevents_success(tmp_path):
    setup = mock_run(tmp_path)
    file = setup[3] / "payload/job-0/result.json"
    file.chmod(0o600)
    file.write_text("{}")
    result = seal_fixture(tmp_path, setup)
    assert result["state"] == "UNVERIFIED"


def test_no_delivery_cannot_ship_or_be_reviewed(tmp_path):
    contract, plan, source, evidence, run = mock_run(tmp_path)
    result = finalize_run(
        contract,
        plan,
        run,
        contract_path=tmp_path / "contract.json",
        source_root=tmp_path / "source",
        evidence_root=evidence,
        delivery=None,
        coordinator_findings={"r4.visual.all_views_rendered": []},
        gates={"reference": Gate(True)},
    )
    summary = json.loads((evidence / "summary.json").read_text())
    assert result["state"] == "UNVERIFIED" and result["bindings"]["D"] is None
    assert not summary["success"] and summary["D"] is None
    assert "evidence_missing" in summary["infra_failures"]
    with pytest.raises(AcceptanceFailure):
        deliver(evidence, delivery_path=source.path, destination=tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


def test_incomplete_gate_with_complete_asset_failure_is_unverified(tmp_path):
    setup = mock_run(tmp_path)
    setup[4].findings["r2.geometry.validate_clean"].append(Finding("bad_geometry", "error"))
    result = seal_fixture(tmp_path, setup, gates={"reference": Gate(False)})
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert result["state"] == "UNVERIFIED"
    assert summary["failure_code"] == "check_failed"
    assert "r2.geometry.validate_clean" in summary["failed_check_ids"]


def test_changed_payload_after_completion_blocks_delivery(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup)["state"] == "SHIP"
    source, evidence = setup[2:4]
    payload = evidence / "payload/job-0/result.json"
    payload.chmod(0o600)
    payload.write_text("{}")
    with pytest.raises(AcceptanceFailure):
        deliver(evidence, delivery_path=source.path, destination=tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


@pytest.mark.parametrize("when", ["before", "after"])
def test_result_findings_come_only_from_received_copy(tmp_path, monkeypatch, when):
    from acceptance import controller

    real_copy = controller._copy

    def mutate(source):
        result = json.loads(source.read_text())
        row = next(row for row in result["checks"] if row["id"] == "r2.geometry.validate_clean")
        row["findings"] = [
            dict(code="invalid_geometry", severity="error", pointer="/mesh/0", detail="mutated")
        ]
        source.chmod(0o600)
        source.write_text(json.dumps(result))

    def copy(source, target, **kwargs):
        relevant = kwargs["file_id"] == "job-0.result"
        if relevant and when == "before":
            mutate(source)
        received = real_copy(source, target, **kwargs)
        if relevant and when == "after":
            mutate(source)
        return received

    monkeypatch.setattr(controller, "_copy", copy)
    setup = mock_run(tmp_path, artifact=True)
    run, evidence = setup[4], setup[3]
    result = json.loads((evidence / "payload/job-0/result.json").read_text())
    findings = next(
        row["findings"] for row in result["checks"] if row["id"] == "r2.geometry.validate_clean"
    )
    assert [f.code for f in run.findings["r2.geometry.validate_clean"]] == [
        f["code"] for f in findings
    ]
    assert bool(findings) == (when == "before")
    assert run.results["job-0"] == result
    assert seal_fixture(tmp_path, setup)["state"] == ("UNVERIFIED" if when == "before" else "SHIP")


@pytest.mark.parametrize("forge", ["bytes", "sha256"])
def test_actual_forged_artifact_is_not_adopted(tmp_path, forge):
    setup = mock_run(tmp_path, artifact=True, forge=forge)
    run = setup[4]
    assert run.jobs[0]["failure_code"] == "hash_mismatch"
    assert "hash_mismatch" in run.infra_failures
    assert "preview" not in run.files and "job-0.result" not in run.files
    assert "job-0" not in run.results and "r2.geometry.validate_clean" not in run.findings
    assert (setup[3] / "payload/job-0/preview.bin").read_bytes() == b"real fixture artifact"
    assert seal_fixture(tmp_path, setup)["state"] == "UNVERIFIED"


def test_typed_runner_failure_survives_job_run_summary(tmp_path, monkeypatch):
    import subprocess
    from acceptance import controller

    real_command = controller.run_command
    real_subprocess_run = subprocess.run

    def broken_ps(args, **kwargs):
        if args[0] == "/bin/ps":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "fixture")
        return real_subprocess_run(args, **kwargs)

    def run_command(*args, **kwargs):
        with monkeypatch.context() as patch:
            patch.setattr(subprocess, "run", broken_ps)
            return real_command(*args, **kwargs)

    monkeypatch.setattr(controller, "run_command", run_command)
    setup = mock_run(tmp_path)
    run = setup[4]
    job = run.jobs[0]
    assert job["started"] and job["pid"] and job["started_at"]
    assert job["exit_code"] is not None and "memory_sampling" in job
    assert job["failure_code"] == "runner_internal_error"
    assert "runner_internal_error" in run.infra_failures
    assert json.loads((setup[3] / "payload/job-0/job.json").read_text()) == job
    assert json.loads((setup[3] / "payload/run.json").read_text())["jobs"][0] == job
    assert seal_fixture(tmp_path, setup)["state"] == "UNVERIFIED"
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert not summary["success"] and "runner_internal_error" in summary["infra_failures"]


def test_launch_must_match_previously_verified_executable(tmp_path, monkeypatch):
    from acceptance import controller

    alias = tmp_path / "python-alias"
    alias.symlink_to(sys.executable)
    real_verify = controller.verify_tools

    def verify(*args, **kwargs):
        measurements = real_verify(*args, **kwargs)
        alias.unlink()
        alias.symlink_to(tmp_path / "fixture-blender")
        return measurements

    monkeypatch.setattr(controller, "verify_tools", verify)
    setup = mock_run(tmp_path, executable=alias)
    assert not setup[4].jobs[0]["started"]
    assert setup[4].jobs[0]["failure_code"] == "toolchain_mismatch"


def test_changed_delivery_never_publishes_bad_target(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup)["state"] == "SHIP"
    source, evidence = setup[2:4]
    source.path.write_bytes(b"X" * source.bytes)
    destination = tmp_path / "delivered.blend"
    with pytest.raises(AcceptanceFailure) as caught:
        deliver(evidence, delivery_path=source.path, destination=destination)
    assert caught.value.code == "hash_mismatch"
    assert not destination.exists()
    assert not (evidence / "delivery-receipt.json").exists()
    assert not list(tmp_path.glob(".delivery-*"))


def test_existing_destination_is_preserved(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup)["state"] == "SHIP"
    destination = tmp_path / "delivered.blend"
    destination.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        deliver(setup[3], delivery_path=setup[2].path, destination=destination)
    assert destination.read_bytes() == b"existing"
    assert not (setup[3] / "delivery-receipt.json").exists()
    assert not list(tmp_path.glob(".delivery-*"))


def review_fixture():
    bindings = {key: key * 64 for key in ("C", "S", "D", "E", "V")}
    policy = {"reviewer_ids": ["reviewer"], "required_image_ids": ["view"]}
    manifest = {"files": [{"id": "view", "sha256": "a" * 64, "media_type": "image/png"}]}
    review = {
        "schema_version": 2,
        "bindings": bindings,
        "records": [
            {
                "reviewer_id": "reviewer",
                "outcome": "approved",
                "note": "fixture",
                "reviewed_at": "2026-09-08T00:00:00+00:00",
                "reviewed_images": [{"id": "view", "sha256": "a" * 64}],
            }
        ],
    }
    return review, bindings, policy, manifest


@pytest.mark.parametrize("outcome, approved", [("approved", True), ("rejected", False)])
def test_review_valid_controls(outcome, approved):
    from acceptance.evidence import _validate_review

    review, bindings, policy, manifest = review_fixture()
    review["records"][0]["outcome"] = outcome
    assert _validate_review(review, bindings, policy, manifest) is approved


@pytest.mark.parametrize(
    "field, value",
    [
        ("reviewer_id", []),
        ("reviewer_id", 1),
        ("reviewer_id", "unauthorized"),
        ("reviewed_at", []),
        ("reviewed_at", "not-a-time"),
        ("reviewed_at", "2026-09-08"),
    ],
)
def test_review_closed_types_and_timezone(field, value):
    from acceptance.evidence import _validate_review

    review, bindings, policy, manifest = review_fixture()
    review["records"][0][field] = value
    with pytest.raises(AcceptanceFailure) as caught:
        _validate_review(review, bindings, policy, manifest)
    assert caught.value.code == "tool_output_invalid"


@pytest.mark.parametrize(
    "images, code",
    [
        ([{"id": [], "sha256": "a" * 64}], "tool_output_invalid"),
        ([{"id": 1, "sha256": "a" * 64}], "tool_output_invalid"),
        ([{"id": "view", "sha256": "a" * 64}] * 2, "tool_output_invalid"),
        ([{"id": "view", "sha256": "b" * 64}], "hash_mismatch"),
        ([], "evidence_missing"),
    ],
)
def test_review_image_guards_preserve_failure_families(images, code):
    from acceptance.evidence import _validate_review

    review, bindings, policy, manifest = review_fixture()
    review["records"][0]["reviewed_images"] = images
    with pytest.raises(AcceptanceFailure) as caught:
        _validate_review(review, bindings, policy, manifest)
    assert caught.value.code == code


def test_non_dictionary_review_record_is_invalid():
    from acceptance.evidence import _validate_review

    review, bindings, policy, manifest = review_fixture()
    review["records"] = [None]
    with pytest.raises(AcceptanceFailure) as caught:
        _validate_review(review, bindings, policy, manifest)
    assert caught.value.code == "tool_output_invalid"


@pytest.mark.parametrize(
    "gates, state, failure_code, failed_ids",
    [
        (
            {"reference": Gate(True, (Finding("mismatch", "error"),))},
            "REJECTED",
            "check_failed",
            ["reference"],
        ),
        ({"reference": Gate(False)}, "UNVERIFIED", "runner_internal_error", []),
        ({"reference": Gate(True), "extra": Gate(True)}, "UNVERIFIED", "expected_set_mismatch", []),
    ],
)
def test_final_technical_verdict_drives_summary(tmp_path, gates, state, failure_code, failed_ids):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup, gates=gates)["state"] == state
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert not summary["success"]
    assert summary["expected_gate_ids"] == list(setup[1].gate_ids) == ["reference"]
    assert summary["failure_code"] == failure_code
    assert summary["failed_gate_ids"] == failed_ids


def test_review_rejection_preserves_technical_summary(tmp_path):
    setup = mock_run(tmp_path, require_review=True)
    pending = seal_fixture(tmp_path, setup)
    evidence = setup[3]
    before = (evidence / "summary.json").read_bytes()
    review = {
        "schema_version": 2,
        "bindings": pending["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "rejected",
                "reviewed_images": [],
                "reviewed_at": "2026-09-08T00:00:00+00:00",
                "note": "fixture rejection",
            }
        ],
    }
    assert (
        finish_review(evidence, delivery_path=setup[2].path, review=review)["state"] == "REJECTED"
    )
    assert (evidence / "summary.json").read_bytes() == before
    assert json.loads(before)["success"] is True
    with pytest.raises(AcceptanceFailure):
        deliver(evidence, delivery_path=setup[2].path, destination=tmp_path / "forbidden")
    assert not (tmp_path / "forbidden").exists()


def test_partial_delivery_copy_cleans_only_attempt_staging(tmp_path, monkeypatch):
    from acceptance import evidence, input_bundle

    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup)["state"] == "SHIP"
    unrelated = tmp_path / ".delivery-user-data"
    unrelated.mkdir()
    (unrelated / "keep").write_bytes(b"keep")
    real_measure = evidence.measure_file

    def fail_write(*args):
        raise OSError("fixture copy write failed")

    def measure(*args, **kwargs):
        if kwargs.get("copy_to") is not None:
            with monkeypatch.context() as patch:
                patch.setattr(input_bundle.os, "write", fail_write)
                return real_measure(*args, **kwargs)
        return real_measure(*args, **kwargs)

    monkeypatch.setattr(evidence, "measure_file", measure)
    destination = tmp_path / "delivered.blend"
    with pytest.raises(OSError, match="fixture copy write failed"):
        deliver(setup[3], delivery_path=setup[2].path, destination=destination)
    assert not destination.exists() and not (setup[3] / "delivery-receipt.json").exists()
    assert list(tmp_path.glob(".delivery-*")) == [unrelated]
    assert (unrelated / "keep").read_bytes() == b"keep"
