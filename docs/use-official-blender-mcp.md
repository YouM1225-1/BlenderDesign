# Blender Lab 官方 MCP：安全建模运行手册

状态：operational、non-normative

本仓库技术版本：`0.1.0`

本手册只规定安装完成后的建模、验证和证据流程。安装、配置、更新与回滚请使用
[`install-official-blender-mcp.md`](install-official-blender-mcp.md)，不要在此重复安装步骤。

## 1. 边界与前置条件

只使用名为 `blender` 的 Blender Lab 官方 MCP，不调用本仓库的自定义 MCP Server。

运行边界为：

- Blender `>=5.2`；`5.2.0` 是实测基线，更高版本必须重新通过本手册的运行时探测；
- 官方源码固定在
  `4309a39646e644261624bfcd2bca669b343b7621`，运行中不得更新或修改该 checkout；
- Server 继续使用 Python 3.13 和 `mcp[cli]>=1.2.0,<2`；
- `MCP_SOURCE_DIR`、`UV_BIN` 和有效 Server 参数从已验证的安装配置解析，不硬编码用户名；
- 只操作新启动的 disposable factory scene，不打开、保存或覆盖用户 `.blend`；
- 运行文件只写入当前 UID 所有、非 symlink、mode `0700` 的临时 run root。

开始前验证 checkout 的完整 commit、clean 状态和有效配置。live catalog、固定源码
catalog 与 configured catalog 必须动态、逐名相等。不得把工具数量硬编码为 `26`；
经批准更新后出现的新增工具，只有在三份 catalog 与结果表全部一致时才可接受。

## 2. Shell 与 SDD 纪律

所有标为 Bash 的 fence 都使用 `/bin/bash -euo pipefail` 执行，不把它们直接交给
默认 zsh。zsh 的 `path` 是与 `PATH` 联动的特殊参数；循环变量使用
`fixture_path` 等普通名称。

SDD 的 brief 必须使用 helper 的第三个 `OUTFILE` 参数：

```text
scripts/task-brief PLAN_FILE TASK_NUMBER OUTFILE
```

不得把 helper stdout 重定向到它管理的 brief 文件。每次执行生成唯一
`RUN_STEM`，brief 与 report 使用同一个 stem：

```bash
RUN_STEM="modeling-run-YYYYMMDD-HHMMSS-task-N"
BRIEF=".superpowers/sdd/${RUN_STEM}-brief.md"
REPORT=".superpowers/sdd/${RUN_STEM}-report.md"

test ! -e "$BRIEF"
test ! -e "$REPORT"
/bin/bash "$TASK_BRIEF_HELPER" "$PLAN_FILE" "$TASK_NUMBER" "$BRIEF"
test -s "$BRIEF"
```

dispatch 时显式传递该 `BRIEF` 和 `REPORT`。agent 完成后必须执行
`test -s "$REPORT"`；不得把旧的通用 `task-N-report.md` 当成本次报告。

仓库自身 gate 与后文官方 MCP source/config harness 是两条不同的环境边界。
`scripts/checks.sh` 必须在 `PYTHONDONTWRITEBYTECODE` 后导出 `UV_NO_EDITABLE=1`，并在
vendor generate 与 `--check` 都成功后执行：

```bash
"$UV_BIN" sync --frozen --python 3.13 --reinstall-package blender-codex
```

这样 tmp-cwd console entrypoint 与测试读取的是当次 vendor 生成后的
site-packages package snapshot，不依赖 editable `.pth`。不得用 `chflags`、
`PYTHONPATH` 或减少/跳过 369 个测试来规避 worktree 的 `UF_HIDDEN` sweep。
该实施环境事件记为 `POSTPLAN-ENV-01`，仅用 prose 记录，不加入第 11 节的 24 个
`MODEL-*` issue，也不写入 audit CLI 的 literal issue-ID 字段。

## 3. Preflight 与精确写入范围

启动 recorder 后、任何 Blender 写入前，验证：

1. `127.0.0.1:9876` 恰有一个 Blender listener，并记录 PID；
2. `bpy.data.filepath == ""`，当前是 unsaved factory scene；
3. mode、factory object exact set、active/selected 状态和 `VIEW_3D` 均符合计划；
4. 本次所有目标 collection、object、mesh、curve、material、camera、light、
   image、library 与 sentinel 均不存在；
5. fixture 和 run root 通过 `lstat`、UID、mode、普通文件/目录及 hash 检查。

计划必须逐名列出允许创建或修改的 datablock，不能只用 `Lamp_*` 一类模式表示范围。
允许的 Scene、World、camera、render 和 color-management 设置也必须逐项列出。
factory 数据和 allowlist 之外的既有对象不得修改。

