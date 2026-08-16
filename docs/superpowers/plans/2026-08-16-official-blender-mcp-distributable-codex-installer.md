# Blender Lab Official MCP Distributable Codex Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Ship a macOS Apple Silicon, LLM-driven Codex plugin installer for the pinned official Blender MCP, using one client-neutral artifact contract and a local STDIO MCP configuration.

**Architecture:** A release builder creates a reviewed, SHA-256-integrity-checked bundle containing the official wheel, official Blender extension, and an exact hash-pinned runtime lock. A skill-only Codex plugin invokes a small installer whose filesystem, runtime, Blender, Codex, verification, and recovery transactions are defined and tested before orchestration. The plugin is an adapter only: it has no .mcp.json and contains no second MCP implementation.

**Tech Stack:** Python 3.13 (build baseline 3.13.13); uv 0.12.2; pytest; tomlkit 0.13.3 in the isolated installer runtime; Darwin renameatx_np; Blender 5.2.0 LTS CLI/Python API; Codex CLI capability probes; JSON/TOML; SHA-256.

## Global Constraints

- V1 supports exactly Darwin arm64, a pre-existing local Python 3.13 interpreter, and Blender >=5.2.0,<5.3.0. The tested baselines are Blender 5.2.0 LTS, Python 3.13.13, uv 0.12.2, and codex-cli 0.148.0-alpha.9; target Python patch version is probed and recorded, not fixed to 3.13.13.
- Upstream is https://projects.blender.org/lab/blender_mcp.git at commit 482c540395ad93a2f86b1ada1520f4fddf8ebcfa. Bundle versions are blender-mcp 1.0.0, extension repository user_default / id mcp / version 1.0.0, and mcp[cli] 1.28.1.
- The distribution uses a SHA-256 integrity manifest. Authenticity comes from an operator-supplied reviewed distribution commit. Before plugin add, Python import, or installer execution, one fail-fast external bootstrap clears Git/Python redirection variables, materializes a fresh private detached worktree at that exact commit, verifies its clean scoped tree and commit-object SHA256SUMS, and runs only that commit-derived plugin with isolated Python startup. V1 adds no signing authority.
- V1 is network-assisted. Runtime packages are fetched only as wheels at exact versions and hashes from https://pypi.org/simple. The plan adds no offline wheelhouse.
- The bridge is exactly localhost:9876. Every build, inspect, install, and live probe receives sanitized BLENDER_MCP_HOST=localhost and BLENDER_MCP_PORT=9876; hostile ambient values never win.
- The exact catalog is the 26 names listed under Artifact Contract. Arbitrary-Python tools remain included only after host-local consent.
- Four independent install flags are required: --allow-extension-install, --allow-online-access, --allow-localhost-bridge, and --approve-arbitrary-python. Missing any one exits 2 before creating the state root, lock, backup, receipt, runtime, config, or Blender file.
- Authorization never travels in the bundle and is never reusable from a receipt. A receipt may contain only consent.all_four_collected_for_this_workflow=true for its install ID.
- The supported threat model covers accidental concurrent edits, concurrent installer runs, stale snapshots, unsafe symlinked ancestors/leaves, foreign ownership, and special files. It does not claim protection from an actively malicious same-UID process.
- Existing path components and recursive trees are walked fd-relative with O_DIRECTORY/O_NOFOLLOW. Every writable-boundary and nested entry is current-UID-owned; stable identity, metadata, and entry sets are checked before/after capture. Existing CODEX_HOME, HOME, Blender resource roots, and other parents are never chmodded. Only installer-created private directories receive mode 0700.
- install/repair/rollback hold one exclusive state lock. inspect and verify do not create the lock and are read-only for managed targets. Their uv launcher may read or create uv execution-cache metadata, but --no-python-downloads and --no-sync prohibit interpreter/package downloads.
- Blender and Codex executable paths are required on inspect, install, verify, and rollback. The installer rejects a symlink/non-executable Blender leaf, requires arm64 in its Mach-O architecture list, queries Blender-reported version/architecture/binary path, and records the values. Codex must be an absolute executable whose validated identity is forwarded unchanged to capability and effective-config probes.
- Blender resource paths are queried from the selected executable; no target-host application or user-directory assumption is permitted. BLENDER_USER_RESOURCES is explicit whenever profile isolation is used, with BLENDER_USER_CONFIG and BLENDER_USER_EXTENSIONS beneath it; all three reported paths must remain descendants of the selected resource root.
- No command opens, modifies, moves, or deletes a project .blend file. userpref.blend is a separately modeled preference target.
- Exact no-op classification occurs under the lock before the closed-Blender gate. A no-op creates no receipt, backup, generation, or mutator log entry and returns the active receipt. Any repair and every rollback require Blender normally closed.
- install configures state and returns requires_blender_start. It never launches, kills, or claims ownership of Blender. The skill asks the operator to start the selected Blender normally; verify then performs listener, MCP handshake/catalog, and the single read-only get_blendfile_summary_datablocks call.
- A changed install is not an end-to-end success until verify returns all four layers true: parsed Codex policy, effective codex mcp get subset, exact MCP catalog/handshake, and localhost Blender read-only tool success.
- The repository marketplace remains part of V1 because the requested workflow is LLM-driven installation on another computer. Disposable marketplace add/plugin add/list/discovery and plugin validation are blocking local gates. Actual codex exec skill invocation needs independent disposable authentication and is recorded NOT_RUN, without blocking the implementation commit, when credentials are not supplied.
- The implementation completion gate is local and reproducible. A real second-Mac canary is documented separately and remains NOT_RUN until a release operator supplies a host; it does not block the implementation commit.
- Task 1 implementation does not begin until three fresh read-only reviewers re-audit this revised plan as READY with zero Critical and zero Important findings.
- Do not add a generic package manager, daemon, GUI installer, other-client adapter, signing infrastructure, root-project tomlkit dependency, or second MCP server.

## Artifact Contract

manifest.json uses schema_version 2 and exactly these top-level keys:

~~~text
schema_version, bundle_version, platform, upstream, python, blender,
server, extension, bridge, build, tools, artifacts
~~~

The fixed values are:

~~~json
{
  "schema_version": 2,
  "bundle_version": "1.0.0+482c540395ad",
  "platform": {"system": "Darwin", "machine": "arm64"},
  "upstream": {
    "url": "https://projects.blender.org/lab/blender_mcp.git",
    "commit": "482c540395ad93a2f86b1ada1520f4fddf8ebcfa"
  },
  "python": {"runtime_minor": "3.13", "build_tested": "3.13.13"},
  "blender": {"minimum": "5.2.0", "maximum_exclusive": "5.3.0", "tested": "5.2.0"},
  "server": {"distribution": "blender-mcp", "version": "1.0.0", "mcp_sdk": "1.28.1"},
  "extension": {"repository": "user_default", "id": "mcp", "version": "1.0.0"},
  "bridge": {"host": "localhost", "port": 9876}
}
~~~

build has exactly source_date_epoch, uv, python, blender, codex_tested, backend, and index. source_date_epoch is a positive integer. uv is 0.12.2, python is 3.13.13, blender is 5.2.0, codex_tested is 0.148.0-alpha.9, backend is exactly {"name":"setuptools","version":"80.9.0"}, and index is exactly https://pypi.org/simple.

artifacts is an ordered three-item array with no other roles or basenames:

| role | filename |
| --- | --- |
| server_wheel | blender_mcp-1.0.0-py3-none-any.whl |
| blender_extension | mcp-1.0.0.zip |
| runtime_lock | runtime-requirements.lock |

Each item has exactly role, filename, size, sha256. Filenames are basenames with no slash, backslash, dot-segment, absolute form, or duplicate; size is an integer >0; sha256 is 64 lowercase hexadecimal characters. SHA256SUMS covers manifest.json plus those three files in that order. Unknown keys, bool-as-int values, duplicate roles/names, traversal, wrong ordering/platform/version/catalog, and extra files fail closed.

tools is exactly this ordered catalog:

~~~text
execute_blender_code
execute_blender_code_for_cli
get_blendfile_summary_datablocks
get_blendfile_summary_datablocks_for_cli
get_blendfile_summary_missing_files
get_blendfile_summary_missing_files_for_cli
get_blendfile_summary_of_linked_libraries
get_blendfile_summary_of_linked_libraries_for_cli
get_blendfile_summary_path_info
get_blendfile_summary_path_info_for_cli
get_blendfile_summary_usage_guess
get_blendfile_summary_usage_guess_for_cli
get_object_detail_summary
get_objects_summary
get_python_api_docs
get_screenshot_of_area_as_image
get_screenshot_of_window_as_image
get_screenshot_of_window_as_json
jump_to_tab_by_name
jump_to_tab_by_space_type
jump_to_view3d_object_by_name
jump_to_view3d_object_data_by_name
render_thumbnail_to_path
render_viewport_to_path
search_api_docs
search_manual_docs
~~~

## File Structure

~~~text
.agents/plugins/marketplace.json
plugins/blender-mcp-installer/
├── .codex-plugin/plugin.json
├── artifacts/
│   ├── manifest.json
│   ├── SHA256SUMS
│   ├── blender_mcp-1.0.0-py3-none-any.whl
│   ├── mcp-1.0.0.zip
│   └── runtime-requirements.lock
├── scripts/
│   ├── install.py
│   └── blender_mcp_installer/
│       ├── __init__.py
│       ├── blender_adapter.py
│       ├── bundle.py
│       ├── cli.py
│       ├── codex_adapter.py
│       ├── filesystem.py
│       ├── model.py
│       ├── runtime.py
│       └── verification.py
└── skills/install-official-blender-mcp/SKILL.md
scripts/
├── build_official_blender_mcp_distribution.py
└── requirements/
    ├── official-blender-mcp-build.in
    ├── official-blender-mcp-build.lock
    └── official-blender-mcp-runtime.in
tests/distribution/
├── __init__.py
├── conftest.py
├── fault_driver.py
├── fake_host.py
├── test_blender_adapter.py
├── test_bundle.py
├── test_cli.py
├── test_codex_adapter.py
├── test_filesystem.py
├── test_plugin_contract.py
├── test_runtime.py
└── test_verification.py
docs/distribute-official-blender-mcp.md
docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md
~~~

model.py owns closed schemas. filesystem.py owns secure traversal, locking, snapshots, and conditional promotion. runtime.py, blender_adapter.py, and codex_adapter.py each own one transaction. verification.py owns live read-only probes. cli.py only sequences already-tested interfaces.

## Derived Paths and Durable Transaction Contract

All paths are lexical descendants opened component-by-component; none is obtained by following an untrusted symlink. BUNDLE_ROOT means the artifacts directory, never the plugin directory.

| Role | Exact derived path |
| --- | --- |
| source_distribution_root | operator-supplied repository containing the reviewed commit; never imported/executed |
| distribution_root | private mode-0700-parent detached worktree materialized from the exact reviewed commit |
| bundle_root | $DISTRIBUTION_ROOT/plugins/blender-mcp-installer/artifacts |
| codex_config | $CODEX_HOME/config.toml |
| data_root | $HOME/.local/share/blender-lab-mcp |
| runtime | $HOME/.local/share/blender-lab-mcp/runtime |
| state_root | $HOME/.local/state/blender-mcp-installer |
| lock | $STATE_ROOT/installer.lock |
| receipts | $STATE_ROOT/receipts |
| receipt | $STATE_ROOT/receipts/$INSTALL_ID.json |
| pending | $STATE_ROOT/pending.json |
| active | $STATE_ROOT/active.json |
| backups | $STATE_ROOT/backups/$INSTALL_ID; selector/non-secret recovery only, never a Codex-config copy |
| previous active selector | $STATE_ROOT/backups/$INSTALL_ID/previous-active.json |
| bundle_stage | $STATE_ROOT/stages/$INSTALL_ID/bundle |
| runtime_stage/recovery | $DATA_ROOT/.blender-mcp-installer.$INSTALL_ID.runtime.stage and .recovery |
| extension target | Blender-reported extensions_root/user_default/mcp |
| extension_stage/recovery | extension target parent/.blender-mcp-installer.$INSTALL_ID.extension.stage and .recovery |
| userpref target | Blender-reported config_root/userpref.blend |
| userpref_stage/recovery | config_root/.blender-mcp-installer.$INSTALL_ID.userpref.stage and .recovery |
| Codex stage/recovery | $CODEX_HOME/.blender-mcp-installer.$INSTALL_ID.codex.stage and .recovery |
| Codex rollback stage | $CODEX_HOME/.blender-mcp-installer.$INSTALL_ID.codex.rollback.stage |

