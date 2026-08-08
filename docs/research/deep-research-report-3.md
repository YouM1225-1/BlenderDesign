# 面向 Codex / AI Agent 的 Token-Efficient Blender Skill、MCP 与 Addon 闭环架构研究

> **仓库归档说明（2026-08-08）**：本文是正式保存的外部研究输入，但**不是规范、实施 Plan 或当前仓库审计结论**。原文第 60–68 行自述未收到本仓库源码，已不适用于当前仓库；41 个 `turn…/filecite…` 引用标记不可移植，不能作为可复核证据。
>
> 原始文件 SHA-256：`91c64abacb3f8a636c2037c6717e4ca90717c7921754e9a98beefbac07c8f554`。经官方资料、源码与本仓库反例复核后的采纳/拒绝裁决见 [研究融合与开工基线审计](../audits/2026-08-08-deep-research-report-3-integration-audit.md)；执行状态只看 [ROADMAP](../ROADMAP.md)。以下正文除本说明外保持原样。


> 研究日期：2026-08-08（America/Los_Angeles）  
> 研究目标：不是单纯压缩 `SKILL.md`，而是最小化 **User → Codex → Skill → MCP → Blender Addon → bpy → Scene → Observation / Validation → Agent** 整个闭环的总 Token、往返次数与重复推理，同时保持或提高可靠性、建模能力、执行速度和可维护性。

本文使用以下标记严格区分证据层级：

| 标记 | 含义 |
|---|---|
| **[OpenAI 官方]** | OpenAI / Codex 官方文档或官方工程文章 |
| **[MCP 官方]** | Model Context Protocol 官方规范、SEP、官方博客 |
| **[Blender 官方]** | Blender Python API 官方文档 |
| **[第三方实现]** | GitHub 开源 Blender MCP / Agent 项目 |
| **[实验性]** | 尚未形成稳定、广泛兼容的产品能力或规范路径 |
| **[工程推断]** | 根据官方机制和源码行为推导出的工程结论 |
| **[生产建议]** | 本研究给出的推荐生产实现 |

## 执行摘要与现有实现审计边界

最重要的结论是：

**Blender Agent 的最大 Token 优化机会通常不在 `SKILL.md`，而在 Observation、Tool Result、Tool Granularity、Validation、Error、Vision 和长任务历史。**

也就是说，把一个 8,000-token 的 Skill 缩到 4,000 token，可能远不如消灭下面这种循环：

```text
get_scene_info → 8k tokens
reason
create object
get_scene_info → 9k
reason
scale
get_scene_info → 9k
reason
bevel
get_scene_info → 10k
reason
material
get_scene_info → 11k
reason
render
image
reason
```

更优的闭环应当是：

```text
scene.summary → 100~数百 token 级结构
reason
scene.apply([...10 个确定性操作...])
→ {"ok":true,"rev":106,"changed":["obj_17"]}
validate.run(...)
→ {"status":"pass","issues":[]}
必要时 render.preview
```

这里的数值只是说明量级关系，不是 OpenAI、MCP 或 Blender 官方给出的固定 Token 指标。

### 对“现有 Blender Skill”的审计状态

本轮对话中**没有收到你的实际 `SKILL.md`、`references/`、`scripts/`、MCP Server 仓库、Blender Addon 源码或仓库地址**。因此不能诚实地声称已经审计了“你的现有实现”。

尤其不能把 `ahujasid/blender-mcp`、`PatrykIti/blender-ai-mcp` 等公共项目假定为你的实现。

所以本报告采取两层处理：

第一层是对公开 Blender MCP 项目进行源码级/架构级抽样审计；第二层给出一个**以最小侵入改造为目标**的审计矩阵，使你的现有实现可以按模块映射进去，而不是建议推倒重写。

### 总体推荐架构

**[生产建议]** 最适合这个问题的方向可以概括为：

> **Thin Intelligent Agent + Thick Deterministic Runtime**
>
> LLM 保留：理解用户意图、空间/造型决策、模糊目标判断、创意决策、失败后的策略选择。  
> MCP / Addon 承担：状态、查询、计算、Batch、Recipe、ID、Diff、Cache、Validation、Retry、Error Classification、Logging、Render Artifact。

最终推荐闭环：

```text
User
  ↓
Codex
  ↓
Thin Blender Skill
  ├── Minimal Core Policy
  └── On-demand References
  ↓
Stable Small MCP Public Surface
  ├── Query
  ├── Batch Mutation
  ├── Recipe
  ├── Validation
  ├── Render / Asset
  └── Debug Escape
  ↓
MCP Control Plane
  ├── Task Manifest
  ├── Idempotency
  ├── Cache
  ├── Capability Registry
  ├── Error Store
  └── Artifact / Resource Registry
  ↓
Blender Addon
  ├── Main-thread Execution Queue
  ├── Stable Handle Registry
  ├── Scene Revision Tracker
  ├── Diff Engine
  ├── Query Projection
  ├── Recipe Engine
  ├── Geometry Compute
  └── Validator
  ↓
bpy / BMesh / Depsgraph
  ↓
Scene
  ↓
Compact Structured Observation
  ↓
Agent
```

这和 OpenAI 当前对 Skills 的 progressive disclosure 思路是高度一致的：Skill 在初始阶段只通过名称、描述等元信息参与选择，完整 `SKILL.md` 在 Skill 被选择后才读取；OpenAI 还明确建议 Skill 的描述承担好“何时使用 / 何时不使用”的路由职责，而不是把所有细节一次性放入初始上下文。citeturn12view0turn13view3turn13view4

同样，OpenAI 对 `AGENTS.md` 的指导强调“短而准确”优于冗长、模糊的说明，并推荐把任务特定内容放到单独 Markdown 文档中；Codex 会按目录层级组合 `AGENTS.md`，默认项目文档总读取量也存在大小预算，因此不适合把 Blender 百科、MCP API 手册和完整建模知识都塞入其中。citeturn13view0turn13view1turn13view2

### 优化优先级

按预期收益排序，我会把优化顺序定为：

| 优先级 | 优化对象 | 原因 |
|---|---|---|
| **Critical** | 全 Scene 重复序列化、Raw Mesh / Nodes、每步 Vision | 一次结果就可能超过整个 Skill |
| **Critical** | Atomic Tool → Observation → Atomic Tool 循环 | 同时放大 Tool Call、Result、History、Latency |
| **High** | 长 Tool Result、完整 traceback、stdout/stderr | 很容易长期滞留在 Agent 上下文 |
| **High** | 大量长期可见 Tool Schema | Schema 本身进入工具上下文，还增加选择难度 |
| **High** | 状态依赖对话历史 | 导致 Agent 每回合重新推断“已经做了什么” |
| **Medium** | 过大的 SKILL.md / AGENTS.md | 应优化，但通常不是最大热点 |
| **Medium** | 无条件 Validation、无条件 Render | 可通过分层显著减少 |
| **Low** | JSON 字段名从 `revision` 缩成 `r` | 可能牺牲可靠性，收益非常有限 |

这里有一个关键区别：**Prompt Caching 不等于 Context Optimization**。OpenAI 官方对 Codex Agent Loop 的说明表明，工具定义属于请求前缀的一部分；稳定、完全相同的前缀可以利用 prompt caching，而工具列表变化、顺序变化等会破坏缓存命中。Prompt caching 能改善成本和延迟，但已经进入当前逻辑上下文的大量 Scene Result、错误和历史仍然需要管理；长任务真正的上下文增长还要靠 progressive disclosure、结果外部化和 compaction。citeturn11search0turn13view3

## 官方能力与关键设计约束

### OpenAI / Codex 对 Skill、AGENTS、MCP 和 Context 的启示

**[OpenAI 官方]** 没有一个官方规则说“`SKILL.md` 必须小于 X tokens”，也没有官方规则说“Codex MCP 最佳工具数量一定是 8 个、10 个或 20 个”。

因此，任何固定数字都应该被看作工程起点，而不是官方限制。

更可靠的官方结论如下：

