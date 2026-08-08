# Blender × Codex 安全自动化系统 · 需求规格说明书

| 项 | 值 |
|---|---|
| 版本 | v1.17 |
| 日期 | 2026-07-23（v1.0）· 2026-08-08（v1.17：r18 Task 3 测试/来源修正） |
| 状态 | 已评审；决策 D-1 / D-2 / D-3 / **D-4（官方 MCP 重评与边界澄清）** / **D-5（MCP SDK v2）** 已确认；当前为交付目标与隔离预检，**Phase 0 尚未执行**；变更记录见 §13。项目所有者已接受三项平台候选；重启后当前模型面与宿主目录均为 26/26，并以“当前用户接受风险”关闭 G5。该关闭是对 screenshot 顺序敏感性与 deferred render `SIGABRT` 的知情风险接受，**不是缺陷已修复或 26 工具稳定性证明**。r17 已 attested，但因 Task 3 空洞同输入测试的评审发现被 r18 supersede；当前 r18 仍为 proposed，须经精确 SHA/计数审批后方可提交或执行 |
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

**当功能覆盖度与 G1–G3 冲突时，删减功能。** G1–G3 只约束 §1.3 定义的 Blender-Codex 安全自动化系统，不得把外部兼容通道的能力或证据计入本系统合规结论。

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

用户另行明确授权启用的 **Blender Lab 官方 MCP** 是并存的兼容/验证通道，不属于上图四层，也不继承本系统的 G1–G3、FR-04、审计或事务保证。其 26 个工具包含任意 Python 执行能力，因此该通道本身**不满足 G3**；任何测试或交付报告都必须分别标注“自定义安全系统”与“官方兼容通道”，不得合并宣称合规。

---

## 2. 术语定义

| 术语 | 定义 |
|---|---|
| **Modeling IR** | 版本化声明式中间表示，所有写操作的唯一表达形式 |
| **stable_id** | 受管对象的稳定标识，存于自定义属性 `bcx.v1.id`，独立于 Blender 对象名 |
| **scene_revision** | 会话内单调递增**整数**，由 `depsgraph_update_post` 递增，Bridge 重启后归零。**仅用于会话内快速变更检测**；跨会话比对一律用 hash |
| **scene_hash** | 场景**结构摘要 v1**：对每个对象取 `(name, object type, 量化至 1e-6 的 matrix_world, obj.data 的 RNA 类型标识与计数)`，排序后 SHA-256；无 data 时类型标识为空字符串。跨进程、跨文件重载有效。**盲区（v1.2 审计实测）**：顶点坐标/拓扑/modifier/材质/可见性/collection/相机灯光/场景设置不可见——只用于粗粒度变更检测与快照标识；**禁止**单独作为跨会话等价或验收证据；不用于冲突判定 |
| **plan_scope_hash** | 仅覆盖 IR 的 `target` / `depends_on` 涉及对象的摘要，**冲突判定的唯一权威依据**（Phase 1 交付）。**v1.2 起要求**：除结构行外必须纳入目标对象的**几何摘要**（量化顶点坐标 + 拓扑连接 + modifier 栈及参数）——依赖集小，成本可控；否则顶点级手动编辑逃过冲突检测，US-B3 失守 |
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
| 8 | `begin_transaction` | 状态变更 | 否 | prompt | 否 |
| 9 | `apply_modeling_plan` | 写 | **是** | prompt | **是 → job** |
| 10 | `create_primitive` | 写 | **是** | prompt | 否 |
| 11 | `finalize_transaction` | 写 | **是** | prompt | **是 → job** |
| 12 | `render_preview` | 任务 | 否 | auto | **是 → job** |
| 13 | `cancel_job` | 状态变更 | 否 | auto | 否 |

### 5.2 需求条目

#### 观察与能力发现

| ID | 需求 | 优先级 |
|---|---|---|
| FR-01 | 提供 `get_blender_status`、`get_scene_summary`。`get_scene_summary` 接受 `include_collections` 与 `include_managed_objects` 两个布尔开关（默认 `true`）；MCP adapter → UDS `scene_summary.params` → Bridge Router → `SceneReader.snapshot_steps()` 必须逐层传递，`false` 必须在 reader 数据源处跳过对应枚举，不得先枚举再在响应层裁剪。单次 object/collection 源各自最多 1,000,000 项与 64 MiB 文本；超限返回 `INTERNAL_LIMIT_EXCEEDED`，不得静默截断 | P0 |
| FR-02 | 提供 `describe_capabilities`：返回 IR schema 版本、支持的 operation kinds、Blender 完整版本号、Server / Bridge 版本 | P0 |
| FR-03 | 握手时检测 Blender 版本；非基线版本（见 NFR-C2）时只读工具可用，**所有写工具拒绝**并返回 `UNSUPPORTED_BLENDER_VERSION` | P0 |

#### 写入路径

| ID | 需求 | 优先级 |
|---|---|---|
| FR-04 | 本系统的场景写入**只能**经由版本化 Modeling IR。本系统不得暴露任意 Python / Shell / 通用文件系统 / 网络下载工具；§1.3 的外部兼容通道不计入本系统工具面，也不得作为绕过路径写入本系统事务 | P0（红线） |
| FR-05 | IR 的每个 `operation.payload` 按 `kind` 做判别联合（`oneOf` + `if/then`），每个 kind 一个封闭 payload schema（`additionalProperties: false`）。**不得存在 `payload: {type: object}` 这类开放定义** | P0 |
| FR-06 | 提供 `validate_modeling_ir` 作为**唯一** dry-run 入口；`apply_modeling_plan` **不提供** `dry_run` 参数 | P0 |
| FR-07 | 提供 `create_primitive`，内部展开为单操作 IR，审计日志记录展开后的 IR | P1 |
| FR-08 | 提供 `apply_modeling_plan`，仅在事务上下文内可调用 | P0 |

#### 标识与一致性

| ID | 需求 | 优先级 |
|---|---|---|
| FR-09 | 受管对象标识存于自定义属性 `bcx.v1.id`。对象名仅用于展示与降级回退，**不得作为查找依据** | P0 |
| FR-10 | 重复 `bcx.v1.id` 检测：在 `begin_transaction`、`apply_modeling_plan` 完成后、`validate_scene` **三处**均须执行。发现重复立即返回 `STABLE_ID_COLLISION`，要求人工消歧，**不得自动猜测** | P0 |
| FR-11 | 冲突检测以 **`plan_scope_hash`** 为权威依据（`scene_hash` 是**结构摘要 v1**，覆盖面窄且对无关对象敏感，两头都不适合判定；`scene_revision` 仅作会话内快速路径）。IR 携带的 plan_scope_hash 与执行时不符即拒绝写入，返回 `SCENE_REVISION_CONFLICT` | P0 |
| FR-12 | 幂等键由**服务端派生**：`SHA-256( canonical_json(IR \ 易变字段) ‖ plan_scope_hash )`。**IR 自身不得携带 `idempotency_key` 字段**，避免定义循环。**v1.3 补充（复审 F-10）**：① 幂等键绑定 `plan_scope_hash` 而非 `scene_hash`——后者看不到顶点/材质/modifier，顶点编辑后重放会被误判为「已完成」并返回旧结果；② **执行顺序固定为「先冲突/预条件校验，后幂等查询」**，不得颠倒 | P0 |
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
| FR-21 | 原始 `.blend` 永不被覆盖。提交产物写入新路径，经临时文件 + `os.replace` 原子替换。是否写到原文件不得用路径字符串或未绑定 fd 的 `Path.stat` 查询决定；Phase 1 必须在 `O_NOFOLLOW`/dir-fd 打开的文件描述符上校验并在提交边界重新校验 `(st_dev, st_ino)`，任何无法建立 identity 的错误均 fail-closed。`same_file()` 只能作查询辅助，不能替代 TOCTOU 防线 | P0（红线） |

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
| FR-30 | 所有路径经 `expanduser` → `realpath` → root containment → 扩展名白名单，**fail-closed**。**v1.2 附注（TOCTOU）**：该校验是前置过滤，非写入安全边界；Phase 1 实际写入必须 fd-based（`O_NOFOLLOW`/dir-fd `openat`、同目录临时文件 + 原子 rename，授权绑定已打开 fd） | P0 |
| FR-31 | Bridge 的 UDS 端点置于应用自有、精确 `0700` 的 runtime/run/session 目录下，socket 文件 `0600`，并要求每会话随机 token 握手。会话叶目录必须独占创建，不能接管同名既存目录 | P0 |
| FR-32 | 多实例支持：每会话独立目录 + `session.json`（`instance_id` 必须与目录 basename 全等，`socket_path` 为权威字段；socket 与父目录的四个 dev/inode 字段全部必填），Server 扫描 `run/` 发现；stale 清理用双条件判据 + 宽限期。枚举时记录目录 dev/inode，读取时以 `O_DIRECTORY|O_NOFOLLOW` 绑定 dir-fd 并相对打开 `session.json`；跨调用复用扫描 cursor 前必须重新确认 cursor fd 与当前 `run/` identity 一致，部分/缺失 socket identity 或 cursor 换入均 fail-closed 并标记 partial；清理只允许对同 identity 目录删除已知会话文件，**不得递归删除换入或未知目录树**。`socket_path` 仅允许会话叶目录内的 `bridge.sock` 或确定性回退 `/tmp/bcx-<sha256(instance_id)[:16]>/bridge.sock`；不得依赖两进程可能不同的 `$TMPDIR`。发布后在 `session.json` 记录 socket 与回退目录 identity，发布前崩溃则用确定性路径 + 当前 uid + `0700` + 宽限期判据回收。cleanup 可部分完成：已完成且 identity 匹配的已知叶项可 unlink；未知 child 只阻止最终 `rmdir`，不回滚已完成 unlink；identity 不符或 absolute deadline 耗尽时保留替换物与会话证据并标记本轮 partial，后续扫描重试。**不设中心注册表** | P1 |
| FR-33 | 逐次调用审计日志（JSONL）：`request_id` **定义为入站 JSON-RPC request 的 `id`（不另行生成）并保留 string/integer 原类型，不得 `str()` 化**、工具名、参数摘要、结果、涉及路径、耗时、事务 ID。日志目录初始化须 race-safe create-or-validate；既存目标经 `lstat`/`O_NOFOLLOW|O_NONBLOCK`/`fstat` 验证为当前 uid 的 `0600` regular file，否则 fail-closed。并发调用的每条 JSONL 必须完整：进程内序列化，多个 MCP Host 进程共享 runtime 时使用文件锁。每次调用先执行业务 core budget，再运行独立的 audit postlude（预算 ≤1 s）；初始化、锁、write、flush、close 任一步失败或完成 I/O 后发现越过 deadline，均 **fail-closed** 返回 `AUDIT_UNAVAILABLE`，可覆盖业务结果。**Phase 1 起写工具另记**：`scene_revision_before/after`、结果摘要 `result_digest`、审批决定、tool schema 版本 | P0 |

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
| NFR-S4 | 权限边界从 `BLENDERCODEX_ROOT` 开始；其上方用户既存祖先不改权限。应用自有 `runtime_root`、`run/`、`logs/` 必须 race-safe 创建为或验证为当前 uid 所有、非 symlink、精确 `0700`，否则 fail-closed；会话叶目录必须以 exclusive `mkdir(0700)` 新建。新文件以 `O_EXCL` mode `0o600` 创建并显式收紧；既存审计文件只在 `lstat` 与同 fd `fstat` 均证明为当前 uid 的 `0600` regular file 后追加。socket bind 后立即 chmod `0600`。**不得使用进程级 `os.umask`**——Blender 是共享进程 |
| NFR-S5 | token 的作用是**提升攻击成本并实现凭据轮换**：把攻击从「扫描 socket 盲连」提升为「须定位并读取 0600 会话文件」。同 uid 进程可读取该文件，token **不能**阻断同 uid 越权；真正压缩风险的是显式会话窗口（用户主动开启才监听）。文件权限只防其他 uid |
| NFR-S6 | 短时会话 token 存 `0600` runtime 文件，随进程销毁。仅持久秘密（OAuth、渲染农场凭据）使用 Keychain |
| NFR-S7 | 分发二进制 / GUI 壳需 Developer ID 签名 + notarization |
| NFR-S8 | Bridge 扩展**不得**在运行时安装 Python 模块（Blender 扩展指南明令禁止）。Bridge 保持零第三方依赖，仅用 stdlib；JSON Schema 等重校验全部置于 MCP Server 侧 |
| NFR-S9 | Bridge 侧执行结构性校验（kind 白名单、必填字段、类型检查），不因 MCP Server 已校验而略过 |

