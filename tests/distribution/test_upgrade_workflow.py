from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))
from blender_mcp_installer import cli
from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_handoff import RuntimeInUse
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root
import project_marketplace as marketplace


def test_runtime_busy_prevents_first_registration_mutation(tmp_path, monkeypatch):
    home, codex = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    projection = roots.projections / ("a" * 40)
    plugin = projection / "plugins/blender-mcp-installer"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / "artifacts").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "blender-mcp-installer", "version": "2"})
    )
    (plugin / "artifacts/manifest.json").write_text(json.dumps({"bundle_version": "1.0.0"}))
    calls = []
    monkeypatch.setattr(
        marketplace,
        "inspect_registration",
        lambda *_args: (_ for _ in ()).throw(InstallerError("old registration")),
    )
    monkeypatch.setattr(marketplace, "profile_from_context", lambda _context: None)
    monkeypatch.setattr(cli, "_inspection", lambda _context: SimpleNamespace(exact=False))
    monkeypatch.setattr(marketplace, "_register", lambda *_args, **_kw: calls.append("register"))

    def occupied(*_args, **_kwargs):
        raise RuntimeInUse("busy")

    monkeypatch.setattr(marketplace, "runtime_quiescence", occupied)
    args = SimpleNamespace(
        reviewed_commit="a" * 40, codex="/fake/codex", workflow_id=None, handoff_id=None
    )
    context = SimpleNamespace(
        roots=SimpleNamespace(runtime=home / ".local/share/blender-lab-mcp/runtime")
    )
    with state_root(roots) as state:
        with pytest.raises(RuntimeInUse):
            marketplace._run_workflow(args, state, roots, projection, context)
    assert calls == []


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    from dataclasses import dataclass
    from blender_mcp_installer.upgrade_locks import mutation_locks
    from blender_mcp_installer.filesystem import NoOpFaultInjector

    home, codex = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    projection = roots.projections / ("b" * 40)
    plugin = projection / "plugins/blender-mcp-installer"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / "artifacts").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(json.dumps({"version": "2"}))
    (plugin / "artifacts/manifest.json").write_text(json.dumps({"bundle_version": "1"}))
    runtime = home / ".local/share/blender-lab-mcp/runtime"
    runtime.mkdir(parents=True)
    profile = {
        "executable": str(home / "Blender"),
        "architecture": "arm64",
        "version": "5.2.0",
        "resources": str(home / "resources"),
        "config": str(home / "resources/config"),
        "extensions": str(home / "resources/extensions"),
    }

    @dataclass
    class Context:
        roots: object
        workflow_id: str | None = None
        source_bundle: object = None
        blender: object = None
        manifest_sha256: str = "c" * 64

    context = Context(SimpleNamespace(runtime=runtime, home=home, codex_home=codex))
    args = SimpleNamespace(
        reviewed_commit="b" * 40,
        codex="/fake/codex",
        workflow_id=None,
        handoff_id=None,
        _fault=NoOpFaultInjector(),
    )
    events = []

    def inspection(_context):
        events.append("inspect")
        return SimpleNamespace(exact=False)

    monkeypatch.setattr(cli, "_inspection", inspection)
    monkeypatch.setattr(marketplace, "profile_from_context", lambda _: profile)
    monkeypatch.setattr(
        marketplace,
        "inspect_registration",
        lambda *_: SimpleNamespace(cache=SimpleNamespace(entries=())),
    )
    monkeypatch.setattr(marketplace, "_register", lambda *_args, **_kw: events.append("register"))
    monkeypatch.setattr(cli, "_lifecycle_closed", lambda _: events.append("closed"))
    monkeypatch.setattr(
        cli, "recover_active", lambda *_a, **_kw: events.append("recover") or {"recovered": False}
    )
    monkeypatch.setattr(cli, "_changed_install", lambda *_: pytest.fail("nested public locks"))
    with mutation_locks(roots) as state:
        yield args, state, roots, projection, context, events


