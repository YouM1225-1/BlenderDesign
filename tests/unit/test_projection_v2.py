import copy
import itertools

import pytest

from acceptance.projection import compare_projection, validate_projection
from tests.unit.interchange_support import clean, policy, projection


def triangles(value):
    return value["objects"][0]["triangles"]


def textured():
    value = projection()
    material = triangles(value)[0]["material"]
    material["pbr"]["base_color"] = None
    material["texture"] = {
        "size": [1, 1],
        "channels": 4,
        "colorspace": "sRGB",
        "precision": "decoded-f32-le",
        "pixels": "a" * 64,
        "sampling": ["Linear", "REPEAT"],
        "uv_index": 0,
    }
    return value


def test_pruning_and_corner_rotation_preserve_the_actual_surface(tmp_path):
    source = projection()
    target = copy.deepcopy(source)
    target["objects"][0].update(vertices=3, slots=1)
    corners = triangles(target)[0]["corners"]
    triangles(target)[0]["corners"] = corners[1:] + corners[:1]
    report = compare_projection(source, target, policy(tmp_path))
    assert clean(report)
    assert report["matches"][0]["source_to_import"] == [[0, 0]]
    assert report["matches"][0]["source_slots"] == 2
    assert report["matches"][0]["import_slots"] == 1


@pytest.mark.parametrize(
    "field",
    [
        "position",
        "normal",
        "uv",
        "unused_uv",
        "material",
        "custom",
        "identity",
        "winding",
        "matrix",
        "triangle_count",
        "sidedness",
    ],
)
def test_same_counts_do_not_hide_semantic_loss(tmp_path, field):
    source = projection()
    target = copy.deepcopy(source)
    obj = target["objects"][0]
    tri = triangles(target)[0]
    if field in ("position", "normal"):
        tri["corners"][0][field][0] += 0.1
    elif field == "uv":
        tri["corners"][0]["uv"][0][0] += 0.1
    elif field == "unused_uv":
        for corner in tri["corners"]:
            corner["uv"] = []
    elif field == "material":
        tri["material"]["pbr"]["roughness"] = 0.9
    elif field == "custom":
        obj["custom"]["name"] = "lost"
    elif field == "identity":
        obj["id"][1] = "other"
    elif field == "matrix":
        obj["matrix"][0][3] += 0.1
    elif field == "triangle_count":
        obj["triangles"].append(copy.deepcopy(tri))
    elif field == "sidedness":
        tri["material"]["double_sided"] = False
    else:
        tri["corners"].reverse()
    assert not clean(compare_projection(source, target, policy(tmp_path)))


@pytest.mark.parametrize("size", [1.0, 1e-6, 1e-300, 1e308])
@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_ordered_orientation_survives_numeric_extremes(tmp_path, size, order):
    source = projection()
    tiny = copy.deepcopy(triangles(source)[0])
    for corner, position in zip(tiny["corners"], [[0, 0, 0], [size, 0, 0], [0, size, 0]]):
        corner.update(position=position, uv=[[0, 0]])
    triangles(source).append(tiny)
    target = copy.deepcopy(source)
    corners = triangles(target)[1]["corners"]
    triangles(target)[1]["corners"] = [corners[i] for i in order]
    report = compare_projection(source, target, policy(tmp_path))
    assert clean(report) == (order in ((0, 1, 2), (1, 2, 0), (2, 0, 1)))
    assert not any("bounds" in finding for finding in report["transformed"])


def test_orientation_handles_overflowing_edge_subtraction(tmp_path):
    source = projection()
    for corner, position in zip(
        triangles(source)[0]["corners"],
        [
            [-1e308, 0, 0],
            [1e308, 0, 0],
            [0, 1e308, 0],
        ],
    ):
        corner.update(position=position, uv=[[0, 0]])
    assert clean(compare_projection(source, copy.deepcopy(source), policy(tmp_path)))
    target = copy.deepcopy(source)
    triangles(target)[0]["corners"].reverse()
    assert not clean(compare_projection(source, target, policy(tmp_path)))


