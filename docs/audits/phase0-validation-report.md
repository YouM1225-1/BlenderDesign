# Phase 0 验收核对报告

## 执行与历史锚点

- 获批 Plan：`docs/superpowers/plans/2026-07-23-phase0-readonly-channel.md`，SHA-256 `3f4bad1b3e5d0d5a6aa2febfc120f17cb5febbe48f9d38e41b8bf5ed33570fb5`。
- Task 18 正式 execution manifest：`docs/audits/evidence/phase0-l3-execution-manifest.json`，SHA-256 `463a2a6362d6251056c1efac0efbe1d65bec907a8e90db5e9c2d9a5941bac77a`；它的执行 HEAD 是 `c3dff7f00ec9da2cc8cd40a106257f0db59bebf8`，不是本报告之后的 post-acceptance HEAD。
- Task 18 获批 source：`b9651b509cf43b3b29f4eba6656dd335528e36d4`；历史 r18 attestation commit：`b8f7e1dca4affbab7c1f76468e0aee0e35194012`；旧 attestation 文件 SHA-256：`6e88adc2891a919bc0c972e78f61a269e704804052e043dc0f544ced91927058`。这些历史证据均保持原字节不变。
- Task 0–18 提交记录：T0 `425215d..3952aef`；T1 `3952aef..a71e6d3`；T2 `a71e6d3..46387b7`；T3 `46387b7..bd1457a`；T4 `c427cff..ceabb58`；T5 `ceabb58..17569ea`；T6 `bd1457a..c427cff`；T7 `17569ea..abdde66`；T8 `abdde66..e1786ab`；T9 `e1786ab..ed340b4`；T10 `ed340b4..4506ea3`；T11 `4506ea3..4c58227`；T12 `4c58227..5be0622`，并含 `4c80403`；T13 `5be0622..7aae399`；T14 `7aae399..010a9f0`；T15 `010a9f0..cb903ae`；T16 `cb903ae..69629b7`，并含 `0660b2d`；T17 `0660b2d..3f16a5d`；T18 Phase A `b8f7e1d..c3dff7f`，evidence commit `97a0eb4`。

以下五项是 Phase 0 补充关闭门，不是 URS §10.1 checkbox。

| 补充门 | 验证方式 | 状态 |
|---|---|---|
| G2 三代协议合同 | Task 17：Codex `2025-06-18`、legacy `2025-11-25`、SDK modern `2026-07-28` 三条独立 wire path 精确断言 | 通过 |
| G3 structure hash v1 边界 | Task 3 字段结构 + Task 18 真 Blender `hash_scope`（顶点不可见、transform 可见） | 通过 |
| 完整 stdio → adapter → UDS → Bridge | Task 17 `test_stdio_mcp_to_fake_bridge_roundtrip`；Task 18 NFR 再走真 GUI | 通过 |
| NFR-P1 正式门 | Task 18 `phase0-l3-execution-manifest.json` 为归因入口：clean Git/tree + 四文档 exact approved/source-blob tuple + 两提交 attestation 祖先链 + bounded tracked-source manifest/lock/Blender build；三工具各 20 个计时与 canonical result preimage，外部重做模型/语义、result+args digest、nearest-rank P95/max/代表结果且均 `<2000 ms`，并逐行复核 audit 40+20 行；sidecar 仅校验文件完整性 | 通过 |
| G5 官方兼容通道 | 模型面/宿主目录 26/26、摘要 transcript 24 个非-render `ok`、approval=0；项目所有者已接受严格截图序列与 render SIGABRT 风险。只关闭部署 Gate，不宣称稳定 | 通过 |

下表按 URS §10.1 稳定 ID 同序，恰好 20 行。

