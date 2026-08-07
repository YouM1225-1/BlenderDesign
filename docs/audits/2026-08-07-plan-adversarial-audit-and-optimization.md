# Blender × Codex Phase 0 对抗性审计与优化建议

> 审计日期：2026-08-07  
> 审计对象：仓库现有 URS、Phase 0 spec、Phase 0 plan、外部研究报告、Blender Lab 官方 MCP 及相关开源仓库  
> 交付边界：**仅审计、实测、提出优化建议；没有修改或执行仓库中的 plan。**

## 1. 结论先行

1. Phase 0 plan 的代码骨架具有可实现性：按文档机械重建到隔离的 `/tmp` 目录后，87 个测试、ruff、mypy、vendoring、后台 Blender 检查和真实 GUI Blender 冒烟均通过。
2. “测试全绿”不足以批准执行。对抗测试证实三个关键保证不成立：
   - `scene_hash` 看不到顶点坐标和可见性变化，却被 spec 描述为跨会话的全场景变更摘要；
   - `BridgeClient` 的 timeout 是逐次 `recv` 超时，不是总 deadline；
   - Discovery 在候选实例超过 worker 数时会分批叠加超时，突破声称的 3 秒预算。
3. 仓库 ADR-5 的重评触发条件已经满足：当前安装的 Blender Lab 官方 MCP（manifest 1.0.0、主分支 commit `4309a39`）暴露 26 个工具，并非“只有任意 Python”。它已经提供对象/场景摘要、文件健康检查、文档检索、截图、UI 导航、渲染及 CLI 变体。
4. 官方 MCP 仍不能直接作为本项目的安全控制底座：它保留任意 Python、使用无鉴权的 localhost TCP bridge，并有大响应截断、CLI 路径缺失等实测问题。建议采用“自研安全控制面 + 有选择借鉴官方只读分析能力”的混合方案。
5. 外部研究报告的总体架构方向有参考价值，但内部引用占位符不可复核，且包含已过时事实和可执行示例缺陷。它已作为“外部研究输入”整合，不能替代 URS、ADR 或验收证据。
6. 当前目录不是 Git 仓库。为避免执行 plan Task 0 中的 `git init`，本次没有初始化仓库，也无法完成 Git commit；需要项目所有者给出真实 Git 根目录或明确授权初始化。

## 2. 范围、方法与证据等级

### 2.1 审计范围

- `Blender-Codex-需求规格说明书-v1.md`
- `docs/superpowers/specs/2026-07-23-phase0-readonly-channel-design.md`
- `docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`
- `/Users/yeminjie/Downloads/deep-research-report-2.md`
- Blender Lab 官方 MCP：
  - 官方页面
  - 本机安装源码
  - 当前 Codex 会话暴露的 MCP 工具
  - 真实 Blender 5.2.0 LTS 会话
- 8 个相关 GitHub 仓库和 MCP/OpenAI/Blender 官方资料

### 2.2 执行边界

- 没有在工作区创建 plan 所描述的 Python 包、Bridge、Server、测试或脚本。
- 没有运行 plan Task 0 的 `git init`、`git add` 或任何计划中的 commit。
- plan 代码只被机械重建到 `/tmp/blender-plan-audit.uq2FRj`，该目录不属于工作区。
- 官方 MCP 的写出测试只写入 Blender 管理的临时目录；没有保存或改写当前未保存场景。
- 本次工作区改动仅为研究输入与本审计报告。

### 2.3 证据等级

| 等级 | 含义 |
|---|---|
| E1 | 本机真实 Blender / MCP / 进程实测 |
| E2 | plan 隔离重建和自动化测试 |
| E3 | 固定 commit 源码检查 |
| E4 | 官方文档或官方 API 元数据 |
| E5 | 第三方仓库自述；需进一步独立验证 |

## 3. 仓库基线与不变性

审计开始时工作区只有 3 个业务 Markdown 文件和若干 `.DS_Store`，没有 `.git`。原始关键文档当前 SHA-256 如下：

| 文件 | SHA-256 |
|---|---|
| `Blender-Codex-需求规格说明书-v1.md` | `94b95c5c2cce7641abbb7641cedfce9311b56a68094d6d365bd2d36e10c4cca8` |
| Phase 0 design spec | `0b0cee6135407d51e50355ef936de8c01a7312147bd768a5017377209ceb7e61` |
| Phase 0 plan | `af52e1a6ae83c76e25a0ba6f3d873ef8ce510b9a6c661e74f0ef7ec6bfd4e38a` |

