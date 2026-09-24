from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePath
from typing import Iterator

from blender_mcp_installer.filesystem import InstallerError, InstallerLock, SafeRoot
from blender_mcp_installer.model import TreeImage
from blender_mcp_installer.upgrade_state import UpgradeRoots, absolute, state_root

USAGE_MARKER = ".blender-mcp-usage-v1"
_PROTOCOLS = {
    hashlib.sha256(b"inode-v1\n").hexdigest(): 1,
    hashlib.sha256(b"inode-v2\n").hexdigest(): 2,
}


def usage_protocol(image: TreeImage) -> int | None:
    """Which lease name the entries of a tree open: 1 device+inode, 2 inode only."""
    for item in image.entries:
        if item.path == USAGE_MARKER and item.kind == "file":
            return _PROTOCOLS.get(item.sha256)
    return None


def usage_name(inode: int) -> str:
    """Lease name of a v2 tree; stable across boots that renumber the volume device.

    An inode names one object per volume at a time, so the name can only be shared
    with a tree on another volume or with a deleted one. A shared lease file only
    adds holders: exclusive acquisition may then report busy, never idle.
    """
    if type(inode) is not int or inode < 0:
        raise InstallerError("invalid usage identity")
    return hashlib.sha256(f"tree-v2:{inode}".encode()).hexdigest() + ".lock"


def device_usage_name(device: int, inode: int) -> str:
    """Lease name a v1 entry derives from the device number of its current boot."""
    if type(device) is not int or device < 0 or type(inode) is not int or inode < 0:
        raise InstallerError("invalid usage identity")
    return hashlib.sha256(f"tree:{device}:{inode}".encode()).hexdigest() + ".lock"


def tree_usage_name(image: TreeImage) -> str:
    """The lease an installer creates for a live tree: the one its entries open.

    Lease-less trees keep the device name recorded with their image, which cleanup
    later derives from that record rather than from the live device.
    """
    if usage_protocol(image) == 2:
        return usage_name(image.ino)
    return device_usage_name(image.dev, image.ino)


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


def ensure_usage_lock(state: SafeRoot, name: str) -> None:
    directory = state.open_directory(PurePath("usage"), create=True)
    with SafeRoot(state.path / "usage", os.getuid(), directory) as usage:
        fd = _lock_fd(usage, name, create=True)
        os.close(fd)


@contextmanager
def usage_lock(
    state: SafeRoot, name: str, *, exclusive: bool, missing_idle: bool = False
) -> Iterator[bool]:
    # Entries never create lease files, so a caller may treat a missing one as unheld.
    try:
        directory = state.open_directory(PurePath("usage"))
    except FileNotFoundError:
        yield missing_idle
        return
    with SafeRoot(state.path / "usage", os.getuid(), directory) as usage:
        try:
            fd = _lock_fd(usage, name, create=False)
        except FileNotFoundError:
            yield missing_idle
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


def exclusive_usage(
    leases: ExitStack,
    state: SafeRoot,
    recorded: TreeImage,
    current_device: int,
) -> bool:
    """Hold every lease an entry of a recorded tree could hold, exclusively.

    Entries never create lease files and nothing unlinks them, so a missing file has
    no holder; requiring one still refuses a lease removed under a live holder. A v2
    lease must exist. A v1 lease named by the live device must exist until a remount
    renumbers it; afterwards v1 entries can only hold an already existing file named
    by the new device, and the recorded one names a device no longer mounted.
    """
    if usage_protocol(recorded) == 2:
        return leases.enter_context(
            usage_lock(state, usage_name(recorded.ino), exclusive=True)
        )
    remounted = current_device != recorded.dev
    return all(
        leases.enter_context(
            usage_lock(
                state,
                device_usage_name(device, recorded.ino),
                exclusive=True,
                missing_idle=remounted,
            )
        )
        for device in dict.fromkeys((recorded.dev, current_device))
    )


@contextmanager
def script_usage(script: Path, roots: UpgradeRoots) -> Iterator[None]:
    # Test-only installer mirror of the v2 entry prelude, which is the real entry guard;
    # a v1 cache has no inode lease and fails closed.
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
        with usage_lock(state, usage_name(before.st_ino), exclusive=False) as acquired:
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
