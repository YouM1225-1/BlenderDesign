# Official Blender MCP Modeling Validation

Status: baseline running

## Scope and safety boundary

No user `.blend` was opened or saved. Runtime binaries are untracked. All runtime paths in this report use `$RUN_ROOT` rather than an account name. This active audit is the cumulative Task 1–4 plan output, not historical frozen-plan evidence; it records execution facts and any approved deviations without changing the frozen plan bytes.

## Environment and catalog

- Branch: `codex/official-blender-mcp-install`
- Official Blender MCP source pin: `4309a39646e644261624bfcd2bca669b343b7621`
- Initial GUI listener: PID `5949`, the only `Blender` process on `127.0.0.1:9876`; this process was later terminated during mandatory failure recovery.
- Recovery GUI listeners: PID `79677` replaced the initial process after `MODEL-RUN-01`, then was terminated after `MODEL-RUN-02`; PID `89410` held the first completed model and was deliberately terminated without saving for the review-requested controlled timing replay; current PID `28354` is the sole listener and contains the clean-replayed completed model.
- Each GUI baseline/recovery preflight proved an unsaved, clean factory scene with exact direct objects `Camera`, `Cube`, and `Light`, Object mode, no target data-block, and a `VIEW_3D` area before any replay write.

## Stage timings

- Terminal immutable-state preflight: 200 ms (command wall time).
- MCP preflight calls: 784.2 ms path info, 22.0 ms object summary, and 391.1 ms window summary (1,197.3 ms total).
- Fixture process wall time: 1,305.094 ms.
- Blender provisioner `elapsed_ms`: 98.274 ms.
- Waived non-writing postcondition-verification timing-wrapper wall time: 54.995 ms; the subsequently rerun safe verification command exited `0`.

Task 2 phase attempts and mandatory recovery replays are recorded separately:

| Phase/case | UTC start → end | MCP tool wall | Blender internal | Result |
|---|---|---:|---:|---|
| Phase 1 attempt 1 | 2026-08-09 23:59:55.086811Z → 2026-08-10 00:00:44.741704Z | 1,105.4 ms | unavailable | failed after partial Phase 1 state; `MODEL-RUN-01` |
| Phase 1 replay after first clean restart | 00:04:26.887705Z → 00:05:09.378596Z | 1,237.3 ms | 16.953 ms | passed, then discarded by the later mandatory clean restart |
| Phase 2 attempt 1 | 00:05:23.524447Z → 00:06:43.435361Z | 1,176.8 ms | unavailable | failed in a precondition before any Phase 2 write; `MODEL-RUN-02` |
| Phase 1 second full replay | 00:10:50.519445Z → 00:11:31.318237Z | 1,087.4 ms | 9.573 ms | passed; final GUI state |
| Phase 2 corrected attempt | 00:11:41.155737Z → 00:12:37.685293Z | 1,113.1 ms | 56.421 ms | passed; final GUI state |
| Phase 3 corrected attempt | 00:12:53.227348Z → 00:13:42.827648Z | 1,229.9 ms | 23.171 ms | passed on first attempt; final GUI state |

- The three final successful phase calls used 3,430.4 ms of MCP tool wall time and 89.165 ms of Blender-internal payload time.
- The final strong assertion plus four read-only acceptance tools used 4,241.8 ms of MCP tool wall time.
- Across Task 2, the 20 recorded MCP invocations used 15,512.2 ms of tool wall time. The two failed calls used 2,282.2 ms; the two mandatory process-restart brackets used another 4,558.439 ms outside MCP tool time.
- The original run captured UTC/system-monotonic brackets around individual calls, retry counts, raw symptoms, first hypotheses and each individual tool wall time in the ignored raw report. It did **not** capture a comparable system-monotonic Task-start marker; its 1,810,040.383 ms total is therefore a UTC-only interval and is not reconstructed from incompatible clocks. Bracket-minus-tool residual is “unattributed orchestration time,” not “LLM time.” No original Task 2 call crossed the design's potential-abnormal threshold; final classification remains a Task 4 responsibility.

