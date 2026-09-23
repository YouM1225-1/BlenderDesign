# Final fix: I1–I3

Status: implementation, focused regressions, actual M2/M3 gates, full repository checks, actual Codex stage retry, and isolated owned-profile installer version-only install/verify/finalize are complete. Candidate commit `6ad6638e77f0cebd226172f793301112bdd7322f` has tree `2aceeac1484f6dc9affe7b89fc8183658eb410b1`. Final `graft build .` / `graft check .` passed after the report, plan, and index were updated; the three-file documentation follow-up commit records those results. Controller independent review and main-delivery approval remain separate gates.

## Fixed base and scope

- FIX_BASE: `140fd697992634b0f8cdaa6ebb5a4d0745409335`
- FIX_BASE tree: `434c0dfc6ead11b17b0361079100faf7e4e1452b`
- Final candidate: `6ad6638e77f0cebd226172f793301112bdd7322f`; tree: `2aceeac1484f6dc9affe7b89fc8183658eb410b1`; parent: `140fd697992634b0f8cdaa6ebb5a4d0745409335`. Controller verified commit, tree, parent, and production file hashes before the live operations.
- The four inherited `.claude/` deletions remain unstaged. No merge or push was performed.
- Implementation touches acceptance evidence/plan/stages/toolchain, installer registration and version, associated unit/distribution/integration tests, and current formal docs. The untracked `tmp20pthrgl/` fixture was left untouched.

## Findings and fixes

**I1 — durable config-stage retry.** The verified native registration output is bound to a durable intent before its config file is moved to `.registration.stage`. Recovery validates the original live config image, verified cache image, recorded native-stage identity, and staged file identity, then continues that exact publication without rerunning `codex plugin add`. This tolerates legitimate native marketplace metadata changes across retries while preserving the old cache and live config; unknown stages, external config edits, changed stage bytes/inode, or cache drift fail closed and remain available for recovery. Existing stage-boundary regressions include the publication-absent interruption and metadata changes, plus stage and external-config drift.

**I2 — optional review verdict.** `review.required` controls whether missing review blocks; when a review is present, `_validate_review` now determines the state for both optional and required policies. A valid explicit rejection produces `REJECTED`, leaves durable technical summary V byte-for-byte unchanged, and prevents delivery. Optional absence and approval continue to ship. Recovery tests exercise approved and rejected verdicts after V is durable.

**I3 — Blender glTF closure.** For `artifact_kind=interchange`, the supported Blender 5.2 macOS application layout determines the actual `Resources/5.2/scripts/addons_core/io_scene_gltf2` tree. Plan creation, tool measurement, R0, and R5 require the exact locked ordinary-file set and verify member bytes and hashes; missing or all-omitted members, new/changed/removed members, links, non-ordinary nodes, and enumeration failures reject. Reproducible `__pycache__` files are excluded from the source lock, with cache nodes still required to be ordinary. The rule is enabled by the interchange capability, so Native contracts remain independent. No transient member count is hardcoded. The fresh real M3 contract derived the closure from the supported bundle rather than relying on a transient count.

The independent pre-fix reproductions are preserved by reference in `final-review.md`: I1 stage written/publication absent with native metadata drift, I2 optional explicit rejection published as SHIP, and I3 exporter members omitted at public contract boundaries. Final regressions exercise each behavior, including a direct `run_r0` call that removes the full module lock while presenting matching measured tool rows and observes the closure failure finding. A real Native rerun initially exposed an over-broad I3 implementation that keyed on the executable basename and incorrectly failed Native R5; the capability boundary was narrowed to interchange and verified by the final Native run.

## Verification

Focused command:

```bash
.venv/bin/python -m pytest tests/distribution/test_registration_staging.py tests/unit/test_asset_v2_pipeline.py tests/unit/test_interchange_contract.py -q
```

Result: **109 passed**. Ruff passed for `acceptance/toolchain.py`; the M1 CLI boundary regression passed 2/2 after updating the expected NotTested count to reflect plan-time rejection of an unlocked interchange tool closure.

Final real Native gate:

```bash
RUN_ASSET_NATIVE=1 BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
.venv/bin/python -m pytest tests/integration/test_asset_native.py -vv --tb=long \
  --basetemp=/private/tmp/blenderdesign-finalfix-native-final3
```

Result: **21 passed in 1106.08s**, zero failures, zero skips. This includes 12 good/bad asset cases, supported-capability positives, accurate review binding and exact-D delivery, invalid-image rejection, and durable-summary optional approval/rejection recovery. Log SHA-256: `e82b789a0089fc5e67d69c4ef162184a90bf4ac6e2c7bf696137cd99099b32bd`.

Final real M3 gate:

```bash
RUN_ASSET_INTERCHANGE=1 RUN_GLTF_VALIDATOR=1 \
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
NODE_BIN=/Users/yeminjie/.local/share/pnpm/bin/node \
GLTF_PACKAGE_ROOT=/private/tmp/blenderdesign-closeout-20260922-27x0hxjj/task5-tools/gltf \
.venv/bin/python -m pytest tests/integration/test_asset_interchange.py \
  tests/integration/test_interchange_surface.py tests/integration/test_gltf_validator.py \
  -vv --tb=long --basetemp=/private/tmp/blenderdesign-finalfix-m3-final
```

