# BlenderDesign 资产验收规范 V5

状态：schema v2 的 M0/M1、有限 M2 原生静态资产与有限 M3 静态 GLB 路径已接线；最终修复候选的 M2 完整门禁为 21 passed/0 failed/0 skipped，M3 真实三文件门禁为 8 passed/0 failed/0 skipped；通用资产不能自动放行。

本规范采用已经认可的资产验收整合设计。官方分发、自研 Phase 0、资产验收分别报告；有限 M3 结果不代表完整原生资产或任意 GLB 通过。V3.8 与外部 V4 是迁移输入，不是 v2 的可兼容合同。

## 合同与版本

v2 只读取 schema_version=2。旧合同作为政策草案，经重新冻结输入与核对工具后生成新 C/S 和新 run；不自动补值。所有嵌套字段封闭，C 为 canonical.digest("contract.v2", document)。运行快照深不可变。GLB 合同在计划与 R0/R5 强制核验受支持 macOS Blender 5.2 `io_scene_gltf2` 的实际内容闭包：锁定全部普通非 `__pycache__` 文件，包含动态库/目录外字节码，精确集合与逐文件摘要均须匹配；枚举错误、链接及非普通节点失败关闭。`__pycache__` 缓存不纳入源锁，其节点仍须普通；范围保持可信 L0。原生与 GLB 的 required 集分别保留 24/34 个现有检查；本页版本表与机器注册表成套更新。

## v2 合同字段表

所有对象封闭；列表项也按对应行封闭。SHA-256 为 64 位小写十六进制，数值不接受 bool/NaN/Inf。字段类型与进一步约束由 acceptance.contract.validate_document 唯一实现。

| 对象 | 完整字段与类型 |
|---|---|
| 根 | schema_version:int=2；contract_id:ID；artifact_kind:blend_native/interchange；profile:static_render；required_isolation_grade:local-trusted；input:object；checks:list；na_check_ids:list；warning_allowlist:list；tools:list；limits:object；budget:object；native:null/object；interchange:null/object；review:object；policy_baseline:null/冻结输入 ID |
| input | main:输入 ID；sha256:source.v2 有序清单摘要；files:list |
| input.files[] | id:唯一 ID；path:相对普通路径；bytes:非负整数；sha256:文件摘要 |
| checks[] | id:registry ID；impl:整数；order:整数；列表必须等于 kind 对应唯一有序注册集 |
| warning_allowlist[] | check_id:string；warning_code:string；tool_id:string；tool_version:string；只能引用 registry 声明的 warning，覆盖缺口不允许豁免 |
| tools[] | id:python/acceptance/blender/node；path:绝对路径；version:精确观察版本；sha256:真实可执行或 CLI 摘要；files:list |
| tools[].files[] | path:唯一绝对路径；bytes:非负整数；sha256:文件摘要 |
| limits | timeout_seconds:writer→正数；cpu_seconds、rss_bytes、open_files、log_bytes、file_size_bytes:正整数；RSS 是采样边界，记录峰值及采样数，不声明硬地址空间隔离 |
| budget | max_files、max_file_bytes、max_total_bytes、max_result_bytes:正整数 |
| review | required:bool；reviewer_ids:唯一 ID 列表；required_image_ids:唯一图像 ID 列表；reason:非空字符串 |
| policy_baseline 引用文件 | schema_version:int=2；kind:acceptance_policy_baseline；constraints:精确包含 tools/warning_allowlist/budget/limits/review/native/interchange 并与合同完全相同 |
| native/interchange | M1 只能 null；M2/M3 各自启用完整封闭政策，所有外部参考/配置引用已冻结输入，不接受任意 JSON 或执行命令 |

## 文件、作业与 writer 注册

静态 RunPlan 从 Contract 导出；子进程不能增加文件或 writer。每份业务输出只归一个 JobSpec；安全阻断只使实际未产生项留在 E 的 unproduced/missing 中，相关检查仍 NotTested。

