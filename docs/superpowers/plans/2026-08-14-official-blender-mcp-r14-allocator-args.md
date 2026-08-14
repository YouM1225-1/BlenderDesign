# Official Blender MCP R14 Allocator-Arguments Recovery Plan

> **For agentic workers:** execute task-by-task. R13 Task 2 and Task 3 are immutable; neither builder nor allocator may be replayed.

**Goal:** Recover from R13's relative-argument allocator failure by binding the exact canonical controller and modeling-root arguments before the sole allocator invocation, then consume the still-unused live attempt.

**Architecture:** Freeze every R13 artifact. Derive one R14 driver from the exact unlaunched R13 driver by changing only Plan, follow-up report, and topology anchors; keep the `r12-evidence` attempt anchor unchanged. Reuse the exact committed R12 allocator bytes. A temporary exact Appendix C runner is the sole allocator caller and owns canonical path, identity, root-FD, argv, subprocess, and marker validation.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is R13 Plan commit `c0f38156cad28996cfddcabb1cf775ae84983cf5`, parent `76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8`. The committed R13 Plan is 286 lines / 19,400 bytes / SHA-256 `7ecf491eebf31b32d16eef37fe718b7d3f2959946994e99d4b32313e41ad4697`.
- R13 Task 2 PASS report is dev/inode `16777232/306066231`, native-0600/nlink-1, 1,305 bytes, SHA-256 `3a05ff2eb0ec9866fd8a9885bd018c3be84eba7193ed18e34f42f1e6721bda04`. It records builder invocation 1 and R13 launch/actual 0/0.
- R13 runtime parent is dev/inode `16777232/306066232`, native-0700. Its sole exact unlaunched driver is dev/inode `16777232/306066235`, native-0600/nlink-1, 33,696 bytes, SHA-256 `340d4899882b65481c3dda1514a3457b095e64106d8c07b56b63b7054d9793f4`.
- R13 Task 3 report `.superpowers/sdd/modeling-remediation/task-7-r12-followup-1-report.md` is frozen BLOCKED at dev/inode `16777232/306073842`, native-0600/nlink-1, 1,177 bytes, SHA-256 `64b2c79b6a83cad0765964041f95804eb9eee2c17c08139547822ded9bcd0d22`. It uniquely records allocator invocation 1, allocator exit 1, R13 launch/actual 0/0, and `STATUS: BLOCKED`.
- Exact R13 failure was `RuntimeError: unsafe R12 controller source`: its implementer supplied relative `SOURCE_CONTROLLER` and `MODELING_ROOT` argv elements. The allocator rejected before creating any evidence.
- R13 brief `.superpowers/sdd/modeling-remediation/task-7-r12-followup-1-brief.md` is frozen at dev/inode `16777232/306096357`, native-0600/nlink-1, 3,461 bytes, SHA-256 `bea6b1bc9f06642362dc443ecf6af0f1346b799f1521e2d8fa27fdd5caaa1d73`.
- Never reopen, append, replace, delete, relabel, or replay any R13 report, brief, runtime, driver, builder, allocator invocation, or terminal. Reading the exact R13 driver as the R14 builder source is permitted.
- `.superpowers/sdd/modeling-remediation/r12-evidence`, its ticket, `final-retest-r3/attempt-0001`, and every `attempt-0002` remain absent. R14 explicitly takes ownership of that still-unused evidence namespace.
- R14 uses fresh `.superpowers/sdd/modeling-remediation/task-7-r14-followup-1-{brief,report}.md`; the frozen R13 `task-7-r12-*` pair remains external history.
- Exact R12 allocator source remains Appendix B of committed R12 Plan `76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8`: 115 lines / 5,615 bytes / SHA-256 `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`. It may be extracted once and invoked only through exact Appendix C in R14 Task 3; it may not be copied, patched, parameter-rewritten, or invoked through any alternate wrapper.
- Exact controller source is `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py`, dev/inode `16777232/305390856`, 285,409 bytes, SHA-256 `58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27`.
- Exact modeling root is `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation`; exact Appendix C alone opens and retains its canonical native-0700 directory FD and constructs allocator argv from that FD.
- Port 9876 and owned Blender/controller/recorder processes are absent. No probe, CLI helper, loader-only probe, Blender, MCP, GUI, listener, controller, driver, ticket, inherited visual/verdict/ACK, retry, or attempt-0002 is permitted before Task 3's one-shot sequence.
- `.superpowers/sdd/modeling-remediation/r14-live-runtime`, `r14-task2-report.md`, and `task-7-r14-followup-1-{brief,report}.md` are absent.

