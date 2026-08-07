# Blender × Codex 安全自动化系统 · 需求规格说明书

| 项 | 值 |
|---|---|
| 版本 | v1.1 |
| 日期 | 2026-07-23（v1.0）· 2026-08-06（v1.1） |
| 状态 | 已评审，决策 D-1 / D-2 / D-3 已确认；v1.1 变更见 §13 |
| 适用范围 | macOS 桌面端本地部署 |

---

## 1. 目标与约束

### 1.1 系统目标

在 macOS 上，用户通过自然语言驱动 Codex 完成 Blender 建模、材质、灯光、预览渲染与导出。

### 1.2 优先级最高的三条硬约束

| ID | 约束 | 含义 |
|---|---|---|
| **G1** | 不可破坏 | 任何自动化操作不得损坏用户既有工程文件 |
| **G2** | 可解释 | 每次场景变更都能回答：改了什么、依据哪条计划、结果是否达标 |
| **G3** | 不可逃逸 | Agent 不能执行任意代码、访问工作区外文件、发起未授权网络请求 |

**当功能覆盖度与 G1–G3 冲突时，删减功能。**

### 1.3 系统边界

```
用户 → Codex Skill → MCP Server（stdio） → Bridge Add-on（UDS） → Blender GUI 主线程
                          └──────────────→ Headless Worker（受控 CLI）
```

四层信任边界，每层独立成立、互不依赖上层的正确性：

| 层 | 职责 | 失效时的兜底 |
|---|---|---|
| Codex Host | sandbox / approval / protected paths | 不依赖；见 NFR-S2 |
| MCP Server | 工具白名单、JSON Schema 校验、路径策略、事务、审计 | 唯一被信任的文件边界 |
| Bridge | 只接受结构化 IR 命令，主线程串行执行 | 不信任 MCP Server 传来的任何参数 |
| 文件系统 | 工作副本 / 导出目录 / 缓存目录白名单 | 原工程默认不可写 |

---

## 2. 术语定义

| 术语 | 定义 |
|---|---|
| **Modeling IR** | 版本化声明式中间表示，所有写操作的唯一表达形式 |
| **stable_id** | 受管对象的稳定标识，存于自定义属性 `bcx.v1.id`，独立于 Blender 对象名 |
| **scene_revision** | 会话内单调递增**整数**，由 `depsgraph_update_post` 递增，Bridge 重启后归零。**仅用于会话内快速变更检测**；跨会话比对一律用 hash |
| **scene_hash** | **全场景**结构化摘要：对每个对象取 `(name, type, 量化至 1e-6 的 matrix_world, data 类型与计数)`，排序后 SHA-256。跨进程、跨文件重载有效。**用于变更检测与快照标识，不用于冲突判定**（过度敏感） |
| **plan_scope_hash** | 仅覆盖 IR 的 `target` / `depends_on` 涉及对象的结构化摘要。**冲突判定的唯一权威依据**（Phase 1 交付） |
| **回滚快照**<br>(rollback snapshot) | `begin_transaction` 时刻的自包含 `.blend` 副本，用于 hard 回滚 |
| **物化快照**<br>(materialization snapshot) | 验证 / 渲染 / 导出时刻，从 GUI 实例**当前状态**导出的自包含临时 `.blend`，供 Headless Worker 消费 |
| **自包含** | 副本已执行资源打包，不含指向原目录的相对外部引用（见 FR-24） |
| **job** | 服务端自铸的长任务句柄，通过轮询查询状态 |

> **回滚快照与物化快照必须区分。** 回滚快照是事务起点的状态；物化快照是当前状态。Headless 渲染与导出验证消费的是**物化快照**——否则验证的是修改前的场景。

---

## 3. 用户角色

| 角色 | 描述 | 核心诉求 |
|---|---|---|
| **U1 3D 创作者**（主要） | 会用 Blender，不写 Python | 别弄坏我的文件；结果要能看；出错能撤回 |
| **U2 技术美术 / Pipeline** | 会写脚本，负责接入团队流程 | IR 可扩展；可进 CI；版本兼容矩阵清晰 |
| **U3 安全 / IT 审批人** | 决定能否安装在公司设备上 | 新增了什么攻击面；审计日志在哪 |

---

## 4. 用户故事

### Epic A —— 安全地观察

| ID | 故事 |
|---|---|
| US-A1 | 作为 U1，我想知道当前 Blender 开着哪些实例、版本、Bridge 通没通，以判断能否开始 |
| US-A2 | 作为 U1，我想获得场景概览（对象数、单位、相机灯光、受管对象），不必自己清点 |
| US-A3 | 作为 U1，我要求只读操作永不弹确认，以免探索阶段被打断 |

### Epic B —— 受控地修改

| ID | 故事 |
|---|---|
| US-B1 | 作为 U1，我说"在桌面上放一个 40cm 的圆角盒子"，系统应先给出计划，我确认后才动场景 |
| US-B2 | 作为 U1，任何写操作前系统自动建立工作副本，原始 `.blend` 绝不被覆盖 |
| US-B3 | 作为 U1，若我在计划生成后手动改了场景，系统必须拒绝执行旧计划并告知，而非覆盖我的改动 |
| US-B4 | 作为 U1，同一计划重复提交不得产生重复物体 |
| US-B5 | 作为 U1，我要能随时回滚，且系统必须**提前**告诉我回滚会丢什么 |
| US-B6 | 作为 U1，系统不得通过任何途径在我的 Blender 中执行它自己生成的 Python |

### Epic C —— 证明结果正确