Result: **8 passed in 312.62s**, zero failures, zero skips. This used a fresh calibration generated from final code and real Blender 5.2, Node 20.20.2, and gltf-validator 2.0.0-dev.3.10. It covered full CLI delivery, missing-consumer and missing-bottom rejection, projection changes, and real Validator positive/negative/truncation paths. Log SHA-256: `1d5cc22fb99630e5dd9810d4c09c75cdce0dfb7a15e57407f5dfde02017a7c6e`.

Actual Codex I1 stage interruption/retry on the immutable candidate:

- The isolated fixture against candidate `6ad6638e77f0cebd226172f793301112bdd7322f` invoked the real Codex CLI and interrupted production registration after `.registration.stage` was durably written while `publication.json` was absent. Recovery ID `d495a6ad-1f6a-4e97-b065-21c8060ef7f9` then resumed successfully without another Codex invocation: call count remained 2 before and after retry.
- The live config remained unchanged until retry; retry removed all owned native config snapshots and the recorded stage, preserved the old cache inode and an unknown `native-codex.unknown` directory, and retained non-target TOML semantics.
- Durable result: `/private/var/tmp/blenderdesign-finalfix-evidence-20260923/codex-stage/result.json`; log: `/private/var/tmp/blenderdesign-finalfix-evidence-20260923/codex-stage/run.log`; SHA-256 `05a0b70acea0f5f6460e2e215567342fd593d205d46f61215417a8a937adf54d`.

Actual isolated owned-profile installer version-only install/verify/finalize:

- A fresh mode-0700 owned HOME first installed and finalized reviewed Task 3 delivery commit `d2cd53eabcdaf98f805c384b20fc28ca5d72283c` (`1.0.0+codex.20260922175350`), then upgraded from clean detached candidate `6ad6638e77f0cebd226172f793301112bdd7322f` (`1.0.0+codex.20260922221552`). Task 3 recorded the delivery commit and reviewed source candidate `a4bf15db6b565b08de37b76439b96d89e7e7add3` as byte-identical across all 29 installer/plugin/artifact production files. Both registrations used real Codex and Blender 5.2.0 LTS; both verified 26 MCP tools and read-only Blender access, and both finalizations completed. Candidate version-only install reported `no_op=true` with the same receipt and bundle `1.0.0+4309a39646e6.p912ed3244261`; finalization removed the old plugin cache version.
- Runtime, extension, preferences, receipts, and active install state matched byte-for-byte across the update. Final owned native config snapshots: zero. No normal profile files, credentials, sessions, projects, or live user applications were used.
- Durable structured evidence: `/private/var/tmp/blenderdesign-finalfix-evidence-20260923/owned-profile-complete/version-only-summary.json`; full real Codex/installer/Blender logs: `oldD.log` (SHA-256 `ac28cc24bd6f4852e1b55f0d6e849f6534226e1936651597c451bb811ea64a23`) and `final.log` (SHA-256 `5a7c5b12728c149487f941088cfa611c16c17a1d50be53f058fa6dc1c76d20ee`) in that evidence directory.

Full repository checks:

```bash
bash scripts/checks.sh
```

Result: **1173 passed, 29 skipped** in the regular suite; **1046 passed** in distribution; final line `ALL CHECKS PASSED`. The 29 skips are the regular entrypoint's explicit integration skips; they do not replace the separately run M2/M3 gates. The first post-documentation run reached ENOSPC during temporary fixture setup; after its temporary directory cleanup, retries completed cleanly with 16–20 GiB free. Latest final-tree log: `/private/var/tmp/blenderdesign-finalfix-evidence-20260923/checks-final.log`, SHA-256 `d4ca6eecd794e298f84dc82b83d745aaa1694f10cadd7cacd571c2a0cb4c8e82`. The prior successful runs were `a6f431dab7b31044446e87e1bb3733b054802400021b4089e7d55fcd0f9ed0cb` and `201688df80a257292ecb35939031f95e04eef421ec8468ab9b6cad8c8286364c`.

## Remaining gates and limits

The installer skill/workflow was read, and the controller verified the exact immutable candidate before live use. The real Codex retry and isolated version-only lifecycle passed as recorded above. The post-documentation full checks passed as recorded above. After updating this report, `graft build .` produced 3542 nodes, 10659 edges, and 178 cards; `graft check .` exited 0 and reported that the wiring graph is in sync. Graft remained at the required wiring-only tier; no deep build was run. The report/plan/index follow-up commit is documentation-only. Controller independent re-review remains a separate gate. The initial `/private/tmp` evidence root was removed during temporary-directory cleanup after the earlier ENOSPC run; I reran both live checks and retained these exact-candidate results under `/private/var/tmp/blenderdesign-finalfix-evidence-20260923`. No normal user config, credentials, sessions, source `.blend`, or live user application was touched.

`RELEASE=1` was not rerun; strict release status remains the previously reported upstream-outdated failure. Normal user profile verification remains previously unpassed; LLM/canary, second Mac, and legacy full-app handoff remain `NOT_RUN`. No main merge or push was made.