def test_recheck_releases_only_usage_and_reselects(workflow, monkeypatch):
    from contextlib import contextmanager
    from blender_mcp_installer.upgrade_state import update_record, load_record
    from blender_mcp_installer.upgrade_locks import mutation_locks

    args, state, roots, projection, context, events = workflow
    identifiers = []

    @contextmanager
    def barrier(*_args):
        # Both mutation locks remain unavailable on each acquisition.
        with pytest.raises(BlockingIOError):
            with mutation_locks(roots):
                pytest.fail("mutation locks released")
        events.append("enter")
        try:
            yield None
        finally:
            events.append("leave")

    monkeypatch.setattr(marketplace, "runtime_quiescence", barrier)

    def install(_context, _fault, state, identity, handoff):
        identifiers.append(identity)
        events.append("install")
        if len(identifiers) == 1:
            update_record(state, roots, load_record(state, roots, identity), status="cancelled")
            raise cli._RuntimeRecheck
        return {"changed": True}

    monkeypatch.setattr(cli, "_changed_install_locked", install)
    result = marketplace._run_workflow(args, state, roots, projection, context)
    assert result["changed"] and len(set(identifiers)) == 2
    assert events == [
        "inspect",
        "enter",
        "register",
        "install",
        "leave",
        "inspect",
        "enter",
        "register",
        "install",
        "leave",
    ]


@pytest.mark.parametrize(
    "error_type",
    [
        RuntimeInUse,
        __import__(
            "blender_mcp_installer.upgrade_handoff", fromlist=["LegacyHandoffRequired"]
        ).LegacyHandoffRequired,
    ],
)
def test_typed_install_refusal_never_recovers(workflow, monkeypatch, error_type):
    args, state, roots, projection, context, events = workflow
    monkeypatch.setattr(marketplace, "runtime_quiescence", lambda *_: nullcontext(None))

    def install(*_):
        raise error_type("refused")

    monkeypatch.setattr(cli, "_changed_install_locked", install)
    with pytest.raises(error_type):
        marketplace._run_workflow(args, state, roots, projection, context)
    assert "recover" not in events


def test_failed_install_recovery_requires_new_runtime_inode(workflow, monkeypatch):
    from contextlib import contextmanager
    from blender_mcp_installer.upgrade_locks import ensure_usage_lock, usage_lock

    args, state, roots, projection, context, events = workflow
    runtime = context.roots.runtime
    held = []

    @contextmanager
    def barrier(*_):
        info = runtime.stat()
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        with usage_lock(state, info.st_dev, info.st_ino, exclusive=True) as acquired:
            if not acquired:
                raise RuntimeInUse("new runtime busy")
            held.append(info.st_ino)
            yield None

    monkeypatch.setattr(marketplace, "runtime_quiescence", barrier)
    child = None

    def install(*_):
        nonlocal child
        runtime.rename(runtime.with_name("old"))
        runtime.mkdir()
        info = runtime.stat()
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        import subprocess
        from blender_mcp_installer.upgrade_locks import usage_name

        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import fcntl,sys,time; f=open(sys.argv[1],'r+'); fcntl.flock(f,fcntl.LOCK_SH); print('ready',flush=True); time.sleep(60)",
                str(state.path / "usage" / usage_name(info.st_dev, info.st_ino)),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert child.stdout.readline().strip() == "ready"
        raise InstallerError("verification failed")

    monkeypatch.setattr(cli, "_changed_install_locked", install)
    try:
        with pytest.raises(RuntimeInUse, match="new runtime busy"):
            marketplace._run_workflow(args, state, roots, projection, context)
        assert len(held) == 1 and "recover" not in events
    finally:
        if child:
            child.terminate()
            child.wait(timeout=5)
    monkeypatch.setattr(
        cli,
        "_changed_install_locked",
        lambda *_: (_ for _ in ()).throw(InstallerError("retry verification failed")),
    )
    with pytest.raises(InstallerError, match="retry verification failed"):
        marketplace._run_workflow(args, state, roots, projection, context)
    assert events[-1] == "recover" and len(held) == 3
    assert held[-1] == held[-2] and held[-1] != held[0]


