# Official Blender MCP R4 File-Backed Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the still-unconsumed R3 Blender/MCP run once, replacing only the failed long-text PTY transport with a byte-bound file-backed driver.

**Architecture:** Keep the certified R3 controller, validator, payloads, attempt name, option-C acknowledgement, and terminal semantics unchanged. Mechanically derive one native-0600 Bash driver from the four certified R3 protocol fences, remove obsolete hand-paste scaffolding, bound the recorder wait, execute that file as the sole foreground process of one PTY so the controller continues to read acknowledgements from the PTY, and append a fixed review gate so the same Bash and report FD survive independent review.

**Tech Stack:** Bash 3.2+, Python 3.13 through `/Users/yeminjie/.local/bin/uv`, Git, macOS `lsof`/`ps`, Blender 5.2 LTS, official Blender MCP add-on.

## Global Constraints

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on branch `codex/official-blender-mcp-install`.
- Frozen clean base HEAD is `8d05ec975a6ba7317d5e9c23963233b2f2d11832`; its sole path is `docs/use-official-blender-mcp.md`, and its parent is `6a544bd5cad850ba57840c23d7a87d63ea868203`.
- The certified R3 Plan is `docs/superpowers/plans/2026-08-13-official-blender-mcp-r3-exception-diagnostics.md`, 2,974 lines, 133,959 bytes, SHA-256 `197b2fa515c4e2ae3181ca11ed796bee25da9e5ac15a0018401f06fb1fc23d71`.
- The certified runbook is `docs/use-official-blender-mcp.md`, 435 lines, 22,329 bytes, SHA-256 `658c1b20ff9569f05f32a699d3dcbd496201be30fc96efaa538d4e808f26136c`.
- The certified R3 live-protocol generator is 742 lines, 30,639 bytes, SHA-256 `828aaebc53cda2fe628d0730fd5ce4bf98da3222e883cea66b373315234c80ba`; its output is 820 lines, 36,189 bytes, SHA-256 `6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2`.
- The R3 controller remains 6,924 lines, 285,387 bytes, SHA-256 `7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a`; do not rename, regenerate differently, or patch it.
- The R3 direct-failure validator remains 422 lines, 18,969 bytes, SHA-256 `791d4e0b49b79f279608fe04e8e46dc1cc0d8b5e9596c21b27adb4a58e015f84`.
- The frozen payload brief remains `.superpowers/sdd/modeling-remediation/task-7-brief.md`, dev `16777232`, inode `295274948`, mode `0600`, nlink `1`, 538,571 bytes, SHA-256 `fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b`.
- The failed control-channel brief remains dev `16777232`, inode `299417373`, mode `0600`, nlink `1`, 19,975 bytes, SHA-256 `40de66889cc904e8f51509c5cd1424ff12204f4b67c91590786ea2a4b35e0a24`.
- The failed control-channel report remains dev `16777232`, inode `299417372`, mode `0600`, nlink `1`, size `0`, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; never reopen, append, replace, or unlink it.
- `.superpowers/sdd/modeling-remediation/final-retest-r3` and its `attempt-0001/run-ticket.json` are absent; controller/recorder/listener processes are absent; therefore the actual R3 run count is exactly zero and this Plan authorizes at most one successful ticket acquisition.
- Reuse `final-retest-r3/attempt-0001`; do not create `attempt-0002`, an R4 controller, another validator, a PTY sender, `expect`, `tmux`, a writer broker, or a retry lane.
- Before the Plan-only commit, do not start Blender/MCP or create R3 evidence. After that commit, do not modify this Plan, the R3 Plan, runbook, tests, MCP source, or application code.
- The only later tracked change allowed is the modeling audit after a successful option-C run. Main and every unrelated worktree remain untouched.
- Blender Online Access is already enabled under the user's explicit authorization. Recheck it; do not change any other network or security preference.
- Any missing identity, unexpected file, failed guard, lost PTY, lost FD8, malformed review, or ambiguous visual verdict is fail-closed. Never manufacture a replacement writer or retry inside this Plan.

---

## File map

- Create and commit: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md` — this authorization and exact driver generator.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r4-live-driver/build.py` — byte-exact extraction of this Plan's Appendix A.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r4-live-driver/driver.sh` — sole PTY foreground program.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-2-brief.md` — compact frozen binding manifest; the committed Plan remains the sole prose contract.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-2-report.md` — immutable live-run report.
- Conditionally create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-2-failure-root-checks.json` or `task-7-followup-2-success-root-checks.json` — canonical root validation transcript.
- Conditionally create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-2-failure-review-package.json` or `task-7-followup-2-success-review-package.json` — canonical immutable reviewer input manifest.
- Conditionally create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-2-failure-review.md` or `task-7-followup-2-success-review.md`.
- Modify only after certified success: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`.

### Task 1: adversarially certify and commit this Plan