### 6.2 可靠性（R）

| ID | 需求 |
|---|---|
| NFR-R1 | Blender 写操作严格在主线程串行执行。IPC 线程只负责收包、鉴权、入队 |
| NFR-R2 | Bridge 的关闭必须确定性回收线程、监听/活跃连接与 socket 文件。I/O 线程与唤醒 `socketpair` 两端均须非阻塞；`_wake_pending` 合并唤醒风暴，循环边界必须重查停止标志，停止通过唤醒 fd 打断 `select`，不得以标志位配合阻塞 `accept()` 实现。活跃连接上限 64；全局未成帧入站上限 32 MiB；单请求 payload 上限 64 KiB；outbox 单连接 32 MiB、全局 64 MiB，均 fail-closed。accept 后未完成登记及 close 失败的 socket 必须保留 ownership 并重试；发送查找须防 fd 数字复用。创建后记录 session/fallback 目录及 socket/session 文件 dev/inode；清理只删除同类型、同 identity 的自有路径或空目录，换入目标一律保留。首次 join 最长 2 s；关闭活跃连接与监听/socketpair 后必须进行第二次 join（最长 1 s）确认 I/O 线程退出；transport 未完全关闭时不得删除 socket/session 路径，`stop()` 返回 false 并由 driver/UI 保留引用供重试。该回收承诺限定于普通本地非阻塞 I/O，不把内核中已进入的不可中断调用表述为绝对墙钟保证。生命周期回调必须覆盖 timer、`depsgraph_update_post` 与 `load_pre` 的注册/注销，并保持 spec §3.7 的停止顺序 |
| NFR-R3 | IPC 采用显式分帧（4 字节大端长度前缀 + UTF-8 JSON 文本）。**不得假设单次 `recv()` 收全消息**，两端均须循环读满；拒绝非法 UTF-8、畸形 JSON 与超过实现深度上限的深层嵌套，并在同一次 `recv()` 批次中首帧拒绝后不得派发其后的帧。对象/数组/字符串/number/boolean/null 按 JSON wire 类型处理；number 必须有限，收发两端拒绝 `NaN` / `Infinity` / `-Infinity` 与解析溢出为无穷的数值。信封类型必须精确校验：`v` 是 exact integer，`ok`/`retryable` 是 exact boolean；不得利用 Python `bool <: int` 或隐式字符串/数字转换。只有“字段存在且为 exact integer、值不等于 1”才映射 `ENVELOPE_VERSION_MISMATCH`；缺失、boolean、string 等畸形 `v`，以及畸形 `id/ok/result/error/retryable`，统一映射为 retryable `BRIDGE_UNAVAILABLE` 并 fail-closed |
| NFR-R4 | 主线程 timer 回调采用 **50 ms cooperative checking budget**：在每个 handler/continuation step 前后检查预算并分片，且不得把它表述为绝对墙钟上界。单个 Python、bpy、原生调用或最终 bytes 构造不可抢占；诚实边界为 `50 ms + 有界原子 step 成本 + 调度抖动`。无法证明单步有界的工作必须转交 Headless Worker |
| NFR-R5 | 主线程任务队列**不得跨文件重载持有 bpy 数据引用**。continuation yield 之间只能保存纯 Python 游标与 scene identity；每个 step 重新取得 wrapper 并立即转成纯 Python 值。`load_pre` 必须在 Blender 释放旧数据前使所有 continuation 失效 |
| NFR-R6 | Bridge 的 timer、`depsgraph_update_post` 与 `load_pre` handler 均须以 persistent 机制注册，并具备重载后的自愈重注册路径（hard 回滚会触发文件重载）。`load_pre` 先递增持久 generation 标记；continuation 的 generation/revision marker 不匹配时结构化终止，不得继续访问旧 bpy 数据 |
| NFR-R7 | 优先使用 Data API（`bpy.data.*.new()` + `collection.objects.link()`）。必须使用 operator 时经**统一 OperatorAdapter**：显式 `temp_override` 构造 context、调用前检查 `poll()`、保存并在 `finally` 中恢复 Mode 与 Selection、将 `FINISHED`/`CANCELLED`/异常转换为结构化结果（Phase 1 实现指引） |
| NFR-R8 | Blender 崩溃或 Bridge 断连后可恢复；已提交事务的持久状态不丢失 |
| NFR-R9 | Bridge 每实例 `scene_summary` 的 queued + active continuation 合计最多 2；Server adapter 进程级 scene-summary 准入同为 2，且必须覆盖 SDK v2 完整 `call_next`（reader、结果转换、structuredContent/wire shaping 与 audit postlude）。第三个 wire 请求 fail-fast 返回 retryable `BRIDGE_BUSY`，不得阻塞 async 事件循环；异常、超限、审计失败与成功均释放槽位。两层上限独立，不宣称相乘后即为全系统内存上界 |

### 6.3 性能（P）

| ID | 需求 |
|---|---|
| NFR-P1 | 在固定基线机上，三个只读工具各执行**恰好 20 次**完整 MCP `tools/call`，分别计算 nearest-rank P95（20 个排序样本中的第 19 个），每项均须严格 `< 2 s`；不得重试、删除慢样本或用 Bridge-only 指标替代。计时从每次 SDK `Client.call_tool()` 前开始，到 SDK 返回 `structuredContent` 且对应 Pydantic 模型与语义断言完成后结束，覆盖 stdio、SDK middleware、adapter、Discovery（适用时）、UDS/Bridge、结果转换与 audit postlude。`get_scene_summary` 固定使用 100k 真 GUI 场景且两个 include flag=false；`get_blender_status` 固定选择已连接真 GUI 实例；`describe_capabilities` 在独立空 root、`include_instances=false` 下证明离线。初始化和 fixture 构造不计入 P95；正式证据合同见下文，不得以 helper 自报布尔或 64-hex 外形检查代替外部复算 |
| NFR-P2 | MCP Server 冷启动 < 5 s（Codex `startup_timeout_sec` 默认 10 s） |
| NFR-P3 | 单次工具调用阻塞时长 < 60 s（Codex `tool_timeout_sec` 默认 60 s）。超出者一律走 job 模式 |
| NFR-P4 | 长任务须有超时与内存上限；超限产生日志并终止，不得静默挂死 |
| NFR-P5 | 同一 Server 版本与 capability profile 下，公开 `tools/list` 的名称、完整定义与顺序必须确定，固定为 `get_blender_status` → `get_scene_summary` → `describe_capabilities`；不得按实例状态、调用历史或回合动态增删/重排。Phase 0 正式 artifact 必须保存并可复算 wire Server identity/version、Server `instructions`、ordered catalog/schema 的 UTF-8/canonical bytes+SHA，以及 60 次调用中 `structuredContent` 与兼容 TextContent 的原文、JSON 等价性、各自 bytes/SHA、合计双内容 result payload 与 duplication ratio。该合计只证明 SDK/transport result 中两份内容的字节上界，不证明目标 Codex Host 把两份都注入模型；byte 不冒充 token。未经同模型/同推理配置/同 fixture 的 Host A/B，不设 Token 降幅或工具数量经验门槛 |

#### NFR-P1 正式证据合同