def test_undefined_orientation_cannot_claim_preservation(tmp_path):
    source = projection()
    for i, corner in enumerate(triangles(source)[0]["corners"]):
        corner["position"] = [i, 0, 0]
    assert not clean(compare_projection(source, copy.deepcopy(source), policy(tmp_path)))


@pytest.mark.parametrize("scale", [1, 1.0])
def test_numeric_metre_scales_are_supported(tmp_path, scale):
    source = projection()
    source["scale_length"] = scale
    assert clean(compare_projection(source, projection(), policy(tmp_path)))


@pytest.mark.parametrize("scale", [True, False, "1", None, 0, 2, 10**400, float("nan")])
def test_invalid_metre_scales_raise_value_error(scale):
    value = projection()
    value["scale_length"] = scale
    with pytest.raises(ValueError):
        validate_projection(value, 10)


@pytest.mark.parametrize(
    "field", ["position", "normal", "uv", "matrix", "roughness", "base_color", "emission"]
)
@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), -float("inf"), 10**400])
def test_numeric_validation_is_total(field, bad):
    value = projection()
    tri = triangles(value)[0]
    if field in ("position", "normal"):
        tri["corners"][0][field][0] = bad
    elif field == "uv":
        tri["corners"][0]["uv"][0][0] = bad
    elif field == "matrix":
        value["objects"][0]["matrix"][0][0] = bad
    elif field == "roughness":
        tri["material"]["pbr"][field] = bad
    else:
        tri["material"]["pbr"][field][0] = bad
    with pytest.raises(ValueError):
        validate_projection(value, 10)


@pytest.mark.parametrize("number", [0, 1, 0.0, 1.0])
def test_pbr_scalar_boundaries_are_valid(number):
    value = projection()
    triangles(value)[0]["material"]["pbr"]["roughness"] = number
    validate_projection(value, 10)


@pytest.mark.parametrize("number", [-0.01, 1.01])
def test_pbr_scalar_outside_range_is_rejected(number):
    value = projection()
    triangles(value)[0]["material"]["pbr"]["roughness"] = number
    with pytest.raises(ValueError, match="bounded PBR"):
        validate_projection(value, 10)


@pytest.mark.parametrize(
    "custom",
    [
        {"number": 10**400},
        {"number": 2**53 + 1},
        {"number": float("nan")},
        {"number": float("inf")},
        {"tuple": (1, 2)},
        {1: "bad"},
        {"text": "e\u0301"},
    ],
)
def test_custom_values_must_belong_to_canonical_json_domain(custom):
    value = projection()
    value["objects"][0]["custom"] = custom
    with pytest.raises(ValueError):
        validate_projection(value, 10)


def test_custom_supported_json_and_exact_integer_control(tmp_path):
    value = projection()
    value["objects"][0]["custom"] = {"values": [None, True, False, 2**60, 0.25, {"é": "kept"}]}
    assert clean(compare_projection(value, copy.deepcopy(value), policy(tmp_path)))


def test_custom_depth_is_bounded():
    value = projection()
    nested = []
    for _ in range(17):
        nested = [nested]
    value["objects"][0]["custom"] = {"nested": nested}
    with pytest.raises(ValueError, match="depth"):
        validate_projection(value, 10)


@pytest.mark.parametrize("replacement", [1.0, True, 2])
def test_p12_preserves_exact_numeric_types(tmp_path, replacement):
    source = projection()
    source["objects"][0]["custom"] = {"number": 1}
    target = copy.deepcopy(source)
    target["objects"][0]["custom"]["number"] = replacement
    report = compare_projection(source, target, policy(tmp_path))
    assert any("p12" in finding for finding in report["preserved"])


def test_texture_valid_control_and_digest_changes(tmp_path):
    source = textured()
    assert clean(compare_projection(source, copy.deepcopy(source), policy(tmp_path)))
    target = copy.deepcopy(source)
    triangles(target)[0]["material"]["texture"]["pixels"] = "b" * 64
    assert not clean(compare_projection(source, target, policy(tmp_path)))


