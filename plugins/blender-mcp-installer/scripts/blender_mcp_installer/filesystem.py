from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import stat
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePath, PurePosixPath
from typing import Iterator, Mapping, Protocol, TypeAlias
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


class FaultInjector(Protocol):
    def hit(self, point: str) -> None: ...


class NoOpFaultInjector:
    def hit(self, point: str) -> None:
        pass


class InstallerError(RuntimeError):
    pass


class NativeState(str, Enum):
    SWAPPED = "swapped"
    PARKED = "parked"
    PUBLISHED = "published"
    COMPLETED = "completed"


class RestoreState(str, Enum):
    RESTORING = "restoring"
    RESTORED = "restored"


@dataclass(frozen=True)
class TreeRef(TargetRef):
    def capture(self) -> TreeImage:
        return capture_tree(self.root, self.relative)


@dataclass(frozen=True)
class StagedFile(TargetRef):
    image: FileImage

    def capture(self) -> FileImage:
        return capture_file(self.root, self.relative)

    def refresh(self) -> StagedFile:
        return StagedFile(self.root, self.relative, self.capture())

    def with_image(self, image: FileImage) -> StagedFile:
        return StagedFile(self.root, self.relative, image)


@dataclass(frozen=True)
class StagedTree(TreeRef):
    image: TreeImage

    def refresh(self) -> StagedTree:
        return StagedTree(self.root, self.relative, self.capture())

    def with_image(self, image: TreeImage) -> StagedTree:
        return StagedTree(self.root, self.relative, image)


StagedObject: TypeAlias = StagedFile | StagedTree


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


_RENAME_ERRORS = {
    errno.EEXIST: "rename destination already exists",
    errno.ENOTSUP: "native rename is not supported",
    errno.EXDEV: "cross-device rename is not supported",
}


def _basename(value: str) -> str:
    if (
        type(value) is not str
        or not value
        or PurePath(value).name != value
        or "\\" in value
        or "\0" in value
        or value in {".", ".."}
    ):
        raise ValueError("invalid deterministic basename")
    return value


def _validate_parent(parent: SafeRoot) -> None:
    if parent._closed:
        raise ValueError("safe root is closed")
    info = os.fstat(parent.fd)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("safe root is not a directory")
    _require_owner(info, parent.owner_uid)


def _native_rename(
    source_parent: SafeRoot,
    source: str,
    target_parent: SafeRoot,
    target: str,
    fault: FaultInjector,
    *,
    swap: bool,
) -> None:
    _validate_parent(source_parent)
    _validate_parent(target_parent)
    source = _basename(source)
    target = _basename(target)
    try:
        _rename_atomic(
            source_parent.fd,
            source,
            target_parent.fd,
            target,
            swap=swap,
        )
    except OSError as exc:
        message = _RENAME_ERRORS.get(exc.errno)
        if message is not None:
            raise InstallerError(message) from exc
        raise InstallerError("native rename failed") from exc
    fault.hit("after_native_rename")
    os.fsync(source_parent.fd)
    fault.hit("after_source_parent_fsync")
    if target_parent.fd != source_parent.fd:
        os.fsync(target_parent.fd)
    fault.hit("after_destination_parent_fsync")


def rename_excl(
    src_parent: SafeRoot,
    src_name: str,
    dst_parent: SafeRoot,
    dst_name: str,
    fault: FaultInjector,
) -> None:
    _native_rename(src_parent, src_name, dst_parent, dst_name, fault, swap=False)


def rename_swap(
    left_parent: SafeRoot,
    left_name: str,
    right_parent: SafeRoot,
    right_name: str,
    fault: FaultInjector,
) -> None:
    _native_rename(left_parent, left_name, right_parent, right_name, fault, swap=True)