- **独立预算**：NFR helper 的 work deadline 为 `165 s`，从 helper spawn 后覆盖 provenance 与 60 次调用；GUI runner 从该次 spawn 起使用单一 `180 s` outer deadline，最后 `15 s` 是统一 cleanup 预算（TERM worker 最多 8 s、TERM 已登记 groups 最多 3 s，并至少保留 2 s 给 KILL/reap），各阶段不得重新开窗。NFR runner 与 recovery supervisor 均在 `poll()` 前后检查 absolute deadline，边界后才观察到的 `returncode=0` 仍失败。recovery 的 hidden worker work deadline 为 `120 s`，public OS supervisor 从安装 non-raising SIGINT/SIGTERM flag handler 前开始使用 `135 s` absolute deadline；取消、超时、leader-exit child 与截止点仍存活 group 均进入同一 TERM→KILL→worker/group liveness→registry cleanup，截止点 final KILL 不重开等待窗。worker 内 `asyncio.timeout()` 不是外层硬监督器。100k fixture 构造及其 20 次 Bridge-only 查询发生在 NFR helper spawn 前，既不计入 P95，也不受 165/180 s helper 窗口约束；本版不宣称完整 GUI Task 18 具有另一个全局墙钟上限。
- **进程证据**：每次 invocation 使用 fresh、当前 uid、精确 `0700` 的私有 registry 和 128-bit（32 lowercase hex）随机 marker。parent 在任何独立 process-group spawn 前先创建 identity-bound `0600` reservation；child 的首个项目脚本必须是纯 stdlib bootstrap，在加载 MCP/Blender 重依赖前发布 exact-key/exact-type `schema_version=1`、`pid`、`pgid`、`marker`、`started_monotonic_ns` 与 opened dev/inode record，再完成 reservation；若参数构造、SDK client enter 或 `Popen` 在 record 发布前失败，parent 必须按 reservation 的 opened dev/inode 清理。observer 只读，不得删除 owner record；owner retire/publication rename 导致枚举后的单 entry 消失时标 pending 并重扫。`MAX_RECORDS=8` **只限制已验证可信 record cache，不是目录 entry 枚举上限**；formal scanner 由调用方共享 absolute deadline、单 record 4096-byte 上限与私有目录边界限界，unknown/identity/schema 单项错误须记首错并继续枚举，所有第 9 条及后续有效 overflow 都必须在 identity 复核后立即 KILL，不得遗忘后续可信组。leader PID 退出不代表 group 清洁；检查 recorded PID 后，PID 已复用到不同 PGID必须 fail-closed，PID 消失才检查旧 PGID 是否仍有 orphan child。cleanup 固定 TERM→KILL→确认 group gone→unlink 前再次核 record inode；public recovery 在 work 期持续预观察，并从 15 s cleanup margin 中固定保留 5 s 给 registry。marker/stale/PID-PGID reuse/record 换入/reservation/inflight publication/observer-owner race/cache overflow 均须有直接反例且不得误 signal/unlink。旧 group 完全消失后同数值 PID+PGID 被完整复用，以及最后一次 liveness/identity 检查后的同 UID 主动换入，仍是 POSIX 无法由裸 PGID/path 消除的明确边界。
- **provenance 与批准链**：先证明 Git worktree clean，再从具有 stdout byte cap 与 absolute deadline 的 `git ls-files -z` 枚举至多 512 个 tracked 源；`pyproject.toml`、`uv.lock`、attestation 与四份批准文档等 required 输入必须确为 tracked。ignored vendor 只允许生成器声明的 exact 目录/文件集合，不得有 `.so`/pyc/symlink/额外项，且每个 vendored Python 文件须与 `protocol/` 同 hash。所有读取使用 no-follow/nonblocking fd，`fstat` 必须为 regular file；单源文件 ≤16 MiB、实际读取合计 ≤128 MiB。post-freeze attestation 使用 exact-key/exact-type schema；Plan/URS/spec/ROADMAP 的 live SHA、approved tuple SHA 与 `source_commit` blob SHA 必须三者全等，同时精确固定 20 Tasks、open/checked checkbox、Python fence、path-bound/unique Python 及最终 unit/contract/full/adapter 门禁计数。missing/extra key、bool 冒充 int、任一文档漂移或祖先链不符均拒绝。
- **catalog、样本与 audit 可复算性**：live/offline 两个 fresh Server 均重复请求 `tools/list`，保存并证明 ordered catalog 完整定义/顺序相同；artifact 保留 catalog/schema canonical preimage、`instructions` 原文及其 bytes/SHA，并与 Task 17 的冻结值全等。另保留 60 个 canonical validated-result preimage及对应兼容 TextContent 原文；structured preimage 每项 ≤256 KiB、跨三个工具合计 ≤16 MiB，单个正式 artifact JSON ≤32 MiB。外部验证器必须重新运行对应 Pydantic model 与语义断言，证明 TextContent JSON 与 `structuredContent` 等价，复算两者各自 bytes/SHA、合计双内容 result payload、duplication ratio，并核对 exact-type arguments 及其自身 digest、20 个原始 duration、非 bool finite/non-negative P95/max、`p95_method=nearest_rank`、第 19 个样本、代表结果与全局 byte total；helper 自报 `validated=true` 或 digest 的 64-hex 外形不构成证据。双内容 result 合计不等于实际 model-visible 字节，后者须经目标 Codex Host/prompt capture 另行验证。主 root 40 行、离线 root 20 行及 recovery audit 使用 shared deadline、no-follow regular file、文件数/单文件/总量/单行/行数上限逐行复核；FIFO、symlink、partial line 与 oversize 均拒绝。
- **同一会话**：recovery 在 Blender A kill 前、kill 后及 Blender B 重启成功后，分别重新读取唯一 MCP record；`(pid, pgid, marker, started_monotonic_ns)` 必须完全一致并写入 artifact，外部验证器再次比较。常量 `same_mcp_server_session=true` 不构成证据。
- **归因入口**：正式 artifact 绑定 clean Git HEAD/tree、上述获批 tuple 与两提交 attestation 链、`uv.lock`、关键源码 manifest、Blender exact build 和 execution manifest；SHA sidecar 只证明文件完整性，不能替代 provenance。

### 6.4 可观测（O）

| ID | 需求 |
|---|---|
| NFR-O1 | stdio 传输下，stdout **仅**承载 JSON-RPC。所有日志写 stderr 或独立文件；验证器在目标响应后仍须进行有界 tail-drain，直到 EOF 或 quiet timeout settle，延迟非目标事件/半行/洪泛仍计入污染，且继续服从单行、累计缓冲、事件与消息上限 |
| NFR-O2 | 不使用 MCP logging 特性（2026-07-28 规范已弃用）。Phase 0 交付本地 JSONL 审计；OpenTelemetry 与 `traceparent` 传播推迟至 Phase 1（Phase 0 spec §1.2 已声明） |
| NFR-O3 | 审计日志脱敏：不记录完整文件内容，路径按工作区根做相对化 |

### 6.5 兼容性（C）

| ID | 需求 |
|---|---|
| NFR-C1 | 支持面 = macOS 14+ / Apple Silicon。Intel Mac 不在本版支持范围 |
| NFR-C2 | Blender 生产基线 = **5.2 LTS 单栈**，钉定具体补丁版本（不写 `>=5.2`）。4.5 LTS 兼容为 best-effort：不刻意破坏，但不测试、不承诺、不进验收门槛 |
| NFR-C3 | Server 解释器声明 **`>=3.13,<3.14`**，与 Blender 5.2.0 内置 Python 3.13.13 对齐；不得让 uv 自动漂移到 3.14（深层 JSON/递归失败行为已实测不同）。**Python SDK 钉 `mcp>=2.0,<3`（决策 D-5）**；SDK v2 必须同时服务当前 Codex 实测的 `2025-06-18`、legacy 合同 `2025-11-25` 与 SDK 直连 `2026-07-28`，协议 rollout 与 SDK 版本解耦。协议适配收敛于 ≤ 375 行 adapter 层；v7 隔离实现实质代码为 373 行 |
| NFR-C4 | Server / Bridge / IR 三者独立版本号，握手时协商；不匹配则拒绝并返回可读原因 |
| NFR-C5 | Codex Skill 置于 `.agents/skills/<name>/`；`agents/openai.yaml` 中设 `policy.allow_implicit_invocation: false`；`description` ≤ 200 字符、触发词前置；schema 与策略正文置于 `references/`。Skill 交付物**另含 `AGENTS.md` 模板片段**（Blender 版本矩阵、先检查后修改、禁任意 Python、长任务须走 job）供用户仓库采用（Phase 1 与 Skill 同批交付） |
| NFR-C6 | `AGENTS.md` 只承载仓库/测试约定；Skill 承载 Agent 决策与按需 reference 路由；MCP `instructions` 只承载跨工具运行合同；单工具 schema/description 只承载选择与调用语义；可机器强制的 Blender context/validation 规则落在 Server/Addon。规范性规则只设一个权威定义，其余层引用，不复制成多份易漂移正文 |

---

## 7. 外部约束（已核实）

以下事实约束本设计，与实现选择无关。核实日期 2026-07-23，**§7.1/§7.2 于 2026-08-08 复核更新**；来源见附录 A。

### 7.1 Codex

- 仅支持 **stdio** 与 **Streamable HTTP** 两种 MCP 传输。
- 配置项：`enabled_tools`、`disabled_tools`、`default_tools_approval_mode`（`auto` / `prompt` / `writes` / `approve`）、逐工具 `approval_mode`、`startup_timeout_sec`（默认 10）、`tool_timeout_sec`（默认 60）。其中 `prompt` 总是请求批准，`writes` 对未标记只读的工具请求批准，`approve` 是预先批准、从不弹工具审批；名称不得按自然语言反向理解。
- 提供 `codex mcp add / list / get / remove / login / logout` 子命令，无需手写 `config.toml`。
- Skill 发现路径按优先级：仓库 `.agents/skills` → `$HOME/.agents/skills` → `/etc/codex/skills` → 内置。
- `policy.allow_implicit_invocation` 默认 `true`。
- Skill 列表占用上下文预算上限 2%（未知时约 8000 字符），超出则 description 被截断、skill 可能被省略。
- 官方文档**未承诺**支持 MCP 的 Resources / Prompts / Roots / Sampling / Elicitation / Tasks。
- Codex 会读取 Server `instructions`，且官方要求前 512 字符自包含；OpenAI prompt-caching 指南把 tool definitions/schema/顺序列入可缓存前缀，顺序或定义变化会破坏 exact-prefix 命中。该结论只支持“稳定 catalog”，不证明某次请求必然命中 cache。

### 7.2 MCP 协议

