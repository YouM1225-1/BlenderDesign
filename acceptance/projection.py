from __future__ import annotations

import json
import math
from fractions import Fraction
from typing import Any, cast

from acceptance.canonical import canonicalize


def _finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(cast(int | float, value))
    except OverflowError:
        return False


def _face_direction(triangle: Any) -> list[Fraction]:
    # Exact binary rationals retain orientation without overflow, underflow, or
    # an area epsilon. Compute once per face, before the bounded pair search.
    points = [[Fraction(v) for v in c["position"]] for c in triangle["corners"]]
    u = [b - a for a, b in zip(points[0], points[1])]
    v = [b - a for a, b in zip(points[0], points[2])]
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]


def exact(a: Any, b: Any) -> Any:
    return type(a) is type(b) and (
        a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
        if isinstance(a, dict)
        else len(a) == len(b) and all(exact(x, y) for (x, y) in zip(a, b))
        if isinstance(a, list)
        else a == b
    )


def validate_projection(value: object, max_triangles: int) -> None:

    def fields(item: Any, keys: Any) -> Any:
        if not isinstance(item, dict) or set(item) != set(keys.split()):
            raise ValueError("closed projection fields mismatch")

    def vector(item: Any, n: Any) -> Any:
        if not isinstance(item, list) or len(item) != n or any(not _finite_number(x) for x in item):
            raise ValueError("finite projection vector required")

    def finite_json(item: Any, depth: Any = 0) -> Any:
        if depth > 16:
            raise ValueError("custom property depth exceeded")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if isinstance(item, list):
            for child in item:
                finite_json(child, depth + 1)
            return
        if isinstance(item, dict) and all(isinstance(k, str) for k in item):
            for child in item.values():
                finite_json(child, depth + 1)
            return
        raise ValueError("unsupported projection JSON value")

    fields(value, "schema_version objects scale_length")
    assert isinstance(value, dict)
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 2
        or not _finite_number(value["scale_length"])
        or value["scale_length"] != 1
    ):
        raise ValueError("schema2 metre-scale projection required")
    if not isinstance(value["objects"], list) or not value["objects"]:
        raise ValueError("empty projection")
    total = 0
    for obj in value["objects"]:
        fields(obj, "id matrix vertices slots custom triangles")
        if (
            not isinstance(obj["id"], list)
            or len(obj["id"]) != 2
            or obj["id"][0] != "OBJECT"
            or (not isinstance(obj["id"][1], str))
            or (not obj["id"][1])
        ):
            raise ValueError("structured object identity required")
        if not isinstance(obj["matrix"], list) or len(obj["matrix"]) != 4:
            raise ValueError("4x4 matrix required")
        for row in obj["matrix"]:
            vector(row, 4)
        for key in ("vertices", "slots"):
            if type(obj[key]) is not int or obj[key] < 0:
                raise ValueError("nonnegative count required")
        if not isinstance(obj["custom"], dict):
            raise ValueError("custom mapping required")
        finite_json(obj["custom"])
        canonicalize(obj["custom"])
        if not isinstance(obj["triangles"], list) or not obj["triangles"]:
            raise ValueError("nonempty triangle surface required")
        total += len(obj["triangles"])
        if total > max_triangles:
            raise ValueError("bounded triangle profile exceeded")
        for tri in obj["triangles"]:
            fields(tri, "corners material")
            if not isinstance(tri["corners"], list) or len(tri["corners"]) != 3:
                raise ValueError("three corners required")
            for corner in tri["corners"]:
                fields(corner, "position normal uv")
                vector(corner["position"], 3)
                vector(corner["normal"], 3)
                if not isinstance(corner["uv"], list):
                    raise ValueError("UV list required")
                for uv in corner["uv"]:
                    vector(uv, 2)
            material = tri["material"]
            fields(material, "pbr texture double_sided")
            if type(material["double_sided"]) is not bool:
                raise ValueError("boolean side policy required")
            pbr = material["pbr"]
            fields(pbr, "base_color metallic roughness alpha emission")
            if pbr["base_color"] is not None:
                vector(pbr["base_color"], 4)
            vector(pbr["emission"], 3)
            for key in ("metallic", "roughness", "alpha"):
                if not _finite_number(pbr[key]) or (not 0 <= pbr[key] <= 1):
                    raise ValueError("bounded PBR scalar required")
            texture = material["texture"]
            if texture is not None:
                fields(
                    texture,
                    "size channels colorspace precision pixels sampling uv_index",
                )
                if (
                    not isinstance(texture["size"], list)
                    or len(texture["size"]) != 2
                    or any(type(n) is not int or n <= 0 for n in texture["size"])
                ):
                    raise ValueError("positive image size required")
                if (
                    type(texture["channels"]) is not int
                    or texture["channels"] != 4
                    or texture["colorspace"] != "sRGB"
                    or texture["precision"] != "decoded-f32-le"
                ):
                    raise ValueError("supported texture representation required")
                if (
                    not isinstance(texture["pixels"], str)
                    or len(texture["pixels"]) != 64
                    or any(c not in "0123456789abcdef" for c in texture["pixels"])
                ):
                    raise ValueError("decoded texture digest required")
                if (
                    texture["sampling"] != ["Linear", "REPEAT"]
                    or type(texture["uv_index"]) is not int
                    or texture["uv_index"] < 0
                ):
                    raise ValueError("supported sampler/UV binding required")
                if any(texture["uv_index"] >= len(c["uv"]) for c in tri["corners"]):
                    raise ValueError("texture UV binding missing")
            if (pbr["base_color"] is None) != (texture is not None):
                raise ValueError("active base color representation mismatch")


