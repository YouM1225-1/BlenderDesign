# 平台优化交接清单

> **固定时点交接快照（2026-08-07 至 2026-08-08）**：§1–§6 保留 Plan SHA `4216c69a…` 时的 r12 前原始交接，§0.1 与 §5 保留随后 r15/r16 融合和所有者裁决时态；相关证据链由 `e5ac5590f8ab2d2df915771f5266bc549a3b3a4e` 冻结。全文不追踪 r17 等后续修订，旧的 262/307-test、checkbox、Gate 与审批表述均不得当作 live 状态；当前状态统一见 [ROADMAP](../ROADMAP.md)。

> 日期：2026-08-07
> 交接方：macOS 平台优化实测（本文作者）
> 接收方：Phase 0 plan / URS / spec 维护方
> 相关文档：[实测报告](../measurements/2026-08-07-macos-platform-optimization.md) · [融合对抗审计](../audits/2026-08-07-platform-optimization-handoff-adversarial-audit.md) · [收口 v3](../audits/2026-08-07-closeout-v3.md)

## 0. 原始一句话交接（历史快照）

交接当时的统计是：四项平台优化中**三项已合入 plan 并全门禁通过**，第四项（blake2b）按用户裁决**撤回**；另有 **5 项待办**、**4 项待实测**、**2 项需你方决策**。这些数量是原始快照，当前状态见 §0.1 与 [ROADMAP](../ROADMAP.md)。

## 0.1 融合后的待办裁决（先审计，再执行）

| 项目 | 当前状态 | 是否阻断 Phase 0 |
|---|---|---|
| T-1 FR-21 inode / fd-bound 要求 | 已写入当前 URS v1.15；`same_file` 仍仅查询辅助，Phase 1 写入边界未实现 | 否（Phase 1 前必须保留） |
| T-2 F_FULLFSYNC | 证据方向成立，留作 Phase 1 durability ADR；本轮不进入 Phase 0 | 否 |
| T-3 APFS clonefile | 适用面/失败语义已核实，留作 Phase 1/2 候选；不替代内存态快照 | 否 |
| T-4 Cycles Metal | baseline 枚举/选择已复现；真实 render 与 CPU fallback 仍属 Phase 2 | 否（不得误写“完全关闭”） |
| T-5 manifest / provenance | v5–v8 仅固定历史 r15；r16 proposed 将由 B-5 manifest/审计固定，获批提交后再形成两提交 post-freeze attestation 链 | **B-5 proposed tuple 待批** |
| M-1 / M-2 / M-3 | blake2b 成因、跨机/跨版、battery 影响均未形成合同；只保留为后续测量 | 否 |
| M-4 大场景 GUI | v8 真 GUI 100k Bridge-RPC 子路径：20-query P95 `1605.18 ms`（max `2560.86 ms`）、observer P95 `1655.44 ms`、`max_tick=62.50 ms`，结构/计数通过；未覆盖 MCP stdio/adapter/Discovery/schema/audit | Bridge 子门关闭；端到端 NFR-P1 仍开放 |
| D-1 | 项目所有者已于 2026-08-08 明确接受全部三项平台候选 | 已关闭 |
| D-2 | 提交动作已由 `e5ac559` 完成 | 已关闭；不能反推 D-1 已批准 |
| 新增红队项 | r15/v8 项继续保留；r16 另补 20-ID 映射、三工具 NFR-P1、真 SIGKILL/restart、foreign uid/device/ancestor/FIFO/stale/load_pre 直接反例与 helper deadline/process/audit/provenance 护栏 | G5 以风险接受关闭；仅 B-5 proposed tuple/批准仍阻断 Task 0 |

这张表是 §2–§5 历史清单的 live 融合索引；不把候选隔离预检写成 Phase 0 已实施，也不把 G5 风险接受写成 screenshot/render 缺陷修复。

## 1. 原始候选合入记录（r12 审计前历史快照，不是当前待验证项）

> 本节所有门禁数字（包括 262 passed）均为 r12 历史值；r15/v8 历史数字见 v8 provenance 与 closeout v3，live r16 只见 §0.1、ROADMAP 与 r16 B-5 审计。

plan SHA-256（合入后）：`4216c69ac6c0e0f803e3fbc1340d7886c9baea782abb40bd6491f24221dcf988`
合入前基线：`a05bf3dd2456180052e22375917cc4ef8e33a3451d505a4e1090884b660be7bf`（与红队报告的复原基线一致）