- **当前正式版 `2026-07-28`**（2026-07-28 发布；`2025-11-25` 为上一版）。但 Codex 0.147.0 宿主实测：默认与启用 `mcp_2026_07_28` 时均实际协商 `2025-06-18`；feature flag 变化不等于 wire 已切换。Phase 0 因而精确覆盖当前宿主 `2025-06-18`、legacy `2025-11-25` 与 SDK v2 直连 `2026-07-28`，Phase 1.5 只负责 Codex 宿主实际切换与旧协议退役。
- `2026-07-28` 的破坏性变更：移除 `initialize` 握手与 `Mcp-Session-Id`（协议层无状态）；新增必须实现的 `server/discover`；Tasks 移出核心成为扩展 `io.modelcontextprotocol/tasks`（轮询式 `tasks/get`）；**Roots / Sampling / Logging 弃用**；服务端发起请求改由 MRTR 模式取代；结果新增必填 `resultType`；`inputSchema` / `outputSchema` 放开为完整 JSON Schema 2020-12。
- 规范明确：需要跨调用状态的服务器应使用**服务端自铸句柄作为普通工具参数** —— 本设计的 `transaction_id` / `job_id` / `instance_id` 与此一致。
- Tools 规范明确要求工具集合不变时 `tools/list` **SHOULD** 返回确定顺序，并说明这有利于客户端 tool-list cache 与 LLM prompt cache；返回 `structuredContent` 时为向后兼容 **SHOULD** 同时返回序列化 JSON TextContent，故两份 result 内容的 transport 字节必须实测而不能假定其中一份“免费”。MCP 不规定 Host 如何把两字段放进模型上下文，真实 model-visible/token 成本仍须目标 Codex Host 实测。
- Resources 在协议层是 application-driven；Host 决定如何列出、读取或纳入上下文。Codex 当前 supported-features 文档未承诺 Resource 必然 lazy 或不进入模型上下文，因此本项目在目标 Host 实测前不能依赖 Resources 节省 Token，且必须保留 projected Tool fallback。
- Python SDK **v2.0.0 已于 2026-07 末发布稳定版**；**v1.x 进入维护期，仅接收安全修复**；`pip install mcp` 现默认安装 2.x。**本项目采用 v2（D-5）**——本仓库实测：v2 `MCPServer` 与 `protocolVersion: 2025-11-25` 客户端握手成功并协商为该版本，`tools/list`、`tools/call`、`structuredContent`、`instructions` 全部正常；`mcp.server.fastmcp` 在 v2 中已移除。
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

### 7.4 第三方生态与并存兼容通道

- Blender Lab 官方 MCP Server：add-on + TCP 9876，当前 commit `4309a39` 注册 26 个工具，覆盖摘要、文件健康、文档检索、截图、UI 导航、渲染及 GUI/CLI 任意 Python 执行。官方警告其**无任何防护**阻止数据被删除或发送至远端，建议在虚拟机或无敏感信息的系统上使用。用户已明确授权以完整 26 工具并存；它仍是 §1.3 边界外的兼容/验证通道，不改变本系统的 13 工具设计或合规结论。
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
| MCP 协议 | **SDK 钉 `mcp>=2.0,<3`（D-5，2026-08-07 改判）**；Phase 0 精确回归 `2025-06-18` / `2025-11-25` / `2026-07-28`，Codex 宿主仍以其实际协商版本为准；只有 protocol probe 返回 `2026-07-28` 才算完成宿主切换——**不迁移 Server SDK** |
| 长任务实现 | 服务端自铸 job 句柄 + 轮询工具，**不依赖 MCP tasks 扩展** |
| 确认交互 | 自定义写工具逐工具 `approval_mode = "prompt"`；官方兼容通道另用 `approve` 免审批；**不使用 elicitation** |
| 日志 | 本地 JSONL + OpenTelemetry，**不使用 MCP logging** |
| `2026-07-28` 迁移 | **已撤销 SDK 升级条目**（D-5：v2 起步即到位）。Phase 1.5 若保留，内容仅为协议一致性回归与旧协议退役评估 |

### ADR-4 回滚语义（D-2）

**决策**：文件级快照是唯一有保证的回滚机制；接受"hard 回滚丢弃事务窗口内手动编辑"这一约束，以 FR-20 的 `pre-rollback` 快照缓解。

**理由**：`bpy.ops.ed.undo_push()` / `undo()` 在后台模式不可用、在非 UI context 下不可靠，不能承担事务回滚职责。

### ADR-5 附录：2026-08-07 触发记录与决策 D-4

**触发**：条件 1 已满足——Blender Lab 官方 MCP v1.0.0（commit `4309a39`，GPL-3.0-or-later）暴露 26 个结构化工具（场景/对象摘要、文件健康、文档检索、截图、UI 导航、渲染、CLI 变体），不再是"只有任意 Python"（本机实测，见 `docs/audits/2026-08-07-plan-adversarial-audit-and-optimization.md` §7）。

**决策 D-4：维持自研（Build）作为唯一受 G1–G3 约束的交付系统；官方 Server 完整 26 工具可作为用户明确授权的并存兼容/验证通道，并继续只作行为参考，不替换本系统。**

理由：① 官方仍默认公开任意 Python 执行；② Bridge 为无鉴权 localhost TCP 9876，无 token、无 deadline、无审计、无事务——G1/G3 与 NFR-S3/S5 全部不满足；③ 实测存在大响应截断（非阻塞 sendall 部分发送后吞错关连接）与 CLI `BLENDER_PATH` 缺失问题；④ GPL-3.0-or-later：**借鉴行为可以，复制源码即触发衍生义务**——本项目不复制；⑤ Lab 官方明示不在 Blender 路线图内。

可借鉴清单（按公开行为独立实现）：渐进式 scene/object summary、missing files / linked libraries 检查、截图大小协商、输出统一写 scratch 目录、GUI/CLI 双模式能力表。并存配置对当前上游目录显式列出完整 26 项 `enabled_tools`（固定快照；上游增删工具时须复核并更新）、`omit_tools_from = []`，并把 `mcp__blender` 设为 code-mode `direct_only`；`default_tools_approval_mode = "approve"`（Codex 语义为不请求工具审批），不设置 `disabled_tools` / 逐工具 override。官方 Server 独立钉 `mcp[cli]>=1.2.0,<2`，该上界不得传播到本系统。

**下一次重评触发点（替换原条件 1）**：官方 MCP 默认禁用任意执行，且其 bridge 同时获得鉴权、deadline、审计与事务语义，达到可进入本系统信任边界的最低条件。

### ADR-5 重新评估触发条件

出现下列**任一**可观测信号时重新评估本架构：

1. Blender Lab MCP 进入 Blender 正式路线图；
2. Codex 官方文档明确承诺支持 MCP tasks 扩展与更强的本地工具权限模型；
3. Codex 官方文档明确承诺消费 MCP **Resources / Prompts**——届时重估「场景快照经 Resources 承载、标准工作流经 Prompts 承载」以降低工具面与上下文占用（当前已核实 Codex 未承诺，故 V1 全部经 Tools）。

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
- MCP `2026-07-28` **wire 协议适配**（Phase 1.5）。注意：**SDK 已是 v2**（决策 D-5），本条指的是客户端协议切换与 `server/discover` 等 wire 层适配，不是 SDK 升级

---

## 10. 验收标准

### 10.1 Phase 0 —— 只读通道

- [ ] **P0-01** 在 5.2 LTS（钉定补丁版本）/ Apple Silicon 上，`get_blender_status` / `get_scene_summary` / `describe_capabilities` 均返回符合 outputSchema 的结果
- [ ] **P0-02** 连接非基线版本 Blender 时，只读工具可用、写工具被拒并返回 `UNSUPPORTED_BLENDER_VERSION`
- [ ] **P0-03** 强制终止 Blender 进程后 MCP Server 不崩溃，返回 exact `{"code":"BRIDGE_UNAVAILABLE","retryable":true}`；同一 MCP Server 会话内 Blender 重启后自动重连。正式 recovery 由 public OS supervisor 包住 hidden worker，且 kill 前/后/重启后的 MCP `(pid, pgid, marker, started_monotonic_ns)` 三次观察完全一致；public cancel/final-KILL、poll deadline 边界、leader 退出但 group child 存活、marker/stale/PID-PGID reuse、record 换入、pre-spawn reservation/stdlib bootstrap/launch-before-publish failure、read-only observer/owner race、unknown-before-valid、第 9 条 overflow/inflight publication 与强杀 worker 后的 group 回收均有直接反例
- [ ] **P0-04** 完整会话循环（enable → 允许连接 → 建连验证 → 断开 → disable）20 次，无线程泄漏、无残留 socket 文件——P0-D1 下裸 enable/disable 不建 socket，必须含会话启停才测到实体
- [ ] **P0-05** 传输 ≥5 MiB 的 framed scene-summary / wire payload，分帧正确、无截断（Phase 0 不交付 IR）
- [ ] **P0-06** socket inode 自创建起位于 `0700` 私有目录；`bind` 后、`listen` / I/O 线程启动 / `session.json` 发布前立即 `chmod 0600`；无 token 的连接被立即断开并记日志
- [ ] **P0-07** 全程 stdout 仅含 JSON-RPC
- [ ] **P0-08** MCP Server 冷启动 < 5 s

Phase 0 的性能与生命周期反例门禁还必须逐项通过：

