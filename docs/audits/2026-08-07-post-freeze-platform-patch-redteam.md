# Phase 0 冻结后平台优化补丁·对抗性复审

> **SUPERSEDED（2026-08-08）**：本文件是 r12/v5 平台补丁历史记录；当前裁决见 [closeout v3](2026-08-07-closeout-v3.md) 与 [r15/v8 融合审计](2026-08-07-platform-optimization-handoff-adversarial-audit.md)。其中旧 Plan SHA、queue 数字和 260-test 门禁不得作为当前状态。

> 日期：2026-08-07  
> 审计边界：只读审计、隔离树复现与文档回滚；**未执行 Phase 0 Plan，未暂存，未提交**。  
> 当前裁决以 [2026-08-07-closeout-v2.md](2026-08-07-closeout-v2.md) 及本报告为准。

## 结论

最终保留已冻结的 SHA-256 / `round(v, 6)` / queue `busy=0.01 s, idle=0.1 s` 合同。审计期间出现的 macOS 平台优化补丁（临时 Plan SHA `906f804b…`）未纳入交付基线；其代码、规范和平台承诺均已移除。当前 Plan 与冻结隔离树重新逐字节一致。

## 新补丁的可复现发现

| ID | 级别 | 复现与影响 | 裁决 |
|---|---|---|---|
| EXT-01 | **P0** | `scene_hash.digest()` 改成 `blake2b:`，但 `bridge/blender/scene_reader.py` 仍生成 `sha256:`；真实 `test_scene_reader.py` 的 3 个用例中 2 个失败（snapshot hash 与 helper digest 不等）。URS/spec 也分别仍写 SHA-256，属于运行时、规范和证据三方不一致。 | 回滚 helper、测试和 L3 前缀到 SHA-256；若未来换算法，必须一次性更新 reader、schema、URS/spec、fixture、manifest 并重跑真 Blender。 |
| EXT-02 | **P0** | queue 迟滞版在 `tick()` 持有非可重入 `threading.Lock` 时调用 `_next_interval()`；该函数访问 `self.pending` 并再次取得同一把锁。队列排空后真实回归在 2 s 内超时，Blender timer 会被永久卡住。 | 回滚 `ACTIVITY_HOLD`/`_next_interval()`，保留规范基线 `0.01/0.1`。 |
| EXT-03 | **P1（证据）** | 临时补丁只改了 7 个 Python 文件块，导致 Plan 与冻结树仅 39/46 一致；已存 Python manifest 仍是旧 hash，无法从当前 Plan 自足重建。`same_file()` 还只是未被 Phase 0 调用的路径查询辅助，不能替代 Phase 1 的 fd-based/`O_NOFOLLOW` 写入边界。 | 移除未获批准的 helper/fixture 和平台段；保留 FR-21 的 TOCTOU 边界说明，不宣称 Phase 0 已交付。 |
| EXT-04 | **P2** | “`hashlib.openssl_sha256` 不存在 ⇒ 无 OpenSSL 后端”的推断错误。Blender 5.2.0 内置 Python 3.13.13 中 `hashlib.sha256` 来自 `_hashlib`，OpenSSL 3.5.6；公开属性名缺失不等于后端缺失。BLAKE2b 在本机确实更快（约 1.4 GB/s vs SHA-256 约 0.12 GB/s），但这只是实现优化证据，不是已批准的协议变更。 | 删除错误归因；将算法优化留作未来独立 ADR/跨版本 benchmark。 |
| EXT-05 | **P2** | 直接 f-string 与 `round`+f-string 在大规模边界/随机样本中未发现输出差异，方向上约 2× 更快，但补丁写入了不可复算的绝对耗时；迟滞 `.05/1.5 s` 的收益依赖请求到达分布，且增加空闲唤醒，没有 NFR/CPU 预算依据。 | 不写入当前规范；未来以 workload、CPU/电量和跨版本回归为前置条件。 |
| EXT-06 | **P2** | URS 临时 v1.9 追加了与头部 v1.8 不一致的变更记录，重复了 R-09/R-10，并声称 `same_file` 已交付；spec 的 hash 公式和 BLAKE2b 段互相矛盾。 | 删除 v1.9 及重复/过时平台承诺，恢复 v1.8 文档闭环。 |

## 复原后的闭环

- Plan SHA-256：`a05bf3dd2456180052e22375917cc4ef8e33a3451d505a4e1090884b660be7bf`
- URS SHA-256：`80e4d1dfb6fb5f6b9953b65ed419daf51e02db08ad0f4b78b80488ba2e769e79`
- spec SHA-256：`a37d362f2b181710ae7322e508e09ee7643b048aa0be594f589bc0260c13d3ef`
- Plan Python 块：46/46 与冻结树逐字节一致；非 Python literal 3/3；vendored manifest 3/3
- Plan checkbox：93 个，已勾选 0 个
- 冻结隔离门禁：260 passed（unit 233 + contract 27）、adapter 33、ruff clean、mypy strict 22 文件 0 错误、vendor/nested import/lock 全绿
- Blender L3 v5：`BG_CHECK_OK`、`SMOKE_OK`，五项判据为 true，`errors=[]`
- 官方 Blender MCP：宿主 effective config 与注册目录 26/26；当前任务启动快照仍为 10 项，不能混写
- Git：`main`、HEAD `578f49e…` 未变，无 staged、无新 commit

这些门禁证明的是冻结 Plan 的组合性与反例关闭，不是 Phase 0 已实施。继续执行必须先由用户审批，再按 Task 重新生成独立证据。
