# 全分支独立审查：preliminary

Ready to merge: **No**。冻结候选有三个 Important 问题，尚待实现者修复及独立复审；Task 5 最终文档增量、完整门禁与候选身份包尚未收齐。本报告不能作为合入或发布批准。

## 审查身份与范围

- Base：`5a3bb97765cb2002d049a4982df7c1e8fff2d8ed`。
- 冻结 Head：`98b91403d30ee3e2023831720619cbea6bd558fa`。
- 全差异：`review-5a3bb97..98b9140.diff`，121 个文件，57 个分支独有提交；审查覆盖整个功能分支，不只 closeout 提交。
- 固定源码副本：`/var/folders/pl/bpv2s_ks1mz24cd8ks4gblbr0000gn/T/blender-final-review-98b9140-nrxygwf4`，由该 Head 的 Git archive 创建。
- 审查者：`/root/closeout_final_review`。未修改源码、index 或 HEAD，未派子代理，未运行安装/清理/场景操作。仓库内只写本报告；最小探针及证据在外部新目录。四个既有 `.claude/` 删除保持原样。
- 依据：V5、asset integration design、installer upgrade design、当前 architecture/validation、Task 5 brief。实施计划的大段示例代码按历史提案处理，不作为当前实现。

## 已确认问题

### Important I1：未落 publication 记录的配置 stage 会阻断后续注册重试

位置：`plugins/blender-mcp-installer/scripts/project_marketplace.py:719–731`，恢复入口在 `:658–673`。

配置 stage 的 `_atomic_write` 已经成功，但 `publication.json` 尚未写入时进程退出，下一次重试先清理旧 native stage，然后再次执行 native Codex。若目标 marketplace 的合法元数据（例如 `last_updated`）变化，新 `post_raw` 不再与既有 `.registration.stage` 字节相同；`:721–722` 永久报 `registration config stage requires recovery`，既无 publication 数据可恢复，也没有该状态的自动完成路径。即使没有外部配置编辑、旧 cache 完全有效，注册升级也无法完成，私有暂存配置继续保留。

已复现：调用现有 `registration` fixture；仅让 fake native 在每次目标 marketplace add 后增加不同的合法 `last_updated`；在原 `_atomic_write` 写完 `.registration.stage` 后注入一次退出。恢复正常写入后，连续两次 `_register` 重试都报上述错误。live config 未变化、旧 cache inode 保留、publication 不存在、config stage 存在。这是恢复功能缺陷，不是误删发现。这里模拟了 native 可变元数据，不宣称已经对真实 Codex 执行本中断点。

- 证据：`/private/tmp/blender-review-stage-retry-t1hunqrs/result.json`，同目录保留 fixture 状态。
- 可重复脚本：`/private/tmp/blender-review-stage-retry-t1hunqrs/reproduce.py`。
- 现有测试缺口：`test_registration_staging.py` 的 `cache_published` 注入在 stage 写入**之前**，publication 相关注入在 publication 写入**之后**；遗漏两者之间的 durable stage 窗口。
- 修复方向：在这个窗口保留可验证的原发布数据，或以持久归属和原 config/cache 身份为依据安全重建未发布 stage；不能通过无条件覆盖 stage 或采用外部漂移来绕过冲突检查。补 stage 写后/publication 写前、合法元数据变化、外部配置或 stage 身份漂移的回归。

### Important I2：可选审阅的明确 rejected 会封装为 SHIP 并允许交付

位置：`acceptance/evidence.py:293–296`；合法政策入口 `acceptance/contract.py:224–243`，公开恢复入口 `acceptance/evidence.py:333`。

`review.required=false` 允许配置非空 `reviewer_ids`。当提供有效 review 时，else 分支调用 `_validate_review`，但忽略其 False 返回值，随后无条件设 `SHIP`。`required` 可以决定缺少 review 时是否必须等待，不能把实际收到且身份正确的拒收改成批准。设计 `docs/superpowers/specs/2026-09-08-asset-acceptance-integration-design.md:100` 明确要求：技术通过后业务审阅明确拒收也输出 REJECTED，且不改写技术 summary。

