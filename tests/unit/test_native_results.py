from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import pytest
from acceptance.native_results import native_results
from acceptance.native_plan import NATIVE_GATES
from acceptance.native_policy import VIEWS, PASSES
from acceptance.primitives import AcceptanceFailure


def image_hash(view, render_pass):
    return hashlib.sha256((view + "." + render_pass).encode()).hexdigest()


def result_case(tmp_path):
    digest = hashlib.sha256(b"fixture").hexdigest()
    render = {
        "platform": {"blender": "locked-fixture-platform", "build": "fixture-build"},
        "max_abs": {p: 0 for p in PASSES},
        "beauty_hard_gate": False,
        "reference_images": {v + "." + p: f"reference.{v}.{p}" for v in VIEWS for p in PASSES},
    }
    contract = SimpleNamespace(
        raw={
            "native": {"render": render},
            "input": {
                "files": [
                    {
                        "id": fid,
                        "sha256": digest if fid == "asset" else image_hash(*fid.split(".")[1:]),
                    }
                    for fid in ("asset", *render["reference_images"].values())
                ]
            },
        }
    )
    files = {}

    def record(fid, value):
        path = tmp_path / (fid + ".json")
        path.write_text(json.dumps(value))
        files[fid] = SimpleNamespace(path=path, sha256=digest)

    jobs = []
    for experiment in ("same_process", "fresh_a", "fresh_b"):
        records = []
        pid = 100 + len(jobs)
        for repetition in range(2 if experiment == "same_process" else 1):
            for view in VIEWS:
                for render_pass in PASSES:
                    if repetition == 1 and render_pass == "beauty":
                        continue
                    fid = f"image.{experiment}.{repetition}.{view}.{render_pass}"
                    files[fid] = SimpleNamespace(sha256=image_hash(view, render_pass))
                    records.append(
                        {
                            "id": fid,
                            "view": view,
                            "pass": render_pass,
                            "repetition": repetition,
                            "pid": pid,
                            "experiment": experiment,
                            "engine": "BLENDER_EEVEE"
                            if render_pass == "beauty"
                            else "BLENDER_WORKBENCH",
                        }
                    )
        record(
            "render." + experiment,
            {
                "schema_version": 2,
                "platform": render["platform"],
                "settings": render,
                "images": records,
                "source_digest_before": digest,
                "source_digest_after": digest,
            },
        )
        jobs.append(
            {
                "job_id": "native.render." + experiment,
                "writer": "render_views(src)"
                if experiment == "same_process"
                else "render_views(src-" + experiment.replace("_", "-") + ")",
                "exit_code": 0,
                "blocked_by": [],
                "failure_code": None,
                "error": None,
                "started": True,
                "started_at": "2026-09-08T00:00:00+00:00",
                "pid": pid,
            }
        )
    comparisons = []
    for group in ("same", "fresh", "reference"):
        for view in VIEWS:
            for render_pass in PASSES:
                if group == "same" and render_pass == "beauty":
                    continue
                left = (
                    f"image.fresh_a.0.{view}.{render_pass}"
                    if group == "fresh"
                    else f"image.same_process.0.{view}.{render_pass}"
                )
                right = (
                    f"image.same_process.1.{view}.{render_pass}"
                    if group == "same"
                    else f"image.fresh_b.0.{view}.{render_pass}"
                    if group == "fresh"
                    else render["reference_images"][view + "." + render_pass]
                )
                diff = f"diff.{group}.{view}.{render_pass}"
                files[diff] = SimpleNamespace(sha256=digest)
                comparisons.append(
                    {
                        "decoder": "blender-rgba-f32-v1",
                        "size": [1024, 1024],
                        "channels": 4,
                        "precision": "float32",
                        "color_interpretation": "Blender PNG decode, Standard output",
                        "left_bytes_sha256": image_hash(view, render_pass),
                        "right_bytes_sha256": image_hash(view, render_pass),
                        "different_channels": 0,
                        "different_pixels": 0,
                        "max_abs": 0,
                        "left_rgb_energy": 100,
                        "right_rgb_energy": 100,
                        "group": group,
                        "view": view,
                        "pass": render_pass,
                        "left_id": left,
                        "right_id": right,
                        "diff_id": diff,
                    }
                )
    data = {
        "schema_version": 2,
        "comparisons": comparisons,
        "reference_findings": [],
        "geometry_findings": [],
        "scope_gaps": [],
        "platform": {
            "blender": "locked-fixture-platform",
            "build": "fixture-build",
            "decoder": "blender-rgba-f32-v1",
            "execution": "cpu-image-decode",
        },
    }
    record("native.comparisons", data)
    record("native.manifest", {"scope_gaps": []})
    run = SimpleNamespace(
        files=files,
        results={},
        jobs=jobs,
        findings={"r4.visual.self_determinism": (), "r4.visual.scene_not_empty": ()},
    )
    return contract, run, data, record


