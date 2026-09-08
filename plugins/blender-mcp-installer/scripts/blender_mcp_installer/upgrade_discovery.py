from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path, PurePath
from typing import Any
from uuid import UUID

from blender_mcp_installer.filesystem import (
    InstallerError,
    SafeRoot,
    TargetRef,
    capture_file,
    capture_tree,
)
from blender_mcp_installer.model import (
    BlenderPaths,
    ImageState,
    InstallRoots,
    ReceiptStatus,
    TargetRole,
    TreeImage,
    parse_receipt,
)
from blender_mcp_installer.upgrade_cleanup import candidate_path
from blender_mcp_installer.upgrade_registration import content_sha256, read_owned_bytes
from blender_mcp_installer.upgrade_state import (
    COMMIT,
    UpgradeRoots,
    absolute,
    load_any_record,
    record_ids,
)


def install_roots(roots: UpgradeRoots, doc: dict[str, Any]) -> InstallRoots:
    profile = doc["profile"]
    if profile is None:
        raise InstallerError("installation profile is missing")
    paths = BlenderPaths(
        Path(profile["executable"]),
        profile["architecture"],
        profile["version"],
        Path(profile["resources"]),
        Path(profile["config"]),
        Path(profile["extensions"]),
    )
    source = Path(doc["desired"]["projection"])
    return InstallRoots.discover(
        roots.home,
        roots.codex_home,
        paths,
        source_distribution_root=source,
        distribution_root=source,
    )


def read_evidence(state: SafeRoot, relative: PurePath) -> tuple[bytes, dict[str, Any]]:
    if capture_file(state, relative).state is ImageState.ABSENT:
        raise FileNotFoundError(str(state.path / relative))
    raw, image = read_owned_bytes(TargetRef(state, relative))
    return raw, {
        "relative": relative.as_posix(),
        "expected": image.to_dict(),
    }


def read_proof(state: SafeRoot, relative: PurePath) -> tuple[Any, dict[str, Any]]:
    raw, proof = read_evidence(state, relative)
    return json.loads(raw), proof


def directory_names(state: SafeRoot, relative: PurePath) -> tuple[str, ...]:
    try:
        fd = state.open_directory(relative)
    except FileNotFoundError:
        return ()
    try:
        return tuple(sorted(os.listdir(fd)))
    finally:
        os.close(fd)


def lease_protocol(image: TreeImage) -> bool:
    expected = hashlib.sha256(b"inode-v1\n").hexdigest()
    return any(
        item.path == ".blender-mcp-usage-v1"
        and item.kind == "file"
        and item.sha256 == expected
        for item in image.entries
    )


def current_paths(roots: UpgradeRoots, doc: dict[str, Any]) -> tuple[Path, ...]:
    paths = [
        Path(doc["desired"]["projection"]),
        roots.caches / doc["desired"]["plugin_version"],
    ]
    if doc["mode"] == "install":
        installed = install_roots(roots, doc)
        paths.extend((installed.runtime, installed.extension_target))
    return tuple(paths)


def legacy_registration_scope(
    state: SafeRoot,
    roots: UpgradeRoots,
    reference: PurePath,
    before: Any,
    before_proof: dict[str, Any] | None,
) -> tuple[UpgradeRoots | None, list[dict[str, Any]]]:
    try:
        raw, restore_proof = read_evidence(state, reference / "RESTORE.txt")
    except FileNotFoundError:
        return None, []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, []
    lines = text.splitlines()
    has_legacy_scope = any(
        line.startswith("HOME: ") or line.startswith("CODEX_HOME: ") for line in lines
    )
    if not has_legacy_scope:
        return None, []
    expected_last = (
        "Then add the prior local source recorded in before.json: " + str(before["source"])
        if before.get("present")
        else "before.json records that the target was previously absent; do not add it."
    )
    if (
        not text.endswith("\n")
        or len(lines) != 6
        or lines[0]
        != "Restore only marketplace official-blender-mcp; installer receipts are not required."
        or not lines[1].startswith("CODEX_BIN: ")
        or lines[4]
        != "Remove the target with the recorded environment: plugin marketplace remove official-blender-mcp"
        or lines[5] != expected_last
    ):
        return None, []
    codex = absolute(lines[1].removeprefix("CODEX_BIN: "))
    home = absolute(lines[2].removeprefix("HOME: "))
    codex_home = absolute(lines[3].removeprefix("CODEX_HOME: "))
    if not codex.name or home != roots.home:
        raise InstallerError("invalid legacy registration restore evidence")
    if (
        before_proof is None
        or capture_file(state, reference / "before.json").to_dict()
        != before_proof["expected"]
    ):
        raise InstallerError("legacy registration evidence changed")
    return UpgradeRoots(home, codex_home), [restore_proof, before_proof]


