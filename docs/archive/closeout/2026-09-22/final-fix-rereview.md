Ready to merge: Yes

# final-fix 独立复审：140fd69..f8e7692

结论：I1、I2、I3 均已关闭。没有确认的 Critical 或 Important 回归。发现 3 个 Minor，都是文档或证据指针问题，建议合入前顺手修正，但不阻塞。另有 3 个未确认疑点，需要实测才能下结论。本结论只覆盖本增量，不改变以下状态：严格 RELEASE、普通用户 profile、LLM/canary、第二台 Mac、legacy 交接仍未通过或未运行。

## 身份与范围

- 审查增量：`git diff 140fd69..f8e7692`。修复提交是 `6ad6638`（tree `2aceeac`）。之后 `bf266ad`、`8338125`、`f8e7692` 只改文档；`git diff 6ad6638 f8e7692` 只涉及 3 个文档文件，生产字节与 6ad6638 相同。
- 复审源码：用 `git archive f8e7692` 在仓库外 scratch 目录（`.../scratchpad/src-f8e`）生成副本。RED 对照使用 `git archive 140fd69`，再覆盖新测试文件。
- 未修改、暂存或提交仓库文件，未运行 checks.sh 和 graft，未启动 Blender/Codex 安装或注册，也未操作任何 profile。仓库内只写了本报告。

## I1：config stage 在 publication 记录之前的持久窗口（已关闭）

实现位于 `plugins/blender-mcp-installer/scripts/project_marketplace.py:649-772`。

- 新流程：native 验证、cache 发布完成后，先写 `config-stage.json` intent（`:722-728`）。intent 绑定 pre 配置镜像、native 文件 post 镜像（含 dev/ino/mtime/sha256）、cache 树镜像和 native_stage 名称。之后用 `forward_file` 以 RENAME_EXCL 把同一个 native inode 移到公开 stage 名（`:729-746`），再写 publication，最后清理 native 目录（`:748-750`）。
- 重试时只要有 intent 或 publication，就不再运行 native Codex（`:663-667`）。因此 native `last_updated` 等合法元数据变化不会触发冲突。
- 失败关闭的情形：
  - 没有 intent 却存在 stage：报 `lacks durable intent`，并保留 stage（`:670-671`）。
  - live 配置变化、cache 变化、native 目录身份变化：分别拒绝（`:730-735`）。
  - stage 路径被外部文件占用：`forward_file` 报 `transaction state conflict`。
  - stage 字节或 inode 变化：`:745` 拒绝。
- 敏感副本：崩溃窗口内原来同时存在 native 副本和 stage 副本，现在只剩一份（inode 被移动，不再复制）。intent JSON 只含镜像元数据和摘要，不含配置内容。成功后没有遗留副本。
- 新增 `post.mode != 0o600` 检查（`:697`）。它保证被移入 live 的 inode 是私有权限。

独立探针 `scratchpad/i1_probe.py`，基于现有 `registration` fixture，fake native 每次改写 `last_updated`：

| 场景 | 结果 |
|---|---|
| intent 写入后崩溃 | 崩溃时仅 1 份 native 副本；重试 native add 调用数 1→1；成功；旧 cache inode 保留；成功后 0 份副本；最终配置含 T1（原始 native 输出） |
| 移动后、publication 前崩溃（即原 I1 窗口） | 崩溃时仅 1 份公开 stage；重试不再调用 native，成功；旧 inode 保留；0 份副本 |
| 旧版遗留的无 intent stage | `registration config stage lacks durable intent`，stage 与 live 配置都保留 |
| intent 后 stage 名被外部文件占用 | `transaction state conflict`，外部文件和 native 副本都保留，live 配置不变 |
| 初始无 config.toml | 成功，生成的配置为 0600 |
| native 写成 0644 | 失败关闭（`native registration changed non-target configuration`），live 不变，私有 native 副本留作诊断 |

