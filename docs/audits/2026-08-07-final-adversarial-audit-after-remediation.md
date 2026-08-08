# BlenderDesign 最终全量对抗审计（修复闭环后）

> **SUPERSEDED（2026-08-08）**：本文件保留早期 166-test/r10 结论；当前裁决见 [closeout v3](2026-08-07-closeout-v3.md) 与 [r15/v8 融合审计](2026-08-07-platform-optimization-handoff-adversarial-audit.md)。

> **历史快照，已被取代**：本报告保留当时的 166-test、旧 L3 与无 allowlist 结论，不再代表当前状态。最新裁决与证据见 [2026-08-07-closeout-v2.md](2026-08-07-closeout-v2.md)。

> 日期：2026-08-07  
> Git 分支 / 基线：`main` / `578f49e52f818dd0f01745c6b0a5ba7c4558e2dd`  
> 审计对象：URS v1.6、Phase 0 design spec、Phase 0 Plan、SDK 决策与 spikes、外部研究输入、官方 Blender Lab MCP、Codex effective 配置  
> 执行边界：**没有执行 Phase 0 Plan，没有暂存，没有提交**

## 1. 最终裁决

在本轮新增反例全部修复并再次对抗复核后，**当前 Plan-as-code 与规范中没有已知未关闭 P0/P1**。执行前 Gate G0–G5 可保持关闭，但这只表示「允许进入实施」；不表示 Phase 0 已实现。

最终状态：

| 项 | 裁决 |
|---|---|
| Phase 0 Plan | 46 个完整 Python 文件块可自足重建；隔离门禁全绿；**尚未执行** |
| URS / spec | 已落账最终权限、wire exact types、deadline、identity、fallback 崩溃恢复与审计并发合同 |
| 自定义 Server SDK | 继续选 **MCP Python SDK v2.0.0**；这是当前最优路线 |
| 官方 Blender MCP | 独立兼容通道，effective 工具目录 **26/26**，无 allow/deny，`approval_mode=approve` |
| 当前 Codex 任务的 10 工具 | 任务启动时冻结的旧目录快照；不是磁盘配置或当前新宿主仍只有 10 个 |
| Git | 仍在 `main`，HEAD 未变化，无 staged、无新 commit；等待用户审批 |

本报告取代修复前历史快照 [2026-08-07-full-repository-adversarial-reaudit.md](2026-08-07-full-repository-adversarial-reaudit.md) 的执行裁决；历史反例和当时证据保留，不回写篡改。

## 2. 审计边界与证据分级

仓库当前仍以文档、Plan 与 spikes 为主，没有把 Phase 0 生产包写入工作树。为避免「审 Plan = 执行 Plan」的混淆，本轮采用：

| 级别 | 证据 |
|---|---|
| E1 | 当前机器上的 Codex app-server、官方 MCP 进程、Blender 5.2.0 与 effective config 实测 |
| E2 | 从 Plan 完整文件块重建的隔离实现及对抗 fixture |
| E3 | 当前工作树 URS / spec / Plan / ADR / spikes 的逐项一致性与机械门禁 |
| E4 | OpenAI、Blender、MCP SDK 官方资料与上游 Git 远端 |

隔离树：

```text
/tmp/claude-501/-Users-yeminjie-Documents-BlenderDesign/
4e2a82a5-8b6c-4170-b17f-a6541694f371/scratchpad/verify
```

用户上传的研究文档已经以非规范输入整合为 [deep-research-report-2.md](../research/deep-research-report-2.md)，其可借鉴项、拒绝项和时效缺陷已在既有审计与 URS 变更记录中落账；它不覆盖官方来源或实测结果。

## 3. 修复前六条 P0 与主要 P1 的关闭状态

