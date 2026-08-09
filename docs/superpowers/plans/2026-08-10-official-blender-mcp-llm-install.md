# Blender Lab 官方 MCP LLM 安装与实测实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** 新增一份可由 LLM 安全执行的官方 Blender Lab MCP 安装手册，并在当前 macOS Apple Silicon 主机上完成备份、最小修复和只读端到端实测。

**Architecture:** 保持本仓库技术版本 `0.1.0` 和冻结的自研 Phase 0 交付不变；新增的 operational 文档描述独立的官方链路 `Codex -> 官方 blender MCP Server（stdio）-> localhost:9876 -> Blender 官方 mcp Extension`。当前机器优先走 no-op/repair 分支：复用已安装且内容一致的官方扩展和 Codex stanza，只在备份后开启被关闭的 Blender Online Access。新安装和显式上游更新分支固定完整 commit，并从实际 Server catalog 生成精确 allowlist。

**Tech Stack:** Markdown · zsh · Git · uv · Python 3.13 · Blender 5.2+ Extension CLI/Python API · Codex CLI/App Server JSON-RPC · MCP SDK `>=1.2.0,<2`

## Global Constraints

- 仅安装/验证 Blender Lab 官方 MCP；不得安装、注册或重新启用本仓库的 `blender-codex-server`、`blender_codex_bridge` 或 `blender-codex` MCP entry。
- 平台限定 macOS Apple Silicon；Blender 必须 `>=5.2`。5.2 是实测基线；更高版本必须通过扩展加载、listener 和安全只读调用后才能报告兼容。
- 当前固定上游为 `https://projects.blender.org/lab/blender_mcp.git@4309a39646e644261624bfcd2bca669b343b7621`。不得在 Server 每次启动时静默跟随 `main`。
- 官方 Server 必须经 `uv run --quiet --no-project --python 3.13 --with "mcp[cli]>=1.2.0,<2"` 隔离启动；`<2` 不得传播到本仓库自研 MCP SDK v2 环境。
- 修改 `~/.codex/config.toml` 或 Blender `userpref.blend` 前必须创建可验证备份。目标必须是当前 UID 所有的普通非 symlink 文件；检测到 inode/SHA 并发变化立即停止。
- Blender 正在运行且需要写偏好时，必须先正常保存并退出；不得强制终止，不得让 GUI 与另一个 CLI 进程并发写 `userpref.blend`。
- 官方 bridge 仅监听 `localhost:9876`；不得改成 `0.0.0.0` 或外部接口。
- 本用户已明确接受完整目录、显式更新时自动接受上游工具增删改名、`default_tools_approval_mode="approve"`，以及两个任意 Python 工具的风险；手册必须说明该授权不可默认复制到其他用户或主机。
- 安装 smoke 只调用 `get_blendfile_summary_datablocks` 或等价的已知只读工具；不得调用 `execute_blender_code*`、render 或 screenshot 长序列。
- 不修改 `docs/install.md`、`docs/ROADMAP.md`、既有 audit/evidence/attestation 或用户 `.blend` 文件；不新增 pytest，保持 337 unit / 32 contract / 369 full 历史门禁计数。
- 仓库内只新增 `docs/install-official-blender-mcp.md` 和本计划；真实执行记录写入 `.superpowers/sdd/`，不伪装成历史 evidence。
- 保持最小实现：不用通用安装脚本、不增加依赖、不为一次运维流程创建抽象层。

---

## Task 1: 新增 LLM 可执行的官方 MCP 安装手册

**Files:**
- Create: `docs/install-official-blender-mcp.md`
- Read-only reference: `docs/superpowers/specs/2026-08-09-official-blender-mcp-llm-install-design.md`
- Test: inline documentation contract checker only; do not create a test file

- [ ] **Step 1: 记录任务基线并运行缺失文档的 RED 检查**

Run:

```bash
git status --short --branch
python3 - <<'PY'
from pathlib import Path

path = Path("docs/install-official-blender-mcp.md")
assert path.is_file(), f"missing: {path}"
PY
```

Expected: Git worktree clean；第二条命令以 `AssertionError: missing: docs/install-official-blender-mcp.md` 失败。

- [ ] **Step 2: 创建完整手册**

Create `docs/install-official-blender-mcp.md` with this exact content:

````markdown
# Blender Lab 官方 MCP：LLM 执行安装手册

状态：operational、non-normative

本仓库技术版本：`0.1.0`

适用平台：macOS Apple Silicon

适用 Blender：`>=5.2`（5.2 为实测基线）

## 1. 目的与边界

本手册供 LLM 在获得用户明确授权后，检测、备份、安装、配置、验证、更新和
回滚 Blender Lab 官方 MCP。目标链路是：

```text
Codex
  -> 官方 blender MCP Server（stdio）
  -> localhost:9876
  -> Blender 官方 mcp Extension
  -> 当前 Blender 场景
```

本流程不安装本仓库的 `blender-codex-server`、`blender_codex_bridge` 或
`blender-codex` MCP entry，不修改用户 `.blend` 文件，也不修改本仓库冻结的
`docs/install.md`、ROADMAP、audit 或 evidence。

