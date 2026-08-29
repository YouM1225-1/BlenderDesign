# 项目架构

BlenderDesign 包含两套相互独立的本地 MCP 链路。它们可以并存，但不共享 Server、传输协议或权限模型。

## 官方 Blender MCP 链路

```text
Codex
  └─ STDIO → managed official Blender MCP Server
                └─ localhost:9876 → official Blender Extension
                                      └─ current Blender session
```

`plugins/blender-mcp-installer/` 提供固定产物和事务化安装器。Codex 插件本身只交付安装 skill，不是第二个 MCP Server。安装器负责：

- 核验受信 Git 提交和 `SHA256SUMS`；
- 安装固定 Python runtime、官方 Server wheel 和 Blender Extension；
- 合并受管 Codex 配置；
- 记录 receipt，支持验证、故障恢复和回滚。

官方链路暴露 manifest 中声明的完整工具目录，其中包括任意 Python 执行能力。它只绑定 `localhost:9876`，但该端口没有独立鉴权；使用者必须信任当前本机用户环境。

## Phase 0 只读链路

```text
Codex
  └─ STDIO → blender-codex-server
                └─ private Unix Domain Socket → Blender Codex Bridge
                                                   └─ SceneReader
```

Phase 0 只提供三个 MCP 工具：

- `get_blender_status`
- `get_scene_summary`
- `describe_capabilities`

Blender 用户必须在 3D 视图的 `Codex` 侧栏中显式允许连接。Bridge 为每个会话创建私有 socket 和 token；Server 通过 discovery 找到实例并校验协议、版本与响应结构。该链路不提供 Python 执行、渲染或场景写入。

## 代码分层

| 目录 | 职责 |
|---|---|
| `protocol/` | framing、envelope、错误码和版本合同 |
| `bridge/core/` | 不依赖 `bpy` 的会话、队列、路由与生命周期 |
| `bridge/blender/` | Blender UI、driver 与场景读取 |
| `server/core/` | 配置、实例发现、审计和 Bridge client |
| `server/mcp/` | MCP SDK v2 adapter 与三个只读工具 |
| `acceptance/` | checkout-only 的资产验收 P0 判定核心，不进入 wheel/sdist |
| `plugins/blender-mcp-installer/` | 官方 MCP 的固定分发与安装器 |
| `smoke/` | background、GUI、恢复与性能验证 |
| `tests/` | unit、contract 和 distribution 测试 |

## 数据与信任边界

- Phase 0 运行目录和日志位于当前用户的 BlenderCodex 应用支持目录；socket、token 和日志均受本地权限约束。
- 官方安装器会修改 Codex 配置、Blender Extension 和 Blender 用户偏好，但不会打开或修改项目 `.blend` 文件。
- `.blend` 样例和 PNG 属于仓库资产，不参与 MCP 安装器信任链。
- 除 `docs/README.md` 明确列出的资产验收演进档案外，历史设计和审计只存在于 Git 历史；两者都不作为当前运行时输入。