- [ ] **P0-09** 大场景 `scene_summary` 使用 cooperative continuation；一次 GUI timer tick 不得因整体遍历/编码同步物化而超出测量上限，并记录总耗时与最大 tick
- [ ] **P0-10** continuation yield 间无 `bpy` wrapper；已注册的 `load_pre` handler 递增 generation 后，旧 continuation 以 `SCENE_QUERY_FAILED` 结构化终止
- [ ] **P0-11** 2.2M collections 场景传 `include_collections=false` 时 reader 源端不枚举 collections，响应保持在 16 MiB 限制内
- [ ] **P0-12** 队列容量同时计 queued + active continuation；满载返回 `BRIDGE_BUSY`，不出现 64 → 65 的超额提交
- [ ] **P0-13** 唤醒 socket 非阻塞且 wake storm 被合并；停止时生命周期回调与活跃连接按 §3.7 的 1–10 顺序完成
- [ ] **P0-14** 文件/父目录/清理目标在读取或探活期间被换入时，dir-fd 与 dev/inode 绑定阻止越界读取和误删；socket/session 路径被替换时 stop 保留替换物
- [ ] **P0-15** `v=true`、非布尔 `ok`、畸形 `error` 与会被 SDK 强制转换的参数类型均被拒；错误保持结构化且进入审计
- [ ] **P0-16** 线程并发与多个 MCP Host 进程并发写审计日志时，每行仍是完整、可解析的单条 JSON
- [ ] **P0-17** 应用自有 runtime/run/logs 若既存且非当前 uid、非目录/regular file、为 symlink 或权限不是 `0700/0600`，必须 fail-closed；`BLENDERCODEX_ROOT` 上方既存祖先权限保持不变
- [ ] **P0-18** `sun_path` 回退在 session 发布前或发布后崩溃均能回收外置 socket/空目录；回退或 session 目录 identity 被换入时保留替换物与诊断元数据
- [ ] **P0-19** stale cleanup 每次 I/O 前检查共享 deadline，预算耗尽保留证据并在后续扫描重试；目录名与 `session.json.instance_id` 不一致时隔离
- [ ] **P0-20** 日志目录/当天文件由多线程、多进程首次并发创建时无 `FileExistsError`；FIFO 目标须在 `<0.5 s` 内 fail-closed，device/symlink 目标不得被写入

除上述 20 项外，Phase 0 关闭还必须通过 NFR-P1 正式门；其精确计时、样本与 artifact 合同见 §6.3，不得以历史 100k Bridge-RPC 候选数据代替。

### 10.2 Phase 1 —— 事务化最小写入

四个 fixture 可重复通过：**平板桌 / 圆角盒 / 带孔支架 / STL 导出**。每个 fixture 须验证：

- [ ] 原 `.blend` 的 mtime 与内容 hash 未改变
- [ ] 同一 IR 提交两次，对象数不变
- [ ] 计划生成后手动移动一个对象再提交 → 返回 `SCENE_REVISION_CONFLICT`，场景未被改动
- [ ] **计划生成后进入编辑模式移动目标对象的顶点**（计数不变）再提交 → 同样返回 `SCENE_REVISION_CONFLICT`（v1.2：plan_scope_hash 的几何摘要覆盖）
- [ ] hard 回滚后场景与回滚快照一致——**判据为 `.blend` 文件内容 hash**，不得用 `scene_hash`（结构摘要 v1 看不到顶点/材质/modifier，无法证明完整恢复；复审 F-10）
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
| **Phase 1.5** | 协议一致性回归与旧协议退役评估（**SDK 升级条目已撤销**——D-5 起步即 v2）。触发条件：Codex 宿主 protocol probe 实际协商 `2026-07-28`；仅打开同名 feature flag 不满足条件 |
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
| **R-04** | `open_mainfile`（hard 回滚）会释放全部 bpy 数据；文件加载期间若 continuation 持有旧 wrapper，会在回调恢复后触发失效访问 | 回滚后 Bridge 失联或读到错误场景 | NFR-R5/R6：continuation 只保存纯 Python cursor/scene identity；persistent `load_pre` 先递增 generation 使旧 continuation 结构化失效；Phase 1 验收含回滚后可用性用例 |
| **R-05** | **SDK 选择已解决、宿主 rollout 未完成（2026-08-07，决策 D-5）**：`2026-07-28` 与 SDK v2.0.0 均已发布，v1 进入维护期；Codex 0.147.0 即使打开同名 flag 仍协商 `2025-06-18` | 停在 SDK v1 会制造迁移债务；把 feature flag 当 wire 证据会形成假阳性 | 依赖钉 `mcp>=2.0,<3`；精确回归 `2025-06-18`、`2025-11-25`、SDK 直连 `2026-07-28`，Codex 宿主另以 protocol probe 判定，不接受 flag 代替协议证据 |
| **R-06** | 受管对象被复制（Duplicate / Alt+D / Make Real / Append）会连同 `bcx.v1.id` 一起复制 | stable_id 唯一性被破坏，写操作可能作用于错误对象 | FR-10 三处检测 + 人工消歧，不自动猜测 |
| **R-07** | `bcx.v1.id` 作为用户自定义属性在 UI 中可见可编辑，可能被用户改动或与自有属性冲突 | 受管对象失联 | 命名空间前缀降低冲突概率；FR-10 检测缺失与重复 |
| **R-08** | 用户同机启用官方 Blender Lab MCP 完整 26 工具时，无鉴权 TCP 9876 bridge 与任意 Python 工具可直接作用于共享 Blender；且官方依赖声明无 `<2` 上界，默认解析到 SDK 2.0.0 会启动失败 | 官方通道不满足 G3，且错误依赖解析会导致冷启动失败 | 将其明确置于 §1.3 边界外并分开报告；用户已接受完整工具面的风险。并存配置显式列出当前完整 26 项 `enabled_tools`、`omit_tools_from = []`，不设 `disabled_tools` / 逐工具 override；使用 `default_tools_approval_mode = "approve"` 免工具审批、不开 HTTP，并以 `mcp[cli]>=1.2.0,<2` 隔离官方 Server。上游增删工具时须重新同步快照。**该上界不得传播到本系统** |
| **R-09** | cooperative 预算无法抢占单个 Python/bpy/native/bytes 原子 step；某一步本身若无界，单 tick 仍可能超出 50 ms | GUI 短暂卡顿，不能兑现绝对 `≤50 ms` 声明 | 对象、hash、collection、JSON encoder piece 分片并在 step 前后检查 deadline；合同明确为 `50 ms + 有界原子 step 成本 + 调度抖动`；无界工作转 Headless Worker，并用大场景 wall-clock 回归守住测量上限 |
| **R-10** | 用户主动放宽 `BLENDERCODEX_ROOT` **上方祖先目录**权限 | 应用根目录名可能可见；强制 chmod 范围外祖先会越权改变用户设置 | 不主动重写边界外祖先；但 `BLENDERCODEX_ROOT` 自身及 `run/logs` 必须精确 0700，否则 fail-closed。会话叶目录独占创建为 0700，session/socket/日志文件为 0600 |

### 12.2 待验证（不阻塞启动）

| ID | 事项 | 处理方式 |
|---|---|---|
| **V-01** | `agents/openai.yaml` 中 **stdio 型** MCP 依赖的声明字段（官方示例仅给出 `streamable_http`） | Phase 0 实测。在此之前 Skill 不依赖自动接线，安装文档直接提供 `codex mcp add` 命令 |
| **V-02** | Codex 启动的第三方 MCP Server 子进程是否继承 Codex sandbox | 不影响实现——NFR-S2 要求路径策略独立成立。仅影响安全文档措辞 |
| **V-03** | Cycles Metal 在 `blender --background` 下的 GPU 设备枚举与选择行为（基线 Apple M4 / Blender 5.2.0 已复现；真实渲染成功性与跨硬件 fallback 不在本次枚举证据内） | Phase 0 固定枚举/选择证据；Phase 2 仍须真实 render 与 CPU fallback 验收，不能因一次枚举关闭降级路径 |
| **V-04** | `bpy.app.timers` 与 persistent handlers 在 `open_mainfile` 路径上的最终验收（`read_homefile` 机制 spike 已完成） | 机制已由 GUI spike 验证：persistent timer 与 handlers 存活；Phase 1 仅补直接 `open_mainfile` hard-rollback 验收与重载后可用性，不再把 timer 持久性列为未决 |
| **V-05** | 默认 `get_scene_summary` 仍令两个 include flag=true，而 NFR-P1 100k 基线固定 false，未覆盖“默认结果可能返回大 collections/managed arrays”的模型上下文成本 | Phase 1 开始前裁决 observation contract；不得只把默认改 false 并用空数组制造“真实为空/未取回”歧义。若采用 compact default，必须同步设计 `included/omitted/complete/truncated` 元数据与 selector/fields/limit/cursor，并保留原完整查询的显式路径；raw mesh/完整 node graph 不得成为默认结果 |

---

## 13. 变更记录

### v1.1（2026-08-06）

触发：对外部研究报告《构建生产级 Blender AI Skill》（2026-08-06）的核查采纳 + Phase 0 spec §10 挂账修订的正式落账 + 外部约束时效复核。

**采纳自外部报告（经核实或属通用工程实践）**：FR-34（server instructions，Codex 消费该字段已在 2026-07-23 核实）、FR-35（job 状态机与心跳）、FR-33 增强（改前改后 revision、result_digest、审批记录）、NFR-R7（OperatorAdapter 模式）、NFR-C5（AGENTS.md 模板交付）、§10.3（重复顶点、法线一致性）、§11 Phase 3（release manifest、资产策略、BVH 检查）、§7.4 生态补充与供应链反例、ADR-5 触发条件 4。

**拒绝采纳（记录原因）**：① 场景快照经 MCP Resources / SOP 经 Prompts 承载——MCP 语义正确，但已核实 Codex 未承诺消费，列入 ADR-5 的 Resources / Prompts 重评触发项（v1.4 后编号 3）；② 每个写工具携带 `dry_run`——与 FR-06「唯一 dry-run 入口」的既有决策冲突，维持原决策；③ Streamable HTTP 远程部署——超出本版「本机单用户」范围（NFR-S3）；④ 报告对 MCP 传输的描述（会话 ID、SSE 断线恢复）沿用 `2025-11-25` 语义，已被 `2026-07-28` 移除，属报告时效缺陷，不采纳。

**落账 Phase 0 spec 的挂账修订**（spec §10 表 6 项 + spec §2.2 的 NFR-S4 机制表化；spec §10 中 get_scene_summary schema 一行不涉及 URS 文本，未列入）：术语表 `scene_revision`（整数、会话内）与 `scene_hash`（全场景）重定义、新增 `plan_scope_hash` 词条、FR-11 权威依据改为 `plan_scope_hash`、NFR-S4 权限机制表化、NFR-S5 token 保证下调、NFR-O2 OTel 推迟声明、FR-32 取消中心注册表。

