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
    atomic_json = marketplace._atomic_json

    def json_write(path, value):
        nonlocal fired
        if not fired and boundary == "cache_published" and path.name == "config-stage.json":
            fired = True
            raise RuntimeError("injected exit after cache publication")
        atomic_json(path, value)
        if not fired and ((boundary == "config_published" and path.name == "publication.json" and value.get("complete"))
                          or (boundary == "after_evidence" and path.name == "after.json")):
            fired = True
            raise RuntimeError("injected exit after publication")

    monkeypatch.setattr(marketplace, "_atomic_json", json_write)
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
    sensitive = native / "config.toml"
    if not sensitive.exists():
        sensitive = config.parent / f".blender-mcp-installer.{identity}.registration.stage"
    retained = sensitive.read_bytes()
    with pytest.raises(InstallerError, match="identity changed|state conflict|lacks native stage evidence"):
        marketplace._register(*args, recovery_id=identity)
    assert sensitive.read_bytes() == retained
    assert config.read_bytes() == initial and old.exists()


@pytest.mark.parametrize("conflict", [None, "stage_bytes", "stage_inode", "external_config", "cache"])
def test_durable_config_stage_retry_uses_original_native_metadata(registration, monkeypatch, conflict):
    args, identity, config, old, roots = registration
    initial, inode = config.read_bytes(), old.stat().st_ino
    original_codex, original_capture = marketplace._codex, marketplace.capture_file
    native_calls = 0
    fired = False
    recovery = args[1] / ("registration." + identity)

    def varying(codex, home, codex_home, *argv):
        nonlocal native_calls
        result = original_codex(codex, home, codex_home, *argv)
        if argv[:3] == ("plugin", "marketplace", "add"):
            import tomlkit
            native_calls += 1
            path = codex_home / "config.toml"
            data = tomlkit.parse(path.read_text())
            data["marketplaces"][marketplace.MARKETPLACE_NAME]["last_updated"] = str(native_calls)
            path.write_text(tomlkit.dumps(data))
        return result

    def capture(root, relative):
        nonlocal fired
        image = original_capture(root, relative)
        if (not fired and relative.name.endswith(".registration.stage")
                and image.state is marketplace.ImageState.PRESENT):
            fired = True
            assert not (recovery / "publication.json").exists()
            raise RuntimeError("injected durable stage exit")
        return image

    monkeypatch.setattr(marketplace, "_codex", varying)
    monkeypatch.setattr(marketplace, "capture_file", capture)
    with pytest.raises(RuntimeError, match="injected durable stage"):
        marketplace._register(*args, recovery_id=identity)
    assert config.read_bytes() == initial and old.stat().st_ino == inode
    stage = roots.codex_home / f".blender-mcp-installer.{identity}.registration.stage"
    stage_before = stage.read_bytes()
    unknown = recovery / "native-codex.unknown"
    unknown.mkdir(mode=0o700)
    (unknown / "sentinel").write_text("keep")
    if conflict == "stage_bytes":
        stage.write_bytes(stage_before + b"# drift\n")
    elif conflict == "stage_inode":
        stage.rename(stage.with_suffix(".preserved"))
        stage.write_bytes(stage_before)
        stage.chmod(0o600)
    elif conflict == "external_config":
        config.write_bytes(initial + b"# external edit\n")
    elif conflict == "cache":
        (roots.caches / "2.0.0/payload.py").write_text("drift\n")
    config_before, retained = config.read_bytes(), stage.read_bytes()
    if conflict:
        with pytest.raises(InstallerError):
            marketplace._register(*args, recovery_id=identity)
        assert stage.read_bytes() == retained and config.read_bytes() == config_before
    else:
        marketplace._register(*args, recovery_id=identity)
        assert config.read_bytes() == stage_before
        assert not stage.exists()
        assert not list(recovery.glob("native-codex.*/config.toml"))
    assert native_calls == 1
    assert old.stat().st_ino == inode and (unknown / "sentinel").read_text() == "keep"