| # | 改动 | 位置 | 依据 |
|---|---|---|---|
| 1 | `IDLE_INTERVAL` 0.1 → 0.02 | `bridge/core/queue.py` + 1 条断言 | 往返 p50 **59.8 ms → 11.5 ms**（5×）；空转唤醒 9.8/s → 42.6/s，每次仅取锁看空 deque |
| 2 | `quantize` 去掉多余 `round(v, 6)` | `bridge/core/scene_hash.py` | 1.6M 次调用 **33.9 ms → 17.2 ms**；等价性在 5 万随机值 + 11 个边界用例上逐字比对通过 |
| 3 | 新增 `same_file(a, b)` + 2 条测试 | `server/core/path_policy.py` | FR-21 红线：APFS 大小写不敏感下按路径字符串判定会让原稿被静默覆盖（已实测复现） |

**合入后门禁**（隔离物化树，Blender 5.2.0 内置 Python 3.13.13 + mcp 2.0.0）：

```
ruff            All checks passed
mypy strict     22 source files, 0 errors
pytest          262 passed（unit 235 + contract 27）
Blender bg      BG_CHECK_OK
Blender GUI L3  SMOKE_OK，五项判据全 true，errors=[]
```

### 已撤回：blake2b

按用户裁决撤回，`scene_hash` 保持 SHA-256。理由采纳红队 EXT-04 的定性：**加速可复现（122 → 1400 MB/s）但成因未查明**，属实现优化证据而非已论证的协议变更依据。plan 里保留了一条注释说明这一点及未来更换时的同步范围。

## 2. 待办（历史清单；当前裁决见 §0.1）

> 以下 T-1–T-5 是交接当时的原始问题描述。URS/spec 已在 v1.11/r15 中同步其中已采纳项；保留原文用于追溯，不应再次按本节标题执行或判断当前缺口。

### T-1（历史 P0，已在 URS v1.11 写入；Phase 1 边界仍开放）

**历史现状**：plan 已交付 `path_policy.same_file()` 并在 docstring 说明理由；当时 URS FR-21 尚未规定判定方式。该需求缺口已在 URS v1.11 写入；`same_file()` 仍不是 Phase 1 的 fd-bound/TOCTOU 防线。

**实测复现**（macOS 默认 APFS）：

```json
{"路径字符串判定为不同文件": true, "inode 判定为同一文件": true,
 "原文件内容": "AGENT-OUTPUT", "原始工作是否被覆盖": true}
```

**建议措辞**：在 FR-21 后追加——「『是否写到原文件』的判定必须按 `(st_dev, st_ino)`，不得比较路径字符串。macOS 默认 APFS 大小写不敏感且 `Path.resolve()` 不归一化大小写，`Scene.blend` 与 `scene.blend` 字符串不等、inode 相同。」

**注意红队 EXT-03 的正确提醒**：`same_file()` 只是路径查询辅助，**不能替代 Phase 1 的 fd-based / `O_NOFOLLOW` 写入边界**（TOCTOU）。两者是互补关系，不要在文档里把它写成已解决 TOCTOU。

### T-2（P1）URS FR-15 未写入 `F_FULLFSYNC`

macOS 的 `fsync()` 只把数据交给驱动器，**不刷写其缓存**；掉电会丢已「fsync」的事务日志。FR-15 要求事务状态持久化用于崩溃恢复，当前措辞不足以保证这一点。

实测：`fsync` 0.05 ms vs `fcntl(fd, F_FULLFSYNC)` 5.7 ms（64 KiB）。事务提交时一次，可忽略。

Phase 0 的 `session.json` **不需要**（本来就是易失的，重启即重建）。

### T-3（P1）URS FR-24 可加入 APFS `clonefile`

实测 512 MiB：`shutil.copyfile` 337 ms vs `clonefile` **1 ms（350×）**，COW 隔离已验证。stdlib `ctypes` 即可，无新依赖。

**适用面必须如实标注**，否则会被误读为「所有快照都 O(1)」：

| 场景 | 受益 |
|---|---|
| `create_project_copy`（源是已存盘 `.blend`） | ✅ |
| `begin_transaction` 回滚快照（文件已保存且未脏时） | ✅ |
| 失败事务归档、fixture / golden 基线管理 | ✅ |
| `pre-rollback` 快照（FR-20，当前内存态） | ❌ 必须走 Blender 保存 |
| 物化快照（FR-23，当前内存态） | ❌ 同上 |

### T-4（P1）URS V-03 可关闭

