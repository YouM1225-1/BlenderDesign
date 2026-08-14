# Official Blender MCP R5 Verifier Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Complete the still-unconsumed R3 Blender/MCP run once by correcting the single pre-ticket verifier lookup that terminated the certified R4 file driver.

**Architecture:** Keep the certified R3 controller, evidence root, attempt name, protocol, Option-C acknowledgement, recorder, cleanup, and review state machine unchanged. Derive one R5 driver from the frozen R4 driver with four exact textual substitutions: read the exported controller digest through `os.environ`, point at followup-3 report and this Plan, and bind the additional Plan-only commit in Git topology. No controller patch, retry loop, second attempt, or new transport exists.

**Tech Stack:** Bash 3.2+, Python 3.13 through `/Users/yeminjie/.local/bin/uv`, Git, macOS `lsof`/`ps`, Blender 5.2 LTS, official Blender MCP add-on.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- The evidence root is exactly `.superpowers/sdd/modeling-remediation/final-retest-r3` relative to that worktree root.
- Clean base HEAD is R4 Plan commit `81752dd10be750964d72cda9036db32e0cd2baf2`; its parent is runbook commit `8d05ec975a6ba7317d5e9c23963233b2f2d11832`.
- R4 Plan is `docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md`, 1,005 lines, 58,598 bytes, SHA-256 `5d31005d65ea7b6f5f13cc73295683ef3da67dbc67c03f2daa3b9eafde88c4ac`.
- R4 driver is `.superpowers/sdd/modeling-remediation/r4-live-driver/driver.sh`, dev `16777232`, inode `301212712`, uid `501`, mode `0600`, nlink `1`, 805 lines, 32,482 bytes, SHA-256 `369c1f7eeb910acceb4a9c85a2d696e4a89a00a338121bead51cc0fa4bc68fd8`.
- Certified controller is `.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001/r3_controller.py`, dev `16777232`, inode `301445840`, mode `0600`, nlink `1`, 6,924 lines, 285,387 bytes, SHA-256 `7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a`.
- `run-ticket.json` and `attempt-0002` are absent, so actual run count remains exactly zero. Attempt-0001 contains only the controller. Port 9876 and owned Blender/controller/recorder processes are absent.
- Failed followup-1 brief/report pair remains dev/inodes `16777232/299417373` and `16777232/299417372`, mode `0600`, nlink `1`, sizes `19975` and `0`, SHA-256 values `40de66889cc904e8f51509c5cd1424ff12204f4b67c91590786ea2a4b35e0a24` and the empty SHA-256; never reopen, append, replace, unlink, or reuse its report.
- Failed followup-2 brief remains dev/inode `16777232/301399373`, mode `0600`, nlink `1`, size `2408`, SHA-256 `73f9655b6680caf97fd236c7c0d988b224107bd6e6350a572e39b46677bd10bf`.
- Failed followup-2 report remains dev/inode `16777232/301399372`, mode `0600`, nlink `1`, size `0`, empty SHA-256; never reopen, append, replace, unlink, or reuse it.
- The sole R4 PTY exited before ticket acquisition. Its output was not durably retained; certification relies on mechanically reproducing the unique bare verifier lookup plus the bound empty report/ticket state, not on this Plan's account of terminal text.
- Reuse `.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001` and its existing controller. Never create attempt-0002, regenerate/patch the controller, or rerun controller probes inside the evidence root.
- Before this Plan-only commit, do not start Blender/MCP. After it, do not modify either Plan, runbook, tests, controller, application code, or MCP source.
- Any failed guard, lost PTY/FD, malformed ACK/review, unexpected attempt leaf, or identity drift is fail-closed. This Plan authorizes at most one successful run-ticket acquisition and no retry.

## File map

- Create/commit: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r5-verifier-env.md`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r5-live-driver/build.py` and `driver.sh`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-3-brief.md` and `task-7-followup-3-report.md`.
- Modify only after certified success: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`.

### Task 1: adversarially certify and commit this Plan

