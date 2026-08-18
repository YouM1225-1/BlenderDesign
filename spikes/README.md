# Compatibility spikes

`spikes/` 保存仍可运行的兼容性探针，不属于生产入口。

## MCP SDK v2

`mcp-sdk-v2/` 验证 SDK client、真实 STDIO、协议版本、封闭 schema 和 structured content。生产行为由 `tests/contract/` 固定；spike 只用于升级 SDK 或 Codex Host 前的独立探测。

## Official Blender MCP

`official-blender-mcp/verify_cli.py` 用于检查官方 Server 的 CLI 启动和工具目录。正式安装、验证与回滚使用仓库插件 skill，不从 spike 启动生产环境。

运行 spike 时使用临时 profile，不复制正常 Codex 凭据，也不修改项目 `.blend` 文件。