Review remediation added a separate clean controlled replay without rewriting the original record. The first required operation emitted UTC `2026-08-10T00:33:11.259309Z` and Python `time.monotonic_ns()=9688291`; because this environment gives short-lived Python processes separate monotonic origins, that marker is retained but not compared. Before any Blender action or payload read, one long-lived Python timer emitted the canonical replay start and all later canonical markers.

| Controlled replay stage | UTC wall | Same-process monotonic wall | UTC−mono | MCP tool wall | Blender internal | Unattributed orchestration | Outcome |
|---|---:|---:|---:|---:|---:|---:|---|
| Clean restart + full preflight | 43,636.538 ms | 43,636.418 ms | 0.120 ms | 1,117.2 ms | unavailable | 42,519.218 ms | PID `89410` gone; PID `28354` sole listener; clean/default/target-absence/hash checks pass |
| Phase 1, including payload read | 47,231.349 ms | 47,231.196 ms | 0.153 ms | 1,816.4 ms | 11.734 ms | 45,414.796 ms | pass, no retry |
| Phase 2, including payload read | 48,347.732 ms | 48,347.563 ms | 0.169 ms | 1,945.2 ms | 53.365 ms | 46,402.363 ms | pass, no retry |
| Phase 3 + strong assertion, including both payload reads | 82,118.693 ms | 82,118.429 ms | 0.264 ms | 2,998.2 ms | 13.471 ms | 79,120.229 ms | both calls pass, no retry |
| Path-info acceptance | 8,226.414 ms | 8,226.391 ms | 0.023 ms | 594.3 ms | unavailable | 7,632.091 ms | unsaved; dirty observed false |
| Objects acceptance | 10,491.773 ms | 10,491.755 ms | 0.018 ms | 632.8 ms | unavailable | 9,858.955 ms | exact collection/parents/selection pass |
| Shade-detail acceptance | 10,671.455 ms | 10,671.421 ms | 0.034 ms | 277.4 ms | unavailable | 10,394.021 ms | exact type/data/material/parent/child pass |
| Datablocks acceptance | 8,046.435 ms | 8,046.423 ms | 0.012 ms | 938.8 ms | unavailable | 7,107.623 ms | counts/library/engine pass |
| Canonical replay Task | 431,244.808 ms | 431,243.301 ms | 1.507 ms | 10,320.3 ms | 78.570 ms for Phases 1–3 | 420,923.001 ms | full replay and acceptance pass |

The canonical replay interval is UTC `2026-08-10T00:33:44.819973Z` / monotonic `13975958 ns` through UTC `2026-08-10T00:40:56.064781Z` / monotonic `431257276916 ns`. The first required standalone marker through Task end is a separate UTC-only interval of 464,805.472 ms. No dual-clock duration was reconstructed, and all UTC/monotonic stage differences are below 1 ms except the full-Task accumulated 1.507 ms. “Unattributed orchestration” includes required payload reading/review, dispatch, result handling and gaps; it is not “LLM time.” No replay MCP call crossed its abnormal-time threshold.

## 26-tool results

The complete 26-row matrix is a Task 3 deliverable and is not claimed here. Task 2 gave determinate outcomes for five unique tools: `execute_blender_code`, `get_blendfile_summary_path_info`, `get_objects_summary`, `get_object_detail_summary`, and `get_blendfile_summary_datablocks`. Including Task 1's window JSON preflight, the run has exercised six unique catalog tools so far; screenshots, navigation, documentation, CLI and render coverage remain pending.

## Modeling contract

`$RUN_ROOT` is an owned non-symlink `0700` directory with `assets` and `renders` children. `library_source.blend` and `lamp_fixture.blend` are ordinary non-empty files, and `$RUN_ROOT/assets/known-missing.png` remains absent.

