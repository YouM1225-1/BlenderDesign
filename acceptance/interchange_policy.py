from __future__ import annotations

import math
from pathlib import Path
from typing import cast

PRESET = dict(
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_draco_mesh_compression_enable=False,
    export_image_format="AUTO",
    export_cameras=False,
    export_lights=False,
    export_animations=False,
    export_extras=True,
    export_skins=False,
    export_morph=False,
    export_texcoords=True,
    export_normals=True,
    export_tangents=False,
    export_materials="EXPORT",
    use_selection=True,
    use_visible=False,
    use_renderable=False,
    use_active_collection=False,
)
LIMITS = {
    "max_glb_bytes",
    "max_json_bytes",
    "max_nodes",
    "max_meshes",
    "max_stored_triangles",
    "max_rendered_triangles",
    "max_draw_calls",
    "max_texture_pixels",
    "max_matches",
    "max_projection_triangles",
}


def _is_finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(cast(int | float, value))
    except OverflowError:
        return False


def validate_interchange_policy(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "profile",
        "preset",
        "package_root",
        "validator_version",
        "limits",
        "tolerances",
        "reference_scale",
        "allowed_extensions",
        "losses",
        "consumer",
    }:
        raise ValueError("closed interchange policy required")
    preset = value["preset"]
    if (
        value["profile"] != "glb-static-surface-v1"
        or not isinstance(preset, dict)
        or set(preset) != set(PRESET)
        or any(
            type(preset[k]) is not type(v) or preset[k] != v for k, v in PRESET.items()
        )
    ):
        raise ValueError("unsupported GLB preset/profile")
    if (
        value["validator_version"] != "2.0.0-dev.3.10"
        or not isinstance(value["package_root"], str)
        or not Path(value["package_root"]).is_absolute()
    ):
        raise ValueError("locked validator package identity required")
    if not isinstance(value["limits"], dict) or set(value["limits"]) != LIMITS:
        raise ValueError("closed budget fields required")
    if any(type(n) is not int or n <= 0 for n in value["limits"].values()):
        raise ValueError("positive integer GLB budgets required")
    if (
        value["limits"]["max_projection_triangles"] > 4096
        or value["limits"]["max_matches"] > 2000000
    ):
        raise ValueError("bounded surface profile exceeded")
    if not isinstance(value["tolerances"], dict) or set(value["tolerances"]) != {
        "geometry",
        "normal",
        "uv",
        "material",
    }:
        raise ValueError("four typed tolerances required")
    for tolerance in value["tolerances"].values():
        if not isinstance(tolerance, dict) or set(tolerance) != {"abs", "rel"}:
            raise ValueError("closed abs/rel tolerance required")
        if any(not _is_finite_number(n) or n < 0 for n in tolerance.values()):
            raise ValueError("finite nonnegative tolerance required")
    scale = value["reference_scale"]
    if not _is_finite_number(scale) or scale <= 0:
        raise ValueError("positive frozen source reference scale required")
    if value["allowed_extensions"] != []:
        raise ValueError("first GLB profile accepts core glTF 2.0 only")
    if value["losses"] != {
        "collections": "omit",
        "modifiers": "bake",
        "unused_vertices": "prune",
        "unused_material_slots": "prune",
        "unused_uv_layers": "preserve",
    }:
        raise ValueError("explicit first-profile loss policy required")
    if value["consumer"] is not None and (
        not isinstance(value["consumer"], str) or not value["consumer"]
    ):
        raise ValueError("consumer must be null or a named required adapter")