本手册允许联网，不提供离线 wheelhouse，不安装 Blender 本体，不支持 Intel
Mac、Windows 或 Linux。高于 Blender 5.2 的版本只有在安装后冒烟全部通过时
才能报告为兼容。

## 2. 安全授权与已知风险

开始写入前，LLM 必须得到以下授权：

1. 备份后修改 Codex `config.toml`；
2. 安装并启用 Blender Lab 官方 `mcp` Extension；
3. 备份后开启 Blender Online Access；
4. 接受完整工具目录及其中任意 Python 工具的执行风险；
5. 显式更新时是否自动接受上游新增、删除和重命名的工具。

本手册当前所有者已接受以上五项，并允许
`default_tools_approval_mode="approve"`。该授权不可自动复制给另一位用户或
另一台主机。

风险边界：

- `execute_blender_code` 和 `execute_blender_code_for_cli` 可执行任意 Python；
- Blender Extension 在没有鉴权的 `localhost:9876` 上提供 bridge；必须保持
  `localhost`，禁止使用 `0.0.0.0` 或局域网地址；
- Online Access 是 Blender 的全局用户偏好；
- 当前固定的上游 commit 没有签名且不是 release tag；完整 SHA 是本流程的来源
  边界，不是发布者签名；
- 上游依赖缺少 MCP SDK v2 上界，未加 `<2` 会因
  `mcp.server.fastmcp.FastMCP` 不存在而启动失败；
- Blender Extension CLI 的 exit code 不能独立证明安装成功；必须执行后置核验；
- 安装 smoke 不运行任意 Python、render 或截图长序列。安装成功也不代表所有
  26 个工具都已证明稳定。

## 3. 固定值与执行记录

首次安装使用：

```text
UPSTREAM_URL=https://projects.blender.org/lab/blender_mcp.git
PINNED_COMMIT=4309a39646e644261624bfcd2bca669b343b7621
EXTENSION_ID=mcp
EXTENSION_VERSION=1.0.0
MCP_NAME=blender
MCP_SDK_SPEC=mcp[cli]>=1.2.0,<2
BRIDGE_HOST=localhost
BRIDGE_PORT=9876
```

LLM 在自己的执行记录中保存以下值，但不得输出完整 Codex config 或可能包含
凭据的环境变量：

- 实际 Blender、Codex、uv、Git 和 checkout 路径；
- Blender 精确版本、架构、Extension ID/version；
- checkout 的旧/新 commit 和 clean 状态；
- 修改目标的 mode、device、inode、pre-SHA 和 post-SHA；
- 备份路径及 SHA；
- 旧/新 MCP stanza、旧/新工具集合和 namespace membership；
- 每层验证结果和回滚结果。

## 4. 路径解析与写入前检查

下面的变量只是本次 shell 会话的已解析值；不得把示例用户名写入配置：

```bash
set -euo pipefail

BLENDER_APP="/Applications/Blender.app"
BLENDER_BIN="$BLENDER_APP/Contents/MacOS/Blender"

if command -v codex >/dev/null 2>&1; then
  CODEX_BIN="$(command -v codex)"
elif [ -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]; then
  CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex"
else
  echo "STOP: Codex CLI not found" >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  UV_BIN="$(command -v uv)"
elif [ -x "$HOME/.local/bin/uv" ]; then
  UV_BIN="$HOME/.local/bin/uv"
else
  echo "STOP: uv not found" >&2
  exit 1
fi

CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
CODEX_CONFIG="$CODEX_ROOT/config.toml"
MCP_SOURCE_DIR="${MCP_SOURCE_DIR:-$HOME/.local/share/blender-lab-mcp/source}"

export BLENDER_APP BLENDER_BIN CODEX_BIN UV_BIN CODEX_ROOT CODEX_CONFIG MCP_SOURCE_DIR
```

Run preflight:

```bash
test "$(uname -s)" = "Darwin"
test "$(uname -m)" = "arm64"
test -x "$BLENDER_BIN"
test -x "$CODEX_BIN"
test -x "$UV_BIN"
git --version
"$UV_BIN" --version
"$CODEX_BIN" --version
"$BLENDER_BIN" --background --factory-startup --python-expr \
  'import bpy, platform; print({"version": bpy.app.version, "machine": platform.machine()}); assert bpy.app.version >= (5, 2, 0); assert platform.machine() == "arm64"'
```

Expected: 所有命令 exit 0，最后输出版本元组且断言通过。

停止条件：平台不符、Blender `<5.2`、工具缺失、目标 checkout 是 symlink、
checkout 不由当前 UID 所有、Codex config 不是当前 UID 所有的普通非 symlink
文件，或 TOML 无法解析。缺失的 config 可作为新文件创建，但其父目录必须为
当前 UID 所有且不是 symlink。

用 Python 3.13 验证现有 Codex config，不打印内容：

```bash
"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
import os
import stat
import tomllib
from pathlib import Path

path = Path(os.environ["CODEX_CONFIG"])
if path.exists():
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and not path.is_symlink()
    assert info.st_uid == os.getuid()
    tomllib.loads(path.read_text(encoding="utf-8"))
print("codex-config-preflight=ok")
PY
```

## 5. No-op 判定

先检查，后决定是否写入：

