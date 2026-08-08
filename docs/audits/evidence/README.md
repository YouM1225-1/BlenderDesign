# 机器证据索引与保留规则

> 更新：2026-08-08。本文只解释 `docs/audits/evidence/` 中 artifact 的身份与适用范围；live Gate 只看 [ROADMAP](../../ROADMAP.md)。历史 artifact 不因文件名较旧、没有 Markdown 反向链接或字节相同而自动失效，也不能反过来证明当前工作树已经实施 Phase 0。

## 证据类别

| 类别 | 文件 | 身份与可证明范围 | 保留规则 |
|---|---|---|---|
| r15/v8 capture 根 | `2026-08-08-phase0-closeout-v8-provenance.json` | canonical immutable capture；SHA-256 `90432ae43b705b8b366e0dfe237e387ab8e8ba8a03d523d6ade2b61bf1a1fe54`，绑定 `578f49e` 工作区及八份文档、六类 artifact | 永不就地更新；后续 live 文档漂移不回写 |
| 早期 provenance | `2026-08-07-phase0-closeout-v4-provenance.json`、`-v5-...`、`-v7-...` | r11～r14 的固定时点机器记录；v7 文件名兼作已发布的兼容入口 | 保留原路径；不得改名或把 v7 当 live v8 |
| Plan Python manifest | `2026-08-07-phase0-plan-python-manifest-v5.tsv`～`v8.tsv` | 各 revision 的 path-bound Python fence 字节清单 | 保留 revision 身份；不能拿旧 manifest 校验新 Plan |
| proposed manifest | `2026-08-08-r16-proposed-plan-python-manifest.tsv`、`2026-08-08-r17-proposed-plan-python-manifest.tsv`、`2026-08-08-r18-proposed-plan-python-manifest.tsv` | 隔离物化候选，不是实施产物；r18 从最终 Plan 独立生成 49/49 清单，因 Task 3 测试与 Task 18 attestation path 修订而与 r17 不同 | r16/r17 文件保持不可变历史；r18 是当前 B-7 审批辅助证据 |
| post-freeze attestation | `2026-08-08-r17-post-freeze-attestation.json`、`2026-08-08-r18-post-freeze-attestation.json` | r17 文件固定 `source_commit 4a7083d…` 的已批准 tuple，已因后续评审发现 supersede；r18 路径是当前 exact tuple 获批后才能生成的正式身份，候选阶段不得存在 | r17 原字节永不改写；r18 必须从获批 r18 source commit blobs 生成并以第二个提交纳入 |
| 非 Python artifact manifest | `2026-08-07-phase0-artifact-manifest-v5.tsv`～`v8.tsv` | 当轮 Plan 的非 Python/空包等物化输入 | v7/v8 字节相同仍分别保留 revision 身份 |
| vendor manifest | `2026-08-07-phase0-vendor-manifest-v5.tsv`～`v8.tsv` | vendored protocol exact-set/hash 快照 | 四版字节相同；不物理去重，不冒充 live vendor |
| GUI smoke | `2026-08-07-phase0-gui-smoke-closeout-v2.json`～`v8.json` | 真实 Blender GUI 的当轮基础判据；不是 r18 正式 NFR/recovery | v2～v5、v6～v7 各自 byte-identical，文件名仍承载 run/revision |
| 100k measurement | `2026-08-07-phase0-gui-100k-measurement-v6.json`～`v8.json` | 单机 Bridge-RPC/continuation 测量；不覆盖完整 MCP stdio/adapter NFR-P1 | 保留原始值，不外推跨机或改写为 Phase 0 完成 |
| 官方 MCP 历史快照 | `2026-08-07-official-blender-mcp-v1.json`、`2026-08-08-official-blender-mcp-v2.json` | 官方 Server 注册/宿主兼容与已知 screenshot/render 风险；v2 明示当时模型面并非 26/26 | 只按 `captured_at` 和 scope 解读 |
| 官方 MCP A-4 摘要 | `2026-08-08-official-blender-mcp-a4-transcript.ndjson` 及 `.sha256` | 1 run + 26 tool records + 1 summary；24 个非-render `ok`、2 个 render `not_called`、审批事件 0 | 不含 raw 参数/响应、不可重放；不能证明 26 工具稳定或 render 缺陷修复 |

## Canonical、alias 与 byte-identical snapshot

- `2026-08-08-phase0-closeout-v8-provenance.json` 是 r15/v8 capture 的 canonical 根。
- `2026-08-07-phase0-closeout-v7-provenance.json` 是历史兼容入口，不是同一字节的 v8 alias；仓库外消费者可能依赖其路径。
- GUI smoke v2～v5 的 SHA 均为 `6305b173…`；v6～v7 均为 `dda8796d…`。
- artifact manifest v7～v8 均为 `6a1cea7d…`；vendor manifest v5～v8 均为 `fa45e6d…`。
- byte-identical 只表示内容相同，不消除文件名承载的 revision/run 身份。Git 已压缩相同 blob，删除文件几乎没有收益，却会破坏当前 checkout 的自包含复核。

## 使用纪律

1. 先看 artifact 自身的 revision、时间、scope，再看它由哪份审计或 provenance 引用；不能按“日期最新”自动升级权威。
2. `proposed`、`preflight`、`isolated` 只表示候选代码在临时树通过相应门禁；不得写成 Phase 0 已执行。
3. 正式 Phase 0 artifact 只能在获批 r18 exact tuple、新的 `source_commit → r18 attestation commit` 两提交链和执行前机械验证完成后生成；r17 attestation 只作不可变历史，不能授权当前执行。
4. JSON/NDJSON/TSV 必须保持可解析；sidecar 只校验文件完整性，不证明语义正确。
5. 禁止把缓存、bytecode、`.DS_Store` 或临时 `.blend` 放进本目录；这些文件由根 `.gitignore` 排除。
