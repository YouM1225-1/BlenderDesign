# 文档中心

本目录按文档用途区分当前实现、操作说明、现行规范、待实施方案和历史档案。
当前实现总设计仅在 `architecture.md` 维护；各操作手册保留具体流程，避免重复定义架构。

## 正式文档

- [项目架构与实现设计](architecture.md)：当前实现的唯一总设计，覆盖 MCP 链路、安装事务、摘要语义、资产验收核心和技术边界。
- [Phase 0 只读通道安装](install.md)：安装 Blender Bridge 并注册自研 MCP Server。
- [官方 Blender MCP 分发与安装](distribute-official-blender-mcp.md)：受审分发、信任边界、安装和回滚入口。
- [官方 Blender MCP 使用](use-official-blender-mcp.md)：安装后的安全使用方式。
- [验证说明](validation.md)：文档审计、自动化门禁、发行验证和现场验收。
- [Agent 执行约定](../AGENTS.md)：协作、授权、检索和交付规则；`CLAUDE.md` 引用同一文件。

## 现行规范与技术决策

- [资产验收规范 V3.8](acceptance/blender_mcp_skill_acceptance_optimized_v3_8.md)：现行详细规范，定义检查目录、文件目录、判定公式与夹具。规范表由 `tests/unit/test_asset_spec_counts.py` 校验。
- [MCP SDK v2 决策](decisions/2026-08-07-mcp-sdk-v2-selection.md)：自研 Phase 0 Server 的 SDK 选择依据和兼容边界。

资产验收运行时仍为 schema v1，目前接入 R0/R1/R5 九项检查；R2–R4 尚未接入。
规范的目标能力不等于生产实现，通用资产不能据此自动发布放行。

## 待实施设计与计划

下列方案的方向已获认可，但尚未改变生产代码行为。计划仅用于相应开发任务，
不增加安装、删除用户缓存或发布资产的授权。

| 设计 | 实施计划 | 依赖与范围 |
|---|---|---|
| [安装升级与旧版本自动清理](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md) | [升级清理计划](superpowers/plans/2026-09-08-installer-upgrade-cleanup.md) | 独立实施；受管版本归属、使用锁、验证后清理与崩溃恢复 |
| [资产验收整合设计](superpowers/specs/2026-09-08-asset-acceptance-integration-design.md) | [M0/M1 可信核心](superpowers/plans/2026-09-08-asset-acceptance-core-v2.md) | V5 目标规范与 schema v2 迁移、冻结输入、唯一判定和证据归属 |
| 同上 | [M2 原生闭环](superpowers/plans/2026-09-08-asset-acceptance-native.md) | 依赖 M0/M1；真实重开、视觉比较、审阅和交付 |
| 同上 | [M3 GLB 闭环](superpowers/plans/2026-09-08-asset-acceptance-interchange.md) | 依赖 M2；Validator、逐实例预算、有限表面投影与消费者验证 |

[计划审阅与原型验证记录](superpowers/reviews/2026-09-08-plans-adversarial-review.md)仍服务于上述待实施计划，
保留在审阅目录。仓库外原型只证明记录中的实验范围，不能作为生产功能已完成的证据。
V5/schema v2 在代码与回归迁移完成前不替代 V3.8/schema v1；外部 V4 不自动成为仓库规范。

## 历史档案

旧版资产验收方案、对应审计和初期判定核心计划统一收录于[归档目录](archive/README.md)。
档案保留原始结论及其时间、提交和实验范围，不作为当前执行指令或验收结果。

## 维护规则

- 实现事实以当前源码和行为测试为准；项目依赖以 `pyproject.toml`、`uv.lock` 为准，官方分发以 `plugins/blender-mcp-installer/artifacts/manifest.json` 及对应锁文件为准。
- 正式设计记录已实现行为，规范记录要求；二者不一致时明确列出差距，不将计划能力写成当前事实。
- 安装命令由安装技能及其引用文件维护，执行约定由 `AGENTS.md` 维护；其他文档通过链接引用，避免重复规则。
- 方案完成或被替代后，将仍有追溯价值的材料归档并更新引用；重复说明在独有信息迁移后删除。
- 文档不固定本机用户名、临时证据路径或重复的版本与工具清单。历史快照中的版本和行号仅用于追溯。
