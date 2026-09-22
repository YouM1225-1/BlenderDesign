# 验证说明

## 自动化门禁

开发过程中按改动选择最小有效检查；已有环境可用 `bash scripts/checks-fast.sh`
快速反馈。纯文档修改检查引用、命令和技能结构，不新增匹配措辞的测试。
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
`PLUGIN_CREATOR_ROOT` 指定。该检查不再跳过。

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

### 独立 M2 原生资产门禁

使用锁定 Python、Blender 与仓库外全新证据目录显式执行全部 Native 测试；默认常规门禁的 skip 不能替代它。每次更换 `--basetemp`，避免 pytest 清理旧证据。

```bash
NATIVE_E2E="$(mktemp -d /private/tmp/asset-native-m2-e2e.XXXXXX)"
RUN_ASSET_NATIVE=1 .venv/bin/python -m pytest \
  tests/integration/test_asset_native.py -vv --tb=long \
  --basetemp "$NATIVE_E2E/pytest" > "$NATIVE_E2E/pytest.log" 2>&1
```

2026-09-23 在代码基线 `117b133`、CPython 3.13.13、Blender 5.2.0 LTS / `fbe6228777e7` 上完成 `19 passed in 1018.12s`，0 失败、0 跳过。每个完整正例验证 24 个现有适用检查、三个固定原生 gates、135 原图、99 比较/差异图、exact-byte fresh reopen 与 E/V；未签收只报告 NEEDS_REVIEW。签收交付用例另行验证 Q/T/D 和真实交付回执。测试 reviewer 仅验证流程，不能代替真实业务签收。

本门禁只证明当前工具下声明的有限原生静态支持范围。未支持实例/曲线/动画与未知平台仍为 UNVERIFIED，不代表 Phase 0、RELEASE、安装或 live 验收。历史 6 项失败本次未复现，旧证据缺失使其根因不可追溯；[执行记录](superpowers/plans/2026-09-08-asset-acceptance-native.md#当前执行结果2026-09-23) 保存本次完整命令与外部证据位置。

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
并同时检查 Codex 策略、MCP 握手/工具目录和 Blender localhost 只读调用。安装器不会
启动 Blender，必须由操作者正常启动后再运行现场验证。

## 结论边界

- 自动化测试通过证明当前提交满足仓库合同，不等于任意 Blender 文件或任意 Python payload 都安全。
- 官方工具数量、版本和哈希以当前 manifest 为准，不在文档中维护第二份目录。
- 平台支持只覆盖 manifest 声明的 macOS Apple Silicon 与 Blender 版本范围。
- 历史验收结果可从 Git 历史追溯，但不作为当前工作树的运行时依赖。

### 2026-09-23 安装升级当前现场结果

真实空 profile 首装暴露锁内升级入口未创建托管数据目录的问题，已复用安全目录初始化并补公共/锁内入口回归。真实 Codex 0.155.0-alpha.9.2 的 `plugin add` 提前删除持锁旧缓存，已改为私有事务 profile 注册、完整非目标 TOML 语义核验及 cache→config 条件发布；旧缓存路径/inode 留给验证后清理器。崩溃恢复、配置竞争和凭据环境隔离均有行为回归。

在 macOS arm64、Python 3.13.13、uv 0.12.2、Blender 5.2.0 LTS / `fbe6228777e7` 上，修复后的隔离 A→B→C 已完成真实 Codex 注册、MCP 26 工具目录和 Blender 只读调用、验证后物理清理及重复 finalize。A/B/C 使用真实不同 wheel 内容，A→B 的扩展也不同；B→C 的扩展字节相同，但现有事务会重新暂存扩展并清理其 recovery，不声称 inode 不变。非目标插件、marketplace、配置备份、其他 profile 和历史 projection 保持不变。真实旧缓存入口持锁时返回 `cleanup_pending` 并保留目录，释放自有进程后重试物理删除；真实 managed runtime 持锁时在修改前返回 `runtime_in_use`。当前 C 的同内容安装为 `no_op=true`；独立 inspect/verify 不改变 receipts、upgrade journals、active 或 Codex 配置。

本次执行证据位于 `/private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task3`，当前真实升级在 `live-final/`，固定候选与产物哈希见 `fixture-identities-staging.json`。C 为受审不可变提交 `f23c8a783b10be6e17c89aed5f7527caa528a7ec`；最终仓库提交只追加执行结果文档，安装器源码、plugin 和产物字节须与该 C 对应。测试只启动并正常退出未打开项目文件的自有 Blender，不覆盖源 `.blend` 或停止用户进程。

仓库 Phase 0 的 `httpx2` / `httpcore2` 旧锁定版本扫描失败，已定向更新至兼容的 2.12.0；官方 runtime 锁和固定产物未改。固定分发完整性、五文件可重建比对及三个依赖审计通过。严格 `RELEASE=1` 仍退出 1：`upstream_freshness=outdated`，固定上游 `4309a39646e644261624bfcd2bca669b343b7621` 落后于当次远端 `ff54e4d8f6b09502f2f466189cca0e52b4a91643`。因此当前不具备 RELEASE 发布资格；未修改上游 pin 或放宽最新性要求。

正常用户 profile 单独只读检查为 `exact=false`：Codex effective/namespace/policy、recorded Blender executable 和 runtime 未达精确目标，Blender 扩展/host/online access/port/autostart 检查为真；正常 Blender 未运行，verify 未通过。本任务没有维修正常 profile。需要独立维护交接后修复并重新 live 验证；隔离环境成功不代替此结论。无一次性 LLM 凭据和第二台 Mac，相关 LLM/跨机检查为 `NOT_RUN`；当前运行中的普通 Codex 也未执行 legacy 全应用退出交接。
