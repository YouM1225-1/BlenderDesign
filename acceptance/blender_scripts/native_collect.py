"""Collect the bounded native profile inside an authorized disposable Blender process."""

from __future__ import annotations

import hashlib
import math
from typing import Any

import bpy

MODIFIERS = {
    "TRIANGULATE": ("quad_method", "ngon_method", "min_vertices", "keep_custom_normals"),
    "BEVEL": (
        "width",
        "width_pct",
        "segments",
        "affect",
        "limit_method",
        "angle_limit",
        "use_clamp_overlap",
        "offset_type",
        "profile_type",
        "profile",
        "material",
        "loop_slide",
        "mark_seam",
        "mark_sharp",
        "harden_normals",
        "face_strength_mode",
        "miter_outer",
        "miter_inner",
        "spread",
        "vmesh_method",
    ),
}
IGNORED_IDS = {"screens", "workspaces", "window_managers", "brushes", "palettes"}
SUPPORTED_IDS = {
    "objects",
    "collections",
    "scenes",
    "meshes",
    "materials",
    "images",
    "worlds",
    "cameras",
    "lights",
}


def value(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): value(x) for k, x in v.items()}
    if hasattr(v, "to_dict"):
        return value(v.to_dict())
    if v is None or isinstance(v, (str, bool, int, float)):
        return v
    return [value(x) for x in v]


def finite(v: Any) -> bool:
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, dict):
        return all(finite(x) for x in v.values())
    if isinstance(v, list):
        return all(finite(x) for x in v)
    return True


def geometry(mesh: Any, limits: dict[str, int]) -> dict[str, Any]:
    if (
        len(mesh.vertices) > limits["max_vertices"]
        or len(mesh.polygons) > limits["max_triangles"]
        or sum(max(0, p.loop_total - 2) for p in mesh.polygons) > limits["max_triangles"]
    ):
        raise ValueError("geometry exceeds bounded native collection profile")
    raw: dict[str, Any] = {
        "vertices": [list(v.co) for v in mesh.vertices],
        "edges": [list(e.vertices) for e in mesh.edges],
        "edge_seams": [e.use_seam for e in mesh.edges],
        "edge_sharp": [e.use_edge_sharp for e in mesh.edges],
        "loops": [int(x.vertex_index) for x in mesh.loops],
        "polygons": [
            [p.loop_start, p.loop_total, p.material_index, p.use_smooth] for p in mesh.polygons
        ],
        "uv": [
            {
                "name": uv.name,
                "active_render": uv.active_render,
                "values": [list(x.uv) for x in uv.data],
            }
            for uv in mesh.uv_layers
        ],
        "colors": [
            {
                "name": a.name,
                "domain": a.domain,
                "type": a.data_type,
                "values": [list(x.color) for x in a.data],
            }
            for a in mesh.color_attributes
        ],
    }
    duplicate = mesh.copy()
    try:
        corrected = bool(duplicate.validate(verbose=False, clean_customdata=True))
    finally:
        bpy.data.meshes.remove(duplicate)
    raw["validate_corrected"] = corrected
    raw["triangulation"] = "Blender Mesh.calc_loop_triangles locked build"
    raw["triangles_complete"] = not corrected and finite(raw)
    raw["triangles"] = []
    raw["corner_normals"] = []
    if raw["triangles_complete"]:
        mesh.calc_loop_triangles()
        raw["triangles"] = [list(t.loops) for t in mesh.loop_triangles]
        raw["corner_normals"] = [list(n.vector) for n in mesh.corner_normals]
    return raw


