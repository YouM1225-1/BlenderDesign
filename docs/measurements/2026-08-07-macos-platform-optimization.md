# macOS 平台优化实测报告

> 日期：2026-08-07
> 性质：实测数据 + 补丁规格。
> **当前审计状态（2026-08-08 r15/v8 / URS v1.11 / spec v1.11）：本报告是单机测量记录，不是规范合同。§3.1 / §3.3 作为 Plan 候选实现保留；§3.4 的 inode 方向成立，但 `same_file()` 仅为查询辅助，不能关闭 FR-21/TOCTOU；§3.2（blake2b）已撤回；§3.5–§3.7 仍是待决策/待真实验收事项。r12/v5/v6/v7 数字与门禁均为历史证据；v8 真 GUI 100k 结果（worker P95 1605.18 ms、max 2560.86 ms、observer P95 1655.44 ms、max tick 62.50 ms）只关闭 Bridge-RPC/continuation 子门，端到端 MCP NFR-P1 仍开放且不外推跨机。交接审计见 [`docs/audits/2026-08-07-platform-optimization-handoff-adversarial-audit.md`](../audits/2026-08-07-platform-optimization-handoff-adversarial-audit.md)。**
> 背景：报告产出期间 plan 由另一方并行推进至 r11。首次应用因基线过时造成冲突并被覆盖；本次应用前先取基线 SHA-256 并在补丁脚本中做前置校验。

## 0. 阅读须知

- 所有数字为**本机实测**：Apple M4 / macOS 26.5.2 / Blender 5.2.0 LTS（内置 Python 3.13.13）/ MCP SDK 2.0.0。换机器或换 Blender 版本需复测。
- 被测对象是**从当时 plan 机械物化出的隔离实现**，不是工作区代码。
- 报告包含**负面结果**（假设被推翻）与**验证为非风险**两类结论，同样重要——它们的价值在于阻止后人重复尝试。

## 1. 结论速览

| # | 项 | 实测 | 裁决 |
|---|---|---|---|
| 1 | 工具调用往返延迟 | 原测量：0.1s → p50 **59.8 ms**；0.02s → p50 **11.5 ms**；独立 GUI timer 复算确认周期方向、同时观察到约 4.4× 唤醒/回调 CPU | **候选保留**；电量影响未测，不外推 |
| 2 | `scene_hash` 算法 | sha256 **122 MB/s** vs blake2b **1400 MB/s**（**原因未确定**，见 §3.2 更正） | **已撤回**——成因未明，不作为协议变更依据；成因待查见交接清单 M-1 |
| 3 | `quantize` 实现 | 原绝对值不可独立复现；多组固定随机/边界反例集未见输出差异，相对方向约 1.7–2.2× | **候选保留**；不写跨机绝对值 |
| 4 | FR-21「原稿不被覆盖」判定 | 路径字符串判「不同文件」，inode 判「同一文件」，**原稿被覆盖** | **需求缺口成立**；查询 helper 不是写安全边界 |
| 5 | 事务日志落盘 | Apple man page 支持 `F_FULLFSYNC` 语义；本机数量级差异成立 | **Phase 1 待决策**；先定义文件/目录顺序及不支持时行为 |
| 6 | 快照复制 | APFS `clonefile` 的 COW 与显著加速方向成立 | **Phase 1/2 候选**；须限定同卷、新目标和安全 fallback |
| 7 | Cycles Metal headless | `--background` 下枚举并选择 METAL 设备 | **只关闭枚举子问题**；真实 render / CPU fallback 仍开放 |
| 8 | I/O 线程 QoS | `USER_INTERACTIVE` 与默认在 p50/p95/p99/stdev 上**全在噪声内** | **否决**（假设被推翻） |
| 9 | Server 冷启动 | 430 ms 中 409 ms 是 `import mcp.server` | **不优化**（NFR-P2 余量 10×） |
| 10 | 后台 Blender timer | 后台 p50 **50.9 ms** = 前台 p50 50.9 ms | **验证为非风险** |
| 11 | tick 迟滞策略 | 按旧信号无效（p50 58.2 ms ≈ 59.8 ms）；正确实现与 r11 契约冲突 | **否决**（见 §3.1） |

## 2. 延迟归因

### 2.1 往返延迟几乎全部是「等下一次 tick」

