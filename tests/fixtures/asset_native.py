# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
"""Saved/reopened fixture gate for a disposable background Blender process."""

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.blender_scripts import native_collect
from acceptance.native_checks import (
    inspect_checks,
    scene_geometry_findings,
    reference_findings,
    validate_manifest,
)

collect = native_collect.collect
LIMITS = {
    "max_objects": 1000,
    "max_vertices": 1000000,
    "max_triangles": 2000000,
    "max_image_pixels": 1048576,
}


def reopen(name):
    bpy.ops.wm.open_mainfile(
        filepath=str(root / (name + ".blend")), load_ui=False, use_scripts=False
    )


def write(name, value):
    (root / (name + ".json")).write_text(json.dumps(value, sort_keys=True, allow_nan=False))


def saved(name, variant=None):
    bpy.ops.wm.save_as_mainfile(filepath=str(root / (name + ".blend")))
    reopen(name)
    if variant is not None:
        postload(variant)
    digest = hashlib.sha256((root / (name + ".blend")).read_bytes()).hexdigest()
    manifest = collect("Scene", "ViewLayer", 1)
    validate_manifest(manifest, LIMITS)
    assert hashlib.sha256((root / (name + ".blend")).read_bytes()).hexdigest() == digest
    write(name, manifest)
    return manifest


root = Path(sys.argv[sys.argv.index("--") + 1])
root = root.resolve()
assert not root.is_relative_to(Path(__file__).resolve().parents[2])
root.mkdir(parents=True, exist_ok=False)


def base():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = bpy.data.materials.new("Body material")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.2, 0.05, 1)
    for name, location, scale in [
        ("Body", (0, 0, 0), (1, 1, 0.7)),
        ("Top", (0, 0, 1), (1.1, 1.1, 0.12)),
        ("Bottom", (0, 0, -0.9), (0.6, 0.6, 0.1)),
    ]:
        bpy.ops.mesh.primitive_cube_add(location=location)
        obj = bpy.context.object
        obj.name = name
        obj.scale = scale
        obj.data.materials.append(mat)


base()
reference = saved("reference")
base()
good = saved("good")
assert not reference_findings(good, reference)
variants = (
    "missing_bottom",
    "zero_scale",
    "material_missing",
    "invalid_face",
    "curve",
    "triangulate",
    "bevel",
    "packed_image",
    "nan",
    "same_counts_surface",
    "transform_wrong",
    "material_changed",
    "nested_custom",
    "reserved_material",
    "missing_dependency",
    "custom_nan",
    "plain_collection",
    "holdout",
    "indirect_only",
    "object_holdout",
    "object_shadow_catcher",
    "muted_node",
    "reserved_tree",
    "reserved_master",
    "tree_driver",
    "offscene_object",
    "orphan_mesh",
    "offscene_collection",
    "shared_mesh",
    "shared_reserved",
    "multiview",
    "cycles_output",
    "eevee_output",
)


