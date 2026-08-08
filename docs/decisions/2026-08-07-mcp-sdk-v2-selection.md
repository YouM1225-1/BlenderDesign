# ADR：自定义 Server 采用 MCP Python SDK v2

> 状态：Accepted（自定义 Server）；官方 deferred-render 稳定性另有外部兼容风险
> 日期：2026-08-08（r15/v8 复审）
> 适用对象：本仓库计划实现的 Blender Codex MCP Server
> 不适用对象：Blender Lab 官方 MCP 的独立运行环境

## 决策

自定义 Server 从首次实现开始采用：

```toml
dependencies = ["mcp>=2.0,<3"]
```

当前 `uv.lock` 应解析并固定到 `mcp==2.0.0`；CI 使用 `uv sync --frozen`，升级必须通过显式依赖更新和兼容测试。

Server API 使用：

```python
from mcp.server import MCPServer

mcp = MCPServer("blender-codex", instructions=INSTRUCTIONS)
```

v7 红队补充：SDK v2 的 `Tool.run` 在同步工具函数返回后才执行结果/structuredContent 转换；因此 scene-summary 容量准入必须放在 Server middleware、包住完整 `call_next` 与 audit postlude。只包同步 reader 会在转换阶段提前释放，已由三请求 wire 反例复现并修复。

不先实现 `FastMCP` v1 版本，也不维护应用级 v1/v2 双栈。

## 协议 rollout

SDK v2 同时服务 2025-era 和 2026-07-28 客户端：

- SDK v2 Client 的 legacy 与 auto 模式分别走独立 wire path，精确断言 `2025-11-25` 与 `2026-07-28`；
- Codex 的 `mcp_2026_07_28` 开关稳定前，生产继续使用宿主实际协商的旧协议；
- 当前 Codex 即使启用该开关仍协商为 `2025-06-18`。开关启用与工具调用成功不能充当 2026 wire 证据；
- 开关稳定后切换客户端，不迁移 Server SDK；
- Tasks extension 仍不进入当前范围，长任务继续使用服务端句柄 + 轮询。

原 Phase 1.5 不再包含“SDK 从 v1 升 v2”。如保留该里程碑，其内容只应是协议一致性、结果形状和旧协议退役评估。

## 证据

Server uv 隔离环境使用 Python 3.13.14；Blender 5.2.0 内置 Python 为 3.13.13。SDK 2.0.0、Codex 0.147.0-alpha.6.5 下，三工具 spike 已通过：

| 路径 | 结果 |
|---|---|
| SDK v2 in-memory Client，legacy | 精确协商 `2025-11-25`；发现、schema、三次结构化调用通过 |
| SDK v2 stdio Client，legacy | 精确协商 `2025-11-25`；发现、schema、三次结构化调用通过 |
| SDK v2 in-memory Client，auto | 精确协商 `2026-07-28`；发现、schema、三次结构化调用通过 |
| SDK v2 stdio Client，auto | 精确协商 `2026-07-28`；发现、schema、三次结构化调用通过 |
| Codex 默认路径 | feature=false；Server 侧实测协商 `2025-06-18`，工具调用通过 |
| Codex opt-in 路径 | feature=true；Server 侧仍实测协商 `2025-06-18`，**不作为 2026 wire 证据** |
| Codex + 官方 Blender MCP | effective config 显式 allowlist 为当前完整 26 项、`omit_tools_from=[]`、无 deny/逐工具覆盖；`approve`；完整 26 工具发现、代表调用通过且 `approval_events=0` |

验证代码位于 `spikes/mcp-sdk-v2/`；官方通道的机器可读收口证据为 `docs/audits/evidence/2026-08-08-official-blender-mcp-v2.json`（历史 v1 JSON 仍保留）。Codex 当前未协商 2026 是宿主 rollout 状态，不是 SDK v2 Server 的能力缺陷；后者已由真实 in-memory 与 stdio Client 独立证明。

## 与 Blender Lab 官方 MCP 并存

官方 MCP 当前仍导入 v1 `FastMCP`，所以保留其独立启动命令中的 `mcp[cli]>=1.2.0,<2`。它和本项目各自由独立 `uv` 环境运行：

- 官方 Server：SDK v1；Codex 显式暴露当前注册的完整 26 个工具，`omit_tools_from=[]`，不设 `disabled_tools` 或逐工具覆盖，审批模式为 `approve`；上游新增工具需重新同步 allowlist；
- 自定义 Server：SDK v2，提供 UDS、token、审计和后续事务能力。

当前本机配置为：

