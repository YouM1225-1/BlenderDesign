# Official Blender MCP R11 Journal-Clock Follow-up Plan

> **For agentic workers:** execute this Plan task-by-task; R10 is immutable and no predecessor launch may be replayed.

**Goal:** Remove the invalid cross-process FIFO timestamp-envelope assertion while retaining every deterministic journal/manifest binding, then perform one fresh certified run.

**Architecture:** Freeze R10 as a valid dispatch with a terminal validator rejection. Derive one R11 controller from the exact R10 controller by deleting only the eight-line cross-process envelope loop, and derive one R11 driver by changing only controller SHA, Plan/topology, attempt root, and report path. Everything live uses a fresh namespace, ticket, report, GUI session, scratch, images, user verdicts, and ACK.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is R10 Plan commit `ad89648ae3a4ff620ff30285a48d1317f4b9782b`; R10 Plan is 364 lines / 24,269 bytes / SHA-256 `39467c5385012fa0c98fa70fbf33812fec6e06b24f369e95dea46a4a17169318`.
- R10 Task 2 PASS report is dev/inode `16777232/304267923`, native-0600/nlink-1, 2,143 bytes, SHA-256 `447f545ade6fa4f710a9a4757c919eeca50753ac9ff0bcf35531b185deb48e1a`. Its runtime parent is dev/inode `16777232/304267924`, native-0700, with sole driver inode `304267927`, 33,300 bytes, SHA-256 `215e20c1ec0859ad36760ea1cb9a4bd054e3459b100cb6acc126f5d2de56d0d7`.
- R10 followup report is dev/inode `16777232/304447902`, native-0600/nlink-1, 201 bytes, SHA-256 `fe59b5598b874b7068f27f37807fb7cbb957fb74aaf1cd952503db5f522cb654`, with unique `actual_run_count: 1` and `STATUS: BLOCKED`. Its brief is dev/inode `16777232/305024699`, native-0600/nlink-1, 4,446 bytes, SHA-256 `138e4bd6c5d1fc6fc1f5f123b0778f1fa0a30ea9e34d7f2783c5b265ba504ef8`. Never reopen, append, replace, delete, or relabel either.
- R10 attempt is dev/inode `16777232/305024758`, native-0700. Exact controller inode `305024759`, 285,770 bytes, SHA-256 `c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc`; ticket inode `305025348`, SHA-256 `68fbecf7cdc3e0a5833bc327e8e7f7e1dc7aa2145a9456377f0e89f2e7e655f3`; journal inode `305025095`, 15,305 bytes, SHA-256 `054f91da57a762c61e82d45d4bb2d6214ccd0c1019d7ec7fd19f7161275faecb`; dispatch manifest inode `305025505`, 226,054 bytes, SHA-256 `9aa5407dfc3d87fb94fac990e27b4c0ba753c15fb81ab955d796114ec55a090e`. Freeze the entire attempt closure: lexically sorted 21 regular leaves encoded as canonical JSON rows with keys `path,dev,ino,uid,mode,nlink,size,sha256`, sorted keys, compact separators and one trailing LF are 3,781 bytes / SHA-256 `f3a1965993658f4aa51bfb73e3f5009dfbce92de646ffb80b66e26c90821d492`.
- R10 has 56 exact ordered journal events and 26 call rows. All calls are `outcome=pass`, with zero dispatch/acceptance errors and zero repeats. Four fresh R10 visual rows were individually user-PASS and ACKed once. This is diagnostic history only; no R10 byte, visual verdict, or ACK is reusable.
- Root cause is exact: controller writes the call-start FIFO record and then samples `dispatch_start_ns`; the recorder timestamps receipt asynchronously. All 26 R10 rows have `dispatch_start < journal_begin < dispatch_end < journal_finish`. Cross-process receipt time cannot safely envelope controller-local dispatch time without an ACK protocol.
- Preserve journal event count, event identity/order, sequence, UUID clock identity, UTC format/order, monotonic order, and all dispatch-manifest start/end/duration/digest checks. Only the cross-process envelope loop is deleted. No sleep, tolerance, timestamp rewrite, protocol bypass, wrapper, compatibility lane, retry, attempt-0002, old evidence finalization, or inherited ACK is allowed.
- `.superpowers/sdd/modeling-remediation/r11-live-runtime`, `r11-task2-report.md`, `r11-evidence`, and `task-7-r11-followup-1-{brief,report}.md` are absent.

