# Phase 0：只读端到端链路 · 设计规格

| 项 | 值 |
|---|---|
| 日期 | 2026-07-23 |
| 状态 | 待评审 |
| 上游需求 | `Blender-Codex-需求规格说明书-v1.md`（URS v1.1；v1.1 已落账本 spec §10 的全部挂账修订，并新增 FR-34 server instructions——本 spec §6.4 为其 Phase 0 落点） |
| 覆盖子系统 | S1 传输与 Bridge 骨架 · S2 MCP Server 骨架 · S4 标识与一致性（读取部分） |

---

## 1. 范围

### 1.1 本 spec 交付

Codex → MCP Server（stdio）→ UDS → Bridge Add-on → Blender 主线程 → 结构化返回，这条链路端到端成立，且满足 URS §10.1 的八条验收标准。

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
| **P0-D2** | **双 hash 分层**：`scene_hash` 覆盖全场景（本阶段交付）；`plan_scope_hash` 只覆盖 IR 依赖集（Phase 1 交付，作为冲突判定的唯一依据） |
| **P0-D3** | **内核/适配分层**：`bridge/core/` 与 `server/core/` 零外部依赖，bpy 与 MCP SDK 各自隔离在薄适配层 |
| **P0-D4** | **`protocol/` 用 vendoring 而非 wheel**，配 CI hash 一致性检查 |
| **P0-D5** | **实例存活以握手 `instance_id` 比对为权威判定**，`os.kill(pid, 0)` 仅作预筛 |

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
  │   → 生成 token → session.json (0600)   │
  │   → bind socket → I/O 线程          │
  │   → register timer + depsgraph handler │
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
  "started_at": "2026-07-23T10:00:00Z"
}
```

`instance_id` = `gui-<pid>-<secrets.token_hex(4)>`。

后缀**不能用时间戳**：同一 Blender 进程反复点击「断开 → 允许连接」时，PID 不变，秒级时间戳也可能相同，两个会话会产生同名 `instance_id` 并冲突到同一目录。用随机后缀彻底消除这个碰撞。

后缀的作用是**保证 `instance_id` 唯一**，不是判定存活——存活判定见 §4.3（P0-D5），由握手比对负责，与 PID 复用无关。

**权限的达成机制必须显式，不得依赖 umask**（URS NFR-S4 禁改进程级 umask；Blender 是共享进程，改全局 umask 会影响用户自己的文件保存）：

| 对象 | 机制 |
|---|---|
| `BlenderCodex/`、`run/`、会话目录 | **逐级**显式创建并各自 `chmod 0700`——`os.makedirs` 的 `mode` 参数不作用于中间层目录，一次 makedirs 会让父目录落在默认 umask 下（0755） |
| `session.json` | 临时文件用 `os.open(path, O_WRONLY \| O_CREAT \| O_EXCL, 0o600)` 创建后写入，再 `os.replace`（replace 保留源文件权限） |
| `bridge.sock` | `bind()` 创建的 socket 文件权限是 `0777 & ~umask`（默认 0755），**bind 后必须立即 `os.chmod(sock_path, 0o600)`**。chmod 前的短暂窗口无害——socket 位于 `0700` 目录内，其他用户根本走不到它。**这正是 0700 目录设计的收益：让 bind-then-chmod 的竞态不可利用，而不是「不需要 chmod」** |
| `logs/` 与日志文件 | 目录 0700，文件以 `O_CREAT` mode `0o600` 打开 |

`session.json` 通过**临时文件 + `os.replace`** 写入，保证 Server 不会读到半截内容。

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
    adapter.py               FastMCP 注册三个工具（≤300 行，URS NFR-C3）

tests/
  unit/                      L1
  contract/                  L2
smoke/                       L3（真 GUI Blender）
```

**`protocol/` 用 vendoring（P0-D4）。** URS NFR-S8 禁止 Bridge 运行时装包；wheel 声明虽可行，但会让扩展打包与版本发布耦合。vendoring 保持 Bridge 零依赖，代价是一条 CI 检查：`bridge/_vendor/protocol/` 与 `protocol/` 的内容 hash 必须一致，否则构建失败。

**扩展命名空间对 import 的两条硬约束**（Blender 扩展在运行时以 `bl_ext.<repo>.<ext_id>` 命名空间加载）：

1. **扩展根目录必须有 `__init__.py` 且在其中暴露 `register`/`unregister`**——Blender 只调用扩展根包的入口，不会去子包里找。根 `__init__.py` 是纯转发 shim（`from .blender import register, unregister`），本身不含 bpy 逻辑，分层论述不变：bpy 逻辑仍只存在于 `blender/`。
2. **`protocol/` 包内部只允许相对导入**（framing / envelope 互引用一律 `from . import ...`）。原因是组合约束：vendored 副本运行在 `bl_ext.<repo>.bridge._vendor.protocol` 深层命名空间下，绝对导入 `import protocol` 会 `ModuleNotFoundError`；而 P0-D4 的逐字节 hash 一致性检查恰好**封死了「vendoring 时改写 import」这条标准出路**——所以约束只能落在源头。注意这个错误在 L1、L2、CI hash 检查下**全部隐形**（普通解释器里顶层 `protocol` 恰好可导入），只在 L3 真 Blender enable 时爆发，因此必须靠 §9 的专项 CI 检查提前拦截。

