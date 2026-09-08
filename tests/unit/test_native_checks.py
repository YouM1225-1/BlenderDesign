from copy import deepcopy
from typing import Any, Callable

import pytest

from acceptance.native_checks import (
    inspect_checks,
    reference_findings,
    scene_geometry_findings,
    validate_manifest,
)


LIMITS = {
    "max_objects": 100,
    "max_vertices": 100,
    "max_triangles": 100,
    "max_image_pixels": 100,
}


def geometry() -> dict[str, Any]:
    return {
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        "edges": [[0, 1], [1, 2], [2, 0]],
        "edge_seams": [False, False, False],
        "edge_sharp": [False, False, False],
        "loops": [0, 1, 2],
        "polygons": [[0, 3, 0, False]],
        "uv": [],
        "colors": [],
        "validate_corrected": False,
        "triangulation": "Blender Mesh.calc_loop_triangles locked build",
        "triangles_complete": True,
        "triangles": [[0, 1, 2]],
        "corner_normals": [[0, 0, 1], [0, 0, 1], [0, 0, 1]],
    }


def sample() -> dict[str, Any]:
    matrix = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return {
        "schema_version": 2,
        "support_profile": "native-static-v1",
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "units": {"system": "METRIC", "scale_length": 1},
        "auxiliary_inventory": {"worlds": [], "cameras": [], "lights": []},
        "coverage": [],
        "scope_gaps": [],
        "occurrences_complete": True,
        "reserved_props": [],
        "collections": [{"path": ["Collection"], "exclude": False, "hide_render": False}],
        "objects": [
            {
                "id": ["OBJECT", "Body"],
                "type": "MESH",
                "paths": [["Collection"]],
                "parent": None,
                "matrix_world": deepcopy(matrix),
                "hide_render": False,
                "hide_viewport": False,
                "hide_get": False,
                "render_included": True,
                "exclusion_reason": None,
                "modifiers": [],
                "custom_props": {"review": {"weight": 1}},
                "materials": ["Paint"],
            }
        ],
        "meshes": {"Body": {"authored": geometry(), "evaluated": geometry()}},
        "occurrences": [
            {
                "key": [["OBJECT", "Body"], []],
                "source": ["OBJECT", "Body"],
                "instancer_chain": [],
                "geometry": ["MESH", "Body", "evaluated"],
                "matrix_world": deepcopy(matrix),
            }
        ],
        "materials": [
            {
                "id": ["MATERIAL", "Paint"],
                "nodes": [{"name": "Principled BSDF", "type": "BSDF_PRINCIPLED", "inputs": {}}],
                "links": [],
            }
        ],
        "dependencies": [],
        "invalid_numbers": [],
    }


def failed_checks(value: dict[str, Any]) -> set[str]:
    return {row["id"] for row in inspect_checks(value, True) if row["findings"]}


def one_vertex_geometry() -> dict[str, Any]:
    value = geometry()
    value.update(
        vertices=[[0, 0, 0]],
        edges=[],
        edge_seams=[],
        edge_sharp=[],
        loops=[],
        polygons=[],
        triangles=[],
        corner_normals=[],
    )
    return value


def two_triangle_geometry() -> dict[str, Any]:
    value = geometry()
    value.update(
        loops=[0, 1, 2, 0, 2, 1],
        polygons=[[0, 3, 0, False], [3, 3, 0, False]],
        triangles=[[0, 1, 2], [3, 4, 5]],
        corner_normals=[[0, 0, 1]] * 6,
    )
    return value


def test_valid_manifest_and_checks_are_clean() -> None:
    value = sample()
    validate_manifest(value, LIMITS)
    assert not failed_checks(value)
    assert not scene_geometry_findings(value)
    assert not reference_findings(value, deepcopy(value))


@pytest.mark.parametrize("slots", [[], [None], ["Ghost"]])
def test_actual_used_material_is_required(slots: list[str | None]) -> None:
    value = sample()
    value["objects"][0]["materials"] = slots
    if slots == ["Ghost"]:
        value["materials"] = []
    assert "r2.material.slots_resolved" in failed_checks(value)


def test_unused_null_material_slot_remains_allowed() -> None:
    value = sample()
    value["objects"][0]["materials"].append(None)
    assert "r2.material.slots_resolved" not in failed_checks(value)


def test_negative_used_material_slot_is_unresolved_before_validation() -> None:
    value = sample()
    value["meshes"]["Body"]["evaluated"]["polygons"][0][2] = -1
    assert "r2.material.slots_resolved" in failed_checks(value)


def test_tex_image_reference_must_resolve_to_declared_dependency() -> None:
    value = sample()
    value["materials"][0]["nodes"].append(
        {
            "name": "Image Texture",
            "type": "TEX_IMAGE",
            "inputs": {},
            "image": "Ghost",
            "interpolation": "Linear",
            "projection": "FLAT",
            "extension": "REPEAT",
        }
    )
    assert "r2.dependency.all_present" in failed_checks(value)