The final direct Scene object set and `MCP_Lamp_Isolated` object set both equal these 14 names; the linked source contributes one additional non-direct `Library_Accent` object datablock, so the summary reports 15 total objects.

| Object | Type/data | Material | Parent / role |
|---|---|---|---|
| `Lamp_Ground` | MESH / `Lamp_Ground_Mesh` | `Mat_Ground` | none; shadow ground |
| `Lamp_Base` | MESH / `Lamp_Base_Mesh` | `Mat_Base` | none; beveled base |
| `Lamp_Stem` | MESH / `Lamp_Stem_Mesh` | `Mat_Metal` | `Lamp_Base` |
| `Lamp_Joint_Lower` | MESH / `Lamp_Joint_Lower_Mesh` | `Mat_Metal` | `Lamp_Stem` |
| `Lamp_Arm_Lower` | MESH / `Lamp_Arm_Lower_Mesh` | `Mat_Metal` | `Lamp_Joint_Lower` |
| `Lamp_Joint_Upper` | MESH / `Lamp_Joint_Upper_Mesh` | `Mat_Metal` | `Lamp_Arm_Lower` |
| `Lamp_Arm_Upper` | MESH / `Lamp_Arm_Upper_Mesh` | `Mat_Metal` | `Lamp_Joint_Upper` |
| `Lamp_Shade` | MESH / `Lamp_Shade_Mesh` | `Mat_Shade` | `Lamp_Arm_Upper`; beveled; unique active/selected object |
| `Lamp_Bulb` | MESH / `Lamp_Bulb_Mesh` | `Mat_Bulb` | `Lamp_Shade` |
| `Lamp_Cable` | CURVE / `Lamp_Cable_Curve` | `Mat_Metal` | none |
| `Lamp_Camera` | CAMERA / `Lamp_Camera_Data` | none | none; active scene camera |
| `Lamp_Key` | AREA LIGHT / `Lamp_Key` | none | none |
| `Lamp_Fill` | AREA LIGHT / `Lamp_Fill` | none | none |
| `Lamp_LinkedProp` | EMPTY collection instance | none | none; instances linked `Lamp_LinkedAsset` |

| Material set | Assigned contract |
|---|---|
| `Mat_Base` | `Lamp_Base` |
| `Mat_Metal` | stem, joints, arms and cable |
| `Mat_Shade` | `Lamp_Shade` |
| `Mat_Bulb` | `Lamp_Bulb`, with emission strength `4.0` |
| `Mat_Ground` | `Lamp_Ground` |

The complete lamp parent chain is `Lamp_Base` → `Lamp_Stem` → `Lamp_Joint_Lower` → `Lamp_Arm_Lower` → `Lamp_Joint_Upper` → `Lamp_Arm_Upper` → `Lamp_Shade` → `Lamp_Bulb`; all other declared objects have no parent. The exact five-name `Mat_*` set matched, the active camera and lights matched, the linked library resolved to `$RUN_ROOT/library_source.blend`, the missing image resolved to the deliberately absent `$RUN_ROOT/assets/known-missing.png`, and no checked datablock had an unexpected `.001` suffix.

Lamp-body world bounds, excluding `Lamp_Ground` and the linked collection instance, are `min=[-2.25, -2.25, 0.02]` and `max=[5.2461, 2.25, 7.45]`; every maximum is greater than its minimum. Phase 3 selected and read back Blender 5.2's `BLENDER_EEVEE` before any Phase 3 object/data-block creation. Resolution is 640×640 at 75%, but no render result is claimed in Task 2.

## Errors and recoveries

The frozen Task 1 Step 4 plan prescribed `for path in ...`. In `zsh`, that special parameter is tied to `PATH`, so the original post-provision verification failed after Blender provisioning exited successfully with `zsh:16: command not found: stat`, `zsh:16: command not found: id`, and `zsh:17: command not found: stat`. This first failure remains part of the record.

