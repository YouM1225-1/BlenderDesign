# 验证说明

## 自动化门禁

开发过程中按改动选择最小有效检查；已有环境可用 `bash scripts/checks-fast.sh`
快速反馈。纯文档修改检查引用、命令及指令一致性；涉及技能入口时才验证技能结构，不新增匹配措辞的测试。
提交前运行下述完整入口一次；通过后，仅在后续改动、失败或未解决疑虑涉及其覆盖范围时重跑。

仓库唯一的完整验证入口是：

```bash
bash scripts/checks.sh
```

该入口依次验证：

- frozen 依赖同步；
- 安装器改动必须带有更大的插件版本号；
- Ruff；
- strict mypy；
- 插件结构（缺少官方插件验证器时失败）；
- core/protocol 不导入 `bpy`；
- protocol vendor 生成与一致性；
- 嵌套导入 smoke；
- sdist 文件白名单；
- unit 与 contract 测试；
- 官方分发 installer 测试。

脚本按 `UV_BIN`、`PATH`、`$HOME/.local/bin/uv` 的顺序解析 uv。
插件验证器默认从 `$HOME/.codex/skills/.system/plugin-creator` 读取，也可通过
`PLUGIN_CREATOR_ROOT` 指定。插件结构校验为必需检查。

分发测试的模拟可执行程序使用 shell 跳转到当前 Python，支持解释器路径中的空格；
便携包审计应在含中文和空格的解包目录运行完整入口，避免只验证原仓库路径。

### 安装器版本自动更新

每个开发克隆启用一次仓库提交钩子：

```bash
git config --local core.hooksPath .githooks
```

提交与合并提交钩子按暂存区检查 `plugins/blender-mcp-installer/` 的所有文件。每次提交的一组改动
自动更新一次 `.codex-plugin/plugin.json`，保留 `1.0.0+codex.YYYYMMDDHHMMSS` 格式，
使用 UTC 时间并确保大于所有父提交的版本；普通提交已更新的版本不会重复增加，
合并提交生成新的版本。钩子只额外暂存版本文件，
需要自动更新时，若该文件还有未暂存的修改则停止，避免把其他编辑带入提交。
仓库其他目录的修改不触发更新。

提交前需要检查尚未提交的安装器修改时，先运行：

```bash
python3 scripts/update_installer_version.py
```

完整检查和快速检查均运行只读的 `--check` 校验，漏更新、回退或非法版本会失败。
工作树中没有安装器修改时，会检查最近一次安装器提交与其父提交，绕过钩子的漏更新
不会因之后提交无关文件而漏检。浅克隆缺少比较历史时失败，需要先补齐历史。
这些规则由本地钩子和检查入口执行；新克隆需启用钩子，不能以跳过检查代替验证。

修改上游补丁、runtime 依赖或固定产物时，可独立验证固定提交的可复现构建与五个发行文件的
逐字节一致性：

```bash
VERIFY_DISTRIBUTION_INTEGRITY=1 \
OFFICIAL_MCP_SOURCE="$OFFICIAL_MCP_SOURCE" \
BLENDER_BIN="$BLENDER_BIN" \
bash scripts/checks.sh
```

该模式会查询远端 `main` 并单独输出最新性记录，但最新性只作建议：固定提交与远端 `main` 不一致或远端不可用
不会导致固定版完整性失败。它仍会运行构建、依赖和审计门禁，冷机器可能需要访问包索引，
因此不是完全离线检查。网络错误报告为 `upstream_freshness` 不可验证，不表示固定版内容损坏。

正式发布 runtime 时使用发行门禁：

```bash
RELEASE=1 \
OFFICIAL_MCP_SOURCE="$OFFICIAL_MCP_SOURCE" \
BLENDER_BIN="$BLENDER_BIN" \
bash scripts/checks.sh
```

该模式执行同一固定输入重建与五文件比较，并要求固定提交仍是上游 HTTPS `main`；固定提交与远端 `main` 不一致
或最新性不可验证都会使发行失败，但固定版完整性结果仍会独立输出。随后从提交对象重放完整补丁序列，分别用
MCP SDK `1.28.1` 和 `2.0.0` 执行上游质量门禁及非 Blender 测试，运行 Bandit、
detect-secrets 与 pip-audit，进行两次确定性构建，并逐字节比对仓库发行物。缺少任一
输入、验证器或扫描器都会失败。

仅更新指令、技能或文档的分发包同步，若固定 runtime 产物逐字节未变，运行完整入口、
技能验证、提交内容与 ZIP 解包比对及校验和检查即可；这不产生新的 runtime 或现场验收结论。

最后一次仓库文件修改后执行 `graft build .`，交付前 `graft check .` 必须退出 0。
`graft/` 保留为未跟踪的本地缓存，不进入提交或分发包；不默认使用 `--deep`。

