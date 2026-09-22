# 文档中心

本目录保留当前实现的正式文档，以及资产验收方案(`acceptance/`)、待实施设计(`superpowers/specs/`)与实施计划(`superpowers/plans/`)。此外，仓库根目录保留一份绑定旧提交的 V3.1 对抗性审计作为明确档案例外；其余历史研究草稿和机器证据不在工作树中，需要追溯时使用 Git 历史。

## 使用文档

- [项目架构](architecture.md)：两条 MCP 链路、组件关系与安全边界。
- [Phase 0 只读通道安装](install.md)：安装 Blender Bridge 并注册自研 MCP Server。
- [官方 Blender MCP 分发与安装](distribute-official-blender-mcp.md)：受审分发、信任边界、安装和回滚入口。
- [官方 Blender MCP 使用](use-official-blender-mcp.md)：安装后的安全使用方式。
- [验证说明](validation.md)：自动化门禁、手工验证与结论边界。
- [Agent 工作流](agent-workflow.md)：GPT-6 Astra 指令对齐、技能范围和维护场景。

## 资产验收方案

- [资产验收规范 V5](acceptance/blender_mcp_skill_acceptance_optimized_v5.md)：当前 schema v2 规范；有限 M2 原生静态资产与有限 M3 静态 GLB 已通过各自独立夹具门禁；旧 V3.8 为历史记录。
- [判定核心实施计划](superpowers/plans/2026-08-24-asset-acceptance-decision-core.md):P0 的第一份计划,只覆盖不依赖 Blender 的判定核心。
- [V3.1 对抗性审计档案](../blender_mcp_skill_acceptance_adversarial_audit_v3_1.md)：仅记录旧提交 `102a3a2…` 的审计证据，不代表当前实现；其 D35～D43 所述 wrapper 实现实际于 `bf63c89294a5f79649a2c550331ea8987cdeab1b` 入仓。

当前 M0/M1 完成可信核心、冻结输入与真实证据封装；M2/M3 worker 已接线，有限 M3 静态 GLB 已通过独立夹具门禁。Native7 于 2026-09-23 完整门禁 19 项通过、零跳过，通用资产验收仍未完成，不得自动发布放行。

## 已认可设计与实施状态

- [安装升级与旧版本自动清理](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md)：新版验证成功后自动清理旧托管 runtime、扩展恢复副本和该 Codex 插件的历史缓存；包含清理记录、并发与回滚边界。
- [资产验收整合设计](superpowers/specs/2026-09-08-asset-acceptance-integration-design.md)：结合源码审计、外部 V4 与 2026-09-08 Blender 实测，按可信核心、原生闭环、GLB 闭环实施；包含 v2 迁移、结果归属、无环证据和回归条件。

两份设计独立实施。安装升级与旧版本自动清理已完成计划内代码、常规自动化测试及修复后的真实隔离 A→B→C/live/busy/no-op 验收；固定分发完整性通过，严格 RELEASE 因上游 outdated 未通过，正常用户 profile 仍需维护和 live 复验，LLM/跨机门禁 NOT_RUN（见 [validation](validation.md#2026-09-23-安装升级当前现场结果)）；资产验收已切换到 schema v2，M2/M3 worker 已接线，有限 M3 静态 GLB 夹具门禁已通过，Native7 于 2026-09-23 完整门禁 19 项通过、零跳过。设计中的其他能力不代表当前已完成，外部 V4 也不自动取得仓库规范地位。

## 执行计划与对抗审计

- [安装升级与自动清理执行计划](superpowers/plans/2026-09-08-installer-upgrade-cleanup.md)：独立实施；包含启动前使用锁、历史归属、孤儿缓存报告、验证后清理与崩溃续删。
- [M0/M1 可信核心执行计划](superpowers/plans/2026-09-08-asset-acceptance-core-v2.md)：v2 规范迁移、冻结合同/输入、真实工具与进程边界、唯一判定和 E/V/Q/T。
- [M2 原生闭环执行计划](superpowers/plans/2026-09-08-asset-acceptance-native.md)：依赖 M0/M1；真实重开、完整视觉、有效线框、参考门禁与签收/交付。
- [M3 GLB 闭环执行计划](superpowers/plans/2026-09-08-asset-acceptance-interchange.md)：依赖 M2；真实 Validator、逐实例预算、有限表面投影及消费者门禁。
- [计划对抗审计与实测记录](superpowers/reviews/2026-09-08-plans-adversarial-review.md)：记录发现、修复、复测范围及实施阶段仍需执行的现场门禁。

上述计划记录目标代码和完整回归步骤；仓库外原型只用于核对可执行性，当前 M3 结论以独立三文件实际门禁为准，Native7 以 2026-09-23 的 19 项完整通过记录为准，历史失败未复现且不追溯修改旧结论。

## 技术决策

- [MCP SDK v2](decisions/2026-08-07-mcp-sdk-v2-selection.md)：自研 Phase 0 Server 的 SDK 选择。

## 权威顺序

发生冲突时按以下顺序处理：

1. 代码、测试、`pyproject.toml` 和官方分发 `artifacts/manifest.json`；
2. 插件运行时说明 `plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md`；
3. 本目录中的正式文档；
4. Git 历史中的旧计划、审计和实验记录。

文档不得固定本机用户名、临时路径或已被新 manifest 取代的上游提交。版本、工具目录和产物哈希以当前 manifest 为准。