本报告完成后应再次校验这些摘要；任何差异都视为违反“不改 plan”的边界。

## 4. Phase 0 plan 隔离重建结果

### 4.1 正向验证

从 plan 中机械提取并重建 47 个文件，并应用 plan 自己在后续任务中明确要求的三个补丁：

- `SceneReader.status_info`
- `Instance.envelope_mismatch`
- `[project.scripts]`

结果：

| 检查 | 结果 |
|---|---|
| pytest | `87 passed` |
| ruff | `All checks passed` |
| mypy strict | `Success: no issues found in 19 source files` |
| vendoring / nested import gate | 通过 |
| Blender background check | `BG_CHECK_OK` |
| 真实 GUI Blender L3 | `SMOKE_OK` |

`scripts/checks.sh` 首次运行因 `uv: command not found` 失败；将 `/Users/yeminjie/.local/bin` 加入 `PATH` 后全绿。说明代码路径基本闭合，但“开发机恰好有正确 PATH”被错误地当成前置条件。

### 4.2 为什么全绿仍不能批准执行

plan 的测试主要验证“实现是否符合 plan 中写出的同一组假设”。当 spec、实现和测试共享一个遗漏时，三者可以同时全绿。以下三项正是通过独立攻击输入才暴露。

## 5. 对抗性发现

### F-01（阻断）`scene_hash` 严重漏检

**实测：** 在真实 Blender 5.2 中分别移动 Cube 顶点、切换 `hide_render`，三个 hash 完全相同。

| 状态 | hash 是否变化 |
|---|---|
| 初始场景 | 基线 |
| 顶点坐标改变 | 否 |
| render visibility 改变 | 否 |

**根因：** 当前算法只覆盖对象名、对象类型、`matrix_world`、数据类型以及 Mesh 顶/边/面数量。它不覆盖：

- 顶点坐标和边/面连接关系
- modifier 与参数
- material / node tree 关系
- viewport / render visibility
- collection 关系
- camera / light 参数
- scene unit、render、color management 等场景设置

**影响：** spec 中“跨会话一律看 `scene_hash`”以及“对整个场景敏感”的陈述不成立。它可以作为轻量结构摘要，但不能称为完整 scene fingerprint。

**执行前建议：**

1. 先明确语义，二选一：
   - 改名为 `scene_structure_hash_v1`，明确只检测对象结构和 transform；
   - 或定义版本化 `scene_fingerprint_v2`，覆盖项目实际关心的状态。
2. 不要直接 hash 整个 `.blend` 内存对象。建立规范化、版本化字段清单，避免把缓存、无关 UI 状态和浮点噪声纳入。
3. 增加真实 Blender 对抗矩阵：顶点移动、拓扑重连、modifier、material、visibility、collection、camera、light、unit、render setting。
4. 在覆盖范围修正前，禁止把该值用于“无变化”“快照等价”或验收证明。

### F-02（阻断）`BridgeClient` timeout 不是总 deadline

**实测：** bridge 每 20ms 只发送 1 字节，配置 `timeout=0.03s`，客户端在 **1.554s** 后仍成功返回，而不是约 30ms 超时。

**根因：** `socket.settimeout(timeout)` 约束的是每一次阻塞操作；每次成功收到 1 字节都会重新获得一个完整 timeout 窗口。

**影响：** 慢滴流响应可以无限延长调用。方法超时、队列 deadline 与调用方重试策略失去统一语义。

**执行前建议：**

- 在调用开始时记录 `deadline = time.monotonic() + timeout`；
- connect、send、每次 recv 前都按 `deadline - now` 设置剩余 timeout；
- 剩余时间 `<= 0` 立即返回 `BRIDGE_TIMEOUT`；
- 添加慢 header、慢 body、永不结束 frame 和超大 frame 测试。

### F-03（阻断）Discovery 可突破 3 秒预算

**实测：** 16 个挂起候选、`max_workers=8` 时，扫描耗时 **4.008s**，高于声称的 3 秒预算。

**根因：** 每个 probe 有自己的超时，线程池只允许 8 个并发，第二批再次消耗完整超时；`executor.map` 没有总 deadline。

**执行前建议：**

