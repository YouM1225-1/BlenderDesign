# Blender MCP / Skill 建模产物验收方案 V3.3 全量审计报告

> 审计对象：`blender_mcp_skill_acceptance_optimized_v3_3.md`  
> 对象 SHA-256：`95bd01d104b4d1b4d53dd8b698f9f12e41f09930d01f57c624d5f2a7908ba912`  
> 仓库基线：`bf63c89294a5f79649a2c550331ea8987cdeab1b`  
> 审计日期：2026-08-24（Asia/Shanghai）  
> 审计方式：只读审计；未修改 V3.3 方案正文或仓库源码

## 1. 执行结论

**总体判定：Major Revision Required / 暂不可作为实施与发布放行的规范性基线。**

V3.3 的核心方向成立：六门结构、fail-closed 双判定、expected-set equality、独立 fresh-import、evaluator-owned 视觉证据、分级信任边界，以及“当前通用资产验收仍是设计”的结论，均比 V3.1 更收敛，也与仓库已有 Phase 0 / `verify_live` 的证据范式一致。

但本轮发现 **5 项 High、11 项 Medium、5 项 Low**。High 项不是对总体架构的否定，而是说明当前文本还不能唯一地驱动实现与判定：

1. 规范依赖两个外部版本且 V3.2 未跟踪，无法独立重建完整合同；
2. L1 的 macOS 隔离路径采用已弃用、无受支持 profile 语言的 `sandbox-exec`，并包含无法直接套用到 Blender 路径加载模型的 FD 次序要求；
3. 未经过独立判定的工作树资产被预先命名为 `known-good`，形成循环测试预言机；
4. “文件级 P0”仍保留目录二选一，并缺少外部工具锁定、机器输出协议、视觉基线生命周期和 L1 runner；
5. `Warning` 的原始状态、allowlist disposition 与“Required 只有 Pass 放行”之间没有可执行的归并规则。

