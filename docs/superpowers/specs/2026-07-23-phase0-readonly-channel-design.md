# Phase 0：只读端到端链路 · 设计规格

| 项 | 值 |
|---|---|
| 版本 | v1.16 |
| 日期 | 2026-07-23（初版）· 2026-08-08（r17 确定性 catalog 与 payload 基线；v1.16） |
| 状态 | 交付目标／隔离预检；**Phase 0 未执行**（隔离树只用于组合性与对抗性验证；决策见 URS ADR-3/D-4 与 `docs/decisions/2026-08-07-mcp-sdk-v2-selection.md`） |
| 上游需求 | `Blender-Codex-需求规格说明书-v1.md`（**URS v1.16**；含 20 项稳定验收 ID、三工具 NFR-P1 正式门与可复算证据合同、确定性 catalog / 双内容 result payload 基线、官方 MCP 风险接受边界、continuation/崩溃恢复、process-registry 生命周期、文件 identity 红线、资源上限与 conversion 准入契约及决策 D-4/D-5） |
| 覆盖子系统 | S1 传输与 Bridge 骨架 · S2 MCP Server 骨架 · S4 标识与一致性（读取部分） |

**v1.9 隔离预检快照（历史、非实施证据）**：Plan 代码块提取到隔离树后候选门禁为 **262 passed（L1/unit 235 + L2/contract 27）**、ruff clean、mypy strict 22 个配置内源文件零错误；adapter 实质代码 375 行。真 Blender 大场景反例促使 SceneReader 从数值索引改为有界 slice 分块；本机 100k 共享网格候选预检约 1.2 s，最大 source step 约 22 ms。v1.10 又加入 run cursor fd identity 复核、socket identity 全有/全无约束与验证器有界读取；新的计数、SHA 与 v6 provenance 必须在最终冻结后生成，不能沿用 v1.9 数字。

**v1.10/r13 最终隔离预检（非实施证据）**：46 个 path-bound Python 文件块物化后为 **280 passed（unit 249 + contract 31）**、ruff clean、mypy strict 22 文件零错误，vendor/nested/lock/background/基础 GUI 全绿。100k shared-mesh GUI 的 20-query worker-side nearest-rank P95 约 **1439.21 ms**（max 约 2071.10 ms），`max_tick≈62.12 ms`；固定基线候选门通过。证据由 v6 manifest/provenance 与原始 GUI JSON 固定；Phase 0 仍未执行，92 个执行 checkbox + 1 个 G0 preflight 均未执行。

**v1.11/r15/v8 历史隔离预检（非实施证据）**：旧 v5/v6/v7 数字仅作历史；当时 Plan fresh-tree 物化为 **307 passed（unit 275 + contract 32）**、adapter 35 passed/373 实质代码行，ruff/mypy/vendor/nested/lock 全绿。fresh Blender background 与 GUI smoke 五项全 true；100k shared-mesh Bridge-RPC 20-query worker P95 **1605.18 ms**、max **2560.86 ms**、observer P95 **1655.44 ms**、max tick **62.50 ms**，只关闭 Bridge/continuation 子门，不外推端到端 NFR-P1。v8 manifest/provenance/raw artifacts 见 `docs/audits/evidence/`；Phase 0 仍未执行，92 个 checkbox + 1 个 G0 preflight 均未执行。

**v1.12/r16 proposed（非实施证据）**：A-1 三项平台候选已由项目所有者全部接受；官方 MCP 的模型面与宿主目录均为 26/26，G5 由项目所有者以“当前用户接受风险”关闭，**不是 screenshot/render 缺陷修复或 26 工具稳定性证明**。本轮只修订 Plan-as-code 与文档合同并重新做隔离预检；正式 GUI/NFR/SIGKILL 门仍留给 Phase 0 执行，proposed SHA/计数须在最终机械复核后由用户批准。

**v1.13/r16 E2E 对抗加固（非实施证据）**：二轮红队复现 process-group leader 假清洁、recovery 缺 OS supervisor、provenance 越过共享 deadline，以及 approved tuple/result digest/same-session 的假阳性。合同已同步 fresh marker registry、group-level liveness、bounded provenance、四文档 exact tuple、result preimage 外部复算与真实 MCP identity；最终数字须由新 Plan SHA 的机械物化复核给出。正式 GUI/NFR/recovery 仍未运行，Phase 0 未执行。

**v1.14/r16 process-registry 生命周期闭合（非实施证据）**：三轮红队继续复现 pending/partial scan cache 丢失、unknown first publisher、observer/owner unlink race、PID reuse 截断后续 valid group、cache 无界增长及 public cleanup deadline 被前序 worker cleanup 耗尽。合同改为 parent pre-spawn reservation + 最小 stdlib bootstrap；observer 只读并把并发 entry 消失视为 pending；cache 上限 8、逐 entry 错误聚合、overflow identity-rechecked KILL；public recovery work 期持续预观察并保留 5 s registry cleanup。最终数字须由新 Plan SHA 的 fresh-tree 机械复核给出；正式 GUI/NFR/recovery 仍未运行，Phase 0 未执行。

**v1.15/r16 最终门禁反例闭合（非实施证据）**：独立复核发现标准 unit 的 bytecode 污染、目录第 9 条 record 在 identity 前被截断、unknown entry 隐藏后续可信组及 pre-spawn failure 遗留 reservation。vendor exact-set 不放宽；checks/fixture 清理 bytecode。cache 上限 8 与 deadline-bound 枚举分离，逐 entry 错误继续扫描、所有 overflow 复核后 KILL；parent 在参数构造、SDK enter/`Popen` 未发布 record 的失败路径清理 reservation。正式 GUI/NFR/recovery 仍未运行，Phase 0 未执行。

**v1.16/r17 研究融合（非实施证据）**：MCP `2026-07-28` Tools 规范已明确要求集合不变时返回确定顺序，并说明它改善 tool-list 与 LLM prompt cache。三工具 catalog 因而固定名称/顺序/完整定义；Task 17 冻结 ordered catalog 与 instructions 的 canonical/UTF-8 bytes+SHA，Task 18 进一步保留 60 次 `structuredContent` 与兼容 TextContent 的原文、等价性、字节与 duplication ratio。byte 只作可复算基线，不冒充 token，也不引入 tokenizer 依赖或未经 A/B 的经验阈值。r16 tuple 虽已获所有者批准，但在 source commit/attestation 前被本轮 r17 修订取代；Phase 0 仍未执行。

---

## 1. 范围

### 1.1 本 spec 交付

目标是让 Codex → MCP Server（stdio）→ UDS → Bridge Add-on → Blender 主线程 → 结构化返回的链路端到端成立，并满足 URS §10.1 的 20 项验收与 NFR-P1 正式门；当前只有隔离预检，尚未完成正式 Phase 0 验收。

三个只读工具：`get_blender_status`、`get_scene_summary`、`describe_capabilities`。

### 1.2 本 spec 不交付

| 项 | 归属 |
|---|---|
| Codex Skill | 后续阶段（本阶段只提供 `codex mcp add` 安装文档） |
| Modeling IR、任何写工具 | Phase 1 |
| 事务、快照、回滚 | Phase 1 |
| `plan_scope_hash` | Phase 1（需 IR 才能算依赖集） |
| OpenTelemetry / `traceparent` 传播（URS NFR-O2 后半） | Phase 1（Phase 0 只交付 JSONL 审计；NFR-O2 的「不用 MCP logging」本阶段即遵守） |
| Headless Worker、渲染、导出 | Phase 2 |
| 多实例并发写入协调 | Phase 1（Phase 0 支持多实例**只读**发现与查询） |

### 1.3 本 spec 确立的决策

| ID | 决策 |
|---|---|
| **P0-D1** | **显式会话授权**：扩展 enable 不建 socket；用户在 N 面板点击「允许 Codex 连接」才创建会话目录、socket 与一次性 token |
| **P0-D2** | **双 hash 分层**：`scene_hash` 是**结构摘要 v1**（对象名/object type/matrix/`obj.data` RNA 类型标识与计数五项，非全场景指纹——见 §3.5 语义边界）；`plan_scope_hash` 覆盖 IR 依赖集并追加几何摘要（Phase 1 交付，冲突判定的唯一依据） |
| **P0-D3** | **内核/适配分层**：`bridge/core/` 与 `server/core/` 零外部依赖，bpy 与 MCP SDK 各自隔离在薄适配层 |
| **P0-D4** | **`protocol/` 用 vendoring 而非 wheel**，配 `scripts/checks.sh` hash 一致性门禁 |
| **P0-D5** | **实例存活以握手 `instance_id` 比对为权威判定**，`os.kill(pid, 0)` 仅作预筛 |
| **P0-D6** | **MCP SDK v2（声明 `mcp>=2.0,<3`，`uv.lock` 精确锁定 `mcp==2.0.0`，使用 `MCPServer`）**；SDK v2 同时服务 2025-era 与 2026-07-28 客户端，协议 rollout 与 SDK 版本解耦（URS D-5）。当前 Codex 0.147 宿主的精确合同仍是 `2025-06-18`，不能由 feature flag 名称推断 wire 版本 |
| **P0-D7** | **确定性公开 catalog**：同一 Server 版本与 capability profile 的三工具名称、完整定义与顺序固定为 `get_blender_status` → `get_scene_summary` → `describe_capabilities`；不得按实例状态、调用历史或回合动态增删/重排，易变能力经工具结果表达 |

---

## 2. 架构

### 2.1 进程与生命周期

三个进程，生命周期完全独立：

```
Blender GUI（用户长驻）              MCP Server（Codex 按需拉起）      Codex
  │                                        │
  ├ 扩展 enable                            │
  │   → 只注册 UI panel + operator         │
  │   → 不建 socket、不起线程              │
  │                                        │
  ├ 用户点「允许 Codex 连接」              │
  │   → mkdir 0700 会话目录                │
  │   → token → bind → chmod → listen → I/O│
  │   → session.json (0600) 最后发布       │
  │   → register timer + 两个 handlers     │
  │   → 面板转为「已开启 / 断开」          │
  │                                        ├ 启动：扫描 run/ 发现实例
  │                                        ├ 读 session.json 取 token
  │                                        ├ 连接 + 握手（比对 instance_id）
  │←──────────────── UDS ───────────────────┤                  ←── stdio ──┤
  │                                        │
  │                                        ├ 退出
  │                                        ×   ← Bridge 会话不受影响
  │
  ├ 用户点「断开」或 Blender 退出
  │   → 停 accept、注销 timer/handler
  │   → 删 socket、session.json、会话目录
  ×
```

**核心不对称**：Server 是无状态短命进程，可反复重启；Bridge 会话是有状态长命体，由用户显式开关。这让「Codex 崩了」与「Blender 崩了」成为两个独立故障域，兑现 URS ADR-1 的隔离目标。

### 2.2 Runtime 布局

```
~/Library/Application Support/BlenderCodex/
├── run/                                  0700
│   └── gui-<pid>-<rand8>/                0700   ← 用户点击时创建
│       ├── bridge.sock                   0600
│       └── session.json                  0600
└── logs/
    └── server-YYYY-MM-DD.jsonl           0600
```

`session.json`：

```json
{
  "instance_id": "gui-4711-a3f9c1d2",
  "token": "<43 字符 urlsafe>",
  "pid": 4711,
  "socket_path": "/Users/u/Library/Application Support/BlenderCodex/run/gui-4711-a3f9c1d2/bridge.sock",
  "blender_version": "5.2.0",
  "bridge_version": "0.1.0",
  "envelope_version": 1,
  "socket_external": false,
  "socket_dev": 16777234,
  "socket_ino": 123456,
  "socket_dir_dev": 16777234,
  "socket_dir_ino": 123455,
  "started_at": "2026-07-23T10:00:00Z"
}
```

`instance_id` = `gui-<pid>-<secrets.token_hex(4)>`。

后缀**不能用时间戳**：同一 Blender 进程反复点击「断开 → 允许连接」时，PID 不变，秒级时间戳也可能相同，两个会话会产生同名 `instance_id` 并冲突到同一目录。用随机后缀彻底消除这个碰撞。

后缀的作用是**保证 `instance_id` 唯一**，不是判定存活——存活判定见 §4.3（P0-D5），由握手比对负责，与 PID 复用无关。

**权限的达成机制必须显式，不得依赖 umask**（URS NFR-S4 禁改进程级 umask；Blender 是共享进程，改全局 umask 会影响用户自己的文件保存）：

| 对象 | 机制 |
|---|---|
| `BlenderCodex/`、`run/`、`logs/` | 权限边界从 `BLENDERCODEX_ROOT` 开始：应用目录用 race-safe create-or-validate，必须是当前 uid 所有、非 symlink、精确 `0700`，否则 fail-closed；更上层既存祖先不改权限 |
| 会话目录 | `instance_id` 生成后以 exclusive `mkdir(0700)` 创建，拒绝任何同名既存对象；创建后记录 dev/inode |
| `session.json` | 临时文件用 `os.open(path, O_WRONLY \| O_CREAT \| O_EXCL, 0o600)` 创建后写入，再 `os.replace`（replace 保留源文件权限）；成功发布后记录 dev/inode |
| `bridge.sock` | `bind()` 创建的 socket 文件权限是 `0777 & ~umask`（默认 0755），**bind 后必须立即 `os.chmod(sock_path, 0o600)`**。chmod 前的短暂窗口无害——socket 位于 `0700` 目录内，其他用户根本走不到它。**这正是 0700 目录设计的收益：让 bind-then-chmod 的竞态不可利用，而不是「不需要 chmod」** |
| 日志文件 | 新文件以 `O_EXCL` mode `0o600` 打开并显式 `fchmod(0600)`；既存目标先 `lstat`，再以 `O_NOFOLLOW\|O_NONBLOCK` 打开并在同 fd 上 `fstat`，必须是当前 uid 的 `0600` regular file，否则 fail-closed |

