# Phase 0 只读端到端链路 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 Codex → MCP Server（stdio）→ UDS → Blender Bridge → 主线程 → 结构化返回的只读链路，交付 `get_blender_status` / `get_scene_summary` / `describe_capabilities` 三个工具，满足 URS §10.1 八条验收。

**Architecture:** 内核/适配分层（spec P0-D3）：`protocol/` 为两侧共用的线格式单一真相源（vendoring 进 Bridge）；`bridge/core/` 与 `server/core/` 零外部依赖、纯 stdlib，bpy 与 MCP SDK 各自隔离在薄适配层。Bridge 侧单 I/O 线程 select 多路复用 + 主线程 timer tick；Server 侧无状态短命进程。

**Tech Stack:** Python 3.13（Blender 5.2.0 内置 3.13.13，SPIKE-2 实测）· `mcp==1.28.x`（FastMCP）· uv · pytest + pytest-timeout · ruff（target py313）· mypy strict（core）

**上游文档：** spec = `docs/superpowers/specs/2026-07-23-phase0-readonly-channel-design.md`（引用记为 §N）；URS = `Blender-Codex-需求规格说明书-v1.md`

## Global Constraints

以下约束适用于**每个**任务，值从 spec 原文复制：

- Python 语法基线 **py313**；Server uv 钉 Python 3.13；`mcp>=1.28,<1.29`（§8.2、§9）
- `bridge/`（含 `_vendor/`）**只准 stdlib**——不得 import 任何第三方包，不得 import mcp（URS NFR-S8）
- `bridge/core/` 与 `protocol/` 内**不得出现 `import bpy`**（§3.1，CI 检查 1）
- `protocol/` 包内部**只准相对导入**（`from . import ...`）——vendored 副本运行在 `bl_ext.<repo>.<ext_id>._vendor.protocol` 深层命名空间（§3.1 约束 2）
- 帧上限 **16 MiB，读写两端同限**（§3.2）；帧格式 = 4 字节大端 uint32 长度 + UTF-8 JSON
- 权限：目录**逐级**创建并各自 chmod `0700`；文件以 `O_EXCL` mode `0o600` 创建；socket bind 后立即 chmod `0600`（§2.2 权限机制表）
- 所有时间比较用 `time.monotonic()`，不用墙钟（§3.6）
- Server 的 runtime 根目录从环境变量 **`BLENDERCODEX_ROOT`** 读取，默认 `~/Library/Application Support/BlenderCodex`（§7.2）
- 基线常量：Blender **5.2.0** / `macos-arm64`（§8.3）；`ENVELOPE_VERSION = 1`
- stdio 模式下 stdout 只准 JSON-RPC，日志一律 stderr 或文件（URS NFR-O1）
- 每个 commit message 以 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 结尾
- 测试命令统一 `uv run pytest`；提交前该任务的全部测试必须绿
- **每个任务提交前还须 `uv run ruff check .` 与 `uv run mypy` 全绿**——类型与 lint 门禁逐任务执行，不推迟到 Task 14 首跑（r3 审计：推迟会让数十个错误集中爆发在打包阶段，诱发当场放宽 strict）

## File Structure

```
（仓库根 = /Users/yeminjie/Documents/BlenderDesign）
pyproject.toml               项目与工具链配置（Task 0）
protocol/
  __init__.py                空
  framing.py                 帧编解码 + FrameBuffer 累帧（Task 1）
  envelope.py                Request/错误码/METHOD_TIMEOUTS/编解码（Task 2）
bridge/
  __init__.py                扩展入口 shim（Task 13）
  core/
    __init__.py              空
    contracts.py             SceneSnapshot/ManagedObject/SceneReader/Clock（Task 3）
    scene_hash.py            纯函数版 §3.5 hash 算法（Task 3；spec 模块表外的新增文件，
                             理由：hash 逻辑零 bpy 依赖，放 core 才能进 L1）
    _proto.py                protocol 双路径导入垫片（Task 3；见其说明）
    queue.py                 TaskQueue：deadline/预算/批处理（Task 4）
    session.py               token 生成/常数时间校验 + session.json 原子读写（Task 5）
    router.py                method 分发：ping/status/scene_summary（Task 6）
    lifecycle.py             BridgeSession.start/stop + I/O 线程（Task 7）
  blender/
    __init__.py              register/unregister 实现（Task 13）
    scene_reader.py          bpy 版 SceneReader（Task 13）
    driver.py                _tick_guard + timer/handler 注册（Task 13）
    panel.py                 N 面板 + 允许连接/断开 operator（Task 13）
  _vendor/protocol/          Task 14 的 vendor 脚本生成，不手写
  blender_manifest.toml      Task 14
server/
  __init__.py                空
  core/
    __init__.py              空
    config.py                BLENDERCODEX_ROOT 解析（Task 8；spec 模块表外的新增文件，
                             理由：§7.2 的注入点需单一定义处）
    path_policy.py           路径策略（Task 8）
    audit.py                 JSONL 审计（Task 9）
    versions.py              版本门禁（Task 9）
    capabilities.py          describe_capabilities 静态应答（Task 9）
    bridge_client.py         UDS 客户端（Task 10）
    discovery.py             扫描/握手/缓存/清理（Task 11）
  mcp/
    __init__.py              空
    adapter.py               FastMCP 三工具注册，≤300 行（Task 12）
tests/
  unit/                      L1（各任务内）
  contract/
    fake_bridge.py           真 core + FakeSceneReader + 线程 driver（Task 15）
    test_roundtrip.py        基础往返（Task 15）
    test_adversarial.py      半帧/交错/BUSY/过期/reply 失败/护栏（Task 16）
    test_server_process.py   stdout 纯净性 + 冷启动（Task 17）
scripts/
  vendor_protocol.py         复制 + hash 校验（Task 14）
  checks.sh                  全部 CI 检查（Task 14）
smoke/
  runner.py                  L3 冒烟（Task 18）
docs/
  install.md                 codex mcp add 安装文档（Task 19）
```

任务依赖：0 → 1 → 2 → {3,4,5} → 6 → 7 → {8,9} → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19。Task 1–12、14–17 **无需 Blender**；Task 13、18 需要（已安装 5.2.0）。

---

### Task 0: 仓库初始化与工具链

**Files:**
- Create: `pyproject.toml`、`.gitignore`、`protocol/__init__.py`、`bridge/__init__.py`、`bridge/core/__init__.py`、`server/__init__.py`、`server/core/__init__.py`、`server/mcp/__init__.py`、`tests/__init__.py`、`tests/unit/__init__.py`（空文件）

两个 `__init__.py` 不可省：`tests/__init__.py` 支撑 L2 的 `from tests.unit.test_lifecycle import FakeReader` 跨模块导入；**`bridge/__init__.py` 缺席会让 mypy 对同一份 `bridge/core/*.py` 得到两个模块名**（`files` 遍历按包爬升得 `core.session`，`from bridge.core.session import ...` 按 namespace package 得 `bridge.core.session`）从而报 duplicate module。Task 13 会把它覆写为 bpy 探测 shim，行为不变。

**Interfaces:**
- Produces: 可运行的 `uv run pytest`（空收集退出码 **5** 属预期——pytest 对 NO_TESTS_COLLECTED 返回 5，不是 0）；hatchling 构建就位（Task 12 的 entry point 依赖它）；git 仓库

- [ ] **Step 1: git init 并提交既有文档**

```bash
cd /Users/yeminjie/Documents/BlenderDesign
git init -b main
printf '__pycache__/\n*.pyc\n.venv/\n.DS_Store\nbridge/_vendor/\n' > .gitignore
git add .gitignore Blender-Codex-需求规格说明书-v1.md docs/
git commit -m "docs: URS v1 与 Phase 0 设计 spec（含 spike 实测结果）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

注意 `.gitignore` 排除 `bridge/_vendor/`——它是构建产物（Task 14 生成），不入库。

- [ ] **Step 2: 写 pyproject.toml**

```toml
[project]
name = "blender-codex"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["mcp>=1.28,<1.29"]