每个 mutating phase 在第一次写入前重新断言：

- 所有前置 phase 的 exact object/material/data/parent set；
- 本 phase 新目标全部不存在；
- filepath、sentinel、mode、collection 和 run-root 身份仍匹配；
- 不存在意外 `.001` 名称。

最终结构验收使用 exact set、data 名称、parent chain、collection membership、
active/selected、library、missing-file 路径和明确排除 ground 后的数值 bounds。
summary 工具只能作为交叉验证，不能替代 exact assertion。

## 4. Locale 与场景身份

不要按本地化 display name 查找 Blender 内置节点。必须按稳定 RNA type 查找，并
断言唯一：

- Principled shader：`node.type == "BSDF_PRINCIPLED"`；
- World background：`node.type == "BACKGROUND"`。

由本次运行创建的名称必须使用计划中的固定 ASCII 名称。

`bpy.data.is_dirty` 只记录为 observation，不参与场景身份或 phase precondition。
场景身份由空 filepath、run sentinel、exact object/material/data set、parent chain、
collection membership 和 active/selected 状态共同证明。

## 5. Transactional phase 与恢复

每个 mutating phase 视为一次事务。发生异常时必须按以下顺序处理：

1. 立即写入失败 end event，保留原始 symptom；
2. 在任何恢复动作前写入当时的 verbatim first hypothesis，不得事后改写；
3. 记录是否已经产生 partial state；
4. 不在原 session 中删除、补写或继续；
5. 确认它仍是 unsaved disposable scene 后退出该 Blender GUI，不保存；
6. 等待旧 listener 消失，重新启动 factory scene，并验证恰有一个新 listener；
7. 完整重跑 preflight，再从 Phase 1 全量 replay 一次；
8. recovery 使用新的 event ID，设置正整数 `attempt` 并引用 `recovery_of`。

同一失败再次出现时停止盲目重试，保留两次证据并进入根因分析。不得用 `.001`
对象、局部删除或强制修改 dirty flag 掩盖 partial state。

## 6. Interpreter、fixture 与文档查询 contract

所有 source/config harness 使用解析后的绝对 `UV_BIN`、Python 3.13 和 Server
实际依赖边界：

```bash
"$UV_BIN" run --quiet --no-project --python 3.13 \
  --with 'mcp[cli]>=1.2.0,<2' \
  --with-editable "$MCP_SOURCE_DIR/mcp" \
  python -
```

命令在 `/bin/bash -euo pipefail` 下运行。执行后重新验证固定 checkout clean，
且没有生成 `uv.lock`。

断言返回字段前先读固定源码的响应 contract；官方 API 搜索结果字段是 `hits`，
不得猜测为 `results`。Cylinder operator 的已验证查询为：

```text
bpy.ops.mesh primitive_cylinder_add
```

不要发送已知返回零结果的自然语言拆分形式。

Blender 保存时可能丢弃 zero-user image。需要在保存后仍存在的受控 missing-image
fixture，保存前设置 `use_fake_user=True`，然后重新打开文件验证 image 和 missing
路径。已有 fixture 保持不变；需要恢复时创建新的 derived fixture，并只对失败工具
重试一次。

## 7. Blender 5.2 与上游限制

在 Phase 3 的其他写入前，从当前 Blender 运行时枚举 render engine，确认目标值
存在，赋值后立即读回。Blender 5.2 的实测 EEVEE 值是 `BLENDER_EEVEE`。

固定上游 thumbnail 实现仍包含旧的 `BLENDER_EEVEE_NEXT` 分支；该字符串不是
Blender 5.2 的 render-engine 值。此分支在 5.2 上不会自动降低 EEVEE samples。
调用 thumbnail 前后记录实际 engine、render samples、viewport samples 和耗时，
但不修改固定上游源码。

area 和 window screenshot 从第一次调用起都使用
`size_limit_in_bytes=48_000`。更大的 base64 response 可能被当前非阻塞 bridge
截断；48 KB 是运行规避措施，不代表上游传输问题已被仓库修复。返回值仍须验证为
非空 PNG 和合理尺寸。

## 8. Render scratch

render 前从 Blender 读取 `bpy.app.tempdir` 并先做 `realpath`。安全检查区分两类路径：

- canonical temp root 以上的系统祖先只要求正常解析为既有普通目录；不得要求它们
  属于当前 UID，也不得创建、chmod 或替换它们；
- canonical temp root 及本次使用的所有下级路径必须由当前 UID 所有，逐层
  `lstat`，不得含 symlink。

