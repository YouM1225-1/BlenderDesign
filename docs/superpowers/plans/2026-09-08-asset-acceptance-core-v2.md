# Asset Acceptance Core V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 M0/M1：把已核对的 v1 判定核心迁移为严格 v2 合同、冻结输入、真实工具锁、受控作业协议及可复核的无环证据链；生产入口继续对尚未实现的 Blender 检查失败关闭。

**Architecture:** 保留 `acceptance/`、唯一 `decide.py`、37 个检查的身份和失败码家族；新增文件按冻结输入、工具身份、静态计划、JSON 协议、进程控制分别负责一件事。Blender/GLB 通过 JSON 文件与控制器通信；控制器拥有运行事实、文件测量、归约和封装，worker 只能提供 findings 与测量材料。M2/M3 只接入本文定义的接口，不另建协调框架。

**Tech Stack:** 仓库锁定 Python 3.13.13、标准库、现有 pytest、既有 canonical/strict_json 和进程组原语。M1 单元测试不启动 Blender，不引入数据库、队列、jsonschema 或插件发现框架。

## Global Constraints

- 已认可设计：[资产验收整合设计](../specs/2026-09-08-asset-acceptance-integration-design.md)。本文仅 M0/M1；安装清理、M2 与 M3 分别验收。
- 首发支持 `blend_native + static_render + local-trusted`。M1 只完成可信核心；未接线的必需项返回 `NotTested`，不能称真实资产已通过。
- native 保留全部 24 项现有适用检查，interchange 保留全部 34 项，新增业务 gate 不能代替它们。
- v2 明确拒绝 v1。迁移必须重新冻结输入、生成新合同与新 run；不补摘要、工具、阈值或 N/A。
- `summary.success` 包含全部 required checks 与技术 gates；签收与交付状态写上层记录，Q 不改变技术 V。
- `bridge/core` 与 `protocol` 不得导入 `bpy`；本计划不改变 wheel/sdist 打包范围。
- 证据与原型在仓库外；保持用户已有改动。`graft/` 不暂存、不提交。
- 每个实施包提交前运行一次 `bash scripts/checks.sh`，确认 `ALL CHECKS PASSED`；最后一次仓库修改后运行 `graft build .`，交付前 `graft check .` 必须退出 0。
- 下文 pytest 使用 `.venv/bin/python -m pytest`；环境未准备时先运行仓库既有 `bash scripts/checks.sh` 创建锁定环境。不要假设 PATH 中有 `uv`。

---

## 范围、文件与提交边界

此计划中的代码块是目标实现的完整新增文件、完整函数替换块或明确标注的插入块。执行时先读目标文件，保留无关内容；按任务给出的回归验证变更。不把计划代码直接当作当前运行能力。

| 文件 | 责任 |
|---|---|
| `docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md`、`docs/README.md` | 新规范权威、v2 字段/版本/状态与阶段能力 |
| `acceptance/check_registry.py` | 37 个 check 的逐项 impl 和唯一顺序 |
| `acceptance/contract.py` | 封闭加载、深不可变快照、v2 digest |
| `acceptance/input_bundle.py` | 无链接父链、安全有界流式复制、冻结包和文件身份 |
| `acceptance/toolchain.py` | 精确工具版本/字节/脚本身份、显式可信代码闭包 |
| `acceptance/plan.py` | 固定 JobSpec/FileSpec/RunPlan、归属及依赖顺序 |
| `acceptance/worker_protocol.py` | 纯 Python JSON request/result，Blender 端也可导入 |
| `acceptance/controller.py` | 有界作业、输入副本、独立事故、可信 payload 接收 |
| `acceptance/decide.py`、`acceptance/stages.py` | 内部不变量、N/A、R0/R1/R5 与唯一归约 |
| `acceptance/evidence.py`、`scripts/asset_accept.py` | E/V/Q/T、失败摘要与生产 CLI |
| `tests/unit/test_asset_v2_*.py` | 行为回归；模拟 worker 仅在测试注入 |
| 既有 `tests/unit/test_asset_*.py` | 保留或明确迁移旧接口回归，不保留 v1 放行入口 |

## 提供给 M2/M3 的固定接口

`Contract.raw` 为深冻结 Mapping；保留 `digest`、`artifact_kind`、`na_check_ids`、`required_isolation_grade`、`allowlisted(...)`。

```text
# acceptance.input_bundle
BoundFile(id: str, path: Path, bytes: int, sha256: str)

# acceptance.plan
FileSpec(id: str, path: str, writer: str, media_type: str, max_bytes: int)
JobSpec(job_id: str, writer: str, tool_id: str,
        check_ids: tuple[str, ...], input_ids: tuple[str, ...],
        outputs: tuple[FileSpec, ...], parameters: Mapping,
        blocking_check_ids: tuple[str, ...] = ())
RunPlan(jobs: tuple[JobSpec, ...], files: tuple[FileSpec, ...],
        check_ids: tuple[str, ...], na_check_ids: tuple[str, ...],
        required_tools: tuple[str, ...], gate_ids: tuple[str, ...] = ())
assemble_plan(contract: Contract, jobs: tuple[JobSpec, ...], *,
              gate_ids: tuple[str, ...] = ()) -> RunPlan

# acceptance.worker_protocol — 只导入标准库和 acceptance.strict_json
read_request(path: Path) -> dict
write_result(request: dict, checks: list[dict], observations: dict[str, str]) -> Path

# acceptance.controller
run_jobs(contract: Contract, plan: RunPlan, *, run_id: str,
         input_files: Mapping[str, BoundFile], scratch_root: Path,
         evidence_root: Path, commands: Mapping[str, tuple[str, ...]]) -> RunResult
collect_verdict(contract: Contract, plan: RunPlan, run: RunResult, *,
                coordinator_findings: Mapping[str, list[Finding]]) -> Verdict

# acceptance.decide / acceptance.evidence
Gate(complete: bool, findings: tuple[Finding, ...] = ())
finalize_run(contract, plan, run, *, contract_path: Path, source_root: Path,
             evidence_root: Path, delivery: BoundFile | None,
             coordinator_findings: Mapping[str, list[Finding]],
             gates: Mapping[str, Gate], review: dict | None = None) -> dict
finish_review(evidence_root: Path, *, delivery_path: Path, review: dict) -> dict
```

`commands` 按 **writer** 键控，是受信代码构造的完整 argv prefix；Blender prefix 末尾为 `--python <worker.py> --`，Python/Node prefix 为执行文件及脚本。控制器统一追加 `--request <absolute request.json>`。候选、子进程和合同内容不能提供任意可执行 argv。

`RunResult` 暴露 `findings`、`infra_failures`、`files: dict[id, BoundFile]`、`results: dict[job_id, dict]`、`jobs` 与 `measurements`。后续 reducer 只能读取已接收 `files`；`coordinator_findings` 仅能完成 registry writer 为 coordinator 的检查，或向已经由合法 worker 完成的检查追加 controller 测量，不得为空缺的 inspector/render 检查制造 Pass。

每个 job 得到独立 input/output root。`input_ids` 从冻结源或前一阶段 **已验证接收** 的 payload 取；控制器复制并再次测量。S 始终标识原始冻结源，GLB、manifest 等上游输出用各自 inputs 条目绑定。

request 的固定字段：

```json
{
  "schema_version": 2,
  "run_id": "run-001",
  "attempt": 1,
  "nonce": "00000000000000000000000000000000",
  "job_id": "inspect",
  "writer": "inspector",
  "contract_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "source_digest": "0000000000000000000000000000000000000000000000000000000000000000",
  "input_root": "/absolute/job/input",
  "inputs": [],
  "output_root": "/absolute/job/output",
  "outputs": [],
  "parameters": {}
}
```

上述全零值只是形状示例；真实运行必须使用实际 digest 和随机 nonce。inputs 条目为 `{id,path,bytes,sha256}`；outputs 为 `{id,path,media_type,max_bytes}`，path 相对各 job 根。固定协议输出 `result.json` **不在 outputs 内**，避免结果自引用；控制器自动将其作为 `job_id.result` 纳入 E 的叶子。

result 固定字段为 request 的八个身份字段，加：

```json
{
  "checks": [{"id": "r2.inventory.no_nan_inf", "findings": [], "metrics": {}}],
  "artifacts": [],
  "observations": {"blender_version": "5.2.0"}
}
```

finding 严格为 `{code,severity,pointer,detail}`，severity 为 error/warning/info；metrics 是有限 JSON scalar 映射。artifacts 条目为 `{id,path,bytes,sha256}`，只引用业务产物。拒绝 success/raw/effective/disposition/N/A、旧身份、未知 check、越权 writer、缺失和超限输出；控制器重测所有 bytes/hash。

无实际交付物时传 `delivery=None`：summary.D 与 bindings.D 均为 null，记录 evidence_missing，不能生成 SHIP。若已有实际资产失败同时有 NotTested / 未完成 gate，技术码保留 check_failed，上层独立按完整性输出 UNVERIFIED。安全 blocked_by 不伪造基础设施事故，E 列出 controller 已确认未产生的文件；其他文件缺失仍为事故。

M2 在 `acceptance/native_policy.py` 定义 `validate_native_policy(value) -> None` 并启用 `raw['native']` 的完整封闭对象；该接入块须将 ValueError 包装为 contract_invalid，并校验 reference_manifest_id、reference_authority 及 reference_images 全部引用冻结输入 ID。M3 对 `raw['interchange']` 同理。M1 这两字段只允许 null，表示 worker 尚未接线；不得把任意 JSON 当成已受 schema 保护的参数。


### Task 1: 固定 V5/v2 迁移及逐检查 impl

**Files:**
- Create: `docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md`
- Modify: `docs/README.md`
- Modify: `acceptance/check_registry.py`（`CHECKS` 定义之后、`_STAGE_INDEX` 之前）
- Test: `tests/unit/test_asset_v2_registry.py`

**Interfaces:**
- Consumes: `CheckSpec`、`CHECKS`、`checks_for_kind()` 和 `sort_key()`。
- Produces: 37 个原有 check ID 的 v2 impl 映射；M0 是目标规范，M1 CLI 切换完成才将运行时入口标为 V5。

- [ ] **Step 1: 写入兼容性回归。**

完整新增 `tests/unit/test_asset_v2_registry.py`：

```python
from acceptance import check_registry as reg

def test_v2_keeps_required_sets_and_versions_changed_semantics():
    assert len(reg.CHECKS) == 37
    assert len(reg.checks_for_kind("blend_native")) == 24
    assert len(reg.checks_for_kind("interchange")) == 34
    impl = {s.id: s.impl for s in reg.CHECKS}
    assert impl["r0.contract.tools_locked"] == 2
    assert impl["r1.input.digest_recorded"] == 2
    assert impl["r2.inventory.coverage_complete"] == 2
    assert impl["r5.evidence.hashes_match"] == 2
    assert impl["r3.validator.report_complete"] == 1
```

- [ ] **Step 2: 验证旧版实现先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_registry.py -q`

Expected: 版本断言失败，原始 required 数量不变。

- [ ] **Step 3: 插入唯一版本表，并据同表生成规范版本清单。**

先将文件顶部 `from dataclasses import dataclass` 改为 `from dataclasses import dataclass, replace`，再在 `CHECKS` 元组后插入：

```python
_V2_IMPL = {
    "r0.contract.schema_closed": 2,
    "r0.contract.tools_locked": 2,
    "r0.contract.na_set_declared": 1,
    "r1.input.digest_recorded": 2,
    "r1.input.no_link_or_device": 2,
    "r1.input.size_within_limit": 2,
    "r2.inventory.coverage_complete": 2,
    "r2.inventory.no_nan_inf": 1,
    "r2.inventory.no_reserved_props": 1,
    "r2.geometry.validate_clean": 2,
    "r2.geometry.manifest_written": 2,
    "r2.material.slots_resolved": 2,
    "r2.dependency.all_present": 2,
    "r2.source.digest_stable": 2,
    "r3.export.file_nonempty": 1,
    "r3.export.source_unchanged": 1,
    "r3.validator.no_error": 1,
    "r3.validator.resources_read": 1,
    "r3.validator.report_complete": 1,
    "r3.extension.none_forbidden": 1,
    "r3.budget.within_limits": 2,
    "r4.reopen.offline_ok": 2,
    "r4.reopen.dependencies_resolved": 2,
    "r4.reopen.manifest_matches_source": 2,
    "r4.import.manifest_written": 2,
    "r4.projection.preserved_fields_match": 2,
    "r4.projection.transformed_within_tolerance": 2,
    "r4.projection.undeclared_loss": 2,
    "r4.projection.ambiguous_object_names": 2,
    "r4.visual.scene_not_empty": 2,
    "r4.visual.all_views_rendered": 2,
    "r4.visual.self_determinism": 2,
    "r4.visual.platform_key_known": 2,
    "r4.visual.source_import_match": 2,
    "r5.evidence.manifest_closed": 2,
    "r5.evidence.hashes_match": 2,
    "r5.contract.digest_stable": 2,
}
if set(_V2_IMPL) != {spec.id for spec in CHECKS}:
    raise RuntimeError("v2 implementation table is not the exact check registry")
CHECKS = tuple(replace(spec, impl=_V2_IMPL[spec.id]) for spec in CHECKS)
```

`impl=1` 项保留旧规范的同一判据；schema、输入包边界、coverage/表面、R4 完整图像以及真实 R5 改义使用 2。N/A/outcome 协议归约由 schema2 统一改变，不发明第 38 个旧 check。新增 scope/reference/cross-process/consumer 作为独立 required gate，并计入 v2 技术判定。

完整创建 V5 文档如下；嵌套合同、文件与 writer 字段表已给出，随后用本步骤脚本追加唯一机器版本表：

```markdown
# BlenderDesign 资产验收规范 V5

状态：M0/M1 目标规范。完成 v2 CLI 和回归切换后才标为当前实现规范。

本规范采用已经认可的资产验收整合设计。官方分发、自研 Phase 0、资产验收分别报告；当前 M1 不代表完整资产通过。V3.8 与外部 V4 是迁移输入，不是 v2 的可兼容合同。

## 合同与版本

v2 只读取 schema_version=2。旧合同作为政策草案，经重新冻结输入与核对工具后生成新 C/S 和新 run；不自动补值。所有嵌套字段封闭，C 为 canonical.digest("contract.v2", document)。运行快照深不可变。原生与 GLB 的 required 集分别保留 24/34 个现有检查；本页版本表与机器注册表成套更新。

## v2 合同字段表

所有对象封闭；列表项也按对应行封闭。SHA-256 为 64 位小写十六进制，数值不接受 bool/NaN/Inf。字段类型与进一步约束由 acceptance.contract.validate_document 唯一实现。

| 对象 | 完整字段与类型 |
|---|---|
| 根 | schema_version:int=2；contract_id:ID；artifact_kind:blend_native/interchange；profile:static_render；required_isolation_grade:local-trusted；input:object；checks:list；na_check_ids:list；warning_allowlist:list；tools:list；limits:object；budget:object；native:null/object；interchange:null/object；review:object；policy_baseline:null/冻结输入 ID |
| input | main:输入 ID；sha256:source.v2 有序清单摘要；files:list |
| input.files[] | id:唯一 ID；path:相对普通路径；bytes:非负整数；sha256:文件摘要 |
| checks[] | id:registry ID；impl:整数；order:整数；列表必须等于 kind 对应唯一有序注册集 |
| warning_allowlist[] | check_id:string；warning_code:string；tool_id:string；tool_version:string；只能引用 registry 声明的 warning，覆盖缺口不允许豁免 |
| tools[] | id:python/acceptance/blender/node；path:绝对路径；version:精确观察版本；sha256:真实可执行或 CLI 摘要；files:list |
| tools[].files[] | path:唯一绝对路径；bytes:非负整数；sha256:文件摘要 |
| limits | timeout_seconds:writer→正数；cpu_seconds、rss_bytes、open_files、log_bytes、file_size_bytes:正整数；RSS 是采样边界，记录峰值及采样数，不声明硬地址空间隔离 |
| budget | max_files、max_file_bytes、max_total_bytes、max_result_bytes:正整数 |
| review | required:bool；reviewer_ids:唯一 ID 列表；required_image_ids:唯一图像 ID 列表；reason:非空字符串 |
| policy_baseline 引用文件 | schema_version:int=2；kind:acceptance_policy_baseline；constraints:精确包含 tools/warning_allowlist/budget/limits/review/native/interchange 并与合同完全相同 |
| native/interchange | M1 只能 null；M2/M3 各自启用完整封闭政策，所有外部参考/配置引用已冻结输入，不接受任意 JSON 或执行命令 |

## 文件、作业与 writer 注册

静态 RunPlan 从 Contract 导出；子进程不能增加文件或 writer。每份业务输出只归一个 JobSpec；安全阻断只使实际未产生项留在 E 的 unproduced/missing 中，相关检查仍 NotTested。

| 注册项 | 固定字段或归属 |
|---|---|
| FileSpec | id、相对 path、writer、media_type、max_bytes |
| JobSpec | job_id、writer、tool_id、check_ids、input_ids、outputs、parameters、blocking_check_ids |
| request.json | controller；schema_version/run_id/attempt/nonce/job_id/writer/contract_digest/source_digest，加 input_root/inputs/output_root/outputs/parameters |
| result.json | 唯一作业 writer；原样八项身份，加 checks/artifacts/observations；不在 request.outputs 内，无自引用 |
| checks[] | id、findings、metrics；findings 项固定 code/severity/pointer/detail，metrics 只含有限 JSON scalar；无最终状态 |
| artifacts[] | id、path、bytes、sha256；controller 复制并独立重测后才接受 |
| job.json、process.log、run.json | controller；真实启动、PID、时间、退出、事故、blocked_by、工具/输入与 RSS 测量 |
| gates.json | controller；expected_gate_ids 与完整 gate 测量，作为 E 的叶子；裁决写 V |
| evidence-manifest.json（E） | controller；C、S、files、missing、unknown、unproduced；不包含自身或 V/Q/T |
| summary.json（V） | 唯一裁决结果；C/S/D/E、checks、gates、failed IDs、infra_failures、success；缺 D 为 null，不能通过 |
| review.json（Q） | controller 封装真实审阅记录；绑定 C/S/D/E/V 和实际所看图像；测试 reviewer 不授权生产签收 |
| completion.json（T） | controller 最后同步写入；绑定 C/S/D/E/V/Q 与最终 state；没有自 hash |
| delivery-receipt.json | controller；复核全部证据与 D 后复制原字节，记录 D/T、目标、长度和交付时间 |

