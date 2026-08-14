# Official Blender MCP R12 Dir-FD Allocation Follow-up Plan

> **For agentic workers:** execute task-by-task; R11 is immutable and no failed allocation or predecessor launch may be replayed.

**Goal:** Replace the unsupported Node `/dev/fd/<n>/child` allocation with one exact Python `dir_fd` allocator, then perform the still-unconsumed live run with the certified R11 controller.

**Architecture:** Freeze R11's launch-zero terminal. Reuse the exact certified R11 controller bytes, derive one R12 driver from the exact R11 driver, and use a fixed stdlib allocator that creates the fresh evidence hierarchy with `mkdir(..., dir_fd=...)` and the controller leaf with `O_EXCL|O_NOFOLLOW`. Root reopens and retains the returned identities before the sole live launch.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is R11 Plan commit `9b0926b7f10a289d0fc4eb5d92649f85745f7890`; R11 Plan is 329 lines / 24,010 bytes / SHA-256 `7161ff494facacb6839a15c7312e0c121526a2db8bb1d9c085f972a73f728ef9`.
- R11 Task 2 PASS report is dev/inode `16777232/305390850`, native-0600/nlink-1, 1,534 bytes, SHA-256 `65b948db54f238be7b2f363184cb71c52048820367f434ea5e086751b2ae1aa4`. Spec review inode `305390851`, SHA-256 `f715d8257c81737c508793f038ccda4a41904dbae03b037e8221628df9818695`; quality review inode `305390852`, SHA-256 `88787063d5280e4f1273287b10992785b1a0722b767ab9d31ee56a63a5a35e80`; both uniquely APPROVED.
- R11 runtime parent is dev/inode `16777232/305390853`, native-0700. Exact controller inode `305390856`, 285,409 bytes, SHA-256 `58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27`; exact driver inode `305390857`, 33,432 bytes, SHA-256 `d38e792492fee3a8fcab2b6bb5d4243c90acb1840ea4f35cd420d3bcdb11d3db`.
- R11 followup brief is dev/inode `16777232/305726261`, native-0600/nlink-1, 4,869 bytes, SHA-256 `cd4ad67032dbcad9c5109968c090bb77a7c6740375c979025c0e38751330a0ed`. Its report is dev/inode `16777232/305401705`, native-0600/nlink-1, 955 bytes, SHA-256 `66d3ef85335e18e4a0dfda508899f14d508af5a5fa01b67b1578556298858fa2`, with unique launch-count 0, actual-count 0, and `STATUS: BLOCKED`. Never reopen, append, replace, delete, or relabel either.
- R11's only partial evidence is empty directory `.superpowers/sdd/modeling-remediation/r11-evidence`, dev/inode `16777232/305726291`, native-0700. No stage, attempt, controller, ticket, PTY, or driver launch exists. Freeze that directory and never add a child.
- Exact R11 failure was `ENOENT` from Node attempting `mkdir('/dev/fd/13/final-retest-r3')`. The platform transport was wrong; the evidence naming/controller/driver/scratch contracts were not.
- Final external cleanup bound Blender PID 14062 by start/image and terminated only that owned process. Port 9876 and owned Blender/controller/recorder processes are absent.
- No controller change, probe/CLI replay, Node `/dev/fd` child path, wrapper, attempt-0002, retry, inherited image/verdict/ACK, or old evidence mutation is permitted.
- `.superpowers/sdd/modeling-remediation/r12-live-runtime`, `r12-task2-report.md`, `r12-evidence`, and `task-7-r12-followup-1-{brief,report}.md` are absent.

## File map

- Commit only this Plan in Task 1.
- Create after commit: `.superpowers/sdd/modeling-remediation/r12-live-runtime/driver.sh` and `r12-task2-report.md`.
- Preallocate `task-7-r12-followup-1-report.md` at Task 3 admission and retain its original FD.
- Create `.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001`, `task-7-r12-followup-1-brief.md`, and conditional review artifacts only after GUI/scratch GREEN.
- Modify the audit file only after certified success.

### Task 1: certify and commit this Plan

