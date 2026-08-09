# Official Blender MCP Modeling Validation

Status: baseline running

## Scope and safety boundary

No user `.blend` was opened or saved. Runtime binaries are untracked. All runtime paths in this report use `$RUN_ROOT` rather than an account name.

## Environment and catalog

- Branch: `codex/official-blender-mcp-install`
- Official Blender MCP source pin: `4309a39646e644261624bfcd2bca669b343b7621`
- GUI listener: one `Blender` process on `127.0.0.1:9876`
- GUI baseline: unsaved, clean factory scene with `Camera`, `Cube`, and `Light`; a `VIEW_3D` area is present.

## Stage timings

- Terminal immutable-state preflight: 200 ms (command wall time).
- MCP preflight calls: 784.2 ms path info, 22.0 ms object summary, and 391.1 ms window summary (1,197.3 ms total).
- Fixture process wall time: 1,305.094 ms.
- Blender provisioner `elapsed_ms`: 98.274 ms.

## 26-tool results

Not started; this Task establishes the isolated baseline only.

## Modeling contract

`$RUN_ROOT` is an owned non-symlink `0700` directory with `assets` and `renders` children. `library_source.blend` and `lamp_fixture.blend` are ordinary non-empty files, and `$RUN_ROOT/assets/known-missing.png` remains absent.

## Errors and recoveries

The prescribed Step 4 shell loop used `path` as its loop variable. In `zsh`, that special parameter is tied to `PATH`, so the post-provision verification failed with `command not found: stat` and `command not found: id` after Blender exited successfully. The same non-mutating assertions were rerun with `fixture_path`; both fixtures passed and their SHA-256 hashes were recorded in the ignored run report.

## Root-cause analysis

The failure was shell-variable shadowing in the verification harness, not a Blender or fixture-generation failure.

## Remediation decision

Keep the provisioner unchanged and use a non-special loop variable for subsequent fixture-file verification.

## Adversarial audit and retest

Retest passed: both fixture files are regular, non-symlink, owned, non-empty files; the intentionally absent image file is still absent.

## Final verdict

Baseline preflight passed and fixtures are ready for the dependent validation tasks, with the Step 4 shell-loop recovery documented above.