### 3.2 线格式

```
[4 字节大端 uint32 长度][UTF-8 JSON 载荷]
```

| 规则 | 值 |
|---|---|
| 读端行为 | 必须读满 `length` 字节才切帧——在 §3.7 的非阻塞模型下由每连接接收缓冲区保证（URS NFR-R3） |
| 单帧上限 | 16 MiB，**读写两端同限** |
| 读端超限 | 直接断开，**不做部分解析**（防恶意长度头导致内存耗尽） |
| **写端超限** | 序列化后超过 16 MiB 的响应帧**不得发送**：丢弃原响应，改回 `INTERNAL_LIMIT_EXCEEDED` 错误帧，并记诊断日志。写端行为必须显式定义——否则超大响应的异常会逸出 tick（见 §3.6 护栏） |
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

`params` 在信封层是开放 object，**这不违反 URS FR-05**。FR-05 约束的是 IR 内部 `operation.payload` 的判别联合，校验发生在 Server 的 IR 校验器中，不在传输层。Phase 1 的 IR 以 `params.modeling_ir` 进入，**信封无需改版**——这是本 spec 为 IR 预留的承载能力。

`v` 是信封版本，独立于 IR schema 版本与 Bridge 版本（URS NFR-C4 要求三者独立编号）。线上字段名用短名 `v`；同一个值在 `session.json` 与 `describe_capabilities` 中的字段名是 `envelope_version`——**同一概念，两处命名不同是刻意的**（线上省字节，对外可读）。

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
    def snapshot(self) -> SceneSnapshot: ...
```

`SceneSnapshot` 是纯 dataclass，**不含任何 bpy 对象**——这是分层边界的物理保证。

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

`bridge/core/` 内**不得出现 `import bpy`**，由 CI 静态检查强制。

### 3.5 `scene_hash` 算法

```
line(obj) = f"{obj.name}\t{obj.type}\t{q(matrix_world)}\t{data_kind}\t{data_counts}"
q(m)      = 16 个浮点各自 round(v, 6)，并以 +0.0 归一化 -0.0，定长格式化
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

`scene_revision` 是会话内单调计数器，由 `depsgraph_update_post` handler 递增，Phase 0 需注册该 handler。它在 Bridge 重启后归零，因此**只能用于会话内比对**；跨进程、跨会话的「场景是否变过」一律看 `scene_hash`。

**注意这不等于说 `scene_hash` 是冲突判定依据。** 按 P0-D2，Phase 1 的冲突判定用 `plan_scope_hash`（只覆盖 IR 依赖集）。`scene_hash` 的职责限于变更检测与快照标识——它对整个场景敏感，用作拒绝计划的依据会过度触发。

### 3.6 任务队列与 tick

```python
class TaskQueue:
    def submit(self, req: Request, reply: Callable[[Response], None],
               deadline: float) -> None:
        """I/O 线程调用，线程安全。队列满时抛 QueueFull。"""

    def tick(self, budget_ms: int) -> float:
        """主线程调用。在预算内批量处理，返回建议的下次调用间隔（秒）。"""
```

| 参数 | 值 | 依据 |
|---|---|---|
| 队列容量 | 64 | 超出抛 `QueueFull` |
| tick 预算 | 50 ms | URS NFR-R4 |
| 有任务时返回间隔 | 0.01 s | 尽快继续排空 |
| 空闲时返回间隔 | 0.1 s | 降低空转开销 |

**队列满的响应路径**：`submit` 抛 `QueueFull` 后，**I/O 线程直接回一帧 `BRIDGE_BUSY`（`retryable=true`）**，请求不入队。这是少数几种「回错误帧」而非「静默断开」的情况——调用方需要知道该重试，而非误判为故障。

**过期请求的处理**：每个任务携带 `deadline`（入队时间 + 客户端超时）。`tick` 取出任务时先检查 `deadline`，已过期的**直接丢弃、不执行**——Server 早已超时断开，执行它只会白占主线程预算。

**reply 绝不直接写 socket**（§3.7 规则 3）：reply 的实现是「入 outbox + 唤醒 I/O 线程」，对已断开连接的入队被静默丢弃。队列层仍防御性捕获 `OSError` 并只记诊断日志、不向上传播——双保险，因为 tick 循环的存活优先于任何单个响应。

`tick` 一次处理**多个**任务直到预算耗尽，不是每次一个。

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

**护栏不可省略**：`bpy.app.timers` 对抛异常的回调**直接注销**。§3.6 已强制捕获的两类异常（SceneReader、reply）之外，任何逸出的异常（信封序列化、framing 编码、队列内部缺陷）都会永久杀死 tick——此后 I/O 线程还活着、面板还显示「已开启」、请求照常入队然后全部过期，Server 端只见 `BRIDGE_TIMEOUT`，Bridge 变成无人知晓的静默僵尸。护栏保证回调永不向 timer 抛异常、永远返回下次间隔。

