# ruff: noqa: E402 -- cache lease must precede installer imports
import atexit as _atexit
import fcntl as _fcntl
import hashlib as _hashlib
import os as _os
from pathlib import Path as _Path
import stat as _stat


def _entry_directory(path: _Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise SystemExit(75)
    fd = _os.open("/", _os.O_RDONLY | _os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = _os.open(part, _os.O_RDONLY | _os.O_DIRECTORY | _os.O_NOFOLLOW, dir_fd=fd)
            _os.close(fd)
            fd = child
        info = _os.fstat(fd)
        if info.st_uid != _os.getuid() or _stat.S_IMODE(info.st_mode) & 0o022:
            raise SystemExit(75)
        return fd
    except BaseException:
        _os.close(fd)
        raise


def _entry_lease() -> int | None:
    home = _Path(_os.environ.get("HOME", "/"))
    codex = _Path(_os.environ.get("CODEX_HOME", str(home / ".codex")))
    cache = codex / "plugins/cache/official-blender-mcp/blender-mcp-installer"
    script = _Path(__file__).absolute()
    if not script.is_relative_to(cache):
        return None
    relative = script.relative_to(cache)
    if len(relative.parts) < 2:
        raise SystemExit(75)
    version = cache / relative.parts[0]
    root_fd = _entry_directory(version)
    info = _os.fstat(root_fd)
    name = _hashlib.sha256(f"tree:{info.st_dev}:{info.st_ino}".encode()).hexdigest() + ".lock"
    usage_fd = _entry_directory(home / ".local/state/blender-mcp-installer/usage")
    lease_fd = _os.open(name, _os.O_RDWR | _os.O_NOFOLLOW, dir_fd=usage_fd)
    lease = _os.fstat(lease_fd)
    linked = _os.stat(name, dir_fd=usage_fd, follow_symlinks=False)
    if (
        not _stat.S_ISREG(lease.st_mode)
        or lease.st_uid != _os.getuid()
        or _stat.S_IMODE(lease.st_mode) != 0o600
        or lease.st_nlink != 1
        or (lease.st_dev, lease.st_ino) != (linked.st_dev, linked.st_ino)
    ):
        raise SystemExit(75)
    try:
        _fcntl.flock(lease_fd, _fcntl.LOCK_SH | _fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(75)
    check_fd = _entry_directory(version)
    after = _os.fstat(check_fd)
    if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino) or not script.is_file():
        raise SystemExit(75)
    for fd in (root_fd, usage_fd, check_fd):
        _os.close(fd)
    _atexit.register(_os.close, lease_fd)
    return lease_fd


_SCRIPT_USAGE_FD = _entry_lease()

from blender_mcp_installer.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
