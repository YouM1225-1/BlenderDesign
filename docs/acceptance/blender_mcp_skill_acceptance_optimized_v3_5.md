# Blender MCP / Skill 建模产物验收方案 V3.5

## 可执行规范版:注册表冻结、判定边界闭合与 P0 参数定案

> 修订日期:2026-08-24(Asia/Shanghai)
> 仓库基线:`BlenderDesign` commit `bf63c89294a5f79649a2c550331ea8987cdeab1b`;当日实测 `bash scripts/checks.sh` → `ALL CHECKS PASSED`(362 passed;821 passed + 1 skipped)
> 前序:V3.3 及其审计(5H/11M/5L)→ V3.4(21/21 处置)→ V3.4 双路复审(事实与处置闭合:通过;自包含与判定唯一性:5H/12M/4L)→ **本文 V3.5**
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

### L2:生产发布或合规(`attested`)

在 L1 上增加:角色分离、签名 contract/approval、DSSE + Sigstore(可由 GitHub Artifact Attestations 承载——它是 **CI provenance carrier**,把产物 digest 链接到源码与构建过程,本身不是质量或安全保证;签发对象为发布产物与 evidence manifest,不是每次测试输出)、可信时间/透明日志、内容寻址晋级、Publisher receipt。

C2PA 不作为验收证据载体:其 external manifest 可绑定任意资产内容哈希,但 sidecar 缺失时无法区分"从未验收"与"凭证被剥离",不满足"缺失即失败"的闭包要求。仅 P2 对外发布渲染图环节可选。

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
disposition =
  AcceptedWarning  当且仅当 raw_status == Warning
                   且 (check_id, warning_code, tool_id, tool_version) ∈ R0 冻结 allowlist
  None             其他一切情况

effective_status =
  Pass           当 raw_status == Pass
  Pass           当 disposition == AcceptedWarning(同时记 accepted=true,raw 保留)
  NotApplicable  当 raw_status == NotApplicableByContract 且 check_id ∈ R0 的 N/A 集
  Fail           其他一切(含 Warning 无 disposition、NotTested、Crash、Truncated、Missing、
                 以及 NotApplicableByContract 但 ID 不在 N/A 集 → 另记 forged_not_applicable)
```

四元组分量来源:`check_id` 取自 §7.1 注册表;`tool_id` 取自 §7.4 工具锁定表的 `id` 列;`tool_version` 取自该表实测记录值;`warning_code` 对外部工具取其原生稳定码(glTF-Validator 的消息码),对自研检查取 §7.1 注册表 `warning_codes` 列声明的码——**未在注册表声明的自研 warning code 不可 allowlist**(fail-closed)。

### 2.6 放行公式(唯一)

```text
整体放行(coordinator exit 0)当且仅当以下全部成立:
 1. contract 加载成功,且 R5 复算的 contract digest == R0 记录值
 2. achieved_isolation_grade ⊒ contract.required_isolation_grade
 3. 每个 stage:actual check ID 集 == expected check ID 集(严格相等;先拒绝重复 ID、未知 ID)
 4. 每个 stage:actual file ID 集 == expected file ID 集
 5. 每个 required check 的 effective_status == Pass 或 NotApplicable
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

`blend_native` 的 N/A 集 = §7.1 中"适用 kind = interchange"的 11 项(其中 R3 的 7 项构成一个整段跳过的 stage,R4 的 4 项与该 stage 内其他 check 并存);`interchange` 的 N/A 集 = "适用 kind = blend_native"的 2 项(均在 R4)。注册表 33 项 = 20 all + 11 interchange + 2 blend_native。

---

## 3. 三个进程边界

- **Producer**(官方 MCP 26 工具链路,含任意 Python)只写自己的候选工作区;
- **Verifier coordinator** 只读输入、在私有全新 evidence root 编排子进程、独占写 evidence;不 import `bpy`;**不在自身进程内解析任何候选可控字节**(GLB 统计见 §7.6);
- **Reviewer/调用方** 只读冻结 evidence。

Blender 不是沙箱:`--disable-autoexec`、`--offline-mode`、`--factory-startup` 都不能替代 §1 的 OS 级隔离。官方链路 `localhost:9876` 无独立鉴权,威胁模型假定同机进程可达。L2 才拆分 Contract Authority、Attestor、Publisher。

---

## 4. Manifest(规范)

