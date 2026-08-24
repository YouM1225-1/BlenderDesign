# 资产验收判定核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `acceptance/` 包的判定核心——注册表、合同加载、JCS 摘要、判定引擎、证据写入与 CLI coordinator——使其能对**合成的子进程产物**做出符合规范 §2.6 的放行判定,全程不依赖 Blender。

**Architecture:** 判定核心是一个纯函数式管线:`contract.json` 经封闭校验后冻结出 expected check/file 集合;各 stage 的 `result.json`(本计划中由测试合成)被解析为 finding 列表;`decide.py` 把 finding 聚合成 `raw_status`、再算 `effective_status`,最后按十条放行公式产出 `summary.json` 与退出码。所有安全原语(私有目录、`O_EXCL` 写入、进程组清理)从既有的 Phase 0 wrapper **提取**为共享模块,Phase 0 回 import,使这两条链路不再各持一份。(注:`smoke/e2e.py` 与 `smoke/runner.py` 另有严格 JSON 三件套的独立副本,规范 §7.7 未要求本轮合并,留待后续。)

**Tech Stack:** Python 3.13.13 · uv(`--frozen`)· pytest · ruff · mypy strict · 标准库 `hashlib`/`json`/`os`(无新增第三方依赖)

## Global Constraints

- 规范唯一来源:`docs/acceptance/blender_mcp_skill_acceptance_optimized_v3_8.md`(以下简称"规范")。凡本计划与规范冲突,以规范为准并在实施中提出。
- Python 精确 `3.13.13`;所有命令经 `uv run --frozen` 执行。
- 验证唯一入口:`bash scripts/checks.sh`,必须输出 `ALL CHECKS PASSED`。
- 形式化证据要求 Git 工作树完全干净(未跟踪文件也算脏);新增文件先提交再跑证据链。
- 本计划**不引入任何第三方依赖**,不引入 Blender 硬依赖:默认 `pytest` 不得启动 Blender。
- 新代码必须被 ruff 与 mypy strict 覆盖(Task 1 负责把 `acceptance` 纳入两者范围)。
- 所有写入 evidence root 的文件用 `O_EXCL` 新建、权限 `0600`;目录 `0700`。
- 判定引擎是规范 §2.5/§2.6 的**唯一实现处**;任何其他模块不得复制判定逻辑。

---

### Task 1: 提取共享原语并纳入门禁

**Files:**
- Create: `acceptance/__init__.py`
- Create: `acceptance/primitives.py`
- Modify: `scripts/run_phase0_acceptance.py`(删除被提取的函数体,改为 re-export)
- Modify: `scripts/checks.sh:37-38`(ruff 路径)、`scripts/checks.sh:134`(bandit 路径)
- Modify: `pyproject.toml:37`(mypy `files`)
- Test: 既有 `tests/unit/test_phase0_acceptance.py` **一行不改**必须继续全绿

**Interfaces:**
- Consumes: `scripts/run_phase0_acceptance.py` 现有的模块私有函数
- Produces: `acceptance.primitives` 暴露 `AcceptanceFailure`、`normalise_new_root(path, repo_root)`、`create_private_directory(path)`、`clean_environment(uv, blocked_prefixes)`、`reject_json_constant(value)`、`finite_json_float(value)`、`reject_duplicate_keys(pairs)`、`file_evidence(path, max_bytes)`、`write_json_exclusive(path, value)`、`group_exists(pid)`、`stop_group(process)`、`run_command(stage, command, *, cwd, env, log_path, timeout)`、`require_zero(stage, returncode)`

- [ ] **Step 1: 确认基线全绿(改动前的对照)**

Run: `bash scripts/checks.sh 2>&1 | tail -3`
Expected: 末行 `ALL CHECKS PASSED`;记下 `362 passed` 与 `821 passed, 1 skipped` 两个数字。**这两个基线只在 Task 1 内用作“提取未改变行为”的对照**;Task 2 起每个任务都会新增测试,后续步骤只需 `ALL CHECKS PASSED`,不要拿它们逐字比对。

- [ ] **Step 2: 创建包与原语模块**

`acceptance/__init__.py` 内容为空文件(仅换行)。

`acceptance/primitives.py`:把 `scripts/run_phase0_acceptance.py` 中下列符号**整体搬迁**并去掉前导下划线(改为公开名),函数体逐字不变:

| 源符号(`run_phase0_acceptance.py`) | 新名(`acceptance/primitives.py`) |
|---|---|
| `AcceptanceFailure` | `AcceptanceFailure` |
| `_normalise_new_root` | `normalise_new_root` |
| `_create_private_directory` | `create_private_directory` |
| `_clean_environment` | `clean_environment` |
| `_reject_json_constant` | `reject_json_constant` |
| `_finite_json_float` | `finite_json_float` |
| `_reject_duplicate_keys` | `reject_duplicate_keys` |
| `_file_evidence` | `file_evidence` |
| `_write_json_exclusive` | `write_json_exclusive` |
| `_group_exists` | `group_exists` |
| `_stop_group` | `stop_group` |
| `_run_command` | `run_command` |
| `_require_zero` | `require_zero` |

两处必须参数化(原版把仓库根与常量写死,新模块要能服务两个 coordinator):

```python
def normalise_new_root(path: Path, repo_root: Path) -> Path:
    """返回一个规范化的、尚不存在的、位于 repo_root 之外的绝对路径。"""
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    parent = candidate.parent.resolve(strict=True)
    candidate = parent / candidate.name
    try:
        candidate.lstat()
    except FileNotFoundError:
        pass
    else:
        raise AcceptanceFailure(
            "reused_evidence_root", f"evidence root already exists: {candidate}")
    if candidate == repo_root or repo_root in candidate.parents:
        raise AcceptanceFailure(
            "evidence_root_inside_candidate",
            "evidence root must be outside the candidate Git worktree",
        )
    return candidate


def file_evidence(path: Path, max_bytes: int) -> dict[str, object]:
    try:
        raw = read_private_bytes(path, time.monotonic() + 5.0, max_bytes)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AcceptanceFailure(
            "evidence_file_invalid", f"invalid evidence file {path}: {exc}") from exc
    return {"path": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def run_command(
    stage: str,
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    timeout: float,
) -> int:
    """与 Phase 0 版本逐行一致,仅把写死的 ROOT 换成 cwd 形参。"""
    descriptor = os.open(
        log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=descriptor,
            stderr=subprocess.STDOUT, start_new_session=True, umask=0o077)
    finally:
        os.close(descriptor)
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stop_group(process)
        raise AcceptanceFailure(
            f"{stage}_timeout", f"{stage} exceeded {timeout:g} seconds") from exc
    except BaseException:
        stop_group(process)
        raise
    if group_exists(process.pid):
        stop_group(process)
        raise AcceptanceFailure(
            f"{stage}_process_group_leak", f"{stage} left a live process group")
    return returncode
```

**"去掉前导下划线"只作用于上表列出的顶层符号名**,不要动 `__init__` 这类 dunder、`self.code` 这类属性,也不要动局部变量。被搬迁函数之间的相互引用要一并改名:`run_command` 内部调用的 `_stop_group`/`_group_exists` 必须写成 `stop_group`/`group_exists`,否则得到 `F821`。

`clean_environment` 的 `blocked` 元组改为形参 `blocked_prefixes: tuple[str, ...]`,默认值取 Phase 0 现值 `("BLENDERCODEX_", "BLENDER_", "DYLD_", "GIT_", "LD_", "PYTHON", "UV_")`。

**依赖说明(实测确认)**:`run_phase0_acceptance.py:19` 有 `from smoke.process_registry import read_private_bytes, require_private_directory`,`file_evidence` 与 `write_json_exclusive` 都用到它们。这一行必须**一并搬进** `acceptance/primitives.py`,因此 `acceptance` 会依赖 `smoke`。这是仓库内模块间的正常依赖(`smoke/` 已是可导入包),但会影响 Step 5 的 mypy 配置——见该步的处理。文件顶部需要的完整 import 集合:

```python
from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path

from smoke.process_registry import read_private_bytes, require_private_directory
```

`math` 是 `finite_json_float` 需要的,漏掉会得到 `F821`。

- [ ] **Step 3: 让 Phase 0 回 import**

**关键约束:内部调用点一律保持旧私有名不变。** 只把这些私有函数的**函数体**换成转调 `acceptance.primitives`,**不要**把 `_execute()` 里的调用改成新名——`tests/unit/test_phase0_acceptance.py` 的第 71 行与第 104 行做的是 `monkeypatch.setattr(acceptance, "_run_command", fake_run)`;一旦调用点绕过私有名,monkeypatch 失效,真实的 Blender 子进程会被拉起,两条测试挂掉。

在 `scripts/run_phase0_acceptance.py` 中删除上表全部函数体,替换为:

```python
from acceptance.primitives import (
    AcceptanceFailure,
    clean_environment,
    create_private_directory,
    file_evidence,
    finite_json_float,
    group_exists,
    normalise_new_root,
    reject_duplicate_keys,
    reject_json_constant,
    require_zero,
    run_command,
    stop_group,
    write_json_exclusive,
)
```

**同时删除因搬迁而失效的导入**——实测会报 3 个 `F401`,而 `scripts` 在 `checks.sh:38` 的 ruff 范围内,不删则 Step 6 必红:

- 删 `import hashlib`(原只被 `_file_evidence` 用)
- 删 `import signal`(原只被 `_stop_group` 用)
- 第 19 行改为 `from smoke.process_registry import read_private_bytes`

`AcceptanceFailure` **不需要**别名——全仓 grep 确认从不存在 `_AcceptanceFailure` 这个名字,既有测试用的就是公开名。

然后为每个被搬迁的符号保留**同名薄封装**,签名与原版逐字一致:

```python
def _normalise_new_root(path: Path) -> Path:
    return normalise_new_root(path, ROOT)


def _clean_environment(uv: Path) -> dict[str, str]:
    clean = clean_environment(uv)
    return clean


def _run_command(stage, command, *, env, log_path, timeout):
    return run_command(stage, command, cwd=ROOT, env=env, log_path=log_path, timeout=timeout)
```

其余符号(`_create_private_directory`、`_reject_json_constant`、`_finite_json_float`、`_reject_duplicate_keys`、`_group_exists`、`_stop_group`、`_require_zero`)用 `_name = name` 别名即可;`_file_evidence` 与 `_write_json_exclusive` 保留同名薄封装,内部转调新模块;`MAX_ARTIFACT_BYTES` 常量留在 `run_phase0_acceptance.py` 并作为实参传入 `file_evidence`。

`AcceptanceFailure` **不需要**别名——全仓 grep 确认从不存在 `_AcceptanceFailure` 这个名字,既有测试用的就是公开名 `acceptance.AcceptanceFailure`。

**这一步的验收标准是既有测试一行不改仍全绿**——它们直接 import 这些私有名,薄封装保证签名不变。

- [ ] **Step 4: 运行既有 Phase 0 测试**

Run: `uv run --frozen pytest tests/unit/test_phase0_acceptance.py -q`
Expected: 全部通过,无 skip、无 error。若失败,**回滚本任务并改用规范 §7.7 的复制方案**,在提交信息中记录原因。

