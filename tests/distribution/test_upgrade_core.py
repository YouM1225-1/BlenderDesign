from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path, PurePath
from uuid import UUID, uuid4

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
from blender_mcp_installer.model import BlenderPaths, InstallRoots  # noqa: E402
from blender_mcp_installer import upgrade_cleanup, upgrade_registration  # noqa: E402
from blender_mcp_installer.upgrade_cleanup import (  # noqa: E402
    RollbackUnavailable,
    assert_rollback_available,
    cleanup_result,
    finalize_record,
)
from blender_mcp_installer.upgrade_locks import (  # noqa: E402
    device_usage_name,
    ensure_usage_lock,
    tree_usage_name,
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
    update_record,
    validate_record,
)


def _install_profile(roots: UpgradeRoots) -> dict[str, str]:
    resources = roots.home / "blender/resources"
    return {
        "executable": str(roots.home / "bin/blender"),
        "architecture": "arm64",
        "version": "5.2.0",
        "resources": str(resources),
        "config": str(resources / "config"),
        "extensions": str(resources / "extensions"),
    }


def _install_roots(roots: UpgradeRoots, doc: dict[str, object]) -> InstallRoots:
    profile = doc["profile"]
    assert isinstance(profile, dict)
    blender = BlenderPaths(
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
        blender,
        source_distribution_root=source,
        distribution_root=source,
    )