def mutate(variant):
    body = bpy.data.objects["Body"]
    if variant == "missing_bottom":
        bpy.data.objects.remove(bpy.data.objects["Bottom"], do_unlink=True)
    if variant == "zero_scale":
        body.scale = (0, 0, 0)
    if variant == "material_missing":
        body.data.materials.clear()
    if variant == "invalid_face":
        mesh = bpy.data.meshes.new("Invalid")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 0, 1)])
        body.data = mesh
    if variant == "curve":
        curve = bpy.data.objects.new("Curve object", bpy.data.curves.new("Curve", "CURVE"))
        bpy.context.scene.collection.objects.link(curve)
    if variant == "triangulate":
        body.modifiers.new("Triangulate", "TRIANGULATE")
    if variant == "bevel":
        body.modifiers.new("Bevel", "BEVEL")
    if variant == "object_holdout":
        body.is_holdout = True
    if variant == "object_shadow_catcher":
        body.is_shadow_catcher = True
    if variant == "packed_image":
        image = bpy.data.images.new("Packed color", width=2, height=2)
        image.pixels[:] = [0.8, 0.2, 0.1, 1] * 4
        image.pack()
        tree = body.data.materials[0].node_tree
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        tree.links.new(node.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    if variant == "nan":
        body.data.vertices[0].co.x = float("nan")
    if variant == "same_counts_surface":
        body.data.vertices[0].co.x += 0.2
    if variant == "transform_wrong":
        body.location.x += 0.1
    if variant == "material_changed":
        body.data.materials[0].node_tree.nodes["Principled BSDF"].inputs[
            "Base Color"
        ].default_value = (1, 1, 1, 1)
    if variant == "nested_custom":
        body["nested"] = {"review": {"weight": [1.0, 2.5], "visible": True}}
    if variant == "reserved_material":
        body.data.materials[0]["bcx_uid"] = "candidate-forged"
    if variant == "missing_dependency":
        image = bpy.data.images.new("Missing external", width=2, height=2)
        image.source = "FILE"
        image.filepath = "//does-not-exist.png"
        tree = body.data.materials[0].node_tree
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        tree.links.new(node.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    if variant == "custom_nan":
        body["nested"] = {"weights": [1.0, float("nan")]}
    if variant in {"plain_collection", "holdout", "indirect_only"}:
        collection = bpy.data.collections.new("Parts/Assembly")
        bpy.context.scene.collection.children.link(collection)
        for parent in list(body.users_collection):
            parent.objects.unlink(body)
        collection.objects.link(body)
        if variant != "plain_collection":
            setattr(
                bpy.context.view_layer.layer_collection.children[collection.name], variant, True
            )
    if variant == "muted_node":
        body.data.materials[0].node_tree.nodes["Principled BSDF"].mute = True
    if variant == "reserved_tree":
        body.data.materials[0].node_tree["acceptance_forged"] = True
    if variant == "reserved_master":
        bpy.context.scene.collection["bcx_uid"] = "candidate-forged"
    if variant == "tree_driver":
        body.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Roughness"].driver_add(
            "default_value"
        )
    if variant == "offscene_object":
        obj = bpy.data.objects.new("Offscene", body.data)
        obj.use_fake_user = True
    if variant == "orphan_mesh":
        mesh = body.data.copy()
        mesh.name = "Orphan"
        mesh.use_fake_user = True
    if variant == "offscene_collection":
        collection = bpy.data.collections.new("Offscene")
        collection.use_fake_user = True
    if variant in {"shared_mesh", "shared_reserved"}:
        bpy.data.objects["Top"].data = body.data
        if variant == "shared_reserved":
            body.data["bcx_uid"] = "shared-forged"
    if variant == "multiview":
        for suffix, color in [("_L", (1, 0, 0, 1)), ("_R", (0, 1, 0, 1))]:
            image = bpy.data.images.new("source" + suffix, width=2, height=2)
            image.pixels[:] = list(color) * 4
            image.file_format = "PNG"
            image.save(filepath=str(root / ("stereo" + suffix + ".png")))
            bpy.data.images.remove(image)
        bpy.context.scene.render.use_multiview = True
        bpy.ops.image.open(
            filepath=str(root / "stereo_L.png"),
            use_multiview=True,
            use_sequence_detection=False,
            use_udim_detecting=False,
        )
        image = bpy.data.images["stereo_L.png"]
        tree = body.data.materials[0].node_tree
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        tree.links.new(node.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
        image.views_format = "INDIVIDUAL"
        image.reload()
        assert len(image.pixels[:4]) == 4
        image.pack()
    if variant in {"cycles_output", "eevee_output"}:
        target = "CYCLES" if variant == "cycles_output" else "EEVEE"
        body.data.materials[0].node_tree.nodes["Material Output"].target = target


def postload(variant):
    body = bpy.data.objects["Body"]
    if variant == "invalid_face":
        assert [loop.vertex_index for loop in body.data.loops] == [0, 0, 1]
    if variant == "nan":
        assert math.isnan(body.data.vertices[0].co.x)
    if variant in {"holdout", "indirect_only"}:
        assert getattr(bpy.context.view_layer.layer_collection.children["Parts/Assembly"], variant)
    if variant == "object_holdout":
        assert body.is_holdout
    if variant == "object_shadow_catcher":
        assert body.is_shadow_catcher
    if variant == "muted_node":
        assert body.data.materials[0].node_tree.nodes["Principled BSDF"].mute
    if variant == "reserved_tree":
        assert body.data.materials[0].node_tree["acceptance_forged"]
    if variant == "reserved_master":
        assert bpy.context.scene.collection["bcx_uid"] == "candidate-forged"
    if variant == "tree_driver":
        assert body.data.materials[0].node_tree.animation_data.drivers
    if variant == "offscene_object":
        assert bpy.data.objects["Offscene"] not in list(bpy.context.scene.objects)
    if variant == "orphan_mesh":
        assert bpy.data.meshes["Orphan"].use_fake_user
    if variant == "offscene_collection":
        assert bpy.data.collections["Offscene"].use_fake_user
    if variant == "shared_mesh":
        assert bpy.data.objects["Top"].data == body.data
    if variant == "multiview":
        image = bpy.data.images["stereo_L.png"]
        assert image.use_multiview and len(image.packed_files) == 2
        hashes = [hashlib.sha256(bytes(p.packed_file.data)).hexdigest() for p in image.packed_files]
        assert len(set(hashes)) == 2
        write("multiview_payloads", hashes)
    if variant in {"cycles_output", "eevee_output"}:
        target = "CYCLES" if variant == "cycles_output" else "EEVEE"
        assert body.data.materials[0].node_tree.nodes["Material Output"].target == target

    if variant == "missing_bottom":
        assert "Bottom" not in bpy.data.objects
    if variant == "zero_scale":
        assert list(body.scale) == [0, 0, 0]
    if variant == "material_missing":
        assert not body.data.materials
    if variant == "curve":
        assert bpy.data.objects["Curve object"].type == "CURVE"
    if variant in {"triangulate", "bevel"}:
        assert body.modifiers[0].type == variant.upper()
    if variant == "packed_image":
        image = bpy.data.images["Packed color"]
        assert image.packed_file.size > 0 and len(image.packed_files) == 1
        assert not image.use_multiview
    if variant == "same_counts_surface":
        assert len(body.data.vertices) == 8 and len(body.data.polygons) == 6
        assert math.isclose(body.data.vertices[0].co.x, -0.8, abs_tol=1e-6)
    if variant == "transform_wrong":
        assert math.isclose(body.location.x, 0.1, abs_tol=1e-6)
    if variant == "material_changed":
        assert list(
            body.data.materials[0]
            .node_tree.nodes["Principled BSDF"]
            .inputs["Base Color"]
            .default_value
        ) == [1, 1, 1, 1]
    if variant == "nested_custom":
        assert body["nested"].to_dict() == {"review": {"weight": [1.0, 2.5], "visible": True}}
    if variant == "custom_nan":
        assert math.isnan(body["nested"]["weights"][1])
    if variant == "reserved_material":
        assert body.data.materials[0]["bcx_uid"] == "candidate-forged"
    if variant == "missing_dependency":
        image = bpy.data.images["Missing external"]
        assert image.packed_file is None and not Path(bpy.path.abspath(image.filepath)).exists()
    if variant == "plain_collection":
        layer = bpy.context.view_layer.layer_collection.children["Parts/Assembly"]
        assert not layer.holdout and not layer.indirect_only
    if variant == "shared_reserved":
        assert bpy.data.objects["Top"].data == body.data
        assert body.data["bcx_uid"] == "shared-forged"


results = {"reference": reference, "good": good}
for variant in variants:
    reopen("good")
    mutate(variant)
    results[variant] = saved(variant, variant)

for name in (
    "reference",
    "good",
    "triangulate",
    "bevel",
    "packed_image",
    "plain_collection",
    "shared_mesh",
):
    result = results[name]
    assert not result["scope_gaps"], (name, result["scope_gaps"])
    assert not any(c["findings"] for c in inspect_checks(result, True)), name
    assert not scene_geometry_findings(result), name
for name in ("triangulate", "bevel", "packed_image", "shared_mesh"):
    if name != "shared_mesh":
        assert reference_findings(results[name], reference), name
    base()
    mutate(name)
    assert not reference_findings(results[name], saved(name + "_reference", name)), name
for name in ("missing_bottom", "same_counts_surface", "transform_wrong", "material_changed"):
    assert reference_findings(results[name], reference), name
assert scene_geometry_findings(results["zero_scale"])
assert any(
    c["id"] == "r2.material.slots_resolved" and c["findings"]
    for c in inspect_checks(results["material_missing"], True)
)
invalid = results["invalid_face"]["meshes"]["Body"]["authored"]
assert invalid["loops"] == [0, 0, 1] and invalid["validate_corrected"]
assert not invalid["triangles_complete"] and not invalid["triangles"]
for name, path in [
    ("nan", ["meshes", "Body", "authored", "vertices", 0, 0]),
    ("custom_nan", ["objects", 0, "custom_props", "nested", "weights", 1]),
]:
    assert {"path": path, "value": "nan"} in results[name]["invalid_numbers"]
    item = results[name]
    for segment in path:
        item = item[segment]
    assert item is None
assert results["nan"]["meshes"]["Body"]["authored"]["validate_corrected"]
assert results["nested_custom"]["objects"][0]["custom_props"]["nested"]["review"] == {
    "weight": [1.0, 2.5],
    "visible": True,
}
assert len(results["shared_reserved"]["reserved_props"]) == 1
assert not results["shared_reserved"]["scope_gaps"]
for name in ("reserved_material", "reserved_tree", "reserved_master"):
    assert results[name]["reserved_props"], name
    assert any(
        c["id"] == "r2.inventory.no_reserved_props" and c["findings"]
        for c in inspect_checks(results[name], True)
    )
for name, prefix in [
    ("curve", "object-type:"),
    ("holdout", "layer-holdout:"),
    ("indirect_only", "layer-indirect-only:"),
    ("object_holdout", "object-holdout:Body"),
    ("object_shadow_catcher", "object-shadow-catcher:Body"),
    ("muted_node", "material-node-muted:"),
    ("tree_driver", "animation:"),
    ("offscene_object", "uncollected:objects:"),
    ("orphan_mesh", "uncollected:meshes:"),
    ("offscene_collection", "uncollected:collections:"),
    ("multiview", "image-multiview:"),
    ("multiview", "image-multiple-packed-files:"),
    ("missing_dependency", "external-image:"),
    ("cycles_output", "material-output-target:Body material:Material Output:CYCLES"),
]:
    assert any(gap.startswith(prefix) for gap in results[name]["scope_gaps"]), (name, prefix)
    assert not results[name]["occurrences_complete"]
    assert next(
        check for check in inspect_checks(results[name], True)
        if check["id"] == "r2.inventory.coverage_complete"
    )["findings"], name
assert not results["eevee_output"]["scope_gaps"]
assert results["eevee_output"]["occurrences_complete"]
assert not any(c["findings"] for c in inspect_checks(results["eevee_output"], True))
assert not scene_geometry_findings(results["eevee_output"])
assert not reference_findings(results["eevee_output"], reference)
for name, kind in [
    ("offscene_object", "objects"),
    ("orphan_mesh", "meshes"),
    ("offscene_collection", "collections"),
]:
    assert (
        next(row for row in results[name]["coverage"] if row["type"] == kind)["policy"]
        == "unsupported"
    )
assert any(
    c["id"] == "r2.dependency.all_present" and c["findings"]
    for c in inspect_checks(results["missing_dependency"], True)
)
reopen("packed_image")
image = bpy.data.images["Packed color"]
dependency = results["packed_image"]["dependencies"][0]
assert dependency["bytes"] == image.packed_file.size > 0
assert dependency["sha256"] == hashlib.sha256(bytes(image.packed_file.data)).hexdigest()


def exceeds(limits, message):
    try:
        collect("Scene", "ViewLayer", 1, limits=limits)
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("collection did not enforce " + message)


exceeds(LIMITS | {"max_image_pixels": 3}, "image")
reopen("missing_dependency")
collect("Scene", "ViewLayer", 1, limits=LIMITS | {"max_image_pixels": 1})
reopen("good")
exceeds(LIMITS | {"max_objects": 2}, "object")
exceeds(LIMITS | {"max_vertices": 16}, "authored")
exceeds(LIMITS | {"max_triangles": 24}, "authored")
collect("Scene", "ViewLayer", 1, limits=LIMITS | {"max_vertices": 24, "max_triangles": 36})
reopen("bevel")
exceeds(LIMITS | {"max_vertices": 24}, "evaluated")
exceeds(LIMITS | {"max_triangles": 36}, "evaluated")

# Inject failures only around real Blender meshes, retaining normal ownership/finally.
reopen("good")
mesh_ids = {mesh.as_pointer() for mesh in bpy.data.meshes}
for _ in range(3):
    assert collect("Scene", "ViewLayer", 1) == good
    assert {mesh.as_pointer() for mesh in bpy.data.meshes} == mesh_ids
original_geometry = native_collect.geometry
calls, temporary = [], []


def fail_evaluated(mesh, limits):
    calls.append(mesh)
    if len(calls) == 2:
        temporary.append(mesh)
        raise RuntimeError("injected evaluated collection error")
    return original_geometry(mesh, limits)


native_collect.geometry = fail_evaluated
try:
    try:
        collect("Scene", "ViewLayer", 1)
    except RuntimeError as error:
        assert str(error) == "injected evaluated collection error"
    else:
        raise AssertionError("injected exception did not execute")
finally:
    native_collect.geometry = original_geometry
assert {mesh.as_pointer() for mesh in bpy.data.meshes} == mesh_ids
try:
    temporary[0].name
except ReferenceError:
    pass
else:
    raise AssertionError("evaluated temporary mesh was not released")


def fail_validation(frame, event, arg):
    if (
        frame.f_code is original_geometry.__code__
        and event == "line"
        and "duplicate" in frame.f_locals
    ):
        import linecache

        if "duplicate.validate(" in linecache.getline(frame.f_code.co_filename, frame.f_lineno):
            raise RuntimeError("injected validation error")
    return fail_validation


sys.settrace(fail_validation)
try:
    try:
        original_geometry(bpy.data.objects["Body"].data, LIMITS)
    except RuntimeError as error:
        assert str(error) == "injected validation error"
    else:
        raise AssertionError("validation exception did not execute")
finally:
    sys.settrace(None)
assert {mesh.as_pointer() for mesh in bpy.data.meshes} == mesh_ids
assert collect("Scene", "ViewLayer", 1) == good
write(
    "fixture_gate",
    {
        "blender": bpy.app.version_string,
        "build": bpy.app.build_hash.decode(),
        "variants": list(results),
        "saved_reopened": True,
        "aggregate_budgets": True,
        "cleanup_repeats": 3,
        "cleanup_exceptions": ["validation", "evaluated"],
        "file_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.glob("*.blend"))
        },
    },
)
print("NATIVE_COLLECTOR_FIXTURES_OK")
