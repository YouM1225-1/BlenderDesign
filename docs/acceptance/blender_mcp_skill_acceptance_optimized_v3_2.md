# Blender MCP / Skill 建模产物验收方案 V3.2

## 源码复核、GitHub 最佳实践与可落地优化版

> 复核日期：2026-08-24（Asia/Shanghai）  
> 仓库基线：`BlenderDesign` commit `bf63c89294a5f79649a2c550331ea8987cdeab1b`  
> 输入材料：附件 V2、仓库内 V3.1、当前源码/测试/正式文档，以及本报告列出的 GitHub 固定提交  
> 文档性质：设计与实施建议，不是 R0～R5 已实现的声明

---

## 0. 结论

V2/V3.1 的安全方向基本正确，但默认落地范围过大。它把三类不同问题放进了同一条 P0：

1. Blender MCP/Bridge 自身是否可靠；
2. 一个建模产物是否正确、可导出、可复现；
3. 多主体生产发布是否需要签名、证明和内容寻址晋级。

当前仓库只完成第 1 类的一部分：官方 Blender MCP 的受审分发与 Phase 0 只读通道验收。它没有实现通用资产验收，`scene_hash` 也不能代表资产语义。

推荐把默认方案收敛成六个条件门：

```text
合同冻结 → 输入冻结 → clean Blender 检查 → 条件导出/独立验证
        → fresh-import/视觉证据 → fail-closed 汇总
```

多 OS principal、DSSE/Sigstore、透明日志、独立 Publisher 和多目标引擎不是默认 P0；只有处理不可信第三方资产、多人审批或正式生产发布时才升级启用。

### 当前可声明范围

| 能力 | 状态 | 结论 |
|---|---|---|
| 仓库常规门禁 | implemented-and-enforced | 362 个 unit/contract 通过；821 个 distribution 通过、1 个条件跳过 |
| Phase 0 正式 wrapper | implemented-and-enforced | 验证只读 Bridge 的真 Blender GUI/NFR/recovery，不验证建模资产 |
| 官方 Blender MCP 固定分发 | implemented-and-enforced | 固定上游、补丁、哈希、安装/验证/回滚和 26 项工具目录 |
| 深层资产 manifest | absent | 当前 `scene_hash` 仅为结构摘要 |
| 导出格式独立验证/fresh-import 等价 | absent | 仓库没有通用 glTF/USD/FBX 资产门禁 |
| evaluator-owned 视觉验收 | absent | 现有渲染工具不等于独立视觉判定 |
| 多次 clean-run 产物比较 | absent | Phase 0 NFR/recovery 不是资产确定性验证 |
| 签名审批/attestation/发布系统 | absent | 只保留为高风险增强项 |

---

## 1. 当前仓库源码与文档事实

### 1.1 两条运行链路必须继续分开

| 链路 | 入口 | 权限 | 能证明什么 |
|---|---|---|---|
| 官方 Blender MCP | `plugins/blender-mcp-installer/` | 26 个工具，含任意 Python | 固定发行物可安装、可连接、工具契约符合仓库基线 |
| 自研 Phase 0 | `bridge/` + `server/` | 三个只读工具 | 会话授权、场景摘要、性能、恢复和审计链路正常 |

官方 MCP 适合作为 Producer/操作器；Phase 0 适合作为只读观察入口。两者都不能兼任独立资产 Verifier。

### 1.2 `scene_hash` 不能用于发布等价

`bridge/core/scene_hash.py` 与 `bridge/blender/scene_reader.py` 只覆盖当前场景对象的名称、类型、量化矩阵、数据 RNA 类型，以及 Mesh 顶点/边/面数量。以下变化可能不改变摘要：

- 顶点坐标和拓扑连接；
- 材质节点、纹理内容、UV；
- modifier/Geometry Nodes 参数；
- collection、可见性、world、相机、灯光；
- rig、FCurve、driver、cache 和外部依赖。