def _write_receipt(
    state: SafeRoot,
    installed: InstallRoots,
    install_id: str,
    *,
    generation: int,
    parent_install_id: str | None,
    status: str,
    runtime_image=None,
) -> Path:
    from tests.distribution.test_filesystem import _receipt

    value = _receipt(installed)
    value.update(
        install_id=install_id,
        generation=generation,
        parent_install_id=parent_install_id,
        status=status,
        actions=[],
    )
    if runtime_image is not None:
        runtime = next(target for target in value["targets"] if target["role"] == "runtime")
        runtime.update(
            pre=runtime_image.to_dict(),
            install_post=runtime_image.to_dict(),
            recovery_path=str(installed.runtime_recovery(uuid4_from_text(install_id))),
            recovery_hash=runtime_image.digest,
        )
    path = state.path / "receipts" / f"{install_id}.json"
    path.parent.mkdir(exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    path.chmod(0o600)
    return path


def _register_case(tmp_path: Path) -> tuple[UpgradeRoots, dict[str, object]]:
    home, codex = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    desired = {
        "commit": "b" * 40,
        "manifest_sha256": "c" * 64,
        "bundle_version": "1.0.0",
        "plugin_version": "2",
        "projection": str(roots.projections / ("b" * 40)),
    }
    return roots, new_record(roots, "register", desired)


def _registration_evidence(
    state: SafeRoot,
    roots: UpgradeRoots,
    *,
    version: str = "1",
    after: dict[str, object] | None,
    registration_name: str = "historical",
    restore_codex_home: Path | None = None,
) -> tuple[Path, Path, Path]:
    projection = roots.projections / ("a" * 40)
    plugin = projection / "plugins/blender-mcp-installer"
    cache = roots.caches / version
    manifest = json.dumps({"name": "blender-mcp-installer", "version": version})
    for tree in (plugin, cache):
        (tree / ".codex-plugin").mkdir(parents=True)
        (tree / ".codex-plugin/plugin.json").write_text(manifest)
        (tree / "payload").write_text("managed")
        (tree / ".blender-mcp-usage-v1").write_text("inode-v1\n")
    proof = state.path / "marketplace-recovery" / f"registration.{registration_name}"
    proof.mkdir(parents=True, mode=0o700)
    before = {"present": False}
    (proof / "before.json").write_text(json.dumps(before) + "\n")
    (proof / "before.json").chmod(0o600)
    if after is not None:
        (proof / "after.json").write_text(json.dumps(after) + "\n")
        (proof / "after.json").chmod(0o600)
    _write_legacy_restore(proof, roots, before, restore_codex_home or roots.codex_home)
    return projection, plugin, cache


def _write_legacy_restore(
    proof: Path,
    roots: UpgradeRoots,
    before: dict[str, object],
    codex_home: Path,
) -> Path:
    lines = [
        "Restore only marketplace official-blender-mcp; installer receipts are not required.",
        f"CODEX_BIN: {roots.home / 'bin/codex'}",
        f"HOME: {roots.home}",
        f"CODEX_HOME: {codex_home}",
        "Remove the target with the recorded environment: plugin marketplace remove official-blender-mcp",
    ]
    if before["present"]:
        lines.append(
            "Then add the prior local source recorded in before.json: "
            + str(before["source"])
        )
    else:
        lines.append(
            "before.json records that the target was previously absent; do not add it."
        )
    restore = proof / "RESTORE.txt"
    restore.write_text("\n".join(lines) + "\n")
    restore.chmod(0o600)
    return restore


def uuid4_from_text(value: object) -> UUID:
    assert isinstance(value, str)
    return UUID(value)


@pytest.fixture
def prepared(tmp_path, request):
    marker = getattr(request, "param", None)
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
        if marker is not None:
            (tree / ".blender-mcp-usage-v1").write_bytes(marker)
    registration_id = str(uuid4())
    with state_root(roots) as state:
        folder = state.path / "marketplace-recovery" / ("registration." + registration_id)
        folder.mkdir(parents=True, mode=0o700)
        proof = folder / "after.json"
        proof.write_text("{}\n")
        proof.chmod(0o600)
        before = folder / "before.json"
        before.write_text('{"present": false}\n')
        before.chmod(0o600)
        _write_legacy_restore(folder, roots, {"present": False}, roots.codex_home)
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
        ensure_usage_lock(state, tree_usage_name(old_image))
        doc = new_record(roots, "register", desired)
        doc["registration"] = {"id": str(uuid4()), "state": "registered"}
        current_registration = (
            state.path
            / "marketplace-recovery"
            / ("registration." + doc["registration"]["id"])
        )
        current_registration.mkdir(mode=0o700)
        current_before = current_registration / "before.json"
        current_before.write_text('{"present": false}\n')
        current_before.chmod(0o600)
        _write_legacy_restore(
            current_registration, roots, {"present": False}, roots.codex_home
        )
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
    invalid = copy.deepcopy(doc)
    invalid["candidates"] = [row]
    invalid["candidates"][0]["proofs"][0]["relative"] = "upgrades/not-a-uuid.json"
    with pytest.raises(InstallerError, match="invalid workflow UUID"):
        validate_record(invalid, roots)
    for change in ({"schema_version": 3}, {"home": "/foreign"}, {"extra": True}):
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
    with usage_lock(state, device_usage_name(image["dev"], image["ino"]), exclusive=False) as acquired:
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
    lock_path = state.path / "usage" / device_usage_name(info["dev"], info["ino"])
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
        with usage_lock(state, device_usage_name(info["dev"], info["ino"]), exclusive=True) as acquired:
            assert not acquired
    finally:
        process.terminate()
        process.wait(timeout=5)
    with usage_lock(state, device_usage_name(info["dev"], info["ino"]), exclusive=True) as acquired:
        assert acquired


def test_discovery_keeps_cache_without_historical_source(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, state, doc, _row, old = prepared
    candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert findings
    assert old.exists()


def test_register_mode_never_discovers_runtime_recovery(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, state, doc, _row, _old = prepared
    recovery = (
        roots.home
        / ".local/share/blender-lab-mcp/.blender-mcp-installer.fake.runtime.recovery"
    )
    recovery.mkdir(parents=True)
    (recovery / "user-file").write_text("preserve")
    candidates, _findings = discover_candidates(state, roots, doc)
    assert all(row["kind"] == "plugin_cache" for row in candidates)
    assert (recovery / "user-file").read_text() == "preserve"


def test_exact_current_codex_home_discovers_proven_historical_cache(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, doc = _register_case(tmp_path)
    with state_root(roots) as state:
        projection, plugin, cache = _registration_evidence(
            state,
            roots,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        candidates, findings = discover_candidates(state, roots, doc)
    assert findings == []
    assert [row["key"] for row in candidates] == ["plugin_cache:1"]
    assert candidates[0]["content_source"] == str(plugin)
    assert candidates[0]["proofs"][0]["relative"].endswith("/after.json")
    assert projection.exists() and cache.exists()


def test_current_plugin_version_is_excluded_from_discovery(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, doc = _register_case(tmp_path)
    with state_root(roots) as state:
        _projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            version="2",
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert findings == []
    assert (cache / "payload").read_text() == "managed"


@pytest.mark.parametrize(
    "missing", ["after", "source", "projection", "scope", "ambiguous_scope"]
)
def test_incomplete_registration_evidence_keeps_cache(tmp_path, missing):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, doc = _register_case(tmp_path)
    after = None
    if missing == "source":
        after = {"present": True, "source_type": "local"}
    elif missing in {"projection", "scope", "ambiguous_scope"}:
        after = {
            "present": True,
            "source_type": "local",
            "source": str(
                roots.projections / (("d" if missing == "projection" else "a") * 40)
            ),
        }
    with state_root(roots) as state:
        _projection, _plugin, cache = _registration_evidence(
            state, roots, after=after
        )
        restore = state.path / "marketplace-recovery/registration.historical/RESTORE.txt"
        if missing == "scope":
            restore.unlink()
        elif missing == "ambiguous_scope":
            restore.write_text(
                restore.read_text() + f"CODEX_HOME: {roots.home / 'other-codex'}\n"
            )
        candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert findings
    assert (cache / "payload").read_text() == "managed"


def test_foreign_cache_content_is_reported_and_retained(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, doc = _register_case(tmp_path)
    with state_root(roots) as state:
        projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        (cache / "foreign").write_text("user")
        candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert any("differs from projection" in row["reason"] for row in findings)
    assert projection.exists()
    assert (cache / "foreign").read_text() == "user"


def test_orphan_cache_without_any_registration_is_unverified(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, doc = _register_case(tmp_path)
    orphan = roots.caches / "orphan-1"
    orphan.mkdir(parents=True)
    (orphan / "user-file").write_text("preserve")
    with state_root(roots) as state:
        candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert any(item["path"] == str(orphan) for item in findings)
    assert (orphan / "user-file").read_text() == "preserve"


def test_cleanup_pending_reuses_original_image_after_partial_removal(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, state, original, row, old = prepared
    original = update_record(
        state,
        roots,
        original,
        status="cleanup_pending",
        candidates=[row],
        verification={"registration": "passed", "live": "not_run"},
    )
    current = save_record(state, roots, None, new_record(roots, "register", original["desired"]))
    (old / "b").unlink()

    candidates, _findings = discover_candidates(state, roots, current)

    assert len(candidates) == 1
    assert candidates[0]["expected"] == row["expected"]
    assert candidates[0]["state"] == "pending"
    assert candidates[0]["reason"] == "carried durable cleanup baseline"
    assert not (old / "b").exists()


def test_historical_retirement_remains_authoritative_over_later_awaiting_record(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, state, original, row, old = prepared
    registration_ref = str(PurePath(row["proofs"][0]["relative"]).parent)
    original = update_record(
        state,
        roots,
        original,
        status="cleanup_pending",
        candidates=[row],
        verification={"registration": "passed", "live": "not_run"},
        retired_registrations=[registration_ref],
    )
    awaiting = new_record(roots, "register", original["desired"])
    awaiting["registration"] = {"id": row["owner"], "state": "registered"}
    save_record(state, roots, None, awaiting)
    current = save_record(
        state, roots, None, new_record(roots, "register", original["desired"])
    )

    candidates, findings = discover_candidates(state, roots, current)

    assert [item["key"] for item in candidates] == [row["key"]]
    assert not any("unfinished upgrade transaction" in item["reason"] for item in findings)
    assert old.exists()


def test_other_codex_home_references_are_protected_but_not_adopted(prepared):
    from blender_mcp_installer.upgrade_discovery import (
        discover_candidates,
        other_references,
    )

    roots, state, doc, _row, old = prepared
    foreign_home = roots.home / "second-codex"
    foreign_home.mkdir(mode=0o700)
    foreign_roots = UpgradeRoots(roots.home, foreign_home)
    other = save_record(
        state, foreign_roots, None, new_record(foreign_roots, "register", doc["desired"])
    )

    references = other_references(state, roots, doc)
    candidates, _findings = discover_candidates(state, roots, doc)

    assert foreign_roots.projections / other["desired"]["commit"] in references
    assert foreign_roots.caches / other["desired"]["plugin_version"] in references
    assert candidates == []
    assert old.exists()


def test_awaiting_install_references_include_targets_and_recoveries(prepared):
    from blender_mcp_installer.upgrade_discovery import other_references

    roots, state, current, _row, _old = prepared
    other = new_record(roots, "install", current["desired"])
    other["profile"] = _install_profile(roots)
    other["install_id"] = str(uuid4())
    other = save_record(state, roots, None, other)
    installed = _install_roots(roots, other)

    references = set(other_references(state, roots, current))

    assert {
        Path(other["desired"]["projection"]),
        roots.caches / other["desired"]["plugin_version"],
        installed.runtime,
        installed.extension_target,
        installed.runtime_recovery(uuid4_from_text(other["install_id"])),
        installed.extension_recovery(uuid4_from_text(other["install_id"])),
    } <= references


def test_first_install_without_parent_does_not_prove_old_recovery(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, register_doc = _register_case(tmp_path)
    doc = new_record(roots, "install", register_doc["desired"])
    doc["profile"] = _install_profile(roots)
    doc["install_id"] = str(uuid4())
    installed = _install_roots(roots, doc)
    recovery = installed.runtime_recovery(uuid4_from_text(doc["install_id"]))
    recovery.mkdir(parents=True)
    (recovery / "managed").write_text("old")
    with state_root(roots) as state:
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            image = capture_tree(home, recovery.relative_to(roots.home))
        _write_receipt(
            state,
            installed,
            doc["install_id"],
            generation=1,
            parent_install_id=None,
            status="installed",
            runtime_image=image,
        )
        candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert any("lacks exact managed parent provenance" in row["reason"] for row in findings)
    assert (recovery / "managed").read_text() == "old"


def test_exact_parent_postimage_proves_runtime_recovery(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, register_doc = _register_case(tmp_path)
    doc = new_record(roots, "install", register_doc["desired"])
    doc["profile"] = _install_profile(roots)
    doc["install_id"] = str(uuid4())
    parent_id = str(uuid4())
    installed = _install_roots(roots, doc)
    recovery = installed.runtime_recovery(uuid4_from_text(doc["install_id"]))
    recovery.mkdir(parents=True)
    (recovery / "managed").write_text("old")
    with state_root(roots) as state:
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            image = capture_tree(home, recovery.relative_to(roots.home))
        _write_receipt(
            state,
            installed,
            parent_id,
            generation=1,
            parent_install_id=None,
            status="installed",
            runtime_image=image,
        )
        _write_receipt(
            state,
            installed,
            doc["install_id"],
            generation=2,
            parent_install_id=parent_id,
            status="installed",
            runtime_image=image,
        )

        candidates, findings = discover_candidates(state, roots, doc)

    assert findings == []
    assert [row["key"] for row in candidates] == [
        "runtime_recovery:" + doc["install_id"]
    ]
    assert candidates[0]["expected"] == image.to_dict()
    assert len(candidates[0]["proofs"]) == 2


def test_missing_install_profile_preserves_recovery_tree(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, register_doc = _register_case(tmp_path)
    doc = new_record(roots, "install", register_doc["desired"])
    recovery = roots.home / ".local/share/blender-lab-mcp/unclassified.recovery"
    recovery.mkdir(parents=True)
    (recovery / "user-file").write_text("preserve")
    with state_root(roots) as state:
        with pytest.raises(InstallerError, match="installation profile is missing"):
            discover_candidates(state, roots, doc)
    assert (recovery / "user-file").read_text() == "preserve"


def test_invalid_receipt_is_strictly_rejected_without_rewrite(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    roots, register_doc = _register_case(tmp_path)
    doc = new_record(roots, "install", register_doc["desired"])
    doc["profile"] = _install_profile(roots)
    doc["install_id"] = str(uuid4())
    installed = _install_roots(roots, doc)
    recovery = installed.runtime_recovery(uuid4_from_text(doc["install_id"]))
    recovery.mkdir(parents=True)
    (recovery / "managed").write_text("old")
    with state_root(roots) as state:
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            image = capture_tree(home, recovery.relative_to(roots.home))
        receipt = _write_receipt(
            state,
            installed,
            doc["install_id"],
            generation=1,
            parent_install_id=None,
            status="installed",
            runtime_image=image,
        )
        value = json.loads(receipt.read_text())
        value["unknown"] = True
        receipt.write_text(json.dumps(value, sort_keys=True) + "\n")
        before = receipt.read_bytes()
        with pytest.raises(ValueError, match="invalid receipt schema"):
            discover_candidates(state, roots, doc)
        assert receipt.read_bytes() == before
    assert (recovery / "managed").read_text() == "old"


def test_prepared_receipt_recovery_overrides_retirement_reference(tmp_path):
    from blender_mcp_installer.upgrade_discovery import other_references

    roots, doc = _register_case(tmp_path)
    install_id = str(uuid4())
    install_doc = new_record(roots, "install", doc["desired"])
    install_doc["profile"] = _install_profile(roots)
    install_doc["install_id"] = install_id
    installed = _install_roots(roots, install_doc)
    recovery = installed.runtime_recovery(uuid4_from_text(install_id))
    recovery.mkdir(parents=True)
    (recovery / "managed").write_text("old")
    with state_root(roots) as state:
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            image = capture_tree(home, recovery.relative_to(roots.home))
        receipt = _write_receipt(
            state,
            installed,
            install_id,
            generation=1,
            parent_install_id=None,
            status="prepared",
            runtime_image=image,
        )
        before = receipt.read_bytes()
        retired = copy.deepcopy(doc)
        retired["retired_receipts"] = [install_id]
        references = other_references(state, roots, retired)
        assert receipt.read_bytes() == before
    assert recovery in references


def test_legacy_registration_before_protects_projection_and_cache(prepared):
    from blender_mcp_installer.upgrade_discovery import other_references

    roots, state, doc, row, old = prepared
    plugin = Path(row["content_source"])
    projection = plugin.parent.parent
    (plugin / ".codex-plugin").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(json.dumps({"version": "1"}))
    proof = state.path / "marketplace-recovery/registration.legacy-before-only"
    proof.mkdir(mode=0o700)
    (proof / "before.json").write_text(
        json.dumps({"present": True, "source_type": "local", "source": str(projection)})
    )
    (proof / "before.json").chmod(0o600)
    _write_legacy_restore(
        proof,
        roots,
        {"present": True, "source": str(projection)},
        roots.codex_home,
    )

    references = other_references(state, roots, doc)

    assert projection in references
    assert old in references


def _legacy_before_reference(
    state: SafeRoot, roots: UpgradeRoots, projection: Path
) -> tuple[Path, bytes]:
    proof = state.path / "marketplace-recovery/registration.legacy-removed-source"
    proof.mkdir(mode=0o700)
    before = {"present": True, "source_type": "local", "source": str(projection)}
    (proof / "before.json").write_text(json.dumps(before) + "\n")
    (proof / "before.json").chmod(0o600)
    _write_legacy_restore(proof, roots, before, roots.codex_home)
    return proof, (proof / "before.json").read_bytes()


def _finalize_with_real_references(state, roots, doc, row):
    from blender_mcp_installer.upgrade_discovery import other_references

    return finalize_record(
        state,
        roots,
        doc["id"],
        lambda _: (),
        lambda _: ([row], []),
        lambda current: other_references(state, roots, current),
    )


def test_absent_legacy_before_projection_references_no_cache(prepared):
    roots, state, doc, row, old = prepared
    projection = roots.projections / ("d" * 40)
    proof, evidence = _legacy_before_reference(state, roots, projection)

    result = _finalize_with_real_references(state, roots, doc, row)

    assert result["status"] == "complete"
    assert not old.exists()
    assert not projection.exists()
    assert (proof / "before.json").read_bytes() == evidence
    assert (proof / "RESTORE.txt").is_file()


def _assert_legacy_reference_blocks(state, roots, doc, row, old, projection):
    from blender_mcp_installer.upgrade_cleanup import CleanupReferenceUnproven

    _proof, evidence = _legacy_before_reference(state, roots, projection)
    with pytest.raises(CleanupReferenceUnproven) as caught:
        _finalize_with_real_references(state, roots, doc, row)
    assert caught.value.code == "cleanup_reference_unproven"
    assert str(roots.home) not in str(caught.value)
    assert old.exists()
    assert _proof.joinpath("before.json").read_bytes() == evidence
    record = load_record(state, roots, doc["id"])
    assert record["status"] == "cleanup_pending"
    assert record["candidates"][0]["state"] == "pending"


def test_present_legacy_projection_without_manifest_fails_closed(prepared):
    roots, state, doc, row, old = prepared
    projection = roots.projections / ("d" * 40)
    (projection / "plugins/blender-mcp-installer").mkdir(parents=True)

    _assert_legacy_reference_blocks(state, roots, doc, row, old, projection)
    assert projection.is_dir()


@pytest.mark.parametrize("dangling", [False, True])
def test_symlinked_legacy_projection_fails_closed(prepared, dangling):
    roots, state, doc, row, old = prepared
    target = roots.home / "elsewhere"
    if not dangling:
        manifest = target / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "blender-mcp-installer", "version": "1"}))
    projection = roots.projections / ("d" * 40)
    projection.symlink_to(target, target_is_directory=True)

    _assert_legacy_reference_blocks(state, roots, doc, row, old, projection)
    assert projection.is_symlink()


def test_non_directory_legacy_projection_fails_closed(prepared):
    roots, state, doc, row, old = prepared
    projection = roots.projections / ("d" * 40)
    projection.write_text("not a projection")

    _assert_legacy_reference_blocks(state, roots, doc, row, old, projection)
    assert projection.read_text() == "not a projection"


def test_foreign_owned_legacy_projection_fails_closed(prepared, monkeypatch):
    from blender_mcp_installer import filesystem

    roots, state, doc, row, old = prepared
    projection = roots.projections / ("d" * 40)
    manifest = projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "blender-mcp-installer", "version": "1"}))
    foreign = projection.stat().st_ino
    original = filesystem._require_owner

    def foreign_owner(info, uid):
        if info.st_ino == foreign:
            raise ValueError("foreign-owned path")
        original(info, uid)

    monkeypatch.setattr(filesystem, "_require_owner", foreign_owner)

    _assert_legacy_reference_blocks(state, roots, doc, row, old, projection)
    assert manifest.is_file()


def test_absent_projection_ancestor_references_only_source(tmp_path):
    from blender_mcp_installer.upgrade_discovery import source_reference

    roots, _doc = _register_case(tmp_path)
    source = roots.projections / ("d" * 40)
    before = {"present": True, "source_type": "local", "source": str(source)}

    assert not roots.projections.parent.exists()
    assert source_reference(roots, before) == (source,)


def test_symlinked_projection_ancestor_with_absent_leaf_fails_closed(tmp_path):
    from blender_mcp_installer.upgrade_discovery import source_reference

    roots, _doc = _register_case(tmp_path)
    target = roots.home / "elsewhere"
    target.mkdir()
    roots.projections.parent.mkdir(parents=True)
    roots.projections.symlink_to(target, target_is_directory=True)
    before = {
        "present": True,
        "source_type": "local",
        "source": str(roots.projections / ("d" * 40)),
    }

    with pytest.raises(ValueError):
        source_reference(roots, before)


def test_unproven_legacy_registration_scope_fails_closed(prepared):
    from blender_mcp_installer.upgrade_cleanup import CleanupReferenceUnproven

    roots, state, doc, row, old = prepared
    projection = roots.projections / ("d" * 40)
    proof, evidence = _legacy_before_reference(state, roots, projection)
    (proof / "RESTORE.txt").unlink()

    with pytest.raises(CleanupReferenceUnproven):
        _finalize_with_real_references(state, roots, doc, row)
    assert old.exists()
    assert (proof / "before.json").read_bytes() == evidence
    assert load_record(state, roots, doc["id"])["status"] == "cleanup_pending"


def test_non_object_legacy_manifest_fails_closed(prepared):
    roots, state, doc, row, old = prepared
    projection = roots.projections / ("d" * 40)
    manifest = projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("[]")

    _assert_legacy_reference_blocks(state, roots, doc, row, old, projection)
    assert manifest.read_text() == "[]"


def test_foreign_registration_evidence_cannot_authorize_or_retire_current_cache(tmp_path):
    from blender_mcp_installer.upgrade_discovery import (
        current_paths,
        discover_candidates,
        other_references,
    )

    roots, current = _register_case(tmp_path)
    foreign_home = roots.home / "foreign-codex"
    foreign_home.mkdir(mode=0o700)
    foreign = UpgradeRoots(roots.home, foreign_home)
    registration_id = str(uuid4())
    with state_root(roots) as state:
        projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            registration_name=registration_id,
            restore_codex_home=foreign_home,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        historical = new_record(
            foreign,
            "register",
            {
                **current["desired"],
                "commit": "a" * 40,
                "plugin_version": "1",
                "projection": str(projection),
            },
        )
        historical["registration"] = {"id": registration_id, "state": "registered"}
        historical = save_record(state, foreign, None, historical)
        current = save_record(state, roots, None, current)

        candidates, findings = discover_candidates(state, roots, current)
        result = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )

        assert candidates == []
        assert any("another CODEX_HOME" in item["reason"] for item in findings)
        assert cache.exists()
        assert result["retired_registrations"] == []
        assert load_record(state, foreign, historical["id"])["status"] == "awaiting_verification"
        assert_rollback_available(
            state,
            foreign,
            registration_ref="marketplace-recovery/registration." + registration_id,
        )


def test_foreign_legacy_before_resolves_cache_against_exact_original_root(tmp_path):
    from blender_mcp_installer.upgrade_discovery import other_references

    roots, doc = _register_case(tmp_path)
    foreign_home = roots.home / "foreign-codex"
    foreign_home.mkdir(mode=0o700)
    projection = roots.projections / ("a" * 40)
    manifest = projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "blender-mcp-installer", "version": "1"}))
    current_cache = roots.caches / "1"
    foreign_cache = foreign_home / "plugins/cache/official-blender-mcp/blender-mcp-installer/1"
    current_cache.mkdir(parents=True)
    foreign_cache.mkdir(parents=True)
    with state_root(roots) as state:
        proof = state.path / "marketplace-recovery/registration.legacy-foreign"
        proof.mkdir(parents=True, mode=0o700)
        before = {"present": True, "source_type": "local", "source": str(projection)}
        (proof / "before.json").write_text(json.dumps(before) + "\n")
        (proof / "before.json").chmod(0o600)
        _write_legacy_restore(proof, roots, before, foreign_home)

        references = other_references(state, roots, doc)

    assert projection in references
    assert foreign_cache in references
    assert current_cache not in references


def test_conflicting_registration_scope_fails_closed_without_retirement(tmp_path):
    from blender_mcp_installer.upgrade_discovery import (
        current_paths,
        discover_candidates,
        other_references,
    )

    roots, current = _register_case(tmp_path)
    foreign_home = roots.home / "foreign-codex"
    foreign_home.mkdir(mode=0o700)
    registration_id = str(uuid4())
    with state_root(roots) as state:
        projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            registration_name=registration_id,
            restore_codex_home=foreign_home,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        historical = new_record(
            roots,
            "register",
            {
                **current["desired"],
                "commit": "a" * 40,
                "plugin_version": "1",
                "projection": str(projection),
            },
        )
        historical["registration"] = {"id": registration_id, "state": "registered"}
        historical = save_record(state, roots, None, historical)
        current = save_record(state, roots, None, current)

        candidates, findings = discover_candidates(state, roots, current)
        result = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )

        assert candidates == []
        assert any(
            "conflicting registration CODEX_HOME" in item["reason"] for item in findings
        )
        assert cache.exists()
        assert result["retired_registrations"] == []
        assert load_record(state, roots, historical["id"])["status"] == "awaiting_verification"
        assert_rollback_available(
            state,
            roots,
            registration_ref="marketplace-recovery/registration." + registration_id,
        )
def test_registration_root_binding_is_guarded_through_deletion(
    tmp_path, monkeypatch
):
    from blender_mcp_installer.upgrade_discovery import (
        current_paths,
        discover_candidates,
        other_references,
    )

    roots, current = _register_case(tmp_path)
    with state_root(roots) as state:
        _projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        current = save_record(state, roots, None, current)
        candidates, _findings = discover_candidates(state, roots, current)
        restore = state.path / "marketplace-recovery/registration.historical/RESTORE.txt"
        assert any(proof["relative"].endswith("/RESTORE.txt") for proof in candidates[0]["proofs"])
        image = candidates[0]["expected"]
        ensure_usage_lock(state, device_usage_name(image["dev"], image["ino"]))
        original_remove = upgrade_cleanup.conditional_remove_tree

        def remove_after_root_binding_drift(reference, expected, guards, fault):
            guarded = {guard.path for guard, _image in guards}
            assert restore in guarded
            restore.write_text("changed\n")
            return original_remove(reference, expected, guards, fault)

        monkeypatch.setattr(
            upgrade_cleanup,
            "conditional_remove_tree",
            remove_after_root_binding_drift,
        )
        result = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )

    assert result["candidates"][0]["state"] == "conflict"
    assert result["candidates"][0]["reason"] == "transaction state conflict"
    assert cache.exists()


def test_same_root_awaiting_registration_is_not_a_retirement_candidate(tmp_path):
    from blender_mcp_installer.upgrade_discovery import (
        current_paths,
        discover_candidates,
        other_references,
    )

    roots, current = _register_case(tmp_path)
    registration_id = str(uuid4())
    with state_root(roots) as state:
        projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            registration_name=registration_id,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        historical = new_record(
            roots,
            "register",
            {
                **current["desired"],
                "commit": "a" * 40,
                "plugin_version": "1",
                "projection": str(projection),
            },
        )
        historical["registration"] = {"id": registration_id, "state": "registered"}
        historical = save_record(state, roots, None, historical)
        current = save_record(state, roots, None, current)
        with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
            before = capture_tree(codex, cache.relative_to(roots.codex_home))
        ensure_usage_lock(state, device_usage_name(before.dev, before.ino))

        candidates, findings = discover_candidates(state, roots, current)
        result = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )

        assert candidates == []
        assert any("unfinished upgrade transaction" in item["reason"] for item in findings)
        assert cache.exists()
        assert result["retired_registrations"] == []
        assert load_record(state, roots, historical["id"])["status"] == "awaiting_verification"
        assert_rollback_available(
            state,
            roots,
            registration_ref="marketplace-recovery/registration." + registration_id,
        )
        historical = update_record(state, roots, historical, status="cancelled")
        resumed = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )
        assert resumed["candidates"] == []
        assert cache.exists()
        assert_rollback_available(
            state,
            roots,
            registration_ref="marketplace-recovery/registration." + registration_id,
        )
        retry = new_record(roots, "register", current["desired"])
        retry = save_record(state, roots, None, retry)
        retry_candidates, _retry_findings = discover_candidates(state, roots, retry)
        assert len(retry_candidates) == 1
        assert retry_candidates[0]["expected"] == before.to_dict()
        migrated = finalize_record(
            state,
            roots,
            retry["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )
        assert migrated["status"] == "complete"
        assert not cache.exists()
        with pytest.raises(RollbackUnavailable):
            assert_rollback_available(
                state,
                roots,
                registration_ref="marketplace-recovery/registration." + registration_id,
            )


def test_completed_same_root_journal_can_prove_historical_migration(tmp_path):
    from blender_mcp_installer.upgrade_discovery import (
        current_paths,
        discover_candidates,
        other_references,
    )

    roots, current = _register_case(tmp_path)
    registration_id = str(uuid4())
    with state_root(roots) as state:
        projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            registration_name=registration_id,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        (state.path / f"marketplace-recovery/registration.{registration_id}/RESTORE.txt").unlink()
        historical = new_record(
            roots,
            "register",
            {
                **current["desired"],
                "commit": "a" * 40,
                "plugin_version": "1",
                "projection": str(projection),
            },
        )
        historical["registration"] = {"id": registration_id, "state": "registered"}
        historical = save_record(state, roots, None, historical)
        historical = update_record(
            state,
            roots,
            historical,
            status="cleanup_pending",
            verification={"registration": "passed", "live": "not_run"},
        )
        update_record(state, roots, historical, status="complete")
        current = save_record(state, roots, None, current)

        candidates, findings = discover_candidates(state, roots, current)
        assert findings == []
        assert len(candidates) == 1
        assert any(proof["relative"].startswith("upgrades/") for proof in candidates[0]["proofs"])
        image = candidates[0]["expected"]
        ensure_usage_lock(state, device_usage_name(image["dev"], image["ino"]))
        result = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )
        assert result["status"] == "complete"
        assert not cache.exists()
        with pytest.raises(RollbackUnavailable):
            assert_rollback_available(
                state,
                roots,
                registration_ref="marketplace-recovery/registration." + registration_id,
            )


@pytest.mark.parametrize("changed_field", ["codex_home", "status"])
def test_changed_journal_snapshot_cannot_authorize_cleanup(
    tmp_path, monkeypatch, changed_field
):
    from blender_mcp_installer import upgrade_discovery
    from blender_mcp_installer.upgrade_discovery import (
        current_paths,
        discover_candidates,
        other_references,
    )

    roots, current = _register_case(tmp_path)
    foreign_home = roots.home / "foreign-codex"
    foreign_home.mkdir(mode=0o700)
    registration_id = str(uuid4())
    with state_root(roots) as state:
        projection, _plugin, cache = _registration_evidence(
            state,
            roots,
            registration_name=registration_id,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        (state.path / f"marketplace-recovery/registration.{registration_id}/RESTORE.txt").unlink()
        historical = new_record(
            roots,
            "register",
            {
                **current["desired"],
                "commit": "a" * 40,
                "plugin_version": "1",
                "projection": str(projection),
            },
        )
        historical["registration"] = {"id": registration_id, "state": "registered"}
        historical = save_record(state, roots, None, historical)
        historical = update_record(
            state,
            roots,
            historical,
            status="cleanup_pending",
            verification={"registration": "passed", "live": "not_run"},
        )
        historical = update_record(state, roots, historical, status="complete")
        current = save_record(state, roots, None, current)
        journal_relative = PurePath("upgrades", historical["id"] + ".json")
        journal_path = state.path / journal_relative
        original_read = upgrade_discovery.read_evidence
        changed = []

        def read_after_journal_change(safe, relative):
            if relative == journal_relative and not changed:
                changed.append(True)
                value = json.loads(journal_path.read_bytes())
                value[changed_field] = (
                    str(foreign_home)
                    if changed_field == "codex_home"
                    else "awaiting_verification"
                )
                journal_path.write_text(json.dumps(value))
            return original_read(safe, relative)

        monkeypatch.setattr(
            upgrade_discovery, "read_evidence", read_after_journal_change
        )
        result = finalize_record(
            state,
            roots,
            current["id"],
            lambda doc: current_paths(roots, doc),
            lambda doc: discover_candidates(state, roots, doc),
            lambda doc: other_references(state, roots, doc),
        )

        assert changed == [True]
        assert result["status"] == "complete"
        assert result["candidates"] == []
        assert any("upgrade journal changed" in item["reason"] for item in result["findings"])
        assert cache.exists()
        assert result["retired_registrations"] == []
        assert_rollback_available(
            state,
            roots,
            registration_ref="marketplace-recovery/registration." + registration_id,
        )


def test_full_finalize_probes_live_once_and_rechecks_snapshot(prepared, monkeypatch):
    from types import SimpleNamespace

    from blender_mcp_installer import upgrade_integration as integration
    from blender_mcp_installer import verification

    roots, state, prior, row, old = prepared
    profile = {
        "executable": str(roots.home / "Blender"),
        "architecture": "arm64",
        "version": "5.2.0",
        "resources": str(roots.home / "profile"),
        "config": str(roots.home / "profile/config"),
        "extensions": str(roots.home / "profile/extensions"),
    }
    document = new_record(roots, "install", prior["desired"])
    document["profile"] = profile
    document["registration"] = prior["registration"]
    document["install_id"] = str(uuid4())
    document = save_record(state, roots, None, document)
    context = SimpleNamespace(
        roots=SimpleNamespace(
            home=roots.home,
            codex_home=roots.codex_home,
            runtime=roots.home / ".local/share/blender-lab-mcp/runtime",
            receipt=lambda identifier: state.path / "receipts" / f"{identifier}.json",
        ),
        host=SimpleNamespace(codex_bin=Path("/fake/codex"), env={}),
        source_bundle=object(),
        blender=object(),
    )
    executable = context.roots.runtime / "bin/python"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    live = []
    fingerprints = []
    monkeypatch.setattr(integration, "desired_from_context", lambda _context: prior["desired"])
    monkeypatch.setattr(integration, "profile_from_context", lambda _context: profile)
    monkeypatch.setattr(
        integration,
        "installation_fingerprint",
        lambda *_args: (fingerprints.append("read") or ("stable",)),
    )
    monkeypatch.setattr(verification, "verify_live", lambda *_args: live.append("live"))
    monkeypatch.setattr(integration, "discover_candidates", lambda *_args: ([row], []))
    monkeypatch.setattr(integration, "other_references", lambda *_args: ())

    result = integration.finalize_install_locked(
        state, context, document["id"], NoOpFaultInjector()
    )

    assert result["status"] == "complete" and not old.exists()
    assert live == ["live"] and len(fingerprints) >= 4


def test_full_finalize_stops_after_recorded_cleanup_when_snapshot_changes(
    prepared, monkeypatch
):
    from types import SimpleNamespace

    from blender_mcp_installer import upgrade_integration as integration
    from blender_mcp_installer import verification

    roots, state, prior, first, first_path = prepared
    second_path = roots.caches / "0.9.0"
    second_path.mkdir(mode=0o700)
    (second_path / "a").write_bytes(b"old-a")
    (second_path / "b").write_bytes(b"old-b")
    with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
        second_image = capture_tree(codex, second_path.relative_to(roots.codex_home))
    ensure_usage_lock(state, device_usage_name(second_image.dev, second_image.ino))
    second = copy.deepcopy(first)
    second.update(
        key="plugin_cache:0.9.0",
        version="0.9.0",
        expected=second_image.to_dict(),
    )
    profile = {
        "executable": str(roots.home / "Blender"),
        "architecture": "arm64",
        "version": "5.2.0",
        "resources": str(roots.home / "profile"),
        "config": str(roots.home / "profile/config"),
        "extensions": str(roots.home / "profile/extensions"),
    }
    document = new_record(roots, "install", prior["desired"])
    document["profile"] = profile
    document["registration"] = prior["registration"]
    document["install_id"] = str(uuid4())
    document = save_record(state, roots, None, document)
    context = SimpleNamespace(
        roots=SimpleNamespace(
            home=roots.home,
            codex_home=roots.codex_home,
            runtime=roots.home / ".local/share/blender-lab-mcp/runtime",
            receipt=lambda identifier: state.path / "receipts" / f"{identifier}.json",
        ),
        host=SimpleNamespace(codex_bin=Path("/fake/codex"), env={}),
        source_bundle=object(),
        blender=object(),
    )
    executable = context.roots.runtime / "bin/python"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o700)
    live = []
    changed = False
    fingerprints = []

    class ChangeAfterFirstRecord(NoOpFaultInjector):
        def hit(self, point):
            nonlocal changed
            if point == "after_upgrade_candidate_record":
                changed = True

    monkeypatch.setattr(integration, "desired_from_context", lambda _context: prior["desired"])
    monkeypatch.setattr(integration, "profile_from_context", lambda _context: profile)
    monkeypatch.setattr(
        integration,
        "installation_fingerprint",
        lambda *_args: (fingerprints.append(changed) or (changed,)),
    )
    monkeypatch.setattr(verification, "verify_live", lambda *_args: live.append("live"))
    monkeypatch.setattr(integration, "discover_candidates", lambda *_args: ([first, second], []))
    monkeypatch.setattr(integration, "other_references", lambda *_args: ())

    with pytest.raises(InstallerError, match="snapshot changed during cleanup"):
        integration.finalize_install_locked(
            state, context, document["id"], ChangeAfterFirstRecord()
        )

    persisted = load_record(state, roots, document["id"], recover=True)
    assert persisted is not None and persisted["status"] == "cleanup_pending"
    assert persisted["candidates"][0]["state"] == "removed"
    assert persisted["candidates"][0]["reason"] == "verified deletion"
    assert persisted["candidates"][1]["state"] == "pending"
    assert not first_path.exists() and second_path.exists()
    with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
        assert capture_tree(codex, second_path.relative_to(roots.codex_home)) == second_image
    assert live == ["live"]
    assert fingerprints[-1] is True and all(not value for value in fingerprints[:-1])


@pytest.mark.parametrize("interrupt_before_cleanup", [False, True])
def test_exact_registration_creates_migration_journal_when_old_cache_remains(
    prepared, monkeypatch, interrupt_before_cleanup, capsys
):
    from types import SimpleNamespace
    from blender_mcp_installer import upgrade_integration
    from blender_mcp_installer.upgrade_state import record_ids
    import project_marketplace as marketplace

    roots, state, prior, row, old = prepared
    update_record(state, roots, prior, status="cancelled")
    projection = Path(prior["desired"]["projection"])
    plugin = projection / "plugins/blender-mcp-installer"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / "artifacts").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "blender-mcp-installer", "version": "2"})
    )
    (plugin / "artifacts/manifest.json").write_text(json.dumps({"bundle_version": "1.0.0"}))
    called = []
    config = roots.codex_home / "config.toml"
    config_text = (
        '[marketplaces.official-blender-mcp]\nsource_type = "local"\n'
        f"source = {json.dumps(str(projection))}\n"
    )
    config.write_text(config_text)
    monkeypatch.setattr(upgrade_integration, "inspect_registration", lambda *_args: None)
    monkeypatch.setattr(upgrade_integration, "discover_candidates", lambda *_args: ([row], []))
    monkeypatch.setattr(upgrade_integration, "other_references", lambda *_args: ())
    monkeypatch.setattr(
        marketplace, "inspect_registration",
        lambda *_args: SimpleNamespace(cache=SimpleNamespace(entries=())),
    )
    monkeypatch.setattr(marketplace, "discover_candidates", lambda *_args: ([row], []))
    monkeypatch.setattr(
        marketplace, "_register", lambda *_args, **_kwargs: called.append("register")
    )
    args = SimpleNamespace(reviewed_commit="b" * 40, codex="/fake/codex", workflow_id=None)
    if interrupt_before_cleanup:
        def interrupt(*_args):
            raise InstallerError("interrupted before cleanup")

        monkeypatch.setattr(marketplace, "finalize_register_locked", interrupt)
        with pytest.raises(InstallerError, match="interrupted before cleanup"):
            marketplace._run_workflow(args, state, roots, projection)
        identity, = set(record_ids(state)) - {prior["id"]}
        recovery = roots.state / "marketplace-recovery" / ("registration." + identity)
        codex_calls = []

        def codex_stub(codex, home, codex_home, *arguments):
            assert (codex, home, codex_home) == (Path(args.codex), roots.home, roots.codex_home)
            codex_calls.append(arguments)
            if arguments == marketplace.REMOVE_MARKETPLACE:
                config.write_text("")
            else:
                assert arguments == ("plugin", "marketplace", "add", str(projection))
                config.write_text(config_text)
            return ""

        monkeypatch.setattr(marketplace, "_codex", codex_stub)
        marketplace._restore_evidence(SimpleNamespace(
            home=str(roots.home), codex_home=str(roots.codex_home),
            codex=args.codex, recovery=str(recovery),
        ))
        assert json.loads(capsys.readouterr().out)["marketplace_source_restored"] is True
        assert len(codex_calls) == 2 and config.read_text() == config_text
        assert old.exists()
        assert load_record(state, roots, identity)["status"] == "awaiting_verification"
        for field, value in (("HOME", roots.home), ("CODEX_HOME", roots.codex_home),
                             ("CODEX_BIN", args.codex)):
            assert f"{field}: {value}" in (recovery / "RESTORE.txt").read_text().splitlines()
    else:
        result = marketplace._run_workflow(args, state, roots, projection)
        assert result["status"] == "complete" and not old.exists()
        assert result["workflow_id"] != prior["id"]
    assert len(record_ids(state)) == 2 and called == []


