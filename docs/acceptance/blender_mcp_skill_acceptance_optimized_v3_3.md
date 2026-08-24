# Blender MCP / Skill 建模产物验收方案 V3.3

## 全量源码复核、GitHub 证据修正与 P0 文件级落地

> 复核日期:2026-08-24(Asia/Shanghai)
> 仓库基线:`BlenderDesign` commit `bf63c89294a5f79649a2c550331ea8987cdeab1b`,当日实测 `bash scripts/checks.sh` → `ALL CHECKS PASSED`(362 passed;821 passed + 1 skipped)
> 输入材料:V3.1(仓库内跟踪)、V3.2(工作树 untracked)、当前源码/测试/正式文档,以及三路独立 GitHub 调研(引用仓库逐条复核、上游生态实查、业界实践检索)
> 文档性质:设计与实施建议。继承 V3.2 的收敛结论,修正其三处引用错误,把 P0 细化到文件级

---

## 0. 结论

V3.2 的三项核心判断经本轮全量复核全部成立,继续作为默认方案:

1. **收敛正确**:六个条件门(R0~R5)+ 三个进程边界 + L0/L1/L2 分级,替代 V3.1 的 R-1~R10 十一门/十角色默认全量;
2. **仓库事实准确**:V3.2 对 `scene_hash`、Phase 0 wrapper、测试数量、工具清单、docs 口径矛盾的全部声明与源码逐条一致(见 §1.1);
3. **边界诚实**:MCP/Bridge 验收已闭合,通用建模产物验收仍是设计。

V3.3 相对 V3.2 的增量只有四类,不改变门禁结构:

- **修正**:三处 GitHub 引用错误(§2.1),其中钉住的 blender-asset-tracer 提交无法解析 Blender 5.x 文件,若照抄会让 L1 依赖闭包直接失效;
- **补强**:七项 V3.2 未覆盖的仓库事实(§1.2),核心是本仓对"分发链路"已实现接近 L2 的证据强度,资产链路可以直接复用其范式;
- **注证**:六门中的关键实现细节换成 2026-08 实查证据(oiiotool 三态阈值体系、`mesh.validate()` 副作用陷阱、glTF 双层验收、VLM 防欺骗对照、解析沙箱先例);
- **落地**:P0 细化到"提取哪些函数、新建哪些文件、用哪个 .blend 试点"(§6),并列出当前工作树上直接阻塞正式验收的现实问题(§9)。

### 当前可声明范围(2026-08-24 实测更新)

| 能力 | 状态 | 结论 |
|---|---|---|
| 仓库常规门禁 | implemented-and-enforced | 本日实测 `ALL CHECKS PASSED`:362 unit/contract;821 distribution + 1 条件跳过 |
| `RELEASE=1` 发行门禁 | implemented-and-enforced | 上游 `ls-remote` 精确一致、补丁重放、MCP SDK 1.28.1/2.0.0 双重放、Bandit/detect-secrets/pip-audit、双确定性构建逐字节 `cmp`(V3.2 漏列) |
| Phase 0 正式 wrapper | implemented-and-enforced | 只验证只读 Bridge 的真 Blender GUI/NFR/recovery;`exit_zero`/`reused_root`/`wrong_python` 三个 known-bad 已有 unit 回归 |
| 官方 Blender MCP 固定分发 | implemented-and-enforced | 上游为 Blender 官方实验室 `projects.blender.org/lab/blender_mcp` @ `4309a396`,10 个下游 patch,26 项工具目录 |
| 深层资产 manifest | absent | `scene_hash` 仍仅结构摘要 |
| 导出格式独立验证 / fresh-import | absent | 无通用 glTF/USD/FBX 资产门禁 |
| evaluator-owned 视觉验收 | absent | 渲染工具 ≠ 独立视觉判定 |
| 多次 clean-run 产物比较 | absent | Phase 0 NFR/recovery 不是资产确定性验证 |
| 签名审批 / attestation / 发布系统 | absent | 仅 L2 增强项 |

