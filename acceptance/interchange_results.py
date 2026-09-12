from __future__ import annotations

import json
from typing import Any

from acceptance.contract import thaw
from acceptance.decide import Finding, Gate
from acceptance.glb_budget import measure_glb
from acceptance.interchange_policy import validate_interchange_policy
from acceptance.native_policy import PASSES, VIEWS
from acceptance.native_results import load, native_results, bounded_number
from acceptance.primitives import AcceptanceFailure
from acceptance.projection import compare_projection

GLB_CHECKS = (
    "r3.validator.no_error",
    "r3.validator.resources_read",
    "r3.validator.report_complete",
    "r3.extension.none_forbidden",
    "r4.projection.preserved_fields_match",
    "r4.projection.transformed_within_tolerance",
    "r4.projection.undeclared_loss",
    "r4.projection.ambiguous_object_names",
    "r4.visual.source_import_match",
)


def validate_export_evidence(
    value: Any,
    source: Any,
    native: Any,
    *,
    source_sha256: Any,
    delivery_sha256: Any,
    preset: Any,
) -> Any:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "source_before",
            "source_after",
            "delivery_sha256",
            "exported_ids",
            "preset",
        }
        or type(value["schema_version"]) is not int
        or (value["schema_version"] != 2)
    ):
        raise AcceptanceFailure("tool_output_invalid", "export measurement schema mismatch")
    if (
        value["source_before"] != value["source_after"]
        or value["source_before"] != source_sha256
        or value["delivery_sha256"] != delivery_sha256
    ):
        raise AcceptanceFailure("tool_output_invalid", "export byte identity mismatch")
    if (
        not isinstance(value["preset"], dict)
        or value["preset"] != preset
        or any(type(value["preset"][key]) is not type(expected) for key, expected in preset.items())
    ):
        raise AcceptanceFailure("tool_output_invalid", "export preset differs from frozen policy")
    ids = [obj["id"] for obj in source["objects"]]
    expected = [row["source"] for row in native["occurrences"]]

    def encode(rows: list[Any]) -> list[str]:
        return sorted(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in rows)

    if (
        value["exported_ids"] != ids
        or len(encode(ids)) != len(set(encode(ids)))
        or encode(ids) != encode(expected)
    ):
        raise AcceptanceFailure(
            "tool_output_invalid", "export occurrence set differs from inspected source"
        )


def resources_read(
    resources: Any, report: Any, budget: Any, policy: Any, *, input_sha256: str, input_bytes: int
) -> bool:
    """Shared pre-import safety and final-controller resource evidence predicate."""

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise AcceptanceFailure("tool_output_invalid", message)

    require(
        isinstance(resources, dict)
        and set(resources)
        == {"schema_version", "input_sha256", "input_bytes", "external_requests", "resources"}
        and type(resources["schema_version"]) is int
        and resources["schema_version"] == 2,
        "resource report schema mismatch",
    )
    require(
        type(resources["input_bytes"]) is int
        and resources["input_bytes"] == input_bytes
        and resources["input_sha256"] == input_sha256,
        "validator read different delivery bytes",
    )
    info = report.get("info", {})
    require(isinstance(info, dict), "validator resource info malformed")
    require(
        resources["resources"] == info.get("resources", []),
        "resource log differs from validator report",
    )
    rows = resources["resources"]
    require(
        isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
        "resource rows required",
    )
    requests = resources["external_requests"]
    require(
        isinstance(requests, list) and all(isinstance(x, str) for x in requests),
        "external resource requests malformed",
    )
    pointers = [row.get("pointer") for row in rows]
    require(all(isinstance(x, str) for x in pointers), "resource pointers malformed")

    def read(row: Any) -> bool:
        if row["pointer"].startswith("/buffers/"):
            return (
                row.get("storage") == "glb"
                and type(row.get("byteLength")) is int
                and row["byteLength"] > 0
            )
        image = row.get("image")
        return (
            row["pointer"].startswith("/images/")
            and row.get("storage") == "buffer-view"
            and row.get("mimeType") == "image/png"
            and isinstance(image, dict)
            and all(type(image.get(k)) is int and image[k] > 0 for k in ("width", "height"))
            and type(image.get("bits")) is int
            and image["bits"] == 8
            and image["width"] * image["height"] <= policy["limits"]["max_texture_pixels"]
        )

    return (
        not requests
        and len(pointers) == len(set(pointers))
        and set(pointers) == set(budget["resource_pointers"])
        and all(read(row) for row in rows)
    )


