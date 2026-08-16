from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"),
)

from blender_mcp_installer.bundle import parse_manifest
from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer import verification
from blender_mcp_installer.verification import (
    HostCapabilityError,
    HostCapabilities,
    InstallationInspection,
    inspect_installation,
    probe_host,
    verify_live,
)


MANIFEST = parse_manifest(
    (
        Path(__file__).parents[2] / "plugins/blender-mcp-installer/artifacts/manifest.json"
    ).read_bytes()
)


class HostRunner:
    def __init__(self, *, json_help: bool = True) -> None:
        self.json_help = json_help
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv, *, cwd, env):
        args = tuple(map(str, argv))
        self.calls.append(args)
        if args[-1:] == ("--version",):
            values = {
                "codex": "codex-cli 0.148.0-alpha.9\n",
                "uv": "uv 0.12.2\n",
                "Blender": "Blender 5.2.0\n",
                "python": "Python 3.13.13\n",
            }
            return SimpleNamespace(returncode=0, stdout=values[Path(args[0]).name], stderr="")
        if args[0] == "/usr/bin/lipo":
            return SimpleNamespace(returncode=0, stdout="arm64 x86_64\n", stderr="")
        if args[-3:] == ("mcp", "get", "--help"):
            return SimpleNamespace(
                returncode=0,
                stdout="usage: codex mcp get --json" if self.json_help else "usage",
                stderr="",
            )
        if args[-4:] == ("plugin", "marketplace", "add", "--help"):
            return SimpleNamespace(returncode=0, stdout="usage", stderr="")
        if args[-3:] == ("plugin", "add", "--help"):
            return SimpleNamespace(returncode=0, stdout="usage", stderr="")
        raise AssertionError(args)


def _executable(path: Path, name: str) -> Path:
    result = path / name
    result.write_text("#!/bin/sh\nexit 0\n")
    result.chmod(0o700)
    return result


def test_probe_host_uses_help_without_querying_unpublished_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = HostRunner()
    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    host = probe_host(*bins, {"SECRET": "not-forwarded"}, runner=runner)

    assert host.supported
    assert host.platform_system == "Darwin" and host.platform_machine == "arm64"
    assert host.blender_version == "5.2.0"
    assert host.codex_version == "0.148.0-alpha.9"
    assert host.uv_version == "0.12.2" and host.python_version == "3.13.13"
    assert host.blender_arches == ("arm64", "x86_64")
    assert not any(call[-4:] == ("mcp", "get", "blender", "--json") for call in runner.calls)
    assert all("SECRET" not in call for call in runner.calls)


def test_probe_host_unsupported_json_retains_redacted_version_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = HostRunner(json_help=False)
    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    with pytest.raises(HostCapabilityError, match="unsupported host capabilities") as caught:
        probe_host(*bins, {}, runner=runner)

    assert caught.value.capabilities.codex_version == "0.148.0-alpha.9"
    assert not caught.value.capabilities.codex_mcp_get_json
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "tool,version",
    [("uv", "uv 0.13.0\n"), ("Blender", "Blender 5.3.0\n"), ("python", "Python 3.14.0\n")],
)
def test_probe_host_rejects_unsupported_actual_versions_with_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, version: str
) -> None:
    runner = HostRunner()
    original = runner.__call__

    def changed(argv, *, cwd, env):
        if tuple(argv)[-1:] == ("--version",) and Path(argv[0]).name == tool:
            return SimpleNamespace(returncode=0, stdout=version, stderr="")
        return original(argv, cwd=cwd, env=env)

    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    with pytest.raises(HostCapabilityError) as caught:
        probe_host(*bins, {}, runner=changed)

    assert getattr(caught.value.capabilities, f"{tool.lower()}_version") == version.split()[1]


FIELDS = (
    "runtime",
    "extension_repository",
    "extension_id",
    "extension_version",
    "extension_payload_digest",
    "enablement",
    "preferences",
    "codex_policy",
    "codex_namespace",
    "codex_effective",
    "active_generation",
    "manifest_hash",
    "recorded_blender_executable",
)


