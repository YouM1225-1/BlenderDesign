from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path, PurePath
from uuid import UUID

import pytest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer import filesystem  # noqa: E402
from blender_mcp_installer.filesystem import (  # noqa: E402
    InstallerError,
    InstallerLock,
    NativeState,
    NoOpFaultInjector,
    RestoreState,
    SafeRoot,
    StagedFile,
    StagedTree,
    TargetRef,
    TreeRef,
    capture_file,
    capture_tree,
    copy_tree,
    create_deterministic_stage,
    forward_file,
    forward_tree,
    load_active,
    load_pending,
    load_receipt,
    rename_excl,
    rename_swap,
    restore_file,
    restore_tree,
    write_atomic_json,
)
from blender_mcp_installer.model import (  # noqa: E402
    ActionKind,
    ActionState,
    ActiveSelector,
    BlenderPaths,
    BoundaryRole,
    FileImage,
    ImageState,
    InstallRoots,
    ObjectKind,
    PendingSelector,
    ReceiptAction,
    ReceiptStatus,
    TargetRole,
    TreeEntry,
    TreeImage,
)
from tests.distribution.fake_host import HostHarness, SANITIZED_ENV  # noqa: E402


INSTALL_ID = UUID("12345678-1234-4234-9234-123456789abc")
PARENT_ID = UUID("87654321-4321-4321-8321-cba987654321")
HASH = "a" * 64


def _blender(root: Path) -> BlenderPaths:
    resources = root / "blender/resources"
    return BlenderPaths(
        executable=root / "bin/blender",
        architecture="arm64",
        version="5.2.0",
        user_resources=resources,
        user_config=resources / "config",
        user_extensions=resources / "extensions",
    )


def _roots(root: Path) -> InstallRoots:
    return InstallRoots.discover(
        root / "home",
        root / "codex",
        _blender(root),
        source_distribution_root=root / "source-distribution",
        distribution_root=root / "distribution",
    )


def _absent_file() -> dict[str, object]:
    return FileImage.absent().to_dict()


def _present_file() -> dict[str, object]:
    return FileImage(ImageState.PRESENT, 1, 2, os.getuid(), 0o600, 3, 4, HASH).to_dict()


def _absent_tree() -> dict[str, object]:
    return TreeImage.absent().to_dict()


def _present_tree() -> dict[str, object]:
    entry = TreeEntry("file", "file", 1, 2, os.getuid(), 0o600, 3, 4, HASH)
    raw = json.dumps([entry.to_dict()], sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    return TreeImage(ImageState.PRESENT, 1, 2, os.getuid(), 0o700, 4, digest, (entry,)).to_dict()


def _active(install_id: UUID = INSTALL_ID, generation: int = 1) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generation": generation,
        "install_id": str(install_id),
        "receipt_basename": f"{install_id}.json",
    }


def _receipt(roots: InstallRoots, secret: str | None = None) -> dict[str, object]:
    action = {
        "ordinal": 0,
        "kind": "bundle_stage",
        "object_kind": "bundle",
        "state": "planned",
        "target_role": None,
        "target_path": str(roots.bundle_stage(INSTALL_ID)),
        "stage_basename": "bundle",
        "recovery_basename": None,
        "pre": _absent_tree(),
        "intended_post": None,
        "actual_post": None,
        "recovery_image": None,
        "rollback_intended": None,
        "rollback_displaced": None,
    }
    value: dict[str, object] = {
        "schema_version": 1,
        "install_id": str(INSTALL_ID),
        "generation": 1,
        "parent_install_id": str(PARENT_ID),
        "status": "prepared",
        "created_at": "2026-08-16T01:02:03Z",
        "bundle": {"version": "1.0.0", "manifest_sha256": HASH},
        "host": {
            "home": str(roots.home),
            "codex_home": str(roots.codex_home),
            "blender_executable": str(roots.blender.executable),
            "blender_architecture": "arm64",
            "blender_version": "5.2.0",
            "blender_user_resources": str(roots.blender.user_resources),
            "blender_user_config": str(roots.blender.user_config),
            "blender_user_extensions": str(roots.blender.user_extensions),
            "codex_version": "0.148.0-alpha.9",
            "uv_version": "0.12.2",
            "python_version": "3.13.13",
        },
        "consent": {"all_four_collected_for_this_workflow": True},
        "targets": [
            {
                "role": role.value,
                "path": str(path),
                "boundary_role": boundary.value,
                "pre": _absent_tree()
                if role in {TargetRole.RUNTIME, TargetRole.BLENDER_EXTENSION}
                else _absent_file(),
                "install_post": None,
                "recovery_path": None,
                "recovery_hash": None,
            }
            for role, path, boundary in (
                (TargetRole.RUNTIME, roots.runtime, BoundaryRole.DATA_ROOT),
                (
                    TargetRole.BLENDER_EXTENSION,
                    roots.extension_target,
                    BoundaryRole.BLENDER_EXTENSIONS,
                ),
                (TargetRole.BLENDER_USERPREF, roots.userpref_target, BoundaryRole.BLENDER_CONFIG),
                (TargetRole.CODEX_CONFIG, roots.codex_config, BoundaryRole.CODEX_HOME),
                (TargetRole.ACTIVE_SELECTOR, roots.active, BoundaryRole.STATE_ROOT),
            )
        ],
        "actions": [action],
        "verification": {"configured": False, "live": "not_run"},
    }
    if secret is not None:
        value["token"] = secret
    return value


def _safe(path: Path, owned_from: Path | None = None) -> SafeRoot:
    return SafeRoot.open(path, os.getuid(), owned_from or path)


