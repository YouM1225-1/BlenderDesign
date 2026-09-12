# ruff: noqa: E402 -- Blender entrypoint establishes trusted repository path.
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import bpy

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from acceptance.blender_scripts.native_render import (
    compare,
    render_images,
)
from acceptance.blender_scripts.native_worker import (
    read_json,
    write_json,
)
from acceptance.blender_scripts.projection_capture import (
    capture,
    render_manifest,
)
from acceptance.interchange_policy import (
    validate_interchange_policy,
)
from acceptance.native_policy import PASSES, VIEWS
from acceptance.projection import validate_projection
from acceptance.worker_protocol import read_request, write_result
from acceptance.input_bundle import measure_file
from acceptance.interchange_results import resources_read


def work(request: Any) -> Any:
    p = request["parameters"]
    if set(p) != {"operation", "policy", "native"} or p["operation"] not in {
        "export",
        "import",
        "source_render",
        "compare",
    }:
        raise ValueError("closed GLB worker operation required")
    policy = p["policy"]
    validate_interchange_policy(policy)
    inputs = {x["id"]: Path(request["input_root"]) / x["path"] for x in request["inputs"]}
    outputs = {x["id"]: Path(request["output_root"]) / x["path"] for x in request["outputs"]}
    if p["operation"] == "compare":
        rows = []
        for view in VIEWS:
            for render_pass in PASSES:
                left = f"image.projection_source.0.{view}.{render_pass}"
                right = f"image.projection_import.0.{view}.{render_pass}"
                diff = f"diff.projection.{view}.{render_pass}"
                outputs[diff].parent.mkdir(parents=True, exist_ok=True)
                row = compare(
                    inputs[left],
                    inputs[right],
                    outputs[diff],
                    p["native"]["geometry_limits"]["max_image_pixels"],
                )
                row.update(
                    {
                        "view": view,
                        "pass": render_pass,
                        "left_id": left,
                        "right_id": right,
                        "diff_id": diff,
                    }
                )
                rows.append(row)
        write_json(outputs["projection.visual"], {"schema_version": 2, "comparisons": rows})
        return []
    fid = "delivery.glb" if p["operation"] == "import" else "asset"
    descriptors = [row for row in request["inputs"] if row["id"] == fid]
    if len(descriptors) != 1:
        raise ValueError("unique frozen input descriptor required")
    descriptor = descriptors[0]

    def identity() -> str:
        measured = measure_file(inputs[fid], descriptor["bytes"], file_id=fid)
        if (measured.bytes, measured.sha256) != (descriptor["bytes"], descriptor["sha256"]):
            raise ValueError("input differs from frozen descriptor")
        return measured.sha256

    before = identity()
    if p["operation"] == "import":
        validation = read_json(inputs["validator.report"])
        budget = read_json(inputs["glb.budget"])
        if (
            validation["issues"]["truncated"]
            or validation["issues"]["numErrors"]
            or budget["extensions"]
            or budget["exceeded"]
        ):
            raise ValueError("import blocked by unsafe/incomplete GLB validation or budget")
        if not resources_read(
            read_json(inputs["validator.resources"]),
            validation,
            budget,
            policy,
            input_sha256=before,
            input_bytes=descriptor["bytes"],
        ):
            raise ValueError("import blocked by resource evidence")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        identity()
        bpy.ops.import_scene.gltf(filepath=str(inputs["delivery.glb"]))
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        projection = capture(objects, policy, imported=True)
        validate_projection(projection, policy["limits"]["max_projection_triangles"])
        write_json(outputs["projection.import"], projection)
        report = render_images(
            render_manifest(objects),
            p["native"]["render"],
            outputs,
            "projection_import",
        )
        report["input_sha256_before"] = before
        report["input_sha256_after"] = identity()
        write_json(outputs["render.projection_import"], report)
        return [
            {
                "id": "r4.import.manifest_written",
                "findings": [],
                "metrics": {"objects": len(objects)},
            }
        ]
    bpy.ops.wm.open_mainfile(filepath=str(inputs["asset"]), load_ui=False, use_scripts=False)
    native = p["native"]
    bpy.context.window.scene = bpy.data.scenes[native["scene"]]
    bpy.context.window.view_layer = bpy.context.scene.view_layers[native["view_layer"]]
    bpy.context.scene.frame_set(native["frame"])
    manifest = read_json(inputs["native.manifest"])
    objects = [bpy.context.scene.objects[o["source"][1]] for o in manifest["occurrences"]]
    if any(o.type == "EMPTY" and list(o.keys()) for o in bpy.context.scene.objects):
        raise ValueError("custom properties on omitted EMPTY unsupported")
    if any(
        k.startswith(("bcx_", "acceptance_")) for o in bpy.context.scene.objects for k in o.keys()
    ):
        raise ValueError("candidate cannot supply evaluator identity")
    projection = capture(objects, policy)
    validate_projection(projection, policy["limits"]["max_projection_triangles"])
    if p["operation"] == "source_render":
        frozen = read_json(inputs["projection.source"])
        if projection != frozen:
            raise ValueError("recovered source differs from frozen projection")
        from acceptance.blender_scripts.projection_capture import projected_surface

        with projected_surface(objects, frozen, policy) as projected:
            report = render_images(
                render_manifest(projected), native["render"], outputs, "projection_source"
            )
        report["input_sha256_before"] = before
        report["input_sha256_after"] = identity()
        write_json(outputs["render.projection_source"], report)
        return []
    write_json(outputs["projection.source"], projection)
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj["bcx_uid"] = json.dumps(["OBJECT", obj.name], ensure_ascii=False, separators=(",", ":"))
        obj.select_set(True)
    if not objects:
        raise ValueError("no exportable surfaces")
    bpy.context.view_layer.objects.active = objects[0]
    outputs["delivery.glb"].parent.mkdir(parents=True, exist_ok=True)
    if outputs["delivery.glb"].exists():
        raise FileExistsError(outputs["delivery.glb"])
    identity()
    bpy.ops.export_scene.gltf(filepath=str(outputs["delivery.glb"]), **policy["preset"])
    after = identity()
    write_json(
        outputs["export.measurements"],
        {
            "schema_version": 2,
            "source_before": before,
            "source_after": after,
            "delivery_sha256": measure_file(
                outputs["delivery.glb"], policy["limits"]["max_glb_bytes"], file_id="delivery.glb"
            ).sha256,
            "exported_ids": [x["id"] for x in projection["objects"]],
            "preset": policy["preset"],
        },
    )

    def finding(code: Any) -> Any:
        return {"code": code, "severity": "error", "pointer": None, "detail": code}

    return [
        {
            "id": "r3.export.file_nonempty",
            "findings": []
            if outputs["delivery.glb"].stat().st_size > 20
            else [finding("empty_export")],
            "metrics": {},
        },
        {
            "id": "r3.export.source_unchanged",
            "findings": [] if before == after else [finding("source_modified")],
            "metrics": {},
        },
    ]


def main() -> Any:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    request = read_request(args.request)
    checks = work(request)
    write_result(request, checks, {"pid": str(os.getpid()), "blender": bpy.app.version_string})


if __name__ == "__main__":
    main()
