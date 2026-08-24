# Blender MCP / Skill 建模产物验收方案 V3.4

## 自包含规范版:审计修复、判定闭合与 P0 实施合同

> 修订日期:2026-08-24(Asia/Shanghai)
> 仓库基线:`BlenderDesign` commit `bf63c89294a5f79649a2c550331ea8987cdeab1b`;当日实测 `bash scripts/checks.sh` → `ALL CHECKS PASSED`(362 passed;821 passed + 1 skipped)
> 输入材料:V3.3(SHA-256 `95bd01d104b4d1b4d53dd8b698f9f12e41f09930d01f57c624d5f2a7908ba912`)及其全量审计报告(5 High / 11 Medium / 5 Low);审计发现经独立验证后逐条处置,处置表见 §11
> 文档性质:**本文是自包含规范**——实现者只依据本文即可恢复全部门禁、状态语义、判定公式与 P0 完成定义,无需阅读 V3.1/V3.2/V3.3(它们降级为历史演进记录)。本文同时仍是设计:通用建模产物验收在本仓库尚未实现,不得用于自动发布放行

---

## 0. 结论

### 0.1 方案定位

把"AI 经 MCP 在 Blender 中产出的建模产物是否正确、可导出、可复现"的验收,收敛为六个条件门与三个进程边界,按三级风险选择启用范围:

```text
R0 合同冻结 → R1 输入冻结 → R2 clean Blender 检查 → R3 条件导出/独立验证
           → R4 fresh-import/视觉证据 → R5 fail-closed 汇总
```

```text
Producer(可写候选)
Verifier coordinator(只读输入、编排子进程、写 evidence)
Reviewer/调用方(读取冻结 evidence 后作最终决定)
```

多 OS principal、DSSE/Sigstore、透明日志、独立 Publisher、多目标引擎不是默认项,只在 L2 启用(§3)。

### 0.2 当前可声明范围(2026-08-24 实测)

| 能力 | 状态 | 结论 |
|---|---|---|
| 仓库常规门禁 | implemented-and-enforced | 当日实测 `ALL CHECKS PASSED`:362 unit/contract;821 distribution + 1 条件跳过 |
| `RELEASE=1` 发行门禁 | implemented-and-enforced(源码与既有测试结构核实;本轮未重放全链路) | 上游 `ls-remote` 精确一致、补丁重放、MCP SDK 1.28.1/2.0.0 双重放、Bandit/detect-secrets/pip-audit、双确定性构建逐字节 `cmp` |
| Phase 0 正式 wrapper | implemented-and-enforced | 只验证只读 Bridge 的真 Blender GUI/NFR/recovery;三个 known-bad 已有 unit 回归 |
| 官方 Blender MCP 固定分发 | implemented-and-enforced | 上游 `projects.blender.org/lab/blender_mcp` @ `4309a39646e6…`,10 个下游 patch,26 项工具目录 |
| 深层资产 manifest | absent | `scene_hash` 仅结构摘要(§6.1) |
| 导出格式独立验证 / fresh-import | absent | 无通用 glTF/USD/FBX 资产门禁 |
| evaluator-owned 视觉验收 | absent | 渲染工具 ≠ 独立视觉判定 |
| 多次 clean-run 产物比较 | absent | Phase 0 NFR/recovery 不是资产确定性验证 |
| 签名审批 / attestation / 发布系统 | absent | 仅 L2 增强项 |

### 0.3 正式验收当前被工作树状态阻塞

