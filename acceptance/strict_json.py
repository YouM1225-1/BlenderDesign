"""Strict JSON parsing shared by acceptance and smoke tools."""

import json
import math


def reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_json_loads(raw: str | bytes) -> object:
    return json.loads(
        raw,
        parse_constant=reject_json_constant,
        parse_float=finite_json_float,
        object_pairs_hook=reject_duplicate_keys,
    )
