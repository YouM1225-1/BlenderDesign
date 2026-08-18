# Phase 0 只读通道安装

本文只安装仓库自研的只读通道。需要完整 Blender 操作能力时，使用[官方 Blender MCP 分发](distribute-official-blender-mcp.md)。

## 前置条件

- macOS Apple Silicon；
- Python `>=3.13,<3.14`；
- `uv`；
- Blender 5.2.x 为当前验证基线；
- Codex CLI。

## 安装依赖

在仓库根目录执行：

```bash
uv sync --frozen --python 3.13
```

## 打包 Blender Bridge

先生成 vendored protocol，再打包 Extension：

```bash
uv run --frozen python scripts/vendor_protocol.py
(cd bridge && zip -r ../blender_codex_bridge.zip . -x '*__pycache__*')
```

在 Blender 中打开 `Edit → Preferences → Get Extensions → Install from Disk…`，选择仓库根目录的 `blender_codex_bridge.zip` 并启用。

## 注册 MCP Server

在仓库根目录执行：

```bash
codex mcp add blender-codex -- uv --directory "$(pwd)" run --frozen blender-codex-server
```

该 Server 只暴露三个只读工具，不需要开放任意 Python 执行权限。

## 连接与验证

1. 正常启动 Blender。
2. 在 3D 视图按 `N` 打开侧栏。
3. 进入 `Codex` 页签并点击“允许 Codex 连接”。
4. 在 Codex 中调用 `get_blender_status`。
5. 使用返回的 `instance_id` 调用 `get_scene_summary`。

不需要连接 Blender 时，`describe_capabilities` 仍可离线返回 Server 能力。

## 卸载

先在 Blender 的 `Codex` 面板中断开连接，再禁用或移除 Extension。使用 Codex CLI 删除名为 `blender-codex` 的 MCP 注册项。

## 排障

| 现象 | 检查 |
|---|---|
| 未发现实例 | 确认已在 Blender 面板中允许连接 |
| `BRIDGE_UNAVAILABLE` | Bridge 已断开、正在关闭或 discovery 记录过期 |
| `ENVELOPE_VERSION_MISMATCH` | 重新生成并安装与当前仓库一致的 Extension |
| `version_warning` | 当前 Blender 版本不是验证基线；只读结果仍会明确标注版本状态 |

完整开发门禁见[验证说明](validation.md)。
