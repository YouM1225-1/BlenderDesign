from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import zipfile
from contextlib import nullcontext
from dataclasses import replace
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
    ActiveSelector,
    BlenderPaths,
    BoundaryRole,
    FileImage,
    InstallRoots,
    PendingSelector,
    Receipt,
    ReceiptAction,
    ReceiptStatus,
    TargetRole,
    TreeImage,
)
from blender_mcp_installer.verification import HostCapabilities  # noqa: E402
from tests.distribution.fake_host import HostHarness  # noqa: E402
from tests.distribution.test_bundle import _checkout  # noqa: E402
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


def test_empty_home_outer_python_inspect_does_not_rediscover_python(
    tmp_path: Path, host: HostHarness
) -> None:
    real_uv_raw = os.environ.get("UV") or shutil.which("uv")
    assert real_uv_raw is not None
    real_uv = Path(real_uv_raw).resolve()
    found = subprocess.run(
        [
            real_uv,
            "python",
            "find",
            "3.13",
            "--no-project",
            "--no-python-downloads",
            "--no-config",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    python = Path(found.stdout.strip())
    assert python.is_absolute() and python.is_symlink()
    bundle, commit = _checkout(tmp_path / "distribution")
    profile = tmp_path / "empty-home"
    codex_home = profile / ".codex"
    resources = profile / "blender-resources"
    config = resources / "config"
    extensions = resources / "extensions"
    for path in (profile, codex_home, resources, config, extensions):
        path.mkdir(exist_ok=True, parents=True, mode=0o700)
        path.chmod(0o700)
    state = json.loads(host.state_file.read_text())
    state.update(
        {
            "resources": str(resources),
            "config": str(config),
            "extensions": str(extensions),
        }
    )
    host.state_file.write_text(json.dumps(state, sort_keys=True) + "\n")
    host.blender.write_text(
        f"#!{sys.executable}\n"
        "import json,sys\n"
        f"state=json.load(open({str(host.state_file)!r}))\n"
        "if sys.argv[1:]==['--version']:\n print('Blender '+state['version'])\n"
        "elif '--background' in sys.argv and '--python-expr' in sys.argv:\n"
        " value={'binary_path':sys.argv[0],'version':[5,2,0],"
        "'architecture':state['architecture'],'user_resources':state['resources'],"
        "'config_root':state['config'],'extensions_root':state['extensions'],"
        "'repository':state['repository'],'enabled':False,'online_access':False,"
        "'host':None,'port':None,'autostart':None}\n"
        " print('__BLENDER_MCP_INSTALLER__'+json.dumps(value,sort_keys=True))\n"
        "else:\n raise SystemExit(2)\n"
    )
    host.blender.chmod(0o700)
    runner = (
        "import runpy,subprocess,sys; from types import SimpleNamespace; "
        "root=sys.argv[1]; script=sys.argv[2]; "
        "sys.argv=sys.argv[2:]; sys.path.insert(0,root); "
        "from blender_mcp_installer import cli,verification; probe=cli.probe_host; "
        "host_run=lambda argv,**kw: subprocess.CompletedProcess(argv,0,b'arm64\\n',b'') "
        "if argv[0]=='/usr/bin/lipo' else verification._default_runner(argv,**kw); "
        "cli.probe_host=lambda *args: probe(*args,runner=host_run); "
        "cli._inspection=lambda _context: SimpleNamespace("
        "exact=False,managed_targets=(),active_install_id=None); "
        'runpy.run_path(script,run_name="__main__")'
    )
    command = [
        str(real_uv),
        "run",
        "--quiet",
        "--no-project",
        "--python",
        str(python),
        "--no-python-downloads",
        "--no-sync",
        "python",
        "-I",
        "-B",
        "-c",
        runner,
        str(SCRIPTS),
        str(SCRIPTS / "install.py"),
        "inspect",
        "--bundle-root",
        str(bundle),
        "--expected-distribution-commit",
        commit,
        "--blender",
        str(host.blender),
        "--codex",
        str(host.codex),
        "--uv",
        str(host.uv),
    ]
    env = {
        "HOME": str(profile),
        "CODEX_HOME": str(codex_home),
        "BLENDER_USER_RESOURCES": str(resources),
        "BLENDER_USER_CONFIG": str(config),
        "BLENDER_USER_EXTENSIONS": str(extensions),
        "PATH": f"{real_uv.parent}:/usr/bin:/bin:/usr/sbin:/sbin",
    }

    completed = subprocess.run(
        command, cwd=bundle.parents[2], env=env, capture_output=True, text=True, check=False
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["command"] == "inspect"
    assert not (profile / ".local/state/blender-mcp-installer").exists()
    assert not (profile / ".local/share/blender-lab-mcp").exists()
    assert not (codex_home / "config.toml").exists()
    assert not (config / "userpref.blend").exists()
    calls = [json.loads(line) for line in host.commands.read_text().splitlines()]
    assert [call["argv"] for call in calls if call["tool"] == "uv"] == [["--version"]]
    assert all(call["argv"][:2] != ["python", "find"] for call in calls)
    assert command[1] == "run" and command[1:3] != ["python", "find"]


@pytest.mark.parametrize("value", [None, "", "relative-python", "non-executable", "broken-symlink"])
def test_current_python_must_be_an_absolute_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value == "non-executable":
        path = tmp_path / value
        path.write_bytes(b"python")
        value = str(path)
    elif value == "broken-symlink":
        path = tmp_path / value
        path.symlink_to(tmp_path / "missing-python")
        value = str(path)
    monkeypatch.setattr(sys, "executable", value)

    with pytest.raises(InstallerError, match="local Python 3.13 probe failed"):
        cli._resolve_python()


def test_current_python_resolves_a_valid_symlink_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "python3.13"
    target.write_bytes(b"python")
    target.chmod(0o700)
    middle = tmp_path / "python"
    middle.symlink_to(target.name)
    entry = tmp_path / "python3"
    entry.symlink_to(middle.name)
    monkeypatch.setattr(sys, "executable", str(entry))

    assert cli._resolve_python() == target


def test_current_python_revalidates_the_resolved_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "python3.13"
    target.write_bytes(b"python")
    target.chmod(0o700)
    entry = tmp_path / "python3"
    entry.symlink_to(target.name)
    monkeypatch.setattr(sys, "executable", str(entry))
    original_resolve = Path.resolve

    def swap_after_resolve(path: Path, *, strict: bool = False) -> Path:
        resolved = original_resolve(path, strict=strict)
        if path == entry:
            target.unlink()
            target.symlink_to(tmp_path / "replacement")
        return resolved

    monkeypatch.setattr(Path, "resolve", swap_after_resolve)

    with pytest.raises(InstallerError, match="local Python 3.13 probe failed"):
        cli._resolve_python()


def test_current_python_must_be_owned_by_current_user(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = tmp_path / "python"
    python.write_bytes(b"python")
    python.chmod(0o700)
    monkeypatch.setattr(sys, "executable", str(python))
    original_lstat = Path.lstat

    def foreign_lstat(path: Path) -> os.stat_result:
        info = original_lstat(path)
        if path != python:
            return info
        values = list(info)
        values[4] = os.getuid() + 1
        return os.stat_result(values)

    monkeypatch.setattr(Path, "lstat", foreign_lstat)

    with pytest.raises(InstallerError, match="local Python 3.13 probe failed"):
        cli._resolve_python()


def test_current_python_wrong_version_remains_bound_to_host_probe(
    tmp_path: Path, host: HostHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = tmp_path / "python-3.12"
    python.write_text("#!/bin/sh\necho 'Python 3.12.0'\n")
    python.chmod(0o700)
    monkeypatch.setattr(sys, "executable", str(python))
    monkeypatch.setattr(cli, "verify_distribution_checkout", lambda *_args: object())
    monkeypatch.setattr(cli, "open_verified_bundle", lambda _checkout: nullcontext(object()))
    for name, value in {
        "HOME": host.home,
        "CODEX_HOME": host.codex_home,
        "BLENDER_USER_RESOURCES": host.resources,
        "BLENDER_USER_CONFIG": host.config,
        "BLENDER_USER_EXTENSIONS": host.extensions,
    }.items():
        monkeypatch.setenv(name, str(value))
    args = SimpleNamespace(
        bundle_root=host.bundle,
        expected_distribution_commit="a" * 40,
        blender=host.blender,
        codex=host.codex,
        uv=host.uv,
    )

    with pytest.raises(InstallerError, match="host capability probe failed"):
        with cli._context(args):
            raise AssertionError("wrong-version Python reached installer context")


def test_absent_semantic_codex_restored_receipt_delta_is_exact(tmp_path: Path) -> None:
    image_path = tmp_path / "image"
    image_path.write_bytes(b"image")
    with SafeRoot.open(tmp_path, os.getuid(), tmp_path) as root:
        present = capture_file(root, Path("image"))
    action = cli._action(
        0,
        ActionKind.CODEX_FILE,
        ActionState.RESTORING,
        tmp_path / "config.toml",
        tmp_path / "stage",
        tmp_path / "recovery",
        FileImage.absent(),
        intended=present,
        actual=present,
        recovery_image=FileImage.absent(),
        rollback_intended=present,
        rollback_displaced=present,
    )
    receipt = Receipt(
        1,
        UUID("12345678-1234-4234-9234-123456789abc"),
        1,
        None,
        ReceiptStatus.ROLLBACK_PENDING,
        "2026-01-01T00:00:00Z",
        {},
        {},
        {},
        (),
        (action,),
        {},
    )

    assert cli._receipt_transition(
        receipt,
        replace(receipt, actions=(replace(action, state=ActionState.RESTORED),)),
    )


def test_reversed_selector_rejects_cross_install_before_receipt_settle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested = UUID("12345678-1234-4234-9234-123456789abc")
    reversed_id = UUID("87654321-4321-4321-8321-cba987654321")
    state_path = tmp_path / "state"
    receipts = state_path / "receipts"
    receipts.mkdir(parents=True)
    receipt_file = receipts / f"{reversed_id}.json"
    receipt_file.write_bytes(b"receipt")
    temp = receipts / f".blender-mcp-installer.{reversed_id}.{reversed_id}.json.tmp"
    temp.write_bytes(b"temp")
    image_file = tmp_path / "image"
    image_file.write_bytes(b"image")
    with SafeRoot.open(tmp_path, os.getuid(), tmp_path) as boundary:
        image = capture_file(boundary, Path("image"))
    selector = ActiveSelector(1, 2, reversed_id, f"{reversed_id}.json")
    candidate = SimpleNamespace(
        install_id=reversed_id,
        generation=2,
        status=ReceiptStatus.ROLLBACK_PENDING,
        targets=(
            SimpleNamespace(
                role=TargetRole.ACTIVE_SELECTOR,
                pre=image,
                install_post=image,
            ),
        ),
    )
    roots = SimpleNamespace(receipt=lambda install_id: receipts / f"{install_id}.json")
    monkeypatch.setattr(cli, "load_receipt", lambda *_args: candidate)
    monkeypatch.setattr(cli, "capture_file", lambda *_args: image)
    monkeypatch.setattr(
        cli,
        "load_atomic_json_pair",
        lambda *_args: (selector.to_dict(), None),
    )
    settled: list[UUID] = []
    monkeypatch.setattr(
        cli,
        "_settle_known_receipt_atomic_json",
        lambda _roots, _bundle, _manifest, install_id, _state, _fault: settled.append(install_id),
    )
    before = (receipt_file.read_bytes(), temp.read_bytes())

    with SafeRoot.open(state_path, os.getuid(), state_path) as state:
        with pytest.raises(InstallerError, match="active selector recovery conflict"):
            cli._discover_reversed_selector_receipt(
                roots,
                object(),
                "0" * 64,
                state,
                NoOpFaultInjector(),
                requested,
            )

    assert settled == []
    assert (receipt_file.read_bytes(), temp.read_bytes()) == before


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
            roots,
            context.source_bundle,
            context.manifest_sha256,
            installed.install_id,
            state,
            NoOpFaultInjector(),
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


_BASELINE_EXTENSION_SOURCES = (
    "__init__.py",
    "capture_output.py",
    "cli.py",
    "deferred_tool.py",
    "execute_blocking.py",
    "execute_interactive.py",
    "mcp_to_blender_server.py",
    "weak_sandbox.py",
)


def _compile_extension_sources(root: Path, sources: tuple[str, ...]) -> None:
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import py_compile;"
            + "".join(f"py_compile.compile({source!r},doraise=True);" for source in sources),
        ],
        cwd=root,
        check=True,
    )


def _extension_rollback_fixture(
    host: HostHarness,
) -> tuple[InstallRoots, StagedBundle, Receipt, Path, TreeImage]:
    manifest = parse_manifest((ARTIFACTS / "manifest.json").read_bytes())
    bundle = StagedBundle(ARTIFACTS, manifest)
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
    cli._ensure_mutation_roots(roots)
    roots.receipts.mkdir(mode=0o700)
    install_id = UUID("12345678-1234-4234-9234-123456789abc")
    roots.previous_active(install_id).parent.mkdir(parents=True, mode=0o700)
    roots.extension_target.mkdir(parents=True)
    with zipfile.ZipFile(bundle.extension_path) as archive:
        archive.extractall(roots.extension_target)
    for path in roots.extension_target.rglob("*"):
        if path.is_file():
            path.chmod(0o644)
    _compile_extension_sources(roots.extension_target, _BASELINE_EXTENSION_SOURCES)
    with SafeRoot.open(host.extensions, os.getuid(), host.resources) as extensions:
        extension_post = capture_tree(extensions, Path("user_default/mcp"))
    selector = cli._selector(None, install_id, 1)
    roots.active.write_text(json.dumps(selector.to_dict(), sort_keys=True) + "\n")
    roots.active.chmod(0o600)
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        active_post = capture_file(state, Path("active.json"))
    absent_tree = TreeImage.absent()
    absent_file = FileImage.absent()
    actions = (
        cli._action(
            0,
            ActionKind.BUNDLE_STAGE,
            ActionState.CLEANED,
            roots.bundle_stage(install_id),
            roots.bundle_stage(install_id),
            None,
            absent_tree,
            intended=extension_post,
        ),
        cli._action(
            1,
            ActionKind.RUNTIME_TREE,
            ActionState.PLANNED,
            roots.runtime,
            roots.runtime_stage(install_id),
            roots.runtime_recovery(install_id),
            absent_tree,
        ),
        cli._action(
            2,
            ActionKind.EXTENSION_TREE,
            ActionState.COMPLETED,
            roots.extension_target,
            roots.extension_stage(install_id),
            roots.extension_recovery(install_id),
            absent_tree,
            intended=extension_post,
            actual=extension_post,
        ),
        cli._action(
            3,
            ActionKind.USERPREF_FILE,
            ActionState.PLANNED,
            roots.userpref_target,
            roots.userpref_stage(install_id),
            roots.userpref_recovery(install_id),
            absent_file,
        ),
        cli._action(
            4,
            ActionKind.CODEX_FILE,
            ActionState.PLANNED,
            roots.codex_config,
            roots.codex_stage(install_id),
            roots.codex_recovery(install_id),
            absent_file,
        ),
    )
    receipt = Receipt(
        1,
        install_id,
        1,
        None,
        ReceiptStatus.INSTALLED,
        "2026-01-01T00:00:00Z",
        {"version": manifest.bundle_version, "manifest_sha256": "0" * 64},
        {
            "home": str(roots.home),
            "codex_home": str(roots.codex_home),
            "blender_executable": str(roots.blender.executable),
            "blender_architecture": roots.blender.architecture,
            "blender_version": roots.blender.version,
            "blender_user_resources": str(roots.blender.user_resources),
            "blender_user_config": str(roots.blender.user_config),
            "blender_user_extensions": str(roots.blender.user_extensions),
            "codex_version": "0.148.0-alpha.9",
            "uv_version": "0.12.2",
            "python_version": "3.13.13",
        },
        {"all_four_collected_for_this_workflow": True},
        (
            cli._target(TargetRole.RUNTIME, roots.runtime, BoundaryRole.DATA_ROOT, absent_tree),
            cli._target(
                TargetRole.BLENDER_EXTENSION,
                roots.extension_target,
                BoundaryRole.BLENDER_EXTENSIONS,
                absent_tree,
                post=extension_post,
            ),
            cli._target(
                TargetRole.BLENDER_USERPREF,
                roots.userpref_target,
                BoundaryRole.BLENDER_CONFIG,
                absent_file,
            ),
            cli._target(
                TargetRole.CODEX_CONFIG,
                roots.codex_config,
                BoundaryRole.CODEX_HOME,
                absent_file,
            ),
            cli._target(
                TargetRole.ACTIVE_SELECTOR,
                roots.active,
                BoundaryRole.STATE_ROOT,
                absent_file,
                post=active_post,
            ),
        ),
        actions,
        {"configured": True, "live": "not_run"},
    )
    receipt_path = roots.receipt(install_id)
    receipt_path.write_text(json.dumps(receipt.to_dict(), sort_keys=True) + "\n")
    receipt_path.chmod(0o600)
    return roots, bundle, receipt, receipt_path, extension_post


def test_extension_rollback_passes_post_provenance_and_rejects_unrecorded_pyc(
    host: HostHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots, bundle, receipt, receipt_path, extension_post = _extension_rollback_fixture(host)
    foreign = roots.extension_target / "__pycache__/cli.cpython-999.pyc"
    foreign.write_bytes(b"foreign")
    foreign.chmod(0o644)
    compare = cli.compare_extension_tree
    receipt_before = receipt_path.read_bytes()
    active_before = roots.active.read_bytes()
    with SafeRoot.open(host.extensions, os.getuid(), host.resources) as extensions:
        extension_before = capture_tree(extensions, Path("user_default/mcp"))
    provenances: list[TreeImage | None] = []

    def tracked_compare(payload, current, provenance=None):
        provenances.append(provenance)
        return compare(payload, current, provenance)

    monkeypatch.setattr(cli, "compare_extension_tree", tracked_compare)
    with pytest.raises(InstallerError, match="rollback preflight conflict"):
        cli._rollback_receipt(
            roots,
            bundle,
            object(),
            receipt,
            NoOpFaultInjector(),
            manifest_sha256="0" * 64,
        )
    assert provenances == [extension_post]
    assert receipt_path.read_bytes() == receipt_before
    assert roots.active.read_bytes() == active_before
    with SafeRoot.open(host.extensions, os.getuid(), host.resources) as extensions:
        assert capture_tree(extensions, Path("user_default/mcp")) == extension_before
    assert foreign.read_bytes() == b"foreign"


def test_extension_rollback_cleanup_is_retryable_at_native_restore_fault(
    host: HostHarness,
) -> None:
    roots, bundle, receipt, receipt_path, _ = _extension_rollback_fixture(host)

    with pytest.raises(SystemExit, match="70"):
        cli._rollback_receipt(
            roots,
            bundle,
            object(),
            receipt,
            cli.ExitFaultInjector("after_extension_tree_restore_move", 70),
            manifest_sha256="0" * 64,
        )

    recovery_cache = roots.extension_recovery(receipt.install_id) / "__pycache__"
    assert not roots.extension_target.exists()
    assert recovery_cache.is_dir() and len(tuple(recovery_cache.glob("*.pyc"))) == 8
    pending = cli.load_receipt(receipt_path, roots)
    rolled = cli._rollback_receipt(
        roots,
        bundle,
        object(),
        pending,
        NoOpFaultInjector(),
        manifest_sha256="0" * 64,
    )
    assert rolled.status is ReceiptStatus.ROLLED_BACK
    assert not roots.extension_target.exists()
    assert not roots.extension_recovery(receipt.install_id).exists()


@pytest.mark.parametrize(
    "conflict",
    [
        "foreign-pyc",
        "mapped-unrecorded",
        "unmapped",
        "nested",
        "source-modified",
        "baseline-pyc-changed",
    ],
)
def test_extension_cache_conflicts_fail_before_rollback_intent(
    host: HostHarness, conflict: str
) -> None:
    roots, bundle, receipt, receipt_path, _ = _extension_rollback_fixture(host)
    if conflict == "foreign-pyc":
        (roots.extension_target / "foreign.pyc").write_bytes(b"foreign")
    elif conflict == "mapped-unrecorded":
        cache = roots.extension_target / "__pycache__"
        (cache / "cli.cpython-999.pyc").write_bytes(b"foreign")
    elif conflict == "unmapped":
        cache = roots.extension_target / "__pycache__"
        (cache / "foreign.cpython-313.pyc").write_bytes(b"foreign")
    elif conflict == "nested":
        cache = roots.extension_target / "nested/__pycache__"
        cache.mkdir(parents=True)
        (cache / "capture_output.cpython-313.pyc").write_bytes(b"foreign")
    else:
        if conflict == "source-modified":
            (roots.extension_target / "capture_output.py").write_bytes(b"modified")
        elif conflict == "baseline-pyc-changed":
            pyc = next((roots.extension_target / "__pycache__").glob("capture_output.*.pyc"))
            pyc.write_bytes(b"modified")
    receipt_before = receipt_path.read_bytes()
    active_before = roots.active.read_bytes()
    with SafeRoot.open(host.extensions, os.getuid(), host.resources) as extensions:
        extension_before = capture_tree(extensions, Path("user_default/mcp"))

    with pytest.raises(InstallerError, match="rollback preflight conflict"):
        cli._rollback_receipt(
            roots,
            bundle,
            object(),
            receipt,
            NoOpFaultInjector(),
            manifest_sha256="0" * 64,
        )

    assert receipt_path.read_bytes() == receipt_before
    assert roots.active.read_bytes() == active_before
    with SafeRoot.open(host.extensions, os.getuid(), host.resources) as extensions:
        assert capture_tree(extensions, Path("user_default/mcp")) == extension_before


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
    (kind, preimage, point, command)
    for kind, preimages in _PREIMAGES.items()
    for preimage in preimages
    for point, commands in _applicable_points(kind, preimage).items()
    for command in sorted(commands)
)


def _crash_receipt_path(state_root: Path, requested: Path | None) -> Path | None:
    if requested is not None:
        return requested
    receipts = tuple((state_root / "receipts").glob("[0-9a-f]*.json"))
    for candidate in sorted(receipts, key=lambda path: path.stat().st_mtime_ns, reverse=True):
        if json.loads(candidate.read_text())["status"] in {"rollback_pending", "rolled_back"}:
            return candidate
    for selector_name in ("pending.json", "active.json"):
        selector = state_root / selector_name
        if selector.exists():
            value = json.loads(selector.read_text())
            return state_root / "receipts" / value["receipt_basename"]
    return None if not receipts else max(receipts, key=lambda path: path.stat().st_mtime_ns)


def _captured(path: Path, *, tree: bool):
    if not path.parent.exists():
        return TreeImage.absent() if tree else FileImage.absent()
    parent_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    with SafeRoot(path.parent, os.getuid(), parent_fd) as safe:
        return capture_tree(safe, Path(path.name)) if tree else capture_file(safe, Path(path.name))


def _native_point_tuple_matches(
    action: ReceiptAction, suffix: str, physical: tuple[object, object, object]
) -> bool:
    absent = TreeImage.absent() if isinstance(action.pre, TreeImage) else FileImage.absent()
    post = action.actual_post or action.intended_post
    expected = {
        "planned": (action.pre, absent, absent),
        "stage": (action.pre, post, absent),
        "swap": (post, action.pre, absent),
        "park": (post, absent, action.pre),
        "publish": (post, absent, absent),
        "completed": (
            post,
            absent,
            action.pre if action.pre.state.value == "present" else absent,
        ),
        "restore_swap": (action.pre, absent, post),
        "restore_move": (action.pre, absent, post),
        "restore_cleanup": (action.pre, absent, absent),
    }[suffix]
    return physical == expected


def test_native_restoring_prefix_probe_rejects_pre_swap_orientation(tmp_path: Path) -> None:
    root_path = tmp_path / "root"
    root_path.mkdir()
    (root_path / "pre").write_bytes(b"pre")
    (root_path / "post").write_bytes(b"post")
    with SafeRoot.open(root_path, os.getuid(), root_path) as root:
        pre = capture_file(root, Path("pre"))
        post = capture_file(root, Path("post"))
    absent = FileImage.absent()
    action = cli._action(
        0,
        ActionKind.USERPREF_FILE,
        ActionState.RESTORING,
        root_path / "target",
        root_path / "stage",
        root_path / "recovery",
        pre,
        intended=post,
        actual=post,
    )
    pre_swap = (post, absent, pre)
    post_restore_swap = (pre, absent, post)

    assert cli._native_rollback_tuple_valid(action, *pre_swap)
    assert cli._native_rollback_tuple_valid(action, *post_restore_swap)
    assert not _native_point_tuple_matches(action, "restore_swap", pre_swap)
    assert _native_point_tuple_matches(action, "restore_swap", post_restore_swap)


def _json_document(path: Path) -> dict[str, object] | None:
    return None if not path.exists() else json.loads(path.read_text())


def _assert_atomic_json_prefix(
    state_root: Path,
    requested: Path | None,
    fixture_kind: str,
    point: str,
    command: str,
    before_receipt: dict[str, object] | None,
) -> None:
    receipt_path = _crash_receipt_path(state_root, requested)
    if fixture_kind == "atomic_json" and command == "install":
        path = state_root / "pending.json"
        candidates = (path, *state_root.rglob("*.pending.json.tmp"))
        document = next(_json_document(candidate) for candidate in candidates if candidate.exists())
        pending = PendingSelector.from_dict(document)
        assert pending.generation == 1
        assert pending.previous_active is None
        assert pending.manifest_sha256 == (
            "2b799aff562693ce0b79e9df4737158b4b785e5c854e39673a289192adaf4a60"
        )
        old = None
        new = pending.to_dict()
        install_id = pending.install_id
    else:
        assert receipt_path is not None and before_receipt is not None
        path = receipt_path
        old = before_receipt
        new = json.loads(json.dumps(old))
        install_id = UUID(str(old["install_id"]))
        if fixture_kind == "codex_semantic":
            action = next(item for item in new["actions"] if item["kind"] == "codex_file")
            assert action["state"] == "restoring"
            assert action["pre"]["state"] == "absent"
            action["state"] = "restored"
        else:
            assert command == "rollback"
            assert new["status"] == "installed"
            new["status"] = "rollback_pending"
    temp = path.parent / f".blender-mcp-installer.{install_id}.{path.name}.tmp"
    if point == "after_json_file_fsync":
        assert _json_document(path) == old
        assert _json_document(temp) == new
    else:
        assert _json_document(path) == new
        assert _json_document(temp) == old
    assert tuple(state_root.rglob(".blender-mcp-installer.*.tmp")) == (
        () if old is None and point != "after_json_file_fsync" else (temp,)
    )


def _assert_pending_document(state_root: Path) -> PendingSelector:
    document = _json_document(state_root / "pending.json")
    assert document is not None
    pending = PendingSelector.from_dict(document)
    assert pending.to_dict() == document
    assert pending.manifest_sha256 == (
        "2b799aff562693ce0b79e9df4737158b4b785e5c854e39673a289192adaf4a60"
    )
    return pending


def _assert_selector_prefix(state_root: Path, receipt: dict[str, object], point: str) -> None:
    active_path = state_root / "active.json"
    previous_path = state_root / "backups" / str(receipt["install_id"]) / "previous-active.json"
    selector = next(item for item in receipt["targets"] if item["role"] == "active_selector")
    pre = FileImage.from_dict(selector["pre"])
    post = FileImage.from_dict(selector["install_post"])
    absent = FileImage.absent()
    if point == "after_rollback_intent":
        expected = (post, pre if pre.state.value == "present" else absent)
    elif point == "after_active_restore_cleanup":
        expected = (pre, absent)
    else:
        expected = (pre, post)
    assert (_captured(active_path, tree=False), _captured(previous_path, tree=False)) == expected


def _assert_install_selector_prefix(state_root: Path, point: str) -> None:
    pending = _assert_pending_document(state_root)
    new = ActiveSelector(
        1, pending.generation, pending.install_id, pending.receipt_basename
    ).to_dict()
    old = None if pending.previous_active is None else pending.previous_active.to_dict()
    active = state_root / "active.json"
    previous = state_root / "backups" / str(pending.install_id) / "previous-active.json"
    temp = state_root / f".blender-mcp-installer.{pending.install_id}.active.json.tmp"
    assert _json_document(active) == new
    if point == "after_active_swap":
        assert _json_document(temp) == old
        assert _json_document(previous) is None
    else:
        assert _json_document(temp) is None
        assert _json_document(previous) == old


def _assert_exact_crash_prefix(
    state_root: Path,
    requested: Path | None,
    fixture_kind: str,
    preimage: str,
    point: str,
    command: str,
    before_receipt: dict[str, object] | None,
    before_semantic_target: FileImage | None,
) -> None:
    semantic_atomic = (
        fixture_kind == "codex_semantic"
        and preimage == "absent"
        and point.startswith("after_json_")
    )
    if point.startswith("after_json_"):
        _assert_atomic_json_prefix(
            state_root, requested, fixture_kind, point, command, before_receipt
        )
        if not semantic_atomic:
            return
    elif point in {
        "after_active_publish",
        "after_active_swap",
        "after_active_park",
        "after_active_parent_fsync",
    }:
        _assert_install_selector_prefix(state_root, point)
    else:
        assert not tuple(state_root.rglob(".blender-mcp-installer.*.tmp"))
    if point == "after_pending_publish":
        pending = _assert_pending_document(state_root)
        assert _json_document(state_root / "receipts" / pending.receipt_basename) is None
        assert _json_document(state_root / "active.json") == (
            None if pending.previous_active is None else pending.previous_active.to_dict()
        )
        return
    receipt_path = _crash_receipt_path(state_root, requested)
    assert receipt_path is not None
    receipt = json.loads(receipt_path.read_text())
    rollback_prefix = (
        "restore" in point
        or point.startswith("after_rollback")
        or point.startswith("after_codex_semantic")
        or semantic_atomic
    )
    expected_status = (
        "rolled_back"
        if point in {"after_rollback_status", "after_active_restore_cleanup"}
        else "installed"
        if point in {"after_receipt_installed", "after_bundle_stage_cleanup"}
        else "rollback_pending"
        if rollback_prefix
        else "prepared"
    )
    assert receipt["status"] == expected_status

    expected_states = {
        "planned": "planned",
        "stage": "staged",
        "swap": "swapped",
        "park": "parked",
        "publish": "published",
        "completed": "completed",
        "restore_swap": "restoring",
        "restore_move": "restoring",
        "restore_cleanup": "restored",
    }
    selected = next(
        (action for action in receipt["actions"] if point.startswith(f"after_{action['kind']}_")),
        None,
    )
    if selected is not None:
        suffix = point.removeprefix(f"after_{selected['kind']}_")
        if suffix in expected_states:
            assert selected["state"] == expected_states[suffix]
    semantic_states = {
        "after_codex_semantic_stage_fsync": "semantic_staged",
        "after_codex_semantic_swap": "semantic_staged",
        "after_codex_semantic_receipt": "semantic_swapped",
        "after_codex_semantic_displaced_cleanup": "restoring",
        "after_codex_semantic_recovery_cleanup": "restored",
    }
    if point in semantic_states:
        selected = next(action for action in receipt["actions"] if action["kind"] == "codex_file")
        assert selected["state"] == semantic_states[point]
    if selected is not None and selected["kind"] != "bundle_stage":
        action = ReceiptAction.from_dict(selected)
        target = Path(selected["target_path"])
        tree = selected["kind"] in {"runtime_tree", "extension_tree"}
        stage = target.parent / selected["stage_basename"]
        recovery = target.parent / selected["recovery_basename"]
        physical = (
            _captured(target, tree=tree),
            _captured(stage, tree=tree),
            _captured(recovery, tree=tree),
        )
        if selected["rollback_intended"] is None:
            suffix = point.removeprefix(f"after_{selected['kind']}_")
            assert _native_point_tuple_matches(action, suffix, physical)
        else:
            rollback_stage = target.parent / (
                f".blender-mcp-installer.{receipt['install_id']}.codex.rollback.stage"
            )
            rollback_image = _captured(rollback_stage, tree=False)
            intended = FileImage.from_dict(selected["rollback_intended"])
            displaced = (
                None
                if selected["rollback_displaced"] is None
                else FileImage.from_dict(selected["rollback_displaced"])
            )
            absent = FileImage.absent()
            assert before_semantic_target is not None
            semantic_rows = {
                "after_codex_semantic_stage_fsync": (
                    (before_semantic_target, absent, action.pre, intended),
                    None,
                ),
                "after_codex_semantic_swap": (
                    (intended, absent, action.pre, before_semantic_target),
                    None,
                ),
                "after_codex_semantic_receipt": (
                    (intended, absent, action.pre, before_semantic_target),
                    before_semantic_target,
                ),
                "after_codex_semantic_displaced_cleanup": (
                    (intended, absent, action.pre, absent),
                    before_semantic_target,
                ),
                "after_codex_semantic_recovery_cleanup": (
                    (intended, absent, absent, absent),
                    before_semantic_target,
                ),
            }
            if semantic_atomic:
                expected_physical = (intended, absent, absent, absent)
                expected_displaced = displaced
            else:
                expected_physical, expected_displaced = semantic_rows[point]
            assert (*physical, rollback_image) == expected_physical
            assert displaced == expected_displaced

    bundle_action = next(
        (action for action in receipt["actions"] if action["kind"] == "bundle_stage"), None
    )
    if point.startswith("after_bundle_stage_") or point == "after_receipt_installed":
        assert bundle_action is not None
        expected = (
            TreeImage.absent()
            if point in {"after_bundle_stage_planned", "after_bundle_stage_cleanup"}
            else TreeImage.from_dict(bundle_action["intended_post"])
        )
        assert _captured(Path(bundle_action["target_path"]), tree=True) == expected

    if point == "after_pending_remove":
        assert not (state_root / "pending.json").exists()
        _assert_selector_prefix(state_root, receipt, "after_rollback_intent")
    if point == "after_receipt_publish":
        pending = _assert_pending_document(state_root)
        selector = next(item for item in receipt["targets"] if item["role"] == "active_selector")
        assert receipt["actions"] == []
        assert pending.receipt_basename == receipt_path.name
        assert _captured(state_root / "active.json", tree=False) == FileImage.from_dict(
            selector["pre"]
        )
        assert (
            _captured(
                state_root / "backups" / receipt["install_id"] / "previous-active.json",
                tree=False,
            )
            == FileImage.absent()
        )
    if point.startswith("after_active_restore") or point in {
        "after_rollback_intent",
        "after_rollback_status",
    }:
        _assert_selector_prefix(state_root, receipt, point)


@pytest.mark.parametrize(("fixture_kind", "preimage", "point", "command"), _FAULT_CASES)
def test_closed_fault_matrix_exits_70_then_fresh_process_recovers_exactly(
    tmp_path: Path, fixture_kind: str, preimage: str, point: str, command: str
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
    semantic_atomic = (
        fixture_kind == "codex_semantic"
        and preimage == "absent"
        and point.startswith("after_json_")
    )
    rollback_point = rollback_point or semantic_atomic
    receipt: Path | None = None
    if semantic_atomic:
        seeded = invoke("install", recover=True)
        assert seeded.returncode == 0, seeded.stderr + seeded.stdout
        active = json.loads(
            (host_root / "home/.local/state/blender-mcp-installer/active.json").read_text()
        )
        semantic_receipt = (
            host_root
            / "home/.local/state/blender-mcp-installer/receipts"
            / active["receipt_basename"]
        )
        prepared = invoke(
            "rollback",
            recover=False,
            receipt=semantic_receipt,
            selected_point="after_codex_semantic_displaced_cleanup",
        )
        assert prepared.returncode == 70, prepared.stderr + prepared.stdout
        if command == "rollback":
            receipt = semantic_receipt
    elif command == "install" and rollback_point:
        seeded = invoke("install", recover=True)
        assert seeded.returncode == 0, seeded.stderr + seeded.stdout
        if fixture_kind == "active_selector" and preimage == "present":
            (scenario / "force-change").write_text("1\n")
            seeded = invoke("install", recover=True)
            assert seeded.returncode == 0, seeded.stderr + seeded.stdout
        active = json.loads(
            (host_root / "home/.local/state/blender-mcp-installer/active.json").read_text()
        )
        prepared_path = (
            host_root
            / "home/.local/state/blender-mcp-installer/receipts"
            / active["receipt_basename"]
        )
        prepared = json.loads(prepared_path.read_text())
        prepared["status"] = "prepared"
        prepared["verification"]["configured"] = False
        selected_action = next(
            (
                action
                for action in prepared["actions"]
                if point.startswith(f"after_{action['kind']}_")
            ),
            None,
        )
        if fixture_kind == "codex_file" and selected_action is not None:
            selected_action["state"] = "staged"
            selected_action["actual_post"] = None
            selected_action["recovery_image"] = None
        if preimage == "present" and point.endswith("_restore_move"):
            assert selected_action is not None
            target = Path(selected_action["target_path"])
            stage = target.parent / selected_action["stage_basename"]
            recovery = target.parent / selected_action["recovery_basename"]
            os.rename(recovery, stage)
            selected_action["state"] = "staged"
            selected_action["actual_post"] = None
            selected_action["recovery_image"] = None
        prepared_path.write_text(json.dumps(prepared, sort_keys=True, separators=(",", ":")) + "\n")
    elif command == "install" and fixture_kind == "active_selector" and preimage == "present":
        seeded = invoke("install", recover=True)
        assert seeded.returncode == 0, seeded.stderr + seeded.stdout
        (scenario / "force-change").write_text("1\n")
    if command == "rollback" and not semantic_atomic:
        staged_move = preimage == "present" and point.endswith("_restore_move")
        if staged_move and fixture_kind != "codex_file":
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
        if fixture_kind == "codex_file":
            prepared = json.loads(receipt.read_text())
            prepared["status"] = "prepared"
            prepared["verification"]["configured"] = False
            selected_action = next(
                action for action in prepared["actions"] if action["kind"] == "codex_file"
            )
            selected_action["state"] = "staged"
            selected_action["actual_post"] = None
            selected_action["recovery_image"] = None
            if staged_move:
                target = Path(selected_action["target_path"])
                os.rename(
                    target.parent / selected_action["recovery_basename"],
                    target.parent / selected_action["stage_basename"],
                )
            receipt.write_text(json.dumps(prepared, sort_keys=True, separators=(",", ":")) + "\n")

    state_root = host_root / "home/.local/state/blender-mcp-installer"
    before_receipt_path = _crash_receipt_path(state_root, receipt)
    before_receipt = (
        None if before_receipt_path is None else json.loads(before_receipt_path.read_text())
    )
    before_semantic_target = None
    if fixture_kind == "codex_semantic" and before_receipt is not None:
        codex_action = next(
            action for action in before_receipt["actions"] if action["kind"] == "codex_file"
        )
        semantic_marker = scenario / ".semantic-seeded"
        if not semantic_marker.exists():
            with Path(codex_action["target_path"]).open("a") as stream:
                stream.write('\n[foreign_after]\nsecret = "SECRET-SENTINEL"\n')
            semantic_marker.write_text("seeded\n")
        before_semantic_target = _captured(Path(codex_action["target_path"]), tree=False)

    crashed = invoke(command, recover=False, receipt=receipt)
    assert crashed.returncode == 70, crashed.stderr + crashed.stdout
    assert "SECRET-SENTINEL" not in crashed.stdout + crashed.stderr
    _assert_exact_crash_prefix(
        host_root / "home/.local/state/blender-mcp-installer",
        receipt,
        fixture_kind,
        preimage,
        point,
        command,
        before_receipt,
        before_semantic_target,
    )
    recovered = invoke(command, recover=True, receipt=receipt)
    assert recovered.returncode == 0, recovered.stderr + recovered.stdout
    assert "SECRET-SENTINEL" not in recovered.stdout + recovered.stderr
    recovered_again = invoke(command, recover=True, receipt=receipt)
    assert recovered_again.returncode == 0, recovered_again.stderr + recovered_again.stdout
    assert "SECRET-SENTINEL" not in recovered_again.stdout + recovered_again.stderr

    assert not list(state_root.rglob(".blender-mcp-installer.*.tmp"))
    for owned_file in state_root.rglob("*"):
        if owned_file.is_file():
            assert b"SECRET-SENTINEL" not in owned_file.read_bytes()
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
            expected_target = (
                action["rollback_intended"]
                if action["kind"] == "codex_file" and action["rollback_intended"] is not None
                else action["pre"]
            )
            assert image_at(target, tree=tree) == image_type.from_dict(expected_target)
            assert image_at(recovery_path, tree=tree).state.value == "absent"

    selector = next(target for target in terminal["targets"] if target["role"] == "active_selector")
    assert image_at(Path(selector["path"]), tree=False) == FileImage.from_dict(
        selector["install_post"] if command == "install" else selector["pre"]
    )