`session.json` 通过固定临时名 `session.json.tmp` + `os.replace` 写入，保证 Server 不会读到半截内容。临时文件一旦由本次调用成功创建，任何写入、关闭或 replace 失败都必须删除；若在 open 前已存在，则视为外部碰撞，启动失败且不得删除。这里保证原子可见性，不宣称 fsync 级崩溃持久性。

### 2.3 安全边界与一处必须修正的保证

| 边界 | Phase 0 的落点 |
|---|---|
| Codex → Server | stdio；Phase 0 三个工具全只读，`approval_mode = auto` |
| Server → Bridge | UDS + 每请求 token 校验 |
| Bridge 进程内 | I/O 线程只做收帧、鉴权、入队；主线程 tick 才触碰 bpy |
| 文件系统 | Phase 0 只写 `run/` 与 `logs/`，不触碰任何用户工程文件 |

**token 保证的边界（URS v1.0 曾表述过强，v1.1 已修订）**：token 存于 `0600` 文件，任何同 uid 进程都能读取后合法连接——token 阻断不了同 uid 越权。

token 的真实作用是把攻击从「扫描 socket 盲连」提升为「必须主动定位并读取会话文件」，并让凭据随会话轮换、不跨会话复用。真正压缩风险的是 **P0-D1 的显式会话**——暴露窗口只存在于用户主动开启期间，而非 Blender 全生命周期。

彻底解决需要 `SCM_RIGHTS` 传递 fd 或系统级沙箱，超出 Phase 0 范围，进风险登记（R-P0-01）。

---

## 3. 组件

### 3.1 模块布局

```
protocol/                    ← 单一真相源，两侧共用
  framing.py                 线格式编解码
  envelope.py                请求/响应信封 + 错误码枚举

bridge/
  __init__.py                扩展入口 shim：from .blender import register, unregister
  core/                      零 bpy 导入
    session.py               token 生成/校验、会话状态机
    router.py                method → handler 分发
    queue.py                 任务队列 + tick
    lifecycle.py             启动/停止状态机
    contracts.py             SceneReader / Clock 协议
  blender/                   唯一定义 bpy 逻辑的目录
    scene_reader.py          SceneReader 实现
    driver.py                timer 注册/注销
    panel.py                 N 面板 + operator
    __init__.py              register / unregister 实现
  _vendor/protocol/          构建时从 protocol/ 复制
  blender_manifest.toml

server/
  core/                      零 mcp 导入
    discovery.py             扫描、探活、stale 清理
    bridge_client.py         UDS 客户端
    path_policy.py           realpath + containment + 扩展名白名单
    audit.py                 JSONL 审计
    versions.py              版本门禁判定
    capabilities.py          describe_capabilities 静态回答
  mcp/
    adapter.py               MCPServer 注册三个工具（SDK v2；实质代码 ≤375 行，URS NFR-C3；v8 隔离实现 373 行）

tests/
  unit/                      L1
  contract/                  L2
smoke/                       L3（真 GUI Blender）
```

**`protocol/` 用 vendoring（P0-D4）。** URS NFR-S8 禁止 Bridge 运行时装包；wheel 声明虽可行，但会让扩展打包与版本发布耦合。vendoring 保持 Bridge 零依赖，代价是一条门禁脚本检查：`bridge/_vendor/protocol/` 与 `protocol/` 的内容 hash 必须一致，否则检查失败。

**扩展命名空间对 import 的两条硬约束**（Blender 扩展在运行时以 `bl_ext.<repo>.<ext_id>` 命名空间加载）：

1. **扩展根目录必须有 `__init__.py` 且在其中暴露 `register`/`unregister`**——Blender 只调用扩展根包的入口，不会去子包里找。根 `__init__.py` 是纯转发 shim（`from .blender import register, unregister`），本身不含 bpy 逻辑，分层论述不变：bpy 逻辑仍只存在于 `blender/`。
2. **`protocol/` 包内部只允许相对导入**（framing / envelope 互引用一律 `from . import ...`）。原因是组合约束：vendored 副本运行在 `bl_ext.<repo>.bridge._vendor.protocol` 深层命名空间下，绝对导入 `import protocol` 会 `ModuleNotFoundError`；而 P0-D4 的逐字节 hash 一致性检查恰好**封死了「vendoring 时改写 import」这条标准出路**——所以约束只能落在源头。注意这个错误在普通 L1、L2 与单纯 hash 检查下**全部隐形**（普通解释器里顶层 `protocol` 恰好可导入），只在 L3 真 Blender enable 时爆发，因此必须靠 §9 的嵌套 import 专项门禁提前拦截。

### 3.2 线格式

```
[4 字节大端 uint32 长度][UTF-8 JSON 载荷]
```

| 规则 | 值 |
|---|---|
| 读端行为 | 必须读满 `length` 字节才切帧——在 §3.7 的非阻塞模型下由每连接接收缓冲区保证（URS NFR-R3） |
| 单帧上限 | 16 MiB，**读写两端同限** |
| 读端超限 | 直接断开，**不做部分解析**（防恶意长度头导致内存耗尽） |
| **写端超限** | 响应使用 `ok_frame_steps()` 以 `JSONEncoder.iterencode()` 增量编码；每个 piece 累计字节数并在追加前检查 16 MiB。超过上限时**不得发送**原响应，改回 `INTERNAL_LIMIT_EXCEEDED` 错误帧并记诊断日志。编码步骤通过 `ResponseSteps` 回到队列尾部，不能在一个 tick 内同步物化大 payload |
| 验收余量 | URS 要求 5 MiB 通过，上限留 3 倍余量 |

### 3.3 请求 / 响应信封

```json
{ "v": 1, "id": "<uuid4>", "token": "<session token>",
  "method": "ping" | "status" | "scene_summary", "params": {} }
```

```json
{ "v": 1, "id": "<echo>", "ok": true, "result": {} }
```

```json
{ "v": 1, "id": "<echo>", "ok": false,
  "error": { "code": "BRIDGE_BUSY", "message": "...", "retryable": true } }
```

`params` 在信封层是开放 object，**这不违反 URS FR-05**。Phase 0 的 `scene_summary` 参数是显式的 `include_collections` / `include_managed_objects` 布尔值；Server adapter 必须把它们原样写入 UDS `params`，Bridge Router 再传给 `SceneReader.snapshot_steps()`。两个 `false` 都必须在 reader 源端跳过相应 Blender 集合枚举，不能先生成后裁剪。FR-05 约束的是 IR 内部 `operation.payload` 的判别联合，校验发生在 Server 的 IR 校验器中，不在传输层。Phase 1 的 IR 以 `params.modeling_ir` 进入，**信封无需改版**。

`v` 是信封版本，独立于 IR schema 版本与 Bridge 版本（URS NFR-C4 要求三者独立编号）。线上字段名用短名 `v`；同一个值在 `session.json` 与 `describe_capabilities` 中的字段名是 `envelope_version`——**同一概念，两处命名不同是刻意的**（线上省字节，对外可读）。

**wire 类型按 JSON 类型精确校验，不采用 Python 的宽松子类/强制转换语义。** object / array / string / number / boolean / null 只按 JSON wire 类型解释；文本必须是合法 UTF-8；number 必须为有限值，拒绝 `NaN` / `Infinity` / `-Infinity` 以及解析溢出为无穷的数值，编码端固定 `allow_nan=False`。请求的 `id/token/method` 必须是 string，`params` 必须是 object；`v` 缺省时按 1 兼容，出现时必须是 exact integer 1，JSON `true` 不得借 `bool <: int` 冒充版本，也不得把字符串隐式转为数字或把数字隐式转为字符串。响应必须含 exact integer `v=1`、与请求完全相同的 string `id`、exact boolean `ok`；成功响应的 `result` 必须是 object，失败响应的 `error` 必须是 object 且 `code/message` 为 string、`retryable` 为 exact boolean。除合法的 `v` 不匹配映射为 `ENVELOPE_VERSION_MISMATCH` 外，任何 malformed response shape 都 fail-closed 为 retryable `BRIDGE_UNAVAILABLE`。

非法 UTF-8、畸形 JSON 或超过实现深度上限的嵌套 JSON 必须结构化拒绝或断开，不能让 `UnicodeDecodeError` / `RecursionError` 逸出并杀死 I/O 线程。未知请求外层字段仍为向前兼容而忽略；该兼容不放宽已知字段的类型。若一次 `recv()` 解出多帧，首个被拒帧导致连接关闭后，**同一批次其后的帧不得再派发**，避免认证/协议拒绝后的尾随请求越过边界。

**`ping` 的响应**（握手用，§4.3）：

```json
{ "v": 1, "id": "<echo>", "ok": true,
  "result": { "instance_id": "gui-4711-a3f9c1d2",
              "bridge_version": "0.1.0",
              "blender_version": "5.2.0",
              "envelope_version": 1 } }
```

`ping` 与其余 method 一样需要 token。这不会与 stale 会话冲突：若 `session.json` 是残留的，其进程已死、socket 连不上，流程在连接阶段就终止，走不到 token 校验。反之若 socket 连得上，说明进程活着，文件里的 token 就是当前有效的。

### 3.4 `bridge/core/` 契约

```python
class Clock(Protocol):
    def monotonic(self) -> float: ...

class SceneReader(Protocol):
    def blender_version(self) -> str: ...
    def status_info(self) -> tuple[str | None, int]: ...
    def snapshot_steps(
        self, *, include_collections: bool = True,
        include_managed_objects: bool = True,
    ) -> Generator[None, None, SceneSnapshot]: ...
```

`status_info()` 只读取路径与当前 revision；`snapshot_steps()` 是 cooperative generator，返回值在 generator 完成时才产生。`SceneSnapshot` 是纯 dataclass，**不含任何 bpy 对象**——这是分层边界的物理保证。`SnapshotInvalidated` 表示 revision 或文件 generation 在 continuation 期间变化，Router 将其映射为 `SCENE_QUERY_FAILED`，错误响应只含异常类型。

```python
@dataclass(frozen=True)
class SceneSnapshot:
    scene_revision: int
    scene_hash: str                 # "sha256:<hex>"
    scene_name: str                 # 实际读取的 scene，见 §3.5
    scene_path: str | None          # bpy.data.filepath or None
    units_system: str               # "NONE" | "METRIC" | "IMPERIAL"
    units_scale_length: float
    object_count: int
    mesh_count: int
    camera_count: int
    light_count: int
    collections: tuple[str, ...]
    managed_objects: tuple[ManagedObject, ...]   # Phase 0 恒为空元组
```

`managed_objects` 在 Phase 0 恒为空——尚无任何对象被写入 `bcx.v1.id`。字段现在就位是因为它属于 URS 的 `get_scene_summary` outputSchema，Phase 1 才有内容。

`include_collections=false` / `include_managed_objects=false` 必须贯穿 adapter → UDS → Router → reader，并在 reader 数据源处短路；不得先枚举所有 collections/managed objects 再在 envelope 层删除。

**Reader 资源上限（v1.11）**：单次 `scene_summary` 对 object 与 collection 源各自最多物化 `1_000_000` 项、各自最多 64 MiB 文本；上限检查必须在继续物化前进行。超过上限抛 `SnapshotLimitExceeded`，Router 结构化为 `INTERNAL_LIMIT_EXCEEDED`，不得截断后伪装成功。`false` 源端短路不消耗对应集合上限。

`bridge/core/` 内**不得出现 `import bpy`**，由 `scripts/checks.sh` 静态检查强制。

### 3.5 `scene_hash` 算法

```
line(obj) = f"{obj.name}\t{obj.type}\t{q(matrix_world)}\t{data_kind}\t{data_counts}"
q(m)      = 16 个浮点直接以 .6f 定长格式化；字符串 -0.000000 归一为 0.000000
digest_in = "\n".join(sorted(line(obj) for obj in target_scene.objects))
scene_hash = "sha256:" + sha256(digest_in.encode("utf-8")).hexdigest()
```

**`target_scene` 的选择策略（依据 SPIKE-1.3 实测更新）**：

```python
target_scene = bpy.context.scene or bpy.data.scenes[0]
```

SPIKE-1.3 已实测确认 timer 回调内 `bpy.context.scene` 可用且返回活动 scene（5.2.0 GUI 模式），故**主选活动 scene**——这正是用户正在看的那个。回退 `bpy.data.scenes[0]` 仅作防御（context 异常返回 `None` 时）；注意 `bpy.data` 集合按**名称字典序**维护（SPIKE 附带实测确认），`scenes[0]` 是「名字最靠前的」而非「最早建的」。无论走哪条路径，`scene_name` 都在响应中回报，调用方永远知道读的是哪个 scene（风险 R-P0-07）。

`SceneSnapshot` 因此增加一个字段 `scene_name: str`，`get_scene_summary` 的 outputSchema 同步增加（见 §6.2）。

| 决定 | 理由 |
|---|---|
| 排序后再 hash | Blender 的对象遍历顺序不保证稳定 |
| `-0.0` 归一化为 `0.0` | 否则数值相等的场景会产生不同 hash |
| 量化到 1e-6 | 吸收浮点噪声，同时保留亚毫米级差异 |
| 含 `obj.name` | 重命名是一次真实变更，change detector 应当感知 |

实现不得用 `sorted(line(obj) for ...)` 在单一步骤物化整场景，也不得用 `scene.objects[index]` 逐项读取：Blender 5.2.0 的数值索引从集合头部步进，真 Blender 10k/20k 反例呈近 O(N²)。`snapshot_steps()` 每一步以不超过 1024 项的 collection slice 顺序取源对象，在同一步内转换成纯 Python line 并清除所有 bpy wrapper 后再 yield；每个 source chunk 排序后，用 `heapq.merge(*chunks)` 产生与全量 `sorted()` **逐字节相同**的输入顺序，hash merge 与 collection 名读取每 128 项 yield。revision/generation 在每个 source/collection chunk 前后及每个 hash 项前检查。JSON 响应同理由 `ok_frame_steps()` 按 encoder piece 分片。yield 之间只允许 scene 名、整数 cursor/count、revision/generation 与字符串/tuple chunk；不得保存 Scene/Object/Collection wrapper 或任何 bpy collection iterator。