| 问题 | 官方资料支持的结论 | 对 Blender Skill 的意义 |
|---|---|---|
| Skill 应有多少长期指令？ | 无固定 Token 数字；强调按需读取和 progressive disclosure | Core Skill 只保留真正长期有效的路由、约束和 Done Definition |
| 哪些内容 Progressive Disclosure？ | 大型说明、示例、模板、附属资源可以只在 Skill 触发后读取 | Blender API 百科、Geometry Nodes 教程、复杂 troubleshooting 不应长期常驻 |
| AGENTS.md 放什么？ | durable project guidance；应保持短、准确 | 放仓库约定、测试命令、结构规则，不复制 Blender Skill |
| Skill 放什么？ | workflow / domain expertise | 放 Blender Agent 的工作策略，而非每个 bpy API |
| MCP 放什么？ | 外部工具/系统集成 | Blender 状态与执行能力应通过 MCP，而非聊天文本模拟 |
| 长任务 Context 如何处理？ | Codex 支持 compaction，Skills 按需展开 | 不应只依赖“模型自己记住全部过去结果” |
| Prompt caching 怎么利用？ | 稳定、完全相同的 prompt prefix 更容易命中 | Tool catalog / schema / server instructions 应尽量稳定 |
| Tool 是否属于 Prompt？ | Codex agent loop 中 tools 是请求的一部分 | Tool Explosion 不只是 UX 问题，也有上下文成本 |

OpenAI 的 Codex MCP 文档还指出，Codex 会读取 MCP 初始化时的 `instructions`，并和 server tools 一起使用；官方特别建议让**前 512 个字符自包含**，以便在决定是否使用服务器时就具备关键指导。citeturn24view0

这意味着一个很容易忽略的新 Token 源是：

```text
AGENTS.md
+
SKILL.md
+
MCP Server instructions
+
Tool descriptions
```

如果四者重复写：

> 调 Blender 前要检查 Scene  
> 操作后要验证  
> Blender Context 必须正确  
> 遇错先看日志  
> 不要……

你不是增加了可靠性，而是在**重复购买同一条规则的上下文 Token**。

**[生产建议]** 应采用单一职责：

```text
AGENTS.md
    Repo / test / development conventions

SKILL.md
    Agent decision policy + workflow router

MCP instructions
    Cross-tool runtime contract only

Tool schema
    Only semantics needed to select/call this tool

Addon
    Rules that can be programmatically enforced
```

例如“进入 Edit Mode 前确保 selection / active object 正确”属于 Blender 执行机制，最好由 Addon 保证，而不是让 LLM 每次记住。

### Tool 数量与 Prompt Cache 的一个重要反直觉结论

**[工程推断]** 对 Codex 而言，最佳设计不是：

> 每一回合根据情况动态修改 `tools/list`，只留下几个工具。

这样虽然这一回合工具少，却可能改变 prompt prefix，损害 OpenAI prompt cache 的稳定性。OpenAI 已明确指出工具及其顺序属于可缓存前缀的一部分，早期 Codex MCP 工程甚至遇到过工具顺序不一致造成缓存 miss 的问题。citeturn11search0

更好的方式是：

```text
始终稳定可见：
    scene.summary
    scene.query
    scene.apply
    recipe.run
    validate.run
    render.run
    asset.transfer
    capability.search
    debug.inspect

内部有：
    80+ atomic/internal operations
```

长尾能力通过：

```text
capability.search(...)
→ compact signatures

scene.apply(op=...)
或
recipe.run(...)
```

调用。

也就是说：

> **不要不断改变 MCP 可见 surface；保持一个小而稳定的 public surface，再让它访问内部能力。**

这同时优化：

- Tool Schema Token
- Prompt Cache
- Tool Selection
- Agent Planning
- API 可维护性

### MCP Tool 与 Resource 应如何分工

MCP 官方规范明确把 Tools 定义为 model-controlled 的操作能力；Resources 是通过 URI 暴露的上下文数据，支持 `resources/list`、`resources/read`、URI templates，以及协议定义的分页等机制。自定义 URI scheme 是可以成立的。citeturn14view0turn14view1turn21search2turn21search3

因此你提出的：

```text
blender://scene/current
blender://object/{id}
blender://material/{id}
blender://render/{id}
blender://task/{id}
```

**在 MCP 协议设计层面是合理的。**

推荐职责：

| MCP Primitive | 应承担 |
|---|---|
| **Tool** | 修改状态、执行计算、运行验证、触发 Render、Import/Export |
| **Resource** | Scene snapshot、Object Detail、大型 Node Graph、Render Artifact、Task Manifest、Error Detail |
| **Resource Link** | Tool Result 中指向大型结果 |
| **Prompt** | 可复用的用户/工作流提示，不作为 Scene 状态数据库 |

例如：

```json
{
  "ok": true,
  "revision": 106,
  "changed": ["obj_17"],
  "detail_uri": "blender://scene/s7/diff/105/106"
}
```

而不是：

```json
{
  "ok": true,
  "scene": {
    "... 12,000 tokens ...": "..."
  }
}
```

但是有一个必须强调的限制：

**[MCP 官方] Resource 并不保证自动节省 LLM Token。**

协议定义了 Resource，**Host 如何把 Resource 暴露给模型、何时读入 Context 是 application-driven 的**；协议本身并不规定“Resource 永远不进入模型上下文”。citeturn14view0turn21search3

同时，当前 Codex MCP 文档明确说明 stdio、Streamable HTTP、server instructions 等能力，但本次检索到的 Codex MCP 功能说明没有给出“所有 MCP Resource 一定按照某种 lazy-loading 方式呈现”的强保证。citeturn24view0

所以生产实现应该：

```text
首选：
Tool → minimal structured output + resource URI

兼容 fallback：
Tool(detail="full")
debug.inspect(error_id)
scene.query(... projection ...)
```

而不是让整个架构依赖未经目标 Codex Client 实测的 Resource UX。

### Structured Content 也存在隐藏 Token 陷阱

MCP Tools 规范支持结构化 Tool Result，并允许声明 `outputSchema`。但为了兼容旧客户端，规范还建议返回 `structuredContent` 时同时提供对应的 JSON text content。citeturn14view1

这意味着如果你返回：

```json
structuredContent = 8,000 tokens
text = 同一份 JSON 8,000 tokens
```

在某些 Host 路径中可能造成极其浪费的重复信息。

所以推荐：

```json
{
  "ok": true,
  "revision": 106,
  "issue_count": 2,
  "detail_uri": "blender://validation/val_92"
}
```

结构化输出本身保持紧凑；大型细节放 Resource / Artifact，真正需要时才读取。

### MCP 的最新演进对 Blender Agent 有什么意义

MCP 官方围绕 `2026-07-28` 代际规范的说明把核心协议进一步推向 stateless，并引入 Extensions 框架、Tasks 扩展以及 `ttlMs` / `cacheScope` 等列表与 Resource Read 的缓存提示。官方同时明确指出，2025-11-25 中实验性的 Tasks 模型已经重新设计，旧实现需要迁移。citeturn25search3turn25search9

这非常适合 Blender：

```text
render
bake
simulation
large import
geometry optimization
```

都属于潜在 long-running operations。

但必须区别：

**[MCP 官方 / 当前演进]**

```text
MCP protocol core = increasingly stateless
Blender application = may remain stateful
```

所以不是说“Server 不许有 SQLite 状态”，而是：

> 不要让重要任务状态只存在一个隐式 TCP/MCP session 里。

应该显式使用：

```text
task_id
scene_epoch
revision
job_id
request_state / state handle
```

并把真正状态存入服务端持久层。

对于 MCP Tasks，也应采用 capability negotiation：客户端支持 Tasks extension 时使用协议扩展；否则自己的：

```text
job.start
job.get
job.cancel
```

仍然需要存在兼容路径。MCP 官方当前 Tasks 已进入 extension 体系，而不是假定所有 Host 都支持。citeturn25search3turn25search9

### Blender 官方约束决定了 Addon 侧必须更“厚”

Blender 官方明确警告其 Python 集成**不是 thread-safe**，后台 Python thread 与 Blender 内部状态交互可能导致难以诊断的崩溃；官方更建议独立工作使用独立进程等方案。citeturn25search0

