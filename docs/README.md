# 文档中心

本目录按文档用途区分当前实现、操作说明、现行规范、待实施方案和历史档案。
当前实现总设计仅在 `architecture.md` 维护；各操作手册保留具体流程，避免重复定义架构。

## 正式文档

- [项目架构与实现设计](architecture.md)：当前实现的唯一总设计，覆盖 MCP 链路、安装事务、摘要语义、资产验收核心和技术边界。
- [Phase 0 只读通道安装](install.md)：安装 Blender Bridge 并注册自研 MCP Server。
- [官方 Blender MCP 分发与安装](distribute-official-blender-mcp.md)：受审分发、信任边界、安装和回滚入口。
- [官方 Blender MCP 使用](use-official-blender-mcp.md)：安装后的安全使用方式。
- [验证说明](validation.md)：文档审计、自动化门禁、发行验证和现场验收。
- [Agent 执行约定](../AGENTS.md)：协作、授权、检索和交付规则；`CLAUDE.md` 仅引用同一文件。

## 现行规范与技术决策

- [资产验收规范 V5](acceptance/blender_mcp_skill_acceptance_optimized_v5.md)：当前 schema v2 规范；M0/M1 已实现，M2/M3 worker 已接线。
- [MCP SDK v2 决策](decisions/2026-08-07-mcp-sdk-v2-selection.md)：自研 Phase 0 Server 的 SDK 选择依据和兼容边界。

有限 M2 原生静态路径在锁定环境的完整门禁中 `19 passed`/0 failed/0 skipped；有限 M3 静态 GLB L0 在候选 `98b9140` 的真实三文件门禁中 `8 passed`/0 failed/0 skipped。两者是独立门禁，只证明各自声明范围；测试 reviewer 与交付夹具不构成业务批准，通用资产仍不能自动发布放行。

## 设计与计划状态

| 设计 | 实施计划 | 依赖与范围 |
|---|---|---|
| [安装升级与旧版本自动清理](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md) | [升级清理计划](superpowers/plans/2026-09-08-installer-upgrade-cleanup.md) | 已实施 journal、使用锁、私有注册 staging、条件发布、验证后清理与崩溃恢复 |
| [资产验收整合设计](superpowers/specs/2026-09-08-asset-acceptance-integration-design.md) | [M0/M1 可信核心](superpowers/plans/2026-09-08-asset-acceptance-core-v2.md) | 已完成 schema v2、冻结输入、唯一判定和证据归属 |
| 同上 | [M2 原生闭环](superpowers/plans/2026-09-08-asset-acceptance-native.md) | 有限静态支持已通过当前独立门禁；未获通用业务批准 |
| 同上 | [M3 GLB 闭环](superpowers/plans/2026-09-08-asset-acceptance-interchange.md) | 有限静态 L0 worker 已实现并通过当前三文件实际门禁；未获通用业务批准 |

安装器的隔离 A→B→C 与修订 C→D 现场验证已覆盖真实 Codex 注册、26 个 MCP 工具、Blender 只读调用、busy/no-op、finalize 及敏感快照恢复。固定分发完整性与三份依赖审计通过；严格 `RELEASE=1` 因上游 outdated 退出 1，正常用户 profile 仍未精确匹配，LLM/第二台 Mac/legacy 交接为 `NOT_RUN`。详见 [验证说明](validation.md#2026-09-23-安装升级当前现场结果)。

[计划审阅与原型验证记录](superpowers/reviews/2026-09-08-plans-adversarial-review.md)保留在审阅目录。计划和原型记录的未实施能力不是当前事实；外部 V4 不自动成为仓库规范。

## 历史档案

旧版资产验收方案、对应审计和初期判定核心计划统一收录于[归档目录](archive/README.md)。
档案保留原始结论及其时间、提交和实验范围，不作为当前执行指令或验收结果。

## 维护规则

- 实现事实以当前源码和行为测试为准；项目依赖以 `pyproject.toml`、`uv.lock` 为准，官方分发以 `plugins/blender-mcp-installer/artifacts/manifest.json` 及对应锁文件为准。
- 正式设计记录已实现行为，规范记录要求；二者不一致时明确列出差距，不将计划能力写成当前事实。
- 安装命令由安装技能及其引用文件维护，执行约定由 `AGENTS.md` 维护；其他文档通过链接引用，避免重复规则。
- 阶段状态变化时更新对应计划与本索引；通用文档同步和版本纪律遵循 [AGENTS.md](../AGENTS.md)，不另建平行设计或计划。
- 方案完成或被替代后，将仍有追溯价值的材料归档并更新引用；重复说明在独有信息迁移后删除。
- 文档不固定本机用户名、临时证据路径或重复的版本与工具清单。历史快照中的版本和行号仅用于追溯。