@pytest.mark.parametrize("boundary", ["before_intent", "after_intent", "before_move", "after_move", "before_publication", "after_publication"])
def test_config_stage_intent_retries_at_every_durable_boundary(registration, monkeypatch, boundary):
    args, identity, config, old, _ = registration
    initial, old_inode = config.read_bytes(), old.stat().st_ino
    original_json, original_forward, original_codex = marketplace._atomic_json, marketplace.forward_file, marketplace._codex
    fired = False
    calls = 0

    def crash():
        nonlocal fired
        fired = True
        raise RuntimeError("intent boundary exit")

    def json_write(path, value):
        if not fired and ((boundary == "before_intent" and path.name == "config-stage.json") or
                          (boundary == "before_publication" and path.name == "publication.json")):
            crash()
        original_json(path, value)
        if not fired and ((boundary == "after_intent" and path.name == "config-stage.json") or
                          (boundary == "after_publication" and path.name == "publication.json")):
            crash()

    def forward(target, *argv):
        moving = target.relative.name.endswith(".registration.stage")
        if not fired and moving and boundary == "before_move":
            crash()
        result = original_forward(target, *argv)
        if not fired and moving and boundary == "after_move":
            crash()
        return result

    def codex(*argv):
        nonlocal calls
        calls += 1
        return original_codex(*argv)

    monkeypatch.setattr(marketplace, "_atomic_json", json_write)
    monkeypatch.setattr(marketplace, "forward_file", forward)
    monkeypatch.setattr(marketplace, "_codex", codex)
    with pytest.raises(RuntimeError, match="intent boundary exit"):
        marketplace._register(*args, recovery_id=identity)
    assert config.read_bytes() == initial and old.stat().st_ino == old_inode
    before_calls = calls
    recovery = marketplace._register(*args, recovery_id=identity)
    assert calls == before_calls if boundary != "before_intent" else calls > before_calls
    assert not list(recovery.glob("native-codex.*"))
    assert not list(config.parent.glob("*.registration.stage"))
    assert old.stat().st_ino == old_inode


def test_unknown_config_stage_is_preserved_without_durable_intent(registration):
    args, identity, config, old, roots = registration
    stage = roots.codex_home / f".blender-mcp-installer.{identity}.registration.stage"
    stage.write_bytes(b"unknown ownership")
    stage.chmod(0o600)
    before = config.read_bytes()
    with pytest.raises(InstallerError, match="lacks durable intent"):
        marketplace._register(*args, recovery_id=identity)
    assert stage.read_bytes() == b"unknown ownership"
    assert config.read_bytes() == before and old.exists()


@pytest.fixture
def separate_codex_volume(registration, monkeypatch):
    """Model CODEX_HOME on another volume: the real renameatx_np refuses to cross it."""
    import errno
    import fcntl
    from blender_mcp_installer import filesystem

    codex_home = os.path.realpath(registration[4].codex_home)
    rename = filesystem._rename_atomic
    crossings = []

    def volume(fd):
        path = fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024)).rstrip(b"\0").decode()
        return path == codex_home or path.startswith(codex_home + os.sep)

    def guarded(source_fd, source, target_fd, target, *, swap):
        if volume(source_fd) != volume(target_fd):
            crossings.append((source, target))
            raise OSError(errno.EXDEV, os.strerror(errno.EXDEV), target)
        return rename(source_fd, source, target_fd, target, swap=swap)

    monkeypatch.setattr(filesystem, "_rename_atomic", guarded)
    return crossings


def _cross_volume_leftovers(recovery, codex_home):
    return (list(recovery.glob("native-codex.*/config.toml"))
            + list(codex_home.glob(".blender-mcp-installer.*.registration.*")))


def test_cross_volume_codex_home_registers_after_refused_rename(registration, separate_codex_volume):
    args, identity, config, old, roots = registration
    initial, old_inode = config.read_bytes(), old.stat().st_ino
    recovery = marketplace._register(*args, recovery_id=identity)
    assert [target for _, target in separate_codex_volume] == [f".blender-mcp-installer.{identity}.registration.stage"]
    assert tomllib.loads(config.read_text())["plugins"]["blender-mcp-installer@official-blender-mcp"]["enabled"]
    assert marketplace._unmanaged_config(initial) == marketplace._unmanaged_config(config.read_bytes())
    assert config.stat().st_mode & 0o777 == 0o600
    assert _cross_volume_leftovers(recovery, roots.codex_home) == []
    assert old.stat().st_ino == old_inode


