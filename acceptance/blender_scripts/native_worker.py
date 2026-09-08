# ruff: noqa: E402 -- Blender --python entrypoint must establish the trusted repo path.
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from acceptance.worker_protocol import read_request, write_result
from acceptance.input_bundle import measure_file
from acceptance.native_policy import validate_native_parameters, VIEWS, PASSES
from acceptance.native_checks import (
    inspect_checks,
    scene_geometry_findings,
    reference_findings,
    finding,
    validate_manifest,
)
from acceptance.blender_scripts.native_collect import collect
from acceptance.blender_scripts.native_render import render_images, compare
from acceptance.strict_json import strict_json_loads


def read_json(path: Path, limit: int = 64 * 1024 * 1024) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("native JSON exceeds bounded input")
    data = strict_json_loads(raw)
    if not isinstance(data, dict):
        raise ValueError("native JSON object required")
    return data


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        stream.write("\n")


def work(request: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = request["parameters"]
    validate_native_parameters(parameters)
    operation = parameters["operation"]
    policy = parameters["policy"]
    inputs = {x["id"]: Path(request["input_root"]) / x["path"] for x in request["inputs"]}
    outputs = {x["id"]: Path(request["output_root"]) / x["path"] for x in request["outputs"]}
    if operation == "compare":
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
                        else policy["render"]["reference_images"][view + "." + render_pass]
                    )
                    diff_id = f"diff.{group}.{view}.{render_pass}"
                    outputs[diff_id].parent.mkdir(parents=True, exist_ok=True)
                    result = compare(
                        inputs[left],
                        inputs[right],
                        outputs[diff_id],
                        policy["geometry_limits"]["max_image_pixels"],
                    )
                    result.update(
                        {
                            "group": group,
                            "view": view,
                            "pass": render_pass,
                            "left_id": left,
                            "right_id": right,
                            "diff_id": diff_id,
                        }
                    )
                    comparisons.append(result)
        source = read_json(inputs["native.manifest"])
        reference = read_json(inputs[policy["reference_manifest_id"]])
        validate_manifest(source, policy["geometry_limits"])
        validate_manifest(reference, policy["geometry_limits"])
        write_json(
            outputs["native.comparisons"],
            {
                "schema_version": 2,
                "comparisons": comparisons,
                "reference_findings": reference_findings(source, reference),
                "geometry_findings": scene_geometry_findings(source),
                "scope_gaps": source["scope_gaps"],
                "platform": {
                    "blender": bpy.app.version_string,
                    "build": bpy.app.build_hash.decode(),
                    "decoder": "blender-rgba-f32-v1",
                    "execution": "cpu-image-decode",
                },
            },
        )
        return []
    original = inputs["asset"]
    assets = [row for row in request["inputs"] if row["id"] == "asset"]
    if len(assets) != 1:
        raise ValueError("unique frozen asset descriptor required")
    expected_bytes, expected_sha = assets[0]["bytes"], assets[0]["sha256"]

    def identity(path: Path) -> tuple[int, str]:
        measured = measure_file(path, expected_bytes, file_id="asset")
        return measured.bytes, measured.sha256

    expected = (expected_bytes, expected_sha)
    # The request already verified this physical job parent; avoid macOS /var aliases.
    # Only trusted local source is accepted; no OS/network isolation is claimed.
    with tempfile.TemporaryDirectory(
        prefix="native-fresh-", dir=Path(request["output_root"]).parent
    ) as directory:
        fresh = Path(directory) / "asset.blend"
        copied = measure_file(original, expected_bytes, file_id="asset", copy_to=fresh)
        if (copied.bytes, copied.sha256) != expected:
            raise ValueError("original does not match frozen asset D")
        if identity(original) != expected or identity(fresh) != expected:
            raise ValueError("fresh path copy does not match frozen asset D")
        bpy.ops.wm.open_mainfile(filepath=str(fresh), load_ui=False, use_scripts=False)
        manifest = collect(
            policy["scene"], policy["view_layer"], policy["frame"], limits=policy["geometry_limits"]
        )
        limits = policy["geometry_limits"]
        if (
            len(manifest["objects"]) > limits["max_objects"]
            or sum(len(m["evaluated"]["vertices"]) for m in manifest["meshes"].values())
            > limits["max_vertices"]
            or sum(len(m["evaluated"]["triangles"]) for m in manifest["meshes"].values())
            > limits["max_triangles"]
        ):
            raise ValueError("bounded native profile geometry limit exceeded")
        validate_manifest(manifest, limits)
        original_after, fresh_after = identity(original), identity(fresh)
        stable = original_after == expected == fresh_after
        if operation == "inspect":
            write_json(outputs["native.manifest"], manifest)
            write_json(
                outputs["native.dependencies"],
                {"schema_version": 2, "dependencies": manifest["dependencies"]},
            )
            return inspect_checks(manifest, stable)
        if operation == "reopen":
            source = read_json(inputs["native.manifest"])
            write_json(outputs["native.reopened"], manifest)
            write_json(
                outputs["native.reopen_dependencies"],
                {
                    "schema_version": 2,
                    "dependencies": manifest["dependencies"],
                    "offline_mode": bpy.app.online_access is False,
                    "input_sha256": expected_sha,
                    "input_bytes": expected_bytes,
                    "reopened_sha256": fresh_after[1],
                    "reopened_bytes": fresh_after[0],
                    "fresh_path": str(fresh),
                    "external_dependency_count": sum(
                        not d["packed"] for d in manifest["dependencies"]
                    ),
                },
            )
            return [
                {
                    "id": "r4.reopen.offline_ok",
                    "findings": []
                    if not bpy.app.online_access and stable
                    else [
                        finding("offline_reopen_not_proven", "Offline flag or D digest mismatch")
                    ],
                    "metrics": {},
                },
                {
                    "id": "r4.reopen.dependencies_resolved",
                    "findings": []
                    if all(d["packed"] and d["sha256"] for d in manifest["dependencies"])
                    else [finding("dependency_missing", "Native dependency not packed")],
                    "metrics": {},
                },
                {
                    "id": "r4.reopen.manifest_matches_source",
                    "findings": []
                    if source == manifest
                    else [
                        finding(
                            "reopen_manifest_mismatch", "Authored/evaluated/dependencies changed"
                        )
                    ],
                    "metrics": {},
                },
            ]
        experiment = parameters["experiment"]
        report = render_images(manifest, policy["render"], outputs, experiment)
        original_after, fresh_after = identity(original), identity(fresh)
        if original_after != expected or fresh_after != expected:
            raise ValueError("render changed frozen asset D")
        report["source_digest_before"] = expected_sha
        report["source_digest_after"] = original_after[1]
        write_json(outputs["render." + experiment], report)
        if experiment != "same_process":
            return []
        return [
            {
                "id": "r4.visual.scene_not_empty",
                "findings": scene_geometry_findings(manifest),
                "metrics": {},
            },
            {
                "id": "r4.visual.self_determinism",
                "findings": [],
                "metrics": {"measurement_ready": True},
            },
            {
                "id": "r4.visual.platform_key_known",
                "findings": []
                if report["platform"] == policy["render"]["platform"]
                else [finding("unknown_platform", "Observed platform differs from calibration")],
                "metrics": {},
            },
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    request = read_request(args.request)
    checks = work(request)
    write_result(
        request,
        checks,
        {
            "pid": str(os.getpid()),
            "blender": bpy.app.version_string,
            "build": bpy.app.build_hash.decode(),
        },
    )


if __name__ == "__main__":
    main()
