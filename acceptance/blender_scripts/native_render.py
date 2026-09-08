from __future__ import annotations
from array import array
from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import os
import platform
import math
import struct
from pathlib import Path
from typing import Any
import bpy
import gpu  # type: ignore[import-not-found]
from mathutils import Vector, Matrix  # type: ignore[import-not-found]

VIEWS = {
    "front": ("ORTHO", (0, -1, 0)),
    "back": ("ORTHO", (0, 1, 0)),
    "left": ("ORTHO", (-1, 0, 0)),
    "right": ("ORTHO", (1, 0, 0)),
    "top": ("ORTHO", (0, 0, 1)),
    "bottom": ("ORTHO", (0, 0, -1)),
    "persp": ("PERSP", (1, -1, 0.8)),
    "obliqueA": ("PERSP", (1, -1, 0.6)),
    "obliqueB": ("PERSP", (-1, -1, 0.35)),
}
PASSES = ("beauty", "clay", "silhouette", "wire")


def platform_key() -> dict[str, str]:
    return {
        "blender": bpy.app.version_string,
        "build": bpy.app.build_hash.decode(),
        "os": platform.system(),
        "arch": platform.machine(),
        "backend": gpu.platform.backend_type_get(),
        "vendor": gpu.platform.vendor_get(),
        "gpu": gpu.platform.renderer_get(),
        "engines": "BLENDER_EEVEE,BLENDER_WORKBENCH",
        "view_transform": "Standard",
        "look": "None",
        "format": "PNG_RGBA8",
        "comparator": "blender-rgba-f32-v1",
    }


@contextmanager
def diagnostic_scene(manifest: dict[str, Any], wire_radius: float) -> Iterator[Any]:
    """Own only this call's diagnostics, including partially constructed data."""
    window = bpy.context.window
    previous_scene, previous_layer = window.scene, window.view_layer
    owned = []

    def own(collection: Any, block: Any) -> Any:
        owned.append((collection, block))
        return block

    try:
        source = bpy.data.scenes[manifest["scene"]]
        window.scene = source
        window.view_layer = source.view_layers[manifest["view_layer"]]
        dg = bpy.context.evaluated_depsgraph_get()
        scene = own(bpy.data.scenes, bpy.data.scenes.new("Evaluator controlled diagnostics"))
        scene.world = own(bpy.data.worlds, bpy.data.worlds.new("Evaluator world"))
        scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (
            0.05,
            0.05,
            0.05,
            1,
        )
        scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1
        for occurrence in manifest["occurrences"]:
            original = source.objects[occurrence["source"][1]]
            evaluated = original.evaluated_get(dg)
            mesh = own(
                bpy.data.meshes,
                bpy.data.meshes.new_from_object(
                    evaluated, preserve_all_data_layers=True, depsgraph=dg
                ),
            )
            face_indices = [face.material_index for face in mesh.polygons]
            mesh.materials.clear()
            for slot in evaluated.material_slots:
                mesh.materials.append(slot.material)
            for face, index in zip(mesh.polygons, face_indices, strict=True):
                face.material_index = index
            obj = own(bpy.data.objects, bpy.data.objects.new(original.name, mesh))
            scene.collection.objects.link(obj)
            obj.matrix_world = Matrix(occurrence["matrix_world"])
            curve = own(
                bpy.data.curves, bpy.data.curves.new(original.name + " evaluator edges", "CURVE")
            )
            curve.dimensions = "3D"
            curve.resolution_u = 1
            curve.bevel_depth = wire_radius
            curve.bevel_resolution = 0
            curve.fill_mode = "FULL"
            for edge in mesh.edges:
                spline = curve.splines.new("POLY")
                spline.points.add(1)
                for point, vertex_index in zip(spline.points, edge.vertices, strict=True):
                    co = obj.matrix_world @ mesh.vertices[vertex_index].co
                    point.co = (*co, 1.0)
            wire = own(
                bpy.data.objects, bpy.data.objects.new(original.name + " evaluator wire", curve)
            )
            scene.collection.objects.link(wire)
            wire.hide_render = True
        for name, direction, energy in [
            ("key", (1, -1, -1), 3),
            ("fill", (-1, -0.5, -0.3), 1),
            ("rim", (0, 1, -0.5), 1.5),
        ]:
            light = own(bpy.data.lights, bpy.data.lights.new(name, "SUN"))
            light.energy = energy
            obj = own(bpy.data.objects, bpy.data.objects.new(name, light))
            scene.collection.objects.link(obj)
            obj.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
        cam = own(
            bpy.data.objects,
            bpy.data.objects.new(
                "Evaluator camera", own(bpy.data.cameras, bpy.data.cameras.new("Evaluator camera"))
            ),
        )
        scene.collection.objects.link(cam)
        scene.camera = cam
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "8"
        scene.render.resolution_percentage = 100
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
        scene.render.film_transparent = False
        scene.render.use_file_extension = True
        scene.render.use_stamp = False
        scene.render.use_compositing = False
        scene.render.use_sequencer = False
        yield scene
    finally:
        window.scene = previous_scene
        window.view_layer = previous_layer
        for collection, block in reversed(owned):
            collection.remove(block, do_unlink=True)


