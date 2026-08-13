# Official Blender MCP R3 exception diagnostics and one-shot retest

> Status: candidate. Do not execute product or Blender steps until three fresh Plan
> reviews bind the same bytes and report Critical/Important/Minor = 0/0/0, and the
> resulting Plan-only commit is the clean current HEAD.

## Outcome and success criteria

Task 7 stopped correctly after two actual R2 controller runs failed before the first MCP
tool call. Both retained only the top-level text `ExceptionGroup: unhandled errors in a
TaskGroup (1 sub-exception)` and the same SHA-256
`964e32d540eb4c805fef83232636cd2fad8612873cf8092430bf8ad840c2add2`.
That equality is not root-cause evidence: the current controller hashes only the
top-level type and message, and an in-memory mechanical reproduction gives the same
digest for groups whose leaves are respectively `ConnectionRefusedError` and
`BrokenPipeError`.

This follow-up has one narrow goal: make a generic direct-session failure retain its
ordered recursive exception tree and bounded stderr before requesting the failure ACK,
then authorize exactly one new actual controller run. Success is either:

1. the run reaches `VISUAL_ACK_REQUIRED`, every ordered PNG receives the user's explicit
   option-C pass/fail decision in the same live PTY, all tools and validators pass, the
   audit-only commit is reviewed, and the clean full gate reports exactly 369 tests; or
2. the single run reaches a generic direct-session failure, leaves a mechanically
   validated leaf-complete tree within the declared root-zero maximum edge-depth
   16/256-node bound (at most 17 levels) plus bounded
   stderr and a valid journal, cleans up owned processes, passes independent failure-
   evidence review, records `STATUS: BLOCKED`, and stops without another attempt.

Every other preflight/live failure still fails closed and stops without retry, but is
reported as unverified BLOCKED rather than being misrepresented as either success.

## Frozen state and red lines

Run from `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install`
on branch `codex/official-blender-mcp-install`.

- Current clean HEAD: `1d454dd4a9eedde0652be2467bec2f7fe1e145c1`.
- Frozen R2 controller:
  `.superpowers/sdd/modeling-remediation/final-retest-r2/attempt-0009/r2_controller.py`,
  dev `16777232`, ino `295510972`, mode `0600`, nlink `1`, 6,193 lines, 254,319 bytes,
  SHA-256 `cc325e471aa0d1a0349deade58d0f7517575c35d901fb99f00ee1cc4de7f640a`.
- Frozen blocked Task 7 report:
  `.superpowers/sdd/modeling-remediation/task-7-report.md`, dev `16777232`,
  ino `295274949`, mode `0600`, nlink `1`, 7,856 bytes,
  SHA-256 `cf42c8ff5bebd49aa8f8213bb787fa3b9f3d6669d61f2b8924e424556f2b9f04`.
- Frozen R2 journals: attempt-0008 SHA-256
  `b86d30fd8954e4610017904b5411237d92796dd74d7b31395deb146dbe35c95e` and
  attempt-0009 SHA-256
  `5a7a4febe8c14fa364056cfb3ef29951dfdfa543775febf76c64c09561a59cc7`.
- Current runbook: `docs/use-official-blender-mcp.md`, 425 lines, 21,493 bytes,
  SHA-256 `39b2665064ee8e1be72bb73318a60a46b467c01da636eed4dab5c05945c6d610`.
- Certified parent Plan SHA-256:
  `397a57590121f67e5abbe62aac76efb42418b2f66a72bcba3277ada176395ff2`.
- Continuation baseline r3 SHA-256:
  `431b9175cc13f32283b49a609736914ae963adeb7741c46f63814cd323afce89`.

Red lines:

1. Never modify, unlink, rename, replace, truncate, chmod, or reuse any R2 attempt,
   `task-7-brief.md`, or `task-7-report.md`.
2. Do not touch main or its dirty user-owned files. Do not merge, rebase, reset, amend,
   stash, hide status entries, or use an alternate index.
3. Before the certified Plan-only commit, do not edit the runbook/audit, start Blender,
   start a listener, or create `final-retest-r3`.
4. Only the runbook and, after a successful live run, the modeling audit may become
   tracked product diffs. Do not modify tests, helpers, MCP source, config, P6, or the
   old Plan.
5. All temporary roots are native owned mode-0700 under `/private/tmp`; set
   `PYTHONDONTWRITEBYTECODE=1`; use the absolute UV executable
   `/Users/yeminjie/.local/bin/uv` and Python 3.13.
6. The R3 controller is generated only from the exact frozen R2 bytes by Appendix A.
   No hand edits are allowed.
7. The follow-up brief/report are allocated before GUI preflight so every terminal that
   retains its bound writer is durable. Loss of that writer is itself fail-closed and is
   mechanically represented by the missing unique terminal lines; it cannot be reported
   as PASS or certified evidence. The R3 evidence root is allocated only after preflight
   passes. Any later deviation is terminal for this follow-up.
8. Exactly one actual `r3_controller.py run` is allowed. Probe/fixture/validate commands
   are not actual runs. There is no R3 retry or attempt-0002.
9. At `VISUAL_ACK_REQUIRED`, the implementer must not view, judge, construct, or type
   an ACK. It reports the live PTY plus every ordered absolute PNG path/SHA-256 and
   stops. The controller presents every image to the user and types only the user's
   explicit per-image verdict into that same PTY.
10. A live failure gets its exact ACK and cleanup, but never a guessed diagnosis. A
    grouped generic direct-session failure without both new evidence files and the
    accepted-ACK marker, or whose tree exceeds the declared capture bound, is a hard
    implementation failure rather than valid root-cause evidence.

## Task 1: certify and commit this Plan only

Controller records this candidate's absolute path, line count, byte count, SHA-256,
current HEAD, branch, clean-status expectation, and every frozen identity above. It
exclusive-creates three ignored native-0600 reports in a fresh
`.superpowers/sdd/modeling-remediation/r3-plan-review/` directory and dispatches three
fresh independent reviewers against the same immutable candidate bytes:

- spec/safety: contracts, option C, ownership, stop states, evidence completeness;
- execution/state machine: run every safe probe, mutation, selector, and transition in
  disposable fixtures;
- Ponytail/YAGNI: find redundant machinery, stale retry lanes, or simpler safe fixes.

Each reviewer may write only its preallocated report through the original bound file
descriptor. The controller rechecks Plan identity after all three return and accepts
only exact standalone verdict counts `Critical: 0`, `Important: 0`, `Minor: 0` plus
`SPEC_VERDICT: PASS`. Any finding burns the round; amend only this Plan, allocate three
new report names, and repeat with fresh reviewers. Never ask a reviewer to approve its
own correction.

Only after one round is 0/0/0, commit exactly this Plan:

```bash
/bin/bash -euo pipefail <<'BASH'
PLAN=docs/superpowers/plans/2026-08-13-official-blender-mcp-r3-exception-diagnostics.md
test "$(git rev-parse HEAD)" = 1d454dd4a9eedde0652be2467bec2f7fe1e145c1
test "$(git status --short --untracked-files=all)" = "?? $PLAN"
git diff --check -- "$PLAN"
git add -- "$PLAN"
test "$(git diff --cached --name-only)" = "$PLAN"
git diff --cached --check
git commit -m "docs: plan leaf-complete MCP failure diagnostics"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git diff-tree --no-commit-id --name-only -r HEAD)" = "$PLAN"
BASH
```

## Task 2: patch the runbook and prove the diagnostic controller

Use one fresh implementer. First recheck clean certified-Plan HEAD plus every frozen
R2/report/runbook identity. Apply only this exact runbook insertion after the existing
paragraph ending `掩盖 partial state。`:

```markdown
`same failure` 必须按 canonical recursive exception tree 判定：记录每个 exception/group
的 module-qualified type、完整有界 message 和有序 child tree；不得只哈希顶层
`ExceptionGroup` 摘要。direct MCP session 在请求 failure acknowledgement 前，必须先
exclusive-create 并 fsync `direct-session-failure.json` 与 bounded
`direct-session.stderr`，把 exception-tree SHA-256、stderr observed/retained bytes、
digest、truncation 和 drain error 绑定进 acknowledgement identity。缺少这些证据的
grouped exception 只能证明 controller fail-closed，不能证明两个底层失败相同。
tree capture 以 root depth 0 计最多 16 条 parent→child 边（最多 17 个层级）、256 节点；超限必须显式记录 truncated，且不得据此声明
leaf-complete 或 same failure。
```

The amended runbook must be exactly 435 lines, 22,329 bytes, SHA-256
`658c1b20ff9569f05f32a699d3dcbd496201be30fc96efaa538d4e808f26136c`.

In a disposable mode-0700 `/private/tmp` root, extract Appendix A, verify its declared
identity, compile it in memory, and run it against the exact frozen
R2 controller. The output must be 6,924 lines, 285,387 bytes, SHA-256
`7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a`.
Then run:

```bash
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR=/private/tmp
UV_BIN=/Users/yeminjie/.local/bin/uv
UVX_BIN=/Users/yeminjie/.local/bin/uvx
"$UV_BIN" run --python 3.13 python - "$TMP_R3/r3_controller.py" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
compile(path.read_bytes(), str(path), "exec")
PY
"$UVX_BIN" --quiet ruff@0.16.2 check --no-cache --isolated \
  --target-version py313 --select E4,E7,E9,F "$TMP_R3/r3_controller.py"
"$UV_BIN" run --python 3.13 python "$TMP_R3/r3_controller.py" probe
test ! -e "$TMP_R3/__pycache__"
```

Expected exact markers:

```text
R3_FAILURE_DIAGNOSTICS_GREEN distinct=2 ordered=1 persisted_before_ack=1
R3_PROTOCOL_R20_1_GREEN positive=6 negative=85
```

Run two non-no-op mutations in separate disposable copies and require every probe to
exit nonzero:

1. inside the unique `production_exception_tree` function slice, replace the unique
   `if isinstance(current, BaseExceptionGroup)` with
   `if False and isinstance(current, BaseExceptionGroup)`;
2. replace the unique call to `production_persist_direct_failure` inside
   `production_close_direct_or_deviation` with fixed dummy response/symptom values.

For each mutation, assert the target count is exactly one, bytes changed, Python still
compiles in memory without `__pycache__`, and the probe is RED. This proves the old
top-level collision and ACK-before-evidence lanes cannot pass by deletion. The positive
probe also covers deep/wide bounds, hostile message rendering, split UTF-8 retention,
a long symptom retaining its evidence SHA, safe nonempty generic fallback identity,
both evidence files, stderr drain liveness, exact stderr digests, all-pass/one-fail
visual ACK parsing, the run-ticket allowlist, authorized ticket/catalog creation without
self-invalidating cached inputs, and cached-leaf drift rejection.
It also starts a harmless disposable audit-script harness through the exact production
`uv run ... record --output ...` argv, proves executable/full argv/start-time/UID/stdin-
FIFO inode binding GREEN, and requires a wrong start time, wrong `uv` identity, a live
substring impostor carrying the expected tokens, wrong executable image, same-path FIFO
replacement, and a dead former recorder PID to be RED; the replacement case also proves
no run ticket exists. The production slice must repeat the frozen audit-FD/FIFO/recorder
identity checks immediately before the unique ticket create.

Also parse the generated file's unique `production_run` source slice and assert this
strict textual order: audit-FD range/open check; raw absolute-path rejection;
audit-FIFO/path binding; root/controller SHA; scratch; canonical
feature/Codex/config validation; bound recorder PID/start/UID/executable/full-argv/stdin-
FIFO validation;
config/source/git reads; all four fixture reads and
`known-missing.png` absence; unique `create_owned(root, "run-ticket.json"...)`; then
unique `production_app_catalogs`; then `ProductionBoundedStderr` and `stdio_client`.
Delete or move the ticket call ahead of any one precondition in disposable copies and
require this order check RED. Thus a typo/missing input cannot consume the one-shot
ticket, while the ticket still precedes every App/direct-session side effect.

Extract Appendix B exactly, verify its declared identity, and compile it in memory. In a
disposable `final-retest-r3/attempt-0001`, use the generated controller helpers to write
one bounded group with one leaf failure JSON/stderr pair, exact `run-ticket.json`, exact
`direct-failure-ack.json`, plus a four-row
nested task/stage failure journal with UUIDv4 clock, increasing monotonic/UTC timestamps,
exact row fields, and a symptom containing the exact JSON payload SHA. Appendix B emits exactly
one JSON object with `status: failure_evidence_valid`. In four separate copied fixtures,
mutate (a) one retained stderr byte, (b) the exception-tree digest, (c) the final journal
symptom's evidence SHA, and (d) the expected controller SHA argument; assert each
mutation is non-no-op and Appendix B exits nonzero. Also replace the validator's unique
`value["truncated"] is not False` guard with `False`; run it against a truncated deep
tree and require RED from independent node schema/count checks. Add three journal RED
fixtures for null clock, malformed/nonmonotonic UTC, and an extra row key; add ticket
missing/tampered, plain-leaf tree, false message/stderr truncation, empty issue IDs, and
duplicate event-ID RED. Also require RED for a bare/unqualified or lookalike group type,
a non-group node carrying children, and any fifth call row: certified evidence is the
exact four-row failure before the first tool call. Require self-consistent rehashed RED
fixtures for a JSON integer in any SHA field, a non-qualified render-error type, a
truncated message retaining fewer than exactly 8,192 bytes, and truncated stderr
retaining fewer than exactly 4 MiB. Missing, malformed, or evidence-SHA-mismatched
`direct-failure-ack.json` must also be RED. No validator probe may create
`__pycache__` or touch durable evidence. In instrumented disposable validator copies,
inject (1) a same-mode replacement between pre-stat and descriptor open, and (2) a
chmod or added hard link after open but before the final stat; both must be non-no-op
and RED. In a third copy, mutate a previously read evidence leaf only after the last
`owned()` call but before the unique `recheck_all()`; the package-wide final recheck
must make it RED. The positive fixture must remain GREEN through the descriptor-bound
reader and final package recheck.

Extract Appendix C, verify its declared identity, compile it in memory, create one fresh
owned mode-0700 `/private/tmp` output directory, and run it against the exact frozen Task
7 brief with output `<that-directory>/protocol.md` (never under attempt-0001). Verify the
exact 820/36,189/output-SHA identity and compile all seven embedded Python heredocs.
Assert exactly four paired top-level Bash fences and require `/bin/bash -n` zero for
each. Extract every single-quoted `<<'PY'` body from those fences (exactly seven), compile
each in memory with uv Python 3.13, and execute the standalone ticket parser against
canonical, missing, symlink, duplicate-key, equivalent-noncanonical, and 4,097-byte
fixtures; only canonical returns count one. Require the run fence to contain exactly one each of `--audit-fd 9`,
`--audit-fifo "$EVENT_FIFO"`, `--recorder-pid "$RECORDER_PID"`,
`--recorder-start "$RECORDER_START"`, `--recorder-uv-bin "$UV_BIN"`, and
`--recorder-mcp-editable "$MCP_SOURCE_DIR/mcp"`; require the
recorder-close/validate/finalize
continuation to occur only in the following separate fence. Outside the three frozen
R2 marker names, reject any executable `R2_`, `r2_`, `r2-`, old
report path, retry/start-new-attempt text, or `r2_controller.py`. Mutate one source-slice
byte and one output identity constant in separate copies; both must exit nonzero before
creating an accepted protocol.
From a copied protocol, extract the unique `r3_report_append` function and its delayed
FD-8 bind block. In a disposable native-0600 report, require one two-line append to keep
the original inode/mode/nlink, fsync the exact bytes, and increase size exactly; replace
the report path with a new same-mode inode before a second append and require RED with no
bytes written to either inode. Also assert FD 8 is first opened only in the post-run
continuation, after controller and recorder completion. Only the two bounded report
identity/append helpers receive it explicitly; instrumented validate/finalize and every
other child must observe FD 8 closed.
In disposable shell fixtures, exercise the exact cleanup fence with inherited errexit,
an unreadable journal, a bound Blender PID whose listener socket has already closed, and
canonical/duplicate-key/equivalent-noncanonical ticket variants. Every secondary failure
must still kill/reap the bound PID and append a durable cleanup error plus exact count and
BLOCKED status; only the canonical ticket is count one. For both certifying branches,
prove the fence returns to the same live PTY with the original FD 8 open, accepts exactly
one matching `r3_finish_review` call, appends the correct PASS/BLOCKED terminal, and then
closes FD 8; wrong flow/kind/verdict and lost FD must be RED without a terminal append.
Also launch a harmless macOS process whose `lsof -d txt -F fDin` output contains its main
image plus dyld: the shared parser must select the requested main-image path and return
exactly its device/inode composite, accept that binding, and reject a wrong composite or a
same-PID replacement without signalling it.

