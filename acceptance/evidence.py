from __future__ import annotations

from typing import Any, cast

import datetime
import os
import secrets
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from acceptance.contract import Contract, load_contract, thaw
from acceptance.controller import (
    RunResult,
    collect_verdict,
    unproduced_files,
    _files_under,
    _family,
    REPO_ROOT,
)
from acceptance.decide import Finding, Gate, decide_technical
from acceptance.input_bundle import BoundFile, measure_file, read_bounded, verify_bundle
from acceptance.plan import RunPlan
from acceptance.primitives import AcceptanceFailure, write_json_exclusive
from acceptance.strict_json import strict_json_loads
from acceptance.toolchain import verify_tools


def _write(path: Path, value: object) -> BoundFile:
    temporary = path.parent / (".control-" + secrets.token_hex(16))
    write_json_exclusive(temporary, value)
    fd = os.open(temporary, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    # link is atomic and refuses an existing final name; unlike replace it never overwrites evidence.
    os.link(temporary, path, follow_symlinks=False)
    temporary.unlink()
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return measure_file(path, 64 * 1024 * 1024, file_id="control")


def _json(path: Path) -> Any:
    return strict_json_loads(read_bounded(path, 64 * 1024 * 1024).decode("utf-8"))


def _identity(path: Path) -> str:
    return measure_file(path, 64 * 1024 * 1024, file_id="control").sha256


def finalize_run(
    contract: Contract,
    plan: RunPlan,
    run: RunResult,
    *,
    contract_path: Path,
    source_root: Path,
    evidence_root: Path,
    delivery: BoundFile | None,
    coordinator_findings: Mapping[str, list[Finding]],
    gates: Mapping[str, Gate],
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = evidence_root / "payload"
    gate_rows = {key: asdict(value) for key, value in gates.items()}
    gate_path = payload / "gates.json"
    _write(
        gate_path,
        {"schema_version": 2, "expected_gate_ids": list(plan.gate_ids), "gates": gate_rows},
    )
    planned = {f.id: f for f in plan.files}
    run.files["gates"] = measure_file(gate_path, planned["gates"].max_bytes, file_id="gates")
    extra = {key: list(value) for key, value in coordinator_findings.items()}
    r5: dict[str, list[Finding]] = {
        "r5.evidence.manifest_closed": [],
        "r5.evidence.hashes_match": [],
        "r5.contract.digest_stable": [],
    }
    failures = list(run.infra_failures)
    try:
        current_contract = load_contract(contract_path, candidate_root=source_root)
        if (
            current_contract.digest != contract.digest
            or current_contract.byte_sha256 != contract.byte_sha256
        ):
            raise AcceptanceFailure(
                "hash_mismatch", "contract file changed after execution snapshot"
            )
        verify_bundle(
            source_root,
            thaw(contract.raw["input"]["files"]),
            max_file_bytes=contract.raw["budget"]["max_file_bytes"],
        )
        current_tools = verify_tools(contract, plan.required_tools, REPO_ROOT)
        if current_tools != run.measurements.get("tools"):
            raise AcceptanceFailure("toolchain_mismatch", "tool identities changed during run")
        if delivery is None or delivery.bytes <= 0:
            raise AcceptanceFailure("evidence_missing", "no nonempty checked delivery was produced")
        measured_delivery = measure_file(
            delivery.path, contract.raw["budget"]["max_file_bytes"], file_id=delivery.id
        )
        if (measured_delivery.bytes, measured_delivery.sha256) != (delivery.bytes, delivery.sha256):
            raise AcceptanceFailure("hash_mismatch", "delivery changed after checks")
    except Exception as exc:
        failures.append(_family(exc))
        r5["r5.contract.digest_stable"].append(Finding("identity_drift", "error", detail=str(exc)))
    rows = []
    actual_paths = _files_under(payload)
    expected_paths = {spec.path for spec in plan.files}
    unproduced = unproduced_files(plan, run)
    blocked_paths = {row["path"] for row in unproduced.values()}
    if actual_paths != expected_paths - blocked_paths or set(run.files) != set(planned) - set(
        unproduced
    ):
        failures.append("expected_set_mismatch")
        r5["r5.evidence.manifest_closed"].append(Finding("file_set_mismatch", "error"))
    total = 0
    for file_id, spec in sorted(planned.items()):
        path = payload / spec.path
        if not path.exists():
            continue
        try:
            measured = measure_file(path, spec.max_bytes, file_id=file_id)
            previous = run.files.get(file_id)
            if previous is None or (measured.bytes, measured.sha256) != (
                previous.bytes,
                previous.sha256,
            ):
                raise AcceptanceFailure("hash_mismatch", "payload changed after acceptance")
            total += measured.bytes
            rows.append(
                measured.descriptor(spec.path)
                | {"writer": spec.writer, "media_type": spec.media_type}
            )
        except Exception as exc:
            failures.append(_family(exc))
            r5["r5.evidence.hashes_match"].append(
                Finding("payload_identity_invalid", "error", detail=str(exc))
            )
    if total > contract.raw["budget"]["max_total_bytes"]:
        failures.append("resource_limit_exceeded")
    run.infra_failures = tuple(failures)
    for key, findings in r5.items():
        if key in extra:
            raise AcceptanceFailure(
                "tool_output_invalid", "R5 is controller-owned and cannot be supplied"
            )
        if key == "r5.evidence.manifest_closed" and unproduced and not findings:
            continue  # Required products did not run: this check remains NotTested, never a fabricated R5 Pass.
        extra[key] = findings
    manifest = {
        "schema_version": 2,
        "C": contract.digest,
        "S": contract.raw["input"]["sha256"],
        "files": rows,
        "missing": sorted(expected_paths - actual_paths),
        "unproduced": [unproduced[key] for key in sorted(unproduced)],
        "unknown": sorted(actual_paths - expected_paths),
    }
    e = _write(evidence_root / "evidence-manifest.json", manifest)
    base = collect_verdict(contract, plan, run, coordinator_findings=extra)
    verdict = decide_technical(base, expected_gate_ids=plan.gate_ids, gates=gates)
    _write(evidence_root / "contract.json", thaw(contract.raw))
    summary = {
        "schema_version": 2,
        "kind": "asset_acceptance",
        "success": verdict.success,
        "C": contract.digest,
        "S": contract.raw["input"]["sha256"],
        "D": None
        if delivery is None
        else {"id": delivery.id, "bytes": delivery.bytes, "sha256": delivery.sha256},
        "E": e.sha256,
        "checks": [asdict(o) for o in verdict.outcomes],
        "gates": gate_rows,
        "expected_gate_ids": list(plan.gate_ids),
        "failure_code": verdict.failure_code,
        "failed_check_ids": list(verdict.failed_check_ids),
        "failed_gate_ids": list(verdict.failed_gate_ids),
        "infra_failures": list(run.infra_failures),
        "review_policy": thaw(contract.raw["review"]),
        "advisories": ["L0 has no deployment policy baseline"]
        if contract.raw["policy_baseline"] is None
        else [],
        "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    v = _write(evidence_root / "summary.json", summary)
    bindings = {
        "C": summary["C"],
        "S": summary["S"],
        "D": None if delivery is None else delivery.sha256,
        "E": e.sha256,
        "V": v.sha256,
    }
    if verdict.success and contract.raw["review"]["required"] and review is None:
        return {"schema_version": 2, "state": "NEEDS_REVIEW", "bindings": bindings}
    return _seal(
        evidence_root, summary, bindings, None if delivery is None else delivery.path, review
    )


def _validate_review(
    review: dict[str, Any],
    bindings: dict[str, Any],
    policy: dict[str, Any],
    manifest: dict[str, Any],
) -> bool:
    if (
        type(review) is not dict
        or set(review) != {"schema_version", "bindings", "records"}
        or type(review["schema_version"]) is not int
        or review["schema_version"] != 2
        or review["bindings"] != bindings
        or type(review["records"]) is not list
    ):
        raise AcceptanceFailure("tool_output_invalid", "review is not bound to this evidence")
    records = review["records"]
    if any(type(r) is not dict or type(r.get("reviewer_id")) is not str for r in records):
        raise AcceptanceFailure("tool_output_invalid", "reviewer ids must be strings")
    ids = [r["reviewer_id"] for r in records]
    if len(set(ids)) != len(records) or set(ids) != set(policy["reviewer_ids"]):
        raise AcceptanceFailure("tool_output_invalid", "reviewer set is incomplete or unauthorized")
    images = {r["id"]: r["sha256"] for r in manifest["files"] if r["media_type"] == "image/png"}
    for row in records:
        if set(row) != {"reviewer_id", "outcome", "reviewed_images", "reviewed_at", "note"}:
            raise AcceptanceFailure("tool_output_invalid", "closed review record required")
        if row["outcome"] not in ("approved", "rejected") or type(row["note"]) is not str:
            raise AcceptanceFailure("tool_output_invalid", "invalid review outcome")
        if type(row["reviewed_at"]) is not str:
            raise AcceptanceFailure("tool_output_invalid", "review timestamp must be a string")
        try:
            parsed = datetime.datetime.fromisoformat(row["reviewed_at"])
        except ValueError as exc:
            raise AcceptanceFailure("tool_output_invalid", "invalid review timestamp") from exc
        if parsed.tzinfo is None or type(row["reviewed_images"]) is not list:
            raise AcceptanceFailure("tool_output_invalid", "review timestamp/images invalid")
        viewed = {}
        for image in row["reviewed_images"]:
            if (
                type(image) is not dict
                or set(image) != {"id", "sha256"}
                or type(image["id"]) is not str
                or image["id"] in viewed
            ):
                raise AcceptanceFailure("tool_output_invalid", "invalid reviewed image")
            if images.get(image["id"]) != image["sha256"]:
                raise AcceptanceFailure("hash_mismatch", "reviewed image identity mismatch")
            viewed[image["id"]] = image["sha256"]
        if not set(policy["required_image_ids"]) <= set(viewed):
            raise AcceptanceFailure("evidence_missing", "required review images not reviewed")
    return all(row["outcome"] == "approved" for row in records)


def _seal(
    root: Path,
    summary: dict[str, Any],
    bindings: dict[str, Any],
    delivery_path: Path | None,
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest = _json(root / "evidence-manifest.json")
    policy = summary["review_policy"]
    complete = (
        all(
            row["raw_status"] in ("Pass", "Fail", "Warning", "NotApplicableByContract")
            for row in summary["checks"]
        )
        and set(summary["gates"]) == set(summary["expected_gate_ids"])
        and all(gate["complete"] for gate in summary["gates"].values())
    )
    has_delivery = (
        delivery_path is not None
        and type(summary["D"]) is dict
        and type(summary["D"].get("bytes")) is int
        and summary["D"]["bytes"] > 0
        and summary["D"].get("sha256") == bindings["D"]
    )
    if not summary["success"] or not complete or not has_delivery:
        state = (
            "REJECTED"
            if complete and has_delivery and summary["failure_code"] == "check_failed"
            else "UNVERIFIED"
        )
    elif policy["required"]:
        approved = _validate_review(cast(dict[str, Any], review), bindings, policy, manifest)
        state = "SHIP" if approved else "REJECTED"
    else:
        if review is not None:
            _validate_review(review, bindings, policy, manifest)
        state = "SHIP"
    if state == "SHIP":
        actual = measure_file(
            cast(Path, delivery_path), summary["D"]["bytes"], file_id=summary["D"]["id"]
        )
        if actual.bytes != summary["D"]["bytes"] or actual.sha256 != bindings["D"]:
            raise AcceptanceFailure("hash_mismatch", "delivery changed before completion")
        if any(o["accepted"] for o in summary["checks"]):
            state = "SHIP_WITH_NOTES"
    q = _write(
        root / "review.json",
        {
            "schema_version": 2,
            "bindings": bindings,
            "review": review,
            "reason": policy["reason"],
            "state": state,
        },
    )
    completion = {"schema_version": 2, "bindings": bindings | {"Q": q.sha256}, "state": state}
    _write(root / "completion.json", completion)
    # completion.json is the last durable control file; no self-hash is embedded.
    return completion


def _verify_payload(evidence_root: Path, manifest: dict[str, Any]) -> None:
    expected = {r["path"] for r in manifest["files"]}
    if _files_under(evidence_root / "payload") != expected:
        raise AcceptanceFailure("expected_set_mismatch", "review payload set changed")
    for row in manifest["files"]:
        actual = measure_file(
            evidence_root / "payload" / row["path"], row["bytes"], file_id=row["id"]
        )
        if (actual.bytes, actual.sha256) != (row["bytes"], row["sha256"]):
            raise AcceptanceFailure("hash_mismatch", "review payload changed")


def finish_review(
    evidence_root: Path, *, delivery_path: Path, review: dict[str, Any]
) -> dict[str, Any]:
    if (evidence_root / "completion.json").exists():
        raise AcceptanceFailure("reused_evidence_root", "run is already complete")
    summary = _json(evidence_root / "summary.json")
    if not summary["success"] or summary["D"] is None or summary["D"]["bytes"] <= 0:
        raise AcceptanceFailure("tool_output_invalid", "cannot approve an incomplete technical run")
    manifest_path = evidence_root / "evidence-manifest.json"
    if _identity(manifest_path) != summary["E"]:
        raise AcceptanceFailure("hash_mismatch", "evidence manifest changed")
    manifest = _json(manifest_path)
    _verify_payload(evidence_root, manifest)
    contract = load_contract(
        evidence_root / "contract.json", candidate_root=evidence_root / "payload"
    )
    if contract.digest != summary["C"] or thaw(contract.raw["review"]) != summary["review_policy"]:
        raise AcceptanceFailure("hash_mismatch", "review policy changed")
    bindings = {
        "C": summary["C"],
        "S": summary["S"],
        "D": summary["D"]["sha256"],
        "E": summary["E"],
        "V": _identity(evidence_root / "summary.json"),
    }
    return _seal(evidence_root, summary, bindings, delivery_path, review)


def deliver(evidence_root: Path, *, delivery_path: Path, destination: Path) -> dict[str, Any]:
    completion = _json(evidence_root / "completion.json")
    if completion["state"] not in ("SHIP", "SHIP_WITH_NOTES"):
        raise AcceptanceFailure("tool_output_invalid", "completed run is not approved for delivery")
    summary = _json(evidence_root / "summary.json")
    if (
        _identity(evidence_root / "summary.json") != completion["bindings"]["V"]
        or _identity(evidence_root / "evidence-manifest.json") != completion["bindings"]["E"]
        or _identity(evidence_root / "review.json") != completion["bindings"]["Q"]
    ):
        raise AcceptanceFailure("hash_mismatch", "completed control chain changed")
    q = _json(evidence_root / "review.json")
    expected_bindings = {key: completion["bindings"][key] for key in ("C", "S", "D", "E", "V")}
    if (
        q["bindings"] != expected_bindings
        or q["state"] != completion["state"]
        or not summary["success"]
    ):
        raise AcceptanceFailure("hash_mismatch", "completion/review/technical identities disagree")
    _verify_payload(evidence_root, _json(evidence_root / "evidence-manifest.json"))
    contract = load_contract(
        evidence_root / "contract.json", candidate_root=evidence_root / "payload"
    )
    if contract.digest != completion["bindings"]["C"]:
        raise AcceptanceFailure("hash_mismatch", "completed contract changed")
    if summary["D"] is None or summary["D"]["bytes"] <= 0:
        raise AcceptanceFailure("evidence_missing", "delivery identity is missing or empty")
    # A private staging directory owns cleanup, including partially copied files.
    # Its parent is the destination parent, so hard-link publication stays on one filesystem.
    with tempfile.TemporaryDirectory(prefix=".delivery-", dir=destination.parent) as staging:
        temporary = Path(staging) / "delivery"
        copied = measure_file(
            delivery_path, summary["D"]["bytes"], file_id=summary["D"]["id"], copy_to=temporary
        )
        if (copied.bytes, copied.sha256) != (summary["D"]["bytes"], completion["bindings"]["D"]):
            raise AcceptanceFailure("hash_mismatch", "delivered bytes differ from D")
        os.link(temporary, destination, follow_symlinks=False)
        parent_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    receipt = {
        "schema_version": 2,
        "D": copied.sha256,
        "T": _identity(evidence_root / "completion.json"),
        "destination": str(destination),
        "bytes": copied.bytes,
        "delivered_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    _write(evidence_root / "delivery-receipt.json", receipt)
    return receipt