The plan bytes are frozen. Based on the user's autonomous-completion authorization, the controller formally records one execution deviation/waiver: after the failed postcondition verification, it reran only those non-writing postconditions with `fixture_path`. That safe verification exited `0` in `zsh`, printed the same SHA-256 values for both fixtures, and confirmed the missing image was absent. The successful provisioner was not rerun because that would overwrite fixtures.

- `MODEL-RUN-01`: Phase 1 attempt 1 failed after partial writes because the payload looked up the Principled shader by the localized display name `Principled BSDF`; the Chinese UI returned no such name and the assertion failed. The first hypothesis was recorded before recovery. The failed GUI (PID `5949`) was terminated without saving, a new sole listener (PID `79677`) passed the full clean factory/target-absence/fixture-hash preflight, and Phase 1 was replayed with exactly-one `node.type == "BSDF_PRINCIPLED"`. The same localization audit proactively corrected the Phase 3 World node lookup to exactly-one `node.type == "BACKGROUND"`.
- `MODEL-RUN-02`: Phase 2 attempt 1 failed before its first write because the payload assumed `bpy.data.is_dirty is True`. The successful programmatic Phase 1 result had actually observed `false`. PID `79677` was terminated without saving; PID `89410` passed the same full clean preflight; Phase 1 was replayed; and Phase 2 used exact path/mode/run-root/object/material/data/parent invariants while recording dirty as an observation. The later controlled replay on current PID `28354` independently reproduced the exact structure and the same observed `is_dirty=false`. The frozen Step 4 prediction was therefore an invalid plan assumption, not a structural model failure; the flag was not forced.
- `MODEL-PLAN-01` prevented an otherwise Critical Phase 3 failure: the frozen payload's `BLENDER_EEVEE_NEXT` value was never attempted. Before any Phase 3 datablock creation, the corrected payload inspected the engine enum, found `BLENDER_EEVEE`, assigned it, read it back and asserted equality, so no partial Phase 3 state was created by the invalid value.
- `MODEL-PLAN-02` required complete prior/absence assertions and destroy-and-full-replay recovery after either mutating-phase failure.
- `MODEL-PLAN-03` limited writes to the verified factory Scene/World settings and exact isolated `Lamp_*`, `Mat_*`, `MCP_Lamp_Isolated`, and `BCX_RUN_ROOT` data.
- `MODEL-PLAN-04` required the separate read-only exact-set, no-`.001`, linked/missing, parent and ground-excluded bounds assertion.
- `MODEL-PLAN-05` required UTC/system-monotonic brackets plus separate tool/internal/retry/symptom/first-hypothesis evidence. The original run satisfied the per-call fields but missed a comparable Task-start monotonic marker, so it did not fully satisfy this control; see `MODEL-RUN-04`. The frozen Plan bytes were not edited.
- `MODEL-RUN-03`: the first pre-commit audit validator rejected the shorthand “`MODEL-PLAN-02` through `MODEL-PLAN-05`” because stable machine-readable evidence requires every issue ID as a literal marker. The audit was expanded to four explicit rows before commit; no Blender or fixture state changed.
- `MODEL-RUN-04`: the original Task-start system-monotonic value was not captured. The printed Python `0.008563500` value was process-local and was correctly retained only as a terminal-command elapsed reading; the original total wall can be computed from UTC only. A review-requested clean controlled replay uses one long-lived Python timing process for every canonical `datetime.now(timezone.utc)` and `time.monotonic_ns()` marker. The first standalone replay-start probe is also retained but not compared because this environment gives each short-lived Python process a separate monotonic origin; no historical value is synthesized.

The controlled replay closes the actionable part of `MODEL-RUN-04`: canonical Task, Phase 1, Phase 2, combined Phase 3/assertion and each acceptance now have comparable same-process monotonic endpoints plus UTC endpoints, tool wall, internal time where available and unattributed orchestration. It does not retroactively make the original run dual-clock complete.

