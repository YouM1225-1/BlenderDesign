from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError  # noqa: E402
from blender_mcp_installer.runtime import _launcher_source  # noqa: E402
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, usage_lock  # noqa: E402
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root  # noqa: E402


@pytest.mark.parametrize("status", ["prepared", "installed"])
def test_external_bootstrap_gates_runtime_before_exec(tmp_path, status):
    home = (tmp_path / "home").resolve()
    home.mkdir(mode=0o700)
    roots = UpgradeRoots(home, home / ".codex")
    roots.codex_home.mkdir(mode=0o700)
    runtime = home / ".local/share/blender-lab-mcp/runtime"
    (runtime / "bin").mkdir(parents=True)
    (runtime / "bin/python").symlink_to(Path(sys.executable).resolve())
    (runtime / "bin/blender-mcp").write_text(
        "import time; print('payload-ready', flush=True); time.sleep(30)"
    )
    launcher = runtime / "bin/blender-mcp-managed"
    environment = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "BLENDER_MCP_BOOTSTRAP_PYTHON": str(Path(sys.executable).resolve()),
        "BLENDER_MCP_CODEX_HOME": str(roots.codex_home),
    }
    launcher.write_bytes(_launcher_source(environment))
    launcher.chmod(0o700)
    info = runtime.stat()
    identifier = str(uuid4())
    with state_root(roots) as state:
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        (state.path / "receipts").mkdir()
        (state.path / "active.json").write_text(json.dumps({"install_id": identifier}))
        (state.path / "receipts" / f"{identifier}.json").write_text(
            json.dumps(
                {
                    "install_id": identifier,
                    "status": status,
                    "targets": [
                        {
                            "role": "runtime",
                            "path": str(runtime),
                            "install_post": {"dev": info.st_dev, "ino": info.st_ino},
                        }
                    ],
                }
            )
        )
        process = subprocess.Popen(
            [str(launcher)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            assert process.stdout is not None
            if status == "prepared":
                out, error = process.communicate(timeout=5)
                assert process.returncode == 75, error
                assert not out
            else:
                assert process.stdout.readline().strip() == "payload-ready"
                with usage_lock(state, info.st_dev, info.st_ino, exclusive=True) as acquired:
                    assert not acquired
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)


def test_custom_codex_cache_cannot_supply_bootstrap(tmp_path):
    custom_codex = tmp_path / "custom-codex"
    bootstrap = (
        custom_codex
        / "plugins/cache/official-blender-mcp/blender-mcp-installer/old/bin/python"
    )
    environment = {
        "HOME": str(tmp_path / "home"),
        "PATH": "/usr/bin:/bin",
        "BLENDER_MCP_BOOTSTRAP_PYTHON": str(bootstrap),
        "BLENDER_MCP_CODEX_HOME": str(custom_codex),
    }
    with pytest.raises(InstallerError, match="retired program tree"):
        _launcher_source(environment)


@pytest.mark.parametrize("inventory", [
    "12345 {uid} Tue Sep 8 10:00:00 2026 /usr/bin/printf don't\n",
    "not a process row\n",
    "² {uid} Tue Sep 8 10:00:00 2026 /usr/bin/printf hello\n",
    subprocess.CalledProcessError(1, "ps"),
    subprocess.TimeoutExpired("ps", 15),
    OSError("ps unavailable"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte"),
])
def test_process_inventory_failure_refuses_install_without_recovery(tmp_path, monkeypatch, inventory):
    import os
    from types import SimpleNamespace
    from blender_mcp_installer import cli, upgrade_handoff
    from tests.distribution.test_cli import _userpref_completion_fault_scenario

    def ps(*_args, **_kwargs):
        if isinstance(inventory, Exception):
            raise inventory
        return SimpleNamespace(stdout=inventory.format(uid=os.getuid()))

    monkeypatch.setattr(upgrade_handoff.subprocess, "run", ps)
    with _userpref_completion_fault_scenario(tmp_path) as context:
        roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
        monkeypatch.setattr(cli, "_changed_install", lambda *_args: upgrade_handoff.process_snapshot(
            roots, context.roots.runtime, context.host.codex_bin))
        monkeypatch.setattr(cli, "recover_active", lambda *_args, **_kwargs: pytest.fail("barrier refusal entered recovery"))
        with pytest.raises(upgrade_handoff.LegacyHandoffRequired):
            cli.install(SimpleNamespace())
        assert not context.roots.runtime.exists()
        assert not context.roots.active.exists()
