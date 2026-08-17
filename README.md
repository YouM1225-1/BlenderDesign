# BlenderDesign

面向 Codex 与 Blender 的本地 MCP 集成与建模实验仓库。目前同时维护两条边界明确的链路：

- **官方 Blender MCP 分发**：为 Blender Lab 官方 MCP 提供经过固定版本、完整性校验和事务化回滚的 Codex 安装器。
- **Phase 0 只读通道**：仓库自研的会话授权型 Blender Bridge，仅暴露状态、场景摘要和能力描述三个只读工具。

仓库还包含一个 18W USB-C 电源适配器的 Blender 样例与渲染图，用于验证实际建模工作流。

![A1720 18W USB-C Adapter](A1720_USB_Hero.png)

## 当前状态

截至 2026-08-18，仓库中的主要产物如下：

| 产物 | 状态 | 当前边界 |
|---|---|---|
| 官方 Blender MCP 安装器 | 已打包并通过仓库验收 | macOS Apple Silicon、Blender `>=5.2.0,<5.3.0`、Python `3.13.13`、uv `0.12.2` |
| 官方 MCP 工具目录 | 26 个工具 | 包含场景检查、UI 导航、文档查询、渲染和任意 Python 执行 |
| 自研 Phase 0 通道 | 已实现并完成验收 | 只读、Unix Domain Socket、逐会话授权；Server 版本 `0.1.0` |
| A1720 建模样例 | 已纳入仓库 | `A1720_18W_USB-C_Adapter.blend` 及两张 PNG 渲染图 |

官方分发的精确上游提交、工具列表和产物哈希以
[`plugins/blender-mcp-installer/artifacts/manifest.json`](plugins/blender-mcp-installer/artifacts/manifest.json)
为准。

## 选择哪条链路

### 官方 Blender MCP

适合需要完整 Blender 操作能力的场景。仓库提供的是 **skill-only 安装适配器**，不会再启动第二套 MCP Server；安装后的 Codex 通过本地 STDIO 连接官方 Server，官方 Server 再通过 `localhost:9876` 连接 Blender Extension。

安装器支持：

- `inspect`：只读检查 Codex、Blender 和现有安装状态；
- `install`：安装固定产物并记录 receipt；
- `verify`：在用户正常启动 Blender 后验证完整链路；
- `rollback`：按 receipt 恢复安装前状态。

安装会修改 Codex 配置和 Blender 用户配置，并启用包含任意 Python 执行在内的完整工具集。不要直接运行源码 checkout；请按受信提交、私有 worktree 和校验和边界执行：

- [安装器操作说明](plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md)
- [分发与信任边界](docs/distribute-official-blender-mcp.md)
- [安装后安全建模手册](docs/use-official-blender-mcp.md)

### Phase 0 只读通道

适合只需要读取 Blender 状态、又不希望开放代码执行或场景写入的场景。它提供：

| MCP 工具 | 用途 |
|---|---|
| `get_blender_status` | 枚举 Blender 实例及 Bridge、版本和场景状态 |
| `get_scene_summary` | 返回对象统计、单位、collection、受管对象和场景哈希 |
| `describe_capabilities` | 返回 Server、协议、Blender 基线和已连接实例能力 |

连接由用户在 Blender 的 3D 视图侧栏中显式开启：按 `N` → `Codex` → “允许 Codex 连接”。完整安装和 Codex 注册步骤见 [Phase 0 安装说明](docs/install.md)。

## 开发环境

项目 Python 包要求 `>=3.13,<3.14`，依赖由 `uv.lock` 固定。

```bash
uv sync --frozen --python 3.13
```

本地启动自研 MCP Server：

```bash
uv run --frozen blender-codex-server
```

仓库唯一的完整验证入口是：

```bash
bash scripts/checks.sh
```

该脚本依次执行依赖同步、Ruff、严格 mypy、协议 vendor 一致性、嵌套导入 smoke，以及 unit、contract 和 distribution 测试。当前脚本按仓库验证机配置使用 `/Users/yeminjie/.local/bin/uv`；在其他机器运行前需先使该路径可用或按本机环境调整脚本。

## 仓库结构

```text
protocol/                      MCP 与 Bridge 共用的 framing/envelope 协议
bridge/core/                   与 bpy 解耦的会话、队列、路由和生命周期逻辑
bridge/blender/                Blender Extension 的 UI、driver 与场景读取层
server/core/                   discovery、配置、审计和 Bridge client
server/mcp/                    Phase 0 MCP SDK v2 adapter
plugins/blender-mcp-installer/ 官方 Blender MCP 的 Codex 插件、安装器与固定产物
scripts/                       构建、vendor、审计和验证脚本
smoke/                         Blender background/GUI/E2E smoke 工具
tests/                         unit、contract 与 distribution 测试
docs/                          规范、计划、安装手册、审计和机器证据
spikes/                        MCP SDK 与 Codex Host 的兼容性验证代码
```

## 关键文档

- [文档导航与权威层级](docs/README.md)
- [需求规格说明书](Blender-Codex-%E9%9C%80%E6%B1%82%E8%A7%84%E6%A0%BC%E8%AF%B4%E6%98%8E%E4%B9%A6-v1.md)
- [Phase 0 验收报告](docs/audits/phase0-validation-report.md)
- [官方 MCP 分发验收](docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md)
- [官方 MCP 最终认证](docs/audits/2026-08-17-official-blender-mcp-final-certification-v3.md)
- [开发路线与历史状态](docs/ROADMAP.md)

`docs/audits/` 与 `docs/audits/evidence/` 保留了不同 revision 的不可变审计和机器证据。阅读历史结论时，应以文件标注的提交、作用域和 superseded 状态为准，不要把旧快照当作当前实现。