## Root-cause analysis

The Task 1 plan defect was shell-variable shadowing in the verification harness, not a Blender or fixture-generation failure. `path` is a special `zsh` parameter synchronized with `PATH`; assigning it in the loop removed command-search paths before `stat`, `id`, and subsequent commands ran.

Task 2 adds two preliminary root causes for final Task 4 classification: display-name lookup of built-in nodes is locale-dependent and must use stable RNA types, while `bpy.data.is_dirty` does not express the exact structural state of this programmatic unsaved workflow and must not be used as a post-mutation identity assertion. Both are deterministic plan assumptions rather than abnormal tool latency; neither changed a user file.

`MODEL-RUN-03` is a reporting-harness mistake: human-readable range shorthand omitted three literal issue markers required by the focused validator. The validator caught it before staging; explicit markers are the minimal recovery.

`MODEL-RUN-04` is a timing-capture gap and overstatement: the original Task lacked one comparable monotonic endpoint, so its total cannot be called dual-clock verified and its `MODEL-PLAN-05` compliance was incomplete. The corrective evidence must come from a new clean replay, not reconstructed history.

## Remediation decision

The Task 1 plan remains byte-for-byte frozen. The controller's authorized execution deviation/waiver is limited to the failed postcondition verification: use `fixture_path` for the non-writing recovery checks, retain the original failure as evidence, and do not rerun the successful provisioner because it would overwrite fixtures. The provisioner and fixtures remain unchanged.

Task 2 establishes two evidence-backed candidates for the later remediation decision: stable node-type guidance for localized Blender sessions and explicit guidance that dirty state is observational, while exact structural/path sentinels determine model identity. Task 4 will apply the frozen file-justification rule; this Task does not create a manual, helper or product-code fix.

The immediate Task 2 review remediation for `MODEL-RUN-04` is evidence-only: perform a clean full modeling replay under one persistent monotonic clock, retain both original and replay records, and avoid changing product code or frozen documents.

## Adversarial audit and retest

The waiver's non-writing postcondition verification was rerun in `zsh` and exited `0`; a separately timed equivalent invocation completed in 54.995 ms. Both fixture files remain regular, non-symlink, owned, non-empty files with their original recorded SHA-256 values; the intentionally absent image file is still absent. The successful provisioner was not rerun because it would overwrite existing fixtures, outside this waiver's no-fixture-write scope.

After Phase 3, one independent read-only code assertion compared exact direct Scene and isolated-collection object sets, exact `Mat_*` set, all 14 parent entries, camera, lights, linked library, controlled missing image, selection, engine and relevant data names; it rejected any `.001` and proved non-degenerate ground-excluded lamp-body bounds. The four mandated read-only tools then independently confirmed the unsaved path, exact collection tree/parents/selection, `Lamp_Shade` detail, and summary counts of 15 objects, 7 total materials, 2 cameras, 3 lights and one library. The controlled replay repeated this complete sequence from a newly verified factory scene with zero retries and identical structural results. The counts exceed contract minima because unlinked factory datablocks and the linked source remain data-blocks; exact contract sets were verified separately. Fixture SHA-256 values stayed unchanged. No GUI `.blend` was saved.

## Final verdict

Baseline preflight/provisioning and Task 2 structural modeling acceptance passed. The two original Task 2 failures and mandatory clean replays remain explicit; the timing-capture gap is not rewritten. The separate controlled replay passed every phase and acceptance without retry under one comparable clock, and current PID `28354` contains the exact unsaved isolated scene. The official dirty flag's observed `false` value contradicts the frozen Step 4 prediction but not the exact in-memory structure and is retained as `MODEL-RUN-02`. Full 26-tool coverage, screenshots and renders have not yet run and are not claimed.
