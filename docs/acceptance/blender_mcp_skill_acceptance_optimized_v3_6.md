# Blender MCP / Skill 建模产物验收方案 V3.6

## 可执行规范版:误拒修正、失败模型重构与注册表补全

> 修订日期:2026-08-24(Asia/Shanghai)
> 仓库基线:`BlenderDesign` commit `bf63c89294a5f79649a2c550331ea8987cdeab1b`;当日实测 `bash scripts/checks.sh` → `ALL CHECKS PASSED`(362 passed;821 passed + 1 skipped)
> 前序:V3.3 及其审计(5H/11M/5L)→ V3.4(21/21 处置)→ V3.4 双路复审 → V3.5 → **V3.5 全量审计(9H/8M/2L)经逐条独立验证:18 项成立、1 项部分成立** → 本文 V3.6
> 本版重点:修正三处会**误拒合法资产**的实测缺陷(GLB 换轴、相机拟合距离、bounds 只取 mesh),重构失败模型(区分资产拒收与基础设施失败、支持多 finding),补齐 file registry / manifest schema / 摘要规范化算法,并撤销"P0 零修改既有文件"这一被实测推翻的约束
> 文档性质:**自包含且可执行的规范**。实现者只依据本文即可编码 P0——全部 check ID、failure code、JSON 字段、相机与阈值参数、投影映射均在文内冻结,不需要另行拍板产品决策。本文同时仍是设计:通用建模产物验收在本仓库尚未实现,不得用于自动发布放行

---

## 0. 结论

### 0.1 方案定位

```text
R0 合同冻结 → R1 输入冻结 → R2 clean Blender 检查 → R3 条件导出/独立验证
           → R4 fresh-import/重开/视觉证据 → R5 fail-closed 汇总
```

```text
Producer(可写候选)
Verifier coordinator(只读输入、编排子进程、写 evidence)
Reviewer/调用方(读取冻结 evidence 后作最终决定)
```

多 OS principal、DSSE/Sigstore、透明日志、独立 Publisher、多目标引擎只在 L2 启用(§3)。

### 0.2 当前可声明范围(2026-08-24 实测)

| 能力 | 状态 | 结论 |
|---|---|---|
| 仓库常规门禁 | implemented-and-enforced | 当日实测 `ALL CHECKS PASSED`:362 unit/contract;821 distribution + 1 条件跳过 |
| `RELEASE=1` 发行门禁 | implemented-and-enforced(源码与既有测试结构核实;本轮未重放全链路) | 上游 `ls-remote` 精确一致、补丁重放、MCP SDK 1.28.1/2.0.0 双重放、Bandit/detect-secrets/pip-audit、双确定性构建逐字节 `cmp` |
| Phase 0 正式 wrapper | implemented-and-enforced | 只验证只读 Bridge 的真 Blender GUI/NFR/recovery;三个 known-bad 已有 unit 回归 |
| 官方 Blender MCP 固定分发 | implemented-and-enforced | 上游 `projects.blender.org/lab/blender_mcp` @ `4309a39646e6…`,10 个下游 patch,26 项工具目录 |
| 深层资产 manifest | absent | `scene_hash` 仅结构摘要(§4) |
| 导出格式独立验证 / fresh-import | absent | 无通用 glTF/USD/FBX 资产门禁 |
| evaluator-owned 视觉验收 | absent | 渲染工具 ≠ 独立视觉判定 |
| 多次 clean-run 产物比较 | absent | Phase 0 NFR/recovery 不是资产确定性验证 |
| 签名审批 / attestation / 发布系统 | absent | 仅 L2 增强项 |

### 0.3 正式验收当前被工作树状态阻塞

