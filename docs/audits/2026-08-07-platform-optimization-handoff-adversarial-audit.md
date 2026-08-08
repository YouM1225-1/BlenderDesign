# 平台优化交接清单·融合对抗性审计（r15/v8）

> **当前审批报告（2026-08-08）**：本报告审计 handoff、URS/spec/Plan、测量记录、SDK ADR、隔离证据与官方 Blender MCP 证据。它取代旧的 r12/r13/r14 收口表述；Phase 0 Plan 仍未执行、未勾选、未提交。

## 1. 结论

本轮先复现了一个此前遗漏的 P1：Blender 扩展的第二个 `register_class` 失败时，旧 `register()` 会把第一个已注册 class 留在 Blender 中。Blender 的 `addon_utils` 在模块加载失败后不会替扩展调用 `unregister()`，所以残留会造成重复注册和后续重试失败。

修复已写回 Plan-as-code，并加入两个反例：

- 注册部分失败时，只逆序撤销本次新增 class；
- 回滚自身失败时保留未撤销栈并抛出明确的 `class registration rollback incomplete`。

r15/v8 隔离树随后通过 307 tests、ruff、mypy、vendor/nested import、background、GUI smoke 和新的 100k GUI 子门。就自研候选实现而言，本轮没有已知未关闭的 P0/P1；这不是 Phase 0 已实施证明。

仍不能收口为“所有官方 MCP 26 项稳定”：

- 官方 checkout/注册目录/独立 app-server effective catalog 是 26/26；
- 历史单轮 26 工具直调记录与最新安全 host 长序列不是同一证据。最新 24 项安全 host 复跑在第 15 项 `get_screenshot_of_area_as_image` 出现截断/无效 JSON，单独重试成功但未消除长序列缺陷；
- 连续 deferred render 已复现 Blender 5.2 `SIGABRT`；
- 当前任务模型工具面仍是 10/26，不能由磁盘配置或另一个 app-server 热刷新。

因此最终状态是“自研隔离预检通过、官方兼容边界开放、等待用户审批”，不是自动执行 Plan。

## 2. 审计边界与方法

证据分级：

| 级别 | 内容 |
|---|---|
| E1 | 当前机器的 Blender 5.2.0、官方 checkout、Codex effective 配置与 host replay |
| E2 | 从当前 Plan 机械物化到工作区外 r15/v8 树的测试、静态门禁和真 Blender smoke |
| E3 | 当前 URS/spec/Plan/ADR/handoff/measurement 的版本、SHA、交叉链接和口径检查 |
| E4 | Blender、MCP SDK、Codex 官方资料及上游 issue/PR |

隔离根：`/private/tmp/blenderdesign-v8-r15-audit.9595`。该目录不属于仓库生产代码。

## 3. 对抗性发现与处置

| ID | 严重度 | 攻击输入/证据 | 处置与当前状态 |
|---|---|---|---|
| A-25 | P1 | 第二个 class 的 `register_class` 抛异常；第一个 class 在 Blender 中仍注册。`addon_utils` 删除失败模块而不调用其 `unregister`。 | Plan 的 `register()` 记录起始栈，异常时逆序回滚本次新增项；回滚失败保留栈并报告。两个单测加入，已关闭。 |
| F-01a/F-01b | P0 | 目录全量物化、FIFO session 可阻塞。 | 惰性 cursor/backlog、同 fd no-follow、regular-file 与有界读取；回归通过。 |
| F-02 | P0 | discovery 与聚合二次开窗。 | 单一 absolute monotonic deadline 贯穿 discovery/probe/aggregation/cleanup；回归通过。 |
| F-03 | P0 | SDK v2 conversion 前 semaphore 提前释放。 | 准入移入 raw-argument middleware，包住完整 `call_next`、structuredContent 转换和 audit postlude；第三请求 fail-fast `BRIDGE_BUSY`；wire 三请求反例通过。 |
| F-04/F-05 | P0/证据 | 协议测试静默降级、L3 hash fixture 盲区。 | legacy/modern 独立 wire path；真实 Blender `hash_scope=true` 进入判据。 |
| F-06/F-07/F-08 | P1 | SDK 版本属性、capabilities 触网、字典序饿死活实例。 | `importlib.metadata.version`、默认本地回答、跨窗口 cursor/backlog；回归通过。 |
| 官方 deferred render | 外部 P0 | `SIGABRT` crash report，见 §5。 | 不再重复运行成对 deferred render；记录为外部兼容阻断，不混入自研 G1–G3。 |

注册回滚的诚实边界：如果 `unregister_class` 自身失败，代码只能保留栈并报告；Blender 可能随后卸载失败模块，因此不能声称“自动可重试”。这正是反例测试固定的失败语义，而不是隐藏的成功声明。

## 4. 规范/文档融合审计

