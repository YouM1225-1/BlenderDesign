from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from pathlib import Path

from acceptance.contract import Contract, thaw
from acceptance.decide import Finding
from acceptance.input_bundle import BoundFile
from acceptance.primitives import AcceptanceFailure
from acceptance.toolchain import verify_blender_gltf


def run_r0(contract: Contract, *, tools_measured: list[dict[str, Any]]) -> dict[str, list[Finding]]:
    declared = {t["id"]: t for t in contract.raw["tools"]}
    measured = {t["id"]: t for t in tools_measured}
    valid = len(measured) == len(tools_measured) and set(measured) == set(declared)
    gltf_error = None
    if contract.artifact_kind == "interchange" and "blender" in declared:
        try:
            verify_blender_gltf(declared["blender"])
        except AcceptanceFailure as exc:
            gltf_error = str(exc)
            valid = False
    if valid:
        valid = all(
            measured[key]["sha256"] == value["sha256"]
            and measured[key]["version"] == value["version"]
            and Path(measured[key]["path"]).resolve() == Path(value["path"]).resolve()
            and measured[key].get("files") == thaw(value["files"])
            for key, value in declared.items()
        )
    return {
        "r0.contract.schema_closed": [],
        "r0.contract.na_set_declared": [],
        "r0.contract.tools_locked": []
        if valid
        else [Finding("tool_identity_mismatch", "error", detail=gltf_error)],
    }


def run_r1(contract: Contract, input_files: Mapping[str, BoundFile]) -> dict[str, list[Finding]]:
    expected = {r["id"]: r for r in contract.raw["input"]["files"]}
    identity_ok = set(input_files) == set(expected) and all(
        actual.bytes == expected[key]["bytes"] and actual.sha256 == expected[key]["sha256"]
        for key, actual in input_files.items()
        if key in expected
    )
    within = (
        len(input_files) <= contract.raw["budget"]["max_files"]
        and sum(item.bytes for item in input_files.values())
        <= contract.raw["budget"]["max_total_bytes"]
        and all(
            item.bytes <= contract.raw["budget"]["max_file_bytes"] for item in input_files.values()
        )
    )
    return {
        "r1.input.digest_recorded": []
        if identity_ok
        else [Finding("input_identity_mismatch", "error")],
        "r1.input.no_link_or_device": [],
        "r1.input.size_within_limit": [] if within else [Finding("input_budget_exceeded", "error")],
    }