> **历史建议，已被融合裁决取代**：本节原文的“Phase 2 无需 CPU 降级预案/建议关闭”不再是当前结论。融合表保留真实 render 与 CPU fallback 为 Phase 2 待验证项；本节仅保留当时的 Metal 枚举观测，不能作为 V-03 完全关闭依据。

`blender --background --factory-startup` 下探测 Cycles 设备：

```json
[["Apple M4", "CPU", false], ["Apple M4 (GPU - 10 cores)", "METAL", true]]
```

GPU 被正确枚举并启用；这只关闭 Metal 枚举/选择子项。真实 render 与 CPU fallback 仍须在 Phase 2 以独立 golden 证据验证。

### T-5（历史 P2，v8 manifest / provenance 已完成）

本次合入改动了 plan 的 Python 代码块，曾使旧 manifest 失效。该历史缺口现已由 r15/v8 重新物化、46/46 parity、v8 artifact/vendor manifest 与 provenance 闭环；当前不再是缺失证据，只保留用户审批门。

本文作者的隔离验证已跑通；最终树、命令和 SHA 见 v8 provenance，仍不等同于 Phase 0 已执行。

## 3. 待实测（我没做完或做不了的）

### M-1 blake2b 加速的真实成因

**已知**：Blender 5.2.0 内置 Python 3.13.13 上，sha256 = 122 MB/s，blake2b = 1400 MB/s（32 MiB 载荷，中位数，5 次）。

**已排除**：不是「缺 OpenSSL 后端」——`hashlib.sha256()` 返回 `_hashlib.HASH`，`ssl.OPENSSL_VERSION` = OpenSSL 3.5.6，`_hashlib.openssl_sha256` 存在（只是没有 `hashlib.openssl_sha256` 公开别名）。

**未查明**：是该 OpenSSL 构建未启用 ARMv8 加密扩展（`sha2` / `sha512` feature），还是 EVP 层开销，还是别的。

**建议方法**：`openssl speed -evp sha256` 对比系统 OpenSSL；检查 Blender 内置 OpenSSL 的编译配置；跨 Blender 版本与跨机器复测。查明前不应把它写进任何合同。

### M-2 跨机器 / 跨版本复测

本轮全部数字来自单机（Apple M4 10 核 / macOS 26.5.2 / Blender 5.2.0 LTS）。以下项对硬件敏感，换机器需复测：

- §2.1 往返延迟与唤醒频率（核数、能效核比例）
- §4.1 QoS 负面结论（核数、调度器版本）
- M-1 的 hash 吞吐（CPU 加密扩展）

### M-3 `IDLE_INTERVAL = 0.02` 的电量影响

**已测**：CPU 开销可忽略（每次唤醒仅取锁看空 deque，约 0.04%）。

**后续复算更正**：原“约 0.04%”缺少持久原始样本；独立 GUI timer 复算为回调 CPU 约 0.022% → 0.096%（约 4.4×）。这仍是低 CPU 数值，但不能证明电池或深度 idle 影响可忽略。

**未测**：对电池续航的实际影响。42.6 次/秒的唤醒会阻止 CPU 进入更深的空闲状态；在插电工作站上无所谓，笔记本长时间挂机场景需要实测（`powermetrics` 采样对比）。

**若发现有影响**：正确解法是迟滞（活动后快、真闲下来慢），但**必须避开我踩过的坑**——见 §4 的 EXT-02。

### M-4 大场景下 tick 预算的真实表现

历史 r13/v6 测量保留如下：构造约 `130081 ms`，worker P95 `≈1439.21 ms`、max `≈2071.10 ms`，`max_tick≈62.12 ms`。v8 复测结果为：构造 `167361.47 ms`，worker P95 `1605.18 ms`、max `2560.86 ms`，observer P95 `1655.44 ms`、max `2598.42 ms`、`max_tick=62.50 ms`。两者都只证明 `BridgeClient → UDS → Bridge` 的 counts/query/max-tick；未经过 MCP stdio、SDK middleware、Discovery、Pydantic output validation 与 audit postlude，因此只能关闭 M-4 的 Bridge/continuation 子门，不能单独关闭端到端 NFR-P1；不能外推到其他机器/Blender 版本。

后续正式 Phase 0 须补 MCP tools/call → 真 GUI 的 20-query/P95 计时并重跑本子门；50 ms 仍是 cooperative budget（不是硬墙钟），`max_tick_ms` 只能作为本机证据。

## 4. 我踩过的坑（务必避开）

