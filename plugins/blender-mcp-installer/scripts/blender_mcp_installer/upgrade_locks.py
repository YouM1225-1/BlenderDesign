from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Iterator

from blender_mcp_installer.filesystem import InstallerError, InstallerLock, SafeRoot
from blender_mcp_installer.upgrade_state import UpgradeRoots, absolute, state_root


def usage_name(device: int, inode: int) -> str:
    if type(device) is not int or device < 0 or type(inode) is not int or inode < 0:
        raise InstallerError("invalid usage identity")
    return hashlib.sha256(f"tree:{device}:{inode}".encode()).hexdigest() + ".lock"


def _lock_fd(parent: SafeRoot, name: str, *, create: bool) -> int:
    flags = os.O_RDWR | os.O_NOFOLLOW
    if create:
        try:
            fd = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent.fd)
            os.fchmod(fd, 0o600)
            os.fsync(fd)
            os.fsync(parent.fd)
        except FileExistsError:
            fd = os.open(name, flags, dir_fd=parent.fd)
    else:
        fd = os.open(name, flags, dir_fd=parent.fd)
    try:
        opened = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
        ):
            raise InstallerError("unsafe upgrade lock")
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def mutation_locks(roots: UpgradeRoots) -> Iterator[SafeRoot]:
    with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
        fd = _lock_fd(codex, ".blender-mcp-marketplace.lock", create=True)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with state_root(roots) as state:
                with InstallerLock.acquire(state):
                    yield state
        finally:
            os.close(fd)


def ensure_usage_lock(state: SafeRoot, device: int, inode: int) -> None:
    name = usage_name(device, inode)
    directory = state.open_directory(PurePath("usage"), create=True)
    with SafeRoot(state.path / "usage", os.getuid(), directory) as usage:
        fd = _lock_fd(usage, name, create=True)
        os.close(fd)


@contextmanager
def usage_lock(state: SafeRoot, device: int, inode: int, *, exclusive: bool) -> Iterator[bool]:
    name = usage_name(device, inode)
    try:
        directory = state.open_directory(PurePath("usage"))
    except FileNotFoundError:
        yield False
        return
    with SafeRoot(state.path / "usage", os.getuid(), directory) as usage:
        try:
            fd = _lock_fd(usage, name, create=False)
        except FileNotFoundError:
            yield False
            return
        try:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            try:
                fcntl.flock(fd, operation | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            os.close(fd)


@contextmanager
def script_usage(script: Path, roots: UpgradeRoots) -> Iterator[None]:
    script = absolute(str(script))
    if not script.is_relative_to(roots.caches):
        yield
        return
    parts = script.relative_to(roots.caches).parts
    if len(parts) < 2:
        raise InstallerError("invalid cached script path")
    version_root = roots.caches / parts[0]
    before = version_root.stat(follow_symlinks=False)
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        directory = home.open_directory(roots.state.relative_to(roots.home))
    with SafeRoot(roots.state, os.getuid(), directory) as state:
        with usage_lock(state, before.st_dev, before.st_ino, exclusive=False) as acquired:
            if not acquired:
                raise InstallerError("plugin version is being retired; retry from current version")
            with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
                parent_fd, name = codex.open_parent(script.relative_to(roots.codex_home))
                try:
                    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                        raise InstallerError("cached script disappeared or changed")
                finally:
                    os.close(parent_fd)
            after = version_root.stat(follow_symlinks=False)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise InstallerError("cached version changed while acquiring lease")
            yield
