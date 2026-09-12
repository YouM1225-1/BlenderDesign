from __future__ import annotations

import hashlib
import json
import math
import struct
from array import array
from typing import Any

import bpy


def plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if value is None or type(value) in (str, bool, int, float):
        return value
    if hasattr(value, "to_dict"):
        return {k: plain(v) for (k, v) in value.to_dict().items()}
    if hasattr(value, "to_list"):
        return [plain(v) for v in value.to_list()]
    return [plain(v) for v in value]


def material_record(material: Any, mesh: Any, max_pixels: Any) -> Any:
    if material is None or material.node_tree is None:
        raise ValueError("one explicit Principled material required")
    nodes = material.node_tree.nodes
    shaders = [n for n in nodes if n.type == "BSDF_PRINCIPLED"]
    outputs = [n for n in nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output]
    if len(shaders) != 1 or len(outputs) != 1:
        raise ValueError("one active PBR surface required")
    node = shaders[0]
    link = list(outputs[0].inputs["Surface"].links)
    if (
        len(link) != 1
        or link[0].from_node != node
        or outputs[0].inputs["Volume"].is_linked
        or outputs[0].inputs["Displacement"].is_linked
    ):
        raise ValueError("unsupported material output")
    supported = {
        "Base Color",
        "Metallic",
        "Roughness",
        "Alpha",
        "Emission Color",
        "Emission Strength",
    }
    default = bpy.data.materials.new("Evaluator PBR defaults")
    try:
        baseline = default.node_tree.nodes.get("Principled BSDF")
        defaults = {
            socket.identifier: plain(socket.default_value)
            for socket in baseline.inputs
            if hasattr(socket, "default_value")
        }
        for socket in node.inputs:
            if socket.is_linked and socket.name != "Base Color":
                raise ValueError("unsupported linked PBR socket:" + socket.name)
            if (
                socket.name not in supported
                and hasattr(socket, "default_value")
                and (plain(socket.default_value) != defaults.get(socket.identifier))
            ):
                raise ValueError("unsupported nondefault PBR socket:" + socket.name)
    finally:
        bpy.data.materials.remove(default)
    pbr = {
        "base_color": list(node.inputs["Base Color"].default_value),
        "metallic": float(node.inputs["Metallic"].default_value),
        "roughness": float(node.inputs["Roughness"].default_value),
        "alpha": float(node.inputs["Alpha"].default_value),
        "emission": [
            float(x) * float(node.inputs["Emission Strength"].default_value)
            for x in node.inputs["Emission Color"].default_value[:3]
        ],
    }
    texture = None
    if node.inputs["Base Color"].is_linked:
        links = list(node.inputs["Base Color"].links)
        if (
            len(links) != 1
            or links[0].from_node.type != "TEX_IMAGE"
            or links[0].from_socket.name != "Color"
        ):
            raise ValueError("direct base-color texture required")
        image_node = links[0].from_node
        img = image_node.image
        if (
            img is None
            or img.is_float
            or img.packed_file is None
            or (img.channels != 4)
            or (img.colorspace_settings.name != "sRGB")
        ):
            raise ValueError("packed sRGB RGBA8 texture required")
        if (
            img.size[0] * img.size[1] > max_pixels
            or len(img.packed_file.data) < 33
            or (not img.packed_file.data.startswith(b"\x89PNG\r\n\x1a\n"))
            or (img.packed_file.data[24:26] != bytes([8, 6]))
        ):
            raise ValueError("bounded RGBA8 PNG texture required")
        if (
            image_node.interpolation != "Linear"
            or image_node.extension != "REPEAT"
            or image_node.projection != "FLAT"
        ):
            raise ValueError("supported linear repeat sampler required")
        if image_node.inputs["Vector"].is_linked:
            raise ValueError("first profile uses active render UV without vector nodes")
        uv_index = next((i for (i, uv) in enumerate(mesh.uv_layers) if uv.active_render), None)
        if uv_index is None:
            raise ValueError("texture has no active render UV")
        data = array("f", [0.0]) * len(img.pixels)
        img.pixels.foreach_get(data)
        if not all(math.isfinite(x) for x in data):
            raise ValueError("finite texture pixels required")
        texture = {
            "size": list(img.size),
            "channels": img.channels,
            "colorspace": "sRGB",
            "precision": "decoded-f32-le",
            "pixels": hashlib.sha256(struct.pack("<" + str(len(data)) + "f", *data)).hexdigest(),
            "sampling": ["Linear", "REPEAT"],
            "uv_index": uv_index,
        }
        pbr["base_color"] = None
    return {
        "pbr": pbr,
        "texture": texture,
        "double_sided": not material.use_backface_culling,
    }


def capture(objects: Any, policy: Any, *, imported: Any = False) -> Any:
    if bpy.context.scene.unit_settings.scale_length != 1:
        raise ValueError("metre scale required")
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    records = []
    total = 0
    for obj in sorted(objects, key=lambda x: x.name):
        if obj.type != "MESH" or obj.matrix_world.to_3x3().determinant() <= 0:
            raise ValueError("non-mirrored static mesh required")
        identity = json.loads(obj["bcx_uid"]) if imported else ["OBJECT", obj.name]
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        try:
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
            if total > policy["limits"]["max_projection_triangles"]:
                raise ValueError("bounded projection triangle count exceeded")
            matrix = obj.matrix_world.to_3x3().inverted().transposed()
            triangles = []
            materials = {}
            for tri in mesh.loop_triangles:
                if tri.material_index not in materials:
                    material = (
                        evaluated.material_slots[tri.material_index].material
                        if tri.material_index < len(evaluated.material_slots)
                        else None
                    )
                    materials[tri.material_index] = material_record(
                        material, mesh, policy["limits"]["max_texture_pixels"]
                    )
                corners = []
                for loop_id in tri.loops:
                    point = obj.matrix_world @ mesh.vertices[mesh.loops[loop_id].vertex_index].co
                    normal = (matrix @ mesh.corner_normals[loop_id].vector).normalized()
                    corners.append(
                        {
                            "position": list(point),
                            "normal": list(normal),
                            "uv": [list(uv.data[loop_id].uv) for uv in mesh.uv_layers],
                        }
                    )
                triangles.append({"corners": corners, "material": materials[tri.material_index]})
            records.append(
                {
                    "id": identity,
                    "matrix": [list(row) for row in obj.matrix_world],
                    "vertices": len(mesh.vertices),
                    "slots": len(evaluated.material_slots),
                    "custom": {k: plain(obj[k]) for k in obj.keys() if k != "bcx_uid"},
                    "triangles": triangles,
                }
            )
        finally:
            evaluated.to_mesh_clear()
    return {"schema_version": 2, "objects": records, "scale_length": 1}


def render_manifest(objects: Any) -> Any:
    return {
        "scope_gaps": [],
        "occurrences": [
            {
                "source": ["OBJECT", o.name],
                "matrix_world": [list(row) for row in o.matrix_world],
            }
            for o in objects
        ],
    }
