# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
"""Real Blender regressions: -- <new external output directory> <frozen good.blend>."""

import copy
import json
import runpy
import struct
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.blender_scripts import native_render as nr
from acceptance.blender_scripts.native_collect import collect


def rejected(call, error=ValueError):
    try:
        call()
    except error:
        return
    raise AssertionError("expected rejection")


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(path, rgba, level=6, width=2, height=2, depth=8, color=6, interlace=0):
    header = struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, interlace)
    rows = b"".join(b"\0" + bytes(rgba[y * 8 : (y + 1) * 8]) for y in range(2))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows, level))
        + chunk(b"IEND", b"")
    )


def loader_proxy(loader):
    # The real RNA method cannot be patched; forward removal to actual Blender.
    return SimpleNamespace(
        data=SimpleNamespace(images=SimpleNamespace(load=loader, remove=bpy.data.images.remove))
    )


def png_regressions(root):
    original_scenes = {x.as_pointer() for x in bpy.data.scenes}
    original_images = {x.as_pointer() for x in bpy.data.images}
    original_context = (bpy.context.scene, bpy.context.view_layer)
    a = [10, 20, 30, 255] * 4
    png(root / "a.png", a)
    png(root / "b.png", a, 0)
    b = a.copy()
    b[0] += 1
    png(root / "rgb.png", b)
    b = a.copy()
    b[3] = 128
    png(root / "alpha.png", b)
    records = []
    for name, channels in [("a", 0), ("b", 0), ("rgb", 1), ("alpha", 1)]:
        diff = root / f"diff-{name}.png"
        rec = nr.compare(root / "a.png", root / f"{name}.png", diff, 4)
        assert rec["different_channels"] == channels and rec["different_pixels"] == channels
        assert rec["size"] == [2, 2]
        assert (rec["max_abs"] > 0) == bool(channels)
        assert struct.unpack(">IIBBBBB", diff.read_bytes()[16:29]) == (2, 2, 8, 6, 0, 0, 0)
        assert nr.decode(diff, 4)[0] == (2, 2)
        records.append(rec)
    assert records[1]["left_bytes_sha256"] != records[1]["right_bytes_sha256"]
    assert records[3]["left_rgb_energy"] == records[3]["right_rgb_energy"]
    rejected(lambda: nr.decode(root / "a.png", 3))
    malformed = {
        "oversize": {"width": 3},
        "zero": {"width": 0},
        "rgb-format": {"color": 2},
        "depth": {"depth": 16},
        "interlace": {"interlace": 1},
    }
    for name, settings in malformed.items():
        png(root / f"{name}.png", a, **settings)
    (root / "bad.png").write_bytes(b"not png")
    bad_length = bytearray((root / "a.png").read_bytes())
    bad_length[11] = 12
    (root / "ihdr-length.png").write_bytes(bad_length)
    # Invalid metadata must be rejected before the Blender decoder is called.
    with patch.object(nr, "bpy", loader_proxy(Mock(side_effect=AssertionError("loader reached")))):
        for name in [*malformed, "bad", "ihdr-length"]:
            rejected(lambda: nr.decode(root / f"{name}.png", 4))
    real_load = bpy.data.images.load

    def wrong_size(*args, **kwargs):
        image = real_load(*args, **kwargs)
        image.scale(1, 1)
        return image

    with patch.object(nr, "bpy", loader_proxy(wrong_size)):
        rejected(lambda: nr.decode(root / "a.png", 4))
    # Saving fails after temporary image/scene allocation; neither may leak.
    rejected(
        lambda: nr.compare(root / "a.png", root / "a.png", root / "a.png" / "diff.png", 4),
        RuntimeError,
    )
    rejected(
        lambda: nr.compare(root / "a.png", root / "a.png", root / "a.png", 4),
        FileExistsError,
    )
    assert original_scenes == {x.as_pointer() for x in bpy.data.scenes}
    assert original_images == {x.as_pointer() for x in bpy.data.images}
    assert original_context == (bpy.context.scene, bpy.context.view_layer)
    return records


def probe_regressions():
    validate = runpy.run_path(str(Path(__file__).with_name("native_visual_probe.py")))[
        "validate_comparisons"
    ]
    valid = [
        dict(
            group=g,
            view=v,
            render_pass=p,
            size=[1024, 1024],
            different_pixels=0,
            left_rgb_energy=1,
            right_rgb_energy=1,
        )
        for g in ["same", "fresh"]
        for v in nr.VIEWS
        for p in nr.PASSES
        if not (g == "same" and p == "beauty")
    ]
    validate(valid)
    for mode in ["single", "same", "membership", "size"]:
        bad = copy.deepcopy(valid)
        if mode == "single":
            bad[0]["left_rgb_energy"] = 0
        elif mode == "same":
            for record in bad:
                if record["group"] == "same":
                    record["left_rgb_energy"] = record["right_rgb_energy"] = 0
        elif mode == "membership":
            bad[-1] = bad[0]
        else:
            bad[0]["size"] = [512, 512]
        rejected(lambda: validate(bad), AssertionError)