- 对一次 discovery 设置整体 monotonic deadline；
- 对候选数设置硬上限，并优先最近 session；
- 超过 deadline 后取消未开始任务，不等待所有 Future；
- 结果中显式返回 `partial=true` / `skipped_count`，不要把预算耗尽伪装成“没有实例”；
- 用 1、8、9、16、100 个挂起实例做时间上界测试。

### F-04（高）启动失败会留下“假会话”

`BridgeSession.start()` 先写 `session.json`，之后才执行 socket `bind` 和 listener 初始化。若地址冲突、权限错误或线程启动失败，session 文件已经公开，PID 仍然活着，Discovery 可能把它长期识别为断开实例。

**建议：** 启动过程做成事务：

1. 在私有临时 session 目录准备状态；
2. 完成 bind、listen、socket 权限、wake pair 和线程启动；
3. 最后原子发布 session 元数据；
4. 任一步失败都关闭 fd、删除 socket、session 目录和 fallback 临时目录。

### F-05（高，Phase 1 前阻断）`PathPolicy.resolve(strict=False)` 存在 TOCTOU

当前代码先解析并验证路径，真正写入发生在未来的另一个时刻。攻击者可在验证后替换路径组件为 symlink。

**建议：** Phase 0 可以保留纯校验接口，但不得把它宣传成安全写入边界。Phase 1 应使用目录 fd / `openat` 风格、`O_NOFOLLOW`、原子临时文件与同目录 rename；最终授权应绑定已打开 fd，而不是字符串路径。

### F-06（高）协议/SDK 路线可能造成可避免返工

plan 新项目仍固定 `mcp>=1.28,<1.29` 和 2025 协议，再在 Phase 1.5 迁移。2026-07-28 起 Python SDK v2.0.0 已稳定，v1 只做安全维护，默认 `pip install mcp` 已进入 v2。

**建议：** 在 Task 0 前设置一次有退出标准的决策门：

- 用最小三工具 spike 验证 Codex + SDK v2；
- 比较 v1/v2 的启动、schema、server instructions 和兼容成本；
- 若无明确阻断，直接以 v2 为基线；
- 若必须留在 v1，记录负责人、最后迁移日期和可删除兼容层，避免“Phase 1.5”无限延期。

这不等于把 MCP Tasks extension引入当前设计；长任务仍可保持服务端句柄 + 轮询。

该建议只针对本仓库计划新建的自定义 Server。Blender Lab 官方 MCP 当前仍导入 v1 `FastMCP`，本机启动命令也明确固定 `<2`；在上游声明兼容前，不应擅自把官方 Server 升到 SDK v2。

### F-07（中）工具链依赖没有被前置验证

`checks.sh` 假设 `uv` 在 PATH。实际机器上 `uv` 位于 `/Users/yeminjie/.local/bin/uv`，非交互 shell 首次失败。

**建议：**

- preflight 用 `command -v uv`、`command -v blender` 明确失败；
- CI 和 Codex MCP 配置使用可解释的绝对路径或受控 PATH；
- 记录 `uv --version`、Blender binary hash、Python 版本；
- 不在检查脚本中静默安装或自动更新依赖。

### F-08（中）计划元信息和执行依赖不可靠

- 每个示例 commit 硬编码 `Co-Authored-By: Claude Fable 5`，与实际作者和执行代理无关，属于错误来源标记。
- plan 要求 `superpowers:*` 子技能，但当前环境未安装 Superpowers 插件。
- Task 0 自身执行 `git init`，而当前目录没有 Git 基线。直接执行会把“仓库初始化”与“功能实现”混为一体。

**建议：** 删除虚假署名模板；把可选工作流插件改成非阻塞建议；把 Git 根目录确认、初始历史和代码 Task 分成独立人工 gate。

## 6. 外部研究报告审计

整合副本位于 `docs/research/deep-research-report-2.md`。原文不可复核的 `turn…` 引用占位符已移除，并加上“外部研究输入”状态说明。

### 6.1 已核实问题

