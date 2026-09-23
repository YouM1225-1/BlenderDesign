from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from acceptance.contract import load_contract
from acceptance.decide import Finding
from acceptance.input_bundle import BoundFile, measure_file
from acceptance.native_results import native_results
from acceptance.primitives import AcceptanceFailure
from tests.integration.asset_runtime_support import (
    REPO,
    AssetCase,
    prepare_calibration,
    prepare_native_case,
    run_case,
    write_case,
)

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_ASSET_NATIVE") != "1",
        reason="Explicit native integration gate; unit tests never launch Blender",
    ),
    pytest.mark.timeout(900),
]
BLENDER = Path(os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender"))
NATIVE_CHECK_IDS = {
    "r0.contract.schema_closed",
    "r0.contract.tools_locked",
    "r0.contract.na_set_declared",
    "r1.input.digest_recorded",
    "r1.input.no_link_or_device",
    "r1.input.size_within_limit",
    "r2.inventory.coverage_complete",
    "r2.inventory.no_nan_inf",
    "r2.inventory.no_reserved_props",
    "r2.geometry.validate_clean",
    "r2.geometry.manifest_written",
    "r2.material.slots_resolved",
    "r2.dependency.all_present",
    "r2.source.digest_stable",
    "r4.reopen.offline_ok",
    "r4.reopen.dependencies_resolved",
    "r4.reopen.manifest_matches_source",
    "r4.visual.scene_not_empty",
    "r4.visual.all_views_rendered",
    "r4.visual.self_determinism",
    "r4.visual.platform_key_known",
    "r5.evidence.manifest_closed",
    "r5.evidence.hashes_match",
    "r5.contract.digest_stable",
}
NATIVE_GATE_IDS = {"native.scope_supported", "native.cross_process", "native.reference"}


@pytest.fixture(scope="module")
def calibration(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return prepare_calibration(BLENDER, tmp_path_factory.mktemp("native-calibration") / "run")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def finding_codes(container: dict[str, Any]) -> set[str]:
    return {row["code"] for row in container["findings"]}


def check(summary: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(row for row in summary["checks"] if row["id"] == check_id)


def manifest_path(case: AssetCase) -> Path:
    return case.evidence_root / "payload/native.inspect/data/native.manifest.json"


def assert_complete_native_summary(case: AssetCase, summary: dict[str, Any]) -> None:
    applicable = {
        row["id"] for row in summary["checks"] if row["raw_status"] != "NotApplicableByContract"
    }
    assert applicable == NATIVE_CHECK_IDS and len(applicable) == 24
    assert all(check(summary, check_id)["raw_status"] == "Pass" for check_id in NATIVE_CHECK_IDS)
    assert set(summary["gates"]) == NATIVE_GATE_IDS and len(summary["gates"]) == 3
    assert all(gate["complete"] and not gate["findings"] for gate in summary["gates"].values())
    evidence = read_json(case.evidence_root / "evidence-manifest.json")
    assert sum(row["id"].startswith("image.") for row in evidence["files"]) == 135
    assert sum(row["id"].startswith("diff.") for row in evidence["files"]) == 99


def actual_replay(case: AssetCase, target: Path) -> SimpleNamespace:
    evidence = read_json(case.evidence_root / "evidence-manifest.json")
    files = {
        row["id"]: BoundFile(
            row["id"], case.evidence_root / "payload" / row["path"], row["bytes"], row["sha256"]
        )
        for row in evidence["files"]
    }
    target.mkdir()
    for file_id in (
        "native.comparisons",
        "render.same_process",
        "render.fresh_a",
        "render.fresh_b",
    ):
        copied = target / (file_id + ".json")
        shutil.copyfile(files[file_id].path, copied)
        files[file_id] = measure_file(copied, 64 * 1024 * 1024, file_id=file_id)
    run_data = read_json(case.evidence_root / "payload/run.json")
    findings: dict[str, list[Finding]] = {}
    for row in evidence["files"]:
        if not row["id"].endswith(".result"):
            continue
        result = read_json(case.evidence_root / "payload" / row["path"])
        for outcome in result["checks"]:
            findings[outcome["id"]] = [Finding(**finding) for finding in outcome["findings"]]
    return SimpleNamespace(files=files, results={}, jobs=run_data["jobs"], findings=findings)


def assert_actual_replay_rejects_confusion(case: AssetCase) -> None:
    contract = load_contract(case.contract_path, candidate_root=case.source_root)
    replay = actual_replay(case, case.root / "actual-replay")
    summary = read_json(case.evidence_root / "summary.json")
    findings, gates = native_results(contract, replay)
    gate_rows = json.loads(json.dumps({key: asdict(value) for key, value in gates.items()}))
    assert gate_rows == summary["gates"]
    for check_id, actual in findings.items():
        assert [asdict(finding) for finding in actual] == check(summary, check_id)["findings"]

    def clone() -> SimpleNamespace:
        return SimpleNamespace(
            files=dict(replay.files),
            results={},
            jobs=deepcopy(replay.jobs),
            findings=deepcopy(replay.findings),
        )

    wrong_pair = clone()
    comparisons = read_json(replay.files["native.comparisons"].path)
    comparisons["comparisons"][0]["right_id"] = comparisons["comparisons"][0]["left_id"]
    wrong_path = case.root / "wrong-pair.json"
    wrong_path.write_text(json.dumps(comparisons))
    wrong_pair.files["native.comparisons"] = measure_file(
        wrong_path, 64 * 1024 * 1024, file_id="native.comparisons"
    )

    missing_image = clone()
    missing_image.files.pop(comparisons["comparisons"][1]["left_id"])

    wrong_pid = clone()
    observed = next(row for row in wrong_pid.jobs if row["job_id"] == "native.render.same_process")
    observed["pid"] += 1

    for mutant in (wrong_pair, missing_image, wrong_pid):
        with pytest.raises(AcceptanceFailure) as caught:
            native_results(contract, mutant)
        assert caught.value.code == "tool_output_invalid"


@pytest.mark.parametrize(
    "fixture_name,state,reason_owner,reason_code,blocker",
    [
        ("good", "NEEDS_REVIEW", None, None, None),
        ("missing_bottom", "REJECTED", "native.reference", "reference_objects_mismatch", None),
        ("zero_scale", "REJECTED", "r4.visual.scene_not_empty", "degenerate_world_triangle", None),
        (
            "same_counts_surface",
            "REJECTED",
            "native.reference",
            "reference_meshes_mismatch",
            None,
        ),
        (
            "transform_wrong",
            "REJECTED",
            "native.reference",
            "reference_objects_mismatch",
            None,
        ),
        (
            "material_missing",
            "REJECTED",
            "r2.material.slots_resolved",
            "used_material_unresolved",
            None,
        ),
        (
            "material_changed",
            "REJECTED",
            "native.reference",
            "reference_materials_mismatch",
            None,
        ),
        (
            "invalid_face",
            "UNVERIFIED",
            "r2.geometry.validate_clean",
            "mesh_validate_changed",
            "r2.geometry.validate_clean",
        ),
        (
            "nan",
            "UNVERIFIED",
            "r2.inventory.no_nan_inf",
            "non_finite_data",
            "r2.inventory.no_nan_inf",
        ),
        (
            "curve",
            "UNVERIFIED",
            "r2.inventory.coverage_complete",
            "capability_gap",
            "r2.inventory.coverage_complete",
        ),
        (
            "missing_dependency",
            "UNVERIFIED",
            "r2.dependency.all_present",
            "dependency_missing",
            "r2.inventory.coverage_complete",
        ),
        (
            "reserved_material",
            "REJECTED",
            "r2.inventory.no_reserved_props",
            "reserved_property",
            None,
        ),
    ],
)
def test_native_positive_and_actual_bad_assets(
    tmp_path: Path,
    calibration: Path,
    fixture_name: str,
    state: str,
    reason_owner: str | None,
    reason_code: str | None,
    blocker: str | None,
) -> None:
    case = prepare_native_case(BLENDER, tmp_path, fixture_name, calibration_root=calibration)
    exit_code, result = run_case(case)
    assert exit_code == 1 and result["state"] == state
    summary = read_json(case.evidence_root / "summary.json")
    assert summary["success"] is (fixture_name == "good")
    if fixture_name in {"invalid_face", "nan"}:
        assert summary["failure_code"] == "check_failed"
    if reason_owner in NATIVE_GATE_IDS:
        assert reason_code in finding_codes(summary["gates"][reason_owner])
    elif reason_owner is not None:
        assert reason_code in finding_codes(check(summary, reason_owner))
        assert reason_owner in summary["failed_check_ids"]
    run = read_json(case.evidence_root / "payload/run.json")
    evidence = read_json(case.evidence_root / "evidence-manifest.json")
    if blocker is None:
        assert all(row["started"] for row in run["jobs"])
        assert all(gate["complete"] for gate in summary["gates"].values())
    else:
        downstream = [row for row in run["jobs"] if row["job_id"] != "native.inspect"]
        assert downstream and all(not row["started"] for row in downstream)
        assert all(blocker in row["blocked_by"] for row in downstream)
        unproduced = [row for row in evidence["unproduced"] if row["job_id"] != "native.inspect"]
        assert unproduced and all(blocker in row["blocked_by"] for row in unproduced)
    if fixture_name == "good":
        assert_complete_native_summary(case, summary)
        assert not (case.evidence_root / "completion.json").exists()
        assert not (case.evidence_root / "review.json").exists()
        assert (
            result["bindings"]["D"]
            == hashlib.sha256((case.source_root / "asset.blend").read_bytes()).hexdigest()
        )
        assert_actual_replay_rejects_confusion(case)


def assert_supported_feature(manifest: dict[str, Any], fixture_name: str) -> None:
    body = next(row for row in manifest["objects"] if row["id"] == ["OBJECT", "Body"])
    if fixture_name in {"bevel", "triangulate"}:
        expected = fixture_name.upper()
        assert [row["type"] for row in body["modifiers"]] == [expected]
        authored = manifest["meshes"]["Body"]["authored"]
        evaluated = manifest["meshes"]["Body"]["evaluated"]
        if fixture_name == "bevel":
            assert len(evaluated["vertices"]) > len(authored["vertices"])
            assert len(evaluated["polygons"]) > len(authored["polygons"])
        else:
            assert len(authored["polygons"]) == 6 and len(evaluated["polygons"]) == 12
    elif fixture_name == "packed_image":
        dependency = next(
            row for row in manifest["dependencies"] if row["id"] == ["IMAGE", "Packed color"]
        )
        assert dependency["packed"] is True and dependency["bytes"] > 0
        assert len(dependency["sha256"]) == 64
        material = next(
            row for row in manifest["materials"] if row["id"] == ["MATERIAL", "Body material"]
        )
        assert any(
            row["type"] == "TEX_IMAGE" and row["image"] == "Packed color"
            for row in material["nodes"]
        )
        assert any(link[1] == "Color" and link[3] == "Base Color" for link in material["links"])
    else:
        assert body["custom_props"]["nested"]["review"] == {
            "weight": [1.0, 2.5],
            "visible": True,
        }


@pytest.mark.parametrize("fixture_name", ["bevel", "triangulate", "packed_image", "nested_custom"])
def test_each_supported_capability_has_its_own_complete_positive(
    tmp_path: Path, fixture_name: str
) -> None:
    reference = prepare_calibration(BLENDER, tmp_path / "reference", fixture_name)
    case = prepare_native_case(BLENDER, tmp_path / "case", fixture_name, calibration_root=reference)
    exit_code, result = run_case(case)
    assert exit_code == 1 and result["state"] == "NEEDS_REVIEW"
    summary = read_json(case.evidence_root / "summary.json")
    assert summary["success"] is True
    assert_complete_native_summary(case, summary)
    candidate_manifest = read_json(manifest_path(case))
    reference_manifest = read_json(case.source_root / "reference/manifest.json")
    assert_supported_feature(candidate_manifest, fixture_name)
    assert_supported_feature(reference_manifest, fixture_name)


def evidence_rows(case: AssetCase) -> dict[str, dict[str, Any]]:
    return {
        row["id"]: row for row in read_json(case.evidence_root / "evidence-manifest.json")["files"]
    }


def fixture_review(case: AssetCase, result: dict[str, Any]) -> dict[str, Any]:
    rows = evidence_rows(case)
    images = []
    for file_id in case.document["review"]["required_image_ids"]:
        row = rows[file_id]
        path = case.evidence_root / "payload" / row["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == row["sha256"]
        images.append({"id": file_id, "sha256": digest})
    return {
        "schema_version": 2,
        "bindings": result["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_images": images,
                "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "note": "Test-only fixture authorization. This is not a human approval of production artwork.",
            }
        ],
    }


def call_cli(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (sys.executable, str(REPO / "scripts/asset_accept.py"), *map(str, args)),
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=900,
    )


def assert_ready_for_fixture_review(case: AssetCase, result: dict[str, Any]) -> None:
    assert result["state"] == "NEEDS_REVIEW"
    assert read_json(case.evidence_root / "summary.json")["success"] is True
    assert not (case.evidence_root / "review.json").exists()
    assert not (case.evidence_root / "completion.json").exists()


def test_review_and_delivery_bind_exact_frozen_D(tmp_path: Path, calibration: Path) -> None:
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    _, result = run_case(case)
    assert_ready_for_fixture_review(case, result)
    review_document = fixture_review(case, result)
    manifest_before = (case.evidence_root / "evidence-manifest.json").read_bytes()
    summary_before = (case.evidence_root / "summary.json").read_bytes()
    assert result["bindings"]["E"] == hashlib.sha256(manifest_before).hexdigest()
    assert result["bindings"]["V"] == hashlib.sha256(summary_before).hexdigest()

    rejected_reviews = []
    wrong_e = deepcopy(review_document)
    wrong_e["bindings"]["E"] = "0" * 64
    rejected_reviews.append(wrong_e)
    wrong_v = deepcopy(review_document)
    wrong_v["bindings"]["V"] = "0" * 64
    rejected_reviews.append(wrong_v)
    wrong_hash = deepcopy(review_document)
    wrong_hash["records"][0]["reviewed_images"][0]["sha256"] = "0" * 64
    rejected_reviews.append(wrong_hash)
    swapped_ids = deepcopy(review_document)
    images = swapped_ids["records"][0]["reviewed_images"]
    images[0]["id"], images[1]["id"] = images[1]["id"], images[0]["id"]
    rejected_reviews.append(swapped_ids)

    review_path = case.root / "fixture-review.json"
    for document in rejected_reviews:
        review_path.write_text(json.dumps(document))
        rejected = call_cli(
            "review",
            "--evidence-root",
            case.evidence_root,
            "--delivery",
            case.source_root / "asset.blend",
            "--review",
            review_path,
        )
        assert rejected.returncode != 0
        assert not (case.evidence_root / "review.json").exists()
        assert not (case.evidence_root / "completion.json").exists()
        assert (case.evidence_root / "evidence-manifest.json").read_bytes() == manifest_before
        assert (case.evidence_root / "summary.json").read_bytes() == summary_before

    review_path.write_text(json.dumps(review_document))
    finished = call_cli(
        "review",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        case.source_root / "asset.blend",
        "--review",
        review_path,
    )
    assert finished.returncode == 0, finished.stderr
    completion = json.loads(finished.stdout)
    assert completion["state"] in {"SHIP", "SHIP_WITH_NOTES"}
    assert (case.evidence_root / "evidence-manifest.json").read_bytes() == manifest_before
    assert (case.evidence_root / "summary.json").read_bytes() == summary_before
    stored_review = read_json(case.evidence_root / "review.json")
    assert stored_review["review"]["records"] == review_document["records"]
    assert (
        completion["bindings"]["Q"]
        == hashlib.sha256((case.evidence_root / "review.json").read_bytes()).hexdigest()
    )

    source = (case.source_root / "asset.blend").read_bytes()
    changed = bytearray(source)
    changed[len(changed) // 2] ^= 1
    wrong = case.root / "changed-delivery.blend"
    wrong.write_bytes(changed)
    destination = case.root / "rejected-delivery.blend"
    rejected = call_cli(
        "deliver",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        wrong,
        "--destination",
        destination,
    )
    assert rejected.returncode != 0
    assert not destination.exists()
    assert not (case.evidence_root / "delivery-receipt.json").exists()

    destination = case.root / "accepted-delivery.blend"
    delivered = call_cli(
        "deliver",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        case.source_root / "asset.blend",
        "--destination",
        destination,
    )
    assert delivered.returncode == 0, delivered.stderr
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == result["bindings"]["D"]
    receipt = json.loads(delivered.stdout)
    assert receipt["D"] == result["bindings"]["D"]
    assert (
        receipt["T"]
        == hashlib.sha256((case.evidence_root / "completion.json").read_bytes()).hexdigest()
    )


def test_missing_image_cannot_be_signed_off(tmp_path: Path, calibration: Path) -> None:
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    _, result = run_case(case)
    review = case.root / "fixture-review.json"
    review.write_text(json.dumps(fixture_review(case, result)))
    manifest_before = (case.evidence_root / "evidence-manifest.json").read_bytes()
    summary_before = (case.evidence_root / "summary.json").read_bytes()
    row = evidence_rows(case)["image.same_process.0.bottom.wire"]
    (case.evidence_root / "payload" / row["path"]).unlink()
    rejected = call_cli(
        "review",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        case.source_root / "asset.blend",
        "--review",
        review,
    )
    assert rejected.returncode != 0
    assert not (case.evidence_root / "review.json").exists()
    assert not (case.evidence_root / "completion.json").exists()
    assert (case.evidence_root / "evidence-manifest.json").read_bytes() == manifest_before
    assert (case.evidence_root / "summary.json").read_bytes() == summary_before


def test_uncalibrated_platform_remains_unverified(tmp_path: Path, calibration: Path) -> None:
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    case.document["native"]["render"]["platform"]["gpu"] = "unrecognized-fixture-platform"
    write_case(case)
    exit_code, result = run_case(case)
    assert exit_code == 1 and result["state"] == "UNVERIFIED"
    summary = read_json(case.evidence_root / "summary.json")
    assert summary["success"] is False
    assert summary["gates"]["native.scope_supported"]["complete"] is True
    for gate_id in ("native.cross_process", "native.reference"):
        assert summary["gates"][gate_id]["complete"] is False
        assert "unknown_platform" in finding_codes(summary["gates"][gate_id])


@pytest.mark.parametrize("outcome", ["approved", "rejected"])
def test_optional_review_after_durable_summary_uses_actual_verdict(
    tmp_path: Path, calibration: Path, monkeypatch: pytest.MonkeyPatch, outcome: str,
) -> None:
    from acceptance import evidence as module
    from acceptance.native_run import run_native
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    case.document["review"]["required"] = False
    write_case(case)
    original = module._write

    def stop(path, value):
        result = original(path, value)
        if path.name == "summary.json":
            raise RuntimeError("durable native summary exit")
        return result

    case.evidence_root.mkdir(mode=0o700)
    with monkeypatch.context() as patch:
        patch.setattr(module, "_write", stop)
        with pytest.raises(RuntimeError, match="durable native summary exit"):
            run_native(case.contract_path, case.source_root, case.evidence_root, case.scratch_root)
    before = (case.evidence_root / "summary.json").read_bytes()
    summary = json.loads(before)
    assert_complete_native_summary(case, summary)
    bindings = {key: summary[key] for key in ("C", "S", "E")}
    bindings.update(D=summary["D"]["sha256"], V=hashlib.sha256(before).hexdigest())
    review = fixture_review(case, {"bindings": bindings})
    review["records"][0]["outcome"] = outcome
    result = module.finish_review(case.evidence_root, delivery_path=case.source_root / "asset.blend", review=review)
    assert result["state"] == ("SHIP" if outcome == "approved" else "REJECTED")
    assert (case.evidence_root / "summary.json").read_bytes() == before
    target = case.root / "delivered.blend"
    if outcome == "rejected":
        with pytest.raises(AcceptanceFailure):
            module.deliver(case.evidence_root, delivery_path=case.source_root / "asset.blend", destination=target)
        assert not target.exists()
    else:
        module.deliver(case.evidence_root, delivery_path=case.source_root / "asset.blend", destination=target)
        assert target.read_bytes() == (case.source_root / "asset.blend").read_bytes()
