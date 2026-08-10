# Official Blender MCP Modeling Validation

Status: tool coverage complete; root-cause analysis pending

## Scope and safety boundary

No user `.blend` was opened or saved. Runtime binaries are untracked. All runtime paths in this report use `$RUN_ROOT` rather than an account name. This active audit is the cumulative Task 1–4 plan output, not historical frozen-plan evidence; it records execution facts and any approved deviations without changing the frozen plan bytes.

## Environment and catalog

- Branch: `codex/official-blender-mcp-install`
- Official Blender MCP source pin: `4309a39646e644261624bfcd2bca669b343b7621`
- Initial GUI listener: PID `5949`, the only `Blender` process on `127.0.0.1:9876`; this process was later terminated during mandatory failure recovery.
- Recovery GUI listeners: PID `79677` replaced the initial process after `MODEL-RUN-01`, then was terminated after `MODEL-RUN-02`; PID `89410` held the first completed model and was deliberately terminated without saving for the review-requested controlled timing replay; current PID `28354` is the sole listener and contains the clean-replayed completed model.
- Each GUI baseline/recovery preflight proved an unsaved, clean factory scene with exact direct objects `Camera`, `Cube`, and `Light`, Object mode, no target data-block, and a `VIEW_3D` area before any replay write.
- Task 3's literal App Server verifier returned exactly 26 unique live `blender` tools. Pinned-source AST, live names and effective configured `enabled_tools` were set-for-set equal; the source pin and checkout remained unchanged and clean.
- Task 3 called every live name afresh. The sole GUI remained PID `28354`; the two original fixture hashes stayed unchanged. One additional disposable derived fixture under `$RUN_ROOT` preserved the missing image with a fake user after the original fixture exposed `MODEL-RUN-06`.

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

Task 3 used one long-lived timing process from its first operation. Its canonical execution interval was UTC `2026-08-10T00:50:22.969020Z` / monotonic `10706458 ns` through UTC `2026-08-10T01:19:30.042727Z` / monotonic `1747069296041 ns`: UTC wall `1,747,073.707 ms`, same-process monotonic wall `1,747,058.590 ms`, and delta `15.117 ms`.

- The literal App Server catalog verifier used `3,278.041 ms` command wall outside MCP tool time.
- Task 3 made 33 official MCP invocations across 26 fresh unique tools. MCP-reported wall summed to `33,632.4 ms`; the residual `1,713,426.190 ms` is unattributed orchestration time, not inferred LLM time.
- No safe summary/docs/navigation call exceeded `5,000 ms`; no individual screenshot call exceeded `10,000 ms`; thumbnail was `2,475.6 ms` versus the `30,000 ms` threshold; viewport was `1,151.6 ms` versus the `60,000 ms` threshold. No threshold-only rerun was needed.
- The 2 MB area screenshot failed in `2,916.8 ms`; its single reduced-size recovery succeeded in `3,113.0 ms`. The original CLI missing-fixture calls and their single authorized derived-fixture recoveries are included in the MCP total. Final abnormal-time classification remains a Task 4 deliverable.

## 26-tool results

Wall ms is the sum of all fresh Task 3 invocations for that unique tool, including a recovery or required postcondition call where applicable.

