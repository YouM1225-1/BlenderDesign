# Official Blender MCP Distribution: Local Acceptance

Date: 2026-08-17 (Asia/Shanghai)

IMPLEMENTATION_GATE: PASS

LOCAL_LLM_INVOCATION_STATUS: NOT_RUN

Reason: no independent disposable Codex credential was supplied. Normal credentials were
neither copied nor used for an authenticated model invocation.

SECOND_MAC_CANARY_STATUS: NOT_RUN

Reason: no separately supplied release-canary host/operator was available in this
implementation session.

## Scope and result

The local Darwin arm64 clean-profile gate passed. The tested distribution installed the
official Blender MCP bundle into an empty profile, passed the four-layer live gate, was an
exact no-op on repeat installation, rolled back to its original image, and recovered from
one real post-publication crash. The bounded normal-profile and project inventory was
byte-identical before and after.

The original full-lifecycle reviewed implementation commit was
`660163365127bcc32c310bff50a01be66285dcf0`. The acceptance began from the last complete
repository-gate capture at `b470dcc4d931b3e455fecd57d9a2488897ca3f43` and then exercised
the final rollback correction from a fresh, commit-derived trust root against the same
preserved installed profile. That final correction had independently completed its exact
directed tests (9 passed), focused suite (257 passed), full distribution suite (734 passed),
Ruff, formatting, mypy, and clean-diff gates before the preserved-profile rollback.

Evidence was retained under the mode-0700 disposable directory
`/private/tmp/blender-mcp-task10-evidence.enzkXO`. It contains metadata and closed command
results, not copied normal credentials.

## Final Execution Audit Remediation Gate

FINAL_EXECUTION_AUDIT_REMEDIATION_GATE: PASS

The post-audit reviewed implementation is
`7e81cb7a8305cf5ac6389dffd8590fe4ace22879`; the aligned workflow-document commit exercised
by this gate is `40c34d5b18fe0529032c3183fffbadf53ea5fba3`. From that exact commit, the current Skill's
literal `TRUST_BOOTSTRAP`, `UV_BOOTSTRAP`, and public `inspect` blocks created a fresh private
trusted tree and ran this redacted ordinary-profile command shape in the same fail-fast shell:

```bash
env -i HOME="$SYSTEM_ACCOUNT_HOME" PATH="$SANITIZED_PATH" \
  SOURCE_DISTRIBUTION_ROOT="$REVIEWED_SOURCE" \
  EXPECTED_DISTRIBUTION_COMMIT=40c34d5b18fe0529032c3183fffbadf53ea5fba3 \
  BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
  CODEX_BIN=/Applications/ChatGPT.app/Contents/Resources/codex /bin/bash
# CODEX_HOME and all BLENDER_USER_* variables omitted
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync python -I -B -c "$ISOLATED_RUNNER" \
  "$PLUGIN_ROOT/scripts" "$PLUGIN_ROOT/scripts/install.py" inspect \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
```

The real host identities were Blender 5.2.0 LTS, Codex 0.148.0-alpha.9, uv 0.12.2, and
CPython 3.13.13. `inspect` exited 0 and emitted exactly one closed JSON object with
`command=inspect`, `managed_target_count=5`, `active_install_id=null`, and no stderr. Its
stdout SHA-256 is `9648b922012dc6b266b21f537f692ec2651174ac155b7795738761a924c74570`.
The trusted Skill SHA-256 was
`ce2261da9585e8da2133149ec42ec1e1661fd940f3c73e807fe5d4804c575f74`.