- [ ] **Step 5: 把 acceptance 纳入 lint / type / security 范围**

`scripts/checks.sh` 第 37-38 行改为:

```bash
"$UV_BIN" run --frozen ruff check \
  protocol bridge server tests scripts smoke acceptance plugins/blender-mcp-installer/scripts
```

`scripts/checks.sh` 第 134 行(RELEASE 分支的第一处 bandit)改为:

```bash
    bandit -q -r protocol bridge server smoke scripts acceptance \
```

`pyproject.toml` 第 37 行改为:

```toml
files = ["protocol", "bridge/core", "server", "acceptance"]
```

**mypy 跟随导入的处理**:`acceptance/primitives.py` 会 import `smoke.process_registry`,而 `smoke` 不在 `files` 里。先直接跑一次:

```bash
uv run --frozen mypy
```

- 若通过(mypy 会跟随并检查 `smoke.process_registry`,该模块本身有类型注解时即可通过),不做额外改动;
- 若报 `smoke` 相关错误,**先尝试把 `"smoke"` 加入 `files`**(最干净,让该模块也受 strict 检查);
- 只有当 `smoke` 存在大量遗留类型问题、加入会淹没本任务时,才退而在 `[[tool.mypy.overrides]]` 中为 `smoke.*` 设 `follow_imports = "skip"`,并在提交信息中记录该妥协及后续清理计划。

三种结果都必须在本任务的提交信息里写明实际采用了哪一种。

**不改** `[tool.hatch.build.targets.wheel] packages` 与 sdist 白名单——本工具是 repo-only,不进分发(规范 §7.7 定案 1)。

- [ ] **Step 6: 跑完整门禁**

Run: `bash scripts/checks.sh 2>&1 | tail -3`
Expected: `ALL CHECKS PASSED`,且两个测试数字与 Step 1 记录的一致。

- [ ] **Step 7: 提交**

```bash
git add acceptance/__init__.py acceptance/primitives.py scripts/run_phase0_acceptance.py scripts/checks.sh pyproject.toml
git commit -m "refactor: extract acceptance primitives shared with Phase 0 wrapper"
```

---

### Task 2: Check registry 与 failure-code family

**Files:**
- Create: `acceptance/check_registry.py`
- Create: `acceptance/failure_codes.py`
- Test: `tests/unit/test_asset_registry.py`

**Interfaces:**
- Consumes: 无
- Produces: `CHECKS: tuple[CheckSpec, ...]`(`CheckSpec` 为 frozen dataclass,字段 `id: str`、`stage: str`、`order: int`、`impl: int`、`kind: str`、`writer: str`、`warning_codes: tuple[str, ...]`);`checks_for_kind(kind) -> tuple[CheckSpec, ...]`;`na_check_ids(kind) -> tuple[str, ...]`;`FAILURE_FAMILIES: tuple[str, ...]`(按规范 §7.2 的优先级顺序);`INFRA_FAMILIES`;`family_priority(code) -> int`

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_asset_registry.py`:

```python
from acceptance import check_registry as reg
from acceptance import failure_codes as fc


def test_registry_has_37_unique_checks():
    assert len(reg.CHECKS) == 37
    assert len({c.id for c in reg.CHECKS}) == 37


def test_kind_split_matches_spec():
    counts: dict[str, int] = {}
    for c in reg.CHECKS:
        counts[c.kind] = counts.get(c.kind, 0) + 1
    assert counts == {"all": 21, "interchange": 13, "blend_native": 3}


def test_every_check_has_exactly_one_writer():
    assert all(c.writer for c in reg.CHECKS)


def test_na_set_is_complement_of_kind():
    blend = set(reg.na_check_ids("blend_native"))
    inter = set(reg.na_check_ids("interchange"))
    assert blend == {c.id for c in reg.CHECKS if c.kind == "interchange"}
    assert inter == {c.id for c in reg.CHECKS if c.kind == "blend_native"}
    assert blend & inter == set()


def test_stage_order_id_is_a_total_order():
    keys = [(c.stage, c.order, c.id) for c in reg.CHECKS]
    assert len(set(keys)) == len(keys)


def test_failure_families_are_16_and_check_failed_is_last():
    assert len(fc.FAILURE_FAMILIES) == 16
    assert fc.FAILURE_FAMILIES[-1] == "check_failed"
    assert "check_failed" not in fc.INFRA_FAMILIES
    assert len(fc.INFRA_FAMILIES) == 15