def registration_scope_hint(
    state: SafeRoot, roots: UpgradeRoots, reference: PurePath
) -> UpgradeRoots | None:
    try:
        raw, _proof = read_evidence(state, reference / "RESTORE.txt")
        lines = raw.decode("utf-8").splitlines()
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    homes = [line.removeprefix("HOME: ") for line in lines if line.startswith("HOME: ")]
    codex_homes = [
        line.removeprefix("CODEX_HOME: ")
        for line in lines
        if line.startswith("CODEX_HOME: ")
    ]
    if len(homes) != 1 or len(codex_homes) != 1:
        return None
    try:
        home = absolute(homes[0])
        codex_home = absolute(codex_homes[0])
    except InstallerError:
        return None
    if home != roots.home:
        raise InstallerError("conflicting registration HOME")
    return UpgradeRoots(home, codex_home)


def registration_scope(
    state: SafeRoot,
    roots: UpgradeRoots,
    reference: PurePath,
    records: list[dict[str, Any] | None],
) -> tuple[UpgradeRoots, list[dict[str, Any]]]:
    name = reference.name
    if not re.fullmatch(r"registration\.[A-Za-z0-9_-]+", name):
        raise InstallerError("invalid historical registration identity")
    identity = name.removeprefix("registration.")
    journals = [
        item
        for item in records
        if item is not None
        and item["registration"] is not None
        and item["registration"]["id"] == identity
    ]
    if len(journals) > 1:
        raise InstallerError("ambiguous registration CODEX_HOME")
    journal_scope = None
    journal_proofs: list[dict[str, Any]] = []
    if journals:
        journal = journals[0]
        journal_scope = UpgradeRoots(roots.home, Path(journal["codex_home"]))
        _raw, journal_proof = read_evidence(
            state, PurePath("upgrades", journal["id"] + ".json")
        )
        journal_proofs.append(journal_proof)
    try:
        before, before_proof = read_proof(state, reference / "before.json")
    except FileNotFoundError:
        before = {}
        before_proof = None
    legacy_scope, legacy_proofs = legacy_registration_scope(
        state, roots, reference, before, before_proof
    )
    scope_hint = registration_scope_hint(state, roots, reference)
    if journal_scope is not None and scope_hint is not None and journal_scope != scope_hint:
        raise InstallerError("conflicting registration CODEX_HOME")
    if journal_scope is not None and legacy_scope is not None and journal_scope != legacy_scope:
        raise InstallerError("conflicting registration CODEX_HOME")
    selected = journal_scope or legacy_scope
    if selected is None:
        raise InstallerError("historical registration CODEX_HOME is unproven")
    return selected, [*journal_proofs, *legacy_proofs]


def source_reference(roots: UpgradeRoots, before: Any) -> tuple[Path, ...]:
    if not before.get("present") or before.get("source_type") != "local":
        return ()
    source = Path(before["source"])
    if source.parent != roots.projections or not COMMIT.fullmatch(source.name):
        return (source,)
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        raw, _image = read_owned_bytes(
            TargetRef(
                home,
                (
                    source / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
                ).relative_to(roots.home),
            )
        )
    manifest = json.loads(raw)
    version = manifest.get("version")
    if type(version) is not str or "/" in version or version in {".", ".."}:
        raise InstallerError("invalid recovery source plugin version")
    return (source, roots.caches / version)