def test_same_count_surface_change_is_not_an_equal_reference() -> None:
    reference = sample()
    candidate = deepcopy(reference)
    candidate["meshes"]["Body"]["evaluated"]["vertices"][0][0] = 0.25
    assert reference_findings(candidate, reference)
    assert not reference_findings(reference, reference)


def test_reference_comparison_uses_project_canonical_number_model() -> None:
    reference = sample()
    candidate = deepcopy(reference)
    candidate["objects"][0]["custom_props"]["review"]["weight"] = True
    assert [row["code"] for row in reference_findings(candidate, reference)] == [
        "reference_objects_mismatch"
    ]
    candidate["objects"][0]["custom_props"]["review"]["weight"] = 1.0
    assert not reference_findings(candidate, reference)


def test_zero_transform_has_occurrence_but_degenerate_surface() -> None:
    value = sample()
    value["occurrences"][0]["matrix_world"] = [[0, 0, 0, 0]] * 3 + [[0, 0, 0, 1]]
    assert value["occurrences"]
    assert {row["code"] for row in scene_geometry_findings(value)} == {"degenerate_world_triangle"}


def test_nonzero_finite_cross_is_not_lost_to_square_underflow() -> None:
    value = sample()
    vertices = [[0, 0, 0], [1e-44, 0, 0], [0, 1e-44, 0]]
    value["meshes"]["Body"]["authored"]["vertices"] = deepcopy(vertices)
    value["meshes"]["Body"]["evaluated"]["vertices"] = deepcopy(vertices)
    matrix = [[1e-44, 0, 0, 0], [0, 1e-44, 0, 0], [0, 0, 1e-44, 0], [0, 0, 0, 1]]
    value["objects"][0]["matrix_world"] = deepcopy(matrix)
    value["occurrences"][0]["matrix_world"] = deepcopy(matrix)
    validate_manifest(value, LIMITS)
    assert not scene_geometry_findings(value)


def test_large_finite_coordinates_do_not_escape_cross_check() -> None:
    value = sample()
    big = 2**1023
    vertices = [[0, 0, 0], [big, 0, 0], [0, big, 0]]
    value["meshes"]["Body"]["authored"]["vertices"] = deepcopy(vertices)
    value["meshes"]["Body"]["evaluated"]["vertices"] = deepcopy(vertices)
    validate_manifest(value, LIMITS)
    assert {row["code"] for row in scene_geometry_findings(value)} == {
        "degenerate_world_triangle"
    }


def test_large_finite_coordinates_do_not_escape_world_point_check() -> None:
    value = sample()
    big = 2**1023
    vertices = [[0, 0, 0], [big, big, 0], [0, big, 0]]
    value["meshes"]["Body"]["authored"]["vertices"] = deepcopy(vertices)
    value["meshes"]["Body"]["evaluated"]["vertices"] = deepcopy(vertices)
    matrix = [[big, 1.0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    value["objects"][0]["matrix_world"] = deepcopy(matrix)
    value["occurrences"][0]["matrix_world"] = deepcopy(matrix)
    validate_manifest(value, LIMITS)
    assert {row["code"] for row in scene_geometry_findings(value)} == {
        "degenerate_world_triangle"
    }


def test_missing_bottom_cannot_be_fixed_by_repeating_wrong_asset() -> None:
    reference = sample()
    candidate = deepcopy(reference)
    candidate["occurrences"] = []
    assert reference_findings(candidate, reference)
    assert {row["code"] for row in scene_geometry_findings(candidate)} == {"no_render_occurrence"}


def test_diagnosed_nan_is_quality_evidence_not_protocol_rejection() -> None:
    value = sample()
    value["meshes"]["Body"]["authored"]["vertices"][0][0] = None
    value["meshes"]["Body"]["authored"]["validate_corrected"] = True
    value["meshes"]["Body"]["authored"]["triangles_complete"] = False
    value["meshes"]["Body"]["authored"]["triangles"] = []
    value["invalid_numbers"] = [
        {"path": ["meshes", "Body", "authored", "vertices", 0, 0], "value": "nan"}
    ]
    validate_manifest(value, LIMITS)
    failed = failed_checks(value)
    assert {
        "r2.inventory.no_nan_inf",
        "r2.geometry.validate_clean",
        "r2.geometry.manifest_written",
    } <= failed
    assert {row["code"] for row in scene_geometry_findings(value)} == {"geometry_not_verified"}


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value["meshes"]["Body"]["evaluated"].update(polygons=[[]]),
        lambda value: value["occurrences"][0].update(matrix_world=[]),
        lambda value: value.update(meshes=[]),
    ],
)
def test_consumed_shapes_are_rejected_before_downstream_checks(
    change: Callable[[dict[str, Any]], None],
) -> None:
    value = sample()
    change(value)
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


