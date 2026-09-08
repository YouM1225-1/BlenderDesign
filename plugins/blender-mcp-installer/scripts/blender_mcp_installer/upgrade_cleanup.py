from __future__ import annotations

import copy
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Any, Callable, Iterator
from uuid import UUID

from blender_mcp_installer.filesystem import (
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    TargetRef,
    TreeRef,
    capture_file,
    capture_tree,
    conditional_remove_tree,
    write_atomic_json,
)
from blender_mcp_installer.model import FileImage, TreeImage
from blender_mcp_installer.upgrade_locks import usage_lock
from blender_mcp_installer.upgrade_registration import content_sha256, read_owned_bytes
from blender_mcp_installer.upgrade_state import (
    UpgradeRoots,
    load_any_record,
    load_record,
    record_ids,
    update_record,
    validate_record,
)


class RollbackUnavailable(InstallerError):
    code = "rollback_unavailable"


def candidate_path(roots: UpgradeRoots, doc: dict[str, Any], row: dict[str, Any]) -> Path:
    if row["kind"] == "runtime_recovery":
        return roots.home / ".local/share/blender-lab-mcp" / (
            f".blender-mcp-installer.{row['owner']}.runtime.recovery"
        )
    if row["kind"] == "extension_recovery":
        return Path(doc["profile"]["extensions"]) / "user_default" / (
            f".blender-mcp-installer.{row['owner']}.extension.recovery"
        )
    if row["kind"] == "plugin_cache":
        return roots.caches / row["version"]
    raise InstallerError("unsupported cleanup boundary")


@contextmanager
def candidate_ref(
    roots: UpgradeRoots, doc: dict[str, Any], row: dict[str, Any]
) -> Iterator[TreeRef]:
    path = candidate_path(roots, doc, row)
    if row["kind"] == "plugin_cache":
        boundary = roots.codex_home
    elif row["kind"] == "extension_recovery":
        boundary = Path(doc["profile"]["resources"])
    else:
        boundary = roots.home
    with SafeRoot.open(boundary, os.getuid(), boundary) as root:
        yield TreeRef(root, path.relative_to(boundary))


def proof_matches(state: SafeRoot, roots: UpgradeRoots, row: dict[str, Any]) -> bool:
    for proof in row["proofs"]:
        if capture_file(state, PurePath(proof["relative"])) != FileImage.from_dict(
            proof["expected"]
        ):
            return False
    if row["kind"] == "plugin_cache":
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            source = capture_tree(
                home, Path(row["content_source"]).relative_to(roots.home)
            )
        return content_sha256(source) == row["content_sha256"]
    return True


def execution_paths() -> tuple[Path, ...]:
    paths = {Path.cwd(), Path(sys.executable).absolute()}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if isinstance(filename, str):
            paths.add(Path(filename).absolute())
    for path in sys.path:
        paths.add(Path(path or ".").absolute())
    return tuple(paths)


def overlapping(path: Path, protected: tuple[Path, ...]) -> bool:
    return any(path == item or item.is_relative_to(path) for item in protected)


def assert_rollback_available(
    state: SafeRoot,
    roots: UpgradeRoots,
    *,
    install_id: str | None = None,
    registration_ref: str | None = None,
) -> None:
    for workflow_id in record_ids(state):
        doc = load_any_record(state, roots, workflow_id)
        if doc is None or doc["status"] not in {"cleanup_pending", "complete"}:
            continue
        if (
            install_id is not None
            and install_id in doc["retired_receipts"]
            or registration_ref is not None
            and registration_ref in doc["retired_registrations"]
        ):
            raise RollbackUnavailable(
                "old program entered automatic cleanup; local rollback unavailable"
            )


def write_retirement_notices(state: SafeRoot, doc: dict[str, Any], fault: Any) -> None:
    notice = {
        "schema_version": 1,
        "program_rollback": "unavailable",
        "reason": "automatic_cleanup_started",
    }
    for reference in doc["retired_registrations"]:
        path = PurePath(reference, "RECOVERY_STATUS.json")
        target = TargetRef(state, path)
        image = capture_file(state, path)
        if image.state.value == "present":
            raw, _image = read_owned_bytes(target)
            if json.loads(raw) != notice:
                raise InstallerError("registration recovery notice conflict")
            continue
        write_atomic_json(target, image, notice, UUID(doc["id"]), fault=fault)