## 文档与执行约定审计

`AGENTS.md` 是执行约定的唯一入口，`CLAUDE.md` 仅引用同一文件。修改指令时核对根级约定与
实际适用技能的任务范围、授权条件和验证要求，避免重复批准、无条件扩大检查或将计划当作实现。
已知文件编辑可直接开始；仅检查安装状态不触发注册或安装，仅注册不安装 runtime。

文档移动或合并需核对入站链接、相对路径、测试引用和未完成任务的依赖。归档正文保留历史语义，
不将旧基线改写为当前结论；删除重复说明前将独有规则移入其职责对应的正式入口。
计划中的待创建路径不按当前断链处理；其中用于修改现有文件的标题、文本锚点和命令仍需核对。

安装技能的命令由其 `references/workflow.md` 维护，
`tests/distribution/test_plugin_contract.py` 验证 operation recipes 的行为合同。
涉及技能结构修改时使用 skill-creator 提供的 `quick_validate.py`；普通 Markdown 编辑不触发技能安装或现场验证。

## Blender 验证

正式 Phase 0 验收入口是：

```bash
uv run --python 3.13.13 --frozen python scripts/run_phase0_acceptance.py \
  --evidence-root /absolute/new/path/outside/the/repository \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --uv /absolute/reviewed/uv
```

`--evidence-root` 必须位于候选仓库外且尚不存在。该入口固定 100,000 对象，依次执行
vendor generate/check、background smoke、GUI/NFR 和 kill/restart recovery；任一进程非零、
产物缺失/非 0600 普通文件、严格 JSON/schema/`success` 无效、进程组或 registry 残留都会
失败。汇总文件记录三份 JSON 与五份日志的 SHA-256。必须显式使用 Python 3.13.13，其他
patch 版本以 `wrong_python_patch` 失败。

`--blender` 默认使用上面的标准 macOS 路径；显式选择时必须为可执行文件，解析后的绝对
路径会贯穿 background、GUI/NFR、recovery 及其 provenance。三个 Blender 阶段分别在
证据根下创建 0700 的 user config/scripts/extensions/datafiles/resources 与临时目录，并向
所有子 Blender 进程传入对应的 `BLENDER_USER_*`、`TMPDIR`、`TMP` 和 `TEMP`。

该入口只闭合本仓库 Phase 0 验收，不实现通用资产方案的 trust policy、signed contract、
双 child repeatability、semantic manifest、Reviewer、attestation 或 Publisher。

Background smoke：

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --python-exit-code 1 \
  --python smoke/bg_check.py
```

`smoke/runner.py` 与 `smoke/e2e.py` 是上面正式入口编排的底层驱动；直接运行它们只作
诊断，不能仅凭 Blender 退出码称为正式 GUI 验收。正式运行要求 Git 工作树完全干净，
并对当前受跟踪的 Python、shell、TOML、`pyproject.toml`、`uv.lock` 和生成的 vendored
protocol 建立有界哈希清单。历史计划或审计文档不参与运行时 provenance。

2026-09-26 在提交 `b36095d`（工具描述补全合同语义，冻结 catalog 更新为 7,246 字节、SHA-256 `4a651553138d2156c35c07c55a06cc2e774ad9de979fd1bde22588c4687f71bc`）的干净 worktree 上，以 CPython 3.13.13、Blender 5.2.0 LTS、uv 0.12.2 运行正式入口，输出 `PHASE0_ACCEPTANCE_OK`；GUI/NFR 与 kill/restart 恢复均 `success=true`，NFR 证据记录的 `ordered_catalog_sha256` 与新冻结值一致。证据位于 `/private/var/tmp/blenderdesign-phase0-evidence-20260926-b36095d`，`summary.json` 的 SHA-256 为 `15555e10deb2f242f7c9a2a8ec0a7483d7c2048d54036f85bc3ccdb9ed9ffa25`。

### 独立 M2 原生资产门禁

使用锁定 Python、Blender 与仓库外全新证据目录显式执行全部 Native 测试；默认常规门禁的 skip 不能替代它。每次更换 `--basetemp`，避免 pytest 清理旧证据。

```bash
NATIVE_E2E="$(mktemp -d /private/tmp/asset-native-m2-e2e.XXXXXX)"
RUN_ASSET_NATIVE=1 .venv/bin/python -m pytest \
  tests/integration/test_asset_native.py -vv --tb=long \
  --basetemp "$NATIVE_E2E/pytest" > "$NATIVE_E2E/pytest.log" 2>&1