`persistent=True` 是为 Phase 1 的 hard 回滚（`wm.open_mainfile`）提前铺路（URS NFR-R6）。Phase 0 用不到文件重载，但注册方式现在定对，省去 Phase 1 返工。

### 3.7 连接 I/O 模型与确定性关闭

**连接读取模型是规格，不是实现自由度：单 I/O 线程，select 多路复用，非阻塞读。**

```python
wake_r, wake_w = socket.socketpair()

# I/O 线程主循环
ready, _, _ = select.select([listener, wake_r] + established_conns, [], [])
if wake_r in ready:
    break
```

五条强制规则（v3 审计后修订：写路径改为**单写者**，发送锁废止）：

1. **select 集合包含所有已建立连接**，不只是 listener。已建立连接设为非阻塞；每连接维护一个接收缓冲区，数据到达即追加，凑满「4 字节长度头 + length 字节」才切出一帧进入鉴权与路由。**NFR-R3 的「读满 length 字节」由缓冲逻辑保证，不是阻塞 recv 循环**——阻塞循环会让一个只发半个长度头的客户端（半开连接、慢客户端或恶意进程）楔死整个 I/O 线程，其余连接全部得不到服务，且 self-pipe 唤不醒阻塞中的 `recv`。
2. **接收缓冲区累计超过 16 MiB 上限即断开该连接**（§3.2 读端规则在此模型下的落点）。
3. **单写者：所有 socket 写只由 I/O 线程执行。** 主线程 tick 的 reply 与 QueueFull 的 `BRIDGE_BUSY` 都只是**把整帧追加进该连接的发送队列（outbox）并唤醒 select**；I/O 线程在连接可写时非阻塞发送（部分写以偏移量续写，整帧序不可交错——由单写者结构保证，无需锁）。**主线程从不触碰 socket**：不读数据的恶意客户端只能堆积自己的 outbox，不可能阻塞主线程（NFR-R4 的 50 ms 预算因此在结构上成立，而非依赖发送超时）。
4. **发送背压有上限**：单连接 outbox 累计超过 **32 MiB** 即断开该连接并丢弃积压——「建立连接、发出请求、拒不读取响应」是最廉价的本地资源攻击，必须 fail-closed。**断开动作由 I/O 线程执行**：主线程若代劳就等于碰了 socket，规则 3 立即失效。同理，outbox 的字节计数被两个线程读写，其增减必须在同一把锁内完成——单边持锁不构成互斥。
5. **I/O 线程每轮迭代有顶层护栏**（与 §3.6 的 tick 护栏对等）：单连接的任何异常只允许断开该连接；意外异常记诊断日志后继续循环。没有这条，一个 `BrokenPipeError` 逸出就会杀死唯一的 I/O 线程——listener 不再 accept、面板仍显示「已开启」，与 tick 之死同构的静默僵尸。

停止时向 `wake_w` 写一字节并置停止标志，`select` 立即返回，线程干净退出。`wake_w` 同时用作「outbox 有新帧」的通知信号——收到唤醒后先检查停止标志再继续循环。单线程模型下不存在「连接线程」，join 一个线程即回收全部连接处理。

`unregister()` 固定顺序：

1. 置停止标志
2. 唤醒 `select`
3. join I/O 线程（超时 2 s）
4. **`shutdown()` + `close()` 所有仍活跃的已 accept 连接**
5. 关闭监听 socket 与 `socketpair`
6. 注销 timer
7. 注销 `depsgraph_update_post` handler
8. 清空任务队列（对残留任务不再回复）
9. 删除 socket 文件与 `session.json`
10. 删除会话目录

**第 4、5 步不可省略。** I/O 线程退出只停止事件循环，已建立的 conn 仍持有 fd。漏掉它们会同时造成两个后果：fd 泄漏（直接导致「会话循环 20 次无泄漏」验收失败），以及 Server 侧挂起等待响应直到超时，而不是立即收到连接关闭。

会话期间必须维护一个活跃连接集合（加锁），accept 时加入、连接结束时移除；关闭时各连接的 outbox 积压一并丢弃，不做 flush——确定性关闭优先于末尾响应的送达。

**任一步失败都记日志并继续执行后续步骤**，避免停在半清理状态。`unregister()` 必须幂等——重复调用不抛异常。

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
  逐级建目录并各自 chmod 0700（见 §2.2 权限机制表）
  token = secrets.token_urlsafe(32)
  确定 socket 路径（含 sun_path 长度校验，见下）
  写 session.json（O_EXCL + 0o600 临时文件 → os.replace）
  bind socket → os.chmod(sock, 0o600) → listen(8)
  启动 I/O 线程

# bridge/blender/panel.py —— operator 额外做：
  register timer(persistent=True) + register depsgraph handler（必须带 @persistent 装饰器，SPIKE-1.4）
  面板状态 → 「已开启 / 断开」