def create_deterministic_stage(
    parent: SafeRoot,
    basename: str,
    expected_absent: FileImage | TreeImage,
    fault: FaultInjector,
) -> StagedObject:
    _validate_parent(parent)
    basename = _basename(basename)
    if expected_absent.state is not ImageState.ABSENT:
        raise ValueError("deterministic stage requires an absent image")
    try:
        if isinstance(expected_absent, FileImage):
            fd = os.open(
                basename,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent.fd,
            )
            try:
                os.fchmod(fd, 0o600)
                os.fsync(fd)
                created_file = _file_image(os.fstat(fd), _hash_fd(fd))
            finally:
                os.close(fd)
            try:
                captured_file = _capture_file_at(parent.fd, basename, parent.owner_uid)
            except (OSError, ValueError) as exc:
                raise InstallerError("transaction state conflict") from exc
            if captured_file != created_file:
                raise InstallerError("transaction state conflict")
            stage: StagedObject = StagedFile(
                parent,
                PurePosixPath(basename),
                created_file,
            )
        elif isinstance(expected_absent, TreeImage):
            os.mkdir(basename, mode=0o700, dir_fd=parent.fd)
            os.chmod(basename, 0o700, dir_fd=parent.fd, follow_symlinks=False)
            directory = _open_verified_directory(parent.fd, basename, parent.owner_uid)
            try:
                os.fsync(directory)
                info = os.fstat(directory)
                created_tree = TreeImage(
                    ImageState.PRESENT,
                    info.st_dev,
                    info.st_ino,
                    info.st_uid,
                    stat.S_IMODE(info.st_mode),
                    info.st_mtime_ns,
                    hashlib.sha256(b"[]").hexdigest(),
                    (),
                )
            finally:
                os.close(directory)
            try:
                captured_tree = capture_tree(parent, PurePosixPath(basename))
            except (OSError, ValueError) as exc:
                raise InstallerError("transaction state conflict") from exc
            if captured_tree != created_tree:
                raise InstallerError("transaction state conflict")
            stage = StagedTree(
                parent,
                PurePosixPath(basename),
                created_tree,
            )
        else:
            raise TypeError("unsupported stage image")
    except FileExistsError as exc:
        raise InstallerError("deterministic stage already exists") from exc
    fault.hit("after_stage_create")
    os.fsync(parent.fd)
    fault.hit("after_stage_parent_fsync")
    return stage


class _PartialCopyError(Exception):
    def __init__(self, cause: BaseException, image: FileImage):
        self.cause = cause
        self.image = image


def _copy_file(source_fd: int, name: str, target_fd: int, uid: int) -> FileImage:
    before = _capture_file_at(source_fd, name, uid)
    if before.state is not ImageState.PRESENT:
        raise ValueError("source file disappeared")
    source = os.open(name, _FILE_FLAGS, dir_fd=source_fd)
    try:
        target = os.open(
            name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=target_fd,
        )
    except BaseException:
        os.close(source)
        raise
    failure: BaseException | None = None
    partial: FileImage | None = None
    created: FileImage | None = None
    try:
        opened = os.fstat(source)
        if _file_image(opened, _hash_fd(source)) != before:
            raise ValueError("source file changed before copy")
        os.lseek(source, 0, os.SEEK_SET)
        while chunk := os.read(source, 1024 * 1024):
            _write_all(target, chunk)
        os.fchmod(target, before.mode)
        os.fsync(target)
        created = _file_image(os.fstat(target), _hash_fd(target))
    except BaseException as exc:
        failure = exc
        try:
            partial = _file_image(os.fstat(target), _hash_fd(target))
        except BaseException:
            partial = None
    finally:
        os.close(target)
        os.close(source)
    if failure is not None:
        if partial is not None and _capture_file_at(target_fd, name, uid) == partial:
            raise _PartialCopyError(failure, partial) from failure
        raise failure
    assert created is not None
    if _capture_file_at(target_fd, name, uid) != created:
        cause = InstallerError("transaction state conflict")
        raise _PartialCopyError(cause, created) from cause
    if _capture_file_at(source_fd, name, uid) != before:
        cause = ValueError("source file changed during copy")
        raise _PartialCopyError(cause, created) from cause
    return created


@dataclass(frozen=True)
class _CreatedEntry:
    kind: str
    dev: int
    ino: int
    uid: int
    mode: int
    file: FileImage | None = None


def _created_entry(info: os.stat_result, kind: str, file: FileImage | None = None) -> _CreatedEntry:
    return _CreatedEntry(
        kind,
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
        file,
    )


