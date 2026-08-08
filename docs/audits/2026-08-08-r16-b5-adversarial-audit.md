# r16/B-5 proposed Plan · 全量对抗审计

> **固定时点快照（2026-08-08，r16 pre-approval）**：正文保留当时“待批准”时态；该 tuple 后来获项目所有者批准，但在形成 source commit/attestation 前被 r17 研究融合取代，不能授权当前执行。live 状态与当前审批入口统一见 [ROADMAP](../ROADMAP.md)。

> 日期：2026-08-08
> 审计对象：Plan r16 proposed、URS/spec v1.15、ROADMAP、r16 Python manifest、A-1/A-3 裁决与官方 Blender MCP 风险边界
> stable Plan SHA-256：`0f7a96464ad408b51c09d0cd297d021dda111162965b40b3109987d32e4ad8a2`
> 边界：本轮只修改/物化/审计 Plan-as-code 与文档；**未执行 Phase 0 Plan，未运行 Blender background/GUI/render、正式 NFR-P1 或 recovery，未 stage/commit/push**

## 1. 裁决

**r16 proposed 已达到“可提交审批”的文档与隔离门禁状态，但 B-5 尚未关闭。**

- A-1：项目所有者已接受三项平台候选；不再保留代码回退动作。
- A-3：项目所有者选择“当前用户接受风险”；G5 以风险接受关闭。该裁决不表示官方 screenshot 顺序敏感性或 deferred render `SIGABRT` 已修复。
- B-5：仍等待项目所有者批准 §7 的完整 proposed tuple。A-1/A-3 的批准**不等于** proposed tuple 批准。
- 获批后才可形成仓库内 `source_commit → attestation commit` 两提交链；当前没有生成仓库内 post-freeze attestation，也没有开始 Task 0。

在最终候选上，已知 P0/P1 均已关闭；保留的外部官方 MCP 风险是用户明确接受的部署边界，不是自研 Plan 的“已修复”结论。

## 2. 审计方法

| 类别 | 方法 |
|---|---|
| Plan parity | 从 49 个 path-bound Python fence 逐块物化，保留首行 `# <path>.py`，与 manifest 逐行复算 |
| 结构 | 行首锚定统计 Task、open/checked checkbox、Python fence、path-bound/unique path |
| 机械门禁 | fresh 临时 Git 树；标准 unit 明确不设置 `PYTHONDONTWRITEBYTECODE`；再跑 `scripts/checks.sh`、contract、adapter、helper、ruff、mypy、compileall、lock、vendor、nested import |
| provenance | 在临时树真实构造 source commit 与后续 attestation commit，复核四文档 live/approved/source-blob SHA、祖先关系、tracked source 与 Git clean |
| 对抗输入 | bytecode 污染、真实 9-entry overflow、unknown-before-valid、pre-spawn/SDK-enter/`Popen` failure、pending/partial/cache/PID reuse/leader-exit 等直接反例 |
| 文档审计 | 交叉核对 A-1/A-3/G5、20 个稳定验收 ID、三工具 NFR-P1、未执行边界与历史 v8 capture |

本方 fresh 验证树：`/private/tmp/r16-v15-final-verify.R9Kmip`。独立机械复核另从零物化 `/private/tmp/blenderdesign-r16-final-check.vHRofj`，得到相同 tuple、manifest 与门禁数字；其临时 source/attestation commit 为 `7dd38a3… → 462daf6…`，最终 Git clean。独立 registry 红队树 `/private/tmp/r16-redteam2-final.S2vejf` 再次复现 9-entry 输入为 100–107 入 cache、108 identity-rechecked KILL、`missed=[]`，并确认 unknown-before-valid 与两类 reservation failure 直接反例全绿。三棵树都不属于仓库，不构成正式 Phase 0 artifact。

## 3. 本轮新增发现与修复

| ID | 严重度 | 修复前复现 | 根因 | 修复与反例 |
|---|---|---|---|---|
| R16-F01 | P1 | 标准 unit：`334 passed, 2 failed`；失败为 `test_provenance_ignores_ignored_untracked_python`、`test_provenance_rejects_vendor_extra_or_content_drift` | 测试 imports 在 `bridge/_vendor/**/__pycache__` 生成 pyc；provenance exact-set 正确拒绝额外项，旧成功依赖隐藏环境变量 | 不放宽 vendor 白名单；`scripts/checks.sh` 显式禁写并预清 bytecode，provenance 夹具只清理测试 import 生成的 vendor bytecode。无隐藏环境标准 unit 为 336 passed |
| R16-F02 | P1 | 8 个 live record + 第 9 个有效 record 时，第 9 项在 `read_record`/identity 复核前因 `seen > MAX_RECORDS` 直接失败；PGID 108 未收到 signal | 同一常量同时充当可信 cache 上限和目录枚举上限 | 删除 entry-count 截断；8 只限制 cache，formal scan 由 shared deadline 限界。真实 9-entry 顺序反例断言 100–107 留在 cache、108 identity-rechecked `SIGKILL` |
| R16-F03 | P1 | `unknown.txt` 排在有效 record 前时立即抛错，后续可信 group 未被读取/清理 | unknown 分支未遵守“逐 entry 错误聚合”合同 | unknown 记为 `first_error` 后继续；同一反例同时放入坏 marker、unknown、valid，旧实现会在 valid 前失败，新实现保留 valid 后统一报告首错 |
| R16-F04 | P2 | 参数构造、SDK client enter 或 `Popen` 在 child 发布 record 前失败时，空 reservation 留在 registry；后续 cleanup 永久 pending 到 deadline | parent 创建 reservation 后没有持有完整失败清理责任 | `_server_params`/`_start_blender` 返回或持有 publication identity；构造/`Popen` 异常立即按 dev/inode finish，caller finally 在 record 不存在时清 reservation。现有 reservation 测试加入两类 pre-spawn failure |

