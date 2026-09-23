from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
from contextlib import ExitStack, contextmanager
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
from blender_mcp_installer.model import FileImage, ImageState, TreeImage
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


class CleanupReferenceUnproven(InstallerError):
    code = "cleanup_reference_unproven"

    def __init__(self) -> None:
        super().__init__("legacy registration recovery evidence cannot be proven")


def host_boot_time_ns() -> int:
    try:
        output = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "kern.boottime"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise InstallerError("host boot time unavailable") from exc
    match = re.fullmatch(r"\{ sec = (\d+), usec = (\d+) \}.*", output.strip())
    if match is None or int(match[2]) >= 1_000_000:
        raise InstallerError("host boot time unavailable")
    return int(match[1]) * 1_000_000_000 + int(match[2]) * 1_000


def remounted(expected: Any, current: FileImage | TreeImage) -> Any:
    """Carry a recorded image across a remount that renumbered its whole volume.

    Only the device number is adopted; inode, owner, mode, size, time and content
    still have to match the recording exactly.
    """
    if (
        expected.state is not ImageState.PRESENT
        or current.state is not ImageState.PRESENT
        or expected.dev == current.dev
    ):
        return expected
    if isinstance(expected, FileImage):
        return dataclasses.replace(expected, dev=current.dev)
    if any(entry.dev != expected.dev for entry in expected.entries):
        return expected
    entries = tuple(dataclasses.replace(entry, dev=current.dev) for entry in expected.entries)
    encoded = json.dumps(
        [entry.to_dict() for entry in entries], sort_keys=True, separators=(",", ":")
    ).encode()
    return dataclasses.replace(
        expected,
        dev=current.dev,
        digest=hashlib.sha256(encoded).hexdigest(),
        entries=entries,
    )


def retired_before_boot(row: dict[str, Any], boot_ns: int | None) -> bool:
    """Whether a host restart ended every process that could still use a lease-less recovery.

    The owner receipt becomes INSTALLED only after the old tree was renamed away, so
    its last write bounds the retirement (assuming no forward wall-clock step within
    the current boot). Managed entries resolve only the active runtime path, and a
    recovery name is not an importable Blender extension. Leased rows keep using
    their lease; plugin caches stay excluded because resumed tasks can run old cached
    scripts after a restart.
    """
    if (
        boot_ns is None
        or row["lease_known"]
        or row["kind"] not in {"runtime_recovery", "extension_recovery"}
    ):
        return False
    receipt = "receipts/" + row["owner"] + ".json"
    written = [
        FileImage.from_dict(proof["expected"]).mtime_ns
        for proof in row["proofs"]
        if proof["relative"] == receipt
    ]
    return len(written) == 1 and written[0] < boot_ns


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


@contextmanager
def retained_evidence(
    state: SafeRoot, roots: UpgradeRoots, row: dict[str, Any]
) -> Iterator[tuple[tuple[TargetRef, FileImage | TreeImage], ...]]:
    guards: list[tuple[TargetRef, FileImage | TreeImage]] = []
    for proof in row["proofs"]:
        reference = TargetRef(state, PurePath(proof["relative"]))
        current = capture_file(state, reference.relative)
        if current != remounted(FileImage.from_dict(proof["expected"]), current):
            raise InstallerError("candidate proof changed")
        guards.append((reference, current))
    if row["kind"] == "plugin_cache":
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            reference = TargetRef(
                home, Path(row["content_source"]).relative_to(roots.home)
            )
            source = capture_tree(home, reference.relative)
            if content_sha256(source) != row["content_sha256"]:
                raise InstallerError("candidate proof changed")
            yield (*guards, (reference, source))
        return
    yield tuple(guards)


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


def retire_superseded(
    state: SafeRoot, roots: UpgradeRoots, doc: dict[str, Any], fault: Any
) -> None:
    """Complete an older release's journal once every recorded baseline is absent.

    Its own finalize can no longer validate a release that is not current, so the
    current workflow records the absence; nothing is deleted here.
    """
    for workflow_id in record_ids(state):
        if workflow_id == doc["id"]:
            continue
        try:
            other = load_record(state, roots, workflow_id)
            if (
                other is None
                or other["status"] != "cleanup_pending"
                or other["desired"] == doc["desired"]
            ):
                continue
            rows = copy.deepcopy(other["candidates"])
            for row in rows:
                if row["state"] == "removed":
                    continue
                with candidate_ref(roots, other, row) as reference:
                    if reference.capture() != TreeImage.absent():
                        break
                row.update(state="removed", reason="verified absent")
            else:
                update_record(
                    state, roots, other, fault=fault, candidates=rows, status="complete"
                )
        except (InstallerError, OSError, ValueError):
            continue


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
    try:
        boot_ns: int | None = host_boot_time_ns()
    except InstallerError:
        boot_ns = None
    doc = load_record(state, roots, workflow_id, recover=True)
    if doc is None or doc["status"] == "cancelled":
        raise InstallerError("upgrade cannot be finalized")
    if doc["status"] == "complete":
        validate(doc)
        retire_superseded(state, roots, doc, fault)
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
                with retained_evidence(state, roots, row):
                    pass
                recorded = TreeImage.from_dict(row["expected"])
                with candidate_ref(roots, doc, row) as reference, ExitStack() as leases:
                    current = reference.capture()
                    expected = remounted(recorded, current)
                    if current == TreeImage.absent():
                        row.update(state="removed", reason="verified absent")
                        idle = False
                    elif retired_before_boot(row, boot_ns):
                        idle = True
                    elif not row["lease_known"]:
                        row.update(
                            state="deferred_in_use",
                            reason="legacy usage is not proven idle",
                        )
                        idle = False
                    else:
                        # Leases taken before a remount use the recorded device number;
                        # later entries can only hold an already existing lease file.
                        idle = leases.enter_context(
                            usage_lock(state, recorded.dev, recorded.ino, exclusive=True)
                        ) and (
                            expected.dev == recorded.dev
                            or leases.enter_context(
                                usage_lock(
                                    state,
                                    expected.dev,
                                    expected.ino,
                                    exclusive=True,
                                    missing_idle=True,
                                )
                            )
                        )
                        if not idle:
                            row.update(
                                state="deferred_in_use",
                                reason="version lease is busy or missing",
                            )
                    if idle:
                        validate(doc)
                        with retained_evidence(state, roots, row) as guards:
                            conditional_remove_tree(reference, expected, guards, fault)
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
    retire_superseded(state, roots, doc, fault)
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
