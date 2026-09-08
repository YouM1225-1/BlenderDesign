from copy import deepcopy
from typing import Any, Callable

import pytest

from acceptance.native_policy import (
    PASSES,
    VIEWS,
    validate_native_parameters,
    validate_native_policy,
)


def policy() -> dict[str, Any]:
    return {
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "support_profile": "native-static-v1",
        "reference_manifest_id": "native.reference",
        "reference_authority": "trusted-native-fixture-v1",
        "geometry_limits": {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 1048576,
        },
        "render": {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
            "beauty_hard_gate": False,
            "platform": {
                "blender": "5.2.0 LTS",
                "build": "fbe6228777e7",
                "os": "Darwin",
                "arch": "arm64",
                "backend": "METAL",
                "vendor": "Apple M4",
                "gpu": "Metal API",
                "engines": "BLENDER_EEVEE,BLENDER_WORKBENCH",
                "view_transform": "Standard",
                "look": "None",
                "format": "PNG_RGBA8",
                "comparator": "blender-rgba-f32-v1",
            },
            "max_abs": {p: 0 for p in PASSES},
            "reference_images": {
                v + "." + p: "reference." + v + "." + p
                for v in VIEWS
                for p in PASSES
            },
        },
    }


def test_complete_policy_and_closed_job_parameters() -> None:
    value = policy()
    validate_native_policy(value)
    validate_native_parameters({"operation": "inspect", "policy": value, "experiment": "none"})
    with pytest.raises(ValueError):
        validate_native_parameters(
            {"operation": "inspect", "policy": value, "experiment": "fresh_a"}
        )


@pytest.mark.parametrize("center", [[-1, 0, 0], [-0.5, 0, 0]])
def test_policy_accepts_signed_reference_center_coordinates(center: list[int | float]) -> None:
    value = policy()
    value["render"]["reference_center"] = center
    validate_native_policy(value)


@pytest.mark.parametrize(
    ("location", "value"),
    [
        (("render", "reference_radius"), 0),
        (("render", "reference_radius"), -1),
        (("render", "max_abs", "beauty"), -0.1),
        (("render", "max_abs", "beauty"), 1.1),
    ],
)
def test_policy_rejects_radius_and_threshold_sign_boundaries(
    location: tuple[str, ...], value: int | float
) -> None:
    candidate = policy()
    target = candidate
    for key in location[:-1]:
        target = target[key]
    target[location[-1]] = value
    with pytest.raises(ValueError):
        validate_native_policy(candidate)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(frame=True),
        lambda x: x["render"].update(reference_radius=float("nan")),
        lambda x: x["render"].update(views=list(VIEWS)[:-1]),
        lambda x: x["render"].update(extra="silently accepted"),
        lambda x: x["render"]["max_abs"].update(clay=True),
        lambda x: x["geometry_limits"].update(max_image_pixels=1024),
    ],
)
def test_policy_rejects_incomplete_or_ill_typed_values(
    change: Callable[[dict[str, Any]], None],
) -> None:
    value = deepcopy(policy())
    change(value)
    with pytest.raises(ValueError):
        validate_native_policy(value)


@pytest.mark.parametrize("field_value", [[], {}])
def test_parameters_reject_unhashable_operation_or_experiment(field_value: Any) -> None:
    value = policy()
    for field in ("operation", "experiment"):
        parameters = {
            "operation": "inspect",
            "policy": value,
            "experiment": "none",
        }
        parameters[field] = field_value
        with pytest.raises(ValueError):
            validate_native_parameters(parameters)


@pytest.mark.parametrize(
    ("location", "value"),
    [
        (("render", "reference_center", 0), 10**400),
        (("render", "reference_radius"), 10**400),
        (("render", "max_abs", "beauty"), 10**400),
    ],
)
def test_policy_normalizes_large_integer_overflow_to_value_error(
    location: tuple[str, ...], value: int
) -> None:
    candidate = policy()
    target = candidate
    for key in location[:-1]:
        target = target[key]
    target[location[-1]] = value
    with pytest.raises(ValueError):
        validate_native_policy(candidate)
