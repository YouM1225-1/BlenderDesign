# BlenderDesign 全量对抗性复审（文档与 Plan 修订后）

> **SUPERSEDED（2026-08-08）**：本文件记录修复前阻断项；当前裁决见 [closeout v3](2026-08-07-closeout-v3.md) 与 [r15/v8 融合审计](2026-08-07-platform-optimization-handoff-adversarial-audit.md)。

> **历史快照（修复前）**：本报告记录的是 `578f49e` 基线上一轮修复前状态，其中“不得执行”、10 工具 allowlist 与 Gate 未关闭等裁决已被后续修复和实测取代。当前结论以 [2026-08-07-closeout-v2.md](2026-08-07-closeout-v2.md) 为准；以下历史证据不回写、不篡改。

> 日期：2026-08-07
> 审计对象：当前工作树中的 URS、Phase 0 design spec、Phase 0 plan、研究输入、既有审计、SDK 决策、spikes、官方 Blender MCP 与 Codex 配置
> Git 基线：`578f49e`
> 边界：只审计、隔离重建和实测；未执行或修改工作区中的 Phase 0 plan

## 1. 裁决

当前 Phase 0 plan **不得执行**。修订方向大体正确，SDK v2 决策继续成立，socket ownership 修复也通过；但“全部 Gate 已关闭”的结论不成立。

本轮发现 6 项 P0 阻断：

1. Discovery 的目录枚举与 `session.json` 读取仍可突破或永久绕过总 deadline；
2. `get_blender_status` 没有共享整体 3 秒 deadline；
3. 三个 MCP 工具都没有 `outputSchema`，输入 schema 也未封闭，未知参数被静默接受；
4. 所谓 2026-07-28 合同测试实际走旧协议并允许静默降级；
5. spec 声称的真 Blender hash 盲区 fixture 并未进入 L3 runner；
6. Task 0 仍包含 SDK v1 遗留命令，在 SDK v2 环境会直接失败。

Gate 应改判为：

| Gate | 当前裁决 | 原因 |
|---|---|---|
| G0 Git 基线 | 关闭 | `f81ee3c`、`578f49e` 存在 |
| G1 官方 MCP 重评 | 关闭 | Build + 行为借鉴结论仍合理 |
| G2 SDK 路线 | **决策关闭、实施未关闭** | v2 选择正确；plan 的 schema、合同测试、Task 0 未迁完 |
| G3 scene hash 语义 | **未关闭** | 文档仍自相矛盾，L3 fixture 缺失 |
| G4 总 deadline | **未关闭** | Discovery 4.803 s；status 4.508 s；FIFO 可无限阻塞 |
| G5 官方 MCP 并存配置 | **部分关闭** | 持久配置正确，但当前桌面宿主仍运行旧启动命令，需重启后复核 |

## 2. 当前工作树与方法

相对 `578f49e`，只有以下三份既有文档被修改；本报告之外未改它们：

| 文件 | 变更 | 当前 SHA-256 |
|---|---:|---|
| `Blender-Codex-需求规格说明书-v1.md` | +42 / -12 | `572d057029b5011cd71b2c40160589d06eac28f10b514d3a637aa71d28e6c99b` |
| Phase 0 spec | +17 / -7 | `ae635863588791e69c01221947d684f3e66274d4c547e74e65c51b2e4a54f959` |
| Phase 0 plan | +416 / -170 | `064c0185cca4553de27077195461048508e5f4b0656079cbb202546a15a2a540` |

证据分级：

| 等级 | 含义 |
|---|---|
| E1 | 当前机器上的真实 Codex / Blender / MCP 进程实测 |
| E2 | `/tmp/blender-plan-full-reaudit.ECoOGz/repo` 隔离重建与对抗输入 |
| E3 | 当前文档、plan 代码块与固定 commit 源码检查 |
| E4 | OpenAI、Blender、MCP SDK 官方资料 |

隔离副本是在上轮完整重建的 91-test 副本上机械应用本轮新增/替换代码块，不属于工作区，也不是 Phase 0 实施产物。

## 3. 正向结果

### 3.1 当前 plan 隔离重建

| 检查 | 结果 |
|---|---|
| Python / MCP SDK | Python 3.13.14 / `mcp==2.0.0` |
| pytest | `97 passed in 11.89s`（完整 `checks.sh` 复跑同样 97 passed） |
| ruff | 通过 |
| mypy strict | 19 个源文件通过 |
| vendoring / nested import | 通过 |
| `scripts/checks.sh` | 受控 PATH 后 `ALL CHECKS PASSED` |
| socket bind 冲突保留外部 socket | 通过 |

这证明大部分代码块可以组合和运行，但不证明承重保证成立。