| ID | 故事 |
|---|---|
| US-C1 | 作为 U1，我要一份验证报告：结构、几何、渲染三类判据 |
| US-C2 | 作为 U1，我要预览图，且渲染不得冻结我的 Blender 界面 |
| US-C3 | 作为 U1，导出后系统必须重新导入验证：单位、尺寸、对象数 |
| US-C4 | 作为 U1，验证不通过时系统不得提交 |

### Epic D —— 可运维

| ID | 故事 |
|---|---|
| US-D1 | 作为 U2，MCP Server 或 Blender 崩溃重启后，我要能列出未完成事务并显式回滚 |
| US-D2 | 作为 U2，我要能查询支持的 IR 操作、schema 版本、Blender 兼容版本，不必读源码 |
| US-D3 | 作为 U2，长任务要能查进度、能取消，取消后有日志 |
| US-D4 | 作为 U3，我要逐次调用的审计日志：时间、工具、参数、结果、涉及路径 |
| US-D5 | 作为 U3，安装不得要求 Full Disk Access、不得默认常驻 LaunchAgent、不得开监听端口 |

---

## 5. 功能需求

### 5.1 工具面（13 个）

写入路径**只有一条**：Modeling IR。`create_primitive` 是服务端语法糖，内部展开为单操作 IR，走完全相同的校验与审计路径（FR-07）。

| # | Tool | 类别 | 写场景 | 审批 | 可能 >60s |
|---|---|---|---|---|---|
| 1 | `get_blender_status` | 只读 | 否 | auto | 否 |
| 2 | `get_scene_summary` | 只读 | 否 | auto | 否 |
| 3 | `describe_capabilities` | 只读 | 否 | auto | 否 |
| 4 | `validate_modeling_ir` | 只读 | 否 | auto | 否 |
| 5 | `validate_scene` | 只读 | 否 | auto | **是 → job** |
| 6 | `list_transactions` | 只读 | 否 | auto | 否 |
| 7 | `get_job_status` | 只读 | 否 | auto | 否 |
| 8 | `begin_transaction` | 状态变更 | 否 | approve | 否 |
| 9 | `apply_modeling_plan` | 写 | **是** | approve | **是 → job** |
| 10 | `create_primitive` | 写 | **是** | approve | 否 |
| 11 | `finalize_transaction` | 写 | **是** | approve | **是 → job** |
| 12 | `render_preview` | 任务 | 否 | auto | **是 → job** |
| 13 | `cancel_job` | 状态变更 | 否 | auto | 否 |

### 5.2 需求条目

#### 观察与能力发现

| ID | 需求 | 优先级 |
|---|---|---|
| FR-01 | 提供 `get_blender_status`、`get_scene_summary` | P0 |
| FR-02 | 提供 `describe_capabilities`：返回 IR schema 版本、支持的 operation kinds、Blender 完整版本号、Server / Bridge 版本 | P0 |
| FR-03 | 握手时检测 Blender 版本；非基线版本（见 NFR-C2）时只读工具可用，**所有写工具拒绝**并返回 `UNSUPPORTED_BLENDER_VERSION` | P0 |

#### 写入路径

| ID | 需求 | 优先级 |
|---|---|---|
| FR-04 | 场景写入**只能**经由版本化 Modeling IR。系统不得暴露任意 Python / Shell / 通用文件系统 / 网络下载工具 | P0（红线） |
| FR-05 | IR 的每个 `operation.payload` 按 `kind` 做判别联合（`oneOf` + `if/then`），每个 kind 一个封闭 payload schema（`additionalProperties: false`）。**不得存在 `payload: {type: object}` 这类开放定义** | P0 |
| FR-06 | 提供 `validate_modeling_ir` 作为**唯一** dry-run 入口；`apply_modeling_plan` **不提供** `dry_run` 参数 | P0 |
| FR-07 | 提供 `create_primitive`，内部展开为单操作 IR，审计日志记录展开后的 IR | P1 |
| FR-08 | 提供 `apply_modeling_plan`，仅在事务上下文内可调用 | P0 |

#### 标识与一致性

| ID | 需求 | 优先级 |
|---|---|---|
| FR-09 | 受管对象标识存于自定义属性 `bcx.v1.id`。对象名仅用于展示与降级回退，**不得作为查找依据** | P0 |
| FR-10 | 重复 `bcx.v1.id` 检测：在 `begin_transaction`、`apply_modeling_plan` 完成后、`validate_scene` **三处**均须执行。发现重复立即返回 `STABLE_ID_COLLISION`，要求人工消歧，**不得自动猜测** | P0 |
| FR-11 | 冲突检测以 **`plan_scope_hash`** 为权威依据（`scene_hash` 对全场景敏感，用作判定会误拒无关改动；`scene_revision` 仅作会话内快速路径）。IR 携带的 plan_scope_hash 与执行时不符即拒绝写入，返回 `SCENE_REVISION_CONFLICT` | P0 |
| FR-12 | 幂等键由**服务端派生**：`SHA-256( canonical_json(IR \ 易变字段) ‖ scene_hash )`，其中 `canonical_json` = `json.dumps(sort_keys=True, separators=(',',':'))`。**IR 自身不得携带 `idempotency_key` 字段**，避免定义循环 | P0 |
| FR-13 | 幂等键持久化于事务日志；重放已完成的键不产生第二次写入，返回首次结果 | P0 |

#### 事务与回滚

