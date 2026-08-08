# ROADMAP 执行与 Codex 重启后对抗审计

> 日期：2026-08-08
> 范围：[ROADMAP](../ROADMAP.md) · 官方 Blender MCP 当前模型面 · A-2/A-4 证据 · B-5/C 组前置关系
> 边界：未执行 Phase 0 Plan，未运行两个 deferred render，未修改 URS/spec/Plan/v8 provenance，未 stage/commit/push

> **固定时点审计快照（2026-08-08）**：本报告保留当轮 A-2/A-4 执行、重启验证及随后所有者裁决；正文中的 A-1/A-3/G5、B-5 和 Plan r15/r16 表述均只描述该轮时态，不追踪后续修订。当前状态统一见 [ROADMAP](../ROADMAP.md)。

## 1. 裁决

本轮应执行且可自动完成的只有 A-2 与 A-4 的有界摘要层：A-2 已关闭，A-4 摘要证据已完成：

- 当前模型直接工具目录已由旧任务的 10/26 刷新为 **26/26**；
- 三个指定的此前缺失只读工具在当前模型上下文直调成功；
- 独立 Codex host 的 `mcpServerStatus/list` 为 26/26；
- 24 个非 render 工具全部成功，逐调用与总审批事件均为 0；
- 两个 deferred render 按既有 Blender 5.2 `SIGABRT` 证据记为 `not_called`，没有重跑。

A-1 与 A-3 仍必须由项目所有者裁决。B-5 必须等这两项决定后再修订/重审 Plan；C 组仍全部禁止执行。

## 2. A-2 重启后现场证据

| 证据层 | 结果 |
|---|---|
| 当前模型目录 | 官方 `mcp__blender` 26 项全部注入；direct-only namespace 不应再用代码模式 `ALL_TOOLS` 计数 |
| 模型直调 1 | `get_screenshot_of_window_as_json`：成功 |
| 模型直调 2 | `get_blendfile_summary_path_info_for_cli`：临时 Storyboarding 副本，成功 |
| 模型直调 3 | `get_blendfile_summary_datablocks_for_cli`：同一临时副本，成功 |
| 附加直调 | 窗口截图与 Outliner 区域截图均成功 |
| host catalog | `mcpServerStatus/list`：26/26 |
| effective policy | `enabled_tools` 精确 26、`omit_tools_from=[]`、MCP mode=`approve`、全局 policy=`never` |

