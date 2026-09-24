import dataclasses
import fcntl
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError
from contextlib import ExitStack

from blender_mcp_installer.filesystem import SafeRoot, capture_tree
from blender_mcp_installer.upgrade_locks import (
    device_usage_name,
    ensure_usage_lock,
    exclusive_usage,
    mutation_locks,
    script_usage,
    tree_usage_name,
    usage_lock,
    usage_name,
    usage_protocol,
)
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root
from tests.distribution.remount import renumbered_in_process


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
        ensure_usage_lock(state, usage_name(info.st_ino))
        lock = state.path / "usage" / usage_name(info.st_ino)
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
            with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
                assert not acquired
        finally:
            process.terminate()
            process.wait(timeout=5)
        with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
            assert acquired


def test_usage_lock_missing_legacy_lease_fails_closed(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    with state_root(roots) as state:
        with usage_lock(state, usage_name(2), exclusive=True) as acquired:
            assert not acquired
        assert not (state.path / "usage").exists()


def test_usage_lock_busy_is_nonblocking_and_release_succeeds(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    tree = roots.home / "old"
    tree.mkdir()
    info = tree.stat()
    with state_root(roots) as state:
        ensure_usage_lock(state, usage_name(info.st_ino))
        lock = state.path / "usage" / usage_name(info.st_ino)
        fd = os.open(lock, os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
                assert not acquired
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
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


def test_script_usage_survives_volume_renumbering(tmp_path: Path, monkeypatch) -> None:
    roots = _roots(tmp_path)
    version = roots.caches / "1.0.0"
    script = version / "scripts" / "entry.py"
    script.parent.mkdir(parents=True, mode=0o700)
    script.write_text("pass")
    info = version.stat()
    with state_root(roots) as state:
        ensure_usage_lock(state, usage_name(info.st_ino))
    with renumbered_in_process(monkeypatch, offset=7):
        with script_usage(script, roots):
            with state_root(roots) as state:
                with usage_lock(state, usage_name(info.st_ino), exclusive=True) as acquired:
                    assert not acquired


def _tree(roots: UpgradeRoots, name: str, marker: bytes | None):
    tree = roots.home / name
    tree.mkdir()
    if marker is not None:
        (tree / ".blender-mcp-usage-v1").write_bytes(marker)
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        return capture_tree(home, Path(name))


def _held(state, name: str):
    path = state.path / "usage" / name
    fd = os.open(path, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_SH)
    return fd


def _idle(state, recorded, device: int) -> bool:
    with ExitStack() as leases:
        return exclusive_usage(leases, state, recorded, device)


def test_usage_protocol_and_installer_lease_name(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    v1 = _tree(roots, "v1", b"inode-v1\n")
    v2 = _tree(roots, "v2", b"inode-v2\n")
    legacy = _tree(roots, "legacy", None)
    unknown = _tree(roots, "unknown", b"inode-v3\n")
    assert [usage_protocol(image) for image in (v1, v2, legacy, unknown)] == [1, 2, None, None]
    assert tree_usage_name(v2) == usage_name(v2.ino)
    assert tree_usage_name(v1) == device_usage_name(v1.dev, v1.ino)
    assert tree_usage_name(legacy) == device_usage_name(legacy.dev, legacy.ino)
    assert usage_name(v2.ino) != device_usage_name(v2.dev, v2.ino)


def test_v2_lease_ignores_device_but_missing_stays_fail_closed(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    image = _tree(roots, "v2", b"inode-v2\n")
    with state_root(roots) as state:
        assert not _idle(state, image, image.dev + 7)
        ensure_usage_lock(state, usage_name(image.ino))
        assert _idle(state, image, image.dev + 7)
        fd = _held(state, usage_name(image.ino))
        try:
            assert not _idle(state, image, image.dev)
            assert not _idle(state, image, image.dev + 7)
        finally:
            os.close(fd)


def test_cross_volume_inode_collision_is_busy_never_idle(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    image = _tree(roots, "v2", b"inode-v2\n")
    # Another volume may hold a different tree with the same inode number.
    other = dataclasses.replace(image, dev=image.dev + 1)
    with state_root(roots) as state:
        ensure_usage_lock(state, tree_usage_name(other))
        assert tree_usage_name(other) == tree_usage_name(image)
        fd = _held(state, tree_usage_name(other))
        try:
            assert not _idle(state, image, image.dev)
        finally:
            os.close(fd)
        assert _idle(state, image, image.dev)


def test_v1_lease_requires_live_device_file_until_remount(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    image = _tree(roots, "v1", b"inode-v1\n")
    recorded = device_usage_name(image.dev, image.ino)
    current = device_usage_name(image.dev + 7, image.ino)
    with state_root(roots) as state:
        # Same device: the installer-created lease must exist.
        assert not _idle(state, image, image.dev)
        # A remount leaves no v1 entry able to hold a missing file.
        assert _idle(state, image, image.dev + 7)
        for name in (recorded, current):
            ensure_usage_lock(state, name)
            fd = _held(state, name)
            try:
                assert not _idle(state, image, image.dev + 7)
            finally:
                os.close(fd)
        assert _idle(state, image, image.dev)
        assert _idle(state, image, image.dev + 7)
        assert not (state.path / "usage" / usage_name(image.ino)).exists()


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