RED：在 140fd69 的生产代码上运行新测试，12 个 I1 用例失败，包括 `test_durable_config_stage_retry_uses_original_native_metadata[*]`、`test_config_stage_intent_retries_at_every_durable_boundary[*]` 和 `test_unknown_config_stage_is_preserved_without_durable_intent`。GREEN 见下方测试命令。

真实 Codex 证据已读取，脚本、result.json 和日志哈希与报告一致：`/private/var/tmp/blenderdesign-finalfix-evidence-20260923/codex-stage/`。候选为 6ad6638，中断点是 stage 已持久且 publication 缺失；重试前后 Codex 调用数都是 2，0 份副本，未知目录与旧 inode 保留。自有 profile 的 version-only 证据 `owned-profile-complete/version-only-summary.json` 也与报告一致：verify 26 tools，finalize 移除旧 cache，0 份副本。

## I2：可选审阅的显式拒收（已关闭）

`acceptance/evidence.py:290-294`：只要提供了 review，无论 required 还是 optional，都以 `_validate_review` 的返回值决定 SHIP 或 REJECTED；`required` 只决定缺席审阅时是否停在 NEEDS_REVIEW（`:201`）。V 在 `_seal` 之前就已写入，`_seal` 只写 Q/T，所以 V 字节不变。`deliver`（`:361`）拒绝非 SHIP 状态。

- 原审查者探针 `/private/tmp/blender-review-optional-reject-e5ajlxb4/reproduce.py`：
  - 在 98b9140 冻结副本上：`completion_state=SHIP`、`delivery_succeeded=true`，复现了原问题。
  - 在 f8e7692 副本上：`completion_state=REJECTED`、`delivery_succeeded=false`、`technical_success=true`。
- 新回归 `test_optional_review_recovery_honors_explicit_verdict[approved|rejected]` 断言 V 字节不变、rejected 时 deliver 失败且目标不存在，`test_optional_named_reviewer_absent_can_ship` 覆盖 optional 缺席仍可 SHIP。RED：rejected 用例在旧代码上失败。
- 真实 Native `test_optional_review_after_durable_summary_uses_actual_verdict` 在 final3 日志中 PASSED。

## I3：Blender glTF 内容闭包（已关闭）

- `acceptance/toolchain.py:45-71` `blender_gltf_files`：只接受 `Contents/MacOS/Blender` 布局。在 `Resources/5.2/scripts/addons_core/io_scene_gltf2` 下用 `os.walk(followlinks=False, onerror=...)` 枚举，逐节点 lstat，要求目录为普通目录、文件为普通文件；链接、FIFO 和枚举错误都失败关闭；必须有 `__init__.py`；`__pycache__` 不纳入锁。代码里没有硬编码文件数。
- `:74-87` `verify_blender_gltf`：要求合同中位于该根下的声明集合与实际集合精确相等，并逐一复算 bytes 和 sha256。
- 调用点：
  - 计划：`interchange_plan.py:42-45`，缺少 blender 工具或闭包不符都拒绝。
  - R0：`toolchain.py:167-176`，interchange 合同强制校验，不依赖文件名提示；`stages.py:20-25,32` 另做 defense-in-depth，并新增 files 相等比较。
  - R5：`evidence.py:100-102` 重新运行 `verify_tools`，漂移时抛异常。
- Native 合同不受影响：只有当合同行路径中含 `io_scene_gltf2` 时才顺带校验，这是只会更严格的 opt-in。
- 没有放宽任何边界：可执行文件 hash/version、声明成员 hash、acceptance 代码闭包、命令脚本必须在锁定闭包内等检查都保持不变。

真实应用只读探针 `scratchpad/i3_probe.py`，直接调用 `blender_gltf_files`/`verify_blender_gltf`，未启动 Blender：

- 闭包共 128 个成员（`.py` 与 `.dylib`，原 fixture 只锁了 126 个 `.py`，漏掉 Draco 等动态库），不含 `__pycache__`。
- full → ACCEPTED。
- 全部省略、省略一个、声明不存在的额外成员、声明 `__pycache__` 下的 pyc → 均为 `REJECTED toolchain_mismatch: ... closure mismatch`。
- hash 漂移 → `REJECTED ... member content mismatch`。

