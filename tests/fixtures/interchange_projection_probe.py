# ruff: noqa: E402 -- Establish trusted repository imports in subprocess entrypoint.
"""Actual Blender frozen-projection geometry; no rendering or policy relaxation."""

import json
from pathlib import Path
import sys
import bpy

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from acceptance.blender_scripts import projection_capture as pc
from tests.unit.interchange_support import policy
from tests.fixtures.interchange_png import png

root = Path(sys.argv[sys.argv.index("--") + 1])
root.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.object
obj.name = "Surface"
mat = bpy.data.materials.new("PBR")
obj.data.materials.append(mat)
# Preserve authored cube surface, append a visibly distant loose edge and unused vertex.
mesh = obj.data
vertices = [list(v.co) for v in mesh.vertices] + [[1.4, 0, 0], [1.8, 0, 0], [2, 0, 0]]
faces = [list(p.vertices) for p in mesh.polygons]
new = bpy.data.meshes.new("With loose data")
new.from_pydata(vertices, [(8, 9)], faces)
new.update()
obj.data = new
new.materials.append(mat)
for name in ("UV first", "UV second"):
    uv = new.uv_layers.new(name=name)
    for i, loop in enumerate(uv.data):
        loop.uv = (i / 100, (i % 3) / 3)
new.uv_layers[1].active_render = True
for face in new.polygons:
    face.use_smooth = True
new.normals_split_custom_set([(0, 0, 1)] * len(new.loops))
# Object-level effective material, nested custom property, and nonidentity positive transform.
effective = bpy.data.materials.new("Effective")
effective.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.2, 0.4, 0.8, 1)
obj.material_slots[0].link = "OBJECT"
obj.material_slots[0].material = effective
texture_path = root / "texture.png"
texture_path.write_bytes(png(16))
image = bpy.data.images.load(str(texture_path))
image.pack()
texture = effective.node_tree.nodes.new("ShaderNodeTexImage")
texture.image = image
shader = effective.node_tree.nodes["Principled BSDF"]
effective.node_tree.links.new(texture.outputs["Color"], shader.inputs["Base Color"])
obj["nested"] = {"x": {"v": [1, 2, 3]}}
obj.location = (0.1, 0.2, 0.3)
obj.scale = (1.1, 0.9, 1.2)
bpy.context.view_layer.update()
p = policy(root)
frozen = pc.capture([obj], p)
assert frozen["objects"][0]["vertices"] == 11
before = {o.name for o in bpy.data.objects}
before_meshes = {m.name for m in bpy.data.meshes}
before_materials = {m.name for m in bpy.data.materials}
with pc.projected_surface([obj], frozen, p) as projected:
    assert len(projected) == 1
    surface = projected[0].data
    surface.calc_loop_triangles()
    assert len(surface.vertices) == 8 and len(surface.loop_triangles) == 12
    assert len(surface.edges) == 12 and len(surface.uv_layers) == 2
    assert all(sum(abs(x) for x in v.co) < 6 for v in surface.vertices)
    assert surface.uv_layers[1].active_render
    observed = pc.capture(projected, p)["objects"][0]["triangles"]
    expected = frozen["objects"][0]["triangles"]
    (root / "observed.json").write_text(
        json.dumps(
            dict(
                observed=observed,
                expected=expected,
                attributes=[(a.name, a.data_type, a.domain) for a in surface.attributes],
            )
        )
    )
    for actual, original in zip(observed, expected, strict=True):
        assert actual["material"] == original["material"]
        for a, b in zip(actual["corners"], original["corners"], strict=True):
            assert all(abs(x - y) < 1e-6 for x, y in zip(a["position"], b["position"], strict=True))
            assert all(abs(x - y) < 1e-6 for x, y in zip(a["normal"], b["normal"], strict=True))
            assert a["uv"] == b["uv"]
    manifest = pc.render_manifest(projected)
    assert (
        manifest["scene"] == bpy.context.scene.name
        and manifest["view_layer"] == bpy.context.view_layer.name
    )
assert {o.name for o in bpy.data.objects} == before
assert {m.name for m in bpy.data.meshes} == before_meshes
assert {m.name for m in bpy.data.materials} == before_materials
assert pc.capture([obj], p) == frozen
bad = json.loads(json.dumps(frozen))
bad["objects"][0]["triangles"].pop()
try:
    with pc.projected_surface([obj], bad, p):
        pass
except ValueError:
    pass
else:
    raise AssertionError("missing actual triangle accepted")
(root / "projection.json").write_text(json.dumps(frozen))
(root / "result.json").write_text(
    json.dumps(
        dict(
            success=True,
            source_vertices=11,
            retained_triangles=12,
            projection_vertices=8,
            unused_vertices_removed=3,
            uv_layers=2,
            custom_normals=True,
            effective_material=True,
            packed_texture=True,
            missing_triangle_rejected=True,
        )
    )
)

# Optional actual visual boundary, separate from the no-GPU geometry proof above.
if "visual" in sys.argv[sys.argv.index("--") + 2 :]:
    from acceptance.blender_scripts.native_render import render_images, compare
    from acceptance.native_policy import VIEWS, PASSES

    calibration = json.loads(Path(sys.argv[sys.argv.index("visual") + 1]).read_text())
    settings = calibration["settings"]

    def outputs(experiment):
        return {
            f"image.{experiment}.0.{v}.{p}": root / experiment / (v + "-" + p + ".png")
            for v in VIEWS
            for p in PASSES
        }

    full = render_images(pc.render_manifest([obj]), settings, outputs("full_source"), "full_source")
    with pc.projected_surface([obj], frozen, p) as retained:
        projected = render_images(
            pc.render_manifest(retained),
            settings,
            outputs("projection_source"),
            "projection_source",
        )
    assert full["settings"] == projected["settings"] == settings
    assert full["platform"] == projected["platform"] == calibration["platform"]
    (root / "full-source-render.json").write_text(json.dumps(full))
    (root / "projection-source-render.json").write_text(json.dumps(projected))
    differences = []
    for view in VIEWS:
        for render_pass in PASSES:
            diff = root / ("diff-" + view + "-" + render_pass + ".png")
            measured = compare(
                outputs("full_source")[f"image.full_source.0.{view}.{render_pass}"],
                outputs("projection_source")[f"image.projection_source.0.{view}.{render_pass}"],
                diff,
                1048576,
            )
            measured.update(view=view, render_pass=render_pass)
            differences.append(measured)
    assert any(row["different_pixels"] > 0 for row in differences if row["render_pass"] == "wire")
    assert all(
        row["different_pixels"] == 0 for row in differences if row["render_pass"] == "silhouette"
    )
    (root / "visual-differences.json").write_text(json.dumps(differences))