已从公开 API 路径复现：合法可选 reviewer 合同执行真实受控 Python worker fixture，在 `summary.json` durable 写完后模拟退出；随后用正确 C/S/D/E/V 绑定的 `rejected` 记录调用公开 `finish_review`，得到 `SHIP`；公开 `deliver` 成功。未修改任何既有合同、summary 或 payload，技术 summary 仍为 true。普通无中断 CLI 会直接完成可选审阅流程，本发现不是声称它能重新审阅已经完成的 T；复现利用的是完成 T 前可到达的恢复状态。

- 证据：`/private/tmp/blender-review-optional-reject-e5ajlxb4/result.json`；同目录 `evidence/` 保留完整链及实际 `delivered.blend`。
- 可重复脚本：`/private/tmp/blender-review-optional-reject-e5ajlxb4/reproduce.py`。
- 现有测试缺口：required reviewer 的 rejected 和底层 `_validate_review` 的 False 有测试，但没有 optional reviewer rejected 对最终 T/交付的测试。
- 修复方向：存在 review 时统一消费 `_validate_review` 的批准结果；仅用 `required` 决定缺失 review 是否阻塞。回归应证明 optional rejected 为 REJECTED、V 字节不变且 `deliver` 拒绝，同时保留 optional absent/approved 的正确行为。

### Important I3：公开合同可遗漏实际 Blender glTF 模块锁并通过工具/计划校验

位置：`acceptance/toolchain.py:50–59`，`acceptance/interchange_plan.py:18–43`；真实 fixture 额外补锁位于 `tests/integration/interchange_runtime_support.py:53–61`。

`measure_tool` 只散列调用方声明的 `files`，只有 acceptance 代码有必需成员闭包；interchange 计划强制 Node validator 的必需包成员，却没有同等校验实际 `io_scene_gltf2` 导出/导入模块。Blender 二进制 hash/version/build 不会随这些外部 Python 模块内容变化而变化。合同遗漏该模块后，R0/R5 无法检测它的变化，削弱工具内容身份和运行可复核性。设计 `docs/superpowers/specs/2026-09-08-asset-acceptance-integration-design.md:73–81` 要求真实工具的版本/build、脚本/包内容身份以及大型应用的经审核分发身份和受支持模块清单。

当前真实 M3 fixture **原本已经声明了完整 126 个 glTF Python 成员**，不能把本问题解释为该次 M3 未锁模块或既有结果无效。缺陷在公开合同入口不能强制这项前提：复制 Task 5 刚产生的真实正例合同至外部目录，删去全部 126 个 `io_scene_gltf2` 成员、保留 5 个 Blender worker 文件后，冻结版本的 `validate_document`、`build_interchange_plan` 和真实 Blender 的 `measure_tool` 均接受。只读真实工具，没有修改 live 应用，也没有重跑场景；该探针证明缺失闭包仍被接受，不声称完成了篡改 exporter 后的全资产运行。

- 原真实合同：`/private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task5-m3.rCWtQP/pytest/test_real_interchange_full_cha0/contract.json`。
- 证据：`/private/tmp/blender-review-app-closure-1jnf440c/result.json` 和 `reduced-contract.json`。
- 可重复脚本：`/private/tmp/blender-review-app-closure-1jnf440c/reproduce.py`。
- 修复方向：从支持的应用布局和本次启用的能力推导必需模块闭包，与合同中的经审核锁定清单核对，失败关闭缺失、额外未绑定可执行成员及内容漂移；在 R0 和 R5 都执行。无需扩展到所有平台或新增隔离等级。覆盖“fixture 完整列表”“删一个/全部成员”“模块新增或运行中改变”的行为回归。

Critical：无确认发现。Minor：无确认发现。以上三个 Important 均已即时反馈 controller，尚未修复或复审关闭。

## 复现执行方式

用冻结源码及既有 Python 执行，不会写入源码树；每次脚本新建自己的外部目录：

