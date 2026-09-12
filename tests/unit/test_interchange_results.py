import pytest
from acceptance.interchange_results import validate_export_evidence
from acceptance.primitives import AcceptanceFailure
from tests.unit.interchange_support import PRESET, projection
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from acceptance.interchange_results import interchange_results
from acceptance.native_policy import PASSES, VIEWS
from tests.unit.interchange_support import policy
from tests.unit.test_native_policy import policy as native_policy


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "source_before",
        "source_after",
        "delivery_sha256",
        "preset",
        "exported_ids",
        "unknown",
        "native_scope",
    ],
)
def test_controller_rejects_each_export_measurement_mismatch(field):
    source = projection()
    native = {"occurrences": [{"source": ["OBJECT", "Asset"]}]}
    value = {
        "schema_version": 2,
        "source_before": "a" * 64,
        "source_after": "a" * 64,
        "delivery_sha256": "b" * 64,
        "preset": dict(PRESET),
        "exported_ids": [["OBJECT", "Asset"]],
    }
    validate_export_evidence(
        value,
        source,
        native,
        source_sha256="a" * 64,
        delivery_sha256="b" * 64,
        preset=PRESET,
    )
    if field == "schema_version":
        value[field] = True
    elif field in {"source_before", "source_after", "delivery_sha256"}:
        value[field] = "c" * 64
    elif field == "preset":
        value[field]["export_yup"] = False
    elif field == "exported_ids":
        value[field] = []
    elif field == "unknown":
        value[field] = "extra"
    else:
        native["occurrences"] = []
    with pytest.raises(AcceptanceFailure):
        validate_export_evidence(
            value,
            source,
            native,
            source_sha256="a" * 64,
            delivery_sha256="b" * 64,
            preset=PRESET,
        )


def visual_case(tmp_path):
    native = native_policy()
    files, comparisons, reports = {}, [], {}

    def put(fid, value):
        path = tmp_path / fid
        raw = json.dumps(value).encode() if isinstance(value, dict) else value
        path.write_bytes(raw)
        files[fid] = SimpleNamespace(
            path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)
        )

    for experiment in ("projection_source", "projection_import"):
        records = []
        for view in VIEWS:
            for render_pass in PASSES:
                fid = f"image.{experiment}.0.{view}.{render_pass}"
                put(fid, b"same encoded pixels")
                records.append(
                    dict(
                        id=fid,
                        view=view,
                        **{"pass": render_pass},
                        repetition=0,
                        pid=23,
                        experiment=experiment,
                        engine="BLENDER_EEVEE" if render_pass == "beauty" else "BLENDER_WORKBENCH",
                    )
                )
        reports[experiment] = dict(
            schema_version=2,
            settings=native["render"],
            platform=native["render"]["platform"],
            images=records,
            input_sha256_before="a" * 64,
            input_sha256_after="a" * 64,
        )
        put("render." + experiment, reports[experiment])
    files["delivery.glb"] = SimpleNamespace(sha256="a" * 64)
    for view in VIEWS:
        for render_pass in PASSES:
            left = f"image.projection_source.0.{view}.{render_pass}"
            right = f"image.projection_import.0.{view}.{render_pass}"
            diff = f"diff.projection.{view}.{render_pass}"
            put(diff, b"difference PNG placeholder: reducer seam only")
            comparisons.append(
                dict(
                    decoder="blender-rgba-f32-v1",
                    size=[1024, 1024],
                    channels=4,
                    precision="float32",
                    color_interpretation="Blender PNG decode, Standard output",
                    left_bytes_sha256=files[left].sha256,
                    right_bytes_sha256=files[right].sha256,
                    different_channels=0,
                    different_pixels=0,
                    max_abs=0,
                    left_rgb_energy=100,
                    right_rgb_energy=100,
                    view=view,
                    **{"pass": render_pass},
                    left_id=left,
                    right_id=right,
                    diff_id=diff,
                )
            )
    data = dict(schema_version=2, comparisons=comparisons)
    put("projection.visual", data)
    contract = SimpleNamespace(
        raw=dict(
            native=native,
            interchange=policy(tmp_path),
            input={"files": [{"id": "asset", "sha256": "a" * 64}]},
        )
    )
    run = SimpleNamespace(
        files=files,
        findings={},
        jobs=[
            dict(job_id="glb." + e, started=True, started_at="2026-09-13T00:00:00Z", pid=23)
            for e in reports
        ],
    )
    return contract, run, data, reports, put