Run `git diff --check`, verify the sole tracked diff is the runbook, commit it with
message `docs: require leaf-complete MCP failure evidence`, then on the same clean HEAD
run `./scripts/checks.sh`. Require exactly one `369 passed in ...` summary and exact
`ALL CHECKS PASSED`; recheck clean status and unchanged HEAD after the gate.

## Task 3: one durable R3 run

Before any GUI action, the controller exclusive-creates and externally binds:

- `.superpowers/sdd/modeling-remediation/task-7-followup-1-brief.md`;
- `.superpowers/sdd/modeling-remediation/task-7-followup-1-report.md`.

The brief binds the certified Plan commit, runbook commit and SHA, frozen R2 controller
and blocked report identities, Appendix A/B SHA values, the new report inode, and
`actual_run_limit=1`. The implementer may write only the bound report until preflight
authorizes R3 attempt evidence and a successful run later authorizes the modeling audit.

The allocator writes the brief as this Plan's complete Task 3 through Task 5 text,
preceded by the literal binding block below (values replace only angle-bracket fields):

```text
R3_PLAN_COMMIT=<the unique parent of the Task 2 runbook commit>
R3_PLAN_SHA256=<this exact Plan SHA256>
R3_RUNBOOK_COMMIT=<Task 2 clean HEAD>
R3_RUNBOOK_SHA256=658c1b20ff9569f05f32a699d3dcbd496201be30fc96efaa538d4e808f26136c
R3_GENERATOR_SHA256=42e20d1cc0a982580c89f44182e4dae85a897c2b07cbf106fab2f54157d361e4
R3_LIVE_GENERATOR_SHA256=828aaebc53cda2fe628d0730fd5ce4bf98da3222e883cea66b373315234c80ba
R3_LIVE_PROTOCOL_SHA256=6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2
R3_CONTROLLER_SHA256=7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a
R3_VALIDATOR_SHA256=791d4e0b49b79f279608fe04e8e46dc1cc0d8b5e9596c21b27adb4a58e015f84
R3_REPORT_DEV=<preallocated report device>
R3_REPORT_INO=<preallocated report inode>
ACTUAL_RUN_LIMIT=1
```

The allocator leaves the preallocated report empty. During work the implementer appends
only immutable fact lines through the original bound descriptor: `preflight: PASS|BLOCKED`,
`attempt_root: NONE|<absolute path>`, `ticket_sha256`,
`journal_sha256`, `owned_processes_after_cleanup`, and literal command output. It appends
exactly one `actual_run_count: 0|1` line followed by exactly one final
`STATUS: PASS|BLOCKED` line only after the applicable independent review process reaches
its terminal outcome: exact approval or any rejected, malformed, oversized, replaced,
drifted, crashed, or nonzero-exit state. A parser failure is terminal disapproval, not a
reason to omit the final BLOCKED lines; neither final line appears earlier.
Preflight/visual/persistence terminals that have no certifying
review append count plus BLOCKED only after cleanup. The allocator and final reader bind both files by
dev/ino/uid/mode/nlink/size/SHA through an original descriptor; the report is native
0600/nlink-1 and is never replaced. For either certifying branch, the implementer's same
live PTY and its original FD 8 remain open across independent review; losing either is
terminal disapproval and makes terminal-line absence the fail-closed signal; it never
authorizes a replacement writer or a PASS/certification claim. Only the generated
`r3_finish_review` function may append the review verdict, exact count, and terminal
status, then close FD 8.

The allocator proves `R3_RUNBOOK_COMMIT` has exactly one parent, binds that parent as
`R3_PLAN_COMMIT`, and requires its one-path diff to be exactly this Plan. It separately
requires the runbook commit's one-path diff to be exactly `docs/use-official-blender-mcp.md`.
Before pasting the generated live protocol, the controller copies the brief's exact
`R3_PLAN_COMMIT`, `R3_PLAN_SHA256`, `R3_RUNBOOK_COMMIT`, `R3_RUNBOOK_SHA256`,
`R3_REPORT_DEV`, and `R3_REPORT_INO` values as shell assignments into the same persistent
PTY. The protocol requires all six,
checks clean current HEAD/topology/path scopes and both on-disk SHA-256 values once at
the guarded preamble and again immediately before the sole `run`; any drift stops before
ticket acquisition.

### Exact Task 3 execution manifest

The immutable payload source is the existing
`.superpowers/sdd/modeling-remediation/task-7-brief.md`: dev `16777232`, inode
`295274948`, mode `0600`, nlink `1`, 13,076 lines, 538,571 bytes, SHA-256
`fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b`.
Lines 5,444–13,076 (SHA-256
`2119def3d937d9154109c578bca9e3fead71b30266489f084c486ac48a72dd59`)
are the frozen Appendix-F protocol source; lines 12,299–12,912 (SHA-256
`06940a887e30674eb0f0c3127aea2aafdc2c9d4031caeee6fbc21d6d6e64d0c0`)
are the guarded extraction/recorder/run source. Read them only through the same bounded
descriptor protocol as Appendix B. They supply the exact `fixture_setup.py`,
`model_body.py`, and `cli_body.py` marker payloads and GUI/recorder sequencing; their
payload identities remain respectively 57/2,288/
`b94433e1aea2d8087a0ebd4596a4cb2d19c04955086abcbf8ee388a989cd8681`,
368/14,604/`534f38477d968d8ae4262340b1f172d51cba25e206c86a6a41976071aa638034`,
and 33/944/`c358ad5ec7f30c8bdf7d7fae28ef1f71682d118b2b6dd462ac5ee522a7e241d2`.

The frozen source is never edited or executed verbatim. Appendix C is the sole exact
transformer: it verifies the full source and slice identities, removes the embedded R2
controller and retry lane, requires the Appendix-A controller already be the sole
attempt artifact, binds repository/Plan/runbook/brief identities, creates scratch before
the run, adds bound FIFO/recorder arguments, keeps FD 8 bound to the preallocated report,
and contains the exact success versus direct-review versus unverified-BLOCKED cleanup
continuation. Cleanup disables inherited errexit, accumulates every secondary error,
checks both the bound Blender PID and listener port after termination, and parses the
ticket through strict duplicate-key rejection plus exact canonical bytes. Its output
must be exactly 820 lines, 36,189
bytes, SHA-256
`6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2`.
The implementer follows only that generated protocol; its separated run fence is the
sole actual invocation, and no continuation bytes are sent until the authorized ACK.
Any executable R2 token outside the frozen payload-marker source bindings,
any output identity mismatch, or any pre-existing `attempt-0001` is a hard stop.

Preflight before allocating evidence:

1. Verify no task-owned Blender, listener, recorder, or controller process exists. Do
   not terminate unrelated host-owned processes.
2. Through visible GUI control, launch one exact factory-startup Blender, enable the
   already-installed official add-on, and start one listener. In visible Blender
   Console prove version 5.2.x, empty filepath, `is_saved=False`, OBJECT mode, exact
   `Camera/Cube/Light`, and display the session tempdir. Canonicalize the displayed
   `/var/...` value to `/private/var/...` outside Blender and require equality.
3. Prove the new listener is sole and differs from every retained prior listener. If
   any preflight condition fails, close only this preflight, record the observation and
   cleanup in the bound report with unique `STATUS: BLOCKED`, report it as unverified,
   and stop. Do not allocate R3 evidence; this does not consume the actual-run
   allowance, but there is still no retry inside this Plan.

Perform those steps while one fresh persistent `/bin/bash` PTY is already open. Before
any attempt/evidence allocation, set and export `R3_LISTENER_PID` to the sole verified
listener PID, `R3_LISTENER_START` to its exact `ps lstart`,
and the single `R3_LISTENER_IMAGE` composite to the device/inode from the unique
complete `lsof -d txt -F fDin` record whose path equals `BLENDER_BIN` (other `txt`
mappings such as dyld are allowed but ignored), and `R3_SCRATCH` to the canonical observed
`realpath(bpy.app.tempdir)/blender_mcp`; append all bound preflight facts to the report. Also copy
the four bound Plan/runbook variables from the brief into that same PTY. Appendix C's
generated protocol consumes these variables and rechecks listener/scratch plus repository
bindings at its preamble and immediately before `run`; it does not launch or replace the
preflight Blender/listener. Cleanup rechecks PID, start time, and that exact executable
path-filtered device/inode identity before signalling; a reused PID is recorded as identity drift
and is never killed.

After preflight passes, controller exclusive-creates only:

- owned mode-0700 `.superpowers/sdd/modeling-remediation/final-retest-r3/`.

Generate durable `attempt-0001/r3_controller.py` with Appendix A; Appendix A creates
the attempt directory, so do not create it separately. Recheck its exact
identity, compile it in memory and prove no `__pycache__`, rerun both probe markers,
then run Appendix C to a separate fresh mode-0700 `/private/tmp` output directory and
paste its exact protocol. That protocol requires the controller-only attempt allowlist
before it builds the original fixture payloads and runs their existing strict probes.
In that already-open persistent PTY, start exactly one recorder.
Send the guarded preamble in bounded chunks. Send only the single controller `run`
command, leaving stdin empty for either failure ACK or visual ACK; never paste trailing
post-run commands before the controller requests input.

The controller's first run-side effect after binding its own SHA is exclusive creation
and fsync of `run-ticket.json`, binding command `run`, attempt, and controller SHA. A
successful ticket acquisition defines one actual run; a second invocation fails before
session/App/fixture side effects because the ticket already exists. Both terminal
validators and reviewers require exactly this one ticket. Probe in a disposable attempt
must execute ticket acquisition twice, require the first GREEN and second RED, and prove
the ticket bytes/inode did not change. The generated terminal continuation derives
`actual_run_count` only by descriptor-bound exact parsing of those three ticket fields;
absence or malformed content is count zero and an unverified cleanup error, never an
assumed run.

### Failure terminal

If the run fails, type the exact failure ACK with a literal immediate hypothesis that
describes only observed facts. Close and validate the journal, stop the recorder,
discard the unsaved scene, stop the owned listener, and recheck no owned processes.
For a generic grouped direct-session failure, require before the ACK:

- native-0600/nlink-1 `direct-session.stderr` and
  `direct-session-failure.json` in attempt-0001;
- JSON with module-qualified ordered recursive exception tree, per-node retained
  base64 retained bytes plus full observed byte count/SHA/truncation/render-error type,
  tree SHA, and stderr
  observed/retained counts, full observed digest, retained digest, truncation and
  drain error;
- ACK `response_sha256` equal to the exact JSON payload SHA-256 and the journal symptom
  carrying that evidence SHA;
- native-0600/nlink-1 `direct-failure-ack.json`, exclusive-created only after the
  controller accepted that ACK, binding the same attempt and evidence SHA.

Only an untruncated `BaseExceptionGroup` with nonempty ordered children is eligible for
this certified lane; plain controller/config/catalog errors are not. If stderr drain or
either exclusive evidence write/fsync fails, the handler still closes open call/stage/
task scopes as deviation using a safe nonempty fallback tree hash, records the secondary
persistence error, and terminates as unverified BLOCKED without requesting a diagnostic
ACK or entering Task 4. Probe injects a real stderr-close exception, a completed drain
with error, first/second evidence-create failures, and a truncated group tree; every
case must close the journal as deviation and request no diagnostic ACK.

Record exact evidence identities in the new follow-up report without a terminal status.
Run Appendix B and retain its exact JSON summary. Missing or invalid ACK marker, or any
Appendix-B rejection, appends the exact count plus `STATUS: BLOCKED` after cleanup and
never enters review. There is no second run. Skip Task 5,
complete Task 4's independent failure review, and report the blocker to the user.

### Visual option-C checkpoint

If the controller emits `VISUAL_ACK_REQUIRED`, the implementer reports only the live
PTY session/FIFO and the complete ordered list of absolute PNG paths and SHA-256 values,
then stops. The controller renders every PNG to the user and ends the turn asking for
an explicit pass/fail result for each row. Only after the user responds does one of
three transitions occur in the same live PTY:

1. every ordered image is explicitly PASS: type the controller's exact all-pass ACK;
2. any ordered image is explicitly FAIL: type canonical JSON binding the complete
   ordered artifact set and the user's literal `pass`/`fail` verdicts using the same
   top-level `action/attempt_id/artifacts` schema as PASS. The controller strictly
   validates path/SHA/order/result, persists that parsed acknowledgement in the visual
   deviation manifest plus its raw SHA, closes the journal, and enters unverified
   BLOCKED cleanup;
3. any verdict is missing, ambiguous, reordered, or the PTY identity is lost: type
   nothing and close stdin to produce `ack EOF` visual deviation, then close the journal
   and enter the same unverified BLOCKED cleanup path.

The last two transitions stop recorder/listener/Blender, verify no owned processes,
then use Appendix C's already bound report FD to append the journal SHA, exact empty
owned-process inventory, `actual_run_count: 1`, and unique `STATUS: BLOCKED`; they never
enter Task 4/5 or start another attempt. A generic direct failure instead appends the
same cleanup facts plus `failure_review_pending: 1` without a terminal status and enters
Task 4 while preserving that same live PTY and FD 8. The generated continuation is the
sole executable recipe for all three branches;
the implementer does not synthesize cleanup or report commands. These user-decision
terminals are reported as unverified.

## Task 4: independent terminal-failure review

This certification task applies only to a generic direct-session failure that passes
Appendix B. Preflight failure, visual user-FAIL/EOF, stderr-drain failure, or any other
implementation/environment failure is still cleaned up and recorded as BLOCKED, but is
reported to the user as unverified terminal evidence and cannot claim this Plan's second
success criterion. The controller exclusive-creates
`.superpowers/sdd/modeling-remediation/task-7-followup-1-failure-review.md` as a bound
native-0600/nlink-1 file and dispatches one fresh independent reviewer. For a generic
direct-session failure, its package contains exact Appendix B output and binds:

- Plan/runbook commits and bytes, R3 controller, attempt root, `ACTUAL_RUN_LIMIT=1`,
  exact run-ticket identity, and proof that `attempt-0002` is absent;
- both direct failure files, the accepted-ACK marker, recursive-tree/stderr digests,
  ACK identity and report;
- journal bytes/clock/scope closure/symptom/hypothesis and cleanup process inventory;
- frozen R2 artifacts and proof that tracked status is clean.

The reviewer writes only its preallocated report through the original bound descriptor.
Approval requires exact standalone `Critical: 0`, `Important: 0`, `Minor: 0`, and
`REVIEW_VERDICT: APPROVED`. A finding is terminal and cannot authorize a fix or retry;
it is reported as an implementation/evidence failure. The controller rechecks every
package input after review. Its bounded syntactic reader reads at most 1 MiB through the
originally bound review-report descriptor and rechecks dev/ino/uid/mode/nlink/size/SHA.
The separate approval predicate requires exactly one full line for each marker and rejects
nonzero findings or duplicates. Reviewer crash/nonzero exit, malformed or oversized text,
wrong verdict, replacement, post-read drift, or any package-input drift is terminal
disapproval. After cleanup, both approval and disapproval append `actual_run_count: 1`
and unique `STATUS: BLOCKED`; approval distinguishes certified leaf-complete evidence
from unverified terminal evidence in the facts, not by changing terminal status. The
controller then resumes the still-live implementer PTY with exactly
`r3_finish_review failure APPROVED` or `r3_finish_review failure REJECTED` according to
the fail-closed parser result. That generated function rechecks the direct-review state,
count and cleanup facts, appends through the still-open original FD 8, and closes it.

