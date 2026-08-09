"""把 bridge/（含 _vendor）复制进人造 bl_ext 深层包，在剥离仓库根的 sys.path 下 import。
拦截 protocol/ 或 bridge/core 里的顶层绝对导入（spec §3.1 约束 2 + _proto 垫片）。"""
from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory() as td:
    ns = Path(td) / "bl_ext" / "user_default"
    ns.mkdir(parents=True)
    (ns.parent / "__init__.py").write_text("")
    (ns / "__init__.py").write_text("")
    shutil.copytree(ROOT / "bridge", ns / "blender_codex_bridge",
                    ignore=shutil.ignore_patterns("__pycache__", "blender"))
    (ns / "blender_codex_bridge" / "__init__.py").write_text("")   # 根 shim 换成空：不测 bpy 分支
    sys.path = [td] + [p for p in sys.path if Path(p or ".").resolve() != ROOT]
    for mod in ("bl_ext.user_default.blender_codex_bridge._vendor.protocol.envelope",
                "bl_ext.user_default.blender_codex_bridge.core.lifecycle"):
        importlib.import_module(mod)
    print("nested import ok")