## File map

- Commit only this Plan in Task 1.
- Create after commit: `.superpowers/sdd/modeling-remediation/r14-live-runtime/driver.sh` and `r14-task2-report.md`.
- Preallocate `task-7-r14-followup-1-report.md` at Task 3 admission and retain its original FD.
- Create `.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001`, `task-7-r14-followup-1-brief.md`, and conditional review artifacts only after fresh GUI/scratch GREEN.
- Modify the audit file only after certified success.

### Task 1: certify and commit this Plan

- [ ] Recheck clean base HEAD, every frozen R13/R12/R11 identity, exact absent R14 and transferred evidence targets, empty port, and empty owned-process inventory.
- [ ] Extract Appendices A, B, and C exactly. Run Appendix B once with absolute worktree Python 3.13 and canonical absolute inputs in one fresh native-0700 `/private/tmp` root. Require `R14_PLAN_HARNESS_GREEN driver=1 allocator_extract=1 argv_green=1 relative_source_red=1 relative_root_red=1 python_green=1 python_symlink_red=1 static=1`. It may generate one disposable driver, extract the exact allocator, and execute Appendix C only under a non-main module name to call its validation and pure `build_argv` functions; it may not invoke the allocator or run a driver, controller, Blender, or MCP.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan identity. Any Critical, Important, or Minor burns the round.
- [ ] Commit only this Plan with message `docs: plan canonical allocator args`, parent `c0f38156cad28996cfddcabb1cf775ae84983cf5`, and clean status.

### Task 2: generate the R14 driver

- [ ] Main root exclusive-creates and retains the original native-0600 `r14-task2-report.md` FD, then exclusive-creates and retains the native-0700 `r14-live-runtime` directory FD. Extract exact Appendix A and invoke it exactly once with the frozen R13 driver source.
- [ ] Require the declared marker and driver identity. The builder must prove exact raw reversal with its single canonical anchor set; no implementer may retype a second Plan/report/topology predicate. Also require `/bin/bash -n`, seven compiling Python heredocs, one controller `run`, and no run stdin redirect.
- [ ] Record frozen R13 Task 2 PASS and Task 3 BLOCKED, all final Plan reviews, report/runtime/driver identities, builder invocation 1, R13 launch/actual 0/0, and R14 launch/actual 0/0. Do not execute a driver, controller, allocator, Blender, MCP, or probe.
- [ ] Recheck all bindings, R13 freeze, R14/evidence absence, Git, port, and process state before one unique original-FD `STATUS: PASS` or `STATUS: BLOCKED`; fsync, fstat/path-freeze, and close both original descriptors. No Task 2 retry or runtime review exists.

### Task 3: perform the sole fresh live run