def _copy_directory(
    source_fd: int,
    target_fd: int,
    uid: int,
    created: dict[str, _CreatedEntry] | None = None,
    prefix: str = "",
) -> None:
    if created is None:
        created = {}
    before = os.fstat(source_fd)
    names = _listdir(source_fd)
    if _listdir(target_fd):
        raise InstallerError("transaction state conflict")
    for name in names:
        info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        _require_owner(info, uid)
        path = _entry_path(prefix, name)
        if stat.S_ISREG(info.st_mode):
            try:
                image = _copy_file(source_fd, name, target_fd, uid)
            except _PartialCopyError as exc:
                image = exc.image
                created[path] = _CreatedEntry(
                    "file", image.dev, image.ino, image.uid, image.mode, image
                )
                raise exc.cause from exc
            created[path] = _CreatedEntry(
                "file", image.dev, image.ino, image.uid, image.mode, image
            )
            if _capture_file_at(target_fd, name, uid) != image:
                raise InstallerError("transaction state conflict")
        elif stat.S_ISDIR(info.st_mode):
            source_child = _open_verified_directory(source_fd, name, uid)
            try:
                os.mkdir(name, mode=0o700, dir_fd=target_fd)
                target_child = _open_verified_directory(target_fd, name, uid)
                try:
                    created[path] = _created_entry(os.fstat(target_child), "dir")
                    _copy_directory(source_child, target_child, uid, created, path)
                    os.fchmod(target_child, stat.S_IMODE(info.st_mode))
                    created[path] = _created_entry(os.fstat(target_child), "dir")
                    os.fsync(target_child)
                finally:
                    os.close(target_child)
            finally:
                os.close(source_child)
        else:
            raise ValueError("tree contains a symlink or special entry")
    after = os.fstat(source_fd)
    if not _stable(before, after, directory=True) or names != _listdir(source_fd):
        raise ValueError("source tree changed during copy")
    if names != _listdir(target_fd):
        raise InstallerError("transaction state conflict")
    os.fsync(target_fd)


def _created_matches(entry: TreeEntry, created: _CreatedEntry) -> bool:
    if (
        entry.kind != created.kind
        or entry.dev != created.dev
        or entry.ino != created.ino
        or entry.uid != created.uid
        or entry.mode != created.mode
    ):
        return False
    return created.file is None or (
        entry.size == created.file.size
        and entry.mtime_ns == created.file.mtime_ns
        and entry.sha256 == created.file.sha256
    )


def _validate_created_tree(
    stage: StagedTree,
    created: Mapping[str, _CreatedEntry],
) -> TreeImage:
    current = stage.capture()
    initial = stage.image
    if (
        current.state is not ImageState.PRESENT
        or current.dev != initial.dev
        or current.ino != initial.ino
        or current.uid != initial.uid
        or current.mode != initial.mode
        or set(created) != {entry.path for entry in current.entries}
    ):
        raise InstallerError("transaction state conflict")
    if any(not _created_matches(entry, created[entry.path]) for entry in current.entries):
        raise InstallerError("transaction state conflict")
    return current


def _remove_created_stage(stage: StagedTree, created: Mapping[str, _CreatedEntry]) -> None:
    current = _validate_created_tree(stage, created)
    _remove_tree_prefix(stage, current, NoOpFaultInjector())


def copy_tree(source: TreeRef, stage: StagedTree) -> TreeImage:
    source_before = source.capture()
    if source_before.state is not ImageState.PRESENT:
        raise ValueError("source tree is absent")
    stage_before = stage.capture()
    if stage_before != stage.image or stage_before.entries:
        raise InstallerError("transaction state conflict")
    source_parent_fd, source_name = source.root.open_parent(source.relative)
    stage_parent_fd, stage_name = stage.root.open_parent(stage.relative)
    created: dict[str, _CreatedEntry] = {}
    try:
        source_fd = _open_verified_directory(source_parent_fd, source_name, source.root.owner_uid)
        try:
            stage_fd = _open_verified_directory(stage_parent_fd, stage_name, stage.root.owner_uid)
            try:
                _copy_directory(source_fd, stage_fd, source.root.owner_uid, created)
            finally:
                os.close(stage_fd)
        finally:
            os.close(source_fd)
        os.fsync(stage_parent_fd)
    except BaseException as exc:
        try:
            _remove_created_stage(stage, created)
        except InstallerError as cleanup_error:
            raise cleanup_error from exc
        raise
    finally:
        os.close(stage_parent_fd)
        os.close(source_parent_fd)
    try:
        if source.capture() != source_before:
            raise ValueError("source tree changed during copy")
        return _validate_created_tree(stage, created)
    except BaseException as exc:
        try:
            _remove_created_stage(stage, created)
        except InstallerError as cleanup_error:
            raise cleanup_error from exc
        raise


@contextmanager
def _parent_root(reference: TargetRef) -> Iterator[tuple[SafeRoot, str]]:
    fd, name = reference.root.open_parent(reference.relative)
    parent = SafeRoot(reference.path.parent, reference.root.owner_uid, fd)
    try:
        yield parent, name
    finally:
        parent.close()


def _capture_reference(reference: TargetRef, *, tree: bool) -> FileImage | TreeImage:
    try:
        if tree:
            return capture_tree(reference.root, reference.relative)
        return capture_file(reference.root, reference.relative)
    except (OSError, ValueError) as exc:
        raise InstallerError("transaction state conflict") from exc


