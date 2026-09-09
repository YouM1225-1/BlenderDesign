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

修改上游补丁、runtime 依赖、固定产物或正式发布 runtime 时，额外使用发行门禁：

```bash
RELEASE=1 \
OFFICIAL_MCP_SOURCE=/absolute/path/to/blender_mcp \
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
bash scripts/checks.sh
```

该模式会确认固定提交仍是上游 HTTPS `main`，从提交对象重放完整补丁序列，分别用
MCP SDK `1.28.1` 和 `2.0.0` 执行上游质量门禁及非 Blender 测试，运行 Bandit、
detect-secrets 与 pip-audit，进行两次确定性构建，并逐字节比对仓库发行物。缺少任一
输入、验证器或扫描器都会失败。

仅更新指令、技能或文档的分发包同步，若固定 runtime 产物逐字节未变，运行完整入口、
技能验证、提交内容与 ZIP 解包比对及校验和检查即可；这不产生新的 runtime 或现场验收结论。

最后一次仓库文件修改后执行 `graft build .`，交付前 `graft check .` 必须退出 0。
`graft/` 保留为未跟踪的本地缓存，不进入提交或分发包；不默认使用 `--deep`。

## 文档与执行约定审计

`AGENTS.md` 是执行约定的唯一入口，`CLAUDE.md` 引用同一文件。修改指令时核对根级约定与
实际适用技能的任务范围、授权条件和验证要求，避免重复批准、无条件扩大检查或将计划当作实现。
已知文件编辑可直接开始；仅检查安装状态不触发注册或安装，仅注册不安装 runtime。

文档移动或合并需核对入站链接、相对路径、测试引用和未完成任务的依赖。归档正文保留历史语义，
不将旧基线改写为当前结论；删除重复说明前将独有规则移入其职责对应的正式入口。

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
