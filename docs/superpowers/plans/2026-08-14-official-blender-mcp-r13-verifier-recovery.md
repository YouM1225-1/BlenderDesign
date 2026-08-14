# Official Blender MCP R13 Verifier-Recovery Plan

> **For agentic workers:** execute task-by-task. R12 is immutable; its Task 2 builder and terminal may not be replayed or rewritten.

**Goal:** Recover from R12's verifier-only false BLOCKED by deriving one fresh driver from the exact unlaunched R12 driver, while letting R13 take ownership of the still-absent R12 live namespace.

**Architecture:** Freeze the R12 Task 2 report/runtime. Change only the Plan path and first-parent topology in the exact R12 driver; keep its attempt and follow-up report anchors byte-identical. Reuse the exact R12 Python `dir_fd` allocator by extracting it from the committed R12 Plan, not by copying or modifying it.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is the R12 Plan commit `76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8`, parent `9b0926b7f10a289d0fc4eb5d92649f85745f7890`. The committed R12 Plan is 444 lines / 27,434 bytes / SHA-256 `32be7ab4dbd854312cacaf64d13f3bd14431ce7ada54c1253c38c78df9720e5e`.
- R12 Task 2 report is frozen BLOCKED at dev/inode `16777232/305780222`, native-0600/nlink-1, 1,606 bytes, SHA-256 `efb9ca794cb5e426c78cf701eef412a6833c5cbf8c93ae1e357bd8b6809fcd7b`. It uniquely records builder invocation 1, R12 driver launch 0, R12 actual run 0, failure `RuntimeError: reversal anchors differ`, and `STATUS: BLOCKED`.
- R12 runtime is frozen at dev/inode `16777232/305780223`, native-0700, with sole driver dev/inode `16777232/305780226`, native-0600/nlink-1, 33,565 bytes, SHA-256 `9bf8612848520e95d0d04d71c92d29d0d6f9b7a99bc5cb261f0c97629a6158ad`.
- The frozen driver is exact and unlaunched. Recomputing with the committed R12 builder constants gives modified-anchor counts `1/1`, new attempt/report counts `2/1`, and exact raw reversal to the R11 driver SHA-256 `d38e792492fee3a8fcab2b6bb5d4243c90acb1840ea4f35cd420d3bcdb11d3db`. R12 failed only because its implementer duplicated the anchors in a second, non-diagnostic verifier.
- Never reopen, append, replace, delete, relabel, or rerun the R12 Task 2 report, runtime, driver, builder, or terminal. Reading the exact frozen driver as the R13 builder source is permitted.
- The top-level `.superpowers/sdd/modeling-remediation/r12-evidence`, its `final-retest-r3/attempt-0001`, and `task-7-r12-followup-1-{brief,report}.md` remain completely absent. R13 explicitly takes ownership of those still-unused live names; they are not R12 evidence and may be created only by R13 Task 3.
- Exact R12 allocator source is Appendix B of the committed R12 Plan: 115 lines / 5,615 bytes / SHA-256 `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`. It may be extracted once to private storage and invoked once in R13 Task 3. It may not be copied into this Plan, patched, wrapped, or parameter-rewritten.
- R11 controller remains exact at dev/inode `16777232/305390856`, native-0600/nlink-1, 285,409 bytes, SHA-256 `58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27`.
- Port 9876 and owned Blender/controller/recorder processes are absent. No probe, CLI helper, loader-only probe, Blender, MCP, GUI, listener, controller, driver, ticket, inherited visual/verdict/ACK, retry, or attempt-0002 is permitted before Task 3's explicitly authorized one-shot sequence.
- `.superpowers/sdd/modeling-remediation/r13-live-runtime` and `r13-task2-report.md` are absent.

## File map

- Commit only this Plan in Task 1.
- Create after commit: `.superpowers/sdd/modeling-remediation/r13-live-runtime/driver.sh` and `r13-task2-report.md`.
- Preallocate `task-7-r12-followup-1-report.md` at R13 Task 3 admission and retain its original FD.
- Create `.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001`, `task-7-r12-followup-1-brief.md`, and conditional review artifacts only after fresh GUI/scratch GREEN.
- Modify the audit file only after certified success.

### Task 1: certify and commit this Plan