def test_restore_rejects_foreign_profile_before_writes(workflow, monkeypatch):
    from blender_mcp_installer.upgrade_state import new_record, save_record, update_record

    args, state, roots, projection, context, _events = workflow
    desired = {
        "commit": "b" * 40,
        "manifest_sha256": "c" * 64,
        "bundle_version": "1",
        "plugin_version": "2",
        "projection": str(projection),
    }
    doc = save_record(state, roots, None, new_record(roots, "register", desired))
    update_record(state, roots, doc, registration={"id": doc["id"], "state": "registered"})
    recovery = roots.state / "marketplace-recovery" / ("registration." + doc["id"])
    recovery.parent.mkdir(mode=0o700, exist_ok=True)
    recovery.mkdir(mode=0o700)
    marketplace._atomic_json(recovery / "before.json", {"present": False})
    marketplace._atomic_write(
        recovery / "RESTORE.txt",
        f"HOME: {roots.home}\nCODEX_HOME: {roots.codex_home}\nCODEX_BIN: /fake/codex\n".encode(),
    )
    foreign = roots.home / "never-created-codex"
    restore = SimpleNamespace(
        home=str(roots.home), codex_home=str(foreign), codex="/fake/codex", recovery=str(recovery)
    )
    monkeypatch.setattr(marketplace, "_restore", lambda *_: pytest.fail("foreign restore mutation"))
    with pytest.raises(InstallerError, match="profile mismatch"):
        marketplace._restore_evidence(restore)
    assert not foreign.exists()


