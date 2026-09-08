# 资产验收整合设计：可信核心、原生闭环与 GLB 投影

状态：整体设计已于 2026-09-08 获用户认可；本文为待实施设计，尚未改变运行时行为。本文整合源码审计、外部 V4 优化方案与同日 Blender 实测。与[安装升级清理设计](2026-09-08-installer-upgrade-cleanup-design.md)独立实施、独立验收。

## 1. 决策、范围与成功标准

沿用 `acceptance/` 的 R0–R5、检查 ID、失败优先级和既有安全原语，先修可信判定边界，再让一个明确支持范围内的真实原生资产完整通过，最后接通 GLB。所有必需检查均须真实执行；不能通过减少 required 集合、合成 Pass 或放宽阈值制造成功。

三条链各证明自己的对象：官方 MCP 分发链证明安装版本与现场可用性；自研 Phase 0 证明只读协议及运行行为；本设计证明冻结资产满足合同。安装成功、结构 `scene_hash` 一致或 Phase 0 通过，均不能替代资产验收。

首发支持 `blend_native + static_render + local-trusted`：用户认可来源、单场景与固定帧、静态 MESH、明确枚举的静态 modifier、Principled BSDF 常量及已打包图像。首个正向资产可不用 modifier 和图像，以减少接线变量；支持清单仍须明确到类型和字段。链接库、外部缓存、动画、驱动、任意程序材质、第三方不可信文件和其他用途暂不接收。范围外返回未验证及具体能力缺口；不能伪造空几何，也不能宣称所有曲线、文字或实例已支持。

本设计的成功标准是：好资产完整通过；实际缺件、变换错误、使用中的材质或表面丢失被拒；缺证据和工具故障被识别为未验证；交付字节与被验字节相同。以误拒、漏拒、运行耗时和维护成本评估改进，不以测试数量或模型评分代替这些结果。

## 2. 证据基线与当前缺口

审计基线为仓库提交 `97abbad7f43fbc4b16de45246ee9b196d1527ba0`。当前入口仍是 [V3.8](../../acceptance/blender_mcp_skill_acceptance_optimized_v3_8.md)，[合同加载器](../../../acceptance/contract.py)只接受 schema v1。外部 V4 与本文不会自动升级现行接口。

| 已核对对象 | 当前事实 | 本次设计的处理 |
|---|---|---|
| [检查注册表](../../../acceptance/check_registry.py)与 [CLI](../../../scripts/asset_accept.py) | 37 项；仅 R0/R1/R5 九项接线。native 24 项适用、15 项 NotTested；interchange 34 项适用、25 项 NotTested | 保留失败关闭；以完整阶段接线替换 NotTested |
| R0/R1 | 工具存在不等于真实身份；嵌套合同不完整；实读摘要未与声明对账 | 深 schema、实测工具锁、冻结包身份核对 |
| R5 | CLI 传空 manifest、空文件集；局部函数不承担完整枚举与测量 | 注册表生成文件计划，controller 实际读取并封装 |
| Contract / decide | frozen dataclass 内有可变字典；矛盾内部 outcome 可通过；N/A 可掩盖运行事故 | 深层不可变快照、内部不变量复核、独立事故累积 |
| provenance | 缺少实际导入的 `smoke/process_registry.py` | 显式可信代码闭包 |
| 测试 | 上述基线完整检查为主测试 599 passed、分发测试 824 passed/1 skipped；专项 167 项包含在主测试中 | 是历史核对结果，不是目标闭环已经通过的证明 |

同日实测使用 Blender 5.2.0 LTS，build `fbe6228777e7`，macOS/arm64，Workbench METAL / Apple M4；它是有限平台的独立探针，尚未接入 acceptance worker。

