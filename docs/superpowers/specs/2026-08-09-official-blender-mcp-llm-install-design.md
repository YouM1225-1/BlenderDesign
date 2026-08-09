# Blender Lab 官方 MCP：LLM 安装设计

日期：2026-08-09  
状态：用户已批准  
适用版本：本仓库技术版本保持 `0.1.0`

## 1. 目标

为 LLM 提供一份可直接执行的官方 Blender MCP 安装手册，使其能在联网的
macOS Apple Silicon 主机上完成检测、备份、安装、配置、验证、更新和回滚。
支持 Blender 5.2 LTS 及以上版本；5.2 是实测基线，更高版本必须通过安装后
冒烟验证后才可报告为兼容。

安装目标是 Blender Lab 官方 MCP，不安装本仓库的自定义
`blender-codex-server` 或 `blender_codex_bridge`。本仓库现有 ROADMAP、
`docs/install.md`、历史 audit 和 evidence 保持冻结。

## 2. 交付范围

仓库内实现阶段只新增：

- `docs/install-official-blender-mcp.md`：面向 LLM 的操作手册。

不新增通用安装脚本。LLM 按手册调用现有 Git、uv、Blender CLI、Codex CLI
和安全文件编辑能力，因此可根据实际路径与现有 TOML 结构做精确修改，避免
维护一套会覆盖用户配置的安装器。

手册属于 operational、non-normative 文档，不纳入既有 Phase 0 attestation。
若未来要把它提升为正式安装合同，需建立新的 attestation 链。

仓库外还需按新手册对当前机器执行一次真实修复和验收：在无需重装扩展时开启
Online Access、验证官方 Server 配置、重启所需进程并完成安全只读调用。真实
执行结果只作为本轮运维报告，不回写历史 evidence。

## 3. 已确认约束

- 平台：macOS Apple Silicon。
- Blender：`>=5.2`；5.2 为唯一当前实测基线。
- 安装时允许联网。
- 允许流程在修改前备份，然后自动修改 `~/.codex/config.toml`。
- 允许安装并启用官方 Blender 扩展。
- 允许在备份 `userpref.blend` 后自动开启 Blender Online Access。
- 允许在显式更新流程中自动接受上游新增、删除或重命名的工具。
- 不在每次启动时静默跟随上游 `main`。
- 不修改、移动或删除用户 `.blend` 文件。

## 4. 当前事实与待修问题

### 4.1 当前官方组件

- 官方源码：`https://projects.blender.org/lab/blender_mcp.git`。
- 当前已核验提交：
  `4309a39646e644261624bfcd2bca669b343b7621`。
- 官方 Python distribution：`blender-mcp==1.0.0`。
- 官方 Blender Extension：`id="mcp"`、`version="1.0.0"`。
- 当前上游 `main` 与上述提交一致，但该提交无签名且不是 release tag；安装手册
  以完整 commit SHA 固定来源，并记录这一 provenance 边界。

### 4.2 当前机器状态

- Blender 5.2 中的官方 `mcp` 扩展已安装、启用，内容与当前 checkout 一致；
  因此首次修复应跳过扩展重装。
- 扩展默认 `use_autostart=true`，但当前 `bpy.app.online_access=false`，官方扩展
  会直接拒绝启动 localhost bridge。这是当前无法连接 `localhost:9876` 的直接
  阻断项。
- Codex 已存在名为 `blender` 的官方 MCP 配置及 26 个工具。
- 本仓库自定义 MCP Server、uv tool 和 Blender 扩展均已卸载。

### 4.3 已知安装缺陷

- 上游依赖只声明 `mcp[cli]>=1.2.0`，但源码仍导入 SDK v1 的
  `mcp.server.fastmcp.FastMCP`。默认解析到 MCP SDK v2 会以
  `ModuleNotFoundError` 启动失败。
- 本机 `uv` 位于 `~/.local/bin/uv`，不一定在 `PATH`；手册不得仅依赖
  `command -v uv`，也不得硬编码用户名。
- Blender Extension CLI 的 exit code 不能单独证明安装成功；逐包失败后仍可能
  返回成功，必须做状态复核。
- Blender GUI 自动化曾无法取得窗口状态，因此手册必须提供完整 CLI 路径，
  不能把 GUI 可访问性作为唯一安装路径。

## 5. 架构与数据流

```text
Codex
  -> 官方 blender MCP Server（stdio）
  -> localhost:9876
  -> Blender 官方 mcp Extension
  -> 当前 Blender 场景
```