**外部约束复核（§7.2）**：MCP `2026-07-28` 已发布；Python SDK v2.0.0 稳定、v1.x 维护期、`pip install mcp` 默认 2.x；R-05 相应更新，Phase 1.5 优先级上调。

### v1.2（2026-08-07）

触发：外部对抗审计（`docs/audits/2026-08-07-plan-adversarial-audit-and-optimization.md`）+ 外部研究报告二（`docs/research/deep-research-report-2.md`）。审计三条阻断发现全部经本仓库独立复现确认（F-02 慢滴流 1.38s 击穿 0.3s 超时；F-03 16 候选 4.0s 突破 3s 预算；F-01 由构造即真）。

**采纳**：scene_hash 术语改「结构摘要 v1」+ 盲区清单；plan_scope_hash 增加几何摘要硬性要求 + §10.2 顶点编辑冲突 fixture；FR-30 增 TOCTOU 附注（Phase 1 fd-based 写入）；ADR-5 附录 D-4（官方 MCP 重评：维持自研 + 行为参考 + GPL 不复制）；新增 R-08；plan 侧同步修复 F-02/F-03/F-04/F-07/F-08 并新增执行前决策门 G0–G5。

**范围裁定**：研究报告二的企业拓扑（Gateway/Planner/PostgreSQL/K8s/多租户）与本 URS「macOS 桌面端本地部署」范围不符，**不采纳**为本版需求；其中与本设计同向的要素（总 deadline、结构化结果、能力分层、供应链禁自动更新）已在本版或既有条款覆盖。

### v1.3a（2026-08-07，SDK 决策复审）

触发：第三方对抗复审（`docs/audits/2026-08-07-claude-plan-changes-adversarial-reaudit.md`）。其两条 P0 代码发现与一条 P0 决策发现均经本仓库独立复现/复核。

**采纳**：D-5 MCP SDK 改判 v2（NFR-C3、ADR-3、R-05、§7.2、Phase 1.5 同步修订，ADR 见 `docs/decisions/2026-08-07-mcp-sdk-v2-selection.md`）；补齐 v1.2 遗漏的 **R-08**（含官方 Server `<2` 上界不得传播的约束）；头部状态同步至 D-4/D-5；plan 侧修复 R-02（socket ownership，防误删外部 socket 造成 DoS）、R-03（deadline 覆盖扫描阶段 + partial 标记）、R-04（scene_hash 恒真式测试改为字段结构断言 + L3 真机盲区证明）、R-05（官方 Server 隔离环境上界）并关闭当轮 G0/宿主配置 G5（历史状态；不等同于当前模型工具面验收）。

**本仓库独立复核记录**：R-02 外部 socket 被删（DoS 成立）；R-03 400 候选 × 10 ms I/O 实测 5.007 s vs 声称 2.5 s；SDK v2 服务 2025-11-25 客户端全通。**未能在本会话复核**：两条 Codex app-server 路径——`codex` 不在本会话 shell 的 PATH 中（该机器确有 Codex 0.147.0-alpha.6.5，见 2026-08-07 全量复审 §3.2）。其承重前提「v2 服务 2025-era 客户端」已由本仓库直接验证，结论不依赖该两条。

### v1.3b（2026-08-07，全量复审）

触发：全量对抗复审（`docs/audits/2026-08-07-full-repository-adversarial-reaudit.md`）。六条 P0 与主要 P1 均经本仓库独立复现。

**复现记录**：F-01a 慢 `iterdir` 实测 4.773 s vs 预算 2.5 s（`sorted()` 在 deadline 检查前物化整个目录）；F-01b FIFO `session.json` 使扫描**永久阻塞**；F-03 三工具 `output_schema=None`、`additionalProperties=None`、未知参数被吞、`structured_content` 亦为 None；F-04 请求 `2026-07-28` 实测协商为 `2025-11-25` 而测试仍通过；F-06 `mcp.__version__` 在 SDK v2 下 `AttributeError`；F-07 `describe_capabilities` 实测 2.002 s（触碰 Bridge）；F-08 字典序取前 16 使最新活实例不可发现。F-02 结构缺陷成立（发现与聚合各自计时），但本会话 fixture 未触发。

**修复后复测**：F-01a 0.016 s；F-01b 3 s 内返回；F-07 0.0 s；F-08 活实例可发现；L1 78 passed、L2 22 passed、ruff/mypy 全绿。

**文档修订**：FR-11 措辞（不再称 scene_hash 全场景敏感）、FR-12 幂等键改绑 `plan_scope_hash` 并固定「先校验后幂等」顺序、§10.2 回滚判据改用 `.blend` 内容 hash、§9 澄清 Phase 1.5 指 wire 协议而非 SDK、v1.3 复核记录措辞更正（本会话 PATH 无 codex ≠ 该机器无 Codex）。

### v1.4（2026-08-07）

触发：对全量复审发现的再次对抗性修复与官方 MCP 26 工具宿主实测。最终审计见 `docs/audits/2026-08-07-final-adversarial-audit-after-remediation.md`。

**实施修复**：Discovery 改为公平游标扫描、同 fd 非阻塞有界读取和单一绝对 deadline；MCP 输入/输出改为封闭 Pydantic 模型并在参数绑定前拒绝未知参数；旧/新协议改走独立真实 stdio 路径；stdout 半行读取受 deadline 约束；补齐 MCP → adapter → UDS → Bridge 全链路与真 Blender hash scope 回归。隔离验证初始为 108 passed、ruff clean、mypy strict 19 个源文件零错误；真 Blender GUI 五项判据全 true。随后 protocol probe 发现 Codex 0.147.0 即使打开 `mcp_2026_07_28` 仍协商 `2025-06-18`，故把当前宿主版本加入精确合同覆盖，并撤回“flag 已证明 2026 wire”的旧声明。

**边界与并存配置（历史当轮；现行过滤合同见 v1.7）**：G1–G3 明确只约束自定义安全系统。Blender Lab 官方 MCP 作为用户明确授权的独立兼容通道，完整暴露 26 个工具、`approve` 免工具审批；v1.7 起以显式 26 项 allowlist + 空 omit 固定当前完整目录。自定义写工具修正为 `prompt`。官方 Server 继续以 SDK `<2` 隔离，自定义 Server 继续采用 `mcp>=2,<3`。两条通道的能力和合规结论不得混写。

### v1.5（2026-08-07）

触发：对 Phase 0 主线程大响应路径、文件重载与生命周期进行 continuation 级对抗复审。旧同步实现可在单 tick 占用约 619 ms；仅在任务之间检查 50 ms 预算无法约束单个大任务。

**契约修订**：FR-01 固定两个 summary 开关的端到端传播与源端裁剪；NFR-R2 固定非阻塞合并唤醒、loop-boundary stop recheck、发布物 identity 与真实 1–10 停止钩子；NFR-R3 固定信封 exact-type 校验；FR-32 固定 dir-fd/dev-inode 绑定与非递归清理；FR-33 固定线程/跨进程 JSONL 序列化；NFR-R4 将 50 ms 明确为 cooperative checking budget；NFR-R5/R6 增加纯 Python continuation 状态、persistent `load_pre` generation 失效语义；Phase 0 验收新增大场景 wall-clock、active-capacity、wake storm、源端裁剪、reload invalidation、换入竞态和并发审计反例；生命周期注册失败必须逆序回滚本次新增 timer/handler。

**隔离验证证据（当轮）**：12.59 MiB scene response 分 36 ticks，最大 tick 53.76 ms、总耗时 1.8 s；`include_collections=false` 面对 2.2M collections 时总耗时 108.3 ms 且返回 0 项；旧 continuation 在 generation 变化后结构化失败；队列不再出现 64 → 65 容量竞态；driver 注册失败的本次新增回调均按逆序清理；父目录/清理目标/socket 换入、bool-as-int、SDK 类型强制、线程与 fork/spawn 多进程日志交错均有反例。该轮隔离套件为 149 passed；后续最终证据见 v1.6。

### v1.6（2026-08-07）

触发：最终收尾对抗复核以长路径 fallback、既存权限和首次并发初始化为攻击面，再发现并复现 6 组残余：发布前/后崩溃遗留外置 socket、session/fallback 目录换入误删、cleanup 越过 deadline、应用自有目录/审计文件权限未 fail-closed、AuditLog 首次创建竞态、目录名/实例 ID 歧义及 malformed success retryable 不一致。

**契约与实现修订**：应用自有目录改为 race-safe create-or-validate，会话叶目录 exclusive 创建；审计目标经 no-follow/nonblocking + 同 fd identity/类型/uid/mode 校验；fallback 路径由实例 ID 确定性推导并发布 identity，故 session 发布前后崩溃均可恢复；stop 与 Discovery cleanup 对目录/文件 identity 和同一 deadline fail-closed；`instance_id` 必须匹配目录名；所有 malformed response shape 统一 retryable `BRIDGE_UNAVAILABLE`。

**最终隔离验证证据**：完整套件 **166 passed（L1 140 + L2 26，无 warnings）**，ruff clean，mypy strict 19 个配置内源文件零错误，vendor 与 nested import 门禁通过；Blender 5.2.0 background 为 `BG_CHECK_OK`。最新真 Blender GUI smoke `/tmp/bcx-final-smoke-20260807-04.json` 的 timer/revision/fields/hash_scope/cycles 五项全 true、`errors=[]`，且 artifact 晚于全部最终 Python 源码。50 ms 仍仅是 cooperative checking budget，不外推为硬墙钟保证。

### v1.7（2026-08-07）

触发：对最终隔离实现与 URS / spec / Plan 做合同逐项对齐，重点复核 cleanup 部分完成语义、审计失败闭合、并发 status 聚合、发现快照配对、深层 wire 边界以及官方 MCP 的宿主配置与当前回合工具面差异。

**合同修订**：FR-32 明确已完成 unlink 不回滚、未知 child 只阻止最终 `rmdir`，并收窄合法 `socket_path`；FR-33 将 `request_id` 绑定入站 JSON-RPC id，业务预算与独立 ≤1 s audit postlude 分离且审计失败返回 `AUDIT_UNAVAILABLE`；NFR-R2 加入 transport close 后第二次 1 s join；NFR-R3 固定 UTF-8、深层 JSON、exact wire type、有限 number 与同批拒绝边界；adapter 上限按已验证实现统一为 ≤375 行。官方兼容通道改用显式 26 项 allowlist、空 omit 与 code-mode direct-only；宿主 effective 配置和目录已验证 26/26，当前回合模型工具面仍须在 Codex 重启或新回合后另行确认。

