from __future__ import annotations

from typing import Any

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from acceptance.canonical import digest
from acceptance.primitives import AcceptanceFailure, path_is_within

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _stat_signature(s: os.stat_result) -> tuple[int, int, int, int, int]:
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def valid_id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def relative_path(value: object) -> str:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise AcceptanceFailure("contract_invalid", "invalid relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise AcceptanceFailure("contract_invalid", "path must contain ordinary relative segments")
    return value


def open_parent(path: Path) -> tuple[int, str]:
    path = path.expanduser().absolute()
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for segment in path.parts[1:-1]:
            next_fd = os.open(segment, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd, path.name
    except BaseException:
        os.close(fd)
        raise


def safe_open(path: Path, flags: int, mode: int = 0o600) -> int:
    parent, name = open_parent(path)
    try:
        return os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=parent)
    finally:
        os.close(parent)


@dataclass(frozen=True, slots=True)
class BoundFile:
    id: str
    path: Path
    bytes: int
    sha256: str

    def descriptor(self, relative: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": relative_path(relative),
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


def measure_file(
    path: Path, max_bytes: int, *, file_id: str, copy_to: Path | None = None
) -> BoundFile:
    if not valid_id(file_id) or type(max_bytes) is not int or max_bytes < 0:
        raise AcceptanceFailure("contract_invalid", "invalid file identity/budget")
    src = safe_open(path, os.O_RDONLY)
    dst = -1
    try:
        before = os.fstat(src)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise AcceptanceFailure("evidence_file_invalid", "not a bounded regular file")
        if copy_to is not None:
            dst = safe_open(copy_to, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        hasher = hashlib.sha256()
        count = 0
        while True:
            chunk = os.read(src, min(1024 * 1024, max_bytes - count + 1))
            if not chunk:
                break
            count += len(chunk)
            if count > max_bytes:
                raise AcceptanceFailure("evidence_file_invalid", "file grew beyond budget")
            hasher.update(chunk)
            if dst >= 0:
                view = memoryview(chunk)
                while view:
                    written = os.write(dst, view)
                    if written <= 0:
                        raise AcceptanceFailure(
                            "evidence_file_invalid", "copy write made no progress"
                        )
                    view = view[written:]
        after = os.fstat(src)

        if _stat_signature(before) != _stat_signature(after) or count != before.st_size:
            raise AcceptanceFailure("hash_mismatch", "file changed while reading")
        if dst >= 0:
            os.fsync(dst)
            os.fchmod(dst, 0o400)
        return BoundFile(file_id, copy_to or path, count, hasher.hexdigest())
    finally:
        if dst >= 0:
            os.close(dst)
        os.close(src)


def descriptor_valid(entry: object) -> bool:
    if type(entry) is not dict or set(entry) != {"id", "path", "bytes", "sha256"}:
        return False
    if not valid_id(entry["id"]) or type(entry["bytes"]) is not int or entry["bytes"] < 0:
        return False
    if type(entry["sha256"]) is not str or _HEX.fullmatch(entry["sha256"]) is None:
        return False
    relative_path(entry["path"])
    return True


def source_digest(entries: list[dict[str, Any]]) -> str:
    if any(not descriptor_valid(row) for row in entries):
        raise AcceptanceFailure("contract_invalid", "invalid source descriptor")
    if (
        not entries
        or entries != sorted(entries, key=lambda row: row["id"])
        or len({r["id"] for r in entries}) != len(entries)
        or len({r["path"] for r in entries}) != len(entries)
    ):
        raise AcceptanceFailure("contract_invalid", "source members must be unique and ordered")
    return digest("source.v2", entries)


def _raise_walk_error(error: OSError) -> None:
    raise error


def verify_bundle(
    root: Path, entries: list[dict[str, Any]], *, max_file_bytes: int
) -> dict[str, BoundFile]:
    source_digest(entries)
    expected = {row["path"] for row in entries}
    actual = set()
    for current, directories, files in os.walk(
        root, followlinks=False, onerror=_raise_walk_error
    ):
        for name in directories:
            if (Path(current) / name).is_symlink():
                raise AcceptanceFailure("evidence_file_invalid", "symlink directory in source")
        for name in files:
            actual.add((Path(current) / name).relative_to(root).as_posix())
    if actual != expected:
        raise AcceptanceFailure("expected_set_mismatch", "source file set changed")
    result = {}
    for entry in entries:
        actual_file = measure_file(root / entry["path"], max_file_bytes, file_id=entry["id"])
        if actual_file.bytes != entry["bytes"] or actual_file.sha256 != entry["sha256"]:
            raise AcceptanceFailure("hash_mismatch", "source bytes do not match contract")
        result[entry["id"]] = actual_file
    return result


def freeze_bundle(
    sources: list[dict[str, Any]],
    root: Path,
    *,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> list[dict[str, Any]]:
    budgets = (max_files, max_file_bytes, max_total_bytes)
    if any(type(value) is not int or value <= 0 for value in budgets):
        raise AcceptanceFailure("contract_invalid", "source budgets must be positive integers")
    if root.exists() or not 0 < len(sources) <= max_files:
        raise AcceptanceFailure("contract_invalid", "new bounded source bundle required")
    for source in sources:
        if type(source) is not dict or set(source) != {"id", "path", "source"}:
            raise AcceptanceFailure("contract_invalid", "source needs id/path/source")
        if not valid_id(source["id"]):
            raise AcceptanceFailure("contract_invalid", "invalid source id")
        relative_path(source["path"])
    if len({r["id"] for r in sources}) != len(sources) or len(
        {r["path"] for r in sources}
    ) != len(sources):
        raise AcceptanceFailure("contract_invalid", "duplicate source member")
    root.mkdir(mode=0o700)
    rows = []
    total = 0
    for source in sorted(sources, key=lambda row: row["id"]):
        target = root / source["path"]
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        measured = measure_file(
            Path(source["source"]),
            min(max_file_bytes, max_total_bytes - total),
            file_id=source["id"],
            copy_to=target,
        )
        total += measured.bytes
        rows.append(measured.descriptor(source["path"]))
    return rows


def read_bounded(path: Path, max_bytes: int) -> bytes:
    if type(max_bytes) is not int or max_bytes < 0:
        raise AcceptanceFailure("contract_invalid", "invalid read budget")
    fd = safe_open(path, os.O_RDONLY)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise AcceptanceFailure("evidence_file_invalid", "invalid bounded JSON file")
        chunks = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)

        raw = b"".join(chunks)
        if (
            _stat_signature(before) != _stat_signature(after)
            or len(raw) != before.st_size
            or len(raw) > max_bytes
        ):
            raise AcceptanceFailure("hash_mismatch", "JSON changed or exceeded budget")
        return raw
    finally:
        os.close(fd)


def _absolute_path(path: Path) -> Path:
    absolute = path.expanduser().absolute()
    if ".." in absolute.parts:
        raise AcceptanceFailure("contract_invalid", "managed paths cannot contain '..'")
    return absolute


def validate_roots(
    source_root: Path, evidence_root: Path, scratch_root: Path, repo_root: Path
) -> None:
    roots = [_absolute_path(path) for path in (source_root, evidence_root, scratch_root)]
    repo_root = _absolute_path(repo_root)
    for root in roots:
        parent, name = open_parent(root)
        try:
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if info is not None and not stat.S_ISDIR(info.st_mode):
                raise AcceptanceFailure(
                    "contract_invalid", "managed root is not an ordinary directory"
                )
        finally:
            os.close(parent)
        if path_is_within(root, repo_root):
            raise AcceptanceFailure("contract_invalid", "managed root is inside repository")
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if path_is_within(left, right) or path_is_within(right, left):
                raise AcceptanceFailure("contract_invalid", "managed roots overlap")