因此：

```text
Socket / HTTP worker thread
          ↓
不要直接任意 bpy.xxx
          ↓
Main-thread / controlled execution queue
          ↓
bpy
```

应该是生产架构原则。

第三方 AuraFriday MCP-Link 也采用 `bpy.app.timers` 将操作回到 Blender 主线程，这属于社区实现对这一 Blender 限制的工程应对，而不是 MCP 官方能力。citeturn25search4

Blender 的 Dependency Graph 提供更新信息，并暴露诸如 geometry / transform 更新状态，可作为 Scene Revision Tracker 的底层信号源之一。citeturn17search0

Blender `ID.session_uid` 还提供 session 范围内的唯一身份，适合用来解决 rename 后对象身份仍然保持的问题；但它的语义是 **session-wide**，因此不能据此假定跨 Blender 进程 restart 永久稳定。citeturn19search0

## 开源 Blender MCP 审计与代表性架构

当前公共 Blender MCP 生态已经出现了非常明显的几种不同哲学。

### 代表性仓库对比

| Repository | Architecture | Tool Count / Surface | Scene Query | Batch | Cache / State | Diff | Validation | Python Execute | Token Efficiency | Production Readiness |
|---|---|---:|---|---|---|---|---|---|---|---|
| `ahujasid/blender-mcp` | FastMCP → persistent TCP → Blender Addon | 持续扩展；未假定固定数量 | `get_scene_info`, object info | 未观察到 token-aware transaction batch | 有连接状态；未见 Scene projection cache 作为核心协议 | 未见 revision diff 为核心 | Screenshot / result-driven | **Yes** | **Low–Medium** | 很强的生态/原型参考，但默认观察协议仍偏重 |
| `djeada/blender-mcp-server` | stdio MCP → JSON/TCP Addon，并支持 headless Blender | README 当前声明 **27 tools / 7 namespaces** | scene info / list / hierarchy 等 | 未见统一 Batch DSL | async jobs | 未见 semantic Scene Diff | 基础结构化行为 | **Yes，sync/async** | **Medium-Low** | 运维、安全、长任务设计比 Demo 更成熟 |
| `PatrykIti/blender-ai-mcp` | FastMCP + Router + Addon + inspection/assert layers | 内部能力多，主张 curated LLM surface | inspection / scene graph / truth layer | Macro / Workflow 导向 | goal/session context | 架构方向适合扩展 | **Deterministic measurement/assert** | 默认哲学为不依赖 raw Python | **High potential** | 目前最接近本研究目标的第三方架构 |
| `AuraFriday/mcp_link_blender` | 通用 MCP bridge → full Blender Python API | 核心接口非常 generic | Agent 自己写 bpy 查询 | 可以靠单次 Python 脚本实现 | persistent Python session | 无语义 Diff 层 | Agent 自己决定 | **核心能力** | Schema Low，但 call/code/result cost High | 强力 escape hatch；不推荐作为默认语义 API |
| `mackson/blender-mcp` | stdio MCP → TypeScript/WebSocket bridge → Addon | README 声明 17 tools | 有 Scene / preview | 有较紧凑响应设计 | 未深度验证 | 未深度验证 | Vision-oriented | 有 custom bpy | **Medium–High 潜力** | 值得关注，但本次未做同等深度源码审计 |

`ahujasid/blender-mcp` 是目前非常有代表性的项目，GitHub 显示其已有大量 commits、forks 和活跃生态。其 MCP server 源码采用 FastMCP，通过持久 socket 与 Blender Addon 通信；源码包含 `get_scene_info`、`get_object_info`、viewport screenshot 与 `execute_blender_code` 等能力，并直接将 Blender 返回对象进行 JSON 文本化。citeturn25search10 fileciteturn2file0L2-L2

这类设计的优点是**极快获得 Blender 完整覆盖能力**，缺点则非常接近你的研究问题：

```text
Agent asks
→ full scene JSON
→ writes Python
→ result string
→ asks full scene again
```

它在功能覆盖上非常有效，但没有从协议层强制解决 observation amplification。

`djeada/blender-mcp-server` 当前公开说明有 27 个 tools / 7 namespaces，使用 stdio MCP server → localhost TCP Blender Addon，并包括 Scene、Object、Material、Render、Export、Undo/Redo、同步与异步 Python、Job status/cancel/list 等能力。citeturn25search5

其源码里大量操作分别暴露为：

```text
blender_object_create
blender_object_delete
blender_object_translate
blender_object_rotate
blender_object_scale
blender_object_duplicate
...
```

并普遍以 `json.dumps(result, indent=2)` 作为 Tool Result；同时提供 `blender_python_exec` 和 `blender_python_exec_async`。fileciteturn8file0L2-L2 fileciteturn9file0L2-L2

从 Token 角度，这已经比完全 raw Python API 稳定，但仍属于相对 atomic 的模型：

```text
create
→ transform
→ scale
→ material
→ render
```

容易形成很多 Agent ↔ Blender 往返。

`PatrykIti/blender-ai-mcp` 则特别值得借鉴，因为它的架构文档明确反对“一个 Blender API 对应一个 Tool”，目标是“one tool = one logical modeling task”，并要求工具内部处理 mode、selection、argument validation 和 Blender context。fileciteturn11file0L2-L2

更重要的是，该项目当前的 Tool Layering Policy 明确提出：

```text
Atomic Tool
→ primarily hidden/internal

Macro Tool
→ preferred normal public working layer

Workflow Tool
→ bounded orchestration

Vision
→ support

Measurement / Assertion
→ truth layer
```

并明确主张生产 LLM surface 使用较小的公开 Catalog，而不是默认暴露整个 atomic layer。fileciteturn12file0L2-L2

这不是 OpenAI 官方架构，但作为第三方实现，它与本研究结论高度吻合。

`AuraFriday/mcp_link_blender` 代表另一极端：提供 arbitrary Python、direct API access、persistent variables，让 Agent 几乎可以做任何 Blender 能做的事情。citeturn25search4

这种架构有一个非常有趣的 Token 特性：

```text
Tool Schema Token       很低
Tool Selection          很简单
```

但转移成：

```text
Generated Python Token      高
Bpy API reasoning           高
Retry / debugging           高
Traceback                   高
Security complexity         高
Auditability                低
Deterministic retry         低
```

所以：

> **少 Tool ≠ 少总 Token。**

一个只有：

```text
execute_python(code)
```

的 MCP，可能比 10 个设计合理的 domain tools 消耗更多总 Context。

另外，公共 Blender MCP 的安全问题不能忽略。`ahujasid/blender-mcp` 2026 年曾出现关于用户控制路径造成任意本地文件读取/外传风险的公开 issue；这再次说明 Blender MCP 不能把任意路径、任意 Python、任意网络调用都视为无风险 escape hatch。citeturn25search8

### 从这些仓库真正值得借鉴什么

可以归纳为：

| 值得借鉴 | 不应直接复制 |
|---|---|
| `ahujasid` 的成熟 Blender bridge 与生态覆盖 | full Scene / string result / Python-first 的 Observation 模式 |
| `djeada` 的 async jobs、headless execution、操作边界 | 过多 atomic round trips |
| `PatrykIti` 的 hidden atomic → macro/workflow public surface | 不应直接照搬其所有工具名或 router 逻辑 |
| `AuraFriday` 的 main-thread dispatch 与 universal escape hatch | 不能把 arbitrary Python 当默认工作层 |
| 小而稳定的 public surface | 为“工具少”而创造巨大 catch-all schema |
| 结构化结果 | pretty JSON、全量日志、全量状态自动返回 |

## Token Cost Model 与真正的 Token Hotspots

### 完整 Token 成本模型

对于一个 Blender Agent 长任务，可以近似表示为：

\[
T_{total}
=
T_{base}
+
T_{AGENTS}
+
T_{skill}
+
T_{tools}
+
\sum_{turn=1}^{N}
(
T_{history}
+
T_{args}
+
T_{results}
+
T_{validation}
+
T_{errors}
+
T_{vision}
)
\]

其中还有两个独立但相关的维度：

