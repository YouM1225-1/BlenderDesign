# 历史文档档案

本目录保存已被后续规范或计划替代、仍具有追溯价值的材料。归档日期为 2026-09-09。
当前实现见[项目架构与实现设计](../architecture.md)，现行规范与待实施任务见[文档中心](../README.md)。

## 使用范围

档案中的结论、版本、测试数量、源码行号和操作步骤仅适用于原文标注的历史基线。
归档不更新其技术结论，不使其中的命令成为当前执行指令，也不证明当前工作树已通过验收。
归档时保留正文，仅修正指向仓库文件的相对链接；历史行号不保证仍对应当前源码位置。

## 资产验收演进

| 档案 | 历史定位 |
|---|---|
| [V3.1 方案与对抗审计](acceptance/blender_mcp_skill_acceptance_adversarial_audit_v3_1.md) | 原位于仓库根目录；记录旧提交与当时实验 |
| [V3.2 方案](acceptance/blender_mcp_skill_acceptance_optimized_v3_2.md) | V3.8 之前的方案版本 |
| [V3.3 方案](acceptance/blender_mcp_skill_acceptance_optimized_v3_3.md) | 方案修订 |
| [V3.3 审计](acceptance/blender_mcp_skill_acceptance_optimized_v3_3_audit_report.md) | 对应版本的缺陷与建议 |
| [V3.4 方案](acceptance/blender_mcp_skill_acceptance_optimized_v3_4.md) | 双路复审后的修订 |
| [V3.5 方案](acceptance/blender_mcp_skill_acceptance_optimized_v3_5.md) | 全量审计前的修订 |
| [V3.5 审计](acceptance/blender_mcp_skill_acceptance_optimized_v3_5_audit_report.md) | 对应版本的审计报告 |
| [V3.5 审计复验](acceptance/blender_mcp_skill_acceptance_v3_5_audit_verification.md) | 对报告结论的复核 |
| [V3.6 方案](acceptance/blender_mcp_skill_acceptance_optimized_v3_6.md) | 后续修订 |
| [V3.7 方案](acceptance/blender_mcp_skill_acceptance_optimized_v3_7.md) | V3.8 的前序版本 |

V3.2–V3.7 及对应报告原位于 `docs/acceptance/`。现行
[V3.8 规范](../acceptance/blender_mcp_skill_acceptance_optimized_v3_8.md)仍保留原路径，供规范测试读取。

V3.1 原文标注的审计基线是 `102a3a2efe8aaf2f7dbdc6dd216f621951812d14`；
其中 D35–D43 描述的 wrapper 实现实际于 `bf63c89294a5f79649a2c550331ea8987cdeab1b` 入仓。
原文是历史记录，不能据此将后续实现归入更早的提交。

## 初期实施计划

[2026-08-24 资产验收判定核心计划](plans/2026-08-24-asset-acceptance-decision-core.md)
原位于 `docs/superpowers/plans/`，记录 schema v1/P0 核心的初期实施与复核过程。
当前核心行为由源码和正式设计描述；后续开发使用文档中心中的 M0/M1、M2、M3 计划。
原计划中的复选框和后续建议不作为当前任务状态。

## 保留与合并规则

仍服务于未完成任务的设计、计划和审阅记录保留在 `docs/superpowers/`，不因日期较早而归档。
重复说明在迁移独有信息后删除；既有 Agent 工作流说明已合并到 `AGENTS.md` 与
[验证说明](../validation.md)，不再维护第二份执行约定。