@pytest.mark.parametrize(
    "operation", ["PERSISTENT_MARKETPLACE", "INSTALL", "FINALIZE", "REGISTER_FINALIZE"]
)
@pytest.mark.parametrize("command_rc", [0, 3, 7, "invalid_pending"])
@pytest.mark.parametrize("with_recovery", [False, True])
def test_documented_bash_status_cleanup_and_persistent_verify(
    tmp_path, operation, command_rc, with_recovery
):
    import os
    import subprocess
    from uuid import uuid4
    from tests.distribution.test_plugin_contract import _shell_block, WORKFLOW

    home = tmp_path / "home"
    home.mkdir()
    trust = tmp_path / "trust"
    trust.mkdir()
    distribution = trust / "distribution"
    scripts = distribution / "plugins/blender-mcp-installer/scripts"
    scripts.mkdir(parents=True)
    projection = home / "projection"
    persistent = projection / "plugins/blender-mcp-installer/scripts"
    persistent.mkdir(parents=True)
    journal, recovery = home / "journal.json", home / "recovery"
    journal.write_text("retained journal")
    recovery.mkdir()
    (recovery / "before.json").write_text("retained recovery")
    checksums = trust / "checksums"
    checksums.touch()
    for name in ("private.git", "template", "git-home"):
        (trust / name).mkdir()
    log = tmp_path / "order.log"
    identity = str(uuid4())
    payload = {
        "workflow_id": identity,
        "projection": str(projection),
        "recovery": str(recovery),
        "status": "cleanup_pending" if command_rc == 3 else "complete",
    }
    if not with_recovery:
        payload.pop("recovery")
    program = """import json,os,sys
from pathlib import Path
with open(os.environ['ORDER_LOG'],'a') as out: out.write(sys.argv[1]+'\\n')
if sys.argv[1] == 'verify':
    assert not Path(os.environ['TRUST_PARENT']).exists()
    assert sys.argv[sys.argv.index('--home') + 1] == os.environ['HOME']
    assert sys.argv[sys.argv.index('--codex-home') + 1] == os.environ['CODEX_HOME']
    assert ('--recovery' in sys.argv) == (os.environ['WITH_RECOVERY'] == '1')
    print('{}')
else:
    print(os.environ['RESULT_JSON'])
    raise SystemExit(int(os.environ['COMMAND_RC']))
"""
    for path in (
        scripts / "project_marketplace.py",
        scripts / "install.py",
        persistent / "project_marketplace.py",
    ):
        path.write_text(program)
    uv = tmp_path / "uv"
    uv.write_text(
        '#!/bin/bash\nwhile test "$1" != python; do shift; done\nshift\nexec "$PYTHON_BIN" "$@"\n'
    )
    uv.chmod(0o700)
    git = tmp_path / "git"
    git.write_text('#!/bin/bash\necho cleanup >> "$ORDER_LOG"\nrm -R "$3"\n')
    git.chmod(0o700)
    runner = 'import runpy,sys; sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name="__main__")'
    env = dict(
        os.environ,
        HOME=str(home),
        CODEX_HOME=str(home / "recorded-codex-profile"),
        PYTHON_BIN=sys.executable,
        UV_BIN=str(uv),
        PLUGIN_ROOT=str(scripts.parent),
        ISOLATED_RUNNER=runner,
        PRIVATE_GIT_DIR=str(trust / "private.git"),
        GIT_SAFE_HOME=str(trust / "git-home"),
        EMPTY_TEMPLATE=str(trust / "template"),
        TRUST_PARENT=str(trust),
        TRUSTED_DISTRIBUTION_ROOT=str(distribution),
        TRUSTED_CHECKSUMS=str(checksums),
        EXPECTED_DISTRIBUTION_COMMIT="a" * 40,
        BUNDLE_ROOT=str(distribution / "artifacts"),
        BLENDER_BIN="/fake/blender",
        CODEX_BIN="/fake/codex",
        ORDER_LOG=str(log),
        RESULT_JSON=json.dumps(payload),
        COMMAND_RC="3" if command_rc == "invalid_pending" else str(command_rc),
        WITH_RECOVERY="1" if with_recovery else "0",
        WORKFLOW_ID=identity,
        WORKFLOW_RC="0",
        WORKFLOW_JSON=json.dumps(payload),
        PERSISTENT_MARKETPLACE_ROOT=str(projection),
        REGISTRATION_RECOVERY_DIR=str(recovery) if with_recovery else "",
        FAKE_GIT=str(git),
    )
    env.pop("NORMAL_CODEX_HOME", None)
    script = "\n".join(
        (
            "set -euo pipefail",
            "run_uv_bootstrap() { :; }",
            'GIT_PRIVATE=("$FAKE_GIT")',
            _shell_block(WORKFLOW.read_text(), operation),
            _shell_block(WORKFLOW.read_text(), "TRUST_CLEANUP"),
            _shell_block(WORKFLOW.read_text(), "PERSISTENT_MARKETPLACE_VERIFY"),
        )
    )
    result = subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, timeout=10
    )
    assert result.returncode == (1 if command_rc == "invalid_pending" else command_rc), (
        result.stderr
    )
    assert journal.read_text() == "retained journal"
    assert (recovery / "before.json").read_text() == "retained recovery"
    if command_rc in (0, 3):
        assert not trust.exists() and projection.exists()
        assert log.read_text().splitlines()[-2:] == ["cleanup", "verify"]
        assert json.loads(result.stdout.splitlines()[-1]) == payload
    else:
        assert trust.exists() and "verify" not in log.read_text()


def test_explicit_retired_workflow_cannot_rebind_after_recheck(workflow, monkeypatch):
    from blender_mcp_installer.upgrade_state import (
        new_record,
        save_record,
        update_record,
        load_record,
        record_ids,
    )
    import hashlib

    args, state, roots, projection, context, events = workflow
    raw = (projection / "plugins/blender-mcp-installer/artifacts/manifest.json").read_bytes()
    desired = {
        "commit": "b" * 40,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "bundle_version": "1",
        "plugin_version": "2",
        "projection": str(projection),
    }
    doc = new_record(roots, "install", desired)
    doc["profile"] = marketplace.profile_from_context(context)
    doc = save_record(state, roots, None, doc)
    args.workflow_id = doc["id"]
    monkeypatch.setattr(marketplace, "runtime_quiescence", lambda *_: nullcontext(None))

    def install(_context, _fault, state, identity, _handoff):
        update_record(state, roots, load_record(state, roots, identity), status="cancelled")
        raise cli._RuntimeRecheck

    monkeypatch.setattr(cli, "_changed_install_locked", install)
    with pytest.raises(InstallerError, match="workflow identity mismatch"):
        marketplace._run_workflow(args, state, roots, projection, context)
    assert record_ids(state) == (doc["id"],)
    assert "recover" not in events