| ID | 需求 | 优先级 |
|---|---|---|
| FR-14 | 提供 `begin_transaction` / `finalize_transaction(commit\|rollback)` | P0 |
| FR-15 | 事务状态**持久化到磁盘**，不得仅存于进程内存。提供 `list_transactions` 支持崩溃恢复 | P0 |
| FR-16 | 回滚分两级：`soft` = 尽力 undo，仅对 GUI 会话内低风险操作有效、**不保证**；`hard` = 重载回滚快照，**唯一有保证的机制** | P0 |
| FR-17 | `begin_transaction` 输出必须含 `rollback_warning` 字段，明文声明"hard 回滚将丢弃本事务窗口内的所有手动编辑" | P0 |
| FR-18 | Skill 必须转述 FR-17 警告，并在首次 `begin_transaction` 时要求用户确认 | P0 |
| FR-19 | 事务期间 Bridge 在 GUI 显示持久提示，标明事务 ID 与开始时间 | P1 |
| FR-20 | 执行 hard 回滚前，先将**当前场景**另存为 `pre-rollback` 快照。用户的手动编辑降级为"需手工找回"，而非不可逆丢失 | P0 |
| FR-21 | 原始 `.blend` 永不被覆盖。提交产物写入新路径，经临时文件 + `os.replace` 原子替换 | P0（红线） |

#### 验证与长任务

| ID | 需求 | 优先级 |
|---|---|---|
| FR-22 | 提供 `validate_scene`，输出 Validation Report（结构 / 几何 / 渲染 / 导出四类），报告须记录 Blender 完整版本号 | P0 |
| FR-23 | 渲染、导出、重导入验证一律在 **Headless Worker** 上对**物化快照**执行，不占用 GUI 主线程 | P0 |
| FR-24 | 生成回滚快照与物化快照时，必须先执行资源打包使副本自包含。**不得依赖 `save_as_mainfile` 的 `relative_remap` 参数**（见 R-03） | P0 |
| FR-25 | 预览与验证渲染引擎固定为 **Cycles**（Metal GPU）。EEVEE 不用于 headless 路径（见 R-02） | P0 |
| FR-26 | 任何可能超过 60 秒的工具必须**立即返回 job 句柄**而非阻塞。提供 `get_job_status`（轮询）与 `cancel_job` | P0 |
| FR-27 | 取消 job 后 60 秒内子进程终止，产生取消日志，清理临时产物 | P0 |
| FR-28 | 导出后重导入验证，容差见 §10.3 | P1 |
| FR-29 | 验证未全部通过时，`finalize_transaction(commit)` 必须拒绝，返回 `COMMIT_VALIDATION_REQUIRED` | P0 |

#### 安全与运维

| ID | 需求 | 优先级 |
|---|---|---|
| FR-30 | 所有路径经 `expanduser` → `realpath` → root containment → 扩展名白名单，**fail-closed** | P0 |
| FR-31 | Bridge 的 UDS 端点置于 `0700` 私有运行目录下，socket 文件 `0600`，并要求每会话随机 token 握手 | P0 |
| FR-32 | 多实例支持：每会话独立目录 + `session.json`（含 socket_path 权威字段），Server 扫描 `run/` 发现；stale 清理用双条件判据 + 宽限期。**不设中心注册表**——共享可变文件需要跨进程加锁，每会话一文件天然无锁 | P1 |
| FR-33 | 逐次调用审计日志（JSONL）：request_id、工具名、参数摘要、结果、涉及路径、耗时、事务 ID。**Phase 1 起写工具另记**：`scene_revision_before/after`、结果摘要 `result_digest`、审批决定、tool schema 版本——审计要能回答「改前改后各是什么、谁批准的」 | P0 |

#### v1.1 增补（2026-08-06，来源见 §13）

| ID | 需求 | 优先级 |
|---|---|---|
| FR-34 | MCP Server 初始化响应的 **`instructions`** 字段必须携带跨工具规则（Codex 已核实会消费该字段）：先查 `get_blender_status`；无实例时引导用户在 N 面板点击「允许 Codex 连接」；写操作必须在事务中；长任务经 job 句柄轮询。关键规则前置。**Phase 0 起交付** | P1 |
| FR-35 | job 生命周期显式状态机：`CREATED → QUEUED → RUNNING → VALIDATING_OUTPUT → SUCCEEDED`；任意运行态可 `CANCELLING → CANCELLED`；异常终态 `FAILED / TIMED_OUT / LOST`。job 记录持久化：当前阶段、进度、**心跳时间戳**、worker PID、输入快照、输出目录、重试次数；心跳超时判 `LOST` 而非永久 `RUNNING`。客户端断连不隐含取消——取消只经 `cancel_job`。**Phase 2 生效** | P1 |

---

## 6. 非功能需求

### 6.1 安全（S）

| ID | 需求 |
|---|---|
| NFR-S1 | 四层信任边界（§1.3）各自独立成立 |
| NFR-S2 | **不假设** Codex 启动的 MCP Server 子进程继承 Codex sandbox。MCP Server 的路径策略必须独立 fail-closed，是唯一被信任的文件边界 |
| NFR-S3 | 不申请 Full Disk Access；不默认注册 LaunchAgent；不开 TCP / HTTP / WebSocket 监听端口 |
| NFR-S4 | 权限达成机制必须显式：目录**逐级**创建并各自 chmod `0700`（`makedirs` 的 mode 不作用于中间目录）；文件以 `O_EXCL` mode `0o600` 创建；socket bind 后立即 chmod `0600`（竞态窗口因位于 0700 目录内而无害）。**不得使用进程级 `os.umask`**——Blender 是共享进程 |
| NFR-S5 | token 的作用是**提升攻击成本并实现凭据轮换**：把攻击从「扫描 socket 盲连」提升为「须定位并读取 0600 会话文件」。同 uid 进程可读取该文件，token **不能**阻断同 uid 越权；真正压缩风险的是显式会话窗口（用户主动开启才监听）。文件权限只防其他 uid |
| NFR-S6 | 短时会话 token 存 `0600` runtime 文件，随进程销毁。仅持久秘密（OAuth、渲染农场凭据）使用 Keychain |
| NFR-S7 | 分发二进制 / GUI 壳需 Developer ID 签名 + notarization |
| NFR-S8 | Bridge 扩展**不得**在运行时安装 Python 模块（Blender 扩展指南明令禁止）。Bridge 保持零第三方依赖，仅用 stdlib；JSON Schema 等重校验全部置于 MCP Server 侧 |
| NFR-S9 | Bridge 侧执行结构性校验（kind 白名单、必填字段、类型检查），不因 MCP Server 已校验而略过 |

