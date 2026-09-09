# Blender MCP / Skill 建模产物验收方案 V3.5 全量审计报告

> 审计对象：`blender_mcp_skill_acceptance_optimized_v3_5.md`
> 对象 SHA-256：`775f93a2fcd18acdee937958b9fc92e4ce40a68dd2141d21b0af9df812e6175d`
> 仓库基线：`bf63c89294a5f79649a2c550331ea8987cdeab1b`
> 审计日期：2026-08-24（Asia/Shanghai）
> 审计方式：只读审计；未修改 V3.5 或仓库源码

## 1. 结论

V3.5 相比 V3.3/V3.4 有显著、实质性进步：33 个 check、14 个 failure family、N/A 合成规则、warning disposition、视觉参数、GLB 预算和夹具分类都已进入正文，之前关于 macOS `sandbox-exec`、正式日志截断、`mesh.validate()` 副作用、pilot oracle、GLB 计数等问题也得到有效修正。

但本轮结论仍是：

> **不接受 V3.5 对“自包含且可执行、实现者无需另行拍板即可编码 P0”的声明。**

它目前适合作为高质量的架构设计与实施 backlog，不适合作为可由不同实现者独立恢复出同一行为的验收规范。阻断原因不是“表格不够多”，而是表与表之间仍存在不可计算、互相冲突或实测错误的边界：合同摘要没有规范化算法、文件闭集没有注册表、failure code 无法表达正常资产拒收、warning 模型丢失多条消息、fresh-import 坐标被重复换轴、视觉相机可能裁切合法资产，以及新包根本不在现有仓库门禁与分发范围内。

严重度汇总：

| 严重度 | 数量 | 结论 |
|---|---:|---|
| Critical | 0 | 方案尚未实现，未发现已部署的直接破坏路径 |
| High | 9 | 阻断“可直接编码 / 判定唯一 / 可作为 P0 规范” |
| Medium | 8 | 不阻断架构方向，但会造成误分、漂移或维护债务 |
| Low | 2 | 命名和证据可复核性问题 |