`_require_clean_worktree`([run_phase0_acceptance.py:87](scripts/run_phase0_acceptance.py#L87))把 untracked 文件也算脏。当前工作树的全部未跟踪文件——V3.2、V3.3、V3.3 审计报告、本文 V3.4、`hantavirus_scientific_cutaway.blend`、`hantavirus_scientific_cutaway_v2.blend`、`hantavirus_scientific_cutaway_final.png`——任何一个存在都会使正式 Phase 0 验收以 `dirty_worktree` 失败。处置见 §10。

---

## 1. 风险分级(规范)

风险等级只能在运行前由外部 policy 选择;Producer 不能自行降级。报告必须记录实际达到的 `isolation_grade`。

### L0:可信本地建模

适用:个人项目、输入由当前操作者生成、不自动发布。

必需:R0~R5 全部;R1 只记录 exact bytes,不要求不同 principal 的只读 staging;允许同一 UID;不要求签名或第二个 clean-run。报告必须写 `isolation_grade=local-trusted`。

### L1:CI 或第三方资产

适用:下载资产、自动化构建、团队共享输入。在 L0 上增加:

1. **进程隔离——可证明基线**(按平台声明,不得混淆):
   - Linux CI:nsjail/bwrap + seccomp 白名单,新 namespace、默认断网、只读输入挂载、专属输出;
   - macOS:**独立 OS 用户**(不同 uid;输入对该用户只读、输出目录专属)或 VM/受控远程 runner。`sandbox-exec` 已被 Apple 标记 DEPRECATED 且 SBPL 无受支持文档(本机 `man sandbox-exec` 实证),**不得计入受支持安全边界**;如仍附加使用,只能标注 `best-effort defense-in-depth`,并以黑盒夹具(拒网络、拒路径逃逸)验证其仍然生效,失效时不改变 L1 判定。macOS 本机无法建立独立用户/VM 时,L1 声明该平台不支持,降级 L0 并如实标记 `isolation_grade`;
   - OS 级强制断网:Linux namespace 可证明;macOS 本机只能达到应用层(`--offline-mode` + 代理环境变量清洗),不得声明为 OS 级断网。
2. **资源限制**(所有平台可证明):coordinator 以 POSIX rlimit 设置子进程 CPU 时间、地址空间/数据段、打开文件数、`RLIMIT_FSIZE`;超限终止即 Fail,不重试。
3. **不可信字节接触次序**:该原则仅适用于自研解析工具("先打开全部输入/输出 fd,再接触不可信字节");Blender、格式 validator 等按路径递归加载的第三方工具无法预打开全部 fd,对它们的等价手段是只读输入挂载/目录白名单 + 上述资源限制。
4. **内嵌媒体解码与几何解析同级隔离**(SketchUp 事件中 117 个漏洞有 97 个来自内嵌图像解码路径)。
5. 两个独立 clean child 与四级确定性比较(§5.4)、依赖闭包 + 空缓存 offline reopen、known-bad fixtures 全套。
6. **解析器版本钉死属于合同**:USD 侧 OpenUSD ≥26.08 且 `PXR_PREFER_SAFETY_OVER_SPEED` 构建(GHSA-8878-wr6v-j5cm:恶意 `.usdc` 打开不报错、读值才触发超大分配;官方口径是无安全构建不得在缺少沙箱/资源限制时处理不可信 crate 文件);blender-asset-tracer 用官方 `projects.blender.org/blender/blender-asset-tracer` 1.x 线 ≥v1.23,且其 changelog 只明确覆盖到 Blender 5.0 文件特性——**对 Blender 5.2 的依赖类型(linked libraries、UDIM、GN simulation cache、Alembic/USD cache、字体、音频)先建 fixture matrix 验证覆盖,验证前 L1 依赖闭包以可信 Blender 进程内枚举为主、BAT 为交叉验证**。

### L2:生产发布或合规

适用:多人审批、外部客户、不可抵赖发布。在 L1 上增加:角色分离、签名 contract/approval、DSSE + Sigstore 证据链(可由 GitHub Artifact Attestations 承载——它是 **CI provenance carrier**,把产物 digest 链接到源码与构建过程,本身不是质量或安全保证;签发对象应为发布产物与 evidence manifest,不是每次测试输出)、可信时间/透明日志、内容寻址晋级、Publisher receipt。

C2PA 不作为验收证据载体:其 external manifest(sidecar)机制确实可绑定任意资产的内容哈希,但 sidecar 缺失时验证方无法区分"从未验收"与"凭证被剥离",不满足验收证据"缺失即失败"的闭包要求;其生态工具链面向媒体发布场景。仅在 P2 对外发布渲染图环节可选。

---

## 2. 六个条件门(规范)

### 2.1 门禁表

| Gate | Required 动作 | Required 证据 | Fail 条件 |
|---|---|---|---|
| R0 Contract | 冻结 `artifact_kind`、Profile、export set、required check ID 集 + **各 check 实现版本 + 执行序**、阈值(含视觉阈值键与平台 blocklist)、validator severity 覆盖配置、工具锁定表、资源上限、N/A 集合、golden 基线引用 | `contract.json` 及其 digest | 未知字段/ID、隐式 N/A、运行后改阈值、工具版本未锁定 |
| R1 Freeze | L1/L2 将候选复制到新私有只读 staging;所有等级记录输入与依赖的大小和 SHA-256 | 输入/依赖清单 | 旧 root、链接/设备文件、路径逃逸、资源超限、读取竞态 |
| R2 Inspect | clean Blender(`--background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1`)运行 trusted inspector;枚举全部 scene/collection/object/datablock 与 authored/evaluated 摘要;依赖清单 | source manifest、dependency report | 缺对象、NaN/Inf、依赖缺失、coverage 不完整、候选代码执行 |
| R3 Produce/Validate | 仅对适用 kind 在新进程以固定 preset 导出/渲染;先做"交付文件存在且 size>0" smoke;再运行独立格式 validator(解析其 JSON report 判定,退出码只是辅助信号)与预算统计 | deliverable、producer log、format report、budget report | source 前后 rehash 改变、输出空、validator error、report 截断、外部资源未读、预算超限 |
| R4 Reopen/Evidence | 第二个 clean 进程 fresh-import/离线重开;按合同投影比较 source↔import;生成 evaluator-owned 视觉证据(§5) | imported manifest、projection diff、图像与渲染设置清单 | 只证明"能打开"、字段超容差、缺图、candidate compositor 欺骗 |
| R5 Decide | 按 §2.4 判定公式汇总;比较 expected/actual check 与 file ID 集;校验 exit、schema、`success`、hash;L1 比较两个 child | `summary.json`、evidence manifest | Missing/Crash/Truncated/NotTested、假绿、重复/未知 ID、hash 漂移、`stale_result_file`、`zero_checks_collected` |

补充规则:

- **结果文件生命周期**:每个子进程的结果文件路径在启动前必须不存在(`O_EXCL` 语义);启动前已存在 → `stale_result_file` Fail;子进程失败且未产出 → 该证据记 `Missing`,永不读取任何先前存在的同名文件。
- **零收集即失败**:任一 stage 的 expected check 集非空而实际为空 → Fail(不允许"没有检查跑过=通过")。
- **正式证据日志**:全量落盘,单文件上限(默认 32 MiB,与现有 wrapper 一致);达到上限即记 `Truncated` 并使该 required 证据 Fail。"保尾弃头"只允许用于面向 LLM/UI 的响应通道,且必须带显式 `output_truncated` 标志与原始字节数;二者是不同通道,不得混用。

### 2.2 Artifact Kind 条件

| Kind | R3 | R4 |
|---|---|---|
| `blend_native` | 不要求 interchange export | clean offline reopen + source 视觉 |
| `interchange` | export + 独立格式 validator + 预算统计 | fresh-import 投影 diff + source/import 视觉 |
| `runtime_asset` | 同 interchange | 再加合同声明的 target consumer |
| `rendered_media` | render + 独立媒体解码 | 帧、色彩、编码、音轨与视觉回归;不跑 3D import |
| `fabrication` | export + 几何/单位/水密/壁厚 validator | 声明切片器时才运行 target consumer |

未适用分支必须由 R0 生成 `NotApplicableByContract` 记录,不能靠省略表达。

### 2.3 状态语义

每个检查的 `raw_status` 只能是:

```text
Pass | Fail | Warning | NotTested | NotApplicableByContract | Crash | Truncated | Missing
```

`raw_status` 一经写入不可改写。`NotApplicableByContract` 只能来自 R0 合同,不是运行时状态。waiver 不进入默认方案;L2 如需走独立 conditional release,永不冒充 Production Pass。

### 2.4 判定公式(唯一)

```text
对每个 check:
  disposition =
    AcceptedWarning  当且仅当 raw_status == Warning
                     且 (check_id, warning_code, tool_id, tool_version) ∈ R0 冻结 allowlist
    None             其他一切情况

  effective_status =
    Pass           当 raw_status == Pass
    Pass           当 disposition == AcceptedWarning(记录 accepted=true,raw 保留)
    NotApplicable  当 raw_status == NotApplicableByContract
    Fail           其他一切(含 Warning 无 disposition、NotTested、Crash、Truncated、Missing)

整体放行(exit 0)当且仅当:
  每个 stage 的 actual check ID 集 == expected check ID 集(严格相等,拒绝重复/未知 ID)
  且 每个 stage 的 actual file ID 集 == expected file ID 集
  且 所有 required check 的 effective_status == Pass
  且 NotApplicable 的集合 == R0 合同声明的 N/A 集合(逐一对应)
  且 所有 required 文件 hash 与 evidence manifest 一致
  且 所有子进程 exit == 0 且其结构化产物 schema 合法、success == true
```

allowlist 本身进入 contract digest;任何降级/升级都要求新 contract digest 并从 R0 重跑。同一份 validator report 在本公式下只有一种结论。

---

## 3. 三个进程边界与信任模型

- **Producer**(官方 Blender MCP 26 工具链路,含任意 Python)只能写自己的候选工作区;
- **Verifier coordinator** 只读输入、在私有全新 evidence root 编排子进程、独占写 evidence;不 import `bpy`;
- **Reviewer/调用方** 只读冻结 evidence。

Blender 不是沙箱:`--disable-autoexec`、`--offline-mode`、`--factory-startup` 都不能替代 §1 的 OS 级隔离。官方链路 `localhost:9876` 无独立鉴权(docs/architecture.md 已声明),威胁模型必须假定同机进程可达。

L2 才拆分 Contract Authority、Attestor、Publisher。

---

## 4. 最小 manifest(规范)

V1 manifest 只覆盖放行所需字段:

- scene、view layer、collection、object、instance 的稳定路径与可见性;
- object transform、parent、类型、data identity;
- Mesh 顶点坐标/面索引/normal/UV/material index 的量化摘要(固定 dtype、endianness、量化与 chunk 规则);
- modifier 名称、类型、关键参数与 evaluated mesh 摘要;
- material slot、节点/链接摘要、纹理相对路径与 byte hash;
- armature/action/FCurve 的 applicable 摘要;
- unit、frame range、render/export preset;
- 外部依赖相对路径、大小、hash、packed 状态;
- `schema_version`、`coverage`、`unsupported_fields`。

只有实际出现误判后再扩 coverage。现有 `scene_hash`([scene_hash.py:13-32](bridge/core/scene_hash.py#L13))仅覆盖名称/类型/量化矩�阵/RNA 类型/顶点边面数,正式名称保持 `phase0_structure_digest`,禁止用于 source↔export、两次 clean-run、checkpoint 或发布 identity。

**`mesh.validate()` 使用约束**(Blender API:返回 `True` 表示发现**并已修正/移除**非法几何——有副作用):

1. inspector 先在原始数据上完成 authored/evaluated manifest 计算;
2. 之后仅在 **disposable copy**(`mesh.copy()` 于临时 datablock,用后即弃)或独立短命进程上调用 `validate(verbose=True)`;原始 datablock 永不调用;
3. 返回 `True` → 记 `geometry_invalid` Fail(数据本含非法结构),不是"已修好"的 Pass;
4. `validate()` 不覆盖非流形、法线朝向、UV 重叠、材质语义——这些是独立自建检查。

---

## 5. 视觉协议(规范)

### 5.1 视图与 pass

L0:front/back/left/right/top 五个正交视图 + 一个 perspective + 两个固定斜视角,共 8 视角;每视角输出 beauty、silhouette、wire 三个 pass。silhouette/wire/clay 用 Workbench(确定性好);beauty 用 EEVEE 时必须绑定参考平台声明(GPU 厂商 × 后端 × OS 作为阈值键)——Blender 官方自身将 EEVEE 视为跨平台非确定。

L1/L2:斜视角升级为输入冻结后派生的 holdout;动画按合同选关键帧与极值帧。

所有图由 evaluator-owned camera、light、world、OCIO 与 render setting 生成;没有实际打开并判读的图只能写 `visual_unverified`。

### 5.2 像素回归

主门:`oiiotool ref out --fail <t> --failpercent <p> --diff`,保存 RGB/Alpha diff 图。默认起点 `t=0.016, p=1`——**这是 Blender 官方渲染回归的工程起点**(实测 [render_report.py @ e6d1620](https://github.com/blender/blender/blob/e6d1620ad53feed4a83e3b168f0a2ea74f4de6ce/tests/python/modules/render_report.py) 与当前 main 均如此),**不是资产质量依据**;每份合同必须显式声明自己的阈值,只能收紧或按 R0 冻结的平台键放宽。失败态映射:子进程崩溃→`Crash`,输出缺失/零字节→`Missing`,超阈值→`Fail`(对应上游 CRASH/NO OUTPUT/VERIFY,不新增状态)。

### 5.3 软评分(P1 起,非 P0)

FLIP(NVIDIA,感知第二意见)与 VLM/CLIP 评分都属 P1,引入时:版本进入工具锁定表;评分只产生 `Warning` 级软信号,永不参与 §2.4 硬判定;同一视角必须同时评 beauty 与 clay(无纹理)两版以对抗 typographic 作弊,两版分数差超过 R0 冻结阈值 → 人工告警;评分渲染一律 evaluator-owned,拒收候选自渲图。

### 5.4 确定性分级(L1)

| 级别 | 比较对象 | 典型容差 |
|---|---|---|
| Byte | exact artifact bytes | 0 |
| Structure | 层级、数量、标识、依赖图 | 0 |
| Geometry | evaluated positions/normals/UV/bounds | 合同量化容差 |
| Render | diagnostics/beauty | 合同 hardfail+percent |

含时间戳、随机 seed、GPU 非确定性的层先规范化或声明不可要求 byte deterministic,其余 applicable 层仍需比较。

---

## 6. GitHub 与上游证据(修订版)

事实锚定原则:一律以 commit/advisory/release ID 为准;动态指标(star 数、当日版本号)不作为架构依据,如出现则标注 `observed_at=2026-08-24`。

### 6.1 对 V3.3 证据链的三处修正(经实测)

1. **撤回"e6d1620 是 idiff 时代提交"**。本轮实测该提交源码:已使用 oiiotool、默认 `0.016/1%`、生成 RGB/Alpha diff——V3.2 的原始引用一直是准确的,V3.3 的"修正"本身是错误(源自对二手调研的过度推断)。教训入 §11 处置表。
2. **ellmos 评价改写**。其 "one-shot"(每次调用一个全新 Blender 子进程)描述属实,不承诺全局互斥,先前以"无互斥"反驳属概念错位。真正成立且经双重实测的是假绿路径:固定结果文件名 + 未传 `--python-exit-code` 时,内嵌脚本抛普通异常 Blender 仍 exit 0(本机实测:无 flag exit=0,`--python-exit-code 7` 时 exit=7),残留 JSON 会被当作本轮结果。→ 夹具 `stale_result_file`。
3. **glTF-Validator 盲区逐项处置**(取代"合同记录"的含糊表述):

| 项 | 性质 | L0 处置 | L1+ 处置 |
|---|---|---|---|
| Draco 压缩网格检查整体跳过(issue #235) | 假绿盲区 | **forbid**:导出 preset 不启用;输入含该扩展 → 拒收 | 合同声明时 supplement:目标运行时实测解码 |
| KTX2/basisu 纹理载荷不验证(#177) | 假绿盲区 | **forbid**(同上) | 同上 |
| `KHR_animation_pointer` 验证不完整(#248;glTF-Blender-IO 的 CI 对含 "pointer" 的用例跳过 validator) | 假绿盲区 | **forbid**:P0 只支持静态资产,含该扩展 → 拒收 | 动画 Profile(P1)引入时 supplement:导入端实测 |
| >4GB 误报 `BUFFER_BYTE_LENGTH_MISMATCH`(#244) | 误报而非盲区 | 合同大小上限(建议 ≤512 MiB)天然规避;记 known-issue | 同 L0 |

其余上游事实维持 V3.3 结论,均以固定 ID 锚定:glTF-Validator 仅 severity=error 影响退出码、CLI 默认 `--validate-resources` 而库 API 默认关闭、npm 最后发布 `2.0.0-dev.3.10`(2024-10)、`--config` YAML 可升级消息 severity;OpenUSD GHSA-8878-wr6v-j5cm(见 §1 L1);blender-asset-tracer 官方源与版本线(§1);`mesh.validate()` 副作用(§4);MCP ToolAnnotations 均为 hint、不可作为安全决策依据。

### 6.2 已验证可继续引用的先例

- 仓库内:Phase 0 wrapper 的全部安全原语与三个 known-bad 回归([test_phase0_acceptance.py](tests/unit/test_phase0_acceptance.py):L55/L78/L172);`verify_live` 的等序目录比较、单一只读探针、快照防 stale([verification.py:1035-](plugins/blender-mcp-installer/scripts/blender_mcp_installer/verification.py#L1035));`RELEASE=1` 的"精确重建 + 逐字节比对"范式。
- 上游对照:ahujasid/blender-mcp 的 `execute_code` 为裸 `exec`,无沙箱与产物校验,RCE 类 issue 关闭不修(#201/#207/#261),有两个 2026 CVE(GHSA-qqw9-95ww-prfm、GHSA-5hr7-6m56-f3rg)——最流行上游把验收明确让位使用者;PatrykIti/blender-ai-mcp 以确定性测量为卖点,方向与本方案一致(observed_at=2026-08-24)。
- 反例转化:dcc-mcp 的 `passed=false` 仍 `skill_success`、pytest exit 5(零收集)当成功;blender-agent-studio 的 `hard_gate_pass=false` 但脚本 exit 0、公开 CI 不启动 Blender;→ 夹具 `zero_checks_collected` 与双判定原则。
- 可借鉴:blender-agent-studio `verifyReproduction`(生成脚本在干净环境重跑并重过全部硬门,P1 可选合同声明 `reproducible_by_script`);newo-ether 的"提交时重新验证、不信任先前 validate"与指针泄漏审计(P1);pyblish/AYON 的有序插件范式(本方案的增强:冻结 check 集+版本+序的哈希,pyblish 生态无此概念);Unreal DataValidation 的单 CLI 非零退出形态;glTF-Blender-IO 每周 cron 对 daily build 的金丝雀回归(P1)。

---

## 7. P0 实施合同(L0,文件级)

### 7.1 范围与非目标

P0 支持两种 kind:`blend_native`、`interchange`(GLB)。不含:USD/FBX、动画 Profile、双 child、沙箱、软评分、签名。P0 目标平台:本机 macOS(`isolation_grade=local-trusted`)。

### 7.2 包结构(定案,不再二选一)

新建顶层包 `acceptance/`(与 `bridge/`、`server/`、`smoke/` 并列;不并入 `smoke/`——后者是 Phase 0 专属域):

```text
acceptance/
  __init__.py
  primitives.py          # 从 run_phase0_acceptance.py 复制的最小原语(见 7.3)
  contract.py            # contract.json 封闭加载与校验(未知字段即 Fail)
  check_registry.py      # check ID → (实现版本, 执行序) 注册表;R0 哈希对象
  failure_codes.py       # 封闭 failure-code family 枚举
  glb_budget.py          # 自研 GLB JSON-chunk 只读统计(见 7.5)
  schemas/
    contract.schema.json
    result.schema.json   # 每个子进程结构化产物的封闭 schema
    summary.schema.json
  blender_scripts/       # 在 Blender 子进程内运行,可 import bpy
    inspector.py         # R2:manifest + 依赖清单 + mesh.validate(copy)
    export_glb.py        # R3:固定 preset(禁 Draco/KTX2/animation_pointer)
    reimport_probe.py    # R4:fresh-import 投影提取
    render_views.py      # R4:evaluator-owned 8 视角 × 3 pass
scripts/asset_accept.py  # 薄 CLI coordinator(argparse → acceptance.*)
tests/unit/test_asset_accept.py      # 判定逻辑(monkeypatch,无真 Blender)
tests/asset_fixtures/
  generators/            # 每个 fixture 一个确定性 bpy 生成脚本
  expected/              # 每个 fixture 的预期 manifest/failure code
docs/acceptance/         # 本文与历史版本的正式归档位(见 §10)
```

### 7.3 与既有代码的关系(P0 不修改任何既有文件)

`primitives.py` **复制**(非迁移)`run_phase0_acceptance.py` 中的最小原语:root 规范化与私有目录、环境清洗、严格 JSON 三件套、`_file_evidence`、`_write_json_exclusive`、进程组运行/终止、`AcceptanceFailure`(约 150 行,逐函数注明来源与"与源同步检查"义务)。理由:

- `tests/unit/test_phase0_acceptance.py:8` 直接 `from scripts import run_phase0_acceptance`,证明 import 路径可行,但生产代码依赖另一脚本的私有函数会把 Phase 0 的私有实现固化为公共 API;
- 两条链路生命周期不同步,复制保持"已闭合的 Phase 0 零变更";
- 共享库提取推迟到 P1:当两个消费者的接口都稳定后,一次性提取并让双方回 import,以 `checks.sh` 全绿收口。

### 7.4 外部工具锁定表(结构冻结;版本值在 P0 首次实施时填死并入 contract digest)

| 工具 | 用途 | 锁定方式 |
|---|---|---|
| Blender | R2/R3/R4 子进程 | 绝对路径 + `--version` 输出记录(现状 5.2.x LTS) |
| glTF-Validator | R3 合规层 | 二进制/npm 版本 + SHA-256;基线 `2.0.0-dev.3.10`(npm 最后发布);`--config` YAML 文件本身入合同 digest |
| oiiotool | R4 像素回归 | 安装来源 + `--version` 记录 |
| Python/uv | coordinator | 沿仓库现状:精确 3.13.13、`uv run --frozen` |
| FLIP / gltf-transform / BAT | P1 起 | 进入本表后才可使用 |

工具输出解析失败、版本与锁定不符 → 对应 stage Fail(`tool_output_invalid` / `toolchain_mismatch`)。

### 7.5 GLB 预算层(自研,消除对外部 CLI 输出格式的依赖)

P0 的预算统计不解析 `gltf-transform` 的人类可读输出,而是**自研 GLB JSON-chunk 只读解析**(`glb_budget.py`):按 GLB 容器规范读 header 与 JSON chunk(严格 JSON 模式、大小上限),从 glTF JSON 直接统计 mesh/primitive/material/image 数、accessor count(三角形数)、声明的 image 尺寸与 buffer 大小、扩展列表(用于 §6.1 的 forbid 判定);**不解码任何二进制载荷**。预算键与阈值由合同声明。`gltf-transform inspect` 降级为 P1 可选交叉验证(引入时冻结 `--format csv` + 版本 + 每表列 schema,解析失败即 Fail)。

### 7.6 Fixture 预言机(独立于被测实现)

- **golden fixture 一律由 `tests/asset_fixtures/generators/` 下的小型确定性 bpy 脚本生成**(数十行、人工可穷举审阅),预期 manifest/failure code 手写在 `expected/`,不由被测实现生成;
- `hantavirus_scientific_cutaway_v2.blend` 是 **pilot candidate,不是 known-good**:它走完整流程产出报告供人工审定;只有当独立人工审阅记录(审阅人、日期、预期对象清单、视觉基线认可、来源说明)入库后才可晋级,且晋级本身是新 contract digest;
- golden/基线更新权限:任何 expected/基线变更必须伴随生成脚本或审阅记录变更,禁止"跑一遍把输出存成新基线"的自我更新。

### 7.7 P0 完成定义

以下全部满足才可声明 P0/L0 完成:

1. `blend_native` 与 `interchange/glb` 两分支实现且 coordinator 满足 §2.4 公式;
2. 至少一个生成器 known-good 全绿;
3. §8 全部 L0 夹具以预期 failure code 被拒绝(父 harness 不改写 child 原始 Fail);
4. 真 Blender 路径在本机通过(coordinator 判定逻辑另有无 Blender 的 unit 覆盖);
5. `bash scripts/checks.sh` 全绿(新增测试并入);
6. pilot candidate 报告产出并附人工审定结论(无论 Pass/Fail)。

### 7.8 P1 / P2(概要)

P1(L1):第二 normal child 与四级确定性;沙箱与资源限制(§1);BAT 5.2 fixture matrix 后启用依赖闭包交叉验证;offline reopen;USD/FBX/动画 Profile;`reproducible_by_script` 可选门;FLIP/VLM 软信号;gltf-transform 交叉验证;每周 daily-build 金丝雀;共享库提取评估。
P2(L2):不同 OS principal、签名审批、DSSE/Sigstore、透明日志、Publisher receipt。

---

## 8. 回归夹具(规范)

义务边界:**每个规范性决策分支、每个 fail-open 风险类别、每个稳定 failure-code family 至少一个夹具**;OS/第三方工具的动态错误统一映射到有限父级 code(如 `tool_crashed`、`tool_output_invalid`),原始 detail 保留在 error 字段——不为无界底层错误码逐一建夹具。

| Fixture | 等级 | 预期 | 现状 |
|---|---|---|---|
| `exit_zero_success_false` | L0 | 子进程 exit 0 但产物 `success!=true` → 外层 Fail | wrapper 层已有([tests/unit/test_phase0_acceptance.py:55](tests/unit/test_phase0_acceptance.py#L55));资产层需对应物 |
| `reused_evidence_root` | L0 | 启动子进程前拒绝 | wrapper 层已有(L78);原语复制后同规则 |
| `stale_result_file` | L0 | 结果文件预先存在 → 拒绝;失败路径不得读旧 JSON | 无(实测依据 §6.1) |
| `zero_checks_collected` | L0 | expected 非空、actual 为空 → Fail | 无 |
| `validator_warning_passthrough` | L0 | report 含 policy 关注 warning 而退出码 0 → 仍 Fail | 无 |
| `forbidden_extension_present` | L0 | 输入/导出物含 Draco/KTX2/animation_pointer 扩展 → 拒收 | 无 |
| `hidden_extra_object` | L0 | inventory/coverage 捕获 | 无 |
| `same_counts_changed_vertices` | L0 | structure 同、geometry 摘要异 | 无 |
| `missing_texture` | L0 | dependency 检查失败 | 无 |
| `external_gltf_resource_missing` | L0 | validator 资源验证失败(CLI 默认 `-r`;库 API 须显式开) | 无 |
| `material_or_uv_lost_on_import` | L0 | 投影 diff 失败 | 无 |
| `candidate_compositor_spoof` | L0 | evaluator-owned diagnostics 不受影响 | 无 |
| `report_truncated_or_unknown_id` | L0 | expected-set equality / Truncated 失败 | 无 |
| `mesh_validate_dirty` | L0 | `validate()` 在 copy 上返回 True → `geometry_invalid`,原数据 manifest 未被污染 | 无 |
| `fixed_view_billboards` | L1 | post-freeze holdout 暴露 | 无 |
| `nondeterministic_geometry` | L1 | 两 child geometry 比较失败 | 无 |
| `parser_resource_bomb` | L1 | 资源限制终止 child,父级记录明确 code(GHSA-8878 型:打开不报错、读值才爆) | 无 |

L0 计 14 项(前 14 行);其中 5 项(`exit_zero_success_false`、`reused_evidence_root`、`stale_result_file`、`zero_checks_collected`、`report_truncated_or_unknown_id`)是 coordinator 层夹具,用合成产物即可,不需要 .blend;其余 9 项由 `generators/` 的确定性脚本构造。

L1 侧另需一项 `compressed_payload_supplement`:当合同按 §6.1 声明 Draco/KTX2/`KHR_animation_pointer` 的 supplement 分支时,缺少目标运行时实测证据即 Fail。P0 不实现该分支(L0 一律 forbid,由 `forbidden_extension_present` 覆盖),但该分支是 §6.1 表中的规范性决策分支,按本节义务边界必须在启用前配夹具——列此以免 L1 出现无夹具的规范分支。

---

## 9. 完成定义(四级)

- **本文完成**:门禁无顺序矛盾;自包含(单文档可恢复全部规范);审计发现全部处置(§11);
- **P0/L0 完成**:§7.7 六条全部满足;
- **L1 完成**:两个 clean child、可证明沙箱/资源限制(§1 平台基线)、依赖闭包 + offline reopen、L1 夹具通过;
- **L2 完成**:签名审批与 exact-digest Publisher 链实际 E2E 通过。

P0 代码与真 Blender fixture 落地前,唯一诚实结论仍是:

> 当前仓库的 MCP/Bridge 与分发链路验收已闭合;通用建模产物验收仍是设计,不得用于自动发布放行。

---

## 10. 立即行动清单

1. **解除正式验收阻塞**:处置 §0.3 列出的全部 untracked 文件——方案文档归档进 `docs/acceptance/`(并更新 `docs/README.md` 的"历史已移除"表述与 V3.1 的跟踪位置,使口径一致);`.blend`/PNG 作为 pilot candidate 移入 `tests/asset_fixtures/`(或仓库外资产目录,合同记录路径)。
2. **V3.1 勘误**:若保留,页首补一行"D35~D43 所述 wrapper 实际入仓于 `bf63c89`"。
3. **P0 启动**:按 §7 依序落地;首个提交即包含 `primitives.py` 复制与 coordinator 骨架 + unit 夹具,不触碰任何既有文件。

已从行动清单剥离(与验收闭环无关或不宜先验承诺):docs/ 空目录清理(git 不跟踪空目录,不影响任何门禁,列为可选卫生项);Phase 0 工具 `readOnlyHint` 标注(MCP 规范明确 annotations 仅为 hint,不构成安全边界;实施需同步更新 [test_server_process.py](tests/contract/test_server_process.py) 的目录投影断言,变更面小但非零——移入 P1 可选项)。

---

## 11. 审计发现处置表

V3.3 审计报告(5H/11M/5L)经独立验证后逐条处置。验证手段:e6d1620 源码实测、`man sandbox-exec`、Blender 退出码双实测(0/7)、pilot 资产计数复测(205 objects/21 meshes 与审计一致)、仓库 import/测试锚点核对。

| ID | 验证结论 | V3.4 处置 |
|---|---|---|
| H-01 自包含缺失 | 成立 | 本文内联全部门禁/状态/公式/kind/完成定义;V3.1~V3.3 降级为历史记录(§0 文档性质) |
| H-02 macOS 沙箱不可支持 | 核心成立(man page 实证 DEPRECATED) | §1 L1:独立用户/VM 为可证明基线;sandbox-exec 仅 best-effort;FD 次序原则限定于自研工具;macOS 断网诚实分级 |
| H-03 known-good 循环预言机 | 成立 | §7.6:pilot candidate 语义;golden 一律生成器产生;人工审定后才晋级;基线更新权限规则 |
| H-04 P0 缺实施合同 | 成立 | §7:包结构定案、工具锁定表、schema/registry 文件、golden 流程、完成定义六条 |
| H-05 Warning 判定不完备 | 成立 | §2.4 唯一公式(raw → disposition → effective → 放行) |
| M-01 e6d1620 判断错误 | 成立(实测该提交已用 oiiotool/0.016/1%/RGB+Alpha diff) | §6.1 撤回错误"修正",恢复 V3.2 引用;教训:二手调研结论不得直接改写对固定提交的事实声明 |
| M-02 盲区处置不完整 | 部分成立(V3.3 原文"三盲区+#244 误报"分类无计数矛盾;animation_pointer 无处置属实) | §6.1 四项逐一 forbid/supplement/known-issue 表 |
| M-03 inspect 无机器协议 | 成立 | §7.5 预算层改自研 GLB JSON-chunk 统计;gltf-transform 降 P1 且引入时冻结 CSV 协议 |
| M-04 视觉不闭合 | 成立(含"FLIP 未进入依赖锁与 check ID"一项——V3.3 提及 FLIP 但从未指派阶段,复审确认此子项属实) | §5.1 视图措辞修正为 5 正交+1 perspective+2 斜共 8 视角;§5.2 阈值定位为上游工程起点、每份合同必须显式声明;§5.3 FLIP/VLM 明确划入 P1、引入即入工具锁定表、只产生 Warning 级软信号 |
| M-05 validate 污染证据 | 成立 | §4:disposable copy/独立进程;新增夹具 `mesh_validate_dirty` |
| M-06 BAT 5.2 覆盖未建立 | 成立 | §1 L1 第 6 条:fixture matrix 前 BAT 仅交叉验证 |
| M-07 C2PA 论证错误/attestation 过宽 | 成立 | §1 L2:C2PA 排除理由改为"缺失即失败"闭包性;attestation 定位 CI provenance carrier |
| M-08 readOnlyHint 误作安全升级 | 成立(仓库实证:adapter 无 annotations;contract 测试含目录投影断言) | §10:移出立即行动,降 P1 可选,措辞改 hint |
| M-09 共享库提取非必要前置 | 成立(tests 已有 `from scripts import …` 先例) | §7.3:P0 复制原语、零改既有文件;提取延至 P1 |
| M-10 保尾弃头与取证冲突 | 成立 | §2.1 补充规则:证据日志全量+上限+Truncated 即 Fail;tail 仅限 LLM/UI 通道 |
| M-11 failure code 夹具无界 | 成立 | §8 义务边界改为决策分支/风险类别/稳定 family;动态错误映射父 code |
| L-01 阻塞清单漏 V3.3 | 成立 | §0.3 列全(含本文自身) |
| L-02 "八项"计数错误 | 成立 | §8 明确 L0 14 项及其构造方式分类 |
| L-03 一次一进程误读 | 成立(概念错位;stale 假绿经双方实测保留) | §6.1 第 2 条改写 |
| L-04 空目录属无关范围 | 成立 | §10 剥离为可选卫生项 |
| L-05 动态指标/绝对措辞 | 成立 | §6 锚定原则;"全部属实"限定为"固定提交范围内逐条核对";star 数标 observed_at |

复审勘误(本文自身的一处错误):V3.4 初稿曾以"复测 590 个 datablock"质疑审计报告的 295,复审实测证明**审计报告的 295 正确**——590 = 295 × 2,系把 `bpy.data.all_ids`(它本身再列出全部 ID)与其余各集合一并求和造成的重复计数(实测 `SUM_ALL_COLLECTIONS=590`、`len(all_ids)=295`、`SUM_MINUS_all_ids=295`)。这与 §11 M-01 记下的教训同类:错误的复核不得反向改写正确的事实声明。两侧 objects=205、meshes=21 本就一致。

**该错误直接产生一条 R2 实现约束**:inspector 统计 datablock coverage 时必须按具体类型集合枚举并显式排除 `bpy.data.all_ids`,否则内建 2× 重复计数;`hidden_extra_object` 夹具的预期值以按类型求和为准。