```bash
REVIEW_PYTHON=~/Developer/BlenderDesign/.worktrees/acceptance-v2-upgrade/.venv/bin/python
REVIEW_SOURCE=/var/folders/pl/bpv2s_ks1mz24cd8ks4gblbr0000gn/T/blender-final-review-98b9140-nrxygwf4
PYTHONDONTWRITEBYTECODE=1 "$REVIEW_PYTHON" /private/tmp/blender-review-stage-retry-t1hunqrs/reproduce.py "$REVIEW_SOURCE"
PYTHONDONTWRITEBYTECODE=1 "$REVIEW_PYTHON" /private/tmp/blender-review-optional-reject-e5ajlxb4/reproduce.py "$REVIEW_SOURCE"
PYTHONDONTWRITEBYTECODE=1 "$REVIEW_PYTHON" /private/tmp/blender-review-app-closure-1jnf440c/reproduce.py "$REVIEW_SOURCE" /private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task5-m3.rCWtQP/pytest/test_real_interchange_full_cha0/contract.json
```

## 覆盖与优点

已逐模块审读全部改动生产代码，测试按生产风险审读具体构造、断言及负例，未把测试名称或历史通过报告当作正确性证明。测试审读是风险抽样，不声称逐行阅读了 13,468 行全部测试增量。

| 范围 | 生产覆盖 | 具体核验与测试证据 |
|---|---|---|
| v2 输入/合同/计划 | `contract.py`、`input_bundle.py`、`plan.py`、`check_registry.py`、`toolchain.py` | 封闭精确类型、深不可变、source digest、无链接父链、macOS 物理别名/前瞻路径、预算与 baseline；读 `test_asset_v2_contract/input/protocol/toolchain/registry` 与迁移边界断言。应用模块闭包见 I3。 |
| worker/进程/归约 | `worker_protocol.py`、`controller.py`、`primitives.py`、`decide.py`、`stages.py` | nonce/attempt/writer、重复/越权/多余 result、接收副本重新实测、退出和事故保留、RSS/超时/日志上限、blocked_by 与 NotTested、required/N/A 和 gate；读 `test_asset_v2_protocol/decide/pipeline/legacy_boundaries` 及 Phase 0 共用原语回归。 |
| 证据/CLI | `evidence.py`、`scripts/asset_accept.py` | C/S/D/E/V/Q/T 无环、R5 重测、输入/工具/交付漂移、payload 精确集合、错误签收、existing destination 和部分 copy 清理；读 pipeline/CLI 的实际签收与交付断言。可选拒收见 I2。 |
| Native | `native_policy/plan/run/results/checks.py`；Blender `native_collect/render/worker.py` 与 `__init__.py` | 有限静态支持、安全阻断、manifest/reference、135 原图/99 比较、精确重开、进程/PID/平台身份、像素而非 PNG 字节、黑图及观察项；读 native policy/plan/checks/worker/results 测试和真实 Native fixture/support/测试的关键正负例。 |
| GLB | `interchange_policy/plan/run/results.py`、`projection.py`、`projection_worker.py`、`glb_budget.py`、`glb_budget_worker.py`；`glb_worker.py`、`projection_capture.py`、`validator_worker.mjs` | 固定 preset、Node 包锁、接收 D、逐实例预算、图环/多父、URI/扩展限制、表面有向匹配与全局工作预算、声明损失、projection visual 集合、未实现 consumer 失败关闭；读 interchange contract/policy/results、GLB worker/budget/projection 与真实 M3/Validator/surface 支持及断言。 |
| 升级状态/归属/清理 | `upgrade_state/locks/cleanup/discovery/registration.py` | home/CODEX_HOME/profile 绑定、revision 恢复、历史 receipt ancestry、保护引用、原始删除镜像、精确 proof/source guards、busy 延后、删除后回滚失效；读 upgrade core/state/locks 的断点、外部漂移、跨 root、snapshot 重验及 lease 真子进程测试。 |
| 安装/入口/注册 | `upgrade_handoff/integration.py`、`cli.py`、`runtime.py`、`project_marketplace.py`、`entry_lease.py`、`generate_entry_preludes.py`、`install.py` | marketplace→state 锁序、树外 bootstrap 后 exec、inode lease、prepared 拒启动、runtime recheck/recovery 重获屏障、no-op/只注册边界、目标 TOML 语义、敏感 stage 清理；读 workflow/launcher/registration staging 以及 CLI/runtime/verification 相关增量。新增未记录 stage 窗口见 I1。 |
| 门禁/分发/依赖 | `check_official_upstream.py`、`checks.sh`、`checks-fast.sh`、插件 manifest/lease marker、`uv.lock` | 最新性与固定完整性分列，严格 RELEASE 保留失败；逐五文件 cmp，不把比较故障写成腐坏；生成 prelude 一致性；定向 httpx2/httpcore2 升级不改官方固定 runtime 产物。读 bundle 门禁矩阵及共用 runtime 测试增量。 |
| 文档/职责 | README、docs index/architecture/validation/archive index、V5、两个设计、四份实施计划当前状态、closeout 计划、安装 skill/workflow | 当前事实与历史代码块分离；有限 M2/M3、普通 profile、RELEASE 和外部 NOT_RUN 分列；注册/完整安装/finalize/handoff/恢复的命令与代码相符。Task 5 新 M3 状态增量尚待补交。 |

