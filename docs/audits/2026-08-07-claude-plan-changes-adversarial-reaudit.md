# Claude 修改的对抗性复审与 SDK 版本裁决

> **SUPERSEDED（2026-08-08）**：本文件是早期 SDK/反例快照；当前裁决见 [closeout v3](2026-08-07-closeout-v3.md) 与 [r15/v8 融合审计](2026-08-07-platform-optimization-handoff-adversarial-audit.md)。

> **历史快照**：本报告记录 SDK 决策与早期反例，当前状态以 [2026-08-07-closeout-v2.md](2026-08-07-closeout-v2.md) 为准。

> 日期：2026-08-07
> 对象：Claude 对 URS、Phase 0 spec、Phase 0 plan 的未提交修改
> 边界：只复审和裁决，不执行或修改 Phase 0 plan

## 1. 裁决

Claude 的修改不能原样批准。91 个自动化测试全部通过，但新对抗输入仍击穿两项被标记为“已关闭”的 Gate，并发现一项启动失败时删除非本会话 socket 的回归。

SDK 最优选择为：**自定义 Blender Codex Server 从第一天使用 MCP Python SDK v2，当前锁定 2.0.0；不再先建 v1、再安排 Phase 1.5 迁移。**

官方 Blender Lab MCP 继续使用其上游要求的 SDK v1 隔离环境。两个 Server 由不同 `uv` 进程启动，不共享 Python 环境，不构成依赖冲突。

## 2. 审计方法

1. 审阅相对基线 commit `f81ee3c` 的全部 URS/spec/plan diff。
2. 将修改后的 10 个代码块机械覆盖到隔离副本：
   `/tmp/blender-plan-reaudit.Bs8sOM/repo`。
3. 运行 plan 自带的 lint、类型、vendoring 和测试。
4. 构造 plan 未覆盖的攻击输入：
   - 慢 session 文件扫描；
   - bind 到已被其他 listener 占用的 socket；
   - SDK v2 在新旧两代 Codex 协议下的发现和工具调用。

## 3. 正向结果

| 验证 | 结果 |
|---|---|
| ruff | 通过 |
| mypy strict | 19 个源文件通过 |
| vendoring / nested import | 通过 |
| pytest | `91 passed in 10.80s` |
| `scripts/checks.sh` | 裸非交互 shell 因 `uv` 不在 PATH 而 fail-fast；受控 PATH 后 `ALL CHECKS PASSED` |
| BridgeClient slow-drip 测试 | 通过 |
| 官方 MCP CLI 三个代表工具 | 配置 `BLENDER_PATH` 后全部通过 |
| 官方 MCP 启动隔离 | 改用 `uv --no-project --with-editable` 后冒烟通过，上游 checkout 保持 clean |

以下修改方向可保留：

- BridgeClient 使用同一个 monotonic 总 deadline；
- 明确 `scene_hash` 不是完整场景指纹；
- session 元数据最后发布；
- PathPolicy 明确不是安全写入边界；
- 移除虚假 `Co-Authored-By`；
- Superpowers 插件改为非强制前置；
- 非交互 shell 增加 `uv` preflight；
- 官方 MCP 采用只读 allowlist，并与自研 UDS Bridge 隔离。

## 4. 阻断发现

### R-01（P0）SDK v1 决策是主动制造迁移债务

Claude 把 G2 标记为：继续 `mcp 1.28.x`，Phase 1 后再迁移 SDK v2。该选择与当前证据相反：

- MCP Python SDK v2.0.0 已稳定发布；PyPI 默认版本为 2.0.0；
- v1 处于维护分支，仅接收 critical/security fixes；
- v2 的 `MCPServer` 同时服务 2026-07-28 和所有 2025-era 客户端；
- 当前项目还没有实现代码，不存在存量迁移成本；
- plan 对 SDK 的直接耦合主要集中在依赖声明、`FastMCP` import/构造和协议测试，越晚修改成本越高。

#### 本机实测

环境：Python 3.13.14、MCP SDK 2.0.0、Codex CLI 0.147.0-alpha.6.5。

同一组三工具 `get_blender_status`、`get_scene_summary`、`describe_capabilities` 在以下路径全部成功：

1. SDK v2 内存 Client；
2. SDK v2 stdio Client；
3. Codex app-server，启用 `mcp_2026_07_28`；
4. Codex app-server，**不启用** `mcp_2026_07_28`，由 SDK v2 自动兼容旧协议。

因此 Codex 的 2026-07-28 支持目前仍是 opt-in，并不会阻断 SDK v2。生产环境可以先让 Codex 使用旧协议；Server 本身仍直接采用 v2 SDK，待 Codex 开关稳定后只改变客户端协议选择，无需迁移 Server SDK。

**结论：G2 未关闭，且应改判为 SDK v2。** 详细决策见 `docs/decisions/2026-08-07-mcp-sdk-v2-selection.md`。

### R-02（P0）启动失败会删除不属于本会话的 socket

Claude 的事务化启动在异常路径调用 `self.stop()`。此时 `_unlink_files()` 只检查 `socket_path != Path()`，没有证明当前会话成功 bind 过该路径。

攻击步骤：

1. 创建一个仍在监听的外部 UDS；
2. 令 `_resolve_socket_path` 返回该路径；
3. `BridgeSession.start()` 因 `EADDRINUSE` 失败；
4. 异常清理调用 `unlink(socket_path)`。

实测：

```text
{'start_error': 'OSError', 'foreign_socket_survived': False}
```

外部 listener 的 fd 仍开着，但路径已被删除，新客户端无法再连接，造成拒绝服务。