| 实测 | 已观察结果 | 冻结为实施约束 |
|---|---|---|
| 求值可见性 | 曲线、文字和集合实例的 evaluated `visible_get()` 可为 false，但仍导出；集合源 original 也可能为 false | 不用任一单独 visible_get 谓词定义交付集合 |
| 求值计数 | CURVE/FONT 与生成 MESH 有双记录，实际各导出一个 mesh node | 通过 occurrence 与几何关联去重 |
| 合法表示变化 | 立方体 8→24 顶点；另一夹具 12→3 顶点、2→1 材质槽 | 允许已声明的拆点和未使用数据裁剪，比较实际表面 |
| UV | 该夹具 2→2 层，名称变化 | UV 裁剪仍是条件化风险，未复现即不写成已证实 |
| PNG | 同进程 16 对 clay/silhouette 像素一致，5 对文件 hash 不同；新进程两种 pass 像素一致而 hash 不同 | 文件身份与解码像素比较分开，保留两组原图 |
| 退化/验证 | 零尺度对象仍存在但 bounds 为零；mesh 副本 validate 修正了退化面 | 分开对象存在、几何存在、有限 bounds、非退化；修正即原数据不干净 |

材料身份供追溯，证据文件保留在仓库外；不依赖某台机器的绝对路径：

| 材料 | SHA-256 |
|---|---|
| 外部 `blender_mcp_skill_acceptance_blenderdesign_v4.md` | `3f97ef4a806234857c14b395abab7bfd741260aede2993f68ec2bb9a78ea20ba` |
| 2026-09-08 `验证报告.md` | `d95e26167ee6f77d87e8906277c66f9ec1e6ee362a966508e975a3d1ebbf8167` |
| 同轮 `evidence-files.sha256` | `7a7befed31d81b762fa8226f58dc61350d680f33663cf34a3263dba5b09a8deb` |

本轮未完成 wire/beauty 的完整重复性、全部 24 对诊断重复图、Khronos Validator、指定消费者、隔离攻击验证、正式签收或发布链。11 组 Python 诊断复现和局部函数反例也不等于已证明正常 CLI 可被外部 JSON 绕过。

## 3. 版本与权威迁移

采取明确切换，不长期维护两套放行算法。M0 形成唯一的资产验收 V5 规范及 schema v2 字段表；外部 V4 仅作已审计输入，V3.8 保留为历史版本。规范、合同/result/summary 的 schema、check/file/writer 注册和文档入口在对应实现阶段成套更新。本文本次入仓不提前把 V3.8 标为已被运行时替代。

v2 入口明确拒绝 v1 合同和结果，不静默补工具、摘要、阈值或 N/A。旧合同只能作为政策草案，重新冻结输入、核对工具、生成 v2 新合同与新 run；旧证据保留。旧消费者不理解 v2 时明确报不支持。`summary.success` 继续只表示技术判定，上层交付状态单独记录。

保持语义未变的 check ID/impl；改变规则的检查提升 impl，并同步机器表、规范表、夹具和合同期望。至少涵盖深 schema/tools、输入对账、覆盖/几何 manifest、投影比较、非空判定、视觉文件/重复性和 R5 闭包。N/A 与 outcome 归约语义由 v2 协议统一约束。M0 必须给出逐 ID 的版本差异表；不允许实施时在旧 impl 下改变含义。

不增加通用插件框架、任务平台、全环境依赖扫描器或默认多代理审核系统。仅在检查需要时引入锁定的 Blender、validator 和图像比较工具；不要求静态原生资产运行 GLB 或游戏引擎分支。

## 4. 输入、合同与真实工具锁

处理顺序为：需求政策草案 → 安全接收并冻结 S → 编译执行合同 C 和不可变运行计划 → R0/R1 → worker。合同不能先签未知摘要再补写。

接收器把候选和必要依赖流式复制到独占新目录，限制总量、单文件大小和文件数，并从安全打开的同一文件描述符记录类型、长度、摘要及前后身份。原路径仅作来源信息，worker 只读冻结包。源码根、冻结包根、scratch、可信证据根互不重叠；包内引用必须是无歧义的相对路径。拒绝链接、设备、路径逃逸和读取期间替换；受管根的父链需显式验证，不能把叶子 `O_NOFOLLOW` 当作全路径保护。

