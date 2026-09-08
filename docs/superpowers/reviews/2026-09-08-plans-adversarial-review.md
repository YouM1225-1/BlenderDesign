# 执行计划对抗审计与实测记录

日期：2026-09-08。审计基线：`487274c5c5090645dc5b4971f9f1156e4f406c93`。

本轮交付四份可按任务实施的计划，并通过独立交叉审计、主代理复核、仓库外原型与真实 Blender/Node 实验修正计划。当前发现的问题已落实修复和对应复测；这表示本轮审计闭环，不构成对未来实现或任意资产“绝无问题”的证明。

| 实施包 | 依赖与范围 |
| --- | --- |
| [安装升级与清理](../plans/2026-09-08-installer-upgrade-cleanup.md) | 独立；journal、使用锁、验证后清理、崩溃续删与有限恢复 |
| [M0/M1 可信核心](../plans/2026-09-08-asset-acceptance-core-v2.md) | v2 合同、冻结输入、作业/文件归属、进程预算、唯一判定与证据链 |
| [M2 原生闭环](../plans/2026-09-08-asset-acceptance-native.md) | 依赖 M0/M1；真实重开、几何/视觉/参考、审阅与交付 |
| [M3 GLB 闭环](../plans/2026-09-08-asset-acceptance-interchange.md) | 依赖 M2；真实 Validator、逐实例预算、有限表面投影与消费者门禁 |

仓库内仅修改计划、相关设计澄清及文档入口。原型代码和机器证据保存在仓库外。生产 `acceptance/` 仍是现有 schema v1/P0 实现，现行规范仍为 V3.8；本轮没有实施生产 v2、安装升级、删除用户缓存或签收用户资产。

## 审计方法

1. 从现有入口和数据结构确定计划依赖，固定具体文件、接口、代码、失败测试、命令与完成条件。
2. 分包作者进行原型验证，其他作者只读交叉审计；主代理另行检查跨包依赖、完整判定链和计划自身结构。
3. 对可运行假设使用真实 CPython、Blender 5.2.0 LTS、Node v20.20.2 和 `gltf-validator@2.0.0-dev.3.10`；安装器破坏性路径使用临时目录与现有安全文件系统 adapter。
4. 保留失败试验，修改原型与计划，再运行针对性回归。不会通过删 required check、合成 worker Pass、放宽合同阈值或伪造审阅来结束审计。

## 发现、修复与闭环证据

以下编号仅用于本报告。所有条目均已修正计划；“实测”范围以证据列为准。

