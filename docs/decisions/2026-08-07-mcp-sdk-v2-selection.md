# ADR：自定义 Server 采用 MCP Python SDK v2

> 状态：Accepted
> 日期：2026-08-07
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

不先实现 `FastMCP` v1 版本，也不维护应用级 v1/v2 双栈。

## 协议 rollout

SDK v2 同时服务 2025-era 和 2026-07-28 客户端：

- Codex 的 `mcp_2026_07_28` 开关稳定前，生产可继续使用 Codex 默认旧协议；
- CI 同时验证 Codex 默认协议与 opt-in 2026-07-28；
- 开关稳定后切换客户端，不迁移 Server SDK；
- Tasks extension 仍不进入当前范围，长任务继续使用服务端句柄 + 轮询。

原 Phase 1.5 不再包含“SDK 从 v1 升 v2”。如保留该里程碑，其内容只应是协议一致性、结果形状和旧协议退役评估。

## 证据

Python 3.13.14、SDK 2.0.0、Codex 0.147.0-alpha.6.5 下，三工具 spike 已通过：

| 路径 | 结果 |
|---|---|
| SDK v2 in-memory Client | 通过 |
| SDK v2 stdio Client | 通过 |
| Codex + `mcp_2026_07_28` | 通过 |
| Codex 默认旧协议 + SDK v2 Server | 通过 |

四条路径均完成工具发现和三次结构化工具调用。验证代码位于 `spikes/mcp-sdk-v2/`。

## 与 Blender Lab 官方 MCP 并存

官方 MCP 当前仍导入 v1 `FastMCP`，所以保留其独立启动命令中的 `mcp[cli]>=1.2.0,<2`。它和本项目各自由独立 `uv` 环境运行：

- 官方 Server：SDK v1，仅暴露已配置的只读 allowlist；
- 自定义 Server：SDK v2，提供 UDS、token、审计和后续事务能力。

不得为统一版本而强行修改官方源码环境，也不得因为官方 Server 使用 v1 而让新项目降级到 v1。

该上界不能省略：官方 commit `4309a39` 的依赖声明仍是无上界的 `mcp[cli]>=1.2.0`，默认解析到 2.0.0 后会因缺少 `mcp.server.fastmcp` 而启动失败；显式 `<2` 当前解析为 1.29.0 并通过 CLI 冒烟。

## 被否决方案

### 先用 v1，Phase 1 后迁移

否决原因：v1 已进入维护期；当前无存量实现；v2 已证明兼容 Codex 新旧协议。该方案只会重复实现和测试 adapter，增加 3–5 人日计划债务。

### 同时维护 v1/v2 adapter

否决原因：SDK v2 已提供多协议兼容，应用层双栈没有新增能力。

### 立即强制所有 Codex 客户端启用 2026-07-28

否决原因：当前 Codex 开关仍标为 under development。SDK 与协议 rollout 解耦即可，不需要承担该风险。

## 执行前门槛

Phase 0 plan 在真正执行前必须另行修订以下引用，但本 ADR 不直接修改 plan：

- `mcp>=1.28,<1.29` → `mcp>=2.0,<3`；
- `FastMCP` → `MCPServer`；
- 更新 adapter 和协议测试；
- 删除“Phase 1.5 再升级 SDK”的承诺；
- 保留一个旧协议兼容测试和一个 2026-07-28 测试。

## 来源

- [MCP Python SDK v2.0.0 Release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
- [OpenAI Docs：Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenAI Codex Changelog](https://learn.chatgpt.com/docs/changelog#month-2026-08)
- [Blender Lab MCP 固定 commit](https://projects.blender.org/lab/blender_mcp/src/commit/4309a39646e644261624bfcd2bca669b343b7621)