L0 先限已打包或无需 Blender 解析即可列明的依赖。依赖发现若要打开第三方 `.blend`，隔离必须在首次解析前生效；L1 未实现时不接收该类输入。L0 的私有目录、关闭自动执行、摘要复核防止误用与检测变化，不声称能阻挡同一用户权限的恶意进程。

合同编译后只暴露深层不可变的值对象、元组和只读映射；执行不保留共享的可变 raw 字典。C 使用 v2 域分离与明确 canonical 规则；R5 核对执行快照身份、输入合同字节及其摘要。canonical 用标准向量和独立实现差分验证；当前并无已证实的合法向量算法错误。

| 合同/计划内容 | 必须冻结的约束 |
|---|---|
| schema | 所有嵌套字段封闭、精确类型、有限数、单位、范围、唯一 ID 与跨字段一致性；bool 不当数值 |
| 输入 | S 的成员清单、长度、完整 SHA-256、依赖引用和包根策略；R1 实测对账 |
| 检查 | 从 kind/profile 派生完整 required/N/A；不由 worker 或合同任意缩小；每项绑定 impl/writer |
| 工具 | 必需集由计划推导；工具 ID 不重复；真实可执行文件、版本/build、脚本/包内容身份、配置与启动参数匹配 |
| 比较政策 | 阈值、量纲、reference_scale、比较器版本、平台、参考图、投影字段、允许损失和 warning allowlist |
| 文件计划 | 文件 ID、唯一 writer、固定相对路径、媒体/schema 类型、大小与解析上限、条件展开式 |
| 资源与签收 | 作业时限、内存/文件/图像预算、目标消费者要求、审阅主体与必需签收项 |

validator 配置、参考图、导出 preset 和其他影响裁决的外部文件均成为冻结内容引用，不能只绑定路径字符串。工具锁不能仅散列 Python/Node 二进制而忽略实际脚本或包；大型应用绑定经审核的分发身份、build 和受支持模块清单。

provenance 最小显式闭包覆盖 `acceptance/`、CLI、实际共享依赖 [process_registry](../../../smoke/process_registry.py)、worker/比较器代码及锁定应用身份。完整 SHA-256 用于比较，短摘要仅展示。允许政策放宽的字段受部署方 policy baseline 约束；L0 缺 baseline 必须留痕，L1/L2 缺失则拒绝。失败后不得自动放宽阈值；政策改变必须生成新合同、新 run。

## 5. controller、worker 与判定责任

controller 从不可变计划启动作业，绑定 `run_id + attempt + nonce + writer + C + S`、专属 scratch 和允许输出集合。每个 worker 只提供白名单 findings、metrics、工具观测和文件描述；不能提交最终 success、effective 状态、允许 warning 的 disposition 或自授 N/A。

controller 有界读取完整 result，拒绝重复键、未知保留字段、错误类型、未知/重复 check、越权 writer、旧 attempt、迟到结果及缺失输出。日志/result 超限即截断事故，不能截去尾部后接受。关闭并回收作业及其后代后才接收可信证据；L0 只承诺既有进程组边界，更强进程逃逸防护属于 L1。

继续以 [decide.py](../../../acceptance/decide.py)作为唯一归约位置。即使对象来自内部调用，也复核 ID/stage、状态枚举、tool identity、findings/disposition、截断、raw/effective 和 accepted 的一致性。controller 的退出码、超时、崩溃、泄漏、缺失、截断和身份错配独立累积；先按基础设施优先级判定，再检查资产失败，不因某个 N/A 分支丢失事故。

N/A 仅由计划对未调度的不适用检查合成，不带工具、运行 findings 或截断。误调度的不适用作业及其事故仍阻断。重试创建新 attempt，不修改旧失败证据。

| 上层状态 | 必要条件 |
|---|---|
| UNVERIFIED | 工具、隔离或证据故障；必需项缺失、未运行、未实现或不支持；报告具体原因 |
| REJECTED | 所需检查完成，至少一个实际资产检查硬失败或 warning 未获合同允许 |
| NEEDS_REVIEW | 技术通过，合同所需审阅尚未完成 |
| SHIP / SHIP_WITH_NOTES | 技术通过、所需审阅通过、T 完成且 D 复测一致；后者仅用于合同接受且留痕的 warning |

