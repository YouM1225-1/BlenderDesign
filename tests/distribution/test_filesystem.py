from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
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
    return InstallRoots.discover(root / "home", root / "codex", _blender(root))


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
    assert roots.codex_config == tmp_path / "codex/config.toml"
    assert roots.data_root == tmp_path / "home/.local/share/blender-lab-mcp"
    assert roots.runtime == roots.data_root / "runtime"
    assert roots.state_root == tmp_path / "home/.local/state/blender-mcp-installer"
    assert roots.lock == roots.state_root / "installer.lock"
    assert roots.receipts == roots.state_root / "receipts"
    assert roots.receipt(install_id) == roots.receipts / f"{install_id}.json"
    assert roots.pending == roots.state_root / "pending.json"
    assert roots.active == roots.state_root / "active.json"
    assert roots.backups(install_id) == roots.state_root / "backups" / str(install_id)
    assert roots.previous_active(install_id) == roots.backups(install_id) / "previous-active.json"
    assert (
        roots.bundle_stage(install_id) == roots.state_root / "stages" / str(install_id) / "bundle"
    )
    assert (
        roots.runtime_stage(install_id)
        == roots.data_root / f".blender-mcp-installer.{install_id}.runtime.stage"
    )
    assert (
        roots.runtime_recovery(install_id)
        == roots.data_root / f".blender-mcp-installer.{install_id}.runtime.recovery"
    )
    assert roots.extension_target == roots.blender.user_extensions / "user_default/mcp"
    assert (
        roots.extension_stage(install_id).name
        == f".blender-mcp-installer.{install_id}.extension.stage"
    )
    assert (
        roots.extension_recovery(install_id).name
        == f".blender-mcp-installer.{install_id}.extension.recovery"
    )
    assert roots.userpref_target == roots.blender.user_config / "userpref.blend"
    assert (
        roots.userpref_stage(install_id).name
        == f".blender-mcp-installer.{install_id}.userpref.stage"
    )
    assert (
        roots.userpref_recovery(install_id).name
        == f".blender-mcp-installer.{install_id}.userpref.recovery"
    )
    assert roots.codex_stage(install_id).name == f".blender-mcp-installer.{install_id}.codex.stage"
    assert (
        roots.codex_recovery(install_id).name
        == f".blender-mcp-installer.{install_id}.codex.recovery"
    )
    assert (
        roots.codex_rollback_stage(install_id).name
        == f".blender-mcp-installer.{install_id}.codex.rollback.stage"
    )
    assert (
        InstallRoots.discover(roots.home, None, roots.blender).codex_home == roots.home / ".codex"
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