最终 scratch 固定为 canonical temp root 下的 `blender_mcp`。若它不存在，先记录
absence，再只创建这一层 mode `0700` 目录；若已存在，则必须是当前 UID 所有的
普通非 symlink 私有目录，否则停止。

每次 render 使用包含 `RUN_STEM` 和唯一随机后缀的 basename。调用前分别对官方
source target 和 run-root copy target 执行 `lstat`，两者都必须不存在；不能用
`exists()` 代替，因为 broken symlink 也必须拒绝。

调用后验证：

1. 返回路径的 `realpath` 恰等于预期 source target；
2. basename 和 canonical parent 恰好匹配；
3. source 经 `lstat` 是当前 UID 所有、非 symlink、非空的普通文件；
4. 文件头是 PNG magic；
5. 记录 source 的 `sha256`；
6. copy parent 已通过逐层 ownership/symlink 检查；
7. 使用 exclusive-create 方式复制，不覆盖既有路径；
8. copy 经同样的 `lstat`、PNG 和 ownership 检查；
9. source 与 copy 的 `sha256` 完全相等；
10. `bpy.data.filepath`、原 render filepath 和 unsaved 状态保持不变。

render 失败但留下 partial file 时，不删除或复用它；记录路径、size、magic 和 hash，
recovery 使用新的唯一 basename。

## 9. 单一时钟与证据

在读取 payload、catalog 或 Blender 状态前，启动
`scripts/official_blender_mcp_audit.py record` 的一个长生命周期进程。一个 run
只能有一个 recorder 和一个由它生成的 `clock_id`；不得为每个 event 启动新的
Python 进程。

使用私有 FIFO 保持 recorder stdin 打开：

```bash
umask 077
JOURNAL="$RUN_ROOT/events.ndjson"
EVENT_FIFO="$RUN_ROOT/events.fifo"

test ! -e "$JOURNAL"
test ! -e "$EVENT_FIFO"
mkfifo -m 600 "$EVENT_FIFO"

"$UV_BIN" run --quiet --no-project --python 3.13 \
  python scripts/official_blender_mcp_audit.py \
  record --output "$JOURNAL" <"$EVENT_FIFO" &
RECORDER_PID=$!
exec 9>"$EVENT_FIFO"
```

通过 FD 9 发送 JSON event。Task、stage 和每次 tool call 分别使用
`scope=task|stage|call`、稳定 `event_id` 及恰好一对 `start`/`end`。唯一 Task start
必须是首个 event，唯一 Task end 必须是末个 event，所有 stage/call 都位于其间。
failure end event 必须在 recovery start event 之前包含非空 `symptom`、调用者原样
提供的 `first_hypothesis` 和 literal issue IDs；deviation 与 linked recovery end 也必须
有非空 literal issue IDs。记录 `attempt`、`recovery_of`、MCP wall 和 Blender internal
time；不推测缺失值。

结束时先发送 Task end，关闭 FD，等待 recorder 正常退出，再运行 `validate`：

```bash
exec 9>&-
wait "$RECORDER_PID"

"$UV_BIN" run --quiet --no-project --python 3.13 \
  python scripts/official_blender_mcp_audit.py validate \
  --journal "$JOURNAL" \
  --audit "$AUDIT_FILE" \
  --live-catalog "$LIVE_CATALOG" \
  --source-catalog "$SOURCE_CATALOG" \
  --config-catalog "$CONFIG_CATALOG"
```

只有 validate 成功后才能报告 coverage、duration 或 recovery 结论。stage
monotonic duration 减去 MCP wall 的剩余部分只能称为
`unattributed orchestration`，不能称为 LLM time。

潜在异常阈值为：summary/docs/navigation `5,000 ms`、screenshot `10,000 ms`、
thumbnail `30,000 ms`、viewport `60,000 ms`。首次成功调用超过对应阈值时，保留
首次证据并执行一次同条件复测；render 复测必须换新 basename。未超过阈值不得仅为
“看起来慢”而重试。

## 10. Soft process diagnostic 与正常清理

Task 前后各记录一次只读 `ps` snapshot，统计与当前 Codex/App Server 相关的
uv launcher 和 `blender-mcp` child 数量及 RSS；同时记录
`127.0.0.1:9876` 的唯一 listener。snapshot 只能用于比较 count/RSS delta，
不能从进程数量反推每次 tool call 都启动了新 Server。

运行中不得逐个终止 idle stdio Server；它们没有额外监听 `9876`，且单独终止可能
破坏仍在使用的 session。等所有 agents、报告、journal 和 Git 工作都完成后，如需
清理 retained pairs，正常退出并重新启动 Codex Desktop，然后重新记录 snapshot。