技术失败与运行事故可同时保留在证据中；主 failure_code 沿用既有优先级。技术通过后业务审阅明确拒收也输出 REJECTED，原因属于审阅层，不改写技术 summary。评分不能抵消 required check；`summary.success=true` 本身不是交付许可。

混合状态明确如下：没有基础设施事故时，实际 `Fail/Warning + NotTested` 保留技术 `success=false、failure_code=check_failed` 和实际失败 ID，但因检查不完整，上层为 UNVERIFIED；只有 NotTested 而没有实际检查失败时，技术码继续为 `runner_internal_error`。若已发现的坏数据使下游无法安全执行，记录 `blocked_by` 指向原失败，并以同一混合规则报告“已发现拒收理由，剩余检查未验证”，不能声称完整验收已执行。发生基础设施事故时主码仍按既有优先级选择。上层状态必须检查完整性，不能只从 failure_code 推导。

## 6. 文件注册、真实 R5 与无环封装

固定写入方向为 **叶子证据 → E → V → Q → T**。C、S、D 是独立输入身份，由后续层引用。

| 对象 | 内容及引用 | 排除项 |
|---|---|---|
| C | 冻结执行合同规范化摘要 | 运行后结果 |
| S | 冻结源包成员身份 | 合同、报告 |
| D | 实际待交付单文件字节，或显式声明的包清单与归档字节身份 | 验证后重新导出的版本 |
| E | payload manifest 字节摘要；逐项引用叶子证据 | 自身、summary、R5 结论、签收、完成记录 |
| V | 最终技术 summary 字节摘要，含全部归约结果和 R5 结论，引用 C/S/D/E | V 自己、尚未生成的 Q/T |
| Q | 审阅记录，绑定 C/S/D/E/V 与审阅政策、结论、主体 | T；无人工要求也显式记录政策为何不需要 |
| T | 完成记录，引用已形成的 C/S/D/E/V/Q，包含上层状态 | 自身及之后的交付 receipt |

同一 `.blend` 原样交付时，D 等于 S 中主文件字节身份；若要修包、重打包或重导出，先形成新 D 再验，不在验后制作替代品。

| 文件族 | 归属和展开 |
|---|---|
| inspector result、authored/evaluated/依赖 manifest | `inspector`，计划固定的 R2 文件 |
| GLB 与 export result | `export_glb`；仅 interchange |
| validator 原始完整报告与资源读取记录、budget result | controller/`glb_budget`；仅 interchange，各文件唯一归属 |
| reopen 或 fresh-import result、manifest | `reopen_probe` 或 `reimport_probe`，由 kind 唯一选择 |
| 首次图像、重复图像、render result | 对应 src/import render 作业；按 experiment/side/view/pass/repetition 展开，每个 experiment 绑定独立 job/进程身份，不复用 check writer |
| 比较器原始输出、差异图与 metrics | controller 调用锁定比较器后验证接收；每个比较项都有输出与判读记录 |
| job 退出/超时/日志、工具与输入测量记录 | controller；每个已计划作业展开，记录其是否实际启动 |
| manifest、summary、review、completion | 上层控制文件；按拓扑验证存在性与引用，排除在 payload 集之外 |

check writer 与文件 writer 分开登记。沿用 source render 检查唯一归属；重复/import render 不重复发布相同 check ID，controller 根据这些作业证据归约结果。R5 的结论只写 V，不产生一个再被 E 引用的 R5 result。必需文件由一次编译生成，不在多个模块分别硬编码数量。

controller 停止所有 writer，核对文件集合、ID、路径、writer、类型、大小与内容，再复制到可信 payload；随后重新枚举并测量已接收文件，生成 E。R5 以真实测量判断闭包与摘要，缺实测值即未完成。成功路径要求叶子集合精确相等；失败路径也可封装实际诊断和缺失清单，但 summary 必须失败，不能伪造缺失文件或成功的 R5。

