from __future__ import annotations

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
    InstallerLock,
    SafeRoot,
    TargetRef,
    capture_file,
    capture_tree,
    load_active,
    load_pending,
    load_receipt,
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
        if state in {"parked", "completed", "restoring", "restored", "cleaned"}:
            value["recovery_image"] = _present_tree()
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
        if state in {"restoring", "restored", "cleaned"}:
            value["recovery_image"] = _present_tree()
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

    def invoke(point: str, command: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", str(driver), "--point", point, "--", command, *extra],
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
