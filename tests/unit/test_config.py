from pathlib import Path

from server.core import config


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BLENDERCODEX_ROOT", str(tmp_path))
    assert config.runtime_root() == tmp_path
    assert config.run_dir() == tmp_path / "run"
    assert config.logs_dir() == tmp_path / "logs"


def test_default_under_app_support(monkeypatch):
    monkeypatch.delenv("BLENDERCODEX_ROOT", raising=False)
    p = config.runtime_root()
    assert p == Path.home() / "Library" / "Application Support" / "BlenderCodex"
