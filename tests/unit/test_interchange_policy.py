import pytest

from acceptance import interchange_policy
from acceptance.interchange_policy import validate_interchange_policy
from tests.unit.interchange_support import policy


def test_valid_policy_is_accepted(tmp_path) -> None:
    validate_interchange_policy(policy(tmp_path))


def test_zero_tolerances_are_allowed(tmp_path) -> None:
    value = policy(tmp_path)
    for tolerance in value["tolerances"].values():
        tolerance.update(abs=0, rel=0.0)
    validate_interchange_policy(value)


@pytest.mark.parametrize(
    "mutation",
    [
        "nan",
        "bool",
        "unknown",
        "negative",
        "uv_loss",
        "package",
        "tolerance",
        "preset_bool",
    ],
)
def test_closed_policy_rejects_unsafe_values(tmp_path, mutation) -> None:
    value = policy(tmp_path)
    if mutation == "nan":
        value["reference_scale"] = float("nan")
    elif mutation == "bool":
        value["limits"]["max_nodes"] = True
    elif mutation == "unknown":
        value["extra"] = 1
    elif mutation == "negative":
        value["limits"]["max_glb_bytes"] = -1
    elif mutation == "uv_loss":
        value["losses"]["unused_uv_layers"] = "prune"
    elif mutation == "package":
        value["package_root"] = "relative"
    elif mutation == "preset_bool":
        value["preset"]["export_apply"] = 1
    else:
        value["tolerances"]["uv"]["abs"] = True
    with pytest.raises(ValueError):
        validate_interchange_policy(value)


@pytest.mark.parametrize("target", ["reference_scale", "tolerance"])
def test_large_integer_overflow_is_rejected_as_value_error(tmp_path, target) -> None:
    value = policy(tmp_path)
    if target == "reference_scale":
        value["reference_scale"] = 10**400
    else:
        value["tolerances"]["uv"]["abs"] = 10**400
    with pytest.raises(ValueError):
        validate_interchange_policy(value)


def test_borrowed_public_preset_cannot_change_validator_policy(tmp_path) -> None:
    original = policy(tmp_path)
    saved_preset = dict(interchange_policy.PRESET)
    try:
        interchange_policy.PRESET["export_apply"] = False
        customized = policy(tmp_path)

        validate_interchange_policy(original)
        with pytest.raises(ValueError):
            validate_interchange_policy(customized)
    finally:
        interchange_policy.PRESET.clear()
        interchange_policy.PRESET.update(saved_preset)


def test_borrowed_limit_names_cannot_change_validator_policy(tmp_path) -> None:
    original = policy(tmp_path)
    missing_required_limit = policy(tmp_path)
    missing_required_limit["limits"].pop("max_nodes")
    borrowed_limits = interchange_policy.LIMITS
    try:
        borrowed_limits -= {"max_nodes"}

        with pytest.raises(ValueError):
            validate_interchange_policy(missing_required_limit)
        validate_interchange_policy(original)
    finally:
        if isinstance(borrowed_limits, set):
            borrowed_limits.add("max_nodes")