def other_references(
    state: SafeRoot, roots: UpgradeRoots, doc: dict[str, Any]
) -> tuple[Path, ...]:
    references: list[Path] = []
    retired_receipts = set(doc["retired_receipts"])
    retired_registrations = set(doc["retired_registrations"])
    records = [load_any_record(state, roots, identifier) for identifier in record_ids(state)]
    for other in records:
        if other is not None and other["status"] in {"cleanup_pending", "complete"}:
            retired_receipts.update(other["retired_receipts"])
            retired_registrations.update(other["retired_registrations"])
    for other in records:
        if other is None:
            continue
        if other["id"] == doc["id"] or other["status"] != "awaiting_verification":
            continue
        registration = other["registration"]
        registration_ref = (
            None
            if registration is None
            else "marketplace-recovery/registration." + registration["id"]
        )
        if (
            other["install_id"] is not None
            and other["install_id"] in retired_receipts
            or registration_ref in retired_registrations
        ):
            continue
        selected = UpgradeRoots(roots.home, Path(other["codex_home"]))
        references.extend(current_paths(selected, other))
        if other["mode"] == "install" and other["install_id"] is not None:
            installed = install_roots(selected, other)
            references.extend(
                (
                    installed.runtime_recovery(UUID(other["install_id"])),
                    installed.extension_recovery(UUID(other["install_id"])),
                )
            )

    # Receipts remain authoritative even if the producing version predates upgrade journals.
    for name in directory_names(state, PurePath("receipts")):
        if not name.endswith(".json") or name.endswith(".usage.json"):
            continue
        try:
            identity = str(UUID(name[:-5]))
        except ValueError:
            raise InstallerError("unknown receipt filename blocks cleanup") from None
        value, _proof = read_proof(state, PurePath("receipts", name))
        host = value["host"]
        if host["home"] != str(roots.home):
            raise InstallerError("foreign receipt home blocks cleanup")
        selected = UpgradeRoots(roots.home, Path(host["codex_home"]))
        profile = BlenderPaths(
            Path(host["blender_executable"]),
            host["blender_architecture"],
            host["blender_version"],
            Path(host["blender_user_resources"]),
            Path(host["blender_user_config"]),
            Path(host["blender_user_extensions"]),
        )
        source = Path(doc["desired"]["projection"])
        installed = InstallRoots.discover(
            selected.home,
            selected.codex_home,
            profile,
            source_distribution_root=source,
            distribution_root=source,
        )
        receipt = parse_receipt(value, installed)
        if str(receipt.install_id) != identity:
            raise InstallerError("receipt filename identity mismatch")
        if receipt.status is ReceiptStatus.ROLLED_BACK:
            continue
        if receipt.status is ReceiptStatus.INSTALLED and identity in retired_receipts:
            continue
        # Never let a retirement record override PREPARED / ROLLBACK_PENDING authority.
        for target in receipt.targets:
            if (
                isinstance(target.pre, TreeImage)
                and target.pre.state is ImageState.PRESENT
                and target.recovery_path is not None
            ):
                references.append(target.recovery_path)

    # Legacy source-restore evidence can reference an old cache without any new journal.
    for name in directory_names(state, PurePath("marketplace-recovery")):
        reference = PurePath("marketplace-recovery", name)
        if (
            not name.startswith("registration.")
            or reference.as_posix() in retired_registrations
        ):
            continue
        try:
            before, _proof = read_proof(state, reference / "before.json")
        except FileNotFoundError:
            continue
        selected, _scope_proofs = registration_scope(state, roots, reference, records)
        references.extend(source_reference(selected, before))
    return tuple(references)