| Ordinal | Tool | Outcome | Wall ms | Observed shape | Retry count | Issue ID |
|---:|---|---|---:|---|---:|---|
| 1 | `execute_blender_code` | pass | 2429.1 | exact model contract plus render tempdir/engine/sample postconditions | 0 | `MODEL-PLAN-08`; `MODEL-PLAN-09` |
| 2 | `execute_blender_code_for_cli` | pass_with_recovery | 1866.7 | original missing-image assertion failed; derived fixture returned image/fake-user/object/library contract | 1 | `MODEL-RUN-06`; `MODEL-RUN-11` |
| 3 | `get_blendfile_summary_datablocks` | pass | 992.4 | nested counts, EEVEE, scene and localized workspace | 0 | none |
| 4 | `get_blendfile_summary_datablocks_for_cli` | pass | 662.9 | fixture counts with three objects and one library; no persisted image | 0 | `MODEL-RUN-06` |
| 5 | `get_blendfile_summary_missing_files` | pass | 383.3 | exactly one controlled GUI missing image | 0 | none |
| 6 | `get_blendfile_summary_missing_files_for_cli` | pass_with_recovery | 2021.0 | original fixture empty; derived fixture exactly one controlled missing image | 1 | `MODEL-RUN-06`; `MODEL-RUN-11` |
| 7 | `get_blendfile_summary_of_linked_libraries` | pass | 54.4 | one exact direct library and zero indirect | 0 | none |
| 8 | `get_blendfile_summary_of_linked_libraries_for_cli` | pass | 597.7 | one direct relative library and zero indirect | 0 | none |
| 9 | `get_blendfile_summary_path_info` | pass | 859.7 | empty filepath, unsaved before and after renders, dirty observed false | 0 | `MODEL-RUN-02` |
| 10 | `get_blendfile_summary_path_info_for_cli` | pass | 807.7 | exact saved clean fixture path, size and no backups | 0 | none |
| 11 | `get_blendfile_summary_usage_guess` | pass | 2968.0 | 11 integer score/certainty pairs in range | 0 | none |
| 12 | `get_blendfile_summary_usage_guess_for_cli` | pass | 1094.0 | 11 integer score/certainty pairs in range | 0 | none |
| 13 | `get_object_detail_summary` | pass | 989.8 | exact Shade type/data/material/modifier/parent/child/collection | 0 | none |
| 14 | `get_objects_summary` | pass | 771.3 | exact 14-object isolated tree, parents, camera and Shade selection | 0 | none |
| 15 | `get_python_api_docs` | pass | 70.5 | exact lookup found; large class summarized to definitions | 0 | none |
| 16 | `get_screenshot_of_area_as_image` | pass_with_recovery | 6029.8 | frozen 2 MB case truncated; 48 KB recovery returned PNG 350×192 | 1 | `MODEL-RUN-08` |
| 17 | `get_screenshot_of_window_as_image` | pass_with_deviation | 2060.5 | preventive 48 KB case returned PNG 320×164 | 0 | `MODEL-RUN-08` |
| 18 | `get_screenshot_of_window_as_json` | pass | 2787.8 | pre/post navigation layout, VIEW_3D and active Shade JSON | 0 | none |
| 19 | `jump_to_tab_by_name` | pass | 225.6 | nested status and exact localized workspace `布局` | 0 | none |
| 20 | `jump_to_tab_by_space_type` | pass | 477.8 | existing `布局` VIEW_3D selected without creation | 0 | none |
| 21 | `jump_to_view3d_object_by_name` | pass | 748.2 | exact Shade MESH and location | 0 | none |
| 22 | `jump_to_view3d_object_data_by_name` | pass | 555.6 | exact Shade object/data/type/location | 0 | none |
| 23 | `render_thumbnail_to_path` | pass | 2475.6 | confined owned ordinary PNG, copied and hash-verified | 0 | `MODEL-RUN-09`; `MODEL-PLAN-09` |
| 24 | `render_viewport_to_path` | pass | 1151.6 | confined owned ordinary PNG, copied and hash-verified | 0 | `MODEL-RUN-09` |
| 25 | `search_api_docs` | pass | 264.9 | corrected query returned path/text/breadcrumb/score | 0 | `MODEL-PLAN-06` |
| 26 | `search_manual_docs` | pass | 286.5 | two hits with path/text/breadcrumb/score | 0 | none |

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

Lamp-body world bounds, excluding `Lamp_Ground` and the linked collection instance, are `min=[-2.25, -2.25, 0.02]` and `max=[5.2461, 2.25, 7.45]`; every maximum is greater than its minimum. Phase 3 selected and read back Blender 5.2's `BLENDER_EEVEE` before any Phase 3 object/data-block creation. Resolution is 640×640 at 75%.

Task 3 validated both render copies as owned ordinary non-symlink nonempty PNGs with exact magic and source/copy hash equality:

| Artifact | Bytes | SHA-256 | Visual result |
|---|---:|---|---|
| `$RUN_ROOT/renders/thumbnail.png` | 121586 | `7a4799be69540a5faa24080d6d24cdfd23050ef692651d5be92881aae66f4bcb` | complete lamp, ground/shadow and linked prop visible |
| `$RUN_ROOT/renders/viewport.png` | 260917 | `1bde67e12dbb50fb7dc1a94a69b484dbcfa410e60164b484a475b2c5fdcd8e14` | complete lamp, material separation, lit bulb and no user content |

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