**Files:**
- Create: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md`
- Create ignored: `.superpowers/sdd/modeling-remediation/r4-plan-review/rNN-{spec,execution,ponytail}.md`

**Interfaces:**
- Consumes: the frozen identities in Global Constraints and Appendix A.
- Produces: one clean Plan-only HEAD and three same-SHA reports with `Critical: 0`, `Important: 0`, `Minor: 0`, `SPEC_VERDICT: PASS`.

- [ ] **Step 1: prove the failed state is still exact**

Run read-only checks for HEAD, branch, clean status, both old control-channel artifacts, absence of `final-retest-r3`, absence of ticket, and absence of listener/controller/recorder. Expected: every Global Constraint matches and port 9876 has no listener.

- [ ] **Step 2: compile and exercise Appendices A through C in a disposable native temporary root**

Extract all three appendices byte-for-byte and verify their declared identities. Run Appendix C with the exact Appendix A/Appendix B/protocol paths and a fresh mode-0700 output root. Expected: its single `R4_PLAN_HARNESS_GREEN` line reports exact driver generation, Bash/heredoc syntax, PTY ACK/review behavior, source/stdin/non-TTY rejection, protocol mutation rejection, and reviewer-parser positive/negative cases. Any other output or nonzero exit burns the round.

- [ ] **Step 3: dispatch three fresh independent lenses against one frozen Plan SHA**

The spec/safety lens checks state transitions, report/FD ownership, one-run proof, option C, review terminals, and Git topology. The execution lens reruns Appendix C, adds only the bounded recorder normal/stuck/TERM-ignore/identity-drift fixtures that require the full derived cleanup body, and checks topology mutations. The Ponytail lens looks only for removable duplication, a second truth source, retry machinery, or code beyond the transport fix. Each writes only its preallocated native-0600/nlink-1 report through the original descriptor.

- [ ] **Step 4: repair every finding and repeat all three lenses**

Any Critical, Important, or Minor finding burns the round. Edit only this Plan, rerun Step 2, allocate three new report paths, and repeat until all three reports bind the same final Plan SHA and independently show exact zero findings plus PASS. Do not ask a lens to inherit a previous verdict.

- [ ] **Step 5: commit only the certified Plan**

```bash
PLAN=docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md
test "$(git rev-parse HEAD)" = 8d05ec975a6ba7317d5e9c23963233b2f2d11832
test "$(git status --short --untracked-files=all)" = "?? $PLAN"
git diff --check -- "$PLAN"
git add -- "$PLAN"
test "$(git diff --cached --name-only)" = "$PLAN"
git diff --cached --check
git commit -m "docs: plan file-backed Blender MCP retest"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git diff-tree --no-commit-id --name-only -r HEAD)" = "$PLAN"
test "$(git rev-parse HEAD^)" = 8d05ec975a6ba7317d5e9c23963233b2f2d11832
```

Expected: one Plan-only commit on top of the runbook commit; no Blender/MCP process or R3 evidence exists.

### Task 2: generate and prove the file-backed PTY driver

**Files:**
- Create ignored: `.superpowers/sdd/modeling-remediation/r4-live-driver/build.py`
- Create ignored: `.superpowers/sdd/modeling-remediation/r4-live-driver/driver.sh`

**Interfaces:**
- Consumes: Appendix A, the exact 820-line R3 protocol, committed follow-up Plan path, and frozen runbook topology.
- Produces: `driver.sh` as native 0600/nlink-1 under a native 0700 parent, with frozen dev/ino/size/SHA for Task 3.

- [ ] **Step 1: create the driver parent and extract Appendix A**

Exclusive-create `.superpowers/sdd/modeling-remediation/r4-live-driver` as mode 0700. Extract Appendix A to `build.py` without its Markdown fences, require the Appendix A SHA declared below, compile in memory with uv Python 3.13, and create no `__pycache__`.

- [ ] **Step 2: regenerate the certified R3 protocol outside the attempt root**

Extract the certified R3 Appendix C by its declared SHA and run it against the frozen payload brief into a fresh native mode-0700 `/private/tmp` directory. Require exact `820/36189/6b137ede...00cb2` and exactly four top-level Bash bodies.

- [ ] **Step 3: generate the driver and prove its declared identity**

Run `build.py PROTOCOL DRIVER`. It must make only Appendix A's exact transport changes: two report-path occurrences, one Plan path, three topology lines, removal of the frozen hand-paste comment/sentinel/continuation guards, the bounded recorder wait, fixed invocation prefix, and fixed review gate. Require exact driver line/byte/SHA identity printed by Appendix A, native uid/mode/nlink, `/bin/bash -n` zero, seven heredoc Python bodies compile, exactly one foreground controller `run`, and no stdin redirection for the driver.

### Task 3: perform the sole live R3 run through the file driver

**Files:**
- Create ignored: `.superpowers/sdd/modeling-remediation/task-7-followup-2-brief.md`
- Create ignored: `.superpowers/sdd/modeling-remediation/task-7-followup-2-report.md`
- Consume ignored: `.superpowers/sdd/modeling-remediation/r4-live-driver/driver.sh`

**Interfaces:**
- Consumes: the certified Plan-only HEAD, Task 2's driver identity, exact old empty report identity, and the existing R3 controller/validator protocol.
- Produces: either an unverified BLOCKED terminal, a direct-failure review wait, or a success review wait; never a retry.

- [ ] **Step 1: root-allocate the new brief and report**

The root orchestrator exclusive-creates the new report native 0600/nlink-1 and a compact brief containing only exact current values for: follow-up Plan path/commit/SHA; runbook commit/SHA; driver dev/ino/uid/mode/nlink/size/SHA; old brief/report identities; new report dev/ino; `ACTUAL_RUN_LIMIT=1`; and proof that root/ticket/processes are absent. The brief points to this committed Plan's Task 3 through Task 5 headings and does not copy their prose. Any pre-existing target is a hard stop. The old followup-1 files remain untouched.

- [ ] **Step 2: complete GUI preflight before allocating R3 evidence or a PTY**

Using Computer Use, launch one factory-startup Blender, recheck Online Access is enabled, enable the already-installed official add-on, and start one listener. In the visible Blender Console prove version 5.2.x, filepath `''`, `is_saved=False`, OBJECT mode, exact `Camera/Cube/Light`, and display `bpy.app.tempdir`. Externally canonicalize `/var/...` to `/private/var/...`; bind scratch, sole listener PID, exact `ps lstart`, and the unique path-filtered Blender main-image `dev|ino`. If any check fails, stop only that owned Blender/listener, leave the report empty as the fail-closed terminal, and stop this Plan with actual run count zero.

- [ ] **Step 3: create the controller and prepare the exact ten launch arguments**

Only after GUI preflight PASS, generate `final-retest-r3/attempt-0001/r3_controller.py` with certified R3 Appendix A; require it is the sole attempt artifact and matches the frozen controller identity, compile/Ruff/probe GREEN, and create no pyc. Recheck driver identity and clean repository topology. The ten driver arguments, in exact order, are: canonical scratch; listener PID; listener start string; listener image composite; current follow-up Plan commit; current follow-up Plan SHA; fixed runbook commit; fixed runbook SHA; new report dev; new report inode. Reject control characters, tabs, or newlines in every argument; validate numeric/hex/path schemas before launch.

- [ ] **Step 4: launch the sole PTY foreground process without a prompt or paste**

Start one PTY whose process is exactly:

```text
/usr/bin/env -u BASH_ENV /bin/bash --noprofile --norc <absolute-driver> <ten exact arguments>
```

The API launches this argv once; it does not first open an interactive prompt, paste/source the driver, redirect stdin, or queue an acknowledgement. Bind the PTY session/process identity. The file-backed Bash reads commands from the driver while the foreground controller inherits PTY fd0.

- [ ] **Step 5: handle only the prompt that actually appears**

For `FAILURE_ACK_REQUIRED`, send exactly one canonical failure ACK with a literal immediate hypothesis restricted to observed facts. For `VISUAL_ACK_REQUIRED`, the implementer sends the root agent only the live session identity and complete ordered absolute PNG paths/SHA-256 values, then writes no stdin. The root displays every image to the user. Option C requires an explicit verdict for every row: all PASS sends the exact all-pass JSON; any FAIL sends the exact complete ordered mixed-verdict JSON; missing/ambiguous/reordered verdict or lost PTY sends no invented value and closes stdin for the controller's EOF deviation. No acknowledgement bytes are prequeued.

- [ ] **Step 6: let the fixed fourth body clean up and route the terminal**

After controller return, the driver closes FIFO, performs the Appendix-A bounded recorder wait/identity cleanup, accumulates cleanup errors with errexit disabled, rechecks PID/start/image before signalling, verifies port 9876 is empty, parses the canonical run ticket to derive count zero or one, opens only the new report as FD8 by its bound inode, and appends cleanup facts. A recorder that does not exit within ten seconds is signalled only while its captured PID/start identity still matches; TERM gets five seconds, then KILL gets five seconds. Identity drift is never signalled, any survivor is included in `owned_processes_after_cleanup`, and every such case forces BLOCKED without an unbounded `wait`. Unverified failure or visual FAIL/EOF appends unique count plus `STATUS: BLOCKED` and exits. A valid grouped direct failure emits `R3_DIRECT_FAILURE_REVIEW_REQUIRED`; success emits `R3_POSTRUN_VALIDATION_GREEN`. Only those two states reach the fixed review gate with FD8 open.

- [ ] **Step 7: stop at the review gate**

When the driver prints `R3_FINISH_REVIEW_INPUT_REQUIRED`, the implementer writes nothing further and returns the live PTY session to the root orchestrator, which is the only review dispatcher, report parser, and terminal-token sender. EOF or an invalid token is converted to the current flow's canonical REJECTED call while FD8 remains valid, producing BLOCKED. If the PTY/session or FD8 itself is lost, the append is impossible: perform only exact owned-process cleanup, never reopen the report, and treat the missing terminal line as the fail-closed external BLOCKED proof; never claim PASS.

### Task 4: independently review a certified direct failure

**Files:**
- Create ignored only on the direct-failure lane: `.superpowers/sdd/modeling-remediation/task-7-followup-2-failure-review.md`

**Interfaces:**
- Consumes: a still-live driver in `direct_review`, FD8, Appendix B GREEN output, run ticket, direct evidence/ACK files, journal, report, and cleanup inventory.
- Produces: exactly one terminal review token for the waiting driver.

- [ ] **Step 1: validate before dispatch**

Run the exact R3 Appendix B validator against descriptor-bound immutable evidence. Require one `failure_evidence_valid` JSON object, canonical ticket count one, untruncated grouped exception tree, accepted ACK marker, four-row closed journal, matching evidence SHA in the symptom, empty owned-process inventory, clean tracked status, and absence of attempt-0002. Exclusive-create the failure root-checks path from the File map as native 0600/nlink-1 and write at most 1 MiB of canonical JSON with exact keys `schema`, `scope`, `checks`, `git`, and `processes`: schema `r4-root-checks-v1`, scope `failure`; `checks` is a length-one array whose object has exact keys `name`, `argv`, `rc`, `stdout`, and `stderr`, with name `failure_evidence_validator`, argv an array of the literal invocation strings, strict-integer rc `0`, stdout the exact single newline-terminated validator JSON line, and stderr a string; `git` has exact string keys `head` (lowercase hex40) and `status` (empty); `processes` has exact keys `attempt_0002_absent` (true), `controller_pids`, `listener_pids`, `port_9876_pids`, and `recorder_pids` (all empty arrays). Unknown keys, non-string argv/output values, booleans used as integers, or nonempty PID arrays are RED. Serialize with the same exact JSON rule used for the review package below, fsync, and retain its descriptor identity/SHA. Any validation or persistence rejection sends `r3_finish_review failure REJECTED` to the waiting PTY and ends BLOCKED.

- [ ] **Step 2: dispatch one fresh failure reviewer**

The root first exclusive-creates the review report native 0600/nlink-1, records its zero-size identity, and only then exclusive-creates the failure package path from the File map as native 0600/nlink-1. The package is one canonical UTF-8 JSON object with exact top-level keys `schema`, `scope`, `plan`, `review_report`, and `inputs`: `schema` is `r4-review-package-v1`; `scope` is `failure`; `plan` has exact keys `path`, `commit`, and `sha256`; `review_report` has exact keys `path`, `dev`, `ino`, `uid`, `mode`, `nlink`, and initial `size`; and every `inputs` entry has exact keys `path`, `dev`, `ino`, `uid`, `mode`, `nlink`, `size`, and `sha256`. The sorted unique input-path set equals exactly the six actual R3 leaves `r3_controller.py`, `run-ticket.json`, `direct-session.stderr`, `direct-session-failure.json`, `direct-failure-ack.json`, and `events.ndjson` under the canonical attempt root, plus the bound Task 3 report and the fixed failure root-checks path; no semantic alias or caller-selected subset is allowed. Every input is native regular 0600/nlink-1/current-UID. Integers are strict JSON integers; hashes are lowercase hex64; all paths (including `plan.path` and `review_report.path`) are canonical absolute paths without control characters. The exact package bytes are `json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"`, are at most 1 MiB, and must round-trip byte-identically through a duplicate-key-rejecting strict UTF-8 parser. The root retains the package creation FD through fsync/fstat, records its dev/ino/size/SHA outside the package, and passes those four values plus the report binding in the fresh reviewer task; the package cannot establish its own trust root. The reviewer descriptor-binds that external package identity, proves exact input-path set equality, rechecks every input before and after review, writes only the bound report through one `O_RDWR|O_NOFOLLOW` descriptor, and ends with unique full lines `REVIEW_SCOPE: FAILURE`, `Critical: 0`, `Important: 0`, `Minor: 0`, and `REVIEW_VERDICT: APPROVED` only on approval. After the session ends, the root lstat-checks the supplied dev/ino before descriptor-opening both artifacts, runs Appendix B with the bound report dev/ino, reparses the exact package bytes and path set fail-closed, and rechecks the package plus every input. Only Appendix B's unique `REVIEW_REPORT_APPROVED` output is approval; crash, timeout, nonzero exit, invalid/oversized report, or any pre/post drift is rejection.