这些修复保持最小范围：没有新增依赖，没有放宽 provenance，没有把 8-record cache 改成无界，也没有把 deadline 表述成不可实现的内核 I/O 绝对墙钟保证。

## 4. 最终机械结果

| 门禁 | 实测结果 |
|---|---|
| 标准 unit（无隐藏环境） | **336 passed** |
| contract | **32 passed** |
| full / `scripts/checks.sh` | **368 passed**；`ALL CHECKS PASSED` |
| adapter 专项 | **35 passed**；373 实质代码行（≤375） |
| Task 18 helper | **53 passed** |
| ruff | `All checks passed!` |
| mypy strict | 22 source files，0 issues |
| compileall | exit 0 |
| `uv lock --check` | 44 packages resolved，exit 0 |
| vendor | generate + `vendor ok` |
| nested import | `nested import ok` |
| 临时两提交 provenance | source/attestation 分离；helper 53 passed；Git clean |

结构复算：

| 项 | 结果 |
|---|---:|
| Tasks | 20 |
| open / checked checkbox | 93 / 0 |
| Python fences | 50 |
| path-bound / unique | 49 / 49 |

## 5. Manifest 可重建性

算法：对每个带 path Python fence，把 fence body（含首行 `# <path>.py` 与末尾 LF）作为物化文件字节取 SHA-256；按 path 排序输出 `path<TAB>sha256<LF>`，再对 TSV 全字节取 SHA-256。

结果：49/49 路径与 hash 一致，无 missing/extra；manifest SHA-256 为：

`ed50f6f1dda32b2723d27f9d0f0d5a86eb27d8711690b3ec7d2f3a5a7f1d0f12`

证据：[2026-08-08-r16-proposed-plan-python-manifest.tsv](evidence/2026-08-08-r16-proposed-plan-python-manifest.tsv)。

## 6. 官方 MCP 与风险边界

| 层 | 当前结论 |
|---|---|
| 当前模型工具面 / host catalog | 26/26 |
| A-4 有界摘要 | 24 个非-render 调用 `ok`，2 个 render `not_called`，approval event 0；无 raw payload、不可重放 |
| screenshot | 严格中段序列仍出现截断 JSON；置后摘要成功不等于修复 |
| deferred render | 本轮未重跑；既有 Blender 5.2 `SIGABRT` 证据继续成立 |
| A-3 | 当前用户知情接受上述风险，保留完整 26 工具与无逐工具审批 |

因此可以关闭部署决策门，但不能写成“官方 26 工具已稳定”“screenshot 顺序问题已修复”或“render 崩溃已修复”。

## 7. Proposed tuple（待项目所有者批准）

| 字段 | 值 |
|---|---|
| `plan_sha256` | `0f7a96464ad408b51c09d0cd297d021dda111162965b40b3109987d32e4ad8a2` |
| `urs_sha256` | `08f202f4ea955766e16fc1899e748e1bc2499a26fdc21df480ed116eee2a3a75` |
| `spec_sha256` | `abe0f2aac3b0656d3db6138e66c3db5652ceeec8d4cd10970446e2a63a651c5d` |
| `roadmap_sha256` | `de8083bf0a75570f95e3c162363a65895cf76d4ba2ce5c7e2b149acfaa6c6f27` |
| `tasks` | 20 |
| `open_checkboxes` / `checked_checkboxes` | 93 / 0 |
| `python_fences` | 50 |
| `path_bound_python` / `unique_path_bound_python` | 49 / 49 |
| `unit_tests` / `contract_tests` / `full_tests` | 336 / 32 / 368 |
| `adapter_tests` / `adapter_substantive_lines` | 35 / 373 |

辅助但不进入 approved tuple 的 manifest SHA：`ed50f6f1dda32b2723d27f9d0f0d5a86eb27d8711690b3ec7d2f3a5a7f1d0f12`。

## 8. 停点与下一步

当前必须停止，不执行 C 组或任一 Plan Task。

项目所有者若批准 §7 的**完整 tuple**，下一轮才执行：

1. 只提交获批精确范围，形成 `source_commit`；
2. 从该 commit blobs 生成 post-freeze attestation；
3. 以第二个提交纳入 attestation；
4. 机械复核 source/blob/live tuple 与祖先关系、Git clean；
5. 再决定是否启动 Task 0。

v8 provenance SHA `90432ae43b705b8b366e0dfe237e387ab8e8ba8a03d523d6ade2b61bf1a1fe54` 保持不可变 capture。