def test_absent_worker_stays_not_tested():
    contract = SimpleNamespace(raw={"native": {}})
    run = SimpleNamespace(files={}, results={}, jobs=(), findings={})
    findings, gates = native_results(contract, run)
    assert findings == {}
    assert set(gates) == set(NATIVE_GATES)
    assert all(not gate.complete for gate in gates.values())


def test_absent_comparator_cannot_leave_completed_render_check_passed():
    contract = SimpleNamespace(raw={"native": {}})
    run = SimpleNamespace(
        files={}, results={}, jobs=(), findings={"r4.visual.self_determinism": ()}
    )
    findings, gates = native_results(contract, run)
    assert findings["r4.visual.self_determinism"]
    assert all(not gate.complete for gate in gates.values())


def test_exact_measurements_complete_the_frozen_gate(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    findings, gates = native_results(contract, run)
    assert not findings["r4.visual.self_determinism"]
    assert all(gate.complete and not gate.findings for gate in gates.values())


@pytest.mark.parametrize(
    "mutation",
    ["wrong_pair", "missing_pair", "duplicate_pair", "contradiction", "wrong_hash", "wrong_color"],
)
def test_invalid_comparison_cannot_pass_even_if_pixels_match(tmp_path, mutation):
    contract, run, data, record = result_case(tmp_path)
    first = data["comparisons"][0]
    if mutation == "wrong_pair":
        first["right_id"] = first["left_id"]
    elif mutation == "missing_pair":
        data["comparisons"].pop()
    elif mutation == "duplicate_pair":
        data["comparisons"].append(deepcopy(first))
    elif mutation == "contradiction":
        first["different_pixels"] = 1
    elif mutation == "wrong_hash":
        first["left_bytes_sha256"] = "0" * 64
    else:
        first["color_interpretation"] = "arbitrary uncalibrated space"
    record("native.comparisons", data)
    with pytest.raises(AcceptanceFailure):
        native_results(contract, run)


def test_render_pid_must_match_controller_observation(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    run.jobs[0]["pid"] += 1
    with pytest.raises(AcceptanceFailure):
        native_results(contract, run)


def test_missing_image_cannot_pass_with_unchanged_report(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    del run.files["image.same_process.0.bottom.wire"]
    with pytest.raises(AcceptanceFailure):
        native_results(contract, run)


def test_black_wire_is_incomplete_diagnostic_evidence(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    for item in data["comparisons"]:
        if item["pass"] == "wire":
            item["left_rgb_energy"] = item["right_rgb_energy"] = 0
    record("native.comparisons", data)
    findings, gates = native_results(contract, run)
    assert findings["r4.visual.scene_not_empty"]
    assert not gates["native.reference"].complete


def test_observe_only_beauty_never_relaxes_diagnostic_gate(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    beauty = next(
        row for row in data["comparisons"] if row["group"] == "fresh" and row["pass"] == "beauty"
    )
    change_image(run, data, beauty["right_id"])
    beauty.update(max_abs=0.1, different_pixels=1, different_channels=1)
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert not gates["native.cross_process"].findings
    clay = next(
        row for row in data["comparisons"] if row["group"] == "fresh" and row["pass"] == "clay"
    )
    change_image(run, data, clay["right_id"])
    clay.update(max_abs=0.1, different_pixels=1, different_channels=1)
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert gates["native.cross_process"].findings


def change_image(run, data, fid, *, energy=None, digest=None):
    """Keep every measurement of a changed fixture artifact bound to its bytes."""
    digest = digest or hashlib.sha256(fid.encode()).hexdigest()
    run.files[fid].sha256 = digest
    for row in data["comparisons"]:
        for side in ("left", "right"):
            if row[side + "_id"] == fid:
                row[side + "_bytes_sha256"] = digest
                if energy is not None:
                    row[side + "_rgb_energy"] = energy


def invalid(contract, run):
    with pytest.raises(AcceptanceFailure) as caught:
        native_results(contract, run)
    assert caught.value.code == "tool_output_invalid"


def test_frozen_evidence_counts(tmp_path):
    contract, run, data, _ = result_case(tmp_path)
    assert len(data["comparisons"]) == 99
    assert sum(row["pass"] == "beauty" for row in data["comparisons"]) == 18
    assert sum(fid.startswith("image.") for fid in run.files) == 135
    assert sum(fid.startswith("diff.") for fid in run.files) == 99
    assert (
        sum(fid.endswith(".beauty") and fid.startswith("image.") for fid in run.files)
        + sum(
            fid.endswith(".beauty")
            for fid in contract.raw["native"]["render"]["reference_images"].values()
        )
        == 36
    )


@pytest.mark.parametrize("render_pass", ["clay", "silhouette", "wire"])
def test_each_fresh_pair_must_have_foreground(tmp_path, render_pass):
    contract, run, data, record = result_case(tmp_path)
    for row in data["comparisons"]:
        if row["group"] == "fresh" and row["pass"] == render_pass:
            digest = hashlib.sha256(("black." + row["view"]).encode()).hexdigest()
            for side in ("left", "right"):
                change_image(run, data, row[side + "_id"], energy=0, digest=digest)
    record("native.comparisons", data)
    findings, gates = native_results(contract, run)
    assert findings["r4.visual.scene_not_empty"]
    assert not gates["native.cross_process"].complete or gates["native.cross_process"].findings


@pytest.mark.parametrize("render_pass", ["clay", "silhouette", "wire"])
def test_second_same_repetition_must_have_foreground(tmp_path, render_pass):
    contract, run, data, record = result_case(tmp_path)
    for row in data["comparisons"]:
        if row["group"] == "same" and row["pass"] == render_pass:
            change_image(run, data, row["right_id"], energy=0)
            row.update(max_abs=1, different_channels=100, different_pixels=100)
    record("native.comparisons", data)
    findings, _ = native_results(contract, run)
    assert any(
        f.code == "diagnostic_render_empty" and "same_process.1" in f.detail
        for f in findings["r4.visual.scene_not_empty"]
    )


def test_single_edge_on_black_view_is_valid(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    for row in data["comparisons"]:
        if row["view"] == "left" and row["pass"] != "beauty":
            row["left_rgb_energy"] = row["right_rgb_energy"] = 0
    record("native.comparisons", data)
    findings, gates = native_results(contract, run)
    assert not any(findings.values())
    assert all(g.complete and not g.findings for g in gates.values())


@pytest.mark.parametrize("field", ["blender", "build", "decoder", "execution"])
def test_comparator_platform_mismatch_is_incomplete_with_reason(tmp_path, field):
    contract, run, data, record = result_case(tmp_path)
    data["platform"][field] = "other-supported-shaped-value"
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    for key in ("native.cross_process", "native.reference"):
        assert not gates[key].complete
        assert any(field in finding.detail for finding in gates[key].findings)


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {},
        {"blender": "fixture"},
        {"blender": "a", "build": "b", "decoder": "c", "execution": "d", "gpu": "extra"},
        {"blender": 2, "build": "b", "decoder": "c", "execution": "d"},
        {"blender": "", "build": "b", "decoder": "c", "execution": "d"},
    ],
)
def test_malformed_comparator_platform_is_invalid(tmp_path, value):
    contract, run, data, record = result_case(tmp_path)
    data["platform"] = value
    record("native.comparisons", data)
    invalid(contract, run)


@pytest.mark.parametrize(
    "mutation", ["zero_energy", "reused_id", "reused_hash", "equal_hash_difference"]
)
def test_contradictory_energy_and_byte_identity_is_invalid(tmp_path, mutation):
    contract, run, data, record = result_case(tmp_path)
    row = data["comparisons"][0]
    if mutation == "zero_energy":
        row["right_rgb_energy"] = 0
    elif mutation == "reused_id":
        row["left_rgb_energy"] = row["right_rgb_energy"] = 999
        change_image(run, data, row["left_id"])
        change_image(run, data, row["right_id"])
    elif mutation == "reused_hash":
        row["left_rgb_energy"] = row["right_rgb_energy"] = 999
    else:
        row = next(r for r in data["comparisons"] if r["pass"] == "beauty")
        row.update(max_abs=0.1, different_pixels=1, different_channels=1)
    record("native.comparisons", data)
    invalid(contract, run)


def test_distinct_png_bytes_can_decode_to_identical_pixels(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    change_image(run, data, data["comparisons"][0]["left_id"])
    record("native.comparisons", data)
    findings, gates = native_results(contract, run)
    assert not any(findings.values())
    assert all(g.complete and not g.findings for g in gates.values())


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2.0),
        ("schema_version", True),
        ("comparisons", {}),
        ("comparisons", [None]),
        ("reference_findings", {}),
        ("reference_findings", [False]),
        ("geometry_findings", False),
        ("geometry_findings", [None]),
        ("scope_gaps", None),
        ("scope_gaps", [1]),
    ],
)
def test_top_level_shapes_are_strict(tmp_path, field, value):
    contract, run, data, record = result_case(tmp_path)
    data[field] = value
    record("native.comparisons", data)
    invalid(contract, run)


@pytest.mark.parametrize(
    "field,value",
    [
        ("channels", 4.0),
        ("channels", True),
        ("size", [1024.0, 1024]),
        ("size", {"x": 1024}),
        ("size", [True, 1024]),
        ("group", []),
        ("view", {}),
        ("pass", None),
        ("left_id", []),
        ("right_id", {}),
        ("diff_id", 1),
        ("left_bytes_sha256", []),
        ("decoder", []),
        ("different_pixels", True),
        ("different_channels", 1.0),
        ("max_abs", True),
        ("max_abs", 10**400),
        ("left_rgb_energy", 10**400),
        ("right_rgb_energy", True),
        ("max_abs", -0.1),
        ("max_abs", 1.1),
        ("left_rgb_energy", -1),
        ("right_rgb_energy", 3 * 1024 * 1024 + 1),
        ("different_pixels", 1024 * 1024 + 1),
    ],
)
def test_measurement_shapes_and_ranges_are_strict(tmp_path, field, value):
    contract, run, data, record = result_case(tmp_path)
    data["comparisons"][0][field] = value
    record("native.comparisons", data)
    invalid(contract, run)


@pytest.mark.parametrize(
    "field,value",
    [
        ("repetition", "0"),
        ("repetition", 0.0),
        ("repetition", False),
        ("pid", 100.0),
        ("pid", True),
        ("pid", 0),
        ("pid", -1),
        ("view", []),
        ("pass", {}),
        ("id", []),
        ("experiment", None),
        ("engine", 1),
    ],
)
def test_image_metadata_shapes_are_strict(tmp_path, field, value):
    contract, run, _, record = result_case(tmp_path)
    report = json.loads(run.files["render.same_process"].path.read_text())
    report["images"][0][field] = value
    record("render.same_process", report)
    invalid(contract, run)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2.0),
        ("images", {}),
        ("images", [None]),
        ("platform", []),
        ("settings", []),
        ("source_digest_before", []),
    ],
)
def test_render_report_shapes_are_strict(tmp_path, field, value):
    contract, run, _, record = result_case(tmp_path)
    report = json.loads(run.files["render.same_process"].path.read_text())
    report[field] = value
    record("render.same_process", report)
    invalid(contract, run)