def test_registration_retry_preserves_original_before_images(tmp_path, monkeypatch):
    from uuid import uuid4

    home, codex, recovery = tmp_path / "home", tmp_path / "codex", tmp_path / "recovery"
    for path in (home, codex, recovery):
        path.mkdir(mode=0o700)
    projection = home / "new"
    original = {"present": True, "source_type": "local", "source": str(home / "old")}
    current = dict(original)
    others = {"count": 0, "sha256": "a" * 64}
    monkeypatch.setattr(
        marketplace, "_marketplace_snapshot", lambda _: (dict(current), dict(others))
    )
    monkeypatch.setattr(marketplace, "_validate_plugin_cache", lambda *_: None)

    def publish(desired, _recovery, _codex, _home, _codex_home):
        current.update(present=True, source_type="local", source=str(desired))

    monkeypatch.setattr(marketplace, "_isolated_registration", publish)
    identifier = str(uuid4())
    folder = marketplace._register(
        projection, recovery, Path("/fake/codex"), home, codex, recovery_id=identifier
    )
    before = {
        name: ((folder / name).read_bytes(), (folder / name).stat().st_ino)
        for name in ("before.json", "non-target-before.json")
    }
    assert (
        marketplace._register(
            projection, recovery, Path("/fake/codex"), home, codex, recovery_id=identifier
        )
        == folder
    )
    assert before == {
        name: ((folder / name).read_bytes(), (folder / name).stat().st_ino) for name in before
    }
    assert json.loads((folder / "before.json").read_bytes()) == original
    others["count"] = 1
    with pytest.raises(InstallerError, match="non-target changes"):
        marketplace._register(
            projection, recovery, Path("/fake/codex"), home, codex, recovery_id=identifier
        )


def test_prepare_after_unfinished_authority_ends_creates_new_migration(tmp_path, monkeypatch):
    from tests.distribution.test_upgrade_core import _register_case, _registration_evidence
    from blender_mcp_installer.upgrade_state import (
        new_record,
        save_record,
        update_record,
        record_ids,
    )
    from blender_mcp_installer.upgrade_locks import ensure_usage_lock
    from blender_mcp_installer import upgrade_integration
    from uuid import uuid4

    roots, current = _register_case(tmp_path)
    projection = Path(current["desired"]["projection"])
    plugin = projection / "plugins/blender-mcp-installer"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / "artifacts").mkdir()
    (plugin / ".codex-plugin/plugin.json").write_text(
        json.dumps({"name": "blender-mcp-installer", "version": "2"})
    )
    (plugin / "artifacts/manifest.json").write_text(json.dumps({"bundle_version": "1.0.0"}))
    args = SimpleNamespace(reviewed_commit="b" * 40, codex="/fake/codex", workflow_id=None)
    monkeypatch.setattr(
        marketplace,
        "inspect_registration",
        lambda *_: SimpleNamespace(cache=SimpleNamespace(entries=())),
    )
    monkeypatch.setattr(upgrade_integration, "inspect_registration", lambda *_: None)
    monkeypatch.setattr(
        marketplace, "_register", lambda *_a, **_kw: pytest.fail("exact registration changed")
    )
    monkeypatch.setattr(
        marketplace,
        "_marketplace_snapshot",
        lambda *_: ({"present": True, "source_type": "local", "source": str(projection)}, {}),
    )
    with state_root(roots) as state:
        identity = str(uuid4())
        old_projection, _, old_cache = _registration_evidence(
            state,
            roots,
            registration_name=identity,
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
                "projection": str(old_projection),
            },
        )
        historical["registration"] = {"id": identity, "state": "registered"}
        historical = save_record(state, roots, None, historical)
        restore = roots.state / f"marketplace-recovery/registration.{identity}/RESTORE.txt"
        marketplace._atomic_write(restore, b"Journal provenance is authoritative.\n")
        first = marketplace._run_workflow(args, state, roots, projection)
        assert (
            first["no_op"] and not first["all_old_versions_removed"] and "workflow_id" not in first
        )
        assert len(record_ids(state)) == 1 and old_cache.exists()
        historical = update_record(
            state,
            roots,
            historical,
            status="cleanup_pending",
            verification={"registration": "passed", "live": "not_run"},
        )
        update_record(state, roots, historical, status="complete")
        info = old_cache.stat()
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        second = marketplace._run_workflow(args, state, roots, projection)
        assert second["status"] == "complete" and not old_cache.exists()
        assert second["workflow_id"] != historical["id"] and len(record_ids(state)) == 2