| 位置/主题 | 问题 | 建议 |
|---|---|---|
| 模型基线 | “GPT-5.3-Codex 是当前最强”已过时 | 引用 OpenAI 当前 Models 页面；不要把架构绑定到滚动别名 |
| `execute_task` | `requires_checkpoint=False` 时 `checkpoint` 未定义，却仍访问 `checkpoint.path` | 明确 `blend_path = checkpoint.path if ... else task.input_path` 并测试两条分支 |
| Dispatcher | 捕获 `BaseException` 会吞 `KeyboardInterrupt` / `SystemExit` | 捕获 `Exception`；`stop()` 时取消或失败化队列内 Future |
| Kubernetes rootfs | `readOnlyRootFilesystem: true`，但 Blender 配置写 `/tmp/blender-config`；示例没有可写 `/tmp` 挂载 | 增加受限 `emptyDir` 并挂载 `/tmp`，限制大小 |
| NetworkPolicy | 只允许 artifact namespace 的 443，没有 DNS；按服务名访问会失败 | 允许集群 DNS，且 artifact egress 同时使用 namespaceSelector + podSelector |
| ConfigMap | 用于 task manifest / 参考资产，存在约 1MiB 等限制 | ConfigMap 只放小型控制元数据；资产使用对象存储或只读 volume，并校验 digest |
| 引用 | `cite(turn…)` 一类生成会话内部占位符，仓库读者无法复核 | 改为可点击的官方 URL、固定 commit 和访问日期 |
| 仓库数字 | 工具数、测试数等多来自仓库 README | 明确标记“仓库自述”，关键数字用源码或本地测试复核 |

### 6.2 许可证边界

- Blender Lab 官方 MCP：GPL-3.0-or-later
- `blend-ai`：AGPL-3.0
- `PatrykIti/blender-ai-mcp`：Apache-2.0
- 本次检查的其余主要 GitHub 候选多为 MIT

“借鉴架构”不等于可以复制源码。任何代码迁入前都应：

1. 固定来源 commit；
2. 记录文件级许可证；
3. 决定整个衍生作品的分发许可证是否兼容；
4. 若不希望引入 copyleft 传递义务，只借鉴公开接口与行为，进行独立实现。

## 7. Blender Lab 官方 MCP 实测

### 7.1 安装与版本基线

| 项 | 实测 |
|---|---|
| Blender | 5.2.0 LTS, Apple Silicon |
| 官方 MCP 源码 | `https://projects.blender.org/lab/blender_mcp.git` |
| 本机 commit | `4309a39646e644261624bfcd2bca669b343b7621` |
| 描述 | `v1.0.0-5-g4309a39` |
| manifest 版本 | 1.0.0 |
| 许可证 | GPL-3.0-or-later |
| Codex transport | stdio |
| Blender bridge | `localhost:9876` TCP |
| 当前源码状态 | `mcp/uv.lock` 为未跟踪文件 |

官方页面明确警告：服务器会在 Blender 中执行 LLM 生成代码，没有防止删除数据或向远端发送数据的保护，建议使用虚拟机或无敏感数据环境。该页面创建于 2026-03-30，最近修改于 2026-05-26；v1.0.0 发布于 2026-04-27。

### 7.2 26 个工具能力矩阵

| 能力组 | 工具 | 结果 |
|---|---|---|
| 场景概览 | `get_objects_summary`, `get_object_detail_summary` | 成功；识别 Scene、Cube、Camera、Light，Cube 返回 transform、dimension、material、visibility、collection |
| 文件健康 | 5 个当前会话 summary：datablocks、missing files、linked libraries、path info、usage guess | 全部成功；当前文件未保存，无 missing file / linked library |
| 文档检索 | `search_api_docs`, `get_python_api_docs`, `search_manual_docs` | 全部成功；返回 timer API 和命令行渲染参数顺序等官方资料 |
| 结构化截图 | `get_screenshot_of_window_as_json` | 成功 |
| 图片截图 | window / area image | **部分成功**；100KB、256KB、320KB 级限制可成功，默认 window、384KB 及以上多次返回截断 JSON |
| UI 导航 | 按工作区名、space type、对象名、对象 data 名定位 | 全部成功；包括本地化“布局”、`VIEW_3D`、Cube |
| 临时渲染 | thumbnail、viewport | 成功；输出被重定向到 Blender scratch 目录 |
| 任意代码 | 当前会话 `execute_blender_code` | 成功；只读返回版本、对象数、online access、filepath、mode |
| CLI 变体 | path summary、datablocks summary、任意代码三个代表调用 | 失败：`Blender executable not found at 'blender'` |
| 其余 CLI summary | missing、linked libraries、usage guess | 未逐一调用；与失败项共享同一 `run_blender_cli` 前置路径，当前配置同样被阻断 |

临时渲染的宿主机文件已验证：

- thumbnail：320×180 PNG，约 35KB
- viewport：1920×1080 PNG，约 1.1MB

