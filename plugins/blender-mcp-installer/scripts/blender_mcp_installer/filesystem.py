from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import stat
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from typing import Iterator, Mapping
from uuid import UUID

from .model import (
    ActiveSelector,
    FileImage,
    ImageState,
    InstallRoots,
    PendingSelector,
    Receipt,
    TreeEntry,
    TreeImage,
    parse_receipt,
)


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW
RENAME_SWAP = 0x00000002
RENAME_EXCL = 0x00000004


def _relative_parts(value: PurePath) -> tuple[str, ...]:
    if value.is_absolute():
        raise ValueError("path must be relative to its safe root")
    parts = value.parts
    if any(part in {"", ".", "..", os.sep} for part in parts):
        raise ValueError("unsafe relative path")
    return parts


def _stable(left: os.stat_result, right: os.stat_result, *, directory: bool) -> bool:
    fields = ("st_dev", "st_ino", "st_uid", "st_mode", "st_mtime_ns")
    if not directory:
        fields += ("st_size",)
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _require_owner(info: os.stat_result, uid: int) -> None:
    if info.st_uid != uid:
        raise ValueError("foreign-owned path")


def _open_verified_directory(parent_fd: int, name: str, uid: int | None) -> int:
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError("path component is not a real directory")
    try:
        child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        raise ValueError("unsafe directory component") from exc
    after = os.fstat(child_fd)
    if not _stable(before, after, directory=True):
        os.close(child_fd)
        raise ValueError("directory component changed while opening")
    if uid is not None:
        try:
            _require_owner(after, uid)
        except ValueError:
            os.close(child_fd)
            raise
    return child_fd


def _mkdir_private(parent_fd: int, name: str) -> None:
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    os.chmod(name, 0o700, dir_fd=parent_fd, follow_symlinks=False)


@dataclass
class SafeRoot:
    path: Path
    owner_uid: int
    fd: int
    _closed: bool = False

    @classmethod
    def open(cls, path: Path, owner_uid: int, owned_from: Path) -> SafeRoot:
        if type(owner_uid) is not int or owner_uid != os.getuid():
            raise ValueError("safe-root owner must be the current UID")
        if not path.is_absolute() or not owned_from.is_absolute():
            raise ValueError("safe roots must be absolute")
        if ".." in path.parts or ".." in owned_from.parts or not path.is_relative_to(owned_from):
            raise ValueError("owned boundary must be a lexical ancestor")
        root_fd = os.open("/", _DIRECTORY_FLAGS)
        current_fd = root_fd
        current_path = Path("/")
        owned_open = owned_from == Path("/")
        try:
            if owned_open:
                _require_owner(os.fstat(current_fd), owner_uid)
            for part in path.parts[1:]:
                next_path = current_path / part
                check_owner = owned_open or next_path == owned_from
                try:
                    child_fd = _open_verified_directory(
                        current_fd, part, owner_uid if check_owner else None
                    )
                except FileNotFoundError:
                    if not owned_open:
                        raise ValueError("cannot create the owned boundary") from None
                    try:
                        _mkdir_private(current_fd, part)
                    except OSError as exc:
                        raise ValueError("cannot create safe path component") from exc
                    child_fd = _open_verified_directory(current_fd, part, owner_uid)
                    if stat.S_IMODE(os.fstat(child_fd).st_mode) != 0o700:
                        os.close(child_fd)
                        raise ValueError("created path component is not mode 0700")
                if current_fd != root_fd:
                    os.close(current_fd)
                current_fd = child_fd
                current_path = next_path
                if next_path == owned_from:
                    owned_open = True
            if not owned_open:
                raise ValueError("owned boundary was not traversed")
            if current_fd != root_fd:
                os.close(root_fd)
            return cls(path, owner_uid, current_fd)
        except OSError as exc:
            os.close(current_fd)
            if current_fd != root_fd:
                os.close(root_fd)
            raise ValueError("unsafe path traversal") from exc
        except BaseException:
            os.close(current_fd)
            if current_fd != root_fd:
                os.close(root_fd)
            raise

    def close(self) -> None:
        if not self._closed:
            os.close(self.fd)
            self._closed = True

    def __enter__(self) -> SafeRoot:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def open_directory(self, relative: PurePath, *, create: bool = False) -> int:
        parts = _relative_parts(relative)
        current_fd = os.dup(self.fd)
        try:
            for part in parts:
                try:
                    child_fd = _open_verified_directory(current_fd, part, self.owner_uid)
                except FileNotFoundError:
                    if not create:
                        raise
                    _mkdir_private(current_fd, part)
                    child_fd = _open_verified_directory(current_fd, part, self.owner_uid)
                    if stat.S_IMODE(os.fstat(child_fd).st_mode) != 0o700:
                        os.close(child_fd)
                        raise ValueError("created directory is not mode 0700")
                os.close(current_fd)
                current_fd = child_fd
            return current_fd
        except BaseException:
            os.close(current_fd)
            raise

    def open_parent(self, relative: PurePath) -> tuple[int, str]:
        parts = _relative_parts(relative)
        if not parts:
            raise ValueError("target must name a child of the safe root")
        parent_fd = self.open_directory(PurePosixPath(*parts[:-1]))
        return parent_fd, parts[-1]