def test_public_profile_mismatch_precedes_handler(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    args = [
        "project_marketplace.py",
        "begin-handoff",
        "--home",
        str(tmp_path / "home"),
        "--codex-home",
        str(tmp_path / "foreign"),
        "--codex",
        "/fake/codex",
    ]
    monkeypatch.setattr(sys, "argv", args)
    called = []
    monkeypatch.setattr(marketplace, "_begin_handoff", lambda _: called.append("mutation"))
    with pytest.raises(InstallerError, match="environment"):
        marketplace.main()
    assert called == []


@pytest.mark.parametrize("explicit", [False, True])
def test_recheck_reselects_when_receipt_retired_but_journal_stays_pending(
    workflow, monkeypatch, explicit
):
    from blender_mcp_installer.upgrade_state import load_record, update_record
    from blender_mcp_installer import upgrade_integration
    from blender_mcp_installer.model import ReceiptStatus
    from uuid import uuid4

    args, state, roots, projection, context, events = workflow
    context.roots.receipt = lambda identity: roots.state / "receipts" / (str(identity) + ".json")
    monkeypatch.setattr(marketplace, "runtime_quiescence", lambda *_: nullcontext(None))
    monkeypatch.setattr(
        cli, "load_receipt", lambda *_: SimpleNamespace(status=ReceiptStatus.ROLLED_BACK)
    )
    monkeypatch.setattr(
        upgrade_integration,
        "load_receipt",
        lambda *_: SimpleNamespace(status=ReceiptStatus.ROLLED_BACK),
    )
    monkeypatch.setattr(
        upgrade_integration, "profile_from_context", marketplace.profile_from_context
    )
    calls = []

    def install(_context, _fault, state, identity, _handoff):
        calls.append(identity)
        if len(calls) == 1:
            update_record(
                state, roots, load_record(state, roots, identity), install_id=str(uuid4())
            )
            if explicit:
                args.workflow_id = identity
            raise cli._RuntimeRecheck
        assert len(calls) == 2
        return {"changed": True}

    monkeypatch.setattr(cli, "_changed_install_locked", install)
    if explicit:
        with pytest.raises(InstallerError, match="workflow"):
            marketplace._run_workflow(args, state, roots, projection, context)
        assert len(calls) == 1
    else:
        result = marketplace._run_workflow(args, state, roots, projection, context)
        assert result["changed"] and len(set(calls)) == 2
    assert "recover" not in events
    assert load_record(state, roots, calls[0])["status"] == "cancelled"


def test_restore_retired_authority_refuses_before_mutation(tmp_path, monkeypatch):
    from tests.distribution.test_upgrade_core import _register_case, _registration_evidence
    from blender_mcp_installer.upgrade_state import save_record, update_record
    from blender_mcp_installer.upgrade_cleanup import RollbackUnavailable

    roots, doc = _register_case(tmp_path)
    reference = "marketplace-recovery/registration.historical"
    with state_root(roots) as state:
        _registration_evidence(
            state,
            roots,
            after={
                "present": True,
                "source_type": "local",
                "source": str(roots.projections / ("a" * 40)),
            },
        )
        doc = save_record(state, roots, None, doc)
        update_record(
            state,
            roots,
            doc,
            status="cleanup_pending",
            verification={"registration": "passed", "live": "not_run"},
            retired_registrations=[reference],
        )
    args = SimpleNamespace(
        home=str(roots.home),
        codex_home=str(roots.codex_home),
        codex=str(roots.home / "bin/codex"),
        recovery=str(roots.state / reference),
    )
    before = marketplace._tree_manifest(roots.state)
    monkeypatch.setattr(marketplace, "_restore", lambda *_: pytest.fail("retired source restored"))
    with pytest.raises(RollbackUnavailable):
        marketplace._restore_evidence(args)
    assert marketplace._tree_manifest(roots.state) == before
    assert not (roots.codex_home / ".blender-mcp-marketplace.lock").exists()


@pytest.fixture
def exact_cache(tmp_path, monkeypatch):
    import hashlib
    import shutil
    from blender_mcp_installer import upgrade_registration

    roots = UpgradeRoots(tmp_path / "home", tmp_path / "codex")
    roots.home.mkdir(mode=0o700)
    roots.codex_home.mkdir(mode=0o700)
    projection = roots.projections / ("b" * 40)
    source = projection / "plugins/blender-mcp-installer"
    original = Path(marketplace.__file__).parents[1]
    shutil.copytree(
        original / "scripts", source / "scripts", ignore=shutil.ignore_patterns("__pycache__")
    )
    for name in (".codex-plugin/plugin.json", "artifacts/manifest.json", ".blender-mcp-usage-v1"):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / name, target)
    version = json.loads((source / ".codex-plugin/plugin.json").read_text())["version"]
    cache = roots.caches / version
    shutil.copytree(source, cache)
    (roots.codex_home / "config.toml").write_text(
        '[marketplaces.official-blender-mcp]\nsource_type = "local"\n'
        f"source = {json.dumps(str(projection))}\n"
    )
    desired = dict(
        commit="b" * 40,
        plugin_version=version,
        projection=str(projection),
        bundle_version=json.loads((source / "artifacts/manifest.json").read_text())[
            "bundle_version"
        ],
        manifest_sha256=hashlib.sha256(
            (source / "artifacts/manifest.json").read_bytes()
        ).hexdigest(),
    )
    item = dict(
        pluginId="blender-mcp-installer@official-blender-mcp",
        name="blender-mcp-installer",
        marketplaceName="official-blender-mcp",
        version=version,
        installed=True,
        enabled=True,
        source={"source": "local", "path": str(source)},
        marketplaceSource={"sourceType": "local", "source": str(projection)},
    )

    def codex_json(_codex, _roots, *arguments):
        if arguments[1] == "marketplace":
            return {"marketplaces": [{"name": "official-blender-mcp", "root": str(projection)}]}
        return {"installed": [item]}

    monkeypatch.setattr(upgrade_registration, "codex_json", codex_json)
    return roots, projection, cache, desired