### 3.2 SDK v2 与 Codex

同一组三工具在以下路径全部完成发现与调用：

| 路径 | 结果 |
|---|---|
| SDK v2 in-memory Client | 通过 |
| SDK v2 stdio Client | 通过 |
| Codex + `mcp_2026_07_28` | 通过 |
| Codex 默认旧协议 | 通过 |

当前 Codex 为 `0.147.0-alpha.6.5`；`mcp_2026_07_28` 仍显示 `under development / false`。因此自定义 Server 采用 SDK v2、客户端暂用旧协议的决策仍是最优路径。

### 3.3 Blender Lab 官方 MCP

| 项 | 当前实测 |
|---|---|
| 上游 HEAD | `4309a39646e644261624bfcd2bca669b343b7621` |
| 完整工具面 | 26 个 |
| Codex allowlist | 10 个只读摘要/文档工具 |
| CLI SDK | 1.29.0（显式 `<2`） |
| CLI 代表工具 | path info、datablocks、只读 Python 三项通过 |
| Blender | 5.2.0 LTS |

官方页面仍明确警告其会在无保护的情况下执行 LLM 生成代码。维持“官方只作行为参考，不作为安全控制底座”的 D-4 合理。

## 4. P0 阻断发现

### F-01 Discovery 总 deadline 仍可被目录枚举和特殊文件击穿

Plan 在 `_scan()` 入口创建 deadline，但随后执行：

```python
for d in sorted(self._run.iterdir()):
```

`sorted()` 会先完整消费并排序全部目录项，循环体中的 deadline 检查尚未开始。达到 16 个候选后代码也只是 `continue`，仍遍历所有剩余项。

对抗输入：400 个目录项，每次迭代延迟 10 ms。

```text
{'entries': 400, 'elapsed_seconds': 4.803,
 'claimed_budget_seconds': 2.5, 'returned': 1}
```

第二个反例把 `session.json` 设为 FIFO。`stat().st_size == 0` 通过 64 KiB 检查，随后 `read_text()` 永久等待 writer；monotonic deadline 无法中断同步文件读取：

```text
{'returned_within_1s': False, 'session_kind': 'fifo',
 'claimed_budget_seconds': 2.5}
```

影响：spec §4.3 的“遍历、stat、读取、解析、排序和 probe 全部受 2.5 s 限制”仍不成立，G4 必须重开。

修正门槛：惰性 `os.scandir()`；预算/候选耗尽立即 `break`；对 session 文件做 `lstat`、regular-file、no-symlink、fd-based、有界读取；FIFO/device/symlink 必须拒绝。同步本地文件系统无法提供严格 I/O deadline 时，文档应诚实限定保证边界，而不是声称绝对总 deadline。

### F-02 `get_blender_status` 把 2.5 s discovery 与 3 s 聚合串联

Spec 要求“扫描 2.5 s + 聚合 0.5 s = 整体 3 s”，实现却先同步调用 `discovery.instances()`，随后重新给 `as_completed()` 一个完整 3 秒窗口。

对抗输入：discovery 2.5 s，单个 status 2.0 s。

```text
{'elapsed_seconds': 4.508,
 'claimed_overall_seconds': 3.0, 'rows': 1}
```

修正门槛：在 `status_impl` 入口创建唯一 absolute deadline，并把同一剩余预算传给 discovery、probe、status 聚合；增加端到端计时测试，不能分别测试两个局部 timeout。

### F-03 MCP schema 与结构化结果不符合 spec/URS

Spec §6 为三个工具定义了封闭 `inputSchema` 和正式 `outputSchema`；URS Phase 0 第一项也要求结果符合 outputSchema。当前 plan 的工具函数使用裸 `-> dict`。

SDK v2 `tools/list` 实测：

```text
get_blender_status: outputSchema=null
get_scene_summary: outputSchema=null
describe_capabilities: outputSchema=null
```

实际 input schema 也没有 `additionalProperties: false`。给 `get_blender_status` 和 `describe_capabilities` 传 `{"unexpected": 1}`，两次均成功，未知参数被静默忽略。两次调用的 `structured_content` 也都是 `None`，仅有 text content。

这同时否定了 plan G2 的“structuredContent 全部正常”在本实现上的适用性：该证据来自 spike，不是 Task 12 adapter。

修正门槛：为输入和输出建立明确模型（例如 Pydantic/TypedDict，输入 `extra='forbid'`），并在 `tools/list` 中断言三工具的 schema、required、`additionalProperties`；`tools/call` 同时断言 `structuredContent` 与 schema 一致。不能只断言 Python dict 的内部形状。

### F-04 2026-07-28 合同测试是静默降级的假阳性