def _renumbered(image, device, *, only=None, keep=None):
    """Rewrite device numbers as a volume remount does, keeping the digest consistent."""
    import dataclasses
    import hashlib

    from blender_mcp_installer.model import FileImage

    if isinstance(image, FileImage):
        return dataclasses.replace(image, dev=device)
    entries = tuple(
        dataclasses.replace(entry, dev=device)
        if (only is None or entry.path == only) and entry.path != keep
        else entry
        for entry in image.entries
    )
    encoded = json.dumps(
        [entry.to_dict() for entry in entries], sort_keys=True, separators=(",", ":")
    ).encode()
    return dataclasses.replace(
        image,
        dev=device if only is None else image.dev,
        entries=entries,
        digest=hashlib.sha256(encoded).hexdigest(),
    )


def _replace_file_inode(path: Path) -> None:
    info = path.stat()
    fresh = path.with_name(path.name + ".fresh")
    fresh.write_bytes(path.read_bytes())
    fresh.chmod(info.st_mode & 0o7777)
    os.replace(fresh, path)
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))


def _replace_with_copy(recovery: Path) -> None:
    import shutil

    parked = recovery.with_name("parked")
    recovery.rename(parked)
    shutil.copytree(parked, recovery)
    shutil.rmtree(parked)


RUNTIME_DRIFTS = {
    "bytecode": lambda root: (
        (root / "pkg/__pycache__/mod.cpython-313.pyc").write_bytes(b"new cache"),
        (root / "pkg/__pycache__/mod.cpython-312.pyc").write_bytes(b"rewritten cache"),
        (root / "__pycache__").mkdir(),
        (root / "__pycache__/top.cpython-313.opt-1.pyc").write_bytes(b"optimized"),
    ),
    "source": lambda root: (root / "pkg/mod.py").write_text("managed = 2\n"),
    "orphan_bytecode": lambda root: (
        root / "pkg/__pycache__/ghost.cpython-313.pyc"
    ).write_bytes(b"no source"),
    "foreign_in_cache": lambda root: (
        root / "pkg/__pycache__/notes.txt"
    ).write_text("user"),
    "new_file": lambda root: (root / "pkg/extra.py").write_text("user"),
    "nested_cache": lambda root: (root / "pkg/__pycache__/__pycache__").mkdir(),
    "replaced_file": lambda root: _replace_file_inode(root / "pkg/mod.py"),
    "copied_tree": _replace_with_copy,
}