def finalize_record(
    state: SafeRoot,
    roots: UpgradeRoots,
    workflow_id: str,
    validate: Callable[[dict[str, Any]], tuple[Path, ...]],
    discover: Callable[
        [dict[str, Any]], tuple[list[dict[str, Any]], list[dict[str, str]]]
    ],
    other_references: Callable[[dict[str, Any]], tuple[Path, ...]],
    fault: Any = None,
) -> dict[str, Any]:
    fault = fault or NoOpFaultInjector()
    doc = load_record(state, roots, workflow_id, recover=True)
    if doc is None or doc["status"] == "cancelled":
        raise InstallerError("upgrade cannot be finalized")
    if doc["status"] == "complete":
        validate(doc)
        return doc
    protected = validate(doc)
    if doc["status"] == "awaiting_verification":
        candidates, findings = discover(doc)
        pending = copy.deepcopy(doc)
        pending["candidates"], pending["findings"] = candidates, findings
        pending["verification"] = {
            "registration": "passed",
            "live": "passed" if doc["mode"] == "install" else "not_run",
        }
        receipts = {row["owner"] for row in candidates if row["kind"] != "plugin_cache"}
        registrations = {
            str(PurePath(proof["relative"]).parent)
            for row in candidates
            if row["kind"] == "plugin_cache"
            for proof in row["proofs"]
            if PurePath(proof["relative"]).parts[0] == "marketplace-recovery"
        }
        if receipts and doc["install_id"] is not None:
            receipts.add(doc["install_id"])
        if registrations and doc["registration"] is not None:
            registrations.add(
                "marketplace-recovery/registration." + doc["registration"]["id"]
            )
        pending["retired_receipts"] = sorted(receipts)
        pending["retired_registrations"] = sorted(registrations)
        pending["status"] = "cleanup_pending"
        changes = {
            key: pending[key]
            for key in pending
            if key
            not in {
                "revision",
                "id",
                "schema_version",
                "mode",
                "home",
                "codex_home",
                "desired",
                "profile",
                "registration",
                "install_id",
            }
        }
        doc = update_record(state, roots, doc, fault=fault, **changes)
        fault.hit("after_upgrade_cleanup_intent")
    write_retirement_notices(state, doc, fault)
    for index, original in enumerate(tuple(doc["candidates"])):
        if original["state"] == "removed":
            continue
        row = copy.deepcopy(original)
        path = candidate_path(roots, doc, row)
        protected = (*validate(doc), *other_references(doc), *execution_paths())
        if overlapping(path, protected):
            row.update(state="deferred_in_use", reason="active or recovery reference")
        else:
            try:
                if not proof_matches(state, roots, row):
                    raise InstallerError("candidate proof changed")
                expected = TreeImage.from_dict(row["expected"])
                with candidate_ref(roots, doc, row) as reference:
                    current = reference.capture()
                    if current == TreeImage.absent():
                        row.update(state="removed", reason="verified absent")
                    elif not row["lease_known"]:
                        row.update(
                            state="deferred_in_use",
                            reason="legacy usage is not proven idle",
                        )
                    else:
                        with usage_lock(
                            state, expected.dev, expected.ino, exclusive=True
                        ) as acquired:
                            if not acquired:
                                row.update(
                                    state="deferred_in_use",
                                    reason="version lease is busy or missing",
                                )
                            else:
                                validate(doc)
                                conditional_remove_tree(reference, expected, (), fault)
                                validate(doc)
                                row.update(state="removed", reason="verified deletion")
            except (InstallerError, OSError, ValueError) as exc:
                row.update(state="conflict", reason=str(exc))
        rows = copy.deepcopy(doc["candidates"])
        rows[index] = row
        doc = update_record(state, roots, doc, fault=fault, candidates=rows)
        fault.hit("after_upgrade_candidate_record")
    if all(row["state"] == "removed" for row in doc["candidates"]):
        validate(doc)
        doc = update_record(state, roots, doc, fault=fault, status="complete")
    return validate_record(doc, roots)


def cleanup_result(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_id": doc["id"],
        "status": doc["status"],
        "new_version_verified": doc["verification"]["registration"] == "passed"
        and (doc["mode"] == "register" or doc["verification"]["live"] == "passed"),
        "removed": [row["key"] for row in doc["candidates"] if row["state"] == "removed"],
        "pending": [
            {"key": row["key"], "reason": row["reason"]}
            for row in doc["candidates"]
            if row["state"] != "removed"
        ],
        "unverified": doc["findings"],
        "all_old_versions_removed": doc["status"] == "complete" and not doc["findings"],
    }
