# r18 Task 3 拓扑测试/来源基线审计

> 日期：2026-08-08
> 对象：[Phase 0 Plan r18 proposed](../superpowers/plans/2026-07-23-phase0-readonly-channel.md)、[URS v1.17](../../Blender-Codex-需求规格说明书-v1.md)、[design spec v1.17](../superpowers/specs/2026-07-23-phase0-readonly-channel-design.md)、[ROADMAP B-7](../ROADMAP.md)
> 边界：本轮只准备 pre-approval baseline；**未执行 Phase 0、未运行 Blender background/GUI/render、正式 NFR/recovery，未 commit，也未生成仓库内 r18 attestation**

## 1. 评审发现与所有者裁决

r17 Plan 的 `test_same_counts_different_topology_collide_by_design` 用完全相同的 `object_line` 输入生成 `before` 与 `after`，再断言摘要相等。该断言只证明确定性，不能证明 topology 被输入合同排除，因此是空洞的 topology-collision 测试。

项目所有者选择选项 1：一对一替换该测试，保持总测试数不变。修正精确为：

- 在既有 `from bridge.core import scene_hash` 前加入 `from inspect import signature`；
- 新测试名为 `test_object_line_input_contract_excludes_topology`；
- 精确断言 `tuple(signature(scene_hash.object_line).parameters) == ("name", "obj_type", "matrix16", "data_kind", "data_counts")`；
- 保留 `test_structure_hash_v1_covers_only_declared_fields`；真实 topology-only Blender 语义仍由 Task 18 L3 `hash_scope` 覆盖。

`bridge/core/scene_hash.py`、产品合同、公开工具面与运行行为均未修改；这是测试与 provenance 修正，不是 Phase 0 产品任务。

## 2. r17 evidence 保留

r17 的 [manifest](evidence/2026-08-08-r17-proposed-plan-python-manifest.tsv)、[post-freeze attestation](evidence/2026-08-08-r17-post-freeze-attestation.json) 与 [融合审计](2026-08-08-deep-research-report-3-integration-audit.md) 原字节保持不变。r17 attestation 仍如实固定 `source_commit 4a7083db949f9a53ba7afdb18f8b4cf622b52d52 → attestation commit 4f13451…` 的历史 approved tuple；它因本次评审发现被 supersede，不授权当前执行。

r18 使用新 [49 行 manifest](evidence/2026-08-08-r18-proposed-plan-python-manifest.tsv)，未来正式 attestation 身份固定为 `evidence/2026-08-08-r18-post-freeze-attestation.json`。该文件只有在本审计 §6 的 exact tuple 获批并形成新的 source commit 后才能生成。

## 3. Manifest 与结构复算

从最终 Plan 逐 fence 解析：每个 path-bound Python fence 的 hash 输入是完整 payload，包含首行 `# path.py` 与结尾 LF；按 path 排序后输出 `path<TAB>sha256<LF>`。结果为 49 行、49 个唯一 path，manifest SHA-256：

`14cc45aab2809c8bbd9c425a7d402b272b41e295d0d7f7833f3d26a7a493d67b`

与 r17 manifest 比较恰有两项变化：

| path | r17 SHA-256 | r18 SHA-256 | 原因 |
|---|---|---|---|
| `smoke/e2e.py` | `cc3e168e2af5c56fd18e46ffedfa573e9d64f07c2442f71b720561c8164888ba` | `da82d1a9869ee3d6a44ef40a996d9164f302234a33b33601ef7e878390bbeafd` | active attestation path 改为 r18 |
| `tests/unit/test_scene_hash.py` | `2fa228c076dd0ea7e984de701422bd34e992ef54f2c4d752a0fc81cb0a02cef0` | `7d2745f5f7156359e558a81a371bb90c812fac46c0a377099d901eff202d22a6` | 一对一修正空洞测试 |

结构机械复算仍为：20 Tasks、93 open / 0 checked checkbox、50 Python fences、49 path-bound / 49 unique。

## 4. fresh-tree 方法