### 6.2 可靠性（R）

| ID | 需求 |
|---|---|
| NFR-R1 | Blender 写操作严格在主线程串行执行。IPC 线程只负责收包、鉴权、入队 |
| NFR-R2 | Bridge 的关闭必须确定性回收线程与 socket 文件。**不得以标志位配合阻塞 `accept()` 实现**——需 socket timeout 或 self-pipe 唤醒 |
| NFR-R3 | IPC 采用显式分帧（4 字节大端长度前缀 + JSON）。**不得假设单次 `recv()` 收全消息**，两端均须循环读满 |
| NFR-R4 | 主线程 timer 回调单次执行预算 ≤ 50 ms。超预算操作必须分片或转交 Headless Worker |
| NFR-R5 | 主线程任务队列**不得跨文件重载持有 bpy 数据引用**。`open_mainfile` 会释放全部 bpy 数据，跨越该点的引用即失效 |
| NFR-R6 | Bridge 的 timer 须以 `persistent=True` 注册，并具备重载后的自愈重注册路径（hard 回滚会触发文件重载） |
| NFR-R7 | 优先使用 Data API（`bpy.data.*.new()` + `collection.objects.link()`）。必须使用 operator 时经**统一 OperatorAdapter**：显式 `temp_override` 构造 context、调用前检查 `poll()`、保存并在 `finally` 中恢复 Mode 与 Selection、将 `FINISHED`/`CANCELLED`/异常转换为结构化结果（Phase 1 实现指引） |
| NFR-R8 | Blender 崩溃或 Bridge 断连后可恢复；已提交事务的持久状态不丢失 |

### 6.3 性能（P）

| ID | 需求 |
|---|---|
| NFR-P1 | 只读工具 P95 < 2 s |
| NFR-P2 | MCP Server 冷启动 < 5 s（Codex `startup_timeout_sec` 默认 10 s） |
| NFR-P3 | 单次工具调用阻塞时长 < 60 s（Codex `tool_timeout_sec` 默认 60 s）。超出者一律走 job 模式 |
| NFR-P4 | 长任务须有超时与内存上限；超限产生日志并终止，不得静默挂死 |

### 6.4 可观测（O）

| ID | 需求 |
|---|---|
| NFR-O1 | stdio 传输下，stdout **仅**承载 JSON-RPC。所有日志写 stderr 或独立文件 |
| NFR-O2 | 不使用 MCP logging 特性（2026-07-28 规范已弃用）。Phase 0 交付本地 JSONL 审计；OpenTelemetry 与 `traceparent` 传播推迟至 Phase 1（Phase 0 spec §1.2 已声明） |
| NFR-O3 | 审计日志脱敏：不记录完整文件内容，路径按工作区根做相对化 |

### 6.5 兼容性（C）

| ID | 需求 |
|---|---|
| NFR-C1 | 支持面 = macOS 14+ / Apple Silicon。Intel Mac 不在本版支持范围 |
| NFR-C2 | Blender 生产基线 = **5.2 LTS 单栈**，钉定具体补丁版本（不写 `>=5.2`）。4.5 LTS 兼容为 best-effort：不刻意破坏，但不测试、不承诺、不进验收门槛 |
| NFR-C3 | MCP 协议本版目标 `2025-11-25`，Python SDK 钉 `mcp==1.28.x`。协议适配收敛于 ≤ 300 行 adapter 层 |
| NFR-C4 | Server / Bridge / IR 三者独立版本号，握手时协商；不匹配则拒绝并返回可读原因 |
| NFR-C5 | Codex Skill 置于 `.agents/skills/<name>/`；`agents/openai.yaml` 中设 `policy.allow_implicit_invocation: false`；`description` ≤ 200 字符、触发词前置；schema 与策略正文置于 `references/`。Skill 交付物**另含 `AGENTS.md` 模板片段**（Blender 版本矩阵、先检查后修改、禁任意 Python、长任务须走 job）供用户仓库采用（Phase 1 与 Skill 同批交付） |

---

## 7. 外部约束（已核实）

以下事实约束本设计，与实现选择无关。核实日期 2026-07-23，**§7.2 于 2026-08-06 复核更新**；来源见附录 A。

### 7.1 Codex

- 仅支持 **stdio** 与 **Streamable HTTP** 两种 MCP 传输。
- 配置项：`enabled_tools`、`disabled_tools`、`default_tools_approval_mode`（`auto` / `prompt` / `writes` / `approve`）、逐工具 `approval_mode`、`startup_timeout_sec`（默认 10）、`tool_timeout_sec`（默认 60）。
- 提供 `codex mcp add / list / get / remove / login / logout` 子命令，无需手写 `config.toml`。
- Skill 发现路径按优先级：仓库 `.agents/skills` → `$HOME/.agents/skills` → `/etc/codex/skills` → 内置。
- `policy.allow_implicit_invocation` 默认 `true`。
- Skill 列表占用上下文预算上限 2%（未知时约 8000 字符），超出则 description 被截断、skill 可能被省略。
- 官方文档**未承诺**支持 MCP 的 Resources / Prompts / Roots / Sampling / Elicitation / Tasks。

