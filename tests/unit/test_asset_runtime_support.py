from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.integration import asset_runtime_support


def test_selected_blender_version_uses_bounded_process_and_first_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def run(command: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, "Blender 5.2.1 LTS\nbuild data\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    blender = Path("/candidate/Blender")

    assert asset_runtime_support.selected_blender_version(blender) == "Blender 5.2.1 LTS"
    assert observed["command"] == (str(blender), "--version")
    assert observed["timeout"] == 10


def test_selected_blender_version_propagates_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 7, "", "version failed")

    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(AssertionError, match="version failed"):
        asset_runtime_support.selected_blender_version(Path("/candidate/Blender"))