官方 Server 与 Blender Extension 来自同一固定上游 checkout。Server 使用独立
uv 解析环境，不共享本仓库自定义 Server 的 MCP SDK v2 环境。

手册采用以下阶段：

1. preflight；
2. 状态判定与 no-op；
3. 备份；
4. 固定或更新上游 checkout；
5. 构建、安装及启用 Blender Extension；
6. 开启 Online Access 并确认 autostart；
7. 写入 Codex MCP 配置；
8. 重启并验证；
9. 必要时回滚。

## 6. Preflight 与状态判定

LLM 必须先解析并记录实际值，不假设用户名或安装位置：

- Blender 可执行文件；
- 精确 Blender 版本和 CPU 架构；
- Codex CLI；
- uv；
- Git；
- `CODEX_HOME` 与 `config.toml`；
- Blender 版本对应的配置、扩展目录和 `userpref.blend`；
- 上游 checkout 目录。

若 Blender 小于 5.2、平台不符、目标路径为 symlink/非本 UID 所有、配置不能
解析或关键工具缺失，流程在任何写入前停止。

状态判定遵循最小修改：

- checkout 已在目标提交且 clean：不 fetch、不 checkout；
- 扩展 ID、版本、文件树和启用状态一致：不重装；
- Online Access 与 autostart 已满足：不写 `userpref.blend`；
- Codex stanza、工具集合和 namespace 已一致：不写 config、不创建重复备份。

Blender 正在运行且需要写偏好时，LLM 要求用户先保存并正常退出；不得强制
终止 Blender，也不得在运行中的 GUI 与另一个 CLI 进程之间竞争写偏好。

## 7. 来源、依赖与配置

### 7.1 上游固定

首次安装固定完整提交
`4309a39646e644261624bfcd2bca669b343b7621`。checkout 路径由 LLM 在目标主机
解析并写入配置，不能复制本机的 `/Users/yeminjie/...` 路径。

### 7.2 SDK 隔离

Server 启动必须同时包含：

- `uv run --quiet --no-project`；
- `mcp[cli]>=1.2.0,<2`；
- 指向固定 checkout 的 `--with-editable <checkout>/mcp`；
- `blender-mcp` entry point。

`<2` 只属于官方 Server，不得传播到本仓库自定义 SDK v2 Server。

### 7.3 Codex 配置

手册只允许修改：

- `[mcp_servers.blender]`；
- `[mcp_servers.blender.env]`；
- `features.code_mode.direct_only_tool_namespaces` 中的 `mcp__blender` 成员。

配置要求：

- command 是实际解析出的 uv 绝对路径；
- args 包含 `--no-project`、SDK `<2` 和固定 checkout；
- `BLENDER_PATH` 指向实际 Blender 可执行文件；
- startup timeout 为 20 秒，tool timeout 为 60 秒；
- `enabled_tools` 与已验证 Server catalog 集合完全相等；
- `omit_tools_from=[]`；
- 不写 `disabled_tools` 或逐工具 override；
- `mcp__blender` 只走 direct tool path。

本用户已明确接受完整目录、自动接受更新目录及其中任意 Python 工具的风险，
因此可保留 `default_tools_approval_mode="approve"`。该授权不得默认复制给其他
用户或其他机器；新的操作者必须重新明确接受。

## 8. Blender Extension 与 Online Access

Extension 由固定 checkout 构建并先执行 Blender 原生 validate。安装前解析 ZIP
根 manifest，确认 `id="mcp"`、期望版本和最低 Blender 版本。

当前机器的内容一致时跳过重装。新安装或真实升级时，必须在 Blender 关闭后：

1. 备份现有扩展目录和 `userpref.blend`；
2. 用 Blender Extension CLI 安装并启用；
3. 用 Blender 自身 API 开启 Online Access；
4. 保存偏好；
5. 重新读取并验证扩展、Online Access、autostart 和端口配置。

网络监听必须保持 `localhost:9876`，不得设置为 `0.0.0.0` 或外部接口。

Blender CLI 报成功后仍须验证：

- `extension list` 中存在目标包；
- 实际 manifest ID/version；
- 安装文件树与目标 ZIP 一致；
- 模块在启用列表中；
- Online Access 为 true；
- autostart 为 true。

## 9. 备份、并发与回滚

备份目录必须为当前用户所有、模式 `0700`；配置和偏好备份模式为 `0600`。
记录每个文件的原始 bytes、SHA-256、mode、device/inode、修改后预期 SHA、旧
MCP stanza、旧工具集合、旧 namespace membership、旧扩展版本和旧提交。
日志不得输出完整 Codex config、环境变量值或其他可能包含凭据的原始内容。