写出 V 后执行所需审阅形成 Q，最后形成 T；受管输出用独占创建、文件与父目录同步，并最后原子写入完成标记。中断时留不完整目录，恢复须逐层重验，不能仅凭旧 summary 恢复为 SHIP。交付前重新测量 D，交付 receipt 记录实际 D/T。L0 的本地记录只提供本地可信链；独立签名和受保护发布基础设施按 L2 需求另建。

## 7. R2、原生重开与几何覆盖

R2 同时形成 authored inventory、evaluated geometry、dependency manifest、coverage 和 scope。合同固定 scene/view layer/frame、完整资产、渲染范围和交付投影范围；任何排除对象都记录原因和政策，必需部件不能靠缩小范围消失。

内部 collection path 用字符串数组，身份用结构化元组，不用 `/` 拼接产生歧义。occurrence 至少包含原对象身份、instancer 链、求值几何引用和 world matrix；同源多个实例允许共享 source UID。稳定排序和匹配有多个解时明确报歧义，不用名字猜测。曲线/文字与其求值 MESH 合为同一个可交付 occurrence，辅助 EMPTY 不计为网格部件。

先建立明确支持类型的采集器和正反夹具，再扩展类型；不先造通用几何等价系统。最小 manifest 记录顶点、边端点、loop 顶点索引、polygon 范围、三角化规则、法线/UV/必要颜色属性、面材质绑定、单位与世界变换，带 schema 和覆盖清单。计数、bbox、量化 hash 只作辅助，不能替代拓扑与表面数据。

对 disposable mesh copy 调用 validate，原资产不被修复；修正结果形成原数据不干净的 finding。NaN/Inf、无效索引、退化范围按合同检查；非流形、自相交、壁厚等只在已定义相应用途规则时声称支持。

native 的 R4 在新 Blender 进程、全新路径实际重开精确 D，对账 authored/evaluated manifest 和实际使用依赖，并执行计划中的视觉证据。首发要求依赖已自包含、无外部路径解析成功；记录 offline 设置与依赖读取证据，但不把 Blender offline 标志或进程重开宣称为 OS 网络隔离。

## 8. GLB 投影的有限比较规则

M3 先支持锁定导出 preset 的静态三角表面、简单 PBR 和已明确用途的纹理。对 source 使用冻结的 export projection，import 使用对应投影及同一相机；全源诊断单独保留。Blender→GLB→Blender 已完成轴转换时，不再额外换轴。

投影字段从只有 preserved/transformed/lost 分类升级为逐字段绑定的 `范围 + 比较器 + 容差 + 允许损失 + 匹配规则`。保留 p01–p14 的可追溯 ID，具体策略如下：

| 字段 | v2 比较决策 |
|---|---|
| p01 对象数、p09 对象身份 | 对账 occurrence、变换、几何关联与必需部件；对象/辅助 node 分开，不只数 UID |
| p02 三角形、p04 顶点 | 允许合同明确的拆点、未使用顶点裁剪；首个比较器基于锁定三角化后的表面与角点属性匹配，未知重拓扑不自动接受 |
| p03 bbox | 作为 transformed 的数值比较，明确绝对/相对容差；禁止“任何差异失败”与非零容差并存 |
| p05 UV | 对使用中的 UV 值、引用与变换比较；未用层是否可丢由合同声明，需新增真实正向夹具后才开放该能力 |
| p06 槽、p07 PBR | 比较实际面绑定和使用中的材质语义；允许未使用槽裁剪；覆盖 alpha、发光、法线、采样等支持字段 |
| p08 贴图 | 锁定解码器，保留尺寸、通道、位深、用途及颜色解释；HDR 不转 RGBA8 后声称同一性；重打包用显式通道映射 |
| p10 collection、p11 modifier | 原生检查保留；GLB 中结构变化/烘焙损失须逐项声明并验证结果，不要求不可表示的源结构往返 |
| p12 自定义属性 | 仅目标格式可表示且合同要求的属性精确对账；保留属性不得被候选伪造为 evaluator 身份 |
| p13 单位 | 固定单位与轴边界，对实际尺度和 world transform 验证 |
| p14 driver/constraint | 首发不支持；后续若允许烘焙，显式验证固定帧结果并声明源结构损失 |

