# 审计 Spikes

> r15/v8 复审说明：这些脚本用于 Plan 执行前的兼容/配置验证，绝不执行 Phase 0。官方 MCP 注册目录与 effective catalog 为 26/26；旧顺序的 24 项长序列在第 15 项截图工具出现截断 JSON，重启后把截图置后则 24/24 成功，说明顺序敏感性仍不能写成稳定性已修复。不要在同一 Blender GUI 连续重跑 deferred render 工具：该序列已复现 Blender 5.2 `SIGABRT`，详见 `docs/audits/2026-08-08-roadmap-execution-and-post-restart-audit.md`、`docs/audits/evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson` 与官方 issue #157084。

这些脚本只用于 plan 执行前的兼容与配置验证，不是 Phase 0 实现。

## MCP SDK v2

```bash
cd spikes/mcp-sdk-v2
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 --with 'mcp==2.0.0' python verify.py
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py --legacy-codex
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py --configured-blender
/Users/yeminjie/.local/bin/uv run --no-project --python 3.13 python verify_codex_host.py --capture-blender-transcript
```

`verify.py` 让 SDK v2 Client 的 legacy/auto 分别走 in-memory 与真实 stdio，四条组合精确断言 `2025-11-25` / `2026-07-28`、schema 和 structured content；它同时固定 raw SDK 对 `dict` 返回值生成开放 output schema 的已知边界（生产 adapter 必须另行封闭），Client 与逐工具调用均有 10 s 读取上限，整段验证有 240 s 总上限。`verify_codex_host.py` 的写入/读取共享单一 absolute deadline，stdout 用非阻塞分块读取并限制单行 16 MiB、未成行缓冲 32 MiB、非目标事件 1024 条/4 MiB；半行或无换行洪泛在有限资源内失败，不宣称可承受无界输出。初始 probe 成功后，transcript 循环即使写出失败记录，也会在工具错误、传输/收尾异常或审批事件存在时以非零状态退出；启动、目录或初始 probe 更早失败同样非零，但可能只有部分记录且没有 summary。

两个 Codex host 命令分别断言 `mcp_2026_07_28` feature=false/true，并通过 Server 侧 probe 精确读取实际协商版本。当前两者均为 `2025-06-18`；opt-in 成功不再被误报为已走 2026 wire。`--configured-blender` 保留原严格调用顺序，另行断言本机官方 Server 的 effective config 为 `approve`、显式完整 26 项 allowlist、`omit_tools_from=[]`、无 deny/逐工具 override，并严格调用 24 个非 render 工具。`--capture-blender-transcript` 使用临时 `.blend` 副本且仅在该模式把截图置后，为相同 24 项输出有界逐调用 NDJSON、耗时、参数/响应摘要与审批事件；两个 deferred render 只记录为 `not_called`。本轮证据见 `docs/audits/evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson`。这些验证互相独立，不执行 Phase 0 plan。

## Blender Lab 官方 MCP CLI

`verify_cli.py` 是历史全目录复现器：它会调用全部 26 项，包括两个已复现 `SIGABRT` 的 deferred render；单项 render/CLI 上限 180 s、整段 600 s。**当前不得运行该脚本。** 非 render 的 24 项复核统一使用上一节的 host transcript 模式；既有 render crash 只引用已归档 IPS/SHA，不重复触发。

`<2` 上界是必需的：官方 commit `4309a39` 仍使用 v1 `FastMCP`，但上游依赖声明没有上界，按默认版本 2.0.0 解析会启动失败。当前该约束解析为 MCP SDK 1.29.0；它只属于官方 Server 的隔离环境，不传播到自定义 SDK v2 Server，也不改变后者的认证与授权设计。
