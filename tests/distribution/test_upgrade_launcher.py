from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest


REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError  # noqa: E402
from blender_mcp_installer.runtime import _launcher_source  # noqa: E402
from blender_mcp_installer.upgrade_locks import (  # noqa: E402
    device_usage_name,
    ensure_usage_lock,
    usage_lock,
    usage_name,
)
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root  # noqa: E402
from tests.distribution.remount import renumbering_python  # noqa: E402


@contextmanager
def _installed_runtime(tmp_path, status="installed", bootstrap=None, receipt_ino=None):
    """Install a lease-gated runtime; yield (state, launcher, root stat)."""
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
        "BLENDER_MCP_BOOTSTRAP_PYTHON": str(bootstrap or Path(sys.executable).resolve()),
        "BLENDER_MCP_CODEX_HOME": str(roots.codex_home),
    }
    launcher.write_bytes(_launcher_source(environment))
    launcher.chmod(0o700)
    info = runtime.stat()
    identifier = str(uuid4())
    post = {"dev": info.st_dev, "ino": info.st_ino if receipt_ino is None else receipt_ino}
    with state_root(roots) as state:
        ensure_usage_lock(state, usage_name(info.st_ino))
        (state.path / "receipts").mkdir()
        (state.path / "active.json").write_text(json.dumps({"install_id": identifier}))
        (state.path / "receipts" / f"{identifier}.json").write_text(
            json.dumps(
                {
                    "install_id": identifier,
                    "status": status,
                    "targets": [{"role": "runtime", "path": str(runtime), "install_post": post}],
                }
            )
        )
        yield state, launcher, info


@contextmanager
def _launched(launcher):
    process = subprocess.Popen(
        [str(launcher)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def _refused(launcher, reason: str) -> None:
    with _launched(launcher) as process:
        out, error = process.communicate(timeout=10)
        assert process.returncode == 75, error
        assert not out and "Traceback" not in error
        assert error == f"blender-mcp-managed: {reason}\n"


@pytest.mark.parametrize("status", ["prepared", "installed"])
def test_external_bootstrap_gates_runtime_before_exec(tmp_path, status):
    with _installed_runtime(tmp_path, status) as (state, launcher, info):
        if status == "prepared":
            _refused(launcher, "active installation is not installed")
            return
        with _launched(launcher) as process:
            assert process.stdout is not None
            assert process.stdout.readline().strip() == "payload-ready"
            with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
                assert not acquired


def test_launcher_survives_volume_renumbering_after_install(tmp_path):
    bootstrap = renumbering_python(tmp_path / "bootstrap", offset=7)
    with _installed_runtime(tmp_path, bootstrap=bootstrap) as (state, launcher, info):
        with _launched(launcher) as process:
            assert process.stdout is not None
            line = process.stdout.readline().strip()
            if line != "payload-ready":
                process.wait(timeout=5)
                pytest.fail(f"exit {process.returncode}: {process.stderr.read()}")
            with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
                assert not acquired


@pytest.mark.parametrize("missing", ["lease", "usage_directory"])
def test_launcher_without_lease_exits_cleanly(tmp_path, missing):
    bootstrap = renumbering_python(tmp_path / "bootstrap", offset=7)
    with _installed_runtime(tmp_path, bootstrap=bootstrap) as (state, launcher, info):
        lease = state.path / "usage" / usage_name(info.st_ino)
        lease.unlink()
        if missing == "usage_directory":
            lease.parent.rmdir()
        else:
            # A first-generation lease for the old device cannot admit a v2 runtime.
            ensure_usage_lock(state, device_usage_name(info.st_dev, info.st_ino))
        _refused(launcher, "usage lease or installer state unavailable (FileNotFoundError)")


def test_launcher_refuses_while_the_installer_retires_the_runtime(tmp_path):
    with _installed_runtime(tmp_path) as (state, launcher, info):
        with usage_lock(state, usage_name(info.st_ino), exclusive=True) as held:
            assert held
            _refused(launcher, "runtime is being retired")


def test_launcher_keeps_exit_75_when_stderr_is_closed(tmp_path):
    with _installed_runtime(tmp_path) as (state, launcher, info):
        (state.path / "usage" / usage_name(info.st_ino)).unlink()
        result = subprocess.run(
            ["/bin/sh", "-c", 'exec "$0" 2>&-', str(launcher)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 75 and not result.stdout


@pytest.mark.parametrize("drift", ["replaced_tree", "runtime_mount"])
def test_launcher_still_rejects_other_trees_after_renumbering(tmp_path, drift):
    directory = tmp_path / "bootstrap"
    if drift == "replaced_tree":
        bootstrap = renumbering_python(directory, offset=7)
        with _installed_runtime(tmp_path, bootstrap=bootstrap, receipt_ino=1) as (_s, launcher, _i):
            _refused(launcher, "active receipt does not match this runtime")
        return
    with _installed_runtime(tmp_path) as (_state, launcher, info):
        # Only the runtime root reports a new device: it is no longer on its parent's volume.
        wrapper = renumbering_python(directory, offset=7, only=info.st_ino)
        source = launcher.read_bytes().replace(
            str(Path(sys.executable).resolve()).encode(), str(wrapper).encode(), 1
        )
        launcher.write_bytes(source)
        _refused(launcher, "runtime root was replaced or is a mount point")


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
