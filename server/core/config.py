"""runtime 根注入点。spec §7.2：BLENDERCODEX_ROOT。"""
from __future__ import annotations

import os
from pathlib import Path


def runtime_root() -> Path:
    env = os.environ.get("BLENDERCODEX_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Library" / "Application Support" / "BlenderCodex"


def run_dir() -> Path:
    return runtime_root() / "run"


def logs_dir() -> Path:
    return runtime_root() / "logs"
