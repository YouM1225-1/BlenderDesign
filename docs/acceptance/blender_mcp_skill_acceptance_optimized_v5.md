# BlenderDesign 资产验收规范 V5

状态：M0/M1 目标规范。完成 v2 CLI 和回归切换后才标为当前实现规范。

本规范采用已经认可的资产验收整合设计。官方分发、自研 Phase 0、资产验收分别报告；当前 M1 不代表完整资产通过。V3.8 与外部 V4 是迁移输入，不是 v2 的可兼容合同。

## 合同与版本

v2 只读取 schema_version=2。旧合同作为政策草案，经重新冻结输入与核对工具后生成新 C/S 和新 run；不自动补值。所有嵌套字段封闭，C 为 canonical.digest("contract.v2", document)。运行快照深不可变。原生与 GLB 的 required 集分别保留 24/34 个现有检查；本页版本表与机器注册表成套更新。

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

叶子证据 → E → V → Q → T。E 不引用自己、R5 结论或上层对象；R5 写 V。技术 gate 纳入 schema2 summary.success，并单列 gates/failed_gate_ids。Q 只影响业务接受，不改写技术 V。缺必需审阅时只有 E/V，返回 NEEDS_REVIEW；最后复测 D，写 Q/T，交付只复制已验 D 并生成 receipt。

## 事实与范围

2026-09-08 实测只覆盖所记 Blender build/platform 和探针。曲线/文字实例去重、合法拆点与未使用数据裁剪、PNG 像素/字节分离是后续实现约束，不代表 M1 worker 已完成。UV 层裁剪、完整 wire/beauty 复现、消费者与隔离按各实施阶段单独验收。

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