```

因为建目录、bind、写 token 都在 core 里，**L2 契约测试可以直接断言权限位（`0700` / `0600`）而无需启动 Blender**（§7.2）。若把这些逻辑写在 operator 中，该验收项就只能退到 L3。

**sun_path 长度校验**：macOS 的 UDS 路径受 `sun_path` **104 字节**硬限制，默认 socket 路径的固定部分（`/Users/<name>/Library/Application Support/BlenderCodex/run/gui-<pid>-<rand8>/bridge.sock`）已占约 83 字节 + 用户名长度，用户名超过 ~20 字符即触界。`Session.start` 必须校验完整 socket 路径 ≤ 100 字节；超限时将 socket 落到 `tempfile.mkdtemp(prefix="bcx-")`（`$TMPDIR` 下，天然 0700）。**因此 `session.json` 增加 `socket_path` 字段作为 socket 位置的权威来源**——discovery 一律从 `session.json` 读取 socket 路径，不得假设 socket 位于会话目录内。

**token 随每个请求校验，不是只在握手时。** 用 `secrets.compare_digest` 常数时间比较。Server 可能中途重启重连，一次性握手态在此不成立。

### 4.2 三个工具

| 工具 | 流程 | 超时 |
|---|---|---|
| `get_blender_status` | Server 扫描 → 并发向各活实例发 `status` → 聚合 | 单实例 2 s，整体 3 s |
| `get_scene_summary` | Server → `scene_summary` → I/O 线程校验 token 后**入队即返回** → 主线程 tick 取出 → `SceneReader.snapshot()` → reply | 15 s |
| `describe_capabilities` | Server 本地回答，**不经 Bridge** | — |

**`get_blender_status` 必须并发，不能串行。** URS NFR-P1 要求只读工具 P95 < 2 s；串行遍历 N 个实例会退化为 N × 2 s。实现用 `concurrent.futures.ThreadPoolExecutor`（`max_workers=8`），单实例超时 2 s、整体超时 3 s，超时的实例标记为 `disconnected` 后继续聚合。

**网络线程绝不触碰 bpy。** token 校验是纯字符串比较，放在网络线程既安全又必要——未认证请求不该有资格占用主线程预算。

`describe_capabilities` 不需要 Blender 在线，这是刻意的：它回答「你支持什么」，不是「现在能干什么」。

**无活跃实例时 `get_blender_status` 返回 `ok=true` + 空列表 + 引导文案，不是错误。** 这直接对应 P0-D1 的已知摩擦点——用户忘记点按钮时，Codex 必须拿到「去 N 面板点击允许连接」，而不是语焉不详的失败。

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

**发现是惰性的，且带短缓存。** discovery **不在 Server 启动或 import 期执行**（否则违反 §5.3 的冷启动预算），而是在首次需要实例信息时触发，结果缓存 1 秒。缓存是必要的：`get_blender_status` 与 `get_scene_summary` 在同一轮对话中往往连续调用，没有缓存就会对每个实例重复握手，白白吃掉超时预算。缓存过期或显式收到 `BRIDGE_UNAVAILABLE` 时重新扫描。

### 4.4 版本门禁在 Phase 0 的实际效果

Bridge 在 `session.json` 与 `status` 响应中上报完整版本号，Server 侧 `versions.py` 判定。

因为 Phase 0 全是只读工具，**非基线版本不会被拒**，只在响应中附 `version_warning`（符合 URS FR-03：非基线版本只读可用、写工具拒绝）。拒绝逻辑要到 Phase 1 有写工具时才生效，但判定函数在 Phase 0 就位并测试。

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
| 执行 | `reply` 时 socket 已关闭 | 捕获并静默丢弃，只记诊断日志 |
| 发现 | 无活实例 | `ok=true` + 空列表 + 引导文案 |
| 发现 | `instance_id` 不存在 | `INSTANCE_NOT_FOUND` |
| 发现 | 握手 `instance_id` 不匹配 | 视为 stale，不计入活实例 |
| 编码 | 响应帧序列化超过 16 MiB | `INTERNAL_LIMIT_EXCEEDED`（写端规则，§3.2） |
| 版本 | 握手 `envelope_version` 不一致 | `ENVELOPE_VERSION_MISMATCH`（status 中仍列出该实例，见 §4.3） |
| 连接 | 连不上 / ECONNRESET / EPIPE | `BRIDGE_UNAVAILABLE`，`retryable=true` |
| 超时 | 请求超时 | `BRIDGE_TIMEOUT`，`retryable=true` |
| 版本 | 非基线 Blender | **Phase 0：只读放行 + `version_warning`** |
| 版本 | 非基线 Blender + 写工具 | `UNSUPPORTED_BLENDER_VERSION`（错误码在 Phase 0 定义并单测，**运行时不触发**——本阶段无写工具） |

**认证失败为何不回响应**：回「token 错误」等于向扫描者确认「此 socket 存在且协议正确」。直接断开，让盲扫拿不到区分信息。这与 §2.3 承认的 token 局限配套——既然 token 挡不住能读文件的进程，至少不要主动帮它确认目标。

**traceback 不进错误响应**，只进本地诊断日志——异常文本可能携带文件路径。

### 5.1 Blender 崩溃后的残留

崩溃不执行 `unregister`，socket 与 `session.json` 会留在磁盘。清理责任在 Server 的 discovery——那是唯一能观察到「进程已不在」的位置。

**Server 只清理同时满足两个条件的会话目录**：预筛判定进程不存在，且连接失败。两条同时成立才动手，避免误删一个只是暂时繁忙的实例。

**`session.json` 缺失或损坏的目录**是双条件判据的盲区（无 pid 可预筛、无 socket_path 可连）。规则：仅当该目录 mtime 距今超过 60 秒才允许清理——`Session.start` 的「建目录 → 写 json」序列存在毫秒级窗口，Bridge 也可能恰在窗口内崩溃，宽限期把「正在创建」与「真残留」区分开。

### 5.2 日志分流

| 类型 | 去向 | 内容 |
|---|---|---|
| 审计（URS FR-33） | `logs/server-YYYY-MM-DD.jsonl` | `ts` / `request_id` / `tool` / `instance_id` / `transaction_id` / `params_digest` / `ok` / `duration_ms` / `paths` / `error` |
| Server 诊断 | Server 进程 stderr | traceback、连接细节、时序 |
| Bridge 诊断 | Python `logging` → Blender 进程 stderr（终端启动 Blender 时可见） | 认证失败、tick 护栏捕获的异常、清理步骤失败 |

参数记摘要不记原文（URS NFR-O3）。`paths` 与 `transaction_id` 在 Phase 0 分别恒为空数组与 `null`——两个占位字段策略一致：FR-33 要求的 schema 现在就位，Phase 1 才有内容。

**Bridge 侧无独立审计文件**：审计责任在 Server 侧（每次工具调用一条）；Bridge 只做诊断日志。「无 token 连接被拒并记日志」这条验收中的「记日志」落在 Bridge 诊断日志，L2 通过向 FakeBridge 注入 logger 断言。

**stdout 全程只有 JSON-RPC**（URS NFR-O1），由 L2 测试强制：跑完整 stdio 会话，断言 stdout 每一行都能解析为合法 JSON-RPC。

### 5.3 冷启动预算

URS NFR-P2 要求 < 5 s，Codex `startup_timeout_sec` 默认 10 s。风险在 import 阶段。措施：重模块延迟导入；discovery 扫描**不在 import 期执行**；加一条启动耗时回归断言。

---

## 6. 工具 Schema

### 6.1 `get_blender_status`

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "instance_selector": { "type": ["string", "null"] }
    },
    "additionalProperties": false
  },
  "outputSchema": {
    "type": "object",
    "required": ["ok", "instances"],
    "properties": {
      "ok": { "type": "boolean" },
      "guidance": { "type": ["string", "null"] },
      "instances": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["instance_id", "pid", "mode", "bridge_state",
                       "blender_version", "blender_supported"],
          "properties": {
            "instance_id": { "type": "string" },
            "pid": { "type": "integer" },
            "mode": { "type": "string", "enum": ["gui"] },
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

`mode` 的 enum 在 Phase 0 只有 `"gui"`——Headless Worker 属于 Phase 2，届时扩为 `["gui", "headless"]`。

无活实例时：`ok=true`，`instances=[]`，`guidance` 填引导文案。

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
                 "units", "summary"],
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
        "required": ["object_count", "mesh_count", "camera_count", "light_count"],
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
  "inputSchema": { "type": "object", "properties": {}, "additionalProperties": false },
  "outputSchema": {
    "type": "object",
    "required": ["server_version", "envelope_version", "phase",
                 "supported_tools", "baseline_blender", "ir_schema_version",
                 "supported_operation_kinds"],
    "properties": {
      "server_version": { "type": "string" },
      "envelope_version": { "type": "integer" },
      "phase": { "type": "string" },
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
      }
    },
    "additionalProperties": false
  }
}
```

