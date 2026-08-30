#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
export UV_NO_EDITABLE=1
PWD_ROOT="$PWD"
PYTHON_VERSION="3.13.13"

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

"$UV_BIN" sync --frozen --python "$PYTHON_VERSION"  # ADR：锁定依赖与解释器，禁止隐式升级

# venv 健康探针：iCloud「桌面与文稿」同步会给点开头的条目打 UF_HIDDEN，.venv 内的
# .pth 随之变 hidden，CPython 的 site.addsitedir 直接跳过 → editable 安装失效，
# 表现为子进程 ModuleNotFoundError 引发的无关断言失败。uv sync 检测不到这种损坏。
# 必须在仓库外执行，否则 cwd 恰好在 sys.path 上会假阳性。
if ! (cd / && "$PWD_ROOT/.venv/bin/python" -c "import server" 2>/dev/null); then
  echo "FAIL: .venv 的 .pth 被 iCloud 标记为 hidden，editable 安装失效"
  echo "  修复：chflags -R nohidden .venv"
  exit 1
fi
"$UV_BIN" run --frozen ruff check \
  protocol bridge server tests scripts smoke acceptance plugins/blender-mcp-installer/scripts
"$UV_BIN" run --frozen mypy
"$UV_BIN" run --frozen mypy --strict --ignore-missing-imports --follow-imports=skip \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/__init__.py \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/codex_adapter.py \
  plugins/blender-mcp-installer/scripts/install.py \
  plugins/blender-mcp-installer/scripts/project_marketplace.py
PLUGIN_CREATOR_ROOT="${PLUGIN_CREATOR_ROOT:-$HOME/.codex/skills/.system/plugin-creator}"
PLUGIN_VALIDATOR="$PLUGIN_CREATOR_ROOT/scripts/validate_plugin.py"
test -f "$PLUGIN_VALIDATOR" || {
  echo "FAIL: PLUGIN_CREATOR_ROOT 未提供有效的插件验证器"; exit 1;
}
"$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" \
  --with PyYAML==6.0.2 python "$PLUGIN_VALIDATOR" plugins/blender-mcp-installer
# 检查 1：core 与 protocol 禁 bpy（行首匹配，避开注释/文案）
if grep -rnE '^[[:space:]]*(import bpy|from bpy)' bridge/core protocol --include='*.py'; then
  echo "FAIL: bpy import in core/protocol"; exit 1
fi
"$UV_BIN" run --frozen python scripts/vendor_protocol.py            # 生成
"$UV_BIN" run --frozen python scripts/vendor_protocol.py --check    # 检查 2
"$UV_BIN" sync --frozen --python "$PYTHON_VERSION" --reinstall-package blender-codex
"$UV_BIN" run --frozen python scripts/nested_import_smoke.py        # 检查 3
SDIST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/blender-codex-sdist.XXXXXX")"
trap 'rm -rf "$SDIST_DIR"' EXIT
"$UV_BIN" build --sdist --no-build-logs --out-dir "$SDIST_DIR"
SDIST="$(find "$SDIST_DIR" -maxdepth 1 -type f -name '*.tar.gz' -print -quit)"
test -n "$SDIST"
UNEXPECTED_SDIST="$(tar -tzf "$SDIST" | sed 's|^[^/]*/||' | \
  grep -Ev '^$|^(\.gitignore|PKG-INFO|pyproject.toml|(bridge|protocol|server)/.*)$' || true)"
if test -n "$UNEXPECTED_SDIST"; then
  echo "FAIL: sdist 包含白名单外文件"
  echo "$UNEXPECTED_SDIST"
  exit 1
fi
"$UV_BIN" run --frozen pytest -q --ignore=tests/distribution         # L1 + L2
"$UV_BIN" run --frozen pytest tests/distribution -q                 # distributable