def _host(tmp_path: Path, runner=object()) -> HostCapabilities:
    blender = _executable(tmp_path, "Blender")
    return HostCapabilities(
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
        blender,
        _executable(tmp_path, "codex"),
        _executable(tmp_path, "uv"),
        _executable(tmp_path, "python"),
        {"HOME": str(tmp_path)},
        runner,
    )


def _inspection(tmp_path: Path, **changes: object) -> InstallationInspection:
    target = tmp_path / "managed"
    target.write_text("same")
    values = {name: True for name in FIELDS}
    values.update(changes)
    return InstallationInspection(
        **values,
        host=_host(tmp_path),
        blender_executable=tmp_path / "Blender",
        runtime_command=(str(tmp_path / "managed-runtime"),),
        expected_tools=MANIFEST.tools,
        managed_targets=(target,),
        managed_images=("file:same",),
        active_install_id="00000000-0000-4000-8000-000000000001",
    )


def test_inspection_exact_requires_every_independent_field(tmp_path: Path) -> None:
    exact = _inspection(tmp_path)
    assert exact.exact
    for field in FIELDS:
        assert not replace(exact, **{field: False}).exact, field


def test_inspection_snapshots_all_targets_before_and_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _inspection(tmp_path)
    snapshots: list[tuple[str, ...]] = []

    def snapshot(paths):
        result = tuple(f"image-{len(snapshots)}" for _ in paths)
        snapshots.append(result)
        return result

    monkeypatch.setattr(
        "blender_mcp_installer.verification._managed_paths", lambda roots: before.managed_targets
    )
    monkeypatch.setattr("blender_mcp_installer.verification._snapshot", snapshot)
    monkeypatch.setattr(
        "blender_mcp_installer.verification._inspect",
        lambda bundle, roots, blender_state, host, images: replace(before, managed_images=images),
    )

    with pytest.raises(InstallerError, match="managed targets changed during inspection"):
        inspect_installation(SimpleNamespace(manifest=MANIFEST), object(), object(), before.host)
    assert len(snapshots) == 2


def test_inspection_still_takes_after_snapshot_when_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _inspection(tmp_path)
    calls = 0

    def snapshot(paths):
        nonlocal calls
        calls += 1
        return ("unchanged",)

    monkeypatch.setattr(
        "blender_mcp_installer.verification._managed_paths", lambda roots: before.managed_targets
    )
    monkeypatch.setattr("blender_mcp_installer.verification._snapshot", snapshot)
    monkeypatch.setattr(
        "blender_mcp_installer.verification._inspect",
        lambda *args: (_ for _ in ()).throw(ValueError("secret")),
    )

    with pytest.raises(InstallerError, match="installation inspection failed") as caught:
        inspect_installation(SimpleNamespace(manifest=MANIFEST), object(), object(), before.host)
    assert calls == 2 and "secret" not in str(caught.value)


def test_inspection_never_queries_effective_codex_before_active_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    resources = tmp_path / "resources"
    config = resources / "config"
    extensions = resources / "extensions"
    for path in (data_root, config, extensions):
        path.mkdir(parents=True)
    runtime = data_root / "runtime"
    launcher = runtime / "bin/blender-mcp-managed"
    roots = SimpleNamespace(
        data_root=data_root,
        runtime=runtime,
        extension_target=extensions / "user_default/mcp",
        userpref_target=config / "userpref.blend",
        codex_config=tmp_path / "codex/config.toml",
        active=tmp_path / "state/active.json",
        state_root=tmp_path / "state",
        receipts=tmp_path / "state/receipts",
        home=tmp_path,
    )
    blender = SimpleNamespace(
        repository="user_default",
        manifest_id="mcp",
        manifest_version="1.0.0",
        canonical_payload_digest="digest",
        enabled=True,
        online_access=True,
        host="localhost",
        port=9876,
        autostart=True,
        user_resources=resources,
        config_root=config,
        extensions_root=extensions,
        executable=tmp_path / "Blender",
        reported_architecture="arm64",
        version="5.2.0",
    )
    monkeypatch.setattr(
        verification,
        "inspect_runtime",
        lambda *args: SimpleNamespace(exact=True, launcher_path=launcher),
    )
    monkeypatch.setattr(
        verification,
        "load_extension_payload",
        lambda path: SimpleNamespace(canonical_digest="digest"),
    )
    monkeypatch.setattr(
        verification,
        "_effective",
        lambda *args: (_ for _ in ()).throw(AssertionError("prepublication query")),
    )

    inspected = verification._inspect(
        SimpleNamespace(
            manifest=MANIFEST,
            extension_path=tmp_path / "extension.zip",
            manifest_path=tmp_path / "manifest.json",
        ),
        roots,
        blender,
        _host(tmp_path),
        ("absent",) * 5,
    )

    assert not inspected.active_generation and not inspected.codex_effective