def test_exact_derived_path_table(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    install_id = INSTALL_ID
    expected = {
        "source_distribution_root": tmp_path / "source-distribution",
        "distribution_root": tmp_path / "distribution",
        "bundle_root": tmp_path / "distribution/plugins/blender-mcp-installer/artifacts",
        "codex_config": tmp_path / "codex/config.toml",
        "data_root": tmp_path / "home/.local/share/blender-lab-mcp",
        "runtime": tmp_path / "home/.local/share/blender-lab-mcp/runtime",
        "state_root": tmp_path / "home/.local/state/blender-mcp-installer",
        "lock": tmp_path / "home/.local/state/blender-mcp-installer/installer.lock",
        "receipts": tmp_path / "home/.local/state/blender-mcp-installer/receipts",
        "receipt": tmp_path / f"home/.local/state/blender-mcp-installer/receipts/{install_id}.json",
        "pending": tmp_path / "home/.local/state/blender-mcp-installer/pending.json",
        "active": tmp_path / "home/.local/state/blender-mcp-installer/active.json",
        "backups": tmp_path / f"home/.local/state/blender-mcp-installer/backups/{install_id}",
        "previous_active": tmp_path
        / f"home/.local/state/blender-mcp-installer/backups/{install_id}/previous-active.json",
        "bundle_stage": tmp_path
        / f"home/.local/state/blender-mcp-installer/stages/{install_id}/bundle",
        "runtime_stage": tmp_path
        / f"home/.local/share/blender-lab-mcp/.blender-mcp-installer.{install_id}.runtime.stage",
        "runtime_recovery": tmp_path
        / f"home/.local/share/blender-lab-mcp/.blender-mcp-installer.{install_id}.runtime.recovery",
        "extension_target": roots.blender.user_extensions / "user_default/mcp",
        "extension_stage": roots.blender.user_extensions
        / f"user_default/.blender-mcp-installer.{install_id}.extension.stage",
        "extension_recovery": roots.blender.user_extensions
        / f"user_default/.blender-mcp-installer.{install_id}.extension.recovery",
        "userpref_target": roots.blender.user_config / "userpref.blend",
        "userpref_stage": roots.blender.user_config
        / f".blender-mcp-installer.{install_id}.userpref.stage",
        "userpref_recovery": roots.blender.user_config
        / f".blender-mcp-installer.{install_id}.userpref.recovery",
        "codex_stage": roots.codex_home / f".blender-mcp-installer.{install_id}.codex.stage",
        "codex_recovery": roots.codex_home / f".blender-mcp-installer.{install_id}.codex.recovery",
        "codex_rollback_stage": roots.codex_home
        / f".blender-mcp-installer.{install_id}.codex.rollback.stage",
    }
    actual = {
        "source_distribution_root": roots.source_distribution_root,
        "distribution_root": roots.distribution_root,
        "bundle_root": roots.bundle_root,
        "codex_config": roots.codex_config,
        "data_root": roots.data_root,
        "runtime": roots.runtime,
        "state_root": roots.state_root,
        "lock": roots.lock,
        "receipts": roots.receipts,
        "receipt": roots.receipt(install_id),
        "pending": roots.pending,
        "active": roots.active,
        "backups": roots.backups(install_id),
        "previous_active": roots.previous_active(install_id),
        "bundle_stage": roots.bundle_stage(install_id),
        "runtime_stage": roots.runtime_stage(install_id),
        "runtime_recovery": roots.runtime_recovery(install_id),
        "extension_target": roots.extension_target,
        "extension_stage": roots.extension_stage(install_id),
        "extension_recovery": roots.extension_recovery(install_id),
        "userpref_target": roots.userpref_target,
        "userpref_stage": roots.userpref_stage(install_id),
        "userpref_recovery": roots.userpref_recovery(install_id),
        "codex_stage": roots.codex_stage(install_id),
        "codex_recovery": roots.codex_recovery(install_id),
        "codex_rollback_stage": roots.codex_rollback_stage(install_id),
    }
    assert actual == expected
    assert (
        InstallRoots.discover(
            roots.home,
            None,
            roots.blender,
            source_distribution_root=roots.source_distribution_root,
            distribution_root=roots.distribution_root,
        ).codex_home
        == roots.home / ".codex"
    )
    with pytest.raises(ValueError):
        InstallRoots.discover(
            roots.home,
            roots.codex_home,
            roots.blender,
            source_distribution_root=Path("relative"),
            distribution_root=roots.distribution_root,
        )


def test_ancestor_and_leaf_symlinks_rejected(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    real = owned / "real"
    real.mkdir()
    (owned / "link").symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError):
        SafeRoot.open(owned / "link/child", os.getuid(), owned)
    with _safe(owned) as root:
        (owned / "leaf").symlink_to(owned / "missing")
        with pytest.raises(ValueError):
            capture_file(root, PurePath("leaf"))


def test_foreign_owner_and_special_file_rejected(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    with pytest.raises(ValueError):
        SafeRoot.open(owned, os.getuid() + 1, owned)
    fifo = owned / "fifo"
    os.mkfifo(fifo)
    with _safe(owned) as root, pytest.raises(ValueError):
        capture_file(root, PurePath("fifo"))


def test_existing_parent_mode_never_changes(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    owned.mkdir(mode=0o751)
    owned.chmod(0o751)
    with SafeRoot.open(owned / "new/leaf", os.getuid(), owned):
        pass
    assert stat.S_IMODE(owned.stat().st_mode) == 0o751
    assert stat.S_IMODE((owned / "new").stat().st_mode) == 0o700
    assert stat.S_IMODE((owned / "new/leaf").stat().st_mode) == 0o700


def test_restrictive_umask_sets_only_new_private_objects(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    owned.mkdir(mode=0o751)
    owned.chmod(0o751)
    previous = os.umask(0o777)
    try:
        with SafeRoot.open(owned / "state", os.getuid(), owned) as root:
            assert stat.S_IMODE((owned / "state").stat().st_mode) == 0o700
            with InstallerLock.acquire(root):
                assert stat.S_IMODE((owned / "state/installer.lock").stat().st_mode) == 0o600
            target = TargetRef(root, PurePath("value.json"))
            first = write_atomic_json(target, FileImage.absent(), {"value": 1}, INSTALL_ID)
            assert first.mode == 0o600
            second = write_atomic_json(target, first, {"value": 2}, INSTALL_ID)
            assert second.mode == 0o600
    finally:
        os.umask(previous)
    assert stat.S_IMODE(owned.stat().st_mode) == 0o751
    with _safe(owned / "state") as root:
        target = TargetRef(root, PurePath("value.json"))
        current = capture_file(root, target.relative)
        write_atomic_json(target, current, {"value": 3}, INSTALL_ID)


def test_file_snapshot_detects_in_place_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    target = owned / "target"
    target.write_bytes(b"old")
    original = filesystem._hash_fd

    def mutate(fd: int) -> str:
        digest = original(fd)
        target.write_bytes(b"new content")
        return digest

    monkeypatch.setattr(filesystem, "_hash_fd", mutate)
    with _safe(owned) as root, pytest.raises(ValueError, match="changed"):
        capture_file(root, PurePath("target"))


def test_tree_snapshot_is_deterministic_and_rejects_nested_symlink(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    tree = owned / "tree"
    (tree / "b").mkdir(parents=True)
    (tree / "a").write_text("a")
    (tree / "b/z").write_text("z")
    with _safe(owned) as root:
        first = capture_tree(root, PurePath("tree"))
        second = capture_tree(root, PurePath("tree"))
        assert first == second
        assert [entry.path for entry in first.entries] == ["a", "b", "b/z"]
        (tree / "bad").symlink_to(tree / "a")
        with pytest.raises(ValueError):
            capture_tree(root, PurePath("tree"))


@pytest.mark.parametrize("mutation", ["rewrite", "rename", "add", "remove", "foreign"])
def test_tree_detects_nested_rewrite_rename_add_remove_and_foreign_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    owned = tmp_path / "owned"
    tree = owned / "tree"
    tree.mkdir(parents=True)
    target = tree / "a"
    target.write_text("old")
    if mutation == "foreign":
        original_owner = filesystem._require_owner
        calls = 0

        def reject_nested(info: os.stat_result, uid: int) -> None:
            nonlocal calls
            calls += 1
            if calls == 5:
                raise ValueError("foreign-owned path")
            original_owner(info, uid)

        monkeypatch.setattr(filesystem, "_require_owner", reject_nested)
    elif mutation == "rewrite":
        original_hash = filesystem._hash_fd

        def rewrite(fd: int) -> str:
            digest = original_hash(fd)
            target.write_text("changed")
            return digest

        monkeypatch.setattr(filesystem, "_hash_fd", rewrite)
    else:
        original_list = filesystem._listdir
        calls = 0

        def change_entries(fd: int) -> list[str]:
            nonlocal calls
            names = original_list(fd)
            calls += 1
            if calls == 1:
                if mutation == "rename":
                    target.rename(tree / "renamed")
                elif mutation == "add":
                    (tree / "added").write_text("x")
                else:
                    target.unlink()
            return names

        monkeypatch.setattr(filesystem, "_listdir", change_entries)
    with _safe(owned) as root, pytest.raises(ValueError):
        capture_tree(root, PurePath("tree"))


def test_image_variant_nullability() -> None:
    assert FileImage.from_dict(_absent_file()) == FileImage.absent()
    assert TreeImage.from_dict(_absent_tree()) == TreeImage.absent()
    for image, change in (
        (_absent_file(), {"sha256": HASH}),
        (_present_file(), {"size": None}),
        (_absent_tree(), {"entries": [_present_tree()["entries"][0]]}),
        (_present_tree(), {"digest": None}),
    ):
        image.update(change)
        parser = TreeImage.from_dict if "entries" in image else FileImage.from_dict
        with pytest.raises(ValueError):
            parser(image)
    bad_entry = _present_tree()
    bad_entry["entries"][0]["sha256"] = None
    with pytest.raises(ValueError):
        TreeImage.from_dict(bad_entry)


def _bundle_action() -> dict[str, object]:
    return {
        "ordinal": 0,
        "kind": "bundle_stage",
        "object_kind": "bundle",
        "state": "planned",
        "target_role": None,
        "target_path": "/tmp/bundle",
        "stage_basename": "bundle",
        "recovery_basename": None,
        "pre": _absent_tree(),
        "intended_post": None,
        "actual_post": None,
        "recovery_image": None,
        "rollback_intended": None,
        "rollback_displaced": None,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"rollback_intended": None, "rollback_displaced": None},
        {"rollback_intended": None},
        {"rollback_displaced": None},
        {"rollback_intended": _absent_file()},
        {"rollback_displaced": _absent_file()},
        {"rollback_intended": _present_tree()},
        {"rollback_displaced": _present_tree()},
    ],
)
def test_semantic_swapped_requires_two_present_file_images(changes: dict[str, object]) -> None:
    base = {
        **_bundle_action(),
        "kind": "codex_file",
        "object_kind": "codex",
        "state": "semantic_swapped",
        "target_role": "codex_config",
        "target_path": "/tmp/config.toml",
        "stage_basename": ".stage",
        "recovery_basename": ".recovery",
        "pre": _present_file(),
        "intended_post": _present_file(),
        "actual_post": _present_file(),
        "recovery_image": _present_file(),
        "rollback_intended": _present_file(),
        "rollback_displaced": _present_file(),
    }
    with pytest.raises(ValueError):
        ReceiptAction.from_dict({**base, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": ActionKind.RUNTIME_TREE},
        {"object_kind": ObjectKind.TREE},
        {"state": ActionState.PUBLISHED},
        {"target_role": TargetRole.RUNTIME},
        {"pre": FileImage.absent()},
        {"recovery_basename": ".recovery"},
        {"intended_post": _present_tree()},
    ],
)
def test_receipt_action_direct_construction_is_closed(changes: dict[str, object]) -> None:
    valid = ReceiptAction.from_dict(_bundle_action())
    with pytest.raises(ValueError):
        replace(valid, **changes)


def test_receipt_action_direct_managed_matrix_is_closed() -> None:
    runtime = {
        **_bundle_action(),
        "kind": "runtime_tree",
        "object_kind": "tree",
        "target_role": "runtime",
        "target_path": "/tmp/runtime",
        "stage_basename": ".runtime.stage",
        "recovery_basename": ".runtime.recovery",
    }
    valid_runtime = ReceiptAction.from_dict(runtime)
    for changes in (
        {"object_kind": ObjectKind.FILE},
        {"target_role": TargetRole.CODEX_CONFIG},
        {"recovery_basename": None},
        {"state": ActionState.SWAPPED},
        {"intended_post": _present_tree()},
        {"pre": FileImage.absent()},
    ):
        with pytest.raises(ValueError):
            replace(valid_runtime, **changes)

    semantic = ReceiptAction.from_dict(
        {
            **runtime,
            "kind": "codex_file",
            "object_kind": "codex",
            "state": "semantic_swapped",
            "target_role": "codex_config",
            "target_path": "/tmp/config.toml",
            "pre": _present_file(),
            "intended_post": _present_file(),
            "actual_post": _present_file(),
            "recovery_image": _present_file(),
            "rollback_intended": _present_file(),
            "rollback_displaced": _present_file(),
        }
    )
    for changes in (
        {"rollback_intended": None},
        {"rollback_displaced": None},
        {"rollback_intended": FileImage.absent()},
        {"rollback_displaced": TreeImage.absent()},
    ):
        with pytest.raises(ValueError):
            replace(semantic, **changes)


def test_receipt_action_enum_transition_and_nullability() -> None:
    assert tuple(item.value for item in BoundaryRole) == (
        "data_root",
        "state_root",
        "codex_home",
        "blender_resources",
        "blender_config",
        "blender_extensions",
        "target_parent",
    )
    assert tuple(item.value for item in TargetRole) == (
        "runtime",
        "blender_extension",
        "blender_userpref",
        "codex_config",
        "active_selector",
    )
    assert tuple(item.value for item in ReceiptStatus) == (
        "prepared",
        "installed",
        "rollback_pending",
        "rolled_back",
        "failed",
        "conflict",
    )
    assert tuple(item.value for item in ActionKind) == (
        "bundle_stage",
        "runtime_tree",
        "extension_tree",
        "userpref_file",
        "codex_file",
    )
    assert tuple(item.value for item in ObjectKind) == ("bundle", "tree", "file", "codex")
    assert tuple(item.value for item in ActionState) == (
        "planned",
        "staged",
        "swapped",
        "parked",
        "published",
        "completed",
        "semantic_staged",
        "semantic_swapped",
        "restoring",
        "restored",
        "cleaned",
    )
    roots = _roots(Path("/tmp/closed-contract"))
    bundle = _receipt(roots)["actions"][0]
    assert ReceiptAction.from_dict(bundle).target_role is None
    for mutation in (
        {"target_role": "runtime"},
        {"object_kind": "tree"},
        {"recovery_basename": "recovery"},
        {"rollback_intended": _present_tree()},
        {"state": "published"},
    ):
        invalid = {**bundle, **mutation}
        with pytest.raises(ValueError):
            ReceiptAction.from_dict(invalid)
    runtime = {
        **bundle,
        "kind": "runtime_tree",
        "object_kind": "tree",
        "target_role": "runtime",
        "target_path": "/tmp/runtime",
        "stage_basename": ".stage",
        "recovery_basename": ".recovery",
    }
    assert ReceiptAction.from_dict(runtime).state is ActionState.PLANNED
    with pytest.raises(ValueError):
        ReceiptAction.from_dict({**runtime, "state": "parked"})
    present_runtime = {**runtime, "pre": _present_tree()}
    for state in (
        "planned",
        "staged",
        "swapped",
        "parked",
        "completed",
        "restoring",
        "restored",
        "cleaned",
    ):
        value = {**present_runtime, "state": state}
        if state != "planned":
            value["intended_post"] = _present_tree()
        if state not in {"planned", "staged"}:
            value["actual_post"] = _present_tree()
        if state in {"parked", "completed", "restoring"}:
            value["recovery_image"] = _present_tree()
        elif state in {"restored", "cleaned"}:
            value["recovery_image"] = _absent_tree()
        assert ReceiptAction.from_dict(value).state.value == state
    for state in (
        "planned",
        "staged",
        "published",
        "completed",
        "restoring",
        "restored",
        "cleaned",
    ):
        value = {**runtime, "state": state}
        if state != "planned":
            value["intended_post"] = _present_tree()
        if state not in {"planned", "staged"}:
            value["actual_post"] = _present_tree()
        if state == "restoring":
            value["recovery_image"] = _present_tree()
        elif state in {"restored", "cleaned"}:
            value["recovery_image"] = _absent_tree()
        assert ReceiptAction.from_dict(value).state.value == state
    codex = {
        **runtime,
        "kind": "codex_file",
        "object_kind": "codex",
        "target_role": "codex_config",
        "pre": _present_file(),
        "state": "semantic_staged",
        "intended_post": _present_file(),
        "actual_post": _present_file(),
        "recovery_image": _present_file(),
        "rollback_intended": _present_file(),
    }
    assert ReceiptAction.from_dict(codex).state is ActionState.SEMANTIC_STAGED
    with pytest.raises(ValueError):
        ReceiptAction.from_dict({**codex, "kind": "userpref_file"})
    semantic_swapped = {**codex, "state": "semantic_swapped", "rollback_displaced": _present_file()}
    assert ReceiptAction.from_dict(semantic_swapped).state is ActionState.SEMANTIC_SWAPPED
    for changes in (
        {"rollback_intended": None, "rollback_displaced": None},
        {"rollback_intended": None},
        {"rollback_displaced": None},
        {"rollback_intended": _absent_file()},
        {"rollback_displaced": _absent_file()},
        {"rollback_intended": _present_tree()},
        {"rollback_displaced": _present_tree()},
    ):
        with pytest.raises(ValueError):
            ReceiptAction.from_dict({**semantic_swapped, **changes})
    valid = ReceiptAction.from_dict(bundle)
    for changes in (
        {"object_kind": ObjectKind.TREE},
        {"state": ActionState.PUBLISHED},
        {"target_role": TargetRole.RUNTIME},
        {"pre": FileImage.absent()},
        {"recovery_basename": ".recovery"},
    ):
        with pytest.raises(ValueError):
            replace(valid, **changes)


@pytest.mark.parametrize(
    "mutation",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("generation", True),
        ("schema_version", 1.0),
        ("generation", 0),
        ("generation", -1),
        ("generation", 1.0),
        ("install_id", "not-uuid"),
        ("install_id", str(INSTALL_ID).upper()),
        ("receipt_basename", "other.json"),
        ("receipt_basename", "../value.json"),
    ],
)
def test_pending_active_exact_schema_variants(mutation: tuple[str, object]) -> None:
    active = _active()
    assert ActiveSelector.from_dict(active).install_id == INSTALL_ID
    pending = {
        **active,
        "manifest_sha256": HASH,
        "previous_active": None,
    }
    assert PendingSelector.from_dict(pending).previous_active is None
    pending["previous_active"] = _active(PARENT_ID, 2)
    assert PendingSelector.from_dict(pending).previous_active.install_id == PARENT_ID
    key, value = mutation
    with pytest.raises(ValueError):
        ActiveSelector.from_dict({**active, key: value})
    with pytest.raises(ValueError):
        ActiveSelector.from_dict({**active, "extra": 1})
    missing = dict(active)
    missing.pop("generation")
    with pytest.raises(ValueError):
        ActiveSelector.from_dict(missing)
    with pytest.raises(ValueError):
        PendingSelector.from_dict({**pending, "manifest_sha256": "A" * 64})
    with pytest.raises(ValueError):
        PendingSelector.from_dict({**pending, "manifest_sha256": None})
    with pytest.raises(ValueError):
        PendingSelector.from_dict({**pending, "previous_active": False})
    with pytest.raises(ValueError):
        PendingSelector.from_dict({**pending, "extra": 1})


def test_atomic_json_crash_is_old_or_new_complete_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    target = owned / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("value.json"))
        old = capture_file(root, ref.relative)
        original = filesystem._rename_atomic

        def crash(*args: object, **kwargs: object) -> None:
            original(*args, **kwargs)
            raise RuntimeError("crash")

        monkeypatch.setattr(filesystem, "_rename_atomic", crash)
        with pytest.raises(RuntimeError):
            write_atomic_json(ref, old, {"value": "new"}, INSTALL_ID)
    assert json.loads(target.read_text()) in ({"value": "old"}, {"value": "new"})
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    monkeypatch.setattr(filesystem, "_rename_atomic", original)
    with _safe(owned) as root:
        fresh = TargetRef(root, PurePath("fresh.json"))
        first = write_atomic_json(fresh, FileImage.absent(), {"value": 1}, INSTALL_ID)
        retained = TargetRef(root, PurePath("retained.json"))
        second = write_atomic_json(fresh, first, {"value": 2}, INSTALL_ID, retained)
        assert second.state is ImageState.PRESENT
        assert json.loads(fresh.path.read_text()) == {"value": 2}
        assert json.loads(retained.path.read_text()) == {"value": 1}
        assert stat.S_IMODE(retained.path.stat().st_mode) == 0o600


def test_atomic_json_concurrent_swap_restores_foreign_document_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    target = owned / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    original = filesystem._rename_atomic
    calls = 0

    def race(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            target.write_text('{"value":"concurrent"}\n')
            target.chmod(0o600)
        original(*args, **kwargs)

    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("value.json"))
        expected = capture_file(root, ref.relative)
        monkeypatch.setattr(filesystem, "_rename_atomic", race)
        with pytest.raises(ValueError, match="concurrent"):
            write_atomic_json(ref, expected, {"value": "installer"}, INSTALL_ID)
        assert json.loads(target.read_text()) == {"value": "concurrent"}
        assert not list(owned.glob(".blender-mcp-installer.*.tmp"))
        monkeypatch.setattr(filesystem, "_rename_atomic", original)
        concurrent = capture_file(root, ref.relative)
        write_atomic_json(ref, concurrent, {"value": "retry"}, INSTALL_ID)
        assert json.loads(target.read_text()) == {"value": "retry"}


def test_atomic_json_reverse_swap_crash_prefix_has_clean_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    target = owned / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    original = filesystem._rename_atomic
    calls = 0

    def crash_after_reverse(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            target.write_text('{"value":"concurrent"}\n')
            target.chmod(0o600)
        original(*args, **kwargs)
        if calls == 2:
            raise RuntimeError("reverse-swap crash")

    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("value.json"))
        expected = capture_file(root, ref.relative)
        monkeypatch.setattr(filesystem, "_rename_atomic", crash_after_reverse)
        with pytest.raises(RuntimeError, match="reverse-swap crash"):
            write_atomic_json(ref, expected, {"value": "installer"}, INSTALL_ID)
        assert json.loads(target.read_text()) == {"value": "concurrent"}
        assert len(list(owned.glob(".blender-mcp-installer.*.tmp"))) == 1
        monkeypatch.setattr(filesystem, "_rename_atomic", original)
        concurrent = capture_file(root, ref.relative)
        write_atomic_json(ref, concurrent, {"value": "installer"}, INSTALL_ID)
        assert json.loads(target.read_text()) == {"value": "installer"}
        assert not list(owned.glob(".blender-mcp-installer.*.tmp"))


def test_atomic_json_post_swap_crash_prefix_retains_old_on_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    target = owned / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    original = filesystem._finish_old_json

    def crash_before_cleanup(*args: object, **kwargs: object) -> None:
        raise RuntimeError("cleanup crash")

    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("value.json"))
        retained = TargetRef(root, PurePath("retained.json"))
        expected = capture_file(root, ref.relative)
        monkeypatch.setattr(filesystem, "_finish_old_json", crash_before_cleanup)
        with pytest.raises(RuntimeError, match="cleanup crash"):
            write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID, retained)
        assert json.loads(target.read_text()) == {"value": "new"}
        assert len(list(owned.glob(".blender-mcp-installer.*.tmp"))) == 1
        monkeypatch.setattr(filesystem, "_finish_old_json", original)
        result = write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID, retained)
        assert result == capture_file(root, ref.relative)
        assert json.loads(target.read_text()) == {"value": "new"}
        assert json.loads(retained.path.read_text()) == {"value": "old"}
        assert not list(owned.glob(".blender-mcp-installer.*.tmp"))