def _drifted_runtime_case(tmp_path, drift):
    roots, register_doc = _register_case(tmp_path)
    doc = new_record(roots, "install", register_doc["desired"])
    doc["profile"] = _install_profile(roots)
    doc["install_id"] = str(uuid4())
    installed = _install_roots(roots, doc)
    recovery = installed.runtime_recovery(uuid4_from_text(doc["install_id"]))
    (recovery / "pkg/__pycache__").mkdir(parents=True)
    (recovery / "pkg/mod.py").write_text("managed = 1\n")
    (recovery / "pkg/__pycache__/mod.cpython-312.pyc").write_bytes(b"install cache")
    (recovery / "top.py").write_text("top = 1\n")
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        post = capture_tree(home, recovery.relative_to(roots.home))
        drift(recovery)
        pre = capture_tree(home, recovery.relative_to(roots.home))
    return roots, doc, installed, recovery, post, pre


def _discover_drifted(roots, doc, installed, post, pre):
    from blender_mcp_installer.upgrade_discovery import discover_candidates

    parent_id = str(uuid4())
    with state_root(roots) as state:
        _write_receipt(
            state, installed, parent_id, generation=1, parent_install_id=None,
            status="installed", runtime_image=post,
        )
        _write_receipt(
            state, installed, doc["install_id"], generation=2,
            parent_install_id=parent_id, status="installed", runtime_image=pre,
        )
        return discover_candidates(state, roots, doc)