因此正式名称应保持 `phase0_structure_digest` 或等价表述，不得把它用于 source↔export、两次 clean-run、checkpoint 或发布 identity。

### 1.3 Phase 0 wrapper 的强项与边界

`scripts/run_phase0_acceptance.py` 已实现：

- 精确 Python `3.13.13`；
- 候选仓库外、尚不存在的 0700 evidence root；
- Git/Python/Blender/uv/dynamic-loader 环境清洗；
- vendor generate/check、clean worktree、background、GUI/NFR、kill/restart；
- 进程退出码与 JSON `success=true` 双判定；
- 0600 普通文件、重复 key、NaN/Inf、schema/mode 和大小限制；
- 进程组、registry 清理和证据 SHA-256 汇总。

它没有加载、检查或发布任意候选建模资产。最省事且正确的做法是复用其进程、证据和严格 JSON 模式，新建薄的资产 coordinator；不要把 Phase 0 wrapper 扩写成通用发布平台。

### 1.4 文档需要修正的口径

- `docs/README.md` 说工作树不保留历史审计，但仓库根实际跟踪 V3.1；两者应择一：正式化并从文档中心链接，或移回 Git 历史。
- V3.1 页首审计基线是 `102a3a2...`，但其 D35～D43 讨论的 wrapper 与 patch 在 `bf63c89...` 才进入仓库；实现结论应绑定后者。
- V3.1 多处写“沿用 V2”，而 V2 只在下载目录，不是仓库内稳定依赖；正式方案必须自包含。
- “四轮审计无未处置 Critical/High/Medium”只能描述已检查范围，不能转化为生产安全保证。

---

## 2. GitHub 源码复核

本轮只把源码、测试和真实 CI 当证据；README 声明单独标记。

### 2.1 可直接借鉴