Phase 0 的 `ir_schema_version` 为 `null`，`supported_operation_kinds` 为 `[]`。这是诚实的——本阶段确实没有 IR，返回一个假版本号会误导调用方。

`baseline_blender` 来自 `server/core/capabilities.py` 中的**配置常量**（形如 `{"version": "5.2.0", "platform": "macos-arm64"}`），不是运行时探测。它回答的是「本 Server 以哪个版本为基线」，与当前连着什么无关。`versions.py` 的门禁判定读同一常量，保证判定依据与对外声明一致。`connected_instances` 才是运行时信息，且在无实例时为空数组。

---

### 6.4 Server `instructions`（URS FR-34，2026-08-06 增补）

MCP Server 初始化响应必须携带 `instructions`（Codex 消费该字段已核实）。Phase 0 文案，关键规则前置：

> Blender 只读控制通道（Phase 0）。调用任何工具前先 `get_blender_status`；若无实例，引导用户在 Blender 3D 视口按 N → 「Codex」页签 → 点击「允许 Codex 连接」。本 Server 无写工具，不要尝试让 Blender 执行代码。`describe_capabilities` 可在 Blender 离线时回答。

实现：`FastMCP(name, instructions=...)`；L2 子进程测试断言 initialize 响应含非空 `instructions`（§7.2）。该文案与 `GUIDANCE` 常量口径一致——两处都指向同一个 N 面板操作路径。