@pytest.mark.parametrize(
    "field,value",
    [
        ("started", False),
        ("started", 1),
        ("started_at", None),
        ("started_at", ""),
        ("started_at", 42),
        ("pid", 100.0),
        ("pid", True),
        ("pid", -1),
    ],
)
def test_observed_process_identity_is_required(tmp_path, field, value):
    contract, run, _, _ = result_case(tmp_path)
    run.jobs[0][field] = value
    invalid(contract, run)


@pytest.mark.parametrize(
    "mutation", ["missing_job", "duplicate_job", "missing_report", "missing_diff"]
)
def test_required_evidence_and_unique_observation_are_required(tmp_path, mutation):
    contract, run, _, _ = result_case(tmp_path)
    if mutation == "missing_job":
        run.jobs.pop(0)
    elif mutation == "duplicate_job":
        run.jobs.append(deepcopy(run.jobs[0]))
    elif mutation == "missing_report":
        del run.files["render.same_process"]
    else:
        del run.files["diff.same.front.clay"]
    invalid(contract, run)


def test_os_pid_reuse_is_valid_with_observed_job_context(tmp_path):
    contract, run, _, record = result_case(tmp_path)
    for index, job in enumerate(run.jobs):
        job["pid"] = 100
        job["started_at"] = f"2026-09-08T00:00:0{index}+00:00"
        fid = job["job_id"].removeprefix("native.")
        report = json.loads(run.files[fid].path.read_text())
        for row in report["images"]:
            row["pid"] = 100
        record(fid, report)
    findings, gates = native_results(contract, run)
    assert not any(findings.values())
    assert all(g.complete and not g.findings for g in gates.values())