RED：14 个 `test_gltf_content_closure_at_public_boundaries[*]`、2 个 `test_interchange_requires_closure_even_without_any_gltf_hint[*]`、3 个 `test_gltf_closure_scan_fails_closed[*]`，以及 `test_r5_rejects_gltf_module_drift_after_r0[new]`，在旧代码上均失败。

已披露限制：`__pycache__` 中的 pyc 是本机生成的 timestamp 型（本机抽查 flags=0），不在锁内。同 UID 恶意改写 pyc 头部可绕过闭包，V5 与集成设计已明确“不宣称对抗同 UID 恶意篡改解释器缓存”，不作为本次发现。

## 回归检查（第 4 项）

- 证据伪造/缺失、判定绕过：I2 只收紧判定；I3 在 R0/R5 失败时进入 toolchain_mismatch 和 UNVERIFIED。M1 CLI 的 NotTested 数从 25 变为 31，原因是 interchange 在 R0 preflight 被拒，仍为 UNVERIFIED，没有 mock SHIP。
- 清理归属与锁：I1 没有改锁顺序；native 目录清理仍使用持久删除镜像，并且推迟到 publication 之后；未知 `native-codex.*` 目录不被删除（探针与测试都已证实）。
- 验证后内容漂移：R5 复核 glTF 闭包；I1 的 intent 绑定 inode、mtime 和 hash。

未发现新的 Critical 或 Important。

## 发现

### Minor M1：validation.md 引用的 Native 运行和 M3 数据与保留证据不符

位置：`docs/validation.md:160` 和 `docs/validation.md:179`。

- Native（`:160`）：写的是“最终修复候选……`21 passed in 1080.41s`”，并引用 `/private/tmp/blenderdesign-finalfix-native-final2.log`。该日志 mtime 为 13:59:04，按 1080s 推算约 13:41 开始；而 `acceptance/toolchain.py` 最后一次修改是 14:09:09（`stat -f "%Sm" -t '%F %T'`），所以 final2 运行的不是最终 toolchain 字节。最终字节对应的运行是 `native-final3.log`：`21 passed in 1106.08s`，SHA-256 e82b789a…，与 final-fix-report 一致，约 14:09:55 开始。
- M3（`:179`）：写的是 `8 passed in 306.80s`，但保留的 `/private/tmp/blenderdesign-finalfix-m3-final.log` 末行是 `8 passed in 312.62s`（SHA-256 1d5cc22f…，与报告一致）。306.80s 在任何保留日志中都找不到。
- 两处引用的 basetemp 目录（`/private/tmp/blenderdesign-finalfix-native-final2`、`/private/tmp/blenderdesign-finalfix-m3-final`）都已不存在。
- 实质结论（最终候选 21/0/0、8/0/0）有 final3 和 m3-final 日志支撑，因此不是把未通过写成通过。问题在于正式文档的运行身份指针错误。

### Minor M2：多处文档引用已删除的外部证据根

`/private/tmp/blenderdesign-closeout-20260922-27x0hxjj` 整个目录已不存在（`ls` 报 No such file）。以下正式文档仍把它当作现存证据引用：`docs/validation.md:213`、`docs/superpowers/plans/2026-09-08-asset-acceptance-native.md:18-22`、`docs/superpowers/plans/2026-09-08-installer-upgrade-cleanup.md:3087`，以及 final-fix-report 中 M3 命令的 `GLTF_PACKAGE_ROOT`。final-fix-report 只含糊提到“initial /private/tmp evidence root was removed”，没有指出历史证据和 validator 包根一并丢失。建议在文档中标注这些证据已不可复核。此外，`validation.md:207-220` 的安装升级现场段落没有补入 6ad6638 的 I1 真实 Codex 与 version-only 结果（只在 README 和报告中有）。

### Minor M3：收尾计划的状态与授权记录不准确

