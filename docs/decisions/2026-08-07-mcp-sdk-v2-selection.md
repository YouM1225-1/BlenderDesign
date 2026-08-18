# ADR：Phase 0 使用 MCP SDK v2

状态：Accepted

## 决策

自研 `blender-codex-server` 使用 `mcp>=2,<3` 和 `mcp.server.MCPServer`。协议适配集中在 `server/mcp/adapter.py`，core 层不依赖 MCP SDK。

## 原因

- 项目没有必须兼容的 SDK v1 实现；
- SDK v2 支持封闭输入/输出 schema 和 structured content；
- adapter 已通过当前 Codex、legacy 协议和 SDK client 的独立 contract 测试；
- 只维护一套 adapter 能减少协议分叉和重复测试。

## 约束

- Python 保持 `>=3.13,<3.14`；
- SDK 大版本由 `pyproject.toml` 和 `uv.lock` 固定；
- `server/core/`、`bridge/core/` 与 `protocol/` 不导入 MCP SDK；
- output model 使用严格 Pydantic schema，未知参数在工具执行前拒绝；
- 协议升级必须先扩展 contract 测试，再修改 adapter。

## 非目标

本决策不适用于仓库打包的官方 Blender MCP。官方分发拥有独立 runtime 和 manifest，不与 Phase 0 Server 共用 Python 环境。
