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

- [验收方案 V3.8](acceptance/blender_mcp_skill_acceptance_optimized_v3_8.md):当前生效的规范版本,含 check registry、file registry、判定公式与夹具表。同目录保留 V3.2~V3.7 与历次审计报告作为演进记录,**它们不是当前规范**。
- [判定核心实施计划](superpowers/plans/2026-08-24-asset-acceptance-decision-core.md):P0 的第一份计划,只覆盖不依赖 Blender 的判定核心。
- [V3.1 对抗性审计档案](../blender_mcp_skill_acceptance_adversarial_audit_v3_1.md)：仅记录旧提交 `102a3a2…` 的审计证据，不代表当前实现；其 D35～D43 所述 wrapper 实现实际于 `bf63c89294a5f79649a2c550331ea8987cdeab1b` 入仓。

当前只实现了不依赖 Blender 的 P0 判定核心与 R0/R1/R5 九项检查；方案中的通用资产验收仍未完成，不得用于自动发布放行。

## 已认可方向的待实施设计

- [安装升级与旧版本自动清理](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md)：新版验证成功后自动清理旧托管 runtime、扩展恢复副本和该 Codex 插件的历史缓存；包含清理记录、并发与回滚边界。
- [资产验收整合设计](superpowers/specs/2026-09-08-asset-acceptance-integration-design.md)：结合源码审计、外部 V4 与 2026-09-08 Blender 实测，按可信核心、原生闭环、GLB 闭环实施；包含 v2 迁移、结果归属、无环证据和回归条件。

两份设计独立实施，目前均未改变代码行为。资产验收运行时仍为 schema v1，现行规范仍是 V3.8；后续按整合设计成套迁移到 V5 规范与 schema v2。设计中的目标能力不代表当前已完成，外部 V4 也不自动取得仓库规范地位。

## 技术决策

- [MCP SDK v2](decisions/2026-08-07-mcp-sdk-v2-selection.md)：自研 Phase 0 Server 的 SDK 选择。

## 权威顺序

发生冲突时按以下顺序处理：

1. 代码、测试、`pyproject.toml` 和官方分发 `artifacts/manifest.json`；
2. 插件运行时说明 `plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md`；
3. 本目录中的正式文档；
4. Git 历史中的旧计划、审计和实验记录。

文档不得固定本机用户名、临时路径或已被新 manifest 取代的上游提交。版本、工具目录和产物哈希以当前 manifest 为准。