- `docs/superpowers/plans/2026-09-22-acceptance-upgrade-closeout.md:61` 仍写“报告同步后的最终 graft、完整 checks 和报告补充提交待完成”，但 checks-final.log（16:51:32，`ALL CHECKS PASSED`）、graft-check-final.log（OK）和提交 8338125 都已完成。
- `:18` 把原来计划级的“用户已经授权最终提交到 main 并 push……不 force push”整体替换为“本轮 final-fix 授权仅包括限定文件提交；不合并或推送 main”，而 `:63` 的 Task 6 仍是合并与推送。这是把一轮的限制写成了全计划约束，并删掉了“不 force push”。是否仍有 Task 6 授权应由 controller 与用户确认，本报告不作判断。

## 未确认疑点

1. 跨卷 CODEX_HOME。`:743` 是本分支第一个跨 root 的 rename（从 `HOME/.local/state/.../marketplace-recovery` 移到 `CODEX_HOME`）。`_rename_atomic` 使用 `renameatx_np`，EXDEV 会映射为 “cross-device rename is not supported”（`filesystem.py:534`）。修复前 stage 在 codex_home 内用 `_atomic_write` 复制，cache 也先复制到目标文件系统内的 sibling（`:708` 注释），所以理论上支持两者不同卷；修复后这种配置下注册会失败关闭，且不丢数据。本机没有可写的第二卷，挂载 DMG 属于系统改动，因此未实测。
2. 真实 Codex 在初始没有 config.toml 时的行为。在最终代码上，只用 fake Codex 验证了“预创建空 0600 文件”路径（成功）。真实 Codex 在 stage 探针和自有 profile 中都是在已有配置上运行的。如果真实 Codex 以非 0600 权限重建文件，会触发 `:697` 失败关闭。该路径未实测。
3. 门禁运行与候选的绑定是推断出来的。final3 与 m3-final 都早于 6ad6638 提交时间（14:54），在未提交的工作树上运行，日志中也没有记录 tree 身份。目前的依据是：当前工作树中 acceptance 与 tests/integration 和 6ad6638 相同（`git diff --quiet` 通过），且相关文件 mtime 都早于运行开始时间；其中 toolchain.py 只比 final3 开始早约 46 秒。这不是强证据。

## 实际运行的命令与结果