`scene_revision` 是会话内单调计数器，由 persistent `depsgraph_update_post` handler 递增，Phase 0 需注册该 handler。另有 persistent `load_pre` 在 Blender 释放旧数据前递增 generation（并同步递增 revision）；每个 continuation step 前验证二者，marker 不一致即抛 `SnapshotInvalidated`。计数器在 Bridge 重启后归零，因此**只能用于会话内比对**。

跨进程、跨会话的比对只能用 `scene_hash`，但**它回答的是「结构是否变过」，不是「场景是否变过」**——见下方语义边界。Phase 0 不提供完整场景等价判定；需要它的场合（Phase 1 冲突检测）由 `plan_scope_hash` 的几何摘要承担。

**语义边界（2026-08-07 两轮审计 F-01 / R-04）：本值是「结构摘要 v1」，不是全场景指纹，也不对「整个场景」敏感。** 覆盖面 = 对象名/object type/量化 matrix/`obj.data` 的 RNA 类型标识（无 data 为空字符串）与顶边面**计数**，仅此五项；顶点坐标、拓扑连接、modifier 参数、材质/节点、可见性、collection 归属、相机/灯光/场景设置**均不可见**。会话内细粒度变更由 `scene_revision`（depsgraph 计数）承担；**跨会话等价性禁止以本值单独作证**；Phase 1 的 `plan_scope_hash` 必须对 IR 目标对象追加几何摘要（URS v1.2）。验收必须由 L1 的字段结构断言 + L3 的真 Blender 顶点移动 fixture 共同证明该边界（§7.3），不能用纯函数同构 fixture 代替真机证据。

**注意这不等于说 `scene_hash` 是冲突判定依据。** 按 P0-D2，Phase 1 的冲突判定用 `plan_scope_hash`（只覆盖 IR 依赖集）。`scene_hash` 的职责限于粗粒度结构变更检测与快照标识：它只对结构摘要 v1 的五类字段敏感，既会漏掉顶点级变化，也会因依赖集外对象的覆盖字段变化而过度触发，因此禁止用作拒绝计划的依据。

### 3.6 任务队列与 tick

```python
ResponseSteps = Generator[None, None, bytes]

class TaskQueue:
    def __init__(self, handler: Callable[[Request], bytes | ResponseSteps],
                 clock: Clock, capacity: int = 64) -> None: ...

    def submit(self, req: Request, reply: Callable[[bytes], None],
               deadline: float) -> None:
        """I/O 线程调用；queued + active 达到容量时抛 QueueFull。"""

    def tick(self, budget_ms: int) -> float:
        """主线程调用。在预算内批量处理，返回建议的下次调用间隔（秒）。"""
```

| 参数 | 值 | 依据 |
|---|---|---|
| 队列容量 | 64 | 超出抛 `QueueFull` |
| tick cooperative checking budget | 50 ms | URS NFR-R4；不是硬抢占墙钟上界 |
| 有任务时返回间隔 | 0.01 s | 尽快继续排空 |
| 空闲时返回间隔 | 0.02 s | 本机降低首个请求等待；约 4.4× 唤醒增量已知，电量影响未测 |

**队列满的响应路径**：容量必须计 `len(queued) + active`。任务/continuation 被主线程取出执行时仍占一个 active slot，完成、过期或异常后才释放；否则 I/O 线程可在出队到回队的窗口把 64 扩成 65。`submit` 抛 `QueueFull` 后，**I/O 线程直接回一帧 `BRIDGE_BUSY`（`retryable=true`）**，请求不入队。

Bridge 对每个实例另设 `MAX_SCENE_SUMMARY_TASKS = 2`，同样按 queued + active continuation 计数；complete、deadline、exception、drain 每条终止路径都释放槽位。该上限独立于总 64 槽，避免两个大 reader 工作集叠加并饿死 ping/status。

**过期请求的处理**：每个任务携带 `deadline`（入队时间 + 客户端超时）。`tick` 在取出任务后、推进每个 continuation step 前以及发送最终 frame 前检查；已过期的**直接关闭 continuation、丢弃且不回复**——绝不能在过期后继续遍历或发送迟到结果。

**reply 绝不直接写 socket**（§3.7 规则 3）：reply 的实现是「入 outbox + 唤醒 I/O 线程」，对已断开连接的入队被静默丢弃。队列层防御性捕获任意普通 `Exception` 并只记诊断日志、不向上传播——不能假设失败只表现为 `OSError`，tick 循环的存活优先于任何单个响应。

`tick` 一次处理**多个**任务直到预算耗尽。handler 可直接返回小响应 `bytes`，也可返回 `ResponseSteps`；每推进一步若尚未完成，就把 continuation 放回同一队列**尾部**并释放 active slot，使 `ping`/`status` 与其他 summary 保持公平。generator 完成时必须以 `bytes` 作为 return value。

**50 ms 是 cooperative checking budget，不是绝对墙钟保证。** Python 无法抢占正在执行的单次 bpy property access、原生调用、encoder piece 或最终有界 frame 构造；诚实上界是 `50 ms + 有界原子 step 成本 + Blender 调度抖动`。所以 aggregate work 必须拆成 object/hash/collection/encoder piece 等小步骤，且每个原子步骤本身需有界并经实测；无法满足者转交 Headless Worker。对抗 fixture 中旧同步路径单 tick 约 619 ms；cooperative 12.59 MiB 响应分 36 ticks，最大 tick 53.76 ms、总耗时 1.8 s。该数字是回归证据，不是跨硬件绝对保证。

**deadline 的时钟与来源**：`deadline = time.monotonic()（入队时刻）+ 该 method 的超时值`。超时值以 §4.2 的表为权威，Bridge 内置同一张 method → 超时映射——两侧由同一份 spec 实现，共享 spec 级常量，信封不需要携带超时字段。一律用 `monotonic`，不用墙钟。

driver 侧注册**必须带顶层异常护栏**：

```python
def _tick_guard():
    try:
        return queue.tick(budget_ms=50)
    except Exception:
        _diag_log.exception("tick failed")
        return 0.1

bpy.app.timers.register(_tick_guard, persistent=True)
```

首次注册的 `first_interval` 必须与正常空闲间隔同为 0.02 s；异常护栏返回的 0.1 s 是显式诊断退避，只在 tick 抛出异常后生效，不代表正常 idle 合同。

**护栏不可省略**：`bpy.app.timers` 对抛异常的回调**直接注销**。§3.6 已强制捕获的两类异常（SceneReader、reply）之外，任何逸出的异常（信封序列化、framing 编码、队列内部缺陷）都会永久杀死 tick——此后 I/O 线程还活着、面板还显示「已开启」、请求照常入队然后全部过期，Server 端只见 `BRIDGE_TIMEOUT`，Bridge 变成无人知晓的静默僵尸。护栏保证回调永不向 timer 抛异常、永远返回下次间隔。

`persistent=True` 与 persistent handlers 既是 Phase 0 会话生命周期契约，也是为 Phase 1 hard 回滚（`wm.open_mainfile`）铺路（URS NFR-R6）。Phase 0 已验证 `load_pre` 的 generation 失效路径；Phase 1 仍需直接覆盖 hard 回滚后的完整可用性。

### 3.7 连接 I/O 模型与确定性关闭

**连接读取模型是规格，不是实现自由度：单 I/O 线程，select 多路复用，非阻塞读。**

```python
wake_r, wake_w = socket.socketpair()
wake_r.setblocking(False)
wake_w.setblocking(False)

# I/O 线程主循环
while not stopping:  # 每次 iterate 返回后都重读；wake 只降低退出延迟
    ready, _, _ = select.select([listener, wake_r] + established_conns, [], [])
    if wake_r in ready:
        drain_wake_nonblocking()
        wake_pending = False
        if stopping:
            break
```

五条强制规则（v3 审计后修订：写路径改为**单写者**，发送锁废止）：

1. **select 集合包含所有已建立连接**，不只是 listener。已建立连接设为非阻塞；每连接维护一个接收缓冲区，数据到达即追加，凑满「4 字节长度头 + length 字节」才切出一帧进入鉴权与路由。**NFR-R3 的「读满 length 字节」由缓冲逻辑保证，不是阻塞 recv 循环**——阻塞循环会让一个只发半个长度头的客户端楔死整个 I/O 线程。活跃连接最多 **64** 个；超限的新连接立即关闭。`accept()` 后在非阻塞设置或登记完成前仍由局部变量拥有，任一步失败都必须 close；close 失败则保留引用并暂停继续 accept，后续 I/O 轮次重试，不能丢失 fd ownership。
2. **分层入站上限**：单帧声明或接收缓冲区不得超过 16 MiB；所有连接尚未组成完整帧的累计待收字节不得超过 **32 MiB**；一个已成帧请求的 JSON payload 不得超过 **64 KiB**。任一上限超出即由 I/O 线程关闭该连接，不进入认证/队列。全局待收统计在同一 I/O 线程每次 recv 后执行，因此不会让 64 个慢客户端各自占满 16 MiB。
3. **单写者：所有 socket 写只由 I/O 线程执行。** 主线程 tick 的 reply 与 QueueFull 的 `BRIDGE_BUSY` 都只是**把整帧追加进该连接的发送队列（outbox）并唤醒 select**；I/O 线程在连接可写时非阻塞发送（部分写以偏移量续写，整帧序不可交错——由单写者结构保证，无需锁）。**主线程从不触碰连接 socket**：不读响应的客户端只能堆积自己的 outbox，不能把发送阻塞成本加入 timer tick；这消除一种阻塞源，但不把 NFR-R4 的 cooperative budget 提升为硬墙钟保证。
4. **发送背压有双层上限**：单连接 outbox 最多 **32 MiB**，全部连接合计最多 **64 MiB**。超限时 `send()` 只在锁内把该连接标为 closing 并唤醒；真正 close 仍由 I/O 线程执行，主线程不碰 socket。计数定义为「进程仍持有的完整 frame bytes」：部分 send 不递减，只有整帧 `popleft` 或 drop/stop 清空时才释放，避免底层 bytes 尚在内存却低估全局占用。fd 数字可能复用，`send()` 必须同时验证映射中的对象 identity，不能只判断 key 存在。
5. **I/O 线程每轮迭代有顶层护栏**（与 §3.6 的 tick 护栏对等）：单连接的任何异常只允许断开该连接；意外异常记诊断日志后继续循环。没有这条，一个 `BrokenPipeError` 逸出就会杀死唯一的 I/O 线程——listener 不再 accept、面板仍显示「已开启」，与 tick 之死同构的静默僵尸。

所有唤醒都经 `_wake_pending` 合并：持锁发现已有未消费唤醒时不再写；首次通知对非阻塞 `wake_w` 写一字节，`BlockingIOError` 也视为已有字节可唤醒。I/O 线程 drain 后才清 pending。这样高并发 reply/wake storm 既不会填满 socketpair 后阻塞主线程，也不会丢失停止通知。`wake_w` 同时承载「outbox 有新帧」与停止通知；收到后先 drain、再检查停止标志。单线程模型下不存在「连接线程」，join 一个线程即回收全部连接处理。

**停止正确性不得依赖本轮一定观察到 wake byte。** `_io_iterate()` 返回后，外层循环必须重新读取停止标志；即使 join 超时后 stop 已关闭 listener/socketpair、上一轮 select 未把 wake fd 列入 ready，也不得再拿已关闭 fd 进入下一次 select 并异常自旋。

`unregister()` 固定顺序：

1. 置停止标志
2. 唤醒 `select`
3. join I/O 线程（超时 2 s）
4. **`shutdown()` + `close()` 所有仍活跃的已 accept 连接**
5. 关闭监听 socket 与 `socketpair`，随后第二次 join I/O 线程（超时 1 s）
6. 注销 timer
7. 注销 `depsgraph_update_post` 与 `load_pre` handlers
8. 清空任务队列（对残留任务不再回复）
9. 删除 socket 文件与 `session.json`
10. 删除会话目录

**第 4、5 步不可省略。** 首次 2 s join 可能因为线程仍阻塞在本地 transport 调用中而超时；第 4/5 步先关闭活跃连接、listener 与 socketpair，再做第二次最多 1 s join，确认 transport close 已使线程退出。漏掉连接关闭会同时造成 fd 泄漏（直接导致「会话循环 20 次无泄漏」验收失败）与 Server 侧挂起等待响应；漏掉第二次 join 则会在资源已关闭后仍遗留短命线程。该回收承诺限定于普通本地非阻塞 I/O；已经进入内核且不可中断的异常文件系统/设备调用不承诺绝对墙钟上界。

`stop(...) -> bool` 只在 transport、连接、pending-close 引用、线程和路径清理全部完成时返回 `True`。任一 close/join 失败时仍执行安全的 timer/handler 注销与队列 drain，但**不得进入第 9/10 步删除 socket/session 路径**；必须保留可重试的 session 引用。driver 仅在 `True` 时清空模块状态；否则面板显示「清理未完成，点击重试」，disconnect 返回 `CANCELLED`，下一次 start 也必须先完成旧 session 的 cleanup，不能覆盖引用制造孤儿。

第 9/10 步是 identity-bound cleanup：会话启动时记录 session/fallback 目录及成功 bind 的 socket、成功 replace 的 session 文件类型与 `(st_dev, st_ino)`；停止只删除本次取得 ownership 且当前类型/identity 完全匹配的路径或空目录。bind 冲突、路径/目录被换入、identity 缺失一律保留。所谓「全量回滚」只覆盖本次创建并能证明 ownership 的对象。

会话期间必须维护一个活跃连接集合（加锁），accept 时加入、连接结束时移除；关闭时各连接的 outbox 积压一并丢弃，不做 flush——确定性关闭优先于末尾响应的送达。