## Task 5: successful-run audit, gate, and review

This task exists only after every image passed option C and the generated continuation
completed the controller's single `validate` and non-idempotent `finalize` calls. Do not
rerun either command. Descriptor-bind and verify their already-created
`dispatch-validation.json` and `evidence-manifest.json`, then run only the read-only
`summary` and active-audit validators against immutable attempt-0001. Require one pass
row per dynamic tool, zero recoveries, exact catalog and scene identities, valid journal,
retained visual manifest, and no generic failure or direct-ACK files.

Replace only the modeling audit's Tool-results/visual sections with the exact R3 report
and add exactly one complete set of `R3_*` attempt/controller/report/dispatch/evidence/
visual binding lines. Commit only
`docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md` with message
`docs: record clean diagnostic Blender final retest`.

On that clean audit HEAD run:

- the R3 controller active-audit validator;
- `scripts/official_blender_mcp_audit.py validate` against the R3 journal, audit,
  direct/source/effective-config catalogs;
- `git diff --check`;
- `./scripts/checks.sh`, requiring exactly 369 passed and `ALL CHECKS PASSED`;
- clean status, unchanged HEAD, and exact two-commit follow-up scope: runbook then audit,
  with no other paths.

Write exact commands/output/hashes to the new follow-up report without a terminal status.
A fresh independent combined reviewer binds the report, R3 attempt, two tracked commits,
current clean HEAD, old immutable R2 evidence, option-C ACK, validators, and full gate.
Approval requires Critical/Important/Minor = 0/0/0 and `REVIEW_VERDICT: APPROVED`.
Its report is preallocated/bound before dispatch at exact fresh path
`.superpowers/sdd/modeling-remediation/task-7-followup-1-success-review.md`; the
controller records dev/ino/uid/mode/nlink/size before dispatch and uses the same bounded
syntactic reader, separate approval predicate, original-FD 1 MiB cap, and post-read
identity rechecks as Task 4. A disposable parser probe must accept one exact success
report and make missing/duplicate/nonzero finding markers, wrong verdict, oversize,
replaced inode, post-read byte drift, reviewer crash, and nonzero exit terminal
disapproval rather than an unfinishable parser state.
Any nonapproval terminates this Plan; do not amend, retry Blender, or self-fix. After the
review process reaches either exact approval or terminal disapproval, append
`actual_run_count: 1` plus unique `STATUS: PASS` only for approval, otherwise append the
same count plus unique `STATUS: BLOCKED`. The controller reports success only after the
PASS append and final bound report recheck. It resumes the still-live implementer PTY
with exactly `r3_finish_review success APPROVED` or
`r3_finish_review success REJECTED`; no other command may produce the terminal lines.

## Appendix A: exact R3 controller generator

Extract this fence byte-for-byte: 1,197 lines, 46,213 bytes, SHA-256
`42e20d1cc0a982580c89f44182e4dae85a897c2b07cbf106fab2f54157d361e4`.
Run with uv-managed Python 3.13. The parent `final-retest-r3` directory must already be
owned native mode-0700 and the output attempt path must not exist.