def test_family_priority_is_strictly_increasing():
    priorities = [fc.family_priority(f) for f in fc.FAILURE_FAMILIES]
    assert priorities == sorted(priorities)
    assert len(set(priorities)) == len(priorities)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --frozen pytest tests/unit/test_asset_registry.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'acceptance.check_registry'`

- [ ] **Step 3: 实现注册表**

`acceptance/check_registry.py`:

```python
"""规范 §7.1 的 check registry。本文件即该表的唯一机器可读形式。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckSpec:
    id: str
    stage: str
    order: int
    impl: int
    kind: str          # "all" | "interchange" | "blend_native"
    writer: str
    warning_codes: tuple[str, ...] = ()


CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec("r0.contract.schema_closed", "R0", 10, 1, "all", "coordinator"),
    CheckSpec("r0.contract.tools_locked", "R0", 20, 1, "all", "coordinator"),
    CheckSpec("r0.contract.na_set_declared", "R0", 30, 1, "all", "coordinator"),
    CheckSpec("r1.input.digest_recorded", "R1", 10, 1, "all", "coordinator"),
    CheckSpec("r1.input.no_link_or_device", "R1", 20, 1, "all", "coordinator"),
    CheckSpec("r1.input.size_within_limit", "R1", 30, 1, "all", "coordinator"),
    CheckSpec("r2.inventory.coverage_complete", "R2", 10, 1, "all", "inspector",
              ("unsupported_datablock_type", "unsupported_modifier_type")),
    CheckSpec("r2.inventory.no_nan_inf", "R2", 20, 1, "all", "inspector"),
    CheckSpec("r2.inventory.no_reserved_props", "R2", 25, 1, "all", "inspector"),
    CheckSpec("r2.geometry.validate_clean", "R2", 30, 1, "all", "inspector"),
    CheckSpec("r2.geometry.manifest_written", "R2", 40, 1, "all", "inspector"),
    CheckSpec("r2.material.slots_resolved", "R2", 50, 1, "all", "inspector",
              ("empty_material_slot",)),
    CheckSpec("r2.dependency.all_present", "R2", 60, 1, "all", "inspector",
              ("packed_dependency",)),
    CheckSpec("r2.source.digest_stable", "R2", 70, 1, "all", "inspector"),
    CheckSpec("r3.export.file_nonempty", "R3", 10, 1, "interchange", "export_glb"),
    CheckSpec("r3.export.source_unchanged", "R3", 20, 1, "interchange", "export_glb"),
    CheckSpec("r3.validator.no_error", "R3", 30, 1, "interchange", "coordinator"),
    CheckSpec("r3.validator.resources_read", "R3", 40, 1, "interchange", "coordinator"),
    CheckSpec("r3.validator.report_complete", "R3", 50, 1, "interchange", "coordinator"),
    CheckSpec("r3.extension.none_forbidden", "R3", 60, 1, "interchange", "coordinator"),
    CheckSpec("r3.budget.within_limits", "R3", 70, 1, "interchange", "glb_budget",
              ("budget_near_limit", "non_triangle_primitive")),
    CheckSpec("r4.reopen.offline_ok", "R4", 10, 1, "blend_native", "reopen_probe"),
    CheckSpec("r4.reopen.dependencies_resolved", "R4", 20, 1, "blend_native", "reopen_probe"),
    CheckSpec("r4.reopen.manifest_matches_source", "R4", 25, 1, "blend_native", "reopen_probe"),
    CheckSpec("r4.import.manifest_written", "R4", 30, 1, "interchange", "reimport_probe"),
    CheckSpec("r4.projection.preserved_fields_match", "R4", 40, 1, "interchange", "coordinator"),
    CheckSpec("r4.projection.transformed_within_tolerance", "R4", 45, 1, "interchange",
              "coordinator"),
    CheckSpec("r4.projection.undeclared_loss", "R4", 50, 1, "interchange", "coordinator"),
    CheckSpec("r4.projection.ambiguous_object_names", "R4", 55, 1, "interchange", "coordinator"),
    CheckSpec("r4.visual.scene_not_empty", "R4", 60, 1, "all", "render_views(src)"),
    CheckSpec("r4.visual.all_views_rendered", "R4", 70, 1, "all", "coordinator"),
    CheckSpec("r4.visual.self_determinism", "R4", 80, 1, "all", "render_views(src)"),
    CheckSpec("r4.visual.platform_key_known", "R4", 90, 1, "all", "render_views(src)"),
    CheckSpec("r4.visual.source_import_match", "R4", 100, 1, "interchange", "coordinator"),
    CheckSpec("r5.evidence.manifest_closed", "R5", 10, 1, "all", "coordinator"),
    CheckSpec("r5.evidence.hashes_match", "R5", 20, 1, "all", "coordinator"),
    CheckSpec("r5.contract.digest_stable", "R5", 30, 1, "all", "coordinator"),
)

_STAGE_INDEX = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}


def sort_key(spec: CheckSpec) -> tuple[int, int, str]:
    """规范 §2.5.1 规则 2 的全序键。"""
    return (_STAGE_INDEX[spec.stage], spec.order, spec.id)


def checks_for_kind(kind: str) -> tuple[CheckSpec, ...]:
    return tuple(c for c in CHECKS if c.kind in ("all", kind))


def na_check_ids(kind: str) -> tuple[str, ...]:
    return tuple(sorted(c.id for c in CHECKS if c.kind not in ("all", kind)))
```

`acceptance/failure_codes.py`:

```python
"""规范 §7.2 的 failure-code family,元组顺序即优先级(靠前者优先)。"""
from __future__ import annotations

FAILURE_FAMILIES: tuple[str, ...] = (
    "contract_invalid",
    "toolchain_mismatch",
    "tool_crashed",
    "tool_output_invalid",
    "stale_result_file",
    "zero_checks_collected",
    "expected_set_mismatch",
    "forged_not_applicable",
    "forged_disposition",
    "evidence_missing",
    "evidence_truncated",
    "hash_mismatch",
    "isolation_insufficient",
    "resource_limit_exceeded",
    "runner_internal_error",
    "check_failed",
)

INFRA_FAMILIES: tuple[str, ...] = tuple(f for f in FAILURE_FAMILIES if f != "check_failed")

_PRIORITY = {family: index for index, family in enumerate(FAILURE_FAMILIES)}


def family_priority(code: str) -> int:
    if code not in _PRIORITY:
        raise ValueError(f"unknown failure family: {code}")
    return _PRIORITY[code]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run --frozen pytest tests/unit/test_asset_registry.py -q`
Expected: `7 passed`

- [ ] **Step 5: 提交**

```bash
git add acceptance/check_registry.py acceptance/failure_codes.py tests/unit/test_asset_registry.py
git commit -m "feat: add acceptance check registry and failure-code families"
```

---

### Task 3: JCS 规范化与 digest

**Files:**
- Create: `acceptance/canonical.py`
- Test: `tests/unit/test_asset_canonical.py`

**Interfaces:**
- Consumes: 无
- Produces: `canonicalize(value: object) -> bytes`(RFC 8785 JCS);`digest(kind: str, value: object) -> str`(带 `bcx.digest.v1.<kind>.` 域前缀的 SHA-256 十六进制);`CanonicalError`

- [ ] **Step 1: 写失败的测试(含规范 §2.5.1 要求的 golden vectors)**

`tests/unit/test_asset_canonical.py`:

```python
import pytest

from acceptance.canonical import CanonicalError, canonicalize, digest


def test_key_order_is_normalised():
    assert canonicalize({"b": 1, "a": 2}) == canonicalize({"a": 2, "b": 1})
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_integer_and_float_with_same_value_serialise_identically():
    assert canonicalize({"x": 1}) == canonicalize({"x": 1.0}) == b'{"x":1}'


def test_negative_zero_is_normalised_to_zero():
    assert canonicalize({"x": -0.0}) == b'{"x":0}'


def test_unicode_must_be_nfc():
    # 必须用转义字面量:直接粘贴的两个 e-acute 在编辑器或文件写入时会被归一化成
    # 同一串,那样这条测试会静默失效(本计划初稿就踩过这个坑)。
    composed = "\u00e9"        # 单码点
    decomposed = "e\u0301"     # e + combining acute,两码点
    assert composed != decomposed
    assert canonicalize({"k": composed}) == '{"k":"\u00e9"}'.encode("utf-8")
    with pytest.raises(CanonicalError):
        canonicalize({"k": decomposed})


def test_non_finite_numbers_are_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalError):
            canonicalize({"x": bad})


def test_empty_containers_round_trip():
    assert canonicalize({"a": {}, "b": []}) == b'{"a":{},"b":[]}'


def test_array_order_is_preserved():
    assert canonicalize([2, 1]) == b"[2,1]"


def test_digest_is_domain_separated():
    value = {"a": 1}
    assert digest("contract", value) != digest("manifest", value)
    assert len(digest("contract", value)) == 64


def test_digest_is_stable_across_key_order():
    assert digest("contract", {"a": 1, "b": 2}) == digest("contract", {"b": 2, "a": 1})


@pytest.mark.parametrize(("value", "expected"), [
    (1e-5, "0.00001"),      # 规范 §6 的默认几何容差
    (1e-6, "0.000001"),     # 规范 §4.2 的量化步长
    (1e-7, "1e-7"),
    (1e-8, "1e-8"),
    (1.5e-7, "1.5e-7"),
    (1e21, "1e+21"),
    (123456789012345678901.0, "123456789012345680000"),
    (0.5, "0.5"),
    (100.0, "100"),
    (6.02e23, "6.02e+23"),
])
def test_numbers_match_ecmascript_tostring(value, expected):
    """基准值取自 node 的 String(x);CPython 的 repr 在前五条上与之分歧。"""
    assert canonicalize({"x": value}) == f'{{"x":{expected}}}'.encode()


def test_control_characters_use_short_escapes():
    assert canonicalize({"k": "\b\f"}) == b'{"k":"\\b\\f"}'


def test_digest_is_stable_across_processes(tmp_path):
    """规范 §2.5.1 要求跨进程复算一致 —— 同进程重算证明不了这一点。"""
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = tmp_path / "recompute.py"
    script.write_text(
        "from acceptance.canonical import digest\n"
        "print(digest('contract', {'a': [1, 1.0, -0.0], 'b': '\\u00e9'}))\n",
        encoding="utf-8")
    # Must explicitly pass PYTHONPATH to the subprocess because the `acceptance` package
    # is repo-only (not in wheel/sdist). In non-editable installs, the repo root is not
    # on sys.path, so the subprocess fails to import unless we add it explicitly.
    # This makes the test independent of whether the venv is editable or not.
    repo_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, str(script)], check=True, capture_output=True, text=True,
        env=os.environ | {"PYTHONPATH": str(repo_root)})
    here = digest("contract", {"a": [1, 1.0, -0.0], "b": "\u00e9"})
    assert completed.stdout.strip() == here


def test_digest_has_the_frozen_domain_prefix():
    import hashlib
    expected = hashlib.sha256(b"bcx.digest.v1.contract." + b'{"a":1}').hexdigest()
    assert digest("contract", {"a": 1}) == expected
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --frozen pytest tests/unit/test_asset_canonical.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'acceptance.canonical'`

- [ ] **Step 3: 实现**

`acceptance/canonical.py`:

```python
"""规范 §2.5.1:RFC 8785 JSON Canonicalization Scheme + 四条项目内规则。"""
from __future__ import annotations

import hashlib
import math
import unicodedata

_DIGEST_PREFIX = "bcx.digest.v1."


class CanonicalError(ValueError):
    """输入不满足规范化前置条件(非 NFC、非有限数、未知类型)。"""


def _check_string(value: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalError(f"string is not NFC-normalised: {value!r}")
    return value


def _number(value: float | int) -> str:
    """ECMAScript `Number::toString`(RFC 8785 §3.2.2.3 引用的算法)。

    **不能用 `repr`**:CPython 与 ES 在多处分歧,且分歧恰好落在本方案实际使用的
    量级上——`1e-5`(规范 §6 的默认几何容差)`repr` 得 `1e-05` 而 ES 得 `0.00001`;
    `1e-6`(规范 §4.2 的量化步长)`repr` 得 `1e-06` 而 ES 得 `0.000001`。
    下面按 ES 规范逐条实现;`repr` 只用来取"最短往返十进制数字串",这一点二者一致。
    """
    if isinstance(value, bool):
        raise CanonicalError("bool must be handled before number")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise CanonicalError(f"non-finite number: {value!r}")
    if value == 0.0:
        return "0"                      # 同时覆盖 -0.0
    if value < 0:
        return "-" + _number(-value)

    text = repr(value)
    mantissa, _, exponent = text.partition("e")
    exp = int(exponent) if exponent else 0
    int_part, _, frac_part = mantissa.partition(".")
    combined = int_part + frac_part
    stripped = combined.lstrip("0")
    leading = len(combined) - len(stripped)
    # n:使 value == 0.digits x 10**n 成立的十进制指数(ES 规范中的 n)
    n_exp = len(int_part) + exp - leading
    digits = stripped.rstrip("0") or "0"
    k = len(digits)

    if k <= n_exp <= 21:
        return digits + "0" * (n_exp - k)
    if 0 < n_exp <= 21:
        return digits[:n_exp] + "." + digits[n_exp:]
    if -6 < n_exp <= 0:
        return "0." + "0" * (-n_exp) + digits
    power = n_exp - 1
    sign = "+" if power >= 0 else "-"
    head = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{head}e{sign}{abs(power)}"


def _escape(value: str) -> str:
    out = ['"']
    for char in value:
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif char == "\b":
            out.append("\\b")
        elif char == "\f":
            out.append("\\f")
        elif ord(char) < 0x20:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _emit(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _escape(_check_string(value))
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_emit(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = [k for k in value]
        if any(not isinstance(k, str) for k in keys):
            raise CanonicalError("object keys must be strings")
        if len(set(keys)) != len(keys):
            raise CanonicalError("duplicate object key")
        ordered = sorted(keys, key=lambda k: _check_string(k).encode("utf-16-be"))
        body = ",".join(f"{_escape(k)}:{_emit(value[k])}" for k in ordered)
        return "{" + body + "}"
    raise CanonicalError(f"unsupported type: {type(value).__name__}")


def canonicalize(value: object) -> bytes:
    return _emit(value).encode("utf-8")


def digest(kind: str, value: object) -> str:
    payload = (_DIGEST_PREFIX + kind + ".").encode("ascii") + canonicalize(value)
    return hashlib.sha256(payload).hexdigest()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run --frozen pytest tests/unit/test_asset_canonical.py -q`
Expected: `22 passed`(9 条基础 + 10 条 ES 数字参数化 + 短转义 + 跨进程 + 域前缀)

- [ ] **Step 5: 提交**

```bash
git add acceptance/canonical.py tests/unit/test_asset_canonical.py
git commit -m "feat: add RFC 8785 canonicalization and domain-separated digests"
```

---

### Task 4: 合同加载与封闭校验

**Files:**
- Create: `acceptance/contract.py`
- Test: `tests/unit/test_asset_contract.py`

**Interfaces:**
- Consumes: `acceptance.canonical.digest`、`acceptance.check_registry`、`acceptance.primitives.AcceptanceFailure`
- Produces: `Contract`(frozen dataclass,字段见下);`load_contract(path: Path, *, candidate_root: Path) -> Contract`;`Contract.digest -> str`

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_asset_contract.py`:

```python
import json
from pathlib import Path

import pytest

from acceptance import check_registry as reg
from acceptance.contract import load_contract
from acceptance.primitives import AcceptanceFailure


def _valid(kind: str = "blend_native") -> dict[str, object]:
    checks = [
        {"id": c.id, "impl": c.impl, "order": c.order}
        for c in sorted(reg.checks_for_kind(kind), key=reg.sort_key)
    ]
    return {
        "schema_version": 1,
        "contract_id": "pilot-001",
        "artifact_kind": kind,
        "profile": "static_render",
        "required_isolation_grade": "local-trusted",
        "input": {"path": "asset.blend", "sha256": "0" * 64, "bytes": 1024},
        "export": None,
        "checks": checks,
        "na_check_ids": list(reg.na_check_ids(kind)),
        "warning_allowlist": [],
        "visual_thresholds": {"macos-arm64-workbench-metal-apple_m4":
                              {"fail": 0.016, "failpercent": 1.0}},
        "platform_blocklist": [],
        "texture_colorspace": {"base_color": "sRGB", "data": "Non-Color"},
        "tolerated_unknown_types": [],
        "validator_config_path": None,
        "budget": {"max_triangles": 1000000, "max_materials": 64, "max_images": 64,
                   "max_image_bytes": 33554432, "max_file_bytes": 536870912,
                   "vertex_split_ratio_max": 4.0},
        "projection": {"preserved": [], "transformed": [], "lost": []},
        "tools": [{"id": "blender", "version": "5.2.0", "sha256": "1" * 64,
                   "path": "/Applications/Blender.app/Contents/MacOS/Blender"}],
        "limits": {"cpu_seconds": 600, "address_space_bytes": 8589934592,
                   "open_files": 256, "file_size_bytes": 1073741824},
        "golden": None,
    }


def _write(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_contract_loads_and_has_stable_digest(tmp_path):
    path = _write(tmp_path, _valid())
    first = load_contract(path, candidate_root=tmp_path / "candidate")
    second = load_contract(path, candidate_root=tmp_path / "candidate")
    assert first.digest == second.digest
    assert first.artifact_kind == "blend_native"


def test_unknown_top_level_field_is_rejected(tmp_path):
    bad = _valid() | {"surprise": 1}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_na_set_must_equal_derived_set(tmp_path):
    bad = _valid()
    bad["na_check_ids"] = bad["na_check_ids"][:-1]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_checks_must_be_in_total_order(tmp_path):
    bad = _valid()
    checks = list(bad["checks"])
    checks[0], checks[1] = checks[1], checks[0]
    bad["checks"] = checks
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_contract_inside_candidate_root_is_rejected(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    path = _write(candidate, _valid())
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=candidate)
    assert caught.value.code == "contract_invalid"


def test_interchange_projection_union_must_be_p01_to_p14(tmp_path):
    value = _valid("interchange")
    value["export"] = {"format": "glb", "preset": {}}
    value["projection"] = {"preserved": ["p01_object_count"], "transformed": [], "lost": []}
    path = _write(tmp_path, value)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_missing_top_level_field_is_rejected(tmp_path):
    bad = _valid()
    del bad["contract_id"]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_invalid_artifact_kind_is_rejected(tmp_path):
    bad = _valid()
    bad["artifact_kind"] = "not_a_real_kind"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_invalid_profile_is_rejected(tmp_path):
    bad = _valid()
    bad["profile"] = "not_static_render"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_invalid_required_isolation_grade_is_rejected(tmp_path):
    bad = _valid()
    bad["required_isolation_grade"] = "not_a_real_grade"
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_tools_entry_field_set_is_rejected(tmp_path):
    bad = _valid()
    bad["tools"] = [{"id": "blender", "version": "5.2.0"}]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_tools_sha256_wrong_length_is_rejected(tmp_path):
    bad = _valid()
    bad["tools"] = [{"id": "blender", "version": "5.2.0", "sha256": "abc",
                      "path": "/Applications/Blender.app/Contents/MacOS/Blender"}]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_projection_field_in_multiple_groups_is_rejected(tmp_path):
    bad = _valid()
    bad["projection"] = {"preserved": ["dup_field"], "transformed": ["dup_field"], "lost": []}
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_candidate_root_equal_to_contract_path_is_rejected(tmp_path):
    path = _write(tmp_path, _valid())
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=path)
    assert caught.value.code == "contract_invalid"


def test_symlinked_candidate_root_bypass_is_rejected(tmp_path):
    real_candidate = tmp_path / "real_candidate"
    real_candidate.mkdir()
    link_candidate = tmp_path / "link_candidate"
    link_candidate.symlink_to(real_candidate, target_is_directory=True)
    _write(real_candidate, _valid())
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(link_candidate / "contract.json", candidate_root=link_candidate)
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("alias", [True, 1.0])
def test_schema_version_alias_value_is_rejected(tmp_path, alias):
    bad = _valid()
    bad["schema_version"] = alias
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"


def test_tools_non_dict_entry_is_rejected(tmp_path):
    bad = _valid()
    bad["tools"] = [5]
    path = _write(tmp_path, bad)
    with pytest.raises(AcceptanceFailure) as caught:
        load_contract(path, candidate_root=tmp_path / "candidate")
    assert caught.value.code == "contract_invalid"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --frozen pytest tests/unit/test_asset_contract.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'acceptance.contract'`

- [ ] **Step 3: 实现**

`acceptance/contract.py`:

```python
"""规范 §7.3 contract.json 的封闭加载与 §2.5.1 的 digest。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acceptance import check_registry as reg
from acceptance.canonical import CanonicalError, digest as canonical_digest
from acceptance.primitives import (
    AcceptanceFailure,
    finite_json_float,
    reject_duplicate_keys,
    reject_json_constant,
)