数值条件统一为 `abs(a-b) <= abs_tolerance + rel_tolerance * reference_scale`；reference_scale 取冻结源或可信参考，不能从损坏的导入物体放大。比较器保存未量化数据、匹配与差值，量化摘要只作加速提示。合法表示变化也必须同时证明使用中的表面/材质保留。

GLB 依次经过副本导出、源身份复核、锁定 Khronos Validator（完整报告与资源读取、`issues.truncated=false`）、预算/扩展检查、新进程导入和上述比较。格式合法、往返保真和目标可用性是三个条件；合同若要求实际网页/引擎消费者，必须新增版本化 check 或上层必需门禁，缺适配器即未验证。首发不声称支持任意消费者。

## 9. 视觉比较与签收

视觉证据分为用户成片、受控几何诊断、参考/投影匹配三类。诊断副本由 evaluator 控制相机、灯光、world 和允许的材质替换；用户成片保留合同允许的画面流程。producer 或模型可以辅助描述问题，不能签发 machine Pass。

以当前八视角模板起步，完整三维部件追加 bottom，并按必需部件覆盖增加剖切/近景。v2 文件数由计划展开：source 四种 pass，source clay/silhouette/wire 各保留两次原图；interchange import clay/silhouette 及对应差异图。M2 执行全部适用项与所要求的视角，不能用同日 16 对诊断图替代 wire、beauty 和全计划。底部缺件需有能正确拒收的负例。

文件 SHA-256 证明证据字节身份；解码像素由锁定比较器、通道、精度、颜色空间、阈值和掩码比较。PNG 时间/耗时元数据引起文件 hash 差异，不是像素失败，也不是放宽像素阈值的依据。两组原图均进入文件注册，hash 不能替代被丢弃图像。

平台身份包含 Blender build、OS/arch、engine/backend/GPU、色彩管理、分辨率、采样与 comparator。未知平台、未经校准阈值或预算不足均不能默认通过。先用已知好/坏资产校准，再锁合同；不把某个通用 SSIM/IoU 或外部回归工具参数作为普遍品质线。

分别报告同进程重复、新进程读取同一冻结资产、从建模步骤重建三个实验。M2/M3 完整支持前两项所需实验，各自有独立图像对、比较记录、job 与进程身份；不能复用一组 repetition 证明两个实验。只有合同要求可重建交付时才增加第三项的真实重建和比较门禁。重渲相同错误会一致，仍需缺件/尺寸/参考匹配及业务签收。

Q 绑定实际查看的图像和 C/S/D/E/V，记录所需业务审阅者、时间、结论与范围。机器比较不能伪造人工签收；没有任何已授权审阅者给出必需结论时停在 NEEDS_REVIEW。批准本设计本身不构成未来某个资产的签收。

## 10. 实施分包与验收

| 分包 | 主要影响面 | 可验证完成条件 |
|---|---|---|
| M0 规范迁移 | V5 规范、v2 字段/检查/file/writer 表、文档入口 | 唯一权威、逐 ID 版本变化、支持集与无环拓扑无歧义；v1 明确拒绝/重建流程 |
| M1 可信核心 | `contract.py`、`stages.py`、`decide.py`、`evidence.py`、`primitives.py`、CLI；最小新增工具/文件计划/result 接收模块 | 真实工具/输入核对、深不可变、内部结果约束、真实 R5；受控模拟 worker 完整正向链和下表负例通过；模拟不称资产验收 |
| M2 原生闭环 | inspector/reopen/render worker、对应 fixtures 与 v2 CLI | 支持集内真实冻结资产完成全部 24 个现有适用检查及新增必需门禁，完整图像/重复比较/重开/签收/T/D；坏资产拒收 |
| M3 GLB 闭环 | export/validator/budget/reimport/projection 与视觉比较 | 完成全部 34 个现有适用检查及新增必需门禁；合法表示变化通过、实际语义损失被拒；按合同验证消费者 |
| 后续能力 | 新类型、动画等新 profile、L1/L2 或更多消费者 | 每次有独立正向资产、对抗资产、环境实测与覆盖声明；不借用静态 L0 的完成状态 |

