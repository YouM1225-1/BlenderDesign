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
- Corrected Step 4b fixture-verification timing-wrapper wall time: 54.995 ms; the subsequently rerun literal 4b command exited `0`.

## 26-tool results

Not started; this Task establishes the isolated baseline only.

## Modeling contract

`$RUN_ROOT` is an owned non-symlink `0700` directory with `assets` and `renders` children. `library_source.blend` and `lamp_fixture.blend` are ordinary non-empty files, and `$RUN_ROOT/assets/known-missing.png` remains absent.

## Errors and recoveries

The original Task 1 plan prescribed `for path in ...` in what is now Step 4b. In `zsh`, that special parameter is tied to `PATH`, so the original post-provision verification failed after Step 4a Blender provisioning exited successfully with `zsh:16: command not found: stat`, `zsh:16: command not found: id`, and `zsh:17: command not found: stat`. This first failure remains part of the record.

The controller split the plan into Step 4a (the already successful, non-repeatable provisioner) and Step 4b (fixture verification), then corrected every 4b loop-variable reference to `fixture_path`. The corrected literal 4b command exited `0` in `zsh`, printed the same SHA-256 values for both fixtures, and confirmed the missing image was absent.

## Root-cause analysis

The plan defect was shell-variable shadowing in the verification harness, not a Blender or fixture-generation failure. `path` is a special `zsh` parameter synchronized with `PATH`; assigning it in the loop removed command-search paths before `stat`, `id`, and subsequent commands ran.

## Remediation decision

The controller formally corrected the tracked Task 1 plan: Step 4a records the already successful provisioner and prohibits verification-only reruns that would overwrite fixtures; Step 4b contains the file checks and uses the non-special `fixture_path` loop variable in every reference. The provisioner and fixtures remain unchanged. This is a plan correction, not a waiver of the original failed command.

## Adversarial audit and retest

The corrected literal Step 4b fixture-verification command was rerun in `zsh` and exited `0`; a separately timed equivalent invocation completed in 54.995 ms. Both fixture files remain regular, non-symlink, owned, non-empty files with their original recorded SHA-256 values; the intentionally absent image file is still absent. Step 4a was not rerun because it would overwrite existing fixtures, outside this correction's no-fixture-write scope.

## Final verdict

Baseline preflight and Step 4a provisioning passed. The original Step 4b plan was defective in `zsh`; the controller correction is tracked, and the corrected literal 4b command exited `0`. Task 1 is ready for dependent validation tasks; the original failure and its cause remain explicitly documented, and Step 4a is not represented as a rerun.
