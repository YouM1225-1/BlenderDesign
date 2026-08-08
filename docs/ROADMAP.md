# BlenderDesign 待办与执行路线

> 生成日期：2026-08-08
> 当前 revision 基线：`main@e5ac559`（post-capture anchor）· Plan **r17 proposed**（研究融合后的机械复核已完成，完整 tuple 见 [B-6 审计](audits/2026-08-08-deep-research-report-3-integration-audit.md)）· URS/spec v1.16
> **Phase 0 未执行**：全部执行项保持未勾选。r16 tuple 虽已获项目所有者批准，但在 source commit/attestation 前被 r17 研究融合取代，不能继承到未知新哈希。只有 B-6 对抗审计完成、项目所有者批准 r17 完整 proposed tuple，并完成 `source_commit → attestation commit` 两提交链及机械验证后，才可执行 Task 0；执行期间 Plan 文件保持不可变，进度进入 executor task log，正式 5+20 门进入 Task 19 的 `docs/audits/phase0-validation-report.md`
> 本文是**live 状态与 Gate 入口**。 [closeout v3](audits/2026-08-07-closeout-v3.md) 与 [v8 provenance](audits/evidence/2026-08-08-phase0-closeout-v8-provenance.json) 只固定 r15/v8 历史 capture，不是 live 裁决；重启后 A-2/A-4 的限定结果见 [ROADMAP 执行审计](audits/2026-08-08-roadmap-execution-and-post-restart-audit.md)。
> v8 provenance 是 `578f49e` 工作区的不可变 capture，`e5ac559` 是 post-capture commit anchor；本清单不追逐叙述文档的 live SHA，也不反写 v8。

## 0. 开工前必做（每次会话）

仓库处于**多方并发修改**状态。动任何文件前先跑：

```bash
cd /Users/yeminjie/Documents/BlenderDesign
git log -3 --oneline
git status --short
shasum -a 256 docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md | cut -c1-16
```

- r15 历史基线 SHA 为 `7160f61846e628f6`；r16 approved-but-superseded SHA 为 `0f7a96464ad408b5`。当前 r17 proposed 的完整 SHA/计数必须与 B-6 最终审计一致；用户批准并完成两提交链后才改用 post-freeze attestation。任何不一致都表示基线漂移，停下重审。
- 若要批量修改任一文档，补丁脚本里**必须内置基线 SHA 前置校验**（本仓库已因缺此步骤发生过两次覆盖事故）。

---

## A 组 · 阻断 Task 0 的决策门（A-1～A-3）

### A-1 · handoff D-1 裁决：三项平台候选是否正式接受

| 项 | 值 |
|---|---|
| **负责人** | 项目所有者 |
| **阻断** | Task 0 及其后全部执行 |
| **前置** | 无（可立即决定） |

**原待决内容（现已裁决）**：以下三项源自 Plan r15 平台候选；这里的 D-1/D-2 属于平台 handoff，不是 URS §6 的 ADR 编号。

| 改动 | 位置 | 实测依据 |
|---|---|---|
| `IDLE_INTERVAL` 0.1 → 0.02 | `bridge/core/queue.py` | 往返 p50 59.8 ms → 11.5 ms |
| `quantize` 去掉多余 `round(v, 6)` | `bridge/core/scene_hash.py` | 独立 1.6M 次中位数约 593.7 ms → 345.7 ms；方向与等价性已验证，旧 33.9/17.2 ms 不可重建 |
| 新增 `path_policy.same_file()` | `server/core/path_policy.py` | FR-21 红线：APFS 大小写不敏感下按路径字符串判定会让原稿被静默覆盖 |

**裁决结果（2026-08-08）：✅ 三项全部接受。** `IDLE_INTERVAL=0.02`、`quantize` 直接定长格式化与 `path_policy.same_file()` 均保留；不再保留代码回退动作。`IDLE_INTERVAL` 的电量/深度 idle 影响仍只列为非阻断 E-3，不把本机延迟收益外推为跨硬件合同；`same_file()` 仍不是 Phase 1 的 TOCTOU 防线。

**验收：✅ 已通过。** 项目所有者已明确接受全部三项，日期与边界已同步到 Plan/URS/spec。

---

### A-2 · G5：确认当前模型工具面 26/26