写 Codex config 前后均使用 TOML parser 校验。写入前再次比较 SHA 和 inode；
检测到并发变化立即停止。同目录 mode `0600` 临时文件解析成功后才能原子替换。

回滚规则：

- 当前 SHA 等于安装器记录的 post-image SHA：允许原子恢复完整 pre-image；
- 当前 SHA 已变化：禁止整文件覆盖，只恢复原 `blender` stanza 和本次新增的
  namespace membership；
- 原 stanza 不存在：只删除本次创建的 stanza；
- 原 stanza 存在：恢复原值，不使用简单 `mcp remove` 代替迁移回滚；
- 扩展升级失败：重装备份扩展内容并恢复原 `userpref.blend`；
- 不清理共享 uv cache，不删除 checkout 中用户新增内容，不接触 `.blend` 文件。

## 10. 上游更新与自动接受工具

自动接受只发生在显式更新流程中，不在每次 Server 启动时静默发生：

1. 查询上游 `main` 的新 commit；
2. 记录旧 commit、旧 catalog 和全部 pre-image；
3. checkout 新 commit；
4. 构建并 validate 新 Extension；
5. 在修改 Codex 配置前独立启动新版 Server；
6. 获取真实 catalog，验证名称唯一且 Server 可握手；
7. 自动把 `enabled_tools` 更新为新 catalog 的精确集合，包括新增、删除和重命名；
8. 安装 Extension、写配置、重启 Codex；
9. 验证 Server catalog、effective config 和新任务模型目录三者集合全等；
10. 任一步失败则恢复旧 commit、旧 Extension、旧 config 和旧工具集合。

更新日志必须显示 commit 变化和工具 diff，但本用户无需逐工具确认。新的 commit
在验证成功后成为下一次执行的固定 pin。

## 11. 验证与成功标准

### 11.1 来源与运行时

- checkout HEAD 等于记录的 pin，Git worktree clean；
- MCP SDK major 小于 2；
- `FastMCP` import 成功；
- 独立 Server handshake 成功；
- checkout 内没有因安装流程意外生成 `uv.lock`。

### 11.2 Blender

- Blender 精确版本 `>=5.2`；
- Extension 已安装、启用；
- Online Access、autostart 均开启；
- Blender 运行后 `localhost:9876` 可连接；
- 高于 5.2 的版本通过 Extension load、listener 和只读调用后才标记兼容。

### 11.3 Codex

- 修改后的 TOML 可解析；
- `codex mcp get blender --json` 与目标 transport、args、env、timeouts 一致；
- App Server 的 `config/read` 与 `mcpServerStatus/list` 分别确认 effective config
  和 Server 状态；
- Server catalog、`enabled_tools` 和 fresh/reloaded task 的模型工具集合完全相等；
- 当前已知安全只读工具 `get_blendfile_summary_datablocks` 调用成功。

当前 Codex CLI 不支持 `codex --strict-config mcp get`，手册不得把该命令列为
验收步骤。

安装 smoke 不调用 `execute_blender_code`、`execute_blender_code_for_cli` 或 render。
安装成功不等于所有工具稳定；既有 screenshot 长序列缺陷和 deferred render
`SIGABRT` 风险继续作为已知边界披露。

## 12. 手册写作合同

最终手册必须：

- 明确标注“LLM 执行手册”和官方/自定义边界；
- 不包含用户名或机器绝对路径；
- 每一步包含目的、命令、预期结果、停止条件和回滚入口；
- 将“配置存在”“Server running”“模型看到工具”“只读调用成功”分成四层验证；
- 明确 Online Access、任意 Python 和无鉴权 localhost TCP 的风险；
- 对当前机器提供 no-op 分支，只修复 Online Access 和连接状态；
- 对新机器提供完整安装分支；
- 对上游更新提供自动 catalog 同步与可回滚分支。

## 13. 非目标

- 不安装或重新启用本仓库自定义 MCP Server/Bridge；
- 不安装 Blender 本体；
- 不支持 Intel Mac、Windows 或 Linux；
- 不提供离线 wheelhouse；
- 不自动暴露 TCP 端口到外网；
- 不以 GUI 自动化作为唯一成功路径；
- 不修改冻结 ROADMAP、既有安装文档或历史证据；
- 不新增 pytest，以保持既有 337 unit、32 contract、369 full gate count。