### 7.2 MCP 协议

- **当前正式版 `2026-07-28`**（2026-07-28 发布；`2025-11-25` 为上一版）。本项目按 ADR-3 仍以 `2025-11-25` 为 Phase 0/1 目标，Phase 1.5 迁移。
- `2026-07-28` 的破坏性变更：移除 `initialize` 握手与 `Mcp-Session-Id`（协议层无状态）；新增必须实现的 `server/discover`；Tasks 移出核心成为扩展 `io.modelcontextprotocol/tasks`（轮询式 `tasks/get`）；**Roots / Sampling / Logging 弃用**；服务端发起请求改由 MRTR 模式取代；结果新增必填 `resultType`；`inputSchema` / `outputSchema` 放开为完整 JSON Schema 2020-12。
- 规范明确：需要跨调用状态的服务器应使用**服务端自铸句柄作为普通工具参数** —— 本设计的 `transaction_id` / `job_id` / `instance_id` 与此一致。
- Python SDK **v2.0.0 已于 2026-07 末发布稳定版**（支持 `2026-07-28` 并可服务更早版本）；**v1.x 进入维护期，仅接收安全修复**；`pip install mcp` 现默认安装 2.x——**依赖必须钉 `mcp>=1.28,<2` 上界**，否则会被静默升级到 v2。
- stdio 服务器向 stdout 写日志会破坏 JSON-RPC 消息流。

### 7.3 Blender

- 5.2 LTS 于 2026-07-14 发布，支持至 2028-07；4.5 LTS 支持至 2027-07。
- 5.0 起仅支持 Apple Silicon + macOS 13+；4.5 LTS 是最后一个提供 Intel 构建的版本。
- Python 线程不支持直接操作 `bpy`；operator 受 context 约束，并非全部可从 Python 有意义地调用。
- 5.0 起 `bpy.props` 注册的属性与用户自定义属性**分离存储**，不能再以 dict 语法访问前者。用户自定义属性（`obj["key"]`）不受影响，仍是 stable_id 的可用载体。
- 5.2 变更了 Geometry Nodes modifier 属性的访问方式（改为正式 RNA 属性）。
- **EEVEE 不支持 macOS 上的 headless 渲染**（仅 Linux 自 3.4 起支持）。
- 扩展需 `blender_manifest.toml`；第三方模块须以 wheels 声明。**扩展不得在运行时安装 Python 模块 / pip 包**。
- Blender 自身的 Auto Save 是崩溃保护网，不是事务系统；从 Auto Save 恢复会丢失最后一次自动保存后的改动。
- Python 脚本默认不自动执行，可用 `-Y` / `--disable-autoexec` 关闭自动执行。

### 7.4 第三方生态（不采用，仅作背景）

- Blender Lab 官方 MCP Server：add-on + TCP 9876，工具面为任意 Python 执行。官方警告其**无任何防护**阻止数据被删除或发送至远端，建议在虚拟机或无敏感信息的系统上使用。官方明确 Lab 活动不在 Blender 路线图内、无发布时间表。
- `ahujasid/blender-mcp`（MIT，24.7k stars）：TCP 9876，`execute_blender_code` 任意 Python，无沙箱。
- `seehiong/blender-mcp-n8n`（MIT，46 stars / 23 commits）：Bridge 8008 + Addon 8888，93 个工具，有主线程命令队列。

**2026-08-06 生态补充**（源自外部研究报告转述，**未逐项独立核验**，仅作方向参考）：

- 生态趋势与本设计一致的两点印证：多个较新项目（如 `PatrykIti/blender-ai-mcp`、`glonorce/Blender_mcp`）转向**小公开工具面 + 内部原子库 + 搜索/分层发现**，并以**确定性测量而非视觉截图**作为验收真相源——与本 URS 的 13 工具面与 Validation Report 路线相同。
- 供应链反例：据报告，`6xvl/blender-mcp` 每次 Blender 启动自动从远端 `main` 分支替换 Add-on 与 Server 且默认无关闭选项。本项目**明令禁止**任何形式的运行时自更新（版本钉定 + 哈希校验，见 Phase 3 release manifest）。

### 7.5 Apple / macOS

- Full Disk Access 授予近乎全盘访问（含 Mail、Messages、Safari、Time Machine 备份）；Files & Folders 权限可按位置单独控制。
- Keychain 适用于存放小型持久秘密（密码、加密密钥）。
- 分发的二进制需 Developer ID 签名 + notarization，否则触发 Gatekeeper 警告。

---

## 8. 架构决策记录

### ADR-1 部署拓扑

**决策**：独立本地 MCP Server + 独立 Blender Bridge Add-on + Modeling IR 写入层 + Headless Worker。

**理由**：Codex 官方支持本地 stdio MCP 与逐工具审批；Blender 要求写操作在主线程串行且 operator 受 context 约束；三者只有分层才能同时满足。MCP Server 独立于 Blender 进程，使 Blender 卡死时协议层与审计层仍然存活。

**否决的替代方案**：