| 项 | 值 |
|---|---|
| **负责人** | 项目所有者 / 可访问 App Server 控制面的执行者 |
| **阻断** | G5；当前已关闭模型面子门 |
| **前置** | 无 |

**执行结果（2026-08-08，重启后）**：当前模型目录已从 10/26 刷新为 **26/26**。`get_screenshot_of_window_as_json`、`get_blendfile_summary_path_info_for_cli`、`get_blendfile_summary_datablocks_for_cli` 均在本模型上下文直调成功；CLI 两项使用临时 Storyboarding `.blend` 副本。独立 host transcript 同时复核 `mcpServerStatus/list=26/26`、24 个非 render 工具成功、`approval_events=0`。因此 A-2 已关闭；完全重启已替代 reload 路径。

**复现步骤**：

1. 调用当前 App Server 的 `config/mcpServer/reload`；若桌面客户端没有暴露该控制面，记录为不可用
2. 用 `mcpServerStatus/list` 确认宿主目录仍是 26/26
3. 在下一 turn 直接观察模型工具目录；若仍是 10，才新建任务或完全退出并重启 Codex
4. 抽调 3 个当前缺失且上游标注 `readOnlyHint=True` 的工具验证可用：
   - `get_screenshot_of_window_as_json`
   - `get_blendfile_summary_path_info_for_cli`
   - `get_blendfile_summary_datablocks_for_cli`

CLI 工具使用专用 `.blend` 副本，不使用生产工作文件。

**验收：✅ 已通过。** 模型工具目录 26 名；上述 3 个直调返回非错误；host 记录 `approval_events=0`。模型直调证据见 [ROADMAP 执行审计](audits/2026-08-08-roadmap-execution-and-post-restart-audit.md)；独立 host 证据见 [A-4 transcript](audits/evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson) 及其 [SHA sidecar](audits/evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson.sha256)。

**注意**：**不要**用 effective config 或另一个 app-server 的输出代替模型面证据——这正是当前证据链明确区分的两层。

---

### A-3 · 官方 MCP 可靠性部署策略裁决

| 项 | 值 |
|---|---|
| **负责人** | 项目所有者 |
| **阻断** | G5 完全关闭 |
| **前置** | A-2（先看清工具面再定策略） |

**已知风险**（[官方 MCP v2 证据](audits/evidence/2026-08-08-official-blender-mcp-v2.json)）：

| 风险 | 证据 |
|---|---|
| 长序列不稳定 | 24 项 replay 第 15 项 `get_screenshot_of_area_as_image` 返回截断/无效 JSON；单独重试成功 |
| render 崩溃 | 成对 deferred render 复现 Blender 5.2 `SIGABRT`，crash report SHA `cc8c7f4a…`；上游 3 个 issue 仍开放 |
| 任意代码执行 | `execute_blender_code` / `_for_cli` 默认在 effective catalog 中 |

用户已明确要求**完整 26 工具、无审批、不以安全风险为裁剪理由**。因此本项只处理可靠性/进程隔离，不能删掉 execute、screenshot 或 render。

**历史候选策略**（已选择“当前用户接受风险”；保留三项用于解释裁决边界）：

| 策略 | 做法 | 代价 | G5 关闭条件 |
|---|---|---|---|
| **隔离（推荐）** | 保留 26/无审批，在独立 macOS 用户或 VM 中运行官方 MCP | 配置复杂度 | 隔离环境实际部署后，复核 26/26、24 个非 render 调用、审批为 0；render 仍按既有崩溃证据延期，不得只记录意向便关门 |
| **当前用户接受风险** | 保留 26/无审批；不对重要工作文件运行已知崩溃序列 | 依赖人工纪律，Blender 仍可能崩溃 | 项目所有者明确接受 screenshot 顺序敏感性与 render 崩溃风险后关闭 |
| **等待上游** | 保留注册配置，但在上游修复前不依赖 screenshot/render 完成正式工作流 | G5 可靠性门继续开放 | 只记录裁决；G5 保持未关闭，C 组禁止执行，直至上游修复后复测 |

**裁决结果（2026-08-08）：✅ 选择“当前用户接受风险”。** 项目所有者明确接受严格中段 screenshot 序列的顺序敏感性与两个 deferred render 的 Blender 5.2 `SIGABRT` 风险，继续保留完整 26 工具、无逐工具审批。