def test_undiagnosed_numeric_null_is_rejected() -> None:
    value = sample()
    value["occurrences"][0]["matrix_world"][0][0] = None
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


@pytest.mark.parametrize(
    "path",
    [
        ["missing"],
        ["objects", 99],
        ["objects", "wrong-container-key"],
        ["objects", {}],
    ],
)
def test_malformed_invalid_number_paths_are_normalized_to_value_error(path: list[Any]) -> None:
    value = sample()
    value["invalid_numbers"] = [{"path": path, "value": "nan"}]
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


def test_unhashable_diagnostic_token_is_normalized_to_value_error() -> None:
    value = sample()
    value["invalid_numbers"] = [{"path": ["objects", 0, "parent"], "value": []}]
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


def test_unhashable_coverage_policy_is_normalized_to_value_error() -> None:
    value = sample()
    value["coverage"] = [{"type": "objects", "count": 1, "policy": []}]
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


@pytest.mark.parametrize("stage", ["authored", "evaluated"])
@pytest.mark.parametrize("kind", ["vertices", "triangles"])
def test_each_geometry_stage_has_its_own_aggregate_cap(stage: str, kind: str) -> None:
    value = sample()
    other = "evaluated" if stage == "authored" else "authored"
    value["meshes"]["Body"][stage] = two_triangle_geometry() if kind == "triangles" else geometry()
    value["meshes"]["Body"][other] = one_vertex_geometry()
    limits = deepcopy(LIMITS)
    limits["max_triangles" if kind == "triangles" else "max_vertices"] = (
        1 if kind == "triangles" else 2
    )
    with pytest.raises(ValueError):
        validate_manifest(value, limits)


def test_authored_and_evaluated_exact_caps_are_not_summed() -> None:
    value = sample()
    limits = deepcopy(LIMITS)
    limits.update(max_vertices=3, max_triangles=1)
    validate_manifest(value, limits)


def test_packed_image_pixel_cap_and_exact_boundary() -> None:
    value = sample()
    value["dependencies"] = [
        {
            "id": ["IMAGE", "Packed"],
            "source": "FILE",
            "packed": True,
            "bytes": 16,
            "sha256": "a" * 64,
            "size": [2, 2],
            "channels": 4,
            "is_float": False,
            "colorspace": "sRGB",
            "path": "//packed.png",
        }
    ]
    limits = deepcopy(LIMITS)
    limits["max_image_pixels"] = 4
    validate_manifest(value, limits)
    limits["max_image_pixels"] = 3
    with pytest.raises(ValueError):
        validate_manifest(value, limits)


def test_unpacked_zero_size_dependency_is_representable_but_fails_check() -> None:
    value = sample()
    value["dependencies"] = [
        {
            "id": ["IMAGE", "Missing"],
            "source": "FILE",
            "packed": False,
            "bytes": None,
            "sha256": None,
            "size": [0, 0],
            "channels": 0,
            "is_float": False,
            "colorspace": "sRGB",
            "path": "//missing.png",
        }
    ]
    validate_manifest(value, LIMITS)
    assert "r2.dependency.all_present" in failed_checks(value)


@pytest.mark.parametrize("records", ["materials", "dependencies"])
def test_declared_reference_ids_are_structured_and_unique(records: str) -> None:
    value = sample()
    if records == "materials":
        value[records].append(deepcopy(value[records][0]))
    else:
        dependency = {
            "id": ["IMAGE", "Packed"],
            "source": "FILE",
            "packed": True,
            "bytes": 16,
            "sha256": "a" * 64,
            "size": [2, 2],
            "channels": 4,
            "is_float": False,
            "colorspace": "sRGB",
            "path": "//packed.png",
        }
        value[records] = [dependency, deepcopy(dependency)]
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


def test_occurrence_identity_and_matrix_shapes_are_closed() -> None:
    value = sample()
    value["occurrences"][0]["geometry"] = ["MESH", "Other", "evaluated"]
    with pytest.raises(ValueError):
        validate_manifest(value, LIMITS)


def test_incomplete_geometry_retains_quality_findings() -> None:
    value = sample()
    authored = value["meshes"]["Body"]["authored"]
    authored["validate_corrected"] = True
    authored["triangles_complete"] = False
    authored["triangles"] = []
    authored["loops"] = [99]
    authored["polygons"] = [[0, 1, 0, False]]
    authored["corner_normals"] = []
    validate_manifest(value, LIMITS)
    assert {
        "r2.geometry.validate_clean",
        "r2.geometry.manifest_written",
    } <= failed_checks(value)