## File map

- Commit only this Plan in Task 1.
- Create after Plan commit: `.superpowers/sdd/modeling-remediation/r11-live-runtime/{r3_controller.py,driver.sh}`, `r11-task2-{report,spec-review,quality-review}.md`.
- Create live only after admission/scratch GREEN: `.superpowers/sdd/modeling-remediation/r11-evidence/final-retest-r3/attempt-0001`, `task-7-r11-followup-1-{brief,report}.md` and conditional review artifacts with the same prefix.
- Modify the audit file only after certified success.

### Task 1: certify and commit this Plan

- [ ] Recheck every frozen identity/closure, clean HEAD, absent R11 targets/ticket, empty port 9876, and empty owned-process inventory.
- [ ] Extract Appendices A and B exactly. Run Appendix B once with exact interpreter `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.venv/bin/python3` and six canonical absolute path arguments in a fresh canonical native-0700 `/private/tmp` root. Require unique GREEN for exact controller deletion/reversal, exact driver reversal, R10 timing facts, controller Ruff/probe, Bash/heredoc/run shape, and allocation-parent replacement RED. It may not execute a live driver, Blender, or MCP.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan SHA. Any Critical, Important, or Minor burns the round.
- [ ] Commit only this Plan with message `docs: plan recorder clock semantics`, parent `ad89648ae3a4ff620ff30285a48d1317f4b9782b`, and clean status.

### Task 2: generate and review the R11 runtime

- [ ] Root exclusive-creates and retains original native-0600 report/spec-review/quality-review FDs, then exclusive-creates and retains the native-0700 runtime directory FD. Extract exact Appendix A and invoke it once to create exactly the controller and driver through that bound directory.
- [ ] Require declared identities, exact reversals, pinned Ruff, one controller-probe invocation through the exact worktree Python 3.13 with its exact two markers, `/bin/bash -n`, seven Python heredocs, one controller `run`, and no run stdin redirect. Do not execute a live driver, Blender, or MCP. Recheck all frozen state and absences before reviews.
- [ ] Fresh spec and quality reviewers write only their preallocated original FDs. Root descriptor-parses exact unique approvals, fsync/fstat/hash/path-freezes and closes both review FDs, records their exact identities through the original Task 2 report FD, then writes unique `STATUS: PASS`. Any failure records observations/counts and unique `STATUS: BLOCKED` through the original FD before closing all descriptors; no Task 2 retry exists.

### Task 3: perform the sole fresh live run

- [ ] Bind R11 Task 2 PASS and both recorded approvals, three Plan reviews, current R11 runtime parent/two leaves, exact R10 terminal closure, all older frozen history, clean Git, absent R11 live targets/ticket, empty port, and empty owned-process inventory. Preallocate the fresh report with an original read/write CLOEXEC FD retained only by root.
- [ ] Apply R10 Task 3 GUI/listener and exact Appendix-C scratch contract to the current Blender session. Derive fresh `T=realpath(bpy.app.tempdir)` and absent `S=T/blender_mcp`; after checker GREEN, create/freeze the fresh brief. No old tempdir, listener, scratch, image, verdict, or ACK is reusable.
- [ ] Through retained canonical directory FDs, exclusive-create `r11-evidence/final-retest-r3/attempt-0001` and copy the exact R11 runtime controller as its sole native-0600/nlink-1 leaf. Carry every parent/leaf identity through prelaunch and terminal. Launch only the exact R11 driver once with argument 1 exactly `S`.
- [ ] Preserve R10/R8/R7 FD8, recorder, cleanup, one-ticket and original-report-FD fallback semantics after explicitly replacing admission, controller, attempt/report, Plan/driver and history bindings. Any branch without one descriptor-valid driver terminal is rewritten to canonical BLOCKED through root's retained original FD; no reopen, retry, or attempt-0002 exists.
- [ ] At `VISUAL_ACK_REQUIRED`, return only the live PTY and every ordered fresh R11 PNG path/SHA. Root displays every image and obtains a fresh verdict for every row before one canonical ACK. R10 verdicts are not reusable.

