# 审计 Spikes

这些脚本只用于 plan 执行前的兼容与配置验证，不是 Phase 0 实现。

## MCP SDK v2

```bash
cd spikes/mcp-sdk-v2
uv run --no-project --python 3.13 --with 'mcp==2.0.0' python verify.py
python3 verify_codex_host.py
python3 verify_codex_host.py --legacy-codex
```

分别验证 SDK 内存/stdio、Codex 2026-07-28 opt-in、Codex 默认旧协议。

## Blender Lab 官方 MCP CLI

```bash
cd spikes/official-blender-mcp
uv run --no-project --with 'mcp[cli]>=1.2.0,<2' python verify_cli.py
```

脚本显式设置 `BLENDER_PATH`，只读取 Blender 自带 Storyboarding 模板，验证 path info、datablocks summary 和 CLI 只读代码执行路径。

`<2` 上界是必需的：官方 commit `4309a39` 仍使用 v1 `FastMCP`，但上游依赖声明没有上界，按默认版本 2.0.0 解析会启动失败。当前该约束解析为 MCP SDK 1.29.0；它只属于官方 Server 的隔离环境。
