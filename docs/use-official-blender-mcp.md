# 官方 Blender MCP 使用

本文适用于仓库当前 manifest 描述的官方 Blender MCP 分发。安装、验证和回滚必须使用 [`install-official-blender-mcp` skill](../plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md)，不要使用旧源码 checkout 或手工拼接依赖。

## 支持边界

- macOS Apple Silicon；
- Blender `>=5.2.0,<5.3.0`；
- 本地 Python `3.13.13`；
- uv `0.12.2`；
- Bridge `localhost:9876`；
- 工具目录与固定产物以 `plugins/blender-mcp-installer/artifacts/manifest.json` 为准。

安装器不会启动或关闭 Blender，也不会打开或修改项目 `.blend` 文件。需要变更 Blender 配置、修复或回滚时，先保存工作并正常退出 Blender。

## 推荐工作流

1. 处理安装状态或故障时使用安装 skill 的 `inspect`；仅检查时不注册或安装。已连通的建模任务直接从场景 summary 开始。
2. 用户要求安装时复用已有四项默认授权，执行一次 `install`；明确撤销任一授权时停止相关安装。
3. 等用户正常启动选定的 Blender；已有确认或当前只读状态足以证明就绪时直接执行 `verify`，验证四层链路。
4. 建模前用 summary 了解场景，再执行请求所需的导航、代码或渲染操作。
5. 发生安装问题时保留 receipt；确认 Blender 已关闭后按 receipt 修复或回滚，仍在运行时请用户保存并正常退出。

重复安装在目标状态完全一致时应为 no-op，不应重复修改 Codex 或 Blender 配置。

## 工具使用原则

- 优先使用 summary、对象详情和文档查询工具确认当前状态。
- GUI 工具依赖当前 Blender 窗口、workspace 和 area；调用前先检查窗口布局。
- `_for_cli` 工具读取磁盘上的 `.blend`，不包含 GUI 中尚未保存的修改。
- `execute_blender_code` 修改当前打开场景；执行前明确选择、active object、mode 和保存边界。
- `execute_blender_code_for_cli` 使用隔离快照做批处理，不应保存回源文件。
- 渲染工具必须使用明确输出路径，并确认目录可写。
- 独立只读查询可并行；场景写入、渲染和依赖当前选择的操作顺序执行。默认逐个部件创建并截图检查，再处理材质、装配和最终视觉检查；用户明确要求一批完成时可批处理。阶段完成后自动继续，仅在用户要求逐阶段审批时暂停。

## 安全边界

完整工具目录包含任意 Python 执行。它能够访问当前用户可访问的文件和 Blender 数据，因此：

- 不执行来源不明的 Python；
- 不在生产 `.blend` 上试验破坏性脚本；
- 不把 bridge 改为局域网地址或 `0.0.0.0`；
- 不复制正常 Codex 凭据到测试 profile；
- 不把安装成功等同于所有建模操作都安全或可撤销。

## 故障处理

- Server 无法启动：重新执行 `inspect`，核对固定 Python、uv 和 manifest。
- Bridge 不可用：确认 Blender 已正常启动、Extension 已启用且端口 9876 只有预期 listener。
- GUI 工具找不到区域：先读取窗口布局，再切换 workspace 或 area。
- 长任务超时：先确认 Blender 是否仍在计算；不要并发重试同一写操作。
- 安装状态不一致：保留 receipt，正常关闭 Blender，然后使用 installer 的恢复或回滚路径。

分发的信任模型和操作入口见[官方 Blender MCP 分发与安装](distribute-official-blender-mcp.md)。