- [ ] **Step 3: finish through the live driver**

Send one newline-terminated `r3_finish_review failure APPROVED` only for Appendix B approval; otherwise send one newline-terminated `r3_finish_review failure REJECTED`. The trusted sender performs exactly one write call and queues no later stdin. The gate calls the existing function, appends count one plus unique `STATUS: BLOCKED`, closes FD8, reaches `R3_FLOW=terminal`, and exits. There is no second run and Task 5 is skipped.

### Task 5: audit and commit a successful option-C run

**Files:**
- Modify: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`
- Create ignored: `.superpowers/sdd/modeling-remediation/task-7-followup-2-success-review.md`

**Interfaces:**
- Consumes: a still-live driver in `success`, FD8, finalized attempt-0001, all-PASS user ACK, clean journal, and option-C PNGs.
- Produces: one audit-only commit, clean full gate, independent approval, report `STATUS: PASS`, and no owned process.

- [ ] **Step 1: inspect immutable finalized evidence without rerunning finalize**

Descriptor-bind `dispatch-validation.json`, `evidence-manifest.json`, journal, catalogs, scene/report, visual manifest and all PNGs. Run only controller `summary`, the controller active-audit validator, and official audit validation. Require one pass row per dynamic tool, zero recoveries, valid journal, exact scene/catalog identities, all-PASS option-C ACK, no direct-failure files, and no owned process. Do not rerun controller `validate` or non-idempotent `finalize`.

- [ ] **Step 2: make and commit the sole audit change**

Replace only the modeling audit Tool-results/visual sections with the exact R3 results and one set of R3 binding lines. Require the sole tracked diff is `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`, `git diff --check` is clean, and commit with message `docs: record clean diagnostic Blender final retest`.

- [ ] **Step 3: run the clean final gates and exact history-scope checks**

On the unchanged clean audit HEAD, run active-audit validation, official audit validation, `git diff --check`, and `./scripts/checks.sh`. Require exactly one `369 passed in ...` line and exact `ALL CHECKS PASSED`. Starting at old R3 Plan commit `6a544bd5...`, the first-parent sequence must be exactly: runbook commit touching only the runbook; this R4 Plan commit touching only this Plan; audit commit touching only the modeling audit. Exclusive-create the success root-checks path from the File map as native 0600/nlink-1 and write at most 1 MiB using the exact canonical JSON rules in Task 4: top-level keys are exactly `schema`, `scope`, `checks`, `git`, and `processes`, with schema `r4-root-checks-v1` and scope `success`; `checks` is an ordered length-six array named exactly `controller_summary`, `active_audit`, `official_audit`, `diff_check`, `full_gate`, and `history_scope`, each object having only `name`, `argv`, `rc`, `stdout`, and `stderr` with the same types as Task 4 and strict-integer rc `0`; `git` has exact keys `head` (hex40), `status` (empty string), and `first_parent` (length-three array in runbook/Plan/audit order), whose entries have only hex40 `commit`, hex40 `parent`, and `paths`. Each `paths` value is a length-one JSON array of one string, mapped by position exactly to `docs/use-official-blender-mcp.md`, this R4 Plan path, and `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`; each row's `parent` equals the preceding bound commit (old R3 Plan, runbook, then R4 Plan). `processes` has the same exact keys/types as Task 4, with `attempt_0002_absent: true` and all PID arrays empty. Unknown keys, wrong order/cardinality/type, or mismatched literal output are RED. Fsync and retain its descriptor identity/SHA.

- [ ] **Step 4: dispatch one fresh success reviewer**

The root orchestrator creates the success report first and then the success package exactly as Task 4 specifies, using the success paths from the File map, `scope: success`, fresh inodes, and a fresh reviewer session. The package has the same exact schema except that its sorted unique input-path set equals: the bound `evidence-manifest.json`; every `files[].path` row in that manifest resolved beneath the canonical attempt root with exact path/SHA set equality (including all fixed leaves and every dynamic PNG, neither omissions nor extras); the committed modeling audit file; the bound Task 3 report; and the fixed success root-checks path. Each manifest path must be a nonempty relative single-component basename: absolute paths, `/` or `\\`, `.`, `..`, control characters, repeated names, symlinks, or a resolved realpath outside/directly unequal to `attempt_root / basename` are RED. No semantic role registry exists. All ignored inputs are native regular 0600/nlink-1/current-UID; only the tracked audit input is regular mode 0644. Parse `dispatch-manifest.ndjson` in its native record order: its PNG rows must have unique basenames, resolve by the same rule, and their `(path, sha256)` set must equal the set of every `.png` row in the evidence manifest. Preserve the dispatch row order separately and require the parsed all-PASS option-C acknowledgement to match that ordered list element-for-element; never infer visual order from the lexically sorted package inputs. The report scope line is `REVIEW_SCOPE: SUCCESS`. The reviewer and root both descriptor-bind the external package identity, parse the evidence closure, and prove this same path/SHA set equality plus ordered ACK equality before and after review; the root then runs Appendix B with the success report binding and rechecks every input. Any crash, timeout, nonzero exit, parser rejection, replacement, drift, closure mismatch, or finding is rejection.

- [ ] **Step 5: finish through the still-live driver**

Send one newline-terminated `r3_finish_review success APPROVED` only for Appendix B approval; otherwise send one newline-terminated `r3_finish_review success REJECTED`. The trusted sender performs exactly one write call and queues no later stdin. Approval appends `actual_run_count: 1` and unique `STATUS: PASS`; rejection appends the same count and unique `STATUS: BLOCKED`. The driver closes FD8, reaches terminal, exits, and the root orchestrator performs a final bounded report/status, clean-worktree, unchanged-HEAD, empty-port, and no-owned-process recheck.

## Appendix A: exact R4 driver generator

Extract the following Python body without its Markdown fences. It is exactly 386 lines,
14,706 bytes, SHA-256
`37ccb7d05d858eb20f22d03f1c9a66286f97105716191ad2cf7366ac4b21191e`.
It accepts no runtime values except the two CLI paths. The generated driver is exactly
805 lines, 32,482 bytes, SHA-256
`369c1f7eeb910acceb4a9c85a2d696e4a89a00a338121bead51cc0fa4bc68fd8`.
The compact Task 3 brief is the sole runtime binding for the produced driver's inode and digest.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path


PROTOCOL_SHA256 = "6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2"
PROTOCOL_SIZE = 36189
DRIVER_SHA256 = "369c1f7eeb910acceb4a9c85a2d696e4a89a00a338121bead51cc0fa4bc68fd8"
PLAN_REL = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md"


def identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        stat.S_IMODE(value.st_mode),
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def parent_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        stat.S_IMODE(value.st_mode),
    )


def owned_read(path: Path, expected_size: int, expected_sha: str) -> bytes:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("protocol path is not canonical")
    parent = path.parent
    parent_before = os.lstat(parent)
    if (
        not stat.S_ISDIR(parent_before.st_mode)
        or stat.S_ISLNK(parent_before.st_mode)
        or parent_before.st_uid != os.getuid()
        or stat.S_IMODE(parent_before.st_mode) != 0o700
    ):
        raise RuntimeError("protocol parent is unsafe")
    parent_id = identity(parent_before)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(parent_fd)) != parent_id:
            raise RuntimeError("protocol parent changed before open")
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size != expected_size
        ):
            raise RuntimeError("protocol identity differs")
        before_id = identity(before)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if identity(os.fstat(fd)) != before_id:
                raise RuntimeError("protocol changed before open")
            chunks: list[bytes] = []
            remaining = expected_size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    raise RuntimeError("short protocol read")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(fd, 1):
                raise RuntimeError("protocol exceeds bound")
            if identity(os.fstat(fd)) != before_id:
                raise RuntimeError("protocol changed during read")
        finally:
            os.close(fd)
        if (
            identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != before_id
            or identity(os.fstat(parent_fd)) != parent_id
            or identity(os.lstat(parent)) != parent_id
        ):
            raise RuntimeError("protocol path changed during read")
    finally:
        os.close(parent_fd)
    raw = b"".join(chunks)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError("protocol digest differs")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"driver anchor count differs: {old!r}")
    return text.replace(old, new)


PREFIX = r'''#!/bin/bash
case "$0" in /*) ;; *) echo 'STOP: driver path must be absolute' >&2; exit 91 ;; esac
test "${BASH_SOURCE[0]-}" = "$0" || { echo 'STOP: driver must execute as a file' >&2; exit 92; }
test -t 0 && test -t 1 && test -t 2 || { echo 'STOP: driver requires one live PTY' >&2; exit 93; }
test "$#" = 10 || { echo 'STOP: driver requires ten bound arguments' >&2; exit 94; }
R3_SCRATCH=$1
R3_LISTENER_PID=$2
R3_LISTENER_START=$3
R3_LISTENER_IMAGE=$4
R3_PLAN_COMMIT=$5
R3_PLAN_SHA256=$6
R3_RUNBOOK_COMMIT=$7
R3_RUNBOOK_SHA256=$8
R3_REPORT_DEV=$9
R3_REPORT_INO=${10}
shift 10
'''


REVIEW_GATE = r'''r4_reject_review() {
  case "$R3_FLOW" in
    direct_review) r3_finish_review failure REJECTED ;;
    success) r3_finish_review success REJECTED ;;
    *) return 2 ;;
  esac
}
printf 'R3_FINISH_REVIEW_INPUT_REQUIRED flow=%s\n' "$R3_FLOW"
if ! IFS= read -r R3_FINISH_LINE; then
  r4_reject_review || exit 95
elif [[ "$R3_FINISH_LINE" =~ ^r3_finish_review\ (failure|success)\ (APPROVED|REJECTED)$ ]]; then
  r3_finish_review "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" || {
    r4_reject_review || exit 96
  }
else
  r4_reject_review || exit 97
fi
test "$R3_FLOW" = terminal || { echo 'STOP: review did not reach terminal' >&2; exit 98; }
'''


def build(raw: bytes) -> bytes:
    text = raw.decode()
    original_bodies = re.findall(r"^```bash\n(.*?)^```$", text, flags=re.MULTILINE | re.DOTALL)
    if len(original_bodies) != 4:
        raise RuntimeError("expected exactly four frozen Bash bodies")
    text = once(
        text,
        '''# This fence and the three that continue it are hand-pasted into one persistent PTY, so
# `set -e` cannot be the enforcement mechanism here. Whether an interactive shell ignores
# errexit is unverified -- it was reported once and did not reproduce on two later
# harnesses, and the disagreement is unexplained -- but the two load-bearing reasons stand
# on their own and reproduced on every harness: `A && B` never aborts on a failing A even
# under errexit or an exiting ERR trap, and a failed `${VAR:?}` expansion does not end an
# interactive shell. Every guard below is therefore made binding by an ERR
# trap that exits, by explicit `|| { ...; exit 1; }` where a trap cannot see the failure,
# and by one guard per line. Each continuation fence re-asserts that this preamble ran, so
# pasting one of them into an unprepared shell fails closed instead of running advisory.
''',
        '''# This file is the sole foreground process of one live PTY. Every command guard is
# binding through the exiting ERR trap or an explicit exit; no later body can be skipped.
''',
    )
    text = once(
        text,
        '''# Set here rather than at the top, where it meant only "this preamble started": it
# preceded the six emptiness guards, every absoluteness `case` and every executability
# test, so a continuation fence could assert it and then use a variable the preamble had
# never validated. It is *not* the last line of the fence -- roughly three hundred lines
# follow, including the Task 7 brief validation and the `r3_python` definition the
# continuation fences call. What it now means precisely is: every path and executable a
# continuation fence consumes by name has been checked. Anything failing after this
# point terminates the shell through the exiting ERR trap above rather than leaving the
# sentinel set on a half-prepared shell.
# Exported because every continuation fence runs in this same persistent PTY.
R3_GUARDED_SHELL=1
export R3_GUARDED_SHELL

''',
        "",
    )
    continuation_guard = "test \"${R3_GUARDED_SHELL-}\" = 1 || { echo 'STOP: paste the guarded preamble fence into this PTY first' >&2; exit 1; }\n"
    if text.count(continuation_guard) != 2:
        raise RuntimeError("continuation-guard count differs")
    text = text.replace(continuation_guard, "")
    text = once(
        text,
        '''finish_r3_recorder() {
  if [ "$RECORDER_FD_OPEN" = 1 ]; then exec 9>&-; RECORDER_FD_OPEN=0; fi
  if [ -n "$RECORDER_PID" ]; then wait "$RECORDER_PID" || true; RECORDER_PID=''; fi
}
''',
        '''finish_r3_recorder() {
  if [ "$RECORDER_FD_OPEN" = 1 ]; then exec 9>&-; RECORDER_FD_OPEN=0; fi
  if [ -n "$RECORDER_PID" ]; then
    RECORDER_TRAP_START="$(/bin/ps -p "$RECORDER_PID" -o lstart= 2>/dev/null | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if test -n "${RECORDER_START-}" && test "$RECORDER_TRAP_START" = "$RECORDER_START"; then
      kill "$RECORDER_PID" 2>/dev/null || true
      for _ in 1 2 3 4 5; do
        kill -0 "$RECORDER_PID" 2>/dev/null || break
        /bin/sleep 1
      done
      RECORDER_TRAP_START="$(/bin/ps -p "$RECORDER_PID" -o lstart= 2>/dev/null | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
      if test "$RECORDER_TRAP_START" = "$RECORDER_START"; then
        kill -KILL "$RECORDER_PID" 2>/dev/null || true
      fi
    fi
    RECORDER_PID=''
  fi
}
''',
    )
    if text.count("task-7-followup-1-report.md") != 2:
        raise RuntimeError("old report-path count differs")
    text = text.replace("task-7-followup-1-report.md", "task-7-followup-2-report.md")
    text = once(
        text,
        "PLAN_REL=docs/superpowers/plans/2026-08-13-official-blender-mcp-r3-exception-diagnostics.md",
        f"PLAN_REL={PLAN_REL}",
    )
    text = once(
        text,
        'test "$(git -C "$FEATURE_ROOT" rev-parse HEAD)" = "$R3_RUNBOOK_COMMIT"',
        'test "$(git -C "$FEATURE_ROOT" rev-parse HEAD)" = "$R3_PLAN_COMMIT"',
    )
    text = once(
        text,
        'test "$(git -C "$FEATURE_ROOT" rev-list --parents -n 1 "$R3_RUNBOOK_COMMIT" | /usr/bin/awk \'{print NF}\')" = 2',
        'test "$(git -C "$FEATURE_ROOT" rev-list --parents -n 1 "$R3_PLAN_COMMIT" | /usr/bin/awk \'{print NF}\')" = 2',
    )
    text = once(
        text,
        'test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_RUNBOOK_COMMIT^")" = "$R3_PLAN_COMMIT"',
        'test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = "$R3_RUNBOOK_COMMIT"',
    )
    text = once(
        text,
        '''exec 9>&-
RECORDER_FD_OPEN=0
RECORDER_EXIT=0
wait "$RECORDER_PID" || RECORDER_EXIT=$?
RECORDER_PID=''
trap - EXIT ERR
set +e +u
CLEANUP_ERRORS=''
record_cleanup_error() { CLEANUP_ERRORS="${CLEANUP_ERRORS}$1;"; }
''',
        '''exec 9>&-
RECORDER_FD_OPEN=0
trap - EXIT ERR
set +e +u
RECORDER_BOUND_PID=$RECORDER_PID
RECORDER_EXIT=0
RECORDER_WAIT_ERROR=''
for _ in 1 2 3 4 5 6 7 8 9 10; do
  kill -0 "$RECORDER_BOUND_PID" 2>/dev/null || break
  /bin/sleep 1 8>&-
done
if kill -0 "$RECORDER_BOUND_PID" 2>/dev/null; then
  RECORDER_START_NOW="$(/bin/ps -p "$RECORDER_BOUND_PID" -o lstart= 2>/dev/null | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if test "$RECORDER_START_NOW" = "$RECORDER_START"; then
    kill "$RECORDER_BOUND_PID" 2>/dev/null || RECORDER_WAIT_ERROR=recorder_term
    for _ in 1 2 3 4 5; do
      kill -0 "$RECORDER_BOUND_PID" 2>/dev/null || break
      /bin/sleep 1 8>&-
    done
    if kill -0 "$RECORDER_BOUND_PID" 2>/dev/null; then
      RECORDER_START_NOW="$(/bin/ps -p "$RECORDER_BOUND_PID" -o lstart= 2>/dev/null | /usr/bin/sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
      if test "$RECORDER_START_NOW" = "$RECORDER_START"; then
        kill -KILL "$RECORDER_BOUND_PID" 2>/dev/null || RECORDER_WAIT_ERROR=recorder_kill
      else
        RECORDER_WAIT_ERROR=recorder_identity
      fi
    fi
  else
    RECORDER_WAIT_ERROR=recorder_identity
  fi
fi
for _ in 1 2 3 4 5; do
  kill -0 "$RECORDER_BOUND_PID" 2>/dev/null || break
  /bin/sleep 1 8>&-
done
if kill -0 "$RECORDER_BOUND_PID" 2>/dev/null; then
  RECORDER_EXIT=124
  test -n "$RECORDER_WAIT_ERROR" || RECORDER_WAIT_ERROR=recorder_alive
else
  wait "$RECORDER_BOUND_PID" || RECORDER_EXIT=$?
fi
RECORDER_PID=''
CLEANUP_ERRORS=''
record_cleanup_error() { CLEANUP_ERRORS="${CLEANUP_ERRORS}$1;"; }
test -z "$RECORDER_WAIT_ERROR" || record_cleanup_error "$RECORDER_WAIT_ERROR"
''',
    )
    text = once(
        text,
        "OWNED_AFTER=''\n",
        '''OWNED_AFTER=''
if kill -0 "$RECORDER_BOUND_PID" 2>/dev/null; then
  OWNED_AFTER="recorder:$RECORDER_BOUND_PID"
fi
''',
    )
    text = once(
        text,
        '  OWNED_AFTER="pid:$R3_LISTENER_PID"',
        '  OWNED_AFTER="${OWNED_AFTER}${OWNED_AFTER:+,}pid:$R3_LISTENER_PID"',
    )
    bodies = re.findall(r"^```bash\n(.*?)^```$", text, flags=re.MULTILINE | re.DOTALL)
    if len(bodies) != 4:
        raise RuntimeError("expected exactly four top-level Bash bodies")
    driver = PREFIX + "\n".join(bodies) + REVIEW_GATE
    payload = driver.encode()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != DRIVER_SHA256:
        raise RuntimeError(f"driver digest differs: {actual}")
    return payload


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build.py PROTOCOL DRIVER")
    protocol = Path(sys.argv[1])
    output = Path(sys.argv[2])
    raw = owned_read(protocol, PROTOCOL_SIZE, PROTOCOL_SHA256)
    payload = build(raw)
    parent = output.parent
    parent_info = os.lstat(parent)
    if (
        output != Path(os.path.realpath(output))
        or not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_ISLNK(parent_info.st_mode)
        or parent_info.st_uid != os.getuid()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
    ):
        raise RuntimeError("driver output target is unsafe")
    parent_id = parent_identity(parent_info)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if parent_identity(os.fstat(parent_fd)) != parent_id:
            raise RuntimeError("driver parent changed before open")
        fd = os.open(
            output.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise RuntimeError("short driver write")
                view = view[written:]
            os.fsync(fd)
            final = os.fstat(fd)
            if (
                not stat.S_ISREG(final.st_mode)
                or stat.S_IMODE(final.st_mode) != 0o600
                or final.st_uid != os.getuid()
                or final.st_nlink != 1
                or final.st_size != len(payload)
            ):
                raise RuntimeError("driver identity differs after write")
        finally:
            os.close(fd)
        current = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            identity(current) != identity(final)
            or parent_identity(os.fstat(parent_fd)) != parent_id
            or parent_identity(os.lstat(parent)) != parent_id
        ):
            raise RuntimeError("driver path or parent changed after write")
    finally:
        os.close(parent_fd)
    print(
        f"R4_DRIVER_GREEN lines={len(payload.splitlines())} bytes={len(payload)} "
        f"sha256={hashlib.sha256(payload).hexdigest()} dev={final.st_dev} ino={final.st_ino}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact live-review report parser

Extract this body without its Markdown fences. It is exactly 113 lines, 4,133 bytes,
SHA-256 `d881cbdfe5d902c91270079007fe03a8c107c767c454badddffb8f7d9941897e`.
Compile it in memory with uv Python 3.13 and run it only after the fresh reviewer process has ended. Invocation is
`review.py REPORT EXPECTED_DEV EXPECTED_INO failure|success`. It reads at most 1 MiB,
binds the original report inode and parent before/open/after, rejects trailing ambiguity,
and emits one approval line or exits nonzero.

The root orchestrator alone creates and rechecks the immutable package manifest, launches
the fresh reviewer, runs this parser, and sends one terminal token. The reviewer can only
write its bound report. This parser authenticates that report's bytes and grammar; it does
not replace the root's independent pre/post recheck of every package-manifest input.

```python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


