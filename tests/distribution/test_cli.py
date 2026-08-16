from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

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
from blender_mcp_installer.model import BlenderPaths, InstallRoots  # noqa: E402
from blender_mcp_installer.verification import HostCapabilities  # noqa: E402
from tests.distribution.fake_host import HostHarness  # noqa: E402


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
    host: HostHarness, monkeypatch: pytest.MonkeyPatch, bad: str
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
        Verified(), StagedBundle(ARTIFACTS, manifest), capabilities, blender, roots
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
    rolled = cli._rollback_receipt(
        roots,
        context.source_bundle,
        blender,
        installed,
        NoOpFaultInjector(),
    )
    assert rolled.status.value == "rolled_back"
    assert not roots.active.exists()
    assert not roots.runtime.exists()
    assert not roots.extension_target.exists()
    assert not roots.userpref_target.exists()
    assert not roots.codex_config.exists()
