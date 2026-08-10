# Official Blender MCP Modeling Validation

Status: baseline complete; remediation pending

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
- `MODEL-RUN-10`: after canonical Task end, the first host retained 15 uv launchers plus 15 paired `blender-mcp` children consuming `724,208 KiB` (`707.2 MiB`) combined RSS. All disappeared when that App Server exited. New App Server PID `63199` then accumulated 13 pairs consuming about `320,000 KiB` over about 29 minutes. These observations support lifecycle accumulation and host-wide cleanup; they do not constitute a controlled causal reproduction of the inferred root/subagent-session mapping. Independent correlation rejected per-call spawning because Task 3 used one stable pair for all 33 calls. All observed pairs were idle and opened no extra `9876` listener, so they do not explain per-call wall time. Severity remains P2/Medium for resources and Low for modeling correctness. Individual mid-run kills remain unjustified; normal final Codex Desktop exit/restart is safer.

## Root-cause analysis

The ledger below is exhaustive for the baseline: one shell issue, two SDD-controller issues, all eleven observed run issues, and all ten pre-execution plan issues. “Not separately timed” is retained where no contemporaneous bracket exists; no duration is reconstructed. A prevented plan issue has zero failed-call time even when its safety check had a normal execution cost.

| ID | Phase/tool | Symptom | First LLM hypothesis | Evidence | Root cause class | Wall time lost | Recovery | Reproducible | Preventable file |
|---|---|---|---|---|---|---|---|---|---|
| `MODEL-SHELL-01` | Task 1 fixture postconditions | A Bash-labelled fence ran in default zsh; assigning loop variable `path` changed `PATH`, then `stat` and `id` were not found. | The zsh `path` special parameter was coupled to command lookup. | Exact zsh errors plus a green equivalent loop using `fixture_path`. | `manual_gap` | Failed command not separately timed; safe recovery verification was 54.995 ms. | Rerun only no-write checks with a non-special variable; durable rule is explicit `/bin/bash`. | yes; deterministic zsh semantics | `docs/use-official-blender-mcp.md` |
| `MODEL-SDD-01` | SDD `task-brief` generation | Controller redirected helper stdout onto the file the helper itself writes, replacing the brief with a status line. | Shell redirection was assumed to be the helper's output-file interface. | Reviewer rejected the truncated brief; rerun with the helper's explicit third `OUTFILE` restored 205 lines. | `manual_gap` | not separately timed | Use the third `OUTFILE`; never redirect helper stdout to its managed file. | yes; deterministic command/file collision | `docs/use-official-blender-mcp.md` |
| `MODEL-SDD-02` | SDD completion reporting | An older generic `task-1-report.md` was treated as the current destination, so the run-scoped report was initially absent. | The generic report path was assumed to be the active task's report. | Controller absence check and follow-up created `modeling-task-1-report.md`; tracked/runtime state was unchanged. | `manual_gap` | not separately timed | Require a run-scoped brief/report stem and assert the report was absent before dispatch and present after completion. | yes; deterministic path ambiguity | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-01` | Phase 1 `execute_blender_code` | `nodes.get("Principled BSDF")` returned `None` in the Chinese UI after partial Phase 1 writes. | Built-in node display names were localized; stable RNA type `BSDF_PRINCIPLED` should be used. | Failure bracket 49,654.893 ms; MCP wall 1,105.4 ms; clean replay with unique RNA-type lookup passed. | `llm_plan` | 49,654.893 ms failure bracket, including 1,105.4 MCP ms | Terminate unsaved PID, clean preflight, replay Phase 1; proactively use `BACKGROUND` by type too. | yes; locale-dependent display-name lookup | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-02` | Phase 2 `execute_blender_code` | `assert bpy.data.is_dirty is True` failed before Phase 2 wrote; successful programmatic modeling repeatedly observed false. | Dirty reflects a different UI/save lifecycle and is not a structural identity invariant. | Failure bracket 79,910.914 ms; MCP wall 1,176.8 ms; clean replay and later controlled replay both observed false with exact structure. | `llm_plan` | 79,910.914 ms failure bracket, including 1,176.8 MCP ms | Restart clean; use filepath, sentinel, exact sets, data names and parent chain; retain dirty only as observation. | yes; reproduced on clean controlled replay | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-03` | Audit validator | Human range shorthand omitted literal issue IDs and the validator raised `AssertionError: MODEL-PLAN-03`. | Human-readable shorthand was assumed to satisfy machine evidence coverage. | Focused validator failed before staging; explicit literal rows passed without Blender changes. | `manual_gap` | not separately timed | Expand exact issue rows and validate the parsed table rather than prose mentions. | yes; deterministic parser result | `scripts/official_blender_mcp_audit.py` |
| `MODEL-RUN-04` | Task 2 timing | Original Task start lacked a comparable monotonic endpoint; a short-process value was not comparable and prior compliance was overstated. | Per-call markers were assumed sufficient to prove the Task total. | Original total remains UTC-only; clean replay used one clock ID and ended at 431,243.301 ms monotonic / 431,244.808 ms UTC. | `automation_gap` | 431,243.301 ms corrective replay; historical evidence loss itself has no reconstructable duration | Preserve the gap, replay clean under one long-lived dual clock, never synthesize history. | yes; validator can reject missing/mixed clock pairs | `scripts/official_blender_mcp_audit.py` |
| `MODEL-RUN-05` | Catalog harness | Default macOS Python 3.9.6 raised `ModuleNotFoundError: tomllib`. | The unpinned system interpreter predated Python 3.11 while the install used uv Python 3.13. | Version probe proved 3.9.6; absolute uv Python 3.13 recovery passed live/source/config equality in 500.577 ms. | `manual_gap` | Failure not separately timed; recovery was 500.577 ms. | Use the documented absolute uv-managed Python and fail-fast shell. | yes; interpreter version is stable | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-06` | CLI arbitrary code and missing summary | Saved original fixture had no `Fixture_KnownMissing`; arbitrary code errored and missing summary returned empty. | **missing; see `MODEL-RUN-11`; no retrospective wording is substituted** | Failed MCP calls were 684.6 and 557.3 ms; saved/reopened datablocks proved the zero-user image was dropped; fake-user derived fixture passed. | `llm_plan` | 3,887.7 MCP ms: 1,241.9 failed plus 2,645.8 recovery | Preserve originals; create one derived fixture with `use_fake_user=true`; retry each failed tool once. | yes; Blender save/reopen behavior reproduced by the fixture | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-07` | Source-only docs-search reproduction | First harness lacked editable dependencies (`yaml`); second assumed response key `results` instead of `hits`. | First: pinned project dependencies were missing. Second: the response shape had been guessed without source inspection. | Effective editable environment plus source-verified `hits` shape passed; frozen query had zero hits and corrected query one; source stayed clean. | `manual_gap` | not separately timed | Use the effective configured environment and inspect the source response contract before asserting keys. | yes; both failures reproduce deterministically | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-08` | Area screenshot | Frozen 2 MB PNG cap produced truncated JSON / `Unterminated string`; one 48 KB retry passed. | A multi-megabyte base64 response was partially written through a nonblocking bridge frame. | Pinned add-on sets accepted sockets nonblocking, calls one `sendall`, swallows `OSError`, then closes; failure 2,916.8 ms, recovery 3,113.0 ms. | `upstream_tool` | 6,029.8 MCP ms total; 2,916.8 ms was the failed call | Use a 48 KB cap and record the frozen larger case as failed; do not patch the external checkout. | source-confirmed; runtime large case sampled once | `docs/use-official-blender-mcp.md` mitigates the trigger, not the upstream root |
| `MODEL-RUN-09` | Render scratch preflight | Canonical `blender_mcp` scratch parent was absent and pinned render tools do not create it. | The upstream render path was assumed to provision its own parent. | Source inspection plus owned canonical path walk; safety bracket 462.833 ms; both renders passed after creating only the final mode-0700 parent. | `upstream_tool` | 0 failed-call ms; 462.833 ms preventive safety bracket | Record absence, create only the owned final parent, require unique absent basenames and canonical containment. | source-confirmed; absent-parent runtime sampled once | `docs/use-official-blender-mcp.md` mitigates the workflow gap |
| `MODEL-RUN-10` | Post-run process snapshot | First host retained 15 idle uv/server pairs at 707.2 MiB; after its exit all disappeared. A new App Server PID `63199` accumulated 13 pairs at about 320,000 KiB over about 29 minutes; neither host exposed an extra 9876 listener. | App Server lifecycle retained server pairs; the initial per-call-spawn explanation was rejected. | First snapshot took 522.189 ms and Task 3 used one stable pair for all 33 calls. Host-wide exit cleanup and the second accumulation support lifecycle retention, but do not prove a controlled per-root/subagent-session causal mapping. | `upstream_tool` | 0 tool-call ms; first diagnostic 522.189 ms, second not separately timed; P2 resource anomaly only | No mid-run pair kill; normal host exit cleared all old pairs. Keep only a soft baseline/delta diagnostic and normal final exit/restart guidance. | observed again / causal reproduction incomplete | none; the runbook may diagnose it but must not claim prevention |
| `MODEL-RUN-11` | Task 3 evidence capture | Verbatim first hypothesis for `MODEL-RUN-06` was not persisted and cannot be recovered. | **missing; the evidence gap itself was discovered only during review** | Raw report retains symptoms and recovery but explicitly lacks the original wording; correction commit removed the overclaim. | `automation_gap` | 0 tool ms; claim-correction work was not separately timed | Keep the gap explicit; validate that every failure event has symptom and first-hypothesis text before recovery. | yes; current record deterministically fails the field requirement | `scripts/official_blender_mcp_audit.py` |
| `MODEL-PLAN-01` | Phase 3 plan | Frozen payload named invalid Blender 5.2 engine `BLENDER_EEVEE_NEXT`. | The previous engine enum was assumed to remain valid in 5.2. | Runtime enum exposed and accepted exact `BLENDER_EEVEE`; invalid value was never attempted. | `llm_plan` | 0 ms; prevented before mutation | Discover enum, assign/read back before Phase 3 writes. | yes; exact Blender 5.2 enum | `docs/use-official-blender-mcp.md` |
| `MODEL-PLAN-02` | Mutating-phase recovery | Frozen phases lacked complete prior/absence assertions and destroy-and-full-replay recovery. | Sequential payloads were assumed safe to retry in place. | Both real mutating errors required clean PID replacement and full replay; no `.001` or partial state survived. | `llm_plan` | 0 ms as a prevented control; actual recoveries are booked under `MODEL-RUN-01/02` | Transactional preconditions, capture symptom/hypothesis, discard unsaved partial session, replay once. | yes; two failures demonstrated the risk | `docs/use-official-blender-mcp.md` |
| `MODEL-PLAN-03` | Scope contract | Frozen prose allowed too little to express required Scene/World/render changes and did not enumerate exact write ownership. | `Lamp_*` naming was assumed to imply all dependent settings. | Binding scope listed exact isolated datablocks plus verified factory Scene/World/camera/render settings; exact final assertion passed. | `llm_plan` | 0 ms; prevented | Declare exact allowed writes and reject every pre-existing object outside the disposable factory scope. | yes; deterministic plan inspection | `docs/use-official-blender-mcp.md` |
| `MODEL-PLAN-04` | Structural acceptance | Minima, non-degenerate bounds and summary counts could pass with missing, duplicate or stray data. | Summary counts were assumed to prove the model contract. | Extra read-only assertion compared exact 14 objects, exact five materials, parents, data names, library/missing path, no `.001`, and ground-excluded numeric bounds. | `llm_plan` | 0 failed-call ms; original assertion cost 1,847.1 ms and replay assertion 1,900.3 ms | Require exact sets and semantic exclusions, then corroborate with summaries. | yes; deterministic contract comparison | `docs/use-official-blender-mcp.md` |
| `MODEL-PLAN-05` | Task 2 evidence plan | Timing instructions did not enforce one clock ID, paired Task endpoints or literal failure fields. | Independent per-call UTC/monotonic notes were assumed composable. | Original Task total was not dual-clock; `MODEL-RUN-04` replay closed only the new evidence. | `llm_plan` | 0 incremental ms; corrective replay is booked under `MODEL-RUN-04` | Journal paired events under one clock ID and validate finite durations plus required error fields. | yes; original journal fails the invariant | `docs/use-official-blender-mcp.md`; `scripts/official_blender_mcp_audit.py` |
| `MODEL-PLAN-06` | API search | Frozen query deterministically returned zero hits. | Natural spaced tokens were assumed equivalent to the underscored Blender operator identifier. | Source-only reproduction returned zero; corrected `bpy.ops.mesh primitive_cylinder_add` returned one exact hit live. | `llm_plan` | 0 live-failure ms; source reproduction not separately timed | Use the source-proven query form and avoid a known-zero live call. | yes; source reproduction passed | `docs/use-official-blender-mcp.md` |
| `MODEL-PLAN-07` | Tool coverage proof | Marker-presence validator could pass duplicates, missing table rows or prose-only mentions. | Mentioning every tool name somewhere was assumed to prove exact coverage. | Strict parser and `Counter` matched 26 table rows to dynamic live/source/config catalogs; frozen marker validator remained secondary. | `automation_gap` | 0 failed-call ms; validators not separately timed | Dynamically compare catalogs and exact parsed table rows without hardcoding 26. | yes; deterministic adversarial cases | `scripts/official_blender_mcp_audit.py` |
| `MODEL-PLAN-08` | Render containment | Predictable basenames and suffix-only path checks could accept aliasing, overwrite or symlink escapes. | A returned `/blender_mcp/<basename>` suffix plus `test -f` was assumed sufficient. | Unique absent targets, canonical parent equality, lstat/owner/PNG/hash checks all passed for both renders. | `llm_plan` | 0 failed-call ms; safety work is booked under `MODEL-RUN-09` | Canonicalize first, walk owned descendants, reject symlinks, use unique basenames, never overwrite. | yes; deterministic path adversaries | `docs/use-official-blender-mcp.md` |
| `MODEL-PLAN-09` | Thumbnail implementation | Pinned code lowers samples only for obsolete `_NEXT`; Blender 5.2 stayed EEVEE at 64 render samples. | The upstream branch condition was assumed compatible with Blender 5.2. | Source lines 96-99 plus pre/post engine/sample evidence; thumbnail still passed in 2,475.6 ms. | `upstream_tool` | 0 failure ms; 2,475.6 ms thumbnail cost was normal | Record actual engine/samples and time; do not set invalid enum or patch external source. | yes; source/runtime mismatch is stable | none; runbook records the compatibility warning but cannot fix upstream code |
| `MODEL-PLAN-10` | Task 3 timing/recovery | Frozen steps lacked immediate paired timestamps, threshold reruns, partial-render retention and clean replay rules. | Later narrative timing was assumed sufficient for recovery evidence. | One long-lived clock covered all 33 calls; no threshold-only rerun was required; original/recovery artifacts and symptoms were retained except the explicit `MODEL-RUN-11` gap. | `llm_plan` | 0 threshold-rerun ms; instrumentation is included in stage wall | Use journal-first call wrappers in procedure and validate clock pairs/finite durations/literal issue IDs. | yes; deterministic evidence rules | `docs/use-official-blender-mcp.md`; `scripts/official_blender_mcp_audit.py` |

### Event-level failure, retry, and deviation ledger

The issue ledger above gives one root-cause decision per stable ID. This second ledger repeats IDs intentionally so every concrete error, recovery invocation and preventive deviation has its own row and measured cost. It does not change the unique-issue count.

| ID | Phase/tool | Symptom | First LLM hypothesis | Evidence | Root cause class | Wall time lost | Recovery | Reproducible | Preventable file |
|---|---|---|---|---|---|---|---|---|---|
| `MODEL-SHELL-01` | Task 1 fixture check failure | zsh could not find `stat` or `id` after `for path`. | `path` changed zsh's coupled `PATH`. | Exact stderr retained. | `manual_gap` | failed command not separately timed | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-SHELL-01` | Task 1 no-write fixture-check recovery | No Blender/provisioner retry was allowed because fixtures already existed. | A non-special loop variable would preserve command lookup. | Equivalent `fixture_path` checks and both hashes passed. | `manual_gap` | 54.995 ms recovery cost | no-write postconditions only | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-SDD-01` | SDD brief-generation failure | Managed brief was replaced by one stdout status line. | Redirection was assumed to be the output-file interface. | Reviewer rejected truncated input. | `manual_gap` | not separately timed | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-SDD-01` | SDD brief-generation recovery | Helper needed to own the output path. | Its third `OUTFILE` was the supported interface. | Rerun without redirection restored 205 lines. | `manual_gap` | not separately timed | use explicit `OUTFILE` | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-SDD-02` | SDD report-routing failure | Run-scoped completion report was absent. | Old generic report was assumed current. | Controller absence check failed. | `manual_gap` | not separately timed | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-SDD-02` | SDD report-routing recovery | Implementer wrote the required run-scoped report after follow-up. | A run-scoped stem removes ambiguity. | `modeling-task-1-report.md` exists; tracked/runtime state unchanged. | `manual_gap` | not separately timed | follow-up plus presence check | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-01` | Phase 1 failure | Localized display-name lookup asserted after partial writes. | Use stable `BSDF_PRINCIPLED` RNA type. | 49,654.893 ms bracket; 1,105.4 MCP ms. | `llm_plan` | 49,654.893 ms | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-01` | Clean restart and Phase 1 replay | Partial unsaved session could not be retried in place. | Clean full replay would prevent duplicate state. | Restart bracket 2,350.854 ms; Phase 1 replay 1,237.3 MCP ms passed. | `llm_plan` | 3,588.154 ms measured recovery cost | terminate PID, factory preflight, full replay | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-02` | Phase 2 failure | Dirty-true assertion failed before the first Phase 2 write. | Dirty was not a valid programmatic identity invariant. | 79,910.914 ms bracket; 1,176.8 MCP ms. | `llm_plan` | 79,910.914 ms | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-02` | Clean restart plus Phase 1/2 recovery | The pre-Phase-2 state was discarded despite no Phase 2 write. | Exact path/sentinel/sets/parents could replace dirty. | Restart 2,207.585 ms; Phase 1 1,087.4 and Phase 2 1,113.1 MCP ms passed. | `llm_plan` | 4,408.085 ms measured recovery cost | factory preflight, replay Phase 1, corrected Phase 2 | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-03` | Audit validation failure | Range shorthand omitted literal IDs. | Human-readable shorthand was assumed parseable as exact coverage. | `AssertionError: MODEL-PLAN-03`. | `manual_gap` | not separately timed | none in this row | yes | `scripts/official_blender_mcp_audit.py` |
| `MODEL-RUN-03` | Audit validation recovery | Four explicit plan IDs replaced the shorthand. | Literal parsed rows would pass. | Validator passed before staging; no Blender change. | `manual_gap` | not separately timed | expand and revalidate | yes | `scripts/official_blender_mcp_audit.py` |
| `MODEL-RUN-04` | Timing-evidence failure | Original Task total had no comparable monotonic start. | Per-call markers were assumed sufficient. | Original remains UTC-only; no synthesized marker. | `automation_gap` | historical evidence loss not measurable | none in this row | yes | `scripts/official_blender_mcp_audit.py` |
| `MODEL-RUN-04` | Controlled timing recovery | A new factory replay was required to produce valid evidence. | One long-lived clock ID would make all endpoints comparable. | 431,243.301 ms monotonic / 431,244.808 ms UTC; zero replay retries. | `automation_gap` | 431,243.301 ms recovery cost | clean full replay and paired validation | yes | `scripts/official_blender_mcp_audit.py` |
| `MODEL-RUN-05` | Catalog harness failure | System Python lacked `tomllib`. | System Python was older than the pinned environment. | Python 3.9.6 proved. | `manual_gap` | not separately timed | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-05` | Catalog harness recovery | Absolute uv Python 3.13 ran the same equality check. | Pinned interpreter would include `tomllib`. | live/source/config equality passed in 500.577 ms. | `manual_gap` | 500.577 ms recovery cost | fail-fast absolute uv invocation | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-06` | `execute_blender_code_for_cli` failure | `Fixture_KnownMissing` key was absent. | **missing; see `MODEL-RUN-11`** | Error returned in 684.6 ms. | `llm_plan` | 684.6 ms | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-06` | CLI missing-summary failure | Original fixture returned empty `missing_files`. | **missing; see `MODEL-RUN-11`** | Determinate empty result in 557.3 ms. | `llm_plan` | 557.3 ms | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-06` | CLI arbitrary-code recovery | Derived fixture persisted the exact image with fake user. | Save/reopen had dropped a zero-user image. | Authorized recovery passed in 1,182.1 ms; originals unchanged. | `llm_plan` | 1,182.1 ms recovery cost | create new derived fixture only | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-06` | CLI missing-summary recovery | Derived fixture returned exactly the controlled missing path. | Fake-user persistence should make summary deterministic. | Authorized recovery passed in 1,463.7 ms. | `llm_plan` | 1,463.7 ms recovery cost | one retry against derived fixture | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-07` | Source reproduction failure 1 | `yaml` dependency was missing. | Editable pinned project dependencies were omitted. | Exact `ModuleNotFoundError: yaml`. | `manual_gap` | not separately timed | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-07` | Source reproduction failure 2 | Harness asserted nonexistent `results` key. | Response shape was guessed. | Source exposed `hits`. | `manual_gap` | not separately timed | none in this row | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-07` | Source reproduction recovery | Effective editable environment and `hits` assertion passed. | Source contract plus configured dependencies would close both errors. | Frozen query zero; corrected query one; checkout clean. | `manual_gap` | not separately timed | source-verified final harness | yes | `docs/use-official-blender-mcp.md` |
| `MODEL-RUN-08` | 2 MB area screenshot failure | Response JSON was truncated. | Nonblocking one-frame bridge partially sent the expanded base64 payload. | `Unterminated string` in 2,916.8 ms; pinned source confirms risky path. | `upstream_tool` | 2,916.8 ms | none in this row | runtime once; source-confirmed | `docs/use-official-blender-mcp.md` mitigates trigger |
| `MODEL-RUN-08` | 48 KB area screenshot retry | Reduced payload returned a valid 350×192 PNG. | Smaller frame would remain within reliable bridge response size. | Authorized retry passed in 3,113.0 ms. | `upstream_tool` | 3,113.0 ms recovery cost | one reduced-size retry | runtime once; source-confirmed | `docs/use-official-blender-mcp.md` mitigates trigger |
| `MODEL-RUN-08` | Window screenshot preventive deviation | Frozen 3 MB case was not called; 48 KB cap returned 320×164 PNG. | The same transport risk applied to the larger window case. | Preventive call passed in 2,060.5 ms and is not counted as a failure/retry. | `upstream_tool` | 0 failure ms; 2,060.5 ms normal call | preventive cap, no retry | source-confirmed risk | `docs/use-official-blender-mcp.md` mitigates trigger |
| `MODEL-RUN-09` | Render-parent observation/recovery | Final scratch parent was absent; tool lacked directory creation. | Tool was assumed to provision its parent. | 462.833 ms safety bracket; both later renders passed. | `upstream_tool` | 0 failed-call ms; 462.833 ms preventive work | create only final owned 0700 parent | source-confirmed; runtime once | `docs/use-official-blender-mcp.md` mitigates gap |
| `MODEL-RUN-11` | Evidence correction | Review found the `MODEL-RUN-06` first-hypothesis overclaim. | **missing at failure time** | Correction commit made the absence explicit. | `automation_gap` | not separately timed | retain gap; add future validation | yes | `scripts/official_blender_mcp_audit.py` |

### Timing and abnormal-cost verdict

The four non-overlapping measured scopes are kept separate because Task 1 has no full-Task bracket and the original Task 2 total is UTC-only:

| Scope | Stage wall | MCP tool wall | Blender internal | Residual / note |
|---|---:|---:|---:|---|
| Task 1 measured fragments | 2,757.389 ms | 1,197.3 ms | 98.274 ms provisioner | Not a full Task total; includes 200 ms terminal preflight, 1,305.094 ms background process and 54.995 ms safe verification. |
| Task 2 original | 1,810,040.383 ms UTC-only | 15,512.2 ms | 89.165 ms for final successful phases | 1,789,769.744 ms previously derived after tool, restart and terminal preflight subtraction; unattributed orchestration, not LLM time. |
| Task 2 controlled replay | 431,243.301 ms same-process monotonic; 431,244.808 ms UTC | 10,320.3 ms | 78.570 ms phases | 420,923.001 ms unattributed orchestration. |
| Task 3 | 1,747,058.590 ms same-process monotonic; 1,747,073.707 ms UTC | 33,632.4 ms | only embedded call-level values where returned | 1,713,426.190 ms unattributed orchestration. |

The sum of those non-overlapping measured stage durations, using monotonic duration where available, is 3,991,099.663 ms. The corresponding MCP sum is 60,662.2 ms. The 3,930,437.463 ms difference is not “LLM time”: it includes required reading, dispatch brackets, result handling, payload/audit work, SDD coordination, validation, commits, process startup and the explicitly listed Task 1 command/process spans. LLM-only time was not instrumented and is therefore **unknown**.

Explicit failure/recovery costs are reported without manufacturing a single “LLM/retry” number: Task 2's two failed MCP calls were 2,282.2 ms, its two restart brackets were 4,558.439 ms, and its recovery phase calls were 3,437.8 ms; Task 3's three failed frozen-case calls were 4,158.7 ms and its three recovery calls were 5,758.8 ms. The separate 431,243.301 ms controlled replay was evidence remediation for `MODEL-RUN-04`, not an MCP retry.

No official tool invocation was abnormally slow under the frozen rules. Summary/docs/navigation calls peaked at 2,968.0 ms, below 5,000 ms. Screenshot calls were 2,060.5-3,113.0 ms, below 10,000 ms. Thumbnail was 2,475.6 ms, below 30,000 ms; viewport was 1,151.6 ms, below 60,000 ms. Same-case failed/recovery pairs were not over 3× their successful comparison. No threshold-only rerun was justified. Cold docs/summary/render startup is therefore normal cost on this evidence, while Task 3's roughly 28-minute residual is only unattributed orchestration and is insufficient evidence of tool latency. `MODEL-RUN-10` is a P2 resource anomaly, not a call-duration root cause.

## Remediation decision

The frozen decision rule justifies exactly two repository files in the separate remediation plan:

1. Create `docs/use-official-blender-mcp.md`, one concise operational runbook. It prevents the repeatable sequencing and safety mistakes `MODEL-SHELL-01`, `MODEL-SDD-01`, `MODEL-SDD-02`, `MODEL-RUN-01`, `MODEL-RUN-02`, `MODEL-RUN-05`, `MODEL-RUN-06`, `MODEL-RUN-07`, `MODEL-PLAN-01`, `MODEL-PLAN-02`, `MODEL-PLAN-03`, `MODEL-PLAN-04`, `MODEL-PLAN-05`, `MODEL-PLAN-06`, `MODEL-PLAN-08`, and `MODEL-PLAN-10`. It also mitigates the known large-screenshot and missing-render-parent triggers in `MODEL-RUN-08` and `MODEL-RUN-09`, and records the `MODEL-PLAN-09` compatibility warning without claiming to fix external source. For `MODEL-RUN-10`, it may contain only a soft before/after process diagnostic and normal final Codex Desktop exit/restart guidance; the repeated observation supports lifecycle accumulation, but causal reproduction remains incomplete and does not justify a prevention claim.
2. Create `scripts/official_blender_mcp_audit.py`, one standard-library CLI with only `record` and `validate`. `record` writes UTC and monotonic NDJSON events from one long-lived `clock_id`. `validate` dynamically compares live/source/config catalogs, parses the exact audit table with a `Counter`, rejects duplicate/missing/extra/blank fields, requires paired clock events, finite durations, literal issue IDs, and symptom/first-hypothesis fields before recovery. It prevents `MODEL-RUN-03`, `MODEL-RUN-04`, `MODEL-RUN-11`, `MODEL-PLAN-05`, and `MODEL-PLAN-07`, and enforces the evidence part of `MODEL-PLAN-10`. It must not hardcode 26, so approved upstream additions remain accepted dynamically.

A `process-snapshot` subcommand is explicitly rejected for now: `MODEL-RUN-10` was observed again, but its root/subagent-session mapping still lacks a controlled causal reproduction and a runbook `ps` diagnostic is sufficient. This keeps the helper at two commands and avoids turning an incompletely attributed lifecycle observation into product surface.

No product abstraction, Blender transaction wrapper, external-checkout patch, pytest file, dependency, product wrapper or `checks.sh` change is justified. `MODEL-RUN-08`, `MODEL-RUN-09`, `MODEL-PLAN-09`, and `MODEL-RUN-10` concern pinned external/runtime behavior; none has the required twice-reproduced failure in repository-owned product code. No file is created for normal tool startup/render cost or the unattributed orchestration residual. Task 4 is analysis only; the controller will create a separate writing-plans remediation plan before implementing either file.

## Adversarial audit and retest

Task 4 inspected both copied PNGs locally at original detail without editing them. Task 3's independent inspection and the machine PNG/hash checks provide separate corroboration.

| Visual criterion | Thumbnail | Viewport |
|---|---|---|
| Full lamp visible | pass | pass |
| No clipping | pass | pass |
| Materials distinguishable | pass | pass |
| Bulb visibly illuminated | pass | pass |
| Ground shadow present | pass | pass |
| Linked faceted prop visible | pass | pass |
| No user content | pass | pass |

Both views show the complete stylized lamp and linked prop against only the disposable ground/world. No visual issue ID is required. The thumbnail and viewport hashes remain `7a4799be69540a5faa24080d6d24cdfd23050ef692651d5be92881aae66f4bcb` and `1bde67e12dbb50fb7dc1a94a69b484dbcfa410e60164b484a475b2c5fdcd8e14`.

The prior structural and path adversarial evidence remains green: exact scene/material/parent/data sets, no `.001`, non-degenerate ground-excluded bounds, unsaved GUI path, unchanged fixture hashes, controlled missing path, canonical render-parent equality, owned ordinary non-symlink PNGs and exact source/copy hashes. The strict 26-row `Counter` validator has no duplicate, missing, extra or blank row. This Task made no Blender call and changed no runtime, config, frozen file, source checkout or external process.

## Final verdict

Baseline root-cause analysis is complete and remediation is pending. The catalog contained 26 unique tools; the frozen plan expected 26 successes and zero expected errors. Actual first-issued outcomes were 23 successes and three unexpected failures: original-fixture arbitrary CLI code, original-fixture CLI missing summary, and the 2 MB area screenshot. Exactly three authorized recovery invocations passed, so all 26 unique tools ended with a usable determinate success. The preventive 48 KB window screenshot is one recorded deviation, not a fourth failure or recovery.

Unresolved modeling correctness failures: **0**. Irrecoverable historical evidence gaps: **1** (`MODEL-RUN-11`, kept explicit). Repository remediation pending: exactly the two files named above. External/runtime observations not locally repaired: `MODEL-RUN-08`, `MODEL-RUN-09`, `MODEL-PLAN-09`, and `MODEL-RUN-10`; none invalidated the model or tool-call acceptance, and `MODEL-RUN-10` remains evidence-insufficient for its inferred thread/session mapping. Both renders, all seven visual criteria, structural acceptance, containment, catalog/table equality and safety boundaries pass. No user `.blend` was opened, saved or overwritten.