- checkout 已处于固定 commit 且 clean：不 fetch、不 checkout；
- 已安装 Extension 的 ID、version 和文件内容与固定来源一致且已启用：不重装；
- Online Access、autostart、host 和 port 已正确：不写 `userpref.blend`；
- `codex mcp get blender --json`、真实 Server catalog 和 direct namespace 已正确：
  不写 config，也不为该 no-op 创建重复备份。

若 Blender 正在运行且必须写偏好，要求用户保存并正常退出，然后确认无 Blender
进程。不得 `kill -9`，不得在运行中的 GUI 旁边另启 CLI 写偏好：

```bash
if pgrep -x Blender >/dev/null 2>&1; then
  echo "STOP: save and quit Blender normally before preference changes" >&2
  exit 1
fi
```

## 6. 备份合同

只为将要修改的对象创建一次备份。对象不存在时也要把 pre-state 明确记录为
`absent`；这不是可跳过的空值，而是首次安装回滚必须恢复的状态。先建立受限
目录：

```bash
umask 077
BACKUP_PARENT="$HOME/Library/Application Support/BlenderMCPInstallBackups"
install -d -m 700 "$BACKUP_PARENT"
BACKUP_ROOT="$(mktemp -d "$BACKUP_PARENT/run.XXXXXX")"
chmod 700 "$BACKUP_ROOT"
export BACKUP_ROOT
```

对将修改的普通文件执行 `cp -p`，随后 `chmod 600` 并记录
`stat -f '%d %i %p %u'` 与 `shasum -a 256`。例如：

```bash
if [ -f "$CODEX_CONFIG" ]; then
  cp -p "$CODEX_CONFIG" "$BACKUP_ROOT/config.toml.pre"
  chmod 600 "$BACKUP_ROOT/config.toml.pre"
  stat -f '%d %i %p %u' "$CODEX_CONFIG" "$BACKUP_ROOT/config.toml.pre"
  shasum -a 256 "$CODEX_CONFIG" "$BACKUP_ROOT/config.toml.pre"
fi
```

从 Blender 精确版本的用户资源路径解析 `userpref.blend`，不要假设版本目录名。
如果即将写偏好，备份存在的文件：

```bash
BLENDER_VERSION="$($BLENDER_BIN --background --factory-startup --python-expr 'import bpy; print("%d.%d" % bpy.app.version[:2])' 2>&1 | awk '/^[0-9]+\.[0-9]+$/{print; exit}')"
BLENDER_USER_ROOT="$HOME/Library/Application Support/Blender/$BLENDER_VERSION"
USERPREF="$BLENDER_USER_ROOT/config/userpref.blend"
export BLENDER_VERSION BLENDER_USER_ROOT USERPREF

if [ -f "$USERPREF" ]; then
  cp -p "$USERPREF" "$BACKUP_ROOT/userpref.blend.pre"
  chmod 600 "$BACKUP_ROOT/userpref.blend.pre"
  stat -f '%d %i %p %u' "$USERPREF" "$BACKUP_ROOT/userpref.blend.pre"
  shasum -a 256 "$USERPREF" "$BACKUP_ROOT/userpref.blend.pre"
fi
```

只有真实安装/升级 Extension 时才备份现有扩展目录；内容一致的当前安装必须
跳过重装。目录备份使用 `ditto`，并记录源目录与备份目录的逐文件 SHA 清单。
若 Extension 目录或 `userpref.blend` 原本不存在，分别记录 `extension=absent` 或
`userpref=absent`，并记录本次创建后的 identity/SHA，供失败时只移除本次创建且
未被外部替换的对象。

每次写入前重新读取目标 device/inode/SHA；与记录不一致时停止，不覆盖并发
修改。

## 7. 固定源码与隔离 Server

新安装时创建父目录并 clone；已有 checkout 先验证所有权、非 symlink 和 clean：

```bash
UPSTREAM_URL="https://projects.blender.org/lab/blender_mcp.git"
PINNED_COMMIT="4309a39646e644261624bfcd2bca669b343b7621"
export UPSTREAM_URL PINNED_COMMIT

if [ ! -e "$MCP_SOURCE_DIR/.git" ]; then
  install -d -m 700 "$(dirname "$MCP_SOURCE_DIR")"
  git clone "$UPSTREAM_URL" "$MCP_SOURCE_DIR"
fi

test ! -L "$MCP_SOURCE_DIR"
test "$(stat -f '%u' "$MCP_SOURCE_DIR")" = "$(id -u)"
test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain)"

if [ "$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)" != "$PINNED_COMMIT" ]; then
  git -C "$MCP_SOURCE_DIR" fetch origin "$PINNED_COMMIT"
  git -C "$MCP_SOURCE_DIR" checkout --detach "$PINNED_COMMIT"
fi

test "$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)" = "$PINNED_COMMIT"
test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain)"
test ! -e "$MCP_SOURCE_DIR/uv.lock"
```

用真实 MCP handshake 读取 catalog；这一步不需要 Blender listener：