def node_values(tree):
    return [
        (
            n.type,
            [
                (
                    i.name,
                    list(i.default_value)
                    if hasattr(i.default_value, "__len__")
                    else i.default_value,
                )
                for i in n.inputs
                if hasattr(i, "default_value")
            ],
        )
        for n in tree.nodes
    ]


def preservation_regressions(root, good_blend):
    bpy.ops.wm.open_mainfile(filepath=str(good_blend), load_ui=False, use_scripts=False)
    obj = next(x for x in bpy.context.scene.objects if x.type == "MESH")
    obj.data.materials.clear()
    for name in ["mesh-first", None, "last"]:
        obj.data.materials.append(bpy.data.materials.new(name) if name else None)
    obj.material_slots[0].link = "OBJECT"
    obj.material_slots[0].material = bpy.data.materials.new("override")
    for face in obj.data.polygons:
        face.material_index = 2 if face.index % 2 else 0
    bpy.context.scene.world = bpy.data.worlds.new("Preserved source world")
    bpy.ops.wm.save_as_mainfile(filepath=str(root / "materials.blend"))
    bpy.ops.wm.open_mainfile(
        filepath=str(root / "materials.blend"), load_ui=False, use_scripts=False
    )
    manifest = collect("Scene", "ViewLayer", 1)
    assert not manifest["scope_gaps"], manifest["scope_gaps"]
    source_scene = bpy.context.scene
    source_layer = source_scene.view_layers.new("Restore me")
    bpy.context.window.view_layer = source_layer
    collections = [
        "scenes",
        "worlds",
        "objects",
        "meshes",
        "curves",
        "lights",
        "cameras",
        "materials",
    ]

    def snapshot():
        return {
            "ids": {k: sorted(x.as_pointer() for x in getattr(bpy.data, k)) for k in collections},
            "scene": bpy.context.scene.as_pointer(),
            "layer": bpy.context.view_layer.as_pointer(),
            "objects": [
                (
                    o.as_pointer(),
                    list(map(list, o.matrix_world)),
                    [
                        (s.link, s.material.as_pointer() if s.material else None)
                        for s in o.material_slots
                    ],
                    [(v.index, list(v.co)) for v in o.data.vertices],
                    [p.material_index for p in o.data.polygons],
                )
                for o in source_scene.objects
                if o.type == "MESH"
            ],
            "materials": [
                (m.as_pointer(), list(m.diffuse_color), node_values(m.node_tree))
                for m in bpy.data.materials
            ],
            "world": node_values(source_scene.world.node_tree),
            "render": (
                source_scene.render.engine,
                source_scene.render.filepath,
                source_scene.render.resolution_x,
                source_scene.render.resolution_y,
            ),
        }

    before = snapshot()
    with nr.diagnostic_scene(manifest, 0.003) as scene:
        meshes = [o for o in scene.objects if o.type == "MESH"]
        for clone, occurrence in zip(meshes, manifest["occurrences"], strict=True):
            src = source_scene.objects[occurrence["source"][1]]
            ev = src.evaluated_get(bpy.context.evaluated_depsgraph_get())
            assert [m.as_pointer() if m else None for m in clone.data.materials] == [
                s.material.as_pointer() if s.material else None for s in ev.material_slots
            ]
            assert [p.material_index for p in clone.data.polygons] == [
                p.material_index for p in ev.data.polygons
            ]
    assert snapshot() == before
    broken = copy.deepcopy(manifest)
    broken["occurrences"].append(copy.deepcopy(broken["occurrences"][0]))
    broken["occurrences"][-1]["source"][1] = "Missing source after first clone"
    rejected(lambda: nr.render_images(broken, {"reference_radius": 2}, {}, "fresh_a"), KeyError)
    assert snapshot() == before
    settings = {
        "resolution": 1024,
        "views": ["front"],
        "reference_center": [0, 0, 0],
        "reference_radius": 2,
    }
    for call in ["first", "second", "failure"]:
        outputs = {f"image.fresh_a.0.front.{p}": root / f"{call}-{p}.png" for p in nr.PASSES}
        if call == "failure":
            outputs["image.fresh_a.0.front.clay"].write_bytes(b"occupied")
        try:
            result = nr.render_images(manifest, settings, outputs, "fresh_a")
            assert call != "failure"
            assert len(result["images"]) == 4
        except FileExistsError:
            assert call == "failure" and outputs["image.fresh_a.0.front.beauty"].exists()
            assert outputs["image.fresh_a.0.front.clay"].read_bytes() == b"occupied"
        assert snapshot() == before


def main():
    args = sys.argv[sys.argv.index("--") + 1 :]
    root, good_blend = map(Path, args)
    root.mkdir()
    records = png_regressions(root)
    probe_regressions()
    preservation_regressions(root, good_blend)
    (root / "result.json").write_text(
        json.dumps(
            {
                "png": records,
                "source_preservation": True,
                "partial_construction_cleanup": True,
                "post_render_failure_cleanup": True,
                "repeated_calls": 2,
                "platform": nr.platform_key(),
            },
            allow_nan=False,
        )
    )
    print("TASK4_REAL_REGRESSIONS_OK")


if __name__ == "__main__":
    main()
