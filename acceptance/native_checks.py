from __future__ import annotations

import math
from typing import Any

from acceptance.canonical import canonicalize

R2 = (
    "r2.inventory.coverage_complete",
    "r2.inventory.no_nan_inf",
    "r2.inventory.no_reserved_props",
    "r2.geometry.validate_clean",
    "r2.geometry.manifest_written",
    "r2.material.slots_resolved",
    "r2.dependency.all_present",
    "r2.source.digest_stable",
)


def finding(code: str, detail: str) -> dict[str, Any]:
    return {"code": code, "severity": "error", "pointer": None, "detail": detail}


def inspect_checks(manifest: dict[str, Any], digest_stable: bool) -> list[dict[str, Any]]:
    failures: dict[str, list[dict[str, Any]]] = {key: [] for key in R2}

    def fail(key: str, code: str, detail: str) -> None:
        failures[key].append(finding(code, detail))

    if manifest["scope_gaps"]:
        fail(R2[0], "capability_gap", repr(manifest["scope_gaps"]))
    if manifest["invalid_numbers"]:
        fail(R2[1], "non_finite_data", repr(manifest["invalid_numbers"]))
    if manifest["reserved_props"]:
        fail(R2[2], "reserved_property", repr(manifest["reserved_props"]))
    for name, stages in manifest["meshes"].items():
        for stage, geometry in stages.items():
            if geometry["validate_corrected"]:
                fail(R2[3], "mesh_validate_changed", name + ":" + stage)
            if not geometry["triangles_complete"]:
                fail(R2[4], "incomplete_geometry", name + ":" + stage)

    material_ids = {material["id"][1] for material in manifest["materials"]}
    for obj in manifest["objects"]:
        if obj["type"] != "MESH":
            continue
        for polygon in manifest["meshes"][obj["id"][1]]["evaluated"]["polygons"]:
            slot = polygon[2]
            name = obj["materials"][slot] if 0 <= slot < len(obj["materials"]) else None
            if name is None or name not in material_ids:
                fail(R2[5], "used_material_unresolved", repr(obj["id"]))

    dependency_ids = {dependency["id"][1] for dependency in manifest["dependencies"]}
    for material in manifest["materials"]:
        for node in material["nodes"]:
            if node["type"] == "TEX_IMAGE" and node["image"] not in dependency_ids:
                fail(R2[6], "dependency_missing", repr(node["image"]))
    for dependency in manifest["dependencies"]:
        if not dependency["packed"] or not dependency["bytes"] or not dependency["sha256"]:
            fail(R2[6], "dependency_missing", repr(dependency["id"]))
    if not digest_stable:
        fail(R2[7], "source_changed", "Source bytes changed while inspecting")
    return [{"id": key, "findings": failures[key], "metrics": {}} for key in R2]