BoundaryRole is exactly data_root, state_root, codex_home, blender_resources, blender_config, blender_extensions, or target_parent. TargetRole is exactly runtime, blender_extension, blender_userpref, codex_config, or active_selector. Receipt action target_role is `TargetRole|null`; null is allowed only for bundle_stage, whose target_path is the exact bundle_stage path.

FileImage.state and TreeImage.state are exactly absent or present. An absent FileImage has dev/ino/uid/mode/size/mtime_ns/sha256 all null. A present FileImage has all fields non-null, size >=0, and a 64-hex hash. An absent TreeImage has dev/ino/uid/mode/mtime_ns/digest null and entries=[]. A present TreeImage has all root fields non-null plus sorted entries.

Each TreeEntry has exactly path, kind, dev, ino, uid, mode, size, mtime_ns, sha256. kind is file or dir; sha256 is required only for file and null for dir. Every nested uid equals current UID. Each directory is opened no-follow, its dev/ino/mtime and sorted child-name set are identical before and after recursive traversal, and each file's dev/ino/size/mtime are identical before and after hashing. Nested rewrite, rename, add/remove, ownership change, symlink, and special entry fail.

ReceiptStatus is exactly prepared, installed, rollback_pending, rolled_back, failed, or conflict. ActionKind is exactly bundle_stage, runtime_tree, extension_tree, userpref_file, or codex_file. ObjectKind is exactly bundle, tree, file, or codex. ActionState is exactly planned, staged, swapped, parked, published, completed, semantic_staged, semantic_swapped, restoring, restored, or cleaned.

Each receipt action has exactly ordinal, kind, object_kind, state, target_role, target_path, stage_basename, recovery_basename, pre, intended_post, actual_post, recovery_image, rollback_intended, rollback_displaced. The allowed combinations are:

| Kind | Object | target/stage | recovery basename | Allowed states | Image nullability |
| --- | --- | --- | --- | --- | --- |
| bundle_stage | bundle | target_role=null; exact deterministic bundle path | null | planned -> staged -> cleaned | pre=absent TreeImage; intended_post required from staged; actual_post/recovery_image/rollback_intended/rollback_displaced null |
| runtime_tree | tree | non-null matching target role/path | required | present pre: planned -> staged -> swapped -> parked -> completed -> restoring -> restored -> cleaned; absent pre uses published instead of swapped/parked | pre always required; intended_post required from staged; actual_post required from swapped/published. Present PARKED/COMPLETED has recovery_image=pre. Native present RESTORING has recovery_image=null while post is at S or recovery_image=actual_post once post is at R; absent RESTORING has recovery_image=actual_post at R. Native RESTORED/CLEANED has a closed absent recovery image. Rollback fields null. |
| extension_tree | tree | non-null matching target role/path | required | same as runtime_tree | same as runtime_tree |
| userpref_file | file | non-null matching target role/path | required | same transitions as runtime_tree | FileImage variants with the same null rules; rollback fields null |
| codex_file | codex | target_role=codex_config; required path | required | same forward transitions; exact restore uses restoring/restored, semantic restore uses semantic_staged -> semantic_swapped -> restoring -> restored | FileImage variants; sole original preimage is recovery_image after parked; rollback_intended and rollback_displaced are null except the semantic states defined below |

Task 8 owns durable action-state updates. Task 3 never writes a journal. Before any stage is created, Task 8 writes the action with its deterministic basename and state planned. Each filesystem transition is followed by a complete receipt rewrite.

For a present preimage, T=target, S=stage, and R=recovery have this native state machine:

| State | T | S | R | Transition |
| --- | --- | --- | --- | --- |
| P0 staged | pre | post | absent | renameatx_np(T,S,RENAME_SWAP) |
| P1 swapped | post | pre | absent | renameatx_np(S,R,RENAME_EXCL) |
| P2 parked/installed | post | absent | pre | retain through installed lifetime |
| RS restore-staged | pre | post | absent | renameatx_np(S,R,RENAME_EXCL) |
| R1 restore-swapped | pre | absent | post | result of renameatx_np(T,R,RENAME_SWAP) |
| R2 restored | pre | absent | absent | verify/remove installer post at R, fsync |

Recovery from P0 moves verified post S to R. Recovery from P1 swaps T/S back, records RESTORING with null recovery_image at RS, then the next journaled call moves verified post S to R. Recovery from P2 swaps T/R. All paths reach R1 with recovery_image=actual_post before cleanup. A crash at R1 is idempotent: current==pre and recovery==post means already restored, so retry removes only verified post R and finishes with a closed absent recovery image.

For an absent preimage:

| State | T | S | R | Transition |
| --- | --- | --- | --- | --- |
| A0 staged | absent | post | absent | renameatx_np(S,T,RENAME_EXCL) |
| A1 installed | post | absent | absent | retain target |
| AR1 restore-moved | absent | absent | post | renameatx_np(T,R,RENAME_EXCL) |
| AR2 restored | absent | absent | absent | verify/remove installer post at R, fsync |

A0 recovery moves verified post S to R with RENAME_EXCL; A1 recovery moves T to R. Both reach AR1 with recovery_image=actual_post before cleanup and finish with a closed absent recovery image. A crash at AR1 is already restored and retry-safe. EEXIST, ENOTSUP, and EXDEV always fail closed. filesystem.py contains the only ctypes wrapper for Darwin renameatx_np and constants RENAME_EXCL/RENAME_SWAP.

Every recognized post-rename crash prefix re-fsyncs every affected target/stage/recovery parent and recaptures the exact tuple before the next transition or terminal return. Tree cleanup happens only from R in deterministic child-before-parent order. A retry may accept only an exact deletion prefix: the remaining entries are an exact suffix of that order with the original root dev/ino/uid/mode and original entry identities, with no extra or changed entry; every removal fsyncs its parent. A mismatch conflicts without deleting the changed or extra object.

write_atomic_json(path, expected, payload, install_id, retain_old=None) uses a deterministic same-directory mode-0600 O_EXCL temp, complete write, file fsync, then RENAME_EXCL for absent path or RENAME_SWAP with the validated installer-owned prior inode, followed by parent fsync. After swap, the old JSON at the temp name is either moved with RENAME_EXCL to retain_old (the exact previous-active selector path above) or removed after validation, then both parents are fsynced. A crash leaves an old or new complete JSON, never torn; reconciliation recognizes the deterministic temp and retain path.

PendingSelector has exactly schema_version=1, generation (positive non-bool integer), install_id (canonical UUIDv4), receipt_basename (exactly `<install_id>.json`), manifest_sha256 (64 lowercase hex), and previous_active (`ActiveSelector|null`). ActiveSelector has exactly schema_version=1, generation (positive non-bool integer), install_id (canonical UUIDv4), and receipt_basename (exactly `<install_id>.json`). Unknown fields and mismatched IDs/generations/basenames fail closed. Selector order under lock is: durable pending -> durable prepared receipt -> durable active switch -> durable pending removal. Reconciliation is exact:

| Observed state | Action |
| --- | --- |
| pending, no receipt, old/absent active | verify no stage/target action exists; remove pending and reuse generation |
| pending + valid prepared receipt, old/absent active | publish active to that receipt, remove pending, recover receipt |
| pending + valid prepared receipt + matching active | remove pending, recover receipt |
| no pending + matching active prepared receipt | recover receipt |
| no pending + matching active rollback_pending receipt in SP2/SA1 | resume managed-action restore, selector restoration, terminal receipt rewrite, and selector cleanup |
| rollback_pending receipt named by validated previous-active recovery in SR1/SAR1 | finish final status and selector cleanup |
| failed or rolled_back receipt named by validated previous-active recovery in SR1/SAR1 | validate/remove the displaced new selector, fsync, and finish SR2/SAR2 idempotently |
| receipt not named by pending, active, or validated selector recovery | stale; never adopt or mutate targets |

For active-selector publication/restoration, T=active.json, S=its deterministic same-directory new-selector temp, and R=previous-active.json. A present prior selector uses:

| State | T | S | R | Transition/retry |
| --- | --- | --- | --- | --- |
| SP0 | old | new | absent | RENAME_SWAP(T,S) |
| SP1 | new | old | absent | RENAME_EXCL(S,R); retry may swap T/S back for failed forward recovery |
| SP2 active | new | absent | old | installed state; reverse uses RENAME_SWAP(T,R) |
| SR1 | old | absent | new | already restored; validate/remove new R and fsync |
| SR2 | old | absent | absent | restored |

An absent prior selector uses:

| State | T | S | R | Transition/retry |
| --- | --- | --- | --- | --- |
| SA0 | absent | new | absent | RENAME_EXCL(S,T) |
| SA1 active | new | absent | absent | installed state; reverse uses RENAME_EXCL(T,R) |
| SAR1 | absent | absent | new | already restored; validate/remove new R and fsync |
| SAR2 | absent | absent | absent | restored |

Failure recovery and explicit rollback first durably write the new receipt as rollback_pending, then restore managed actions, restore the active selector, durably write failed or rolled_back, validate/remove the displaced new selector, and fsync both parents. Reconciliation completes any prefix of that order idempotently. Common failpoints are after_rollback_intent, after_active_restore_parent_fsync, after_rollback_status, and after_active_restore_cleanup; present-prior restoration uses after_active_restore_swap and absent-prior restoration uses after_active_restore_move.

Codex semantic rollback uses T=live config, RS=the deterministic codex.rollback.stage, and R=the sole protected original recovery. Let C be the validated current config with permitted foreign additions and M be the deterministic three-way merge restoring managed values while preserving those additions:

| State | T | RS | R | Receipt images and next operation |
| --- | --- | --- | --- | --- |
| C0 | C | absent | pre | derive M; rollback fields null |
| C1 semantic_staged | C | M | pre | rollback_intended=M, rollback_displaced=null; fsync then RENAME_SWAP(T,RS) |
| C2 semantic_swapped | M | C | pre | rollback_intended=M, rollback_displaced=C; rewrite receipt |
| C3 restoring | M | absent | pre | after validating/removing C at RS and parent fsync |
| C4 restored | M | absent | absent | after validating/removing protected pre R and parent fsync |

A fresh process derives C/M again, validates every listed image, and advances only the matching row; unlisted combinations conflict without deletion. Hard-crash points are after_codex_semantic_stage_fsync, after_codex_semantic_swap, after_codex_semantic_receipt, after_codex_semantic_displaced_cleanup, and after_codex_semantic_recovery_cleanup.

All names derive from install ID and every model/native basename rejects separators, dot segments, and embedded NUL before encoding or syscall use. There is no unjournaled random stage. Protected preimages for the active installed receipt remain until successful rollback; installed cleanup removes verified stages only. Retiring an installed generation's preimages is an explicit future retention operation outside V1.

FaultInjector.hit(point: FailPoint) is explicit dependency injection. tests/distribution/fault_driver.py requires `--point`, `--fixture-kind`, and `--preimage` before the `--` command separator, validates that closed fixture descriptor against the applicable matrix in Task 8 before importing the CLI, calls run_cli(argv, fault=ExitFaultInjector(point,70)), and exits with a distinct test-contract error if the point was not hit; production main() always calls run_cli(argv, fault=NoOpFaultInjector()) and never reads failure controls from environment.

---

### Task 1: Strict Bundle Parser, Locked Build, and Staged Publication

**Files:**

