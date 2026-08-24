# 文档中心

本目录保留当前实现的正式文档,以及资产验收方案(`acceptance/`)与实施计划(`superpowers/plans/`)。其余历史研究草稿和机器证据不在工作树中,需要追溯时使用 Git 历史。

## 使用文档

- [项目架构](architecture.md)：两条 MCP 链路、组件关系与安全边界。
- [Phase 0 只读通道安装](install.md)：安装 Blender Bridge 并注册自研 MCP Server。
- [官方 Blender MCP 分发与安装](distribute-official-blender-mcp.md)：受审分发、信任边界、安装和回滚入口。
- [官方 Blender MCP 使用](use-official-blender-mcp.md)：安装后的安全使用方式。
- [验证说明](validation.md)：自动化门禁、手工验证与结论边界。

## 资产验收方案

- [验收方案 V3.8](acceptance/blender_mcp_skill_acceptance_optimized_v3_8.md):当前生效的规范版本,含 check registry、file registry、判定公式与夹具表。同目录保留 V3.2~V3.7 与历次审计报告作为演进记录,**它们不是当前规范**。
- [判定核心实施计划](superpowers/plans/2026-08-24-asset-acceptance-decision-core.md):P0 的第一份计划,只覆盖不依赖 Blender 的判定核心。

该方案描述的通用资产验收**尚未实现**,不得用于自动发布放行。

## 技术决策

- [MCP SDK v2](decisions/2026-08-07-mcp-sdk-v2-selection.md)：自研 Phase 0 Server 的 SDK 选择。

## 权威顺序

发生冲突时按以下顺序处理：

1. 代码、测试、`pyproject.toml` 和官方分发 `artifacts/manifest.json`；
2. 插件运行时说明 `plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md`；
3. 本目录中的正式文档；
4. Git 历史中的旧计划、审计和实验记录。

文档不得固定本机用户名、临时路径或已被新 manifest 取代的上游提交。版本、工具目录和产物哈希以当前 manifest 为准。