- [ ] Bind R14 Task 2 PASS, three frozen Plan reviews, current R14 runtime, frozen R13 Task 2/Task 3/brief/runtime, exact R12 allocator Plan and R11 controller, all older history, clean Git, absent R14/evidence targets/ticket, empty port, and empty owned-process inventory. Exclusive-create `task-7-r14-followup-1-report.md` with a root-only original read/write CLOEXEC FD before GUI work.
- [ ] Apply the inherited current-session GUI/listener and exact scratch checker contract. Only after fresh scratch GREEN, create/freeze `task-7-r14-followup-1-brief.md`. No predecessor listener/tempdir/scratch/image/verdict/ACK is reusable.
- [ ] Main root creates and retains one fresh canonical native-0700 private root below `/private/tmp`, extracts the exact R12 allocator to `<private-root>/r12_allocator.py` native-0600, and extracts exact Appendix C to `<private-root>/r14_allocator_runner.py` native-0600. Using canonical `/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13`, it then launches the runner exactly once with exactly these three arguments after the script: the canonical absolute extracted allocator, `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py`, and `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation`. The runner is the sole allocator caller. Any failure before the runner process starts is canonical BLOCKED with allocator invocation count 0; once the runner process starts, conservatively record allocator invocation count 1 regardless of whether its internal `subprocess.run` is reached. No alternate wrapper or inline argv construction is permitted.
- [ ] Require the runner's sole stdout to fullmatch the one R12 allocation marker and require empty stderr. Parse its four dev/inode identities; no shell command construction, relative argument, `cwd` dependence, alternate marker parser, explicit `check`, or explicit `shell` parameter is permitted. Freeze the extracted runner and allocator identities through runner completion, then remove the private root only during terminal cleanup.
- [ ] Descriptor-open every canonical `r12-evidence/final-retest-r3/attempt-0001` directory and controller, require exact equality to the marker, and retain all directory FDs through terminal. Recheck scratch/listener/all bindings, then launch only the exact R14 driver once with argument 1 exactly the fresh scratch.
- [ ] Preserve inherited FD8, recorder, cleanup, one-ticket, original-report fallback, validation/review, and Option-C semantics. Any branch without one descriptor-valid driver terminal becomes canonical BLOCKED through root's original report FD. No reopen, replay, allocator rerun, launch retry, or attempt-0002.
- [ ] At `VISUAL_ACK_REQUIRED`, return only the live PTY and every ordered fresh PNG path/SHA. Main root displays every image and obtains a fresh per-image verdict before one canonical ACK. No predecessor visual state may be reused or synthesized.

### Task 4: independently review grouped direct failure

- [ ] Apply inherited direct-failure review with R14 bindings. All predecessor and Task 2 history remains external to the fresh package.

### Task 5: audit and commit certified success

- [ ] Apply inherited success review/final gate with R14 bindings. First-parent history is exact length thirteen in runbook/R4/R5/R6/R7/R8/R9/R10/R11/R12/R13/R14/audit order; thirteen length-one path arrays have parents old-R3/runbook/R4/R5/R6/R7/R8/R9/R10/R11/R12/R13/R14.

## Appendix A: exact R14 driver builder

Extract the following Python body without fences. Exact identity: 134 lines / 6,115 bytes / SHA-256 `319fa5a286a006fd3c2114bb05a49caf6619b8ba21200f001decfa0fb82a91c1`. Invoke once as `builder.py SOURCE_R13_DRIVER OUTPUT_R14_DRIVER EXPECTED_PARENT_DEV EXPECTED_PARENT_INO`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_ID = (16777232, 306066235)
SOURCE_SIZE = 33696
SOURCE_SHA256 = "340d4899882b65481c3dda1514a3457b095e64106d8c07b56b63b7054d9793f4"
OUTPUT_SIZE = 33823
OUTPUT_SHA256 = "e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd"
OLD_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r13-verifier-recovery.md"
NEW_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md"
OLD_REPORT = "task-7-r12-followup-1-report.md"
NEW_REPORT = "task-7-r14-followup-1-report.md"
OLD_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8^)" = 9b0926b7f10a289d0fc4eb5d92649f85745f7890'
)
NEW_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse c0f38156cad28996cfddcabb1cf775ae84983cf5^)" = 76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8^)" = 9b0926b7f10a289d0fc4eb5d92649f85745f7890'
)


def identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_owned(path: Path) -> bytes:
    before = os.lstat(path)
    expected = identity(before)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size != SOURCE_SIZE or expected[:2] != SOURCE_ID:
        raise RuntimeError("unsafe R14 source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(fd)) != expected:
            raise RuntimeError("R14 source changed before open")
        raw = os.read(fd, SOURCE_SIZE + 1)
        if len(raw) != SOURCE_SIZE or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256 or identity(os.fstat(fd)) != expected:
            raise RuntimeError("R14 source bytes changed")
    finally:
        os.close(fd)
    if identity(os.lstat(path)) != expected:
        raise RuntimeError("R14 source path changed")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("R14 anchor differs")
    return text.replace(old, new, 1)


def transform_driver(raw: bytes) -> bytes:
    text = once(raw.decode(), OLD_PLAN, NEW_PLAN)
    text = once(text, OLD_REPORT, NEW_REPORT)
    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)
    payload = text.encode()
    if len(payload) != OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_SHA256:
        raise RuntimeError("R14 driver identity differs")
    return payload


