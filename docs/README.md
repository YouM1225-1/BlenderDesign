# BlenderDesign 文档导航与权威层级

> 更新：2026-08-08 · 当前状态：`main@e5ac559` 上的 **r17 proposed** 文档基线；Phase 0 未执行、未提交、未生成 r17 attestation。r16 tuple 曾获批准但被研究融合取代；随后一次 r17 批准又因 live 四文档已漂移而未能绑定。当前只认融合审计 §9 的精确 tuple。

本页是文档入口，不复制规范正文。发生冲突时按下表的权威层级处理；任何历史 capture、研究输入或单机测量都不能覆盖 live ROADMAP 与当前规范。

## 当前审批入口

| 角色 | 文件 | 状态与用法 |
|---|---|---|
| Live 状态与 Gate | [ROADMAP](ROADMAP.md) | 唯一 live 状态入口；当前由 B-6 阻断 Task 0 |
| 需求合同 | [URS](../Blender-Codex-需求规格说明书-v1.md) | Normative v1.16 |
| Phase 0 设计合同 | [design spec](superpowers/specs/2026-07-23-phase0-readonly-channel-design.md) | Normative v1.16 |
| 执行输入 | [Phase 0 Plan](superpowers/plans/2026-07-23-phase0-readonly-channel.md) | r17 proposed；新 tuple 批准并完成两提交 attestation 前不可执行 |
| 当前研究/基线审计 | [研究报告三融合审计](audits/2026-08-08-deep-research-report-3-integration-audit.md) | r17 当前审批证据；不等于实施结果 |
| 上一候选审计 | [r16/B-5 审计](audits/2026-08-08-r16-b5-adversarial-audit.md) | Approved but superseded；只作历史追溯 |
| SDK 决策 | [MCP SDK v2 ADR](decisions/2026-08-07-mcp-sdk-v2-selection.md) | Accepted；本系统使用 `mcp>=2,<3` |

## 文档分类

| 分类 | 入口 | 解释 |
|---|---|---|
| r15/v8 不可变历史 capture | [closeout v3](audits/2026-08-07-closeout-v3.md) · [v8 provenance](audits/evidence/2026-08-08-phase0-closeout-v8-provenance.json) | 固定 `578f49e` 工作区并由 `e5ac559` 锚定；不追踪 live 文件 |
| 官方 MCP 运行快照 | [重启后执行审计](audits/2026-08-08-roadmap-execution-and-post-restart-audit.md) · [A-4 transcript](audits/evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson) | 24 个非-render `ok`、2 个 render `not_called`；不证明 26 工具稳定或缺陷修复 |
| 平台交接与测量 | [handoff](handoff/2026-08-07-platform-optimization-handoff.md) · [macOS 测量](measurements/2026-08-07-macos-platform-optimization.md) | 固定时点、单机数据；只有已进入 URS/Plan 的条款才是合同 |
| 历史审计 | [audits/](audits/) | superseded 的“当前裁决”失效；当轮反例、发现来源和修订链继续有效 |
| 机器证据 | [evidence 索引](audits/evidence/README.md) | 按 revision、scope、canonical/alias 解读；不得把隔离预检冒充 Phase 0 实施 |
| 外部研究输入 | [report 2](research/deep-research-report-2.md) · [report 3](research/deep-research-report-3.md) | 正式归档但 non-normative；只能经独立审计后采纳 |
| 验证工具 | [spikes](../spikes/README.md) | 兼容性/配置验证辅助，不是生产代码或 Plan 执行结果 |

## 历史审计保留策略

以下报告已被后续裁决取代，但仍是 URS changelog、Plan 自审或 provenance 的来源，因此保留原路径，不物理去重：首轮 Plan 审计、Claude 修改复审、全仓复审、修复后审计、closeout v2、post-freeze 平台红队、handoff 融合审计与 r15/v8 独立核验。

evidence 中部分 GUI smoke、vendor/artifact manifest 字节相同，但文件名承载 revision/run 身份；它们不是孤儿。兼容别名 `2026-08-07-phase0-closeout-v7-provenance.json` 也保留给仓库外消费者。真正的缓存、bytecode、`.DS_Store` 不属于证据，已清理并由 `.gitignore` 排除。

## 批准与执行纪律

1. 修改 Plan/URS/spec/ROADMAP 任一字节都会使 proposed tuple 失效。
2. 项目所有者必须批准**完整且已知的** Plan/URS/spec/ROADMAP SHA 与结构/门禁计数；不能预批准未知哈希。
3. 批准后先形成 `source_commit`，再从该 commit blobs 生成并单独提交 attestation。
4. 只有 live/source blob/approved tuple 三方全等、祖先链成立且工作树 clean 后，才可执行 Task 0。
5. Phase 0 进度写执行日志与最终 validation report，不改获批 Plan 的 checkbox。
