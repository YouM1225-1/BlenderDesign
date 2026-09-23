# 资产验收与安装升级收尾执行计划

状态：Task 1–5 已完成并通过独立复审；Task 6 按用户授权快进合入 main 并推送，落地以最终 Git refs 为证。基线为开发分支 `92169b4` 与主线 `5a3bb97`；本计划按实际剩余工作收尾，不重复已经实现的旧计划任务。

## 目标与依据

完成用户指定顺序：核验未提交改动 → 修复 M2 验收 → 安装升级现场验收 → 同步主线与文档 → 完整检查 → 提交合并并推送 main。每步独立审查，最终对全部待合并修改进行对抗性审计；实际问题修复后复审，未解决问题不得宣称通过。

约束依据：现行 [整合设计](../specs/2026-09-08-asset-acceptance-integration-design.md)、[升级设计](../specs/2026-09-08-installer-upgrade-cleanup-design.md)、[V5](../../acceptance/blender_mcp_skill_acceptance_optimized_v5.md)，以及四份 2026-09-08 实施计划。已实现的 M0/M1 与有限 M3 继续沿用；M2 历史 13 pass / 6 fail / 0 skip 已由 2026-09-23 当前锁定环境的 19 pass / 0 fail / 0 skip 完整运行闭合；旧失败未复现，因旧证据缺失不追溯根因。

## Global Constraints

- 只在现有 `codex/asset-acceptance-v2-upgrade` worktree 实现；既有无关 `.claude/` 删除不能混入提交或强制清理。2026-09-23 用户要求恢复项目级 graft 钩子，这些文件已恢复为已提交版本，不再是待保留的删除。
- 输入、合同、工具、证据和交付字节必须绑定；未知能力与缺证据保持失败关闭，不删检查、不放松阈值来获得通过。
- 测试资产和机器证据放在仓库外新目录；不覆盖用户源 `.blend`，不重启或强制退出用户 Blender/Codex。
- 安装遵循安装技能的受信固定提交和私有工作树流程。真实安装、现场 live、模拟测试与发行门禁分开报告，不替代。
- 每个提交前运行 `bash scripts/checks.sh`，结果必须包含 `ALL CHECKS PASSED`；最后源码/文档修改后 `graft build .`，交付前 `graft check .` 退出 0。
- final-fix 实现轮的授权仅包括限定文件提交，不合并或推送 main；独立复审通过后，用户于 2026-09-23 明确授权 Task 6 合并到 main 并正常推送，不 force push、不建 PR。审计有问题就修复复审，不以技能轮数上限为由搁置已确认问题。
- 每任务只派一个实现者，禁止实现者自行派子代理；独立审查由控制器安排。报告保存至本计划 SDD workspace。

## Task 1: 核验并收尾现有未提交改动

读取 `git diff HEAD`，逐项核验 11 个相关改动文件；保留 4 个 `.claude/` 删除原样。范围为 controller 输出枚举失败处理、marketplace 当前缓存 lease 的创建与身份核验、对应测试/计划和插件版本；本收尾计划随该包提交。

确认修复实际风险：`os.walk` 读错必须失败关闭；已有精确注册、cold no-op 与恢复路径的 cache lease 不缺失，重验路径替换竞争；已有新增 GLB/判定回归有效。运行相关测试，修复明确问题，运行完整仓库门禁与 graft。只暂存相关文件，自审并提交。报告命令、结果和风险，等待独立 spec/quality 审查。

## Task 2: 修复 M2 原生资产验收

参照原生计划 Task 7 与 V5，用锁定 Python、真实 Blender 和仓库外新证据目录运行 `RUN_ASSET_NATIVE=1` 的 `tests/integration/test_asset_native.py`，不得 skip。先保存具体失败和输入/工具/代码身份，再修复根因。

不得通过减弱支持合同、删除好资产、跳过用例、扩大阈值或伪造图像/签收来通过。正资产通过技术门禁，未业务签收为 NEEDS_REVIEW；坏几何、缺件、证据变更与假签收应按合同拒绝。真实运行验证 exact-byte reopen、跨进程、参考/视觉及 E/V/Q/T/D 链。补必要回归，更新 V5/native 计划的当前结果，运行完整检查及 graft 后提交；独立审查后继续。