def test_atomic_json_absent_publish_crash_prefix_retries_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    original_rename = filesystem._rename_atomic

    def crash_after_rename(*args: object, **kwargs: object) -> None:
        original_rename(*args, **kwargs)
        raise RuntimeError("publish crash")

    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("value.json"))
        monkeypatch.setattr(filesystem, "_rename_atomic", crash_after_rename)
        with pytest.raises(RuntimeError, match="publish crash"):
            write_atomic_json(ref, FileImage.absent(), {"value": "new"}, INSTALL_ID)
        assert json.loads(ref.path.read_text()) == {"value": "new"}
        assert not list(owned.glob(".blender-mcp-installer.*.tmp"))
        monkeypatch.setattr(filesystem, "_rename_atomic", original_rename)
        synced: list[int] = []
        original_fsync = os.fsync

        def record_fsync(fd: int) -> None:
            synced.append(os.fstat(fd).st_ino)
            original_fsync(fd)

        monkeypatch.setattr(filesystem.os, "fsync", record_fsync)
        result = write_atomic_json(ref, FileImage.absent(), {"value": "new"}, INSTALL_ID)
        assert result == capture_file(root, ref.relative)
        assert owned.stat().st_ino in synced


def test_atomic_json_old_unlink_crash_prefix_retries_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    target = owned / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    original_unlink = os.unlink

    def crash_after_unlink(path: str, *, dir_fd: int | None = None) -> None:
        original_unlink(path, dir_fd=dir_fd)
        raise RuntimeError("unlink crash")

    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("value.json"))
        expected = capture_file(root, ref.relative)
        monkeypatch.setattr(filesystem.os, "unlink", crash_after_unlink)
        with pytest.raises(RuntimeError, match="unlink crash"):
            write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID)
        assert json.loads(ref.path.read_text()) == {"value": "new"}
        assert not list(owned.glob(".blender-mcp-installer.*.tmp"))
        monkeypatch.setattr(filesystem.os, "unlink", original_unlink)
        synced: list[int] = []
        original_fsync = os.fsync

        def record_fsync(fd: int) -> None:
            synced.append(os.fstat(fd).st_ino)
            original_fsync(fd)

        monkeypatch.setattr(filesystem.os, "fsync", record_fsync)
        result = write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID)
        assert result == capture_file(root, ref.relative)
        assert owned.stat().st_ino in synced


def test_atomic_json_retain_rename_crash_prefix_retries_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = tmp_path / "owned"
    target_parent = owned / "state"
    retain_parent = owned / "recovery"
    target_parent.mkdir(parents=True)
    retain_parent.mkdir()
    target = target_parent / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    original_rename = filesystem._rename_atomic
    calls = 0

    def crash_after_retain(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        original_rename(*args, **kwargs)
        if calls == 2:
            raise RuntimeError("retain crash")

    with _safe(owned) as root:
        ref = TargetRef(root, PurePath("state/value.json"))
        retained = TargetRef(root, PurePath("recovery/old.json"))
        expected = capture_file(root, ref.relative)
        monkeypatch.setattr(filesystem, "_rename_atomic", crash_after_retain)
        with pytest.raises(RuntimeError, match="retain crash"):
            write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID, retained)
        assert json.loads(ref.path.read_text()) == {"value": "new"}
        assert capture_file(root, retained.relative) == expected
        assert not list(target_parent.glob(".blender-mcp-installer.*.tmp"))
        monkeypatch.setattr(filesystem, "_rename_atomic", original_rename)
        synced: list[int] = []
        original_fsync = os.fsync

        def record_fsync(fd: int) -> None:
            synced.append(os.fstat(fd).st_ino)
            original_fsync(fd)

        monkeypatch.setattr(filesystem.os, "fsync", record_fsync)
        result = write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID, retained)
        assert result == capture_file(root, ref.relative)
        assert {target_parent.stat().st_ino, retain_parent.stat().st_ino} <= set(synced)


