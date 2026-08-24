"""规范 §7.3 contract.json 的封闭加载与 §2.5.1 的 digest。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acceptance import check_registry as reg
from acceptance.canonical import CanonicalError, digest as canonical_digest
from acceptance.primitives import (
    AcceptanceFailure,
    finite_json_float,
    reject_duplicate_keys,
    reject_json_constant,
)

_TOP_LEVEL = frozenset({
    "schema_version", "contract_id", "artifact_kind", "profile",
    "required_isolation_grade", "input", "export", "checks", "na_check_ids",
    "warning_allowlist", "visual_thresholds", "platform_blocklist",
    "texture_colorspace", "tolerated_unknown_types", "validator_config_path",
    "budget", "projection", "tools", "limits", "golden",
})
_KINDS = frozenset({"blend_native", "interchange"})
_GRADES = ("local-trusted", "isolated", "attested")
PROJECTION_FIELDS: tuple[str, ...] = (
    "p01_object_count", "p02_triangle_count", "p03_bbox", "p04_vertex_count",
    "p05_uv_layers", "p06_material_slot_count", "p07_pbr_factors",
    "p08_texture_pixels", "p09_object_identity", "p10_collection_hierarchy",
    "p11_modifier_stack", "p12_custom_props", "p13_unit_system",
    "p14_drivers_constraints",
)


def _fail(message: str) -> AcceptanceFailure:
    return AcceptanceFailure("contract_invalid", message)


@dataclass(frozen=True, slots=True)
class Contract:
    raw: dict[str, Any]
    digest: str

    @property
    def artifact_kind(self) -> str:
        try:
            return str(self.raw["artifact_kind"])
        except KeyError as exc:
            raise _fail(f"missing required field: {exc}") from exc

    @property
    def na_check_ids(self) -> tuple[str, ...]:
        try:
            return tuple(self.raw["na_check_ids"])
        except KeyError as exc:
            raise _fail(f"missing required field: {exc}") from exc

    @property
    def required_isolation_grade(self) -> str:
        try:
            return str(self.raw["required_isolation_grade"])
        except KeyError as exc:
            raise _fail(f"missing required field: {exc}") from exc

    def allowlisted(self, check_id: str, code: str, tool_id: str, version: str) -> bool:
        target = {"check_id": check_id, "warning_code": code,
                  "tool_id": tool_id, "tool_version": version}
        try:
            allowlist = self.raw["warning_allowlist"]
        except KeyError as exc:
            raise _fail(f"missing required field: {exc}") from exc
        return any(entry == target for entry in allowlist)


def load_contract(path: Path, *, candidate_root: Path) -> Contract:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise _fail(f"contract file not found: {exc}") from exc
    root = candidate_root.expanduser().resolve()
    if resolved == root or root in resolved.parents:
        raise _fail("contract must live outside the candidate input tree")
    try:
        value = json.loads(
            resolved.read_text(encoding="utf-8"),
            parse_constant=reject_json_constant,
            parse_float=finite_json_float,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, ValueError) as exc:
        raise _fail(f"unreadable or invalid JSON: {exc}") from exc
    if type(value) is not dict:
        raise _fail("contract must be a JSON object")
    unknown = set(value) - _TOP_LEVEL
    if unknown:
        raise _fail(f"unknown top-level fields: {sorted(unknown)}")
    missing = _TOP_LEVEL - set(value)
    if missing:
        raise _fail(f"missing top-level fields: {sorted(missing)}")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise _fail("schema_version must be 1")
    kind = value["artifact_kind"]
    if type(kind) is not str or kind not in _KINDS:
        raise _fail(f"artifact_kind must be one of {sorted(_KINDS)}")
    if type(value["profile"]) is not str or value["profile"] != "static_render":
        raise _fail("profile must be static_render in P0")
    if type(value["required_isolation_grade"]) is not str or value["required_isolation_grade"] not in _GRADES:
        raise _fail(f"required_isolation_grade must be one of {list(_GRADES)}")

    expected_specs = sorted(reg.checks_for_kind(kind), key=reg.sort_key)
    declared = value["checks"]
    if type(declared) is not list or len(declared) != len(expected_specs):
        raise _fail("checks must list exactly the registry entries for this kind")
    for entry, spec in zip(declared, expected_specs, strict=True):
        if entry != {"id": spec.id, "impl": spec.impl, "order": spec.order}:
            raise _fail(f"checks entry mismatch or out of order at {spec.id}")

    if type(value["na_check_ids"]) is not list:
        raise _fail("na_check_ids must be a list")
    if list(value["na_check_ids"]) != list(reg.na_check_ids(kind)):
        raise _fail("na_check_ids must equal the derived not-applicable set")

    warning_allowlist = value["warning_allowlist"]
    if type(warning_allowlist) is not list:
        raise _fail("warning_allowlist must be a list")
    for entry in warning_allowlist:
        if type(entry) is not dict:
            raise _fail("warning_allowlist entries must be objects")
        if set(entry) != {"check_id", "warning_code", "tool_id", "tool_version"}:
            raise _fail("warning_allowlist entries must have check_id/warning_code/tool_id/tool_version")
        for key in ("check_id", "warning_code", "tool_id", "tool_version"):
            if type(entry[key]) is not str:
                raise _fail(f"warning_allowlist entries[].{key} must be a string")

    projection = value["projection"]
    if type(projection) is not dict:
        raise _fail("projection must be an object")
    if set(projection) != {"preserved", "transformed", "lost"}:
        raise _fail("projection must have preserved/transformed/lost")
    union: list[str] = []
    for group in ("preserved", "transformed", "lost"):
        items = projection[group]
        if type(items) is not list:
            raise _fail(f"projection.{group} must be a list")
        for item in items:
            if type(item) is not str:
                raise _fail(f"projection.{group} contains non-string element")
        union.extend(items)
    if kind == "interchange" and sorted(union) != sorted(PROJECTION_FIELDS):
        raise _fail("projection union must be exactly p01..p14 for interchange")
    if len(set(union)) != len(union):
        raise _fail("projection field appears in more than one group")

    tools = value["tools"]
    if type(tools) is not list:
        raise _fail("tools must be a list")
    for tool in tools:
        if type(tool) is not dict:
            raise _fail("tools entries must be objects")
        if set(tool) != {"id", "version", "sha256", "path"}:
            raise _fail("tools entries must have id/version/sha256/path")
        if not isinstance(tool["sha256"], str) or len(tool["sha256"]) != 64:
            raise _fail("tools[].sha256 must be a 64-char hex string")

    body = {k: v for k, v in value.items() if k != "contract_digest"}
    try:
        computed = canonical_digest("contract", body)
    except CanonicalError as exc:
        raise _fail(f"contract is not canonicalizable: {exc}") from exc
    return Contract(raw=value, digest=computed)