官方 [App Server API](https://learn.chatgpt.com/docs/app-server#api-overview) 支持 `config/mcpServer/reload`；本轮用户已完全重启，因此无需再把 reload 当必做步骤。官方 [MCP 配置文档](https://learn.chatgpt.com/docs/extend/mcp#other-configuration-options)确认 `approve` 是支持的 MCP approval mode。

## 3. A-4 有界逐调用摘要 transcript

证据文件：

- [有界 NDJSON](evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson)
- [SHA-256 sidecar](evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson.sha256)

机械统计：

| 项 | 结果 |
|---|---:|
| NDJSON 行数 | 28 |
| 目录工具数 | 26 |
| 实际调用 | 24 |
| `ok` | 24 |
| `error` / transport failure | 0 / 0 |
| `not_called` | 2 个 deferred render |
| approval events | 0 |
| transcript SHA-256 | `d5ae61959c7f76f151915cc19fd12e04c21e1c57c7652f81d87141cd928edf2d` |

每条调用记录工具名、参数键与 canonical 参数 SHA、耗时、canonical response 字节数/SHA、内容类型、结构化内容状态及调用期间审批事件；不把大图 base64 或场景内容原样复制进仓库。因此该 artifact 可复核调用集合、结果标志与自身完整性，但不是 raw payload、不可重放，也不能独立验证完整响应语义；临时 fixture 路径还使参数 SHA 不保证跨运行复现。

严格 verifier 在截图位于序列中段时再次复现 `get_screenshot_of_area_as_image` 的上游 JSON 截断错误。transcript 模式把三个截图放到最后后 24/24 成功。这说明故障具有序列/顺序敏感性，**不等于可靠性缺陷已修复**；A-3 仍需裁决。

## 4. 执行中修复

- `verify_codex_host.py` 新增显式 `--capture-blender-transcript`；默认严格模式保持不变；该模式拒绝与 `--include-render-tools` 同用。
- CLI 工具只读取 `TemporaryDirectory` 中的 Storyboarding 副本。
- 仅 transcript 模式把截图置后。初始 probe 成功后，循环中的传输异常会 fail-stop 并为剩余项写 `not_called`；循环工具错误、传输/收尾异常或审批事件存在时，写完摘要后非零退出。启动、目录或初始 probe 更早失败也非零，但可能只有部分记录且没有 summary。
- `spikes/README.md` 删除会误导执行全部 26 项（含 render）的命令，改为明确禁跑历史 CLI verifier。
- ROADMAP 将 A-4 改为非阻断证据任务，并修正 B-5 的审批→提交→attestation 顺序。

二次独立红队发现并修复：

| ID | 严重度 | 攻击/歧义 | 修复后 |
|---|---|---|---|
| V-01 | P1 | 初始 probe 成功后的 transcript 循环遇到工具错误、传输/收尾异常或审批事件时只记日志，进程仍可能退出 0 | 循环/收尾阶段完整写出 summary 后强制非零；Fake AppServer 的四类反例均通过；更早失败保持非零但不承诺 summary |
| V-02 | P1 | render/transcript 互斥只在 CLI parser；直接调用函数可绕过并触发已知崩溃 render | 护栏下沉到 `verify_blender_policy()` 入口，AppServer 构造前拒绝 |
| V-03 | P2 | 为捕获证据而全局改变严格 verifier 的截图顺序，会让原回归路径消失 | 默认严格顺序恢复；仅 transcript 模式置后截图 |
| G5-01 | P1 | “A-3 已裁决”可能被误当作 G5 已关闭；选择等待上游后仍可表面进入 C 组 | 策略裁决与 G5 分栏；隔离、风险接受、等待上游各有独立关闭条件，C 组显式要求 G5 关闭 |
| E-01 | P2 | 把只有参数/响应摘要与 SHA 的 artifact 称为 raw transcript | 全文降格为“有界逐调用摘要 transcript”，明确不可重放、不能复核完整响应语义 |

修复后代码静态门禁、证据机械复算和双路文档复核均未发现剩余 P0/P1。R-07 的 raw payload 可重放性仍是明确、非阻断的 P2 证据缺口；本轮没有把 UI/图像/场景原始响应写入仓库。

## 5. 新发现与剩余 Gate

| 项 | 状态 | 处置 |
|---|---|---|
| A-1 handoff D-1 | ☐ | 用户决定三项平台候选全部/部分/不接受；提交事实不能代替裁决 |
| A-2 模型面 26/26 | ✅ | 本轮已关闭 |
| A-3 官方 MCP 可靠性策略 | ☐ | 用户选择隔离、当前用户接受风险或等待上游 |
| A-4 摘要 transcript | ✅ 非阻断 | 24 ok、2 render not_called、approval=0；无 raw payload |
| B-5 Plan 修订 | ☐ | 等 A-1/A-3 后统一修改，避免 proposed SHA 立刻陈旧 |
| G5 可靠性门 | ☐ | A-3 只记录策略；当前用户风险接受可直接关闭，隔离需部署复核，等待上游则保持开放 |
| C 组 | 禁止执行 | 等 A-1、G5 可靠性门、B-5 与新 SHA 审批全部关闭 |

B-5 还必须处理两项新发现：

1. URS §10.1 现写 socket “自身自创建瞬间即 `0600`”，与 spec/Plan 的私有 `0700` 目录内 bind→立即 chmod `0600` 语义冲突；不得通过修改全局 umask 伪造出生权限。
2. URS §10.1 第 17/20 项需要非当前 uid/device 与边界上方祖先权限不变的直接 fixture；间接覆盖不能冒充逐项验收。

## 6. 审计结论

A-2 与 A-4 摘要层的证据闭环成立，但只能关闭模型可见性、24 个非 render 功能调用、无审批和逐调用摘要子门；raw payload 可重放性不在该 artifact 中。官方 screenshot 顺序敏感性和 deferred render 崩溃仍开放；A-3 裁决与 G5 关闭必须分开记录。Plan r15 仍为 pre-revision 基线，Phase 0 仍未执行。