LIMIT = 1024 * 1024


def identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        stat.S_IMODE(value.st_mode),
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: review.py REPORT EXPECTED_DEV EXPECTED_INO failure|success")
    path = Path(sys.argv[1])
    expected_dev = int(sys.argv[2])
    expected_ino = int(sys.argv[3])
    scope = sys.argv[4]
    if scope not in {"failure", "success"}:
        raise RuntimeError("review scope differs")
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("review path is not canonical")
    parent = path.parent
    parent_before = os.lstat(parent)
    if (
        not stat.S_ISDIR(parent_before.st_mode)
        or stat.S_ISLNK(parent_before.st_mode)
        or parent_before.st_uid != os.getuid()
        or stat.S_IMODE(parent_before.st_mode) != 0o700
    ):
        raise RuntimeError("review parent is unsafe")
    parent_id = identity(parent_before)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(parent_fd)) != parent_id:
            raise RuntimeError("review parent changed before open")
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            (before.st_dev, before.st_ino) != (expected_dev, expected_ino)
            or not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size > LIMIT
        ):
            raise RuntimeError("review identity differs")
        before_id = identity(before)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if identity(os.fstat(fd)) != before_id:
                raise RuntimeError("review changed before open")
            chunks: list[bytes] = []
            remaining = before.st_size
            while remaining:
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    raise RuntimeError("short review read")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(fd, 1):
                raise RuntimeError("review exceeds bound")
            if identity(os.fstat(fd)) != before_id:
                raise RuntimeError("review changed during read")
        finally:
            os.close(fd)
        if (
            identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != before_id
            or identity(os.fstat(parent_fd)) != parent_id
            or identity(os.lstat(parent)) != parent_id
        ):
            raise RuntimeError("review path changed during read")
    finally:
        os.close(parent_fd)
    raw = b"".join(chunks)
    if not raw or not raw.endswith(b"\n") or b"\r" in raw or b"\x00" in raw:
        raise RuntimeError("review bytes are not canonical text")
    lines = raw.decode("utf-8", "strict").splitlines()
    required = (
        f"REVIEW_SCOPE: {scope.upper()}",
        "Critical: 0",
        "Important: 0",
        "Minor: 0",
        "REVIEW_VERDICT: APPROVED",
    )
    for marker in required:
        if lines.count(marker) != 1:
            raise RuntimeError(f"review marker differs: {marker}")
    if tuple(lines[-5:]) != required:
        raise RuntimeError("review approval markers are not the exact final five lines")
    for line in lines:
        if line.startswith(("Critical:", "Important:", "Minor:", "REVIEW_VERDICT:", "REVIEW_SCOPE:")) and line not in required:
            raise RuntimeError(f"contradictory review marker: {line}")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"REVIEW_REPORT_APPROVED scope={scope} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Appendix C: exact disposable Plan harness