def _images(
    target: TargetRef,
    stage: StagedObject,
    recovery: TargetRef,
    *,
    tree: bool,
) -> tuple[FileImage | TreeImage, FileImage | TreeImage, FileImage | TreeImage]:
    return (
        _capture_reference(target, tree=tree),
        _capture_reference(stage, tree=tree),
        _capture_reference(recovery, tree=tree),
    )


def _rename_refs(
    source: TargetRef,
    target: TargetRef,
    fault: FaultInjector,
    *,
    swap: bool,
) -> None:
    with _parent_root(source) as (source_parent, source_name):
        with _parent_root(target) as (target_parent, target_name):
            if swap:
                rename_swap(source_parent, source_name, target_parent, target_name, fault)
            else:
                rename_excl(source_parent, source_name, target_parent, target_name, fault)


def _entry_matches(info: os.stat_result, entry: TreeEntry) -> bool:
    return (
        info.st_dev == entry.dev
        and info.st_ino == entry.ino
        and info.st_uid == entry.uid
        and stat.S_IMODE(info.st_mode) == entry.mode
        and info.st_size == entry.size
        and info.st_mtime_ns == entry.mtime_ns
    )


def _tree_cleanup_order(image: TreeImage) -> tuple[str, ...]:
    entries = {entry.path: entry for entry in image.entries}
    result: list[str] = []

    def visit(prefix: str) -> None:
        depth = 0 if not prefix else len(PurePosixPath(prefix).parts)
        children = sorted(
            path
            for path in entries
            if len(PurePosixPath(path).parts) == depth + 1
            and (not prefix or path.startswith(f"{prefix}/"))
        )
        for path in children:
            if entries[path].kind == "dir":
                visit(path)
            result.append(path)

    visit("")
    return tuple(result)


def _tree_prefix(current: TreeImage, expected: TreeImage) -> tuple[str, ...] | None:
    if (
        current.state is not ImageState.PRESENT
        or current.dev != expected.dev
        or current.ino != expected.ino
        or current.uid != expected.uid
        or current.mode != expected.mode
    ):
        return None
    expected_entries = {entry.path: entry for entry in expected.entries}
    for entry in current.entries:
        original = expected_entries.get(entry.path)
        if original is None or (
            entry.kind != original.kind
            or entry.dev != original.dev
            or entry.ino != original.ino
            or entry.uid != original.uid
            or entry.mode != original.mode
            or (
                entry.kind == "file"
                and (
                    entry.size != original.size
                    or entry.mtime_ns != original.mtime_ns
                    or entry.sha256 != original.sha256
                )
            )
        ):
            return None
    order = _tree_cleanup_order(expected)
    paths = {entry.path for entry in current.entries}
    return next(
        (order[index:] for index in range(len(order) + 1) if paths == set(order[index:])), None
    )


def _remove_tree_prefix(
    reference: TargetRef,
    expected: TreeImage,
    fault: FaultInjector,
) -> None:
    if _tree_prefix(_capture_reference(reference, tree=True), expected) is None:
        raise InstallerError("transaction state conflict")
    fault.hit("before_cleanup_delete")
    while True:
        current = _capture_reference(reference, tree=True)
        remaining = _tree_prefix(current, expected)
        if remaining is None:
            raise InstallerError("transaction state conflict")
        if not remaining:
            break
        path = remaining[0]
        entry = next(item for item in current.entries if item.path == path)
        relative = PurePosixPath(*reference.relative.parts, *PurePosixPath(path).parts)
        parent_fd, name = reference.root.open_parent(relative)
        try:
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            original = next(item for item in expected.entries if item.path == path)
            if entry.kind == "file":
                if not _entry_matches(info, original):
                    raise InstallerError("transaction state conflict")
                os.unlink(name, dir_fd=parent_fd)
            else:
                if (
                    not stat.S_ISDIR(info.st_mode)
                    or info.st_dev != original.dev
                    or info.st_ino != original.ino
                    or info.st_uid != original.uid
                    or stat.S_IMODE(info.st_mode) != original.mode
                ):
                    raise InstallerError("transaction state conflict")
                os.rmdir(name, dir_fd=parent_fd)
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        fault.hit("after_cleanup_entry")
    with _parent_root(reference) as (parent, name):
        directory = _open_verified_directory(parent.fd, name, parent.owner_uid)
        try:
            root = os.fstat(directory)
            if (
                root.st_dev != expected.dev
                or root.st_ino != expected.ino
                or root.st_uid != expected.uid
                or stat.S_IMODE(root.st_mode) != expected.mode
                or _listdir(directory)
            ):
                raise InstallerError("transaction state conflict")
        finally:
            os.close(directory)
        os.rmdir(name, dir_fd=parent.fd)
        os.fsync(parent.fd)