def interchange_results(contract: Any, run: Any) -> Any:
    (findings, gates) = native_results(contract, run)
    policy = thaw(contract.raw["interchange"])
    validate_interchange_policy(policy)
    gates.update(
        {
            "interchange.scope_supported": Gate(False, ()),
            "interchange.consumer": Gate(
                policy["consumer"] is None,
                ()
                if policy["consumer"] is None
                else (Finding("consumer_adapter_missing", "error", detail=policy["consumer"]),),
            ),
        }
    )

    def require(condition: Any, message: Any) -> Any:
        if not condition:
            raise AcceptanceFailure("tool_output_invalid", message)

    if "export.measurements" in run.files:
        require(
            all(k in run.files for k in ("projection.source", "native.manifest", "delivery.glb")),
            "incomplete export identity evidence",
        )
        source_sha = next(
            row["sha256"] for row in contract.raw["input"]["files"] if row["id"] == "asset"
        )
        validate_export_evidence(
            load(run.files["export.measurements"].path),
            load(run.files["projection.source"].path),
            load(run.files["native.manifest"].path),
            source_sha256=source_sha,
            delivery_sha256=run.files["delivery.glb"].sha256,
            preset=policy["preset"],
        )
    if all(
        k in run.files
        for k in (
            "validator.report",
            "validator.resources",
            "glb.budget",
            "delivery.glb",
        )
    ):
        report = load(run.files["validator.report"].path)
        require(
            set(report) <= {"uri", "mimeType", "validatorVersion", "issues", "info"}
            and {"uri", "mimeType", "validatorVersion", "issues"} <= set(report),
            "validator top-level schema mismatch",
        )
        require(
            report["uri"] == "delivery.glb"
            and report["mimeType"] == "model/gltf-binary"
            and (report["validatorVersion"] == policy["validator_version"]),
            "validator identity mismatch",
        )
        issues = report["issues"]
        require(
            isinstance(issues, dict)
            and set(issues)
            == {
                "numErrors",
                "numWarnings",
                "numInfos",
                "numHints",
                "messages",
                "truncated",
            },
            "validator issues schema mismatch",
        )
        require(
            type(issues["truncated"]) is bool and isinstance(issues["messages"], list),
            "validator report completeness malformed",
        )
        counts = [issues[k] for k in ("numErrors", "numWarnings", "numInfos", "numHints")]
        require(all(type(n) is int and n >= 0 for n in counts), "validator counts malformed")
        actual = [0] * 4
        asset_findings = []
        for item in issues["messages"]:
            require(
                isinstance(item, dict)
                and {"code", "message", "severity"} <= set(item)
                and (set(item) <= {"code", "message", "severity", "pointer", "offset"}),
                "validator message schema mismatch",
            )
            severity = item["severity"]
            require(
                type(severity) is int and 0 <= severity <= 3,
                "validator severity malformed",
            )
            require(
                isinstance(item["code"], str) and isinstance(item["message"], str),
                "validator message text malformed",
            )
            actual[severity] += 1
            if severity < 2:
                asset_findings.append(
                    Finding("validator_" + item["code"], "error", detail=item["message"])
                )
        require(
            issues["truncated"] or actual == counts,
            "validator issue counts inconsistent",
        )
        findings["r3.validator.no_error"] = asset_findings
        findings["r3.validator.report_complete"] = (
            [] if not issues["truncated"] else [Finding("validator_truncated", "error")]
        )
        budget = measure_glb(run.files["delivery.glb"].path, policy["limits"])
        require(
            load(run.files["glb.budget"].path) == budget,
            "budget report differs from controller remeasurement",
        )
        findings["r3.extension.none_forbidden"] = [
            Finding("forbidden_extension", "error", detail=x)
            for x in budget["extensions"]
            if x not in policy["allowed_extensions"]
        ]
        all_read = resources_read(
            load(run.files["validator.resources"].path),
            report,
            budget,
            policy,
            input_sha256=run.files["delivery.glb"].sha256,
            input_bytes=run.files["delivery.glb"].bytes,
        )
        findings["r3.validator.resources_read"] = (
            [] if all_read else [Finding("resources_not_proven_read", "error")]
        )
    if all(
        k in run.files for k in ("projection.source", "projection.import", "projection.matches")
    ):
        measured = compare_projection(
            load(run.files["projection.source"].path),
            load(run.files["projection.import"].path),
            policy,
        )
        require(
            load(run.files["projection.matches"].path) == measured,
            "surface report differs from trusted comparator",
        )
        for group, check in [
            ("preserved", "r4.projection.preserved_fields_match"),
            ("transformed", "r4.projection.transformed_within_tolerance"),
            ("loss", "r4.projection.undeclared_loss"),
            ("ambiguous", "r4.projection.ambiguous_object_names"),
        ]:
            findings[check] = [
                Finding("projection_" + group, "error", detail=x) for x in measured[group]
            ]
        gates["interchange.scope_supported"] = Gate(True, ())
    if "projection.visual" not in run.files:
        return (findings, gates)
    data = load(run.files["projection.visual"].path)
    require(
        set(data) == {"schema_version", "comparisons"}
        and type(data["schema_version"]) is int
        and data["schema_version"] == 2
        and isinstance(data["comparisons"], list),
        "projection visual schema mismatch",
    )
    seen = []
    energy_by_hash: dict[str, int | float] = {}
    failures = []
    energy = {side: {p: 0.0 for p in ("clay", "silhouette", "wire")} for side in ("left", "right")}
    for row in data["comparisons"]:
        require(
            isinstance(row, dict)
            and set(row)
            == {
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
                "left_rgb_energy",
                "right_rgb_energy",
                "view",
                "pass",
                "left_id",
                "right_id",
                "diff_id",
            },
            "projection visual row schema mismatch",
        )
        (view, render_pass) = (row["view"], row["pass"])
        seen.append((view, render_pass))
        require(
            isinstance(view, str)
            and isinstance(render_pass, str)
            and view in VIEWS
            and render_pass in PASSES,
            "unplanned projection visual pair",
        )
        require(
            (row["left_id"], row["right_id"], row["diff_id"])
            == (
                f"image.projection_source.0.{view}.{render_pass}",
                f"image.projection_import.0.{view}.{render_pass}",
                f"diff.projection.{view}.{render_pass}",
            ),
            "wrong projection image pair",
        )
        require(
            row["color_interpretation"] == "Blender PNG decode, Standard output"
            and row["decoder"] == "blender-rgba-f32-v1"
            and (row["precision"] == "float32")
            and type(row["channels"]) is int
            and (row["channels"] == 4)
            and isinstance(row["size"], list)
            and all(type(v) is int for v in row["size"])
            and (row["size"] == [1024, 1024]),
            "projection decoder mismatch",
        )
        for side in ("left", "right"):
            require(
                row[side + "_id"] in run.files
                and row[side + "_bytes_sha256"] == run.files[row[side + "_id"]].sha256,
                "projection compared different image bytes",
            )
        require(row["diff_id"] in run.files, "missing projection difference image")
        bounded_number(row["max_abs"], 1)
        for side in ("left", "right"):
            value = row[side + "_rgb_energy"]
            bounded_number(value, 3 * 1024 * 1024)
            image_hash = row[side + "_bytes_sha256"]
            require(isinstance(image_hash, str), "projection image hash malformed")
            require(
                image_hash not in energy_by_hash or energy_by_hash[image_hash] == value,
                "same projection bytes have inconsistent decoded energy",
            )
            energy_by_hash[image_hash] = value
            if render_pass in energy[side]:
                energy[side][render_pass] += value
        (dc, dp) = (row["different_channels"], row["different_pixels"])
        require(
            type(dc) is int
            and type(dp) is int
            and (0 <= dp <= 1024 * 1024)
            and (dp <= dc <= 4 * dp)
            and ((dc == 0) == (row["max_abs"] == 0)),
            "projection counts inconsistent",
        )
        require(
            dc != 0 or row["left_rgb_energy"] == row["right_rgb_energy"],
            "zero projection difference has unequal energy",
        )
        require(
            row["left_bytes_sha256"] != row["right_bytes_sha256"] or dc == 0,
            "identical projection bytes have nonzero differences",
        )
        if (
            render_pass in {"clay", "silhouette"}
            and row["max_abs"] > contract.raw["native"]["render"]["max_abs"][render_pass]
        ):
            failures.append(
                Finding(
                    "projection_pixel_mismatch",
                    "error",
                    detail=view + "." + render_pass,
                )
            )
    require(
        len(seen) == len(set(seen)) and set(seen) == {(v, p) for v in VIEWS for p in PASSES},
        "incomplete projection visual set",
    )
    hashes = {x["id"]: x["sha256"] for x in contract.raw["input"]["files"]}
    hashes.update({key: value.sha256 for (key, value) in run.files.items()})
    for experiment, input_id in [
        ("projection_source", "asset"),
        ("projection_import", "delivery.glb"),
    ]:
        require("render." + experiment in run.files, "projection render report missing")
        report = load(run.files["render." + experiment].path)
        require(
            set(report)
            == {
                "schema_version",
                "platform",
                "settings",
                "images",
                "input_sha256_before",
                "input_sha256_after",
            }
            and type(report["schema_version"]) is int
            and report["schema_version"] == 2,
            "projection render schema mismatch",
        )
        require(
            report["settings"] == thaw(contract.raw["native"]["render"])
            and report["platform"] == thaw(contract.raw["native"]["render"]["platform"]),
            "unfrozen projection platform/settings",
        )
        require(
            report["input_sha256_before"] == report["input_sha256_after"] == hashes[input_id],
            "projection rendered changed input",
        )
        processes = [x for x in run.jobs if x["job_id"] == "glb." + experiment]
        require(len(processes) == 1, "unique projection process observation required")
        process = processes[0]
        require(
            process.get("started") is True
            and type(process.get("pid")) is int
            and process["pid"] > 0
            and isinstance(process.get("started_at"), str)
            and bool(process["started_at"]),
            "projection process was not observed started",
        )
        require(isinstance(report["images"], list), "projection images list required")
        ids = []
        for row in report["images"]:
            require(
                isinstance(row, dict)
                and set(row) == {"id", "view", "pass", "repetition", "pid", "experiment", "engine"},
                "projection image metadata malformed",
            )
            require(
                isinstance(row["id"], str)
                and isinstance(row["view"], str)
                and isinstance(row["pass"], str)
                and row["view"] in VIEWS
                and row["pass"] in PASSES
                and row["id"] == f"image.{experiment}.0.{row['view']}.{row['pass']}"
                and row["experiment"] == experiment
                and (
                    row["engine"]
                    == ("BLENDER_EEVEE" if row["pass"] == "beauty" else "BLENDER_WORKBENCH")
                )
                and (type(row["repetition"]) is int)
                and (row["repetition"] == 0)
                and process["started"]
                and type(row["pid"]) is int
                and row["pid"] > 0
                and (row["pid"] == process["pid"]),
                "projection image process mismatch",
            )
            ids.append(row["id"])
        require(
            len(ids) == len(set(ids))
            and set(ids) == {f"image.{experiment}.0.{v}.{p}" for v in VIEWS for p in PASSES},
            "projection render image set mismatch",
        )
    for side in energy:
        for render_pass, value in energy[side].items():
            if value <= 0:
                failures.append(
                    Finding(
                        "empty_projection_diagnostic",
                        "error",
                        detail=side + "." + render_pass,
                    )
                )
    findings["r4.visual.source_import_match"] = failures
    return (findings, gates)