## 7. 测试策略

### 7.1 L1 单元测试（无 Blender、无 socket）

| 模块 | 覆盖点 |
|---|---|
| `framing` | 粘包、部分读、超限拒绝、长度头畸形 |
| `envelope` | 序列化往返、版本字段、未知字段处理 |
| `session` | token 生成熵、常数时间比较、会话状态机 |
| `router` | 分发、未知 method |
| `queue` | 预算控制、批量处理、队列满、并发提交线程安全 |
| `lifecycle` | 停止幂等、失败步骤不中断后续 |
| `path_policy` | `..`、符号链接、`~` 展开越界、扩展名白名单 |
| `versions` | 门禁判定矩阵 |
| `discovery` | `tmp_path` 造假会话目录，扫描与 stale 判定 |
| `audit` | JSONL 格式、参数脱敏 |

tick 由 `FakeClock` 驱动，不使用真实 sleep。

### 7.2 L2 契约测试（真 UDS，Fake Blender）

进程内起 FakeBridge：**真实的 `bridge/core/`** + `FakeSceneReader` + 测试专用 driver（线程驱动 tick，不碰 `bpy.app.timers`）。Server core 通过真实 UDS 连接。

覆盖：完整往返 · token 拒绝后断开（含诊断日志断言） · 5 MiB 载荷 · 16 MiB 拒绝 · 并发请求 · Bridge 中途断开 · 超时 · self-pipe 确定性关闭 · socket 与目录权限位断言 · stdio 会话 stdout 纯净性 · 冷启动计时 · **initialize 响应含非空 `instructions`（§6.4）** · **单连接流水线下 BUSY 与正常响应帧不交错（§3.7 单写者的直接验证）** · **不读响应的客户端触发 outbox 上限断开且 tick 不受阻**。

审计新增的必测项：

- **关闭时活跃连接被回收**：建立 N 条连接后 `unregister()`，断言全部 fd 已关闭、客户端立即收到关闭而非超时（§3.7 第 4–5 步）
- **半帧不楔死 I/O 线程**：一条连接只发 4 字节长度头后静默，断言其余连接的请求仍被正常服务，且关闭仍在 2 s 内完成（§3.7 规则 1）
- **并发写不交错**：一条连接上流水线提交使 BUSY 与正常响应同时在途，断言客户端收到的每一帧长度前缀完好（§3.7 规则 3 单写者）
- **队列满回 `BRIDGE_BUSY` 而非断开**：塞满 64 个任务后再提交，断言收到错误帧且连接仍可用
- **过期任务被丢弃**：提交一个 deadline 已过的任务，断言 `SceneReader` 未被调用
- **`reply` 失败不中断 tick**：客户端在响应前断开，断言后续排队任务仍被正常处理
- **tick 护栏兜底**：注入在信封序列化阶段抛异常的响应，断言 tick 返回间隔而非抛出、后续任务不受影响（§3.6 护栏）
- **非基线版本附警告**：FakeBridge 上报 `4.5.3`，断言 `get_scene_summary` 响应中 `version_warning` 非 null（§4.4 的运行时行为，仅测判定函数不够）
- **信封版本不匹配**：FakeBridge 上报 `envelope_version: 2`，断言实例在 status 中列出且 `scene_summary` 返回 `ENVELOPE_VERSION_MISMATCH`

**Server 的 runtime 根注入**：`server/core` 从环境变量 `BLENDERCODEX_ROOT` 读取根目录（默认 `~/Library/Application Support/BlenderCodex`），`run/` 与 `logs/` 由此派生。这是 stdout 纯净性与冷启动计时两条子进程级测试的前提——没有注入点，它们只能污染真实用户目录。

### 7.3 L3 冒烟测试（真 GUI Blender）

只覆盖 L1/L2 在原理上无法证明的四件事：

1. `bpy.app.timers` 真的在主线程驱动 tick
2. `depsgraph_update_post` 真的递增 `scene_revision`
3. `SceneReader` 从真实场景读出的字段正确
4. **完整会话循环** 20 次无线程泄漏、无残留 socket。**循环定义：enable → 调用「允许连接」operator → 建连验证 → 调用「断开」operator → disable。** 在 P0-D1 下 enable 本身不建 socket 不起线程，只循环 enable/disable 会空转通过、什么也没测——被测对象是 `Session.start`/`stop`，循环必须包含它们。由 runner 脚本直接调用 operator（`bpy.ops`）驱动，泄漏断言用 `threading.enumerate()` 计数与会话目录残留检查

执行方式：`blender --python smoke/runner.py`（GUI，**不是** `--background`），runner 在 Blender 内跑断言并写结果文件，外部脚本读文件判定。

### 7.4 验收映射（URS §10.1）

