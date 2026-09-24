"""Run a Python entry as if the host rebooted and renumbered volume device numbers.

macOS may assign the data volume a different st_dev on every boot. The wrapper is a
real executable interpreter script that adds a fixed offset to every st_dev reported
by os.stat/os.lstat/os.fstat (uniform renumbering), or only for one inode (a
directory that became its own mount), then runs the target as __main__.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_WRAPPER = '''#!{python}
import os
import runpy
import sys

_OFFSET = {offset}
_ONLY = {only}


class _Renumbered:
    def __init__(self, info):
        self._info = info

    def __getattr__(self, name):
        value = getattr(self._info, name)
        if name == "st_dev" and (_ONLY is None or self._info.st_ino == _ONLY):
            return value + _OFFSET
        return value


def _shift(function):
    def shifted(*args, **kwargs):
        return _Renumbered(function(*args, **kwargs))
    return shifted


for _name in ("stat", "lstat", "fstat"):
    setattr(os, _name, _shift(getattr(os, _name)))
sys.argv = sys.argv[1:]
# Match direct script execution: the script directory leads the import path.
if not sys.flags.safe_path:
    sys.path[0] = os.path.dirname(os.path.abspath(sys.argv[0]))
runpy.run_path(sys.argv[0], run_name="__main__")
'''


def renumbering_python(directory: Path, offset: int = 7, only: int | None = None) -> Path:
    """Write an executable bootstrap that reports renumbered device numbers."""
    directory.mkdir(parents=True, exist_ok=True)
    wrapper = directory / f"python-renumbered-{offset}-{only}"
    wrapper.write_text(
        _WRAPPER.format(python=Path(sys.executable).resolve(), offset=offset, only=only)
    )
    wrapper.chmod(0o700)
    return wrapper.resolve()


@contextmanager
def renumbered_in_process(monkeypatch, offset: int = 7) -> Iterator[None]:
    """Report every st_dev in this process as renumbered by a fixed offset."""

    class Renumbered:
        def __init__(self, info: os.stat_result) -> None:
            self._info = info

        def __getattr__(self, name: str) -> object:
            value = getattr(self._info, name)
            return value + offset if name == "st_dev" else value

    def shift(function):
        def shifted(*args, **kwargs):
            return Renumbered(function(*args, **kwargs))

        return shifted

    with monkeypatch.context() as patch:
        for name in ("stat", "lstat", "fstat"):
            patch.setattr(os, name, shift(getattr(os, name)))
        yield