@pytest.mark.parametrize(
    "field,bad",
    [
        ("channels", 4.0),
        ("channels", True),
        ("size", [True, 1]),
        ("uv_index", True),
        ("uv_index", 1),
        ("pixels", "g" * 64),
        ("sampling", ["Closest", "REPEAT"]),
        ("precision", "encoded"),
        ("colorspace", "Linear"),
    ],
)
def test_texture_closed_representation(field, bad):
    value = textured()
    triangles(value)[0]["material"]["texture"][field] = bad
    with pytest.raises(ValueError):
        validate_projection(value, 10)


@pytest.mark.parametrize(
    "level", ["projection", "object", "triangle", "corner", "material", "pbr", "texture"]
)
def test_closed_projection_fields(level):
    value = textured()
    tri = triangles(value)[0]
    scopes = {
        "projection": value,
        "object": value["objects"][0],
        "triangle": tri,
        "corner": tri["corners"][0],
        "material": tri["material"],
        "pbr": tri["material"]["pbr"],
        "texture": tri["material"]["texture"],
    }
    scopes[level]["unknown"] = 1
    with pytest.raises(ValueError, match="closed projection"):
        validate_projection(value, 10)


@pytest.mark.parametrize("field,bad", [("vertices", True), ("slots", 1.0), ("vertices", -1)])
def test_counts_require_nonnegative_exact_integers(field, bad):
    value = projection()
    value["objects"][0][field] = bad
    with pytest.raises(ValueError):
        validate_projection(value, 10)


def test_aggregate_triangle_cap_and_empty_surface():
    value = projection()
    second = copy.deepcopy(value["objects"][0])
    second["id"][1] = "second"
    value["objects"].append(second)
    with pytest.raises(ValueError, match="bounded triangle"):
        validate_projection(value, 1)
    triangles(value).clear()
    with pytest.raises(ValueError, match="nonempty triangle"):
        validate_projection(value, 10)


def test_duplicate_identity_is_ambiguous(tmp_path):
    source = projection()
    target = copy.deepcopy(source)
    target["objects"].append(copy.deepcopy(target["objects"][0]))
    assert compare_projection(source, target, policy(tmp_path))["ambiguous"]


def roughness_surface(values):
    result = projection()
    template = triangles(result).pop()
    for roughness in values:
        tri = copy.deepcopy(template)
        tri["material"]["pbr"]["roughness"] = roughness
        triangles(result).append(tri)
    return result


def test_augmenting_matching_reassigns_previous_owner(tmp_path):
    limits = policy(tmp_path)
    limits["tolerances"]["material"] = {"abs": 0.100001, "rel": 0}
    limits["limits"]["max_matches"] = 4
    source = roughness_surface([0.5, 0.3])
    target = roughness_surface([0.4, 0.6])
    report = compare_projection(source, target, limits)
    assert clean(report)
    assert report["matches"][0]["source_to_import"] == [[0, 1], [1, 0]]
    assert report["comparisons"] == 4
    limits["limits"]["max_matches"] = 3
    with pytest.raises(ValueError, match="matching budget"):
        compare_projection(source, target, limits)


def test_hall_deficit_cannot_reuse_target_triangle(tmp_path):
    report = compare_projection(
        roughness_surface([0.3, 0.3, 0.7]), roughness_surface([0.3, 0.7, 0.7]), policy(tmp_path)
    )
    assert not clean(report)
    assert not report["matches"][0]["complete"]
    mapping = report["matches"][0]["source_to_import"]
    assert len({row[1] for row in mapping}) == len(mapping)


def test_matching_budget_is_global_and_counts_material_misses(tmp_path):
    source = projection()
    second = copy.deepcopy(source["objects"][0])
    second["id"][1] = "second"
    source["objects"].append(second)
    target = copy.deepcopy(source)
    triangles(target)[0]["material"]["pbr"]["roughness"] = 0.9
    limits = policy(tmp_path)
    limits["limits"]["max_matches"] = 1
    with pytest.raises(ValueError, match="matching budget"):
        compare_projection(source, target, limits)
    limits["limits"]["max_matches"] = 2
    assert compare_projection(source, target, limits)["comparisons"] == 2