**G5 可靠性门：✅ 以风险接受关闭。** `enabled_tools` 保持精确 26、`omit_tools_from=[]`、MCP approval mode 为 `approve`，宿主顶层 `approval_policy="never"`。这是部署决策，不是上游缺陷修复：A-4 仍只有 24 个非-render 调用的有界摘要，两个 render 未重跑，严格中段截图序列仍失败。

---

## 非阻断证据任务

### A-4 · 官方 26 工具有界逐调用摘要证据（已完成）

旧 v2 evidence 如实标注历史 26 项直调 `raw_transcript_present=false`，且旧 host replay 只有 14/24 + 失败摘要。新摘要 transcript 已补齐逐调用参数/响应的字节数与 SHA、耗时、结果标志及审批事件：24 个非 render 工具全部 `ok`；两个 deferred render 按既有 `SIGABRT` 证据记为 `not_called`。它可机械复核调用集合、计数、结果标志与 artifact 完整性，但**不含原始参数/响应、不可重放，也不能独立复核完整响应语义**；临时路径还使参数 SHA 不保证跨运行一致。这关闭摘要证据债务，不代表 raw payload 债务、render 稳定性或顺序敏感性已消除。

**验收：✅ 已通过。** NDJSON 共 28 行：1 run + 26 tool records + 1 summary；24 `ok`、2 `not_called`、0 approval event、0 transport failure。SHA-256：`d5ae61959c7f76f151915cc19fd12e04c21e1c57c7652f81d87141cd928edf2d`。未运行 deferred render。

---

## B 组 · 文档一致性（B-6 阻断 Task 0）

### B-0 · SHA 锚点表的漂移治理（已确定策略）

**根因**：冻结产物与持续修订的叙述文档混在同一 SHA 表中；追 live SHA 会循环失效，事后改 v8 JSON 又会改写历史 capture。

**固定策略**：

- `2026-08-08-phase0-closeout-v8-provenance.json` 保持不可变，继续描述 `captured_at` 时的 `578f49e` 工作区；
- `e5ac5590…` 作为 post-capture 的 commit/tree anchor，叙述文档用 `commit + path` 定位；
- closeout §2 只把 SHA 解释为 `e5ac559` 冻结对象，不宣称匹配 live 工作区；
- r17 获批后先提交精确范围形成 `source_commit`；只从该 commit 的 blobs 生成 `docs/audits/evidence/2026-08-08-r17-post-freeze-attestation.json`，其 top-level 与 `approved_tuple` 都使用 exact-key schema。tuple 精确固定 Plan/URS/spec/ROADMAP SHA、20 Tasks、open/checked checkbox、Python fence、path-bound/unique Python，以及最终 unit/contract/full/adapter tests 与 adapter 实质行计数；四份 live SHA 必须同时等于 tuple 值和 `source_commit` blob SHA。再用**第二个提交**纳入 attestation；`source_commit != attestation_commit`，实际执行 HEAD 必须是 attestation commit 的后代。missing/extra key、任一文档漂移或祖先链不符均停止；提交前不生成会再次漂移的“当前 clean/HEAD”证据。

**验收**：v8 JSON 字节不变；当前叙述文档不再声称其 SHA/clean 状态是 live 值。

---

### B-1 ~ B-4 · 我的审计发现处置

| ID | 内容 | 状态 |
|---|---|---|
| B-1 | closeout v3 §2 的 handoff 审计 SHA 陈旧 | ✅ 已按 `e5ac559` capture 对象修正为 `a7ad55cf…` |
| B-2 | GUI smoke 证据里 `large_scene* = null` 需注明"同一 runner 两种模式" | ✅ closeout §3 已注明 |
| B-3 | handoff §1 门禁块漏历史标注（§2/§4 都有） | ✅ 已补历史标记 |
| B-4 | 100k 的"只关闭 Bridge 子门"限定建议前置到 closeout §1 | ✅ 已前置 |
| B-5 | URS §10.1 20 项与 Plan Task 19 12 行映射不完整 | ✅ r16 修订/审计与完整 tuple 批准均完成；因 r17 在 source commit 前取代该 tuple，B-5 只保留历史裁决，不授权当前执行 |

### B-5 · r16 执行前修订（历史：tuple 已批准、未提交即 superseded）

**前置：✅ 已满足。** A-1 全部接受；A-3 选择当前用户接受风险，G5 已按对应条件关闭。