@dataclass(frozen=True)
class TargetRef:
    root: SafeRoot
    relative: PurePath

    def __post_init__(self) -> None:
        if not _relative_parts(self.relative):
            raise ValueError("target must name a child")

    @property
    def path(self) -> Path:
        return self.root.path.joinpath(*self.relative.parts)


class InstallerLock:
    def __init__(self, fd: int):
        self.fd = fd

    @classmethod
    @contextmanager
    def acquire(cls, state_root: SafeRoot) -> Iterator[InstallerLock]:
        try:
            before = os.stat("installer.lock", dir_fd=state_root.fd, follow_symlinks=False)
        except FileNotFoundError:
            before = None
        if before is not None:
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("installer lock is not a regular file")
            _require_owner(before, state_root.owner_uid)
            if stat.S_IMODE(before.st_mode) != 0o600:
                raise ValueError("installer lock is not mode 0600")
        created = False
        if before is None:
            try:
                fd = os.open(
                    "installer.lock",
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=state_root.fd,
                )
                created = True
            except FileExistsError:
                before = os.stat("installer.lock", dir_fd=state_root.fd, follow_symlinks=False)
                fd = os.open("installer.lock", os.O_RDWR | os.O_NOFOLLOW, dir_fd=state_root.fd)
        else:
            fd = os.open("installer.lock", os.O_RDWR | os.O_NOFOLLOW, dir_fd=state_root.fd)
        locked = False
        try:
            if created:
                os.fchmod(fd, 0o600)
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError("installer lock is not a regular file")
            _require_owner(opened, state_root.owner_uid)
            if stat.S_IMODE(opened.st_mode) != 0o600:
                raise ValueError("installer lock is not mode 0600")
            if before is not None and not _stable(before, opened, directory=False):
                raise ValueError("installer lock changed while opening")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            yield cls(fd)
        finally:
            try:
                if locked:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