Extract this body without its Markdown fences. It is exactly 260 lines, 10,571 bytes,
SHA-256 `ef281164aa37f172064f65249ed10a660764e8806f60be404a2bbf565ecd6e1e`.
Run it as `harness.py BUILD_PY REVIEW_PY PROTOCOL_MD OUTPUT_ROOT`, where every path is
canonical, `OUTPUT_ROOT` already exists as an empty native mode-0700 directory, and all
artifacts remain under `/private/tmp`. It starts only harmless Bash/Python fixture
processes; it never imports Blender, connects MCP, or reads/writes Git.

````python
from __future__ import annotations

import hashlib
import os
import pty
import re
import runpy
import select
import stat
import subprocess
import sys
import time
from pathlib import Path


BUILD_SHA256 = "37ccb7d05d858eb20f22d03f1c9a66286f97105716191ad2cf7366ac4b21191e"
REVIEW_SHA256 = "d881cbdfe5d902c91270079007fe03a8c107c767c454badddffb8f7d9941897e"
PROTOCOL_SHA256 = "6b137ede56744b81ad84d1890148a9c19c5abd16d8d0489cf17974dd80100cb2"
DRIVER_SHA256 = "369c1f7eeb910acceb4a9c85a2d696e4a89a00a338121bead51cc0fa4bc68fd8"
BASH = "/bin/bash"