**任一步失败都记日志并继续执行后续步骤**，避免停在半清理状态。core lifecycle 的 `stop(unregister_timer, unregister_handlers)` 必须在第 6/7 步调用 Blender driver 传入的真实回调，不能只在注释里声称注销；`unregister()` 必须幂等——重复调用不抛异常。

---

## 4. 数据流

### 4.1 会话建立

用户点击面板按钮 → operator 在主线程执行（context 完整，是做此类初始化的正确时机）。

**职责划分是可测性的前提**：会话目录、socket、token 的创建全部在 `bridge/core/lifecycle.py` 内，`blender/panel.py` 的 operator 只负责调用它并更新 UI 状态。

```python
# bridge/core/lifecycle.py —— 零 bpy 依赖，L2 可直接驱动
session = Session.start(runtime_root, scene_reader, meta)
```

```
Session.start() 内部：
  instance_id = f"gui-{os.getpid()}-{secrets.token_hex(4)}"
  create-or-validate runtime_root/run 为当前 uid 的精确 0700
  exclusive mkdir(0700) 创建会话叶目录并记录 identity
  token = secrets.token_urlsafe(32)
  确定 socket 路径；必要时 exclusive 创建可推导的短目录并记录 identity
  bind socket → 记录 identity → os.chmod(sock, 0o600) → listen(8)
  建立两端非阻塞 socketpair
  启动 I/O 线程
  最后写 session.json（O_EXCL + 0o600 临时文件 → os.replace）并记录 identity

# bridge/blender/panel.py —— operator 额外做：
  事务式注册 timer(persistent=True)
  + depsgraph_update_post handler(@persistent)
  + load_pre handler(@persistent)
  任一步失败：只逆序注销本次新增 callback，并 stop core session
  面板状态 → 「已开启 / 断开」
```

因为建目录、bind、写 token 都在 core 里，**L2 契约测试可以直接断言权限位（`0700` / `0600`）而无需启动 Blender**（§7.2）。若把这些逻辑写在 operator 中，该验收项就只能退到 L3。

**sun_path 长度校验与崩溃可恢复回退**：macOS 的 UDS 路径受 `sun_path` **104 字节**硬限制。完整默认路径超过 100 字节时，短目录固定为 `/tmp/bcx-<sha256(instance_id)[:16]>`，exclusive 创建为 0700。不能使用进程各自的 `$TMPDIR` 或不可推导的 `tempfile.mkdtemp(prefix="bcx-")`：Blender 与 MCP Host 的环境变量可能不同，且 Blender 若在 `session.json` 发布前硬崩溃，Server 会失去随机路径的定位信息。`session.json.socket_path` 仍是发布后权威路径，并同时记录 `socket_external`、socket 与父目录 dev/inode。发布前崩溃则由会话目录 basename 推导短路径，只在会话/回退目录均超过 60 秒、当前 uid、0700、且只含已知 socket 时清理。

**`session.json` 最后发布（2026-08-07 审计 F-04 修订）**：严格按 bind → 记录 identity → chmod `0600` → listen → socketpair → I/O 线程 → 原子发布 session.json；先发布再初始化会留下被 Discovery 长期误识别的「假会话」。任一步失败执行 identity-bound 回滚；临时文件若由本次创建，则写入/关闭/replace 任一失败都删除。被换入或无法证明 ownership 的对象不删，保留供后续扫描/人工检查，因此这里不再使用无条件「全量删除」措辞。

**token 随每个请求校验，不是只在握手时。** 用 `secrets.compare_digest` 常数时间比较。Server 可能中途重启重连，一次性握手态在此不成立。

### 4.2 三个工具

| 工具 | 流程 | 超时 |
|---|---|---|
| `get_blender_status` | Server 扫描 → 并发向各活实例发 `status` → 聚合 | **单一绝对 deadline = 入口 + 3 s，贯穿发现与聚合**：发现阶段传入剩余预算，聚合阶段用 `deadline - now`。**不得给聚合另开一个完整 3 s 窗口**——那会让最坏耗时变成 2.5 + 3.0 = 5.5 s（复审 F-02） |
| `get_scene_summary` | Server 将两个 include flags 写入 UDS `scene_summary.params` → I/O 线程校验 token 后**入队即返回** → 主线程 tick 分步推进 `SceneReader.snapshot_steps(...)` 与 `ok_frame_steps()` → reply；`false` 在 reader 源端跳过对应枚举 | 15 s |
| `describe_capabilities` | Server 本地回答，**不经 Bridge**；`include_instances=True` 时才扫描（默认 `False`，Blender 离线也能回答——复审 F-07） | — |

**`get_blender_status` 必须并发，不能串行，也不能按请求新建线程池。** URS NFR-P1 要求只读工具 P95 < 2 s；串行遍历 N 个实例会退化为 N × 2 s，而每请求新建 executor 会让并发 MCP 调用把线程数乘上请求数。adapter 进程只保留一个模块级、固定 `max_workers=8` 的共享 `ThreadPoolExecutor`，并以一把 aggregation lock 串行进入 submit / `as_completed` 聚合区。锁等待也消耗同一个 3 s absolute deadline；未在 deadline 前取得锁或未提交/完成的实例计入顶层 `partial=true` 与 `skipped_count`，不得再开新窗口。单实例 Bridge 调用上限仍为 2 s，并同时受整体剩余预算约束。

每个 `status` 结果的 `instance_id` 必须与发起调用的发现实例精确一致；缺失、类型错误或串到另一个实例都按该实例 retryable `BRIDGE_UNAVAILABLE` 隔离，并使 discovery cache 失效。非 BUSY 的本次失败必须覆盖缓存里的旧 `busy` 状态。`scene_summary` 的 `summary` 只接受真实 JSON object/Python `dict`，不得用 `dict(list_of_pairs)` 等隐式强制转换接受错误 wire shape；其余缺字段或类型错误统一在 MCP 边界映射为 retryable `BRIDGE_UNAVAILABLE`。

**Server 进程级 scene-summary 准入（v1.11）**：adapter 以容量 2 的有界 semaphore 保护完整 MCP middleware `call_next`，不是只保护同步 `scene_summary_impl`。SDK v2 的 `Tool.run` 会在同步工具函数返回后执行 `convert_result`；因此槽位必须覆盖 reader、Pydantic/structured result 转换、wire shaping 与 audit postlude，直至 middleware finally。第三个 wire 请求不等待、不阻塞 async 事件循环，立即返回 retryable `BRIDGE_BUSY`；异常、结构化失败、审计失败与成功均释放槽位。该上限与 Bridge 的每实例 2 槽独立，合同只保证各层各自上界，不把它们相乘宣称为全系统内存上界。

**网络线程绝不触碰 bpy。** token 校验是纯字符串比较，放在网络线程既安全又必要——未认证请求不该有资格占用主线程预算。

`describe_capabilities` 不需要 Blender 在线，这是刻意的：它回答「你支持什么」，不是「现在能干什么」。

**没有 `connected` 实例时 `get_blender_status` 返回引导文案，不是错误。** 完全没有候选时列表为空；存在 disconnected/mismatch 行时保留诊断行但仍给 guidance。

### 4.3 实例发现与存活判定（P0-D5）

```
扫描 run/*/session.json
  → os.kill(pid, 0) 预筛（仅用于跳过明显已死的会话，避免无谓连接）
  → 连接 session.json 中 socket_path 指向的 socket
  → 握手：发 ping，比对响应中的 instance_id 与 session.json 一致
  → 校验 ping 返回的 envelope_version 与 Server 自身一致
  → 全部通过才计入活实例
```

**信封版本协商（URS NFR-C4）**：握手时 `envelope_version` 不一致的实例**不算死实例也不算活实例**——它出现在 `get_blender_status` 的列表中（`bridge_state: "disconnected"` + `version_warning` 说明版本不匹配及各自版本号），但其余工具对它返回 `ENVELOPE_VERSION_MISMATCH`。不清理其会话目录：进程活着，只是话不投机。

**`instance_selector` 的语义**（`get_blender_status` 入参）：与 `instance_id` **精确匹配**，无前缀、无模糊。`null` = 返回全部实例；给定值无匹配时返回 `ok=true` + 空列表 + guidance（与「无活实例」同路径，不是错误——selector 指向的实例刚被用户断开是正常场景）。

**权威判定是握手比对，不是 PID 探活。** PID 会被复用，`os.kill(pid, 0)` 成功不代表那是 Blender；而比对 `instance_id` 单一、可靠、不需要额外依赖（Bridge 侧无法引入 psutil）。

**发现的预算语义（三轮审计 F-03 / R-03 / F-01 累积修订）——有界，不是绝对**：

- `deadline` 在 `_scan()` **入口**创建，覆盖枚举、`stat`、读取、解析、排序与 probe 全过程；默认 **2.5 s**，`get_blender_status` 会传入自己的剩余预算（见 §4.2）。
- 枚举用惰性 `os.scandir()`；每次 `next()` 前检查预算，单窗口处理 **256** 项并保留 iterator cursor。复用跨调用 cursor 前，必须重新打开当前 `run/` 并以 `fstat` 对比 cursor fd、当前目录和初始化时记录的 identity；任一不符即清空 cursor/backlog、标记 `partial`，只在 fd 当前 identity 仍等于记录值时关闭该 fd，避免 different-identity 数字复用误关无关文件。有限次 `fstat` 不能消灭最后一次检查后的 TOCTOU，POSIX 也没有可移植的 open-file-description nonce；同进程外部代码主动关闭私有 cursor fd、再把同 identity fd 换回同一数字不在保证范围。窗口内按 mtime 排序后，每次只探测前 **16** 个，但其余候选必须进入 backlog；后续调用先耗尽 backlog，再推进 iterator。这样同时避免第 257 项之后和同窗第 17 项之后永久饿死。**不得用 `sorted(iterdir())`**——它会在检查生效前物化整个目录（旧实现实测 4.8 s）。
- 候选按 **mtime 由新到旧**分批探测，而不是每次重新丢弃第 17 项以后候选。按目录名排序会饿死字典序靠后的最新活实例；只保留前 16 而无 backlog 则会饿死同窗较旧的活实例。
- 枚举时记录会话目录 `(st_dev, st_ino)`；读取时先以 `O_DIRECTORY|O_NOFOLLOW|O_NONBLOCK` 打开目录并 `fstat` 匹配，再相对 dir-fd 以 `O_NOFOLLOW|O_NONBLOCK` 打开 `session.json`，在**同一文件 fd** 上 `fstat`、按 64 KiB 上限读取和 JSON/字段校验。socket 与其父目录的四个 dev/inode 字段全部必填；部分或全部缺失时隔离且不得连接。拒绝 FIFO/device/symlink、父目录/文件换入、读取中扩容与合法 JSON 缺字段。
- `session.json.instance_id` 必须与目录 basename 全等；否则隔离。这个单一约束也排除了同一次扫描中两个不同目录伪装成同一 ID 后令 `find()` 顺序相关的歧义。
- stale cleanup 重新绑定同一目录 identity，只相对 dir-fd 删除 `session.json`、`session.json.tmp`、`bridge.sock` 三个已知名称，绝不递归。cleanup 允许部分完成：已成功 unlink 的已知叶项不回滚；未知子项只令最终 `rmdir` 失败并保留目录，不阻止此前已验证叶项的清理。外置 fallback 必须先按 §4.1 的发布 identity 清理；identity 不符则连 session 元数据也保留。发布前无 metadata 时仅使用确定性短路径 + uid/mode/宽限期判据。
- absolute deadline 贯穿 cleanup；每次 `open/fstat/stat/unlink/rmdir` 前重查，预算耗尽即停止后续动作、把本轮标为 partial，并保留尚未处理的证据供后续扫描重试。固定次数/常规本机 I/O 仍不提升为可抢占的硬墙钟保证。
- dead、corrupt、发布前 fallback 或未知 child 的任一 cleanup 返回未完成时，都必须把本次 `ScanStats` 标记为 `partial=true`、增加 `skipped_count` 并给出稳定 reason；不能因候选未进入最终实例列表而把清理失败隐藏掉。
- **诚实边界**：本设计在每次目录/file I/O 前检查预算，并把目标绑定到已验证 fd；常规文件系统调用进入内核后仍不可强制取消，因此不对失效网络文件系统或内核卡死宣称绝对墙钟上界。
- 截断或预算耗尽通过 **`ScanStats(partial, skipped_count, reasons)`** 上报。`instances_with_stats()` / `find_with_stats()` 必须用 absolute deadline 限制 discovery lock 获取，并在同一把锁下返回「instances（或命中实例）+ 产生该结果的 ScanStats 副本」，cache hit 也一样；锁等待超时返回 `discovery lock deadline` 的 partial 快照。adapter 禁止在取实例后再独立读取 `last_scan`，否则并发扫描会把另一轮统计错配到本轮结果。`last_scan` 仅作内部诊断。无法在不继续枚举的情况下得知精确余量时，`skipped_count` 是保守下界（至少 1）；绝不伪装成「没有实例」或触发误清理。

**发现是惰性的，且带短缓存。** discovery **不在 Server 启动或 import 期执行**，首次需要时才扫描并缓存 1 秒；缓存过期或收到 `BRIDGE_UNAVAILABLE` 时调用 `invalidate()`。失效通知用一槽队列有界合并、不得等待 discovery 扫描锁；扫描期间到达的通知必须阻止该扫描发布缓存，下一次请求重新扫描。同一 Discovery 的停止→过期→重启恢复进入 L2 回归。

### 4.4 版本门禁在 Phase 0 的实际效果

Bridge 在 `session.json` 与 `status` 响应中上报完整版本号，Server 侧 `versions.py` 判定。

支持判定必须比较**完整版本号**：仅 `5.2.0` 为 supported，不得以 `5.2` 前缀或 `5.2.x` 范围放行。`5.2.1`、`5.2.3` 等 corrective release 在完成兼容性重评并更新基线常量前都属于非基线版本。