| ID | URS §10.1 验收项 | 验证方式 | 状态 |
|---|---|---|---|
| P0-01 | 三工具 outputSchema/structured result | Task 17 `test_tools_declare_closed_schemas`、`test_current_protocol_via_sdk_client`；Task 18 真 GUI NFR 的三模型验证 | 通过 |
| P0-02 | 非基线只读可用、写拒绝 | Task 9 `test_check_matrix`/`test_gate_write_matrix` + Task 15 `test_non_baseline_version_warning_attached`；按 spec 单栈 fixture，不冒充另装 4.5 | 通过 |
| P0-03 | SIGKILL 后 Server 存活、exact retryable `BRIDGE_UNAVAILABLE`、重启重连 | Task 16 FakeBridge 回归 + Task 18 public recovery supervisor/hidden worker 真 SIGKILL；kill 前/后/重启后三次 MCP identity 全等，并通过 public cancel/final-KILL、late poll、leader-exit/live-child、marker/stale/PID-PGID reuse、record 换入、pre-spawn reservation/stdlib bootstrap、read-only observer、bounded cache/overflow 与 inflight publication 直接反例 | 通过 |
| P0-04 | 完整会话 20 次无泄漏/残留 | Task 18 `cycles_leak_free`；以 `threading.enumerate()` 精确比较新增存活 `bcx-io` 线程并检查 `run/gui-*` | 通过 |
| P0-05 | ≥5 MiB 分帧无截断 | Task 1 `test_five_mib_roundtrip` + Task 16 `test_five_mib_payload_roundtrip` | 通过 |
| P0-06 | 私有 socket/token | Task 7 `test_start_creates_private_files`、`test_socket_is_0600_before_listen_and_session_publish` + Task 16 permission/token/auth-log 回归 | 通过 |
| P0-07 | stdout 仅 JSON-RPC | Task 17 cold-start、同块/延迟污染、半行/无换行/洪泛与 tail-drain 全组 | 通过 |
| P0-08 | 冷启动 `<5 s` | Task 17 `test_cold_start_and_stdout_purity`，计时含进程启动到 initialize | 通过 |
| P0-09 | cooperative continuation、总耗时/max tick | Task 4 大场景 wall-clock 回归 + Task 18 正式 100k `large_scene_metrics`/`max_tick_ms` | 通过 |
| P0-10 | yield 无 bpy wrapper；load_pre 后结构化失败 | Task 13 snapshot wrapper/generation 与 scene-info race；注册后的 load_pre 行为测试；Task 4 `SCENE_QUERY_FAILED` 映射 | 通过 |
| P0-11 | 2.2M collections 源端跳过 | Task 13 source-skip/item-cap + Task 16 `test_excluding_huge_collections_crops_before_frame_limit` | 通过 |
| P0-12 | queued+active 容量，64→65 拒绝 | Task 4 capacity/active continuation + Task 12 完整 SDK conversion admission/release 三请求反例 | 通过 |
| P0-13 | wake 合并与 1–10 停机顺序 | Task 7 wake storm/ordered hooks/final join + Task 16 N 连接回收与单写者回归 | 通过 |
| P0-14 | file/parent/cleanup 换入不越界、不误删 | Task 7 socket/session replacement + Task 11 opened-fd、parent swap、dead cleanup、socket identity replacement 回归 | 通过 |
| P0-15 | exact wire types、SDK coercion、结构化审计 | Task 2 malformed exact-type组 + Task 10 malformed response + Task 12 coercion/success/unknown/output-validation audit 组 | 通过 |
| P0-16 | 线程/多 Host JSONL 完整 | Task 9 `test_concurrent_records_remain_complete_jsonl_lines` 的线程与 spawn 进程 split-write | 通过 |
| P0-17 | runtime/run/logs 类型、uid、mode、祖先不改 | Task 7/9/11 wide/symlink 与新增 foreign-uid、真实 device FD、`test_start_preserves_permissions_above_runtime_root` 直接 fixture | 通过 |
| P0-18 | sun_path 发布前/后崩溃恢复及换入保留 | Task 11 pre/post publication/fallback identity 回归 + Task 7 stop replacement | 通过 |
| P0-19 | stale deadline、后续重试、instance ID | Task 11 expired/recheck/evidence-preservation + `test_expired_cleanup_is_retried_by_a_later_scan` + instance-id mismatch | 通过 |
| P0-20 | 首次并发初始化；FIFO/device/symlink 不阻塞/不写 | Task 9 concurrent directory/file creation、FIFO 明确 `<0.5 s`、真实 `/dev/null` FD 换入与 symlink preservation | 通过 |

全部 5 个补充门与 20 个稳定 ID 已通过。Plan 的 93 个 checkbox 保持 93 open / 0 checked；本报告是执行状态副本，不改写获批 Plan。
