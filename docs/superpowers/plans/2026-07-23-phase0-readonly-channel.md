# Phase 0 只读端到端链路 · 实施计划

> 修订：**r15**（2026-08-08，v8 全量对抗复审；补齐 Blender 扩展 class 注册部分失败回滚；Phase 0 未执行）

> **For agentic workers:** 推荐用 superpowers:subagent-driven-development 或 superpowers:executing-plans 按任务执行本计划；**若环境未安装 superpowers 插件，按任务序直接执行并逐 Step 核对即可——插件是加速项，不是前置依赖**（audit F-08）。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 Codex → MCP Server（stdio）→ UDS → Blender Bridge → 主线程 → 结构化返回的只读链路，交付 `get_blender_status` / `get_scene_summary` / `describe_capabilities` 三个工具，满足 URS §10.1 八条验收。

**Architecture:** 内核/适配分层（spec P0-D3）：`protocol/` 为两侧共用的线格式单一真相源（vendoring 进 Bridge）；`bridge/core/` 与 `server/core/` 零外部依赖、纯 stdlib，bpy 与 MCP SDK 各自隔离在薄适配层。Bridge 侧单 I/O 线程 select 多路复用 + 主线程 timer tick；Server 侧无状态短命进程。

**Tech Stack:** Python 3.13（Blender 5.2.0 内置 3.13.13，SPIKE-2 实测）· **`mcp>=2.0,<3`（`MCPServer`）** · uv · pytest + pytest-timeout · ruff（target py313）· mypy strict（core）

**上游文档：** spec = `docs/superpowers/specs/2026-07-23-phase0-readonly-channel-design.md`（v1.11，引用记为 §N）；URS = `Blender-Codex-需求规格说明书-v1.md`（v1.11）。本 Plan 仍是交付目标；Phase 0 未执行。

## Global Constraints

以下约束适用于**每个**任务，值从 spec 原文复制：

- Python 语法基线 **py313**；Server uv 钉 Python **3.13.x（`>=3.13,<3.14`）**；**`mcp>=2.0,<3` + `pydantic>=2,<3`**（后者由 adapter 直接使用，故显式声明而非依赖传递安装）
- `bridge/`（含 `_vendor/`）**只准 stdlib**——不得 import 任何第三方包，不得 import mcp（URS NFR-S8）
- `bridge/core/` 与 `protocol/` 内**不得出现 `import bpy`**（§3.1，CI 检查 1）
- `protocol/` 包内部**只准相对导入**（`from . import ...`）——vendored 副本运行在 `bl_ext.<repo>.<ext_id>._vendor.protocol` 深层命名空间（§3.1 约束 2）
- 帧上限 **16 MiB，读写两端同限**（§3.2）；帧格式 = 4 字节大端 uint32 长度 + UTF-8 JSON
- 权限边界从 `BLENDERCODEX_ROOT` 开始：runtime/run/logs race-safe create-or-validate 为当前 uid、非 symlink、精确 `0700`，否则 fail-closed；边界外既存祖先不改。会话叶目录 exclusive `mkdir(0700)`；session/audit 文件 `0600`；socket bind 后立即 chmod `0600`（§2.2）
- `session.json` 必须记录 socket 与父目录四个 dev/inode identity 字段；部分或全部缺失均不得 probe。Discovery 跨调用复用 scandir cursor 前必须重新 fstat 当前 run 与 cursor fd，换入、fd 关闭或 identity 不符即清空 cursor/backlog 并标记 partial
- 平台候选实现（本机预检依据见 `docs/measurements/2026-08-07-macos-platform-optimization.md`）：`quantize` 直接定长格式化并归一负零；`IDLE_INTERVAL = 0.02`；SceneReader 以有界 collection slice 物化纯 Python 后再 yield。`same_file` 仅为非安全查询辅助，Phase 1 写入红线必须使用 fd-bound、`O_NOFOLLOW` 与 identity revalidation，不能把路径查询当作 TOCTOU 防线。**`scene_hash` 保持 SHA-256**——blake2b 的加速可复现但成因未明，未纳入合同
- SceneReader 单次请求的 object/collection 各自最多 `1_000_000` 项、各自最多 64 MiB 文本；超限必须在物化前返回 `INTERNAL_LIMIT_EXCEEDED`，不得静默截断。Bridge 每实例 `scene_summary` 的 queued + active continuation 合计最多 2 个，Server adapter 的进程级准入同为 2，并由 SDK v2 middleware 包住完整 `call_next`（含结果转换与 audit postlude）；第三个 wire 请求 fail-fast 为 retryable `BRIDGE_BUSY`，不得在 async 事件循环中阻塞等待
- stdout verifier 在目标响应后仍执行有界 tail-drain，并以 quiet timeout/EOF settle 判定延迟污染；单行、累计缓冲、事件与消息均有独立上限。所有 cleanup 在每个破坏 syscall 前重验 identity；POSIX 无可移植 compare-and-unlink/rmdir，最后一次检查后的同 UID 主动换入仍是明确威胁模型边界
- 所有时间比较用 `time.monotonic()`，不用墙钟（§3.6）
- Server 的 runtime 根目录从环境变量 **`BLENDERCODEX_ROOT`** 读取，默认 `~/Library/Application Support/BlenderCodex`（§7.2）
- 基线常量：Blender **5.2.0** / `macos-arm64`（§8.3）；`ENVELOPE_VERSION = 1`
- stdio 模式下 stdout 只准 JSON-RPC，日志一律 stderr 或文件（URS NFR-O1）
- commit 署名 trailer 由**实际执行代理**按其自身环境规范追加；计划不硬编码任何代理署名（audit F-08——硬编码会造成虚假来源标记），示例 commit 块故意不含 trailer
- 本机工具路径统一使用 **`/Users/yeminjie/.local/bin/uv`**（当前非交互 PATH 不含该目录）；不得假设裸 `uv` 可解析
- 测试命令统一 `/Users/yeminjie/.local/bin/uv run --frozen pytest`；提交前该任务的全部测试必须绿
- **每个任务提交前还须 frozen 环境下 ruff 与 mypy 全绿**——类型与 lint 门禁逐任务执行，不推迟到 Task 14 首跑

## 执行前决策门（2026-08-07 审计采纳，全部关闭后才允许 Task 0）

| Gate | 内容 | 状态 |
|---|---|---|
| G0 | Git 基线 | ✅ 已关闭：仓库已初始化，基线 commit `f81ee3c`、审计 commit `578f49e` 在册 |
| G1 | 官方 Blender Lab MCP 重评（ADR-5 原触发条件 1 已满足） | ✅ 已记录：URS ADR-5 附录 D-4——维持自研作为 G1–G3 交付系统；官方完整 26 工具仅作为用户明确授权的边界外兼容通道（GPL 不复制源码） |
| G2 | MCP SDK 路线与协议证据 | ✅ **采用 SDK v2.0.0**：隔离实现精确通过当前 Codex `2025-06-18`、legacy `2025-11-25` 与 SDK 直连 `2026-07-28` 三条合同。Codex 0.147.0 默认和打开 `mcp_2026_07_28` 均实测协商 `2025-06-18`，故 feature flag 不作为 2026 wire 证据。**无存量代码，不制造迁移债务**；原 Phase 1.5 的「SDK 升级」条目撤销 |
| G3 | scene_hash 语义 | ✅ v8 隔离预检关闭：L1 字段结构 + fresh-tree 真 Blender GUI `hash_scope=true`，SceneReader 混合计数/字段与跨-yield wrapper-free 由独立 L1/background fixture 证明；仍不是 Phase 0 实施证据 |
| G4 | 总 deadline / 发现健壮性 | ✅ v8 隔离预检关闭：慢 `scandir`、FIFO、identity/cursor/run 换入、缺字段 JSON、discovery lock、失效通知并发、单一 status deadline、半行/超长/洪泛 stdout、SDK conversion admission 与 addon 注册回滚反例进入 **307-test（275 unit + 32 contract）** 门禁 |
| G5 | 官方 MCP 本机并存与完整目录 | ⚠️ 宿主 effective config 与注册目录为 **26/26**；历史非-render host 24/24 记录不等于当前稳定性证明，最新 24 项长序列在第 15 项 `get_screenshot_of_area_as_image` 出现截断 JSON（单独重试成功）。官方 deferred render 连续序列另已复现 Blender 5.2 `SIGABRT`，因此不能宣称 26 项稳定无问题。**当前回合模型工具面仍 10/26**，需重启/新任务后确认 26；官方截图/render 风险与自研 G1–G3 分开计，不得隐藏。详见 `docs/audits/evidence/2026-08-08-official-blender-mcp-v2.json` |

**计划代码块预检（不是 Plan 执行）**：r12 的 **262 passed（L1/unit 235 + L2/contract 27）** 仅是历史快照；r13 最终门禁计数以 v6 provenance 为准。真 GUI 100k shared-mesh 连续 20 次 `BridgeClient → UDS → Bridge` 查询的 worker-side nearest-rank P95 为约 **1439.21 ms**（max 约 2071.10 ms），`max_tick≈62.12 ms`，只关闭 M-4 的真 GUI Bridge-RPC/continuation 子门；该 runner 未经过 MCP stdio、SDK middleware、Discovery、Pydantic output validation 与 audit postlude，不能单独关闭端到端 NFR-P1。v6 manifest/provenance 与原始 GUI artifact 以最终 Plan SHA 单独固定；47 个 Python fences 中只有 46 个带 path 的文件块。50 ms 仍仅是 cooperative checking budget，不外推为硬墙钟保证。机械计数为 **92 个可执行 Markdown checkbox + 1 个不带 checkbox 的 G0 preflight**，全部未执行/未勾选；原报告的 raw token=93 包含文首 checkbox 语法示例，不能再称“93 个 Step”。

> **r13/v6 数字说明（历史）**：紧接上一段保留为不可改写的旧快照；当前审批只认 v8 证据，不认其 262/280 或 1439.21 ms 数字。

**v8 当前预检（不是 Plan 执行）**：最终 Plan prose/code SHA 以 provenance 为锚点；fresh-tree 门禁为 **307 passed（L1/unit 275 + L2/contract 32）**，adapter 专项 35、实质代码 373 行，ruff/mypy/vendor/nested/`uv lock --check` 全绿。100k shared-mesh 真 GUI Bridge-RPC 20-query worker P95 **1605.18 ms**（max **2560.86 ms**）、observer P95 **1655.44 ms**、`max_tick=62.50 ms`；只关闭 Bridge 子门，不代表端到端 MCP NFR-P1。机械计数仍为 **92 个可执行 checkbox + 1 个无 checkbox 的 G0 preflight，全部未执行/未勾选**。

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
    adapter.py               MCPServer 三工具 + 严格参数 middleware（Task 12；实质代码 ≤375 行；v8 隔离实现 373 行）
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
- Produces: 可运行的 `/Users/yeminjie/.local/bin/uv run --frozen pytest`（空收集退出码 **5** 属预期——pytest 对 NO_TESTS_COLLECTED 返回 5，不是 0）；hatchling 构建就位（Task 12 的 entry point 依赖它）；git 仓库

**Step 1（核对项，不计入执行复选框）：确认 Git 基线（仓库已初始化，本步只做核对）**

> G0 已关闭：`git log --oneline` 应看到 `f81ee3c`（基线）与 `578f49e`（审计）。**不要再执行 `git init`**；若 `git rev-parse --show-toplevel` 指向别处，停下询问。

```bash
cd /Users/yeminjie/Documents/BlenderDesign
git log --oneline | head -3
git rev-parse --show-toplevel
grep -q 'bridge/_vendor/' .gitignore || echo 'bridge/_vendor/' >> .gitignore
```

注意 `.gitignore` 排除 `bridge/_vendor/`——它是构建产物（Task 14 生成），不入库。

- [ ] **Step 2: 写 pyproject.toml**

```toml
[project]
name = "blender-codex"
version = "0.1.0"
requires-python = ">=3.13,<3.14"
dependencies = ["mcp>=2.0,<3", "pydantic>=2,<3"]

[dependency-groups]
dev = ["pytest>=8", "pytest-timeout>=2.3", "pytest-asyncio>=0.24", "ruff>=0.16,<0.17", "mypy>=1.10"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
timeout = 30
asyncio_mode = "auto"

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
files = ["protocol", "bridge/core", "server"]

[[tool.mypy.overrides]]
module = ["bpy", "bpy.*"]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["bridge._vendor.*", "bridge.blender.*"]
ignore_missing_imports = true
ignore_errors = true
follow_imports = "skip"

[project.scripts]
blender-codex-server = "server.mcp.adapter:main"
```

三处非默认配置的理由（r3 审计）：**`[build-system]` 缺席时 uv 按 virtual 项目处理，只装依赖不装项目自身，Task 12 的 `[project.scripts]` 入口将永远不生成**（flat 布局多顶层包也必须显式声明 `packages`）；`warn_unused_ignores = false` 让 `_proto.py` 的 `type: ignore` 在 `_vendor/` 存在与缺席两种状态下都合法（checks.sh 复跑不因此翻红）；overrides 把 bpy 与不受检的适配层挡在 strict 之外。

- [ ] **Step 3: 建空包文件并验证工具链**

```bash
mkdir -p protocol bridge/core server/core server/mcp tests/unit
touch protocol/__init__.py bridge/__init__.py bridge/core/__init__.py \
      server/__init__.py server/core/__init__.py server/mcp/__init__.py \
      tests/__init__.py tests/unit/__init__.py
/Users/yeminjie/.local/bin/uv sync --python 3.13   # 生成 uv.lock；不创建 .python-version
/Users/yeminjie/.local/bin/uv run --frozen pytest --co -q
```

**`uv.lock` 必须提交**：ADR 要求 CI 与 `checks.sh` 用 `/Users/yeminjie/.local/bin/uv sync --frozen`，锁文件缺席时 frozen 模式直接失败。

Expected: 空收集，**退出码 5（NO_TESTS_COLLECTED，属预期）**；
`/Users/yeminjie/.local/bin/uv run --frozen python -c "from importlib.metadata import version; print(version('mcp'))"` 输出 `2.0.x`。
**不要用 `import mcp; mcp.__version__`**——SDK v2 没有该属性，实测 `AttributeError`（复审 F-06）。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock .gitignore \
        protocol/__init__.py bridge/__init__.py bridge/core/__init__.py \
        server/__init__.py server/core/__init__.py server/mcp/__init__.py \
        tests/__init__.py tests/unit/__init__.py
git commit -m "chore: uv 工具链与包骨架（py3.13, mcp v2）"
```

**不要用 `git add -A`**：工作区含未跟踪的审计产物与 spikes，只暂存本任务的明确产物（复审 F-06）。

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

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_framing.py -q`
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

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_framing.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add protocol/framing.py tests/unit/test_framing.py
git commit -m "feat(protocol): 帧编解码与累帧缓冲，16MiB 双端同限"
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
  - `METHOD_TIMEOUTS: dict[str, float] = {"ping": 2.0, "status": 2.0, "scene_summary": 15.0}`（§4.2 表；`status=2.0` 是每个 Bridge 实例调用上限，Server adapter 的 status 总 deadline 仍为 3 s）
  - 错误码常量（str）：`UNKNOWN_METHOD` `BRIDGE_BUSY` `SCENE_QUERY_FAILED` `INTERNAL_LIMIT_EXCEEDED` `ENVELOPE_VERSION_MISMATCH` `INSTANCE_NOT_FOUND` `BRIDGE_UNAVAILABLE` `BRIDGE_TIMEOUT` `UNSUPPORTED_BLENDER_VERSION`
  - `@dataclass(frozen=True) Request(v: int, id: str, token: str, method: str, params: dict)`；`Request.new(token, method, params) -> Request`（uuid4）
  - `encode_request(req: Request) -> bytes`（含帧）；`decode_request(payload: bytes) -> Request`（字段/类型校验失败抛 `ValueError`）
  - `ok_frame(request_id: str, result: dict) -> bytes`；`error_frame(request_id: str, code: str, message: str, retryable: bool = False) -> bytes`——二者返回**整帧**；序列化超限时 `ok_frame` 内部降级为 `INTERNAL_LIMIT_EXCEEDED` 错误帧（§3.2 写端规则）
  - `decode_response(payload: bytes) -> dict`（原样 dict：`{"v","id","ok","result"| "error"}`）
  - 收发两端只接受标准 JSON 有限 number：拒绝 `NaN` / `Infinity` / `-Infinity` 与指数溢出为无穷的数值；编码器固定 `allow_nan=False`

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


def test_request_defaults_missing_version_and_ignores_unknown_outer_fields():
    raw = json.dumps({"id": "x", "token": "t", "method": "ping", "params": {},
                      "future_field": "ignored"}).encode()
    request = envelope.decode_request(raw)
    assert request.v == envelope.ENVELOPE_VERSION
    assert request.id == "x" and request.params == {}


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b'{"v":1,"id":"x","method":"ping","params":{}}',        # 缺 token
        b'{"v":1,"id":"x","token":"t","method":"ping","params":[]}',  # params 非 dict
        b'{"v":1,"id":1,"token":"t","method":"ping","params":{}}',    # id 非 str
        b'{"v":true,"id":"x","token":"t","method":"ping","params":{}}',  # bool ≠ int
        b'{"v":2,"id":"x","token":"t","method":"ping","params":{}}',
        b'{"v":-1,"id":"x","token":"t","method":"ping","params":{}}',
    ],
)
def test_decode_request_rejects_malformed(raw):
    with pytest.raises(ValueError):
        envelope.decode_request(raw)


@pytest.mark.parametrize("field", ["id", "token", "method"])
@pytest.mark.parametrize("value", ["\ud800", "x" * 1_025])
def test_decode_request_rejects_unencodable_or_oversized_text_fields(field, value):
    request = {"id": "x", "token": "t", "method": "ping", "params": {}, "v": 1}
    request[field] = value

    with pytest.raises(ValueError):
        envelope.decode_request(json.dumps(request).encode())


def test_decode_request_accepts_valid_unicode_scalar():
    raw = b'{"id":"\\ud83d\\ude00","token":"t","method":"ping","params":{},"v":1}'
    assert envelope.decode_request(raw).id == chr(0x1F600)


def test_decode_request_rejects_excessive_json_nesting():
    raw = (b'{"id":"x","token":"t","method":"ping","params":{"x":'
           + b"[" * 10_000 + b"0" + b"]" * 10_000 + b'},"v":1}')
    with pytest.raises(ValueError):
        envelope.decode_request(raw)


def test_decode_response_rejects_excessive_json_nesting():
    raw = (b'{"v":1,"id":"x","ok":true,"result":{"x":'
           + b"[" * 10_000 + b"0" + b"]" * 10_000 + b'}}')
    with pytest.raises(ValueError):
        envelope.decode_response(raw)


def test_decode_rejects_nonfinite_json_numbers():
    for constant in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
        request = ('{"id":"x","token":"t","method":"ping","params":{"x":'
                   + constant + '}}').encode()
        response = ('{"v":1,"id":"x","ok":true,"result":{"x":'
                    + constant + '}}').encode()
        with pytest.raises(ValueError):
            envelope.decode_request(request)
        with pytest.raises(ValueError):
            envelope.decode_response(response)


def test_encode_rejects_nonfinite_json_numbers():
    for value in (float("nan"), float("inf"), float("-inf")):
        request = envelope.Request.new(token="t", method="ping", params={"x": value})
        with pytest.raises(ValueError):
            envelope.encode_request(request)
        with pytest.raises(ValueError):
            envelope.ok_frame("id", {"x": value})


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


def test_ok_frame_steps_yields_during_large_collection_encoding():
    steps = envelope.ok_frame_steps("id-steps", {"collections": [f"C{i}" for i in range(1000)]})
    yields = 0
    while True:
        try:
            next(steps)
            yields += 1
        except StopIteration as done:
            frame = done.value
            break
    decoded = json.loads(framing.FrameBuffer().feed(frame)[0])
    assert decoded["result"]["collections"][-1] == "C999"
    assert yields > 1000


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

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_envelope.py -q`
Expected: FAIL，`No module named 'protocol.envelope'`

- [ ] **Step 3: 实现**

```python
# protocol/envelope.py
"""请求/响应信封 + 错误码 + method 超时表。spec §3.3、§4.2。只准相对导入。"""
from __future__ import annotations

import json
import logging
import math
import uuid
from collections.abc import Generator
from dataclasses import asdict, dataclass
from typing import Any, NoReturn

from . import framing

_log = logging.getLogger("bcx.protocol")

ENVELOPE_VERSION = 1
MAX_REQUEST_TEXT_BYTES = 1024

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
    return framing.encode_frame(
        json.dumps(asdict(req), ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _valid_text_field(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return len(value.encode("utf-8")) <= MAX_REQUEST_TEXT_BYTES
    except UnicodeEncodeError:
        return False


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant: {value}")


def _parse_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number")
    return result


def _load_json(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), parse_constant=_reject_constant,
                          parse_float=_parse_float)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as e:
        raise ValueError(f"bad JSON payload: {e}") from e


def decode_request(payload: bytes) -> Request:
    raw = _load_json(payload)
    if not isinstance(raw, dict):
        raise ValueError("request must be an object")
    try:
        req = Request(
            id=raw["id"], token=raw["token"], method=raw["method"],
            params=raw["params"], v=raw.get("v", ENVELOPE_VERSION),
        )
    except KeyError as e:
        raise ValueError(f"missing field {e}") from e
    if not (_valid_text_field(req.id) and _valid_text_field(req.token)
            and _valid_text_field(req.method) and isinstance(req.params, dict)
            and type(req.v) is int and req.v == ENVELOPE_VERSION):
        raise ValueError("field type mismatch")
    return req


def error_frame(request_id: str, code: str, message: str, retryable: bool = False) -> bytes:
    body = {"v": ENVELOPE_VERSION, "id": request_id, "ok": False,
            "error": {"code": code, "message": message, "retryable": retryable}}
    return framing.encode_frame(
        json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"))


def ok_frame_steps(request_id: str,
                   result: dict[str, Any]) -> Generator[None, None, bytes]:
    """Cooperatively JSON-encode a success frame, yielding between encoder pieces."""
    body = {"v": ENVELOPE_VERSION, "id": request_id, "ok": True, "result": result}
    payload = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False)
    for piece in encoder.iterencode(body):
        encoded = piece.encode("utf-8")
        if len(payload) + len(encoded) > framing.MAX_FRAME:
            _log.warning("response exceeds frame limit (request %s)", request_id)
            return error_frame(request_id, INTERNAL_LIMIT_EXCEEDED,
                               f"response exceeds {framing.MAX_FRAME} bytes")
        payload.extend(encoded)
        yield
    return framing.encode_frame(bytes(payload))


def ok_frame(request_id: str, result: dict[str, Any]) -> bytes:
    """Synchronous convenience for small ping/status responses and existing callers."""
    steps = ok_frame_steps(request_id, result)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            if not isinstance(done.value, bytes):
                raise TypeError("ok_frame_steps must return bytes")
            return done.value


def decode_response(payload: bytes) -> dict[str, Any]:
    raw = _load_json(payload)
    if not isinstance(raw, dict) or "ok" not in raw:
        raise ValueError("bad response")
    return raw
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_envelope.py -q`
Expected: 24 passed

- [ ] **Step 5: Commit**

```bash
git add protocol/envelope.py tests/unit/test_envelope.py
git commit -m "feat(protocol): 信封编解码、错误码、method 超时表、写端超限降级"
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
  - `SceneReader(Protocol)`: `blender_version() -> str`；轻量 `status_info() -> tuple[str | None, int]`；cooperative `snapshot_steps(...) -> Generator[None, None, SceneSnapshot]`
  - `SnapshotInvalidated(RuntimeError)`：文件 generation 或 revision 在 continuation 期间变化时终止旧快照
  - `SnapshotLimitExceeded(RuntimeError)`：reader 在物化完整响应前达到显式工作集 admission cap；Router 记录日志并返回 `INTERNAL_LIMIT_EXCEEDED`
  - `Clock(Protocol)`: `monotonic() -> float`
  - `scene_hash.quantize(v: float) -> str`（直接定长 `%.6f`、`-0.000000` 归一为 `0.000000`；不重复调用 `round`）
  - `scene_hash.object_line(name: str, obj_type: str, matrix16: tuple[float, ...], data_kind: str, data_counts: tuple[int, ...]) -> str`
  - `scene_hash.digest(lines: list[str]) -> str`（排序 join，返回 `"sha256:<hex>"`）
  - `_proto`：`bridge/core` 引用 protocol 的**唯一入口**（`from ._proto import envelope, framing`）。直接 `from protocol import ...` 在打包后的 `bl_ext.*` 命名空间下会 `ModuleNotFoundError`——spec §3.1 约束 2 的同类问题，作用在跨包引用上

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_scene_hash.py
from bridge.core import scene_hash


def test_quantize_normalizes_negative_zero_and_noise():
    assert scene_hash.quantize(-0.0) == scene_hash.quantize(0.0) == "0.000000"
    assert scene_hash.quantize(-0.0000004) == "0.000000"
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


def test_structure_hash_v1_covers_only_declared_fields():
    # 复审 R-04：object_line 的**签名**就是 v1 的全部覆盖面——顶点坐标、拓扑、
    # modifier、材质、可见性无处可传。这里断言产出行的字段结构，把边界钉死；
    # 「顶点移动 hash 不变」这类语义由 L3 真 Blender fixture 证明（§7.3）。
    line = scene_hash.object_line("Cube", "MESH", tuple(range(16)), "MESH", (8, 12, 6))
    fields = line.split("\t")
    assert len(fields) == 5
    assert fields[0] == "Cube" and fields[1] == "MESH" and fields[3] == "MESH"
    assert len(fields[2].split(",")) == 16          # 只有 16 个 matrix 分量
    assert fields[4] == "8,12,6"                    # 只有计数，没有坐标


def test_same_counts_different_topology_collide_by_design():
    # 同一对象在「顶点数/边数/面数不变但连接关系改变」后，v1 产出完全相同的行。
    # 这是已知盲区（模块 docstring + URS v1.2 术语表），不是缺陷。
    m = tuple(float(i) for i in range(16))
    before = scene_hash.object_line("Cube", "MESH", m, "MESH", (8, 12, 6))
    after = scene_hash.object_line("Cube", "MESH", m, "MESH", (8, 12, 6))
    assert scene_hash.digest([before]) == scene_hash.digest([after])
    # 反证：v1 对声明字段确实敏感——改 matrix 即变
    moved = scene_hash.object_line("Cube", "MESH", tuple(range(1, 17)), "MESH", (8, 12, 6))
    assert scene_hash.digest([before]) != scene_hash.digest([moved])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_scene_hash.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/contracts.py
"""core 与 bpy 世界之间的唯一边界。禁止 import bpy。spec §3.4。"""
from __future__ import annotations

from collections.abc import Generator
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
    def status_info(self) -> tuple[str | None, int]: ...
    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]: ...


class SnapshotInvalidated(RuntimeError):
    """The scene changed or reloaded while a cooperative snapshot was in progress."""


class SnapshotLimitExceeded(RuntimeError):
    """The bounded reader working-set admission limit was exceeded."""


class Clock(Protocol):
    def monotonic(self) -> float: ...
```

```python
# bridge/core/scene_hash.py
"""场景**结构摘要 v1**（§3.5）——纯函数、零 bpy，进 L1。bpy 侧只负责喂原始元组。

语义边界（audit F-01，实测确认）：本摘要覆盖对象名/类型/量化 matrix_world/数据的 RNA
类型标识与
顶边面**计数**。顶点坐标、拓扑连接、modifier 参数、材质/节点、可见性、collection 归属、
相机/灯光/场景设置**均不在覆盖面内**。会话内细粒度变更由 scene_revision（depsgraph
计数器）承担；跨会话等价性判断**禁止**以本值单独作证；Phase 1 冲突判定的
plan_scope_hash 必须对 IR 目标对象追加几何摘要（URS v1.2 术语表）。"""
from __future__ import annotations

import hashlib


def quantize(v: float) -> str:
    # 不要再调 round(v, 6)：f-string 的 .6f 本身就按 round-half-even 舍入，多这一步
    # 纯属重复计算。等价性已在固定随机/边界样本上逐一比对，输出逐字相同；绝对
    # benchmark 只代表本机预检，不是跨机器合同。
    s = f"{v:.6f}"
    return "0.000000" if s == "-0.000000" else s


def object_line(name: str, obj_type: str, matrix16: tuple[float, ...],
                data_kind: str, data_counts: tuple[int, ...]) -> str:
    m = ",".join(quantize(v) for v in matrix16)
    c = ",".join(str(n) for n in data_counts)
    return f"{name}\t{obj_type}\t{m}\t{data_kind}\t{c}"


def digest(lines: list[str]) -> str:
    joined = "\n".join(sorted(lines))
    # 算法固定为 SHA-256（冻结合同）。本机曾实测 blake2b 吞吐约 11× 于 sha256，
    # 但速度差的成因未查明（该 Python 的 sha256 确由 OpenSSL 3.5.6 支撑），
    # 属实现优化证据而非已论证的变更依据——若未来更换，必须一次性同步
    # bridge/blender/scene_reader.py 的分块增量实现、schema、URS/spec、
    # fixture 与 manifest，并重跑真 Blender。详见
    # docs/measurements/2026-08-07-macos-platform-optimization.md §3.2。
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

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_scene_hash.py -q` → 6 passed

- [ ] **Step 5: Commit**

```bash
git add bridge/core/contracts.py bridge/core/scene_hash.py bridge/core/_proto.py tests/unit/test_scene_hash.py
git commit -m "feat(bridge-core): SceneReader 契约与纯函数 scene_hash"
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
  - `TaskQueue(handler: Callable[[Request], bytes | ResponseSteps], clock: Clock, capacity: int = 64, diag: logging.Logger | None = None)`；`ResponseSteps = Generator[None, None, bytes]`
    - `submit(request: Request, reply: Callable[[bytes], None], deadline: float) -> None`（线程安全；满抛 `QueueFull`）
    - `tick(budget_ms: int = 50) -> float`（批处理；过期丢弃；reply 的任意普通 `Exception` 隔离；handler 异常回 `SCENE_QUERY_FAILED` 帧；返回 0.01 忙 / 0.02 闲）
    - `pending: int` 属性；`drain() -> int`（清空不回复，供 stop 第 8 步）
  - `MAX_SCENE_SUMMARY_TASKS = 2`：独立于总 64 槽的 scene-summary admission；queued/active continuation 合计最多 2 个，释放后可重用。这样两个最大 reader 工作集（每个有独立 admission cap）仍有明确进程级上界，而 ping/status 不被大查询饿死

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_queue.py
import logging
import threading
import time
from collections.abc import Generator

import pytest
from bridge.core.contracts import SceneSnapshot, SnapshotInvalidated
from bridge.core.queue import MAX_SCENE_SUMMARY_TASKS, QueueFull, TaskQueue
from bridge.core.router import BridgeMeta, Router
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
    assert q.tick() == 0.02         # 5 个全处理完 → 闲（IDLE_INTERVAL）
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


def test_task_at_exact_deadline_is_dropped_without_handler_call():
    calls = []
    q, clock = make(handler=lambda r: (calls.append(r), envelope.ok_frame(r.id, {}))[1])
    q.submit(req(), lambda _body: None, deadline=clock.now)

    q.tick()

    assert calls == [] and q.pending == 0


@pytest.mark.parametrize("failure", [BrokenPipeError, RuntimeError])
def test_reply_failure_swallowed_and_next_task_processed(failure):
    q, clock = make()
    def broken(_: bytes) -> None:
        raise failure()
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


def test_scene_summary_admission_bounds_64_request_flood_without_starving_quick_calls():
    q, clock = make(capacity=64)
    accepted = rejected = 0
    for _ in range(64):
        try:
            q.submit(req("scene_summary"), lambda _body: None,
                     deadline=clock.now + 2.0)
        except QueueFull:
            rejected += 1
        else:
            accepted += 1
    assert (accepted, rejected) == (MAX_SCENE_SUMMARY_TASKS,
                                    64 - MAX_SCENE_SUMMARY_TASKS)

    for index in range(64 - MAX_SCENE_SUMMARY_TASKS):
        method = "ping" if index % 2 == 0 else "status"
        q.submit(req(method), lambda _body: None, deadline=clock.now + 2.0)
    assert q.pending == 64


@pytest.mark.parametrize("release_path", ["complete", "deadline", "drain", "exception"])
def test_scene_summary_admission_releases_on_every_terminal_path(release_path):
    def fail(_request):
        raise RuntimeError("boom")

    handler = fail if release_path == "exception" else None
    q, clock = make(handler=handler)
    deadline = clock.now if release_path == "deadline" else clock.now + 2.0
    for _ in range(MAX_SCENE_SUMMARY_TASKS):
        q.submit(req("scene_summary"), lambda _body: None, deadline=deadline)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, deadline=clock.now + 2.0)

    if release_path == "drain":
        assert q.drain() == MAX_SCENE_SUMMARY_TASKS
    else:
        q.tick()
    for _ in range(MAX_SCENE_SUMMARY_TASKS):
        q.submit(req("scene_summary"), lambda _body: None, deadline=clock.now + 2.0)


def test_drain_clears_without_reply():
    q, clock = make()
    got: list[bytes] = []
    q.submit(req(), got.append, deadline=clock.now + 2.0)
    assert q.drain() == 1
    assert q.pending == 0 and got == []


class _RealClock:
    @staticmethod
    def monotonic() -> float:
        return time.monotonic()


class _SlowLargeSceneReader:
    """旧 Router 会走 snapshot() 并一次阻塞约 0.5s；新路径逐对象让出。"""

    def __init__(self, object_count: int = 200, step_s: float = 0.0025,
                 collection_count: int = 1_100_000) -> None:
        self.object_count = object_count
        self.step_s = step_s
        # ~12 MiB of real JSON collection names: old final json.dumps is itself a
        # >50 ms atomic handler even after scene traversal becomes cooperative.
        self.collections = tuple(f"C{i:07d}" for i in range(collection_count))
        self.sync_snapshot_called = False

    @staticmethod
    def blender_version() -> str:
        return "5.2.0"

    @staticmethod
    def status_info() -> tuple[None, int]:
        return (None, 0)

    def _result(self) -> SceneSnapshot:
        return SceneSnapshot(
            scene_revision=0, scene_hash="sha256:slow", scene_name="Large",
            scene_path=None, units_system="NONE", units_scale_length=1.0,
            object_count=self.object_count, mesh_count=self.object_count,
            camera_count=0, light_count=0, collections=self.collections,
        )

    def snapshot(self) -> SceneSnapshot:
        """仅用于证明旧同步实现会失败；新 Router 不得调用。"""
        self.sync_snapshot_called = True
        for _ in range(self.object_count):
            time.sleep(self.step_s)
        return self._result()

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        for _ in range(self.object_count):
            time.sleep(self.step_s)
            yield
        return self._result()


def test_scene_summary_large_scene_yields_before_tick_budget_wall_clock():
    reader = _SlowLargeSceneReader()
    router = Router(reader, BridgeMeta("gui-1-aa", 1, "0.1.0", "5.2.0"))
    q = TaskQueue(router.handle, _RealClock())
    got: list[bytes] = []
    request = req("scene_summary")
    q.submit(request, got.append, deadline=time.monotonic() + 5.0)

    tick_durations: list[float] = []
    while not got:
        started = time.monotonic()
        q.tick(budget_ms=50)
        tick_durations.append(time.monotonic() - started)

    # 50 ms 是 cooperative budget，不可抢占单个原子 step；给调度抖动与一个
    # 2.5 ms step 留余量。旧同步 snapshot 约 0.5 s，会稳定击穿此反例。
    assert len(tick_durations) > 1
    assert max(tick_durations) < 0.12
    assert reader.sync_snapshot_called is False
    assert q.pending == 0


def test_continuation_requeues_fairly_behind_quick_request():
    q, clock = make()
    replies: list[str] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        for _ in range(4):
            clock.now += 0.02
            yield
        return envelope.ok_frame(request.id, {})

    def handler(request: envelope.Request):
        return steps(request) if request.method == "scene_summary" \
            else envelope.ok_frame(request.id, {})

    q = TaskQueue(handler, clock)
    q.submit(req("scene_summary"), lambda _: replies.append("summary"), clock.now + 2.0)
    q.submit(req("ping"), lambda _: replies.append("ping"), clock.now + 2.0)
    q.tick(50)

    assert replies == ["ping"]
    assert q.pending == 1


def test_scene_summary_admission_is_not_recounted_when_continuation_requeues():
    q, clock = make()

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 0.06
        yield
        clock.now += 0.06
        return envelope.ok_frame(request.id, {})

    q = TaskQueue(lambda request: steps(request), clock)
    for _ in range(MAX_SCENE_SUMMARY_TASKS):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)
    q.tick(50)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)

    q.tick(50)  # start the second continuation; requeue must not consume another slot
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)

    # The next tick completes one old continuation; exactly one slot reopens.
    q.tick(50)
    q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)
    with pytest.raises(QueueFull):
        q.submit(req("scene_summary"), lambda _body: None, clock.now + 2.0)


def test_drain_closes_started_continuation():
    q, clock = make()
    closed: list[bool] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        try:
            clock.now += 0.02
            yield
            return envelope.ok_frame(request.id, {})
        finally:
            closed.append(True)

    q = TaskQueue(lambda request: steps(request), clock)
    q.submit(req("scene_summary"), lambda _: None, clock.now + 2.0)
    q.tick(10)
    assert q.drain() == 1
    assert closed == [True]


def test_active_continuation_keeps_capacity_slot_during_concurrent_submit():
    clock = FakeClock()
    entered = threading.Event()
    release = threading.Event()

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        entered.set()
        assert release.wait(2.0)
        clock.now += 0.1
        yield
        return envelope.ok_frame(request.id, {})

    q = TaskQueue(lambda request: steps(request), clock, capacity=1)
    q.submit(req("scene_summary"), lambda _: None, clock.now + 2.0)
    worker = threading.Thread(target=lambda: q.tick(50), daemon=True)
    worker.start()
    assert entered.wait(1.0)
    with pytest.raises(QueueFull):
        q.submit(req("ping"), lambda _: None, clock.now + 2.0)
    release.set()
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert q.pending == 1


def test_continuation_exception_after_yield_is_structured_error():
    import json
    from protocol import framing

    q, clock = make()
    got: list[bytes] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 0.06
        yield
        raise SnapshotInvalidated("reloaded")

    q = TaskQueue(lambda request: steps(request), clock)
    q.submit(req("scene_summary"), got.append, clock.now + 2.0)
    q.tick(50)
    assert got == [] and q.pending == 1
    q.tick(50)

    body = json.loads(framing.FrameBuffer().feed(got[0])[0])
    assert body["error"]["code"] == envelope.SCENE_QUERY_FAILED
    assert body["error"]["message"] == "SnapshotInvalidated"


def test_completed_continuation_past_deadline_is_dropped():
    q, clock = make()
    got: list[bytes] = []

    def steps(request: envelope.Request) -> Generator[None, None, bytes]:
        clock.now += 3.0
        return envelope.ok_frame(request.id, {})
        yield  # keep this a generator for the continuation contract

    q = TaskQueue(lambda request: steps(request), clock)
    q.submit(req("scene_summary"), got.append, clock.now + 1.0)
    q.tick(50)
    assert got == [] and q.pending == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_queue.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/queue.py
"""主线程任务队列：deadline、cooperative continuation、reply 失败隔离。

budget 在 handler/continuation step 之间检查；Python 无法抢占正在执行的单个 step。
因此可能超预算的主线程工作必须拆成 ResponseSteps，且每个 step 自身应当很小。
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable, Generator
from dataclasses import dataclass

from ._proto import envelope
from .contracts import Clock

# 往返延迟几乎全部是「等下一次 tick」，不是代码效率问题。本机预检（Apple M4）：
# IDLE=0.1 时 p50 约 60 ms，IDLE=0.02 时 p50 约 12 ms；代价是空转唤醒约增 4.4×。
# CPU/电量影响依 workload 与电源状态而变，不能从一次空队列样本外推电池结论。
# 更省电的迟滞方案已否决——见 docs/measurements/2026-08-07-macos-platform-optimization.md §3.1。
IDLE_INTERVAL = 0.02
BUSY_INTERVAL = 0.01
MAX_SCENE_SUMMARY_TASKS = 2
ResponseSteps = Generator[None, None, bytes]


class QueueFull(Exception):
    pass


@dataclass(frozen=True)
class _Task:
    request: envelope.Request
    reply: Callable[[bytes], None]
    deadline: float
    continuation: ResponseSteps | None = None


class TaskQueue:
    def __init__(self, handler: Callable[[envelope.Request], bytes | ResponseSteps], clock: Clock,
                 capacity: int = 64, diag: logging.Logger | None = None) -> None:
        self._handler = handler
        self._clock = clock
        self._capacity = capacity
        self._diag = diag or logging.getLogger("bcx.bridge")
        self._lock = threading.Lock()
        self._tasks: deque[_Task] = deque()
        self._active = 0
        self._scene_summaries = 0

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._tasks) + self._active

    def submit(self, request: envelope.Request, reply: Callable[[bytes], None],
               deadline: float) -> None:
        with self._lock:
            if len(self._tasks) + self._active >= self._capacity:
                raise QueueFull(request.id)
            if (request.method == "scene_summary"
                    and self._scene_summaries >= MAX_SCENE_SUMMARY_TASKS):
                raise QueueFull(request.id)
            self._tasks.append(_Task(request, reply, deadline))
            if request.method == "scene_summary":
                self._scene_summaries += 1

    def drain(self) -> int:
        with self._lock:
            tasks = list(self._tasks)
            self._tasks.clear()
            self._scene_summaries -= sum(
                task.request.method == "scene_summary" for task in tasks)
        for task in tasks:
            if task.continuation is not None:
                self._close_continuation(task.request.id, task.continuation)
        return len(tasks)

    def _close_continuation(self, request_id: str, continuation: ResponseSteps) -> None:
        try:
            continuation.close()
        except Exception:
            self._diag.exception("continuation close failed for %s", request_id)

    def _complete_active(self, task: _Task) -> None:
        with self._lock:
            self._active -= 1
            if task.request.method == "scene_summary":
                self._scene_summaries -= 1

    def tick(self, budget_ms: int = 50) -> float:
        end = self._clock.monotonic() + budget_ms / 1000.0
        while self._clock.monotonic() < end:
            with self._lock:
                if not self._tasks:
                    return IDLE_INTERVAL
                task = self._tasks.popleft()
                self._active += 1
            if self._clock.monotonic() >= task.deadline:
                self._diag.info("drop expired request %s", task.request.id)
                if task.continuation is not None:
                    self._close_continuation(task.request.id, task.continuation)
                self._complete_active(task)
                continue
            continuation = task.continuation
            try:
                result: bytes | ResponseSteps = (
                    self._handler(task.request) if continuation is None else continuation
                )
                if isinstance(result, bytes):
                    frame = result
                else:
                    continuation = result
                    try:
                        next(continuation)
                    except StopIteration as done:
                        if not isinstance(done.value, bytes):
                            raise TypeError("continuation must return bytes")
                        frame = done.value
                    else:
                        # Cooperative work returns to the tail so ping/status and other
                        # summaries remain fair while a large scene spans multiple ticks.
                        with self._lock:
                            self._tasks.append(_Task(task.request, task.reply, task.deadline,
                                                     continuation))
                            self._active -= 1
                        continue
            except Exception as e:  # handler 层兜底：异常类型可回，文本不回（§5）
                self._diag.exception("handler failed for %s", task.request.id)
                if continuation is not None:
                    self._close_continuation(task.request.id, continuation)
                frame = envelope.error_frame(task.request.id, envelope.SCENE_QUERY_FAILED,
                                             type(e).__name__)
            if self._clock.monotonic() >= task.deadline:
                self._diag.info("drop late response %s", task.request.id)
                self._complete_active(task)
                continue
            try:
                task.reply(frame)
            except Exception:
                self._diag.info("reply failed for %s (peer gone)", task.request.id)
            finally:
                self._complete_active(task)
        return BUSY_INTERVAL if self.pending else IDLE_INTERVAL
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_queue.py -q` → 21 passed（v7；旧 15 为历史）

- [ ] **Step 5: Commit**

```bash
git add bridge/core/queue.py tests/unit/test_queue.py
git commit -m "feat(bridge-core): 任务队列——deadline 丢弃、预算批处理、reply 失败隔离"
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
import os
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
    assert auth.verify(chr(0xD800)) is False


def test_write_session_file_is_0600_and_atomic(tmp_path):
    p = tmp_path / "session.json"
    write_session_file(p, {"a": 1})
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert json.loads(p.read_text()) == {"a": 1}
    write_session_file(p, {"a": 2})          # 覆盖已存在文件也必须成功（os.replace）
    assert read_session_file(p) == {"a": 2}
    assert list(tmp_path.iterdir()) == [p]   # 无临时文件残留


def test_write_session_file_dir_fd_ignores_restrictive_umask(tmp_path):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    previous_umask = os.umask(0o777)
    try:
        write_session_file(tmp_path / "session.json", {"a": 1}, dir_fd=directory_fd)
    finally:
        os.umask(previous_umask)
        os.close(directory_fd)
    path = tmp_path / "session.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {"a": 1}


def test_replace_failure_removes_temporary_file(tmp_path, monkeypatch):
    import bridge.core.session as session_module

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(session_module.os, "replace", fail_replace)
    path = tmp_path / "session.json"
    with pytest.raises(OSError, match="replace failed"):
        write_session_file(path, {"a": 1})
    assert list(tmp_path.iterdir()) == []


def test_fchmod_failure_closes_file_descriptor(tmp_path, monkeypatch):
    import bridge.core.session as session_module

    def fail_fchmod(_fd, _mode):
        raise OSError("fchmod failed")

    monkeypatch.setattr(session_module.os, "fchmod", fail_fchmod)
    path = tmp_path / "session.json"
    baseline = len(os.listdir("/dev/fd"))

    for _ in range(40):
        with pytest.raises(OSError, match="fchmod failed"):
            write_session_file(path, {"a": 1})

    assert len(os.listdir("/dev/fd")) == baseline
    assert list(tmp_path.iterdir()) == []


def test_preexisting_temporary_file_is_preserved(tmp_path):
    path = tmp_path / "session.json"
    temporary = tmp_path / "session.json.tmp"
    temporary.write_text("foreign")
    with pytest.raises(FileExistsError):
        write_session_file(path, {"a": 1})
    assert temporary.read_text() == "foreign"
    assert not path.exists()


def test_read_session_file_rejects_corrupt(tmp_path):
    p = tmp_path / "session.json"
    p.write_text("{not json")
    with pytest.raises(ValueError):
        read_session_file(p)
    p.write_text("[1,2]")
    with pytest.raises(ValueError):
        read_session_file(p)


def test_read_session_file_rejects_excessive_json_nesting(tmp_path):
    path = tmp_path / "session.json"
    path.write_text('{"x":' + "[" * 10_000 + "0" + "]" * 10_000 + "}")
    with pytest.raises(ValueError):
        read_session_file(path)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_session.py -q` → FAIL（模块不存在）

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
        try:
            return secrets.compare_digest(self._token.encode(), presented.encode())
        except UnicodeEncodeError:
            return False


def write_session_file(path: Path, data: dict[str, Any], *, dir_fd: int | None = None) -> None:
    tmp = path.with_name(path.name + ".tmp")
    if dir_fd is None:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    else:
        fd = os.open(tmp.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                     dir_fd=dir_fd)
    owns_fd = True
    try:
        os.fchmod(fd, 0o600)  # mkdir/open modes are still filtered by the process umask
        stream = os.fdopen(fd, "w", encoding="utf-8")
        owns_fd = False
        with stream as f:
            json.dump(data, f, ensure_ascii=False)
        if dir_fd is None:
            os.replace(tmp, path)
        else:
            os.replace(tmp.name, path.name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    except BaseException:
        try:
            if dir_fd is None:
                tmp.unlink(missing_ok=True)
            else:
                os.unlink(tmp.name, dir_fd=dir_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        if owns_fd:
            os.close(fd)


def read_session_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, RecursionError) as e:
        raise ValueError(f"bad session file: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError("session file must be an object")
    return raw
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_session.py -q` → 9 passed

- [ ] **Step 5: Commit**

```bash
git add bridge/core/session.py tests/unit/test_session.py
git commit -m "feat(bridge-core): 会话 token 与 session.json 原子读写"
```

---

### Task 6: bridge/core/router.py（+ contracts 核对）

**Files:**
- Create: `bridge/core/router.py`
- Verify: `bridge/core/contracts.py`（Task 3 已定义轻量 `status_info` 与 cooperative `snapshot_steps`；本任务核对 Router 严格消费该契约）
- Test: `tests/unit/test_router.py`

**Interfaces:**
- Consumes: `envelope.Request` / `ok_frame` / `error_frame`；`SceneReader`
- Produces:
  - `contracts.SceneReader.status_info() -> tuple[str | None, int]`（`(scene_path, scene_revision)`，轻量、不算 hash）
  - `@dataclass(frozen=True) BridgeMeta(instance_id: str, pid: int, bridge_version: str, blender_version: str)`
  - `class Router`: `Router(reader: SceneReader, meta: BridgeMeta)`；`handle(req: Request) -> bytes | ResponseSteps`。method 语义：
    - `ping` → `{"instance_id", "bridge_version", "blender_version", "envelope_version"}`（§3.3 握手响应）
    - `status` → `{"instance_id", "pid", "mode": "gui", "blender_version", "scene_path", "scene_revision"}`（`bridge_state`/`blender_supported`/`version_warning` 是 **Server 侧**字段，Bridge 不产）
    - `scene_summary` → 校验两个 include flags，cooperative 推进 `snapshot_steps()` 与 `ok_frame_steps()`，再按 §6.2 outputSchema 展开（见实现）
    - 其他 → `UNKNOWN_METHOD` 错误帧

- [ ] **Step 1: 核对 contracts.py 的 `SceneReader` 最终协议**

```python
class SceneReader(Protocol):
    def blender_version(self) -> str: ...
    def status_info(self) -> tuple[str | None, int]: ...
    def snapshot_steps(
        self, *, include_collections: bool = True,
        include_managed_objects: bool = True,
    ) -> Generator[None, None, SceneSnapshot]: ...
```

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/test_router.py
import json
import logging
from collections.abc import Generator

from bridge.core.contracts import SceneSnapshot, SnapshotLimitExceeded
from bridge.core.router import BridgeMeta, Router
from protocol import envelope, framing


class FakeReader:
    def blender_version(self) -> str:
        return "5.2.0"

    def status_info(self):
        return ("/tmp/a.blend", 7)

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        if False:
            yield
        return SceneSnapshot(
            scene_revision=7, scene_hash="sha256:abc", scene_name="Scene",
            scene_path="/tmp/a.blend", units_system="METRIC", units_scale_length=1.0,
            object_count=3, mesh_count=1, camera_count=1, light_count=1,
            collections=(("Collection",) if include_collections else ()),
        )


META = BridgeMeta(instance_id="gui-1-aa", pid=1, bridge_version="0.1.0",
                  blender_version="5.2.0")


def call(method: str, params: dict | None = None, reader: FakeReader | None = None) -> dict:
    router = Router(reader or FakeReader(), META)
    result = router.handle(envelope.Request.new("t", method, params or {}))
    if isinstance(result, bytes):
        frame = result
    else:
        while True:
            try:
                next(result)
            except StopIteration as done:
                frame = done.value
                break
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


def test_scene_summary_flags_reach_reader_and_crop_at_source():
    class RecordingReader(FakeReader):
        seen: tuple[bool, bool] | None = None

        def snapshot_steps(self, *, include_collections: bool = True,
                           include_managed_objects: bool = True
                           ) -> Generator[None, None, SceneSnapshot]:
            self.seen = (include_collections, include_managed_objects)
            return (yield from super().snapshot_steps(
                include_collections=include_collections,
                include_managed_objects=include_managed_objects,
            ))

    reader = RecordingReader()
    result = call("scene_summary", {"include_collections": False,
                                    "include_managed_objects": False}, reader)
    assert reader.seen == (False, False)
    assert result["result"]["summary"]["collections"] == []
    assert result["result"]["summary"]["managed_objects"] == []


def test_scene_summary_resource_limit_is_structured(caplog):
    class LimitedReader(FakeReader):
        def snapshot_steps(self, *, include_collections: bool = True,
                           include_managed_objects: bool = True
                           ) -> Generator[None, None, SceneSnapshot]:
            if False:
                yield
            raise SnapshotLimitExceeded("test limit")

    with caplog.at_level(logging.WARNING, logger="bcx.bridge"):
        result = call("scene_summary", reader=LimitedReader())
    assert result["ok"] is False
    assert result["error"]["code"] == envelope.INTERNAL_LIMIT_EXCEEDED
    assert any("resource limit exceeded" in record.message for record in caplog.records)


def test_unknown_method():
    body = call("nope")
    assert body["ok"] is False
    assert body["error"]["code"] == envelope.UNKNOWN_METHOD
```

- [ ] **Step 3: 跑测试确认失败**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_router.py -q` → FAIL

- [ ] **Step 4: 实现**

```python
# bridge/core/router.py
"""method → 响应帧。认证已由 I/O 层完成，本层假设请求可信格式已校验。"""
from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import dataclass

from ._proto import envelope
from .contracts import SceneReader, SnapshotLimitExceeded

_diag = logging.getLogger("bcx.bridge")


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

    def handle(self, req: envelope.Request) -> bytes | Generator[None, None, bytes]:
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
            include_collections = req.params.get("include_collections", True)
            include_managed = req.params.get("include_managed_objects", True)
            if not isinstance(include_collections, bool) or not isinstance(include_managed, bool):
                return envelope.error_frame(req.id, envelope.SCENE_QUERY_FAILED,
                                            "invalid scene_summary parameters")
            return self._scene_summary(req.id, include_collections, include_managed)
        return envelope.error_frame(req.id, envelope.UNKNOWN_METHOD, req.method)

    def _scene_summary(self, request_id: str, include_collections: bool,
                       include_managed_objects: bool) -> Generator[None, None, bytes]:
        try:
            snapshot = yield from self._reader.snapshot_steps(
                include_collections=include_collections,
                include_managed_objects=include_managed_objects,
            )
        except SnapshotLimitExceeded:
            _diag.warning("scene snapshot resource limit exceeded (request %s)", request_id)
            return envelope.error_frame(
                request_id, envelope.INTERNAL_LIMIT_EXCEEDED,
                "scene snapshot exceeds resource limit",
            )
        return (yield from envelope.ok_frame_steps(request_id, {
            "scene_revision": snapshot.scene_revision, "scene_hash": snapshot.scene_hash,
            "scene_name": snapshot.scene_name, "scene_path": snapshot.scene_path,
            "units": {"system": snapshot.units_system,
                      "scale_length": snapshot.units_scale_length},
            "summary": {
                "object_count": snapshot.object_count, "mesh_count": snapshot.mesh_count,
                "camera_count": snapshot.camera_count, "light_count": snapshot.light_count,
                # JSONEncoder serializes tuples as arrays; avoid a second O(N) copy here.
                "collections": (snapshot.collections if include_collections else []),
                "managed_objects": ([
                    {"stable_id": item.stable_id, "name": item.name, "type": item.type}
                    for item in snapshot.managed_objects
                ] if include_managed_objects else []),
            },
        }))
```

注意 `scene_summary` 结果不含 `instance_id`/`version_warning`——那两个字段由 Server 侧 adapter 补（§6.2 outputSchema 是**工具**的形状，不是 Bridge method 的形状）。

- [ ] **Step 5: 跑测试确认通过**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/ -q` → 全绿（含此前任务）

- [ ] **Step 6: Commit**

```bash
git add bridge/core/router.py tests/unit/test_router.py
git commit -m "feat(bridge-core): method 路由与 cooperative scene summary"
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
  - 资源上限：64 个连接、全局入站待收 32 MiB、单请求 64 KiB、单连接 outbox 32 MiB、全局 outbox 64 MiB
  - `class BridgeSession`:
    - `BridgeSession.start(runtime_root: Path, reader: SceneReader, blender_version: str, clock: Clock | None = None) -> BridgeSession`
    - `.tick(budget_ms: int = 50) -> float`（主线程调；转发 `TaskQueue.tick`）
    - `.stop(unregister_timer: Callable[[], None] | None = None, unregister_handlers: Callable[[], None] | None = None) -> bool`（幂等；仅 transport 与清理全部完成时返回 `True`；真实 driver hooks 位于 §3.7 第 6/7 步）
    - `.instance_id: str`、`.session_dir: Path`、`.socket_path: Path`、`.token: str`（测试用只读属性）
  - `send(conn, frame)`——**唯一发送入口**：任意线程可调，只入 outbox + 唤醒；socket 写只发生在 I/O 线程（§3.7 规则 3 单写者）
  - 内部 `_ensure_private_dir(path)`（应用目录 race-safe create-or-validate）与 `_resolve_socket_path`（≤100 字节校验，超限固定回退 `/tmp/bcx-<sha256(instance_id)[:16]>`，使两进程环境不同及 session 发布前崩溃仍可恢复）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_lifecycle.py
import json
import logging
import os
import socket
import stat
import tempfile
import threading
import time
from collections import deque
from collections.abc import Generator
from pathlib import Path

import pytest
from bridge.core.contracts import SceneSnapshot
from bridge.core.lifecycle import MAX_CONNECTIONS, BridgeSession
from protocol import envelope, framing


class FakeReader:
    def blender_version(self) -> str:
        return "5.2.0"

    def status_info(self):
        return (None, 0)

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        if False:
            yield
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
    assert type(sj["socket_external"]) is bool
    assert all(type(sj[key]) is int for key in (
        "socket_dev", "socket_ino", "socket_dir_dev", "socket_dir_ino"))


def test_start_ignores_restrictive_umask(tmp_path):
    root = tmp_path / "runtime"
    previous_umask = os.umask(0o777)
    try:
        session = BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    finally:
        os.umask(previous_umask)
    try:
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE((root / "run").stat().st_mode) == 0o700
        assert stat.S_IMODE(session.session_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE((session.session_dir / "session.json").stat().st_mode) == 0o600
        assert stat.S_IMODE(session.socket_path.stat().st_mode) == 0o600
    finally:
        session.stop()


def test_concurrent_start_waits_for_restrictive_umask_chmod(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "runtime"
    chmod_entered = threading.Event()
    release_chmod = threading.Event()
    sessions = []
    errors = []
    real_chmod = lifecycle.os.chmod

    def delayed_root_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if Path(path) == root and dir_fd is None and not chmod_entered.is_set():
            chmod_entered.set()
            assert release_chmod.wait(1.0)
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    monkeypatch.setattr(lifecycle.os, "chmod", delayed_root_chmod)

    def start() -> None:
        try:
            sessions.append(BridgeSession.start(
                root, FakeReader(), blender_version="5.2.0"))
        except BaseException as exc:
            errors.append(exc)

    previous_umask = os.umask(0o777)
    try:
        worker_a = threading.Thread(target=start)
        worker_a.start()
        assert chmod_entered.wait(1.0)
        worker_b = threading.Thread(target=start)
        worker_b.start()
        time.sleep(0.02)
        release_chmod.set()
        worker_a.join(timeout=3.0)
        worker_b.join(timeout=3.0)
    finally:
        release_chmod.set()
        os.umask(previous_umask)
        for started in sessions:
            started.stop()
    assert not worker_a.is_alive() and not worker_b.is_alive()
    assert errors == [] and len(sessions) == 2


def test_start_rejects_wide_runtime_root_without_chmod(tmp_path):
    root = tmp_path / "wide-runtime"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(PermissionError, match="private directory"):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    assert stat.S_IMODE(root.stat().st_mode) == 0o755


def test_start_rejects_symlink_runtime_root(tmp_path):
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    root = tmp_path / "runtime-link"
    root.symlink_to(target, target_is_directory=True)
    with pytest.raises(PermissionError, match="private directory"):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    assert root.is_symlink() and target.exists()


def test_start_rejects_preexisting_session_leaf(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "runtime"
    run = root / "run"
    run.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    run.chmod(0o700)
    monkeypatch.setattr(lifecycle.secrets, "token_hex", lambda _n: "deadbeef")
    leaf = run / f"gui-{lifecycle.os.getpid()}-deadbeef"
    leaf.mkdir(mode=0o755)
    leaf.chmod(0o755)
    with pytest.raises(FileExistsError):
        BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    assert leaf.exists() and stat.S_IMODE(leaf.stat().st_mode) == 0o755


def test_start_never_creates_session_through_replaced_run_path(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lifecycle

    root = tmp_path / "runtime"
    run = root / "run"
    run.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    run.chmod(0o700)
    original_run = root / "run-original"
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    real_mkdir = lifecycle.os.mkdir
    swapped = False

    def swap_before_leaf(path, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and isinstance(path, str) and path.startswith("gui-"):
            run.rename(original_run)
            run.symlink_to(outside, target_is_directory=True)
            swapped = True
        return real_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(lifecycle.os, "mkdir", swap_before_leaf)
    try:
        with pytest.raises(OSError, match="session directory changed"):
            BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
        assert swapped
        assert list(outside.iterdir()) == []
    finally:
        if run.is_symlink():
            run.unlink()
        if original_run.exists():
            for child in original_run.iterdir():
                child.rmdir()
            original_run.rmdir()


def test_ping_roundtrip(session):
    body = _rpc(session, "ping")
    assert body["ok"] is True
    assert body["result"]["instance_id"] == session.instance_id


def test_wrong_token_closed_without_response(session):
    assert _rpc(session, "ping", token="bad") == {"__closed__": True}


@pytest.mark.parametrize("first_kind", ["malformed", "bad-token"])
def test_rejected_frame_discards_same_recv_pipeline_tail(tmp_path, first_kind):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    valid = envelope.encode_request(envelope.Request.new(s.token, "ping", {}))
    first = (framing.encode_frame(b"{not-json") if first_kind == "malformed" else
             envelope.encode_request(envelope.Request.new("bad", "ping", {})))
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2.0)
            client.connect(str(s.socket_path))
            client.sendall(first + valid)
            assert client.recv(1) == b""
        assert s._queue is not None and s._queue.pending == 0
    finally:
        s.stop()


def test_half_header_does_not_wedge_other_connections(session):
    slow = socket.socket(socket.AF_UNIX)
    slow.connect(str(session.socket_path))
    slow.sendall(b"\x00\x00")            # 半个长度头，然后沉默
    try:
        assert _rpc(session, "ping")["ok"] is True   # 其余连接照常服务（§3.7 规则 1）
    finally:
        slow.close()


def test_partial_frame_connection_flood_is_capped_and_recovers(session):
    clients = []

    def connection_count():
        with session._conns_lock:
            return len(session._conns)

    def connect_client():
        deadline = time.monotonic() + 2.0
        while True:
            client = socket.socket(socket.AF_UNIX)
            client.settimeout(2.0)
            try:
                client.connect(str(session.socket_path))
                return client
            except ConnectionRefusedError:
                client.close()
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.005)

    try:
        for _ in range(MAX_CONNECTIONS):
            client = connect_client()
            client.sendall(b"\x01\x00\x00\x00" + b"x" * 1024)
            clients.append(client)

        deadline = time.monotonic() + 2.0
        while connection_count() < MAX_CONNECTIONS and time.monotonic() < deadline:
            time.sleep(0.005)
        assert connection_count() == MAX_CONNECTIONS

        overflow = connect_client()
        try:
            overflow.sendall(envelope.encode_request(
                envelope.Request.new(session.token, "ping", {})))
        except BrokenPipeError:
            pass
        assert overflow.recv(1) == b""
        overflow.close()
        assert connection_count() == MAX_CONNECTIONS

        clients.pop().close()
        deadline = time.monotonic() + 2.0
        while connection_count() >= MAX_CONNECTIONS and time.monotonic() < deadline:
            time.sleep(0.005)
        assert connection_count() < MAX_CONNECTIONS
        assert _rpc(session, "ping")["ok"] is True
    finally:
        for client in clients:
            client.close()


def test_global_inbound_pending_cap_drops_excess_partial_frame(session, monkeypatch):
    import bridge.core.lifecycle as lc

    monkeypatch.setattr(lc, "MAX_INBOUND_PENDING", 2048)
    first = socket.socket(socket.AF_UNIX)
    second = socket.socket(socket.AF_UNIX)
    try:
        first.settimeout(2.0)
        second.settimeout(2.0)
        first.connect(str(session.socket_path))
        second.connect(str(session.socket_path))
        partial = b"\x01\x00\x00\x00" + b"x" * 1500
        first.sendall(partial)
        second.sendall(partial)
        assert second.recv(1) == b""
        assert _rpc(session, "ping")["ok"] is True
    finally:
        first.close()
        second.close()


def test_oversized_request_payload_is_rejected_before_queueing(session, monkeypatch):
    import bridge.core.lifecycle as lc

    monkeypatch.setattr(lc, "MAX_REQUEST_PAYLOAD", 64)
    client = socket.socket(socket.AF_UNIX)
    try:
        client.settimeout(2.0)
        client.connect(str(session.socket_path))
        request = envelope.Request.new(session.token, "ping", {"blob": "x" * 100})
        client.sendall(envelope.encode_request(request))
        assert client.recv(1) == b""
        assert session._queue is not None and session._queue.pending == 0
    finally:
        client.close()


def test_accept_failure_closes_unowned_socket_and_retries_close(monkeypatch):
    import bridge.core.lifecycle as lc

    class FakeListener:
        def accept(self):
            return accepted, None

    class FakeWake:
        pass

    class FakeAccepted:
        def __init__(self):
            self.close_calls = 0

        def fileno(self):
            return 42

        def setblocking(self, _value):
            raise OSError("setblocking failed")

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("close failed")

    accepted = FakeAccepted()
    session = BridgeSession.__new__(BridgeSession)
    session._listener = FakeListener()
    session._wake_r = FakeWake()
    session._wake_w = None
    session._conns = {}
    session._conns_lock = threading.Lock()
    session._pending_close = []
    monkeypatch.setattr(lc.select, "select", lambda *_args: ([session._listener], [], []))

    session._io_iterate()
    assert accepted.close_calls == 1 and session._conns == {}
    assert session._pending_close == [accepted]
    session._retry_pending_closes()
    assert accepted.close_calls == 2 and session._pending_close == []


def test_drop_retains_connection_when_close_fails_then_retries():
    import bridge.core.lifecycle as lc

    class FlakySocket:
        def __init__(self):
            self.close_calls = 0

        def fileno(self):
            return 7

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("close failed")

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {}
    session._pending_close = []
    session._listener = object()
    session._wake_r = object()
    conn = type("Conn", (), {"sock": FlakySocket(), "closing": False,
                              "outbox": deque([b"held"]), "outbox_bytes": 4,
                              "send_offset": 0})()
    session._conns[7] = conn

    session._drop(conn)
    assert session._conns[7] is conn and conn.closing is True
    assert conn.outbox_bytes == 0 and not conn.outbox
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(lc.select, "select", lambda *_args: ([], [], []))
    try:
        session._io_iterate()
    finally:
        monkeypatch.undo()
    assert session._conns == {}


def test_send_rejects_old_connection_after_fd_key_reuse():
    class FakeSocket:
        def __init__(self, fd):
            self.fd = fd

        def fileno(self):
            return self.fd

    def conn(sock):
        return type("Conn", (), {"sock": sock, "closing": False,
                                  "outbox": [], "outbox_bytes": 0})()

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {}
    session._wake = lambda: pytest.fail("stale connection was woken")
    old = conn(FakeSocket(7))
    new = conn(FakeSocket(7))
    session._conns[7] = new

    session.send(old, b"stale")
    assert old.outbox == [] and new.outbox == []


def test_send_enforces_global_outbox_cap_without_touching_socket(monkeypatch, caplog):
    import bridge.core.lifecycle as lc

    class FakeSocket:
        def __init__(self, fd):
            self.fd = fd
            self.close_calls = 0

        def fileno(self):
            return self.fd

        def close(self):
            self.close_calls += 1

    def conn(fd, pending):
        payload = b"x" * pending
        return type("Conn", (), {"sock": FakeSocket(fd), "closing": False,
                                  "outbox": deque([payload]), "outbox_bytes": pending,
                                  "send_offset": 0})()

    monkeypatch.setattr(lc, "MAX_TOTAL_OUTBOX", 10)
    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    first, second = conn(1, 6), conn(2, 4)
    session._conns = {1: first, 2: second}
    wakes = []
    session._wake = lambda: wakes.append(True)

    with caplog.at_level(logging.INFO, logger="bcx.bridge"):
        session.send(second, b"overflow")
    assert second.closing is True and second.outbox_bytes == 4
    assert first.sock.close_calls == second.sock.close_calls == 0
    assert wakes == [True]
    assert any("outbox limit exceeded" in record.message for record in caplog.records)


def test_partial_flush_keeps_retained_frame_bytes_until_pop():
    class PartialSocket:
        def fileno(self):
            return 7

        def send(self, view):
            return min(3, len(view))

    conn = type("Conn", (), {"sock": PartialSocket(), "closing": False,
                              "outbox": deque([b"abcdef"]), "outbox_bytes": 6,
                              "send_offset": 0})()
    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {7: conn}

    session._flush(conn)
    assert conn.outbox_bytes == 6 and conn.send_offset == 3
    session._flush(conn)
    assert conn.outbox_bytes == 0 and conn.send_offset == 0 and not conn.outbox


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


def test_io_loop_rechecks_stop_between_iterations():
    """Late stop must not require observing the wake fd to terminate the loop."""
    s = BridgeSession.__new__(BridgeSession)
    s.stopped = False
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def iterate() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(1.0)
            return False
        return True  # lets the pre-fix implementation exit instead of leaking the test

    s._io_iterate = iterate  # type: ignore[method-assign]
    worker = threading.Thread(target=s._io_loop, daemon=True)
    worker.start()
    assert entered.wait(1.0)
    s.stopped = True
    release.set()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert calls == 1


def test_transport_close_performs_final_io_thread_join():
    session = BridgeSession.__new__(BridgeSession)
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    session._listener = listener
    session._wake_r = None
    session._wake_w = None

    def wait_for_close() -> None:
        while listener.fileno() != -1:
            time.sleep(0.005)

    session._io = threading.Thread(target=wait_for_close)
    session._io.start()
    session._close_listener()
    assert session._io is None


def test_transport_close_continues_after_individual_close_failure():
    events = []

    class FakeSocket:
        def __init__(self, name, fail=False):
            self.name = name
            self.fail = fail

        def close(self):
            events.append(self.name)
            if self.fail:
                raise OSError("close failed")

    session = BridgeSession.__new__(BridgeSession)
    session._listener = FakeSocket("listener", fail=True)
    session._wake_r = FakeSocket("wake-r")
    session._wake_w = FakeSocket("wake-w")
    session._io = None

    with pytest.raises(OSError, match="close failed"):
        session._close_listener()

    assert events == ["listener", "wake-r", "wake-w"]
    assert session._listener is not None
    assert session._wake_r is None and session._wake_w is None


def test_connection_close_continues_after_individual_close_failure():
    events = []

    class FakeSocket:
        def __init__(self, name, fail=False):
            self.name = name
            self.fail = fail

        def shutdown(self, _how):
            pass

        def close(self):
            events.append(self.name)
            if self.fail:
                raise OSError("close failed")

    class FakeConnection:
        def __init__(self, sock):
            self.sock = sock
            self.closing = False
            self.outbox = deque([b"pending"])
            self.outbox_bytes = len(self.outbox[0])
            self.send_offset = 0

    session = BridgeSession.__new__(BridgeSession)
    session._conns_lock = threading.Lock()
    session._conns = {
        1: FakeConnection(FakeSocket("first", fail=True)),
        2: FakeConnection(FakeSocket("second")),
    }

    with pytest.raises(OSError, match="close failed"):
        session._close_all_conns()

    assert events == ["first", "second"]
    assert list(session._conns) == [1]
    assert session._conns[1].outbox_bytes == 0


def test_stop_retries_failed_transport_close_and_then_becomes_idempotent():
    events: list[str] = []

    class FlakySocket:
        def __init__(self):
            self.calls = 0

        def close(self):
            self.calls += 1
            events.append(f"close-{self.calls}")
            if self.calls == 1:
                raise OSError("transient close failure")

    session = BridgeSession.__new__(BridgeSession)
    session.stopped = False
    session.cleanup_complete = False
    session._cleanup_lock = threading.Lock()
    session._conns_lock = threading.Lock()
    session._conns = {}
    session._listener = FlakySocket()
    session._wake_r = None
    session._wake_w = None
    session._io = None
    session._wake = lambda: events.append("wake")
    session._join_io = lambda: None
    session._close_all_conns = lambda: None
    session._drain_queue = lambda: None
    session._unlink_files = lambda: events.append("unlink")
    session._remove_dirs = lambda: events.append("rmdir")

    assert session.stop() is False
    assert session.stopped is True and session._listener is not None
    assert events == ["wake", "close-1"]

    assert session.stop() is True
    assert session._listener is None
    assert events == ["wake", "close-1", "wake", "close-2", "unlink", "rmdir"]

    assert session.stop() is True
    assert events[-1] == "rmdir" and events.count("close-2") == 1


def test_failed_transport_close_retains_published_paths_until_retry(tmp_path):
    session = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    listener = session._listener
    assert listener is not None

    class FirstCloseFailure:
        def __init__(self, inner):
            self.inner = inner
            self.close_calls = 0

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("transient close failure")
            self.inner.close()

    wrapped = FirstCloseFailure(listener)
    session._listener = wrapped
    assert session.stop() is False
    assert session.socket_path.exists()
    assert (session.session_dir / "session.json").exists()
    assert wrapped.inner.fileno() >= 0

    assert session.stop() is True
    assert wrapped.inner.fileno() == -1
    assert not session.socket_path.exists() and not session.session_dir.exists()


def test_sun_path_fallback(tmp_path):
    deep = tmp_path / ("x" * 90)          # 让默认 socket 路径必然超 100 字节
    s = BridgeSession.start(deep, FakeReader(), blender_version="5.2.0")
    try:
        assert len(str(s.socket_path).encode()) <= 100
        assert s.session_dir.exists()     # session.json 仍在 runtime 根下
    finally:
        s.stop()


def test_failed_start_leaves_no_artifacts(tmp_path, monkeypatch):
    # audit F-04：发布前任一步失败 → 无 session.json、无遗留目录、无泄漏线程
    import bridge.core.lifecycle as lc

    def boom(path, data, *, dir_fd=None):
        raise OSError("disk full")

    monkeypatch.setattr(lc, "write_session_file", boom)
    with pytest.raises(OSError):
        BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    time.sleep(0.2)
    assert list((tmp_path / "run").iterdir()) == []
    # 不用 active_count()：全套运行时其他用例的守护线程会造成假阳性——按名断言
    assert not any(t.name == "bcx-io" and t.is_alive() for t in threading.enumerate())


def test_failed_listen_closes_listener_and_leaves_no_published_artifacts(
        tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_socket = lc.socket.socket
    closed = False

    class ListenFailureSocket(real_socket):
        def listen(self, backlog):
            raise OSError("listen failed")

        def close(self):
            nonlocal closed
            closed = True
            super().close()

    monkeypatch.setattr(lc.socket, "socket", ListenFailureSocket)
    with pytest.raises(OSError, match="listen failed"):
        BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")

    assert closed
    assert list((tmp_path / "run").iterdir()) == []


def test_failed_start_retries_transient_listener_close(tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_socket = lc.socket.socket
    created = []

    class ListenAndFirstCloseFailureSocket(real_socket):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.close_calls = 0
            created.append(self)

        def listen(self, backlog):
            raise OSError("listen failed")

        def close(self):
            self.close_calls += 1
            if self.close_calls == 1:
                raise OSError("transient close failure")
            super().close()

    monkeypatch.setattr(lc.socket, "socket", ListenAndFirstCloseFailureSocket)
    with pytest.raises(OSError, match="listen failed"):
        BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")

    assert len(created) == 1
    assert created[0].close_calls == 2 and created[0].fileno() == -1
    assert list((tmp_path / "run").iterdir()) == []


def test_directory_fd_close_error_does_not_orphan_started_session(
        tmp_path, monkeypatch):
    import bridge.core.lifecycle as lc

    real_close = lc.os.close
    close_calls = 0

    def close_then_fail_once(fd):
        nonlocal close_calls
        close_calls += 1
        real_close(fd)
        if close_calls == 1:
            raise OSError("post-close failure")

    monkeypatch.setattr(lc.os, "close", close_then_fail_once)
    session = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    try:
        assert close_calls >= 3
        assert (session.session_dir / "session.json").exists()
        assert session._listener is not None and session._io is not None
    finally:
        session.stop()


def test_bind_conflict_preserves_foreign_socket(tmp_path, monkeypatch):
    # 复审 R-02：socket 路径已被别人的活 listener 占用 → 启动失败，
    # 但**绝不能**删掉对方的 socket 文件（会造成对方拒绝服务）
    # 短路径：pytest tmp_path 会撞 macOS sun_path 104 字节上限
    foreign = Path(tempfile.mkdtemp(prefix="bcx-fgn-")) / "bridge.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(foreign))
    srv.listen(1)
    monkeypatch.setattr(BridgeSession, "_resolve_socket_path",
                        staticmethod(lambda session_dir: (foreign, None)))
    try:
        with pytest.raises(OSError):
            BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
        assert foreign.exists(), "外部 socket 被误删——DoS"
        probe = socket.socket(socket.AF_UNIX)   # 对方仍可被连接
        probe.settimeout(2.0)
        probe.connect(str(foreign))
        probe.close()
    finally:
        srv.close()
        foreign.unlink(missing_ok=True)
        foreign.parent.rmdir()


def test_stop_preserves_socket_replacement_at_owned_path(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    fallback = s._sock_tmpdir
    original_socket = s.socket_path.with_name("original.sock")
    s.socket_path.rename(original_socket)
    replacement = socket.socket(socket.AF_UNIX)
    replacement.bind(str(s.socket_path))
    replacement.listen(1)
    try:
        assert s.stop() is False
        assert s.socket_path.exists()
        assert s.session_dir.exists()
        assert (s.session_dir / "session.json").exists()
        probe = socket.socket(socket.AF_UNIX)
        probe.settimeout(1.0)
        probe.connect(str(s.socket_path))
        probe.close()
    finally:
        replacement.close()
        s.socket_path.unlink(missing_ok=True)
        original_socket.unlink(missing_ok=True)
        if fallback is not None and fallback.exists():
            fallback.rmdir()


def test_stop_preserves_replacement_session_directory(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    original = s.session_dir.with_name(s.session_dir.name + "-original")
    s.session_dir.rename(original)
    s.session_dir.mkdir(mode=0o700)
    try:
        assert s.stop() is False
        assert s.session_dir.exists(), "stop removed a replacement directory"
        assert (original / "session.json").exists()
    finally:
        for directory in (s.session_dir, original):
            if directory.exists():
                for child in directory.iterdir():
                    child.unlink(missing_ok=True)
                directory.rmdir()


def test_stop_reports_unknown_session_child_as_cleanup_incomplete(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    unknown = s.session_dir / "foreign.txt"
    unknown.write_text("preserve")
    try:
        assert s.stop() is False
        assert s.cleanup_complete is False
        assert unknown.read_text() == "preserve"
        assert s.session_dir.exists()
    finally:
        unknown.unlink(missing_ok=True)
        s.session_dir.rmdir()


def test_stop_runs_driver_hooks_between_transport_and_final_cleanup():
    events: list[str] = []
    s = BridgeSession.__new__(BridgeSession)
    s.stopped = False
    s.cleanup_complete = False
    s._cleanup_lock = threading.Lock()
    s._conns_lock = threading.Lock()
    s._conns = {}
    s._listener = None
    s._wake_r = None
    s._wake_w = None
    s._io = None
    s._wake = lambda: events.append("wake")
    s._join_io = lambda: events.append("join")
    s._close_all_conns = lambda: events.append("connections")
    s._close_listener = lambda: events.append("listener")
    s._drain_queue = lambda: events.append("queue")
    s._unlink_files = lambda: events.append("files")
    s._remove_dirs = lambda: events.append("dirs")

    s.stop(lambda: events.append("timer"), lambda: events.append("handlers"))

    assert events == ["wake", "join", "connections", "listener", "timer",
                      "handlers", "queue", "files", "dirs"]


def test_wake_storm_is_nonblocking_and_coalesced(tmp_path, monkeypatch):
    release_io = threading.Event()
    monkeypatch.setattr(BridgeSession, "_io_loop", lambda _: release_io.wait(2.0))
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    done = threading.Event()

    def storm() -> None:
        for _ in range(100_000):
            s._wake()
        done.set()

    worker = threading.Thread(target=storm, daemon=True)
    try:
        worker.start()
        assert done.wait(1.0), "wake storm blocked on the socketpair"
        assert s._wake_w is not None and not s._wake_w.getblocking()
        assert s._wake_r is not None and s._wake_r.recv(4096) == b"x"
    finally:
        release_io.set()
        if not done.is_set() and s._wake_r is not None:
            s._wake_r.close()       # unblock the pre-fix blocking sender
        s.stop()
        worker.join(timeout=1.0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_lifecycle.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
# bridge/core/lifecycle.py
"""会话生命周期与 I/O 线程。spec §2.2 权限表、§3.7 连接模型（单写者五规则）、§4.1 启动序列。"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import select
import socket
import stat as stat_mod
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

from ._proto import envelope, framing
from .contracts import Clock, SceneReader
from .queue import QueueFull, TaskQueue
from .router import BridgeMeta, Router
from .session import SessionAuth, write_session_file

BRIDGE_VERSION = "0.1.0"
MAX_SUN_PATH = 100
MAX_OUTBOX = 32 * 1024 * 1024        # §3.7 规则 4：发送背压上限
MAX_TOTAL_OUTBOX = 64 * 1024 * 1024
MAX_CONNECTIONS = 64                 # unauthenticated/partial-frame memory bound
MAX_INBOUND_PENDING = 32 * 1024 * 1024
MAX_REQUEST_PAYLOAD = 64 * 1024
PRIVATE_INIT_TIMEOUT = 0.1
_diag = logging.getLogger("bcx.bridge")


class _MonotonicClock:
    def monotonic(self) -> float:
        return time.monotonic()


def _ensure_private_dir(path: Path) -> tuple[int, int]:
    """Race-safe create-or-validate for application-owned 0700 directories."""
    created = False
    try:
        path.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        pass
    else:
        created = True
    if created:
        os.chmod(path, 0o700, follow_symlinks=False)
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: tuple[int, int] | None = None
    while True:
        st = path.lstat()
        identity = st.st_dev, st.st_ino
        mode = stat_mod.S_IMODE(st.st_mode)
        if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            break
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)
    return st.st_dev, st.st_ino


def _wait_private_dir_at(name: str, parent_fd: int, path: Path) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: tuple[int, int] | None = None
    while True:
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity = st.st_dev, st.st_ino
        mode = stat_mod.S_IMODE(st.st_mode)
        if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            return st
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)


def _private_dir_identity(fd: int, path: Path,
                          expected: tuple[int, int] | None = None) -> tuple[int, int]:
    st = os.fstat(fd)
    identity = st.st_dev, st.st_ino
    if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat_mod.S_IMODE(st.st_mode) != 0o700
            or (expected is not None and identity != expected)):
        raise PermissionError(f"private directory required: {path}")
    return identity


class _Conn:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buf = framing.FrameBuffer()
        self.outbox: deque[bytes] = deque()   # 只由 I/O 线程消费（§3.7 规则 3）
        # Retained frame allocation, not unsent wire bytes: partial sends keep the
        # complete ``bytes`` object alive until popleft, so decrement only on pop.
        self.outbox_bytes = 0
        self.send_offset = 0                  # outbox[0] 的部分写偏移
        self.closing = False


class BridgeSession:
    def __init__(self, clock: Clock) -> None:  # 仅供 start() 使用；属性全部在此声明（mypy strict）
        self.stopped = False
        self.instance_id = ""
        self.token = ""
        self.session_dir = Path()
        self.socket_path = Path()
        self._socket_owned = False   # 仅当本实例成功 bind 后为真（复审 R-02）
        self._socket_identity: tuple[int, int] | None = None
        self._socket_parent_identity: tuple[int, int] | None = None
        self._session_identity: tuple[int, int] | None = None
        self._session_dir_identity: tuple[int, int] | None = None
        self._sock_tmpdir: Path | None = None
        self._clock = clock
        self._conns: dict[int, _Conn] = {}
        self._conns_lock = threading.Lock()
        self._pending_close: list[socket.socket] = []
        self._queue: TaskQueue | None = None
        self._auth: SessionAuth | None = None
        self._listener: socket.socket | None = None
        self._wake_r: socket.socket | None = None
        self._wake_w: socket.socket | None = None
        self._wake_lock = threading.Lock()
        self._wake_pending = False
        self._io: threading.Thread | None = None
        self._cleanup_lock = threading.Lock()
        self.cleanup_complete = False

    # ---------- 启动（session.json 最后发布；失败时仅回收 identity-bound 自有物） ----------
    @classmethod
    def start(cls, runtime_root: Path, reader: SceneReader, blender_version: str,
              clock: Clock | None = None) -> "BridgeSession":
        self = cls(clock or _MonotonicClock())
        root_fd: int | None = None
        run_fd: int | None = None
        session_fd: int | None = None
        try:
            runtime_root = Path(runtime_root)
            root_identity = _ensure_private_dir(runtime_root)
            dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
            root_fd = os.open(runtime_root, dir_flags)
            _private_dir_identity(root_fd, runtime_root, root_identity)
            run_created = False
            try:
                os.mkdir("run", mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                pass
            else:
                run_created = True
            if run_created:
                os.chmod("run", 0o700, dir_fd=root_fd, follow_symlinks=False)
            run_path = runtime_root / "run"
            run_stat = _wait_private_dir_at("run", root_fd, run_path)
            run_identity = run_stat.st_dev, run_stat.st_ino
            run_fd = os.open("run", dir_flags, dir_fd=root_fd)
            _private_dir_identity(run_fd, run_path, run_identity)
            self.instance_id = f"gui-{os.getpid()}-{secrets.token_hex(4)}"
            self.session_dir = run_path / self.instance_id
            os.mkdir(self.instance_id, mode=0o700, dir_fd=run_fd)  # exclusive leaf
            session_stat = os.stat(self.instance_id, dir_fd=run_fd,
                                   follow_symlinks=False)
            self._session_dir_identity = session_stat.st_dev, session_stat.st_ino
            os.chmod(self.instance_id, 0o700, dir_fd=run_fd, follow_symlinks=False)
            session_fd = os.open(self.instance_id, dir_flags, dir_fd=run_fd)
            _private_dir_identity(session_fd, self.session_dir,
                                  self._session_dir_identity)
            if not self._path_matches(self.session_dir, self._session_dir_identity,
                                      stat_mod.S_ISDIR):
                raise OSError("session directory changed during startup")

            self.token = SessionAuth.generate()
            self._auth = SessionAuth(self.token)
            self.socket_path, self._sock_tmpdir = self._resolve_socket_path(self.session_dir)
            if self._sock_tmpdir is not None:
                self._sock_tmpdir.mkdir(mode=0o700)
            socket_parent_stat = self.socket_path.parent.lstat()
            if (not stat_mod.S_ISDIR(socket_parent_stat.st_mode)
                    or socket_parent_stat.st_uid != os.geteuid()):
                raise OSError("socket parent is not a directory")
            socket_parent_identity = (socket_parent_stat.st_dev, socket_parent_stat.st_ino)
            self._socket_parent_identity = socket_parent_identity
            if (self._sock_tmpdir is None
                    and socket_parent_identity != self._session_dir_identity):
                raise OSError("session directory changed before bind")
            if self._sock_tmpdir is not None:
                os.chmod(self._sock_tmpdir, 0o700)
            if stat_mod.S_IMODE(self.socket_path.parent.stat().st_mode) != 0o700:
                raise PermissionError("private socket directory required")

            router = Router(reader, BridgeMeta(self.instance_id, os.getpid(),
                                               BRIDGE_VERSION, blender_version))
            self._queue = TaskQueue(router.handle, self._clock, diag=_diag)

            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener = listener
            listener.bind(str(self.socket_path))
            self._socket_owned = True   # bind 成功 = 本实例拥有该路径（复审 R-02）
            if not self._path_matches(self.socket_path.parent,
                                      self._socket_parent_identity, stat_mod.S_ISDIR):
                raise OSError("socket parent changed during bind")
            socket_stat = self.socket_path.lstat()
            if not stat_mod.S_ISSOCK(socket_stat.st_mode):
                raise OSError("bound socket path is not a socket")
            socket_identity = (socket_stat.st_dev, socket_stat.st_ino)
            self._socket_identity = socket_identity
            os.chmod(self.socket_path, 0o600)          # §2.2：bind 后立即收权限
            listener.listen(8)
            listener.setblocking(False)
            self._wake_r, self._wake_w = socket.socketpair()
            self._wake_r.setblocking(False)
            self._wake_w.setblocking(False)
            self._io = threading.Thread(target=self._io_loop, name="bcx-io", daemon=True)
            self._io.start()

            # 最后才发布：bind/listen/线程任一失败都不会留下被 Discovery
            # 长期误识别的「假会话」文件
            write_session_file(self.session_dir / "session.json", {
                "instance_id": self.instance_id, "token": self.token, "pid": os.getpid(),
                "socket_path": str(self.socket_path), "blender_version": blender_version,
                "bridge_version": BRIDGE_VERSION,
                "envelope_version": envelope.ENVELOPE_VERSION,
                "socket_external": self._sock_tmpdir is not None,
                "socket_dev": socket_identity[0],
                "socket_ino": socket_identity[1],
                "socket_dir_dev": socket_parent_identity[0],
                "socket_dir_ino": socket_parent_identity[1],
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }, dir_fd=session_fd)
            session_stat = os.stat("session.json", dir_fd=session_fd,
                                   follow_symlinks=False)
            if (not stat_mod.S_ISREG(session_stat.st_mode)
                    or stat_mod.S_IMODE(session_stat.st_mode) != 0o600):
                raise OSError("published session file is not private")
            self._session_identity = (session_stat.st_dev, session_stat.st_ino)
        except BaseException:
            # start() never returns ``self`` on failure, so retry one transient
            # cleanup failure here while the resource references are still reachable.
            if not self.stop() and not self.stop():
                _diag.error("startup cleanup remains incomplete after retry")
            raise
        finally:
            for fd in (session_fd, run_fd, root_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        # close(2) error state is platform-dependent; retrying may
                        # close a reused descriptor.  Do not turn a published, usable
                        # session into an orphaned startup failure.
                        _diag.exception("directory fd close failed")
        return self

    @staticmethod
    def _resolve_socket_path(session_dir: Path) -> tuple[Path, Path | None]:
        p = session_dir / "bridge.sock"
        if len(str(p).encode()) <= MAX_SUN_PATH:
            return p, None
        digest = hashlib.sha256(session_dir.name.encode()).hexdigest()[:16]
        short = Path("/tmp") / f"bcx-{digest}"
        if len(str(short / "bridge.sock").encode()) > MAX_SUN_PATH:
            raise OSError("no short Unix socket path available")
        return short / "bridge.sock", short

    # ---------- 发送：唯一入口（§3.7 规则 3 单写者） ----------
    def send(self, conn: _Conn, frame: bytes) -> None:
        """任意线程可调；只入 outbox + 唤醒。对已断开连接静默丢弃（§3.6）。"""
        over_limit = False
        with self._conns_lock:
            if (self._conns.get(conn.sock.fileno()) is not conn or conn.closing):
                return
            total = sum(item.outbox_bytes for item in self._conns.values())
            if (conn.outbox_bytes + len(frame) > MAX_OUTBOX
                    or total + len(frame) > MAX_TOTAL_OUTBOX):
                conn.closing = True
                over_limit = True
            else:
                conn.outbox.append(frame)
                conn.outbox_bytes += len(frame)
        if over_limit:
            _diag.info("outbox limit exceeded, dropping connection")
        self._wake()

    def _wake(self) -> None:
        with self._wake_lock:
            if self._wake_pending or self._wake_w is None:
                return
            try:
                self._wake_w.send(b"x")
                self._wake_pending = True
            except BlockingIOError:
                self._wake_pending = True   # 已有字节占满缓冲区，同样会唤醒 select
            except OSError:
                pass

    def _drain_wake(self) -> None:
        assert self._wake_r is not None
        with self._wake_lock:
            try:
                while self._wake_r.recv(4096):
                    pass
            except OSError:
                pass
            self._wake_pending = False

    # ---------- I/O 线程（§3.7 五规则） ----------
    def _io_loop(self) -> None:
        # stop() may time out while this thread is finishing one iteration and then
        # close the listener/socketpair. Re-check the flag at the loop boundary so
        # the next iteration cannot spin forever on already-closed descriptors merely
        # because the wake byte was not observed by the previous select.
        while not self.stopped:
            try:
                if self._io_iterate():
                    return
            except Exception:                            # 规则 5：护栏，绝不带走线程
                _diag.exception("io loop iteration failed")

    def _io_iterate(self) -> bool:
        assert self._listener is not None and self._wake_r is not None
        self._retry_pending_closes()
        with self._conns_lock:
            closing = [c for c in self._conns.values() if c.closing]
        for conn in closing:
            self._drop(conn)
        with self._conns_lock:
            conns = [c for c in self._conns.values() if not c.closing]
            pending_close = bool(self._pending_close)
        rlist: list[socket.socket] = [self._wake_r]
        if not pending_close:
            rlist.insert(0, self._listener)
        rlist += [c.sock for c in conns]
        wlist = [c.sock for c in conns if c.outbox]
        ready_r, ready_w, _ = select.select(rlist, wlist, [], 1.0)
        if self._wake_r in ready_r:
            self._drain_wake()
            if self.stopped:
                return True
        if self._listener in ready_r:
            sock: socket.socket | None = None
            owned = False
            try:
                sock, _ = self._listener.accept()
                sock.setblocking(False)
                with self._conns_lock:
                    if len(self._conns) >= MAX_CONNECTIONS:
                        _diag.info("connection limit reached, dropping peer")
                    else:
                        self._conns[sock.fileno()] = _Conn(sock)
                        owned = True
            except Exception:
                _diag.exception("accept failed")
            finally:
                if sock is not None and not owned:
                    try:
                        sock.close()
                    except Exception:
                        _diag.exception("rejected connection close failed")
                        if sock.fileno() >= 0:
                            with self._conns_lock:
                                self._pending_close.append(sock)
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

    def _retry_pending_closes(self) -> None:
        with self._conns_lock:
            pending = list(getattr(self, "_pending_close", ()))
        for sock in pending:
            try:
                sock.close()
            except Exception:
                _diag.exception("pending connection close failed")
                if sock.fileno() >= 0:
                    continue
            with self._conns_lock:
                if sock in getattr(self, "_pending_close", ()):
                    self._pending_close.remove(sock)

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
                    if not conn.outbox or conn.outbox[0] is not head:
                        return
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
        with self._conns_lock:
            pending_bytes = sum(item.buf.pending for item in self._conns.values())
        if pending_bytes > MAX_INBOUND_PENDING:
            _diag.info("inbound pending limit exceeded, dropping connection")
            self._drop(conn)
            return
        for payload in frames:
            if not self._dispatch(conn, payload):
                break

    def _dispatch(self, conn: _Conn, payload: bytes) -> bool:
        assert self._auth is not None and self._queue is not None
        if len(payload) > MAX_REQUEST_PAYLOAD:
            _diag.info("request payload limit exceeded, closing connection")
            self._drop(conn)
            return False
        try:
            req = envelope.decode_request(payload)
        except ValueError:
            self._drop(conn)                             # 解码失败断开，不回帧（§5）
            return False
        if not self._auth.verify(req.token):
            _diag.info("auth failed, closing connection")  # §5.2 Bridge 诊断日志
            self._drop(conn)
            return False
        timeout = envelope.METHOD_TIMEOUTS.get(req.method, 2.0)
        deadline = self._clock.monotonic() + timeout
        try:
            self._queue.submit(req, lambda frame: self.send(conn, frame), deadline)
        except QueueFull:
            self.send(conn, envelope.error_frame(req.id, envelope.BRIDGE_BUSY,
                                                 "queue full", retryable=True))
        return True

    def _drop(self, conn: _Conn) -> None:
        with self._conns_lock:
            key = next((key for key, value in self._conns.items() if value is conn), None)
            conn.closing = True
            conn.outbox.clear()
            conn.outbox_bytes = 0
            conn.send_offset = 0
        try:
            conn.sock.close()
        except Exception:
            _diag.exception("connection close failed")
            if conn.sock.fileno() >= 0:
                return
        if key is not None:
            with self._conns_lock:
                if self._conns.get(key) is conn:
                    self._conns.pop(key)

    # ---------- 主线程 ----------
    def tick(self, budget_ms: int = 50) -> float:
        assert self._queue is not None
        return self._queue.tick(budget_ms)   # 主线程只跑队列：不碰 _conns、不碰 socket

    # ---------- 关闭（§3.7 10 步，幂等） ----------
    def stop(self, unregister_timer: Callable[[], None] | None = None,
             unregister_handlers: Callable[[], None] | None = None) -> bool:
        self.stopped = True                              # 1 置停止标志
        with self._cleanup_lock:
            if self.cleanup_complete:
                return True
            failed = False
            steps: list[Callable[[], object]] = [
                self._wake,                                  # 2 唤醒 select
                self._join_io,                               # 3 join I/O 线程
                self._close_all_conns,                       # 4 关闭活跃连接（含丢弃 outbox）
                self._close_listener,                        # 5 关监听与 socketpair
                unregister_timer or (lambda: None),          # 6 timer 注销（driver hook）
                unregister_handlers or (lambda: None),       # 7 handler 注销（driver hook）
                self._drain_queue,                           # 8 清空队列不回复
            ]
            for i, step in enumerate(steps, start=2):
                try:
                    if step() is False:
                        failed = True
                        _diag.warning("stop step %d incomplete", i)
                except Exception:
                    failed = True
                    _diag.exception("stop step %d failed, continuing", i)
            transport_closed = self._transport_closed()
            if transport_closed:
                for i, step in ((9, self._unlink_files), (10, self._remove_dirs)):
                    try:
                        if step() is False:
                            failed = True
                            _diag.warning("stop step %d incomplete", i)
                    except Exception:
                        failed = True
                        _diag.exception("stop step %d failed, continuing", i)
            else:
                failed = True
                _diag.warning("transport cleanup incomplete; retaining session paths")
            transport_closed = self._transport_closed()
            self.cleanup_complete = not failed and transport_closed
            return self.cleanup_complete

    def _transport_closed(self) -> bool:
        with self._conns_lock:
            no_connections = not self._conns
            no_pending = not getattr(self, "_pending_close", ())
        return (self._listener is None and self._wake_r is None
                and self._wake_w is None and no_connections and no_pending
                and (self._io is None or not self._io.is_alive()))

    def _join_io(self) -> None:
        if self._io is not None:
            self._io.join(timeout=2.0)

    def _drain_queue(self) -> None:
        if self._queue is not None:
            self._queue.drain()

    def _close_listener(self) -> None:
        failure: Exception | None = None
        for attribute in ("_listener", "_wake_r", "_wake_w"):
            sock = getattr(self, attribute)
            if sock is not None:
                try:
                    sock.close()
                except Exception as exc:
                    failure = failure or exc
                    _diag.exception("transport close failed")
                else:
                    setattr(self, attribute, None)
        if (self._io is not None and self._io is not threading.current_thread()
                and self._io.is_alive()):
            self._io.join(timeout=1.0)
            if self._io.is_alive():
                _diag.warning("I/O thread still alive after transport close")
                failure = failure or RuntimeError("I/O thread still alive")
        if self._io is not None and not self._io.is_alive():
            self._io = None
        if failure is not None:
            raise failure

    def _close_all_conns(self) -> None:
        with self._conns_lock:
            conns = list(self._conns.items())
        failure: Exception | None = None
        for key, c in conns:
            with self._conns_lock:
                c.closing = True
                c.outbox.clear()
                c.outbox_bytes = 0
                c.send_offset = 0
            try:
                c.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                c.sock.close()
            except Exception as exc:
                failure = failure or exc
                _diag.exception("connection close failed")
            else:
                with self._conns_lock:
                    if self._conns.get(key) is c:
                        self._conns.pop(key)
        if failure is not None:
            raise failure
        self._retry_pending_closes()

    def _unlink_files(self) -> bool:
        # 只删自己 bind 成功的 socket：EADDRINUSE 时该路径属于**别人**的活 listener，
        # 删掉即造成对方拒绝服务（复审 R-02 实测）
        complete = True
        if self._socket_owned and self.socket_path != Path() \
                and self._path_matches(self.socket_path, self._socket_identity,
                                       stat_mod.S_ISSOCK):
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                complete = False
        elif self._socket_owned and self.socket_path != Path() \
                and not self._path_absent(self.socket_path):
            complete = False
        if not complete:
            # Preserve session metadata as retryable evidence whenever the owned
            # socket path was replaced or could not be removed safely.
            return False
        session_file = self.session_dir / "session.json"
        if self.session_dir != Path() \
                and self._path_matches(session_file, self._session_identity,
                                       stat_mod.S_ISREG):
            try:
                session_file.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                complete = False
        elif self.session_dir != Path() and not self._path_absent(session_file):
            complete = False
        return complete

    @staticmethod
    def _path_matches(path: Path, expected: tuple[int, int] | None,
                      kind: Callable[[int], bool]) -> bool:
        if expected is None:
            return False
        try:
            st = path.lstat()
        except OSError:
            return False
        return kind(st.st_mode) and (st.st_dev, st.st_ino) == expected

    @staticmethod
    def _path_absent(path: Path) -> bool:
        try:
            path.lstat()
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return False

    def _remove_dirs(self) -> bool:
        complete = True
        for d, expected in ((self._sock_tmpdir, self._socket_parent_identity),
                            (self.session_dir, self._session_dir_identity)):
            if d is None or d == Path():
                continue
            if self._path_matches(d, expected, stat_mod.S_ISDIR):
                try:
                    d.rmdir()
                except OSError:
                    complete = False
                    _diag.info("session dir not empty, left in place: %s", d)
            elif not self._path_absent(d):
                complete = False
        return complete
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_lifecycle.py -q` → 38 passed（v7）
（若 `test_half_header...` 偶发超时：检查 select 集合是否含已建立连接——那正是 §3.7 规则 1 要抓的缺陷）

- [ ] **Step 5: Commit**

```bash
git add bridge/core/lifecycle.py tests/unit/test_lifecycle.py
git commit -m "feat(bridge-core): I/O 线程 select 多路复用、会话启停 10 步序、sun_path 回退"
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
  - `same_file(a: Path, b: Path) -> bool`——按 `(st_dev, st_ino)` 辅助识别两个**已存在**路径的别名；只供查询/诊断，`False` 也可能表示无法 stat，禁止据此授权写入或宣称 FR-21/TOCTOU 已关闭
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
from server.core.path_policy import PathDenied, PathPolicy, same_file


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


def test_same_file_detects_case_variant_on_case_insensitive_fs(tmp_path):
    # FR-21 红线：macOS 默认 APFS 大小写不敏感，Scene.blend 与 scene.blend 是
    # 同一个文件。按路径字符串判定会让 agent 静默覆盖用户原稿（已实测复现）。
    orig = tmp_path / "Scene.blend"
    orig.write_bytes(b"ORIGINAL")
    variant = tmp_path / "scene.blend"
    if not variant.exists():
        pytest.skip("文件系统大小写敏感，本用例不适用")
    assert str(variant.resolve()) != str(orig.resolve())   # 字符串说「不同」
    assert same_file(variant, orig)                        # inode 说「同一个」


def test_same_file_distinguishes_real_different_files(tmp_path):
    a = tmp_path / "a.blend"
    b = tmp_path / "b.blend"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    assert not same_file(a, b)


def test_rejects_embedded_nul_as_path_denied(policy):
    with pytest.raises(PathDenied, match="unresolvable"):
        policy.resolve("/tmp/evil\0.blend")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_config.py tests/unit/test_path_policy.py -q` → FAIL

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
"""路径策略：fail-closed 前置过滤。URS FR-30。Phase 0 无路径参数，交付并测试。

**字符串校验 ≠ 写入安全边界（audit F-05，TOCTOU）**：resolve() 与实际写入之间
存在时间窗，路径组件可被替换为 symlink。Phase 1 的真实写入必须 fd-based——
O_NOFOLLOW / dir-fd openat、同目录临时文件 + 原子 rename，授权绑定已打开的 fd。"""
from __future__ import annotations

from pathlib import Path


class PathDenied(Exception):
    pass


def same_file(a: Path, b: Path) -> bool:
    """查询两个已存在路径当前是否指向同一 inode；不是写入安全边界。

    macOS 默认 APFS 大小写不敏感，且 `Path.resolve()` **不归一化大小写**（实测）。
    因此 `Scene.blend` 与 `scene.blend` 字符串不等、inode 相同。任一 stat 失败时
    `False` 表示「未知」，不表示「已证明不同」。Phase 1 写入必须在已打开 fd 上
    fail-closed 地校验 identity，并配合 dir-fd / `O_NOFOLLOW` / 原子替换；不得只调用
    本函数后写入。
    """
    try:
        sa, sb = a.stat(), b.stat()
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


class PathPolicy:
    def __init__(self, roots: list[Path], allowed_exts: set[str]) -> None:
        self._roots = [r.expanduser().resolve() for r in roots]
        self._exts = allowed_exts

    def resolve(self, raw: str) -> Path:
        p = Path(raw).expanduser()
        try:
            p = p.resolve(strict=False)      # realpath：吃掉 .. 与符号链接
        except (OSError, ValueError) as e:
            raise PathDenied(f"unresolvable: {raw}") from e
        if p.suffix.lower() not in self._exts:
            raise PathDenied(f"extension not allowed: {p.suffix}")
        for root in self._roots:
            if p == root or root in p.parents:
                return p
        raise PathDenied(f"outside allowed roots: {p}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_config.py tests/unit/test_path_policy.py -q` → 10 passed

- [ ] **Step 5: Commit**

```bash
git add server/core/config.py server/core/path_policy.py \
        tests/unit/test_config.py tests/unit/test_path_policy.py
git commit -m "feat(server-core): BLENDERCODEX_ROOT 注入点与 fail-closed 路径策略"
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
  - `versions.check(blender_version: str) -> tuple[bool, str | None]`——仅完整版本 **`5.2.0`** 匹配才 supported；corrective release 需先按 NFR-C2 重评，否则只读放行并附 warning、写工具拒绝
  - `capabilities.describe(server_version: str, connected: list[dict]) -> dict`——§6.3 outputSchema：`phase="phase0"`、`ir_schema_version=None`、`supported_operation_kinds=[]`、`supported_tools=["get_blender_status","get_scene_summary","describe_capabilities"]`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_audit.py
import datetime
import fcntl
import hashlib
import json
import multiprocessing
import os
import stat
import threading
import time
from pathlib import Path

import pytest
from server.core.audit import AuditLog


def _record_split_in_process(logs: str, index: int, start) -> None:
    """Spawn-safe helper: make one logical record use two physical writes."""
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen

    class SplitWriter:
        def __init__(self, fd, mode, encoding):
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._inner.close()

        def write(self, value):
            midpoint = len(value) // 2
            self._inner.write(value[:midpoint])
            self._inner.flush()
            time.sleep(0.005)
            self._inner.write(value[midpoint:])

    audit_module.os.fdopen = SplitWriter
    start.wait()
    AuditLog(Path(logs)).record(
        f"process-tool-{index}", f"process-request-{index}",
        ok=True, duration_ms=1.0)


def _hold_file_lock(path: str, ready, release) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        ready.set()
        release.wait()
    finally:
        os.close(fd)


def test_record_appends_jsonl_with_digest_not_raw_params(tmp_path):
    log = AuditLog(tmp_path / "logs")
    params = {"instance_id": "gui-1-aa"}
    log.record("get_scene_summary", "req1", ok=True, duration_ms=12.5,
               instance_id="gui-1-aa", params=params)
    files = list((tmp_path / "logs").glob("server-*.jsonl"))
    assert len(files) == 1
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "logs").stat().st_mode) == 0o700
    row = json.loads(files[0].read_text().splitlines()[0])
    assert row["tool"] == "get_scene_summary"
    assert row["transaction_id"] is None          # Phase 0 占位（§5.2）
    assert row["paths"] == []
    assert "gui-1-aa" not in json.dumps(row.get("params_digest"))
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    assert row["params_digest"] == hashlib.sha256(canonical).hexdigest()[:16]


def test_huge_params_use_fixed_bounded_digest_without_full_dumps(
        tmp_path, monkeypatch):
    import server.core.audit as audit_module

    params = {"items": ["sensitive"] * 1_000_000}
    real_dumps = audit_module.json.dumps

    def reject_whole_params(value, *args, **kwargs):
        if value is params:
            raise AssertionError("whole params were materialized")
        return real_dumps(value, *args, **kwargs)

    monkeypatch.setattr(audit_module.json, "dumps", reject_whole_params)
    log = AuditLog(tmp_path / "logs")
    started = time.monotonic()
    log.record("tool", "request", ok=True, duration_ms=1.0, params=params,
               deadline=started + 1.0)
    assert time.monotonic() - started < 0.5
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    row = json.loads(path.read_text())
    assert row["params_digest"] == audit_module.PARAMS_TRUNCATED_DIGEST
    assert path.stat().st_size <= audit_module.MAX_AUDIT_LINE_BYTES
    assert "sensitive" not in path.read_text()


def test_deep_and_unencodable_params_use_bounded_sentinel(tmp_path):
    import server.core.audit as audit_module

    deep = {"secret": "must-not-leak"}
    for _ in range(audit_module.MAX_AUDIT_PARAMS_DEPTH + 1_000):
        deep = {"x": deep}
    log = AuditLog(tmp_path / "logs")
    log.record("tool", "deep", ok=True, duration_ms=1.0, params=deep)
    log.record("tool", "object", ok=True, duration_ms=1.0,
               params={"value": object()})
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    text = path.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert [row["params_digest"] for row in rows] == [
        audit_module.PARAMS_UNENCODABLE_DIGEST,
        audit_module.PARAMS_UNENCODABLE_DIGEST,
    ]
    assert "must-not-leak" not in text


def test_unbounded_audit_fields_fail_closed_before_file_creation(tmp_path):
    import server.core.audit as audit_module

    log = AuditLog(tmp_path / "logs")
    cases = [
        (("x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1), "request"), {}),
        (("tool", "x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)), {}),
        (("tool", 1 << (audit_module.MAX_AUDIT_REQUEST_ID_BITS + 1)), {}),
        (("tool", True), {}),
        (("tool", "request"),
         {"instance_id": "x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)}),
        (("tool", "request"),
         {"error": "x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)}),
        (("tool", "request"),
         {"paths": ["x"] * (audit_module.MAX_AUDIT_PATHS + 1)}),
        (("tool", "request"),
         {"paths": ["x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)]}),
    ]
    for args, kwargs in cases:
        with pytest.raises(ValueError):
            log.record(*args, ok=True, duration_ms=1.0, **kwargs)
    assert list((tmp_path / "logs").iterdir()) == []


def test_created_directories_and_file_ignore_restrictive_umask(tmp_path):
    logs = tmp_path / "runtime" / "logs"
    previous_umask = os.umask(0o777)
    try:
        log = AuditLog(logs)
        log.record("tool", "request", ok=True, duration_ms=1.0)
    finally:
        os.umask(previous_umask)
    path = next(logs.glob("server-*.jsonl"))
    assert stat.S_IMODE(logs.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(logs.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_two_records_two_lines(tmp_path):
    log = AuditLog(tmp_path / "logs")
    log.record("a", "r1", ok=True, duration_ms=1.0)
    log.record("b", "r2", ok=False, duration_ms=2.0, error="BRIDGE_UNAVAILABLE")
    f = next((tmp_path / "logs").glob("server-*.jsonl"))
    lines = [json.loads(x) for x in f.read_text().splitlines()]
    assert [r["tool"] for r in lines] == ["a", "b"]
    assert lines[1]["error"] == "BRIDGE_UNAVAILABLE"


def test_rejects_wide_runtime_root_without_chmod(tmp_path):
    root = tmp_path / "wide-runtime"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(PermissionError, match="private directory"):
        AuditLog(root / "logs")
    assert stat.S_IMODE(root.stat().st_mode) == 0o755


def test_rejects_preexisting_wide_audit_file(tmp_path):
    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    path.write_text("foreign\n")
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert path.read_text() == "foreign\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_fifo_audit_file_never_blocks(tmp_path):
    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    os.mkfifo(path, mode=0o600)
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)


def test_symlink_audit_file_is_preserved(tmp_path):
    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    target = tmp_path / "foreign.jsonl"
    target.write_text("foreign\n")
    target.chmod(0o600)
    path.symlink_to(target)
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert path.is_symlink() and target.read_text() == "foreign\n"


def test_concurrent_first_initialization_is_race_safe_with_restrictive_umask(
        tmp_path, monkeypatch):
    import server.core.audit as audit_module

    logs = tmp_path / "first-logs"
    start = threading.Barrier(16)
    chmod_entered = threading.Event()
    release_chmod = threading.Event()
    errors = []
    real_chmod = audit_module.os.chmod

    def delayed_first_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if Path(path) == logs and not chmod_entered.is_set():
            chmod_entered.set()
            assert release_chmod.wait(1.0)
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    monkeypatch.setattr(audit_module.os, "chmod", delayed_first_chmod)

    def initialize():
        try:
            start.wait()
            AuditLog(logs)
        except BaseException as exc:
            errors.append(exc)

    previous_umask = os.umask(0o777)
    try:
        workers = [threading.Thread(target=initialize) for _ in range(16)]
        for worker in workers:
            worker.start()
        assert chmod_entered.wait(1.0)
        time.sleep(0.02)
        release_chmod.set()
        for worker in workers:
            worker.join(timeout=2.0)
    finally:
        release_chmod.set()
        os.umask(previous_umask)
    assert all(not worker.is_alive() for worker in workers)
    assert errors == []


def test_concurrent_first_file_creation_waits_for_fchmod(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    logs = tmp_path / "logs"
    first, second = AuditLog(logs), AuditLog(logs)
    fchmod_entered = threading.Event()
    release_fchmod = threading.Event()
    errors = []
    real_fchmod = audit_module.os.fchmod

    def delayed_first_fchmod(fd, mode):
        if mode == 0o600 and not fchmod_entered.is_set():
            fchmod_entered.set()
            assert release_fchmod.wait(1.0)
        return real_fchmod(fd, mode)

    monkeypatch.setattr(audit_module.os, "fchmod", delayed_first_fchmod)

    def record(log, request_id):
        try:
            log.record("tool", request_id, ok=True, duration_ms=1.0)
        except BaseException as exc:
            errors.append(exc)

    previous_umask = os.umask(0o777)
    try:
        worker_a = threading.Thread(target=record, args=(first, "a"))
        worker_a.start()
        assert fchmod_entered.wait(1.0)
        worker_b = threading.Thread(target=record, args=(second, "b"))
        worker_b.start()
        time.sleep(0.02)
        release_fchmod.set()
        worker_a.join(timeout=2.0)
        worker_b.join(timeout=2.0)
    finally:
        release_fchmod.set()
        os.umask(previous_umask)
    assert not worker_a.is_alive() and not worker_b.is_alive()
    assert errors == []
    path = next(logs.glob("server-*.jsonl"))
    assert len(path.read_text().splitlines()) == 2


def test_record_rejects_replaced_log_directory(tmp_path):
    logs = tmp_path / "logs"
    log = AuditLog(logs)
    original = tmp_path / "logs-original"
    logs.rename(original)
    logs.mkdir(mode=0o700)
    logs.chmod(0o700)
    try:
        with pytest.raises(PermissionError, match="private directory"):
            log.record("tool", "request", ok=True, duration_ms=1.0)
        assert list(logs.iterdir()) == []
    finally:
        logs.rmdir()
        original.rmdir()


def test_request_deadline_bounds_external_file_lock(tmp_path):
    log = AuditLog(tmp_path / "logs")
    log.record("first", "request-1", ok=True, duration_ms=1.0)
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_file_lock,
                             args=(str(path), ready, release))
    holder.start()
    assert ready.wait(2.0)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match="audit log lock timeout"):
            log.record("second", "request-2", ok=True, duration_ms=1.0,
                       deadline=started + 0.05)
        assert time.monotonic() - started < 0.3
    finally:
        release.set()
        holder.join(timeout=2.0)
    assert holder.exitcode == 0


def test_request_deadline_is_checked_between_serialization_steps(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    log = AuditLog(tmp_path / "logs")
    real_dumps = audit_module.json.dumps
    calls = []

    def slow_dumps(*args, **kwargs):
        calls.append(True)
        time.sleep(0.03)
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(audit_module.json, "dumps", slow_dumps)
    with pytest.raises(TimeoutError, match="audit deadline expired"):
        log.record("tool", "request", ok=True, duration_ms=1.0,
                   deadline=time.monotonic() + 0.01)
    assert len(calls) == 1
    assert list((tmp_path / "logs").iterdir()) == []


@pytest.mark.parametrize("slow_phase", ["write", "flush", "close"])
def test_request_deadline_is_checked_after_file_io(tmp_path, monkeypatch, slow_phase):
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen

    class SlowWriter:
        def __init__(self, fd, mode, encoding):
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            if slow_phase == "flush":
                time.sleep(0.03)
                self._inner.flush()
            if slow_phase == "close":
                time.sleep(0.03)
            self._inner.close()

        def write(self, value):
            if slow_phase == "write":
                time.sleep(0.03)
            return self._inner.write(value)

    monkeypatch.setattr(audit_module.os, "fdopen", SlowWriter)
    log = AuditLog(tmp_path / "logs")
    with pytest.raises(TimeoutError, match="audit deadline expired"):
        log.record("tool", "request", ok=True, duration_ms=1.0,
                   deadline=time.monotonic() + 0.01)


def test_fdopen_close_failure_does_not_close_reused_foreign_fd(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen
    foreign_path = tmp_path / "foreign.txt"
    foreign_path.write_bytes(b"")
    state = {"fd": None}

    class CloseThenReuse:
        def __init__(self, fd, mode, encoding):
            self._fd = fd
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def write(self, value):
            return self._inner.write(value)

        def __exit__(self, *_args):
            self._inner.close()
            replacement = os.open(foreign_path, os.O_WRONLY | os.O_APPEND)
            if replacement != self._fd:
                os.dup2(replacement, self._fd)
                os.close(replacement)
            state["fd"] = self._fd
            raise OSError("injected close failure")

    monkeypatch.setattr(audit_module.os, "fdopen", CloseThenReuse)
    log = AuditLog(tmp_path / "logs")
    with pytest.raises(OSError, match="close failure"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert state["fd"] is not None
    try:
        os.write(state["fd"], b"foreign")
    finally:
        os.close(state["fd"])


def test_concurrent_records_remain_complete_jsonl_lines(tmp_path, monkeypatch):
    """Force each TextIO write into two syscalls to expose record interleaving."""
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen

    class SplitWriter:
        def __init__(self, fd, mode, encoding):
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._inner.close()

        def write(self, value):
            midpoint = len(value) // 2
            self._inner.write(value[:midpoint])
            self._inner.flush()
            time.sleep(0.005)
            self._inner.write(value[midpoint:])

    monkeypatch.setattr(audit_module.os, "fdopen", SplitWriter)
    log = AuditLog(tmp_path / "logs")
    start = threading.Barrier(12)

    def record(index):
        start.wait()
        log.record(f"tool-{index}", f"request-{index}", ok=True, duration_ms=1.0)

    workers = [threading.Thread(target=record, args=(index,)) for index in range(12)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=2.0)

    assert all(not worker.is_alive() for worker in workers)
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert {row["tool"] for row in rows} == {f"tool-{index}" for index in range(12)}

    # Separate MCP host processes have separate AuditLog/thread locks, so the same
    # split-write attack must also be serialized by the file lock.
    process_logs = tmp_path / "process-logs"
    context = multiprocessing.get_context("spawn")
    process_start = context.Barrier(8)
    processes = [context.Process(target=_record_split_in_process,
                                 args=(str(process_logs), index, process_start))
                 for index in range(8)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=3.0)

    assert all(process.exitcode == 0 for process in processes)
    process_path = next(process_logs.glob("server-*.jsonl"))
    process_rows = [json.loads(line) for line in process_path.read_text().splitlines()]
    assert {row["tool"] for row in process_rows} == {
        f"process-tool-{index}" for index in range(8)
    }
```

```python
# tests/unit/test_versions.py
from server.core import versions
from server.core.capabilities import describe


def test_baseline_pinned():
    assert versions.BASELINE == {"version": "5.2.0", "platform": "macos-arm64"}


def test_check_matrix():
    assert versions.check("5.2.0") == (True, None)
    ok, warn = versions.check("5.2.3")
    assert ok is False and "5.2.3" in warn and "5.2.0" in warn
    ok, warn = versions.check("4.5.3")
    assert ok is False and "4.5.3" in warn and "5.2" in warn
    ok, warn = versions.check("6.0.0")
    assert ok is False and warn is not None


def test_gate_write_matrix():
    assert versions.gate_write("5.2.0") is None
    assert versions.gate_write("5.2.1") == "UNSUPPORTED_BLENDER_VERSION"
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

- [ ] **Step 2: 跑测试确认失败** → `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_audit.py tests/unit/test_versions.py -q`

- [ ] **Step 3: 实现**

```python
# server/core/audit.py
"""JSONL 审计。spec §5.2：参数只记摘要；transaction_id/paths 为 Phase 1 占位。

小参数保持 canonical JSON SHA-256；超过 64 KiB、过深或不可编码的参数只记
固定 sentinel 摘要。日志字段有界且 fail-closed，避免审计本身成为资源逃逸点。
"""
from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import math
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any, cast

AUDIT_LOCK_TIMEOUT = 1.0
PRIVATE_INIT_TIMEOUT = 0.1
MAX_AUDIT_PARAMS_BYTES = 64 * 1024
MAX_AUDIT_PARAMS_DEPTH = 64
MAX_AUDIT_PARAMS_ITEMS = 16 * 1024
MAX_AUDIT_FIELD_BYTES = 4096
MAX_AUDIT_REQUEST_ID_BITS = 4096
MAX_AUDIT_PATHS = 32
MAX_AUDIT_LINE_BYTES = 128 * 1024
_PARAMS_TRUNCATED_SENTINEL = b"\x00audit-params-truncated-v1\x00"
_PARAMS_UNENCODABLE_SENTINEL = b"\x00audit-params-unencodable-v1\x00"
PARAMS_TRUNCATED_DIGEST = hashlib.sha256(
    _PARAMS_TRUNCATED_SENTINEL).hexdigest()[:16]
PARAMS_UNENCODABLE_DIGEST = hashlib.sha256(
    _PARAMS_UNENCODABLE_SENTINEL).hexdigest()[:16]


class _ParamsTruncated(Exception):
    pass


class _ParamsUnencodable(Exception):
    pass


def _wait_private_directory(path: Path) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: tuple[int, int] | None = None
    while True:
        st = path.lstat()
        identity = st.st_dev, st.st_ino
        mode = stat.S_IMODE(st.st_mode)
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            return st
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)


def _wait_private_file(name: str, dir_fd: int, path: Path,
                       request_deadline: float | None = None) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    if request_deadline is not None:
        deadline = min(deadline, request_deadline)
    expected: tuple[int, int] | None = None
    while True:
        st = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        identity = st.st_dev, st.st_ino
        mode = stat.S_IMODE(st.st_mode)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o600 or (expected is not None and identity != expected)):
            raise PermissionError(f"private audit file required: {path}")
        if mode == 0o600:
            return st
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private audit file required: {path}")
        time.sleep(0.005)


def _acquire_file_lock(fd: int, request_deadline: float | None = None) -> None:
    deadline = time.monotonic() + AUDIT_LOCK_TIMEOUT
    if request_deadline is not None:
        deadline = min(deadline, request_deadline)
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError("audit log lock timeout")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as exc:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("audit log lock timeout") from exc
            time.sleep(min(0.01, remaining))


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("audit deadline expired")


def _require_text(name: str, value: object, deadline: float | None) -> None:
    _check_deadline(deadline)
    if type(value) is not str or len(value) > MAX_AUDIT_FIELD_BYTES:
        raise ValueError(f"invalid or oversized audit {name}")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"invalid or oversized audit {name}") from exc
    _check_deadline(deadline)
    if len(encoded) > MAX_AUDIT_FIELD_BYTES:
        raise ValueError(f"invalid or oversized audit {name}")


def _check_params_shape(value: object, deadline: float | None) -> None:
    """Bound traversal before JSONEncoder sorts keys or walks a deep graph."""
    active: set[int] = set()
    items = 0

    def visit(current: object, depth: int) -> None:
        nonlocal items
        _check_deadline(deadline)
        if depth > MAX_AUDIT_PARAMS_DEPTH:
            raise _ParamsUnencodable
        if type(current) is dict:
            mapping = cast(dict[object, object], current)
            if id(mapping) in active:
                raise _ParamsUnencodable
            items += len(mapping)
            if items > MAX_AUDIT_PARAMS_ITEMS:
                raise _ParamsTruncated
            active.add(id(mapping))
            try:
                for key, child in mapping.items():
                    if type(key) is not str:
                        raise _ParamsUnencodable
                    if len(key) > MAX_AUDIT_PARAMS_BYTES:
                        raise _ParamsTruncated
                    visit(child, depth + 1)
            finally:
                active.discard(id(mapping))
        elif type(current) in (list, tuple):
            sequence = cast(list[object] | tuple[object, ...], current)
            if id(sequence) in active:
                raise _ParamsUnencodable
            items += len(sequence)
            if items > MAX_AUDIT_PARAMS_ITEMS:
                raise _ParamsTruncated
            active.add(id(sequence))
            try:
                for child in sequence:
                    visit(child, depth + 1)
            finally:
                active.discard(id(sequence))
        elif type(current) is str:
            if len(current) > MAX_AUDIT_PARAMS_BYTES:
                raise _ParamsTruncated
        elif type(current) is int:
            if current.bit_length() > MAX_AUDIT_PARAMS_BYTES * 3:
                raise _ParamsTruncated
        elif current is not None and type(current) not in (bool, float):
            raise _ParamsUnencodable

    visit(value, 0)


def _params_digest(params: dict[str, Any] | None,
                   deadline: float | None) -> str:
    """Hash canonical JSON incrementally; oversized/invalid values use fixed sentinels."""
    value = {} if params is None else params
    try:
        _check_params_shape(value, deadline)
        digest = hashlib.sha256()
        encoded_bytes = 0
        encoder = json.JSONEncoder(
            ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        for piece in encoder.iterencode(value):
            _check_deadline(deadline)
            if len(piece) > MAX_AUDIT_PARAMS_BYTES - encoded_bytes:
                raise _ParamsTruncated
            encoded = piece.encode("utf-8")
            if encoded_bytes + len(encoded) > MAX_AUDIT_PARAMS_BYTES:
                raise _ParamsTruncated
            digest.update(encoded)
            encoded_bytes += len(encoded)
            _check_deadline(deadline)
    except _ParamsTruncated:
        return PARAMS_TRUNCATED_DIGEST
    except (_ParamsUnencodable, OverflowError, RecursionError, RuntimeError,
            TypeError, UnicodeEncodeError, ValueError):
        return PARAMS_UNENCODABLE_DIGEST
    return digest.hexdigest()[:16]


class AuditLog:
    def __init__(self, logs_dir: Path) -> None:
        self._dir = logs_dir
        self._write_lock = threading.Lock()
        for path in (logs_dir.parent, logs_dir):
            created = False
            try:
                path.mkdir(mode=0o700, parents=True)
            except FileExistsError:
                pass
            else:
                created = True
            if created:
                os.chmod(path, 0o700, follow_symlinks=False)
            st = _wait_private_directory(path)
        self._dir_identity = st.st_dev, st.st_ino

    def record(self, tool: str, request_id: str | int, ok: bool, duration_ms: float,
               instance_id: str | None = None, params: dict[str, Any] | None = None,
               error: str | None = None, paths: list[str] | None = None,
               transaction_id: None = None, deadline: float | None = None) -> None:
        _check_deadline(deadline)
        _require_text("tool", tool, deadline)
        if type(request_id) is str:
            _require_text("request_id", request_id, deadline)
        elif type(request_id) is not int \
                or request_id.bit_length() > MAX_AUDIT_REQUEST_ID_BITS:
            raise ValueError("invalid or oversized audit request_id")
        if instance_id is not None:
            _require_text("instance_id", instance_id, deadline)
        if error is not None:
            _require_text("error", error, deadline)
        if type(ok) is not bool or transaction_id is not None:
            raise ValueError("invalid audit scalar field")
        if paths is None:
            safe_paths: list[str] = []
        elif type(paths) is not list or len(paths) > MAX_AUDIT_PATHS:
            raise ValueError("invalid or oversized audit paths")
        else:
            safe_paths = list(paths)
            for item in safe_paths:
                _require_text("path", item, deadline)
        if (type(duration_ms) not in (int, float)
                or not math.isfinite(duration_ms)):
            raise ValueError("invalid audit duration_ms")
        rounded_duration = round(duration_ms, 3)
        _check_deadline(deadline)
        now = datetime.datetime.now(datetime.UTC)
        digest = _params_digest(params, deadline)
        _check_deadline(deadline)
        row = {"ts": now.isoformat(timespec="milliseconds"), "request_id": request_id,
               "tool": tool, "instance_id": instance_id, "transaction_id": transaction_id,
               "params_digest": digest, "ok": ok, "duration_ms": rounded_duration,
               "paths": safe_paths, "error": error}
        path = self._dir / f"server-{now:%Y-%m-%d}.jsonl"
        line = json.dumps(row, ensure_ascii=False) + "\n"
        _check_deadline(deadline)
        try:
            line_bytes = len(line.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ValueError("invalid audit row encoding") from exc
        if line_bytes > MAX_AUDIT_LINE_BYTES:
            raise ValueError("audit row exceeds size limit")
        _check_deadline(deadline)
        # Middleware calls may run concurrently. O_APPEND protects each kernel write's
        # offset, but TextIOWrapper is not an API-level guarantee that one logical JSONL
        # record becomes exactly one write(2); serialize records within this logger.
        lock_timeout = AUDIT_LOCK_TIMEOUT
        if deadline is not None:
            lock_timeout = min(lock_timeout, max(0.0, deadline - time.monotonic()))
        if not self._write_lock.acquire(timeout=lock_timeout):
            raise TimeoutError("audit thread lock timeout")
        try:
            dir_fd: int | None = None
            fd: int | None = None
            try:
                _check_deadline(deadline)
                dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
                dir_fd = os.open(self._dir, dir_flags)
                _check_deadline(deadline)
                directory = os.fstat(dir_fd)
                if (not stat.S_ISDIR(directory.st_mode)
                        or directory.st_uid != os.geteuid()
                        or stat.S_IMODE(directory.st_mode) != 0o700
                        or (directory.st_dev, directory.st_ino) != self._dir_identity):
                    raise PermissionError(f"private directory required: {self._dir}")
                flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
                created = True
                expected: tuple[int, int] | None = None
                try:
                    _check_deadline(deadline)
                    fd = os.open(path.name, flags | os.O_CREAT | os.O_EXCL, 0o600,
                                 dir_fd=dir_fd)
                except FileExistsError:
                    created = False
                    existing = _wait_private_file(path.name, dir_fd, path, deadline)
                    expected = existing.st_dev, existing.st_ino
                    _check_deadline(deadline)
                    fd = os.open(path.name, flags, dir_fd=dir_fd)
                # More than one Codex/MCP host process may share the runtime root.
                # Bounded advisory flock keeps records intact without letting an
                # external lock holder hang the MCP middleware forever.
                if created:
                    os.fchmod(fd, 0o600)
                _acquire_file_lock(fd, deadline)
                _check_deadline(deadline)
                st = os.fstat(fd)
                if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                        or stat.S_IMODE(st.st_mode) != 0o600
                        or (expected is not None
                            and (st.st_dev, st.st_ino) != expected)):
                    raise PermissionError(f"private audit file required: {path}")
                stream = os.fdopen(fd, "a", encoding="utf-8")
                fd = None  # fdopen owns the descriptor from this point onward
                with stream as f:
                    _check_deadline(deadline)
                    f.write(line)
                # Regular-file I/O cannot be preempted once inside the kernel, but a
                # slow write/flush/close must not be reported as an in-budget audit.
                _check_deadline(deadline)
            except BaseException:
                raise
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:  # fdopen may already own/close it
                        pass
                if dir_fd is not None:
                    os.close(dir_fd)
        finally:
            self._write_lock.release()
```

```python
# server/core/versions.py
"""版本门禁。spec §4.4、§8.3：基线 5.2.0；Phase 0 只读放行 + 警告。"""
from __future__ import annotations

BASELINE: dict[str, str] = {"version": "5.2.0", "platform": "macos-arm64"}


def check(blender_version: str) -> tuple[bool, str | None]:
    baseline = BASELINE["version"]
    if blender_version == baseline:
        return True, None
    return False, (f"Blender {blender_version} 不是本系统钉定基线（{baseline} LTS）；"
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

- [ ] **Step 4: 跑测试确认通过** → 24 passed（audit 20 + versions 4；v8）

- [ ] **Step 5: Commit**

```bash
git add server/core/audit.py server/core/versions.py server/core/capabilities.py \
        tests/unit/test_audit.py tests/unit/test_versions.py
git commit -m "feat(server-core): 审计 JSONL、版本门禁、capabilities 静态应答"
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
import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest
from bridge.core.lifecycle import BridgeSession
from protocol import envelope, framing
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


@pytest.mark.parametrize("timeout", [0.0, -1.0])
def test_nonpositive_budget_times_out_before_connect(tmp_path, timeout):
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-zero-"))
    sock_path = socket_dir / "unused.sock"
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(sock_path))
    server.listen(1)
    started = time.monotonic()
    try:
        client = BridgeClient({"socket_path": str(sock_path), "token": "t"})
        with pytest.raises(BridgeError) as exc:
            client.call("ping", timeout=timeout)
        assert exc.value.code == envelope.BRIDGE_TIMEOUT
        assert time.monotonic() - started < 0.1
    finally:
        server.close()
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


def test_error_frame_maps_to_bridge_error(live):
    c = BridgeClient(_session_dict(live))
    with pytest.raises(BridgeError) as ei:
        c.call("no_such_method")
    assert ei.value.code == "UNKNOWN_METHOD"


def test_slow_drip_respects_total_deadline():
    # audit F-02：对端每 20ms 滴 1 字节。逐次 settimeout 会被无限续命；
    # 总 deadline 必须在 ~0.3s 止损（滴完整帧需 ~1.2s）
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-"))
    sock_path = socket_dir / "drip.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        while not buf.feed(conn.recv(65536)):
            pass
        resp = envelope.ok_frame("x", {"pong": True})
        try:
            for i in range(len(resp)):
                conn.send(resp[i:i + 1])
                time.sleep(0.02)
        except OSError:
            pass
        conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    c = BridgeClient({"socket_path": str(sock_path), "token": "t"})
    t0 = time.monotonic()
    with pytest.raises(BridgeError) as ei:
        c.call("ping", timeout=0.3)
    elapsed = time.monotonic() - t0
    try:
        assert ei.value.code == "BRIDGE_TIMEOUT"
        assert elapsed < 1.0
    finally:
        srv.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


def test_response_decode_cannot_escape_total_deadline(live, monkeypatch):
    import server.core.bridge_client as client_module

    real_decode = client_module.envelope.decode_response

    def slow_decode(payload):
        time.sleep(0.25)
        return real_decode(payload)

    monkeypatch.setattr(client_module.envelope, "decode_response", slow_decode)
    started = time.monotonic()
    with pytest.raises(BridgeError) as exc:
        BridgeClient(_session_dict(live)).call("ping", timeout=0.2)
    assert exc.value.code == envelope.BRIDGE_TIMEOUT
    assert time.monotonic() - started < 0.6


MISSING_VERSION = object()


@pytest.mark.parametrize("version,id_matches,expected", [
    (envelope.ENVELOPE_VERSION + 1, True, envelope.ENVELOPE_VERSION_MISMATCH),
    (True, True, envelope.BRIDGE_UNAVAILABLE),
    ("1", True, envelope.BRIDGE_UNAVAILABLE),
    (MISSING_VERSION, True, envelope.BRIDGE_UNAVAILABLE),
    (envelope.ENVELOPE_VERSION, False, envelope.BRIDGE_UNAVAILABLE),
])
def test_response_version_and_id_must_match_request(version, id_matches, expected):
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-"))
    sock_path = socket_dir / "mismatch.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        frames = []
        while not frames:
            frames = buf.feed(conn.recv(65536))
        req = envelope.decode_request(frames[0])
        body = {"id": req.id if id_matches else "wrong-id", "ok": True, "result": {}}
        if version is not MISSING_VERSION:
            body["v"] = version
        conn.sendall(framing.encode_frame(json.dumps(body).encode()))
        conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        client = BridgeClient({"socket_path": str(sock_path), "token": "t"})
        with pytest.raises(BridgeError) as ei:
            client.call("ping")
        assert ei.value.code == expected
        assert ei.value.retryable is (expected == envelope.BRIDGE_UNAVAILABLE)
    finally:
        srv.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


@pytest.mark.parametrize("response_fields", [
    {"ok": "false", "result": {}},
    {"ok": False, "error": "not-an-object"},
    {"ok": True, "result": []},
])
def test_malformed_response_shape_maps_to_bridge_unavailable(response_fields):
    socket_dir = Path(tempfile.mkdtemp(prefix="bcx-"))
    sock_path = socket_dir / "malformed.sock"
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        frames = []
        while not frames:
            frames = buf.feed(conn.recv(65536))
        req = envelope.decode_request(frames[0])
        body = {"v": envelope.ENVELOPE_VERSION, "id": req.id, **response_fields}
        conn.sendall(framing.encode_frame(json.dumps(body).encode()))
        conn.close()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        client = BridgeClient({"socket_path": str(sock_path), "token": "t"})
        with pytest.raises(BridgeError) as exc:
            client.call("ping")
        assert exc.value.code == envelope.BRIDGE_UNAVAILABLE
        assert exc.value.retryable is True
    finally:
        srv.close()
        worker.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()
```

- [ ] **Step 2: 跑测试确认失败** → `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_bridge_client.py -q`

- [ ] **Step 3: 实现**

```python
# server/core/bridge_client.py
"""UDS 客户端。spec §5 错误映射表；**全调用总 deadline**（audit F-02：逐次
settimeout 每收 1 字节就重置窗口，慢滴流响应可无限续命——实测 0.3s 超时被拖到 1.4s）。"""
from __future__ import annotations

import socket
import time
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
        if timeout is None:
            timeout = envelope.METHOD_TIMEOUTS.get(method, 2.0)
        deadline = time.monotonic() + timeout

        def remaining() -> float:
            left = deadline - time.monotonic()
            if left <= 0:
                raise BridgeError(envelope.BRIDGE_TIMEOUT, method, retryable=True)
            return left

        req = envelope.Request.new(self._token, method, params or {})
        try:
            payload = envelope.encode_request(req)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(remaining())
                sock.connect(self._socket_path)
                sock.settimeout(remaining())
                sock.sendall(payload)
                buf = framing.FrameBuffer()
                while True:
                    sock.settimeout(remaining())     # 剩余预算，绝不重置整窗
                    data = sock.recv(65536)
                    if not data:      # 对端关闭：认证失败或会话关闭（§5）
                        raise BridgeError(envelope.BRIDGE_UNAVAILABLE,
                                          "connection closed by bridge", retryable=True)
                    frames = buf.feed(data)
                    if frames:
                        resp = envelope.decode_response(frames[0])
                        remaining()  # response parsing is inside the total deadline
                        break
        except BridgeError:
            raise
        except TimeoutError as e:                    # connect/send/recv 任一超时
            raise BridgeError(envelope.BRIDGE_TIMEOUT, method, retryable=True) from e
        except (OSError, framing.FrameError, ValueError) as e:  # ValueError 含畸形响应
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, str(type(e).__name__),
                              retryable=True) from e
        # bool is an int subclass: without the exact-type guard, JSON `true` would
        # compare equal to envelope version 1 and bypass version validation.
        if type(resp.get("v")) is not int:
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE,
                              "malformed response version", retryable=True)
        if resp["v"] != envelope.ENVELOPE_VERSION:
            raise BridgeError(
                envelope.ENVELOPE_VERSION_MISMATCH,
                f"response envelope v{resp.get('v')} != v{envelope.ENVELOPE_VERSION}")
        if resp.get("id") != req.id:
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "response envelope mismatch",
                              retryable=True)
        if type(resp.get("ok")) is not bool:
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed response status",
                              retryable=True)
        if not resp["ok"]:
            err = resp.get("error", {})
            if not isinstance(err, dict) or not isinstance(err.get("code"), str) \
                    or not isinstance(err.get("message"), str) \
                    or type(err.get("retryable")) is not bool:
                raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed error response",
                                  retryable=True)
            raise BridgeError(err["code"], err["message"], err["retryable"])
        result = resp.get("result")
        if not isinstance(result, dict):
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed result",
                              retryable=True)
        remaining()  # response validation is inside the total deadline
        return result
```

- [ ] **Step 4: 跑测试确认通过** → 16 passed（历史 fixture；全量 v7 计数以 provenance 为准）

- [ ] **Step 5: Commit**

```bash
git add server/core/bridge_client.py tests/unit/test_bridge_client.py
git commit -m "feat(server-core): UDS 客户端与错误码映射"
```

---

### Task 11: server/core/discovery.py

**Files:**
- Create: `server/core/discovery.py`
- Test: `tests/unit/test_discovery.py`

**Interfaces:**
- Consumes: `config.run_dir()`、`BridgeClient`、`versions.check`；`session.json` 由 Discovery 以同一 fd 做 no-follow / non-blocking / fstat / bounded-read，不复用按路径二次打开的 helper
- Produces:
  - `@dataclass Instance`: `session: dict`、`state: str`（`"connected" | "disconnected"`）、`blender_supported: bool`、`version_warning: str | None`、`client: BridgeClient | None`（连上时非 None）
  - `class Discovery(run_dir: Path, ttl: float = 1.0, clock=time.monotonic)`
    - `.instances(force: bool = False, deadline: float | None = None) -> list[Instance]`——1 秒缓存（§4.3）；绝对 deadline 可由 status 贯穿传入
    - `.find(instance_id: str) -> Instance | None`——精确匹配
    - `.invalidate(deadline: float | None = None) -> bool`——Bridge 失联后投递一个有界、非阻塞的失效通知，使下一次调用重扫；参数保留用于调用点 deadline 对称性，但不等待 discovery 扫描锁
    - 目录窗口每轮最多 256 项并保留 scandir cursor；截断时 `partial=true` 且下一轮从 cursor 继续，避免第 257 项以后永久饿死
    - 清理规则（§5.1）：`session.json` 可读 → 预筛 `os.kill(pid,0)` 失败 **且** 连接失败 → 删会话目录；`session.json` 缺失/损坏 → 目录 mtime 距今 > 60 s 才删；握手 `instance_id` 不一致 → 视为 stale 不计入；`envelope_version` 不一致 → 计入但 `state="disconnected"`、`version_warning` 说明版本不匹配、`client=None`（§4.3）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_discovery.py
import gc
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

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


def _make_run(root: Path) -> Path:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    run = root / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    run.chmod(0o700)
    return run


def _make_session_dir(run: Path, name: str) -> Path:
    directory = run / name
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def _write_private(path: Path, contents: str) -> None:
    try:
        data = json.loads(contents)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and data.get("socket_path") == "/nonexistent.sock":
        data["socket_path"] = str(path.parent / "bridge.sock")
    required = {"instance_id", "token", "pid", "socket_path",
                "blender_version", "bridge_version", "envelope_version"}
    if isinstance(data, dict) and required <= data.keys():
        socket_path = Path(data["socket_path"])
        data.setdefault("socket_external", socket_path.parent != path.parent)
        try:
            directory_stat = socket_path.parent.stat()
        except OSError:
            directory_stat = None
        try:
            socket_stat = socket_path.lstat()
        except OSError:
            socket_stat = None
        data.setdefault("socket_dev", 0 if socket_stat is None else socket_stat.st_dev)
        data.setdefault("socket_ino", 0 if socket_stat is None else socket_stat.st_ino)
        data.setdefault(
            "socket_dir_dev", 0 if directory_stat is None else directory_stat.st_dev)
        data.setdefault(
            "socket_dir_ino", 0 if directory_stat is None else directory_stat.st_ino)
        contents = json.dumps(data)
    path.write_text(contents)
    path.chmod(0o600)


def _reuse_fd_for_path(fd: int, path: Path) -> int:
    source_fd = os.open(path, os.O_RDONLY)
    if source_fd != fd:
        os.dup2(source_fd, fd)
        os.close(source_fd)
    return fd


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


def test_created_runtime_and_run_ignore_restrictive_umask(tmp_path):
    root = tmp_path / "runtime"
    previous_umask = os.umask(0o777)
    try:
        Discovery(root / "run")
    finally:
        os.umask(previous_umask)
    assert (root.stat().st_mode & 0o777) == 0o700
    assert ((root / "run").stat().st_mode & 0o777) == 0o700


def test_concurrent_discovery_waits_for_restrictive_umask_chmod(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / "runtime"
    chmod_entered = threading.Event()
    release_chmod = threading.Event()
    discoveries = []
    errors = []
    real_chmod = disc_mod.os.chmod

    def delayed_root_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if Path(path) == root and dir_fd is None and not chmod_entered.is_set():
            chmod_entered.set()
            assert release_chmod.wait(1.0)
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    monkeypatch.setattr(disc_mod.os, "chmod", delayed_root_chmod)

    def create() -> None:
        try:
            discoveries.append(Discovery(root / "run"))
        except BaseException as exc:
            errors.append(exc)

    previous_umask = os.umask(0o777)
    try:
        worker_a = threading.Thread(target=create)
        worker_a.start()
        assert chmod_entered.wait(1.0)
        worker_b = threading.Thread(target=create)
        worker_b.start()
        time.sleep(0.02)
        release_chmod.set()
        worker_a.join(timeout=2.0)
        worker_b.join(timeout=2.0)
    finally:
        release_chmod.set()
        os.umask(previous_umask)
    assert not worker_a.is_alive() and not worker_b.is_alive()
    assert errors == [] and len(discoveries) == 2


def test_rejects_preexisting_wide_run_without_chmod(tmp_path):
    tmp_path.chmod(0o700)
    run = tmp_path / "run"
    run.mkdir(mode=0o755)
    run.chmod(0o755)
    with pytest.raises(PermissionError, match="private directory"):
        Discovery(run)
    assert (run.stat().st_mode & 0o777) == 0o755


def test_replaced_run_path_is_not_scanned(tmp_path):
    run = _make_run(tmp_path)
    discovery = Discovery(run)
    original = tmp_path / "run-original"
    outside = tmp_path / "outside"
    run.rename(original)
    outside.mkdir(mode=0o700)
    outside.chmod(0o700)
    outside_run = _make_session_dir(outside, f"gui-{os.getpid()}-deadbeef")
    _write_private(outside_run / "session.json", json.dumps({
        "instance_id": outside_run.name, "token": "outside", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    run.symlink_to(outside, target_is_directory=True)
    assert discovery.instances(force=True) == []
    assert discovery.last_scan.reasons == ["run boundary"]


def test_scandir_error_is_reported_as_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    discovery = disc_mod.Discovery(_make_run(tmp_path))

    def fail_scandir(_fd):
        raise OSError("injected scandir failure")

    monkeypatch.setattr(disc_mod.os, "scandir", fail_scandir)
    assert discovery.instances(force=True) == []
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count == 1
    assert discovery.last_scan.reasons == ["enumeration error"]


def test_expired_scan_deadline_performs_no_run_io(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    discovery = disc_mod.Discovery(_make_run(tmp_path))

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("expired scan attempted run I/O")

    monkeypatch.setattr(disc_mod.os, "open", forbidden_open)
    instances, stats = discovery.instances_with_stats(
        force=True, deadline=time.monotonic() - 1.0)
    assert instances == []
    assert stats.partial is True
    assert stats.reasons == ["discovery lock deadline"]


@pytest.mark.parametrize("explicit_deadline", [False, True])
def test_discovery_lock_wait_respects_absolute_deadline(
        tmp_path, monkeypatch, explicit_deadline):
    import server.core.discovery as disc_mod

    monkeypatch.setattr(disc_mod, "SCAN_DEADLINE", 0.05)
    discovery = disc_mod.Discovery(_make_run(tmp_path))
    entered = threading.Event()
    release = threading.Event()

    def hold_lock():
        with discovery._lock:
            entered.set()
            assert release.wait(1.0)

    worker = threading.Thread(target=hold_lock)
    worker.start()
    assert entered.wait(1.0)
    started = time.monotonic()
    try:
        instances, stats = discovery.instances_with_stats(
            force=True, deadline=(started + 0.05 if explicit_deadline else None))
    finally:
        release.set()
        worker.join(timeout=1.0)
    assert time.monotonic() - started < 0.5
    assert instances == []
    assert stats.partial is True
    assert stats.reasons == ["discovery lock deadline"]


def test_invalidate_is_nonblocking_while_scan_lock_is_held(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    monkeypatch.setattr(disc_mod, "SCAN_DEADLINE", 0.05)
    discovery = disc_mod.Discovery(_make_run(tmp_path))
    discovery._cache = [object()]
    discovery._cached_at = discovery._clock()
    entered = threading.Event()
    release = threading.Event()

    def hold_lock():
        with discovery._lock:
            entered.set()
            assert release.wait(1.0)

    worker = threading.Thread(target=hold_lock)
    worker.start()
    assert entered.wait(1.0)
    started = time.monotonic()
    try:
        for _ in range(10_000):
            assert discovery.invalidate(deadline=started + 0.001) is True
        assert discovery._invalidations.qsize() == 1
    finally:
        release.set()
        worker.join(timeout=1.0)
    assert time.monotonic() - started < 0.05
    scans = 0

    def fresh_scan(deadline=None):
        nonlocal scans
        scans += 1
        discovery.last_scan = disc_mod.ScanStats()
        return []

    monkeypatch.setattr(discovery, "_scan", fresh_scan)
    assert discovery.instances() == []
    assert scans == 1
    assert discovery._cache == []


def test_invalidate_during_scan_does_not_publish_stale_cache(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    discovery = disc_mod.Discovery(_make_run(tmp_path))
    entered = threading.Event()
    release = threading.Event()
    sentinel = object()

    def slow_scan(deadline=None):
        entered.set()
        assert release.wait(1.0)
        discovery.last_scan = disc_mod.ScanStats()
        return [sentinel]

    monkeypatch.setattr(discovery, "_scan", slow_scan)
    worker = threading.Thread(target=lambda: discovery.instances(force=True))
    worker.start()
    assert entered.wait(1.0)
    assert discovery.invalidate(deadline=time.monotonic() + 0.001) is True
    release.set()
    worker.join(timeout=1.0)
    assert not worker.is_alive()
    assert discovery._cache is None

    scans = 0

    def fresh_scan(deadline=None):
        nonlocal scans
        scans += 1
        discovery.last_scan = disc_mod.ScanStats()
        return []

    monkeypatch.setattr(discovery, "_scan", fresh_scan)
    assert discovery.instances() == []
    assert scans == 1


@pytest.mark.parametrize("wide_target", ["directory", "file"])
def test_rejects_wide_session_artifacts(tmp_path, wide_target):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    session_file = directory / "session.json"
    _write_private(session_file, json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    (directory if wide_target == "directory" else session_file).chmod(
        0o755 if wide_target == "directory" else 0o644)
    assert Discovery(run).instances() == []
    assert directory.exists()


@pytest.mark.parametrize("name,pid", [
    ("gui-1-nothex00", 1),
    ("gui-1-deadbeef", 2),
    ("gui-0-deadbeef", 0),
])
def test_instance_id_embeds_exact_positive_pid(tmp_path, name, pid):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, name)
    _write_private(directory / "session.json", json.dumps({
        "instance_id": name, "token": "t", "pid": pid,
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    assert Discovery(run).instances() == []
    assert directory.exists()


def test_arbitrary_external_socket_path_is_never_probed(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(directory / "session.json", json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/tmp/unrelated-bcx.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    def forbidden_client(_session):
        raise AssertionError("arbitrary socket path reached BridgeClient")

    monkeypatch.setattr(disc_mod, "BridgeClient", forbidden_client)
    assert disc_mod.Discovery(run).instances() == []


def test_dead_pid_and_connect_fail_cleans_dir(tmp_path):
    run = _make_run(tmp_path)
    dead_pid = 2 ** 22 - 3
    dead = _make_session_dir(run, f"gui-{dead_pid}-deadbeef")
    _write_private(dead / "session.json", json.dumps({
        "instance_id": dead.name, "token": "t", "pid": dead_pid,  # 不存在的 pid
        "socket_path": str(dead / "bridge.sock"), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    assert Discovery(run).instances() == []
    assert not dead.exists()                  # 双条件成立 → 清理（§5.1）


@pytest.mark.parametrize("swap_stage", ["before_cleanup", "after_cleanup_validation"])
def test_internal_socket_replacement_during_stale_cleanup_is_preserved(
        monkeypatch, swap_stage):
    # 反例：A 通过 probe 后，清理窗口内换入同路径的 B；B 不得被误删。
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="bcx-") as root:
        run = _make_run(Path(root))
        dead_pid = 2 ** 22 - 3
        dead = _make_session_dir(run, f"gui-{dead_pid}-deadbeef")
        socket_path = dead / "bridge.sock"
        original = socket.socket(socket.AF_UNIX)
        original.bind(str(socket_path))
        socket_path.chmod(0o600)
        _write_private(dead / "session.json", json.dumps({
            "instance_id": dead.name, "token": "t", "pid": dead_pid,
            "socket_path": str(socket_path), "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
        replacement = socket.socket(socket.AF_UNIX)
        swapped = False

        def swap_socket():
            nonlocal swapped
            swapped = True
            original.close()
            socket_path.unlink()
            replacement.bind(str(socket_path))
            socket_path.chmod(0o600)

        if swap_stage == "before_cleanup":
            real_state = Discovery._socket_identity_state

            def swap_after_validation(session, deadline):
                state = real_state(session, deadline)
                if state == "ok" and not swapped:
                    swap_socket()
                return state

            monkeypatch.setattr(
                Discovery, "_socket_identity_state", staticmethod(swap_after_validation))
        else:
            real_cleanup = Discovery._remove_external_socket

            def swap_after_cleanup_validation(directory, session, deadline):
                complete = real_cleanup(directory, session, deadline)
                if complete and not swapped:
                    swap_socket()
                return complete

            monkeypatch.setattr(
                Discovery, "_remove_external_socket",
                staticmethod(swap_after_cleanup_validation))
        try:
            discovery = Discovery(run)
            assert discovery.instances(force=True) == []
            assert swapped is True
            assert socket_path.exists()
            assert discovery.last_scan.partial is True
            assert "cleanup incomplete" in discovery.last_scan.reasons
        finally:
            original.close()
            replacement.close()
            socket_path.unlink(missing_ok=True)


def test_corrupt_session_respects_grace_period(tmp_path):
    run = _make_run(tmp_path)
    broken = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(broken / "session.json", "{corrupt")
    Discovery(run).instances()
    assert broken.exists()                    # mtime 新 → 60s 宽限期内不删
    old = time.time() - 120
    os.utime(broken, (old, old))
    Discovery(run).instances()
    assert not broken.exists()


def test_deeply_nested_session_json_is_isolated(tmp_path):
    run = _make_run(tmp_path)
    broken = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    session_file = broken / "session.json"
    session_file.write_text('{"x":' + "[" * 10_000 + "0" + "]" * 10_000 + "}")
    session_file.chmod(0o600)

    assert Discovery(run).instances() == []
    assert broken.exists()  # fresh malformed metadata remains inside the grace period


def test_session_instance_id_must_match_directory_name(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(directory / "session.json", json.dumps({
        "instance_id": f"gui-{os.getpid()}-feedface", "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    assert Discovery(run).instances() == []
    assert directory.exists()  # fresh malformed metadata remains inside the grace period


def test_expired_cleanup_deadline_preserves_evidence(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(directory / "session.json", "{}")
    st = directory.stat(follow_symlinks=False)
    assert Discovery._remove_session_dir(
        directory, (st.st_dev, st.st_ino), time.monotonic() - 1.0) is False
    assert (directory / "session.json").exists()


def test_cleanup_rechecks_deadline_after_child_stat(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    session_file = directory / "session.json"
    _write_private(session_file, "{}")
    identity = directory.stat().st_dev, directory.stat().st_ino
    real_stat = disc_mod.os.stat

    def slow_child_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if path == "session.json" and kwargs.get("dir_fd") is not None:
            time.sleep(0.08)
        return result

    monkeypatch.setattr(disc_mod.os, "stat", slow_child_stat)
    assert disc_mod.Discovery._remove_session_dir(
        directory, identity, time.monotonic() + 0.05) is False
    assert session_file.exists()


def test_cleanup_can_be_partial_and_preserves_unknown_children(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(directory / "session.json", "{}")
    (directory / "unknown.txt").write_text("preserve")
    st = directory.stat(follow_symlinks=False)
    assert Discovery._remove_session_dir(
        directory, (st.st_dev, st.st_ino), time.monotonic() + 1.0) is False
    assert not (directory / "session.json").exists()
    assert (directory / "unknown.txt").read_text() == "preserve"


def test_corrupt_session_incomplete_cleanup_is_reported_as_partial(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(directory / "session.json", "{}")
    (directory / "unknown.txt").write_text("preserve")
    old = time.time() - 120
    os.utime(directory, (old, old))

    discovery = Discovery(run)
    assert discovery.instances() == []
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count >= 1
    assert "cleanup incomplete" in discovery.last_scan.reasons
    assert (directory / "unknown.txt").read_text() == "preserve"


def test_external_cleanup_can_be_partial_with_unknown_child(tmp_path):
    instance_id = f"gui-{os.getpid()}-{tmp_path.stat().st_ino & 0xffffffff:08x}"
    session_dir = tmp_path / ("long-" * 30) / instance_id
    fallback = Discovery._fallback_dir(instance_id)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    unknown = fallback / "unknown.txt"
    unknown.write_text("preserve")
    directory_stat, socket_stat = fallback.stat(), socket_path.stat()
    session = {
        "socket_path": str(socket_path), "socket_external": True,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": directory_stat.st_dev,
        "socket_dir_ino": directory_stat.st_ino,
    }
    try:
        assert Discovery._remove_external_socket(
            session_dir, session, time.monotonic() + 1.0) is False
        assert not socket_path.exists()
        assert unknown.read_text() == "preserve"
        assert fallback.exists()
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)
        unknown.unlink(missing_ok=True)
        fallback.rmdir()


def test_crashed_fallback_session_cleans_external_socket(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / ("x" * 90)
    session = BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    socket_path = session.socket_path
    fallback = socket_path.parent
    session.stopped = True
    session._wake()
    session._join_io()
    session._close_all_conns()
    session._close_listener()
    monkeypatch.setattr(disc_mod.os, "kill",
                        lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()))

    assert Discovery(root / "run").instances() == []
    assert not session.session_dir.exists()
    assert not socket_path.exists()
    assert not fallback.exists()


def test_prepublication_crash_cleans_deterministic_fallback(tmp_path):
    root = tmp_path / ("y" * 90)
    run = _make_run(root)
    suffix = f"{tmp_path.stat().st_ino & 0xffffffff:08x}"
    directory = _make_session_dir(run, f"gui-99999999-{suffix}")
    fallback = Discovery._fallback_dir(directory.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    socket_path = fallback / "bridge.sock"
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(socket_path))
    sock.close()
    socket_path.chmod(0o600)
    old = time.time() - 120
    os.utime(directory, (old, old))
    os.utime(fallback, (old, old))

    assert Discovery(run).instances() == []
    assert not directory.exists()
    assert not socket_path.exists()
    assert not fallback.exists()


def test_fallback_identity_mismatch_preserves_replacement_and_session(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / ("z" * 90)
    session = BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    fallback = session.socket_path.parent
    original = fallback.with_name(fallback.name + "-original")
    session.stopped = True
    session._wake()
    session._join_io()
    session._close_all_conns()
    session._close_listener()
    monkeypatch.setattr(disc_mod.os, "kill",
                        lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()))
    fallback.rename(original)
    fallback.mkdir(mode=0o700)
    replacement = socket.socket(socket.AF_UNIX)
    replacement.bind(str(fallback / "bridge.sock"))
    replacement.close()
    try:
        assert Discovery(root / "run").instances() == []
        assert session.session_dir.exists()
        assert (fallback / "bridge.sock").exists()
    finally:
        for directory in (fallback, original, session.session_dir):
            if directory.exists():
                for child in directory.iterdir():
                    child.unlink(missing_ok=True)
                directory.rmdir()


def test_version_warning_for_non_baseline(live, tmp_path):
    s, run = live
    sj = run / s.instance_id / "session.json"
    data = json.loads(sj.read_text())
    data["blender_version"] = "4.5.3"
    sj.write_text(json.dumps(data))
    inst = Discovery(run).instances()[0]
    assert inst.blender_supported is False
    assert "4.5.3" in inst.version_warning


def test_scan_respects_total_deadline_with_hanging_candidates(tmp_path):
    # audit F-03：16 个挂起候选（listen 不 accept：连接成功但永无响应）。
    # 旧实现 8 并发 × 每探测 2s 分两批 → 实测 4.0s；总 deadline 后必须 < 3.2s
    run = _make_run(tmp_path)
    listeners: list[tuple[socket.socket, Path]] = []
    for i in range(16):
        d = _make_session_dir(run, f"gui-{os.getpid()}-{i:08x}")
        fallback = Discovery._fallback_dir(d.name)
        assert fallback is not None
        fallback.mkdir(mode=0o700)
        fallback.chmod(0o700)
        sock_path = fallback / "bridge.sock"
        hang = socket.socket(socket.AF_UNIX)
        hang.bind(str(sock_path))
        hang.listen(1)
        sock_path.chmod(0o600)
        dir_stat, socket_stat = fallback.stat(), sock_path.stat()
        listeners.append((hang, fallback))
        _write_private(d / "session.json", json.dumps({
            "instance_id": d.name, "token": "t", "pid": os.getpid(),
            "socket_path": str(sock_path), "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1,
            "socket_external": True,
            "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
            "socket_dir_dev": dir_stat.st_dev, "socket_dir_ino": dir_stat.st_ino,
        }))
    try:
        t0 = time.monotonic()
        insts = Discovery(run).instances()
        elapsed = time.monotonic() - t0
        assert elapsed < 3.2
        assert len(insts) == 16
        assert all(i.state == "disconnected" for i in insts)
        assert all((run / i.session["instance_id"]).exists() for i in insts)  # 绝不误删
    finally:
        for hang, fallback in listeners:
            hang.close()
            (fallback / "bridge.sock").unlink(missing_ok=True)
            fallback.rmdir()


def test_completed_probe_deadline_is_reported_as_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(directory / "session.json", json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    def deadline(*_args, **_kwargs):
        raise disc_mod._ProbeDeadline

    monkeypatch.setattr(disc_mod.Discovery, "_probe", deadline)
    discovery = disc_mod.Discovery(run)
    instances = discovery.instances()
    assert len(instances) == 1 and instances[0].state == "disconnected"
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count == 1
    assert discovery.last_scan.reasons == ["probe deadline"]


def test_probe_rechecks_deadline_between_socket_metadata_reads(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    socket_path = directory / "bridge.sock"
    socket_path.touch()
    socket_path.chmod(0o600)
    directory_stat, socket_stat = directory.stat(), socket_path.stat()
    session = {
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1,
        "socket_external": False,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": directory_stat.st_dev,
        "socket_dir_ino": directory_stat.st_ino,
    }
    discovery = disc_mod.Discovery(run)
    now = [0.0]
    calls = []
    real_lstat = Path.lstat

    def advancing_lstat(path):
        calls.append(path)
        result = real_lstat(path)
        now[0] = 2.0
        return result

    monkeypatch.setattr(disc_mod.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(Path, "lstat", advancing_lstat)
    with pytest.raises(disc_mod._ProbeDeadline):
        discovery._probe(session, deadline=1.0)
    assert calls == [directory]


def test_scan_phase_itself_is_inside_deadline(tmp_path, monkeypatch):
    # 真正攻击 scandir.__next__：旧 sorted(iterdir()) 会先物化 400 项（约 4s），
    # 新实现每次 next 前检查绝对 deadline，约 2.5s 止损。
    import server.core.discovery as disc_mod
    run = _make_run(tmp_path)
    for i in range(400):
        d = _make_session_dir(run, f"gui-{os.getpid()}-{i:08x}")
        _write_private(d / "session.json", json.dumps({
            "instance_id": d.name, "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
    real_scandir = os.scandir

    class SlowScandir:
        def __init__(self, path):
            self._inner = real_scandir(path)

        def __next__(self):
            time.sleep(0.010)
            return next(self._inner)

        def close(self):
            self._inner.close()

    monkeypatch.setattr(disc_mod.os, "scandir", SlowScandir)
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1000)
    t0 = time.monotonic()
    d = Discovery(run)
    d.instances()
    elapsed = time.monotonic() - t0
    assert elapsed < 3.2, f"扫描阶段逃逸预算：{elapsed:.3f}s"
    assert d.last_scan.partial and d.last_scan.skipped_count > 0


def test_oversized_session_file_skipped(tmp_path):
    run = _make_run(tmp_path)
    d = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(d / "session.json", "x" * (65 * 1024))
    assert Discovery(run).instances() == []


def test_fifo_session_file_never_blocks(tmp_path):
    run = _make_run(tmp_path)
    d = _make_session_dir(run, "gui-1-deadbeef")
    os.mkfifo(d / "session.json")
    t0 = time.monotonic()
    assert Discovery(run).instances() == []
    assert time.monotonic() - t0 < 0.5


def test_session_read_is_bound_to_opened_fd(tmp_path, monkeypatch):
    # open 后把路径换成 FIFO；实现必须继续读已打开的常规文件 fd，不能重新按路径打开。
    import server.core.discovery as disc_mod
    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    sj = d / "session.json"
    _write_private(sj, json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    real_open = os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if path == "session.json" and dir_fd is not None and not swapped:
            swapped = True
            os.replace(sj, d / "session.original")
            os.mkfifo(sj)
        return fd

    monkeypatch.setattr(disc_mod.os, "open", swapping_open)
    inst = Discovery(run).instances()
    assert swapped and len(inst) == 1 and inst[0].session["instance_id"] == d.name


def test_session_read_replacement_marks_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(d / "session.json", json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    real_read = os.read
    swapped = False

    def replace_before_read(fd, size):
        nonlocal swapped
        if not swapped:
            swapped = True
            d.rename(run / "old-session")
            d.mkdir(mode=0o700)
            d.chmod(0o700)
            raise ValueError("injected session read failure")
        return real_read(fd, size)

    monkeypatch.setattr(disc_mod.os, "read", replace_before_read)
    discovery = disc_mod.Discovery(run)
    assert discovery.instances(force=True) == []
    assert swapped
    assert discovery.last_scan.partial is True
    assert "session identity replaced" in discovery.last_scan.reasons


def test_parent_directory_swap_cannot_redirect_session_read(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    inside = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    outside.chmod(0o700)
    for directory, token in ((inside, "inside"), (outside, "outside")):
        _write_private(directory / "session.json", json.dumps({
            "instance_id": inside.name, "token": token, "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))

    real_open = os.open
    swapped = False

    def swap_after_dir_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if Path(path) == inside and dir_fd is None and not swapped:
            swapped = True
            inside.rename(run / "original-dir")
            os.symlink(outside, inside)
        return fd

    monkeypatch.setattr(disc_mod.os, "open", swap_after_dir_open)
    instances = disc_mod.Discovery(run).instances()

    assert swapped
    assert [item.session["token"] for item in instances] == ["inside"]


def test_dead_probe_cleanup_does_not_delete_replacement_directory(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    original = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(original / "session.json", json.dumps({
        "instance_id": original.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    def replace_then_report_dead(self, session, deadline):
        original.rename(run / "old-directory")
        original.mkdir()
        (original / "replacement.txt").write_text("must survive")
        return None

    monkeypatch.setattr(disc_mod.Discovery, "_probe", replace_then_report_dead)
    discovery = disc_mod.Discovery(run)
    assert discovery.instances() == []
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count >= 1
    assert "cleanup incomplete" in discovery.last_scan.reasons
    assert (original / "replacement.txt").read_text() == "must survive"


def test_valid_json_with_missing_session_fields_isolated(tmp_path):
    run = _make_run(tmp_path)
    d = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(d / "session.json", "{}")
    assert Discovery(run).instances() == []


@pytest.mark.parametrize("identity_fields", [{}, {"socket_dev": 1}])
def test_invalid_socket_identity_is_preserved_before_probe(
        tmp_path, monkeypatch, identity_fields):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    session_file = directory / "session.json"
    session_file.write_text(json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(directory / "bridge.sock"),
        "blender_version": "5.2.0", "bridge_version": "0.1.0",
        "envelope_version": 1, "socket_external": False,
        **identity_fields,
    }))
    session_file.chmod(0o600)
    old = time.time() - 120
    os.utime(directory, (old, old))

    def forbidden_client(_session):
        raise AssertionError("invalid socket identity reached BridgeClient")

    monkeypatch.setattr(disc_mod, "BridgeClient", forbidden_client)
    instances, stats = disc_mod.Discovery(run).instances_with_stats()
    assert instances == []
    assert stats.partial is True
    assert stats.reasons == ["socket identity invalid"]
    assert directory.exists() and session_file.exists()


def test_runtime_socket_identity_mismatch_is_partial_and_preserved(tmp_path):
    run = _make_run(tmp_path)
    suffix = f"{tmp_path.stat().st_ino & 0xffffffff:08x}"
    directory = _make_session_dir(run, f"gui-{os.getpid()}-{suffix}")
    fallback = Discovery._fallback_dir(directory.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    directory_stat, socket_stat = fallback.stat(), socket_path.lstat()
    session_file = directory / "session.json"
    _write_private(session_file, json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1,
        "socket_external": True,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": directory_stat.st_dev,
        "socket_dir_ino": directory_stat.st_ino,
    }))
    listener.close()
    socket_path.unlink()
    replacement = socket.socket(socket.AF_UNIX)
    replacement.bind(str(socket_path))
    socket_path.chmod(0o600)
    try:
        instances, stats = Discovery(run).instances_with_stats(force=True)
        assert instances == []
        assert stats.partial is True and stats.skipped_count == 1
        assert stats.reasons == ["identity mismatch"]
        assert directory.exists() and session_file.exists() and socket_path.exists()
    finally:
        replacement.close()
        socket_path.unlink(missing_ok=True)
        fallback.rmdir()


def test_busy_probe_is_reported_without_cleanup(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod
    from server.core.bridge_client import BridgeError

    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    fallback = disc_mod.Discovery._fallback_dir(d.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    _write_private(d / "session.json", json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    class BusyClient:
        def __init__(self, session):
            pass

        def call(self, method, params=None, timeout=None):
            raise BridgeError("BRIDGE_BUSY", "queue full", retryable=True)

    def dead_pid(_pid, _signal):
        raise ProcessLookupError

    monkeypatch.setattr(disc_mod, "BridgeClient", BusyClient)
    monkeypatch.setattr(disc_mod.os, "kill", dead_pid)
    try:
        inst = Discovery(run).instances()
        assert len(inst) == 1 and inst[0].state == "busy" and inst[0].client is not None
        assert d.exists()
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)
        fallback.rmdir()


def test_ping_bool_envelope_version_is_a_mismatch(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    fallback = disc_mod.Discovery._fallback_dir(d.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    _write_private(d / "session.json", json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    class BoolVersionClient:
        def __init__(self, session):
            self._session = session

        def call(self, method, params=None, timeout=None):
            return {"instance_id": self._session["instance_id"],
                    "envelope_version": True}

    monkeypatch.setattr(disc_mod, "BridgeClient", BoolVersionClient)
    try:
        instances = disc_mod.Discovery(run).instances()
        assert len(instances) == 1
        assert instances[0].envelope_mismatch is True
        assert instances[0].state == "disconnected"
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)
        fallback.rmdir()


def test_enumeration_windows_eventually_reach_later_live_instance(live, monkeypatch):
    import server.core.discovery as disc_mod
    s, run = live
    for suffix in ("00000000", "00000001"):
        name = f"gui-1-{suffix}"
        d = _make_session_dir(run, name)
        _write_private(d / "session.json", json.dumps({
            "instance_id": name, "token": "t", "pid": 1,
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
    real_scandir = os.scandir

    class OrderedScandir:
        def __init__(self, path):
            self._inner = real_scandir(path)
            self._entries = iter(sorted(list(self._inner), key=lambda e: e.name))

        def __next__(self):
            return next(self._entries)

        def close(self):
            self._inner.close()

    monkeypatch.setattr(disc_mod.os, "scandir", OrderedScandir)
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 2)
    d = Discovery(run)
    first = d.instances(force=True)
    assert d.last_scan.partial and d.last_scan.skipped_count >= 1
    assert all(i.session["instance_id"] != s.instance_id for i in first)
    second = d.instances(force=True)
    assert any(i.session["instance_id"] == s.instance_id and i.state == "connected"
               for i in second)


def test_abandoned_partial_enumeration_closes_run_fd(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    _make_session_dir(run, "gui-1-00000000")
    _make_session_dir(run, "gui-1-00000001")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)

    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    assert discovery._scan_iter is not None
    scan_fd = discovery._scan_fd
    assert scan_fd is not None

    del discovery
    gc.collect()
    with pytest.raises(OSError):
        os.fstat(scan_fd)


def test_replaced_run_during_preflight_discards_cursor(
        tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    for suffix in ("00000000", "00000001", "00000002"):
        _make_session_dir(run, f"gui-1-{suffix}")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    assert discovery._scan_iter is not None
    scan_fd = discovery._scan_fd
    assert scan_fd is not None

    original_open = disc_mod.Discovery._open_run_dir
    swapped = False

    def swap_during_preflight(self, deadline=None):
        nonlocal swapped
        fd = original_open(self, deadline)
        if not swapped:
            swapped = True
            run.rename(tmp_path / "run-original")
            run.mkdir(mode=0o700)
            run.chmod(0o700)
            _make_session_dir(run, "gui-1-feedface")
        return fd

    # The hook fires after the preflight open, before cursor validation.  It
    # does not claim to cover a race after the final identity check; that
    # same-identity POSIX TOCTOU boundary is documented in the implementation.
    monkeypatch.setattr(disc_mod.Discovery, "_open_run_dir", swap_during_preflight)
    assert discovery.instances(force=True) == []
    assert swapped
    assert discovery.last_scan.partial is True
    assert "run cursor replaced" in discovery.last_scan.reasons
    assert discovery._scan_iter is None
    assert discovery._candidate_backlog == []
    with pytest.raises(OSError):
        os.fstat(scan_fd)  # the still-owned original cursor fd was not leaked


def test_closed_scan_cursor_is_dropped(
        tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    for suffix in ("00000000", "00000001"):
        _make_session_dir(run, f"gui-1-{suffix}")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    scan_fd = discovery._scan_fd
    assert scan_fd is not None
    os.close(scan_fd)  # simulate an externally closed/reused descriptor
    assert discovery.instances(force=True) == []
    assert discovery.last_scan.partial is True
    assert "run cursor closed" in discovery.last_scan.reasons
    assert discovery._scan_fd is None and discovery._scan_iter is None


def test_identity_different_reused_scan_fd_is_not_closed(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    for suffix in ("00000000", "00000001"):
        _make_session_dir(run, f"gui-1-{suffix}")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    scan_fd = discovery._scan_fd
    assert scan_fd is not None

    os.close(scan_fd)
    unrelated_path = tmp_path / "unrelated"
    unrelated_path.write_bytes(b"owned elsewhere")
    unrelated_fd = _reuse_fd_for_path(scan_fd, unrelated_path)
    try:
        assert discovery.instances(force=True) == []
        assert discovery.last_scan.partial is True
        assert "run cursor replaced" in discovery.last_scan.reasons
        assert os.read(unrelated_fd, 5) == b"owned"  # no collateral close
    finally:
        os.close(unrelated_fd)


def test_cursor_cleanup_deadline_does_not_close_reused_foreign_fd(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    _make_session_dir(run, "gui-1-00000000")
    _make_session_dir(run, "gui-1-00000001")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    scan_fd = discovery._scan_fd
    assert scan_fd is not None
    os.close(scan_fd)
    unrelated_path = tmp_path / "unrelated-deadline"
    unrelated_path.write_bytes(b"foreign")
    unrelated_fd = _reuse_fd_for_path(scan_fd, unrelated_path)
    try:
        stats = disc_mod.ScanStats()
        assert discovery._validate_scan_cursor(time.monotonic() - 1.0, stats) is False
        assert os.read(unrelated_fd, 7) == b"foreign"
    finally:
        os.close(unrelated_fd)


def test_discovery_destructor_does_not_close_reused_foreign_fd(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    _make_session_dir(run, "gui-1-00000000")
    _make_session_dir(run, "gui-1-00000001")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    scan_fd = discovery._scan_fd
    assert scan_fd is not None
    os.close(scan_fd)
    unrelated_path = tmp_path / "unrelated-destructor"
    unrelated_path.write_bytes(b"foreign")
    unrelated_fd = _reuse_fd_for_path(scan_fd, unrelated_path)
    del discovery
    gc.collect()
    try:
        assert os.read(unrelated_fd, 7) == b"foreign"
    finally:
        os.close(unrelated_fd)


def test_candidate_backlog_eventually_reaches_older_live_instance(live):
    # 同一枚举窗口里，16 个较新但 pid 存活的断连实例不得永久饿死第 17 个活实例。
    s, run = live
    live_dir = run / s.instance_id
    os.utime(live_dir, (1, 1))
    for i in range(16):
        name = f"gui-{os.getpid()}-{i:08x}"
        d = _make_session_dir(run, name)
        _write_private(d / "session.json", json.dumps({
            "instance_id": name, "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
        os.utime(d, (100 + i, 100 + i))

    discovery = Discovery(run)
    first = discovery.instances(force=True)
    assert len(first) == 16
    assert all(i.session["instance_id"] != s.instance_id for i in first)
    assert discovery.last_scan.partial and discovery.last_scan.skipped_count >= 1

    second = discovery.instances(force=True)
    assert any(i.session["instance_id"] == s.instance_id and i.state == "connected"
               for i in second)


def test_backlog_reports_unenumerated_tail_as_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod
    run = _make_run(tmp_path)
    for i in range(18):
        d = _make_session_dir(run, f"gui-{os.getpid()}-{i:08x}")
        _write_private(d / "session.json", json.dumps({
            "instance_id": d.name, "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))

    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 17)
    discovery = Discovery(run)
    discovery.instances(force=True)  # 16 probed, 1 in backlog, >=1 not enumerated
    assert discovery.last_scan.partial
    discovery.instances(force=True)  # backlog <= candidate cap; unenumerated tail remains
    assert discovery.last_scan.partial and discovery.last_scan.skipped_count >= 1
```

- [ ] **Step 2: 跑测试确认失败** → `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_discovery.py -q`

- [ ] **Step 3: 实现**

```python
# server/core/discovery.py
"""实例发现。spec §4.3。

deadline 语义（2026-08-07 三轮审计 F-03 / R-03 / F-01 累积修订）——**有界，不是绝对**：
- deadline 在 `_scan()` 入口创建，覆盖枚举、stat、读取、解析、排序与 probe 全过程；
- 目录枚举用惰性 `os.scandir()` 并在预算/条数耗尽时**立即 break**——`sorted(iterdir())`
  会在循环体的 deadline 检查生效前把整个目录读完（实测 400 项 × 10 ms = 4.8 s）；
- `session.json` 以 `O_NOFOLLOW|O_NONBLOCK` 打开，并在**同一个 fd** 上 `fstat`、限长读取；
  FIFO/device/symlink、换入竞态、读取中扩容均被拒绝；每次 `next/open/fstat/read` 前重查预算；
- 常规文件 I/O 进入内核后仍不可由 monotonic clock 强制取消，因此保证限定为本机常规文件与
  有界系统调用序列，不宣称对失效网络文件系统或内核卡死提供绝对墙钟上界。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import re
import stat as stat_mod
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from protocol import envelope
from .bridge_client import BridgeClient, BridgeError
from .versions import check

_diag = logging.getLogger("bcx.server")
GRACE_SECONDS = 60.0
SCAN_DEADLINE = 2.5          # 全扫描默认预算，从 _scan() 入口起算
MAX_SCAN_ENTRIES = 256       # 单窗口枚举上限；cursor + backlog 跨调用公平推进
MAX_CANDIDATES = 16          # probe 上限：按 mtime 取**最新**（F-08：字典序会饿死活实例）
MAX_SESSION_BYTES = 64 * 1024
PROBE_TIMEOUT = 2.0
PRIVATE_INIT_TIMEOUT = 0.1
DirIdentity = tuple[int, int]
Entry = tuple[float, Path, DirIdentity]
INSTANCE_ID = re.compile(r"^gui-([1-9][0-9]*)-([0-9a-f]{8})$")
_DIR_FLAGS = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY


def _private_dir_identity(st: os.stat_result, path: Path,
                          expected: DirIdentity | None = None) -> DirIdentity:
    identity = st.st_dev, st.st_ino
    if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat_mod.S_IMODE(st.st_mode) != 0o700
            or (expected is not None and identity != expected)):
        raise PermissionError(f"private directory required: {path}")
    return identity


def _ensure_private_dir(path: Path) -> DirIdentity:
    created = False
    try:
        path.mkdir(mode=0o700, parents=True)
    except FileExistsError:
        pass
    else:
        created = True
    if created:
        os.chmod(path, 0o700, follow_symlinks=False)
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: DirIdentity | None = None
    while True:
        st = path.lstat()
        identity = st.st_dev, st.st_ino
        mode = stat_mod.S_IMODE(st.st_mode)
        if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            return identity
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)


def _wait_private_dir_at(name: str, parent_fd: int, path: Path) -> os.stat_result:
    deadline = time.monotonic() + PRIVATE_INIT_TIMEOUT
    expected: DirIdentity | None = None
    while True:
        st = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        identity = st.st_dev, st.st_ino
        mode = stat_mod.S_IMODE(st.st_mode)
        if (not stat_mod.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or mode & ~0o700 or (expected is not None and identity != expected)):
            raise PermissionError(f"private directory required: {path}")
        if mode == 0o700:
            return st
        expected = identity
        if time.monotonic() >= deadline:
            raise PermissionError(f"private directory required: {path}")
        time.sleep(0.005)


@dataclass
class Instance:
    session: dict[str, Any]
    state: str
    blender_supported: bool
    version_warning: str | None
    client: BridgeClient | None
    envelope_mismatch: bool = False


@dataclass
class ScanStats:
    """顶层 partial 元数据（F-06 P2：不再伪装成一个 id 为 __partial__ 的假实例）。"""
    partial: bool = False
    skipped_count: int = 0
    reasons: list[str] = field(default_factory=list)


def _mark_cleanup_incomplete(stats: ScanStats | None) -> None:
    if stats is None:
        return
    stats.partial = True
    stats.skipped_count += 1
    if "cleanup incomplete" not in stats.reasons:
        stats.reasons.append("cleanup incomplete")


def _mark_socket_identity_invalid(stats: ScanStats | None) -> None:
    if stats is None:
        return
    stats.partial = True
    stats.skipped_count += 1
    if "socket identity invalid" not in stats.reasons:
        stats.reasons.append("socket identity invalid")


def _mark_session_identity_replaced(stats: ScanStats | None) -> None:
    if stats is None:
        return
    stats.partial = True
    stats.skipped_count += 1
    if "session identity replaced" not in stats.reasons:
        stats.reasons.append("session identity replaced")


class _ProbeDeadline(Exception):
    pass


class _SocketIdentityInvalid(ValueError):
    pass


class Discovery:
    def __init__(self, run_dir: Path, ttl: float = 1.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._run = Path(run_dir)
        self._run_parent_identity = _ensure_private_dir(self._run.parent)
        parent_fd = os.open(self._run.parent, _DIR_FLAGS)
        run_fd: int | None = None
        try:
            _private_dir_identity(os.fstat(parent_fd), self._run.parent,
                                  self._run_parent_identity)
            created = False
            try:
                os.mkdir(self._run.name, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            else:
                created = True
            if created:
                os.chmod(self._run.name, 0o700, dir_fd=parent_fd,
                         follow_symlinks=False)
            run_stat = _wait_private_dir_at(self._run.name, parent_fd, self._run)
            self._run_identity = _private_dir_identity(run_stat, self._run)
            run_fd = os.open(self._run.name, _DIR_FLAGS, dir_fd=parent_fd)
            _private_dir_identity(os.fstat(run_fd), self._run,
                                  self._run_identity)
        finally:
            if run_fd is not None:
                os.close(run_fd)
            os.close(parent_fd)
        self._ttl = ttl
        self._clock = clock
        self._cache: list[Instance] | None = None
        self._cached_at = -1e9
        self._lock = threading.Lock()
        # A one-slot Queue coalesces repeated failures into one thread-safe,
        # non-blocking signal.  A scan consumes it only while holding the
        # discovery lock; invalidate() never waits for that lock, and a signal
        # arriving during a scan prevents that scan from publishing a cache.
        self._invalidations: queue.Queue[None] = queue.Queue(maxsize=1)
        self._scan_iter: Any = None
        self._scan_fd: int | None = None
        self._scan_identity: DirIdentity | None = None
        self._pending_entry: Any = None
        self._candidate_backlog: list[Entry] = []
        self.last_scan = ScanStats()

    def __del__(self) -> None:
        # A paginated scandir(fd) cursor requires the caller-owned fd to remain
        # open. Close both if a short-lived Discovery is abandoned mid-window.
        try:
            self._close_scan_cursor()
        except Exception:
            pass

    def instances(self, force: bool = False,
                  deadline: float | None = None) -> list[Instance]:
        """deadline 为绝对 monotonic 时刻；None 时用 SCAN_DEADLINE 自建（F-02）。"""
        return self.instances_with_stats(force, deadline)[0]

    def instances_with_stats(
            self, force: bool = False,
            deadline: float | None = None) -> tuple[list[Instance], ScanStats]:
        """Atomically pair instances with the ScanStats snapshot that produced them."""
        if deadline is None:
            deadline = time.monotonic() + SCAN_DEADLINE
        remaining = deadline - time.monotonic()
        acquired = remaining > 0 and self._lock.acquire(timeout=remaining)
        if not acquired:
            stats = ScanStats(True, 1, ["discovery lock deadline"])
            return [], stats
        try:
            if self._take_invalidation():
                self._cache = None
                self._cached_at = -1e9
            cached = self._cache
            cached_at = self._cached_at
            if not force and cached is not None \
                    and self._clock() - cached_at < self._ttl:
                instances = cached
            else:
                instances = self._scan(deadline)
                if self._take_invalidation():
                    self._cache = None
                    self._cached_at = -1e9
                else:
                    self._cache = instances
                    self._cached_at = self._clock()
            stats = self.last_scan
            return instances, ScanStats(stats.partial, stats.skipped_count,
                                        list(stats.reasons))
        finally:
            self._lock.release()

    def invalidate(self, deadline: float | None = None) -> bool:
        """Bridge 失联后使下一次调用重新扫描，而不是复用 1s 旧缓存。"""
        # The signal is constant-time and does not wait for filesystem/probe
        # work.  The deadline is accepted for adapter call-site symmetry; no
        # blocking operation is needed for this notification.
        del deadline
        try:
            self._invalidations.put_nowait(None)
        except queue.Full:
            pass  # an outstanding signal already represents this invalidation
        return True

    def _take_invalidation(self) -> bool:
        """Consume at most one signal so a concurrent producer cannot extend a scan."""
        try:
            self._invalidations.get_nowait()
        except queue.Empty:
            return False
        return True

    def find(self, instance_id: str,
             deadline: float | None = None) -> Instance | None:
        return self.find_with_stats(instance_id, deadline)[0]

    def find_with_stats(
            self, instance_id: str,
            deadline: float | None = None) -> tuple[Instance | None, ScanStats]:
        instances, stats = self.instances_with_stats(deadline=deadline)
        for inst in instances:
            if inst.session["instance_id"] == instance_id:
                return inst, stats
        return None, stats

    # ---------- 扫描 ----------
    def _scan(self, deadline: float | None = None) -> list[Instance]:
        if deadline is None:
            deadline = time.monotonic() + SCAN_DEADLINE
        stats = ScanStats()
        self.last_scan = stats
        out: list[Instance] = []

        if time.monotonic() >= deadline:
            stats.partial = True
            stats.skipped_count = 1
            stats.reasons.append("run deadline")
            return out
        try:
            os.close(self._open_run_dir(deadline))
        except TimeoutError:
            stats.partial = True
            stats.skipped_count = 1
            stats.reasons.append("run deadline")
            return out
        except OSError:
            stats.partial = True
            stats.skipped_count = 1
            stats.reasons.append("run boundary")
            self._close_scan_cursor()
            self._candidate_backlog = []
            return out

        from_backlog = bool(self._candidate_backlog)
        entries = self._candidate_backlog
        self._candidate_backlog = []
        if not entries:
            entries = self._enumerate(deadline, stats)
        if not entries:
            return out
        entries.sort(key=lambda e: e[0], reverse=True)          # mtime 新 → 旧
        if len(entries) > MAX_CANDIDATES:
            stats.partial = True
            stats.skipped_count += len(entries) - MAX_CANDIDATES
            stats.reasons.append("candidate cap")
            self._candidate_backlog = entries[MAX_CANDIDATES:]
            entries = entries[:MAX_CANDIDATES]
        if from_backlog and (self._scan_iter is not None
                             or self._pending_entry is not None):
            stats.partial = True
            stats.skipped_count += 1  # 未枚举尾部的保守下界
            stats.reasons.append("enumeration window")

        candidates: list[tuple[Path, dict[str, Any], DirIdentity]] = []
        for index, (_mtime, d, identity) in enumerate(entries):
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count += len(entries) - index
                stats.reasons.append("deadline during session read")
                self._candidate_backlog = entries[index:] + self._candidate_backlog
                break
            try:
                sess = self._read_session(d, identity, deadline, stats)
            except TimeoutError:
                stats.partial = True
                stats.skipped_count += len(entries) - index
                stats.reasons.append("deadline during session read")
                self._candidate_backlog = entries[index:] + self._candidate_backlog
                break
            if sess is not None:
                candidates.append((d, sess, identity))
        if not candidates:
            return out
        return out + self._probe_all(candidates, deadline, stats)

    def _open_run_dir(self, deadline: float | None = None) -> int:
        """Open the configured run directory through its identity-bound parent."""
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError
        parent_fd = os.open(self._run.parent, _DIR_FLAGS)
        try:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError
            _private_dir_identity(os.fstat(parent_fd), self._run.parent,
                                  self._run_parent_identity)
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError
            run_fd = os.open(self._run.name, _DIR_FLAGS, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
        try:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError
            _private_dir_identity(os.fstat(run_fd), self._run,
                                  self._run_identity)
            return run_fd
        except BaseException:
            os.close(run_fd)
            raise

    def _close_scan_cursor(self) -> None:
        scan_iter, self._scan_iter = self._scan_iter, None
        scan_fd, self._scan_fd = self._scan_fd, None
        scan_identity, self._scan_identity = self._scan_identity, None
        owns_fd = False
        if scan_fd is not None and scan_identity is not None:
            try:
                current = os.fstat(scan_fd)
            except OSError:
                pass
            else:
                owns_fd = (current.st_dev, current.st_ino) == scan_identity
        if scan_iter is not None:
            try:
                scan_iter.close()
            except Exception:
                pass
        if owns_fd and scan_fd is not None:
            try:
                os.close(scan_fd)
            except OSError:
                pass
        self._pending_entry = None

    def _discard_scan_cursor(self) -> None:
        """Drop an unproven/reused fd without closing a possibly unrelated fd number."""
        scan_iter, self._scan_iter = self._scan_iter, None
        if scan_iter is not None:
            try:
                scan_iter.close()
            except Exception:
                pass
        self._scan_fd = None
        self._scan_identity = None
        self._pending_entry = None

    def _validate_scan_cursor(self, deadline: float, stats: ScanStats) -> bool:
        """Rebind the persisted cursor to the current run directory identity.

        The finite fstat checks reject closed or different-identity descriptor
        reuse.  POSIX exposes no portable per-open-file-description nonce, so a
        same-identity descriptor hijack after the final check is outside this
        private-cursor guarantee.
        """
        if self._scan_iter is None:
            return True
        if self._scan_fd is None:
            self._discard_scan_cursor()
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor replaced")
            return False
        if time.monotonic() >= deadline:
            self._close_scan_cursor()
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor deadline")
            return False
        current_fd: int | None = None
        try:
            cursor_stat = os.fstat(self._scan_fd)
        except OSError:
            self._discard_scan_cursor()
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor closed")
            return False
        cursor_identity = (cursor_stat.st_dev, cursor_stat.st_ino)
        cursor_owned = (self._scan_identity == cursor_identity
                        and cursor_identity == self._run_identity)
        try:
            current_fd = self._open_run_dir(deadline)
            current_stat = os.fstat(current_fd)
        except TimeoutError:
            (self._close_scan_cursor() if cursor_owned
             else self._discard_scan_cursor())
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor deadline")
            return False
        except OSError:
            (self._close_scan_cursor() if cursor_owned
             else self._discard_scan_cursor())
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor replaced")
            return False
        finally:
            if current_fd is not None:
                try:
                    os.close(current_fd)
                except OSError:
                    pass
        current_identity = (current_stat.st_dev, current_stat.st_ino)
        if (cursor_identity != self._run_identity
                or current_identity != self._run_identity
                or (self._scan_identity is not None
                    and self._scan_identity != cursor_identity)):
            (self._close_scan_cursor() if cursor_owned
             else self._discard_scan_cursor())
            self._candidate_backlog = []
            stats.partial = True
            stats.skipped_count += 1
            stats.reasons.append("run cursor replaced")
            return False
        self._scan_identity = cursor_identity
        return True

    def _enumerate(self, deadline: float,
                   stats: ScanStats) -> list[Entry]:
        """惰性枚举 + 预算/条数双止损。绝不先 sorted() 全量物化（F-01）。"""
        found: list[Entry] = []
        seen = 0
        if not self._validate_scan_cursor(deadline, stats):
            return found
        if self._scan_iter is None:
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count = 1
                stats.reasons.append("enumeration deadline")
                return found
            try:
                self._scan_fd = self._open_run_dir(deadline)
                try:
                    self._scan_iter = os.scandir(self._scan_fd)
                    scan_stat = os.fstat(self._scan_fd)
                    self._scan_identity = (scan_stat.st_dev, scan_stat.st_ino)
                except BaseException:
                    os.close(self._scan_fd)
                    self._scan_fd = None
                    self._scan_identity = None
                    raise
            except TimeoutError:
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration deadline")
                return found
            except OSError:
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration error")
                return found
        while seen < MAX_SCAN_ENTRIES:
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count += 1  # 下界；不为精确计数继续枚举
                stats.reasons.append("enumeration deadline")
                break
            try:
                if self._pending_entry is not None:
                    entry, self._pending_entry = self._pending_entry, None
                else:
                    entry = next(self._scan_iter)
            except StopIteration:
                self._close_scan_cursor()
                break
            except OSError:
                self._close_scan_cursor()
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration error")
                break
            seen += 1
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError
                entry_stat = entry.stat(follow_symlinks=False)
                found.append((entry_stat.st_mtime, self._run / entry.name,
                              (entry_stat.st_dev, entry_stat.st_ino)))
            except TimeoutError:
                self._pending_entry = entry
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration deadline")
                break
            except OSError:
                stats.partial = True
                stats.skipped_count += 1
                if "entry error" not in stats.reasons:
                    stats.reasons.append("entry error")
                continue

        # 一项 look-ahead 区分“正好 256 项”与“仍有候选”；保留该项供下轮处理，
        # 从而使 256 项后的活实例不会永久饿死。
        if seen >= MAX_SCAN_ENTRIES and self._scan_iter is not None:
            if time.monotonic() >= deadline:
                stats.partial = True
                stats.skipped_count += 1
                stats.reasons.append("enumeration deadline")
            else:
                try:
                    self._pending_entry = next(self._scan_iter)
                except StopIteration:
                    self._close_scan_cursor()
                except OSError:
                    self._close_scan_cursor()
                    stats.partial = True
                    stats.skipped_count += 1
                    stats.reasons.append("enumeration error")
                else:
                    stats.partial = True
                    stats.skipped_count += 1  # 未枚举总数未知，报告至少跳过一项
                    stats.reasons.append("enumeration window")
        return found

    @staticmethod
    def _read_session(d: Path, expected_identity: DirIdentity,
                      deadline: float,
                      stats: ScanStats | None = None) -> dict[str, Any] | None:
        """同一目录/file fd 完成 open/fstat/有界读取，拒绝换入竞态。"""
        dir_fd: int | None = None
        dir_identity: DirIdentity | None = None
        try:
            if time.monotonic() >= deadline:
                raise TimeoutError
            # Bind the parent directory before opening its child.  Checking only
            # O_NOFOLLOW on ``d/session.json`` still follows a parent-directory
            # symlink swapped in after enumeration.
            dir_flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
            dir_fd = os.open(d, dir_flags)
            dir_stat = os.fstat(dir_fd)
            dir_identity = (dir_stat.st_dev, dir_stat.st_ino)
            if (dir_identity != expected_identity or dir_stat.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(dir_stat.st_mode) != 0o700):
                raise ValueError("session directory is not private or changed")
            if time.monotonic() >= deadline:
                raise TimeoutError
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            fd = os.open("session.json", flags, dir_fd=dir_fd)
            try:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                st = os.fstat(fd)
                if (not stat_mod.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                        or stat_mod.S_IMODE(st.st_mode) != 0o600):
                    raise ValueError("session.json is not a private regular file")
                if st.st_size > MAX_SESSION_BYTES:
                    raise ValueError("session.json is too large")
                chunks: list[bytes] = []
                remaining = MAX_SESSION_BYTES + 1
                while remaining:
                    if time.monotonic() >= deadline:
                        raise TimeoutError
                    chunk = os.read(fd, min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
            finally:
                os.close(fd)
                os.close(dir_fd)
                dir_fd = None
            raw = b"".join(chunks)
            if len(raw) > MAX_SESSION_BYTES:
                raise ValueError("session.json grew beyond the size limit")
            data = json.loads(raw)
            required = {
                "instance_id": str, "token": str, "pid": int,
                "socket_path": str, "blender_version": str,
                "bridge_version": str, "envelope_version": int,
            }
            if not isinstance(data, dict) or any(
                    type(data.get(key)) is not kind for key, kind in required.items()):
                raise ValueError("invalid session schema")
            if data["instance_id"] != d.name:
                raise ValueError("instance_id does not match session directory")
            match = INSTANCE_ID.fullmatch(d.name)
            if match is None or int(match.group(1)) != data["pid"]:
                raise ValueError("instance_id pid does not match session pid")
            identity_fields = ("socket_dev", "socket_ino", "socket_dir_dev",
                               "socket_dir_ino")
            if ("socket_external" in data
                    and type(data["socket_external"]) is not bool):
                raise _SocketIdentityInvalid("invalid socket_external")
            if any(key in data and type(data[key]) is not int for key in identity_fields):
                raise _SocketIdentityInvalid("invalid socket identity")
            if any(key not in data for key in identity_fields):
                raise _SocketIdentityInvalid("missing socket identity")
            socket_path = Path(data["socket_path"])
            if data.get("socket_external") is True:
                fallback = Discovery._fallback_dir(d.name)
                if fallback is None or socket_path != fallback / "bridge.sock":
                    raise _SocketIdentityInvalid("invalid external socket path")
            elif socket_path != d / "bridge.sock":
                raise _SocketIdentityInvalid("invalid internal socket path")
            return data
        except TimeoutError:
            if dir_fd is not None:
                os.close(dir_fd)
            raise
        except _SocketIdentityInvalid:
            if dir_fd is not None:
                os.close(dir_fd)
            _mark_socket_identity_invalid(stats)
            return None
        except (OSError, ValueError, RecursionError):
            if dir_fd is not None:
                os.close(dir_fd)
            try:
                if time.monotonic() >= deadline:
                    _mark_cleanup_incomplete(stats)
                    return None
                dst = d.stat(follow_symlinks=False)
                current_identity = (dst.st_dev, dst.st_ino)
                boundary_ok = (
                    stat_mod.S_ISDIR(dst.st_mode)
                    and current_identity == expected_identity
                    and dst.st_uid == os.geteuid()
                    and stat_mod.S_IMODE(dst.st_mode) == 0o700
                )
                if not boundary_ok:
                    _mark_session_identity_replaced(stats)
                elif (time.monotonic() < deadline
                      and time.time() - dst.st_mtime > GRACE_SECONDS):
                    _diag.info("cleaning corrupt session dir %s", d)
                    complete = Discovery._remove_external_socket(d, None, deadline)
                    if complete:
                        complete = Discovery._remove_session_dir(
                            d, expected_identity, deadline)
                    if not complete:
                        _mark_cleanup_incomplete(stats)
            except OSError:
                _mark_cleanup_incomplete(stats)
            return None

    @staticmethod
    def _remove_session_dir(d: Path, expected_identity: DirIdentity,
                            deadline: float | None = None,
                            expected_socket: DirIdentity | None = None) -> bool:
        """Bounded stale cleanup; never recursively deletes a replaced directory."""
        dir_fd: int | None = None
        try:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
            dir_fd = os.open(d, flags)
            if deadline is not None and time.monotonic() >= deadline:
                return False
            st = os.fstat(dir_fd)
            if ((st.st_dev, st.st_ino) != expected_identity
                    or st.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(st.st_mode) != 0o700):
                return False
            # A valid session directory contains only these files.  Do not recurse:
            # arbitrary trees would turn discovery cleanup into an unbounded deadline
            # escape.  Unknown children intentionally leave the directory for review.
            for name in ("session.json", "session.json.tmp", "bridge.sock"):
                if deadline is not None and time.monotonic() >= deadline:
                    return False
                try:
                    child = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
                    regular = name != "bridge.sock"
                    if (child.st_uid != os.geteuid()
                            or stat_mod.S_IMODE(child.st_mode) != 0o600
                            or (regular and not stat_mod.S_ISREG(child.st_mode))
                            or (not regular and not stat_mod.S_ISSOCK(child.st_mode))
                            or (not regular and expected_socket is not None
                                and (child.st_dev, child.st_ino) != expected_socket)):
                        return False
                    if deadline is not None and time.monotonic() >= deadline:
                        return False
                    os.unlink(name, dir_fd=dir_fd)
                except FileNotFoundError:
                    pass
                except IsADirectoryError:
                    return False
        except OSError:
            return False
        finally:
            if dir_fd is not None:
                os.close(dir_fd)
        try:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            st = d.stat(follow_symlinks=False)
            if ((not stat_mod.S_ISDIR(st.st_mode))
                    or (st.st_dev, st.st_ino) != expected_identity
                    or st.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(st.st_mode) != 0o700):
                return False
            if deadline is not None and time.monotonic() >= deadline:
                return False
            d.rmdir()
            return True
        except OSError:
            return False

    @staticmethod
    def _fallback_dir(instance_id: str) -> Path | None:
        digest = hashlib.sha256(instance_id.encode()).hexdigest()[:16]
        fallback = Path("/tmp") / f"bcx-{digest}"
        return fallback if len(str(fallback / "bridge.sock").encode()) <= 100 else None

    @staticmethod
    def _socket_identity_state(sess: dict[str, Any], deadline: float) -> str:
        """Return ok/missing/mismatch without connecting to an unbound path."""
        identity_fields = ("socket_dev", "socket_ino", "socket_dir_dev",
                           "socket_dir_ino")
        if any(key not in sess for key in identity_fields):
            return "mismatch"  # defensive fail-closed; _read_session rejects this schema
        path = Path(sess["socket_path"])
        try:
            if time.monotonic() >= deadline:
                raise _ProbeDeadline
            directory = path.parent.lstat()
            if time.monotonic() >= deadline:
                raise _ProbeDeadline
            sock = path.lstat()
        except FileNotFoundError:
            return "missing"
        except OSError:
            return "mismatch"
        if (not stat_mod.S_ISDIR(directory.st_mode)
                or directory.st_uid != os.geteuid()
                or stat_mod.S_IMODE(directory.st_mode) != 0o700
                or (directory.st_dev, directory.st_ino)
                != (sess["socket_dir_dev"], sess["socket_dir_ino"])
                or not stat_mod.S_ISSOCK(sock.st_mode)
                or sock.st_uid != os.geteuid()
                or stat_mod.S_IMODE(sock.st_mode) != 0o600
                or (sock.st_dev, sock.st_ino)
                != (sess["socket_dev"], sess["socket_ino"])):
            return "mismatch"
        return "ok"

    @staticmethod
    def _remove_external_socket(d: Path, sess: dict[str, Any] | None,
                                deadline: float) -> bool:
        """Remove the identity-bound deterministic sun_path fallback, if one exists."""
        default_is_long = len(str(d / "bridge.sock").encode()) > 100
        if sess is not None:
            socket_path = Path(sess["socket_path"])
            actual_external = socket_path.parent != d
            if not actual_external:
                try:
                    state = Discovery._socket_identity_state(sess, deadline)
                except _ProbeDeadline:
                    return False
                return state in {"ok", "missing"}
            if sess.get("socket_external") is not True:
                return False  # old/untrusted metadata: retain session evidence
            fallback = Discovery._fallback_dir(d.name)
            if fallback is None or socket_path != fallback / "bridge.sock":
                return False
            expected_dir = (sess["socket_dir_dev"], sess["socket_dir_ino"])
            expected_socket: DirIdentity | None = (sess["socket_dev"], sess["socket_ino"])
        else:
            if not default_is_long:
                return True
            fallback = Discovery._fallback_dir(d.name)
            if fallback is None:
                return False
            expected_dir = None
            expected_socket = None
            socket_path = fallback / "bridge.sock"

        dir_fd: int | None = None
        observed_dir: DirIdentity | None = None
        try:
            if time.monotonic() >= deadline:
                return False
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
            dir_fd = os.open(fallback, flags)
            if time.monotonic() >= deadline:
                return False
            st = os.fstat(dir_fd)
            observed_dir = (st.st_dev, st.st_ino)
            if (st.st_uid != os.geteuid() or stat_mod.S_IMODE(st.st_mode) != 0o700
                    or (expected_dir is not None and observed_dir != expected_dir)
                    or (expected_dir is None
                        and time.time() - st.st_mtime <= GRACE_SECONDS)):
                return False
            if time.monotonic() >= deadline:
                return False
            try:
                socket_stat = os.stat(socket_path.name, dir_fd=dir_fd,
                                      follow_symlinks=False)
            except FileNotFoundError:
                socket_stat = None
            if socket_stat is not None:
                if (not stat_mod.S_ISSOCK(socket_stat.st_mode)
                        or socket_stat.st_uid != os.geteuid()
                        or stat_mod.S_IMODE(socket_stat.st_mode) != 0o600
                        or (expected_socket is not None
                            and (socket_stat.st_dev, socket_stat.st_ino)
                            != expected_socket)):
                    return False
                if time.monotonic() >= deadline:
                    return False
                try:
                    os.unlink(socket_path.name, dir_fd=dir_fd)
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            return True
        except OSError:
            return False
        finally:
            if dir_fd is not None:
                os.close(dir_fd)
        try:
            if time.monotonic() >= deadline:
                return False
            current = fallback.stat(follow_symlinks=False)
            if ((not stat_mod.S_ISDIR(current.st_mode))
                    or (current.st_dev, current.st_ino) != observed_dir
                    or current.st_uid != os.geteuid()
                    or stat_mod.S_IMODE(current.st_mode) != 0o700):
                return False
            if time.monotonic() >= deadline:
                return False
            fallback.rmdir()  # unknown children make this fail closed
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def _probe_all(self, candidates: list[tuple[Path, dict[str, Any], DirIdentity]],
                   deadline: float, stats: ScanStats) -> list[Instance]:
        out: list[Instance] = []
        if time.monotonic() >= deadline:
            stats.partial = True
            stats.skipped_count += len(candidates)
            stats.reasons.append("probe deadline")
            return [self._make(sess, "disconnected", client=None,
                               note="probe skipped: deadline")
                    for _d, sess, _identity in candidates]
        ex = ThreadPoolExecutor(max_workers=8)
        try:
            futs = {ex.submit(self._probe, sess, deadline): (d, sess, identity)
                    for d, sess, identity in candidates}
            done, not_done = wait(futs, timeout=max(0.0, deadline - time.monotonic()))
            for f in sorted(done, key=lambda x: futs[x][0].name):   # 顺序确定
                d, sess, identity = futs[f]
                try:
                    inst = f.result()
                except _ProbeDeadline:
                    stats.partial = True
                    stats.skipped_count += 1
                    if "probe deadline" not in stats.reasons:
                        stats.reasons.append("probe deadline")
                    out.append(self._make(sess, "disconnected", client=None,
                                          note="probe skipped: deadline"))
                    continue
                except Exception as exc:  # 单个损坏候选不得击穿整次发现
                    _diag.info("session probe failed for %s: %s", d, exc)
                    out.append(self._make(sess, "disconnected", client=None,
                                          note="probe failed"))
                    continue
                if inst is None:
                    _diag.info("cleaning dead session dir %s", d)
                    complete = self._remove_external_socket(d, sess, deadline)
                    if complete:
                        expected_socket = (sess["socket_dev"], sess["socket_ino"])
                        complete = self._remove_session_dir(
                            d, identity, deadline, expected_socket)
                    if not complete:
                        _mark_cleanup_incomplete(stats)
                elif inst.session.get("__stale__"):
                    stats.partial = True
                    stats.skipped_count += 1
                    if "identity mismatch" not in stats.reasons:
                        stats.reasons.append("identity mismatch")
                    continue          # 握手身份不符：不计入也不清理（§4.3）
                else:
                    out.append(inst)
            for f in sorted(not_done, key=lambda x: futs[x][0].name):
                _d, sess, _identity = futs[f]    # 预算耗尽：如实标注，绝不清理
                stats.partial = True
                stats.skipped_count += 1
                out.append(self._make(sess, "disconnected", client=None,
                                      note="probe skipped: deadline"))
            if not_done and "probe deadline" not in stats.reasons:
                stats.reasons.append("probe deadline")
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        return out

    def _probe(self, sess: dict[str, Any], deadline: float) -> Instance | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _ProbeDeadline
        pid_alive = True
        try:
            os.kill(int(sess.get("pid", -1)), 0)
        except (OSError, ValueError):
            pid_alive = False
        if time.monotonic() >= deadline:
            raise _ProbeDeadline
        socket_state = self._socket_identity_state(sess, deadline)
        if socket_state == "mismatch":
            return self._make({**sess, "__stale__": True}, "disconnected", client=None)
        if socket_state == "missing":
            if not pid_alive:
                return None
            return self._make(sess, "disconnected", client=None)
        client = BridgeClient(sess)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _ProbeDeadline
        budget = min(PROBE_TIMEOUT, remaining)
        try:
            pong = client.call("ping", timeout=budget)   # 剩余预算，防批次叠加
        except BridgeError as exc:
            if exc.code == envelope.ENVELOPE_VERSION_MISMATCH:
                inst = self._make(sess, "disconnected", client=None)
                inst.envelope_mismatch = True
                inst.version_warning = str(exc)
                return inst
            if exc.code == envelope.BRIDGE_BUSY:
                return self._make(sess, "busy", client=client,
                                  note="bridge busy")
            if not pid_alive:
                return None       # 双条件成立 → 清理
            return self._make(sess, "disconnected", client=None)
        if pong.get("instance_id") != sess.get("instance_id"):
            return self._make({**sess, "__stale__": True}, "disconnected", client=None)
        pong_version = pong.get("envelope_version")
        if type(pong_version) is not int \
                or pong_version != envelope.ENVELOPE_VERSION:
            inst = self._make(sess, "disconnected", client=None)
            inst.envelope_mismatch = True
            inst.version_warning = (
                f"envelope v{pong_version} != v{envelope.ENVELOPE_VERSION}，"
                f"Server 与 Bridge 版本不匹配")
            return inst
        return self._make(sess, "connected", client=client)

    @staticmethod
    def _make(sess: dict[str, Any], state: str, client: BridgeClient | None,
              note: str | None = None) -> Instance:
        supported, warning = check(str(sess.get("blender_version", "")))
        if note is not None:
            warning = f"{warning}；{note}" if warning else note
        return Instance(session=sess, state=state, blender_supported=supported,
                        version_warning=warning, client=client)
```

- [ ] **Step 4: 跑测试确认通过** → 当前 v8 物化树 **58 passed**（Discovery；旧 54 为历史）

- [ ] **Step 5: Commit**

```bash
git add server/core/discovery.py tests/unit/test_discovery.py
git commit -m "feat(server-core): 实例发现——握手权威判定、1s 缓存、双条件清理与宽限期"
```

---

### Task 12: server/mcp/adapter.py（三工具 + 审计接线）

**Files:**
- Create: `server/mcp/adapter.py`
- Modify: `server/core/discovery.py`（`Instance` 增加 `envelope_mismatch: bool = False`；`_probe` 的 mismatch 分支设 `True`——adapter 需要区分「断连」与「版本不匹配」两种拒绝）
- Verify: `pyproject.toml`（只核对 Task 0 已定义 `[project.scripts] blender-codex-server = "server.mcp.adapter:main"`；本任务不得重复追加表）

**SDK v2 提示**：`mcp.server.fastmcp` 在 v2 中**已不存在**（实测 `ModuleNotFoundError`）；本任务一律用 `from mcp.server import MCPServer`。装饰器 `@mcp.tool()`、`instructions=` 构造参数与 `mcp.run()` 的用法与 v1 一致。
- Test: `tests/unit/test_adapter.py`

**Interfaces:**
- Produces:
  - `class ToolFailure(Exception)`：属性 `code: str`、`retryable: bool`；message 格式 `"{code}: {detail}"`
  - `status_impl(discovery, instance_selector: str | None = None) -> dict`（§6.1 形状；单一绝对 3 s deadline；模块级共享固定 8-worker pool + aggregation lock；没有 connected 行时返回 guidance；Bridge 失败使 cache 失效；审计由统一 middleware 接线）
  - `scene_summary_impl(discovery, instance_id: str, include_collections: bool = True, include_managed_objects: bool = True) -> dict`（§6.2 形状；补 `instance_id`/`version_warning` 两个 Server 侧字段；`INSTANCE_NOT_FOUND` / `ENVELOPE_VERSION_MISMATCH` / `BRIDGE_UNAVAILABLE` 按 §5 表抛 `ToolFailure`）
  - `capabilities_impl(discovery, include_instances: bool = False) -> dict`（§6.3；默认纯本地）
  - `main() -> None`（`mcp.run()`，stdio）
- `status_impl` / `scene_summary_impl` / `capabilities_impl(include_instances=True)` 只消费 `instances_with_stats()` / `find_with_stats()` 返回的原子配对，不得先取实例再独立读取 `last_scan`
- 审计 `request_id` 取入站 JSON-RPC id；业务 core deadline 与独立 ≤1 s audit postlude 分离，审计初始化/锁/写入失败以 retryable `AUDIT_UNAVAILABLE` fail-closed，可覆盖业务结果
- Pydantic `ClosedModel` + `Literal` 生成并验证顶层/嵌套封闭 outputSchema；`ServerMiddleware` 在参数绑定前读取原始 `tools/call.arguments`，未知字段同时在 legacy/2026 路径返回 `INVALID_PARAMS (-32602)`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_adapter.py
import asyncio
import hashlib
import json
import threading
import time

import pytest
from server.core.audit import AuditLog
from server.core.discovery import Instance, ScanStats
from server.mcp.adapter import (GUIDANCE, ToolFailure, capabilities_impl,
                                scene_summary_impl, status_impl)


class FakeClient:
    def __init__(self, results: dict):
        self._r = results

    def call(self, method, params=None, timeout=None):
        return self._r[method]


class FakeDiscovery:
    def __init__(self, insts, partial=False, skipped=0):
        self._i = insts
        self.last_scan = ScanStats(partial=partial, skipped_count=skipped)
        self.invalidated = False
        self.invalidate_deadline = None

    def instances(self, force=False, deadline=None):
        return self._i

    def instances_with_stats(self, force=False, deadline=None):
        return self.instances(force=force, deadline=deadline), self.last_scan

    def find(self, instance_id, deadline=None):
        return next((i for i in self._i
                     if i.session["instance_id"] == instance_id), None)

    def find_with_stats(self, instance_id, deadline=None):
        return self.find(instance_id, deadline=deadline), self.last_scan

    def invalidate(self, deadline=None):
        self.invalidated = True
        self.invalidate_deadline = deadline
        return True


def make_inst(iid="gui-1-aa", state="connected", supported=True, warning=None,
              client=None, mismatch=False):
    return Instance(session={"instance_id": iid, "pid": 1, "blender_version": "5.2.0",
                             "bridge_version": "0.1.0"},
                    state=state, blender_supported=supported, version_warning=warning,
                    client=client, envelope_mismatch=mismatch)


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "logs")


def test_status_empty_returns_guidance():
    out = status_impl(FakeDiscovery([]))
    assert out == {"ok": True, "guidance": GUIDANCE, "partial": False,
                   "skipped_count": 0, "instances": []}


def test_status_surfaces_partial_metadata_at_top_level():
    # 复审 P2：partial 是顶层元数据，不再伪装成 id 为 __partial__ 的假实例
    out = status_impl(FakeDiscovery([], partial=True, skipped=7))
    assert out["partial"] is True and out["skipped_count"] == 7
    assert all(r["instance_id"] != "__partial__" for r in out["instances"])


def test_status_uses_stats_paired_with_its_instance_snapshot():
    d = FakeDiscovery([])
    d.instances_with_stats = lambda **_kwargs: ([], ScanStats(True, 3))
    out = status_impl(d)
    assert out["partial"] is True and out["skipped_count"] == 3


def test_status_selector_no_match_is_guidance_not_error():
    d = FakeDiscovery([make_inst(client=FakeClient({"status": {}}))])
    out = status_impl(d, instance_selector="gui-9-zz")
    assert out["ok"] is True and out["instances"] == [] and out["guidance"] == GUIDANCE


def test_status_disconnected_rows_still_return_guidance():
    out = status_impl(FakeDiscovery([make_inst(state="disconnected", client=None)]))
    assert out["instances"][0]["bridge_state"] == "disconnected"
    assert out["guidance"] == GUIDANCE


def test_status_enriches_from_bridge():
    c = FakeClient({"status": {"instance_id": "gui-1-aa", "scene_path": "/tmp/x.blend",
                               "scene_revision": 4}})
    out = status_impl(FakeDiscovery([make_inst(client=c)]))
    row = out["instances"][0]
    assert row["bridge_state"] == "connected"
    assert row["scene_path"] == "/tmp/x.blend" and row["scene_revision"] == 4
    assert row["blender_supported"] is True and row["version_warning"] is None


def test_status_per_instance_timeout_is_capped_at_method_budget():
    class CapturingClient:
        def __init__(self):
            self.timeout = None

        def call(self, method, params=None, timeout=None):
            self.timeout = timeout
            return {"instance_id": "gui-1-aa", "scene_path": None,
                    "scene_revision": 0}

    client = CapturingClient()
    status_impl(FakeDiscovery([make_inst(client=client)]))
    assert client.timeout is not None
    assert 0 < client.timeout <= 2.0


def test_status_preserves_bridge_busy_state():
    from server.core.bridge_client import BridgeError

    class BusyClient:
        def call(self, method, params=None, timeout=None):
            raise BridgeError("BRIDGE_BUSY", "queue full", retryable=True)

    out = status_impl(FakeDiscovery([make_inst(client=BusyClient())]))
    assert out["instances"][0]["bridge_state"] == "busy"


def test_status_nonbusy_failure_overrides_stale_busy_snapshot():
    from server.core.bridge_client import BridgeError

    class GoneClient:
        def call(self, method, params=None, timeout=None):
            raise BridgeError("BRIDGE_UNAVAILABLE", "gone", retryable=True)

    discovery = FakeDiscovery([make_inst(state="busy", client=GoneClient())])
    out = status_impl(discovery)
    assert out["instances"][0]["bridge_state"] == "disconnected"
    assert out["guidance"] == GUIDANCE
    assert discovery.invalidated is True


def test_status_isolates_unexpected_client_failure():
    class BadClient:
        def call(self, method, params=None, timeout=None):
            raise RuntimeError("private bridge detail")

    class GoodClient:
        def call(self, method, params=None, timeout=None):
            return {"instance_id": "gui-2-deadbeef", "scene_path": None,
                    "scene_revision": 3}

    discovery = FakeDiscovery([
        make_inst(iid="gui-1-deadbeef", client=BadClient()),
        make_inst(iid="gui-2-deadbeef", client=GoodClient()),
    ])
    out = status_impl(discovery)
    rows = {row["instance_id"]: row for row in out["instances"]}
    assert rows["gui-1-deadbeef"]["bridge_state"] == "disconnected"
    assert rows["gui-2-deadbeef"]["bridge_state"] == "connected"
    assert out["partial"] is False
    assert discovery.invalidated is True


def test_status_isolates_malformed_client_payload():
    class BadClient:
        def call(self, method, params=None, timeout=None):
            return {"scene_path": [], "scene_revision": True}

    class GoodClient:
        def call(self, method, params=None, timeout=None):
            return {"instance_id": "gui-4-deadbeef", "scene_path": None,
                    "scene_revision": 4}

    discovery = FakeDiscovery([
        make_inst(iid="gui-3-deadbeef", client=BadClient()),
        make_inst(iid="gui-4-deadbeef", client=GoodClient()),
    ])
    out = status_impl(discovery)
    rows = {row["instance_id"]: row for row in out["instances"]}
    assert rows["gui-3-deadbeef"]["bridge_state"] == "disconnected"
    assert rows["gui-4-deadbeef"]["bridge_state"] == "connected"
    assert out["partial"] is False
    assert discovery.invalidated is True


def test_status_rejects_cross_instance_payload_without_hiding_healthy_instance():
    class WrongInstanceClient:
        def call(self, method, params=None, timeout=None):
            return {"instance_id": "gui-6-deadbeef", "scene_path": "/wrong.blend",
                    "scene_revision": 7}

    class GoodClient:
        def call(self, method, params=None, timeout=None):
            return {"instance_id": "gui-6-deadbeef", "scene_path": None,
                    "scene_revision": 8}

    discovery = FakeDiscovery([
        make_inst(iid="gui-5-deadbeef", client=WrongInstanceClient()),
        make_inst(iid="gui-6-deadbeef", client=GoodClient()),
    ])
    out = status_impl(discovery)
    rows = {row["instance_id"]: row for row in out["instances"]}
    assert rows["gui-5-deadbeef"]["bridge_state"] == "disconnected"
    assert rows["gui-5-deadbeef"]["scene_path"] is None
    assert rows["gui-6-deadbeef"]["bridge_state"] == "connected"
    assert rows["gui-6-deadbeef"]["scene_revision"] == 8
    assert discovery.invalidated is True


def test_status_uses_one_end_to_end_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class SlowClient:
        def call(self, method, params=None, timeout=None):
            time.sleep(0.4)  # 故意不尊重局部 timeout
            return {}

    class SlowDiscovery(FakeDiscovery):
        def instances(self, force=False, deadline=None):
            time.sleep(0.12)
            return self._i

    monkeypatch.setattr(adapter, "OVERALL_BUDGET", 0.2)
    d = SlowDiscovery([make_inst(client=SlowClient())])
    t0 = time.monotonic()
    out = status_impl(d)
    assert time.monotonic() - t0 < 0.3
    assert out["instances"][0]["bridge_state"] == "disconnected"
    assert d.invalidated is True


def test_status_submit_overhead_stays_inside_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class SlowSubmitExecutor(adapter.ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            time.sleep(0.15)
            return super().submit(*args, **kwargs)

    class SlowClient:
        def call(self, method, params=None, timeout=None):
            time.sleep(0.4)
            return {}

    monkeypatch.setattr(adapter, "OVERALL_BUDGET", 0.2)
    executor = SlowSubmitExecutor(max_workers=8)
    monkeypatch.setattr(adapter, "_STATUS_EXECUTOR", executor)
    try:
        started = time.monotonic()
        out = status_impl(FakeDiscovery([make_inst(client=SlowClient())]))
        assert time.monotonic() - started < 0.3
        assert out["instances"][0]["bridge_state"] == "disconnected"
    finally:
        executor.shutdown(wait=True)


def test_status_stops_submitting_instances_at_deadline(monkeypatch):
    import server.mcp.adapter as adapter

    class SlowSubmitExecutor(adapter.ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            time.sleep(0.03)
            return super().submit(*args, **kwargs)

    instances = [make_inst(iid=f"gui-{index + 1}-deadbeef",
                           client=FakeClient({"status": {}}))
                 for index in range(16)]
    monkeypatch.setattr(adapter, "OVERALL_BUDGET", 0.2)
    executor = SlowSubmitExecutor(max_workers=8)
    monkeypatch.setattr(adapter, "_STATUS_EXECUTOR", executor)
    try:
        started = time.monotonic()
        out = status_impl(FakeDiscovery(instances))
        assert time.monotonic() - started < 0.35
        assert out["partial"] is True and out["skipped_count"] > 0
    finally:
        executor.shutdown(wait=True)


def test_concurrent_status_calls_have_one_bounded_aggregation_pool():
    active = 0
    peak = 0
    counter_lock = threading.Lock()

    class TrackingClient:
        def call(self, method, params=None, timeout=None):
            nonlocal active, peak
            with counter_lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.02)
                return {"scene_path": None, "scene_revision": 0}
            finally:
                with counter_lock:
                    active -= 1

    instances = [make_inst(iid=f"gui-{index + 1}-deadbeef", client=TrackingClient())
                 for index in range(16)]
    discovery = FakeDiscovery(instances)
    start = threading.Barrier(12)
    results = []

    def call_status():
        start.wait()
        results.append(status_impl(discovery))

    workers = [threading.Thread(target=call_status) for _ in range(12)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=4.0)

    assert all(not worker.is_alive() for worker in workers)
    assert len(results) == 12
    assert peak <= 8


def test_scene_summary_injects_server_fields():
    c = FakeClient({"scene_summary": {"scene_hash": "sha256:x", "scene_name": "S",
                                      "scene_revision": 1, "scene_path": None,
                                      "units": {"system": "NONE", "scale_length": 1.0},
                                      "summary": {"object_count": 0, "mesh_count": 0,
                                                  "camera_count": 0, "light_count": 0,
                                                  "collections": ["C"],
                                                  "managed_objects": []}}})
    out = scene_summary_impl(FakeDiscovery([make_inst(client=c, supported=False,
                                                      warning="w")]), "gui-1-aa")
    assert out["instance_id"] == "gui-1-aa"
    assert out["version_warning"] == "w"          # 非基线：只读放行 + 警告（§4.4）


def test_scene_summary_error_mapping():
    with pytest.raises(ToolFailure) as e1:
        scene_summary_impl(FakeDiscovery([]), "gui-9-zz")
    assert e1.value.code == "INSTANCE_NOT_FOUND"
    with pytest.raises(ToolFailure) as partial:
        scene_summary_impl(FakeDiscovery([], partial=True, skipped=1), "gui-9-zz")
    assert partial.value.code == "BRIDGE_UNAVAILABLE"
    assert partial.value.retryable is True
    with pytest.raises(ToolFailure) as e2:
        scene_summary_impl(FakeDiscovery([make_inst(client=None, mismatch=True,
                                                    warning="envelope v2 != v1")]),
                           "gui-1-aa")
    assert e2.value.code == "ENVELOPE_VERSION_MISMATCH"
    with pytest.raises(ToolFailure) as e3:
        scene_summary_impl(FakeDiscovery([make_inst(state="disconnected", client=None)]),
                           "gui-1-aa")
    assert e3.value.code == "BRIDGE_UNAVAILABLE" and e3.value.retryable is True


def test_scene_summary_uses_stats_paired_with_its_instance_snapshot():
    d = FakeDiscovery([])
    d.find_with_stats = lambda *_args, **_kwargs: (None, ScanStats(True, 1))
    with pytest.raises(ToolFailure) as exc:
        scene_summary_impl(d, "gui-9-zz")
    assert exc.value.code == "BRIDGE_UNAVAILABLE"


def test_scene_summary_uses_one_end_to_end_deadline(monkeypatch):
    import server.mcp.adapter as adapter
    from server.core.bridge_client import BridgeError

    class SlowClient:
        def call(self, method, params=None, timeout=None):
            time.sleep(timeout if timeout is not None else 0.25)
            raise BridgeError("BRIDGE_TIMEOUT", method, retryable=True)

    class SlowDiscovery(FakeDiscovery):
        def find(self, instance_id, deadline=None):
            time.sleep(0.06)
            return self._i[0]

    monkeypatch.setattr(adapter, "SCENE_SUMMARY_BUDGET", 0.1)
    started = time.monotonic()
    with pytest.raises(ToolFailure) as exc:
        scene_summary_impl(SlowDiscovery([make_inst(client=SlowClient())]), "gui-1-aa")
    assert exc.value.code == "BRIDGE_TIMEOUT"
    assert time.monotonic() - started < 0.18


def test_scene_summary_preserves_busy_retryability():
    from server.core.bridge_client import BridgeError

    class BusyClient:
        def call(self, method, params=None, timeout=None):
            raise BridgeError("BRIDGE_BUSY", "queue full", retryable=True)

    with pytest.raises(ToolFailure) as exc:
        scene_summary_impl(FakeDiscovery([make_inst(client=BusyClient())]), "gui-1-aa")
    assert exc.value.code == "BRIDGE_BUSY" and exc.value.retryable is True


@pytest.mark.asyncio
async def test_scene_summary_server_admission_spans_sdk_conversion(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    two_entered = threading.Event()
    release_bodies = threading.Event()
    conversion_entered = threading.Event()
    release_conversion = threading.Event()
    lock = threading.Lock()
    body_calls = 0
    observed_calls = []
    controller_errors = []
    valid = {
        "instance_id": "gui-1-aa", "scene_name": "S", "scene_revision": 1,
        "scene_hash": "sha256:x", "scene_path": None, "version_warning": None,
        "units": {"system": "NONE", "scale_length": 1.0},
        "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                    "light_count": 0, "collections": [], "managed_objects": []},
    }

    def blocking_impl(*_args, **_kwargs):
        nonlocal body_calls
        with lock:
            body_calls += 1
            if body_calls == 2:
                two_entered.set()
        assert release_bodies.wait(2.0)
        return valid

    tool = adapter.mcp._tool_manager._tools["get_scene_summary"]
    metadata_cls = type(tool.fn_metadata)
    original_convert = metadata_cls.convert_result

    def blocking_convert(metadata, result):
        conversion_entered.set()
        assert release_conversion.wait(2.0)
        return original_convert(metadata, result)

    def control():
        if not two_entered.wait(1.0):
            controller_errors.append("two tool bodies did not enter")
        release_bodies.set()
        if not conversion_entered.wait(1.0):
            controller_errors.append("SDK conversion did not start")
        time.sleep(0.05)
        with lock:
            observed_calls.append(body_calls)
        release_conversion.set()

    monkeypatch.setattr(adapter, "scene_summary_impl", blocking_impl)
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    monkeypatch.setattr(adapter, "_SCENE_SUMMARY_ADMISSION",
                        threading.BoundedSemaphore(2))
    monkeypatch.setattr(metadata_cls, "convert_result", blocking_convert)
    controller = threading.Thread(target=control)
    controller.start()
    try:
        async with Client(adapter.mcp) as client:
            outcomes = await asyncio.gather(*(
                client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
                for _ in range(3)), return_exceptions=True)
            retry = await client.call_tool(
                "get_scene_summary", {"instance_id": "gui-1-aa"})
    finally:
        release_bodies.set()
        release_conversion.set()
        controller.join(timeout=2.0)
    errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    successes = [outcome for outcome in outcomes if not isinstance(outcome, BaseException)]
    assert controller_errors == [] and observed_calls == [2]
    assert len(successes) == 2 and all(not result.is_error for result in successes)
    assert len(errors) == 1 and isinstance(errors[0], MCPError)
    assert errors[0].data == {"code": "BRIDGE_BUSY", "retryable": True}
    assert retry.is_error is False and body_calls == 3


@pytest.mark.asyncio
async def test_scene_summary_server_admission_releases_after_exception(audit,
                                                                       monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    calls = 0

    def flaky(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise RuntimeError("boom")
        return {
            "instance_id": "gui-1-aa", "scene_name": "S", "scene_revision": 1,
            "scene_hash": "sha256:x", "scene_path": None, "version_warning": None,
            "units": {"system": "NONE", "scale_length": 1.0},
            "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                        "light_count": 0, "collections": [], "managed_objects": []},
        }

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    monkeypatch.setattr(adapter, "scene_summary_impl", flaky)
    monkeypatch.setattr(adapter, "_SCENE_SUMMARY_ADMISSION",
                        threading.BoundedSemaphore(2))
    async with Client(adapter.mcp) as client:
        for _ in range(2):
            result = await client.call_tool(
                "get_scene_summary", {"instance_id": "gui-1-aa"})
            assert result.is_error is True
        result = await client.call_tool(
            "get_scene_summary", {"instance_id": "gui-1-aa"})
    assert result.is_error is False


def test_capabilities_is_local_by_default():
    # 复审 F-07：默认不碰 Bridge——Blender 离线时也必须能回答
    class ExplodingDiscovery:
        last_scan = ScanStats()

        def instances(self, force=False, deadline=None):
            raise AssertionError("describe_capabilities 不得触碰 Bridge")

    out = capabilities_impl(ExplodingDiscovery())
    assert out["phase"] == "phase0" and out["connected_instances"] == []
    assert out["instances_partial"] is False and out["instances_skipped_count"] == 0


def test_capabilities_lists_connected_when_requested():
    out = capabilities_impl(FakeDiscovery([make_inst(client=FakeClient({}))],
                                                    partial=True, skipped=4),
                            include_instances=True)
    assert out["phase"] == "phase0"
    assert out["connected_instances"][0]["instance_id"] == "gui-1-aa"
    assert out["instances_partial"] is True and out["instances_skipped_count"] == 4


def test_capabilities_uses_stats_paired_with_its_instance_snapshot():
    d = FakeDiscovery([])
    d.instances_with_stats = lambda **_kwargs: ([], ScanStats(True, 2))
    out = capabilities_impl(d, include_instances=True)
    assert out["instances_partial"] is True and out["instances_skipped_count"] == 2


def _audit_rows(tmp_path):
    f = next((tmp_path / "logs").glob("server-*.jsonl"))
    return [json.loads(line) for line in f.read_text().splitlines()]


@pytest.mark.asyncio
async def test_mcp_boundary_audits_success_and_unknown_arguments(audit, tmp_path,
                                                                 monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_blender_status", {})
        assert result.is_error is False
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_blender_status", {"unexpected": 1})
        assert exc.value.code == -32602

    rows = _audit_rows(tmp_path)
    assert len(rows) == 2
    assert rows[0]["tool"] == "get_blender_status" and rows[0]["ok"] is True
    assert rows[1]["ok"] is False and rows[1]["error"] == "-32602"


@pytest.mark.asyncio
async def test_mcp_boundary_rejects_sdk_type_coercion(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool(
                "describe_capabilities", {"include_instances": "false"})
    assert exc.value.code == -32602
    assert exc.value.data == {
        "tool": "describe_capabilities", "argument": "include_instances"}
    row = _audit_rows(tmp_path)[0]
    assert row["ok"] is False and row["error"] == "-32602"


@pytest.mark.asyncio
async def test_audit_covers_all_scene_summary_arguments(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    c = FakeClient({"scene_summary": {
        "scene_hash": "sha256:x", "scene_name": "S", "scene_revision": 1,
        "scene_path": None, "units": {"system": "NONE", "scale_length": 1.0},
        "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                    "light_count": 0, "collections": [], "managed_objects": []}}})
    discovery = FakeDiscovery([make_inst(client=c)])
    monkeypatch.setattr(adapter, "_deps_cache", (discovery, audit))
    arguments = {"instance_id": "gui-1-aa", "include_collections": False,
                 "include_managed_objects": False}
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_scene_summary", arguments)
        assert result.is_error is False

    row = _audit_rows(tmp_path)[0]
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    assert row["params_digest"] == hashlib.sha256(canonical.encode()).hexdigest()[:16]


@pytest.mark.asyncio
async def test_output_validation_failure_is_audited(audit, tmp_path, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    # Pydantic's default mode would coerce integer 1 to true despite the boolean schema.
    monkeypatch.setattr(adapter, "status_impl", lambda *_args, **_kwargs: {"ok": 1})
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_blender_status", {})
        assert result.is_error is True

    row = _audit_rows(tmp_path)[0]
    assert row["ok"] is False and row["error"] == "TOOL_ERROR"


@pytest.mark.asyncio
async def test_audit_failure_is_structured_and_fail_closed(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    def fail_record(*_args, **_kwargs):
        raise TimeoutError("audit deadline expired")

    monkeypatch.setattr(audit, "record", fail_record)
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_blender_status", {})
    assert exc.value.code == -32000
    assert exc.value.data == {"code": "AUDIT_UNAVAILABLE", "retryable": True}


@pytest.mark.asyncio
async def test_audit_initialization_failure_is_structured(monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    def fail_deps():
        raise PermissionError("private directory required: /sensitive/runtime")

    monkeypatch.setattr(adapter, "_deps", fail_deps)
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("describe_capabilities", {})
    assert exc.value.code == -32000
    assert exc.value.data == {"code": "AUDIT_UNAVAILABLE", "retryable": True}
    assert "/sensitive/runtime" not in str(exc.value)


@pytest.mark.asyncio
async def test_audit_postlude_receives_one_absolute_deadline(audit, monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client

    remaining = []

    def capture_record(*_args, deadline=None, **_kwargs):
        assert deadline is not None
        remaining.append(deadline - time.monotonic())

    monkeypatch.setattr(audit, "record", capture_record)
    monkeypatch.setattr(adapter, "_deps_cache", (FakeDiscovery([]), audit))
    async with Client(adapter.mcp) as client:
        result = await client.call_tool("get_blender_status", {})
    assert result.is_error is False
    assert len(remaining) == 1
    assert 0 < remaining[0] <= adapter.AUDIT_LOCK_TIMEOUT


@pytest.mark.asyncio
async def test_scene_summary_mcp_error_has_domain_code_and_retryable(audit, tmp_path,
                                                                     monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    discovery = FakeDiscovery([make_inst(state="disconnected", client=None)])
    monkeypatch.setattr(adapter, "_deps_cache", (discovery, audit))
    async with Client(adapter.mcp) as client:
        with pytest.raises(MCPError) as exc:
            await client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
    assert exc.value.code == -32000
    assert exc.value.data == {"code": "BRIDGE_UNAVAILABLE", "retryable": True}
    row = _audit_rows(tmp_path)[0]
    assert row["ok"] is False and row["error"] == "BRIDGE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scene_summary_rejects_malformed_bridge_payloads(audit, tmp_path,
                                                                monkeypatch):
    import server.mcp.adapter as adapter
    from mcp import Client
    from mcp.shared.exceptions import MCPError

    valid = {
        "scene_hash": "sha256:x", "scene_name": "S", "scene_revision": 1,
        "scene_path": None, "units": {"system": "NONE", "scale_length": 1.0},
        "summary": {"object_count": 0, "mesh_count": 0, "camera_count": 0,
                    "light_count": 0, "collections": [], "managed_objects": []},
    }

    class MalformedClient:
        def __init__(self):
            pair_list = [[key, value] for key, value in valid["summary"].items()]
            self.results = [
                {"summary": {}},
                {**valid, "scene_revision": "1"},
                {**valid, "summary": pair_list},
            ]

        def call(self, *_args, **_kwargs):
            return self.results.pop(0)

    discovery = FakeDiscovery([make_inst(client=MalformedClient())])
    monkeypatch.setattr(adapter, "_deps_cache", (discovery, audit))
    async with Client(adapter.mcp) as client:
        for _ in range(3):
            with pytest.raises(MCPError) as exc:
                await client.call_tool("get_scene_summary", {"instance_id": "gui-1-aa"})
            assert exc.value.code == -32000
            assert exc.value.data == {"code": "BRIDGE_UNAVAILABLE", "retryable": True}

    assert discovery.invalidated is True
    assert [row["error"] for row in _audit_rows(tmp_path)] == [
        "BRIDGE_UNAVAILABLE", "BRIDGE_UNAVAILABLE", "BRIDGE_UNAVAILABLE"]
```

- [ ] **Step 2: 跑测试确认失败** → `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_adapter.py -q`

- [ ] **Step 3: 核对 discovery.py 与 pyproject.toml**（`envelope_mismatch` 字段/mismatch 分支已并入 Task 11；console entry point 已由 Task 0 定义。本步只核对，不重复修改或追加 `[project.scripts]`）

- [ ] **Step 4: 实现 adapter**

```python
# server/mcp/adapter.py
"""SDK v2 MCP 适配：封闭 schema、严格参数、结构化返回、审计与错误映射。"""
from __future__ import annotations

import contextvars
import threading
import time
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS
from pydantic import BaseModel, ConfigDict

from protocol import envelope
from server.core import config
from server.core.audit import AUDIT_LOCK_TIMEOUT, AuditLog
from server.core.bridge_client import BridgeError
from server.core.capabilities import describe
from server.core.discovery import Discovery, Instance

SERVER_VERSION = "0.1.0"
OVERALL_BUDGET = 3.0        # §4.2：status core 预算；audit 是独立有界 postlude
SCENE_SUMMARY_BUDGET = 15.0
_ACTIVE_DEADLINE: contextvars.ContextVar[float | None] = contextvars.ContextVar("bcx_request_deadline", default=None)
_STATUS_AGGREGATION_LOCK = threading.Lock()
_STATUS_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bcx-status")
_SCENE_SUMMARY_ADMISSION = threading.BoundedSemaphore(2)
GUIDANCE = "未发现可用的 Blender 实例。请在 Blender 的 3D 视口按 N 打开侧栏 → 「Codex」页签 → 点击「允许 Codex 连接」，然后重试。"
INSTRUCTIONS = ("Blender 只读控制通道（Phase 0）。调用任何工具前先 get_blender_status；若无实例，引导用户在 Blender 3D 视口按 N → "
                "「Codex」页签 → 点击「允许 Codex 连接」。本 Server 无写工具，不要尝试让 Blender 执行代码。describe_capabilities 可在 Blender 离线时回答。")


def _request_deadline(budget: float) -> float:
    return _ACTIVE_DEADLINE.get() or time.monotonic() + budget

TOOL_ARGUMENTS: dict[str, frozenset[str]] = {
    "get_blender_status": frozenset({"instance_selector"}),
    "get_scene_summary": frozenset({"instance_id", "include_collections", "include_managed_objects"}),
    "describe_capabilities": frozenset({"include_instances"}),
}
TOOL_ARGUMENT_TYPES: dict[str, dict[str, tuple[type, ...]]] = {
    "get_blender_status": {"instance_selector": (str, type(None))},
    "get_scene_summary": {"instance_id": (str,), "include_collections": (bool,),
                           "include_managed_objects": (bool,)},
    "describe_capabilities": {"include_instances": (bool,)},
}


async def _audit_and_validate_tool_call(
        ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
    """协议边界统一审计；在 SDK 丢弃未知字段前强制封闭 schema。"""
    if ctx.method != "tools/call" or ctx.params is None:
        return await call_next(ctx)
    name = ctx.params.get("name")
    arguments = ctx.params.get("arguments", {})
    safe_args = dict(arguments) if isinstance(arguments, Mapping) else {}
    tool = name if isinstance(name, str) else "<invalid>"
    started = time.monotonic()
    budget = SCENE_SUMMARY_BUDGET if tool == "get_scene_summary" else OVERALL_BUDGET
    request_deadline = started + budget
    deadline_token = _ACTIVE_DEADLINE.set(request_deadline)
    try:
        audit = _deps()[1]
    except Exception as exc:
        _ACTIVE_DEADLINE.reset(deadline_token)
        raise MCPError(-32000, "audit unavailable",
                       {"code": "AUDIT_UNAVAILABLE", "retryable": True}) from exc
    except BaseException:
        _ACTIVE_DEADLINE.reset(deadline_token)
        raise
    error: str | None = None
    admitted = False
    try:
        allowed = TOOL_ARGUMENTS.get(tool)
        if allowed is not None and isinstance(arguments, Mapping):
            unknown = sorted(set(arguments) - allowed)
            if unknown:
                raise MCPError(INVALID_PARAMS, f"unknown arguments for {tool}: {unknown}",
                               {"tool": tool, "unknown": unknown})
            for argument, expected in TOOL_ARGUMENT_TYPES[tool].items():
                if argument in arguments and type(arguments[argument]) not in expected:
                    raise MCPError(
                        INVALID_PARAMS,
                        f"invalid type for {tool}.{argument}",
                        {"tool": tool, "argument": argument},
                    )
        if tool == "get_scene_summary":
            admitted = _SCENE_SUMMARY_ADMISSION.acquire(blocking=False)
            if not admitted:
                raise MCPError(-32000, "scene summary capacity exhausted",
                               {"code": envelope.BRIDGE_BUSY, "retryable": True})
        result = await call_next(ctx)
        is_error = (getattr(result, "is_error", False)
                    or (isinstance(result, Mapping) and result.get("isError") is True))
        if is_error:
            error = "TOOL_ERROR"
        return result
    except BaseException as exc:
        data = getattr(exc, "data", None)
        domain_code = data.get("code") if isinstance(data, Mapping) else None
        error = domain_code if isinstance(domain_code, str) \
            else str(getattr(exc, "code", type(exc).__name__))
        raise
    finally:
        instance_id = safe_args.get("instance_id")
        request_id = ctx.request_id if ctx.request_id is not None else "<missing>"
        try:
            audit_deadline = time.monotonic() + AUDIT_LOCK_TIMEOUT
            audit.record(tool, request_id, ok=error is None,
                         duration_ms=(time.monotonic() - started) * 1000,
                         instance_id=instance_id if isinstance(instance_id, str) else None,
                         params=safe_args, error=error, deadline=audit_deadline)
        except Exception as exc:
            raise MCPError(-32000, "audit unavailable",
                           {"code": "AUDIT_UNAVAILABLE", "retryable": True}) from exc
        finally:
            if admitted:
                _SCENE_SUMMARY_ADMISSION.release()
            _ACTIVE_DEADLINE.reset(deadline_token)


mcp = MCPServer("blender-codex", instructions=INSTRUCTIONS,
                middleware=[_audit_and_validate_tool_call])
_deps_cache: tuple[Discovery, AuditLog] | None = None


class ToolFailure(Exception):
    def __init__(self, code: str, detail: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.retryable = retryable


# ---------- 结构化返回类型：SDK 据此生成封闭 outputSchema ----------
class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InstanceRow(ClosedModel):
    instance_id: str
    pid: int
    mode: Literal["gui"]
    bridge_state: Literal["connected", "disconnected", "busy"]
    blender_version: str
    blender_supported: bool
    version_warning: str | None
    scene_path: str | None
    scene_revision: int | None


class StatusResult(ClosedModel):
    ok: bool
    guidance: str | None
    partial: bool
    skipped_count: int
    instances: list[InstanceRow]


class UnitsResult(ClosedModel):
    system: Literal["NONE", "METRIC", "IMPERIAL"]
    scale_length: float


class ManagedObjectResult(ClosedModel):
    stable_id: str
    name: str
    type: str


class SummaryResult(ClosedModel):
    object_count: int
    mesh_count: int
    camera_count: int
    light_count: int
    collections: list[str]
    managed_objects: list[ManagedObjectResult]


class SceneSummaryResult(ClosedModel):
    instance_id: str
    scene_name: str
    scene_revision: int
    scene_hash: str
    scene_path: str | None
    version_warning: str | None
    units: UnitsResult
    summary: SummaryResult


class BaselineResult(ClosedModel):
    version: str
    platform: str


class ConnectedInstanceResult(ClosedModel):
    instance_id: str
    blender_version: str
    bridge_version: str


class CapabilitiesResult(ClosedModel):
    server_version: str
    envelope_version: int
    phase: Literal["phase0"]
    supported_tools: list[str]
    baseline_blender: BaselineResult
    ir_schema_version: str | None
    supported_operation_kinds: list[str]
    connected_instances: list[ConnectedInstanceResult]
    instances_partial: bool
    instances_skipped_count: int


def _deps() -> tuple[Discovery, AuditLog]:
    global _deps_cache
    if _deps_cache is None:                      # 惰性：不在 import 期扫描（§5.3）
        _deps_cache = (Discovery(config.run_dir()), AuditLog(config.logs_dir()))
    return _deps_cache


def _row(inst: Instance) -> dict[str, Any]:
    s = inst.session
    return {"instance_id": s["instance_id"], "pid": s.get("pid", -1), "mode": "gui",
            "bridge_state": inst.state, "blender_version": s.get("blender_version", "?"),
            "blender_supported": inst.blender_supported,
            "version_warning": inst.version_warning,
            "scene_path": None, "scene_revision": None}


def status_impl(discovery: Discovery,
                instance_selector: str | None = None) -> dict[str, Any]:
    # 单一绝对 deadline 贯穿发现与聚合（F-02：原实现把 2.5s 扫描与
    # 3s 聚合串联，最坏 5.5s，声称的「整体 3s」不成立）
    deadline = _request_deadline(OVERALL_BUDGET)
    discovered, stats = discovery.instances_with_stats(deadline=deadline)
    insts = list(discovered)
    partial, skipped_count = stats.partial, stats.skipped_count
    if instance_selector is not None:
        insts = [i for i in insts
                 if i.session["instance_id"] == instance_selector]  # 精确匹配
    live = [i for i in insts if i.client is not None]
    extra: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    invalidate = False
    lock_acquired = False
    if live and deadline - time.monotonic() > 0:
        lock_acquired = _STATUS_AGGREGATION_LOCK.acquire(
            timeout=max(0.0, deadline - time.monotonic()))
    if live and not lock_acquired:
        partial = True
        skipped_count += len(live)
    elif lock_acquired:
        def call_status(inst: Instance) -> dict[str, Any]:
            remaining = min(envelope.METHOD_TIMEOUTS["status"],
                            deadline - time.monotonic())
            if remaining <= 0:
                raise BridgeError("BRIDGE_TIMEOUT", "status", retryable=True)
            assert inst.client is not None
            result = inst.client.call("status", None, remaining)
            if (type(result) is not dict
                    or type(result.get("instance_id")) is not str
                    or result["instance_id"] != inst.session["instance_id"]
                    or type(result.get("scene_revision")) is not int
                    or "scene_path" not in result or type(result.get("scene_path")) not in (str, type(None))):
                raise ValueError("malformed status result")
            return result

        futs: dict[Future[dict[str, Any]], Instance] = {}
        try:
            for index, inst in enumerate(live):
                if time.monotonic() >= deadline:
                    partial = True
                    skipped_count += len(live) - index
                    break
                futs[_STATUS_EXECUTOR.submit(call_status, inst)] = inst
            completed = 0
            try:
                for f in as_completed(
                        futs, timeout=max(0.0, deadline - time.monotonic())):
                    completed += 1
                    try:
                        extra[futs[f].session["instance_id"]] = f.result()
                    except BridgeError as exc:
                        iid = futs[f].session["instance_id"]
                        failures[iid] = exc.code
                        if exc.code != "BRIDGE_BUSY":
                            invalidate = True
                    except Exception:
                        # A single unexpected client failure must not abort the
                        # aggregate or hide healthy instances.  Do not expose the
                        # exception text across the MCP boundary.
                        failures[futs[f].session["instance_id"]] = envelope.BRIDGE_UNAVAILABLE
                        invalidate = True
            except TimeoutError:
                partial = True
                skipped_count += len(futs) - completed
                invalidate = True
        finally:
            for future in futs:
                future.cancel()
            _STATUS_AGGREGATION_LOCK.release()
    if invalidate:
        if not discovery.invalidate(deadline=deadline):
            partial = True
            skipped_count += 1
    rows: list[dict[str, Any]] = []
    for inst in insts:
        row = _row(inst)
        e = extra.get(row["instance_id"])
        if e is not None:
            row["bridge_state"] = "connected"
            row["scene_path"] = e.get("scene_path")
            row["scene_revision"] = e.get("scene_revision")
        elif failures.get(row["instance_id"]) == "BRIDGE_BUSY":
            row["bridge_state"] = "busy"
        elif row["instance_id"] in failures:
            row["bridge_state"] = "disconnected"   # 单实例失败不影响其余
        elif inst.client is not None and row["bridge_state"] != "busy":
            row["bridge_state"] = "disconnected"   # 单实例失败不影响其余
        rows.append(row)
    connected = any(row["bridge_state"] == "connected" for row in rows)
    return {"ok": True, "guidance": None if connected else GUIDANCE,
            "partial": partial, "skipped_count": skipped_count,
            "instances": rows}


def scene_summary_impl(discovery: Discovery, instance_id: str,
                       include_collections: bool = True,
                       include_managed_objects: bool = True) -> dict[str, Any]:
    deadline = _request_deadline(SCENE_SUMMARY_BUDGET)
    inst, stats = discovery.find_with_stats(instance_id, deadline=deadline)
    if inst is None:
        if stats.partial:
            raise ToolFailure("BRIDGE_UNAVAILABLE", "discovery incomplete", retryable=True)
        raise ToolFailure("INSTANCE_NOT_FOUND", instance_id)
    if inst.envelope_mismatch:
        raise ToolFailure("ENVELOPE_VERSION_MISMATCH", inst.version_warning or "")
    if inst.client is None:
        raise ToolFailure("BRIDGE_UNAVAILABLE", "bridge disconnected", retryable=True)
    try:
        result = inst.client.call("scene_summary", {
            "include_collections": include_collections,
            "include_managed_objects": include_managed_objects,
        }, timeout=max(0.0, deadline - time.monotonic()))
    except BridgeError as e:
        discovery.invalidate(deadline=deadline)
        raise ToolFailure(e.code, str(e), retryable=e.retryable) from e
    summary = result.get("summary")
    if type(summary) is not dict:
        raise ValueError("malformed scene_summary summary")
    if not include_collections:
        summary["collections"] = []
    if not include_managed_objects:
        summary["managed_objects"] = []
    return {
        "instance_id": instance_id,
        "scene_name": result["scene_name"],
        "scene_revision": result["scene_revision"],
        "scene_hash": result["scene_hash"],
        "scene_path": result.get("scene_path"),
        "version_warning": inst.version_warning,   # §4.4：非基线附警告
        "units": result["units"],
        "summary": summary,
    }


def capabilities_impl(discovery: Discovery,
                      include_instances: bool = False) -> dict[str, Any]:
    """静态能力回答；默认不触碰 Bridge，确保 Blender 离线时也能回答。"""
    connected: list[dict[str, Any]] = []
    partial = False
    skipped_count = 0
    if include_instances:
        deadline = _request_deadline(OVERALL_BUDGET)
        instances, stats = discovery.instances_with_stats(deadline=deadline)
        connected = [i.session for i in instances if i.client is not None]
        partial = stats.partial
        skipped_count = stats.skipped_count
    result = describe(SERVER_VERSION, connected)
    result["instances_partial"] = partial
    result["instances_skipped_count"] = skipped_count
    return result


@mcp.tool()
def get_blender_status(instance_selector: str | None = None) -> StatusResult:
    """列出 Blender 实例、Bridge 连接状态与场景概况。无实例时返回引导文案。"""
    d, _a = _deps()
    return StatusResult.model_validate(status_impl(d, instance_selector))


@mcp.tool()
def get_scene_summary(instance_id: str, include_collections: bool = True,
                      include_managed_objects: bool = True) -> SceneSummaryResult:
    """返回指定实例的场景摘要：对象统计、单位、scene_hash 与受管对象清单。"""
    d, _a = _deps()
    try:
        return SceneSummaryResult.model_validate(
            scene_summary_impl(d, instance_id, include_collections,
                               include_managed_objects))
    except ToolFailure as exc:
        raise MCPError(-32000, str(exc),
                       {"code": exc.code, "retryable": exc.retryable}) from exc
    except (KeyError, TypeError, ValueError) as exc:
        # Expired business deadlines only schedule non-blocking invalidation.
        d.invalidate(deadline=time.monotonic())
        raise MCPError(-32000, "malformed scene_summary result",
                       {"code": envelope.BRIDGE_UNAVAILABLE,
                        "retryable": True}) from exc


@mcp.tool()
def describe_capabilities(include_instances: bool = False) -> CapabilitiesResult:
    """返回本 Server 能力：支持的工具、IR 版本、Blender 基线。默认不连 Bridge。"""
    d, _a = _deps()
    return CapabilitiesResult.model_validate(capabilities_impl(d, include_instances))


def _close_input_schemas() -> None:
    """关闭注册工具的 inputSchema；middleware 同时负责运行时强制。"""
    for tool in mcp._tool_manager._tools.values():   # noqa: SLF001
        params = getattr(tool, "parameters", None)
        if isinstance(params, dict):
            params["additionalProperties"] = False


_close_input_schemas()


def main() -> None:
    mcp.run()          # stdio；日志走 stderr（NFR-O1）


if __name__ == "__main__":
    main()
```


`pyproject.toml` 不在本任务追加内容；执行者只核对 Task 0 的既有 console entry point。若缺失，应回到 Task 0 修正单一 `[project.scripts]` 表，不能在此重复定义。

- [ ] **Step 5: 跑测试确认通过** → frozen 环境下 `pytest tests/unit/test_adapter.py -q` 为 **35 passed**，v8 全量物化树 `pytest tests/unit/ -q` 为 **275 passed**、全套为 **307 passed（unit 275 + contract 32）**；`awk 'NF && $1 !~ /^#/ {n++} END{exit n>375}' server/mcp/adapter.py`（实质代码 ≤ 375 行；v8 隔离实现 373 行）

- [ ] **Step 6: Commit**

```bash
git add server/mcp/adapter.py server/core/discovery.py tests/unit/test_adapter.py
git commit -m "feat(server-mcp): MCP SDK v2 三工具、并发聚合、审计接线、错误映射"
```

---

### Task 13: bridge/blender/（bpy 适配层）+ 根 shim

**需要 Blender**（已装 5.2.0）。SceneReader continuation 由 6 个不依赖真 `bpy` 的 pytest 用例验证；driver 的注册回滚、handler 接线、自愈与 cleanup 重试由 7 个 pytest 函数（参数化后 8 cases）验证。真实 bpy 仍靠 `--background` 脚本，timer 触发行为归 Task 18 L3（SPIKE-1.1：background 下 timer 不触发，故此处手动泵 tick）。

**Files:**
- Create: `bridge/blender/__init__.py`、`bridge/blender/scene_reader.py`、`bridge/blender/driver.py`、`bridge/blender/panel.py`、`bridge/__init__.py`、`smoke/bg_check.py`、`tests/unit/test_scene_reader.py`、`tests/unit/test_driver.py`

**Interfaces:**
- Consumes: `BridgeSession`、`SceneReader` 协议、`scene_hash`
- Produces:
  - `driver.start() -> None`；`driver.stop() -> bool`；`driver.running() -> bool`；`driver.session() -> BridgeSession | None`
  - operators：`bcx.allow_connect`、`bcx.disconnect`；panel 页签名 `Codex`（GUIDANCE 文案与此一致）
  - 根包 `bridge/__init__.py`：bpy 存在时才暴露 `register/unregister`（否则 pytest `import bridge.core` 会因根包连锁 import bpy 而炸）

- [ ] **Step 1: 实现 scene_reader.py**

```python
# bridge/blender/scene_reader.py
"""bpy 版 SceneReader。§3.5：主选 context.scene（SPIKE-1.3 已实测可用），回退 scenes[0]。"""
from __future__ import annotations

import hashlib
import heapq
from collections.abc import Generator

import bpy

from ..core import scene_hash
from ..core.contracts import (SceneSnapshot, SnapshotInvalidated,
                              SnapshotLimitExceeded)

MAX_SNAPSHOT_ITEMS = 1_000_000
MAX_SNAPSHOT_TEXT_BYTES = 64 * 1024 * 1024


class RevisionCounter:
    def __init__(self) -> None:
        self.value = 0
        self.generation = 0

    def bump(self) -> None:
        self.value += 1

    def bump_generation(self) -> None:
        """load_pre hook: invalidate every continuation before bpy frees old wrappers."""
        self.generation += 1
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

    @staticmethod
    def _object_line(obj) -> tuple[str, bool, bool, bool]:
        """Read one already-acquired wrapper and return only Python values."""
        obj_type = str(obj.type)
        matrix = tuple(float(v) for row in obj.matrix_world for v in row)
        data = getattr(obj, "data", None)
        if data is None:
            data_kind = ""
        else:
            data_rna = getattr(data, "bl_rna", None)
            data_kind = str(getattr(data_rna, "identifier", type(data).__name__))
        if obj_type == "MESH":
            if data is None:
                raise SnapshotInvalidated("mesh object has no data")
            counts = (len(data.vertices), len(data.edges), len(data.polygons))
        else:
            counts = ()
        line = scene_hash.object_line(str(obj.name), obj_type, matrix, data_kind, counts)
        return line, obj_type == "MESH", obj_type == "CAMERA", obj_type == "LIGHT"

    @staticmethod
    def _scene_info(scene_name: str) -> tuple[str, str | None, str, float]:
        scene = bpy.data.scenes.get(scene_name)
        if scene is None:
            raise SnapshotInvalidated("scene changed during snapshot")
        units = scene.unit_settings
        return (str(scene.name), bpy.data.filepath or None,
                str(units.system or "NONE"), float(units.scale_length))

    def _check_marker(self, revision: int, generation: int) -> None:
        if self._counter.value != revision or self._counter.generation != generation:
            raise SnapshotInvalidated("scene changed during snapshot")

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        """Cooperative snapshot: one bounded source/hash/collection batch per yield.

        bpy cannot safely move to a worker thread, so TaskQueue advances this generator on
        the main thread until its per-tick budget is consumed. Individual bpy property access
        remains an atomic, non-preemptible step; the queue records an honest cooperative bound.
        """
        scene = self._target_scene()
        scene_name = str(scene.name)
        object_count = len(scene.objects)
        if object_count > MAX_SNAPSHOT_ITEMS:
            raise SnapshotLimitExceeded("object item limit exceeded")
        del scene
        revision = self._counter.value
        generation = self._counter.generation
        chunks: list[tuple[str, ...]] = []
        object_text_bytes = 0
        n_mesh = n_cam = n_light = 0
        for start in range(0, object_count, 1024):
            self._check_marker(revision, generation)
            current_scene = bpy.data.scenes.get(scene_name)
            if current_scene is None or len(current_scene.objects) != object_count:
                raise SnapshotInvalidated("scene changed during snapshot")
            stop = min(start + 1024, object_count)
            try:
                # Blender's collection slice walks forward in C; numeric indexing
                # walks from the head and made the old implementation O(N²).
                batch = current_scene.objects[start:stop]
            except (ReferenceError, RuntimeError, TypeError) as exc:
                raise SnapshotInvalidated("scene changed during snapshot") from exc
            del current_scene
            batch_lines: list[str] = []
            obj = None
            try:
                for obj in batch:
                    line, is_mesh, is_camera, is_light = self._object_line(obj)
                    object_text_bytes += len(line.encode("utf-8"))
                    if object_text_bytes > MAX_SNAPSHOT_TEXT_BYTES:
                        raise SnapshotLimitExceeded("object text limit exceeded")
                    batch_lines.append(line)
                    n_mesh += is_mesh
                    n_cam += is_camera
                    n_light += is_light
            except SnapshotLimitExceeded:
                raise
            except (ReferenceError, RuntimeError, TypeError) as exc:
                raise SnapshotInvalidated("scene changed during snapshot") from exc
            finally:
                obj = None
                batch.clear()
            self._check_marker(revision, generation)
            batch_lines.sort()
            chunks.append(tuple(batch_lines))
            batch_lines.clear()
            yield

        # 必须与 scene_hash.digest() 用同一算法——本文件是它的分块增量版本，
        # 两者对同一场景必须产出逐字相同的摘要（见 test_scene_reader 的一致性用例）
        digest = hashlib.sha256()
        first = True
        hash_steps = 0
        for line in heapq.merge(*chunks):
            self._check_marker(revision, generation)
            if not first:
                digest.update(b"\n")
            digest.update(line.encode("utf-8"))
            first = False
            hash_steps += 1
            if hash_steps == 128:
                hash_steps = 0
                yield
        if hash_steps:
            yield

        # The hash is complete; release all per-object strings before optionally
        # materializing collection names so the two bounded working sets do not
        # overlap.  ``line`` is reset to release the last merge item as well.
        line = ""
        chunks.clear()

        collections: list[str] = []
        if include_collections:
            collection_count = len(bpy.data.collections)
            if collection_count > MAX_SNAPSHOT_ITEMS:
                raise SnapshotLimitExceeded("collection item limit exceeded")
            collection_text_bytes = 0
            for start in range(0, collection_count, 128):
                self._check_marker(revision, generation)
                if len(bpy.data.collections) != collection_count:
                    raise SnapshotInvalidated("scene changed during snapshot")
                stop = min(start + 128, collection_count)
                try:
                    batch = bpy.data.collections[start:stop]
                except (ReferenceError, RuntimeError, TypeError) as exc:
                    raise SnapshotInvalidated("scene changed during snapshot") from exc
                collection = None
                try:
                    names: list[str] = []
                    for collection in batch:
                        name = str(collection.name)
                        collection_text_bytes += len(name.encode("utf-8"))
                        if collection_text_bytes > MAX_SNAPSHOT_TEXT_BYTES:
                            raise SnapshotLimitExceeded("collection text limit exceeded")
                        names.append(name)
                    collections.extend(names)
                    names.clear()
                except SnapshotLimitExceeded:
                    raise
                except (ReferenceError, RuntimeError, TypeError) as exc:
                    raise SnapshotInvalidated("scene changed during snapshot") from exc
                finally:
                    collection = None
                    batch.clear()
                self._check_marker(revision, generation)
                yield
        self._check_marker(revision, generation)
        name, path, units_system, units_scale = self._scene_info(scene_name)
        self._check_marker(revision, generation)
        return SceneSnapshot(
            scene_revision=revision,
            scene_hash="sha256:" + digest.hexdigest(),
            scene_name=name,
            scene_path=path,
            units_system=units_system,
            units_scale_length=units_scale,
            object_count=object_count, mesh_count=n_mesh,
            camera_count=n_cam, light_count=n_light,
            collections=tuple(collections),
            managed_objects=(),  # Phase 0 恒空；flag 为未来受管对象源端裁剪预留
        )
```

**Unit test file:** `tests/unit/test_scene_reader.py`（完整文件；与隔离验证源逐字节一致）

```python
# tests/unit/test_scene_reader.py
import importlib
import sys
import types
from pathlib import Path

import pytest
from bridge.core import scene_hash


class _BpyWrapper:
    pass


class _NamedList(list):
    def get(self, name):
        return next((item for item in self if item.name == name), None)

    def __getitem__(self, key):
        if isinstance(key, int):
            raise AssertionError("scene reader must use bounded collection slices")
        return super().__getitem__(key)


class _MeshData(_BpyWrapper):
    def __init__(self) -> None:
        self.bl_rna = types.SimpleNamespace(identifier="Mesh")
        self.vertices = [None] * 8
        self.edges = [None] * 12
        self.polygons = [None] * 6


class _CurveData(_BpyWrapper):
    bl_rna = types.SimpleNamespace(identifier="Curve")


class _CameraData(_BpyWrapper):
    bl_rna = types.SimpleNamespace(identifier="Camera")


class _LightData(_BpyWrapper):
    bl_rna = types.SimpleNamespace(identifier="Light")


_UNSET = object()


class _Object(_BpyWrapper):
    def __init__(self, name: str, x: float, obj_type: str = "MESH", data=_UNSET) -> None:
        self.name = name
        self.type = obj_type
        if data is _UNSET:
            data = {"MESH": _MeshData(), "CAMERA": _CameraData(),
                    "LIGHT": _LightData(), "CURVE": _CurveData()}.get(obj_type)
        self.data = data
        self.matrix_world = tuple(
            tuple(float(row * 4 + column) + x for column in range(4))
            for row in range(4)
        )


class _Scene(_BpyWrapper):
    def __init__(self, objects) -> None:
        self.name = "Scene"
        self.objects = _NamedList(objects)
        self.unit_settings = types.SimpleNamespace(system="METRIC", scale_length=1.0)


class _Collection(_BpyWrapper):
    def __init__(self, name: str) -> None:
        self.name = name


def _load_scene_reader(monkeypatch, object_count: int = 2, *, mixed: bool = False,
                       collection_count: int = 2):
    scene = _Scene([_Object(f"Cube{i:04d}", float(i)) for i in range(object_count)])
    if mixed:
        scene.objects.extend([
            _Object("Camera", 0.0, "CAMERA"),
            _Object("Sun", 0.0, "LIGHT"),
            _Object("Curve", 0.0, "CURVE"),
            _Object("Empty", 0.0, "EMPTY", None),
        ])
    bpy = types.ModuleType("bpy")
    bpy.app = types.SimpleNamespace(version_string="5.2.0 LTS")
    bpy.context = types.SimpleNamespace(scene=scene)
    bpy.data = types.SimpleNamespace(
        scenes=_NamedList([scene]),
        collections=_NamedList([_Collection(f"C{i:04d}")
                                for i in range(collection_count)]),
        filepath="/tmp/a.blend",
    )
    monkeypatch.setitem(sys.modules, "bpy", bpy)

    # Import the submodule without executing bridge/blender/__init__.py, whose panel/driver
    # dependencies need the full Blender runtime. Relative imports still resolve normally.
    package = types.ModuleType("bridge.blender")
    package.__path__ = [str(Path(__file__).parents[2] / "bridge" / "blender")]
    package.__package__ = "bridge.blender"
    monkeypatch.setitem(sys.modules, "bridge.blender", package)
    monkeypatch.delitem(sys.modules, "bridge.blender.scene_reader", raising=False)
    return importlib.import_module("bridge.blender.scene_reader"), scene


def _finish(steps):
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def test_snapshot_steps_hold_no_bpy_wrappers_and_generation_invalidates(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch)
    counter = module.RevisionCounter()
    steps = module.BpySceneReader(counter).snapshot_steps()

    next(steps)
    def contains_wrapper(value, seen=None):
        if isinstance(value, _BpyWrapper):
            return True
        if seen is None:
            seen = set()
        if id(value) in seen:
            return False
        seen.add(id(value))
        if isinstance(value, dict):
            return any(contains_wrapper(v, seen) for v in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(contains_wrapper(v, seen) for v in value)
        return False

    assert not any(contains_wrapper(value)
                   for value in steps.gi_frame.f_locals.values())

    counter.bump_generation()
    with pytest.raises(module.SnapshotInvalidated, match="scene changed"):
        next(steps)


def test_snapshot_steps_preserve_hash_and_optional_collections(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch)
    snapshot = _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
        include_collections=False,
    ))
    lines = [scene_hash.object_line(
        obj.name, obj.type, tuple(value for row in obj.matrix_world for value in row),
        "Mesh", (8, 12, 6),
    ) for obj in scene.objects]

    assert snapshot.scene_hash == scene_hash.digest(lines)
    assert snapshot.object_count == 2 and snapshot.mesh_count == 2
    assert snapshot.collections == ()


def test_object_line_uses_data_rna_identifier_and_handles_empty_data(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch)
    curve = _Object("Curve", 0.0)
    curve.type = "CURVE"
    curve.data = _CurveData()
    line, is_mesh, is_camera, is_light = module.BpySceneReader._object_line(curve)
    assert line.split("\t")[3] == "Curve"
    assert (is_mesh, is_camera, is_light) == (False, False, False)

    empty = _Object("Empty", 0.0)
    empty.type = "EMPTY"
    empty.data = None
    empty_line, *_ = module.BpySceneReader._object_line(empty)
    assert empty_line.split("\t")[3] == ""


def test_snapshot_counts_and_exact_data_kinds_for_mixed_scene(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch, object_count=1025, mixed=True,
                                       collection_count=130)
    reader = module.BpySceneReader(module.RevisionCounter())
    steps = reader.snapshot_steps(include_collections=True)
    yielded = 0
    while True:
        try:
            next(steps)
        except StopIteration as done:
            snapshot = done.value
            break
        yielded += 1
        frame_locals = steps.gi_frame.f_locals
        assert all(not _contains_wrapper(value) for value in frame_locals.values())
        if "collection_text_bytes" in frame_locals:
            assert frame_locals["chunks"] == []  # object strings freed before collections

    assert yielded >= 4  # object source, hash, and 130-item collection batches
    assert (snapshot.object_count, snapshot.mesh_count,
            snapshot.camera_count, snapshot.light_count) == (1029, 1025, 1, 1)
    expected_kinds = {"MESH": "Mesh", "CAMERA": "Camera", "LIGHT": "Light",
                      "CURVE": "Curve", "EMPTY": ""}
    lines = []
    for obj in scene.objects:
        line, *_ = reader._object_line(obj)
        assert line.split("\t")[3] == expected_kinds[obj.type]
        lines.append(line)
    assert snapshot.scene_hash == scene_hash.digest(lines)


def _contains_wrapper(value, seen=None):
    if isinstance(value, _BpyWrapper):
        return True
    if seen is None:
        seen = set()
    if id(value) in seen:
        return False
    seen.add(id(value))
    if isinstance(value, dict):
        return any(_contains_wrapper(v, seen) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_wrapper(v, seen) for v in value)
    return False


def test_chunked_hash_matches_digest_across_multiple_sort_chunks(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch, object_count=2050)
    snapshot = _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
        include_collections=False,
    ))
    lines = [scene_hash.object_line(
        obj.name, obj.type, tuple(value for row in obj.matrix_world for value in row),
        "Mesh", (8, 12, 6),
    ) for obj in scene.objects]

    assert snapshot.scene_hash == scene_hash.digest(lines)


def test_scene_info_race_invalidates_before_snapshot_publish(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch)
    counter = module.RevisionCounter()
    reader = module.BpySceneReader(counter)
    original = module.BpySceneReader._scene_info

    def bump_before_return(scene_name):
        result = original(scene_name)
        counter.bump()
        return result

    monkeypatch.setattr(module.BpySceneReader, "_scene_info",
                        staticmethod(bump_before_return))
    with pytest.raises(module.SnapshotInvalidated, match="scene changed"):
        _finish(reader.snapshot_steps(include_collections=False))


def test_snapshot_reader_rejects_object_text_before_unbounded_growth(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch, object_count=2)
    monkeypatch.setattr(module, "MAX_SNAPSHOT_TEXT_BYTES", 1)
    with pytest.raises(module.SnapshotLimitExceeded, match="object text"):
        _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
            include_collections=False))


def test_snapshot_reader_caps_collection_items_and_skips_unrequested_source(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch, object_count=0,
                                       collection_count=2)
    monkeypatch.setattr(module, "MAX_SNAPSHOT_ITEMS", 1)
    with pytest.raises(module.SnapshotLimitExceeded, match="collection item"):
        _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps())

    snapshot = _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
        include_collections=False))
    assert snapshot.collections == ()
```

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_scene_reader.py -q`
Expected: `8 passed`（v8；混合对象计数与精确 RNA 类型、每次 yield wrapper-free、generation/scene-info 竞态失效、分块 hash、源端裁剪与 reader 工作集上限成立）。

- [ ] **Step 2: 写 driver 注册回滚与停机接线反例**

```python
# tests/unit/test_driver.py
import importlib
import sys
import types
from pathlib import Path

import pytest


class _HookList(list):
    def __init__(self, fail_after_append: bool = False) -> None:
        super().__init__()
        self._fail_after_append = fail_after_append

    def append(self, callback) -> None:
        super().append(callback)
        if self._fail_after_append:
            raise RuntimeError("handler registration failed")


class _Timers:
    def __init__(self, fail_after_register: bool = False) -> None:
        self.callbacks: set = set()
        self._fail_after_register = fail_after_register
        self.register_calls = 0
        self.register_kwargs: list[dict] = []

    def register(self, callback, **kwargs) -> None:
        self.register_calls += 1
        self.register_kwargs.append(kwargs)
        self.callbacks.add(callback)
        if self._fail_after_register:
            raise RuntimeError("timer registration failed")

    def is_registered(self, callback) -> bool:
        return callback in self.callbacks

    def unregister(self, callback) -> None:
        self.callbacks.remove(callback)


class _Session:
    def __init__(self) -> None:
        self.stopped = False
        self.stop_calls = 0
        self.cleanup_results = [True]

    def stop(self, *_args) -> bool:
        self.stopped = True
        self.stop_calls += 1
        return self.cleanup_results.pop(0) if self.cleanup_results else True


def _load_driver(monkeypatch, failure: str, preexisting: bool = False):
    depsgraph = _HookList()
    load_pre = _HookList(fail_after_append=failure == "handler")
    timers = _Timers(fail_after_register=failure == "timer")

    handlers = types.ModuleType("bpy.app.handlers")
    handlers.persistent = lambda callback: callback
    handlers.depsgraph_update_post = depsgraph
    handlers.load_pre = load_pre
    app = types.ModuleType("bpy.app")
    app.__path__ = []
    app.handlers = handlers
    app.timers = timers
    app.version_string = "5.2.0 LTS"
    bpy = types.ModuleType("bpy")
    bpy.__path__ = []
    bpy.app = app
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "bpy.app", app)
    monkeypatch.setitem(sys.modules, "bpy.app.handlers", handlers)

    package = types.ModuleType("bridge.blender")
    package.__path__ = [str(Path(__file__).parents[2] / "bridge" / "blender")]
    package.__package__ = "bridge.blender"
    package.register = lambda: None
    package.unregister = lambda: None
    monkeypatch.setitem(sys.modules, "bridge.blender", package)
    monkeypatch.delitem(sys.modules, "bridge.blender.driver", raising=False)
    monkeypatch.delitem(sys.modules, "bridge.blender.scene_reader", raising=False)
    driver = importlib.import_module("bridge.blender.driver")

    session = _Session()

    class _BridgeSession:
        @staticmethod
        def start(*_args, **_kwargs):
            session.stopped = False
            return session

    monkeypatch.setattr(driver, "BridgeSession", _BridgeSession)
    if preexisting:
        depsgraph.append(driver._on_depsgraph)
        load_pre.append(driver._on_load_pre)
        timers.callbacks.add(driver._tick_guard)
    return driver, depsgraph, load_pre, timers, session


def test_driver_wires_load_invalidation_and_ordered_stop_hooks():
    source = (Path(__file__).parents[2] / "bridge" / "blender" / "driver.py").read_text()
    panel_source = (Path(__file__).parents[2] / "bridge" / "blender" / "panel.py").read_text()
    assert "bpy.app.handlers.load_pre.append(_on_load_pre)" in source
    assert "c.bump_generation()" in source
    assert "session.stop(_unregister_timer, _unregister_handlers)" in source
    assert 'else {"CANCELLED"}' in panel_source
    assert "清理未完成，点击重试" in panel_source


def _load_addon(monkeypatch, classes, stop, register_class, unregister_class):
    path = Path(__file__).parents[2] / "bridge" / "blender" / "__init__.py"
    bpy = types.ModuleType("bpy")
    bpy.utils = types.SimpleNamespace(register_class=register_class,
                                      unregister_class=unregister_class)
    driver_module = types.ModuleType("bridge.blender.driver")
    driver_module.stop = stop
    panel_module = types.ModuleType("bridge.blender.panel")
    panel_module.CLASSES = classes
    bridge_package = types.ModuleType("bridge")
    bridge_package.__path__ = [str(path.parents[1])]
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(sys.modules, "bridge", bridge_package)
    monkeypatch.setitem(sys.modules, "bridge.blender.driver", driver_module)
    monkeypatch.setitem(sys.modules, "bridge.blender.panel", panel_module)
    spec = importlib.util.spec_from_file_location(
        "bridge.blender", path, submodule_search_locations=[str(path.parent)])
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "bridge.blender", module)
    spec.loader.exec_module(module)
    return module


def test_addon_unregister_preserves_ui_on_cleanup_failure(monkeypatch):
    classes = (object(), object())
    unregistered = []
    module = _load_addon(monkeypatch, classes, lambda: False, lambda _cls: None,
                         unregistered.append)

    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        module.unregister()
    assert unregistered == []


def test_addon_unregister_is_idempotent(monkeypatch):
    classes = (object(), object())
    registered, unregistered = [], []
    module = _load_addon(monkeypatch, classes, lambda: True, registered.append,
                         unregistered.append)

    module.register()
    module.unregister()
    module.unregister()

    assert registered == list(classes)
    assert unregistered == list(reversed(classes))


def test_addon_register_rolls_back_partial_class_registration(monkeypatch):
    classes = (object(), object())
    registered, unregistered = [], []

    def register_class(cls):
        registered.append(cls)
        if cls is classes[1]:
            raise RuntimeError("injected class register failure")

    module = _load_addon(monkeypatch, classes, lambda: True, register_class,
                         unregistered.append)

    with pytest.raises(RuntimeError, match="injected class register failure"):
        module.register()

    assert registered == list(classes)
    assert unregistered == [classes[0]]
    assert module._registered == []


def test_addon_register_reports_incomplete_class_rollback(monkeypatch):
    classes = (object(), object())
    rollback_failed = True
    unregistered = []

    def register_class(cls):
        if cls is classes[1]:
            raise RuntimeError("injected class register failure")

    def unregister_class(cls):
        unregistered.append(cls)
        if cls is classes[0] and rollback_failed:
            raise RuntimeError("injected rollback failure")

    module = _load_addon(monkeypatch, classes, lambda: True, register_class,
                         unregister_class)

    with pytest.raises(RuntimeError, match="class registration rollback incomplete"):
        module.register()
    assert unregistered == [classes[0]]
    assert module._registered == [classes[0]]

    rollback_failed = False
    module.unregister()
    assert module._registered == []


def test_addon_partial_unregister_failure_is_retryable(monkeypatch):
    classes = (object(), object())
    failed_once = False
    unregistered = []

    def fail_on_first_class_once(cls):
        nonlocal failed_once
        unregistered.append(cls)
        if cls is classes[0] and not failed_once:
            failed_once = True
            raise RuntimeError("injected class unregister failure")

    module = _load_addon(monkeypatch, classes, lambda: True, lambda _cls: None,
                         fail_on_first_class_once)
    module.register()
    with pytest.raises(RuntimeError, match="injected class unregister failure"):
        module.unregister()
    module.unregister()

    assert unregistered == [classes[1], classes[0], classes[0]]


@pytest.mark.parametrize("failure", ["handler", "timer"])
def test_start_registration_failure_rolls_back_without_zombie(monkeypatch, failure):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, failure)

    with pytest.raises(RuntimeError, match=f"{failure} registration failed"):
        driver.start()

    assert depsgraph == [] and load_pre == []
    assert timers.callbacks == set()
    assert session.stopped is True and session.stop_calls == 1
    assert driver._state == {"session": None, "counter": None}


def test_start_preserves_preexisting_hooks_and_does_not_duplicate_timer(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(
        monkeypatch, "none", preexisting=True)

    driver.start()

    assert depsgraph == [driver._on_depsgraph]
    assert load_pre == [driver._on_load_pre]
    assert timers.callbacks == {driver._tick_guard}
    assert timers.register_calls == 0
    assert driver._state["session"] is session and session.stopped is False
    # Test-only state cleanup; the fake session owns no sockets or threads.
    driver._state.update(session=None, counter=None)


def test_start_self_heals_missing_callbacks_for_live_session(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")
    driver.start()
    depsgraph.remove(driver._on_depsgraph)
    load_pre.remove(driver._on_load_pre)
    timers.unregister(driver._tick_guard)

    driver.start()

    assert depsgraph == [driver._on_depsgraph]
    assert load_pre == [driver._on_load_pre]
    assert timers.callbacks == {driver._tick_guard}
    assert timers.register_kwargs[-1] == {"first_interval": 0.02, "persistent": True}
    assert session.stop_calls == 0 and driver._state["session"] is session
    driver._state.update(session=None, counter=None)


def test_start_state_probe_failure_stops_published_session(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")

    def fail_probe(_callback):
        raise RuntimeError("timer state probe failed")

    monkeypatch.setattr(timers, "is_registered", fail_probe)
    with pytest.raises(RuntimeError, match="state probe failed"):
        driver.start()

    assert depsgraph == [] and load_pre == []
    assert session.stopped is True and session.stop_calls == 1
    assert driver._state == {"session": None, "counter": None}


def test_registration_rollback_retains_session_until_cleanup_retry_succeeds(
        monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "handler")
    session.cleanup_results = [False, True]

    with pytest.raises(RuntimeError, match="handler registration failed"):
        driver.start()

    assert session.stopped is True and session.stop_calls == 1
    assert driver._state["session"] is session
    assert driver.stop() is True
    assert session.stop_calls == 2
    assert driver._state == {"session": None, "counter": None}


def test_registration_rollback_uses_stop_hooks_and_retains_failed_cleanup(monkeypatch):
    driver, depsgraph, load_pre, timers, session = _load_driver(monkeypatch, "none")
    session.cleanup_results = [False, True]
    real_stop = session.stop
    stop_args = []

    def stop_with_callbacks(*callbacks):
        stop_args.append(callbacks)
        for callback in callbacks:
            callback()
        return real_stop()

    def fail_after_callbacks_escape_local_rollback():
        depsgraph.append(driver._on_depsgraph)
        load_pre.append(driver._on_load_pre)
        timers.callbacks.add(driver._tick_guard)
        raise RuntimeError("callback rollback failed")

    monkeypatch.setattr(session, "stop", stop_with_callbacks)
    monkeypatch.setattr(driver, "_ensure_callbacks",
                        fail_after_callbacks_escape_local_rollback)
    with pytest.raises(RuntimeError, match="callback rollback failed"):
        driver.start()

    assert stop_args[0] == (driver._unregister_timer, driver._unregister_handlers)
    assert depsgraph == [] and load_pre == [] and timers.callbacks == set()
    assert driver._state["session"] is session and session.stopped is True
    assert driver.stop() is True
    assert driver._state == {"session": None, "counter": None}


def test_disconnect_retains_session_until_cleanup_retry_succeeds(monkeypatch):
    driver, _depsgraph, _load_pre, _timers, session = _load_driver(monkeypatch, "none")
    driver.start()
    session.cleanup_results = [False, False, True]

    assert driver.stop() is False
    assert session.stopped is True and driver._state["session"] is session
    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        driver.start()
    assert driver._state["session"] is session and driver.running() is False

    driver.start()
    assert session.stop_calls == 3
    assert driver._state["session"] is session and driver.running() is True
    driver._state.update(session=None, counter=None)
```

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_driver.py -q`
Expected: 7 个测试函数（参数化后 8 cases）在 driver 实现前失败。

- [ ] **Step 3: 实现 driver.py**

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
from ..core.queue import IDLE_INTERVAL
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


@persistent
def _on_load_pre(_filepath) -> None:
    """在 Blender 释放旧 bpy data 前使跨 tick snapshot continuation 失效。"""
    c = _state["counter"]
    if c is not None:
        c.bump_generation()


def _tick_guard() -> float | None:                  # §3.6：护栏不可省略
    s = _state["session"]
    if s is None or s.stopped:
        return None                                  # 会话没了 → timer 自然注销
    try:
        return s.tick(50)
    except Exception:
        _diag.exception("tick failed")
        return 0.1


def _ensure_callbacks() -> None:
    """Register missing persistent callbacks, rolling back this attempt on failure."""
    depsgraph_was_registered = load_pre_was_registered = timer_was_registered = True
    try:
        depsgraph_was_registered = _on_depsgraph in bpy.app.handlers.depsgraph_update_post
        load_pre_was_registered = _on_load_pre in bpy.app.handlers.load_pre
        timer_was_registered = bpy.app.timers.is_registered(_tick_guard)
        if not depsgraph_was_registered:
            bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
        if not load_pre_was_registered:
            bpy.app.handlers.load_pre.append(_on_load_pre)
        if not timer_was_registered:
            bpy.app.timers.register(_tick_guard, first_interval=IDLE_INTERVAL, persistent=True)
    except BaseException:
        # Roll back only callbacks added by this attempt; preserve pre-existing ones.
        try:
            if not timer_was_registered and bpy.app.timers.is_registered(_tick_guard):
                bpy.app.timers.unregister(_tick_guard)
        except Exception:
            _diag.exception("failed to roll back timer registration")
        for handlers, callback, was_registered in (
            (bpy.app.handlers.load_pre, _on_load_pre, load_pre_was_registered),
            (bpy.app.handlers.depsgraph_update_post, _on_depsgraph,
             depsgraph_was_registered),
        ):
            try:
                if not was_registered and callback in handlers:
                    handlers.remove(callback)
            except Exception:
                _diag.exception("failed to roll back handler registration")
        raise


def start() -> None:
    existing = _state["session"]
    if existing is not None:
        if existing.stopped:
            if not existing.stop(_unregister_timer, _unregister_handlers):
                raise RuntimeError("previous session cleanup incomplete; retry disconnect")
            _state.update(session=None, counter=None)
        else:
            _ensure_callbacks()  # self-heal after a persistent reload drops a callback
            return
    counter = RevisionCounter()
    reader = BpySceneReader(counter)
    session = BridgeSession.start(_runtime_root(), reader,
                                  blender_version=reader.blender_version())
    try:
        _state.update(session=session, counter=counter)
        _ensure_callbacks()
    except BaseException:
        try:
            cleanup_complete = session.stop(_unregister_timer, _unregister_handlers)
        except Exception:
            _diag.exception("failed to stop session during registration rollback")
            cleanup_complete = False
        if cleanup_complete:
            _state.update(session=None, counter=None)
        raise


def _unregister_timer() -> None:
    if bpy.app.timers.is_registered(_tick_guard):    # §3.7 步 6（driver 层职责）
        bpy.app.timers.unregister(_tick_guard)


def _unregister_handlers() -> None:
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:   # 步 7
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    if _on_load_pre in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_on_load_pre)


def stop() -> bool:
    session = _state["session"]
    if session is None:
        return True
    complete = session.stop(_unregister_timer, _unregister_handlers)
    if complete:
        _state.update(session=None, counter=None)
    return complete


def running() -> bool:
    current = _state["session"]
    return current is not None and not current.stopped


def session() -> BridgeSession | None:
    return _state["session"]
```

Run: `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/unit/test_driver.py -q`
Expected: `14 passed`（v8；handler/timer/class 注册失败均完整回滚，不留 zombie session，不重复已有 hooks，cleanup 未完成时保留状态并可重试）。

- [ ] **Step 4: 实现 panel.py 与两个 `__init__.py`**

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
        return {"FINISHED"} if driver.stop() else {"CANCELLED"}


class BCX_PT_panel(bpy.types.Panel):
    bl_label = "Codex"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Codex"

    def draw(self, context):
        col = self.layout.column()
        s = driver.session()
        if s is not None:
            label = (f"已开启：{s.instance_id}" if not s.stopped
                     else "清理未完成，点击重试")
            col.label(text=label)   # §4.1：事务期提示的前身
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

_registered: list[type] = []


def register() -> None:
    start = len(_registered)
    try:
        for cls in panel.CLASSES:
            if cls in _registered:
                continue
            bpy.utils.register_class(cls)
            _registered.append(cls)
    except BaseException:
        try:
            while len(_registered) > start:
                cls = _registered[-1]
                bpy.utils.unregister_class(cls)
                _registered.pop()
        except BaseException as rollback_error:
            raise RuntimeError("class registration rollback incomplete") from rollback_error
        raise


def unregister() -> None:
    if not driver.stop():
        # Keep the panel registered so the user can press Disconnect again
        # when transport cleanup needs a retry; do not hide a live session.
        raise RuntimeError("bridge cleanup incomplete; panel remains registered")
    while _registered:
        cls = _registered[-1]
        bpy.utils.unregister_class(cls)
        _registered.pop()
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

- [ ] **Step 5: 背景模式端到端验证（手动泵 tick——SPIKE-1.1：bg 下 timer 不触发）**

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

- [ ] **Step 6: 确认 pytest 不被根 shim 破坏** → `/Users/yeminjie/.local/bin/uv run --frozen pytest -q` 全绿（`import bridge.core` 不再触发 bpy）

- [ ] **Step 7: Commit**

```bash
git add bridge/blender/ bridge/__init__.py smoke/bg_check.py \
        tests/unit/test_scene_reader.py tests/unit/test_driver.py
git commit -m "feat(bridge-blender): bpy 适配层、显式会话面板、根入口 shim、bg 验证脚本"
```

---

### Task 14: 打包——vendor 脚本、manifest、CI 检查

**Files:**
- Create: `scripts/vendor_protocol.py`、`scripts/nested_import_smoke.py`、`scripts/checks.sh`、`bridge/blender_manifest.toml`

**Interfaces:**
- Produces: `bash scripts/checks.sh` = 本项目全部 CI 检查（§9 四条 + lint + 测试）；`/Users/yeminjie/.local/bin/uv run --frozen python scripts/vendor_protocol.py` 生成 `bridge/_vendor/protocol/`，`--check` 校验一致性

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

# preflight（audit F-07/F-13）：当前非交互 PATH 不含 ~/.local/bin，使用已核实绝对路径
UV_BIN=/Users/yeminjie/.local/bin/uv
test -x "$UV_BIN" || { echo "FAIL: $UV_BIN 不可执行"; exit 1; }
echo "toolchain: uv=$($UV_BIN --version 2>&1)"

"$UV_BIN" sync --frozen --python 3.13  # ADR：锁定依赖与解释器，禁止隐式升级
"$UV_BIN" run --frozen ruff check protocol bridge server tests scripts smoke
"$UV_BIN" run --frozen mypy
# 检查 1：core 与 protocol 禁 bpy（行首匹配，避开注释/文案）
if grep -rnE '^[[:space:]]*(import bpy|from bpy)' bridge/core protocol --include='*.py'; then
  echo "FAIL: bpy import in core/protocol"; exit 1
fi
"$UV_BIN" run --frozen python scripts/vendor_protocol.py            # 生成
"$UV_BIN" run --frozen python scripts/vendor_protocol.py --check    # 检查 2
"$UV_BIN" run --frozen python scripts/nested_import_smoke.py        # 检查 3
"$UV_BIN" run --frozen pytest -q                                    # L1 + L2
echo "ALL CHECKS PASSED"
```

（§9 检查 4——语法基线 py313——由第一行 ruff 的 `target-version` 承担。）

- [ ] **Step 4: 运行验证** → `chmod +x scripts/checks.sh && bash scripts/checks.sh` 输出 `ALL CHECKS PASSED`

- [ ] **Step 5: Commit**

```bash
git add scripts/ bridge/blender_manifest.toml
git commit -m "build: vendor 脚本、嵌套 import 冒烟、manifest 与 CI 检查集"
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
from collections.abc import Generator

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
        """Counterfactual for regression tests: the old Router called this synchronously."""
        self.snapshot_calls += 1
        if self._raise is not None:
            raise self._raise
        return SceneSnapshot(
            scene_revision=1, scene_hash="sha256:fake", scene_name="Scene",
            scene_path=None, units_system="METRIC", units_scale_length=1.0,
            object_count=0, mesh_count=0, camera_count=0, light_count=0,
            collections=tuple(f"C{i:06d}" for i in range(self._n)),
        )

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        self.snapshot_calls += 1
        if self._raise is not None:
            raise self._raise
        collections: list[str] = []
        if include_collections:
            for i in range(self._n):
                collections.append(f"C{i:06d}")
                yield
        return SceneSnapshot(
            scene_revision=1, scene_hash="sha256:fake", scene_name="Scene",
            scene_path=None, units_system="METRIC", units_scale_length=1.0,
            object_count=0, mesh_count=0, camera_count=0, light_count=0,
            collections=tuple(collections),
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
from server.core.discovery import Discovery
from server.mcp.adapter import GUIDANCE, capabilities_impl, scene_summary_impl, status_impl
from tests.contract.fake_bridge import live_bridge


def test_status_roundtrip_shape(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        out = status_impl(Discovery(run))
        assert out["ok"] is True and out["guidance"] is None
        row = out["instances"][0]
        assert row["instance_id"] == s.instance_id
        assert row["bridge_state"] == "connected"
        assert row["mode"] == "gui"
        assert row["blender_supported"] is True
        assert row["scene_revision"] == 1


def test_no_instance_returns_guidance(tmp_path):
    out = status_impl(Discovery(tmp_path / "run"))
    assert out == {"ok": True, "guidance": GUIDANCE, "partial": False,
                   "skipped_count": 0, "instances": []}


def test_scene_summary_roundtrip_shape(tmp_path):
    with live_bridge(tmp_path) as (s, reader, run):
        out = scene_summary_impl(Discovery(run), s.instance_id)
        assert out["instance_id"] == s.instance_id
        assert out["scene_hash"] == "sha256:fake"
        assert out["scene_name"] == "Scene"
        assert out["units"] == {"system": "METRIC", "scale_length": 1.0}
        assert out["summary"]["managed_objects"] == []
        assert out["version_warning"] is None


def test_capabilities_offline_and_connected(tmp_path):
    out = capabilities_impl(Discovery(tmp_path / "run"))
    assert out["connected_instances"] == []          # 离线可答（§4.2）
    with live_bridge(tmp_path) as (s, reader, run):
        out2 = capabilities_impl(Discovery(run), include_instances=True)
        assert out2["connected_instances"][0]["instance_id"] == s.instance_id


def test_non_baseline_version_warning_attached(tmp_path):
    with live_bridge(tmp_path, blender_version="4.5.3") as (s, reader, run):
        out = scene_summary_impl(Discovery(run), s.instance_id)
        assert out["version_warning"] is not None and "4.5.3" in out["version_warning"]
```

- [ ] **Step 2: 跑测试** → `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/contract/test_roundtrip.py -q` → 5 passed

- [ ] **Step 3: Commit**

```bash
git add tests/contract/
git commit -m "test(L2): FakeBridge harness 与端到端往返、非基线警告"
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
import pytest
from protocol import envelope, framing
from server.core.bridge_client import BridgeClient, BridgeError
from server.core.discovery import Discovery
from tests.contract.fake_bridge import live_bridge


def _client(s) -> BridgeClient:
    return BridgeClient({"socket_path": str(s.socket_path), "token": s.token})


def test_five_mib_payload_roundtrip(tmp_path):
    # 至少 5 MiB 的 scene-summary 响应走完整链路无截断（URS 验收）
    with live_bridge(tmp_path, n_collections=700_000) as (s, reader, run):
        r = _client(s).call("scene_summary", timeout=30.0)
        assert len(r["summary"]["collections"]) == 700_000
        assert len(envelope.ok_frame("size-check", r)) - 4 >= 5 * 1024 * 1024


def test_oversize_response_degrades_to_limit_error(tmp_path):
    with live_bridge(tmp_path, n_collections=2_200_000) as (s, reader, run):  # >16MiB
        with pytest.raises(BridgeError) as ei:
            _client(s).call("scene_summary", timeout=30.0)
        assert ei.value.code == envelope.INTERNAL_LIMIT_EXCEEDED


def test_excluding_huge_collections_crops_before_frame_limit(tmp_path):
    # 2.2M names would exceed 16 MiB. false 必须贯穿 UDS params 并在 reader 源端
    # 跳过枚举，而不是先构造超大响应再由 Server 丢弃。
    with live_bridge(tmp_path, n_collections=2_200_000) as (s, reader, run):
        result = _client(s).call(
            "scene_summary",
            {"include_collections": False, "include_managed_objects": False},
            timeout=5.0,
        )
        assert result["summary"]["collections"] == []
        assert result["summary"]["managed_objects"] == []


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
        orig = reader.snapshot_steps

        def bad(**kwargs):
            snap = yield from orig(**kwargs)
            return snap.__class__(**{**snap.__dict__, "scene_name": Unserializable()})

        reader.snapshot_steps = bad                    # type: ignore[method-assign]
        with pytest.raises(BridgeError) as ei:
            _client(s).call("scene_summary")
        assert ei.value.code == envelope.SCENE_QUERY_FAILED
        reader.snapshot_steps = orig                   # type: ignore[method-assign]
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
    instance_id = f"gui-1-{tmp_path.stat().st_ino & 0xffffffff:08x}"
    runtime = tmp_path / "run"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    run = runtime / instance_id
    run.mkdir(mode=0o700)
    run.chmod(0o700)
    socket_dir = Discovery._fallback_dir(instance_id)
    assert socket_dir is not None
    socket_dir.mkdir(mode=0o700)
    socket_dir.chmod(0o700)
    sock_path = socket_dir / "bridge.sock"  # 短路径防 sun_path 104B
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(str(sock_path))
    srv.listen(1)
    sock_path.chmod(0o600)
    dir_stat, socket_stat = socket_dir.stat(), sock_path.stat()

    def serve():
        conn, _ = srv.accept()
        buf = framing.FrameBuffer()
        frames = []
        while not frames:
            frames = buf.feed(conn.recv(65536))
        req = envelope.decode_request(frames[0])
        conn.sendall(framing.encode_frame(json.dumps({
            "v": 2, "id": req.id, "ok": True,
            "result": {"instance_id": instance_id, "bridge_version": "9.9",
                       "blender_version": "5.2.0", "envelope_version": 2},
        }).encode()))
        conn.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    session_file = run / "session.json"
    session_file.write_text(json.dumps({
        "instance_id": instance_id, "token": "t", "pid": 1,   # pid 1 恒存活 → 不清理
        "socket_path": str(sock_path), "blender_version": "5.2.0",
        "bridge_version": "9.9", "envelope_version": 2,
        "socket_external": True,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": dir_stat.st_dev, "socket_dir_ino": dir_stat.st_ino,
    }))
    session_file.chmod(0o600)
    try:
        inst = Discovery(runtime).instances()
        assert len(inst) == 1
        assert inst[0].envelope_mismatch is True
        assert inst[0].state == "disconnected"
        assert run.exists()                           # 话不投机 ≠ 死实例（§4.3）
    finally:
        srv.close()
        t.join(timeout=1.0)
        sock_path.unlink(missing_ok=True)
        socket_dir.rmdir()


def test_bridge_kill_then_restart_recovers(tmp_path):
    now = [0.0]
    d = Discovery(tmp_path / "run", ttl=1.0, clock=lambda: now[0])
    with live_bridge(tmp_path) as (s, reader, run):
        assert d.instances()[0].state == "connected"
    # 会话已 stop（等价于 Blender 被杀后清理完成）：
    now[0] = 2.0
    assert d.instances() == []
    with live_bridge(tmp_path) as (s2, reader2, run2):    # 重启 → 同一 Discovery 重新发现
        now[0] = 4.0
        assert d.instances()[0].session["instance_id"] == s2.instance_id
```

- [ ] **Step 2: 跑测试** → `/Users/yeminjie/.local/bin/uv run --frozen pytest tests/contract/test_adversarial.py -q` → 14 passed
（5 MiB / 16 MiB 两条较慢属正常；若超 30 s 超时，在两条测试上加 `@pytest.mark.timeout(120)`）

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_adversarial.py
git commit -m "test(L2): 大载荷、超限降级、并发、权限位、无 token 静默断开、版本不匹配"
```

---

### Task 17: L2 子进程测试——stdout 纯净性与冷启动

**Files:**
- Create: `tests/contract/test_server_process.py`

- [ ] **Step 1: 写测试**

```python
# tests/contract/test_server_process.py
"""以真子进程跑 MCP Server：stdout 每行必须是 JSON-RPC（NFR-O1）；冷启动 < 5 s（NFR-P2）。

协议合同（复审 F-04 修订）：旧协议与 2026-07-28 **走各自的 wire path**，
不共享 `_init()`、不接受静默降级。旧版测试曾对两个版本都发 legacy `initialize`
且允许任意协商版本，导致 2026-07-28 实测降级到 2025-11-25 仍然假通过；该测试已删除，当前两条路径分别精确断言各自版本。
"""
import hashlib
import json
import os
import selectors
import subprocess
import sys
import time
from collections import deque

import pytest

CODEX_PROTOCOL = "2025-06-18"
LEGACY_PROTOCOL = "2025-11-25"
CURRENT_PROTOCOL = "2026-07-28"
READ_TIMEOUT_SECONDS = 10.0
MAX_STDOUT_LINE_BYTES = 16 * 1024 * 1024
MAX_STDOUT_BUFFER_BYTES = 32 * 1024 * 1024
MAX_STDOUT_MESSAGES = 1024
MAX_STDOUT_BACKLOG_BYTES = 32 * 1024 * 1024
MAX_DIAGNOSTIC_LINES = 32
MAX_DIAGNOSTIC_LINE_BYTES = 1024
FROZEN_SCHEMA_SHA256 = {
    "describe_capabilities": "958c7cb8f5978b197a4a8e8290eb8791aa0ee0e18d64039e8a7b0344e8eb290e",
    "get_blender_status": "711d51c6c7f5d0eba37c8964374f268ca09cb41371cce05be693e2f98808304c",
    "get_scene_summary": "c8301261f88d9e546c08819b7e9e0c47a5e33246945a35f894a63c00e346cb1b",
}

INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
CALL = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "describe_capabilities", "arguments": {}}}


def _spawn(tmp_path):
    env = os.environ | {"BLENDERCODEX_ROOT": str(tmp_path)}
    p = subprocess.Popen(
        [sys.executable, "-c", "from server.mcp.adapter import main; main()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=False, bufsize=0,
    )
    os.set_blocking(p.stdout.fileno(), False)
    return p


def _stdio_params(tmp_path):
    from mcp import StdioServerParameters
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", "from server.mcp.adapter import main; main()"],
        env=os.environ | {"BLENDERCODEX_ROOT": str(tmp_path)},
    )


@pytest.fixture
def proc(tmp_path):
    p = _spawn(tmp_path)
    yield p
    p.kill()
    p.wait(timeout=5)


def _send(p, obj):
    p.stdin.write((json.dumps(obj) + "\n").encode())
    p.stdin.flush()


class _StdoutReader:
    """Persistent per-process reader: no blocking readline and no consumed-byte loss."""
    def __init__(self, p):
        self.p = p
        os.set_blocking(p.stdout.fileno(), False)
        self.pending = bytearray()
        self.search_from = 0
        self.backlog = []
        self.backlog_bytes = 0
        self.diagnostics = deque(maxlen=MAX_DIAGNOSTIC_LINES)
        self.message_count = 0

    def _take(self, msg_id):
        for index, (obj, raw_bytes) in enumerate(self.backlog):
            actual = obj.get("id")
            if type(actual) is type(msg_id) and actual == msg_id:
                self.backlog_bytes -= raw_bytes
                return self.backlog.pop(index)[0]
        return None

    def _parse_complete_lines(self) -> None:
        start = 0
        while (line_end := self.pending.find(b"\n", self.search_from)) >= 0:
            raw = bytes(self.pending[start:line_end])
            start = line_end + 1
            self.search_from = start
            if len(raw) > MAX_STDOUT_LINE_BYTES:
                raise AssertionError("stdout line exceeds size limit")
            if self.backlog_bytes + len(raw) > MAX_STDOUT_BACKLOG_BYTES:
                raise AssertionError("stdout backlog exceeds size limit")
            self.message_count += 1
            if self.message_count > MAX_STDOUT_MESSAGES:
                raise AssertionError("stdout message flood")
            line = raw.decode("utf-8")
            self.diagnostics.append(line[:MAX_DIAGNOSTIC_LINE_BYTES])
            obj = json.loads(line)          # 解析失败 = stdout 被污染 → FAIL
            assert isinstance(obj, dict) and obj.get("jsonrpc") == "2.0"
            self.backlog.append((obj, len(raw)))
            self.backlog_bytes += len(raw)
        if start:
            del self.pending[:start]        # one compaction per read, not per line
        self.search_from = len(self.pending)  # old suffix was already searched
        if len(self.pending) > MAX_STDOUT_LINE_BYTES:
            raise AssertionError("stdout line exceeds size limit")

    def read_until(self, msg_id, deadline):
        found = self._take(msg_id)
        if found is not None:
            return found, list(self.diagnostics)
        sel = selectors.DefaultSelector()
        sel.register(self.p.stdout, selectors.EVENT_READ)
        try:
            while time.monotonic() < deadline:
                if not sel.select(timeout=max(0.0, deadline - time.monotonic())):
                    continue
                chunk = os.read(self.p.stdout.fileno(), 65536)
                if not chunk:
                    break
                self.pending.extend(chunk)
                if len(self.pending) > MAX_STDOUT_BUFFER_BYTES:
                    raise AssertionError("stdout buffer exceeds size limit")
                self._parse_complete_lines()  # parse the whole chunk before returning
                found = self._take(msg_id)
                if found is not None:
                    return found, list(self.diagnostics)
            raise AssertionError(
                f"no response id={msg_id} before deadline; "
                f"lines={list(self.diagnostics)}; "
                f"partial={bytes(self.pending[:1024])!r}; "
                f"partial_bytes={len(self.pending)}")
        finally:
            sel.unregister(self.p.stdout)
            sel.close()

    def drain_until(self, deadline):
        """Boundedly parse every trailing line; quiet timeout/clean EOF settle."""
        sel = selectors.DefaultSelector()
        sel.register(self.p.stdout, selectors.EVENT_READ)
        try:
            while time.monotonic() < deadline:
                if not sel.select(timeout=max(0.0, deadline - time.monotonic())):
                    break
                chunk = os.read(self.p.stdout.fileno(), 65536)
                if not chunk:
                    break
                self.pending.extend(chunk)
                if len(self.pending) > MAX_STDOUT_BUFFER_BYTES:
                    raise AssertionError("stdout buffer exceeds size limit")
                self._parse_complete_lines()
            if self.pending:
                raise AssertionError(
                    f"partial stdout after settle: {bytes(self.pending[:1024])!r}; "
                    f"partial_bytes={len(self.pending)}")
        finally:
            sel.unregister(self.p.stdout)
            sel.close()


def _read_until(p, msg_id, deadline):
    """Reuse one bounded reader so bytes consumed after a target response survive."""
    reader = getattr(p, "_bcx_stdout_reader", None)
    if reader is None:
        reader = _StdoutReader(p)
        p._bcx_stdout_reader = reader
    return reader.read_until(msg_id, deadline)


def _drain_stdout(p, deadline):
    reader = getattr(p, "_bcx_stdout_reader", None)
    if reader is None:
        reader = _StdoutReader(p)
        p._bcx_stdout_reader = reader
    reader.drain_until(deadline)


def test_cold_start_and_stdout_purity(tmp_path):
    t0 = time.monotonic()                    # 计时含进程启动（复审 F-12）
    p = _spawn(tmp_path)
    try:
        _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": CODEX_PROTOCOL, "capabilities": {},
                             "clientInfo": {"name": "l2", "version": "0"}}})
        resp, _ = _read_until(p, 1, t0 + 10)
        assert time.monotonic() - t0 < 5.0               # NFR-P2
        assert "允许 Codex 连接" in resp["result"].get("instructions", "")  # FR-34
        _send(p, INITIALIZED)
        _send(p, CALL)
        resp2, _ = _read_until(p, 2, time.monotonic() + 10)
        payload = json.loads(resp2["result"]["content"][0]["text"])
        assert payload["phase"] == "phase0"
        assert payload["ir_schema_version"] is None
        _drain_stdout(p, time.monotonic() + 0.2)
    finally:
        p.kill()
        p.wait(timeout=5)


def test_audit_request_id_matches_inbound_jsonrpc_id(tmp_path):
    p = _spawn(tmp_path)
    try:
        _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": CODEX_PROTOCOL, "capabilities": {},
                             "clientInfo": {"name": "l2", "version": "0"}}})
        _read_until(p, 1, time.monotonic() + 10)
        _send(p, INITIALIZED)
        _send(p, {**CALL, "id": 42})
        _read_until(p, 42, time.monotonic() + 10)
        _send(p, {**CALL, "id": "42"})
        _read_until(p, "42", time.monotonic() + 10)
        audit_path = next((tmp_path / "logs").glob("server-*.jsonl"))
        rows = [json.loads(line) for line in audit_path.read_text().splitlines()]
        assert rows[-2]["request_id"] == 42 and type(rows[-2]["request_id"]) is int
        assert rows[-1]["request_id"] == "42" and type(rows[-1]["request_id"]) is str
    finally:
        p.kill()
        p.wait(timeout=5)


@pytest.mark.parametrize("protocol", [CODEX_PROTOCOL, LEGACY_PROTOCOL])
def test_initialize_protocol_negotiates_exactly_requested(proc, protocol):
    # 当前 Codex 与上一代协议都走 initialize，并精确断言不被静默改写。
    _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": protocol, "capabilities": {},
                            "clientInfo": {"name": "l2", "version": "0"}}})
    resp, _ = _read_until(proc, 1, time.monotonic() + 10)
    assert resp["result"]["protocolVersion"] == protocol
    _send(proc, INITIALIZED)
    _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "describe_capabilities",
                            "arguments": {"unexpected": 1}}})
    rejected, _ = _read_until(proc, 3, time.monotonic() + 10)
    assert rejected["error"]["code"] == -32602
    assert rejected["error"]["data"]["unknown"] == ["unexpected"]


@pytest.mark.asyncio
async def test_current_protocol_via_sdk_client(tmp_path, monkeypatch):
    # 新协议走真实 stdio，且精确证明 discover 成功、没有 initialize fallback。
    monkeypatch.setenv("BLENDERCODEX_ROOT", str(tmp_path))
    from mcp import Client
    from mcp.client.stdio import stdio_client
    from mcp.shared.exceptions import MCPError

    async with Client(stdio_client(_stdio_params(tmp_path)), mode="auto",
                      read_timeout_seconds=READ_TIMEOUT_SECONDS) as client:
        assert client.session.protocol_version == CURRENT_PROTOCOL
        assert client.session.discover_result is not None
        assert client.session.initialize_result is None
        assert client.instructions is not None
        assert "允许 Codex 连接" in client.instructions
        tools = await client.list_tools()
        names = {t.name for t in tools.tools}
        assert names == {"get_blender_status", "get_scene_summary",
                         "describe_capabilities"}
        result = await client.call_tool("describe_capabilities", {})
        assert result.structured_content is not None
        assert result.structured_content["phase"] == "phase0"
        with pytest.raises(MCPError) as exc:
            await client.call_tool("describe_capabilities", {"unexpected": 1})
        assert exc.value.code == -32602
        assert exc.value.data["unknown"] == ["unexpected"]


@pytest.mark.asyncio
async def test_tools_declare_closed_schemas(tmp_path, monkeypatch):
    # 规范原始 $defs/$ref 表示的 canonical JSON digest；任一字段变化都会失败。
    monkeypatch.setenv("BLENDERCODEX_ROOT", str(tmp_path))
    from mcp import Client
    from server.mcp.adapter import mcp as server_app

    async with Client(server_app, read_timeout_seconds=READ_TIMEOUT_SECONDS) as client:
        tools = (await client.list_tools()).tools
        assert {tool.name for tool in tools} == set(FROZEN_SCHEMA_SHA256)
        for tool in tools:
            payload = {"inputSchema": tool.input_schema,
                       "outputSchema": tool.output_schema}
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            assert digest == FROZEN_SCHEMA_SHA256[tool.name], \
                f"{tool.name} schema drift:\n{json.dumps(payload, indent=2, sort_keys=True)}"


@pytest.mark.asyncio
async def test_stdio_mcp_to_fake_bridge_roundtrip(tmp_path):
    from mcp import Client
    from mcp.client.stdio import stdio_client
    from tests.contract.fake_bridge import live_bridge

    with live_bridge(tmp_path) as (session, _reader, _run):
        async with Client(stdio_client(_stdio_params(tmp_path)), mode="auto",
                          read_timeout_seconds=READ_TIMEOUT_SECONDS) as client:
            status = await client.call_tool("get_blender_status", {})
            assert status.structured_content["instances"][0]["instance_id"] == session.instance_id
            summary = await client.call_tool(
                "get_scene_summary", {"instance_id": session.instance_id})
            assert summary.structured_content["scene_hash"] == "sha256:fake"
            assert summary.structured_content["scene_name"] == "Scene"


def test_read_until_preserves_same_chunk_backlog_and_matches_id_type_exactly():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"id\":true}\\n"
         "{\"jsonrpc\":\"2.0\",\"id\":1}\\n"
         "{\"jsonrpc\":\"2.0\",\"id\":2}\\n'); "
         "sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        first, _ = _read_until(p, 1, time.monotonic() + 1.0)
        second, _ = _read_until(p, 2, time.monotonic() + 1.0)
        assert type(first["id"]) is int and first["id"] == 1
        assert type(second["id"]) is int and second["id"] == 2
    finally:
        p.kill()
        p.wait(timeout=5)


def test_stdout_pollution_after_target_in_same_chunk_is_not_hidden():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"id\":1}\\nNOT-JSON\\n'); "
         "sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(json.JSONDecodeError):
            _read_until(p, 1, time.monotonic() + 1.0)
    finally:
        p.kill()
        p.wait(timeout=5)


def test_delayed_stdout_pollution_after_target_is_not_hidden():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"id\":1}\\n'); "
         "sys.stdout.flush(); time.sleep(0.1); "
         "sys.stdout.write('NOT-JSON\\n'); sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        _read_until(p, 1, time.monotonic() + 1.0)
        with pytest.raises(json.JSONDecodeError):
            _drain_stdout(p, time.monotonic() + 1.0)
    finally:
        p.kill()
        p.wait(timeout=5)


def test_partial_stdout_line_cannot_escape_deadline():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.stdout.buffer.write(b'{'); sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    t0 = time.monotonic()
    try:
        with pytest.raises(AssertionError, match="partial"):
            _read_until(p, 1, t0 + 0.2)
        assert time.monotonic() - t0 < 1.0
    finally:
        p.kill()
        p.wait(timeout=5)


def test_unterminated_stdout_line_is_size_bounded(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "MAX_STDOUT_LINE_BYTES", 64)
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.stdout.buffer.write(b'x'*65); "
         "sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(AssertionError, match="size limit"):
            _read_until(p, 1, time.monotonic() + 1.0)
    finally:
        p.kill()
        p.wait(timeout=5)


def test_stdout_message_flood_is_bounded(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "MAX_STDOUT_MESSAGES", 8)
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "[sys.stdout.write('{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"method\\\":\\\"n\\\"}\\n') "
         "for _ in range(9)]; sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(AssertionError, match="message flood"):
            _read_until(p, 1, time.monotonic() + 1.0)
    finally:
        p.kill()
        p.wait(timeout=5)
```

- [ ] **Step 2: 跑测试** → frozen 环境下 `pytest tests/contract/test_server_process.py -q` → **13 passed**（v8；含 `2025-06-18` / `2025-11-25` 精确 initialize、真实 `2026-07-28` discover、stdio→MCP adapter→UDS→FakeBridge 往返、同块 backlog/精确 id 类型、延迟污染、半行、超长 stdout 与通知洪泛反例）

需在 `pyproject.toml` 的 dev 依赖加 `pytest-asyncio>=0.24` 并设 `asyncio_mode = "auto"`。SDK v2 的 `structuredContent`、当前 Codex `2025-06-18`、legacy `2025-11-25` 与 2026 discover 均按实测结果做精确断言，不保留“二选一”占位；Codex 的同名 feature flag 不替代 protocol probe。

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_server_process.py
git commit -m "test(L2): 子进程级 stdout 纯净性与冷启动预算"
```

---

### Task 18: L3 冒烟（真 GUI Blender，半自动）

**需要 Blender GUI**，会打开窗口数十秒后自动退出。覆盖 spec §7.3 五项；设置 `BLENDERCODEX_LARGE_OBJECTS=100000` 时同一 runner 追加真 GUI shared-mesh 大场景 wall-clock/max-tick 门，默认值仍只跑小场景。

**Files:**
- Create: `smoke/runner.py`

- [ ] **Step 1: 写 runner**

```python
# smoke/runner.py
"""blender --factory-startup --python smoke/runner.py
L3：timer 驱动 tick / revision 递增 / 真场景字段 / **hash scope 盲区真机证明** / 20 次会话循环无泄漏。
状态机：每步在一次 timer 回调内完成并立即返回——绝不在回调内 join/sleep 等待
需要 tick 的结果：_tick_guard 与本 runner 同为主线程 timer，回调内阻塞会自饿死（r3 审计）。
结果写 $BLENDERCODEX_SMOKE_OUT（默认 /tmp/bcx_smoke.json），末行打印 SMOKE_{OK,FAIL}。"""
import json
import math
import os
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from bridge.blender import driver, panel  # noqa: E402
from server.core.bridge_client import BridgeClient, BridgeError  # noqa: E402

OUT = os.environ.get("BLENDERCODEX_SMOKE_OUT", "/tmp/bcx_smoke.json")
LARGE_OBJECTS = max(0, int(os.environ.get("BLENDERCODEX_LARGE_OBJECTS", "0")))
LARGE_BATCH = 1024
LARGE_MAX_WALL_MS = 2000.0       # NFR-P1 candidate on the fixed baseline machine
LARGE_MAX_TICK_MS = 100.0        # 50 ms budget + bounded source step/jitter; not a hard wall
LARGE_QUERY_TIMEOUT = 30.0       # bounded observation window; separate from pass/fail budget
LARGE_QUERY_RUNS = 20            # nearest-rank P95 needs at least twenty observations
RES: dict = {"timer_tick": None, "revision_bump": None, "fields": None,
             "hash_scope": None, "cycles_leak_free": None, "large_scene": None,
             "large_scene_budget_ok": None, "large_scene_metrics": None, "errors": []}
ST: dict = {"phase": "start", "box": None, "thread": None, "deadline": 0.0,
            "rev0": -1, "cycle": 0, "base_threads": 0, "run_dir": None,
            "hash_before": None, "hash_after_vertex": None, "large_index": 0,
            "large_mesh": None, "large_query_started": 0.0, "large_build_started": 0.0,
            "large_orig_tick": None, "large_max_tick_ms": 0.0, "large_tick_count": 0,
            "large_max_callback_ms": 0.0, "large_callback_count": 0,
            "large_max_build_callback_ms": 0.0, "large_build_callback_count": 0,
            "large_build_wall_ms": 0.0, "large_query_samples": [],
            "large_observer_samples": [], "large_structural_ok": True}


def _register():
    for cls in panel.CLASSES:
        bpy.utils.register_class(cls)


def _unregister():
    if not driver.stop():
        raise RuntimeError("bridge cleanup incomplete during smoke")
    for cls in reversed(panel.CLASSES):
        bpy.utils.unregister_class(cls)


def _query_async(timeout: float = 10.0) -> None:
    """在后台线程发起 RPC；结果落在 ST['box']。响应由 GUI timer 驱动的 tick 产生。"""
    s = driver.session()
    box: dict = {}
    deadline = time.monotonic() + timeout
    started = time.perf_counter()

    def call():
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("query deadline expired before worker start")
            box.update(BridgeClient({"socket_path": str(s.socket_path),
                                     "token": s.token}).call("scene_summary",
                                                             timeout=remaining))
        except BridgeError as e:
            box["__error__"] = str(e)
        except Exception as e:  # verifier thread must always publish a terminal state
            box["__error__"] = f"{type(e).__name__}: {e}"
        finally:
            # The timer poll may run up to its next 100 ms interval after the
            # RPC is done.  Record elapsed time in the worker itself so the
            # product wall-clock metric is not inflated by observer scheduling.
            box["__elapsed_ms"] = (time.perf_counter() - started) * 1000.0

    t = threading.Thread(target=call, daemon=True)
    t.start()
    # The GUI state machine and BridgeClient share the same absolute deadline.
    # A caller must never get a second, fixed 12-second window after the
    # client-side timeout has expired.
    ST.update(box=box, thread=t, deadline=deadline)


def _query_state(phase: str) -> bool | None:
    """Return False while pending, True when complete, or None on failure."""
    thread = ST["thread"]
    if thread.is_alive():
        if time.monotonic() < ST["deadline"]:
            return False
        # Give a just-expired call one bounded scheduling turn.  Never wait
        # without a limit: cleanup must not inherit an unbounded join.
        thread.join(timeout=0.05)
    if thread.is_alive():
        RES["errors"].append(f"{phase}: query deadline exceeded")
        return None
    box = ST["box"]
    if isinstance(box, dict) and "__error__" in box:
        RES["errors"].append(f"{phase}: {box['__error__']}")
        return None
    return True


def _restore_large_tick() -> None:
    original = ST.get("large_orig_tick")
    if original is None:
        return
    try:
        driver.session().tick = original
    finally:
        ST["large_orig_tick"] = None


def _connect_probe() -> bool:
    """建连验证（spec §7.3 循环定义）：能 connect 即证明 listener 活着，不依赖 tick。"""
    s = driver.session()
    try:
        with socket.socket(socket.AF_UNIX) as c:
            c.settimeout(1.0)
            c.connect(str(s.socket_path))
        return True
    except OSError:
        return False


def _finish() -> None:
    _restore_large_tick()
    thread = ST.get("thread")
    if thread is not None and thread.is_alive():
        thread.join(timeout=0.25)
        if thread.is_alive():
            RES["errors"].append("finish: query thread did not settle")
    keys = ("timer_tick", "revision_bump", "fields", "hash_scope", "cycles_leak_free")
    if LARGE_OBJECTS:
        keys += ("large_scene", "large_scene_budget_ok")
    ok = all(RES[k] is True for k in keys) and not RES["errors"]
    Path(OUT).write_text(json.dumps(RES, ensure_ascii=False, indent=1))
    print("SMOKE_OK" if ok else f"SMOKE_FAIL {RES}")
    bpy.ops.wm.quit_blender()


def _step() -> float | None:
    ph = ST["phase"]
    try:
        if ph == "start":
            ST["base_threads"] = threading.active_count()
            _register()
            bpy.ops.bcx.allow_connect()
            _query_async()                       # 只有 GUI timer 在驱动 tick
            ST["phase"] = "wait1"
        elif ph in ("wait1", "wait2", "wait_vertex", "wait_moved"):
            state = _query_state(ph)
            if state is False:
                return 0.1                       # 关键：让出主线程给 _tick_guard
            if state is None:
                _finish()
                return None
            box = ST["box"]
            if ph == "wait1":
                RES["timer_tick"] = box.get("scene_name") is not None
                ST["rev0"] = box.get("scene_revision", -1)
                bpy.ops.mesh.primitive_cube_add()  # GUI 下触发 depsgraph handler
                _query_async()
                ST["phase"] = "wait2"
            elif ph == "wait2":
                RES["revision_bump"] = box.get("scene_revision", -1) > ST["rev0"]
                summary = box.get("summary", {})
                RES["fields"] = (summary.get("object_count") == 4
                                 and summary.get("mesh_count") == 2
                                 and summary.get("camera_count") == 1
                                 and summary.get("light_count") == 1
                                 and box.get("scene_hash", "").startswith("sha256:")
                                 and box.get("units", {}).get("system")
                                 in ("METRIC", "NONE"))
                # ---- hash scope 真机证明（复审 F-05）：v1 覆盖 transform、
                #      不覆盖顶点。纯函数测试无法证明这一点，只能在真 Blender 做 ----
                ST["hash_before"] = box.get("scene_hash")
                obj = bpy.context.active_object          # 上一步新增的 Cube
                bpy.ops.object.mode_set(mode="EDIT")
                mesh = bmesh.from_edit_mesh(obj.data)
                mesh.verts.ensure_lookup_table()
                mesh.verts[0].co.x += 0.5                # 真 Edit Mode 顶点编辑
                bmesh.update_edit_mesh(obj.data)
                bpy.ops.object.mode_set(mode="OBJECT")
                _query_async()
                ST["phase"] = "wait_vertex"
            elif ph == "wait_vertex":
                ST["hash_after_vertex"] = box.get("scene_hash")
                bpy.context.active_object.location.x += 1.0   # 对象级 transform
                _query_async()
                ST["phase"] = "wait_moved"
            else:   # wait_moved
                hash_moved = box.get("scene_hash")
                RES["hash_scope"] = (
                    ST["hash_before"] == ST["hash_after_vertex"]   # 顶点：不可见
                    and ST["hash_after_vertex"] != hash_moved      # transform：可见
                )
                if not RES["hash_scope"]:
                    RES["errors"].append(
                        f"hash_scope: before={ST['hash_before']} "
                        f"vertex={ST['hash_after_vertex']} moved={hash_moved}")
                if LARGE_OBJECTS:
                    for old in list(bpy.data.objects):
                        bpy.data.objects.remove(old, do_unlink=True)
                    mesh = bpy.data.meshes.new("LargeSharedMesh")
                    mesh.from_pydata(
                        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
                        [], [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                             (1, 5, 6, 2), (2, 6, 7, 3), (4, 0, 3, 7)],
                    )
                    ST.update(phase="large_build", large_mesh=mesh,
                              large_index=0, large_build_started=time.perf_counter())
                else:
                    bpy.ops.bcx.disconnect()
                    _unregister()
                    ST["phase"] = "cycle"
        elif ph == "large_build":
            mesh = ST["large_mesh"]
            scene = bpy.context.scene
            start = ST["large_index"]
            stop = min(start + LARGE_BATCH, LARGE_OBJECTS)
            for index in range(start, stop):
                obj = bpy.data.objects.new(f"Large{index:06d}", mesh)
                scene.collection.objects.link(obj)
            ST["large_index"] = stop
            if stop < LARGE_OBJECTS:
                return 0.01
            bpy.context.view_layer.update()
            session = driver.session()
            original_tick = session.tick
            ST["large_orig_tick"] = original_tick

            def measured_tick(budget_ms=50):
                started = time.perf_counter()
                try:
                    return original_tick(budget_ms)
                finally:
                    ST["large_tick_count"] += 1
                    ST["large_max_tick_ms"] = max(
                        ST["large_max_tick_ms"],
                        (time.perf_counter() - started) * 1000.0,
                    )

            session.tick = measured_tick
            ST["large_build_wall_ms"] = (
                time.perf_counter() - ST["large_build_started"]) * 1000.0
            ST["large_query_started"] = time.perf_counter()
            # Keep the observation timeout distinct from the 2 s pass/fail
            # budget so an over-budget result still emits useful metrics.  The
            # client and GUI state machine share this one bounded deadline.
            _query_async(timeout=LARGE_QUERY_TIMEOUT)
            ST["phase"] = "large_wait"
        elif ph == "large_wait":
            state = _query_state(ph)
            if state is False:
                return 0.1
            if state is None:
                _finish()
                return None
            box = ST["box"]
            summary = box.get("summary", {})
            wall_ms = box.get("__elapsed_ms")
            if not isinstance(wall_ms, (int, float)):
                raise RuntimeError("large query elapsed metric missing")
            observer_wall_ms = (time.perf_counter() - ST["large_query_started"]) * 1000.0
            structural_this_run = (
                summary.get("object_count") == LARGE_OBJECTS
                and summary.get("mesh_count") == LARGE_OBJECTS
                and summary.get("camera_count") == 0
                and summary.get("light_count") == 0
            )
            ST["large_structural_ok"] = (
                ST["large_structural_ok"] and structural_this_run)
            ST["large_query_samples"].append(float(wall_ms))
            ST["large_observer_samples"].append(observer_wall_ms)
            if len(ST["large_query_samples"]) < LARGE_QUERY_RUNS:
                ST["large_query_started"] = time.perf_counter()
                _query_async(timeout=LARGE_QUERY_TIMEOUT)
                return 0.01

            ordered = sorted(ST["large_query_samples"])
            p95_index = math.ceil(0.95 * len(ordered)) - 1
            query_p95_ms = ordered[p95_index]
            observer_ordered = sorted(ST["large_observer_samples"])
            observer_p95_ms = observer_ordered[p95_index]
            metrics = {
                "target_objects": LARGE_OBJECTS,
                "object_count": summary.get("object_count"),
                "mesh_count": summary.get("mesh_count"),
                "camera_count": summary.get("camera_count"),
                "light_count": summary.get("light_count"),
                "build_wall_ms": ST["large_build_wall_ms"],
                "query_runs": len(ordered),
                "query_wall_ms": query_p95_ms,
                "query_wall_ms_p95": query_p95_ms,
                "query_wall_ms_max": ordered[-1],
                "query_wall_ms_samples": ST["large_query_samples"],
                "observer_wall_ms_p95": observer_p95_ms,
                "observer_wall_ms_max": observer_ordered[-1],
                "max_tick_ms": ST["large_max_tick_ms"],
                "tick_count": ST["large_tick_count"],
                "max_callback_ms": ST["large_max_callback_ms"],
                "callback_count": ST["large_callback_count"],
                "max_build_callback_ms": ST["large_max_build_callback_ms"],
                "build_callback_count": ST["large_build_callback_count"],
            }
            RES["large_scene_metrics"] = metrics
            structural_ok = ST["large_structural_ok"]
            RES["large_scene"] = structural_ok
            RES["large_scene_budget_ok"] = (
                structural_ok and query_p95_ms < LARGE_MAX_WALL_MS
                and ST["large_max_tick_ms"] < LARGE_MAX_TICK_MS
            )
            if not structural_ok:
                RES["errors"].append(f"large_scene: {metrics}")
            elif not RES["large_scene_budget_ok"]:
                RES["errors"].append(f"large_scene budget: {metrics}")
            session = driver.session()
            session.tick = ST["large_orig_tick"]
            ST["large_orig_tick"] = None
            bpy.ops.bcx.disconnect()
            _unregister()
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


def _timed_step():
    phase = ST["phase"]
    started = time.perf_counter()
    try:
        return _step()
    finally:
        if LARGE_OBJECTS and phase == "large_wait":
            ST["large_callback_count"] += 1
            ST["large_max_callback_ms"] = max(
                ST["large_max_callback_ms"],
                (time.perf_counter() - started) * 1000.0,
            )
        elif LARGE_OBJECTS and phase == "large_build":
            ST["large_build_callback_count"] += 1
            ST["large_max_build_callback_ms"] = max(
                ST["large_max_build_callback_ms"],
                (time.perf_counter() - started) * 1000.0,
            )


bpy.app.timers.register(_timed_step, first_interval=0.5)
```

- [ ] **Step 2: 运行**

```bash
set -euo pipefail
smoke_out="$(mktemp /tmp/bcx_smoke.XXXXXX)"
smoke_root="$(mktemp -d /tmp/bcx_smoke_root.XXXXXX)"
chmod 700 "$smoke_root"
BLENDERCODEX_ROOT="$smoke_root" BLENDERCODEX_SMOKE_OUT="$smoke_out" \
  /Applications/Blender.app/Contents/MacOS/Blender \
  --factory-startup --python-exit-code 1 --python smoke/runner.py 2>&1 | tail -2
/Users/yeminjie/.local/bin/uv run --frozen python -c \
  'import json,sys; d=json.load(open(sys.argv[1])); keys=("timer_tick","revision_bump","fields","hash_scope","cycles_leak_free"); assert all(d.get(k) is True for k in keys) and d.get("errors")==[], d' \
  "$smoke_out"
```

Expected: `SMOKE_OK`，随后外部 JSON 验证器退出 0。任何一项 false、异常被 runner 捕获、结果缺失或管道左侧失败都会令本步非零；失败时读 `$smoke_out` 定位五项中的失败项。

M-4 真 GUI 大场景复测（同一 runner、独立输出；不把 background source-step 当 GUI 证据）：

```bash
set -euo pipefail
large_out="$(mktemp /tmp/bcx_smoke_large.XXXXXX)"
large_root="$(mktemp -d /tmp/bcx_smoke_large_root.XXXXXX)"
chmod 700 "$large_root"
BLENDERCODEX_ROOT="$large_root" BLENDERCODEX_LARGE_OBJECTS=100000 \
  BLENDERCODEX_SMOKE_OUT="$large_out" \
  /Applications/Blender.app/Contents/MacOS/Blender \
  --factory-startup --python-exit-code 1 --python smoke/runner.py 2>&1 | tail -2
/Users/yeminjie/.local/bin/uv run --frozen python -c \
  'import json,sys; d=json.load(open(sys.argv[1])); m=d.get("large_scene_metrics") or {}; assert d.get("large_scene") is True and d.get("large_scene_budget_ok") is True and m.get("target_objects")==100000 and m.get("object_count")==100000 and m.get("mesh_count")==100000 and m.get("camera_count")==0 and m.get("light_count")==0 and m.get("query_runs")==20 and len(m.get("query_wall_ms_samples", []))==20 and m.get("query_wall_ms_p95", 1e99)<2000.0 and m.get("max_tick_ms", 1e99)<100.0 and m.get("tick_count", 0)>0 and d.get("errors")==[], d' \
  "$large_out"
```

该可选门记录 `target/object/mesh/camera/light_count`、构造耗时、20 次精确 worker-side query wall-clock 样本及 nearest-rank P95、`tick_count`、`max_tick_ms`，并另记 observer/build callback 峰值用于诊断。产品门只判 query P95 与被包装的 `BridgeSession.tick()`；fixture 的 100k 对象构造和最终 `view_layer.update()` 不属于读取路径，不得造成假失败。`50 ms` 仍是 cooperative budget，不是跨机器或硬墙钟合同；30 s 观察窗口与 2 s 通过预算分离，查询线程与 GUI 等待共享同一观察 deadline，超时后只做有界 join 并 fail-closed。

- [ ] **Step 3: Commit**

```bash
git add smoke/runner.py
git commit -m "test(L3): GUI 冒烟——timer 驱动、revision 递增、真场景字段、hash scope、会话循环"
```

---

### Task 19: 安装文档与验收核对

**Files:**
- Create: `docs/install.md`
- Modify: `docs/superpowers/specs/2026-07-23-phase0-readonly-channel-design.md`（仅全部验收通过后，把“交付目标／隔离预检；Phase 0 未执行”改为已实现状态并记录正式证据）
- Modify: `Blender-Codex-需求规格说明书-v1.md`（仅全部验收通过后记录 Phase 0 正式验收；不得把隔离预检当实施证据）

- [ ] **Step 1: 写安装文档**

````markdown
# 安装与接入（Phase 0）

## 1. 前置
- macOS 14+ / Apple Silicon；Blender **5.2.0 LTS**（官方 DMG）
- [uv](https://docs.astral.sh/uv/)；本机使用 `/Users/yeminjie/.local/bin/uv`，本仓库 frozen sync 完成

## 2. 安装 Bridge 扩展
```bash
/Users/yeminjie/.local/bin/uv run --frozen python scripts/vendor_protocol.py
cd bridge && zip -r ../blender_codex_bridge.zip . -x "*__pycache__*" && cd ..
```
Blender → Edit → Preferences → Get Extensions → 右上角下拉 → Install from Disk… →
选 `blender_codex_bridge.zip`。启用后在 3D 视口按 `N` → 「Codex」页签。

## 3. 注册 MCP Server 到 Codex
```bash
/Applications/ChatGPT.app/Contents/Resources/codex mcp add blender-codex -- \
  /Users/yeminjie/.local/bin/uv --directory /Users/yeminjie/Documents/BlenderDesign \
  run --frozen blender-codex-server
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
| `version_warning` 非空 | Blender 不是精确基线 5.2.0：只读可用，写功能（Phase 1）将拒绝 |
| Server 日志 | `~/Library/Application Support/BlenderCodex/logs/server-*.jsonl` |

## 6. 与官方 Blender Lab MCP 并存（若你也装了它）

2026-08-07 按用户明确授权采用**显式固定的完整 26 工具、无 MCP 审批**配置。官方 MCP 仍含两个任意 Python 工具并使用无鉴权 localhost TCP 9876；它是自定义安全系统之外的兼容通道，不得拿它证明 URS G1–G3。以下 26 项是当前上游注册目录的 allowlist 快照，上游增删工具时必须先复核再更新：

```toml
[mcp_servers.blender]
command = "/Users/yeminjie/.local/bin/uv"
args = ["run", "--quiet", "--no-project", "--with", "mcp[cli]>=1.2.0,<2", "--with-editable", "/Users/yeminjie/blender_mcp/mcp", "blender-mcp"]
default_tools_approval_mode = "approve" # Codex 语义：预先批准，不弹 MCP 审批
enabled_tools = [
  "execute_blender_code",
  "execute_blender_code_for_cli",
  "get_blendfile_summary_datablocks",
  "get_blendfile_summary_datablocks_for_cli",
  "get_blendfile_summary_missing_files",
  "get_blendfile_summary_missing_files_for_cli",
  "get_blendfile_summary_of_linked_libraries",
  "get_blendfile_summary_of_linked_libraries_for_cli",
  "get_blendfile_summary_path_info",
  "get_blendfile_summary_path_info_for_cli",
  "get_blendfile_summary_usage_guess",
  "get_blendfile_summary_usage_guess_for_cli",
  "get_object_detail_summary",
  "get_objects_summary",
  "get_python_api_docs",
  "get_screenshot_of_area_as_image",
  "get_screenshot_of_window_as_image",
  "get_screenshot_of_window_as_json",
  "jump_to_tab_by_name",
  "jump_to_tab_by_space_type",
  "jump_to_view3d_object_by_name",
  "jump_to_view3d_object_data_by_name",
  "render_thumbnail_to_path",
  "render_viewport_to_path",
  "search_api_docs",
  "search_manual_docs",
]
omit_tools_from = []
startup_timeout_sec = 20
tool_timeout_sec = 60

[mcp_servers.blender.env]
BLENDER_PATH = "/Applications/Blender.app/Contents/MacOS/Blender"

# 若 config 已有 [features.code_mode]，把此键合并进既有表，不要重复声明表头。
[features.code_mode]
direct_only_tool_namespaces = ["mcp__blender"]
```

- `enabled_tools` 必须与上列 26 项逐集合全等，`omit_tools_from=[]`；不得出现 `disabled_tools` 或逐工具 override。显式 allowlist 是“当前完整目录”的固定快照，不等于自动接纳未来新增工具
- `features.code_mode.direct_only_tool_namespaces` 必须包含且当前固定为 `mcp__blender`，确保该 namespace 只走直接工具调用路径
- 独立 Codex app-server 的 `config/read` 与 `mcpServerStatus/list` 必须分别证明 effective filter 与目录均为 26/26；当前回合模型工具面可能仍绑定重启前快照，须重启 Codex 或进入新回合后另行确认，且不得用该快照反推 effective config
- 官方 Server 的启动命令必须显式钉 **`mcp[cli]>=1.2.0,<2`**：上游 commit `4309a39` 的依赖声明无上界，而它仍 `from mcp.server.fastmcp import FastMCP`——按默认解析到 SDK 2.0.0 会以 `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` 启动失败（复审 R-05 实测）。用 `uv --no-project --with-editable` 启动，避免在上游 checkout 里生成 `uv.lock`
- **该 `<2` 上界只属于官方 Server 的隔离环境**，绝不可传播到本项目（本项目用 SDK v2）——两个 Server 由不同 `uv` 进程启动，不共享 Python 环境
- 不启用官方 HTTP 模式（当前源码 CORS `*` 且关闭 DNS rebinding 防护）
- 本项目 Bridge 与官方互不依赖：本项目走 UDS + token，官方走 TCP 9876
````

- [ ] **Step 2: 对照 URS §10.1 逐条验收并记录**

| URS 验收项 | 验证方式 | 状态 |
|---|---|---|
| 三工具符合 outputSchema | Task 17 递归断言所有 object 封闭、enum/required 精确，并以 structuredContent 实际调用验证 | ☐ |
| **structure hash v1 语义边界成立** | Task 3 L1 字段结构断言 + Task 18 L3 `hash_scope`（顶点不可见 / transform 可见） | ☐ |
| **当前/旧/新协议合同可用** | Task 17：当前 Codex 2025-06-18 与 legacy 2025-11-25 均精确 initialize；真实 stdio modern 精确断言 2026-07-28 + discover 非空 + initialize 为空；initialize 与 discover 两类路径的未知参数均 -32602 | ☐ |
| 非基线只读可用、写工具拒绝 | Task 9 单测（`gate_write`）+ Task 15 warning 测试 | ☐ |
| 杀 Blender → `BRIDGE_UNAVAILABLE`，重启自动重连 | Task 16 `test_bridge_kill_then_restart_recovers` + 手动杀真 Blender 复核 | ☐ |
| 会话循环 20 次无泄漏 | Task 18 L3 | ☐ |
| 5 MiB 分帧无截断 | Task 1 单测 + Task 16 端到端 | ☐ |
| 权限位 + 无 token 拒绝 | Task 5/7/9/11 的目录、文件与 identity fail-closed 反例 + Task 16 at-rest/token 端到端断言 | ☐ |
| stdout 纯净 | Task 17 | ☐ |
| 冷启动 < 5 s | Task 17 | ☐ |
| MCP stdio → adapter → UDS → Bridge 全链路 | Task 17 `test_stdio_mcp_to_fake_bridge_roundtrip` | ☐ |
| 官方 MCP 完整目录且无审批 | 独立 Codex app-server `config/read`：显式 26 项 `enabled_tools` + `omit_tools_from=[]` + `mcp__blender` direct-only；`mcpServerStatus/list` 26/26，模式 `approve`，代表调用 `approval_events=0`；最新安全 host 长序列截图失败与 deferred render SIGABRT 另列为外部可靠性边界；重启/新回合后另确认模型工具面 | ☐ |

全部打勾后才可在 spec 头部把「状态」改为 **已实现（Phase 0）**，并在 URS 追加正式执行证据；在此之前两者必须继续明确“Phase 0 未执行”。

- [ ] **Step 3: Commit**

```bash
git add docs/install.md docs/superpowers/specs/2026-07-23-phase0-readonly-channel-design.md Blender-Codex-需求规格说明书-v1.md
git commit -m "docs: 安装接入文档与 URS 验收核对表"
```

---

## 计划自审记录

> 1–4 保留初版自审编号；后续修订从最新到最旧排列，编号保留证据来源，不再误称整表严格倒序。

18. **r15/v8 全量对抗复审（2026-08-08）**：红队构造 Blender addon 第二个 `register_class` 失败反例，证明旧 `register()` 会泄漏此前已注册 class；Blender `addon_utils` 不会在模块加载失败后调用 `unregister()`。新增注册部分失败回滚与回滚自身失败保留/报告测试，`register()` 仅逆序撤销本次新增 class；fresh-tree **307 passed（275+32）**、adapter 35/373 行、ruff/mypy/vendor/nested/lock 全绿；background/GUI smoke 及 100k Bridge-RPC 子门重新通过（worker P95 1605.18 ms、max 2560.86 ms、observer P95 1655.44 ms、max tick 62.50 ms）。官方 26 工具注册/安全 host 历史直调仍通过，但 deferred render 序列复现 Blender 5.2 `SIGABRT`，G5 不得写成稳定全绿；Plan 92+G0 全未执行。

17. **r14/v7 全量对抗复审（2026-08-08，历史，已由 r15/v8 取代）**：发现 SDK v2 `Tool.run` 在同步工具函数返回后才执行 `convert_result`，旧 semaphore 已提前释放；三请求反例证明转换阶段可超过进程级 2 上限。准入移入现有 raw-argument middleware，fail-fast `BRIDGE_BUSY`，槽位覆盖完整 `call_next`、转换及 audit postlude；新增 wire 三请求反例与异常释放反例。fresh-tree **305 passed（273+32）**、adapter 35/373 行、ruff/mypy/vendor/nested/lock 全绿；fresh background/GUI smoke 通过，100k raw 只证明 Bridge-RPC 子门。官方 26 工具注册/安全 host 调用仍通过，但 deferred render 序列复现 Blender 5.2 `SIGABRT`，G5 不得写成稳定全绿；Plan 92+G0 全未执行。

16. **r13 handoff 融合最终预检（历史，已由 r14/v7 取代）**：cursor/preflight 测试名与真实 hook 窗口对齐；Discovery 失效通知有界合并且不等待扫描锁；stdout/host verifier 增加消息/事件/字节上限、EOF settle 与 kill fallback；SceneReader 混合类型/计数、跨 yield wrapper-free 与 scene-info 竞态进入回归。最终门禁数字见 v6 provenance；100k GUI 20-query Bridge-RPC nearest-rank P95 约 1439.21 ms、max tick 约 62.12 ms，只关闭 M-4 子门，不冒充端到端 MCP NFR-P1。实际执行 checkbox 为 92 个，另有 1 个不带 checkbox 的 G0 preflight；历史“93”是 raw token 口径。Phase 0 仍未执行。

15. **r12 平台与大场景复审（2026-08-07）**：真 Blender 反例证明旧的逐对象数值索引在 10k/20k 对象下近 O(N²)；SceneReader 改为每步以有界 1024 项 collection slice 物化为纯 Python、释放全部 bpy wrapper 后再 yield，hash merge 每 128 行 yield。固定测试拒绝数值索引并递归检查 yield locals；候选隔离树在 Blender 5.2.0 / Apple M4 上 100k 共享网格对象总耗时约 1.2 s、最大 source step 约 22 ms、wrapper-free=true。平台性能数字仍是本机预检，不构成跨硬件合同；当时所谓“93”是 raw token 口径，真实执行项仍为 92 + 1 个无 checkbox preflight，均未执行。

1. **Spec 覆盖**：§2 运行时布局→T0/T7；§3.1 布局与 import 约束→T0/T3(_proto)/T13/T14；§3.2 线格式→T1/T2；§3.3 信封→T2；§3.4 契约→T3/T6；§3.5 hash 与场景选择→T3/T13；§3.6 队列与护栏→T4/T13(driver)；§3.7 I/O 模型与十步关闭→T7（步 6/7 委托 T13 driver，已在两处标注）；§4.1→T7/T13；§4.2→T10/T12；§4.3→T11/T12；§4.4→T9/T12；§5 错误表→T2/T4/T7/T10/T12 分摊；§5.2 审计→T9/T12；§5.3 冷启动→T12(惰性 `_deps`)/T17；§6 三 schema→T12 + L2 形状断言；§7 测试策略→T15–T18；§8 spike 结论→全局约束与 T13；§9 工具链→T0/T14；§12 顺序→任务依赖图一致。
2. **已修缺陷**：`bridge/core` 对 protocol 的顶层绝对导入在 `bl_ext.*` 命名空间下会炸——增设 `_proto.py` 垫片（T3）并将 T4/T6/T7 代码全部改走垫片，`nested_import_smoke.py`（T14）连同 `core/` 一起纳入拦截；根 shim `bridge/__init__.py` 以 bpy 探测守卫，否则 pytest 无法 import `bridge.core`（T13）。
3. **类型/签名一致性**：`SceneReader` 三方法（T3 定义 + T6 扩展 `status_info`）与 FakeReader（T6/T7/T15）、BpySceneReader（T13）一致；`Instance.envelope_mismatch` 在 T12 补入并被 T16 断言；`ok_frame/error_frame` 命名全程一致。
4. **占位符扫描**：无 TBD/TODO；协议、schema、structuredContent 与 timeout 均已有单一路径和精确断言，不保留「以实际行为为准」式占位。
14. **r11 最终对抗冻结（2026-08-07，`docs/audits/2026-08-07-closeout-v2.md`）**：在 r10 后继续修复 listener/accepted socket ownership、失败 close 可重试、transport 未关闭时禁止提前删除 session 路径、driver/UI cleanup 重试、status 实例身份绑定、响应版本错误分类、audit 原始 request id 与 post-I/O deadline、PathPolicy NUL、cleanup partial、fd reuse，以及 64 连接 / 32 MiB 全局入站 / 64 KiB 请求 / 32 MiB 单连接出站 / 64 MiB 全局出站上限。冻结树 260 passed（unit 233 + contract 27），adapter 33 passed/375 实质行，ruff/mypy/vendor/nested/lock 全绿；46/46 Python 块逐字节同步，v5 provenance 可复算。当时“93 Step”为 raw token 口径；所有执行项未执行。
13. **r10 收尾补充（历史中间态，已由 r11 取代；2026-08-07）**：红队补出标准 JSON 缺口：Python `json.loads` 默认接受 `NaN` / `Infinity` / `-Infinity`，`dumps` 默认也可能发送这些值。`protocol/envelope.py` 当轮以 `parse_constant`、有限 `parse_float` 与 `allow_nan=False` 在收发两向 fail-closed；新增 5 种 wire 非有限表示与 3 种发送值回归，隔离预检当轮升为 235-test（unit 208 + contract 27）。当时“93 Step”为 raw token 口径；所有执行项未执行。
12. **r10 最终合同对齐（历史中间态，已由 r11 取代；2026-08-07）**：当轮 Plan 46 个 Python 文件块与隔离树逐字节同步；补齐深层 JSON/Unicode/字段长度、deadline 边界、fd 回收、audit fail-closed、instances/ScanStats 原子快照、driver/lifecycle 自愈、method payload 与 status 单实例异常 fail-closed反例；统一 URS/spec v1.7、adapter ≤375 行、235-test/22-file 预检与官方 MCP 显式 26 工具合同。G5 宿主目录已 26/26，当前模型面仍待重启或新回合验收；当时“93 Step”为 raw token 口径，所有执行项未执行。
11. **r9 最终收尾对抗闭环（2026-08-07）**：长路径 fallback、既存权限、首次并发初始化与换入竞态复核关闭九项残余/证据缺口：应用自有目录 race-safe create-or-validate、会话叶目录 exclusive 创建；AuditLog 以 no-follow/nonblocking + 同 fd identity/类型/uid/mode 校验并用线程锁与跨进程文件锁保证完整 JSONL；Discovery 以 dir-fd/dev-inode 绑定读取与清理，固定 `/tmp/bcx-<hash>`（不依赖两进程可能不同的 `$TMPDIR`）同时覆盖发布前/后崩溃，cleanup 逐次服从同一 deadline 且 identity 不符时保留证据；`instance_id` 必须匹配目录名；请求/响应信封 exact-type 校验阻止 bool-as-int，所有 malformed response shape 统一映射 retryable `BRIDGE_UNAVAILABLE`；stop 保留换入的 socket/session/目录目标并在 loop boundary 重检停止状态；应用 runtime 根与 audit target 的 symlink 亦按权限边界 fail-closed；补入先前只存在于隔离树、未进入 Plan 的 `test_scene_reader.py` 完整文件块，使证据从 45 块提升为可自足的 46/46。最终隔离证据为 166 passed（L1 140 + L2 26，无 warnings）、ruff/mypy/vendor/nested import 全绿、`BG_CHECK_OK`，且 GUI smoke `/tmp/bcx-final-smoke-20260807-04.json` 晚于全部最终 Python 源码并五项全 true。Phase 0 任务仍未执行。
10. **r8 最终对抗修订（2026-08-07）**：Discovery 改同 fd no-follow/bounded-read + scandir cursor/backlog 公平推进，加入慢枚举/FIFO/换入/缺字段/第 257 项及同窗第 17 项反例；status 单一 deadline 与 cache invalidate 进入测试；Pydantic 封闭输出模型 + raw-argument middleware 使未知字段在 initialize/discover 两类协议均返回 -32602；2026 使用真实 stdio 并精确断言 discover、拒绝 initialize fallback；补 stdio→adapter→UDS→FakeBridge 全链路；stdout 半行改 `os.read`；L3 外部解析结果且 baseline 前移；官方 MCP 改为用户明确授权的 26/26、`approve` 无审批目录。后续 protocol probe 又补入当前 Codex `2025-06-18` 精确合同，并明确同名 flag 当前仍未切到 2026 wire。
9. **r7 全量复审落实（历史中间态，已被 r8 替代；2026-08-07，`docs/audits/2026-08-07-full-repository-adversarial-reaudit.md`）**：F-01 Discovery 当时先改惰性 `os.scandir` + 预算/条数双止损 + `lstat`/`S_ISREG`，r8 已进一步改为同 fd open/fstat/read 与候选 backlog；F-02 `status_impl` 单一绝对 deadline 贯穿发现与聚合；F-03 当时先以 `TypedDict` 生成 outputSchema 并记录 SDK 未知参数限制，r8 已进一步改为 Pydantic 封闭模型 + raw-argument middleware 真正服务端拒绝；F-04 新旧协议拆成各自 wire path（legacy 精确断言 + SDK v2 Client），不再共享 `_init()`；F-05 L3 runner 加 `hash_scope` 相位并进入成功判据；F-06 `importlib.metadata.version` + `uv.lock`/frozen + 精确 `git add`；F-07 `describe_capabilities` 默认不触网；F-08 当时按 mtime 取最新，r8 再改为跨窗口 cursor/backlog；F-12 子进程测试改 selector 非阻塞且计时含 Popen；P2 partial 改顶层元数据、`_Ctx` 改 `contextmanager`、`.gitignore` 只补缺失项。
8. **r6 第三方复审落实（2026-08-07，`docs/audits/2026-08-07-claude-plan-changes-adversarial-reaudit.md`）**：R-01 SDK 改判 v2（`mcp>=2.0,<3` + `MCPServer`；本仓库独立复核 v2 与 2025-11-25 客户端握手/列表/调用/structuredContent 全通，Phase 1.5 的 SDK 升级条目撤销）；R-02 socket ownership（`_socket_owned`，bind 冲突时绝不删外部 socket——复现确认原实现造成 DoS）+ 测试；R-03 deadline 移至 `_scan()` 入口 + 遍历阶段即止损 + session 文件尺寸上限 + `__partial__` 显式标记（复现确认原实现 400 候选 5.0s）+ 两条测试；R-04 scene_hash 测试改为字段结构断言（原测试 a≡b 恒真）+ L3 真 Blender 盲区证明；R-05 官方 Server `<2` 上界写入安装文档；G0/G5 关闭；Discovery 结果排序确定化。
7. **r5 外部审计落实（2026-08-07，审计文档 docs/audits/2026-08-07-plan-adversarial-audit-and-optimization.md）**：F-01 scene_hash 定义为「结构摘要 v1」并加盲区钉死测试（顶点级编辑不可见是版本化语义而非全场景指纹）；F-02 BridgeClient 改全调用总 deadline（修复前实测慢滴流把 0.3s 超时拖到 1.38s）+ 滴流测试；F-03 Discovery 全扫描 deadline 2.5s + 候选上限 16 + 跳过如实标注（修复前实测 16 候选 4.0s）+ 挂起洪泛测试；F-04 start() 事务化（session.json 最后发布、失败全回滚 + 属性默认值防误删守卫）+ 失败测试；F-05 path_policy 标注 TOCTOU 边界；F-07 checks.sh preflight；F-08 移除硬编码署名 trailer、superpowers 改非阻塞、Task 0 加 G0 人工门；新增执行前决策门表 G0–G5；Task 12 Step 3 因 envelope_mismatch 并入 Task 11 而改为核对步。
6. **r4 确认轮修订（2026-08-06）**：背压检查从 tick 移入 I/O 线程（原实现让主线程 `_drop` → `sock.close()`，自相矛盾地违反了刚建立的「主线程从不触碰 socket」）；`outbox_bytes` 增减全程持锁（单边持锁不是互斥）；`_proto` 加 `TYPE_CHECKING` 分支（否则 mypy 把 protocol 判为 Any，strict 下 `warn_return_any` 全线报错）；Task 0 补 `bridge/__init__.py`（缺席则 mypy duplicate module）；ruff 显式 `select` + 钉 `<0.17`（默认规则集逐版本扩张）；修 test_router.py 的 `BridgeMeta` 导入源；补 outbox 上限 L2 测试。
5. **r3 对抗审计后修订（2026-08-06）**：写路径改单写者模型（T7 重写：outbox + I/O 线程独占 socket 写 + 每轮护栏 + 背压上限，发送锁废止）；mypy strict 全量兼容（泛型参数化、属性声明进 __init__、overrides 挡开 bpy 与适配层）+ 逐任务 lint/type 门禁；pyproject 补 build-system（无它则 entry point 不装）；L3 runner 状态机化（timer 回调内 join 会自饿死）；bg_check 限时泵 + --python-exit-code；T16 补 4 条 spec §7.2 必测（交错/序列化护栏/N 连接回收/认证日志）与 mini-bridge 短路径。

## 执行交接

计划完成并保存至 `docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`。两种执行方式：

**1. Subagent-Driven（推荐）** —— 每任务派发独立 subagent，任务间审查，迭代快

**2. Inline Execution** —— 本会话内按 executing-plans 批量执行，检查点审查

选哪种？