`_require_clean_worktree`([run_phase0_acceptance.py:87](scripts/run_phase0_acceptance.py#L87))把 untracked 文件也算脏。当前全部未跟踪文件——V3.2、V3.3、V3.3 审计报告、V3.4、本文 V3.5、`hantavirus_scientific_cutaway.blend`、`hantavirus_scientific_cutaway_v2.blend`、`hantavirus_scientific_cutaway_final.png`——任一存在都会使正式 Phase 0 验收以 `dirty_worktree` 失败。处置见 §11。

---

## 1. 风险分级(规范)

**合同权属与 policy 下限(冻结)**:`contract.json` **由 Verifier/调用方一侧产生并持有**,候选资产及其 Producer **不得携带、提供或覆盖**合同的任何字段。coordinator 只从命令行显式给定的合同路径加载,该路径**不得**位于候选输入目录之下(违反 → `contract_invalid`)。

合同中可放宽拒收边界的字段——`warning_allowlist`、`visual_thresholds`、`budget`、`projection.lost`、`platform_blocklist`——受一份独立的 **policy baseline** 约束:baseline 由部署方在 coordinator 安装位置提供(与合同分离),声明这些字段的**允许上界**;R0 校验合同不得越过 baseline(如 allowlist 不得包含 baseline 禁止的 code、`visual_thresholds` 不得松于 baseline 上限、`projection.lost` 不得包含 baseline 标记为必须 preserved 的 field_id)。缺少 baseline 时,L0 允许运行并在报告中标 `policy_baseline=absent`;**L1/L2 缺少 baseline 即 `contract_invalid`**。没有这一层,"合同摘要稳定"只能证明弱合同未被运行中篡改,不能证明合同足够强。

风险等级由外部 policy 在运行前选择并写入合同 `required_isolation_grade`;Producer 不能自行降级。coordinator 记录 `achieved_isolation_grade`,并按 §2.6 参与放行判定。等级偏序:`local-trusted` ⊏ `isolated` ⊏ `attested`。

### L0:可信本地建模(`local-trusted`)

适用:个人项目、输入由当前操作者生成、不自动发布。必需 R0~R5 全部;R1 只记录 exact bytes,不要求只读 staging;允许同一 UID;不要求签名或第二个 clean-run。

### L1:CI 或第三方资产(`isolated`)

在 L0 上增加:

1. **进程隔离——可证明基线**(按平台声明,不得混淆):
   - Linux CI:nsjail/bwrap + seccomp 白名单,新 namespace、默认断网、只读输入挂载、专属输出;
   - macOS:**独立 OS 用户**(不同 uid;输入对该用户只读、输出目录专属)或 VM/受控远程 runner。`sandbox-exec` 已被 Apple 标记 DEPRECATED 且 SBPL 无受支持文档(本机 `man sandbox-exec` 实证),**不得计入受支持安全边界**;如附加使用只能标 `best-effort defense-in-depth`,失效不改变判定。macOS 本机无法建立独立用户/VM 时,该平台不满足 L1——按 §2.6 直接 Fail(不静默降级);
   - OS 级强制断网:Linux namespace 可证明;macOS 本机只能达到应用层(`--offline-mode` + 代理环境变量清洗),不得声明为 OS 级断网。
2. **资源限制**(所有平台可证明):coordinator 以 POSIX rlimit 设置子进程 CPU 时间、地址空间、打开文件数、`RLIMIT_FSIZE`;超限终止即 Fail,不重试。
3. **不可信字节接触次序**:仅适用于自研解析工具("先打开全部输入/输出 fd,再接触不可信字节");Blender、格式 validator 等按路径递归加载的第三方工具改用只读输入挂载/目录白名单 + 资源限制。
4. **内嵌媒体解码与几何解析同级隔离**(SketchUp 事件 117 个漏洞中 97 个来自内嵌图像解码路径)。
5. 两个独立 clean child 与四级确定性比较(§5.5)、依赖闭包 + 空缓存 offline reopen、L1 夹具全套。
6. **解析器版本钉死属于合同**:OpenUSD ≥26.08 且 `PXR_PREFER_SAFETY_OVER_SPEED` 构建(GHSA-8878-wr6v-j5cm:恶意 `.usdc` 打开不报错、`UsdAttribute::Get()` 解包才触发超大分配);blender-asset-tracer 用官方 `projects.blender.org/blender/blender-asset-tracer` 1.x 线 ≥v1.23,其 changelog 只明确覆盖到 Blender 5.0 文件特性——**对 Blender 5.2 依赖类型(linked libraries、UDIM、GN simulation cache、Alembic/USD cache、字体、音频)先建 fixture matrix,验证前 BAT 仅作交叉验证,主用可信 Blender 进程内枚举**。

**L1 的实现边界(诚实声明)**:本文冻结了 L1 的**目标与验收条件**(可证明隔离、资源限制、断网分级、解析器版本),但**未冻结**具体 runner 实现、seccomp profile 内容、mount namespace 布局、网络阻断的证明方法与 `achieved_isolation_grade` 的测量算法。这些属 P1 交付物;在它们冻结前,**L1 完成定义不可据本文直接实现**,任何声称达到 `isolated` 的运行都必须附带其测量方法的独立说明。P0 只用 L0,不受此限。

### L2:生产发布或合规(`attested`)

在 L1 上增加:角色分离、签名 contract/approval、DSSE + Sigstore(可由 GitHub Artifact Attestations 承载——它是 **CI provenance carrier**,把产物 digest 链接到源码与构建过程,本身不是质量或安全保证;签发对象为发布产物与 evidence manifest,不是每次测试输出)、可信时间/透明日志、内容寻址晋级、Publisher receipt。

C2PA 不作为 P0/P1 的验收证据载体,但**理由是成本与生态,不是能力**:C2PA 2.4 支持 external manifest(sidecar),可用内容哈希绑定不内嵌凭证的资产,并新增 repository receipt assertion;只要合同规定"manifest 必须存在且可验证",凭证缺失与被剥离**都直接失败**,fail-closed 完全可达。(V3.5 曾以"无法区分从未验收与被剥离"论证其不可用——该推理不成立,两种情况本就都应失败、无需区分,已撤回。)不采用的实际原因是:其规范与工具链面向媒体发布,`.blend`/`.glb` 无内嵌类型定义,而 DSSE + Sigstore 已能直接承载任意文件 digest 且与 §2.5.1 的摘要模型同构。仅 P2 对外发布渲染图环节可选。

---

## 2. 判定模型(规范)

### 2.1 术语定案

| 术语 | 定义 |
|---|---|
| `stage` | 恰好等于一个 gate:`R0`…`R5`。每个 check 属于且仅属于一个 stage(见 §7 注册表) |
| `check` | 注册表中的一条判定项,有稳定 ID、stage、`required` 标志、实现版本、执行序 |
| `required` | **由 §7.1 check registry 声明(P0 表上方一句统一声明全部条目 `required=true`,故表中不另设列;P1 引入非 required check 时须为该表补一列 `required`),不由运行时决定**。合同只能在注册表的 required 子集上追加,不能把 required 改成非 required |
| 非 required check | P0 中**不存在**。注册表全部 `required=true`;为将来保留语义:非 required check 的 `Fail` 记入报告但不阻断放行,且**永远不得**是 `Crash`/`Missing`/`Truncated`(这三者一律阻断,不分 required) |
| `advisory` | 软信号(P1 的 FLIP/VLM 评分等),写入 `advisories[]` 数组,**不是 check、不进注册表、不参与 §2.6 任何一条**。这是"软评分永不参与硬判定"的唯一实现方式 |
| `success`(子进程字段) | **仅表示"本子进程完成了计划内的全部工作并写出了全部计划内 check 记录"**,不表示这些 check 都通过。检出缺陷的子进程仍应 `success=true` 且 exit 0 |
| 子进程退出码约定 | exit 0 = 完成(无论 check 结果);非 0 = 基础设施失败(未完成、未能写出记录)。子进程**不得**因 check 判 Fail 而非零退出——否则父级只会看到 `Missing`,拿不到预期 failure code |

### 2.2 门禁表

| Gate | Required 动作 | Required 证据 | Fail 条件(均映射到 §7.1 的具体 check ID) |
|---|---|---|---|
| R0 Contract | 加载并封闭校验 `contract.json`(未知字段即 Fail);冻结 artifact_kind、Profile、export set、check 集与实现版本与执行序、阈值、validator 配置、工具锁定表、资源上限、N/A 集、golden 引用 | `contract.json` 及其 digest | 未知字段/ID、隐式 N/A、工具版本未锁定 |
| R1 Freeze | L1/L2 复制到新私有只读 staging;所有等级记录输入与依赖的大小与 SHA-256 | 输入/依赖清单 | 旧 root、链接/设备文件、路径逃逸、资源超限、读取竞态 |
| R2 Inspect | clean Blender(`--background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1`)运行 trusted inspector;枚举全部 datablock 与 authored/evaluated 摘要;依赖清单 | source manifest、dependency report | 缺对象、NaN/Inf、依赖缺失、coverage 不完整、候选代码执行 |
| R3 Produce/Validate | 仅对适用 kind 在新进程以固定 preset 导出/渲染;先做 size>0 smoke;再跑独立格式 validator(**解析 JSON report 判定**,退出码仅辅助)与预算统计 | deliverable、producer log、format report、budget report | source 前后 rehash 改变、输出空、validator error、report 截断、外部资源未读、**出现被禁扩展**、预算超限 |
| R4 Reopen/Evidence | `blend_native`:clean offline reopen;`interchange`:第二 clean 进程 fresh-import + §6 投影 diff。两者均生成 evaluator-owned 视觉证据(§5) | reopen/imported manifest、projection diff、图像与渲染设置清单 | 只证明"能打开"、字段超容差、缺图、candidate compositor 欺骗 |
| R5 Decide | 按 §2.6 汇总;比较 expected/actual check 与 file ID 集;复算 contract digest;校验 exit/schema/success/hash | `summary.json`、evidence manifest | 见 §2.6 全部条件 |

补充规则:

- **结果文件生命周期**:每个子进程结果文件路径启动前必须不存在(`O_EXCL`);已存在 → `stale_result_file`;子进程未产出 → 该证据 `Missing`,**永不读取任何先前存在的同名文件**。
- **零收集即失败**:任一 stage 的 expected 非空而 actual 为空 → Fail。
- **正式证据日志**:全量落盘,单文件上限 32 MiB(与现有 wrapper 一致);达上限记 `Truncated` 并使该证据 Fail。"保尾弃头"只允许用于 LLM/UI 响应通道,须带 `output_truncated` 与原始字节数;两通道不得混用。

### 2.3 Artifact Kind 条件

| Kind | R3 | R4 | P0 |
|---|---|---|---|
| `blend_native` | 不要求 interchange export | clean offline reopen + source 视觉 | ✔ |
| `interchange` | export + 独立格式 validator + 预算统计 | fresh-import 投影 diff + source/import 视觉 | ✔(仅 GLB) |
| `runtime_asset` | 同 interchange | 再加合同声明的 target consumer | ✘ |
| `rendered_media` | render + 独立媒体解码 | 帧/色彩/编码/音轨与视觉回归;不跑 3D import | ✘ |
| `fabrication` | export + 几何/单位/水密/壁厚 validator | 声明切片器时才运行 target consumer | ✘ |

未适用分支由 R0 生成 `NotApplicableByContract` 记录,不能靠省略表达。

**Profile**(R0 必冻结字段,封闭枚举):P0 仅 `static_render`(静帧/结构展示,不要求动画与实时预算);保留值 `realtime`、`rigged_animation`、`procedural`、`fabrication`、`marketplace` 在 P1+ 定义。Profile 只能追加检查,不能移除注册表 required 项。

### 2.4 状态语义

`raw_status` 封闭枚举,写入后不可改写:

```text
Pass | Fail | Warning | NotTested | NotApplicableByContract | Crash | Truncated | Missing
```

`visual_unverified` **不是状态,是 finding code**:表示图像已生成但未被任何判定器实际打开判读,其 `raw_status` 恒为 `NotTested`(从而按 §2.5 → Fail)。P0 的"判读"主体是 oiiotool 或确定性比较器,不是人;人工审阅记录另存于 §8.3,不改变机器判定。

### 2.5 disposition 与 effective status

```text
一个 check 可携带**多条 finding**(外部工具如 glTF-Validator 的官方 schema 是 `issues.messages[]`,同一资产会同时产生多条 error/warning/info)。逐条 finding 定 disposition,再聚合成该 check 的 raw_status:

```text
对每条 finding f:
  f.disposition =
    AcceptedWarning  当且仅当 f.severity == "warning"
                     且 (check_id, f.code, tool_id, tool_version) ∈ R0 冻结 allowlist
    None             其他一切情况

check.raw_status(聚合,冻结优先级):
  Truncated  当 check.source_truncated == true                    # 无法证明"所有 warning 都已 allowlist"
  Fail       当存在 severity == "error" 的 finding
  Warning    当存在 severity == "warning" 且 disposition == None 的 finding
  Pass       当所有 warning 均为 AcceptedWarning 且无 error(info 不影响)
             —— 此时 check.accepted = true
  Pass       当 findings 为空
```

`accepted` 是 summary 中的**派生序列化字段**(§7.3),由上式计算后写出,便于审阅方不重算即可看到;`raw_status` 与逐条 finding 的 `disposition` 均原样保留,不被改写。

effective_status =
  Pass           当 raw_status == Pass
  Pass           当 disposition == AcceptedWarning(同时记 accepted=true,raw 保留)
  NotApplicable  当 raw_status == NotApplicableByContract 且 check_id ∈ R0 的 N/A 集
  Fail           其他一切(含 Warning 无 disposition、NotTested、Crash、Truncated、Missing、
                 以及 NotApplicableByContract 但 ID 不在 N/A 集 → 另记 forged_not_applicable)
```

四元组分量来源:`check_id` 取自 §7.1 注册表;`tool_id` 取自 §7.4 工具锁定表的 `id` 列;`tool_version` 取自该表实测记录值;`warning_code` 对外部工具取其原生稳定码(glTF-Validator 的消息码),对自研检查取 §7.1 注册表 `warning_codes` 列声明的码——**未在注册表声明的自研 warning code 不可 allowlist**(fail-closed)。

### 2.5.1 摘要规范化(冻结算法)

所有进入 digest 的 JSON 对象一律按 **[RFC 8785 JSON Canonicalization Scheme (JCS)](https://www.rfc-editor.org/rfc/rfc8785.html)** 序列化后取 SHA-256:UTF-8 无 BOM、对象键按 UTF-16 码元升序、无多余空白、数字按 ECMAScript `Number::toString` 规则(故 `1` 与 `1.0` 同形)。补充四条项目内规则:

1. **禁止**:重复键、`NaN`/`Infinity`、未规范化 Unicode(输入先做 NFC,否则 `contract_invalid`)、`-0`(一律写 `0`);
2. **数组顺序有语义**,不排序;需要顺序无关的集合(如 `na_check_ids`、`checks[]`)在**写入合同前**即按注册表 order 升序、其余按 ID 字典序规范化,顺序不符 → `contract_invalid`;
3. **域分隔**:被摘要的字节前缀 `bcx.digest.v1.<object_kind>.`(`object_kind` ∈ `contract`/`manifest`/`evidence`),防止不同对象类型共用裸 hash;
4. **路径规范化**:合同内所有路径用 POSIX 分隔符、相对于合同声明的 root、拒绝 `..`/绝对路径/符号链接分量;`input.path` **参与**摘要(路径变更即换合同)。

`contract_digest` = SHA-256(`bcx.digest.v1.contract.` ‖ JCS(contract.json 去除 `contract_digest` 自身字段))。R0 计算并记录,R5 用同一算法重算比对(`r5.contract.digest_stable`)。实现必须附带 golden vectors:同义键序、Unicode NFC/NFD、`1` vs `1.0`、`-0`、嵌套空对象/空数组各一例,跨进程复算一致。

### 2.6 放行公式(唯一)

```text
整体放行(coordinator exit 0)当且仅当以下全部成立:
 1. contract 加载成功,且 R5 复算的 contract digest == R0 记录值
 2. achieved_isolation_grade ⊒ contract.required_isolation_grade
 3. 每个 stage:actual check ID 集 == expected check ID 集(严格相等;先拒绝重复 ID、未知 ID)
 4. 每个 stage:actual file ID 集 == expected file ID 集
 5. 每个 required check 的 effective_status == Pass 或 NotApplicable
    (任一为 Fail → 整体不放行,`failure_code = "check_failed"` 且 `failed_check_ids[]` 非空)
 6. 携带 NotApplicableByContract 的 check ID 集 == R0 声明的 N/A 集(双向包含)
 7. 任何 check 的 raw_status ∉ {Crash, Missing, Truncated}(不分 required)
 8. 所有 required 文件的 hash 与 evidence manifest 一致
 9. 所有子进程 exit == 0,且其产物 schema 合法、success == true
10. advisories[] 不参与以上任何一条
```

条款 6 使"child 伪造 N/A"成为可检出失败(`forged_not_applicable`),条款 2 使隔离等级降级无法静默通过,条款 7 覆盖非 required 情形。allowlist 与 N/A 集均进入 contract digest;任何变更需新 digest 并从 R0 重跑。

### 2.7 N/A 记录的产生与集合构造(使条款 3/4/6/9 可同时满足)

不适用当前 kind 的 check(如 `blend_native` 运行时的全部 `interchange`-only 项)按以下机制处理,**这是条款 3 与条款 6 唯一相容的读法**:

1. **合成方**:R0 阶段由 **coordinator** 为 `contract.na_check_ids` 中每个 ID 合成一条记录,`raw_status = NotApplicableByContract`,归属到该 ID 在 §7.1 注册表中声明的 stage。子进程**永不**产生该状态;子进程产生即 `forged_not_applicable`。
2. **expected 集**:stage S 的 expected check ID 集 = 注册表中 `stage == S` 的**全部** ID(与 kind 无关,恒定)。这使集合恒定、可在 R0 冻结。
3. **actual 集**:stage S 的 actual = 该 stage 子进程写出的记录 ∪ coordinator 为 S 合成的 N/A 记录。二者 ID 不得重叠(重叠 → `expected_set_mismatch`)。
4. **整段跳过的 stage**:当某 stage 的全部 check 均在 N/A 集内(如 `blend_native` 的 R3),该 stage **不启动任何子进程**,其 actual 全部由合成记录构成,`summary.stages.<S>` 记 `{"exit_code": null, "skipped_by_contract": true, "result_file": null}`。条款 9 只对**实际启动过**的子进程生效;条款 4 对该 stage 的 expected file ID 集为空集。
5. **N/A 集的合法性**:R0 由 **coordinator 从自身 §7.1 注册表 + `artifact_kind` 推导**出"不适用 ID 集合"(推导源是代码,不是合同),再校验合同 `na_check_ids` 与该集合**恰好相等**——既不允许把适用的 check 塞进 N/A 逃避执行,也不允许漏掉不适用项(违反任一 → `contract_invalid`)。因此 N/A 集完全由 `artifact_kind` 决定,不是自由字段。

`blend_native` 的 N/A 集 = §7.1 中"适用 kind = interchange"的 12 项(其中 R3 的 7 项构成整段跳过的 stage,R4 的 5 项与该 stage 内其他 check 并存),以及 §7.1.1 file registry 中条件为 kind=interchange 的文件 ID;`interchange` 的 N/A 集 = "适用 kind = blend_native"的 2 项(均在 R4)与对应文件 ID。注册表 34 项 = 20 all + 12 interchange + 2 blend_native。文件集同理按 kind 条件展开,规则与 check 完全一致。

---

## 3. 三个进程边界

- **Producer**(官方 MCP 26 工具链路,含任意 Python)只写自己的候选工作区;
- **Verifier coordinator** 只读输入、在私有全新 evidence root 编排子进程、独占写 evidence;不 import `bpy`;**不在自身进程内解析任何候选可控字节**(GLB 统计见 §7.6);
- **Reviewer/调用方** 只读冻结 evidence。

Blender 不是沙箱:`--disable-autoexec`、`--offline-mode`、`--factory-startup` 都不能替代 §1 的 OS 级隔离。官方链路 `localhost:9876` 无独立鉴权,威胁模型假定同机进程可达。L2 才拆分 Contract Authority、Attestor、Publisher。

---

## 4. Manifest(规范)

### 4.1 manifest 字段表(冻结;`source-manifest.json` 的第四份 schema)

顶层:

```text
schema_version: int = 1
blender_version: str            # 如 "5.2.0"
unit_system: {system: str, scale_length: float, length_unit: str}
frame_range: {start: int, end: int, fps: float}
objects: [ObjectRecord]         # 按 stable_id 字典序
collections: [CollectionRecord] # 按 path 字典序
materials: [MaterialRecord]     # 按 stable_id 字典序
images: [ImageRecord]           # 按 stable_id 字典序
dependencies: [DependencyRecord]
coverage: {enumerated_types: [str], skipped_types: [str],
           datablock_counts: {<type>: int}, total: int}
unsupported_fields: [str]
```

**稳定 ID 与路径语法(冻结)**——解决同名 datablock 与实例消歧:

- `stable_id` = `<TYPE>:<library>:<name>:<disambiguator>`,其中 `TYPE` 为 `bpy.data` 集合名大写(`OBJECT`/`MESH`/`MATERIAL`/`IMAGE`…),`library` 为链接库的相对路径(本地为空串),`name` 为 datablock 名;Blender 保证 `(library, name)` 在同类型内唯一,故 `disambiguator` 恒为空串,保留位供将来使用;
- 名称转义:`\` → `\\`、`:` → `\c`,先转义后拼接,使解析无歧义;
- collection/object 的 `path` = 从 scene collection 到该节点的名称序列(逐段同上转义)用 `/` 连接;同一 datablock 被多处链接时列出全部 path,按字典序;
- instance identity = `(instancer_stable_id, persistent_id_tuple)`,取自 `depsgraph.object_instances` 的 `parent` 与 `persistent_id`。

**记录字段**:

| 记录 | 字段 |
|---|---|
| `ObjectRecord` | `stable_id`、`paths[]`、`type`、`data_stable_id\|null`、`parent_stable_id\|null`、`matrix_world`(16 个量化 float)、`visible_render: bool`、`visible_viewport: bool`、`modifiers: [{name, type, params}]`、`geometry: GeometrySummary\|null`(仅可渲染几何类型)、`material_slot_ids: [str\|null]` |
| `GeometrySummary` | `authored: {vertex_count, edge_count, poly_count, tri_count, positions_digest, normals_digest, uv_digests: [{name, digest}], material_index_digest}`;`evaluated`: 同结构(取 evaluated depsgraph);`bbox: [6 个量化 float]` |
| `CollectionRecord` | `stable_id`、`path`、`children_paths[]`、`object_stable_ids[]`、`exclude: bool`、`hide_render: bool` |
| `MaterialRecord` | `stable_id`、`use_nodes: bool`、`node_summary: [{node_type, name, inputs_digest}]`(按 `name` 字典序)、`links_digest`、`pbr: {base_color[4], metallic, roughness}\|null`(仅当存在 Principled BSDF) |
| `ImageRecord` | `stable_id`、`source`(FILE/PACKED/GENERATED)、`filepath_rel\|null`、`size: [w,h]`、`channels`、`colorspace`、`pixels_digest`(见下)、`packed: bool` |
| `DependencyRecord` | `kind`(IMAGE/LIBRARY/CACHE/FONT/SOUND)、`filepath_rel`、`exists: bool`、`bytes\|null`、`sha256\|null`、`packed: bool` |

**modifier "关键参数"注册表(冻结)**:`params` 只收录该 modifier 类型在下表中声明的属性,其余忽略并计入 `unsupported_fields`;未在表中的 modifier 类型记 `params={}` 并把类型名加入 `unsupported_fields`(使 coverage 缺口显式)。P0 表:`SUBSURF`(`levels`,`render_levels`)、`MIRROR`(`use_axis`)、`SOLIDIFY`(`thickness`)、`ARRAY`(`count`)、`BEVEL`(`width`,`segments`)、`BOOLEAN`(`operation`)、`TRIANGULATE`(`quad_method`)。扩表即 `impl` 递增。

**coverage 完整性算法(冻结)**:按 §4.2 逐类型枚举 `bpy.data` 的具体集合(**排除 `all_ids`**),`coverage.total` = 各类型计数之和;`enumerated_types` 为已建记录的类型,`skipped_types` 为已知不参与判定的类型(`screens`/`workspaces`/`window_managers`/`brushes`/`palettes`)。`r2.inventory.coverage_complete` 当且仅当 `enumerated_types ∪ skipped_types` 覆盖全部非空集合时 Pass;出现任何未分类的非空类型即 Fail。

### 4.2 量化与摘要规则

**量化规则(冻结)**:坐标/法线/UV 取 float64,先 `round(v / 1e-6)` 得整数刻度——**tie-breaking 用 banker's rounding(Python `round` 的默认行为,即 round-half-to-even)**,再乘回 1e-6 并按 `<`(little-endian)打包为 float64;`-0.0` 一律规范化为 `0.0`;`NaN`/`Inf` 出现即 `r2.inventory.no_nan_inf` Fail(不进摘要)。索引用 `<I`(uint32)。数组按 8192 元素分块,逐块 SHA-256,再对块摘要按序拼接后取 SHA-256 得数组摘要。摘要前缀 `bcx.manifest.v1.<field>.`。

`ImageRecord.pixels_digest` 与 §6 `p08` 同规则:解码为 RGBA 8-bit、颜色空间归一到记录的 `colorspace`,对像素缓冲取 SHA-256——**不对文件字节取 hash**(同一图像不同编码会得到不同字节但相同像素)。

实现必须附带量化 golden vectors:`1e-7`(应量化为 0)、`0.5e-6` 与 `1.5e-6`(检验 half-to-even)、`-0.0`、跨块边界(8192±1 元素)各一例。

**datablock coverage 约束**:按具体类型集合枚举并**显式排除 `bpy.data.all_ids`**——它本身重列全部 ID,一并求和会得到精确 2× 的重复计数(本仓 pilot 资产实测:按类型求和 295,含 `all_ids` 得 590)。

**`mesh.validate()` 使用约束**(Blender API:返回 `True` 表示发现**并已修正/移除**非法几何——有副作用):

1. 先在原始数据上完成 authored/evaluated manifest 计算;
2. 仅在 **disposable copy**(`mesh.copy()` 临时 datablock,用后即弃)或独立短命进程上调用 `validate(verbose=True)`;原始 datablock 永不调用;
3. 返回 `True` → `r2.geometry.validate_clean` 记 Fail(数据本含非法结构),不是"已修好"的 Pass;
4. 它不覆盖非流形、法线朝向、UV 重叠、材质语义——这些是独立自建检查。

现有 `scene_hash`([scene_hash.py:13-32](bridge/core/scene_hash.py#L13))仅覆盖名称/类型/量化矩阵/RNA 类型/顶点边面数。**该摘要在代码与协议中的实际字段名就是 `scene_hash`**(`bridge/core/contracts.py:19`、`server/mcp/adapter.py:111`;`phase0_structure_digest` 至今未在任何源码或协议中出现,只是历次方案的改名建议)。本文不要求改名,只规定其语义边界:禁止用于 source↔export、两次 clean-run、checkpoint 或发布 identity。

---

## 5. 视觉协议(规范)

### 5.1 视角与 pass(冻结)

8 视角:`front`、`back`、`left`、`right`、`top`(正交)+ `persp`(透视)+ `obliqueA`、`obliqueB`(固定斜视角,欧拉角见下表)。

`offset` 定义为 **由目标指向相机的单位向量**(`camera_position = C + offset·d`,相机始终 `look_at = C`,故视线方向为 `-offset`)。命名以观察者所见为准:`front` 指"看到物体正面",相机因此位于 -Y 侧。

| 视角 | 类型 | `offset`(目标→相机,单位向量) | up 轴 |
|---|---|---|---|
| front | ORTHO | (0, -1, 0) | +Z |
| back | ORTHO | (0, +1, 0) | +Z |
| left | ORTHO | (-1, 0, 0) | +Z |
| right | ORTHO | (+1, 0, 0) | +Z |
| top | ORTHO | (0, 0, +1) | +Y |
| persp | PERSP | normalize(+1, -1, +0.8) | +Z |
| obliqueA | PERSP | normalize(+1, -1, +0.6) | +Z |
| obliqueB | PERSP | normalize(-1, -1, +0.35) | +Z |

**构图规则(冻结)**:取 evaluated depsgraph 中**全部可渲染几何**的世界包围盒——包含 `MESH`、`CURVE`、`SURFACE`、`META`、`FONT`、`VOLUME`、`POINTCLOUD` 与 `GREASEPENCIL`,以及全部 instance(遍历 `depsgraph.object_instances`,对每个 instance 取其 evaluated geometry 的世界空间角点);排除 `EMPTY`、`CAMERA`、`LIGHT`、`ARMATURE` 与 `hide_render` 对象。记中心 `C`、包围球半径 `r`。

- 正交:`ortho_scale = 2.2r`(几何最小需 2r,含 10% margin),相机置于 `C + offset·(4r)`,`clip_start = 0.1r`、`clip_end = 10r`;
- 透视:焦距 50 mm、传感器宽 36 mm,水平 FOV = `2·atan(18/50)` = **39.598°**;拟合半径 r 的包围球所需最小距离为 `r/sin(FOV/2)` = **2.9523r**,冻结取值 `d = 3.25r`(含约 10% margin),`clip_start = 0.05r`、`clip_end = 10r`。方形画幅下垂直 FOV 与水平相同,故该距离对两轴同时成立。

`r == 0`(无任何可渲染几何)→ `r4.visual.scene_not_empty` Fail。**`r == 0` 只在真正没有可渲染对象时成立;curve-only、font-only、点云等资产必须正常通过。**

> 实测依据(Blender 5.2.0):curve-only 场景的 `depsgraph.object_instances` 类型集合为 `['CURVE']`,**MESH 计数为 0**——V3.5 只取可见 mesh 的规则会得 `r = 0` 并误判空场景。font 对象会同时产生 `FONT` 与其求值 `MESH` 两个 instance,故单独的文本资产恰好能被旧规则捕获,但曲线、点云、体积资产不能。混合资产下旧规则会得到**不完整**的包围盒,使部分几何落在画面外。
> 另一实测(同版本):按本节新参数,半径 `r = 5.0657` 的 curve+font 场景在 `d = 3.25r` 下的最大可见半径为 `5.5766 ≥ r`(完整入画);V3.5 的 `2.6r` 只有 `4.4613 < r`,**必定裁切**。

**pass(冻结,每视角 4 张)**:`beauty`(EEVEE)、`clay`(Workbench,solid、单一 0.8 灰、studio 光照、无纹理)、`silhouette`(Workbench,flat、单色 shadeless、黑底白物)、`wire`(Workbench,wireframe)。共 8×4 = 32 张。P0 硬判定只用 `clay`、`silhouette`、`wire`(Workbench,确定性好);`beauty` 生成并落盘作为证据,但不参与像素回归硬门,除非合同显式声明参考平台键(见 §5.3)。

**渲染设置(冻结)**:分辨率 1024×1024、100%;色彩管理 view transform = `Standard`、look = `None`、exposure 0、gamma 1;输出 PNG RGBA 8-bit;`clay`/`silhouette`/`wire` 使用 Workbench 引擎(其 studio 光照内置,不依赖场景灯光)并关闭 AA 抖动、固定采样数 8;`beauty` 使用 EEVEE、固定采样数 64。

**evaluator-owned 光照(冻结,仅 beauty 需要)**:候选场景的全部灯光与 world 在渲染前被移除/覆盖,由 evaluator 建立固定三点光——`key`:SUN,方向 `normalize(+1,-1,-1)`,energy 3.0;`fill`:SUN,方向 `normalize(-1,-0.5,-0.3)`,energy 1.0;`rim`:SUN,方向 `normalize(0,+1,-0.5)`,energy 1.5;三者 color 均为纯白。world 使用中性灰 `(0.05, 0.05, 0.05)`、strength 1.0(**不是纯黑**——纯黑加无灯会使 beauty 恒为黑图,失去证据价值)。`silhouette` 单独使用纯黑 world 与 shadeless 白色物体,由 Workbench flat 模式实现,不受此项影响。

全部设置由 evaluator 脚本写入,**不读取候选文件的任何 scene render/world/light/compositor 设置**(这是抗 compositor 欺骗的机制)。

### 5.2 P0 的视觉判定(不依赖外部 golden)

P0 不要求预先存在的 golden 图像。判定项为:

1. `r4.visual.all_views_rendered`:32 张全部存在、非零字节、可被 oiiotool 读取(否则 `Missing`);
2. `r4.visual.self_determinism`:同一 run 内对 `clay`/`silhouette`/`wire` 共 24 张各重渲一次(第二组渲染到 `views2/` 子目录),与首次结果按 `oiiotool --fail 0 --failpercent 0 --diff` 逐张比较,**任一张不一致即该 check Fail**(单条 check 聚合 24 张结果)。第二组图像**不进入 evidence file ID 集**(条款 4 只覆盖 `views/` 的 32 张 + 差异图),但其 24 个 SHA-256 以 `{view_pass: [sha_first, sha_second]}` 形式写入该 check 的 `metrics` 字段(§7.3;`detail` 只放单行原因),使判定可复核而不使 file 集随渲染次数漂移;
3. `interchange` 追加 `r4.visual.source_import_match`:source 与 import 的同视角 `clay`/`silhouette` 按 `--fail 0.016 --failpercent 1` 比较(阈值来源见 §5.3),超阈值 Fail,并保存 RGB/Alpha diff。

`blend_native` 因只有一组图,不做跨对象像素回归;其视觉证据由 1、2 加人工审阅记录(§8.3)承载。**这消除了"首张基线从哪来"的循环**:P0 的机器判定不需要基线;需要基线的比较只在 `interchange`(两侧同 run 生成)与 §8 fixture(基线由生成器产出,见 §8.2)中出现。

### 5.3 阈值与平台键

`--fail 0.016 --failpercent 1` 是 **Blender 官方渲染回归的工程起点**(实测 [render_report.py @ e6d1620](https://github.com/blender/blender/blob/e6d1620ad53feed4a83e3b168f0a2ea74f4de6ce/tests/python/modules/render_report.py) 与当前 main 均如此),**不是资产质量依据**。每份合同必须显式声明自己的 `visual_thresholds`,只能收紧,或按平台键放宽。

平台键格式(冻结):`<os>-<arch>-<engine>-<gpu_backend>-<gpu_vendor>`,例如 `macos-arm64-workbench-metal-apple_m4`。

**探测与归一化(冻结)**:在 Blender 子进程内**必须先调用 `gpu.init()`**——background 模式下未初始化时 `gpu.platform.backend_type_get()` 抛 `SystemError`(本机 Blender 5.2.0 实测确认)。随后读 `gpu.platform.backend_type_get()`(实测返回 `METAL`)与 `gpu.platform.vendor_get()`(实测返回 `Apple M4`)。归一化规则:转小写 → 去首尾空白 → 内部连续空白与 `/` 折叠为单个 `_` → 仅保留 `[a-z0-9_]`,其余字符丢弃。故 `Apple M4` → `apple_m4`、`METAL` → `metal`。`gpu.init()` 失败或探测抛异常 → 该 check Fail(`tool_output_invalid`),不得回退默认值。coordinator 另从 `bpy.app.build_platform` 取 os/arch 并同规则归一化,并写入 `summary.json.platform_key`;合同 `visual_thresholds` 是 `platform_key → {fail, failpercent}` 的映射,缺键 → `r4.visual.platform_key_known` Fail(不静默用默认值)。`blocklist` 是同格式键的数组,列出**明确不支持验收的平台**,命中即 Fail。

失败态映射(与 Blender 上游术语对齐,不新增状态):子进程崩溃 → `Crash`;输出缺失/零字节 → `Missing`;超阈值 → `Fail`。

### 5.4 软评分(P1 起,非 P0)

FLIP 与 VLM/CLIP 评分进入 `advisories[]`,按 §2.1 定义**永不参与 §2.6**。引入时:版本入 §7.4 工具锁定表;同一视角必须同时评 `beauty` 与 `clay` 两版以对抗 typographic 作弊,分差超合同阈值 → 写入 advisory 并触发人工告警(不改机器判定);评分渲染一律 evaluator-owned,拒收候选自渲图。

### 5.5 确定性分级(L1)

| 级别 | 比较对象 | 典型容差 |
|---|---|---|
| Byte | exact artifact bytes | 0 |
| Structure | 层级、数量、标识、依赖图 | 0 |
| Geometry | evaluated positions/normals/UV/bounds | 合同量化容差(默认 1e-5 绝对) |
| Render | clay/silhouette/wire | 合同 fail+failpercent |

含时间戳、随机 seed、GPU 非确定性的层先规范化或声明不可要求 byte deterministic,其余 applicable 层仍需比较。

---

## 6. GLB 投影映射(规范,消除"投影规则未定义")

`interchange/glb` 的 source↔import 比较只在下表声明的字段上进行。表中未出现的字段不参与判定;**声明为 preserved 的字段发生差异即 Fail**;**未被合同 `projection.lost` 列出的字段(即 preserved/transformed 两类)若实际丢失,记 `r4.projection.undeclared_loss` Fail**——即"丢失"本身不是问题,"未预先声明的丢失"才是。合同 `projection` 三个数组的并集必须恰好等于本表 13 行,缺项或多项 → `contract_invalid`。

**比较空间(冻结,修正 V3.5 的实测错误)**:两侧 manifest **均在 Blender 空间**采集——source 侧来自 R2 inspector,import 侧来自 R4 在新 Blender 进程中 `import_scene.gltf` 后的同一套采集代码。Blender 的 glTF 导出器与导入器**已在文件边界各自完成一次 Z-up↔Y-up 转换**,回环后坐标不变(本机 Blender 5.2.0 实测:位置 `(1,2,3)` 导出 GLB 再导入仍为 `(1,2,3)`)。**因此比较时不得再施加任何换轴**;V3.5 曾要求对 import 侧施加 `(x,-z,y)`,那会把合法回环误算成 `(1,-3,2)` 并误拒——已删除。若将来改为在 raw glTF 边界比较(不经 Blender 导入),才需要显式做且仅做一次 Y-up→Z-up 转换,并须另立 field ID。

| field_id | manifest 字段 | 分类 | 变换/容差 |
|---|---|---|---|
| `p01_object_count` | 可渲染 object 数量 | preserved | 精确相等 |
| `p02_triangle_count` | 每 object 的三角形数 | preserved | 精确相等(source 侧取 evaluated 三角化后计数) |
| `p03_bbox` | 顶点位置包围盒 | preserved | 两侧均为 Blender 空间,**不换轴**;容差 1e-4 × 包围球半径 |
| `p04_vertex_count` | 顶点数 | transformed | 导出因 UV/法线接缝拆点而增加,允许 `import ≥ source`,比值上限由合同 `vertex_split_ratio_max`(默认 3.0)约束 |
| `p05_uv_layers` | UV 层数量与每层存在性 | preserved | 精确相等(名称可变,顺序保持) |
| `p06_material_slot_count` | material slot 数量 | preserved | 精确相等 |
| `p07_pbr_factors` | 每 material 的 base color / metallic / roughness | transformed | Principled BSDF → pbrMetallicRoughness 映射;容差 1e-3 |
| `p08_texture_pixels` | 纹理图像内容 | preserved | **按像素比较,不比字节**:两侧图像各自解码为 RGBA 8-bit、颜色空间统一为合同 `texture_colorspace`(默认 `Non-Color` 用于数据贴图、`sRGB` 用于 base color),再对像素缓冲取 SHA-256 后比较。尺寸/通道不同即 Fail。**禁止仅比较尺寸与通道数**——那会让同尺寸的不同贴图假绿(V3.5 缺陷,已修正) |
| `p09_object_identity` | object 身份对应 | transformed | **不依赖名称**:导出时由 `export_glb.py` 为每个源 object 写入 glTF `extras.bcx_uid`(值为 R2 manifest 的稳定 object ID),导入后由该 extras 回连。若目标 glTF 剖面禁止 extras,则退化为名称匹配并**必须先检测归一化碰撞**:若去后缀后出现重名(如 `Cube` 与 `Cube.001` 同时存在),该资产判 `r4.projection.ambiguous_object_names` Fail,不得静默折叠(V3.5 缺陷,已修正) |
| `p10_collection_hierarchy` | collection 层级 | lost | glTF 摊平为 node 树 |
| `p11_modifier_stack` | modifier 栈 | lost | 导出即烘焙 |
| `p12_custom_props` | 自定义属性、驱动、约束 | lost | 注:`extras.bcx_uid` 由 evaluator 写入,不属候选自定义属性 |
| `p13_unit_system` | 单位系统 | transformed | glTF 固定米;source 非米制时按比例换算后比较 |

合同 `projection` 的三个数组存的是**上表 `field_id`**(稳定 ASCII 标识符),不是中文描述;三数组并集必须恰好等于 `p01`…`p13` 全集,缺项/多项/未知 ID → `contract_invalid`。这使"并集等于 13 行"成为可机械校验的断言(V3.5 存中文描述,无法校验,已修正)。

---

## 7. P0 实施合同(L0,可直接编码)

### 7.1 Check registry(冻结;`check_registry.py` 的内容即本表)

ID 命名规则:`<stage>.<domain>.<name>`,全小写 snake,stage ∈ {r0…r5}。全部 `required=true`(P0 无非 required check)。`order` 为同 stage 内执行序。实现版本 `impl` 随该 check 逻辑变更递增,与 ID、order 一并进入 contract digest。

| ID | stage | order | impl | 适用 kind | warning_codes |
|---|---|---|---|---|---|
| `r0.contract.schema_closed` | R0 | 10 | 1 | all | — |
| `r0.contract.tools_locked` | R0 | 20 | 1 | all | — |
| `r0.contract.na_set_declared` | R0 | 30 | 1 | all | — |
| `r1.input.digest_recorded` | R1 | 10 | 1 | all | — |
| `r1.input.no_link_or_device` | R1 | 20 | 1 | all | — |
| `r1.input.size_within_limit` | R1 | 30 | 1 | all | — |
| `r2.inventory.coverage_complete` | R2 | 10 | 1 | all | `unsupported_datablock_type` |
| `r2.inventory.no_nan_inf` | R2 | 20 | 1 | all | — |
| `r2.geometry.validate_clean` | R2 | 30 | 1 | all | — |
| `r2.geometry.manifest_written` | R2 | 40 | 1 | all | — |
| `r2.material.slots_resolved` | R2 | 50 | 1 | all | `empty_material_slot` |
| `r2.dependency.all_present` | R2 | 60 | 1 | all | `packed_dependency` |
| `r2.source.digest_stable` | R2 | 70 | 1 | all | — |
| `r3.export.file_nonempty` | R3 | 10 | 1 | interchange | — |
| `r3.export.source_unchanged` | R3 | 20 | 1 | interchange | — |
| `r3.validator.no_error` | R3 | 30 | 1 | interchange | (glTF-Validator 原生码) |
| `r3.validator.resources_read` | R3 | 40 | 1 | interchange | — |
| `r3.validator.report_complete` | R3 | 50 | 1 | interchange | — |
| `r3.extension.none_forbidden` | R3 | 60 | 1 | interchange | — |
| `r3.budget.within_limits` | R3 | 70 | 1 | interchange | `budget_near_limit`, `non_triangle_primitive` |
| `r4.reopen.offline_ok` | R4 | 10 | 1 | blend_native | — |
| `r4.reopen.dependencies_resolved` | R4 | 20 | 1 | blend_native | — |
| `r4.import.manifest_written` | R4 | 30 | 1 | interchange | — |
| `r4.projection.preserved_fields_match` | R4 | 40 | 1 | interchange | — |
| `r4.projection.undeclared_loss` | R4 | 50 | 1 | interchange | — |
| `r4.projection.ambiguous_object_names` | R4 | 55 | 1 | interchange | — |
| `r4.visual.scene_not_empty` | R4 | 60 | 1 | all | — |
| `r4.visual.all_views_rendered` | R4 | 70 | 1 | all | — |
| `r4.visual.self_determinism` | R4 | 80 | 1 | all | — |
| `r4.visual.platform_key_known` | R4 | 90 | 1 | all | — |
| `r4.visual.source_import_match` | R4 | 100 | 1 | interchange | — |
| `r5.evidence.manifest_closed` | R5 | 10 | 1 | all | — |
| `r5.evidence.hashes_match` | R5 | 20 | 1 | all | — |
| `r5.contract.digest_stable` | R5 | 30 | 1 | all | — |

不适用当前 kind 的 check 由 R0 写入 N/A 集,按 §2.6 条款 6 校验。`blend_native` 的 N/A 集 = 全部 `interchange`-only ID;反之亦然。

### 7.1.1 File registry(冻结;条款 4 的 expected file 集即本表)

`id` 为稳定 ASCII 标识;`path` 相对 evidence root;`producer` = 写出方;`条件` 为空表示恒出现。视觉图像用模板展开:`{view}` ∈ 8 视角、`{pass}` ∈ 4 pass。

| file_id | stage | producer | path | 条件 |
|---|---|---|---|---|
| `contract_snapshot` | R0 | coordinator | `contract.json` | — |
| `input_manifest` | R1 | coordinator | `input.json` | — |
| `source_manifest` | R2 | inspector | `r2/source-manifest.json` | — |
| `dependency_report` | R2 | inspector | `r2/dependencies.json` | — |
| `r2_result` | R2 | inspector | `r2/result.json` | — |
| `deliverable_glb` | R3 | export_glb | `r3/asset.glb` | kind=interchange |
| `format_report` | R3 | coordinator | `r3/validator-report.json` | kind=interchange |
| `budget_report` | R3 | glb_budget | `r3/budget.json` | kind=interchange |
| `r3_result` | R3 | coordinator | `r3/result.json` | kind=interchange |
| `reopen_manifest` | R4 | reopen_probe | `r4/reopen-manifest.json` | kind=blend_native |
| `imported_manifest` | R4 | reimport_probe | `r4/imported-manifest.json` | kind=interchange |
| `projection_diff` | R4 | coordinator | `r4/projection-diff.json` | kind=interchange |
| `view_{view}_{pass}` | R4 | render_views | `r4/views/{view}-{pass}.png` | 32 项(8×4) |
| `render_settings` | R4 | render_views | `r4/render-settings.json` | — |
| `visual_diff_{view}_{pass}` | R4 | coordinator | `r4/diff/{view}-{pass}.png` | kind=interchange,仅 `clay`/`silhouette` 两 pass × 8 视角 = 16 项 |
| `r4_result` | R4 | coordinator | `r4/result.json` | — |
| `summary` | R5 | coordinator | `summary.json` | — |
| `evidence_manifest` | R5 | coordinator | `evidence-manifest.json` | — |

规则:

- **差异图恒生成**(不只在失败时),使集合与结果无关、可在 R0 冻结;`blend_native` 无差异图(该 16 项进入其 N/A 文件集,机制同 §2.7)。
- 第二组自确定性渲染写入 `r4/views2/`,**不属本表**,故不进条款 4(其哈希写入 check 的 `metrics`,见 §5.2)。
- **R0 与 R5 的 check 记录由 coordinator 直接写入 `summary.json`,不产生独立 `result.json`**(`result.json.stage` 因此只有 `r1`…`r4`)。coordinator 是这两个 stage 的 producer,其记录与子进程记录在 §2.6 条款 3 中一并参与集合相等校验。
- **`output_truncated` / `source_truncated` 的唯一映射**:任一 required 证据文件达到 32 MiB 上限,或工具报告自身标记截断 → 对应 check 的 `raw_status = Truncated` → 按 §2.5 → Fail,并使 `failure_code = evidence_truncated`。不存在"截断但放行"的路径。

### 7.2 Failure-code family(冻结封闭集;`failure_codes.py` 的内容即本表)

底层 OS/第三方动态错误一律映射到下列父级 code,原始细节存 `detail` 字段;**不为无界底层错误码逐一建夹具**。

**第一分类:失败必须先分两类**——`check_failed`(资产本身被拒收,验收流程正常完成)与其余 13 个基础设施 family(流程未能正常完成)。`summary.failure_code` 取值规则:

1. 若存在任何基础设施失败 → 取其中**优先级最高**的一个(优先级 = 下表自上而下的顺序,`runner_internal_error` 最低);
2. 否则若存在 `effective_status == Fail` 的 check → `failure_code = "check_failed"`,并**必须**填充 `failed_check_ids[]`(按注册表 order 升序,不去重前先拒绝重复);
3. 二者皆无 → `success = true`、`failure_code = null`。

夹具的预期断言写在 `(failure_code, failed_check_ids)` 二元组上,而不是笼统的 "Fail"。

| family | 类别 | 触发 |
|---|---|---|
| `contract_invalid` | infra | schema 未知字段、缺字段、类型错、digest 不稳、`projection` 并集不等 |
| `toolchain_mismatch` | infra | 工具版本/hash 与锁定表不符,或锁定表要求的工具未安装 |
| `tool_crashed` | infra | 子进程或外部工具**异常终止**:信号终止、无输出、或非零退出**且未产出合法报告**。**glTF-Validator 在发现 error 时按其官方约定非零退出,但同时产出完整 JSON 报告——这是"检查失败"而非 crash**,归 `check_failed`(V3.5 缺陷:原定义会把正常的格式拒收误报为工具崩溃,已修正) |
| `tool_output_invalid` | infra | 产物非法 JSON、schema 不符、重复 key、NaN/Inf、超限 |
| `stale_result_file` | infra | 结果文件启动前已存在 |
| `zero_checks_collected` | infra | expected 非空而 actual 为空 |
| `expected_set_mismatch` | infra | check/file ID 集不等、重复或未知 ID |
| `forged_not_applicable` | infra | N/A 状态的 ID 不在 R0 N/A 集 |
| `evidence_missing` | infra | required 证据文件缺失或零字节 |
| `evidence_truncated` | infra | 证据达大小上限 |
| `hash_mismatch` | infra | 文件 hash 与 manifest 不一致 |
| `isolation_insufficient` | infra | achieved < required isolation grade |
| `resource_limit_exceeded` | infra | rlimit 触发(L1) |
| `runner_internal_error` | infra | coordinator 自身未预期异常 |
| `check_failed` | **asset** | 流程完整跑完,但至少一个 check 的 effective_status == Fail;细节见 `failed_check_ids[]` |

### 7.3 JSON schema 字段(冻结)

**`contract.json`**(顶层字段封闭,未知字段即 `contract_invalid`):

```text
schema_version: int = 1
contract_id: str                      # 稳定标识
artifact_kind: "blend_native"|"interchange"
profile: "static_render"
required_isolation_grade: "local-trusted"|"isolated"|"attested"
input: {path: str, sha256: str, bytes: int}
export: {format: "glb"|null, preset: {...}}     # blend_native 时为 null
checks: [{id: str, impl: int, order: int}]      # 必须与 §7.1 注册表逐项相等
na_check_ids: [str]
warning_allowlist: [{check_id, warning_code, tool_id, tool_version}]
visual_thresholds: {<platform_key>: {fail: float, failpercent: float}}
platform_blocklist: [str]
budget: {max_triangles: int, max_materials: int, max_images: int,
         max_image_bytes: int, max_file_bytes: int, vertex_split_ratio_max: float}
projection: {preserved: [str], transformed: [str], lost: [str]}   # 见 §6
tools: [{id: str, version: str, sha256: str|null, path: str}]
limits: {cpu_seconds: int, address_space_bytes: int, open_files: int, file_size_bytes: int}
golden: {fixture_id: str, expected_dir: str}|null
```

**`result.json`**(每个子进程产出):

```text
schema_version: int = 1
stage: "r1"|"r2"|"r3"|"r4"
success: bool                          # 语义见 §2.1
contract_digest: str
checks: [{id: str, raw_status: str,
          tool_id: str|null, tool_version: str|null,
          findings: [{code: str, severity: "error"|"warning"|"info",
                      pointer: str|null, offset: int|null,
                      disposition: "AcceptedWarning"|null, detail: str|null}],
          source_truncated: bool,    # 工具报告自身被截断(如 validator 的 issues.truncated)
          detail: str|null,          # 人类可读的单行原因
          metrics: object|null}]     # 结构化证据(数组/映射),如逐张哈希、计数、实测值
files: [{id: str, path: str, bytes: int, sha256: str}]
advisories: [{code: str, detail: str}]
output_truncated: bool
```

**`summary.json`**(coordinator 产出):

```text
schema_version: int = 1
kind: "asset_acceptance"
success: bool
contract_id: str
contract_digest: str
artifact_kind: str
required_isolation_grade: str
achieved_isolation_grade: str
platform_key: str
started_at / completed_at: ISO-8601 UTC
stages: {<stage>: {exit_code: int|null, skipped_by_contract: bool,
                     result_file: {...}|null}}   # 整段跳过时 exit_code=null、skipped=true(§2.7-4)
checks: [{id, stage, raw_status, effective_status, accepted: bool,
          tool_id, tool_version, findings: [...], source_truncated: bool,
          detail, metrics}]        # findings 逐条含 code/severity/disposition,审阅方可据此重算 allowlist
evidence_manifest: [{id, path, bytes, sha256}]
advisories: [...]
failure_code: str|null                 # success=false 时必填,取自 §7.2
failed_check_ids: [str]                # failure_code=="check_failed" 时必填(按 order 升序),否则为 []
error: str|null
runner_provenance: {acceptance_files: [{path: str, sha256: str}],
                    tools: [{id: str, version: str}],
                    input_digest: str}   # §7.7.1 承诺的四项 provenance 的落点
```

### 7.4 外部工具锁定表(结构冻结;版本值在 P0 首次实施时填死并入 contract digest)

| id | 工具 | 用途 | 锁定值(本机 2026-08-24 实测) | 校验方式 |
|---|---|---|---|---|
| `blender` | Blender | R2/R3/R4 子进程 | `5.2.0 LTS`,build hash `fbe6228777e7`,build date `2026-07-14` | 绝对路径 + `--version` 首行与 build hash 精确匹配 |
| `python` | CPython | coordinator | `3.13.13` | `sys.version_info[:3]` 精确相等 |
| `uv` | uv | 依赖与子进程 | `0.12.2` | `uv --version` 前两段精确匹配 |
| `gltf_validator` | Khronos glTF-Validator | R3 合规层 | `2.0.0-dev.3.10`(npm 最后发布,2024-10-22)| 可执行文件 SHA-256 + `--version`;**调用形态一并冻结**:`gltf_validator -r -o -a <file>`(`-r` 显式开启资源验证——CLI 默认开但库 API 默认关,故必须显式;`-o` 输出 JSON 到 stdout),`--config <file>` 的 YAML 本身入 contract digest |
| `oiiotool` | OpenImageIO | R4 像素回归 | **本机未安装**——P0 前置条件 | 安装后填入 `--version` 实测值与来源(Homebrew formula 版本或构建 commit),`r0.contract.tools_locked` 校验其存在且匹配 |
| `flip` / `gltf_transform` / `bat` | — | P1 起 | — | 进入本表后方可使用 |

**hash 边界(冻结)**:`sha256` 对**被直接执行的文件**计算(单文件可执行或入口脚本);对 macOS `.app` bundle 形态的 Blender,hash 其 `Contents/MacOS/Blender` 可执行文件,并另记 build hash——不对整个 bundle 递归求 hash(不确定且昂贵)。`sha256` **不允许为 null**;无法取得 hash 的工具不得进入锁定表,从而不得在 P0 使用。

**P0 前置条件(诚实记录)**:`oiiotool` 与 `gltf_validator` 在本机尚未安装。P0 首个可运行版本之前必须完成安装并把实测值填入本表;在此之前 `r0.contract.tools_locked` 恒 Fail(`toolchain_mismatch`),这是预期行为,不是缺陷。

**GLB 导出 preset(冻结,`contract.export.preset`)**:`export_format='GLB'`、`export_apply=True`(应用 modifier)、`export_yup=True`(导出器默认,与导入端对称,见 §6)、`export_draco_mesh_compression_enable=False`、`export_image_format='AUTO'`、`export_jpeg_quality=100`、`export_texture_dir=''`(内嵌)、`export_cameras=False`、`export_lights=False`、`export_animations=False`(P0 静态)、`export_extras=True`(承载 `bcx_uid`,见 §6 `p09`)、`export_skins=False`、`export_morph=False`。KTX2/basisu 与 `KHR_animation_pointer` 在此 preset 下不产生;`r3.extension.none_forbidden` 另做出后校验。

工具输出解析失败 → `tool_output_invalid`;版本/hash 不符或工具缺失 → `toolchain_mismatch`。

### 7.5 包结构(定案)

```text
acceptance/
  __init__.py
  primitives.py          # 复制自 run_phase0_acceptance.py 的最小原语(§7.7)
  contract.py            # contract.json 封闭加载与 digest
  check_registry.py      # §7.1 表
  failure_codes.py       # §7.2 表
  decide.py              # §2.5/§2.6 判定引擎(唯一实现处)
  evidence.py            # evidence manifest 与 summary.json 写入
  pixel.py               # oiiotool 调用与结果解析
  projection.py          # §6 映射比较器
  glb_budget.py          # §7.6 GLB 统计(在独立子进程中运行)
  schemas/
    contract.schema.json / result.schema.json / summary.schema.json
  blender_scripts/       # 在 Blender 子进程内运行,可 import bpy
    inspector.py         # R2
    export_glb.py        # R3 固定 preset(禁 Draco/KTX2/animation_pointer)
    reopen_probe.py      # R4 blend_native 的 offline reopen
    reimport_probe.py    # R4 interchange 的 fresh-import 投影提取
    render_views.py      # R4 8 视角 × 4 pass
scripts/asset_accept.py  # 薄 CLI(argparse → acceptance.decide 等)
tests/unit/test_asset_accept.py       # 判定引擎与 coordinator(合成产物,无 Blender)
tests/asset_fixtures/{generators,expected,artifacts}/
docs/acceptance/         # 方案归档位(§11)
```

### 7.6 GLB 预算层(自研,更正 V3.4 的两处技术错误)

`glb_budget.py` 在**独立短命子进程**中运行(不在 coordinator 进程内接触候选字节),按 GLB 容器规范读 header 与 JSON chunk(严格 JSON、大小上限),统计:

- `mesh_count` = `meshes` 数组长度;`primitive_count` = 各 mesh 的 primitives 之和;
- **`triangle_count`**:对每个 primitive,若有 `indices` 则取该 accessor 的 `count`,否则取 `POSITION` accessor 的 `count`;再按 `mode` 换算——`4/TRIANGLES`(默认):`n/3`;`5/TRIANGLE_STRIP`、`6/TRIANGLE_FAN`:`n-2`;其余 mode 记 0 并置 `r3.budget.within_limits` 的 warning `non_triangle_primitive`。(V3.4 误写为"accessor count 即三角形数",更正)
- `material_count`、`image_count` = 对应数组长度;
- **图像尺寸不可从 glTF JSON 获得**——`image` 对象只有 `uri`/`mimeType`/`bufferView`/`name`(实测 Khronos `image.schema.json` 属性集为 `bufferView, extensions, extras, mimeType, name, uri`)。因此预算键改为 `max_image_bytes`(按 `bufferView.byteLength` 或外部文件大小统计),**不统计像素宽高**;需要宽高时属 P1 且必须在沙箱内解码图像头。(V3.4 误列"声明的 image 尺寸",更正)
- `extensions_used`/`extensions_required` 全集,用于 §9 盲区表的 forbid 判定(`r3.extension.none_forbidden`);
- 不解码任何二进制载荷。

### 7.7 与既有代码的关系(修正 V3.5 的"零修改"约束)

**V3.5 曾要求"P0 不修改任何既有文件",该约束经复核不成立且有害**,已撤销。实测证据:

| 既有配置 | 现状(实测) | 后果 |
|---|---|---|
| `scripts/checks.sh` ruff 范围 | `protocol bridge server tests scripts smoke plugins/…` | `acceptance/` **不被 lint** |
| `pyproject.toml` `[tool.mypy] files` | `["protocol", "bridge/core", "server"]` | `acceptance/` **不被类型检查** |
| `checks.sh` RELEASE Bandit 范围 | 同样不含 `acceptance/` | 安全敏感代码**不被扫描** |
| `[tool.hatch.build.targets.wheel] packages` | `["protocol", "bridge", "server"]` | 新包不入 wheel/sdist |
| `[project.scripts]` | 仅 `blender-codex-server` | 无验收 CLI 入口 |

即:坚持零修改会让**安全敏感的验收代码完全逃过全部静态门禁,而 `checks.sh` 仍然全绿**——这与本方案"证据不说谎"的前提直接冲突。

**定案**:

1. **边界**:资产验收工具为 **repo-only**,不进 wheel/sdist(`only-include` 与 sdist 白名单**不变**,避免扩大分发面);因此 `[project.scripts]` 也不新增入口,CLI 以 `uv run python scripts/asset_accept.py` 调用。
2. **必须修改的既有文件(最小集)**:`scripts/checks.sh` 的 ruff 与 RELEASE Bandit 路径列表各加 `acceptance`;`pyproject.toml` 的 `[tool.mypy] files` 加 `"acceptance"`。两处均为纯增列,不改变既有行为。
3. **共享原语改为提取,不复制**(撤销 V3.5 的复制方案):把 root 规范化与私有目录、环境清洗、严格 JSON 三件套、`_file_evidence`、`_write_json_exclusive`、进程组运行/终止、`AcceptanceFailure`(实测函数体约 135 行)提取为 `acceptance/primitives.py`,并让 `scripts/run_phase0_acceptance.py` 回 import。理由:这些是**安全敏感**逻辑(权限位、`O_EXCL`、进程组清理),复制后靠人工"同步检查"必然漂移;而既然门禁配置已必须修改,"零修改"这一原本支持复制的唯一理由已不存在。
   - **风险控制**:该重构是纯搬迁,不改语义;完成标准是既有 `tests/unit/test_phase0_acceptance.py` **一行不改**继续全绿,且 `bash scripts/checks.sh` 输出 `ALL CHECKS PASSED`。若任一不满足则回滚,退回复制方案并在文档记录原因。

> 审计间冲突记录:上一轮审计判"先提取共享函数不是必要前置"(故 V3.5 改为复制),本轮审计判"复制造成双份真相"。本文采纳后者,因为前者的立论基础("P0 可以零修改既有文件")已被本轮实测推翻。

### 7.7.1 工作树与 provenance 边界(与 Phase 0 的区别)

资产 coordinator **不要求 Git 工作树干净**:被验对象是候选资产,不是本仓库,`dirty_worktree`(§0.3)是 Phase 0 formal 证据的前置条件,不适用于本链路。coordinator 记录的 provenance 只有:自身代码版本(`acceptance/` 的文件哈希清单)、§7.4 工具锁定表实测值、`contract_digest`、输入资产 digest。这四项进入 `summary.json`,与仓库 Git 状态无关。若将来要求资产验收也具备仓库级 provenance(L2 场景),再引入与 Phase 0 相同的 clean-worktree 前置,并作为新 check ID 入注册表。

### 7.8 P0 完成定义

1. `blend_native` 与 `interchange/glb` 两分支实现,coordinator 严格实现 §2.6 十条;
2. §7.1 全部 check 有实现且被至少一次真实执行覆盖;
3. 至少一个生成器 known-good 全绿(含 32 张视觉证据齐备与自确定性通过);
4. §8 全部 L0 夹具以预期 failure code 被拒绝(父 harness 不改写 child 原始 Fail);
5. §8.4 的两个正向夹具(allowlisted warning 放行、N/A 集匹配)通过;
6. `bash scripts/checks.sh` 全绿(含 §7.7 定案的两处最小门禁修改后),`acceptance/` 实际被 ruff/mypy/Bandit 覆盖,且**未因本工作引入 Blender 硬依赖**(见 §8.5);
6b. `oiiotool` 与 `gltf_validator` 已安装并把实测版本/hash 填入 §7.4;`r0.contract.tools_locked` 通过;
6c. §8.3 的 family 覆盖矩阵机械断言通过(15/15);
6d. 摘要规范化与量化的 golden vectors 跨进程复算一致(§2.5.1、§4.2);
7. `ASSET_E2E=1` 真 Blender 路径在本机通过;
8. pilot candidate 报告产出并附人工审定结论(无论 Pass/Fail)。

### 7.9 P1 / P2(概要)

P1(L1):第二 normal child 与四级确定性;沙箱与资源限制(§1);BAT 5.2 fixture matrix;**空缓存** offline reopen(P0 的 reopen 是普通 offline 重开,不清缓存);USD/FBX/动画 Profile;`reproducible_by_script` 可选门;FLIP/VLM advisories;gltf-transform 交叉验证;每周 daily-build 金丝雀;共享库提取;`readOnlyHint` 等 MCP annotations(仅元数据,非安全边界;实施需同步更新 [test_server_process.py](tests/contract/test_server_process.py) 的目录投影断言)。
P2(L2):不同 OS principal、签名审批、DSSE/Sigstore、透明日志、Publisher receipt。

---

## 8. 回归夹具(规范)

### 8.1 义务边界

每个规范性决策分支、每个 fail-open 风险类别、每个 §7.2 failure-code family 至少一个夹具;动态底层错误映射到父级 family,不逐一建夹具。

### 8.2 夹具构造方式(三类,消除 V3.4 的归类错误)

- **synthetic**:纯合成 JSON/文件,coordinator 层,不需要 Blender;
- **generator**:`tests/asset_fixtures/generators/` 下的确定性 bpy 脚本产出 `.blend`;
- **handcrafted**:手工构造的二进制/报告(GLB 容器、validator report),提交入库并附构造脚本。

golden/expected 一律**由生成器或手工构造过程产出并经人工审阅后提交**,不由被测实现生成;禁止"跑一遍把输出存成新基线"。expected 只覆盖可人工判读的字段(计数、状态、failure code、preserved 字段的期望关系),**不手写量化摘要哈希**——摘要类断言以"两侧相等/不等"的关系式表达,不以字面值表达(解决"人手写不出量化哈希"的矛盾)。

### 8.3 夹具表

| Fixture | 等级 | 构造 | expected `failure_code` / 关键 check | 现状 |
|---|---|---|---|---|
| `exit_zero_success_false` | L0 | synthetic | `tool_output_invalid`(exit 0 但 `success!=true`) | wrapper 层已有([tests/unit/test_phase0_acceptance.py:55](tests/unit/test_phase0_acceptance.py#L55)) |
| `reused_evidence_root` | L0 | synthetic | `runner_internal_error`(启动子进程前拒绝) | wrapper 层已有(L78) |
| `stale_result_file` | L0 | synthetic | `stale_result_file` | 无 |
| `zero_checks_collected` | L0 | synthetic | `zero_checks_collected` | 无 |
| `report_truncated` | L0 | synthetic | `evidence_truncated` | 无 |
| `unknown_or_duplicate_check_id` | L0 | synthetic | `expected_set_mismatch` | 无 |
| `forged_not_applicable` | L0 | synthetic | `forged_not_applicable` | 无 |
| `isolation_grade_downgrade` | L0 | synthetic | `isolation_insufficient` | 无 |
| `contract_digest_drift` | L0 | synthetic | `contract_invalid`(R5 复算不符) | 无 |
| `contract_unknown_field` | L0 | synthetic | `contract_invalid`(顶层未知字段) | 无 |
| `projection_union_incomplete` | L0 | synthetic | `contract_invalid`(三数组并集 ≠ `p01`…`p13`) | 无 |
| `tool_version_mismatch` | L0 | synthetic | `toolchain_mismatch`(锁定表版本不符或工具缺失) | 无 |
| `tool_killed_by_signal` | L0 | synthetic | `tool_crashed`(信号终止、无报告) | 无 |
| `evidence_file_missing` | L0 | synthetic | `evidence_missing` | 无 |
| `evidence_hash_tampered` | L0 | synthetic | `hash_mismatch`(冻结后改动文件) | 无 |
| `coordinator_internal_error` | L0 | synthetic | `runner_internal_error` | 无 |
| `validator_error_nonzero_exit` | L0 | handcrafted | `check_failed` + `r3.validator.no_error`——**非 `tool_crashed`**;验证"validator 非零退出但报告完整 = 检查失败" | 无 |
| `validator_warning_passthrough` | L0 | handcrafted | `check_failed` + `r3.validator.no_error`(未 allowlist 的 warning,退出码 0 仍 Fail) | 无 |
| `validator_multi_message_mixed` | L0 | handcrafted | `check_failed`——一条 allowlisted + 一条未 allowlisted warning 共存,验证 `findings[]` 聚合规则 | 无 |
| `validator_report_truncated` | L0 | handcrafted | `evidence_truncated`(`issues.truncated=true` → `source_truncated` → `Truncated`) | 无 |
| `external_gltf_resource_missing` | L0 | handcrafted | `check_failed` + `r3.validator.resources_read`(GLB 中 image 用外部 `uri` 且文件缺失) | 无 |
| `forbidden_extension_present` | L0 | handcrafted | `check_failed` + `r3.extension.none_forbidden` | 无 |
| `hidden_extra_object` | L0 | generator | `check_failed` + `r2.inventory.coverage_complete`(按类型求和,排除 `all_ids`) | 无 |
| `same_counts_changed_vertices` | L0 | generator | `check_failed` + `r2.geometry.manifest_written`(structure 同、geometry 摘要异) | 无 |
| `missing_texture` | L0 | generator | `check_failed` + `r2.dependency.all_present` | 无 |
| `mesh_validate_dirty` | L0 | generator | `check_failed` + `r2.geometry.validate_clean`(copy 上返回 True,原数据 manifest 未污染) | 无 |
| `material_or_uv_lost_on_import` | L0 | generator | `check_failed` + `r4.projection.preserved_fields_match` | 无 |
| `texture_swapped_same_dimensions` | L0 | generator | `check_failed` + `r4.projection.preserved_fields_match`——**同尺寸同通道的不同贴图必须被抓到**(V3.5 只比尺寸会假绿) | 无 |
| `object_name_collision` | L0 | generator | `check_failed` + `r4.projection.ambiguous_object_names`——`Cube` 与 `Cube.001` 并存时禁止静默折叠 | 无 |
| `candidate_compositor_spoof` | L0 | generator | 通过(evaluator 全量覆盖渲染设置,诊断图不受影响) | 无 |
| `nondeterministic_render` | L0 | generator | `check_failed` + `r4.visual.self_determinism` | 无 |
| `axis_roundtrip_identity` | L0 | generator | **通过**——位置 `(1,2,3)` 的对象经 GLB 回环后 `p03_bbox` 必须相等;本夹具专防"再次换轴"回归(V3.5 缺陷) | 无 |
| `curve_only_asset` | L0 | generator | **通过**——纯曲线资产(depsgraph 中 MESH 计数为 0)必须正常验收,不得判空场景;这是 V3.5 mesh-only bounds 的确定性反例 | 无 |
| `mixed_curve_mesh_framing` | L0 | generator | **通过**——曲线远离网格时,包围盒须覆盖两者;断言曲线部分在渲染图中可见(旧规则会漏掉曲线并使其出画) | 无 |
| `oversized_bounds_framing` | L0 | generator | **通过**——细长/大跨度资产在 8 视角中完整入画;断言渲染图非空且前景像素未触边框(防 2.6r 型裁切回归) | 无 |
| `compressed_payload_supplement` | L1 | handcrafted | `check_failed`(合同声明 supplement 分支但缺目标运行时证据) | 无 |
| `fixed_view_billboards` | L1 | generator | `check_failed`(post-freeze holdout 暴露) | 无 |
| `nondeterministic_geometry` | L1 | generator | `check_failed`(两 child geometry 比较失败) | 无 |
| `parser_resource_bomb` | L1 | handcrafted | `resource_limit_exceeded` | 无 |

**family 覆盖矩阵(§8.1 义务的机械证明)**:15 个 family 全部有夹具——`contract_invalid`(3)、`toolchain_mismatch`(1)、`tool_crashed`(1)、`tool_output_invalid`(1)、`stale_result_file`(1)、`zero_checks_collected`(1)、`expected_set_mismatch`(1)、`forged_not_applicable`(1)、`evidence_missing`(1)、`evidence_truncated`(2)、`hash_mismatch`(1)、`isolation_insufficient`(1)、`resource_limit_exceeded`(1)、`runner_internal_error`(2)、`check_failed`(14)。测试套件须有一条机械断言:遍历夹具表的 expected 列,其 family 集合 == §7.2 全集,否则该断言失败。

L0 计 35 项(16 synthetic + 6 handcrafted + 13 generator),L1 计 4 项。其中 4 项(`axis_roundtrip_identity`、`curve_only_asset`、`mixed_curve_mesh_framing`、`oversized_bounds_framing`)是**正向回归夹具**,专防本轮修复的三处误拒缺陷复发——它们断言的是"必须通过",与其余"必须被拒"的夹具方向相反,缺一不可。

### 8.4 正向夹具(防"只测拒绝")

| Fixture | 预期 |
|---|---|
| `allowlisted_warning_accepted` | 四元组命中 allowlist 的 Warning → `effective=Pass`、`accepted=true`、`raw_status` 仍为 `Warning` |
| `na_set_exact_match` | `blend_native` 运行时,全部 interchange-only check 记 N/A 且与 R0 N/A 集双向相等 → 放行 |

### 8.5 fixture 产物与 CI 依赖(消除 checks.sh 硬依赖风险)

实测确认:`scripts/checks.sh` 默认路径不启动 Blender(仅 `RELEASE=1` 分支要求 `BLENDER_BIN`),`tests/` 下也无 Blender 可用性 gating(唯一 `skipif` 是 darwin 平台判断)。因此:

- generator 产出的 `.blend` 与 handcrafted 二进制**提交入库**至 `tests/asset_fixtures/artifacts/`,连同生成脚本与人工审阅记录;
- 默认 `pytest`(即 `checks.sh` 覆盖范围)只跑 synthetic 夹具与判定引擎单测,**不启动 Blender**;
- 真 Blender 路径(generator 再生成一致性、handcrafted 端到端)由独立开关 `ASSET_E2E=1` 触发,与 `RELEASE=1` 同款,不进默认门禁;
- 再生成一致性检查:`ASSET_E2E=1` 下重跑 generator,产物必须与入库 `.blend` 结构等价(不要求字节相等,Blender 写盘含时间戳/版本;比较 §4 manifest 的 structure 与 geometry 层)。

---

## 9. 事实锚定与外部证据

一律以 commit/advisory/release ID 为准;动态指标标 `observed_at=2026-08-24` 且不作架构依据。

- **e6d1620 更正**:该提交源码实测已使用 oiiotool、默认 `0.016/1%`、生成 RGB/Alpha diff。V3.3 曾称其为"idiff 时代提交"属错误推断,已撤回;V3.2 的原始引用一直准确。教训:二手调研不得改写对固定提交的事实声明。
- **ellmos 评价**:其 "one-shot"(每次调用一个全新 Blender 子进程)属实,不承诺全局互斥;以"无互斥"反驳属概念错位,已撤回。成立且经双实测的是假绿路径:固定结果文件名 + 未传 `--python-exit-code` 时脚本抛普通异常 Blender 仍 exit 0(本机实测:无 flag exit=0,`--python-exit-code 7` 时 exit=7),残留 JSON 会被当作本轮结果 → 夹具 `stale_result_file`。
- **glTF-Validator 盲区逐项处置**:

| 项 | 性质 | L0 | L1+ |
|---|---|---|---|
| Draco 压缩网格检查整体跳过(#235) | 假绿盲区 | **forbid** | 合同声明时 supplement:目标运行时实测解码 |
| KTX2/basisu 纹理载荷不验证(#177) | 假绿盲区 | **forbid** | 同上 |
| `KHR_animation_pointer` 验证不完整(#248) | 假绿盲区 | **forbid**(P0 只支持静态资产) | 动画 Profile 引入时 supplement |
| >4GB 误报(#244) | 误报非盲区 | 合同 `max_file_bytes`(默认 512 MiB)天然规避;记 known-issue | 同 L0 |

- 其余锚定事实:glTF-Validator 仅 severity=error 影响退出码、CLI 默认 `--validate-resources` 而库 API 默认关闭、npm 最后发布 `2.0.0-dev.3.10`(2024-10);OpenUSD GHSA-8878-wr6v-j5cm(§1);`mesh.validate()` 副作用(§4);MCP ToolAnnotations 均为 hint、不可作安全决策依据;glTF `image` 对象无宽高字段(§7.6 实测)。
- **仓库内先例**:Phase 0 wrapper 安全原语与三个 known-bad 回归;`verify_live` 的等序目录比较、单一只读探针、快照防 stale([verification.py:1035-](plugins/blender-mcp-installer/scripts/blender_mcp_installer/verification.py#L1035));`RELEASE=1` 的"精确重建 + 逐字节比对"。
- **上游对照**(observed_at=2026-08-24):ahujasid/blender-mcp 的 `execute_code` 为裸 `exec`,无沙箱与产物校验,RCE 类 issue 关闭不修,有两个 2026-06-03 公布的 low 级 CVE:[CVE-2026-10661](https://github.com/advisories/GHSA-qqw9-95ww-prfm)(`input_image_url` 注入)与 [CVE-2026-10662](https://github.com/advisories/GHSA-5hr7-6m56-f3rg)(`zip_file_url` SSRF)——二者位于全局 GitHub Advisory Database,该仓库自身 Security advisories 页未发布公告;[PatrykIti/blender-ai-mcp](https://github.com/PatrykIti/blender-ai-mcp) 以确定性测量为卖点,方向一致。
- **反例转化**:dcc-mcp 的 `passed=false` 仍 `skill_success`、pytest exit 5 当成功;blender-agent-studio 的 `hard_gate_pass=false` 但 exit 0、公开 CI 不启动 Blender → 夹具 `zero_checks_collected` 与双判定原则。
- **可借鉴**(P1):blender-agent-studio `verifyReproduction`;newo-ether 的"提交时重新验证"与指针泄漏审计;pyblish/AYON 有序插件范式(本方案增强:冻结 check 集+版本+序的哈希);Unreal DataValidation 的单 CLI 非零退出形态;glTF-Blender-IO 每周 daily-build 金丝雀。

---

## 10. 完成定义(四级)

- **本文完成**:自包含(单文档可恢复全部规范与参数)、判定唯一、注册表冻结;
- **P0/L0 完成**:§7.8 八条全部满足;
- **L1 完成**:两个 clean child、可证明隔离与资源限制(§1)、依赖闭包 + 空缓存 offline reopen、§8.3 的 4 项 L1 夹具通过;
- **L2 完成**:签名审批与 exact-digest Publisher 链实际 E2E 通过。

P0 代码与真 Blender fixture 落地前,唯一诚实结论仍是:

> 当前仓库的 MCP/Bridge 与分发链路验收已闭合;通用建模产物验收仍是设计,不得用于自动发布放行。

---

## 11. 立即行动清单

1. **解除正式验收阻塞**:处置 §0.3 全部 untracked 文件——方案文档归档进 `docs/acceptance/`(同步更新 `docs/README.md` 的"历史已移除"表述与 V3.1 的跟踪位置);`.blend`/PNG 作为 pilot candidate 移入 `tests/asset_fixtures/artifacts/` 或仓库外资产目录并在合同记录路径。
2. **V3.1 勘误**:若保留,页首补"D35~D43 所述 wrapper 实际入仓于 `bf63c89`"。
3. **P0 启动**:按 §7 依序落地,首个提交含 `primitives.py` 复制、`check_registry.py`/`failure_codes.py`/三个 schema、`decide.py` 与 synthetic 夹具,不触碰任何既有文件。

已剥离(与验收闭环无关或不宜先验承诺):docs/ 空目录清理(git 不跟踪空目录,列为可选卫生项);MCP `readOnlyHint` 标注(移入 §7.9 P1)。

---

## 12. 复审处置表(V3.4 → V3.5)

V3.4 经两路独立复审:**事实与处置闭合路判定通过**(21/21 实质闭合、五个 High 真闭合、全部仓库锚点与三项外部事实核实无误),另发现 1 Medium + 2 Low;**自包含与判定唯一性路**发现 5 High + 12 Medium + 4 Low。逐条处置如下。

| 复审发现 | 验证 | V3.5 处置 |
|---|---|---|
| 事实路 F-1:590 datablock 系 `all_ids` 重复计数,审计报告 295 正确 | 成立(实测 `SUM=590`、`len(all_ids)=295`、`SUM−all_ids=295`) | §4 转为 R2 实现约束(排除 `all_ids`);撤回对审计数字的质疑 |
| 事实路 F-2:M-04 的 FLIP 辩解不实 | 成立 | 本表取代 V3.4 §11 相应行;§5.4 明确 FLIP 为 P1 advisory |
| 事实路 F-3:L1 压缩 supplement 夹具丢失 | 成立 | §8.3 表内恢复 `compressed_payload_supplement` |
| H1:check ID/failure code/contract/result schema 只有文件名 | 成立(H-04 唯一未闭合部分) | §7.1 注册表 33 项、§7.2 family 14 项、§7.3 三份 schema 字段全部冻结入文 |
| H2:`required` 声明来源缺失、非 required 无归宿、软信号与公式冲突 | 成立 | §2.1 定案:required 由注册表声明、P0 无非 required、软信号改 `advisories[]` 不入公式;§2.6 条款 7 覆盖非 required 的 Crash/Missing/Truncated |
| H3:`blend_native` 的 offline reopen 在 P0/P1 自相矛盾 | 成立 | §2.2/§2.3 明确 P0 做普通 offline reopen(`reopen_probe.py`);§7.9 P1 只保留**空缓存**版本 |
| H4:投影规则/字段映射/容差缺失 | 成立 | §6 冻结 13 行 GLB 投影映射表(preserved/transformed/lost + 容差) |
| H5:相机/OCIO/引擎键缺失、首张视觉基线来源不存在 | 成立 | §5.1 冻结视角/构图/pass/渲染设置;§5.2 改为不依赖外部 golden 的三项判定(存在性、自确定性、source↔import);§5.3 定义 platform_key 格式与缺键即 Fail |
| M1:`success` 语义与子进程退出码约定未定义 | 成立 | §2.1 两条术语定案 |
| M2:N/A 条款恒真、伪造 N/A 无 code 无夹具 | 成立 | §2.5/§2.6 条款 6 改为双向包含 + `forged_not_applicable`;§8.3 加同名夹具 |
| M3:accessor count≠三角形数;glTF image 无宽高 | 成立(实测 Khronos `image.schema.json` 属性集无 width/height) | §7.6 更正为按 mode 换算三角形数;预算键改 `max_image_bytes`,不统计宽高 |
| M4:allowlist 放行分支与 N/A 分支无夹具 | 成立 | §8.4 新增两个正向夹具,并入 §7.8 完成定义第 5 条 |
| M5:三个夹具构造方式归错 | 成立(GLB 确为自包含容器,但规范允许非 BIN-chunk 资源用外部 URI,故该夹具改 handcrafted 而非取消) | §8.2 引入 synthetic/generator/handcrafted 三分类;§8.3 逐行标注 |
| M6:手写 expected 与量化摘要不相容 | 成立 | §8.2:expected 只覆盖可人工判读字段,摘要类断言用关系式表达 |
| M7:fixture .blend 提交还是运行时生成,关系 checks.sh 硬依赖 | 成立(实测默认路径无 Blender、无可用性 gating) | §8.5 定案:产物入库 + 默认 pytest 只跑 synthetic + `ASSET_E2E=1` 独立开关 + 再生成结构等价检查 |
| M8:包结构缺判定引擎与 R4/R5 落点 | 成立 | §7.5 补 `decide.py`/`evidence.py`/`pixel.py`/`projection.py`/`reopen_probe.py` |
| M9:`isolation_grade` 不参与判定、运行期降级与禁令冲突 | 成立 | §2.6 条款 2 纳入判定;§1 改为不满足即 Fail,不静默降级 |
| M10:`visual_unverified` 不在状态枚举内 | 成立 | §2.4 定性为 finding code,`raw_status` 恒 `NotTested` |
| M11:`tool_id`/`warning_code` 无来源 | 成立 | §2.5 四元组来源逐项定义;§7.1 增 `warning_codes` 列;§7.4 增 `id` 列 |
| M12:`Profile` 与"平台 blocklist"无定义 | 成立 | §2.3 Profile 封闭枚举(P0 仅 `static_render`);§5.3 定义 blocklist 为 platform_key 数组 |
| L1:L1 夹具溢出到散文 | 成立 | §8.3 单表承载全部夹具 |
| L2:clay 是不是第四个 pass | 成立 | §5.1 明确 4 pass,`render_views.py` 注释同步 |
| L3:validator 调用形态未冻结 | 成立 | §7.4 冻结完整参数向量与调用形态 |
| L4:§11 L-05 处置描述与正文不符 | 成立 | 本表以实际做法描述:删除绝对措辞 + 立锚定原则(§9) |
| 新问题:`glb_budget.py` 进程归属未绑定 | 成立 | §3 与 §7.6 明确在独立子进程运行,coordinator 不接触候选字节 |

### 12.2 V3.5 全量审计(第四轮)处置

V3.5 审计报告提出 9 High / 8 Medium / 2 Low,经逐条独立验证:**18 项成立、1 项部分成立(H-05 降为 Medium)**,并发现审计报告自身 1 处引用错误。全部处置如下。

| 发现 | 验证方式与结论 | V3.6 处置 |
|---|---|---|
| H-01 `contract_digest` 无规范化算法 | 成立(全文检索 `JCS\|RFC 8785\|canonical` **0 命中**;V3.1 原有 JCS,收敛时丢失) | 新增 §2.5.1:冻结 RFC 8785 JCS + 四条项目规则 + golden vectors |
| H-02 evidence file 闭集不可推导 | 成立(`result.json.stage` 仅 `r1`…`r4`,而注册表有 3 个 R0 + 3 个 R5 check,无产生方) | 新增 §7.1.1 file registry(18 类、模板展开);明确 R0/R5 记录由 coordinator 直写 summary;`output_truncated` 唯一映射到 `evidence_truncated` |
| H-03 failure family 无法表达正常拒收 | 成立(14 family 全为基础设施类;且 glTF-Validator error 非零退出会被误判 `tool_crashed`) | §7.2 引入 `check_failed` 类别 + `failed_check_ids[]` + 冻结优先级;明确"非零退出但报告完整 = 检查失败" |
| H-04 单 `warning_code` 丢消息 | 成立(validator 官方 schema 为 `issues.messages[]` 且带 `issues.truncated`) | §2.5 改为逐条 `findings[]` + 冻结聚合优先级;`source_truncated` → `Truncated` |
| H-05 schema 仍是字段草图、工具锁未冻结 | **部分成立,降 Medium**:实质缺陷成立(preset 未展开、`sha256` 可 null、无 hash 边界),但"版本值延后填死"是 V3.5 显式声明的延迟绑定,且上一轮审计明确判其合规——两轮标准不一致,不宜按 High 计 | §7.4 填入实测值(Blender 5.2.0/`fbe6228777e7`、Python 3.13.13、uv 0.12.2、validator 2.0.0-dev.3.10)、冻结 hash 边界与调用形态、展开 GLB preset;`sha256` 不再允许 null;并**如实记录 `oiiotool`/`gltf_validator` 本机未安装**,列为 P0 前置条件 |
| H-06 深层 manifest 无机器协议 | 成立 | 新增 §4.1 manifest 字段表(第四份 schema):稳定 ID 语法与转义、6 类记录字段、modifier 关键参数注册表、coverage 完整性算法;§4.2 补 banker's rounding、`-0`、golden vectors |
| H-07 投影含 1 实测错误 + 2 假绿 | 成立(**Blender 5.2 实测:`(1,2,3)` 导出 GLB 再导入仍为 `(1,2,3)`**,V3.5 的额外换轴会算成 `(1,-3,2)` 并误拒) | §6 删除换轴并说明两侧均为 Blender 空间;纹理改**按解码像素**比较(不再只比尺寸/通道);对象身份改用 `extras.bcx_uid`,退化为名称时必须先检测归一化碰撞;13 行改用稳定 `field_id`(`p01`…`p13`)使并集可机械校验 |
| H-08 视觉协议误视角/裁切/漏内容 | 成立(计算确认:hFOV 39.598° 下拟合需 **2.9523r**,V3.5 冻结 2.6r 必裁切) | §5.1 重定义 `offset` 为"目标→相机"并给全 8 行向量;透视距离改 `3.25r`(含 margin)、冻结 clip planes;bounds 扩至全部可渲染类型 + instance(curve/font-only 必须通过);新增冻结的 evaluator 三点光与中性灰 world(避免 beauty 全黑) |
| H-09 "零既有文件修改"与仓库事实冲突 | 成立(实测:ruff/mypy/Bandit/wheel 范围均无 `acceptance/`) | §7.7 **撤销该约束**;定案 repo-only 边界 + 两处最小门禁修改(`checks.sh` ruff/Bandit 路径、`pyproject.toml` mypy files);完成定义新增 6 条 |
| M-01 `accepted` 与 schema 不一致 | 成立 | summary `checks[]` 补 `accepted`、`tool_id`、`tool_version`、`findings[]`,审阅方可重算 allowlist |
| M-02 `non_triangle_primitive` 未声明 | 成立 | §7.1 注册表 `r3.budget.within_limits` 的 `warning_codes` 补入 |
| M-03 GPU 未初始化 + key 无归一化 | 成立(实测:未 `gpu.init()` 抛 `SystemError`;vendor 实际返回 `Apple M4`) | §5.3 要求先 `gpu.init()`,冻结归一化规则(`Apple M4` → `apple_m4`),探测失败即 Fail 不回退 |
| M-04 夹具未覆盖全部 family | 成立 | §8.3 重写:新增 `expected_failure_code` 列、补 10 个缺失 family 夹具、给出 15/15 覆盖矩阵与机械断言要求 |
| M-05 C2PA 论证不成立 | 成立(其反驳逻辑正确:合同要求存在时两种情况都应失败) | §1 改写:排除**结论**保留,**理由**改为成本/生态与格式覆盖,并撤回原逻辑 |
| M-06 复制原语造成双份真相 | 成立,且**与上一轮审计结论相反** | §7.7 采纳本轮:改复制为提取 + Phase 0 回 import,并给出回滚条件。理由:上一轮的立论前提("可零修改")已被 H-09 推翻 |
| M-07 L1 仍是选项列表 | 成立 | §1 新增"L1 实现边界(诚实声明)":冻结目标但未冻结 runner/profile/测量算法,L1 完成定义不可据本文实现 |
| M-08 合同权属与 policy 下限缺失 | 成立 | §1 新增合同权属条款:合同由 Verifier 侧持有、候选不得提供;引入独立 policy baseline 约束放宽类字段,L1/L2 缺 baseline 即 `contract_invalid` |
| L-01 外部证据违反自定锚定规则 | 成立 | §9 补 [CVE-2026-10661](https://github.com/advisories/GHSA-qqw9-95ww-prfm)、[CVE-2026-10662](https://github.com/advisories/GHSA-5hr7-6m56-f3rg) 与仓库链接 |
| L-02 `platform_key_unknown` 命名反向 | 成立 | 全文重命名为 `r4.visual.platform_key_known` |

**审计报告自身的错误(1 处)**:L-01 建议补引 `CVE-2026-10688`;实测解析 `GHSA-5hr7-6m56-f3rg` 得到的是 **`CVE-2026-10662`**。指控本身成立,但采纳时须用正确编号——本版已用后者。另澄清:这两条公告位于全局 GitHub Advisory Database,该仓库自身 Security advisories 页无已发布公告。

### 12.1 终审(V3.5 第三轮)处置

V3.5 经终审:**五个原始 High 全部真闭合**(依据为正文的具体表格/公式,非文字宣称);新发现 4 Medium + 3 Low,全部为局部机械性缺陷,已在本版就地修复:

| 终审发现 | 验证 | 处置 |
|---|---|---|
| M-a `skipped_by_contract`/`exit_code:null` 与 §7.3 冻结 schema 不一致(blend_native 每次运行必触发) | 成立 | §7.3 `stages` 字段改为 `exit_code: int\|null` + `skipped_by_contract: bool` |
| M-b 24 个哈希写入 `detail: str` 缺序列化格式 | 成立 | 终审运行期间已修:check 记录新增结构化 `metrics` 字段,格式定为 `{view_pass: [sha_first, sha_second]}` |
| M-c §7.7.1 承诺的"`acceptance/` 代码哈希清单"在 summary.json 无落点 | 成立 | §7.3 新增 `runner_provenance` 字段承载四项 provenance |
| M-d `r4.projection.undeclared_loss` 触发句缺否定词、语义自相矛盾 | 成立 | §6 改写为"未被 `projection.lost` 列出的字段若实际丢失才 Fail",并要求三数组并集恰好等于 13 行 |
| L-a §2.1 援引 §7.1 的 `required` 列,但表中无该列 | 成立 | §2.1 改为援引表上方统一声明,并注明 P1 引入非 required 时须补列 |
| L-b `phase0_structure_digest` 全仓零命中,实际字段名是 `scene_hash` | 成立(实测:`bridge/core/contracts.py:19`、`server/mcp/adapter.py:111` 均为 `scene_hash`;该建议名从未进入代码) | §4 改回事实陈述:本文不要求改名,只规定语义边界。此错误自 V3.4 起以陈述语气存在,两轮事实复审均未捕获 |
| L-c §2.2 的 R3 Fail 条件漏列"出现被禁扩展" | 成立 | §2.2 R3 行补入 |

终审同时确认两项**不成立**的疑虑,记录以免后续重复质疑:§2.7 第 5 条不存在"谁来算 N/A 集"的信任真空(推导源是 coordinator 自身注册表代码,合同只是被校验对象);§8.2 的"关系式表达"与 `same_counts_changed_vertices`、`material_or_uv_lost_on_import` 等 generator 夹具完全相容(其预期本就是关系断言,无需预写字面哈希)。

**流程教训**:L-b 连续两轮通过了"事实与处置闭合"复审才被第三轮发现——对**代码中并不存在的标识符**做陈述式命名声明,是审计容易漏过的一类错误;后续凡在方案中写"名称为 X"必须先 grep 确认 X 已存在于代码,否则一律用建议语气。

V3.4 的原 §11(对 V3.3 审计 21 项的处置)结论保持有效,已由事实路复审逐项核实闭合;本表只记录 V3.4 → V3.5 的增量。
