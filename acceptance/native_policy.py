from __future__ import annotations

import math
from typing import Any

VIEWS = ("front", "back", "left", "right", "top", "bottom", "persp", "obliqueA", "obliqueB")
PASSES = ("beauty", "clay", "silhouette", "wire")
PLATFORM_FIELDS = {
    "blender",
    "build",
    "os",
    "arch",
    "backend",
    "vendor",
    "gpu",
    "engines",
    "view_transform",
    "look",
    "format",
    "comparator",
}


def exact(value: Any, keys: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("closed native policy keys mismatch")


def number(value: Any, *, positive: bool = False) -> None:
    if type(value) not in (int, float):
        raise ValueError("finite native number required")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError("finite native number required") from exc
    if not finite or (value <= 0 if positive else value < 0):
        raise ValueError("finite native number required")


def validate_native_policy(value: Any) -> None:
    exact(
        value,
        {
            "scene",
            "view_layer",
            "frame",
            "support_profile",
            "reference_manifest_id",
            "reference_authority",
            "render",
            "geometry_limits",
        },
    )
    for key in ("scene", "view_layer", "reference_manifest_id", "reference_authority"):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 1024:
            raise ValueError("native policy text required")
    if type(value["frame"]) is not int or not -1048574 <= value["frame"] <= 1048574:
        raise ValueError("native frame outside Blender range")
    if value["support_profile"] != "native-static-v1":
        raise ValueError("unsupported native profile")
    limits = value["geometry_limits"]
    exact(limits, {"max_objects", "max_vertices", "max_triangles", "max_image_pixels"})
    for item in limits.values():
        if type(item) is not int or item <= 0:
            raise ValueError("positive integer geometry limit required")
    render = value["render"]
    exact(
        render,
        {
            "resolution",
            "views",
            "reference_center",
            "reference_radius",
            "platform",
            "max_abs",
            "reference_images",
            "beauty_hard_gate",
        },
    )
    if render["resolution"] != 1024 or type(render["resolution"]) is not int:
        raise ValueError("native-static-v1 uses 1024x1024")
    if render["views"] != list(VIEWS):
        raise ValueError("full 3D native profile requires all nine views")
    if not isinstance(render["reference_center"], list) or len(render["reference_center"]) != 3:
        raise ValueError("reference center needs three coordinates")
    for item in render["reference_center"]:
        number(item)
    number(render["reference_radius"], positive=True)
    exact(render["platform"], PLATFORM_FIELDS)
    if any(not isinstance(v, str) or not v for v in render["platform"].values()):
        raise ValueError("complete calibrated platform identity required")
    exact(render["max_abs"], set(PASSES))
    for item in render["max_abs"].values():
        number(item)
        if item > 1:
            raise ValueError("RGBA float32 comparison threshold outside [0,1]")
    exact(render["reference_images"], {v + "." + p for v in VIEWS for p in PASSES})
    image_ids = list(render["reference_images"].values())
    if any(not isinstance(v, str) or not v for v in image_ids) or len(set(image_ids)) != len(
        image_ids
    ):
        raise ValueError("unique frozen reference image IDs required")
    if type(render["beauty_hard_gate"]) is not bool:
        raise ValueError("beauty_hard_gate must be bool")
    if limits["max_image_pixels"] < 1024 * 1024:
        raise ValueError("image budget cannot cover the mandatory image")


def validate_native_parameters(parameters: Any) -> None:
    exact(parameters, {"operation", "policy", "experiment"})
    operation = parameters["operation"]
    experiment = parameters["experiment"]
    if type(operation) is not str or operation not in {"inspect", "reopen", "render", "compare"}:
        raise ValueError("unknown native operation")
    if type(experiment) is not str or experiment not in {"none", "same_process", "fresh_a", "fresh_b"}:
        raise ValueError("unknown native experiment")
    if (operation == "render") != (experiment != "none"):
        raise ValueError("operation/experiment mismatch")
    validate_native_policy(parameters["policy"])