| 原发现 | 修复前反例 | 最终关闭证据 |
|---|---|---|
| F-01a `sorted(iterdir())` 先全量物化 | 4.773 s，突破 2.5 s | 惰性 `scandir` + cursor/backlog + 每步 deadline |
| F-01b FIFO `session.json` | 可永久阻塞 | dir-fd + `O_NOFOLLOW\|O_NONBLOCK` + regular-file + bounded read |
| F-02 status 二次开窗 | 结构上最坏 5.5 s | 唯一 absolute deadline 贯穿 discovery、probe、aggregation、cleanup |
| F-03 MCP schema/structured content 缺失 | 3 工具 `outputSchema=None`，未知参数被吞 | Pydantic strict 封闭输出 + raw-argument middleware；两条 wire path 均拒绝未知/可转换类型 |
| F-04 2026 协议假阳性 | 请求 2026，实际降级 2025 仍通过 | legacy initialize 与 modern discover 使用独立真实 stdio 路径并精确断言 |
| F-05 L3 hash fixture 未进成功判据 | runner 只 grep/打印 | 真 Blender 顶点变换不改 hash、object transform 改 hash；`hash_scope=true` 是强制字段 |
| F-06 `mcp.__version__` | SDK v2 下 `AttributeError` | `importlib.metadata.version("mcp")` |
| F-07 capabilities 默认触网 | 2.002 s | 默认纯本地；仅 `include_instances=true` 才发现实例 |
| F-08 候选饿死 | 第 17 个或后续窗口活实例不可发现 | mtime 排序 + candidate backlog + enumeration cursor |
| F-09/F-10 文档与 hash/幂等矛盾 | 版本、冲突、回滚依据互相冲突 | URS v1.6：结构摘要、`plan_scope_hash`、先校验后幂等、`.blend` 内容 hash 已统一 |
| F-11 旧官方启动命令 | 老宿主仍运行旧参数 | 当前宿主全部子进程使用 `--no-project` + SDK `<2` + editable 新命令 |
| F-12 测试自身阻塞读取 | `readline()` 可绕过局部 deadline | selector / `os.read` 非阻塞读取，计时覆盖 `Popen` |

## 4. 最终收尾轮新增反例及修复

上一轮「149 passed」之后仍发现以下残余；本报告不把“已有很多测试”当作停止条件。

| ID | 级别 | 对抗反例 | 根因 | 最终修复 |
|---|---|---|---|---|
| A-01 | P0 | 预建 runtime/run/logs 为 0755、日志为 0644，原实现继续使用 | 只处理“缺失时 mkdir”，没有 create-or-validate | 应用边界内目录验证 uid/type/mode=0700；日志 no-follow/nonblocking + 同 fd identity/type/uid/mode=0600；否则 fail-closed |
| A-02 | P1 | 16 线程首次同时构造 `AuditLog`，出现 `FileExistsError` | `exists() → mkdir()` TOCTOU | race-safe mkdir；当天日志 `O_EXCL` 创建，多个 Host 以 `flock` 串行整行写入 |
| A-03 | P1 | 长路径 session 死亡后，会话目录消失但外置 socket/目录永久残留 | cleanup 只处理 session 目录内固定路径 | fallback 目录可推导并发布 socket/dir identity；先清 fallback，再删 session 证据 |
| A-04 | P1 | `session.json` 发布前崩溃仍遗留随机 fallback | `tempfile.mkdtemp()` 无法从 session basename 恢复 | 固定 `/tmp/bcx-<sha256(instance_id)[:16]>`；宽限期后可恢复清理 |
| A-05 | P1 | Bridge/Server 的 `$TMPDIR` 不同时推导不同路径 | 恢复算法依赖进程环境 | 恢复根固定 `/tmp`，不依赖两进程环境变量 |
| A-06 | P1 | stop 会删除换入的空 session 目录 | 只给 socket/session 文件记录 identity | session/fallback 目录也记录 dev/inode；第 10 步只 rmdir identity 匹配的空目录 |
| A-07 | P1 | cleanup 可在 probe deadline 耗尽后继续多个文件 I/O | helper 未接收共享 deadline | `open/fstat/stat/unlink/rmdir` 前逐次检查同一 absolute deadline；耗尽则保留并重试 |
| A-08 | P1 | 不同目录声明同一 `instance_id`，`find()` 顺序相关 | 未绑定目录名与 session 身份 | `session.json.instance_id == directory basename` 为硬合同；不符即隔离 |
| A-09 | P2 | malformed success `result=[]` 返回 `BRIDGE_UNAVAILABLE` 却 `retryable=false` | 错误映射漏传 flag | 除 `v` mismatch 外，所有 malformed response shape 统一 retryable `BRIDGE_UNAVAILABLE` |
| A-10 | P1（证据） | Plan 只有 45 个完整块，但 164 计数包含 Plan 外 `test_scene_reader.py` | 隔离证据不是 Plan 自足重建 | 将该测试作为第 46 个完整块纳入 Task 13；最终 46/46 byte parity |

