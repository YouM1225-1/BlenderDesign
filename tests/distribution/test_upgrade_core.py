from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path, PurePath
from uuid import uuid4

import pytest

REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import (  # noqa: E402
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    capture_file,
    capture_tree,
)
from blender_mcp_installer import upgrade_cleanup, upgrade_registration  # noqa: E402
from blender_mcp_installer.upgrade_cleanup import (  # noqa: E402
    RollbackUnavailable,
    assert_rollback_available,
    cleanup_result,
    finalize_record,
)
from blender_mcp_installer.upgrade_locks import (  # noqa: E402
    ensure_usage_lock,
    usage_lock,
    usage_name,
)
from blender_mcp_installer.upgrade_registration import (  # noqa: E402
    content_sha256,
    inspect_registration,
    validate_installed_payload,
)
from blender_mcp_installer.upgrade_state import (  # noqa: E402
    UpgradeRoots,
    load_record,
    new_record,
    save_record,
    state_root,
    validate_record,
)


@pytest.fixture
def prepared(tmp_path):
    home, codex = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    desired = {"commit": "b" * 40, "manifest_sha256": "c" * 64,
               "bundle_version": "1.0.0", "plugin_version": "2", "projection": str(roots.projections / ("b" * 40))}
    version = "1"
    old_source = roots.projections / ("a" * 40) / "plugins/blender-mcp-installer"
    old_cache = roots.caches / version
    for tree in (old_source, old_cache):
        tree.mkdir(parents=True, mode=0o700)
        (tree / "a").write_bytes(b"old-a")
        (tree / "b").write_bytes(b"old-b")
    registration_id = str(uuid4())
    with state_root(roots) as state:
        folder = state.path / "marketplace-recovery" / ("registration." + registration_id)
        folder.mkdir(parents=True, mode=0o700)
        proof = folder / "after.json"
        proof.write_text("{}\n")
        proof.chmod(0o600)
        with SafeRoot.open(codex, os.getuid(), codex) as safe_codex:
            old_image = capture_tree(safe_codex, old_cache.relative_to(codex))
        with SafeRoot.open(home, os.getuid(), home) as safe_home:
            source_image = capture_tree(safe_home, old_source.relative_to(home))
        row = {"key": "plugin_cache:1", "kind": "plugin_cache", "owner": registration_id,
               "version": version, "expected": old_image.to_dict(),
               "proofs": [{"relative": proof.relative_to(state.path).as_posix(),
                           "expected": capture_file(state, proof.relative_to(state.path)).to_dict()}],
               "content_source": str(old_source), "content_sha256": content_sha256(source_image),
               "lease_known": True, "state": "pending", "reason": ""}
        ensure_usage_lock(state, old_image.dev, old_image.ino)
        doc = new_record(roots, "register", desired)
        doc["registration"] = {"id": str(uuid4()), "state": "registered"}
        (state.path / "marketplace-recovery" / ("registration." + doc["registration"]["id"])).mkdir(mode=0o700)
        doc = save_record(state, roots, None, doc)
        yield roots, state, doc, row, old_cache


def test_exact_codex_identity_checks_distinct_source_shapes():
    desired = {"bundle_version": "1.0.0", "plugin_version": "2", "projection": "/managed/new"}
    item = {"pluginId": "blender-mcp-installer@official-blender-mcp",
            "name": "blender-mcp-installer", "marketplaceName": "official-blender-mcp",
            "version": "2", "installed": True, "enabled": True,
            "source": {"source": "local", "path": "/managed/new/plugins/blender-mcp-installer"},
            "marketplaceSource": {"sourceType": "local", "source": "/managed/new"}}
    assert validate_installed_payload({"installed": [item]}, desired) == item
    for field, value in (("version", "1"), ("enabled", False), ("installed", 1)):
        bad = dict(item)
        bad[field] = value
        with pytest.raises(InstallerError):
            validate_installed_payload({"installed": [bad]}, desired)
    bad = dict(item, marketplaceSource=item["source"])
    with pytest.raises(InstallerError):
        validate_installed_payload({"installed": [bad]}, desired)