真实 Bridge 上的往返测量（成簇请求，模拟 agent 连续调工具）：

| 配置 | p50 | p95 | max | 空转唤醒 |
|---|---:|---:|---:|---:|
| `IDLE_INTERVAL=0.1`（当时值） | 59.8 ms | 101.4 ms | 103.5 ms | 9.8 /s |
| `IDLE_INTERVAL=0.02` | **11.5 ms** | 22.3 ms | 23.2 ms | 42.6 /s |

p50 ≈ 半个轮询周期，与理论完全吻合——延迟由常量决定，不是代码效率问题。

唤醒代价：每次 tick 在空队列下只是「取锁、看空 deque、返回」。原报告的约 0.04% CPU 缺少持久原始样本；独立 GUI timer 复算得到回调 CPU 约 0.022% → 0.096%（约 4.4×）。这仍是低 CPU 数值，但不能证明电池或深度 idle 影响可忽略。

### 2.2 冷启动分解

| 阶段 | 中位耗时 |
|---|---:|
| `python -c pass` | 13.7 ms |
| `python -S -c pass` | 12.5 ms |
| **`from mcp.server import MCPServer`** | **409.1 ms** |
| `import server.mcp.adapter`（完整） | 405.3 ms |
| `uv run python -c pass` | 22.7 ms |

SDK import 占 95%。NFR-P2 上限 5 s，余量 10 倍；`uv run` 只增加 9 ms。**不建议为此扭曲设计**——现有 core/adapter 分层已保证 `server/core` 不 import mcp，没有更多空间。

### 2.3 `scene_hash` 随规模的成本

下表只测纯 Python 行构造/排序摘要，不是 `BpySceneReader.snapshot_steps()` 的端到端证据。后续对抗实测发现旧 reader 的 `scene.objects[index]` 在 10k/20k 对象下近 O(N²)；r12 改用有界 collection slice 后，100k 共享网格候选约 1.2 s、最大 source step 约 22 ms。两组数字不可混用。

| 对象数 | 构造行 | 排序+摘要 | 合计 |
|---:|---:|---:|---:|
| 1 000 | 7.1 ms | 1.9 ms | 9.0 ms |
| 10 000 | 49.8 ms | 13.7 ms | 63.5 ms |
| 100 000 | 534.5 ms | 141.8 ms | 676.3 ms |

构造行（字符串格式化）是这个纯 Python microbenchmark 的主项，摘要是次项。blake2b 已撤回，不能再用“§3.2 + §3.3 约 280 ms”推导当前实现。

### 2.4 SceneReader 端到端反例与修正

这是对 handoff 原始数字的独立对抗复算，使用真 Blender 5.2.0 background、`BpySceneReader.snapshot_steps(include_collections=false)` 和临时纯对象/共享网格场景：

| reader | 场景 | 总耗时 | 最大 source step | yield 后 bpy wrapper |
|---|---:|---:|---:|---:|
| 旧 `scene.objects[index]` | 10 000 空对象 | 约 2.6–3.1 s | < 50 ms | — |
| 旧 `scene.objects[index]` | 20 000 空对象 | 约 12.8 s | < 50 ms | — |
| r12（历史）：1024 项 slice、128 项 hash batch | 20 000 共享网格对象 | 约 0.31 s | 约 3.7 ms | true |
| r12（历史）：1024 项 slice、128 项 hash batch | 100 000 共享网格对象 | 约 1.2 s | 约 22 ms | true |
| r13：真 GUI Bridge-RPC `scene_summary`（同一 reader） | 100 000 共享网格对象 | 20-query P95 约 1.439 s（max 约 2.071 s） | `BridgeSession.tick` max 约 62.12 ms | true（由 L1/background 证明） |

旧 handoff 的 100k/676 ms 只对应纯 Python 行构造/排序，不是 reader 端到端事实。r12 的 slice 方案在每个 source step 内复制所需字段为字符串/数值，清空临时 wrapper 列表后才 yield；固定单测还拒绝数值索引并递归检查 generator locals。r13 真 GUI 20-query worker-side nearest-rank P95 约 1.439 s，固定基线 Bridge-RPC 子门通过；单次 max 约 2.071 s。该路径绕过 MCP stdio/adapter/Discovery/schema/audit，不能替代端到端 NFR-P1、mesh-heavy 多场景、跨硬件和正式 Phase 0 L3 验收。