必须在进入 C 组前完成：

1. 把 URS §10.1 **20 个 checkbox** 逐项映射到 Task 19，不得继续写“八条”；
2. 在 Task 18 的末尾或 Task 19 的前置 Step 加入三只读工具各 20-query 的端到端 P95 `< 2 s` 正式门：`get_scene_summary` 使用 100k 真 GUI 压力场景，`get_blender_status` 使用已连接真 GUI，`describe_capabilities` 走完整 MCP stdio/adapter 且保持离线；保留顶层 Task 0–19 编号，不新增第 21 个 Task；
3. 把 Plan/spec/URS 中 G5 的陈旧 10/26/restart-only 状态更新为本轮模型面 26/26、transcript 模式（截图置后）host 24/24、严格中段截图序列仍失败、render 未重跑，且可靠性策略以 A-3 裁决为准；
4. 校正 URS §10.1 的 socket 权限措辞：socket 自创建即位于 `0700` 私有目录，bind 后、listen/session 发布前立即 chmod `0600`；不得声称在不改进程 umask 时 inode 出生即为 `0600`；
5. 为 URS §10.1 第 17/20 项补直接 fixture，覆盖非当前 uid/device 与“边界上方祖先权限不变”，不以间接测试冒充逐项验收；
6. 关闭 E2E 红队合同：group-level liveness、exact-type marker/time-window/dev-inode record、pre-spawn reservation/stdlib bootstrap 与 parent failure cleanup、read-only observer/owner race、8-record cache 与 deadline-bound 全 entry 扫描/overflow、unknown-before-valid、inflight publication/PID reuse/unlink 换入、public pre-observe/5 s registry reserve/cancel/final-KILL 与 poll 前后 deadline、bounded Git/vendor/audit provenance、required-tracked 与四文档 exact-type tuple/source blob、标准命令下 bytecode 污染、60 个 result preimage 跨工具总量外部复算、exact retryable `BRIDGE_UNAVAILABLE`、三次 MCP identity 全等及如实的 helper/fixture deadline 边界；每项都须有直接反例，不能只修 prose；
7. 对新 Plan/spec/URS/ROADMAP 重做对抗审计、manifest/parity，并计算 proposed SHA/checkbox/门禁计数；此时不生成 post-freeze attestation；
8. 由用户批准完整 proposed tuple；
9. 批准后提交精确范围形成 `source_commit`；从该 commit blobs 生成上述 attestation 并另行提交。机械验证 attestation 的 source commit/blob、完整 approved tuple、attestation commit→执行 HEAD 祖先关系后，B-5 才关闭。v8 provenance 永远保持 capture 不变。

**历史停点**：第 1～8 项已完成，项目所有者已批准 r16 完整 tuple；证据见 `docs/audits/2026-08-08-r16-b5-adversarial-audit.md` 与 `docs/audits/evidence/2026-08-08-r16-proposed-plan-python-manifest.tsv`。第 9 项尚未发生时，研究报告三触发 r17 规范/Plan 变更，故 r16 approval 自动失效且未生成 attestation；不得回头用旧 tuple 执行。

### B-6 · r17 研究融合与开工基线冻结（当前阻断）

1. 归档研究报告三为非规范输入，重新以 OpenAI、MCP、Blender 官方资料及代表性 GitHub 仓库核验主张；不可解析的 `turn…/filecite…` 不进入证据链；
2. 只把确定性 catalog、双内容 SDK/transport result payload byte baseline 与跨层单一职责纳入 URS/spec/Plan；真实 model-visible/token 成本留给目标 Codex Host A/B。Resources、projection/diff、progressive error、Recipe/visual budget 按证据触发延期，不扩张 Phase 0 产品工具面；
3. Task 17/18 直接验证 wire Server identity/version、ordered catalog/schema/instructions 与 `structuredContent`/兼容 TextContent JSON 等价、bytes/SHA、合计双内容 result payload/duplication ratio；Task 18 必须绑定 Task 17 freeze，不引入 tokenizer 或经验 Token 阈值；
4. 清理 ignored 缓存/Finder 元数据，补 `.gitignore`，建立正式文档与 evidence 索引；保留 v8 provenance 及所有历史 tracked evidence，不以“引用入度零”破坏复核链；
5. 对 r17 重新做 fresh-tree unit/contract/full、adapter、Task 18 helper、ruff/mypy/compileall/lock/vendor/nested、manifest/parity、链接/JSON/NDJSON/TSV 与独立对抗复核；
6. 发布新的完整 proposed tuple 并等待项目所有者逐值批准；获批后才允许 `source_commit → r17 attestation commit`，随后才可进入 C 组。