```text
Logical Context Cost
≠
Billed / Cached Input Cost
```

OpenAI Prompt Caching 会使稳定前缀变便宜、更快，但并不会神奇地让 Scene JSON 不再占当前上下文；Codex compaction 才属于长任务的 Context 管理机制之一。citeturn11search0turn13view3

### Token Cost Map

| Token Source | 严重度 | 为什么 |
|---|---|---|
| 重复完整 Scene serialization | **Critical** | Scene 规模随任务增长，结果越来越大 |
| Vertex / Edge / Face 原始数组 | **Critical** | 数千到数十万数字几乎永远不应给 LLM |
| Shader / Geometry Node 全图 JSON | **Critical** | 节点、socket、link 数量快速膨胀 |
| 每次修改后的图像 | **Critical** | Vision context 和模型调用成本都高 |
| Agent history 中累计 Tool Results | **Critical** | 每轮旧 Observation 继续存在 |
| Atomic Tool 往返 | **High** | 同时增加 args/result/reasoning/latency |
| 全量 traceback / logs | **High** | 一次异常即可产生大量无用上下文 |
| 大量始终可见 Tool Schemas | **High** | 工具定义本身进入 prompt/tool context |
| Agent 生成完整 bpy script | **High** | 每任务重复“编译”确定性知识 |
| Selected SKILL.md 过大 | **Medium–High** | 会进入任务 context，但通常只加载一次 |
| 过早加载全部 references | **Medium–High** | 与任务无关知识进入 context |
| 每次完整 Validation report | **Medium** | pass 信息往往没必要逐项展示 |
| Pretty-printed JSON | **Medium** | 空格和换行在高频结果中积少成多 |
| 简短 handle / revision / issue code | **Low** | 应优先保持可读与稳定 |

### 为什么 Scene Observation 通常比 Skill 更值得先优化

假设旧流程有一个大小为 `S` 的 Scene Result，并读取 `N` 次：

\[
T_{scene-old} \approx N \times S
\]

改成：

```text
每轮 Digest = D
只在 k 次需要时读取 Projection = P
```

则：

\[
T_{scene-new}
\approx
N \times D + k \times P
\]

只要：

```text
D << S
k << N
P << S
```

收益就是数量级上的。

这比：

```text
SKILL 6000 tokens → 4000 tokens
```

通常更有价值。

**[生产建议] Token 优化第一原则：**

> **优化“重复的大东西”，再优化“只出现一次的小东西”。**

### Tool Explosion 的真实成本

五种 Tool 设计可以这样比较：

| 架构 | Schema Cost | Selection | Calls | Reliability | Audit | Token Overall |
|---|---:|---:|---:|---:|---:|---:|
| Atomic Tools | 高 | 中低 | **高** | 单步高 | 高 | 中低 |
| 一个 Generic Mega Tool | 低/或 schema 巨大 | 低 | 低 | **低** | 低 | 不稳定 |
| Domain Tools | 中 | 高 | 中低 | 高 | 高 | **高效** |
| Batch Tool | 中 | 高 | **最低** | 高，若 DSL 强类型 | 高 | **非常高效** |
| Hybrid | 中 | **最高** | **低** | **最高** | **最高** | **推荐** |

纯 Atomic：

```text
create_cube
move_object
rotate_object
scale_object
apply_bevel
assign_material
```

的问题不仅是六个 Schema，而是：

```text
Call
→ Result
→ Reason
→ Call
→ Result
→ Reason
```

纯 Generic：

```text
blender.do(anything)
```

则把复杂度转移给 LLM。

生产推荐：

```text
Small Public Domain Tools
+
Typed Batch DSL
+
Versioned Recipe
+
Hidden Atomic Registry
+
Gated Python Escape Hatch
```

工具数量不应追求理论最少。

**[工程目标而非官方标准]** 可以把约 **8–15 个长期稳定、语义清晰的 public tools** 作为第一版 benchmark 起点，然后通过 eval 决定增减。真正重要的不是数字，而是：

```text
Schema 总长度
Tool 语义重叠
选择歧义
调用次数
结果大小
失败恢复复杂度
```

## Token-Efficient Blender 闭环设计

### SKILL.md 应变成 Router，而不是 Blender 百科

OpenAI 官方 Skills 设计支持按需展开资源，因此下面这种结构是合理的。citeturn12view0turn13view3

```text
blender-skill/
├── SKILL.md
├── references/
│   ├── modeling.md
│   ├── mesh-editing.md
│   ├── materials.md
│   ├── geometry-nodes.md
│   ├── lighting-camera.md
│   ├── animation.md
│   ├── rendering.md
│   ├── import-export.md
│   ├── validation.md
│   └── troubleshooting.md
├── scripts/
│   ├── validate_contracts.py
│   ├── token_audit.py
│   ├── schema_lint.py
│   └── eval_tasks.py
└── assets/
    └── optional templates / presets
```

`SKILL.md` 应只回答：

```text
什么时候用 Blender Skill？
什么时候不用？
默认工作循环是什么？
什么时候读取哪个 reference？
什么操作优先 Batch / Recipe？
什么时候必须 Validate？
什么时候允许 Python Escape？
什么条件定义任务完成？
FAST/NORMAL/DEEP/DEBUG 如何选择？
```

而不应长期写入：

```text
bpy.ops.mesh.primitive_cube_add 的所有参数
Principled BSDF 的全部属性
Geometry Nodes 教程
全部错误排查步骤
每个 Tool 的完整文档
所有建模 example
```

职责划分应为：

| 内容 | 最佳归属 |
|---|---|
| Agent workflow / escalation | `SKILL.md` |
| Blender domain knowledge | `references/` |
| 大型 examples | `references/` |
| Tool 参数约束 | MCP Schema |
| Object mode / selection management | Addon |
| Context correction | Addon |
| Dimension / topology math | Validator |
| Scene state | MCP/Add-on state |
| Stable IDs | Addon |
| Cache | Server |
| Traceback | Error store |
| Retry classification | Server |
| Mesh statistics | Addon |
| “每次必须记住的 bpy 细节” | **根本不应该告诉 LLM** |

核心原则确实应该是：

> **能通过程序保证的规则，不要每轮通过 Token 请求模型遵守。**

### Scene Digest 与 Progressive Inspection

推荐四层观察模型。

**Level 0：Scene Digest**

```json
{
  "scene": "s7",
  "rev": 42,
  "objects": 17,
  "active": "obj_3",
  "selected": ["obj_3"],
  "dirty": ["obj_3"]
}
```

**Level 1：Object Summary**

```json
{
  "id": "obj_3",
  "name": "Body",
  "type": "MESH",
  "dimensions": [2.0, 1.0, 0.5],
  "materials": ["mat_4"],
  "modifiers": ["Bevel", "WeightedNormal"]
}
```

**Level 2：Projected Detail**

```json
{
  "id": "obj_3",
  "transform": {...},
  "bounds": {...},
  "modifiers": [...],
  "mesh_stats": {
    "verts": 624,
    "edges": 1248,
    "faces": 626
  }
}
```

**Level 3：Raw / Specialized Detail**

```text
mesh topology
shader node graph
geometry nodes
UV detail
vertex groups
animation fcurves
```

Level 3 不应自动进入 Agent context。

查询：

```json
{
  "selector": {
    "ids": ["obj_3"]
  },
  "fields": [
    "dimensions",
    "bounds",
    "modifiers"
  ],
  "depth": 1,
  "limit": 20
}
```

进一步支持：

```text
fields
include
exclude
depth
limit
cursor
changed_since
```

尤其是：

```json
{
  "changed_since": 105,
  "fields": ["dimensions", "modifiers"]
}
```

会比重新读取 Scene 极其有效。

### Scene Revision 与 Semantic Diff

Blender Dependency Graph 会暴露更新的 ID，并能区分 geometry / transform 等更新类别，因此可以作为 Dirty Tracker 的基础。citeturn17search0

不过：

**不要直接把每一个 depsgraph callback 都定义成一个 LLM-visible revision。**

内部事件可能非常密集。

推荐双层模型：

```text
raw blender updates
        ↓ coalesce
dirty ID registry
        ↓
MCP transaction commit
        ↓
semantic scene_revision += 1
```