def render_images(
    manifest: dict[str, Any], settings: dict[str, Any], outputs: dict[str, Path], experiment: str
) -> dict[str, Any]:
    if manifest["scope_gaps"]:
        raise ValueError("unsupported asset must not enter renderer")
    with diagnostic_scene(manifest, settings["reference_radius"] * 0.0015) as scene:
        bpy.context.window.scene = scene
        scene.render.resolution_x = settings["resolution"]
        scene.render.resolution_y = settings["resolution"]
        center = Vector(settings["reference_center"])
        radius = settings["reference_radius"]
        records = []
        for repetition in range(2 if experiment == "same_process" else 1):
            for view in settings["views"]:
                projection, offset = VIEWS[view]
                direction = Vector(offset).normalized()
                scene.camera.data.type = projection
                scene.camera.data.lens = 50
                scene.camera.data.sensor_width = 36
                scene.camera.data.ortho_scale = 2.2 * radius
                scene.camera.data.clip_start = (0.1 if projection == "ORTHO" else 0.05) * radius
                scene.camera.data.clip_end = 10 * radius
                scene.camera.location = (
                    center + direction * (4 if projection == "ORTHO" else 3.25) * radius
                )
                scene.camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
                for render_pass in PASSES:
                    if repetition == 1 and render_pass == "beauty":
                        continue
                    shading = scene.display.shading
                    shading.type = "SOLID"
                    shading.light = "STUDIO" if render_pass == "clay" else "FLAT"
                    shading.color_type = "SINGLE"
                    shading.single_color = (0.8, 0.8, 0.8) if render_pass == "clay" else (1, 1, 1)
                    shading.show_shadows = False
                    shading.show_cavity = False
                    shading.show_specular_highlight = False
                    shading.background_type = "VIEWPORT"
                    shading.background_color = (0, 0, 0)
                    for obj in scene.objects:
                        if obj.type == "MESH":
                            obj.display_type = "SOLID"
                            obj.hide_render = render_pass == "wire"
                        elif obj.type == "CURVE":
                            obj.hide_render = render_pass != "wire"
                    scene.render.engine = (
                        "BLENDER_EEVEE" if render_pass == "beauty" else "BLENDER_WORKBENCH"
                    )
                    scene.display.render_aa = "8"
                    scene.eevee.taa_render_samples = 64
                    fid = f"image.{experiment}.{repetition}.{view}.{render_pass}"
                    path = outputs[fid]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if path.exists():
                        raise FileExistsError(path)
                    scene.render.filepath = str(path)
                    bpy.ops.render.render(write_still=True, scene=scene.name)
                    records.append(
                        {
                            "id": fid,
                            "view": view,
                            "pass": render_pass,
                            "repetition": repetition,
                            "pid": os.getpid(),
                            "experiment": experiment,
                            "engine": scene.render.engine,
                        }
                    )
        return {
            "schema_version": 2,
            "platform": platform_key(),
            "settings": settings,
            "images": records,
        }