class LifecycleRunner:
    def __init__(self, blender: Path, *, listener: str = "selected") -> None:
        self.blender = blender
        self.listener = listener

    def __call__(self, argv, *, cwd, env):
        args = tuple(argv)
        selected = self.blender
        foreign = _executable(self.blender.parent, "Foreign")
        selected_stat = selected.stat()
        foreign_stat = foreign.stat()
        executable = selected if self.listener == "selected" else foreign
        info = selected_stat if self.listener == "selected" else foreign_stat
        if args == ("/usr/bin/pgrep", "-x", "Blender"):
            pids = "10\n" if self.listener != "missing" else ""
            return SimpleNamespace(returncode=0 if pids else 1, stdout=pids, stderr="")
        if args == ("/usr/sbin/lsof", "-nP", "-iTCP:9876", "-sTCP:LISTEN", "-FpcfDinu"):
            if self.listener == "missing":
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            listener = f"p10\ncBlender\nu{os.getuid()}\nf12\nn127.0.0.1:9876\n"
            if self.listener == "ambiguous":
                listener += f"p11\ncBlender\nu{os.getuid()}\nf13\nn127.0.0.1:9876\n"
            return SimpleNamespace(returncode=0, stdout=listener, stderr="")
        if args[:4] == ("/usr/sbin/lsof", "-a", "-p", args[3]):
            raw = (
                f"p10\ncBlender\nu{os.getuid()}\n"
                f"ftxt\nD{info.st_dev}\ni{info.st_ino}\nn{executable}\n"
            )
            return SimpleNamespace(returncode=0, stdout=raw, stderr="")
        raise AssertionError(args)


class Session:
    def __init__(self, tools=MANIFEST.tools, *, fail: str | None = None) -> None:
        self.tools = tools
        self.fail = fail
        self.calls: list[tuple[str, object]] = []
        self.closed = self.terminated = self.waited = False

    def initialize(self):
        self.calls.append(("initialize", None))
        if self.fail == "initialize":
            raise ValueError("secret protocol failure")
        return {"protocolVersion": "2025-06-18"}

    def list_tools(self):
        self.calls.append(("list_tools", None))
        return self.tools

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.fail == "call":
            raise ValueError("secret call failure")
        if self.fail == "call_result":
            return {"isError": True, "content": [{"type": "text", "text": "secret"}]}
        return {"content": [{"type": "text", "text": "{}"}]}

    def close(self):
        self.closed = True
        if self.fail == "close":
            raise ValueError("secret close failure")

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        self.waited = timeout
        if self.fail == "wait":
            raise subprocess.TimeoutExpired("secret", timeout)


class MCPProbe:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.command = None
        self.env = None

    def start(self, command, *, env):
        self.command = tuple(command)
        self.env = dict(env)
        return self.session


def _live(tmp_path: Path, session: Session, *, listener: str = "selected"):
    runner = LifecycleRunner(tmp_path / "Blender", listener=listener)
    inspection = replace(_inspection(tmp_path), host=_host(tmp_path, runner))
    probe = MCPProbe(session)
    hostile = {
        "HOME": str(tmp_path / "hostile-home"),
        "PYTHONPATH": "hostile-python",
        "BLENDER_MCP_HOST": "foreign.invalid",
        "BLENDER_MCP_PORT": "1",
        "BLENDER_USER_RESOURCES": str(tmp_path / "foreign-profile"),
    }
    return inspection, probe, hostile