- [ ] Prove every frozen identity, empty ticket/process state, old empty report, and clean HEAD. Mechanically reproduce from the frozen R4 driver that the pre-run verifier has exactly one bare `CONTROLLER_SHA256` load and no Python binding for it; do not treat historical PTY text as durable evidence.
- [ ] Extract Appendices A and B byte-for-byte, compile them in memory, and run Appendix B in a fresh native mode-0700 `/private/tmp` root against the frozen R4 driver. Require its unique GREEN line; all declared mutation/parent-swap negatives must be RED.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan SHA. Each uses a fresh native-0600/nlink-1 report and writes only through its original descriptor. Any Critical, Important, or Minor finding burns the round; repair only this Plan and repeat all three.
- [ ] Commit only this Plan with message `docs: plan verifier environment Blender retest`. Require parent `81752dd10be750964d72cda9036db32e0cd2baf2`, one changed path, and clean status. Do not start Blender/MCP.

### Task 2: generate and prove the corrected file driver

- [ ] Exclusive-create `.superpowers/sdd/modeling-remediation/r5-live-driver` mode 0700. Extract Appendix A exactly to `build.py`, compile in memory, and create no pyc.
- [ ] Run `build.py R4_DRIVER R5_DRIVER`. Require frozen input identity and exact output identity declared in Appendix A, native 0600/nlink-1, `/bin/bash -n`, seven compilable Python heredocs, and exactly one controller `run` with no driver stdin redirection.

### Task 3: perform the sole live run with the corrected driver

- [ ] Root exclusive-creates followup-3 report native 0600/nlink-1 and a compact brief binding this Plan commit/SHA; R4 Plan commit/SHA `81752dd10be750964d72cda9036db32e0cd2baf2`/`5d31005d65ea7b6f5f13cc73295683ef3da67dbc67c03f2daa3b9eafde88c4ac`; runbook commit/SHA `8d05ec975a6ba7317d5e9c23963233b2f2d11832`/`658c1b20ff9569f05f32a699d3dcbd496201be30fc96efaa538d4e808f26136c`; R5 driver identity; existing controller identity; both prior brief/report identity pairs; new report identity; `ACTUAL_RUN_LIMIT=1`; and absent ticket/processes. The brief points to this Plan and the bound R4 Plan Tasks 3 through 5; it copies no prose.
- [ ] Apply R4 Task 3 Step 2 exactly; the fail-closed preflight terminal is unchanged.
- [ ] Recheck attempt-0001 contains exactly the frozen controller and no ticket; do not regenerate it. Recheck R5 driver and repo topology. Use the ten arguments in the exact order defined by R4 Task 3 Step 3 and launch exactly once with the argv form in R4 Task 3 Step 4, substituting the R5 Plan commit/SHA and followup-3 report dev/ino.
- [ ] Apply R4 Task 3 Steps 5 through 7 exactly; no acknowledgement, cleanup, FD8, or review-gate behavior changes.

### Task 4: independently review a direct failure

- [ ] Apply R4 Task 4 exactly with these substitutions only: current Plan/commit/SHA; followup-3 report; `task-7-followup-3-failure-{root-checks.json,review-package.json,review.md}`.

### Task 5: audit and commit a successful Option-C run

- [ ] Apply R4 Task 5 exactly with these substitutions only: current Plan/commit/SHA; followup-3 report; `task-7-followup-3-success-{root-checks.json,review-package.json,review.md}`. In Step 3, replace only the length-three `git.first_parent` rule with an exact length-four array in runbook/R4-Plan/R5-Plan/audit order. Its four length-one `paths` arrays map respectively to `docs/use-official-blender-mcp.md`, the R4 Plan path, this R5 Plan path, and the modeling-audit path; its `parent` values equal old R3 Plan, runbook, R4 Plan, and R5 Plan commits respectively.

## Appendix A: exact R5 driver patcher