```bash
"$UV_BIN" run --quiet --no-project --python 3.13 \
  --with 'mcp[cli]>=1.2.0,<2' \
  --with-editable "$MCP_SOURCE_DIR/mcp" \
  python - <<'PY'
import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main() -> None:
    params = StdioServerParameters(
        command=os.environ["UV_BIN"],
        args=[
            "run", "--quiet", "--no-project", "--python", "3.13",
            "--with", "mcp[cli]>=1.2.0,<2",
            "--with-editable", os.path.join(os.environ["MCP_SOURCE_DIR"], "mcp"),
            "blender-mcp",
        ],
        env={"BLENDER_PATH": os.environ["BLENDER_BIN"]},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            names = [tool.name for tool in tools]
            assert names and len(names) == len(set(names))
            print(json.dumps(names, ensure_ascii=False))

asyncio.run(main())
PY
```

Expected for the pinned commit: exit 0 and exactly 26 unique names. Also run:

```bash
"$UV_BIN" run --quiet --no-project --python 3.13 \
  --with 'mcp[cli]>=1.2.0,<2' \
  --with-editable "$MCP_SOURCE_DIR/mcp" \
  python -c 'import mcp; from importlib.metadata import version; from mcp.server.fastmcp import FastMCP; print(version("mcp")); assert int(version("mcp").split(".", 1)[0]) < 2'
```

Expected: SDK version major `<2` and `FastMCP` imports successfully. The checkout must
still be clean and contain no generated `uv.lock`.

## 8. Blender Extension：安装、启用与 Online Access

Source directory:

```bash
EXT_SOURCE="$MCP_SOURCE_DIR/addon/blender_mcp_addon"
EXT_MODULE="bl_ext.user_default.mcp"
EXT_INSTALLED="$BLENDER_USER_ROOT/extensions/user_default/mcp"
export EXT_SOURCE EXT_MODULE EXT_INSTALLED
```

先用 manifest 和逐文件比较判定是否已是目标内容。允许忽略运行生成的
`__pycache__`；其他差异意味着升级。已安装且一致时跳过本节的 build/install，
但仍检查启用状态和 Online Access。

新安装或升级必须在 Blender 正常退出后执行：

```bash
BUILD_DIR="$(mktemp -d)"
EXT_ZIP="$BUILD_DIR/mcp-1.0.0.zip"
"$BLENDER_BIN" --command extension validate "$EXT_SOURCE"
"$BLENDER_BIN" --command extension build \
  --source-dir "$EXT_SOURCE" \
  --output-filepath "$EXT_ZIP"
"$BLENDER_BIN" --command extension validate "$EXT_ZIP"
unzip -p "$EXT_ZIP" blender_manifest.toml | \
  "$UV_BIN" run --quiet --no-project --python 3.13 python -c \
  'import sys,tomllib; d=tomllib.loads(sys.stdin.read()); assert d["id"]=="mcp"; assert d["version"]=="1.0.0"; assert tuple(map(int,d["blender_version_min"].split("."))) <= (5,2,0); print("manifest=ok")'
"$BLENDER_BIN" --command extension install-file -r user_default -e "$EXT_ZIP"
```

不要只信最后一条命令的 exit code。随后必须确认 installed manifest、Extension
列表、启用模块和文件树。任一不一致即视为安装失败并从备份回滚。

在 `userpref.blend` 已备份、Blender 已退出且写前 SHA/inode 未变化后，开启
Online Access、固定 host/port、启用 autostart，并保存偏好：

```bash
"$BLENDER_BIN" --background --python-expr '
import bpy
module = "bl_ext.user_default.mcp"
if module not in bpy.context.preferences.addons:
    result = bpy.ops.preferences.addon_enable(module=module)
    assert result == {"FINISHED"}, result
system = bpy.context.preferences.system
system.use_online_access = True
prefs = bpy.context.preferences.addons[module].preferences
prefs.host = "localhost"
prefs.port = 9876
prefs.use_autostart = True
result = bpy.ops.wm.save_userpref()
assert result == {"FINISHED"}, result
print("preferences-saved=ok")
'
```

重新启动一个正常读取用户偏好的 Blender 进程核验。`bpy.app.online_access` 只有
重启后才反映保存的 Online Access：

```bash
"$BLENDER_BIN" --background --python-expr '
import bpy
module = "bl_ext.user_default.mcp"
assert bpy.app.version >= (5, 2, 0)
assert bpy.context.preferences.system.use_online_access
assert bpy.app.online_access
assert module in bpy.context.preferences.addons
prefs = bpy.context.preferences.addons[module].preferences
assert prefs.host == "localhost"
assert prefs.port == 9876
assert prefs.use_autostart
print("blender-preferences=ok")
'
```

## 9. Codex 配置的安全修改

先执行：

```bash
"$CODEX_BIN" mcp get blender --json
```

不存在 entry 时可用 `codex mcp add` 创建 transport 骨架；存在 entry 时不得先
remove。LLM 必须解析 TOML、只修改 `[mcp_servers.blender]`、其 `env`，并集合式
合并 `features.code_mode.direct_only_tool_namespaces` 中的 `mcp__blender`。保留其他
配置、注释和成员。

目标语义如下。路径值取第 4 节已解析变量的实际绝对路径；`enabled_tools` 取第
7 节真实 handshake 返回的完整、唯一字符串数组，不能复制过期清单：