def test_live_uses_hostile_parent_exact_catalog_and_only_read_only_no_arg_call(
    tmp_path: Path,
) -> None:
    session = Session()
    inspection, probe, hostile = _live(tmp_path, session)

    result = verify_live(
        SimpleNamespace(manifest=MANIFEST),
        inspection,
        inspection.runtime_command,
        inspection.host.codex_bin,
        hostile,
        probe,
    )

    assert result.parsed_codex and result.effective_codex
    assert result.mcp_catalog and result.blender_read_only and result.tool_count == 26
    assert probe.command == inspection.runtime_command and probe.env == hostile
    assert session.calls == [
        ("initialize", None),
        ("list_tools", None),
        ("get_blendfile_summary_datablocks", {}),
    ]
    assert session.closed and session.terminated and session.waited == 2.0


@pytest.mark.parametrize("listener", ["missing", "foreign", "ambiguous"])
def test_live_rejects_listener_not_uniquely_owned_by_selected_blender(
    tmp_path: Path, listener: str
) -> None:
    session = Session()
    inspection, probe, hostile = _live(tmp_path, session, listener=listener)
    with pytest.raises(InstallerError, match="selected Blender listener verification failed"):
        verify_live(
            SimpleNamespace(manifest=MANIFEST),
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert not session.calls


@pytest.mark.parametrize(
    "tools",
    [
        MANIFEST.tools[:-1],
        (*MANIFEST.tools, "extra"),
        tuple(reversed(MANIFEST.tools)),
        (*MANIFEST.tools[:-1], MANIFEST.tools[0]),
    ],
    ids=("missing", "extra", "reordered", "duplicate"),
)
def test_live_rejects_any_catalog_difference_and_cleans_up(tmp_path: Path, tools) -> None:
    session = Session(tools)
    inspection, probe, hostile = _live(tmp_path, session)
    with pytest.raises(InstallerError, match="MCP catalog verification failed"):
        verify_live(
            SimpleNamespace(manifest=MANIFEST),
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert session.closed and session.terminated and session.waited == 2.0
    assert all("execute" not in call[0] for call in session.calls)


@pytest.mark.parametrize(
    "failure,error",
    [
        ("initialize", "MCP handshake failed"),
        ("call", "Blender read-only verification failed"),
        ("call_result", "Blender read-only verification failed"),
        ("close", "MCP cleanup failed"),
        ("wait", "MCP cleanup failed"),
    ],
)
def test_live_redacts_failures_and_always_closes_terminates_waits(
    tmp_path: Path, failure: str, error: str
) -> None:
    session = Session(fail=failure)
    inspection, probe, hostile = _live(tmp_path, session)
    with pytest.raises(InstallerError, match=error) as caught:
        verify_live(
            SimpleNamespace(manifest=MANIFEST),
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert "secret" not in str(caught.value)
    assert session.closed and session.terminated and session.waited == 2.0


def test_live_detects_managed_target_change_after_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    inspection, probe, hostile = _live(tmp_path, session)
    calls = 0

    def changing_snapshot(paths):
        nonlocal calls
        calls += 1
        return tuple(f"{calls}:{path}" for path in paths)

    monkeypatch.setattr(
        "blender_mcp_installer.verification._snapshot",
        changing_snapshot,
    )
    with pytest.raises(InstallerError, match="managed targets changed during verification"):
        verify_live(
            SimpleNamespace(manifest=MANIFEST),
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert session.closed and session.terminated and session.waited == 2.0


def test_live_rejects_unconfigured_command_before_start(tmp_path: Path) -> None:
    session = Session()
    inspection, probe, hostile = _live(tmp_path, session)
    with pytest.raises(InstallerError, match="managed runtime command mismatch"):
        verify_live(
            SimpleNamespace(manifest=MANIFEST),
            inspection,
            (sys.executable, "-c", "print('foreign')"),
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command is None


def test_fixed_catalog_is_exactly_ordered_and_has_single_safe_probe() -> None:
    assert len(MANIFEST.tools) == 26
    assert MANIFEST.tools[2] == "get_blendfile_summary_datablocks"
    forbidden = ("execute", "render", "screenshot", "_for_cli")
    assert not any(part in "get_blendfile_summary_datablocks" for part in forbidden)
    assert json.loads(json.dumps(list(MANIFEST.tools))) == list(MANIFEST.tools)
