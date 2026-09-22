from pathlib import Path
import json
import os
import sys
import tomllib
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))
import project_marketplace as marketplace
from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_locks import mutation_locks
from blender_mcp_installer.upgrade_state import UpgradeRoots
from tests.distribution.test_plugin_contract import _fake_marketplace_codex


@pytest.fixture
def registration(tmp_path):
    home = tmp_path / "home"
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True, mode=0o700)
    roots = UpgradeRoots(home, codex_home)
    projection = roots.projections / ("b" * 40)
    plugin = projection / "plugins/blender-mcp-installer"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / ".codex-plugin/plugin.json").write_text(json.dumps({
        "name": "blender-mcp-installer", "version": "2.0.0",
    }))
    (plugin / "payload.py").write_text("actual_new_payload = True\n")
    (projection / ".agents/plugins").mkdir(parents=True)
    (projection / ".agents/plugins/marketplace.json").write_text(json.dumps({
        "name": "official-blender-mcp", "plugins": [],
    }))
    marketplace._secure_tree(projection)
    old = roots.caches / "1.0.0"
    old.mkdir(parents=True)
    (old / "payload.py").write_text("actual_old_payload = True\n")
    config = codex_home / "config.toml"
    config.write_text('# preserve this comment\nmodel = "protected-model"\n'
                      '[plugins."blender-mcp-installer@official-blender-mcp"]\n'
                      'enabled = false\nprotected_option = "retained"\n'
                      '[mcp_servers.protected.env]\nLOCAL_TEST_VALUE = "retained"\n')
    config.chmod(0o600)
    backup = codex_home / "config.toml.backup"
    backup.write_bytes(config.read_bytes())
    codex = _fake_marketplace_codex(tmp_path)
    recovery_root = roots.state / "marketplace-recovery"
    recovery_root.mkdir(parents=True, mode=0o700)
    identity = str(uuid4())
    args = projection, recovery_root, codex, home, codex_home
    with mutation_locks(roots):
        yield args, identity, config, old, roots


def test_destructive_native_add_cannot_prune_old_live_cache(registration, monkeypatch):
    args, identity, config, old, roots = registration
    before, inode = config.read_bytes(), old.stat().st_ino
    seen = []
    original = marketplace._codex

    def record(codex, home, codex_home, *argv):
        seen.append((codex_home, argv))
        assert codex_home != roots.codex_home
        return original(codex, home, codex_home, *argv)

    monkeypatch.setattr(marketplace, "_codex", record)
    recovery = marketplace._register(*args, recovery_id=identity)
    assert old.stat().st_ino == inode
    assert (old / "payload.py").read_text() == "actual_old_payload = True\n"
    assert marketplace._unmanaged_config(before) == marketplace._unmanaged_config(config.read_bytes())
    assert (roots.codex_home / "config.toml.backup").read_bytes() == before
    assert tomllib.loads(config.read_text())["plugins"]["blender-mcp-installer@official-blender-mcp"]["enabled"]
    assert "# preserve this comment" in config.read_text()
    assert not list(recovery.glob("native-codex.*"))
    assert not list(roots.codex_home.glob("*.registration.pre"))
    assert any(argv[:2] == ("plugin", "add") for _, argv in seen)


@pytest.mark.parametrize("boundary", ["cache_published", "config_published", "after_evidence"])
def test_registration_publication_retries_without_replacing_old_cache(registration, monkeypatch, boundary):
    args, identity, config, old, roots = registration
    initial = config.read_bytes()
    old_inode = old.stat().st_ino
    cache_inode = None
    fired = False
    atomic_json, atomic_write = marketplace._atomic_json, marketplace._atomic_write

    def json_write(path, value):
        nonlocal fired
        atomic_json(path, value)
        if not fired and ((boundary == "config_published" and path.name == "publication.json" and value.get("complete"))
                          or (boundary == "after_evidence" and path.name == "after.json")):
            fired = True
            raise RuntimeError("injected exit after publication")

    def raw_write(path, value):
        nonlocal fired
        if not fired and boundary == "cache_published" and path.name.endswith(".registration.stage"):
            fired = True
            raise RuntimeError("injected exit after cache publication")
        return atomic_write(path, value)

    monkeypatch.setattr(marketplace, "_atomic_json", json_write)
    monkeypatch.setattr(marketplace, "_atomic_write", raw_write)
    with pytest.raises(RuntimeError, match="injected exit"):
        marketplace._register(*args, recovery_id=identity)
    assert fired and old.stat().st_ino == old_inode
    cache_inode = (roots.caches / "2.0.0").stat().st_ino
    if boundary == "cache_published":
        assert config.read_bytes() == initial
    marketplace._register(*args, recovery_id=identity)
    assert old.stat().st_ino == old_inode
    assert (roots.caches / "2.0.0").stat().st_ino == cache_inode
    assert marketplace._unmanaged_config(initial) == marketplace._unmanaged_config(config.read_bytes())