```python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


BASE_SHA256 = "cc325e471aa0d1a0349deade58d0f7517575c35d901fb99f00ee1cc4de7f640a"
OUTPUT_SHA256 = "7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a"
OUTPUT_LINES = 6924
OUTPUT_BYTES = 285387


def replace(text: str, old: str, new: str, count: int = 1) -> str:
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f"anchor count differs: expected {count}, got {actual}: {old[:72]!r}")
    return text.replace(old, new)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_r3_controller.py BASE OUTPUT")
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise RuntimeError("frozen R2 controller SHA differs")
    text = raw.decode("utf-8")

    for old, new, count in (
        ("final-retest-r2", "final-retest-r3", 17),
        ("r2_controller.py", "r3_controller.py", 7),
        ("r2-call-", "r3-call-", 20),
        ("r2-repeat-", "r3-repeat-", 14),
        ("r2-future-", "r3-future-", 5),
        ("r2-report.md", "r3-report.md", 9),
        ("r2-production-controller", "r3-production-controller", 1),
        ("R2_", "R3_", 34),
    ):
        text = replace(text, old, new, count)

    text = replace(
        text,
        "import base64\nimport hashlib\n",
        "import base64\nimport fcntl\nimport hashlib\nimport shlex\n",
    )
    text = replace(
        text,
        '''BASE_EVIDENCE = frozenset({
    "r3_controller.py", "fixture_setup.py", "model_body.py", "cli_body.py",
''',
        '''BASE_EVIDENCE = frozenset({
    "r3_controller.py", "fixture_setup.py", "model_body.py", "cli_body.py",
    "run-ticket.json",
''',
    )
    text = replace(
        text,
        '''    def close(self) -> None:
        if not self.errlog.closed:
            self.errlog.close()
        self._thread.join(timeout=60)
        if self._read_fd >= 0:
''',
        '''    def close(self, timeout: float = 60.0) -> None:
        if not self.errlog.closed:
            self.errlog.close()
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise R2Error("APP", "MCP server stderr drain did not terminate")
        if self._read_fd >= 0:
''',
    )
    text = replace(
        text,
        "MCP_STDERR_MAX = 4 * 1024 * 1024\n",
        """MCP_STDERR_MAX = 4 * 1024 * 1024
FAILURE_MESSAGE_MAX = 8 * 1024
FAILURE_TREE_MAX_DEPTH = 16
FAILURE_TREE_MAX_NODES = 256
""",
    )
    text = replace(
        text,
        '''    snapshots: ProductionSnapshotSet | None = None
    mcp_stderr: ProductionBoundedStderr | None = None
    try:
''',
        '''    snapshots: ProductionSnapshotSet | None = None
    mcp_stderr: ProductionBoundedStderr | None = None
    root: Path | None = None
    try:
''',
    )
    text = replace(
        text,
        '''def production_stat_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


@dataclass(frozen=True)
''',
        '''def production_stat_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def production_parent_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode))


@dataclass(frozen=True)
''',
    )
    text = replace(
        text,
        '''        or expected_parent is not None
        and parent_bound != production_stat_identity(expected_parent)
''',
        '''        or expected_parent is not None
        and production_parent_identity(parent_before)
        != production_parent_identity(expected_parent)
''',
    )
    text = replace(
        text,
        '''            bound = production_stat_identity(self.root_info)
            if (
                production_stat_identity(os.fstat(directory_fd)) != bound
                or production_stat_identity(os.lstat(self.root)) != bound
            ):
                raise R2Error("INPUT", "attempt directory identity changed")
            result = set(os.listdir(directory_fd))
            if (
                production_stat_identity(os.fstat(directory_fd)) != bound
                or production_stat_identity(os.lstat(self.root)) != bound
            ):
                raise R2Error("INPUT", "attempt listing generation changed")
''',
        '''            bound = production_parent_identity(self.root_info)
            if (
                production_parent_identity(os.fstat(directory_fd)) != bound
                or production_parent_identity(os.lstat(self.root)) != bound
            ):
                raise R2Error("INPUT", "attempt directory identity changed")
            result = set(os.listdir(directory_fd))
            if (
                production_parent_identity(os.fstat(directory_fd)) != bound
                or production_parent_identity(os.lstat(self.root)) != bound
            ):
                raise R2Error("INPUT", "attempt listing generation changed")
''',
    )
    text = replace(
        text,
        '''        bound = production_stat_identity(self.root_info)
        if production_stat_identity(os.lstat(self.root)) != bound:
            raise R2Error("INPUT", "attempt directory generation changed")
''',
        '''        bound = production_parent_identity(self.root_info)
        if production_parent_identity(os.lstat(self.root)) != bound:
            raise R2Error("INPUT", "attempt directory generation changed")
''',
    )
    text = replace(
        text,
        '''            if production_stat_identity(os.fstat(directory_fd)) != bound:
                raise R2Error("INPUT", "attempt directory binding changed")
''',
        '''            if production_parent_identity(os.fstat(directory_fd)) != bound:
                raise R2Error("INPUT", "attempt directory binding changed")
''',
    )
    text = replace(
        text,
        '''        tracked_sources = production_git_pin(source_mcp)
        source = production_source_names(source_mcp, tracked_sources)
        app_live, effective = production_app_catalogs(codex_bin, feature_root, root)
        for required in ("fixture.blend", "library_source.blend", "model_body.py", "cli_body.py"):
            production_read_owned(root, required)
        if os.path.lexists(root / "known-missing.png"):
            raise R2Error("FIXTURE", "controlled missing file unexpectedly exists")
''',
        '''        tracked_sources = production_git_pin(source_mcp)
        source = production_source_names(source_mcp, tracked_sources)
        for required in (
            "fixture.blend", "library_source.blend", "model_body.py", "cli_body.py",
        ):
            production_read_owned(root, required)
        if os.path.lexists(root / "known-missing.png"):
            raise R2Error("FIXTURE", "controlled missing file unexpectedly exists")
        current_audit = os.fstat(audit_fd)
        current_fifo = os.lstat(audit_fifo)
        if (
            (current_audit.st_dev, current_audit.st_ino)
            != (audit_info.st_dev, audit_info.st_ino)
            or (current_fifo.st_dev, current_fifo.st_ino)
            != (audit_info.st_dev, audit_info.st_ino)
        ):
            raise R2Error("INPUT", "audit FIFO changed before run ticket")
        production_require_recorder(
            args.recorder_pid, args.recorder_start, audit_fifo, root, feature_root,
            recorder_uv, recorder_mcp,
            (audit_info.st_dev, audit_info.st_ino),
            (recorder_uv_info.st_dev, recorder_uv_info.st_ino),
        )
        create_owned(root, "run-ticket.json", cbytes({
            "attempt_id": root.name,
            "controller_sha256": controller_sha,
            "command": "run",
        }) + b"\\n")
        app_live, effective = production_app_catalogs(codex_bin, feature_root, root)
''',
    )
    text = replace(
        text,
        '''    try:
        info = os.lstat(path)
    except FileNotFoundError:
        os.mkdir(path, 0o700)
        info = os.lstat(path)
''',
        '''    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise R2Error("SCRATCH", "preflight scratch directory is missing") from exc
''',
    )
    text = replace(
        text,
        '''        try:
            os.fstat(audit_fd)
        except OSError as exc:
            raise R2Error("INPUT", "audit fd is not open") from exc
        root = production_root(args.root)
''',
        '''        try:
            audit_info = os.fstat(audit_fd)
        except OSError as exc:
            raise R2Error("INPUT", "audit fd is not open") from exc
        if any(
            not os.path.isabs(raw)
            for raw in (
                args.root, args.scratch, args.codex_bin, args.config,
                args.feature_root, args.audit_fifo, args.recorder_uv_bin,
                args.recorder_mcp_editable,
            )
        ):
            raise R2Error("INPUT", "all run paths must be caller-supplied absolute paths")
        audit_fifo = Path(os.path.abspath(args.audit_fifo))
        fifo_info = os.lstat(audit_fifo)
        if (
            Path(os.path.realpath(audit_fifo)) != audit_fifo
            or not stat.S_ISFIFO(audit_info.st_mode)
            or not stat.S_ISFIFO(fifo_info.st_mode)
            or audit_info.st_uid != os.getuid()
            or stat.S_IMODE(audit_info.st_mode) != 0o600
            or audit_info.st_nlink != 1
            or (audit_info.st_dev, audit_info.st_ino)
            != (fifo_info.st_dev, fifo_info.st_ino)
            or fcntl.fcntl(audit_fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_WRONLY
        ):
            raise R2Error("INPUT", "audit fd is not the bound recorder FIFO write end")
        root = production_root(args.root)
''',
    )
    text = replace(
        text,
        '''    command.add_argument("--audit-fd", type=int, default=9)
''',
        '''    command.add_argument("--audit-fd", type=int, default=9)
    command.add_argument("--audit-fifo", required=True)
    command.add_argument("--recorder-pid", required=True, type=int)
    command.add_argument("--recorder-start", required=True)
    command.add_argument("--recorder-uv-bin", required=True)
    command.add_argument("--recorder-mcp-editable", required=True)
''',
    )
    text = replace(
        text,
        "async def production_run(args: argparse.Namespace) -> dict[str, Any]:\n",
        '''def production_require_recorder(
    pid: int,
    start: str,
    fifo: Path,
    root: Path,
    feature_root: Path,
    uv_bin: Path,
    mcp_editable: Path,
    fifo_identity: tuple[int, int],
    uv_identity: tuple[int, int],
) -> None:
    if pid <= 0:
        raise R2Error("INPUT", "recorder PID differs")
    try:
        os.kill(pid, 0)
    except OSError as exc:
        raise R2Error("INPUT", "bound recorder is not live") from exc
    expected_script = feature_root / "scripts/official_blender_mcp_audit.py"
    expected_journal = root / "events.ndjson"
    observed_start = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart="],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not start or observed_start != start:
        raise R2Error("INPUT", "recorder process start identity differs")
    fifo_info = os.lstat(fifo)
    if (fifo_info.st_dev, fifo_info.st_ino) != fifo_identity:
        raise R2Error("INPUT", "bound FIFO identity differs")
    observed = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "uid=", "-o", "command="],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    fields = observed.split(None, 1)
    command = fields[1] if len(fields) == 2 else ""
    expected_argv = [
        str(uv_bin), "run", "--quiet", "--no-project", "--python", "3.13",
        "--with", "mcp[cli]>=1.2.0,<2", "--with-editable", str(mcp_editable),
        "python", str(expected_script), "record", "--output", str(expected_journal),
    ]
    try:
        observed_argv = shlex.split(command)
    except ValueError as exc:
        raise R2Error("INPUT", "recorder process argv is malformed") from exc
    if len(fields) != 2 or fields[0] != str(os.getuid()) or observed_argv != expected_argv:
        raise R2Error("INPUT", "recorder process identity differs")
    opened = subprocess.run(
        ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "0", "-F0int"],
        check=True,
        capture_output=True,
    ).stdout.split(b"\\0")
    expected_fields = {
        b"tFIFO", f"i{fifo_info.st_ino}".encode(), f"n{fifo}".encode(),
    }
    if not expected_fields.issubset(set(opened)):
        raise R2Error("INPUT", "recorder stdin is not the bound FIFO inode")
    text_records = subprocess.run(
        ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "txt", "-F0Dint"],
        check=True,
        capture_output=True,
    ).stdout.splitlines()
    executable = next(
        (row.split(b"\\0") for row in text_records if row.startswith(b"ftxt\\0")),
        [],
    )
    expected_executable = {
        b"ftxt", f"D{uv_identity[0]:#x}".encode(),
        f"i{uv_identity[1]}".encode(), f"n{uv_bin}".encode(),
    }
    if not expected_executable.issubset(set(executable)):
        raise R2Error("INPUT", "recorder executable image differs")


async def production_run(args: argparse.Namespace) -> dict[str, Any]:
''',
    )
    text = replace(
        text,
        '''        if (
            Path(os.path.realpath(feature_root)) != feature_root
            or not feature_root.is_dir()
        ):
            raise R2Error("INPUT", "feature root differs")
''',
        '''        if (
            Path(os.path.realpath(feature_root)) != feature_root
            or not feature_root.is_dir()
        ):
            raise R2Error("INPUT", "feature root differs")
        production_safe_executable(codex_bin, "Codex")
        if Path(os.path.realpath(config_path)) != config_path:
            raise R2Error("CONFIG", "config path differs")
        production_read_path(config_path, limit=1024 * 1024)
        recorder_uv = Path(args.recorder_uv_bin)
        recorder_mcp = Path(args.recorder_mcp_editable)
        production_safe_executable(recorder_uv, "recorder uv")
        recorder_uv_info = os.lstat(recorder_uv)
        if (
            Path(os.path.realpath(recorder_mcp)) != recorder_mcp
            or not recorder_mcp.is_dir()
        ):
            raise R2Error("INPUT", "recorder editable source differs")
        production_require_recorder(
            args.recorder_pid,
            args.recorder_start,
            audit_fifo,
            root,
            feature_root,
            recorder_uv,
            recorder_mcp,
            (audit_info.st_dev, audit_info.st_ino),
            (recorder_uv_info.st_dev, recorder_uv_info.st_ino),
        )
''',
    )
    text = replace(
        text,
        '''        production_safe_executable(codex_bin, "Codex")
        section, on_disk, source_mcp = production_config(config_path)
''',
        '''        section, on_disk, source_mcp = production_config(config_path)
''',
    )
    for old, new in (
        ("# Final retest R2", "# Final retest R3"),
        ("R2 report bytes/digest differ", "R3 report bytes/digest differ"),
        ("active Tool results bytes differ from R2 report", "active Tool results bytes differ from R3 report"),
        ("active visual section bytes differ from R2 report", "active visual section bytes differ from R3 report"),
    ):
        text = replace(text, old, new)
    text = replace(
        text,
        '''        self.error = ""
        read_fd, write_fd = os.pipe()
''',
        '''        self.error = ""
        self._sha256 = hashlib.sha256()
        read_fd, write_fd = os.pipe()
''',
    )
    text = replace(
        text,
        '''            self.observed += len(chunk)
            room = MCP_STDERR_MAX - len(self.retained)
''',
        '''            self.observed += len(chunk)
            self._sha256.update(chunk)
            room = MCP_STDERR_MAX - len(self.retained)
''',
    )
    text = replace(
        text,
        '''                f"{self.observed} bytes observed, limit {MCP_STDERR_MAX}",
            )


def production_app_request(
''',
        '''                f"{self.observed} bytes observed, limit {MCP_STDERR_MAX}",
            )

    def evidence(self) -> dict[str, object]:
        retained = bytes(self.retained)
        return {
            "observed_bytes": self.observed,
            "observed_sha256": self._sha256.hexdigest(),
            "retained_bytes": len(retained),
            "retained_sha256": hashlib.sha256(retained).hexdigest(),
            "truncated": self.observed > len(retained),
            "drain_error": self.error or None,
        }


def production_exception_message(exc: BaseException) -> dict[str, object]:
    render_error_type: str | None = None
    try:
        rendered = str(exc)
    except BaseException as render_error:
        rendered = ""
        render_error_type = (
            f"{type(render_error).__module__}.{type(render_error).__qualname__}"
        )
    observed = 0
    retained = bytearray()
    hasher = hashlib.sha256()
    for offset in range(0, len(rendered), 4096):
        chunk = rendered[offset:offset + 4096].encode(
            "utf-8", errors="backslashreplace",
        )
        observed += len(chunk)
        hasher.update(chunk)
        room = FAILURE_MESSAGE_MAX - len(retained)
        if room > 0:
            retained.extend(chunk[:room])
    retained_bytes = bytes(retained)
    return {
        "observed_bytes": observed,
        "sha256": hasher.hexdigest(),
        "retained_base64": base64.b64encode(retained_bytes).decode("ascii"),
        "retained_sha256": hashlib.sha256(retained_bytes).hexdigest(),
        "truncated": observed > len(retained_bytes),
        "render_error_type": render_error_type,
    }


def production_exception_tree(exc: BaseException) -> dict[str, object]:
    node_count = [0]
    truncated = [False]

    def visit(current: BaseException, depth: int) -> dict[str, object]:
        if node_count[0] >= FAILURE_TREE_MAX_NODES:
            truncated[0] = True
            return {"capture": "truncated", "reason": "node_limit"}
        node_count[0] += 1
        value: dict[str, object] = {
            "type": f"{type(current).__module__}.{type(current).__qualname__}",
            "message": production_exception_message(current),
        }
        if isinstance(current, BaseExceptionGroup):
            if depth >= FAILURE_TREE_MAX_DEPTH:
                truncated[0] = True
                value["children"] = [{
                    "capture": "truncated",
                    "reason": "depth_limit",
                    "remaining_children": len(current.exceptions),
                }]
            else:
                children: list[dict[str, object]] = []
                for index, child in enumerate(current.exceptions):
                    if node_count[0] >= FAILURE_TREE_MAX_NODES:
                        truncated[0] = True
                        children.append({
                            "capture": "truncated",
                            "reason": "node_limit",
                            "remaining_children": len(current.exceptions) - index,
                        })
                        break
                    children.append(visit(child, depth + 1))
                value["children"] = children
        return value

    root = visit(exc, 0)
    return {
        "limits": {
            "max_depth": FAILURE_TREE_MAX_DEPTH,
            "max_nodes": FAILURE_TREE_MAX_NODES,
        },
        "node_count": node_count[0],
        "truncated": truncated[0],
        "root": root,
    }


def production_persist_direct_failure(
    root: Path,
    exc: BaseException,
    stderr_sink: ProductionBoundedStderr,
) -> tuple[str, str]:
    stderr_sink.close()
    retained = bytes(stderr_sink.retained)
    stderr = stderr_sink.evidence()
    if stderr["drain_error"] is not None:
        raise R2Error("APP", "MCP server stderr drain failed before evidence persistence")
    create_owned(root, "direct-session.stderr", retained)
    tree = production_exception_tree(exc)
    if tree["truncated"] is not False:
        raise R2Error("CONTROLLER", "exception tree exceeds certified capture limits")
    evidence = {
        "exception_tree": tree,
        "exception_tree_sha256": digest(tree),
        "stderr": stderr,
    }
    payload = cbytes(evidence) + b"\\n"
    create_owned(root, "direct-session-failure.json", payload)
    evidence_sha = hashlib.sha256(payload).hexdigest()
    root_value = tree["root"]
    assert isinstance(root_value, dict)
    suffix = f" [failure_evidence_sha256={evidence_sha}]"
    prefix = f"{root_value.get('type', 'capture.truncated')}: "
    message_value = root_value.get("message", {})
    retained_message = ""
    if isinstance(message_value, dict):
        retained_raw = base64.b64decode(
            str(message_value.get("retained_base64", "")), validate=True,
        )
        retained_message = retained_raw.decode("utf-8", errors="replace")
    symptom = prefix + retained_message[:max(0, 2_000 - len(prefix) - len(suffix))] + suffix
    return evidence_sha, symptom


def production_app_request(
''',
    )
    text = replace(
        text,
        '''    return True


async def production_invoke(
''',
        '''    return True


def production_close_direct_or_deviation(
    root: Path,
    audit_fd: int,
    pending_call: dict[str, object] | None,
    issue_ids: list[str],
    exc: BaseException,
    stderr_sink: ProductionBoundedStderr,
) -> tuple[bool, str]:
    try:
        response_sha, symptom = production_persist_direct_failure(
            root, exc, stderr_sink,
        )
    except BaseException as evidence_error:
        production_close_deviation(audit_fd, pending_call)
        secondary_sha, _ = production_generic_failure(evidence_error)
        raise R2Error(
            "CONTROLLER",
            f"direct evidence persistence failed [exception_tree_sha256={secondary_sha}]",
        ) from evidence_error
    accepted = production_close_failure(
        audit_fd, pending_call, issue_ids, response_sha, symptom,
    )
    if accepted:
        create_owned(root, "direct-failure-ack.json", cbytes({
            "attempt_id": root.name,
            "evidence_sha256": response_sha,
            "status": "accepted",
        }) + b"\\n")
    return accepted, symptom


def production_direct_failure_eligible(
    exc: BaseException,
    root: Path | None,
    stderr_sink: ProductionBoundedStderr | None,
    pending_call: dict[str, object] | None,
    calls: list[dict[str, Any]],
) -> bool:
    return (
        isinstance(exc, BaseExceptionGroup)
        and root is not None
        and stderr_sink is not None
        and pending_call is None
        and not calls
    )


def production_generic_failure(
    exc: BaseException,
) -> tuple[str, str]:
    tree = production_exception_tree(exc)
    response_sha = digest(tree)
    root = tree["root"]
    assert isinstance(root, dict)
    symptom = f"{root.get('type', 'capture.truncated')} [exception_tree_sha256={response_sha}]"
    return response_sha, symptom


def production_failure_diagnostics_probe() -> None:
    generic_sha, generic_symptom = production_generic_failure(RuntimeError("generic"))
    assert re.fullmatch(r"[0-9a-f]{64}", generic_sha) is not None
    assert generic_sha in generic_symptom
    refused = ExceptionGroup("session", [ConnectionRefusedError("listener refused")])
    broken = ExceptionGroup("session", [BrokenPipeError("writer broke")])
    refused_tree = production_exception_tree(refused)
    broken_tree = production_exception_tree(broken)
    assert digest(refused_tree) != digest(broken_tree)
    assert digest(refused_tree) == digest(production_exception_tree(refused))
    ordered = ExceptionGroup("session", [ValueError("a"), TypeError("b")])
    reversed_group = ExceptionGroup("session", [TypeError("b"), ValueError("a")])
    assert digest(production_exception_tree(ordered)) != digest(
        production_exception_tree(reversed_group)
    )
    long_message = "x" * (FAILURE_MESSAGE_MAX + 7)
    long_value = production_exception_message(RuntimeError(long_message))
    assert long_value["observed_bytes"] == len(long_message)
    assert long_value["sha256"] == hashlib.sha256(long_message.encode()).hexdigest()
    assert long_value["truncated"] is True
    assert len(base64.b64decode(long_value["retained_base64"], validate=True)) == FAILURE_MESSAGE_MAX
    split_value = production_exception_message(RuntimeError("x" * 8191 + "é"))
    assert len(base64.b64decode(split_value["retained_base64"], validate=True)) == FAILURE_MESSAGE_MAX
    class BadString(RuntimeError):
        def __str__(self) -> str:
            raise RuntimeError("render broke")
    hostile_value = production_exception_message(BadString())
    assert hostile_value["render_error_type"] == "builtins.RuntimeError"
    assert hostile_value["observed_bytes"] == 0
    assert hostile_value["retained_sha256"] == hashlib.sha256(b"").hexdigest()
    deep: BaseException = RuntimeError("leaf")
    for _ in range(64):
        deep = ExceptionGroup("deep", [deep])
    deep_tree = production_exception_tree(deep)
    assert deep_tree["truncated"] is True
    assert deep_tree["node_count"] == FAILURE_TREE_MAX_DEPTH + 1
    wide_tree = production_exception_tree(ExceptionGroup(
        "wide", [RuntimeError(str(index)) for index in range(300)],
    ))
    assert wide_tree["truncated"] is True
    assert wide_tree["node_count"] == FAILURE_TREE_MAX_NODES

    with tempfile.TemporaryDirectory(prefix="r3-snapshot-probe-") as raw:
        family = Path(raw) / "final-retest-r3"
        family.mkdir(mode=0o700)
        root = family / "attempt-0001"
        root.mkdir(mode=0o700)
        create_owned(root, "fixture.blend", b"fixture\\n")
        snapshots = ProductionSnapshotSet(root)
        assert snapshots.read("fixture.blend", limit=1024) == b"fixture\\n"
        create_owned(root, "run-ticket.json", b"ticket\\n")
        ticket_info = os.lstat(root / "run-ticket.json")
        ticket_bytes = (root / "run-ticket.json").read_bytes()
        try:
            create_owned(root, "run-ticket.json", b"replacement\\n")
        except FileExistsError:
            pass
        else:
            raise AssertionError("second run ticket acquisition was accepted")
        assert (root / "run-ticket.json").read_bytes() == ticket_bytes
        current_ticket = os.lstat(root / "run-ticket.json")
        assert (current_ticket.st_dev, current_ticket.st_ino) == (
            ticket_info.st_dev, ticket_info.st_ino,
        )
        snapshots.recheck_all()
        create_owned(root, "catalog.json", b"catalog\\n")
        assert snapshots.read("catalog.json", limit=1024) == b"catalog\\n"
        snapshots.recheck_all()
        os.chmod(root / "fixture.blend", 0o400)
        try:
            snapshots.recheck_all()
        except R2Error as exc:
            assert "cached evidence changed" in str(exc)
        else:
            raise AssertionError("cached leaf drift was accepted")

    with tempfile.TemporaryDirectory(prefix="r3-failure-probe-") as raw:
        root = Path(raw)
        os.chmod(root, 0o700)
        sink = ProductionBoundedStderr()
        sink.errlog.write("bounded stderr\\n")
        sink.errlog.flush()
        original_close = globals()["production_close_failure"]

        def observe(
            _audit_fd: int,
            _pending: dict[str, object] | None,
            _issues: list[str],
            response_sha: str,
            symptom: str,
        ) -> bool:
            stderr_path = root / "direct-session.stderr"
            failure_path = root / "direct-session-failure.json"
            assert stderr_path.read_bytes() == b"bounded stderr\\n"
            payload = failure_path.read_bytes()
            assert response_sha == hashlib.sha256(payload).hexdigest()
            assert response_sha in symptom
            assert len(symptom) <= 2_000
            value = strict_json(payload, "failure probe")
            assert isinstance(value, dict)
            assert value["exception_tree_sha256"] == digest(value["exception_tree"])
            assert value["exception_tree"]["truncated"] is False
            assert value["stderr"]["observed_sha256"] == hashlib.sha256(
                stderr_path.read_bytes()
            ).hexdigest()
            for path in (stderr_path, failure_path):
                info = os.lstat(path)
                assert stat.S_ISREG(info.st_mode)
                assert info.st_uid == os.getuid()
                assert stat.S_IMODE(info.st_mode) == 0o600
                assert info.st_nlink == 1
            return True

        globals()["production_close_failure"] = observe
        try:
            closed_result, closed_symptom = production_close_direct_or_deviation(
                root, -1, None, ["MODEL-PLAN-05"], refused, sink,
            )
            assert closed_result
            assert closed_symptom
            ack_marker = strict_json(
                (root / "direct-failure-ack.json").read_bytes(), "failure ACK marker",
            )
            assert ack_marker == {
                "attempt_id": root.name,
                "evidence_sha256": hashlib.sha256(
                    (root / "direct-session-failure.json").read_bytes(),
                ).hexdigest(),
                "status": "accepted",
            }
        finally:
            globals()["production_close_failure"] = original_close
    held = ProductionBoundedStderr()
    held_duplicate = os.dup(held.errlog.fileno())
    try:
        try:
            held.close(timeout=0.01)
        except R2Error as exc:
            assert str(exc) == "MCP server stderr drain did not terminate"
        else:
            raise AssertionError("held stderr writer did not fail closed")
    finally:
        os.close(held_duplicate)
        held.close(timeout=1.0)
    for fault in (
        "close", "drain", "stderr_create", "json_create", "truncated_tree",
    ):
        with tempfile.TemporaryDirectory(prefix=f"r3-{fault}-probe-") as raw:
            root = Path(raw)
            os.chmod(root, 0o700)
            read_fd, write_end = os.pipe()
            probe_sink = ProductionBoundedStderr()
            original_sink_close = probe_sink.close
            original_create = globals()["create_owned"]
            original_ack = globals()["production_failure_ack"]
            if fault == "close":
                def fault_close(timeout: float = 60.0) -> None:
                    del timeout
                    raise R2Error("APP", "injected stderr close failure")

                probe_sink.close = fault_close  # type: ignore[method-assign]
            elif fault == "drain":
                probe_sink.error = "injected drain failure"

            def fault_create(target: Path, name: str, data: bytes) -> None:
                if (
                    (fault == "stderr_create" and name == "direct-session.stderr")
                    or (fault == "json_create" and name == "direct-session-failure.json")
                ):
                    raise OSError(f"injected {fault}")
                original_create(target, name, data)

            globals()["create_owned"] = fault_create
            globals()["production_failure_ack"] = lambda *_: (_ for _ in ()).throw(
                AssertionError("diagnostic ACK requested after persistence failure")
            )
            try:
                try:
                    production_close_direct_or_deviation(
                        root, write_end, None, ["MODEL-PLAN-05"],
                        (
                            ExceptionGroup(
                                "wide",
                                [RuntimeError(str(index)) for index in range(300)],
                            )
                            if fault == "truncated_tree"
                            else ExceptionGroup("session", [RuntimeError("leaf")])
                        ),
                        probe_sink,
                    )
                except R2Error as exc:
                    assert "direct evidence persistence failed" in str(exc)
                else:
                    raise AssertionError("persistence failure was accepted")
            finally:
                globals()["create_owned"] = original_create
                globals()["production_failure_ack"] = original_ack
                probe_sink.close = original_sink_close  # type: ignore[method-assign]
                if not probe_sink.errlog.closed:
                    probe_sink.close()
                os.close(write_end)
            closure_rows = [strict_json(line, "deviation closure") for line in os.read(
                read_fd, 64 * 1024,
            ).splitlines()]
            os.close(read_fd)
            assert [row["outcome"] for row in closure_rows] == ["deviation", "deviation"]
    assert production_direct_failure_eligible(refused, Path("/x"), held, None, [])
    assert not production_direct_failure_eligible(
        refused, Path("/x"), held, {"event_id": "call"}, [],
    )
    assert not production_direct_failure_eligible(
        refused, Path("/x"), held, None, [{"status": "completed"}],
    )
    with tempfile.TemporaryDirectory(prefix="r3-long-failure-probe-") as raw:
        root = Path(raw)
        os.chmod(root, 0o700)
        empty_sink = ProductionBoundedStderr()
        evidence_sha, symptom = production_persist_direct_failure(
            root, RuntimeError("x" * 3_000), empty_sink,
        )
        assert len(symptom) <= 2_000
        assert evidence_sha in symptom
    with tempfile.TemporaryDirectory(prefix="r3-recorder-probe-") as raw:
        probe_root = Path(raw)
        os.chmod(probe_root, 0o700)
        feature = probe_root / "feature"
        (feature / "scripts").mkdir(parents=True, mode=0o700)
        script = feature / "scripts/official_blender_mcp_audit.py"
        script.write_text(
            "import argparse, time\\n"
            "p=argparse.ArgumentParser(); p.add_argument('command'); "
            "p.add_argument('--output'); p.parse_args(); time.sleep(60)\\n"
        )
        uv = Path("/Users/yeminjie/.local/bin/uv")
        editable = Path("/Users/yeminjie/blender_mcp/mcp")
        if not uv.is_file() or not editable.is_dir():
            raise AssertionError("recorder probe inputs differ")
        fifo = probe_root / "events.fifo"
        os.mkfifo(fifo, 0o600)
        guard = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        read_fd = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
        journal = probe_root / "events.ndjson"
        command = [
            str(uv), "run", "--quiet", "--no-project", "--python", "3.13",
            "--with", "mcp[cli]>=1.2.0,<2", "--with-editable", str(editable),
            "python", str(script), "record", "--output", str(journal),
        ]
        recorder = subprocess.Popen(command, stdin=read_fd)
        wrong = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)", *command],
            stdin=read_fd,
        )
        os.close(read_fd)
        try:
            fifo_identity = (os.lstat(fifo).st_dev, os.lstat(fifo).st_ino)
            uv_identity = (os.lstat(uv).st_dev, os.lstat(uv).st_ino)
            start = subprocess.run(
                ["/bin/ps", "-p", str(recorder.pid), "-o", "lstart="],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            production_require_recorder(
                recorder.pid, start, fifo, probe_root, feature, uv, editable,
                fifo_identity, uv_identity,
            )
            for bad_start, bad_uv in (
                (start + " changed", uv),
                (start, Path("/bin/false")),
            ):
                try:
                    production_require_recorder(
                        recorder.pid, bad_start, fifo, probe_root, feature,
                        bad_uv, editable, fifo_identity, uv_identity,
                    )
                except R2Error:
                    pass
                else:
                    raise AssertionError("wrong recorder identity passed binding")
            try:
                wrong_start = subprocess.run(
                    ["/bin/ps", "-p", str(wrong.pid), "-o", "lstart="],
                    check=True, capture_output=True, text=True,
                ).stdout.strip()
                production_require_recorder(
                    wrong.pid, wrong_start, fifo, probe_root, feature, uv, editable,
                    fifo_identity, uv_identity,
                )
            except R2Error:
                pass
            else:
                raise AssertionError("unrelated live PID passed recorder binding")
            os.unlink(fifo)
            os.mkfifo(fifo, 0o600)
            try:
                production_require_recorder(
                    recorder.pid, start, fifo, probe_root, feature, uv, editable,
                    fifo_identity, uv_identity,
                )
            except R2Error:
                pass
            else:
                raise AssertionError("replaced FIFO path passed recorder binding")
            assert not (probe_root / "run-ticket.json").exists()
            recorder.terminate()
            recorder.wait(timeout=10)
            try:
                production_require_recorder(
                    recorder.pid, start, fifo, probe_root, feature, uv, editable,
                    fifo_identity, uv_identity,
                )
            except R2Error:
                pass
            else:
                raise AssertionError("dead recorder PID passed binding")
        finally:
            if recorder.poll() is None:
                recorder.terminate()
                recorder.wait(timeout=10)
            wrong.terminate()
            wrong.wait(timeout=10)
            os.close(guard)
    print("R3_FAILURE_DIAGNOSTICS_GREEN distinct=2 ordered=1 persisted_before_ack=1")


async def production_invoke(
''',
    )
    text = replace(
        text,
        '''        response_sha = digest({
            "exception_type": type(exc).__name__,
            "message": str(exc),
        })
        if isinstance(exc, ProductionCallFailure):
            response_sha = str(exc.row["response_sha256"])
        elif isinstance(exc, AppEvidenceError):
            response_sha = exc.response_sha256
        if not isinstance(exc, VisualAckDeviation) and not closed:
            closed = True
            production_close_failure(
                audit_fd,
                pending_call,
                issue_ids,
                response_sha,
                f"{type(exc).__name__}: {exc}"[:2_000],
            )
''',
        '''        direct_failure = False
        if isinstance(exc, ProductionCallFailure):
            response_sha = str(exc.row["response_sha256"])
            _, symptom = production_generic_failure(exc)
        elif isinstance(exc, AppEvidenceError):
            response_sha = exc.response_sha256
            _, symptom = production_generic_failure(exc)
        elif not isinstance(exc, VisualAckDeviation) and production_direct_failure_eligible(
            exc, root, mcp_stderr, pending_call, calls,
        ):
            direct_failure = True
            response_sha = ""
            symptom = ""
        else:
            response_sha, symptom = production_generic_failure(exc)
        if not isinstance(exc, VisualAckDeviation) and not closed:
            closed = True
            if direct_failure:
                assert root is not None
                assert mcp_stderr is not None
                _, symptom = production_close_direct_or_deviation(
                    root, audit_fd, pending_call, issue_ids, exc, mcp_stderr,
                )
            else:
                production_close_failure(
                    audit_fd, pending_call, issue_ids, response_sha, symptom,
                )
''',
    )
    text = replace(
        text,
        '''        raise R2Error("CONTROLLER", f"{type(exc).__name__}: {exc}") from exc
''',
        '''        raise R2Error("CONTROLLER", symptom) from exc
''',
    )
    text = replace(
        text,
        '''    if not isinstance(value, dict) or not exact_json(value, expected):
        return None, "visual ack identity/artifacts differ"
    return value, None


def production_visual_ack(
''',
        '''    if not isinstance(value, dict) or set(value) != {"action", "attempt_id", "artifacts"}:
        return None, "visual ack identity/artifacts differ"
    if value["action"] != expected["action"] or value["attempt_id"] != expected["attempt_id"]:
        return None, "visual ack identity/artifacts differ"
    artifacts = value["artifacts"]
    expected_artifacts = expected["artifacts"]
    if (
        not isinstance(artifacts, list)
        or len(artifacts) != len(expected_artifacts)
        or any(
            not isinstance(item, dict)
            or set(item) != {"path", "sha256", "result"}
            or item.get("path") != wanted["path"]
            or item.get("sha256") != wanted["sha256"]
            or item.get("result") not in {"pass", "fail"}
            for item, wanted in zip(artifacts, expected_artifacts)
        )
    ):
        return None, "visual ack identity/artifacts differ"
    if any(item["result"] == "fail" for item in artifacts):
        return value, "visual ack contains fail verdict"
    return value, None


def production_visual_ack(
''',
    )
    text = replace(
        text,
        '''    assert production_parse_visual_ack(visual_line, visual_expected) == (visual_expected, None)
    wrong_visual = {**visual_expected, "attempt_id": "attempt-0002"}
''',
        '''    assert production_parse_visual_ack(visual_line, visual_expected) == (visual_expected, None)
    visual_fail = {
        **visual_expected,
        "artifacts": [{**visual_expected["artifacts"][0], "result": "fail"}],
    }
    assert production_parse_visual_ack(
        cbytes(visual_fail).decode("utf-8") + "\\n", visual_expected,
    ) == (visual_fail, "visual ack contains fail verdict")
    wrong_visual = {**visual_expected, "attempt_id": "attempt-0002"}
''',
    )
    text = replace(
        text,
        '''        placeholders = {
            "r3_controller.py": b"x",
''',
        '''        placeholders = {
            "r3_controller.py": b"x",
            "run-ticket.json": cbytes({
                "attempt_id": root.name,
                "controller_sha256": "1" * 64,
                "command": "run",
            }) + b"\\n",
''',
    )
    text = replace(
        text,
        '''def _production_validate_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root = production_root(args.root)
    controller_sha = production_controller_sha(root)
    catalogs = [production_catalog(root, name) for name in CATALOG_FILES]
''',
        '''def _production_validate_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root = production_root(args.root)
    controller_sha = production_controller_sha(root)
    ticket = strict_json(production_read_owned(root, "run-ticket.json"), "run ticket")
    if ticket != {
        "attempt_id": root.name,
        "controller_sha256": controller_sha,
        "command": "run",
    }:
        raise R2Error("CONTROLLER", "run ticket identity differs")
    catalogs = [production_catalog(root, name) for name in CATALOG_FILES]
''',
    )
    text = replace(
        text,
        '''            validation = production_validate(validation_args)
            assert validation["tools"] == len(KNOWN)
            create_owned(root, "dispatch-validation.json", cbytes(validation) + b"\\n")
''',
        '''            validation = production_validate(validation_args)
            assert validation["tools"] == len(KNOWN)
            ticket_bytes = production_read_owned(root, "run-ticket.json")
            replace_probe_file(root / "run-ticket.json", b"tampered-ticket\\n")
            try:
                production_validate(validation_args)
            except R2Error as exc:
                assert exc.category in {"JSON", "CONTROLLER"}
            else:
                raise AssertionError("tampered run ticket accepted")
            replace_probe_file(root / "run-ticket.json", ticket_bytes)
            create_owned(root, "dispatch-validation.json", cbytes(validation) + b"\\n")
''',
    )
    text = replace(
        text,
        '''    assert positive == 6
    assert negative == 85
    print("R3_PROTOCOL_R20_1_GREEN positive=6 negative=85")
''',
        '''    assert positive == 6
    assert negative == 85
    production_failure_diagnostics_probe()
    print("R3_PROTOCOL_R20_1_GREEN positive=6 negative=85")
''',
    )

    result = text.encode("utf-8")
    if (
        len(result) != OUTPUT_BYTES
        or result.count(b"\n") != OUTPUT_LINES
        or hashlib.sha256(result).hexdigest() != OUTPUT_SHA256
    ):
        raise RuntimeError("generated R3 controller identity differs")
    output.parent.mkdir(mode=0o700, parents=False, exist_ok=False)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(result)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_size != OUTPUT_BYTES
        ):
            raise RuntimeError("unsafe generated controller")
    finally:
        os.close(fd)
    print(f"R3_CONTROLLER_GREEN sha256={OUTPUT_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Appendix C: exact R3 live-protocol generator

Extract this fence byte-for-byte to an owned native-0600 file in a disposable mode-0700
`/private/tmp` root. Its identity is 742 lines, 30,639 bytes, SHA-256
`828aaebc53cda2fe628d0730fd5ce4bf98da3222e883cea66b373315234c80ba`.
Run it only against the frozen Task 7 brief; the output must be 820 lines, 36,189 bytes,
SHA-256 `6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_SHA256 = "fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b"
SLICE_SHA256 = "06940a887e30674eb0f0c3127aea2aafdc2c9d4031caeee6fbc21d6d6e64d0c0"
OUTPUT_SHA256 = "6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2"
OUTPUT_LINES = 820
OUTPUT_BYTES = 36189
SOURCE_DEV = 16777232
SOURCE_INO = 295274948
SOURCE_SIZE = 538571


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"protocol anchor count differs: {old[:80]!r}")
    return text.replace(old, new)


def identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def read_source(path: Path) -> bytes:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("Task 7 brief path is not canonical")
    parent = path.parent
    parent_before = os.lstat(parent)
    if (
        stat.S_ISLNK(parent_before.st_mode)
        or not stat.S_ISDIR(parent_before.st_mode)
        or parent_before.st_uid != os.getuid()
        or stat.S_IMODE(parent_before.st_mode) != 0o700
    ):
        raise RuntimeError("Task 7 brief parent is unsafe")
    parent_id = identity(parent_before)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    if identity(os.fstat(parent_fd)) != parent_id:
        os.close(parent_fd)
        raise RuntimeError("Task 7 brief parent changed before open")
    before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    expected = (SOURCE_DEV, SOURCE_INO, os.getuid(), 0o600, 1, SOURCE_SIZE)
    if identity(before)[:6] != expected or not stat.S_ISREG(before.st_mode):
        os.close(parent_fd)
        raise RuntimeError("Task 7 brief identity differs")
    fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        if identity(opened) != identity(before):
            raise RuntimeError("Task 7 brief changed before open")
        chunks: list[bytes] = []
        remaining = SOURCE_SIZE
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                raise RuntimeError("Task 7 brief short read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise RuntimeError("Task 7 brief exceeds bound size")
        if identity(os.fstat(fd)) != identity(opened):
            raise RuntimeError("Task 7 brief changed during read")
        if (
            identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != identity(before)
            or identity(os.fstat(parent_fd)) != parent_id
            or identity(os.lstat(parent)) != parent_id
        ):
            raise RuntimeError("Task 7 brief path changed during read")
    finally:
        os.close(fd)
        os.close(parent_fd)
    if identity(os.lstat(path)) != identity(before):
        raise RuntimeError("Task 7 brief path changed during read")
    return b"".join(chunks)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_r3_live_protocol.py OLD_BRIEF OUTPUT")
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    raw = read_source(source)
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("frozen Task 7 brief differs")
    lines = raw.decode().splitlines(keepends=True)
    text = "".join(lines[12298:12912])
    if hashlib.sha256(text.encode()).hexdigest() != SLICE_SHA256:
        raise RuntimeError("frozen live-protocol slice differs")
    text = text[text.index("<!-- R2_CONTROLLER_END -->") + len("<!-- R2_CONTROLLER_END -->\n"):]
    text = text.replace("import ast\n", "", 1)

    order_start = text.index("ORDER_ANCHORS = (")
    order_end = text.index("markers = {", order_start)
    text = text[:order_start] + text[order_end:]

    controller_marker = '''    "r2_controller.py": (
        b"<!-- R2_CONTROLLER_BEGIN -->\\n````python\\n",
        b"````\\n<!-- R2_CONTROLLER_END -->",
    ),
'''
    controller_expected = '''    "r2_controller.py": (
        6193,
        254319,
        "cc325e471aa0d1a0349deade58d0f7517575c35d901fb99f00ee1cc4de7f640a",
    ),
'''
    text = once(text, controller_marker, "")
    text = once(text, controller_expected, "")
    ast_start = text.index('    controller_tree = ast.parse(payloads["r2_controller.py"]')
    ast_end = text.index("    for name, payload in payloads.items():", ast_start)
    text = text[:ast_start] + text[ast_end:]

    old_probe = '''PROBE_OUTPUT="$(r2_python "$ATTEMPT_ROOT/r2_controller.py" probe)"
test "$PROBE_OUTPUT" = 'R2_PROTOCOL_R20_1_GREEN positive=6 negative=85'
printf '%s\\n' "$PROBE_OUTPUT"
PRIVATE_TMP_PROBE="$(TMPDIR=/private/tmp r2_python \\
  "$ATTEMPT_ROOT/r2_controller.py" probe)"
test "$PRIVATE_TMP_PROBE" = 'R2_PROTOCOL_R20_1_GREEN positive=6 negative=85'
printf '%s\\n' "$PRIVATE_TMP_PROBE"
'''
    new_probe = '''PROBE_OUTPUT="$(TMPDIR=/private/tmp r3_python "$ATTEMPT_ROOT/r3_controller.py" probe)"
EXPECTED_PROBE=$'R3_FAILURE_DIAGNOSTICS_GREEN distinct=2 ordered=1 persisted_before_ack=1\\nR3_PROTOCOL_R20_1_GREEN positive=6 negative=85'
test "$PROBE_OUTPUT" = "$EXPECTED_PROBE"
printf '%s\\n' "$PROBE_OUTPUT"
'''
    text = once(text, old_probe, new_probe)

    for old, new in (
        ("R2_", "R3_"),
        ("r2_", "r3_"),
        ("r2-", "r3-"),
        ("r2_controller.py", "r3_controller.py"),
        ("final-retest-r2", "final-retest-r3"),
        ("task-7-report.md", "task-7-followup-1-report.md"),
        ("cc325e471aa0d1a0349deade58d0f7517575c35d901fb99f00ee1cc4de7f640a",
         "7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a"),
    ):
        text = text.replace(old, new)

    for marker in ("FIXTURE_SETUP", "MODEL_BODY", "CLI_BODY"):
        text = text.replace(f"R3_{marker}_BEGIN", f"R2_{marker}_BEGIN")
        text = text.replace(f"R3_{marker}_END", f"R2_{marker}_END")

    text = once(
        text,
        "# Exported because the final fence is a child `/bin/bash`, not this PTY.\n",
        "# Exported because every continuation fence runs in this same persistent PTY.\n",
    )
    text = once(
        text,
        "Continue in that same fresh Task 7 implementer's persistent PTY/controller shell.",
        "Continue in the same R3 follow-up implementer's persistent PTY/controller shell.",
    )

    text = once(
        text,
        '''if os.path.lexists(path):
    info = os.lstat(path)
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RuntimeError("existing render scratch is unsafe")
print(f"R3_SCRATCH_GREEN path={path}")
''',
        '''if not os.path.lexists(path):
    os.mkdir(path, 0o700)
info = os.lstat(path)
if (
    not stat.S_ISDIR(info.st_mode)
    or stat.S_ISLNK(info.st_mode)
    or info.st_uid != os.getuid()
    or stat.S_IMODE(info.st_mode) != 0o700
):
    raise RuntimeError("render scratch is unsafe")
print(f"R3_SCRATCH_GREEN path={path}")
''',
    )

    text = once(
        text,
        '''test -n "${ATTEMPT_ROOT-}" || { echo 'STOP: copy the allocation block exact attempt root' >&2; exit 1; }
test -n "${BRIEF_SHA256-}" || { echo 'STOP: copy the controller-recorded Task 7 brief SHA-256' >&2; exit 1; }
test -n "${BRIEF_DEV-}" || { echo 'STOP: copy the controller-recorded Task 7 brief device' >&2; exit 1; }
test -n "${BRIEF_INO-}" || { echo 'STOP: copy the controller-recorded Task 7 brief inode' >&2; exit 1; }
test -n "${BLENDER_BIN-}" || { echo 'STOP: absolute Blender 5.2-or-newer executable required' >&2; exit 1; }
test -n "${MCP_SOURCE_DIR-}" || { echo 'STOP: absolute pinned official source checkout required' >&2; exit 1; }
''',
        '''ATTEMPT_ROOT=/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001
BRIEF_SHA256=fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b
BRIEF_DEV=16777232
BRIEF_INO=295274948
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
MCP_SOURCE_DIR=/Users/yeminjie/blender_mcp
''',
    )
    text = once(text, 'UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"\n', 'UV_BIN=/Users/yeminjie/.local/bin/uv\n')
    text = once(text, 'UVX_BIN="${UVX_BIN:-$HOME/.local/bin/uvx}"\n', 'UVX_BIN=/Users/yeminjie/.local/bin/uvx\n')
    text = once(text, 'CODEX_BIN="${CODEX_BIN:-$(command -v codex)}"\n', 'CODEX_BIN=/Applications/ChatGPT.app/Contents/Resources/codex\n')
    text = once(text, 'CODEX_CONFIG="${CODEX_CONFIG:-${CODEX_HOME:-$HOME/.codex}/config.toml}"\n', 'CODEX_CONFIG=/Users/yeminjie/.codex/config.toml\n')
    text = once(
        text,
        '''case "$ATTEMPT_ROOT" in
  "$FEATURE_ROOT"/.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-[0-9][0-9][0-9][0-9]) ;;
  *) echo 'STOP: selected attempt binding differs' >&2; exit 1 ;;
esac
test "${ATTEMPT_ROOT##*/}" != attempt-0000
''',
        'test "$ATTEMPT_ROOT" = "$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001"\n',
    )

    text = once(
        text,
        'print(\n    "R3_INPUTS_GREEN controller=7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a "\n',
        'print(\n    "R3_INPUTS_GREEN "\n',
    )

    text = once(
        text,
        'CONTROLLER_SHA256=7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a\n',
        '''CONTROLLER_SHA256=7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a
R3_SCRATCH="${R3_SCRATCH:?set the canonical scratch from bound GUI preflight}"
R3_LISTENER_PID="${R3_LISTENER_PID:?set the sole listener PID from bound GUI preflight}"
R3_LISTENER_START="${R3_LISTENER_START:?set the bound listener start time from GUI preflight}"
R3_LISTENER_IMAGE="${R3_LISTENER_IMAGE:?set the bound listener executable device/inode from GUI preflight}"
R3_PLAN_COMMIT="${R3_PLAN_COMMIT:?copy the bound Plan commit from the follow-up brief}"
R3_PLAN_SHA256="${R3_PLAN_SHA256:?copy the bound Plan SHA-256 from the follow-up brief}"
R3_RUNBOOK_COMMIT="${R3_RUNBOOK_COMMIT:?copy the bound runbook commit from the follow-up brief}"
R3_RUNBOOK_SHA256="${R3_RUNBOOK_SHA256:?copy the bound runbook SHA-256 from the follow-up brief}"
R3_REPORT_DEV="${R3_REPORT_DEV:?copy the bound follow-up report device from the brief}"
R3_REPORT_INO="${R3_REPORT_INO:?copy the bound follow-up report inode from the brief}"
R3_REPORT_PATH="$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/task-7-followup-1-report.md"
PLAN_REL=docs/superpowers/plans/2026-08-13-official-blender-mcp-r3-exception-diagnostics.md
RUNBOOK_REL=docs/use-official-blender-mcp.md
''',
    )
    text = once(
        text,
        'export CODEX_BIN CODEX_CONFIG CONTROLLER_SHA256\n',
        '''export CODEX_BIN CODEX_CONFIG CONTROLLER_SHA256 R3_SCRATCH R3_LISTENER_PID
export R3_LISTENER_START R3_LISTENER_IMAGE
export R3_PLAN_COMMIT R3_PLAN_SHA256 R3_RUNBOOK_COMMIT R3_RUNBOOK_SHA256
export R3_REPORT_DEV R3_REPORT_INO R3_REPORT_PATH
r3_listener_image() {
  /usr/sbin/lsof -a -p "$1" -d txt -F fDin 2>/dev/null | /usr/bin/awk -v want="$BLENDER_BIN" '
    function emit() {
      if (active && name == want && dev != "" && ino != "") print dev "|" ino
    }
    $0 == "ftxt" { emit(); active=1; dev=""; ino=""; name=""; next }
    active && substr($0,1,1) == "D" { dev=substr($0,2); next }
    active && substr($0,1,1) == "i" { ino=substr($0,2); next }
    active && substr($0,1,1) == "n" { name=substr($0,2); next }
    END { emit() }
  '
}
r3_preflight_binding() {
  case "$R3_LISTENER_PID" in ''|*[!0-9]*) return 1 ;; esac
  test "$R3_LISTENER_PID" -gt 0
  test "$(/usr/sbin/lsof -nP -t -iTCP:9876 -sTCP:LISTEN)" = "$R3_LISTENER_PID"
  test "$(/bin/ps -p "$R3_LISTENER_PID" -o lstart= | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')" = "$R3_LISTENER_START"
  test "$(r3_listener_image "$R3_LISTENER_PID")" = "$R3_LISTENER_IMAGE"
  case "$R3_SCRATCH" in /*/blender_mcp) ;; *) return 1 ;; esac
}
r3_repo_binding() {
  test "$(git -C "$FEATURE_ROOT" rev-parse HEAD)" = "$R3_RUNBOOK_COMMIT"
  test -z "$(git -C "$FEATURE_ROOT" status --porcelain=v1 --untracked-files=all)"
  test "$(git -C "$FEATURE_ROOT" rev-list --parents -n 1 "$R3_RUNBOOK_COMMIT" | /usr/bin/awk '{print NF}')" = 2
  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_RUNBOOK_COMMIT^")" = "$R3_PLAN_COMMIT"
  test "$(git -C "$FEATURE_ROOT" diff-tree --no-commit-id --name-only -r "$R3_PLAN_COMMIT")" = "$PLAN_REL"
  test "$(git -C "$FEATURE_ROOT" diff-tree --no-commit-id --name-only -r "$R3_RUNBOOK_COMMIT")" = "$RUNBOOK_REL"
  test "$(/usr/bin/shasum -a 256 "$FEATURE_ROOT/$PLAN_REL" | /usr/bin/awk '{print $1}')" = "$R3_PLAN_SHA256"
  test "$(/usr/bin/shasum -a 256 "$FEATURE_ROOT/$RUNBOOK_REL" | /usr/bin/awk '{print $1}')" = "$R3_RUNBOOK_SHA256"
}
r3_preflight_binding
r3_repo_binding
r3_report_append() {
  r3_python - "$R3_REPORT_PATH" "$@" 8<&8 <<'PY'
import os, stat, sys
path = sys.argv[1]
opened = os.fstat(8)
current = os.lstat(path)
expected = (int(os.environ["R3_REPORT_DEV"]), int(os.environ["R3_REPORT_INO"]))
if (
    (opened.st_dev, opened.st_ino) != expected
    or (current.st_dev, current.st_ino) != expected
    or not stat.S_ISREG(opened.st_mode)
    or stat.S_IMODE(opened.st_mode) != 0o600
    or opened.st_uid != os.getuid()
    or opened.st_nlink != 1
):
    raise RuntimeError("bound follow-up report differs before append")
payload = "".join(line + "\\n" for line in sys.argv[2:]).encode()
os.lseek(8, 0, os.SEEK_END)
view = memoryview(payload)
while view:
    written = os.write(8, view)
    if written <= 0:
        raise RuntimeError("short follow-up report write")
    view = view[written:]
os.fsync(8)
after = os.fstat(8)
current_after = os.lstat(path)
if (
    (after.st_dev, after.st_ino) != expected
    or (current_after.st_dev, current_after.st_ino) != expected
    or after.st_size != opened.st_size + len(payload)
):
    raise RuntimeError("bound follow-up report changed after append")
PY
}
r3_finish_review() {
  test "$#" = 2 || return 2
  REVIEW_KIND="$1"
  REVIEW_VERDICT="$2"
  test "$ACTUAL_RUN_COUNT" = 1 || return 2
  test -z "$CLEANUP_ERRORS" || return 2
  case "$REVIEW_KIND:$R3_FLOW" in
    failure:direct_review|success:success) ;;
    *) return 2 ;;
  esac
  case "$REVIEW_VERDICT" in APPROVED|REJECTED) ;; *) return 2 ;; esac
  FINAL_STATUS=BLOCKED
  if test "$REVIEW_KIND:$REVIEW_VERDICT" = success:APPROVED; then
    FINAL_STATUS=PASS
  fi
  r3_report_append "review_kind: $REVIEW_KIND" "review_verdict: $REVIEW_VERDICT" \
    "actual_run_count: $ACTUAL_RUN_COUNT" "STATUS: $FINAL_STATUS" || return 2
  exec 8>&-
  R3_FLOW=terminal
}
''',
    )
    text = text.replace("four marked fences", "three marked payload fences")
    text = text.replace("four marker names", "three payload marker names")
    text = text.replace("all four payloads -- including the controller", "all three payloads")
    text = text.replace(
        "Run the following in the same persistent `/bin/bash` PTY after copying the allocation\n"
        "block's one printed `ATTEMPT_ROOT`.",
        "After bound GUI preflight, run the following in that same persistent `/bin/bash` PTY.",
    )
    text = text.replace("numbered attempt immutable", "sole follow-up attempt immutable")
    text = text.replace(
        "A fixture or GUI-preflight failure invalidates this numbered\n"
        "attempt; close FD 9, retain its incomplete/rejected journal and external recorder\n"
        "diagnostics unchanged, and start a new numbered attempt after fixing the cause:",
        "A fixture or GUI-preflight failure invalidates this sole attempt; close FD 9, retain\n"
        "its incomplete/rejected journal and external recorder diagnostics unchanged, and stop:",
    )
    text = once(
        text,
        '    if set(os.listdir(root_fd)):\n        raise RuntimeError("attempt root must be empty before extraction")\n',
        '    if set(os.listdir(root_fd)) != {"r3_controller.py"}:\n        raise RuntimeError("attempt root must contain only the generated controller")\n',
    )
    text = once(
        text,
        '    if set(os.listdir(root_fd)) != set(markers):\n',
        '    if set(os.listdir(root_fd)) != set(markers) | {"r3_controller.py"}:\n',
    )
    text = once(
        text,
        '''if hashlib.sha256(brief).hexdigest() != os.environ["BRIEF_SHA256"]:
    raise RuntimeError("Task 7 brief digest differs from controller allocation")
''',
        '''if hashlib.sha256(brief).hexdigest() != os.environ["BRIEF_SHA256"]:
    raise RuntimeError("Task 7 brief digest differs from controller allocation")
controller, _ = gate_snapshot(
    root / "r3_controller.py", label="R3 controller", limit=8 * 1024 * 1024, mode=0o600,
)
if hashlib.sha256(controller).hexdigest() != CONTROLLER_SHA256:
    raise RuntimeError("generated R3 controller differs")
''',
    )

    text = once(
        text,
        '  --audit-fd 9 || R3_RUN_EXIT=$?\n',
        '  --audit-fd 9 \\\n  --audit-fifo "$EVENT_FIFO" \\\n  --recorder-pid "$RECORDER_PID" \\\n  --recorder-start "$RECORDER_START" \\\n  --recorder-uv-bin "$UV_BIN" \\\n  --recorder-mcp-editable "$MCP_SOURCE_DIR/mcp" || R3_RUN_EXIT=$?\n',
    )
    text = text.replace(
        "Any failure\nsuppresses this marker, preserves the selected attempt byte-for-byte, discards the\n"
        "unsaved GUI without saving and restarts only after fix-forward in a new numbered root.",
        "Any failure suppresses this marker, preserves the sole attempt byte-for-byte, discards\n"
        "the unsaved GUI without saving, and stops without retry.",
    )
    run_tail = '  --recorder-mcp-editable "$MCP_SOURCE_DIR/mcp" || R3_RUN_EXIT=$?\nexec 9>&-\n'
    text = once(
        text,
        run_tail,
        '''  --recorder-mcp-editable "$MCP_SOURCE_DIR/mcp" || R3_RUN_EXIT=$?
```

Send no further stdin until the controller requests and receives the authorized ACK.
Only after that terminal permits continuation, paste this next fence in the same PTY:

```bash
exec 9>&-
''',
    )
    text = once(
        text,
        '''exec 9>&-
RECORDER_FD_OPEN=0
RECORDER_EXIT=0
wait "$RECORDER_PID" || RECORDER_EXIT=$?
RECORDER_PID=''
trap - EXIT
test "$R3_RUN_EXIT" = 0
test "$RECORDER_EXIT" = 0
test ! -s "$RECORDER_STDERR"
printf 'R3_DISPATCH_AND_JOURNAL_GREEN attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
''',
        '''exec 9>&-
RECORDER_FD_OPEN=0
RECORDER_EXIT=0
wait "$RECORDER_PID" || RECORDER_EXIT=$?
RECORDER_PID=''
trap - EXIT ERR
set +e +u
CLEANUP_ERRORS=''
record_cleanup_error() { CLEANUP_ERRORS="${CLEANUP_ERRORS}$1;"; }
test "$RECORDER_EXIT" = 0 || record_cleanup_error recorder_exit
test ! -s "$RECORDER_STDERR" || record_cleanup_error recorder_stderr
REPORT_READY=0
if test -f "$R3_REPORT_PATH" && test ! -L "$R3_REPORT_PATH" && exec 8<>"$R3_REPORT_PATH"; then
  if "$UV_BIN" run --quiet --no-project --python 3.13 python - "$R3_REPORT_PATH" 8<&8 <<'PY'
import os, stat, sys
path = sys.argv[1]
opened = os.fstat(8)
current = os.lstat(path)
expected = (int(os.environ["R3_REPORT_DEV"]), int(os.environ["R3_REPORT_INO"]))
if (
    (opened.st_dev, opened.st_ino) != expected
    or (current.st_dev, current.st_ino) != expected
    or not stat.S_ISREG(opened.st_mode)
    or stat.S_IMODE(opened.st_mode) != 0o600
    or opened.st_uid != os.getuid()
    or opened.st_nlink != 1
):
    raise RuntimeError("bound follow-up report differs")
PY
  then
    REPORT_READY=1
  else
    record_cleanup_error report_identity
  fi
else
  record_cleanup_error report_open
fi
LISTENER_NOW="$(/usr/sbin/lsof -nP -t -iTCP:9876 -sTCP:LISTEN 8>&- || true)"
LISTENER_START_NOW="$(/bin/ps -p "$R3_LISTENER_PID" -o lstart= 2>/dev/null 8>&- | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' 8>&-)"
LISTENER_IMAGE_NOW="$(r3_listener_image "$R3_LISTENER_PID" 8>&-)"
LISTENER_OWNED=0
if kill -0 "$R3_LISTENER_PID" 2>/dev/null && \
   test "$LISTENER_START_NOW" = "$R3_LISTENER_START" && \
   test "$LISTENER_IMAGE_NOW" = "$R3_LISTENER_IMAGE"; then
  LISTENER_OWNED=1
  if test -n "$LISTENER_NOW" && test "$LISTENER_NOW" != "$R3_LISTENER_PID"; then
    record_cleanup_error listener_identity
  fi
  kill "$R3_LISTENER_PID" 2>/dev/null || record_cleanup_error listener_kill
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$R3_LISTENER_PID" 2>/dev/null || break
    /bin/sleep 1 8>&-
  done
elif kill -0 "$R3_LISTENER_PID" 2>/dev/null || test -n "$LISTENER_NOW"; then
  record_cleanup_error listener_identity
fi
OWNED_AFTER=''
if test "$LISTENER_OWNED" = 1 && kill -0 "$R3_LISTENER_PID" 2>/dev/null; then
  OWNED_AFTER="pid:$R3_LISTENER_PID"
fi
PORT_AFTER="$(/usr/sbin/lsof -nP -t -iTCP:9876 -sTCP:LISTEN 8>&- || true)"
if test -n "$PORT_AFTER"; then
  OWNED_AFTER="${OWNED_AFTER}${OWNED_AFTER:+,}port:$PORT_AFTER"
fi
test -z "$OWNED_AFTER" || record_cleanup_error owned_processes
JOURNAL_SHA256='UNAVAILABLE'
if test -f "$JOURNAL" && test ! -L "$JOURNAL"; then
  JOURNAL_SHA256="$(/usr/bin/shasum -a 256 "$JOURNAL" 2>/dev/null 8>&- | /usr/bin/awk '{print $1}' 8>&-)" || {
    JOURNAL_SHA256='UNAVAILABLE'
    record_cleanup_error journal_read
  }
fi
if [[ ! "$JOURNAL_SHA256" =~ ^[0-9a-f]{64}$ ]]; then record_cleanup_error journal_sha; fi
ACTUAL_RUN_COUNT=0
ACTUAL_RUN_COUNT="$("$UV_BIN" run --quiet --no-project --python 3.13 python - \
    "$ATTEMPT_ROOT/run-ticket.json" "$CONTROLLER_SHA256" 8>&- <<'PY'
import json, os, stat, sys
path, controller_sha = sys.argv[1:]
info = os.lstat(path)
if (
    not stat.S_ISREG(info.st_mode)
    or stat.S_ISLNK(info.st_mode)
    or info.st_uid != os.getuid()
    or stat.S_IMODE(info.st_mode) != 0o600
    or info.st_nlink != 1
    or info.st_size > 4096
):
    raise RuntimeError("unsafe run ticket")
def identity(value):
    return (
        value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode),
        value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns,
    )
before = identity(info)
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    if identity(os.fstat(fd)) != before:
        raise RuntimeError("run ticket changed before open")
    chunks = []
    remaining = info.st_size
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            raise RuntimeError("short run ticket read")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(fd, 1):
        raise RuntimeError("run ticket grew during read")
    if identity(os.fstat(fd)) != before:
        raise RuntimeError("run ticket changed during read")
finally:
    os.close(fd)
raw = b"".join(chunks)
if identity(os.stat(path, follow_symlinks=False)) != before:
    raise RuntimeError("run ticket changed")
def pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise RuntimeError("duplicate run ticket key")
        value[key] = item
    return value
value = json.loads(
    raw, object_pairs_hook=pairs,
    parse_constant=lambda item: (_ for _ in ()).throw(RuntimeError(item)),
)
expected = {
    "attempt_id": "attempt-0001",
    "controller_sha256": controller_sha,
    "command": "run",
}
canonical = json.dumps(
    expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode() + b"\\n"
if value != expected or raw != canonical:
    raise RuntimeError("run ticket content differs")
print(1)
PY
  )" || { ACTUAL_RUN_COUNT=0; record_cleanup_error ticket_identity; }
if test "$REPORT_READY" = 1; then
  r3_report_append "journal_sha256: $JOURNAL_SHA256" \\
    "owned_processes_after_cleanup: [${OWNED_AFTER}]" \\
    "cleanup_errors: ${CLEANUP_ERRORS:-NONE}" || REPORT_READY=0
fi
if test "$REPORT_READY" != 1; then
  echo 'STOP: terminal report unavailable after cleanup' >&2
  exit 1
fi
R3_FLOW=success
if test "$R3_RUN_EXIT" != 0; then
  if test "$ACTUAL_RUN_COUNT" = 1 && test -z "$CLEANUP_ERRORS" && \\
     test -f "$ATTEMPT_ROOT/direct-session-failure.json" && \\
     test -f "$ATTEMPT_ROOT/direct-session.stderr" && \\
     test -f "$ATTEMPT_ROOT/direct-failure-ack.json"; then
    r3_report_append 'failure_review_pending: 1'
    printf 'R3_DIRECT_FAILURE_REVIEW_REQUIRED attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
    R3_FLOW=direct_review
  else
    r3_report_append "actual_run_count: $ACTUAL_RUN_COUNT" 'STATUS: BLOCKED'
    printf 'R3_UNVERIFIED_FAILURE_BLOCKED attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
    exec 8>&-
    exit 0
  fi
fi
if test "$R3_FLOW" = success; then
  if test -n "$CLEANUP_ERRORS"; then
    r3_report_append "actual_run_count: $ACTUAL_RUN_COUNT" 'STATUS: BLOCKED'
    exec 8>&-
    printf 'R3_SUCCESS_CLEANUP_BLOCKED attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
    exit 0
  fi
  printf 'R3_DISPATCH_AND_JOURNAL_GREEN attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
''',
    )
    text = once(
        text,
        '''r3_python "$ATTEMPT_ROOT/r3_controller.py" validate \\
  --root "$ATTEMPT_ROOT" \\
  --config "$CODEX_CONFIG" \\
  --output dispatch-validation.json
r3_python "$ATTEMPT_ROOT/r3_controller.py" finalize \\
  --root "$ATTEMPT_ROOT" \\
  --config "$CODEX_CONFIG"
''',
        '''VALIDATE_EXIT=0
r3_python "$ATTEMPT_ROOT/r3_controller.py" validate \\
  --root "$ATTEMPT_ROOT" \\
  --config "$CODEX_CONFIG" \\
  --output dispatch-validation.json 8>&- || VALIDATE_EXIT=$?
FINALIZE_EXIT=0
if test "$VALIDATE_EXIT" = 0; then
  r3_python "$ATTEMPT_ROOT/r3_controller.py" finalize \\
    --root "$ATTEMPT_ROOT" \\
    --config "$CODEX_CONFIG" 8>&- || FINALIZE_EXIT=$?
fi
if test "$VALIDATE_EXIT" != 0 || test "$FINALIZE_EXIT" != 0; then
  r3_report_append "postrun_validation_exit: $VALIDATE_EXIT/$FINALIZE_EXIT" \\
    "actual_run_count: $ACTUAL_RUN_COUNT" 'STATUS: BLOCKED'
  exec 8>&-
  printf 'R3_POSTRUN_VALIDATION_BLOCKED attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
  exit 0
fi
printf 'R3_POSTRUN_VALIDATION_GREEN attempt=%s\\n' "${ATTEMPT_ROOT##*/}"
fi
''',
    )
    text = once(text, "R3_RUN_EXIT=0\n", "r3_preflight_binding\nr3_repo_binding\nR3_RUN_EXIT=0\n")
    text = once(
        text,
        '"$UVX_BIN" --quiet ruff@0.16.2 check --no-cache --isolated --select E4,E7,E9,F \\\n',
        '"$UVX_BIN" --quiet ruff@0.16.2 check --no-cache --isolated --target-version py313 --select E4,E7,E9,F \\\n',
    )
    text = once(
        text,
        '''r3_python "$AUDIT_SCRIPT" record --output "$JOURNAL" \\
  <"$EVENT_FIFO" 2>"$RECORDER_STDERR" &
''',
        '''"$UV_BIN" run --quiet --no-project --python 3.13 \\
  --with 'mcp[cli]>=1.2.0,<2' \\
  --with-editable "$MCP_SOURCE_DIR/mcp" \\
  python "$AUDIT_SCRIPT" record --output "$JOURNAL" \\
  <"$EVENT_FIFO" 2>"$RECORDER_STDERR" &
''',
    )
    text = once(
        text,
        '''RECORDER_PID=$!
exec 9>"$EVENT_FIFO"
''',
        '''RECORDER_PID=$!
RECORDER_START="$(/bin/ps -p "$RECORDER_PID" -o lstart= | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
test -n "$RECORDER_START"
exec 9>"$EVENT_FIFO"
''',
    )
    text = text.replace(
        "Now use **Computer Use** for the GUI boundary.",
        "GUI preflight was completed and bound before attempt allocation; use **Computer Use** only to recheck that boundary.",
    )
    text = text.replace(
        "First record the sole old\n`127.0.0.1:9876` listener PID. End the old Blender process without saving and wait\n"
        "until the listener is absent. Through the visible UI/Terminal, launch the exact\n"
        "`BLENDER_BIN` with `--factory-startup`, enable the already-installed official extension\n"
        "if needed, and require one different listener PID.",
        "Require the same sole preflight-bound `127.0.0.1:9876` listener PID and factory-startup Blender; do not relaunch or replace either.",
    )
    text = text.replace(
        "Set `R3_SCRATCH` in\nthe persistent PTY to `realpath(bpy.app.tempdir)/blender_mcp`.",
        "Require `realpath(bpy.app.tempdir)/blender_mcp` equals the already bound `R3_SCRATCH`.",
    )
    text = text.replace("reused PID", "changed PID")

    result = text.encode()
    if (
        len(result) != OUTPUT_BYTES
        or result.count(b"\n") != OUTPUT_LINES
        or hashlib.sha256(result).hexdigest() != OUTPUT_SHA256
    ):
        raise RuntimeError("generated R3 live protocol identity differs")
    output = Path(os.path.abspath(output))
    parent = output.parent
    parent_info = os.lstat(parent)
    if (
        Path(os.path.realpath(parent)) != parent
        or stat.S_ISLNK(parent_info.st_mode)
        or not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != os.getuid()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
    ):
        raise RuntimeError("unsafe generated live protocol parent")
    parent_id = identity(parent_info)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    if identity(os.fstat(parent_fd)) != parent_id:
        os.close(parent_fd)
        raise RuntimeError("generated live protocol parent changed")
    fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    parent_after_create = identity(os.fstat(parent_fd))
    if identity(os.lstat(parent)) != parent_after_create:
        os.close(fd)
        os.close(parent_fd)
        raise RuntimeError("generated live protocol parent changed during create")
    try:
        view = memoryview(result)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RuntimeError("short write for generated live protocol")
            view = view[written:]
        os.fsync(fd)
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_size != OUTPUT_BYTES
        ):
            raise RuntimeError("unsafe generated live protocol")
        file_id = identity(info)
        if (
            identity(os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)) != file_id
            or identity(os.fstat(parent_fd)) != parent_after_create
            or identity(os.lstat(parent)) != parent_after_create
        ):
            raise RuntimeError("generated live protocol changed after write")
    finally:
        os.close(fd)
        os.close(parent_fd)
    print(len(result.splitlines()), len(result), hashlib.sha256(result).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact terminal direct-failure validator

Extract this fence byte-for-byte to an owned native-0600 file in a disposable mode-0700
`/private/tmp` root and run it with uv Python 3.13. Its exact identity is 422 lines,
18,969 bytes, SHA-256
`791d4e0b49b79f279608fe04e8e46dc1cc0d8b5e9596c21b27adb4a58e015f84`.
It is read-only against the durable attempt.

```python
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import uuid
from datetime import datetime
from pathlib import Path


HEX64 = re.compile(r"[0-9a-f]{64}")
QUALIFIED = re.compile(r"(?:[A-Za-z_]\w*\.)+[A-Za-z_]\w*")
BINDINGS: list[tuple[Path, tuple[int, int, int, int], tuple[int, int, int, int, int, int, int, int]]] = []


def cbytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()


def strict(data: bytes, label: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in items:
            if key in out:
                raise RuntimeError(f"{label}: duplicate key {key}")
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(RuntimeError(f"{label}: constant {x}")))


def parent_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode))


def leaf_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode),
        info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
    )


def owned(path: Path, mode: int, limit: int) -> bytes:
    path = Path(os.path.abspath(path))
    parent = path.parent
    if Path(os.path.realpath(parent)) != parent:
        raise RuntimeError(f"unsafe evidence parent: {parent}")
    parent_before = os.lstat(parent)
    parent_binding = parent_identity(parent_before)
    if (
        stat.S_ISLNK(parent_before.st_mode)
        or not stat.S_ISDIR(parent_before.st_mode)
        or parent_before.st_uid != os.getuid()
        or stat.S_IMODE(parent_before.st_mode) != 0o700
    ):
        raise RuntimeError(f"unsafe evidence parent: {parent}")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    if parent_identity(os.fstat(parent_fd)) != parent_binding:
        os.close(parent_fd)
        raise RuntimeError(f"evidence parent changed: {parent}")
    before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    identity = leaf_identity(before)
    if (
        stat.S_ISLNK(before.st_mode)
        or (not stat.S_ISDIR(before.st_mode) if mode == 0o700 else not stat.S_ISREG(before.st_mode))
        or before.st_uid != os.getuid()
        or stat.S_IMODE(before.st_mode) != mode
        or (mode == 0o600 and before.st_nlink != 1)
        or (mode == 0o600 and before.st_size > limit)
    ):
        os.close(parent_fd)
        raise RuntimeError(f"unsafe evidence path: {path}")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if mode == 0o700:
        flags |= os.O_DIRECTORY
    fd = os.open(path.name, flags, dir_fd=parent_fd)
    try:
        if leaf_identity(os.fstat(fd)) != identity:
            raise RuntimeError(f"evidence changed while opening: {path}")
        data = bytearray()
        if mode == 0o600:
            remaining = before.st_size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    raise RuntimeError(f"short evidence read: {path}")
                data.extend(chunk)
                remaining -= len(chunk)
            if os.read(fd, 1):
                raise RuntimeError(f"evidence grew while reading: {path}")
        after = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if any((
            leaf_identity(os.fstat(fd)) != identity,
            leaf_identity(after) != identity,
            parent_identity(os.fstat(parent_fd)) != parent_binding,
            parent_identity(os.lstat(parent)) != parent_binding,
        )):
            raise RuntimeError(f"evidence changed while reading: {path}")
        BINDINGS.append((path, parent_binding, identity))
        return bytes(data)
    finally:
        os.close(fd)
        os.close(parent_fd)


def recheck_all() -> None:
    for path, parent_binding, identity in BINDINGS:
        parent = path.parent
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if (
                parent_identity(os.fstat(parent_fd)) != parent_binding
                or parent_identity(os.lstat(parent)) != parent_binding
                or leaf_identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != identity
            ):
                raise RuntimeError(f"evidence package changed after read: {path}")
        finally:
            os.close(parent_fd)


def message(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"observed_bytes", "sha256", "retained_base64", "retained_sha256", "truncated", "render_error_type"}:
        raise RuntimeError("exception message schema differs")
    if (
        not isinstance(value["observed_bytes"], int)
        or isinstance(value["observed_bytes"], bool)
        or value["observed_bytes"] < 0
        or not isinstance(value["retained_base64"], str)
        or not isinstance(value["sha256"], str)
        or HEX64.fullmatch(value["sha256"]) is None
        or not isinstance(value["retained_sha256"], str)
        or HEX64.fullmatch(value["retained_sha256"]) is None
        or not isinstance(value["truncated"], bool)
    ):
        raise RuntimeError("exception message values differ")
    try:
        retained = base64.b64decode(value["retained_base64"], validate=True)
    except ValueError as exc:
        raise RuntimeError("exception retained bytes differ") from exc
    if (
        len(retained) > 8192
        or value["observed_bytes"] < len(retained)
        or value["retained_sha256"] != hashlib.sha256(retained).hexdigest()
        or not (
            value["render_error_type"] is None
            or isinstance(value["render_error_type"], str)
            and QUALIFIED.fullmatch(value["render_error_type"]) is not None
        )
    ):
        raise RuntimeError("exception retained byte bound differs")
    if not value["truncated"] and (
        value["observed_bytes"] != len(retained)
        or value["sha256"] != hashlib.sha256(retained).hexdigest()
    ):
        raise RuntimeError("complete exception message digest differs")
    if value["truncated"] is not (value["observed_bytes"] > len(retained)):
        raise RuntimeError("exception message truncation flag differs")
    if value["truncated"] and len(retained) != 8192:
        raise RuntimeError("truncated exception retention length differs")


def tree(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"limits", "node_count", "truncated", "root"}:
        raise RuntimeError("exception tree schema differs")
    if value["limits"] != {"max_depth": 16, "max_nodes": 256} or value["truncated"] is not False:
        raise RuntimeError("exception tree is not leaf-complete within limits")
    if not isinstance(value["node_count"], int) or isinstance(value["node_count"], bool):
        raise RuntimeError("exception node count type differs")
    group_types = {"builtins.ExceptionGroup", "builtins.BaseExceptionGroup"}
    root_value = value["root"]
    if (
        not isinstance(root_value, dict)
        or "children" not in root_value
        or not isinstance(root_value["children"], list)
        or not root_value["children"]
        or root_value.get("type") not in group_types
    ):
        raise RuntimeError("certified direct failure must be an exception group")
    count = 0
    stack: list[tuple[object, int]] = [(value["root"], 0)]
    while stack:
        node, depth = stack.pop()
        if not isinstance(node, dict) or set(node) not in ({"type", "message"}, {"type", "message", "children"}):
            raise RuntimeError("exception node schema differs")
        if (
            depth > 16
            or not isinstance(node["type"], str)
            or QUALIFIED.fullmatch(node["type"]) is None
        ):
            raise RuntimeError("exception node identity differs")
        message(node["message"])
        count += 1
        if count > 256:
            raise RuntimeError("exception node limit exceeded")
        children = node.get("children", [])
        if not isinstance(children, list) or not children:
            if "children" in node:
                raise RuntimeError("exception group has no children")
            if node["type"] in group_types:
                raise RuntimeError("exception group children are missing")
            continue
        if node["type"] not in group_types:
            raise RuntimeError("non-group exception carries children")
        stack.extend((child, depth + 1) for child in reversed(children))
    if value["node_count"] != count:
        raise RuntimeError("exception node count differs")


def journal(data: bytes, evidence_sha: str) -> dict[str, object]:
    rows = [strict(line, f"journal line {index}") for index, line in enumerate(data.splitlines(), 1)]
    if len(rows) != 4 or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError("failure journal length/schema differs")
    clock = rows[0].get("clock_id")
    try:
        parsed_clock = uuid.UUID(str(clock))
    except ValueError as exc:
        raise RuntimeError("journal clock UUID differs") from exc
    if parsed_clock.version != 4 or str(parsed_clock) != clock:
        raise RuntimeError("journal clock UUID differs")
    stack: list[tuple[str, str]] = []
    seen_events: set[tuple[str, str]] = set()
    last_ns = -1
    last_utc: datetime | None = None
    for index, row in enumerate(rows, 1):
        if (
            not isinstance(row.get("sequence"), int)
            or isinstance(row.get("sequence"), bool)
            or row.get("sequence") != index
            or row.get("clock_id") != clock
        ):
            raise RuntimeError("journal sequence/clock differs")
        now = row.get("monotonic_ns")
        if not isinstance(now, int) or isinstance(now, bool) or now <= last_ns:
            raise RuntimeError("journal monotonic clock differs")
        last_ns = now
        identity = (row.get("scope"), row.get("event_id"))
        scope, event_id = identity
        expected_event = {
            "task": "final-retest-r3",
            "stage": "final-retest-r3-tools",
        }.get(scope)
        if expected_event is not None:
            if event_id != expected_event:
                raise RuntimeError("journal event identity differs")
        else:
            raise RuntimeError("certified direct failure journal contains a call")
        if (
            row.get("stage") != "final-retest-r3"
            or not isinstance(row.get("attempt"), int)
            or isinstance(row.get("attempt"), bool)
            or row.get("attempt") != 0
            or row.get("recovery_of") is not None
        ):
            raise RuntimeError("journal R3 identity differs")
        raw_utc = row.get("recorded_at_utc")
        if not isinstance(raw_utc, str) or not raw_utc.endswith("Z"):
            raise RuntimeError("journal UTC syntax differs")
        try:
            parsed_utc = datetime.fromisoformat(raw_utc[:-1] + "+00:00")
        except ValueError as exc:
            raise RuntimeError("journal UTC syntax differs") from exc
        if last_utc is not None and parsed_utc <= last_utc:
            raise RuntimeError("journal UTC order differs")
        last_utc = parsed_utc
        if row.get("kind") == "start":
            if identity in seen_events:
                raise RuntimeError("journal event identity repeats")
            seen_events.add(identity)
            stack.append(identity)
        elif row.get("kind") == "end":
            if not stack or stack.pop() != identity:
                raise RuntimeError("journal scope nesting differs")
        else:
            raise RuntimeError("journal kind differs")
        common = {"attempt", "clock_id", "event_id", "kind", "monotonic_ns", "recorded_at_utc", "recovery_of", "scope", "sequence", "stage"}
        if row["kind"] == "start":
            expected_keys = common
        else:
            expected_keys = common | {"outcome", "issue_ids"}
            if row.get("outcome") == "fail":
                expected_keys |= {"symptom", "first_hypothesis"}
        if set(row) != expected_keys:
            raise RuntimeError("journal row keys differ")
        if row["kind"] == "end":
            if row.get("outcome") not in {"pass", "fail", "deviation"}:
                raise RuntimeError("journal outcome differs")
            issues = row.get("issue_ids")
            if (
                not isinstance(issues, list)
                or not all(isinstance(item, str) and item for item in issues)
                or issues != sorted(set(issues))
            ):
                raise RuntimeError("journal issue IDs differ")
            if row.get("outcome") == "fail" and (
                not isinstance(row.get("first_hypothesis"), str)
                or not row["first_hypothesis"].strip()
                or row["first_hypothesis"].strip() != row["first_hypothesis"]
            ):
                raise RuntimeError("journal hypothesis differs")
    if stack:
        raise RuntimeError("journal scopes remain open")
    if [(row.get("scope"), row.get("kind")) for row in rows[:2]] != [("task", "start"), ("stage", "start")]:
        raise RuntimeError("journal opening differs")
    final = rows[-2:]
    if [(row.get("scope"), row.get("outcome")) for row in final] != [("stage", "fail"), ("task", "fail")]:
        raise RuntimeError("journal failure closure differs")
    if any(row.get("issue_ids") != ["MODEL-PLAN-05"] for row in final):
        raise RuntimeError("certified direct failure issue IDs differ")
    symptoms = {row.get("symptom") for row in final}
    hypotheses = {row.get("first_hypothesis") for row in final}
    symptom = next(iter(symptoms), "")
    hypothesis = next(iter(hypotheses), "")
    ack = cbytes({
        "action": "failure_ack",
        "event_id": final[0]["event_id"],
        "response_sha256": evidence_sha,
        "first_hypothesis": hypothesis,
    }) + b"\n"
    if (
        len(symptoms) != 1
        or len(hypotheses) != 1
        or not isinstance(symptom, str)
        or len(symptom) > 2_000
        or evidence_sha not in symptom
        or not isinstance(hypothesis, str)
        or not hypothesis
        or len(ack) > 65_536
    ):
        raise RuntimeError("journal evidence/hypothesis binding differs")
    return {"rows": len(rows), "clock_id": clock, "symptom": symptom}


def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("--root", required=True)
    args.add_argument("--controller-sha256", required=True)
    value = args.parse_args()
    root = Path(os.path.abspath(value.root))
    if Path(os.path.realpath(root)) != root or root.name != "attempt-0001" or root.parent.name != "final-retest-r3":
        raise RuntimeError("failure attempt root differs")
    owned(root, 0o700, 0)
    controller = owned(root / "r3_controller.py", 0o600, 8 * 1024 * 1024)
    if hashlib.sha256(controller).hexdigest() != value.controller_sha256:
        raise RuntimeError("failure controller digest differs")
    ticket_raw = owned(root / "run-ticket.json", 0o600, 4096)
    ticket = strict(ticket_raw, "run ticket")
    if ticket != {
        "attempt_id": root.name,
        "controller_sha256": value.controller_sha256,
        "command": "run",
    }:
        raise RuntimeError("single run ticket differs")
    stderr = owned(root / "direct-session.stderr", 0o600, 4 * 1024 * 1024)
    raw = owned(root / "direct-session-failure.json", 0o600, 4 * 1024 * 1024)
    evidence_sha = hashlib.sha256(raw).hexdigest()
    ack_raw = owned(root / "direct-failure-ack.json", 0o600, 4096)
    ack = strict(ack_raw, "direct failure ack")
    if ack != {
        "attempt_id": root.name,
        "evidence_sha256": evidence_sha,
        "status": "accepted",
    }:
        raise RuntimeError("direct failure acknowledgement differs")
    evidence = strict(raw, "direct failure")
    if not isinstance(evidence, dict) or set(evidence) != {"exception_tree", "exception_tree_sha256", "stderr"}:
        raise RuntimeError("direct failure schema differs")
    tree(evidence["exception_tree"])
    if evidence["exception_tree_sha256"] != hashlib.sha256(cbytes(evidence["exception_tree"])).hexdigest():
        raise RuntimeError("exception tree digest differs")
    stderr_value = evidence["stderr"]
    if not isinstance(stderr_value, dict) or set(stderr_value) != {"observed_bytes", "observed_sha256", "retained_bytes", "retained_sha256", "truncated", "drain_error"}:
        raise RuntimeError("stderr schema differs")
    if (
        stderr_value["retained_bytes"] != len(stderr)
        or stderr_value["retained_sha256"] != hashlib.sha256(stderr).hexdigest()
        or not isinstance(stderr_value["observed_bytes"], int)
        or isinstance(stderr_value["observed_bytes"], bool)
        or stderr_value["observed_bytes"] < len(stderr)
        or not isinstance(stderr_value["retained_bytes"], int)
        or isinstance(stderr_value["retained_bytes"], bool)
        or not isinstance(stderr_value["observed_sha256"], str)
        or HEX64.fullmatch(stderr_value["observed_sha256"]) is None
        or not isinstance(stderr_value["retained_sha256"], str)
        or HEX64.fullmatch(stderr_value["retained_sha256"]) is None
        or not isinstance(stderr_value["truncated"], bool)
        or stderr_value["drain_error"] is not None
    ):
        raise RuntimeError("stderr evidence differs")
    if not stderr_value["truncated"] and (
        stderr_value["observed_bytes"] != len(stderr)
        or stderr_value["observed_sha256"] != hashlib.sha256(stderr).hexdigest()
    ):
        raise RuntimeError("complete stderr digest differs")
    if stderr_value["truncated"] is not (
        stderr_value["observed_bytes"] > stderr_value["retained_bytes"]
    ):
        raise RuntimeError("stderr truncation flag differs")
    if stderr_value["truncated"] and stderr_value["retained_bytes"] != 4 * 1024 * 1024:
        raise RuntimeError("truncated stderr retention length differs")
    journal_value = journal(owned(root / "events.ndjson", 0o600, 128 * 1024 * 1024), evidence_sha)
    summary = {
        "status": "failure_evidence_valid",
        "attempt": root.name,
        "controller_sha256": value.controller_sha256,
        "run_ticket_sha256": hashlib.sha256(ticket_raw).hexdigest(),
        "failure_evidence_sha256": evidence_sha,
        "failure_ack_sha256": hashlib.sha256(ack_raw).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "journal": journal_value,
    }
    recheck_all()
    print(cbytes(summary).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