@pytest.mark.parametrize("renumber", [False, True])
def test_bytecode_and_remount_drift_keep_parent_provenance(tmp_path, renumber):
    roots, doc, installed, recovery, post, pre = _drifted_runtime_case(
        tmp_path, RUNTIME_DRIFTS["bytecode"]
    )
    assert pre != post
    if renumber:
        pre = _renumbered(pre, pre.dev + 1)

    candidates, findings = _discover_drifted(roots, doc, installed, post, pre)

    assert findings == []
    assert [row["key"] for row in candidates] == ["runtime_recovery:" + doc["install_id"]]
    assert candidates[0]["expected"] == pre.to_dict()
    assert (recovery / "pkg/__pycache__/mod.cpython-313.pyc").exists()


@pytest.mark.parametrize(
    "drift",
    [
        "source",
        "orphan_bytecode",
        "foreign_in_cache",
        "new_file",
        "nested_cache",
        "replaced_file",
        "copied_tree",
    ],
)
def test_unexplained_preimage_drift_stays_unverified(tmp_path, drift):
    roots, doc, installed, recovery, post, pre = _drifted_runtime_case(
        tmp_path, RUNTIME_DRIFTS[drift]
    )

    candidates, findings = _discover_drifted(roots, doc, installed, post, pre)

    assert candidates == []
    assert [row["reason"] for row in findings] == [
        "preimage lacks exact managed parent provenance"
    ]
    assert recovery.is_dir()