@pytest.mark.parametrize(
    "mutation",
    [
        "zero_diff_energy",
        "same_bytes_beauty_diff",
        "hash_energy",
        "schema_float",
        "channels_float",
        "size_float",
        "render_schema_float",
        "pid_float",
        "missing_start",
        "duplicate_job",
        "huge_max",
        "huge_energy",
        "row_list",
        "view_list",
        "image_list",
        "pid_bool",
        "started_int",
        "repetition_float",
        "bad_source_hash",
    ],
)
def test_projection_reducer_rejects_invalid_measurements(tmp_path, mutation):
    contract, run, data, reports, put = visual_case(tmp_path)
    assert not interchange_results(contract, run)[0]["r4.visual.source_import_match"]
    row = data["comparisons"][0]
    if mutation == "zero_diff_energy":
        run.files[row["right_id"]].sha256 = "b" * 64
        row["right_bytes_sha256"] = "b" * 64
        row["right_rgb_energy"] = 99
    elif mutation == "same_bytes_beauty_diff":
        row.update(different_channels=1, different_pixels=1, max_abs=0.1)
    elif mutation == "hash_energy":
        row.update(left_rgb_energy=99, right_rgb_energy=99)
    elif mutation == "schema_float":
        data["schema_version"] = 2.0
    elif mutation == "channels_float":
        row["channels"] = 4.0
    elif mutation == "size_float":
        row["size"] = [1024.0, 1024.0]
    elif mutation == "render_schema_float":
        reports["projection_source"]["schema_version"] = 2.0
    elif mutation == "pid_float":
        reports["projection_source"]["images"][0]["pid"] = 23.0
    elif mutation == "missing_start":
        run.jobs[0]["started_at"] = None
    elif mutation == "duplicate_job":
        run.jobs.append(deepcopy(run.jobs[0]))
    elif mutation == "huge_max":
        row["max_abs"] = 10**400
    elif mutation == "huge_energy":
        row["left_rgb_energy"] = 10**400
    elif mutation == "row_list":
        data["comparisons"][0] = []
    elif mutation == "view_list":
        row["view"] = []
    elif mutation == "image_list":
        reports["projection_source"]["images"] = [[]]
    elif mutation == "pid_bool":
        run.jobs[0]["pid"] = True
    elif mutation == "started_int":
        run.jobs[0]["started"] = 1
    elif mutation == "repetition_float":
        reports["projection_source"]["images"][0]["repetition"] = 0.0
    elif mutation == "bad_source_hash":
        reports["projection_source"]["input_sha256_after"] = "b" * 64
    put("projection.visual", data)
    for e, report in reports.items():
        put("render." + e, report)
    with pytest.raises(AcceptanceFailure) as exc:
        interchange_results(contract, run)
    assert exc.value.code == "tool_output_invalid"


@pytest.mark.parametrize(
    "variant",
    [
        "equal_encoding",
        "different_encoding",
        "quality_difference",
        "edge_on_black",
        "empty_right",
        "observed_beauty",
        "observed_wire",
    ],
)
def test_projection_reducer_controls(tmp_path, variant):
    contract, run, data, reports, put = visual_case(tmp_path)
    if variant == "edge_on_black":
        row = data["comparisons"][0]
        for side in ("left", "right"):
            sha = side[0] * 64
            run.files[row[side + "_id"]].sha256 = sha
            row[side + "_bytes_sha256"] = sha
            row[side + "_rgb_energy"] = 0
    if variant == "empty_right":
        for row in data["comparisons"]:
            run.files[row["right_id"]].sha256 = "b" * 64
            row.update(
                right_bytes_sha256="b" * 64,
                right_rgb_energy=0,
                different_channels=1,
                different_pixels=1,
                max_abs=0.1,
            )
    if variant in ("different_encoding", "quality_difference", "observed_beauty", "observed_wire"):
        row = next(
            r
            for r in data["comparisons"]
            if r["pass"]
            == (
                "clay"
                if variant == "quality_difference"
                else "wire"
                if variant == "observed_wire"
                else "beauty"
            )
        )
        run.files[row["right_id"]].sha256 = "b" * 64
        row["right_bytes_sha256"] = "b" * 64
        if variant != "different_encoding":
            row.update(different_channels=1, different_pixels=1, max_abs=0.1)
    put("projection.visual", data)
    findings = interchange_results(contract, run)[0]["r4.visual.source_import_match"]
    if variant == "quality_difference":
        assert [f.code for f in findings] == ["projection_pixel_mismatch"]
    elif variant == "empty_right":
        assert any(f.code == "empty_projection_diagnostic" for f in findings)
    else:
        assert not findings


def test_export_preset_numeric_boolean_is_not_the_frozen_preset():
    source = projection()
    native = {"occurrences": [{"source": ["OBJECT", "Asset"]}]}
    value = dict(
        schema_version=2,
        source_before="a" * 64,
        source_after="a" * 64,
        delivery_sha256="b" * 64,
        preset=dict(PRESET),
        exported_ids=[["OBJECT", "Asset"]],
    )
    value["preset"]["export_yup"] = 1
    with pytest.raises(AcceptanceFailure):
        validate_export_evidence(
            value, source, native, source_sha256="a" * 64, delivery_sha256="b" * 64, preset=PRESET
        )
