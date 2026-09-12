from __future__ import annotations

from typing import Any

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from acceptance import check_registry as reg
from acceptance.canonical import canonicalize, digest
from acceptance.input_bundle import read_bounded, source_digest, valid_id
from acceptance.primitives import AcceptanceFailure, path_is_within
from acceptance.strict_json import strict_json_loads

_MAX_CONTRACT_BYTES = 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TOP = {
    "schema_version",
    "contract_id",
    "artifact_kind",
    "profile",
    "required_isolation_grade",
    "input",
    "checks",
    "na_check_ids",
    "warning_allowlist",
    "tools",
    "limits",
    "budget",
    "native",
    "interchange",
    "review",
    "policy_baseline",
}


def freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if type(value) is list:
        return tuple(freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if type(value) is tuple:
        return [thaw(v) for v in value]
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceFailure("contract_invalid", message)


def fields(value: Any, expected: set[str], name: str) -> None:
    require(type(value) is dict and set(value) == expected, f"{name}: closed fields required")


def positive(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def sha(value: Any) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


def validate_document(value: Any) -> None:
    fields(value, _TOP, "contract")
    require(
        type(value["schema_version"]) is int and value["schema_version"] == 2,
        "schema_version must be 2; v1 requires a new frozen candidate and contract",
    )
    require(valid_id(value["contract_id"]), "invalid contract_id")
    require(value["artifact_kind"] in ("blend_native", "interchange"), "invalid artifact_kind")
    require(value["profile"] == "static_render", "only static_render supported")
    require(
        value["required_isolation_grade"] == "local-trusted", "M1 has no isolated/attested runner"
    )
    source = value["input"]
    fields(source, {"main", "sha256", "files"}, "input")
    require(type(source["files"]) is list and sha(source["sha256"]), "invalid source identity")
    require(source_digest(source["files"]) == source["sha256"], "input package digest mismatch")
    require(type(source["main"]) is str, "main input id must be a string")
    require(source["main"] in {row["id"] for row in source["files"]}, "main input is not a member")
    specs = sorted(reg.checks_for_kind(value["artifact_kind"]), key=reg.sort_key)
    expected = [{"id": s.id, "impl": s.impl, "order": s.order} for s in specs]
    require(
        type(value["checks"]) is list and value["checks"] == expected, "check registry mismatch"
    )
    require(
        all(
            type(r) is dict
            and set(r) == {"id", "impl", "order"}
            and type(r["impl"]) is int
            and type(r["order"]) is int
            for r in value["checks"]
        ),
        "check types must be exact",
    )
    require(
        value["na_check_ids"] == list(reg.na_check_ids(value["artifact_kind"])),
        "N/A registry mismatch",
    )
    require(type(value["warning_allowlist"]) is list, "warning_allowlist must be a list")
    by_id = {s.id: s for s in specs}
    seen = set()
    for row in value["warning_allowlist"]:
        fields(row, {"check_id", "warning_code", "tool_id", "tool_version"}, "warning")
        require(all(type(v) is str and v for v in row.values()), "warning values must be strings")
        require(
            row["check_id"] in by_id
            and row["warning_code"] in by_id[row["check_id"]].warning_codes,
            "unknown warning rule",
        )
        require(
            row["check_id"] != "r2.inventory.coverage_complete",
            "unsupported coverage cannot be allowlisted",
        )
        key = tuple(sorted(row.items()))
        require(key not in seen, "duplicate warning rule")
        seen.add(key)
    fields(
        value["budget"],
        {"max_files", "max_file_bytes", "max_total_bytes", "max_result_bytes"},
        "budget",
    )
    require(
        all(type(v) is int and v > 0 for v in value["budget"].values()),
        "positive integer budgets required",
    )
    budget = value["budget"]
    require(
        len(source["files"]) <= budget["max_files"]
        and sum(r["bytes"] for r in source["files"]) <= budget["max_total_bytes"]
        and all(r["bytes"] <= budget["max_file_bytes"] for r in source["files"]),
        "source exceeds budget",
    )
    fields(
        value["limits"],
        {
            "timeout_seconds",
            "cpu_seconds",
            "rss_bytes",
            "open_files",
            "log_bytes",
            "file_size_bytes",
        },
        "limits",
    )
    limits = value["limits"]
    require(
        type(limits["timeout_seconds"]) is dict
        and all(type(k) is str and positive(v) for k, v in limits["timeout_seconds"].items()),
        "invalid writer timeouts",
    )
    require(
        all(type(limits[k]) is int and limits[k] > 0 for k in limits if k != "timeout_seconds"),
        "resource limits must be positive integers",
    )
    require(type(value["tools"]) is list and bool(value["tools"]), "tools cannot be empty")
    ids = set()
    for tool in value["tools"]:
        fields(tool, {"id", "path", "version", "sha256", "files"}, "tool")
        require(
            type(tool["id"]) is str
            and tool["id"] in {"python", "acceptance", "blender", "node"}
            and tool["id"] not in ids,
            "unknown or repeated tool",
        )
        ids.add(tool["id"])
        require(
            type(tool["path"]) is str and Path(tool["path"]).is_absolute(),
            "absolute tool path required",
        )
        require(
            type(tool["version"]) is str and bool(tool["version"]) and sha(tool["sha256"]),
            "invalid tool lock",
        )
        require(type(tool["files"]) is list, "tool files must be a list")
        seen_paths = set()
        for row in tool["files"]:
            fields(row, {"path", "bytes", "sha256"}, "tool file")
            require(
                type(row["path"]) is str
                and Path(row["path"]).is_absolute()
                and row["path"] not in seen_paths
                and sha(row["sha256"])
                and type(row["bytes"]) is int
                and row["bytes"] >= 0,
                "invalid tool file",
            )
            seen_paths.add(row["path"])
    require({"acceptance", "python", "blender"} <= ids, "required tool set is incomplete")
    if value["native"] is not None:
        from acceptance.native_policy import validate_native_policy

        try:
            validate_native_policy(value["native"])
        except ValueError as exc:
            raise AcceptanceFailure("contract_invalid", str(exc)) from exc
        input_ids = {item["id"] for item in value["input"]["files"]}
        native_ids = {value["native"]["reference_manifest_id"], value["native"]["reference_authority"]}
        native_ids.update(value["native"]["render"]["reference_images"].values())
        require(native_ids <= input_ids, "native references must be frozen input members")
        require(value["input"]["main"] == "asset", "native main file ID must be asset")
    if value["interchange"] is not None:
        require(value["artifact_kind"] == "interchange" and value["native"] is not None,
                "interchange requires an explicit native inspection/render policy")
        from acceptance.interchange_policy import validate_interchange_policy
        try:
            validate_interchange_policy(value["interchange"])
        except ValueError as exc:
            raise AcceptanceFailure("contract_invalid", str(exc)) from exc
    fields(value["review"], {"required", "reviewer_ids", "required_image_ids", "reason"}, "review")
    review = value["review"]
    require(
        type(review["required"]) is bool
        and type(review["reviewer_ids"]) is list
        and all(valid_id(x) for x in review["reviewer_ids"])
        and len(set(review["reviewer_ids"])) == len(review["reviewer_ids"])
        and type(review["reason"]) is str
        and bool(review["reason"]),
        "invalid review policy",
    )
    require(
        type(review["required_image_ids"]) is list
        and all(valid_id(x) for x in review["required_image_ids"])
        and len(set(review["required_image_ids"])) == len(review["required_image_ids"]),
        "invalid required images",
    )
    require(
        not review["required"] or bool(review["reviewer_ids"]), "required review needs reviewers"
    )
    require(
        value["policy_baseline"] is None or type(value["policy_baseline"]) is str,
        "policy baseline reference must be a string or null",
    )
    require(
        value["policy_baseline"] is None
        or value["policy_baseline"] in {r["id"] for r in source["files"]},
        "policy baseline must be a frozen source reference",
    )


@dataclass(frozen=True, slots=True)
class Contract:
    raw: Mapping[str, Any]
    digest: str
    byte_sha256: str = ""

    def __post_init__(self) -> None:
        value = thaw(self.raw)
        validate_document(value)
        expected = digest("contract.v2", value)
        require(self.digest == expected, "Contract digest inconsistent with fields")
        object.__setattr__(self, "raw", freeze(value))

    @property
    def artifact_kind(self) -> Any:
        return self.raw["artifact_kind"]

    @property
    def na_check_ids(self) -> Any:
        return self.raw["na_check_ids"]

    @property
    def required_isolation_grade(self) -> Any:
        return self.raw["required_isolation_grade"]

    def allowlisted(self, check_id: Any, code: Any, tool_id: Any, version: Any) -> Any:
        target = {
            "check_id": check_id,
            "warning_code": code,
            "tool_id": tool_id,
            "tool_version": version,
        }
        return any(dict(row) == target for row in self.raw["warning_allowlist"])


def load_contract(path: Path, *, candidate_root: Path) -> Contract:
    candidate_root = candidate_root.expanduser().absolute()
    path = path.expanduser().absolute()
    require(
        ".." not in candidate_root.parts and ".." not in path.parts,
        "managed paths cannot contain '..'",
    )
    try:
        candidate_owner = candidate_root.resolve(strict=False)
        path_owner = path.resolve(strict=True)
        require(
            not path_is_within(path_owner, candidate_owner),
            "contract must live outside candidate input tree",
        )
        raw = read_bounded(path, _MAX_CONTRACT_BYTES)
        value: Any = strict_json_loads(raw.decode("utf-8"))
        validate_document(value)
        return Contract(value, digest("contract.v2", value), hashlib.sha256(raw).hexdigest())
    except AcceptanceFailure as exc:
        raise AcceptanceFailure("contract_invalid", str(exc)) from exc
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise AcceptanceFailure("contract_invalid", str(exc)) from exc


_BASELINE_FIELDS = {
    "tools",
    "warning_allowlist",
    "budget",
    "limits",
    "review",
    "native",
    "interchange",
}


def enforce_baseline(contract: Contract, input_files: Mapping[str, Any]) -> None:
    reference = contract.raw["policy_baseline"]
    if reference is None:
        return
    descriptor = next(row for row in contract.raw["input"]["files"] if row["id"] == reference)
    bound = input_files[reference]
    if (
        bound.id != reference
        or bound.bytes != descriptor["bytes"]
        or bound.sha256 != descriptor["sha256"]
    ):
        raise AcceptanceFailure("hash_mismatch", "baseline source identity differs from contract")
    raw = read_bounded(bound.path, _MAX_CONTRACT_BYTES)
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    if len(raw) != descriptor["bytes"] or raw_sha256 != descriptor["sha256"]:
        raise AcceptanceFailure("hash_mismatch", "baseline bytes do not match frozen source identity")
    baseline: Any = strict_json_loads(raw.decode("utf-8"))
    fields(baseline, {"schema_version", "kind", "constraints"}, "baseline")
    require(
        type(baseline["schema_version"]) is int
        and baseline["schema_version"] == 2
        and baseline["kind"] == "acceptance_policy_baseline",
        "invalid baseline version/kind",
    )
    fields(baseline["constraints"], _BASELINE_FIELDS, "baseline constraints")
    expected = {key: thaw(contract.raw[key]) for key in _BASELINE_FIELDS}
    require(
        canonicalize(baseline["constraints"]) == canonicalize(expected),
        "policy differs from frozen deployment baseline; create a newly authorized baseline and run",
    )
