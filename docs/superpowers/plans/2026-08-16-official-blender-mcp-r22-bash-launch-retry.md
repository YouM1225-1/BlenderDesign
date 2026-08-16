# Official Blender MCP R22 Bash-Launch Retry Plan

## Goal

Perform one fresh R22 live acceptance after the R21 transport-only prelaunch
failure. Preserve the completed R19 Task2, upstream source and controller semantics.
Use `/bin/bash /absolute/driver.sh ...` as the sole driver launch form because the
certified driver is intentionally native-0600.

## Frozen predecessors

- Plan parent is R21 commit `8c40dfa815e7976336761626408aaf42f27d08a6`.
- Upstream `/Users/yeminjie/blender_mcp` remains clean at
  `482c540395ad93a2f86b1ada1520f4fddf8ebcfa`, parent
  `4309a39646e644261624bfcd2bca669b343b7621`.
- R19 Task2 remains PASS with two approvals and its 0400 receipt. R19 live remains
  frozen as visual-ACK EOF. R20 remains frozen BLOCKED at semantic call 14.
- The post-R20 exact read-only diagnostic sequence passed with `Lamp_Shade` active
  and selected throughout; no source change is justified.
- R21 remains frozen `STATUS: BLOCKED`. It allocated once, but direct kernel exec of
  the native-0600 driver was rejected before interpreter entry. Driver-body count,
  ticket count, and actual-run count are zero; attempt-0002 is absent and cleanup is
  complete. No R21 path is reopened for writing or reused.

## Fresh R22 paths

- Runtime: `.superpowers/sdd/modeling-remediation/r22-live-runtime-r21-recovery`.
- Evidence: `.superpowers/sdd/modeling-remediation/r22-evidence-r21-recovery/final-retest-r3/attempt-0001`.
- Brief/report: `.superpowers/sdd/modeling-remediation/task-7-r22-followup-1-{brief,report}.md`.
- Reviews: `.superpowers/sdd/modeling-remediation/task-7-r22-followup-1-{success,failure}-review.md`.

Every fresh path must be absent before allocation. R22 attempt-0002 is forbidden.

## Task 1 — Plan and runtime

1. Commit only this Plan with the frozen R21 parent.
2. Create a native-0700 runtime with exactly native-0600/nlink1
   `r3_controller.py`, `driver.sh`, `r22_allocator.py`, and
   `r22_allocator_runner.py`.
3. Copy the R21 controller byte-for-byte. Mechanically change only fresh namespaces,
   allocator markers/identities, Plan path, report path, and the topology head.
   Preserve driver and controller behavior.
4. Require Bash syntax, Python syntax, exact controller probe output, four-leaf
   topology, hashes, permissions, static bindings, and clean repositories.

## Task 2 — admission and GUI

Require exact R19 Task2 PASS, frozen R19/R20/R21 shapes, clean source/main pins,
`mcp==1.28.1` with FastMCP import, absent R22 allocation paths, and empty ports
9876/9877/9878. Exclusive-create the brief, original report and both reviews as
native-0600/nlink1 while retaining report FD8.

Start one Blender 5.2 factory GUI. The user has authorized enabling Allow Online
Access for subsequent attempts. Bind enabled online access, the official extension
at localhost:9876, the sole listener PID/start/image, raw/canonical tempdir, and one
absent canonical `blender_mcp` scratch proven by the exact R10 checker.

## Task 3 — sole live PTY

Invoke the R22 allocator runner once. In the same PTY retaining FD8, execute exactly:

`exec /bin/bash /absolute/r22-live-runtime-r21-recovery/driver.sh <ten bound arguments>`

No direct kernel exec of the 0600 script is permitted. No second driver, allocator,
ticket, or attempt is permitted.

At `VISUAL_ACK_REQUIRED`, verify and display every fresh PNG in manifest order,
obtain one explicit PASS/FAIL per image, and feed exactly one canonical ordered ACK to
the still-running PTY. EOF, malformed/reordered ACK, any FAIL, tool deviation,
cleanup error, or incomplete evidence terminally blocks R22.

After cleanup, write only the matching preallocated review and feed one exact driver
finish-review line. PASS requires 26 first calls, four passing image verdicts, one
run_end, validation and package closure, one ticket, no unexpected repeat/recovery,
an approved success review, and one terminal original report with
`actual_run_count: 1` and `STATUS: PASS`.

## Task 4 — closeout

Independently verify the manifest/report/validation/package digest chain, retained
PNG identities, report inode, empty ports/processes/scratch, clean source, unchanged
predecessors, and absent attempt-0002. Then add one audit document as the sole
follow-up commit. Any non-PASS R22 is never promoted.