**当前停点**：第 1～5 项已完成；完整机械结果、manifest 与 proposed tuple 已发布到 [B-6 研究融合审计](audits/2026-08-08-deep-research-report-3-integration-audit.md)。项目所有者随后批准了当时可见的一组 r17 tuple，但机械绑定发现四份 live 文档已被后续加固改写，故该批准与此前 r16 批准一样不能跨未知哈希继承。第 6 项现在只剩项目所有者对审计 §9 **当前精确 r17 tuple** 的逐值批准；批准前不得 stage/commit、生成正式 attestation 或进入 C 组。

## C 组 · Phase 0 主线执行（A-1、G5 可靠性门与 B-6 全关后）

当前 r17 proposed 保留 20 个 Task；SHA/checkbox/test 计数必须以 B-6 最终审计为准。实际执行只能使用项目所有者明确批准、提交后 r17 attestation 固定的新 SHA/计数，并逐 Task 核对 Expected。

### C-1 · 环境前置（每次开工）

```bash
set -euo pipefail
test -x /Users/yeminjie/.local/bin/uv
test -x /Applications/Blender.app/Contents/MacOS/Blender
/Users/yeminjie/.local/bin/uv --version
/Applications/Blender.app/Contents/MacOS/Blender --version
```

`test -x` 失败必须令 preflight 非零退出，不得仅打印后继续。

### C-2 · 无需 Blender 的第一段（Task 0–12）

| 批次 | Task | 产物 | 里程碑验收 |
|---|---|---|---|
| **批 1** | 0 | `pyproject.toml`、包骨架、`uv.lock` | `/Users/yeminjie/.local/bin/uv run --frozen pytest --co` 退出码 5（空收集属预期） |
| **批 2** | 1–2 | `protocol/`（framing、envelope） | 该 Task 的 L1 全绿 |
| **批 3** | 3–7 | `bridge/core/`（contracts+scene_hash、queue、session、router、lifecycle） | L1 全绿；Task 7 是 Bridge 侧核心，含 I/O 线程与十步关闭 |
| **批 4** | 8–12 | `server/core/` + MCP adapter | L1 全绿；adapter 实质行 ≤ 375 |

**逐 Task 固定检查**（批次仅作导航，不得推迟）：Task 0 按表中 `pytest --co` 精确接受 exit 5，并单独跑 ruff/mypy；从 Task 1 起，每个 Task 提交前以下三项都必须 exit 0。

```bash
/Users/yeminjie/.local/bin/uv run --frozen ruff check .
/Users/yeminjie/.local/bin/uv run --frozen mypy
/Users/yeminjie/.local/bin/uv run --frozen pytest -q
```

### C-3 · Task 13：先生成 Blender addon

| Task | 内容 | 验收 |
|---|---|---|
| 13 | `bridge/blender/` bpy 适配层 + 根 shim | `/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python-exit-code 1 --python smoke/bg_check.py` → `BG_CHECK_OK`，退出码 0 |

### C-4 · Task 14–17：在完整树上做 vendor/L2/stdio

| Task | 内容 | 验收 |
|---|---|---|
| 14 | vendor 脚本、manifest、`scripts/checks.sh` | `bash scripts/checks.sh` → ALL CHECKS PASSED |
| 15–17 | L2 契约 / 对抗 / 子进程 / stdio | L2 全绿；Task 17 全链路与协议断言通过 |

### C-5 · Task 18：真 Blender GUI

| Task | 内容 | 验收 |
|---|---|---|
| 18 | L3 GUI/NFR/recovery | 严格执行 B-6 后获批 r17 Plan：基础五项与 100k/NFR 走隔离 root；NFR helper 使用 165 s work + 从 spawn 起 180 s runner outer deadline，recovery 使用 public 135 s OS supervisor + hidden 120 s worker。fresh marker-bound registry、leader-exit/live-child cleanup、三次 MCP identity 全等、catalog/payload byte baseline 及外部 artifact 断言都必须成功；不得使用省略监督器或护栏的简化命令 |