状态：

```json
{
  "scene_epoch": "scene_e9ca",
  "revision": 105
}
```

执行后：

```json
{
  "ok": true,
  "revision": 106,
  "created": ["obj_17"],
  "changed": ["obj_3"],
  "deleted": []
}
```

查询：

```json
{
  "from": 105,
  "to": 106
}
```

返回：

```json
{
  "created": ["obj_17"],
  "changed": [
    {
      "id": "obj_3",
      "fields": ["dimensions", "modifiers"]
    }
  ],
  "deleted": []
}
```

### Diff 不应该默认做 Vertex-Level Diff

这是一个重要边界。

推荐：

```text
L0 semantic diff:
    created / changed / deleted

L1:
    transform / geometry / material / modifiers

L2:
    stats / bounds / fingerprints

L3 debug:
    detailed topology diff
```

对于几何改变，只告诉模型：

```json
{
  "id": "obj_3",
  "geometry_changed": true,
  "mesh_stats_before": [624,1248,626],
  "mesh_stats_after": [680,1360,682]
}
```

往往已经足够。

而不是返回 680 个 vertex positions。

### Undo / Redo / Reload / Restart 必须纳入 Revision 模型

推荐：

```text
scene_epoch
    identifies a Scene lineage

revision
    monotonic logical change within epoch
```

发生以下情况：

```text
new file
load file
major re-index
Blender process restart
```

应该重新建立：

```text
handle index
cache
revision baseline
```

并在无法证明 Diff 完整时返回：

```json
{
  "diff_complete": false,
  "reason": "scene_reindexed"
}
```

比返回一个看似精确但错误的 Diff 更可靠。

### Stable ID / Handle

Blender 官方 `ID.session_uid` 是很好的**会话内底层身份信号**，因为它不依赖对象名称；但是官方语义是 session-wide，不能把它扩展解释为跨 Blender process 的永久 UUID。citeturn19search0

因此推荐两层：

```text
Agent Handle
    obj_17

Internal current-session mapping
    obj_17 → session_uid

Durable editable datablock identity
    custom property _agent_uuid
```

即：

```json
{
  "handle": "obj_17",
  "name": "Body",
  "persistent_id": "d7f2..."
}
```

Agent 永远用：

```text
obj_17
```

而不是：

```text
"Body"
```

名称仍作为 human-readable metadata。

Rename：

```text
obj_17 stays obj_17
Body → MainBody
```

Duplicate：

```text
obj_17
→ duplicate
→ obj_18
```

即使复制操作复制了自定义 property，Addon 也应检测 UUID collision，并立即 mint 新 durable ID。

对于 linked/read-only datablocks，无权写 custom property 时，需要额外 composite identity 策略。

同时，Undo/Redo 后不要长期保留老的 Python datablock reference；应该重新从 registry / ID 查找实际 datablock。Blender 的 Python gotchas 也长期提醒 Undo 等操作会让已有 Python references 失效或不再代表当前数据。citeturn15search1

### Batch Operation

推荐核心 mutation 形态：

```json
{
  "expected_rev": 105,
  "idempotency_key": "task12-step4",
  "on_error": "rollback",
  "operations": [
    {
      "id": "a",
      "op": "primitive.create",
      "args": {
        "type": "cube",
        "alias": "body"
      }
    },
    {
      "id": "b",
      "op": "transform.set",
      "target": "$a",
      "depends_on": ["a"],
      "args": {
        "scale": [2, 1, 0.5]
      }
    },
    {
      "id": "c",
      "op": "modifier.bevel",
      "target": "$a",
      "depends_on": ["b"],
      "args": {
        "width": 0.05,
        "segments": 3
      }
    },
    {
      "id": "d",
      "op": "material.assign",
      "target": "$a",
      "depends_on": ["a"],
      "args": {
        "material": "mat_black"
      }
    }
  ]
}
```

默认只返回：

```json
{
  "ok": true,
  "revision": 106,
  "created": {
    "a": "obj_17"
  },
  "changed": ["obj_17"]
}
```

这一步可以一次消灭：

```text
4 Tool Calls
4 Results
3~4 Agent reasoning transitions
3~4 Scene Queries
3~4 network round trips
```

### Batch Size 不应是一个固定数字

没有 OpenAI、MCP 或 Blender 官方的“最优 batch operations 数量”。

**[生产建议]** 不按数量，而按边界切分：

```text
可以同 Batch：
cheap
deterministic
same semantic phase
same rollback boundary

应拆开：
render
bake
simulation
large import
destructive remesh
complex boolean
creative inspection checkpoint
```

如果一定要给工程启动值，可以把约 **5–30 个廉价确定性 operations** 作为性能实验范围，而不是规范。

### Transaction、Rollback 和 Retry

Blender 不是数据库，因此不应宣传“真正 ACID transaction”。

推荐语义：

```text
Preflight
→ validate all handles/schema/permissions

Checkpoint
→ optional Undo marker / temporary file snapshot

Execute
→ deterministic ordered operations

Validate
→ basic postconditions

Commit revision
→ only after successful batch
```

失败时：

```json
{
  "ok": false,
  "revision": 105,
  "batch_id": "batch_92",
  "failed": "c",
  "succeeded": ["a", "b"],
  "skipped": ["d"],
  "rolled_back": true,
  "error": {
    "id": "err_42",
    "code": "E_MODIFIER_CONTEXT"
  }
}
```

`idempotency_key` 用于处理：

```text
MCP retry
network retry
Agent accidentally repeats
timeout uncertainty
```

例如服务端看到相同：

```text
(task_id, idempotency_key)
```

已经成功，就返回历史结果，而不是再生成一个 Cube。

### Server-Side Computation

这是整个设计中最重要的部分之一。

错误架构：

```text
Blender
↓
10,000 vertices
↓
LLM
↓
计算 bounding box
```

正确架构：

```text
Blender
↓
BVH / BMesh / mathutils / evaluated depsgraph
↓
{
  "dimensions":[...],
  "bbox":[...],
  "manifold":true,
  "nonmanifold_edges":0
}
```

Blender 官方提供 Mesh、BMesh、Depsgraph 等适合在数据附近处理 mesh 和 evaluated geometry 的 API。citeturn17search1turn15search3turn18search9

应下沉的典型计算包括：

| 类型 | Addon / Validator 计算 |
|---|---|
| Geometry | bbox、dimensions、centroid、surface stats |
| Mesh | verts/edges/faces、loose geometry、degenerate geometry |
| Topology | manifold / non-manifold、normal consistency |
| Spatial | distance、gap、contact、overlap、intersection |
| Layout | alignment、symmetry、containment |
| Modifiers | enabled / applied / invalid target |
| Materials | slot、missing material、missing image |
| UV | existence、coverage、overlap指标 |
| Camera | framing、clipping、target coverage |
| Lighting | light count、exposure metadata、shadow configuration |
| Export | missing assets、unsupported data、scale/origin consistency |

核心规则：

> **Compute near the data; reason near ambiguity.**

### Validation 变成机器可执行的 Truth Layer

验证不应该返回：

> “I inspected the scene. The dimensions seem slightly too large…”

而应该返回：

```json
{
  "status": "fail",
  "revision": 106,
  "issues": [
    {
      "code": "DIMENSION_X",
      "severity": "error",
      "entity": "obj_17",
      "expected": 100.0,
      "actual": 102.3,
      "delta": 2.3,
      "suggested_action": "adjust_scale_x"
    }
  ]
}
```

默认：

```text
only_failures = true
```

通过的 47 项验证可以只写：

```json
{
  "status": "fail",
  "passed": 47,
  "failed": 1,
  "issues": [...]
}
```

分级：

| Validation Mode | 内容 |
|---|---|
| `fast` | handle、object existence、transform、dimensions、basic mesh/material invariants |
| `standard` | evaluated mesh、manifold、intersection、alignment、UV/export checks |
| `visual` | preview / final image + visual interpretation |