URS 自己说明 2026-07-28 已移除 `initialize`，新增 `server/discover`。Plan 却对两个版本都发送 legacy `initialize`，并接受协商结果是请求版本、旧版本或新版本中的任意一个：

```python
assert negotiated in (protocol, LEGACY_PROTOCOL, CURRENT_PROTOCOL)
```

实测请求 `2026-07-28` 时：

```text
{'requested': '2026-07-28',
 'negotiated': '2025-11-25',
 'has_initialize_result': True}
```

测试仍通过，因此它只证明旧协议 fallback 可用，不证明 2026-07-28 wire path 可用。

修正门槛：旧协议测试保留 `initialize` 并精确断言协商旧版本；新协议测试必须走 SDK v2 Client 或真实 `server/discover`/无握手路径，并拒绝静默降级。两条测试不得共享 `_init()`。

### F-05 scene hash 的 L3 真实盲区证明仍未实现

Spec §7.3 声称 L3 会证明“移动顶点 hash 不变，移动对象 hash 改变”；plan 自审也声称已落实。实际 runner 只新增一个 Cube，然后检查对象数、hash 前缀和 revision，没有进入编辑模式、移动顶点或比较前后 hash。

L1 的 `test_same_counts_different_topology_collide_by_design` 仍为 `before`/`after` 构造完全相同的参数；“different topology”只存在于测试名和注释中。

影响：G3 没有获得 plan 所声称的真 Blender 证据，spec 的“共同证明”陈述不实。

修正门槛：L3 runner 保存初始 hash，编辑模式移动顶点后断言 hash 不变，再做 object transform 后断言 hash 改变；结果 JSON 增独立 `hash_scope` 字段，必须进入 `_finish()` 的成功判据。

### F-06 Task 0 的 SDK v2 迁移未完成

Task 0 已把依赖改为 `mcp>=2.0,<3`，但仍要求：

```bash
uv run python -c "import mcp; print(mcp.__version__)"
```

SDK v2 实测直接失败：

```text
AttributeError: module 'mcp' has no attribute '__version__'
```

同一任务的预期输出和 commit message 仍写 1.28.x；文件结构、Task 12 说明和 Task 17 备注仍残留 `FastMCP`。此外 ADR 要求 CI `uv sync --frozen`，plan 的检查脚本和安装文档仍只用普通 `uv run` / `uv sync`。

修正门槛：版本检查使用 `importlib.metadata.version('mcp')`；清除所有自定义 Server 的 v1/FastMCP 残留；生成并提交 `uv.lock` 后，CI/检查统一使用 frozen 模式；Task 0 禁止 `git add -A`，只暂存该任务明确产物。

## 5. P1 高优先级发现

### F-07 `describe_capabilities` 并非本地回答

Spec 写明它“不经 Bridge”且无需 Blender 在线。实现却调用 `discovery.instances()`，会扫描并 ping Bridge。挂起 listener 下实测耗时 2.003 s，返回零连接实例。

静态能力必须与动态实例状态解耦；若需要连接列表，应由可选、显式且有预算的字段或另一个工具提供。

### F-08 候选上限会饿死最新的真实实例

新实现按目录名排序后取前 16 个，不再按 mtime 选最新。构造 16 个字典序靠前的 stale 目录和 1 个字典序靠后的最新活实例：

```text
{'live_discovered': False, 'returned': 17, 'has_partial': True}
```

`__partial__` 只说明截断，不能弥补真实活实例不可发现。需要明确、可验证的选择策略和公平性边界。

### F-09 文档版本与 hash 语义仍自相矛盾

- URS 头部写 v1.2，spec 声称上游是 v1.3，URS 变更记录已存在 v1.3；
- spec 连续写“不对整个场景敏感”和“对整个场景敏感”；
- URS FR-11 仍写 `scene_hash` 对全场景敏感；
- URS “不在本版范围”仍列 2026-07-28 适配，但 G2/SDK 决策文字容易让读者误以为协议适配已完成；
- v1.3 记录声称环境没有 Codex CLI，当前实际为 `0.147.0-alpha.6.5` 且两条 app-server 路径已复测通过。

### F-10 幂等与回滚验收仍依赖不完整 `scene_hash`

URS 已承认结构 hash 看不到顶点、modifier、材质等，但 FR-12 仍把它用于幂等键。若幂等查询早于 `plan_scope_hash` 冲突校验，顶点编辑后重放可能被误判为已完成调用并返回旧结果。执行顺序没有定义。

Phase 1 的“hard 回滚后场景 hash 与快照一致”也不能证明完整场景恢复。应明确使用文件内容 hash、版本化完整 fingerprint 或逐类状态断言；幂等检查必须晚于冲突/预条件校验，或直接绑定 `plan_scope_hash`。