## 执行与归约

controller 编译唯一文件/作业计划，固定 writer、输入/输出及安全阻断前置。子进程不能提供最终状态、N/A 或 warning disposition。每次结果绑定 run/attempt/nonce/job/writer/C/S。若已证实 Fail 同时存在必需 NotTested，技术结果仍为未完成并保留全部失败证据；不能把未完成检查变 N/A。错误几何阻断危险下游，安全质量失败继续可执行的诊断。

## 证据与签收

叶子证据 → E → V → Q → T。E 不引用自己、R5 结论或上层对象；R5 写 V。技术 gate 纳入 schema2 summary.success，并单列 gates/failed_gate_ids。Q 只影响业务接受，不改写 V。缺必需审阅时只有 E/V，返回 NEEDS_REVIEW；最后复测 D，写 Q/T，交付只复制已验 D 并生成 receipt。

## 事实与范围

2026-09-08 实测只覆盖所记 Blender build/platform 和探针。曲线/文字实例去重、合法拆点与未使用数据裁剪、PNG 像素/字节分离是后续实现约束，不代表 M1 worker 已完成。UV 层裁剪、完整 wire/beauty 复现、消费者与隔离按各实施阶段单独验收。
```

在已应用本任务 `_V2_IMPL` 的仓库根执行，追加机器表而不改变 M0 目标状态：

```python
from pathlib import Path
from acceptance import check_registry as reg, failure_codes as fc
path = Path("docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md")
text = path.read_text().split("\n## 当前机器表\n")[0]
text += "\n## 当前机器表\n\n| Check ID | impl | writer |\n|---|---:|---|\n"
text += "".join(f"| `{row.id}` | {row.impl} | `{row.writer}` |\n" for row in reg.CHECKS)
text += "\n| Failure family | priority |\n|---|---:|\n"
text += "".join(f"| `{name}` | {priority} |\n" for priority, name in enumerate(fc.FAILURE_FAMILIES))
path.write_text(text)
```

在 `docs/README.md` “资产验收方案”下添加一条目标规范链接，暂保留 V3.8 当前入口：

```markdown
- [V5/v2 迁移目标](acceptance/blender_mcp_skill_acceptance_optimized_v5.md)：已认可设计的实施规范；v2 CLI 切换完成前，不代表当前运行时已升级。
```

- [ ] **Step 4: 通过版本回归并检查文档链接。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_registry.py -q`

Expected: PASS；任何 required 数量变化均失败。

- [ ] **Step 5: 审阅 M0 差异。**

Run: `git diff --check`

Expected: 退出 0；M0 文档不得宣称 worker 已完成。

### Task 2: 冻结输入与安全文件身份

**Files:**
- Create: `acceptance/input_bundle.py`
- Test: `tests/unit/test_asset_v2_input.py`

**Interfaces:**
- Consumes: 既有 `AcceptanceFailure` 与 `canonical.digest()`。
- Produces: `BoundFile`、`freeze_bundle()`、`verify_bundle()`、`measure_file()`、`read_bounded()`、`safe_open()`；完整签名见下列文件。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_input.py`：

```python
import os
import pytest
from acceptance.input_bundle import freeze_bundle, measure_file, verify_bundle
from acceptance.primitives import AcceptanceFailure


def test_freeze_survives_original_edit_and_rechecks_members(tmp_path):
    original = tmp_path / "source.blend"
    original.write_bytes(b"before")
    root = tmp_path / "frozen"
    rows = freeze_bundle(
        [{"id": "asset", "path": "asset.blend", "source": str(original)}],
        root,
        max_files=1,
        max_file_bytes=32,
        max_total_bytes=32,
    )
    original.write_bytes(b"after")
    assert verify_bundle(root, rows, max_file_bytes=32)["asset"].bytes == 6
    (root / "extra").write_bytes(b"unexpected")
    with pytest.raises(AcceptanceFailure, match="file set"):
        verify_bundle(root, rows, max_file_bytes=32)


@pytest.mark.parametrize("kind", ["symlink", "fifo", "parent_link", "too_large"])
def test_streaming_reader_rejects_unsafe_paths(tmp_path, kind):
    real = tmp_path / "real"
    real.mkdir()
    path = real / "asset"
    path.write_bytes(b"1234")
    limit = 4
    if kind == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif kind == "parent_link":
        link = tmp_path / "folder"
        link.symlink_to(real, target_is_directory=True)
        path = link / "asset"
    else:
        limit = 3
    with pytest.raises((AcceptanceFailure, OSError)):
        measure_file(path, limit, file_id="asset")


def test_mid_read_change_does_not_return_a_digest(tmp_path, monkeypatch):
    path = tmp_path / "asset"
    path.write_bytes(b"old")
    original = os.read
    changed = False

    def race(fd, size):
        nonlocal changed
        data = original(fd, size)
        if data and not changed:
            changed = True
            path.write_bytes(b"new")
        return data

    monkeypatch.setattr(os, "read", race)
    with pytest.raises(AcceptanceFailure, match="changed"):
        measure_file(path, 32, file_id="asset")
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_input.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

完整新增 `acceptance/input_bundle.py`：

```python
from __future__ import annotations

from typing import Any

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from acceptance.canonical import digest
from acceptance.primitives import AcceptanceFailure

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def valid_id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def relative_path(value: object) -> str:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise AcceptanceFailure("contract_invalid", "invalid relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise AcceptanceFailure("contract_invalid", "path must contain ordinary relative segments")
    return value


def open_parent(path: Path) -> tuple[int, str]:
    path = path.expanduser().absolute()
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for segment in path.parts[1:-1]:
            next_fd = os.open(segment, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd, path.name
    except BaseException:
        os.close(fd)
        raise


def safe_open(path: Path, flags: int, mode: int = 0o600) -> int:
    parent, name = open_parent(path)
    try:
        return os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=parent)
    finally:
        os.close(parent)


@dataclass(frozen=True, slots=True)
class BoundFile:
    id: str
    path: Path
    bytes: int
    sha256: str

    def descriptor(self, relative: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": relative_path(relative),
            "bytes": self.bytes,
            "sha256": self.sha256,
        }


def measure_file(
    path: Path, max_bytes: int, *, file_id: str, copy_to: Path | None = None
) -> BoundFile:
    if not valid_id(file_id) or type(max_bytes) is not int or max_bytes < 0:
        raise AcceptanceFailure("contract_invalid", "invalid file identity/budget")
    src = safe_open(path, os.O_RDONLY)
    dst = -1
    try:
        before = os.fstat(src)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise AcceptanceFailure("evidence_file_invalid", "not a bounded regular file")
        if copy_to is not None:
            dst = safe_open(copy_to, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        hasher = hashlib.sha256()
        count = 0
        while True:
            chunk = os.read(src, min(1024 * 1024, max_bytes - count + 1))
            if not chunk:
                break
            count += len(chunk)
            if count > max_bytes:
                raise AcceptanceFailure("evidence_file_invalid", "file grew beyond budget")
            hasher.update(chunk)
            if dst >= 0:
                view = memoryview(chunk)
                while view:
                    written = os.write(dst, view)
                    view = view[written:]
        after = os.fstat(src)

        def signature(s: os.stat_result) -> tuple[int, int, int, int, int]:
            return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

        if signature(before) != signature(after) or count != before.st_size:
            raise AcceptanceFailure("hash_mismatch", "file changed while reading")
        if dst >= 0:
            os.fsync(dst)
            os.fchmod(dst, 0o400)
        return BoundFile(file_id, copy_to or path, count, hasher.hexdigest())
    finally:
        if dst >= 0:
            os.close(dst)
        os.close(src)


def descriptor_valid(entry: object) -> bool:
    if type(entry) is not dict or set(entry) != {"id", "path", "bytes", "sha256"}:
        return False
    if not valid_id(entry["id"]) or type(entry["bytes"]) is not int or entry["bytes"] < 0:
        return False
    if type(entry["sha256"]) is not str or _HEX.fullmatch(entry["sha256"]) is None:
        return False
    relative_path(entry["path"])
    return True


def source_digest(entries: list[dict[str, Any]]) -> str:
    if any(not descriptor_valid(row) for row in entries):
        raise AcceptanceFailure("contract_invalid", "invalid source descriptor")
    if (
        not entries
        or entries != sorted(entries, key=lambda row: row["id"])
        or len({r["id"] for r in entries}) != len(entries)
        or len({r["path"] for r in entries}) != len(entries)
    ):
        raise AcceptanceFailure("contract_invalid", "source members must be unique and ordered")
    return digest("source.v2", entries)


def verify_bundle(
    root: Path, entries: list[dict[str, Any]], *, max_file_bytes: int
) -> dict[str, BoundFile]:
    source_digest(entries)
    expected = {row["path"] for row in entries}
    actual = set()
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            if (Path(current) / name).is_symlink():
                raise AcceptanceFailure("evidence_file_invalid", "symlink directory in source")
        for name in files:
            actual.add((Path(current) / name).relative_to(root).as_posix())
    if actual != expected:
        raise AcceptanceFailure("expected_set_mismatch", "source file set changed")
    result = {}
    for entry in entries:
        actual_file = measure_file(root / entry["path"], max_file_bytes, file_id=entry["id"])
        if actual_file.bytes != entry["bytes"] or actual_file.sha256 != entry["sha256"]:
            raise AcceptanceFailure("hash_mismatch", "source bytes do not match contract")
        result[entry["id"]] = actual_file
    return result


def freeze_bundle(
    sources: list[dict[str, Any]],
    root: Path,
    *,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> list[dict[str, Any]]:
    if root.exists() or not 0 < len(sources) <= max_files:
        raise AcceptanceFailure("contract_invalid", "new bounded source bundle required")
    for source in sources:
        if type(source) is not dict or set(source) != {"id", "path", "source"}:
            raise AcceptanceFailure("contract_invalid", "source needs id/path/source")
        if not valid_id(source["id"]):
            raise AcceptanceFailure("contract_invalid", "invalid source id")
        relative_path(source["path"])
    if len({r["id"] for r in sources}) != len(sources) or len({r["path"] for r in sources}) != len(
        sources
    ):
        raise AcceptanceFailure("contract_invalid", "duplicate source member")
    root.mkdir(mode=0o700)
    rows = []
    total = 0
    for source in sorted(sources, key=lambda row: row["id"]):
        target = root / source["path"]
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        measured = measure_file(
            Path(source["source"]),
            min(max_file_bytes, max_total_bytes - total),
            file_id=source["id"],
            copy_to=target,
        )
        total += measured.bytes
        rows.append(measured.descriptor(source["path"]))
    return rows


def read_bounded(path: Path, max_bytes: int) -> bytes:
    fd = safe_open(path, os.O_RDONLY)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise AcceptanceFailure("evidence_file_invalid", "invalid bounded JSON file")
        chunks = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)

        def signature(s: os.stat_result) -> tuple[int, int, int, int, int]:
            return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

        raw = b"".join(chunks)
        if (
            signature(before) != signature(after)
            or len(raw) != before.st_size
            or len(raw) > max_bytes
        ):
            raise AcceptanceFailure("hash_mismatch", "JSON changed or exceeded budget")
        return raw
    finally:
        os.close(fd)


def validate_roots(
    source_root: Path, evidence_root: Path, scratch_root: Path, repo_root: Path
) -> None:
    roots = [p.expanduser().absolute() for p in (source_root, evidence_root, scratch_root)]
    for root in roots:
        parent, name = open_parent(root)
        try:
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if info is not None and not stat.S_ISDIR(info.st_mode):
                raise AcceptanceFailure(
                    "contract_invalid", "managed root is not an ordinary directory"
                )
        finally:
            os.close(parent)
        if root == repo_root or repo_root in root.parents:
            raise AcceptanceFailure("contract_invalid", "managed root is inside repository")
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if left == right or left in right.parents or right in left.parents:
                raise AcceptanceFailure("contract_invalid", "managed roots overlap")
```

路径先验证每一层父目录，不先 resolve 用户输入从而抹掉符号链接；macOS 的系统 `/tmp` 别名应由调用者选择实际目录路径。源读取一份 fd；复制结果与合同核对，不在后续重新打开编辑源。失败只留下本次独占的未完成目录，不删除原输入。

- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_input.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。

### Task 3: v2 封闭合同、深不可变及显式拒绝 v1

**Files:**
- Modify: `acceptance/contract.py`（完整替换）
- Create: `tests/unit/asset_v2_support.py`
- Test: `tests/unit/test_asset_v2_contract.py`

**Interfaces:**
- Consumes: Task 1 注册表、Task 2 source digest/有界读取。
- Produces: `Contract`、`load_contract(path, *, candidate_root)`、`freeze()`/`thaw()`；保持 M2/M3 共享属性。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_contract.py`：

```python
from dataclasses import replace
import json
import pytest
from acceptance.contract import load_contract
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document, write_contract


def test_deep_immutable_snapshot_and_domain(tmp_path):
    document = valid_document(tmp_path)
    contract = write_contract(tmp_path, document)
    document["budget"]["max_files"] = 1
    assert contract.raw["budget"]["max_files"] == 1000
    with pytest.raises(TypeError):
        contract.raw["budget"]["max_files"] = 2
    with pytest.raises(AcceptanceFailure, match="digest"):
        replace(contract, digest="0" * 64)


@pytest.mark.parametrize(
    "mutation",
    [
        "v1",
        "bool_version",
        "wrong_nested_type",
        "tool_missing",
        "tool_duplicate",
        "hash_not_hex",
        "bool_budget",
        "unknown_nested",
        "old_impl",
        "input_digest",
        "forged_na",
        "native_opaque",
        "unknown_review",
        "coverage_allowance",
    ],
)
def test_closed_schema_rejects_specific_counterexample(tmp_path, mutation):
    value = valid_document(tmp_path)
    if mutation == "v1":
        value["schema_version"] = 1
    elif mutation == "bool_version":
        value["schema_version"] = True
    elif mutation == "wrong_nested_type":
        value["limits"] = "bad"
    elif mutation == "tool_missing":
        value["tools"] = []
    elif mutation == "tool_duplicate":
        value["tools"].append(dict(value["tools"][0]))
    elif mutation == "hash_not_hex":
        value["tools"][0]["sha256"] = "z" * 64
    elif mutation == "bool_budget":
        value["budget"]["max_files"] = True
    elif mutation == "unknown_nested":
        value["input"]["shadow"] = {}
    elif mutation == "old_impl":
        value["checks"][0]["impl"] = 0
    elif mutation == "input_digest":
        value["input"]["sha256"] = "0" * 64
    elif mutation == "forged_na":
        value["na_check_ids"] = []
    elif mutation == "native_opaque":
        value["native"] = {"anything": True}
    elif mutation == "unknown_review":
        value["review"]["approved"] = True
    elif mutation == "coverage_allowance":
        value["warning_allowlist"] = [
            {
                "check_id": "r2.inventory.coverage_complete",
                "warning_code": "unsupported_datablock_type",
                "tool_id": "blender",
                "tool_version": "Blender 5.2.0 LTS",
            }
        ]
    with pytest.raises(AcceptanceFailure):
        write_contract(tmp_path, value)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_strict_utf8_and_contract_size_cap(tmp_path, encoding):
    value = valid_document(tmp_path)
    path = tmp_path / "contract.json"
    path.write_bytes(json.dumps(value).encode(encoding))
    with pytest.raises(AcceptanceFailure):
        load_contract(path, candidate_root=tmp_path / "source")


def test_declared_baseline_is_enforced_not_just_hashed(tmp_path):
    from acceptance.contract import enforce_baseline, _BASELINE_FIELDS
    from acceptance.input_bundle import measure_file, source_digest, verify_bundle

    value = valid_document(tmp_path)
    baseline = {
        "schema_version": 2,
        "kind": "acceptance_policy_baseline",
        "constraints": {key: value[key] for key in _BASELINE_FIELDS},
    }
    path = tmp_path / "source/baseline.json"
    path.write_text(json.dumps(baseline))
    value["input"]["files"].append(
        measure_file(path, 1048576, file_id="policy").descriptor("baseline.json")
    )
    value["input"]["sha256"] = source_digest(value["input"]["files"])
    value["policy_baseline"] = "policy"
    contract = write_contract(tmp_path, value)
    inputs = verify_bundle(tmp_path / "source", value["input"]["files"], max_file_bytes=1048576)
    enforce_baseline(contract, inputs)
    value["budget"]["max_files"] += 1
    changed = write_contract(tmp_path, value)
    with pytest.raises(AcceptanceFailure, match="baseline"):
        enforce_baseline(changed, inputs)
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_contract.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

完整替换 `acceptance/contract.py`：