视觉不应成为 geometry correctness 的最终事实来源。这也是 `PatrykIti/blender-ai-mcp` 第三方架构明确采取的方向：Vision 做 interpretation，measurement/assertion 做 Truth Layer。fileciteturn12file0L2-L2

### Progressive Error Disclosure

普通错误：

```json
{
  "ok": false,
  "error": {
    "id": "err_51",
    "code": "E_CONTEXT",
    "operation": "modifier.apply",
    "entity": "obj_17",
    "retryable": true,
    "hint": "object_not_active"
  }
}
```

只有：

```text
debug.inspect("err_51")
```

才返回：

```text
Python traceback
Blender mode
active object
selection
stack
internal RPC log
recent Blender messages
```

完整 traceback 放服务端 ring buffer / persistent error store。

这是典型的：

> **Progressive Error Disclosure**

而不是：

```text
每一次失败都把 200 行 traceback 永久放进上下文。
```

### Recipe / Macro

Recipe 最适合：

```text
高频
参数明确
确定性强
容易验证
容易版本化
容易测试
```

例如：

```text
camera_fit
three_point_lighting
product_render_setup
clean_mesh
prepare_export
apply_bevel_profile
optimize_scene
normalize_import
```

调用：

```json
{
  "recipe": "product_render_setup",
  "version": "2.1",
  "args": {
    "target": "obj_17",
    "preset": "studio_soft"
  }
}
```

结果：

```json
{
  "ok": true,
  "recipe": "product_render_setup@2.1",
  "revision": 132,
  "changed": ["cam_2", "light_4", "light_5", "light_6"]
}
```

不适合 Recipe 的：

```text
设计一款“更未来主义”的汽车
雕刻一个更自然的脸
决定复杂拓扑如何走线
根据概念图推断隐藏结构
```

这些仍然需要智能推理。

### Python Execute 的正确位置

生产优先级：

```text
Structured Domain Tool
        ↓
Typed Batch DSL
        ↓
Versioned Recipe
        ↓
Hidden Atomic Operation
        ↓
Python Escape Hatch
```

而不是：

```text
execute_python
        ↓
everything
```

Raw Python 的确提供最大 Blender 覆盖度，`ahujasid`、`djeada`、AuraFriday 等项目都显示了这种能力的实用性。citeturn25search4turn25search5turn25search10

但它应该是最后手段，因为：

```text
LLM 每次重新生成代码
↓
需要理解 bpy context
↓
产生大量 code tokens
↓
异常时产生 traceback
↓
难做 semantic retry
↓
难做 idempotency
↓
难审计
↓
安全边界更宽
```

对于真正 arbitrary Python，**不要把 Python 级“sandbox”当成强隔离**。更安全的方案通常是受限文件/网络能力，或者在独立 headless Blender process / OS sandbox 中运行高风险任务。Blender 官方也建议需要独立 Python 工作时优先考虑独立进程，而不是不安全的持续后台线程。citeturn25search0

### Agent State 不应该主要存在聊天历史

推荐 canonical state：

```json
{
  "task_id": "task_12",
  "goal": "product_model",
  "scene_epoch": "s7",
  "scene_revision": 52,
  "working_objects": [
    "obj_3",
    "obj_7"
  ],
  "completed": [
    "base_geometry",
    "materials"
  ],
  "pending": [
    "lighting",
    "render"
  ],
  "validation_profile": "standard",
  "checkpoints": [48, 52]
}
```

比较五个位置：

| State Location | 适合程度 |
|---|---|
| Conversation Context | **低**：昂贵、会 compact、需要重新推断 |
| MCP transport session memory | 中低：连接重启脆弱 |
| Blender Custom Properties | 中：适合 Scene linkage，不适合全部工作流状态 |
| JSON Task Manifest | 高：简单、可审计 |
| SQLite / Local DB | **最高**：复杂任务、历史、cache、idempotency、jobs |

推荐：

```text
SQLite / durable manifest
        =
canonical task state

Blender custom props
        =
task linkage + persistent entity IDs

Conversation
        =
temporary reasoning only
```

这也符合 MCP 新一代 stateless protocol 的方向：协议本身可以 stateless，但 application 仍可以持有状态，而且状态应由显式 handles / request state 表达，而不是依赖隐式连接。citeturn25search3

### Render / Vision Token 分层

推荐：

```text
Geometry Validation
        ↓
Scene Validation
        ↓
Cheap Viewport Preview
        ↓
Milestone Visual Check
        ↓
Final Render
        ↓
Final Visual Validation
```

而不是：

```text
every modification
        ↓
render
        ↓
vision
```

建议行为：

| 阶段 | 默认行为 |
|---|---|
| primitive / transform | 不 Render |
| modifier / mesh edit | geometry validator |
| material creation | material metadata first |
| lighting phase | preview |
| camera phase | viewport / framing analysis |
| major modeling milestone | optional preview |
| final | final render + visual check |

Render Tool 默认返回：

```json
{
  "ok": true,
  "render_id": "render_8",
  "mode": "preview",
  "revision": 140,
  "artifact_uri": "blender://render/render_8"
}
```

而不是无条件把完整图像塞回模型。

## 推荐 MCP API、数据契约与 Token Budget

### 推荐公开 Tool Surface

**[生产建议]** 我不建议直接采用你问题中列出的所有名称，也不建议只剩一个 `blender.execute`。

建议 public surface 约为：

```text
scene.summary
scene.query
scene.diff
scene.apply
recipe.run
validate.run
render.run
asset.transfer
capability.search
job.control
debug.inspect
python.exec
```

其中 `python.exec` 默认可能在 production profile 隐藏。

核心不是 12 这个数字，而是：

> Public surface 保持稳定、低歧义；内部能力可以远多于公开工具。

### 核心 API 设计

| Tool | Purpose / Input Schema 摘要 | Default Minimal Output | Detailed Output | Error | Token Cost / 场景 |
|---|---|---|---|---|---|
| `scene.summary` | `detail?`, `changed_since?` | epoch/rev/object count/active/dirty | collection/type counts | standard compact error | **Very Low**；每轮可用 |
| `scene.query` | `selector`, `fields`, `include/exclude`, `depth`, `limit`, `cursor` | projected requested fields | detail resource | query issue code | **Low→High 可控** |
| `scene.diff` | `from_rev`, `to_rev`, `detail?` | created/changed/deleted | semantic fields/fingerprint delta | revision unavailable | **Low** |
| `scene.apply` | `expected_rev`, `idempotency_key`, typed `operations[]`, `on_error` | ok/rev/created/changed | per-op report URI | batch error structure | **Low per operation** |
| `recipe.run` | `name`, `version?`, `args`, `expected_rev` | recipe/rev/changed | execution + validation report | recipe code | **Very Low** for repetitive work |
| `validate.run` | `profile`, `selector`, `checks?`, `only_failures` | status/count/issues | full check resource | validator error | **Low–Medium** |
| `render.run` | `mode=preview\|final`, camera/region/profile | render_id/artifact | image metadata/result | render error/job | **High only when requested** |
| `asset.transfer` | `action=import\|export`, format, URI/path, profile | asset/job/rev | diagnostics | asset code | Medium |
| `capability.search` | `query`, `domain?`, `limit` | capability IDs + concise signatures | schema/resource | discovery error | Low；访问长尾能力 |
| `job.control` | `action=get\|cancel`, `job_id` | state/progress | result/error URI | job error | Very Low |
| `debug.inspect` | `error_id/job_id`, `fields?` | selected debug fields | traceback/logs/context | debug code | **High，仅 DEBUG** |
| `python.exec` | `code`, `timeout`, `scope`, policy credential | status/result handle | stdout/stderr/debug URI | Python error ID | **Very High；Escape only** |

MCP 2026 演进中支持更完整的 JSON Schema 2020-12 表达，因此 Batch DSL 可以采用 discriminated union，而不是一个完全无类型的 `{op, args:any}`。citeturn25search3

例如：

```json
{
  "oneOf": [
    {
      "properties": {
        "op": {"const": "transform.set"},
        "target": {"type": "string"},
        "location": {
          "type": "array",
          "prefixItems": [
            {"type": "number"},
            {"type": "number"},
            {"type": "number"}
          ]
        }
      }
    },
    {
      "properties": {
        "op": {"const": "modifier.bevel"},
        "target": {"type": "string"},
        "width": {"type": "number"},
        "segments": {"type": "integer"}
      }
    }
  ]
}
```

