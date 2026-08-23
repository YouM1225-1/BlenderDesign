"""会话 token 与 session.json 原子读写。spec §2.2、§4.1。"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any


class SessionAuth:
    def __init__(self, token: str) -> None:
        self._token = token

    @staticmethod
    def generate() -> str:
        return secrets.token_urlsafe(32)

    def verify(self, presented: object) -> bool:
        if not isinstance(presented, str):
            return False
        try:
            return secrets.compare_digest(self._token.encode(), presented.encode())
        except UnicodeEncodeError:
            return False


def write_session_file(path: Path, data: dict[str, Any], *, dir_fd: int | None = None) -> None:
    tmp = path.with_name(path.name + ".tmp")
    if dir_fd is None:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    else:
        fd = os.open(tmp.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=dir_fd)
    owns_fd = True
    tmp_identity: tuple[int, int] | None = None
    try:
        tmp_stat = os.fstat(fd)
        tmp_identity = tmp_stat.st_dev, tmp_stat.st_ino
        os.fchmod(fd, 0o600)
        stream = os.fdopen(fd, "w", encoding="utf-8")
        owns_fd = False
        with stream as file:
            json.dump(data, file, ensure_ascii=False)
        if dir_fd is None:
            os.replace(tmp, path)
        else:
            os.replace(tmp.name, path.name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    except BaseException:
        try:
            if dir_fd is None:
                current = os.stat(tmp, follow_symlinks=False)
            else:
                current = os.stat(tmp.name, dir_fd=dir_fd, follow_symlinks=False)
            # POSIX has no atomic identity check and unlink; this only bounds that race.
            if tmp_identity == (current.st_dev, current.st_ino):
                if dir_fd is None:
                    os.unlink(tmp)
                else:
                    os.unlink(tmp.name, dir_fd=dir_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        if owns_fd:
            os.close(fd)