def reverse_driver(payload: bytes) -> bytes:
    text = once(payload.decode(), NEW_TOPOLOGY, OLD_TOPOLOGY)
    text = once(text, NEW_REPORT, OLD_REPORT)
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
        raise RuntimeError("unsafe R14 output parent")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created: tuple[int, int] | None = None
    success = False
    try:
        opened_parent = os.fstat(parent_fd)
        if (opened_parent.st_dev, opened_parent.st_ino, opened_parent.st_uid, stat.S_IMODE(opened_parent.st_mode)) != expected:
            raise RuntimeError("R14 output parent changed")
        raw = read_owned(source)
        payload = transform_driver(raw)
        if reverse_driver(payload) != raw:
            raise RuntimeError("R14 raw reversal differs")
        fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            created = opened.st_dev, opened.st_ino
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise RuntimeError("short R14 write")
                view = view[count:]
            os.fsync(fd)
            final = os.fstat(fd)
            if (final.st_dev, final.st_ino) != created or final.st_uid != os.getuid() or stat.S_IMODE(final.st_mode) != 0o600 or final.st_nlink != 1 or final.st_size != len(payload):
                raise RuntimeError("R14 output identity differs")
        finally:
            os.close(fd)
        leaf = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if (leaf.st_dev, leaf.st_ino) != created:
            raise RuntimeError("R14 output path changed")
        os.fsync(parent_fd)
        after = os.lstat(parent)
        if (after.st_dev, after.st_ino, after.st_uid, stat.S_IMODE(after.st_mode)) != expected:
            raise RuntimeError("R14 output parent changed after create")
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
    print(f"R14_DRIVER_GREEN sha256={OUTPUT_SHA256} plan=1 report=1 topology=1 reversal=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable R14 offline harness

Extract the following Python body without fences. Exact identity: 128 lines / 6,417 bytes / SHA-256 `09e6b688ac32364e013402985dfe2d9a1ea370211f2b36c938c8ee8e52a0cc4b`. Run as `harness.py BUILDER RUNNER SOURCE_R13_DRIVER COMMITTED_R12_PLAN SOURCE_CONTROLLER MODELING_ROOT OUTPUT_ROOT` using the exact worktree Python 3.13 and canonical absolute arguments.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


BUILDER_SHA256 = "319fa5a286a006fd3c2114bb05a49caf6619b8ba21200f001decfa0fb82a91c1"
RUNNER_SHA256 = "a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9"
OUTPUT_SHA256 = "e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd"
R12_PLAN_SHA256 = "32be7ab4dbd854312cacaf64d13f3bd14431ce7ada54c1253c38c78df9720e5e"
ALLOCATOR_SHA256 = "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"
PYTHON = "/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13"
PYTHON_SYMLINK = "/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.venv/bin/python3"


def owned(path: Path, digest: str, mode: int) -> bytes:
    before = os.lstat(path)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1 or before.st_size > 1024 * 1024:
        raise RuntimeError("unsafe R14 harness input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        raw = os.read(fd, before.st_size + 1)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, before.st_size) or len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("R14 harness input differs")
    finally:
        os.close(fd)
    return raw


def extract_allocator(plan: bytes) -> bytes:
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
    return allocator


def write_new(path: Path, payload: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise RuntimeError("short R14 harness write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    if len(sys.argv) != 8:
        raise SystemExit("usage: harness.py BUILDER RUNNER SOURCE R12_PLAN SOURCE_CONTROLLER MODELING_ROOT OUTPUT_ROOT")
    builder, runner, source, r12_plan, source_controller, modeling_root, output_root = map(Path, sys.argv[1:])
    owned(builder, BUILDER_SHA256, 0o600)
    runner_raw = owned(runner, RUNNER_SHA256, 0o600)
    plan_raw = owned(r12_plan, R12_PLAN_SHA256, 0o644)
    if plan_raw.count(b"\n") != 444 or len(plan_raw) != 27434:
        raise RuntimeError("R12 Plan shape differs")
    root_info = os.lstat(output_root)
    if output_root != Path(os.path.realpath(output_root)) or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700 or any(output_root.iterdir()):
        raise RuntimeError("unsafe R14 harness root")
    modeling_info = os.lstat(modeling_root)
    allocator = output_root / "r12_allocator.py"
    write_new(allocator, extract_allocator(plan_raw))
    namespace = {"__name__": "r14_runner_harness"}
    exec(compile(runner_raw, "<r14-runner>", "exec"), namespace)
    python_fd, _ = namespace["open_owned"](Path(PYTHON), "python", 0o755, 17439616, "7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683", (16777232, 259766870))
    os.close(python_fd)
    try:
        namespace["canonical"](Path(PYTHON_SYMLINK), "python")
    except RuntimeError:
        pass
    else:
        raise RuntimeError("R14 Python symlink was accepted")
    argv = namespace["build_argv"](allocator, source_controller, modeling_root, modeling_info.st_dev, modeling_info.st_ino)
    expected_argv = [PYTHON, str(allocator), str(source_controller), str(modeling_root), str(modeling_info.st_dev), str(modeling_info.st_ino)]
    if argv != expected_argv:
        raise RuntimeError("R14 canonical argv differs")
    try:
        namespace["build_argv"](allocator, Path("r3_controller.py"), modeling_root, modeling_info.st_dev, modeling_info.st_ino)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("R14 relative controller was accepted")
    try:
        namespace["build_argv"](allocator, source_controller, Path("modeling-remediation"), modeling_info.st_dev, modeling_info.st_ino)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("R14 relative root was accepted")
    output = output_root / "driver.sh"
    built = subprocess.run([sys.executable, str(builder), str(source), str(output), str(root_info.st_dev), str(root_info.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    expected = f"R14_DRIVER_GREEN sha256={OUTPUT_SHA256} plan=1 report=1 topology=1 reversal=1\n"
    if built.returncode or built.stdout != expected or built.stderr:
        raise RuntimeError(f"R14 builder failed: {built.returncode} {built.stdout!r} {built.stderr!r}")
    driver = owned(output, OUTPUT_SHA256, 0o600)
    subprocess.run(["/bin/bash", "-n", str(output)], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("R14 heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r14-heredoc-{number}>", "exec")
    anchor = b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n'
    if driver.count(anchor) != 1:
        raise RuntimeError("R14 run count differs")
    command = driver[driver.index(anchor):driver.index(b" || R3_RUN_EXIT=$?", driver.index(anchor))]
    if b"<" in command:
        raise RuntimeError("R14 run stdin redirect differs")
    print("R14_PLAN_HARNESS_GREEN driver=1 allocator_extract=1 argv_green=1 relative_source_red=1 relative_root_red=1 python_green=1 python_symlink_red=1 static=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix C: exact one-shot R14 allocator runner

Extract the following Python body without fences. Exact identity: 115 lines / 6,019 bytes / SHA-256 `a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9`. Invoke once as `r14_allocator_runner.py ALLOCATOR SOURCE_CONTROLLER MODELING_ROOT`; each argument is the exact canonical absolute path fixed in Task 3.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


PYTHON = Path("/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13")
PYTHON_ID = (16777232, 259766870)
PYTHON_UID = 501
PYTHON_MODE = 0o755
PYTHON_SIZE = 17439616
PYTHON_SHA256 = "7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683"
SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")
MODELING_ROOT = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation")
ALLOCATOR_SIZE = 5615
ALLOCATOR_SHA256 = "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"
SOURCE_ID = (16777232, 305390856)
SOURCE_SIZE = 285409
SOURCE_SHA256 = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"
MARKER = r"R12_ALLOCATION_GREEN dir1=[0-9]+:[0-9]+ dir2=[0-9]+:[0-9]+ dir3=[0-9]+:[0-9]+ controller=[0-9]+:[0-9]+\n"


def identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def canonical(path: Path, label: str) -> None:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RuntimeError(f"missing R14 {label}") from exc
    if resolved != path:
        raise RuntimeError(f"noncanonical R14 {label}")


def open_owned(path: Path, label: str, mode: int, size: int, digest: str, expected_id: tuple[int, int] | None = None) -> tuple[int, tuple[int, ...]]:
    canonical(path, label)
    before = os.lstat(path)
    expected = identity(before)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1 or before.st_size != size or (expected_id is not None and expected[:2] != expected_id):
        raise RuntimeError(f"unsafe R14 {label}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(fd)) != expected:
            raise RuntimeError(f"changed R14 {label}")
        raw = os.read(fd, size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest or identity(os.fstat(fd)) != expected:
            raise RuntimeError(f"different R14 {label}")
    except BaseException:
        os.close(fd)
        raise
    if identity(os.lstat(path)) != expected:
        os.close(fd)
        raise RuntimeError(f"replaced R14 {label}")
    return fd, expected


def build_argv(allocator: Path, source: Path, root: Path, root_dev: int, root_ino: int) -> list[str]:
    canonical(allocator, "allocator")
    if source != SOURCE_CONTROLLER or root != MODELING_ROOT:
        raise RuntimeError("unexpected R14 allocator argument")
    current_root = os.lstat(root)
    if (current_root.st_dev, current_root.st_ino) != (root_dev, root_ino):
        raise RuntimeError("unexpected R14 allocator argument")
    return [str(PYTHON), str(allocator), str(source), str(root), str(root_dev), str(root_ino)]


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: r14_allocator_runner.py ALLOCATOR SOURCE_CONTROLLER MODELING_ROOT")
    allocator, source, root = map(Path, sys.argv[1:])
    if os.getuid() != PYTHON_UID:
        raise RuntimeError("unexpected R14 uid")
    python_fd, python_id = open_owned(PYTHON, "python", PYTHON_MODE, PYTHON_SIZE, PYTHON_SHA256, PYTHON_ID)
    allocator_fd, allocator_id = open_owned(allocator, "allocator", 0o600, ALLOCATOR_SIZE, ALLOCATOR_SHA256)
    source_fd, source_id = open_owned(source, "controller", 0o600, SOURCE_SIZE, SOURCE_SHA256, SOURCE_ID)
    root_fd = -1
    try:
        canonical(root, "modeling root")
        before = os.lstat(root)
        expected_root = before.st_dev, before.st_ino, before.st_uid, stat.S_IMODE(before.st_mode)
        if not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o700:
            raise RuntimeError("unsafe R14 modeling root")
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened_root = os.fstat(root_fd)
        if (opened_root.st_dev, opened_root.st_ino, opened_root.st_uid, stat.S_IMODE(opened_root.st_mode)) != expected_root:
            raise RuntimeError("changed R14 modeling root")
        argv = build_argv(allocator, source, root, opened_root.st_dev, opened_root.st_ino)
        if identity(os.fstat(python_fd)) != python_id or identity(os.lstat(PYTHON)) != python_id or identity(os.fstat(allocator_fd)) != allocator_id or identity(os.lstat(allocator)) != allocator_id or identity(os.fstat(source_fd)) != source_id or identity(os.lstat(source)) != source_id:
            raise RuntimeError("changed R14 allocator input")
        completed = subprocess.run(argv, text=True, capture_output=True, timeout=30)
        after_root = os.lstat(root)
        if (after_root.st_dev, after_root.st_ino, after_root.st_uid, stat.S_IMODE(after_root.st_mode)) != expected_root:
            raise RuntimeError("replaced R14 modeling root")
        if identity(os.fstat(python_fd)) != python_id or identity(os.lstat(PYTHON)) != python_id or identity(os.fstat(allocator_fd)) != allocator_id or identity(os.lstat(allocator)) != allocator_id or identity(os.fstat(source_fd)) != source_id or identity(os.lstat(source)) != source_id:
            raise RuntimeError("replaced R14 allocator input")
        if completed.returncode != 0 or completed.stderr != "" or re.fullmatch(MARKER, completed.stdout) is None:
            raise RuntimeError("R14 allocator result differs")
    finally:
        if root_fd >= 0:
            os.close(root_fd)
        os.close(source_fd)
        os.close(allocator_fd)
        os.close(python_fd)
    sys.stdout.write(completed.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