| 方案 | 否决理由 |
|---|---|
| MCP Server 内嵌 Blender | 故障域、协议面、主线程执行面绑死；Blender 卡死则审计一并失效 |
| 受控 CLI + Headless Worker 作为主方案 | 适合批处理，不适合 GUI 交互编辑与会话状态管理 |
| 直接生成并执行 Blender Python | 等同任意代码执行，违反 G3 |
| 声明式 IR 作为独立架构 | IR 不是传输层；缺少协议层与进程隔离则无法解决会话、鉴权、实例发现与主线程调度 |

**代价**：需维护 Server / Bridge / IR 三套版本号，以及 GUI 与 Headless 双栈测试。

### ADR-2 传输选择

**决策**：Codex ↔ MCP Server 用 **stdio**；MCP Server ↔ Bridge 用 **Unix Domain Socket**。

**理由**：本地单客户端场景 stdio 是官方推荐形态。UDS 避开额外网络监听面，天然本机地址族，可用目录与文件权限位约束访问。TCP / HTTP / WebSocket 会引入不必要的监听端口（违反 NFR-S3）。

### ADR-3 版本策略（D-1 / D-3）

| 项 | 决策 |
|---|---|
| Blender | 5.2 LTS on Apple Silicon 单栈；4.5 LTS best-effort、不进验收门槛；Intel 不支持 |
| golden render 基线 | 只维护一套，与 Blender 补丁版本绑定；Blender 升级即触发基线重录 |
| 版本分支方式 | 运行时能力探测（`describe_capabilities`），不做编译期双栈分支 |
| MCP 协议 | 本版目标 `2025-11-25`，SDK 钉 `mcp==1.28.x` |
| 长任务实现 | 服务端自铸 job 句柄 + 轮询工具，**不依赖 MCP tasks 扩展** |
| 确认交互 | Codex 逐工具 `approval_mode = "approve"`，**不使用 elicitation** |
| 日志 | 本地 JSONL + OpenTelemetry，**不使用 MCP logging** |
| `2026-07-28` 迁移 | Phase 1.5 独立工作项，预算 3–5 人日 |

### ADR-4 回滚语义（D-2）

**决策**：文件级快照是唯一有保证的回滚机制；接受"hard 回滚丢弃事务窗口内手动编辑"这一约束，以 FR-20 的 `pre-rollback` 快照缓解。

**理由**：`bpy.ops.ed.undo_push()` / `undo()` 在后台模式不可用、在非 UI context 下不可靠，不能承担事务回滚职责。

### ADR-5 重新评估触发条件

出现下列**任一**可观测信号时重新评估本架构：

1. 官方 Blender MCP 出现非任意代码执行的结构化工具面；
2. Blender Lab MCP 进入 Blender 正式路线图；
3. Codex 官方文档明确承诺支持 MCP tasks 扩展与更强的本地工具权限模型；
4. Codex 官方文档明确承诺消费 MCP **Resources / Prompts**——届时重估「场景快照经 Resources 承载、标准工作流经 Prompts 承载」以降低工具面与上下文占用（当前已核实 Codex 未承诺，故 V1 全部经 Tools）。

---

## 9. 不在本版范围内

- 任意 Python / Shell 代理
- 自由雕刻、笔刷轨迹
- Geometry Nodes 图合成（另注：5.2 变更了 GN modifier 属性 API）
- 动画与 rigging 全量支持
- 第三方资产自动下载与安装
- 远程 / 多用户共享控制
- **USD 与 FBX 导出** —— 本版导出格式白名单仅含 `gltf` / `obj` / `stl`
- 自相交检测（代价高，降级为可选检查项）
- MCP `2026-07-28` 规范适配（Phase 1.5）

---

## 10. 验收标准

### 10.1 Phase 0 —— 只读通道

- [ ] 在 5.2 LTS（钉定补丁版本）/ Apple Silicon 上，`get_blender_status` / `get_scene_summary` / `describe_capabilities` 均返回符合 outputSchema 的结果
- [ ] 连接非基线版本 Blender 时，只读工具可用、写工具被拒并返回 `UNSUPPORTED_BLENDER_VERSION`
- [ ] 强制终止 Blender 进程后 MCP Server 不崩溃，返回 `BRIDGE_UNAVAILABLE`；Blender 重启后自动重连
- [ ] 完整会话循环（enable → 允许连接 → 建连验证 → 断开 → disable）20 次，无线程泄漏、无残留 socket 文件——P0-D1 下裸 enable/disable 不建 socket，必须含会话启停才测到实体
- [ ] 传输 5 MB IR 载荷，分帧正确、无截断
- [ ] socket 自创建瞬间即位于 `0700` 目录下且自身为 `0600`；无 token 的连接被立即断开并记日志
- [ ] 全程 stdout 仅含 JSON-RPC
- [ ] MCP Server 冷启动 < 5 s

### 10.2 Phase 1 —— 事务化最小写入

四个 fixture 可重复通过：**平板桌 / 圆角盒 / 带孔支架 / STL 导出**。每个 fixture 须验证：

- [ ] 原 `.blend` 的 mtime 与内容 hash 未改变
- [ ] 同一 IR 提交两次，对象数不变
- [ ] 计划生成后手动移动一个对象再提交 → 返回 `SCENE_REVISION_CONFLICT`，场景未被改动
- [ ] hard 回滚后场景 hash 与回滚快照一致
- [ ] 事务期间手动移动对象后 hard 回滚：主场景恢复至快照状态，且 `pre-rollback` 快照存在并含该手动改动
- [ ] `begin_transaction` 输出含 `rollback_warning`
- [ ] hard 回滚（触发文件重载）后 Bridge 仍可服务后续请求
- [ ] 复制一个受管对象产生重复 `bcx.v1.id` → 返回 `STABLE_ID_COLLISION`
- [ ] 包围盒尺寸与计划声明值相对误差 < 0.5%
- [ ] MCP Server 被强制终止后重启，`list_transactions` 能列出未完成事务并成功 rollback
- [ ] 含外部纹理引用的工程：快照后纹理仍可解析，无 missing texture

