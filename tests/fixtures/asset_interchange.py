# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
import copy
import json
import sys
from pathlib import Path

import bpy

repository = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repository))
from acceptance.blender_scripts.projection_capture import capture
from acceptance.interchange_policy import PRESET, validate_interchange_policy
from acceptance.projection import compare_projection
from tests.unit.interchange_support import policy as make_policy


def clean(report):
    return not any(report[key] for key in ("preserved", "transformed", "loss", "ambiguous"))


def assert_reason(report, bucket, marker):
    assert any(marker in reason for reason in report[bucket]), report
    assert all(
        not report[key]
        for key in ("preserved", "transformed", "loss", "ambiguous")
        if key != bucket
    ), report


args = sys.argv[sys.argv.index("--") + 1 :]
root = Path(args[0])
root.mkdir(parents=True, exist_ok=True)
mode = args[1]
policy = make_policy(Path(args[2]))
validate_interchange_policy(policy)
result = {}

for name in ("cube", "pruning", "texture"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if mode == "build":
        if name == "pruning":
            mesh = bpy.data.meshes.new("Pruned")
            mesh.from_pydata(
                [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
                + [(9 + index, 9, 9) for index in range(9)],
                [],
                [(0, 1, 2)],
            )
            obj = bpy.data.objects.new("Asset", mesh)
            bpy.context.collection.objects.link(obj)
            mesh.uv_layers.new(name="UVMap")
            mesh.uv_layers.new(name="Unused")
        else:
            bpy.ops.mesh.primitive_cube_add(location=(1, 2, 3))
            obj = bpy.context.object
            obj.name = "Asset"
        material = bpy.data.materials.new("Visible")
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (0.2, 0.4, 0.8, 1)
        obj.data.materials.append(material)
        obj["label"] = "fixture"
        if name == "pruning":
            obj.data.materials.append(bpy.data.materials.new("Unused"))
        if name == "texture":
            image = bpy.data.images.new("Texture", width=2, height=2, alpha=True)
            image.pixels = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 1]
            image.filepath_raw = str(root / "texture.png")
            image.file_format = "PNG"
            image.save()
            bpy.data.images.remove(image)
            image = bpy.data.images.load(str(root / "texture.png"))
            image.pack()
            texture = material.node_tree.nodes.new("ShaderNodeTexImage")
            texture.image = image
            material.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
        bpy.context.view_layer.update()
        (root / f"{name}-source.json").write_text(
            json.dumps(capture([obj], policy), allow_nan=False)
        )
        bpy.ops.wm.save_as_mainfile(filepath=str(root / f"{name}.blend"))
        obj["bcx_uid"] = json.dumps(["OBJECT", obj.name])
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.gltf(filepath=str(root / f"{name}.glb"), **PRESET)
        continue

    bpy.ops.import_scene.gltf(filepath=str(root / f"{name}.glb"))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    imported = capture(objects, policy, imported=True)
    expected = json.loads((root / f"{name}-source.json").read_text())
    (root / f"{name}-import.json").write_text(json.dumps(imported, allow_nan=False))
    positive = compare_projection(expected, imported, policy)
    assert clean(positive), positive
    case = {
        "source_vertices": expected["objects"][0]["vertices"],
        "import_vertices": imported["objects"][0]["vertices"],
        "source_slots": expected["objects"][0]["slots"],
        "import_slots": imported["objects"][0]["slots"],
        "positive": positive,
        "negative": {},
    }
    oracles = {
        "surface": ("transformed", "p02-p08"),
        "material": ("transformed", "p02-p08"),
        "uv": ("transformed", "p02-p08"),
        "identity": ("preserved", "p01/p09"),
        "custom": ("preserved", "p12"),
        "texture": ("transformed", "p02-p08"),
        "normal": ("transformed", "p02-p08"),
    }
    mutations = ("surface", "material", "uv", "identity", "custom") + (
        ("texture",) if name == "texture" else ("normal",)
    )
    for mutation in mutations:
        changed = copy.deepcopy(imported)
        first = changed["objects"][0]
        if mutation == "surface":
            first["triangles"][0]["corners"][0]["position"][0] += 0.1
        elif mutation == "material":
            first["triangles"][0]["material"]["pbr"]["roughness"] = 0.99
        elif mutation == "uv":
            first["triangles"][0]["corners"][0]["uv"][0][0] += 0.1
        elif mutation == "identity":
            first["id"][1] = "forged"
        elif mutation == "custom":
            first["custom"]["label"] = "changed"
        elif mutation == "texture":
            first["triangles"][0]["material"]["texture"]["pixels"] = "0" * 64
        else:
            first["triangles"][0]["corners"][0]["normal"][0] += 0.2
        checked = compare_projection(expected, changed, policy)
        bucket, marker = oracles[mutation]
        assert_reason(checked, bucket, marker)
        case["negative"][mutation] = checked[bucket]

    obj = objects[0]
    obj.location.x += 0.2
    bpy.context.view_layer.update()
    moved = compare_projection(expected, capture(objects, policy, imported=True), policy)
    assert_reason(moved, "transformed", "p13")
    case["actual_transform_negative"] = moved["transformed"]
    obj.location.x -= 0.2
    bpy.context.view_layer.update()
    roughness = obj.data.materials[0].node_tree.nodes.get("Principled BSDF").inputs["Roughness"]
    roughness.default_value = 0.95
    changed = compare_projection(expected, capture(objects, policy, imported=True), policy)
    assert_reason(changed, "transformed", "p02-p08")
    case["actual_material_negative"] = changed["transformed"]
    result[name] = case

if mode == "build":
    (root / "policy.json").write_text(json.dumps(policy, indent=2))
else:
    (root / "probe-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