def _remove_verified(
    reference: TargetRef,
    expected: FileImage | TreeImage,
    fault: FaultInjector,
) -> None:
    tree = isinstance(expected, TreeImage)
    if _capture_reference(reference, tree=tree) != expected:
        raise InstallerError("transaction state conflict")
    if tree:
        assert isinstance(expected, TreeImage)
        _remove_tree_prefix(reference, expected, fault)
        fault.hit("after_installer_cleanup")
        return
    with _parent_root(reference) as (parent, name):
        assert isinstance(expected, FileImage)
        if _capture_file_at(parent.fd, name, parent.owner_uid) != expected:
            raise InstallerError("transaction state conflict")
        os.unlink(name, dir_fd=parent.fd)
        os.fsync(parent.fd)
    fault.hit("after_installer_cleanup")


def conditional_remove_file(
    reference: TargetRef,
    expected: FileImage,
    guards: tuple[tuple[TargetRef, FileImage], ...],
    fault: FaultInjector,
) -> None:
    if expected.state is not ImageState.PRESENT:
        raise ValueError("conditional removal requires a present file")
    with ExitStack() as stack:
        parent, name = stack.enter_context(_parent_root(reference))
        guard_entries = tuple(
            (*stack.enter_context(_parent_root(guard)), image) for guard, image in guards
        )

        def capture() -> tuple[FileImage, tuple[FileImage, ...]]:
            return (
                _capture_file_at(parent.fd, name, parent.owner_uid),
                tuple(
                    _capture_file_at(item.fd, item_name, item.owner_uid)
                    for item, item_name, _ in guard_entries
                ),
            )

        wanted_guards = tuple(image for _, _, image in guard_entries)
        try:
            if capture() != (expected, wanted_guards):
                raise InstallerError("transaction state conflict")
            os.unlink(name, dir_fd=parent.fd)
            os.fsync(parent.fd)
            if capture() != (FileImage.absent(), wanted_guards):
                raise InstallerError("transaction state conflict")
        except (OSError, ValueError) as exc:
            raise InstallerError("transaction state conflict") from exc
    fault.hit("after_installer_cleanup")


def conditional_remove_tree(
    reference: TreeRef,
    expected: TreeImage,
    guards: tuple[tuple[TargetRef, FileImage | TreeImage], ...],
    fault: FaultInjector,
) -> None:
    if expected.state is not ImageState.PRESENT:
        raise ValueError("conditional removal requires a present tree")

    def guard_images() -> tuple[FileImage | TreeImage, ...]:
        return tuple(
            _capture_reference(guard, tree=isinstance(image, TreeImage)) for guard, image in guards
        )

    wanted = tuple(image for _, image in guards)
    try:
        if guard_images() != wanted:
            raise InstallerError("transaction state conflict")
        current = reference.capture()
        if current.state is ImageState.PRESENT:
            _remove_tree_prefix(reference, expected, fault)
        elif current != TreeImage.absent():
            raise InstallerError("transaction state conflict")
        if reference.capture() != TreeImage.absent() or guard_images() != wanted:
            raise InstallerError("transaction state conflict")
    except InstallerError:
        raise
    except (OSError, ValueError) as exc:
        raise InstallerError("transaction state conflict") from exc
    fault.hit("after_installer_cleanup")


def conditional_swap_file(
    left: TargetRef,
    expected_left: FileImage,
    right: TargetRef,
    expected_right: FileImage,
    guards: tuple[tuple[TargetRef, FileImage], ...],
    fault: FaultInjector,
) -> None:
    if (
        expected_left.state is not ImageState.PRESENT
        or expected_right.state is not ImageState.PRESENT
    ):
        raise ValueError("conditional swap requires present files")
    with ExitStack() as stack:
        left_parent, left_name = stack.enter_context(_parent_root(left))
        right_parent, right_name = stack.enter_context(_parent_root(right))
        guard_entries = tuple(
            (*stack.enter_context(_parent_root(guard)), image) for guard, image in guards
        )

        def capture() -> tuple[FileImage, FileImage, tuple[FileImage, ...]]:
            return (
                _capture_file_at(left_parent.fd, left_name, left_parent.owner_uid),
                _capture_file_at(right_parent.fd, right_name, right_parent.owner_uid),
                tuple(
                    _capture_file_at(item.fd, item_name, item.owner_uid)
                    for item, item_name, _ in guard_entries
                ),
            )

        wanted_guards = tuple(image for _, _, image in guard_entries)
        before = (expected_left, expected_right, wanted_guards)
        after = (expected_right, expected_left, wanted_guards)
        try:
            if capture() != before:
                raise InstallerError("transaction state conflict")
            rename_swap(
                left_parent,
                left_name,
                right_parent,
                right_name,
                fault,
            )
            if capture() == after:
                return
            current = capture()
            if current[0].state is ImageState.PRESENT and current[1].state is ImageState.PRESENT:
                rename_swap(
                    left_parent,
                    left_name,
                    right_parent,
                    right_name,
                    NoOpFaultInjector(),
                )
                if capture() != current[1::-1] + (current[2],):
                    raise InstallerError("transaction state conflict")
            raise InstallerError("transaction state conflict")
        except (OSError, ValueError) as exc:
            raise InstallerError("transaction state conflict") from exc