这样：

```text
Structured
但不是 Atomic Tool Explosion
```

### 不应该用一个无限大的 Batch Schema

如果 `scene.apply` 的 schema 内部塞入：

```text
200 kinds of operations
×
20 parameters each
```

那只是把 Tool Explosion 搬进一个 JSON Schema。

更好的三级结构：

```text
Public Batch DSL
    10~20 高频 primitive operations

Recipes / Macro
    常用高层流程

capability.search
    长尾操作 registry
```

对于内部 registry：

```json
{
  "query": "curve bevel geometry nodes"
}
```

返回：

```json
{
  "matches": [
    {
      "id": "geo.curve_bevel",
      "summary": "Apply curve bevel profile",
      "args": ["target", "depth", "resolution"]
    }
  ]
}
```

只有选中后才获取更完整参数契约。

### Resource URI 设计

推荐：

```text
blender://scene/{epoch}/summary
blender://scene/{epoch}/rev/{rev}
blender://scene/{epoch}/diff/{from}/{to}

blender://object/{handle}/summary
blender://object/{handle}/mesh/stats
blender://object/{handle}/material
blender://object/{handle}/nodes

blender://validation/{validation_id}
blender://render/{render_id}
blender://task/{task_id}
blender://debug/{error_id}
```

这些自定义 URI 与 MCP Resource 模型相容。citeturn14view0turn21search3

但大型 Mesh 不应：

```text
blender://object/obj_17
→ automatically return everything
```

应该：

```text
blender://object/obj_17/mesh/stats
blender://object/obj_17/mesh/issues
```

需要 Raw 数据时才：

```text
.../mesh/raw?segment=...
```

### Token Budget 模式

推荐 Skill / MCP 共用一个显式 budget profile：

| Mode | Scene Detail | References | Validation | Render | Result | Error |
|---|---|---|---|---|---|---|
| **FAST** | L0–L1 | 不主动加载 | fast | none | minimal | compact |
| **NORMAL** | L1–L2 projection | 当前领域 | standard | milestone only | minimal | compact |
| **DEEP** | L2 / selective L3 | 多领域按需 | standard + expensive checks | milestone | detailed on request | medium |
| **DEBUG** | explicit raw | troubleshooting | diagnostic | as required | verbose | traceback/log |

自动选择可以基于：

```text
task complexity
operation risk
current validation failures
uncertainty
number of affected objects
render/bake presence
```

默认：

```text
simple edit
→ FAST

general modeling
→ NORMAL

complex hard surface / topology
→ DEEP

repeated errors
→ DEBUG
```

关键是：

> **升级是单向按需发生的，而不是一开始所有任务都 DEBUG。**

### Tool Result 统一 Envelope

所有 Tools 最好共享：

```json
{
  "ok": true,
  "revision": 106,
  "result": {},
  "detail_uri": null,
  "warnings": []
}
```

失败：

```json
{
  "ok": false,
  "revision": 105,
  "error": {
    "id": "err_92",
    "code": "E_REVISION_CONFLICT",
    "retryable": true,
    "entity": "obj_17",
    "hint": "refresh_scene_digest"
  }
}
```

这样 Agent 不需要学习：

```text
Tool A 错误叫 message
Tool B 错误叫 exception
Tool C 返回 success:false
Tool D 抛 MCP exception
```

错误一致性本身会减少重复推理。

### Optimistic Revision Control

这是提升可靠性的关键。

Agent 读取：

```json
{
  "revision": 105
}
```

然后调用：

```json
{
  "expected_rev": 105,
  "operations": [...]
}
```

如果用户手动在 Blender 中改了 Scene：

```text
revision = 106
```

Server 不盲执行，而返回：

```json
{
  "ok": false,
  "error": {
    "code": "E_REVISION_CONFLICT",
    "expected": 105,
    "actual": 106
  }
}
```

Agent 只读取：

```text
scene.diff(105,106)
```

再决定是否继续。

这比：

```text
每次 action 前 get_scene_info()
```

同时更省 Token、更安全。

### Cache 设计

推荐 cache key：

```text
(
  scene_epoch,
  revision,
  entity_handle,
  projection_hash
)
```

例如：

```text
rev 52
obj_17
fields = dimensions,bounds,modifiers
```

结果缓存后，只要：

```text
obj_17 not dirty
revision dependency unchanged
```

无需重新进行重计算。

特别适合：

```text
mesh stats
material graph summary
UV stats
bounding boxes
export checks
camera visibility
```

注意 MCP 2026 规范演进中的 `ttlMs` / `cacheScope` 属于协议层缓存提示，不应与 Blender 自己的 revision-aware Scene Cache 或 OpenAI Prompt Cache 混为一谈。citeturn25search3

三者应分别理解：

```text
OpenAI Prompt Cache
    model request prefix reuse

MCP Cache Hints
    protocol/client resource/list caching

Blender Scene Cache
    domain computation reuse
```

### Main-Thread Addon Execution Layer

推荐：

```text
MCP Server
     ↓
request_id / task_id
     ↓
Socket / HTTP Listener
     ↓
Thread-safe queue
     ↓
Blender controlled/main-thread dispatcher
     ↓
Command Handler
     ↓
bpy / BMesh
```

严禁形成：

```text
random TCP worker thread
→ arbitrary bpy mutation
```

因为 Blender 官方明确没有提供一般意义上的 thread-safe Python integration。citeturn25search0

### 对现有代码最小改造的职责迁移表

在没有你的实际源码情况下，以下是最值得逐项检查的审计表：

| 当前实现若存在 | Token / Reliability Smell | 最小改法 |
|---|---|---|
| `get_scene_info()` 每步调用 | **Critical** | 保留旧 API，新增 `scene.summary/query` |
| Result `json.dumps(..., indent=2)` | 高频无价值 token | 改 compact JSON / structured output |
| Action 后自动返回 Scene | **Critical** | 只返回 rev + changed IDs |
| 每个 bpy op 一个 Tool | Tool + roundtrip explosion | 兼容保留，增加 Batch facade |
| Agent 依赖名称 `"Cube"` | rename 脆弱 | 内部增加 handle registry |
| 无 revision | 必须反复 read | 增加 epoch + revision |
| Tool 自动返回 traceback | Context pollution | error_id + debug.inspect |
| 每次 render | Vision explosion | render tiers |
| Validation 在 prompt 中 | 每次由 LLM 重算 | Addon validator |
| Tool 文档复制到 SKILL | 重复 | Skill 只保留 routing |
| 所有 refs 自动读取 | Progressive disclosure 失效 | domain trigger |
| task progress 写在聊天 | compaction 后丢失 | manifest / SQLite |
| raw Python 为主 | code/retry/security cost | 增加 structured fast path |
| TCP bridge 已稳定 | 无必要重写 | **不要为了架构美观更换 transport** |
| 无测试 Token 指标 | 优化不可验证 | 加 telemetry + eval harness |

最后一行非常重要：

> **先测量，再重构。**

否则很容易把 30% 开发时间花在缩 `SKILL.md`，而真正 80% Token 都在 Scene Result。

## 迁移路线、测试体系与最终生产方案

### 最低风险迁移顺序

不要先重写 Blender bridge。

如果你现有的：

```text
Codex
→ MCP
→ TCP
→ Blender Addon
```

已经可靠，就保留。

第一轮只改**数据契约**。

推荐演进：

```text
Existing Tools
      │
      ├── compatibility adapters
      │
      ↓
New compact facade

scene.summary
scene.query
scene.apply
validate.run
```

内部仍然调用你现有的 handler。

这样不会为了“Token Architecture”重写几十个已经验证的 bpy 操作。

### 基础观测阶段

首先埋点：

```text
input tokens
cached input tokens
skill bytes/tokens loaded
reference documents loaded
tool definitions bytes/tokens
tool call args bytes/tokens
tool result bytes/tokens
scene result bytes
error bytes
image count
tool call count
Blender round trips
retries
wall time
validation success
Python escape usage
compaction count
```