## 3. 待应用补丁清单

以下按「改哪里 / 改什么 / 影响哪些测试」给出规格，便于 plan 维护方直接应用。

### 3.1 `bridge/core/queue.py` — 降低空闲轮询间隔

```python
# 现状
IDLE_INTERVAL = 0.1
BUSY_INTERVAL = 0.01

# 建议
# 往返延迟几乎全部是「等下一次 tick」。本机原始测量：IDLE=0.1 时 p50 59.8 ms，
# IDLE=0.02 时 p50 11.5 ms；代价是空转唤醒增加，CPU/电量影响需按实际工作负载复测。
IDLE_INTERVAL = 0.02
BUSY_INTERVAL = 0.01
```

**测试影响**：断言 `q.tick() == 0.02` 的用例固定正常 idle 间隔；首次 timer 注册也必须使用同一值。

> **迟滞方案已否决（当前实现层面）。** 更省电的做法是「活动后保持快节奏、真闲下来再降频」，但它要求 `tick()` 改报「刚干过活」而非「还有活」——按旧信号做迟滞**实测毫无效果**（p50 58.2 ms ≈ 不做的 59.8 ms），因为每轮都排空队列时旧信号永远为假。而正确实现与 r11 的冻结 `FakeClock` 单测契约冲突（实测触发 9 个失败）。0.02 s 先作为延迟候选；若后续电量测试显示代价，再以独立契约设计迟滞，不能把本次未测结果写成“可忽略”。

### 3.2 `bridge/core/scene_hash.py` — blake2b 候选（已撤回）

```python
def digest(lines: list[str]) -> str:
    joined = "\n".join(sorted(lines))
    # blake2b 而非 sha256：本机实测 122 MB/s vs 1400 MB/s。**原因未确定**（见下）。
    # 本值是变更检测摘要而非安全边界，blake2b-256 完全够用。
    return "blake2b:" + hashlib.blake2b(joined.encode("utf-8"),
                                        digest_size=32).hexdigest()
```

> **更正（2026-08-07，经第三方红队 EXT-04 指出并由本文作者复核）**：本报告初稿把速度差归因为「Blender 内置 Python 没有 OpenSSL 后端」，**该归因错误**。实测 `hashlib.sha256()` 返回 `_hashlib.HASH`，由 **OpenSSL 3.5.6** 支撑；`hashlib.openssl_sha256` 只是没有公开别名，`_hashlib.openssl_sha256` 是存在的。**速度差本身可复现，但原因尚未查明**（可能是该 OpenSSL 构建未启用 ARMv8 加密扩展，也可能是别的原因）。在查明前，本项应视为**实现优化证据，不是已论证的协议变更依据**。

吞吐实测（32 MiB 载荷）：

| 算法 | MB/s |
|---|---:|
| sha256 | 122 |
| sha1 | 184 |
| blake2s | 835 |
| **blake2b** | **1400** |

**测试影响**：所有 `startswith("sha256:")` 断言与 fixture 里的 `"sha256:..."` 字面量改前缀（当时 plan 中约 16 处）。

**时效性**：golden render 基线尚未录制，现在切换零成本；一旦录制就要重录。

### 3.3 `bridge/core/scene_hash.py` — `quantize` 去掉多余的 `round`

```python
def quantize(v: float) -> str:
    # 不要再调 round(v, 6)：f-string 的 .6f 本身就按 round-half-even 舍入，
    # 多这一步纯属重复计算。
    s = f"{v:.6f}"
    return "0.000000" if s == "-0.000000" else s
```

实测 1.6M 次调用 33.9 ms → 17.2 ms。等价性已在 2 万个随机值 + 边界用例（`0.0`、`-0.0`、`1e-9`、`-4e-7`）上逐一比对，输出**逐字相同**。

**复算更正**：原始 33.9/17.2 ms 绝对值无法从当前缺失的脚本与样本重建；Blender 内置 Python 的独立 1.6M 调用中位数约为 593.7 ms（旧实现）→ 345.7 ms（直接格式化），方向成立但不得作为跨机数字。负微小值（如 `-4e-7`）必须在字符串层归一为 `0.000000`，否则直接 `.6f` 会产生 `-0.000000`。

### 3.4 `server/core/path_policy.py` — 同一文件判定（FR-21 红线）