def test_external_config_edit_during_native_stage_is_not_overwritten(registration, monkeypatch):
    args, identity, config, old, roots = registration
    original = marketplace._codex
    changed = b""

    def race(*argv):
        nonlocal changed
        result = original(*argv)
        if argv[3:5] == ("plugin", "add"):
            changed = config.read_bytes().replace(b"protected-model", b"external-edit")
            config.write_bytes(changed)
        return result

    monkeypatch.setattr(marketplace, "_codex", race)
    with pytest.raises(InstallerError, match="changed during staging"):
        marketplace._register(*args, recovery_id=identity)
    assert config.read_bytes() == changed and old.exists()
    assert not (roots.caches / "2.0.0").exists()


def test_native_environment_omits_credentials(registration, monkeypatch):
    args, identity, *_ = registration
    original = marketplace.subprocess.run
    observed = []
    for key in tuple(os.environ):
        if key not in {"HOME", "PATH", "TMPDIR", "LANG", "LC_ALL"}:
            monkeypatch.delenv(key)
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-forward")
    monkeypatch.setenv("ARBITRARY_PASSWORD", "do-not-forward")

    def run(*a, **kw):
        __tracebackhide__ = True
        if a and a[0][0] == str(args[2]):
            observed.append(kw["env"])
            assert "OPENAI_API_KEY" not in kw["env"]
            assert "ARBITRARY_PASSWORD" not in kw["env"]
        return original(*a, **kw)

    monkeypatch.setattr(marketplace.subprocess, "run", run)
    # Registration inspection uses codex_json too; its environment must have the same boundary.
    marketplace._register(*args, recovery_id=identity)
    assert observed


def test_new_cache_drift_stops_config_publication(registration, monkeypatch):
    args, identity, config, old, roots = registration
    initial = config.read_bytes()
    original = marketplace._atomic_json

    def drift(path, value):
        original(path, value)
        if path.name == "publication.json" and not value["complete"]:
            (roots.caches / "2.0.0/payload.py").write_text("unexpected drift\n")

    monkeypatch.setattr(marketplace, "_atomic_json", drift)
    with pytest.raises(InstallerError, match="cache changed before"):
        marketplace._register(*args, recovery_id=identity)
    assert config.read_bytes() == initial and old.exists()


def test_foreign_old_cache_and_symlink_are_not_touched(registration):
    args, identity, _, old, roots = registration
    unknown = roots.caches / "foreign"
    unknown.mkdir()
    (unknown / "user-file").write_text("retain me")
    alias = roots.caches / "foreign-link"
    alias.symlink_to(unknown, target_is_directory=True)
    before = old.stat().st_ino, unknown.stat().st_ino, alias.lstat().st_ino
    marketplace._register(*args, recovery_id=identity)
    assert before == (old.stat().st_ino, unknown.stat().st_ino, alias.lstat().st_ino)
    assert (unknown / "user-file").read_text() == "retain me"