def test_partial_device_renumbering_is_not_a_remount(tmp_path):
    roots, doc, installed, recovery, post, _pre = _drifted_runtime_case(
        tmp_path, lambda _root: None
    )
    split = _renumbered(post, post.dev + 1, only="pkg/mod.py")

    candidates, findings = _discover_drifted(roots, doc, installed, post, split)

    assert candidates == []
    assert [row["reason"] for row in findings] == [
        "preimage lacks exact managed parent provenance"
    ]


@pytest.fixture
def legacy_recovery(tmp_path):
    roots, register_doc = _register_case(tmp_path)
    doc = new_record(roots, "install", register_doc["desired"])
    doc["profile"] = _install_profile(roots)
    doc["install_id"] = str(uuid4())
    doc["registration"] = {"id": doc["id"], "state": "registered"}
    owner = str(uuid4())
    recovery = _install_roots(roots, doc).runtime_recovery(UUID(owner))
    (recovery / "bin").mkdir(parents=True)
    (recovery / "bin/python").write_text("legacy")
    with state_root(roots) as state:
        receipt = state.path / "receipts" / f"{owner}.json"
        receipt.parent.mkdir(mode=0o700)
        receipt.write_text("{}\n")
        receipt.chmod(0o600)
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            image = capture_tree(home, recovery.relative_to(roots.home))
        proof = capture_file(state, receipt.relative_to(state.path))
        row = {
            "key": "runtime_recovery:" + owner, "kind": "runtime_recovery",
            "owner": owner, "version": None, "expected": image.to_dict(),
            "proofs": [{"relative": f"receipts/{owner}.json", "expected": proof.to_dict()}],
            "content_source": None, "content_sha256": None, "lease_known": False,
            "state": "pending", "reason": "",
        }
        doc = save_record(state, roots, None, doc)
        yield roots, state, doc, row, recovery, proof