@pytest.mark.parametrize("boundary", ["after_intent", "transfer_written", "transfer_bound", "after_move", "after_publication"])
def test_cross_volume_transfer_retries_at_every_durable_boundary(registration, separate_codex_volume, monkeypatch, boundary):
    args, identity, config, old, roots = registration
    initial, old_inode = config.read_bytes(), old.stat().st_ino
    original_json, original_forward, original_codex = marketplace._atomic_json, marketplace.forward_file, marketplace._codex
    fired, calls = False, 0

    def crash():
        nonlocal fired
        fired = True
        raise RuntimeError("transfer boundary exit")

    def json_write(path, value):
        binding = path.name == "config-stage.json" and value.get("transfer") is not None
        if not fired and boundary == "transfer_written" and binding:
            crash()
        original_json(path, value)
        if not fired and ((boundary == "after_intent" and path.name == "config-stage.json")
                          or (boundary == "transfer_bound" and binding)
                          or (boundary == "after_publication" and path.name == "publication.json")):
            crash()

    def forward(target, *argv):
        result = original_forward(target, *argv)
        if not fired and boundary == "after_move" and target.relative.name.endswith(".registration.stage"):
            crash()
        return result

    def codex(*argv):
        nonlocal calls
        calls += 1
        return original_codex(*argv)

    monkeypatch.setattr(marketplace, "_atomic_json", json_write)
    monkeypatch.setattr(marketplace, "forward_file", forward)
    monkeypatch.setattr(marketplace, "_codex", codex)
    with pytest.raises(RuntimeError, match="transfer boundary exit"):
        marketplace._register(*args, recovery_id=identity)
    assert config.read_bytes() == initial and old.stat().st_ino == old_inode
    before_calls = calls
    recovery = marketplace._register(*args, recovery_id=identity)
    assert calls == before_calls and separate_codex_volume
    assert tomllib.loads(config.read_text())["plugins"]["blender-mcp-installer@official-blender-mcp"]["enabled"]
    assert _cross_volume_leftovers(recovery, roots.codex_home) == []
    assert old.stat().st_ino == old_inode


@pytest.mark.parametrize("drift", ["unbound_bytes", "bound_bytes", "bound_inode"])
def test_cross_volume_transfer_drift_fails_closed(registration, separate_codex_volume, monkeypatch, drift):
    args, identity, config, old, roots = registration
    initial = config.read_bytes()
    original_json = marketplace._atomic_json
    fired = False

    def json_write(path, value):
        nonlocal fired
        binding = path.name == "config-stage.json" and value.get("transfer") is not None
        if not fired and binding and drift == "unbound_bytes":
            fired = True
            raise RuntimeError("transfer drift exit")
        original_json(path, value)
        if not fired and binding:
            fired = True
            raise RuntimeError("transfer drift exit")

    monkeypatch.setattr(marketplace, "_atomic_json", json_write)
    with pytest.raises(RuntimeError, match="transfer drift exit"):
        marketplace._register(*args, recovery_id=identity)
    transfer = roots.codex_home / f".blender-mcp-installer.{identity}.registration.transfer"
    content = transfer.read_bytes()
    if drift == "bound_inode":
        transfer.rename(transfer.with_suffix(".preserved"))
        transfer.write_bytes(content)
        transfer.chmod(0o600)
    else:
        transfer.write_bytes(content + b"# drift\n")
    retained = transfer.read_bytes()
    with pytest.raises(InstallerError, match="requires recovery|state conflict"):
        marketplace._register(*args, recovery_id=identity)
    assert transfer.read_bytes() == retained
    assert not (roots.codex_home / f".blender-mcp-installer.{identity}.registration.stage").exists()
    assert config.read_bytes() == initial and old.exists()


def test_unknown_config_transfer_is_preserved_without_durable_intent(registration):
    args, identity, config, old, roots = registration
    transfer = roots.codex_home / f".blender-mcp-installer.{identity}.registration.transfer"
    transfer.write_bytes(b"unknown ownership")
    transfer.chmod(0o600)
    before = config.read_bytes()
    with pytest.raises(InstallerError, match="lacks durable intent"):
        marketplace._register(*args, recovery_id=identity)
    assert transfer.read_bytes() == b"unknown ownership"
    assert config.read_bytes() == before and old.exists()