相关防御测试还覆盖：既存 `session.json.tmp` 保留、runtime/audit symlink fail-closed、FIFO 审计目标不阻塞、socket/fallback/session 目录换入保留、发布前/后 fallback 崩溃清理。

## 5. 最终隔离门禁

| 门禁 | 结果 |
|---|---|
| pytest 总计 | **166 passed，无 warnings** |
| L1 / unit | **140 passed** |
| L2 / contract | **26 passed** |
| ruff | clean |
| mypy strict | 配置内 19 个源文件，0 errors |
| vendored protocol | `vendor ok` |
| 深层扩展命名空间 import | `nested import ok` |
| Blender 5.2.0 background | `BG_CHECK_OK` |
| Plan 完整文件块 | **46/46** 与隔离树逐字节一致 |
| Plan 实施 checkbox | **93 个，全部未勾选** |

真 Blender GUI L3 最终证据：`/tmp/bcx-final-smoke-20260807-04.json`。

```json
{
  "timer_tick": true,
  "revision_bump": true,
  "fields": true,
  "hash_scope": true,
  "cycles_leak_free": true,
  "errors": []
}
```

该 artifact 晚于最终实现 Python 源码；Blender 进程退出码为 0，外部解析器逐字段验证，而不是只接受 `SMOKE_OK` 文本。

## 6. 官方 Blender MCP：26/26 已生效

### 6.1 Effective 配置与宿主

磁盘及独立 app-server effective config 共同证明：

- command：`/Users/yeminjie/.local/bin/uv`
- args：`run --quiet --no-project --with mcp[cli]>=1.2.0,<2 --with-editable /Users/yeminjie/blender_mcp/mcp blender-mcp`
- `enabled=true`
- `default_tools_approval_mode="approve"`
- 不存在 `enabled_tools`、`disabled_tools`、`tools.<name>` 覆盖
- effective `filters=null`
- Server：`blender-mcp 1.29.0`

OpenAI 官方文档定义 `enabled_tools` 为 allowlist、`disabled_tools` 为其后的 denylist，并将 `approve` 列为默认工具审批模式之一。当前结论因此分成两条独立证据：配置证明「无过滤 + 默认预批准」，`mcpServerStatus/list` 实测证明「effective 目录 26/26」。

当前 Codex 桌面宿主 PID 60640 的 Blender MCP 子进程均使用上述新命令；未发现旧 `uv --directory ...` 启动参数。

### 6.2 精确 26 工具

```text
execute_blender_code
execute_blender_code_for_cli
get_blendfile_summary_datablocks
get_blendfile_summary_datablocks_for_cli
get_blendfile_summary_missing_files
get_blendfile_summary_missing_files_for_cli
get_blendfile_summary_of_linked_libraries
get_blendfile_summary_of_linked_libraries_for_cli
get_blendfile_summary_path_info
get_blendfile_summary_path_info_for_cli
get_blendfile_summary_usage_guess
get_blendfile_summary_usage_guess_for_cli
get_object_detail_summary
get_objects_summary
get_python_api_docs
get_screenshot_of_area_as_image
get_screenshot_of_window_as_image
get_screenshot_of_window_as_json
jump_to_tab_by_name
jump_to_tab_by_space_type
jump_to_view3d_object_by_name
jump_to_view3d_object_data_by_name
render_thumbnail_to_path
render_viewport_to_path
search_api_docs
search_manual_docs
```

最终安全只读调用 `get_blendfile_summary_path_info` 成功：`isError=false`，`structuredContent.status="ok"`。本任务冻结的 10 项目录上同一只读调用也成功。

### 6.3 为什么本任务仍显示 10 个

Codex 在任务启动时把可调用工具目录注入当前任务上下文。本任务的目录快照确实仍只有 10 个摘要/文档工具；重启后新 app-server 与新任务已经读取无过滤配置并发现 26 个。旧任务不会在中途把模型可见工具 schema 热替换成新目录，因此：

