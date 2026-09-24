# 文档中心

本目录按文档用途区分当前实现、操作说明、现行规范与设计、待实施方案和历史档案。
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

有限 M2 原生静态路径在最终修复候选的完整门禁中 `21 passed`/0 failed/0 skipped；有限 M3 静态 GLB L0 在最终修复候选的真实三文件门禁中 `8 passed`/0 failed/0 skipped。固定修复候选已通过真实 Codex stage 中断恢复及隔离自有 profile 的 installer-version-only install/verify/finalize；其身份、现场证据与完整门禁见 [closeout 修复报告](archive/closeout/2026-09-22/final-fix-report.md)。两者是独立门禁，只证明各自声明范围；最终修复已通过独立复审，业务签收仍单独控制资产放行，通用资产仍不能自动发布放行。

## 现行设计

| 设计 | 状态与范围 |
|---|---|
| [安装升级与旧版本自动清理](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md) | 已实施 journal、使用锁、私有注册 staging、条件发布、验证后清理与崩溃恢复 |
| [资产验收整合设计](superpowers/specs/2026-09-08-asset-acceptance-integration-design.md) | 已实施 schema v2 可信核心（M0/M1）、有限静态 M2 原生与 M3 GLB L0；新类型、动画、L1/L2 或更多消费者按其准入规则另行设计与验收；未获通用业务批准 |

安装器的隔离 A→B→C 与修订 C→D 现场验证已覆盖真实 Codex 注册、26 个 MCP 工具、Blender 只读调用、busy/no-op、finalize 及敏感快照恢复。固定分发完整性与三份依赖审计通过；严格 `RELEASE=1` 因上游 outdated 退出 1。2026-09-24 正常用户 profile 已修复：首代无使用锁的 legacy runtime 已完成外部维护交接，inspect 为 `exact=true`，live VERIFY（26 工具、Blender 只读调用）与注册验证通过；随后以 `112f486`（状态 JSON 32 MiB 上限与跨启动稳定的 inode 租约）重新 install/VERIFY/FINALIZE，工作流 `complete`，删除 11 个 runtime recovery、6 个扩展 recovery 与 2 个旧插件 cache，旧 journal 全部收尾；手工补丁、源码改动、整树副本与首装前的 recovery 当时按设计保留为未验证发现，其后按操作者要求与无法证明作用域的旧注册目录一并移入废纸篓的独立文件夹（由操作者自行清空），只读重跑发现为 0。主机重启使数据卷设备号重编后，launcher 与缓存入口照常可用；因 Codex 自动更新而重新 install 后，VERIFY 与 FINALIZE 通过，旧版本全部清理。LLM/第二台 Mac 仍为 `NOT_RUN`。详见 [验证说明](validation.md#2026-09-23-安装升级当前现场结果)。

## 待实施计划

当前没有进行中的实施计划。2026-09-08 的 M0/M1、M2、M3 与升级清理计划、对应审阅记录及 2026-09-22 收尾计划均已完成并归档；外部 V4 不自动成为仓库规范。

## 历史档案

旧版资产验收方案、对应审计、已完成的实施计划与收尾审查统一收录于[归档目录](archive/README.md)。
档案保留原始结论及其时间、提交和实验范围，不作为当前执行指令或验收结果。

## 维护规则

- 实现事实以当前源码和行为测试为准；项目依赖以 `pyproject.toml`、`uv.lock` 为准，官方分发以 `plugins/blender-mcp-installer/artifacts/manifest.json` 及对应锁文件为准。
- 正式设计记录已实现行为，规范记录要求；二者不一致时明确列出差距，不将计划能力写成当前事实。
- 安装命令由安装技能及其引用文件维护，执行约定由 `AGENTS.md` 维护；其他文档通过链接引用，避免重复规则。
- 阶段状态变化时更新对应计划与本索引；通用文档同步和版本纪律遵循 [AGENTS.md](../AGENTS.md)，不另建平行设计或计划。
- 方案完成或被替代后，将仍有追溯价值的材料归档并更新引用；重复说明在独有信息迁移后删除。
- 文档不固定本机用户名、临时证据路径或重复的版本与工具清单。历史快照中的版本和行号仅用于追溯。