def png_size(path: Path, max_pixels: int) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(33)
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[8:16] != b"\0\0\0\rIHDR":
        raise ValueError("locked decoder accepts PNG only")
    width, height, depth, color, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header[16:29]
    )
    if (
        width <= 0
        or height <= 0
        or width * height > max_pixels
        or (depth, color, compression, filter_method, interlace) != (8, 6, 0, 0, 0)
    ):
        raise ValueError("bounded noninterlaced RGBA8 PNG required")
    return width, height


def decode(path: Path, max_pixels: int) -> tuple[tuple[int, int], array[float]]:
    expected = png_size(path, max_pixels)
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        w, h = image.size
        if (w, h) != expected or w * h > max_pixels or image.channels != 4:
            raise ValueError("RGBA image dimensions/channels outside frozen budget")
        pixels = array("f", [0.0]) * (w * h * 4)
        image.pixels.foreach_get(pixels)
        # Float32 values and bounded pixel counts cannot overflow a float64 sum.
        if not math.isfinite(sum(pixels)):
            raise ValueError("non-finite decoded image")
        return (w, h), pixels
    finally:
        bpy.data.images.remove(image)


def compare(left: Path, right: Path, diff: Path, max_pixels: int) -> dict[str, Any]:
    if diff.exists():
        raise FileExistsError(diff)
    ls, lp = decode(left, max_pixels)
    rs, rp = decode(right, max_pixels)
    if ls != rs:
        raise ValueError("image dimension mismatch")
    if lp == rp:
        changed_channels = changed_pixels = 0
        maximum = 0.0
        delta = array("f", [0.0, 0.0, 0.0, 1.0]) * (ls[0] * ls[1])
    else:
        delta = array("f", (abs(a - b) for a, b in zip(lp, rp, strict=True)))
        changed_channels = sum(v != 0 for v in delta)
        changed_pixels = sum(any(delta[i : i + 4]) for i in range(0, len(delta), 4))
        maximum = max(delta)
        for i in range(3, len(delta), 4):
            delta[i] = 1.0
    difference = bpy.data.images.new(
        "Evaluator diff", width=ls[0], height=ls[1], alpha=True, float_buffer=True
    )
    output_scene = None
    try:
        output_scene = bpy.data.scenes.new("Evaluator diff output")
        output_scene.render.image_settings.file_format = "PNG"
        output_scene.render.image_settings.color_mode = "RGBA"
        output_scene.render.image_settings.color_depth = "8"
        output_scene.view_settings.view_transform = "Standard"
        output_scene.view_settings.look = "None"
        output_scene.view_settings.exposure = 0
        output_scene.view_settings.gamma = 1
        difference.pixels.foreach_set(delta)
        difference.save_render(str(diff), scene=output_scene)
        if decode(diff, max_pixels)[0] != ls:
            raise ValueError("difference image dimension mismatch")
    finally:
        bpy.data.images.remove(difference)
        if output_scene is not None:
            bpy.data.scenes.remove(output_scene)
    return {
        "decoder": "blender-rgba-f32-v1",
        "size": list(ls),
        "channels": 4,
        "precision": "float32",
        "color_interpretation": "Blender PNG decode, Standard output",
        "left_bytes_sha256": hashlib.sha256(left.read_bytes()).hexdigest(),
        "right_bytes_sha256": hashlib.sha256(right.read_bytes()).hexdigest(),
        "different_channels": changed_channels,
        "different_pixels": changed_pixels,
        "max_abs": maximum,
        "left_rgb_energy": sum(lp) - sum(lp[3::4]),
        "right_rgb_energy": sum(rp) - sum(rp[3::4]),
    }