- [ ] Recheck the clean base HEAD, every frozen R12/R11 identity, the exact absent R13 runtime/report and transferred live names, empty port, and empty owned-process inventory.
- [ ] Extract Appendices A and B exactly. Run Appendix B once with the absolute worktree Python 3.13 and canonical absolute arguments in one fresh native-0700 `/private/tmp` root. Require one exact GREEN. It may generate a disposable driver and compile the extracted allocator, but may not run the driver, allocator, controller, Blender, or MCP.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan identity. Any Critical, Important, or Minor burns the round.
- [ ] Commit only this Plan with message `docs: plan verifier recovery`, parent `76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8`, and clean status.

### Task 2: generate the R13 driver

- [ ] Root exclusive-creates and retains the original native-0600 `r13-task2-report.md` FD, then exclusive-creates and retains the native-0700 `r13-live-runtime` directory FD. Extract exact Appendix A and invoke it exactly once with the frozen R12 driver as source.
- [ ] Require the declared marker and driver identity. The builder itself must prove exact raw reversal using its single canonical anchor set; no implementer may retype or serialize a second Plan/topology predicate. Also require `/bin/bash -n`, seven compiling Python heredocs, one controller `run`, and no run stdin redirect.
- [ ] Record the frozen R12 terminal/source, three final Plan reviews, report/runtime/driver identities, builder invocation 1, R12 launch/actual 0/0, and R13 launch/actual 0/0. Do not execute a driver, controller, Blender, MCP, allocator, or probe.
- [ ] Recheck every binding, transferred-name absence, Git, port, and process state before one unique original-FD `STATUS: PASS` or `STATUS: BLOCKED`; fsync, fstat/path-freeze, and close both original descriptors. No Task 2 retry or runtime review exists.

### Task 3: perform the sole fresh live run

- [ ] Bind R13 Task 2 PASS, the three frozen Plan reviews, current R13 runtime, frozen R12 BLOCKED report/runtime/source, exact R11 controller and approvals, all older history, clean Git, absent transferred live names/ticket, empty port, and empty owned-process inventory. Exclusive-create the transferred `task-7-r12-followup-1-report.md` with a root-only original read/write CLOEXEC FD before GUI work.
- [ ] Apply the R11/R10 current-session GUI/listener and exact scratch checker contract. Only after fresh scratch GREEN, create/freeze the transferred `task-7-r12-followup-1-brief.md`. No predecessor listener/tempdir/scratch/image/verdict/ACK is reusable.
- [ ] Bind the committed R12 Plan path, blob, 444/27,434 identity and SHA. Mechanically extract its Appendix B to private native-0700 storage; require 115/5,615/SHA `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`. Invoke that exact allocator exactly once through the absolute worktree Python 3.13 as `allocator.py SOURCE_R11_CONTROLLER MODELING_ROOT EXPECTED_ROOT_DEV EXPECTED_ROOT_INO`.
- [ ] Require exit zero and one exact `R12_ALLOCATION_GREEN` marker. The allocator must create the transferred top-level `r12-evidence/final-retest-r3/attempt-0001` and exact controller through Python `dir_fd`; no `/dev/fd` pathname is allowed.
- [ ] Parse the marker, descriptor-open every canonical transferred directory/controller path, require exact identity equality, and retain all directory FDs through the live terminal. Recheck scratch/listener/all bindings, then launch only the exact R13 driver once with argument 1 exactly the fresh scratch.
- [ ] Preserve inherited FD8, recorder, cleanup, one-ticket, original-report fallback, validation/review, and Option-C semantics. Any branch without one descriptor-valid driver terminal becomes canonical BLOCKED through root's original report FD. No reopen, replay, retry, allocator rerun, or attempt-0002.
- [ ] At `VISUAL_ACK_REQUIRED`, return only the live PTY and every ordered fresh PNG path/SHA. Root displays every image and obtains a fresh per-image verdict before one canonical ACK. No R12 visual state exists; no predecessor visual state may be reused or synthesized.

### Task 4: independently review grouped direct failure

- [ ] Apply inherited direct-failure review with R13 bindings. R12 Task 2 and all predecessor history stay external to the fresh failure package.

### Task 5: audit and commit certified success

- [ ] Apply inherited success review/final gate with R13 bindings. First-parent history is exact length twelve in runbook/R4/R5/R6/R7/R8/R9/R10/R11/R12/R13/audit order; twelve length-one path arrays have parents old-R3/runbook/R4/R5/R6/R7/R8/R9/R10/R11/R12/R13.

