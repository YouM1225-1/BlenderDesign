# 验证说明

## 自动化门禁

仓库唯一的完整验证入口是：

```bash
bash scripts/checks.sh
```

该入口依次验证：

- frozen 依赖同步；
- Ruff；
- strict mypy；
- 插件结构（提供 `PLUGIN_CREATOR_ROOT` 时）；
- core/protocol 不导入 `bpy`；
- protocol vendor 生成与一致性；
- 嵌套导入 smoke；
- unit 与 contract 测试；
- 官方分发 installer 测试。

脚本按 `UV_BIN`、`PATH`、`$HOME/.local/bin/uv` 的顺序解析 uv。

## Blender 验证

Background smoke：

```bash
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup --python-exit-code 1 \
  --python smoke/bg_check.py
```

GUI、恢复和 100k 场景验证由 `smoke/runner.py` 与 `smoke/e2e.py` 提供。正式运行要求 Git 工作树完全干净，并对当前受跟踪的 Python、shell、TOML、`pyproject.toml`、`uv.lock` 和生成的 vendored protocol 建立有界哈希清单。历史计划或审计文档不参与运行时 provenance。

## 官方分发验证

安装器测试覆盖：

- manifest 和 checksum 的封闭解析；
- detached commit 与干净作用域；
- Python、uv、Codex 和 Blender host 探测；
- Codex 配置与 Blender Extension 的事务化安装；
- receipt、故障恢复、no-op 和 rollback；
- managed launcher 与四层 live verification。

对已安装 runtime 的定向回归可运行：

```bash
python3 scripts/verify_official_blender_mcp_runtime.py
```

该脚本读取当前用户安装目录，仅适用于已经安装且路径符合当前分发约定的环境。

## 结论边界

- 自动化测试通过证明当前提交满足仓库合同，不等于任意 Blender 文件或任意 Python payload 都安全。
- 官方工具数量、版本和哈希以当前 manifest 为准，不在文档中维护第二份目录。
- 平台支持只覆盖 manifest 声明的 macOS Apple Silicon 与 Blender 版本范围。
- 历史验收结果可从 Git 历史追溯，但不作为当前工作树的运行时依赖。