```toml
[mcp_servers.blender]
command = "/Users/yeminjie/.local/bin/uv"
args = ["run", "--quiet", "--no-project", "--with", "mcp[cli]>=1.2.0,<2", "--with-editable", "/Users/yeminjie/blender_mcp/mcp", "blender-mcp"]
default_tools_approval_mode = "approve"
enabled_tools = ["execute_blender_code", "execute_blender_code_for_cli",
  "get_blendfile_summary_datablocks", "get_blendfile_summary_datablocks_for_cli",
  "get_blendfile_summary_missing_files", "get_blendfile_summary_missing_files_for_cli",
  "get_blendfile_summary_of_linked_libraries", "get_blendfile_summary_of_linked_libraries_for_cli",
  "get_blendfile_summary_path_info", "get_blendfile_summary_path_info_for_cli",
  "get_blendfile_summary_usage_guess", "get_blendfile_summary_usage_guess_for_cli",
  "get_object_detail_summary", "get_objects_summary", "get_python_api_docs",
  "get_screenshot_of_area_as_image", "get_screenshot_of_window_as_image",
  "get_screenshot_of_window_as_json", "jump_to_tab_by_name", "jump_to_tab_by_space_type",
  "jump_to_view3d_object_by_name", "jump_to_view3d_object_data_by_name",
  "render_thumbnail_to_path", "render_viewport_to_path", "search_api_docs", "search_manual_docs"]
omit_tools_from = []
startup_timeout_sec = 20
tool_timeout_sec = 60

[features.code_mode]
direct_only_tool_namespaces = ["mcp__blender"]
```

`enabled_tools` 是当前官方 checkout 的完整 26 项 allowlist，`omit_tools_from=[]` 且没有 deny/逐工具覆盖；上游新增工具必须重新核对并更新该快照。`approve` 代表不触发 MCP 工具审批；全局 `approval_policy=never` 也保持不弹审批。该选择只属于官方 Server 的本机 Codex 接入层，**不替代身份认证，也不传播到自定义 Server**。自定义 Server 的 UDS、token、审计和写事务授权边界保持独立。

不得为统一版本而强行修改官方源码环境，也不得因为官方 Server 使用 v1 而让新项目降级到 v1。

### 官方 deferred render 限定（v8）

官方 26 项注册与独立 app-server 目录为 26/26；历史单轮直调曾报告 26 项，但最新安全 host 24 项长序列在第 15 项截图工具出现截断 JSON（单独重试成功），所以不把 24/24 写成稳定性证明。随后在 Blender 5.2 GUI 连续调用 deferred `render_thumbnail_to_path`/后续 render 时复现 `SIGABRT`（libmalloc `pointer being freed was not allocated`）。上游 [Blender #157084](https://projects.blender.org/blender/blender/issues/157084) 标为 5.1/5.2 broken/confirmed，[PR #156953](https://projects.blender.org/blender/blender/pulls/156953) 说明 render 开始后才恢复 RenderData 的竞态，[blender_mcp #12](https://projects.blender.org/lab/blender_mcp/issues/12) 仍记录临时 render 设置需保持到完成。当前 ADR 不把官方 render 稳定性计入自定义 Server 的 G1–G3，也不建议在同一 Blender GUI 重跑成对 deferred render；部署方应禁用/替换该工具，或改为独立 headless render，待上游修复后再验收。机器细节见 `docs/audits/evidence/2026-08-08-official-blender-mcp-v2.json`。

该上界不能省略：官方 commit `4309a39` 的依赖声明仍是无上界的 `mcp[cli]>=1.2.0`，默认解析到 2.0.0 后会因缺少 `mcp.server.fastmcp` 而启动失败；显式 `<2` 当前解析为 1.29.0 并通过 CLI 冒烟。

## 被否决方案

### 先用 v1，Phase 1 后迁移

否决原因：v1 已进入维护期；当前无存量实现；v2 已证明兼容 Codex 新旧协议。该方案只会重复实现和测试 adapter，增加 3–5 人日计划债务。

### 同时维护 v1/v2 adapter

否决原因：SDK v2 已提供多协议兼容，应用层双栈没有新增能力。

### 立即强制所有 Codex 客户端启用 2026-07-28

否决原因：当前 Codex 开关仍标为 under development。SDK 与协议 rollout 解耦即可，不需要承担该风险。

## 迁移完成状态

仓库 URS、spec 与 Phase 0 plan 已完成以下文档迁移；这只更新实施基线，不代表已经执行 plan：

- 依赖改为 `mcp>=2.0,<3`，实现 API 改为 `MCPServer`；
- adapter、schema 与协议测试按 SDK v2 修订；
- “Phase 1.5 再升级 SDK”已撤销，Phase 1.5 仅保留 wire 协议 rollout；
- 旧协议与 2026-07-28 使用独立 wire path 并精确断言协商版本。

## 来源

- [MCP Python SDK v2.0.0 Release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
- [OpenAI Docs：Codex 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)
- [OpenAI Docs：Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenAI Codex Changelog](https://learn.chatgpt.com/docs/changelog#month-2026-08)
- [Blender Lab MCP 固定 commit](https://projects.blender.org/lab/blender_mcp/src/commit/4309a39646e644261624bfcd2bca669b343b7621)