工具忽略调用方目录，只保留 basename 并写入 `bpy.app.tempdir/blender_mcp/`。这是合理的路径收敛，但 API 应明确说明“output_path 不是任意宿主机路径”。

### 7.3 大截图截断的源码解释

实测错误：

```text
Invalid response from Blender at localhost:9876:
Unterminated string starting at: line 1 column 61 (char 60)
```

固定 commit 源码显示：

1. accept 后把 client socket 设为 non-blocking；
2. 响应阶段直接对可能很大的 JSON 调用一次 `sendall`；
3. `BlockingIOError` 属于 `OSError`，被吞掉后立即关闭连接；
4. 客户端因此收到没有 NUL 结尾的部分 JSON。

这与“默认大小已经预留 2KiB MCP envelope headroom”是两个不同层次的问题：即使 MCP message 理论上低于 1MiB，add-on TCP bridge 仍可能在非阻塞 socket 上发生部分发送。

**上游建议：** 为连接维护 outbox + offset，只在 writable 时继续发送；或在响应发送阶段切换为有总 deadline 的阻塞发送。必须加高压 socket buffer 和 100KB–1MB 响应回归。

### 7.4 CLI 变体的配置缺口

官方 helper 只读取 `BLENDER_PATH`，否则调用裸 `blender`。当前 Codex MCP 配置没有该环境变量；实际可执行文件位于：

```text
/Applications/Blender.app/Contents/MacOS/Blender
```

在修复配置并重启 Codex 前，所有 6 个 `*_for_cli` 工具均不可视为可用。建议通过 MCP server 的显式环境配置传入 `BLENDER_PATH`，并增加启动 preflight；不要依赖 GUI shell 的 PATH。

### 7.5 安全与运行时问题

- Blender bridge 默认监听 localhost TCP 9876，请求只有 `type/code/strict_json`，没有 session token 或请求鉴权。
- 连接 helper 使用 300 秒 socket timeout，同样不是严格总 deadline。
- 任意 Python 工具仍然公开，官方所谓 `WeakSandboxForLLM` 不是主机隔离。
- 若启用官方 HTTP 模式，当前源码允许 CORS `*` 且关闭 DNS rebinding protection；不能暴露到不可信网络。
- 当前 Codex 配置没有 `enabled_tools` / `disabled_tools` allowlist。
- 运行 `uv` 后官方源码 checkout 出现未跟踪 `mcp/uv.lock`；安装流程不应污染供应链基线。

**本机安全建议（不在本次审计中执行）：**

1. 默认禁用 `execute_blender_code` 与 `execute_blender_code_for_cli`；
2. 只 allowlist 只读 summary、文档检索和必要截图工具；
3. render / UI 导航按写入或交互工具对待；
4. 仅绑定 loopback，不启用 HTTP，除非补齐认证、Origin 和 DNS rebinding 防护；
5. 在无敏感凭据的专用 macOS 用户、VM 或隔离 worker 中运行；
6. 固定官方 commit / release 和依赖锁，不在启动时更新主分支。

## 8. 官方 MCP 对仓库 ADR 的影响

URS ADR-5 写明：一旦“官方 Blender MCP 出现非任意代码执行的结构化工具面”就重评架构。v1.0.0 已满足该条件。

### 8.1 不建议的两个极端

- **完全替换为官方 MCP：** 安全、鉴权、deadline、审计和事务保证不满足本项目目标。
- **完全忽略官方 MCP：** 会重复实现已经存在且经过真实 Blender 使用的摘要、文档检索、截图降采样、UI 定位和 scratch-path 行为。

### 8.2 推荐混合方案

保留 plan 的核心安全价值：

- 每实例能力 token
- UDS 与文件权限
- 明确 envelope
- 主线程队列
- 总 deadline
- 审计
- Phase 1 的事务/快照语义

有选择吸收官方 MCP 的行为和测试案例：

- progressive scene/object summary
- missing files / linked libraries / path info
- 本地 Blender API 与 Manual 检索
- screenshot 大小协商
- UI 定位时 `allow_edits=false`
- 输出统一写 scratch 目录
- GUI 与 CLI 双模式能力表

如复制官方源码，项目必须接受 GPL-3.0-or-later 的衍生和分发要求；否则应基于公开 API 行为独立实现。

## 9. 相关 GitHub 仓库可借鉴项

元数据快照：2026-08-07。Stars 会变化，只用于生态成熟度参考，不代表质量结论。

