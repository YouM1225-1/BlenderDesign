# 安装升级与旧版本自动清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每次安装或注册升级通过对应验证后，自动删除可证明归属且空闲的历史 runtime/extension recovery 和目标插件历史缓存，保留新版及全部用户配置与审计证据。

**Architecture:** 使用独立 schema v1 升级 journal 串联现有注册、安装和验证 adapter；复用 SafeRoot、条件删除和原子 JSON 持久化。清理单独提交，不进入安装失败回滚的异常范围；所有变更固定按 marketplace → state 获取锁，版本使用锁按树的 device/inode 标识。完整工作流由同进程编排器跨注册与安装持有旧 runtime 的排他使用锁，等待用户启动 Blender 期间释放变更锁；finalize 在锁内只做一次完整现场验证，之后重验绑定快照。

**Tech Stack:** Python 3.13、标准库 fcntl/json/pathlib、现有 Blender/Codex/uv adapter、pytest、Ruff；不增加数据库、服务或第三方依赖。

## Global Constraints

- 设计依据：[安装升级与旧版本自动清理设计](../specs/2026-09-08-installer-upgrade-cleanup-design.md)。
- 仅删除历史托管 runtime recovery、历史托管 extension recovery、`official-blender-mcp/blender-mcp-installer/<version>` 历史缓存。
- 保留当前 runtime、扩展、插件缓存，用户偏好和 Codex 配置及其备份，历史受审 projection，安装 receipt、注册恢复证据和清理日志。
- `inspect`、`verify`、`rollback` 不创建清理任务；`verify` 不删除文件。完整安装要求现场 `verify_live`，仅注册不要求 Blender。
- receipt schema v1 不变；升级 journal 使用独立 schema v1，目录 0700、文件 0600。未知 schema 不猜测、不清理。
- 缺失历史来源、内容漂移、未知进程占用、恢复引用、符号链接、非本用户所有或不安全权限均保留并报告。
- 成功安装与清理失败分开报告；存在候选未删除或未证明归属的发现结果时，`all_old_versions_removed` 必须为 false。
- 锁只约束协作入口。不得将一次 `lsof` 空输出或用户口头“已关闭”当作全系统无人使用证明。
- 旧 runtime 的固定路径切换前必须排他占用；inode lease 仅解决身份随 rename 稳定的问题，不能让运行中旧 Python 的 `__file__`/`sys.path` 自动安全。
- launcher 先用托管树外、已探测的 bootstrap Python 获取共享 lease，再 exec runtime Python；不能先启动旧 runtime Python 再加锁。
- 第一代无 lease 安装只允许在外部终端的维护交接中迁移；相关 Codex 桌面/CLI 客户端及托管 MCP 进程须完成有正向身份记录的停止交接。没有证据返回 `legacy_handoff_required`，不修改目标。此计划编写阶段不关闭当前用户应用。
- 不更改上游 wheel、扩展 zip 或共享 uv 缓存；只修改分发安装器及其测试/文档。
- 任务中的 commit 步骤只在执行阶段已有用户提交授权时进行。编写本计划不执行实现、安装、删除、提交或推送。

## 文件与依赖图

| 文件 | 责任 |
| --- | --- |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_state.py` | 独立 schema、revision、原子 journal 写入/恢复 |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_locks.py` | 固定锁序、稳定 inode 共享/排他使用锁 |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_registration.py` | 实际 Codex JSON 身份与完整缓存内容验证 |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_cleanup.py` | 删除边界、逐候选续删、回滚失效与结果 |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_discovery.py` | receipt ancestry、历史注册与候选归属、恢复引用 |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py` | install journal 关联、完整 finalize、前置回滚守卫 |
| `plugins/blender-mcp-installer/scripts/blender_mcp_installer/runtime.py` | launcher 的外部 bootstrap 与 runtime lease 协议标记 |
| `plugins/blender-mcp-installer/scripts/project_marketplace.py` | 首次变更前 journal、仅注册 finalize、完整工作流编排 |
| `plugins/blender-mcp-installer/scripts/install.py` | 最早获取脚本目录使用锁后才导入 installer 模块 |
| `plugins/blender-mcp-installer/.blender-mcp-usage-v1` | 新缓存参与 inode-v1 协作入口协议的内容标记 |
| `tests/distribution/test_upgrade_core.py` | journal/删除/锁/崩溃与真实形状 Codex JSON 回归 |
| `tests/distribution/test_cli.py`、`test_runtime.py`、`fake_host.py` | 与真实入口一致的安装/注册/launcher 接线回归 |
| `scripts/checks.sh`、`tests/distribution/test_bundle.py` | 固定版完整性与远端最新性分开报告 |
| 安装技能 `SKILL.md`、`references/workflow.md`、`references/recovery.md`（若不存在则不创建） | 同步完整、仅注册、finalize 和有限恢复能力 |

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7。核心模块的完整文本在每个 Task 的代码块中；不得用新抽象替换已有 adapter。

---

### Task 1: 独立升级 journal 与故障恢复

**Files:**
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_state.py`
- Create: `tests/distribution/test_upgrade_state.py`

**Interfaces:**
- Consumes: `write_atomic_json(reference: TargetRef, expected: FileImage, value: dict, install_id: UUID, *, fault) -> FileImage`；`load_atomic_json_pair(reference: TargetRef, install_id: UUID) -> tuple[object | None, object | None]`；`reconcile_atomic_json` 保留现有参数。
- Produces: `UpgradeRoots(home: Path, codex_home: Path)`；`new_record(roots: UpgradeRoots, mode: str, desired: dict[str, str], workflow_id: str | None = None) -> dict[str, Any]`；`load_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str, *, recover: bool = False) -> dict[str, Any] | None`；`update_record(state: SafeRoot, roots: UpgradeRoots, old: dict[str, Any], *, fault: Any = None, **changes: Any) -> dict[str, Any]`；`record_ids(state: SafeRoot) -> tuple[str, ...]`；`load_any_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str, *, recover: bool = False) -> dict[str, Any] | None`（同 HOME 的只读枚举按记录自身 CODEX_HOME 校验，候选发现仍显式限制当前 CODEX_HOME）。

- [ ] **Step 1: 写入独立 state 回归，并确认模块缺失时失败。**

```python
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[2] / 'plugins/blender-mcp-installer/scripts'))
from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_state import UpgradeRoots,new_record,state_root,save_record,load_record,update_record,validate_record

def test_state_rejects_unknown_schema_and_persists_revision(tmp_path):
    home=tmp_path/'home';codex=tmp_path/'codex'
    home.mkdir(mode=0o700);codex.mkdir(mode=0o700)
    roots=UpgradeRoots(home,codex)
    desired={'commit':'a'*40,'manifest_sha256':'b'*64,'bundle_version':'1.0.0',
             'plugin_version':'2','projection':str(roots.projections/('a'*40))}
    doc=new_record(roots,'register',desired)
    with pytest.raises(InstallerError): validate_record(dict(doc,schema_version=2),roots)
    with state_root(roots) as state:
        saved=save_record(state,roots,None,doc)
        updated=update_record(state,roots,saved,status='cancelled')
        assert updated['revision']==1 and load_record(state,roots,doc['id'])==updated
```

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_state.py -q
```

预期：新模块未创建时报 ModuleNotFoundError；Step 2 实现后该单独文件通过。

- [ ] **Step 2: 创建下面完整模块。**

```python
from __future__ import annotations

import copy
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Iterator
from uuid import UUID, uuid4

from blender_mcp_installer.filesystem import (
    InstallerError, NoOpFaultInjector, SafeRoot, TargetRef, capture_file,
    load_atomic_json_pair, reconcile_atomic_json, write_atomic_json,
)
from blender_mcp_installer.model import FileImage, ImageState, TreeImage

VERSION = re.compile(r"[A-Za-z0-9.+-]+\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
STATUSES = {"awaiting_verification", "cleanup_pending", "complete", "cancelled"}
KINDS = {"runtime_recovery", "extension_recovery", "plugin_cache"}
ROW_STATES = {"pending", "deferred_in_use", "conflict", "removed"}


def uuid_text(value: object) -> str:
    if type(value) is not str:
        raise InstallerError("invalid workflow UUID")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise InstallerError("invalid workflow UUID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise InstallerError("invalid workflow UUID")
    return value


def absolute(value: object) -> Path:
    if type(value) is not str:
        raise InstallerError("invalid absolute path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        raise InstallerError("invalid absolute path")
    return path


def exact(value: object, keys: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(keys.split()):
        raise InstallerError("invalid upgrade schema")
    return value


@dataclass(frozen=True)
class UpgradeRoots:
    home: Path
    codex_home: Path

    @property
    def state(self) -> Path:
        return self.home / ".local/state/blender-mcp-installer"

    @property
    def projections(self) -> Path:
        return self.home / ".local/share/blender-mcp-installer/marketplaces/official-blender-mcp"

    @property
    def caches(self) -> Path:
        return self.codex_home / "plugins/cache/official-blender-mcp/blender-mcp-installer"

    def __post_init__(self) -> None:
        absolute(str(self.home))
        absolute(str(self.codex_home))


def _validate_record(raw: object, roots: UpgradeRoots) -> dict[str, Any]:
    doc = exact(raw, "schema_version id revision mode status home codex_home desired profile "
                "registration install_id candidates findings verification retired_receipts "
                "retired_registrations")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise InstallerError("unsupported upgrade schema")
    uuid_text(doc["id"])
    if type(doc["revision"]) is not int or doc["revision"] < 0:
        raise InstallerError("invalid upgrade revision")
    if doc["mode"] not in {"install", "register"} or doc["status"] not in STATUSES:
        raise InstallerError("invalid upgrade mode or status")
    if (doc["home"], doc["codex_home"]) != (str(roots.home), str(roots.codex_home)):
        raise InstallerError("upgrade host mismatch")
    wanted = exact(doc["desired"], "commit manifest_sha256 bundle_version plugin_version projection")
    if (type(wanted["commit"]) is not str or not COMMIT.fullmatch(wanted["commit"])
            or type(wanted["manifest_sha256"]) is not str
            or not HASH.fullmatch(wanted["manifest_sha256"])
            or type(wanted["bundle_version"]) is not str or not wanted["bundle_version"]
            or type(wanted["plugin_version"]) is not str
            or not VERSION.fullmatch(wanted["plugin_version"])
            or wanted["plugin_version"] in {".", ".."}):
        raise InstallerError("invalid upgrade release identity")
    if wanted["projection"] != str(roots.projections / wanted["commit"]):
        raise InstallerError("upgrade projection mismatch")
    if doc["profile"] is not None:
        profile = exact(doc["profile"], "executable architecture version resources config extensions")
        for key in ("executable", "resources", "config", "extensions"):
            absolute(profile[key])
        if not all(type(profile[key]) is str and profile[key] for key in ("architecture", "version")):
            raise InstallerError("invalid Blender identity")
        if not all(Path(profile[key]).is_relative_to(Path(profile["resources"]))
                   for key in ("config", "extensions")):
            raise InstallerError("invalid Blender profile boundary")
    if doc["registration"] is not None:
        registration = exact(doc["registration"], "id state")
        uuid_text(registration["id"])
        if registration["state"] not in {"prepared", "registered", "failed", "restored"}:
            raise InstallerError("invalid registration state")
    if doc["install_id"] is not None:
        uuid_text(doc["install_id"])
    if doc["mode"] == "register" and (doc["profile"] is not None or doc["install_id"] is not None):
        raise InstallerError("registration workflow contains Blender state")
    verification = exact(doc["verification"], "registration live")
    if any(value not in {"not_run", "passed", "failed"} for value in verification.values()):
        raise InstallerError("invalid verification state")
    if type(doc["candidates"]) is not list or type(doc["findings"]) is not list:
        raise InstallerError("invalid upgrade collections")
    seen: set[str] = set()
    for row in doc["candidates"]:
        row = exact(row, "key kind owner version expected proofs content_source content_sha256 "
                    "lease_known state reason")
        if row["kind"] not in KINDS or row["state"] not in ROW_STATES:
            raise InstallerError("invalid cleanup candidate")
        if type(row["key"]) is not str or row["key"] in seen:
            raise InstallerError("duplicate cleanup candidate")
        seen.add(row["key"])
        uuid_text(row["owner"])
        if row["kind"] == "plugin_cache":
            if (type(row["version"]) is not str or not VERSION.fullmatch(row["version"])
                    or row["version"] in {".", ".."}):
                raise InstallerError("invalid cache version")
            expected_key = "plugin_cache:" + row["version"]
        else:
            if row["version"] is not None or doc["mode"] != "install" or doc["profile"] is None:
                raise InstallerError("invalid recovery candidate")
            expected_key = row["kind"] + ":" + row["owner"]
        if row["key"] != expected_key or type(row["lease_known"]) is not bool:
            raise InstallerError("invalid candidate key")
        if type(row["reason"]) is not str:
            raise InstallerError("invalid candidate reason")
        image = TreeImage.from_dict(row["expected"])
        if image.state is not ImageState.PRESENT:
            raise InstallerError("candidate must retain its original present image")
        if type(row["proofs"]) is not list or not row["proofs"]:
            raise InstallerError("missing candidate proof")
        for proof in row["proofs"]:
            proof = exact(proof, "relative expected")
            path = PurePath(proof["relative"])
            if (path.is_absolute() or ".." in path.parts
                    or path.as_posix() != proof["relative"]
                    or not path.parts or path.parts[0] not in {"receipts", "marketplace-recovery"}):
                raise InstallerError("invalid proof path")
            if FileImage.from_dict(proof["expected"]).state is not ImageState.PRESENT:
                raise InstallerError("missing proof image")
        if row["kind"] == "plugin_cache":
            source = absolute(row["content_source"])
            if (source.name != "blender-mcp-installer" or source.parent.name != "plugins"
                    or source.parent.parent.parent != roots.projections
                    or not COMMIT.fullmatch(source.parent.parent.name)):
                raise InstallerError("invalid historical projection")
            if type(row["content_sha256"]) is not str or not HASH.fullmatch(row["content_sha256"]):
                raise InstallerError("invalid historical content hash")
        elif row["content_source"] is not None or row["content_sha256"] is not None:
            raise InstallerError("unexpected recovery content source")
    if not all(type(item) is dict and set(item) == {"path", "reason"}
               and all(type(value) is str for value in item.values()) for item in doc["findings"]):
        raise InstallerError("invalid discovery finding")
    for key in ("retired_receipts", "retired_registrations"):
        if type(doc[key]) is not list or len(doc[key]) != len(set(doc[key])):
            raise InstallerError("invalid retirement list")
        for value in doc[key]:
            if key == "retired_receipts":
                uuid_text(value)
            elif (type(value) is not str
                    or not re.fullmatch(r"marketplace-recovery/registration\.[A-Za-z0-9_-]+", value)):
                raise InstallerError("invalid retired registration reference")
    if doc["status"] in {"cleanup_pending", "complete"}:
        if verification["registration"] != "passed":
            raise InstallerError("cleanup lacks registration verification")
        if doc["mode"] == "install" and (verification["live"] != "passed"
                or doc["install_id"] is None or doc["profile"] is None):
            raise InstallerError("cleanup lacks live installation verification")
    if doc["status"] == "complete" and any(row["state"] != "removed" for row in doc["candidates"]):
        raise InstallerError("completed cleanup has remaining candidates")
    return copy.deepcopy(doc)


def validate_record(raw: object, roots: UpgradeRoots) -> dict[str, Any]:
    try:
        return _validate_record(raw, roots)
    except (TypeError, ValueError, KeyError) as exc:
        raise InstallerError("invalid upgrade schema") from exc


def new_record(roots: UpgradeRoots, mode: str, desired: dict[str, str],
               workflow_id: str | None = None) -> dict[str, Any]:
    return validate_record({
        "schema_version": 1, "id": workflow_id or str(uuid4()), "revision": 0,
        "mode": mode, "status": "awaiting_verification", "home": str(roots.home),
        "codex_home": str(roots.codex_home), "desired": desired, "profile": None,
        "registration": None, "install_id": None, "candidates": [], "findings": [],
        "verification": {"registration": "not_run", "live": "not_run"},
        "retired_receipts": [], "retired_registrations": [],
    }, roots)


def follows(old: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    if old is None:
        return new["revision"] == 0 and new["status"] == "awaiting_verification"
    if new["revision"] != old["revision"] + 1:
        return False
    if any(new[key] != old[key] for key in ("schema_version", "id", "mode", "home",
                                           "codex_home", "desired")):
        return False
    allowed = {
        "awaiting_verification": {"awaiting_verification", "cleanup_pending", "cancelled"},
        "cleanup_pending": {"cleanup_pending", "complete"},
        "complete": {"complete"},
        "cancelled": {"cancelled"},
    }
    if new["status"] not in allowed[old["status"]]:
        return False
    if old["install_id"] is not None and new["install_id"] != old["install_id"]:
        return False
    if old["profile"] is not None and new["profile"] != old["profile"]:
        return False
    if old["status"] in {"cleanup_pending", "complete", "cancelled"}:
        for key in ("profile", "registration", "install_id", "retired_receipts",
                    "retired_registrations", "findings", "verification"):
            if new[key] != old[key]:
                return False
        if len(old["candidates"]) != len(new["candidates"]):
            return False
        for before, after in zip(old["candidates"], new["candidates"], strict=True):
            if any(before[key] != after[key] for key in before if key not in {"state", "reason"}):
                return False
            if before["state"] == "removed" and after["state"] != "removed":
                return False
    return True


@contextmanager
def state_root(roots: UpgradeRoots) -> Iterator[SafeRoot]:
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        relative = roots.state.relative_to(roots.home)
        fd = home.open_directory(relative, create=True)
        os.close(fd)
    with SafeRoot.open(roots.state, os.getuid(), roots.home) as state:
        fd = state.open_directory(PurePath("upgrades"), create=True)
        os.close(fd)
        yield state


def record_ids(state: SafeRoot) -> tuple[str, ...]:
    try:
        fd = state.open_directory(PurePath("upgrades"))
    except FileNotFoundError:
        return ()
    try:
        names = os.listdir(fd)
    finally:
        os.close(fd)
    result: set[str] = set()
    for name in names:
        match = re.fullmatch(r"([0-9a-f-]{36})\.json", name)
        if match:
            result.add(uuid_text(match[1]))
        match = re.fullmatch(r"\.blender-mcp-installer\.([0-9a-f-]{36})\.\1\.json\.tmp", name)
        if match:
            result.add(uuid_text(match[1]))
    return tuple(sorted(result))


def load_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str,
                *, recover: bool = False) -> dict[str, Any] | None:
    workflow_id = uuid_text(workflow_id)
    ref = TargetRef(state, PurePath("upgrades", workflow_id + ".json"))
    live, stale = load_atomic_json_pair(ref, UUID(workflow_id))
    current = None if live is None else validate_record(live, roots)
    temporary = None if stale is None else validate_record(stale, roots)
    if any(doc is not None and doc["id"] != workflow_id for doc in (current, temporary)):
        raise InstallerError("upgrade filename identity mismatch")
    if temporary is None:
        return current
    transitions = []
    if follows(current, temporary):
        transitions.append((current, temporary))
    if current is not None and follows(temporary, current):
        transitions.append((temporary, current))
    if len(transitions) != 1:
        raise InstallerError("upgrade journal recovery conflict")
    if not recover:
        raise InstallerError("upgrade journal needs reconciliation")
    old, new = transitions[0]
    reconcile_atomic_json(ref, [(old, new)], UUID(workflow_id), fault=NoOpFaultInjector())
    return new


def save_record(state: SafeRoot, roots: UpgradeRoots, old: dict[str, Any] | None,
                new: dict[str, Any], fault: Any = None) -> dict[str, Any]:
    new = validate_record(new, roots)
    if not follows(old, new):
        raise InstallerError("invalid upgrade transition")
    ref = TargetRef(state, PurePath("upgrades", new["id"] + ".json"))
    actual = load_record(state, roots, new["id"])
    if actual != old:
        raise InstallerError("upgrade journal changed concurrently")
    write_atomic_json(ref, capture_file(state, ref.relative), new, UUID(new["id"]),
                      fault=fault or NoOpFaultInjector())
    return new


def update_record(state: SafeRoot, roots: UpgradeRoots, old: dict[str, Any],
                  *, fault: Any = None, **changes: Any) -> dict[str, Any]:
    new = copy.deepcopy(old)
    new.update(changes)
    new["revision"] += 1
    return save_record(state, roots, old, new, fault=fault)


def load_any_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str,
                    *, recover: bool = False) -> dict[str, Any] | None:
    workflow_id = uuid_text(workflow_id)
    ref = TargetRef(state, PurePath("upgrades", workflow_id + ".json"))
    live, stale = load_atomic_json_pair(ref, UUID(workflow_id))
    seed = live if live is not None else stale
    if seed is None:
        return None
    if type(seed) is not dict or seed.get("home") != str(roots.home):
        raise InstallerError("foreign or malformed shared-home upgrade record")
    selected = UpgradeRoots(roots.home, absolute(seed.get("codex_home")))
    return load_record(state, selected, workflow_id, recover=recover)
```