### 10.3 Phase 2 —— 渲染与导出

- [ ] `render_preview` 执行期间 GUI 保持可交互（主线程占用采样 < 50 ms/次）
- [ ] `render_preview` 反映的是**提交时刻**的场景状态，而非事务起点状态
- [ ] 渲染中途 `cancel_job` → 60 s 内子进程终止、产生取消日志、无残留临时文件
- [ ] 单次工具调用阻塞时长均 < 60 s

导出重导入容差：

| 判据 | 阈值 |
|---|---|
| 包围盒尺寸 | 相对误差 < 0.1% |
| 单位 scale | 完全一致 |
| 对象数增量 | = 0 |
| 顶点数 | 按格式分别定义；STL 因三角化必然变化，改校验拓扑闭合性与体积 |
| golden render | SSIM ≥ 阈值，阈值与 Blender 完整版本号绑定 |

几何判据：

| 检查 | 实现 | 通过判据 |
|---|---|---|
| 非流形边 | `bmesh` + `BMEdge.is_manifold` | 计数 = 0 或不高于事务前基线 |
| 零面积面 | `bmesh` 面积 < ε（ε 随场景单位缩放） | 计数 = 0 |
| 孤立顶点 | `BMVert.link_edges` 为空 | 计数 = 0 |
| 重复顶点 | `bmesh.ops.find_doubles`（阈值随场景单位缩放） | 计数 = 0 或不高于事务前基线 |
| 法线一致性 | `bmesh` 面法线与相邻面点积符号统计 | 无翻转面，或不高于事务前基线 |
| 渲染有内容 | 组合判据：alpha 覆盖率在阈值区间 **且** 目标包围盒投影落在画面内 **且** golden render SSIM 达标 | 三者同时满足 |

> 单一的"非黑像素比例"判据不可用——纯黑材质的合法场景会被误判。

### 10.4 安全（全阶段，任一失败即阻断发布）

- [ ] 路径穿越（`../`、符号链接、`~` 展开后越界）全部 fail-closed
- [ ] IR 中夹带 `kind: "execute_python"` 或未知 kind → `UNSUPPORTED_OPERATION`，无副作用
- [ ] IR payload 夹带 schema 外字段 → 被 `additionalProperties: false` 拒绝
- [ ] 重放已完成的幂等键不产生第二次写入
- [ ] 两个并发事务写同一实例 → 第二个返回 `LOCK_CONFLICT`
- [ ] 无 token 的同 uid 进程无法通过 UDS 下达任何命令

---

## 11. 里程碑

| 阶段 | 内容 |
|---|---|
| **Phase 0** | 只读通道、实例发现、分帧 UDS + token 握手、审计日志、路径策略、主线程队列、确定性关闭、`describe_capabilities` |
| **Phase 1** | 事务化最小写入、IR 判别联合 schema、stable_id 防碰撞、两级回滚 + `pre-rollback` 快照、事务持久化、原子保存、自包含快照 |
| **Phase 1.5** | 迁移至 MCP `2026-07-28`：实现 `server/discover`、结果加 `resultType`、去 initialize 依赖、SDK 升 v2。预算 3–5 人日 |
| **Phase 2** | Headless 渲染 / 导出 / 重导入验证、job 句柄与取消（含 FR-35 状态机与心跳）、golden render 基线 |
| **Phase 3** | Geometry Nodes、更多 modifier、签名公证安装器、持续回归；release manifest（版本 + schema/模板/依赖哈希 + 签名）；资产 LINK/APPEND 策略与资产清单；BVH 间隙/穿插等空间检查（可选） |

---

## 12. 风险与待验证事项

### 12.1 已识别风险

| ID | 风险 | 影响 | 缓解 |
|---|---|---|---|
| **R-01** | Blender 5.2.0 于 2026-07-14 发布，LTS 的 `.0` 通常伴随 corrective release | 基线不稳，golden render 需重录 | 钉定补丁版本；版本号写入 Validation Report |
| **R-02** | EEVEE 不支持 macOS headless 渲染 | 若预览走 EEVEE，headless 路径直接失败 | FR-25 固定 Cycles；Phase 0 实测确认 Cycles Metal 在 `--background` 下的设备选择行为 |
| **R-03** | `save_as_mainfile(copy=True)` 与 `relative_remap` 均存在破坏相对纹理路径的已知缺陷 | 快照缺纹理 → 渲染与导出验证结果不可信，且**失败方式是静默的** | FR-24 要求快照前打包资源；Phase 1 验收含"含外部纹理引用工程"用例 |
| **R-04** | `open_mainfile`（hard 回滚）会释放全部 bpy 数据并可能清除非 persistent timer | 回滚后 Bridge 失联 | NFR-R5 / NFR-R6；Phase 1 验收含回滚后可用性用例 |
| **R-05** | **已发生（2026-08-06 复核）**：`2026-07-28` 已发布，SDK v1.x 仅接收安全修复，`pip install mcp` 默认装 2.x | 不钉上界会被静默升到 v2；v1 安全修复窗口有限 | 依赖钉 `mcp>=1.28,<2`（计划已含）；Phase 1.5 优先级**上调**——建议 Phase 1 完成后立即执行 |
| **R-06** | 受管对象被复制（Duplicate / Alt+D / Make Real / Append）会连同 `bcx.v1.id` 一起复制 | stable_id 唯一性被破坏，写操作可能作用于错误对象 | FR-10 三处检测 + 人工消歧，不自动猜测 |
| **R-07** | `bcx.v1.id` 作为用户自定义属性在 UI 中可见可编辑，可能被用户改动或与自有属性冲突 | 受管对象失联 | 命名空间前缀降低冲突概率；FR-10 检测缺失与重复 |