| 仓库 | Stars | 许可证 | 借鉴项 | 不应照搬 |
|---|---:|---|---|---|
| `ahujasid/blender-mcp` | 25,574 | MIT | 生态兼容性、用户工作流基线 | 任意代码能力不能作为安全底座 |
| `dcc-mcp/dcc-mcp-blender` | 18 | MIT | progressive skill/tool discovery、readiness probe、真实 E2E | 先核对其 DCC 抽象是否超出本项目范围 |
| `HoldMyBeer-gg/blend-ai` | 118 | AGPL-3.0 | 主线程队列、输入 allowlist、render guard | 黑名单不是沙箱；AGPL 传播义务 |
| `sandraschi/blender-mcp` | 30 | MIT | headless-first、per-tool execution mode、artifact workflow | 不要无差别扩大工具面 |
| `djeada/blender-mcp-server` | 21 | MIT | 小而明确的工具面、异步 job API、data API script library | 仓库自述数字需独立验证 |
| `PatrykIti/blender-ai-mcp` | 52 | Apache-2.0 | 目标路由、小公开工具面、确定性验证 | 不要把路由层当授权层 |
| `glonorce/Blender_mcp` | 4 | MIT | main-thread dispatcher、tool intent filtering | 历史和体量较小，证据权重有限 |
| `6xvl/blender-mcp` | 2 | MIT | 供应链反例 | 避免强制更新和运行时拉取 |

本次源码检查使用的固定 commit 示例：

- dcc-mcp-blender：`1f1dacc54c1bb9fa0f8b347f345437f59c23e40d`
- glonorce/Blender_mcp：`21e8048ec2e28f974e2d06d937bfd7d18182a52b`
- sandraschi/blender-mcp：`63e6fa112268917f1a9b4bc5c0b6625489650846`
- djeada/blender-mcp-server：`7eed33edf4aca2ab0ca84a6da27321f89f68b504`

## 10. 对 plan 的优化建议（不修改 plan）

### 10.1 执行前阻断门

| Gate | 决策/产物 | 验证 |
|---|---|---|
| G0 Git 基线 | 确认真正 Git 根目录；或单独批准初始化与初始文档 commit | `git rev-parse --show-toplevel`，历史可追溯 |
| G1 Build / Adopt / Hybrid | 根据 ADR-5 正式记录官方 MCP 重评结论 | ADR 含安全、许可、维护成本 |
| G2 MCP SDK | v2 spike；或有截止日期的 v1 例外 | Codex 启动 + 三工具契约测试 |
| G3 Fingerprint 语义 | 明确 hash 覆盖范围和版本 | 真实 Blender 变更矩阵 |
| G4 Deadline 语义 | 所有 I/O 与 discovery 使用总 monotonic deadline | slow-drip 与候选洪泛测试 |
| G5 官方 MCP 安全策略 | 工具 allowlist、`BLENDER_PATH`、隔离说明 | 重启后列工具 + CLI 冒烟 |

任一 Gate 未通过，不应开始 Task 0。

### 10.2 对现有 Task 的最小调整建议

| 当前 Task | 建议调整 | 新增验收 |
|---|---|---|
| Task 0 | 把 Git 初始化移到人工批准 gate；preflight 解析 uv/Blender 绝对路径；先做 SDK v2 spike | 非交互 shell 可重复 |
| Task 3 | 版本化 scene fingerprint；扩大覆盖或缩小承诺 | 顶点、拓扑、材质、modifier、visibility 等真实测试 |
| Task 7 | listener 成功后再原子发布 session；失败全回滚 | bind 冲突不留任何目录/文件/fd |
| Task 8 | 明确 Phase 0 仅字符串校验；Phase 1 改为 fd-based 安全写入 | symlink race 测试 |
| Task 10 | 改为全调用总 deadline | 每 20ms 滴 1 byte 仍按总预算失败 |
| Task 11 | 全扫描 deadline + 候选上限 + partial 结果 | 100 个挂起候选仍满足上界 |
| Task 14 | `command -v` preflight；依赖锁与源 checkout 清洁检查 | PATH 缺失时给可操作错误 |
| Task 16 | 加上述三个真实对抗测试 | 缺陷在修复前必须红 |
| Task 18 | 增加官方 MCP 兼容性对照，不把“截图成功”当几何正确性 | GUI、background、CLI 能力矩阵 |
| Task 19 | 记录工具 allowlist、官方 MCP 风险、许可证清单 | 新机器按文档可复现 |