**修正要求：** 增加明确的 `_socket_owned` 状态，只在当前实例成功 bind 后设为 true；清理只能 unlink 自己拥有的路径。必须增加“bind 冲突保留外部 socket”测试。仅测试 `write_session_file` 失败不够。

### R-03（P0）Discovery 的“全扫描 deadline”不包含扫描

代码在完成以下所有工作后才创建 deadline：

- `sorted(run_dir.iterdir())`；
- 对每个目录执行 `is_dir/stat`；
- 读取并解析每个 `session.json`；
- 收集全部候选；
- 超过 16 个后再次 `stat` 排序。

因此 `MAX_CANDIDATES=16` 只是 probe 上限，不是扫描上限。慢文件系统、大量目录、巨型 JSON、symlink 或 FIFO 可以在 deadline 启动前耗尽任意时间。

对抗测试给 400 个 session read 各增加 10ms I/O 延迟。2026-08-07 重启后复测：

```text
{'candidates': 400, 'elapsed_seconds': 4.847,
 'claimed_total_budget_seconds': 2.5, 'returned': 400}
```

**修正要求：** deadline 必须在 `_scan()` 入口创建；session 文件必须是有大小上限的普通文件；迭代、stat、读取、解析、排序和 probe 共用同一剩余预算。预算耗尽返回显式 partial 元数据，不清理未完成判定的目录。

### R-04（P1）`scene_hash` 文档自相矛盾，新增测试是恒真式

同一 spec 连续出现三种冲突表述：

- 跨进程、跨会话“是否变过”一律看 `scene_hash`；
- `scene_hash` 看不到顶点、拓扑、材质、modifier、visibility 等；
- `scene_hash` “对整个场景敏感”。

三者不能同时成立。

新增测试 `test_structure_hash_v1_blind_spots_are_by_design` 创建的 `a` 和 `b` 参数逐字相同，只证明“相同输入得到相同 hash”。它没有构造两个不同场景，也无法验证盲区语义。

**修正要求：** 将 wire 字段语义正式定为 `scene_structure_hash_v1`，只证明所列结构字段；跨会话完整等价不得由该值回答。用真实 Blender fixture 验证顶点等变化确实不在 v1 覆盖面，同时避免再写“全场景敏感”。

### R-05（P1）官方 Blender MCP 的默认依赖解析已与源码不兼容

官方 commit `4309a39` 的 `mcp/pyproject.toml` 声明 `mcp[cli]>=1.2.0`，没有 `<2` 上界；同一 commit 仍从 `mcp.server.fastmcp` 导入 v1 `FastMCP`。PyPI 当前默认版本已是 2.0.0。

按上游声明生成的 lock 固定到 `mcp==2.0.0` 后，默认启动实测失败：

```text
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

显式叠加 `mcp[cli]>=1.2.0,<2` 后解析为 1.29.0，三项 CLI 冒烟恢复通过。

**结论：** 官方 Server 必须保留独立 v1 环境和显式 `<2` 上界；启动命令使用 `uv --no-project --with-editable`，避免生成上游 `uv.lock`；也不要把官方 Server 的 v1 约束传播到自定义 Server。本机配置已按此修正并经 Codex app-server 复测。

## 5. 其他一致性问题

| 等级 | 问题 |
|---|---|
| P1 | plan 将 G0 标为待确认，但仓库已由用户授权初始化并已有基线 commit |
| P1 | plan 将 G5 标为待处理，但官方 MCP allowlist、`BLENDER_PATH` 和冷启动验证已经完成 |
| P1 | URS v1.2 变更记录声称“新增 R-08”，正文不存在 R-08 |
| P2 | URS 头部仍写“v1.1 变更见 §13”，未同步到 v1.2 |
| P2 | spec 状态仍为“待评审”，与 URS“已评审”和新增决策不一致 |
| P2 | Discovery 遍历 completed Future 的 set，返回实例顺序不再确定 |
| P2 | `shutdown(wait=False)` 不会停止已经运行的 probe；异常慢 probe 可跨扫描存活 |

## 6. SDK 选择比较

| 维度 | SDK v1.28 | SDK v2.0.0 |
|---|---|---|
| 上游状态 | 维护分支（critical/security fixes） | 当前稳定版 |
| 新项目适配 | 先实现再迁移 | 一次实现 |
| Codex 旧协议 | 支持 | 实测支持 |
| Codex 2026-07-28 | 需迁移 | 实测支持 |
| Server API | `FastMCP` | `MCPServer` |
| outputSchema | plan 记录为弱约束 | 根据类型生成；可配合结构化返回 |
| 未来工作 | SDK + 协议双迁移 | 只需协议兼容回归与开关切换 |
| 与官方 Blender MCP 并存 | 可 | 可；进程环境隔离 |

保留 v1 唯一可能的理由是“已有大量不可迁移代码”。当前仓库不存在实现代码，因此该理由不成立。

## 7. 审批结论

- Claude 修改：**有条件拒绝原样合入**。
- BridgeClient 总 deadline：通过。
- Discovery 总 deadline：失败，G4 不得关闭。
- 启动事务：目标正确、异常清理失败，需补 ownership 修复。
- scene hash 语义：部分修正，但文档和测试仍不成立。
- SDK G2：改判为 SDK v2.0.0。
- Phase 0 plan：继续保持未执行状态。

## 8. 来源

- [OpenAI Docs：Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [OpenAI Codex Changelog](https://learn.chatgpt.com/docs/changelog#month-2026-08)
- [MCP Python SDK v2.0.0](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
- [PyPI mcp](https://pypi.org/project/mcp/)
- [MCP 2026-07-28 Specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [Blender Lab MCP 固定 commit](https://projects.blender.org/lab/blender_mcp/src/commit/4309a39646e644261624bfcd2bca669b343b7621)