值得保留的实现：controller 使用接收副本作为 findings 来源；required checks 与技术 gates 不依赖 worker 自报；Native/M3 真正核验完整输出集合和精确交付字节；installer 的条件删除继续携带归属/内容/快照 guards，lease 不随路径 rename 失效，外部配置不直接被 native plugin add 修改。上述优点不消除三个未闭合问题。

边界核对：`acceptance/` 仍是 checkout-only，`pyproject.toml` 的 wheel/sdist 白名单没有扩张；完整门禁包含 sdist 白名单与 `bridge/core`/`protocol` 禁 `bpy` 检查。此次分支未修改 bridge/protocol 产品代码。本审查不重复构建发行物。

## 验证证据与尚未完成的最终绑定

- 本审查实际运行了三个具体疑点的外部最小探针，结果如上。没有重跑完整 pytest、M2/M3、发行或现场安装门禁。
- 已读 Task 1–4 审查/相关报告和 `progress.md` Ruling。Task 3 原 publication 后遗留敏感 stage 的修复已读，I1 是不同的更早窗口，不是重复旧 finding。Rulings 对隔离测试授权、保留普通用户状态、固定分发与 RELEASE 分列的处理没有新增异议。
- controller 已通报新真实 M3 三文件 `8 passed / 0 failed / 0 skipped`，263.29s，exit 0，位于 `/private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task5-m3.rCWtQP`。本审查已读取其正例合同用于 I3，但尚未收到 Task 5 最终完整身份/门禁包，不能据此批准最终候选。
- 历史当前 M2 是 `19 passed / 0 failed / 0 skipped`；Task 5 需要对是否复用以及修复后的受影响门禁给出明确代码身份依据。I2/I3 修复将影响 acceptance 生产身份，旧结果不能无说明地变成新候选的通过记录。
- 只读审查未运行可能更新本地缓存的 graft 命令。最终实现者仍须在最后修改后完成 `graft build .` 与退出 0 的 `graft check .`，并提交相应证据；本报告不替代该门禁。

## Declined to judge

1. 最终候选和 I1/I2/I3 修复后的正确性：尚未提供修复及最终增量，必须独立复审。
2. 最新候选完整 checks、graft、发行/现场证据的一致性：Task 5 最终包尚未收齐，本版仅为 preliminary。
3. 普通用户 profile 的安装/live 合格性：现有声明仍为 inspect exact=false、verify 未通过；本审查未维修或操作该 profile。
4. 正式 RELEASE 资格：既有严格门禁因 upstream outdated 失败；固定完整性通过不能替代最新性，不在审查中改变上游 pin。
5. 一次性 LLM/canary、第二台 Mac、普通 Codex legacy 全应用交接：NOT_RUN/缺少外部输入，不用单元测试或隔离 fixture 代替。
6. 通用资产/范围外动画、实例、曲线、消费者适配和 L1/L2 隔离：本分支只承诺有限静态 L0；审查核验了相应失败关闭，不批准未实现能力。
7. 真实业务审阅与美术质量批准：测试 reviewer/生成夹具只能证明流程；没有业务授权的作品不因测试 SHIP 获得批准。
8. 同 UID 恶意参与者整体重写 C/S/D/E/V/Q/T、非协作进程绕过 lease 或逃离 L0 进程组：不属于本分支声明的本机可信/协作入口保证，不据此制造范围外安全结论。

下一轮放行条件：三个具体问题修复并有独立回归/复审；审阅冻结 Head 之后每个生产及文档增量；收齐与最终候选绑定的适用门禁、graft 和诚实限制记录。满足前均保持 **Ready to merge: No**。