if test "${RELEASE:-0}" = 1; then
  : "${OFFICIAL_MCP_SOURCE:?RELEASE=1 requires OFFICIAL_MCP_SOURCE}"
  : "${BLENDER_BIN:?RELEASE=1 requires BLENDER_BIN}"
  case "$OFFICIAL_MCP_SOURCE:$BLENDER_BIN" in
    /*:/*) ;;
    *) echo "FAIL: release paths must be absolute"; exit 1 ;;
  esac
  test -d "$OFFICIAL_MCP_SOURCE/.git"
  test -x "$BLENDER_BIN"

  RELEASE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/blender-codex-release.XXXXXX")"
  trap 'rm -rf "$SDIST_DIR" "$RELEASE_DIR"' EXIT
  UPSTREAM_COMMIT="$($PWD_ROOT/.venv/bin/python -I -c \
    'import sys; sys.path.insert(0, "plugins/blender-mcp-installer/scripts"); from blender_mcp_installer.bundle import UPSTREAM_COMMIT; print(UPSTREAM_COMMIT)')"
  REMOTE_MAIN="$(/usr/bin/env -i HOME=/var/empty PATH=/usr/bin:/bin LC_ALL=C \
    GIT_TERMINAL_PROMPT=0 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
    /usr/bin/git ls-remote --exit-code \
    https://projects.blender.org/lab/blender_mcp.git refs/heads/main)"
  test "$REMOTE_MAIN" = "$UPSTREAM_COMMIT$(printf '\t')refs/heads/main"
  "$PWD_ROOT/.venv/bin/python" -I - "$PWD_ROOT" "$OFFICIAL_MCP_SOURCE" \
    "$RELEASE_DIR" <<'PY'
import sys
from pathlib import Path

root, source, workspace = map(Path, sys.argv[1:])
sys.path.insert(0, str(root))
from scripts.build_official_blender_mcp_distribution import (  # noqa: E402
    _apply_downstream_patches,
    _extract_two_archives,
    _stage_downstream_patches,
)

sources, _epoch = _extract_two_archives(source, workspace)
patches = _stage_downstream_patches(workspace)
for extracted in sources:
    _apply_downstream_patches(extracted, patches)
PY
  PATCHED_SOURCE="$RELEASE_DIR/source-1"

  for sdk in 1.28.1 2.0.0; do
    "$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" \
      --with "mcp[cli]==$sdk" --with pyyaml==6.0.3 --with docutils==0.23 \
      --with types-pyyaml==6.0.12.20260815 \
      --with types-docutils==0.22.3.20260724 \
      --with ruff==0.12.5 --with mypy==1.17.1 --with vulture==2.14 \
      make -C "$PATCHED_SOURCE" PYTHON=python check_all
    for test_file in test_tool_listing.py test_rst_parse.py test_rst_search.py \
      test_mcp_server.py test_transport_limits.py test_chat_client.py; do
      (
        cd "$PATCHED_SOURCE"
        PYTHONPATH="$PATCHED_SOURCE/mcp:$PATCHED_SOURCE/addon:$PATCHED_SOURCE" \
          "$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" \
          --with "mcp[cli]==$sdk" --with pyyaml==6.0.3 --with docutils==0.23 \
          python "tests/$test_file"
      )
    done
  done

  "$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" --with bandit==1.9.4 \
    bandit -q -r protocol bridge server smoke scripts acceptance \
    plugins/blender-mcp-installer/scripts -ll
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" --with bandit==1.9.4 \
    bandit -q -r "$PATCHED_SOURCE/mcp" "$PATCHED_SOURCE/addon" \
    "$PATCHED_SOURCE/chat_client" "$PATCHED_SOURCE/_misc" -ll
  SECRET_SCAN="$("$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" \
    --with detect-secrets==1.5.0 detect-secrets scan \
    --disable-plugin Base64HighEntropyString \
    --disable-plugin HexHighEntropyString)"
  "$PWD_ROOT/.venv/bin/python" -I -c \
    'import json,sys; data=json.loads(sys.argv[1]); raise SystemExit(any(data["results"].values()))' \
    "$SECRET_SCAN"

  "$UV_BIN" export --quiet --frozen --no-emit-project --no-header \
    --output-file "$RELEASE_DIR/root-requirements.txt"
  for requirements in "$RELEASE_DIR/root-requirements.txt" \
    scripts/requirements/official-blender-mcp-build.lock \
    plugins/blender-mcp-installer/artifacts/runtime-requirements.lock; do
    "$UV_BIN" run --quiet --no-project --python "$PYTHON_VERSION" \
      --with pip-audit==2.10.1 pip-audit --progress-spinner off -r "$requirements"
  done

  "$UV_BIN" run --frozen python scripts/build_official_blender_mcp_distribution.py \
    --source "$OFFICIAL_MCP_SOURCE" --blender "$BLENDER_BIN" --uv "$UV_BIN" \
    --output "$RELEASE_DIR/artifacts"
  for artifact in SHA256SUMS manifest.json blender_mcp-1.0.0-py3-none-any.whl \
    mcp-1.0.0.zip runtime-requirements.lock; do
    cmp "plugins/blender-mcp-installer/artifacts/$artifact" \
      "$RELEASE_DIR/artifacts/$artifact"
  done
  echo "RELEASE CHECKS PASSED"
fi
echo "ALL CHECKS PASSED"