- URS 与 spec 仍为 v1.11；当前 r15/v8 预检数字已同步为 307（275 unit + 32 contract）、100k worker P95 1605.18 ms / max 2560.86 ms / observer P95 1655.44 ms / max tick 62.50 ms。
- Plan 当前 SHA 为 `7160f61846e628f6c11fb29305064ad98ff49c16170804d283fc6c8fac750487`；46 个带路径 Python fence 仍与新隔离树逐字节一致。92 个可执行 checkbox 与 1 个无 checkbox 的 G0 preflight 均未执行。
- handoff 的 T-1/T-5 和 M-4 原文已显式标为历史或更新为当前裁决；不再把旧 v5/v6/v7 manifest、93 token 计数或 r13 性能数字当作当前证据。
- SDK ADR 已区分 Server uv Python 3.13.14 与 Blender embedded Python 3.13.13，并链接官方 MCP v2 机器证据。
- 上传研究文档仍是非规范输入；其不可复核引用/过时断言不覆盖 URS、官方来源或实测合同。

## 5. 官方 Blender MCP：注册、功能与风险分层

机器可读证据：[official-blender-mcp-v2.json](evidence/2026-08-08-official-blender-mcp-v2.json)。

| 层 | 结论 | 能否当作“26 稳定” |
|---|---|---|
| 源码 AST/运行时注册 | 26 个精确名称，checkout `4309a396…` clean | 不能；只证明注册 |
| 独立 app-server catalog | effective `enabled_tools` 26、`omit_tools_from=[]`、无 deny/逐工具覆盖、审批事件 0 | 不能；只证明宿主目录 |
| 历史单轮直调 | 26 项曾有成功记录，但无完整 raw transcript；仅代表调用可复算 | 不能外推全量稳定 |
| 最新安全 host replay | 24 项请求，第 15 项截图工具长序列 JSON 截断；单独重试成功 | 明确未关闭 |
| deferred render | `SIGABRT`；crash SHA-256 `cc8c7f4a…`；上游 #157084/#156953/blender_mcp #12 仍开放 | 明确不能 |

当前模型工具面：10 个摘要/文档工具；缺少 execute、CLI、截图、跳转和 render 共 16 个。需要重启/新任务后由模型上下文直接确认，当前任务不能热替换 schema。

## 6. r15/v8 隔离门禁

| 门禁 | 结果 |
|---|---|
| pytest | **307 passed**（unit 275 + contract 32） |
| adapter 专项 | 35 passed；实质代码 373 行（≤375） |
| ruff | clean |
| mypy strict | 22 文件、0 错误 |
| `bash scripts/checks.sh` | ALL CHECKS PASSED |
| vendor / nested import / `uv lock --check` | 通过 |
| Blender background | `BG_CHECK_OK`，退出码 0 |
| Blender GUI smoke | `SMOKE_OK`，五项 true，`errors=[]` |
| 100k GUI Bridge-RPC | object/mesh 100000；worker P95 1605.18 ms、max 2560.86 ms；observer P95 1655.44 ms；max tick 62.50 ms；`large_scene_budget_ok=true` |
| Plan parity | 46/46；artifact/vendor 3/3（详见 v8 manifests） |

100k 证据只覆盖 `BridgeClient → UDS → Bridge`，不覆盖 MCP stdio、SDK middleware、Discovery、schema、Pydantic validation 或 audit postlude；max 超过 2 s，故不关闭端到端 NFR-P1。

## 7. Ponytail repo-wide complexity pass

- Lean already. Required contracts explain the small Protocol/dataclass and fixed executor/semaphore surfaces; vendored protocol duplication is an explicit build boundary, not removable bloat.
- No dependency can be safely deleted: the only runtime third-party dependencies are the requested MCP SDK v2 and Pydantic; dev tools are directly used by the frozen gates.
- No speculative factory/config layer or dead feature flag was found in the materialized implementation.

net: -0 lines, -0 deps possible.

## 8. 审批前剩余 Gate

1. 用户确认 D-1/D-2（平台候选归属/提交策略）。
2. 如需“当前模型面 26/26”，重启 Codex 或新建任务后直接观察工具目录并调用缺失工具；不要把 effective config 代替模型面证据。
3. 官方 render/screenshot 外部风险需由部署方决定禁用、隔离 headless 或等待上游修复。
4. 用户批准前不进入 Task 0；不 commit、push 或重启 dirty Blender。

## 9. 复算入口

- [r15 Plan](../superpowers/plans/2026-07-23-phase0-readonly-channel.md)
- [URS](../../Blender-Codex-需求规格说明书-v1.md)
- [spec](../superpowers/specs/2026-07-23-phase0-readonly-channel-design.md)
- [SDK ADR](../decisions/2026-08-07-mcp-sdk-v2-selection.md)
- [handoff](../handoff/2026-08-07-platform-optimization-handoff.md)
- [r15/v8 closeout](2026-08-07-closeout-v3.md)