```python
from __future__ import annotations

from typing import Any

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from acceptance import check_registry as reg
from acceptance.canonical import digest
from acceptance.input_bundle import read_bounded, source_digest, valid_id
from acceptance.primitives import AcceptanceFailure
from acceptance.strict_json import strict_json_loads

_MAX_CONTRACT_BYTES = 1024 * 1024
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TOP = {
    "schema_version",
    "contract_id",
    "artifact_kind",
    "profile",
    "required_isolation_grade",
    "input",
    "checks",
    "na_check_ids",
    "warning_allowlist",
    "tools",
    "limits",
    "budget",
    "native",
    "interchange",
    "review",
    "policy_baseline",
}


def freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if type(value) is list:
        return tuple(freeze(v) for v in value)
    return value


def thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if type(value) is tuple:
        return [thaw(v) for v in value]
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceFailure("contract_invalid", message)


def fields(value: Any, expected: set[str], name: str) -> None:
    require(type(value) is dict and set(value) == expected, f"{name}: closed fields required")


def positive(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def sha(value: Any) -> bool:
    return type(value) is str and _HEX.fullmatch(value) is not None


def validate_document(value: Any) -> None:
    fields(value, _TOP, "contract")
    require(
        type(value["schema_version"]) is int and value["schema_version"] == 2,
        "schema_version must be 2; v1 requires a new frozen candidate and contract",
    )
    require(valid_id(value["contract_id"]), "invalid contract_id")
    require(value["artifact_kind"] in ("blend_native", "interchange"), "invalid artifact_kind")
    require(value["profile"] == "static_render", "only static_render supported")
    require(
        value["required_isolation_grade"] == "local-trusted", "M1 has no isolated/attested runner"
    )
    source = value["input"]
    fields(source, {"main", "sha256", "files"}, "input")
    require(type(source["files"]) is list and sha(source["sha256"]), "invalid source identity")
    require(source_digest(source["files"]) == source["sha256"], "input package digest mismatch")
    require(source["main"] in {row["id"] for row in source["files"]}, "main input is not a member")
    specs = sorted(reg.checks_for_kind(value["artifact_kind"]), key=reg.sort_key)
    expected = [{"id": s.id, "impl": s.impl, "order": s.order} for s in specs]
    require(
        type(value["checks"]) is list and value["checks"] == expected, "check registry mismatch"
    )
    require(
        all(
            type(r) is dict
            and set(r) == {"id", "impl", "order"}
            and type(r["impl"]) is int
            and type(r["order"]) is int
            for r in value["checks"]
        ),
        "check types must be exact",
    )
    require(
        value["na_check_ids"] == list(reg.na_check_ids(value["artifact_kind"])),
        "N/A registry mismatch",
    )
    require(type(value["warning_allowlist"]) is list, "warning_allowlist must be a list")
    by_id = {s.id: s for s in specs}
    seen = set()
    for row in value["warning_allowlist"]:
        fields(row, {"check_id", "warning_code", "tool_id", "tool_version"}, "warning")
        require(all(type(v) is str and v for v in row.values()), "warning values must be strings")
        require(
            row["check_id"] in by_id
            and row["warning_code"] in by_id[row["check_id"]].warning_codes,
            "unknown warning rule",
        )
        require(
            row["check_id"] != "r2.inventory.coverage_complete",
            "unsupported coverage cannot be allowlisted",
        )
        key = tuple(sorted(row.items()))
        require(key not in seen, "duplicate warning rule")
        seen.add(key)
    fields(
        value["budget"],
        {"max_files", "max_file_bytes", "max_total_bytes", "max_result_bytes"},
        "budget",
    )
    require(
        all(type(v) is int and v > 0 for v in value["budget"].values()),
        "positive integer budgets required",
    )
    budget = value["budget"]
    require(
        len(source["files"]) <= budget["max_files"]
        and sum(r["bytes"] for r in source["files"]) <= budget["max_total_bytes"]
        and all(r["bytes"] <= budget["max_file_bytes"] for r in source["files"]),
        "source exceeds budget",
    )
    fields(
        value["limits"],
        {
            "timeout_seconds",
            "cpu_seconds",
            "rss_bytes",
            "open_files",
            "log_bytes",
            "file_size_bytes",
        },
        "limits",
    )
    limits = value["limits"]
    require(
        type(limits["timeout_seconds"]) is dict
        and all(type(k) is str and positive(v) for k, v in limits["timeout_seconds"].items()),
        "invalid writer timeouts",
    )
    require(
        all(type(limits[k]) is int and limits[k] > 0 for k in limits if k != "timeout_seconds"),
        "resource limits must be positive integers",
    )
    require(type(value["tools"]) is list and bool(value["tools"]), "tools cannot be empty")
    ids = set()
    for tool in value["tools"]:
        fields(tool, {"id", "path", "version", "sha256", "files"}, "tool")
        require(
            tool["id"] in {"python", "acceptance", "blender", "node"} and tool["id"] not in ids,
            "unknown or repeated tool",
        )
        ids.add(tool["id"])
        require(
            type(tool["path"]) is str and Path(tool["path"]).is_absolute(),
            "absolute tool path required",
        )
        require(
            type(tool["version"]) is str and bool(tool["version"]) and sha(tool["sha256"]),
            "invalid tool lock",
        )
        require(type(tool["files"]) is list, "tool files must be a list")
        seen_paths = set()
        for row in tool["files"]:
            fields(row, {"path", "bytes", "sha256"}, "tool file")
            require(
                type(row["path"]) is str
                and Path(row["path"]).is_absolute()
                and row["path"] not in seen_paths
                and sha(row["sha256"])
                and type(row["bytes"]) is int
                and row["bytes"] >= 0,
                "invalid tool file",
            )
            seen_paths.add(row["path"])
    require({"acceptance", "python", "blender"} <= ids, "required tool set is incomplete")
    # M2/M3 replace only these two rejection rules with their pure-Python validators.
    require(value["native"] is None, "native worker policy is not implemented in M1")
    require(value["interchange"] is None, "interchange worker policy is not implemented in M1")
    fields(value["review"], {"required", "reviewer_ids", "required_image_ids", "reason"}, "review")
    review = value["review"]
    require(
        type(review["required"]) is bool
        and type(review["reviewer_ids"]) is list
        and all(valid_id(x) for x in review["reviewer_ids"])
        and len(set(review["reviewer_ids"])) == len(review["reviewer_ids"])
        and type(review["reason"]) is str
        and bool(review["reason"]),
        "invalid review policy",
    )
    require(
        type(review["required_image_ids"]) is list
        and all(valid_id(x) for x in review["required_image_ids"])
        and len(set(review["required_image_ids"])) == len(review["required_image_ids"]),
        "invalid required images",
    )
    require(
        not review["required"] or bool(review["reviewer_ids"]), "required review needs reviewers"
    )
    require(
        value["policy_baseline"] is None
        or value["policy_baseline"] in {r["id"] for r in source["files"]},
        "policy baseline must be a frozen source reference",
    )


@dataclass(frozen=True, slots=True)
class Contract:
    raw: Mapping[str, Any]
    digest: str
    byte_sha256: str = ""

    def __post_init__(self) -> None:
        value = thaw(self.raw)
        validate_document(value)
        expected = digest("contract.v2", value)
        require(self.digest == expected, "Contract digest inconsistent with fields")
        object.__setattr__(self, "raw", freeze(value))

    @property
    def artifact_kind(self) -> Any:
        return self.raw["artifact_kind"]

    @property
    def na_check_ids(self) -> Any:
        return self.raw["na_check_ids"]

    @property
    def required_isolation_grade(self) -> Any:
        return self.raw["required_isolation_grade"]

    def allowlisted(self, check_id: Any, code: Any, tool_id: Any, version: Any) -> Any:
        target = {
            "check_id": check_id,
            "warning_code": code,
            "tool_id": tool_id,
            "tool_version": version,
        }
        return any(dict(row) == target for row in self.raw["warning_allowlist"])


def load_contract(path: Path, *, candidate_root: Path) -> Contract:
    candidate_root = candidate_root.expanduser().absolute()
    path = path.expanduser().absolute()
    require(
        path != candidate_root and candidate_root not in path.parents,
        "contract must live outside candidate input tree",
    )
    try:
        raw = read_bounded(path, _MAX_CONTRACT_BYTES)
        value: Any = strict_json_loads(raw.decode("utf-8"))
        validate_document(value)
        return Contract(value, digest("contract.v2", value), hashlib.sha256(raw).hexdigest())
    except AcceptanceFailure as exc:
        raise AcceptanceFailure("contract_invalid", str(exc)) from exc
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise AcceptanceFailure("contract_invalid", str(exc)) from exc


_BASELINE_FIELDS = {
    "tools",
    "warning_allowlist",
    "budget",
    "limits",
    "review",
    "native",
    "interchange",
}


def enforce_baseline(contract: Contract, input_files: Mapping[str, Any]) -> None:
    reference = contract.raw["policy_baseline"]
    if reference is None:
        return
    raw = read_bounded(input_files[reference].path, _MAX_CONTRACT_BYTES)
    baseline: Any = strict_json_loads(raw.decode("utf-8"))
    fields(baseline, {"schema_version", "kind", "constraints"}, "baseline")
    require(
        type(baseline["schema_version"]) is int
        and baseline["schema_version"] == 2
        and baseline["kind"] == "acceptance_policy_baseline",
        "invalid baseline version/kind",
    )
    fields(baseline["constraints"], _BASELINE_FIELDS, "baseline constraints")
    expected = {key: thaw(contract.raw[key]) for key in _BASELINE_FIELDS}
    require(
        baseline["constraints"] == expected,
        "policy differs from frozen deployment baseline; create a newly authorized baseline and run",
    )
```

完整新增共享测试构造器 `tests/unit/asset_v2_support.py`：

```python
from __future__ import annotations

import json
import sys
from pathlib import Path

from acceptance import check_registry as reg
from acceptance.contract import load_contract
from acceptance.input_bundle import measure_file, source_digest
from acceptance.canonical import digest

REPO = Path(__file__).resolve().parents[2]


def file_lock(path):
    measured = measure_file(path.resolve(), 2 * 1024**3, file_id="lock")
    return {"path": str(path.absolute()), "bytes": measured.bytes, "sha256": measured.sha256}


def trusted_code_files(repo_root):
    # Fixture owns its expected code lock before the production toolchain task exists.
    return tuple(
        sorted(
            list((repo_root / "acceptance").rglob("*.py"))
            + list((repo_root / "acceptance").rglob("*.json"))
            + [repo_root / "scripts/asset_accept.py", repo_root / "smoke/process_registry.py"]
        )
    )


def provenance(repo_root):
    rows = [
        {
            "path": p.relative_to(repo_root).as_posix(),
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for p in trusted_code_files(repo_root)
        for item in (file_lock(p),)
    ]
    return {"version": "acc-v2-" + digest("code.v2", rows)}


def valid_document(tmp_path):
    source_root = tmp_path / "source"
    source_root.mkdir()
    asset = source_root / "asset.blend"
    asset.write_bytes(b"fixture source bytes; this is not a Blender asset")
    descriptor = measure_file(asset, 1024, file_id="asset").descriptor("asset.blend")
    fake_blender = tmp_path / "fixture-blender"
    fake_blender.write_text(f"#!{sys.executable}\nprint('Blender 5.2.0 LTS')\n")
    fake_blender.chmod(0o700)

    def tool(key, path, version, files):
        return {
            "id": key,
            "path": str(path),
            "version": version,
            "sha256": file_lock(path)["sha256"],
            "files": files,
        }

    return {
        "schema_version": 2,
        "contract_id": "fixture-001",
        "artifact_kind": "blend_native",
        "profile": "static_render",
        "required_isolation_grade": "local-trusted",
        "input": {"main": "asset", "sha256": source_digest([descriptor]), "files": [descriptor]},
        "checks": [
            {"id": s.id, "impl": s.impl, "order": s.order}
            for s in sorted(reg.checks_for_kind("blend_native"), key=reg.sort_key)
        ],
        "na_check_ids": list(reg.na_check_ids("blend_native")),
        "warning_allowlist": [],
        "tools": [
            tool("python", Path(sys.executable).resolve(), "Python 3.13.13", []),
            tool(
                "acceptance",
                REPO / "scripts/asset_accept.py",
                provenance(REPO)["version"],
                [file_lock(p) for p in trusted_code_files(REPO)],
            ),
            tool("blender", fake_blender, "Blender 5.2.0 LTS", []),
        ],
        "limits": {
            "timeout_seconds": {"inspector": 5, "reopen_probe": 5, "render_views(src)": 5},
            "cpu_seconds": 10,
            "rss_bytes": 2 * 1024**3,
            "open_files": 128,
            "log_bytes": 8192,
            "file_size_bytes": 1024 * 1024,
        },
        "budget": {
            "max_files": 1000,
            "max_file_bytes": 2 * 1024 * 1024,
            "max_total_bytes": 16 * 1024 * 1024,
            "max_result_bytes": 1024 * 1024,
        },
        "native": None,
        "interchange": None,
        "review": {
            "required": False,
            "reviewer_ids": [],
            "required_image_ids": [],
            "reason": "unit fixture only; not production asset approval",
        },
        "policy_baseline": None,
    }


def write_contract(tmp_path, value):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "source")
```

上列测试已使用目标导入 `tests.unit.asset_v2_support`，REPO 已是仓库根 parents[2]。构造器独立建立预期工具锁，因此 Task 3 不依赖 Task 5 尚未创建的 toolchain；测试合同不构成未来资产签收。

- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_contract.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。

### Task 4: 不可变计划与标准 JSON worker 协议

**Files:**
- Create: `acceptance/plan.py`
- Create: `acceptance/worker_protocol.py`
- Test: `tests/unit/test_asset_v2_protocol.py`

**Interfaces:**
- Consumes: Task 3 Contract/thaw、37 项注册表。
- Produces: 共享 FileSpec/JobSpec/RunPlan/assemble_plan、read_request/write_result/validate_result；安全前置用 blocking_check_ids，required gate 用 gate_ids。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_protocol.py`：

```python
import copy
import json
import pytest
from acceptance.plan import JobSpec, assemble_plan
from acceptance.primitives import AcceptanceFailure
from acceptance.worker_protocol import read_request, validate_result, write_result
from tests.unit.asset_v2_support import valid_document, write_contract


def request_fixture(tmp_path):
    inputs, outputs = tmp_path / "input", tmp_path / "output"
    inputs.mkdir()
    outputs.mkdir()
    return {
        "schema_version": 2,
        "run_id": "run-001",
        "attempt": 1,
        "nonce": "a" * 32,
        "job_id": "inspect",
        "writer": "inspector",
        "contract_digest": "b" * 64,
        "source_digest": "c" * 64,
        "input_root": str(inputs),
        "inputs": [],
        "output_root": str(outputs),
        "outputs": [],
        "parameters": {},
    }


def test_result_has_no_self_reference_and_controller_owns_state(tmp_path):
    request = request_fixture(tmp_path)
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    request = read_request(path)
    result_path = write_result(
        request, [{"id": "r2.inventory.no_nan_inf", "findings": [], "metrics": {}}], {}
    )
    result = json.loads(result_path.read_text())
    assert result["artifacts"] == []
    assert validate_result(result, request, ("r2.inventory.no_nan_inf",)) == result
    result["success"] = True
    with pytest.raises(ValueError, match="closed result"):
        validate_result(result, request, ("r2.inventory.no_nan_inf",))


@pytest.mark.parametrize(
    "change", ["nonce", "version", "check", "duplicate", "disposition", "nan", "artifact"]
)
def test_result_boundary_rejects_forgery(tmp_path, change):
    request = request_fixture(tmp_path)
    path = write_result(
        request, [{"id": "r2.inventory.no_nan_inf", "findings": [], "metrics": {}}], {}
    )
    result = json.loads(path.read_text())
    if change == "nonce":
        result["nonce"] = "d" * 32
    elif change == "version":
        result["schema_version"] = 1
    elif change == "check":
        result["checks"][0]["id"] = "r0.contract.tools_locked"
    elif change == "duplicate":
        result["checks"].append(copy.deepcopy(result["checks"][0]))
    elif change == "disposition":
        result["checks"][0]["findings"] = [
            {
                "code": "x",
                "severity": "warning",
                "pointer": None,
                "detail": None,
                "disposition": "AcceptedWarning",
            }
        ]
    elif change == "nan":
        result["checks"][0]["metrics"] = {"bad": float("nan")}
    else:
        result["artifacts"] = [
            {"id": "self", "path": "result.json", "bytes": 1, "sha256": "a" * 64}
        ]
    with pytest.raises(ValueError):
        validate_result(result, request, ("r2.inventory.no_nan_inf",))