**标准 JSON 数值边界补充**：最终红队复核发现 Python 标准库默认接受并可能发出 JSON 规范外的 `NaN` / `Infinity` / `-Infinity`，且 `1e999` 可解析为无穷，原“按 JSON wire 类型处理”不足以形成可执行门禁。Plan 的共享 envelope parser 现使用 `parse_constant` 拒绝命名常量、有限 `parse_float` 拒绝指数溢出，request / error / success 三类编码路径均固定 `allow_nan=False`；request/response 解码与 request/success 编码均有回归。

**当轮隔离预检证据（历史，已由 v1.8 取代；不是 Phase 0 执行）**：完整套件 **235 passed（L1/unit 208 + L2/contract 27）**，ruff clean，mypy strict 覆盖 22 个配置内源文件且零错误；adapter 实质代码 374 行。收发双向非有限 JSON number 与指数溢出反例均已进入回归。Blender 5.2.0 background 为 `BG_CHECK_OK`，GUI v4 五项全 true、`errors=[]`；其命令、build、Plan SHA 与 46 文件 manifest SHA 已落在 `docs/audits/evidence/2026-08-07-phase0-closeout-v4-provenance.json`，不再以 mtime 单独证明归因。该证据仅证明当时 Plan 代码块的组合性与已知反例关闭，Phase 0 任务、验收和复选框仍全部未执行。

### v1.8（2026-08-07）

触发：在 v1.7 后继续按 availability、fd/socket ownership 和失败重试做对抗性冻结，复现单连接上限无法约束 64 连接合计内存、fd 数字复用误判连接、transport close 失败后过早删除会话路径，以及 accept/close 失败丢失 ownership 等残余。

**合同修订**：NFR-R2 增加 64 连接、32 MiB 全局未成帧入站、64 KiB 单请求、32 MiB 单连接 outbox 与 64 MiB 全局 outbox 上限；部分 send 仍按完整驻留 frame 计数。`stop() -> bool` 仅在 transport/线程/路径清理完成时成功，失败由 driver/UI 保留 session 并重试。FR-33 保留 numeric/string JSON-RPC id 的原始类型，并把 post-write/flush/close deadline 检查纳入 fail-closed。NFR-R3 区分合法版本不匹配与缺失/bool/string 等畸形 `v`。同时固定 status 响应实例身份绑定、scene summary 真 object、cleanup failure→partial、reply 普通异常隔离与 NUL 路径拒绝。

**最终隔离预检证据（不是 Phase 0 执行）**：冻结树 **260 passed（L1/unit 233 + L2/contract 27）**，adapter 专项 33 passed、实质代码 375 行；ruff clean，mypy strict 22 个配置内源文件零错误，vendor、nested import 与 `uv lock --check` 全绿；另有 20 轮并发 RPC/stop 压测通过。Plan 46 个 Python 文件块与冻结树逐字节一致。Blender 5.2.0 background 与 GUI v5 再验证通过；可复算 Python manifest、非 Python 产物 SHA、命令与 build 信息见 `docs/audits/evidence/2026-08-07-phase0-closeout-v5-provenance.json`。这些仍是隔离预检，93 个 Plan Step 保持全部未执行。

### v1.9（2026-08-07）

触发：对平台优化 handoff 做对抗性融合时，真 Blender 复现旧 SceneReader 数值索引在 10k/20k 对象下近 O(N²)，并发现平台报告、Plan、spec 与 v5 provenance 已分叉。

**合同修订**：FR-21 明确文件同一性必须在 fd-bound / `O_NOFOLLOW` 边界 fail-closed 地校验，`same_file()` 只作查询辅助；V-03 拆分为「基线 Metal 设备枚举/选择已复现」与「真实 GPU render / CPU fallback 仍由 Phase 2 验收」。Phase 0 SceneReader 采用有界 collection slice，在单步内转为纯 Python 并释放 wrapper 后再 yield；禁止用逐对象数值索引或跨 yield 保留 bpy wrapper/collection iterator。`quantize` 的直接定长格式化与 0.02 s idle 只按本机候选实现记录，不产生跨硬件吞吐或电量承诺。

**候选隔离预检（不是 Phase 0 执行）**：Plan r12 当前为 **262 passed（L1/unit 235 + L2/contract 27）**、adapter 33、ruff/mypy/vendor/nested/lock 全绿；真 Blender 100k 共享网格候选约 1.2 s、最大 source step 约 22 ms、yield 后无 bpy wrapper。最终 Plan SHA、46 文件 manifest、BG/GUI artifact 与 v6 provenance 必须在本轮文档全部冻结后重新生成；旧 v5 继续只证明 v1.8/a05 基线，不能改写归因。93 个 Plan Step 仍未执行。

### v1.10（2026-08-07，handoff 融合复审）

触发：平台优化 handoff 与 r12 候选的对抗性融合复审；补充发现发现游标在目录换入窗口缺少 fd identity 复核、部分 socket identity 字段可走 legacy fail-open 分支，以及验证器自身存在 selector 后阻塞 `readline()` 的证据鲁棒性缺口。

**合同与证据修订**：Discovery 复用跨调用 cursor 前必须以 `fstat` 重新确认其 fd 仍绑定当前 run identity；不匹配时关闭 cursor、清空其 backlog 并标记 `partial`，不得继续消费旧目录。有限次 identity 重检不能消灭最后一次检查后的 TOCTOU；同进程外部代码主动关闭私有 cursor fd 并把同 identity fd 换回同一数字不在保证范围，different-identity 复用必须不被误关。`session.json` 的四个 socket identity 字段全部必填；部分或全部缺失均隔离并保留证据，不得按“legacy”直接 probe。失效通知不得等待 discovery 扫描锁，重复通知须有界合并且扫描中通知不得发布旧缓存。Server Python 固定 `>=3.13,<3.14`；验证脚本的子进程读取改为 selector + 有界 `os.read`，并对单行、累计缓冲/事件/消息及每次请求设置独立上限。v6 manifest/provenance 只在最终文档与 Plan SHA 冻结后生成；旧 v5 与 closeout-v2 继续作为历史证据，不得作为当前审批依据。

**r13/v6 最终隔离预检（不是 Phase 0 执行）**：最终 Plan 46 个 path-bound Python 文件块物化后为 **280 passed（unit 249 + contract 31）**、ruff clean、mypy strict 22 文件零错误，vendor/nested/`uv lock --check`、Blender background 与基础 GUI 五项全绿。100k shared-mesh GUI 连续 20 次 worker-side query 的 nearest-rank P95 约 **1439.21 ms**（max 约 2071.10 ms），`max_tick≈62.12 ms`，固定基线 NFR-P1/P0 cooperative 候选门通过；wrapper-free 由独立 L1/background fixture 证明。Plan 实际有 92 个可执行 checkbox + 1 个无 checkbox 的 G0 preflight，全部未执行/未勾选；旧 raw=93 计数包含文首语法示例。证据见 `docs/audits/evidence/*-v6.*` 与 closeout-v3。官方独立 app-server 仍为 26/26 且代表调用无审批事件，当前任务模型面实测 10/26，因此 G5 只关闭宿主侧。

### v1.11（2026-08-08，r15/v8 全量对抗复审）

触发：对 v1.10/r13 Plan 做 fresh-tree 全量复验时，红队先阻塞 SDK v2 `Tool.run` 的 `convert_result`，随后构造 Blender addon 第二个 `register_class` 失败反例，证明旧 `register()` 会泄漏此前已注册 class；同时复核 reader 资源上限、stdout 目标响应后延迟污染、cleanup 最后一次检查后的 POSIX 边界，并对官方 MCP deferred render 做故障注入/上游交叉核对。

**合同与实现修订**：NFR-R9 固定 Bridge 每实例与 Server middleware 各自容量 2；Server 准入移到 raw-argument middleware，覆盖完整 `call_next`、SDK 结果/structuredContent 转换与 audit postlude，第三个 wire 请求 fail-fast `BRIDGE_BUSY` 且不阻塞 async 事件循环；reader object/collection 各自 1,000,000 项/64 MiB 文本上限，超限映射 `INTERNAL_LIMIT_EXCEEDED`；NFR-O1 明确目标响应后的 bounded tail-drain/quiet timeout/EOF settle；FR-32/NFR-R2 诚实记录 POSIX 无 compare-and-unlink/rmdir 及同 UID 最后窗口边界；addon `register()` 对本次新增 class 做逆序回滚，回滚自身失败时保留栈并报告。adapter 现为 ≤375 行，v8 隔离实测 373 行。

**v8 隔离预检（不是 Phase 0 执行）**：最终 Plan fresh-tree **307 passed（unit 275 + contract 32）**、adapter 专项 35、ruff/mypy/vendor/nested/lock 全绿；fresh Blender background/GUI smoke 通过。100k shared-mesh Bridge-RPC 20-query worker P95 1605.18 ms、max 2560.86 ms、observer P95 1655.44 ms、max tick 62.50 ms，只证明 Bridge/continuation 子门，不能关闭端到端 NFR-P1。v8 manifests/provenance/raw artifacts 见 `docs/audits/evidence/`；92 个 checkbox + 1 个 G0 preflight 全未执行/未勾选。