- Create: scripts/requirements/official-blender-mcp-build.in
- Create: scripts/requirements/official-blender-mcp-build.lock
- Create: scripts/requirements/official-blender-mcp-runtime.in
- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py
- Create: scripts/build_official_blender_mcp_distribution.py
- Create: tests/distribution/__init__.py
- Create: tests/distribution/test_bundle.py
- Generate: plugins/blender-mcp-installer/artifacts/*

**Interfaces:**

- parse_manifest(raw: bytes) -> ReleaseManifest; strict schema above.
- verify_distribution_checkout(bundle_root: Path, expected_commit: str, runner: Runner) -> TrustedCheckout.
- open_verified_bundle(checkout: TrustedCheckout) -> context manager[VerifiedBundle].
- VerifiedBundle.materialize(private_bundle_stage: Path) -> StagedBundle; consumers receive only StagedBundle paths.
- build_distribution(source: Path, blender_bin: Path, uv_bin: Path, output_dir: Path) -> ReleaseManifest.
- Checkout Git subprocesses explicitly remove GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY, GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_COMMON_DIR, and GIT_CEILING_DIRECTORIES.
- Build subprocess environment explicitly sets BLENDER_MCP_HOST=localhost and BLENDER_MCP_PORT=9876 and removes competing uv/pip/index/bridge variables before setting the fixed index.

- [ ] **Step 1: Write strict parser and builder RED tests**

Add parametrized tests named test_manifest_rejects_unknown_or_missing_keys, test_manifest_rejects_bool_sizes_and_bad_hashes, test_manifest_rejects_bad_names_roles_and_traversal, test_manifest_requires_fixed_versions_and_catalog, test_checkout_requires_detached_exact_clean_commit, test_checkout_rejects_scoped_untracked_file, test_checkout_ignores_redirected_git_environment, test_payload_and_working_checksum_tamper_fails_against_commit_bytes, test_bundle_hashes_same_opened_files, test_replace_wheel_zip_or_lock_after_verify_cannot_change_staged_copy, test_runtime_lock_is_fully_pinned_and_hashed, test_builder_uses_two_fresh_git_archives, test_builder_sanitizes_probe_environment, test_normalized_extension_is_revalidated, and test_publish_keeps_last_good_output_on_gate_failure.

Fixtures create a valid manifest from the contract above, then change exactly one field. Runtime-lock validation groups continuation lines into logical requirement stanzas; each stanza contains one == pin and at least one --hash=sha256:. It rejects editable, URL, local-path, -r, -c, and sdist-only entries.

Checkout verification requires detached HEAD equal to the 40-hex operator input, no staged/unstaged tracked change anywhere, and no untracked file under .agents, plugins/blender-mcp-installer, docs/distribute-official-blender-mcp.md, docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md, scripts/build_official_blender_mcp_distribution.py, or scripts/requirements. It loads trusted checksum bytes with git show EXPECTED_COMMIT:plugins/blender-mcp-installer/artifacts/SHA256SUMS, compares them byte-for-byte to the opened working checksum file, and verifies payloads against those trusted bytes.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_bundle.py -q
~~~

Expected: collection succeeds and fails because bundle.py and the builder do not exist.

- [ ] **Step 3: Implement the bundle and builder contracts**

Build input is exactly build==1.3.0, setuptools==80.9.0, and wheel==0.45.1. Runtime input is exactly docutils, mcp[cli]==1.28.1, pyyaml, and tomlkit==0.13.3. official-blender-mcp-build.lock is a committed builder input; artifacts/runtime-requirements.lock is a committed distributable output.

Regenerate with these exact commands into temporary outputs, then cmp them with the committed locks:

~~~bash
LOCK_CHECK_DIR="$(mktemp -d /private/tmp/blender-mcp-locks.XXXXXX)"
chmod 700 "$LOCK_CHECK_DIR"
$UV_BIN pip compile scripts/requirements/official-blender-mcp-build.in \
  --output-file "$LOCK_CHECK_DIR/official-blender-mcp-build.lock" \
  --python-version 3.13.13 --python-platform aarch64-apple-darwin \
  --only-binary :all: --generate-hashes --no-header --no-annotate \
  --no-sources --exclude-newer 2026-08-16T00:00:00Z \
  --default-index https://pypi.org/simple
$UV_BIN pip compile scripts/requirements/official-blender-mcp-runtime.in \
  --output-file "$LOCK_CHECK_DIR/runtime-requirements.lock" \
  --python-version 3.13 --python-platform aarch64-apple-darwin \
  --only-binary :all: --generate-hashes --no-header --no-annotate \
  --no-sources --exclude-newer 2026-08-16T00:00:00Z \
  --default-index https://pypi.org/simple
cmp scripts/requirements/official-blender-mcp-build.lock \
  "$LOCK_CHECK_DIR/official-blender-mcp-build.lock"
cmp plugins/blender-mcp-installer/artifacts/runtime-requirements.lock \
  "$LOCK_CHECK_DIR/runtime-requirements.lock"
~~~

Build from two separate git archive extractions of the pinned commit. Install the committed build lock with --require-hashes --only-binary :all: --no-deps, then run python -m build --wheel --no-isolation.

Normalize both ZIP-format payloads using SOURCE_DATE_EPOCH, sorted entries, fixed permissions, and no absolute/traversal/symlink/special entries. Run Blender extension validate on the normalized ZIP. Discover the catalog from the normalized wheel in the locked runtime environment and require exact equality.

Build under a unique sibling candidate directory. Validate schema, hashes, locks, wheel metadata, extension manifest, final normalized extension, catalog, and a second clean rebuild before renaming current output to a sibling recovery directory and candidate to output. On failure, leave previous output untouched.

VerifiedBundle retains the trusted checksum, manifest, wheel, ZIP, and lock fds until materialize copies each from its verified fd into the deterministic private bundle stage, fsyncs, and rechecks source identity plus copy size/hash. Read-only commands receive only parsed manifest/payload-index values while the context is open; every subprocess or path consumer receives only StagedBundle copies. No consumer reopens a checkout artifact pathname.

- [ ] **Step 4: Run GREEN and build artifacts**

~~~bash
uv run --frozen pytest tests/distribution/test_bundle.py -q
test -n "$SOURCE_ROOT"
test -n "$BLENDER_BIN"
test -n "$UV_BIN"
test -d "$SOURCE_ROOT"
test -x "$BLENDER_BIN"
test -x "$UV_BIN"
$UV_BIN run --frozen python scripts/build_official_blender_mcp_distribution.py \
  --source "$SOURCE_ROOT" --blender "$BLENDER_BIN" --uv "$UV_BIN" \
  --output plugins/blender-mcp-installer/artifacts
(cd plugins/blender-mcp-installer/artifacts && shasum -a 256 -c SHA256SUMS)
~~~

Expected: tests pass; builder prints tools=26 and recorded tool versions; four checksum lines report OK; a deliberate final-validation failure leaves previous output byte-identical.

- [ ] **Step 5: Run relevant gate**

~~~bash
uv run --frozen ruff check scripts/build_official_blender_mcp_distribution.py \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py \
  tests/distribution/test_bundle.py
~~~

Expected: exit 0.

- [ ] **Step 6: Commit**

~~~bash
git add scripts/requirements scripts/build_official_blender_mcp_distribution.py \
  plugins/blender-mcp-installer/artifacts \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py \
  tests/distribution/__init__.py tests/distribution/test_bundle.py
git commit -m "build: publish locked official Blender MCP bundle"
~~~

---

### Task 2: Closed State Models, Host Fakes, Secure Paths, and Lock

**Files:**

- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/__init__.py
- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/model.py
- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/filesystem.py
- Create: tests/distribution/conftest.py
- Create: tests/distribution/fault_driver.py
- Create: tests/distribution/fake_host.py
- Create: tests/distribution/test_filesystem.py

**Interfaces:**

- InstallRoots.discover(home: Path, codex_home: Path|None, blender: BlenderPaths, *, source_distribution_root: Path, distribution_root: Path) -> InstallRoots.
- SafeRoot.open(path: Path, owner_uid: int, owned_from: Path) -> SafeRoot; walks every system-prefix component with dirfd/O_NOFOLLOW, then requires current-UID ownership from owned_from through path.
- InstallerLock.acquire(state_root: SafeRoot) -> context manager using flock(LOCK_EX|LOCK_NB).
- capture_file(root: SafeRoot, relative: PurePath) -> FileImage.
- capture_tree(root: SafeRoot, relative: PurePath) -> TreeImage.
- write_atomic_json(path: TargetRef, expected: FileImage, payload: Mapping[str,object], install_id: UUID, retain_old: TargetRef|None = None) -> FileImage.
- load_receipt(path: Path, roots: InstallRoots) -> Receipt; accepts only roots.receipts/install_id.json.
- load_pending/load_active(path: Path, roots: InstallRoots) -> PendingSelector|ActiveSelector|None.

InstallRoots exposes every exact path in Derived Paths, including the supplied source_distribution_root and distribution_root and the exact derived bundle_root; tests compare every field to that table. FileImage, TreeImage, TreeEntry, boundary/target roles, selectors, receipt status, action kind/object/state, and nullability are the closed contracts above.

Receipt top-level keys are exactly schema_version, install_id, generation, parent_install_id, status, created_at, bundle, host, consent, targets, actions, verification. schema_version is 1; install_id is canonical UUIDv4; generation is positive; parent_install_id is UUIDv4 or null; created_at is UTC RFC 3339; status uses ReceiptStatus.

- bundle has exactly version and manifest_sha256.
- host has exactly home, codex_home, blender_executable, blender_architecture, blender_version, blender_user_resources, blender_user_config, blender_user_extensions, codex_version, uv_version, python_version.
- consent has exactly all_four_collected_for_this_workflow=true and is never read as authorization.
- targets is ordered by runtime, blender_extension, blender_userpref, codex_config, active_selector. Each item has exactly role, path, boundary_role, pre, install_post, recovery_path, recovery_hash.
- actions are ordinal-sorted and use the exact action schema/state table above.
- verification has exactly configured and live. configured is boolean; live is the literal not_run because verify is read-only and does not rewrite the receipt.

Targets record exact host-derived paths, boundary roles, images, and protected recovery hashes. Recorded paths are evidence, never rollback authority.

Receipt/pending/active files are 0600 and every transition uses write_atomic_json. Created parents are 0700. Receipt contains no config bytes, old MCP tables, environment dumps, tokens, or individual consent booleans.

**Runnable fake-host protocol:**

- host fixture creates HOME, CODEX_HOME, BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, BLENDER_USER_EXTENSIONS, bundle, state, and data roots beneath tmp_path, mode 0700; config/extensions are descendants of resources.
- fake codex handles --version, mcp --help, plugin --help, plugin marketplace --help, and mcp get blender --json; it derives JSON from temporary config.
- fake Blender handles --version, --background --python-expr, extension validate, and extension install-file. State JSON controls running/version/architecture/resource paths/repository/manifest/preferences.
- fake uv handles --version, python find, venv --relocatable, and exact pip install forms. It materializes a deterministic fake runtime and blender-mcp executable.
- fake blender-mcp implements newline JSON-RPC initialize, tools/list, and tools/call; tools/call succeeds only for get_blendfile_summary_datablocks.
- every fake appends JSON to commands.jsonl with tool, argv, sanitized env subset, and mutated paths. Fakes never read failure controls from environment.
- fault_driver.py is invoked by absolute path with Python `-I`; it first parses and validates the required `--point POINT --fixture-kind KIND --preimage present|absent|any --` descriptor against its closed matrix, then derives the trusted distribution root from its own resolved `__file__`, inserts only that root's `plugins/blender-mcp-installer/scripts` into `sys.path`, imports run_cli, and supplies ExitFaultInjector explicitly for the named internal point. It is never packaged into the plugin.

- [ ] **Step 1: Write RED tests for closed-state rules**

Tests: test_exact_derived_path_table, test_ancestor_and_leaf_symlinks_rejected, test_foreign_owner_and_special_file_rejected, test_existing_parent_mode_never_changes, test_file_snapshot_detects_in_place_change, test_tree_snapshot_is_deterministic_and_rejects_nested_symlink, test_tree_detects_nested_rewrite_rename_add_remove_and_foreign_owner, test_image_variant_nullability, test_receipt_action_enum_transition_and_nullability including null-only bundle target role and semantic fields, test_pending_active_exact_schema_variants including previous_active null/present and every wrong type/value, test_atomic_json_crash_is_old_or_new_complete_document, test_receipt_requires_active_root_and_exact_schema, test_receipt_never_contains_secret_sentinel, and test_second_installer_cannot_acquire_lock.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_filesystem.py -q
~~~

Expected: fail on missing model/filesystem modules, not fixture collection.

- [ ] **Step 3: Implement schemas, traversal, capture, receipt IO, and lock**

Use openat-style operations via Python dir_fd arguments. Missing components may be created only under an opened current-UID boundary with mkdir(mode=0700, dir_fd=parent_fd). Reject changes between lstat/open/fstat and before/after hash. Do not add publish, rollback, Codex, Blender, or runtime orchestration.

- [ ] **Step 4: Run GREEN and gate**

~~~bash
uv run --frozen pytest tests/distribution/test_filesystem.py -q
uv run --frozen ruff check \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/model.py \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/filesystem.py \
  tests/distribution/conftest.py tests/distribution/fault_driver.py \
  tests/distribution/fake_host.py \
  tests/distribution/test_filesystem.py
~~~

Expected: tests/Ruff pass; every pre-existing parent keeps its original mode.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer \
  tests/distribution/conftest.py tests/distribution/fake_host.py \
  tests/distribution/fault_driver.py \
  tests/distribution/test_filesystem.py
git commit -m "feat: add closed installer state primitives"
~~~

---

### Task 3: Conditional File and Directory Transactions

**Files:**

- Modify: plugins/blender-mcp-installer/scripts/blender_mcp_installer/filesystem.py
- Modify: tests/distribution/test_filesystem.py

**Interfaces:**

- rename_excl(src_parent: SafeRoot, src_name: str, dst_parent: SafeRoot, dst_name: str, fault: FaultInjector) -> None.
- rename_swap(left_parent: SafeRoot, left_name: str, right_parent: SafeRoot, right_name: str, fault: FaultInjector) -> None.
- create_deterministic_stage(parent: SafeRoot, basename: str, expected_absent: FileImage|TreeImage, fault: FaultInjector) -> StagedObject.
- copy_tree(source: TreeRef, stage: StagedTree) -> TreeImage; rejects nested symlinks/special files.
- forward_file/forward_tree(target, expected_pre, staged_post, recovery, fault) -> NativeState.
- restore_file/restore_tree(target, expected_pre, expected_post, stage, recovery, fault) -> RestoreState.

The wrappers call renameatx_np only with RENAME_EXCL or RENAME_SWAP, use dirfds, fsync both affected parents, and map EEXIST/ENOTSUP/EXDEV to fixed fail-closed InstallerError values. Stage/recovery basenames are the deterministic values already recorded by Task 8; Task 3 never allocates random names and never reads/writes the receipt.

forward/restore implement exactly P0-P2/RS/R1-R2 and A0-A1/AR1-AR2 from Durable Transaction Contract. They classify the present-preimage and absent-preimage crash states from closed images. Restore accepts current==pre plus recovery==post as already restored; any unlisted combination conflicts without a rename.

- [ ] **Step 1: Write RED transaction tests**

Cover absent/present file, empty/non-empty directory, deterministic stage collision, nested symlink/FIFO, cross-volume recovery, concurrent destination after snapshot, RENAME_EXCL EEXIST, RENAME_SWAP ENOTSUP/EXDEV, crash after present swap, crash after preimage park, crash after absent publish, crash after each reverse rename, present/absent quarantine-before-cleanup, both native RESTORING recovery-image variants, retry from exact deletion prefixes and R1/AR1, affected-parent fsync redrive, embedded-NUL rejection, conditional restore, and foreign postimage/remainder preservation. Assert exact T/S/R images and direct ReceiptAction construction for every reverse row; no Task 3 test expects journal writes.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_filesystem.py -q
~~~

Expected: new transaction tests fail on absent interfaces.

- [ ] **Step 3: Implement minimal transactions**

Implement the local ctypes signature and Darwin constants, then the state tables without a fallback to os.rename/os.replace. Never recursively delete an unverified path. Cleanup removes only a closed installer post/stage after root identity and entries are revalidated. Installed cleanup never removes rollback preimages; they remain through a fresh-process installed rollback.

- [ ] **Step 4: Run GREEN**

~~~bash
uv run --frozen pytest tests/distribution/test_filesystem.py -q
~~~

Expected: all transaction cases pass with byte/tree-identical restoration.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/filesystem.py \
  tests/distribution/test_filesystem.py
git commit -m "feat: add conditional installer transactions"
~~~

---

### Task 4: Codex Three-Way Configuration Transaction

**Files:**

- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/codex_adapter.py
- Create: tests/distribution/test_codex_adapter.py

**Interfaces:**

- desired_codex_values(managed_launcher: Path, profile: ManagedProfile, tools: Sequence[str]) -> ManagedCodexValues.
- stage_codex_config(live_config_fd: int|None, current: FileImage, desired: ManagedCodexValues, runtime_python: Path, stage: StagedFile) -> CodexChange.
- verify_codex_toml(raw: bytes, desired: ManagedCodexValues) -> None.
- verify_codex_effective(codex_bin: Path, desired: ManagedCodexValues, env: Mapping[str,str]) -> EffectiveCodexState.
- rollback_codex(current, protected_recovery, installer_post, managed_keys, runtime_python, fault: FaultInjector) -> RollbackResult.

Owned values are command=the verified runtime/bin/blender-mcp-managed launcher; args=[]; omit_tools_from=[]; startup_timeout_sec=20.0; tool_timeout_sec=60.0; default_tools_approval_mode=approve; enabled_tools=the exact catalog; env.HOME; env.BLENDER_USER_RESOURCES; env.BLENDER_USER_CONFIG; env.BLENDER_USER_EXTENSIONS; env.BLENDER_PATH; env.BLENDER_MCP_HOST=localhost; env.BLENDER_MCP_PORT=9876; env.PYTHONNOUSERSITE=1; env.PYTHONSAFEPATH=1; and membership mcp__blender in features.code_mode.direct_only_tool_namespaces.

tomlkit runs only through the staged/active locked runtime; pyproject.toml and uv.lock do not change. The helper reads the still-live config through the inherited validated fd and writes only the deterministic mode-0600 merged stage. It creates no preimage copy. After RENAME_SWAP, the old config in the stage is parked at the deterministic Codex recovery path and becomes the sole protected preimage. Receipt stores only its re-derived path/hash and managed key metadata.

Rollback reads pre values/nodes from that sole recovery object. For each owned scalar/list/env key: current==installer-post restores pre; current==pre is already restored; any other current value is a conflict. Foreign table/env keys and namespace additions are preserved. Exact current/post uses the generic native swap. A non-conflicting semantic merge follows C0-C4 in the central contract: journal and fsync codex.rollback.stage, call `fault.hit(after_codex_semantic_stage_fsync)`, swap it with current, call the matching swap hit, journal both semantic images and hit the receipt boundary, validate/remove the displaced current and hit its cleanup boundary, then validate/remove the protected preimage and hit its cleanup boundary. `run_cli(..., fault)` forwards its explicit injector to `rollback_codex`; production supplies only `NoOpFaultInjector`. Any managed-key or unlisted crash-state conflict stops before deletion/publication. Parsed TOML verifies every owned value; codex mcp get blender --json runs only after publication and verifies its exposed command, args, env, enabled tools, and timeouts.

- [ ] **Step 1: Write RED adapter tests**

Tests cover fd-read merge with no preimage copy; exact merge/comment preservation; managed launcher/profile/host/port under hostile ambient values; all owned TOML fields; effective JSON subset only after publish; changed command/profile/host/port/tool policy conflicts; foreign env/table/namespace additions preserved; missing-pre restored to absent; every C0-C4 semantic state; crashes after semantic-stage fsync, swap, receipt rewrite, displaced cleanup, and protected-recovery cleanup; fresh-process retry; and secret sentinel absent from every receipt/error/duplicate backup/orphan stage after every failpoint.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen --with tomlkit==0.13.3 \
  pytest tests/distribution/test_codex_adapter.py -q
~~~

Expected: fail because codex_adapter.py is absent.

- [ ] **Step 3: Implement adapter and helper subprocess**

The helper receives the inherited live fd and non-secret desired values through a mode-0600 deterministic request below the receipt stage, writes one mode-0600 staged TOML file, and emits only a redacted result. It closes inherited descriptors in finally. Parser/UTF-8/JSON errors become fixed-message InstallerError values without echoing bytes.

- [ ] **Step 4: Run GREEN and existing config regression**

~~~bash
uv run --frozen --with tomlkit==0.13.3 \
  pytest tests/distribution/test_codex_adapter.py tests/unit/test_config.py -q
~~~

Expected: pass; existing custom-server behavior is unchanged.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/codex_adapter.py \
  tests/distribution/test_codex_adapter.py
git commit -m "feat: add three-way Codex configuration transaction"
~~~

---

### Task 5: Blender Discovery and Staged Extension/Preference Transaction

**Files:**

- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/blender_adapter.py
- Create: tests/distribution/test_blender_adapter.py

**Interfaces:**

- inspect_blender(blender_bin: Path, env: Mapping[str,str], runner: Runner) -> BlenderState.
- resolve_blender_paths(blender_bin, env, runner) -> BlenderPaths.
- probe_blender_lifecycle(blender_bin: Path, runner: Runner) -> BlenderLifecycle.
- stage_blender_change(state, extension_zip, install_stage, authorizations, runner) -> BlenderChange.
- compare_extension_tree(expected_payload: PayloadIndex, current: TreeRef) -> ExtensionComparison.
- prepare_extension_for_restore(comparison: ExtensionComparison) -> TreeImage.
- verify_blender_files(state: BlenderState, expected_payload: PayloadIndex) -> None.

BlenderState includes executable, executable_arches, reported_binary, reported_architecture, version, user_resources, config_root, userpref, extensions_root, repository, extension_root, manifest_id/version, enabled, online_access, host, port, autostart, and canonical_payload_digest. BlenderLifecycle includes matching_selected_pids, listener_pid, listener_executable, and port_free.

Path discovery uses one read-only background expression to return bpy.app.binary_path, bpy.app.version, platform.machine(), bpy.utils.resource_path("USER"), bpy.utils.user_resource("CONFIG"), and bpy.utils.user_resource("EXTENSIONS"). BLENDER_USER_RESOURCES is explicit for isolated profiles; BLENDER_USER_CONFIG and BLENDER_USER_EXTENSIONS are descendants of it. Reported binary must match the supplied non-symlink executable, and reported user/config/extensions must all be descendants of the declared resources root after component-safe validation.

The lifecycle probe runs only fixed /usr/bin/pgrep and /usr/sbin/lsof paths. It parses `/usr/bin/pgrep -x Blender` as decimal PIDs, then `/usr/sbin/lsof -a -p PID -d txt -FpcfDinu` as one strict process header plus one-or-more complete `txt` file records containing fd, device, inode, path, and numeric UID. Nonmatching system text images such as dyld are permitted, but exactly one complete record must match the already-open selected executable's device/inode/path and the process UID must equal the current UID; zero or multiple matches fail closed. It obtains the TCP 9876 listener with `/usr/sbin/lsof -nP -iTCP:9876 -sTCP:LISTEN -FpcfDinu` and requires the listener PID/UID plus that PID's separately queried matching `txt` record to identify the selected executable. Missing, duplicate-within-record, malformed, ambiguous, wrong-UID, same-path/different-inode, or multiple-listener records fail closed. Repair/rollback require no matching selected PID and port_free=true. Verify requires listener_pid among matching_selected_pids and matching selected executable; this proves executable/PID ownership only, not that macOS exposes the process's profile environment.

Staging sets BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, and BLENDER_USER_EXTENSIONS to private transaction descendants, copies existing userpref into staging when present, never copies one for absent preimage, validates/installs staged ZIP into user_default, enables bl_ext.user_default.mcp, sets Online Access/localhost/9876/autostart, then saves only staged userpref. A fresh process inspects staged extension/userpref before publication.

One extension policy serves inspect/no-op/verify/recovery/rollback. Every bundled payload entry must match bytes/mode exactly. The only allowed extras are current-UID regular files matching __pycache__/*.pyc whose source stem maps to a bundled .py file; they are disposable, never part of payload digest, and are removed fd-relatively after revalidation before restore. Missing/changed payload or any other extra conflicts. Blender's .cache/compat.dat outside the managed mcp subtree is documented as an unowned side effect and is inventoried, not deleted.

- [ ] **Step 1: Write RED adapter tests**

Tests cover non-default executable/resource roots; required BLENDER_USER_RESOURCES ancestry; symlink/non-arm64 executable; resource escape; wrong repository/ID/version; altered/missing/foreign-extra payload; validated pyc allowance/removal; rollback after actual extension import; empty-profile creation; existing userpref preservation; four preference values; hostile ambient host/port; fake state order; no real-target write during staging; exact no-op/repair; matching/nonmatching pgrep process; free/foreign/ambiguous listener; exact lsof `D/i/u` fixtures; one executable plus dyld `txt` multi-record output; missing/duplicate-within-record fields; zero/multiple executable matches; wrong UID; same path with different inode; and one disposable live-process parser probe.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_blender_adapter.py -q
~~~

Expected: fail because blender_adapter.py is absent.

- [ ] **Step 3: Implement discovery and staging only**

Runner environments are allowlists containing exact HOME, BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, BLENDER_USER_EXTENSIONS, selected executable PATH needs, and literal bridge values. Use only fixed native probe paths. Do not start a GUI, touch real extension/userpref targets, or add rollback sequencing.

- [ ] **Step 4: Run GREEN**

~~~bash
uv run --frozen pytest tests/distribution/test_blender_adapter.py -q
~~~

Expected: pass with command logs proving only stage paths were mutated.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/blender_adapter.py \
  tests/distribution/test_blender_adapter.py
git commit -m "feat: stage exact Blender extension and preferences"
~~~

---

### Task 6: Hash-Enforced Runtime Transaction

**Files:**

- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/runtime.py
- Create: tests/distribution/test_runtime.py

**Interfaces:**

- inspect_runtime(runtime_root: TargetRef, manifest: ReleaseManifest) -> RuntimeState.
- stage_runtime(bundle: StagedBundle, uv_bin, python_bin, profile: ManagedProfile, stage, runner) -> TreeImage.
- verify_runtime(runtime_root, manifest, profile, runner) -> RuntimeState.
- RuntimeState includes tree image, actual Python 3.13 patch version, every locked distribution/version, blender-mcp 1.0.0, mcp 1.28.1, tomlkit 0.13.3, official entry-point identity, managed-launcher identity/environment, and exact catalog.

Stage with:

~~~text
uv venv --relocatable --python <resolved-local-3.13> <deterministic-stage>
uv pip install --python <stage-python> --require-hashes --only-binary :all:
  --no-build --no-deps --default-index https://pypi.org/simple
  -r runtime-requirements.lock
uv pip install --python <stage-python> --no-deps --no-build <verified-wheel>
~~~

Subprocess environment sets UV_REQUIRE_HASHES=1, UV_NO_BUILD=1, fixed index, and literal bridge values while removing competing uv/pip/index/bridge variables. uv cache/network writes during install are an explicit non-managed side effect. Exact runtime is no-op. Different, incomplete, or altered runtime uses Task 3 state machine.

Stage writes runtime/bin/blender-mcp-managed as the only Codex command. The launcher uses os.execve on the verified official blender-mcp entry point. It discards inherited environment and constructs exactly PATH=/usr/bin:/bin:/usr/sbin:/sbin, HOME, BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, BLENDER_USER_EXTENSIONS, BLENDER_PATH, BLENDER_MCP_HOST=localhost, BLENDER_MCP_PORT=9876, PYTHONNOUSERSITE=1, and PYTHONSAFEPATH=1. LANG, LC_ALL, TMPDIR, PYTHONPATH, PYTHONHOME, PYTHONUSERBASE, PYTHONSTARTUP, PYTHONINSPECT, VIRTUAL_ENV, UV_*, PIP_*, and all other BLENDER_* values are absent. Tests execute the actual launcher under a hostile parent and assert the exact environment, runtime import path, selected binary/profile, and bridge identity.

- [ ] **Step 1: Write RED runtime tests**

Tests cover every command option and sanitized variable; compatible local Python 3.13 patch recording; lock hash failure before publication; sdist rejection; hostile Python/bridge/profile parent values; actual managed launcher environment/runtime identity; absent install; exact no-op with zero uv calls; different runtime repair; deterministic stage collision; P1/P2 and reverse crash states; deterministic tree digest; retained installed preimage; fresh-process installed rollback; and conditional conflict after foreign runtime edit.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_runtime.py -q
~~~

Expected: fail because runtime.py is absent.

- [ ] **Step 3: Implement runtime staging/inspection**

Use only StagedBundle copies and Task 3 transactions. Verify distributions with importlib.metadata inside staged runtime and query official entry point through fake/real catalog probe. Do not edit receipts, Codex, or Blender.

- [ ] **Step 4: Run GREEN**

~~~bash
uv run --frozen pytest tests/distribution/test_runtime.py -q
~~~

Expected: pass; exact second inspection produces no command-log change.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/runtime.py \
  tests/distribution/test_runtime.py
git commit -m "feat: add locked Blender MCP runtime transaction"
~~~

---

### Task 7: Read-Only Inspection and Four-Layer Verification

**Files:**

- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/verification.py
- Create: tests/distribution/test_verification.py

**Interfaces:**

- probe_host(blender_bin: Path, codex_bin: Path, uv_bin: Path, python_bin: Path, env) -> HostCapabilities.
- inspect_installation(bundle, roots, blender_state, host) -> InstallationInspection.
- verify_live(bundle, inspection, runtime_command, codex_bin, env, mcp_probe) -> VerificationResult.

HostCapabilities records actual platform, Codex/uv/Blender/Python versions, arm64 evidence, and exact capability probes. codex mcp get --help must exit 0 and contain --json; codex plugin marketplace add --help and codex plugin add --help must exit 0. codex mcp get blender --json is forbidden before Codex publication and runs only in post-publication inspection/verification. Unsupported/missing capability fails before mutation and actual versions remain in redacted evidence.

InstallationInspection is exact only when runtime, extension repository/ID/version/payload digest, enablement, preferences, Codex parsed policy/namespace, effective Codex subset, active generation, manifest hash, and recorded Blender executable all match. It does not require a running GUI. inspect and verify snapshot all managed targets before/after and fail if they change.

verify_live calls Task 5 lifecycle probe and requires the 9876 listener PID/executable to match the selected Blender as far as pgrep/lsof prove. It then launches the actual configured managed STDIO command under a hostile parent, requires MCP initialize, exact ordered catalog, and get_blendfile_summary_datablocks with no arguments. TCP/handshake from a foreign matching-protocol listener never passes. No execute, render, screenshot, or _for_cli tool is called. In finally it closes MCP streams, sends terminate to the temporary STDIO child, waits with a fixed timeout, and reports cleanup failure; it never terminates Blender.

- [ ] **Step 1: Write RED verification tests**

Tests cover help-based capability success with absent Blender MCP entry; unsupported --json; exact inspection; every exactness field independently false; missing/foreign/ambiguous listener; protocol-compatible listener owned by another executable; handshake failure; catalog missing/extra/reordered/duplicate; read-only call failure; hostile Python/host/profile parent; STDIO close/terminate/wait on every exit; and before/after managed-target images identical for inspect/verify.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_verification.py -q
~~~

Expected: fail because verification.py is absent.

- [ ] **Step 3: Implement read-only probes**

Use injected runners/MCP probe for unit tests and the official MCP client in locked runtime for real probe. Convert JSON/TOML/UTF-8/protocol failures to redacted InstallerError messages.

- [ ] **Step 4: Run GREEN**

~~~bash
uv run --frozen pytest tests/distribution/test_verification.py -q
~~~

Expected: pass and commands.jsonl contains no managed mutation for inspect/verify.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/verification.py \
  tests/distribution/test_verification.py
git commit -m "feat: verify Blender MCP without managed writes"
~~~

---

### Task 8: Journaled Install, No-Op, Failure Recovery, and Rollback CLI

**Files:**

- Create: plugins/blender-mcp-installer/scripts/install.py
- Create: plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py
- Create: tests/distribution/test_cli.py

**Interfaces:**

~~~text
install.py inspect  --bundle-root ARTIFACTS --expected-distribution-commit SHA
                    --blender PATH --codex PATH --uv PATH
install.py install  --bundle-root ARTIFACTS --expected-distribution-commit SHA
                    --blender PATH --codex PATH --uv PATH
                    --allow-extension-install --allow-online-access
                    --allow-localhost-bridge --approve-arbitrary-python
install.py verify   --bundle-root ARTIFACTS --expected-distribution-commit SHA
                    --blender PATH --codex PATH --uv PATH [--receipt PATH]
install.py rollback --bundle-root ARTIFACTS --expected-distribution-commit SHA
                    --blender PATH --codex PATH --uv PATH --receipt PATH
~~~

ARTIFACTS must be the exact artifacts directory in Derived Paths. Public functions are inspect(args)->dict, install(args)->dict, verify(args)->dict, rollback(args)->dict, reconcile_selectors(roots,bundle,blender,fault)->ReconcileResult, recover_active(roots,bundle,blender,fault)->dict, run_cli(argv: Sequence[str], fault: FaultInjector)->int, and main(argv: Sequence[str]|None)->int. main always supplies NoOpFaultInjector.

**Install sequence:**

1. argparse validates BUNDLE_ROOT shape, 40-hex expected commit, absolute executable --blender/--codex/--uv, and all four install flags before invoking any installer function; the validated Codex path is forwarded unchanged to every capability/effective probe.
2. Open TrustedCheckout/VerifiedBundle, retaining fds; run read-only uv/Python/Codex/Blender capability and path probes.
3. Acquire exclusive lock; re-derive roots/targets and reconcile pending/receipt/active plus deterministic JSON temps exactly as the selector table states.
4. If the active receipt is prepared or rollback_pending, reconcile each action and selector against the exact native/semantic tables, then recover before continuing. If it is installed but bundle_stage is staged or its cleanup rewrite is incomplete, validate/remove the present stage or accept its verified absence, rewrite bundle_stage=cleaned, and finish cleanup before no-op classification; this covers after_receipt_installed.
5. Inspect exact state. If exact, return no_op=true and active receipt without mutation even if Blender is open.
6. For repair/change, Task 5 must report no selected Blender PID and free port. Allocate install ID/generation and complete planned actions with deterministic basenames.
7. Through write_atomic_json: publish pending; publish prepared receipt; switch active while parking prior selector below backups/install_id; remove pending. Inject after every durable substep.
8. For bundle_stage, write planned receipt before creating state stages, materialize VerifiedBundle from retained fds, write staged. For each runtime/extension/userpref/Codex action, write planned before stage creation, write staged after deterministic post snapshot, execute one Task 3 native transition at a time, and rewrite swapped/published, parked, and completed states.
9. Re-inspect filesystem/config exactness, write status=installed, inject after_receipt_installed, validate/remove the bundle stage, fsync, rewrite bundle_stage=cleaned, retain every installed rollback preimage, and return changed=true, no_op=false, receipt, requires_blender_start=true, and redacted host/bundle facts. Do not live-verify.

Normal injected failures reverse actions under the same lock. Recovery classifies only the exact selector and native states in Durable Transaction Contract; any other identity/hash/path conflicts without writing. It is retry-safe after every reverse transition. Codex uses Task 4 exact/semantic three-way protocol. All paths are re-derived from install ID/role; receipt strings are comparison evidence only.

rollback accepts only active installed or prepared receipt below resolved receipts root. It revalidates owner/mode/schema/manifest/generation/selected Blender/profile/targets/recoveries, requires selected Blender closed and port free, and keeps the lock through rollback_pending, managed-action restore, exact active-selector restoration, final receipt status, and selector cleanup. Stale, copied, renamed, inactive, divergent, or secret-hash-mismatched receipts fail without mutation.

**Success JSON:**

- inspect: command, exact, host, managed_target_count, active_install_id.
- install: command, changed, no_op, bundle_version, receipt, requires_blender_start.
- verify: command, receipt, parsed_codex, effective_codex, mcp_catalog, blender_read_only, tool_count=26.
- rollback: command, receipt, status=rolled_back, restored_roles.

- [ ] **Step 1: Write runnable end-to-end RED tests with HostHarness**

Each real argparse subparser test invokes inspect/install/verify/rollback with an actual artifacts directory, --expected-distribution-commit, --blender, --codex, and --uv; install includes all flags. Tests prove each command forwards the exact absolute Codex executable; a missing/relative Codex path and a plugin-root bundle value fail before mutation.

Tests independently cover each missing consent flag with zero managed-target/download/sync/fake-host mutation; a direct main() call proves zero installer-owned writes while skill-level tests acknowledge possible uv launcher-cache metadata. Also cover first install; exact no-op same receipt/images; repair; selected-Blender-open no-op/repair rejection; free-port gate; install has no GUI command; verify while open; rollback while open rejection; active installed fresh-process rollback with recoveries present; installed-but-bundle-stage-present and installed-but-bundle-stage-absent cleanup before no-op; selector reconciliation for every pending/active and SP0-SR2/SA0-SAR2 row; rollback_pending retry after every selector reverse boundary; stale receipt; re-derived path mismatch; recovery hash mismatch; concurrent lock; Codex conflict; and payload-plus-working-checksum tamper.

Closed FAILPOINTS and their only applicable variants are below. Each action/selector transition point fires after the corresponding complete receipt/selector rewrite and parent fsync unless its name explicitly identifies an earlier fsync/rename boundary.

| Scope | Preimage | Applicable points |
| --- | --- | --- |
| atomic JSON | any | after_json_file_fsync, after_json_rename, after_json_parent_fsync |
| pending/receipt common forward | prior active present or absent | after_pending_publish, after_receipt_publish, after_pending_remove |
| active selector forward | prior present | after_active_swap, after_active_park, after_active_parent_fsync |
| active selector forward | prior absent | after_active_publish, after_active_parent_fsync |
| bundle_stage | absent only | after_bundle_stage_planned, after_bundle_stage_stage, after_receipt_installed, after_bundle_stage_cleanup |
| runtime_tree, extension_tree, userpref_file, codex_file exact | present | after_KIND_planned, after_KIND_stage, after_KIND_swap, after_KIND_park, after_KIND_completed, after_KIND_restore_swap, after_KIND_restore_move, after_KIND_restore_cleanup |
| runtime_tree, extension_tree, userpref_file, codex_file exact | absent | after_KIND_planned, after_KIND_stage, after_KIND_publish, after_KIND_completed, after_KIND_restore_move, after_KIND_restore_cleanup |
| codex_file semantic rollback | present | after_codex_semantic_stage_fsync, after_codex_semantic_swap, after_codex_semantic_receipt, after_codex_semantic_displaced_cleanup, after_codex_semantic_recovery_cleanup |
| active selector reverse | prior present | after_rollback_intent, after_active_restore_swap, after_active_restore_parent_fsync, after_rollback_status, after_active_restore_cleanup |
| active selector reverse | prior absent | after_rollback_intent, after_active_restore_move, after_active_restore_parent_fsync, after_rollback_status, after_active_restore_cleanup |

fault_driver.py requires `--point POINT --fixture-kind KIND --preimage present|absent|any -- COMMAND ...`, rejects a point not applicable to that closed fixture/action/preimage state before CLI import, and proves the requested point was hit; an injected hit exits exactly 70. The exhaustive subprocess matrix reruns normal recovery to completion and asserts exact T/S/R/selector/receipt states, retry behavior, retained installed preimages, cleaned installed bundle stage, and no secret sentinel in receipts, errors, duplicate backups, or orphan stages.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen --with tomlkit==0.13.3 pytest tests/distribution/test_cli.py -q
~~~

Expected: fixture collects and tests fail because install.py/cli.py are absent.

- [ ] **Step 3: Implement only orchestration and redacted error boundary**

install.py imports main and contains no logic. cli.py owns selector/action journal sequencing and calls prior interfaces; it does not parse TOML, walk trees, install packages, construct Blender scripts, or read fault controls from environment. main prints one sorted JSON object, maps parser/missing-consent errors to 2, expected InstallerError to 1, unexpected errors to fixed redacted internal-error and 1.

- [ ] **Step 4: Run GREEN and distribution gate**

~~~bash
uv run --frozen --with tomlkit==0.13.3 pytest tests/distribution -q
uv run --frozen ruff check \
  plugins/blender-mcp-installer/scripts tests/distribution
~~~

Expected: all tests pass; each failure/crash parameter has exact postconditions; Ruff passes.

- [ ] **Step 5: Commit**

~~~bash
git add plugins/blender-mcp-installer/scripts/install.py \
  plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py \
  tests/distribution/test_cli.py
git commit -m "feat: orchestrate recoverable Blender MCP installation"
~~~

---

### Task 9: Skill-Only Plugin, Repository Marketplace, and Operator Workflow

**Files:**

- Create: plugins/blender-mcp-installer/.codex-plugin/plugin.json
- Create: plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md
- Create: .agents/plugins/marketplace.json
- Create: tests/distribution/test_plugin_contract.py
- Create: docs/distribute-official-blender-mcp.md
- Modify: docs/README.md
- Modify: scripts/checks.sh

**Interfaces:**

- Plugin manifest has exactly name, version, description, author, skills, interface; skills is ./skills/; mcpServers and apps are absent.
- Marketplace source is ./plugins/blender-mcp-installer with installation AVAILABLE and authentication ON_INSTALL.
- Operator supplies SOURCE_DISTRIBUTION_ROOT, EXPECTED_DISTRIBUTION_COMMIT, BLENDER_BIN, and a validated absolute CODEX_BIN. Before plugin add/import, the following fail-fast external bootstrap is the sole entrypoint. It materializes `.agents/` and the complete plugin tree inside a fresh private detached worktree; thereafter DISTRIBUTION_ROOT always means that trusted worktree, PLUGIN_ROOT is `$DISTRIBUTION_ROOT/plugins/blender-mcp-installer`, and BUNDLE_ROOT is `$PLUGIN_ROOT/artifacts`.

~~~bash
set -euo pipefail
: "${SOURCE_DISTRIBUTION_ROOT:?set source repository path}"
: "${EXPECTED_DISTRIBUTION_COMMIT:?set reviewed 40-hex commit}"
: "${BLENDER_BIN:?set absolute Blender executable}"
: "${CODEX_BIN:?set absolute Codex executable}"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_CEILING_DIRECTORIES
unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONINSPECT \
  PYTHONBREAKPOINT VIRTUAL_ENV
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
case "$EXPECTED_DISTRIBUTION_COMMIT" in
  ''|*[!0-9a-f]*) echo "expected distribution commit must be 40 lowercase hex characters" >&2; exit 1 ;;
  *) ;;
esac
test "${#EXPECTED_DISTRIBUTION_COMMIT}" -eq 40
test "$(git -C "$SOURCE_DISTRIBUTION_ROOT" rev-parse HEAD)" = \
  "$EXPECTED_DISTRIBUTION_COMMIT"
git -C "$SOURCE_DISTRIBUTION_ROOT" diff --quiet
git -C "$SOURCE_DISTRIBUTION_ROOT" diff --cached --quiet
test -z "$(git -C "$SOURCE_DISTRIBUTION_ROOT" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer \
  docs/distribute-official-blender-mcp.md \
  docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md \
  scripts/build_official_blender_mcp_distribution.py scripts/requirements)"
TRUST_PARENT="$(mktemp -d /private/tmp/blender-mcp-trust.XXXXXX)"
chmod 700 "$TRUST_PARENT"
TRUSTED_DISTRIBUTION_ROOT="$TRUST_PARENT/distribution"
EMPTY_HOOKS="$TRUST_PARENT/empty-hooks"
mkdir "$EMPTY_HOOKS"
chmod 700 "$EMPTY_HOOKS"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  worktree add --detach --no-checkout \
  "$TRUSTED_DISTRIBUTION_ROOT" "$EXPECTED_DISTRIBUTION_COMMIT"
chmod 700 "$TRUSTED_DISTRIBUTION_ROOT"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$TRUSTED_DISTRIBUTION_ROOT" \
  read-tree "$EXPECTED_DISTRIBUTION_COMMIT"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  archive --format=tar "$EXPECTED_DISTRIBUTION_COMMIT" | \
  tar -x -C "$TRUSTED_DISTRIBUTION_ROOT"
test -z "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" symbolic-ref -q HEAD || true)"
test "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" rev-parse HEAD)" = \
  "$EXPECTED_DISTRIBUTION_COMMIT"
git -C "$TRUSTED_DISTRIBUTION_ROOT" diff --quiet
git -C "$TRUSTED_DISTRIBUTION_ROOT" diff --cached --quiet
test -z "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer)"
test -d "$TRUSTED_DISTRIBUTION_ROOT/.agents"
test -d "$TRUSTED_DISTRIBUTION_ROOT/plugins/blender-mcp-installer"
TRUSTED_CHECKSUMS="$(mktemp "$TRUST_PARENT/SHA256SUMS.XXXXXX")"
chmod 600 "$TRUSTED_CHECKSUMS"
git -C "$TRUSTED_DISTRIBUTION_ROOT" show \
  "$EXPECTED_DISTRIBUTION_COMMIT:plugins/blender-mcp-installer/artifacts/SHA256SUMS" \
  > "$TRUSTED_CHECKSUMS"
DISTRIBUTION_ROOT="$TRUSTED_DISTRIBUTION_ROOT"
PLUGIN_ROOT="$DISTRIBUTION_ROOT/plugins/blender-mcp-installer"
BUNDLE_ROOT="$PLUGIN_ROOT/artifacts"
cmp "$TRUSTED_CHECKSUMS" "$BUNDLE_ROOT/SHA256SUMS"
(cd "$BUNDLE_ROOT" && shasum -a 256 -c "$TRUSTED_CHECKSUMS")
~~~

Every shell command checks status because `set -euo pipefail` remains active. The worktree is created with `--no-checkout` and an empty private hooks path; `read-tree` plus built-in `git archive --format=tar` materializes commit objects without checkout hooks or working-tree filters before the scoped clean check. Plugin-add and each installer command execute in the same fail-fast shell session as this bootstrap and never reuse an unchecked path from another session; a new session reruns the bootstrap. The trusted worktree and checksum file are retained through the workflow as evidence. Cleanup first runs `git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" worktree remove "$TRUSTED_DISTRIBUTION_ROOT"`, then removes exactly `$TRUSTED_CHECKSUMS` and the now-empty `$EMPTY_HOOKS` directory, and only then removes the now-empty private parent. Tests cover a dirty tracked installer script, scoped untracked file, redirected Git variables, hostile `PYTHONPATH` sitecustomize, payload plus working checksum tamper, replacement of the source-checkout script after the clean check, and a source `post-checkout` sentinel hook that must never run; every negative fails before plugin import, while the post-check source replacement proves execution still comes from the unchanged trusted worktree.

- After external trust is established, before every installer command the skill runs this bootstrap without installing uv/Python:

~~~bash
if test -n "$UV_BIN"; then
  CANDIDATE_UV="$UV_BIN"
elif command -v uv >/dev/null 2>&1; then
  CANDIDATE_UV="$(command -v uv)"
elif test -x "$HOME/.local/bin/uv"; then
  CANDIDATE_UV="$HOME/.local/bin/uv"
else
  echo "uv 0.12.2 and a local Python 3.13 are required; install them, then retry." >&2
  exit 1
fi
case "$CANDIDATE_UV" in /*) ;; *) echo "UV_BIN must be absolute" >&2; exit 1;; esac
test -x "$CANDIDATE_UV"
test "$("$CANDIDATE_UV" --version | awk '{print $2}')" = "0.12.2"
"$CANDIDATE_UV" run --help | grep -q -- "--no-sync"
"$CANDIDATE_UV" run --help | grep -q -- "--no-python-downloads"
PYTHON_BIN="$("$CANDIDATE_UV" python find 3.13 --no-project \
  --no-python-downloads --no-config)"
test -x "$PYTHON_BIN"
"$PYTHON_BIN" -I -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 13))'
UV_BIN="$CANDIDATE_UV"
ISOLATED_RUNNER='import runpy,sys; root=sys.argv[1]; script=sys.argv[2]; sys.argv=sys.argv[2:]; sys.path.insert(0,root); runpy.run_path(script,run_name="__main__")'
~~~

The skill then runs:

~~~bash
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" inspect \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
~~~

The exact command suffixes after the isolated runner and `"$PLUGIN_ROOT/scripts/install.py"` are:

~~~text
inspect  --bundle-root "$BUNDLE_ROOT"
         --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT"
         --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
install  --bundle-root "$BUNDLE_ROOT"
         --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT"
         --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
         --allow-extension-install --allow-online-access
         --allow-localhost-bridge --approve-arbitrary-python
verify   --bundle-root "$BUNDLE_ROOT"
         --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT"
         --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
rollback --bundle-root "$BUNDLE_ROOT"
         --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT"
         --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
         --receipt "$RECEIPT_PATH"
~~~

The installer performs locked network installation only for changed install. The skill reports launcher-cache caveat, runs inspect first, presents four separate risks, waits for four explicit answers, passes all flags once, and never treats receipt consent evidence as permission.

After changed install, skill stops, asks operator to start selected Blender normally, waits for confirmation, and runs verify. It asks operator to close Blender normally before repair/rollback. It never starts or terminates Blender.

- [ ] **Step 1: Scaffold and write RED contract tests**

Use plugin-creator only for missing manifest/marketplace structure; never force over artifacts/scripts. Tests assert skill-only shape, exact marketplace entry/artifact integrity, fail-fast commit-derived trust bootstrap, cleared Git/Python redirection, private checksum path, isolated runner, uv explicit/PATH/home fallback including allowed symlinked uv, exact uv/Python probe before every command, artifacts bundle root, expected commit/Blender/Codex/uv arguments on every real parser, all consent flags, no receipt authorization reuse, operator start/close checkpoints, integrity/authenticity wording, no machine-specific path, optional external-auth wording, and canary initialized to NOT_RUN.

- [ ] **Step 2: Run RED**

~~~bash
uv run --frozen pytest tests/distribution/test_plugin_contract.py -q
~~~

Expected: fail because plugin metadata, skill, and docs are absent.

- [ ] **Step 3: Create plugin, marketplace, docs, and checks integration**

Implement and document the Interfaces block's external trust bootstrap as the sole pre-plugin entrypoint. EXPECTED_DISTRIBUTION_COMMIT comes from the reviewed repository/release channel, not manifest.json. Document network wheel fetches, uv cache effects, Blender .cache/compat.dat, supported boundaries, receipt retention, exact commands, local STDIO managed launcher, and why marketplace is LLM delivery adapter rather than another MCP.

- [ ] **Step 4: Run GREEN plugin validation and focused gates**

~~~bash
test -n "$PLUGIN_CREATOR_ROOT"
python3 "$PLUGIN_CREATOR_ROOT/scripts/validate_plugin.py" \
  plugins/blender-mcp-installer
uv run --frozen pytest tests/distribution -q
uv run --frozen ruff check scripts/build_official_blender_mcp_distribution.py \
  plugins/blender-mcp-installer/scripts tests/distribution
~~~

Expected: validator, tests, and Ruff pass.

- [ ] **Step 5: Run blocking disposable marketplace discovery smoke**

~~~bash
SMOKE_HOME="$(mktemp -d /private/tmp/blender-mcp-marketplace.XXXXXX)"
chmod 700 "$SMOKE_HOME"
SMOKE_CODEX_HOME="$SMOKE_HOME/.codex"
mkdir "$SMOKE_CODEX_HOME"
chmod 700 "$SMOKE_CODEX_HOME"
SMOKE_PATH="$(dirname "$UV_BIN"):/usr/bin:/bin:/usr/sbin:/sbin"
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" plugin marketplace add "$DISTRIBUTION_ROOT"
MARKETPLACE_NAME="$("$PYTHON_BIN" -I -c \
  'import json,sys;print(json.load(open(sys.argv[1]))["name"])' \
  "$DISTRIBUTION_ROOT/.agents/plugins/marketplace.json")"
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" plugin add "blender-mcp-installer@$MARKETPLACE_NAME"
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" plugin list --marketplace "$MARKETPLACE_NAME" --json > "$SMOKE_HOME/plugins.json"
"$PYTHON_BIN" -I -c 'import json,sys; p=json.load(open(sys.argv[1])); assert type(p) is dict and set(p)=={"installed","available"}; assert type(p["installed"]) is list and type(p["available"]) is list; assert all(type(x) is dict and type(x.get("name")) is str for x in p["installed"]+p["available"]); assert sum(x["name"]=="blender-mcp-installer" for x in p["installed"])==1' \
  "$SMOKE_HOME/plugins.json"
~~~

Expected: marketplace add/plugin add/list/discovery and plugin validation pass without authentication from the trusted commit-derived tree; normal HOME/CODEX_HOME, source checkout, artifacts, and managed roots remain identical. Tests require actionable failure for missing CODEX_HOME, uv, top-level array, missing/extra top-level key, non-array installed/available value, malformed item, duplicate/missing installed plugin, and dirty/replaced/untrusted source trees.

If an operator supplies DISPOSABLE_CODEX_API_KEY independently, authenticate only the disposable profile and run optional invocation:

~~~bash
printf '%s' "$DISPOSABLE_CODEX_API_KEY" | \
  HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" login --with-api-key
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" login status
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" exec --sandbox read-only --skip-git-repo-check \
  "Invoke install-official-blender-mcp in inspect-only mode. Do not install."
~~~

Never copy normal Codex credentials. Scan logs/evidence for the credential sentinel. Without supplied disposable credentials record LOCAL_LLM_INVOCATION_STATUS: NOT_RUN; this optional external-auth result does not block Step 6.

- [ ] **Step 6: Commit**

~~~bash
git add .agents/plugins/marketplace.json plugins/blender-mcp-installer \
  tests/distribution/test_plugin_contract.py docs/distribute-official-blender-mcp.md \
  docs/README.md scripts/checks.sh
git commit -m "feat: package Blender MCP installer plugin"
~~~

---

### Task 10: Local Clean-Profile Gate and Separately Owned Second-Mac Canary

**Files:**

- Create: docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md
- Runtime-only: clean detached distribution checkout plus disposable HOME/CODEX_HOME/BLENDER_USER_RESOURCES/BLENDER_USER_CONFIG/BLENDER_USER_EXTENSIONS

**Implementation completion interface:** local report has IMPLEMENTATION_GATE: PASS, LOCAL_LLM_INVOCATION_STATUS: PASS or NOT_RUN, and SECOND_MAC_CANARY_STATUS: NOT_RUN. It records reviewed implementation commit, clean-detached/trusted-checksum evidence, artifact sizes/hashes, actual platform/Blender/Codex/uv/Python patch versions, local receipt hash, fake-host failure/crash matrix count, blocking marketplace discovery, one real post-publication crash recovery, clean-profile install/no-op/verify/rollback, and before/after normal-profile/project inventories.

Steps 2-4 run in one fail-fast shell session so private trust/profile variables cannot be lost. If execution is split across sessions, rerun Step 2's external bootstrap and derive a new trusted worktree/checksum path before importing or invoking the plugin.

- [ ] **Step 1: Create the evidence skeleton and verify RED**

Create the report with all required section headings, IMPLEMENTATION_GATE: NOT_RUN, LOCAL_LLM_INVOCATION_STATUS: NOT_RUN, and SECOND_MAC_CANARY_STATUS: NOT_RUN. Then run:

~~~bash
python3 -c 'from pathlib import Path; text=Path("docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md").read_text(); assert "IMPLEMENTATION_GATE: PASS" in text'
~~~

Expected: AssertionError because no local evidence has passed yet.

- [ ] **Step 2: Run clean repository and artifact gates**

Resolve UV_BIN and the download-disabled local Python 3.13 PYTHON_BIN with Task 9's executable/version/capability bootstrap before this block; this step still performs no repository import.

~~~bash
set -euo pipefail
: "${SOURCE_DISTRIBUTION_ROOT:?set source repository path}"
: "${EXPECTED_DISTRIBUTION_COMMIT:?set reviewed 40-hex commit}"
: "${BLENDER_BIN:?set absolute Blender executable}"
: "${CODEX_BIN:?set absolute Codex executable}"
: "${UV_BIN:?set validated absolute uv executable}"
: "${PYTHON_BIN:?set validated local Python 3.13 executable}"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_CEILING_DIRECTORIES
unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONINSPECT \
  PYTHONBREAKPOINT VIRTUAL_ENV
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
ISOLATED_RUNNER='import runpy,sys; root=sys.argv[1]; script=sys.argv[2]; sys.argv=sys.argv[2:]; sys.path.insert(0,root); runpy.run_path(script,run_name="__main__")'
case "$EXPECTED_DISTRIBUTION_COMMIT" in
  ''|*[!0-9a-f]*) echo "expected distribution commit must be 40 lowercase hex characters" >&2; exit 1 ;;
  *) ;;
esac
test "${#EXPECTED_DISTRIBUTION_COMMIT}" -eq 40
test "$(git -C "$SOURCE_DISTRIBUTION_ROOT" rev-parse HEAD)" = \
  "$EXPECTED_DISTRIBUTION_COMMIT"
git -C "$SOURCE_DISTRIBUTION_ROOT" diff --quiet
git -C "$SOURCE_DISTRIBUTION_ROOT" diff --cached --quiet
test -z "$(git -C "$SOURCE_DISTRIBUTION_ROOT" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer \
  docs/distribute-official-blender-mcp.md \
  docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md \
  scripts/build_official_blender_mcp_distribution.py scripts/requirements)"
TRUST_PARENT="$(mktemp -d /private/tmp/blender-mcp-accept.XXXXXX)"
chmod 700 "$TRUST_PARENT"
TRUSTED_DISTRIBUTION_ROOT="$TRUST_PARENT/distribution"
EMPTY_HOOKS="$TRUST_PARENT/empty-hooks"
mkdir "$EMPTY_HOOKS"
chmod 700 "$EMPTY_HOOKS"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  worktree add --detach --no-checkout \
  "$TRUSTED_DISTRIBUTION_ROOT" "$EXPECTED_DISTRIBUTION_COMMIT"
chmod 700 "$TRUSTED_DISTRIBUTION_ROOT"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$TRUSTED_DISTRIBUTION_ROOT" \
  read-tree "$EXPECTED_DISTRIBUTION_COMMIT"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  archive --format=tar "$EXPECTED_DISTRIBUTION_COMMIT" | \
  tar -x -C "$TRUSTED_DISTRIBUTION_ROOT"
DISTRIBUTION_ROOT="$TRUSTED_DISTRIBUTION_ROOT"
PLUGIN_ROOT="$DISTRIBUTION_ROOT/plugins/blender-mcp-installer"
BUNDLE_ROOT="$PLUGIN_ROOT/artifacts"
test -z "$(git -C "$DISTRIBUTION_ROOT" symbolic-ref -q HEAD || true)"
test "$(git -C "$DISTRIBUTION_ROOT" rev-parse HEAD)" = "$EXPECTED_DISTRIBUTION_COMMIT"
git -C "$DISTRIBUTION_ROOT" diff --quiet
git -C "$DISTRIBUTION_ROOT" diff --cached --quiet
test -z "$(git -C "$DISTRIBUTION_ROOT" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer \
  docs/distribute-official-blender-mcp.md \
  docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md \
  scripts/build_official_blender_mcp_distribution.py scripts/requirements)"
test -d "$DISTRIBUTION_ROOT/.agents"
test -d "$PLUGIN_ROOT"
TRUSTED_CHECKSUMS="$(mktemp "$TRUST_PARENT/SHA256SUMS.XXXXXX")"
chmod 600 "$TRUSTED_CHECKSUMS"
git -C "$DISTRIBUTION_ROOT" show \
  "$EXPECTED_DISTRIBUTION_COMMIT:plugins/blender-mcp-installer/artifacts/SHA256SUMS" \
  > "$TRUSTED_CHECKSUMS"
cmp "$TRUSTED_CHECKSUMS" "$BUNDLE_ROOT/SHA256SUMS"
(cd "$BUNDLE_ROOT" && shasum -a 256 -c "$TRUSTED_CHECKSUMS")
(cd "$DISTRIBUTION_ROOT" && ./scripts/checks.sh)
test -n "$PLUGIN_CREATOR_ROOT"
"$PYTHON_BIN" -I "$PLUGIN_CREATOR_ROOT/scripts/validate_plugin.py" \
  "$PLUGIN_ROOT"
~~~

Expected: fail-fast detached/commit/dirty/scoped-untracked/trusted-checksum gates, private worktree/checksum paths, repository checks, and validator pass before any plugin import. This is the same hook-free bootstrap used by Task 9, not a second implementation. Negative acceptance cases cover dirty installer script, scoped untracked file, redirected Git variables, hostile sitecustomize, replacement of the source script after the clean check, payload plus working SHA256SUMS at unchanged HEAD, and a source `post-checkout` sentinel hook that must never run; none can cause unreviewed code execution.

- [ ] **Step 3: Inventory bounded normal targets**

Confirm the absolute BLENDER_BIN, CODEX_BIN, UV_BIN, and PYTHON_BIN identities resolved before Step 2 before changing HOME. Run read-only inspect with normal environment to obtain selected executable's normal user-resources/config/userpref/extensions targets. Record closed images for normal Codex config, installer data/state roots, Blender userpref, installed mcp tree, Blender .cache/compat.dat, and every project .blend file under repository. Do not create a missing normal target.

Expected: canonical before-inventory JSON lives under disposable evidence directory, not normal state.

- [ ] **Step 4: Exercise empty isolated profile**

Create empty mode-0700 TEST_HOME, TEST_CODEX_HOME, BLENDER_USER_RESOURCES, BLENDER_USER_CONFIG, and BLENDER_USER_EXTENSIONS, with config/extensions beneath resources. Do not copy userpref.blend. Set CLEAN_PATH to dirname UV_BIN plus /usr/bin:/bin:/usr/sbin:/sbin.

~~~bash
TEST_HOME="$(mktemp -d /private/tmp/blender-mcp-profile.XXXXXX)"
chmod 700 "$TEST_HOME"
EVIDENCE_DIR="$TRUST_PARENT/evidence"
mkdir "$EVIDENCE_DIR"
chmod 700 "$EVIDENCE_DIR"
INSTALL_JSON="$EVIDENCE_DIR/install.json"
TEST_CODEX_HOME="$TEST_HOME/.codex"
BLENDER_USER_RESOURCES="$TEST_HOME/blender-resources"
BLENDER_USER_CONFIG="$BLENDER_USER_RESOURCES/config"
BLENDER_USER_EXTENSIONS="$BLENDER_USER_RESOURCES/extensions"
mkdir "$TEST_CODEX_HOME" "$BLENDER_USER_RESOURCES" \
  "$BLENDER_USER_CONFIG" "$BLENDER_USER_EXTENSIONS"
chmod 700 "$TEST_CODEX_HOME" "$BLENDER_USER_RESOURCES" \
  "$BLENDER_USER_CONFIG" "$BLENDER_USER_EXTENSIONS"
CLEAN_PATH="$(dirname "$UV_BIN"):/usr/bin:/bin:/usr/sbin:/sbin"
~~~

Run each command with all five explicit profile variables. First inspect and assert Blender-reported user/config/extensions plus every managed target are descendants of the declared disposable roots:

~~~bash
env HOME="$TEST_HOME" CODEX_HOME="$TEST_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" inspect --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
env HOME="$TEST_HOME" CODEX_HOME="$TEST_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" install --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access \
  --allow-localhost-bridge --approve-arbitrary-python > "$INSTALL_JSON"
RECEIPT_PATH="$("$PYTHON_BIN" -I -c 'import json,sys; from pathlib import Path; p=json.load(open(sys.argv[1])); assert type(p) is dict and set(p)=={"command","changed","no_op","bundle_version","receipt","requires_blender_start"}; assert p["command"]=="install" and p["changed"] is True and p["no_op"] is False and p["requires_blender_start"] is True; r=Path(p["receipt"]); root=Path(sys.argv[2])/".local/state/blender-mcp-installer/receipts"; assert r.is_absolute() and r.parent==root and r.name.endswith(".json"); print(r)' "$INSTALL_JSON" "$TEST_HOME")"
test -f "$RECEIPT_PATH"
~~~

The closed install JSON binds RECEIPT_PATH before any verify/rollback. Start selected Blender normally in a separate terminal with the same explicit environment:

~~~bash
env HOME="$TEST_HOME" CODEX_HOME="$TEST_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$BLENDER_BIN"
~~~

With GUI open, run verify and then install again:

~~~bash
env HOME="$TEST_HOME" CODEX_HOME="$TEST_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" verify --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" --receipt "$RECEIPT_PATH"
env HOME="$TEST_HOME" CODEX_HOME="$TEST_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" install --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access \
  --allow-localhost-bridge --approve-arbitrary-python
~~~

Require live layer PASS and no_op=true with same receipt, no new generation/action/stage/backup, and identical targets. Close Blender normally, then:

~~~bash
env HOME="$TEST_HOME" CODEX_HOME="$TEST_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" rollback --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" --receipt "$RECEIPT_PATH"
~~~

Require original empty/config-fixture state.

The fake-host suite remains exhaustive. The real clean profile runs only one representative Blender-specific post-publication crash in a fresh isolated profile:

~~~bash
CRASH_HOME="$TRUST_PARENT/crash-home"
CRASH_CODEX_HOME="$CRASH_HOME/.codex"
CRASH_BLENDER_USER_RESOURCES="$CRASH_HOME/blender-resources"
CRASH_BLENDER_USER_CONFIG="$CRASH_BLENDER_USER_RESOURCES/config"
CRASH_BLENDER_USER_EXTENSIONS="$CRASH_BLENDER_USER_RESOURCES/extensions"
mkdir "$CRASH_HOME" "$CRASH_CODEX_HOME" \
  "$CRASH_BLENDER_USER_RESOURCES" "$CRASH_BLENDER_USER_CONFIG" \
  "$CRASH_BLENDER_USER_EXTENSIONS"
chmod 700 "$CRASH_HOME" "$CRASH_CODEX_HOME" \
  "$CRASH_BLENDER_USER_RESOURCES" "$CRASH_BLENDER_USER_CONFIG" \
  "$CRASH_BLENDER_USER_EXTENSIONS"
set +e
env HOME="$CRASH_HOME" CODEX_HOME="$CRASH_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$CRASH_BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$CRASH_BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$CRASH_BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$PYTHON_BIN" -I "$DISTRIBUTION_ROOT/tests/distribution/fault_driver.py" \
  --point after_extension_tree_publish \
  --fixture-kind extension_tree --preimage absent -- install \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access \
  --allow-localhost-bridge --approve-arbitrary-python
CRASH_STATUS=$?
set -e
test "$CRASH_STATUS" -eq 70
CRASH_RECEIPT_PATH="$("$PYTHON_BIN" -I -c 'import json,sys; from pathlib import Path; root=Path(sys.argv[1])/".local/state/blender-mcp-installer"; a=json.load(open(root/"active.json")); assert type(a) is dict and set(a)=={"schema_version","generation","install_id","receipt_basename"} and a["schema_version"]==1; r=root/"receipts"/a["receipt_basename"]; p=json.load(open(r)); assert p["status"]=="prepared"; xs=[x for x in p["actions"] if x["kind"]=="extension_tree"]; assert len(xs)==1 and xs[0]["state"]=="published"; print(r)' "$CRASH_HOME")"
test -f "$CRASH_RECEIPT_PATH"
env HOME="$CRASH_HOME" CODEX_HOME="$CRASH_CODEX_HOME" \
  BLENDER_USER_RESOURCES="$CRASH_BLENDER_USER_RESOURCES" \
  BLENDER_USER_CONFIG="$CRASH_BLENDER_USER_CONFIG" \
  BLENDER_USER_EXTENSIONS="$CRASH_BLENDER_USER_EXTENSIONS" PATH="$CLEAN_PATH" \
  "$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" install --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access \
  --allow-localhost-bridge --approve-arbitrary-python
~~~

Assert the driver reports the requested point was hit, its process exits exactly 70 before recovery, and normal retry completes with no orphan stage or normal-profile change.

Expected: install, verify, exact no-op, rollback, and the one real extension-publication recovery pass; no project .blend path appears in mutator log.

- [ ] **Step 5: Re-inventory normal targets**

Repeat Step 3 inventory and compare canonical JSON.

Expected: byte-for-byte equality. Any normal-profile or project difference fails implementation gate.

- [ ] **Step 6: Write local report, canary procedure, and verify GREEN**

Second-Mac procedure: obtain separate Darwin arm64 host/operator; obtain EXPECTED_DISTRIBUTION_COMMIT from reviewed release channel; run the identical fail-fast external trust bootstrap to create the private commit-derived tree and checksums; resolve absolute Codex/Blender/uv plus local Python 3.13 without downloads; create explicit BLENDER_USER_RESOURCES/config/extensions; install/discover the trusted repository marketplace; provide four fresh consents; run inspect/install with artifacts bundle root and required `--codex`; start selected Blender normally with exact profile variables; run verify; close normally; run no-op/rollback; return redacted host/version/receipt/hash evidence. Authenticated codex exec is optional and separately reported. End section with:

~~~text
SECOND_MAC_CANARY_STATUS: NOT_RUN
Reason: no separately supplied release-canary host/operator in this implementation session.
~~~

Also record LOCAL_LLM_INVOCATION_STATUS as PASS only with independent disposable-auth invocation evidence; otherwise leave NOT_RUN. Do not change second-Mac status without returned evidence. Change IMPLEMENTATION_GATE to PASS only when Steps 2-5 pass, then rerun the Step 1 Python command.

Expected: exit 0 while SECOND_MAC_CANARY_STATUS remains NOT_RUN.

- [ ] **Step 7: Commit local acceptance report**

~~~bash
git add docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md
git commit -m "docs: record local Blender MCP distribution gate"
git status --short --branch
~~~

Expected: audit-only commit and clean implementation worktree. No second-host evidence is fabricated.

## Self-Review Checklist

- Every production interface is introduced before cli.py uses it.
- Manifest, lock, host-path, image, journal, receipt, pending/active-selector, Codex-owned-key, Blender-state, and CLI result schemas are closed.
- External trust is established before plugin add/import; only the private commit-derived plugin runs under isolated Python startup.
- Every CLI/fault-driver path requires and forwards the validated absolute Codex executable.
- Active-selector and Codex semantic rollback plus installed cleanup have exact crash/retry states and applicable failpoints.
- Missing consent, no-op, runtime/Blender/Codex transactions, read-only inspect/verify, every mutation failure/crash, prepared recovery, and rollback conflict have named pytest cases and exact commands.
- install never starts Blender; verify is the live four-layer gate.
- Repository marketplace is exercised locally; plugin is skill-only and configures official wheel as local STDIO.
- V1 uses reviewed Git/release transport plus SHA-256 integrity, exact network wheels, no sdists, no signing system, and no wheelhouse.
- Second-Mac procedure is documented, non-blocking, and NOT_RUN until operator evidence exists.

## References

- docs/superpowers/specs/2026-08-09-official-blender-mcp-llm-install-design.md
- docs/install-official-blender-mcp.md
- docs/audits/2026-08-16-official-blender-mcp-r22-live-acceptance.md
