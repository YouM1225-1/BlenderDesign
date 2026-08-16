from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest


ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "plugins/blender-mcp-installer/scripts"
sys.path.insert(0, str(SCRIPTS))

from blender_mcp_installer import cli  # noqa: E402
from blender_mcp_installer.blender_adapter import BlenderChange, BlenderState  # noqa: E402
from blender_mcp_installer.bundle import StagedBundle, parse_manifest  # noqa: E402
from blender_mcp_installer.filesystem import (  # noqa: E402
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    StagedFile,
    capture_file,
    capture_tree,
)
from blender_mcp_installer.model import (  # noqa: E402
    ActionKind,
    ActionState,
    BlenderPaths,
    FileImage,
    InstallRoots,
    PendingSelector,
    TreeImage,
)
from blender_mcp_installer.verification import HostCapabilities  # noqa: E402
from tests.distribution.fake_host import HostHarness  # noqa: E402
from tests.distribution.fault_driver import _PREIMAGES, _applicable_points  # noqa: E402


COMMIT = "a" * 40
ARTIFACTS = ROOT / "plugins/blender-mcp-installer/artifacts"


def _argv(host: HostHarness, command: str) -> list[str]:
    result = [
        command,
        "--bundle-root",
        str(ARTIFACTS),
        "--expected-distribution-commit",
        COMMIT,
        "--blender",
        str(host.blender),
        "--codex",
        str(host.codex),
        "--uv",
        str(host.uv),
    ]
    if command == "install":
        result += [
            "--allow-extension-install",
            "--allow-online-access",
            "--allow-localhost-bridge",
            "--approve-arbitrary-python",
        ]
    if command == "rollback":
        receipt = host.state_root / "receipts" / "12345678-1234-4234-9234-123456789abc.json"
        result += ["--receipt", str(receipt)]
    return result