### C-6 · Phase 0 关闭前的端到端 NFR-P1 执行门

进入 C 组时，B-6 应已冻结并 attestation 固定本门。此处只执行，不再修改 Plan：现有 100k 证据绕过 MCP stdio/adapter/Discovery/schema/audit，不能复用为端到端结果。

按新 Plan 对三个只读工具各跑 20-query：`get_scene_summary` 使用 100k 真 GUI 压力场景，`get_blender_status` 使用已连接真 GUI，`describe_capabilities` 走完整 MCP stdio/adapter 且不得触网。每项从 `tools/call` 到 validated structured result 的 P95 都必须 `< 2 s`。外部验证器须从 60 个 bounded canonical preimage 重新执行模型/语义验证并复算 result/argument digest、nearest-rank 第 19 项、max/代表结果；provenance 须先证 clean Git，再验证 bounded tracked-source manifest、四文档 live/tuple/source-blob 三方全等、完整门禁计数与两提交祖先链。100k fixture/Bridge-only 预查询发生在 helper spawn 前，不得误写入 helper deadline。任一失败即停止，不得进入 Task 19。

### C-7 · Task 19：安装文档与正式验收

仅在 C-6 通过后，按新 Plan 写安装文档并核对 URS §10.1 20 项 + NFR-P1。全部通过后才可把 spec/URS 状态改为 Phase 0 已实现。

### C-8 · 全程纪律

- **不要 `git add -A`**：工作区含审计产物与 spikes，只暂存本 Task 的明确产物
- 每个 Task 完成后单独 commit，message 描述该 Task 的交付物
- 任一步 Expected 不符 → 停下查因，不要跳过

---

## D 组 · 后续工作

| ID | 事项 | 阶段 | 说明 |
|---|---|---|---|
| **D-a** | 端到端 NFR-P1 | **已前移 C-6** | 属于 Phase 0 关闭门，不得排在完成后 |
| **D-b** | Phase 1.5 协议一致性回归 + 旧协议退役评估 | Phase 1 后 | **SDK 已是 v2，无升级项**；只做 wire 层一致性 |
| **D-c** | FR-21 的 fd-based / `O_NOFOLLOW` 写入边界 | Phase 1 | `same_file()` 只是查询辅助，**不解决 TOCTOU** |
| **D-d** | FR-15 `F_FULLFSYNC` durability ADR | Phase 1 | macOS `fsync` 不刷驱动器缓存；实测 5.7 ms vs 0.05 ms |
| **D-e** | FR-24 APFS `clonefile` | Phase 1/2 | 512 MiB 337 ms → 1 ms；**只对文件→文件复制有效**，内存态快照不受益 |
| **D-f** | V-03 剩余项：真实 render 与 CPU fallback | Phase 2 | Metal 枚举/选择子项已关闭，**不是完全关闭** |
| **D-g** | Phase 1 前 observation contract 裁决 | Phase 1 preflight | 先用 r17 artifact 的 catalog/instructions/structured/TextContent bytes、调用次数、wall time 建基线；裁决 summary 是否改 compact default。若省略 collections/managed detail，必须同时加入 `included/omitted/complete/truncated` 元数据与 selector/fields/limit/cursor，不能以空数组混淆“真实为空” |
| **D-h** | projected query / semantic diff | Phase 1/2，证据触发 | 仅当真实 task logs 证明重复 full summary 是主要成本才实现；默认禁止 raw mesh/完整 node graph，结果必须有界。`changed_since` 需等待 revision/epoch 语义稳定，不重写已验证 UDS transport |
| **D-i** | Progressive error detail 与 validation projection | Phase 2，证据触发 | 模型默认只收稳定错误码/失败摘要；完整 traceback/报告外置并按需取回。先复用现有审计/Validation Report，不预建 Error Store 或 SQLite |
| **D-j** | Resources / Tasks 兼容试验 | Phase 1.5+ | 目标 Codex Host 必须实测 list/read、未 read 不自动注入、真实上下文行为；Resources/Tasks 永远有 projected Tool / 自铸 job fallback，不作为当前依赖 |
| **D-k** | Recipe / visual budget | Phase 3，任务日志触发 | 只有重复 workflow 经真实日志证明后才 Recipe 化；先确定性验证，歧义或 milestone 才渲染。不采用固定 macro 数或视觉次数 |
| **D-l** | Skill/AGENTS/instructions/schema 去重验收 | Phase 1 Skill 交付 | 按 NFR-C6 单一职责审计；同一规则只保留一个权威定义，其余用链接/引用，不复制 Blender 百科或工具手册 |

