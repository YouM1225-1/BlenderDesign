from __future__ import annotations

from pathlib import Path
from typing import Any

from acceptance.contract import Contract, thaw
from acceptance.decide import Finding, Gate
from acceptance.native_plan import NATIVE_GATES
from acceptance.native_policy import PASSES, VIEWS, finite_number
from acceptance.primitives import AcceptanceFailure
from acceptance.strict_json import strict_json_loads


def load(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise AcceptanceFailure("tool_output_invalid", "Native JSON exceeds bound")
        value = strict_json_loads(raw)
    except (OSError, ValueError) as exc:
        raise AcceptanceFailure(
            "tool_output_invalid", "Native JSON unreadable or malformed"
        ) from exc
    if not isinstance(value, dict):
        raise AcceptanceFailure("tool_output_invalid", "Native JSON object required")
    return value


def closed(value: Any, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise AcceptanceFailure("tool_output_invalid", "Native report closed fields mismatch")


def strings(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AcceptanceFailure("tool_output_invalid", "Native scope gaps must be a string list")
    return value


def report_findings(value: Any) -> list[Finding]:
    if not isinstance(value, list):
        raise AcceptanceFailure("tool_output_invalid", "Native findings list required")
    findings = []
    for row in value:
        closed(row, {"code", "severity", "pointer", "detail"})
        if (
            not isinstance(row["code"], str)
            or not isinstance(row["detail"], str)
            or row["severity"] != "error"
            or row["pointer"] is not None
        ):
            raise AcceptanceFailure("tool_output_invalid", "Native finding malformed")
        findings.append(Finding(**row))
    return findings


def bounded_number(value: Any, maximum: int) -> None:
    try:
        finite_number(value)
    except ValueError as exc:
        raise AcceptanceFailure(
            "tool_output_invalid", "Native measurement number malformed"
        ) from exc
    if not 0 <= value <= maximum:
        raise AcceptanceFailure("tool_output_invalid", "Native measurement outside bounds")


def native_results(
    contract: Contract, run: Any
) -> tuple[dict[str, list[Finding]], dict[str, Gate]]:
    policy = thaw(contract.raw["native"])
    gates = {key: Gate(False, ()) for key in NATIVE_GATES}
    findings: dict[str, list[Finding]] = {}
    if "r4.visual.self_determinism" in run.findings:
        findings["r4.visual.self_determinism"] = [
            Finding("repeat_unverified", "error", detail="Comparison evidence unavailable")
        ]
    gaps = None
    if "native.manifest" in run.files:
        manifest = load(run.files["native.manifest"].path)
        gaps = strings(manifest.get("scope_gaps"))
        gates["native.scope_supported"] = Gate(
            not gaps, tuple(Finding("capability_gap", "error", detail=x) for x in gaps)
        )
    if "native.comparisons" not in run.files:
        return findings, gates
    data = load(run.files["native.comparisons"].path)
    closed(
        data,
        {
            "schema_version",
            "comparisons",
            "reference_findings",
            "geometry_findings",
            "scope_gaps",
            "platform",
        },
    )
    if type(data["schema_version"]) is not int or data["schema_version"] != 2:
        raise AcceptanceFailure("tool_output_invalid", "Comparison schema version mismatch")
    if not isinstance(data["comparisons"], list):
        raise AcceptanceFailure("tool_output_invalid", "Comparisons list required")
    reference = report_findings(data["reference_findings"])
    # Geometry adjudication belongs to the inspector; this copy still has a closed wire shape.
    report_findings(data["geometry_findings"])
    strings(data["scope_gaps"])
    if gaps is None or data["scope_gaps"] != gaps:
        raise AcceptanceFailure(
            "tool_output_invalid", "Comparison scope differs from source manifest"
        )
    closed(data["platform"], {"blender", "build", "decoder", "execution"})
    if any(not isinstance(v, str) or not v for v in data["platform"].values()):
        raise AcceptanceFailure("tool_output_invalid", "Comparator platform strings required")
    expected_platform = {
        "blender": policy["render"]["platform"]["blender"],
        "build": policy["render"]["platform"]["build"],
        "decoder": "blender-rgba-f32-v1",
        "execution": "cpu-image-decode",
    }
    platform_findings = [
        Finding("unknown_platform", "error", detail="Comparator platform differs: " + field)
        for field, value in expected_platform.items()
        if data["platform"][field] != value
    ]
    expected = {
        (g, v, p)
        for g in ("same", "fresh", "reference")
        for v in VIEWS
        for p in PASSES
        if not (g == "same" and p == "beauty")
    }
    actual = []
    same: list[Finding] = []
    fresh: list[Finding] = []
    input_hashes = {row["id"]: row["sha256"] for row in contract.raw["input"]["files"]}
    input_hashes.update({fid: item.sha256 for fid, item in run.files.items()})
    energy_by_id: dict[str, int | float] = {}
    energy_by_hash: dict[str, int | float] = {}
    fields = {
        "decoder",
        "size",
        "channels",
        "precision",
        "color_interpretation",
        "left_bytes_sha256",
        "right_bytes_sha256",
        "different_channels",
        "different_pixels",
        "max_abs",
        "group",
        "view",
        "pass",
        "left_id",
        "right_id",
        "diff_id",
        "left_rgb_energy",
        "right_rgb_energy",
    }
    identity_fields = {
        "decoder",
        "precision",
        "color_interpretation",
        "group",
        "view",
        "pass",
        "left_id",
        "right_id",
        "diff_id",
        "left_bytes_sha256",
        "right_bytes_sha256",
    }
    for item in data["comparisons"]:
        closed(item, fields)
        if any(not isinstance(item[field], str) for field in identity_fields):
            raise AcceptanceFailure("tool_output_invalid", "Comparison identity strings required")
        key = (item["group"], item["view"], item["pass"])
        actual.append(key)
        if (
            key not in expected
            or item["decoder"] != "blender-rgba-f32-v1"
            or item["precision"] != "float32"
            or type(item["channels"]) is not int
            or item["channels"] != 4
            or item["color_interpretation"] != "Blender PNG decode, Standard output"
            or not isinstance(item["size"], list)
            or any(type(value) is not int for value in item["size"])
            or item["size"] != [1024, 1024]
        ):
            raise AcceptanceFailure("tool_output_invalid", "Comparison identity/format mismatch")
        for metric in ("different_channels", "different_pixels"):
            if (
                type(item[metric]) is not int
                or not 0
                <= item[metric]
                <= (4 if metric == "different_channels" else 1) * 1024 * 1024
            ):
                raise AcceptanceFailure("tool_output_invalid", "Comparison count malformed")
        bounded_number(item["max_abs"], 1)
        group, view, render_pass = key
        expected_left = (
            f"image.fresh_a.0.{view}.{render_pass}"
            if group == "fresh"
            else f"image.same_process.0.{view}.{render_pass}"
        )
        expected_right = (
            f"image.same_process.1.{view}.{render_pass}"
            if group == "same"
            else f"image.fresh_b.0.{view}.{render_pass}"
            if group == "fresh"
            else policy["render"]["reference_images"][view + "." + render_pass]
        )
        if (item["left_id"], item["right_id"], item["diff_id"]) != (
            expected_left,
            expected_right,
            f"diff.{group}.{view}.{render_pass}",
        ):
            raise AcceptanceFailure("tool_output_invalid", "Comparison paired the wrong artifacts")
        zero_difference = item["max_abs"] == 0
        if zero_difference != (item["different_channels"] == 0) or not (
            item["different_pixels"] <= item["different_channels"] <= 4 * item["different_pixels"]
        ):
            raise AcceptanceFailure(
                "tool_output_invalid", "Comparison metrics contradict one another"
            )
        for side in ("left", "right"):
            energy = item[side + "_rgb_energy"]
            bounded_number(energy, 3 * 1024 * 1024)
            fid, digest = item[side + "_id"], item[side + "_bytes_sha256"]
            if fid not in input_hashes or digest != input_hashes[fid]:
                raise AcceptanceFailure(
                    "tool_output_invalid", "Comparison input byte identity mismatch"
                )
            if (
                energy_by_id.setdefault(fid, energy) != energy
                or energy_by_hash.setdefault(digest, energy) != energy
            ):
                raise AcceptanceFailure("tool_output_invalid", "Repeated input RGB energy differs")
        if (
            zero_difference
            and item["left_rgb_energy"] != item["right_rgb_energy"]
            or item["left_bytes_sha256"] == item["right_bytes_sha256"]
            and not zero_difference
        ):
            raise AcceptanceFailure(
                "tool_output_invalid", "Decoded measurements contradict byte identity"
            )
        if item["diff_id"] not in run.files:
            raise AcceptanceFailure("tool_output_invalid", "Required difference image missing")
        hard = render_pass != "beauty" or policy["render"]["beauty_hard_gate"]
        if hard and item["max_abs"] > policy["render"]["max_abs"][render_pass]:
            target = same if group == "same" else fresh if group == "fresh" else reference
            target.append(
                Finding("pixel_mismatch", "error", detail=repr(key) + ":" + str(item["max_abs"]))
            )
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise AcceptanceFailure(
            "tool_output_invalid", "Comparison pair set differs from frozen plan"
        )
    for experiment in ("same_process", "fresh_a", "fresh_b"):
        if "render." + experiment not in run.files:
            raise AcceptanceFailure("tool_output_invalid", "Required render report missing")
        report = load(run.files["render." + experiment].path)
        closed(
            report,
            {
                "schema_version",
                "platform",
                "settings",
                "images",
                "source_digest_before",
                "source_digest_after",
            },
        )
        if (
            type(report["schema_version"]) is not int
            or report["schema_version"] != 2
            or not isinstance(report["settings"], dict)
            or report["settings"] != policy["render"]
            or not isinstance(report["platform"], dict)
            or any(not isinstance(v, str) for v in report["platform"].values())
            or not isinstance(report["images"], list)
        ):
            raise AcceptanceFailure("tool_output_invalid", "Render report schema/settings mismatch")
        if report["platform"] != policy["render"]["platform"]:
            platform_findings.append(
                Finding(
                    "unknown_platform", "error", detail="Render platform differs: " + experiment
                )
            )
        for field in ("source_digest_before", "source_digest_after"):
            if not isinstance(report[field], str):
                raise AcceptanceFailure("tool_output_invalid", "Source digest string required")
            if report[field] != input_hashes["asset"]:
                raise AcceptanceFailure("toolchain_mismatch", "Source changed during render")
        observations = [
            row for row in run.jobs if row.get("job_id") == "native.render." + experiment
        ]
        if len(observations) != 1:
            raise AcceptanceFailure("tool_output_invalid", "Unique observed render job required")
        observation = observations[0]
        if (
            observation.get("started") is not True
            or not isinstance(observation.get("started_at"), str)
            or not observation["started_at"]
            or type(observation.get("pid")) is not int
            or observation["pid"] <= 0
        ):
            raise AcceptanceFailure(
                "tool_output_invalid", "Observed render process identity missing"
            )
        ids = []
        for image in report["images"]:
            closed(image, {"id", "view", "pass", "repetition", "pid", "experiment", "engine"})
            if (
                any(
                    not isinstance(image[field], str)
                    for field in ("id", "view", "pass", "experiment", "engine")
                )
                or type(image["repetition"]) is not int
                or image["repetition"] not in range(2 if experiment == "same_process" else 1)
                or type(image["pid"]) is not int
                or image["pid"] <= 0
                or image["pid"] != observation["pid"]
                or image["experiment"] != experiment
                or image["view"] not in VIEWS
                or image["pass"] not in PASSES
                or image["id"]
                != f"image.{experiment}.{image['repetition']}.{image['view']}.{image['pass']}"
                or image["engine"]
                != ("BLENDER_EEVEE" if image["pass"] == "beauty" else "BLENDER_WORKBENCH")
            ):
                raise AcceptanceFailure(
                    "tool_output_invalid", "Image identity/engine/process metadata mismatch"
                )
            ids.append(image["id"])
        expected_ids = {
            f"image.{experiment}.{r}.{v}.{p}"
            for r in range(2 if experiment == "same_process" else 1)
            for v in VIEWS
            for p in PASSES
            if not (r == 1 and p == "beauty")
        }
        if (
            len(ids) != len(set(ids))
            or set(ids) != expected_ids
            or any(fid not in run.files for fid in ids)
        ):
            raise AcceptanceFailure(
                "tool_output_invalid", "Render report does not cover full image set"
            )
    if "r4.visual.self_determinism" not in run.findings:
        raise AcceptanceFailure(
            "tool_output_invalid", "Comparison has no completed source render writer"
        )
    fresh_complete = reference_complete = not platform_findings
    fresh.extend(platform_findings)
    reference.extend(platform_findings)
    for render_pass in ("clay", "silhouette", "wire"):
        # Each actual repetition has its own nine-view foreground aggregate. IDs deduplicate
        # source images reused by same-process and reference comparisons.
        for experiment, repetition in (
            ("same_process", 0),
            ("same_process", 1),
            ("fresh_a", 0),
            ("fresh_b", 0),
        ):
            if (
                sum(
                    energy_by_id[f"image.{experiment}.{repetition}.{view}.{render_pass}"]
                    for view in VIEWS
                )
                <= 0
            ):
                failure = Finding(
                    "diagnostic_render_empty",
                    "error",
                    detail=f"{experiment}.{repetition}.{render_pass}",
                )
                findings.setdefault("r4.visual.scene_not_empty", []).append(failure)
                if experiment != "same_process":
                    fresh_complete = False
                    fresh.append(failure)
        if (
            sum(
                energy_by_id[policy["render"]["reference_images"][view + "." + render_pass]]
                for view in VIEWS
            )
            <= 0
        ):
            reference_complete = False
            reference.append(Finding("reference_diagnostic_empty", "error", detail=render_pass))
    findings["r4.visual.all_views_rendered"] = []
    findings["r4.visual.self_determinism"] = same
    gates["native.cross_process"] = Gate(fresh_complete, tuple(fresh))
    gates["native.reference"] = Gate(reference_complete, tuple(reference))
    return findings, gates
