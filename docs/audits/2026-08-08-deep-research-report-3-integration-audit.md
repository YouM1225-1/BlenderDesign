# 研究报告三融合与 r17 开工基线·全量对抗审计

> 日期：2026-08-08
> 审计对象：[研究报告三归档](../research/deep-research-report-3.md)、Plan r17 proposed、URS/spec v1.16、[ROADMAP](../ROADMAP.md)、文档/机器证据索引及当前未提交工作树
> 边界：本轮只做研究核验、文档融合、Plan-as-code 物化、隔离门禁与仓库整理；**未执行 Phase 0 Plan，未运行 Blender background/GUI/render、正式 NFR-P1 或 recovery，未 stage/commit/push，也未生成仓库内 r17 post-freeze attestation**

## 1. 裁决

**r17 proposed 已达到“可提交项目所有者审批”的文档与隔离门禁状态；B-6 仍由新 tuple 审批阻断。**

- r16 tuple 的批准发生在 source commit/attestation 前；研究融合随后改变 Plan、URS、spec 与 ROADMAP 字节，因此该批准已 supersede，不能跨未知哈希继承。
- 项目所有者随后明确批准了本报告上一版 §9 的 r17 tuple；绑定时却发现 live Plan/URS/spec/ROADMAP 已被后续对抗加固改写，四项 SHA 全部不等。该批准没有形成 source commit 或 attestation，不能静默套用到本版 §9 的新哈希。
- 当前已知的 r17 文档/隔离预检 P0/P1 均已关闭；这不是 Phase 0 实施验收，也不改变官方 Blender MCP 的 screenshot 顺序敏感性和 deferred render `SIGABRT` 事实。
- 下一动作只能是项目所有者逐值批准 §9。获批后才允许形成 `source_commit → attestation commit` 两提交链；Task 0 仍在其后。

## 2. 研究输入完整性与证据质量

原始文件 `/Users/yeminjie/Desktop/deep-research-report-3.md` 共 2473 行，SHA-256：

`91c64abacb3f8a636c2037c6717e4ca90717c7921754e9a98beefbac07c8f554`

归档只在正文前增加 non-normative 说明，原始正文保持不变。证据质量限制如下：