**正式验收当前被工作树状态阻塞**:`_require_clean_worktree` 把 untracked 文件也算脏([run_phase0_acceptance.py:87](scripts/run_phase0_acceptance.py#L87)),而工作树上有 V3.2 文档、两个 `.blend` 和一个 PNG 未跟踪。处置见 §9。

---

## 1. 仓库源码与文档事实

### 1.1 V3.2 声明逐条核验(全部属实)

| V3.2 声明 | 源码锚点 | 判定 |
|---|---|---|
| `scene_hash` 仅覆盖名称/类型/量化矩阵/RNA 类型/顶点边面数 | [scene_hash.py:13-32](bridge/core/scene_hash.py#L13) 仅 `quantize`/`object_line`/`digest` 三函数 | ✓ |
| Phase 0 wrapper 十项能力清单 | [run_phase0_acceptance.py](scripts/run_phase0_acceptance.py) 全文核对:精确 3.13.13、仓库外全新 0700 根、环境清洗、vendor 双跑、双判定、严格 JSON、进程组清理、SHA-256 汇总 | ✓ |
| 362 + 821/1 测试 | 本日实测 collect 与运行均一致 | ✓ |
| 三个只读工具 | [capabilities.py:9](server/core/capabilities.py#L9) | ✓ |
| 26 项工具目录 | `plugins/blender-mcp-installer/artifacts/manifest.json` `tools` | ✓ |
| docs 口径矛盾 | [docs/README.md:3](docs/README.md#L3) 与 [architecture.md:58](docs/architecture.md#L58) 均称历史审计只在 Git 历史,但 V3.1 被跟踪于仓库根 | ✓ |

### 1.2 V3.2 未覆盖、对方案有直接影响的七项事实

1. **上游身份**。官方分发的上游是 Blender 官方实验室仓库 `https://projects.blender.org/lab/blender_mcp.git` @ `4309a39646e6…`,bundle `1.0.0+4309a39646e6.p912ed3244261`,带 10 个下游 patch(`0001-server-hardening` … `0010-fix-python-api-member-lookup`)。"官方"不是 ahujasid 社区版;两者的安全姿态差异见 §2.3。
2. **`RELEASE=1` 门禁已接近 L2**。[checks.sh](scripts/checks.sh) 的发行模式对*分发链路*实现了:上游 `main` 与锁定 commit 的 `ls-remote` 精确匹配、从提交对象重放全部补丁、双 MCP SDK 重放上游质量门禁、Bandit/-ll、detect-secrets、三组 pip-audit、双确定性构建后五个发行物逐字节 `cmp`。资产链路的 L2 不必新发明证据哲学,复用这套"精确重建 + 逐字节比对"即可。
3. **`verify_live` 范式可直接迁移**。[verification.py:1035-](plugins/blender-mcp-installer/scripts/blender_mcp_installer/verification.py#L1035) 已实现:四层验证、工具目录与 manifest 严格**等序**比较、恰好一个安全只读探针(`get_blendfile_summary_datablocks`,probe 层强制校验工具名与空参数)、inspection 前后快照防 stale。资产 coordinator 的 expected-set equality(R5)在仓库内已有完整先例。
4. **Phase 0 层 known-bad 已有回归**。[test_phase0_acceptance.py](tests/unit/test_phase0_acceptance.py) 覆盖 `blender_exit_zero_artifact_fail`(L55)、`reused_evidence_root`(L78)、`wrong_python_patch`(L172)。V3.2 §7 夹具表中这三项属于"wrapper 层已实现,资产层需建对应物",不是从零开始。
5. **复用的具体形态**。wrapper 的可复用函数(`_normalise_new_root`、`_create_private_directory`、`_clean_environment`、严格 JSON 三件套、`_read_artifact` 骨架、`_file_evidence`、`_write_json_exclusive`、`_run_command`/`_stop_group`)全部是模块私有;而 `smoke/` 已是可导入包(wrapper 本身 `from smoke.process_registry import …`),[e2e.py](smoke/e2e.py) 另有 `_strict_json_loads`/`_sha256_file`/`_bounded_process_stdout`/`_current_provenance` 可取。P0 的第一步是提取共享模块,见 §6。
6. **正式证据的 provenance 边界**。`e2e.py::_current_provenance` 只对受跟踪的 Python/shell/TOML/`pyproject.toml`/`uv.lock`/vendored protocol 建有界哈希清单,历史 `.md` 不参与——所以把验收方案文档提交进仓库不会污染运行时 provenance,只影响 clean-worktree 判定。
7. **现成试点资产**。工作树上的 `hantavirus_scientific_cutaway_v2.blend` 是真实建模产物,可作为 P0 `blend_native` 分支的第一个 known-good 试点(`final.png` 为其渲染物);它同时是"合同应声明什么"的现实校准器(科学可视化 Profile:剖面、标注、静帧交付)。

### 1.3 文档口径修正(沿 V3.2,给出决议)

- V3.1 被跟踪于仓库根与 `docs/README.md`/`architecture.md` 的"历史只在 Git 历史"矛盾:**建议正式化**——新建 `docs/acceptance/` 收纳 V3.1/V3.2/V3.3(或最新版),从文档中心链接,并把 `docs/README.md` 的表述改为"验收方案属正式文档";若选择移出工作树,则三份都移,不留半跟踪状态。
- V3.1 页首审计基线 `102a3a2` 与其 D35~D43 所述 wrapper 实际入仓 commit `bf63c89` 不一致:V3.1 若保留,应补一行勘误;V3.3 的实现结论一律绑定 `bf63c89`。
- docs/ 下残留的 `audits/`、`handoff/`、`measurements/`、`research/`、`superpowers/` 为空目录(git 不跟踪空目录),建议顺手删除,消除"目录存在但 README 说已移除"的表面矛盾。

---

## 2. GitHub 证据复核(2026-08-24 实查)

三路调研的完整方法:逐仓库拉源码/工作流核对声明、上游生态用 `gh api` 实查、业界实践区分源码/文档/论文/转述四级证据。V3.2 引用的 7 个固定提交全部存在且均为当前 HEAD(其后零提交),引用总体可靠;需修正三处,新增若干可直接转化为夹具的假绿模式。

### 2.1 V3.2 引用的三处修正

| 原引用 | 问题 | V3.3 修正 |
|---|---|---|
| `ellmos-blender-use-mcp`:"一次一进程和超时模型很简洁" | "一次一进程"不成立:全仓无任何互斥,并发调用即并发多个 Blender。且存在 V3.2 未列的假绿:结果文件名固定(`verify_reimport_result.json`)且未传 `--python-exit-code`,脚本异常时 Blender 退 0、上一轮残留 JSON 被当作本轮结果 | 只借鉴其超时/`boundedTail` 有界日志;新增夹具 `stale_result_file`(§7);本方案结果文件一律 `O_EXCL` 新建(wrapper 已如此) |
| `helio/blender-asset-tracer@055457a` | `helio/` 是 2023-07 停更的第三方镜像;官方在 `projects.blender.org/blender/blender-asset-tracer`,活跃(v2.2.0,2026-08-13)。**钉 055457a 无法解析 Blender 5.x .blend**(large header blocks 自 v1.19 才支持) | L1 依赖闭包改钉官方 1.x 线 **v1.23**(2026-03,支持 5.0,独立解析、无需 Blender);2.x 已转为 Blender ≥5.1 内 bpy 运行,只在"已有可信 Blender 进程"场景可选 |
| `glTF-Validator`:"发现 error 时非零退出并输出 JSON report" | 属实但不完整:**仅 severity=error 影响退出码,warning 全放行**;CLI 默认 `--validate-resources` 而库 API 默认不验资源;npm 最后发布停在 2.0.0-dev.3.10(2024-10),HEAD 的 2025-12 改进未发布 | R3 门禁不得只看退出码:解析 JSON report,按冻结 policy 判定 warning;用 `--config` YAML 把关键消息升级为 error(无需 fork);已知盲区必须写进合同(见 §2.2) |

### 2.2 glTF 验收链的精确边界(P0 直接依赖)

- **已确认的 validator 假绿盲区**(均为 open issue):Draco 压缩网格的 accessor/索引检查整体跳过(#235)、KTX2/basisu 纹理载荷不验证(#177)、`KHR_animation_pointer` 验证不完整(#248——glTF-Blender-IO 的 CI 至今对文件名含 "pointer" 的用例跳过 validator);>4GB 文件误报(#244)。**P0 对策:L0 导出 preset 禁用 Draco/KTX2 压缩,合同显式记录这三个盲区**;需要压缩交付时属于 L1,补目标运行时实测。
- **生态已形成两级验收**,照抄即可:Khronos glTF-Validator 判合规(权威、演进慢),`gltf-transform`(CLI 4.4.2,2026-07-25,活跃)`validate` 是 validator 薄包装、`inspect` 出场景/网格/材质/纹理/动画清单与性能画像。P0 的 GLB 分支 = validator(合规层,error 即 Fail)+ `gltf-transform inspect`(预算层,阈值进合同)。Khronos 另有 glTF-Asset-Auditor(3D Commerce 商用检查,2026-07 仍维护)可作 L1 Marketplace Profile 参考。
- **glTF-Blender-IO 的 roundtrip 强度要看清**:其"比较"实为 validator info 摘要(11 个统计键)+ 逐案例手写属性断言,且摘要 deep-equal 只在 `--no-validate` 变体执行;CI 是单 Blender 版本(5.3 daily)非矩阵。它证明"官方导出器 + validator + 摘要级 roundtrip"是可行底线,但**不能替代本方案 R4 的字段级投影 diff**。其每周 cron 对 daily build 回归是值得抄的"上游破坏金丝雀"(P1)。

### 2.3 上游与竞品格局(方向验证)

- **ahujasid/blender-mcp**(26,217★,PyPI 1.8.4 发布于本复核日):`execute_code` 仍是裸 `exec(code, {"bpy": bpy})`,无沙箱、无产物校验;RCE 类 issue(#201/#207/#261)一律关闭不修,属文档化的设计选择;2026-06 有两个正式 CVE(GHSA-qqw9-95ww-prfm 注入、GHSA-5hr7-6m56-f3rg SSRF);2026-08 起默认开启遥测。**结论:最流行上游把验收与安全明确让位给使用者,本仓"官方 lab 上游 + 受审补丁 + 固定分发"的路线在生态里是差异化的,资产验收填的是上游明确放弃的空位。**
- **PatrykIti/blender-ai-mcp**(★54):以 "curated tools + deterministic verification" 为卖点,提供 `scene_measure_*`/`scene_assert_*` 断言与确定性 `silhouette_analysis`,口号 "vision assists interpretation, deterministic measurement provides the final truth layer"——与 V3.2 §5.2 的"像素回归为主门、VLM 只作补充"同构,方向获得独立佐证。
- **MCP 生态层面**:官方 conformance 套件已存在(`modelcontextprotocol/conformance`,按 spec 版本冻结 requirement sets、expected-failures 基线、GH Action 集成);Anthropic Directory 审核把 `readOnlyHint`/`destructiveHint` tool annotations 作为硬门槛。**协议合规与产物验收是叠加关系**:前者管"工具行为符合 MCP 语义",本方案管"工具产出的资产是否正确"——2026-08 后者在 MCP 生态仍是空白。Phase 0 三个只读工具应补齐 `readOnlyHint` 标注(一次性小改,见 §9)。

### 2.4 新增可借鉴机制(带保留意见)

| 来源 | 机制 | 采纳方式 |
|---|---|---|
| blender-agent-studio `verifyReproduction` | 把 agent 交付的生成脚本拷入干净目录,用全新 headless Blender 从零重跑,要求重生成产物再次通过全部硬门——"可脚本复现"本身作为验收项 | P1 采纳为合同可选声明 `reproducible_by_script`;比双 clean-run 更强,但仅适用于"交付物含生成脚本"的任务形态 |
| newo-ether 事务模型 | 提交时**重新验证**、不信任先前 validate 结果;原树从不就地改(副本 + 指针交换原子替换);失败事务后 `bpy.data` 指针集逐一比对防孤儿数据块 | R3"前后 source rehash"已同构;泄漏审计纳入 P1 inspector 增强。其 `rollback_failed` 分支无注入测试的教训:本方案每个 failure code 都必须有夹具(§7 原则) |
| dcc-mcp | `report_id`(uuid)+ 服务端报告留存供事后取证;全部阈值经 `rules` dict 参数化 | contract.json 天然承载参数化;evidence root 即取证留存。反面教训同样入夹具:其 pytest exit 5(零收集)当成功 → `zero_checks_collected` |
| pyblish/AYON(CVEI 四阶段,数字 order 硬排序,校验插件化;AYON 活跃至 2026-08-23) | 检查清单 = 有序插件集。pyblish 生态**没有**"冻结插件集+版本+order 哈希"的概念 | R0 合同冻结的对象精确化为:check ID 集 + 各 check 实现版本 + 执行序,三者哈希入 contract digest——这是对成熟范式的一步增强,非发明 |
| Unreal DataValidation | 单 CLI 入口、任一资产失败即非零退出码,专为 CI 设计 | `asset_accept.py` 的形态即此(V3.2 已定,保持) |
| Figma 解析沙箱 | nsjail:新 namespace、无网络、seccomp 白名单、`rlimit_fsize` 限输出、"先打开全部 fd 再接触不可信字节" | L1 沙箱规格具体化(§3);SketchUp 117 漏洞事件中 97/117 来自**内嵌图像解码**——纹理解码必须与几何解析同级隔离 |

### 2.5 安全证据更新

- **OpenUSD**:GHSA-8878-wr6v-j5cm 细节修正——恶意 `.usdc` 打开时**不报错**,直到 `UsdAttribute::Get()` 解包才触发超大分配;修复自 26.08;边界检查仅在 `PXR_PREFER_SAFETY_OVER_SPEED`(默认开)构建下生效。这是 2026-08-24 前该仓最新公告,但 2026-03 另有 4 条 high(`CrateFile::_ReadPathsImpl` 越界)、2025 年有 critical UAF-RCE。官方对不可信输入的口径只有一句:无安全选项的构建"不应在缺少沙箱或资源限制的情况下处理不可信 crate 文件"。**L1 USD 分支:钉 ≥26.08 + 默认安全构建 + 隔离进程,三者缺一不可**;usdchecker 已迁移到可注册自定义 validator 的 UsdValidation 框架(附带局限:time-sampled 属性只查第一个采样)。
- **Blender 官方图像回归现状**:`render_report.py` 已从 idiff 改用 **oiiotool**(语义不变:`--fail 0.016 --failpercent 1 --diff` 默认,按特性/设备上调),失败态分 **CRASH / NO OUTPUT / VERIFY** 三类,跨设备用厂商×后端分层 blocklist,EEVEE 默认视为跨平台非确定。V3.2 引用的 `e6d1620` 是 idiff 时代提交,更新至 main 现状。
- **`mesh.validate()` 陷阱**(R2 直接相关):返回 `True` 表示"发现**并已修改**非法数据"——语义反直觉且有副作用;详情只打印到控制台,无结构化返回;不覆盖非流形/法线朝向/UV/材质语义。用法约束见 §4 R2。
- **VLM/CLIP 评审可被欺骗有实锤**(typographic attack 自 2021 公开,2025 仍有后续):凡视觉评分参与验收,须同时渲染 evaluator-owned 的 **clay/无纹理对照版**,两版分数背离即标红;渲染永远由验收方以固定相机/设置执行,**拒收候选方自渲图**。
- **证据链选型**(L2):in-toto attestation(DSSE)+ Sigstore 已商品化——GitHub Artifact Attestations 支持给任意文件路径出 SLSA Build L2 证明,`gh attestation verify` 单命令验证;检索**未发现** SLSA/in-toto 用于 3D 资产管线的公开案例(空白而非禁区)。**C2PA 明确不采用**:规范无 glTF/USD/blend 资产类型,且元数据易剥离,对验收场景是致命弱点;仅"最终渲染图对外发布"环节可选。

---

## 3. 风险分级(沿 V3.2,两处具体化)

L0(可信本地建模)/ L1(CI 或第三方资产)/ L2(生产发布或合规)的定义、必需项与"风险等级只能运行前由外部 policy 选择"原则不变。具体化:

**L1 沙箱规格**(替代 V3.2 的"OS sandbox/独立 principal"泛称):

- macOS:独立用户或 `sandbox-exec` profile;Linux CI:nsjail/bwrap + seccomp 白名单;
- 统一要求:默认断网、只读输入挂载、专属输出目录、CPU 时间/内存/进程数/文件数/`rlimit_fsize` 硬限,超限即 Fail 不重试;
- 次序原则:先打开全部输入/输出 fd,再接触不可信字节;
- **纹理与内嵌媒体解码在沙箱内进行**,与几何解析同级(SketchUp 事件:图像解码面 97/117 > 几何面);
- validator/解析器版本属于验收合同:USD ≥26.08 且 `PXR_PREFER_SAFETY_OVER_SPEED` 构建;blender-asset-tracer 官方 1.x ≥v1.23。

**L2 证据链选型**:DSSE + Sigstore(可直接用 GitHub Artifact Attestations 承载),predicate 放合同哈希 + 检查结果 + 渲染环境指纹;不用 C2PA。其余(角色分离、透明日志、内容寻址晋级)不变。

---

## 4. 六个条件门(结构不变,注入实查证据)

R0 Contract → R1 Freeze → R2 Inspect → R3 Produce/Validate → R4 Reopen/Evidence → R5 Decide 的表格、Fail 条件、三个进程边界、Artifact Kind 条件表、八状态语义全部沿 V3.2。以下为各门的证据级修订:

**R0 Contract**:冻结对象精确化为 *check ID 集 + 各 check 实现版本 + 执行序* 三者的哈希(§2.4 pyblish 空白);阈值表新增两类必须冻结的内容——图像回归的(平台×后端)阈值键与 blocklist(§2.5 Blender 现状)、格式 validator 的 severity 覆盖配置(glTF `--config` YAML 本身入合同 digest)。

**R2 Inspect**:

- 命令模板沿 V3.1 §5.2(`--background --factory-startup --disable-autoexec --offline-mode --python-exit-code N`);
- **`mesh.validate()` 使用约束**:inspector 先在原始数据上完成 authored/evaluated manifest 计算,之后才允许调用 `validate()`(它会就地修改数据);`validate()` 返回 `True` 记为 `geometry_invalid` Fail(数据本含非法结构),而非"已修好"的 Pass;语义质量(非流形、法线朝向、UV 重叠)是独立自建检查,`validate()` 不覆盖;
- 依赖闭包工具钉官方 blender-asset-tracer 1.x v1.23(§2.1 修正)。

**R3 Produce/Validate**:

- GLB 分支两级:glTF-Validator(**解析 JSON report 判定,不以退出码为唯一信号**;error 即 Fail,warning 按冻结 policy)+ `gltf-transform inspect` 预算检查;
- L0 导出 preset 禁用 Draco/KTX2,合同记录 validator 三盲区(§2.2);
- 产出后最低限度 smoke:交付文件存在且 size>0(dcc-mcp CI 的廉价先例),在格式 validator 之前先挡"空产物"。

**R4 Reopen/Evidence**:视觉证据规格见 §5;fresh-import 投影 diff 的强度必须高于 glTF-Blender-IO 的摘要级比较(§2.2),字段级容差由合同投影定义(沿 V3.1 §9.3 有损格式规则)。

**R5 Decide**:

- 判定逻辑沿 V3.2(exit、artifact、required IDs、status、hash 全过才 0);
- 新增两条显式 Fail 通路(源自实查假绿):结果文件在子进程启动前已存在 → `stale_result_file`;expected check 集非空而实际为空 → `zero_checks_collected`(不允许"零收集视为通过");
- coordinator 输出遵循 boundedTail 原则:子进程日志保尾弃头、显式 `output_truncated` 标志,防证据文件与 LLM 上下文被兆级日志撑爆。

**状态语义**:八状态与"Required 只有 Pass 放行"不变。对照 Blender 官方三态的映射:CRASH→`Crash`,NO OUTPUT→`Missing`,VERIFY→`Fail`——不新增状态,仅说明与上游术语的对应。

---

## 5. 最小 manifest 与视觉协议(两处更新)

manifest V1 覆盖清单、量化/chunk 规则沿 V3.2 §5.1 不变。

**视觉协议更新**:

1. **渲染引擎与确定性分工**:silhouette/wire/clay 诊断图用 Workbench(确定性好、快);beauty 用 EEVEE 时必须绑定参考平台声明(GPU 厂商×后端×OS 作为阈值键),因为 Blender 官方自己就把 EEVEE 视为跨平台非确定(§2.5)。
2. **像素回归参数直接采用 Blender 官方基线**:`oiiotool ref out --fail 0.016 --failpercent 1 --diff` 起步,按合同收紧或按平台键放宽;保存 RGB/Alpha diff 图。感知第二意见用 NVIDIA FLIP(活跃、渲染领域标准),不用 ssimulacra2(压缩质量域,无渲染回归先例)。
3. **防评分欺骗**:若 L1+ 引入 VLM/CLIP 软评分,同一视角必须同时出 beauty 与 clay(无纹理)两版,分数显著背离即标红送人工;评分渲染一律 evaluator-owned,拒收候选自渲图(§2.5 typographic attack)。
4. L0 视图集(6 正交 + 2 固定斜视角 × beauty/silhouette/wire)与 `visual_unverified` 规则不变。

---

## 6. P0 落地(文件级)

### 6.1 第一步:提取共享验收库

新建 `smoke/acceptance_lib.py`(smoke/ 已是可导入包,improvement 最小),从 [run_phase0_acceptance.py](scripts/run_phase0_acceptance.py) 迁移并由其回 import,行为不变:

- 根管理:`_normalise_new_root`、`_create_private_directory`;
- 环境:`_clean_environment`(参数化 blocked 前缀);
- 严格 JSON:`_reject_json_constant`、`_finite_json_float`、`_reject_duplicate_keys`;
- 证据:`_file_evidence`、`_write_json_exclusive`;
- 进程:`_group_exists`、`_stop_group`、`_run_command`、`_require_zero`;
- `AcceptanceFailure`。

验证:`bash scripts/checks.sh` 全绿(现有 Phase 0 unit 夹具不改语义地继续通过)。这是唯一触碰既有文件的改动,其余全部新增。

### 6.2 新增文件

```text
scripts/asset_accept.py            # 薄 coordinator:参数、合同加载、子进程编排、R5 判定
acceptance/                        # 或并入 smoke/;含:
  contract_schema.py               # contract.json 的封闭校验(未知字段即 Fail)
  inspector.py                     # R2:在 clean Blender 内运行的 trusted inspector
  export_glb.py                    # R3:固定 preset 导出(禁 Draco/KTX2)
  reimport_probe.py                # R4:第二进程 fresh-import 投影提取
  render_views.py                  # R4:evaluator-owned 固定视图渲染
tests/unit/test_asset_accept.py    # coordinator 判定逻辑(monkeypatch,无真 Blender)
tests/asset_fixtures/              # known-good/known-bad .blend 生成脚本与夹具
```

约束:coordinator 不 import `bpy`;inspector/probe 是 Blender 子进程脚本,经 `--python-exit-code 1` 运行;所有产物 JSON 走共享库的严格模式与 `O_EXCL` 写入;glTF-Validator 以固定版本二进制 + `--config` 进合同。

### 6.3 试点与验证顺序

1. `hantavirus_scientific_cutaway_v2.blend` 作为第一个 known-good,跑 `blend_native` 分支(合同:科学可视化静帧 Profile);
2. 从它派生最小 known-bad 集(§7 中 L0 八项,每项一个生成脚本);
3. GLB 分支用极简 fixture(单 mesh + 单材质 + 单贴图)打通 validator + inspect + 投影 diff;
4. 全部 known-bad 以预期 failure code 非零退出后,P0 才算闭合(完成定义沿 V3.2 §8)。

P1/P2 内容沿 V3.2 §6,两处更新:依赖闭包工具版本按 §2.1 修正;新增 `reproducible_by_script` 可选门与"每周 cron 对 Blender daily build 金丝雀"(§2.4)。

---

## 7. 回归夹具(新增"现状"与四个新夹具)

| Fixture | 等级 | 预期 | 现状 |
|---|---|---|---|
| `exit_zero_success_false` | L0 | 外层非零,不被 Blender exit 0 掩盖 | wrapper 层已有([test_phase0_acceptance.py:55](tests/unit/test_phase0_acceptance.py#L55));资产层需对应物 |
| `reused_evidence_root` | L0 | 启动子进程前拒绝 | wrapper 层已有(L78);共享库迁移后直接复用 |
| `stale_result_file` **新** | L0 | 子进程启动前结果文件已存在 → 拒绝;失败路径不得读到上一轮 JSON | 无(源自 ellmos 实查假绿) |
| `zero_checks_collected` **新** | L0 | expected 集非空、实际为空 → Fail | 无(源自 dcc-mcp pytest exit 5 假绿) |
| `validator_warning_passthrough` **新** | L0 | glTF report 含 policy 关注的 warning 而退出码为 0 → 门禁仍 Fail | 无(validator 仅 error 非零) |
| `hidden_extra_object` | L0 | inventory/coverage 捕获 | 无 |
| `same_counts_changed_vertices` | L0 | structure 同、geometry digest 异 | 无 |
| `missing_texture` | L0 | dependency 或 offline reopen 失败 | 无 |
| `external_gltf_resource_missing` | L0 | 独立 validator 失败(CLI 默认 `-r` 已验资源;若走库 API 必须显式开) | 无 |
| `material_or_uv_lost_on_import` | L0 | projection diff 失败 | 无 |
| `candidate_compositor_spoof` | L0 | evaluator-owned diagnostics 不受影响 | 无 |
| `report_truncated_or_unknown_id` | L0 | expected-set equality 失败 | 无 |
| `compressed_payload_blind_spot` **新** | L1 | Draco/KTX2 资产在 L0 合同下被拒收(preset 禁用);L1 声明压缩时必须有目标运行时实测 | 无(validator #235/#177 盲区) |
| `fixed_view_billboards` | L1 | post-freeze holdout 暴露 | 无 |
| `nondeterministic_geometry` | L1 | 两 child geometry 比较失败 | 无 |
| `parser_resource_bomb` | L1 | 资源限制终止 child,父级记录明确 failure code(USD GHSA-8878 型:打开不报错、读值才爆) | 无 |

原则不变:父 harness 只有在坏样例被准确拒绝时才 Pass,不改写 child 原始 Fail。新增一条(newo-ether `rollback_failed` 无测试的教训):**coordinator 每个 failure code 至少一个夹具,无夹具的 failure code 视为未实现**。

---

## 8. 完成定义

沿 V3.2 §8 四级(方案完成 / P0-L0 / L1 / L2)不变。P0 代码与真 Blender fixture 落地前,唯一诚实结论仍是:

> 当前仓库的 MCP/Bridge 验收已闭合(含分发链路的 RELEASE 级门禁);通用建模产物验收仍是设计,不得用于自动发布放行。

---

## 9. 立即行动清单(不依赖 P0 排期)

1. **解除正式验收阻塞**:处置工作树 untracked 文件——验收方案文档按 §1.3 决议入库或移出;`.blend`/PNG 试点资产建议移入 `tests/asset_fixtures/`(P0 需要)或仓库外资产目录。在此之前 `run_phase0_acceptance.py` 必然 `dirty_worktree`。
2. **统一文档口径**:执行 §1.3 三项(docs/acceptance/ 决议、V3.1 基线勘误、删空目录)。
3. **修正 V3.2 引用**:若 V3.2 保留于仓库,附勘误指向本文 §2.1 三处修正(ellmos 单进程、BAT 来源与版本、validator 退出码语义),避免后续读者照抄失效引用。
4. **Phase 0 工具标注**:为三个只读工具补 `readOnlyHint: true` annotations(对齐 MCP 生态硬门槛,改动极小,顺带把"只读"从文档承诺升级为协议声明)。
5. **P0 启动件**:按 §6.1 提取共享库(唯一动旧代码的步骤,`checks.sh` 全绿为完成标准),随后 §6.2 全部为新增文件,不再触碰既有链路。