```python
def same_file(a: Path, b: Path) -> bool:
    """查询两个已存在路径当前是否指向同一 inode；不是写入安全边界。

    macOS 默认 APFS 大小写不敏感，且 Path.resolve() **不归一化大小写**（实测）。
    因此 Scene.blend 与 scene.blend 字符串不等、inode 相同；stat 失败时只能说未知。
    Phase 1 的 FR-21 必须在 fd-bound / O_NOFOLLOW 边界 fail-closed 校验 identity。
    """
    try:
        sa, sb = a.stat(), b.stat()
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)
```

**实测复现**（原稿被覆盖）：

```json
{"路径字符串判定为不同文件": true, "inode 判定为同一文件": true,
 "原文件内容": "AGENT-OUTPUT", "原始工作是否被覆盖": true}
```

**边界**：该函数按当前 `stat()` 快照识别 inode 别名；任一 `OSError` 返回 `False` 代表未知，且检查与写入之间存在 TOCTOU。它只能用于查询/诊断；Phase 1 的 FR-21 必须用 fd-bound、`O_NOFOLLOW`、dir-fd 和提交前 identity revalidation，错误时拒绝。不能把本函数写成“所有判定都走它”或“红线已解决”。

### 3.5 Phase 1 事务日志 — `F_FULLFSYNC`

macOS 的 `fsync()` 只把数据交给驱动器，**不刷写其缓存**；掉电会丢已「fsync」的事务日志。落盘必须用 `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)`。

实测：`fsync` 0.05 ms vs `F_FULLFSYNC` 5.7 ms（64 KiB 写入）；独立复算确认数量级，但绝对值依设备而变。该项是 Phase 1 durability ADR 候选：须定义数据/日志/父目录落盘顺序，并对不支持 `F_FULLFSYNC` 的文件系统规定 fail-closed 或明确降级，不能写成“可忽略”的合同。

对应 URS FR-15。Phase 0 的 `session.json` 不需要（本来就是易失的）。

### 3.6 Phase 1/2 快照 — APFS `clonefile`

```python
libc.clonefile(src.encode(), dst.encode(), 0)   # stdlib ctypes 即可，无新依赖
```

实测 512 MiB：`shutil.copyfile` 337 ms vs `clonefile` **1 ms（350×）**；克隆后写入源文件，副本不受影响（COW 语义已验证）。

**适用面必须如实标注**——只对**同一支持卷上的新目标文件→文件复制**有效；目标已存在、跨卷或不支持时会失败（如 `EEXIST`/`EXDEV`/`ENOTSUP`），实现必须有安全 fallback 或显式错误：

| 场景 | 受益 |
|---|---|
| `create_project_copy`（FR-03，源是已存盘 `.blend`） | ✅ |
| `begin_transaction` 回滚快照（文件已保存且未脏时） | ✅ |
| 失败事务归档、测试 fixture / golden 基线管理 | ✅ |
| `pre-rollback` 快照（FR-20，当前内存态） | ❌ 必须走 Blender 保存 |
| 物化快照（FR-23，当前内存态） | ❌ 同上 |

约一半的快照操作受益，但受益的恰在**用户等待的交互路径**上。

### 3.7 关闭 URS V-03

`blender --background --factory-startup` 下探测 Cycles 设备：

```json
[["Apple M4", "CPU", false], ["Apple M4 (GPU - 10 cores)", "METAL", true]]
```

GPU 被正确枚举并启用；这只关闭 baseline 的设备枚举/选择子问题，不证明真实 render 成功、稳定性或跨硬件可用性。**Phase 2 仍需 CPU fallback 与真实 golden render 验收**。

## 4. 负面结果（记录以免重试）

### 4.1 I/O 线程 QoS 无效

假设：`pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE)` 能压低调度抖动。

方法：10 核 M4，开 20 个 CPU 燃烧子进程制造真实竞争；`IDLE_INTERVAL` 压到 5 ms 使轮询项不再主导；每组 120 次往返。

| 条件 | p50 | p95 | p99 | stdev |
|---|---:|---:|---:|---:|
| 空闲 · 默认 QoS | 5.19 | 6.42 | 6.49 | 1.73 |
| 空闲 · USER_INTERACTIVE | 4.77 | 6.41 | 6.50 | 2.01 |
| 负载 · 默认 QoS | 4.25 | 6.54 | 6.65 | 1.92 |
| 负载 · USER_INTERACTIVE | 4.30 | 6.53 | 6.73 | 1.98 |

