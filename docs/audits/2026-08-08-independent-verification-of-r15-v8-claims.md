# r15/v8 收口断言·独立核验审计

> 日期：2026-08-08
> 审计对象：[handoff 融合对抗审计](2026-08-07-platform-optimization-handoff-adversarial-audit.md) · [closeout v3](2026-08-07-closeout-v3.md) · [v8 provenance](evidence/2026-08-08-phase0-closeout-v8-provenance.json) · [official MCP v2 evidence](evidence/2026-08-08-official-blender-mcp-v2.json) · Plan r15 历史对象（commit/path `e5ac5590f8ab2d2df915771f5266bc549a3b3a4e:docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`；SHA-256 `7160f61846e628f6c11fb29305064ad98ff49c16170804d283fc6c8fac750487`）
> 审计方法：**只做机器可核验断言的独立复算**，不采信文档自述
> 边界：独立核验运行时未执行 Plan、未修改被审计文件、未 commit

> **固定时点核验快照（2026-08-08，r15/v8）**：本报告的 Git/SHA 断言基于 `578f49e` 的未提交 capture，随后由 `e5ac5590f8ab2d2df915771f5266bc549a3b3a4e` 冻结。§8–§9 保留当轮后续复核与处置，但全文不追踪 r16/r17 等再修订；v8 provenance 保持不可变。当前状态统一见 [ROADMAP](../ROADMAP.md)。

## 1. 裁决

**这批文档的可核验断言几乎全部为真。** 我独立复算了 14 项 SHA-256、4 项结构计数、6 项门禁结果、manifest 逐字节重建、官方 MCP 的 checkout/AST/crash 证据，**全部匹配**。

初始核验发现 **1 项跨文档矛盾**（P2）、**1 项证据口径需澄清**（P2）、**2 项措辞风险**（P3），当时没有发现 P0/P1。后续对修复稿和新增 ROADMAP 的再次红队发现 4 组 P1，见 §9；因此“没有 P0/P1”只描述初始 capture，不是当前裁决。

一个必须说明的自我修正：我初次统计 Plan checkbox 得到 93，与文档声称的 92 不符；追查后确认**是我的统计方法有假阳性**（把文首 prose 里的行内代码 `` `- [ ]` `` 计入了），文档的 92 是对的，且 Plan 正文本身已预先说明了这一点。

## 2. 核验方法

| 类别 | 方法 |
|---|---|
| SHA-256 | 对每个被声称的路径独立 `sha256(file bytes)`，与文档记载逐位比对 |
| 结构计数 | 正则提取 Plan 的 ```python fence、path-bound fence、checkbox，独立计数 |
| manifest | 按 provenance 记载的算法**从 Plan 重新生成 TSV**，与仓库文件做逐字节比较 |
| 门禁 | 把 Plan 机械物化到隔离树（`scratchpad/v5`），用 Blender 5.2.0 内置 Python 3.13.13 建 venv，跑 ruff / mypy / pytest / adapter 专项 |
| 真 Blender | `--background` 与 GUI 两条 smoke 各跑一次 |
| 官方 MCP | 直接读 checkout 的 git HEAD / 工作树状态；AST 扫描统计 `@…tool` 装饰器；校验 crash report 文件与 SHA |

隔离树 `scratchpad/v5` 不属于仓库，与被审计方的 `/private/tmp/blenderdesign-v8-r15-audit.9595` 是两棵独立的树。

## 3. 核验结果

### 3.1 SHA-256：14/14 匹配

| 对象 | 声称 | 实测 | |
|---|---|---|---|
| Plan r15 | `7160f61846e628f6` | `7160f61846e628f6` | ✅ |
| URS v1.11 | `428d00921992c4e9` | `428d00921992c4e9` | ✅ |
| spec v1.11 | `2a07d4444ea6a4f2` | `2a07d4444ea6a4f2` | ✅ |
| SDK ADR | `611a6353d923652a` | `611a6353d923652a` | ✅ |
| handoff | `d03be7b1ab2d027b` | `d03be7b1ab2d027b` | ✅ |
| handoff 融合审计 | `a7ad55cf77b32a1a` | `a7ad55cf77b32a1a` | ✅ |
| closeout v3 | `a9cc741cda507b9e` | `a9cc741cda507b9e` | ✅ |
| measurement | `4cebc0d4469665cc` | `4cebc0d4469665cc` | ✅ |
| plan_python manifest | `6bf37fdb228e6eed` | `6bf37fdb228e6eed` | ✅ |
| artifact manifest | `6a1cea7d1e14ca80` | `6a1cea7d1e14ca80` | ✅ |
| vendor manifest | `fa45e6d679ab878a` | `fa45e6d679ab878a` | ✅ |
| GUI smoke v8 | `bfd5292ae2b5beae` | `bfd5292ae2b5beae` | ✅ |
| GUI 100k v8 | `309a1f7f8a9b0d54` | `309a1f7f8a9b0d54` | ✅ |
| official MCP v2 | `219cfe4d31ec8a83` | `219cfe4d31ec8a83` | ✅ |

### 3.2 manifest 可重建性：逐字节一致

按 provenance 记载的算法（「排序后的精确 LF ```python fence，首行为 `# <相对路径>.py`；每行 `path TAB sha256(file bytes) LF`；再对 TSV 字节取 hash」）**从 Plan 重新生成**：