---

## E 组 · 待实测（不阻断任何事）

| ID | 事项 | 方法 |
|---|---|---|
| **E-1** | blake2b 加速成因 | 已排除"缺 OpenSSL 后端"（`hashlib.sha256()` 返回 `_hashlib.HASH`，OpenSSL 3.5.6）。建议 `openssl speed -evp sha256` 对比系统 OpenSSL、检查 Blender 内置 OpenSSL 编译配置、跨版本复测。**查明前不进任何合同** |
| **E-2** | 跨机器 / 跨 Blender 版本复测 | 现有数字全来自单机（M4 10 核 / macOS 26.5.2 / Blender 5.2.0）。对硬件敏感项：往返延迟、QoS 负面结论、hash 吞吐 |
| **E-3** | `IDLE_INTERVAL=0.02` 的电量影响 | 独立 GUI timer 复算仅证明回调 CPU 约 0.022% → 0.096%（约 4.4×），未证明续航或深度 idle 影响；用 `powermetrics` 采样对比。若有影响，迟滞设计必须避开死锁坑（见下） |

---

## 附录 · 已知陷阱（执行时务必避开）

| 陷阱 | 后果 | 规避 |
|---|---|---|
| 迟滞版 `_next_interval()` 在 `tick()` 已持锁时访问 `self.pending`（后者再取同一把非可重入锁） | **Blender timer 永久死锁** | 活动时间戳必须在已持锁的临界区内读写；绝不在持锁时调用会再次取锁的属性 |
| 改 `scene_hash.digest()` 但漏改 `scene_reader` 的分块增量实现 | 两处摘要不一致 | 这是同一算法的两个实现，**任何 hash 变更必须同时改** |
| 基于过时快照做批量字符串替换 | 补丁半数落空、文件被覆盖 | 补丁脚本内置基线 SHA 前置校验 |
| Blender addon 第二个 `register_class` 失败 | 泄漏已注册 class，`addon_utils` 不会替你调 `unregister()` | Plan 已实现逆序回滚；回滚自身失败时保留栈并报错，**不可声称自动可重试** |
| 把公开属性名缺失当作后端缺失 | 错误技术归因 | 看 `type(h).__module__` |
| `git add -A` | 误提交他方审计产物与 spikes | 只暂存本 Task 明确产物 |

---

## 状态跟踪

| 组 | 项 | 状态 | 负责人 |
|---|---|---|---|
| A | A-1 handoff D-1 裁决 | ✅ | 所有者已于 2026-08-08 接受三项平台候选 |
| A | A-2 G5 模型面 26/26 | ✅ | 重启后 26/26；3 个模型直调 + host transcript |
| A | A-3 官方 MCP 部署策略裁决 | ✅ | 所有者选择“当前用户接受风险” |
| A | G5 官方 MCP 可靠性门 | ✅ 风险接受 | screenshot 顺序敏感性与 render `SIGABRT` 仍成立；不是稳定性修复 |
| 证据 | A-4 有界逐调用摘要 transcript | ✅ 非阻断 | 24 ok；2 render not_called；approval=0；无 raw payload |
| B | B-0 SHA 锚点治理 | ✅ 策略已定 | v8 immutable；当前用 commit/path；新 r17 attestation 待 B-6 获批提交后生成 |
| B | B-1 ~ B-4 报告处置 | ✅ | 已修 |
| B | B-5 r16 20 项验收映射 | ✅ 历史完成 | tuple 已批准但未提交即被 r17 supersede，不授权当前执行 |
| B | B-6 r17 研究融合/基线 | ◐ 等待审批 | 机械复核与当前 tuple 已发布；上一组 r17 批准因 live 字节不匹配而未绑定，不得生成 attestation 或进入 C 组 |
| C | Phase 0 主线 | ☐ 未执行 | 仅待 B-6 新 tuple 获批并完成两提交链；本轮禁止执行 |
| D | D-b ~ D-l | ☐ | Phase 0/1 后或证据触发；D-a 已前移 C-6 |
| E | E-1 ~ E-3 | ☐ | 随时 |