def test_registration_projection_baseline_contains_source_capture(tmp_path, monkeypatch):
    home, codex_home = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex_home.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex_home)
    desired = {
        "commit": "b" * 40,
        "manifest_sha256": "c" * 64,
        "bundle_version": "1.0.0",
        "plugin_version": "2",
        "projection": str(roots.projections / ("b" * 40)),
    }
    source = Path(desired["projection"]) / "plugins/blender-mcp-installer"
    cache = roots.caches / "2"
    for tree in (source, cache):
        (tree / ".codex-plugin").mkdir(parents=True)
        (tree / ".codex-plugin/plugin.json").write_text(
            json.dumps({"name": "blender-mcp-installer", "version": "2"})
        )
        (tree / "payload").write_text("old")
    (codex_home / "config.toml").write_text("")
    item = {
        "pluginId": "blender-mcp-installer@official-blender-mcp",
        "name": "blender-mcp-installer",
        "marketplaceName": "official-blender-mcp",
        "version": "2",
        "installed": True,
        "enabled": True,
        "source": {"source": "local", "path": str(source)},
        "marketplaceSource": {"sourceType": "local", "source": desired["projection"]},
    }
    original_capture = upgrade_registration.capture_tree
    changed = False

    def capture_with_drift(root, relative):
        nonlocal changed
        image = original_capture(root, relative)
        if root.path / relative == source and not changed:
            (source / "payload").write_text("new")
            changed = True
        return image

    def codex_response(_codex, _roots, *arguments):
        if arguments[1] == "marketplace":
            return {"marketplaces": [{"name": "official-blender-mcp", "root": desired["projection"]}]}
        return {"installed": [item]}

    monkeypatch.setattr(upgrade_registration, "capture_tree", capture_with_drift)
    monkeypatch.setattr(upgrade_registration, "codex_json", codex_response)
    with pytest.raises(InstallerError, match="registration changed during verification"):
        inspect_registration(Path("/unused"), roots, desired)
    assert (source / "payload").read_text() == "new"
    assert (cache / "payload").read_text() == "old"


def test_schema_rejects_foreign_and_unknown_fields(prepared):
    roots, state, doc, row, _ = prepared
    invalid = copy.deepcopy(doc)
    invalid["candidates"] = [row]
    invalid["candidates"][0]["content_source"] = str(roots.projections / ("a" * 40) / "blender-mcp-installer")
    with pytest.raises(InstallerError):
        validate_record(invalid, roots)
    for change in ({"schema_version": 2}, {"home": "/foreign"}, {"extra": True}):
        with pytest.raises(InstallerError):
            validate_record(dict(doc, **change), roots)


def test_no_delete_if_validation_fails(prepared):
    roots, state, doc, row, old = prepared
    def invalid(_doc):
        raise InstallerError("live failed")
    with pytest.raises(InstallerError, match="live failed"):
        finalize_record(state, roots, doc["id"], invalid, lambda _: ([row], []), lambda _: ())
    assert old.exists()
    assert load_record(state, roots, doc["id"])["status"] == "awaiting_verification"


def test_verified_cleanup_is_idempotent_and_expires_only_recorded_registration(prepared):
    roots, state, doc, row, old = prepared
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ())
    assert result["status"] == "complete" and not old.exists()
    assert Path(row["content_source"]).exists()
    assert load_record(state, roots, doc["id"]) == result
    assert finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ()) == result
    with pytest.raises(RollbackUnavailable):
        assert_rollback_available(state, roots, registration_ref=str(PurePath(row["proofs"][0]["relative"]).parent))
    assert_rollback_available(state, roots, registration_ref="marketplace-recovery/registration.other")
    assert cleanup_result(result)["all_old_versions_removed"] is True
    assert (state.path / PurePath(row["proofs"][0]["relative"]).parent / "RECOVERY_STATUS.json").is_file()


def test_active_reference_and_busy_lease_defer(prepared):
    roots, state, doc, row, old = prepared
    first = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: (old / "a",))
    assert first["candidates"][0]["state"] == "deferred_in_use" and old.exists()
    image = row["expected"]
    with usage_lock(state, image["dev"], image["ino"], exclusive=False) as acquired:
        assert acquired
        second = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
        assert second["candidates"][0]["state"] == "deferred_in_use" and old.exists()
    third = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
    assert third["status"] == "complete" and not old.exists()