_TOP_LEVEL = frozenset({
    "schema_version", "contract_id", "artifact_kind", "profile",
    "required_isolation_grade", "input", "export", "checks", "na_check_ids",
    "warning_allowlist", "visual_thresholds", "platform_blocklist",
    "texture_colorspace", "tolerated_unknown_types", "validator_config_path",
    "budget", "projection", "tools", "limits", "golden",
})
_KINDS = frozenset({"blend_native", "interchange"})
_GRADES = ("local-trusted", "isolated", "attested")
PROJECTION_FIELDS: tuple[str, ...] = (
    "p01_object_count", "p02_triangle_count", "p03_bbox", "p04_vertex_count",
    "p05_uv_layers", "p06_material_slot_count", "p07_pbr_factors",
    "p08_texture_pixels", "p09_object_identity", "p10_collection_hierarchy",
    "p11_modifier_stack", "p12_custom_props", "p13_unit_system",
    "p14_drivers_constraints",
)


def _fail(message: str) -> AcceptanceFailure:
    return AcceptanceFailure("contract_invalid", message)


@dataclass(frozen=True, slots=True)
class Contract:
    raw: dict[str, Any]
    digest: str

    @property
    def artifact_kind(self) -> str:
        return str(self.raw["artifact_kind"])

    @property
    def na_check_ids(self) -> tuple[str, ...]:
        return tuple(self.raw["na_check_ids"])

    @property
    def required_isolation_grade(self) -> str:
        return str(self.raw["required_isolation_grade"])

    def allowlisted(self, check_id: str, code: str, tool_id: str, version: str) -> bool:
        target = {"check_id": check_id, "warning_code": code,
                  "tool_id": tool_id, "tool_version": version}
        return any(entry == target for entry in self.raw["warning_allowlist"])


def load_contract(path: Path, *, candidate_root: Path) -> Contract:
    resolved = path.resolve(strict=True)
    root = candidate_root.expanduser().resolve()
    if resolved == root or root in resolved.parents:
        raise _fail("contract must live outside the candidate input tree")
    try:
        value = json.loads(
            resolved.read_text(encoding="utf-8"),
            parse_constant=reject_json_constant,
            parse_float=finite_json_float,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (OSError, ValueError) as exc:
        raise _fail(f"unreadable or invalid JSON: {exc}") from exc
    if type(value) is not dict:
        raise _fail("contract must be a JSON object")
    unknown = set(value) - _TOP_LEVEL
    if unknown:
        raise _fail(f"unknown top-level fields: {sorted(unknown)}")
    missing = _TOP_LEVEL - set(value)
    if missing:
        raise _fail(f"missing top-level fields: {sorted(missing)}")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise _fail("schema_version must be 1")
    kind = value["artifact_kind"]
    if kind not in _KINDS:
        raise _fail(f"artifact_kind must be one of {sorted(_KINDS)}")
    if value["profile"] != "static_render":
        raise _fail("profile must be static_render in P0")
    if value["required_isolation_grade"] not in _GRADES:
        raise _fail(f"required_isolation_grade must be one of {list(_GRADES)}")

    expected_specs = sorted(reg.checks_for_kind(kind), key=reg.sort_key)
    declared = value["checks"]
    if type(declared) is not list or len(declared) != len(expected_specs):
        raise _fail("checks must list exactly the registry entries for this kind")
    for entry, spec in zip(declared, expected_specs, strict=True):
        if entry != {"id": spec.id, "impl": spec.impl, "order": spec.order}:
            raise _fail(f"checks entry mismatch or out of order at {spec.id}")

    if type(value["na_check_ids"]) is not list:
        raise _fail("na_check_ids must be a list")
    if list(value["na_check_ids"]) != list(reg.na_check_ids(kind)):
        raise _fail("na_check_ids must equal the derived not-applicable set")

    projection = value["projection"]
    if type(projection) is not dict:
        raise _fail("projection must be an object")
    if set(projection) != {"preserved", "transformed", "lost"}:
        raise _fail("projection must have preserved/transformed/lost")
    union: list[str] = []
    for group in ("preserved", "transformed", "lost"):
        union.extend(projection[group])
    if kind == "interchange" and sorted(union) != sorted(PROJECTION_FIELDS):
        raise _fail("projection union must be exactly p01..p14 for interchange")
    if len(set(union)) != len(union):
        raise _fail("projection field appears in more than one group")

    tools = value["tools"]
    if type(tools) is not list:
        raise _fail("tools must be a list")
    for tool in tools:
        if type(tool) is not dict:
            raise _fail("tools entries must be objects")
        if set(tool) != {"id", "version", "sha256", "path"}:
            raise _fail("tools entries must have id/version/sha256/path")
        if not isinstance(tool["sha256"], str) or len(tool["sha256"]) != 64:
            raise _fail("tools[].sha256 must be a 64-char hex string")

    body = {k: v for k, v in value.items() if k != "contract_digest"}
    try:
        computed = canonical_digest("contract", body)
    except CanonicalError as exc:
        raise _fail(f"contract is not canonicalizable: {exc}") from exc
    return Contract(raw=value, digest=computed)
```

**修复记录(超出本节最初示例代码的范围,后续加固):**
- 候选根包含性检查原先只对合同文件路径 `resolve(strict=True)`,`candidate_root` 仅做
  `expanduser` + 绝对化,未解析符号链接,可被 `candidate_root` 自身是符号链接的情形绕过
  (macOS `/tmp`、`/var` 即是符号链接)。改为 `candidate_root.expanduser().resolve()`
  ——非 strict 的 `resolve()` 既能在路径尚不存在时把能解析的前缀解析掉、把剩余部分原样拼回,
  也能在路径存在(哪怕是符号链接)时完整解析,两种场景都覆盖。
- `schema_version` 原先用 `!= 1` 比较,`bool` 是 `int` 子类(`True == 1`)、`1.0 == 1` 也成立,
  导致别名值被接受。改为 `type(value["schema_version"]) is not int or value["schema_version"] != 1`。
- `na_check_ids`、`projection`、`tools` 原先直接喂给 `list()` / `set()` / `for ... in`,类型错时
  抛裸 `TypeError` 而非 `AcceptanceFailure`。三处都补上 `type(...) is not list/dict` 前置检查,
  `tools` 的每个元素还需 `type(tool) is not dict`。
- `path.resolve(strict=True)` 在合同文件不存在时抛裸 `FileNotFoundError`,需要把它纳入合同加载
  的异常处理块,改为 `contract_invalid` 拒绝。
- Step 1 的测试块与上面 Step 3 的实现同步更新,新增 14 条测试(4 类此前零覆盖的既有 guard、
  candidate_root 恰好等于合同路径的等值分支、以及上述四处修复各一条回归测试),测试总数由
  6 增至 21(含 1 个 `schema_version` 别名值的 parametrize,贡献 2 个 case)。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run --frozen pytest tests/unit/test_asset_contract.py -q`
Expected: `21 passed`

- [ ] **Step 5: 提交**

```bash
git add acceptance/contract.py tests/unit/test_asset_contract.py
git commit -m "feat: add closed contract loading with canonical digest"
```

---

### Task 5: 判定引擎

**Files:**
- Create: `acceptance/decide.py`
- Test: `tests/unit/test_asset_decide.py`

**Interfaces:**
- Consumes: `acceptance.contract.Contract`、`acceptance.check_registry`、`acceptance.failure_codes`
- Produces: `Finding`(dataclass:`code`、`severity`、`pointer`、`offset`、`detail`);`CheckOutcome`(dataclass:`id`、`stage`、`raw_status`、`effective_status`、`accepted`、`tool_id`、`tool_version`、`findings`、`source_truncated`);`aggregate(check_id, findings, *, contract, tool_id, tool_version, source_truncated, terminal) -> CheckOutcome`;`Verdict`(dataclass:`success`、`failure_code`、`failed_check_ids`、`outcomes`);`decide(*, contract, outcomes, actual_files, expected_files, achieved_grade, infra_failures) -> Verdict`

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_asset_decide.py`:

```python
import json
from pathlib import Path

import pytest

from acceptance import check_registry as reg
from acceptance.contract import load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import AcceptanceFailure

CHECK = "r2.material.slots_resolved"


def _contract(tmp_path: Path, allowlist: list[dict[str, str]] | None = None):
    from tests.unit.test_asset_contract import _valid  # 复用同一构造器,避免两份真相
    value = _valid()
    value["warning_allowlist"] = allowlist or []
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "candidate")


