# Installer managed-drift diagnosis

## Scope and result

The reported `userpref.blend` whole-file drift is not an input to
`InstallationInspection.exact`. The exact gate was already failing closed because the
managed Blender semantic probe reported `online_access=false`; repository, extension
identity, payload integrity, enablement, host, port, and autostart were otherwise valid.

This change keeps the existing exact and rollback policy. It only makes the existing
decision observable:

- `inspect` emits the 13 booleans that feed `exact` in `checks`.
- `blender_checks` separates extension-file integrity from `online_access`, `host`,
  `port`, and `autostart`.
- A managed preference mismatch still makes `exact=false` and `verify` still fails.
- Extension payload corruption still makes `extension_payload_digest=false` and
  `exact=false`.

## Root cause

Receipt pre/post images of `userpref.blend` serve rollback and intra-command stale
snapshot detection. They are intentionally byte-exact so rollback does not silently
overwrite unrelated user preferences changed after installation. They are not compared
with the current whole file by inspection.

Blender can legitimately rewrite unrelated bytes in `userpref.blend`. A regression test
therefore records a different receipt post-image hash while returning all managed
semantics as valid, and proves `exact=true`. This is a counterexample baseline that
already passed before the production change, not the RED test. The fail-closed cases
cover a foreign repository with an otherwise matching payload, a disabled extension,
corrupt extension files, and each preference subcheck independently.

The production failure was the Online Access semantic value itself, not byte drift.
Historical install verification proves Online Access was true when the staged profile
was published. The available receipt cannot identify which later Blender invocation or
UI action changed it, so this patch does not speculate or weaken the gate.

## TDD commits

- `90ec0d6` — RED tests exposing the missing diagnostics and disproving whole-file drift
  as an exact-gate input.
- `7979edd` — GREEN implementation, fail-closed regression coverage, and skill contract
  documentation.
- `e5cff52` — RED reproduction for normal directory mtime change during verified open,
  plus all six managed-state wrapper counterexamples.
- `6e38f7b` — GREEN identity-only verified-open check; tree snapshot mtime checks remain
  unchanged.

## Validation

Certified interpreter setup:

```text
UV=/Users/yeminjie/.local/bin/uv
Python=/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13
Python 3.13.13
```

Final command:

```sh
UV=/Users/yeminjie/.local/bin/uv /Users/yeminjie/.local/bin/uv run --quiet \
  --no-project \
  --python /Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13 \
  --no-python-downloads --with pytest==9.1.1 --with pytest-timeout \
  --with pytest-asyncio --with tomlkit==0.13.3 python -m pytest -q -rs \
  --basetemp=/private/tmp/official-blender-mcp-final-candidate tests/distribution
```

Passed checks:

- focused inspection/CLI regressions: 25 passed
- payload-versus-preference adapter checks: 9 passed
- trusted-checkout and outer CLI checks: 2 passed
- plugin contract after exposing the certified interpreter at ignored `.venv/bin/python`:
  49 passed
- Ruff over plugin scripts and distribution tests
- plugin and skill validators
- built-in compilation of the 11 installer source modules
- four core distribution modules after the directory-race fix: 550 passed, 1 skipped
- final complete distribution suite after the directory-race fix: 791 passed, 1 skipped
  in 171.08 seconds

An earlier complete distribution run returned 755 passed, 29 skipped, and one failure.
Twenty-eight skips were solely the missing worktree-local `.venv/bin/python`; the other
skip was the guarded disposable port-9876 probe because that port was occupied. The
failure was the fault-matrix case
`codex_semantic-absent-after_json_rename-install`. Its preserved receipt stops at
`bundle_stage=staged` and `runtime_tree=planned`, locating the error inside the test
driver's fake runtime setup before Blender inspection. The same case passed 20 isolated
runs and its five neighbors passed together. Once competing real-Blender tests had
stopped, one complete run under the certified interpreter passed 784 tests with only the
guarded port skip. The preserved failure also exposed a pre-existing verified-directory
race: `_open_verified_directory` treated `st_mtime_ns` as object identity even though
normal child changes update directory mtime. The fix still binds type, device, inode,
owner, and mode during open; all later tree-snapshot comparisons retain mtime.
The final complete run after that fix passed all 791 runnable tests. Its sole skip was
again the explicit disposable port-9876 probe because the port was occupied.

## Residual risk

The added fields extend the `inspect` JSON response. Existing fields and exact semantics
are unchanged. Consumers that reject unknown JSON keys would need to accept this additive
diagnostic output. No installer artifact or live configuration was rebuilt or changed.