def collect(
    scene_name: str, layer_name: str, frame: int, *, limits: dict[str, int] | None = None
) -> dict[str, Any]:
    if limits is None:
        limits = {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 16777216,
        }
    gaps: list[str] = []
    if len(bpy.data.scenes) != 1 or scene_name not in bpy.data.scenes:
        raise ValueError("single named scene required")
    scene = bpy.data.scenes[scene_name]
    if len(scene.objects) > limits["max_objects"]:
        raise ValueError("object count exceeds bounded native collection profile")
    if layer_name not in scene.view_layers:
        raise ValueError("named view layer missing")
    scene.frame_set(frame)
    bpy.context.window.scene = scene
    bpy.context.window.view_layer = scene.view_layers[layer_name]
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    coverage: list[dict[str, Any]] = []
    reserved: list[list[str]] = []
    inspected: set[int] = set()
    collected: dict[str, set[int]] = {name: set() for name in ("objects", "meshes", "collections")}

    def inspect_id(block: Any, kind: str) -> None:
        identity = block.as_pointer()
        if identity in inspected:
            return
        inspected.add(identity)
        if hasattr(block, "keys"):
            for key in block.keys():
                if key.startswith(("bcx_", "acceptance_")):
                    reserved.append([kind, block.name, key])
        if getattr(block, "library", None) is not None:
            gaps.append("linked:" + kind + ":" + block.name)
        if getattr(block, "animation_data", None) is not None:
            gaps.append("animation:" + kind + ":" + block.name)
        tree = getattr(block, "node_tree", None)
        if tree is not None:
            inspect_id(tree, kind + ":" + block.name + ":node_tree")
        if isinstance(block, bpy.types.Scene):
            inspect_id(block.collection, "scenes:" + block.name + ":collection")

    for prop in bpy.data.bl_rna.properties:
        if prop.type != "COLLECTION" or prop.identifier == "all_ids":
            continue
        name = prop.identifier
        members = list(getattr(bpy.data, name))
        policy = (
            "ignored-ui"
            if name in IGNORED_IDS
            else "inventory-only-controlled-lighting"
            if name in {"worlds", "cameras", "lights"}
            else "collected"
        )
        if members and name not in IGNORED_IDS | SUPPORTED_IDS:
            policy = "unsupported"
            gaps.append("datablock:" + name)
        coverage.append({"type": name, "count": len(members), "policy": policy})
        for block in members:
            inspect_id(block, name)
    paths: dict[str, list[list[str]]] = {}
    renderable: set[str] = set()
    collections = []

    def visit(layer: Any, parent: list[str], excluded: bool) -> None:
        path = parent + [layer.collection.name]
        inspect_id(layer.collection, "collections")
        collected["collections"].add(layer.collection.as_pointer())
        if layer.holdout:
            gaps.append("layer-holdout:" + repr(path))
        if layer.indirect_only:
            gaps.append("layer-indirect-only:" + repr(path))
        blocked = excluded or layer.exclude or layer.collection.hide_render
        if layer.exclude or layer.hide_viewport or layer.collection.hide_viewport:
            gaps.append("layer-evaluation-disabled:" + repr(path))
        collections.append(
            {"path": path, "exclude": layer.exclude, "hide_render": layer.collection.hide_render}
        )
        for obj in layer.collection.objects:
            paths.setdefault(obj.name, []).append(path)
            if not blocked and not obj.hide_render:
                renderable.add(obj.name)
        for child in layer.children:
            visit(child, path, blocked)

    visit(scene.view_layers[layer_name].layer_collection, [], False)
    materials, dependencies = [], []
    for image in sorted(bpy.data.images, key=lambda x: x.name):
        if image.type == "RENDER_RESULT":
            continue
        if image.alpha_mode != "STRAIGHT":
            gaps.append("image-alpha-mode:" + image.name + ":" + image.alpha_mode)
        packed = image.packed_file
        if image.use_multiview:
            gaps.append("image-multiview:" + image.name)
        if len(image.packed_files) > 1:
            gaps.append("image-multiple-packed-files:" + image.name)
        if packed is not None:
            width, height = image.size
            if width <= 0 or height <= 0 or width > limits["max_image_pixels"] // height:
                raise ValueError("packed image exceeds bounded native pixel profile")
        if packed is None or image.source not in {"FILE", "GENERATED"}:
            gaps.append("external-image:" + image.name)
        dependencies.append(
            {
                "id": ["IMAGE", image.name],
                "source": image.source,
                "packed": packed is not None,
                "bytes": packed.size if packed else None,
                "sha256": hashlib.sha256(bytes(packed.data)).hexdigest() if packed else None,
                "size": list(image.size),
                "channels": image.channels,
                "is_float": image.is_float,
                "colorspace": image.colorspace_settings.name,
                "path": image.filepath,
            }
        )
    for mat in sorted(bpy.data.materials, key=lambda x: x.name):
        if mat.node_tree is None:
            gaps.append("material-without-principled:" + mat.name)
            continue
        for setting, supported in (
            ("use_backface_culling", False),
            ("use_backface_culling_shadow", False),
            ("surface_render_method", "DITHERED"),
            ("use_transparent_shadow", True),
            ("thickness_mode", "SPHERE"),
            ("use_thickness_from_shadow", False),
            ("use_raytrace_refraction", False),
        ):
            actual = getattr(mat, setting)
            if actual != supported:
                gaps.append(
                    "material-setting:" + mat.name + ":" + setting + ":" + str(actual)
                )
        nodes = list(mat.node_tree.nodes)
        if (
            sum(n.type == "BSDF_PRINCIPLED" for n in nodes) != 1
            or sum(n.type == "OUTPUT_MATERIAL" for n in nodes) != 1
        ):
            gaps.append("material-node-count:" + mat.name)
        record: dict[str, Any] = {"id": ["MATERIAL", mat.name], "nodes": [], "links": []}
        for node in sorted(nodes, key=lambda x: x.name):
            if node.mute:
                gaps.append("material-node-muted:" + mat.name + ":" + node.name)
            if node.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL", "TEX_IMAGE"}:
                gaps.append("material-node:" + mat.name + ":" + node.type)
            if node.type == "BSDF_PRINCIPLED" and node.distribution != "MULTI_GGX":
                gaps.append(
                    "material-node-distribution:"
                    + mat.name
                    + ":"
                    + node.name
                    + ":"
                    + node.distribution
                )
            if node.type == "OUTPUT_MATERIAL" and node.target not in {"ALL", "EEVEE"}:
                gaps.append(
                    "material-output-target:"
                    + mat.name
                    + ":"
                    + node.name
                    + ":"
                    + node.target
                )
            item = {"name": node.name, "type": node.type, "inputs": {}}
            for socket in node.inputs:
                if hasattr(socket, "default_value"):
                    item["inputs"][socket.identifier] = value(socket.default_value)
            if node.type == "TEX_IMAGE":
                if node.image is None or node.image.packed_file is None:
                    gaps.append("image-node-not-packed:" + mat.name)
                item.update(
                    {
                        "image": node.image.name if node.image else None,
                        "interpolation": node.interpolation,
                        "projection": node.projection,
                        "extension": node.extension,
                    }
                )
                if node.projection != "FLAT":
                    gaps.append("image-projection:" + mat.name)
            record["nodes"].append(item)
        for link in mat.node_tree.links:
            allowed = (
                link.from_node.type == "BSDF_PRINCIPLED"
                and link.from_socket.name == "BSDF"
                and link.to_node.type == "OUTPUT_MATERIAL"
                and link.to_socket.name == "Surface"
            ) or (
                link.from_node.type == "TEX_IMAGE"
                and link.from_socket.name == "Color"
                and link.to_node.type == "BSDF_PRINCIPLED"
                and link.to_socket.name == "Base Color"
            )
            if not allowed:
                gaps.append("material-link:" + mat.name)
            record["links"].append(
                [
                    link.from_node.name,
                    link.from_socket.identifier,
                    link.to_node.name,
                    link.to_socket.identifier,
                ]
            )
        record["links"].sort()
        materials.append(record)
    objects: list[dict[str, Any]] = []
    meshes: dict[str, Any] = {}
    occurrences: list[dict[str, Any]] = []
    totals = {stage: {"vertices": 0, "triangles": 0} for stage in ("authored", "evaluated")}

    def bounded_geometry(mesh: Any, stage: str) -> dict[str, Any]:
        # Charge each declared object record, including shared source meshes. Stages have
        # separate budgets, matching the manifest consumer; reject before retaining arrays.
        totals[stage]["vertices"] += len(mesh.vertices)
        totals[stage]["triangles"] += sum(max(0, p.loop_total - 2) for p in mesh.polygons)
        if (
            totals[stage]["vertices"] > limits["max_vertices"]
            or totals[stage]["triangles"] > limits["max_triangles"]
        ):
            raise ValueError(stage + " geometry exceeds bounded native collection profile")
        return geometry(mesh, limits)

    for obj in sorted(scene.objects, key=lambda x: x.name):
        collected["objects"].add(obj.as_pointer())
        if obj.type not in {"MESH", "EMPTY", "CAMERA", "LIGHT"}:
            gaps.append("object-type:" + obj.name + ":" + obj.type)
        if obj.hide_viewport or obj.hide_get():
            gaps.append("viewport-evaluation-disabled:" + obj.name)
        if obj.instance_type != "NONE" or obj.constraints:
            gaps.append("instancer-or-constraint:" + obj.name)
        if obj.is_holdout:
            gaps.append("object-holdout:" + obj.name)
        if obj.is_shadow_catcher:
            gaps.append("object-shadow-catcher:" + obj.name)
        modifiers = []
        for mod in obj.modifiers:
            fields = MODIFIERS.get(mod.type)
            if fields is None or not mod.show_viewport or not mod.show_render:
                gaps.append("modifier:" + obj.name + ":" + mod.type)
            if mod.type == "BEVEL" and (
                mod.limit_method not in {"NONE", "ANGLE"}
                or mod.vertex_group
                or mod.profile_type != "SUPERELLIPSE"
            ):
                gaps.append("bevel-mode:" + obj.name)
            modifiers.append(
                {
                    "name": mod.name,
                    "type": mod.type,
                    "show_viewport": mod.show_viewport,
                    "show_render": mod.show_render,
                    "params": {k: value(getattr(mod, k)) for k in fields or ()},
                }
            )
        if obj.data is not None and obj.type == "MESH":
            for attribute in obj.data.attributes:
                if not attribute.is_internal and attribute.name not in {
                    u.name for u in obj.data.uv_layers
                } | {c.name for c in obj.data.color_attributes} | {
                    "position",
                    ".edge_verts",
                    ".corner_vert",
                    ".corner_edge",
                    "sharp_face",
                    "sharp_edge",
                    "material_index",
                }:
                    gaps.append("mesh-attribute:" + obj.name + ":" + attribute.name)
        custom = {}
        for key in obj.keys():
            try:
                custom[key] = value(obj[key])
            except TypeError:
                gaps.append("custom-property:" + obj.name + ":" + key)
        record = {
            "id": ["OBJECT", obj.name],
            "type": obj.type,
            "paths": sorted(paths.get(obj.name, [])),
            "parent": ["OBJECT", obj.parent.name] if obj.parent else None,
            "matrix_world": [list(r) for r in obj.matrix_world],
            "hide_render": obj.hide_render,
            "hide_viewport": obj.hide_viewport,
            "hide_get": obj.hide_get(),
            "render_included": obj.name in renderable,
            "exclusion_reason": None if obj.name in renderable else "object-or-layer-render-policy",
            "modifiers": modifiers,
            "custom_props": custom,
            "materials": [s.material.name if s.material else None for s in obj.material_slots],
        }
        objects.append(record)
        if obj.type != "MESH":
            continue
        collected["meshes"].add(obj.data.as_pointer())
        meshes[obj.name] = {"authored": bounded_geometry(obj.data, "authored")}
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        try:
            meshes[obj.name]["evaluated"] = bounded_geometry(mesh, "evaluated")
        finally:
            evaluated.to_mesh_clear()
        if obj.name in renderable:
            occurrences.append(
                {
                    "key": [["OBJECT", obj.name], []],
                    "source": ["OBJECT", obj.name],
                    "instancer_chain": [],
                    "geometry": ["MESH", obj.name, "evaluated"],
                    "matrix_world": record["matrix_world"],
                }
            )
    for row in coverage:
        kind = row["type"]
        if kind in collected:
            missing = [
                block
                for block in getattr(bpy.data, kind)
                if block.as_pointer() not in collected[kind]
            ]
            if missing:
                row["policy"] = "unsupported"
                gaps.extend("uncollected:" + kind + ":" + block.name for block in missing)
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "support_profile": "native-static-v1",
        "scene": scene_name,
        "view_layer": layer_name,
        "frame": frame,
        "units": {
            "system": scene.unit_settings.system,
            "scale_length": scene.unit_settings.scale_length,
        },
        "auxiliary_inventory": {
            name: sorted(x.name for x in getattr(bpy.data, name))
            for name in ("worlds", "cameras", "lights")
        },
        "coverage": coverage,
        "scope_gaps": sorted(set(gaps)),
        "occurrences_complete": not gaps,
        "reserved_props": sorted(reserved),
        "collections": collections,
        "objects": objects,
        "meshes": meshes,
        "occurrences": occurrences,
        "materials": materials,
        "dependencies": dependencies,
    }
    invalid_numbers: list[dict[str, Any]] = []

    def scrub(item: Any, pointer: list[Any]) -> Any:
        if isinstance(item, float) and not math.isfinite(item):
            invalid_numbers.append({"path": pointer, "value": repr(item)})
            return None
        if isinstance(item, dict):
            return {k: scrub(v, pointer + [k]) for k, v in item.items()}
        if isinstance(item, list):
            return [scrub(v, pointer + [i]) for i, v in enumerate(item)]
        return item

    manifest = scrub(manifest, [])
    manifest["invalid_numbers"] = invalid_numbers
    return manifest
