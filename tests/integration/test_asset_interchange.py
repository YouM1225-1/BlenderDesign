import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from acceptance.evidence import deliver, finish_review
from tests.integration.asset_runtime_support import (
    prepare_calibration,
    run_case,
    write_case,
)
from tests.integration.interchange_runtime_support import prepare_interchange_case

# Frozen literal test oracles from reviewed V5 section 7.1 and Interchange plan, 2026-09-13.
# Do not calculate expected values from the runtime plan or summary under test.

INTERCHANGE_CHECK_IDS = {
    "r0.contract.na_set_declared",
    "r0.contract.schema_closed",
    "r0.contract.tools_locked",
    "r1.input.digest_recorded",
    "r1.input.no_link_or_device",
    "r1.input.size_within_limit",
    "r2.dependency.all_present",
    "r2.geometry.manifest_written",
    "r2.geometry.validate_clean",
    "r2.inventory.coverage_complete",
    "r2.inventory.no_nan_inf",
    "r2.inventory.no_reserved_props",
    "r2.material.slots_resolved",
    "r2.source.digest_stable",
    "r3.budget.within_limits",
    "r3.export.file_nonempty",
    "r3.export.source_unchanged",
    "r3.extension.none_forbidden",
    "r3.validator.no_error",
    "r3.validator.report_complete",
    "r3.validator.resources_read",
    "r4.import.manifest_written",
    "r4.projection.ambiguous_object_names",
    "r4.projection.preserved_fields_match",
    "r4.projection.transformed_within_tolerance",
    "r4.projection.undeclared_loss",
    "r4.visual.all_views_rendered",
    "r4.visual.platform_key_known",
    "r4.visual.scene_not_empty",
    "r4.visual.self_determinism",
    "r4.visual.source_import_match",
    "r5.contract.digest_stable",
    "r5.evidence.hashes_match",
    "r5.evidence.manifest_closed",
}

INTERCHANGE_NA_IDS = {
    "r4.reopen.dependencies_resolved",
    "r4.reopen.manifest_matches_source",
    "r4.reopen.offline_ok",
}

INTERCHANGE_GATE_IDS = {
    "interchange.consumer",
    "interchange.scope_supported",
    "native.cross_process",
    "native.reference",
    "native.scope_supported",
}


pytestmark = [
    pytest.mark.timeout(900),
    pytest.mark.skipif(
        os.environ.get("RUN_ASSET_INTERCHANGE") != "1",
        reason="explicit real Blender+Node integration",
    ),
]


@pytest.fixture(scope="module")
def environment(tmp_path_factory):
    blender = Path(os.environ["BLENDER_BIN"])
    node = Path(os.environ["NODE_BIN"])
    package = Path(os.environ["GLTF_PACKAGE_ROOT"])
    root = tmp_path_factory.mktemp("m3-calibration")
    calibration = (
        Path(os.environ["ASSET_CALIBRATION_ROOT"])
        if "ASSET_CALIBRATION_ROOT" in os.environ
        else prepare_calibration(blender, root / "reference")
    )
    return blender, node, Path(sys.executable), package, calibration


def test_real_interchange_full_chain_and_exact_delivery(environment, tmp_path):
    blender, node, python, package, calibration = environment
    case = prepare_interchange_case(
        blender, node, python, package, tmp_path, calibration_root=calibration
    )
    code, status = run_case(case)
    assert status["state"] == "NEEDS_REVIEW", status
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is True and not summary["failed_check_ids"]
    applicable = {
        row["id"] for row in summary["checks"] if row["raw_status"] != "NotApplicableByContract"
    }
    na = {row["id"] for row in summary["checks"] if row["raw_status"] == "NotApplicableByContract"}
    assert applicable == INTERCHANGE_CHECK_IDS and len(applicable) == 34
    assert na == INTERCHANGE_NA_IDS and len(na) == 3
    assert all(row["raw_status"] == "Pass" for row in summary["checks"] if row["id"] in applicable)
    assert set(summary["gates"]) == INTERCHANGE_GATE_IDS and len(summary["gates"]) == 5
    assert all(x["complete"] and not x["findings"] for x in summary["gates"].values())
    # This record authorizes only this generated test asset.
    manifest = json.loads((case.evidence_root / "evidence-manifest.json").read_text())
    files = {x["id"]: x for x in manifest["files"]}
    delivery = case.evidence_root / "payload" / files["delivery.glb"]["path"]
    before = hashlib.sha256(delivery.read_bytes()).hexdigest()
    assert_received_interchange_evidence(case, files)
    review = {
        "schema_version": 2,
        "bindings": status["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_at": "2026-09-08T00:00:00+00:00",
                "reviewed_images": [
                    {"id": fid, "sha256": files[fid]["sha256"]}
                    for fid in case.document["review"]["required_image_ids"]
                ],
                "note": "Generated known-fixture approval only; no production artwork authorized",
            }
        ],
    }
    done = finish_review(case.evidence_root, delivery_path=delivery, review=review)
    assert done["state"] in {"SHIP", "SHIP_WITH_NOTES"}
    assert hashlib.sha256(delivery.read_bytes()).hexdigest() == before
    assert (case.evidence_root / "completion.json").is_file()
    destination = tmp_path / "delivered.glb"
    receipt = deliver(case.evidence_root, delivery_path=delivery, destination=destination)
    assert receipt["D"] == before and hashlib.sha256(destination.read_bytes()).hexdigest() == before
    assert (
        receipt["T"]
        == hashlib.sha256((case.evidence_root / "completion.json").read_bytes()).hexdigest()
    )