`MODEL-RUN-10` 只得到 soft diagnostic 和正常 host-lifecycle 清理建议；现有证据
不足以证明 root/subagent-session 因果映射。

## 11. 问题处置清单

下表恰好覆盖 approved audit 的 24 个唯一 issue ID。Disposition 说明未来运行中的
责任边界，不改写历史证据。

| Issue ID | Disposition | 规则 |
|---|---|---|
| `MODEL-SHELL-01` | `prevented_by_runbook` | 显式 Bash，避开 zsh `path` 特殊参数 |
| `MODEL-SDD-01` | `prevented_by_runbook` | helper 第三个 `OUTFILE`，禁止 stdout 覆盖 brief |
| `MODEL-SDD-02` | `prevented_by_runbook` | run-scoped brief/report stem 与前后存在性检查 |
| `MODEL-RUN-01` | `prevented_by_runbook` | 使用唯一稳定 RNA type，不依赖本地化 display name |
| `MODEL-RUN-02` | `prevented_by_runbook` | dirty 仅观察，exact structure 证明身份 |
| `MODEL-RUN-03` | `prevented_by_audit` | 解析 exact table 和 literal issue IDs |
| `MODEL-RUN-04` | `prevented_by_audit` | 单一 recorder、同一 clock ID 和成对事件 |
| `MODEL-RUN-05` | `prevented_by_runbook` | 绝对 uv 与 Python 3.13 |
| `MODEL-RUN-06` | `prevented_by_runbook` | missing image 使用 fake user 和 derived fixture |
| `MODEL-RUN-07` | `prevented_by_runbook` | 有效 editable dependencies 与源码确认响应字段 |
| `MODEL-RUN-08` | `mitigated_only` | 48 KB screenshot cap；上游传输根因未改动 |
| `MODEL-RUN-09` | `mitigated_only` | 安全创建最终 scratch parent；上游未自动创建 |
| `MODEL-RUN-10` | `diagnostic_only` | 只记录 process delta 并正常退出 host |
| `MODEL-RUN-11` | `future_prevention_only` | 未来 failure 必须先持久化 first hypothesis；历史缺口保留 |
| `MODEL-PLAN-01` | `prevented_by_runbook` | 运行时发现并读回 `BLENDER_EEVEE` |
| `MODEL-PLAN-02` | `prevented_by_runbook` | transactional precondition、discard 和 full replay |
| `MODEL-PLAN-03` | `prevented_by_runbook` | 精确声明 Scene/World/render/datablock 写入范围 |
| `MODEL-PLAN-04` | `prevented_by_runbook` | exact sets、parents、data、bounds 与 summary 交叉验证 |
| `MODEL-PLAN-05` | `prevented_by_runbook_and_audit` | one-clock journal 与机器校验 |
| `MODEL-PLAN-06` | `prevented_by_runbook` | 使用 source-proven operator query |
| `MODEL-PLAN-07` | `prevented_by_audit` | 动态 catalog equality 和结果表 `Counter` |
| `MODEL-PLAN-08` | `prevented_by_runbook` | canonical containment、lstat、unique absent target 和 hash |
| `MODEL-PLAN-09` | `warning_only` | 记录 EEVEE/sample 兼容性，不修改固定上游 |
| `MODEL-PLAN-10` | `prevented_by_runbook_and_audit` | immediate events、阈值复测、partial artifact 保留和验证 |

`MODEL-RUN-08`、`MODEL-RUN-09` 只被规避；`MODEL-RUN-10` 只被观察；
`MODEL-PLAN-09` 只记录兼容性警告。它们都不是仓库内修复。
`MODEL-RUN-11` 只能预防未来证据缺口，不能补造已丢失的历史 hypothesis。

## 12. 完成检查

- [ ] 官方 source pin、SDK boundary、Blender version 和动态 catalog equality 通过；
- [ ] recorder 在任何工作读取前启动，Task/stage/call events 全部成对；
- [ ] 唯一 listener、factory scene、target absence 与 exact write allowlist 通过；
- [ ] locale-safe RNA、dirty observation 和 transactional recovery 规则已执行；
- [ ] fixture、docs query、48 KB screenshot 与 Blender engine contract 通过；
- [ ] render source/copy 的 absence、containment、lstat、PNG 和 hash 通过；
- [ ] exact structural assertion 与所有官方工具结果通过；
- [ ] `validate` 通过后才形成结论；
- [ ] Task 前后 process snapshot 已记录，未进行 mid-run individual termination；
- [ ] agents、reports、journal 和 Git 状态全部收口后再正常退出或重启 Codex Desktop。