def test_legacy_lease_never_assumed_idle(prepared):
    roots, state, doc, row, old = prepared
    row["lease_known"] = False
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ())
    assert result["status"] == "cleanup_pending"
    assert result["candidates"][0]["reason"] == "legacy usage is not proven idle"
    assert old.exists()


def test_content_drift_is_not_adopted_as_new_baseline(prepared):
    roots, state, doc, row, old = prepared
    (old / "foreign").write_bytes(b"user")
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ())
    assert result["candidates"][0]["state"] == "conflict"
    assert (old / "foreign").read_bytes() == b"user"
    assert result["candidates"][0]["expected"] == row["expected"]


def test_proof_drift_during_predelete_validation_preserves_candidate(prepared):
    roots, state, doc, row, old = prepared
    proof = state.path / row["proofs"][0]["relative"]
    validations = 0

    def drift_after_validation(_doc):
        nonlocal validations
        validations += 1
        if validations == 3:
            proof.write_text('{"changed":true}')
        return ()

    result = finalize_record(
        state, roots, doc["id"], drift_after_validation, lambda _: ([row], []), lambda _: ()
    )
    assert result["candidates"][0]["state"] == "conflict"
    assert result["candidates"][0]["reason"] == "candidate proof changed"
    assert old.exists()


@pytest.mark.parametrize("mutation", ["proof", "source"])
def test_cleanup_retains_exact_evidence_through_deletion_boundary(
    prepared, monkeypatch, mutation
):
    roots, state, doc, row, old = prepared
    proof = state.path / row["proofs"][0]["relative"]
    source = Path(row["content_source"])
    original_remove = upgrade_cleanup.conditional_remove_tree

    def remove_after_evidence_drift(reference, expected, guards, fault):
        guarded = {guard.path: image for guard, image in guards}
        assert proof in guarded
        assert source in guarded
        if mutation == "proof":
            proof.write_text('{"changed":true}')
        else:
            (source / "a").write_bytes(b"changed")
        return original_remove(reference, expected, guards, fault)

    monkeypatch.setattr(
        upgrade_cleanup, "conditional_remove_tree", remove_after_evidence_drift
    )
    result = finalize_record(
        state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ()
    )
    assert result["candidates"][0]["state"] == "conflict"
    assert result["candidates"][0]["reason"] == "transaction state conflict"
    assert old.exists()


@pytest.mark.parametrize("point", ["after_upgrade_cleanup_intent", "after_cleanup_entry",
                                  "after_installer_cleanup", "after_upgrade_candidate_record"])
def test_crash_is_resumed_from_original_image(prepared, point):
    roots, state, doc, row, old = prepared
    class Crash(NoOpFaultInjector):
        def hit(self, current):
            if current == point:
                raise SystemExit(70)
    with pytest.raises(SystemExit):
        finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []),
                        lambda _: (), Crash())
    pending = load_record(state, roots, doc["id"], recover=True)
    assert pending["status"] in {"cleanup_pending", "complete"}
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
    assert result["status"] == "complete" and not old.exists()


def test_root_inode_lease_survives_rename_and_exec(prepared):
    roots, state, _doc, row, old = prepared
    info = row["expected"]
    lock_path = state.path / "usage" / usage_name(info["dev"], info["ino"])
    source = (
        "import os,fcntl,sys; fd=os.open(sys.argv[1],os.O_RDWR); "
        "fcntl.flock(fd,fcntl.LOCK_SH); os.set_inheritable(fd,True); "
        "os.execv(sys.executable,[sys.executable,'-c',"
        "\"import time; print('ready',flush=True); time.sleep(60)\"])"
    )
    process = subprocess.Popen([sys.executable, "-c", source, str(lock_path)],
                               stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        renamed = old.with_name("parked")
        old.rename(renamed)
        assert (renamed.stat().st_dev, renamed.stat().st_ino) == (info["dev"], info["ino"])
        with usage_lock(state, info["dev"], info["ino"], exclusive=True) as acquired:
            assert not acquired
    finally:
        process.terminate()
        process.wait(timeout=5)
    with usage_lock(state, info["dev"], info["ino"], exclusive=True) as acquired:
        assert acquired