| 坑 | 后果 | 教训 |
|---|---|---|
| **迟滞版 `_next_interval()` 在 `tick()` 已持锁时访问 `self.pending`**，后者再取同一把非可重入 `threading.Lock` | **Blender timer 永久死锁**（红队 EXT-02 复现） | 若将来实现迟滞，活动时间戳必须在**已持锁的临界区内**读写，或改用无锁的 `time.monotonic()` 快照；绝不要在持锁时调用会再次取锁的属性 |
| 改了 `scene_hash.digest()` 但没改 `scene_reader` 的**分块增量实现** | 两处摘要不一致，2 个测试失败（EXT-01） | 这两处是同一算法的两个实现，**任何 hash 变更必须同时改**。plan 里已加注释提醒 |
| 基于过时快照做批量字符串替换 | 补丁半数落空，plan 被改成不一致状态，被覆盖两次 | **改文件前先取 SHA-256 并在补丁脚本里做前置校验**（本次已这么做，见 §1 的两个 hash） |
| 把「`hashlib.openssl_sha256` 不存在」推断为「无 OpenSSL 后端」 | 给出了错误的技术归因（EXT-04） | 公开属性名缺失 ≠ 后端缺失，要看 `type(h).__module__` |

## 5. 决策状态

### D-1 合入的三项是否接受（✅ 2026-08-08 全部接受）

项目所有者已明确接受 `IDLE_INTERVAL=0.02`、`quantize` 直接定长格式化与 `path_policy.same_file()`；不再保留代码回退动作。电量影响仍是非阻断测量，`same_file()` 仍不是 Phase 1 的 TOCTOU 防线。

### D-2 提交策略（提交动作已由 `e5ac559` 完成）

以下混合工作区说明是提交前历史快照：当时你方 r11 修改与本文作者改动混在同一个 Plan 文件中，无法拆分。

本文作者未提交任何内容是原始快照；随后 r15/v8 证据链已由 `e5ac559` 冻结。r16 仍须先批准 proposed tuple，再按 ROADMAP 的 freeze commit → attestation commit 两步执行；本轮未执行该提交动作。

## 6. 证据位置

| 内容 | 位置 |
|---|---|
| 完整实测数据与方法 | [`docs/measurements/2026-08-07-macos-platform-optimization.md`](../measurements/2026-08-07-macos-platform-optimization.md) |
| 红队对第一版补丁的复审 | [`docs/audits/2026-08-07-post-freeze-platform-patch-redteam.md`](../audits/2026-08-07-post-freeze-platform-patch-redteam.md) |
| 融合 handoff 对抗审计 | [`docs/audits/2026-08-07-platform-optimization-handoff-adversarial-audit.md`](../audits/2026-08-07-platform-optimization-handoff-adversarial-audit.md) |
| r15/v8 最终 Plan 物化 provenance | [`docs/audits/evidence/2026-08-08-phase0-closeout-v8-provenance.json`](../audits/evidence/2026-08-08-phase0-closeout-v8-provenance.json) |
| r15/v8 Plan / artifact / vendor manifest | [`docs/audits/evidence/2026-08-07-phase0-plan-python-manifest-v8.tsv`](../audits/evidence/2026-08-07-phase0-plan-python-manifest-v8.tsv) · [`2026-08-07-phase0-artifact-manifest-v8.tsv`](../audits/evidence/2026-08-07-phase0-artifact-manifest-v8.tsv) · [`2026-08-07-phase0-vendor-manifest-v8.tsv`](../audits/evidence/2026-08-07-phase0-vendor-manifest-v8.tsv) |
| r15/v8 GUI 基础 smoke / 100k measurement | [`2026-08-07-phase0-gui-smoke-closeout-v8.json`](../audits/evidence/2026-08-07-phase0-gui-smoke-closeout-v8.json) · [`2026-08-07-phase0-gui-100k-measurement-v8.json`](../audits/evidence/2026-08-07-phase0-gui-100k-measurement-v8.json) |
| 官方 MCP v2 机器证据 | [`2026-08-08-official-blender-mcp-v2.json`](../audits/evidence/2026-08-08-official-blender-mcp-v2.json) |
| 测量脚本 | 隔离树内 `smoke/runner.py`，由最终 Plan 机械物化；复现命令与 SHA 记录在 v8 provenance |
| 本次 r15/v8 隔离验证树 | `/private/tmp/blenderdesign-v8-r15-audit.9595` 临时目录，不作为实施代码；精确路径、物化方法与命令记录在 v8 provenance |