@pytest.mark.parametrize("container", ["reference_findings", "geometry_findings"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("code", 1),
        ("severity", "warning"),
        ("pointer", "/foo"),
        ("detail", None),
        ("disposition", "accepted"),
    ],
)
def test_findings_have_the_existing_closed_shape(tmp_path, container, field, value):
    contract, run, data, record = result_case(tmp_path)
    row = {"code": "problem", "severity": "error", "pointer": None, "detail": "Problem"}
    row[field] = value
    data[container] = [row]
    record("native.comparisons", data)
    invalid(contract, run)


def test_reference_findings_fail_reference_gate(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    data["reference_findings"] = [
        {
            "code": "reference_meshes_mismatch",
            "severity": "error",
            "pointer": None,
            "detail": "mesh",
        }
    ]
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert gates["native.reference"].findings[0].code == "reference_meshes_mismatch"


@pytest.mark.parametrize("source,copied", [([], ["gap"]), (["gap"], []), (["a"], ["b"])])
def test_scope_gap_copy_is_bound_to_manifest(tmp_path, source, copied):
    contract, run, data, record = result_case(tmp_path)
    record("native.manifest", {"scope_gaps": source})
    data["scope_gaps"] = copied
    record("native.comparisons", data)
    invalid(contract, run)


def test_matching_scope_gap_is_incomplete(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    record("native.manifest", {"scope_gaps": ["unsupported curve"]})
    data["scope_gaps"] = ["unsupported curve"]
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert not gates["native.scope_supported"].complete
    assert gates["native.scope_supported"].findings[0].code == "capability_gap"


@pytest.mark.parametrize("value", [None, {}, [1]])
def test_source_scope_gap_shape_is_validated_even_without_comparison(tmp_path, value):
    contract, run, _, record = result_case(tmp_path)
    del run.files["native.comparisons"]
    record("native.manifest", {"scope_gaps": value})
    invalid(contract, run)


def test_missing_manifest_cannot_support_copied_scope(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    del run.files["native.manifest"]
    invalid(contract, run)


def test_beauty_hard_policy_applies_after_measurement_validation(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    contract.raw["native"]["render"]["beauty_hard_gate"] = True
    for job in run.jobs:
        fid = job["job_id"].removeprefix("native.")
        report = json.loads(run.files[fid].path.read_text())
        report["settings"] = contract.raw["native"]["render"]
        record(fid, report)
    row = next(r for r in data["comparisons"] if r["pass"] == "beauty" and r["group"] == "fresh")
    change_image(run, data, row["right_id"])
    row.update(max_abs=0.1, different_pixels=1, different_channels=1)
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert gates["native.cross_process"].findings


def test_comparison_requires_completed_source_writer(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    del run.findings["r4.visual.self_determinism"]
    invalid(contract, run)


@pytest.mark.parametrize("raw", ["[]", '{"a":1,"a":2}', '{"a":NaN}', '{"a":1e400}'])
def test_invalid_json_is_a_typed_rejection(tmp_path, raw):
    contract, run, _, _ = result_case(tmp_path)
    run.files["native.comparisons"].path.write_text(raw)
    invalid(contract, run)


@pytest.mark.parametrize("experiment,side", [("fresh_a", "left"), ("fresh_b", "right")])
def test_one_fresh_experiment_cannot_borrow_other_foreground(tmp_path, experiment, side):
    contract, run, data, record = result_case(tmp_path)
    for row in data["comparisons"]:
        if row["group"] == "fresh" and row["pass"] == "clay":
            change_image(run, data, row[side + "_id"], energy=0)
            row.update(max_abs=1, different_channels=100, different_pixels=100)
    record("native.comparisons", data)
    findings, gates = native_results(contract, run)
    assert any(experiment in f.detail for f in findings["r4.visual.scene_not_empty"])
    assert not gates["native.cross_process"].complete


@pytest.mark.parametrize("field", ["source_digest_before", "source_digest_after"])
def test_source_asset_digest_is_bound_to_frozen_input(tmp_path, field):
    contract, run, _, record = result_case(tmp_path)
    report = json.loads(run.files["render.same_process"].path.read_text())
    report[field] = "0" * 64
    record("render.same_process", report)
    with pytest.raises(AcceptanceFailure) as caught:
        native_results(contract, run)
    assert caught.value.code == "toolchain_mismatch"


def test_valid_shaped_render_platform_mismatch_has_reason(tmp_path):
    contract, run, _, record = result_case(tmp_path)
    report = json.loads(run.files["render.fresh_a"].path.read_text())
    report["platform"]["blender"] = "other-build"
    record("render.fresh_a", report)
    _, gates = native_results(contract, run)
    for key in ("native.cross_process", "native.reference"):
        assert not gates[key].complete
        assert any("fresh_a" in f.detail for f in gates[key].findings)


def test_no_comparator_keeps_render_not_verified_and_scope_independent(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    del run.files["native.comparisons"]
    findings, gates = native_results(contract, run)
    assert findings["r4.visual.self_determinism"]
    assert gates["native.scope_supported"].complete
    assert not gates["native.cross_process"].complete
    assert not gates["native.reference"].complete


@pytest.mark.parametrize("operation", ["missing", "duplicate", "swap", "extra"])
def test_render_image_set_and_metadata_are_exact(tmp_path, operation):
    contract, run, _, record = result_case(tmp_path)
    report = json.loads(run.files["render.same_process"].path.read_text())
    if operation == "missing":
        report["images"].pop()
    elif operation == "duplicate":
        report["images"].append(deepcopy(report["images"][0]))
    elif operation == "swap":
        report["images"][0]["view"] = "back"
    else:
        report["images"][0]["started_at"] = run.jobs[0]["started_at"]
    record("render.same_process", report)
    invalid(contract, run)


def test_oversized_json_is_bounded_and_rejected(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    with run.files["native.comparisons"].path.open("wb") as stream:
        stream.truncate(64 * 1024 * 1024 + 1)
    invalid(contract, run)