| TOML key | 精确目标值 |
|---|---|
| `mcp_servers.blender.command` | 已解析的 `UV_BIN` 绝对路径 |
| `mcp_servers.blender.args` | `run`, `--quiet`, `--no-project`, `--python`, `3.13`, `--with`, `mcp[cli]>=1.2.0,<2`, `--with-editable`, 已解析的 `MCP_SOURCE_DIR/mcp` 绝对路径, `blender-mcp` |
| `mcp_servers.blender.omit_tools_from` | 空数组 |
| `mcp_servers.blender.startup_timeout_sec` | `20.0` |
| `mcp_servers.blender.tool_timeout_sec` | `60.0` |
| `mcp_servers.blender.default_tools_approval_mode` | `approve` |
| `mcp_servers.blender.enabled_tools` | 本次真实 Server catalog 的完整字符串数组 |
| `mcp_servers.blender.env.BLENDER_PATH` | 已解析的 `BLENDER_BIN` 绝对路径 |

`disabled_tools` 和逐工具 override 必须不存在。direct namespace 的目标成员是：

```toml
[features.code_mode]
direct_only_tool_namespaces = ["mcp__blender"]
```

如果该数组已有其他成员，只添加缺失的 `mcp__blender`，不得替换整个数组。

写入流程：

1. 记录原文件 bytes、mode、device、inode 和 SHA；
2. 备份并验证备份 SHA；
3. 写入前重验原文件 identity 和 SHA；
4. 在同目录创建 mode `0600` 的临时文件；
5. 用 Python 3.13 `tomllib.loads()` 验证临时文件；
6. 原子 `replace`；
7. 重读并再次解析，记录 post-SHA；
8. 运行 `codex mcp get blender --json` 精确验证 transport、args、env、timeouts
   和工具集合。

检测到并发变化立即停止。不得使用
`codex --strict-config mcp get`；当前 Codex CLI 不支持该组合。

## 10. 四层验收

### 10.1 配置存在且精确

`codex mcp get blender --json` 必须显示：enabled、stdio、绝对 uv 路径、
`--no-project`、Python 3.13、SDK `<2`、固定 checkout、Blender 绝对路径、
20/60 秒 timeout 和真实 catalog 全集。

### 10.2 Server running 和目录一致

启动或重新加载 Codex 后，用 App Server 验证 effective config 和 host 目录。以下
脚本只输出目标 Server 的状态和工具名，不输出完整 config：

```bash
REPO_CWD="$(pwd)"
export REPO_CWD
"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
import json
import os
import selectors
import subprocess
import time

proc = subprocess.Popen(
    [os.environ["CODEX_BIN"], "app-server", "--stdio"],
    cwd=os.environ["REPO_CWD"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    bufsize=1,
)
assert proc.stdin is not None and proc.stdout is not None
selector = selectors.DefaultSelector()
selector.register(proc.stdout, selectors.EVENT_READ)

def request(request_id: int, method: str, params: dict) -> dict:
    proc.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
    proc.stdin.flush()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for key, _ in selector.select(timeout=0.5):
            message = json.loads(key.fileobj.readline())
            if message.get("id") == request_id:
                assert "error" not in message, message
                return message["result"]
    raise TimeoutError(method)

try:
    request(1, "initialize", {"clientInfo": {"name": "blender-mcp-install-verifier", "version": "1"}})
    config = request(2, "config/read", {"cwd": os.environ["REPO_CWD"], "includeLayers": False})
    status = request(3, "mcpServerStatus/list", {"cursor": None, "limit": 100, "threadId": None, "detail": "toolsAndAuthOnly"})
    assert "blender" in config["config"]["mcp_servers"]
    server = next(item for item in status["data"] if item["name"] == "blender")
    tools = sorted(tool["name"] for tool in server["tools"])
    assert tools and len(tools) == len(set(tools))
    print(json.dumps({"name": server["name"], "tools": tools}, ensure_ascii=False))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
PY
```

Expected for the pinned commit: `name=blender` and exactly the same 26 tools as the
Server handshake and `enabled_tools`.

### 10.3 Blender listener 可达

用正常 GUI 的 autostart，或完整 CLI fallback 启动 bridge。CLI fallback：

```bash
"$BLENDER_BIN" --online-mode --command blender_mcp
```

在另一 shell 中轮询 `localhost:9876`；只检查连接，不发送写操作：

```bash
"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
import socket
import time

deadline = time.monotonic() + 30
while True:
    try:
        with socket.create_connection(("localhost", 9876), timeout=1):
            print("listener=ok")
            break
    except OSError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.5)
PY
```

### 10.4 新任务模型目录与安全只读调用

重启 Codex Desktop 或开启 fresh/reloaded task，确认模型实际看到与 Server
catalog 全等的官方 `mcp__blender` 工具。配置文本或 App Server 状态不能替代这
一层。

只调用：

```text
mcp__blender__get_blendfile_summary_datablocks
```

Expected: 返回当前 Blender 文件的结构化 data-block summary。不得在安装 smoke
中调用 `execute_blender_code*`、`render_*` 或 screenshot 长序列。

四层全部通过才可报告安装成功。Codex Desktop 加载新 MCP 配置通常需要重启或
新任务；未重载不能误报失败。

## 11. 当前机器快速修复分支