因为 Phase 0 全是只读工具，**非基线版本不会被拒**，只在响应中附 `version_warning`（符合 URS FR-03：非基线版本只读可用、写工具拒绝）。Phase 1 的写工具必须对这些版本返回 `UNSUPPORTED_BLENDER_VERSION`；每次决定采用新的 corrective release 时，都先重跑 spike/L3 与 golden 基线，再显式更新完整版本号。判定函数在 Phase 0 就位，并以 `5.2.0`、`5.2.1`、`5.2.3` 等反例测试钉死边界。

---

## 5. 错误处理

| 层 | 情况 | 处理 |
|---|---|---|
| 传输 | 帧超限 / 解码失败 | **断开，不回错误帧** |
| 认证 | token 缺失或不匹配 | **立即断开，不回响应**，记日志 |
| 路由 | 未知 method | `UNKNOWN_METHOD` |
| 队列 | 队列满 | `BRIDGE_BUSY`，`retryable=true`（回帧，不断开） |
| 队列 | 任务已过 deadline | 丢弃，不执行、不回复 |
| 执行 | `SceneReader` 抛异常 | `SCENE_QUERY_FAILED`，含异常类型，**不含 traceback** |
| 执行 | `SnapshotLimitExceeded`（object/collection 项数或 64 MiB 文本上限） | `INTERNAL_LIMIT_EXCEEDED`，`retryable=false`；不得静默截断 |
| 执行 | `SnapshotInvalidated`（revision 或 generation marker 变化） | `SCENE_QUERY_FAILED`，含异常类型，**不含 traceback**；不得继续访问旧 bpy wrapper |
| 执行 | `reply` 回调抛出任意普通 `Exception`（包括 socket 已关闭） | 捕获并静默丢弃，只记诊断日志，不击穿 tick |
| 发现 | 无活实例 | `ok=true` + 空列表 + 引导文案 |
| 发现 | `instance_id` 不存在 | `INSTANCE_NOT_FOUND` |
| 发现 | 握手 `instance_id` 不匹配 | 视为 stale，不计入活实例 |
| 编码 | 响应帧序列化超过 16 MiB | `INTERNAL_LIMIT_EXCEEDED`（写端规则，§3.2） |
| 版本 | 握手 `envelope_version` 不一致 | `ENVELOPE_VERSION_MISMATCH`（status 中仍列出该实例，见 §4.3） |
| 版本 | 外层响应存在 exact integer `v`，但值与协议版本不一致 | `ENVELOPE_VERSION_MISMATCH`，不把合法版本不匹配降级成可重试的连接故障 |
| 协议 | 外层响应 `v` 缺失，或为 boolean/string/其他非 exact integer | `BRIDGE_UNAVAILABLE`，`retryable=true`（畸形响应，不冒充版本协商） |
| 协议 | 外层响应 `id` 与请求不一致 | `BRIDGE_UNAVAILABLE`，`retryable=true`（连接/桥接异常路径） |
| 协议 | `ok/result/error/retryable` 缺失或类型畸形 | `BRIDGE_UNAVAILABLE`，`retryable=true`；不得让 SDK/Python 做宽松转换 |
| 连接 | 连不上 / ECONNRESET / EPIPE | `BRIDGE_UNAVAILABLE`，`retryable=true` |
| 超时 | 请求超时 | `BRIDGE_TIMEOUT`，`retryable=true` |
| 审计 | 日志初始化、锁获取、写入或 flush 失败 | `AUDIT_UNAVAILABLE`，`retryable=true`，**fail-closed；可覆盖已产生的业务成功/失败结果** |
| 版本 | 非基线 Blender | **Phase 0：只读放行 + `version_warning`** |
| 版本 | 非基线 Blender + 写工具 | `UNSUPPORTED_BLENDER_VERSION`（错误码在 Phase 0 定义并单测，**运行时不触发**——本阶段无写工具） |

**认证失败为何不回响应**：回「token 错误」等于向扫描者确认「此 socket 存在且协议正确」。直接断开，让盲扫拿不到区分信息。这与 §2.3 承认的 token 局限配套——既然 token 挡不住能读文件的进程，至少不要主动帮它确认目标。

**traceback 不进错误响应**，只进本地诊断日志——异常文本可能携带文件路径。

### 5.1 Blender 崩溃后的残留

崩溃不执行 `unregister`，socket 与 `session.json` 会留在磁盘。清理责任在 Server 的 discovery——那是唯一能观察到「进程已不在」的位置。

**Server 只清理同时满足两个条件的会话**：预筛判定进程不存在，且连接失败。两条同时成立才进入 cleanup，随后仍须满足 §4.3 的 identity、类型、权限与共享 deadline 判据；任一不符都保留会话证据，避免误删暂时繁忙实例或换入对象。

**`session.json` 缺失或损坏的目录**是双条件判据的盲区（无 pid 可预筛、无 socket_path 可连）。仅当会话目录 mtime 距今超过 60 秒才允许清理；若默认 socket 路径过长，还须按 §4.1 从目录名推导 deterministic fallback，并要求回退目录同样超过 60 秒、当前 uid、0700。这样 session 发布前崩溃也能回收，正常启动窗口内绝不清理。无法验证或存在未知子项时保留，而不是为追求“零残留”递归删除。

每次 `unlink`/`rmdir` 等破坏 syscall 前都必须重新检查目标类型、uid、mode 与记录的 dev/inode；检查前换入的目标必须保留。该机制不宣称 POSIX 原子 compare-and-unlink/rmdir（不存在可移植接口），所以最后一次检查后同 UID 主动换入的竞态仍在威胁模型边界内；runtime `0700` 排除其他 UID，不排除同 UID 进程。

### 5.2 日志分流

| 类型 | 去向 | 内容 |
|---|---|---|
| 审计（URS FR-33） | `logs/server-YYYY-MM-DD.jsonl` | `ts` / `request_id` / `tool` / `instance_id` / `transaction_id` / `params_digest` / `ok` / `duration_ms` / `paths` / `error`；`request_id` 来自入站 JSON-RPC request 的 `id`，保留 string/integer 原类型，不得另行生成或 `str()` 化 |
| Server 诊断 | Server 进程 stderr | traceback、连接细节、时序 |
| Bridge 诊断 | Python `logging` → Blender 进程 stderr（终端启动 Blender 时可见） | 认证失败、tick 护栏捕获的异常、清理步骤失败 |

参数记摘要不记原文（URS NFR-O3）。`paths` 与 `transaction_id` 在 Phase 0 分别恒为空数组与 `null`——两个占位字段策略一致：FR-33 要求的 schema 现在就位，Phase 1 才有内容。

日志目录初始化采用 race-safe create-or-validate，多个线程/进程首次同时启动时不得因 `exists() → mkdir()` TOCTOU 抛 `FileExistsError`。单进程内 mutex 覆盖一整条 JSONL record；跨进程对 `O_APPEND` fd 持 `flock(LOCK_EX)`，锁覆盖同 fd 身份/权限验证、整行 UTF-8 写入及 flush/close，关闭 fd 释放锁。不得假设 `TextIOWrapper` 或 `O_APPEND` 会自动把一次逻辑 record 合并为单个 `write(2)`。既存日志路径必须经 §2.2 的 no-follow/nonblocking 检查，FIFO/device/symlink 不得阻塞或被写入。

工具业务 core 预算与审计预算分离：`get_blender_status` / `describe_capabilities` 的业务 deadline 为入口 + 3 s，`get_scene_summary` 为入口 + 15 s；无论业务成功、结构化失败还是参数拒绝，随后都只创建一次独立的 audit postlude absolute deadline（`now + AUDIT_LOCK_TIMEOUT`，且 `AUDIT_LOCK_TIMEOUT ≤ 1 s`）。审计不得偷用新的业务窗口，业务也不得消耗 postlude 配额；审计初始化、锁、写入、flush、close 任一步失败，或 write/flush/close 完成后才发现已越过 deadline，都 fail-closed 为 `AUDIT_UNAVAILABLE`，即使这会覆盖已经计算出的业务结果。L2 必须分别用 numeric 与 string id 断言日志保留入站 JSON-RPC id 的值和类型。

**Bridge 侧无独立审计文件**：审计责任在 Server 侧（每次工具调用一条）；Bridge 只做诊断日志。「无 token 连接被拒并记日志」这条验收中的「记日志」落在 Bridge 诊断日志，L2 通过向 FakeBridge 注入 logger 断言。

**stdout 全程只有 JSON-RPC**（URS NFR-O1），由 L2 测试强制：跑完整 stdio 会话，断言 stdout 每一行都能解析为合法 JSON-RPC。

验证器在目标响应后不能立即结束并丢弃管道：必须继续执行有界 tail-drain，直到 EOF 或 quiet timeout settle；目标响应后的延迟非目标事件、半行与洪泛仍计入污染判据。单行 16 MiB、未成行累计 32 MiB、事件 1024 条/4 MiB 等上限在 drain 阶段同样生效，超限 fail-closed。

### 5.3 冷启动预算

URS NFR-P2 要求 < 5 s，Codex `startup_timeout_sec` 默认 10 s。风险在 import 阶段。措施：重模块延迟导入；discovery 扫描**不在 import 期执行**；加一条启动耗时回归断言。

---

## 6. 工具 Schema

下列 JSON 是**展开 `$ref`、移除 `title` 等非约束注解后的规范语义视图**，便于审阅 required、enum/const、nullable 与 object closure。运行时 `tools/list` 保留 SDK v2 / Pydantic 生成的原始 `$defs` / `$ref` 表示；L2 另对该原始表示与冻结期望值做逐字段全等断言，二者不得混为“只验证大致形状”。

### 6.1 `get_blender_status`

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "instance_selector": { "type": ["string", "null"], "default": null }
    },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "required": ["ok", "guidance", "partial", "skipped_count", "instances"],
    "properties": {
      "ok": { "type": "boolean" },
      "guidance": { "type": ["string", "null"] },
      "partial": { "type": "boolean" },
      "skipped_count": { "type": "integer" },
      "instances": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["instance_id", "pid", "mode", "bridge_state",
                       "blender_version", "blender_supported", "version_warning",
                       "scene_path", "scene_revision"],
          "properties": {
            "instance_id": { "type": "string" },
            "pid": { "type": "integer" },
            "mode": { "type": "string", "const": "gui" },
            "bridge_state": { "type": "string",
                              "enum": ["connected", "disconnected", "busy"] },
            "blender_version": { "type": "string" },
            "blender_supported": { "type": "boolean" },
            "version_warning": { "type": ["string", "null"] },
            "scene_path": { "type": ["string", "null"] },
            "scene_revision": { "type": ["integer", "null"] }
          },
          "additionalProperties": false
        }
      }
    },
    "additionalProperties": false
  }
}
```

`mode` 在 Phase 0 是固定值 `"gui"`（schema 使用 `const`）——Headless Worker 属于 Phase 2，届时再将契约显式扩为 `"gui" | "headless"`。

无活实例时：`ok=true`，`instances=[]`，`guidance` 填引导文案。`partial` 与 `skipped_count` 是本轮发现扫描的顶层元数据；前者为 true 时，后者是未处理项数的精确值或保守下界。当前工具契约不暴露内部诊断用的 `ScanStats.reasons`。

### 6.2 `get_scene_summary`

```json
{
  "inputSchema": {
    "type": "object",
    "required": ["instance_id"],
    "properties": {
      "instance_id": { "type": "string" },
      "include_collections": { "type": "boolean", "default": true },
      "include_managed_objects": { "type": "boolean", "default": true }
    },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "required": ["instance_id", "scene_name", "scene_revision", "scene_hash",
                 "scene_path", "version_warning", "units", "summary"],
    "properties": {
      "instance_id": { "type": "string" },
      "scene_name": { "type": "string" },
      "scene_revision": { "type": "integer" },
      "scene_hash": { "type": "string" },
      "scene_path": { "type": ["string", "null"] },
      "version_warning": { "type": ["string", "null"] },
      "units": {
        "type": "object",
        "required": ["system", "scale_length"],
        "properties": {
          "system": { "type": "string", "enum": ["NONE", "METRIC", "IMPERIAL"] },
          "scale_length": { "type": "number" }
        },
        "additionalProperties": false
      },
      "summary": {
        "type": "object",
        "required": ["object_count", "mesh_count", "camera_count", "light_count",
                     "collections", "managed_objects"],
        "properties": {
          "object_count": { "type": "integer" },
          "mesh_count": { "type": "integer" },
          "camera_count": { "type": "integer" },
          "light_count": { "type": "integer" },
          "collections": { "type": "array", "items": { "type": "string" } },
          "managed_objects": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["stable_id", "name", "type"],
              "properties": {
                "stable_id": { "type": "string" },
                "name": { "type": "string" },
                "type": { "type": "string" }
              },
              "additionalProperties": false
            }
          }
        },
        "additionalProperties": false
      }
    },
    "additionalProperties": false
  }
}
```

URS 原 schema 含 `include_objects` / `include_materials`。Phase 0 不返回逐对象清单，也不返回材质，这两个开关无对应输出，故移除；`include_managed_objects` 保留（Phase 1 起有内容）。

### 6.3 `describe_capabilities`

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "include_instances": { "type": "boolean", "default": false }
    },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "required": ["server_version", "envelope_version", "phase",
                 "supported_tools", "baseline_blender", "ir_schema_version",
                 "supported_operation_kinds", "connected_instances",
                 "instances_partial", "instances_skipped_count"],
    "properties": {
      "server_version": { "type": "string" },
      "envelope_version": { "type": "integer" },
      "phase": { "type": "string", "const": "phase0" },
      "supported_tools": { "type": "array", "items": { "type": "string" } },
      "baseline_blender": {
        "type": "object",
        "required": ["version", "platform"],
        "properties": {
          "version": { "type": "string" },
          "platform": { "type": "string" }
        },
        "additionalProperties": false
      },
      "ir_schema_version": { "type": ["string", "null"] },
      "supported_operation_kinds": { "type": "array", "items": { "type": "string" } },
      "connected_instances": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["instance_id", "blender_version", "bridge_version"],
          "properties": {
            "instance_id": { "type": "string" },
            "blender_version": { "type": "string" },
            "bridge_version": { "type": "string" }
          },
          "additionalProperties": false
        }
      },
      "instances_partial": { "type": "boolean" },
      "instances_skipped_count": { "type": "integer" }
    },
    "additionalProperties": false
  }
}
```