Blender's factory discovery reported the normal system-account resources, config, and
extensions roots under `$HOME/Library/Application Support/Blender/5.2`; the normalized
discovery evidence SHA-256 is
`ab44be33af0bb62a6399bf036a7c888b457bfd0d0c3ab13ba419c3db0ecb2cd7`.
The 55-entry bounded byte inventory covered the normal Codex config, installer state and
data, those discovered Blender roots, `userpref.blend`, the managed extension tree,
`compat.dat`, and repository `.blend` files. Before and after were byte-identical with
SHA-256 `0bb2bd42dc5133b0d21332b4c7472690a30df4582ca7bb654223013a8553f712`.
Source bytecode inventory was also identical before and after; the source and trusted-tree
Git status captures were empty, the trusted tree and evidence directory gained no bytecode,
and no Blender process or localhost:9876 listener remained.

Evidence is retained under the mode-0700 directory
`/private/tmp/blender-mcp-final-home-only.3491qA`; normal paths inside evidence are expressed
as `$HOME`/`$PROJECT_ROOT` logical targets rather than copied credentials. An initial
disposable-HOME preflight intentionally failed before public `inspect`: on this macOS host,
Blender factory discovery continued to return the system-account roots. The preflight
normal-profile/project inventories were nevertheless identical before and after (SHA-256
`08b382fc0bf33836b465f67c68fd39369b9a9048effe0985111df6e97ea61ada`), so the acceptance
assumption was corrected to the ordinary-profile gate above without a profile mutation.
No install, GUI launch, listener, or authenticated LLM invocation occurred in this
post-audit gate. `LOCAL_LLM_INVOCATION_STATUS` and `SECOND_MAC_CANARY_STATUS` therefore
remain `NOT_RUN`.

## Trust and repository gates

- The exact current Task 9 skill was read once and SHA-256-bound as
  `10d5be8b230e8062398be9711469e430544d4b1e27e4f180142c4d2e6ddbbe8b`.
- Each resumed mutation used the skill's literal `TRUST_BOOTSTRAP_BEGIN/END` private-admin
  bootstrap and a fresh detached, hook-free, commit-derived tree. The obsolete duplicate
  Git bootstrap in the Task 10 draft was not run; this is the intended Task 9 alignment.
- The first real `inspect` emitted one closed JSON object, no Git stdout, and no trusted-tree
  bytecode. Installer entry points ran with isolated Python and `-B`.
- The last complete Task 10 repository capture passed `369` repository checks and `726`
  distribution tests, plus plugin and skill validators. The final-head correction gates are
  recorded above rather than rerunning the already-green multi-minute full suite.
- The closed fake-host failure/crash matrix contained `143` cases.
- The disposable Codex marketplace smoke installed and enabled
  `blender-mcp-installer@personal` version `1.0.0` from the trusted local marketplace.

## Host and artifact identities

| Item | Accepted identity |
| --- | --- |
| Host | macOS 26.5.2 (25F84), Darwin arm64 |
| Blender | `/Applications/Blender.app/Contents/MacOS/Blender`, 5.2.0 LTS |
| Codex | `/Applications/ChatGPT.app/Contents/Resources/codex`, 0.148.0-alpha.9 |
| uv | `/Users/yeminjie/.local/bin/uv`, 0.12.2 |
| Python | repository `.venv/bin/python3`, CPython 3.13.13 |

The reviewed `SHA256SUMS` matched the bundle. Sizes are bytes.

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `manifest.json` | 2,104 | `2b799aff562693ce0b79e9df4737158b4b785e5c854e39673a289192adaf4a60` |
| `blender_mcp-1.0.0-py3-none-any.whl` | 5,611,449 | `f3f0e8a98f7f28d275c1169b768bcdf051aa46e0d17333bb08718041dd9a89c2` |
| `mcp-1.0.0.zip` | 16,842 | `2a2ae48501889c714c8b44f0d93c542c738ec36c23f88d109d8542aac6927025` |
| `runtime-requirements.lock` | 45,155 | `5133f4c4ca9ab5e48c1775548ca98fe914f722dfbf236cfae7047c1c2e117423` |

## Clean-profile lifecycle

The mode-0700 empty profile was
`/private/tmp/blender-mcp-task10-evidence.enzkXO/clean-home`. All five managed targets and
Blender's reported resources, config, and extensions were descendants of that root; no
normal profile content was copied into it.

