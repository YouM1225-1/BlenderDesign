# 安装与接入（Phase 0）

## 1. 前置

- macOS 14+ / Apple Silicon；Blender **5.2.0 LTS**（官方 DMG）
- [uv](https://docs.astral.sh/uv/)；本机使用 `/Users/yeminjie/.local/bin/uv`，本仓库 frozen sync 完成

## 2. 安装 Bridge 扩展

```bash
/Users/yeminjie/.local/bin/uv run --frozen python scripts/vendor_protocol.py
cd bridge && zip -r ../blender_codex_bridge.zip . -x "*__pycache__*" && cd ..
```

Blender → Edit → Preferences → Get Extensions → 右上角下拉 → Install from Disk… →
选 `blender_codex_bridge.zip`。启用后在 3D 视口按 `N` → 「Codex」页签。

## 3. 注册 MCP Server 到 Codex

```bash
/Applications/ChatGPT.app/Contents/Resources/codex mcp add blender-codex -- \
  /Users/yeminjie/.local/bin/uv --directory /Users/yeminjie/Documents/BlenderDesign \
  run --frozen blender-codex-server
```

三个工具全只读，`~/.codex/config.toml` 中可保持 `default_tools_approval_mode = "auto"`。

## 4. 使用

1. Blender 里点「允许 Codex 连接」（每个会话一次，token 随会话轮换）
2. Codex 里问：“我的 Blender 什么状态？” → 应看到实例列表
3. 结束后点「断开」，socket 与 token 即销毁

## 5. 排障

| 现象 | 处理 |
|---|---|
| `BRIDGE_UNAVAILABLE` / 空列表 + 引导文案 | 面板尚未点「允许连接」，或 Blender 已关 |
| `ENVELOPE_VERSION_MISMATCH` | Bridge 扩展与 Server 版本不同步：重新打包安装扩展 |
| `version_warning` 非空 | Blender 不是精确基线 5.2.0：只读可用，写功能（Phase 1）将拒绝 |
| Server 日志 | `~/Library/Application Support/BlenderCodex/logs/server-*.jsonl` |

## 6. 与官方 Blender Lab MCP 并存（若你也装了它）

2026-08-08 按用户明确授权采用**显式固定的完整 26 工具、无 MCP 审批**配置，并选择“当前用户接受风险”。官方 MCP 仍含两个任意 Python 工具并使用无鉴权 localhost TCP 9876；它是自定义安全系统之外的兼容通道，不得拿它证明 URS G1–G3。当前风险接受关闭的是项目部署 Gate，不是上游稳定性修复：严格中段截图序列仍可返回截断 JSON，两个 deferred render 仍有 Blender 5.2 `SIGABRT` 证据且本轮未重跑。以下 26 项是当前上游注册目录的 allowlist 快照，上游增删工具时必须先复核再更新：

```toml
[mcp_servers.blender]
command = "/Users/yeminjie/.local/bin/uv"
args = ["run", "--quiet", "--no-project", "--with", "mcp[cli]>=1.2.0,<2", "--with-editable", "/Users/yeminjie/blender_mcp/mcp", "blender-mcp"]
default_tools_approval_mode = "approve" # Codex 语义：预先批准，不弹 MCP 审批
enabled_tools = [
  "execute_blender_code",
  "execute_blender_code_for_cli",
  "get_blendfile_summary_datablocks",
  "get_blendfile_summary_datablocks_for_cli",
  "get_blendfile_summary_missing_files",
  "get_blendfile_summary_missing_files_for_cli",
  "get_blendfile_summary_of_linked_libraries",
  "get_blendfile_summary_of_linked_libraries_for_cli",
  "get_blendfile_summary_path_info",
  "get_blendfile_summary_path_info_for_cli",
  "get_blendfile_summary_usage_guess",
  "get_blendfile_summary_usage_guess_for_cli",
  "get_object_detail_summary",
  "get_objects_summary",
  "get_python_api_docs",
  "get_screenshot_of_area_as_image",
  "get_screenshot_of_window_as_image",
  "get_screenshot_of_window_as_json",
  "jump_to_tab_by_name",
  "jump_to_tab_by_space_type",
  "jump_to_view3d_object_by_name",
  "jump_to_view3d_object_data_by_name",
  "render_thumbnail_to_path",
  "render_viewport_to_path",
  "search_api_docs",
  "search_manual_docs",
]
omit_tools_from = []
startup_timeout_sec = 20
tool_timeout_sec = 60

[mcp_servers.blender.env]
BLENDER_PATH = "/Applications/Blender.app/Contents/MacOS/Blender"

# 若 config 已有 [features.code_mode]，把此键合并进既有表，不要重复声明表头。
[features.code_mode]
direct_only_tool_namespaces = ["mcp__blender"]
```

- `enabled_tools` 必须与上列 26 项逐集合全等，`omit_tools_from=[]`；不得出现 `disabled_tools` 或逐工具 override。显式 allowlist 是“当前完整目录”的固定快照，不等于自动接纳未来新增工具
- `features.code_mode.direct_only_tool_namespaces` 必须包含且当前固定为 `mcp__blender`，确保该 namespace 只走直接工具调用路径
- 独立 Codex app-server 的 `config/read` 与 `mcpServerStatus/list` 必须分别证明 effective filter 与目录均为 26/26；本轮重启后当前模型面也已直证为 26/26，未来正式执行或新任务仍须重新计数，不得用 effective config 单独替代模型面。截图置后的 A-4 摘要 transcript 为 24/24、approval=0，但不含 raw payload、不可重放，也不消除严格序列缺陷
- 官方 Server 的启动命令必须显式钉 **`mcp[cli]>=1.2.0,<2`**：上游 commit `4309a39` 的依赖声明无上界，而它仍 `from mcp.server.fastmcp import FastMCP`——按默认解析到 SDK 2.0.0 会以 `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` 启动失败（复审 R-05 实测）。用 `uv --no-project --with-editable` 启动，避免在上游 checkout 里生成 `uv.lock`
- **该 `<2` 上界只属于官方 Server 的隔离环境**，绝不可传播到本项目（本项目用 SDK v2）——两个 Server 由不同 `uv` 进程启动，不共享 Python 环境
- 不启用官方 HTTP 模式（当前源码 CORS `*` 且关闭 DNS rebinding 防护）
- 本项目 Bridge 与官方互不依赖：本项目走 UDS + token，官方走 TCP 9876