- [ ] Recheck every frozen identity, clean HEAD, absent R12 targets/ticket, empty port and owned-process inventory.
- [ ] Extract Appendices A, B and C exactly. Run Appendix C once with exact worktree Python 3.13 and canonical absolute arguments in a fresh native-0700 `/private/tmp` root. Require unique GREEN for the driver delta/reversal/static shape, exact `dir_fd` hierarchy/controller copy, and allocation-parent replacement RED. It may not run a controller, driver, Blender, or MCP.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan SHA. Any Critical, Important, or Minor burns the round.
- [ ] Commit only this Plan with message `docs: plan native dirfd allocation`, parent `9b0926b7f10a289d0fc4eb5d92649f85745f7890`, and clean status.

### Task 2: generate the R12 driver

- [ ] Root exclusive-creates and retains original native-0600 Task 2 report FD, then exclusive-creates/retains the native-0700 runtime directory FD. Extract exact Appendix A and invoke it once to create the sole driver through the bound directory.
- [ ] Require declared identity, exact raw reversal to R11 driver, `/bin/bash -n`, seven Python heredocs, one controller `run`, no run stdin redirect, and no controller/driver/Blender/MCP execution. Record frozen history, Plan reviews, runtime identities, `r11_driver_launch_count: 0`, `r11_actual_run_count: 0`, `r12_driver_launch_count: 0`, `r12_actual_run_count: 0`.
- [ ] Recheck all identities/absences/Git/port/process before unique PASS or BLOCKED; fsync/fstat/path-freeze/close original descriptors. No Task 2 retry or separate runtime review exists because the only executable controller is the already-approved exact R11 controller and the new allocator is certified by the Plan lenses.

### Task 3: perform the sole fresh live run

- [ ] Bind R12 Task 2 PASS, three Plan reviews, current R12 runtime, exact R11 Task 2 approvals/runtime and launch-zero terminal, all older frozen history, clean Git, absent R12 live targets/ticket, empty port/process. Preallocate fresh report with a root-only original read/write CLOEXEC FD.
- [ ] Apply R11/R10 current-session GUI/listener and exact scratch checker contract. After fresh scratch GREEN, create/freeze the fresh brief. No old listener/tempdir/scratch/image/verdict/ACK is reusable.
- [ ] Extract exact Appendix B to private native-0700 storage. Invoke it exactly once through the absolute worktree Python 3.13 as `allocator.py SOURCE_R11_CONTROLLER MODELING_ROOT EXPECTED_ROOT_DEV EXPECTED_ROOT_INO`. Require exit zero and one exact `R12_ALLOCATION_GREEN` marker. It must create the entire fresh R12 hierarchy and controller leaf with Python `dir_fd`; no `/dev/fd` pathname is allowed.
- [ ] Parse the marker identities, descriptor-open every canonical R12 directory and controller path, require exact equality, and retain the directory FDs through the live terminal. Recheck scratch/listener/all bindings, then launch only the exact R12 driver once with argument 1 exactly the fresh scratch.
- [ ] Preserve R11/R10 FD8, recorder, cleanup, one-ticket, original-report fallback and Option-C semantics after replacing admission/attempt/report/Plan/driver/history bindings. Any branch without one descriptor-valid driver terminal becomes canonical BLOCKED through root's original FD. No reopen, retry, or attempt-0002.
- [ ] At `VISUAL_ACK_REQUIRED`, return only the live PTY and every ordered fresh R12 PNG path/SHA. Root displays every image and obtains fresh verdicts before one canonical ACK.

### Task 4: independently review grouped direct failure

- [ ] Apply inherited direct-failure review with R12 bindings; predecessor/Task2 history stays external to the fresh package.

### Task 5: audit and commit certified success

- [ ] Apply inherited success review/final gate with R12 bindings. First-parent history is exact length eleven in runbook/R4/R5/R6/R7/R8/R9/R10/R11/R12/audit order; eleven length-one path arrays have parents old-R3/runbook/R4/R5/R6/R7/R8/R9/R10/R11/R12.

## Appendix A: exact R12 driver builder