def _warn(code: str = "empty_material_slot") -> Finding:
    return Finding(code=code, severity="warning", pointer=None, offset=None, detail=None)


def _err() -> Finding:
    return Finding(code="bad", severity="error", pointer=None, offset=None, detail=None)


def _agg(contract, findings, **kw):
    return aggregate(CHECK, findings, contract=contract, tool_id="acceptance",
                     tool_version="acc-000000000000", source_truncated=False,
                     terminal=None, **kw)


def test_no_findings_is_pass(tmp_path):
    outcome = _agg(_contract(tmp_path), [])
    assert (outcome.raw_status, outcome.effective_status, outcome.accepted) == (
        "Pass", "Pass", False)


def test_error_finding_is_fail(tmp_path):
    outcome = _agg(_contract(tmp_path), [_err()])
    assert outcome.raw_status == "Fail" and outcome.effective_status == "Fail"


def test_unlisted_warning_is_fail(tmp_path):
    outcome = _agg(_contract(tmp_path), [_warn()])
    assert outcome.raw_status == "Warning" and outcome.effective_status == "Fail"


def test_all_warnings_allowlisted_is_pass_and_accepted(tmp_path):
    allow = [{"check_id": CHECK, "warning_code": "empty_material_slot",
              "tool_id": "acceptance", "tool_version": "acc-000000000000"}]
    outcome = _agg(_contract(tmp_path, allow), [_warn()])
    assert (outcome.raw_status, outcome.effective_status, outcome.accepted) == (
        "Pass", "Pass", True)
    assert outcome.findings[0].severity == "warning"
    assert outcome.findings[0].disposition == "AcceptedWarning"


def test_mixed_allowlisted_and_not_is_fail(tmp_path):
    allow = [{"check_id": CHECK, "warning_code": "empty_material_slot",
              "tool_id": "acceptance", "tool_version": "acc-000000000000"}]
    outcome = _agg(_contract(tmp_path, allow), [_warn(), _warn("packed_dependency")])
    assert outcome.raw_status == "Warning" and outcome.effective_status == "Fail"


def test_info_only_does_not_set_accepted(tmp_path):
    info = Finding(code="note", severity="info", pointer=None, offset=None, detail=None)
    outcome = _agg(_contract(tmp_path), [info])
    assert outcome.raw_status == "Pass" and outcome.accepted is False


def test_truncated_beats_error(tmp_path):
    outcome = aggregate(CHECK, [_err()], contract=_contract(tmp_path),
                        tool_id="acceptance", tool_version="acc-000000000000",
                        source_truncated=True, terminal=None)
    assert outcome.raw_status == "Truncated" and outcome.effective_status == "Fail"


@pytest.mark.parametrize("terminal", ["Crash", "Missing"])
def test_terminal_states_beat_findings(tmp_path, terminal):
    outcome = aggregate(CHECK, [], contract=_contract(tmp_path), tool_id=None,
                        tool_version=None, source_truncated=False, terminal=terminal)
    assert outcome.raw_status == terminal and outcome.effective_status == "Fail"


def test_not_applicable_beats_everything(tmp_path):
    contract = _contract(tmp_path)
    na_id = contract.na_check_ids[0]
    outcome = aggregate(na_id, [_err()], contract=contract, tool_id=None,
                        tool_version=None, source_truncated=True,
                        terminal="Missing")
    assert outcome.raw_status == "NotApplicableByContract"
    assert outcome.effective_status == "NotApplicable"


def _all_pass(contract):
    return [aggregate(c.id, [], contract=contract, tool_id=None, tool_version=None,
                      source_truncated=False, terminal=None)
            for c in reg.checks_for_kind(contract.artifact_kind)] + [
        aggregate(i, [], contract=contract, tool_id=None, tool_version=None,
                  source_truncated=False, terminal=None)
        for i in contract.na_check_ids]