def safe_source(path: Path, expected: str) -> None:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError(f"noncanonical input: {path}")
    info = os.lstat(path)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size > 1024 * 1024
    ):
        raise RuntimeError(f"unsafe input: {path}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError(f"input digest differs: {path}")
    compile(raw, str(path), "exec")


def write_owned(path: Path, payload: bytes) -> os.stat_result:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise RuntimeError("short fixture write")
            view = view[count:]
        os.fsync(fd)
        return os.fstat(fd)
    finally:
        os.close(fd)


def review_case(review: Path, root: Path, scope: str, lines: list[str], accept: bool) -> None:
    path = root / f"review-{scope}-{len(tuple(root.iterdir()))}.md"
    info = write_owned(path, ("\n".join(lines) + "\n").encode())
    result = subprocess.run(
        [sys.executable, str(review), str(path), str(info.st_dev), str(info.st_ino), scope],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    observed = result.returncode == 0 and result.stdout.startswith("REVIEW_REPORT_APPROVED ")
    if observed is not accept:
        raise RuntimeError(f"review case differs scope={scope} accept={accept}: {result.stderr}")


def read_until(fd: int, marker: bytes, timeout: float = 10.0) -> bytes:
    deadline = time.monotonic() + timeout
    data = bytearray()
    while marker not in data:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"PTY marker timeout: {marker!r}")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            raise RuntimeError(f"PTY EOF before marker: {marker!r}")
        data.extend(chunk)
    return bytes(data)


def gate_case(prefix: str, gate: str, root: Path, line: str | None, expected: str) -> None:
    fixture = root / f"gate-{len(tuple(root.iterdir()))}.sh"
    log = root / f"gate-{len(tuple(root.iterdir()))}.log"
    body = prefix + r'''
R3_FLOW=success
r3_finish_review() {
  case "$1:$R3_FLOW" in success:success|failure:direct_review) ;; *) return 2 ;; esac
  case "$2" in APPROVED|REJECTED) ;; *) return 2 ;; esac
  printf '%s %s\n' "$1" "$2" >&8 || return 2
  exec 8>&-
  R3_FLOW=terminal
}
exec 8>"$R4_GATE_LOG"
''' + gate
    write_owned(fixture, body.encode())
    master, slave = pty.openpty()
    env = dict(os.environ, R4_GATE_LOG=str(log))
    args = ["/tmp/scratch", "123", "Fri Aug 14 00:00:00 2026", "1|2", "a" * 40,
            "b" * 64, "c" * 40, "d" * 64, "1", "2"]
    process = subprocess.Popen(
        [BASH, "--noprofile", "--norc", str(fixture), *args],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=env,
        close_fds=True,
    )
    os.close(slave)
    try:
        data = read_until(master, b"R3_FINISH_REVIEW_INPUT_REQUIRED")
        if b"APPROVED" in data or b"REJECTED" in data:
            raise RuntimeError("review completed before PTY input")
        os.write(master, b"\x04" if line is None else (line + "\n").encode())
        process.wait(timeout=10)
    finally:
        os.close(master)
        if process.poll() is None:
            process.kill()
            process.wait()
    if process.returncode != 0 or log.read_text().strip() != expected:
        raise RuntimeError(f"gate case differs line={line!r} rc={process.returncode}")


def parent_swap_case(build: Path, protocol: Path, root: Path) -> None:
    namespace = runpy.run_path(str(build))
    target_parent = root / "swap-parent"
    old_parent = root / "swap-parent-original"
    target_parent.mkdir(mode=0o700)
    real_open = os.open
    original_argv = sys.argv
    fired = False

    def swapping_open(path: os.PathLike[str] | str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        nonlocal fired
        if not fired and Path(path) == target_parent and flags & os.O_DIRECTORY:
            target_parent.rename(old_parent)
            target_parent.mkdir(mode=0o700)
            fired = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    os.open = swapping_open
    sys.argv = [str(build), str(protocol), str(target_parent / "driver.sh")]
    try:
        try:
            namespace["main"]()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("driver parent swap was accepted")
    finally:
        sys.argv = original_argv
        os.open = real_open
    if not fired or (target_parent / "driver.sh").exists() or (old_parent / "driver.sh").exists():
        raise RuntimeError("driver parent swap negative did not fail before output")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: harness.py BUILD_PY REVIEW_PY PROTOCOL_MD OUTPUT_ROOT")
    build, review, protocol, output = map(Path, sys.argv[1:])
    if output != Path(os.path.realpath(output)):
        raise RuntimeError("output root is not canonical")
    out_info = os.lstat(output)
    if (
        not stat.S_ISDIR(out_info.st_mode)
        or stat.S_ISLNK(out_info.st_mode)
        or out_info.st_uid != os.getuid()
        or stat.S_IMODE(out_info.st_mode) != 0o700
        or any(output.iterdir())
    ):
        raise RuntimeError("output root is unsafe")
    safe_source(build, BUILD_SHA256)
    safe_source(review, REVIEW_SHA256)
    protocol_raw = protocol.read_bytes()
    if hashlib.sha256(protocol_raw).hexdigest() != PROTOCOL_SHA256:
        raise RuntimeError("protocol digest differs")

    driver = output / "driver.sh"
    built = subprocess.run(
        [sys.executable, str(build), str(protocol), str(driver)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if built.returncode != 0 or built.stdout.count("R4_DRIVER_GREEN ") != 1:
        raise RuntimeError(f"driver build failed: {built.stderr}")
    driver_raw = driver.read_bytes()
    if hashlib.sha256(driver_raw).hexdigest() != DRIVER_SHA256:
        raise RuntimeError("driver digest differs")
    parent_swap_case(build, protocol, output)
    subprocess.run([BASH, "-n", str(driver)], timeout=10, check=True)
    text = driver_raw.decode()
    heredocs = re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", text, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("driver heredoc count differs")
    for number, heredoc in enumerate(heredocs, 1):
        compile(heredoc, f"<driver-heredoc-{number}>", "exec")
    for stale in ("hand-pasted", "R3_GUARDED_SHELL", "paste the guarded preamble"):
        if stale in text:
            raise RuntimeError(f"stale transport state remains: {stale}")
    if text.count('wait "$RECORDER_PID"') or text.count('"$ATTEMPT_ROOT/r3_controller.py" run \\') != 1:
        raise RuntimeError("driver wait/run cardinality differs")

    mutated = output / "protocol-mutated.md"
    changed = bytearray(protocol_raw)
    changed[0] ^= 1
    write_owned(mutated, bytes(changed))
    rejected = subprocess.run(
        [sys.executable, str(build), str(mutated), str(output / "must-not-exist.sh")],
        capture_output=True,
        timeout=10,
        check=False,
    )
    if rejected.returncode == 0 or (output / "must-not-exist.sh").exists():
        raise RuntimeError("protocol mutation was accepted")

    required_success = ["REVIEW_SCOPE: SUCCESS", "Critical: 0", "Important: 0", "Minor: 0", "REVIEW_VERDICT: APPROVED"]
    required_failure = ["REVIEW_SCOPE: FAILURE", "Critical: 0", "Important: 0", "Minor: 0", "REVIEW_VERDICT: APPROVED"]
    review_case(review, output, "success", required_success, True)
    review_case(review, output, "failure", required_failure, True)
    review_case(review, output, "success", required_success + ["trailing"], False)
    review_case(review, output, "success", required_success[:-1], False)
    review_case(review, output, "success", required_success + ["Critical: 0"], False)
    review_case(review, output, "success", [line if line != "Important: 0" else "Important: 1" for line in required_success], False)
    review_case(review, output, "failure", required_success, False)

    constants = runpy.run_path(str(build))
    prefix = constants["PREFIX"]
    gate = constants["REVIEW_GATE"]
    gate_case(prefix, gate, output, "r3_finish_review success APPROVED", "success APPROVED")
    gate_case(prefix, gate, output, "garbage", "success REJECTED")
    gate_case(prefix, gate, output, "r3_finish_review failure APPROVED", "success REJECTED")
    gate_case(prefix, gate, output, None, "success REJECTED")
    fixture = next(output.glob("gate-*.sh"))
    non_tty = subprocess.run([BASH, str(fixture), *("x" for _ in range(10))], input=b"", capture_output=True)
    if non_tty.returncode != 93:
        raise RuntimeError("non-TTY driver was accepted")
    sourced = subprocess.run([BASH, "-c", 'source "$1"', "/private/tmp/r4-sourced-driver", str(fixture)], capture_output=True)
    if sourced.returncode != 92:
        raise RuntimeError("sourced driver was accepted")
    with fixture.open("rb") as redirected_input:
        redirected = subprocess.run([BASH], stdin=redirected_input, capture_output=True)
    if redirected.returncode != 92:
        raise RuntimeError("stdin-fed driver was accepted")

    print("R4_PLAN_HARNESS_GREEN build=1 heredocs=7 mutation_red=1 parent_swap_red=1 review_positive=2 review_negative=5 gate_positive=1 gate_negative=6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