### 12.2 待验证（不阻塞启动）

| ID | 事项 | 处理方式 |
|---|---|---|
| **V-01** | `agents/openai.yaml` 中 **stdio 型** MCP 依赖的声明字段（官方示例仅给出 `streamable_http`） | Phase 0 实测。在此之前 Skill 不依赖自动接线，安装文档直接提供 `codex mcp add` 命令 |
| **V-02** | Codex 启动的第三方 MCP Server 子进程是否继承 Codex sandbox | 不影响实现——NFR-S2 要求路径策略独立成立。仅影响安全文档措辞 |
| **V-03** | Cycles Metal 在 `blender --background` 下的 GPU 设备枚举与选择行为 | Phase 0 实测；失败则降级 CPU 渲染并降低 golden render 分辨率 |
| **V-04** | `bpy.app.timers` 的 `persistent=True` 在 `open_mainfile` 前后的确切存活行为（官方文档未明确说明） | Phase 1 实测；无论结果如何均需实现 NFR-R6 的自愈重注册 |

---

## 13. 变更记录

### v1.1（2026-08-06）

触发：对外部研究报告《构建生产级 Blender AI Skill》（2026-08-06）的核查采纳 + Phase 0 spec §10 挂账修订的正式落账 + 外部约束时效复核。

**采纳自外部报告（经核实或属通用工程实践）**：FR-34（server instructions，Codex 消费该字段已在 2026-07-23 核实）、FR-35（job 状态机与心跳）、FR-33 增强（改前改后 revision、result_digest、审批记录）、NFR-R7（OperatorAdapter 模式）、NFR-C5（AGENTS.md 模板交付）、§10.3（重复顶点、法线一致性）、§11 Phase 3（release manifest、资产策略、BVH 检查）、§7.4 生态补充与供应链反例、ADR-5 触发条件 4。

**拒绝采纳（记录原因）**：① 场景快照经 MCP Resources / SOP 经 Prompts 承载——MCP 语义正确，但已核实 Codex 未承诺消费，列入 ADR-5 触发条件 4 待重估；② 每个写工具携带 `dry_run`——与 FR-06「唯一 dry-run 入口」的既有决策冲突，维持原决策；③ Streamable HTTP 远程部署——超出本版「本机单用户」范围（NFR-S3）；④ 报告对 MCP 传输的描述（会话 ID、SSE 断线恢复）沿用 `2025-11-25` 语义，已被 `2026-07-28` 移除，属报告时效缺陷，不采纳。

**落账 Phase 0 spec 的挂账修订**（spec §10 表 6 项 + spec §2.2 的 NFR-S4 机制表化；spec §10 中 get_scene_summary schema 一行不涉及 URS 文本，未列入）：术语表 `scene_revision`（整数、会话内）与 `scene_hash`（全场景）重定义、新增 `plan_scope_hash` 词条、FR-11 权威依据改为 `plan_scope_hash`、NFR-S4 权限机制表化、NFR-S5 token 保证下调、NFR-O2 OTel 推迟声明、FR-32 取消中心注册表。

**外部约束复核（§7.2）**：MCP `2026-07-28` 已发布；Python SDK v2.0.0 稳定、v1.x 维护期、`pip install mcp` 默认 2.x；R-05 相应更新，Phase 1.5 优先级上调。

---

## 附录 A：来源

**MCP**：[2026-07-28 正式版公告](https://blog.modelcontextprotocol.io/posts/2026-07-28/) · [Python SDK v2.0.0 Release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0) · [Versioning](https://modelcontextprotocol.io/specification/versioning) · [Draft Changelog](https://modelcontextprotocol.io/specification/draft/changelog) · [2026-07-28 RC](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) · [SDK Betas](https://blog.modelcontextprotocol.io/posts/sdk-betas-2026-07-28/) · [Python SDK](https://github.com/modelcontextprotocol/python-sdk)

**Codex**：[MCP 配置](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) · [Build skills](https://learn.chatgpt.com/docs/build-skills.md) · [Customization](https://developers.openai.com/codex/concepts/customization)

**Blender**：[5.2 LTS 发布](https://www.blender.org/press/blender-5-2-lts-release/) · [LTS 计划](https://www.blender.org/download/lts/) · [系统要求](https://www.blender.org/download/requirements/) · [5.0 Python API](https://developer.blender.org/docs/release_notes/5.0/python_api/) · [5.2 Python API](https://developer.blender.org/docs/release_notes/5.2/python_api/) · [Intel 构建移除](https://devtalk.blender.org/t/deprecation-and-removal-of-macos-intel-builds-in-blender-5-0/38835) · [bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html) · [GPU Rendering](https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html) · [创建扩展](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html) · [Add-on 指南](https://developer.blender.org/docs/handbook/extensions/addon_guidelines/) · [MCP Server (Lab)](https://www.blender.org/lab/mcp-server/) · [save_as_mainfile 相对路径缺陷](https://developer.blender.org/T33108)

**Apple**：[Notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) · [Keychain](https://developer.apple.com/documentation/security/storing-keys-in-the-keychain) · [文件访问控制](https://support.apple.com/guide/mac-help/control-access-to-files-and-folders-on-mac-mchld5a35146/mac)
