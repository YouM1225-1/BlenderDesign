"""Run with an isolated factory-startup Blender; no file or render is opened."""

# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.blender_scripts.projection_capture import capture, render_manifest
from acceptance.projection import compare_projection, validate_projection
from tests.unit.interchange_support import clean, policy


def snapshot(obj):
    return {
        "mesh_slots": [m.name if m else None for m in obj.data.materials],
        "effective_slots": [s.material.name if s.material else None for s in obj.material_slots],
        "links": [s.link for s in obj.material_slots],
        "face_indices": [p.material_index for p in obj.data.polygons],
        "vertices": [list(v.co) for v in obj.data.vertices],
        "matrix": [list(row) for row in obj.matrix_world],
        "materials": sorted(m.name for m in bpy.data.materials),
        "roughness": {
            m.name: m.node_tree.nodes.get("Principled BSDF").inputs["Roughness"].default_value
            for m in bpy.data.materials
            if m.node_tree and m.node_tree.nodes.get("Principled BSDF")
        },
    }


def main():
    output = Path(sys.argv[sys.argv.index("--") + 1])
    limits = policy(output.parent)
    materials = []
    for name, roughness in [("Mesh first", 0.2), ("Object override", 0.8), ("Mesh last", 0.4)]:
        material = bpy.data.materials.new(name)
        material.node_tree.nodes.get("Principled BSDF").inputs[
            "Roughness"
        ].default_value = roughness
        materials.append(material)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = "Projection material probe"
    obj.data.materials.append(materials[0])
    obj.data.materials.append(None)
    obj.data.materials.append(materials[2])
    for i, polygon in enumerate(obj.data.polygons):
        polygon.material_index = 0 if i % 2 == 0 else 2
    obj.material_slots[0].link = "OBJECT"
    obj.material_slots[0].material = materials[1]
    obj["kept"] = 7
    obj["nested"] = {"group": {"label": "retained", "numbers": [1, 2, 3]}}
    bpy.context.view_layer.update()
    before = snapshot(obj)
    assert before["mesh_slots"] == ["Mesh first", None, "Mesh last"]
    assert before["effective_slots"] == ["Object override", None, "Mesh last"]
    assert before["face_indices"] == [0, 2, 0, 2, 0, 2]
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_slots = [s.material.name if s.material else None for s in evaluated.material_slots]
    assert evaluated_slots == before["effective_slots"]
    obj.data.calc_loop_triangles()
    expected = [
        materials[1 if tri.material_index == 0 else 2]
        .node_tree.nodes.get("Principled BSDF")
        .inputs["Roughness"]
        .default_value
        for tri in obj.data.loop_triangles
    ]
    result = capture([obj], limits)
    validate_projection(result, limits["limits"]["max_projection_triangles"])
    record = result["objects"][0]
    actual = [t["material"]["pbr"]["roughness"] for t in record["triangles"]]
    assert actual == expected, {"actual": actual, "expected": expected}
    assert len(actual) == 12 and len(set(actual)) == 2
    assert record["slots"] == 3
    assert record["custom"] == {
        "kept": 7,
        "nested": {"group": {"label": "retained", "numbers": [1, 2, 3]}},
    }, record["custom"]
    assert snapshot(obj) == before, "capture mutated source data"
    obj["bcx_uid"] = json.dumps(["OBJECT", obj.name])
    imported = capture([obj], limits, imported=True)
    assert clean(compare_projection(result, imported, limits))
    del obj["bcx_uid"]
    assert render_manifest([obj]) == {
        "scope_gaps": [],
        "scene": bpy.context.scene.name,
        "view_layer": bpy.context.view_layer.name,
        "occurrences": [{"source": ["OBJECT", obj.name], "matrix_world": before["matrix"]}],
    }
    obj.data.polygons[0].material_index = 1
    bpy.context.view_layer.update()
    before_empty = snapshot(obj)
    try:
        capture([obj], limits)
    except ValueError as exc:
        assert "explicit Principled material" in str(exc), str(exc)
        empty_error = str(exc)
    else:
        raise AssertionError("used empty material slot was accepted")
    assert snapshot(obj) == before_empty, "failed capture mutated source data"
    output.write_text(
        json.dumps(
            {
                "success": True,
                "version": bpy.app.version_string,
                "build_hash": bpy.app.build_hash.decode(),
                "before": before,
                "evaluated_slots": evaluated_slots,
                "expected_roughness": expected,
                "captured_roughness": actual,
                "projection": result,
                "source_unchanged": True,
                "used_none_rejected": empty_error,
                "source_unchanged_after_failure": True,
                "imported_identity_match": True,
                "python_isolated": bool(sys.flags.isolated),
            },
            indent=2,
            allow_nan=False,
        )
    )
    print("PROJECTION_EFFECTIVE_MATERIAL_CAPTURE_OK")


if __name__ == "__main__":
    main()