| 注册项 | 固定字段或归属 |
|---|---|
| FileSpec | id、相对 path、writer、media_type、max_bytes |
| JobSpec | job_id、writer、tool_id、check_ids、input_ids、outputs、parameters、blocking_check_ids |
| request.json | controller；schema_version/run_id/attempt/nonce/job_id/writer/contract_digest/source_digest，加 input_root/inputs/output_root/outputs/parameters |
| result.json | 唯一作业 writer；原样八项身份，加 checks/artifacts/observations；不在 request.outputs 内，无自引用 |
| checks[] | id、findings、metrics；findings 项固定 code/severity/pointer/detail，metrics 只含有限 JSON scalar；无最终状态 |
| artifacts[] | id、path、bytes、sha256；controller 复制并独立重测后才接受 |
| job.json、process.log、run.json | controller；真实启动、PID、时间、退出、事故、blocked_by、工具/输入与 RSS 测量 |
| gates.json | controller；expected_gate_ids 与完整 gate 测量，作为 E 的叶子；裁决写 V |
| evidence-manifest.json（E） | controller；C、S、files、missing、unknown、unproduced；不包含自身或 V/Q/T |
| summary.json（V） | 唯一裁决结果；C/S/D/E、checks、gates、failed IDs、infra_failures、success；缺 D 为 null，不能通过 |
| review.json（Q） | controller 封装真实审阅记录；绑定 C/S/D/E/V 和实际所看图像；测试 reviewer 不授权生产签收 |
| completion.json（T） | controller 最后同步写入；绑定 C/S/D/E/V/Q 与最终 state；没有自 hash |
| delivery-receipt.json | controller；复核全部证据与 D 后复制原字节，记录 D/T、目标、长度和交付时间 |

## 执行与归约

controller 编译唯一文件/作业计划，固定 writer、输入/输出及安全阻断前置。子进程不能提供最终状态、N/A 或 warning disposition。每次结果绑定 run/attempt/nonce/job/writer/C/S。若已证实 Fail 同时存在必需 NotTested，技术结果仍为未完成并保留全部失败证据；不能把未完成检查变 N/A。错误几何阻断危险下游，安全质量失败继续可执行的诊断。

## 证据与签收

叶子证据 → E → V → Q → T。E 不引用自己、R5 结论或上层对象；R5 写 V。技术 gate 纳入 schema2 summary.success，并单列 gates/failed_gate_ids。Q 只影响业务接受，不改写技术 V。缺必需审阅时只有 E/V，返回 NEEDS_REVIEW；可选审阅缺席可继续，但任何有效明确拒收均为 REJECTED 并禁止交付，V 字节不改写；最后复测 D，写 Q/T，交付只复制已验 D 并生成 receipt。

## 事实与范围

2026-09-23 在最终修复候选、锁定 Blender、Node 与 gltf-validator 上重新执行 M3 三文件真实门禁，覆盖完整 CLI、两进程 surface 和真实 Validator 正反例，结果为 8 通过、0 失败、0 跳过；完整 Native 门禁为 21 通过、0 失败、0 跳过，并覆盖真实审阅、拒绝和交付。原候选 `98b9140` 的 M3 与 Task 2 的 M2 历史结果保留为独立证据，不替代最终候选结果。曲线、文字、动画、任意实例、任意消费者和通用资产发布均不在这些结果内；详细身份与日志见 [修复报告](../superpowers/sdd/2026-09-22-acceptance-upgrade-closeout/final-fix-report.md)。

### M2 原生静态资产实现范围与证据