Extract the following Python body without fences. Exact identity: 129 lines / 6,071 bytes / SHA-256 `165f6337423b8511d2a327ad7ceaffccb828107da5c4f7d9e8f7be8d1326a985`. Invoke once as `builder.py SOURCE_R11_DRIVER OUTPUT_R12_DRIVER EXPECTED_PARENT_DEV EXPECTED_PARENT_INO`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_ID = (16777232, 305390857)
SOURCE_SIZE = 33432
SOURCE_SHA256 = "d38e792492fee3a8fcab2b6bb5d4243c90acb1840ea4f35cd420d3bcdb11d3db"
OUTPUT_SIZE = 33565
OUTPUT_SHA256 = "9bf8612848520e95d0d04d71c92d29d0d6f9b7a99bc5cb261f0c97629a6158ad"
OLD_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r11-journal-clock.md"
NEW_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r12-dirfd-allocation.md"
OLD_ATTEMPT = ".superpowers/sdd/modeling-remediation/r11-evidence/final-retest-r3/attempt-0001"
NEW_ATTEMPT = ".superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001"
OLD_REPORT = "task-7-r11-followup-1-report.md"
NEW_REPORT = "task-7-r12-followup-1-report.md"
OLD_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = ad89648ae3a4ff620ff30285a48d1317f4b9782b\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse ad89648ae3a4ff620ff30285a48d1317f4b9782b^)" = 45df35ef4cf7a00707d65352e2f7059357b2ecac'
)
NEW_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 9b0926b7f10a289d0fc4eb5d92649f85745f7890\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 9b0926b7f10a289d0fc4eb5d92649f85745f7890^)" = ad89648ae3a4ff620ff30285a48d1317f4b9782b\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse ad89648ae3a4ff620ff30285a48d1317f4b9782b^)" = 45df35ef4cf7a00707d65352e2f7059357b2ecac'
)


def identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_owned(path: Path) -> bytes:
    before = os.lstat(path)
    expected = identity(before)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size != SOURCE_SIZE or expected[:2] != SOURCE_ID:
        raise RuntimeError("unsafe R12 source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(fd)) != expected:
            raise RuntimeError("R12 source changed before open")
        raw = os.read(fd, SOURCE_SIZE + 1)
        if len(raw) != SOURCE_SIZE or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256 or identity(os.fstat(fd)) != expected:
            raise RuntimeError("R12 source bytes changed")
    finally:
        os.close(fd)
    if identity(os.lstat(path)) != expected:
        raise RuntimeError("R12 source path changed")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("R12 anchor differs")
    return text.replace(old, new, 1)


def build_driver(raw: bytes) -> bytes:
    text = once(raw.decode(), OLD_PLAN, NEW_PLAN)
    if text.count(OLD_ATTEMPT) != 2:
        raise RuntimeError("R12 attempt anchor differs")
    text = text.replace(OLD_ATTEMPT, NEW_ATTEMPT)
    text = once(text, OLD_REPORT, NEW_REPORT)
    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)
    payload = text.encode()
    if len(payload) != OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_SHA256:
        raise RuntimeError("R12 driver identity differs")
    return payload


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: builder.py SOURCE OUTPUT PARENT_DEV PARENT_INO")
    source, output = map(Path, sys.argv[1:3])
    parent = output.parent
    before = os.lstat(parent)
    expected = before.st_dev, before.st_ino, before.st_uid, stat.S_IMODE(before.st_mode)
    if output != Path(os.path.realpath(output)) or expected[:2] != (int(sys.argv[3]), int(sys.argv[4])) or not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o700:
        raise RuntimeError("unsafe R12 output parent")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created: tuple[int, int] | None = None
    success = False
    try:
        opened_parent = os.fstat(parent_fd)
        if (opened_parent.st_dev, opened_parent.st_ino, opened_parent.st_uid, stat.S_IMODE(opened_parent.st_mode)) != expected:
            raise RuntimeError("R12 output parent changed")
        payload = build_driver(read_owned(source))
        fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            created = opened.st_dev, opened.st_ino
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise RuntimeError("short R12 write")
                view = view[count:]
            os.fsync(fd)
            final = os.fstat(fd)
            if (final.st_dev, final.st_ino) != created or final.st_uid != os.getuid() or stat.S_IMODE(final.st_mode) != 0o600 or final.st_nlink != 1 or final.st_size != len(payload):
                raise RuntimeError("R12 output identity differs")
        finally:
            os.close(fd)
        leaf = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if (leaf.st_dev, leaf.st_ino) != created:
            raise RuntimeError("R12 output path changed")
        os.fsync(parent_fd)
        after = os.lstat(parent)
        if (after.st_dev, after.st_ino, after.st_uid, stat.S_IMODE(after.st_mode)) != expected:
            raise RuntimeError("R12 output parent changed after create")
        success = True
    finally:
        if not success and created is not None:
            try:
                leaf = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
                if (leaf.st_dev, leaf.st_ino) == created:
                    os.unlink(output.name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)
    print(f"R12_DRIVER_GREEN sha256={OUTPUT_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact R12 evidence allocator

Extract the following Python body without fences. Exact identity: 115 lines / 5,615 bytes / SHA-256 `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`. Invoke once as `allocator.py SOURCE_CONTROLLER MODELING_ROOT EXPECTED_ROOT_DEV EXPECTED_ROOT_INO`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_ID = (16777232, 305390856)
SOURCE_SIZE = 285409
SOURCE_SHA256 = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"
PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")


def dir_identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode)