| 验收项 | 层 |
|---|---|
| 三个只读工具返回符合 outputSchema | L2 + L3 |
| 非基线版本：只读可用、写工具被拒 | L1（Phase 0 无写工具，测判定函数本身） |
| 强制终止 Blender → `BRIDGE_UNAVAILABLE`，重启后重连 | L2（模拟断开）；真 kill 在验收核对时人工复核一次（不在 §7.3 的 L3 四项内） |
| 完整会话循环（enable → 允许连接 → 断开 → disable）20 次无泄漏、无残留 socket | **L3 独有**（循环定义见 §7.3 第 4 条） |
| 5 MiB 载荷分帧无截断 | L2 |
| socket 自创建即 0700/0600；无 token 连接被拒 | L2 |
| stdout 全程仅含 JSON-RPC | L2 |
| 冷启动 < 5 s | L2 |

**八条中七条可自动回归，仅一条必须真 Blender。**

### 7.5 不做

不测 MCP SDK 本身 · 不测 bpy 行为正确性（只测本项目的读取逻辑） · Phase 0 不做性能压测，URS NFR-P1 只做单点计时断言。

---

## 8. 前置 Spike —— 已执行，结果如下

**执行日期 2026-07-23，实测环境：Blender 5.2.0 LTS（build 2026-07-14，hash fbe6228777e7）/ Apple M4 / macOS 26.5.2。** 本节由「待验证问题」转为「已确认事实」，后续任务只准引用本节结论。

### 8.1 SPIKE-1 · timer 与 handler 语义

| # | 问题 | 实测结果 | 决策 |
|---|---|---|---|
| 1 | `--background` 下 timer 是否触发 | **不触发**：1 秒主线程 sleep 循环期间回调 0 次；脚本结束即退出，无事件循环 | L3 维持 GUI 半自动；CI 只跑 L1+L2。印证 URS 既有设计（Headless Worker 独立受控 CLI，不复用 Bridge） |
| 2 | GUI 下 timer 间隔与抖动 | `return 0.05` → 中位 50.9 ms、p95 55.4 ms，**+1~5 ms 内稳定守约**；`return 0.0` → 中位 5.7 ms 但 p95 47.8 ms、max 111 ms，**完全随事件循环起伏** | §3.6 参数维持（50 ms 预算 / 忙 0.01 s / 闲 0.1 s）。最坏排队延迟 ~100 ms + 处理时间，对 NFR-P1（2 s）余量充足 |
| 3 | timer 回调内 `bpy.context.scene` 可用性 | **可用**，返回活动 scene；回调确认运行于主线程（`threading.main_thread()` 判定） | §3.5 简化：**主选 `bpy.context.scene`**，`None` 时回退 `bpy.data.scenes[0]`，`scene_name` 照常回报 |
| 4 | `persistent=True` timer 跨文件重载存活（URS V-04） | 经 `read_homefile` 重载：**persistent timer 保持注册，非 persistent 被清除**。同路径实测 handler：**带 `@bpy.app.handlers.persistent` 装饰器的 depsgraph handler 存活，不带的被清除** | NFR-R6 的机制落定：timer 用 `persistent=True`，**handler 必须加 `@persistent` 装饰器**（此前 spec 未指明机制）。自愈重注册保留为防御层。注：实测走 `read_homefile` 重载路径；`open_mainfile` 同属文件加载路径，Phase 1 的 hard 回滚测试会直接覆盖 |

附带发现（Phase 2 备用）：`--background` 下 Data API 建对象 + `view_layer.update()` 会触发带 `@persistent` 的 `depsgraph_update_post`（计 1 次）——headless worker 未来若需变更计数，机制可用。

### 8.2 SPIKE-2 · Python 版本

**Blender 5.2.0 内置 Python = 3.13.13。** 决策：`protocol/` 与 `bridge/` 的语法基线定 **py313**；Server 侧 uv 钉 Python 3.13 与 Bridge 对齐（`mcp` 1.28.x 支持 ≥3.10，无冲突）。§9 工具链同步更新。

### 8.3 附带确认

- `bpy.data.scenes` 实测为**名称字典序**（创建顺序 Zeta→Alpha，遍历得 Alpha, Scene, Zeta）——§3.5 的排序论述由推断转为已验证。
- 钉定版本记录（URS NFR-C2 / R-01）：**Blender 5.2.0 LTS**。5.2 系列出 corrective release 后重估是否升级，升级即触发 golden 基线重录（Phase 2 起生效）。

---

## 9. 工具链

| 项 | 选择 |
|---|---|
| Server 依赖管理 | `uv`，Python 钉 3.13（与 Bridge 对齐，SPIKE-2），`mcp` 钉 `1.28.x`（URS NFR-C3） |
| 测试 | `pytest` + `pytest-timeout` |
| 静态检查 | `ruff`（`target-version = py313`，SPIKE-2）+ `mypy`（`core/` 开 strict） |
| CI | 跑 L1 + L2；L3 本地执行 |

四条 CI 强制检查：

