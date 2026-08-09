# Official Blender MCP Modeling Validation

Status: baseline running

## Scope and safety boundary

No user `.blend` was opened or saved. Runtime binaries are untracked. All runtime paths in this report use `$RUN_ROOT` rather than an account name. This active audit is the cumulative Task 1–4 plan output, not historical frozen-plan evidence; it records execution facts and any approved deviations without changing the frozen plan bytes.

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
- Waived non-writing postcondition-verification timing-wrapper wall time: 54.995 ms; the subsequently rerun safe verification command exited `0`.

## 26-tool results

Not started; this Task establishes the isolated baseline only.

## Modeling contract

`$RUN_ROOT` is an owned non-symlink `0700` directory with `assets` and `renders` children. `library_source.blend` and `lamp_fixture.blend` are ordinary non-empty files, and `$RUN_ROOT/assets/known-missing.png` remains absent.

## Errors and recoveries

The frozen Task 1 Step 4 plan prescribed `for path in ...`. In `zsh`, that special parameter is tied to `PATH`, so the original post-provision verification failed after Blender provisioning exited successfully with `zsh:16: command not found: stat`, `zsh:16: command not found: id`, and `zsh:17: command not found: stat`. This first failure remains part of the record.

The plan bytes are frozen. Based on the user's autonomous-completion authorization, the controller formally records one execution deviation/waiver: after the failed postcondition verification, it reran only those non-writing postconditions with `fixture_path`. That safe verification exited `0` in `zsh`, printed the same SHA-256 values for both fixtures, and confirmed the missing image was absent. The successful provisioner was not rerun because that would overwrite fixtures.

## Root-cause analysis

The plan defect was shell-variable shadowing in the verification harness, not a Blender or fixture-generation failure. `path` is a special `zsh` parameter synchronized with `PATH`; assigning it in the loop removed command-search paths before `stat`, `id`, and subsequent commands ran.

## Remediation decision

The Task 1 plan remains byte-for-byte frozen. The controller's authorized execution deviation/waiver is limited to the failed postcondition verification: use `fixture_path` for the non-writing recovery checks, retain the original failure as evidence, and do not rerun the successful provisioner because it would overwrite fixtures. The provisioner and fixtures remain unchanged.

## Adversarial audit and retest

The waiver's non-writing postcondition verification was rerun in `zsh` and exited `0`; a separately timed equivalent invocation completed in 54.995 ms. Both fixture files remain regular, non-symlink, owned, non-empty files with their original recorded SHA-256 values; the intentionally absent image file is still absent. The successful provisioner was not rerun because it would overwrite existing fixtures, outside this waiver's no-fixture-write scope.

## Final verdict

Baseline preflight and provisioning passed. The frozen Step 4 verification command failed in `zsh`; the controller's authorized execution deviation/waiver reran only the non-writing postconditions with `fixture_path`, which exited `0`. Task 1 is ready for dependent validation tasks; the original failure, frozen plan state, waiver scope, and lack of a provisioner rerun remain explicitly documented.