Phase 0 的 `ir_schema_version` 为 `null`，`supported_operation_kinds` 为 `[]`。这是诚实的——本阶段确实没有 IR，返回一个假版本号会误导调用方。`include_instances=false` 时不扫描，`connected_instances=[]`、`instances_partial=false`、`instances_skipped_count=0`；开启扫描时后二者与同一次 `instances_with_stats()` 快照原子配对，不能读取另一轮 `last_scan`。

**schema 落地方式（复审 F-03 最终修订）**：每个工具返回 `pydantic.BaseModel`，公共基类设置 `ConfigDict(extra="forbid")`，固定值用 `Literal`；SDK v2 由这些模型生成 `outputSchema`、在返回时执行模型验证并填充 `structuredContent`。所有顶层与嵌套 object 都必须封闭。`inputSchema` 在注册后声明 `additionalProperties: false`；同时使用 SDK v2 `ServerMiddleware`，在 SDK 参数绑定前读取原始 `tools/call.arguments`，发现未知字段即返回 JSON-RPC `INVALID_PARAMS (-32602)`。该检查位于协议版本无关的 `tools/call` 入口，因此 `2025-06-18`、`2025-11-25` 与 `2026-07-28` 客户端都由服务端强制拒绝未知参数，不依赖客户端自律。

L2 必须对 `tools/list` 返回的三组 `inputSchema` / `outputSchema` 与 SDK v2 冻结期望值做**全等断言**，而不只抽查 `outputSchema != null` 或顶层 closure；可将包含原始 input/output schema 的 canonical JSON SHA-256 固定为 golden（失败时打印完整 payload），任一字段变化都必须失败。同时覆盖合法调用、未知参数拒绝、`structuredContent` 非空，以及实际结果对对应 Pydantic 模型的运行时验证。Pydantic 生成的 `$defs`/`$ref` 也是冻结契约的一部分，升级 SDK 时若有变化必须显式评审。

`baseline_blender` 来自 `server/core/capabilities.py` 中的**配置常量**（形如 `{"version": "5.2.0", "platform": "macos-arm64"}`），不是运行时探测。它回答的是「本 Server 以哪个版本为基线」，与当前连着什么无关。`versions.py` 的门禁判定读同一常量，保证判定依据与对外声明一致。`connected_instances` 才是运行时信息，且在无实例时为空数组。

---

### 6.4 Server `instructions`（URS FR-34，2026-08-06 增补）

MCP Server 的协议发现元数据必须携带 `instructions`（Codex 消费该字段已核实）：在 2025-era 路径（当前 Codex 的 `2025-06-18` 与 raw legacy `2025-11-25`）中位于 `initialize` 响应，在 `2026-07-28` 路径中位于 `server/discover` 结果。Phase 0 文案，关键规则前置：

> Blender 只读控制通道（Phase 0）。调用任何工具前先 `get_blender_status`；若无实例，引导用户在 Blender 3D 视口按 N → 「Codex」页签 → 点击「允许 Codex 连接」。本 Server 无写工具，不要尝试让 Blender 执行代码。`describe_capabilities` 可在 Blender 离线时回答。

实现：`MCPServer(name, version=SERVER_VERSION, instructions=...)`。L2 分别验证：legacy 客户端的 `initialize` 响应携带该文案与 `serverInfo.version=0.1.0`；2026-07-28 客户端走 `server/discover`，不得产生 `initialize` fallback，并通过 SDK `Client.server_info` 读取同一版本、通过发现结果读取同一 Server instructions。该文案与 `GUIDANCE` 常量口径一致——两处都指向同一个 N 面板操作路径。

### 6.5 确定性 catalog 与双内容 result payload 基线

MCP `2026-07-28` Tools 规范要求工具集合不变时 `tools/list` 使用确定顺序，并明确指出这有助客户端缓存与 LLM prompt cache。本阶段三工具是静态公开面：同一 Server 版本与 capability profile 下，重复请求及 fresh Server 的 ordered catalog 必须逐字段一致；实例连接状态只能出现在工具结果中，不能改变公开工具集合或顺序。

Task 17 固定并复算：完整 ordered catalog canonical JSON、三工具 input/output schema canonical 总字节、Server `instructions` UTF-8 字节及各自 SHA-256；in-process 重复 list 与 fresh stdio Server 均须匹配冻结值。Task 18 在正式 60-call artifact 中再次保存同一 catalog/schema/instructions preimage并绑定 Task 17 冻结值，对每个调用同时保留 validated `structuredContent` canonical preimage 与 SDK 兼容 TextContent 原文；外部验证器必须证明两者 JSON 语义全等，再分别复算 bytes/SHA、合计双内容 result payload 与 duplication ratio。

这些量是**SDK/transport result 字节基线，不是 model-visible 或 Token 合同**。MCP 不规定目标 Codex Host 是否把两份内容都注入模型；本阶段不引入 tokenizer 依赖，不以固定“工具数/操作数/Token 降幅”作为门槛。任何后续模型上下文优化必须在同 Host/模型/推理配置、同 Blender/fixture/任务集下做 A/B，并同时报告正确率、往返次数与 wall time。

## 7. 测试策略

### 7.1 L1 单元测试（无 Blender；discovery 可用临时目录与本机 UDS fixture）

| 模块 | 覆盖点 |
|---|---|
| `framing` | 粘包、部分读、超限拒绝、长度头畸形 |
| `envelope` | 序列化往返；UTF-8 文本、深层嵌套 JSON、收发双向非有限 JSON number 拒绝、同批首帧拒绝后的尾随帧不派发；缺省 `v` 兼容、`v=true` 拒绝、未知请求外层字段忽略；响应 `v/id/ok/result/error/retryable` 精确类型与 malformed 映射 |
| `session` | token 生成熵、常数时间比较、会话状态机 |
| `router` | 分发、未知 method |
| `queue` | cooperative continuation、每 step/deadline 检查、批量处理、queued + active 容量、队列满、并发提交线程安全 |
| `lifecycle` | 非阻塞/合并 wake、loop-boundary stop recheck、transport close 后第二次 1 s join、停止幂等与失败重试、真实 timer/`depsgraph_update_post`/`load_pre` 回调及注册后的 `load_pre` generation 行为、失败步骤不中断后续；64 连接 / 32 MiB 全局入站 / 64 KiB 请求 / 32 MiB 单连接与 64 MiB 全局出站上限、fd reuse、accept/close ownership；应用目录权限 fail-closed、foreign uid 拒绝、边界上方祖先权限不变、会话叶目录 exclusive、bind→chmod→listen→thread→publish、确定性 fallback、transport 未关闭时路径保留及 socket/session/session-dir/fallback-dir replacement 保留 |
| `path_policy` | `..`、符号链接、`~` 展开越界、NUL/不可解析路径、扩展名白名单 |
| `versions` | 完整版本号门禁矩阵：仅 `5.2.0` supported；`5.2.1` / `5.2.3` 只读放行并 warning、未来写工具拒绝 |
| `discovery` / `status` | `tmp_path` 造假会话目录与 stale 判定；慢枚举/FIFO/symlink/父目录换入；foreign uid run 拒绝；目录名与 instance ID 不一致；socket identity 缺失/部分字段；partial cleanup/deadline 及预算耗尽后的后续扫描重试；discovery lock deadline；instances 与 ScanStats 原子配对；session 发布前/后 fallback 崩溃回收、identity replacement 与 cursor/run 换入；status 单一绝对 deadline、响应 instance ID 目标绑定、共享固定 8-worker pool + aggregation lock；256 项 cursor 与第 17 候选公平推进；cache invalidate 与停止→重启恢复 |
| `audit` | JSONL 格式、入站 JSON-RPC numeric/string id 原样配对、参数脱敏、独立 ≤1 s postlude 与 write/flush/close 后 deadline 检查及 `AUDIT_UNAVAILABLE` fail-closed；应用目录/既存文件权限、foreign uid、FIFO `<0.5 s`、真实 device FD 换入与 symlink fail-closed；多线程/多进程首次初始化无竞态；强制 split-write 下线程/进程行不交错 |
| `smoke/e2e` | NFR 165/180 s 与 recovery 120/135 s 两层 absolute deadline；public recovery OS supervisor + hidden worker；fresh marker-bound `0700` registry、pre-spawn reservation + stdlib bootstrap、parent-owned failure cleanup、read-only observer、8-record cache 与 deadline-bound 全 entry 扫描/overflow、5 s public registry reserve、leader-exit group liveness（仅 `killpg(pgid, 0)` 的 `ESRCH` 表示清洁）与 TERM→KILL→reap；ready PID 绑定及 kill 前/后/重启后三次 MCP identity 全等；有界 tracked-source provenance、四文档 exact approved tuple/source blob；ordered catalog/instructions 与 60 个 bounded structured/TextContent preimage 的模型/语义/canonical digest 外部复算；逐行 audit 与 0600/size-capped artifact |

逻辑预算与 deadline 单测由 `FakeClock` 驱动，不使用真实 sleep；另设独立 RealClock wall-clock 反例测量大场景 continuation，二者不得混称。

L1 还必须有反例：大场景响应在多个 tick 间推进且最大 tick 受测量上限约束；`ok_frame_steps` 增量编码在 16 MiB 前失败；continuation 不会把容量从 64 扩到 65；generation 变化使 snapshot 结构化失效；`include_collections=false` 不调用 collection 源；wake storm 不阻塞 producer；既存 `session.json.tmp` 碰撞被保留；fallback cleanup 预算耗尽后保留证据并可重试。

### 7.2 L2 契约测试（真 UDS，Fake Blender）

进程内起 FakeBridge：**真实的 `bridge/core/`** + `FakeSceneReader` + 测试专用 driver（线程驱动 tick，不碰 `bpy.app.timers`）。除分层契约测试外，至少一条子进程级用例必须走完**真实 stdio → MCP adapter → Server core → UDS → FakeBridge**，分别通过 MCP 工具调用读取 status 与 scene summary；只验证 adapter/core 和 core/UDS 两个分段不算完整链路。

协议与宿主兼容测试必须冻结三条彼此独立的精确合同：

1. raw legacy stdio `initialize` 请求精确协商为 `2025-11-25`；
2. modern SDK Client 通过 `server/discover` 精确协商为 `2026-07-28`，并断言 `discover_result` 非空、`initialize_result` 为空；
3. Codex 0.147 app-server 的默认模式与显式启用 `mcp_2026_07_28` feature flag 的模式，均精确协商为 `2025-06-18`。

前两条任一路径静默降级到另一版本即失败，禁止用“请求版本/旧版本/新版本任一皆可”的宽松断言。第三条以宿主实际协商结果为准：**feature flag 被设置不等于已经走 2026-07-28 wire**，测试必须读取并断言协商版本，不能把启动参数或 flag 名称当作证据。Codex 后续若真正切换协议，应由该精确断言先失败，再经兼容性评审更新基线。

覆盖：完整往返 · token 拒绝后断开（含诊断日志断言） · 5 MiB 载荷 · 16 MiB 拒绝 · 并发请求 · Bridge 中途断开 · 超时 · self-pipe 确定性关闭 · socket 与目录权限位断言 · stdio 会话 stdout 纯净性 · 冷启动计时 · **legacy initialize 与 modern discover 均含非空 `instructions`（§6.4）** · **单连接流水线下 BUSY 与正常响应帧不交错（§3.7 单写者的直接验证）** · **不读响应的客户端触发 outbox 上限断开且 tick 不受阻**。

审计新增的必测项：