def test_plan_derives_required_checks_and_closes_writers(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    plan = assemble_plan(contract, ())
    assert len(plan.check_ids) == 24 and len(plan.na_check_ids) == 13
    assert {f.id for f in plan.files} == {"run", "gates"}
    job = JobSpec(
        "inspect", "inspector", "blender", ("r0.contract.tools_locked",), ("asset",), (), {}
    )
    with pytest.raises(AcceptanceFailure, match="writer"):
        assemble_plan(contract, (job,))
    job = JobSpec("inspect", "inspector", "blender", (), ("missing",), (), {})
    with pytest.raises(AcceptanceFailure, match="earlier job"):
        assemble_plan(contract, (job,))
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_protocol.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

完整新增 `acceptance/plan.py`：

```python
from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from dataclasses import dataclass

from acceptance import check_registry as reg
from acceptance.contract import Contract, freeze, thaw, require
from acceptance.input_bundle import relative_path, valid_id

_MEDIA = {
    "application/json",
    "image/png",
    "model/gltf-binary",
    "application/octet-stream",
    "text/plain",
}


@dataclass(frozen=True, slots=True)
class FileSpec:
    id: str
    path: str
    writer: str
    media_type: str
    max_bytes: int

    def __post_init__(self) -> None:
        require(valid_id(self.id), "invalid file id")
        relative_path(self.path)
        require(
            self.media_type in _MEDIA and type(self.max_bytes) is int and self.max_bytes > 0,
            "invalid file type/budget",
        )


@dataclass(frozen=True, slots=True)
class JobSpec:
    job_id: str
    writer: str
    tool_id: str
    check_ids: tuple[str, ...]
    input_ids: tuple[str, ...]
    outputs: tuple[FileSpec, ...]
    parameters: Mapping[str, Any]
    blocking_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require(
            valid_id(self.job_id) and type(self.writer) is str and bool(self.writer),
            "invalid job identity",
        )
        require(self.tool_id in {"python", "blender", "node"}, "unsupported job tool")
        require(
            type(self.parameters) is dict or isinstance(self.parameters, Mapping),
            "parameters must be mapping",
        )
        object.__setattr__(self, "parameters", freeze(thaw(self.parameters)))


@dataclass(frozen=True, slots=True)
class RunPlan:
    jobs: tuple[JobSpec, ...]
    files: tuple[FileSpec, ...]
    check_ids: tuple[str, ...]
    na_check_ids: tuple[str, ...]
    required_tools: tuple[str, ...]
    gate_ids: tuple[str, ...] = ()


def assemble_plan(
    contract: Contract, jobs: tuple[JobSpec, ...], *, gate_ids: tuple[str, ...] = ()
) -> RunPlan:
    specs = {s.id: s for s in reg.checks_for_kind(contract.artifact_kind)}
    known_inputs = {row["id"] for row in contract.raw["input"]["files"]}
    claimed: set[str] = set()
    job_ids = set()
    budget = contract.raw["budget"]
    require(
        len(set(gate_ids)) == len(gate_ids) and all(valid_id(k) for k in gate_ids),
        "invalid gate set",
    )
    files = [
        FileSpec(k, f"{k}.json", "coordinator", "application/json", budget["max_result_bytes"])
        for k in ("run", "gates")
    ]
    for job in jobs:
        require(job.job_id not in job_ids, "duplicate job")
        job_ids.add(job.job_id)
        require(job.writer != "coordinator", "subprocess cannot claim coordinator writer")
        require(
            job.writer in contract.raw["limits"]["timeout_seconds"], "missing writer wall timeout"
        )
        require(
            len(set(job.input_ids)) == len(job.input_ids) and set(job.input_ids) <= known_inputs,
            "input must come from frozen source or an earlier job",
        )
        require(set(job.blocking_check_ids) <= claimed, "blocking check must precede this job")
        for check_id in job.check_ids:
            require(
                check_id in specs
                and specs[check_id].writer == job.writer
                and check_id not in claimed,
                "unknown, duplicate or wrong-writer check",
            )
            claimed.add(check_id)
        for output in job.outputs:
            require(
                output.writer == job.writer and output.path != "result.json",
                "wrong writer or reserved result path",
            )
            require(
                output.id not in known_inputs, "output cannot overwrite source or earlier output"
            )
            known_inputs.add(output.id)
            files.append(
                FileSpec(
                    output.id,
                    f"{job.job_id}/{output.path}",
                    output.writer,
                    output.media_type,
                    output.max_bytes,
                )
            )
        for suffix, name, owner, media, limit in (
            ("result", "result.json", job.writer, "application/json", budget["max_result_bytes"]),
            (
                "request",
                "request.json",
                "coordinator",
                "application/json",
                budget["max_result_bytes"],
            ),
            ("job", "job.json", "coordinator", "application/json", budget["max_result_bytes"]),
            (
                "log",
                "process.log",
                "coordinator",
                "text/plain",
                contract.raw["limits"]["log_bytes"],
            ),
        ):
            files.append(
                FileSpec(f"{job.job_id}.{suffix}", f"{job.job_id}/{name}", owner, media, limit)
            )
    require(
        len({s.id for s in files}) == len(files) and len({s.path for s in files}) == len(files),
        "duplicate planned file id/path",
    )
    require(len(files) <= budget["max_files"], "file plan exceeds count budget")
    require(
        set(contract.raw["review"]["required_image_ids"])
        <= {f.id for f in files if f.media_type == "image/png"},
        "required review image is not in file plan",
    )
    required = {"python", "acceptance", "blender"} | {j.tool_id for j in jobs}
    require(required <= {t["id"] for t in contract.raw["tools"]}, "missing planned tool")
    return RunPlan(
        jobs,
        tuple(files),
        tuple(specs),
        tuple(contract.na_check_ids),
        tuple(sorted(required)),
        gate_ids,
    )
```

完整新增 `acceptance/worker_protocol.py`：

```python
from __future__ import annotations

from typing import Any, cast

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path, PurePosixPath

from acceptance.strict_json import strict_json_loads

IDENTITY = (
    "schema_version",
    "run_id",
    "attempt",
    "nonce",
    "job_id",
    "writer",
    "contract_digest",
    "source_digest",
)
_REQUEST = set(IDENTITY) | {"input_root", "inputs", "output_root", "outputs", "parameters"}
_RESULT = set(IDENTITY) | {"checks", "artifacts", "observations"}


def ensure(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rel(value: Any) -> str:
    ensure(
        type(value) is str and value and "\\" not in value and "\x00" not in value,
        "invalid artifact path",
    )
    ensure(
        not PurePosixPath(value).is_absolute()
        and all(x not in ("", ".", "..") for x in value.split("/")),
        "path escapes root",
    )
    return cast(str, value)


def read_json(path: Path, max_bytes: int = 1048576) -> Any:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        ensure(
            stat.S_ISREG(st.st_mode) and st.st_size <= max_bytes, "JSON is not bounded regular file"
        )
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(max_bytes + 1)
        ensure(len(raw) <= max_bytes, "JSON overflow")
        return strict_json_loads(raw.decode("utf-8"))
    finally:
        os.close(fd)


def check_identity(value: Any) -> None:
    ensure(
        type(value["schema_version"]) is int and value["schema_version"] == 2, "schema must be 2"
    )
    ensure(type(value["attempt"]) is int and value["attempt"] >= 1, "attempt must be positive int")
    ensure(
        all(type(value[k]) is str and value[k] for k in ("run_id", "job_id", "writer")),
        "invalid identity strings",
    )
    ensure(
        type(value["nonce"]) is str and re.fullmatch("[0-9a-f]{32}", value["nonce"]),
        "invalid nonce",
    )
    ensure(
        all(
            type(value[k]) is str and re.fullmatch("[0-9a-f]{64}", value[k])
            for k in ("contract_digest", "source_digest")
        ),
        "invalid digest",
    )


def artifact(path: Path, file_id: str, relative: str, max_bytes: int) -> Any:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        ensure(stat.S_ISREG(before.st_mode) and before.st_size <= max_bytes, "invalid artifact")
        hasher, count = hashlib.sha256(), 0
        while True:
            part = os.read(fd, min(1048576, max_bytes - count + 1))
            if not part:
                break
            count += len(part)
            ensure(count <= max_bytes, "artifact exceeds budget")
            hasher.update(part)
        after = os.fstat(fd)
        ensure(
            (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "artifact changed",
        )
        return {"id": file_id, "path": rel(relative), "bytes": count, "sha256": hasher.hexdigest()}
    finally:
        os.close(fd)


def read_request(path: Path) -> dict[str, Any]:
    value = read_json(path)
    ensure(type(value) is dict and set(value) == _REQUEST, "closed request required")
    check_identity(value)
    ensure(type(value["parameters"]) is dict, "parameters must be object")
    ensure(type(value["inputs"]) is list and type(value["outputs"]) is list, "file lists required")
    for key in ("input_root", "output_root"):
        ensure(type(value[key]) is str and Path(value[key]).is_absolute(), "absolute root required")
    roots = [Path(value[k]) for k in ("input_root", "output_root")]
    ensure(
        roots[0] != roots[1]
        and roots[0] not in roots[1].parents
        and roots[1] not in roots[0].parents,
        "input/output roots overlap",
    )
    for row in value["inputs"]:
        ensure(
            type(row) is dict and set(row) == {"id", "path", "bytes", "sha256"},
            "invalid input descriptor",
        )
        measured = artifact(roots[0] / rel(row["path"]), row["id"], row["path"], row["bytes"])
        ensure(measured == row, "input identity mismatch")
    for row in value["outputs"]:
        ensure(
            type(row) is dict and set(row) == {"id", "path", "media_type", "max_bytes"},
            "invalid output descriptor",
        )
        ensure(
            type(row["max_bytes"]) is int and row["max_bytes"] > 0 and row["path"] != "result.json",
            "invalid output budget/reserved path",
        )
        rel(row["path"])
    ensure(
        len({r["id"] for r in value["outputs"]}) == len(value["outputs"])
        and len({r["path"] for r in value["outputs"]}) == len(value["outputs"]),
        "duplicate output",
    )
    return cast(dict[str, Any], value)


def validate_result(
    result: Any, request: dict[str, Any], check_ids: tuple[str, ...]
) -> dict[str, Any]:
    ensure(type(result) is dict and set(result) == _RESULT, "closed result required")
    check_identity(result)
    ensure(all(result[k] == request[k] for k in IDENTITY), "stale or wrong result identity")
    ensure(type(result["checks"]) is list, "checks must be a list")
    seen = []
    for check in result["checks"]:
        ensure(
            type(check) is dict and set(check) == {"id", "findings", "metrics"},
            "closed check required",
        )
        seen.append(check["id"])
        ensure(
            type(check["metrics"]) is dict
            and all(
                type(k) is str
                and (
                    v is None
                    or type(v) in (str, bool)
                    or (type(v) in (int, float) and math.isfinite(v))
                )
                for k, v in check["metrics"].items()
            ),
            "metrics must be finite scalars",
        )
        ensure(type(check["findings"]) is list, "findings must be a list")
        for finding in check["findings"]:
            ensure(
                type(finding) is dict and set(finding) == {"code", "severity", "pointer", "detail"},
                "closed finding required",
            )
            ensure(
                type(finding["code"]) is str
                and bool(finding["code"])
                and finding["severity"] in ("error", "warning", "info"),
                "invalid finding",
            )
            ensure(
                all(finding[k] is None or type(finding[k]) is str for k in ("pointer", "detail")),
                "invalid finding text",
            )
    ensure(
        len(set(seen)) == len(seen) and set(seen) == set(check_ids), "check set or writer mismatch"
    )
    ensure(type(result["artifacts"]) is list, "artifacts must be a list")
    expected = {r["id"]: r for r in request["outputs"]}
    actual = result["artifacts"]
    ensure(
        len(actual) == len(expected)
        and len({r.get("id") for r in actual if type(r) is dict}) == len(actual),
        "artifact set mismatch",
    )
    for row in actual:
        ensure(
            type(row) is dict and set(row) == {"id", "path", "bytes", "sha256"},
            "closed artifact required",
        )
        ensure(
            row["id"] in expected and row["path"] == expected[row["id"]]["path"],
            "wrong artifact id/path",
        )
        ensure(
            type(row["bytes"]) is int
            and 0 <= row["bytes"] <= expected[row["id"]]["max_bytes"]
            and type(row["sha256"]) is str
            and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
            "bad artifact identity",
        )
    ensure(
        type(result["observations"]) is dict
        and all(type(k) is str and type(v) is str for k, v in result["observations"].items()),
        "observations must be string map",
    )
    return cast(dict[str, Any], result)


def write_result(
    request: dict[str, Any], checks: list[dict[str, Any]], observations: dict[str, str]
) -> Path:
    root = Path(request["output_root"])
    result = {k: request[k] for k in IDENTITY}
    result.update(
        checks=checks,
        observations=observations,
        artifacts=[
            artifact(root / row["path"], row["id"], row["path"], row["max_bytes"])
            for row in request["outputs"]
        ],
    )
    # The controller supplies the authoritative check set. This call still rejects malformed local structures.
    validate_result(result, request, tuple(row["id"] for row in checks))
    path = root / "result.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return path
```

request.outputs 不含 result.json；计划自动添加 result/request/job/log。parameters 来自受信 plan builder，M2/M3 的纯 Python policy 验证器必须封闭验证所有字段，不能由 CLI 任意 JSON 选择命令或 writer。
- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_protocol.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。

### Task 5: 精确工具身份与可执行的本机资源限制

**Files:**
- Modify: `acceptance/primitives.py`（只替换 run_command）
- Create: `acceptance/toolchain.py`
- Test: `tests/unit/test_asset_v2_toolchain.py`

**Interfaces:**
- Consumes: stop_group/group_exists/clean_environment、Task 2 文件读写。
- Produces: run_command(...,max_log_bytes,limits,observation)、provenance/measure_tool/verify_tools。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_toolchain.py`：

```python
from pathlib import Path
import sys
import pytest
from acceptance.primitives import AcceptanceFailure, run_command, clean_environment
from acceptance.toolchain import measure_tool, provenance, verify_tools
from tests.unit.asset_v2_support import REPO, file_lock, valid_document, write_contract


def test_full_tool_lock_and_shared_code_closure(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    measured = verify_tools(contract, ("acceptance", "python", "blender"), REPO)
    assert {m["id"] for m in measured} == {"acceptance", "python", "blender"}
    assert "smoke/process_registry.py" in {r["path"] for r in provenance(REPO)["files"]}


def test_python_cannot_impersonate_blender_even_when_hash_is_accurate(tmp_path):
    tool = valid_document(tmp_path)["tools"][2]
    tool["path"] = str(Path(sys.executable).resolve())
    tool["sha256"] = file_lock(Path(sys.executable))["sha256"]
    with pytest.raises(AcceptanceFailure, match="kind or supported version"):
        measure_tool(tool, REPO)


def test_dependency_replacement_is_not_hidden_by_same_executable(tmp_path):
    value = valid_document(tmp_path)
    script = tmp_path / "worker.py"
    script.write_text("print('first')\n")
    value["tools"][0]["files"].append(file_lock(script))
    script.write_text("print('second')\n")
    with pytest.raises(AcceptanceFailure, match="dependency"):
        measure_tool(value["tools"][0], REPO)


@pytest.mark.parametrize(
    "program,limit,expected",
    [
        ("import time; time.sleep(3)", 0.1, "tool_crashed"),
        ("import os; os.write(1, b'x'*65536)", 3.0, "evidence_truncated"),
    ],
)
def test_process_limits_produce_controller_accidents(tmp_path, program, limit, expected):
    with pytest.raises(AcceptanceFailure) as caught:
        run_command(
            "probe",
            [sys.executable, "-c", program],
            cwd=tmp_path,
            env=clean_environment(Path(sys.executable)),
            log_path=tmp_path / "log",
            timeout=limit,
            max_log_bytes=1024,
        )
    assert caught.value.code == expected
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_toolchain.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

以以下完整函数替换 `acceptance/primitives.py` 中 `run_command`，保留其他函数：

```python
def run_command(
    stage: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout: float,
    max_log_bytes: int = 2 * 1024 * 1024,
    limits: dict[str, int] | None = None,
    observation: dict[str, object] | None = None,
) -> int:
    import resource
    import datetime
    from acceptance.input_bundle import safe_open

    if timeout <= 0 or max_log_bytes <= 0:
        raise AcceptanceFailure("contract_invalid", "positive process budgets required")

    def constrain() -> None:
        file_limit = max_log_bytes if limits is None else limits["file_size_bytes"]
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
        if limits is not None:
            for key, limit_id in (
                ("cpu_seconds", resource.RLIMIT_CPU),
                ("open_files", resource.RLIMIT_NOFILE),
            ):
                hard = resource.getrlimit(limit_id)[1]
                value = limits[key] if hard == resource.RLIM_INFINITY else min(limits[key], hard)
                resource.setrlimit(limit_id, (value, value))

    descriptor = safe_open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=descriptor,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            umask=0o077,
            preexec_fn=constrain,
        )
    finally:
        os.close(descriptor)
    if observation is not None:
        observation.update(
            started=True,
            pid=process.pid,
            started_at=datetime.datetime.now(datetime.UTC).isoformat(),
        )

    def sample_rss() -> int:
        report = subprocess.run(
            ["/bin/ps", "-axo", "pid=,pgid=,rss="],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=True,
        )
        if len(report.stdout) > 2 * 1024 * 1024:
            raise AcceptanceFailure(
                "runner_internal_error", "RSS process inventory exceeded budget"
            )
        total = 0
        for line in report.stdout.splitlines():
            pid, group, rss = map(int, line.split())
            if group == process.pid:
                total += rss * 1024
        return total

    deadline = time.monotonic() + timeout
    next_sample = 0.0
    peak, samples = 0, 0
    try:
        while process.poll() is None:
            if limits is not None and time.monotonic() >= next_sample:
                rss = sample_rss()
                samples += 1
                peak = max(peak, rss)
                next_sample = time.monotonic() + 0.1
                if rss > limits["rss_bytes"]:
                    raise AcceptanceFailure(
                        "resource_limit_exceeded", f"{stage}: sampled group RSS exceeded budget"
                    )
            if log_path.stat().st_size >= max_log_bytes:
                raise AcceptanceFailure("evidence_truncated", f"{stage}: log budget reached")
            if time.monotonic() >= deadline:
                raise AcceptanceFailure("tool_crashed", f"{stage}: wall timeout")
            time.sleep(0.02)
        if log_path.stat().st_size >= max_log_bytes:
            raise AcceptanceFailure("evidence_truncated", f"{stage}: log budget reached")
        if group_exists(process.pid):
            raise AcceptanceFailure("tool_crashed", f"{stage}: process group leak")
        return process.returncode
    finally:
        stop_group(process)
        if observation is not None:
            observation["exit_code"] = process.returncode
            observation["memory_sampling"] = {
                "interval_seconds": 0.1,
                "samples": samples,
                "peak_observed_rss_bytes": peak,
            }
```

完整新增 `acceptance/toolchain.py`：

```python
from __future__ import annotations

from typing import Any

import os
import re
import sys
import tempfile
from pathlib import Path

from acceptance.canonical import digest
from acceptance.contract import Contract, thaw
from acceptance.input_bundle import measure_file, read_bounded
from acceptance.primitives import AcceptanceFailure, clean_environment, run_command


def trusted_code_files(repo_root: Path) -> tuple[Path, ...]:
    paths = list((repo_root / "acceptance").rglob("*.py"))
    paths += list((repo_root / "acceptance").rglob("*.json"))
    paths += [repo_root / "scripts/asset_accept.py", repo_root / "smoke/process_registry.py"]
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise AcceptanceFailure("toolchain_mismatch", "missing or linked trusted code member")
    return tuple(sorted(paths))


def provenance(repo_root: Path) -> dict[str, Any]:
    rows = []
    for path in trusted_code_files(repo_root):
        measured = measure_file(path, 32 * 1024 * 1024, file_id="code")
        rows.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "bytes": measured.bytes,
                "sha256": measured.sha256,
            }
        )
    return {"id": "acceptance", "version": "acc-v2-" + digest("code.v2", rows), "files": rows}


def measure_tool(tool: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    # Installed executable symlinks are resolved once; the resolved binary and declared scripts are measured.
    path = Path(tool["path"]).resolve(strict=True)
    measured = measure_file(path, 2 * 1024**3, file_id=tool["id"])
    if measured.sha256 != tool["sha256"]:
        raise AcceptanceFailure("toolchain_mismatch", "executable hash mismatch")
    for member in tool["files"]:
        item = measure_file(Path(member["path"]), 2 * 1024**3, file_id="dependency")
        if item.bytes != member["bytes"] or item.sha256 != member["sha256"]:
            raise AcceptanceFailure("toolchain_mismatch", "tool dependency hash mismatch")
    if tool["id"] == "acceptance":
        code = provenance(repo_root)
        required = {str(p.absolute()) for p in trusted_code_files(repo_root)}
        declared = {m["path"] for m in tool["files"]}
        if required != declared:
            raise AcceptanceFailure("toolchain_mismatch", "acceptance code closure mismatch")
        version = code["version"]
    else:
        if not os.access(path, os.X_OK):
            raise AcceptanceFailure("toolchain_mismatch", "tool is not executable")
        with tempfile.TemporaryDirectory(prefix="acceptance-version-") as temporary:
            folder = Path(temporary).resolve()
            log = folder / "version.txt"
            rc = run_command(
                "tool-version",
                [str(path), "--version"],
                cwd=folder,
                env=clean_environment(Path(sys.executable)),
                log_path=log,
                timeout=10.0,
                max_log_bytes=8192,
            )
            if rc != 0:
                raise AcceptanceFailure("toolchain_mismatch", "version command failed")
            lines = read_bounded(log, 8192).decode("utf-8", errors="strict").splitlines()
            if not lines:
                raise AcceptanceFailure("toolchain_mismatch", "version output empty")
            version = lines[0].strip()
        patterns = {
            "python": r"Python 3\.13\.13",
            "blender": r"Blender 5\.2\.[0-9]+(?: LTS)?",
            "node": r"v20\.20\.2",
        }
        if re.fullmatch(patterns[tool["id"]], version) is None:
            raise AcceptanceFailure("toolchain_mismatch", "tool kind or supported version mismatch")
    if version != tool["version"]:
        raise AcceptanceFailure("toolchain_mismatch", "observed version differs from lock")
    return {
        "id": tool["id"],
        "path": str(path),
        "bytes": measured.bytes,
        "sha256": measured.sha256,
        "version": version,
        "files": thaw(tool["files"]),
    }


def verify_tools(
    contract: Contract, required_ids: tuple[str, ...], repo_root: Path
) -> list[dict[str, Any]]:
    tools = {t["id"]: thaw(t) for t in contract.raw["tools"]}
    if not set(required_ids) <= set(tools):
        raise AcceptanceFailure("toolchain_mismatch", "missing required tools")
    try:
        return [measure_tool(tools[key], repo_root) for key in sorted(tools)]
    except (OSError, ValueError, KeyError) as exc:
        raise AcceptanceFailure("toolchain_mismatch", str(exc)) from exc
```

2026-09-08 本机试验确认 RLIMIT_AS 设置 2 GiB 抛 ValueError；因此 v2 使用 rss_bytes。RSS 每 0.1 秒采样进程组并终止超限作业；记录 observed peak 和 samples，允许采样间隔内峰值漏采，不声明硬地址空间隔离。CPU、文件大小、FD 数仍使用可执行的内核限制；L1 缺隔离 runner 时未验证。

Node 的真实版本为 v20.20.2；gltf-validator 不是可执行程序，其 wrapper、package-lock、index.js 和 gltf_validator.dart.js 必须进入 node.files，由 M3 安装与锁定。Blender/Node/Python 版本首行和实际文件摘要都要匹配，不能只检查可执行标志。
- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_toolchain.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。

### Task 6: 唯一判定、内部不变量、N/A 与 required gate

**Files:**
- Modify: `acceptance/decide.py`（完整替换）
- Test: `tests/unit/test_asset_v2_decide.py`

**Interfaces:**
- Consumes: 深冻结 Contract 与固定 registry/failure families。
- Produces: Finding/CheckOutcome/Gate/Verdict、aggregate/decide/decide_technical；所有技术判定集中在此。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_decide.py`：

```python
from dataclasses import replace
import pytest
from acceptance import check_registry as reg
from acceptance.decide import Finding, Gate, aggregate, decide, decide_technical, technical_state
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document, write_contract


def complete_outcomes(contract):
    version = next(t["version"] for t in contract.raw["tools"] if t["id"] == "acceptance")
    return [
        aggregate(
            s.id,
            [],
            contract=contract,
            tool_id=None if s.id in contract.na_check_ids else "acceptance",
            tool_version=None if s.id in contract.na_check_ids else version,
            source_truncated=False,
            terminal=None,
        )
        for s in reg.CHECKS
    ]


def verdict(contract, outcomes):
    return decide(
        contract=contract,
        outcomes=outcomes,
        actual_files={"evidence"},
        expected_files={"evidence"},
        achieved_grade="local-trusted",
        infra_failures=[],
    )


@pytest.mark.parametrize(
    "change", ["unknown_raw", "wrong_stage", "truncated_pass", "accepted_alias"]
)
def test_internal_outcomes_do_not_bypass_parser(tmp_path, change):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    if change == "unknown_raw":
        outcomes[0] = replace(outcomes[0], raw_status="UnknownStatus")
    elif change == "wrong_stage":
        outcomes[0] = replace(outcomes[0], stage="R9")
    elif change == "truncated_pass":
        outcomes[0] = replace(outcomes[0], source_truncated=True)
    else:
        outcomes[0] = replace(outcomes[0], accepted=1)
    with pytest.raises(AcceptanceFailure, match="outcome"):
        verdict(contract, outcomes)


def test_na_cannot_erase_accidents_and_fail_not_tested_is_unverified(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    with pytest.raises(AcceptanceFailure, match="N/A"):
        aggregate(
            contract.na_check_ids[0],
            [],
            contract=contract,
            tool_id=None,
            tool_version=None,
            source_truncated=False,
            terminal="Crash",
        )
    outcomes = complete_outcomes(contract)
    for index, terminal in ((0, None), (1, "NotTested")):
        original = outcomes[index]
        outcomes[index] = aggregate(
            original.id,
            [Finding("bad", "error")] if index == 0 else [],
            contract=contract,
            tool_id=original.tool_id,
            tool_version=original.tool_version,
            source_truncated=False,
            terminal=terminal,
        )
    result = verdict(contract, outcomes)
    assert not result.success and result.failure_code == "check_failed"
    assert technical_state(result) == "UNVERIFIED"
    assert outcomes[0].id in result.failed_check_ids


def test_required_gates_cannot_be_dropped_or_compensated(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    base = verdict(contract, complete_outcomes(contract))
    assert base.success
    assert (
        decide_technical(base, expected_gate_ids=("reference",), gates={}).failure_code
        == "expected_set_mismatch"
    )
    gate = Gate(False, (Finding("unsupported", "error"),))
    assert (
        decide_technical(
            base, expected_gate_ids=("reference",), gates={"reference": gate}
        ).failure_code
        == "runner_internal_error"
    )
    gate = Gate(True, (Finding("missing_part", "error"),))
    result = decide_technical(base, expected_gate_ids=("reference",), gates={"reference": gate})
    assert not result.success and result.failure_code == "check_failed"
    assert result.failed_gate_ids == ("reference",)


def test_complete_failure_and_incomplete_gate_keeps_code_but_is_unverified(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    original = outcomes[0]
    outcomes[0] = aggregate(
        original.id,
        [Finding("bad", "error")],
        contract=contract,
        tool_id=original.tool_id,
        tool_version=original.tool_version,
        source_truncated=False,
        terminal=None,
    )
    result = decide_technical(
        verdict(contract, outcomes),
        expected_gate_ids=("reference",),
        gates={"reference": Gate(False)},
    )
    assert result.failure_code == "check_failed"
    assert technical_state(result) == "UNVERIFIED"
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_decide.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

完整替换 `acceptance/decide.py`：

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from acceptance import check_registry as reg, failure_codes as fc
from acceptance.contract import Contract
from acceptance.primitives import AcceptanceFailure

_SPEC = {s.id: s for s in reg.CHECKS}
_TERMINALS = {None, "Crash", "Missing", "NotTested"}


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    pointer: str | None = None
    offset: int | None = None
    detail: str | None = None
    disposition: str | None = None


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    id: str
    stage: str
    raw_status: str
    effective_status: str
    accepted: bool
    tool_id: str | None
    tool_version: str | None
    findings: tuple[Finding, ...]
    source_truncated: bool


@dataclass(frozen=True, slots=True)
class Gate:
    complete: bool
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class Verdict:
    success: bool
    failure_code: str | None
    failed_check_ids: tuple[str, ...] = ()
    outcomes: tuple[CheckOutcome, ...] = ()
    failed_gate_ids: tuple[str, ...] = ()
    gates: tuple[tuple[str, Gate], ...] = ()


def validate_finding(finding: Finding) -> None:
    if (
        type(finding) is not Finding
        or type(finding.code) is not str
        or not finding.code
        or finding.severity not in ("error", "warning", "info")
        or any(
            getattr(finding, key) is not None and type(getattr(finding, key)) is not str
            for key in ("pointer", "detail", "disposition")
        )
        or (finding.offset is not None and (type(finding.offset) is not int or finding.offset < 0))
    ):
        raise AcceptanceFailure("tool_output_invalid", "invalid finding")


def aggregate(
    check_id: str,
    findings: list[Finding],
    *,
    contract: Contract,
    tool_id: str | None,
    tool_version: str | None,
    source_truncated: bool,
    terminal: str | None,
) -> CheckOutcome:
    if check_id not in _SPEC or terminal not in _TERMINALS or type(source_truncated) is not bool:
        raise AcceptanceFailure("tool_output_invalid", "invalid aggregate identity/state")
    spec = _SPEC[check_id]
    if check_id in contract.na_check_ids:
        if (
            findings
            or terminal is not None
            or source_truncated
            or tool_id is not None
            or tool_version is not None
        ):
            raise AcceptanceFailure(
                "forged_not_applicable", "N/A cannot contain a job or its accident"
            )
        return CheckOutcome(
            check_id,
            spec.stage,
            "NotApplicableByContract",
            "NotApplicable",
            False,
            None,
            None,
            (),
            False,
        )
    tools = {t["id"]: t["version"] for t in contract.raw["tools"]}
    if tool_id not in tools or tool_version != tools[tool_id]:
        raise AcceptanceFailure("toolchain_mismatch", "outcome tool identity differs from contract")
    normalized = []
    for finding in findings:
        validate_finding(finding)
        accepted = finding.severity == "warning" and contract.allowlisted(
            check_id, finding.code, tool_id, tool_version
        )
        disposition = "AcceptedWarning" if accepted else None
        if finding.disposition not in (None, disposition):
            raise AcceptanceFailure(
                "forged_disposition", "finding disposition is not policy-derived"
            )
        normalized.append(replace(finding, disposition=disposition))
    if terminal is not None:
        raw = terminal
    elif source_truncated:
        raw = "Truncated"
    elif any(f.severity == "error" for f in normalized):
        raw = "Fail"
    elif any(f.severity == "warning" and f.disposition is None for f in normalized):
        raw = "Warning"
    else:
        raw = "Pass"
    return CheckOutcome(
        check_id,
        spec.stage,
        raw,
        "Pass" if raw == "Pass" else "Fail",
        raw == "Pass" and any(f.severity == "warning" for f in normalized),
        tool_id,
        tool_version,
        tuple(normalized),
        source_truncated,
    )


def decide(
    *,
    contract: Contract,
    outcomes: list[CheckOutcome],
    actual_files: set[str],
    expected_files: set[str],
    achieved_grade: str,
    infra_failures: list[str],
    child_declared_na: set[str] | None = None,
) -> Verdict:
    triggered = list(infra_failures)
    if any(code not in fc.INFRA_FAMILIES for code in triggered):
        raise AcceptanceFailure("runner_internal_error", "unknown infrastructure failure family")
    if achieved_grade != "local-trusted" or contract.required_isolation_grade != "local-trusted":
        triggered.append("isolation_insufficient")
    ids = [o.id for o in outcomes]
    if not ids:
        triggered.append("zero_checks_collected")
    if len(set(ids)) != len(ids) or set(ids) != set(_SPEC) or actual_files != expected_files:
        triggered.append("expected_set_mismatch")
    if child_declared_na:
        triggered.append("forged_not_applicable")
    incomplete = False
    for outcome in outcomes:
        if (
            type(outcome) is not CheckOutcome
            or type(outcome.id) is not str
            or outcome.id not in _SPEC
            or type(outcome.accepted) is not bool
            or type(outcome.findings) is not tuple
        ):
            raise AcceptanceFailure("tool_output_invalid", "unknown internal outcome")
        rebuilt = aggregate(
            outcome.id,
            list(outcome.findings),
            contract=contract,
            tool_id=outcome.tool_id,
            tool_version=outcome.tool_version,
            source_truncated=outcome.source_truncated,
            terminal=outcome.raw_status if outcome.raw_status in _TERMINALS else None,
        )
        if outcome != rebuilt:
            raise AcceptanceFailure("tool_output_invalid", "inconsistent internal outcome")
        incomplete = incomplete or outcome.raw_status == "NotTested"
        failure = {
            "Crash": "tool_crashed",
            "Missing": "evidence_missing",
            "Truncated": "evidence_truncated",
        }.get(outcome.raw_status)
        if failure:
            triggered.append(failure)
    failed = tuple(
        sorted(
            (o.id for o in outcomes if o.raw_status in ("Fail", "Warning")),
            key=lambda key: reg.sort_key(_SPEC[key]),
        )
    )
    code = (
        min(triggered, key=fc.family_priority)
        if triggered
        else ("check_failed" if failed else "runner_internal_error" if incomplete else None)
    )
    return Verdict(code is None, code, failed, tuple(outcomes))


def decide_technical(
    base: Verdict, *, expected_gate_ids: tuple[str, ...], gates: Mapping[str, Gate]
) -> Verdict:
    triggered = [] if base.failure_code in (None, "check_failed") else [base.failure_code]
    if set(gates) != set(expected_gate_ids) or len(set(expected_gate_ids)) != len(
        expected_gate_ids
    ):
        triggered.append("expected_set_mismatch")
    failed = []
    incomplete = False
    for gate_id, gate in gates.items():
        if (
            type(gate) is not Gate
            or type(gate.complete) is not bool
            or type(gate.findings) is not tuple
        ):
            raise AcceptanceFailure("tool_output_invalid", "invalid internal gate")
        for finding in gate.findings:
            validate_finding(finding)
            # Additional gate policies cannot borrow a check warning allowance.
            if finding.disposition is not None:
                raise AcceptanceFailure(
                    "forged_disposition", "gate finding has no implicit warning allowance"
                )
        incomplete = incomplete or not gate.complete
        if gate.complete and any(f.severity in ("error", "warning") for f in gate.findings):
            failed.append(gate_id)
    code: str | None
    if triggered:
        code = min(triggered, key=fc.family_priority)
    else:
        code = (
            "check_failed"
            if base.failure_code == "check_failed" or failed
            else "runner_internal_error"
            if incomplete
            else None
        )
    return Verdict(
        code is None,
        code,
        base.failed_check_ids,
        base.outcomes,
        tuple(sorted(failed)),
        tuple(sorted(gates.items())),
    )


def technical_state(verdict: Verdict) -> str:
    if verdict.success:
        return "NEEDS_REVIEW"
    complete = all(
        o.raw_status in ("Pass", "Fail", "Warning", "NotApplicableByContract")
        for o in verdict.outcomes
    ) and all(gate.complete for _, gate in verdict.gates)
    return "REJECTED" if complete and verdict.failure_code == "check_failed" else "UNVERIFIED"
```

明确 v2 行为变化：Fail + NotTested 保留技术 check_failed 与 failed_check_ids，上层按不完整性为 UNVERIFIED；完整检查硬失败才 REJECTED。必需技术 gate 纳入 summary.success，缺 gate 或未完成不能保持技术 true；人工签收不进入此算法。
- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_decide.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。

### Task 7: 实际运行、可信文件接收和 E/V/Q/T

**Files:**
- Modify: `acceptance/stages.py`（完整替换，移除旧空 run_r5 接口）
- Create: `acceptance/controller.py`
- Modify: `acceptance/evidence.py`（完整替换）
- Test: `tests/unit/test_asset_v2_pipeline.py`

**Interfaces:**
- Consumes: Tasks 2–6 全部固定接口。
- Produces: run_jobs/RunResult/collect_verdict、finalize_run/finish_review/deliver；真实 R5 在 finalize_run 对文件系统执行，旧接受空 manifest 的纯比较接口退出；安全阻断的未产生文件被逐项列入 E，不追加虚构事故；所需文件不全时 r5.evidence.manifest_closed 保持 NotTested，不能伪造完整 R5 Pass。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_pipeline.py`：

```python
from collections import defaultdict
import datetime
import json
import sys
import pytest
from acceptance import check_registry as reg
from acceptance.controller import run_jobs
from acceptance.decide import Finding, Gate
from acceptance.evidence import finalize_run, finish_review, deliver
from acceptance.input_bundle import measure_file
from acceptance.plan import JobSpec, assemble_plan
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import REPO, file_lock, valid_document, write_contract


def mock_run(tmp_path, *, require_review=False, invalid_geometry=False):
    document = valid_document(tmp_path)
    worker = tmp_path / "fixture_worker.py"
    worker.write_text(
        "import argparse,sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(REPO)!r})\n"
        "from acceptance.worker_protocol import read_request,write_result\n"
        "p=argparse.ArgumentParser();p.add_argument('--request');a=p.parse_args()\n"
        "r=read_request(Path(a.request))\nrows=[]\n"
        "for check_id in r['parameters']['checks']:\n"
        "    findings=[]\n"
        "    if r['parameters']['invalid_geometry'] and check_id=='r2.geometry.validate_clean':\n"
        "        findings=[dict(code='invalid_geometry',severity='error',pointer='/mesh/0',detail='fixture')]\n"
        "    rows.append(dict(id=check_id,findings=findings,metrics={}))\n"
        "write_result(r,rows,{'fixture':'not-a-real-Blender-worker'})\n"
    )
    document["tools"][0]["files"].append(file_lock(worker))
    if require_review:
        document["review"] = {
            "required": True,
            "reviewer_ids": ["fixture-reviewer"],
            "required_image_ids": [],
            "reason": "test harness authorization only",
        }
    contract = write_contract(tmp_path, document)
    by_writer = defaultdict(list)
    for spec in reg.checks_for_kind("blend_native"):
        if spec.writer != "coordinator":
            by_writer[spec.writer].append(spec.id)
    jobs = []
    for index, (writer, checks) in enumerate(by_writer.items()):
        blocking = () if writer == "inspector" else ("r2.geometry.validate_clean",)
        jobs.append(
            JobSpec(
                f"job-{index}",
                writer,
                "python",
                tuple(checks),
                ("asset",),
                (),
                {"checks": checks, "invalid_geometry": invalid_geometry},
                blocking,
            )
        )
    plan = assemble_plan(contract, tuple(jobs), gate_ids=("reference",))
    source = measure_file(tmp_path / "source/asset.blend", 1024, file_id="asset")
    evidence = tmp_path / "evidence"
    evidence.mkdir(mode=0o700)
    run = run_jobs(
        contract,
        plan,
        run_id="mock-run",
        input_files={"asset": source},
        scratch_root=tmp_path / "scratch",
        evidence_root=evidence,
        commands={writer: (sys.executable, str(worker)) for writer in by_writer},
    )
    return contract, plan, source, evidence, run


def seal_fixture(tmp_path, setup, *, gates=None):
    contract, plan, source, evidence, run = setup
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=tmp_path / "contract.json",
        source_root=tmp_path / "source",
        evidence_root=evidence,
        delivery=source,
        coordinator_findings={"r4.visual.all_views_rendered": []},
        gates={"reference": Gate(True)} if gates is None else gates,
    )


def test_mock_full_chain_is_closed_and_delivery_is_exact(tmp_path):
    setup = mock_run(tmp_path)
    result = seal_fixture(tmp_path, setup)
    assert result["state"] == "SHIP"
    contract, plan, source, evidence, run = setup
    manifest = json.loads((evidence / "evidence-manifest.json").read_text())
    assert {row["id"] for row in manifest["files"]} == {f.id for f in plan.files}
    assert not {"summary.json", "evidence-manifest.json", "review.json", "completion.json"} & {
        r["path"] for r in manifest["files"]
    }
    assert all(
        record["pid"] and record["started_at"] and record["exit_code"] == 0 for record in run.jobs
    )
    receipt = deliver(evidence, delivery_path=source.path, destination=tmp_path / "delivered.blend")
    assert receipt["D"] == source.sha256
    assert (tmp_path / "delivered.blend").read_bytes() == source.path.read_bytes()


def test_missing_gate_cannot_make_technical_success(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup, gates={})["state"] == "UNVERIFIED"
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert summary["success"] is False


def test_review_does_not_rewrite_v_and_wrong_binding_cannot_seal(tmp_path):
    setup = mock_run(tmp_path, require_review=True)
    pending = seal_fixture(tmp_path, setup)
    assert pending["state"] == "NEEDS_REVIEW"
    evidence = setup[3]
    before = (evidence / "summary.json").read_bytes()
    assert not (evidence / "completion.json").exists()
    review = {
        "schema_version": 2,
        "bindings": pending["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_images": [],
                "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "note": "unit test only",
            }
        ],
    }
    bad = dict(review, bindings=review["bindings"] | {"V": "0" * 64})
    with pytest.raises(AcceptanceFailure):
        finish_review(evidence, delivery_path=setup[2].path, review=bad)
    complete = finish_review(evidence, delivery_path=setup[2].path, review=review)
    assert complete["state"] == "SHIP" and (evidence / "summary.json").read_bytes() == before


def test_safe_blocking_preserves_asset_failure_and_no_render_launch(tmp_path):
    setup = mock_run(tmp_path, invalid_geometry=True)
    result = seal_fixture(tmp_path, setup)
    assert result["state"] == "UNVERIFIED"
    assert setup[4].jobs[0]["started"] is True
    assert all(not record["started"] and record["blocked_by"] for record in setup[4].jobs[1:])
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert "r2.geometry.validate_clean" in summary["failed_check_ids"]
    assert summary["failure_code"] == "check_failed"
    closure = next(row for row in summary["checks"] if row["id"] == "r5.evidence.manifest_closed")
    assert closure["raw_status"] == "NotTested"


def test_received_payload_mutation_prevents_success(tmp_path):
    setup = mock_run(tmp_path)
    file = setup[3] / "payload/job-0/result.json"
    file.chmod(0o600)
    file.write_text("{}")
    result = seal_fixture(tmp_path, setup)
    assert result["state"] == "UNVERIFIED"


def test_no_delivery_cannot_ship_or_be_reviewed(tmp_path):
    contract, plan, source, evidence, run = mock_run(tmp_path)
    result = finalize_run(
        contract,
        plan,
        run,
        contract_path=tmp_path / "contract.json",
        source_root=tmp_path / "source",
        evidence_root=evidence,
        delivery=None,
        coordinator_findings={"r4.visual.all_views_rendered": []},
        gates={"reference": Gate(True)},
    )
    summary = json.loads((evidence / "summary.json").read_text())
    assert result["state"] == "UNVERIFIED" and result["bindings"]["D"] is None
    assert not summary["success"] and summary["D"] is None
    assert "evidence_missing" in summary["infra_failures"]
    with pytest.raises(AcceptanceFailure):
        deliver(evidence, delivery_path=source.path, destination=tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


def test_incomplete_gate_with_complete_asset_failure_is_unverified(tmp_path):
    setup = mock_run(tmp_path)
    setup[4].findings["r2.geometry.validate_clean"].append(Finding("bad_geometry", "error"))
    result = seal_fixture(tmp_path, setup, gates={"reference": Gate(False)})
    summary = json.loads((setup[3] / "summary.json").read_text())
    assert result["state"] == "UNVERIFIED"
    assert summary["failure_code"] == "check_failed"
    assert "r2.geometry.validate_clean" in summary["failed_check_ids"]


def test_changed_payload_after_completion_blocks_delivery(tmp_path):
    setup = mock_run(tmp_path)
    assert seal_fixture(tmp_path, setup)["state"] == "SHIP"
    source, evidence = setup[2:4]
    payload = evidence / "payload/job-0/result.json"
    payload.chmod(0o600)
    payload.write_text("{}")
    with pytest.raises(AcceptanceFailure):
        deliver(evidence, delivery_path=source.path, destination=tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_pipeline.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

完整替换 `acceptance/stages.py`：

```python
from __future__ import annotations

from typing import Any

from collections.abc import Mapping
from pathlib import Path

from acceptance.contract import Contract
from acceptance.decide import Finding
from acceptance.input_bundle import BoundFile


def run_r0(contract: Contract, *, tools_measured: list[dict[str, Any]]) -> dict[str, list[Finding]]:
    declared = {t["id"]: t for t in contract.raw["tools"]}
    measured = {t["id"]: t for t in tools_measured}
    valid = len(measured) == len(tools_measured) and set(measured) == set(declared)
    if valid:
        valid = all(
            measured[key]["sha256"] == value["sha256"]
            and measured[key]["version"] == value["version"]
            and Path(measured[key]["path"]).resolve() == Path(value["path"]).resolve()
            for key, value in declared.items()
        )
    return {
        "r0.contract.schema_closed": [],
        "r0.contract.na_set_declared": [],
        "r0.contract.tools_locked": [] if valid else [Finding("tool_identity_mismatch", "error")],
    }


def run_r1(contract: Contract, input_files: Mapping[str, BoundFile]) -> dict[str, list[Finding]]:
    expected = {r["id"]: r for r in contract.raw["input"]["files"]}
    identity_ok = set(input_files) == set(expected) and all(
        actual.bytes == expected[key]["bytes"] and actual.sha256 == expected[key]["sha256"]
        for key, actual in input_files.items()
        if key in expected
    )
    within = (
        len(input_files) <= contract.raw["budget"]["max_files"]
        and sum(item.bytes for item in input_files.values())
        <= contract.raw["budget"]["max_total_bytes"]
        and all(
            item.bytes <= contract.raw["budget"]["max_file_bytes"] for item in input_files.values()
        )
    )
    return {
        "r1.input.digest_recorded": []
        if identity_ok
        else [Finding("input_identity_mismatch", "error")],
        "r1.input.no_link_or_device": [],
        "r1.input.size_within_limit": [] if within else [Finding("input_budget_exceeded", "error")],
    }
```

完整新增 `acceptance/controller.py`：

```python
from __future__ import annotations

from typing import Any

import os
import secrets
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from acceptance import check_registry as reg, failure_codes as fc
from acceptance.contract import Contract, thaw, enforce_baseline
from acceptance.decide import Finding, Verdict, aggregate, decide
from acceptance.input_bundle import BoundFile, measure_file, read_bounded, validate_roots
from acceptance.plan import RunPlan
from acceptance.primitives import (
    AcceptanceFailure,
    clean_environment,
    run_command,
    write_json_exclusive,
)
from acceptance.strict_json import strict_json_loads
from acceptance.stages import run_r0, run_r1
from acceptance.toolchain import verify_tools
from acceptance.worker_protocol import IDENTITY, validate_result

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunResult:
    findings: dict[str, list[Finding]] = field(default_factory=dict)
    infra_failures: tuple[str, ...] = ()
    files: dict[str, BoundFile] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    jobs: tuple[dict[str, Any], ...] = ()
    measurements: dict[str, Any] = field(default_factory=dict)


def _family(exc: Exception) -> str:
    code = getattr(exc, "code", "")
    if code in fc.INFRA_FAMILIES:
        return code
    if isinstance(exc, FileNotFoundError):
        return "evidence_missing"
    return "tool_output_invalid"


def _copy(source: Path, target: Path, *, file_id: str, max_bytes: int) -> BoundFile:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return measure_file(source, max_bytes, file_id=file_id, copy_to=target)


def _files_under(root: Path) -> set[str]:
    def scan_error(exc: OSError) -> None:
        raise AcceptanceFailure(_family(exc), f"cannot enumerate output directory: {exc}") from exc

    names = set()
    for current, directories, files in os.walk(root, followlinks=False, onerror=scan_error):
        if any((Path(current) / d).is_symlink() for d in directories):
            raise AcceptanceFailure("tool_output_invalid", "symlink output directory")
        for name in files:
            names.add((Path(current) / name).relative_to(root).as_posix())
    return names


def run_jobs(
    contract: Contract,
    plan: RunPlan,
    *,
    run_id: str,
    input_files: Mapping[str, BoundFile],
    scratch_root: Path,
    evidence_root: Path,
    commands: Mapping[str, tuple[str, ...]],
) -> RunResult:
    roots = set()
    for row in contract.raw["input"]["files"]:
        if row["id"] in input_files:
            root = input_files[row["id"]].path.absolute()
            for _ in row["path"].split("/"):
                root = root.parent
            roots.add(root)
    if len(roots) != 1:
        raise AcceptanceFailure("contract_invalid", "input bindings do not share a source root")
    validate_roots(next(iter(roots)), evidence_root, scratch_root, REPO_ROOT)
    scratch_root.mkdir(mode=0o700)
    payload = evidence_root / "payload"
    payload.mkdir(mode=0o700)
    run = RunResult()
    failures = []
    records = []
    available = dict(input_files)
    expected_files = {s.id: s for s in plan.files}
    tools = {t["id"]: t for t in contract.raw["tools"]}
    try:
        run.measurements["tools"] = verify_tools(contract, plan.required_tools, REPO_ROOT)
        run.findings.update(run_r0(contract, tools_measured=run.measurements["tools"]))
        rows = contract.raw["input"]["files"]
        if set(available) != {r["id"] for r in rows}:
            raise AcceptanceFailure("expected_set_mismatch", "input binding set mismatch")
        for row in rows:
            source = available[row["id"]]
            measured = measure_file(
                source.path, contract.raw["budget"]["max_file_bytes"], file_id=source.id
            )
            if (measured.bytes, measured.sha256) != (row["bytes"], row["sha256"]):
                raise AcceptanceFailure("hash_mismatch", "input identity mismatch")
        run.findings.update(run_r1(contract, available))
        enforce_baseline(contract, available)
    except Exception as exc:
        failures.append(_family(exc))
        run.measurements["preflight_error"] = str(exc)
    for job in plan.jobs:
        record: dict[str, Any] = {
            "job_id": job.job_id,
            "writer": job.writer,
            "started": False,
            "pid": None,
            "started_at": None,
            "exit_code": None,
            "failure_code": None,
            "error": None,
            "blocked_by": [],
        }
        folder = scratch_root / job.job_id
        folder.mkdir(mode=0o700)
        inputs, outputs = folder / "input", folder / "output"
        inputs.mkdir(mode=0o700)
        outputs.mkdir(mode=0o700)
        request_path, log_path = folder / "request.json", folder / "process.log"
        try:
            blocked = [
                key
                for key in job.blocking_check_ids
                if key not in run.findings
                or any(f.severity in ("error", "warning") for f in run.findings[key])
            ]
            record["blocked_by"] = blocked
            if blocked and not failures:
                record["error"] = "not started: safety prerequisite was not satisfied"
                continue
            if failures or not set(job.input_ids) <= set(available):
                raise AcceptanceFailure(
                    "runner_internal_error", "job not started after failed prerequisite"
                )
            input_rows = []
            for file_id in job.input_ids:
                source = available[file_id]
                relative = file_id + source.path.suffix
                copied = _copy(
                    source.path, inputs / relative, file_id=file_id, max_bytes=source.bytes
                )
                if copied.sha256 != source.sha256 or copied.bytes != source.bytes:
                    raise AcceptanceFailure("hash_mismatch", "upstream input changed")
                input_rows.append(copied.descriptor(relative))
            request = {
                "schema_version": 2,
                "run_id": run_id,
                "attempt": 1,
                "nonce": secrets.token_hex(16),
                "job_id": job.job_id,
                "writer": job.writer,
                "contract_digest": contract.digest,
                "source_digest": contract.raw["input"]["sha256"],
                "input_root": str(inputs),
                "inputs": input_rows,
                "output_root": str(outputs),
                "outputs": [
                    {
                        "id": s.id,
                        "path": s.path,
                        "media_type": s.media_type,
                        "max_bytes": s.max_bytes,
                    }
                    for s in job.outputs
                ],
                "parameters": thaw(job.parameters),
            }
            write_json_exclusive(request_path, request)
            prefix = commands[job.writer]
            locked = tools[job.tool_id]
            if not prefix or Path(prefix[0]).resolve() != Path(locked["path"]).resolve():
                raise AcceptanceFailure("toolchain_mismatch", "command executable not locked")
            dependencies = {m["path"] for t in tools.values() for m in t["files"]}
            scripts = [p for p in prefix[1:] if p.endswith((".py", ".js", ".cjs", ".mjs"))]
            if any(not Path(p).is_absolute() or p not in dependencies for p in scripts):
                raise AcceptanceFailure(
                    "toolchain_mismatch", "command script outside locked closure"
                )
            env = clean_environment(Path(sys.executable))
            for key in ("BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS", "BLENDER_USER_DATAFILES"):
                directory = folder / key.lower()
                directory.mkdir(mode=0o700)
                env[key] = str(directory)
            rc = run_command(
                job.job_id,
                list(prefix) + ["--request", str(request_path)],
                cwd=folder,
                env=env,
                log_path=log_path,
                timeout=contract.raw["limits"]["timeout_seconds"][job.writer],
                max_log_bytes=contract.raw["limits"]["log_bytes"],
                limits=thaw(contract.raw["limits"]),
                observation=record,
            )
            record["exit_code"] = rc
            if rc != 0:
                raise AcceptanceFailure("tool_crashed", f"worker exited {rc}")
            expected = {s.path for s in job.outputs} | {"result.json"}
            if _files_under(outputs) != expected:
                raise AcceptanceFailure("expected_set_mismatch", "worker output file set mismatch")
            result: Any = strict_json_loads(
                read_bounded(
                    outputs / "result.json", contract.raw["budget"]["max_result_bytes"]
                ).decode("utf-8")
            )
            if any(result.get(k) != request[k] for k in IDENTITY):
                raise AcceptanceFailure("stale_result_file", "result belongs to another attempt")
            validate_result(result, request, job.check_ids)
            reports = {r["id"]: r for r in result["artifacts"]}
            received = {}
            for spec in job.outputs:
                target = expected_files[spec.id]
                copied = _copy(
                    outputs / spec.path,
                    payload / target.path,
                    file_id=spec.id,
                    max_bytes=spec.max_bytes,
                )
                claimed = reports[spec.id]
                if (copied.bytes, copied.sha256) != (claimed["bytes"], claimed["sha256"]):
                    raise AcceptanceFailure(
                        "hash_mismatch", "child artifact hash was not measured honestly"
                    )
                received[spec.id] = copied
            result_spec = expected_files[f"{job.job_id}.result"]
            received[result_spec.id] = _copy(
                outputs / "result.json",
                payload / result_spec.path,
                file_id=result_spec.id,
                max_bytes=result_spec.max_bytes,
            )
            run.files.update(received)
            available.update(received)
            for row in result["checks"]:
                run.findings[row["id"]] = [Finding(**finding) for finding in row["findings"]]
            run.results[job.job_id] = result
        except Exception as exc:
            record["failure_code"], record["error"] = _family(exc), str(exc)
            failures.append(record["failure_code"])
        finally:
            records.append(record)
            job_path = folder / "job.json"
            write_json_exclusive(job_path, record)
            for suffix, control_source in (
                ("job", job_path),
                ("request", request_path),
                ("log", log_path),
            ):
                if control_source.exists():
                    spec = expected_files[f"{job.job_id}.{suffix}"]
                    try:
                        run.files[spec.id] = _copy(
                            control_source,
                            payload / spec.path,
                            file_id=spec.id,
                            max_bytes=spec.max_bytes,
                        )
                    except Exception as exc:
                        failures.append(_family(exc))
    run.infra_failures = tuple(failures)
    run.jobs = tuple(records)
    document = {
        "schema_version": 2,
        "run_id": run_id,
        "C": contract.digest,
        "S": contract.raw["input"]["sha256"],
        "jobs": records,
        "measurements": run.measurements,
    }
    run_path = payload / "run.json"
    write_json_exclusive(run_path, document)
    run.files["run"] = measure_file(run_path, expected_files["run"].max_bytes, file_id="run")
    return run


def unproduced_files(plan: RunPlan, run: RunResult) -> dict[str, dict[str, Any]]:
    # Only controller-owned, deliberate safety blocks permit absent job products.
    blocked = {
        r["job_id"]: r
        for r in run.jobs
        if not r["started"] and r["blocked_by"] and r["failure_code"] is None
    }
    rows = {}
    for job in plan.jobs:
        if job.job_id not in blocked:
            continue
        ids = {s.id for s in job.outputs} | {
            f"{job.job_id}.{suffix}" for suffix in ("request", "log", "result")
        }
        for spec in plan.files:
            if spec.id in ids:
                rows[spec.id] = {
                    "id": spec.id,
                    "path": spec.path,
                    "job_id": job.job_id,
                    "blocked_by": blocked[job.job_id]["blocked_by"],
                }
    return rows


def collect_verdict(
    contract: Contract,
    plan: RunPlan,
    run: RunResult,
    *,
    coordinator_findings: Mapping[str, list[Finding]],
) -> Verdict:
    specs = {s.id: s for s in reg.CHECKS}
    collected = {key: list(value) for key, value in run.findings.items()}
    for check_id, findings in coordinator_findings.items():
        if check_id not in plan.check_ids:
            raise AcceptanceFailure("tool_output_invalid", "unknown or N/A coordinator check")
        if specs[check_id].writer != "coordinator" and check_id not in collected:
            raise AcceptanceFailure("tool_output_invalid", "cannot fabricate missing worker check")
        collected.setdefault(check_id, []).extend(findings)
    versions = {t["id"]: t["version"] for t in contract.raw["tools"]}
    owner = {check_id: job for job in plan.jobs for check_id in job.check_ids}
    outcomes = []
    for spec in reg.CHECKS:
        na = spec.id in plan.na_check_ids
        job = owner.get(spec.id)
        tool_id = None if na else (job.tool_id if job else "acceptance")
        outcomes.append(
            aggregate(
                spec.id,
                collected.get(spec.id, []),
                contract=contract,
                tool_id=tool_id,
                tool_version=None if na else versions[tool_id],
                source_truncated=False,
                terminal=None if na or spec.id in collected else "NotTested",
            )
        )
    return decide(
        contract=contract,
        outcomes=outcomes,
        actual_files=set(run.files),
        expected_files={s.id for s in plan.files} - set(unproduced_files(plan, run)),
        achieved_grade="local-trusted",
        infra_failures=list(run.infra_failures),
    )
```

完整替换 `acceptance/evidence.py`：

```python
from __future__ import annotations

from typing import Any, cast

import datetime
import os
import secrets
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from acceptance.contract import Contract, load_contract, thaw
from acceptance.controller import (
    RunResult,
    collect_verdict,
    unproduced_files,
    _files_under,
    _family,
    REPO_ROOT,
)
from acceptance.decide import Finding, Gate, decide_technical
from acceptance.input_bundle import BoundFile, measure_file, read_bounded, verify_bundle
from acceptance.plan import RunPlan
from acceptance.primitives import AcceptanceFailure, write_json_exclusive
from acceptance.strict_json import strict_json_loads
from acceptance.toolchain import verify_tools


def _write(path: Path, value: object) -> BoundFile:
    temporary = path.parent / (".control-" + secrets.token_hex(16))
    write_json_exclusive(temporary, value)
    fd = os.open(temporary, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    # link is atomic and refuses an existing final name; unlike replace it never overwrites evidence.
    os.link(temporary, path, follow_symlinks=False)
    temporary.unlink()
    parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return measure_file(path, 64 * 1024 * 1024, file_id="control")


def _json(path: Path) -> Any:
    return strict_json_loads(read_bounded(path, 64 * 1024 * 1024).decode("utf-8"))


def _identity(path: Path) -> str:
    return measure_file(path, 64 * 1024 * 1024, file_id="control").sha256


def finalize_run(
    contract: Contract,
    plan: RunPlan,
    run: RunResult,
    *,
    contract_path: Path,
    source_root: Path,
    evidence_root: Path,
    delivery: BoundFile | None,
    coordinator_findings: Mapping[str, list[Finding]],
    gates: Mapping[str, Gate],
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = evidence_root / "payload"
    gate_rows = {key: asdict(value) for key, value in gates.items()}
    gate_path = payload / "gates.json"
    _write(
        gate_path,
        {"schema_version": 2, "expected_gate_ids": list(plan.gate_ids), "gates": gate_rows},
    )
    planned = {f.id: f for f in plan.files}
    run.files["gates"] = measure_file(gate_path, planned["gates"].max_bytes, file_id="gates")
    extra = {key: list(value) for key, value in coordinator_findings.items()}
    r5: dict[str, list[Finding]] = {
        "r5.evidence.manifest_closed": [],
        "r5.evidence.hashes_match": [],
        "r5.contract.digest_stable": [],
    }
    failures = list(run.infra_failures)
    try:
        current_contract = load_contract(contract_path, candidate_root=source_root)
        if (
            current_contract.digest != contract.digest
            or current_contract.byte_sha256 != contract.byte_sha256
        ):
            raise AcceptanceFailure(
                "hash_mismatch", "contract file changed after execution snapshot"
            )
        verify_bundle(
            source_root,
            thaw(contract.raw["input"]["files"]),
            max_file_bytes=contract.raw["budget"]["max_file_bytes"],
        )
        current_tools = verify_tools(contract, plan.required_tools, REPO_ROOT)
        if current_tools != run.measurements.get("tools"):
            raise AcceptanceFailure("toolchain_mismatch", "tool identities changed during run")
        if delivery is None or delivery.bytes <= 0:
            raise AcceptanceFailure("evidence_missing", "no nonempty checked delivery was produced")
        measured_delivery = measure_file(
            delivery.path, contract.raw["budget"]["max_file_bytes"], file_id=delivery.id
        )
        if (measured_delivery.bytes, measured_delivery.sha256) != (delivery.bytes, delivery.sha256):
            raise AcceptanceFailure("hash_mismatch", "delivery changed after checks")
    except Exception as exc:
        failures.append(_family(exc))
        r5["r5.contract.digest_stable"].append(Finding("identity_drift", "error", detail=str(exc)))
    rows = []
    actual_paths = _files_under(payload)
    expected_paths = {spec.path for spec in plan.files}
    unproduced = unproduced_files(plan, run)
    blocked_paths = {row["path"] for row in unproduced.values()}
    if actual_paths != expected_paths - blocked_paths or set(run.files) != set(planned) - set(
        unproduced
    ):
        failures.append("expected_set_mismatch")
        r5["r5.evidence.manifest_closed"].append(Finding("file_set_mismatch", "error"))
    total = 0
    for file_id, spec in sorted(planned.items()):
        path = payload / spec.path
        if not path.exists():
            continue
        try:
            measured = measure_file(path, spec.max_bytes, file_id=file_id)
            previous = run.files.get(file_id)
            if previous is None or (measured.bytes, measured.sha256) != (
                previous.bytes,
                previous.sha256,
            ):
                raise AcceptanceFailure("hash_mismatch", "payload changed after acceptance")
            total += measured.bytes
            rows.append(
                measured.descriptor(spec.path)
                | {"writer": spec.writer, "media_type": spec.media_type}
            )
        except Exception as exc:
            failures.append(_family(exc))
            r5["r5.evidence.hashes_match"].append(
                Finding("payload_identity_invalid", "error", detail=str(exc))
            )
    if total > contract.raw["budget"]["max_total_bytes"]:
        failures.append("resource_limit_exceeded")
    run.infra_failures = tuple(failures)
    for key, findings in r5.items():
        if key in extra:
            raise AcceptanceFailure(
                "tool_output_invalid", "R5 is controller-owned and cannot be supplied"
            )
        if key == "r5.evidence.manifest_closed" and unproduced and not findings:
            continue  # Required products did not run: this check remains NotTested, never a fabricated R5 Pass.
        extra[key] = findings
    manifest = {
        "schema_version": 2,
        "C": contract.digest,
        "S": contract.raw["input"]["sha256"],
        "files": rows,
        "missing": sorted(expected_paths - actual_paths),
        "unproduced": [unproduced[key] for key in sorted(unproduced)],
        "unknown": sorted(actual_paths - expected_paths),
    }
    e = _write(evidence_root / "evidence-manifest.json", manifest)
    base = collect_verdict(contract, plan, run, coordinator_findings=extra)
    verdict = decide_technical(base, expected_gate_ids=plan.gate_ids, gates=gates)
    _write(evidence_root / "contract.json", thaw(contract.raw))
    summary = {
        "schema_version": 2,
        "kind": "asset_acceptance",
        "success": verdict.success,
        "C": contract.digest,
        "S": contract.raw["input"]["sha256"],
        "D": None
        if delivery is None
        else {"id": delivery.id, "bytes": delivery.bytes, "sha256": delivery.sha256},
        "E": e.sha256,
        "checks": [asdict(o) for o in verdict.outcomes],
        "gates": gate_rows,
        "expected_gate_ids": list(plan.gate_ids),
        "failure_code": verdict.failure_code,
        "failed_check_ids": list(verdict.failed_check_ids),
        "failed_gate_ids": list(verdict.failed_gate_ids),
        "infra_failures": list(run.infra_failures),
        "review_policy": thaw(contract.raw["review"]),
        "advisories": ["L0 has no deployment policy baseline"]
        if contract.raw["policy_baseline"] is None
        else [],
        "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    v = _write(evidence_root / "summary.json", summary)
    bindings = {
        "C": summary["C"],
        "S": summary["S"],
        "D": None if delivery is None else delivery.sha256,
        "E": e.sha256,
        "V": v.sha256,
    }
    if verdict.success and contract.raw["review"]["required"] and review is None:
        return {"schema_version": 2, "state": "NEEDS_REVIEW", "bindings": bindings}
    return _seal(
        evidence_root, summary, bindings, None if delivery is None else delivery.path, review
    )


def _validate_review(
    review: dict[str, Any],
    bindings: dict[str, Any],
    policy: dict[str, Any],
    manifest: dict[str, Any],
) -> bool:
    if (
        type(review) is not dict
        or set(review) != {"schema_version", "bindings", "records"}
        or type(review["schema_version"]) is not int
        or review["schema_version"] != 2
        or review["bindings"] != bindings
        or type(review["records"]) is not list
    ):
        raise AcceptanceFailure("tool_output_invalid", "review is not bound to this evidence")
    records = review["records"]
    ids = [r.get("reviewer_id") for r in records if type(r) is dict]
    if len(set(ids)) != len(records) or set(ids) != set(policy["reviewer_ids"]):
        raise AcceptanceFailure("tool_output_invalid", "reviewer set is incomplete or unauthorized")
    images = {r["id"]: r["sha256"] for r in manifest["files"] if r["media_type"] == "image/png"}
    for row in records:
        if set(row) != {"reviewer_id", "outcome", "reviewed_images", "reviewed_at", "note"}:
            raise AcceptanceFailure("tool_output_invalid", "closed review record required")
        if row["outcome"] not in ("approved", "rejected") or type(row["note"]) is not str:
            raise AcceptanceFailure("tool_output_invalid", "invalid review outcome")
        parsed = datetime.datetime.fromisoformat(row["reviewed_at"])
        if parsed.tzinfo is None or type(row["reviewed_images"]) is not list:
            raise AcceptanceFailure("tool_output_invalid", "review timestamp/images invalid")
        viewed = {}
        for image in row["reviewed_images"]:
            if type(image) is not dict or set(image) != {"id", "sha256"} or image["id"] in viewed:
                raise AcceptanceFailure("tool_output_invalid", "invalid reviewed image")
            if images.get(image["id"]) != image["sha256"]:
                raise AcceptanceFailure("hash_mismatch", "reviewed image identity mismatch")
            viewed[image["id"]] = image["sha256"]
        if not set(policy["required_image_ids"]) <= set(viewed):
            raise AcceptanceFailure("evidence_missing", "required review images not reviewed")
    return all(row["outcome"] == "approved" for row in records)


def _seal(
    root: Path,
    summary: dict[str, Any],
    bindings: dict[str, Any],
    delivery_path: Path | None,
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest = _json(root / "evidence-manifest.json")
    policy = summary["review_policy"]
    complete = (
        all(
            row["raw_status"] in ("Pass", "Fail", "Warning", "NotApplicableByContract")
            for row in summary["checks"]
        )
        and set(summary["gates"]) == set(summary["expected_gate_ids"])
        and all(gate["complete"] for gate in summary["gates"].values())
    )
    has_delivery = (
        delivery_path is not None
        and type(summary["D"]) is dict
        and type(summary["D"].get("bytes")) is int
        and summary["D"]["bytes"] > 0
        and summary["D"].get("sha256") == bindings["D"]
    )
    if not summary["success"] or not complete or not has_delivery:
        state = (
            "REJECTED"
            if complete and has_delivery and summary["failure_code"] == "check_failed"
            else "UNVERIFIED"
        )
    elif policy["required"]:
        approved = _validate_review(cast(dict[str, Any], review), bindings, policy, manifest)
        state = "SHIP" if approved else "REJECTED"
    else:
        if review is not None:
            _validate_review(review, bindings, policy, manifest)
        state = "SHIP"
    if state == "SHIP":
        actual = measure_file(
            cast(Path, delivery_path), summary["D"]["bytes"], file_id=summary["D"]["id"]
        )
        if actual.bytes != summary["D"]["bytes"] or actual.sha256 != bindings["D"]:
            raise AcceptanceFailure("hash_mismatch", "delivery changed before completion")
        if any(o["accepted"] for o in summary["checks"]):
            state = "SHIP_WITH_NOTES"
    q = _write(
        root / "review.json",
        {
            "schema_version": 2,
            "bindings": bindings,
            "review": review,
            "reason": policy["reason"],
            "state": state,
        },
    )
    completion = {"schema_version": 2, "bindings": bindings | {"Q": q.sha256}, "state": state}
    _write(root / "completion.json", completion)
    # completion.json is the last durable control file; no self-hash is embedded.
    return completion


def _verify_payload(evidence_root: Path, manifest: dict[str, Any]) -> None:
    expected = {r["path"] for r in manifest["files"]}
    if _files_under(evidence_root / "payload") != expected:
        raise AcceptanceFailure("expected_set_mismatch", "review payload set changed")
    for row in manifest["files"]:
        actual = measure_file(
            evidence_root / "payload" / row["path"], row["bytes"], file_id=row["id"]
        )
        if (actual.bytes, actual.sha256) != (row["bytes"], row["sha256"]):
            raise AcceptanceFailure("hash_mismatch", "review payload changed")


def finish_review(
    evidence_root: Path, *, delivery_path: Path, review: dict[str, Any]
) -> dict[str, Any]:
    if (evidence_root / "completion.json").exists():
        raise AcceptanceFailure("reused_evidence_root", "run is already complete")
    summary = _json(evidence_root / "summary.json")
    if not summary["success"] or summary["D"] is None or summary["D"]["bytes"] <= 0:
        raise AcceptanceFailure("tool_output_invalid", "cannot approve an incomplete technical run")
    manifest_path = evidence_root / "evidence-manifest.json"
    if _identity(manifest_path) != summary["E"]:
        raise AcceptanceFailure("hash_mismatch", "evidence manifest changed")
    manifest = _json(manifest_path)
    _verify_payload(evidence_root, manifest)
    contract = load_contract(
        evidence_root / "contract.json", candidate_root=evidence_root / "payload"
    )
    if contract.digest != summary["C"] or thaw(contract.raw["review"]) != summary["review_policy"]:
        raise AcceptanceFailure("hash_mismatch", "review policy changed")
    bindings = {
        "C": summary["C"],
        "S": summary["S"],
        "D": summary["D"]["sha256"],
        "E": summary["E"],
        "V": _identity(evidence_root / "summary.json"),
    }
    return _seal(evidence_root, summary, bindings, delivery_path, review)


def deliver(evidence_root: Path, *, delivery_path: Path, destination: Path) -> dict[str, Any]:
    completion = _json(evidence_root / "completion.json")
    if completion["state"] not in ("SHIP", "SHIP_WITH_NOTES"):
        raise AcceptanceFailure("tool_output_invalid", "completed run is not approved for delivery")
    summary = _json(evidence_root / "summary.json")
    if (
        _identity(evidence_root / "summary.json") != completion["bindings"]["V"]
        or _identity(evidence_root / "evidence-manifest.json") != completion["bindings"]["E"]
        or _identity(evidence_root / "review.json") != completion["bindings"]["Q"]
    ):
        raise AcceptanceFailure("hash_mismatch", "completed control chain changed")
    q = _json(evidence_root / "review.json")
    expected_bindings = {key: completion["bindings"][key] for key in ("C", "S", "D", "E", "V")}
    if (
        q["bindings"] != expected_bindings
        or q["state"] != completion["state"]
        or not summary["success"]
    ):
        raise AcceptanceFailure("hash_mismatch", "completion/review/technical identities disagree")
    _verify_payload(evidence_root, _json(evidence_root / "evidence-manifest.json"))
    contract = load_contract(
        evidence_root / "contract.json", candidate_root=evidence_root / "payload"
    )
    if contract.digest != completion["bindings"]["C"]:
        raise AcceptanceFailure("hash_mismatch", "completed contract changed")
    if summary["D"] is None or summary["D"]["bytes"] <= 0:
        raise AcceptanceFailure("evidence_missing", "delivery identity is missing or empty")
    copied = measure_file(
        delivery_path, summary["D"]["bytes"], file_id=summary["D"]["id"], copy_to=destination
    )
    if (copied.bytes, copied.sha256) != (summary["D"]["bytes"], completion["bindings"]["D"]):
        raise AcceptanceFailure("hash_mismatch", "delivered bytes differ from D")
    receipt = {
        "schema_version": 2,
        "D": copied.sha256,
        "T": _identity(evidence_root / "completion.json"),
        "destination": str(destination),
        "bytes": copied.bytes,
        "delivered_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    _write(evidence_root / "delivery-receipt.json", receipt)
    return receipt
```

模拟测试真实启动 Python 子进程、读取 result、检查 writer/文件、完成封装，但其中 fixture source 不是 .blend，不能引用此成功作为资产通过。生产 CLI 不接受 commands/JobSpec 注入。

控制文件先写独占暂存文件并同步，再通过硬链接原子创建最终名称；最终名存在时失败，不覆盖。中断文件留在独占 run 中而不成为交付许可。finish_review 校验原始 V 与所看图像绑定；技术 true 缺必需 Q 时无 T。无实际非空 D 则传 None 并生成 UNVERIFIED，summary.D 与 bindings.D 均为 null。
- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_pipeline.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。

### Task 8: 生产 CLI 切换与既有回归迁移

**Files:**
- Modify: `scripts/asset_accept.py`（完整替换）
- Test: `tests/unit/test_asset_v2_cli.py`
- Test: `tests/unit/test_asset_v2_legacy_boundaries.py`
- Modify: `docs/README.md`
- Modify: `tests/unit/test_asset_spec_counts.py`

**Interfaces:**
- Consumes: finalize_run/finish_review/deliver、完整冻结与工具链。
- Produces: freeze/run/review/deliver 子命令；dispatch_run(contract_path,source_root,evidence_root,scratch_root) 是 M2/M3 唯一 kind adapter 插入点。

- [ ] **Step 1: 写入行为回归。**

完整新增 `tests/unit/test_asset_v2_cli.py`：

```python
import json
import stat
import subprocess
import sys
from tests.unit.asset_v2_support import REPO, valid_document


def execute(tmp_path, value, *, evidence="evidence", input_root=None):
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps(value))
    command = [
        sys.executable,
        str(REPO / "scripts/asset_accept.py"),
        "run",
        "--contract",
        str(contract),
        "--input-root",
        str(input_root or tmp_path / "source"),
        "--evidence-root",
        str(tmp_path / evidence),
        "--scratch-root",
        str(tmp_path / (evidence + "-scratch")),
    ]
    return subprocess.run(command, capture_output=True, text=True, timeout=15)


def test_production_m1_cli_does_not_publish_mock_success(tmp_path):
    completed = execute(tmp_path, valid_document(tmp_path))
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["state"] == "UNVERIFIED"
    path = tmp_path / "evidence/summary.json"
    summary = json.loads(path.read_text())
    assert summary["schema_version"] == 2 and summary["success"] is False
    assert sum(c["raw_status"] == "NotTested" for c in summary["checks"]) == 15
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_v1_rejected_and_failed_summary_survives(tmp_path):
    value = valid_document(tmp_path)
    value["schema_version"] = 1
    completed = execute(tmp_path, value)
    assert completed.returncode == 1
    summary = json.loads((tmp_path / "evidence/summary.json").read_text())
    assert summary["failure_code"] == "contract_invalid" and summary["success"] is False


def test_reused_root_preserves_existing_files(tmp_path):
    value = valid_document(tmp_path)
    root = tmp_path / "evidence"
    root.mkdir()
    marker = root / "original"
    marker.write_text("preserve")
    completed = execute(tmp_path, value)
    assert completed.returncode == 1 and marker.read_text() == "preserve"
    assert not (root / "summary.json").exists()


def test_missing_input_and_overlapping_roots_do_not_hang(tmp_path):
    value = valid_document(tmp_path)
    (tmp_path / "source/asset.blend").unlink()
    completed = execute(tmp_path, value)
    assert completed.returncode == 1
    assert json.loads((tmp_path / "evidence/summary.json").read_text())["success"] is False
    completed = execute(tmp_path, value, evidence="source/evidence")
    assert completed.returncode == 1
```
完整新增 `tests/unit/test_asset_v2_legacy_boundaries.py`：

```python
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from acceptance import failure_codes as fc
from acceptance.contract import load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import AcceptanceFailure, run_command, clean_environment
from tests.unit.asset_v2_support import REPO, valid_document, write_contract
from tests.unit.test_asset_v2_decide import complete_outcomes


def test_fifo_contract_remains_bounded(tmp_path):
    fifo = tmp_path / "contract.json"
    os.mkfifo(fifo)
    code = (
        "from pathlib import Path\nfrom acceptance.contract import load_contract\n"
        "from acceptance.primitives import AcceptanceFailure\nimport sys\n"
        "try: load_contract(Path(sys.argv[1]),candidate_root=Path(sys.argv[2]))\n"
        "except AcceptanceFailure: raise SystemExit(0)\nraise SystemExit(2)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, str(fifo), str(tmp_path / "source")],
        cwd=REPO,
        capture_output=True,
        timeout=2,
    )
    assert completed.returncode == 0


def test_contract_cap_and_parent_symlink_rejected(tmp_path, monkeypatch):
    import acceptance.contract as module

    value = valid_document(tmp_path)
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(module, "_MAX_CONTRACT_BYTES", path.stat().st_size - 1)
    with pytest.raises(AcceptanceFailure):
        load_contract(path, candidate_root=tmp_path / "source")
    monkeypatch.setattr(module, "_MAX_CONTRACT_BYTES", 1048576)
    folder = tmp_path / "alias"
    folder.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AcceptanceFailure):
        load_contract(folder / "contract.json", candidate_root=tmp_path / "source")


@pytest.mark.parametrize("family", fc.INFRA_FAMILIES)
def test_every_infra_family_still_blocks_and_preserves_real_failures(tmp_path, family):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    outcomes = complete_outcomes(contract)
    original = outcomes[0]
    outcomes[0] = aggregate(
        original.id,
        [Finding("actual_failure", "error")],
        contract=contract,
        tool_id=original.tool_id,
        tool_version=original.tool_version,
        source_truncated=False,
        terminal=None,
    )
    result = decide(
        contract=contract,
        outcomes=outcomes,
        actual_files={"a"},
        expected_files={"a"},
        achieved_grade="local-trusted",
        infra_failures=[family],
    )
    assert result.failure_code == family and not result.success
    assert original.id in result.failed_check_ids


def test_allowed_warning_does_not_compensate_error(tmp_path):
    value = valid_document(tmp_path)
    check_id = "r2.material.slots_resolved"
    version = value["tools"][0]["version"]
    value["warning_allowlist"] = [
        {
            "check_id": check_id,
            "warning_code": "empty_material_slot",
            "tool_id": "python",
            "tool_version": version,
        }
    ]
    contract = write_contract(tmp_path, value)
    warning = Finding("empty_material_slot", "warning")
    passed = aggregate(
        check_id,
        [warning],
        contract=contract,
        tool_id="python",
        tool_version=version,
        source_truncated=False,
        terminal=None,
    )
    failed = aggregate(
        check_id,
        [warning, Finding("lost_used_material", "error")],
        contract=contract,
        tool_id="python",
        tool_version=version,
        source_truncated=False,
        terminal=None,
    )
    assert passed.raw_status == "Pass" and passed.accepted
    assert failed.raw_status == "Fail" and not failed.accepted


def test_sampled_rss_budget_is_observed_not_fake_address_space_limit(tmp_path):
    observed = {}
    limits = {"cpu_seconds": 10, "rss_bytes": 1, "open_files": 128, "file_size_bytes": 1048576}
    with pytest.raises(AcceptanceFailure) as caught:
        run_command(
            "rss-probe",
            [sys.executable, "-c", "import time; x=bytearray(10000000); time.sleep(2)"],
            cwd=tmp_path,
            env=clean_environment(Path(sys.executable)),
            log_path=tmp_path / "log",
            timeout=3,
            max_log_bytes=4096,
            limits=limits,
            observation=observed,
        )
    assert caught.value.code == "resource_limit_exceeded"
    assert observed["memory_sampling"]["samples"] >= 1
    assert observed["memory_sampling"]["peak_observed_rss_bytes"] > 1
```

- [ ] **Step 2: 确认回归先失败。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_cli.py tests/unit/test_asset_v2_legacy_boundaries.py -q`

Expected: 新接口尚不存在时 collection error，或修复前对应反例 assertion failure；不是环境导入错误。

- [ ] **Step 3: 写入最小实现。**

完整替换 `scripts/asset_accept.py`：

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acceptance.contract import load_contract, thaw  # noqa: E402
from acceptance.controller import run_jobs  # noqa: E402
from acceptance.evidence import _write, finalize_run, finish_review, deliver  # noqa: E402
from acceptance.input_bundle import (  # noqa: E402
    freeze_bundle,
    read_bounded,
    source_digest,
    validate_roots,
    verify_bundle,
)  # noqa: E402
from acceptance.plan import assemble_plan  # noqa: E402
from acceptance.primitives import AcceptanceFailure, create_private_directory, normalise_new_root  # noqa: E402
from acceptance.strict_json import strict_json_loads  # noqa: E402


def dispatch_run(
    contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path
) -> dict[str, Any]:
    contract = load_contract(contract_path, candidate_root=source_root)
    # M2/M3 insert their kind-specific adapter here; M1 never accepts worker commands from CLI JSON.
    plan = assemble_plan(contract, ())
    inputs = verify_bundle(
        source_root,
        thaw(contract.raw["input"]["files"]),
        max_file_bytes=contract.raw["budget"]["max_file_bytes"],
    )
    run = run_jobs(
        contract,
        plan,
        run_id=evidence_root.name,
        input_files=inputs,
        scratch_root=scratch_root,
        evidence_root=evidence_root,
        commands={},
    )
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=contract_path,
        source_root=source_root,
        evidence_root=evidence_root,
        delivery=inputs[contract.raw["input"]["main"]],
        coordinator_findings={},
        gates={},
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="v2 asset acceptance; v1 requires a new contract")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    for flag in ("sources", "bundle-root", "manifest"):
        freeze.add_argument("--" + flag, required=True, type=Path)
    freeze.add_argument("--max-files", type=int, default=1024)
    freeze.add_argument("--max-file-bytes", type=int, default=536870912)
    freeze.add_argument("--max-total-bytes", type=int, default=1073741824)
    run = commands.add_parser("run")
    for flag in ("contract", "input-root", "evidence-root", "scratch-root"):
        run.add_argument("--" + flag, required=True, type=Path)
    review = commands.add_parser("review")
    for flag in ("evidence-root", "delivery", "review"):
        review.add_argument("--" + flag, required=True, type=Path)
    delivery = commands.add_parser("deliver")
    for flag in ("evidence-root", "delivery", "destination"):
        delivery.add_argument("--" + flag, required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = None
    root_created = False
    try:
        if args.command == "freeze":
            source_rows = strict_json_loads(read_bounded(args.sources, 1048576).decode("utf-8"))
            if (
                args.manifest.absolute() == args.bundle_root.absolute()
                or args.bundle_root.absolute() in args.manifest.absolute().parents
            ):
                raise AcceptanceFailure(
                    "contract_invalid", "source manifest must be outside frozen files"
                )
            if not isinstance(source_rows, list):
                raise AcceptanceFailure("contract_invalid", "freeze sources must be a list")
            rows = freeze_bundle(
                cast(list[dict[str, Any]], source_rows),
                args.bundle_root.absolute(),
                max_files=args.max_files,
                max_file_bytes=args.max_file_bytes,
                max_total_bytes=args.max_total_bytes,
            )
            result = {"schema_version": 2, "files": rows, "sha256": source_digest(rows)}
            _write(args.manifest, result)
        elif args.command == "run":
            root = normalise_new_root(args.evidence_root, ROOT)
            scratch = normalise_new_root(args.scratch_root, ROOT)
            validate_roots(args.input_root.absolute(), root, scratch, ROOT)
            create_private_directory(root)
            root_created = True
            result = dispatch_run(
                args.contract.absolute(), args.input_root.absolute(), root, scratch
            )
        elif args.command == "review":
            review = strict_json_loads(read_bounded(args.review, 1048576).decode("utf-8"))
            if not isinstance(review, dict):
                raise AcceptanceFailure("tool_output_invalid", "review must be an object")
            result = finish_review(
                args.evidence_root.absolute(), delivery_path=args.delivery.absolute(), review=review
            )
        else:
            result = deliver(
                args.evidence_root.absolute(),
                delivery_path=args.delivery.absolute(),
                destination=args.destination.absolute(),
            )
    except Exception as exc:
        code = getattr(exc, "code", "runner_internal_error")
        result = {
            "schema_version": 2,
            "state": "UNVERIFIED",
            "failure_code": code,
            "error": str(exc),
        }
        if root_created and root is not None and not (root / "summary.json").exists():
            _write(
                root / "summary.json",
                {
                    "schema_version": 2,
                    "kind": "asset_acceptance",
                    "success": False,
                    "failure_code": code,
                    "error": str(exc),
                    "checks": [],
                    "gates": {},
                    "failed_check_ids": [],
                    "failed_gate_ids": [],
                },
            )
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if args.command in ("run", "review"):
        return 0 if result["state"] in ("SHIP", "SHIP_WITH_NOTES") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

run/review 只有 SHIP/SHIP_WITH_NOTES 退出 0；NEEDS_REVIEW/REJECTED/UNVERIFIED 均退出 1，stdout 是一行 JSON。freeze/deliver 成功退出 0。M1 固定空 worker 计划，不给 CLI 提供模拟成功参数。

现有 v1 测试按下表迁移：保留它们的行为目的，切换到上述完整 v2 测试。`test_asset_canonical.py` 和 `test_asset_registry.py` 保持不变。
- [ ] **Step 4: 确认同一回归通过。**

Run: `.venv/bin/python -m pytest tests/unit/test_asset_v2_cli.py tests/unit/test_asset_v2_legacy_boundaries.py -q`

Expected: 全部通过；此测试不启动真实 Blender。

- [ ] **Step 5: 审阅本任务差异。**

Run: `git diff --check`

Expected: 退出 0。按本文末尾提交门禁合并 M1 提交；没有提交授权时保留可审阅差异，不自行推送。


| 旧文件 | v2 回归归属与改变 |
|---|---|
| `test_asset_contract.py` | v2_contract + legacy_boundaries：封闭字段/精确类型、UTF8/BOM、FIFO、父链、摘要、外部策略、不可变、v1 拒绝 |
| `test_asset_decide.py` | v2_decide + legacy_boundaries：所有 infra family、warning 与硬失败、伪造 outcome/N/A、Fail+NotTested、gates |
| `test_asset_stages.py` | v2_toolchain/input/pipeline：真实 tool/input 身份与 R5，不再拿空 manifest 或未测输入当成功 |
| `test_asset_evidence.py` | v2_pipeline/cli：无环 E/V/Q/T、失败摘要、签收不改 V、精确交付 |
| `test_asset_accept.py` | v2_cli/input/legacy_boundaries：私有新根、复用拒绝、缺失、FIFO/安全读取、变更与大小上限、15 项 NotTested |

五个旧测试文件只在新回归全部通过后退出收集；这是 schema/API 迁移，不保留 v1 放行代码。执行以下明确文件操作：

```python
from pathlib import Path
for name in ("test_asset_contract.py", "test_asset_decide.py", "test_asset_stages.py",
             "test_asset_evidence.py", "test_asset_accept.py"):
    Path("tests/unit", name).unlink()
```

不要删除 `test_asset_canonical.py`、`test_asset_registry.py`。替换旧 V3.8 文本计数测试的完整内容：

```python
from pathlib import Path
import re
from acceptance import check_registry as reg
from acceptance import failure_codes as fc

SPEC = Path(__file__).resolve().parents[2] / "docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md"

def test_current_registry_table_matches_v2():
    text = SPEC.read_text()
    rows = re.findall(r"^\| `(r[0-5]\.[a-z_]+\.[a-z_]+)` \| ([0-9]+) \| `([^`]+)` \|$", text, re.M)
    assert rows == [(s.id, str(s.impl), s.writer) for s in reg.CHECKS]

def test_current_failure_family_table_is_complete():
    text = SPEC.read_text()
    rows = re.findall(r"^\| `([a-z_]+)` \| ([0-9]+) \|$", text, re.M)
    assert rows == [(name, str(index)) for index, name in enumerate(fc.FAILURE_FAMILIES)]
```

M1 切换后，按机器表更新 V5 的版本/失败表与 README 当前入口，保留历史 V3.8 原文。运行下面的完整同步脚本：

```python
from pathlib import Path
from acceptance import check_registry as reg, failure_codes as fc
spec = Path("docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md")
text = spec.read_text().split("\n## 当前机器表\n")[0]
text = text.replace("状态：M0/M1 目标规范。完成 v2 CLI 和回归切换后才标为当前实现规范。",
                    "状态：当前 v2/M1 规范；R2–R4 worker 尚未接线，通用资产不能自动放行。")
text += "\n## 当前机器表\n\n| Check ID | impl | writer |\n|---|---:|---|\n"
text += "".join(f"| `{s.id}` | {s.impl} | `{s.writer}` |\n" for s in reg.CHECKS)
text += "\n| Failure family | priority |\n|---|---:|\n"
text += "".join(f"| `{name}` | {index} |\n" for index, name in enumerate(fc.FAILURE_FAMILIES))
spec.write_text(text)
readme = Path("docs/README.md")
lines = readme.read_text().splitlines()
updated = []
for line in lines:
    if line.startswith("- [V5/v2 迁移目标]"):
        continue
    if line.startswith("- [验收方案 V3.8]"):
        line = "- [资产验收规范 V5](acceptance/blender_mcp_skill_acceptance_optimized_v5.md)：当前 v2/M1 规范；旧 V3.8 为历史记录。"
    if line.startswith("当前只实现了不依赖 Blender 的 P0"):
        line = "当前 M1 完成可信核心、冻结输入与真实证据封装；R2–R4 尚未接线，通用资产验收仍未完成，不得自动发布放行。"
    updated.append(line)
readme.write_text("\n".join(updated) + "\n")
```

### M1 最终门禁与提交

- [ ] `.venv/bin/python -m pytest tests/unit/test_asset_v2_*.py tests/unit/test_asset_canonical.py tests/unit/test_asset_registry.py tests/unit/test_asset_spec_counts.py -q` 全部通过。
- [ ] `bash scripts/checks.sh` 输出 `ALL CHECKS PASSED`；不运行 RELEASE 或正式 Phase 0 现场门禁冒充本任务验证。
- [ ] 最后改动后 `graft build .`；随后 `graft check .` 退出 0。
- [ ] `git diff --check` 退出 0，审阅没有候选资产、日志、冻结包、node_modules 或 graft 缓存被暂存。
- [ ] 在已有提交授权范围内提交 M0/M1；不自行推送。提交标题建议 `feat: harden asset acceptance core with v2 evidence protocol`。

M1 的完成声明限于：纯 Python 可信核心与真实子进程 JSON/文件封装已验证，正常生产 CLI 仍对缺少 15/25 个 worker 检查失败关闭。后续分别执行原生和 GLB 计划；不得用模拟成功替代真实资产的正向闭环。