def _hash_fd(fd: int) -> str:
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while chunk := os.read(fd, 1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _file_image(info: os.stat_result, digest: str) -> FileImage:
    return FileImage(
        ImageState.PRESENT,
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
        info.st_size,
        info.st_mtime_ns,
        digest,
    )


def _capture_file_at(parent_fd: int, name: str, uid: int) -> FileImage:
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return FileImage.absent()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("target is not a regular file")
    _require_owner(before, uid)
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        raise ValueError("unsafe file target") from exc
    try:
        opened = os.fstat(fd)
        if not _stable(before, opened, directory=False):
            raise ValueError("file changed while opening")
        digest = _hash_fd(fd)
        after = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not _stable(opened, after, directory=False) or not _stable(
            after, linked, directory=False
        ):
            raise ValueError("file changed during capture")
        _require_owner(after, uid)
        return _file_image(after, digest)
    finally:
        os.close(fd)


def capture_file(root: SafeRoot, relative: PurePath) -> FileImage:
    try:
        parent_fd, name = root.open_parent(relative)
    except FileNotFoundError:
        return FileImage.absent()
    try:
        return _capture_file_at(parent_fd, name, root.owner_uid)
    finally:
        os.close(parent_fd)


def _listdir(fd: int) -> list[str]:
    return sorted(os.listdir(fd))


def _entry_path(prefix: str, name: str) -> str:
    return name if not prefix else f"{prefix}/{name}"


def _capture_directory(fd: int, prefix: str, uid: int) -> tuple[TreeEntry, ...]:
    before = os.fstat(fd)
    _require_owner(before, uid)
    names = _listdir(fd)
    entries: list[TreeEntry] = []
    for name in names:
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise ValueError("tree entry changed during capture") from exc
        _require_owner(info, uid)
        path = _entry_path(prefix, name)
        if stat.S_ISREG(info.st_mode):
            image = _capture_file_at(fd, name, uid)
            if image.state is not ImageState.PRESENT:
                raise ValueError("tree file disappeared")
            entries.append(
                TreeEntry(
                    path,
                    "file",
                    image.dev,
                    image.ino,
                    image.uid,
                    image.mode,
                    image.size,
                    image.mtime_ns,
                    image.sha256,
                )
            )
        elif stat.S_ISDIR(info.st_mode):
            child_fd = _open_verified_directory(fd, name, uid)
            try:
                nested = _capture_directory(child_fd, path, uid)
                after = os.fstat(child_fd)
            finally:
                os.close(child_fd)
            linked = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not _stable(info, after, directory=True) or not _stable(
                after, linked, directory=True
            ):
                raise ValueError("tree directory changed during capture")
            entries.append(
                TreeEntry(
                    path,
                    "dir",
                    after.st_dev,
                    after.st_ino,
                    after.st_uid,
                    stat.S_IMODE(after.st_mode),
                    after.st_size,
                    after.st_mtime_ns,
                    None,
                )
            )
            entries.extend(nested)
        else:
            raise ValueError("tree contains a symlink or special entry")
    after = os.fstat(fd)
    if not _stable(before, after, directory=True) or names != _listdir(fd):
        raise ValueError("tree directory changed during capture")
    return tuple(sorted(entries, key=lambda entry: entry.path))


def capture_tree(root: SafeRoot, relative: PurePath) -> TreeImage:
    try:
        parent_fd, name = root.open_parent(relative)
    except FileNotFoundError:
        return TreeImage.absent()
    try:
        try:
            before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return TreeImage.absent()
        if not stat.S_ISDIR(before.st_mode):
            raise ValueError("tree target is not a real directory")
        _require_owner(before, root.owner_uid)
        tree_fd = _open_verified_directory(parent_fd, name, root.owner_uid)
        try:
            entries = _capture_directory(tree_fd, "", root.owner_uid)
            after = os.fstat(tree_fd)
        finally:
            os.close(tree_fd)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not _stable(before, after, directory=True) or not _stable(after, linked, directory=True):
            raise ValueError("tree root changed during capture")
        encoded = json.dumps(
            [entry.to_dict() for entry in entries], sort_keys=True, separators=(",", ":")
        ).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        return TreeImage(
            ImageState.PRESENT,
            after.st_dev,
            after.st_ino,
            after.st_uid,
            stat.S_IMODE(after.st_mode),
            after.st_mtime_ns,
            digest,
            entries,
        )
    finally:
        os.close(parent_fd)


def _rename_atomic(
    source_fd: int,
    source: str,
    target_fd: int,
    target: str,
    *,
    swap: bool,
) -> None:
    if sys.platform != "darwin":
        raise OSError(errno.ENOTSUP, "native rename requires Darwin renameatx_np")
    libc = ctypes.CDLL(None, use_errno=True)
    renameatx_np = libc.renameatx_np
    renameatx_np.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameatx_np.restype = ctypes.c_int
    flags = RENAME_SWAP if swap else RENAME_EXCL
    if renameatx_np(source_fd, os.fsencode(source), target_fd, os.fsencode(target), flags) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), target)