否则无法知道：

```text
Tool Schema
还是 Scene JSON
还是 History
```

究竟谁最贵。

### 第一批几乎无风险优化

最先实施：

```text
pretty JSON → compact structured JSON
full traceback → error ID
action result → revision + changed handles
stop automatic full scene echo
stable MCP tool order
remove duplicated Skill/Tool descriptions
lazy references
```

这组优化对建模能力几乎没有负面影响，却通常立刻减少输出和历史 Token。

### 第二批核心状态能力

然后增加：

```text
scene_epoch
scene_revision
stable handles
dirty tracker
scene.summary
scene.query projection
scene.diff
```

这是整个系统真正从：

> stateless chat-driven Blender automation

进入：

> state-aware agent runtime

的分水岭。

### 第三批执行能力

增加：

```text
scene.apply batch
idempotency
expected_rev
preflight
checkpoint
rollback semantics
```

保留旧 Atomic Tools 作为内部 handler。

不要立刻删除旧工具，先让：

```text
new API
→ adapter
→ existing implementation
```

运行。

### 第四批确定性智能下沉

实现：

```text
geometry.stats
measurements
alignment
intersection
manifold
material checks
export checks
camera fit
```

统一挂到：

```text
validate.run
```

此时 Agent 的职责从：

```text
读 Scene → 自己算 → 猜是否正确
```

变为：

```text
定义目标
→ 调 validator
→ 处理失败项
```

### 第五批 Recipe 与 Visual Budget

只有高频 workflow 已经通过真实 task logs 证明反复出现后，才把它 Recipe 化。

否则容易把所有“可能出现的工作流”提前做成 200 个 macro，重新制造 Tool / Recipe Explosion。

视觉验证则改成：

```text
cheap deterministic first
visual only on ambiguity or milestone
```

### 测试集必须覆盖的不只是“能不能创建 Cube”

真正的 regression suite 应覆盖：

| Eval | 测试重点 |
|---|---|
| 简单 transform | FAST 模式 Token |
| 10–30 步产品建模 | Batch / revision |
| hard-surface modifier chain | handle / validator |
| material + lighting | domain references |
| Geometry Nodes | projected node inspection |
| imported dirty mesh | server-side geometry compute |
| UV + export | validator |
| long render / bake | job/task state |
| manual user edit during Agent run | revision conflict |
| rename | Stable ID |
| duplicate | Stable ID uniqueness |
| undo / redo | registry re-resolution |
| save / reopen | persistent ID |
| Blender restart | scene epoch |
| Tool timeout | idempotency |
| malformed batch | rollback |
| Python exception | progressive debug |
| final image quality | visual validation |

### KPI 不应只看 Token

真正生产验收应该同时看：

```text
Total input tokens / task
Total output tokens / task
Tool-schema tokens
Tool-result tokens
Vision inputs
Number of Blender round trips
Number of scene reads
Retry rate
Wrong-tool-selection rate
Python escape rate
p50 / p95 wall time
Validation success rate
Rollback success rate
Task completion rate
Final geometric correctness
Final visual quality
```

必须使用：

```text
same model
same reasoning configuration
same user tasks
same Blender version
same base scenes
```

做 A/B。

否则“Token 下降 60%”可能只是因为新 Agent 少做了验证，最终正确率下降。

### 推荐的最终 Skill / MCP / Addon 分工

最终架构可以收敛为：

```text
User
  ↓
Codex
  │
  │  only:
  │  intent / ambiguity / creative reasoning
  │
  ↓
SKILL.md
  │
  ├── route task
  ├── choose budget
  ├── choose references
  └── define validation strategy
  ↓
MCP Public Surface
  │
  ├── scene.summary
  ├── scene.query
  ├── scene.diff
  ├── scene.apply
  ├── recipe.run
  ├── validate.run
  ├── render.run
  ├── asset.transfer
  ├── capability.search
  └── debug.inspect
  ↓
MCP Control Plane
  │
  ├── Task Manifest
  ├── Operation Registry
  ├── Idempotency Store
  ├── Cache
  ├── Error Store
  ├── Resource Registry
  └── Job Manager
  ↓
Blender Addon
  │
  ├── Main-thread Executor
  ├── Context Manager
  ├── Stable Handle Registry
  ├── Revision / Dirty Tracker
  ├── Semantic Diff
  ├── Query Projection
  ├── Batch Engine
  ├── Recipe Engine
  ├── Geometry Compute
  ├── Validator
  └── Render Artifact Manager
  ↓
bpy / BMesh / Depsgraph
  ↓
Scene
  ↓
Minimal Observation
```

### 最终责任矩阵

| 工作 | LLM | Skill | MCP | Addon |
|---|---:|---:|---:|---:|
| 理解“做什么” | **✓** | route |  |  |
| 创意形状判断 | **✓** |  |  |  |
| Tool routing rules |  | **✓** |  |  |
| reference selection |  | **✓** |  |  |
| Scene canonical state |  |  | **✓** | **✓** |
| Stable ID |  |  | registry | **✓** |
| revision/diff |  |  | contract | **✓** |
| geometry calculations |  |  | API | **✓** |
| selection/mode/context |  |  |  | **✓** |
| cache |  |  | **✓** | optional |
| Batch | plan only | policy | **✓** | **✓** |
| Recipe | choose | policy | **✓** | **✓** |
| Validation | decide criteria | policy | API | **✓** |
| Retry classification | high-level |  | **✓** | error data |
| traceback storage |  |  | **✓** | raw source |
| Render frequency | judgment | **✓** | orchestration | execute |
| raw Python | exceptional reasoning | policy | gate | execute |

### 最终判定

本研究最核心的生产结论不是：

> “把 SKILL.md 缩短。”

而是：

> **把 LLM 从 Blender Runtime 的数据库、计算器、状态机、日志分析器、Validator 和脚本解释器，重新变回“负责不确定性和高层决策的智能层”。**

OpenAI 当前 Skills / AGENTS / compaction 设计支持把知识做 progressive disclosure，而 Codex Agent Loop 对 Prompt Caching 的实现又进一步说明：**长期可见内容应该小而稳定，而不是每轮动态膨胀或修改工具前缀。** citeturn12view0turn13view1turn11search0

MCP 官方的 Tool / Resource 分工为“动作与大型按需状态分离”提供了协议基础，但 Resource 是否真正 lazy 地进入 Codex Context 取决于 Host，因此生产环境必须保留 projected query / detail fallback，而不能把 Resource 当成自动 Token 优化魔法。citeturn14view0turn14view1turn24view0

Blender 官方的 `depsgraph`、`ID.session_uid`、Mesh/BMesh 与 evaluated geometry 则足以支持把 Scene identity、dirty tracking、geometry statistics 和大量验证下沉到 Addon；同时 Blender Python 非 thread-safe 的官方约束意味着 execution layer 必须明确控制 bpy 执行线程，而不是让 MCP 网络线程直接自由修改 Scene。citeturn17search0turn19search0turn17search1turn15search3turn25search0

因此，推荐的优化顺序应固定为：

```text
Full Scene / Raw Geometry / Vision
            ↓
Observation Result Size
            ↓
Atomic Round Trips
            ↓
Batch + Revision + Stable Handles
            ↓
Server-Side Computation
            ↓
Validation + Error Progressive Disclosure
            ↓
Task State / Cache / Diff
            ↓
Recipe
            ↓
Tool Surface
            ↓
SKILL.md / References Fine-Tuning
```

而最终生产形态应是：

```text
LLM Context
=
Intent
+ Minimal Scene Digest
+ Current Task State
+ Relevant Reference
+ Failed Validation Issues
+ Necessary Visual Evidence

NOT

Intent
+ Entire Blender Scene
+ Entire Skill Manual
+ 100 Tool Schemas
+ 10,000 Vertices
+ Every Previous Observation
+ Every Python Script
+ Every Traceback
+ Every Render
```

这才是让 Blender Agent 在长任务中同时获得**更低 Token、较少往返、更强确定性、更好的可恢复性和更高维护性**的根本架构方向。