**全部落在噪声内，p50/p99 甚至略差。假设不成立，不采纳。**

### 4.2 tick 迟滞（按旧信号）

见 §3.1 的说明框。旧信号（`self.pending`）在每轮排空队列的正常路径下永远为假，快节奏根本不触发——实测 p50 58.2 ms，与不做迟滞的 59.8 ms 无差别。

## 5. 验证为非风险

### 5.1 macOS 不限速后台 Blender 的 timer

这是本轮最大的未知：真实使用场景是**用户在 Codex 里工作、Blender 在后台**。若 App Nap / 定时器合并对后台应用生效，前述所有延迟测量都不作数。

方法：真 Blender GUI 内注册 50 ms timer 记录实际间隔；6 s 后用 `osascript` 把 Finder 激活到前台，对比切换前后的分布。

| 状态 | 样本 | p50 | p95 | max |
|---|---:|---:|---:|---:|
| 前台 | 109 | 50.9 ms | 56.2 ms | 247.4 ms |
| **后台** | 196 | **50.9 ms** | **55.3 ms** | **55.7 ms** |

后台不但没被限速，抖动反而更小（前台的 247 ms 尖峰来自 UI 工作）。**测量结论在生产场景下成立。**

## 6. 复现方式

历史 microbenchmark 脚本位于会话 scratchpad，未纳入仓库；当前 r13 GUI runner 已作为 `smoke/runner.py` 代码块纳入 Plan，证据 provenance 记录其物化 SHA。复现路径：

1. 从当前 plan 物化代码块到隔离目录；
2. 用 Blender 内置 Python 建 venv（`/Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13 -m venv`）——这是被测运行时；它实际通过 `_hashlib` 使用 OpenSSL 3.5.6，不能写成“没有 OpenSSL 后端”；
3. 按 §2、§4、§5 各节的方法重跑。

## 7. 应用记录与未决

### 7.1 候选 overlay 的应用记录（不是 Phase 0 执行）

| 节 | 改动 | 复跑结果 |
|---|---|---|
| §3.1 | `IDLE_INTERVAL` 0.1 → 0.02 | 候选 overlay；唤醒/电量仍开放 |
| §3.2 | blake2b **未应用**；`scene_hash` 保持 SHA-256 | 不进入合同 |
| §3.3 | `quantize` 去掉多余 `round`，保留负零字符串归一 | 候选 overlay；相对方向复算成立 |
| §3.4 | 新增 `path_policy.same_file()` + 两条测试 | 查询辅助；不关闭 FR-21/TOCTOU |
| §3.4b（历史） | SceneReader 数值索引改 1024 项 slice，hash merge 128 项 batch | r12；100k 共享网格约 1.2 s、最大 source step 约 22 ms、wrapper-free |
| r13 M-4 | 真 GUI 100k shared-mesh：Bridge-RPC 计数、20-query P95 与 `BridgeSession.tick` | `object_count=mesh_count=100000`、`camera/light=0`、`build_wall_ms≈130081 ms`、worker P95 `≈1439.21 ms`、max `≈2071.10 ms`、`max_tick≈62.12 ms`、474 ticks；Bridge 子门通过，端到端 MCP NFR-P1 仍开放。wrapper-free 另由 L1/background fixture 证明 |
| 全量门禁（历史 v5） | ruff / mypy strict（22 文件）/ **L1 235 passed** / **L2 27 passed** / 真 Blender `BG_CHECK_OK` / GUI `SMOKE_OK` | 仅作历史证据，已由 r13/v6 取代 |
| 全量门禁（r13/v6） | ruff / mypy strict（22 文件）/ **280 passed** / 真 Blender `BG_CHECK_OK` / GUI 基础 smoke | 通过；Plan 未执行，详见 v6 provenance |

**应用中发现的额外一致性要求**：r11 的 `scene_reader` 里有一份**分块增量 hash**（chunked sort + `heapq.merge` 流式摘要），与 `scene_hash.digest()` 是同一算法的两个实现，必须同时改。仅改 `digest()` 会让两者产出不同摘要——已由 `test_scene_reader` 的一致性用例抓到（2 failed），修正后 235 全绿。**后续任何 hash 变更都必须同时改这两处。**