从最终 Plan 与修正后的四文档独立物化到 `/private/tmp/blenderdesign-r18-reviewfix.R3mPeJ`：写入 49 个 path-bound Python fence 的完整 payload、8 个显式空 package marker、`pyproject.toml`、`.gitignore`、`bridge/blender_manifest.toml`、`scripts/checks.sh` 与四份 proposed 文档；用 `/Users/yeminjie/.local/bin/uv lock --python 3.13` 生成 lock（44 packages）。

临时 Git fixture 先提交源码与修正后的四文档为 `source c783c02189e1e60dc09adc915d3b64d48bc26901`，再从该 commit 的四份 blobs 和本审计门禁计数生成临时 `2026-08-08-r18-post-freeze-attestation.json`，以第二个提交形成 `attestation efde5148739625d7a65c1356a689d766bdb1e8f2`。该 attestation 精确绑定 `roadmap_sha256=a23291a53099213e387c4bf63068ea8e0e6c4ac2e71ab25afdb630cf9ec51309`；临时文件未复制进仓库。修正后的 fixture 中 Task 18 helper **54 passed**，四文档 live/approved/source-blob 三方全等、`source → attestation → HEAD` 祖先链成立，最终 Git clean。

## 5. fresh frozen 结果

Plan、URS、spec、49 个 Python payload 与产品源码均未因 ROADMAP/README 时态修正而改变，故完整 product/Plan frozen 门禁沿用同一字节的既有结果；provenance 覆盖则在 §4 的修正 fixture 上重新运行并通过。

| 门禁 | 命令/结果 |
|---|---|
| unit | `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/ -q` → **337 passed** |
| contract | `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/contract/ -q` → **32 passed** |
| full | `/Users/yeminjie/.local/bin/uv run --frozen pytest -q` → **369 passed** |
| adapter | `pytest tests/unit/test_adapter.py -q` → **35 passed**；实质代码 **373** 行 |
| Task 18 helper | 修正 fixture：`pytest tests/unit/test_e2e.py -q` → **54 passed** |
| checks | `bash scripts/checks.sh` → **369 passed** 且 `ALL CHECKS PASSED` |
| lint/type | ruff clean；mypy strict **22 source files / 0 issues** |
| build inputs | compileall exit 0；`uv lock --check` → **44 packages** |
| vendor/import | `vendor ok`；`nested import ok` |
| provenance fixture | 修正后的 `c783c021… → efde5148…`：live/approved/source-blob 全等、祖先链通过，最终 Git clean |

本轮刻意未运行 Blender background、GUI、render、正式 NFR-P1、真 SIGKILL/recovery 或任何 Plan Task；这些仍是获批并 attested 后的 Task 13/18/19 工作。

## 6. r18 proposed exact tuple

| 字段 | 值 |
|---|---|
| `plan_sha256` | `56bfc2db42b51b7b4b679b07cb04109074076248d7990175a84a3253d4fe396a` |
| `urs_sha256` | `edd66512da0d5493d530c24c3df1785eab6dec8e1e35b736a2a48d96615fbf38` |
| `spec_sha256` | `62829d086a71742be9781a1ead5283b4e04c208ecb2282934abeb62073781fd9` |
| `roadmap_sha256` | `a23291a53099213e387c4bf63068ea8e0e6c4ac2e71ab25afdb630cf9ec51309` |
| `tasks` | 20 |
| `open_checkboxes` / `checked_checkboxes` | 93 / 0 |
| `python_fences` | 50 |
| `path_bound_python` / `unique_path_bound_python` | 49 / 49 |
| `unit_tests` / `contract_tests` / `full_tests` | 337 / 32 / 369 |
| `adapter_tests` / `adapter_substantive_lines` | 35 / 373 |

辅助但不进入 approved tuple 的 manifest SHA 为 `14cc45aab2809c8bbd9c425a7d402b272b41e295d0d7f7833f3d26a7a493d67b`。

## 7. 停点

候选停止在 ROADMAP B-7 exact-tuple approval gate。项目所有者逐值批准 §6 前：不 stage/commit、不生成正式 r18 attestation、不进入 C 组或执行 Task 0。获批后只允许新的两提交路径：提交获批精确范围形成 r18 source commit，再从该 commit blobs 生成并以第二个提交纳入 r18 attestation；随后机械验证 live/approved/source blob 三方全等、祖先链、manifest 与 Git clean。
