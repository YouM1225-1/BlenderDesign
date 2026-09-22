from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.distribution.fake_host import python_script_header


def test_python_launcher_preserves_quoted_interpreter_and_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = tmp_path / "python 中文 ' \" $ ` ( ) \\users"
    python.symlink_to(sys.executable)
    monkeypatch.setattr(sys, "executable", str(python))
    launcher = tmp_path / "fake tool"
    launcher.write_text(
        python_script_header()
        + "import json, sys\nprint(json.dumps([sys.executable, sys.argv]))\n"
    )
    launcher.chmod(0o700)
    arguments = ["two words", "中文", "'\"$`()"]

    for prefix in ([], [str(python)]):
        result = subprocess.run(
            [*prefix, str(launcher), *arguments],
            env={}, capture_output=True, text=True, check=True,
        )

        assert json.loads(result.stdout) == [str(python), [str(launcher), *arguments]]