若以下事实全部成立：固定 checkout clean、官方 Extension ID/version/文件内容
一致且已启用、Codex stanza 和 26 工具集合准确，唯一失败为 Online Access
关闭，则：

1. 不 fetch checkout；
2. 不重装 Extension；
3. 不重写 Codex config，不创建 config 重复备份；
4. 用户保存并正常退出 Blender；
5. 只备份 `userpref.blend`；
6. 执行第 8 节的 preference 写入和重读；
7. 重启 Blender/Codex，完成第 10 节四层验收。

## 12. 显式上游更新与自动接受工具

不得在 Server 每次启动时自动更新。只有用户明确启动更新流程时：

1. 读取远端 `main` 的完整 commit，记录旧 commit 和旧 catalog；
2. 在新的临时 checkout 中检出候选 commit，不先移动 live checkout；
3. 用第 7 节的隔离 SDK handshake 获取候选 catalog，要求名称非空且唯一；
4. 构建并 validate 候选 Extension；
5. 显示 `old_commit -> candidate_commit` 以及工具 added/removed/renamed diff；
6. 当前所有者已授权自动接受该完整候选 catalog，不逐工具询问；
7. Blender 正常退出后，备份 Extension/userpref/config；记录 live checkout 的
   目录 device/inode、clean 状态和旧 commit 作为 source pre-image；
8. 写入前重验 live checkout 的 device/inode、HEAD 和 clean 状态。全部仍等于
   pre-image 后，在 live checkout fetch 候选完整 SHA 并执行 detached checkout；
   断言 live `HEAD` 等于候选 SHA、worktree clean，且 Server handshake 返回候选
   catalog；
9. 安装候选 Extension，把 `enabled_tools` 原子替换为候选 catalog 的精确集合，
   包括新增、删除和重命名；
10. 运行四层验收，要求 live candidate Server catalog、effective config 和新任务模型
   目录三者集合全等；
11. 成功后把候选完整 SHA 记录为新 pin；失败则先重验 live checkout 的
    device/inode、`HEAD` 仍等于候选 SHA 且 worktree clean；任一变化都停止，全部
    匹配才 detached checkout 旧 commit，并恢复 Extension、
    userpref、config 和旧 catalog。

若候选引入非唯一/空 catalog、Server 无法握手、Extension validate 失败或 Blender
`>=5.2` smoke 失败，停止更新，保持旧 pin。

## 13. 回滚

Codex config：

- 当前 SHA 等于本次记录的 post-SHA：可在同目录 mode `0600` 临时文件中写入
  完整 pre-image，解析后原子恢复；
- 当前 SHA 已变化：禁止整文件覆盖，只做三方/手术式恢复原 `blender` stanza 和
  本次新增的 `mcp__blender` membership；
- 原 stanza 不存在：只删除本次创建的 stanza；原 stanza 存在：恢复原值，不能
  用简单 `mcp remove` 代替。

Blender：

- 关闭 Blender；
- 原 Extension 存在时，从已验证备份恢复；原 Extension 为 `absent` 时，先验证
  当前目录仍是本次安装的 ID/version/文件树且 identity 未变，再执行
  `"$BLENDER_BIN" --command extension remove --no-prefs user_default.mcp` 并验证目录和模块
  均不存在；若目录已被外部替换则停止，不删除；
- 原 `userpref.blend` 存在时恢复已验证备份；原状态为 `absent` 时，仅当当前文件
  identity/SHA 等于本次记录的 post-image 才删除该文件，变化时停止；
- 重新启动并核验旧 ID/version、启用状态和偏好；
- 不删除或修改任何 `.blend` 文件。

Source/runtime：

- 恢复记录的旧完整 commit 和旧 catalog；
- 不删除 checkout 中用户新增内容，不清理共享 uv cache；
- 回滚后重复第 10 节四层验收。

## 14. 常见问题判定

- `~/.local/bin` 不在 PATH：不是 Server 故障；使用已解析的 uv 绝对路径。
- `blender_org` cache 缺失但本地 Extension 命令 exit 0：是非阻断警告；仍以
  manifest、文件树、启用状态和实际加载后置检查为准。
- `No MCP server named blender`：若目标本应存在，是配置层失败；若发生在明确
  回滚删除后的负向检查，是预期结果。
- listener 不可达且 `bpy.app.online_access=false`：先按备份合同修复 Online
  Access，不要重装内容一致的 Extension。
- 原始手写 JSON-RPC smoke 失败但官方 MCP SDK Client 成功：验证器有误，不代表
  安装失败；目录和调用验证使用官方 ClientSession。
- GUI 自动化无法读取窗口：改用完整 CLI 路径和 socket/App Server 后置验证，
  不把 UI 可访问性当成唯一门槛。
````

- [ ] **Step 3: 运行手册合同 GREEN 检查**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("docs/install-official-blender-mcp.md")
text = path.read_text(encoding="utf-8")
required = (
    "LLM 执行安装手册",
    "Blender：`>=5.2`",
    "4309a39646e644261624bfcd2bca669b343b7621",
    "mcp[cli]>=1.2.0,<2",
    "localhost:9876",
    "Online Access",
    "default_tools_approval_mode",
    "mcpServerStatus/list",
    "get_blendfile_summary_datablocks",
    "当前 Codex CLI 不支持",
    "显式上游更新与自动接受工具",
    "当前机器快速修复分支",
    "回滚",
)
for marker in required:
    assert marker in text, marker