### Task 4: independently review grouped direct failure

- [ ] Apply inherited direct-failure review with R11 bindings. All Task 2 and predecessor failure/history artifacts remain external to the fresh package.

### Task 5: audit and commit certified success

- [ ] Apply inherited success review/final gate with R11 bindings. First-parent history is exact length ten in runbook/R4/R5/R6/R7/R8/R9/R10/R11/audit order; ten length-one path arrays have parents old-R3/runbook/R4/R5/R6/R7/R8/R9/R10/R11.

## Appendix A: exact R11 runtime builder

Extract the following Python body without fences. Exact identity: 156 lines / 8,025 bytes / SHA-256 `800b1a731234f517105db951120fa97cecbc56f22e4d6e58c2d399720674e585`. Invoke once as `builder.py SOURCE_CONTROLLER SOURCE_DRIVER OUTPUT_ROOT EXPECTED_PARENT_DEV EXPECTED_PARENT_INO`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


CONTROLLER_SOURCE_ID = (16777232, 305024759)
CONTROLLER_SOURCE_SIZE = 285770
CONTROLLER_SOURCE_SHA256 = "c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc"
CONTROLLER_OUTPUT_SIZE = 285409
CONTROLLER_OUTPUT_SHA256 = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"
DRIVER_SOURCE_ID = (16777232, 304267927)
DRIVER_SOURCE_SIZE = 33300
DRIVER_SOURCE_SHA256 = "215e20c1ec0859ad36760ea1cb9a4bd054e3459b100cb6acc126f5d2de56d0d7"
DRIVER_OUTPUT_SIZE = 33432
DRIVER_OUTPUT_SHA256 = "d38e792492fee3a8fcab2b6bb5d4243c90acb1840ea4f35cd420d3bcdb11d3db"
OLD_CONTROLLER_BLOCK = b'''    for index, row in enumerate(calls):\n        begin = events[2 + index * 2]\n        finish = events[3 + index * 2]\n        if not (\n            begin["monotonic_ns"] <= row["dispatch_start_ns"]\n            < row["dispatch_end_ns"] <= finish["monotonic_ns"]\n        ):\n            raise R2Error("JOURNAL", f"journal does not envelope dispatch: {row['tool']}")\n'''
CONTROLLER_INSERT_ANCHOR = b"\n\ndef production_tool_section(text: str) -> list[str]:\n"
OLD_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r10-scratch-arg.md"
NEW_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r11-journal-clock.md"
OLD_ATTEMPT = ".superpowers/sdd/modeling-remediation/r10-evidence/final-retest-r3/attempt-0001"
NEW_ATTEMPT = ".superpowers/sdd/modeling-remediation/r11-evidence/final-retest-r3/attempt-0001"
OLD_REPORT = "task-7-r10-followup-1-report.md"
NEW_REPORT = "task-7-r11-followup-1-report.md"
OLD_CONTROLLER_SHA256 = CONTROLLER_SOURCE_SHA256
NEW_CONTROLLER_SHA256 = CONTROLLER_OUTPUT_SHA256
OLD_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 45df35ef4cf7a00707d65352e2f7059357b2ecac\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 45df35ef4cf7a00707d65352e2f7059357b2ecac^)" = 436c3c2b92fe45030b73439b9c67278c92090a7c'
)
NEW_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = ad89648ae3a4ff620ff30285a48d1317f4b9782b\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse ad89648ae3a4ff620ff30285a48d1317f4b9782b^)" = 45df35ef4cf7a00707d65352e2f7059357b2ecac\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 45df35ef4cf7a00707d65352e2f7059357b2ecac^)" = 436c3c2b92fe45030b73439b9c67278c92090a7c'
)


def identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def read_owned(path: Path, expected_id: tuple[int, int], size: int, digest: str) -> bytes:
    before = os.lstat(path)
    expected = identity(before)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size != size or expected[:2] != expected_id:
        raise RuntimeError("unsafe R11 source")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(fd)) != expected:
            raise RuntimeError("R11 source changed before open")
        raw = os.read(fd, size + 1)
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest or identity(os.fstat(fd)) != expected:
            raise RuntimeError("R11 source bytes changed")
    finally:
        os.close(fd)
    if identity(os.lstat(path)) != expected:
        raise RuntimeError("R11 source path changed")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("R11 anchor is not unique")
    return text.replace(old, new, 1)


def build_controller(raw: bytes) -> bytes:
    if raw.count(OLD_CONTROLLER_BLOCK) != 1:
        raise RuntimeError("R11 controller anchor differs")
    payload = raw.replace(OLD_CONTROLLER_BLOCK, b"", 1)
    if len(payload) != CONTROLLER_OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != CONTROLLER_OUTPUT_SHA256:
        raise RuntimeError("R11 controller identity differs")
    return payload


def build_driver(raw: bytes) -> bytes:
    text = once(raw.decode(), OLD_PLAN, NEW_PLAN)
    if text.count(OLD_ATTEMPT) != 2:
        raise RuntimeError("R11 attempt anchor differs")
    text = text.replace(OLD_ATTEMPT, NEW_ATTEMPT)
    text = once(text, OLD_REPORT, NEW_REPORT)
    text = once(text, OLD_CONTROLLER_SHA256, NEW_CONTROLLER_SHA256)
    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)
    payload = text.encode()
    if len(payload) != DRIVER_OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != DRIVER_OUTPUT_SHA256:
        raise RuntimeError("R11 driver identity differs")
    return payload