def test_atomic_json_completed_prefix_mismatches_fail_untouched(tmp_path: Path) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    foreign = owned / "foreign.json"
    foreign.write_text('{"value":"foreign"}\n')
    foreign.chmod(0o600)
    target = owned / "value.json"
    target.write_text('{"value":"old"}\n')
    target.chmod(0o600)
    retained = owned / "retained.json"
    retained.write_text('{"value":"foreign-retained"}\n')
    retained.chmod(0o600)
    with _safe(owned) as root:
        foreign_ref = TargetRef(root, PurePath("foreign.json"))
        foreign_before = capture_file(root, foreign_ref.relative)
        with pytest.raises(ValueError, match="changed before write"):
            write_atomic_json(foreign_ref, FileImage.absent(), {"value": "new"}, INSTALL_ID)
        assert capture_file(root, foreign_ref.relative) == foreign_before

        ref = TargetRef(root, PurePath("value.json"))
        retained_ref = TargetRef(root, PurePath("retained.json"))
        expected = capture_file(root, ref.relative)
        target.write_text('{"value":"new"}\n')
        target.chmod(0o600)
        target_before = capture_file(root, ref.relative)
        retained_before = capture_file(root, retained_ref.relative)
        with pytest.raises(ValueError, match="changed before write"):
            write_atomic_json(ref, expected, {"value": "new"}, INSTALL_ID, retained_ref)
        assert capture_file(root, ref.relative) == target_before
        assert capture_file(root, retained_ref.relative) == retained_before


def test_non_darwin_rename_is_always_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(filesystem.sys, "platform", "linux")
    for swap in (False, True):
        with pytest.raises(OSError) as caught:
            filesystem._rename_atomic(-1, "source", -1, "target", swap=swap)
        assert caught.value.errno == __import__("errno").ENOTSUP


def _prepare_state_roots(tmp_path: Path) -> InstallRoots:
    roots = _roots(tmp_path)
    for path in (
        roots.home,
        roots.codex_home,
        roots.blender.user_resources,
        roots.blender.user_config,
        roots.blender.user_extensions,
        roots.state_root,
        roots.receipts,
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return roots


def _write_private(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n")
    path.chmod(0o600)


def test_receipt_requires_active_root_and_exact_schema(tmp_path: Path) -> None:
    roots = _prepare_state_roots(tmp_path)
    active = _active()
    _write_private(roots.active, active)
    receipt = _receipt(roots)
    receipt_path = roots.receipt(INSTALL_ID)
    _write_private(receipt_path, receipt)
    assert load_receipt(receipt_path, roots).install_id == INSTALL_ID
    assert load_active(roots.active, roots).install_id == INSTALL_ID
    assert load_pending(roots.pending, roots) is None
    copied = roots.state_root / f"{INSTALL_ID}.json"
    _write_private(copied, receipt)
    with pytest.raises(ValueError):
        load_receipt(copied, roots)
    with pytest.raises(ValueError):
        load_receipt(receipt_path.parent / f"../receipts/{INSTALL_ID}.json", roots)
    _write_private(receipt_path, {**receipt, "extra": 1})
    with pytest.raises(ValueError):
        load_receipt(receipt_path, roots)
    _write_private(receipt_path, receipt)
    receipt_path.chmod(0o644)
    with pytest.raises(ValueError):
        load_receipt(receipt_path, roots)


def test_receipt_never_contains_secret_sentinel(tmp_path: Path) -> None:
    roots = _prepare_state_roots(tmp_path)
    sentinel = "SECRET_SENTINEL_DO_NOT_RECORD"
    receipt = _receipt(roots, sentinel)
    with pytest.raises(ValueError):
        filesystem.parse_receipt(receipt, roots)
    clean = json.dumps(_receipt(roots), sort_keys=True)
    assert sentinel not in clean
    for forbidden in (
        "config_bytes",
        "old_mcp_tables",
        "environment",
        "token",
        "allow_online_access",
    ):
        assert forbidden not in clean


def test_second_installer_cannot_acquire_lock(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    with _safe(state) as root:
        with InstallerLock.acquire(root):
            with pytest.raises(BlockingIOError):
                with InstallerLock.acquire(root):
                    pass
            with pytest.raises(BlockingIOError):
                with InstallerLock.acquire(root):
                    pass


def test_fake_host_protocol_is_exact_and_read_only(host: HostHarness) -> None:
    env = {
        "HOME": str(host.home),
        "CODEX_HOME": str(host.codex_home),
        "BLENDER_USER_RESOURCES": str(host.resources),
        "BLENDER_USER_CONFIG": str(host.config),
        "BLENDER_USER_EXTENSIONS": str(host.extensions),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
    }

    def run(executable: Path, argv: list[object]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(executable), *(str(value) for value in argv)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    assert run(host.codex, ["--version"]).returncode == 0
    assert run(host.codex, ["mcp", "get", "blender"]).returncode == 2
    assert run(host.blender, ["--background", "prefix", "--python-expr", "x"]).returncode == 2
    archive = host.root / "extension.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("blender_manifest.toml", 'id = "mcp"\nversion = "1.0.0"\n')
    assert run(host.blender, ["--command", "extension", "validate", archive]).returncode == 0
    assert (
        run(
            host.blender,
            [
                "--command",
                "extension",
                "install-file",
                "--repo",
                "user_default",
                "--enable",
                archive,
            ],
        ).returncode
        == 0
    )
    assert run(host.blender, ["extension", "validate", archive, "extra"]).returncode == 2
    assert run(host.uv, ["python", "find", "3.13"]).returncode == 2
    assert (
        run(
            host.uv,
            ["python", "find", "3.13", "--no-project", "--no-python-downloads", "--no-config"],
        ).returncode
        == 0
    )
    runtime = host.root / "runtime"
    assert (
        run(host.uv, ["venv", "--relocatable", "--python", sys.executable, runtime]).returncode == 0
    )
    python = runtime / "bin/python"
    lock = host.bundle / "runtime-requirements.lock"
    wheel = host.bundle / "blender_mcp-1.0.0-py3-none-any.whl"
    lock_argv = [
        "pip",
        "install",
        "--python",
        python,
        "--require-hashes",
        "--only-binary",
        ":all:",
        "--no-build",
        "--no-deps",
        "--default-index",
        "https://pypi.org/simple",
        "-r",
        lock,
    ]
    wheel_argv = ["pip", "install", "--python", python, "--no-deps", "--no-build", wheel]
    assert run(host.uv, lock_argv).returncode == 0
    assert run(host.uv, wheel_argv).returncode == 0
    assert run(host.uv, ["pip", "install", "--python", python, "UNHASHED"]).returncode == 2
    before = len(host.commands.read_text().splitlines())
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "execute_blender_code", "arguments": {}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "get_blendfile_summary_datablocks", "arguments": {}},
        },
    ]
    result = subprocess.run(
        [str(runtime / "bin/blender-mcp")],
        env=env,
        input="".join(json.dumps(request) + "\n" for request in requests),
        text=True,
        capture_output=True,
        check=True,
    )
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert "error" in responses[2] and "result" not in responses[2]
    assert "result" in responses[3] and "error" not in responses[3]
    records = [json.loads(line) for line in host.commands.read_text().splitlines()]
    assert len(records) == before + len(requests)
    assert all(record["tool"] == "blender-mcp" for record in records[-len(requests) :])
    assert all(set(record["env"]) <= set(SANITIZED_ENV) for record in records)


def test_fault_driver_uses_closed_command_matrix_and_requires_hit(tmp_path: Path) -> None:
    distribution = tmp_path / "distribution"
    driver = distribution / "tests/distribution/fault_driver.py"
    driver.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "tests/distribution/fault_driver.py", driver)

    def invoke(
        point: str,
        command: str,
        *extra: str,
        fixture_kind: str = "extension_tree",
        preimage: str = "absent",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-I",
                str(driver),
                "--point",
                point,
                "--fixture-kind",
                fixture_kind,
                "--preimage",
                preimage,
                "--",
                command,
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    unknown = invoke("not_a_real_point", "install")
    assert unknown.returncode == 2
    assert "No module named" not in unknown.stderr
    inapplicable = invoke("after_extension_tree_publish", "verify")
    assert inapplicable.returncode == 2
    assert "No module named" not in inapplicable.stderr
    for fixture_kind in ("runtime_tree", "extension_tree", "userpref_file", "codex_file"):
        accepted = invoke(
            f"after_{fixture_kind}_restore_move",
            "rollback",
            fixture_kind=fixture_kind,
            preimage="present",
        )
        assert accepted.returncode == 1
        assert "No module named" in accepted.stderr
    for result in (
        invoke("after_extension_tree_publish", "install", fixture_kind="unknown"),
        invoke(
            "after_bundle_stage_stage", "install", fixture_kind="bundle_stage", preimage="present"
        ),
        invoke("after_json_rename", "install", fixture_kind="atomic_json", preimage="absent"),
        invoke("after_extension_tree_publish", "install", preimage="present"),
        invoke(
            "after_extension_tree_restore_move",
            "rollback",
            fixture_kind="runtime_tree",
            preimage="present",
        ),
        invoke("after_extension_tree_restore_move", "rollback", preimage="any"),
        invoke(
            "after_codex_file_restore_move",
            "rollback",
            fixture_kind="codex_semantic",
            preimage="present",
        ),
        invoke("after_extension_tree_swap", "install", preimage="absent"),
        invoke("after_extension_tree_restore_swap", "rollback", preimage="absent"),
        invoke(
            "after_active_publish",
            "install",
            fixture_kind="active_selector",
            preimage="present",
        ),
        invoke(
            "after_active_restore_move",
            "rollback",
            fixture_kind="active_selector",
            preimage="present",
        ),
        invoke(
            "after_active_swap",
            "install",
            fixture_kind="active_selector",
            preimage="absent",
        ),
        invoke(
            "after_active_restore_swap",
            "rollback",
            fixture_kind="active_selector",
            preimage="absent",
        ),
    ):
        assert result.returncode == 2
        assert "No module named" not in result.stderr

    package = distribution / "plugins/blender-mcp-installer/scripts/blender_mcp_installer"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "cli.py").write_text(
        "class ExitFaultInjector:\n"
        "    def __init__(self, point, code):\n"
        "        self.point, self.code, self.hit_requested = point, code, False\n"
        "    def hit(self, point):\n"
        "        if point == self.point:\n"
        "            self.hit_requested = True\n"
        "            raise SystemExit(self.code)\n"
        "def run_cli(argv, fault):\n"
        "    if '--exercise-fault' in argv:\n"
        "        fault.hit('after_extension_tree_publish')\n"
        "    return 0\n"
    )
    assert invoke("after_extension_tree_publish", "install", "--exercise-fault").returncode == 70
    missed = invoke("after_extension_tree_publish", "install")
    assert missed.returncode == 2
    assert "requested fault point was not hit" in missed.stderr


class _InjectedCrash(RuntimeError):
    pass


class _CrashAfterRename:
    def hit(self, point: str) -> None:
        if point == "after_native_rename":
            raise _InjectedCrash