1. `inspect` reported no active install and exactly five managed targets.
2. `install` returned closed JSON with `changed=true`, `no_op=false`, bundle version
   `1.0.0+482c540395ad`, and receipt
   `497fa7f7-ba19-45d6-a68d-39368d40a8d8.json`. Its installed-state SHA-256 was
   `c32f23007727426dd217584ce5b8ab0a2482d764786672370f02a2b1b2eaad20`.
3. Blender started normally with the same five explicit profile variables. PID 98266 owned
   the sole `127.0.0.1:9876` listener.
4. A first read-only live probe met a listener-readiness race. The prescribed bounded retry
   succeeded on attempt 1 after relaunch: parsed Codex, effective Codex, MCP catalog, and
   Blender read-only were all `true`, with 26 tools. No managed state changed during retry.
5. A GUI-open second `install` returned the same receipt with `changed=false` and
   `no_op=true`; the before/after target images were byte-identical (SHA-256
   `cb217c2a6004aea256e97903004b8a8a05ec19831fa728e209910e74af4ca65e`).
6. Blender exited normally with process status 0 and the listener disappeared. The separate
   AppleScript quit request returned localized status -128 after the process had exited; it
   did not leave Blender or a listener running.
7. Final-head rollback completed in 7 seconds and returned `status=rolled_back`, restoring
   runtime, extension, user preferences, and Codex config. It removed only the two new,
   source-mapped live cache files and preserved the four recorded baseline cache files for
   exact comparison. The post-rollback managed image was byte-identical to the initial
   image (SHA-256
   `bd6fe6ad324200ac7af40611ad4213cad026b20e18fd33230a4fe3baca1febc8`).
   The final rolled-back receipt SHA-256 was
   `869fc79c8a0f571734032e5f71118c9dd5f87453fea875fb6ef10e24d19cb7f8`.

After rollback, active and recovery selectors were absent; runtime and extension targets
were restored to their initial absence; receipt stage and backup directories were empty.

## Real crash and fresh-process recovery

The representative real fault point was `after_extension_tree_publish` in a second empty
mode-0700 profile. The driver reached the requested point and exited exactly `70`. Before
recovery, its receipt was `prepared` and the extension action was `published`. A fresh
normal `install` recovered that receipt to `rolled_back`, created receipt
`8508ab2f-1c9b-42b2-9043-44d9f4f5a6ff.json`, and left no active selector, recovery file, or
non-empty stage. Rolling back the recovered installation also returned closed JSON with
`status=rolled_back` and restored all four managed roles.

## Normal-profile and project isolation

The read-only inventory covered 36 bounded targets: normal Codex config, installer data and
state, Blender user preferences, the installed MCP extension tree, Blender cache metadata,
and every repository `.blend` project. Missing targets were not created. Canonical before
and after JSON were byte-for-byte identical, both with SHA-256
`78dc5676b844b9f53f1a08a31c5eef76830127f7fa04efbc948d25eb4fe7ed81`.
No normal-profile or project path appeared in a mutator scope.

## Separate-host canary procedure

On a separately owned Darwin arm64 host, obtain the reviewed 40-hex commit through the
release channel; run the same Task 9 private, hook-free trust bootstrap; resolve absolute
Blender, Codex, uv, and offline-capable Python 3.13 executables; and create an empty explicit
HOME/CODEX_HOME/Blender resources-config-extensions profile. Discover and install the
trusted local marketplace plugin, provide the four fresh consents, then run
inspect/install, launch the selected Blender with the exact profile, run verify, repeat
install for exact no-op, close Blender normally, and rollback. Return redacted host,
version, artifact, receipt-hash, inventory, and closed-result evidence. An authenticated
Codex invocation is optional and must use independently disposable credentials.

SECOND_MAC_CANARY_STATUS: NOT_RUN

Reason: no separately supplied release-canary host/operator in this implementation session.