```
我重算行数        46
我重算 TSV SHA    6bf37fdb228e6eed
仓库 manifest SHA 6bf37fdb228e6eed
逐字节一致        True
```

这一项分量最重：它证明 manifest 不是手抄的数字，而是**能从 Plan 独立复现的**。46/46 parity 声明成立。

### 3.3 结构计数：全部为真

| 项 | 声称 | 实测 | |
|---|---:|---:|---|
| ```python fence 总数 | 47 | 47 | ✅ |
| 带 path 的 fence | 46 | 46 | ✅ |
| 可执行 checkbox | 92 | 92 | ✅ |
| 已勾选 | 0 | 0 | ✅ |

> **我的统计错误与更正**：初次用 `count('- [ ]') + count('- [x]')` 得到 93。追查发现第 93 个来自 Plan 第 5 行的 prose——`Steps use checkbox (`- [ ]`) syntax for tracking.`，是行内代码里的语法示例，不是 checkbox。按行首锚定重数为 92，与文档一致。**文档是对的，我的方法有假阳性。** 且 Plan 第 49 行早已写明「原报告的 raw token=93 包含文首 checkbox 语法示例」——被审计方比我更早发现了这个坑。

另核实：G0 preflight 确实以表格行形式存在（Plan 第 42 行）而非 checkbox，「92 + 1 个无 checkbox 的 G0」表述准确。

### 3.4 门禁：独立复现，数字完全一致

在我自己的隔离树上复跑：

| 门禁 | 声称 | 实测 | |
|---|---|---|---|
| pytest 总数 | 307 | **307 passed** | ✅ |
| ├ unit | 275 | 275 passed | ✅ |
| └ contract | 32 | 32 passed | ✅ |
| adapter 专项 | 35 | 35 passed | ✅ |
| adapter 实质行 | 373（≤375） | **373**（非空非注释行） | ✅ |
| ruff | clean | All checks passed | ✅ |
| mypy strict | 22 文件 0 错误 | 22 files, no issues | ✅ |
| Blender background | `BG_CHECK_OK` 退出码 0 | `BG_CHECK_OK`，exit 0 | ✅ |
| Blender GUI smoke | `SMOKE_OK`，五项 true，`errors=[]` | 同左 | ✅ |

### 3.5 git 状态：一致

核验运行时 HEAD 为 `578f49e52f81…`、分支 `main`、无 staged、无新 commit，与当时 provenance 一致。随后已产生冻结提交 `e5ac559`；该变化不改变 Plan SHA、manifest 或门禁结果。v8 provenance 继续记录 capture，后续叙述文档以 commit/path 或新 attestation 区分 post-capture 状态，不改写历史 JSON。

### 3.6 官方 MCP 证据：可静态核实部分一致

| 断言 | 实测 |
|---|---|
| checkout HEAD `4309a39646e6…` | ✅ 一致 |
| 工作树 clean | ✅ `git status --porcelain` 为空 |
| AST 工具计数 26 | ✅ 我独立 AST 扫描得 26 |
| AST 名称 = effective `enabled_tools` | ✅ 26 个名称集合完全相同 |
| crash report 存在且 SHA `cc8c7f4a…` | ✅ 文件存在，SHA 匹配 |

**「注册 26/26 ≠ 26 项稳定」这个分层结论我认可**：注册目录、宿主 effective catalog、历史单轮直调、最新长序列 replay、deferred render 崩溃五层分开记账，没有把任何一层外推成全量稳定性。上表只核实 checkout/AST/crash 等静态部分；历史直调与长序列 raw transcript 的缺口见 §5、§9 R-07。

## 4. 发现

### D-01（P2）closeout v3 记录的 handoff 审计 SHA 已失效

closeout v3 §2 的文档 SHA 表里：

```
| 融合对抗审计 | c52158da58bc3bdedbe9930a6252da7d0ad34f7efc382b0b3dfea9c5e1a98e41 |
```

但该文件的**实际** SHA 是 `a7ad55cf77b32a1a…`，与 v8 provenance 记载的 `a7ad55cf…` 一致。

**判定**：provenance 正确，**closeout v3 的这一行是陈旧值**——多半是审计文档在 closeout 记录其 hash 之后又被修订过。

**影响**：closeout v3 §2 自称是「文档与内容 SHA-256」的锚点表，其中一行不可复算，会让复算者误判为文件被篡改。同表其余 6 项（Plan / URS / spec / ADR / handoff / official evidence）我都核对为正确。

**建议**：把该行更新为 `a7ad55cf…`，或在表头注明「本表为记录时刻快照，以 provenance 为准」。

### D-02（P2）GUI smoke 证据的字段口径需澄清

provenance 的 `blender_gui_smoke.criteria` 记录了 5 个判据。我复跑得到的 JSON 除这 5 项外，还有 3 个为 `null` 的字段：

```json
"large_scene": null, "large_scene_budget_ok": null, "large_scene_metrics": null
```

这说明 runner 的基础 smoke 与 100k 大场景 smoke 是**同一个脚本的两种模式**，基础模式下三个大场景字段为 null。而 closeout v3 §3 把「GUI smoke」与「100k 子门」列为两行门禁，读者可能误以为是两个独立脚本。

**影响**：不影响结论正确性，但复算者若只看基础 smoke 的 JSON，会困惑于这三个 null 字段的含义。

**建议**：在证据文件或 closeout 中注明「同一 runner 的两种模式；基础模式下大场景字段为 null」。

### D-03（P3）handoff 的历史快照与当前裁决混排

handoff 文档现在有 3 层前置说明（r12 前快照提示 / 融合审计当前指针 / v8 收口状态），其后 §1–§6 仍是原始快照文字，§0.1 是融合裁决表。这个结构是**诚实的**（保留追溯），但阅读负担重：§1 的「三项已合入 plan 并全门禁通过 / 262 passed」与当前 307 并存，需要读者自己分辨哪个是当前值。

**建议**：把 §1 的门禁块加一行「历史值，当前见 §0.1 / v8 provenance」，与 §2 各节已有的历史标注保持一致。（§2/§4 已经这么做了，§1 漏了。）

### D-04（P3）100k 子门的适用边界表述已到位，但建议前置

closeout v3 §3、handoff §0.1 M-4、provenance `gui_artifacts.large_scene_100k.scope` 三处都正确写明了「只覆盖 `BridgeClient → UDS → Bridge`，不覆盖 MCP stdio / SDK middleware / Discovery / schema / validation / audit postlude」。这个限定**非常重要且写得准确**。

但在 closeout v3 §1「最终裁决」里没有出现，只在 §3 末尾。审批者若只读 §1，会带着「100k 已通过」的印象。

**建议**：在 §1 裁决段落里加一句「100k 只关闭 Bridge-RPC 子门」。

## 5. 未核验项（诚实边界）

以下断言我**无法在本会话独立核验**，本报告不对其真伪表态：

| 项 | 原因 |
|---|---|
| 「最新安全 host 24 项 replay 第 15 项失败」 | 需要驱动 Codex app-server 长序列；核验时 shell 的 PATH 不含 `codex`（机器实际有 `/Applications/ChatGPT.app/Contents/Resources/codex`） |
| 「历史单轮 26 工具直调成功」 | 证据自述 `raw_transcript_present: false`，**被审计方已如实标注不可复核** |
| deferred render 的 `SIGABRT` 因果 | crash report 文件与 SHA 已核实存在，但我未复跑成对 deferred render（证据里明确写了 `repeat_policy: Do not rerun`，我遵守） |
| 「当前任务模型面 10/26」 | 这是被审计方所在会话的上下文快照，与我的会话不是同一个 |
| `uv lock --check` / `checks.sh` 全绿 | 我的隔离树未生成 `uv.lock`（未走 Task 0），跳过 |
| 100k GUI 测量数值 | 需构造 10 万对象场景，本次未复跑；其**方法学限定**我已核实写得准确 |

## 6. 对 Plan r15 本身的评价

除上述计数与门禁核验外，我对 Plan 内容做了针对性抽查：

**做得对的地方**

- **A-25 注册回滚的失败语义是诚实的**：`unregister_class` 自身失败时保留栈并抛 `class registration rollback incomplete`，而不是吞掉错误假装成功。审计报告 §3 末尾专门写明「不能声称自动可重试」——这是我在前几轮反复犯错的地方（把缓解写成解决），这里处理得比我好。
- **五层官方 MCP 证据分账**（§3.6）避免了「注册数 = 稳定性」的常见外推。
- **manifest 可从 Plan 独立重建**，而不是手工记录的数字。这让整个证据链可被第三方复算——本报告就是靠它成立的。
- **历史值全部标注为历史**，没有把旧的 262/93/v5-v7 manifest 当作当前证据。

**仍需注意的**

- Plan 的自审记录已累积到 18 条，前 10 条对当前读者的价值在下降。不必删（追溯有用），但建议把「当前生效约束」抽成独立一节置顶，避免执行者需要读完 18 条才知道现在的规则。
- `large_scene_*` 三个 null 字段（D-02）会让证据文件的自解释性打折。

## 7. 结论

**初始 capture 的证据质量高于本仓库此前任何一轮。** 14 项 SHA、4 项结构计数、6 项门禁、manifest 逐字节重建及官方 MCP 的 checkout/AST/crash 静态证据均独立复算一致。历史 26 直调和最新长序列只核实了摘要的自洽与边界标注，未独立重放。初始报告唯一的实质问题是 closeout v3 里一个陈旧的 SHA（D-01），且 provenance 里的对应值是正确的；后续复核新增的 P1 见 §9。

初始四项发现均为 P2/P3，本身**不构成审批阻断**。handoff D-2 提交动作已由 `e5ac559` 完成；handoff D-1 平台候选正式接受仍待用户裁决（与 URS ADR 编号无关）。ROADMAP 的执行顺序/preflight 缺陷已修；当前开放 P1 是 B-5（新 Plan 的 20 项映射、三工具端到端 NFR-P1、重审与用户批准）。重启后的 G5 模型面已关闭为 26/26；官方截图长序列失败和 deferred render 崩溃的可靠性风险仍开放，见 [ROADMAP 执行审计](2026-08-08-roadmap-execution-and-post-restart-audit.md)。

**本次独立核验运行未修改任何被审计文件，也未自行 commit；后续冻结提交 `e5ac559` 是报告完成后的状态变化。**

## 8. 后续复核与处置

本轮再次独立检查后确认 D-01–D-04 均成立，并已按最小范围修复：

- D-01：closeout v3 的融合审计 SHA 更新为实际值 `a7ad55cf77b32a1a…`；
- D-02：closeout v3 明确基础 GUI 与 100k 是同一 runner 的两种模式，基础模式三个 `large_scene_*` 字段为 `null`；
- D-03：handoff §1 的 262-test 门禁块增加就地历史标记；
- D-04：closeout v3 §1 前置“100k 只关闭 Bridge-RPC 子门”限定；
- Git 时态：closeout、handoff、融合审计区分 `578f49e` capture snapshot 与 `e5ac559` post-capture anchor；v8 provenance 保持原样，不追 live 工作区。
- 决策时态：handoff D-1 候选接受仍待用户裁决；handoff D-2 的提交动作已由 `e5ac559` 完成，二者不再混写。

修复仍不执行 Phase 0 Plan，不改变 Plan SHA 或 46/46 manifest。

## 9. 修复稿与 ROADMAP 的后续对抗复核

| ID | 严重度 | 复现/证据 | 处置 |
|---|---|---|---|
| R-01 | P1 | URS §10.1 实有 20 个 checkbox；Plan Task 19 仅列 12 行，后 12 个“性能与生命周期反例门禁”没有逐项映射。 | 不改冻结 Plan；ROADMAP 将“20 项逐条映射 + NFR-P1”列为 Task 19 前阻断，修订 Plan 后必须重审。 |
| R-02 | P1 | 现有 100k 只测 `BridgeClient → UDS → Bridge`，ROADMAP 却把端到端 P95 放在“Phase 0 完成后”；NFR-P1 的主语还是全部三个只读工具。 | 前移到 Phase 0 关闭前；三工具各 20-query P95 未通过时不得标记已实现。 |
| R-03 | P1 | ROADMAP 把 Task 14–17 排在 Task 13 前；Task 14 vendor/manifest 依赖 Task 13 addon 产物。当前 shell `command -v uv` 为空，但命令使用裸 `uv`。 | 顺序改为 0–12 → 13 → 14–17 → 18 → 验收 → 19；所有命令固定 `/Users/yeminjie/.local/bin/uv`。 |
| R-04 | P2 | 动态重算叙述文档 SHA 会自我失效；直接改 v8 provenance 会改写 capture。 | v8 JSON 不变；叙述文档以 `e5ac559` commit/path 定位，批准提交后另建 post-freeze attestation。 |
| R-05 | P2 | `e5ac559` 客观完成 handoff D-2 提交，但没有用户逐项批准 handoff D-1 的明确记录。 | handoff D-1 保持待决，D-2 单独关闭。 |
| R-06 | P2 | `jump_to_tab_by_name` 标注 `destructiveHint=True` 并切换 workspace，不是只读探针。 | G5 抽测改用三个 `readOnlyHint=True` 工具。 |
| R-07 | P2 | official v2 evidence 的历史 26 直调 `raw_transcript_present=false`，最新长序列也没有逐调用 raw artifact。 | ⚠️ 部分处置：已新增 [有界逐调用摘要 transcript](evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson) 与 [SHA sidecar](evidence/2026-08-08-official-blender-mcp-a4-transcript.ndjson.sha256)，可复核 24 个非 render `ok`、2 个 deferred render `not_called`、approval=0；它不含 raw payload、不可重放，见 [执行审计](2026-08-08-roadmap-execution-and-post-restart-audit.md)。 |
| R-08 | P1 | ROADMAP 一度要求 B-5 在 Task 0 前关闭，却把真正的 Plan 修订放在 Task 18 后的 C-6，形成不可达循环；还会错误沿用 r15 的 SHA/92 计数。 | B-5 改为 Task 0 前的独立修订/重审/批准门；C-6 只执行新 Plan 中的端到端门，新 SHA/计数必须重算。 |
| R-09 | P2 | ROADMAP 的 preflight 失败只 `echo`，Task 1–12 门禁按批次推迟，GUI 命令省略临时 root/output、pipefail 和外部 JSON 断言。 | preflight fail-fast；Task 0 保留 pytest collect exit 5 特例、Task 1 起逐 Task 全绿；GUI 必须引用新 Plan 的完整隔离命令。 |

Codex 配置口径另由官方文档复核：[`default_tools_approval_mode`](https://learn.chatgpt.com/docs/extend/mcp#other-configuration-options) 支持 `auto/prompt/writes/approve`；[App Server API](https://learn.chatgpt.com/docs/app-server#api-overview) 提供 `config/mcpServer/reload` 并为 loaded threads 排队刷新。因此“当前任务仍为 10/26”只是在初始核验时的现场事实，不能外推成产品绝对不能热刷新；用户完全重启后，当前模型面已直证为 26/26。

---

### 附：复算入口

本报告的核验脚本位于会话 scratchpad（`verify_claims.py`），依赖从 Plan 机械物化的隔离树 `v5/`，两者均未纳入仓库。复算路径：按 §2 的方法重建即可，所有输入都是仓库内文件与本机 Blender/官方 checkout。