V1 覆盖:scene/view layer/collection/object/instance 的稳定路径与可见性;object transform、parent、类型、data identity;Mesh 几何量化摘要;modifier 名称/类型/关键参数与 evaluated mesh 摘要;material slot、节点/链接摘要、纹理相对路径与 byte hash;armature/action/FCurve 的 applicable 摘要;unit、frame range、render/export preset;外部依赖相对路径/大小/hash/packed 状态;`schema_version`、`coverage`、`unsupported_fields`。

**量化规则(冻结)**:坐标/法线用 float64 → 四舍五入到 1e-6 后按 `<` little-endian 打包 float64;UV 同规则;索引用 uint32;每个数组按 8192 元素分块,逐块 SHA-256,再对块摘要序列取 SHA-256 得数组摘要。摘要域名前缀 `bcx.manifest.v1.<field>`。

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

| 视角 | 类型 | 方向(相机朝向目标) | 备注 |
|---|---|---|---|
| front / back / left / right / top | ORTHO | -Y / +Y / +X / -X / -Z | 沿轴,up 轴取 +Z(top 取 +Y) |
| persp | PERSP | 从 (+1,-1,+0.8) 归一化方向 | 焦距 50 mm |
| obliqueA / obliqueB | PERSP | (+1,-1,+0.6) / (-1,-1,+0.35) 归一化 | 焦距 50 mm |

**构图规则(冻结)**:取 evaluated 场景所有可见 mesh 的世界包围盒,记中心 `C`、包围球半径 `r`。正交:`ortho_scale = 2.2r`,相机置于 `C + dir·(4r)`;透视:相机置于 `C + dir·(2.6r)`,水平 FOV 由 50 mm/36 mm 传感器确定。所有相机 `look_at = C`。`r == 0`(空场景)→ `r4.visual.scene_not_empty` Fail。

**pass(冻结,每视角 4 张)**:`beauty`(EEVEE)、`clay`(Workbench,solid、单一 0.8 灰、studio 光照、无纹理)、`silhouette`(Workbench,flat、单色 shadeless、黑底白物)、`wire`(Workbench,wireframe)。共 8×4 = 32 张。P0 硬判定只用 `clay`、`silhouette`、`wire`(Workbench,确定性好);`beauty` 生成并落盘作为证据,但不参与像素回归硬门,除非合同显式声明参考平台键(见 §5.3)。

**渲染设置(冻结)**:分辨率 1024×1024、100%;色彩管理 view transform = `Standard`、look = `None`、exposure 0、gamma 1;输出 PNG RGBA 8-bit;世界纯黑、strength 0;`clay`/`silhouette`/`wire` 使用 Workbench 引擎且关闭 AA 抖动(固定采样数 8);`beauty` 使用 EEVEE 固定采样数 64。全部由 evaluator 脚本设置,**不读取候选文件的任何 scene render/world/compositor 设置**(这是抗 compositor 欺骗的机制)。

### 5.2 P0 的视觉判定(不依赖外部 golden)

P0 不要求预先存在的 golden 图像。判定项为:

1. `r4.visual.all_views_rendered`:32 张全部存在、非零字节、可被 oiiotool 读取(否则 `Missing`);
2. `r4.visual.self_determinism`:同一 run 内对 `clay`/`silhouette`/`wire` 共 24 张各重渲一次(第二组渲染到 `views2/` 子目录),与首次结果按 `oiiotool --fail 0 --failpercent 0 --diff` 逐张比较,**任一张不一致即该 check Fail**(单条 check 聚合 24 张结果)。第二组图像**不进入 evidence file ID 集**(条款 4 只覆盖 `views/` 的 32 张 + 差异图),但其 24 个 SHA-256 以 `{view_pass: [sha_first, sha_second]}` 形式写入该 check 的 `metrics` 字段(§7.3;`detail` 只放单行原因),使判定可复核而不使 file 集随渲染次数漂移;
3. `interchange` 追加 `r4.visual.source_import_match`:source 与 import 的同视角 `clay`/`silhouette` 按 `--fail 0.016 --failpercent 1` 比较(阈值来源见 §5.3),超阈值 Fail,并保存 RGB/Alpha diff。

`blend_native` 因只有一组图,不做跨对象像素回归;其视觉证据由 1、2 加人工审阅记录(§8.3)承载。**这消除了"首张基线从哪来"的循环**:P0 的机器判定不需要基线;需要基线的比较只在 `interchange`(两侧同 run 生成)与 §8 fixture(基线由生成器产出,见 §8.2)中出现。