```

2026-09-23 在基线 `117b133` 的历史运行完成 `19 passed in 1018.12s`。最终修复候选又以 CPython 3.13.13、Blender 5.2.0 LTS / `fbe6228777e7` 完成全文件 `21 passed in 1106.08s`，0 失败、0 跳过。最终运行覆盖完整的好/坏资产、支持能力正例、审阅准确 D、错误图像拒签以及 durable summary 后 optional review 的 approved/rejected 恢复；日志位于 `/private/tmp/blenderdesign-finalfix-native-final3.log`，其 basetemp 已清理。更早的 `native-final2`（`21 passed in 1080.41s`）开始于最终 `acceptance/toolchain.py` 修改之前，不作为最终候选结果。每个完整正例验证 24 个现有适用检查、三个固定原生 gates、135 原图、99 比较/差异图、exact-byte fresh reopen 与 E/V；未签收只报告 NEEDS_REVIEW。测试 reviewer 仅验证流程，不能代替真实业务签收。

本门禁只证明当前工具下声明的有限原生静态支持范围。未支持实例/曲线/动画与未知平台仍为 UNVERIFIED，不代表 Phase 0、RELEASE、安装或 live 验收。历史 6 项失败本次未复现，旧证据缺失使其根因不可追溯；[执行记录](archive/plans/2026-09-08-asset-acceptance-native.md#当前执行结果2026-09-23) 保存本次完整命令与外部证据位置。

### 独立 M3 资产门禁

先完成 M0/M1 以及 M2 worker 接线和运行前置条件；M2 完整 Native 实际门禁作为独立门禁持续跟踪，不能由 M3 结果替代。准备锁定 Python、Blender、Node 和 gltf-validator 2.0.0-dev.3.10 及其真实工具/包文件摘要。显式运行 `RUN_ASSET_INTERCHANGE=1 RUN_GLTF_VALIDATOR=1` 的三份 integration 测试，并记录 source/C/D、工具身份、退出状态、summary、E/Q/T 和实际交付 receipt。

```bash
RUN_ASSET_INTERCHANGE=1 RUN_GLTF_VALIDATOR=1 \
BLENDER_BIN="$BLENDER_BIN" NODE_BIN="$NODE_BIN" \
GLTF_PACKAGE_ROOT="$GLTF_PACKAGE_ROOT" \
ASSET_CALIBRATION_ROOT="$ASSET_CALIBRATION_ROOT" \
"$PYTHON_BIN" -m pytest \
  tests/integration/test_asset_interchange.py \
  tests/integration/test_interchange_surface.py \
  tests/integration/test_gltf_validator.py -q