def _require_images(
    actual: tuple[FileImage | TreeImage, FileImage | TreeImage, FileImage | TreeImage],
    expected: tuple[FileImage | TreeImage, FileImage | TreeImage, FileImage | TreeImage],
) -> None:
    if actual != expected:
        raise InstallerError("transaction state conflict")


def _conditional_swap(
    left: TargetRef,
    right: TargetRef,
    target: TargetRef,
    stage: StagedObject,
    recovery: TargetRef,
    expected_left: FileImage | TreeImage,
    expected_right: FileImage | TreeImage,
    expected_after: tuple[FileImage | TreeImage, FileImage | TreeImage, FileImage | TreeImage],
    fault: FaultInjector,
    *,
    tree: bool,
) -> None:
    _rename_refs(left, right, fault, swap=True)
    actual = _images(target, stage, recovery, tree=tree)
    if actual == expected_after:
        return
    left_after = _capture_reference(left, tree=tree)
    right_after = _capture_reference(right, tree=tree)
    if (
        (right_after == expected_left or left_after == expected_right)
        and left_after.state is ImageState.PRESENT
        and right_after.state is ImageState.PRESENT
    ):
        _rename_refs(left, right, NoOpFaultInjector(), swap=True)
        if (
            _capture_reference(left, tree=tree) != right_after
            or _capture_reference(right, tree=tree) != left_after
        ):
            raise InstallerError("transaction state conflict")
    raise InstallerError("transaction state conflict")


def _conditional_excl(
    source: TargetRef,
    destination: TargetRef,
    target: TargetRef,
    stage: StagedObject,
    recovery: TargetRef,
    expected_after: tuple[FileImage | TreeImage, FileImage | TreeImage, FileImage | TreeImage],
    fault: FaultInjector,
    *,
    tree: bool,
) -> None:
    _rename_refs(source, destination, fault, swap=False)
    if _images(target, stage, recovery, tree=tree) == expected_after:
        return
    absent = TreeImage.absent() if tree else FileImage.absent()
    source_after = _capture_reference(source, tree=tree)
    destination_after = _capture_reference(destination, tree=tree)
    if source_after == absent and destination_after.state is ImageState.PRESENT:
        _rename_refs(destination, source, NoOpFaultInjector(), swap=False)
        if (
            _capture_reference(source, tree=tree) != destination_after
            or _capture_reference(destination, tree=tree) != absent
        ):
            raise InstallerError("transaction state conflict")
    raise InstallerError("transaction state conflict")


def _sync_prefix(
    references: tuple[TargetRef, ...],
    target: TargetRef,
    stage: StagedObject,
    recovery: TargetRef,
    expected: tuple[FileImage | TreeImage, FileImage | TreeImage, FileImage | TreeImage],
    *,
    tree: bool,
) -> None:
    _sync_parents(references)
    _require_images(_images(target, stage, recovery, tree=tree), expected)


def _sync_parents(references: tuple[TargetRef, ...]) -> None:
    parents: list[SafeRoot] = []
    try:
        for reference in references:
            parent_fd, _ = reference.root.open_parent(reference.relative)
            parent = SafeRoot(reference.path.parent, reference.root.owner_uid, parent_fd)
            if all(parent.fd != opened.fd for opened in parents):
                parents.append(parent)
            else:
                parent.close()
        for parent in parents:
            os.fsync(parent.fd)
    finally:
        for parent in parents:
            parent.close()