- **关闭时活跃连接被回收**：建立 N 条连接后 `unregister()`，断言全部 fd 已关闭、客户端立即收到关闭而非超时，并证明首次 join 超时后 transport close 会触发第二次 ≤1 s join 使 I/O 线程退出（§3.7 第 4–5 步）
- **半帧不楔死 I/O 线程**：一条连接只发 4 字节长度头后静默，断言其余连接的请求仍被正常服务，且关闭仍在 2 s 内完成（§3.7 规则 1）
- **并发写不交错**：一条连接上流水线提交使 BUSY 与正常响应同时在途，断言客户端收到的每一帧长度前缀完好（§3.7 规则 3 单写者）
- **队列满回 `BRIDGE_BUSY` 而非断开**：塞满 64 个任务后再提交，断言收到错误帧且连接仍可用
- **过期任务被丢弃**：提交一个 deadline 已过的任务，断言 `SceneReader` 未被调用
- **`reply` 失败不中断 tick**：客户端在响应前断开，断言后续排队任务仍被正常处理
- **tick 护栏兜底**：注入在信封序列化阶段抛异常的响应，断言 tick 返回间隔而非抛出、后续任务不受影响（§3.6 护栏）
- **非基线版本附警告**：FakeBridge 上报 `4.5.3`，断言 `get_scene_summary` 响应中 `version_warning` 非 null（§4.4 的运行时行为，仅测判定函数不够）
- **信封版本不匹配**：FakeBridge 上报 `envelope_version: 2`，断言实例在 status 中列出且 `scene_summary` 返回 `ENVELOPE_VERSION_MISMATCH`
- **外层 envelope mismatch**：伪造响应 `v` 不匹配时返回 `ENVELOPE_VERSION_MISMATCH`；伪造响应 `id` 不匹配时走 retryable `BRIDGE_UNAVAILABLE`，两条 wire path 都覆盖
- **malformed wire exact types**：`v=true`、非布尔 `ok/retryable`、非 object `result/error` 均拒绝；除 `v` mismatch 外统一 retryable `BRIDGE_UNAVAILABLE`
- **UTF-8 / 深层 JSON / 同批尾随帧**：非法 UTF-8、超过深度上限的 request/response 不得逸出异常；同一次 recv 中首帧被拒并关闭连接后，后续完整帧不得进入 router/queue
- **schema、catalog 与参数边界**：三工具 schema 与冻结期望值全等，所有 object 封闭；同会话重复 list 与 fresh stdio Server 的名称/顺序/完整定义、ordered catalog/schema/instructions bytes+SHA 全等；raw 2025-11-25 与 SDK 2026-07-28 两条 Server wire path都验证合法调用的 `structuredContent`、兼容 TextContent JSON 等价、结果模型校验与未知参数 `-32602`；Codex 2025-06-18 宿主合同另验证工具目录/调用可用及精确协商版本
- **审计 postlude**：三工具成功/失败/未知参数都只写一条日志，`request_id` 精确对应入站 JSON-RPC id；postlude 获得独立且 ≤1 s 的 absolute deadline，初始化/锁/写入失败均返回 retryable `AUDIT_UNAVAILABLE`，允许覆盖业务结果
- **聚合与快照并发**：并发 status 调用仍只使用共享 8-worker pool 且聚合区互斥；锁等待、submit 与 as_completed 共用业务 deadline。并发扫描下，status / scene summary / capabilities 的实例结果与 ScanStats 必须来自同一原子快照
- **发现缓存恢复**：同一 Discovery 先发现实例、模拟 Bridge 停止并触发 `invalidate()`、再重启实例，断言后续 MCP 调用重新发现而非持续命中 stale cache
- **发现锁、失效与游标换入**：持有 discovery lock 时，带 absolute deadline 的调用在锁上超时并返回 partial；`invalidate()` 不等待该锁、重复通知有界合并，扫描中通知不得发布旧 cache；第一次扫描保留 cursor 后替换 run 目录，下一次扫描必须关闭仍属本进程的旧 cursor、清空 backlog、标记 `run cursor replaced`，不得读取旧目录。closed/different-identity fd 数字复用及析构/deadline cleanup 不得误关外部 fd
- **socket identity 完整性**：四个 socket/父目录 dev-inode 字段缺失或只提供部分时，在连接前隔离并保留 session 证据，不得调用 BridgeClient
- **权限与首次并发**：runtime/run/logs 宽权限、symlink、FIFO/device 审计目标均 fail-closed 且不被 chmod/写入；边界外祖先不改。线程/多进程从目录不存在开始同时构造日志器并写入，仍无异常且每行完整
- **fallback 崩溃恢复**：强制长路径后分别在 `session.json` 发布前/后模拟崩溃，外置 socket/空目录最终回收；替换 fallback/session 目录后 cleanup 保留替换物与 session 诊断元数据
- **证据脚本边界**：Codex app-server verifier 与 stdout harness 均显式将 stdout fd 设为 non-blocking，并使用 selector + `os.read`；单行上限 16 MiB。verifier 的未成行缓冲上限 32 MiB、非目标事件上限 1024 条/4 MiB；stdout harness 的未成行缓冲上限 32 MiB、解析后 backlog 上限 32 MiB、消息上限 1024 条且诊断只保留截断尾部；半行、无换行洪泛和写入阻塞均在各自 absolute deadline/size cap 内失败
- **目标响应后的 tail-drain**：目标响应后注入延迟非目标事件与 EOF/quiet timeout，断言 verifier 不提前成功且在有界 drain 内给出污染/settle 结论。
- **双层 scene-summary admission**：Bridge 以 queued + active continuation=2、Server middleware 以完整 `call_next`/conversion/audit=2；三请求 wire 反例必须让第三个在 reader 未进入时得到 `BRIDGE_BUSY`，前两项转换结束后槽位可复用，异常路径同样释放。
- **Reader 工作集上限**：object/collection 各自 1,000,000 项与 64 MiB 文本上限；超限映射 `INTERNAL_LIMIT_EXCEEDED`，`include_* = false` 源端短路。

**continuation/lifecycle 必测回归**：

- 12.59 MiB scene response 至少跨多个 tick；记录最大 tick 与总耗时，不能只断言最终成功
- `include_collections=false` 在 2.2M collections fixture 上不枚举 collections，且 response 不触发 16 MiB
- snapshot generator 跨 yield 的 locals 不含 bpy wrapper；触发 `load_pre`/generation 变化后返回 `SCENE_QUERY_FAILED`
- continuation active 时并发 submit 仍遵守 64 容量；wake socket 两端非阻塞且 1000 次通知合并为有限写入
- driver 注册失败时只回滚本次新增 hooks；正常 stop 通过真实 callbacks 完成 §3.7 1–10 顺序

**Server 的 runtime 根注入**：`server/core` 从环境变量 `BLENDERCODEX_ROOT` 读取根目录（默认 `~/Library/Application Support/BlenderCodex`），`run/` 与 `logs/` 由此派生。这是 stdout 纯净性与冷启动计时两条子进程级测试的前提——没有注入点，它们只能污染真实用户目录。

### 7.3 L3 冒烟与正式真机门（真 GUI Blender）

基础 GUI smoke 覆盖 L1/L2 在原理上无法证明的五件事：

1. `bpy.app.timers` 真的在主线程驱动 tick
2. `depsgraph_update_post` 真的递增 `scene_revision`
3. `SceneReader` 从真实场景读出的字段正确
4. **structure hash v1 盲区的真实证明（`hash_scope`）**：移动一个顶点后 `scene_hash` **不变**，移动整个对象后 `scene_hash` **改变**——两条一起才证明「v1 覆盖 transform、不覆盖顶点」。该字段必须进入 runner 与外部验证器的成功判据；仅打印或 grep 到字段名不算通过
5. **完整会话循环** 20 次无线程泄漏、无残留 socket。**循环定义：enable → 调用「允许连接」operator → 建连验证 → 调用「断开」operator → disable。** 在 P0-D1 下 enable 本身不建 socket 不起线程，只循环 enable/disable 会空转通过、什么也没测——被测对象是 `Session.start`/`stop`，循环必须包含它们。由 runner 脚本直接调用 operator（`bpy.ops`）驱动，泄漏断言用 `threading.enumerate()` 计数与会话目录残留检查

执行方式：`blender --python smoke/runner.py`（GUI，**不是** `--background`）。线程 baseline 必须在首次 register/允许连接之前记录，避免把既有线程误当作 Bridge 泄漏或反向漏计。runner 写出包含五个布尔字段与 `errors` 的 JSON；外部验证器重新解析该文件，要求五项**逐项为 `true`**、字段无缺失且 `errors=[]`，否则以非零退出。命令同时启用 `pipefail`，确保 Blender 自身失败不会被 `tail` 等管道尾部命令掩盖；`SMOKE_OK`/`SMOKE_FAIL` 文本只供人读，不是唯一判据。

Phase 0 关闭还必须在独立临时 root 上执行两项正式真机门，均由 `smoke/e2e.py` 生成有界 JSON artifact，且不得把本节基础 smoke 或历史 Bridge-only 数字当作替代：

6. **NFR-P1**：在同一 100k 真 GUI 会话上，由外部 MCP SDK Client 经 stdio/adapter/Discovery/UDS 调用 `get_scene_summary` 与 `get_blender_status` 各 20 次；再在保留原始 audit 的独立空 root、`include_instances=false` 下调用 `describe_capabilities` 20 次。计时、165/180 s invocation 边界、poll 前后 deadline 判定、样本与大小上限严格采用 URS §6.3；100k fixture 与其 Bridge-only 预查询发生在 helper spawn 前，不得声称服从该窗口。artifact 先固定 live/offline 完全一致且与 Task 17 freeze 全等的 ordered catalog、schema 与 instructions preimage/bytes/SHA，再保存全部 60 个 ≤256 KiB canonical validated-result preimage及兼容 TextContent 原文（跨三工具 structured preimage 合计 ≤16 MiB、artifact ≤32 MiB）；外部验证器重新执行 Pydantic/语义断言，以 exact-type 比较拒绝 Pydantic 归一化前的伪造 preimage，证明 TextContent JSON 与 `structuredContent` 等价并复算两者 bytes/SHA、合计双内容 result payload、duplication ratio、exact-type arguments、全局 byte total、nearest-rank 第 19 项、非 bool finite/non-negative max 与代表结果，同时以 shared deadline 和文件数/字节/行上限逐行核对主 root 40 行与离线 root 20 行 audit。该双内容合计不冒充 Host model-visible 字节。provenance 先证 clean Git，再以 bounded stdout 枚举至多 512 个 tracked 源，required 输入不得是 ignored/untracked；ignored vendor 必须 exact-set、无额外 executable artifact 且逐文件与 `protocol/` 同 hash；四文档 exact-type approved tuple/source blob、lock/源码 manifest 与 Blender exact build 绑定。execution manifest 是归因入口，SHA sidecar 只证明文件完整性。
7. **真 SIGKILL/restart**：public `recovery` 是 135 s OS supervisor，hidden worker 在其中使用单一 120 s work deadline并只创建一个 MCP SDK `Client`；启动真 Blender A 并成功调用后向 A 的独立 process group 发送 `SIGKILL`，同一 Client 必须得到 exact `{"code":"BRIDGE_UNAVAILABLE","retryable":true}`，再启动真 Blender B 并由同一 Client 自动发现/调用成功。两个 Blender 使用同一隔离 runtime root，ready PID 必须等于实际 `Popen.pid`。fresh `0700` registry 的所有独立 group 均由 parent 在 spawn 前创建 identity-bound `0600` reservation，并先运行纯 stdlib bootstrap，在加载 MCP/Blender 重依赖前发布绑定同一 128-bit marker、spawn 时间窗及 opened dev/inode 的完整 record；若参数构造、SDK client enter 或 `Popen` 在 record 发布前失败，parent 按 reservation dev/inode 清理。observer 只读，owner retire/publication rename 的并发 entry 消失标 pending；cache 上限 8 只约束已验证记录，formal scanner 由 shared deadline 限界。unknown/坏 entry 记首错后继续扫描，第 9 条及后续有效 overflow 全部 identity-rechecked KILL。public work 期持续预观察并从 15 s cleanup margin 固定保留 5 s 给 registry。recorded PID 已复用至不同 PGID、marker/stale/identity/record 换入均 fail-closed 且不得误 signal/unlink；unlink 紧前重验 inode。public SIGINT/SIGTERM handler 只置 flag，超时、任意窗口取消、leader-exit child 与截止点仍存活 group 均进入同一 TERM/KILL/registry cleanup；截止点 final KILL 不重开 wait 窗口。kill 前、kill 后与重启后三次观察的 MCP `(pid, pgid, marker, started_monotonic_ns)` 必须全等并由外部验证器复核，不能写死 `same_mcp_server_session=true`。

### 7.4 验收映射（URS §10.1）

下表按 URS v1.16 的稳定 ID **恰好 20 行且同序**；NFR-P1、确定性 catalog/payload 基线、G2/G3 与官方兼容通道属于补充关闭门，不得伪装成其中某一行，也不得反向把 20 行压回旧“八条”口径。

| ID | 验收项 | 自动化层 |
|---|---|---|
| P0-01 | 三工具 outputSchema/structured result | L2 schema/wire 全等 + L3 NFR 三模型验证 |
| P0-02 | 非基线只读可用、写拒绝 | L1 版本矩阵 + L2 FakeBridge warning；单栈 fixture，不冒充另装 Blender |
| P0-03 | SIGKILL 后 Server 存活、exact retryable `BRIDGE_UNAVAILABLE`、重启重连 | L2 断开回归 + §7.3 public supervisor/hidden worker、三次 MCP identity 全等及 public cancel/final-KILL、late poll、leader-exit/live-child、marker/stale/PID-PGID reuse、record 换入、pre-spawn reservation/stdlib bootstrap、read-only observer/owner race、bounded cache overflow/inflight publication 直接反例 |
| P0-04 | 完整会话 20 次无泄漏/残留 | L3；`threading.enumerate()` 精确追踪新增存活 `bcx-io` + `run/gui-*` |
| P0-05 | ≥5 MiB 分帧无截断 | L1 framing + L2 wire roundtrip |
| P0-06 | 私有 socket/token | L1/L2；bind→chmod `0600`→listen→thread→publish 的顺序反例 + auth log |
| P0-07 | stdout 仅 JSON-RPC | L2 子进程及 bounded tail-drain 全组 |
| P0-08 | 冷启动 `<5 s` | L2；进程启动至 initialize |
| P0-09 | cooperative continuation、总耗时/max tick | L1 wall-clock 回归 + L3 正式 100k artifact |
| P0-10 | yield 无 bpy wrapper；已注册 load_pre 后旧 continuation 失败 | L1/background snapshot + driver 注册后 handler 直接反例 |
| P0-11 | 2.2M collections 源端跳过 | L1 reader source-skip/item-cap + L2 frame-limit 回归 |
| P0-12 | queued+active 容量，64→65 拒绝 | L1 Bridge capacity + L2 SDK conversion admission 三请求反例 |
| P0-13 | wake 合并与 1–10 停机顺序 | L1 lifecycle hooks/final join + L2 N 连接/单写者 |
| P0-14 | file/parent/cleanup 换入不越界、不误删 | L1 lifecycle/discovery identity replacement 全组 |
| P0-15 | exact wire types、SDK coercion、结构化审计 | L1 envelope/client + L2 adapter coercion/output/audit |
| P0-16 | 线程/多 Host JSONL 完整 | L1 线程与 spawn 进程 split-write |
| P0-17 | runtime/run/logs 类型、uid、mode、祖先不改 | L1 wide/symlink/foreign-uid/真实 device FD/祖先权限直接反例 |
| P0-18 | sun_path 发布前/后崩溃恢复及换入保留 | L1 discovery fallback pre/post publish + lifecycle replacement |
| P0-19 | stale deadline、后续重试、instance ID | L1 expired/recheck/evidence preservation + 后续 scan 重试 + mismatch |
| P0-20 | 首次并发初始化；FIFO/device/symlink 不阻塞/不写 | L1 concurrent create + FIFO `<0.5 s` + `/dev/null` FD 换入 + symlink preservation |