- `MODEL-RUN-05`: the first Task 3 catalog set-equality harness used macOS Python 3.9.6 and failed on missing `tomllib`. The first hypothesis identified the unpinned interpreter; absolute uv-managed Python 3.13 under `set -euo pipefail` passed live/AST/config equality without state change.
- `MODEL-PLAN-06`: source-only reproduction proved the frozen API query returns zero hits and the corrected `bpy.ops.mesh primitive_cylinder_add` query returns the exact operator hit. The known-zero query was not sent live.
- `MODEL-RUN-07`: that source-only harness first omitted editable project dependencies (`yaml` missing), then misread the implementation's `hits` key as `results`. Both raw symptoms and first hypotheses were retained; the effective editable environment and source-verified response shape closed the reproduction without source writes.
- `MODEL-PLAN-07`: the literal App Server catalog snapshot, pinned AST and configured set were exactly equal at 26 unique names. The strict table validator, not prose markers alone, is the coverage proof.
- `MODEL-RUN-06`: the original CLI fixture did not persist its zero-user missing-image datablock, so exact CLI code failed and CLI missing summary was empty. The original fixture was not changed. A single authorized CLI recovery created only `$RUN_ROOT/lamp_fixture_persisted_missing.blend` with `use_fake_user=true`; the derived missing summary returned the exact controlled path, and both original hashes stayed unchanged.
- `MODEL-PLAN-08`: Blender's canonical tempdir and scratch parent chain were verified with realpath/lstat ownership checks; unique targets were absent before each render and returned aliases canonicalized back to the same parent.
- `MODEL-RUN-09`: the final `blender_mcp` scratch parent was absent, while the upstream render tools do not create it. This was recorded before creating only that owned mode-`0700` directory. No user or repository path was used.
- `MODEL-PLAN-09`: Blender 5.2 reported `BLENDER_EEVEE` with render samples `64`. Pinned thumbnail code lowers Eevee samples only for obsolete `BLENDER_EEVEE_NEXT`; thumbnail still passed in `2,475.6 ms`, and source was not patched.
- `MODEL-RUN-08`: the exact 2 MB area screenshot returned truncated JSON. Pinned add-on source accepts nonblocking clients, performs one `sendall`, swallows `OSError`, and closes; a 48 KB single recovery returned PNG. Window screenshot used the same preventive cap and passed; the uncalled frozen 3 MB case is not mislabeled as a failure.
- `MODEL-PLAN-10`: every official call has immediate same-process UTC/monotonic markers, tool wall, shape, retry and issue, and no threshold-only rerun was required. First symptoms are retained. First-hypothesis capture is complete for the other recorded failures, but not for `MODEL-RUN-06`; this part of the control remains unmet rather than being reconstructed.
- `MODEL-RUN-11`: evidence-capture gap for `MODEL-RUN-06`. Its two original symptoms and recovery evidence are persisted, but the verbatim first-hypothesis text is missing. Contemporaneous messages mentioned only the hypothesis direction; the original wording is no longer recoverable and is not supplied retrospectively. Task 4 must classify this gap and decide its durable prevention.
- `MODEL-RUN-10`: after canonical Task end, 15 uv launchers plus 15 paired `blender-mcp` children remained alive, all rooted at the Codex App Server PID and consuming `724,208 KiB` (`707.2 MiB`) combined RSS. The snapshot directly proves that App Server retained multiple stdio launcher/child pairs, and independent correlation rejected per-call spawning because Task 3 used one stable pair for all 33 calls. Process start times and agent/session logs strongly support, but do not directly prove at thread-runtime identity level, the inference that separate root/subagent sessions initialized separate MCP fleets. All pairs were idle at `0%` CPU, opened no extra `9876` listener and do not explain per-call wall time. Severity is P2/Medium for resources and Low for modeling correctness. No process was killed; normal final Codex Desktop exit/restart is safer than individual mid-run kills.

## Root-cause analysis

The Task 1 plan defect was shell-variable shadowing in the verification harness, not a Blender or fixture-generation failure. `path` is a special `zsh` parameter synchronized with `PATH`; assigning it in the loop removed command-search paths before `stat`, `id`, and subsequent commands ran.

Task 2 adds two preliminary root causes for final Task 4 classification: display-name lookup of built-in nodes is locale-dependent and must use stable RNA types, while `bpy.data.is_dirty` does not express the exact structural state of this programmatic unsaved workflow and must not be used as a post-mutation identity assertion. Both are deterministic plan assumptions rather than abnormal tool latency; neither changed a user file.

`MODEL-RUN-03` is a reporting-harness mistake: human-readable range shorthand omitted three literal issue markers required by the focused validator. The validator caught it before staging; explicit markers are the minimal recovery.

`MODEL-RUN-04` is a timing-capture gap and overstatement: the original Task lacked one comparable monotonic endpoint, so its total cannot be called dual-clock verified and its `MODEL-PLAN-05` compliance was incomplete. The corrective evidence must come from a new clean replay, not reconstructed history.