### 5.3 阈值与平台键

`--fail 0.016 --failpercent 1` 是 **Blender 官方渲染回归的工程起点**(实测 [render_report.py @ e6d1620](https://github.com/blender/blender/blob/e6d1620ad53feed4a83e3b168f0a2ea74f4de6ce/tests/python/modules/render_report.py) 与当前 main 均如此),**不是资产质量依据**。每份合同必须显式声明自己的 `visual_thresholds`,只能收紧,或按平台键放宽。

平台键格式(冻结):`<os>-<arch>-<engine>-<gpu_backend>-<gpu_vendor>`,例如 `macos-arm64-workbench-metal-apple`。coordinator 从 Blender 子进程回读 `bpy.app.build_platform`、`gpu.platform.backend_type_get()`、`gpu.platform.vendor_get()` 填充,并写入 `summary.json.platform_key`;合同 `visual_thresholds` 是 `platform_key → {fail, failpercent}` 的映射,缺键 → `r4.visual.platform_key_unknown` Fail(不静默用默认值)。`blocklist` 是同格式键的数组,列出**明确不支持验收的平台**,命中即 Fail。

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

| manifest 字段 | 分类 | 变换/容差 |
|---|---|---|
| 可见 mesh object 数量 | preserved | 精确相等 |
| 每 object 的三角形数 | preserved | 精确相等(source 侧取 evaluated 三角化后计数) |
| 顶点位置包围盒 | transformed | Blender +Z-up ↔ glTF +Y-up:比较前对 import 侧应用 `(x, -z, y)`;容差 1e-4 相对包围球半径 |
| 顶点数 | transformed | 导出会因 UV/法线接缝拆点而增加,允许 `import ≥ source`,比值上限由合同 `vertex_split_ratio_max`(默认 3.0)约束 |
| UV 层数量与每层存在性 | preserved | 精确相等(名称可变,顺序保持) |
| material slot 数量 | preserved | 精确相等 |
| 每 material 的 base color factor / metallic / roughness | transformed | Principled BSDF → pbrMetallicRoughness 映射;容差 1e-3 |
| 纹理图像的字节 hash | preserved | GLB 内嵌后按解码前字节比较;PNG 重编码时改比图像尺寸与通道数 |
| object 名称 | transformed | glTF 名称唯一化会加后缀;比较用规范化名(去 `.001` 式后缀) |
| collection 层级 | lost | glTF 摊平为 node 树;合同默认声明 lost |
| modifier 栈 | lost | 导出即烘焙;合同默认声明 lost |
| 自定义属性、驱动、约束 | lost | 合同默认声明 lost |
| 单位系统 | transformed | glTF 固定米;source 非米制时按比例换算后比较 |

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
| `r3.budget.within_limits` | R3 | 70 | 1 | interchange | `budget_near_limit` |
| `r4.reopen.offline_ok` | R4 | 10 | 1 | blend_native | — |
| `r4.reopen.dependencies_resolved` | R4 | 20 | 1 | blend_native | — |
| `r4.import.manifest_written` | R4 | 30 | 1 | interchange | — |
| `r4.projection.preserved_fields_match` | R4 | 40 | 1 | interchange | — |
| `r4.projection.undeclared_loss` | R4 | 50 | 1 | interchange | — |
| `r4.visual.scene_not_empty` | R4 | 60 | 1 | all | — |
| `r4.visual.all_views_rendered` | R4 | 70 | 1 | all | — |
| `r4.visual.self_determinism` | R4 | 80 | 1 | all | — |
| `r4.visual.platform_key_unknown` | R4 | 90 | 1 | all | — |
| `r4.visual.source_import_match` | R4 | 100 | 1 | interchange | — |
| `r5.evidence.manifest_closed` | R5 | 10 | 1 | all | — |
| `r5.evidence.hashes_match` | R5 | 20 | 1 | all | — |
| `r5.contract.digest_stable` | R5 | 30 | 1 | all | — |

不适用当前 kind 的 check 由 R0 写入 N/A 集,按 §2.6 条款 6 校验。`blend_native` 的 N/A 集 = 全部 `interchange`-only ID;反之亦然。

### 7.2 Failure-code family(冻结封闭集;`failure_codes.py` 的内容即本表)

底层 OS/第三方动态错误一律映射到下列父级 code,原始细节存 `detail` 字段;**不为无界底层错误码逐一建夹具**。

| family | 触发 |
|---|---|
| `contract_invalid` | schema 未知字段、缺字段、类型错、digest 不稳 |
| `toolchain_mismatch` | 工具版本/hash 与锁定表不符 |
| `tool_crashed` | 子进程或外部工具非零退出、信号终止 |
| `tool_output_invalid` | 产物非法 JSON、schema 不符、重复 key、NaN/Inf、超限 |
| `stale_result_file` | 结果文件启动前已存在 |
| `zero_checks_collected` | expected 非空而 actual 为空 |
| `expected_set_mismatch` | check/file ID 集不等、重复或未知 ID |
| `forged_not_applicable` | N/A 状态的 ID 不在 R0 N/A 集 |
| `evidence_missing` | required 证据文件缺失或零字节 |
| `evidence_truncated` | 证据达大小上限 |
| `hash_mismatch` | 文件 hash 与 manifest 不一致 |
| `isolation_insufficient` | achieved < required isolation grade |
| `resource_limit_exceeded` | rlimit 触发(L1) |
| `runner_internal_error` | coordinator 自身未预期异常 |

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
checks: [{id: str, raw_status: str, warning_code: str|null,
          tool_id: str|null, tool_version: str|null,
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
checks: [{id, stage, raw_status, warning_code, disposition, effective_status, detail, metrics}]
evidence_manifest: [{id, path, bytes, sha256}]
advisories: [...]
failure_code: str|null                 # success=false 时必填,取自 §7.2
error: str|null
runner_provenance: {acceptance_files: [{path: str, sha256: str}],
                    tools: [{id: str, version: str}],
                    input_digest: str}   # §7.7.1 承诺的四项 provenance 的落点
```

### 7.4 外部工具锁定表(结构冻结;版本值在 P0 首次实施时填死并入 contract digest)

| id | 工具 | 用途 | 锁定方式 |
|---|---|---|---|
| `blender` | Blender | R2/R3/R4 子进程 | 绝对路径 + `--version` 实测值(现状 5.2.x LTS) |
| `gltf_validator` | Khronos glTF-Validator | R3 合规层 | 版本 + SHA-256;基线 `2.0.0-dev.3.10`(npm 最后发布);**调用形态一并冻结**:CLI 模式、显式 `--validate-resources`、`-o` 输出 JSON、`--config <file>`,config 文件本身入 digest(CLI 默认开启资源验证而库 API 默认关闭,故形态必须显式) |
| `oiiotool` | OpenImageIO | R4 像素回归 | 安装来源 + `--version` 实测值 |
| `python` / `uv` | coordinator | 全程 | 精确 3.13.13、`uv run --frozen` |
| `flip` / `gltf_transform` / `bat` | — | P1 起 | 进入本表后方可使用 |

工具输出解析失败或版本不符 → `tool_output_invalid` / `toolchain_mismatch`。

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
- `extensions_used`/`extensions_required` 全集,用于 §6.1 的 forbid 判定;
- 不解码任何二进制载荷。

### 7.7 与既有代码的关系(P0 不修改任何既有文件)

`primitives.py` **复制**(非迁移)`run_phase0_acceptance.py` 的最小原语:root 规范化与私有目录、环境清洗、严格 JSON 三件套、`_file_evidence`、`_write_json_exclusive`、进程组运行/终止、`AcceptanceFailure`(实测对应函数体约 135 行,含导入与空行约 150 行),逐函数注明来源与"与源同步检查"义务。理由:`tests/unit/test_phase0_acceptance.py:8` 已证明 `from scripts import …` 可行,但生产代码依赖另一脚本的私有函数会把 Phase 0 私有实现固化为公共 API;两条链路生命周期不同步。共享库提取推迟到 P1,届时一次性提取并让双方回 import,以 `checks.sh` 全绿收口。

### 7.7.1 工作树与 provenance 边界(与 Phase 0 的区别)

资产 coordinator **不要求 Git 工作树干净**:被验对象是候选资产,不是本仓库,`dirty_worktree`(§0.3)是 Phase 0 formal 证据的前置条件,不适用于本链路。coordinator 记录的 provenance 只有:自身代码版本(`acceptance/` 的文件哈希清单)、§7.4 工具锁定表实测值、`contract_digest`、输入资产 digest。这四项进入 `summary.json`,与仓库 Git 状态无关。若将来要求资产验收也具备仓库级 provenance(L2 场景),再引入与 Phase 0 相同的 clean-worktree 前置,并作为新 check ID 入注册表。

### 7.8 P0 完成定义

1. `blend_native` 与 `interchange/glb` 两分支实现,coordinator 严格实现 §2.6 十条;
2. §7.1 全部 check 有实现且被至少一次真实执行覆盖;
3. 至少一个生成器 known-good 全绿(含 32 张视觉证据齐备与自确定性通过);
4. §8 全部 L0 夹具以预期 failure code 被拒绝(父 harness 不改写 child 原始 Fail);
5. §8.4 的两个正向夹具(allowlisted warning 放行、N/A 集匹配)通过;
6. `bash scripts/checks.sh` 全绿,且**未因本工作引入 Blender 硬依赖**(见 §8.5);
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

| Fixture | 等级 | 构造 | 预期 | 现状 |
|---|---|---|---|---|
| `exit_zero_success_false` | L0 | synthetic | 子进程 exit 0 但 `success!=true` → Fail | wrapper 层已有([tests/unit/test_phase0_acceptance.py:55](tests/unit/test_phase0_acceptance.py#L55)) |
| `reused_evidence_root` | L0 | synthetic | 启动子进程前拒绝 | wrapper 层已有(L78) |
| `stale_result_file` | L0 | synthetic | 结果文件预先存在 → 拒绝,不读旧 JSON | 无 |
| `zero_checks_collected` | L0 | synthetic | expected 非空、actual 为空 → Fail | 无 |
| `report_truncated_or_unknown_id` | L0 | synthetic | 集合不等/超限 → `expected_set_mismatch`/`evidence_truncated` | 无 |
| `forged_not_applicable` | L0 | synthetic | child 报 N/A 但 ID 不在 R0 N/A 集 → Fail | 无 |
| `isolation_grade_downgrade` | L0 | synthetic | 合同要 `isolated`、实际 `local-trusted` → Fail | 无 |
| `contract_digest_drift` | L0 | synthetic | R5 复算 digest 与 R0 不符 → Fail | 无 |
| `validator_warning_passthrough` | L0 | handcrafted | validator report 含未 allowlist 的 warning 而退出码 0 → 仍 Fail | 无 |
| `external_gltf_resource_missing` | L0 | handcrafted | GLB 中 image 以外部 `uri` 引用且文件缺失 → validator 资源验证失败(GLB 允许非 BIN-chunk 资源用外部 URI) | 无 |
| `forbidden_extension_present` | L0 | handcrafted | GLB 声明 `KHR_draco_mesh_compression`/`KHR_texture_basisu`/`KHR_animation_pointer` → 拒收 | 无 |
| `hidden_extra_object` | L0 | generator | inventory/coverage 捕获(计数按类型求和,排除 `all_ids`) | 无 |
| `same_counts_changed_vertices` | L0 | generator | structure 同、geometry 摘要异 | 无 |
| `missing_texture` | L0 | generator | 依赖检查失败 | 无 |
| `mesh_validate_dirty` | L0 | generator | copy 上 `validate()` 返回 True → `r2.geometry.validate_clean` Fail,原数据 manifest 未污染 | 无 |
| `material_or_uv_lost_on_import` | L0 | generator | §6 preserved 字段不匹配 → Fail | 无 |
| `candidate_compositor_spoof` | L0 | generator | 候选设置 compositor/world;evaluator 全量覆盖渲染设置,诊断图不受影响 | 无 |
| `nondeterministic_render` | L0 | generator | 自确定性重渲不一致 → Fail | 无 |
| `compressed_payload_supplement` | L1 | handcrafted | 合同声明 supplement 分支但缺目标运行时证据 → Fail | 无 |
| `fixed_view_billboards` | L1 | generator | post-freeze holdout 暴露 | 无 |
| `nondeterministic_geometry` | L1 | generator | 两 child geometry 比较失败 | 无 |
| `parser_resource_bomb` | L1 | handcrafted | 资源限制终止 child,记 `resource_limit_exceeded`(GHSA-8878 型) | 无 |

L0 计 18 项:8 synthetic + 3 handcrafted + 7 generator。L1 计 4 项。

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
- **上游对照**(observed_at=2026-08-24):ahujasid/blender-mcp 的 `execute_code` 为裸 `exec`,无沙箱与产物校验,RCE 类 issue 关闭不修,有两个 2026 CVE;PatrykIti/blender-ai-mcp 以确定性测量为卖点,方向一致。
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