Extract the following Python body without its Markdown fences. It is exactly 200 lines, 7,533 bytes, SHA-256 `95ed0cec8b2c2adec937f9a44383bea88e72d2e21fdb17aa30317e6ab84f0171`. It accepts exactly `R4_DRIVER R5_DRIVER` and performs no other substitution.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_SIZE = 32482
SOURCE_SHA256 = "369c1f7eeb910acceb4a9c85a2d696e4a89a00a338121bead51cc0fa4bc68fd8"
SOURCE_DEV = 16777232
SOURCE_INO = 301212712
OUTPUT_SIZE = 32620
OUTPUT_SHA256 = "43fc40289f029d9fd763208d57914ccd9ddb359c81790662c1b1ca5fa44ede44"
R4_PLAN_COMMIT = "81752dd10be750964d72cda9036db32e0cd2baf2"


def leaf_identity(value: os.stat_result) -> tuple[int, ...]:
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
    return value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode)


def read_owned(path: Path) -> bytes:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("source driver path is not canonical")
    parent = path.parent
    before_parent = os.lstat(parent)
    if (
        not stat.S_ISDIR(before_parent.st_mode)
        or stat.S_ISLNK(before_parent.st_mode)
        or before_parent.st_uid != os.getuid()
        or stat.S_IMODE(before_parent.st_mode) != 0o700
    ):
        raise RuntimeError("source driver parent is unsafe")
    parent_id = parent_identity(before_parent)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if parent_identity(os.fstat(parent_fd)) != parent_id:
            raise RuntimeError("source driver parent changed")
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size != SOURCE_SIZE
            or (before.st_dev, before.st_ino) != (SOURCE_DEV, SOURCE_INO)
        ):
            raise RuntimeError("source driver identity differs")
        before_id = leaf_identity(before)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if leaf_identity(os.fstat(fd)) != before_id:
                raise RuntimeError("source driver changed before open")
            chunks = bytearray()
            while len(chunks) < SOURCE_SIZE:
                chunk = os.read(fd, min(65536, SOURCE_SIZE - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            raw = bytes(chunks)
            if len(raw) != SOURCE_SIZE or os.read(fd, 1):
                raise RuntimeError("source driver bounded read differs")
            if leaf_identity(os.fstat(fd)) != before_id:
                raise RuntimeError("source driver changed during read")
        finally:
            os.close(fd)
        if (
            leaf_identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != before_id
            or parent_identity(os.fstat(parent_fd)) != parent_id
            or parent_identity(os.lstat(parent)) != parent_id
        ):
            raise RuntimeError("source driver path changed")
    finally:
        os.close(parent_fd)
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("source driver digest differs")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"patch anchor count differs: {old!r}")
    return text.replace(old, new)


def build(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    text = once(
        text,
        "hashlib.sha256(controller).hexdigest() != CONTROLLER_SHA256",
        'hashlib.sha256(controller).hexdigest() != os.environ["CONTROLLER_SHA256"]',
    )
    text = once(text, "task-7-followup-2-report.md", "task-7-followup-3-report.md")
    text = once(
        text,
        "docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md",
        "docs/superpowers/plans/2026-08-14-official-blender-mcp-r5-verifier-env.md",
    )
    text = once(
        text,
        '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = "$R3_RUNBOOK_COMMIT"',
        '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = '
        f'{R4_PLAN_COMMIT}\n'
        f'  test "$(git -C "$FEATURE_ROOT" rev-parse {R4_PLAN_COMMIT}^)" = "$R3_RUNBOOK_COMMIT"',
    )
    payload = text.encode("utf-8")
    if len(payload) != OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_SHA256:
        raise RuntimeError("patched driver identity differs")
    return payload


def write_owned(path: Path, payload: bytes) -> os.stat_result:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("output path is not canonical")
    parent = path.parent
    info = os.lstat(parent)
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RuntimeError("output parent is unsafe")
    parent_id = parent_identity(info)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if parent_identity(os.fstat(parent_fd)) != parent_id:
            raise RuntimeError("output parent changed before open")
        fd = os.open(
            path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            try:
                view = memoryview(payload)
                while view:
                    count = os.write(fd, view)
                    if count <= 0:
                        raise RuntimeError("short output write")
                    view = view[count:]
                os.fsync(fd)
                final = os.fstat(fd)
                current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    leaf_identity(current) != leaf_identity(final)
                    or final.st_uid != os.getuid()
                    or stat.S_IMODE(final.st_mode) != 0o600
                    or final.st_nlink != 1
                    or final.st_size != len(payload)
                    or parent_identity(os.fstat(parent_fd)) != parent_id
                    or parent_identity(os.lstat(parent)) != parent_id
                ):
                    raise RuntimeError("output identity changed")
            except BaseException:
                opened = os.fstat(fd)
                try:
                    current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                except OSError:
                    pass
                else:
                    if (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino):
                        os.unlink(path.name, dir_fd=parent_fd)
                raise
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)
    return final


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: build.py R4_DRIVER R5_DRIVER")
    payload = build(read_owned(Path(sys.argv[1])))
    final = write_owned(Path(sys.argv[2]), payload)
    print(
        f"R5_DRIVER_GREEN lines={len(payload.splitlines())} bytes={len(payload)} "
        f"sha256={hashlib.sha256(payload).hexdigest()} dev={final.st_dev} ino={final.st_ino}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable patch harness

Extract this Python body without its Markdown fences. It is exactly 215 lines, 8,483 bytes, SHA-256 `fd86d32b2bf1b15484fc5d0b941aa3a2092e9a4360289f7403b1e6179fc0b62a`. Run `harness.py BUILD_PY R4_DRIVER OUTPUT_ROOT`, where OUTPUT_ROOT is an empty native mode-0700 `/private/tmp` directory; both input paths must be canonical absolute paths.

````python
from __future__ import annotations

import ast
import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


BUILD_SHA256 = "95ed0cec8b2c2adec937f9a44383bea88e72d2e21fdb17aa30317e6ab84f0171"
SOURCE_SHA256 = "369c1f7eeb910acceb4a9c85a2d696e4a89a00a338121bead51cc0fa4bc68fd8"
SOURCE_DEV = 16777232
SOURCE_INO = 301212712
OUTPUT_SHA256 = "43fc40289f029d9fd763208d57914ccd9ddb359c81790662c1b1ca5fa44ede44"


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


def owned(path: Path, expected_sha: str, expected_identity: tuple[int, int] | None = None) -> bytes:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("harness input path is not canonical")
    parent = path.parent
    parent_info = os.lstat(parent)
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_ISLNK(parent_info.st_mode)
        or parent_info.st_uid != os.getuid()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
    ):
        raise RuntimeError("harness input parent is unsafe")
    parent_id = identity(parent_info)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size > 1024 * 1024
            or (expected_identity is not None and (before.st_dev, before.st_ino) != expected_identity)
        ):
            raise RuntimeError("harness input is unsafe")
        before_id = identity(before)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if identity(os.fstat(fd)) != before_id:
                raise RuntimeError("harness input changed before open")
            chunks = bytearray()
            while len(chunks) <= 1024 * 1024:
                chunk = os.read(fd, min(65536, 1024 * 1024 + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            raw = bytes(chunks)
            if len(raw) != before.st_size or os.read(fd, 1):
                raise RuntimeError("harness bounded read differs")
            if identity(os.fstat(fd)) != before_id:
                raise RuntimeError("harness input changed during read")
        finally:
            os.close(fd)
        if (
            identity(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != before_id
            or identity(os.fstat(parent_fd)) != parent_id
            or identity(os.lstat(parent)) != parent_id
        ):
            raise RuntimeError("harness input path changed")
    finally:
        os.close(parent_fd)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError("harness input digest differs")
    return raw


def verifier_ast(driver: bytes) -> None:
    text = driver.decode("utf-8")
    bodies = re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", text, re.DOTALL)
    candidates = [body for body in bodies if "generated R3 controller differs" in body]
    if len(candidates) != 1:
        raise RuntimeError("pre-run verifier heredoc cardinality differs")
    tree = ast.parse(candidates[0])
    bare = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "CONTROLLER_SHA256"]
    env = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "os"
        and node.value.attr == "environ"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "CONTROLLER_SHA256"
    ]
    if bare or len(env) != 1:
        raise RuntimeError("controller digest lookup is not environment-bound")


def require_red(call, label: str) -> None:
    try:
        call()
    except (OSError, RuntimeError):
        return
    raise RuntimeError(f"negative was accepted: {label}")


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: harness.py BUILD_PY R4_DRIVER OUTPUT_ROOT")
    build, source, root = map(Path, sys.argv[1:])
    build_raw = owned(build, BUILD_SHA256)
    compile(build_raw, str(build), "exec")
    source_raw = owned(source, SOURCE_SHA256, (SOURCE_DEV, SOURCE_INO))
    namespace = {"__name__": "r5_build"}
    exec(compile(build_raw, str(build), "exec"), namespace)
    info = os.lstat(root)
    if (
        root != Path(os.path.realpath(root))
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
        or any(root.iterdir())
    ):
        raise RuntimeError("harness output root is unsafe")
    output = root / "driver.sh"
    result = subprocess.run(
        [sys.executable, str(build), str(source), str(output)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode or result.stdout.count("R5_DRIVER_GREEN ") != 1:
        raise RuntimeError(f"driver patch failed: {result.stderr}")
    payload = owned(output, OUTPUT_SHA256)
    subprocess.run(["/bin/bash", "-n", str(output)], timeout=10, check=True)
    heredocs = re.findall(r"<<'PY'\n(.*?)\nPY(?:\n|$)", payload.decode(), re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("driver heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r5-heredoc-{number}>", "exec")
    verifier_ast(payload)
    text = payload.decode()
    required = (
        'task-7-followup-3-report.md',
        'docs/superpowers/plans/2026-08-14-official-blender-mcp-r5-verifier-env.md',
        'rev-parse 81752dd10be750964d72cda9036db32e0cd2baf2^',
    )
    if any(text.count(value) != 1 for value in required):
        raise RuntimeError("R5 driver fixed anchor cardinality differs")
    if text.count('"$ATTEMPT_ROOT/r3_controller.py" run \\') != 1:
        raise RuntimeError("controller run cardinality differs")
    source_text = source_raw.decode()
    source_anchors = (
        "hashlib.sha256(controller).hexdigest() != CONTROLLER_SHA256",
        "task-7-followup-2-report.md",
        "docs/superpowers/plans/2026-08-14-official-blender-mcp-r4-file-backed-driver.md",
        '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = "$R3_RUNBOOK_COMMIT"',
    )
    if any(source_text.count(anchor) != 1 for anchor in source_anchors):
        raise RuntimeError("source patch anchor cardinality differs")
    for number, anchor in enumerate(source_anchors, 1):
        mutated = source_text.replace(anchor, f"R5_MUTATED_ANCHOR_{number}", 1).encode()
        require_red(lambda value=mutated: namespace["build"](value), f"source-anchor-{number}")
    reverted = payload.replace(
        b'os.environ["CONTROLLER_SHA256"]', b"CONTROLLER_SHA256", 1
    )
    require_red(lambda: verifier_ast(reverted), "output-verifier-revert")
    swap_parent = root / "swap-parent"
    swap_parent.mkdir(mode=0o700)
    held_parent = root / "swap-parent-held"
    original_open = os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and path == "driver.sh" and flags & os.O_CREAT and dir_fd is not None:
            swapped = True
            os.rename(swap_parent, held_parent)
            os.mkdir(swap_parent, 0o700)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    os.open = swapping_open
    try:
        require_red(
            lambda: namespace["write_owned"](swap_parent / "driver.sh", payload),
            "output-parent-swap",
        )
    finally:
        os.open = original_open
    if not swapped or (swap_parent / "driver.sh").exists() or (held_parent / "driver.sh").exists():
        raise RuntimeError("parent-swap negative created output")
    print(
        "R5_PATCH_HARNESS_GREEN build=1 syntax=1 heredocs=7 verifier=1 "
        "source_mutations_red=4 output_mutation_red=1 parent_swap_red=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
