from __future__ import annotations

import json
import os
from pathlib import Path, PurePath
from typing import Any
from uuid import UUID

from blender_mcp_installer.filesystem import (
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    TargetRef,
    capture_file,
    capture_tree,
    load_receipt,
    write_atomic_json,
)
from blender_mcp_installer.model import ImageState, Receipt, ReceiptStatus, TargetRole
from blender_mcp_installer.upgrade_cleanup import cleanup_result, finalize_record
from blender_mcp_installer.upgrade_discovery import (
    current_paths,
    discover_candidates,
    other_references,
)
from blender_mcp_installer.upgrade_locks import ensure_usage_lock
from blender_mcp_installer.upgrade_registration import inspect_registration
from blender_mcp_installer.upgrade_state import (
    UpgradeRoots,
    load_any_record,
    load_record,
    new_record,
    record_ids,
    save_record,
    update_record,
)


def desired_from_context(context: Any) -> dict[str, str]:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    path = (
        context.roots.source_distribution_root
        / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
    )
    manifest = json.loads(path.read_bytes())
    return {
        "commit": context.distribution_commit,
        "manifest_sha256": context.manifest_sha256,
        "bundle_version": context.verified.manifest.bundle_version,
        "plugin_version": manifest["version"],
        "projection": str(roots.projections / context.distribution_commit),
    }


def profile_from_context(context: Any) -> dict[str, str]:
    profile = context.roots.blender
    return {
        "executable": str(profile.executable),
        "architecture": profile.architecture,
        "version": profile.version,
        "resources": str(profile.user_resources),
        "config": str(profile.user_config),
        "extensions": str(profile.user_extensions),
    }


def select_install_workflow(
    state: SafeRoot, context: Any, *, exact: bool
) -> dict[str, Any] | None:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    desired = desired_from_context(context)
    profile = profile_from_context(context)
    requested = context.workflow_id
    if requested is not None:
        doc = load_record(state, roots, requested, recover=True)
        if (
            doc is None
            or doc["mode"] != "install"
            or doc["desired"] != desired
            or doc["profile"] not in (None, profile)
            or doc["status"] in {"complete", "cancelled"}
        ):
            raise InstallerError("workflow does not match selected installation")
        return doc
    matches = []
    for identifier in record_ids(state):
        doc = load_any_record(state, roots, identifier, recover=True)
        if not (
            doc is not None
            and doc["codex_home"] == str(roots.codex_home)
            and doc["mode"] == "install"
            and doc["desired"] == desired
            and doc["profile"] == profile
            and doc["status"] in {"awaiting_verification", "cleanup_pending"}
        ):
            continue
        linked = doc["install_id"]
        if linked is not None:
            try:
                receipt_status = load_receipt(
                    context.roots.receipt(UUID(linked)), context.roots
                ).status
            except (InstallerError, OSError, ValueError):
                receipt_status = None
            expected_statuses = (
                {ReceiptStatus.INSTALLED}
                if exact
                else {ReceiptStatus.PREPARED, ReceiptStatus.ROLLBACK_PENDING}
            )
            if receipt_status not in expected_statuses:
                continue
        matches.append(doc)
    if len(matches) > 1:
        raise InstallerError("multiple pending workflows require an explicit workflow ID")
    if matches:
        return matches[0]
    if exact:
        return None
    doc = new_record(roots, "install", desired)
    doc["profile"] = profile
    return save_record(state, roots, None, doc)


def bind_receipt(
    state: SafeRoot, context: Any, workflow_id: str, install_id: UUID
) -> None:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    doc = load_record(state, roots, workflow_id)
    if doc is None or doc["status"] != "awaiting_verification":
        raise InstallerError("installation cannot publish into this cleanup state")
    update_record(
        state,
        roots,
        doc,
        install_id=str(install_id),
        profile=profile_from_context(context),
    )