因此，V3.3 目前适合作为**架构决策与实施 backlog**，不适合作为**可直接编码、可重复执行、可自动发布放行的规范**。方案自己在 [V3.3:249-251](blender_mcp_skill_acceptance_optimized_v3_3.md#L249) 对“尚不可自动发布”的声明是诚实且正确的。

## 2. 范围、成功标准与证据等级

### 2.1 审计范围

- V3.3 全文，包括继承的 V3.2/V3.1 门禁、状态与完成定义；
- 当前仓库源码、测试、正式文档、Git 状态与现有试点资产；
- V3.3 引用的关键上游：Blender、blender-asset-tracer、glTF-Validator、glTF-Transform、OpenUSD、MCP Tool Annotations、GitHub Artifact Attestations、C2PA；
- 反例项目中直接影响结论的 ellmos 与 dcc-mcp 行为；
- 内部一致性、可实现性、判定完备性、威胁模型、证据可追溯性与过度设计风险。

### 2.2 成功标准

只有同时满足以下条件，方案才可判为“实施就绪”：

- 单一版本即可恢复完整、无歧义的规范；
- 每个 Required 门都有唯一输入、执行顺序、结构化输出和 fail-closed 决策；
- L0/L1/L2 的安全边界在目标平台有受支持且可测试的执行路径；
- known-good/known-bad 预言机来源独立于被测实现；
- 外部事实绑定可复核版本，且不会把建议、提示或测试基线误写为安全保证；
- P0 文件与依赖清单足以让另一位实现者在不补产品决策的情况下编码。

V3.3 尚未全部满足这些标准。

### 2.3 严重度

- **High**：会阻断规范实现、使安全边界名义化，或导致相同证据产生不同放行结果；
- **Medium**：会造成错误实现、证据失真或维护性风险，但局部决议后可闭合；
- **Low**：事实、计数、措辞或范围管理问题，不单独改变主结论。

## 3. 发现总表

| ID | 严重度 | 发现 | 影响 |
|---|---|---|---|
| H-01 | High | V3.3 不是自包含规范 | 无法独立重建完整门禁、状态与完成定义 |
| H-02 | High | L1 macOS 沙箱方案不可作为受支持实施路径 | 第三方资产隔离完成定义无法证明 |
| H-03 | High | 未验证资产被预设为 `known-good` | 测试预言机循环，可能把现存缺陷固化为基线 |
| H-04 | High | “文件级 P0”仍缺关键实施合同 | 实现者必须自行补架构与产品决策 |
| H-05 | High | `Warning` / disposition / Required 判定不完备 | 同一 validator report 可能产生不同结论 |
| M-01 | Medium | Blender `e6d1620` 的 idiff 时代判断错误 | 证据修正章节自身包含事实错误 |
| M-02 | Medium | glTF 盲区计数与处置不一致 | `KHR_animation_pointer` 等输入可落入未闭合路径 |
| M-03 | Medium | `gltf-transform inspect` 未定义机器协议 | 预算门不能稳定自动化 |
| M-04 | Medium | 视觉视图数、阈值来源和软评分规则不闭合 | 视觉门无法重现或误把上游测试默认值当资产标准 |
| M-05 | Medium | `mesh.validate()` 会污染同一 inspector 的后续证据 | 失败样本可能被修复后再取证 |
| M-06 | Medium | BAT v1.23 对 Blender 5.2 的通用覆盖未建立 | L1 依赖闭包存在版本空窗 |
| M-07 | Medium | C2PA 排除论证错误，GitHub attestation 能力表述过宽 | L2 技术选型依据失真 |
| M-08 | Medium | `readOnlyHint` 被写成安全能力升级 | 提示被误当强制执行，且低估现有目录哈希测试影响 |
| M-09 | Medium | P0 先提取共享私有函数不是必要前置 | 扩大首个变更面并增加对已闭合 Phase 0 的回归风险 |
| M-10 | Medium | 日志“保尾弃头”与取证目标冲突 | 根因与启动环境可能从正式证据中消失 |
| M-11 | Medium | “每个 failure code 一个夹具”过宽且不可封闭 | 动态 OS/工具错误码会制造无界测试义务 |
| L-01 | Low | 工作树阻塞清单遗漏 V3.3 自身 | 同状态陈述不准确 |
| L-02 | Low | “L0 八项”与表中 12 项 L0 夹具不一致 | 实施范围计数错误 |
| L-03 | Low | ellmos 的“一次一进程”被误解为互斥 | 来源评价失真，但 stale-file 反例成立 |
| L-04 | Low | 删除空文档目录不属于资产验收闭环 | 无关范围扩张 |
| L-05 | Low | 动态 star/版本与“全部属实”绝对措辞不可复现 | 文档快速陈旧，降低审计可信度 |

## 4. High 发现

### H-01：V3.3 不是自包含规范

**证据**

- [V3.3:7-8](blender_mcp_skill_acceptance_optimized_v3_3.md#L7) 明确以工作树未跟踪的 V3.2 为输入并“继承 V3.2”；
- [V3.3:139](blender_mcp_skill_acceptance_optimized_v3_3.md#L139) 将六门表、Fail 条件、三个进程边界、Artifact Kind 表和八状态整体外置到 V3.2；
- [V3.3:145](blender_mcp_skill_acceptance_optimized_v3_3.md#L145) 的命令模板又外置到 V3.1；
- [V3.3:249](blender_mcp_skill_acceptance_optimized_v3_3.md#L249) 的完成定义继续外置到 V3.2；
- 当前 Git 状态中 V3.2、V3.3 都未跟踪，V3.3 也没有冻结 V3.2 的摘要或 digest。

**反例**

只复制 V3.3 到 CI 设计评审或另一仓库，实施者无法从本文恢复 R0-R5 的完整 Required 证据、Artifact Kind 条件、状态归并和 P0 完成定义。若 V3.2 被后续编辑，V3.3 的语义会在自身字节不变时漂移。

**判定**

这不影响其作为“增量评审记录”的价值，但阻断其成为规范性基线。需要单一可版本化对象，或至少固定继承文档的内容摘要并附完整规范快照。

### H-02：L1 macOS 沙箱方案不可作为受支持实施路径

**证据**

- [V3.3:125-131](blender_mcp_skill_acceptance_optimized_v3_3.md#L125) 把 macOS `sandbox-exec` 与独立用户并列为 L1 具体方案；
- Apple DTS 明确说明 `sandbox-exec` 已弃用，SBPL 不对第三方提供受支持文档，不宜据此构建产品；受支持的 App Sandbox 依赖签名与 entitlements，而不是任意进程 profile（[Apple Developer Forums](https://developer.apple.com/forums/thread/661939)、[App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)）；
- [V3.3:129](blender_mcp_skill_acceptance_optimized_v3_3.md#L129) 要求“先打开全部输入/输出 fd，再接触不可信字节”，但 `.blend`、链接库、纹理、缓存和解析器通常按路径在加载过程中递归发现，Blender 与 validator 的现有接口也以路径而非预打开 FD 为主。

**影响**

L1 完成定义要求 sandbox/resource limits；如果 macOS runner 只能依赖已弃用且无受支持 profile 语言的工具，或 FD 原则无法落到实际 API，L1 会出现“文档称有隔离、实现无法证明隔离”的名义安全边界。

**建议方向（未实施）**

把“独立 OS 用户/虚拟机/受控远程 runner”设为 macOS 可证明基线；若仍实验使用 `sandbox-exec`，只能标为 best-effort defense-in-depth，并以拒绝网络、路径逃逸和资源炸弹的黑盒夹具验证，不能等同于受支持的安全边界。

### H-03：未验证资产被预设为 `known-good`

**证据**

- [V3.3:66](blender_mcp_skill_acceptance_optimized_v3_3.md#L66)、[V3.3:213-216](blender_mcp_skill_acceptance_optimized_v3_3.md#L213) 和 [V3.3:257](blender_mcp_skill_acceptance_optimized_v3_3.md#L257) 直接把工作树中的 `hantavirus_scientific_cutaway_v2.blend` 称为第一个 `known-good` 并建议移入测试夹具；
- 它当前未跟踪，没有独立 golden approval、来源/许可证、生成器、预期 manifest 或人工审阅记录；
- 本轮只读实测只能证明：Blender 可加载、无报告的缺失外部文件、BAT v1.23 可解析且未列出外部依赖。它不能证明对象清单、科学语义、视觉质量、渲染一致性或预期合同均正确。

**影响**

若先把该资产定义为通过，再用它校准阈值与 schema，资产中的隐藏对象、错误标注、材料缺陷或偶然平台输出会被固化为“正确答案”。这是典型循环预言机。

**建议方向（未实施）**

先称为 `pilot candidate`；由独立人工审批生成最小预期清单、视觉基线和来源记录后才能晋级 `known-good`。更稳妥的第一批 golden fixture 应由小型确定性生成脚本产生，人工可穷举验证。

### H-04：“文件级 P0”仍缺关键实施合同

**证据**

- [V3.3:197-207](blender_mcp_skill_acceptance_optimized_v3_3.md#L197) 保留 `acceptance/ # 或并入 smoke/` 的未决二选一；
- 文件表没有冻结 contract JSON schema、result/report schema、check ID 注册表、failure-code 注册表、validator policy 文件、golden/reference 文件、视觉基线审批记录或 sandbox runner；
- [V3.3:209](blender_mcp_skill_acceptance_optimized_v3_3.md#L209) 只写“固定版本二进制”，未给 glTF-Validator、glTF-Transform、OIIO、FLIP 的版本、下载来源、SHA-256、平台矩阵或安装/构建方式；
- `gltf-transform inspect`、oiiotool、FLIP 的输出格式与解析失败状态未写入 R5 expected IDs；
- P0 完成要求真 Blender fixtures，但文件级清单没有 fixture 生成/审批入口和 golden update 流程。

**影响**

不同实现者会自行选择包结构、工具版本、输出解析、check IDs 和基线更新权限，得到互不兼容的“P0 通过”。因此“文件级”目前只是文件名级 backlog，不是实施合同。

### H-05：`Warning` / disposition / Required 判定不完备

**证据**

- 继承的 V3.2 规定“Required 只有 `Pass` 可放行”，同时规定 `Warning` 保留原始状态，冻结 policy allowlist 可另记 accepted disposition；
- [V3.3:141](blender_mcp_skill_acceptance_optimized_v3_3.md#L141) 又要求冻结 validator severity 覆盖，[V3.3:151](blender_mcp_skill_acceptance_optimized_v3_3.md#L151) 规定 warning 按 policy 判定；
- 文档没有定义 `raw_status=Warning + disposition=Accepted` 的 effective status，也没有说明它在 expected-set equality 与最终 exit 计算中是否等同于 Pass。

**反例**

同一条 allowlisted validator warning，可以被实现 A 保持 `Warning` 并按“Required 只有 Pass”拒绝，也可以被实现 B 依据 disposition 放行。两者都能从现有文字找到依据。

**判定**

R5 需要唯一决策公式。应显式区分 raw finding、policy disposition 与 effective decision，并规定任何降级/升级都由 R0 冻结且进入合同 digest。

## 5. Medium 发现

### M-01：Blender `e6d1620` 的 idiff 时代判断错误

[V3.3:78](blender_mcp_skill_acceptance_optimized_v3_3.md#L78) 称 V3.2 的七个提交均为当前 HEAD；[V3.3:114](blender_mcp_skill_acceptance_optimized_v3_3.md#L114) 却称同一个 `e6d1620` 是 idiff 时代提交。对该提交的源码实查显示它已经调用 `oiiotool`，包含 `--fail`、`--failpercent`、RGB/Alpha diff，默认阈值正是 `0.016` 与 `1`（[Blender `render_report.py` @ `e6d1620`](https://github.com/blender/blender/blob/e6d1620ad53feed4a83e3b168f0a2ea74f4de6ce/tests/python/modules/render_report.py)）。

oiiotool 机制本身的总结大体正确；错误在“修正来源”的历史判断与内部自相矛盾。

### M-02：glTF 盲区计数与处置不一致

[V3.3:90](blender_mcp_skill_acceptance_optimized_v3_3.md#L90) 列出 Draco、KTX2、`KHR_animation_pointer`、>4GB 四项，却称“三个盲区”；随后只给 Draco/KTX2 禁用策略。`KHR_animation_pointer` 在 validator README 中仍标为 partial；>4GB #244 是误报/兼容性问题，不是同类“假绿盲区”。

已核实的上游事实包括 [Draco #235](https://github.com/KhronosGroup/glTF-Validator/issues/235)、[KTX2 #177](https://github.com/KhronosGroup/glTF-Validator/issues/177)、[>4GB #244](https://github.com/KhronosGroup/glTF-Validator/issues/244)。L0 必须明确禁止、补充检查或允许每一项适用扩展，而不能只“在合同中记录”。

### M-03：`gltf-transform inspect` 未定义机器协议

[V3.3:91](blender_mcp_skill_acceptance_optimized_v3_3.md#L91) 和 [V3.3:151](blender_mcp_skill_acceptance_optimized_v3_3.md#L151) 把 `inspect` 定义为预算硬门，但没有指定 `--format`、表结构、字段映射、单位、缺表行为和 CLI exit 语义。官方 CLI 文档只承诺面向人的性能报告，并提供 pretty/CSV/Markdown 格式，没有 JSON 合同（[glTF-Transform CLI](https://github.com/donmccurdy/glTF-Transform/blob/main/packages/docs/src/lib/pages/cli.md)）。

直接解析默认终端表不稳定；即使采用 CSV，也需冻结版本、每张表的 schema 和解析失败即 Fail 的规则。

### M-04：视觉视图数、阈值来源和软评分规则不闭合

- [V3.3:176](blender_mcp_skill_acceptance_optimized_v3_3.md#L176) 称“6 正交 + 2 固定斜视角”，但 V3.2 的实际集合是 front/back/left/right/top/perspective + 2 斜视角，即 5 个轴向视图 + 1 个 perspective，不是 6 个正交视图；
- [V3.3:174](blender_mcp_skill_acceptance_optimized_v3_3.md#L174) 直接采用 Blender renderer regression 的默认阈值作为资产验收起点。该阈值证明上游渲染回归的工程先例，不证明它适合对象完整性、材质语义或跨平台资产质量；
- FLIP 没有进入 P0 依赖锁或 check ID；
- [V3.3:175](blender_mcp_skill_acceptance_optimized_v3_3.md#L175) 的“显著背离”没有阈值、统计方式和 disposition，只能是人工/软告警，不能成为可重复硬门。

### M-05：`mesh.validate()` 会污染同一 inspector 的后续证据

Blender API 明确规定 `Mesh.validate()` 会修正/移除非法几何，返回 `True` 表示发生了修正。V3.3 已正确识别其反直觉语义，但 [V3.3:146](blender_mcp_skill_acceptance_optimized_v3_3.md#L146) 仍允许在原始 mesh 上原位调用。

若实现不是立刻终止，后续 console、截图、统计或错误详情看到的是修复后的内存状态；即使立刻终止，原始失败详情也只有非结构化控制台输出。应在 disposable mesh copy 或独立短命进程上调用，并保留调用前 manifest。

### M-06：BAT v1.23 对 Blender 5.2 的通用覆盖未建立

官方 BAT v1.19/1.20 的 changelog 只明确写到 Blender 5.0 文件头与 compositor 支持；v1.23 主要是 Geometry Nodes 容错。BAT v2 则从 5.1 起改为 Blender 内 `bpy` 模型，以便自动跟随新路径类型，并列出 5.1 若干依赖遗漏限制。

本轮 `bat 1.23 list hantavirus_scientific_cutaway_v2.blend` 成功，只证明该试点可解析，不证明 Blender 5.2 的所有链接、Geometry Nodes simulation cache、Alembic 序列等依赖都被覆盖。将 v1.23 设为 5.2 通用 L1 依赖闭包工具前，需要针对 5.2 依赖类型建立 fixture matrix。

### M-07：C2PA 排除论证错误，GitHub attestation 表述过宽

[V3.3:117](blender_mcp_skill_acceptance_optimized_v3_3.md#L117) 以 C2PA 没有 blend/glTF/USD 内嵌类型且元数据可剥离为由“明确不采用”。C2PA 2.2 明确允许 external manifest，且外置 manifest 可用内容哈希绑定不支持内嵌的资产；剥离或缺失应导致验证不可得/失败，并非继续保持有效（[C2PA External Manifests](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html)）。因此“不适合作为当前默认方案”可以成立，但现有技术论证不成立。

GitHub Artifact Attestations 的确提供 SLSA v1 Build L2，并可用 `subject-path` 绑定文件（[GitHub Docs](https://docs.github.com/en/actions/concepts/security/artifact-attestations)、[`actions/attest`](https://github.com/actions/attest)）。但 GitHub 同时说明 attestation 不是安全保证，并建议签发布产物/manifest，而不是频繁测试输出或单个嵌入图片。方案应把它表述为 CI provenance carrier，而不是任意资产路径天然获得 L2 质量保证。

### M-08：`readOnlyHint` 被写成安全能力升级

Anthropic Directory 的确要求适用的 tool annotations（[Directory Policy](https://support.anthropic.com/en/articles/11697096-anthropic-mcp-directory-policy)），补标注有兼容性价值。但 MCP 规范明确所有 ToolAnnotations 都只是 hints，来自不可信服务器时不能用于安全决策（[MCP schema](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2025-06-18/schema.ts)）。

因此 [V3.3:260](blender_mcp_skill_acceptance_optimized_v3_3.md#L260) 的“从文档承诺升级为协议声明”只能理解为元数据声明，不能理解为只读强制。当前 adapter 的三个 `@mcp.tool()` 没有 annotations；新增 annotations 还会改变工具目录序列化内容及相关 schema/hash golden，不能先验断言为“一次性小改”。

### M-09：P0 先提取共享私有函数不是必要前置

[V3.3:184-193](blender_mcp_skill_acceptance_optimized_v3_3.md#L184) 要求第一步迁移多个已工作的私有函数并回 import。现有 `tests/unit/test_phase0_acceptance.py` 已直接 import `scripts.run_phase0_acceptance` 并测试其私有函数，说明新 coordinator 可以先复用现有模块或只复制极小稳定原语，等第二个消费者真实稳定后再提公共模块。

一次迁移十余个进程、环境和文件安全函数会扩大对已闭合 Phase 0 的首个变更面，且 `AcceptanceFailure`、参数化环境前缀与 caller-specific error code 很可能并非真正通用。该步骤违反方案自己强调的“最小 P0”和精准修改原则。

### M-10：日志“保尾弃头”与取证目标冲突

[V3.3:161](blender_mcp_skill_acceptance_optimized_v3_3.md#L161) 把保尾弃头同时用于防证据文件和 LLM 上下文膨胀。对 UI/MCP 响应保 tail 是合理的，但正式 evidence 若也只保 tail，会丢失启动命令、版本、环境、最早异常和资源加载路径。

应区分：磁盘上的有界完整原始日志/分段日志，与返回给 LLM 的 bounded tail。超限时应保 head + tail、原始字节数与截断位置，或直接把 Required evidence 标为 `Truncated` 并失败。

### M-11：“每个 failure code 一个夹具”不可封闭

[V3.3:243](blender_mcp_skill_acceptance_optimized_v3_3.md#L243) 将每个 failure code 都设为必须有 fixture。对 coordinator 决策分支和安全分类这是好规则；对 OS errno、第三方 validator 版本错误、签名服务错误、平台 GPU 错误等动态 code 则会形成无界义务。

更可执行的边界是：每个规范性决策分支、每个 fail-open 风险类别和每个公开稳定 failure-code family 至少一个夹具；底层动态错误映射为有限的稳定父级 code，并保留原始 detail。

## 6. Low 发现

### L-01：工作树阻塞清单遗漏 V3.3 自身

[V3.3:41](blender_mcp_skill_acceptance_optimized_v3_3.md#L41) 列出 V3.2、两个 `.blend` 和一个 PNG，却没有列出同样未跟踪的 V3.3。结论“工作树脏、正式 Phase 0 会拒绝”正确，清单不完整。

### L-02：“L0 八项”与夹具表不一致

[V3.3:214](blender_mcp_skill_acceptance_optimized_v3_3.md#L214) 说“§7 中 L0 八项”，而 [V3.3:226-237](blender_mcp_skill_acceptance_optimized_v3_3.md#L226) 实际有 12 条 L0 fixture。

### L-03：ellmos 的“一次一进程”被误解为互斥

ellmos 的 README 所谓 one-shot/stateless 是“每次调用启动一个 Blender 子进程”，并未承诺全局并发互斥；[V3.3:84](blender_mcp_skill_acceptance_optimized_v3_3.md#L84) 用“全仓无互斥”反驳该说法，属于概念错位。

同一段发现的真正风险成立：固定结果文件 + 未使用 `--python-exit-code` 可在普通 Python 异常时留下 Blender exit 0；本轮用 Blender 实测 `RuntimeError` 在无该参数时 exit 0、加参数后 exit 7。`stale_result_file` fixture 因此仍值得保留。

### L-04：删除空文档目录属于无关范围扩张

[V3.3:72](blender_mcp_skill_acceptance_optimized_v3_3.md#L72) 和 [V3.3:258](blender_mcp_skill_acceptance_optimized_v3_3.md#L258) 建议“顺手删除”空目录。Git 不跟踪空目录，它们不影响运行时 provenance、clean-worktree 或资产门禁；这不属于本方案闭环，应从立即行动的必要项中剥离。

### L-05：动态事实与绝对措辞降低可复现性

[V3.3:47](blender_mcp_skill_acceptance_optimized_v3_3.md#L47) 使用“全部属实”，[V3.3:96](blender_mcp_skill_acceptance_optimized_v3_3.md#L96) 使用 star 数、当日发布和遥测状态。这些信息会变化，且 star 数不参与任何门禁决策。应优先固定 commit/tag/advisory ID；无法固定的动态指标标注 `observed_at`，不要作为架构结论的主要证据。

## 7. 经复核成立的关键结论

以下内容没有被上述发现推翻，可继续作为方案基础：

1. **仓库当前常规门禁真实通过。** 本轮复用同一工作树执行结果：362 个 unit/contract 通过；distribution 821 通过、1 条件跳过；`ALL CHECKS PASSED`。
2. **Phase 0 wrapper 的安全与证据原语真实存在。** 全新私有 root、dirty-worktree 拒绝、环境清洗、严格 JSON、`O_EXCL`、进程组清理、exit+artifact 双判定、SHA-256 汇总均有源码与 unit 覆盖。
3. **三项 known-bad 回归真实存在。** `exit_zero_success_false`、`reused_evidence_root`、`wrong_python_patch` 的测试锚点准确。
4. **`verify_live` 是 expected-set equality 与 stale 防护的有效本仓先例。** 工具目录等序比较、只读 probe 名称/空参数固定、inspection 前后快照均可复用其设计思想。
5. **当前 `scene_hash` 不足以担当深层资产 manifest。** 它没有覆盖顶点内容、UV、材质节点、依赖内容等验收关键语义。
6. **glTF-Validator 的退出码边界判断正确。** 官方 README 规定至少一个 error 才非零，CLI 默认验证资源；配置文件允许 severity override（[官方 README](https://github.com/KhronosGroup/glTF-Validator)、[config example](https://github.com/KhronosGroup/glTF-Validator/blob/main/docs/config-example.yaml)）。解析 JSON report 而非只看 exit 是正确设计。
7. **OpenUSD 风险与基本对策准确。** GHSA-8878 影响 `<26.05`、修复于 `>=26.08`，安全检查受 `PXR_PREFER_SAFETY_OVER_SPEED` 控制；无安全构建不应在缺少沙箱/资源限制时处理不可信 crate（[GHSA-8878](https://github.com/PixarAnimationStudios/OpenUSD/security/advisories/GHSA-8878-wr6v-j5cm)）。
8. **Blender 官方图像回归的核心机制引用正确。** 当前 `render_report.py` 使用 oiiotool、默认 `0.016` / `1%`、生成 RGB/Alpha diff，并区分 VERIFY 等失败；错误仅在提交时代判断。
9. **`mesh.validate()` 副作用判断正确。** 它返回是否修正/移除了非法几何，而不是纯检查结果。
10. **MCP annotations 与资产验收是叠加关系。** Directory 合规不能替代产物正确性；补 annotations 有生态兼容价值，只是不能当安全强制。
11. **dcc-mcp 的 zero-collection 假绿是真实反例。** 其 runner 明确把 `pytest.main()` 的 exit 5 映射为 0；`zero_checks_collected` 是合理回归夹具。
12. **“当前通用资产验收仍是设计”是准确状态。** 深层 manifest、独立格式验证、fresh-import、evaluator-owned 视觉判定和 clean-run 资产重复性均未在本仓实现。

## 8. 门禁与威胁模型覆盖矩阵

| 区域 | 设计完整度 | 实现状态 | 审计结论 |
|---|---|---|---|
| R0 Contract | 较强 | absent | check/version/order digest 思路正确；完整 schema 与 disposition 公式缺失 |
| R1 Freeze | 较强 | 仅 Phase 0 有相邻原语 | bytes/hash、私有 root、链接逃逸方向正确；资产递归依赖冻结尚未实现 |
| R2 Inspect | 中等 | absent | manifest 范围合理；BAT 5.2 覆盖和 `mesh.validate` 隔离未闭合 |
| R3 Produce/Validate | 中等 | absent | validator 双判定正确；外部工具锁、机器输出和扩展 policy 不完整 |
| R4 Reopen/Evidence | 中等 | absent | fresh-import/evaluator-owned 正确；视觉集合、golden 生命周期与阈值依据不完整 |
| R5 Decide | 较强但有一处阻塞歧义 | absent | expected equality、stale/zero checks 正确；Warning effective decision 未定义 |
| L0 trusted local | 可落地 | absent | 可作为 P0 首期；known-good 必须先独立建立预言机 |
| L1 untrusted/CI | 概念正确、平台实施不足 | absent | macOS sandbox 与解析器覆盖阻断完成声明 |
| L2 release/compliance | 方向性设计 | absent | DSSE/Sigstore 可行；C2PA 论证与 attestation 语义需校准 |

## 9. 建议的整改优先级（仅报告，不修改方案）

### P0 前必须决议

1. 把完整门禁、状态、Artifact Kind 和完成定义收敛为一个冻结版本；
2. 给出 raw finding → policy disposition → effective decision 的唯一公式；
3. 把试点资产降级为 candidate，先建立独立预期 manifest、人工视觉批准与来源记录；
4. 确定唯一包结构，并冻结所有外部工具、schema、check IDs、failure-code families 和 golden 更新权限；
5. 将 macOS L1 受支持隔离路径改为可验证的独立 principal/VM/runner，或明确 L1 暂不支持 macOS 本机。

### P0 实现时应闭合

1. `mesh.validate()` 在 disposable copy/进程运行；
2. `gltf-transform inspect` 固定 CSV 或改用稳定 API，自建封闭 schema；
3. 对 Draco、KTX2、animation pointer、超大文件分别定义 forbid / supplement / target-runtime / unsupported；
4. 明确视图坐标、投影、相机尺度、渲染引擎版本、OCIO、golden 建立与更新流程；
5. 正式 evidence 保留有界 head+tail 或完整分段日志，LLM 响应单独保 tail；
6. 只为稳定决策分支建立 failure fixtures，不追逐无界底层错误码。

### 可延后

- Tool annotations；
- C2PA 与 DSSE/Sigstore 的最终取舍；
- FLIP/VLM 软评分；
- 文档空目录整理；
- 共享库提取，待第二个消费者形成真实稳定接口后再做。

## 10. 审计执行记录与限制

### 10.1 本地实证

- `bash scripts/checks.sh`：通过；362 + 821/1；
- Git HEAD：`bf63c89294a5f79649a2c550331ea8987cdeab1b`；
- V3.3 SHA-256：`95bd01d104b4d1b4d53dd8b698f9f12e41f09930d01f57c624d5f2a7908ba912`；
- Blender 普通 Python 异常：无 `--python-exit-code` 时 exit 0；设置为 7 时 exit 7；
- BAT 1.23：可解析 `hantavirus_scientific_cutaway_v2.blend`，未列出外部依赖；
- Blender 后台读取试点：295 个 datablock、205 个 object、21 个 mesh；missing-files 检查为 0/0；
- 源码对照：adapter 无 tool annotations；Phase 0 三项 known-bad、strict JSON、`O_EXCL`、环境清洗、进程清理与 provenance 范围均核实。

### 10.2 未执行

- 未重新执行 `RELEASE=1` 全链路；本报告只核实其源码与已有测试结构，不把它表述为本轮动态通过；
- 未把试点资产视为可信语义 golden，也未进行科学内容正确性或人工美术评审；
- 未构造恶意 `.blend`、USD resource bomb 或真实 sandbox escape；L1 的结论基于方案可执行性、平台支持状态和公开安全证据；
- 未修改 V3.3、V3.2、仓库源码、测试或用户资产。

## 11. 最终意见

V3.3 已经拥有一套值得保留的最小信任架构，但“方案方向正确”与“规范可以执行”仍是两个不同结论。当前最重要的不是增加更多 validator、角色或证明系统，而是先消除五个 High：自包含、受支持隔离、独立测试预言机、P0 决策闭合、Warning 判定公式。

在这些问题关闭前，建议维持 V3.3 自己的保守状态声明：**MCP/Bridge 与分发链路已有较强验收，通用建模产物验收仍是设计，不得作为自动发布放行依据。**
