# Official Blender MCP R20 Live-ACK Recovery Plan

## Goal

Recover only the interrupted R19 live acceptance. Keep the completed R19 Task2,
upstream source commit, installed MCP environment, and runtime controller semantics
unchanged. Perform one fresh R20 GUI/live attempt whose visual acknowledgement is
delivered while the sole PTY is still running, then validate, package, review, and
terminalize it.

## Frozen predecessor

- Plan parent is R19 commit `4e126949df4ae1c2d95279339cf46d6eaf76c8ef`.
- Upstream `/Users/yeminjie/blender_mcp` remains clean at
  `482c540395ad93a2f86b1ada1520f4fddf8ebcfa`, parent
  `4309a39646e644261624bfcd2bca669b343b7621`.
- R19 Task2 remains PASS with both approvals and its 0400 receipt. No integration,
  dependency installation, source write, runtime build, or source commit is repeated.
- R19 live is frozen as an unverified failure. Its `attempt-0001` manifest has 28
  records: one `run_start`, 26 passing calls, and one terminal visual row with
  `outcome=deviation`, `error="ack EOF"`; it has no `run_end`, validation, package,
  terminal report, or live review. The bound R19 follow-up report remains an empty
  native-0600 regular file. No R19 path is reopened for writing and R19 attempt-0002
  remains forbidden.
- The four R19 PNGs and the user's later `PASS / PASS / PASS / PASS` response are
  useful diagnosis only. Neither is reusable as the R20 visual acknowledgement.

## Fresh R20 paths

- Runtime: `.superpowers/sdd/modeling-remediation/r20-live-runtime-r19-recovery`.
- Evidence: `.superpowers/sdd/modeling-remediation/r20-evidence-r19-recovery/final-retest-r3/attempt-0001`.
- Root record: `.superpowers/sdd/modeling-remediation/task-7-r20-followup-1-brief.md`.
- Original report: `.superpowers/sdd/modeling-remediation/task-7-r20-followup-1-report.md`.
- Reviews: `.superpowers/sdd/modeling-remediation/task-7-r20-followup-1-{success,failure}-review.md`.

Every fresh path must be absent before allocation. R20 attempt-0002 is forbidden.

## Task 1 — Plan and runtime

1. Commit only this Plan with the frozen R19 parent.
2. Create a native-0700 runtime containing exactly `r3_controller.py`, `driver.sh`,
   `r20_allocator.py`, and `r20_allocator_runner.py`, each native-0600/nlink1.
3. Copy the R19 controller byte-for-byte. Mechanically derive the other three leaves:
   change only the R20 recovery namespaces, markers, Plan path, and the driver topology
   edge from R19 to this Plan. No controller behavior or tool acceptance changes.
4. Compile the Python leaves, run the controller probe, and statically require that
   the driver binds the fresh evidence/report paths, this Plan, the R19 parent, and the
   unchanged source/controller identities.

## Task 2 — admission and GUI

Before any GUI or fresh allocation, require:

- this Plan is the sole changed path of HEAD and the worktree is clean;
- upstream source is clean at the frozen pin;
- current MCP distribution is `mcp==1.28.1`, FastMCP imports, and the bound entrypoint
  and Python 3.14 environment remain usable;
- R19 Task2 PASS/approvals/0400 receipt remain content-valid;
- R19 live failure shape is exactly the frozen predecessor above;
- all R20 fresh paths and ports 9876/9877/9878 are absent/empty.

Allocate the R20 brief, report, and review paths with O_EXCL, native mode 0600, and
retain the original report FD. Start one Blender 5.2 factory GUI. If Allow Online
Access is off, obtain action-time user confirmation before changing it. Start only the
official extension listener on localhost:9876, bind its PID/start/image, obtain the
raw `bpy.app.tempdir`, and create one canonical native-0700 `blender_mcp` scratch.

## Task 3 — sole live PTY

Run the R20 allocator once, then execute `driver.sh` once in one foreground PTY with
the original report FD on FD8 and the existing immutable
`.superpowers/sdd/modeling-remediation/task-7-brief.md` as driver input.

When the controller prints `VISUAL_ACK_REQUIRED`:

1. stop before writing stdin;
2. verify each fresh PNG's path, SHA, dimensions, and visible content;
3. display all fresh PNGs in manifest order;
4. collect one explicit user PASS/FAIL for every fresh image;
5. write exactly one canonical ordered `visual_ack` JSON line to the still-running PTY.

An EOF, malformed/reordered acknowledgement, any FAIL, second ticket, second driver,
or second attempt terminally blocks R20. A PASS requires a passing visual row, one
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
- R19 remains unchanged and upstream remains clean at `482c540...`.

Then add one audit document as the sole follow-up commit. A failed or unverified R20
is never promoted and requires another fresh Plan/namespace.