def write_leaf(parent_fd: int, name: str, payload: bytes) -> tuple[int, int]:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        created = opened.st_dev, opened.st_ino
        view = memoryview(payload)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise RuntimeError("short R11 write")
            view = view[count:]
        os.fsync(fd)
        final = os.fstat(fd)
        if (final.st_dev, final.st_ino) != created or final.st_uid != os.getuid() or stat.S_IMODE(final.st_mode) != 0o600 or final.st_nlink != 1 or final.st_size != len(payload):
            raise RuntimeError("R11 output identity differs")
    finally:
        os.close(fd)
    leaf = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (leaf.st_dev, leaf.st_ino) != created:
        raise RuntimeError("R11 output path changed")
    return created


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit("usage: builder.py CONTROLLER_SOURCE DRIVER_SOURCE OUTPUT_ROOT PARENT_DEV PARENT_INO")
    controller_source, driver_source, root = map(Path, sys.argv[1:4])
    expected_parent = int(sys.argv[4]), int(sys.argv[5])
    before = os.lstat(root)
    expected = before.st_dev, before.st_ino, before.st_uid, stat.S_IMODE(before.st_mode)
    if root != Path(os.path.realpath(root)) or expected[:2] != expected_parent or not stat.S_ISDIR(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o700 or any(root.iterdir()):
        raise RuntimeError("unsafe R11 output root")
    controller = build_controller(read_owned(controller_source, CONTROLLER_SOURCE_ID, CONTROLLER_SOURCE_SIZE, CONTROLLER_SOURCE_SHA256))
    driver = build_driver(read_owned(driver_source, DRIVER_SOURCE_ID, DRIVER_SOURCE_SIZE, DRIVER_SOURCE_SHA256))
    parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created: list[tuple[str, tuple[int, int]]] = []
    success = False
    try:
        opened = os.fstat(parent_fd)
        if (opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode)) != expected:
            raise RuntimeError("R11 output root changed")
        created.append(("r3_controller.py", write_leaf(parent_fd, "r3_controller.py", controller)))
        created.append(("driver.sh", write_leaf(parent_fd, "driver.sh", driver)))
        os.fsync(parent_fd)
        after = os.lstat(root)
        if (after.st_dev, after.st_ino, after.st_uid, stat.S_IMODE(after.st_mode)) != expected:
            raise RuntimeError("R11 output root changed after write")
        success = True
    finally:
        if not success:
            for name, created_id in reversed(created):
                try:
                    leaf = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if (leaf.st_dev, leaf.st_ino) == created_id:
                        os.unlink(name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
        os.close(parent_fd)
    print(f"R11_RUNTIME_GREEN controller={CONTROLLER_OUTPUT_SHA256} driver={DRIVER_OUTPUT_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable R11 harness

Extract the following Python body without fences. Exact identity: 104 lines / 6,498 bytes / SHA-256 `707e658be0b76aafd6cb2a30895129c0e3bde053b174adc230fba5ea369a3c6e`. Run `harness.py BUILDER SOURCE_CONTROLLER SOURCE_DRIVER EVENTS DISPATCH OUTPUT_ROOT` in a fresh canonical native-0700 root with `TMPDIR=/private/tmp` and `PYTHONDONTWRITEBYTECODE=1`.

````python
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


BUILDER_SHA256 = "800b1a731234f517105db951120fa97cecbc56f22e4d6e58c2d399720674e585"
CONTROLLER_SOURCE_SHA256 = "c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc"
CONTROLLER_OUTPUT_SHA256 = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"
DRIVER_SOURCE_SHA256 = "215e20c1ec0859ad36760ea1cb9a4bd054e3459b100cb6acc126f5d2de56d0d7"
DRIVER_OUTPUT_SHA256 = "d38e792492fee3a8fcab2b6bb5d4243c90acb1840ea4f35cd420d3bcdb11d3db"
EVENTS_SHA256 = "054f91da57a762c61e82d45d4bb2d6214ccd0c1019d7ec7fd19f7161275faecb"
DISPATCH_SHA256 = "9aa5407dfc3d87fb94fac990e27b4c0ba753c15fb81ab955d796114ec55a090e"


def owned(path: Path, digest: str) -> bytes:
    before = os.lstat(path)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size > 1024 * 1024:
        raise RuntimeError("unsafe R11 harness input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, before.st_size):
            raise RuntimeError("R11 harness input changed")
        raw = os.read(fd, before.st_size + 1)
        if len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("R11 harness digest differs")
    finally:
        os.close(fd)
    return raw


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit("usage: harness.py BUILDER CONTROLLER DRIVER EVENTS DISPATCH OUTPUT_ROOT")
    builder, controller_source, driver_source, events_path, dispatch_path, root = map(Path, sys.argv[1:])
    builder_raw = owned(builder, BUILDER_SHA256)
    controller_raw = owned(controller_source, CONTROLLER_SOURCE_SHA256)
    driver_raw = owned(driver_source, DRIVER_SOURCE_SHA256)
    events_raw = owned(events_path, EVENTS_SHA256)
    dispatch_raw = owned(dispatch_path, DISPATCH_SHA256)
    namespace: dict[str, object] = {"__name__": "r11_builder_harness"}
    exec(compile(builder_raw, str(builder), "exec"), namespace)
    info = os.lstat(root)
    if root != Path(os.path.realpath(root)) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700 or any(root.iterdir()):
        raise RuntimeError("unsafe R11 harness root")
    run = subprocess.run([sys.executable, str(builder), str(controller_source), str(driver_source), str(root), str(info.st_dev), str(info.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    if run.returncode or run.stdout.count("R11_RUNTIME_GREEN ") != 1:
        raise RuntimeError(f"R11 builder failed: {run.stderr}")
    controller = owned(root / "r3_controller.py", CONTROLLER_OUTPUT_SHA256)
    driver = owned(root / "driver.sh", DRIVER_OUTPUT_SHA256)
    anchor = namespace["CONTROLLER_INSERT_ANCHOR"]
    if controller.count(anchor) != 1 or controller.replace(anchor, namespace["OLD_CONTROLLER_BLOCK"] + anchor, 1) != controller_raw:
        raise RuntimeError("R11 controller reversal differs")
    text = driver.decode()
    reversed_driver = text.replace(namespace["NEW_PLAN"], namespace["OLD_PLAN"], 1).replace(namespace["NEW_ATTEMPT"], namespace["OLD_ATTEMPT"]).replace(namespace["NEW_REPORT"], namespace["OLD_REPORT"], 1).replace(namespace["NEW_CONTROLLER_SHA256"], namespace["OLD_CONTROLLER_SHA256"], 1).replace(namespace["NEW_TOPOLOGY"], namespace["OLD_TOPOLOGY"], 1)
    if reversed_driver.encode() != driver_raw:
        raise RuntimeError("R11 driver reversal differs")
    ruff = subprocess.run(["/Users/yeminjie/.local/bin/uvx", "--quiet", "ruff@0.16.2", "check", "--no-cache", "--isolated", "--target-version", "py313", "--select", "E4,E7,E9,F", str(root / "r3_controller.py")], text=True, capture_output=True, timeout=30, check=False)
    if ruff.returncode:
        raise RuntimeError(f"R11 Ruff failed: {ruff.stdout}{ruff.stderr}")
    probe = subprocess.run([sys.executable, str(root / "r3_controller.py"), "probe"], text=True, capture_output=True, timeout=30, check=False, env={**os.environ, "TMPDIR": "/private/tmp", "PYTHONDONTWRITEBYTECODE": "1"})
    if probe.returncode or probe.stdout.count("R3_FAILURE_DIAGNOSTICS_GREEN ") != 1 or probe.stdout.count("R3_PROTOCOL_R20_1_GREEN ") != 1:
        raise RuntimeError(f"R11 controller probe failed: {probe.stdout}{probe.stderr}")
    subprocess.run(["/bin/bash", "-n", str(root / "driver.sh")], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("R11 heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r11-heredoc-{number}>", "exec")
    if driver.count(b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n') != 1:
        raise RuntimeError("R11 controller run count differs")
    events = [json.loads(line) for line in events_raw.splitlines()]
    dispatch_rows = [json.loads(line) for line in dispatch_raw.splitlines()]
    calls = [row for row in dispatch_rows if row.get("record_type") == "call"]
    if len(events) != 56 or len(calls) != 26:
        raise RuntimeError("R11 frozen timing cardinality differs")
    for index, row in enumerate(calls):
        begin = events[2 + index * 2]["monotonic_ns"]
        finish = events[3 + index * 2]["monotonic_ns"]
        start, end = row["dispatch_start_ns"], row["dispatch_end_ns"]
        if not (start < begin < end < finish):
            raise RuntimeError("R11 frozen timing order differs")
    swap = root.parent / "swap"
    swap.mkdir(mode=0o700)
    allocated = os.lstat(swap)
    held = root.parent / "held"
    os.rename(swap, held)
    os.mkdir(swap, 0o700)
    parent_red = subprocess.run([sys.executable, str(builder), str(controller_source), str(driver_source), str(swap), str(allocated.st_dev), str(allocated.st_ino)], text=True, capture_output=True, timeout=30, check=False)
    if parent_red.returncode == 0 or "R11_RUNTIME_GREEN" in parent_red.stdout or any(swap.iterdir()) or any(held.iterdir()):
        raise RuntimeError("R11 allocation-parent replacement accepted")
    print("R11_PLAN_HARNESS_GREEN controller=1 driver=1 old_envelope_red=26 probe=1 allocation_parent_red=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