def cached_entry(cache, roots, name):
    import os
    import subprocess

    return subprocess.run(
        [sys.executable, "-B", str(cache / "scripts" / name), "--help"],
        env=dict(
            os.environ,
            HOME=str(roots.home),
            CODEX_HOME=str(roots.codex_home),
            PYTHONDONTWRITEBYTECODE="1",
        ),
        capture_output=True,
        text=True,
        timeout=10,
    )


@pytest.mark.parametrize("pending", [False, True], ids=["cold_noop", "rematerialized_pending"])
def test_exact_current_cache_establishes_runnable_lease(exact_cache, pending):
    import shutil
    from blender_mcp_installer.upgrade_locks import mutation_locks, ensure_usage_lock, usage_name
    from blender_mcp_installer.upgrade_state import new_record, save_record, record_ids

    roots, projection, cache, desired = exact_cache
    args = SimpleNamespace(reviewed_commit="b" * 40, codex="/fake/codex", workflow_id=None)
    with mutation_locks(roots) as state:
        if pending:
            doc = new_record(roots, "register", desired)
            doc["registration"] = {"id": doc["id"], "state": "registered"}
            doc = save_record(state, roots, None, doc)
            old_info = cache.stat()
            ensure_usage_lock(state, old_info.st_dev, old_info.st_ino)
            previous = roots.home / "previous-cache"
            cache.rename(previous)
            shutil.copytree(previous, cache)
            assert cache.stat().st_ino != old_info.st_ino
        before_ids = record_ids(state)
        inspected = marketplace.inspect_registration(Path(args.codex), roots, desired)
        lease = state.path / "usage" / usage_name(inspected.cache.dev, inspected.cache.ino)
        assert not lease.exists()
        result = marketplace._run_workflow(args, state, roots, projection)
        assert record_ids(state) == before_ids  # A lease repair is not a new generation.
        assert (
            result["status"] == "complete" if pending else result["no_op"] and not result["changed"]
        )
        assert lease.is_file()
    for name in ("install.py", "project_marketplace.py"):
        entry = cached_entry(cache, roots, name)
        assert entry.returncode == 0, entry.stderr