**官方 MCP 限定（v1.11 当时状态）**：上游 checkout 注册目录与独立 app-server 目录为 26/26；历史单轮直调曾报告 26 项，但最新安全 host 24 项长序列在第 15 项 `get_screenshot_of_area_as_image` 出现截断 JSON（单独重试成功），因此不能把 24/24 写成当前稳定性证明。连续 deferred render 序列在 Blender 5.2 复现 `SIGABRT`，与 [Blender issue #157084](https://projects.blender.org/blender/blender/issues/157084)、[PR #156953](https://projects.blender.org/blender/blender/pulls/156953) 及 [blender_mcp issue #12](https://projects.blender.org/lab/blender_mcp/issues/12) 的异步 RenderData/depsgraph race 方向一致。官方通道不能写成“26 项稳定无问题”，也不计入本系统 G1–G3；当时 Codex 模型面为 10/26，后续刷新与风险裁决见 v1.12。

### v1.12（2026-08-08，r16 proposed 与所有者裁决）

触发：ROADMAP B-5 对抗复核发现 URS §10.1 的 20 项验收与 Plan/Spec 映射不完整、NFR-P1 只有一句目标而没有正式测量合同、socket 出生权限措辞不可实现；Codex 完全重启后模型面已刷新为 26/26，项目所有者随后裁决 A-1 三项平台候选全部接受，并为 A-3 选择“当前用户接受风险”。

**合同修订**：§10.1 为 20 项验收增加稳定 ID `P0-01`～`P0-20`；P0-06 固定 `bind → chmod 0600 → listen → I/O thread → session publish`；P0-03 固定同一 MCP Server 会话内真 Blender SIGKILL/restart；NFR-P1 固定三工具各 20 次完整 MCP 调用、nearest-rank P95、100k/在线/离线三种 fixture、不可删样本及可复算 artifact。新增 foreign uid/device、边界上方祖先权限不变、FIFO `<0.5 s`、stale 后续重试和已注册 `load_pre` handler 的直接反例要求。

**裁决边界**：三项平台候选正式接受，不再保留代码回退动作；`IDLE_INTERVAL=0.02` 的电量影响仍是非阻断测量。官方 MCP 当前模型面与宿主目录均为 26/26，A-4 有界摘要 transcript 记录 24 个非-render `ok`、2 个 render `not_called`、审批事件 0；G5 由项目所有者知情接受 screenshot 顺序敏感性与 deferred render `SIGABRT` 风险而关闭。该关闭不改变已知缺陷事实，也不构成 raw payload 可重放性或 26 工具稳定性证明。r16 在本次隔离复核与 proposed SHA 获批前仍不得提交或执行，Phase 0 保持未执行。

### v1.13（2026-08-08，r16 E2E 证据链对抗加固）

触发：r16 二轮红队实际复现 SDK process-group leader 退出后仍有同 PGID child、recovery worker 缺外层监督、provenance 在 shared deadline 外递归读取 ignored/symlink，以及 approved tuple/result digest/same-session 的假阳性。

**合同修订**：NFR-P1 拆出正式证据合同，固定 NFR 165/180 s 与 recovery 120/135 s 两层 deadline、poll 前后边界判定、non-raising public cancel、fresh marker-bound exact-type process registry、PID/PGID/inode/inflight-publication fail-closed、bounded Git/vendor/audit provenance、四文档 exact-type approved tuple/source blob、60 个 bounded result preimage 跨工具总量外部复算、exact retryable `BRIDGE_UNAVAILABLE` 及三次 MCP identity 全等。100k fixture 与 Bridge-only 预查询明确发生在 helper spawn 前，不再声称服从 helper deadline。Phase 0 仍未执行，所有数字须以最终 r16 机械物化和 B-5 审计为准。

### v1.14（2026-08-08，r16 process-registry 生命周期闭合）

触发：第三轮红队连续复现 cached group 在 pending/deadline 时被清空、partial scan 丢失、unknown first publisher、observer 抢 owner unlink、PID reuse 截断后续 valid group、cache 跨 pending scan 无界增长，以及 public worker cleanup 耗尽 registry deadline。

**合同修订**：所有独立 group 改为 parent pre-spawn reservation + `process_registry.py` 最小 stdlib bootstrap；observer 与 cleanup 明确分权，枚举后的 owner retire/publication rename 作为 pending 重扫；cache 固定上限 8，逐 entry 错误聚合后报告，overflow 经 identity 复核立即 KILL；public recovery work 期持续预观察并保留 5 s registry cleanup。r16 隔离门禁、manifest 与 proposed tuple 由最终机械复核固化；正式 GUI/NFR/recovery 与 Plan 仍未执行。

### v1.15（2026-08-08，r16 最终门禁反例闭合）

触发：独立机械复核在未设置 `PYTHONDONTWRITEBYTECODE` 的标准 unit 命令中复现 vendor `__pycache__` 令 provenance exact-set 失败；第四轮红队又复现目录第 9 条有效 record 在 identity 读取前被 entry cap 截断、unknown entry 直接抛错遮蔽后续可信组，以及 launch-before-publish 失败遗留 reservation。

**合同修订**：保持 vendor exact-set 严格，不把 pyc 加入白名单；标准检查显式禁写并预清 bytecode，provenance 直接夹具清理由测试 imports 产生的 vendor cache。`MAX_RECORDS=8` 仅作为可信 cache 上限，formal 枚举由 shared deadline 限界；unknown/坏 entry 聚合后报告，第 9 条及后续 overflow 均须 identity-rechecked KILL。parent 对尚未完成的 reservation 负责，在参数构造、SDK enter 或 `Popen` 失败路径按 dev/inode 清理。正式 GUI/NFR/recovery 与 Plan 仍未执行。

### v1.16（2026-08-08，r17 研究报告三融合）

触发：对外部研究输入《面向 Codex / AI Agent 的 Token-Efficient Blender Skill、MCP 与 Addon 闭环架构研究》逐行核查，并以 OpenAI、MCP、Blender 官方资料和五个代表性 GitHub 仓库重新取证。原报告的 `turn…/filecite…` 标记不可移植，且自述未收到本仓库源码，故只作为非规范输入，不作为当前实现审计证据。

**采纳**：NFR-P5 固定三工具的完整 catalog 与确定顺序；Task 17/18 保存并外部复算 catalog/schema/instructions bytes+SHA，以及 60 次 `structuredContent`/TextContent 原文、JSON 等价性、bytes/SHA、双内容 result payload 与 duplication ratio。NFR-C6 固定 AGENTS/Skill/instructions/schema/Addon 单一职责。所有 byte 只作 transport/result 基线，不冒充 model-visible 或 token，不采用固定“8–15 tools / 5–30 operations”等经验数字。

**延期或拒绝**：Resources/Tasks 只在目标 Codex Host 实测后重评且始终保留 Tool fallback；scene projection/diff、progressive error detail、Recipe、visual budget 进入 ROADMAP 的证据触发型后续项，不扩张 Phase 0 产品面；不引入 SQLite 或巨型 Batch schema，不重写已验证 UDS；报告中的客户端 `idempotency_key`、自动 mint 重复 stable ID 与 arbitrary Python 分别违反 FR-12、FR-10 与 G3/FR-04，明确拒绝。默认 summary 两个 include flag=true 而 NFR-P1=false 的 observation 成本盲点列入 V-05，不能以静默改默认制造语义歧义。

**审批时态**：r16 完整 tuple 曾获所有者批准，但尚未形成 source commit/attestation 即被本次规范与 Plan 变更取代；批准不能跨未知哈希继承。当前只能以 r17 最终审计产生的新 tuple 重新审批，Phase 0 仍未执行。

### v1.17（2026-08-08，r18 Task 3 测试/来源修正）

评审发现 r17 Plan 的 `test_same_counts_different_topology_collide_by_design` 对完全相同的输入断言完全相同的输出，不能证明 topology 被 `scene_hash.object_line` 输入合同排除。项目所有者选择选项 1：以 `inspect.signature` 精确断言五参数输入合同，一对一替换该测试；保留结构字段测试，真实 topology-only Blender 语义仍由 Task 18 L3 `hash_scope` 覆盖。

本次仅修正测试与 provenance 基线，不改变 `scene_hash` 产品合同、实现、公开工具面、验收数量或门禁计数。r17 evidence 保持不可变历史；r18 exact tuple 获批并完成 `source_commit → attestation commit` 两提交链前，Phase 0 仍不得执行。

---

## 附录 A：来源

**MCP**：[2026-07-28 正式版公告](https://blog.modelcontextprotocol.io/posts/2026-07-28/) · [Python SDK v2.0.0 Release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0) · [Versioning](https://modelcontextprotocol.io/specification/versioning) · [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) · [Draft Changelog](https://modelcontextprotocol.io/specification/draft/changelog) · [Python SDK](https://github.com/modelcontextprotocol/python-sdk)

**Codex**：[配置参考](https://learn.chatgpt.com/docs/config-file/config-reference) · [MCP 配置与 supported features](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) · [Build skills](https://learn.chatgpt.com/docs/build-skills) · [AGENTS.md discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md) · [Prompt Caching 201](https://developers.openai.com/cookbook/examples/prompt_caching_201#42-stabilize-the-prefix) · [Customization](https://developers.openai.com/codex/concepts/customization)

**Blender**：[5.2 LTS 发布](https://www.blender.org/press/blender-5-2-lts-release/) · [LTS 计划](https://www.blender.org/download/lts/) · [系统要求](https://www.blender.org/download/requirements/) · [5.0 Python API](https://developer.blender.org/docs/release_notes/5.0/python_api/) · [5.2 Python API](https://developer.blender.org/docs/release_notes/5.2/python_api/) · [Python threads are not supported](https://docs.blender.org/api/current/info_gotchas_threading.html) · [DepsgraphUpdate](https://docs.blender.org/api/current/bpy.types.DepsgraphUpdate.html) · [bpy.app.timers](https://docs.blender.org/api/current/bpy.app.timers.html) · [GPU Rendering](https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html) · [创建扩展](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html) · [Add-on 指南](https://developer.blender.org/docs/handbook/extensions/addon_guidelines/) · [MCP Server (Lab)](https://www.blender.org/lab/mcp-server/) · [Blender #157084](https://projects.blender.org/blender/blender/issues/157084) · [Blender PR #156953](https://projects.blender.org/blender/blender/pulls/156953) · [blender_mcp #12](https://projects.blender.org/lab/blender_mcp/issues/12) · [save_as_mainfile 相对路径缺陷](https://developer.blender.org/T33108)

**Apple**：[Notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) · [Keychain](https://developer.apple.com/documentation/security/storing-keys-in-the-keychain) · [文件访问控制](https://support.apple.com/guide/mac-help/control-access-to-files-and-folders-on-mac-mchld5a35146/mac)