Task 3 preliminary evidence adds deterministic plan/harness gaps (`MODEL-RUN-05`, `MODEL-RUN-06`, `MODEL-RUN-07`), an evidence-capture gap (`MODEL-RUN-11`), two pinned upstream-tool paths (`MODEL-RUN-08`, `MODEL-PLAN-09`), one render-parent operational gap (`MODEL-RUN-09`), and a multi-stdio MCP session-lifecycle resource issue (`MODEL-RUN-10`). The per-root/subagent-session origin of the last issue is a strong inference, not a directly proven thread-runtime mapping. Task 4 owns the required root-cause class, wall-time loss, reproducibility and preventable-file decision for every row; this section does not prematurely collapse those categories.

## Remediation decision

The Task 1 plan remains byte-for-byte frozen. The controller's authorized execution deviation/waiver is limited to the failed postcondition verification: use `fixture_path` for the non-writing recovery checks, retain the original failure as evidence, and do not rerun the successful provisioner because it would overwrite fixtures. The provisioner and fixtures remain unchanged.

Task 2 establishes two evidence-backed candidates for the later remediation decision: stable node-type guidance for localized Blender sessions and explicit guidance that dirty state is observational, while exact structural/path sentinels determine model identity. Task 4 will apply the frozen file-justification rule; this Task does not create a manual, helper or product-code fix.

The immediate Task 2 review remediation for `MODEL-RUN-04` is evidence-only: perform a clean full modeling replay under one persistent monotonic clock, retain both original and replay records, and avoid changing product code or frozen documents.

Task 3 adds candidates, not implementations: persist controlled orphan datablocks in fixture guidance; durably record verbatim symptoms and first hypotheses before recovery; run harnesses under the documented uv Python/effective editable environment; document screenshot response-size and render-parent safety; update Blender 5.2 render-engine guidance; and add a soft MCP-process baseline/delta diagnostic with normal final Codex Desktop exit/restart guidance. Task 4 will apply the frozen file-justification rule and name exact remediation paths/issue IDs, including `MODEL-RUN-11`.

## Adversarial audit and retest

The waiver's non-writing postcondition verification was rerun in `zsh` and exited `0`; a separately timed equivalent invocation completed in 54.995 ms. Both fixture files remain regular, non-symlink, owned, non-empty files with their original recorded SHA-256 values; the intentionally absent image file is still absent. The successful provisioner was not rerun because it would overwrite existing fixtures, outside this waiver's no-fixture-write scope.

After Phase 3, one independent read-only code assertion compared exact direct Scene and isolated-collection object sets, exact `Mat_*` set, all 14 parent entries, camera, lights, linked library, controlled missing image, selection, engine and relevant data names; it rejected any `.001` and proved non-degenerate ground-excluded lamp-body bounds. The four mandated read-only tools then independently confirmed the unsaved path, exact collection tree/parents/selection, `Lamp_Shade` detail, and summary counts of 15 objects, 7 total materials, 2 cameras, 3 lights and one library. The controlled replay repeated this complete sequence from a newly verified factory scene with zero retries and identical structural results. The counts exceed contract minima because unlinked factory datablocks and the linked source remain data-blocks; exact contract sets were verified separately. Fixture SHA-256 values stayed unchanged. No GUI `.blend` was saved.

Task 3 independently reran the exact structural assertion and all 26 unique tools. The 26-row table matches the live catalog by `Counter`, with no duplicate/missing/extra name or blank field. Render containment used canonical parent equality rather than a suffix check; each target was unique and absent, each copied artifact passed PNG/lstat/hash checks, and path summary remained empty/unsaved after both renders. Local and independent controller image inspection both found the full lamp, distinguishable materials, illuminated bulb, ground shadow, linked prop and no user content. Original fixture hashes and the controlled missing-file absence stayed unchanged; the official source, config, frozen Plan/design and GUI filepath were not modified.

## Final verdict

Baseline preflight/provisioning, Task 2 structural acceptance and fresh Task 3 26/26 coverage completed. Every live tool has a determinate outcome. The frozen plan expected 26 successful tool cases and zero expected errors: 23 unique tools met their first issued case, while three intended-success cases were unexpected failures (original-fixture arbitrary CLI code, original-fixture CLI missing summary, and the 2 MB area screenshot). Exactly three authorized recovery invocations then passed, yielding a usable successful case for all 26 unique tools; those recoveries do not erase the three frozen-case failures. The 3 MB window screenshot was preventively reduced rather than called and is recorded as a deviation, not a failure. Both renders and visual checks passed, and current PID `28354` contains the exact unsaved isolated scene. Task 4 root-cause classification/remediation decisions remain pending; no baseline-complete claim is made here.