def scene_geometry_findings(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest["scope_gaps"] or manifest["invalid_numbers"]:
        return [finding("geometry_not_verified", "Capability/finite-data gate blocked geometry")]
    problems = []
    if not manifest["occurrences"]:
        problems.append(finding("no_render_occurrence", "No supported render geometry"))
    for occurrence in manifest["occurrences"]:
        geometry = manifest["meshes"][occurrence["source"][1]]["evaluated"]
        matrix = occurrence["matrix_world"]
        if not geometry["triangles"]:
            problems.append(finding("empty_geometry", repr(occurrence["key"])))
        points = [
            [sum(matrix[i][k] * vertex[k] for k in range(3)) + matrix[i][3] for i in range(3)]
            for vertex in geometry["vertices"]
        ]
        for triangle in geometry["triangles"]:
            a, b, c = [points[geometry["loops"][index]] for index in triangle]
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            if not all(math.isfinite(item) for item in cross) or all(item == 0 for item in cross):
                problems.append(finding("degenerate_world_triangle", repr(occurrence["key"])))
                break
    return problems


def reference_findings(
    candidate: dict[str, Any], reference: dict[str, Any]
) -> list[dict[str, Any]]:
    fields = ("units", "objects", "meshes", "occurrences", "materials", "dependencies")
    return [
        finding(
            "reference_" + key + "_mismatch",
            key + " differs from independently approved reference",
        )
        for key in fields
        if canonicalize(candidate[key]) != canonicalize(reference[key])
    ]


def validate_manifest(value: Any, limits: dict[str, int]) -> None:
    def closed(item: Any, fields: set[str]) -> None:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("native manifest closed fields mismatch")

    def sequence(item: Any, *, limit: int | None = None) -> None:
        if not isinstance(item, list) or (limit is not None and len(item) > limit):
            raise ValueError("native manifest list exceeds schema/budget")

    def strict_integer(item: Any, *, nonnegative: bool = False) -> None:
        if type(item) is not int or (nonnegative and item < 0):
            raise ValueError("native manifest integer malformed")

    closed(limits, {"max_objects", "max_vertices", "max_triangles", "max_image_pixels"})
    for limit in limits.values():
        if type(limit) is not int or limit <= 0:
            raise ValueError("native manifest limit malformed")
    closed(
        value,
        {
            "schema_version",
            "support_profile",
            "scene",
            "view_layer",
            "frame",
            "units",
            "auxiliary_inventory",
            "coverage",
            "scope_gaps",
            "occurrences_complete",
            "reserved_props",
            "collections",
            "objects",
            "meshes",
            "occurrences",
            "materials",
            "dependencies",
            "invalid_numbers",
        },
    )
    if value["schema_version"] != 2 or value["support_profile"] != "native-static-v1":
        raise ValueError("native manifest version mismatch")

    sequence(value["invalid_numbers"])
    diagnosed_paths: set[tuple[str | int, ...]] = set()
    for entry in value["invalid_numbers"]:
        closed(entry, {"path", "value"})
        sequence(entry["path"])
        if not isinstance(entry["value"], str) or entry["value"] not in {
            "nan",
            "inf",
            "-inf",
        }:
            raise ValueError("invalid numeric diagnostic token")
        if any(type(segment) not in (str, int) for segment in entry["path"]):
            raise ValueError("invalid numeric diagnostic path")
        path = tuple(entry["path"])
        if path in diagnosed_paths:
            raise ValueError("duplicate invalid numeric diagnostic path")
        current = value
        try:
            for segment in path:
                if isinstance(current, dict):
                    if type(segment) is not str or segment not in current:
                        raise ValueError("invalid numeric diagnostic path")
                elif isinstance(current, list):
                    if type(segment) is not int or segment < 0 or segment >= len(current):
                        raise ValueError("invalid numeric diagnostic path")
                else:
                    raise ValueError("invalid numeric diagnostic path")
                current = current[segment]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("invalid numeric diagnostic path") from exc
        if current is not None:
            raise ValueError("invalid-number pointer must identify its null marker")
        diagnosed_paths.add(path)

    def number(item: Any, path: list[str | int]) -> None:
        if item is None:
            if tuple(path) not in diagnosed_paths:
                raise ValueError("numeric null lacks invalid-number diagnostic")
            return
        if type(item) not in (int, float):
            raise ValueError("native manifest number malformed")
        try:
            finite = math.isfinite(item)
        except OverflowError as exc:
            raise ValueError("native manifest number malformed") from exc
        if not finite:
            raise ValueError("native manifest number malformed")

    def vector(item: Any, width: int, path: list[str | int]) -> None:
        if not isinstance(item, list) or len(item) != width:
            raise ValueError("native manifest vector malformed")
        for index, component in enumerate(item):
            number(component, path + [index])

    def matrix(item: Any, path: list[str | int]) -> None:
        if not isinstance(item, list) or len(item) != 4:
            raise ValueError("matrix must have four rows")
        for index, row in enumerate(item):
            vector(row, 4, path + [index])

    def structured_id(item: Any, kind: str, width: int = 2) -> str:
        if (
            not isinstance(item, list)
            or len(item) != width
            or item[0] != kind
            or any(not isinstance(part, str) or not part for part in item)
        ):
            raise ValueError("structured native ID required")
        name = item[1]
        if not isinstance(name, str):
            raise ValueError("structured native ID required")
        return name

    if (
        type(value["frame"]) is not int
        or not isinstance(value["scene"], str)
        or not isinstance(value["view_layer"], str)
    ):
        raise ValueError("scene/layer/frame schema mismatch")
    closed(value["units"], {"system", "scale_length"})
    if not isinstance(value["units"]["system"], str):
        raise ValueError("native unit system malformed")
    number(value["units"]["scale_length"], ["units", "scale_length"])
    if value["units"]["scale_length"] is not None and value["units"]["scale_length"] <= 0:
        raise ValueError("positive native unit scale required")

    closed(value["auxiliary_inventory"], {"worlds", "cameras", "lights"})
    for names in value["auxiliary_inventory"].values():
        sequence(names)
        if any(not isinstance(name, str) for name in names):
            raise ValueError("auxiliary names must be strings")

    sequence(value["coverage"])
    for record in value["coverage"]:
        closed(record, {"type", "count", "policy"})
        if (
            not isinstance(record["type"], str)
            or type(record["count"]) is not int
            or record["count"] < 0
            or not isinstance(record["policy"], str)
            or record["policy"]
            not in {
                "ignored-ui",
                "collected",
                "unsupported",
                "inventory-only-controlled-lighting",
            }
        ):
            raise ValueError("coverage record malformed")

    sequence(value["scope_gaps"])
    if any(not isinstance(item, str) for item in value["scope_gaps"]):
        raise ValueError("capability gaps must be explicit strings")
    if type(value["occurrences_complete"]) is not bool or value["occurrences_complete"] != (
        not value["scope_gaps"]
    ):
        raise ValueError("occurrence completeness contradicts capability gaps")

    sequence(value["reserved_props"])
    if any(
        not isinstance(item, list)
        or len(item) != 3
        or any(not isinstance(part, str) for part in item)
        for item in value["reserved_props"]
    ):
        raise ValueError("reserved property record malformed")

    sequence(value["collections"])
    for record in value["collections"]:
        closed(record, {"path", "exclude", "hide_render"})
        sequence(record["path"])
        if (
            any(not isinstance(segment, str) for segment in record["path"])
            or type(record["exclude"]) is not bool
            or type(record["hide_render"]) is not bool
        ):
            raise ValueError("collection record malformed")

    sequence(value["objects"], limit=limits["max_objects"])
    object_fields = {
        "id",
        "type",
        "paths",
        "parent",
        "matrix_world",
        "hide_render",
        "hide_viewport",
        "hide_get",
        "render_included",
        "exclusion_reason",
        "modifiers",
        "custom_props",
        "materials",
    }
    object_names: set[str] = set()
    mesh_names: set[str] = set()
    for index, obj in enumerate(value["objects"]):
        closed(obj, object_fields)
        name = structured_id(obj["id"], "OBJECT")
        if name in object_names:
            raise ValueError("ambiguous object identities")
        object_names.add(name)
        if not isinstance(obj["type"], str):
            raise ValueError("object type malformed")
        if obj["type"] == "MESH":
            mesh_names.add(name)
        sequence(obj["paths"])
        if any(
            not isinstance(path, list) or any(not isinstance(segment, str) for segment in path)
            for path in obj["paths"]
        ):
            raise ValueError("collection paths must preserve segments")
        if obj["parent"] is not None:
            structured_id(obj["parent"], "OBJECT")
        matrix(obj["matrix_world"], ["objects", index, "matrix_world"])
        if any(
            type(obj[key]) is not bool
            for key in ("hide_render", "hide_viewport", "hide_get", "render_included")
        ):
            raise ValueError("visibility must be bool")
        if obj["exclusion_reason"] is not None and not isinstance(obj["exclusion_reason"], str):
            raise ValueError("exclusion reason malformed")
        sequence(obj["modifiers"])
        for modifier in obj["modifiers"]:
            closed(modifier, {"name", "type", "show_viewport", "show_render", "params"})
            if (
                not isinstance(modifier["name"], str)
                or not isinstance(modifier["type"], str)
                or type(modifier["show_viewport"]) is not bool
                or type(modifier["show_render"]) is not bool
                or not isinstance(modifier["params"], dict)
            ):
                raise ValueError("modifier record malformed")
            canonicalize(modifier["params"])
        if not isinstance(obj["custom_props"], dict):
            raise ValueError("object custom properties malformed")
        canonicalize(obj["custom_props"])
        sequence(obj["materials"])
        if any(item is not None and not isinstance(item, str) for item in obj["materials"]):
            raise ValueError("object material references malformed")
    if any(
        obj["parent"] is not None and obj["parent"][1] not in object_names
        for obj in value["objects"]
    ):
        raise ValueError("dangling object parent")

    if not isinstance(value["meshes"], dict) or any(
        not isinstance(name, str) for name in value["meshes"]
    ):
        raise ValueError("native meshes must be a mapping")
    if set(value["meshes"]) != mesh_names:
        raise ValueError("each mesh object requires authored/evaluated geometry")
    geometry_fields = {
        "vertices",
        "edges",
        "edge_seams",
        "edge_sharp",
        "loops",
        "polygons",
        "uv",
        "colors",
        "validate_corrected",
        "triangulation",
        "triangles_complete",
        "triangles",
        "corner_normals",
    }
    totals = {
        "authored": {"vertices": 0, "triangles": 0},
        "evaluated": {"vertices": 0, "triangles": 0},
    }
    for name, stages in value["meshes"].items():
        closed(stages, {"authored", "evaluated"})
        for stage in ("authored", "evaluated"):
            geometry = stages[stage]
            closed(geometry, geometry_fields)
            prefix: list[str | int] = ["meshes", name, stage]
            for field in (
                "vertices",
                "edges",
                "edge_seams",
                "edge_sharp",
                "loops",
                "polygons",
                "uv",
                "colors",
                "triangles",
                "corner_normals",
            ):
                sequence(geometry[field])
            for index, vertex in enumerate(geometry["vertices"]):
                vector(vertex, 3, prefix + ["vertices", index])
            for edge in geometry["edges"]:
                if (
                    not isinstance(edge, list)
                    or len(edge) != 2
                    or any(type(item) is not int or item < 0 for item in edge)
                ):
                    raise ValueError("mesh edge malformed")
            if len(geometry["edge_seams"]) != len(geometry["edges"]) or len(
                geometry["edge_sharp"]
            ) != len(geometry["edges"]):
                raise ValueError("mesh edge flags mismatch")
            if any(
                type(item) is not bool for item in geometry["edge_seams"] + geometry["edge_sharp"]
            ):
                raise ValueError("mesh edge flags malformed")
            if any(type(item) is not int or item < 0 for item in geometry["loops"]):
                raise ValueError("loop indices must be nonnegative integers")
            for polygon in geometry["polygons"]:
                if (
                    not isinstance(polygon, list)
                    or len(polygon) != 4
                    or any(type(polygon[item]) is not int for item in range(3))
                    or polygon[0] < 0
                    or polygon[1] < 0
                    or polygon[2] < 0
                    or type(polygon[3]) is not bool
                ):
                    raise ValueError("mesh polygon malformed")
            for uv_index, uv in enumerate(geometry["uv"]):
                closed(uv, {"name", "active_render", "values"})
                if not isinstance(uv["name"], str) or type(uv["active_render"]) is not bool:
                    raise ValueError("UV layer malformed")
                sequence(uv["values"])
                for coordinate_index, coordinate in enumerate(uv["values"]):
                    vector(coordinate, 2, prefix + ["uv", uv_index, "values", coordinate_index])
            for color_index, color in enumerate(geometry["colors"]):
                closed(color, {"name", "domain", "type", "values"})
                if any(not isinstance(color[key], str) for key in ("name", "domain", "type")):
                    raise ValueError("color attribute malformed")
                sequence(color["values"])
                for rgba_index, rgba in enumerate(color["values"]):
                    vector(rgba, 4, prefix + ["colors", color_index, "values", rgba_index])
            if (
                type(geometry["validate_corrected"]) is not bool
                or type(geometry["triangles_complete"]) is not bool
                or not isinstance(geometry["triangulation"], str)
            ):
                raise ValueError("geometry completeness malformed")
            for triangle in geometry["triangles"]:
                if (
                    not isinstance(triangle, list)
                    or len(triangle) != 3
                    or any(
                        type(loop_index) is not int
                        or loop_index < 0
                        or loop_index >= len(geometry["loops"])
                        for loop_index in triangle
                    )
                    or any(
                        geometry["loops"][loop_index] >= len(geometry["vertices"])
                        for loop_index in triangle
                    )
                ):
                    raise ValueError("invalid triangulation loop indices")
            for index, normal in enumerate(geometry["corner_normals"]):
                vector(normal, 3, prefix + ["corner_normals", index])
            if geometry["triangles_complete"]:
                if any(index >= len(geometry["vertices"]) for index in geometry["loops"]):
                    raise ValueError("complete geometry has invalid vertex indices")
                if any(
                    polygon[0] + polygon[1] > len(geometry["loops"])
                    for polygon in geometry["polygons"]
                ):
                    raise ValueError("complete geometry has invalid polygon range")
            totals[stage]["vertices"] += len(geometry["vertices"])
            totals[stage]["triangles"] += len(geometry["triangles"])
    for counts in totals.values():
        if (
            counts["vertices"] > limits["max_vertices"]
            or counts["triangles"] > limits["max_triangles"]
        ):
            raise ValueError("native geometry exceeds frozen budget")

    sequence(value["occurrences"])
    occurrence_keys: set[bytes] = set()
    for index, occurrence in enumerate(value["occurrences"]):
        closed(occurrence, {"key", "source", "instancer_chain", "geometry", "matrix_world"})
        source_name = structured_id(occurrence["source"], "OBJECT")
        sequence(occurrence["instancer_chain"])
        if occurrence["instancer_chain"]:
            raise ValueError("unsupported native instancer chain")
        if (
            not isinstance(occurrence["key"], list)
            or len(occurrence["key"]) != 2
            or occurrence["key"][0] != occurrence["source"]
            or occurrence["key"][1] != occurrence["instancer_chain"]
        ):
            raise ValueError("native occurrence key malformed")
        geometry_id = occurrence["geometry"]
        if (
            not isinstance(geometry_id, list)
            or len(geometry_id) != 3
            or geometry_id != ["MESH", source_name, "evaluated"]
            or source_name not in mesh_names
        ):
            raise ValueError("unsupported or dangling native occurrence")
        key = canonicalize(occurrence["key"])
        if key in occurrence_keys:
            raise ValueError("duplicate native occurrence key")
        occurrence_keys.add(key)
        matrix(occurrence["matrix_world"], ["occurrences", index, "matrix_world"])

    sequence(value["materials"])
    material_ids: set[str] = set()
    for material in value["materials"]:
        closed(material, {"id", "nodes", "links"})
        material_id = structured_id(material["id"], "MATERIAL")
        if material_id in material_ids:
            raise ValueError("ambiguous material identities")
        material_ids.add(material_id)
        sequence(material["nodes"])
        for node in material["nodes"]:
            if not isinstance(node, dict) or not isinstance(node.get("type"), str):
                raise ValueError("material node malformed")
            fields = {"name", "type", "inputs"}
            if node["type"] == "TEX_IMAGE":
                fields |= {"image", "interpolation", "projection", "extension"}
            closed(node, fields)
            if (
                not isinstance(node["name"], str)
                or not isinstance(node["inputs"], dict)
                or (
                    node["type"] == "TEX_IMAGE"
                    and (
                        node["image"] is not None
                        and not isinstance(node["image"], str)
                        or any(
                            not isinstance(node[key], str)
                            for key in ("interpolation", "projection", "extension")
                        )
                    )
                )
            ):
                raise ValueError("material node malformed")
            canonicalize(node["inputs"])
        sequence(material["links"])
        if any(
            not isinstance(link, list)
            or len(link) != 4
            or any(not isinstance(item, str) for item in link)
            for link in material["links"]
        ):
            raise ValueError("material link schema mismatch")

    sequence(value["dependencies"])
    dependency_ids: set[str] = set()
    for dependency in value["dependencies"]:
        closed(
            dependency,
            {
                "id",
                "source",
                "packed",
                "bytes",
                "sha256",
                "size",
                "channels",
                "is_float",
                "colorspace",
                "path",
            },
        )
        dependency_id = structured_id(dependency["id"], "IMAGE")
        if dependency_id in dependency_ids:
            raise ValueError("ambiguous image identities")
        dependency_ids.add(dependency_id)
        if (
            not isinstance(dependency["source"], str)
            or type(dependency["packed"]) is not bool
            or type(dependency["is_float"]) is not bool
            or dependency["bytes"] is not None
            and (type(dependency["bytes"]) is not int or dependency["bytes"] < 0)
            or dependency["sha256"] is not None
            and (
                not isinstance(dependency["sha256"], str)
                or len(dependency["sha256"]) != 64
                or any(character not in "0123456789abcdef" for character in dependency["sha256"])
            )
            or type(dependency["channels"]) is not int
            or dependency["channels"] < 0
            or not isinstance(dependency["colorspace"], str)
            or not isinstance(dependency["path"], str)
        ):
            raise ValueError("dependency record malformed")
        sequence(dependency["size"])
        if len(dependency["size"]) != 2:
            raise ValueError("dependency image size malformed")
        for dimension in dependency["size"]:
            strict_integer(dimension, nonnegative=True)
        if dependency["packed"]:
            width, height = dependency["size"]
            if (
                not dependency["bytes"]
                or dependency["sha256"] is None
                or width <= 0
                or height <= 0
                or width > limits["max_image_pixels"] // height
            ):
                raise ValueError("packed dependency exceeds identity/pixel budget")

    canonicalize(value)