def _forward(
    target: TargetRef,
    expected_pre: FileImage | TreeImage,
    staged_post: StagedObject,
    recovery: TargetRef,
    fault: FaultInjector,
    *,
    tree: bool,
) -> NativeState:
    post = staged_post.image
    absent = TreeImage.absent() if tree else FileImage.absent()
    if (
        type(expected_pre) is not type(absent)
        or type(post) is not type(absent)
        or post.state is not ImageState.PRESENT
    ):
        raise ValueError("transaction image kind mismatch")
    current = _images(target, staged_post, recovery, tree=tree)
    if expected_pre.state is ImageState.PRESENT:
        if current == (expected_pre, post, absent):
            _conditional_swap(
                target,
                staged_post,
                target,
                staged_post,
                recovery,
                expected_pre,
                post,
                (post, expected_pre, absent),
                fault,
                tree=tree,
            )
            return NativeState.SWAPPED
        if current == (post, expected_pre, absent):
            _sync_prefix(
                (target, staged_post),
                target,
                staged_post,
                recovery,
                current,
                tree=tree,
            )
            _conditional_excl(
                staged_post,
                recovery,
                target,
                staged_post,
                recovery,
                (post, absent, expected_pre),
                fault,
                tree=tree,
            )
            return NativeState.PARKED
        if current == (post, absent, expected_pre):
            _sync_prefix(
                (staged_post, recovery),
                target,
                staged_post,
                recovery,
                current,
                tree=tree,
            )
            return NativeState.COMPLETED
    else:
        if current == (absent, post, absent):
            _conditional_excl(
                staged_post,
                target,
                target,
                staged_post,
                recovery,
                (post, absent, absent),
                fault,
                tree=tree,
            )
            return NativeState.PUBLISHED
        if current == (post, absent, absent):
            _sync_prefix(
                (staged_post, target),
                target,
                staged_post,
                recovery,
                current,
                tree=tree,
            )
            return NativeState.COMPLETED
    raise InstallerError("transaction state conflict")


def forward_file(
    target: TargetRef,
    expected_pre: FileImage,
    staged_post: StagedFile,
    recovery: TargetRef,
    fault: FaultInjector,
) -> NativeState:
    return _forward(target, expected_pre, staged_post, recovery, fault, tree=False)


def forward_tree(
    target: TreeRef,
    expected_pre: TreeImage,
    staged_post: StagedTree,
    recovery: TreeRef,
    fault: FaultInjector,
) -> NativeState:
    return _forward(target, expected_pre, staged_post, recovery, fault, tree=True)


def _restore(
    target: TargetRef,
    expected_pre: FileImage | TreeImage,
    expected_post: FileImage | TreeImage,
    stage: StagedObject,
    recovery: TargetRef,
    fault: FaultInjector,
    *,
    tree: bool,
) -> RestoreState:
    absent = TreeImage.absent() if tree else FileImage.absent()
    if (
        type(expected_pre) is not type(absent)
        or type(expected_post) is not type(absent)
        or expected_post.state is not ImageState.PRESENT
    ):
        raise ValueError("transaction image kind mismatch")
    current = _images(target, stage, recovery, tree=tree)
    if expected_pre.state is ImageState.PRESENT:
        if current == (expected_pre, absent, absent):
            _sync_prefix((target, recovery), target, stage, recovery, current, tree=tree)
            return RestoreState.RESTORED
        if current == (expected_pre, expected_post, absent):
            _sync_prefix((target, stage), target, stage, recovery, current, tree=tree)
            _conditional_excl(
                stage,
                recovery,
                target,
                stage,
                recovery,
                (expected_pre, absent, expected_post),
                fault,
                tree=tree,
            )
            return RestoreState.RESTORING
        if current == (expected_post, expected_pre, absent):
            _sync_prefix((target, stage), target, stage, recovery, current, tree=tree)
            _conditional_swap(
                target,
                stage,
                target,
                stage,
                recovery,
                expected_post,
                expected_pre,
                (expected_pre, expected_post, absent),
                fault,
                tree=tree,
            )
            return RestoreState.RESTORING
        if current == (expected_post, absent, expected_pre):
            _sync_prefix((stage, recovery), target, stage, recovery, current, tree=tree)
            _conditional_swap(
                target,
                recovery,
                target,
                stage,
                recovery,
                expected_post,
                expected_pre,
                (expected_pre, absent, expected_post),
                fault,
                tree=tree,
            )
            return RestoreState.RESTORING
        recovery_post = current[2] == expected_post or (
            tree
            and isinstance(current[2], TreeImage)
            and isinstance(expected_post, TreeImage)
            and _tree_prefix(current[2], expected_post) is not None
        )
        if current[0] == expected_pre and current[1] == absent and recovery_post:
            _sync_parents((target, stage, recovery))
            refreshed = _images(target, stage, recovery, tree=tree)
            refreshed_post = refreshed[2] == expected_post or (
                tree
                and isinstance(refreshed[2], TreeImage)
                and isinstance(expected_post, TreeImage)
                and _tree_prefix(refreshed[2], expected_post) is not None
            )
            if refreshed[0] != expected_pre or refreshed[1] != absent or not refreshed_post:
                raise InstallerError("transaction state conflict")
            if tree:
                assert isinstance(expected_post, TreeImage)
                _remove_tree_prefix(recovery, expected_post, fault)
            else:
                _remove_verified(recovery, expected_post, fault)
            return RestoreState.RESTORED
    else:
        if current == (absent, absent, absent):
            _sync_prefix((target, recovery), target, stage, recovery, current, tree=tree)
            return RestoreState.RESTORED
        if current == (absent, expected_post, absent):
            _conditional_excl(
                stage,
                recovery,
                target,
                stage,
                recovery,
                (absent, absent, expected_post),
                fault,
                tree=tree,
            )
            return RestoreState.RESTORING
        if current == (expected_post, absent, absent):
            _sync_prefix((stage, target), target, stage, recovery, current, tree=tree)
            _conditional_excl(
                target,
                recovery,
                target,
                stage,
                recovery,
                (absent, absent, expected_post),
                fault,
                tree=tree,
            )
            return RestoreState.RESTORING
        recovery_post = current[2] == expected_post or (
            tree
            and isinstance(current[2], TreeImage)
            and isinstance(expected_post, TreeImage)
            and _tree_prefix(current[2], expected_post) is not None
        )
        if current[0] == absent and current[1] == absent and recovery_post:
            _sync_parents((target, stage, recovery))
            refreshed = _images(target, stage, recovery, tree=tree)
            refreshed_post = refreshed[2] == expected_post or (
                tree
                and isinstance(refreshed[2], TreeImage)
                and isinstance(expected_post, TreeImage)
                and _tree_prefix(refreshed[2], expected_post) is not None
            )
            if refreshed[0] != absent or refreshed[1] != absent or not refreshed_post:
                raise InstallerError("transaction state conflict")
            if tree:
                assert isinstance(expected_post, TreeImage)
                _remove_tree_prefix(recovery, expected_post, fault)
            else:
                _remove_verified(recovery, expected_post, fault)
            return RestoreState.RESTORED
    raise InstallerError("transaction state conflict")