def test_missing_consumer_cannot_ship(environment, tmp_path):
    blender, node, python, package, calibration = environment
    case = prepare_interchange_case(
        blender, node, python, package, tmp_path, calibration_root=calibration
    )
    case.document["interchange"]["consumer"] = "required-engine-with-no-adapter"
    write_case(case)
    code, status = run_case(case)
    assert status["state"] == "UNVERIFIED" and code != 0, status
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is False
    assert not summary["gates"]["interchange.consumer"]["complete"]
    assert not summary["failed_check_ids"]
    assert {
        row["id"] for row in summary["checks"] if row["raw_status"] == "Pass"
    } == INTERCHANGE_CHECK_IDS
    assert set(summary["gates"]) == INTERCHANGE_GATE_IDS
    assert all(
        gate["complete"] and not gate["findings"]
        for key, gate in summary["gates"].items()
        if key != "interchange.consumer"
    )
    assert {row["code"] for row in summary["gates"]["interchange.consumer"]["findings"]} == {
        "consumer_adapter_missing"
    }


def test_actual_missing_bottom_is_not_approved(environment, tmp_path):
    blender, node, python, package, calibration = environment
    case = prepare_interchange_case(
        blender,
        node,
        python,
        package,
        tmp_path,
        "missing_bottom",
        calibration_root=calibration,
    )
    code, status = run_case(case)
    assert status["state"] == "REJECTED" and code != 0, status
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is False
    assert summary["gates"]["native.reference"]["findings"]


def assert_received_interchange_evidence(case, files):
    """Actual file/receiver/process evidence, separate from fixed check-set oracles."""
    payload = case.evidence_root / "payload"

    def read(fid):
        return json.loads((payload / files[fid]["path"]).read_text())

    for fid, row in files.items():
        raw = (payload / row["path"]).read_bytes()
        assert len(raw) == row["bytes"] and hashlib.sha256(raw).hexdigest() == row["sha256"], fid
    assert sum(fid.startswith("image.") for fid in files) == 207
    assert sum(fid.startswith("diff.") for fid in files) == 135
    observed = json.loads((payload / "run.json").read_text())["jobs"]
    assert len({row["job_id"] for row in observed}) == len(observed)
    for job in observed:
        assert job["started"] is True and type(job["pid"]) is int and job["pid"] > 0
        assert isinstance(job["started_at"], str) and job["started_at"]
        assert job["exit_code"] == 0 and job["failure_code"] is None
        request, result = read(job["job_id"] + ".request"), read(job["job_id"] + ".result")
        for key in (
            "schema_version",
            "run_id",
            "attempt",
            "nonce",
            "job_id",
            "writer",
            "contract_digest",
            "source_digest",
        ):
            assert request[key] == result[key]
        assert request["writer"] == job["writer"]
    export = read("glb.export.request")
    source = read("glb.projection_source.request")
    imported = read("glb.projection_import.request")

    def descriptor(request, fid):
        return next(row for row in request["inputs"] if row["id"] == fid)

    expected_source = next(row for row in case.document["input"]["files"] if row["id"] == "asset")
    for request in (export, source):
        row = descriptor(request, "asset")
        assert (row["bytes"], row["sha256"]) == (
            expected_source["bytes"],
            expected_source["sha256"],
        )
    for fid, request in (
        ("projection.source", source),
        ("delivery.glb", imported),
        ("validator.resources", imported),
    ):
        row = descriptor(request, fid)
        assert (row["bytes"], row["sha256"]) == (files[fid]["bytes"], files[fid]["sha256"])
    output = next(row for row in export["outputs"] if row["id"] == "delivery.glb")
    incoming = descriptor(imported, "delivery.glb")
    paths = [
        Path(export["output_root"]) / output["path"],
        payload / files["delivery.glb"]["path"],
        Path(imported["input_root"]) / incoming["path"],
    ]
    assert len(set(paths)) == 3
    assert len({hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}) == 1
    assert (
        read("render.projection_source")["settings"]
        == read("render.projection_import")["settings"]
        == case.document["native"]["render"]
    )
    expected_hashes = {
        "projection_source": expected_source["sha256"],
        "projection_import": files["delivery.glb"]["sha256"],
    }
    for experiment, sha in expected_hashes.items():
        report = read("render." + experiment)
        assert report["input_sha256_before"] == report["input_sha256_after"] == sha
        process = next(row for row in observed if row["job_id"] == "glb." + experiment)
        assert len(report["images"]) == 36
        assert all(row["pid"] == process["pid"] for row in report["images"])
        for image in report["images"]:
            raw = (payload / files[image["id"]]["path"]).read_bytes()
            assert raw[:8] == b"\x89PNG\r\n\x1a\n"
            assert int.from_bytes(raw[16:20], "big") == int.from_bytes(raw[20:24], "big") == 1024


def test_actual_frozen_projection_excludes_loose_data(environment, tmp_path):
    from tests.integration.asset_runtime_support import blender_script, REPO

    blender_script(
        Path(os.environ["BLENDER_BIN"]),
        REPO / "tests/fixtures/interchange_projection_probe.py",
        str(tmp_path / "projection"),
        "visual",
        str(environment[4] / "same_process/render.json"),
        environment_root=tmp_path / "blender-user",
    )
    result = json.loads((tmp_path / "projection/result.json").read_text())
    assert (
        result["success"] and result["source_vertices"] == 11 and result["projection_vertices"] == 8
    )
    assert result["retained_triangles"] == 12 and result["missing_triangle_rejected"]
    assert (tmp_path / "projection/visual-differences.json").is_file()
