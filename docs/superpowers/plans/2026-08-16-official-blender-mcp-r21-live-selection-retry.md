# Official Blender MCP R21 Live Selection-Retry Plan

## Goal

Recover only the failed R20 live acceptance with one fresh R21 GUI/live attempt.
Keep the completed R19 Task2, upstream source commit, installed MCP environment,
and runtime controller semantics unchanged. Preserve R20 as a terminal failure and
do not promote or reuse any R20 evidence.

## Frozen predecessors

- Plan parent is R20 commit `aaaa3397f69aacdf8eed983452fcab9258c60fb0`.
- Upstream `/Users/yeminjie/blender_mcp` remains clean at
  `482c540395ad93a2f86b1ada1520f4fddf8ebcfa`, parent
  `4309a39646e644261624bfcd2bca669b343b7621`.
- R19 Task2 remains PASS with both approvals and its 0400 receipt. No integration,
  dependency installation, source write, runtime build, or source commit is repeated.
- R19 live remains frozen as an unverified visual-ACK EOF failure.
- R20 live remains frozen as `STATUS: BLOCKED`. It allocated exactly one ticket and
  stopped at call 14: `get_objects_summary` returned `Ground` active/selected where
  `Lamp_Shade` was required. Its canonical failure ACK was accepted and its sole PTY
  exited with `R3_UNVERIFIED_FAILURE_BLOCKED`; it has no visual row, validation,
  package, or success review. No R20 path is reopened for writing and R20 attempt-0002
  remains forbidden.
- A post-terminal diagnostic replay used the same R20 `model_body.py` in a fresh
  Blender process. After every live read-only call through datablocks, missing files,
  linked libraries, path info, usage guess, object detail, and objects summary, the
  selection remained exactly `Lamp_Shade`. The failure is therefore not reproducible
  as an upstream tool defect and does not justify a speculative source change.

## Fresh R21 paths

- Runtime: `.superpowers/sdd/modeling-remediation/r21-live-runtime-r20-recovery`.
- Evidence: `.superpowers/sdd/modeling-remediation/r21-evidence-r20-recovery/final-retest-r3/attempt-0001`.
- Root record: `.superpowers/sdd/modeling-remediation/task-7-r21-followup-1-brief.md`.
- Original report: `.superpowers/sdd/modeling-remediation/task-7-r21-followup-1-report.md`.
- Reviews: `.superpowers/sdd/modeling-remediation/task-7-r21-followup-1-{success,failure}-review.md`.

Every fresh path must be absent before allocation. R21 attempt-0002 is forbidden.

## Task 1 — Plan and runtime

1. Commit only this Plan with the frozen R20 parent.
2. Create a native-0700 runtime containing exactly `r3_controller.py`, `driver.sh`,
   `r21_allocator.py`, and `r21_allocator_runner.py`, each native-0600/nlink1.
3. Copy the R20 controller byte-for-byte. Mechanically derive the other three leaves:
   change only the R21 recovery namespaces, markers, Plan path, and the driver topology
   edge from R20 to this Plan. No controller behavior or tool acceptance changes.
4. Compile the Python leaves, run the controller probe, and statically require that
   the driver binds the fresh evidence/report paths, this Plan, the R20 parent, and the
   unchanged source/controller identities.

## Task 2 — admission and GUI

Before any fresh allocation, require:

- this Plan is the sole changed path of HEAD and the worktree is clean;
- upstream source is clean at the frozen pin;
- current MCP distribution is `mcp==1.28.1`, FastMCP imports, and the bound entrypoint
  and Python 3.14 environment remain usable;
- R19 Task2 PASS/approvals/0400 receipt remain content-valid;
- R19 and R20 live failure shapes are exactly the frozen predecessors above;
- the post-R20 diagnostic sequence passed without selection drift;
- all R21 fresh paths and ports 9876/9877/9878 are absent/empty.

Allocate the R21 brief, report, and review paths with O_EXCL, native mode 0600, and
retain the original report FD. Start one Blender 5.2 factory GUI. The user has already
authorized enabling Allow Online Access for subsequent attempts; if the current GUI
requires another security-sensitive setting change outside that authorization, stop
for action-time confirmation. Start only the official extension listener on
localhost:9876, bind its PID/start/image, obtain the raw `bpy.app.tempdir`, and create
one canonical native-0700 `blender_mcp` scratch.

## Task 3 — sole live PTY

Run the R21 allocator once, then execute `driver.sh` once in one foreground PTY with
the original report FD on FD8 and the existing immutable
`.superpowers/sdd/modeling-remediation/task-7-brief.md` as driver input.

When the controller prints `VISUAL_ACK_REQUIRED`:

1. stop before writing stdin;
2. verify each fresh PNG's path, SHA, dimensions, and visible content;
3. display all fresh PNGs in manifest order;
4. collect one explicit user PASS/FAIL for every fresh image;
5. write exactly one canonical ordered `visual_ack` JSON line to the still-running PTY.

An EOF, malformed/reordered acknowledgement, any FAIL, second ticket, second driver,
or second attempt terminally blocks R21. A PASS requires a passing visual row, one
`run_end`, `dispatch-validation.json`, the finalized report/evidence package, exactly
one run ticket, and no recovery or threshold-repeat failure.

After controller cleanup, require ports and owned processes empty. Create only the
matching fresh success or failure review. Feed exactly one driver finish-review line.
The original report must end once with `actual_run_count: 1` and `STATUS: PASS` only
for an approved success review; every other terminal is BLOCKED.

## Task 4 — closeout

For success, independently verify:

- the manifest/report/validation/package digests form one closed chain;
- all 26 first calls pass and no unexpected repeat or recovery exists;
- the four acknowledged PNG identities equal the retained files;
- the original report inode is terminal and immutable for the remainder of the run;
- Blender/listener/recorder/PTY/scratch cleanup is complete;
- R19/R20 remain unchanged and upstream remains clean at `482c540...`.

Then add one audit document as the sole follow-up commit. A failed or unverified R21
is never promoted and requires another fresh Plan/namespace.