M1 先用标准库和已有原语；Blender worker 可导入 `bpy`，coordinator 与纯判定模块保持可脱离 Blender 测试。不得将 `bpy` 引入 `bridge/core` 或 `protocol`。不为本设计把 `acceptance/` 提前加入 wheel/sdist。

| 回归组 | 必须验证的行为 |
|---|---|
| 工具/合同 | 空必需工具集、重复 ID、错误真实版本/代码摘要、非十六进制 hash、嵌套错误、NaN/Inf、bool 数值、外部配置变更均不能通过 |
| 输入/策略 | 摘要或长度错配、读取中替换、链接/设备/路径逃逸、输入与证据根重叠、合同内存修改、失败后政策漂移被拒或检测 |
| result/事故 | 错误 writer/stage/状态、effective=Pass 但截断、重复/缺 check、伪 N/A、N/A 作业崩溃、旧 nonce/attempt、迟到与超限结果均阻断；Fail + NotTested（含 blocked_by）按第 5 节混合规则报告 |
| 证据 | 空/缺/未知/重复文件、无实测 hash、越界路径、接收后篡改、R5 自引用、T 缺失、D 验后变化均不能交付；每层中断可诊断 |
| 原生 | 正向资产真实重开成功；缺依赖、零范围、NaN/非法拓扑、底部缺件、缺视觉图和未签收各得到正确分类 |
| occurrence | 两集合实例、曲线/文字及隐藏对象的独立采集/导出正例；实例移位、少实例、双计数和路径段名称歧义负例。M2 对未支持类型仍返回 UNVERIFIED；类型纳入支持清单后才要求整份资产完整通过，不把探针通过当作 M2/M3 支持承诺 |
| GLB 表面 | 拆点/未用顶点和材质槽裁剪正例；相同计数但表面不同、使用材质/UV 丢失、轴或尺度错误负例；UV 裁剪另行真实验证 |
| 图像/消费者 | 同像素不同 PNG 字节不误拒；像素差异和已知坏资产正确拒收；wire/跨进程/未知平台各自证明；目标消费者缺测不冒充通过 |

纯 Python 回归用锁定解释器，默认单元测试不拉起 Blender。独立 Blender 集成测试在仓库外创建新证据目录，记录输入、合同、工具、环境与代码身份。正式证据遵循 [validation](../../validation.md) 的相应门禁；普通资产验收不额外要求整个 Git 工作树干净，可信代码闭包需如实记录。

每个实施包提交前运行一次 `bash scripts/checks.sh` 并确认 `ALL CHECKS PASSED`；最后修改后执行 `graft build .`，交付前 `graft check .` 退出 0。RELEASE、正式 Phase 0 现场证据和资产完整闭环分别报告，不相互代替。当前文档提交的检查只能证明文档改动未破坏仓库，不能宣称 M1–M3 已完成。

## 11. 自审结论与后续入口

本设计已区分源码事实、有限平台实测和待实现能力；保留了正常 CLI 当前失败关闭的结论。输入身份、worker 归属、内部判定、R5 和签收没有可由子进程自行放行的入口；E/V/Q/T 不循环；首发缩小支持类型但不删必需检查；未把未知 UV/完整视觉/隔离/消费者结论写成通过。

书面设计审阅通过后分别编写 M0–M3 实施计划，列出确切文件、最小行为验证和逐包完成条件；安装清理单独编写计划。后续实现若需改变支持范围、数据格式或本设计的删除/签收边界，先明确修订设计，再实施相关行为。