def _write_all(fd: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        offset += os.write(fd, raw[offset:])


def _matches_json_payload(image: FileImage, raw: bytes, uid: int) -> bool:
    return (
        image.state is ImageState.PRESENT
        and image.uid == uid
        and image.mode == 0o600
        and image.size == len(raw)
        and image.sha256 == hashlib.sha256(raw).hexdigest()
    )


def _unlink_stable_file(parent_fd: int, name: str, expected: FileImage, uid: int) -> None:
    if _capture_file_at(parent_fd, name, uid) != expected:
        raise ValueError("installer JSON temp changed before cleanup")
    os.unlink(name, dir_fd=parent_fd)
    os.fsync(parent_fd)


def _finish_old_json(
    parent_fd: int,
    temp_name: str,
    expected: FileImage,
    root: SafeRoot,
    retain_old: TargetRef | None,
) -> None:
    if _capture_file_at(parent_fd, temp_name, root.owner_uid) != expected:
        raise ValueError("JSON preimage changed before cleanup")
    if retain_old is None:
        _unlink_stable_file(parent_fd, temp_name, expected, root.owner_uid)
        return
    retain_fd, retain_name = retain_old.root.open_parent(retain_old.relative)
    try:
        if capture_file(retain_old.root, retain_old.relative).state is not ImageState.ABSENT:
            raise ValueError("JSON retention target already exists")
        _rename_atomic(parent_fd, temp_name, retain_fd, retain_name, swap=False)
        os.fsync(retain_fd)
        os.fsync(parent_fd)
    finally:
        os.close(retain_fd)


def write_atomic_json(
    path: TargetRef,
    expected: FileImage,
    payload: Mapping[str, object],
    install_id: UUID,
    retain_old: TargetRef | None = None,
) -> FileImage:
    if install_id.version != 4:
        raise ValueError("install ID must be UUIDv4")
    if expected.state is ImageState.PRESENT and expected.mode != 0o600:
        raise ValueError("existing JSON is not mode 0600")
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    )
    parent_fd, target_name = path.root.open_parent(path.relative)
    temp_name = f".blender-mcp-installer.{install_id}.{target_name}.tmp"
    try:
        current = capture_file(path.root, path.relative)
        stale = _capture_file_at(parent_fd, temp_name, path.root.owner_uid)
        if current != expected:
            if (
                stale == expected
                and _matches_json_payload(current, raw, path.root.owner_uid)
                and capture_file(path.root, path.relative) == current
            ):
                _finish_old_json(parent_fd, temp_name, stale, path.root, retain_old)
                if capture_file(path.root, path.relative) != current:
                    raise ValueError("JSON target changed during retry cleanup")
                return current
            raise ValueError("JSON target changed before write")
        if stale.state is ImageState.PRESENT:
            if _matches_json_payload(stale, raw, path.root.owner_uid):
                _unlink_stable_file(parent_fd, temp_name, stale, path.root.owner_uid)
            else:
                raise FileExistsError(errno.EEXIST, "unrecognized JSON temp", temp_name)
        temp_fd = os.open(
            temp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            os.fchmod(temp_fd, 0o600)
            _write_all(temp_fd, raw)
            if stat.S_IMODE(os.fstat(temp_fd).st_mode) != 0o600:
                raise ValueError("JSON temp is not mode 0600")
            os.fsync(temp_fd)
        finally:
            os.close(temp_fd)
        new_image = _capture_file_at(parent_fd, temp_name, path.root.owner_uid)
        if not _matches_json_payload(new_image, raw, path.root.owner_uid):
            raise ValueError("JSON temp does not match the complete payload")
        if capture_file(path.root, path.relative) != expected:
            raise ValueError("JSON target changed before publication")
        _rename_atomic(
            parent_fd,
            temp_name,
            parent_fd,
            target_name,
            swap=expected.state is ImageState.PRESENT,
        )
        os.fsync(parent_fd)
        if expected.state is ImageState.PRESENT:
            old = _capture_file_at(parent_fd, temp_name, path.root.owner_uid)
            if old != expected:
                live = capture_file(path.root, path.relative)
                parked = _capture_file_at(parent_fd, temp_name, path.root.owner_uid)
                if live == new_image and parked == old:
                    _rename_atomic(
                        parent_fd,
                        target_name,
                        parent_fd,
                        temp_name,
                        swap=True,
                    )
                    os.fsync(parent_fd)
                    restored = capture_file(path.root, path.relative)
                    displaced = _capture_file_at(parent_fd, temp_name, path.root.owner_uid)
                    if restored == old and displaced == new_image:
                        _unlink_stable_file(parent_fd, temp_name, new_image, path.root.owner_uid)
                raise ValueError("concurrent JSON change detected")
            _finish_old_json(parent_fd, temp_name, old, path.root, retain_old)
        result = capture_file(path.root, path.relative)
        if result.state is not ImageState.PRESENT or result.mode != 0o600:
            raise ValueError("published JSON is not a private regular file")
        return result
    finally:
        os.close(parent_fd)


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_private_json(root: SafeRoot, relative: PurePath) -> object | None:
    image = capture_file(root, relative)
    if image.state is ImageState.ABSENT:
        return None
    if image.mode != 0o600:
        raise ValueError("state JSON is not mode 0600")
    parent_fd, name = root.open_parent(relative)
    try:
        fd = os.open(name, _FILE_FLAGS, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            if _file_image(opened, _hash_fd(fd)) != image:
                raise ValueError("state JSON changed while reading")
            os.lseek(fd, 0, os.SEEK_SET)
            raw = b""
            while chunk := os.read(fd, 1024 * 1024):
                raw += chunk
                if len(raw) > 16 * 1024 * 1024:
                    raise ValueError("state JSON is too large")
            after = os.fstat(fd)
            linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not _stable(opened, after, directory=False) or not _stable(
                after, linked, directory=False
            ):
                raise ValueError("state JSON changed while reading")
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid state JSON") from exc


def _state_root(roots: InstallRoots) -> SafeRoot:
    return SafeRoot.open(roots.state_root, os.getuid(), roots.state_root)


def load_receipt(path: Path, roots: InstallRoots) -> Receipt:
    if path.parent != roots.receipts:
        raise ValueError("receipt is outside the receipts root")
    try:
        install_id = UUID(path.stem)
    except ValueError as exc:
        raise ValueError("invalid receipt basename") from exc
    if install_id.version != 4 or str(install_id) != path.stem or path != roots.receipt(install_id):
        raise ValueError("receipt path is not canonically derived")
    with _state_root(roots) as root:
        value = _read_private_json(root, PurePosixPath("receipts", path.name))
    if value is None:
        raise ValueError("receipt does not exist")
    receipt = parse_receipt(value, roots)
    if receipt.install_id != install_id:
        raise ValueError("receipt ID does not match its path")
    return receipt


def load_pending(path: Path, roots: InstallRoots) -> PendingSelector | None:
    if path != roots.pending:
        raise ValueError("pending selector path is not derived")
    with _state_root(roots) as root:
        value = _read_private_json(root, PurePosixPath("pending.json"))
    return None if value is None else PendingSelector.from_dict(value)


def load_active(path: Path, roots: InstallRoots) -> ActiveSelector | None:
    if path != roots.active:
        raise ValueError("active selector path is not derived")
    with _state_root(roots) as root:
        value = _read_private_json(root, PurePosixPath("active.json"))
    return None if value is None else ActiveSelector.from_dict(value)