def _write_private_bytes(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    path.chmod(0o600)


def _staged_file(root: SafeRoot, basename: str, raw: bytes) -> StagedFile:
    stage = create_deterministic_stage(root, basename, FileImage.absent(), NoOpFaultInjector())
    assert isinstance(stage, StagedFile)
    _write_private_bytes(stage.path, raw)
    return stage.refresh()


def _installed_file(
    root: SafeRoot, *, present: bool, fault: object | None = None
) -> tuple[TargetRef, FileImage, StagedFile, TargetRef, FileImage]:
    target = TargetRef(root, PurePath("target"))
    recovery = TargetRef(root, PurePath("recovery"))
    if present:
        _write_private_bytes(target.path, b"pre")
    pre = capture_file(root, target.relative)
    stage = _staged_file(root, "stage", b"post")
    post = stage.image
    assert isinstance(post, FileImage)
    while True:
        state = forward_file(
            target,
            pre,
            stage,
            recovery,
            fault or NoOpFaultInjector(),
        )
        if state is NativeState.COMPLETED:
            return target, pre, stage, recovery, post


def test_deterministic_stage_is_private_and_collisions_fail_closed(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        file_stage = create_deterministic_stage(
            root, "file.stage", FileImage.absent(), NoOpFaultInjector()
        )
        tree_stage = create_deterministic_stage(
            root, "tree.stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(file_stage, StagedFile)
        assert isinstance(tree_stage, StagedTree)
        assert stat.S_IMODE(file_stage.path.stat().st_mode) == 0o600
        assert stat.S_IMODE(tree_stage.path.stat().st_mode) == 0o700
        with pytest.raises(InstallerError, match="deterministic stage already exists"):
            create_deterministic_stage(root, "file.stage", FileImage.absent(), NoOpFaultInjector())
        with pytest.raises(ValueError, match="absent"):
            create_deterministic_stage(
                root, "other", capture_file(root, PurePath("file.stage")), NoOpFaultInjector()
            )
        with pytest.raises(ValueError, match="basename"):
            create_deterministic_stage(
                root, "nested/stage", FileImage.absent(), NoOpFaultInjector()
            )


@pytest.mark.parametrize("tree", [False, True])
def test_deterministic_stage_rejects_replacement_before_final_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree: bool
) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        real_open = os.open
        real_close = os.close
        created_fd: int | None = None
        created_ino: int | None = None
        replacement_ino: int | None = None
        replaced = False

        def track_created_fd(*args: object, **kwargs: object) -> int:
            nonlocal created_fd
            fd = real_open(*args, **kwargs)
            name = args[0] if args else kwargs.get("path")
            flags = args[1] if len(args) > 1 else kwargs.get("flags", 0)
            if (
                name == "stage"
                and kwargs.get("dir_fd") == root.fd
                and ((tree and flags & os.O_DIRECTORY) or (not tree and flags & os.O_EXCL))
            ):
                created_fd = fd
            return fd

        def replace_after_created_fd_close(fd: int) -> None:
            nonlocal created_ino, replacement_ino, replaced
            if fd != created_fd or replaced:
                real_close(fd)
                return
            created_ino = os.fstat(fd).st_ino
            real_close(fd)
            replaced = True
            if tree:
                os.rmdir("stage", dir_fd=root.fd)
            else:
                os.unlink("stage", dir_fd=root.fd)
            _foreign_object(root.fd, "stage", tree=tree)
            replacement_ino = os.stat("stage", dir_fd=root.fd, follow_symlinks=False).st_ino

        monkeypatch.setattr(filesystem.os, "open", track_created_fd)
        monkeypatch.setattr(filesystem.os, "close", replace_after_created_fd_close)
        expected_absent = TreeImage.absent() if tree else FileImage.absent()
        with pytest.raises(InstallerError, match="transaction state conflict"):
            create_deterministic_stage(root, "stage", expected_absent, NoOpFaultInjector())
        assert replaced and created_ino != replacement_ino
        if tree:
            assert (tmp_path / "stage/foreign").read_bytes() == b"foreign"
        else:
            assert (tmp_path / "stage").read_bytes() == b"foreign"


@pytest.mark.parametrize("nonempty", [False, True])
def test_copy_tree_proves_stable_source_and_copies_closed_tree(
    tmp_path: Path, nonempty: bool
) -> None:
    source_path = tmp_path / "source"
    stage_parent = tmp_path / "staging"
    source_path.mkdir()
    stage_parent.mkdir()
    if nonempty:
        (source_path / "nested").mkdir()
        _write_private_bytes(source_path / "nested/payload", b"payload")
    with _safe(tmp_path) as root:
        source = TreeRef(root, PurePath("source"))
        stage_root = SafeRoot.open(stage_parent, os.getuid(), stage_parent)
        try:
            created = create_deterministic_stage(
                stage_root, "tree", TreeImage.absent(), NoOpFaultInjector()
            )
            assert isinstance(created, StagedTree)
            copied = copy_tree(source, created)
            assert copied == capture_tree(stage_root, PurePath("tree"))
            assert copied.state is ImageState.PRESENT
            expected_paths = () if not nonempty else ("nested", "nested/payload")
            assert tuple(entry.path for entry in copied.entries) == expected_paths
            assert capture_tree(root, PurePath("source")) == source.capture()
        finally:
            stage_root.close()


@pytest.mark.parametrize("entry_kind", ["symlink", "fifo"])
def test_copy_tree_rejects_nested_links_and_special_files(tmp_path: Path, entry_kind: str) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    if entry_kind == "symlink":
        (source_path / "bad").symlink_to("missing")
    else:
        os.mkfifo(source_path / "bad")
    with _safe(tmp_path) as root:
        created = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(created, StagedTree)
        with pytest.raises(ValueError, match="symlink or special"):
            copy_tree(TreeRef(root, PurePath("source")), created)
        assert capture_tree(root, PurePath("stage")).entries == ()


def test_copy_tree_rejects_foreign_owner_and_source_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    _write_private_bytes(source_path / "payload", b"payload")
    payload_ino = (source_path / "payload").stat().st_ino
    original_owner = filesystem._require_owner

    def reject_payload(info: os.stat_result, uid: int) -> None:
        if info.st_ino == payload_ino:
            raise ValueError("foreign-owned path")
        original_owner(info, uid)

    with _safe(tmp_path) as root:
        stage = create_deterministic_stage(
            root, "foreign-stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(stage, StagedTree)
        monkeypatch.setattr(filesystem, "_require_owner", reject_payload)
        with pytest.raises(ValueError, match="foreign-owned"):
            copy_tree(TreeRef(root, PurePath("source")), stage)
        monkeypatch.setattr(filesystem, "_require_owner", original_owner)

        changing_stage = create_deterministic_stage(
            root, "changing-stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(changing_stage, StagedTree)
        original_copy = filesystem._copy_file

        def mutate_after_copy(source_fd: int, name: str, target_fd: int, uid: int) -> FileImage:
            result = original_copy(source_fd, name, target_fd, uid)
            fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, dir_fd=source_fd)
            try:
                os.write(fd, b"changed")
            finally:
                os.close(fd)
            return result

        monkeypatch.setattr(filesystem, "_copy_file", mutate_after_copy)
        with pytest.raises(ValueError, match="source tree changed"):
            copy_tree(TreeRef(root, PurePath("source")), changing_stage)


def test_native_rename_wrappers_map_closed_errors_and_fsync_both_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    left_path = tmp_path / "left"
    right_path = tmp_path / "right"
    left_path.mkdir()
    right_path.mkdir()
    _write_private_bytes(left_path / "source", b"source")
    _write_private_bytes(right_path / "destination", b"destination")
    with _safe(left_path) as left, _safe(right_path) as right:
        real_rename = filesystem._rename_atomic
        with pytest.raises(InstallerError, match="rename destination already exists"):
            rename_excl(left, "source", right, "destination", NoOpFaultInjector())

        def unsupported(*args: object, **kwargs: object) -> None:
            raise OSError(errno.ENOTSUP, "unsupported")

        monkeypatch.setattr(filesystem, "_rename_atomic", unsupported)
        with pytest.raises(InstallerError, match="native rename is not supported"):
            rename_swap(left, "source", right, "destination", NoOpFaultInjector())

        def cross_device(*args: object, **kwargs: object) -> None:
            raise OSError(errno.EXDEV, "cross-device")

        monkeypatch.setattr(filesystem, "_rename_atomic", cross_device)
        with pytest.raises(InstallerError, match="cross-device rename is not supported"):
            rename_swap(left, "source", right, "destination", NoOpFaultInjector())

        monkeypatch.setattr(filesystem, "_rename_atomic", real_rename)
        (right_path / "destination").unlink()
        fsync_calls: list[int] = []
        real_fsync = os.fsync

        def record_fsync(fd: int) -> None:
            fsync_calls.append(fd)
            real_fsync(fd)

        monkeypatch.setattr(filesystem.os, "fsync", record_fsync)
        rename_excl(left, "source", right, "destination", NoOpFaultInjector())
        assert fsync_calls == [left.fd, right.fd]


def test_rename_excl_preserves_concurrent_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_parent = tmp_path / "source-parent"
    target_parent = tmp_path / "target-parent"
    source_parent.mkdir()
    target_parent.mkdir()
    _write_private_bytes(source_parent / "source", b"installer")
    real = filesystem._rename_atomic

    def race(source_fd: int, source: str, target_fd: int, target: str, *, swap: bool) -> None:
        fd = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=target_fd,
        )
        os.write(fd, b"foreign")
        os.close(fd)
        real(source_fd, source, target_fd, target, swap=swap)

    monkeypatch.setattr(filesystem, "_rename_atomic", race)
    with _safe(source_parent) as source, _safe(target_parent) as target:
        with pytest.raises(InstallerError, match="rename destination already exists"):
            rename_excl(source, "source", target, "target", NoOpFaultInjector())
    assert (source_parent / "source").read_bytes() == b"installer"
    assert (target_parent / "target").read_bytes() == b"foreign"


def test_swap_race_is_conditionally_reversed_and_preserves_foreign_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target = TargetRef(root, PurePath("target"))
        recovery = TargetRef(root, PurePath("recovery"))
        _write_private_bytes(target.path, b"pre")
        pre = capture_file(root, target.relative)
        stage = _staged_file(root, "stage", b"post")
        real = filesystem._rename_atomic
        raced = False

        def race(source_fd: int, source: str, target_fd: int, name: str, *, swap: bool) -> None:
            nonlocal raced
            if not raced:
                raced = True
                os.unlink(name, dir_fd=target_fd)
                fd = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=target_fd,
                )
                try:
                    os.write(fd, b"foreign")
                finally:
                    os.close(fd)
            real(source_fd, source, target_fd, name, swap=swap)

        monkeypatch.setattr(filesystem, "_rename_atomic", race)
        with pytest.raises(InstallerError, match="transaction state conflict"):
            forward_file(target, pre, stage, recovery, NoOpFaultInjector())
        assert capture_file(root, target.relative) == pre
        assert stage.path.read_bytes() == b"foreign"
        assert capture_file(root, recovery.relative).state is ImageState.ABSENT


def test_present_file_forward_recovers_each_crash_prefix(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target = TargetRef(root, PurePath("target"))
        recovery = TargetRef(root, PurePath("recovery"))
        _write_private_bytes(target.path, b"pre")
        pre = capture_file(root, target.relative)
        stage = _staged_file(root, "stage", b"post")
        post = stage.image
        with pytest.raises(_InjectedCrash):
            forward_file(target, pre, stage, recovery, _CrashAfterRename())
        assert (
            capture_file(root, target.relative),
            stage.capture(),
            capture_file(root, recovery.relative),
        ) == (
            post,
            pre,
            FileImage.absent(),
        )
        with pytest.raises(_InjectedCrash):
            forward_file(target, pre, stage, recovery, _CrashAfterRename())
        assert (
            capture_file(root, target.relative),
            stage.capture(),
            capture_file(root, recovery.relative),
        ) == (
            post,
            FileImage.absent(),
            pre,
        )
        assert (
            forward_file(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.COMPLETED
        )


def test_absent_file_forward_publish_crash_is_retry_safe(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target = TargetRef(root, PurePath("target"))
        recovery = TargetRef(root, PurePath("recovery"))
        pre = FileImage.absent()
        stage = _staged_file(root, "stage", b"post")
        post = stage.image
        with pytest.raises(_InjectedCrash):
            forward_file(target, pre, stage, recovery, _CrashAfterRename())
        assert (
            capture_file(root, target.relative),
            stage.capture(),
            capture_file(root, recovery.relative),
        ) == (
            post,
            FileImage.absent(),
            FileImage.absent(),
        )
        assert (
            forward_file(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.COMPLETED
        )


def test_present_file_restore_retries_after_each_reverse_rename(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target, pre, stage, recovery, post = _installed_file(root, present=True)
        with pytest.raises(_InjectedCrash):
            restore_file(target, pre, post, stage, recovery, _CrashAfterRename())
        assert (
            capture_file(root, target.relative),
            stage.capture(),
            capture_file(root, recovery.relative),
        ) == (
            pre,
            FileImage.absent(),
            post,
        )
        assert (
            restore_file(target, pre, post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )
        assert capture_file(root, target.relative) == pre
        assert capture_file(root, recovery.relative).state is ImageState.ABSENT

        stage2 = _staged_file(root, "stage2", b"post-2")
        post2 = stage2.image
        assert (
            forward_file(target, pre, stage2, recovery, NoOpFaultInjector()) is NativeState.SWAPPED
        )
        with pytest.raises(_InjectedCrash):
            restore_file(target, pre, post2, stage2, recovery, _CrashAfterRename())
        assert capture_file(root, target.relative) == pre
        assert stage2.capture() == post2
        assert (
            restore_file(target, pre, post2, stage2, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        assert (
            restore_file(target, pre, post2, stage2, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )
        assert stage2.capture().state is ImageState.ABSENT


@pytest.mark.parametrize("present", [False, True])
def test_file_restore_cleans_only_the_closed_p0_stage(tmp_path: Path, present: bool) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target = TargetRef(root, PurePath("target"))
        recovery = TargetRef(root, PurePath("recovery"))
        if present:
            _write_private_bytes(target.path, b"pre")
        pre = capture_file(root, target.relative)
        stage = _staged_file(root, "stage", b"post")
        assert (
            restore_file(target, pre, stage.image, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        assert capture_file(root, target.relative) == pre
        assert stage.capture().state is ImageState.ABSENT
        assert capture_file(root, recovery.relative) == stage.image
        assert (
            restore_file(target, pre, stage.image, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )
        assert capture_file(root, recovery.relative).state is ImageState.ABSENT


def test_installed_preimage_survives_fresh_root_until_rollback(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    root = _safe(tmp_path)
    target, pre, stage, recovery, post = _installed_file(root, present=True)
    assert capture_file(root, recovery.relative) == pre
    root.close()

    with _safe(tmp_path) as reopened:
        fresh_target = TargetRef(reopened, target.relative)
        fresh_stage = StagedFile(reopened, stage.relative, post)
        fresh_recovery = TargetRef(reopened, recovery.relative)
        assert capture_file(reopened, fresh_recovery.relative) == pre
        assert (
            restore_file(
                fresh_target,
                pre,
                post,
                fresh_stage,
                fresh_recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORING
        )
        assert (
            restore_file(
                fresh_target,
                pre,
                post,
                fresh_stage,
                fresh_recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORED
        )
        assert capture_file(reopened, fresh_target.relative) == pre


def test_absent_file_restore_retry_and_foreign_postimage_preservation(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target, pre, stage, recovery, post = _installed_file(root, present=False)
        with pytest.raises(_InjectedCrash):
            restore_file(target, pre, post, stage, recovery, _CrashAfterRename())
        assert (capture_file(root, target.relative), capture_file(root, recovery.relative)) == (
            FileImage.absent(),
            post,
        )
        assert (
            restore_file(target, pre, post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )

        target2, pre2, stage2, recovery2, post2 = _installed_file(root, present=False)
        target2.path.unlink()
        _write_private_bytes(target2.path, b"foreign")
        foreign = capture_file(root, target2.relative)
        with pytest.raises(InstallerError, match="transaction state conflict"):
            restore_file(target2, pre2, post2, stage2, recovery2, NoOpFaultInjector())
        assert capture_file(root, target2.relative) == foreign
        assert capture_file(root, recovery2.relative).state is ImageState.ABSENT


def test_present_file_cross_volume_recovery_fails_at_closed_p1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target = TargetRef(root, PurePath("target"))
        recovery = TargetRef(root, PurePath("recovery"))
        _write_private_bytes(target.path, b"pre")
        pre = capture_file(root, target.relative)
        stage = _staged_file(root, "stage", b"post")
        post = stage.image
        assert (
            forward_file(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.SWAPPED
        )
        real = filesystem._rename_atomic

        def cross_volume(
            source_fd: int, source: str, target_fd: int, target_name: str, *, swap: bool
        ) -> None:
            if target_name == "recovery":
                raise OSError(errno.EXDEV, "cross-device")
            real(source_fd, source, target_fd, target_name, swap=swap)

        monkeypatch.setattr(filesystem, "_rename_atomic", cross_volume)
        with pytest.raises(InstallerError, match="cross-device rename is not supported"):
            forward_file(target, pre, stage, recovery, NoOpFaultInjector())
        assert (
            capture_file(root, target.relative),
            stage.capture(),
            capture_file(root, recovery.relative),
        ) == (
            post,
            pre,
            FileImage.absent(),
        )


@pytest.mark.parametrize("nonempty", [False, True])
def test_tree_forward_and_restore_are_byte_identical(tmp_path: Path, nonempty: bool) -> None:
    tmp_path.chmod(0o700)
    target_path = tmp_path / "target"
    source_path = tmp_path / "source"
    target_path.mkdir()
    source_path.mkdir()
    if nonempty:
        (target_path / "old-dir").mkdir()
        _write_private_bytes(target_path / "old-dir/old", b"old")
        (source_path / "new-dir").mkdir()
        _write_private_bytes(source_path / "new-dir/new", b"new")
    with _safe(tmp_path) as root:
        target = TreeRef(root, PurePath("target"))
        recovery = TreeRef(root, PurePath("recovery"))
        pre = target.capture()
        created = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(created, StagedTree)
        stage = created.with_image(copy_tree(TreeRef(root, PurePath("source")), created))
        post = stage.image
        assert (
            forward_tree(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.SWAPPED
        )
        assert forward_tree(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.PARKED
        assert (
            forward_tree(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.COMPLETED
        )
        assert target.capture() == post
        assert recovery.capture() == pre
        assert (
            restore_tree(target, pre, post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        assert (
            restore_tree(target, pre, post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )
        assert target.capture() == pre
        assert recovery.capture().state is ImageState.ABSENT


def test_absent_tree_publish_and_ar1_retry(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    source_path = tmp_path / "source"
    source_path.mkdir()
    (source_path / "nested").mkdir()
    _write_private_bytes(source_path / "nested/payload", b"payload")
    with _safe(tmp_path) as root:
        target = TreeRef(root, PurePath("target"))
        recovery = TreeRef(root, PurePath("recovery"))
        created = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(created, StagedTree)
        stage = created.with_image(copy_tree(TreeRef(root, PurePath("source")), created))
        post = stage.image
        with pytest.raises(_InjectedCrash):
            forward_tree(
                target,
                TreeImage.absent(),
                stage,
                recovery,
                _CrashAfterRename(),
            )
        assert target.capture() == post
        assert stage.capture().state is ImageState.ABSENT
        assert (
            forward_tree(
                target,
                TreeImage.absent(),
                stage,
                recovery,
                NoOpFaultInjector(),
            )
            is NativeState.COMPLETED
        )
        with pytest.raises(_InjectedCrash):
            restore_tree(
                target,
                TreeImage.absent(),
                post,
                stage,
                recovery,
                _CrashAfterRename(),
            )
        assert target.capture().state is ImageState.ABSENT
        assert recovery.capture() == post
        assert (
            restore_tree(
                target,
                TreeImage.absent(),
                post,
                stage,
                recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORED
        )
        assert recovery.capture().state is ImageState.ABSENT


class _CrashAt:
    def __init__(self, point: str):
        self.point = point

    def hit(self, point: str) -> None:
        if point == self.point:
            raise _InjectedCrash(point)


@pytest.mark.parametrize(
    "point",
    ["after_native_rename", "after_source_parent_fsync", "after_destination_parent_fsync"],
)
@pytest.mark.parametrize("row", ["p0", "p1", "p2", "a0", "a1", "r1", "ar1"])
def test_recognized_cross_parent_prefix_redrives_both_parent_fsyncs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    point: str,
    row: str,
) -> None:
    target_path = tmp_path / "target-parent"
    stage_path = tmp_path / "stage-parent"
    recovery_path = tmp_path / "recovery-parent"
    for path in (target_path, stage_path, recovery_path):
        path.mkdir()
    with (
        _safe(target_path) as target_root,
        _safe(stage_path) as stage_root,
        _safe(recovery_path) as recovery_root,
    ):
        target = TargetRef(target_root, PurePath("target"))
        recovery = TargetRef(recovery_root, PurePath("recovery"))
        present = row in {"p0", "p1", "p2", "r1"}
        if present:
            _write_private_bytes(target.path, b"pre")
        pre = capture_file(target_root, target.relative)
        stage = _staged_file(stage_root, "stage", b"post")
        post = stage.image

        if row in {"p2", "r1"}:
            assert (
                forward_file(target, pre, stage, recovery, NoOpFaultInjector())
                is NativeState.SWAPPED
            )
        if row == "r1":
            assert (
                forward_file(target, pre, stage, recovery, NoOpFaultInjector())
                is NativeState.PARKED
            )
        if row == "ar1":
            assert (
                forward_file(target, pre, stage, recovery, NoOpFaultInjector())
                is NativeState.PUBLISHED
            )
        if row in {"p1", "p2", "a1"}:
            with pytest.raises(_InjectedCrash):
                forward_file(target, pre, stage, recovery, _CrashAt(point))
        else:
            with pytest.raises(_InjectedCrash):
                restore_file(target, pre, post, stage, recovery, _CrashAt(point))

        synced: list[int] = []
        real_fsync = os.fsync

        def record_fsync(fd: int) -> None:
            synced.append(os.fstat(fd).st_ino)
            real_fsync(fd)

        monkeypatch.setattr(filesystem.os, "fsync", record_fsync)
        if row in {"p1", "p2", "a1"}:
            forward_file(target, pre, stage, recovery, NoOpFaultInjector())
            expected = {
                "p1": {target_root.fd, stage_root.fd},
                "p2": {stage_root.fd, recovery_root.fd},
                "a1": {stage_root.fd, target_root.fd},
            }[row]
        else:
            restore_file(target, pre, post, stage, recovery, NoOpFaultInjector())
            expected = (
                {stage_root.fd, recovery_root.fd}
                if row in {"p0", "a0"}
                else {target_root.fd, recovery_root.fd}
            )
        expected_inodes = {os.fstat(fd).st_ino for fd in expected}
        assert expected_inodes <= set(synced)


def _foreign_object(parent_fd: int, name: str, *, tree: bool) -> None:
    if tree:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            child = os.open(
                "foreign",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=fd,
            )
            os.write(child, b"foreign")
            os.close(child)
        finally:
            os.close(fd)
    else:
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        os.write(fd, b"foreign")
        os.close(fd)


@pytest.mark.parametrize("tree", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("side", ["left", "right"])
def test_swap_races_reverse_either_replaced_operand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree: bool,
    reverse: bool,
    side: str,
) -> None:
    tmp_path.chmod(0o700)
    target_path = tmp_path / "target"
    source_path = tmp_path / "source"
    target_path.mkdir()
    source_path.mkdir()
    _write_private_bytes(target_path / "pre", b"pre")
    _write_private_bytes(source_path / "post", b"post")
    with _safe(tmp_path) as root:
        if tree:
            target: TargetRef = TreeRef(root, PurePath("target"))
            recovery: TargetRef = TreeRef(root, PurePath("recovery"))
            pre = capture_tree(root, target.relative)
            created = create_deterministic_stage(
                root, "stage", TreeImage.absent(), NoOpFaultInjector()
            )
            assert isinstance(created, StagedTree)
            stage: StagedFile | StagedTree = created.with_image(
                copy_tree(TreeRef(root, PurePath("source")), created)
            )
            post = stage.image
            forward = forward_tree
            restore = restore_tree
        else:
            shutil.rmtree(target_path)
            target = TargetRef(root, PurePath("target"))
            recovery = TargetRef(root, PurePath("recovery"))
            _write_private_bytes(target.path, b"pre")
            pre = capture_file(root, target.relative)
            stage = _staged_file(root, "stage", b"post")
            post = stage.image
            forward = forward_file
            restore = restore_file
        if reverse:
            while (
                forward(target, pre, stage, recovery, NoOpFaultInjector())
                is not NativeState.COMPLETED
            ):
                pass
            right_ref = recovery
        else:
            right_ref = stage
        left_ref = target
        expected_left = (
            capture_tree(root, left_ref.relative) if tree else capture_file(root, left_ref.relative)
        )
        expected_right = (
            capture_tree(root, right_ref.relative)
            if tree
            else capture_file(root, right_ref.relative)
        )
        real = filesystem._rename_atomic
        raced = False

        def race(source_fd: int, source: str, target_fd: int, name: str, *, swap: bool) -> None:
            nonlocal raced
            if not raced and swap:
                raced = True
                chosen_fd, chosen_name = (
                    (source_fd, source) if side == "left" else (target_fd, name)
                )
                os.rename(chosen_name, f"lost-{side}", src_dir_fd=chosen_fd, dst_dir_fd=chosen_fd)
                _foreign_object(chosen_fd, chosen_name, tree=tree)
            real(source_fd, source, target_fd, name, swap=swap)

        monkeypatch.setattr(filesystem, "_rename_atomic", race)
        with pytest.raises(InstallerError, match="transaction state conflict"):
            if reverse:
                restore(target, pre, post, stage, recovery, NoOpFaultInjector())
            else:
                forward(target, pre, stage, recovery, NoOpFaultInjector())
        current_left = (
            capture_tree(root, left_ref.relative) if tree else capture_file(root, left_ref.relative)
        )
        current_right = (
            capture_tree(root, right_ref.relative)
            if tree
            else capture_file(root, right_ref.relative)
        )
        if side == "left":
            assert current_left not in {expected_left, expected_right}
            assert current_right == expected_right
        else:
            assert current_left == expected_left
            assert current_right not in {expected_left, expected_right}


@pytest.mark.parametrize("tree", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_excl_source_race_moves_exact_foreign_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree: bool,
    reverse: bool,
) -> None:
    tmp_path.chmod(0o700)
    source_path = tmp_path / "source"
    source_path.mkdir()
    _write_private_bytes(source_path / "post", b"post")
    with _safe(tmp_path) as root:
        if tree:
            target: TargetRef = TreeRef(root, PurePath("target"))
            recovery: TargetRef = TreeRef(root, PurePath("recovery"))
            created = create_deterministic_stage(
                root, "stage", TreeImage.absent(), NoOpFaultInjector()
            )
            assert isinstance(created, StagedTree)
            stage: StagedFile | StagedTree = created.with_image(
                copy_tree(TreeRef(root, PurePath("source")), created)
            )
            pre = TreeImage.absent()
            post = stage.image
            forward = forward_tree
            restore = restore_tree
        else:
            target = TargetRef(root, PurePath("target"))
            recovery = TargetRef(root, PurePath("recovery"))
            stage = _staged_file(root, "stage", b"post")
            pre = FileImage.absent()
            post = stage.image
            forward = forward_file
            restore = restore_file
        if reverse:
            assert (
                forward(target, pre, stage, recovery, NoOpFaultInjector()) is NativeState.PUBLISHED
            )
            source_ref = target
            destination_ref = recovery
        else:
            source_ref = stage
            destination_ref = target
        real = filesystem._rename_atomic
        raced = False

        def race(source_fd: int, source: str, target_fd: int, name: str, *, swap: bool) -> None:
            nonlocal raced
            if not raced and not swap:
                raced = True
                os.rename(source, "lost-source", src_dir_fd=source_fd, dst_dir_fd=source_fd)
                _foreign_object(source_fd, source, tree=tree)
            real(source_fd, source, target_fd, name, swap=swap)

        monkeypatch.setattr(filesystem, "_rename_atomic", race)
        with pytest.raises(InstallerError, match="transaction state conflict"):
            if reverse:
                restore(target, pre, post, stage, recovery, NoOpFaultInjector())
            else:
                forward(target, pre, stage, recovery, NoOpFaultInjector())
        foreign = (
            capture_tree(root, source_ref.relative)
            if tree
            else capture_file(root, source_ref.relative)
        )
        destination = (
            capture_tree(root, destination_ref.relative)
            if tree
            else capture_file(root, destination_ref.relative)
        )
        assert foreign.state is ImageState.PRESENT and foreign != post
        assert destination.state is ImageState.ABSENT


@pytest.mark.parametrize("mutation", ["add", "rename", "remove", "collision"])
def test_copy_tree_never_adopts_or_cleans_foreign_destination_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    _write_private_bytes(source_path / "payload", b"payload")
    with _safe(tmp_path) as root:
        stage = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(stage, StagedTree)
        original_copy = filesystem._copy_file

        def mutate(source_fd: int, name: str, target_fd: int, uid: int) -> FileImage:
            if mutation == "collision":
                _foreign_object(target_fd, name, tree=False)
                return original_copy(source_fd, name, target_fd, uid)
            result = original_copy(source_fd, name, target_fd, uid)
            if mutation == "add":
                _foreign_object(target_fd, "foreign", tree=False)
            elif mutation == "rename":
                os.rename(name, "foreign", src_dir_fd=target_fd, dst_dir_fd=target_fd)
            else:
                os.unlink(name, dir_fd=target_fd)
            return result

        monkeypatch.setattr(filesystem, "_copy_file", mutate)
        with pytest.raises((InstallerError, FileExistsError, ValueError)):
            copy_tree(TreeRef(root, PurePath("source")), stage)
        assert capture_tree(root, stage.relative).state is ImageState.PRESENT


def test_copy_tree_rejects_replacement_before_final_file_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    _write_private_bytes(source_path / "payload", b"payload")
    with _safe(tmp_path) as root:
        stage = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(stage, StagedTree)
        original_capture = filesystem._capture_file_at
        replaced = False

        def replace_before_capture(parent_fd: int, name: str, uid: int) -> FileImage:
            nonlocal replaced
            if not replaced and name == "payload" and os.fstat(parent_fd).st_ino == stage.image.ino:
                replaced = True
                os.unlink(name, dir_fd=parent_fd)
                _foreign_object(parent_fd, name, tree=False)
            return original_capture(parent_fd, name, uid)

        monkeypatch.setattr(filesystem, "_capture_file_at", replace_before_capture)
        with pytest.raises(InstallerError, match="transaction state conflict"):
            copy_tree(TreeRef(root, PurePath("source")), stage)
        assert (stage.path / "payload").read_bytes() == b"foreign"


def test_copy_file_closes_source_when_destination_open_collides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source"
    target_path = tmp_path / "target"
    source_path.mkdir()
    target_path.mkdir()
    _write_private_bytes(source_path / "payload", b"source")
    _write_private_bytes(target_path / "payload", b"collision")
    source_fd = os.open(source_path, os.O_RDONLY | os.O_DIRECTORY)
    target_fd = os.open(target_path, os.O_RDONLY | os.O_DIRECTORY)
    opened: list[int] = []
    closed: list[int] = []
    real_open = os.open
    real_close = os.close

    def record_open(*args: object, **kwargs: object) -> int:
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def record_close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(filesystem.os, "open", record_open)
    monkeypatch.setattr(filesystem.os, "close", record_close)
    try:
        for _ in range(3):
            with pytest.raises(FileExistsError):
                filesystem._copy_file(source_fd, "payload", target_fd, os.getuid())
        assert sorted(opened) == sorted(closed)
    finally:
        real_close(target_fd)
        real_close(source_fd)


@pytest.mark.parametrize("failure", ["collision", "open"])
def test_copy_directory_closes_source_child_on_repeated_destination_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    source_path = tmp_path / "source"
    target_path = tmp_path / "target"
    (source_path / "nested").mkdir(parents=True)
    target_path.mkdir()
    source_fd = os.open(source_path, os.O_RDONLY | os.O_DIRECTORY)
    target_fd = os.open(target_path, os.O_RDONLY | os.O_DIRECTORY)
    real_open_directory = filesystem._open_verified_directory
    real_close = os.close
    active: dict[int, int] = {}

    def track_open_directory(parent_fd: int, name: str, uid: int | None) -> int:
        if failure == "open" and parent_fd == target_fd:
            raise OSError(errno.EIO, "injected destination open failure")
        fd = real_open_directory(parent_fd, name, uid)
        active[fd] = active.get(fd, 0) + 1
        return fd

    def track_close(fd: int) -> None:
        if active.get(fd, 0):
            active[fd] -= 1
            if active[fd] == 0:
                del active[fd]
        real_close(fd)

    monkeypatch.setattr(filesystem, "_open_verified_directory", track_open_directory)
    monkeypatch.setattr(filesystem.os, "close", track_close)
    if failure == "collision":
        real_mkdir = os.mkdir

        def collide(name: str, *args: object, **kwargs: object) -> None:
            if name == "nested" and kwargs.get("dir_fd") == target_fd:
                raise FileExistsError(errno.EEXIST, "injected directory collision", name)
            real_mkdir(name, *args, **kwargs)

        monkeypatch.setattr(filesystem.os, "mkdir", collide)
    try:
        for _ in range(3):
            with pytest.raises(
                FileExistsError if failure == "collision" else OSError,
                match="collision" if failure == "collision" else "open failure",
            ):
                filesystem._copy_directory(source_fd, target_fd, os.getuid())
            if failure == "open":
                os.rmdir("nested", dir_fd=target_fd)
        assert active == {}
    finally:
        real_close(target_fd)
        real_close(source_fd)


def test_copy_tree_closes_source_root_on_repeated_destination_open_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    real_open_directory = filesystem._open_verified_directory
    real_close = os.close
    active: dict[int, int] = {}
    source_opens = 0
    failed_stages: set[str] = set()
    in_copy = False

    def track_open_directory(parent_fd: int, name: str, uid: int | None) -> int:
        nonlocal source_opens
        if in_copy and name == "source":
            source_opens += 1
        if (
            in_copy
            and name.startswith("stage-")
            and source_opens % 2 == 0
            and name not in failed_stages
        ):
            failed_stages.add(name)
            raise OSError(errno.EIO, "injected stage open failure")
        fd = real_open_directory(parent_fd, name, uid)
        active[fd] = active.get(fd, 0) + 1
        return fd

    def track_close(fd: int) -> None:
        if active.get(fd, 0):
            active[fd] -= 1
            if active[fd] == 0:
                del active[fd]
        real_close(fd)

    monkeypatch.setattr(filesystem, "_open_verified_directory", track_open_directory)
    monkeypatch.setattr(filesystem.os, "close", track_close)
    with _safe(tmp_path) as root:
        for index in range(3):
            stage = create_deterministic_stage(
                root,
                f"stage-{index}",
                TreeImage.absent(),
                NoOpFaultInjector(),
            )
            assert isinstance(stage, StagedTree)
            in_copy = True
            try:
                with pytest.raises(OSError, match="stage open failure"):
                    copy_tree(TreeRef(root, PurePath("source")), stage)
            finally:
                in_copy = False
    assert failed_stages == {"stage-0", "stage-1", "stage-2"}
    assert active == {}


def test_copy_tree_pure_partial_failure_removes_stage_for_clean_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    for name in ("a", "b"):
        _write_private_bytes(source_path / name, name.encode())
    with _safe(tmp_path) as root:
        stage = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(stage, StagedTree)
        original_copy = filesystem._copy_file
        calls = 0

        def fail_second(source_fd: int, name: str, target_fd: int, uid: int) -> FileImage:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError(errno.EIO, "injected copy failure")
            return original_copy(source_fd, name, target_fd, uid)

        monkeypatch.setattr(filesystem, "_copy_file", fail_second)
        with pytest.raises(OSError, match="injected copy failure"):
            copy_tree(TreeRef(root, PurePath("source")), stage)
        assert capture_tree(root, stage.relative).state is ImageState.ABSENT
        assert isinstance(
            create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector()),
            StagedTree,
        )


def test_copy_tree_partial_file_write_removes_only_created_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_path = tmp_path / "source"
    source_path.mkdir()
    _write_private_bytes(source_path / "payload", b"payload")
    with _safe(tmp_path) as root:
        stage = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(stage, StagedTree)

        def fail_partial(fd: int, raw: bytes) -> None:
            os.write(fd, raw[:1])
            raise OSError(errno.EIO, "injected partial write")

        monkeypatch.setattr(filesystem, "_write_all", fail_partial)
        with pytest.raises(OSError, match="injected partial write"):
            copy_tree(TreeRef(root, PurePath("source")), stage)
        assert capture_tree(root, stage.relative).state is ImageState.ABSENT


def test_reverse_paths_quarantine_post_before_cleanup(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    with _safe(tmp_path) as root:
        target = TargetRef(root, PurePath("target"))
        recovery = TargetRef(root, PurePath("recovery"))
        _write_private_bytes(target.path, b"pre")
        pre = capture_file(root, target.relative)
        stage = _staged_file(root, "stage", b"post")
        post = stage.image
        assert (
            restore_file(target, pre, post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        assert (
            capture_file(root, target.relative),
            stage.capture(),
            capture_file(root, recovery.relative),
        ) == (
            pre,
            FileImage.absent(),
            post,
        )
        assert (
            restore_file(target, pre, post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )

        stage2 = _staged_file(root, "stage2", b"post2")
        post2 = stage2.image
        assert (
            forward_file(target, pre, stage2, recovery, NoOpFaultInjector()) is NativeState.SWAPPED
        )
        assert (
            restore_file(target, pre, post2, stage2, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        assert stage2.capture() == post2
        assert (
            restore_file(target, pre, post2, stage2, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        assert stage2.capture().state is ImageState.ABSENT
        assert capture_file(root, recovery.relative) == post2


def test_tree_recovery_cleanup_retries_exact_deletion_prefix(
    tmp_path: Path,
) -> None:
    tmp_path.chmod(0o700)
    source = tmp_path / "source"
    source.mkdir()
    for name in ("a", "z"):
        _write_private_bytes(source / name, name.encode())
    with _safe(tmp_path) as root:
        target = TreeRef(root, PurePath("target"))
        recovery = TreeRef(root, PurePath("recovery"))
        stage0 = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(stage0, StagedTree)
        stage = stage0.with_image(copy_tree(TreeRef(root, PurePath("source")), stage0))
        post = stage.image
        assert (
            restore_tree(target, TreeImage.absent(), post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )
        with pytest.raises(_InjectedCrash):
            restore_tree(
                target,
                TreeImage.absent(),
                post,
                stage,
                recovery,
                _CrashAt("after_cleanup_entry"),
            )
        remaining = recovery.capture()
        assert remaining.state is ImageState.PRESENT
        assert 0 < len(remaining.entries) < len(post.entries)
        assert (
            restore_tree(target, TreeImage.absent(), post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORED
        )


@pytest.mark.parametrize("mutation", ["change", "extra"])
def test_tree_recovery_cleanup_preserves_foreign_remainder(tmp_path: Path, mutation: str) -> None:
    tmp_path.chmod(0o700)
    source = tmp_path / "source"
    source.mkdir()
    for name in ("a", "z"):
        _write_private_bytes(source / name, name.encode())
    with _safe(tmp_path) as root:
        target = TreeRef(root, PurePath("target"))
        recovery = TreeRef(root, PurePath("recovery"))
        created = create_deterministic_stage(root, "stage", TreeImage.absent(), NoOpFaultInjector())
        assert isinstance(created, StagedTree)
        stage = created.with_image(copy_tree(TreeRef(root, PurePath("source")), created))
        post = stage.image
        assert (
            restore_tree(target, TreeImage.absent(), post, stage, recovery, NoOpFaultInjector())
            is RestoreState.RESTORING
        )

        class MutateBeforeDelete:
            def hit(self, point: str) -> None:
                if point != "before_cleanup_delete":
                    return
                if mutation == "change":
                    (recovery.path / "z").write_bytes(b"foreign")
                else:
                    _write_private_bytes(recovery.path / "foreign", b"foreign")

        with pytest.raises(InstallerError, match="transaction state conflict"):
            restore_tree(target, TreeImage.absent(), post, stage, recovery, MutateBeforeDelete())
        assert (recovery.path / "a").read_bytes() == b"a"
        if mutation == "change":
            assert (recovery.path / "z").read_bytes() == b"foreign"
        else:
            assert (recovery.path / "foreign").read_bytes() == b"foreign"


def test_native_and_model_basenames_reject_embedded_nul(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    _write_private_bytes(tmp_path / "left", b"left")
    _write_private_bytes(tmp_path / "right", b"right")
    with _safe(tmp_path) as root:
        for operation, args in (
            (rename_excl, (root, "left\0suffix", root, "new")),
            (rename_swap, (root, "left", root, "right\0suffix")),
        ):
            with pytest.raises(ValueError, match="basename"):
                operation(*args, NoOpFaultInjector())
    valid = ReceiptAction.from_dict(_bundle_action())
    for changes in (
        {"stage_basename": "stage\0suffix"},
        {
            "kind": ActionKind.RUNTIME_TREE,
            "object_kind": ObjectKind.TREE,
            "target_role": TargetRole.RUNTIME,
            "recovery_basename": "recovery\0suffix",
            "pre": TreeImage.absent(),
        },
    ):
        with pytest.raises(ValueError, match="basename"):
            replace(valid, **changes)


def test_receipt_action_encodes_every_native_reverse_row() -> None:
    pre = TreeImage.from_dict(_present_tree())
    post = replace(pre, ino=pre.ino + 100)
    absent = TreeImage.absent()
    base = {
        **_bundle_action(),
        "kind": "runtime_tree",
        "object_kind": "tree",
        "target_role": "runtime",
        "target_path": "/tmp/runtime",
        "stage_basename": ".stage",
        "recovery_basename": ".recovery",
        "intended_post": post.to_dict(),
        "actual_post": post.to_dict(),
    }
    rows = (
        ({"state": "parked", "pre": pre.to_dict(), "recovery_image": pre.to_dict()}),
        ({"state": "completed", "pre": pre.to_dict(), "recovery_image": pre.to_dict()}),
        ({"state": "restoring", "pre": pre.to_dict(), "recovery_image": None}),
        ({"state": "restoring", "pre": pre.to_dict(), "recovery_image": post.to_dict()}),
        ({"state": "restored", "pre": pre.to_dict(), "recovery_image": absent.to_dict()}),
        ({"state": "cleaned", "pre": pre.to_dict(), "recovery_image": absent.to_dict()}),
        ({"state": "restoring", "pre": absent.to_dict(), "recovery_image": post.to_dict()}),
        ({"state": "restored", "pre": absent.to_dict(), "recovery_image": absent.to_dict()}),
        ({"state": "cleaned", "pre": absent.to_dict(), "recovery_image": absent.to_dict()}),
    )
    for row in rows:
        assert ReceiptAction.from_dict({**base, **row}).state.value == row["state"]
    for invalid in (
        {"state": "restored", "pre": pre.to_dict(), "recovery_image": pre.to_dict()},
        {"state": "restoring", "pre": absent.to_dict(), "recovery_image": None},
        {"state": "restoring", "pre": pre.to_dict(), "recovery_image": pre.to_dict()},
        {"state": "restored", "pre": pre.to_dict(), "recovery_image": None},
    ):
        with pytest.raises(ValueError):
            ReceiptAction.from_dict({**base, **invalid})


@pytest.mark.parametrize("tree", [False, True])
def test_receipt_action_rejects_shared_absent_post_and_recovery_images(tree: bool) -> None:
    image = _present_tree() if tree else _present_file()
    valid = ReceiptAction.from_dict(
        {
            **_bundle_action(),
            "kind": "runtime_tree" if tree else "userpref_file",
            "object_kind": "tree" if tree else "file",
            "state": "restored",
            "target_role": "runtime" if tree else "blender_userpref",
            "target_path": "/tmp/runtime" if tree else "/tmp/userpref.blend",
            "stage_basename": ".stage",
            "recovery_basename": ".recovery",
            "pre": image,
            "intended_post": image,
            "actual_post": image,
            "recovery_image": _absent_tree() if tree else _absent_file(),
        }
    )
    absent = TreeImage.absent() if tree else FileImage.absent()
    with pytest.raises(ValueError, match="post/recovery images must be present"):
        replace(
            valid,
            intended_post=absent,
            actual_post=absent,
            recovery_image=absent,
        )


def test_receipt_action_keeps_semantic_restore_images_closed() -> None:
    pre = FileImage.from_dict(_present_file())
    post = replace(pre, ino=pre.ino + 100)
    rollback = replace(pre, ino=pre.ino + 200)
    base = {
        **_bundle_action(),
        "kind": "codex_file",
        "object_kind": "codex",
        "target_role": "codex_config",
        "target_path": "/tmp/config.toml",
        "stage_basename": ".stage",
        "recovery_basename": ".recovery",
        "pre": pre.to_dict(),
        "intended_post": post.to_dict(),
        "actual_post": post.to_dict(),
        "rollback_intended": rollback.to_dict(),
        "rollback_displaced": post.to_dict(),
    }
    restoring = {**base, "state": "restoring", "recovery_image": pre.to_dict()}
    restored = {
        **base,
        "state": "restored",
        "recovery_image": FileImage.absent().to_dict(),
    }
    assert ReceiptAction.from_dict(restoring).state is ActionState.RESTORING
    assert ReceiptAction.from_dict(restored).state is ActionState.RESTORED
    with pytest.raises(ValueError):
        ReceiptAction.from_dict({**restoring, "recovery_image": post.to_dict()})
    with pytest.raises(ValueError):
        ReceiptAction.from_dict({**restored, "recovery_image": pre.to_dict()})