- [ ] **Step 3: 验证 schema 的 home/Codex home/profile/UUID/path/未知字段拒绝、revision 单调、原子临时文件合法相邻状态恢复。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_state.py -q
```

预期：schema 回归通过；receipt v1 测试原样通过。`load_record(recover=False)` 对未协调临时文件只报需要恢复，不能在只读入口修复。

- [ ] **Step 4: 检查差异并提交该独立单元。**

```bash
git diff --check
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_state.py tests/distribution/test_upgrade_state.py
git commit -m "feat(installer): journal verified upgrade cleanup separately"
```

### Task 2: 固定锁序与不随 rename 改变的版本使用锁

**Files:**
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_locks.py`
- Test: `tests/distribution/test_upgrade_locks.py`

**Interfaces:**
- Consumes: Task 1 的 `UpgradeRoots`、`state_root`；现有 `InstallerLock.acquire(state: SafeRoot, create: bool = True)`。
- Produces: `mutation_locks(roots: UpgradeRoots) -> Iterator[SafeRoot]`；`ensure_usage_lock(state: SafeRoot, device: int, inode: int) -> None`；`usage_lock(state: SafeRoot, device: int, inode: int, *, exclusive: bool) -> Iterator[bool]`；`script_usage(script: Path, roots: UpgradeRoots) -> Iterator[None]`。

- [ ] **Step 1: 写入 `tests/distribution/test_upgrade_locks.py`，执行真实子进程的 rename/exec 竞争回归。**

```python
import os,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'plugins/blender-mcp-installer/scripts'))
from blender_mcp_installer.upgrade_state import UpgradeRoots,state_root
from blender_mcp_installer.upgrade_locks import ensure_usage_lock,usage_lock,usage_name

def test_usage_identity_survives_rename_and_exec(tmp_path):
    home=tmp_path/'home';codex=tmp_path/'codex';home.mkdir(mode=0o700);codex.mkdir(mode=0o700)
    tree=home/'old';tree.mkdir();info=tree.stat()
    with state_root(UpgradeRoots(home,codex)) as state:
        ensure_usage_lock(state,info.st_dev,info.st_ino)
        lock=state.path/'usage'/usage_name(info.st_dev,info.st_ino)
        code="import os,sys,fcntl;fd=os.open(sys.argv[1],os.O_RDWR);fcntl.flock(fd,fcntl.LOCK_SH);os.set_inheritable(fd,True);os.execv(sys.executable,[sys.executable,'-c',\"import time;print('ready',flush=True);time.sleep(30)\"])"
        process=subprocess.Popen([sys.executable,'-c',code,str(lock)],stdout=subprocess.PIPE,text=True)
        try:
            assert process.stdout.readline().strip()=='ready'
            tree.rename(home/'retired')
            with usage_lock(state,info.st_dev,info.st_ino,exclusive=True) as acquired: assert not acquired
        finally:
            process.terminate();process.wait(timeout=5)
        with usage_lock(state,info.st_dev,info.st_ino,exclusive=True) as acquired: assert acquired
```

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_locks.py -q
```

预期：新模块缺失；实现后子进程仍持锁时排他获取失败，进程退出后成功。

- [ ] **Step 2: 创建完整锁模块。**

```python
from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Iterator

from blender_mcp_installer.filesystem import InstallerError, InstallerLock, SafeRoot
from blender_mcp_installer.upgrade_state import UpgradeRoots, absolute, state_root


def usage_name(device: int, inode: int) -> str:
    if type(device) is not int or device < 0 or type(inode) is not int or inode < 0:
        raise InstallerError("invalid usage identity")
    return hashlib.sha256(f"tree:{device}:{inode}".encode()).hexdigest() + ".lock"


def _lock_fd(parent: SafeRoot, name: str, *, create: bool) -> int:
    flags = os.O_RDWR | os.O_NOFOLLOW
    if create:
        try:
            fd = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent.fd)
            os.fchmod(fd, 0o600)
            os.fsync(fd)
            os.fsync(parent.fd)
        except FileExistsError:
            fd = os.open(name, flags, dir_fd=parent.fd)
    else:
        fd = os.open(name, flags, dir_fd=parent.fd)
    try:
        opened = os.fstat(fd)
        linked = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o600 or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)):
            raise InstallerError("unsafe upgrade lock")
        return fd
    except BaseException:
        os.close(fd)
        raise



@contextmanager
def mutation_locks(roots: UpgradeRoots) -> Iterator[SafeRoot]:
    with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
        fd = _lock_fd(codex, ".blender-mcp-marketplace.lock", create=True)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with state_root(roots) as state:
                with InstallerLock.acquire(state):
                    yield state
        finally:
            os.close(fd)


def ensure_usage_lock(state: SafeRoot, device: int, inode: int) -> None:
    directory = state.open_directory(PurePath("usage"), create=True)
    with SafeRoot(state.path / "usage", os.getuid(), directory) as usage:
        fd = _lock_fd(usage, usage_name(device, inode), create=True)
        os.close(fd)