### 10.3 建议的优先顺序

1. G0–G5 决策门；
2. 修复 fingerprint、总 deadline、discovery 上界；
3. 修复启动事务和 preflight；
4. 再跑隔离 L1/L2/L3；
5. 最后才执行正式 plan。

这比直接按 20 个 Task 顺序推进更早暴露架构返工点，也不会扩大 Phase 0 的交付范围。

## 11. 建议新增的验证清单

### 11.1 场景摘要

- 同计数不同顶点坐标
- 同计数不同边/面连接
- modifier 参数改变
- material slot / node 参数改变
- object / collection visibility
- object 在 collection 间移动
- camera lens / clipping
- light energy / color
- unit scale / render engine / color management
- 多 scene、活动 scene 切换

### 11.2 I/O 与生命周期

- header 每 `timeout - ε` 到 1 byte
- body 每 `timeout - ε` 到 1 byte
- 超大 frame
- 对端永不 NUL / 永不完整 frame
- bind 冲突、线程启动失败、session publish 失败
- stop 时 pending task / Future 得到确定结果

### 11.3 Discovery

- 0 / 1 / 8 / 9 / 16 / 100 候选
- PID 活但 socket 假
- PID 复用
- session 文件被部分写入
- symlink session dir
- deadline 到期后的 partial 结果与 Future 取消

### 11.4 官方 MCP

- 默认和 100KB–1MB 截图响应
- socket 发送缓冲极小场景
- CLI `BLENDER_PATH` preflight
- GUI dirty file 的 CLI 临时副本清理
- `execute_blender_code` 默认禁用验证
- HTTP 模式不得在无认证时启用

## 12. 来源

### 12.1 官方资料

- [Blender Lab MCP Server](https://www.blender.org/lab/mcp-server/)
- [Blender Lab blender_mcp 仓库](https://projects.blender.org/lab/blender_mcp)
- [Blender MCP v1.0.0 release](https://projects.blender.org/lab/blender_mcp/releases/tag/v1.0.0)
- [Blender MCP 固定 commit](https://projects.blender.org/lab/blender_mcp/src/commit/4309a39646e644261624bfcd2bca669b343b7621)
- [截图截断相关发送实现](https://projects.blender.org/lab/blender_mcp/src/commit/4309a39646e644261624bfcd2bca669b343b7621/addon/blender_mcp_addon/mcp_to_blender_server.py)
- [Blender Python Threads Gotcha](https://docs.blender.org/api/current/info_gotchas_threading.html)
- [Blender Python API](https://docs.blender.org/api/current/)
- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Codex Build Skills](https://learn.chatgpt.com/docs/build-skills)
- [OpenAI Models](https://developers.openai.com/api/docs/models)
- [MCP Specification](https://modelcontextprotocol.io/specification/)
- [MCP Python SDK v2.0.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)

### 12.2 相关仓库

- [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)
- [dcc-mcp/dcc-mcp-blender](https://github.com/dcc-mcp/dcc-mcp-blender/tree/1f1dacc54c1bb9fa0f8b347f345437f59c23e40d)
- [HoldMyBeer-gg/blend-ai](https://github.com/HoldMyBeer-gg/blend-ai)
- [sandraschi/blender-mcp](https://github.com/sandraschi/blender-mcp/tree/63e6fa112268917f1a9b4bc5c0b6625489650846)
- [djeada/blender-mcp-server](https://github.com/djeada/blender-mcp-server/tree/7eed33edf4aca2ab0ca84a6da27321f89f68b504)
- [PatrykIti/blender-ai-mcp](https://github.com/PatrykIti/blender-ai-mcp)
- [glonorce/Blender_mcp](https://github.com/glonorce/Blender_mcp/tree/21e8048ec2e28f974e2d06d937bfd7d18182a52b)
- [6xvl/blender-mcp](https://github.com/6xvl/blender-mcp)

## 13. 最终状态

- plan：未修改、未执行。
- 外部报告：已作为带状态说明的研究输入整合。
- 优化建议：已独立成文，不回写 plan。
- 官方 MCP：已完成真实会话、文档、UI、截图、渲染、任意代码只读和 CLI 代表路径实测。
- Git commit：未完成；当前目录没有 `.git`，等待项目所有者确认 Git 根目录或授权初始化。
