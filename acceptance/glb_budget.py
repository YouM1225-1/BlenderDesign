from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from acceptance.strict_json import strict_json_loads


def measure_glb(path: Path, limits: dict[str, Any]) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(limits["max_glb_bytes"] + 1)
    if len(raw) > limits["max_glb_bytes"]:
        raise ValueError("GLB byte budget exceeded")
    if len(raw) < 20 or struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("invalid GLB header/length")
    offset = 12
    chunks = []
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("short GLB chunk")
        (length, kind) = struct.unpack_from("<II", raw, offset)
        offset += 8
        if length % 4 or offset + length > len(raw):
            raise ValueError("invalid chunk boundary")
        chunks.append((kind, raw[offset : offset + length]))
        offset += length
    if (
        len(chunks) not in (1, 2)
        or chunks[0][0] != 1313821514
        or (len(chunks) == 2 and chunks[1][0] != 5130562)
    ):
        raise ValueError("one JSON and optional BIN chunk required")
    if len(chunks[0][1]) > limits["max_json_bytes"]:
        raise ValueError("GLB JSON budget exceeded")
    document = strict_json_loads(chunks[0][1])
    if (
        not isinstance(document, dict)
        or document.get("asset", {}).get("version") != "2.0"
    ):
        raise ValueError("glTF 2.0 required")
    meshes = document.get("meshes", [])
    nodes = document.get("nodes", [])
    accessors = document.get("accessors", [])
    if len(meshes) > limits["max_meshes"] or len(nodes) > limits["max_nodes"]:
        raise ValueError("GLB node/mesh budget exceeded")

    def index(items: Any, i: Any) -> Any:
        if type(i) is not int or not 0 <= i < len(items):
            raise ValueError("GLB index outside array")
        return items[i]

    mesh_counts = []
    for mesh in meshes:
        triangles = 0
        for primitive in mesh["primitives"]:
            if primitive.get("mode", 4) != 4:
                raise ValueError("triangle primitive required")
            accessor = index(
                accessors, primitive.get("indices", primitive["attributes"]["POSITION"])
            )
            count = accessor["count"]
            if type(count) is not int or count < 0 or count % 3:
                raise ValueError("triangle count malformed")
            triangles += count // 3
        mesh_counts.append((triangles, len(mesh["primitives"])))
    scenes = document.get("scenes", [])
    roots = index(scenes, document.get("scene", 0))["nodes"]
    seen = set()
    pending = list(roots)
    rendered = 0
    draws = 0
    while pending:
        n = pending.pop()
        node = index(nodes, n)
        if n in seen:
            raise ValueError("cycle or multiple-parent scene graph")
        seen.add(n)
        if "mesh" in node:
            (triangles, calls) = index(mesh_counts, node["mesh"])
            rendered += triangles
            draws += calls
        pending.extend(node.get("children", []))
    resources = document.get("buffers", []) + document.get("images", [])
    if any("uri" in r for r in resources):
        raise ValueError("self-contained GLB forbids every URI including data URI")
    result: dict[str, Any] = {
        "schema_version": 2,
        "bytes": len(raw),
        "nodes": len(nodes),
        "meshes": len(meshes),
        "stored_triangles": sum(x[0] for x in mesh_counts),
        "rendered_triangles": rendered,
        "draw_calls": draws,
        "extensions": sorted(
            set(document.get("extensionsUsed", []))
            | set(document.get("extensionsRequired", []))
        ),
        "external_resources": 0,
        "resource_pointers": [
            "/buffers/" + str(i) for i in range(len(document.get("buffers", [])))
        ]
        + ["/images/" + str(i) for i in range(len(document.get("images", [])))],
        "exceeded": [],
    }
    for field, limit in [
        ("stored_triangles", "max_stored_triangles"),
        ("rendered_triangles", "max_rendered_triangles"),
        ("draw_calls", "max_draw_calls"),
    ]:
        if result[field] > limits[limit]:
            result["exceeded"].append(field)
    return result