1. `git diff 140fd69..f8e7692` 全量阅读（生产代码、测试、文档）。`git diff --stat 6ad6638 f8e7692` → 只有 3 个文档文件。
2. `git archive f8e7692 | tar -x -C scratchpad/src-f8e`，然后 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/distribution/test_registration_staging.py tests/unit/test_asset_v2_pipeline.py tests/unit/test_interchange_contract.py tests/unit/test_asset_v2_cli.py -q -p no:cacheprovider` → **122 passed in 37.83s**。
3. RED：140fd69 副本覆盖 4 个新测试或支持文件后运行同样的 3 个测试文件 → **31 failed, 78 passed**，失败全部是 I1/I2/I3 的新用例。
4. 原审查者 I2 探针在 98b9140 上 → SHIP/delivered；在 f8e7692 上 → REJECTED/未交付。
5. `scratchpad/i1_probe.py`（6 个场景）→ 结果见 I1 表。
6. `scratchpad/i3_probe.py`（读取真实 /Applications/Blender.app，未启动）→ 结果见 I3。
7. 证据核对：对各日志、checks-final.log、codex-stage、version-only-summary 做 `tail`/`shasum`/`stat`；报告中 4 个 SHA-256 前缀全部吻合；checks-final 为 `1173 passed, 29 skipped`、`1046 passed`、`ALL CHECKS PASSED`；graft-check-final 为 OK。
8. `find`/`stat` 只读检查真实 io_scene_gltf2：共 254 个文件，其中 126 个 pyc，没有非普通节点，pyc flags=0。

## 工作树状态观察

复审开始时 `git status` 有 4 个继承的 `.claude/` 删除。复审结束时，这 4 个文件已在 2026-09-23 22:26 被恢复（`ls -la .claude` 的 mtime 为 22:26），`git status --untracked-files=no` 为空；HEAD 仍是 f8e7692。本复审的命令只做了读取、`git archive`/`git show` 到仓库外 scratch 目录，以及写本报告，没有恢复这些文件。可能是并行运行的门禁或其他进程所为，请 controller 核实。

## Doc delta 57d9b91

复审 `git diff f8e7692..57d9b91`（纯文档，父提交 f8e7692，共 3 个文件）。结论：**Ready to merge: Yes**，发现 1 个 Minor（M4）和 2 个 nit，没有把未通过项写成通过。

核对结果：

- M1 已修正。`validation.md:160` 改为 `21 passed in 1106.08s` 并引用 `native-final3.log`，与日志末行一致（SHA-256 e82b789a…）；同时明确 `native-final2`（1080.41s）开始于最终 toolchain 修改之前，不作为最终结果。`:179` 改为 `8 passed in 312.62s`，与 `m3-final.log` 末行一致（1d5cc22f…）。两处都注明 basetemp 已清理。
- M2 已修正。`validation.md:213` 注明外部证据根已清理，本文及计划中的路径仅供追溯；`:222` 补入 6ad6638 的 I1 与 version-only 现场结果。两份旧计划和 final-fix-report 中的旧路径没有逐处加注，但 `:213` 的总括说明已覆盖，可以接受。
- M3 已修正。计划 `:18` 恢复了 Task 6 授权并写回“不 force push”；`:61` 把“待完成”改为已完成。controller 说明 `.claude/` 恢复和 Task 6 授权均来自用户本次对话，本报告据此不再把这两点作为问题。
- 未通过项没有被写成通过：RELEASE（upstream outdated）、普通 profile、LLM、第二台 Mac、legacy 交接均保持未通过或 NOT_RUN（validation `:215-217`、`:222`，计划 `:61`）。README 中“最终修复已通过独立复审”与本报告一致。
- 复审转述（计划 `:63`）准确：Ready Yes、I1/I2/I3 关闭、无 Critical/Important、122 passed、RED 31 failed、I2 探针 SHIP→REJECTED、三个未确认疑点均如实转述，没有被写成已解决。

### Minor M4：validation.md:222 多写了最终候选上的“重复 FINALIZE”

`docs/validation.md:222` 称隔离自有 profile 在 6ad6638 上完成了“VERIFY、FINALIZE 及重复 FINALIZE”。但 6ad6638 的证据只显示每个候选各跑了一次 finalize：

- `version-only-summary.json` 的键中只有 `old_finalize` 和 `final_finalize`；
- `run_owned_version_update.py:62` 每个 label 只调用一次 `install.py finalize`；
- `driver.log` 中 finalize 只出现 2 次，对应旧版本与候选各 1 次；
- final-fix-report 也没有声称重复 finalize。

“重复 FINALIZE”属于更早的 Task 3（候选 a4bf15d）的证据，见 `:220`。建议删去“及重复 FINALIZE”。实质结论（26 工具 verify 和 finalize 完成）不受影响。

### Nit

- 计划 `:63` 的“同一批新用例 31 failed”：122 passed 来自 4 个测试文件，RED 只跑了其中 3 个（31 failed / 78 passed）。“同一批”略不精确，但数字本身正确。
- `validation.md:222` 和计划 `:61` 的“未知 stage 保留”：真实 Codex 探针保留的是未知 `native-codex.unknown` 目录，而不是未知的 config stage 文件。“无 intent 的 config stage 被保留并拒绝”只在 fake 或探针层面验证过，没有经过真实 Codex。建议写为“未知 native stage 目录保留”。

本节运行的命令：`git diff f8e7692..57d9b91`；`tail`/`shasum` 核对 `/private/tmp/blenderdesign-finalfix-{native-final2,native-final3,m3-final}.log`（前文已记录）；读取 `owned-profile-complete/version-only-summary.json` 的键、`run_owned_version_update.py` 的 finalize 调用，并统计 `driver.log` 中 finalize 出现次数（2 次）。没有修改仓库，也没有运行 checks 或 graft。
