#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
export UV_NO_EDITABLE=1
PWD_ROOT="$PWD"

find protocol bridge server smoke scripts tests -type d -name __pycache__ \
  -prune -exec rm -rf '{}' +
find protocol bridge server smoke scripts tests -type f \
  \( -name '*.pyc' -o -name '*.pyo' \) -delete
test -z "$(find protocol bridge server smoke scripts tests \
  -name __pycache__ -print -quit)"
test -z "$(find protocol bridge server smoke scripts tests -type f \
  \( -name '*.pyc' -o -name '*.pyo' \) -print -quit)"

# Prefer an explicit runner, then PATH, then uv's default per-user install path.
UV_BIN="${UV_BIN:-$(command -v uv || true)}"
if test -z "$UV_BIN" && test -x "$HOME/.local/bin/uv"; then
  UV_BIN="$HOME/.local/bin/uv"
fi
test -x "$UV_BIN" || { echo "FAIL: $UV_BIN 不可执行"; exit 1; }
echo "toolchain: uv=$($UV_BIN --version 2>&1)"

"$UV_BIN" sync --frozen --python 3.13  # ADR：锁定依赖与解释器，禁止隐式升级

# venv 健康探针：iCloud「桌面与文稿」同步会给点开头的条目打 UF_HIDDEN，.venv 内的
# .pth 随之变 hidden，CPython 的 site.addsitedir 直接跳过 → editable 安装失效，
# 表现为子进程 ModuleNotFoundError 引发的无关断言失败。uv sync 检测不到这种损坏。
# 必须在仓库外执行，否则 cwd 恰好在 sys.path 上会假阳性。
if ! (cd / && "$PWD_ROOT/.venv/bin/python" -c "import server" 2>/dev/null); then
  echo "FAIL: .venv 的 .pth 被 iCloud 标记为 hidden，editable 安装失效"
  echo "  修复：chflags -R nohidden .venv"
  exit 1
fi
"$UV_BIN" run --frozen ruff check protocol bridge server tests scripts smoke
"$UV_BIN" run --frozen mypy
if test -n "${PLUGIN_CREATOR_ROOT:-}"; then
  python3 "$PLUGIN_CREATOR_ROOT/scripts/validate_plugin.py" plugins/blender-mcp-installer
else
  echo "plugin validator: SKIP (set PLUGIN_CREATOR_ROOT to run)"
fi
# 检查 1：core 与 protocol 禁 bpy（行首匹配，避开注释/文案）
if grep -rnE '^[[:space:]]*(import bpy|from bpy)' bridge/core protocol --include='*.py'; then
  echo "FAIL: bpy import in core/protocol"; exit 1
fi
"$UV_BIN" run --frozen python scripts/vendor_protocol.py            # 生成
"$UV_BIN" run --frozen python scripts/vendor_protocol.py --check    # 检查 2
"$UV_BIN" sync --frozen --python 3.13 --reinstall-package blender-codex
"$UV_BIN" run --frozen python scripts/nested_import_smoke.py        # 检查 3
"$UV_BIN" run --frozen pytest -q --ignore=tests/distribution         # L1 + L2
"$UV_BIN" run --frozen --with tomlkit==0.13.3 \
  pytest tests/distribution -q                                       # distributable
echo "ALL CHECKS PASSED"