def test_exact_cache_inspection_and_failed_entries_do_not_create_lease(exact_cache):
    roots, _projection, cache, desired = exact_cache
    assert not roots.state.exists()
    marketplace.inspect_registration(Path("/fake/codex"), roots, desired)
    for name in ("install.py", "project_marketplace.py"):
        assert cached_entry(cache, roots, name).returncode != 0
    assert not roots.state.exists()


@pytest.mark.parametrize("when", ["before", "during"])
def test_current_cache_identity_drift_cannot_succeed_or_lease_replacement(
    exact_cache, monkeypatch, when
):
    import shutil
    from blender_mcp_installer.upgrade_locks import mutation_locks, usage_name

    roots, projection, cache, desired = exact_cache
    inspect = marketplace.inspect_registration
    ensure = marketplace.ensure_usage_lock
    calls = 0

    def replace_cache():
        previous = roots.home / "previous-cache"
        cache.rename(previous)
        shutil.copytree(previous, cache)
        assert cache.stat().st_ino != previous.stat().st_ino

    def inspect_with_drift(*args):
        nonlocal calls
        snapshot = inspect(*args)
        calls += 1
        if calls == 1 and when == "before":
            replace_cache()
        return snapshot

    def ensure_with_drift(*args):
        ensure(*args)
        if when == "during":
            replace_cache()

    monkeypatch.setattr(marketplace, "inspect_registration", inspect_with_drift)
    monkeypatch.setattr(marketplace, "ensure_usage_lock", ensure_with_drift)
    args = SimpleNamespace(reviewed_commit="b" * 40, codex="/fake/codex", workflow_id=None)
    with mutation_locks(roots) as state:
        with pytest.raises(InstallerError, match="registration changed .* current cache lease"):
            marketplace._run_workflow(args, state, roots, projection)
        info = cache.stat()
        assert not (state.path / "usage" / usage_name(info.st_dev, info.st_ino)).exists()
        assert not list(state.path.glob("upgrades/*.json"))


def test_current_lease_repair_retains_unknown_lease_less_history(exact_cache):
    from blender_mcp_installer.upgrade_locks import mutation_locks, usage_name

    roots, projection, cache, _desired = exact_cache
    old = roots.caches / "unknown-old"
    old.mkdir()
    (old / "payload").write_bytes(b"retained unknown history")
    info = old.stat()
    args = SimpleNamespace(reviewed_commit="b" * 40, codex="/fake/codex", workflow_id=None)
    with mutation_locks(roots) as state:
        result = marketplace._run_workflow(args, state, roots, projection)
        assert result["no_op"] and result["unverified"] and not result["all_old_versions_removed"]
        assert not (state.path / "usage" / usage_name(info.st_dev, info.st_ino)).exists()
    assert (old / "payload").read_bytes() == b"retained unknown history"
    assert cached_entry(cache, roots, "project_marketplace.py").returncode == 0