## Appendix A: exact R13 driver builder

Extract the following Python body without fences. Exact identity: 130 lines / 5,922 bytes / SHA-256 `1fe1682149ba25ea78813123732ec6d4d59f0eea6c24693d5ac62ae4d07b799d`. Invoke once as `builder.py SOURCE_R12_DRIVER OUTPUT_R13_DRIVER EXPECTED_PARENT_DEV EXPECTED_PARENT_INO`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_ID = (16777232, 305780226)
SOURCE_SIZE = 33565
SOURCE_SHA256 = "9bf8612848520e95d0d04d71c92d29d0d6f9b7a99bc5cb261f0c97629a6158ad"
OUTPUT_SIZE = 33696
OUTPUT_SHA256 = "340d4899882b65481c3dda1514a3457b095e64106d8c07b56b63b7054d9793f4"
OLD_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r12-dirfd-allocation.md"
NEW_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r13-verifier-recovery.md"
OLD_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 9b0926b7f10a289d0fc4eb5d92649f85745f7890\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 9b0926b7f10a289d0fc4eb5d92649f85745f7890^)" = ad89648ae3a4ff620ff30285a48d1317f4b9782b'
)
NEW_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8^)" = 9b0926b7f10a289d0fc4eb5d92649f85745f7890\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 9b0926b7f10a289d0fc4eb5d92649f85745f7890^)" = ad89648ae3a4ff620ff30285a48d1317f4b9782b'
)


def identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_owned(path: Path) -> bytes:
    before = os.lstat(path)
    expected = identity(before)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size != SOURCE_SIZE or expected[:2] != SOURCE_ID:
        raise RuntimeError("unsafe R13 source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(fd)) != expected:
            raise RuntimeError("R13 source changed before open")
        raw = os.read(fd, SOURCE_SIZE + 1)
        if len(raw) != SOURCE_SIZE or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256 or identity(os.fstat(fd)) != expected:
            raise RuntimeError("R13 source bytes changed")
    finally:
        os.close(fd)
    if identity(os.lstat(path)) != expected:
        raise RuntimeError("R13 source path changed")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("R13 anchor differs")
    return text.replace(old, new, 1)


def transform_driver(raw: bytes) -> bytes:
    text = once(raw.decode(), OLD_PLAN, NEW_PLAN)
    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)
    payload = text.encode()
    if len(payload) != OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_SHA256:
        raise RuntimeError("R13 driver identity differs")
    return payload