@pytest.mark.parametrize("boundary", ["publication_recorded", "native_cleanup", "native_cli"])
def test_retry_removes_all_recorded_native_config_snapshots(registration, monkeypatch, boundary):
    args, identity, config, old, _ = registration
    initial, old_inode = config.read_bytes(), old.stat().st_ino
    atomic_json, remove, codex = marketplace._atomic_json, marketplace.conditional_remove_tree, marketplace._codex
    fired = False

    def crash_json(path, value):
        nonlocal fired
        atomic_json(path, value)
        if not fired and boundary == "publication_recorded" and path.name == "publication.json":
            fired = True
            raise RuntimeError("injected native lifecycle exit")

    class CleanupExit:
        def hit(self, point):
            nonlocal fired
            if not fired and point == "after_cleanup_entry":
                fired = True
                raise RuntimeError("injected native lifecycle exit")

    def crash_cleanup(ref, expected, guards, fault):
        if boundary == "native_cleanup" and ref.relative.name.startswith("native-codex."):
            fault = CleanupExit()
        return remove(ref, expected, guards, fault)

    def crash_codex(*argv):
        nonlocal fired
        if not fired and boundary == "native_cli":
            assert (argv[2] / "config.toml").read_bytes() == initial
            fired = True
            raise RuntimeError("injected native lifecycle exit")
        return codex(*argv)

    monkeypatch.setattr(marketplace, "_atomic_json", crash_json)
    monkeypatch.setattr(marketplace, "conditional_remove_tree", crash_cleanup)
    monkeypatch.setattr(marketplace, "_codex", crash_codex)
    with pytest.raises(RuntimeError, match="injected native lifecycle exit"):
        marketplace._register(*args, recovery_id=identity)
    assert fired and config.read_bytes() == initial
    recovery = args[1] / ("registration." + identity)
    unknown = recovery / "native-codex.unrecorded"
    unknown.mkdir(mode=0o700)
    (unknown / "sentinel").write_text("unknown ownership evidence: preserve")
    marketplace._register(*args, recovery_id=identity)
    assert not list(recovery.glob("native-codex.*/config.toml"))
    assert list(recovery.glob("native-codex.*")) == [unknown]
    assert (unknown / "sentinel").read_text() == "unknown ownership evidence: preserve"
    assert old.stat().st_ino == old_inode
    assert marketplace._unmanaged_config(config.read_bytes()) == marketplace._unmanaged_config(initial)


@pytest.mark.parametrize("conflict", ["replaced_root", "changed_cleanup", "missing_record"])
def test_native_stage_recovery_conflicts_preserve_evidence(registration, monkeypatch, conflict):
    args, identity, config, old, _ = registration
    initial = config.read_bytes()
    atomic_json, remove = marketplace._atomic_json, marketplace.conditional_remove_tree
    fired = False

    def crash_json(path, value):
        nonlocal fired
        atomic_json(path, value)
        if not fired and conflict != "changed_cleanup" and path.name == "publication.json":
            fired = True
            raise RuntimeError("injected evidence boundary")

    def crash_cleanup(ref, expected, guards, fault):
        nonlocal fired
        if not fired and conflict == "changed_cleanup" and ref.relative.name.startswith("native-codex."):
            fired = True
            raise RuntimeError("injected evidence boundary")
        return remove(ref, expected, guards, fault)

    monkeypatch.setattr(marketplace, "_atomic_json", crash_json)
    monkeypatch.setattr(marketplace, "conditional_remove_tree", crash_cleanup)
    with pytest.raises(RuntimeError, match="injected evidence boundary"):
        marketplace._register(*args, recovery_id=identity)
    recovery = args[1] / ("registration." + identity)
    record = recovery / "native-stage.json"
    native = recovery / json.loads(record.read_text())["path"]
    if conflict == "replaced_root":
        native.rename(recovery / "preserved-original-stage")
        native.mkdir(mode=0o700)
        (native / "config.toml").write_text('foreign = true\n')
    elif conflict == "changed_cleanup":
        (native / "config.toml").write_text('changed = true\n')
    else:
        record.unlink()
    retained = (native / "config.toml").read_bytes()
    with pytest.raises(InstallerError, match="identity changed|state conflict|lacks native stage evidence"):
        marketplace._register(*args, recovery_id=identity)
    assert (native / "config.toml").read_bytes() == retained
    assert config.read_bytes() == initial and old.exists()