for forbidden in (
    "/Users/yeminjie",
    '"$CODEX_BIN" --strict-config',
    "blender-codex-server =",
):
    assert forbidden not in text, forbidden
assert text.count("```bash") >= 10
print("manual-contract=ok")
PY
git diff --check
```

Expected: `manual-contract=ok` and `git diff --check` exit 0.

- [ ] **Step 4: 审查精准范围并提交手册**

Run:

```bash
git diff --stat
git diff -- docs/install-official-blender-mcp.md
git status --short
git add docs/install-official-blender-mcp.md
git commit -m "docs: add official Blender MCP LLM install guide"
```

Expected: only `docs/install-official-blender-mcp.md` is added by this task; commit succeeds.

---

## Task 2: 对当前机器执行备份与最小修复

**Files:**
- Read: `docs/install-official-blender-mcp.md`
- External read/write: resolved Codex config and Blender 5.2 `userpref.blend`
- External read-only: `/Users/yeminjie/blender_mcp` only after resolving it as the current checkout
- Evidence report: `.superpowers/sdd/official-blender-mcp-current-repair.md` (ignored operational record; do not commit)

- [ ] **Step 1: 写入 repair report 的 preflight 基线**

Run all read-only preflight/no-op checks from manual §§4–7 and record only sanitized facts in
`.superpowers/sdd/official-blender-mcp-current-repair.md`:

```text
platform/version:
resolved executables:
checkout HEAD/clean/no uv.lock:
SDK version/FastMCP import/catalog count:
Extension id/version/enabled/content comparison:
Online Access/autostart/host/port:
Codex entry/catalog/direct namespace:
Blender process state:
planned writes:
```

Expected current facts: arm64; Blender 5.2+; checkout at the fixed commit and clean; SDK major
`<2`; 26 unique tools; official Extension already installed/enabled and source-equivalent;
Codex entry has the expected catalog/direct namespace and may need only the pinned
`--python`, `3.13` args added after `--no-project`; Online Access is false. Any additional
conflicting fact must be investigated before mutation and recorded as a concern.

- [ ] **Step 2: 若 Blender 正在运行，正常退出而不强制终止**

First run:

```bash
pgrep -fl '/Blender.app/Contents/MacOS/Blender|^Blender$' || true
```

If no process is present, continue. If Blender is running, use an available UI control channel to
request normal quit. If Blender presents an unsaved-file dialog, stop and ask the user to choose;
do not discard, overwrite, or save a `.blend` file without an explicit file decision. Continue only
after `pgrep` returns no Blender process.

- [ ] **Step 3: 备份将修改的 `userpref.blend` 和非精确 Codex config**

Use manual §6. The repair report must record backup directory, source and backup SHA-256, mode,
device/inode, and the source pre-SHA immediately before write. Always back up the preference file
because Online Access requires a write. If the only Codex drift is the missing `--python`, `3.13`
pair, also back up the full config bytes and record its pre-SHA/device/inode without printing the
file. Do not reinstall the source-equivalent Extension.

Expected: backup directory mode `0700`, file backup mode `0600`, backup SHA equals source
pre-SHA, and source identity/SHA is unchanged immediately before write.

- [ ] **Step 4: 开启 Online Access 并保存固定的安全监听设置**

Run the exact Blender preference writer from manual §8. Then relaunch the exact read-only verifier
from that section.

Expected:

```text
preferences-saved=ok
blender-preferences=ok
```

Record the new `userpref.blend` SHA. Confirm it differs from pre-SHA, backup remains byte-identical,
official Extension is still enabled, `host=localhost`, `port=9876`, and autostart is true.

- [ ] **Step 5: 原子补齐 Codex 的 Python 3.13 pin**

Only when preflight proves every other `blender` stanza field, 26-tool catalog and direct namespace
is exact, add the two args `--python`, `3.13` immediately after `--no-project`. Follow manual §9:
parse the pre-image, revalidate device/inode/SHA, write a same-directory mode `0600` temporary file,
parse it, atomically replace the target, parse again, and record post-SHA. Preserve all unrelated
tables, keys and existing array members. Do not remove/re-add the MCP entry.

Run `"$CODEX_BIN" mcp get blender --json` and a Python 3.13 `tomllib` checker. Expected: the args
contain exactly one `--python`, `3.13` pair in the required position; all other target values equal
their pre-image; 26-tool catalog, approval, omit list and direct namespace remain exact.

- [ ] **Step 6: 失败时按 identity-aware 规则回滚**

If Step 4 fails and current `userpref.blend` SHA equals the recorded post-image or no successful
post-image exists, restore the verified pre-image while Blender is closed, then rerun the preference
read-only check. If current SHA changed unexpectedly, stop instead of overwriting it and report the
concurrent modification. If Step 5 fails and current config SHA equals the recorded post-image,
atomically restore the verified config pre-image after parsing it; if the SHA changed, stop and use
manual §13 surgical rollback rather than overwriting concurrent work.

Expected after rollback: backup/source SHA relationship is documented and no user `.blend` file was
touched.

---

## Task 3: 执行真实连接、目录与只读调用验收

**Files:**
- Read: `docs/install-official-blender-mcp.md`
- Append evidence: `.superpowers/sdd/official-blender-mcp-current-repair.md`
- External process state: official Blender/Codex processes only

- [ ] **Step 1: 启动官方 Blender bridge 并验证 listener**

Prefer a normal Blender GUI start so autostart is exercised. If UI automation remains unavailable,
use the exact `--online-mode --command blender_mcp` fallback from manual §10.3. Do not load, save or
modify a user `.blend` file for the smoke.

Run the listener poll from manual §10.3.

Expected: `listener=ok` within 30 seconds. Record which start path was used and the process PID.

- [ ] **Step 2: 验证 Codex effective config 与 host catalog**

Run:

```bash
"$CODEX_BIN" mcp get blender --json
```

Then run the complete App Server verifier from manual §10.2.

Expected: entry is enabled, transport/args/env/timeouts are exact, host status contains `blender`,
and its 26 unique tools set-equals both the direct Server handshake and `enabled_tools`.

- [ ] **Step 3: 通过官方 MCP 通道执行唯一安全只读 smoke**

From a fresh/reloaded task or a direct official MCP SDK client connected through the configured
Server, call only:

```text
mcp__blender__get_blendfile_summary_datablocks
```

Expected: structured Blender file data-block summary. Do not call arbitrary Python, render or
screenshot tools. Record success/failure, returned top-level shape, and elapsed time without copying
private scene contents into the report.

- [ ] **Step 4: 验证更新合同但不移动当前 pin**

Run a read-only `git ls-remote` for upstream `refs/heads/main`. If it equals the pinned commit, record
`upstream-update=no-op`. If it differs, do not update during this current repair; record candidate
SHA and verify that manual §12 contains temporary-checkout validation, full catalog replacement,
tool diff, new pin, four-layer validation, and rollback requirements.

Expected: current live checkout remains at the fixed commit and clean.

- [ ] **Step 5: 正常结束测试进程并记录最终状态**

If a CLI fallback process was started only for the smoke, request graceful termination and confirm
port 9876 closes. If a normal GUI was intentionally started for the user, leave it running and state
that explicitly. Do not terminate an unrelated pre-existing process.

Append final outcomes to the repair report:

```text
configuration layer:
server/catalog layer:
listener layer:
fresh-model/read-only-call layer:
backup and rollback readiness:
remaining warnings:
final process state:
```

Expected: all four success layers pass or a precise blocker and rollback state is documented.

---

## Task 4: 整体审查与交付核验

**Files:**
- Review: `docs/install-official-blender-mcp.md`
- Review: `docs/superpowers/specs/2026-08-09-official-blender-mcp-llm-install-design.md`
- Review: `.superpowers/sdd/official-blender-mcp-current-repair.md`

- [ ] **Step 1: 运行文档合同、冻结范围和仓库卫生检查**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path("docs/install-official-blender-mcp.md")
text = path.read_text(encoding="utf-8")
required = (
    "LLM 执行安装手册",
    "Blender：`>=5.2`",
    "4309a39646e644261624bfcd2bca669b343b7621",
    "mcp[cli]>=1.2.0,<2",
    "localhost:9876",
    "Online Access",
    "mcpServerStatus/list",
    "当前机器快速修复分支",
    "显式上游更新与自动接受工具",
    "回滚",
)
assert all(marker in text for marker in required)
assert "/Users/yeminjie" not in text
assert '"$CODEX_BIN" --strict-config' not in text
print("manual-contract=ok")
PY
git diff --check
git status --short --branch
git diff --name-only HEAD~1..HEAD
```