def test_all_pass_releases(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.success is True and verdict.failure_code is None


def test_single_failed_check_yields_check_failed(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    outcomes[0] = aggregate(outcomes[0].id, [_err()], contract=contract,
                            tool_id=None, tool_version=None,
                            source_truncated=False, terminal=None)
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.success is False
    assert verdict.failure_code == "check_failed"
    assert verdict.failed_check_ids == [outcomes[0].id]


def test_infra_failure_outranks_check_failed(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    outcomes[0] = aggregate(outcomes[0].id, [_err()], contract=contract,
                            tool_id=None, tool_version=None,
                            source_truncated=False, terminal=None)
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted",
                     infra_failures=["hash_mismatch", "tool_crashed"])
    assert verdict.failure_code == "tool_crashed"   # 优先级更高者胜出


def test_file_set_mismatch_fails(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary", "extra"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "expected_set_mismatch"


def test_insufficient_isolation_fails(tmp_path):
    contract = _contract(tmp_path)
    contract.raw["required_isolation_grade"] = "isolated"
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "isolation_insufficient"


def test_highest_priority_infra_family_wins(tmp_path):
    """规范 §7.2 规则 1:同时触发多个 infra family 时取优先级最高者。"""
    contract = _contract(tmp_path)
    contract.raw["required_isolation_grade"] = "isolated"      # 优先级 12
    outcomes = _all_pass(contract)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=None,
                            tool_version=None, source_truncated=False,
                            terminal="Crash")                   # 优先级 2
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "tool_crashed"


def test_missing_outranks_truncated(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=None,
                            tool_version=None, source_truncated=True, terminal=None)
    outcomes[1] = aggregate(outcomes[1].id, [], contract=contract, tool_id=None,
                            tool_version=None, source_truncated=False,
                            terminal="Missing")
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "evidence_missing"   # 优先级 9 高于 10


def test_forged_not_applicable_is_detected(tmp_path):
    """规范 §2.6 条款 6:子进程自称 N/A 但该 ID 不在合同 N/A 集内。"""
    contract = _contract(tmp_path)
    applicable = reg.checks_for_kind(contract.artifact_kind)[0].id
    verdict = decide(contract=contract, outcomes=_all_pass(contract),
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[],
                     child_declared_na={applicable})
    assert verdict.failure_code == "forged_not_applicable"


def test_not_tested_without_any_failure_is_runner_error(tmp_path):
    contract = _contract(tmp_path)
    outcomes = _all_pass(contract)
    outcomes[0] = aggregate(outcomes[0].id, [], contract=contract, tool_id=None,
                            tool_version=None, source_truncated=False,
                            terminal="NotTested")
    verdict = decide(contract=contract, outcomes=outcomes,
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "runner_internal_error"
    assert verdict.failed_check_ids == []


def test_unknown_check_id_is_rejected(tmp_path):
    with pytest.raises(AcceptanceFailure) as caught:
        aggregate("r9.bogus.id", [], contract=_contract(tmp_path), tool_id=None,
                  tool_version=None, source_truncated=False, terminal=None)
    assert caught.value.code == "expected_set_mismatch"


def test_zero_checks_is_rejected(tmp_path):
    contract = _contract(tmp_path)
    verdict = decide(contract=contract, outcomes=[],
                     actual_files={"summary"}, expected_files={"summary"},
                     achieved_grade="local-trusted", infra_failures=[])
    assert verdict.failure_code == "zero_checks_collected"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --frozen pytest tests/unit/test_asset_decide.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'acceptance.decide'`

- [ ] **Step 3: 实现**

`acceptance/decide.py`:

```python
"""规范 §2.5 与 §2.6 的唯一实现处。其他模块不得复制判定逻辑。"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from acceptance import check_registry as reg
from acceptance import failure_codes as fc
from acceptance.contract import Contract
from acceptance.primitives import AcceptanceFailure

_GRADE_ORDER = {"local-trusted": 0, "isolated": 1, "attested": 2}


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str                 # "error" | "warning" | "info"
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
class Verdict:
    success: bool
    failure_code: str | None
    failed_check_ids: list[str] = field(default_factory=list)
    outcomes: tuple[CheckOutcome, ...] = ()


_SPEC_BY_ID = {spec.id: spec for spec in reg.CHECKS}


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
    """规范 §2.5 第一步与第二步。terminal 为 coordinator 观测到的 Crash/Missing/NotTested。"""
    spec = _SPEC_BY_ID.get(check_id)
    if spec is None:
        raise AcceptanceFailure(
            "expected_set_mismatch", f"unknown check id: {check_id}")
    dispositioned: list[Finding] = []
    for item in findings:
        accepted = (
            item.severity == "warning"
            and tool_id is not None
            and tool_version is not None
            and contract.allowlisted(check_id, item.code, tool_id, tool_version)
        )
        dispositioned.append(
            replace(item, disposition="AcceptedWarning" if accepted else None))

    accepted_flag = False
    if check_id in contract.na_check_ids:
        raw = "NotApplicableByContract"
    elif terminal == "Crash":
        raw = "Crash"
    elif terminal in ("Missing", "NotTested"):
        raw = terminal
    elif source_truncated:
        raw = "Truncated"
    elif any(f.severity == "error" for f in dispositioned):
        raw = "Fail"
    elif any(f.severity == "warning" and f.disposition is None for f in dispositioned):
        raw = "Warning"
    else:
        raw = "Pass"
        warnings = [f for f in dispositioned if f.severity == "warning"]
        accepted_flag = bool(warnings)

    if raw == "Pass":
        effective = "Pass"
    elif raw == "NotApplicableByContract":
        effective = "NotApplicable"
    else:
        effective = "Fail"

    return CheckOutcome(
        id=check_id, stage=spec.stage, raw_status=raw, effective_status=effective,
        accepted=accepted_flag, tool_id=tool_id, tool_version=tool_version,
        findings=tuple(dispositioned), source_truncated=source_truncated,
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
    """规范 §2.6 的十条放行条件。

    infra_failures 由 coordinator 在编排过程中累积(如 stale_result_file、hash_mismatch)。
    child_declared_na 是**子进程在其 result 里自称 N/A 的 check ID 集**,用于条款 6 的
    伪造检出;coordinator 解析 result 文件时填入(本计划尚无 result 解析,故默认空集,
    对应测试见 test_forged_not_applicable_is_detected)。
    """
    child_declared_na = child_declared_na or set()
    # 规范 §7.2 规则 1:**先把全部触发的 infra family 收齐,再取优先级最高的一个**。
    # 不能按源码书写顺序 early-return —— 那样 "isolation 不足 + 子进程崩溃" 会报
    # isolation_insufficient(优先级 12)而不是 tool_crashed(优先级 2)。
    triggered: list[str] = list(infra_failures)

    if achieved_grade not in _GRADE_ORDER:
        raise AcceptanceFailure("contract_invalid", f"unknown grade: {achieved_grade}")
    if _GRADE_ORDER[achieved_grade] < _GRADE_ORDER[contract.required_isolation_grade]:
        triggered.append("isolation_insufficient")

    expected_ids = {c.id for c in reg.checks_for_kind(contract.artifact_kind)}
    expected_ids |= set(contract.na_check_ids)
    actual_ids = [o.id for o in outcomes]
    if not actual_ids:
        triggered.append("zero_checks_collected")
    if (len(set(actual_ids)) != len(actual_ids)
            or set(actual_ids) != expected_ids
            or actual_files != expected_files):
        triggered.append("expected_set_mismatch")

    # 规范 §2.6 条款 6:子进程声明的 N/A 若不在合同 N/A 集内即为伪造。
    if set(child_declared_na) - set(contract.na_check_ids):
        triggered.append("forged_not_applicable")

    # 规范 §2.6 条款 7:Crash/Missing/Truncated 一律阻断,不分 required。
    statuses = {o.raw_status for o in outcomes}
    if "Crash" in statuses:
        triggered.append("tool_crashed")
    if "Missing" in statuses:
        triggered.append("evidence_missing")
    if "Truncated" in statuses:
        triggered.append("evidence_truncated")

    if triggered:
        return Verdict(False, min(triggered, key=fc.family_priority), [], tuple(outcomes))

    # 只有"实际被评估过并被拒"的 check 进 failed_check_ids;NotTested 表示该 stage
    # 根本没跑,把它算作"资产被拒收"会与规范 §7.2 的第一分类冲突(见下)。
    failed = sorted(
        (o.id for o in outcomes
         if o.effective_status == "Fail" and o.raw_status in ("Fail", "Warning")),
        key=lambda i: reg.sort_key(_SPEC_BY_ID[i]),
    )
    if failed:
        return Verdict(False, "check_failed", failed, tuple(outcomes))

    # 无人失败却有 NotTested,说明 coordinator 没跑完自己的计划 —— fail-closed 兜底。
    if any(o.raw_status == "NotTested" for o in outcomes):
        return Verdict(False, "runner_internal_error", [], tuple(outcomes))

    return Verdict(True, None, [], tuple(outcomes))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run --frozen pytest tests/unit/test_asset_decide.py -q`
Expected: `21 passed`

- [ ] **Step 5: 跑完整门禁**

Run: `bash scripts/checks.sh 2>&1 | tail -3`
Expected: `ALL CHECKS PASSED`

- [ ] **Step 6: 提交**

```bash
git add acceptance/decide.py tests/unit/test_asset_decide.py
git commit -m "feat: add the single acceptance decision engine"
```

---

### Task 6: 夹具表计数的机械断言

**Files:**
- Create: `tests/unit/test_asset_spec_counts.py`

**Interfaces:**
- Consumes: `blender_mcp_skill_acceptance_optimized_v3_8.md`(规范文档本身)、`acceptance.check_registry`、`acceptance.failure_codes`
- Produces: 无(纯断言)

**背景:** 规范的计数在三轮审计中连续以同一形态回归,根因是人工重数。本任务把"从表格重算并与正文比对"落成真断言。

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_asset_spec_counts.py`:

```python
"""防止规范文档的计数与其表格脱节(连续三轮回归的根因)。"""
import re
from pathlib import Path

import pytest

from acceptance import check_registry as reg
from acceptance import failure_codes as fc

SPEC = (Path(__file__).resolve().parents[2]
        / "docs" / "acceptance" / "blender_mcp_skill_acceptance_optimized_v3_8.md")


@pytest.fixture(scope="module")
def spec_text() -> str:
    if not SPEC.exists():
        pytest.skip(f"spec document not present: {SPEC.name}")
    return SPEC.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text.split(start)[1].split(end)[0]


def test_registry_table_matches_code(spec_text):
    table = _section(spec_text, "### 7.1 Check registry", "### 7.1.1")
    ids = re.findall(r"^\| `(r[0-5]\.[a-z_]+\.[a-z_]+)` \|", table, re.M)
    assert ids == [c.id for c in reg.CHECKS]


def test_failure_family_table_matches_code(spec_text):
    table = _section(spec_text, "### 7.2 Failure-code", "### 7.3")
    families = re.findall(r"^\| `([a-z_]+)` \| (?:infra|\*\*asset\*\*) \|", table, re.M)
    assert families == list(fc.FAILURE_FAMILIES)


def test_fixture_counts_in_prose_match_the_table(spec_text):
    table = _section(spec_text, "### 8.3 夹具表", "### 8.4")
    rows = [r for r in table.splitlines() if r.startswith("| `")]
    l0 = [r for r in rows if "| L0 |" in r]
    l1 = [r for r in rows if "| L1 |" in r]
    kinds = {k: sum(1 for r in l0 if f"| {k} |" in r)
             for k in ("synthetic", "handcrafted", "generator")}
    claimed = re.search(
        r"L0 计 (\d+) 项\((\d+) synthetic \+ (\d+) handcrafted \+ (\d+) generator\)"
        r",L1 计 (\d+) 项", table)
    assert claimed is not None, "prose count sentence not found"
    assert [int(g) for g in claimed.groups()] == [
        len(l0), kinds["synthetic"], kinds["handcrafted"], kinds["generator"], len(l1)]


def test_every_family_has_at_least_one_fixture(spec_text):
    table = _section(spec_text, "### 8.3 夹具表", "### 8.4")
    rows = [r for r in table.splitlines() if r.startswith("| `")]
    covered: set[str] = set()
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        expected = cells[4] if len(cells) > 4 else ""
        covered |= {f for f in fc.FAILURE_FAMILIES if f"`{f}`" in expected}
    assert set(fc.FAILURE_FAMILIES) - covered == set()
```

- [ ] **Step 2: 运行测试**

Run: `uv run --frozen pytest tests/unit/test_asset_spec_counts.py -q`
Expected: `4 passed`。若任一断言失败,说明规范文档的计数与表格已脱节——**修文档,不要改断言**。

- [ ] **Step 3: 提交**

```bash
git add tests/unit/test_asset_spec_counts.py
git commit -m "test: assert spec counts are derived from its own tables"
```

---

### Task 7: CLI coordinator 骨架与 evidence 写入

**Files:**
- Create: `acceptance/evidence.py`
- Create: `scripts/asset_accept.py`
- Test: `tests/unit/test_asset_accept.py`

**Interfaces:**
- Consumes: 前六个任务的全部产物
- Produces: `acceptance.evidence.summary_document(*, contract, verdict, achieved_grade, platform_key, started_at, completed_at, evidence_manifest, runner_provenance, failure_code=None, error=None) -> dict`;`acceptance.evidence.write_summary(root, document) -> Path`;`scripts/asset_accept.main(argv) -> int`

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_asset_accept.py`:

```python
import json
from pathlib import Path

from scripts import asset_accept
from tests.unit.test_asset_contract import _valid


def _contract_file(tmp_path: Path) -> Path:
    # 合同必须位于候选输入目录**之外**(规范 §1 的合同权属条款,由 load_contract 强制)。
    # 因此输入放在 tmp_path/candidate/,合同留在 tmp_path/。
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(_valid()), encoding="utf-8")
    return path


def _input_path(tmp_path: Path) -> Path:
    candidate = tmp_path / "candidate"
    candidate.mkdir(exist_ok=True)
    return candidate / "asset.blend"


def _run(tmp_path: Path, *extra: str) -> tuple[int, dict[str, object]]:
    root = tmp_path / "evidence"
    code = asset_accept.main([
        "--contract", str(_contract_file(tmp_path)),
        "--input", str(_input_path(tmp_path)),
        "--evidence-root", str(root),
        *extra,
    ])
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    return code, summary


def test_missing_input_is_reported_not_crashed(tmp_path):
    code, summary = _run(tmp_path)
    assert code == 1
    assert summary["success"] is False
    # 输入不存在 → r1.input.digest_recorded 得一条 error finding → check_failed;
    # 其余未接入的 stage 是 NotTested,按 decide() 的定义**不进** failed_check_ids。
    assert summary["failure_code"] == "check_failed"
    assert summary["failed_check_ids"] == ["r1.input.digest_recorded"]
    assert all(c["raw_status"] == "NotTested"
               for c in summary["checks"]
               if c["id"].startswith(("r2.", "r3.", "r4.", "r5."))
               and c["raw_status"] != "NotApplicableByContract")


def test_summary_matches_the_frozen_schema_shape(tmp_path):
    _, summary = _run(tmp_path)
    assert set(summary) == {
        "schema_version", "kind", "success", "contract_id", "contract_digest",
        "artifact_kind", "required_isolation_grade", "achieved_isolation_grade",
        "platform_key", "started_at", "completed_at", "stages", "checks",
        "evidence_manifest", "advisories", "failure_code", "failed_check_ids",
        "error", "runner_provenance",
    }
    assert set(summary["runner_provenance"]) == {
        "acceptance_files", "tools", "input_digest"}
    for check in summary["checks"]:
        assert set(check) == {
            "id", "stage", "raw_status", "effective_status", "accepted",
            "tool_id", "tool_version", "findings", "source_truncated",
            "detail", "metrics"}
    assert summary["schema_version"] == 1
    assert summary["kind"] == "asset_acceptance"


def test_reused_evidence_root_is_rejected_before_any_work(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    marker = root / "old.txt"
    marker.write_text("stale", encoding="utf-8")
    code = asset_accept.main([
        "--contract", str(_contract_file(tmp_path)),
        "--input", str(_input_path(tmp_path)),
        "--evidence-root", str(root),
    ])
    assert code == 1
    assert marker.read_text(encoding="utf-8") == "stale"
    assert not (root / "summary.json").exists()


def test_summary_is_private_regular_file(tmp_path):
    _, _ = _run(tmp_path)
    summary = tmp_path / "evidence" / "summary.json"
    assert summary.is_file()
    assert summary.stat().st_mode & 0o777 == 0o600
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --frozen pytest tests/unit/test_asset_accept.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'scripts.asset_accept'`

- [ ] **Step 3: 实现 evidence 写入**

`acceptance/evidence.py`:

```python
"""规范 §7.3 summary.json 的写入。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from acceptance.contract import Contract
from acceptance.decide import Verdict
from acceptance.primitives import write_json_exclusive


def summary_document(
    *,
    contract: Contract | None,
    verdict: Verdict | None,
    achieved_grade: str,
    platform_key: str,
    started_at: str,
    completed_at: str,
    evidence_manifest: list[dict[str, object]],
    runner_provenance: dict[str, Any],
    failure_code: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if verdict is not None:
        for outcome in verdict.outcomes:
            checks.append({
                "id": outcome.id,
                "stage": outcome.stage,
                "raw_status": outcome.raw_status,
                "effective_status": outcome.effective_status,
                "accepted": outcome.accepted,
                "tool_id": outcome.tool_id,
                "tool_version": outcome.tool_version,
                "findings": [
                    {"code": f.code, "severity": f.severity, "pointer": f.pointer,
                     "offset": f.offset, "disposition": f.disposition,
                     "detail": f.detail}
                    for f in outcome.findings
                ],
                "source_truncated": outcome.source_truncated,
                "detail": outcome.findings[0].detail if outcome.findings else None,
                "metrics": None,
            })
    success = bool(verdict is not None and verdict.success)
    return {
        "schema_version": 1,
        "kind": "asset_acceptance",
        "success": success,
        "contract_id": None if contract is None else contract.raw["contract_id"],
        "contract_digest": None if contract is None else contract.digest,
        "artifact_kind": None if contract is None else contract.artifact_kind,
        "required_isolation_grade": (
            None if contract is None else contract.required_isolation_grade),
        "achieved_isolation_grade": achieved_grade,
        "platform_key": platform_key,
        "started_at": started_at,
        "completed_at": completed_at,
        "stages": {},
        "checks": checks,
        "evidence_manifest": evidence_manifest,
        "advisories": [],
        "failure_code": (
            failure_code if verdict is None else verdict.failure_code),
        "failed_check_ids": [] if verdict is None else verdict.failed_check_ids,
        "error": error,
        "runner_provenance": runner_provenance,
    }


def write_summary(root: Path, document: dict[str, Any]) -> Path:
    path = root / "summary.json"
    write_json_exclusive(path, document)
    return path
```

- [ ] **Step 4: 实现 CLI**

`scripts/asset_accept.py`:

```python
#!/usr/bin/env python3
"""资产验收 coordinator(规范 §7)。P0 只支持 blend_native 与 interchange/glb。"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import sys
from pathlib import Path

import platform

from acceptance import check_registry as reg
from acceptance import evidence
from acceptance.contract import load_contract
from acceptance.decide import Finding, aggregate, decide
from acceptance.primitives import (
    AcceptanceFailure,
    create_private_directory,
    normalise_new_root,
)

ROOT = Path(__file__).resolve().parents[1]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    return parser.parse_args(argv)


def _acceptance_provenance() -> tuple[str, list[dict[str, str]]]:
    """规范 §7.4 的 `acceptance` 工具行:覆盖 acceptance/ 全部 .py/.json 加本 CLI。"""
    package = ROOT / "acceptance"
    entries = sorted(
        list(package.rglob("*.py")) + list(package.rglob("*.json"))
        + [ROOT / "scripts" / "asset_accept.py"])
    accumulator = hashlib.sha256()
    files: list[dict[str, str]] = []
    for path in entries:
        rel = path.relative_to(ROOT).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": rel, "sha256": file_hash})
        accumulator.update(f"{rel}\n{file_hash}\n".encode("utf-8"))
    return "acc-" + accumulator.hexdigest()[:12], files


def _input_digest(path: Path) -> str:
    """输入不存在时返回 64 个 0,使 provenance 形状恒定,判定交给 R1 的 check。"""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return "0" * 64


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    started_at = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        root = normalise_new_root(args.evidence_root, ROOT)
    except AcceptanceFailure as exc:
        print(f"ASSET_ACCEPT_FAIL {exc.code}: {exc}", file=sys.stderr)
        return 1
    try:
        create_private_directory(root)
    except Exception as exc:                      # noqa: BLE001
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1

    version, files = _acceptance_provenance()
    provenance = {
        "acceptance_files": files,
        "tools": [{"id": "acceptance", "version": version},
                  {"id": "python", "version": platform.python_version()}],
        "input_digest": _input_digest(args.input),
    }
    contract = None
    verdict = None
    failure_code = None
    error = None
    try:
        contract = load_contract(args.contract, candidate_root=args.input.parent)
        # P0 骨架:R1 的输入存在性是第一条真实判定,其余 stage 由后续计划接入。
        findings: list[Finding] = []
        if not args.input.is_file():
            findings.append(Finding(code="input_missing", severity="error",
                                    detail=f"input is not a regular file: {args.input}"))
        outcomes = []
        wired = {"r1.input.digest_recorded"}     # 本计划接入的唯一真实判定
        for spec in reg.CHECKS:
            if spec.id in contract.na_check_ids:
                terminal = None                  # aggregate 会先命中 N/A 分支
            elif spec.id in wired:
                terminal = None
            else:
                terminal = "NotTested"           # 未接入的 stage:规范 §2.4 的唯一产生点
            outcomes.append(aggregate(
                spec.id,
                findings if spec.id in wired else [],
                contract=contract, tool_id="acceptance",
                tool_version=version,
                source_truncated=False, terminal=terminal))
        verdict = decide(contract=contract, outcomes=outcomes,
                         actual_files=set(), expected_files=set(),
                         achieved_grade="local-trusted", infra_failures=[])
    except AcceptanceFailure as exc:
        failure_code = exc.code
        error = str(exc)
    except Exception as exc:                      # noqa: BLE001 - fail-closed 兜底
        failure_code = "runner_internal_error"
        error = f"{type(exc).__name__}: {exc}"

    document = evidence.summary_document(
        contract=contract, verdict=verdict, achieved_grade="local-trusted",
        # P0 不渲染,故 platform_key 的后三段(engine/backend/vendor)填 none;
        # Plan B 接入 render_views 后由 gpu.init() 探测填真值(规范 §5.3)。
        platform_key=f"{platform.system().lower()}-{platform.machine().lower()}-none-none-none",
        started_at=started_at,
        completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
        evidence_manifest=[], runner_provenance=provenance,
        failure_code=failure_code, error=error)
    try:
        evidence.write_summary(root, document)
    except Exception as exc:                      # noqa: BLE001 - 连 summary 都写不出
        print(f"ASSET_ACCEPT_FAIL runner_internal_error: {exc}", file=sys.stderr)
        return 1
    status = "OK" if document["success"] else f"FAIL {document['failure_code']}"
    print(f"ASSET_ACCEPT_{status} {root / 'summary.json'}")
    return 0 if document["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run --frozen pytest tests/unit/test_asset_accept.py -q`
Expected: `4 passed`

- [ ] **Step 6: 跑完整门禁**

Run: `bash scripts/checks.sh 2>&1 | tail -3`
Expected: `ALL CHECKS PASSED`;`acceptance/` 已被 ruff 与 mypy strict 检查(Task 1 的效果)。

- [ ] **Step 7: 提交**

```bash
git add acceptance/evidence.py scripts/asset_accept.py tests/unit/test_asset_accept.py
git commit -m "feat: add asset acceptance coordinator skeleton with fail-closed summary"
```

---

### Task 8: 接线 9 条 coordinator-owned check(R0 / R1 / R5)

**Files:**
- Modify: `scripts/asset_accept.py`(把 `wired` 从 1 条扩到 9 条)
- Create: `acceptance/stages.py`
- Test: `tests/unit/test_asset_stages.py`

**Interfaces:**
- Consumes: `acceptance.contract.Contract`、`acceptance.decide.Finding`
- Produces: `run_r0(contract, *, tools_present) -> dict[str, list[Finding]]`;`run_r1(contract, input_path) -> dict[str, list[Finding]]`;`run_r5(contract, *, evidence_manifest, recomputed_digest) -> dict[str, list[Finding]]`

**背景:** 规范 §7.1 中 `writer == coordinator` 且不依赖 Blender 或外部工具的恰好 9 条(R0×3 + R1×3 + R5×3),全部落在本计划范围内。Task 7 只接了其中 1 条,其余打成 `NotTested`,导致**无法构造一次真正的全绿放行**——测试只能验证"全是 NotTested 就全 Fail"。本任务把它们接上,使判定核心具备端到端的正向路径。

- [ ] **Step 1: 写失败的测试**

`tests/unit/test_asset_stages.py`:

```python
import json
from pathlib import Path

from acceptance import stages
from acceptance.contract import load_contract
from tests.unit.test_asset_contract import _valid


def _contract(tmp_path: Path):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(_valid()), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "candidate")


def test_r0_all_pass_when_tools_present(tmp_path):
    findings = stages.run_r0(_contract(tmp_path), tools_present={"blender"})
    assert set(findings) == {"r0.contract.schema_closed", "r0.contract.tools_locked",
                             "r0.contract.na_set_declared"}
    assert all(v == [] for v in findings.values())


def test_r0_reports_missing_tool(tmp_path):
    findings = stages.run_r0(_contract(tmp_path), tools_present=set())
    assert [f.code for f in findings["r0.contract.tools_locked"]] == ["tool_not_installed"]
    assert findings["r0.contract.tools_locked"][0].severity == "error"


def test_r1_passes_for_a_real_regular_file(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    asset = candidate / "asset.blend"
    asset.write_bytes(b"x" * 16)
    findings = stages.run_r1(_contract(tmp_path), asset)
    assert all(v == [] for v in findings.values())


def test_r1_rejects_a_symlink(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    real = candidate / "real.blend"
    real.write_bytes(b"x")
    link = candidate / "asset.blend"
    link.symlink_to(real)
    findings = stages.run_r1(_contract(tmp_path), link)
    assert [f.code for f in findings["r1.input.no_link_or_device"]] == ["input_is_symlink"]


def test_r1_rejects_oversized_input(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    asset = candidate / "asset.blend"
    asset.write_bytes(b"x" * 32)
    contract = _contract(tmp_path)
    contract.raw["budget"]["max_file_bytes"] = 16
    findings = stages.run_r1(contract, asset)
    assert [f.code for f in findings["r1.input.size_within_limit"]] == ["input_too_large"]


def test_r5_detects_digest_drift(tmp_path):
    contract = _contract(tmp_path)
    findings = stages.run_r5(contract, evidence_manifest=[], recomputed_digest="deadbeef")
    assert [f.code for f in findings["r5.contract.digest_stable"]] == ["contract_digest_drift"]


def test_r5_detects_hash_mismatch(tmp_path):
    contract = _contract(tmp_path)
    manifest = [{"id": "summary", "path": "summary.json", "bytes": 1,
                 "sha256": "a" * 64, "actual_sha256": "b" * 64}]
    findings = stages.run_r5(contract, evidence_manifest=manifest,
                             recomputed_digest=contract.digest)
    assert [f.code for f in findings["r5.evidence.hashes_match"]] == ["evidence_hash_drift"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run --frozen pytest tests/unit/test_asset_stages.py -q`
Expected: FAIL,`ModuleNotFoundError: No module named 'acceptance.stages'`

- [ ] **Step 3: 实现**

`acceptance/stages.py`:

```python
"""coordinator 自算的三个 stage(规范 §7.1 中 writer == coordinator 且不依赖外部进程的部分)。"""
from __future__ import annotations

import stat
from pathlib import Path
from typing import Any

from acceptance.contract import Contract
from acceptance.decide import Finding


def _error(code: str, detail: str) -> Finding:
    return Finding(code=code, severity="error", detail=detail)


def run_r0(contract: Contract, *, tools_present: set[str]) -> dict[str, list[Finding]]:
    """schema 与 N/A 集在 load_contract 已强制,故此处只补工具存在性。"""
    missing = [tool["id"] for tool in contract.raw["tools"]
               if tool["id"] not in tools_present]
    return {
        "r0.contract.schema_closed": [],
        "r0.contract.tools_locked": [
            _error("tool_not_installed", f"locked tools not present: {sorted(missing)}")
        ] if missing else [],
        "r0.contract.na_set_declared": [],
    }


def run_r1(contract: Contract, input_path: Path) -> dict[str, list[Finding]]:
    digest_findings: list[Finding] = []
    link_findings: list[Finding] = []
    size_findings: list[Finding] = []
    try:
        info = input_path.lstat()
    except OSError as exc:
        digest_findings.append(_error("input_missing", f"cannot stat input: {exc}"))
        return {"r1.input.digest_recorded": digest_findings,
                "r1.input.no_link_or_device": link_findings,
                "r1.input.size_within_limit": size_findings}
    if stat.S_ISLNK(info.st_mode):
        link_findings.append(_error("input_is_symlink", str(input_path)))
    elif not stat.S_ISREG(info.st_mode):
        link_findings.append(_error("input_not_regular_file", str(input_path)))
    limit = int(contract.raw["budget"]["max_file_bytes"])
    if info.st_size > limit:
        size_findings.append(
            _error("input_too_large", f"{info.st_size} bytes exceeds {limit}"))
    return {"r1.input.digest_recorded": digest_findings,
            "r1.input.no_link_or_device": link_findings,
            "r1.input.size_within_limit": size_findings}


def run_r5(
    contract: Contract,
    *,
    evidence_manifest: list[dict[str, Any]],
    recomputed_digest: str,
) -> dict[str, list[Finding]]:
    drift = [
        entry["id"] for entry in evidence_manifest
        if "actual_sha256" in entry and entry["actual_sha256"] != entry["sha256"]
    ]
    return {
        "r5.evidence.manifest_closed": [],
        "r5.evidence.hashes_match": [
            _error("evidence_hash_drift", f"hash drift on: {sorted(drift)}")
        ] if drift else [],
        "r5.contract.digest_stable": [
            _error("contract_digest_drift",
                   f"expected {contract.digest}, recomputed {recomputed_digest}")
        ] if recomputed_digest != contract.digest else [],
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run --frozen pytest tests/unit/test_asset_stages.py -q`
Expected: `7 passed`

- [ ] **Step 5: 把 9 条接进 coordinator**

在 `scripts/asset_accept.py` 的 `main()` 里,把原来的单条 `wired` 替换为:

```python
        from acceptance import stages

        collected: dict[str, list[Finding]] = {}
        collected.update(stages.run_r0(contract, tools_present=_present_tools(contract)))
        collected.update(stages.run_r1(contract, args.input))
        collected.update(stages.run_r5(
            contract, evidence_manifest=[], recomputed_digest=contract.digest))
        wired = set(collected)

        outcomes = []
        for spec in reg.CHECKS:
            if spec.id in contract.na_check_ids:
                terminal = None
            elif spec.id in wired:
                terminal = None
            else:
                terminal = "NotTested"
            outcomes.append(aggregate(
                spec.id, collected.get(spec.id, []),
                contract=contract, tool_id="acceptance", tool_version=version,
                source_truncated=False, terminal=terminal))
```

并在模块级加辅助函数:

```python
def _present_tools(contract: Contract) -> set[str]:
    """按锁定表逐个探测:acceptance 自身恒在;其余看 path 是否为可执行文件。"""
    present = {"acceptance"}
    for tool in contract.raw["tools"]:
        path = Path(str(tool["path"]))
        if tool["id"] == "python" or (path.is_file() and os.access(path, os.X_OK)):
            present.add(str(tool["id"]))
    return present
```

对应补上 `import os` 与 `from acceptance.contract import Contract`、`from acceptance.decide import Finding`。

- [ ] **Step 6: 更新 Task 7 的测试期望**

`tests/unit/test_asset_accept.py` 的 `test_missing_input_is_reported_not_crashed` 现在会同时命中 `r1.input.digest_recorded`;把断言改为:

```python
    assert summary["failure_code"] == "check_failed"
    assert "r1.input.digest_recorded" in summary["failed_check_ids"]
```

并新增一条正向测试:

```python
def test_real_input_reaches_r2_not_tested_boundary(tmp_path):
    asset = _input_path(tmp_path)
    asset.write_bytes(b"BLENDER-fake")
    _, summary = _run(tmp_path)
    r1 = [c for c in summary["checks"] if c["id"].startswith("r1.")]
    assert all(c["effective_status"] == "Pass" for c in r1)
    # R2 起尚未接入 → NotTested → 整体仍 fail-closed
    assert summary["failure_code"] in {"check_failed", "runner_internal_error"}
```

- [ ] **Step 7: 跑完整门禁并提交**

Run: `bash scripts/checks.sh 2>&1 | tail -3`
Expected: `ALL CHECKS PASSED`

```bash
git add acceptance/stages.py scripts/asset_accept.py tests/unit/test_asset_stages.py tests/unit/test_asset_accept.py
git commit -m "feat: wire the nine coordinator-owned R0/R1/R5 checks"
```

---

## 审计与实测记录

本计划经一轮对抗性审计(3 High / 9 Medium / 8 Low,审计员把每段代码抽出实跑),**全部处置**;随后本人再次抽取全部代码块实跑复验。

### 三个 High 的处置

| 发现 | 验证 | 处置 |
|---|---|---|
| **H1** Task 7 的 `test_missing_input_is_reported_not_crashed` 实测 FAILED | 成立:合同写在 `tmp_path`、输入也在 `tmp_path`,`load_contract` 的"合同须在候选目录外"守卫立刻抛 `contract_invalid`,decide 路径根本没跑;另一条测试只断言权限,侥幸绿从而掩盖了它 | 输入移入 `tmp_path/candidate/`;新增 `test_summary_matches_the_frozen_schema_shape` 断言 summary 形状,不再有"侥幸绿" |
| **H2** `_number()` 不是 RFC 8785,且原注释指错方向 | 成立且严重:审计用 node 取基准,`1e-5` 经 `repr` 得 `1e-05` 而 ES 得 `0.00001`、`1e-6` 同理——**这两个值正是规范 §6 的默认容差与 §4.2 的量化步长**;而原注释宣称"分歧在 1e21",实测 `String(1e21)` 与 Python 完全一致 | 按 ES `Number::toString` 完整实现(定点与科学计数的切换阈值、指数不补零、整数分支用最短往返十进制);新增 10 条参数化断言把 node 基准值钉死,实测 18/18 与 node 一致 |
| **H3** `decide()` 违反规范 §7.2 规则 1 | 成立:只对传入的 `infra_failures` 取了 `min(priority)`,自己产生的 6 个 family 按**源码书写顺序** early-return。实测三组均返回优先级更低者(如 isolation 优先级 12 压过 Crash 的 2) | 改为把全部触发的 family 收进一个 list 再统一 `min(..., key=family_priority)`;新增 `test_highest_priority_infra_family_wins` 与 `test_missing_outranks_truncated` |

### 其余处置要点

`M1` 搬迁后 3 个 `F401` 会让 Step 6 必红,故 Step 3 明写要删哪三个导入。`M2` Step 3 原文自相矛盾——"调用点改新名"会绕过 `monkeypatch.setattr(acceptance, "_run_command", ...)`,已定为**内部调用点一律保持旧私有名**。`M3` `_AcceptanceFailure` 是死赋值(全仓零命中),删除。`M4` `forged_not_applicable` 分支不可达,`decide()` 增 `child_declared_na` 形参并配测试,同时在边界章节标注"填充它需要 result 解析,随 Plan B 落地"。`M5` `NotTested` 不应算作"资产被拒收",`failed_check_ids` 只收 `raw_status` 属于 `Fail`/`Warning` 的,纯 NotTested 走 `runner_internal_error`。`M6` 未知 check id 与未知 grade 原会抛裸 `KeyError`,改抛带 code 的 `AcceptanceFailure`。`M7` summary 不符规范 §7.3,补 `detail`/`metrics`、`runner_provenance` 改为冻结的三字段形状、`platform_key` 填真值。`M8` Interfaces 与实现不符,改 Interfaces。`M9` 9 条 coordinator-only check 无人认领,**新增 Task 8** 接线,使判定核心具备正向路径。`L1` 补 `\b` 与 `\f` 短转义。`L2` 补域前缀断言与 `subprocess` 跨进程复算测试。`L4` 补 `run_command` 完整函数体。`L5` 补 `import math` 与"相互引用一并改名"。`L7` 把 `create_private_directory` 与 `write_summary` 纳入 fail-closed 包裹。`L8` 说明基线数字只在 Task 1 内有效。

`L3`(合同值校验弱)与 `L6`(`smoke/` 内另有 JSON 三件套副本)记录在案但不在本计划处置:前者属规范 §7.3 的 schema 深度问题,后者规范 §7.7 未要求本轮合并。

### 复验实测(修复后)

在 scratchpad 中按行号抽出全部代码块、建真实文件树后执行(仓库工作树全程未被写入):

```text
test_asset_canonical      22 passed        test_asset_decide     21 passed
test_asset_registry        7 passed        test_asset_stages      7 passed
test_asset_contract        6 passed        test_asset_accept      4 passed
test_asset_spec_counts     4 passed(对真实 v3.8 规范文档)

ruff  check --config pyproject.toml   ->  All checks passed!
mypy  --strict --python-version 3.13  ->  Success: no issues found in 6 source files
```

合计 **71 passed**,与各任务 Step 声明的期望值逐一相符。

---

## 本计划的边界与后续

**本计划交付的是可独立运行、可完整测试的判定核心**:合同能被封闭校验、摘要按 RFC 8785 可跨进程复算、判定引擎实现规范 §2.5 三步式与 §2.6 全部放行条件、9 条 coordinator-owned check(R0/R1/R5)真实接线、coordinator 在任何异常下都写出 fail-closed 的 `summary.json`。它**不包含**任何 Blender 交互。

**两处已知的部分实现,已在代码注释与此处双重标注**:

1. **条款 6 的伪造检出**:`decide()` 已接受 `child_declared_na` 形参并有对应测试,但**填充它需要解析子进程的 `result.json`**——result 解析随 Plan B 落地。在此之前该形参恒为空集,即条款 6 的检出能力尚未真正生效。
2. **`platform_key` 的后三段**:P0 不渲染,故 engine/backend/vendor 三段填 `none`;Plan B 接入 `render_views` 后按规范 §5.3 用 `gpu.init()` 探测填真值。

**后续计划(需另行编写,依赖本计划的接口)**:

1. **Plan B — Blender 侧探针**:`acceptance/blender_scripts/` 的 inspector / export_glb / reopen_probe / reimport_probe / render_views,以及 §4.1 manifest 的实际采集;依赖本计划的 `check_registry` 与 `Finding` 结构。
2. **Plan C — 外部工具接入**:`glb_budget.py`、`pixel.py`(oiiotool)、glTF-Validator 报告解析;前置条件是把两个工具装好并把实测版本/hash 填入规范 §7.4。
3. **Plan D — 夹具与 E2E**:`tests/asset_fixtures/` 的 42 个 L0 夹具与 `ASSET_E2E=1` 入口;其中 5 个待实测项(规范 §5.2 的登记表)必须先完成实测并把结论写回规范。