def compare_projection(
    source: dict[str, Any], imported: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    cap = policy["limits"]["max_projection_triangles"]
    validate_projection(source, cap)
    validate_projection(imported, cap)
    report: dict[str, Any] = {
        "schema_version": 2,
        "preserved": [],
        "transformed": [],
        "loss": [],
        "ambiguous": [],
        "matches": [],
        "comparisons": 0,
    }

    def near(a: Any, b: Any, kind: Any) -> Any:
        if type(a) not in (int, float) or type(b) not in (int, float):
            return False
        t = policy["tolerances"][kind]
        scale = policy["reference_scale"] if kind == "geometry" else 1.0
        return abs(a - b) <= t["abs"] + t["rel"] * scale

    def sequence(a: Any, b: Any, kind: Any) -> Any:
        return len(a) == len(b) and all(
            sequence(x, y, kind)
            if isinstance(x, list) and isinstance(y, list)
            else near(x, y, kind)
            for (x, y) in zip(a, b)
        )

    def material(a: Any, b: Any) -> Any:
        if a["double_sided"] != b["double_sided"] or not exact(a["texture"], b["texture"]):
            return False
        (x, y) = (a["pbr"], b["pbr"])
        if (x["base_color"] is None) != (y["base_color"] is None):
            return False
        if x["base_color"] is not None and (
            not sequence(x["base_color"], y["base_color"], "material")
        ):
            return False
        return sequence(x["emission"], y["emission"], "material") and all(
            near(x[k], y[k], "material") for k in ("metallic", "roughness", "alpha")
        )

    def corners(a: Any, b: Any) -> Any:
        return all(
            sequence(x["position"], y["position"], "geometry")
            and sequence(x["normal"], y["normal"], "normal")
            and sequence(x["uv"], y["uv"], "uv")
            for (x, y) in zip(a, b)
        )

    def indexed(data: Any) -> Any:
        return {
            json.dumps(o["id"], ensure_ascii=False, separators=(",", ":")): o
            for o in data["objects"]
        }

    (left, right) = (indexed(source), indexed(imported))
    if len(left) != len(source["objects"]) or len(right) != len(imported["objects"]):
        report["ambiguous"].append("duplicate occurrence identity")
        return report
    if left.keys() != right.keys():
        report["preserved"].append("p01/p09 occurrence set differs")
    for key in sorted(left.keys() & right.keys()):
        (a, b) = (left[key], right[key])
        if not exact(a["custom"], b["custom"]):
            report["preserved"].append(key + ":p12 custom properties differ")
        if not sequence(a["matrix"], b["matrix"], "geometry"):
            report["transformed"].append(key + ":p13 world matrix differs")
        (aa, bb) = (a["triangles"], b["triangles"])

        def bounds(triangles: Any) -> Any:
            points = [c["position"] for t in triangles for c in t["corners"]]
            return [[op(p[i] for p in points) for i in range(3)] for op in (min, max)]

        if not sequence(bounds(aa), bounds(bb), "geometry"):
            report["transformed"].append(key + ":p03 surface bounds differ")
        if len(aa) != len(bb):
            report["transformed"].append(key + ":p02 triangle count differs")
            continue
        directions_a = [_face_direction(tri) for tri in aa]
        directions_b = [_face_direction(tri) for tri in bb]
        adjacency = []
        for i, tri in enumerate(aa):
            candidates = []
            for j, other in enumerate(bb):
                report["comparisons"] += 1
                if report["comparisons"] > policy["limits"]["max_matches"]:
                    raise ValueError("surface matching budget exceeded")
                if (
                    material(tri["material"], other["material"])
                    and any(
                        corners(tri["corners"], other["corners"][s:] + other["corners"][:s])
                        for s in range(3)
                    )
                    and sum(x * y for x, y in zip(directions_a[i], directions_b[j])) > 0
                ):
                    candidates.append(j)
            adjacency.append(candidates)
        owner: dict[int, int] = {}
        matched = True
        for start in range(len(aa)):
            queue = [start]
            seen = {start}
            predecessor = {}
            target = None
            for s in queue:
                for t in adjacency[s]:
                    if t in predecessor:
                        continue
                    predecessor[t] = s
                    if t not in owner:
                        target = t
                        break
                    if owner[t] not in seen:
                        seen.add(owner[t])
                        queue.append(owner[t])
                if target is not None:
                    break
            if target is None:
                matched = False
                break
            while target is not None:
                s = predecessor[target]
                old = next((t for (t, old_s) in owner.items() if old_s == s), None)
                owner[target] = s
                target = old
        if not matched:
            report["transformed"].append(key + ":p02-p08 corner surface/material mismatch")
        report["matches"].append(
            {
                "id": a["id"],
                "complete": matched,
                "source_to_import": sorted([[s, t] for (t, s) in owner.items()]),
                "source_vertices": a["vertices"],
                "import_vertices": b["vertices"],
                "source_slots": a["slots"],
                "import_slots": b["slots"],
            }
        )
    return report