| 编号 | 可触发的问题 | 已落实的修复 | 复核证据 |
| --- | --- | --- | --- |
| P01 | runtime 目录 rename 后，以路径命名的使用锁失去同一身份 | 以 device/inode 标识 lease，并让 FD 跨 `execve` 保留 | 临时目录 rename/exec/互斥探针 |
| P02 | 有 lease 仍不能保证旧 Python 的固定 `sys.path` 在替换后安全 | 第一次目标变更前持有旧 runtime 非阻塞排他锁；忙时不改变目标 | 安装器占用负例；维护交接边界写入设计 |
| P03 | 先启动托管 Python 再加锁，解释器加载发生在保护前 | 托管树外 bootstrap Python 先取共享锁，核对 installed receipt 与 inode 后再 exec | launcher 两条真实进程探针 |
| P04 | 旧 launcher 无协议，单次进程空扫描不能证明无人使用 | 首次迁移要求外部终端维护交接与已记录进程身份；证据不足保留并报告 | 未执行真实迁移；失败关闭条件进入计划 |
| P05 | 精确版本 no-op、旧注册 before 记录或完全孤儿缓存可能被发现逻辑漏掉 | no-op 仍发现历史；保留恢复引用；未知归属仅列出，并令全部清理完成为 false | before-only 历史、孤儿缓存、跨 CODEX_HOME 回归 |
| P06 | 清理失败落入安装回滚异常范围，或崩溃后重复删除漂移内容 | 独立清理阶段、revision journal、逐候选条件删除与恢复状态 | 四个崩溃点、内容漂移与续删回归 |
| P07 | 文案声称无锁验证，代码却持锁；逐候选重复整个现场验证 | finalize 锁内一次完整验证，逐候选复核有界绑定快照；等待用户启动时释放锁 | adapter/锁序代码复核与文案统一 |
| P08 | 额外技术 gate 只进入上层状态，原有 summary.success 仍可能为 true | 唯一 decide 同时处理 required checks 与 required gates；缺项或未完成均不能技术成功 | M1 gate、混合 Fail/NotTested 回归 |
| P09 | 安全阻断后缺输出，误补空结果或把缺 D 当作成功资产 | 保留 NotTested 和 blocked_by；证据记录未产出文件；D 可为 null，不能以 source 假充 GLB | 核心 pipeline/evidence 负例 |
| P10 | 生成 Q/T 后仅检查 D，期间证据或合同漂移未被交付重新发现 | 交付前复核完整 E/control chain/C，再复测同一 D | 证据修改、合同修改、交付字节绑定回归 |
| P11 | macOS 无法按原方案把 RLIMIT_AS 降到指定值 | 使用进程组 RSS 采样预算，记录峰值与采样口径；不声称 L1 硬隔离 | 实际平台错误复现及进程预算回归 |
| P12 | 无 bpy 的类型检查未覆盖 CLI；合并后暴露返回值与 JSON 类型错误 | 补齐 CLI 类型及 JSON 容器校验，移除冗余 cast | 核心含 CLI strict mypy；最终三包联合 36 源文件通过 |
| P13 | NaN/不支持依赖导致异常或被清洗后看起来有效 | 合法 JSON 显式记录非法数值与覆盖缺口，由 controller 判失败/未验证 | native policy/manifest/checks 负例 |
| P14 | Workbench WIREFRAME 产生全黑图，却因重复结果一致而通过 | 从 mesh edges 构造受控线条；显式前景能量校验；旧全黑图证据作废 | 修复后 135 图、63 对比较；缺底板负例有 3,346 差异像素 |
| P15 | 比较进程只解码图像时查询 GPU，GPU 尚未初始化 | CPU 解码报告只声明 decoder 执行信息；真实渲染另留完整平台信息 | 原生与 GLB 真实 CLI 比较阶段回归 |
| P16 | 假定 npm 包有 `gltf_validator` CLI；资源图片行又未必含 byteLength | 使用官方 `validateBytes` Node wrapper；分别核对 buffer 与 image 资源证据 | 真实外部资源读取、IO_ERROR、报告截断及图片资源实验 |
| P17 | Validator 的唯一 mesh 数量被误当逐实例绘制预算 | 从已验证 GLB 的活动 scene/node 图计算 rendered triangles 与 draw calls | 同一 mesh 两个实例：stored 12、rendered 24、draw calls 2 |
| P18 | 顶点/材质槽数量或固定索引比较误拒合法拆点和裁剪 | 有限的三角角点匹配，允许循环顶点次序和未使用数据裁剪；保留 world/UV/PBR/纹理约束 | 8→24 顶点、12→3 顶点与 2→1 材质槽真实导出/导入通过 |
| P19 | 纹理连接时比较无作用的 Base Color 默认值，造成假失败 | 连接输入按实际语义投影；发光用颜色×强度；不支持的节点/纹理用途拒绝 | 打包 RGBA8 sRGB 纹理真实正例及材质/UV/纹理篡改负例 |
| P20 | export.measurements 被写出但 controller 不读取 | 严格复核导出字段、preset、源与 D hash、ID 与 native occurrence 集 | 8 个导出事实篡改负例 |
| P21 | 图像 engine/color interpretation 字段未纳入接收校验 | 严格检查平台、解码语义、原图 hash、完整 view/pass 与前景能量 | native/M3 receiver 单元与真实联合回归 |
| P22 | M3 的完整合同替换片段覆盖掉 M2 的冻结引用及 main=asset 守卫 | 完整保留 manifest/authority/images 属于冻结输入、main=asset 及异常归一化 | 完整合同跨 native/interchange 红绿回归：修复前 10 失败/2 通过，修复后 12 通过 |

P22 的 `main` 负例尤其防止“检查 asset、交付另一冻结文件”。这项验证调用完整合同入口，不能由单独的 policy 测试替代。

## 实际验证结果与边界

各行存在重叠，不把数字相加成一次统一套件的测试数量。