Task 2 当前执行记录（2026-09-23）：在基线 `117b133`、Python 3.13.13、Blender 5.2.0 LTS / `fbe6228777e7` 上，完整 Native 门禁为 `19 passed in 1018.12s`，零跳过；聚焦 Native 回归 210 项通过。运行时源码、支持合同、测试与阈值均未修改。证据位于 `/private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task2-baseline`，详见 [M2 当前执行记录](2026-09-08-asset-acceptance-native.md#当前执行结果2026-09-23)。当前有限原生路径通过不代表真实业务签收、安装/live 或 RELEASE 通过；独立审查仍由控制器推进。

## Task 3: 完成安装升级现场验收

先阅读安装 skill 和 workflow，核对授权、受信提交、运行平台与工具。按升级设计和安装计划核验真实 A→B→C 内容变化的安装/注册/验证后清理、busy 保护、当前 MCP/扩展可用、非目标配置不变；使用真实工具和有明确归属的隔离测试状态，不复制普通 Codex 凭据。

执行适用 `RELEASE=1` 分发门禁；单列当前用户的磁盘安装和 live 验证。任何必要关闭应用/维护交接都先完成可独立工作并报告具体原因，不擅自终止当前会话。若发行最新性与固定版完整性结果不同，保留两者事实，不修改规则绕过。发现代码问题则最小修复并回归。把真实证据与未完成项写入报告，不能用模拟结果关闭现场门禁。


Task 3 当前执行记录（2026-09-23）：真实冷首装与 native plugin add 提前 prune 缺陷均已修复并覆盖回归，Phase 0 httpx2/httpcore2 定向升级至 2.12.0 以闭合依赖审计。受审不可变候选 C `f23c8a783b10be6e17c89aed5f7527caa528a7ec` 在无凭据自有 profile 完成真实 A→B→C、MCP 26 工具/Blender 只读验证、验证后物理删除、busy 保留/释放后续删、同内容 no-op、只读状态保持。正常用户 inspect exact=false、live 未通过，未擅自维修/退出；一次性 LLM 和第二台 Mac 为 NOT_RUN。固定分发完整性和依赖审计通过，严格 RELEASE 因上游 outdated 仍退出 1，不具备发行资格。详见 [validation 当前结果](../../validation.md#2026-09-23-安装升级当前现场结果)；本任务交付与后续独立审查不等于发布放行。

Task 3 审查修订：修复 publication 后中断遗留敏感配置快照，持久绑定 stage 身份并安全续删；候选 `a4bf15db6b565b08de37b76439b96d89e7e7add3` 在真实自有 profile 完成同产物 C→D runtime no-op、VERIFY/FINALIZE，及三个 native 中断/重试无快照残留。首次 C 身份与修订候选分别保留，RELEASE/正常 profile/NOT_RUN 限制不变。

## Task 4: 同步主线及正式文档

先确认并获取 origin/main 最新状态，将 main 的独有提交合入开发分支，保留新主线的文档整合与 quoted interpreter 修复，并保留开发分支实现。解决冲突时以实际实现与验证结果同步 README、docs/README、architecture、validation、现行 V5 和四份计划状态。历史归档保留原结论。

核对链接、命令、计划状态与实现一致；不将未运行现场检查记为通过。完成范围检查、完整门禁、graft 后提交并独立审查。

Task 4 当前进展（2026-09-23）：已从远端复核 `origin/main=5a3bb97`，并将其合入升级分支。冲突按正式文档职责逐段整合：保留主线文档收敛、历史归档、`AGENTS.md` 唯一执行入口和 quoted-interpreter 夹具修复；同步 schema v2、有限 M2 的 19/0/0 真实门禁、M3 旧有限证据与 Task 5 待跑新三文件门禁，以及安装器 A→B→C/C→D 的当前有限现场结果。严格 RELEASE 仍因 upstream outdated 退出 1，正常 profile 未验证，LLM/第二台 Mac/legacy user-app handoff 仍为 `NOT_RUN`。本任务不变更上游 pin，不把工具准备写成 M3 通过；完整门禁、graft 与合并提交结果见 Task 4 报告。
合并后聚焦 distribution 回归 150 项通过；普通完整门禁为 1150 passed / 27 explicit skips，distribution 为 1034 passed，末行 `ALL CHECKS PASSED`。本次合并未改动 installer/runtime/artifacts、`uv.lock` 或 acceptance 运行时字节，plugin 版本仍为 `1.0.0+codex.20260922175350`；最终合并提交与树身份需由 Task 5 单独记录，不把提交身份变化误写成生产字节变化。

## Task 5: 完整检查与全分支对抗性审计

运行最终候选树的 `bash scripts/checks.sh`、受影响的真实 Native/M3 与适用发行门禁，记录提交/代码身份；同一代码已取得有效结果不无谓重复。最后修改后 build/check graft。

对 main 合入前的全部功能 diff 进行最强模型全分支对抗性审计，重点检查证据伪造/缺失、判定绕过、资源/进程边界、清理归属及锁竞争、验证后内容漂移。审查实现和测试合同，不仅审阅报告。每项实际问题由实现者修复、覆盖测试、独立复审；全部已确认问题闭合才放行。更新结果与计划状态。

Task 5 final-fix（2026-09-23）：修复 I1 durable config-stage 重试、I2 optional explicit rejection 和 I3 Blender 5.2 glTF 内容闭包。Focused 109 项通过；最终真实 Native 完整门禁 21 passed/0 failed/0 skipped，覆盖 Native review 与 exact-D delivery、optional approved/rejected 恢复；最终真实 M3 三文件门禁 8 passed/0 failed/0 skipped，实际锁定真实应用闭包，结果详见 [final-fix 报告](../sdd/2026-09-22-acceptance-upgrade-closeout/final-fix-report.md)。普通完整门禁为 1173 passed / 29 个常规 integration skips，distribution 为 1046 passed，末行 `ALL CHECKS PASSED`。实际 Codex 新 stage 窗口中断/重试和隔离自有 profile installer-version-only install/verify/finalize 均在 controller 核验的固定候选 `6ad6638e77f0cebd226172f793301112bdd7322f` 上通过；真实 Codex 复用同一 recovery ID，重试不再调用 Codex，旧缓存 inode 和未知 stage 保留。隔离 profile 从旧插件版本升级，真实 Blender 5.2 / Codex 验证 26 工具并 finalize，bundle、runtime、扩展与偏好保持不变。完整现场证据和身份见 [final-fix 报告](../sdd/2026-09-22-acceptance-upgrade-closeout/final-fix-report.md)。报告同步后的完整 checks（1173 passed / 29 skipped，distribution 1046 passed，`ALL CHECKS PASSED`）与 graft 已完成并提交。严格 RELEASE 不在本任务重跑，沿用 upstream outdated 的未通过状态；normal profile、LLM、第二台 Mac、legacy user-app handoff 限制不变。

Task 5 独立复审（2026-09-23）：对 `140fd69..f8e7692` 的独立只读复审结论为 Ready to merge: Yes，I1/I2/I3 均关闭，无 Critical/Important。复审在仓库外副本运行相关测试 122 passed；在 `140fd69` 生产代码上同一批新用例 31 failed（全部为 I1/I2/I3 新用例），确认回归有效；原 I2 探针在 `98b9140` 得到 SHIP、在修复后得到 REJECTED 且拒绝交付。三项 Minor 为文档证据指针：Native/M3 最终运行日志与时长、已清理的外部证据根、本计划状态，均已在文档中修正。未确认疑点：CODEX_HOME 与 HOME 跨卷时，config stage rename 可能以 EXDEV 失败关闭；真实 Codex 从无 config.toml 起步的路径仅由 fake Codex 覆盖；最终真实门禁日志未记录 tree 身份，只能以 mtime 与工作树等于 `6ad6638` 推断绑定。

## Task 6: 提交合并到 main 并推送

核对审计结果、暂存范围、`git diff --cached --check`、分支和远端。主工作树的 `.claude/` 文件已按用户要求恢复为已提交版本，合入时不得覆盖或混入无关改动；将已验证候选快进合入 main，核对合并树与已测树一致。必要时复测合并引入变化。

推送 origin main，核验远端 HEAD 与本地 main 一致。报告提交、测试、真实验收证据与限制；不删除带未提交内容的 worktree，不强制清理任何历史分支或其他计划 workspace。