```text
当前任务工具快照 = 10
新宿主 effective 目录 = 26
磁盘 allow/deny = 无
```

三者并不矛盾，也不需要再次修改配置。要在交互界面直接调用其余 16 个工具，应新建一个重启后创建的任务。

### 6.4 上游洁净性

`/Users/yeminjie/blender_mcp`：

- branch：`main...origin/main`
- working tree：clean
- local HEAD：`4309a39646e644261624bfcd2bca669b343b7621`
- local `origin/main`：同值
- 联网 `git ls-remote origin main`：同值

官方 Blender Lab 页面明确警告：该 Server 会在 Blender 中无防护执行 LLM 生成代码，可能删除数据或把数据发送到远端。用户已明确接受官方兼容通道的完整工具面和免工具审批；该通道仍不计入自定义安全系统 G1–G3 的合规证据。

## 7. SDK 选择与 wire 协议实测

自定义 Server 最终仍应采用 **MCP Python SDK 2.0.0**：没有 v1 存量迁移负担，且同一实现可服务当前旧客户端与 2026 协议客户端。官方 Blender MCP 则独立钉 `<2`，实际为 1.29.0；两条依赖边界不得合并。

| 路径 | 精确结果 |
|---|---|
| SDK v2 in-memory legacy | `2025-11-25` |
| SDK v2 stdio legacy | `2025-11-25` |
| SDK v2 in-memory modern discover | `2026-07-28` |
| SDK v2 stdio modern discover | `2026-07-28` |
| Codex 0.147，feature=true | `2025-06-18` |
| Codex 0.147，feature=false | `2025-06-18` |

因此 `mcp_2026_07_28` 的 feature 名称不能作为 2026 wire 证据；只能读取实际协商版本。SDK 决策详见 [2026-08-07-mcp-sdk-v2-selection.md](../decisions/2026-08-07-mcp-sdk-v2-selection.md)。

## 8. 已知诚实边界（不是未关闭缺陷）

1. **50 ms 是 cooperative checking budget，不是硬墙钟上界。** Python 无法抢占单次 bpy/native/property/encoder step；合同为 `50 ms + 有界原子 step + 调度抖动`。
2. **同步内核 I/O 不能被 monotonic deadline 强制中断。** 每次 I/O 发起前检查预算，目标限定为已验证的本机常规文件/目录；不对失效网络文件系统或内核卡死承诺绝对墙钟。
3. **权限边界从 `BLENDERCODEX_ROOT` 开始。** 上方用户既存祖先不 chmod；runtime root/run/logs 必须精确 0700，否则 fail-closed。会话叶目录 exclusive 0700，session/socket/audit 文件 0600。
4. **同 uid 风险仍存在。** token 不能阻止同 uid 恶意进程读取会话凭据；显式会话窗口只是缩小暴露面。
5. **Plan 预检不是实施验收。** 正式执行每个 Task 时仍须重新生成独立测试、L3 与 Git 证据。

## 9. 官方来源与上游核验

- [OpenAI Docs：Codex MCP 配置](https://learn.chatgpt.com/docs/extend/mcp#other-configuration-options)
- [Blender Lab：MCP Server](https://www.blender.org/lab/mcp-server/)
- [Blender Lab blender_mcp](https://projects.blender.org/lab/blender_mcp)
- [MCP Python SDK v2.0.0 Release](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)
- [MCP 2026-07-28 Specification](https://modelcontextprotocol.io/specification/2026-07-28)
- [Blender Python API：Timers](https://docs.blender.org/api/current/bpy.app.timers.html)

联网结果：Blender Lab 页面可达；SDK v2 release HTTP 200；Blender Projects 网页端对自动请求可能返回 403，但 Git 协议 `ls-remote` 成功并与本地 HEAD 一致。

## 10. 审批前最终状态

- Phase 0 Plan：**未执行**。
- 工作树：仅保留本轮用户授权的文档、Plan、spike 与审计修改。
- staged：无。
- commit：无新增，HEAD 仍为 `578f49e`。
- 官方 MCP：26/26、`approve`、无过滤、checkout clean。
- 当前裁决：等待用户审批；不自动进入 Task 0。