def restore_file(
    target: TargetRef,
    expected_pre: FileImage,
    expected_post: FileImage,
    stage: StagedFile,
    recovery: TargetRef,
    fault: FaultInjector,
) -> RestoreState:
    return _restore(
        target,
        expected_pre,
        expected_post,
        stage,
        recovery,
        fault,
        tree=False,
    )


def restore_tree(
    target: TreeRef,
    expected_pre: TreeImage,
    expected_post: TreeImage,
    stage: StagedTree,
    recovery: TreeRef,
    fault: FaultInjector,
) -> RestoreState:
    return _restore(
        target,
        expected_pre,
        expected_post,
        stage,
        recovery,
        fault,
        tree=True,
    )


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


def _complete_json_retry(
    parent_fd: int,
    current: FileImage,
    stale: FileImage,
    expected: FileImage,
    raw: bytes,
    path: TargetRef,
    temp_name: str,
    retain_old: TargetRef | None,
) -> bool:
    if not _matches_json_payload(current, raw, path.root.owner_uid):
        return False
    if capture_file(path.root, path.relative) != current:
        raise ValueError("JSON target changed during retry classification")
    if stale == expected and expected.state is ImageState.PRESENT:
        _finish_old_json(parent_fd, temp_name, stale, path.root, retain_old)
    elif stale.state is ImageState.ABSENT:
        if expected.state is ImageState.PRESENT and retain_old is not None:
            retain_fd, retain_name = retain_old.root.open_parent(retain_old.relative)
            try:
                retained = _capture_file_at(retain_fd, retain_name, retain_old.root.owner_uid)
                if retained != expected:
                    return False
                os.fsync(retain_fd)
                os.fsync(parent_fd)
                if _capture_file_at(retain_fd, retain_name, retain_old.root.owner_uid) != retained:
                    raise ValueError("retained JSON changed during retry completion")
            finally:
                os.close(retain_fd)
        else:
            os.fsync(parent_fd)
    else:
        return False
    if capture_file(path.root, path.relative) != current:
        raise ValueError("JSON target changed during retry completion")
    return True


def write_atomic_json(
    path: TargetRef,
    expected: FileImage,
    payload: Mapping[str, object],
    install_id: UUID,
    retain_old: TargetRef | None = None,
    *,
    fault: FaultInjector,
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
            if _complete_json_retry(
                parent_fd,
                current,
                stale,
                expected,
                raw,
                path,
                temp_name,
                retain_old,
            ):
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
            fault.hit("after_json_file_fsync")
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
        fault.hit("after_json_rename")
        os.fsync(parent_fd)
        fault.hit("after_json_parent_fsync")
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