def _finalize_row(state, roots, doc, row):
    return finalize_record(
        state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ()
    )


def test_legacy_recovery_retired_before_host_boot_is_removed(legacy_recovery, monkeypatch):
    roots, state, doc, row, recovery, proof = legacy_recovery
    monkeypatch.setattr(upgrade_cleanup, "host_boot_time_ns", lambda: proof.mtime_ns + 1)

    result = _finalize_row(state, roots, doc, row)

    assert result["status"] == "complete"
    assert result["candidates"][0]["reason"] == "verified deletion"
    assert not recovery.exists()


@pytest.mark.parametrize("boot", ["same_boot", "unavailable"])
def test_legacy_recovery_without_restart_evidence_stays_deferred(
    legacy_recovery, monkeypatch, boot
):
    roots, state, doc, row, recovery, proof = legacy_recovery

    def boot_time():
        if boot == "unavailable":
            raise InstallerError("host boot time unavailable")
        return proof.mtime_ns

    monkeypatch.setattr(upgrade_cleanup, "host_boot_time_ns", boot_time)

    result = _finalize_row(state, roots, doc, row)

    assert result["status"] == "cleanup_pending"
    assert result["candidates"][0]["state"] == "deferred_in_use"
    assert result["candidates"][0]["reason"] == "legacy usage is not proven idle"
    assert (recovery / "bin/python").read_text() == "legacy"


def test_host_restart_never_proves_plugin_cache_idle(prepared, monkeypatch):
    roots, state, doc, row, old = prepared
    row["lease_known"] = False
    monkeypatch.setattr(upgrade_cleanup, "host_boot_time_ns", lambda: 2**62)

    result = _finalize_row(state, roots, doc, row)

    assert result["candidates"][0]["reason"] == "legacy usage is not proven idle"
    assert old.exists()


def test_remounted_recovery_is_removed_from_its_recorded_image(legacy_recovery, monkeypatch):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, recovery, proof = legacy_recovery
    image = TreeImage.from_dict(row["expected"])
    row["expected"] = _renumbered(image, image.dev + 7).to_dict()
    row["proofs"][0]["expected"] = _renumbered(proof, proof.dev + 7).to_dict()
    monkeypatch.setattr(upgrade_cleanup, "host_boot_time_ns", lambda: proof.mtime_ns + 1)

    result = _finalize_row(state, roots, doc, row)

    assert result["status"] == "complete" and not recovery.exists()
    assert result["candidates"][0]["expected"] == row["expected"]


@pytest.mark.parametrize("drift", ["split_device", "stale_entry", "content"])
def test_remount_never_hides_other_recovery_drift(legacy_recovery, monkeypatch, drift):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, recovery, proof = legacy_recovery
    image = TreeImage.from_dict(row["expected"])
    if drift == "split_device":
        row["expected"] = _renumbered(image, image.dev + 7, only="bin/python").to_dict()
    elif drift == "stale_entry":
        row["expected"] = _renumbered(image, image.dev + 7, keep="bin/python").to_dict()
    else:
        row["expected"] = _renumbered(image, image.dev + 7).to_dict()
        (recovery / "bin/extra").write_text("user")
    monkeypatch.setattr(upgrade_cleanup, "host_boot_time_ns", lambda: proof.mtime_ns + 1)

    result = _finalize_row(state, roots, doc, row)

    assert result["candidates"][0]["state"] == "conflict"
    assert (recovery / "bin/python").read_text() == "legacy"


@pytest.mark.parametrize("prepared", [None, b"inode-v1\n"], indirect=True, ids=["unmarked", "v1"])
def test_remounted_leased_cache_honours_both_device_identities(prepared):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, old = prepared
    image = TreeImage.from_dict(row["expected"])
    row["expected"] = _renumbered(image, image.dev + 7).to_dict()
    ensure_usage_lock(state, device_usage_name(image.dev + 7, image.ino))
    with usage_lock(state, device_usage_name(image.dev, image.ino), exclusive=False) as acquired:
        assert acquired
        first = _finalize_row(state, roots, doc, row)
    assert first["candidates"][0]["reason"] == "version lease is busy or missing"
    assert old.exists()

    second = finalize_record(
        state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ()
    )

    assert second["status"] == "complete" and not old.exists()


def test_host_boot_time_parses_kernel_boottime(monkeypatch):
    import time

    if sys.platform == "darwin":
        real = upgrade_cleanup.host_boot_time_ns()
        assert 0 < real < time.time_ns()

    class Result:
        stdout = "{ sec = 12, usec = 5 } Thu Jan  1 00:00:12 1970\n"

    monkeypatch.setattr(upgrade_cleanup.subprocess, "run", lambda *_a, **_k: Result())
    assert upgrade_cleanup.host_boot_time_ns() == 12_000_005_000
    Result.stdout = "{ sec = 12, usec = 1000000 }\n"
    with pytest.raises(InstallerError, match="host boot time unavailable"):
        upgrade_cleanup.host_boot_time_ns()


def _superseded(state, roots, doc, row, **desired):
    old = new_record(roots, "register", {**doc["desired"], **desired})
    old["registration"] = {"id": old["id"], "state": "registered"}
    old = save_record(state, roots, None, old)
    return update_record(
        state, roots, old, status="cleanup_pending", candidates=[row],
        verification={"registration": "passed", "live": "not_run"},
    )


def test_superseded_journal_completes_once_its_baselines_are_absent(prepared):
    import shutil

    roots, state, doc, row, old = prepared
    superseded = _superseded(
        state, roots, doc, row, commit="a" * 40, plugin_version="1",
        projection=str(roots.projections / ("a" * 40)),
    )
    finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
    assert load_record(state, roots, superseded["id"]) == superseded
    shutil.rmtree(old)

    finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())

    retired = load_record(state, roots, superseded["id"])
    assert retired["status"] == "complete"
    assert [(item["state"], item["reason"]) for item in retired["candidates"]] == [
        ("removed", "verified absent")
    ]
    assert Path(row["content_source"]).is_dir()


def test_journal_for_current_release_is_not_retired_by_another_workflow(prepared):
    import shutil

    roots, state, doc, row, old = prepared
    same_release = _superseded(state, roots, doc, row)
    shutil.rmtree(old)

    finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())

    assert load_record(state, roots, same_release["id"]) == same_release


def test_host_restart_never_replaces_an_available_lease(legacy_recovery, monkeypatch):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, recovery, proof = legacy_recovery
    row["lease_known"] = True
    image = TreeImage.from_dict(row["expected"])
    ensure_usage_lock(state, device_usage_name(image.dev, image.ino))
    monkeypatch.setattr(upgrade_cleanup, "host_boot_time_ns", lambda: proof.mtime_ns + 1)
    with usage_lock(state, device_usage_name(image.dev, image.ino), exclusive=False) as acquired:
        assert acquired
        busy = _finalize_row(state, roots, doc, row)
    assert busy["candidates"][0]["reason"] == "version lease is busy or missing"
    assert recovery.is_dir()

    released = finalize_record(
        state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ()
    )

    assert released["status"] == "complete" and not recovery.exists()