@contextmanager
def usage_lock(state: SafeRoot, device: int, inode: int, *, exclusive: bool) -> Iterator[bool]:
    try:
        directory = state.open_directory(PurePath("usage"))
    except FileNotFoundError:
        yield False
        return
    with SafeRoot(state.path / "usage", os.getuid(), directory) as usage:
        try:
            fd = _lock_fd(usage, usage_name(device, inode), create=False)
        except FileNotFoundError:
            yield False
            return
        try:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            try:
                fcntl.flock(fd, operation | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            os.close(fd)


@contextmanager
def script_usage(script: Path, roots: UpgradeRoots) -> Iterator[None]:
    script = absolute(str(script))
    if not script.is_relative_to(roots.caches):
        yield
        return
    parts = script.relative_to(roots.caches).parts
    if len(parts) < 2:
        raise InstallerError("invalid cached script path")
    version_root = roots.caches / parts[0]
    before = version_root.stat(follow_symlinks=False)
    # No directory creation is allowed when a read-only script takes a lease.
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        directory = home.open_directory(roots.state.relative_to(roots.home))
    with SafeRoot(roots.state, os.getuid(), directory) as state:
        with usage_lock(state, before.st_dev, before.st_ino, exclusive=False) as acquired:
            if not acquired:
                raise InstallerError("plugin version is being retired; retry from current version")
            with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
                parent_fd, name = codex.open_parent(script.relative_to(roots.codex_home))
                try:
                    metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                        raise InstallerError("cached script disappeared or changed")
                finally:
                    os.close(parent_fd)
            after = version_root.stat(follow_symlinks=False)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise InstallerError("cached version changed while acquiring lease")
            yield
```

- [ ] **Step 3: 执行锁回归并核对只读入口不创建目录或锁文件。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_locks.py -q
```

预期：busy 与 legacy 均保留目录，释放后可删除；候选锁非阻塞，没有在变更锁内等待使用者的路径。两把变更锁永远按 marketplace → state 获取；持锁内部函数不再次调用命令行子进程获取同名锁。

- [ ] **Step 4: 提交锁模块及回归。**

```bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_locks.py tests/distribution/test_upgrade_locks.py
git commit -m "feat(installer): protect version use with inode leases"
```

### Task 3: 精确注册证据、不可逆清理边界和逐目录续删

**Files:**
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_registration.py`
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_cleanup.py`
- Create: `tests/distribution/test_upgrade_core.py`

**Interfaces:**
- Consumes: Tasks 1–2；`conditional_remove_tree(reference: TreeRef, expected: TreeImage, retained, fault)` 使用当前 filesystem 原语的合法删除前缀规则。
- Produces: `validate_installed_payload(payload: dict[str, Any], desired: dict[str, str]) -> dict[str, Any]`；`inspect_registration(codex: Path, roots: UpgradeRoots, desired: dict[str, str]) -> RegistrationSnapshot`；`finalize_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str, validate: Callable[[dict[str, Any]], tuple[Path, ...]], discover: Callable[[dict[str, Any]], tuple[list[dict[str, Any]], list[dict[str, str]]]], other_references: Callable[[dict[str, Any]], tuple[Path, ...]], fault: Any = None) -> dict[str, Any]`；`cleanup_result(doc: dict[str, Any]) -> dict[str, Any]`；`assert_rollback_available(state: SafeRoot, roots: UpgradeRoots, *, install_id: str | None = None, registration_ref: str | None = None) -> None`。

- [ ] **Step 1: 写入文末完整核心回归文件，执行当前单元的失败回归。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_core.py -k 'identity or validation or idempotent or crash or drift' -q
```

预期：缺失清理模块。真实 Codex 字段形状固定为 `pluginId=name@marketplace`、`source={source:local,path:plugin-directory}`、`marketplaceSource={sourceType:local,source:projection}`，两种 source 字段不能混用。

- [ ] **Step 2: 创建完整注册核验模块。**

```python
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from blender_mcp_installer.filesystem import (
    InstallerError, SafeRoot, TargetRef, capture_file, capture_tree,
)
from blender_mcp_installer.model import FileImage, ImageState, TreeImage
from blender_mcp_installer.upgrade_state import UpgradeRoots

MARKETPLACE = "official-blender-mcp"
PLUGIN = "blender-mcp-installer"
PLUGIN_ID = PLUGIN + "@" + MARKETPLACE


def read_owned_bytes(reference: TargetRef) -> tuple[bytes, FileImage]:
    before = capture_file(reference.root, reference.relative)
    if before.state is not ImageState.PRESENT or before.size > 32 * 1024 * 1024:
        raise InstallerError("missing or oversized identity file")
    parent_fd, name = reference.root.open_parent(reference.relative)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(32 * 1024 * 1024 + 1)
    finally:
        os.close(parent_fd)
    if (len(raw) != before.size or hashlib.sha256(raw).hexdigest() != before.sha256
            or capture_file(reference.root, reference.relative) != before):
        raise InstallerError("identity file changed")
    return raw, before


def content_sha256(image: TreeImage) -> str:
    if image.state is not ImageState.PRESENT or image.mode & 0o022:
        raise InstallerError("unsafe plugin tree")
    entries = []
    for entry in image.entries:
        if entry.mode & 0o022:
            raise InstallerError("unsafe plugin tree entry")
        entries.append((entry.path, entry.kind, entry.sha256))
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def codex_json(codex: Path, roots: UpgradeRoots, *arguments: str) -> dict[str, Any]:
    env = dict(os.environ)
    env.update(HOME=str(roots.home), CODEX_HOME=str(roots.codex_home))
    result = subprocess.run([str(codex), *arguments], check=True, capture_output=True,
                            text=True, env=env, timeout=30)
    value = json.loads(result.stdout)
    if type(value) is not dict:
        raise InstallerError("invalid Codex registration response")
    return value


def validate_installed_payload(payload: dict[str, Any], desired: dict[str, str]) -> dict[str, Any]:
    installed = payload.get("installed")
    if type(installed) is not list:
        raise InstallerError("missing installed plugin list")
    matches = [item for item in installed if type(item) is dict
               and (item.get("pluginId") == PLUGIN_ID or item.get("name") == PLUGIN)]
    if len(matches) != 1:
        raise InstallerError("installed plugin identity is not unique")
    item = matches[0]
    expected = {"pluginId": PLUGIN_ID, "name": PLUGIN, "marketplaceName": MARKETPLACE,
                "version": desired["plugin_version"]}
    if (any(item.get(key) != value for key, value in expected.items())
            or item.get("installed") is not True or item.get("enabled") is not True):
        raise InstallerError("installed plugin identity mismatch")
    source, marketplace = item.get("source"), item.get("marketplaceSource")
    if (type(source) is not dict or source.get("source") != "local"
            or source.get("path") != str(Path(desired["projection"]) / "plugins" / PLUGIN)
            or type(marketplace) is not dict or marketplace.get("sourceType") != "local"
            or marketplace.get("source") != desired["projection"]):
        raise InstallerError("installed plugin source mismatch")
    return item


@dataclass(frozen=True)
class RegistrationSnapshot:
    item: dict[str, Any]
    config: FileImage
    cache: TreeImage
    projection: TreeImage


def inspect_registration(codex: Path, roots: UpgradeRoots,
                         desired: dict[str, str]) -> RegistrationSnapshot:
    projection = Path(desired["projection"])
    if projection != roots.projections / desired["commit"]:
        raise InstallerError("registration projection mismatch")
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex_root:
            cache_relative = (roots.caches / desired["plugin_version"]).relative_to(roots.codex_home)
            projection_relative = projection.relative_to(roots.home)
            config = capture_file(codex_root, PurePath("config.toml"))
            cache = capture_tree(codex_root, cache_relative)
            source = capture_tree(home, projection_relative / "plugins" / PLUGIN)
            projection_image = capture_tree(home, projection_relative)
            raw, _ = read_owned_bytes(TargetRef(home, projection_relative
                                               / "plugins" / PLUGIN / ".codex-plugin/plugin.json"))
            manifest = json.loads(raw)
            if manifest.get("name") != PLUGIN or manifest.get("version") != desired["plugin_version"]:
                raise InstallerError("projected plugin manifest mismatch")
            if content_sha256(source) != content_sha256(cache):
                raise InstallerError("cached plugin content mismatch")
            item = validate_installed_payload(codex_json(
                codex, roots, "plugin", "list", "--marketplace", MARKETPLACE, "--json"), desired)
            listing = codex_json(codex, roots, "plugin", "marketplace", "list", "--json")
            matches = [row for row in listing.get("marketplaces", [])
                       if type(row) is dict and row.get("name") == MARKETPLACE]
            if len(matches) != 1 or matches[0].get("root") != str(projection):
                raise InstallerError("marketplace source mismatch")
            if (capture_file(codex_root, PurePath("config.toml")) != config
                    or capture_tree(codex_root, cache_relative) != cache
                    or capture_tree(home, projection_relative) != projection_image):
                raise InstallerError("registration changed during verification")
            return RegistrationSnapshot(item, config, cache, projection_image)
```

- [ ] **Step 3: 创建完整清理模块。**

```python
from __future__ import annotations

import copy
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path, PurePath
from uuid import UUID
from typing import Any, Callable, Iterator

from blender_mcp_installer.filesystem import (
    InstallerError, NoOpFaultInjector, SafeRoot, TreeRef, capture_file,
    capture_tree, conditional_remove_tree, TargetRef, write_atomic_json,
)
from blender_mcp_installer.model import FileImage, TreeImage
from blender_mcp_installer.upgrade_locks import usage_lock
from blender_mcp_installer.upgrade_registration import content_sha256, read_owned_bytes
from blender_mcp_installer.upgrade_state import (
    UpgradeRoots, load_any_record, load_record, record_ids, update_record, validate_record,
)


class RollbackUnavailable(InstallerError):
    code = "rollback_unavailable"


def candidate_path(roots: UpgradeRoots, doc: dict[str, Any], row: dict[str, Any]) -> Path:
    if row["kind"] == "runtime_recovery":
        return roots.home / ".local/share/blender-lab-mcp" / (
            f".blender-mcp-installer.{row['owner']}.runtime.recovery")
    if row["kind"] == "extension_recovery":
        return Path(doc["profile"]["extensions"]) / "user_default" / (
            f".blender-mcp-installer.{row['owner']}.extension.recovery")
    if row["kind"] == "plugin_cache":
        return roots.caches / row["version"]
    raise InstallerError("unsupported cleanup boundary")


@contextmanager
def candidate_ref(roots: UpgradeRoots, doc: dict[str, Any],
                  row: dict[str, Any]) -> Iterator[TreeRef]:
    path = candidate_path(roots, doc, row)
    if row["kind"] == "plugin_cache":
        boundary = roots.codex_home
    elif row["kind"] == "extension_recovery":
        boundary = Path(doc["profile"]["resources"])
    else:
        boundary = roots.home
    with SafeRoot.open(boundary, os.getuid(), boundary) as root:
        yield TreeRef(root, path.relative_to(boundary))


def proof_matches(state: SafeRoot, roots: UpgradeRoots, row: dict[str, Any]) -> bool:
    for proof in row["proofs"]:
        if capture_file(state, PurePath(proof["relative"])) != FileImage.from_dict(proof["expected"]):
            return False
    if row["kind"] == "plugin_cache":
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            source = capture_tree(home, Path(row["content_source"]).relative_to(roots.home))
        return content_sha256(source) == row["content_sha256"]
    return True


def execution_paths() -> tuple[Path, ...]:
    paths = {Path.cwd(), Path(sys.executable).absolute()}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if isinstance(filename, str):
            paths.add(Path(filename).absolute())
    for path in sys.path:
        paths.add(Path(path or ".").absolute())
    return tuple(paths)


def overlapping(path: Path, protected: tuple[Path, ...]) -> bool:
    return any(path == item or item.is_relative_to(path) for item in protected)


def assert_rollback_available(state: SafeRoot, roots: UpgradeRoots, *,
                              install_id: str | None = None,
                              registration_ref: str | None = None) -> None:
    for workflow_id in record_ids(state):
        doc = load_any_record(state, roots, workflow_id)
        if doc is None or doc["status"] not in {"cleanup_pending", "complete"}:
            continue
        if ((install_id is not None and install_id in doc["retired_receipts"])
                or (registration_ref is not None and registration_ref in doc["retired_registrations"])):
            raise RollbackUnavailable("old program entered automatic cleanup; local rollback unavailable")


def write_retirement_notices(state: SafeRoot, doc: dict[str, Any], fault: Any) -> None:
    notice = {"schema_version": 1, "program_rollback": "unavailable",
              "reason": "automatic_cleanup_started"}
    for reference in doc["retired_registrations"]:
        path = PurePath(reference, "RECOVERY_STATUS.json")
        target = TargetRef(state, path)
        image = capture_file(state, path)
        if image.state.value == "present":
            raw, _image = read_owned_bytes(target)
            if json.loads(raw) != notice:
                raise InstallerError("registration recovery notice conflict")
            continue
        write_atomic_json(target, image, notice, UUID(doc["id"]), fault=fault)


def finalize_record(
    state: SafeRoot,
    roots: UpgradeRoots,
    workflow_id: str,
    validate: Callable[[dict[str, Any]], tuple[Path, ...]],
    discover: Callable[[dict[str, Any]], tuple[list[dict[str, Any]], list[dict[str, str]]]],
    other_references: Callable[[dict[str, Any]], tuple[Path, ...]],
    fault: Any = None,
) -> dict[str, Any]:
    fault = fault or NoOpFaultInjector()
    doc = load_record(state, roots, workflow_id, recover=True)
    if doc is None or doc["status"] == "cancelled":
        raise InstallerError("upgrade cannot be finalized")
    if doc["status"] == "complete":
        validate(doc)
        return doc
    protected = validate(doc)
    if doc["status"] == "awaiting_verification":
        candidates, findings = discover(doc)
        pending = copy.deepcopy(doc)
        pending["candidates"], pending["findings"] = candidates, findings
        pending["verification"] = {
            "registration": "passed",
            "live": "passed" if doc["mode"] == "install" else "not_run",
        }
        receipts = {row["owner"] for row in candidates if row["kind"] != "plugin_cache"}
        registrations = {str(PurePath(proof["relative"]).parent)
                         for row in candidates if row["kind"] == "plugin_cache"
                         for proof in row["proofs"]
                         if PurePath(proof["relative"]).parts[0] == "marketplace-recovery"}
        if receipts and doc["install_id"] is not None:
            receipts.add(doc["install_id"])
        if registrations and doc["registration"] is not None:
            registrations.add("marketplace-recovery/registration." + doc["registration"]["id"])
        pending["retired_receipts"] = sorted(receipts)
        pending["retired_registrations"] = sorted(registrations)
        pending["status"] = "cleanup_pending"
        # save_record's atomic JSON implementation fsyncs the directory before returning.
        changes = {key: pending[key] for key in pending
                   if key not in {"revision", "id", "schema_version", "mode", "home", "codex_home",
                                  "desired", "profile", "registration", "install_id"}}
        doc = update_record(state, roots, doc, fault=fault, **changes)
        fault.hit("after_upgrade_cleanup_intent")
    write_retirement_notices(state, doc, fault)
    for index, original in enumerate(tuple(doc["candidates"])):
        if original["state"] == "removed":
            continue
        row = copy.deepcopy(original)
        path = candidate_path(roots, doc, row)
        protected = (*validate(doc), *other_references(doc), *execution_paths())
        if overlapping(path, protected):
            row.update(state="deferred_in_use", reason="active or recovery reference")
        else:
            try:
                if not proof_matches(state, roots, row):
                    raise InstallerError("candidate proof changed")
                expected = TreeImage.from_dict(row["expected"])
                with candidate_ref(roots, doc, row) as reference:
                    current = reference.capture()
                    if current == TreeImage.absent():
                        row.update(state="removed", reason="verified absent")
                    elif not row["lease_known"]:
                        row.update(state="deferred_in_use", reason="legacy usage is not proven idle")
                    else:
                        with usage_lock(state, expected.dev, expected.ino, exclusive=True) as acquired:
                            if not acquired:
                                row.update(state="deferred_in_use", reason="version lease is busy or missing")
                            else:
                                validate(doc)
                                conditional_remove_tree(reference, expected, (), fault)
                                validate(doc)
                                row.update(state="removed", reason="verified deletion")
            except (InstallerError, OSError, ValueError) as exc:
                row.update(state="conflict", reason=str(exc))
        rows = copy.deepcopy(doc["candidates"])
        rows[index] = row
        doc = update_record(state, roots, doc, fault=fault, candidates=rows)
        fault.hit("after_upgrade_candidate_record")
    if all(row["state"] == "removed" for row in doc["candidates"]):
        validate(doc)
        doc = update_record(state, roots, doc, fault=fault, status="complete")
    return validate_record(doc, roots)


def cleanup_result(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_id": doc["id"], "status": doc["status"],
        "new_version_verified": doc["verification"]["registration"] == "passed"
            and (doc["mode"] == "register" or doc["verification"]["live"] == "passed"),
        "removed": [row["key"] for row in doc["candidates"] if row["state"] == "removed"],
        "pending": [{"key": row["key"], "reason": row["reason"]}
                    for row in doc["candidates"] if row["state"] != "removed"],
        "unverified": doc["findings"],
        "all_old_versions_removed": doc["status"] == "complete" and not doc["findings"],
    }
```

- [ ] **Step 4: 执行故障矩阵。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_core.py -k "not discovery and not register_mode and not exact_registration and not orphan and not full_finalize and not other_codex and not legacy_registration_before" -q
```

预期：全部通过。`after_upgrade_cleanup_intent`、`after_cleanup_entry`、`after_installer_cleanup`、`after_upgrade_candidate_record` 任意退出后从原镜像恢复；不重新采纳外来文件，不重建旧树，不回滚新版。

- [ ] **Step 5: 提交验证与清理执行器。**

```bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_registration.py plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_cleanup.py tests/distribution/test_upgrade_core.py
git commit -m "feat(installer): finalize verified upgrades with resumable cleanup"
```

### Task 4: 历史归属发现、迁移和其他事务的恢复引用

**Files:**
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_discovery.py`
- Test: `tests/distribution/test_upgrade_core.py`

**Interfaces:**
- Consumes: Tasks 1–3；`parse_receipt(value: object, roots: InstallRoots) -> Receipt`；现有 receipt 的 `parent_install_id`、`target.pre` 和 `target.install_post`。
- Produces: `install_roots(roots: UpgradeRoots, doc: dict[str, Any]) -> InstallRoots`；`discover_candidates(state: SafeRoot, roots: UpgradeRoots, doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]`；`other_references(state: SafeRoot, roots: UpgradeRoots, doc: dict[str, Any]) -> tuple[Path, ...]`；`current_paths(roots: UpgradeRoots, doc: dict[str, Any]) -> tuple[Path, ...]`。

- [ ] **Step 1: 增加发现不会接受“名字像旧版本”的实际回归。**

```python
def test_discovery_keeps_cache_without_historical_source(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates
    roots, state, doc, _row, old = prepared
    candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert findings
    assert old.exists()


def test_register_mode_never_discovers_runtime_recovery(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates
    roots, state, doc, _row, _old = prepared
    recovery = roots.home / '.local/share/blender-lab-mcp/.blender-mcp-installer.fake.runtime.recovery'
    recovery.mkdir(parents=True)
    (recovery / 'user-file').write_text('preserve')
    candidates, _findings = discover_candidates(state, roots, doc)
    assert all(row['kind'] == 'plugin_cache' for row in candidates)
    assert (recovery / 'user-file').read_text() == 'preserve'
```

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_core.py -k 'discovery or register_mode' -q
```

预期：新发现模块不存在。

- [ ] **Step 2: 创建完整候选发现模块。**

```python
from __future__ import annotations

import copy
import json
import os
from pathlib import Path, PurePath
from typing import Any
from uuid import UUID

from blender_mcp_installer.filesystem import InstallerError, SafeRoot, TargetRef, capture_file, capture_tree
from blender_mcp_installer.model import (BlenderPaths, ImageState, InstallRoots,
    ReceiptStatus, TargetRole, TreeImage, parse_receipt)
from blender_mcp_installer.upgrade_cleanup import candidate_path
from blender_mcp_installer.upgrade_registration import content_sha256, read_owned_bytes
from blender_mcp_installer.upgrade_state import (COMMIT, UpgradeRoots, load_any_record, record_ids)


def install_roots(roots: UpgradeRoots, doc: dict[str, Any]) -> InstallRoots:
    profile = doc["profile"]
    if profile is None:
        raise InstallerError("installation profile is missing")
    paths = BlenderPaths(Path(profile["executable"]), profile["architecture"], profile["version"],
                         Path(profile["resources"]), Path(profile["config"]), Path(profile["extensions"]))
    source = Path(doc["desired"]["projection"])
    return InstallRoots.discover(roots.home, roots.codex_home, paths,
                                source_distribution_root=source, distribution_root=source)


def read_proof(state: SafeRoot, relative: PurePath) -> tuple[Any, dict[str, Any]]:
    if capture_file(state, relative).state is ImageState.ABSENT:
        raise FileNotFoundError(str(state.path / relative))
    raw, image = read_owned_bytes(TargetRef(state, relative))
    return json.loads(raw), {"relative": relative.as_posix(), "expected": image.to_dict()}


def directory_names(state: SafeRoot, relative: PurePath) -> tuple[str, ...]:
    try:
        fd = state.open_directory(relative)
    except FileNotFoundError:
        return ()
    try:
        return tuple(sorted(os.listdir(fd)))
    finally:
        os.close(fd)


def lease_protocol(image: TreeImage) -> bool:
    import hashlib
    expected = hashlib.sha256(b"inode-v1\n").hexdigest()
    return any(item.path == ".blender-mcp-usage-v1" and item.kind == "file"
               and item.sha256 == expected for item in image.entries)


def current_paths(roots: UpgradeRoots, doc: dict[str, Any]) -> tuple[Path, ...]:
    paths = [Path(doc["desired"]["projection"]), roots.caches / doc["desired"]["plugin_version"]]
    if doc["mode"] == "install":
        installed = install_roots(roots, doc)
        paths.extend((installed.runtime, installed.extension_target))
    return tuple(paths)


def source_reference(roots: UpgradeRoots, before: Any) -> tuple[Path, ...]:
    if not before.get("present") or before.get("source_type") != "local":
        return ()
    source = Path(before["source"])
    if source.parent != roots.projections or not COMMIT.fullmatch(source.name):
        return (source,)
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        raw, _image = read_owned_bytes(TargetRef(home,
            (source / "plugins/blender-mcp-installer/.codex-plugin/plugin.json").relative_to(roots.home)))
    manifest = json.loads(raw)
    version = manifest.get("version")
    if type(version) is not str or "/" in version or version in {".", ".."}:
        raise InstallerError("invalid recovery source plugin version")
    return (source, roots.caches / version)


def other_references(state: SafeRoot, roots: UpgradeRoots,
                     doc: dict[str, Any]) -> tuple[Path, ...]:
    references = []
    retired_receipts = set(doc["retired_receipts"])
    retired_registrations = set(doc["retired_registrations"])
    records = [load_any_record(state, roots, identifier) for identifier in record_ids(state)]
    for other in records:
        if other is not None and other["status"] in {"cleanup_pending", "complete"}:
            retired_receipts.update(other["retired_receipts"])
            retired_registrations.update(other["retired_registrations"])
    for other in records:
        if other is None:
            continue
        if other["id"] == doc["id"] or other["status"] != "awaiting_verification":
            continue
        registration = other["registration"]
        registration_ref = None if registration is None else (
            "marketplace-recovery/registration." + registration["id"])
        if ((other["install_id"] is not None and other["install_id"] in retired_receipts)
                or registration_ref in retired_registrations):
            continue
        selected = UpgradeRoots(roots.home, Path(other["codex_home"]))
        references.extend(current_paths(selected, other))
        if other["mode"] == "install" and other["install_id"] is not None:
            installed = install_roots(selected, other)
            references.extend((installed.runtime_recovery(UUID(other["install_id"])),
                               installed.extension_recovery(UUID(other["install_id"]))))
    # Receipts remain authoritative even if the producing version predates upgrade journals.
    for name in directory_names(state, PurePath("receipts")):
        if not name.endswith(".json") or name.endswith(".usage.json"):
            continue
        try:
            identity = str(UUID(name[:-5]))
        except ValueError:
            raise InstallerError("unknown receipt filename blocks cleanup") from None
        value, _proof = read_proof(state, PurePath("receipts", name))
        host = value["host"]
        if host["home"] != str(roots.home):
            raise InstallerError("foreign receipt home blocks cleanup")
        selected = UpgradeRoots(roots.home, Path(host["codex_home"]))
        profile = BlenderPaths(Path(host["blender_executable"]), host["blender_architecture"],
            host["blender_version"], Path(host["blender_user_resources"]),
            Path(host["blender_user_config"]), Path(host["blender_user_extensions"]))
        source = Path(doc["desired"]["projection"])
        installed = InstallRoots.discover(selected.home, selected.codex_home, profile,
            source_distribution_root=source, distribution_root=source)
        receipt = parse_receipt(value, installed)
        if str(receipt.install_id) != identity:
            raise InstallerError("receipt filename identity mismatch")
        if receipt.status is ReceiptStatus.ROLLED_BACK:
            continue
        if receipt.status is ReceiptStatus.INSTALLED and identity in retired_receipts:
            continue
        # Never let a retirement record override PREPARED / ROLLBACK_PENDING authority.
        for target in receipt.targets:
            if isinstance(target.pre, TreeImage) and target.pre.state is ImageState.PRESENT:
                references.append(target.recovery_path)
    # Legacy source-restore evidence can reference an old cache without any new journal.
    for name in directory_names(state, PurePath("marketplace-recovery")):
        reference = PurePath("marketplace-recovery", name)
        if not name.startswith("registration.") or reference.as_posix() in retired_registrations:
            continue
        try:
            before, _proof = read_proof(state, reference / "before.json")
        except FileNotFoundError:
            continue
        references.extend(source_reference(roots, before))
    return tuple(references)


def discover_candidates(state: SafeRoot, roots: UpgradeRoots,
                        doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, str]] = []
    # Carry durable deletion baselines forward; never capture a partial deletion as a new baseline.
    for workflow_id in record_ids(state):
        other = load_any_record(state, roots, workflow_id)
        if (other is None or other["codex_home"] != str(roots.codex_home)
                or other["id"] == doc["id"] or other["status"] != "cleanup_pending"):
            continue
        if other["profile"] != doc["profile"] and other["mode"] == "install":
            continue
        for original in other["candidates"]:
            if original["state"] == "removed" or (doc["mode"] == "register" and original["kind"] != "plugin_cache"):
                continue
            row = copy.deepcopy(original)
            row.update(state="pending", reason="carried durable cleanup baseline")
            rows[row["key"]] = row
    if doc["mode"] == "install":
        installed = install_roots(roots, doc)
        identity = doc["install_id"]
        visited = set()
        while identity is not None:
            if identity in visited:
                raise InstallerError("receipt ancestry cycle")
            visited.add(identity)
            value, proof = read_proof(state, PurePath("receipts", identity + ".json"))
            child = parse_receipt(value, installed)
            if str(child.install_id) != identity or child.status is not ReceiptStatus.INSTALLED:
                raise InstallerError("active receipt ancestry is not installed")
            parent_id = None if child.parent_install_id is None else str(child.parent_install_id)
            parent = None
            parent_proof = None
            if parent_id is not None:
                parent_value, parent_proof = read_proof(state, PurePath("receipts", parent_id + ".json"))
                parent = parse_receipt(parent_value, installed)
                if parent.status is not ReceiptStatus.INSTALLED or parent.generation >= child.generation:
                    raise InstallerError("invalid receipt ancestry")
            for role, kind in ((TargetRole.RUNTIME, "runtime_recovery"),
                               (TargetRole.BLENDER_EXTENSION, "extension_recovery")):
                target = next(item for item in child.targets if item.role is role)
                if target.pre.state is ImageState.ABSENT:
                    continue
                key = kind + ":" + identity
                if key in rows:
                    continue
                recovery_path = (installed.runtime_recovery(child.install_id) if role is TargetRole.RUNTIME
                                 else installed.extension_recovery(child.install_id))
                boundary = roots.home if role is TargetRole.RUNTIME else installed.blender.user_resources
                with SafeRoot.open(boundary, os.getuid(), boundary) as root:
                    recovery_image = capture_tree(root, recovery_path.relative_to(boundary))
                if recovery_image.state is ImageState.ABSENT:
                    continue
                old = None if parent is None else next(item for item in parent.targets if item.role is role)
                if old is None or old.install_post != target.pre:
                    findings.append({"path": str(target.recovery_path),
                                     "reason": "preimage lacks exact managed parent provenance"})
                    continue
                row = {"key": key, "kind": kind, "owner": identity, "version": None,
                       "expected": target.pre.to_dict(), "proofs": [proof, parent_proof],
                       "content_source": None, "content_sha256": None,
                       "lease_known": lease_protocol(target.pre), "state": "pending", "reason": ""}
                rows[key] = row
            identity = parent_id
    for name in directory_names(state, PurePath("marketplace-recovery")):
        if not name.startswith("registration."):
            continue
        try:
            after, proof = read_proof(state, PurePath("marketplace-recovery", name, "after.json"))
            source = Path(after["source"])
            if (after.get("source_type") != "local" or source.parent != roots.projections
                    or not COMMIT.fullmatch(source.name)):
                raise InstallerError("historical registration has no reviewed local projection")
            if str(source) == doc["desired"]["projection"]:
                continue
            plugin = source / "plugins/blender-mcp-installer"
            with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
                raw, _manifest_image = read_owned_bytes(TargetRef(home,
                    (plugin / ".codex-plugin/plugin.json").relative_to(roots.home)))
                manifest = json.loads(raw)
                source_image = capture_tree(home, plugin.relative_to(roots.home))
            version = manifest["version"]
            if (manifest.get("name") != "blender-mcp-installer" or type(version) is not str
                    or "/" in version or version in {".", ".."}):
                raise InstallerError("invalid historical plugin manifest")
            if version == doc["desired"]["plugin_version"] or "plugin_cache:" + version in rows:
                continue
            with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
                image = capture_tree(codex, (roots.caches / version).relative_to(roots.codex_home))
            if image.state is ImageState.ABSENT:
                continue
            digest = content_sha256(source_image)
            if digest != content_sha256(image):
                raise InstallerError("historical cache content differs from projection")
            row = {"key": "plugin_cache:" + version, "kind": "plugin_cache", "owner": doc["id"],
                   "version": version, "expected": image.to_dict(), "proofs": [proof],
                   "content_source": str(plugin), "content_sha256": digest,
                   "lease_known": lease_protocol(image), "state": "pending", "reason": ""}
            rows[row["key"]] = row
        except (InstallerError, ValueError, OSError, KeyError, TypeError) as exc:
            findings.append({"path": str(state.path / "marketplace-recovery" / name), "reason": str(exc)})
    # Enumerate only the exact owned plugin namespace to report unproven physical leftovers.
    with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex:
        names = directory_names(codex, roots.caches.relative_to(roots.codex_home))
        for version in names:
            if version == doc["desired"]["plugin_version"] or "plugin_cache:" + version in rows:
                continue
            findings.append({"path": str(roots.caches / version),
                             "reason": "cache has no complete historical ownership proof"})
    protected = current_paths(roots, doc)
    return ([row for _key, row in sorted(rows.items())
             if candidate_path(roots, doc, row) not in protected], findings)
```

- [ ] **Step 3: 执行发现回归并检查迁移限制。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_core.py -k "not exact_registration and not full_finalize" -q
```

预期：没有 parent 的首次安装旧树、未知 profile、无 after/source 的旧注册、缺失 projection、未知文件全部保留。原生 receipt 继续由严格 parser 读取，不重写 receipt。已有 cleanup_pending 的原始镜像被复制为新任务的基线，禁止扫描半删树重新生成摘要；awaiting_verification 的恢复引用继续保护。

- [ ] **Step 4: 提交发现模块及测试。**

```bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_discovery.py tests/distribution/test_upgrade_core.py
git commit -m "feat(installer): derive cleanup ownership from retained evidence"
```

### Task 5: 发布前 runtime 屏障、外部 bootstrap 与安装入口接线

**Files:**
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_handoff.py`
- Create: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_integration.py`
- Modify: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/runtime.py:_launcher_source,stage_runtime,_state,verify_runtime`
- Modify: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py:_Context,_context,_changed_install,install,_preflight_rollback,_parser,run_cli`
- Modify: `tests/distribution/test_cli.py:_install_context`
- Modify: `tests/distribution/fault_driver.py:_patch_scenario`
- Test: `tests/distribution/test_upgrade_launcher.py`

**Interfaces:**
- Consumes: Tasks 1–4；`_lifecycle_closed(context: _Context) -> None`；现有 `verify_live` 不改变签名。
- Produces: `runtime_quiescence(state: SafeRoot, roots: UpgradeRoots, runtime: Path, codex: Path, handoff_id: str | None = None) -> Iterator[dict[str, Any] | None]`；`begin_handoff(state: SafeRoot, roots: UpgradeRoots, runtime: Path, codex: Path) -> dict[str, Any]`；`select_install_workflow(state: SafeRoot, context: Any, *, exact: bool) -> dict[str, Any] | None`；`bind_receipt(state: SafeRoot, context: Any, workflow_id: str, install_id: UUID) -> None`；`_changed_install_locked(context: _Context, fault: FaultInjector, state: SafeRoot, workflow_id: str | None, runtime_handoff: dict[str, Any] | None) -> dict[str, object]`；`finalize_install_locked(state: SafeRoot, context: Any, workflow_id: str, fault: Any) -> dict[str, Any]`。

- [ ] **Step 1: 写入本 Task 末尾的 launcher 回归，验证 prepared receipt 必须在 runtime payload 启动前被拒绝。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_launcher.py -q
```

预期：现有 launcher 会直接执行 payload，prepared 用例失败；installed 用例无法观测共享 lease。回归必须实际 exec 子进程。

- [ ] **Step 2: 创建完整维护交接与屏障模块。**

完整实现见紧随本 Task 的 `upgrade_handoff.py` 代码块。`begin_handoff` 记录正向观察到的受支持客户端 PID、启动时间、命令摘要及旧 runtime 完整镜像；迁移时要求这些 PID 已消失且没有新的受支持客户端。scope 固定为 `cooperating-managed-clients`，不宣称覆盖自行绕过受管入口的进程；未知入口或无法识别的进程状态返回 `legacy_handoff_required`。不得通过写一个空 processes 列表获得交接证据。

- [ ] **Step 3: 用本 Task 完整 `_launcher_source` 替换现有函数，并把 bootstrap 路径纳入已有 runtime marker 的 launcher_environment。**

给 `stage_runtime` 追加仅关键字参数 `codex_home: Path | None = None`，生产 CLI 始终传入真实 roots.codex_home；默认值仅保留原有独立 API 的默认 profile home 兼容性。在 `stage_runtime` 的 `launcher_environment = _profile_env(profile)` 位置替换为：

```python
bootstrap_python = python_bin.resolve(strict=True)
selected_codex_home = _absolute(codex_home or profile.home / ".codex", "Codex home")
managed_caches = selected_codex_home / "plugins/cache/official-blender-mcp/blender-mcp-installer"
if bootstrap_python.is_relative_to(runtime.parent) or bootstrap_python.is_relative_to(managed_caches):
    raise InstallerError("bootstrap Python must remain outside managed runtime trees")
launcher_environment = {
    **_profile_env(profile),
    "BLENDER_MCP_BOOTSTRAP_PYTHON": str(bootstrap_python),
    "BLENDER_MCP_CODEX_HOME": str(selected_codex_home),
}
```

在 `_write_exclusive(runtime / _LOCK_COPY, lock_raw, 0o600)` 后插入协议标记（在 `_content_summary` 之前）：

```python
_write_exclusive(runtime / ".blender-mcp-usage-v1", b"inode-v1\n", 0o600)
```

在 `_state` 的 `expected_environment = _profile_env(...)` 块之后、`if environment != expected_environment` 之前插入：

```python
bootstrap = _absolute(Path(environment["BLENDER_MCP_BOOTSTRAP_PYTHON"]), "bootstrap Python")
selected_codex_home = _absolute(Path(environment["BLENDER_MCP_CODEX_HOME"]), "Codex home")
managed_caches = selected_codex_home / "plugins/cache/official-blender-mcp/blender-mcp-installer"
if (bootstrap.is_relative_to(runtime.parent) or bootstrap.is_relative_to(managed_caches)
        or not bootstrap.is_file()):
    raise InstallerError("runtime bootstrap is not external")
expected_environment["BLENDER_MCP_BOOTSTRAP_PYTHON"] = str(bootstrap)
expected_environment["BLENDER_MCP_CODEX_HOME"] = str(selected_codex_home)
```

在 `verify_runtime` 中替换环境比较这一项：

```diff
@@ def verify_runtime(...):
-        or state.launcher_environment != _profile_env(profile)
+        or {key: value for key, value in state.launcher_environment.items()
+            if key not in {"BLENDER_MCP_BOOTSTRAP_PYTHON", "BLENDER_MCP_CODEX_HOME"}} != _profile_env(profile)
```

其他 runtime 元数据字段和 schema_version 保持现状。旧 launcher 缺失 bootstrap 字段，inspect 判定非 exact 并走受控升级；不能把旧 marker 原地补成新协议。

- [ ] **Step 4: 创建完整安装/注册 finalize 接线模块。**

完整实现见本 Task 的 `upgrade_integration.py` 代码块。一次 finalize 在锁内只运行一次完整 verify_live；每个候选前后比较该次验证绑定的 active/receipt/runtime/extension/registration 快照，任何变化立即停止后续删除。一次 finalize 在锁内只运行一次完整 verify_live；每个候选前后比较该次验证绑定的 active/receipt/runtime/extension/registration 快照，任何变化立即停止后续删除。新旧 helper 都采用显式 context/state；不从全局变量推断 workflow ID，不通过验证子进程重复获取 state lock。

- [ ] **Step 5: 给 `_Context` 增加显式身份字段，生产与两个假宿主构造点一起修改。**

在现有 `_Context.roots` 之后增加：

```python
distribution_commit: str
workflow_id: str | None = None
handoff_id: str | None = None
```

在 `_context` 的 roots 构造后、yield 前增加实际根边界检查：

```python
upgrade_roots = UpgradeRoots(roots.home, roots.codex_home)
if (host.python_bin.is_relative_to(upgrade_roots.caches)
        or host.python_bin.is_relative_to(roots.runtime.parent)):
    raise InstallerError("bootstrap Python cannot be supplied by a cleanup candidate tree")
```

`_context` 的 `_Context(...)` 调用在 `roots` 参数之后追加：

```python
args.expected_distribution_commit,
getattr(args, "workflow_id", None),
getattr(args, "handoff_id", None),
```

`tests/distribution/test_cli.py:_install_context` 的 `_Context(...)` 在 `roots` 后追加已有常量 `COMMIT`；`tests/distribution/fault_driver.py` 的构造点追加 `"a" * 40`。故障测试继续使用显式临时 HOME/Codex home roots，不修改执行 pytest 进程的 HOME。

- [ ] **Step 6: 机械提取原 `_changed_install` 的双层锁内部，保留已有安装事务主体。**

下面脚本是精确变换，不复制或重写原有 300 多行安装动作。运行后检查 diff 只有缩进、函数边界、三个明确插入点与新 wrapper。

```python
from pathlib import Path
import ast
import textwrap

path = Path('plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py')
source = path.read_text()
module = ast.parse(source)
node = next(item for item in module.body if isinstance(item, ast.FunctionDef)
            and item.name == '_changed_install')
lines = source.splitlines(keepends=True)
outer = next(item for item in node.body if isinstance(item, ast.With))
inner = outer.body[0]
assert isinstance(inner, ast.With)
body = textwrap.dedent(''.join(lines[inner.body[0].lineno - 1:inner.end_lineno]))
body = textwrap.indent(body, '    ')
body = body.replace('    install_id = uuid4()\n',
    '    install_id = uuid4()\n'
    '    if workflow_id is None:\n'
    '        raise InstallerError("changed installation requires workflow journal")\n'
    '    bind_receipt(state, context, workflow_id, install_id)\n', 1)
body = body.replace('        assert inspection.receipt_path is not None\n',
    '        assert inspection.receipt_path is not None\n'
    '        if workflow_id is not None:\n'
    '            doc = load_record(state, UpgradeRoots(roots.home, roots.codex_home), workflow_id)\n'
    '            if doc is not None and doc["install_id"] is None:\n'
    '                bind_receipt(state, context, workflow_id, UUID(inspection.receipt_path.stem))\n', 1)
body = body.replace(
    '        receipt = _install_receipt(context, state, refs, active, install_id, generation)\n',
    '        receipt = _install_receipt(context, state, refs, active, install_id, generation)\n'
    '        _lifecycle_closed(context)\n'
    '        record_recovery_usage(state, receipt, runtime_handoff)\n', 1)
needle = '                runtime_stage,\n                context.host.runner,\n            )\n'
assert needle in body
body = body.replace(needle, needle.replace(
    '                context.host.runner,\n',
    '                context.host.runner,\n                codex_home=roots.codex_home,\n') +
    '            ensure_usage_lock(state, runtime_post.dev, runtime_post.ino)\n', 1)
replacement = ('def _changed_install_locked(\n'
    '    context: _Context, fault: FaultInjector, state: SafeRoot,\n'
    '    workflow_id: str | None, runtime_handoff: dict[str, Any] | None,\n'
    ') -> dict[str, object]:\n'
    '    roots = context.roots\n' + body)
source = ''.join(lines[:node.lineno - 1]) + replacement + ''.join(lines[node.end_lineno:])
path.write_text(source)
```

在 cli.py 的 import 区增加：

```python
from contextlib import nullcontext
from typing import Any
from .upgrade_cleanup import RollbackUnavailable, assert_rollback_available
from .upgrade_handoff import LegacyHandoffRequired, RuntimeInUse, runtime_quiescence
from .upgrade_integration import (
    bind_receipt, finalize_install_locked, record_recovery_usage, select_install_workflow,
)
from .upgrade_locks import ensure_usage_lock, mutation_locks
from .upgrade_state import UpgradeRoots, load_record
```

在 `_changed_install_locked` 之前插入完整 wrapper：

```python
def _changed_install(context: _Context, fault: FaultInjector) -> dict[str, object]:
    roots = context.roots
    _ensure_mutation_roots(roots)
    upgrade_roots = UpgradeRoots(roots.home, roots.codex_home)
    with mutation_locks(upgrade_roots) as state:
        inspection = _inspection(context)
        workflow = select_install_workflow(state, context, exact=inspection.exact)
        workflow_id = None if workflow is None else workflow["id"]
        barrier = (nullcontext(None) if inspection.exact else runtime_quiescence(
            state, upgrade_roots, roots.runtime, context.host.codex_bin, context.handoff_id))
        with barrier as handoff:
            result = _changed_install_locked(context, fault, state, workflow_id, handoff)
    if workflow_id is not None:
        result["workflow_id"] = workflow_id
    return result


def finalize(args: argparse.Namespace) -> dict[str, object]:
    with _context(args) as context:
        roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
        with mutation_locks(roots) as state:
            result = finalize_install_locked(state, context, args.workflow_id, args._fault)
    return {"command": "finalize", **result}
```

在 `install` 的 `try: return _changed_install(...)` 后、现有 `except Exception` 前增加：

```diff
@@ def install(args: argparse.Namespace) -> dict[str, object]:
         try:
             return _changed_install(context, fault)
+        except (RuntimeInUse, LegacyHandoffRequired):
+            raise
         except Exception as exc:
```

安装异常恢复与显式 rollback 也是写入口，必须沿用 marketplace → installer 顺序。执行下面精确变换，只替换 install/rollback 内既有双层锁，保留 verify 的只读锁；每次变换后重新 parse AST，避免行号漂移：

```python
from pathlib import Path
import ast, textwrap
path = Path('plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py')
for function_name, roots_expression in [('install', 'context.roots'), ('rollback', 'roots')]:
    source=path.read_text();lines=source.splitlines(keepends=True);module=ast.parse(source)
    function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
    matches=[n for n in ast.walk(function) if isinstance(n,ast.With)
        and len(n.items)==1 and isinstance(n.items[0].context_expr,ast.Call)
        and ast.unparse(n.items[0].context_expr.func)=='SafeRoot.open'
        and len(n.body)==1 and isinstance(n.body[0],ast.With)
        and ast.unparse(n.body[0].items[0].context_expr.func)=='InstallerLock.acquire']
    assert len(matches)==1, function_name
    outer=matches[0];inner=outer.body[0];indent=' '*outer.col_offset
    body=textwrap.indent(textwrap.dedent(''.join(lines[inner.body[0].lineno-1:inner.end_lineno])),indent+'    ')
    replacement=(indent+'with mutation_locks(UpgradeRoots('+roots_expression+'.home, '
        +roots_expression+'.codex_home)) as state:\n'+body)
    updated=''.join(lines[:outer.lineno-1])+replacement+''.join(lines[outer.end_lineno:])
    ast.parse(updated);path.write_text(updated)
```

这两个发布前失败不能触发安装恢复。`finalize` 是独立 handler；不得从 install 的恢复 try 块内部调用它。常规工作流在用户启动 Blender 后显式自动调用 finalize。

- [ ] **Step 7: 加入回滚前置守卫和稳定退出语义。**

在 `_preflight_rollback` 函数体首行插入：

```python
assert_rollback_available(
    state, UpgradeRoots(roots.home, roots.codex_home), install_id=str(receipt.install_id)
)
```

`_parser` 的命令元组增加 `"finalize"`；在循环内增加：

```python
if command in {"install", "finalize"}:
    subparser.add_argument("--workflow-id", required=command == "finalize")
if command == "install":
    subparser.add_argument("--handoff-id")
```

`run_cli` 的 handler 字典加入 `"finalize": finalize`。在通用 `except InstallerError` 之前插入：

```diff
@@ def run_cli(argv: Sequence[str], fault: FaultInjector) -> int:
     try:
         result = handler(args)
+    except (RollbackUnavailable, RuntimeInUse, LegacyHandoffRequired) as exc:
+        print(json.dumps({"error": exc.code, "reason": str(exc)}, sort_keys=True, separators=(",", ":")))
+        return 1
     except InstallerError:
```

将输出结果后的最终 `return 0` 替换为：

```python
return 3 if result.get("status") == "cleanup_pending" else 0
```

`3` 表示新版本已验证但旧目录仍有保护/冲突项，不表示安装失败。工作流遇到这个结果保存证据，不能调用 rollback。

- [ ] **Step 8: 把 `.usage.json` 与原始 receipt 一起作为 recovery 使用协议证据。**

在 Task 4 `discover_candidates` 的 `row = {"key": key, ...}` 前插入下面完整块，并用 `known_lease` 替换该 row 的 `lease_protocol(target.pre)`；用 `proofs` 替换 `[proof, parent_proof]`：

```python
proofs = [proof, parent_proof]
known_lease = lease_protocol(target.pre)
try:
    usage, usage_proof = read_proof(state, PurePath("receipts", identity + ".usage.json"))
except FileNotFoundError:
    usage = None
if usage is not None:
    field = "runtime" if role is TargetRole.RUNTIME else "extension"
    if (usage.get("schema_version") != 1 or usage.get("install_id") != identity
            or usage.get("selected_blender_closed") is not True
            or usage.get(field) != target.pre.to_dict()):
        raise InstallerError("recovery usage proof mismatch")
    known_lease = True
    proofs.append(usage_proof)
```

该证据只能由 Task 5 的闭合 Blender 检查和 runtime 排他屏障下写入。旧 receipt 没有该证明时继续延后；不在扩展 zip 内添加 lease 标记，不凭文件年龄迁移。

- [ ] **Step 9: 执行实际 launcher 和原安装故障回归。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_launcher.py tests/distribution/test_upgrade_core.py tests/distribution/test_runtime.py tests/distribution/test_cli.py -k "not exact_registration" -q
```

预期：所有通过；runtime busy/legacy 无证据时 runtime、扩展、Codex 注册原镜像不变；仅 journal 的失败前态证据可以新建。安装主体仍保留既有阶段故障恢复；cleanup_pending 之后的错误不进入该恢复路径。

- [ ] **Step 10: 提交本 Task。**

```bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_handoff.py plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_integration.py plugins/blender-mcp-installer/scripts/blender_mcp_installer/runtime.py plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py plugins/blender-mcp-installer/scripts/blender_mcp_installer/upgrade_discovery.py tests/distribution/test_cli.py tests/distribution/fault_driver.py tests/distribution/test_upgrade_launcher.py
git commit -m "feat(installer): gate runtime publication and wire verified finalization"
```

### Task 6: 同进程完整编排、仅注册自动 finalize、脚本最早使用锁与工作流文案

**Files:**
- Modify: `plugins/blender-mcp-installer/scripts/project_marketplace.py:_prepare,_register,_verify,_parser,main`
- Modify: `plugins/blender-mcp-installer/scripts/install.py`
- Create: `plugins/blender-mcp-installer/.blender-mcp-usage-v1`
- Modify: `plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md`
- Modify: `plugins/blender-mcp-installer/skills/install-official-blender-mcp/references/workflow.md`
- Modify: `tests/distribution/test_cli.py:test_install_entrypoint_contains_only_main_delegation`
- Test: `tests/distribution/test_upgrade_workflow.py`

**Interfaces:**
- Consumes: Task 5 的 `_changed_install_locked`、`runtime_quiescence`、`finalize_register_locked`。
- Produces: `_run_workflow(args: argparse.Namespace, state: SafeRoot, roots: UpgradeRoots, projection: Path, context: Any = None) -> dict[str, Any]`；`project_marketplace.py prepare` 仅注册并自动 finalize；`project_marketplace.py upgrade` 完整注册+安装；`project_marketplace.py finalize --workflow-id UUID` 仅注册重试；`install.py finalize --workflow-id UUID` 完整现场验证后清理；`project_marketplace.py begin-handoff` 记录第一次迁移的正向进程证据；`project_marketplace.py restore` 在任何修改之前查清理失效标记。

- [ ] **Step 1: 写入发布屏障失败不得先注册的实际调用顺序回归。**

```python
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))
from blender_mcp_installer import cli
from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_handoff import RuntimeInUse
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root
import project_marketplace as marketplace


def test_runtime_busy_prevents_first_registration_mutation(tmp_path, monkeypatch):
    home, codex = tmp_path / 'home', tmp_path / 'codex'
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    projection = roots.projections / ('a' * 40)
    plugin = projection / 'plugins/blender-mcp-installer'
    (plugin / '.codex-plugin').mkdir(parents=True)
    (plugin / 'artifacts').mkdir()
    (plugin / '.codex-plugin/plugin.json').write_text(json.dumps({'name':'blender-mcp-installer','version':'2'}))
    (plugin / 'artifacts/manifest.json').write_text(json.dumps({'bundle_version':'1.0.0'}))
    calls = []
    monkeypatch.setattr(marketplace, 'inspect_registration', lambda *_args: (_ for _ in ()).throw(InstallerError('old registration')))
    monkeypatch.setattr(marketplace, 'profile_from_context', lambda _context: None)
    monkeypatch.setattr(cli, '_inspection', lambda _context: SimpleNamespace(exact=False))
    monkeypatch.setattr(marketplace, '_register', lambda *_args, **_kw: calls.append('register'))
    def occupied(*_args, **_kwargs):
        raise RuntimeInUse('busy')
    monkeypatch.setattr(marketplace, 'runtime_quiescence', occupied)
    args = SimpleNamespace(reviewed_commit='a' * 40, codex='/fake/codex', workflow_id=None, handoff_id=None)
    context = SimpleNamespace(roots=SimpleNamespace(runtime=home / '.local/share/blender-lab-mcp/runtime'))
    with state_root(roots) as state:
        with pytest.raises(RuntimeInUse):
            marketplace._run_workflow(args, state, roots, projection, context)
    assert calls == []
```

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_workflow.py -q
```

预期：`_run_workflow` 缺失。回归直接观察注册调用为零，不能只检查安装目标未变化。

- [ ] **Step 2: 添加本 Task 的完整 `_run_workflow` 与 finalize/handoff/restore 函数代码。**

在 project_marketplace.py 的 import 区加入：

```python
from contextlib import nullcontext
from dataclasses import replace
from uuid import UUID
from blender_mcp_installer.filesystem import InstallerError, NoOpFaultInjector, SafeRoot
from blender_mcp_installer.upgrade_cleanup import RollbackUnavailable, assert_rollback_available
from blender_mcp_installer.upgrade_discovery import discover_candidates, read_proof
from blender_mcp_installer.upgrade_handoff import RuntimeInUse, LegacyHandoffRequired, begin_handoff, runtime_quiescence
from blender_mcp_installer.upgrade_integration import finalize_register_locked, profile_from_context
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, mutation_locks
from blender_mcp_installer.upgrade_registration import inspect_registration
from blender_mcp_installer.upgrade_state import UpgradeRoots, load_any_record, load_record, new_record, record_ids, save_record, update_record, uuid_text
```

在 `_run_workflow` 中 `_changed_install_locked` 调用周围增加同锁、同屏障下的既有安装恢复；此范围不包括任何 finalize：

```python
try:
    result = cli._changed_install_locked(selected, args._fault, state, doc["id"], handoff)
except Exception:
    cli._lifecycle_closed(selected)
    recovered = cli.recover_active(
        selected.roots, selected.source_bundle, selected.blender, NoOpFaultInjector(),
        manifest_sha256=selected.manifest_sha256,
    )
    if recovered["recovered"] and not cli._inspection(selected).exact:
        current = load_record(state, roots, doc["id"])
        if current is not None and current["status"] == "awaiting_verification":
            update_record(state, roots, current, status="cancelled")
    raise
```

- [ ] **Step 3: 让 registration.<workflow-id> 在首次注册变更前绑定，并保持重试的 before 原始证据。**

给 `_register` 增加仅关键字参数：

```diff
@@ def _register(
     codex_home: Path,
+    *,
+    recovery_id: str,
 ) -> Path:
```

替换函数开始 `recovery = Path(tempfile.mkdtemp(...))` 到 `before, non_target_before = ...` 的块：

```python
recovery = recovery_root / ("registration." + uuid_text(recovery_id))
if recovery.exists():
    _private_owner_directory(recovery, os.getuid())
    before = json.loads((recovery / "before.json").read_bytes())
    non_target_before = json.loads((recovery / "non-target-before.json").read_bytes())
    current, non_target_current = _marketplace_snapshot(config)
    if non_target_current != non_target_before:
        raise InstallerError("registration evidence conflicts with non-target changes")
    if current != before and current.get("source") != str(projection):
        raise InstallerError("target registration changed outside pending workflow")
else:
    recovery.mkdir(mode=0o700)
    before, non_target_before = _marketplace_snapshot(config)
```

给 `_atomic_write` 的 `os.replace` 成功路径增加父目录同步，使用它已有的父目录安全检查：

```python
parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    os.fsync(parent_fd)
finally:
    os.close(parent_fd)
```

将生成的 `RESTORE.txt` 首条文字替换为：

```python
restore_lines = [
    "Read the upgrades journal before any recovery action; cleanup_pending/complete may retire local program rollback.",
    "Use project_marketplace.py restore with this recovery directory and recorded HOME/CODEX_HOME/CODEX_BIN.",
    "This operation restores only marketplace source. It does not restore the installed plugin version or cache.",
    f"CODEX_BIN: {codex}",
    f"HOME: {home}",
    f"CODEX_HOME: {codex_home}",
]
```

删除随后输出裸 `plugin marketplace remove/add` 的旧手工配方，before.json 保留原值。记录清理意图时 journal 的 retired_registrations 是权威能力失效记录；首次删除前还在对应 RESTORE.txt 旁持久化 RECOVERY_STATUS.json，写入失败不开始删除。旧文本不能绕过新的 restore 入口。

- [ ] **Step 4: `_prepare` 保留信任探测前半段，替换从 `with _codex_lock` 到函数结束的精确后半段。**

```python
roots = UpgradeRoots(home, codex_home)
with mutation_locks(roots) as state:
    projection = _materialize(
        projection_parent, private_git_dir, git_safe_home,
        args.reviewed_commit, trusted_checksums,
    )
    if args.command == "upgrade":
        from blender_mcp_installer import cli
        args.expected_distribution_commit = args.reviewed_commit
        args._fault = NoOpFaultInjector()
        args.codex = Path(args.codex)
        with cli._context(args) as context:
            if (context.roots.home, context.roots.codex_home) != (roots.home, roots.codex_home):
                raise InstallerError("full workflow roots differ from verified host environment")
            result = _run_workflow(args, state, roots, projection, context)
    else:
        result = _run_workflow(args, state, roots, projection)
result.setdefault("marketplace", MARKETPLACE_NAME)
result.setdefault("projection", str(projection))
if "workflow_id" in result:
    result.setdefault("recovery", str(roots.state / "marketplace-recovery" / ("registration." + result["workflow_id"])))
print(json.dumps(result, sort_keys=True))
if result.get("status") == "cleanup_pending":
    raise SystemExit(3)
```

`_prepare_roots` 只准备受验证根，不获取另一把 state 锁。完整升级同进程持有 marketplace/state/runtime 三者直到注册+安装发布结束；`runtime_quiescence` 必须先于 `_register`，不能用两个独立 shell 命令的“提前检查”替代跨阶段锁。

- [ ] **Step 5: 用文末 `project_functions.py` 中完整 `_verify` 替换旧函数，并增加命令路由。**

`verify.add_argument("--recovery", required=True)` 改为 `verify.add_argument("--recovery")`。精确 cold no-op 无 registration recovery 时仍可独立只读验证；指定 recovery 时安全读取原 non-target-before 并比对当前配置。该入口不写 journal、注册证据或目标目录，不调用 finalize。

`_parser` 的 prepare parser 构造改为 `for command in ("prepare", "upgrade")`，为两者添加现有全部 prepare 参数，再添加：

```python
prepare.add_argument("--workflow-id")
if command == "upgrade":
    from blender_mcp_installer import cli
    prepare.add_argument("--bundle-root", required=True, type=cli._bundle_root)
    prepare.add_argument("--blender", required=True, type=cli._executable)
    prepare.add_argument("--uv", required=True, type=cli._executable)
    prepare.add_argument("--handoff-id")
    for flag in ("allow-extension-install", "allow-online-access", "allow-localhost-bridge", "approve-arbitrary-python"):
        prepare.add_argument("--" + flag, required=True, action="store_true")
```

现有 verify parser 除 recovery 改为可选外保留。追加：

```python
for command in ("finalize", "begin-handoff", "restore"):
    command_parser = commands.add_parser(command)
    for name in ("codex", "home", "codex-home"):
        command_parser.add_argument("--" + name, required=True)
    if command == "finalize":
        command_parser.add_argument("--workflow-id", required=True)
    if command == "restore":
        command_parser.add_argument("--recovery", required=True)
```

用完整 main 替换旧二分派发：

```python
def main() -> None:
    args = _parser().parse_args()
    handlers = {"prepare": _prepare, "upgrade": _prepare, "verify": _verify,
                "finalize": _finalize_registration, "begin-handoff": _begin_handoff,
                "restore": _restore_evidence}
    handlers[args.command](args)
```

在底部通用 except 之前加入以下带模块上下文的分支；模块作用域用 SystemExit，不复制 run_cli 的 return：

```diff
@@ if __name__ == "__main__":
     try:
         main()
+    except (RuntimeInUse, LegacyHandoffRequired, RollbackUnavailable) as exc:
+        print(json.dumps({"error": exc.code, "reason": str(exc)}, sort_keys=True))
+        raise SystemExit(1) from None
     except Exception as exc:
```

`SystemExit(3)` 不被 Exception 捕获。

- [ ] **Step 6: 两个脚本在导入安装器模块前获取缓存目录共享 lease。**

把本 Task 的完整“脚本入口 prelude”复制到 install.py 与 project_marketplace.py 文件开头；project_marketplace.py 原有 `from __future__ import annotations` 仍须位于文档字符串之后、普通语句之前。该 prelude 只用标准库，不先 import upgrade_locks；它持有文件描述符到进程退出。随后再导入原有 installer 模块。创建协议文件：

```text
inode-v1
```

将 `tests/distribution/test_cli.py:test_install_entrypoint_contains_only_main_delegation` 的旧“只有 main 委托”断言替换为实际入口子进程验证：busy 使用锁时不能执行后续 import，锁释放后 `--help` 成功且不存在写 journal 或删除副作用。

- [ ] **Step 7: 同步唯一实际 workflow 文档与技能模式表。**

把 workflow.md 完整安装模式的 `PERSISTENT_MARKETPLACE → INSTALL` 两个独立 shell 步骤替换为下列统一调用；复用该文档已有信任变量和四项授权，不另造全局安装目录。

```bash
run_uv_bootstrap
NORMAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
UPGRADE_JSON="$("$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/project_marketplace.py" upgrade \
  --private-git-dir "$PRIVATE_GIT_DIR" --git-safe-home "$GIT_SAFE_HOME" \
  --reviewed-commit "$EXPECTED_DISTRIBUTION_COMMIT" --trusted-checksums "$TRUSTED_CHECKSUMS" \
  --bundle-root "$BUNDLE_ROOT" \
  --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME" \
  --blender "$BLENDER_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access --allow-localhost-bridge --approve-arbitrary-python)"
WORKFLOW_ID="$("$PYTHON_BIN" -I -c 'import json,sys,uuid; value=json.loads(sys.argv[1]).get("workflow_id"); print("" if value is None else str(uuid.UUID(value)))' "$UPGRADE_JSON")"
PERSISTENT_MARKETPLACE_ROOT="$("$PYTHON_BIN" -I -c 'import json,sys; print(json.loads(sys.argv[1])["projection"])' "$UPGRADE_JSON")"
```

首次无 lease 迁移先在新的受审脚本上运行 `begin-handoff` 保存输出，外部终端确认正向记录的客户端全部退出后，将返回的 handoff_id 通过 `--handoff-id` 传入 upgrade。旧缓存没有协作使用证据时继续 pending；不能仅因 runtime 交接成功就声称旧 Codex 任务已重载。

保留受审 TRUSTED_DISTRIBUTION_ROOT、PRIVATE_GIT_DIR 与校验文件直到现场 finalize 结束。用户启动选定 Blender 后先执行既有只读 verify，再自动执行：

```bash
if test -n "$WORKFLOW_ID"; then
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
    --no-python-downloads --no-sync \
    python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
    "$PLUGIN_ROOT/scripts/install.py" finalize \
    --bundle-root "$BUNDLE_ROOT" \
    --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
    --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
    --workflow-id "$WORKFLOW_ID"
fi
```

从任一 prepare/upgrade 的 JSON 用 `.get("recovery", "")` 解析 REGISTRATION_RECOVERY_DIR，不能继续使用旧的必需字段索引。随后执行原有 TRUST_CLEANUP，并将 PERSISTENT_MARKETPLACE_VERIFY 整块替换为：

```bash
REGISTRATION_VERIFY_ARGS=()
if test -n "${REGISTRATION_RECOVERY_DIR:-}"; then
  REGISTRATION_VERIFY_ARGS+=(--recovery "$REGISTRATION_RECOVERY_DIR")
fi
PERSISTENT_SCRIPTS="$PERSISTENT_MARKETPLACE_ROOT/plugins/blender-mcp-installer/scripts"
"$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" "$PERSISTENT_SCRIPTS"   "$PERSISTENT_SCRIPTS/project_marketplace.py" verify   --projection "$PERSISTENT_MARKETPLACE_ROOT" "${REGISTRATION_VERIFY_ARGS[@]}"   --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME"
```

这保留包导入所需的受审脚本路径；不再直接以 `python -I script.py` 执行含包导入的新版脚本。WORKFLOW_ID 必须从此次 upgrade JSON 输出读取并确认 UUID；不复用不匹配主机或模式的旧值。`status=cleanup_pending`、exit 3 仍执行信任临时目录清理并保留 journal/恢复记录；下一次 install/register/finalize 自动重试。

仅注册配方仍使用 `prepare`，该入口现在自动注册验证+finalize；不传 Blender/uv 参数、不触碰 runtime/extension。技能模式表加入 `finalize` 和 `begin-handoff`，说明权限已由用户此次安装/升级授权覆盖，常规自动清理不重复询问。

- [ ] **Step 8: 验证工作流和插件分发结构，再提交。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_upgrade_workflow.py tests/distribution/test_plugin_contract.py tests/distribution/test_cli.py -q
.venv/bin/python scripts/update_installer_version.py
.venv/bin/python scripts/update_installer_version.py --check
git diff --check
git add plugins/blender-mcp-installer tests/distribution/test_upgrade_workflow.py tests/distribution/test_cli.py
git commit -m "feat(installer): automate verified cleanup in install and register workflows"
```

版本由现有脚本生成，不能把计划编写时的时间戳硬编码到发行版中。新增脚本、协议标记与文档均须进入插件分发内容哈希。

### Task 7: F20 分开验证固定版完整性与远端最新性，并完成整体门禁

**Files:**
- Create: `scripts/check_official_upstream.py`
- Modify: `scripts/checks.sh:RELEASE block`
- Modify: `tests/distribution/test_bundle.py`
- Modify: `docs/validation.md`

**Interfaces:**
- Consumes: 现有 `blender_mcp_installer.bundle.UPSTREAM_COMMIT` 和固定输入的 `build_official_blender_mcp_distribution.py`。
- Produces: `classify_upstream(pinned: str, remote: str, *, require_latest: bool) -> tuple[dict[str, object], int]`；`VERIFY_DISTRIBUTION_INTEGRITY=1` 触发固定版重建与字节比较；`RELEASE=1` 同时保留远端最新性门禁。两项结果独立输出，不能把 outdated 标记写成 integrity_failed。

- [ ] **Step 1: 写入固定旧版仍允许通过完整性的回归。**

```python
from scripts.check_official_upstream import classify_upstream


def test_fixed_release_integrity_does_not_require_latest_upstream():
    result, code = classify_upstream('a' * 40, 'b' * 40, require_latest=False)
    assert code == 0
    assert result == {'check': 'upstream_freshness', 'pinned': 'a' * 40,
                      'remote': 'b' * 40, 'status': 'outdated', 'required': False}
    release, code = classify_upstream('a' * 40, 'b' * 40, require_latest=True)
    assert code == 1 and release['status'] == 'outdated'
```

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_bundle.py -k fixed_release_integrity -q
```

预期：新函数缺失。

- [ ] **Step 2: 创建完整最新性检查脚本。**

```python
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def classify_upstream(pinned: str, remote: str, *, require_latest: bool) -> tuple[dict[str, object], int]:
    if not re.fullmatch(r'[0-9a-f]{40}', pinned) or not re.fullmatch(r'[0-9a-f]{40}', remote):
        raise ValueError('upstream commit must be 40 lowercase hex characters')
    current = pinned == remote
    return ({'check': 'upstream_freshness', 'pinned': pinned, 'remote': remote,
             'status': 'current' if current else 'outdated', 'required': require_latest},
            int(require_latest and not current))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-latest', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'plugins/blender-mcp-installer/scripts'))
    from blender_mcp_installer.bundle import UPSTREAM_COMMIT
    result = subprocess.run(['/usr/bin/git', 'ls-remote', '--exit-code',
        'https://projects.blender.org/lab/blender_mcp.git', 'refs/heads/main'],
        check=True, capture_output=True, text=True, timeout=30,
        env={'PATH':'/usr/bin:/bin','HOME':'/var/empty','LC_ALL':'C',
             'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null'})
    fields = result.stdout.strip().split('\t')
    if len(fields) != 2 or fields[1] != 'refs/heads/main':
        raise ValueError('unexpected upstream reference response')
    report, code = classify_upstream(UPSTREAM_COMMIT, fields[0], require_latest=args.require_latest)
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 3: 精确拆开 checks.sh 的 gate，保留固定输入构建与发布政策。**

将原 `if test "${RELEASE:-0}" = 1; then` 替换为：

```diff
-if test "${RELEASE:-0}" = 1; then
+if test "${RELEASE:-0}" = 1 || test "${VERIFY_DISTRIBUTION_INTEGRITY:-0}" = 1; then
```

将原 `UPSTREAM_COMMIT=...`、`REMOTE_MAIN=...` 和二者相等的 test 块替换为：

```bash
if test "${RELEASE:-0}" = 1; then
  "$PWD_ROOT/.venv/bin/python" -I scripts/check_official_upstream.py --require-latest
else
  "$PWD_ROOT/.venv/bin/python" -I scripts/check_official_upstream.py
fi
```

构建器继续从固定 `UPSTREAM_COMMIT` 提取源码，维持现有 SHA256SUMS/manifest/wheel/zip/lock 五文件逐字节比较。在 `cmp` 循环成功之后、`RELEASE CHECKS PASSED` 之前增加：

```bash
echo '{"check":"fixed_distribution_integrity","status":"passed"}'
```

`docs/validation.md` 添加两条明确命令及区别：

```bash
VERIFY_DISTRIBUTION_INTEGRITY=1 OFFICIAL_MCP_SOURCE="$OFFICIAL_MCP_SOURCE" BLENDER_BIN="$BLENDER_BIN" bash scripts/checks.sh
RELEASE=1 OFFICIAL_MCP_SOURCE="$OFFICIAL_MCP_SOURCE" BLENDER_BIN="$BLENDER_BIN" bash scripts/checks.sh
```

第一条允许远端 main 已更新但固定版重建一致；第二条要求固定提交仍是远端 main。网络错误单列为最新性不可验证，不报告为固定版内容损坏。

- [ ] **Step 4: 完成最小回归与一轮全量检查。**

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/distribution/test_bundle.py -k fixed_release_integrity -q
bash scripts/checks.sh
```

预期：测试通过且出现 `ALL CHECKS PASSED`。普通计划执行不伪造 runtime 发行现场证据；只有实际发行任务才追加 RELEASE=1 与文档规定现场门禁。

- [ ] **Step 5: 最后一次源码/文档修改后构建并检查 Graft，检查通过后提交。**

```bash
graft build .
graft check .
git diff --check
git add scripts/check_official_upstream.py scripts/checks.sh tests/distribution/test_bundle.py docs/validation.md
git commit -m "fix(validation): distinguish pinned integrity from upstream freshness"
```

预期：graft check 退出码 0；不暂存 `graft/`。若此后修改任何仓库文件，重新运行 graft build/check。交付列出新版验证、物理清理、遗留保护项三个独立结论。


## Task 5/6 的完整实现块

### upgrade_handoff.py

```python
from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Any, Iterator
from uuid import UUID, uuid4

from blender_mcp_installer.filesystem import (InstallerError, NoOpFaultInjector, SafeRoot,
    TargetRef, capture_file, capture_tree, write_atomic_json)
from blender_mcp_installer.model import ImageState, TreeImage
from blender_mcp_installer.upgrade_discovery import lease_protocol
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, usage_lock
from blender_mcp_installer.upgrade_registration import read_owned_bytes
from blender_mcp_installer.upgrade_state import UpgradeRoots, uuid_text


class RuntimeInUse(InstallerError):
    code = "runtime_in_use"


class LegacyHandoffRequired(InstallerError):
    code = "legacy_handoff_required"


def process_snapshot(roots: UpgradeRoots, runtime: Path, codex: Path) -> tuple[dict[str, str], ...]:
    output = subprocess.run(["/bin/ps", "-axo", "pid=,uid=,lstart=,command="],
                            check=True, capture_output=True, text=True, timeout=15).stdout
    markers = (str(runtime), str(roots.caches), str(codex),
               "/Applications/ChatGPT.app/", "/Applications/Codex.app/")
    records = []
    for line in output.splitlines():
        fields = line.strip().split(None, 7)
        if len(fields) != 8 or not fields[0].isdigit() or not fields[1].isdigit():
            raise LegacyHandoffRequired("unrecognized process inventory")
        command = fields[7]
        tokens = shlex.split(command)
        if (int(fields[0]) != os.getpid() and int(fields[1]) == os.getuid()
                and any(marker in token for token in tokens[:2] for marker in markers)):
            records.append({"pid": fields[0], "uid": fields[1],
                            "started": " ".join(fields[2:7]), "command_sha256": hashlib.sha256(command.encode()).hexdigest()})
    return tuple(sorted(records, key=lambda row: int(row["pid"])))


def begin_handoff(state: SafeRoot, roots: UpgradeRoots, runtime: Path,
                  codex: Path) -> dict[str, Any]:
    processes = process_snapshot(roots, runtime, codex)
    if not processes:
        raise LegacyHandoffRequired("begin handoff requires positively identified supported clients")
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        image = capture_tree(home, runtime.relative_to(roots.home))
    if image.state is ImageState.ABSENT:
        raise LegacyHandoffRequired("legacy runtime is absent")
    identifier = str(uuid4())
    fd = state.open_directory(PurePath("handoffs"), create=True)
    os.close(fd)
    doc = {"schema_version": 1, "id": identifier, "uid": os.getuid(),
           "home": str(roots.home), "codex_home": str(roots.codex_home),
           "runtime": str(runtime), "expected": image.to_dict(),
           "scope": "cooperating-managed-clients", "processes": list(processes)}
    ref = TargetRef(state, PurePath("handoffs", identifier + ".json"))
    write_atomic_json(ref, capture_file(state, ref.relative), doc, UUID(identifier), fault=NoOpFaultInjector())
    return {"handoff_id": identifier, "stop_required": list(processes),
            "scope": "cooperating-managed-clients"}


def verify_handoff(state: SafeRoot, roots: UpgradeRoots, runtime: Path,
                   codex: Path, identifier: str, image: TreeImage) -> dict[str, Any]:
    identifier = uuid_text(identifier)
    raw, proof = read_owned_bytes(TargetRef(state, PurePath("handoffs", identifier + ".json")))
    doc = json.loads(raw)
    if (type(doc) is not dict or set(doc) != {"schema_version", "id", "uid", "home", "codex_home", "runtime", "expected", "scope", "processes"}
            or type(doc["schema_version"]) is not int or doc["schema_version"] != 1
            or doc["id"] != identifier or doc["uid"] != os.getuid()
            or doc["home"] != str(roots.home) or doc["codex_home"] != str(roots.codex_home)
            or doc["runtime"] != str(runtime) or TreeImage.from_dict(doc["expected"]) != image
            or doc["scope"] != "cooperating-managed-clients"
            or type(doc["processes"]) is not list or not doc["processes"]):
        raise LegacyHandoffRequired("handoff identity mismatch")
    # Positive pre-stop records are required in addition to an empty current supported inventory.
    for record in doc["processes"]:
        if (type(record) is not dict or set(record) != {"pid", "uid", "started", "command_sha256"}
                or record["uid"] != str(os.getuid()) or not record["pid"].isdigit()):
            raise LegacyHandoffRequired("invalid handoff process identity")
        try:
            os.kill(int(record["pid"]), 0)
        except ProcessLookupError:
            pass
        else:
            raise LegacyHandoffRequired("recorded process still exists or PID was reused")
    if process_snapshot(roots, runtime, codex):
        raise LegacyHandoffRequired("supported clients restarted; external maintenance terminal required")
    return {"relative": "handoffs/" + identifier + ".json", "expected": proof.to_dict()}


@contextmanager
def runtime_quiescence(state: SafeRoot, roots: UpgradeRoots, runtime: Path,
                       codex: Path, handoff_id: str | None = None) -> Iterator[dict[str, Any] | None]:
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        image = capture_tree(home, runtime.relative_to(roots.home))
    if image.state is ImageState.ABSENT:
        yield None
        return
    proof = None
    if not lease_protocol(image):
        if handoff_id is None:
            raise LegacyHandoffRequired("legacy runtime requires external maintenance handoff")
        proof = verify_handoff(state, roots, runtime, codex, handoff_id, image)
        ensure_usage_lock(state, image.dev, image.ino)
    with usage_lock(state, image.dev, image.ino, exclusive=True) as acquired:
        if not acquired:
            raise RuntimeInUse("managed runtime is in use; targets unchanged")
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            if capture_tree(home, runtime.relative_to(roots.home)) != image:
                raise RuntimeInUse("runtime changed before handoff")
        yield {"image": image.to_dict(), "legacy_proof": proof}
```

### launcher_function.py

```python
def _launcher_source(environment: Mapping[str, str]) -> bytes:
    clean = dict(sorted(environment.items()))
    bootstrap = Path(clean.pop("BLENDER_MCP_BOOTSTRAP_PYTHON"))
    codex_home = Path(clean.pop("BLENDER_MCP_CODEX_HOME"))
    if not codex_home.is_absolute() or ".." in codex_home.parts:
        raise InstallerError("Codex home must be an absolute owned root")
    if not bootstrap.is_absolute() or ".." in bootstrap.parts:
        raise InstallerError("bootstrap Python must be an absolute external executable")
    managed = Path(clean["HOME"]) / ".local/share/blender-lab-mcp"
    caches = codex_home / "plugins/cache/official-blender-mcp/blender-mcp-installer"
    if bootstrap.is_relative_to(managed) or bootstrap.is_relative_to(caches):
        raise InstallerError("bootstrap Python cannot live in a retired program tree")
    shell_environment = " ".join(f"{key}={shlex.quote(value)}" for key, value in clean.items())
    gate = r'''
import fcntl
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

def directory(path):
    if not path.is_absolute() or '..' in path.parts:
        raise SystemExit(75)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise

def json_file(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > 33554432:
            raise SystemExit(75)
        return json.loads(stream.read(33554433))

runtime = Path(__file__).absolute().parent.parent
root_fd = directory(runtime)
root_info = os.fstat(root_fd)
state_fd = directory(Path(environment['HOME']) / '.local/state/blender-mcp-installer')
usage_fd = os.open('usage', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=state_fd)
name = hashlib.sha256(f'tree:{root_info.st_dev}:{root_info.st_ino}'.encode()).hexdigest() + '.lock'
lease_fd = os.open(name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=usage_fd)
lease_info = os.fstat(lease_fd)
if (not stat.S_ISREG(lease_info.st_mode) or lease_info.st_uid != os.getuid()
        or stat.S_IMODE(lease_info.st_mode) != 0o600 or lease_info.st_nlink != 1):
    raise SystemExit(75)
try:
    fcntl.flock(lease_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit(75)
check_fd = directory(runtime)
if (os.fstat(check_fd).st_dev, os.fstat(check_fd).st_ino) != (root_info.st_dev, root_info.st_ino):
    raise SystemExit(75)
active = json_file(state_fd, 'active.json')
identifier = active.get('install_id')
import uuid
if not isinstance(identifier, str) or str(uuid.UUID(identifier)) != identifier:
    raise SystemExit(75)
receipts_fd = os.open('receipts', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=state_fd)
receipt = json_file(receipts_fd, identifier + '.json')
if receipt.get('status') != 'installed' or receipt.get('install_id') != identifier:
    raise SystemExit(75)
matching = [row for row in receipt.get('targets', []) if row.get('role') == 'runtime']
if len(matching) != 1 or matching[0].get('path') != str(runtime):
    raise SystemExit(75)
post = matching[0].get('install_post') or {}
if (post.get('dev'), post.get('ino')) != (root_info.st_dev, root_info.st_ino):
    raise SystemExit(75)
for fd in (root_fd, state_fd, usage_fd, check_fd, receipts_fd):
    os.close(fd)
os.set_inheritable(lease_fd, True)
runtime_python = runtime / 'bin/python'
entry_point = runtime / 'bin/blender-mcp'
os.execve(str(runtime_python), [str(runtime_python), '-B', str(entry_point), *sys.argv[1:]], environment)
'''
    return ("#!/bin/sh\n"
            f"'''exec' /usr/bin/env -i {shell_environment} {shlex.quote(str(bootstrap))} \"$0\" \"$@\"\n"
            "' '''\n"
            f"environment = {clean!r}\n" + gate).encode()
```

### upgrade_integration.py

```python
from __future__ import annotations

import json
import os
from pathlib import Path, PurePath
from typing import Any
from uuid import UUID

from blender_mcp_installer.filesystem import (InstallerError, NoOpFaultInjector, SafeRoot,
    TargetRef, capture_file, capture_tree, write_atomic_json)
from blender_mcp_installer.model import ImageState, Receipt, TargetRole
from blender_mcp_installer.upgrade_cleanup import cleanup_result, finalize_record
from blender_mcp_installer.upgrade_discovery import current_paths, discover_candidates, other_references
from blender_mcp_installer.upgrade_locks import ensure_usage_lock
from blender_mcp_installer.upgrade_registration import inspect_registration
from blender_mcp_installer.upgrade_state import (UpgradeRoots, load_any_record, load_record, new_record,
    record_ids, save_record, update_record)


def desired_from_context(context: Any) -> dict[str, str]:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    path = context.roots.source_distribution_root / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
    manifest = json.loads(path.read_bytes())
    return {"commit": context.distribution_commit, "manifest_sha256": context.manifest_sha256,
            "bundle_version": context.verified.manifest.bundle_version,
            "plugin_version": manifest["version"], "projection": str(roots.projections / context.distribution_commit)}


def profile_from_context(context: Any) -> dict[str, str]:
    profile = context.roots.blender
    return {"executable": str(profile.executable), "architecture": profile.architecture,
            "version": profile.version, "resources": str(profile.user_resources),
            "config": str(profile.user_config), "extensions": str(profile.user_extensions)}


def select_install_workflow(state: SafeRoot, context: Any, *, exact: bool) -> dict[str, Any] | None:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    desired = desired_from_context(context)
    profile = profile_from_context(context)
    requested = context.workflow_id
    if requested is not None:
        doc = load_record(state, roots, requested, recover=True)
        if (doc is None or doc["mode"] != "install" or doc["desired"] != desired
                or doc["profile"] not in (None, profile)
                or doc["status"] in {"complete", "cancelled"}):
            raise InstallerError("workflow does not match selected installation")
        return doc
    matches = []
    for identifier in record_ids(state):
        doc = load_any_record(state, roots, identifier, recover=True)
        if (doc is not None and doc["codex_home"] == str(roots.codex_home) and doc["mode"] == "install" and doc["desired"] == desired
                and doc["profile"] == profile
                and doc["status"] in {"awaiting_verification", "cleanup_pending"}):
            matches.append(doc)
    if len(matches) > 1:
        raise InstallerError("multiple pending workflows require an explicit workflow ID")
    if matches:
        return matches[0]
    if exact:
        return None
    doc = new_record(roots, "install", desired)
    doc["profile"] = profile
    return save_record(state, roots, None, doc)


def bind_receipt(state: SafeRoot, context: Any, workflow_id: str, install_id: UUID) -> None:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    doc = load_record(state, roots, workflow_id)
    if doc is None or doc["status"] != "awaiting_verification":
        raise InstallerError("installation cannot publish into this cleanup state")
    update_record(state, roots, doc, install_id=str(install_id), profile=profile_from_context(context))


def record_recovery_usage(state: SafeRoot, receipt: Receipt,
                          runtime_handoff: dict[str, Any] | None) -> None:
    runtime = next(item.pre for item in receipt.targets if item.role is TargetRole.RUNTIME)
    extension = next(item.pre for item in receipt.targets if item.role is TargetRole.BLENDER_EXTENSION)
    if runtime.state is ImageState.PRESENT and (
            runtime_handoff is None or runtime_handoff["image"] != runtime.to_dict()):
        raise InstallerError("runtime handoff does not match prepared receipt")
    for image in (runtime, extension):
        if image.state is ImageState.PRESENT:
            ensure_usage_lock(state, image.dev, image.ino)
    document = {"schema_version": 1, "install_id": str(receipt.install_id),
                "runtime": runtime.to_dict(), "extension": extension.to_dict(),
                "runtime_handoff": runtime_handoff, "selected_blender_closed": True}
    reference = TargetRef(state, PurePath("receipts", str(receipt.install_id) + ".usage.json"))
    write_atomic_json(reference, capture_file(state, reference.relative), document,
                      receipt.install_id, fault=NoOpFaultInjector())


def installation_fingerprint(state: SafeRoot, context: Any,
                             doc: dict[str, Any]) -> tuple[Any, ...]:
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    registration = inspect_registration(context.host.codex_bin, roots, doc["desired"])
    active = capture_file(state, PurePath("active.json"))
    receipt = capture_file(state, PurePath("receipts", doc["install_id"] + ".json"))
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        runtime = capture_tree(home, context.roots.runtime.relative_to(roots.home))
    boundary = context.roots.blender.user_resources
    with SafeRoot.open(boundary, os.getuid(), boundary) as resources:
        extension = capture_tree(resources, context.roots.extension_target.relative_to(boundary))
    return (registration, active, receipt, runtime, extension)


def finalize_install_locked(state: SafeRoot, context: Any, workflow_id: str, fault: Any) -> dict[str, Any]:
    from blender_mcp_installer.verification import OfficialMCPProbe, verify_live
    roots = UpgradeRoots(context.roots.home, context.roots.codex_home)
    expected = desired_from_context(context)
    profile = profile_from_context(context)
    verified_fingerprint: tuple[Any, ...] | None = None
    def validate(doc: dict[str, Any]) -> tuple[Path, ...]:
        if doc["mode"] != "install" or doc["desired"] != expected or doc["profile"] != profile:
            raise InstallerError("finalize installation identity mismatch")
        if doc["install_id"] is None or doc["registration"] is None or doc["registration"]["state"] != "registered":
            raise InstallerError("finalize requires linked registration and installed receipt")
        nonlocal verified_fingerprint
        current = installation_fingerprint(state, context, doc)
        if verified_fingerprint is None:
            verify_live(context.source_bundle, context.roots, context.blender, context.host,
                        context.roots.receipt(UUID(doc["install_id"])), context.host.env,
                        OfficialMCPProbe(context.roots.runtime / "bin/python"))
            if installation_fingerprint(state, context, doc) != current:
                raise InstallerError("installation changed during live verification")
            verified_fingerprint = current
        elif current != verified_fingerprint:
            raise InstallerError("verified installation snapshot changed during cleanup")
        return current_paths(roots, doc)
    doc = finalize_record(state, roots, workflow_id, validate,
                          lambda doc: discover_candidates(state, roots, doc),
                          lambda doc: other_references(state, roots, doc), fault)
    return cleanup_result(doc)


def finalize_register_locked(state: SafeRoot, roots: UpgradeRoots,
                             workflow_id: str, codex: Path, fault: Any = None) -> dict[str, Any]:
    def validate(doc: dict[str, Any]) -> tuple[Path, ...]:
        if doc["mode"] != "register" or doc["registration"] is None or doc["registration"]["state"] != "registered":
            raise InstallerError("finalize registration identity mismatch")
        inspect_registration(codex, roots, doc["desired"])
        return current_paths(roots, doc)
    doc = finalize_record(state, roots, workflow_id, validate,
                          lambda doc: discover_candidates(state, roots, doc),
                          lambda doc: other_references(state, roots, doc), fault)
    return cleanup_result(doc)
```

### project_functions.py

```python
def _run_workflow(args: argparse.Namespace, state: SafeRoot, roots: UpgradeRoots,
                  projection: Path, context: Any = None) -> dict[str, Any]:
    plugin = json.loads((projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json").read_bytes())
    bundle = json.loads((projection / "plugins/blender-mcp-installer/artifacts/manifest.json").read_bytes())
    desired = {"commit": args.reviewed_commit, "bundle_version": bundle["bundle_version"],
               "manifest_sha256": hashlib.sha256((projection / "plugins/blender-mcp-installer/artifacts/manifest.json").read_bytes()).hexdigest(),
               "plugin_version": plugin["version"], "projection": str(projection)}
    profile = None if context is None else profile_from_context(context)
    mode = "register" if context is None else "install"
    requested = getattr(args, "workflow_id", None)
    matches = []
    for identifier in record_ids(state):
        doc = load_any_record(state, roots, identifier, recover=True)
        if doc is not None and doc["codex_home"] == str(roots.codex_home) and ((requested is not None and doc["id"] == requested)
                or (requested is None and doc["mode"] == mode and doc["desired"] == desired
                    and doc["profile"] == profile and doc["status"] in {"awaiting_verification", "cleanup_pending"})):
            matches.append(doc)
    if len(matches) > 1 or (requested is not None and not matches):
        raise InstallerError("workflow selection is not unique")
    doc = matches[0] if matches else None
    if doc is not None and (doc["mode"] != mode or doc["desired"] != desired
            or doc["profile"] != profile or doc["status"] in {"complete", "cancelled"}):
        raise InstallerError("workflow identity mismatch")
    try:
        inspect_registration(Path(args.codex), roots, desired)
        registration_exact = True
    except (InstallerError, subprocess.SubprocessError, OSError, ValueError):
        registration_exact = False
    from blender_mcp_installer import cli
    inspection = None if context is None else cli._inspection(context)
    if doc is None and registration_exact and (inspection is None or inspection.exact):
        migration = new_record(roots, mode, desired)
        migration["profile"] = profile
        if inspection is not None:
            if inspection.receipt_path is None:
                raise InstallerError("exact installation lacks receipt identity")
            migration["install_id"] = str(UUID(inspection.receipt_path.stem))
        candidates, findings = discover_candidates(state, roots, migration)
        if not candidates:
            return {"changed": False, "no_op": True, "projection": str(projection),
                    "unverified": findings, "all_old_versions_removed": not findings}
        doc = save_record(state, roots, None, migration)
        doc = update_record(state, roots, doc, registration={"id": doc["id"], "state": "prepared"})
        recovery = roots.state / "marketplace-recovery" / ("registration." + doc["id"])
        recovery.mkdir(mode=0o700)
        before, others = _marketplace_snapshot(roots.codex_home / "config.toml")
        if before.get("source") != str(projection):
            raise InstallerError("registration changed during migration binding")
        for name, value in (("before.json", before), ("after.json", before),
                            ("non-target-before.json", others), ("non-target-after.json", others)):
            _atomic_json(recovery / name, value)
        _atomic_write(recovery / "RESTORE.txt", b"Inspect the upgrade journal before source-only restore. Plugin program rollback may be retired.\n")
        doc = update_record(state, roots, doc, registration={"id": doc["id"], "state": "registered"})
    barrier = (nullcontext(None) if inspection is None or inspection.exact else runtime_quiescence(
        state, roots, context.roots.runtime, Path(args.codex), getattr(args, "handoff_id", None)))
    with barrier as handoff:
        if doc is None:
            doc = new_record(roots, mode, desired)
            doc["profile"] = profile
            doc = save_record(state, roots, None, doc)
        if doc["status"] == "awaiting_verification":
            if doc["registration"] is None or doc["registration"]["state"] != "registered":
                doc = update_record(state, roots, doc, registration={"id": doc["id"], "state": "prepared"})
                try:
                    _register(projection, roots.state / "marketplace-recovery", Path(args.codex),
                              roots.home, roots.codex_home, recovery_id=doc["id"])
                    inspected = inspect_registration(Path(args.codex), roots, desired)
                    ensure_usage_lock(state, inspected.cache.dev, inspected.cache.ino)
                except BaseException:
                    update_record(state, roots, doc, registration={"id": doc["id"], "state": "failed"})
                    raise
                doc = update_record(state, roots, doc, registration={"id": doc["id"], "state": "registered"})
            if context is not None:
                selected = replace(context, workflow_id=doc["id"])
                result = cli._changed_install_locked(selected, args._fault, state, doc["id"], handoff)
                return {**result, "workflow_id": doc["id"], "projection": str(projection)}
        if context is None:
            return finalize_register_locked(state, roots, doc["id"], Path(args.codex))
        return {"workflow_id": doc["id"], "projection": str(projection),
                "requires_blender_start": True, "status": doc["status"]}


def _finalize_registration(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    with mutation_locks(roots) as state:
        result = finalize_register_locked(state, roots, args.workflow_id, Path(args.codex))
    print(json.dumps(result, sort_keys=True))
    if result["status"] == "cleanup_pending":
        raise SystemExit(3)


def _begin_handoff(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    runtime = roots.home / ".local/share/blender-lab-mcp/runtime"
    with mutation_locks(roots) as state:
        result = begin_handoff(state, roots, runtime, Path(args.codex))
    print(json.dumps(result, sort_keys=True))


def _restore_evidence(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    recovery = Path(args.recovery)
    parent = roots.state / "marketplace-recovery"
    if recovery.parent != parent or not re.fullmatch(r"registration\.[A-Za-z0-9_-]+", recovery.name):
        raise InstallerError("unsupported registration recovery path")
    with mutation_locks(roots) as state:
        reference = recovery.relative_to(roots.state).as_posix()
        assert_rollback_available(state, roots, registration_ref=reference)
        before, _proof = read_proof(state, recovery.relative_to(roots.state) / "before.json")
        others, _proof = read_proof(state, recovery.relative_to(roots.state) / "non-target-before.json")
        _restore(Path(args.codex), roots.home, roots.codex_home, before, others)
    print(json.dumps({"marketplace_source_restored": True,
                      "plugin_version_restored": False}, sort_keys=True))


def _verify(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    projection = Path(args.projection)
    _validate_secure_tree(projection)
    plugin = json.loads((projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json").read_bytes())
    manifest_raw = (projection / "plugins/blender-mcp-installer/artifacts/manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    inspect_registration(Path(args.codex), roots, {
        "commit": projection.name, "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "bundle_version": manifest["bundle_version"], "plugin_version": plugin["version"],
        "projection": str(projection),
    })
    if args.recovery is not None:
        recovery = Path(args.recovery)
        if (recovery.parent != roots.state / "marketplace-recovery"
                or not re.fullmatch(r"registration\.[A-Za-z0-9_-]+", recovery.name)):
            raise InstallerError("unsupported registration recovery path")
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            fd = home.open_directory(roots.state.relative_to(roots.home))
        with SafeRoot(roots.state, os.getuid(), fd) as state:
            before, _proof = read_proof(state, recovery.relative_to(roots.state) / "non-target-before.json")
        _target, current = _marketplace_snapshot(roots.codex_home / "config.toml")
        if current != before:
            raise InstallerError("non-target marketplace configuration changed")
    print(json.dumps({"marketplace": MARKETPLACE_NAME, "projection": str(projection),
                      "status": "passed", "read_only": True}, sort_keys=True))
```

### tests/distribution/test_upgrade_launcher.py

```python
from __future__ import annotations
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Mapping
from uuid import uuid4
import pytest

REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / 'plugins/blender-mcp-installer/scripts'))
from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.runtime import _launcher_source
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, usage_lock
from blender_mcp_installer.upgrade_state import UpgradeRoots, state_root

@pytest.mark.parametrize('status', ['prepared', 'installed'])
def test_external_bootstrap_gates_runtime_before_exec(tmp_path, status):
    home = (tmp_path / 'home').resolve()
    home.mkdir(mode=0o700)
    roots = UpgradeRoots(home, home / '.codex')
    roots.codex_home.mkdir(mode=0o700)
    runtime = home / '.local/share/blender-lab-mcp/runtime'
    (runtime / 'bin').mkdir(parents=True)
    (runtime / 'bin/python').symlink_to(Path(sys.executable).resolve())
    (runtime / 'bin/blender-mcp').write_text("import time; print('payload-ready', flush=True); time.sleep(30)")
    launcher = runtime / 'bin/blender-mcp-managed'
    environment = {'HOME': str(home), 'PATH':'/usr/bin:/bin', 'BLENDER_MCP_BOOTSTRAP_PYTHON':str(Path(sys.executable).resolve()), 'BLENDER_MCP_CODEX_HOME':str(roots.codex_home)}
    launcher.write_bytes(_launcher_source(environment))
    launcher.chmod(0o700)
    info = runtime.stat()
    identifier = str(uuid4())
    with state_root(roots) as state:
        ensure_usage_lock(state, info.st_dev, info.st_ino)
        (state.path/'receipts').mkdir()
        (state.path/'active.json').write_text(json.dumps({'install_id':identifier}))
        (state.path/'receipts'/f'{identifier}.json').write_text(json.dumps({'install_id':identifier,'status':status,'targets':[{'role':'runtime','path':str(runtime),'install_post':{'dev':info.st_dev,'ino':info.st_ino}}]}))
        process = subprocess.Popen([str(launcher)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            if status == 'prepared':
                out, error = process.communicate(timeout=5)
                assert process.returncode == 75, error
                assert not out
            else:
                assert process.stdout.readline().strip() == 'payload-ready'
                with usage_lock(state,info.st_dev,info.st_ino,exclusive=True) as acquired:
                    assert not acquired
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)


def test_custom_codex_cache_cannot_supply_bootstrap(tmp_path):
    custom_codex = tmp_path / 'custom-codex'
    bootstrap = custom_codex / 'plugins/cache/official-blender-mcp/blender-mcp-installer/old/bin/python'
    environment = {'HOME': str(tmp_path / 'home'), 'PATH': '/usr/bin:/bin',
                   'BLENDER_MCP_BOOTSTRAP_PYTHON': str(bootstrap),
                   'BLENDER_MCP_CODEX_HOME': str(custom_codex)}
    with pytest.raises(InstallerError, match='retired program tree'):
        _launcher_source(environment)
```

### 脚本入口 prelude

```python
import atexit as _atexit
import fcntl as _fcntl
import hashlib as _hashlib
import os as _os
from pathlib import Path as _Path
import stat as _stat


def _entry_directory(path: _Path) -> int:
    if not path.is_absolute() or '..' in path.parts:
        raise SystemExit(75)
    fd = _os.open('/', _os.O_RDONLY | _os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = _os.open(part, _os.O_RDONLY | _os.O_DIRECTORY | _os.O_NOFOLLOW, dir_fd=fd)
            _os.close(fd)
            fd = child
        info = _os.fstat(fd)
        if info.st_uid != _os.getuid() or _stat.S_IMODE(info.st_mode) & 0o022:
            raise SystemExit(75)
        return fd
    except BaseException:
        _os.close(fd)
        raise


def _entry_lease() -> int | None:
    home = _Path(_os.environ.get('HOME', '/'))
    codex = _Path(_os.environ.get('CODEX_HOME', str(home / '.codex')))
    cache = codex / 'plugins/cache/official-blender-mcp/blender-mcp-installer'
    script = _Path(__file__).absolute()
    if not script.is_relative_to(cache):
        return None
    relative = script.relative_to(cache)
    if len(relative.parts) < 2:
        raise SystemExit(75)
    version = cache / relative.parts[0]
    root_fd = _entry_directory(version)
    info = _os.fstat(root_fd)
    name = _hashlib.sha256(f'tree:{info.st_dev}:{info.st_ino}'.encode()).hexdigest() + '.lock'
    usage_fd = _entry_directory(home / '.local/state/blender-mcp-installer/usage')
    lease_fd = _os.open(name, _os.O_RDWR | _os.O_NOFOLLOW, dir_fd=usage_fd)
    lease = _os.fstat(lease_fd)
    linked = _os.stat(name, dir_fd=usage_fd, follow_symlinks=False)
    if (not _stat.S_ISREG(lease.st_mode) or lease.st_uid != _os.getuid()
            or _stat.S_IMODE(lease.st_mode) != 0o600 or lease.st_nlink != 1
            or (lease.st_dev, lease.st_ino) != (linked.st_dev, linked.st_ino)):
        raise SystemExit(75)
    try:
        _fcntl.flock(lease_fd, _fcntl.LOCK_SH | _fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(75)
    check_fd = _entry_directory(version)
    after = _os.fstat(check_fd)
    if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino) or not script.is_file():
        raise SystemExit(75)
    for fd in (root_fd, usage_fd, check_fd):
        _os.close(fd)
    _atexit.register(_os.close, lease_fd)
    return lease_fd


_SCRIPT_USAGE_FD = _entry_lease()
```

## 完整核心回归文件

Task 3 将以下完整文件写入 `tests/distribution/test_upgrade_core.py`。该文件的 bootstrap 只加入仓库 scripts；计划编写阶段的隔离探针才额外把临时模块路径加入 package path。

```python
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path, PurePath
from uuid import uuid4

import pytest

REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError, NoOpFaultInjector, SafeRoot, capture_file, capture_tree
from blender_mcp_installer.upgrade_state import UpgradeRoots, new_record, save_record, state_root, load_record, validate_record, update_record
from blender_mcp_installer.upgrade_registration import content_sha256, validate_installed_payload
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, usage_lock, usage_name
from blender_mcp_installer.upgrade_cleanup import finalize_record, cleanup_result, assert_rollback_available, RollbackUnavailable


@pytest.fixture
def prepared(tmp_path):
    home, codex = tmp_path / "home", tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home, codex)
    desired = {"commit": "b" * 40, "manifest_sha256": "c" * 64,
               "bundle_version": "1.0.0", "plugin_version": "2", "projection": str(roots.projections / ("b" * 40))}
    version = "1"
    old_source = roots.projections / ("a" * 40) / "plugins/blender-mcp-installer"
    old_cache = roots.caches / version
    for tree in (old_source, old_cache):
        tree.mkdir(parents=True, mode=0o700)
        (tree / "a").write_bytes(b"old-a")
        (tree / "b").write_bytes(b"old-b")
    registration_id = str(uuid4())
    with state_root(roots) as state:
        folder = state.path / "marketplace-recovery" / ("registration." + registration_id)
        folder.mkdir(parents=True, mode=0o700)
        proof = folder / "after.json"
        proof.write_text("{}\n")
        proof.chmod(0o600)
        with SafeRoot.open(codex, os.getuid(), codex) as safe_codex:
            old_image = capture_tree(safe_codex, old_cache.relative_to(codex))
        with SafeRoot.open(home, os.getuid(), home) as safe_home:
            source_image = capture_tree(safe_home, old_source.relative_to(home))
        row = {"key": "plugin_cache:1", "kind": "plugin_cache", "owner": registration_id,
               "version": version, "expected": old_image.to_dict(),
               "proofs": [{"relative": proof.relative_to(state.path).as_posix(),
                           "expected": capture_file(state, proof.relative_to(state.path)).to_dict()}],
               "content_source": str(old_source), "content_sha256": content_sha256(source_image),
               "lease_known": True, "state": "pending", "reason": ""}
        ensure_usage_lock(state, old_image.dev, old_image.ino)
        doc = new_record(roots, "register", desired)
        doc["registration"] = {"id": str(uuid4()), "state": "registered"}
        (state.path / "marketplace-recovery" / ("registration." + doc["registration"]["id"])).mkdir(mode=0o700)
        doc = save_record(state, roots, None, doc)
        yield roots, state, doc, row, old_cache


def test_exact_codex_identity_checks_distinct_source_shapes():
    desired = {"bundle_version": "1.0.0", "plugin_version": "2", "projection": "/managed/new"}
    item = {"pluginId": "blender-mcp-installer@official-blender-mcp",
            "name": "blender-mcp-installer", "marketplaceName": "official-blender-mcp",
            "version": "2", "installed": True, "enabled": True,
            "source": {"source": "local", "path": "/managed/new/plugins/blender-mcp-installer"},
            "marketplaceSource": {"sourceType": "local", "source": "/managed/new"}}
    assert validate_installed_payload({"installed": [item]}, desired) == item
    for field, value in (("version", "1"), ("enabled", False), ("installed", 1)):
        bad = dict(item)
        bad[field] = value
        with pytest.raises(InstallerError):
            validate_installed_payload({"installed": [bad]}, desired)
    bad = dict(item, marketplaceSource=item["source"])
    with pytest.raises(InstallerError):
        validate_installed_payload({"installed": [bad]}, desired)


def test_schema_rejects_foreign_and_unknown_fields(prepared):
    roots, state, doc, row, _ = prepared
    invalid = copy.deepcopy(doc)
    invalid["candidates"] = [row]
    invalid["candidates"][0]["content_source"] = str(roots.projections / ("a" * 40) / "blender-mcp-installer")
    with pytest.raises(InstallerError):
        validate_record(invalid, roots)
    for change in ({"schema_version": 2}, {"home": "/foreign"}, {"extra": True}):
        with pytest.raises(InstallerError):
            validate_record(dict(doc, **change), roots)


def test_no_delete_if_validation_fails(prepared):
    roots, state, doc, row, old = prepared
    def invalid(_doc):
        raise InstallerError("live failed")
    with pytest.raises(InstallerError, match="live failed"):
        finalize_record(state, roots, doc["id"], invalid, lambda _: ([row], []), lambda _: ())
    assert old.exists()
    assert load_record(state, roots, doc["id"])["status"] == "awaiting_verification"


def test_verified_cleanup_is_idempotent_and_expires_only_recorded_registration(prepared):
    roots, state, doc, row, old = prepared
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ())
    assert result["status"] == "complete" and not old.exists()
    assert Path(row["content_source"]).exists()
    assert load_record(state, roots, doc["id"]) == result
    assert finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ()) == result
    with pytest.raises(RollbackUnavailable):
        assert_rollback_available(state, roots, registration_ref=str(PurePath(row["proofs"][0]["relative"]).parent))
    assert_rollback_available(state, roots, registration_ref="marketplace-recovery/registration.other")
    assert cleanup_result(result)["all_old_versions_removed"] is True
    assert (state.path / PurePath(row["proofs"][0]["relative"]).parent / "RECOVERY_STATUS.json").is_file()


def test_active_reference_and_busy_lease_defer(prepared):
    roots, state, doc, row, old = prepared
    first = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: (old / "a",))
    assert first["candidates"][0]["state"] == "deferred_in_use" and old.exists()
    image = row["expected"]
    with usage_lock(state, image["dev"], image["ino"], exclusive=False) as acquired:
        assert acquired
        second = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
        assert second["candidates"][0]["state"] == "deferred_in_use" and old.exists()
    third = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
    assert third["status"] == "complete" and not old.exists()


def test_legacy_lease_never_assumed_idle(prepared):
    roots, state, doc, row, old = prepared
    row["lease_known"] = False
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ())
    assert result["status"] == "cleanup_pending"
    assert result["candidates"][0]["reason"] == "legacy usage is not proven idle"
    assert old.exists()


def test_content_drift_is_not_adopted_as_new_baseline(prepared):
    roots, state, doc, row, old = prepared
    (old / "foreign").write_bytes(b"user")
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []), lambda _: ())
    assert result["candidates"][0]["state"] == "conflict"
    assert (old / "foreign").read_bytes() == b"user"
    assert result["candidates"][0]["expected"] == row["expected"]


@pytest.mark.parametrize("point", ["after_upgrade_cleanup_intent", "after_cleanup_entry",
                                  "after_installer_cleanup", "after_upgrade_candidate_record"])
def test_crash_is_resumed_from_original_image(prepared, point):
    roots, state, doc, row, old = prepared
    class Crash(NoOpFaultInjector):
        def hit(self, current):
            if current == point:
                raise SystemExit(70)
    with pytest.raises(SystemExit):
        finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([row], []),
                        lambda _: (), Crash())
    pending = load_record(state, roots, doc["id"], recover=True)
    assert pending["status"] in {"cleanup_pending", "complete"}
    result = finalize_record(state, roots, doc["id"], lambda _: (), lambda _: ([], []), lambda _: ())
    assert result["status"] == "complete" and not old.exists()


def test_root_inode_lease_survives_rename_and_exec(prepared, tmp_path):
    roots, state, _doc, row, old = prepared
    info = row["expected"]
    lock_path = state.path / "usage" / usage_name(info["dev"], info["ino"])
    source = (
        "import os,fcntl,sys; fd=os.open(sys.argv[1],os.O_RDWR); "
        "fcntl.flock(fd,fcntl.LOCK_SH); os.set_inheritable(fd,True); "
        "os.execv(sys.executable,[sys.executable,'-c',"
        "\"import time; print('ready',flush=True); time.sleep(60)\"])"
    )
    process = subprocess.Popen([sys.executable, "-c", source, str(lock_path)],
                               stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "ready"
        renamed = old.with_name("parked")
        old.rename(renamed)
        assert (renamed.stat().st_dev, renamed.stat().st_ino) == (info["dev"], info["ino"])
        with usage_lock(state, info["dev"], info["ino"], exclusive=True) as acquired:
            assert not acquired
    finally:
        process.terminate()
        process.wait(timeout=5)
    with usage_lock(state, info["dev"], info["ino"], exclusive=True) as acquired:
        assert acquired


def test_discovery_keeps_cache_without_historical_source(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates
    roots, state, doc, _row, old = prepared
    candidates, findings = discover_candidates(state, roots, doc)
    assert candidates == []
    assert findings and old.exists()


def test_register_mode_never_discovers_runtime_recovery(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates
    roots, state, doc, _row, _old = prepared
    recovery = roots.home / '.local/share/blender-lab-mcp/.blender-mcp-installer.fake.runtime.recovery'
    recovery.mkdir(parents=True)
    (recovery / 'user-file').write_text('preserve')
    candidates, _findings = discover_candidates(state, roots, doc)
    assert all(row['kind'] == 'plugin_cache' for row in candidates)
    assert (recovery / 'user-file').read_text() == 'preserve'


def test_exact_registration_creates_migration_journal_when_old_cache_remains(prepared, monkeypatch):
    from types import SimpleNamespace
    from blender_mcp_installer import upgrade_integration
    from blender_mcp_installer.upgrade_state import record_ids
    import project_marketplace as marketplace
    roots, state, prior, row, old = prepared
    update_record(state, roots, prior, status='cancelled')
    projection = Path(prior['desired']['projection'])
    plugin = projection / 'plugins/blender-mcp-installer'
    (plugin / '.codex-plugin').mkdir(parents=True)
    (plugin / 'artifacts').mkdir()
    (plugin / '.codex-plugin/plugin.json').write_text(json.dumps({'name':'blender-mcp-installer','version':'2'}))
    (plugin / 'artifacts/manifest.json').write_text(json.dumps({'bundle_version':'1.0.0'}))
    called = []
    snapshot = {'present':True,'source_type':'local','source':str(projection)}
    monkeypatch.setattr(upgrade_integration, 'inspect_registration', lambda *_args: None)
    monkeypatch.setattr(upgrade_integration, 'discover_candidates', lambda *_args: ([row], []))
    monkeypatch.setattr(upgrade_integration, 'other_references', lambda *_args: ())
    monkeypatch.setattr(marketplace, 'inspect_registration', lambda *_args: None)
    monkeypatch.setattr(marketplace, 'discover_candidates', lambda *_args: ([row], []))
    monkeypatch.setattr(marketplace, '_marketplace_snapshot', lambda *_args: (snapshot, {}))
    monkeypatch.setattr(marketplace, '_register', lambda *_args, **_kwargs: called.append('register'))
    args = SimpleNamespace(reviewed_commit='b'*40, codex='/fake/codex', workflow_id=None)
    result = marketplace._run_workflow(args,state,roots,projection)
    assert result['status']=='complete' and not old.exists()
    assert result['workflow_id'] != prior['id']
    assert len(record_ids(state))==2 and called==[]


def test_orphan_cache_without_any_registration_is_unverified(tmp_path):
    from blender_mcp_installer.upgrade_discovery import discover_candidates
    home, codex = tmp_path/'home', tmp_path/'codex'
    home.mkdir(mode=0o700);codex.mkdir(mode=0o700)
    roots = UpgradeRoots(home,codex)
    orphan = roots.caches/'orphan-1'
    orphan.mkdir(parents=True)
    (orphan/'user-file').write_text('preserve')
    desired = {'commit':'a'*40,'manifest_sha256':'b'*64,'plugin_version':'2','bundle_version':'1.0.0',
               'projection':str(roots.projections/('a'*40))}
    doc = new_record(roots,'register',desired)
    with state_root(roots) as state:
        rows, findings = discover_candidates(state,roots,doc)
    assert rows==[]
    assert any(item['path']==str(orphan) for item in findings)
    assert (orphan/'user-file').read_text()=='preserve'


def test_full_finalize_probes_live_once_and_rechecks_snapshot(prepared, monkeypatch):
    from types import SimpleNamespace
    from blender_mcp_installer import upgrade_integration as integration
    from blender_mcp_installer import verification
    roots, state, prior, row, old = prepared
    profile = {'executable':str(roots.home/'Blender'),'architecture':'arm64','version':'5.2.0',
               'resources':str(roots.home/'profile'),'config':str(roots.home/'profile/config'),
               'extensions':str(roots.home/'profile/extensions')}
    document = new_record(roots,'install',prior['desired'])
    document['profile']=profile
    document['registration']=prior['registration']
    document['install_id']=str(uuid4())
    document=save_record(state,roots,None,document)
    context=SimpleNamespace(roots=SimpleNamespace(home=roots.home,codex_home=roots.codex_home,
        runtime=roots.home/'.local/share/blender-lab-mcp/runtime',
        receipt=lambda identifier: state.path/'receipts'/f'{identifier}.json'),
        host=SimpleNamespace(codex_bin=Path('/fake/codex'),env={}),
        source_bundle=object(),blender=object())
    executable = context.roots.runtime / 'bin/python'
    executable.parent.mkdir(parents=True)
    executable.write_text('#!/bin/sh\nexit 0\n');executable.chmod(0o700)
    live=[];fingerprints=[]
    monkeypatch.setattr(integration,'desired_from_context',lambda _context: prior['desired'])
    monkeypatch.setattr(integration,'profile_from_context',lambda _context: profile)
    monkeypatch.setattr(integration,'installation_fingerprint',lambda *_args:(fingerprints.append('read') or ('stable',)))
    monkeypatch.setattr(verification,'verify_live',lambda *_args:live.append('live'))
    monkeypatch.setattr(integration,'discover_candidates',lambda *_args:([row],[]))
    monkeypatch.setattr(integration,'other_references',lambda *_args:())
    result=integration.finalize_install_locked(state,context,document['id'],NoOpFaultInjector())
    assert result['status']=='complete' and not old.exists()
    assert live==['live'] and len(fingerprints)>=4


def test_legacy_registration_before_protects_cache_without_upgrade_journal(prepared):
    from blender_mcp_installer.upgrade_discovery import other_references
    roots,state,doc,row,old=prepared
    projection=Path(row['content_source']).parent.parent
    plugin=Path(row['content_source']);(plugin/'.codex-plugin').mkdir()
    (plugin/'.codex-plugin/plugin.json').write_text(json.dumps({'version':'1'}))
    proof=state.path/'marketplace-recovery/registration.legacy-before-only'
    proof.mkdir(mode=0o700)
    (proof/'before.json').write_text(json.dumps({'present':True,'source_type':'local','source':str(projection)}))
    (proof/'before.json').chmod(0o600)
    assert old in other_references(state,roots,doc)


def test_other_codex_home_journal_is_validated_but_not_adopted(prepared):
    from blender_mcp_installer.upgrade_discovery import discover_candidates,other_references
    from blender_mcp_installer.upgrade_state import load_any_record
    roots,state,doc,_row,old=prepared
    foreign_home=roots.home/'second-codex';foreign_home.mkdir(mode=0o700)
    foreign_roots=UpgradeRoots(roots.home,foreign_home)
    other=new_record(foreign_roots,'register',doc['desired'])
    save_record(state,foreign_roots,None,other)
    assert load_any_record(state,roots,other['id'])==other
    references=other_references(state,roots,doc)
    assert foreign_roots.caches/'2' in references
    candidates,_=discover_candidates(state,roots,doc)
    assert candidates==[] and old.exists()
```

## 实测证据与执行边界

2026-09-08 在仓库外隔离目录 `/tmp/blender-upgrade-plan-probe.wV3ucU` 执行核心与 launcher 原型，使用本仓库现有 filesystem/model 原语，22 个 pytest 用例通过。原型测试中的 roots 全部来自 pytest 临时目录；没有调用真实安装、注册、删除或关闭进程。这个证据只证明候选/journal/使用锁核心可行，不是完整安装工作流、真实 Codex 自动重载或 Blender 现场验收结论。

执行计划后仍必须完成 A→B→C 内容真实不同的现场验收：每次正式验证通过后检查物理目录删除、当前 MCP 可用、当前扩展可用、非目标目录与配置备份不变。首次 legacy 维护交接需要外部终端和相关应用退出的可观测证据，不能在当前 Codex 任务中伪造通过。