在 9 项 High 解决并以反例测试闭合前，不应按 [V3.5:597](blender_mcp_skill_acceptance_optimized_v3_5.md#L597) 直接启动完整 P0 实现，更不能把 [V3.5:582](blender_mcp_skill_acceptance_optimized_v3_5.md#L582) 的“本文完成”视为已经满足。

## 2. 审计范围与验证

本轮覆盖：

- V3.5 全文 653 行，并与 V3.4、V3.3 审计报告逐项对照；
- check、状态、warning、failure family、JSON 字段、证据文件、夹具和完成定义的交叉不变量；
- 本仓库 `pyproject.toml`、`scripts/checks.sh`、Phase 0 wrapper、打包与测试范围；
- Blender 5.2.0 LTS 后台 GPU API 和 GLB export/import 实测；
- Khronos glTF 规范、glTF-Validator 报告 schema/CLI、Blender 5.2 API、C2PA 2.4、RFC 8259/8785 及相关 GitHub 仓库。

实测结果：

| 项目 | 结果 |
|---|---|
| `bash scripts/checks.sh` | `362 passed`；distribution `821 passed, 1 skipped`；`ALL CHECKS PASSED` |
| check registry | 33 项，`20 all + 11 interchange + 2 blend_native`，计数正确 |
| failure family | 14 项，计数正确 |
| Blender | `5.2.0 LTS`, commit `fbe6228777e7` |
| 后台 GPU | 未调用 `gpu.init()` 时 `gpu.platform.backend_type_get()` 抛 `SystemError`；初始化后返回 `METAL / Apple M4 / Metal API` |
| GLB 回环 | Blender 位置 `(1,2,3)` 导出 GLB 后重新导入仍为 `(1,2,3)`；再应用 V3.5 的 `(x,-z,y)` 会错误变为 `(1,-3,2)` |
| 官方 Blender MCP 上游 | `refs/heads/main = 4309a39646e644261624bfcd2bca669b343b7621`，V3.5 锚点正确 |
| glTF-Validator | `main = 434283be…`；tag `2.0.0-dev.3.10 = bcd52cc4…` |

限制：通用资产验收代码尚不存在，因此无法对不存在的 P0 实现做端到端验证；L1 隔离、L2 签名发布链也未重放。本报告审计的是规范是否足以唯一实现，以及冻结参数是否与当前上游和 Blender 5.2 行为相容。

## 3. High findings

### H-01 `contract_digest` 没有可重复的字节规范

证据：放行公式要求 R0/R5 摘要相等，[V3.5:168](blender_mcp_skill_acceptance_optimized_v3_5.md#L168) 又规定 allowlist、N/A 等进入摘要；但全文没有规定摘要输入的编码、对象键顺序、数组顺序、数字序列化、Unicode、路径规范化、域分隔前缀及是否包含 `input.path` 等细节。

影响：JSON 对象在 RFC 8259 中是无序集合；两个语义完全相同的合同可以因键序、`1`/`1.0`、转义或路径写法得到不同摘要，也可能因实现者选择不同“排序规则”而不可互操作。`r5.contract.digest_stable` 因而没有唯一 oracle。

建议验收条件：冻结摘要域和精确算法；可直接采用 [RFC 8785 JCS](https://www.rfc-editor.org/rfc/rfc8785.html) 加明确的数组排序与路径规则，或定义等价的项目内 canonical encoder，并提供同义 JSON、Unicode、浮点、`-0`、键序和跨进程 golden vectors。

### H-02 evidence file 闭集无法从规范推导

证据：放行条款要求每个 stage 的 actual/expected file ID 集严格相等，并校验所有 required 文件；但 [V3.5:378-417](blender_mcp_skill_acceptance_optimized_v3_5.md#L378) 只有开放的 `files[]` / `evidence_manifest[]` 字段，没有类似 check registry 的 file registry，也没有 `required`、stage、条件分支、稳定 ID 或路径模板。

视觉部分只写“32 张 + 差异图”，没有冻结差异图数量、何时生成、ID/路径及 source/import 前缀；第二组 24 张又明确不进入文件集。[V3.5:391](blender_mcp_skill_acceptance_optimized_v3_5.md#L391) 的 `output_truncated` 也没有进入放行公式或映射到具体 check。R0/R5 各有三个 required check，但 `result.json.stage` 只允许 R1-R4，正文仅定义 N/A 记录由 coordinator 合成，未定义正常 R0/R5 check 记录和证据的产生位置。

影响：不同实现会得到不同 expected file 集；证据日志截断可能在 `output_truncated=true` 时仍满足十条公式；R0/R5 actual check 的来源也只能由实现者猜测。

建议验收条件：新增封闭 file registry（ID、stage、required、kind、producer、path、最大大小、出现条件），明确 R0/R5 coordinator-owned 记录、差异图集合及 `output_truncated=true` 的唯一失败映射。

### H-03 failure family 无法表达正常资产拒收，也没有多失败归并规则

证据：[V3.5:336-351](blender_mcp_skill_acceptance_optimized_v3_5.md#L336) 的 14 个 family 全是合同、工具、证据或 runner 基础设施错误；`summary.success=false` 时又强制只能从该集合选一个 `failure_code`。但最常见的拒收——非法 mesh、缺材质、validator error、禁用扩展、预算超限、投影损失、像素不匹配——都只是 check 的 raw `Fail`，没有对应 family。多个 check 同时失败时也没有优先级或聚合规则。

另有直接冲突：glTF-Validator 官方 CLI 在至少一个 error 时非零退出，而 V3.5 把“外部工具非零”统一归入 `tool_crashed`；一个正常、完整产生 JSON 报告的格式拒收会被误报成工具崩溃。官方行为见 [glTF-Validator README](https://github.com/KhronosGroup/glTF-Validator)。

影响：父 harness 无法得到稳定的预期 failure code，§8 的夹具也无法唯一断言；真实缺陷与基础设施故障混为一类。

建议验收条件：区分 `check_failed` 与 runner/tool failure，允许 `failed_check_ids[]`；若仍保留单一主 `failure_code`，冻结完整优先级和同级排序。对 validator 明确“JSON 报告完整 + error exit”是完成的检查失败，不是 crash。

### H-04 单 check、单 `warning_code` 模型会丢失 validator 多消息

证据：每个 check ID 只能出现一次，每条记录只有一个 `warning_code/tool_id/tool_version`；但 glTF-Validator 的正式 schema 是 `issues.messages[]`，同一资产可同时产生多条 error/warning/info，且还带独立的 `issues.truncated`。见 [官方 validation schema](https://github.com/KhronosGroup/glTF-Validator/blob/main/docs/validation.schema.json)。

影响：一个 allowlisted warning 和一个未 allowlisted warning 同时出现时，没有规则决定保存哪一个或 effective status；复制 check ID 又会触发 expected-set mismatch。报告截断也无法证明“全部 warning 都被 allowlist”。

建议验收条件：check 记录承载封闭 `findings[]`，每条保留 code、severity、pointer/offset、tool identity 和 disposition；冻结聚合规则为“任一 error 或未接受 warning 即 Fail，报告 truncated 必 Fail”。

### H-05 所谓“三份 schema 字段冻结”仍只是字段草图，工具锁也未冻结

证据：[V3.5:353-417](blender_mcp_skill_acceptance_optimized_v3_5.md#L353) 使用 `preset:{...}`、`metrics: object`、`advisories:[...]`、`result_file:{...}` 等开放占位；未给出实际 JSON Schema、`additionalProperties`、字符串格式、数值范围、数组唯一性/顺序、hash 正则、路径约束、嵌套对象闭合规则。合同仅声明“顶层未知字段失败”。

[V3.5:419-427](blender_mcp_skill_acceptance_optimized_v3_5.md#L419) 又明确把工具版本值留到“首次实施时填死”：Blender 只有 `5.2.x`，OIIO 没有版本/来源值，`uv` 没有精确版本，`tools.sha256` 允许 null，导出 preset 也未展开。

影响：实现者仍需决定协议和供应链要点，直接否定 [V3.5:8](blender_mcp_skill_acceptance_optimized_v3_5.md#L8) 的“无需另行拍板产品决策”。

建议验收条件：在方案中纳入三份真实 schema、完整 preset/config、示例与反例；工具锁改为实际可验证的绝对版本、来源和 digest，并说明可执行文件、应用 bundle 或安装树的 hash 边界。

### H-06 深层 manifest 仍没有机器可实现的协议

证据：[V3.5:194-209](blender_mcp_skill_acceptance_optimized_v3_5.md#L194) 只列出希望覆盖的概念，没有 manifest JSON 字段表/schema、稳定路径语法、同名 datablock/collection 的消歧、实例 identity、节点/链接规范化、modifier“关键参数”注册表、unsupported 类型集合或 coverage 完整性算法。“四舍五入到 1e-6”也未定义 tie-breaking，路径和集合排序未冻结。

影响：`r2.inventory.coverage_complete`、`r2.geometry.manifest_written`、两次 clean-run comparison 和 GLB 投影的 source 侧都没有共同 oracle；两个合理实现会产生不同 manifest 和 hash。

建议验收条件：把 manifest 当成第四份正式 schema，给每类记录稳定 ID、排序、路径转义、coverage registry、量化例向量及 Blender 版本迁移规则。

### H-07 GLB 投影包含一个实测错误和两个确定性假绿路径

证据：

1. [V3.5:274](blender_mcp_skill_acceptance_optimized_v3_5.md#L274) 要求在 fresh-import 后对 import 侧再应用 `(x,-z,y)`。Blender exporter/importer 已在文件边界完成 Z-up/Y-up 转换；本机 Blender 5.2 实测 `(1,2,3)` 回导后仍是 `(1,2,3)`，V3.5 的额外换轴会把合法回环误拒为 `(1,-3,2)`。glTF 文件自身的 Y-up 规则见 [Khronos glTF 2.0 §3.4](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units)。
2. [V3.5:279](blender_mcp_skill_acceptance_optimized_v3_5.md#L279) 在 PNG 重编码时只比较尺寸和通道；两张内容完全不同但同尺寸同通道的纹理会假绿。
3. [V3.5:280](blender_mcp_skill_acceptance_optimized_v3_5.md#L280) 直接删除 `.001` 后缀会把合法的 `Cube` 与 `Cube.001` 折叠为同一对象；glTF 规范也明确 `name` 不保证唯一。

此外，`projection` 数组保存的是 13 行中文描述而不是稳定 field ID，机器无法可靠验证“并集恰好等于 13 行”。

影响：合法资产误拒、纹理替换假绿、对象错配，直接破坏核心 interchange 门禁。

建议验收条件：比较两个 Blender-space manifest，或在 raw glTF 边界只转换一次；纹理按冻结 colorspace 解码后比较像素/规范化 hash；对象使用稳定导出 ID/extras 或检测名称归一化碰撞；为 13 项提供稳定英文 ID。

### H-08 视觉协议会错视角、裁切合法资产，并遗漏非 mesh 可见内容

证据：

- 表头把 `dir` 定义为“相机朝向目标”，公式却把相机放在 `C + dir*d` 再看向 C，实际 view vector 是 `-dir`；front/back/top 的语义与位置相反。
- 50 mm 焦距、36 mm 水平传感器的水平 FOV 约 `39.598°`。要容纳半径为 r 的包围球，中心距离至少 `r/sin(FOV/2) ≈ 2.952r`，冻结的 `2.6r` 在没有 margin 前就会裁切。
- [V3.5:225](blender_mcp_skill_acceptance_optimized_v3_5.md#L225) 只用可见 mesh 求 bounds，但方案自己的 pilot 包含 Curve/Font，curve-only 或 font-only 资产会被当成空场景，混合资产的非 mesh 部分可能落在画面外。
- beauty 强制黑色、strength 0 的 world，又没有冻结 evaluator-owned lights；EEVEE beauty 可成为黑图，证据失去审阅价值。

`all_views_rendered` 只验证文件存在/可读，不验证物体是否完整落入画面，所以裁切仍可能全绿。

影响：视觉证据并不稳定代表完整资产，top/oblique 语义漂移，合法资产可被误拒或缺陷被漏看。

建议验收条件：统一 `target_to_camera` 或 `camera_to_target` 语义；用 FOV、aspect 和 margin 求 fit distance；bounds 覆盖全部 evaluated renderable geometry/instances；冻结 clip planes 和 evaluator lights，并增加 frame occupancy/coverage 断言。

### H-09 “P0 不修改既有文件”与仓库门禁、分发事实冲突

证据：[V3.5:470](blender_mcp_skill_acceptance_optimized_v3_5.md#L470) 和 [V3.5:597](blender_mcp_skill_acceptance_optimized_v3_5.md#L597) 要求只新增文件；但当前：

- `pyproject.toml:27-37` 的 wheel/sdist 和 mypy 只包含 `protocol/bridge/server`；
- `scripts/checks.sh:9-16,37-44` 的 bytecode、ruff、mypy 范围没有 `acceptance/`；
- `scripts/checks.sh:65-70` 的 sdist 白名单会排除它；
- `scripts/checks.sh:133-135` 的 RELEASE Bandit 范围也没有 `acceptance/`；
- `[project.scripts]` 只有 `blender-codex-server`，没有资产验收 CLI。

影响：新增的安全敏感验收代码可以完全不被 ruff/mypy/Bandit 和分发测试覆盖，`checks.sh` 仍然全绿；安装后的 wheel/sdist 也没有 `acceptance` 包或 `asset_accept` 入口。要真正集成，必然需要修改既有配置。

建议验收条件：明确该工具是 repo-only 还是发行能力；无论哪种，最小修改现有门禁，使 `acceptance/` 被 lint/type/security/test 覆盖。若要分发，再加入 package、sdist 和 console script。删除“零既有文件修改”这一完成约束不能由新文件绕过。

## 4. Medium findings

### M-01 AcceptedWarning 的字段承诺与 schema 不一致

[V3.5:144](blender_mcp_skill_acceptance_optimized_v3_5.md#L144) 和正向夹具要求 `accepted=true`，但 result/summary check 字段都没有 `accepted`。summary 还丢弃了 result 中的 `tool_id/tool_version`，审阅方无法仅从冻结 summary 重算四元组 allowlist。应明确 `accepted` 是序列化字段还是由 disposition 派生，并保留完整来源元组。

### M-02 自研 warning `non_triangle_primitive` 未在注册表声明

[V3.5:464](blender_mcp_skill_acceptance_optimized_v3_5.md#L464) 会产生 `non_triangle_primitive`，但 `r3.budget.within_limits` 在 [V3.5:315](blender_mcp_skill_acceptance_optimized_v3_5.md#L315) 只声明 `budget_near_limit`。按 §2.5，自研未声明 warning 永远不可 allowlist。这违反“warning code 封闭集”，也会让同一检查的行为与表不一致。

### M-03 后台 GPU 探测缺少初始化，platform key 也没有规范化

[V3.5:245](blender_mcp_skill_acceptance_optimized_v3_5.md#L245) 直接调用 `gpu.platform.*`。Blender 5.2 官方 API 明确 `gpu.init()` 用于 background 初始化；本机不初始化会抛 `SystemError`，初始化后 vendor 返回 `Apple M4`，而文档示例使用 `apple`，却没有 lowercase、空格、型号裁剪或转义规则。见 [Blender 5.2 GPU API](https://docs.blender.org/api/5.2/gpu.html)。这会把支持平台误判为 unknown 或让合同键不可跨机器复用。

### M-04 夹具表没有覆盖自己声明的全部 failure family

§8.1 要求 14 个 family 各至少一个夹具，但 §8.3 没有明确覆盖 `toolchain_mismatch`、`tool_crashed`、`evidence_missing`、`hash_mismatch`、`runner_internal_error`；`tool_output_invalid` 也只有可能的间接覆盖，没有 family 映射列。夹具名与预期中还经常只写“Fail”而非唯一 code。应增加 `expected_failure_code` 列并用机械检查验证 14/14 覆盖。

### M-05 C2PA 排除结论可以保留，但技术论证仍不成立

[V3.5:75](blender_mcp_skill_acceptance_optimized_v3_5.md#L75) 认为 sidecar 缺失无法区分“从未验收/被剥离”，因此不满足“缺失即失败”。如果合同规定 manifest 必须存在，这两种情况都应直接失败，根本不需要区分。当前 [C2PA 2.4](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html) 继续支持 external manifests，还增加 repository receipt assertion。C2PA 不适合作为 P0 默认载体可以是成本/生态选择，但不能用该逻辑证明其无法 fail-closed。

### M-06 复制约 150 行安全原语制造双份真相

[V3.5:472](blender_mcp_skill_acceptance_optimized_v3_5.md#L472) 计划复制环境清洗、O_EXCL 写入、进程组终止、严格 JSON 等安全敏感逻辑，并依赖人工“与源同步检查”，到 P1 才共享。两条链路“生命周期不同”恰恰意味着复制后更容易漂移。最小方案是先把确有两个消费者的极小稳定原语提成公共模块，或暂时从已测试模块显式 import；不应复制后再承诺未来重构。

### M-07 L1 仍是选项列表，不是可执行隔离规范

Linux 写成 `nsjail/bwrap + seccomp`，macOS 写成独立用户或 VM/远程 runner；没有冻结实际 runner、mount namespace、seccomp profile、网络证明、UID/权限验证和 `achieved_isolation_grade` 的测量算法。它不阻断 L0 P0，但 [V3.5:584](blender_mcp_skill_acceptance_optimized_v3_5.md#L584) 的 L1 完成定义仍不能据本文直接实现。

### M-08 contract authority 与 policy 下限没有落点

文档只明确风险等级由 external policy 选择，没有说明谁提供/拥有完整 contract。warning allowlist、视觉阈值、预算、`projection.lost` 和 blocklist 都可显著放宽拒收边界；[V3.5:243](blender_mcp_skill_acceptance_optimized_v3_5.md#L243) 甚至允许按平台放宽，但没有不可突破的 policy baseline。对于 L1 第三方资产，必须明确合同由 verifier/caller 可信侧产生，候选不能携带或覆盖这些字段；否则“合同摘要稳定”只证明弱合同没有被运行中篡改，不证明合同足够强。

## 5. Low findings

### L-01 外部证据段违反了自己的锚定规则

[V3.5:559](blender_mcp_skill_acceptance_optimized_v3_5.md#L559) 要求 commit/advisory/release ID，但 [V3.5:574-576](blender_mcp_skill_acceptance_optimized_v3_5.md#L574) 对多个 GitHub 仓库、两个 CVE、反例项目和“可借鉴”项目没有给 commit、issue/CVE ID 或链接。本轮抽查确认 unrestricted `exec`、确定性测量方向和两个 2026 CVE 的大方向属实，但文档自身不可复核。应给固定链接/ID，例如 [CVE-2026-10661](https://nvd.nist.gov/vuln/detail/CVE-2026-10661)、[CVE-2026-10688](https://nvd.nist.gov/vuln/detail/CVE-2026-10688) 和相关源码 commit。

### L-02 `r4.visual.platform_key_unknown` 的 check 命名与 Pass 语义相反

在已知平台上，这个 required check 应 raw Pass，但 ID 字面意思是“平台键未知”。虽然不必然造成算法错误，却会让报告和查询容易误读。正向谓词式 ID（如 `platform_key_known`）更符合其他 registry 项。

## 6. 已确认正确或明显改善的部分

以下内容经源码、计数或上游资料核验，可保留为 V3.5 的有效成果：

- 当前仓库基线、工作树未跟踪清单、`checks.sh` 测试数量及 `ALL CHECKS PASSED` 结论准确；
- 官方 Blender MCP 的 `4309a396…` 上游 commit、10 个 downstream patch、26 个工具目录与本仓 manifest 相符；
- 33 个 check、14 个 family、`20 + 11 + 2` kind 分解及 L0/L1 fixture 数量算术正确；
- N/A 由 coordinator 按 registry + kind 推导并做双向集合校验，解决了此前省略/伪造问题；
- raw status、disposition、effective status 分层方向正确，advisory 不进入硬门的边界清楚；
- macOS 不再把 `sandbox-exec` 当作受支持安全边界，也不再允许 L1 静默降级；
- 正式日志与 UI bounded tail 已分离，`mesh.validate()` 改在 disposable copy 上执行；
- generator/handcrafted/synthetic 分类、人工审阅 expected、禁止被测实现自生 golden，方向正确；
- GLB accessor count 按 primitive mode 换算、glTF image JSON 本身无宽高字段的修正正确；
- evaluator-owned 诊断渲染、fresh-import、外部 validator、确定性分层和“视觉模型不覆盖确定性 truth”符合相关仓库的良好实践。

## 7. 与前次审计的关系

V3.5 确实关闭了 V3.3 报告中的多数具体事实错误和未决选项，但“21/21 处置”不能等同于“规范闭合”。本轮出现的是更深一层的组合问题：

| 前次主题 | V3.5 状态 |
|---|---|
| macOS 隔离、pilot oracle、正式日志、`mesh.validate()`、计数/术语 | 已实质闭合 |
| check/failure/schema 自包含 | 部分闭合；有表，但摘要、文件集、正常失败和实际 schema 仍不闭合 |
| warning allowlist | 部分闭合；四元组已定义，但多 warning cardinality 未闭合 |
| GLB 投影与视觉参数 | 从“缺失”变成“已冻结但含错误”，必须以反例修正 |
| 包结构与复用 | 选项已定，但与仓库门禁/分发冲突，复制原语仍有漂移债务 |
| C2PA | 结论可接受，技术理由仍未修正 |

因此，本报告不推翻 V3.5 的整体架构方向；它否定的是“已经达到单文档、唯一判定、可直接编码”的完成声明。

## 8. 建议的审计退出条件

这不是对方案的修改，而是下次复审应满足的可验证门槛：

1. 9 项 High 每项至少有一个最小反例测试，且不同实现者不需口头约定即可得到同一结果；
2. 真实 schema、digest golden vectors、check registry、file registry、failure precedence 和 warning findings schema 全部可机械校验；
3. Blender 5.2 轴向回环、纹理替换、`.001` 名称碰撞、curve/font-only、相机边界球、GPU background 初始化均有 E2E fixture；
4. 新包被当前 ruff/mypy/Bandit/pytest 范围实际覆盖，repo-only/分发边界明确；
5. 14 个 failure family 与正向 warning/N/A 分支都能从 fixture 表机械证明覆盖；
6. 再次完整运行 `scripts/checks.sh` 和 `ASSET_E2E=1`，报告记录工具锁、命令、退出码及证据 hash。

在此之前，最稳妥的状态标签仍应是：

> **architecture-ready / implementation-spec-not-ready / release-gate-not-implemented**