### F-11 当前 Codex 桌面宿主仍运行旧官方 MCP 启动命令

磁盘配置已经是 `uv --no-project --with-editable ... <2`，但进程列表显示当前桌面宿主仍运行：

```text
uv --directory /Users/yeminjie/blender_mcp/mcp run --with mcp[cli]>=1.2.0,<2 blender-mcp
```

该旧进程在官方 checkout 重新生成了未跟踪、锁到 `mcp==2.0.0` 的 `mcp/uv.lock`。文件已移到 `/tmp/blender-mcp-uv.lock.full-reaudit.20260807`；受控执行新命令没有重建 lock。

OpenAI Docs 明确要求保存 MCP 配置后重启客户端。G5 只能在重启当前 Codex 桌面宿主、确认进程命令更新且 checkout 继续 clean 后关闭。

### F-12 子进程测试自己的 deadline 也不可靠

`_read_until()` 先检查 monotonic deadline，随后调用阻塞 `readline()`；若 Server 不输出，代码不会回到循环检查 deadline，只能等 pytest 的 30 秒全局 timeout。冷启动计时也在 fixture 已 `Popen` 之后才开始，存在漏计进程启动阶段的窗口。

应用 selector/非阻塞读取，并在 `Popen` 前记录起点。

## 6. P2 一致性与可维护性

| 问题 | 证据 |
|---|---|
| `__partial__` 被伪装成普通 `Instance` | status 返回一个 ID 为 `__partial__` 的假 Blender 实例，而不是顶层 `partial/skipped_count` 元数据 |
| Plan 自审编号倒序 | 1、2、3、4、8、7、6、5 |
| 风险编号顺序异常 | R-08 插在 R-05 与 R-06 之间 |
| `.gitignore` 核对会重复四条规则 | 缺 `bridge/_vendor/` 时追加整组五行，而非只补缺失项 |
| 外部研究报告仍含滚动模型断言 | 已明确标为非规范输入且链接到既有审计，因此不作为阻断项 |
| 链接可达性 | 修改文档的大部分外链为 200；3 个 MCP blog URL 在当前网络被 reset，Blender T33108 返回 403，需用可抓取的官方替代来源或保留“未自动验证”标记 |

## 7. 复杂度审计（ponytail）

stdlib: 删除 `_audited()` 内每次动态定义的 `_Ctx` 类，改用 `contextlib.contextmanager`。`contextlib.contextmanager`。[`docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`:2800]

shrink: Task 0 已有 `.gitignore`，删除“缺一项就追加整组五行”的分支；改为只断言或只追加 `bridge/_vendor/` 一行。[`docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`:123]

net: -11 lines, -0 deps possible.

除此之外，当前仓库只有审计 spikes，没有生产实现；未发现应删除的第三方运行时依赖。SDK v2、pytest、ruff、mypy 均有明确验证职责。

## 8. 建议的重新开放门槛

按优先级执行，全部通过后才允许 Task 0：

1. 修复 F-01/F-02，并新增慢 `iterdir`、FIFO、symlink、status 总时限四个反例；
2. 为三工具交付真实封闭 input/output schema，验证未知参数拒绝和 `structuredContent`；
3. 用真正的 2026-07-28 wire path 替换宽松合同测试；
4. 把 hash scope 真 Blender fixture 写入 runner 成功判据；
5. 完成 Task 0 的 v2/frozen/精确暂存修订；
6. 统一 URS v1.3、spec、plan 的版本与 hash 用语；
7. 重启 Codex，复核官方 MCP 当前进程命令与上游 checkout cleanliness；
8. 重新隔离重建，要求正向测试与本报告全部反例同时通过。

## 9. 来源

- [OpenAI Docs：Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [MCP Python SDK v2.0.0 Release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
- [PyPI mcp](https://pypi.org/project/mcp/)
- [MCP 2026-07-28 Specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [Blender Lab MCP Server](https://www.blender.org/lab/mcp-server/)
- [Blender Lab blender_mcp](https://projects.blender.org/lab/blender_mcp)
- [上轮对抗性复审](2026-08-07-claude-plan-changes-adversarial-reaudit.md)
- [首轮全量审计与外部仓库比较](2026-08-07-plan-adversarial-audit-and-optimization.md)
- [SDK v2 决策](../decisions/2026-08-07-mcp-sdk-v2-selection.md)

## 10. 最终状态

- SDK 选择：**继续采用 v2.0.0；决策不变**。
- 当前 plan：**拒绝执行，等待修订后再审**。
- 官方 MCP：26 工具和 10 工具 allowlist 均复测；三项 CLI 代表功能通过。
- 工作区 Phase 0：**未执行**。
- 本报告：本轮唯一新增仓库文件。