@pytest.mark.parametrize("command", ["inspect", "install", "verify", "rollback"])
def test_real_subparser_forwards_exact_codex_path(
    host: HostHarness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    seen: list[Path] = []

    def handler(args: object) -> dict[str, object]:
        seen.append(args.codex)
        return {"command": command}

    monkeypatch.setattr(cli, command, handler)
    assert cli.run_cli(_argv(host, command), NoOpFaultInjector()) == 0
    assert seen == [host.codex]
    assert json.loads(capsys.readouterr().out) == {"command": command}


@pytest.mark.parametrize("bad", ["relative-codex", "/does/not/exist/codex"])
def test_bad_codex_fails_before_handler(
    host: HostHarness,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    bad: str,
) -> None:
    called = False

    def handler(_args: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(cli, "inspect", handler)
    argv = _argv(host, "inspect")
    argv[argv.index("--codex") + 1] = bad
    assert cli.run_cli(argv, NoOpFaultInjector()) == 2
    assert called is False
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"error": "invalid arguments"}
    assert captured.err == ""


def test_plugin_root_bundle_fails_before_handler(
    host: HostHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    def handler(_args: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(cli, "inspect", handler)
    argv = _argv(host, "inspect")
    argv[argv.index("--bundle-root") + 1] = str(ARTIFACTS.parent)
    assert cli.run_cli(argv, NoOpFaultInjector()) == 2
    assert called is False


@pytest.mark.parametrize(
    "flag",
    [
        "--allow-extension-install",
        "--allow-online-access",
        "--allow-localhost-bridge",
        "--approve-arbitrary-python",
    ],
)
def test_each_missing_consent_fails_without_installer_owned_write(
    host: HostHarness, monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    called = False

    def handler(_args: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(cli, "install", handler)
    argv = _argv(host, "install")
    argv.remove(flag)
    before = tuple(sorted(host.root.rglob("*")))
    assert cli.run_cli(argv, NoOpFaultInjector()) == 2
    assert called is False
    assert tuple(sorted(host.root.rglob("*"))) == before


def test_expected_and_unexpected_errors_are_json_and_redacted(
    host: HostHarness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "SECRET-SENTINEL"

    def expected(_args: object) -> dict[str, object]:
        raise InstallerError(secret)

    monkeypatch.setattr(cli, "inspect", expected)
    assert cli.run_cli(_argv(host, "inspect"), NoOpFaultInjector()) == 1
    output = capsys.readouterr().out
    assert json.loads(output) == {"error": "installer error"}
    assert secret not in output

    def unexpected(_args: object) -> dict[str, object]:
        raise RuntimeError(secret)

    monkeypatch.setattr(cli, "inspect", unexpected)
    assert cli.run_cli(_argv(host, "inspect"), NoOpFaultInjector()) == 1
    output = capsys.readouterr().out
    assert json.loads(output) == {"error": "internal installer error"}
    assert secret not in output


def test_install_entrypoint_contains_only_main_delegation() -> None:
    path = SCRIPTS / "install.py"
    tree = ast.parse(path.read_text())
    assert [
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    ] == []
    assert "blender_mcp_installer.cli import main" in path.read_text()


def test_first_install_orchestrates_journaled_adapters(
    host: HostHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = parse_manifest((ARTIFACTS / "manifest.json").read_bytes())
    paths = BlenderPaths(
        host.blender,
        "arm64",
        "5.2.0",
        host.resources,
        host.config,
        host.extensions,
    )
    roots = InstallRoots.discover(
        host.home,
        host.codex_home,
        paths,
        source_distribution_root=ROOT,
        distribution_root=ROOT,
    )
    blender = BlenderState(
        host.blender,
        ("arm64",),
        host.blender,
        "arm64",
        "5.2.0",
        host.home,
        host.resources,
        host.config,
        host.config / "userpref.blend",
        host.extensions,
        "user_default",
        host.extensions / "user_default/mcp",
        None,
        None,
        False,
        False,
        None,
        None,
        None,
        None,
    )
    env = {
        "HOME": str(host.home),
        "CODEX_HOME": str(host.codex_home),
        "BLENDER_USER_RESOURCES": str(host.resources),
        "BLENDER_USER_CONFIG": str(host.config),
        "BLENDER_USER_EXTENSIONS": str(host.extensions),
    }
    capabilities = HostCapabilities(
        "Darwin",
        "arm64",
        "0.148.0-alpha.9",
        "0.12.2",
        "5.2.0",
        "3.13.13",
        ("arm64",),
        True,
        True,
        True,
        host.blender,
        host.codex,
        host.uv,
        Path(sys.executable),
        env,
        lambda *_a, **_k: None,
    )

    class Verified:
        def __init__(self):
            self.manifest = manifest

        def materialize(self, path: Path) -> StagedBundle:
            path.mkdir()
            (path / "payload").write_bytes(b"bundle")
            return StagedBundle(ARTIFACTS, manifest)

    context = cli._Context(
        Verified(),
        StagedBundle(ARTIFACTS, manifest),
        "2b799aff562693ce0b79e9df4737158b4b785e5c854e39673a289192adaf4a60",
        capabilities,
        blender,
        roots,
    )
    monkeypatch.setattr(cli, "_inspection", lambda _context: SimpleNamespace(exact=False))
    monkeypatch.setattr(cli, "_lifecycle_closed", lambda _context: None)

    def fake_runtime(_bundle, _uv, _python, _profile, stage, _runner):
        (stage.path / "bin").mkdir()
        (stage.path / "bin/python").write_bytes(b"python")
        (stage.path / "bin/blender-mcp-managed").write_bytes(b"launcher")
        return capture_tree(stage.root, stage.relative)

    def fake_blender(_state, _zip, work: Path, _authorizations, _runner):
        extension = work / "resources/extensions/user_default/mcp"
        extension.mkdir(parents=True)
        (extension / "blender_manifest.toml").write_bytes(b"payload")
        userpref = work / "resources/config/userpref.blend"
        userpref.parent.mkdir(parents=True)
        userpref.write_bytes(b"preferences")
        (work / "mcp-1.0.0.zip").write_bytes(b"zip")
        with SafeRoot.open(work, os.getuid(), work) as root:
            extension_image = capture_tree(root, Path("resources/extensions/user_default/mcp"))
            userpref_image = capture_file(root, Path("resources/config/userpref.blend"))
        return BlenderChange(
            True,
            work,
            extension,
            userpref,
            extension_image,
            userpref_image,
            blender,
            (),
        )

    def fake_codex(_fd, _current, _desired, _runtime_python, stage: StagedFile):
        stage.path.write_bytes(b"[mcp_servers.blender]\n")
        refreshed = stage.refresh()
        return SimpleNamespace(post=refreshed.image, stage=refreshed)

    monkeypatch.setattr(cli, "stage_runtime", fake_runtime)
    monkeypatch.setattr(cli, "stage_blender_change", fake_blender)
    monkeypatch.setattr(cli, "stage_codex_config", fake_codex)
    monkeypatch.setattr(cli, "verify_runtime", lambda *_a, **_k: None)
    monkeypatch.setattr(cli, "inspect_blender", lambda *_a, **_k: blender)
    monkeypatch.setattr(cli, "verify_blender_files", lambda *_a, **_k: None)
    monkeypatch.setattr(cli, "load_extension_payload", lambda *_a, **_k: object())
    monkeypatch.setattr(cli, "verify_codex_toml", lambda *_a, **_k: None)
    monkeypatch.setattr(cli, "verify_codex_effective", lambda *_a, **_k: None)

    result = cli._changed_install(context, NoOpFaultInjector())

    assert result["changed"] is True and result["no_op"] is False
    receipt = Path(result["receipt"])
    value = json.loads(receipt.read_text())
    assert value["status"] == "installed"
    assert [action["kind"] for action in value["actions"]] == [
        "bundle_stage",
        "runtime_tree",
        "extension_tree",
        "userpref_file",
        "codex_file",
    ]
    assert value["actions"][0]["state"] == "cleaned"
    assert not roots.bundle_stage(value["install_id"]).exists()
    before = {
        path: path.read_bytes()
        for parent in (roots.data_root, roots.state_root, roots.codex_home)
        for path in parent.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(
        cli,
        "_inspection",
        lambda _context: SimpleNamespace(exact=True, receipt_path=receipt),
    )
    no_op = cli._changed_install(context, NoOpFaultInjector())
    after = {
        path: path.read_bytes()
        for parent in (roots.data_root, roots.state_root, roots.codex_home)
        for path in parent.rglob("*")
        if path.is_file()
    }
    assert no_op["no_op"] is True and no_op["receipt"] == str(receipt)
    assert after == before

    def native_codex(
        journal,
        action,
        target,
        stage,
        recovery,
        _rollback_stage,
        _desired,
        _runtime_python,
    ):
        return cli._restore_action(journal, action, target, stage, recovery)

    monkeypatch.setattr(cli, "_restore_codex", native_codex)
    installed = cli.load_receipt(receipt, roots)
    monkeypatch.setattr(cli, "_inspection", lambda _context: SimpleNamespace(exact=False))
    second_result = cli._changed_install(context, NoOpFaultInjector())
    second_receipt_path = Path(second_result["receipt"])
    second = cli.load_receipt(second_receipt_path, roots)
    assert second.parent_install_id == installed.install_id
    with pytest.raises(SystemExit) as swap_crash:
        cli._rollback_receipt(
            roots,
            context.source_bundle,
            blender,
            second,
            cli.ExitFaultInjector("after_active_restore_swap", 70),
            manifest_sha256=context.manifest_sha256,
        )
    assert swap_crash.value.code == 70
    assert cli.load_active(roots.active, roots).install_id == installed.install_id
    assert roots.previous_active(second.install_id).exists()
    assert cli.load_receipt(second_receipt_path, roots).status.value == "rollback_pending"
    second_recovery = cli.recover_active(
        roots,
        context.source_bundle,
        blender,
        NoOpFaultInjector(),
        manifest_sha256=context.manifest_sha256,
    )
    assert second_recovery == {"recovered": True, "status": "rolled_back"}
    assert cli.load_active(roots.active, roots).install_id == installed.install_id
    assert not roots.previous_active(second.install_id).exists()

    installed = cli.load_receipt(receipt, roots)
    roots.runtime_recovery(installed.install_id).mkdir()
    (roots.runtime_recovery(installed.install_id) / "foreign").write_bytes(b"foreign")
    before_conflict = {
        path: path.read_bytes()
        for parent in (
            roots.data_root,
            roots.state_root,
            roots.codex_home,
            roots.blender.user_resources,
        )
        for path in parent.rglob("*")
        if path.is_file()
    }
    with pytest.raises(InstallerError, match="rollback preflight conflict"):
        cli._rollback_receipt(
            roots,
            context.source_bundle,
            blender,
            installed,
            NoOpFaultInjector(),
            manifest_sha256=context.manifest_sha256,
        )
    after_conflict = {
        path: path.read_bytes()
        for parent in (
            roots.data_root,
            roots.state_root,
            roots.codex_home,
            roots.blender.user_resources,
        )
        for path in parent.rglob("*")
        if path.is_file()
    }
    assert after_conflict == before_conflict
    (roots.runtime_recovery(installed.install_id) / "foreign").unlink()
    roots.runtime_recovery(installed.install_id).rmdir()
    with pytest.raises(SystemExit) as atomic_crash:
        cli._rollback_receipt(
            roots,
            context.source_bundle,
            blender,
            installed,
            cli.ExitFaultInjector("after_json_parent_fsync", 70),
            manifest_sha256=context.manifest_sha256,
        )
    assert atomic_crash.value.code == 70
    receipt_temps = tuple(
        roots.receipts.glob(f".blender-mcp-installer.{installed.install_id}.*.tmp")
    )
    assert len(receipt_temps) == 1
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        cli._settle_known_receipt_atomic_json(
            roots, installed.install_id, state, NoOpFaultInjector()
        )
    assert not receipt_temps[0].exists()
    installed = cli.load_receipt(receipt, roots)
    assert installed.status.value == "rollback_pending"
    with pytest.raises(SystemExit) as crashed:
        cli._rollback_receipt(
            roots,
            context.source_bundle,
            blender,
            installed,
            cli.ExitFaultInjector("after_active_restore_move", 70),
            manifest_sha256=context.manifest_sha256,
        )
    assert crashed.value.code == 70
    assert not roots.active.exists()
    assert roots.previous_active(installed.install_id).exists()
    assert cli.load_receipt(receipt, roots).status.value == "rollback_pending"

    result = cli.recover_active(
        roots,
        context.source_bundle,
        blender,
        NoOpFaultInjector(),
        manifest_sha256=context.manifest_sha256,
    )
    rolled = cli.load_receipt(receipt, roots)
    assert result == {"recovered": True, "status": "rolled_back"}
    assert rolled.status.value == "rolled_back"
    assert not roots.active.exists()
    assert not roots.previous_active(installed.install_id).exists()
    assert not roots.runtime.exists()
    assert not roots.extension_target.exists()
    assert not roots.userpref_target.exists()
    assert not roots.codex_config.exists()


def test_staged_action_restores_with_intended_post(tmp_path: Path) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()
    with SafeRoot.open(root_path, os.getuid(), root_path) as root:
        target = cli.TargetRef(root, Path("target"))
        stage = cli.StagedFile(root, Path("stage"), FileImage.absent())
        stage.path.write_bytes(b"post")
        stage = stage.refresh()
        recovery = cli.TargetRef(root, Path("recovery"))
        action = cli._action(
            0,
            ActionKind.USERPREF_FILE,
            ActionState.STAGED,
            target.path,
            stage.path,
            recovery.path,
            FileImage.absent(),
            intended=stage.image,
        )
        journal = SimpleNamespace(fault=NoOpFaultInjector(), action=lambda value: None)

        restored = cli._restore_action(journal, action, target, stage, recovery)

        assert restored.state is ActionState.RESTORED
        assert capture_file(root, Path("target")) == FileImage.absent()
        assert capture_file(root, Path("stage")) == FileImage.absent()
        assert capture_file(root, Path("recovery")) == FileImage.absent()


def test_planned_action_rejects_partial_stage_without_adopting_it(tmp_path: Path) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()
    with SafeRoot.open(root_path, os.getuid(), root_path) as root:
        target = cli.TargetRef(root, Path("target"))
        stage = cli.StagedFile(root, Path("stage"), FileImage.absent())
        stage.path.write_bytes(b"partial")
        recovery = cli.TargetRef(root, Path("recovery"))
        action = cli._action(
            0,
            ActionKind.USERPREF_FILE,
            ActionState.PLANNED,
            target.path,
            stage.path,
            recovery.path,
            FileImage.absent(),
        )
        journal = SimpleNamespace(fault=NoOpFaultInjector(), action=lambda value: None)

        with pytest.raises(InstallerError, match="conflict"):
            cli._restore_action(journal, action, target, stage, recovery)

        assert stage.path.read_bytes() == b"partial"


def test_cleaned_bundle_action_requires_physically_absent_stage(tmp_path: Path) -> None:
    state_path = tmp_path / "state"
    bundle_path = state_path / "stages/12345678-1234-4234-9234-123456789abc/bundle"
    bundle_path.mkdir(parents=True)
    (bundle_path / "foreign").write_bytes(b"foreign")
    install_id = UUID("12345678-1234-4234-9234-123456789abc")
    with SafeRoot.open(state_path, os.getuid(), state_path) as state:
        image = capture_tree(state, Path("stages", str(install_id), "bundle"))
    action = cli._action(
        0,
        ActionKind.BUNDLE_STAGE,
        ActionState.CLEANED,
        bundle_path,
        bundle_path,
        None,
        TreeImage.absent(),
        intended=image,
    )
    journal = SimpleNamespace(
        receipt=SimpleNamespace(install_id=install_id, actions=(action,)),
        fault=NoOpFaultInjector(),
    )
    with SafeRoot.open(state_path, os.getuid(), state_path) as state:
        with pytest.raises(InstallerError, match="bundle stage recovery conflict"):
            cli._cleanup_bundle(journal, state)
    assert (bundle_path / "foreign").read_bytes() == b"foreign"


def _pending_fixture(host: HostHarness) -> tuple[InstallRoots, StagedBundle, PendingSelector]:
    manifest = parse_manifest((ARTIFACTS / "manifest.json").read_bytes())
    roots = InstallRoots.discover(
        host.home,
        host.codex_home,
        BlenderPaths(
            host.blender,
            "arm64",
            "5.2.0",
            host.resources,
            host.config,
            host.extensions,
        ),
        source_distribution_root=ROOT,
        distribution_root=ROOT,
    )
    roots.state_root.mkdir(parents=True, exist_ok=True)
    roots.receipts.mkdir(exist_ok=True)
    roots.backups(UUID("12345678-1234-4234-9234-123456789abc")).mkdir(parents=True)
    roots.data_root.mkdir(parents=True, exist_ok=True)
    (host.extensions / "user_default").mkdir(exist_ok=True)
    pending = PendingSelector(
        1,
        1,
        UUID("12345678-1234-4234-9234-123456789abc"),
        "12345678-1234-4234-9234-123456789abc.json",
        "2b799aff562693ce0b79e9df4737158b4b785e5c854e39673a289192adaf4a60",
        None,
    )
    roots.pending.write_text(json.dumps(pending.to_dict()))
    roots.pending.chmod(0o600)
    return roots, StagedBundle(ARTIFACTS, manifest), pending


def test_reconcile_malformed_present_receipt_conflicts_without_removing_pending(
    host: HostHarness,
) -> None:
    roots, bundle, pending = _pending_fixture(host)
    receipt = roots.receipt(pending.install_id)
    receipt.write_text("{malformed")
    receipt.chmod(0o600)
    before = roots.pending.read_bytes()

    with pytest.raises(InstallerError, match="selector reconciliation conflict"):
        cli.reconcile_selectors(
            roots,
            bundle,
            object(),
            NoOpFaultInjector(),
            manifest_sha256=pending.manifest_sha256,
        )

    assert roots.pending.read_bytes() == before
    assert receipt.read_text() == "{malformed"


def test_reconcile_no_receipt_rejects_partial_action_stage_without_adoption(
    host: HostHarness,
) -> None:
    roots, bundle, pending = _pending_fixture(host)
    roots.runtime_stage(pending.install_id).mkdir()
    (roots.runtime_stage(pending.install_id) / "partial").write_bytes(b"partial")
    before = roots.pending.read_bytes()

    with pytest.raises(InstallerError, match="selector reconciliation conflict"):
        cli.reconcile_selectors(
            roots,
            bundle,
            object(),
            NoOpFaultInjector(),
            manifest_sha256=pending.manifest_sha256,
        )

    assert roots.pending.read_bytes() == before
    assert (roots.runtime_stage(pending.install_id) / "partial").read_bytes() == b"partial"


def test_reconcile_no_receipt_does_not_publish_or_delete_active_temp(
    host: HostHarness,
) -> None:
    roots, bundle, pending = _pending_fixture(host)
    temp = roots.state_root / (f".blender-mcp-installer.{pending.install_id}.active.json.tmp")
    temp.write_text(
        json.dumps(cli._selector(None, pending.install_id, pending.generation).to_dict())
    )
    temp.chmod(0o600)
    pending_before = roots.pending.read_bytes()
    temp_before = temp.read_bytes()

    with pytest.raises(InstallerError, match="selector reconciliation conflict"):
        cli.reconcile_selectors(
            roots,
            bundle,
            object(),
            NoOpFaultInjector(),
            manifest_sha256=pending.manifest_sha256,
        )

    assert not roots.active.exists()
    assert roots.pending.read_bytes() == pending_before
    assert temp.read_bytes() == temp_before


_FAULT_CASES = tuple(
    (kind, preimage, point)
    for kind, preimages in _PREIMAGES.items()
    for preimage in preimages
    for point in _applicable_points(kind, preimage)
)


@pytest.mark.parametrize(("fixture_kind", "preimage", "point"), _FAULT_CASES)
def test_closed_fault_matrix_exits_70_then_fresh_process_recovers_exactly(
    tmp_path: Path, fixture_kind: str, preimage: str, point: str
) -> None:
    scenario = tmp_path / "scenario"
    driver = ROOT / "tests/distribution/fault_driver.py"
    host_root = scenario / "host"
    common = [
        "--bundle-root",
        str(ARTIFACTS),
        "--expected-distribution-commit",
        COMMIT,
        "--blender",
        str(host_root / "bin/blender"),
        "--codex",
        str(host_root / "bin/codex"),
        "--uv",
        str(host_root / "bin/uv"),
    ]

    def invoke(
        command: str,
        *,
        recover: bool,
        receipt: Path | None = None,
        selected_point: str = point,
    ):
        argv = [
            sys.executable,
            str(driver),
            "--point",
            selected_point,
            "--fixture-kind",
            fixture_kind,
            "--preimage",
            preimage,
            "--scenario-root",
            str(scenario),
        ]
        if recover:
            argv.append("--recover")
        argv += ["--", command, *common]
        if command == "install":
            argv += [
                "--allow-extension-install",
                "--allow-online-access",
                "--allow-localhost-bridge",
                "--approve-arbitrary-python",
            ]
        if receipt is not None:
            argv += ["--receipt", str(receipt)]
        return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)

    rollback_point = (
        "restore" in point
        or point.startswith("after_rollback")
        or point.startswith("after_codex_semantic")
        or point == "after_active_restore_cleanup"
    )
    command = "rollback" if rollback_point else "install"
    receipt: Path | None = None
    if command == "install" and fixture_kind == "active_selector" and preimage == "present":
        seeded = invoke("install", recover=True)
        assert seeded.returncode == 0, seeded.stderr + seeded.stdout
        (scenario / "force-change").write_text("1\n")
    if command == "rollback":
        staged_move = preimage == "present" and point.endswith("_restore_move")
        if staged_move:
            prepared = invoke(
                "install",
                recover=False,
                selected_point=point.replace("_restore_move", "_swap"),
            )
            assert prepared.returncode == 70, prepared.stderr + prepared.stdout
        else:
            seeded = invoke("install", recover=True)
            assert seeded.returncode == 0, seeded.stderr + seeded.stdout
            if fixture_kind == "active_selector" and preimage == "present":
                (scenario / "force-change").write_text("1\n")
                seeded = invoke("install", recover=True)
                assert seeded.returncode == 0, seeded.stderr + seeded.stdout
        active = json.loads(
            (host_root / "home/.local/state/blender-mcp-installer/active.json").read_text()
        )
        receipt = (
            host_root
            / "home/.local/state/blender-mcp-installer/receipts"
            / active["receipt_basename"]
        )

    crashed = invoke(command, recover=False, receipt=receipt)
    assert crashed.returncode == 70, crashed.stderr + crashed.stdout
    assert "SECRET-SENTINEL" not in crashed.stdout + crashed.stderr
    recovered = invoke(command, recover=True, receipt=receipt)
    assert recovered.returncode == 0, recovered.stderr + recovered.stdout
    assert "SECRET-SENTINEL" not in recovered.stdout + recovered.stderr

    state_root = host_root / "home/.local/state/blender-mcp-installer"
    assert not list(state_root.rglob(".blender-mcp-installer.*.tmp"))
    if command == "install":
        active = json.loads((state_root / "active.json").read_text())
        terminal = json.loads((state_root / "receipts" / active["receipt_basename"]).read_text())
        assert terminal["status"] == "installed"
        assert terminal["actions"][0]["state"] == "cleaned"
    else:
        assert receipt is not None
        terminal = json.loads(receipt.read_text())
        assert terminal["status"] == "rolled_back"
        assert all(action["state"] in {"cleaned", "restored"} for action in terminal["actions"])
        assert not (
            state_root / "backups" / terminal["install_id"] / "previous-active.json"
        ).exists()

    def image_at(path: Path, *, tree: bool):
        with SafeRoot.open(path.parent, os.getuid(), path.parent) as safe:
            return (
                capture_tree(safe, Path(path.name)) if tree else capture_file(safe, Path(path.name))
            )

    for action in terminal["actions"]:
        if action["kind"] == "bundle_stage":
            assert not Path(action["target_path"]).exists()
            continue
        tree = action["kind"] in {"runtime_tree", "extension_tree"}
        image_type = TreeImage if tree else FileImage
        target = Path(action["target_path"])
        stage = target.parent / action["stage_basename"]
        recovery_path = target.parent / action["recovery_basename"]
        assert image_at(stage, tree=tree).state.value == "absent"
        if command == "install":
            assert image_at(target, tree=tree) == image_type.from_dict(action["actual_post"])
            expected_recovery = (
                image_type.from_dict(action["pre"])
                if action["pre"]["state"] == "present"
                else image_type.absent()
            )
            assert image_at(recovery_path, tree=tree) == expected_recovery
        else:
            assert image_at(target, tree=tree) == image_type.from_dict(action["pre"])
            assert image_at(recovery_path, tree=tree).state.value == "absent"

    selector = next(target for target in terminal["targets"] if target["role"] == "active_selector")
    assert image_at(Path(selector["path"]), tree=False) == FileImage.from_dict(
        selector["install_post"] if command == "install" else selector["pre"]
    )