def read_controller(path: Path) -> bytes:
    before = os.lstat(path)
    expected = (before.st_dev, before.st_ino, before.st_uid, stat.S_IMODE(before.st_mode), before.st_nlink, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size != SOURCE_SIZE or expected[:2] != SOURCE_ID:
        raise RuntimeError("unsafe R12 controller source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        current = (opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode), opened.st_nlink, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        raw = os.read(fd, SOURCE_SIZE + 1)
        if current != expected or len(raw) != SOURCE_SIZE or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
            raise RuntimeError("R12 controller source changed")
    finally:
        os.close(fd)
    after = os.lstat(path)
    if (after.st_dev, after.st_ino, after.st_uid, stat.S_IMODE(after.st_mode), after.st_nlink, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != expected:
        raise RuntimeError("R12 controller path changed")
    return raw


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: allocator.py SOURCE_CONTROLLER MODELING_ROOT ROOT_DEV ROOT_INO")
    source, root = map(Path, sys.argv[1:3])
    controller = read_controller(source)
    before = os.lstat(root)
    expected = dir_identity(before)
    if root != Path(os.path.realpath(root)) or expected[:2] != (int(sys.argv[3]), int(sys.argv[4])) or not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o700:
        raise RuntimeError("unsafe R12 modeling root")
    fds = [os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    created: list[tuple[int, str, tuple[int, int]]] = []
    leaf_id: tuple[int, int] | None = None
    success = False
    try:
        if dir_identity(os.fstat(fds[0])) != expected:
            raise RuntimeError("R12 modeling root changed")
        for name in PARTS:
            parent_fd = fds[-1]
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            created.append((parent_fd, name, (info.st_dev, info.st_ino)))
            child_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            if dir_identity(os.fstat(child_fd)) != (info.st_dev, info.st_ino, os.getuid(), 0o700):
                os.close(child_fd)
                raise RuntimeError("R12 evidence directory identity differs")
            fds.append(child_fd)
        attempt_fd = fds[-1]
        leaf_fd = os.open("r3_controller.py", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=attempt_fd)
        try:
            opened = os.fstat(leaf_fd)
            leaf_id = opened.st_dev, opened.st_ino
            view = memoryview(controller)
            while view:
                count = os.write(leaf_fd, view)
                if count <= 0:
                    raise RuntimeError("short R12 controller write")
                view = view[count:]
            os.fsync(leaf_fd)
            final = os.fstat(leaf_fd)
            if (final.st_dev, final.st_ino) != leaf_id or final.st_uid != os.getuid() or stat.S_IMODE(final.st_mode) != 0o600 or final.st_nlink != 1 or final.st_size != SOURCE_SIZE:
                raise RuntimeError("R12 controller output identity differs")
        finally:
            os.close(leaf_fd)
        leaf = os.stat("r3_controller.py", dir_fd=attempt_fd, follow_symlinks=False)
        if (leaf.st_dev, leaf.st_ino) != leaf_id:
            raise RuntimeError("R12 controller output path changed")
        for fd in reversed(fds):
            os.fsync(fd)
        if dir_identity(os.lstat(root)) != expected:
            raise RuntimeError("R12 modeling root changed after allocation")
        success = True
    finally:
        if not success:
            try:
                if leaf_id is not None:
                    leaf = os.stat("r3_controller.py", dir_fd=fds[-1], follow_symlinks=False)
                    if (leaf.st_dev, leaf.st_ino) == leaf_id:
                        os.unlink("r3_controller.py", dir_fd=fds[-1])
            except OSError:
                pass
            for parent_fd, name, created_id in reversed(created):
                try:
                    info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if (info.st_dev, info.st_ino) == created_id:
                        os.rmdir(name, dir_fd=parent_fd)
                except OSError:
                    pass
        identities = [dir_identity(os.fstat(fd))[:2] for fd in fds]
        for fd in reversed(fds):
            os.close(fd)
    print("R12_ALLOCATION_GREEN " + " ".join(f"dir{index}={dev}:{ino}" for index, (dev, ino) in enumerate(identities[1:], 1)) + f" controller={leaf_id[0]}:{leaf_id[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix C: exact disposable R12 harness

Extract the following Python body without fences. Exact identity: 121 lines / 6,851 bytes / SHA-256 `06db3124d1fb309e4b86c59771cb466f848644b949e2bb47525beb5d791bce17`. Run as `harness.py BUILDER ALLOCATOR SOURCE_DRIVER SOURCE_CONTROLLER OUTPUT_ROOT MODELING_ROOT` using the exact worktree Python 3.13 and canonical absolute arguments.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


BUILDER_SHA256 = "165f6337423b8511d2a327ad7ceaffccb828107da5c4f7d9e8f7be8d1326a985"
ALLOCATOR_SHA256 = "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"
DRIVER_SOURCE_SHA256 = "d38e792492fee3a8fcab2b6bb5d4243c90acb1840ea4f35cd420d3bcdb11d3db"
DRIVER_OUTPUT_SHA256 = "9bf8612848520e95d0d04d71c92d29d0d6f9b7a99bc5cb261f0c97629a6158ad"
CONTROLLER_SHA256 = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"


def owned(path: Path, digest: str) -> bytes:
    before = os.lstat(path)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size > 1024 * 1024:
        raise RuntimeError("unsafe R12 harness input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        raw = os.read(fd, before.st_size + 1)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, before.st_size) or len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("R12 harness input differs")
    finally:
        os.close(fd)
    return raw


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit("usage: harness.py BUILDER ALLOCATOR DRIVER CONTROLLER OUTPUT_ROOT MODELING_ROOT")
    builder, allocator, driver_source, controller_source, output_root, modeling_root = map(Path, sys.argv[1:])
    builder_raw = owned(builder, BUILDER_SHA256)
    allocator_raw = owned(allocator, ALLOCATOR_SHA256)
    driver_raw = owned(driver_source, DRIVER_SOURCE_SHA256)
    controller_raw = owned(controller_source, CONTROLLER_SHA256)
    namespace: dict[str, object] = {"__name__": "r12_builder_harness"}
    exec(compile(builder_raw, str(builder), "exec"), namespace)
    output_info = os.lstat(output_root)
    modeling_info = os.lstat(modeling_root)
    for path, info in ((output_root, output_info), (modeling_root, modeling_info)):
        if path != Path(os.path.realpath(path)) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700 or any(path.iterdir()):
            raise RuntimeError("unsafe R12 harness root")
    output = output_root / "driver.sh"
    built = subprocess.run([sys.executable, str(builder), str(driver_source), str(output), str(output_info.st_dev), str(output_info.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    if built.returncode or built.stdout.count("R12_DRIVER_GREEN ") != 1:
        raise RuntimeError(f"R12 builder failed: {built.stderr}")
    driver = owned(output, DRIVER_OUTPUT_SHA256)
    text = driver.decode()
    reversed_driver = text.replace(namespace["NEW_PLAN"], namespace["OLD_PLAN"], 1).replace(namespace["NEW_ATTEMPT"], namespace["OLD_ATTEMPT"]).replace(namespace["NEW_REPORT"], namespace["OLD_REPORT"], 1).replace(namespace["NEW_TOPOLOGY"], namespace["OLD_TOPOLOGY"], 1)
    if reversed_driver.encode() != driver_raw:
        raise RuntimeError("R12 driver reversal differs")
    subprocess.run(["/bin/bash", "-n", str(output)], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("R12 heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r12-heredoc-{number}>", "exec")
    if driver.count(b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n') != 1:
        raise RuntimeError("R12 controller run count differs")
    allocated = subprocess.run([sys.executable, str(allocator), str(controller_source), str(modeling_root), str(modeling_info.st_dev), str(modeling_info.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    if allocated.returncode or allocated.stdout.count("R12_ALLOCATION_GREEN ") != 1:
        raise RuntimeError(f"R12 allocation failed: {allocated.stderr}")
    attempt = modeling_root / "r12-evidence/final-retest-r3/attempt-0001"
    if [path.name for path in attempt.iterdir()] != ["r3_controller.py"] or owned(attempt / "r3_controller.py", CONTROLLER_SHA256) != controller_raw:
        raise RuntimeError("R12 allocated controller differs")
    swap = modeling_root.parent / "swap-modeling"
    swap.mkdir(mode=0o700)
    swap_info = os.lstat(swap)
    held = modeling_root.parent / "held-modeling"
    os.rename(swap, held)
    os.mkdir(swap, 0o700)
    parent_red = subprocess.run([sys.executable, str(allocator), str(controller_source), str(swap), str(swap_info.st_dev), str(swap_info.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    if parent_red.returncode == 0 or "R12_ALLOCATION_GREEN" in parent_red.stdout or any(swap.iterdir()) or any(held.iterdir()):
        raise RuntimeError("R12 allocation-parent replacement accepted")
    replacement = modeling_root.parent / "replacement-modeling"
    replacement.mkdir(mode=0o700)
    replacement_info = os.lstat(replacement)
    allocator_namespace: dict[str, object] = {"__name__": "r12_allocator_harness"}
    exec(compile(allocator_raw, str(allocator), "exec"), allocator_namespace)
    target = replacement / "r12-evidence/final-retest-r3/attempt-0001/r3_controller.py"
    real_fsync = os.fsync
    foreign_id: tuple[int, int] | None = None

    def replace_then_fail(fd: int) -> None:
        nonlocal foreign_id
        if foreign_id is None and target.exists():
            os.unlink(target)
            foreign_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            os.write(foreign_fd, b"foreign\n")
            foreign_info = os.fstat(foreign_fd)
            foreign_id = foreign_info.st_dev, foreign_info.st_ino
            os.close(foreign_fd)
            raise RuntimeError("injected post-leaf failure")
        real_fsync(fd)

    old_argv = sys.argv
    os.fsync = replace_then_fail
    sys.argv = [str(allocator), str(controller_source), str(replacement), str(replacement_info.st_dev), str(replacement_info.st_ino)]
    failed = False
    try:
        allocator_namespace["main"]()
    except RuntimeError:
        failed = True
    finally:
        sys.argv = old_argv
        os.fsync = real_fsync
    foreign = os.lstat(target)
    if not failed or foreign_id is None or (foreign.st_dev, foreign.st_ino) != foreign_id or foreign.st_uid != os.getuid() or stat.S_IMODE(foreign.st_mode) != 0o600 or foreign.st_nlink != 1 or target.read_bytes() != b"foreign\n":
        raise RuntimeError("R12 allocation leaf replacement rollback unsafe")
    print("R12_PLAN_HARNESS_GREEN driver=1 allocation=1 allocation_parent_red=1 leaf_replacement_red=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
