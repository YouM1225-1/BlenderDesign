import fcntl
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_locks import (
    ensure_usage_lock,
    mutation_locks,
    script_usage,
    usage_lock,
    usage_name,
)
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root


def _roots(tmp_path: Path) -> UpgradeRoots:
    home = tmp_path / "home"
    codex = tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    return UpgradeRoots(home, codex)


def _filesystem_identity(roots: UpgradeRoots) -> dict[Path, tuple[int, int]]:
    result = {}
    for base in (roots.home, roots.codex_home):
        for path in base.rglob("*"):
            info = path.stat(follow_symlinks=False)
            result[path] = (info.st_dev, info.st_ino)
    return result


def test_usage_identity_survives_rename_and_exec(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    tree = roots.home / "old"
    tree.mkdir()
    info = tree.stat()
    with state_root(roots) as state:
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        lock = state.path / "usage" / usage_name(info.st_dev, info.st_ino)
        code = (
            "import fcntl,os,sys,time;"
            "fd=os.open(sys.argv[1],os.O_RDWR);"
            "fcntl.flock(fd,fcntl.LOCK_SH);"
            "os.set_inheritable(fd,True);"
            "os.execv(sys.executable,[sys.executable,'-c',"
            "\"import time;print('ready',flush=True);time.sleep(30)\"] )"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", code, str(lock)],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert process.stdout is not None
            assert process.stdout.readline().strip() == "ready"
            tree.rename(roots.home / "retired")
            with usage_lock(state, info.st_dev, info.st_ino, exclusive=True) as acquired:
                assert not acquired
        finally:
            process.terminate()
            process.wait(timeout=5)
        with usage_lock(state, info.st_dev, info.st_ino, exclusive=True) as acquired:
            assert acquired


def test_usage_lock_missing_legacy_lease_fails_closed(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    with state_root(roots) as state:
        with usage_lock(state, 1, 2, exclusive=True) as acquired:
            assert not acquired
        assert not (state.path / "usage").exists()


def test_usage_lock_busy_is_nonblocking_and_release_succeeds(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    tree = roots.home / "old"
    tree.mkdir()
    info = tree.stat()
    with state_root(roots) as state:
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        lock = state.path / "usage" / usage_name(info.st_dev, info.st_ino)
        fd = os.open(lock, os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            with usage_lock(state, info.st_dev, info.st_ino, exclusive=True) as acquired:
                assert not acquired
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        with usage_lock(state, info.st_dev, info.st_ino, exclusive=True) as acquired:
            assert acquired


def test_script_usage_fails_closed_without_creating_missing_state(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    version = roots.caches / "1.0.0"
    script = version / "scripts" / "entry.py"
    script.parent.mkdir(parents=True, mode=0o700)
    script.write_text("pass")
    assert not roots.state.exists()
    before = _filesystem_identity(roots)
    with pytest.raises((FileNotFoundError, InstallerError)):
        with script_usage(script, roots):
            pass
    after = _filesystem_identity(roots)
    assert after == before
    assert not roots.state.exists()


def test_script_usage_is_read_only_for_missing_lease(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    version = roots.caches / "1.0.0"
    script = version / "scripts" / "entry.py"
    script.parent.mkdir(parents=True, mode=0o700)
    script.write_text("pass")
    with state_root(roots):
        pass
    before = set(roots.home.rglob("*")) | set(roots.codex_home.rglob("*"))
    with pytest.raises((FileNotFoundError, ValueError, InstallerError)):
        with script_usage(script, roots):
            pass
    after = set(roots.home.rglob("*")) | set(roots.codex_home.rglob("*"))
    assert after == before
    assert not (roots.state / "usage").exists()


def test_mutation_locks_lock_marketplace_before_state(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    marketplace_lock = roots.codex_home / ".blender-mcp-marketplace.lock"
    fd = os.open(marketplace_lock, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    child = (
        "import sys;"
        "sys.path.insert(0,sys.argv[3]);"
        "from blender_mcp_installer.upgrade_locks import mutation_locks;"
        "from blender_mcp_installer.upgrade_state import UpgradeRoots;"
        "roots=UpgradeRoots(__import__('pathlib').Path(sys.argv[1]),"
        "__import__('pathlib').Path(sys.argv[2]));"
        "\ntry:\n with mutation_locks(roots): pass\n"
        "except BlockingIOError: pass\n"
        "else: raise SystemExit('marketplace lock was not busy')"
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                child,
                str(roots.home),
                str(roots.codex_home),
                str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, result.stderr
        assert not roots.state.exists()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    with mutation_locks(roots) as state:
        assert state.path == roots.state
        assert marketplace_lock.is_file()
        assert (roots.state / "installer.lock").is_file()
        assert stat.S_IMODE(marketplace_lock.stat().st_mode) == 0o600
