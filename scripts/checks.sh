#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1

find protocol bridge server smoke scripts tests -type d -name __pycache__ \
  -prune -exec rm -rf '{}' +
find protocol bridge server smoke scripts tests -type f \
  \( -name '*.pyc' -o -name '*.pyo' \) -delete
test -z "$(find protocol bridge server smoke scripts tests \
  -name __pycache__ -print -quit)"
test -z "$(find protocol bridge server smoke scripts tests -type f \
  \( -name '*.pyc' -o -name '*.pyo' \) -print -quit)"

# preflight（audit F-07/F-13）：当前非交互 PATH 不含 ~/.local/bin，使用已核实绝对路径
UV_BIN=/Users/yeminjie/.local/bin/uv
test -x "$UV_BIN" || { echo "FAIL: $UV_BIN 不可执行"; exit 1; }
echo "toolchain: uv=$($UV_BIN --version 2>&1)"

"$UV_BIN" sync --frozen --python 3.13  # ADR：锁定依赖与解释器，禁止隐式升级
"$UV_BIN" run --frozen ruff check protocol bridge server tests scripts smoke
"$UV_BIN" run --frozen mypy
# 检查 1：core 与 protocol 禁 bpy（行首匹配，避开注释/文案）
if grep -rnE '^[[:space:]]*(import bpy|from bpy)' bridge/core protocol --include='*.py'; then
  echo "FAIL: bpy import in core/protocol"; exit 1
fi
"$UV_BIN" run --frozen python scripts/vendor_protocol.py            # 生成
"$UV_BIN" run --frozen python scripts/vendor_protocol.py --check    # 检查 2
"$UV_BIN" run --frozen python scripts/nested_import_smoke.py        # 检查 3
"$UV_BIN" run --frozen pytest -q                                    # L1 + L2
echo "ALL CHECKS PASSED"