[dependency-groups]
dev = ["pytest>=8", "pytest-timeout>=2.3", "ruff>=0.16,<0.17", "mypy>=1.10"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
timeout = 30

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F"]   # 显式钉死规则集——ruff 默认集逐版本扩张，
                                   # 不钉则升级 ruff 就会让既有代码无端翻红

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["protocol", "bridge", "server"]

[tool.mypy]
python_version = "3.13"
strict = true
warn_unused_ignores = false
files = ["protocol", "bridge/core", "server/core"]

[[tool.mypy.overrides]]
module = ["bpy", "bpy.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["bridge._vendor.*", "bridge.blender.*"]
ignore_missing_imports = true
ignore_errors = true
follow_imports = "skip"
```

三处非默认配置的理由（r3 审计）：**`[build-system]` 缺席时 uv 按 virtual 项目处理，只装依赖不装项目自身，Task 12 的 `[project.scripts]` 入口将永远不生成**（flat 布局多顶层包也必须显式声明 `packages`）；`warn_unused_ignores = false` 让 `_proto.py` 的 `type: ignore` 在 `_vendor/` 存在与缺席两种状态下都合法（checks.sh 复跑不因此翻红）；overrides 把 bpy 与不受检的适配层挡在 strict 之外。

- [ ] **Step 3: 建空包文件并验证工具链**

```bash
mkdir -p protocol bridge/core server/core server/mcp tests/unit
touch protocol/__init__.py bridge/__init__.py bridge/core/__init__.py \
      server/__init__.py server/core/__init__.py server/mcp/__init__.py \
      tests/__init__.py tests/unit/__init__.py
uv python pin 3.13
uv sync
uv run pytest --co -q
```

Expected: 空收集，**退出码 5（NO_TESTS_COLLECTED，属预期）**；`uv run python -c "import mcp; print(mcp.__version__)"` 输出 1.28.x。

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: uv 工具链与包骨架（py3.13, mcp 1.28.x）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 1: protocol/framing.py

**Files:**
- Create: `protocol/framing.py`
- Test: `tests/unit/test_framing.py`

**Interfaces:**
- Produces（后续所有任务依赖）:
  - `MAX_FRAME: int = 16 * 1024 * 1024`
  - `class FrameError(Exception)`；`class FrameTooLarge(FrameError)`
  - `encode_frame(payload: bytes) -> bytes` — 超限抛 `FrameTooLarge`（写端同限，§3.2）
  - `class FrameBuffer: feed(data: bytes) -> list[bytes]`（累帧，凑满才出帧；长度头超限抛 `FrameTooLarge`）；`pending: int` 属性

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_framing.py
import pytest
import struct
from protocol.framing import MAX_FRAME, FrameBuffer, FrameTooLarge, encode_frame


def test_encode_prepends_big_endian_length():
    assert encode_frame(b"abc") == b"\x00\x00\x00\x03abc"


def test_encode_rejects_oversize():
    with pytest.raises(FrameTooLarge):
        encode_frame(b"x" * (MAX_FRAME + 1))


def test_feed_accumulates_partial_reads():
    buf = FrameBuffer()
    frame = encode_frame(b"hello")
    assert buf.feed(frame[:3]) == []          # 连长度头都不完整
    assert buf.feed(frame[3:6]) == []         # 头齐了、载荷不齐
    assert buf.feed(frame[6:]) == [b"hello"]  # 凑满出帧
    assert buf.pending == 0


def test_feed_splits_coalesced_frames():
    buf = FrameBuffer()
    data = encode_frame(b"a") + encode_frame(b"bb") + encode_frame(b"c")[:2]
    assert buf.feed(data) == [b"a", b"bb"]
    assert buf.pending == 2                   # 残留半个头


def test_feed_rejects_oversize_header_without_buffering():
    buf = FrameBuffer()
    with pytest.raises(FrameTooLarge):
        buf.feed(struct.pack(">I", MAX_FRAME + 1))


def test_five_mib_roundtrip():
    payload = b"y" * (5 * 1024 * 1024)       # URS 验收：5 MiB 无截断
    buf = FrameBuffer()
    out = []
    encoded = encode_frame(payload)
    for i in range(0, len(encoded), 65536):   # 模拟 64KiB 分片到达
        out += buf.feed(encoded[i : i + 65536])
    assert out == [payload]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_framing.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'protocol.framing'`

- [ ] **Step 3: 实现**

```python
# protocol/framing.py
"""线格式：4 字节大端 uint32 长度前缀 + UTF-8 JSON 载荷。spec §3.2。"""
from __future__ import annotations

import struct

MAX_FRAME = 16 * 1024 * 1024
_HEADER = struct.Struct(">I")


class FrameError(Exception):
    pass


class FrameTooLarge(FrameError):
    pass


def encode_frame(payload: bytes) -> bytes:
    if len(payload) > MAX_FRAME:
        raise FrameTooLarge(f"frame {len(payload)} > {MAX_FRAME}")
    return _HEADER.pack(len(payload)) + payload


class FrameBuffer:
    """每连接一个。凑满「头 + length 字节」才切帧——NFR-R3 的非阻塞落法（§3.7 规则 1）。"""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self._buf += data
        frames: list[bytes] = []
        while len(self._buf) >= _HEADER.size:
            (length,) = _HEADER.unpack_from(self._buf)
            if length > MAX_FRAME:
                raise FrameTooLarge(f"declared {length} > {MAX_FRAME}")
            if len(self._buf) < _HEADER.size + length:
                break
            frames.append(bytes(self._buf[_HEADER.size : _HEADER.size + length]))
            del self._buf[: _HEADER.size + length]
        return frames

    @property
    def pending(self) -> int:
        return len(self._buf)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_framing.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add protocol/framing.py tests/unit/test_framing.py
git commit -m "feat(protocol): 帧编解码与累帧缓冲，16MiB 双端同限

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: protocol/envelope.py

**Files:**
- Create: `protocol/envelope.py`
- Test: `tests/unit/test_envelope.py`

**Interfaces:**
- Consumes: `from . import framing`（**相对导入**，Global Constraints）
- Produces:
  - `ENVELOPE_VERSION: int = 1`
  - `METHOD_TIMEOUTS: dict[str, float] = {"ping": 2.0, "status": 2.0, "scene_summary": 15.0}`（§4.2 表，两侧共享）
  - 错误码常量（str）：`UNKNOWN_METHOD` `BRIDGE_BUSY` `SCENE_QUERY_FAILED` `INTERNAL_LIMIT_EXCEEDED` `ENVELOPE_VERSION_MISMATCH` `INSTANCE_NOT_FOUND` `BRIDGE_UNAVAILABLE` `BRIDGE_TIMEOUT` `UNSUPPORTED_BLENDER_VERSION`
  - `@dataclass(frozen=True) Request(v: int, id: str, token: str, method: str, params: dict)`；`Request.new(token, method, params) -> Request`（uuid4）
  - `encode_request(req: Request) -> bytes`（含帧）；`decode_request(payload: bytes) -> Request`（字段/类型校验失败抛 `ValueError`）
  - `ok_frame(request_id: str, result: dict) -> bytes`；`error_frame(request_id: str, code: str, message: str, retryable: bool = False) -> bytes`——二者返回**整帧**；序列化超限时 `ok_frame` 内部降级为 `INTERNAL_LIMIT_EXCEEDED` 错误帧（§3.2 写端规则）
  - `decode_response(payload: bytes) -> dict`（原样 dict：`{"v","id","ok","result"| "error"}`）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_envelope.py
import json

import pytest
from protocol import envelope, framing


def test_request_roundtrip():
    req = envelope.Request.new(token="tok", method="ping", params={})
    payload = framing.FrameBuffer().feed(envelope.encode_request(req))[0]
    back = envelope.decode_request(payload)
    assert back == req
    assert back.v == envelope.ENVELOPE_VERSION


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b'{"v":1,"id":"x","method":"ping","params":{}}',        # 缺 token
        b'{"v":1,"id":"x","token":"t","method":"ping","params":[]}',  # params 非 dict
        b'{"v":1,"id":1,"token":"t","method":"ping","params":{}}',    # id 非 str
    ],
)
def test_decode_request_rejects_malformed(raw):
    with pytest.raises(ValueError):
        envelope.decode_request(raw)


def test_ok_and_error_frames():
    ok = json.loads(framing.FrameBuffer().feed(envelope.ok_frame("id1", {"a": 1}))[0])
    assert ok == {"v": 1, "id": "id1", "ok": True, "result": {"a": 1}}
    err = json.loads(
        framing.FrameBuffer().feed(
            envelope.error_frame("id2", envelope.BRIDGE_BUSY, "full", retryable=True)
        )[0]
    )
    assert err["ok"] is False
    assert err["error"] == {"code": "BRIDGE_BUSY", "message": "full", "retryable": True}


def test_ok_frame_degrades_to_limit_error_when_oversized():
    huge = {"blob": "x" * (framing.MAX_FRAME + 16)}
    frame = framing.FrameBuffer().feed(envelope.ok_frame("id3", huge))[0]
    decoded = json.loads(frame)
    assert decoded["ok"] is False
    assert decoded["error"]["code"] == envelope.INTERNAL_LIMIT_EXCEEDED


def test_method_timeouts_table():
    assert envelope.METHOD_TIMEOUTS == {"ping": 2.0, "status": 2.0, "scene_summary": 15.0}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_envelope.py -q`
Expected: FAIL，`No module named 'protocol.envelope'`

- [ ] **Step 3: 实现**

```python
# protocol/envelope.py
"""请求/响应信封 + 错误码 + method 超时表。spec §3.3、§4.2。只准相对导入。"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from . import framing

_log = logging.getLogger("bcx.protocol")

ENVELOPE_VERSION = 1

METHOD_TIMEOUTS: dict[str, float] = {"ping": 2.0, "status": 2.0, "scene_summary": 15.0}

UNKNOWN_METHOD = "UNKNOWN_METHOD"
BRIDGE_BUSY = "BRIDGE_BUSY"
SCENE_QUERY_FAILED = "SCENE_QUERY_FAILED"
INTERNAL_LIMIT_EXCEEDED = "INTERNAL_LIMIT_EXCEEDED"
ENVELOPE_VERSION_MISMATCH = "ENVELOPE_VERSION_MISMATCH"
INSTANCE_NOT_FOUND = "INSTANCE_NOT_FOUND"
BRIDGE_UNAVAILABLE = "BRIDGE_UNAVAILABLE"
BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
UNSUPPORTED_BLENDER_VERSION = "UNSUPPORTED_BLENDER_VERSION"


@dataclass(frozen=True)
class Request:
    id: str
    token: str
    method: str
    params: dict[str, Any]
    v: int = ENVELOPE_VERSION

    @classmethod
    def new(cls, token: str, method: str, params: dict[str, Any]) -> "Request":
        return cls(id=str(uuid.uuid4()), token=token, method=method, params=params)


def encode_request(req: Request) -> bytes:
    return framing.encode_frame(json.dumps(asdict(req), ensure_ascii=False).encode("utf-8"))


def decode_request(payload: bytes) -> Request:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"bad request payload: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("request must be an object")
    try:
        req = Request(
            id=raw["id"], token=raw["token"], method=raw["method"],
            params=raw["params"], v=raw.get("v", ENVELOPE_VERSION),
        )
    except KeyError as e:
        raise ValueError(f"missing field {e}") from e
    if not (isinstance(req.id, str) and isinstance(req.token, str)
            and isinstance(req.method, str) and isinstance(req.params, dict)
            and isinstance(req.v, int)):
        raise ValueError("field type mismatch")
    return req


def error_frame(request_id: str, code: str, message: str, retryable: bool = False) -> bytes:
    body = {"v": ENVELOPE_VERSION, "id": request_id, "ok": False,
            "error": {"code": code, "message": message, "retryable": retryable}}
    return framing.encode_frame(json.dumps(body, ensure_ascii=False).encode("utf-8"))


def ok_frame(request_id: str, result: dict[str, Any]) -> bytes:
    body = {"v": ENVELOPE_VERSION, "id": request_id, "ok": True, "result": result}
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    try:
        return framing.encode_frame(payload)
    except framing.FrameTooLarge:
        _log.warning("response %d bytes exceeds frame limit (request %s)",
                     len(payload), request_id)          # §3.2 写端：记诊断日志
        return error_frame(request_id, INTERNAL_LIMIT_EXCEEDED,
                           f"response {len(payload)} bytes exceeds frame limit")


def decode_response(payload: bytes) -> dict[str, Any]:
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, dict) or "ok" not in raw:
        raise ValueError("bad response")
    return raw
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_envelope.py -q`
Expected: 8 passed（含 4 个参数化）

- [ ] **Step 5: Commit**

```bash
git add protocol/envelope.py tests/unit/test_envelope.py
git commit -m "feat(protocol): 信封编解码、错误码、method 超时表、写端超限降级

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: bridge/core/contracts.py + scene_hash.py

**Files:**
- Create: `bridge/core/contracts.py`、`bridge/core/scene_hash.py`、`bridge/core/_proto.py`
- Test: `tests/unit/test_scene_hash.py`

**Interfaces:**
- Produces:
  - `ManagedObject(stable_id: str, name: str, type: str)`（frozen dataclass）
  - `SceneSnapshot`（frozen dataclass，字段按 §3.4：`scene_revision: int, scene_hash: str, scene_name: str, scene_path: str | None, units_system: str, units_scale_length: float, object_count: int, mesh_count: int, camera_count: int, light_count: int, collections: tuple[str, ...], managed_objects: tuple[ManagedObject, ...] = ()`）
  - `SceneReader(Protocol)`: `blender_version() -> str`；`snapshot() -> SceneSnapshot`
  - `Clock(Protocol)`: `monotonic() -> float`
  - `scene_hash.quantize(v: float) -> str`（round 6 位、`-0.0` 归一、定长 `%.6f`）
  - `scene_hash.object_line(name: str, obj_type: str, matrix16: tuple[float, ...], data_kind: str, data_counts: tuple[int, ...]) -> str`
  - `scene_hash.digest(lines: list[str]) -> str`（排序 join，返回 `"sha256:<hex>"`）
  - `_proto`：`bridge/core` 引用 protocol 的**唯一入口**（`from ._proto import envelope, framing`）。直接 `from protocol import ...` 在打包后的 `bl_ext.*` 命名空间下会 `ModuleNotFoundError`——spec §3.1 约束 2 的同类问题，作用在跨包引用上

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_scene_hash.py
from bridge.core import scene_hash


def test_quantize_normalizes_negative_zero_and_noise():
    assert scene_hash.quantize(-0.0) == scene_hash.quantize(0.0) == "0.000000"
    assert scene_hash.quantize(1.0000004) == "1.000000"   # 1e-6 以下噪声被吸收
    assert scene_hash.quantize(1.000001) == "1.000001"    # 1e-6 级差异保留


def test_digest_is_order_independent():
    a = scene_hash.object_line("Cube", "MESH", tuple(range(16)), "MESH", (8, 12, 6))
    b = scene_hash.object_line("Lamp", "LIGHT", tuple(range(16)), "LIGHT", ())
    assert scene_hash.digest([a, b]) == scene_hash.digest([b, a])
    assert scene_hash.digest([a, b]).startswith("sha256:")


def test_rename_changes_digest():
    m = tuple(float(i) for i in range(16))
    a = scene_hash.object_line("Cube", "MESH", m, "MESH", (8, 12, 6))
    b = scene_hash.object_line("Cube2", "MESH", m, "MESH", (8, 12, 6))
    assert scene_hash.digest([a]) != scene_hash.digest([b])


def test_snapshot_dataclass_shape():
    from bridge.core.contracts import SceneSnapshot
    s = SceneSnapshot(
        scene_revision=0, scene_hash="sha256:x", scene_name="Scene", scene_path=None,
        units_system="METRIC", units_scale_length=1.0, object_count=0, mesh_count=0,
        camera_count=0, light_count=0, collections=(),
    )
    assert s.managed_objects == ()   # Phase 0 恒空（§3.4）
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_scene_hash.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/contracts.py
"""core 与 bpy 世界之间的唯一边界。禁止 import bpy。spec §3.4。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ManagedObject:
    stable_id: str
    name: str
    type: str


@dataclass(frozen=True)
class SceneSnapshot:
    scene_revision: int
    scene_hash: str
    scene_name: str
    scene_path: str | None
    units_system: str
    units_scale_length: float
    object_count: int
    mesh_count: int
    camera_count: int
    light_count: int
    collections: tuple[str, ...]
    managed_objects: tuple[ManagedObject, ...] = ()


class SceneReader(Protocol):
    def blender_version(self) -> str: ...
    def snapshot(self) -> SceneSnapshot: ...


class Clock(Protocol):
    def monotonic(self) -> float: ...
```

```python
# bridge/core/scene_hash.py
"""§3.5 hash 算法的纯函数实现——零 bpy，进 L1。bpy 侧只负责喂原始元组。"""
from __future__ import annotations

import hashlib


def quantize(v: float) -> str:
    q = round(v, 6)
    if q == 0.0:
        q = 0.0  # 归一 -0.0
    return f"{q:.6f}"


def object_line(name: str, obj_type: str, matrix16: tuple[float, ...],
                data_kind: str, data_counts: tuple[int, ...]) -> str:
    m = ",".join(quantize(v) for v in matrix16)
    c = ",".join(str(n) for n in data_counts)
    return f"{name}\t{obj_type}\t{m}\t{data_kind}\t{c}"


def digest(lines: list[str]) -> str:
    joined = "\n".join(sorted(lines))
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()
```

另建导入垫片——**此后 `bridge/core` 任何文件引用 protocol 都必须走它**：

```python
# bridge/core/_proto.py
"""protocol 的双路径导入：仓库内走顶层包，打包进扩展后走 _vendor。
bl_ext.<repo>.<ext_id> 命名空间下不存在顶层 protocol（spec §3.1 约束 2 的跨包版）。"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:            # mypy 只走这条：拿到真实类型
    from protocol import envelope, framing
else:                        # 运行时双路径
    try:
        from .._vendor.protocol import envelope, framing
    except ImportError:      # 仓库/测试环境
        from protocol import envelope, framing

__all__ = ["envelope", "framing"]
```

**`TYPE_CHECKING` 分支不可省。** 没有它，mypy 取 try 分支的 `.._vendor.protocol`——该模块被 `[[tool.mypy.overrides]]` 判为 `Any`，于是 `bridge/core` 经 `_proto` 拿到的 `envelope`/`framing` 全变成 `Any`，`Router.handle` 的 `return envelope.ok_frame(...)` 在 strict 的 `warn_return_any` 下逐个报错。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_scene_hash.py -q` → 4 passed

- [ ] **Step 5: Commit**

```bash
git add bridge/core/contracts.py bridge/core/scene_hash.py bridge/core/_proto.py tests/unit/test_scene_hash.py
git commit -m "feat(bridge-core): SceneReader 契约与纯函数 scene_hash

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: bridge/core/queue.py

**Files:**
- Create: `bridge/core/queue.py`
- Test: `tests/unit/test_queue.py`

**Interfaces:**
- Consumes: `protocol.envelope.Request`；`bridge.core.contracts.Clock`
- Produces:
  - `class QueueFull(Exception)`
  - `TaskQueue(handler: Callable[[Request], bytes], clock: Clock, capacity: int = 64, diag: logging.Logger | None = None)`
    - `submit(request: Request, reply: Callable[[bytes], None], deadline: float) -> None`（线程安全；满抛 `QueueFull`）
    - `tick(budget_ms: int = 50) -> float`（批处理；过期丢弃；reply 的 `OSError` 吞掉；handler 异常回 `SCENE_QUERY_FAILED` 帧；返回 0.01 忙 / 0.1 闲）
    - `pending: int` 属性；`drain() -> int`（清空不回复，供 stop 第 8 步）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_queue.py
import logging

import pytest
from bridge.core.queue import QueueFull, TaskQueue
from protocol import envelope


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now


def req(method: str = "ping") -> envelope.Request:
    return envelope.Request.new(token="t", method=method, params={})


def make(handler=None, capacity=64):
    clock = FakeClock()
    q = TaskQueue(handler or (lambda r: envelope.ok_frame(r.id, {})), clock,
                  capacity=capacity, diag=logging.getLogger("test"))
    return q, clock


def test_batch_processes_within_budget_and_reports_idle_interval():
    q, clock = make()
    got: list[bytes] = []
    for _ in range(5):
        q.submit(req(), got.append, deadline=clock.now + 2.0)
    assert q.tick() == 0.1          # 5 个全处理完 → 闲
    assert len(got) == 5


def test_budget_exhaustion_leaves_remainder_and_reports_busy():
    q, clock = make(handler=lambda r: (_advance(clock, 0.030), envelope.ok_frame(r.id, {}))[1])
    for _ in range(3):              # 每个任务耗 30ms，预算 50ms → 一轮只能做 2 个
        q.submit(req(), lambda b: None, deadline=clock.now + 2.0)
    assert q.tick(budget_ms=50) == 0.01
    assert q.pending == 1


def _advance(clock: FakeClock, dt: float) -> None:
    clock.now += dt


def test_expired_task_dropped_without_handler_call():
    calls = []
    q, clock = make(handler=lambda r: (calls.append(r), envelope.ok_frame(r.id, {}))[1])
    q.submit(req(), lambda b: None, deadline=clock.now - 0.001)   # 已过期
    q.tick()
    assert calls == []


def test_reply_oserror_swallowed_and_next_task_processed():
    q, clock = make()
    def broken(_: bytes) -> None:
        raise BrokenPipeError()
    got: list[bytes] = []
    q.submit(req(), broken, deadline=clock.now + 2.0)
    q.submit(req(), got.append, deadline=clock.now + 2.0)
    q.tick()
    assert len(got) == 1            # 后续任务不受前面 reply 失败影响


def test_handler_exception_becomes_scene_query_failed_frame():
    import json
    from protocol import framing
    q, clock = make(handler=lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
    got: list[bytes] = []
    q.submit(req("scene_summary"), got.append, deadline=clock.now + 2.0)
    q.tick()
    err = json.loads(framing.FrameBuffer().feed(got[0])[0])
    assert err["error"]["code"] == envelope.SCENE_QUERY_FAILED
    assert "RuntimeError" in err["error"]["message"]
    assert "boom" not in err["error"]["message"]      # 异常文本不进响应（§5）


def test_capacity_overflow_raises():
    q, clock = make(capacity=2)
    q.submit(req(), lambda b: None, deadline=clock.now + 2.0)
    q.submit(req(), lambda b: None, deadline=clock.now + 2.0)
    with pytest.raises(QueueFull):
        q.submit(req(), lambda b: None, deadline=clock.now + 2.0)


def test_drain_clears_without_reply():
    q, clock = make()
    got: list[bytes] = []
    q.submit(req(), got.append, deadline=clock.now + 2.0)
    assert q.drain() == 1
    assert q.pending == 0 and got == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_queue.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/queue.py
"""主线程任务队列。spec §3.6：deadline 丢弃、预算批处理、reply 失败吞掉。"""
from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from ._proto import envelope
from .contracts import Clock

IDLE_INTERVAL = 0.1
BUSY_INTERVAL = 0.01


class QueueFull(Exception):
    pass


@dataclass(frozen=True)
class _Task:
    request: envelope.Request
    reply: Callable[[bytes], None]
    deadline: float


class TaskQueue:
    def __init__(self, handler: Callable[[envelope.Request], bytes], clock: Clock,
                 capacity: int = 64, diag: logging.Logger | None = None) -> None:
        self._handler = handler
        self._clock = clock
        self._capacity = capacity
        self._diag = diag or logging.getLogger("bcx.bridge")
        self._lock = threading.Lock()
        self._tasks: deque[_Task] = deque()

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._tasks)

    def submit(self, request: envelope.Request, reply: Callable[[bytes], None],
               deadline: float) -> None:
        with self._lock:
            if len(self._tasks) >= self._capacity:
                raise QueueFull(request.id)
            self._tasks.append(_Task(request, reply, deadline))

    def drain(self) -> int:
        with self._lock:
            n = len(self._tasks)
            self._tasks.clear()
            return n

    def tick(self, budget_ms: int = 50) -> float:
        end = self._clock.monotonic() + budget_ms / 1000.0
        while self._clock.monotonic() < end:
            with self._lock:
                if not self._tasks:
                    return IDLE_INTERVAL
                task = self._tasks.popleft()
            if self._clock.monotonic() > task.deadline:
                self._diag.info("drop expired request %s", task.request.id)
                continue
            try:
                frame = self._handler(task.request)
            except Exception as e:  # handler 层兜底：异常类型可回，文本不回（§5）
                self._diag.exception("handler failed for %s", task.request.id)
                frame = envelope.error_frame(task.request.id, envelope.SCENE_QUERY_FAILED,
                                             type(e).__name__)
            try:
                task.reply(frame)
            except OSError:
                self._diag.info("reply failed for %s (peer gone)", task.request.id)
        return BUSY_INTERVAL if self.pending else IDLE_INTERVAL
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_queue.py -q` → 7 passed

- [ ] **Step 5: Commit**

```bash
git add bridge/core/queue.py tests/unit/test_queue.py
git commit -m "feat(bridge-core): 任务队列——deadline 丢弃、预算批处理、reply 失败隔离

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: bridge/core/session.py

**Files:**
- Create: `bridge/core/session.py`
- Test: `tests/unit/test_session.py`

**Interfaces:**
- Produces:
  - `class SessionAuth`: `SessionAuth(token: str)`；`SessionAuth.generate() -> str`（`secrets.token_urlsafe(32)`）；`verify(presented: object) -> bool`（非 str 或不匹配 → False；`secrets.compare_digest` 常数时间）
  - `write_session_file(path: Path, data: dict) -> None`——同目录临时文件 `os.open(O_WRONLY|O_CREAT|O_EXCL, 0o600)` 写入后 `os.replace`（§2.2）
  - `read_session_file(path: Path) -> dict`——损坏/非 dict 抛 `ValueError`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_session.py
import json
import stat

import pytest
from bridge.core.session import SessionAuth, read_session_file, write_session_file


def test_generate_token_length_and_uniqueness():
    a, b = SessionAuth.generate(), SessionAuth.generate()
    assert a != b and len(a) >= 43


def test_verify_accepts_only_exact_string():
    auth = SessionAuth("secret-token")
    assert auth.verify("secret-token") is True
    assert auth.verify("secret-tokeN") is False
    assert auth.verify(None) is False
    assert auth.verify(123) is False


def test_write_session_file_is_0600_and_atomic(tmp_path):
    p = tmp_path / "session.json"
    write_session_file(p, {"a": 1})
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert json.loads(p.read_text()) == {"a": 1}
    write_session_file(p, {"a": 2})          # 覆盖已存在文件也必须成功（os.replace）
    assert read_session_file(p) == {"a": 2}
    assert list(tmp_path.iterdir()) == [p]   # 无临时文件残留


def test_read_session_file_rejects_corrupt(tmp_path):
    p = tmp_path / "session.json"
    p.write_text("{not json")
    with pytest.raises(ValueError):
        read_session_file(p)
    p.write_text("[1,2]")
    with pytest.raises(ValueError):
        read_session_file(p)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_session.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/session.py
"""会话 token 与 session.json 原子读写。spec §2.2、§4.1。"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any


class SessionAuth:
    def __init__(self, token: str) -> None:
        self._token = token

    @staticmethod
    def generate() -> str:
        return secrets.token_urlsafe(32)

    def verify(self, presented: object) -> bool:
        if not isinstance(presented, str):
            return False
        return secrets.compare_digest(self._token.encode(), presented.encode())


def write_session_file(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, path)


def read_session_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"bad session file: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("session file must be an object")
    return raw
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_session.py -q` → 4 passed

- [ ] **Step 5: Commit**

```bash
git add bridge/core/session.py tests/unit/test_session.py
git commit -m "feat(bridge-core): 会话 token 与 session.json 原子读写

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: bridge/core/router.py（+ contracts 扩展）

**Files:**
- Create: `bridge/core/router.py`
- Modify: `bridge/core/contracts.py`（`SceneReader` 增加轻量方法——`status` 不得触发全场景 hash，防 R-P0-08 拖爆 2 s 超时）
- Test: `tests/unit/test_router.py`

**Interfaces:**
- Consumes: `envelope.Request` / `ok_frame` / `error_frame`；`SceneReader`
- Produces:
  - `contracts.SceneReader` 新增：`status_info() -> tuple[str | None, int]`（`(scene_path, scene_revision)`，轻量、不算 hash）
  - `@dataclass(frozen=True) BridgeMeta(instance_id: str, pid: int, bridge_version: str, blender_version: str)`
  - `class Router`: `Router(reader: SceneReader, meta: BridgeMeta)`；`handle(req: Request) -> bytes`（整帧）。method 语义：
    - `ping` → `{"instance_id", "bridge_version", "blender_version", "envelope_version"}`（§3.3 握手响应）
    - `status` → `{"instance_id", "pid", "mode": "gui", "blender_version", "scene_path", "scene_revision"}`（`bridge_state`/`blender_supported`/`version_warning` 是 **Server 侧**字段，Bridge 不产）
    - `scene_summary` → `SceneSnapshot` 按 §6.2 outputSchema 展开（见实现）
    - 其他 → `UNKNOWN_METHOD` 错误帧

- [ ] **Step 1: 在 contracts.py 的 `SceneReader` 协议中加一行**

```python
class SceneReader(Protocol):
    def blender_version(self) -> str: ...
    def status_info(self) -> tuple[str | None, int]: ...
    def snapshot(self) -> SceneSnapshot: ...
```

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/test_router.py
import json

from bridge.core.contracts import SceneSnapshot
from bridge.core.router import BridgeMeta, Router
from protocol import envelope, framing


class FakeReader:
    def blender_version(self) -> str:
        return "5.2.0"

    def status_info(self):
        return ("/tmp/a.blend", 7)

    def snapshot(self) -> SceneSnapshot:
        return SceneSnapshot(
            scene_revision=7, scene_hash="sha256:abc", scene_name="Scene",
            scene_path="/tmp/a.blend", units_system="METRIC", units_scale_length=1.0,
            object_count=3, mesh_count=1, camera_count=1, light_count=1,
            collections=("Collection",),
        )


META = BridgeMeta(instance_id="gui-1-aa", pid=1, bridge_version="0.1.0",
                  blender_version="5.2.0")


def call(method: str) -> dict:
    router = Router(FakeReader(), META)
    frame = router.handle(envelope.Request.new("t", method, {}))
    return json.loads(framing.FrameBuffer().feed(frame)[0])


def test_ping_carries_identity_and_envelope_version():
    r = call("ping")["result"]
    assert r == {"instance_id": "gui-1-aa", "bridge_version": "0.1.0",
                 "blender_version": "5.2.0", "envelope_version": 1}


def test_status_is_lightweight_shape():
    r = call("status")["result"]
    assert r == {"instance_id": "gui-1-aa", "pid": 1, "mode": "gui",
                 "blender_version": "5.2.0", "scene_path": "/tmp/a.blend",
                 "scene_revision": 7}


def test_scene_summary_matches_spec_shape():
    r = call("scene_summary")["result"]
    assert r["scene_hash"] == "sha256:abc"
    assert r["scene_name"] == "Scene"
    assert r["units"] == {"system": "METRIC", "scale_length": 1.0}
    assert r["summary"]["object_count"] == 3
    assert r["summary"]["managed_objects"] == []


def test_unknown_method():
    body = call("nope")
    assert body["ok"] is False
    assert body["error"]["code"] == envelope.UNKNOWN_METHOD
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_router.py -q` → FAIL

- [ ] **Step 4: 实现**

```python
# bridge/core/router.py
"""method → 响应帧。认证已由 I/O 层完成，本层假设请求可信格式已校验。"""
from __future__ import annotations

from dataclasses import dataclass

from ._proto import envelope
from .contracts import SceneReader


@dataclass(frozen=True)
class BridgeMeta:
    instance_id: str
    pid: int
    bridge_version: str
    blender_version: str


class Router:
    def __init__(self, reader: SceneReader, meta: BridgeMeta) -> None:
        self._reader = reader
        self._meta = meta

    def handle(self, req: envelope.Request) -> bytes:
        if req.method == "ping":
            return envelope.ok_frame(req.id, {
                "instance_id": self._meta.instance_id,
                "bridge_version": self._meta.bridge_version,
                "blender_version": self._meta.blender_version,
                "envelope_version": envelope.ENVELOPE_VERSION,
            })
        if req.method == "status":
            scene_path, scene_revision = self._reader.status_info()
            return envelope.ok_frame(req.id, {
                "instance_id": self._meta.instance_id, "pid": self._meta.pid,
                "mode": "gui", "blender_version": self._meta.blender_version,
                "scene_path": scene_path, "scene_revision": scene_revision,
            })
        if req.method == "scene_summary":
            s = self._reader.snapshot()
            return envelope.ok_frame(req.id, {
                "scene_revision": s.scene_revision, "scene_hash": s.scene_hash,
                "scene_name": s.scene_name, "scene_path": s.scene_path,
                "units": {"system": s.units_system, "scale_length": s.units_scale_length},
                "summary": {
                    "object_count": s.object_count, "mesh_count": s.mesh_count,
                    "camera_count": s.camera_count, "light_count": s.light_count,
                    "collections": list(s.collections),
                    "managed_objects": [
                        {"stable_id": m.stable_id, "name": m.name, "type": m.type}
                        for m in s.managed_objects
                    ],
                },
            })
        return envelope.error_frame(req.id, envelope.UNKNOWN_METHOD, req.method)
```

注意 `scene_summary` 结果不含 `instance_id`/`version_warning`——那两个字段由 Server 侧 adapter 补（§6.2 outputSchema 是**工具**的形状，不是 Bridge method 的形状）。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/unit/ -q` → 全绿（含此前任务）

- [ ] **Step 6: Commit**

```bash
git add bridge/core/router.py bridge/core/contracts.py tests/unit/test_router.py
git commit -m "feat(bridge-core): method 路由；SceneReader 增加轻量 status_info

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: bridge/core/lifecycle.py（I/O 线程 + 会话启停）

本任务是 Bridge 侧核心。实现 §3.7 连接模型五规则（单写者）与 §4.1 启动序列、10 步关闭。

**Files:**
- Create: `bridge/core/lifecycle.py`
- Test: `tests/unit/test_lifecycle.py`

**Interfaces:**
- Consumes: Task 1–6 全部
- Produces:
  - `BRIDGE_VERSION: str = "0.1.0"`
  - `class BridgeSession`:
    - `BridgeSession.start(runtime_root: Path, reader: SceneReader, blender_version: str, clock: Clock | None = None) -> BridgeSession`
    - `.tick(budget_ms: int = 50) -> float`（主线程调；转发 `TaskQueue.tick`）
    - `.stop() -> None`（幂等；§3.7 10 步序）
    - `.instance_id: str`、`.session_dir: Path`、`.socket_path: Path`、`.token: str`（测试用只读属性）
  - `send(conn, frame)`——**唯一发送入口**：任意线程可调，只入 outbox + 唤醒；socket 写只发生在 I/O 线程（§3.7 规则 3 单写者）
  - 内部 `_mkdir_private(path)`（逐级 mkdir + chmod 0700）与 `_resolve_socket_path`（≤100 字节校验，超限 `tempfile.mkdtemp(prefix="bcx-")` 回退）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_lifecycle.py
import json
import socket
import stat
import threading
import time

import pytest
from bridge.core.contracts import SceneSnapshot
from bridge.core.lifecycle import BridgeSession
from protocol import envelope, framing


class FakeReader:
    def blender_version(self) -> str:
        return "5.2.0"

    def status_info(self):
        return (None, 0)

    def snapshot(self) -> SceneSnapshot:
        return SceneSnapshot(
            scene_revision=0, scene_hash="sha256:e", scene_name="Scene", scene_path=None,
            units_system="NONE", units_scale_length=1.0, object_count=0, mesh_count=0,
            camera_count=0, light_count=0, collections=(),
        )


@pytest.fixture
def session(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    pump = threading.Thread(target=lambda: _pump(s), daemon=True)
    pump.start()
    yield s
    s.stop()


def _pump(s: BridgeSession) -> None:   # 测试里代替 Blender timer 驱动主线程 tick
    while not s.stopped:
        time.sleep(s.tick(budget_ms=50))


def _rpc(s: BridgeSession, method: str, token: str | None = None) -> dict:
    with socket.socket(socket.AF_UNIX) as c:
        c.settimeout(2.0)
        c.connect(str(s.socket_path))
        tok = s.token if token is None else token
        c.sendall(envelope.encode_request(envelope.Request.new(tok, method, {})))
        buf = framing.FrameBuffer()
        while True:
            data = c.recv(65536)
            if not data:
                return {"__closed__": True}
            frames = buf.feed(data)
            if frames:
                return json.loads(frames[0])


def test_start_creates_private_files(session, tmp_path):
    d = session.session_dir
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert stat.S_IMODE(session.socket_path.stat().st_mode) == 0o600
    sj = json.loads((d / "session.json").read_text())
    assert sj["instance_id"] == session.instance_id
    assert sj["socket_path"] == str(session.socket_path)
    assert sj["envelope_version"] == 1


def test_ping_roundtrip(session):
    body = _rpc(session, "ping")
    assert body["ok"] is True
    assert body["result"]["instance_id"] == session.instance_id


def test_wrong_token_closed_without_response(session):
    assert _rpc(session, "ping", token="bad") == {"__closed__": True}


def test_half_header_does_not_wedge_other_connections(session):
    slow = socket.socket(socket.AF_UNIX)
    slow.connect(str(session.socket_path))
    slow.sendall(b"\x00\x00")            # 半个长度头，然后沉默
    try:
        assert _rpc(session, "ping")["ok"] is True   # 其余连接照常服务（§3.7 规则 1）
    finally:
        slow.close()


def test_stop_is_idempotent_and_cleans_up(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    c = socket.socket(socket.AF_UNIX)
    c.connect(str(s.socket_path))
    s.stop()
    s.stop()                              # 幂等
    assert not s.socket_path.exists()
    assert not s.session_dir.exists()
    assert c.recv(1) == b""               # 活跃连接被关闭（§3.7 第 4 步）
    c.close()


def test_sun_path_fallback(tmp_path):
    deep = tmp_path / ("x" * 90)          # 让默认 socket 路径必然超 100 字节
    s = BridgeSession.start(deep, FakeReader(), blender_version="5.2.0")
    try:
        assert len(str(s.socket_path).encode()) <= 100
        assert s.session_dir.exists()     # session.json 仍在 runtime 根下
    finally:
        s.stop()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_lifecycle.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/lifecycle.py
"""会话生命周期与 I/O 线程。spec §2.2 权限表、§3.7 连接模型（单写者五规则）、§4.1 启动序列。"""
from __future__ import annotations

import logging
import os
import secrets
import select
import socket
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from ._proto import envelope, framing
from .contracts import Clock, SceneReader
from .queue import QueueFull, TaskQueue
from .router import BridgeMeta, Router
from .session import SessionAuth, write_session_file

BRIDGE_VERSION = "0.1.0"
MAX_SUN_PATH = 100
MAX_OUTBOX = 32 * 1024 * 1024        # §3.7 规则 4：发送背压上限
_diag = logging.getLogger("bcx.bridge")


class _MonotonicClock:
    def monotonic(self) -> float:
        return time.monotonic()


def _mkdir_private(path: Path) -> None:
    """逐级创建并逐级 chmod 0700——makedirs 的 mode 不作用于中间目录（§2.2）。"""
    for p in [*reversed(path.parents), path]:
        if not p.exists():
            p.mkdir(mode=0o700)
            os.chmod(p, 0o700)


class _Conn:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buf = framing.FrameBuffer()
        self.outbox: deque[bytes] = deque()   # 只由 I/O 线程消费（§3.7 规则 3）
        self.outbox_bytes = 0
        self.send_offset = 0                  # outbox[0] 的部分写偏移


class BridgeSession:
    def __init__(self, clock: Clock) -> None:  # 仅供 start() 使用；属性全部在此声明（mypy strict）
        self.stopped = False
        self.instance_id = ""
        self.token = ""
        self.session_dir = Path()
        self.socket_path = Path()
        self._sock_tmpdir: Path | None = None
        self._clock = clock
        self._conns: dict[int, _Conn] = {}
        self._conns_lock = threading.Lock()
        self._queue: TaskQueue | None = None
        self._auth: SessionAuth | None = None
        self._listener: socket.socket | None = None
        self._wake_r: socket.socket | None = None
        self._wake_w: socket.socket | None = None
        self._io: threading.Thread | None = None

    # ---------- 启动 ----------
    @classmethod
    def start(cls, runtime_root: Path, reader: SceneReader, blender_version: str,
              clock: Clock | None = None) -> "BridgeSession":
        self = cls(clock or _MonotonicClock())
        self.instance_id = f"gui-{os.getpid()}-{secrets.token_hex(4)}"
        self.session_dir = Path(runtime_root) / "run" / self.instance_id
        _mkdir_private(self.session_dir)

        self.token = SessionAuth.generate()
        self._auth = SessionAuth(self.token)
        self.socket_path, self._sock_tmpdir = self._resolve_socket_path(self.session_dir)

        write_session_file(self.session_dir / "session.json", {
            "instance_id": self.instance_id, "token": self.token, "pid": os.getpid(),
            "socket_path": str(self.socket_path), "blender_version": blender_version,
            "bridge_version": BRIDGE_VERSION,
            "envelope_version": envelope.ENVELOPE_VERSION,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

        router = Router(reader, BridgeMeta(self.instance_id, os.getpid(),
                                           BRIDGE_VERSION, blender_version))
        self._queue = TaskQueue(router.handle, self._clock, diag=_diag)

        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)          # §2.2：bind 后立即收权限
        listener.listen(8)
        listener.setblocking(False)
        self._listener = listener
        self._wake_r, self._wake_w = socket.socketpair()
        self._wake_r.setblocking(False)
        self._io = threading.Thread(target=self._io_loop, name="bcx-io", daemon=True)
        self._io.start()
        return self

    @staticmethod
    def _resolve_socket_path(session_dir: Path) -> tuple[Path, Path | None]:
        p = session_dir / "bridge.sock"
        if len(str(p).encode()) <= MAX_SUN_PATH:
            return p, None
        short = Path(tempfile.mkdtemp(prefix="bcx-"))   # $TMPDIR，天然 0700（R-P0-09）
        return short / "bridge.sock", short

    # ---------- 发送：唯一入口（§3.7 规则 3 单写者） ----------
    def send(self, conn: _Conn, frame: bytes) -> None:
        """任意线程可调；只入 outbox + 唤醒。对已断开连接静默丢弃（§3.6）。"""
        with self._conns_lock:
            if conn.sock.fileno() not in self._conns:
                return
            conn.outbox.append(frame)
            conn.outbox_bytes += len(frame)
        self._wake()

    def _wake(self) -> None:
        try:
            if self._wake_w is not None:
                self._wake_w.send(b"x")
        except OSError:
            pass

    # ---------- I/O 线程（§3.7 五规则） ----------
    def _io_loop(self) -> None:
        while True:
            try:
                if self._io_iterate():
                    return
            except Exception:                            # 规则 5：护栏，绝不带走线程
                _diag.exception("io loop iteration failed")

    def _io_iterate(self) -> bool:
        assert self._listener is not None and self._wake_r is not None
        with self._conns_lock:
            conns = list(self._conns.values())
        rlist: list[socket.socket] = [self._listener, self._wake_r]
        rlist += [c.sock for c in conns]
        wlist = [c.sock for c in conns if c.outbox]
        ready_r, ready_w, _ = select.select(rlist, wlist, [], 1.0)
        if self._wake_r in ready_r:
            try:
                while self._wake_r.recv(4096):
                    pass
            except OSError:
                pass
            if self.stopped:
                return True
        if self._listener in ready_r:
            try:
                sock, _ = self._listener.accept()
                sock.setblocking(False)
                with self._conns_lock:
                    self._conns[sock.fileno()] = _Conn(sock)
            except OSError:
                pass
        for conn in conns:
            if conn.sock in ready_w:
                self._flush(conn)
        for conn in conns:
            if conn.sock in ready_r:
                self._read(conn)
        self._enforce_backpressure(conns)
        return False

    def _enforce_backpressure(self, conns: list[_Conn]) -> None:
        """规则 4 由 I/O 线程执行——主线程绝不触碰 socket（规则 3 的结构性保证）。"""
        for conn in conns:
            with self._conns_lock:
                over = conn.outbox_bytes > MAX_OUTBOX
            if over:
                _diag.info("outbox limit exceeded, dropping connection")
                self._drop(conn)

    def _flush(self, conn: _Conn) -> None:
        try:
            while True:
                with self._conns_lock:       # outbox 的每次读写都持锁：send() 在另一
                    if not conn.outbox:      # 线程做 +=，单边持锁不构成互斥
                        return
                    head = conn.outbox[0]
                view = memoryview(head)[conn.send_offset:]
                sent = conn.sock.send(view)  # send_offset 只由 I/O 线程访问，无需锁
                if sent < len(view):
                    conn.send_offset += sent             # 部分写：偏移续写（规则 3）
                    return
                with self._conns_lock:
                    conn.outbox.popleft()
                    conn.outbox_bytes -= len(head)
                conn.send_offset = 0
        except BlockingIOError:
            return
        except OSError:
            self._drop(conn)

    def _read(self, conn: _Conn) -> None:
        try:
            data = conn.sock.recv(65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._drop(conn)
            return
        try:
            frames = conn.buf.feed(data)
        except framing.FrameTooLarge:
            self._drop(conn)                             # 读端超限断开（§3.2）
            return
        for payload in frames:
            self._dispatch(conn, payload)

    def _dispatch(self, conn: _Conn, payload: bytes) -> None:
        assert self._auth is not None and self._queue is not None
        try:
            req = envelope.decode_request(payload)
        except ValueError:
            self._drop(conn)                             # 解码失败断开，不回帧（§5）
            return
        if not self._auth.verify(req.token):
            _diag.info("auth failed, closing connection")  # §5.2 Bridge 诊断日志
            self._drop(conn)
            return
        timeout = envelope.METHOD_TIMEOUTS.get(req.method, 2.0)
        deadline = self._clock.monotonic() + timeout
        try:
            self._queue.submit(req, lambda frame: self.send(conn, frame), deadline)
        except QueueFull:
            self.send(conn, envelope.error_frame(req.id, envelope.BRIDGE_BUSY,
                                                 "queue full", retryable=True))

    def _drop(self, conn: _Conn) -> None:
        with self._conns_lock:
            self._conns.pop(conn.sock.fileno(), None)
        try:
            conn.sock.close()
        except OSError:
            pass

    # ---------- 主线程 ----------
    def tick(self, budget_ms: int = 50) -> float:
        assert self._queue is not None
        return self._queue.tick(budget_ms)   # 主线程只跑队列：不碰 _conns、不碰 socket

    # ---------- 关闭（§3.7 10 步，幂等） ----------
    def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True                              # 1 置停止标志
        steps = [
            self._wake,                                  # 2 唤醒 select
            self._join_io,                               # 3 join I/O 线程
            self._close_all_conns,                       # 4 关闭活跃连接（含丢弃 outbox）
            self._close_listener,                        # 5 关监听与 socketpair
            lambda: None,                                # 6 timer 注销：driver 层职责（Task 13）
            lambda: None,                                # 7 handler 注销：driver 层职责（Task 13）
            self._drain_queue,                           # 8 清空队列不回复
            self._unlink_files,                          # 9 删 socket 与 session.json
            self._remove_dirs,                           # 10 删会话目录
        ]
        for i, step in enumerate(steps, start=2):
            try:
                step()
            except Exception:
                _diag.exception("stop step %d failed, continuing", i)

    def _join_io(self) -> None:
        if self._io is not None:
            self._io.join(timeout=2.0)

    def _drain_queue(self) -> None:
        if self._queue is not None:
            self._queue.drain()

    def _close_listener(self) -> None:
        for sock in (self._listener, self._wake_r, self._wake_w):
            if sock is not None:
                sock.close()

    def _close_all_conns(self) -> None:
        with self._conns_lock:
            conns, self._conns = list(self._conns.values()), {}
        for c in conns:
            try:
                c.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            c.sock.close()

    def _unlink_files(self) -> None:
        self.socket_path.unlink(missing_ok=True)
        (self.session_dir / "session.json").unlink(missing_ok=True)

    def _remove_dirs(self) -> None:
        for d in (self._sock_tmpdir, self.session_dir):
            if d is not None and d.exists():
                for child in d.iterdir():
                    child.unlink(missing_ok=True)
                d.rmdir()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_lifecycle.py -q` → 6 passed
（若 `test_half_header...` 偶发超时：检查 select 集合是否含已建立连接——那正是 §3.7 规则 1 要抓的缺陷）

- [ ] **Step 5: Commit**

```bash
git add bridge/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(bridge-core): I/O 线程 select 多路复用、会话启停 10 步序、sun_path 回退

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: server/core/config.py + path_policy.py

**Files:**
- Create: `server/core/config.py`、`server/core/path_policy.py`
- Test: `tests/unit/test_config.py`、`tests/unit/test_path_policy.py`

**Interfaces:**
- Produces:
  - `config.runtime_root() -> Path`——`$BLENDERCODEX_ROOT` 或默认 `~/Library/Application Support/BlenderCodex`（§7.2）；`config.run_dir() -> Path`（root/"run"）；`config.logs_dir() -> Path`（root/"logs"）
  - `class PathDenied(Exception)`
  - `class PathPolicy(roots: list[Path], allowed_exts: set[str])`；`.resolve(raw: str) -> Path`——`expanduser → realpath → containment → 扩展名白名单`，任一步不过抛 `PathDenied`（URS FR-30，fail-closed）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_config.py
from pathlib import Path

from server.core import config


def test_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BLENDERCODEX_ROOT", str(tmp_path))
    assert config.runtime_root() == tmp_path
    assert config.run_dir() == tmp_path / "run"
    assert config.logs_dir() == tmp_path / "logs"


def test_default_under_app_support(monkeypatch):
    monkeypatch.delenv("BLENDERCODEX_ROOT", raising=False)
    p = config.runtime_root()
    assert p == Path.home() / "Library" / "Application Support" / "BlenderCodex"
```

```python
# tests/unit/test_path_policy.py
import os

import pytest
from server.core.path_policy import PathDenied, PathPolicy


@pytest.fixture
def policy(tmp_path):
    (tmp_path / "ws").mkdir()
    return PathPolicy(roots=[tmp_path / "ws"], allowed_exts={".blend", ".json"})


def test_accepts_inside_root(policy, tmp_path):
    p = policy.resolve(str(tmp_path / "ws" / "a.blend"))
    assert p == (tmp_path / "ws" / "a.blend").resolve()


def test_rejects_dotdot_escape(policy, tmp_path):
    with pytest.raises(PathDenied):
        policy.resolve(str(tmp_path / "ws" / ".." / "outside.blend"))


def test_rejects_symlink_escape(policy, tmp_path):
    outside = tmp_path / "outside.blend"
    outside.write_text("x")
    link = tmp_path / "ws" / "link.blend"
    os.symlink(outside, link)
    with pytest.raises(PathDenied):
        policy.resolve(str(link))            # realpath 后越界


def test_rejects_bad_extension(policy, tmp_path):
    with pytest.raises(PathDenied):
        policy.resolve(str(tmp_path / "ws" / "evil.py"))


def test_rejects_tilde_escape(policy):
    with pytest.raises(PathDenied):
        policy.resolve("~/outside.blend")    # expanduser 后仍须 containment
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_path_policy.py -q` → FAIL

- [ ] **Step 3: 实现**

```python
# server/core/config.py
"""runtime 根注入点。spec §7.2：BLENDERCODEX_ROOT。"""
from __future__ import annotations

import os
from pathlib import Path


def runtime_root() -> Path:
    env = os.environ.get("BLENDERCODEX_ROOT")
    if env:
        return Path(env)
    return Path.home() / "Library" / "Application Support" / "BlenderCodex"


def run_dir() -> Path:
    return runtime_root() / "run"


def logs_dir() -> Path:
    return runtime_root() / "logs"
```

```python
# server/core/path_policy.py
"""路径策略：fail-closed。URS FR-30。Phase 0 无路径参数，交付并测试，Phase 1 启用。"""
from __future__ import annotations

from pathlib import Path


class PathDenied(Exception):
    pass


class PathPolicy:
    def __init__(self, roots: list[Path], allowed_exts: set[str]) -> None:
        self._roots = [r.expanduser().resolve() for r in roots]
        self._exts = allowed_exts

    def resolve(self, raw: str) -> Path:
        p = Path(raw).expanduser()
        try:
            p = p.resolve(strict=False)      # realpath：吃掉 .. 与符号链接
        except OSError as e:
            raise PathDenied(f"unresolvable: {raw}") from e
        if p.suffix.lower() not in self._exts:
            raise PathDenied(f"extension not allowed: {p.suffix}")
        for root in self._roots:
            if p == root or root in p.parents:
                return p
        raise PathDenied(f"outside allowed roots: {p}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_path_policy.py -q` → 7 passed

- [ ] **Step 5: Commit**

```bash
git add server/core/config.py server/core/path_policy.py \
        tests/unit/test_config.py tests/unit/test_path_policy.py
git commit -m "feat(server-core): BLENDERCODEX_ROOT 注入点与 fail-closed 路径策略

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: server/core/audit.py + versions.py + capabilities.py

**Files:**
- Create: `server/core/audit.py`、`server/core/versions.py`、`server/core/capabilities.py`
- Test: `tests/unit/test_audit.py`、`tests/unit/test_versions.py`

**Interfaces:**
- Produces:
  - `audit.AuditLog(logs_dir: Path)`；`.record(tool: str, request_id: str, ok: bool, duration_ms: float, instance_id: str | None = None, params: dict | None = None, error: str | None = None, paths: list[str] | None = None, transaction_id: None = None) -> None`——追加一行 JSONL 到 `logs_dir/server-YYYY-MM-DD.jsonl`（UTC 日期）；目录 0700、文件 0600；`params_digest = sha256(canonical_json)[:16]`，**不记参数原文**（§5.2）
  - `versions.BASELINE: dict = {"version": "5.2.0", "platform": "macos-arm64"}`（§8.3）
  - `versions.check(blender_version: str) -> tuple[bool, str | None]`——`(blender_supported, version_warning)`；主次版本 `5.2` 匹配即 supported，否则 warning 文案含双方版本号（§4.4）
  - `capabilities.describe(server_version: str, connected: list[dict]) -> dict`——§6.3 outputSchema：`phase="phase0"`、`ir_schema_version=None`、`supported_operation_kinds=[]`、`supported_tools=["get_blender_status","get_scene_summary","describe_capabilities"]`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_audit.py
import json
import stat

from server.core.audit import AuditLog


def test_record_appends_jsonl_with_digest_not_raw_params(tmp_path):
    log = AuditLog(tmp_path / "logs")
    log.record("get_scene_summary", "req1", ok=True, duration_ms=12.5,
               instance_id="gui-1-aa", params={"instance_id": "gui-1-aa"})
    files = list((tmp_path / "logs").glob("server-*.jsonl"))
    assert len(files) == 1
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "logs").stat().st_mode) == 0o700
    row = json.loads(files[0].read_text().splitlines()[0])
    assert row["tool"] == "get_scene_summary"
    assert row["transaction_id"] is None          # Phase 0 占位（§5.2）
    assert row["paths"] == []
    assert "gui-1-aa" not in json.dumps(row.get("params_digest"))
    assert len(row["params_digest"]) == 16


def test_two_records_two_lines(tmp_path):
    log = AuditLog(tmp_path / "logs")
    log.record("a", "r1", ok=True, duration_ms=1.0)
    log.record("b", "r2", ok=False, duration_ms=2.0, error="BRIDGE_UNAVAILABLE")
    f = next((tmp_path / "logs").glob("server-*.jsonl"))
    lines = [json.loads(x) for x in f.read_text().splitlines()]
    assert [r["tool"] for r in lines] == ["a", "b"]
    assert lines[1]["error"] == "BRIDGE_UNAVAILABLE"
```

```python
# tests/unit/test_versions.py
from server.core import versions
from server.core.capabilities import describe


def test_baseline_pinned():
    assert versions.BASELINE == {"version": "5.2.0", "platform": "macos-arm64"}


def test_check_matrix():
    assert versions.check("5.2.0") == (True, None)
    assert versions.check("5.2.3") == (True, None)          # 同 5.2 系列
    ok, warn = versions.check("4.5.3")
    assert ok is False and "4.5.3" in warn and "5.2" in warn
    ok, warn = versions.check("6.0.0")
    assert ok is False and warn is not None


def test_gate_write_matrix():
    assert versions.gate_write("5.2.1") is None
    assert versions.gate_write("4.5.3") == "UNSUPPORTED_BLENDER_VERSION"


def test_describe_capabilities_shape():
    d = describe("0.1.0", connected=[])
    assert d["phase"] == "phase0"
    assert d["ir_schema_version"] is None
    assert d["supported_operation_kinds"] == []
    assert d["baseline_blender"] == {"version": "5.2.0", "platform": "macos-arm64"}
    assert d["envelope_version"] == 1
    assert set(d["supported_tools"]) == {"get_blender_status", "get_scene_summary",
                                         "describe_capabilities"}
    assert d["connected_instances"] == []
```

- [ ] **Step 2: 跑测试确认失败** → `uv run pytest tests/unit/test_audit.py tests/unit/test_versions.py -q`

- [ ] **Step 3: 实现**

```python
# server/core/audit.py
"""JSONL 审计。spec §5.2：参数只记摘要；transaction_id/paths 为 Phase 1 占位。"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, logs_dir: Path) -> None:
        self._dir = logs_dir
        for p in [*reversed(logs_dir.parents), logs_dir]:   # 逐级 0700（§2.2/NFR-S4：
            if not p.exists():                              # mkdir(parents=True) 的中间层
                p.mkdir(mode=0o700)                         # 会落在默认 umask 下）
                os.chmod(p, 0o700)

    def record(self, tool: str, request_id: str, ok: bool, duration_ms: float,
               instance_id: str | None = None, params: dict[str, Any] | None = None,
               error: str | None = None, paths: list[str] | None = None,
               transaction_id: None = None) -> None:
        now = datetime.datetime.now(datetime.UTC)
        digest = hashlib.sha256(
            json.dumps(params or {}, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode()
        ).hexdigest()[:16]
        row = {"ts": now.isoformat(timespec="milliseconds"), "request_id": request_id,
               "tool": tool, "instance_id": instance_id, "transaction_id": transaction_id,
               "params_digest": digest, "ok": ok, "duration_ms": round(duration_ms, 3),
               "paths": paths or [], "error": error}
        path = self._dir / f"server-{now:%Y-%m-%d}.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
```

```python
# server/core/versions.py
"""版本门禁。spec §4.4、§8.3：基线 5.2.0；Phase 0 只读放行 + 警告。"""
from __future__ import annotations

BASELINE: dict[str, str] = {"version": "5.2.0", "platform": "macos-arm64"}


def check(blender_version: str) -> tuple[bool, str | None]:
    base_mm = ".".join(BASELINE["version"].split(".")[:2])
    got_mm = ".".join(blender_version.split(".")[:2])
    if got_mm == base_mm:
        return True, None
    return False, (f"Blender {blender_version} 不是本系统基线（{base_mm} LTS）；"
                   f"只读工具可用，写工具将被拒绝")


# Phase 1 写工具用；Phase 0 仅单测（§4.4）
def gate_write(blender_version: str) -> str | None:
    ok, _ = check(blender_version)
    return None if ok else "UNSUPPORTED_BLENDER_VERSION"
```

```python
# server/core/capabilities.py
"""describe_capabilities 静态应答。spec §6.3：不经 Bridge，可离线回答。"""
from __future__ import annotations

from typing import Any

from protocol import envelope
from .versions import BASELINE

SUPPORTED_TOOLS = ["get_blender_status", "get_scene_summary", "describe_capabilities"]


def describe(server_version: str, connected: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "server_version": server_version,
        "envelope_version": envelope.ENVELOPE_VERSION,
        "phase": "phase0",
        "supported_tools": SUPPORTED_TOOLS,
        "baseline_blender": dict(BASELINE),
        "ir_schema_version": None,
        "supported_operation_kinds": [],
        "connected_instances": [
            {"instance_id": c["instance_id"], "blender_version": c["blender_version"],
             "bridge_version": c["bridge_version"]}
            for c in connected
        ],
    }
```

- [ ] **Step 4: 跑测试确认通过** → 7 passed

- [ ] **Step 5: Commit**

```bash
git add server/core/audit.py server/core/versions.py server/core/capabilities.py \
        tests/unit/test_audit.py tests/unit/test_versions.py
git commit -m "feat(server-core): 审计 JSONL、版本门禁、capabilities 静态应答

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: server/core/bridge_client.py

**Files:**
- Create: `server/core/bridge_client.py`
- Test: `tests/unit/test_bridge_client.py`

**Interfaces:**
- Consumes: `protocol.envelope`（`METHOD_TIMEOUTS`、编解码、错误码）
- Produces:
  - `class BridgeError(Exception)`：属性 `code: str`、`retryable: bool`
  - `class BridgeClient(session: dict)`（入参 = 解析后的 session.json，取 `socket_path`/`token`）
    - `.call(method: str, params: dict | None = None, timeout: float | None = None) -> dict`——返回 `result`；映射：连接失败/对端关闭 → `BRIDGE_UNAVAILABLE(retryable)`；超时 → `BRIDGE_TIMEOUT(retryable)`；Bridge 回错误帧 → `BridgeError(code=帧内 code)`

- [ ] **Step 1: 写失败测试**（用 Task 7 的 `BridgeSession` 当真实对端——它已零 bpy）

```python
# tests/unit/test_bridge_client.py
import threading
import time

import pytest
from bridge.core.lifecycle import BridgeSession
from server.core.bridge_client import BridgeClient, BridgeError
from tests.unit.test_lifecycle import FakeReader


@pytest.fixture
def live(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    t = threading.Thread(target=lambda: _pump(s), daemon=True)
    t.start()
    yield s
    s.stop()


def _pump(s):
    while not s.stopped:
        time.sleep(s.tick(50))


def _session_dict(s: BridgeSession) -> dict:
    return {"socket_path": str(s.socket_path), "token": s.token,
            "instance_id": s.instance_id}


def test_ping_result(live):
    c = BridgeClient(_session_dict(live))
    r = c.call("ping")
    assert r["instance_id"] == live.instance_id
    assert r["envelope_version"] == 1


def test_unavailable_when_socket_missing(tmp_path):
    c = BridgeClient({"socket_path": str(tmp_path / "no.sock"), "token": "t"})
    with pytest.raises(BridgeError) as ei:
        c.call("ping")
    assert ei.value.code == "BRIDGE_UNAVAILABLE" and ei.value.retryable


def test_unavailable_when_auth_rejected(live):
    c = BridgeClient({"socket_path": str(live.socket_path), "token": "wrong"})
    with pytest.raises(BridgeError) as ei:
        c.call("ping")
    assert ei.value.code == "BRIDGE_UNAVAILABLE"     # 对端静默断开的对外表现（§5）


def test_error_frame_maps_to_bridge_error(live):
    c = BridgeClient(_session_dict(live))
    with pytest.raises(BridgeError) as ei:
        c.call("no_such_method")
    assert ei.value.code == "UNKNOWN_METHOD"
```

- [ ] **Step 2: 跑测试确认失败** → `uv run pytest tests/unit/test_bridge_client.py -q`

- [ ] **Step 3: 实现**

```python
# server/core/bridge_client.py
"""UDS 客户端。spec §5 错误映射表。"""
from __future__ import annotations

import socket
from typing import Any

from protocol import envelope, framing


class BridgeError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.retryable = retryable


class BridgeClient:
    def __init__(self, session: dict[str, Any]) -> None:
        self._socket_path = session["socket_path"]
        self._token = session["token"]

    def call(self, method: str, params: dict[str, Any] | None = None,
             timeout: float | None = None) -> dict[str, Any]:
        timeout = timeout or envelope.METHOD_TIMEOUTS.get(method, 2.0)
        req = envelope.Request.new(self._token, method, params or {})
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect(self._socket_path)
                s.sendall(envelope.encode_request(req))
                buf = framing.FrameBuffer()
                while True:
                    try:
                        data = s.recv(65536)
                    except TimeoutError as e:
                        raise BridgeError(envelope.BRIDGE_TIMEOUT, method,
                                          retryable=True) from e
                    if not data:      # 对端关闭：认证失败或会话关闭（§5）
                        raise BridgeError(envelope.BRIDGE_UNAVAILABLE,
                                          "connection closed by bridge", retryable=True)
                    frames = buf.feed(data)
                    if frames:
                        resp = envelope.decode_response(frames[0])
                        break
        except (OSError, framing.FrameError, ValueError) as e:  # ValueError 含 decode_response 的畸形响应
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, str(type(e).__name__),
                              retryable=True) from e
        if not resp.get("ok"):
            err = resp.get("error", {})
            raise BridgeError(err.get("code", "UNKNOWN"), err.get("message", ""),
                              bool(err.get("retryable")))
        result = resp.get("result")
        if not isinstance(result, dict):
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed result")
        return result
```

- [ ] **Step 4: 跑测试确认通过** → 4 passed

- [ ] **Step 5: Commit**

```bash
git add server/core/bridge_client.py tests/unit/test_bridge_client.py
git commit -m "feat(server-core): UDS 客户端与错误码映射

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: server/core/discovery.py

**Files:**
- Create: `server/core/discovery.py`
- Test: `tests/unit/test_discovery.py`

**Interfaces:**
- Consumes: `config.run_dir()`、`BridgeClient`、`session.read_session_file`（从 `bridge.core.session` 导入——Server 侧允许 import bridge.core，反向禁止）、`versions.check`
- Produces:
  - `@dataclass Instance`: `session: dict`、`state: str`（`"connected" | "disconnected"`）、`blender_supported: bool`、`version_warning: str | None`、`client: BridgeClient | None`（连上时非 None）
  - `class Discovery(run_dir: Path, ttl: float = 1.0, clock=time.monotonic)`
    - `.instances(force: bool = False) -> list[Instance]`——1 秒缓存（§4.3）
    - `.find(instance_id: str) -> Instance | None`——精确匹配
    - 清理规则（§5.1）：`session.json` 可读 → 预筛 `os.kill(pid,0)` 失败 **且** 连接失败 → 删会话目录；`session.json` 缺失/损坏 → 目录 mtime 距今 > 60 s 才删；握手 `instance_id` 不一致 → 视为 stale 不计入；`envelope_version` 不一致 → 计入但 `state="disconnected"`、`version_warning` 说明版本不匹配、`client=None`（§4.3）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_discovery.py
import json
import os
import threading
import time

import pytest
from bridge.core.lifecycle import BridgeSession
from server.core.discovery import Discovery
from tests.unit.test_lifecycle import FakeReader


@pytest.fixture
def live(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    threading.Thread(target=lambda: _pump(s), daemon=True).start()
    yield s, tmp_path / "run"
    s.stop()


def _pump(s):
    while not s.stopped:
        time.sleep(s.tick(50))


def test_finds_live_instance(live):
    s, run = live
    d = Discovery(run)
    inst = d.instances()
    assert len(inst) == 1
    assert inst[0].state == "connected"
    assert inst[0].blender_supported is True
    assert inst[0].session["instance_id"] == s.instance_id


def test_cache_within_ttl(live):
    s, run = live
    d = Discovery(run, ttl=10.0)
    first = d.instances()
    s.stop()                                  # 会话没了……
    assert d.instances() is first             # ……但缓存内返回同一对象
    assert d.instances(force=True) == []      # force 绕过缓存


def test_dead_pid_and_connect_fail_cleans_dir(tmp_path):
    run = tmp_path / "run"
    dead = run / "gui-99-zz"
    dead.mkdir(parents=True)
    (dead / "session.json").write_text(json.dumps({
        "instance_id": "gui-99-zz", "token": "t", "pid": 2 ** 22 - 3,   # 不存在的 pid
        "socket_path": str(dead / "bridge.sock"), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    assert Discovery(run).instances() == []
    assert not dead.exists()                  # 双条件成立 → 清理（§5.1）


def test_corrupt_session_respects_grace_period(tmp_path):
    run = tmp_path / "run"
    broken = run / "gui-1-bb"
    broken.mkdir(parents=True)
    (broken / "session.json").write_text("{corrupt")
    Discovery(run).instances()
    assert broken.exists()                    # mtime 新 → 60s 宽限期内不删
    old = time.time() - 120
    os.utime(broken, (old, old))
    Discovery(run).instances()
    assert not broken.exists()


def test_version_warning_for_non_baseline(live, tmp_path):
    s, run = live
    sj = run / s.instance_id / "session.json"
    data = json.loads(sj.read_text())
    data["blender_version"] = "4.5.3"
    sj.write_text(json.dumps(data))
    inst = Discovery(run).instances()[0]
    assert inst.blender_supported is False
    assert "4.5.3" in inst.version_warning
```

- [ ] **Step 2: 跑测试确认失败** → `uv run pytest tests/unit/test_discovery.py -q`

- [ ] **Step 3: 实现**

```python
# server/core/discovery.py
"""实例发现。spec §4.3（惰性 + 1s 缓存 + 握手权威判定）、§5.1（双条件清理 + 宽限期）。"""
from __future__ import annotations

import logging
import os
import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bridge.core.session import read_session_file
from protocol import envelope
from .bridge_client import BridgeClient, BridgeError
from .versions import check

_diag = logging.getLogger("bcx.server")
GRACE_SECONDS = 60.0


@dataclass
class Instance:
    session: dict[str, Any]
    state: str
    blender_supported: bool
    version_warning: str | None
    client: BridgeClient | None


class Discovery:
    def __init__(self, run_dir: Path, ttl: float = 1.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._run = run_dir
        self._ttl = ttl
        self._clock = clock
        self._cache: list[Instance] | None = None
        self._cached_at = -1e9

    def instances(self, force: bool = False) -> list[Instance]:
        if not force and self._cache is not None \
                and self._clock() - self._cached_at < self._ttl:
            return self._cache
        self._cache = self._scan()
        self._cached_at = self._clock()
        return self._cache

    def find(self, instance_id: str) -> Instance | None:
        for inst in self.instances():
            if inst.session["instance_id"] == instance_id:
                return inst
        return None

    def _scan(self) -> list[Instance]:
        out: list[Instance] = []
        if not self._run.exists():
            return out
        candidates: list[tuple[Path, dict[str, Any]]] = []
        for d in sorted(self._run.iterdir()):
            if not d.is_dir():
                continue
            try:
                sess = read_session_file(d / "session.json")
            except ValueError:
                if time.time() - d.stat().st_mtime > GRACE_SECONDS:
                    _diag.info("cleaning corrupt session dir %s", d)
                    shutil.rmtree(d, ignore_errors=True)
                continue
            candidates.append((d, sess))
        if not candidates:
            return out
        with ThreadPoolExecutor(max_workers=8) as ex:   # 并行探测——串行会按实例数叠加
            probed = list(ex.map(                        # 2s 超时，冲破 §4.2 的 3s 预算
                lambda c: self._probe(c[1]), candidates))
        for (d, _sess), inst in zip(candidates, probed):
            if inst is None:
                _diag.info("cleaning dead session dir %s", d)
                shutil.rmtree(d, ignore_errors=True)
            elif inst.session.get("__stale__"):
                continue          # 握手身份不符：不计入也不清理（§4.3）
            else:
                out.append(inst)
        return out

    def _probe(self, sess: dict[str, Any]) -> Instance | None:
        pid_alive = True
        try:
            os.kill(int(sess.get("pid", -1)), 0)
        except (OSError, ValueError):
            pid_alive = False
        client = BridgeClient(sess)
        try:
            pong = client.call("ping")
        except BridgeError:
            if not pid_alive:
                return None       # 双条件成立 → 清理
            return self._make(sess, "disconnected", client=None)
        if pong.get("instance_id") != sess.get("instance_id"):
            return self._make({**sess, "__stale__": True}, "disconnected", client=None)
        if pong.get("envelope_version") != envelope.ENVELOPE_VERSION:
            inst = self._make(sess, "disconnected", client=None)
            inst.version_warning = (
                f"envelope v{pong.get('envelope_version')} != v{envelope.ENVELOPE_VERSION}，"
                f"Server 与 Bridge 版本不匹配")
            return inst
        return self._make(sess, "connected", client=client)

    @staticmethod
    def _make(sess: dict[str, Any], state: str, client: BridgeClient | None) -> Instance:
        supported, warning = check(str(sess.get("blender_version", "")))
        return Instance(session=sess, state=state, blender_supported=supported,
                        version_warning=warning, client=client)
```

- [ ] **Step 4: 跑测试确认通过** → 5 passed

- [ ] **Step 5: Commit**

```bash
git add server/core/discovery.py tests/unit/test_discovery.py
git commit -m "feat(server-core): 实例发现——握手权威判定、1s 缓存、双条件清理与宽限期

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: server/mcp/adapter.py（三工具 + 审计接线）

**Files:**
- Create: `server/mcp/adapter.py`
- Modify: `server/core/discovery.py`（`Instance` 增加 `envelope_mismatch: bool = False`；`_probe` 的 mismatch 分支设 `True`——adapter 需要区分「断连」与「版本不匹配」两种拒绝）
- Modify: `pyproject.toml`（加入口 `[project.scripts] blender-codex-server = "server.mcp.adapter:main"`）
- Test: `tests/unit/test_adapter.py`

**Interfaces:**
- Produces:
  - `class ToolFailure(Exception)`：属性 `code: str`；message 格式 `"{code}: {detail}"`
  - `status_impl(discovery, audit, instance_selector: str | None = None) -> dict`（§6.1 形状；并发聚合 `ThreadPoolExecutor(max_workers=8)`，整体 3 s；空/无匹配 → `ok=True` + `guidance`）
  - `scene_summary_impl(discovery, audit, instance_id: str, include_collections: bool = True, include_managed_objects: bool = True) -> dict`（§6.2 形状；补 `instance_id`/`version_warning` 两个 Server 侧字段；`INSTANCE_NOT_FOUND` / `ENVELOPE_VERSION_MISMATCH` / `BRIDGE_UNAVAILABLE` 按 §5 表抛 `ToolFailure`）
  - `capabilities_impl(discovery, audit) -> dict`（§6.3 形状）
  - `main() -> None`（`mcp.run()`，stdio）
- 形状契约由测试保证（L1 断言字段、L2 端到端断言）；FastMCP 从类型注解生成 inputSchema，outputSchema 不由 SDK 强制——记入 §7.4 验收映射的说明

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_adapter.py
import pytest
from server.core.audit import AuditLog
from server.core.discovery import Instance
from server.mcp.adapter import (GUIDANCE, ToolFailure, capabilities_impl,
                                scene_summary_impl, status_impl)


class FakeClient:
    def __init__(self, results: dict):
        self._r = results

    def call(self, method, params=None, timeout=None):
        return self._r[method]


class FakeDiscovery:
    def __init__(self, insts):
        self._i = insts

    def instances(self, force=False):
        return self._i

    def find(self, instance_id):
        return next((i for i in self._i
                     if i.session["instance_id"] == instance_id), None)


def make_inst(iid="gui-1-aa", state="connected", supported=True, warning=None,
              client=None, mismatch=False):
    return Instance(session={"instance_id": iid, "pid": 1, "blender_version": "5.2.0",
                             "bridge_version": "0.1.0"},
                    state=state, blender_supported=supported, version_warning=warning,
                    client=client, envelope_mismatch=mismatch)


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "logs")


def test_status_empty_returns_guidance(audit):
    out = status_impl(FakeDiscovery([]), audit)
    assert out == {"ok": True, "guidance": GUIDANCE, "instances": []}


def test_status_selector_no_match_is_guidance_not_error(audit):
    d = FakeDiscovery([make_inst(client=FakeClient({"status": {}}))])
    out = status_impl(d, audit, instance_selector="gui-9-zz")
    assert out["ok"] is True and out["instances"] == [] and out["guidance"] == GUIDANCE


def test_status_enriches_from_bridge(audit):
    c = FakeClient({"status": {"scene_path": "/tmp/x.blend", "scene_revision": 4}})
    out = status_impl(FakeDiscovery([make_inst(client=c)]), audit)
    row = out["instances"][0]
    assert row["bridge_state"] == "connected"
    assert row["scene_path"] == "/tmp/x.blend" and row["scene_revision"] == 4
    assert row["blender_supported"] is True and row["version_warning"] is None


def test_scene_summary_injects_server_fields(audit):
    c = FakeClient({"scene_summary": {"scene_hash": "sha256:x", "scene_name": "S",
                                      "scene_revision": 1, "scene_path": None,
                                      "units": {"system": "NONE", "scale_length": 1.0},
                                      "summary": {"object_count": 0, "mesh_count": 0,
                                                  "camera_count": 0, "light_count": 0,
                                                  "collections": ["C"],
                                                  "managed_objects": []}}})
    out = scene_summary_impl(FakeDiscovery([make_inst(client=c, supported=False,
                                                      warning="w")]), audit, "gui-1-aa")
    assert out["instance_id"] == "gui-1-aa"
    assert out["version_warning"] == "w"          # 非基线：只读放行 + 警告（§4.4）


def test_scene_summary_error_mapping(audit):
    with pytest.raises(ToolFailure) as e1:
        scene_summary_impl(FakeDiscovery([]), audit, "gui-9-zz")
    assert e1.value.code == "INSTANCE_NOT_FOUND"
    with pytest.raises(ToolFailure) as e2:
        scene_summary_impl(FakeDiscovery([make_inst(client=None, mismatch=True,
                                                    warning="envelope v2 != v1")]),
                           audit, "gui-1-aa")
    assert e2.value.code == "ENVELOPE_VERSION_MISMATCH"
    with pytest.raises(ToolFailure) as e3:
        scene_summary_impl(FakeDiscovery([make_inst(state="disconnected", client=None)]),
                           audit, "gui-1-aa")
    assert e3.value.code == "BRIDGE_UNAVAILABLE"


def test_capabilities_lists_connected(audit):
    out = capabilities_impl(FakeDiscovery([make_inst(client=FakeClient({}))]), audit)
    assert out["phase"] == "phase0"
    assert out["connected_instances"][0]["instance_id"] == "gui-1-aa"


def test_every_call_writes_audit_row(audit, tmp_path):
    status_impl(FakeDiscovery([]), audit)
    f = next((tmp_path / "logs").glob("server-*.jsonl"))
    assert "get_blender_status" in f.read_text()
```

- [ ] **Step 2: 跑测试确认失败** → `uv run pytest tests/unit/test_adapter.py -q`

- [ ] **Step 3: 改 discovery.py（两处）**

```python
# Instance 定义处：
@dataclass
class Instance:
    session: dict[str, Any]
    state: str
    blender_supported: bool
    version_warning: str | None
    client: BridgeClient | None
    envelope_mismatch: bool = False

# _probe 的 mismatch 分支改为：
        if pong.get("envelope_version") != envelope.ENVELOPE_VERSION:
            inst = self._make(sess, "disconnected", client=None)
            inst.envelope_mismatch = True
            inst.version_warning = (
                f"envelope v{pong.get('envelope_version')} != v{envelope.ENVELOPE_VERSION}，"
                f"Server 与 Bridge 版本不匹配")
            return inst
```

- [ ] **Step 4: 实现 adapter**

```python
# server/mcp/adapter.py
"""FastMCP 适配层：参数进出、审计、错误映射。业务在 core。≤300 行（URS NFR-C3）。"""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from mcp.server.fastmcp import FastMCP

from server.core import config
from server.core.audit import AuditLog
from server.core.bridge_client import BridgeError
from server.core.capabilities import describe
from server.core.discovery import Discovery, Instance

SERVER_VERSION = "0.1.0"
GUIDANCE = ("未发现可用的 Blender 实例。请在 Blender 的 3D 视口按 N 打开侧栏 → "
            "「Codex」页签 → 点击「允许 Codex 连接」，然后重试。")
INSTRUCTIONS = (  # URS FR-34 / spec §6.4：跨工具规则，关键内容前置
    "Blender 只读控制通道（Phase 0）。调用任何工具前先 get_blender_status；"
    "若无实例，引导用户在 Blender 3D 视口按 N → 「Codex」页签 → 点击「允许 Codex 连接」。"
    "本 Server 无写工具，不要尝试让 Blender 执行代码。"
    "describe_capabilities 可在 Blender 离线时回答。"
)

mcp = FastMCP("blender-codex", instructions=INSTRUCTIONS)
_deps_cache: tuple[Discovery, AuditLog] | None = None


class ToolFailure(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


def _deps() -> tuple[Discovery, AuditLog]:
    global _deps_cache
    if _deps_cache is None:                      # 惰性：不在 import 期扫描（§5.3）
        _deps_cache = (Discovery(config.run_dir()), AuditLog(config.logs_dir()))
    return _deps_cache


def _audited(audit: AuditLog, tool: str, params: dict):
    class _Ctx:
        def __enter__(self):
            self.t0 = time.monotonic()
            self.rid = str(uuid.uuid4())
            self.error: str | None = None
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc is not None:
                self.error = getattr(exc, "code", type(exc).__name__)
            audit.record(tool, self.rid, ok=exc is None,
                         duration_ms=(time.monotonic() - self.t0) * 1000,
                         instance_id=params.get("instance_id"), params=params,
                         error=self.error)
            return False
    return _Ctx()


def _row(inst: Instance) -> dict:
    s = inst.session
    return {"instance_id": s["instance_id"], "pid": s.get("pid", -1), "mode": "gui",
            "bridge_state": inst.state, "blender_version": s.get("blender_version", "?"),
            "blender_supported": inst.blender_supported,
            "version_warning": inst.version_warning,
            "scene_path": None, "scene_revision": None}


def status_impl(discovery, audit, instance_selector: str | None = None) -> dict:
    with _audited(audit, "get_blender_status",
                  {"instance_selector": instance_selector}):
        insts = list(discovery.instances())
        if instance_selector is not None:
            insts = [i for i in insts
                     if i.session["instance_id"] == instance_selector]  # 精确匹配（§4.3）
        live = [i for i in insts if i.client is not None]
        extra: dict[str, dict] = {}
        if live:
            ex = ThreadPoolExecutor(max_workers=8)      # §4.2：并发聚合，整体 3s
            try:
                futs = {ex.submit(i.client.call, "status"): i for i in live}
                try:
                    for f in as_completed(futs, timeout=3.0):
                        try:
                            extra[futs[f].session["instance_id"]] = f.result()
                        except BridgeError:
                            pass
                except TimeoutError:
                    pass
            finally:
                ex.shutdown(wait=False, cancel_futures=True)   # 超时后不为掉队 future 陪跑
        rows = []
        for inst in insts:
            row = _row(inst)
            e = extra.get(row["instance_id"])
            if e is not None:
                row["scene_path"] = e.get("scene_path")
                row["scene_revision"] = e.get("scene_revision")
            elif inst.client is not None:
                row["bridge_state"] = "disconnected"        # 单实例失败不影响其余（§4.2）
            rows.append(row)
        return {"ok": True, "guidance": GUIDANCE if not rows else None,
                "instances": rows}


def scene_summary_impl(discovery, audit, instance_id: str,
                       include_collections: bool = True,
                       include_managed_objects: bool = True) -> dict:
    with _audited(audit, "get_scene_summary", {"instance_id": instance_id}):
        inst = discovery.find(instance_id)
        if inst is None:
            raise ToolFailure("INSTANCE_NOT_FOUND", instance_id)
        if inst.envelope_mismatch:
            raise ToolFailure("ENVELOPE_VERSION_MISMATCH", inst.version_warning or "")
        if inst.client is None:
            raise ToolFailure("BRIDGE_UNAVAILABLE", "bridge disconnected")
        try:
            result = inst.client.call("scene_summary")
        except BridgeError as e:
            raise ToolFailure(e.code, str(e)) from e
        result["instance_id"] = instance_id
        result["version_warning"] = inst.version_warning    # §4.4：非基线附警告
        if not include_collections:
            result["summary"]["collections"] = []
        if not include_managed_objects:
            result["summary"]["managed_objects"] = []
        return result


def capabilities_impl(discovery, audit) -> dict:
    with _audited(audit, "describe_capabilities", {}):
        connected = [i.session for i in discovery.instances() if i.client is not None]
        return describe(SERVER_VERSION, connected)


@mcp.tool()
def get_blender_status(instance_selector: str | None = None) -> dict:
    """列出 Blender 实例、Bridge 连接状态与场景概况。无实例时返回引导文案。"""
    d, a = _deps()
    return status_impl(d, a, instance_selector)


@mcp.tool()
def get_scene_summary(instance_id: str, include_collections: bool = True,
                      include_managed_objects: bool = True) -> dict:
    """返回指定实例的场景摘要：对象统计、单位、scene_hash 与受管对象清单。"""
    d, a = _deps()
    return scene_summary_impl(d, a, instance_id, include_collections,
                              include_managed_objects)


@mcp.tool()
def describe_capabilities() -> dict:
    """返回本 Server 的能力：支持的工具、IR 版本、Blender 基线与已连实例。"""
    d, a = _deps()
    return capabilities_impl(d, a)


def main() -> None:
    mcp.run()          # stdio；日志走 stderr（NFR-O1）


if __name__ == "__main__":
    main()
```

pyproject 追加：

```toml
[project.scripts]
blender-codex-server = "server.mcp.adapter:main"
```

- [ ] **Step 5: 跑测试确认通过** → `uv run pytest tests/unit/ -q` 全绿；`wc -l server/mcp/adapter.py` ≤ 300

- [ ] **Step 6: Commit**

```bash
git add server/mcp/adapter.py server/core/discovery.py pyproject.toml tests/unit/test_adapter.py
git commit -m "feat(server-mcp): FastMCP 三工具、并发聚合、审计接线、错误映射

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: bridge/blender/（bpy 适配层）+ 根 shim

**需要 Blender**（已装 5.2.0）。本任务无 pytest——验证靠 `--background` 脚本；timer 触发行为归 Task 18 L3（SPIKE-1.1：background 下 timer 不触发，故此处手动泵 tick）。

**Files:**
- Create: `bridge/blender/__init__.py`、`bridge/blender/scene_reader.py`、`bridge/blender/driver.py`、`bridge/blender/panel.py`、`bridge/__init__.py`、`smoke/bg_check.py`

**Interfaces:**
- Consumes: `BridgeSession`、`SceneReader` 协议、`scene_hash`
- Produces:
  - `driver.start() / driver.stop() / driver.running() -> bool / driver.session() -> BridgeSession | None`
  - operators：`bcx.allow_connect`、`bcx.disconnect`；panel 页签名 `Codex`（GUIDANCE 文案与此一致）
  - 根包 `bridge/__init__.py`：bpy 存在时才暴露 `register/unregister`（否则 pytest `import bridge.core` 会因根包连锁 import bpy 而炸）

- [ ] **Step 1: 实现 scene_reader.py**

```python
# bridge/blender/scene_reader.py
"""bpy 版 SceneReader。§3.5：主选 context.scene（SPIKE-1.3 已实测可用），回退 scenes[0]。"""
from __future__ import annotations

import bpy

from ..core import scene_hash
from ..core.contracts import SceneSnapshot


class RevisionCounter:
    def __init__(self) -> None:
        self.value = 0

    def bump(self) -> None:
        self.value += 1


class BpySceneReader:
    def __init__(self, counter: RevisionCounter) -> None:
        self._counter = counter

    def blender_version(self) -> str:
        return bpy.app.version_string.split()[0]     # "5.2.0 LTS" → "5.2.0"

    def status_info(self) -> tuple[str | None, int]:
        return (bpy.data.filepath or None, self._counter.value)

    @staticmethod
    def _target_scene():
        return bpy.context.scene or bpy.data.scenes[0]

    def snapshot(self) -> SceneSnapshot:
        sc = self._target_scene()
        lines: list[str] = []
        n_mesh = n_cam = n_light = 0
        for obj in sc.objects:
            m = tuple(v for row in obj.matrix_world for v in row)
            if obj.type == "MESH":
                n_mesh += 1
                d = obj.data
                counts = (len(d.vertices), len(d.edges), len(d.polygons))
            else:
                counts = ()
                n_cam += obj.type == "CAMERA"
                n_light += obj.type == "LIGHT"
            lines.append(scene_hash.object_line(obj.name, obj.type, m, obj.type, counts))
        us = sc.unit_settings
        return SceneSnapshot(
            scene_revision=self._counter.value,
            scene_hash=scene_hash.digest(lines),
            scene_name=sc.name,
            scene_path=bpy.data.filepath or None,
            units_system=us.system or "NONE",
            units_scale_length=us.scale_length,
            object_count=len(sc.objects), mesh_count=n_mesh,
            camera_count=n_cam, light_count=n_light,
            collections=tuple(c.name for c in bpy.data.collections),
            managed_objects=(),                       # Phase 0 恒空（§3.4）
        )
```

- [ ] **Step 2: 实现 driver.py**

```python
# bridge/blender/driver.py
"""timer/handler 注册与 tick 护栏。§3.6 护栏、§8.1：timer persistent=True，handler 必须 @persistent。"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

from ..core.lifecycle import BridgeSession
from .scene_reader import BpySceneReader, RevisionCounter

_diag = logging.getLogger("bcx.bridge")
_state: dict = {"session": None, "counter": None}


def _runtime_root() -> Path:
    env = os.environ.get("BLENDERCODEX_ROOT")
    return Path(env) if env else Path.home() / "Library" / "Application Support" / "BlenderCodex"


@persistent
def _on_depsgraph(scene, depsgraph=None) -> None:   # 只自增，不算 hash（R-P0-10）
    c = _state["counter"]
    if c is not None:
        c.bump()


def _tick_guard() -> float | None:                  # §3.6：护栏不可省略
    s = _state["session"]
    if s is None or s.stopped:
        return None                                  # 会话没了 → timer 自然注销
    try:
        return s.tick(50)
    except Exception:
        _diag.exception("tick failed")
        return 0.1


def start() -> None:
    if _state["session"] is not None:
        return
    counter = RevisionCounter()
    reader = BpySceneReader(counter)
    session = BridgeSession.start(_runtime_root(), reader,
                                  blender_version=reader.blender_version())
    _state.update(session=session, counter=counter)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    bpy.app.timers.register(_tick_guard, first_interval=0.1, persistent=True)


def stop() -> None:
    session = _state["session"]
    if session is None:
        return
    if bpy.app.timers.is_registered(_tick_guard):    # §3.7 步 6（driver 层职责）
        bpy.app.timers.unregister(_tick_guard)
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:   # 步 7
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    session.stop()
    _state.update(session=None, counter=None)


def running() -> bool:
    return _state["session"] is not None


def session() -> BridgeSession | None:
    return _state["session"]
```

- [ ] **Step 3: 实现 panel.py 与两个 `__init__.py`**

```python
# bridge/blender/panel.py
"""N 面板与显式会话开关（P0-D1）。"""
from __future__ import annotations

import bpy

from . import driver


class BCX_OT_allow_connect(bpy.types.Operator):
    bl_idname = "bcx.allow_connect"
    bl_label = "允许 Codex 连接"
    bl_description = "创建会话 socket 与一次性 token，开始接受本机 Codex 连接"

    def execute(self, context):
        driver.start()
        return {"FINISHED"}


class BCX_OT_disconnect(bpy.types.Operator):
    bl_idname = "bcx.disconnect"
    bl_label = "断开"
    bl_description = "关闭会话并删除 socket 与 token"

    def execute(self, context):
        driver.stop()
        return {"FINISHED"}


class BCX_PT_panel(bpy.types.Panel):
    bl_label = "Codex"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Codex"

    def draw(self, context):
        col = self.layout.column()
        s = driver.session()
        if s is not None:
            col.label(text=f"已开启：{s.instance_id}")   # §4.1：事务期提示的前身
            col.operator(BCX_OT_disconnect.bl_idname, icon="X")
        else:
            col.operator(BCX_OT_allow_connect.bl_idname, icon="PLAY")


CLASSES = (BCX_OT_allow_connect, BCX_OT_disconnect, BCX_PT_panel)
```

```python
# bridge/blender/__init__.py
"""register/unregister 实现（根 shim 转发到这里）。"""
from __future__ import annotations

import bpy

from . import driver, panel


def register() -> None:
    for cls in panel.CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    driver.stop()                        # enable 期间开着的会话必须收干净
    for cls in reversed(panel.CLASSES):
        bpy.utils.unregister_class(cls)
```

```python
# bridge/__init__.py
"""扩展入口 shim（§3.1 约束 1）。bpy 缺席时保持可 import——pytest 依赖这一点。"""
try:
    import bpy  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    pass                                  # 仓库/测试环境：只用 bridge.core，不暴露入口
else:
    from .blender import register, unregister  # noqa: F401
```

- [ ] **Step 4: 背景模式端到端验证（手动泵 tick——SPIKE-1.1：bg 下 timer 不触发）**

```python
# smoke/bg_check.py
"""blender --background --factory-startup --python smoke/bg_check.py
退出码 0 = Bridge 启停与 ping 往返在真 bpy 下成立。"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge.blender import driver  # noqa: E402
from server.core.bridge_client import BridgeClient  # noqa: E402

driver.start()
s = driver.session()
assert s is not None and s.socket_path.exists()

result: dict = {}
t = threading.Thread(target=lambda: result.update(
    BridgeClient({"socket_path": str(s.socket_path), "token": s.token}).call("ping")))
t.start()
t0 = time.monotonic()
while t.is_alive() and time.monotonic() - t0 < 10.0:   # 限时泵：空队列 tick 微秒级返回，
    time.sleep(s.tick(50))                             # 必须 sleep 让客户端线程有机会跑
t.join(timeout=1)
assert result.get("instance_id") == s.instance_id, result
assert result.get("blender_version") == "5.2.0", result

driver.stop()
assert not s.socket_path.exists()
print("BG_CHECK_OK")
```

Run: `/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python-exit-code 1 --python smoke/bg_check.py`
（`--python-exit-code 1` 不可省：Blender 默认对脚本异常仍以 0 退出，assert 失败会被误判为通过）
Expected: 末尾输出 `BG_CHECK_OK`，退出码 0。
注意：server 侧代码在 Blender 内 import 仅限本脚本复用 `BridgeClient`（纯 stdlib），不构成 Bridge 对 server 的依赖。

- [ ] **Step 5: 确认 pytest 不被根 shim 破坏** → `uv run pytest -q` 全绿（`import bridge.core` 不再触发 bpy）

- [ ] **Step 6: Commit**

```bash
git add bridge/blender/ bridge/__init__.py smoke/bg_check.py
git commit -m "feat(bridge-blender): bpy 适配层、显式会话面板、根入口 shim、bg 验证脚本

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: 打包——vendor 脚本、manifest、CI 检查

**Files:**
- Create: `scripts/vendor_protocol.py`、`scripts/nested_import_smoke.py`、`scripts/checks.sh`、`bridge/blender_manifest.toml`

**Interfaces:**
- Produces: `bash scripts/checks.sh` = 本项目全部 CI 检查（§9 四条 + lint + 测试）；`uv run python scripts/vendor_protocol.py` 生成 `bridge/_vendor/protocol/`，`--check` 校验一致性

- [ ] **Step 1: vendor 脚本**

```python
# scripts/vendor_protocol.py
"""复制 protocol/ → bridge/_vendor/protocol/；--check 校验逐文件 sha256 一致（§9 检查 2）。"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "protocol"
DST = ROOT / "bridge" / "_vendor" / "protocol"


def _digest(d: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.glob("*.py"))}


def main() -> int:
    if "--check" in sys.argv:
        if not DST.exists():
            print("vendor missing: run scripts/vendor_protocol.py first")
            return 1
        src, dst = _digest(SRC), _digest(DST)
        if src != dst:
            print(f"vendor drift: {sorted(set(src) ^ set(dst)) or 'content differs'}")
            return 1
        print("vendor ok")
        return 0
    DST.parent.mkdir(parents=True, exist_ok=True)
    (DST.parent / "__init__.py").write_text("")
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"vendored {len(list(DST.glob('*.py')))} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 嵌套 import 冒烟（§9 检查 3——抓 L1/L2 下隐形的绝对导入）**

```python
# scripts/nested_import_smoke.py
"""把 bridge/（含 _vendor）复制进人造 bl_ext 深层包，在剥离仓库根的 sys.path 下 import。
拦截 protocol/ 或 bridge/core 里的顶层绝对导入（spec §3.1 约束 2 + _proto 垫片）。"""
from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory() as td:
    ns = Path(td) / "bl_ext" / "user_default"
    ns.mkdir(parents=True)
    (ns.parent / "__init__.py").write_text("")
    (ns / "__init__.py").write_text("")
    shutil.copytree(ROOT / "bridge", ns / "blender_codex_bridge",
                    ignore=shutil.ignore_patterns("__pycache__", "blender"))
    (ns / "blender_codex_bridge" / "__init__.py").write_text("")   # 根 shim 换成空：不测 bpy 分支
    sys.path = [td] + [p for p in sys.path if Path(p or ".").resolve() != ROOT]
    for mod in ("bl_ext.user_default.blender_codex_bridge._vendor.protocol.envelope",
                "bl_ext.user_default.blender_codex_bridge.core.lifecycle"):
        importlib.import_module(mod)
    print("nested import ok")
```

- [ ] **Step 3: manifest 与 checks.sh**

```toml
# bridge/blender_manifest.toml
schema_version = "1.0.0"
id = "blender_codex_bridge"
version = "0.1.0"
name = "Blender Codex Bridge"
tagline = "Session-gated read-only bridge for the local Codex MCP server"
maintainer = "yeminjie <jinying020755@gmail.com>"
type = "add-on"
license = ["SPDX:GPL-3.0-or-later"]
blender_version_min = "4.5.0"
platforms = ["macos-arm64"]
```

许可证说明：扩展代码 import bpy，按 Blender 扩展平台惯例标 GPL；`protocol/` 源码在 Server 侧（venv）的使用不经由扩展分发，同仓库同作者不构成冲突。此为内部项目决策记录，不再展开。

```bash
# scripts/checks.sh
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

uv run ruff check protocol bridge server tests scripts
uv run mypy
# 检查 1：core 与 protocol 禁 bpy（行首匹配，避开注释/文案）
if grep -rnE '^[[:space:]]*(import bpy|from bpy)' bridge/core protocol --include='*.py'; then
  echo "FAIL: bpy import in core/protocol"; exit 1
fi
uv run python scripts/vendor_protocol.py            # 生成
uv run python scripts/vendor_protocol.py --check    # 检查 2
uv run python scripts/nested_import_smoke.py        # 检查 3
uv run pytest -q                                    # L1 + L2
echo "ALL CHECKS PASSED"
```

（§9 检查 4——语法基线 py313——由第一行 ruff 的 `target-version` 承担。）

- [ ] **Step 4: 运行验证** → `chmod +x scripts/checks.sh && bash scripts/checks.sh` 输出 `ALL CHECKS PASSED`

- [ ] **Step 5: Commit**

```bash
git add scripts/ bridge/blender_manifest.toml
git commit -m "build: vendor 脚本、嵌套 import 冒烟、manifest 与 CI 检查集

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 15: L2 契约测试——FakeBridge 与基础往返

**Files:**
- Create: `tests/contract/__init__.py`、`tests/contract/fake_bridge.py`、`tests/contract/test_roundtrip.py`

**Interfaces:**
- Produces: `fake_bridge.FakeSceneReader`（可配 `blender_version` / `n_collections` / `raise_on_snapshot`）；`fake_bridge.live_bridge(tmp_path, **reader_kw)` contextmanager——真 `BridgeSession` + 泵线程，yield **三元组** `(session, reader, run_dir)`；`session.pause_pump()` / `session.resume_pump()` 暂停/恢复泵线程（BUSY 类测试需要塞满队列）

- [ ] **Step 1: 写 harness 与测试**

```python
# tests/contract/fake_bridge.py
"""L2 harness：真 bridge/core + Fake bpy 侧。§7.2。"""
from __future__ import annotations

import contextlib
import threading
import time

from bridge.core.contracts import SceneSnapshot
from bridge.core.lifecycle import BridgeSession


class FakeSceneReader:
    def __init__(self, blender_version: str = "5.2.0", n_collections: int = 1,
                 raise_on_snapshot: Exception | None = None) -> None:
        self._v = blender_version
        self._n = n_collections
        self._raise = raise_on_snapshot
        self.snapshot_calls = 0

    def blender_version(self) -> str:
        return self._v

    def status_info(self):
        return (None, 1)

    def snapshot(self) -> SceneSnapshot:
        self.snapshot_calls += 1
        if self._raise is not None:
            raise self._raise
        return SceneSnapshot(
            scene_revision=1, scene_hash="sha256:fake", scene_name="Scene",
            scene_path=None, units_system="METRIC", units_scale_length=1.0,
            object_count=0, mesh_count=0, camera_count=0, light_count=0,
            collections=tuple(f"C{i:06d}" for i in range(self._n)),
        )


@contextlib.contextmanager
def live_bridge(tmp_path, **reader_kw):
    reader = FakeSceneReader(**reader_kw)
    session = BridgeSession.start(tmp_path, reader,
                                  blender_version=reader.blender_version())
    stop = threading.Event()
    paused = threading.Event()

    def pump():
        while not stop.is_set() and not session.stopped:
            if paused.is_set():
                time.sleep(0.01)
                continue
            time.sleep(session.tick(50))

    session.pause_pump = paused.set          # type: ignore[attr-defined]  # 测试挂件
    session.resume_pump = paused.clear       # type: ignore[attr-defined]

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    try:
        yield session, reader, tmp_path / "run"
    finally:
        stop.set()
        session.stop()
        t.join(timeout=2)
```

```python
# tests/contract/test_roundtrip.py
"""端到端（Server core → UDS → 真 bridge/core）。工具形状按 spec §6 断言。"""
import pytest
from server.core.audit import AuditLog
from server.core.discovery import Discovery
from server.mcp.adapter import GUIDANCE, capabilities_impl, scene_summary_impl, status_impl
from tests.contract.fake_bridge import live_bridge


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "logs")


def test_status_roundtrip_shape(tmp_path, audit):
    with live_bridge(tmp_path) as (s, reader, run):
        out = status_impl(Discovery(run), audit)
        assert out["ok"] is True and out["guidance"] is None
        row = out["instances"][0]
        assert row["instance_id"] == s.instance_id
        assert row["bridge_state"] == "connected"
        assert row["mode"] == "gui"
        assert row["blender_supported"] is True
        assert row["scene_revision"] == 1


def test_no_instance_returns_guidance(tmp_path, audit):
    out = status_impl(Discovery(tmp_path / "run"), audit)
    assert out == {"ok": True, "guidance": GUIDANCE, "instances": []}


def test_scene_summary_roundtrip_shape(tmp_path, audit):
    with live_bridge(tmp_path) as (s, reader, run):
        out = scene_summary_impl(Discovery(run), audit, s.instance_id)
        assert out["instance_id"] == s.instance_id
        assert out["scene_hash"] == "sha256:fake"
        assert out["scene_name"] == "Scene"
        assert out["units"] == {"system": "METRIC", "scale_length": 1.0}
        assert out["summary"]["managed_objects"] == []
        assert out["version_warning"] is None


def test_capabilities_offline_and_connected(tmp_path, audit):
    out = capabilities_impl(Discovery(tmp_path / "run"), audit)
    assert out["connected_instances"] == []          # 离线可答（§4.2）
    with live_bridge(tmp_path) as (s, reader, run):
        out2 = capabilities_impl(Discovery(run), audit)
        assert out2["connected_instances"][0]["instance_id"] == s.instance_id


def test_non_baseline_version_warning_attached(tmp_path, audit):
    with live_bridge(tmp_path, blender_version="4.5.3") as (s, reader, run):
        out = scene_summary_impl(Discovery(run), audit, s.instance_id)
        assert out["version_warning"] is not None and "4.5.3" in out["version_warning"]
```

- [ ] **Step 2: 跑测试** → `uv run pytest tests/contract/test_roundtrip.py -q` → 5 passed

- [ ] **Step 3: Commit**

```bash
git add tests/contract/
git commit -m "test(L2): FakeBridge harness 与端到端往返、非基线警告

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 16: L2 对抗测试

**Files:**
- Create: `tests/contract/test_adversarial.py`

覆盖 §7.2 必测清单中尚未被 L1 覆盖的端到端项。

- [ ] **Step 1: 写测试**

```python
# tests/contract/test_adversarial.py
import json
import logging
import socket
import stat
import threading
import time
from pathlib import Path

import pytest
from protocol import envelope, framing
from server.core.bridge_client import BridgeClient, BridgeError
from server.core.discovery import Discovery
from tests.contract.fake_bridge import live_bridge


def _client(s) -> BridgeClient:
    return BridgeClient({"socket_path": str(s.socket_path), "token": s.token})


def test_five_mib_payload_roundtrip(tmp_path):
    # ~5 MiB collections（700k 项 × ~8B）走完整链路无截断（URS 验收）
    with live_bridge(tmp_path, n_collections=700_000) as (s, reader, run):
        r = _client(s).call("scene_summary", timeout=30.0)
        assert len(r["summary"]["collections"]) == 700_000


def test_oversize_response_degrades_to_limit_error(tmp_path):
    with live_bridge(tmp_path, n_collections=2_200_000) as (s, reader, run):  # >16MiB
        with pytest.raises(BridgeError) as ei:
            _client(s).call("scene_summary", timeout=30.0)
        assert ei.value.code == envelope.INTERNAL_LIMIT_EXCEEDED


def test_reader_exception_maps_to_scene_query_failed(tmp_path):
    with live_bridge(tmp_path, raise_on_snapshot=RuntimeError("boom")) as (s, r, run):
        with pytest.raises(BridgeError) as ei:
            _client(s).call("scene_summary")
        assert ei.value.code == envelope.SCENE_QUERY_FAILED
        assert "boom" not in str(ei.value)           # 异常文本不出境（§5）


def test_concurrent_clients_all_served(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        results, errs = [], []

        def one():
            try:
                results.append(_client(s).call("ping")["instance_id"])
            except Exception as e:                    # noqa: BLE001
                errs.append(e)

        ts = [threading.Thread(target=one) for _ in range(8)]
        [t.start() for t in ts]
        [t.join(timeout=5) for t in ts]
        assert errs == [] and results == [s.instance_id] * 8


def test_permissions_at_rest(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        assert stat.S_IMODE(s.session_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(s.socket_path.stat().st_mode) == 0o600
        assert stat.S_IMODE((s.session_dir / "session.json").stat().st_mode) == 0o600


def test_tokenless_connection_closed_silently(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        with socket.socket(socket.AF_UNIX) as c:
            c.settimeout(2.0)
            c.connect(str(s.socket_path))
            req = envelope.Request(id="x", token="", method="ping", params={})
            c.sendall(envelope.encode_request(req))
            assert c.recv(1) == b""                   # 断开、无响应帧（§5）


def test_pipeline_busy_and_reply_frames_never_interleave(tmp_path):
    # §7.2 必测：单连接流水线下 BUSY（I/O 线程入 outbox）与正常响应（tick 入 outbox）
    # 先后在途，断言每帧长度前缀完好、回复总数 = 请求数——单写者模型的直接验证
    with live_bridge(tmp_path) as (s, reader, run):
        s.pause_pump()                                # 暂停 tick → 队列必然打满
        with socket.socket(socket.AF_UNIX) as c:
            c.settimeout(15.0)
            c.connect(str(s.socket_path))
            n = 100                                   # 容量 64 → 至少 36 个 BUSY
            for _ in range(n):
                c.sendall(envelope.encode_request(
                    envelope.Request.new(s.token, "ping", {})))
            time.sleep(0.3)                           # 让 I/O 线程完成入队与 BUSY
            s.resume_pump()
            buf = framing.FrameBuffer()
            frames: list[bytes] = []
            while len(frames) < n:
                data = c.recv(65536)
                assert data, f"connection closed after {len(frames)} frames"
                frames += buf.feed(data)              # feed 抛异常 = 帧交错/损坏
        bodies = [json.loads(f) for f in frames]
        busy = [b for b in bodies
                if not b["ok"] and b["error"]["code"] == envelope.BRIDGE_BUSY]
        ok = [b for b in bodies if b["ok"]]
        assert len(busy) + len(ok) == n and busy and ok


def test_serialization_failure_becomes_scene_query_failed(tmp_path):
    # §7.2 必测（tick 护栏兜底的 L2 版）：信封序列化阶段抛异常 → 结构化错误帧，
    # tick 循环存活、后续请求照常服务
    class Unserializable:
        pass

    with live_bridge(tmp_path) as (s, reader, run):
        orig = reader.snapshot

        def bad():
            snap = orig()
            return snap.__class__(**{**snap.__dict__, "scene_name": Unserializable()})

        reader.snapshot = bad                          # type: ignore[method-assign]
        with pytest.raises(BridgeError) as ei:
            _client(s).call("scene_summary")
        assert ei.value.code == envelope.SCENE_QUERY_FAILED
        reader.snapshot = orig                         # type: ignore[method-assign]
        assert _client(s).call("ping")["instance_id"] == s.instance_id


def test_unregister_recovers_n_connections(tmp_path):
    # §7.2 必测：建立 N 条连接后 stop()，全部立即收到关闭而非超时（§3.7 第 4 步）
    with live_bridge(tmp_path) as (s, reader, run):
        conns = []
        for _ in range(5):
            c = socket.socket(socket.AF_UNIX)
            c.settimeout(3.0)
            c.connect(str(s.socket_path))
            conns.append(c)
        time.sleep(0.3)          # 等 I/O 线程 accept 完——留在 backlog 里的连接
        s.stop()                 # 会在 listener close 时收到 RST 而非干净的 b""
        for c in conns:
            assert c.recv(1) == b""
            c.close()


def test_auth_failure_logged(tmp_path, caplog):
    # URS §10.1：「无 token 连接被拒并记日志」——断言日志真的写了
    with live_bridge(tmp_path) as (s, reader, run):
        with caplog.at_level(logging.INFO, logger="bcx.bridge"):
            with socket.socket(socket.AF_UNIX) as c:
                c.settimeout(2.0)
                c.connect(str(s.socket_path))
                c.sendall(envelope.encode_request(
                    envelope.Request.new("bad", "ping", {})))
                assert c.recv(1) == b""
        assert any("auth failed" in r.message for r in caplog.records)


def test_outbox_limit_drops_non_reading_client(tmp_path, monkeypatch):
    # §7.2 必测 / §3.7 规则 4：建连、发请求、拒不读取的客户端必须被背压上限断开，
    # 且主线程 tick 不受阻。MAX_OUTBOX 调小以免真搬 32 MiB（模块全局，读取即生效）
    from bridge.core import lifecycle
    monkeypatch.setattr(lifecycle, "MAX_OUTBOX", 256 * 1024)
    with live_bridge(tmp_path, n_collections=20_000) as (s, reader, run):
        greedy = socket.socket(socket.AF_UNIX)
        greedy.connect(str(s.socket_path))
        for _ in range(32):                     # 32 × ~160 KiB 远超 256 KiB 上限
            greedy.sendall(envelope.encode_request(
                envelope.Request.new(s.token, "scene_summary", {})))
        time.sleep(2.0)                         # 期间一字节不读：响应堆在 outbox 越限
        greedy.settimeout(20.0)
        dropped = False
        deadline = time.monotonic() + 20.0
        try:
            while time.monotonic() < deadline:  # 此后才读：读到 EOF/RST 即证明被断开
                try:
                    if greedy.recv(1 << 16) == b"":
                        dropped = True
                        break
                except ConnectionResetError:
                    dropped = True
                    break
        finally:
            greedy.close()
        assert dropped, "拒不读取的客户端未被 outbox 上限断开"
        assert _client(s).call("ping")["instance_id"] == s.instance_id   # tick 未受阻


def test_envelope_mismatch_reported_not_cleaned(tmp_path):
    # 手工 mini-bridge：ping 回 envelope_version=2
    import tempfile
    run = tmp_path / "run" / "gui-1-vv"
    run.mkdir(parents=True)
    sock_path = Path(tempfile.mkdtemp(prefix="bcx-")) / "bridge.sock"  # 短路径防 sun_path 104B
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        while not buf.feed(conn.recv(65536)):
            pass
        conn.sendall(framing.encode_frame(json.dumps({
            "v": 2, "id": "x", "ok": True,
            "result": {"instance_id": "gui-1-vv", "bridge_version": "9.9",
                       "blender_version": "5.2.0", "envelope_version": 2},
        }).encode()))
        conn.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    (run / "session.json").write_text(json.dumps({
        "instance_id": "gui-1-vv", "token": "t", "pid": 1,   # pid 1 恒存活 → 不清理
        "socket_path": str(sock_path), "blender_version": "5.2.0",
        "bridge_version": "9.9", "envelope_version": 2}))
    inst = Discovery(tmp_path / "run").instances()
    srv.close()
    assert len(inst) == 1
    assert inst[0].envelope_mismatch is True
    assert inst[0].state == "disconnected"
    assert run.exists()                               # 话不投机 ≠ 死实例（§4.3）


def test_bridge_kill_then_restart_recovers(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        d = Discovery(run)
        assert d.instances()[0].state == "connected"
    # 会话已 stop（等价于 Blender 被杀后清理完成）：
    d2 = Discovery(tmp_path / "run")
    assert d2.instances() == []
    with live_bridge(tmp_path) as (s2, reader2, run2):    # 重启 → 重新发现
        assert Discovery(run2).instances()[0].session["instance_id"] == s2.instance_id
```

- [ ] **Step 2: 跑测试** → `uv run pytest tests/contract/test_adversarial.py -q` → 13 passed
（5 MiB / 16 MiB 两条较慢属正常；若超 30 s 超时，在两条测试上加 `@pytest.mark.timeout(120)`）

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_adversarial.py
git commit -m "test(L2): 大载荷、超限降级、并发、权限位、无 token 静默断开、版本不匹配

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 17: L2 子进程测试——stdout 纯净性与冷启动

**Files:**
- Create: `tests/contract/test_server_process.py`

- [ ] **Step 1: 写测试**

```python
# tests/contract/test_server_process.py
"""以真子进程跑 MCP Server：stdout 每行必须是 JSON-RPC（NFR-O1）；冷启动 < 5 s（NFR-P2）。"""
import json
import os
import subprocess
import sys
import time

import pytest

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                   "clientInfo": {"name": "l2", "version": "0"}}}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
CALL = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "describe_capabilities", "arguments": {}}}


@pytest.fixture
def proc(tmp_path):
    env = os.environ | {"BLENDERCODEX_ROOT": str(tmp_path)}
    p = subprocess.Popen(
        [sys.executable, "-c", "from server.mcp.adapter import main; main()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True, bufsize=1,
    )
    yield p
    p.kill()
    p.wait(timeout=5)


def _send(p, obj):
    p.stdin.write(json.dumps(obj) + "\n")
    p.stdin.flush()


def _read_until(p, msg_id, deadline):
    lines = []
    while time.monotonic() < deadline:
        line = p.stdout.readline()
        if not line:
            break
        lines.append(line)
        obj = json.loads(line)                       # 解析失败 = stdout 被污染 → 直接 FAIL
        assert obj.get("jsonrpc") == "2.0"
        if obj.get("id") == msg_id:
            return obj, lines
    raise AssertionError(f"no response id={msg_id}; lines={lines}")


def test_cold_start_and_stdout_purity(proc):
    t0 = time.monotonic()
    _send(proc, INIT)
    resp, _ = _read_until(proc, 1, t0 + 10)
    assert time.monotonic() - t0 < 5.0               # NFR-P2
    instructions = resp["result"].get("instructions", "")
    assert "允许 Codex 连接" in instructions          # URS FR-34 / spec §6.4
    _send(proc, INITIALIZED)
    _send(proc, CALL)
    resp2, lines = _read_until(proc, 2, time.monotonic() + 10)
    payload = json.loads(resp2["result"]["content"][0]["text"])
    assert payload["phase"] == "phase0"
    assert payload["ir_schema_version"] is None
```

- [ ] **Step 2: 跑测试** → `uv run pytest tests/contract/test_server_process.py -q` → 1 passed
（若 FastMCP 的 tools/call 返回结构含 `structuredContent`：断言改读 `resp2["result"]["structuredContent"]`——以实际 SDK 行为为准，两者取其一，测试里留注释说明）

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_server_process.py
git commit -m "test(L2): 子进程级 stdout 纯净性与冷启动预算

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 18: L3 冒烟（真 GUI Blender，半自动）

**需要 Blender GUI**，会打开窗口数十秒后自动退出。覆盖 §7.3 四项。

**Files:**
- Create: `smoke/runner.py`

- [ ] **Step 1: 写 runner**

```python
# smoke/runner.py
"""blender --factory-startup --python smoke/runner.py
L3：timer 驱动 tick / revision 递增 / 真场景字段 / 20 次会话循环无泄漏。
状态机：每步在一次 timer 回调内完成并立即返回——绝不在回调内 join/sleep 等待
需要 tick 的结果：_tick_guard 与本 runner 同为主线程 timer，回调内阻塞会自饿死（r3 审计）。
结果写 $BLENDERCODEX_SMOKE_OUT（默认 /tmp/bcx_smoke.json），末行打印 SMOKE_{OK,FAIL}。"""
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy  # noqa: E402
from bridge.blender import driver, panel  # noqa: E402
from server.core.bridge_client import BridgeClient, BridgeError  # noqa: E402

OUT = os.environ.get("BLENDERCODEX_SMOKE_OUT", "/tmp/bcx_smoke.json")
RES: dict = {"timer_tick": None, "revision_bump": None, "fields": None,
             "cycles_leak_free": None, "errors": []}
ST: dict = {"phase": "start", "box": None, "thread": None, "deadline": 0.0,
            "rev0": -1, "cycle": 0, "base_threads": 0, "run_dir": None}


def _register():
    for cls in panel.CLASSES:
        bpy.utils.register_class(cls)


def _unregister():
    driver.stop()
    for cls in reversed(panel.CLASSES):
        bpy.utils.unregister_class(cls)


def _query_async() -> None:
    """在后台线程发起 RPC；结果落在 ST['box']。响应由 GUI timer 驱动的 tick 产生。"""
    s = driver.session()
    box: dict = {}

    def call():
        try:
            box.update(BridgeClient({"socket_path": str(s.socket_path),
                                     "token": s.token}).call("scene_summary",
                                                             timeout=10.0))
        except BridgeError as e:
            box["__error__"] = str(e)

    t = threading.Thread(target=call, daemon=True)
    t.start()
    ST.update(box=box, thread=t, deadline=time.monotonic() + 12.0)


def _connect_probe() -> bool:
    """建连验证（spec §7.3 循环定义）：能 connect 即证明 listener 活着，不依赖 tick。"""
    s = driver.session()
    try:
        c = socket.socket(socket.AF_UNIX)
        c.settimeout(1.0)
        c.connect(str(s.socket_path))
        c.close()
        return True
    except OSError:
        return False


def _finish() -> None:
    Path(OUT).write_text(json.dumps(RES, ensure_ascii=False, indent=1))
    ok = all(RES[k] is True for k in
             ("timer_tick", "revision_bump", "fields", "cycles_leak_free"))
    print("SMOKE_OK" if ok else f"SMOKE_FAIL {RES}")
    bpy.ops.wm.quit_blender()


def _step() -> float | None:
    ph = ST["phase"]
    try:
        if ph == "start":
            _register()
            bpy.ops.bcx.allow_connect()
            _query_async()                       # 只有 GUI timer 在驱动 tick
            ST["phase"] = "wait1"
        elif ph in ("wait1", "wait2"):
            if ST["thread"].is_alive() and time.monotonic() < ST["deadline"]:
                return 0.1                       # 关键：让出主线程给 _tick_guard
            box = ST["box"]
            if ph == "wait1":
                RES["timer_tick"] = box.get("scene_name") is not None
                ST["rev0"] = box.get("scene_revision", -1)
                bpy.ops.mesh.primitive_cube_add()  # GUI 下触发 depsgraph handler
                _query_async()
                ST["phase"] = "wait2"
            else:
                RES["revision_bump"] = box.get("scene_revision", -1) > ST["rev0"]
                RES["fields"] = (box.get("summary", {}).get("object_count") == 4
                                 and box.get("scene_hash", "").startswith("sha256:")
                                 and box.get("units", {}).get("system")
                                 in ("METRIC", "NONE"))
                bpy.ops.bcx.disconnect()
                _unregister()
                ST["base_threads"] = threading.active_count()
                ST["phase"] = "cycle"
        elif ph == "cycle":                       # 每次回调跑一整圈会话循环
            _register()
            bpy.ops.bcx.allow_connect()
            s = driver.session()
            ST["run_dir"] = s.session_dir.parent
            assert s.socket_path.exists() and _connect_probe()
            bpy.ops.bcx.disconnect()
            _unregister()
            ST["cycle"] += 1
            if ST["cycle"] >= 20:
                ST.update(phase="settle", deadline=time.monotonic() + 1.0)
        elif ph == "settle":                      # 留 1 秒让 join 完的线程退场
            if time.monotonic() < ST["deadline"]:
                return 0.1
            leaked = threading.active_count() - ST["base_threads"]
            run_dir = ST["run_dir"]
            leftover = (list(run_dir.glob("gui-*"))
                        if run_dir and run_dir.exists() else [])
            RES["cycles_leak_free"] = leaked <= 0 and leftover == []
            if not RES["cycles_leak_free"]:
                RES["errors"].append(f"threads+{leaked}, leftover={leftover}")
            _finish()
            return None
    except Exception as e:  # noqa: BLE001
        RES["errors"].append(f"{ph}: {type(e).__name__}: {e}")
        _finish()
        return None
    return 0.05


bpy.app.timers.register(_step, first_interval=0.5)
```

- [ ] **Step 2: 运行**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup --python-exit-code 1 --python smoke/runner.py 2>&1 | tail -2
```

Expected: `SMOKE_OK`。失败时读 `/tmp/bcx_smoke.json` 定位是四项里哪一项。

- [ ] **Step 3: Commit**

```bash
git add smoke/runner.py
git commit -m "test(L3): GUI 冒烟——timer 驱动、revision 递增、真场景字段、20 次会话循环

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 19: 安装文档与验收核对

**Files:**
- Create: `docs/install.md`

- [ ] **Step 1: 写安装文档**

````markdown
# 安装与接入（Phase 0）

## 1. 前置
- macOS 14+ / Apple Silicon；Blender **5.2.0 LTS**（官方 DMG）
- [uv](https://docs.astral.sh/uv/)；本仓库 `uv sync` 完成

## 2. 安装 Bridge 扩展
```bash
uv run python scripts/vendor_protocol.py
cd bridge && zip -r ../blender_codex_bridge.zip . -x "*__pycache__*" && cd ..
```
Blender → Edit → Preferences → Get Extensions → 右上角下拉 → Install from Disk… →
选 `blender_codex_bridge.zip`。启用后在 3D 视口按 `N` → 「Codex」页签。

## 3. 注册 MCP Server 到 Codex
```bash
codex mcp add blender-codex -- uv --directory /Users/yeminjie/Documents/BlenderDesign run blender-codex-server
```
三个工具全只读，`~/.codex/config.toml` 中可保持 `default_tools_approval_mode = "auto"`。

## 4. 使用
1. Blender 里点「允许 Codex 连接」（每个会话一次，token 随会话轮换）
2. Codex 里问："我的 Blender 什么状态？" → 应看到实例列表
3. 结束后点「断开」，socket 与 token 即销毁

## 5. 排障
| 现象 | 处理 |
|---|---|
| `BRIDGE_UNAVAILABLE` / 空列表 + 引导文案 | 面板尚未点「允许连接」，或 Blender 已关 |
| `ENVELOPE_VERSION_MISMATCH` | Bridge 扩展与 Server 版本不同步：重新打包安装扩展 |
| `version_warning` 非空 | Blender 非 5.2 基线：只读可用，写功能（Phase 1）将拒绝 |
| Server 日志 | `~/Library/Application Support/BlenderCodex/logs/server-*.jsonl` |
````

- [ ] **Step 2: 对照 URS §10.1 逐条验收并记录**

| URS 验收项 | 验证方式 | 状态 |
|---|---|---|
| 三工具符合 outputSchema | Task 15/16 L2 + Task 18 L3 | ☐ |
| 非基线只读可用、写工具拒绝 | Task 9 单测（`gate_write`）+ Task 15 warning 测试 | ☐ |
| 杀 Blender → `BRIDGE_UNAVAILABLE`，重启自动重连 | Task 16 `test_bridge_kill_then_restart_recovers` + 手动杀真 Blender 复核 | ☐ |
| 会话循环 20 次无泄漏 | Task 18 L3 | ☐ |
| 5 MiB 分帧无截断 | Task 1 单测 + Task 16 端到端 | ☐ |
| 权限位 + 无 token 拒绝 | Task 16 | ☐ |
| stdout 纯净 | Task 17 | ☐ |
| 冷启动 < 5 s | Task 17 | ☐ |

全部打勾后在 spec 头部把「状态」改为 **已实现（Phase 0）**。

- [ ] **Step 3: Commit**

```bash
git add docs/install.md
git commit -m "docs: 安装接入文档与 URS 验收核对表

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 计划自审记录

1. **Spec 覆盖**：§2 运行时布局→T0/T7；§3.1 布局与 import 约束→T0/T3(_proto)/T13/T14；§3.2 线格式→T1/T2；§3.3 信封→T2；§3.4 契约→T3/T6；§3.5 hash 与场景选择→T3/T13；§3.6 队列与护栏→T4/T13(driver)；§3.7 I/O 模型与十步关闭→T7（步 6/7 委托 T13 driver，已在两处标注）；§4.1→T7/T13；§4.2→T10/T12；§4.3→T11/T12；§4.4→T9/T12；§5 错误表→T2/T4/T7/T10/T12 分摊；§5.2 审计→T9/T12；§5.3 冷启动→T12(惰性 `_deps`)/T17；§6 三 schema→T12 + L2 形状断言；§7 测试策略→T15–T18；§8 spike 结论→全局约束与 T13；§9 工具链→T0/T14；§12 顺序→任务依赖图一致。
2. **已修缺陷**：`bridge/core` 对 protocol 的顶层绝对导入在 `bl_ext.*` 命名空间下会炸——增设 `_proto.py` 垫片（T3）并将 T4/T6/T7 代码全部改走垫片，`nested_import_smoke.py`（T14）连同 `core/` 一起纳入拦截；根 shim `bridge/__init__.py` 以 bpy 探测守卫，否则 pytest 无法 import `bridge.core`（T13）。
3. **类型/签名一致性**：`SceneReader` 三方法（T3 定义 + T6 扩展 `status_info`）与 FakeReader（T6/T7/T15）、BpySceneReader（T13）一致；`Instance.envelope_mismatch` 在 T12 补入并被 T16 断言；`ok_frame/error_frame` 命名全程一致。
4. **占位符扫描**：无 TBD/TODO；两处「以实际 SDK 行为为准」（T17 structuredContent、T16 timeout 标注）是显式的运行时分支说明而非缺口。
6. **r4 确认轮修订（2026-08-06）**：背压检查从 tick 移入 I/O 线程（原实现让主线程 `_drop` → `sock.close()`，自相矛盾地违反了刚建立的「主线程从不触碰 socket」）；`outbox_bytes` 增减全程持锁（单边持锁不是互斥）；`_proto` 加 `TYPE_CHECKING` 分支（否则 mypy 把 protocol 判为 Any，strict 下 `warn_return_any` 全线报错）；Task 0 补 `bridge/__init__.py`（缺席则 mypy duplicate module）；ruff 显式 `select` + 钉 `<0.17`（默认规则集逐版本扩张）；修 test_router.py 的 `BridgeMeta` 导入源；补 outbox 上限 L2 测试。
5. **r3 对抗审计后修订（2026-08-06）**：写路径改单写者模型（T7 重写：outbox + I/O 线程独占 socket 写 + 每轮护栏 + 背压上限，发送锁废止）；mypy strict 全量兼容（泛型参数化、属性声明进 __init__、overrides 挡开 bpy 与适配层）+ 逐任务 lint/type 门禁；pyproject 补 build-system（无它则 entry point 不装）；L3 runner 状态机化（timer 回调内 join 会自饿死）；bg_check 限时泵 + --python-exit-code；T16 补 4 条 spec §7.2 必测（交错/序列化护栏/N 连接回收/认证日志）与 mini-bridge 短路径。

## 执行交接

计划完成并保存至 `docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`。两种执行方式：

**1. Subagent-Driven（推荐）** —— 每任务派发独立 subagent，任务间审查，迭代快

**2. Inline Execution** —— 本会话内按 executing-plans 批量执行，检查点审查

选哪种？