```

2026-09-23 最终修复候选使用 CPython 3.13.13、Blender 5.2.0 LTS / `fbe6228777e7`、Node v20.20.2 和 `gltf-validator@2.0.0-dev.3.10` 执行上述三文件门禁：`8 passed in 312.62s`，0 失败、0 跳过。测试从最终代码新建 calibration；完整日志位于 `/private/tmp/blenderdesign-finalfix-m3-final.log`，其 basetemp 已清理。先前绑定 `98b9140` 的 M3 记录独立保留，不能冒充最终修复候选的运行结果。修复候选身份和详细门禁链见 [closeout 修复报告](archive/closeout/2026-09-22/final-fix-report.md)。

完整正例的 34 个适用 check 和五个技术 gate 全部通过，三个合同 N/A 保持 N/A，409 个 manifest 文件无 missing/unknown/unproduced；真实 12 个作业均记录正 PID 并退出 0。受控 fixture reviewer 产生 Q/T，交付 4,952 字节 D 至新目标并生成 receipt，交付前后 D 摘要一致。缺消费者与缺底面分别保持 UNVERIFIED/REJECTED；同一运行还覆盖实际投影差异、Validator 缺资源、报告截断、资源记录篡改和内容重验。测试签收不构成用户作品的业务批准。

这组门禁只证明声明的 GLB 静态 L0 支持范围。独立两进程 surface probe、Node validator probe、完整 CLI、人工 Q 和正式交付分别记录，不互相替代。没有对应证据不得把状态标为已完成。M2 与 M3 各自的实际门禁结论独立，不能互相替代。

## 官方分发验证

安装器测试覆盖：

- manifest 和 checksum 的封闭解析；
- detached commit 与干净作用域；
- Python、uv、Codex 和 Blender host 探测；
- Codex 配置与 Blender Extension 的事务化安装；
- receipt、故障恢复、no-op 和 rollback；
- managed launcher 与四层 live verification。

已安装 runtime 只通过安装器 skill 的 `verify` 命令验证；该命令使用固定 Python，
并同时检查 Codex 策略、MCP 握手/工具目录和 Blender localhost 只读调用。
交互式 Blender 由操作者正常启动；安装器的宿主探测可以使用受控后台进程，不能代替现场会话验证。

## 结论边界

- 自动化测试通过证明被测代码满足测试覆盖的合同，不等于任意 Blender 文件或任意 Python payload 都安全。
- 官方工具数量、版本和哈希以当前 manifest 为准，不在文档中维护第二份目录。
- 平台支持只覆盖 manifest 声明的 macOS Apple Silicon 与 Blender 版本范围。
- 历史验收结果按[归档索引](archive/README.md)或 Git 历史追溯，不作为当前工作树的运行时依赖。

### 2026-09-23 安装升级当前现场结果

真实空 profile 首装暴露锁内升级入口未创建托管数据目录的问题，已复用安全目录初始化并补公共/锁内入口回归。真实 Codex 0.155.0-alpha.9.2 的 `plugin add` 提前删除持锁旧缓存，已改为私有事务 profile 注册、完整非目标 TOML 语义核验及 cache→config 条件发布；旧缓存路径/inode 留给验证后清理器。崩溃恢复、配置竞争和凭据环境隔离均有行为回归。

在 macOS arm64、Python 3.13.13、uv 0.12.2、Blender 5.2.0 LTS / `fbe6228777e7` 上，修复后的隔离 A→B→C 已完成真实 Codex 注册、MCP 26 工具目录和 Blender 只读调用、验证后物理清理及重复 finalize。A/B/C 使用真实不同 wheel 内容，A→B 的扩展也不同；B→C 的扩展字节相同，但现有事务会重新暂存扩展并清理其 recovery，不声称 inode 不变。非目标插件、marketplace、配置备份、其他 profile 和历史 projection 保持不变。真实旧缓存入口持锁时返回 `cleanup_pending` 并保留目录，释放自有进程后重试物理删除；真实 managed runtime 持锁时在修改前返回 `runtime_in_use`。当前 C 的同内容安装为 `no_op=true`；独立 inspect/verify 不改变 receipts、upgrade journals、active 或 Codex 配置。

本次执行证据曾位于 `/private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task3`，当前真实升级在 `live-final/`，固定候选与产物哈希见 `fixture-identities-staging.json`。该外部证据根此后已被清理，本文及计划中指向它的路径仅供追溯，结论以本节记录与 [closeout 修复报告](archive/closeout/2026-09-22/final-fix-report.md) 中的身份和日志摘要为准。C 为受审不可变提交 `f23c8a783b10be6e17c89aed5f7527caa528a7ec`；该 C 对应首次交付 `5e70856` 的安装运行字节，后续修订必须另行绑定候选身份。测试只启动并正常退出未打开项目文件的自有 Blender，不覆盖源 `.blend` 或停止用户进程。

仓库 Phase 0 的 `httpx2` / `httpcore2` 旧锁定版本扫描失败，已定向更新至兼容的 2.12.0；官方 runtime 锁和固定产物未改。固定分发完整性、五文件可重建比对及三个依赖审计通过。严格 `RELEASE=1` 仍退出 1：`upstream_freshness=outdated`，固定上游 `4309a39646e644261624bfcd2bca669b343b7621` 落后于当次远端 `ff54e4d8f6b09502f2f466189cca0e52b4a91643`。因此当前不具备 RELEASE 发布资格；未修改上游 pin 或放宽最新性要求。

正常用户 profile 单独只读检查为 `exact=false`：Codex effective/namespace/policy、recorded Blender executable 和 runtime 未达精确目标，Blender 扩展/host/online access/port/autostart 检查为真；正常 Blender 未运行，verify 未通过。本任务没有维修正常 profile。需要独立维护交接后修复并重新 live 验证；隔离环境成功不代替此结论。无一次性 LLM 凭据和第二台 Mac，相关 LLM/跨机检查为 `NOT_RUN`；当前运行中的普通 Codex 也未执行 legacy 全应用退出交接。


独立审查发现 publication 持久化后中断会在成功重试后遗留敏感 native 配置快照，已增加写入配置前的 stage 根身份记录、publication 绑定和持久删除镜像；重试先安全清理前次记录的尝试，未知目录不删除，缺失/冲突证据失败关闭。三个中断边界及三个冲突回归通过；受审修订候选 `a4bf15db6b565b08de37b76439b96d89e7e7add3` 的真实 Codex 三次中断/重试均清除已记录快照。复用自有 C profile 的 C→D installer-only 升级返回 runtime no-op，随后真实 26 tools/Blender 只读 VERIFY、FINALIZE 及重复 FINALIZE 全部通过，旧 cache 只在 live 后移除，runtime/extension/preferences/receipts/active 字节不变。修订后常规门禁为 1150 passed / 27 explicit skips，distribution 为 1033 passed，`ALL CHECKS PASSED`。证据在同一外部根的 `fix1-*`；官方产物和上游 pin 未变，合并若改变 plugin 版本或代码身份，Task 5 重新绑定候选，不改变既有 RELEASE 不具备发布资格的结论。

最终全分支审查确认的注册 config-stage 早期窗口问题（I1）已修复：配置 stage 可见前先持久记录 intent，并将原 native 配置移动到 stage，不产生新的敏感副本；重试续作已记录的发布而不重跑 native。固定修复候选 `6ad6638e77f0cebd226172f793301112bdd7322f` 上，真实 Codex 在新窗口中断后重试复用同一 recovery ID、不再调用 Codex，旧缓存 inode 与未知 native stage 目录保留，已记录快照清零；隔离自有 profile 从旧插件版本完成 installer-version-only install、真实 Blender 5.2 / Codex 26 工具 VERIFY 与 FINALIZE，bundle、runtime、扩展与偏好不变。该修复已通过独立复审。严格 RELEASE 未重跑，正常 profile、LLM、第二台 Mac 与 legacy 交接限制不变。

[最终修复复审](archive/closeout/2026-09-22/final-fix-rereview.md)未确认的跨卷疑点已确认并修复：CODEX_HOME 与 HOME 位于不同卷时，`6ad6638` 将 native 配置 rename 到 CODEX_HOME stage 会收到 EXDEV 并失败关闭（无数据丢失，但重试同样失败）；此前版本直接在 CODEX_HOME 写 stage，不受影响。现在 EXDEV 回退到 intent 绑定的同卷 `.registration.transfer` 副本，再同卷移入 stage；写入失败只删除本次独占创建的残片，进程中断留下的不符残片保留并以含路径的错误拒绝；同卷路径和 publication 恢复不变，已卡在该 EXDEV 的旧 intent 可直接续作。回归以真实 `renameatx_np` 包装模拟跨卷 EXDEV，覆盖成功、五个中断边界、未绑定/已绑定字节与 inode 漂移及无 intent 的 transfer；未修复代码上这 10 个用例全部失败。独立复审对 `6ed4c3c` 结论为 Ready to merge: Yes，无 Critical/Important；三项 Minor（中途写失败遗留未绑定残片、工作流对未记录 transfer 的表述过宽、非 EXDEV/部分写/绑定后漂移缺回归）已在 `78c89aa` 修复并补充 4 个回归，其中部分写回归在 `6ed4c3c` 上失败。另在 APFS RAM 盘第二卷上以 fake Codex 验证：`6ad6638` 真实返回 `Errno 18 Cross-device link`，修复后注册成功，旧版卡住的 intent 续作不再调用 Codex，无残留快照或 stage。最终修复候选 `78c89aaa4f8f0826ddda1e3079078ee47bcc4469`（tree `2e90a6e01fc5c0398c844dad0226a6acceab5452`，`git archive` 不可变导出，`project_marketplace.py` 与工作树逐字节一致）以真实 codex-cli 0.156.0 在 HOME 位于数据卷、CODEX_HOME 位于 RAM 盘（设备号 16777234 / 16777240）时完成四个场景：跨卷注册、transfer 绑定后中断再重试（Codex 调用前后均为 2 次，未重跑）、跨卷无初始 `config.toml`，以及同卷无初始 `config.toml`（未走 transfer）。四者均启用目标插件、保留非目标 TOML 语义与旧缓存 inode，无 native 快照、stage 或 transfer 残留；无初始 config 的两个场景同时关闭了复审中“真实 Codex 从无 config.toml 起步仅由 fake Codex 覆盖”的疑点。证据位于 `/private/var/tmp/blenderdesign-exdev-evidence-20260923/78c89aa`，`result.json` 记录候选提交与 tree，SHA-256 `4979166b94cf8c3e86e36458bddc265deeffbc0b276c2b41383422aebbd030b5`；`run.log` SHA-256 `554ee040fdc38bf6430e0a9bc54b3f3cbbd82c616bf2105b65b61fc3966eb47c`；同一探针在初版候选 `6ed4c3c` 上的结果保留在上级目录。合入前两个修复提交随 main 的归档提交 `1ac39ea` 变基为 `378c6dd` 与 `3d5e6f8`，`plugins/` 与 `tests/` 分别与 `6ed4c3c`、`78c89aa` 逐字节一致，差异仅为 main 上的文档归档。变基后最终树完整门禁：常规 1173 passed / 29 explicit skips，distribution 1059 passed / 1 skipped（运行中的 Blender 占用 9876，端口探针按设计跳过），`ALL CHECKS PASSED`。正常 profile 未使用，严格 RELEASE 未重跑。

2026-09-24 正常用户 profile 已修复，并完成可证明部分的清理；当时工作流仍为 `cleanup_pending`，最终清理结果见下节“2026-09-24 现场结果”段。上文该 profile 的 `exact=false`、未维修及未执行 legacy 全应用退出交接的结论由本段取代。此前修复工作流 `1e522b8d-442b-4a01-a465-aa3fd2fa8e98`（receipt `02adb067`，受信提交 `1ac39ea`）的 install 先以 `legacy_handoff_required` 拒绝；执行者以不属于 Codex 客户端的会话作为外部维护终端执行 begin-handoff，操作者正常退出 ChatGPT，并手动结束两个退出后遗留的旧版 crashpad 进程。首次记录因 PID 复用而重新记录，最终 handoff 为 `ae861d3d-7bfa-4ce4-82b5-96f0a2fac764`，带该 ID 的 install 成功，此后 runtime 使用锁协议。该工作流的 inspect、live VERIFY 与注册验证均已通过，但 FINALIZE 只返回通用 `installer error`，journal 停在 `cleanup_pending`。原因是 28 条旧注册 `before.json` 中有 25 条指向已整体删除的受审 projection，读取其 manifest 失败使受保护引用计算中止；另有 1 条指向已删除的临时 trust 目录，不读取 manifest。`e31c3d7` 改为：整体缺失的 projection 只保护 source 路径；仍存在但无法证明的旧注册 source 引用以固定原因 `cleanup_reference_unproven` 失败关闭，不输出路径、不改写证据。新增 11 个行为回归，缺失 projection 用例在未修复代码上复现同一错误；完整门禁 1070 passed / 1 skipped，`ALL CHECKS PASSED`；三轮独立只读审查无阻塞项。

现场使用 Codex 0.155.0-alpha.16、Blender 5.2.0、Python 3.13.13、uv 0.12.2，受信提交 `e31c3d7`。inspect 为 `exact=true`。首次 install 以 exit 1 结束，其错误 JSON 被工作流变量截获而未留存。执行者事后核对：只物化了可复用的 `e31c3d7` projection，没有新 journal，receipt、active 与 Codex 配置未变；lsof 显示 ChatGPT app 的 codex 进程启动的 7 个托管 MCP 进程持有 runtime 使用锁，据此判断为锁占用，未留存错误码证据。操作者正常退出 ChatGPT 后重试 installer-version-only install，结果为 `no_op=true`，工作流 `caa64e2e-6f0f-4ea5-abfd-85133a6bca79`。操作者重新打开 Blender 后，VERIFY 的 26 工具目录与 Blender 只读调用通过；FINALIZE 以 exit 3 / `cleanup_pending` 结束，删除旧插件 cache `1.0.0+codex.20260922221552`，4 个旧 recovery 候选因 `lease_known=false` 记为 `deferred_in_use`（`legacy usage is not proven idle`）；PERSISTENT_MARKETPLACE_VERIFY 通过。`1e522b8d` 绑定 `1ac39ea`，以 `e31c3d7` 重试在修改前失败（通用 `installer error`，按代码为 `finalize installation identity mismatch`），journal 字节不变，保持 `cleanup_pending`；其候选已由 `caa64e2e` 继承。11 个 runtime 与 12 个扩展 recovery 共 23 个（约 1.3 GB，几乎全部为 runtime）仍保留：4 个（2 runtime、2 扩展）无租约旧候选不能证明空闲，其余 19 个为 `preimage lacks exact managed parent provenance` 发现项；清理保护当时未放宽，回收方案另行处理。证据位于 `/private/var/tmp/blenderdesign-normal-profile-evidence-20260924/e31c3d7`，`SHA256SUMS` 的 SHA-256 为 `b076c4dd747d4917d2f4fbf20545f923eca00905c524b6f130adcc9fd28b7e9b`。严格 RELEASE、LLM 与第二台 Mac 限制不变。

### 2026-09-24 正常 profile 历史 recovery 回收诊断与现场结果

正常 profile 的两条 `cleanup_pending` journal 只读诊断结论：现存全部 11 个 runtime recovery（各约 121 MB）与 12 个扩展 recovery 都无法回收，原因有四。四个候选来自无 `usage.json` 的旧 runtime，只能标为 `legacy usage is not proven idle`；其余多数被报告为 `preimage lacks exact managed parent provenance`，因为父 install post 到子 pre 之间出现了运行产生的 `__pycache__/*.pyc`、目录时间变化和整卷 `st_dev` 重编（同一 inode 在不同启动中分别为 16777229/31/34）。已记录镜像在设备号重编后也无法用于条件删除。旧 journal 的 release 已不是当前版本，无法自行 finalize。

也有确实不属于托管内容的漂移：一个 runtime recovery 含手工补丁和 `codex-backup-*` 目录；扩展 recovery 中四个的 `.py` 源码被改动，两个是内容相同但 inode 全新的整树副本，一个早于首装。这些条目按 [设计 §13](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md#13-2026-09-24-历史-recovery-回收补充) 当时继续保留并报告，后已按操作者要求移入废纸篓（见下文）。

在只读真实 receipt 上复算新规则：11 个有父代的 runtime recovery 中 10 个（约 1.2 GB）可证明来源，12 个扩展 recovery 中 5 个可证明；其中无使用证据的均早于当前启动退役，满足重启空闲证据；最新一代有 `usage.json`，走使用锁。行为回归覆盖字节码/设备号漂移接受、源码改动、孤立缓存、缓存目录外来文件、新增文件、整树复制、部分设备号变化、重启前后与启动时间不可读、有租约时重启证据不替代锁、插件缓存不适用重启证据、双设备号租约及新设备号租约文件缺失，以及被取代 journal 的收尾与不收尾。正常 profile 已以受信提交 `194b917`（`plugins/` 与 `tests/` 同 `de2f956`）完成 installer-version-only install（runtime `no_op=true`）及 26 工具/Blender 只读 VERIFY，工作流 `d2100f19` 发现了上述 16 个候选（10 runtime、5 扩展、1 旧插件缓存）。但 FINALIZE 写入的清理意图 journal 为 20,093,392 字节，超过当时 16 MiB 的状态 JSON 读取上限；写入端没有对应上限，之后在读取引用时以 `state JSON is too large` 失败。该失败发生在第一个候选之前，没有删除任何目录，Blender MCP 仍可用，但之后的 install/register/finalize 都会读取该 journal 并失败关闭。修复把状态 JSON 读写、身份证据读取和 runtime 闸门的上限统一为 32 MiB，写入前检查超限，并补充了 16 MiB 以上往返、超限不写入、超大清理意图在删除边界前失败及闸门上限一致四项回归；新代码可只读加载该 journal 并完成引用计算，受保护的仅为手工补丁 runtime 和首装前扩展。清理需要安装该修订后重新执行（已以 `112f486` 执行，见下文）。

诊断中另发现一项风险：runtime 启动闸门比较 receipt 记录的 `st_dev`，入口租约名也包含 `st_dev`，整卷重编后现有安装会失败关闭（launcher 与缓存脚本因找不到租约文件以 FileNotFoundError 退出 1）。该问题已按[设计 §13 租约身份 v2](superpowers/specs/2026-09-08-installer-upgrade-cleanup-design.md#13-2026-09-24-历史-recovery-回收补充)修复：新 runtime 与插件树标记为 `inode-v2`，租约名只含 inode，launcher 只比较 receipt 记录的 inode 和路径，并拒绝挂载点形式的 runtime 根；缺少租约时 launcher 与缓存入口以 75 干净退出。v1 租约（`inode-v1`）runtime 在设备号变化后，按 receipt 记录的设备号与当前设备号取锁，可以被升级替换；无租约的 legacy runtime 仍需外部维护交接。行为回归在 194b917 上先复现 5 项失败（launcher 重编后与缺租约时 FileNotFoundError 退出 1、缓存入口 FileNotFoundError、v1 runtime 重编后报 `RuntimeInUse`、重编后才记录的 v1 候选在下次重编后仍延后），修复后全部通过。用例用包装解释器统一平移 `st_dev` 来模拟重编，另覆盖挂载点替换与 receipt inode 不符时返回 75、跨卷 inode 碰撞只报忙、v2 缺租约在重编前后都失败关闭且设备号租约不能替代、当前启动的 v1 launcher 仍会阻止 quiescence，e1f650f 的双设备号清理用例继续通过。正常 profile 已安装本修订，现场结果见下段。

2026-09-24 现场结果：受信提交 `112f486`（含状态 JSON 上限修复 `600b862` 与租约 v2 `16ae80a`，插件 `1.0.0+codex.20260924000624`）。操作者正常退出 Blender 与 ChatGPT，执行者核对无残留进程后，inspect 正常读取 20 MB 的 `d2100f19`，结果为 `exact=false`（Codex effective/namespace/policy 与 runtime 未达新目标）。install 因 launcher 变化替换了 runtime，receipt 为 `8dd633b0-c8e0-41d1-a3d2-97511cfb5310`，工作流为 `06a01546-acd0-4310-95b4-d7956e937aa2`。新 runtime（inode 584040082）与新插件 cache（inode 584037949）标记为 `inode-v2`，各得一个 v2 租约（`6928011092ae…`、`695e63b56ac8…`）；被替换的旧树沿用 v1 设备号租约。操作者重新打开 Blender 后，VERIFY 通过（26 工具、Blender 只读调用）。FINALIZE 返回 `status=complete`，无 pending，共删除 19 项：11 个 runtime recovery（原有的 10 个可证明项，加上本次换下的 `8dd633b0`）、6 个扩展 recovery（原有 5 个加 `8dd633b0`），以及旧插件 cache `1.0.0+codex.20260923155625`、`1.0.0+codex.20260923162153`。runtime recovery 占用由约 1.3 GB 降至 122 MB。`1e522b8d`、`caa64e2e`、`d2100f19` 三个旧 journal 以 `verified absent` 收尾为 `complete`；新 journal 为 22,112,843 字节，低于 32 MiB。由于全部 journal 均已完成，下一次工作流不再继承这些候选。以下各项当时保留并列为未验证发现（后续已按操作者要求移入废纸篓，见下段）：runtime `f925fd61`（手工补丁）；扩展 `37946dbe`（早于首装）；扩展 `4a87a07b`、`f925fd61`、`14cdb260`、`9ef2f8e7`（源码改动）；扩展 `836936ca`、`9b5f1953`（新 inode 的整树副本）；以及 25 个 `registration.*` 临时目录（`missing or oversized identity file`）。PERSISTENT_MARKETPLACE_VERIFY 通过。证据位于 `/private/var/tmp/blenderdesign-normal-profile-evidence-20260924/112f486`，`SHA256SUMS` 的 SHA-256 为 `fe8fab847173115647f0bfe5fe71ef4cb11c77cfb75e26d564891e6c9332952f`。严格 RELEASE、LLM 与第二台 Mac 限制不变。

同日按操作者要求处理无法证明归属的剩余项：确认没有 journal 引用、`lsof` 未见任何进程打开后，把 25 个无法证明作用域的旧注册目录、手工补丁 runtime recovery（约 122 MB）和 7 个扩展 recovery 移入废纸篓的独立文件夹，逐项原路径记录在其中的 `MANIFEST.txt`，由操作者自行清空；作用域可证明的旧注册 `registration.du7tbfi0` 保留。移出后以当前代码只读重跑发现，候选与发现项均为 0。随后 journal 改为 schema v2（完整镜像移出 journal，按内容寻址存储，见设计 §13），新增外置与去重、镜像缺失或篡改失败关闭、v1 兼容和写入中断恢复四项回归；新代码只读加载现场 4 个 v1 journal 均与存储形式一致。

2026-09-24 22:08 主机重启后首次真实验证租约 v2：数据卷设备号由 16777234 变为 16777229，runtime 与插件 cache 的 inode 不变（584040082 / 584037949），active receipt 仍记录 16777234。两棵树的 v2 租约都存在，按新设备号计算的 v1 租约名不存在；托管 launcher 通过闸门并完成真实 MCP initialize 握手（返回 0），两个缓存入口 `--help` 返回 0。按旧方案，这三处都会因租约文件缺失而以 FileNotFoundError 退出。launcher 握手、缓存入口返回码、receipt 记录的设备号与插件 cache inode 由执行者现场核对，未留存于证据目录。受信提交 `64178cc` 的 inspect 仍为 `exact=false`，原因与设备号无关：ChatGPT 在重启时把自带 Codex 从 `0.155.0-alpha.16` 自动更新为 `0.155.0-alpha.16.4`，与 receipt 记录不符，因此 `recorded_blender_executable` 为 false（runtime 与 Codex 其余检查均为 true）；VERIFY 按设计以 `installation inspection is not exact` 拒绝，对外只显示通用 `installer error`。操作者正常退出 Blender 与 ChatGPT 后重新 install（receipt `ed4fa14e-803d-4c8e-bfa7-d0ef9d57beac`，工作流 `a40699ba-51e9-46ec-90ac-dfde7db9a83a`，journal schema v2），runtime 被重新暂存（新 inode 598437989）。操作者重新打开 Blender 后，VERIFY 通过（26 工具、Blender 只读调用），FINALIZE 返回 `complete` 且 `all_old_versions_removed=true`：换下的 runtime recovery（`ed4fa14e`）与旧插件 cache `1.0.0+codex.20260924000624` 在重启后取得 v2 租约独占锁，无标记的扩展 recovery 取得按当前设备号创建的租约独占锁，三者均被删除，无未验证发现；新插件 cache 为 `1.0.0+codex.20260924003541`（inode 598437874）。PERSISTENT_MARKETPLACE_VERIFY 通过。

`5d039de` 起 exact 判断不再比较 receipt 记录的 Codex 版本（仍保留为证据），Codex 自动更新本身不再触发重装：当前 Codex 由 effective 配置检查与宿主能力探测实际运行，policy/namespace 检查读取当前配置；Blender、uv 与 Python 版本仍参与判断。该项仅有行为回归（修改前失败、修改后通过），尚未现场验证；正常 profile 当前 receipt `ed4fa14e` 由 `64178cc` 安装，需安装含该修订的版本后才受其约束。后续审计修复让 launcher 与缓存入口在每次 75 拒绝时向 stderr 写一行不含路径的原因（stderr 不可写时仍为 75），launcher 另补租约目录项身份核对；launcher 字节因此改变，下次安装会重新暂存 runtime，需先退出 ChatGPT 与 Blender。

上述重启与重新 install 的证据位于 `/private/var/tmp/blenderdesign-normal-profile-evidence-20260924/64178cc-reboot`，`SHA256SUMS` 的 SHA-256 为 `5c2995f48744c8ae281ee6b6357903684b0581a271bfc2be19a241ef3f0eeb0f`。