`native-static-v1` 在当前锁定环境为 implemented-and-enforced；此状态绑定完整 [M2 门禁](../validation.md#独立-m2-原生资产门禁)，不代表任意平台或任意原生资产通过。2026-09-23 的实际运行使用代码基线 `117b133`、CPython 3.13.13、Blender 5.2.0 LTS / `fbe6228777e7`，19 项全部通过，未修改实现、用例、支持合同或像素阈值。

普通网格、BEVEL、TRIANGULATE、打包图像和嵌套自定义属性各有完整正例与独立可信参考。正例完成 24 个适用 check、`native.scope_supported` / `native.cross_process` / `native.reference` 三个技术 gate、135 原图及 99 对比较/差异图；未签收时仅为 NEEDS_REVIEW。exact-byte fresh reopen、同进程与跨进程渲染、错误几何/缺件/材质、未支持类型/未知平台、证据及签收身份篡改、E/V/Q/T/D 与真实交付回执均由实际 CLI 测试覆盖。诊断图继续使用零阈值，beauty 仅观察，不扩大为 EEVEE 普遍确定性承诺。

测试 reviewer 仅验证签收封装与拒绝路径，不构成用户作品的真实业务签收。本结果不替代 Phase 0、RELEASE、安装或 live 验收。命令、当前工具/代码身份与外部证据位置见 [M2 执行记录](../superpowers/plans/2026-09-08-asset-acceptance-native.md#当前执行结果2026-09-23)。

### M3 静态 GLB 实现范围与证据

M3 保留全部 34 个适用 check，并要求 `native.scope_supported`、`native.cross_process`、`native.reference`、`interchange.scope_supported`、`interchange.consumer` 五个技术 gate。未实现实际消费者、未知类型/平台、缺证据及导出无 D 都禁止技术成功。

有限 profile 为 `glb-static-surface-v1`：普通非镜像静态 MESH，单位 `scale_length=1`，显式固定导出 preset，基本 PBR 与直接 Base Color 打包 sRGB RGBA8 PNG，Linear/REPEAT/default-active-UV；collection 可省略、已支持 modifier 烘焙、未用顶点/槽可裁剪，UV 层仍保留。存在所需扩展、非默认额外 shader 输入、HDR 或外部资源时不声称支持。

Validator 的格式/资源结论、逐 node 绘制预算、表面保真和实际消费者分别报告。原始 GLB 与所有报告/图像进入 E；R5 结论只在 V；Q 绑定实际图像与 C/S/D/E/V。没有真实所需审阅时停在 NEEDS_REVIEW。测试 reviewer 不授权用户作品。

最终修复候选的 [M3 门禁](../validation.md#独立-m3-资产门禁) 完整正例的 34 个适用 check 和五个技术 gate 全部通过，三个合同 N/A 保持 N/A；实际交付复测相同 D 并生成 Q/T 与 receipt。缺消费者、缺底面、投影松散数据、真实 surface 变化，以及 Validator 缺资源、截断和资源记录篡改均由同一零跳过运行覆盖。当前 Blender 5.2 `io_scene_gltf2` 闭包按受支持应用布局完整锁定并在计划、R0、R5 复核。这里的 SHIP 只来自受控 fixture reviewer，不授权用户作品。

## 当前机器表

| Check ID | impl | writer |
|---|---:|---|
| `r0.contract.schema_closed` | 2 | `coordinator` |
| `r0.contract.tools_locked` | 2 | `coordinator` |
| `r0.contract.na_set_declared` | 1 | `coordinator` |
| `r1.input.digest_recorded` | 2 | `coordinator` |
| `r1.input.no_link_or_device` | 2 | `coordinator` |
| `r1.input.size_within_limit` | 2 | `coordinator` |
| `r2.inventory.coverage_complete` | 2 | `inspector` |
| `r2.inventory.no_nan_inf` | 1 | `inspector` |
| `r2.inventory.no_reserved_props` | 1 | `inspector` |
| `r2.geometry.validate_clean` | 2 | `inspector` |
| `r2.geometry.manifest_written` | 2 | `inspector` |
| `r2.material.slots_resolved` | 2 | `inspector` |
| `r2.dependency.all_present` | 2 | `inspector` |
| `r2.source.digest_stable` | 2 | `inspector` |
| `r3.export.file_nonempty` | 1 | `export_glb` |
| `r3.export.source_unchanged` | 1 | `export_glb` |
| `r3.validator.no_error` | 1 | `coordinator` |
| `r3.validator.resources_read` | 1 | `coordinator` |
| `r3.validator.report_complete` | 1 | `coordinator` |
| `r3.extension.none_forbidden` | 1 | `coordinator` |
| `r3.budget.within_limits` | 2 | `glb_budget` |
| `r4.reopen.offline_ok` | 2 | `reopen_probe` |
| `r4.reopen.dependencies_resolved` | 2 | `reopen_probe` |
| `r4.reopen.manifest_matches_source` | 2 | `reopen_probe` |
| `r4.import.manifest_written` | 2 | `reimport_probe` |
| `r4.projection.preserved_fields_match` | 2 | `coordinator` |
| `r4.projection.transformed_within_tolerance` | 2 | `coordinator` |
| `r4.projection.undeclared_loss` | 2 | `coordinator` |
| `r4.projection.ambiguous_object_names` | 2 | `coordinator` |
| `r4.visual.scene_not_empty` | 2 | `render_views(src)` |
| `r4.visual.all_views_rendered` | 2 | `coordinator` |
| `r4.visual.self_determinism` | 2 | `render_views(src)` |
| `r4.visual.platform_key_known` | 2 | `render_views(src)` |
| `r4.visual.source_import_match` | 2 | `coordinator` |
| `r5.evidence.manifest_closed` | 2 | `coordinator` |
| `r5.evidence.hashes_match` | 2 | `coordinator` |
| `r5.contract.digest_stable` | 2 | `coordinator` |

| Failure family | priority |
|---|---:|
| `contract_invalid` | 0 |
| `toolchain_mismatch` | 1 |
| `tool_crashed` | 2 |
| `tool_output_invalid` | 3 |
| `stale_result_file` | 4 |
| `zero_checks_collected` | 5 |
| `expected_set_mismatch` | 6 |
| `forged_not_applicable` | 7 |
| `forged_disposition` | 8 |
| `evidence_missing` | 9 |
| `evidence_truncated` | 10 |
| `hash_mismatch` | 11 |
| `isolation_insufficient` | 12 |
| `resource_limit_exceeded` | 13 |
| `runner_internal_error` | 14 |
| `check_failed` | 15 |
