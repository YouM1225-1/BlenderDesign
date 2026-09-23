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

V3.2–V3.7 及对应报告原位于 `docs/acceptance/`。V3.8 保留原路径作为迁移历史；现行规范为
[V5](../acceptance/blender_mcp_skill_acceptance_optimized_v5.md)。

V3.1 原文标注的审计基线是 `102a3a2efe8aaf2f7dbdc6dd216f621951812d14`；
其中 D35–D43 描述的 wrapper 实现实际于 `bf63c89294a5f79649a2c550331ea8987cdeab1b` 入仓。
原文是历史记录，不能据此将后续实现归入更早的提交。

## 初期实施计划

[2026-08-24 资产验收判定核心计划](plans/2026-08-24-asset-acceptance-decision-core.md)
原位于 `docs/superpowers/plans/`，记录 schema v1/P0 核心的初期实施与复核过程。
当前核心行为由源码和正式设计描述；后续的 M0/M1、M2、M3 计划也已完成并归档于下文。
原计划中的复选框和后续建议不作为当前任务状态。

## 2026-09 资产验收 v2 与安装升级清理

2026-09-23 归档。以下计划均已实施，现行设计仍为
[升级清理设计](../superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md)与
[资产验收整合设计](../superpowers/specs/2026-09-08-asset-acceptance-integration-design.md)。

| 档案 | 历史定位 |
|---|---|
| [升级清理计划](plans/2026-09-08-installer-upgrade-cleanup.md) | journal、使用锁、验证后清理的实施计划 |
| [M0/M1 可信核心计划](plans/2026-09-08-asset-acceptance-core-v2.md) | schema v2 合同、冻结输入、唯一判定与证据链 |
| [M2 原生闭环计划](plans/2026-09-08-asset-acceptance-native.md) | 有限静态原生资产；含 2026-09-23 当前执行结果 |
| [M3 GLB 闭环计划](plans/2026-09-08-asset-acceptance-interchange.md) | 有限静态 GLB L0 投影与 Validator |
| [计划审阅与原型验证记录](reviews/2026-09-08-plans-adversarial-review.md) | 上述计划编写期的对抗审阅与仓库外原型 |
| [收尾执行计划](plans/2026-09-22-acceptance-upgrade-closeout.md) | Task 1–6：M2 复验、安装升级现场验收、主线同步、全分支审计与交付 |
| [最终全分支审查](closeout/2026-09-22/final-review.md) | 冻结候选 `98b9140` 的审查，确认 I1/I2/I3 三个 Important |
| [最终修复报告](closeout/2026-09-22/final-fix-report.md) | I1/I2/I3 修复、真实 Native/M3 门禁与现场证据 |
| [最终修复复审](closeout/2026-09-22/final-fix-rereview.md) | `140fd69..f8e7692` 独立复审及文档增量复审，结论 Ready to merge: Yes |

收尾计划的 Task 6 已于 2026-09-23 完成：`main` 从 `5a3bb97` 快进至
`18aab986438ccda73f7b4e0d345708536bae2981` 并正常推送，本地与远端 refs 一致。交付时
严格 RELEASE 仍因上游 outdated 未通过，正常用户 profile 未修复，LLM/第二台 Mac/legacy
交接为 `NOT_RUN`。三份收尾审查原为仓库外 SDD 工作区记录，归档时仅将本机主目录写作 `~`。
其中的临时证据路径多已清理，仅供追溯。

## 保留与合并规则

仍服务于未完成任务的设计、计划和审阅记录保留在 `docs/superpowers/`，不因日期较早而归档。
重复说明在迁移独有信息后删除；既有 Agent 工作流说明已合并到 `AGENTS.md` 与
[验证说明](../validation.md)，不再维护第二份执行约定。
