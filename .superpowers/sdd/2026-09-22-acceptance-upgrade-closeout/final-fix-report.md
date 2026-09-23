# Final fix: I1–I3

Status: implementation, focused regression, actual M2/M3 gates, and full repository checks are complete. The clean immutable candidate, actual Codex interruption at the stage-written/publication-absent boundary, disposable-profile installer version-only install/verify/finalize, and final graft checks remain open. Do not treat this interim report as independent review or main-delivery approval.

## Fixed base and scope

- FIX_BASE: `140fd697992634b0f8cdaa6ebb5a4d0745409335`
- FIX_BASE tree: `434c0dfc6ead11b17b0361079100faf7e4e1452b`
- Final candidate commit/tree will be recorded after the scoped commit is created.
- The four inherited `.claude/` deletions remain unstaged. No merge or push was performed.
- Implementation touches acceptance evidence/plan/stages/toolchain, installer registration and version, associated unit/distribution/integration tests, and current formal docs. The untracked `tmp20pthrgl/` fixture was left untouched.

## Findings and fixes

**I1 — durable config-stage retry.** The verified native registration output is bound to a durable intent before its config file is moved to `.registration.stage`. Recovery validates the original live config image, verified cache image, recorded native-stage identity, and staged file identity, then continues that exact publication without rerunning `codex plugin add`. This tolerates legitimate native marketplace metadata changes across retries while preserving the old cache and live config; unknown stages, external config edits, changed stage bytes/inode, or cache drift fail closed and remain available for recovery. Existing stage-boundary regressions include the publication-absent interruption and metadata changes, plus stage and external-config drift.

**I2 — optional review verdict.** `review.required` controls whether missing review blocks; when a review is present, `_validate_review` now determines the state for both optional and required policies. A valid explicit rejection produces `REJECTED`, leaves durable technical summary V byte-for-byte unchanged, and prevents delivery. Optional absence and approval continue to ship. Recovery tests exercise approved and rejected verdicts after V is durable.

**I3 — Blender glTF closure.** For `artifact_kind=interchange`, the supported Blender 5.2 macOS application layout determines the actual `Resources/5.2/scripts/addons_core/io_scene_gltf2` tree. Plan creation, tool measurement, R0, and R5 require the exact locked ordinary-file set and verify member bytes and hashes; missing or all-omitted members, new/changed/removed members, links, non-ordinary nodes, and enumeration failures reject. Reproducible `__pycache__` files are excluded from the source lock, with cache nodes still required to be ordinary. The rule is enabled by the interchange capability, so Native contracts remain independent. No transient member count is hardcoded. The fresh real M3 contract locked 128 exporter files in its Blender tool file set.

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

Full repository checks:

```bash
bash scripts/checks.sh
```

Result: **1173 passed, 29 skipped** in the regular suite; **1046 passed** in distribution; final line `ALL CHECKS PASSED`. The 29 skips are the regular entrypoint's explicit integration skips; they do not replace the separately run M2/M3 gates. Log SHA-256: `201688df80a257292ecb35939031f95e04eef421ec8468ab9b6cad8c8286364c`.

## Remaining gates and limits

The exact-candidate actual Codex interruption/retry and the isolated owned-profile installer-version-only install/verify/finalize are not yet run. The installer skill/workflow was read; no normal user config, credentials, sessions, source `.blend`, or live user application was touched. Candidate identity must be sent to the controller and verified before those live operations. Final `graft build .` / `graft check .`, staged scope/whitespace review, final report completion, scoped commit, and controller's independent re-review remain pending.

`RELEASE=1` was not rerun; strict release status remains the previously reported upstream-outdated failure. Normal user profile verification remains previously unpassed; LLM/canary, second Mac, and legacy full-app handoff remain `NOT_RUN`. No main merge or push was made.
