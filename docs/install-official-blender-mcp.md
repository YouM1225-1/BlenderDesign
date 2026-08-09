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
case "$MCP_SOURCE_DIR" in
  /*) ;;
  *) echo "STOP: MCP_SOURCE_DIR must be absolute" >&2; exit 1 ;;
esac

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
try:
    info = path.lstat()
except FileNotFoundError:
    root = Path(os.environ["CODEX_ROOT"])
    info = root.lstat()
    assert stat.S_ISDIR(info.st_mode) and not root.is_symlink()
    assert info.st_uid == os.getuid()
    print("config=absent")
else:
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
- 第 9 节的安全 probe 将 MCP entry 分类为 `present`，且捕获的
  `codex mcp get blender --json`、真实 Server catalog 和 direct namespace 已正确：
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
revalidate_config_image() {
  test ! -L "$CODEX_CONFIG"
  test -f "$CODEX_CONFIG"
  test "$(stat -f '%u' "$CODEX_CONFIG")" = "$(id -u)"
  test "$(stat -f '%d %i' "$CODEX_CONFIG")" = "$1"
  test "$(shasum -a 256 "$CODEX_CONFIG" | awk '{print $1}')" = "$2"
}

record_config_post_image() {
  test ! -L "$CODEX_CONFIG"
  test -f "$CODEX_CONFIG"
  test "$(stat -f '%u' "$CODEX_CONFIG")" = "$(id -u)"
  CONFIG_LAST_STAGE="$1"
  CONFIG_LAST_IDENTITY="$(stat -f '%d %i' "$CODEX_CONFIG")"
  CONFIG_LAST_SHA="$(shasum -a 256 "$CODEX_CONFIG" | awk '{print $1}')"
  printf '%s\t%s\t%s\n' "$CONFIG_LAST_STAGE" "$CONFIG_LAST_IDENTITY" \
    "$CONFIG_LAST_SHA" >> "$BACKUP_ROOT/config-post-images"
  chmod 600 "$BACKUP_ROOT/config-post-images"
  export CONFIG_LAST_STAGE CONFIG_LAST_IDENTITY CONFIG_LAST_SHA
}

CONFIG_PRE_IDENTITY=""
CONFIG_PRE_SHA=""
CONFIG_PARENT_IDENTITY=""
CONFIG_CREATED_IDENTITY=""
CONFIG_CREATED_SHA=""
CONFIG_POST_IDENTITY=""
CONFIG_POST_SHA=""
CONFIG_ADD_EXIT=""
if [ -f "$CODEX_CONFIG" ]; then
  CONFIG_PRESTATE=present
  CONFIG_PRE_IDENTITY="$(stat -f '%d %i' "$CODEX_CONFIG")"
  CONFIG_PRE_SHA="$(shasum -a 256 "$CODEX_CONFIG" | awk '{print $1}')"
  cp -p "$CODEX_CONFIG" "$BACKUP_ROOT/config.toml.pre"
  chmod 600 "$BACKUP_ROOT/config.toml.pre"
  stat -f '%d %i %p %u' "$CODEX_CONFIG" "$BACKUP_ROOT/config.toml.pre"
  shasum -a 256 "$CODEX_CONFIG" "$BACKUP_ROOT/config.toml.pre"
else
  CONFIG_PRESTATE=absent
  CONFIG_PARENT_IDENTITY="$(stat -f '%d %i' "$CODEX_ROOT")"
  printf '%s\n' "config=absent" >> "$BACKUP_ROOT/prestates"
fi
CONFIG_LAST_STAGE="$CONFIG_PRESTATE"
CONFIG_LAST_IDENTITY="$CONFIG_PRE_IDENTITY"
CONFIG_LAST_SHA="$CONFIG_PRE_SHA"
export CONFIG_PRESTATE CONFIG_PRE_IDENTITY CONFIG_PRE_SHA CONFIG_PARENT_IDENTITY
export CONFIG_LAST_STAGE CONFIG_LAST_IDENTITY CONFIG_LAST_SHA
export CONFIG_CREATED_IDENTITY CONFIG_CREATED_SHA CONFIG_POST_IDENTITY CONFIG_POST_SHA
export CONFIG_ADD_EXIT
```

从 Blender 精确版本的用户资源路径解析 `userpref.blend`，不要假设版本目录名。
如果即将写偏好，备份存在的文件：

```bash
BLENDER_VERSION="$($BLENDER_BIN --background --factory-startup --python-expr 'import bpy; print("%d.%d" % bpy.app.version[:2])' 2>&1 | awk '/^[0-9]+\.[0-9]+$/{print; exit}')"
BLENDER_RESOURCE_BOUNDARY="$HOME/Library/Application Support/Blender"
BLENDER_USER_ROOT="$HOME/Library/Application Support/Blender/$BLENDER_VERSION"
USERPREF="$BLENDER_USER_ROOT/config/userpref.blend"
EXT_INSTALLED="$BLENDER_USER_ROOT/extensions/user_default/mcp"
export BLENDER_VERSION BLENDER_RESOURCE_BOUNDARY BLENDER_USER_ROOT USERPREF EXT_INSTALLED

snapshot_blender_target() {
  "$UV_BIN" run --quiet --no-project --python 3.13 python - "$BLENDER_RESOURCE_BOUNDARY" "$1" "$2" <<'PY'
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

boundary = Path(os.path.abspath(sys.argv[1]))
target = Path(os.path.abspath(sys.argv[2]))
kind = sys.argv[3]
uid = os.getuid()
assert kind in {"file", "directory"}
assert target != boundary and target.is_relative_to(boundary)

def directory_info(path: Path):
    info = os.lstat(path)
    assert stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
    assert info.st_uid == uid
    return info

anchor = boundary
directory_info(anchor)
for part in target.relative_to(boundary).parts[:-1]:
    candidate = anchor / part
    try:
        directory_info(candidate)
    except FileNotFoundError:
        break
    anchor = candidate

try:
    info = os.lstat(target)
except FileNotFoundError:
    anchor_info = directory_info(anchor)
    print(json.dumps({"state": "absent", "anchor": str(anchor),
                      "anchor_identity": [anchor_info.st_dev, anchor_info.st_ino]}, sort_keys=True))
    raise SystemExit

assert not stat.S_ISLNK(info.st_mode) and info.st_uid == uid
assert stat.S_ISREG(info.st_mode) if kind == "file" else stat.S_ISDIR(info.st_mode)
record = {"state": "present", "target_identity": [info.st_dev, info.st_ino]}
if kind == "file":
    record["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
else:
    digest = hashlib.sha256()
    for root, directories, files in os.walk(target, followlinks=False):
        directories.sort()
        files.sort()
        for name in directories + files:
            path = Path(root, name)
            item = os.lstat(path)
            assert not stat.S_ISLNK(item.st_mode)
            relative = path.relative_to(target).as_posix()
            digest.update(f"{relative}\0{stat.S_IFMT(item.st_mode):o}\0".encode())
            if stat.S_ISREG(item.st_mode):
                digest.update(hashlib.sha256(path.read_bytes()).digest())
    record["tree_sha256"] = digest.hexdigest()
    manifest = target / "blender_manifest.toml"
    if manifest.is_file() and not manifest.is_symlink():
        record["manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
print(json.dumps(record, sort_keys=True))
PY
}

revalidate_blender_target() {
  current="$(mktemp "$BACKUP_ROOT/$3.now.XXXXXX")"
  expected="${4:-$BACKUP_ROOT/$3.pre.json}"
  chmod 600 "$current"
  snapshot_blender_target "$1" "$2" > "$current"
  if ! cmp -s "$current" "$expected"; then
    echo "STOP: $3 target identity/content drift" >&2
    unlink "$current"
    exit 1
  fi
  unlink "$current"
}

snapshot_blender_target "$USERPREF" file > "$BACKUP_ROOT/userpref.pre.json"
snapshot_blender_target "$EXT_INSTALLED" directory > "$BACKUP_ROOT/extension.pre.json"
chmod 600 "$BACKUP_ROOT/userpref.pre.json" "$BACKUP_ROOT/extension.pre.json"
USERPREF_LAST_SNAPSHOT="$BACKUP_ROOT/userpref.pre.json"
EXTENSION_LAST_SNAPSHOT="$BACKUP_ROOT/extension.pre.json"
export USERPREF_LAST_SNAPSHOT EXTENSION_LAST_SNAPSHOT

if [ -e "$USERPREF" ]; then
  printf '%s\n' "userpref=present" >> "$BACKUP_ROOT/prestates"
else
  printf '%s\n' "userpref=absent" >> "$BACKUP_ROOT/prestates"
fi
if [ -e "$EXT_INSTALLED" ]; then
  printf '%s\n' "extension=present" >> "$BACKUP_ROOT/prestates"
else
  printf '%s\n' "extension=absent" >> "$BACKUP_ROOT/prestates"
fi
chmod 600 "$BACKUP_ROOT/prestates"

if [ -f "$USERPREF" ]; then
  cp -p "$USERPREF" "$BACKUP_ROOT/userpref.blend.pre"
  chmod 600 "$BACKUP_ROOT/userpref.blend.pre"
  stat -f '%d %i %p %u' "$USERPREF" "$BACKUP_ROOT/userpref.blend.pre"
  shasum -a 256 "$USERPREF" "$BACKUP_ROOT/userpref.blend.pre"
fi
```

只有真实安装/升级 Extension 时才备份现有扩展目录；内容一致的当前安装必须
跳过重装。目录备份使用 `ditto`，并记录源目录与备份目录的逐文件 SHA 清单。
上面的 `os.lstat` 检查不跟随 symlink：存在的 `userpref.blend` 必须是当前 UID
所有的普通文件，存在的 Extension 必须是当前 UID 所有的目录；目标不存在时，
则验证 Blender 用户资源边界内直到最近现存父目录的整条路径都是当前 UID 所有的
非 symlink 目录。快照记录目标或最近现存父目录的 device/inode；现有 Extension
还记录 manifest 和完整文件树 digest。

每次备份后、安装或写入前，调用 `revalidate_blender_target` 重新读取 identity、
SHA/manifest/tree digest；与对应 `.pre.json` 不一致时停止，不覆盖并发修改。若
某条安装命令会同时写 Extension 和偏好，两者都必须在该命令前重验，并在命令后
把各自新快照保存为下一次写入的基线。

## 7. 固定源码与隔离 Server

新安装时创建父目录并 clone；已有 checkout 先验证所有权、非 symlink 和 clean：

```bash
UPSTREAM_URL="https://projects.blender.org/lab/blender_mcp.git"
PINNED_COMMIT="4309a39646e644261624bfcd2bca669b343b7621"
PYTHONDONTWRITEBYTECODE=1
export UPSTREAM_URL PINNED_COMMIT PYTHONDONTWRITEBYTECODE

SOURCE_PARENT="$(dirname "$MCP_SOURCE_DIR")"

snapshot_source_parent() {
  "$UV_BIN" run --quiet --no-project --python 3.13 python - "$HOME" "$MCP_SOURCE_DIR" "$1" <<'PY'
import os
import stat
import sys
from pathlib import Path

home = Path(os.path.abspath(sys.argv[1]))
source = Path(os.path.abspath(sys.argv[2]))
require_parent = sys.argv[3] == "required"
uid = os.getuid()
assert source != home and source.is_relative_to(home)
parent = source.parent

def owned_directory(path: Path):
    info = os.lstat(path)
    assert stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
    assert info.st_uid == uid
    return info

current = home
info = owned_directory(current)
for part in parent.relative_to(home).parts:
    candidate = current / part
    try:
        info = owned_directory(candidate)
    except FileNotFoundError:
        assert not require_parent
        print("parent=absent")
        raise SystemExit
    current = candidate
assert current == parent
print(f"{info.st_dev} {info.st_ino}")
PY
}

revalidate_source_checkout() {
  test ! -L "$MCP_SOURCE_DIR"
  test -d "$MCP_SOURCE_DIR"
  test "$(stat -f '%u' "$MCP_SOURCE_DIR")" = "$(id -u)"
  test "$(stat -f '%d %i' "$MCP_SOURCE_DIR")" = "$1"
  test "$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)" = "$2"
  test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all)"
}

SOURCE_PARENT_IDENTITY=""
SOURCE_CREATED_IDENTITY=""
SOURCE_EXISTING_IDENTITY=""
SOURCE_OLD_COMMIT=""
SOURCE_EXISTING_CLEAN=""
snapshot_source_parent optional >/dev/null
if [ -L "$MCP_SOURCE_DIR" ]; then
  echo "STOP: source checkout is a symlink" >&2
  exit 1
elif [ -e "$MCP_SOURCE_DIR" ]; then
  SOURCE_PRESTATE=present
  test -d "$MCP_SOURCE_DIR/.git"
  SOURCE_EXISTING_IDENTITY="$(stat -f '%d %i' "$MCP_SOURCE_DIR")"
  SOURCE_OLD_COMMIT="$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)"
  test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all)"
  SOURCE_EXISTING_CLEAN=clean
else
  SOURCE_PRESTATE=absent
  printf '%s\n' "source=absent" >> "$BACKUP_ROOT/prestates"
  if [ ! -e "$SOURCE_PARENT" ]; then
    install -d -m 700 "$SOURCE_PARENT"
  fi
  SOURCE_PARENT_IDENTITY="$(snapshot_source_parent required)"
  test "$(snapshot_source_parent required)" = "$SOURCE_PARENT_IDENTITY"
  git clone "$UPSTREAM_URL" "$MCP_SOURCE_DIR"
  SOURCE_CREATED_IDENTITY="$(stat -f '%d %i' "$MCP_SOURCE_DIR")"
fi
export SOURCE_PRESTATE SOURCE_PARENT SOURCE_PARENT_IDENTITY SOURCE_CREATED_IDENTITY
export SOURCE_EXISTING_IDENTITY SOURCE_OLD_COMMIT

test ! -L "$MCP_SOURCE_DIR"
test "$(stat -f '%u' "$MCP_SOURCE_DIR")" = "$(id -u)"
SOURCE_WRITE_IDENTITY="$(stat -f '%d %i' "$MCP_SOURCE_DIR")"
SOURCE_WRITE_HEAD="$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)"
test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all)"
SOURCE_WRITE_CLEAN=clean

if [ "$SOURCE_WRITE_HEAD" != "$PINNED_COMMIT" ]; then
  revalidate_source_checkout "$SOURCE_WRITE_IDENTITY" "$SOURCE_WRITE_HEAD"
  git -C "$MCP_SOURCE_DIR" fetch origin "$PINNED_COMMIT"
  revalidate_source_checkout "$SOURCE_WRITE_IDENTITY" "$SOURCE_WRITE_HEAD"
  git -C "$MCP_SOURCE_DIR" checkout --detach "$PINNED_COMMIT"
fi

SOURCE_POST_IDENTITY="$(stat -f '%d %i' "$MCP_SOURCE_DIR")"
SOURCE_POST_HEAD="$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)"
test "$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)" = "$PINNED_COMMIT"
test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all)"
if [ "$SOURCE_PRESTATE" = absent ]; then
  test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all --ignored)"
fi
test ! -e "$MCP_SOURCE_DIR/uv.lock"
SOURCE_POST_CLEAN=clean
export SOURCE_WRITE_IDENTITY SOURCE_WRITE_HEAD SOURCE_WRITE_CLEAN
export SOURCE_POST_IDENTITY SOURCE_POST_HEAD SOURCE_POST_CLEAN SOURCE_EXISTING_CLEAN
```

`snapshot_source_parent` 用 `lstat` 验证从 `$HOME` 到 `SOURCE_PARENT` 的全部现存
祖先都是当前 UID 所有的非 symlink 目录，并把 `MCP_SOURCE_DIR` 词法限制在
`$HOME` 内；越界 override 直接停止。`source=absent` 分支在 clone 前记录并紧邻
重验父目录 identity，在 clone 后记录新目录 identity；`source=present` 分支记录
目录 identity、原完整 commit 和 clean 状态，并在 fetch、checkout 与 rollback 前
执行相同重验。两条分支的回滚合同不同，不得把首次创建描述为“恢复旧 commit”。

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
still be clean and contain no generated `uv.lock`. `SOURCE_PRESTATE=absent` 时还必须再次
要求以下命令无输出；`--ignored` 只检查 working tree，不把 `.git` 内部数据库当作
ignored 内容：

```bash
test ! -e "$MCP_SOURCE_DIR/uv.lock"
if [ "$SOURCE_PRESTATE" = absent ]; then
  test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all --ignored)"
fi
```

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
revalidate_blender_target "$EXT_INSTALLED" directory extension
revalidate_blender_target "$USERPREF" file userpref
if "$BLENDER_BIN" --command extension install-file -r user_default -e "$EXT_ZIP"; then
  EXT_INSTALL_EXIT=0
else
  EXT_INSTALL_EXIT=$?
fi

EXTENSION_POST_SNAPSHOT_OK=1
USERPREF_POST_SNAPSHOT_OK=1
if snapshot_blender_target "$EXT_INSTALLED" directory \
  > "$BACKUP_ROOT/extension.install-post.json"; then
  EXTENSION_POST_SNAPSHOT_OK=1
else
  EXTENSION_POST_SNAPSHOT_OK=0
fi
if snapshot_blender_target "$USERPREF" file \
  > "$BACKUP_ROOT/userpref.install-post.json"; then
  USERPREF_POST_SNAPSHOT_OK=1
else
  USERPREF_POST_SNAPSHOT_OK=0
fi

if [ "$EXTENSION_POST_SNAPSHOT_OK" != 1 ] || [ "$USERPREF_POST_SNAPSHOT_OK" != 1 ]; then
  printf '%s\n' "extension-install-exit=$EXT_INSTALL_EXIT state=unsafe-post-image" \
    >> "$BACKUP_ROOT/prestates"
  echo "STOP: post-install target is unsafe; do not overwrite; manual recovery required" >&2
  exit 1
fi
chmod 600 "$BACKUP_ROOT/extension.install-post.json" \
  "$BACKUP_ROOT/userpref.install-post.json"
EXTENSION_LAST_SNAPSHOT="$BACKUP_ROOT/extension.install-post.json"
USERPREF_LAST_SNAPSHOT="$BACKUP_ROOT/userpref.install-post.json"
export EXTENSION_LAST_SNAPSHOT USERPREF_LAST_SNAPSHOT
if [ "$EXT_INSTALL_EXIT" != 0 ]; then
  printf '%s\n' "extension-install-exit=$EXT_INSTALL_EXIT state=failed" \
    >> "$BACKUP_ROOT/prestates"
  echo "STOP: extension install failed; use section 13 rollback from recorded post-images" >&2
  exit 1
fi
printf '%s\n' "extension-install-exit=0 state=succeeded" >> "$BACKUP_ROOT/prestates"
EXTENSION_MUTATED=1
```

不要只信 install-file 的 exit code。conditional 无论得到 `0` 或非零都会先对
Extension 和 `userpref.blend` 两个可能目标生成 post snapshot，再判断成功/失败；
因此 `set -e` 不会越过 post-image。任一 snapshot 因 symlink、type 或 ownership
不安全而失败时，停止且要求人工恢复，绝不覆盖。install 非零时使用已记录的两个
post-image 进入第 13 节 rollback；成功后仍必须确认 installed manifest、Extension
列表、启用模块和文件树。任一不一致即视为安装失败并从备份回滚。

在 `userpref.blend` 已备份、Blender 已退出且写前 SHA/inode 未变化后，开启
Online Access、固定 host/port、启用 autostart，并保存偏好：

```bash
if [ "${EXTENSION_MUTATED:-0}" = 1 ]; then
  revalidate_blender_target "$USERPREF" file userpref "$BACKUP_ROOT/userpref.install-post.json"
else
  revalidate_blender_target "$USERPREF" file userpref
fi
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
snapshot_blender_target "$USERPREF" file > "$BACKUP_ROOT/userpref.post.json"
chmod 600 "$BACKUP_ROOT/userpref.post.json"
USERPREF_LAST_SNAPSHOT="$BACKUP_ROOT/userpref.post.json"
export USERPREF_LAST_SNAPSHOT
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
MCP_PROBE_DIR="$(mktemp -d "$BACKUP_ROOT/mcp-get.XXXXXX")"
chmod 700 "$MCP_PROBE_DIR"
MCP_GET_JSON="$MCP_PROBE_DIR/blender.json"
MCP_GET_ERR="$MCP_PROBE_DIR/blender.stderr"
MCP_GET_EXPECTED="$MCP_PROBE_DIR/expected-missing.stderr"
for file in "$MCP_GET_JSON" "$MCP_GET_ERR" "$MCP_GET_EXPECTED"; do
  install -m 600 /dev/null "$file"
done
cleanup_mcp_probe() {
  unlink "$MCP_GET_JSON" 2>/dev/null || true
  unlink "$MCP_GET_ERR" 2>/dev/null || true
  unlink "$MCP_GET_EXPECTED" 2>/dev/null || true
  rmdir "$MCP_PROBE_DIR" 2>/dev/null || true
}
trap cleanup_mcp_probe EXIT

if "$CODEX_BIN" mcp get blender --json > "$MCP_GET_JSON" 2> "$MCP_GET_ERR"; then
  MCP_ENTRY_STATE=present
else
  printf '%s\n' "Error: No MCP server named 'blender' found." > "$MCP_GET_EXPECTED"
  if cmp -s "$MCP_GET_ERR" "$MCP_GET_EXPECTED"; then
    MCP_ENTRY_STATE=absent
  else
    cat "$MCP_GET_ERR" >&2
    exit 1
  fi
fi
printf '%s\n' "mcp-entry=$MCP_ENTRY_STATE"

# 若 present，在清理前解析 MCP_GET_JSON 并进行下述精确语义比较；禁止输出原文。
cleanup_mcp_probe
trap - EXIT
export MCP_ENTRY_STATE
```

这个 conditional 在 `set -e` 下可执行：成功只记录 `present`；只有 stderr 与当前
CLI 的 exact missing-entry 消息逐字节相等时记录 `absent`；任何其他失败都会把
捕获的 stderr 原样写回 stderr 后停止。受限目录是 `0700`，文件是 `0600`，清理
只 unlink 这三个确切文件并移除该确切目录；不打印完整 Codex config。

本节的 absent skeleton、原子修改和精确验证全部完成后，再运行以下 focused
probe。它只读验证当前真实 entry 和唯一缺失名称均被正确分类，并证明 config
pre/post fingerprint 未变化；它同样不打印 JSON：

```bash
config_fingerprint() {
  if [ -e "$CODEX_CONFIG" ]; then
    shasum -a 256 "$CODEX_CONFIG" | awk '{print $1}'
  else
    printf '%s\n' absent
  fi
}
CONFIG_PROBE_PRE="$(config_fingerprint)"
READ_PROBE_DIR="$(mktemp -d "$BACKUP_ROOT/mcp-read-probe.XXXXXX")"
chmod 700 "$READ_PROBE_DIR"
for name in present.out present.err missing.out missing.err expected.err; do
  install -m 600 /dev/null "$READ_PROBE_DIR/$name"
done
cleanup_read_probe() {
  for name in present.out present.err missing.out missing.err expected.err; do
    unlink "$READ_PROBE_DIR/$name" 2>/dev/null || true
  done
  rmdir "$READ_PROBE_DIR" 2>/dev/null || true
}
trap cleanup_read_probe EXIT
"$CODEX_BIN" mcp get blender --json \
  > "$READ_PROBE_DIR/present.out" 2> "$READ_PROBE_DIR/present.err"
test ! -s "$READ_PROBE_DIR/present.err"
MISSING_PROBE_NAME="blender-install-absent-probe-$$"
if "$CODEX_BIN" mcp get "$MISSING_PROBE_NAME" --json \
  > "$READ_PROBE_DIR/missing.out" 2> "$READ_PROBE_DIR/missing.err"; then
  echo "STOP: unique missing probe unexpectedly exists" >&2
  exit 1
fi
printf "Error: No MCP server named '%s' found.\n" "$MISSING_PROBE_NAME" \
  > "$READ_PROBE_DIR/expected.err"
cmp -s "$READ_PROBE_DIR/missing.err" "$READ_PROBE_DIR/expected.err"
test "$(config_fingerprint)" = "$CONFIG_PROBE_PRE"
printf '%s\n' "present=present missing=absent config=unchanged"
cleanup_read_probe
trap - EXIT
```

不存在 entry 时，在任何写入前按第 6 节记录 `config=absent` 或备份已有 config，
并用以下精确命令创建 transport 骨架。`CONFIG_PRESTATE=present` 时紧邻 add 前重验
config 仍是当前 UID 的普通非 symlink 文件且 device/inode/SHA 等于 pre-image；
`CONFIG_PRESTATE=absent` 时重验 `CODEX_ROOT` 的 type/owner/identity：

```bash
if [ "$MCP_ENTRY_STATE" = absent ]; then
  if [ "$CONFIG_PRESTATE" = absent ]; then
    test ! -L "$CODEX_ROOT"
    test -d "$CODEX_ROOT"
    test "$(stat -f '%u' "$CODEX_ROOT")" = "$(id -u)"
    test "$(stat -f '%d %i' "$CODEX_ROOT")" = "$CONFIG_PARENT_IDENTITY"
  else
    revalidate_config_image "$CONFIG_PRE_IDENTITY" "$CONFIG_PRE_SHA"
  fi

  if "$CODEX_BIN" mcp add blender \
    --env "BLENDER_PATH=$BLENDER_BIN" \
    -- "$UV_BIN" run --quiet --no-project --python 3.13 \
    --with 'mcp[cli]>=1.2.0,<2' \
    --with-editable "$MCP_SOURCE_DIR/mcp" blender-mcp; then
    CONFIG_ADD_EXIT=0
  else
    CONFIG_ADD_EXIT=$?
  fi

  if [ -L "$CODEX_CONFIG" ]; then
    echo "STOP: config became a symlink; manual recovery required" >&2
    exit 1
  elif [ -f "$CODEX_CONFIG" ]; then
    record_config_post_image "mcp-add-exit-$CONFIG_ADD_EXIT"
    CONFIG_CREATED_IDENTITY="$CONFIG_LAST_IDENTITY"
    CONFIG_CREATED_SHA="$CONFIG_LAST_SHA"
  elif [ "$CONFIG_ADD_EXIT" = 0 ] || [ "$CONFIG_PRESTATE" = present ]; then
    echo "STOP: config path unexpectedly absent after mcp add; manual recovery required" >&2
    exit 1
  fi

  if [ "$CONFIG_ADD_EXIT" != 0 ]; then
    echo "STOP: mcp add failed; rollback from the last completed config post-image" >&2
    exit 1
  fi
  revalidate_config_image "$CONFIG_CREATED_IDENTITY" "$CONFIG_CREATED_SHA"
fi
export CONFIG_ADD_EXIT CONFIG_CREATED_IDENTITY CONFIG_CREATED_SHA
```

add 返回成功或非零后都先记录最后一个安全可读 post-image，再处理状态。成功 add
记录的 `CONFIG_CREATED_IDENTITY`/`CONFIG_CREATED_SHA` 是下一次原子 TOML 写入的
基线；该写入前必须再次调用 `revalidate_config_image`。add 非零且 config 原本
absent、当前路径仍 absent 时无需移动；若留下普通文件，则使用刚记录的 post-image
安全 rollback。任何 symlink/type/identity 异常都停止并要求人工恢复。

存在 entry 时不得先 remove。LLM 必须解析 TOML、只修改
`[mcp_servers.blender]`、其 `env`，并集合式
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

紧邻原子 TOML 写入前选择并重验本次基线：

```bash
if [ "$MCP_ENTRY_STATE" = absent ]; then
  CONFIG_WRITE_BASELINE_IDENTITY="$CONFIG_CREATED_IDENTITY"
  CONFIG_WRITE_BASELINE_SHA="$CONFIG_CREATED_SHA"
else
  CONFIG_WRITE_BASELINE_IDENTITY="$CONFIG_PRE_IDENTITY"
  CONFIG_WRITE_BASELINE_SHA="$CONFIG_PRE_SHA"
fi
revalidate_config_image "$CONFIG_WRITE_BASELINE_IDENTITY" "$CONFIG_WRITE_BASELINE_SHA"
export CONFIG_WRITE_BASELINE_IDENTITY CONFIG_WRITE_BASELINE_SHA
```

写入流程：

1. 选择最近一个已完成的 config post-image 作为写入基线：entry 原本存在时是
   pre-image，刚执行 add 时是 `CONFIG_CREATED_IDENTITY`/`CONFIG_CREATED_SHA`；
2. 备份并验证备份 SHA；
3. 写入前用 `revalidate_config_image` 重验基线文件的当前 UID、普通非 symlink
   type、identity 和 SHA；
4. 在同目录创建 mode `0600` 的临时文件；
5. 用 Python 3.13 `tomllib.loads()` 验证临时文件；
6. 原子 `replace`；
7. replace 返回后立即调用 `record_config_post_image atomic-final`，把
   `CONFIG_POST_IDENTITY="$CONFIG_LAST_IDENTITY"` 和
   `CONFIG_POST_SHA="$CONFIG_LAST_SHA"`，随后重读并再次解析；
8. 运行 `codex mcp get blender --json` 精确验证 transport、args、env、timeouts
   和工具集合。

第 7 步紧邻 replace 返回后执行：

```bash
record_config_post_image atomic-final
CONFIG_POST_IDENTITY="$CONFIG_LAST_IDENTITY"
CONFIG_POST_SHA="$CONFIG_LAST_SHA"
export CONFIG_POST_IDENTITY CONFIG_POST_SHA
```

每次可能写 config 的命令后都必须立即记录 post-image。若记录本身失败，保留上一
个已完成 post-image；rollback 重验会因当前对象不匹配而停止，不能猜测或覆盖。
所有 `CONFIG_CREATED_*`、`CONFIG_POST_*` 和 `CONFIG_LAST_*` 在第 6 节先初始化，
因此中途失败的 `set -u` shell 不会引用未绑定变量。

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
    raw_tools = server["tools"]
    if isinstance(raw_tools, dict):
        tools = sorted(raw_tools)
    else:
        tools = sorted(tool["name"] for tool in raw_tools)
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
一致且已启用、26 工具集合准确、偏好唯一 drift 是 Online Access 关闭，且 Codex
stanza 或者完全精确，或者唯一 drift 是 `--no-project` 后缺少 `--python`, `3.13`
这一对参数，则：

1. 不 fetch checkout；
2. 不重装 Extension；
3. stanza 完全精确时不写 config、不创建 config 重复备份；若是已验证的唯一
   Python-pin drift，只备份一次 config，按第 9 节 identity/SHA 重验和 mode `0600`
   同目录临时文件流程，原子地只在 `--no-project` 后插入一对
   `--python`, `3.13`，并证明其他目标语义及非目标 TOML 均未变化；
4. 用户保存并正常退出 Blender；
5. 备份 `userpref.blend`；
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
   断言 live `HEAD` 等于候选 SHA、worktree clean，立即把当前 device/inode 写入
   `SOURCE_POST_IDENTITY`、候选 SHA 写入 `SOURCE_POST_HEAD`，且 Server handshake
   返回候选 catalog；
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

所有 absent-object recovery move 都必须是同卷 rename。先定义并在每次 `mv` 紧邻
之前调用；source 与 recovery 目标父目录的 `st_dev` 不同就停止，禁止 copy+unlink：

```bash
same_device_or_stop() {
  if [ "$(stat -f '%d' "$1")" != "$(stat -f '%d' "$2")" ]; then
    echo "STOP: recovery move would cross devices; no copy+unlink fallback" >&2
    exit 1
  fi
}
```

Codex config：

- `CONFIG_PRESTATE=present`：先用 `CONFIG_LAST_IDENTITY`/`CONFIG_LAST_SHA` 重验
  最近一个已完成 post-image，匹配时可在同目录 mode `0600` 临时文件中写入完整
  pre-image，解析后原子恢复；
- 当前 SHA 已变化：禁止整文件覆盖，只做三方/手术式恢复原 `blender` stanza 和
  本次新增的 `mcp__blender` membership；
- 原 stanza 不存在：只删除本次创建的 stanza；原 stanza 存在：恢复原值，不能
  用简单 `mcp remove` 代替。
- `CONFIG_PRESTATE=absent` 时按 `CONFIG_LAST_STAGE` 选择最后一个已完成 post-image：
  初值 `absent` 表示路径尚未创建；add 后是 `CONFIG_CREATED_*`；最终 atomic replace
  后是 `CONFIG_POST_*`。只引用 `CONFIG_LAST_IDENTITY`/`CONFIG_LAST_SHA`，因此
  atomic 步骤中途失败也不会在 `set -u` 下引用未绑定的 `CONFIG_POST_*`。路径已
  创建时必须重验当前 UID、普通非 symlink、last identity/SHA 后才能移动；任一
  变化都停止整文件移动并改用手术式 rollback。

Absent-config 的可执行选择与同卷移动：

```bash
if [ "$CONFIG_LAST_STAGE" = absent ]; then
  test ! -e "$CODEX_CONFIG"
  test ! -L "$CODEX_CONFIG"
else
  revalidate_config_image "$CONFIG_LAST_IDENTITY" "$CONFIG_LAST_SHA"
  RECOVERY_CONFIG="$(mktemp -d "$BACKUP_ROOT/recovery-config.XXXXXX")"
  chmod 700 "$RECOVERY_CONFIG"
  same_device_or_stop "$CODEX_CONFIG" "$RECOVERY_CONFIG"
  mv "$CODEX_CONFIG" "$RECOVERY_CONFIG/config.toml.installer-created"
  test ! -e "$CODEX_CONFIG"
  test ! -L "$CODEX_CONFIG"
fi
```

Blender：

- 关闭 Blender；
- 原 Extension 存在时，从已验证备份恢复；原 Extension 为 `absent` 时，先验证
  当前目录仍是本次安装的 ID/version/文件树且 identity 未变，再执行
  `"$BLENDER_BIN" --command extension remove --no-prefs user_default.mcp` 并验证目录和模块
  均不存在；若目录已被外部替换则停止，不删除；
- 原 `userpref.blend` 存在时恢复已验证备份；原状态为 `absent` 时，仅当当前文件
  identity/SHA 等于本次记录的 post-image 才把它移动到 `BACKUP_ROOT` 内唯一
  recovery 目录并恢复路径 absent，变化时停止；紧邻 `mv` 前必须执行
  `same_device_or_stop "$USERPREF" "$RECOVERY_USERPREF"`，跨设备时停止；
- 重新启动并核验旧 ID/version、启用状态和偏好；
- 不删除或修改任何 `.blend` 文件。

原 `userpref.blend` 为 absent 且 last post-image 重验通过时执行：

```bash
revalidate_blender_target "$USERPREF" file userpref "$USERPREF_LAST_SNAPSHOT"
RECOVERY_USERPREF="$(mktemp -d "$BACKUP_ROOT/recovery-userpref.XXXXXX")"
chmod 700 "$RECOVERY_USERPREF"
same_device_or_stop "$USERPREF" "$RECOVERY_USERPREF"
mv "$USERPREF" "$RECOVERY_USERPREF/userpref.blend.installer-created"
test ! -e "$USERPREF"
test ! -L "$USERPREF"
```

Source/runtime：

- `SOURCE_PRESTATE=present`：执行
  `revalidate_source_checkout "$SOURCE_POST_IDENTITY" "$SOURCE_POST_HEAD"`，证明
  source identity 未变、worktree clean 且 HEAD 仍是本流程最后记录的 pin/candidate
  后，才 detached checkout `SOURCE_OLD_COMMIT` 并恢复旧 catalog；否则停止；
- `SOURCE_PRESTATE=absent`：重验 source 父目录和新 checkout 的 device/inode 均
  等于 clone 前后记录值，HEAD 仍等于 `PINNED_COMMIT`，
  `git status --porcelain --untracked-files=all --ignored` 为空且没有生成的
  `uv.lock`。`--ignored` 检查 working tree 中用户新增的 ignored 内容，不检查
  `.git` 内部。全部成立才把整个 checkout 同卷移动到 `BACKUP_ROOT` 内新建的唯一
  `0700` recovery 目录并验证原路径 absent；这不是“恢复旧 commit”。任一条件
  失败都停止，绝不移动或删除用户新增内容；
- 不递归删除 checkout，不清理共享 uv cache；
- 回滚后重复第 10 节四层验收。

Existing-source rollback 在 detached checkout 旧 commit 前执行：

```bash
if [ "$SOURCE_PRESTATE" = present ]; then
  revalidate_source_checkout "$SOURCE_POST_IDENTITY" "$SOURCE_POST_HEAD"
  git -C "$MCP_SOURCE_DIR" checkout --detach "$SOURCE_OLD_COMMIT"
fi
```

例如 absent-source 分支通过上述全部重验后执行：

```bash
test "$(snapshot_source_parent required)" = "$SOURCE_PARENT_IDENTITY"
test ! -L "$MCP_SOURCE_DIR"
test -d "$MCP_SOURCE_DIR"
test "$(stat -f '%u' "$MCP_SOURCE_DIR")" = "$(id -u)"
test "$(stat -f '%d %i' "$MCP_SOURCE_DIR")" = "$SOURCE_CREATED_IDENTITY"
test "$(git -C "$MCP_SOURCE_DIR" rev-parse HEAD)" = "$PINNED_COMMIT"
test -z "$(git -C "$MCP_SOURCE_DIR" status --porcelain --untracked-files=all --ignored)"
test ! -e "$MCP_SOURCE_DIR/uv.lock"
RECOVERY_SOURCE="$(mktemp -d "$BACKUP_ROOT/recovery-source.XXXXXX")"
chmod 700 "$RECOVERY_SOURCE"
same_device_or_stop "$MCP_SOURCE_DIR" "$RECOVERY_SOURCE"
mv "$MCP_SOURCE_DIR" "$RECOVERY_SOURCE/source.installer-created"
test ! -e "$MCP_SOURCE_DIR"
test ! -L "$MCP_SOURCE_DIR"
```

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