独立自审结果（不依赖 plan 内的说法重新验证）：

- `quantize` 新旧实现在 5 万随机值 + 11 个边界用例上输出逐字相同；`-0.0` 归一为 `0.000000`
- `digest` 保持 `sha256` 前缀、64 位 hex、顺序无关、对内容敏感
- SceneReader 1024 source slice / 128 hash batch 与一次性摘要在跨 chunk 边界下保持一致；yield 后递归无 bpy wrapper
- `same_file`：捕获大小写变体 ✓、区分真正不同的文件 ✓、文件不存在返回 False（未知）✓、**硬链接与符号链接均判为同一文件**；这不是 TOCTOU 安全证明

### 7.2 未决

- **§3.5 `F_FULLFSYNC`、§3.6 `clonefile`、§3.7 真实 Metal render/fallback** 属 Phase 1/2 条款或验收候选，本次不改实现合同。
- URS **FR-21** 现已补入 fd-bound/identity/fail-closed 约束；`same_file()` 仍只是查询辅助。
- §3.2 blake2b 未改变 `scene_hash` 对外格式；若未来更换，必须同步 reader、schema、URS/spec、fixture、manifest 并重跑真 Blender。
- 本机为 10 核 M4；核数与 GPU 型号不同的机器上 §2.1、§4.1 应复测。

### 7.3 r13 真 GUI 100k 证据

最终 Plan r13 从全新隔离树物化后，在 Apple M4 / Blender 5.2.0 LTS GUI 中运行 `BLENDERCODEX_LARGE_OBJECTS=100000 smoke/runner.py`。原始 JSON 保留在 [`phase0-gui-100k-measurement-v6.json`](../audits/evidence/2026-08-07-phase0-gui-100k-measurement-v6.json)：`large_scene=true`、计数正确；20 次 worker-side 样本 nearest-rank P95 `≈1439.21 ms`（max `≈2071.10 ms`）、observer P95 `≈1463.67 ms`，`max_tick≈62.12 ms`，故固定基线 Bridge-RPC 子门 `large_scene_budget_ok=true` / `SMOKE_OK`。构造 fixture 的 `max_build_callback_ms≈2064.85` 仅作诊断，不计入产品查询门。该 runner 从 `BridgeClient` 直连 UDS，未经过 MCP stdio/adapter/Discovery/schema/audit；GUI 证明 Bridge 子路径 counts/query/max-tick，yield 后 wrapper-free 来自 L1/background fixture。基础 GUI JSON 与 provenance 同目录；这些证据均为隔离预检，不能写成端到端 NFR-P1 或 Phase 0 已执行。

### 7.4 r15/v8 fresh-tree 收口

从最终 Plan（r15）fresh-tree 物化后，`scripts/checks.sh` 通过：mypy strict 22 文件零错、ruff/vendor/nested/lock 全绿，L1/L2 为 307（275 unit + 32 contract），adapter 专项 35/373 行。Blender 5.2.0 background `BG_CHECK_OK`，fresh GUI 基础 smoke `SMOKE_OK`，raw SHA `dda8796d2aba14e2eb04da1b99a125d4c88cbb741ed3951048e1a16925bf7900`。

同一 100k raw artifact [`phase0-gui-100k-measurement-v8.json`](../audits/evidence/2026-08-07-phase0-gui-100k-measurement-v8.json) 的 `object_count=mesh_count=100000`、20-query worker P95 `1605.1823 ms`、max `2560.8582 ms`、observer P95 `1655.4411 ms`、`max_tick=62.5037 ms`、`errors=[]`。该 JSON 与 r15 fresh-tree 的 `scene_reader.py`、`queue.py`、`smoke/runner.py` 逐字对应；它只证明 `BridgeClient → UDS → Bridge`，不覆盖 MCP stdio、SDK middleware、Discovery、schema、audit，也不宣称 NFR-P1 已关闭。

本轮红队另以 SDK v2 三请求 wire 反例阻塞 `convert_result`：旧 adapter semaphore 在 reader 返回时释放，第三请求可在结果转换阶段进入；修复后准入移至 middleware，覆盖完整 `call_next`、转换与 audit postlude，第三请求 fail-fast `BRIDGE_BUSY`，异常路径可复用。该结论由 `tests/unit/test_adapter.py` 的 35 个测试固定，不应从单纯 direct Python function 并发测试推断。