补充关闭门固定为：G2 三条独立 wire 协议合同、G3 structure-hash 真 Blender 边界、完整 stdio→adapter→UDS→Bridge、NFR-P1 正式 artifact、G5 官方兼容通道风险接受记录。G5 当前仅因项目所有者知情接受 screenshot 顺序敏感性与 render `SIGABRT` 而关闭；26/26 目录和 24 个非-render 摘要成功不等于缺陷已修复或全目录稳定。

### 7.5 不做

不把 MCP SDK 本身作为被测对象 · 不把 bpy 行为正确性当作本项目逻辑测试（仍需真 Blender L3 证明接线与性能边界） · Phase 0 不做跨硬件排名或规范级吞吐承诺。为验证 NFR-P1 / cooperative budget，允许在固定基线机上运行有界压力 fixture、wall-clock 回归与单点计时断言；这些本机测量只能作为候选实现证据，不能外推为跨机器合同。

---

## 8. 前置 Spike —— 已执行，结果如下

**执行日期 2026-07-23，实测环境：Blender 5.2.0 LTS（build 2026-07-14，hash fbe6228777e7）/ Apple M4 / macOS 26.5.2。** 本节由「待验证问题」转为「已确认事实」，后续任务只准引用本节结论。

### 8.1 SPIKE-1 · timer 与 handler 语义

| # | 问题 | 实测结果 | 决策 |
|---|---|---|---|
| 1 | `--background` 下 timer 是否触发 | **不触发**：1 秒主线程 sleep 循环期间回调 0 次；脚本结束即退出，无事件循环 | L3 维持 GUI 半自动；`scripts/checks.sh` 只跑 L1+L2。印证 URS 既有设计（Headless Worker 独立受控 CLI，不复用 Bridge） |
| 2 | GUI 下 timer 间隔与抖动 | `return 0.05` → 中位 50.9 ms、p95 55.4 ms；`return 0.0` → 中位 5.7 ms 但 p95 47.8 ms、max 111 ms，**完全随事件循环起伏** | §3.6 只把 50 ms 作为 cooperative checking budget；这些数字是调度样本，不是 handler 墙钟合规证明。最坏排队延迟约 100 ms + 有界原子 step，对 NFR-P1（2 s）仍有余量 |
| 3 | timer 回调内 `bpy.context.scene` 可用性 | **可用**，返回活动 scene；回调确认运行于主线程（`threading.main_thread()` 判定） | §3.5 简化：**主选 `bpy.context.scene`**，`None` 时回退 `bpy.data.scenes[0]`，`scene_name` 照常回报 |
| 4 | `persistent=True` timer 跨文件重载存活（URS V-04） | 经 `read_homefile` 重载：**persistent timer 保持注册，非 persistent 被清除**。同路径实测 handler：**带 `@bpy.app.handlers.persistent` 装饰器的 depsgraph handler 存活，不带的被清除** | NFR-R6 的机制落定：timer 用 `persistent=True`，**handler 必须加 `@persistent` 装饰器**（此前 spec 未指明机制）。自愈重注册保留为防御层。注：实测走 `read_homefile` 重载路径；`open_mainfile` 同属文件加载路径，Phase 1 的 hard 回滚测试会直接覆盖 |

附带发现（Phase 2 备用）：`--background` 下 Data API 建对象 + `view_layer.update()` 会触发带 `@persistent` 的 `depsgraph_update_post`（计 1 次）——headless worker 未来若需变更计数，机制可用。

### 8.2 SPIKE-2 · Python 版本

**Blender 5.2.0 内置 Python = 3.13.13。** 决策：`protocol/` 与 `bridge/` 的语法基线定 **py313**；Server 项目声明 `requires-python = ">=3.13,<3.14"` 并由 uv 显式选择 3.13，与 Bridge 对齐。3.14 下深层 JSON/递归失败行为与 3.13 实测不同，不能让 uv 自动选取 3.14 后仍沿用 3.13 证据。依赖声明 `mcp>=2.0,<3`，由 frozen `uv.lock` 精确锁定 `mcp==2.0.0`。§9 工具链同步更新。

### 8.3 附带确认

- `bpy.data.scenes` 实测为**名称字典序**（创建顺序 Zeta→Alpha，遍历得 Alpha, Scene, Zeta）——§3.5 的排序论述由推断转为已验证。
- 钉定版本记录（URS NFR-C2 / R-01）：**Blender 5.2.0 LTS**。`5.2.1`、`5.2.3` 等 corrective release 不自动继承 supported 状态；重评通过并显式升级完整基线版本时，触发 spike/L3 重跑与 golden 基线重录（Phase 2 起生效）。

---

## 9. 工具链

| 项 | 选择 |
|---|---|
| Server 依赖管理 | `uv`，项目声明 Python `>=3.13,<3.14` 且命令显式 `--python 3.13`（与 Bridge 对齐，SPIKE-2）；项目声明 `mcp>=2.0,<3`，提交的 `uv.lock` 精确锁定 `mcp==2.0.0`（URS NFR-C3 / 决策 D-5） |
| 测试 | `pytest` + `pytest-timeout` |
| 静态检查 | `ruff`（`target-version = py313`，SPIKE-2）+ `mypy`（`core/` 开 strict） |
| 自动化门禁 | `scripts/checks.sh` 先禁写并清理项目 bytecode，再跑 L1 + L2；L3 本地执行。该脚本可接入 CI，但在实际 workflow 落地前不宣称仓库已有 CI |

`scripts/checks.sh` 的四条强制检查（未来 CI workflow 必须调用同一脚本）：

1. `bridge/core/` 内不得出现 `import bpy`
2. `bridge/_vendor/protocol/` 与 `protocol/` 内容 hash 必须一致
3. **嵌套 import 冒烟**：把 `protocol/` 复制到人造深层包（模拟 `bl_ext.repo.bridge._vendor.protocol`）下执行导入，拦截绝对导入回归（见 §3.1 约束 2——该错误在 L1/L2 下隐形）
4. `protocol/` 与 `bridge/` 的语法版本不高于 py313（SPIKE-2 实测 Blender 5.2.0 内置 Python 3.13.13；`ruff` `target-version` 钉住）

---

## 10. 对 URS 的修订建议

**存档（2026-08-06 已全部落账 URS v1.1，见 URS §13）**——本表保留为当时的决策依据，不再是待办。尤其是下表「全场景摘要」措辞已被 URS v1.2+ 的**结构摘要 v1** 取代；现行语义只认本 spec §3.5，历史建议不得再作为实现依据：

| URS 位置 | 现状 | 建议 |
|---|---|---|
| NFR-S5 | 称「同 uid 进程的越权连接由 token 阻断」 | 下调为「token 提升攻击成本并实现凭据轮换；同 uid 进程可读取会话文件，真正压缩风险的是显式会话窗口」。见 §2.3 |
| §2 术语表 | `scene_hash` 定义为「受管子集摘要」 | **当时建议（已被 v1.2+ 取代）**：改为全场景摘要，并新增 `plan_scope_hash`。现行设计将前者收窄为结构摘要 v1，后者仍只覆盖 IR 依赖集并补几何摘要。见 P0-D2 / §3.5 |
| **FR-11** | 称「冲突检测以 `scene_hash` 为权威依据」 | **仍有效的结论只有：改为以 `plan_scope_hash` 为权威依据。** 当时用「`scene_hash` 重定义为全场景」解释过度敏感，现行理由改为结构摘要覆盖不足且会受依赖集外覆盖字段影响；两头都不适合冲突判定 |
| `get_scene_summary` schema | 含 `include_objects` / `include_materials` | 移除（Phase 0 无对应输出），保留 `include_managed_objects`；新增 `scene_name`（见 §3.5） |
| §2 术语表 `scene_revision` | 格式定义为 `r{n}@{instance_boot_id}` 字符串 | 改为裸整数 + 「仅会话内有效」语义（本 spec §3.5）。跨会话只允许用 `scene_hash` 比较结构摘要 v1；本阶段不提供完整场景等价判定，因此把 boot id 拼进 revision 字符串只会增加解析面 |
| FR-32 | 要求「配 `instances.json` 注册表」 | 改为「每会话 `session.json` + `run/` 目录扫描」（本 spec §2.2/§4.3）。中心注册表是共享可变状态，多实例并发启停需要加锁协调；每会话一文件天然无锁，stale 清理语义也更简单 |
| NFR-O2 | 要求 JSONL + OpenTelemetry | OTel/`traceparent` 推迟至 Phase 1（本 spec §1.2 已声明），Phase 0 只交付 JSONL 审计 |

---

## 11. 风险与未决

| ID | 风险 | 缓解 |
|---|---|---|
| **R-P0-01** | token 存于 `0600` 文件，同 uid 进程可读取后合法连接 | 显式会话缩短暴露窗口；认证失败不回响应；彻底方案（`SCM_RIGHTS` / 系统沙箱）超出 Phase 0 |
| ~~R-P0-02~~ | ~~`--background` 下 timer 行为未确认~~ | **已关闭**：SPIKE-1.1 实测不触发，L3 维持 GUI 半自动（§8.1） |
| ~~R-P0-03~~ | ~~Blender 内置 Python 版本未知~~ | **已关闭**：SPIKE-2 实测 3.13.13，语法基线 py313（§8.2） |
| **R-P0-04** | vendoring 的两份 `protocol/` 可能漂移 | `scripts/checks.sh` 做 hash 一致性检查，不一致即门禁失败；未来 CI workflow 复用同一脚本 |
| **R-P0-05** | Blender 崩溃残留会话目录，若清理判据过松会误删活实例 | 双条件判定（预筛失败 **且** 连接失败）才清理 |
| **R-P0-06** | 显式会话模型下用户可能忘记点击授权 | `get_blender_status` 返回结构化引导文案；Phase 0 结束后据实际反馈评估是否需要更强提示 |
| **R-P0-07** | 多场景文件的 scene 选择：主选 `bpy.context.scene`（SPIKE-1.3 已实测可用）；防御回退 `scenes[0]` 按名称字典序，重命名会改变指向 | 残余风险仅在回退路径；`scene_name` 回报使任何选择对调用方可见 |
| **R-P0-08** | `scene_hash` 仍需遍历目标 scene 的全部对象；旧数值索引实现实测近 O(N²)，10k 已超 2 s。v1.9 改为 1024 项 source slice + 128 项 hash batch 后，本机 100k 共享网格约 1.2 s、最大 source step 约 22 ms，但复杂生产场景与跨硬件尚未正式验收 | L1 拒绝数值索引并检查 yield locals 无 bpy wrapper；L3/验收在真实大场景记录总耗时与最大 step。若正式执行仍超预算，Phase 1 引入增量 hash（依托 `depsgraph_update_post` 脏标记），不得退回跨 yield 保存 bpy wrapper |
| **R-P0-09** | macOS `sun_path` 104 字节上限：长用户名下默认 socket 路径超限；Bridge/Server 的 `$TMPDIR` 还可能不同 | `Session.start` 校验路径 ≤ 100 字节，超限统一回退可推导的 `/tmp/bcx-<hash>`；发布后 `session.json.socket_path` + identity 为权威，发布前由实例 ID 恢复（§4.1） |
| **R-P0-10** | `depsgraph_update_post` 在高频编辑（拖拽、雕刻）下每帧触发，handler 内任何非平凡计算都会拖慢视口 | handler 只做 `revision += 1` 一条自增，**不做 hash**；`scene_hash` 只在收到 `scene_summary` 请求时按需计算 |
| **R-P0-11** | cooperative budget 无法抢占单个 Python/bpy/native/bytes 原子 step；无界 step 仍可超出 50 ms | 每个 step 前后检查 deadline；对象、hash、collection、encoder piece 分片；合同明确 `50 ms + 有界原子 step 成本 + 调度抖动`；无界工作转 Headless Worker，并以大场景 wall-clock 回归监测 |
| **R-P0-12** | 文件重载在 continuation yield 之间释放旧 bpy 数据；仅靠 revision 可能漏掉“计数恰好相同”的新文件 | persistent `load_pre` 在释放前递增 generation；continuation 同时校验 revision + generation，失败映射 `SCENE_QUERY_FAILED`；跨 yield 只保存纯 Python 状态 |
| **R-P0-13** | 用户既存且主动放宽 `BLENDERCODEX_ROOT` 上方祖先目录；强制 chmod 会越权，完全忽略又会让应用目录/日志公开 | 权限边界精确定在 runtime root：边界外祖先不改；runtime_root/run/logs 必须为当前 uid、非 symlink、0700，否则 fail-closed；会话叶目录 exclusive 0700，日志/session/socket 0600 |
| **R-P0-14** | 空闲 timer 从 0.1 s 改为 0.02 s 可降低首个请求等待，但本机实测唤醒/回调 CPU 约增 4.4×；电池和深度 idle 影响未测 | 项目所有者已于 2026-08-08 正式接受为 macOS 基线实现；仍不写电量承诺。Phase 0 执行记录真实工作负载，若电池影响不可接受，再设计并单独证明无锁迟滞，禁止复用已死锁的嵌套取锁方案 |

---

## 12. 实现顺序建议

1. SPIKE-1、SPIKE-2
2. `protocol/`（framing + envelope）+ L1 测试
3. `bridge/core/`（session / router / queue / lifecycle）+ L1 测试
4. `server/core/`（discovery / bridge_client / path_policy / audit / versions）+ L1 测试
5. L2 契约测试骨架 + FakeBridge
6. `bridge/blender/`（scene_reader / driver / panel）+ 扩展打包
7. `server/mcp/adapter.py`
8. L3 冒烟测试
9. `codex mcp add` 安装文档

第 2–5 步完全不需要 Blender，可在没有 GUI 环境的条件下推进。