1. `bridge/core/` 内不得出现 `import bpy`
2. `bridge/_vendor/protocol/` 与 `protocol/` 内容 hash 必须一致
3. **嵌套 import 冒烟**：把 `protocol/` 复制到人造深层包（模拟 `bl_ext.repo.bridge._vendor.protocol`）下执行导入，拦截绝对导入回归（见 §3.1 约束 2——该错误在 L1/L2 下隐形）
4. `protocol/` 与 `bridge/` 的语法版本不高于 py313（SPIKE-2 实测 Blender 5.2.0 内置 Python 3.13.13；`ruff` `target-version` 钉住）

---

## 10. 对 URS 的修订建议

**存档（2026-08-06 已全部落账 URS v1.1，见 URS §13）**——本表保留为当时的决策依据，不再是待办：

| URS 位置 | 现状 | 建议 |
|---|---|---|
| NFR-S5 | 称「同 uid 进程的越权连接由 token 阻断」 | 下调为「token 提升攻击成本并实现凭据轮换；同 uid 进程可读取会话文件，真正压缩风险的是显式会话窗口」。见 §2.3 |
| §2 术语表 | `scene_hash` 定义为「受管子集摘要」 | 改为全场景摘要，并新增 `plan_scope_hash`（IR 依赖集）。见 P0-D2 |
| **FR-11** | 称「冲突检测以 `scene_hash` 为权威依据」 | **改为以 `plan_scope_hash` 为权威依据。** 这是 P0-D2 的直接后果：`scene_hash` 重定义为全场景后，继续用它做冲突判定会过度敏感（场景任何角落的改动都会拒绝计划）。**此条不可与上一条分开执行**，否则冲突检测语义会自相矛盾 |
| `get_scene_summary` schema | 含 `include_objects` / `include_materials` | 移除（Phase 0 无对应输出），保留 `include_managed_objects`；新增 `scene_name`（见 §3.5） |
| §2 术语表 `scene_revision` | 格式定义为 `r{n}@{instance_boot_id}` 字符串 | 改为裸整数 + 「仅会话内有效」语义（本 spec §3.5）。内嵌 boot_id 的动机（跨会话比对天然失效）由「跨会话一律用 `scene_hash`」的规则取代，字符串拼接反而增加解析面 |
| FR-32 | 要求「配 `instances.json` 注册表」 | 改为「每会话 `session.json` + `run/` 目录扫描」（本 spec §2.2/§4.3）。中心注册表是共享可变状态，多实例并发启停需要加锁协调；每会话一文件天然无锁，stale 清理语义也更简单 |
| NFR-O2 | 要求 JSONL + OpenTelemetry | OTel/`traceparent` 推迟至 Phase 1（本 spec §1.2 已声明），Phase 0 只交付 JSONL 审计 |

---

## 11. 风险与未决

| ID | 风险 | 缓解 |
|---|---|---|
| **R-P0-01** | token 存于 `0600` 文件，同 uid 进程可读取后合法连接 | 显式会话缩短暴露窗口；认证失败不回响应；彻底方案（`SCM_RIGHTS` / 系统沙箱）超出 Phase 0 |
| ~~R-P0-02~~ | ~~`--background` 下 timer 行为未确认~~ | **已关闭**：SPIKE-1.1 实测不触发，L3 维持 GUI 半自动（§8.1） |
| ~~R-P0-03~~ | ~~Blender 内置 Python 版本未知~~ | **已关闭**：SPIKE-2 实测 3.13.13，语法基线 py313（§8.2） |
| **R-P0-04** | vendoring 的两份 `protocol/` 可能漂移 | CI hash 一致性检查，不一致即构建失败 |
| **R-P0-05** | Blender 崩溃残留会话目录，若清理判据过松会误删活实例 | 双条件判定（预筛失败 **且** 连接失败）才清理 |
| **R-P0-06** | 显式会话模型下用户可能忘记点击授权 | `get_blender_status` 返回结构化引导文案；Phase 0 结束后据实际反馈评估是否需要更强提示 |
| **R-P0-07** | 多场景文件的 scene 选择：主选 `bpy.context.scene`（SPIKE-1.3 已实测可用）；防御回退 `scenes[0]` 按名称字典序，重命名会改变指向 | 残余风险仅在回退路径；`scene_name` 回报使任何选择对调用方可见 |
| **R-P0-08** | `scene_hash` 对全场景敏感，超大场景（10 万+ 对象）下计算成本可能超出 15 s 超时 | Phase 0 只在真实工程上做单点计时；若超预算，Phase 1 引入增量 hash（依托 `depsgraph_update_post` 的脏标记）而非现在预先优化 |
| **R-P0-09** | macOS `sun_path` 104 字节上限：长用户名下默认 socket 路径超限 | `Session.start` 校验路径 ≤ 100 字节，超限回退 `$TMPDIR` 短目录；`session.json.socket_path` 是权威来源（§4.1） |
| **R-P0-10** | `depsgraph_update_post` 在高频编辑（拖拽、雕刻）下每帧触发，handler 内任何非平凡计算都会拖慢视口 | handler 只做 `revision += 1` 一条自增，**不做 hash**；`scene_hash` 只在收到 `scene_summary` 请求时按需计算 |

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