@pytest.mark.parametrize("prepared", [None, b"inode-v1\n"], indirect=True, ids=["unmarked", "v1"])
def test_remounted_cache_without_new_device_lease_file_is_removed(prepared):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, old = prepared
    image = TreeImage.from_dict(row["expected"])
    row["expected"] = _renumbered(image, image.dev + 7).to_dict()
    ensure_usage_lock(state, device_usage_name(image.dev + 7, image.ino))
    (state.path / "usage" / device_usage_name(image.dev, image.ino)).unlink()

    result = _finalize_row(state, roots, doc, row)

    assert result["status"] == "complete" and not old.exists()


V2 = b"inode-v2\n"


@pytest.mark.parametrize("prepared", [V2], indirect=True)
def test_remounted_v2_cache_is_guarded_by_its_inode_lease(prepared):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, old = prepared
    image = TreeImage.from_dict(row["expected"])
    row["expected"] = _renumbered(image, image.dev + 7).to_dict()
    with usage_lock(state, usage_name(image.ino), exclusive=False) as acquired:
        assert acquired
        busy = _finalize_row(state, roots, doc, row)
    assert busy["candidates"][0]["reason"] == "version lease is busy or missing"
    assert old.exists()

    released = finalize_record(
        state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ()
    )

    assert released["status"] == "complete" and not old.exists()
    assert sorted(path.name for path in (state.path / "usage").iterdir()) == [
        usage_name(image.ino)
    ]


@pytest.mark.parametrize("prepared", [V2], indirect=True)
@pytest.mark.parametrize("remount", [False, True])
def test_missing_v2_lease_stays_fail_closed(prepared, remount):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, old = prepared
    image = TreeImage.from_dict(row["expected"])
    if remount:
        row["expected"] = _renumbered(image, image.dev + 7).to_dict()
    (state.path / "usage" / usage_name(image.ino)).unlink()
    # Device-named leases never stand in for the inode lease of a v2 tree.
    for device in (image.dev, image.dev + 7):
        ensure_usage_lock(state, device_usage_name(device, image.ino))

    result = _finalize_row(state, roots, doc, row)

    assert result["candidates"][0]["reason"] == "version lease is busy or missing"
    assert old.exists()


@pytest.mark.parametrize("prepared", [None, b"inode-v1\n"], indirect=True, ids=["unmarked", "v1"])
@pytest.mark.parametrize("remount", [False, True])
def test_device_lease_recorded_after_renumbering_is_reclaimed_after_next_remount(
    prepared, remount
):
    from blender_mcp_installer.model import TreeImage

    roots, state, doc, row, old = prepared
    image = TreeImage.from_dict(row["expected"])
    # Recorded with the live device of a boot in which its lease was never created.
    (state.path / "usage" / device_usage_name(image.dev, image.ino)).unlink()
    if remount:
        row["expected"] = _renumbered(image, image.dev + 7).to_dict()

    result = _finalize_row(state, roots, doc, row)

    if remount:
        assert result["status"] == "complete" and not old.exists()
        assert not list((state.path / "usage").iterdir())
    else:
        assert result["candidates"][0]["reason"] == "version lease is busy or missing"
        assert old.exists()


def _quiescent_runtime(tmp_path, marker, offset, *, receipt=True):
    from blender_mcp_installer.model import TreeImage

    home, codex = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    runtime = home / ".local/share/blender-lab-mcp/runtime"
    (runtime / "bin").mkdir(parents=True)
    (runtime / ".blender-mcp-usage-v1").write_bytes(marker)
    with SafeRoot.open(home, os.getuid(), home) as safe:
        image = capture_tree(safe, runtime.relative_to(home))
    assert isinstance(image, TreeImage)
    installed = _renumbered(image, image.dev + offset) if offset else image
    identifier = str(uuid4())
    with state_root(roots) as state:
        if receipt:
            (state.path / "receipts").mkdir(mode=0o700)
            for path, value in (
                (state.path / "active.json", {"install_id": identifier}),
                (
                    state.path / "receipts" / (identifier + ".json"),
                    {
                        "install_id": identifier,
                        "status": "installed",
                        "targets": [
                            {
                                "role": "runtime",
                                "path": str(runtime),
                                "install_post": installed.to_dict(),
                            }
                        ],
                    },
                ),
            ):
                path.write_text(json.dumps(value))
                path.chmod(0o600)
    return roots, runtime, image


def _quiesce(roots, runtime):
    from blender_mcp_installer.upgrade_handoff import runtime_quiescence

    with state_root(roots) as state:
        with runtime_quiescence(state, roots, runtime, Path("/unused/codex")) as handoff:
            return handoff


def test_v1_runtime_renumbered_since_install_can_be_quiesced(tmp_path):
    roots, runtime, image = _quiescent_runtime(tmp_path, b"inode-v1\n", 7)
    with state_root(roots) as state:
        # The installer created the lease under the device recorded at install time.
        ensure_usage_lock(state, device_usage_name(image.dev + 7, image.ino))

    handoff = _quiesce(roots, runtime)

    assert handoff["image"] == image.to_dict()
    assert sorted(path.name for path in (roots.state / "usage").iterdir()) == [
        device_usage_name(image.dev + 7, image.ino)
    ]


@pytest.mark.parametrize("held", ["recorded", "live"])
def test_v1_runtime_lease_held_in_either_device_blocks_quiescence(tmp_path, held):
    from blender_mcp_installer.upgrade_handoff import RuntimeInUse

    roots, runtime, image = _quiescent_runtime(tmp_path, b"inode-v1\n", 7)
    names = {
        "recorded": device_usage_name(image.dev + 7, image.ino),
        "live": device_usage_name(image.dev, image.ino),
    }
    with state_root(roots) as state:
        for name in names.values():
            ensure_usage_lock(state, name)
        with usage_lock(state, names[held], exclusive=False) as acquired:
            assert acquired
            with pytest.raises(RuntimeInUse):
                _quiesce(roots, runtime)
    assert _quiesce(roots, runtime)["image"] == image.to_dict()


@pytest.mark.parametrize("receipt", [True, False])
def test_v1_runtime_without_renumbering_proof_needs_its_lease(tmp_path, receipt):
    from blender_mcp_installer.upgrade_handoff import RuntimeInUse

    roots, runtime, image = _quiescent_runtime(
        tmp_path, b"inode-v1\n", 0 if receipt else 7, receipt=receipt
    )
    with state_root(roots) as state:
        ensure_usage_lock(state, device_usage_name(image.dev + 7, image.ino))
    with pytest.raises(RuntimeInUse):
        _quiesce(roots, runtime)


def test_v2_runtime_quiescence_needs_and_honours_its_inode_lease(tmp_path):
    from blender_mcp_installer.upgrade_handoff import RuntimeInUse

    roots, runtime, image = _quiescent_runtime(tmp_path, V2, 7)
    with state_root(roots) as state:
        for device in (image.dev, image.dev + 7):
            ensure_usage_lock(state, device_usage_name(device, image.ino))
    with pytest.raises(RuntimeInUse):
        _quiesce(roots, runtime)
    with state_root(roots) as state:
        ensure_usage_lock(state, usage_name(image.ino))
        with usage_lock(state, usage_name(image.ino), exclusive=False) as acquired:
            assert acquired
            with pytest.raises(RuntimeInUse):
                _quiesce(roots, runtime)
    assert _quiesce(roots, runtime)["image"] == image.to_dict()


def test_superseded_journal_is_retired_by_the_finalize_that_completes_cleanup(prepared):
    roots, state, doc, row, old = prepared
    absent = dict(copy.deepcopy(row), key="plugin_cache:0", version="0")
    superseded = _superseded(
        state, roots, doc, absent, commit="a" * 40, plugin_version="1",
        projection=str(roots.projections / ("a" * 40)),
    )

    result = _finalize_row(state, roots, doc, row)

    assert result["status"] == "complete" and not old.exists()
    retired = load_record(state, roots, superseded["id"])
    assert retired["status"] == "complete"
    assert retired["candidates"][0]["reason"] == "verified absent"


def test_oversized_cleanup_intent_fails_before_the_deletion_boundary(prepared, monkeypatch):
    import blender_mcp_installer.filesystem as filesystem

    roots, state, doc, row, old = prepared
    journal = state.path / "upgrades" / (doc["id"] + ".json")
    monkeypatch.setattr(filesystem, "STATE_JSON_LIMIT", journal.stat().st_size + 1)

    with pytest.raises(ValueError, match="state JSON is too large"):
        _finalize_row(state, roots, doc, row)

    monkeypatch.undo()
    assert load_record(state, roots, doc["id"]) == doc
    assert old.exists()