def record_recovery_usage(
    state: SafeRoot, receipt: Receipt, runtime_handoff: dict[str, Any] | None
) -> None:
    runtime = next(item.pre for item in receipt.targets if item.role is TargetRole.RUNTIME)
    extension = next(
        item.pre for item in receipt.targets if item.role is TargetRole.BLENDER_EXTENSION
    )
    if runtime.state is ImageState.PRESENT and (
        runtime_handoff is None or runtime_handoff["image"] != runtime.to_dict()
    ):
        raise InstallerError("runtime handoff does not match prepared receipt")
    for image in (runtime, extension):
        if image.state is ImageState.PRESENT:
            ensure_usage_lock(state, image.dev, image.ino)
    document = {
        "schema_version": 1,
        "install_id": str(receipt.install_id),
        "runtime": runtime.to_dict(),
        "extension": extension.to_dict(),
        "runtime_handoff": runtime_handoff,
        "selected_blender_closed": True,
    }
    reference = TargetRef(
        state, PurePath("receipts", str(receipt.install_id) + ".usage.json")
    )
    write_atomic_json(
        reference,
        capture_file(state, reference.relative),
        document,
        receipt.install_id,
        fault=NoOpFaultInjector(),
    )


def installation_fingerprint(
    state: SafeRoot, context: Any, doc: dict[str, Any]
) -> tuple[Any, ...]:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    registration = inspect_registration(context.host.codex_bin, roots, doc["desired"])
    active = capture_file(state, PurePath("active.json"))
    receipt = capture_file(state, PurePath("receipts", doc["install_id"] + ".json"))
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        runtime = capture_tree(home, context.roots.runtime.relative_to(roots.home))
    boundary = context.roots.blender.user_resources
    with SafeRoot.open(boundary, os.getuid(), boundary) as resources:
        extension = capture_tree(
            resources, context.roots.extension_target.relative_to(boundary)
        )
    return registration, active, receipt, runtime, extension


def finalize_install_locked(
    state: SafeRoot, context: Any, workflow_id: str, fault: Any
) -> dict[str, Any]:
    from blender_mcp_installer.verification import OfficialMCPProbe, verify_live

    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    expected = desired_from_context(context)
    profile = profile_from_context(context)
    verified_fingerprint: tuple[Any, ...] | None = None

    def validate(doc: dict[str, Any]) -> tuple[Path, ...]:
        if (
            doc["mode"] != "install"
            or doc["desired"] != expected
            or doc["profile"] != profile
        ):
            raise InstallerError("finalize installation identity mismatch")
        if (
            doc["install_id"] is None
            or doc["registration"] is None
            or doc["registration"]["state"] != "registered"
        ):
            raise InstallerError(
                "finalize requires linked registration and installed receipt"
            )
        nonlocal verified_fingerprint
        current = installation_fingerprint(state, context, doc)
        if verified_fingerprint is None:
            verify_live(
                context.source_bundle,
                context.roots,
                context.blender,
                context.host,
                context.roots.receipt(UUID(doc["install_id"])),
                context.host.env,
                OfficialMCPProbe(context.roots.runtime / "bin/python"),
            )
            if installation_fingerprint(state, context, doc) != current:
                raise InstallerError("installation changed during live verification")
            verified_fingerprint = current
        elif current != verified_fingerprint:
            raise InstallerError("verified installation snapshot changed during cleanup")
        return current_paths(roots, doc)

    doc = finalize_record(
        state,
        roots,
        workflow_id,
        validate,
        lambda doc: discover_candidates(state, roots, doc),
        lambda doc: other_references(state, roots, doc),
        fault,
    )
    return cleanup_result(doc)


def finalize_register_locked(
    state: SafeRoot,
    roots: UpgradeRoots,
    workflow_id: str,
    codex: Path,
    fault: Any = None,
) -> dict[str, Any]:
    def validate(doc: dict[str, Any]) -> tuple[Path, ...]:
        if (
            doc["mode"] != "register"
            or doc["registration"] is None
            or doc["registration"]["state"] != "registered"
        ):
            raise InstallerError("finalize registration identity mismatch")
        inspect_registration(codex, roots, doc["desired"])
        return current_paths(roots, doc)

    doc = finalize_record(
        state,
        roots,
        workflow_id,
        validate,
        lambda doc: discover_candidates(state, roots, doc),
        lambda doc: other_references(state, roots, doc),
        fault,
    )
    return cleanup_result(doc)
