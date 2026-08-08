# 审计 Spikes

> r15/v8 复审说明：这些脚本用于 Plan 执行前的兼容/配置验证，绝不执行 Phase 0。官方 MCP 注册目录与 effective catalog 为 26/26；历史非-render host 直调曾通过，但最新 24 项长序列在第 15 项截图工具出现截断 JSON（单独重试成功），不能写成当前稳定性证明。不要在同一 Blender GUI 连续重跑 deferred render 工具：该序列已复现 Blender 5.2 `SIGABRT`，详见 `docs/audits/2026-08-07-platform-optimization-handoff-adversarial-audit.md`、`docs/audits/evidence/2026-08-08-official-blender-mcp-v2.json` 与官方 issue #157084。

这些脚本只用于 plan 执行前的兼容与配置验证，不是 Phase 0 实现。

## MCP SDK v2

```bash
cd spikes/mcp-sdk-v2
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 --with 'mcp==2.0.0' python verify.py
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py --legacy-codex
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py --configured-blender
```

`verify.py` 让 SDK v2 Client 的 legacy/auto 分别走 in-memory 与真实 stdio，四条组合精确断言 `2025-11-25` / `2026-07-28`、schema 和 structured content；它同时固定 raw SDK 对 `dict` 返回值生成开放 output schema 的已知边界（生产 adapter 必须另行封闭），Client 与逐工具调用均有 10 s 读取上限，整段验证有 240 s 总上限。`verify_codex_host.py` 的写入/读取共享单一 absolute deadline，stdout 用非阻塞分块读取并限制单行 16 MiB、未成行缓冲 32 MiB、非目标事件 1024 条/4 MiB；半行或无换行洪泛在有限资源内失败，不宣称可承受无界输出。

两个 Codex host 命令分别断言 `mcp_2026_07_28` feature=false/true，并通过 Server 侧 probe 精确读取实际协商版本。当前两者均为 `2025-06-18`；opt-in 成功不再被误报为已走 2026 wire。`--configured-blender` 另行断言本机官方 Server 的 effective config 为 `approve`、显式完整 26 项 allowlist、`omit_tools_from=[]`、无 deny/逐工具 override，工具目录精确等于 26 项，执行代表性调用，并要求观察到的 approval 事件为 0。三组验证互相独立，不执行 Phase 0 plan。

## Blender Lab 官方 MCP CLI

```bash
cd spikes/official-blender-mcp
/Users/yeminjie/.local/bin/uv run --no-project --with 'mcp[cli]>=1.2.0,<2' python verify_cli.py
```

脚本显式设置 `BLENDER_PATH`，先精确断言官方注册目录为 26 项，再只读取 Blender 自带 Storyboarding 模板，验证 path info、datablocks summary 和 CLI 代码执行路径。Client 初始化设 30 s 读取上限，每个可能拉起 Blender 的 CLI 调用设 120 s 独立上限，整段会话另有 420 s 总上限（覆盖三次调用的最坏合法窗口）；超时即失败，不作为无界证据脚本运行。

`<2` 上界是必需的：官方 commit `4309a39` 仍使用 v1 `FastMCP`，但上游依赖声明没有上界，按默认版本 2.0.0 解析会启动失败。当前该约束解析为 MCP SDK 1.29.0；它只属于官方 Server 的隔离环境，不传播到自定义 SDK v2 Server，也不改变后者的认证与授权设计。