| 发现 | 结论 |
|---|---|
| 原文含 41 个 `turn…/filecite…` 标记 | 这些是会话内部引用，不可移植、不可点击，不进入正式证据链 |
| 原文第 60～68 行声明未收到本仓库源码 | 报告不能被解释为当前仓库审计；本轮必须重新检视实际 Plan/URS/spec |
| 8～15 public tools、5～30 batch operations 等数字 | 报告自己也将其称为工程起点；没有官方门槛，不进入规范 |
| Batch schema 示例缺 `required` 与 `additionalProperties:false` | 与 URS FR-05 的封闭 schema 合同冲突，禁止复制 |
| 原 `ahujasid/blender-mcp` [issue #202](https://github.com/MCPBlender/blender-mcp/issues/202) | 仓库已迁移为 `MCPBlender/blender-mcp`；API 复核为 `closed/completed`（2026-04-19）。历史攻击类别成立，但不能写成当前未修漏洞 |

因此研究原文是正式归档的**外部输入**，不是规范；实际采纳/拒绝只以本报告、URS/spec/Plan 的明确落点为准。

## 3. 官方资料复核

| 主张 | 官方依据 | 裁决 |
|---|---|---|
| 工具集合不变时应保持确定顺序 | [MCP 2026-07-28 Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) 明确说明确定顺序有利于 tool-list cache 与 LLM prompt cache | 采纳为 P0-D7 / NFR-P5 / Task 17 直接合同 |
| 稳定工具定义前缀改善缓存 | [OpenAI Prompt Caching 201 §4.2](https://developers.openai.com/cookbook/examples/prompt_caching_201#42-stabilize-the-prefix) | 采纳“顺序与定义稳定”，不虚构 Token 节省比例 |
| structured result 可同时带兼容 TextContent | MCP Tools 的 Structured Content 条款建议为旧客户端同时返回序列化 JSON 文本 | 采纳为可复算双内容 byte/等价性基线，不假定 Host 一定把两份都计入模型 token |
| Resources 可按需承载详情 | [MCP Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) 把资源定义为 application-driven；Host 决定如何纳入上下文 | 协议方向成立，但“必然 lazy、必然节省 token”不成立；延后真实 Host eval |
| Codex 支持 MCP instructions / Skills / AGENTS 分层 | [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp#supported-mcp-features)、[Build skills](https://learn.chatgpt.com/docs/build-skills)、[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | 采纳跨层单一职责，不新增重复文案或插件前置 |
| Blender 工作必须回到主线程，depsgraph update 可表达变化 | [Python Threads Are Not Supported](https://docs.blender.org/api/current/info_gotchas_threading.html)、[DepsgraphUpdate](https://docs.blender.org/api/current/bpy.types.DepsgraphUpdate.html) | 与既有 queue/timer/revision 路线一致，不重写架构 |

## 4. GitHub 实现抽样

| 项目 | 可借鉴点 | 明确不借鉴 |
|---|---|---|
| [PatrykIti/blender-ai-mcp](https://github.com/PatrykIti/blender-ai-mcp) | curated public surface、hidden atomic、确定性 measurement/assertion truth layer | 不复制实现；只采纳与本仓库合同同向的公开行为 |
| [djeada/blender-mcp-server](https://github.com/djeada/blender-mcp-server) | job status/cancel/list 与同步/异步任务分层可作后续对照 | 当前 Phase 0 不扩张工具面或引入 job 产品代码 |
| [MCPBlender/blender-mcp](https://github.com/MCPBlender/blender-mcp)（原 `ahujasid`） | scene inspection 覆盖面与历史攻击类别 | arbitrary Python、开放文件/代码面不进入自研 G1～G3 系统 |
| [AuraFriday/mcp_link_blender](https://github.com/AuraFriday/mcp_link_blender) | `bpy.app.timers` 主线程 dispatcher 行为 | arbitrary Python 面 |
| [mackson/blender-mcp](https://github.com/mackson/blender-mcp) | compact JSON 只能作为测量线索 | 未发现可依赖的许可证信息，不复制代码；“compact”不替代项目实测 |

## 5. 融合结果

### 已纳入 r17

1. URS v1.16 新增 NFR-P5：三工具 catalog 名称、完整定义与顺序确定；保存 catalog/instructions、structured/TextContent 的 bytes/SHA/等价性基线。
2. spec v1.16 新增 P0-D7 与 §6.5：固定公开顺序 `get_blender_status → get_scene_summary → describe_capabilities`，明确 byte 不等于 token。
3. Plan Task 17 冻结 wire Server identity/version、完整 ordered catalog：6389 canonical bytes，SHA-256 `b2a833a9415363be1db0c9092f46505cb7125f978801ab57fc486448b6c842d8`；三工具 schema 合计 5829 canonical bytes，SHA-256 `52e4b386e581976644ac4f8ef760bae334e11fcc78790ad1adc7ebf3540b3f5c`；instructions 为 322 UTF-8 bytes，SHA-256 `3810714ab9be87e9203432e446fc7ba261737153f4c85f2103a7ec983239cedb`。
4. Plan Task 18 为 60 次正式调用保存 validated structured preimage 与兼容 TextContent 原文，外部复算 JSON 等价、各自 bytes/SHA、duplication ratio 与双内容合计字节。
5. URS 新增 NFR-C6；AGENTS/Skill/MCP instructions/schema/addon 各自只承担其能执行或选择的规则，避免复制同一提醒。
6. URS V-05 与 ROADMAP D-g 明示测量盲点：产品默认 include flags 为 true，而现有 100k NFR 样本固定为 false。默认 observation contract 必须在 Phase 1 前单独裁决，不能静默改默认值。

### 拒绝或延期

| 提议 | 裁决 | 原因 |
|---|---|---|
| 客户端 `idempotency_key` | 拒绝 | 与 FR-12 的服务端派生 `plan_scope_hash` 冲突 |
| duplicate 后自动 mint stable ID | 拒绝 | 与 FR-10 的碰撞人工消歧冲突 |
| 任意 Python escape hatch | 拒绝 | 直接违反 G3/FR-04；官方兼容通道仍是边界外风险接受 |
| 巨型 catch-all batch schema | 拒绝 | 示例 schema 不封闭，也会削弱审批/审计语义 |
| SQLite、Recipe Engine、scene cache 立即进入 Phase 0 | 延期 | 没有本项目 profiling/eval 证明复杂度收益 |
| Resources/Tasks、projection/diff、progressive error | 延期 | 需要目标 Codex Host 的真实 list/read/context 行为与 fallback 证明 |
| 固定工具数、操作数或 Token 降幅 | 拒绝为合同 | 不是官方阈值；后续只能同模型/同推理配置/同 fixture A/B |

## 6. 仓库整理与保留边界

- 可恢复地清理约 14 MiB `.DS_Store`、pytest/mypy/ruff cache 与 bytecode；根 `.gitignore` 补齐对应目录和 `bridge/_vendor/`。
- 新增 [文档导航](../README.md) 与 [机器证据索引](evidence/README.md)，把 live ROADMAP、规范、proposed Plan、历史 capture、研究输入、测量和证据的权威层级分开。
- 统一历史报告顶部为“固定时点快照；当前状态见 ROADMAP”，不再在每份历史文件复制 r16/r17 live 状态。
- 审计时 HEAD `e5ac559` 含 50 个 tracked 文件、约 1.12 MiB；本轮新增正式文档/证据仍保持未暂存。未发现可安全删除的既有 tracked 孤儿；历史审计、兼容 alias 和 byte-identical GUI/vendor/artifact snapshot 都承担 provenance 或 revision/run 身份，全部保留。
- v8 provenance 字节保持不变，SHA-256 仍为 `90432ae43b705b8b366e0dfe237e387ab8e8ba8a03d523d6ade2b61bf1a1fe54`。

## 7. 对抗发现与修复

| ID | 严重度 | 修复前反例 | 修复 |
|---|---|---|---|
| R17-F01 | P1 | Task 18 外部 catalog 校验使用“只过滤 dict 后比较名称”；恶意 catalog 混入非对象时可能让名称检查失真，随后以 `TypeError`/`KeyError` 退出，而不是合同要求的结构断言 | 要求 catalog 为精确长度 list、每项 exact dict 且具备 input/output schema；新增非对象直接反例，稳定抛 `AssertionError` |
| R17-F02 | P2 | 研究原文的 batch schema 缺 `required`/`additionalProperties:false`，若直接复制会回退已关闭的 F-03 | 明确拒绝该 schema；现有三工具封闭 schema 与未知参数 `-32602` 合同不变 |
| R17-F03 | P2 | 历史报告顶部多份重复“current/superseded”块会随每轮变化继续陈旧 | 统一为固定时点 banner；live 状态只保留 ROADMAP 一个入口 |
| R17-F04 | P1 | spec §7.2 声称 raw 2025 两条 wire path 与 SDK 2026 均直接验证双内容 JSON 等价；原 Task 17 只在不同测试里分别观察 TextContent 或 structuredContent，没有同次调用比较 | raw `2025-06-18`、raw `2025-11-25`、SDK `2026-07-28` 三条独立路径均在同次调用中要求唯一 TextContent，并用 strict JSON/canonical 比较验证其与 `structuredContent` 等价；计数不变 |
| R17-F05 | P1 | 重复 list 只比名称；`nextCursor`、`resultType=partial`、完整定义漂移及 fresh stdio catalog 漂移仍可能假通过 | 两次 in-process 与 fresh stdio 都验证 complete 单页、完整 catalog/schema/instructions bytes+SHA，并与固定 6389/5829/322-byte freeze 全等 |
| R17-F06 | P1 | Python `==` 会把 `true` 与 `1` 视为相等；标准 `json.loads` 还接受 `Infinity`、指数溢出与重复键，Pydantic 可把伪造 preimage 归一化后再通过 | 外部验证器改为 strict JSON、递归 exact-type equality；arguments、validated preimage、provenance、identity、P95/max 均拒绝 bool/int/float 混淆及非有限值 |
| R17-F07 | P1 | 单工具 result 可夹带额外 image/resource block，NFR `results` 也可追加第四工具；顶层 artifact 若缺/多字段仍可能被 `.get()` 吞掉 | 每次调用只允许唯一 TextContent；`results` 精确等于三工具集合；NFR 顶层固定 18 个 exact keys，schema/mode/time/environment 均直接验证 |
| R17-F08 | P1 | Task 18 原先只证明 artifact catalog 自洽，攻击者可同时篡改 preimage、bytes 与 digest | `_verify_catalog_baseline` 除自洽复算外必须与 Task 17 的 catalog/schema/instructions 冻结常量全等，并加入“自洽但漂移”反例 |
| R17-F09 | P1 | `MCPServer` 未传 `version`，raw `serverInfo.version` 为空；协议/SDK 测试也未固定 wire identity | adapter 显式传 `SERVER_VERSION=0.1.0`；raw 两版本检查 `serverInfo.version`，2026 SDK 路径通过 `Client.server_info` 检查 name/version |
| R17-F10 | P2 | 文档把 structured+TextContent 合计称为“模型可见 payload”，但 MCP 不规定 Codex Host 如何注入两字段 | 统一降级为“双内容 SDK/transport result payload”；真实 model-visible/token 成本只由目标 Codex Host A/B 关闭 |
| R17-F11 | P1 | 首次修复误从 `DiscoverResult.meta["serverInfo"]` 取值；SDK v2 实际保留键为 `io.modelcontextprotocol/serverInfo`，定向 stdio 测试直接失败 | 使用 SDK v2 公共 `Client.server_info` 属性；同一失败测试转绿，避免依赖私有/命名空间 metadata 布局 |
| R17-F12 | P1 | 取得 `Client.server_info` 对象后，Task 18 `_catalog_baseline` 返回 artifact 时仍残留旧字典写法 `server_info["version"]`；独立 fresh stdio 直接复现 `Implementation object is not subscriptable`，而原 54 条 helper 全绿 | 改用 `.name/.version` 并把两字段都写入/验证 catalog artifact；将既有 catalog 反例测试改为真实 async `Client(server_app)` 成功路径，测试总数不变但覆盖正式入口 |

R17-F01 已先红后绿；它使 unit/full/Task 18 helper 分别比 r16 增加 1 个测试，故不能沿用 r16 的 336/368/53 计数。R17-F05～F12 均由独立红队或实际 SDK 成功路径先复现旧校验缺口，再收紧现有测试/验证器；未扩张 Phase 0 产品工具面。

## 8. 隔离门禁与完整性复核

最终验证树：`/private/tmp/blenderdesign-r17-final5.r3J6LH`。49 个 path-bound Python fence 逐字节物化，另保留 8 个显式空 `__init__.py` 和 Plan 的非 Python 构建输入；只在临时 Git 仓库构造 `source d39980e… → attestation 7eb02ab…` 两提交 fixture，以覆盖 provenance 单测。该 fixture 不属于本仓库，也不是正式 attestation；整链结束后临时树 Git clean。另以真实 SDK `Client(server_app)` 直接调用 `_catalog_baseline`，得到 `server_name=blender-codex`、`server_version=0.1.0` 与 6389/5829/322 三项冻结值，关闭 R17-F12。

独立复核从同一静止字节另建 `/private/tmp/blenderdesign-r17-independent.VUkKNO`，临时 `source 5b1f2cb… → attestation 03eff34…` 后 Git clean；49/49 manifest、结构、unit 337、contract 32、full 369、adapter 35/373、helper 54、checks/ruff/mypy/compileall/lock/vendor/nested 全部与主复核一致。定向三协议 3 tests 与真实 SDK `_catalog_baseline` 均通过；未发现新增 P0/P1 或文档漂移 blocker。此前 final/final2/final4 临时树均被 R17-F05～F12 及 SDK identity 成功路径修复 supersede，不再作为本版 tuple 的证据。

| 门禁 | 实测结果 |
|---|---|
| unit | **337 passed** |
| contract | **32 passed** |
| full | **369 passed** |
| `scripts/checks.sh` | **369 passed**，明确输出 `ALL CHECKS PASSED` |
| adapter | **35 passed**；373 实质代码行（≤375） |
| Task 18 helper | **54 passed** |
| ruff / mypy strict | clean；22 source files 0 issues |
| compileall / `uv lock --check` | exit 0；44 packages resolved |
| vendor / nested import | `vendor ok` / `nested import ok` |
| 临时 provenance fixture | source/attestation 两提交分离，门禁计数与四文档 blob 校验通过，最终 Git clean |

结构复算：20 Tasks、93 open/0 checked checkbox、50 Python fences、49 path-bound/49 unique。r17 manifest 共 49 行，SHA-256：

`49867d461307b7273077359062896705019d5c5e2bc2ef258ac386919b46cb80`

证据：[2026-08-08-r17-proposed-plan-python-manifest.tsv](evidence/2026-08-08-r17-proposed-plan-python-manifest.tsv)。

未运行项必须继续写成未运行：Blender background、GUI smoke、100k 正式 MCP NFR-P1、render、真 SIGKILL/recovery 与所有 Phase 0 Task。这些只在获批/attested Plan 的 Task 13/18/19 执行。

## 9. r17 proposed tuple（等待项目所有者逐值批准）

| 字段 | 值 |
|---|---|
| `plan_sha256` | `8c427d9ffa10c555bf44862655f534e5e3c3f777377976277b88905885f7a200` |
| `urs_sha256` | `c31e31bafcd727ea971561ef4a8098f98d8bc1baf7137dea18616ae6dfe3311c` |
| `spec_sha256` | `e6d9215f873c1ad0a263ab3c86e19c7109dcc87dcc7707831f8b61bf93a8d2a7` |
| `roadmap_sha256` | `a8576e22228336341a3f9487f59aac2d451d6337d8c65901e4be14c2ba8379ee` |
| `tasks` | 20 |
| `open_checkboxes` / `checked_checkboxes` | 93 / 0 |
| `python_fences` | 50 |
| `path_bound_python` / `unique_path_bound_python` | 49 / 49 |
| `unit_tests` / `contract_tests` / `full_tests` | 337 / 32 / 369 |
| `adapter_tests` / `adapter_substantive_lines` | 35 / 373 |

辅助但不进入 approved tuple 的 manifest SHA：`49867d461307b7273077359062896705019d5c5e2bc2ef258ac386919b46cb80`。

## 10. 停点

当前必须停止在 B-6 审批门：不执行 C 组，不 stage/commit/push，不生成正式 r17 attestation。项目所有者若批准 §9 的**完整 r17 tuple**，下一轮才按 ROADMAP 执行：

1. 只提交获批精确范围形成 `source_commit`；
2. 从该 commit blobs 生成 r17 post-freeze attestation；
3. 以第二个提交纳入 attestation；
4. 复核 live/approved/source blob 三方全等、祖先链、manifest 与 Git clean；
5. 再决定是否启动 Task 0。