| 验证 | 实际结果 | 证明范围 |
| --- | --- | --- |
| 安装器临时原型 | 22 passed；7 完整模块 Ruff；2 个现有 CLI 机械变换 AST 通过 | journal、锁、删除条件、发现逻辑、入口修改可落地；不是实际安装验收 |
| M0/M1 原型 | 77 passed；其中 CLI 单独复跑 4 passed；Ruff、strict mypy 16 源文件通过 | 合同、输入、协议、作业、唯一判定及 E/V/Q/T；worker 使用受控 Python 夹具 |
| M2 原型单元 | 27 passed；Ruff；8 runtime 模块 strict mypy 通过 | native 封闭政策、采集与判定接线 |
| M2 实际图像实验 | 修复后 135 张 1024² 原图；63 对比较本次全部像素一致 | 同进程诊断重复与跨进程比较；不把本次一致推广为所有平台的零阈值保证 |
| 缺底板负例 | wire 3,346 不同像素，最大差 0.984313786；同视角另三 pass 为零差 | 证明有效线框补上仅表面视图漏检的缺口；保留全部原图与差异图 |
| M3 最终纯 Python | 39 passed，含 P22 的 12 项 | 封闭政策、有限表面匹配、预算、导出事实与完整合同绑定 |
| M3 真实联合回归 | 15 passed | 三条实际 CLI 正/负流程、两进程表面正例、真实 Node 验证与导出事实负例；部分与上一行重叠 |
| 最终共同入口回归 | 2 passed，184.65 秒；原生与 GLB 各一条完整审阅/交付流程 | 在 P22 修复后的共同合同与 CLI 上重验；测试签收仅绑定其自动生成夹具 |
| 三包联合静态检查 | Ruff；strict mypy 36 源文件通过 | 实际拼接后的 acceptance 与 CLI；仅缺失的 Blender 平台模块允许无 stub，不忽略模块内类型错误 |
| 当前生产仓库检查 | 599 passed；分发 824 passed、1 skipped；`ALL CHECKS PASSED` | 文档任务未破坏当前实现；不能当作 v2 已实现的证明 |

Node 接口核对使用 [Khronos 官方 Node 文档](https://github.com/KhronosGroup/glTF-Validator/blob/434283be08a668a8fb4e437145630ddbf93b0686/node/README.md) 与[官方报告 schema](https://github.com/KhronosGroup/glTF-Validator/blob/434283be08a668a8fb4e437145630ddbf93b0686/docs/validation.schema.json)。本轮 npm 包安装在仓库外专用目录，未添加项目依赖。

## 证据组织

本轮仓库外证据包标识为 `blenderdesign-plan-audit-20260908.KjSAsl`；用户交付消息提供实际可点击目录。文档不固定用户名或临时机器路径。

| 相对证据位置 | 内容 |
| --- | --- |
| `installer-final/final-evidence.json` | 安装器最终计划摘要、检查命令结果与日志；同目录保留原型 |
| `core-final/final-verification/verification.json` | 核心命令、退出码、源码 hash 与可重跑脚本 |
| `native-final/inventory.json`、`native-final/verification.json` | 最终采集/渲染原型、135 原图、63 差异及缺底板材料；逐文件与比较输入 hash 已核对 |
| `glb_draft/combined/` | M0/M1、M2、M3 真实拼接的仓库外代码与夹具 |
| `glb_draft/contract-binding-red.log`、`contract-binding-green.log` | 完整合同边界修复的红绿记录 |
| `glb_draft/combined-final.log`、`m3-unit-final.log` | 15 项联合与最终 39 项纯 Python 记录 |
| `glb_draft/combined-mypy-final.log`、`combined-ruff-clean.log` | 三包最终静态检查 |
| `glb_draft/final-cli-binding.log`、`final-cli-evidence/` | 最终合同修复后的原生/GLB CLI、E/V/Q/T 和实际交付回执 |
| `plan-structure.json`、`document-links.json` | 主代理最终代码块 AST、任务结构及本地文档链接核对 |
| `repository-checks.log`、`graft-build.log`、`graft-check.log` | 当前仓库与最终图门禁原始输出 |
| `evidence-inventory.json` | 最终精选证据文件 SHA-256 清单；不把自身纳入摘要循环 |

早期错误试验（包括缺 CLI 假设、未初始化 GPU、无效线框、材质误比较）保留其失败记录或作废说明，不混入最终通过图像清单。

## 实施阶段必须保留的门禁

- 在实际生产源码按各计划落地后重新运行对应回归及仓库门禁。文档代码块的原型验证不能替代最终合并代码验证。
- 安装器 A→B→C 的真实用户配置迁移、当前 Blender 现场验证及实际历史缓存清理，在实施后的授权环境执行。首代 launcher 的维护交接不能从本轮临时目录测试推导完成。
- L1 隔离、曲线/文字/集合实例的完整资产支持，以及合同要求的实际目标消费者，仍按计划要求提供独立能力和正反证据；缺失即 UNVERIFIED，不宣称支持。
- 真实用户资产的审阅须由合同指定审阅者针对同一 C/S/D/E/V 与所需图像完成。本轮测试记录不产生用户资产的 Q/T 授权。
- 新平台、Blender/Node/Validator 或导出实现变化必须重新冻结工具与合同、校准并回归；不能沿用本机本次通过结果。

最终文档检查、`graft build .` 与 `graft check .` 的退出结果记录在上述证据包。没有通过最终 Graft 门禁不得把本轮任务表述为完成。