| 仓库与固定提交 | 源码事实 | 应借鉴 |
|---|---|---|
| [dcc-mcp/dcc-mcp-blender@2bd7f7b](https://github.com/dcc-mcp/dcc-mcp-blender/tree/2bd7f7b18c5231824ef5dc1bbb8d4c87c4a1b76f) | 有 typed scene/mesh/material/animation/export-readiness 工具；E2E 在真实 Blender 中覆盖 Linux Docker、Windows 和 macOS 多版本 | 原子检查、稳定 issue code、真实 Blender host matrix |
| [ifBars/blender-agent-studio@b1cefdd](https://github.com/ifBars/blender-agent-studio/tree/b1cefdd1bcc1b7bf40423259a5c6fa154e2259f4) | `inspect_asset.py` 同时记录 authored/evaluated 统计；benchmark 使用 fresh process、固定证据和独占输出目录 | authored/evaluated 分层、独占 evidence root、fresh process |
| [newo-ether/blender-mcp@a648a9f](https://github.com/newo-ether/blender-mcp/tree/a648a9fa9a0b1467ee9c906c4c103da22ab96ee0) | 节点 patch 先在副本 dry-run，提交前检查 revision，提交后重导出比较；失败回滚并区分 `rollback_failed` | 变更前 revision、copy-on-write、提交后复验、诚实回滚状态 |
| [Khronos glTF-Validator@434283b](https://github.com/KhronosGroup/glTF-Validator/tree/434283be08a668a8fb4e437145630ddbf93b0686) | CLI 可验证嵌入/外部资源；发现 error 时非零退出并输出 JSON report | interchange 的独立格式门，而非只靠 Blender 重导入 |
| [Khronos glTF-Blender-IO@57af1b4](https://github.com/KhronosGroup/glTF-Blender-IO/tree/57af1b4e33118a4b9377b5659e3c662eab50df5d) | CI 执行 Blender 导出→glTF Validator，并做 import/export roundtrip 比较 | 导出、独立 validator、roundtrip 三段式 |
| [Blender render_report.py@e6d1620](https://github.com/blender/blender/blob/e6d1620ad53feed4a83e3b168f0a2ea74f4de6ce/tests/python/modules/render_report.py) | 使用 OIIO `--fail` + `--failpercent`；生成 RGB 与 Alpha diff | 双阈值和可查看 diff，不把单一 SSIM 当硬门 |
| [blender-asset-tracer@055457a](https://github.com/helio/blender-asset-tracer/tree/055457ab67c7d7f674ea75884e0903b4953014c1) | 专门追踪 `.blend` 外部依赖和递归引用 | 依赖闭包 inventory；最终仍需 offline reopen |

### 2.2 不能直接照搬的假绿

| 仓库 | 源码问题 | 本方案修正 |
|---|---|---|
| `dcc-mcp-blender` | 验证报告即使 `passed=false`，工具层仍返回 `skill_success`；多项预算/UV/材质问题只是 warning | transport success 与 gate pass 分开；coordinator 读取 report 并按冻结 policy 非零退出 |
| `blender-agent-studio` | inspector 写 `hard_gate_pass=false` 但脚本本身仍正常退出；公开 `validate.yml` 只跑 Bun，不启动 Blender | 外层同时要求 exit=0、artifact 合法、`hard_gate_pass=true`；真实 Blender job 独立必跑 |
| [ellmos-blender-use-mcp@1d2804a](https://github.com/ellmos-ai/ellmos-blender-use-mcp/tree/1d2804a673e2b1ec36089ca341102cf6e2effbdf) | 一次一进程和超时模型很简洁，但 FBX 外层只检查 JSON truthy，没有严格检查 `verification.ok`；CI 不运行真实 Blender | 借 stateless worker，不借判定逻辑；严格解析 schema/boolean/check IDs |
| 同生态 roundtrip | Blender 导出后再由 Blender 导入可能共享同一实现缺陷 | 格式 validator 独立；有明确目标消费者时再做目标运行时 |

### 2.3 新安全证据

[OpenUSD 2026-07-30 安全公告](https://github.com/PixarAnimationStudios/OpenUSD/security/advisories/GHSA-8878-wr6v-j5cm)说明，恶意 `.usdc` 可在读取值时触发超大内存分配；修复版本为 26.08 及以上。由此得到的工程结论不是“多加一个格式检查”，而是：任何不可信 3D parser 都必须在资源受限、无秘密、默认断网的独立进程中运行，且 validator 版本属于验收合同。

---

## 3. 优化后的风险分级

### L0：可信本地建模

适用：个人项目、输入由当前操作者生成、不自动发布。

必需：R0～R5；R1 在此等级只记录 exact bytes，不要求不同 principal 的只读 staging。可以同一 UID，不要求签名或第二个 clean-run；报告必须明确 `isolation_grade=local-trusted`。

### L1：CI 或第三方资产

适用：下载资产、自动化构建、团队共享输入。

在 L0 上增加：OS sandbox/独立 principal、CPU/内存/时间/文件数限制、断网、只读输入、两个 clean child、依赖 offline reopen、known-bad fixtures。这是第三方输入的最低目标，在 L0 基线稳定后实现。

### L2：生产发布或合规

适用：多人审批、外部客户、不可抵赖发布、生产 Publisher。

在 L1 上增加：角色分离、签名 contract/approval、DSSE/Sigstore、可信时间/透明日志、内容寻址晋级、Publisher receipt。只有此等级才需要 V3.1 的完整 attestation 链。

风险等级只能在运行前由外部 policy 选择；Producer 不能自行降级。

---

## 4. 六个条件门

| Gate | Required 动作 | Required 证据 | Fail 条件 |
|---|---|---|---|
| R0 Contract | 冻结 `artifact_kind`、Profile、export set、required check IDs、阈值、工具版本、资源上限和 N/A | `contract.json`、digest | 未知字段/ID、隐式 N/A、运行后改阈值 |
| R1 Freeze | L1/L2 将候选复制到新私有只读 staging；所有等级记录 exact bytes | 输入/依赖大小和 SHA-256 | 旧 root、链接/设备、路径逃逸、资源超限、读取竞态 |
| R2 Inspect | clean Blender、禁 autoexec、默认 offline；枚举全部 scene/collection/object/datablock 与 authored/evaluated 摘要 | source manifest、dependency report | 缺对象、NaN/Inf、依赖缺失、coverage 不完整、候选代码执行 |
| R3 Produce/Validate | 仅对适用 kind 导出/渲染；新进程、固定 preset；格式 validator 读取所有资源 | deliverable、producer log、format report | source 改变、输出空、error、report 截断、外部资源未读 |
| R4 Reopen/Evidence | 第二 clean 进程 fresh-import/离线重开；比较合同投影；生成 evaluator-owned canonical/holdout/diagnostic 图 | imported manifest、projection diff、图片与渲染设置 | 只证明“能打开”、字段超容差、缺图、candidate compositor 欺骗 |
| R5 Decide | 严格比较 expected/actual check 和 file ID；同时检查 exit、schema、`success`、hash；L1 比较两个 child | `summary.json`、evidence manifest | Missing/Crash/Truncated/NotTested、假绿、重复/未知 ID、hash 漂移 |

实现上不需要十个长期角色。默认只需三个进程边界：

```text
Producer（可写候选）
Verifier coordinator（只读输入、编排子进程、写 evidence）
Reviewer/调用方（读取冻结 evidence 后作最终决定）
```

L2 再把 Contract Authority、Attestor 和 Publisher 拆开。

### 4.1 Artifact Kind 条件

| Kind | R3 | R4 |
|---|---|---|
| `blend_native` | 不要求 interchange export | clean offline reopen + source visual |
| `interchange` | export + 独立格式 validator | fresh-import projection + source/import visual |
| `runtime_asset` | 同 interchange | 再加合同声明的 target consumer |
| `rendered_media` | render + 独立媒体解码 | 帧、色彩、编码、音轨和视觉回归；不跑 3D import |
| `fabrication` | export + 几何/单位/水密/壁厚 validator | 声明切片器时才运行 target consumer |

未适用分支必须由 R0 生成 `NotApplicableByContract`，不能靠省略记录表达。

### 4.2 最小状态语义

只保留：

```text
Pass | Fail | Warning | NotTested | NotApplicableByContract | Crash | Truncated | Missing
```

- Required 只有 `Pass` 可放行；
- `Warning` 保留原始状态，只有冻结 policy allowlist 才能另记 accepted disposition；
- `NotTested/Crash/Truncated/Missing` 必须失败；
- waiver 不进入默认方案；L2 如需要，走独立 conditional release，永远不冒充 Production Pass。

---

## 5. 最小 manifest 与视觉协议

### 5.1 V1 manifest 只覆盖放行所需字段

不要第一版就为所有 Blender datablock 构建通用 Merkle。先覆盖：

- scene、view layer、collection、object、instance 的稳定路径与可见性；
- object transform、parent、类型、data identity；
- Mesh 顶点坐标/面索引/normal/UV/material index 的量化摘要；
- modifier 名称、类型、关键参数以及 evaluated mesh 摘要；
- material slot、节点/链接摘要、纹理相对路径和 byte hash；
- armature/action/FCurve 的 applicable 摘要；
- unit、frame range、render/export preset；
- 外部依赖相对路径、大小、hash、packed 状态；
- `schema_version`、`coverage`、`unsupported_fields`。

大数组用固定 dtype、endianness、量化和 chunk 规则。只有实际出现误判后再扩 coverage。

### 5.2 视觉最小集

L0：front/back/left/right/top/perspective + 两个固定斜视角，并输出 beauty/silhouette/wire。  
L1/L2：把斜视角升级为输入冻结后派生的 holdout；动画按合同选关键帧与极值帧。

所有图由 evaluator-owned camera、light、world、OCIO 和 render setting 生成。像素回归使用 OIIO hard threshold + failing-pixel percentage，并保存 RGB/Alpha diff；SSIM/LPIPS/VLM 只作补充。没有实际打开并判读的图只能写 `visual_unverified`。

---

## 6. 最小实现顺序

### P0：先闭合 L0 资产门

1. 新建独立 `asset_accept.py` coordinator，复用 Phase 0 wrapper 的进程、私有目录、严格 JSON、超时和清理函数；不要改 Phase 0 三工具语义。
2. 先只支持 `blend_native` 与 `interchange/glb` 两种 kind。
3. 建立小型 `contract.json` schema 和 expected check/file ID 等值比较。
4. 写 trusted Blender inspector：完整 inventory、基础 authored/evaluated mesh、材质/纹理、动画和依赖摘要。
5. GLB 分支执行固定导出、glTF-Validator、fresh-import projection diff。
6. 生成固定视图、两个固定斜视角、silhouette/wire，并写 hash。
7. coordinator 只有在 exit、artifact、required IDs、status 和 hash 全部通过时返回 0。

验证方式：一个 known-good fixture 通过；下列每个 known-bad 独立 child 必须以预期 failure code 非零退出。

### P1：输入不可信时升级到 L1

- 第二 normal child 与 structure/geometry/render repeatability；
- blender-asset-tracer + 空缓存 offline reopen；
- OIIO golden/diff；
- USD、FBX、fabrication 或动画 Profile；
- 合同指定的 Unity/Unreal/Godot/Web consumer。

### P2：只为 L2 增加

- 不同 OS principal；
- signed contract/approval；
- DSSE/Sigstore 与透明日志；
- release subject、Publisher 和 post-publish receipt。

---

## 7. 必须先写的回归夹具

| Fixture | 等级 | 预期 |
|---|---|---|
| `exit_zero_success_false` | L0 | 外层非零，不能被 Blender exit 0 掩盖 |
| `reused_evidence_root` | L0 | 启动子进程前拒绝 |
| `hidden_extra_object` | L0 | inventory/coverage 捕获，不因固定列表截断 |
| `same_counts_changed_vertices` | L0 | structure 相同但 geometry digest 不同 |
| `missing_texture` | L0 | dependency 或 offline reopen 失败 |
| `external_gltf_resource_missing` | L0 | 独立 validator 失败 |
| `material_or_uv_lost_on_import` | L0 | projection diff 失败 |
| `candidate_compositor_spoof` | L0 | evaluator-owned diagnostics 不受影响 |
| `report_truncated_or_unknown_id` | L0 | expected-set equality 失败 |
| `fixed_view_billboards` | L1 | post-freeze holdout 暴露 |
| `nondeterministic_geometry` | L1 | 两个 child 的 geometry 比较失败 |
| `parser_resource_bomb` | L1 | 资源限制终止 child，父级记录明确 failure code |

父 fixture harness 只有在坏样例被准确拒绝时才 Pass；不得改写 child 的原始 Fail。

---

## 8. 完成定义

V3.2 的“方案完成”与“实现完成”必须分开：

- 本文完成：门禁无顺序矛盾，默认范围与仓库目标匹配，GitHub 证据可复核；
- P0/L0 实现完成：两种 artifact kind、known-good、全部 L0 known-bad 和真 Blender CI 通过；
- L1 完成：两个 clean child、sandbox/resource limits、依赖闭包和 offline reopen 通过；
- L2 完成：签名审批与 exact-digest Publisher 链实际 E2E 通过。

在 P0 代码和真 Blender fixture 落地前，唯一诚实的结论仍是：

> 当前仓库的 MCP/Bridge 验收已闭合；通用建模产物验收仍是设计，不得用于自动发布放行。