def reverse_driver(payload: bytes) -> bytes:
    text = once(payload.decode(), NEW_TOPOLOGY, OLD_TOPOLOGY)
    text = once(text, NEW_PLAN, OLD_PLAN)
    return text.encode()


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: builder.py SOURCE OUTPUT PARENT_DEV PARENT_INO")
    source, output = map(Path, sys.argv[1:3])
    parent = output.parent
    before = os.lstat(parent)
    expected = before.st_dev, before.st_ino, before.st_uid, stat.S_IMODE(before.st_mode)
    if output != Path(os.path.realpath(output)) or expected[:2] != (int(sys.argv[3]), int(sys.argv[4])) or not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o700:
        raise RuntimeError("unsafe R13 output parent")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created: tuple[int, int] | None = None
    success = False
    try:
        opened_parent = os.fstat(parent_fd)
        if (opened_parent.st_dev, opened_parent.st_ino, opened_parent.st_uid, stat.S_IMODE(opened_parent.st_mode)) != expected:
            raise RuntimeError("R13 output parent changed")
        raw = read_owned(source)
        payload = transform_driver(raw)
        if reverse_driver(payload) != raw:
            raise RuntimeError("R13 raw reversal differs")
        fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            created = opened.st_dev, opened.st_ino
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise RuntimeError("short R13 write")
                view = view[count:]
            os.fsync(fd)
            final = os.fstat(fd)
            if (final.st_dev, final.st_ino) != created or final.st_uid != os.getuid() or stat.S_IMODE(final.st_mode) != 0o600 or final.st_nlink != 1 or final.st_size != len(payload):
                raise RuntimeError("R13 output identity differs")
        finally:
            os.close(fd)
        leaf = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if (leaf.st_dev, leaf.st_ino) != created:
            raise RuntimeError("R13 output path changed")
        os.fsync(parent_fd)
        after = os.lstat(parent)
        if (after.st_dev, after.st_ino, after.st_uid, stat.S_IMODE(after.st_mode)) != expected:
            raise RuntimeError("R13 output parent changed after create")
        success = True
    finally:
        if not success and created is not None:
            try:
                leaf = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
                if (leaf.st_dev, leaf.st_ino) == created:
                    os.unlink(output.name, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)
    print(f"R13_DRIVER_GREEN sha256={OUTPUT_SHA256} plan=1 topology=1 reversal=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable R13 offline harness

Extract the following Python body without fences. Exact identity: 81 lines / 3,984 bytes / SHA-256 `07a8115756db0a9657166a6c37915b4c3c7dcddcbf76abdbd63e0ba93f842350`. Run as `harness.py BUILDER SOURCE_R12_DRIVER COMMITTED_R12_PLAN OUTPUT_ROOT` using the exact worktree Python 3.13 and canonical absolute arguments.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


BUILDER_SHA256 = "1fe1682149ba25ea78813123732ec6d4d59f0eea6c24693d5ac62ae4d07b799d"
OUTPUT_SHA256 = "340d4899882b65481c3dda1514a3457b095e64106d8c07b56b63b7054d9793f4"
R12_PLAN_SHA256 = "32be7ab4dbd854312cacaf64d13f3bd14431ce7ada54c1253c38c78df9720e5e"
ALLOCATOR_SHA256 = "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"


def owned(path: Path, digest: str, mode: int) -> bytes:
    before = os.lstat(path)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1 or before.st_size > 1024 * 1024:
        raise RuntimeError("unsafe R13 harness input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        raw = os.read(fd, before.st_size + 1)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, before.st_size) or len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("R13 harness input differs")
    finally:
        os.close(fd)
    return raw


def extract_allocator(plan: bytes) -> None:
    header = b"## Appendix B: exact R12 evidence allocator"
    if plan.count(header) != 1:
        raise RuntimeError("R12 allocator header differs")
    section = plan.index(header)
    start = plan.index(b"````python\n", section) + len(b"````python\n")
    end = plan.index(b"\n````", start)
    allocator = plan[start:end] + b"\n"
    if allocator.count(b"\n") != 115 or len(allocator) != 5615 or hashlib.sha256(allocator).hexdigest() != ALLOCATOR_SHA256:
        raise RuntimeError("R12 allocator extraction differs")
    compile(allocator, "<r12-allocator>", "exec")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: harness.py BUILDER SOURCE R12_PLAN OUTPUT_ROOT")
    builder, source, r12_plan, output_root = map(Path, sys.argv[1:])
    owned(builder, BUILDER_SHA256, 0o600)
    plan_raw = owned(r12_plan, R12_PLAN_SHA256, 0o644)
    if plan_raw.count(b"\n") != 444 or len(plan_raw) != 27434:
        raise RuntimeError("R12 Plan shape differs")
    extract_allocator(plan_raw)
    root_info = os.lstat(output_root)
    if output_root != Path(os.path.realpath(output_root)) or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700 or any(output_root.iterdir()):
        raise RuntimeError("unsafe R13 harness root")
    output = output_root / "driver.sh"
    built = subprocess.run([sys.executable, str(builder), str(source), str(output), str(root_info.st_dev), str(root_info.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    expected = f"R13_DRIVER_GREEN sha256={OUTPUT_SHA256} plan=1 topology=1 reversal=1\n"
    if built.returncode or built.stdout != expected or built.stderr:
        raise RuntimeError(f"R13 builder failed: {built.returncode} {built.stdout!r} {built.stderr!r}")
    driver = owned(output, OUTPUT_SHA256, 0o600)
    subprocess.run(["/bin/bash", "-n", str(output)], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("R13 heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r13-heredoc-{number}>", "exec")
    anchor = b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n'
    if driver.count(anchor) != 1:
        raise RuntimeError("R13 run count differs")
    command = driver[driver.index(anchor):driver.index(b" || R3_RUN_EXIT=$?", driver.index(anchor))]
    if b"<" in command:
        raise RuntimeError("R13 run stdin redirect differs")
    print("R13_PLAN_HARNESS_GREEN driver=1 allocator_extract=1 reversal=1 static=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