def discover_candidates(
    state: SafeRoot, roots: UpgradeRoots, doc: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, str]] = []
    records = [load_any_record(state, roots, workflow_id) for workflow_id in record_ids(state)]
    retired_receipts: set[str] = set()
    retired_registrations: set[str] = set()
    for other in records:
        if other is not None and other["status"] in {"cleanup_pending", "complete"}:
            retired_receipts.update(other["retired_receipts"])
            retired_registrations.update(other["retired_registrations"])
    unfinished_receipts: set[str] = set()
    unfinished_registrations: set[str] = set()
    for other in records:
        if (
            other is None
            or other["id"] == doc["id"]
            or other["status"] != "awaiting_verification"
        ):
            continue
        if other["install_id"] is not None and other["install_id"] not in retired_receipts:
            unfinished_receipts.add(other["install_id"])
        if other["registration"] is not None:
            registration_ref = (
                "marketplace-recovery/registration." + other["registration"]["id"]
            )
            if registration_ref not in retired_registrations:
                unfinished_registrations.add(registration_ref)

    # Carry durable deletion baselines forward; never capture a partial deletion as a new baseline.
    for other in records:
        if (
            other is None
            or other["codex_home"] != str(roots.codex_home)
            or other["id"] == doc["id"]
            or other["status"] != "cleanup_pending"
        ):
            continue
        if other["profile"] != doc["profile"] and other["mode"] == "install":
            continue
        for original in other["candidates"]:
            if original["state"] == "removed" or (
                doc["mode"] == "register" and original["kind"] != "plugin_cache"
            ):
                continue
            row = copy.deepcopy(original)
            row.update(state="pending", reason="carried durable cleanup baseline")
            rows[row["key"]] = row

    if doc["mode"] == "install":
        installed = install_roots(roots, doc)
        identity = doc["install_id"]
        visited: set[str] = set()
        while identity is not None:
            if identity in visited:
                raise InstallerError("receipt ancestry cycle")
            visited.add(identity)
            value, proof = read_proof(state, PurePath("receipts", identity + ".json"))
            child = parse_receipt(value, installed)
            if (
                str(child.install_id) != identity
                or child.status is not ReceiptStatus.INSTALLED
            ):
                raise InstallerError("active receipt ancestry is not installed")
            parent_id = (
                None if child.parent_install_id is None else str(child.parent_install_id)
            )
            parent = None
            parent_proof = None
            if parent_id is not None:
                parent_value, parent_proof = read_proof(
                    state, PurePath("receipts", parent_id + ".json")
                )
                parent = parse_receipt(parent_value, installed)
                if (
                    parent.status is not ReceiptStatus.INSTALLED
                    or parent.generation >= child.generation
                ):
                    raise InstallerError("invalid receipt ancestry")
            for role, kind in (
                (TargetRole.RUNTIME, "runtime_recovery"),
                (TargetRole.BLENDER_EXTENSION, "extension_recovery"),
            ):
                target = next(item for item in child.targets if item.role is role)
                if not isinstance(target.pre, TreeImage):
                    raise InstallerError("invalid managed tree target")
                if target.pre.state is ImageState.ABSENT:
                    continue
                key = kind + ":" + identity
                if key in rows:
                    continue
                if identity in unfinished_receipts:
                    findings.append(
                        {
                            "path": str(target.recovery_path),
                            "reason": "recovery belongs to another unfinished upgrade transaction",
                        }
                    )
                    continue
                recovery_path = (
                    installed.runtime_recovery(child.install_id)
                    if role is TargetRole.RUNTIME
                    else installed.extension_recovery(child.install_id)
                )
                boundary = (
                    roots.home
                    if role is TargetRole.RUNTIME
                    else installed.blender.user_resources
                )
                with SafeRoot.open(boundary, os.getuid(), boundary) as root:
                    recovery_image = capture_tree(
                        root, recovery_path.relative_to(boundary)
                    )
                if recovery_image.state is ImageState.ABSENT:
                    continue
                old = (
                    None
                    if parent is None
                    else next(item for item in parent.targets if item.role is role)
                )
                if old is None or old.install_post != target.pre:
                    findings.append(
                        {
                            "path": str(target.recovery_path),
                            "reason": "preimage lacks exact managed parent provenance",
                        }
                    )
                    continue
                row = {
                    "key": key,
                    "kind": kind,
                    "owner": identity,
                    "version": None,
                    "expected": target.pre.to_dict(),
                    "proofs": [proof, parent_proof],
                    "content_source": None,
                    "content_sha256": None,
                    "lease_known": lease_protocol(target.pre),
                    "state": "pending",
                    "reason": "",
                }
                rows[key] = row
            identity = parent_id

    scope_blocked = False
    for name in directory_names(state, PurePath("marketplace-recovery")):
        if not name.startswith("registration."):
            continue
        reference = PurePath("marketplace-recovery", name)
        try:
            selected, scope_proofs = registration_scope(
                state, roots, reference, records
            )
        except (InstallerError, ValueError, OSError, KeyError, TypeError) as exc:
            scope_blocked = True
            findings.append(
                {
                    "path": str(state.path / "marketplace-recovery" / name),
                    "reason": str(exc),
                }
            )
            continue
        try:
            after, proof = read_proof(
                state, reference / "after.json"
            )
            source = Path(after["source"])
            if (
                after.get("source_type") != "local"
                or source.parent != roots.projections
                or not COMMIT.fullmatch(source.name)
            ):
                raise InstallerError(
                    "historical registration has no reviewed local projection"
                )
            if selected.codex_home != roots.codex_home:
                findings.append(
                    {
                        "path": str(state.path / reference),
                        "reason": "historical registration belongs to another CODEX_HOME",
                    }
                )
                continue
            if reference.as_posix() in unfinished_registrations:
                findings.append(
                    {
                        "path": str(state.path / reference),
                        "reason": "registration belongs to another unfinished upgrade transaction",
                    }
                )
                continue
            if str(source) == doc["desired"]["projection"]:
                continue
            plugin = source / "plugins/blender-mcp-installer"
            with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
                raw, _manifest_image = read_owned_bytes(
                    TargetRef(
                        home,
                        (plugin / ".codex-plugin/plugin.json").relative_to(roots.home),
                    )
                )
                manifest = json.loads(raw)
                source_image = capture_tree(home, plugin.relative_to(roots.home))
            version = manifest["version"]
            if (
                manifest.get("name") != "blender-mcp-installer"
                or type(version) is not str
                or "/" in version
                or version in {".", ".."}
            ):
                raise InstallerError("invalid historical plugin manifest")
            if (
                version == doc["desired"]["plugin_version"]
                or "plugin_cache:" + version in rows
            ):
                continue
            with SafeRoot.open(
                roots.codex_home, os.getuid(), roots.codex_home
            ) as codex:
                image = capture_tree(
                    codex, (roots.caches / version).relative_to(roots.codex_home)
                )
            if image.state is ImageState.ABSENT:
                continue
            digest = content_sha256(source_image)
            if digest != content_sha256(image):
                raise InstallerError("historical cache content differs from projection")
            row = {
                "key": "plugin_cache:" + version,
                "kind": "plugin_cache",
                "owner": doc["id"],
                "version": version,
                "expected": image.to_dict(),
                "proofs": [proof, *scope_proofs],
                "content_source": str(plugin),
                "content_sha256": digest,
                "lease_known": lease_protocol(image),
                "state": "pending",
                "reason": "",
            }
            rows[row["key"]] = row
        except (InstallerError, ValueError, OSError, KeyError, TypeError) as exc:
            findings.append(
                {
                    "path": str(state.path / "marketplace-recovery" / name),
                    "reason": str(exc),
                }
            )

    if scope_blocked:
        return [], findings

    # Enumerate only the exact owned plugin namespace to report unproven physical leftovers.
    with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
        names = directory_names(codex, roots.caches.relative_to(roots.codex_home))
        for version in names:
            if (
                version == doc["desired"]["plugin_version"]
                or "plugin_cache:" + version in rows
            ):
                continue
            findings.append(
                {
                    "path": str(roots.caches / version),
                    "reason": "cache has no complete historical ownership proof",
                }
            )
    protected = current_paths(roots, doc)
    return (
        [
            row
            for _key, row in sorted(rows.items())
            if candidate_path(roots, doc, row) not in protected
        ],
        findings,
    )