Expected: manual contract and diff check pass; the implementation commit contains only the new
manual; no frozen file, test count or product version changed.

- [ ] **Step 2: 独立核对 repair report 的证据闭环**

Confirm the report has: exact version/architecture, source pin and clean status, backup paths and
hashes, Online Access post-state, Extension enable/host/port state, SDK `<2`, 26/26 set equality,
Codex entry check, App Server running check, listener check, safe read-only call result, upstream
no-op/candidate state, and final process state.

Expected: no secrets or private scene contents in the report; no claim relies only on a CLI exit
code; failures have an explicit rollback outcome.

- [ ] **Step 3: 运行最终代码审查并修复所有 Critical/Important 问题**

Generate a review package from the feature-branch base through HEAD, dispatch the Superpowers final
reviewer, and include the design, this task brief, implementation report and repair report paths.

Expected: final reviewer returns both spec-compliance and quality approval. Re-run the documentation
contract and only the checks covering any review fix before re-review.

- [ ] **Step 4: 交付最终结果**

Report concisely:

- added manual path and commit;
- whether current machine was changed or was a no-op per component;
- backup path and verified rollback readiness;
- Blender/SDK/source/Codex/26-tool/listener/read-only-call results;
- remaining known risks, especially arbitrary Python, unauthenticated localhost TCP, online-only
  dependency resolution and Blender `>5.2` compatibility needing per-version smoke;
- whether Blender was left running.

Do not call the frozen ROADMAP complete and do not add this operational run to historical evidence.
