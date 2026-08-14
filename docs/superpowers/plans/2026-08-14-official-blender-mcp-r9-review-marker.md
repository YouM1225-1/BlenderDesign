# Official Blender MCP R9 Exact-Review-Marker Follow-up Plan

> **For agentic workers:** execute this Plan task-by-task with fresh Plan reviewers and one-shot terminals.

**Goal:** Replace the overbroad review substring check with an exact full-line marker parser, derive the required R9 Git-bound driver, and reach the still-unconsumed live run without replaying any probe.

**Architecture:** Freeze the correct R8 runtime and its two genuinely approved reviews alongside the immutable R8 aggregate `BLOCKED` false-positive. Add no probe or controller. Use one exact disposable stdlib tool to parse the frozen review markers and derive one driver from the exact R8 driver by changing only this Plan path and one Git-parent block. Task 2 creates only that driver and one aggregate report.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is R8 Plan commit `436c3c2b92fe45030b73439b9c67278c92090a7c`; its parent is R7 `8be47eab75689b584dfb978e5c8e304fcca8927c`. R8 Plan is 385 lines / 23,725 bytes / SHA-256 `99c3f91265f9fb480510a093e4c388854b21ad126142fb8dbb54b979890a83f1`.
- R8 Task 2 report is permanently `BLOCKED`: dev/inode `16777232/303328521`, mode `0600`, nlink `1`, 2,927 bytes, SHA-256 `05dc1df498ccac74f8753e34b2bd1251cc738f3513b4ff6a155e20393fb4eb8c`. It records the historical parser false-positive and may never be reopened, changed, replaced, deleted, or called PASS.
- R8 spec review is dev/inode `16777232/303328522`, 2,584 bytes, SHA-256 `59a05c7b28889ae2c35045a3571e574d41769d387c5bf4f5785746293b5a9584`, with one final full line `SPEC_REVIEW: APPROVED`. R8 quality review is dev/inode `16777232/303328523`, 1,990 bytes, SHA-256 `511768f1c6ee2a7db2fa34984872ab27722e02bf33710902dd84e3dd0db3b960`, with one final full line `QUALITY_REVIEW: APPROVED`. Both are immutable.
- R8 runtime parent is dev/inode `16777232/303328524`, mode `0700`, with exactly `build.py` inode `303328525` SHA `2d86be69ef940ca53b83cf0fe590cd57bffa902bdb0e9b2b2ca2c87049f00299`, `driver.sh` inode `303328526` size 33,034 SHA `d1e808d55cc320ae607809639f33e973184d50023d2809fe237fc64810595211`, and `probe.py` inode `303328527` SHA `1a2e050ab80aa1bf76e92c8ca8a9a0784136379807db4f3532d04b0101bedafe`, all native-0600/nlink-1. Never modify, copy, or execute them; only the exact driver is a read-only derivation source.
- Reuse the exact R6 controller and all R7/R6/older frozen state as R8 binds them. `.superpowers/sdd/modeling-remediation/r6-evidence`, followup-4 brief/report, old-family attempt-0002, and every R9 runtime/report are absent. Port 9876 and owned Blender/controller/recorder processes are absent.
- The sole corrected CLI probe has already run once. R9 runs zero probes, loader-only probes, CLI helpers, Blender/MCP, GUI, controller, or driver before Task 3. No R9 probe/controller, new evidence namespace, followup-5, attempt-0002, retry, wrapper, config/source/test change, or R8 mutation is permitted.

## File map

- Create/commit: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r9-review-marker.md`.
- Create ignored/bound after the Plan commit: `.superpowers/sdd/modeling-remediation/r9-live-runtime/driver.sh` and `.superpowers/sdd/modeling-remediation/r9-task2-report.md`.
- Reuse only as still-absent names after Task 2: `.superpowers/sdd/modeling-remediation/r6-evidence/final-retest-r3/attempt-0001` and `task-7-followup-4-{brief,report}.md`.
- Create conditional followup-4 review artifacts exactly as R8/R7 defines. Modify the audit file only after certified success.

### Task 1: certify and commit this Plan

- [ ] Recheck every frozen artifact, clean HEAD, absent namespaces/ticket/R9 targets, empty port, and empty owned-process inventory.
- [ ] Extract Appendices A and B exactly and compile them in memory. Run Appendix B once in a fresh native mode-0700 `/private/tmp` root. Require its unique GREEN for both exact R8 approvals, the explanatory `E402-REJECTED` regression, exact reject/invalid cases, exact two-anchor driver, Bash/heredoc/run shape, and allocation-parent replacement RED. It may not execute any probe, driver, Blender, or MCP.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan SHA. Any Critical, Important, or Minor burns the round.
- [ ] Commit only this Plan with message `docs: plan exact review markers`. Require parent `436c3c2b92fe45030b73439b9c67278c92090a7c`, one changed path, and clean status.

### Task 2: aggregate the frozen approvals and generate the R9 driver

- [ ] Before allocation, descriptor-bind the final three 0/0/0 Plan-review reports, every frozen R8/R7/R6 artifact, and all absence/process/port/Git gates. Root exclusive-creates and retains the original native-0600/nlink-1 `r9-task2-report.md` descriptor, then exclusive-creates native-mode-0700 `r9-live-runtime`, records its dev/inode/uid/mode, and retains its original directory descriptor until terminalization.
- [ ] Extract Appendix A into a private native-mode-0700 `/private/tmp` root and verify its declared identity. Invoke those exact bytes once with the recorded runtime dev/inode: the same process descriptor-binds both immutable R8 reviews, requires both `APPROVED`, then exclusive-creates the sole native-0600/nlink-1 R9 driver under that exact parent. Require the retained parent descriptor and path identity to remain equal, then descriptor-bind the driver and require exact output SHA, raw two-anchor reversal, `/bin/bash -n`, seven Python heredocs, exactly one controller `run`, and no run stdin redirect. The runtime contains only `driver.sh`. Do not execute any probe, loader-only, CLI helper, driver, Blender/MCP, GUI, controller, or ticket path.
- [ ] Through the original report descriptor, write the frozen Plan reviews, R8 BLOCKED false-positive, both real R8 approvals, parser/tool evidence, recorded runtime parent identity, descriptor-bound driver identity, `inherited_r7_corrected_probe_run_count: 1`, `r8_cli_probe_run_count: 0`, `r8_loader_only_probe_run_count: 0`, `r9_cli_probe_run_count: 0`, `r9_loader_only_probe_run_count: 0`, and `actual_run_count: 0`. Recheck every frozen artifact, exact R8 review marker, retained runtime descriptor/path, driver, absent namespace/ticket, clean Git, and empty port/process inventory immediately before terminalization. On success append unique `STATUS: PASS`; on any failure append exact observed facts and unique `STATUS: BLOCKED`. In either case fsync/fstat/path-recheck/close the report and runtime directory descriptors and freeze their identities. Never reopen, replace, or retry Task 2.

### Task 3: perform the sole fresh live run

- [ ] Before allocating followup-4, descriptor-bind the R9 Task 2 PASS report, final three Plan reviews, exact parser/driver/count facts, both original R8 approvals, the immutable R8/R7 BLOCKED histories, and all inherited frozen state. Require the current canonical `r9-live-runtime` directory dev/inode/uid/mode to equal the Task 2 PASS record and the exact driver to remain its sole leaf; carry and recheck that parent-plus-driver binding at prelaunch, every failure/success root check, and the final gate.
- [ ] Supersede only R8 Task 3's predecessor-Task2 admission: require the R9 PASS above and the real R8/R7 BLOCKED reports as external history. Apply every remaining R8 Task 3 transition exactly with this Plan/commit/SHA and the exact R9 driver. Reuse the exact R6 controller and still-absent R6 evidence/followup-4 names. Never execute any probe or an older driver. Preserve one GUI/listener, live PTY, ticket, cleanup, FD, and old-closure rule.
- [ ] Option C is unchanged: at `VISUAL_ACK_REQUIRED`, return only the live PTY identity and every ordered absolute PNG path/SHA; root displays every image and the user supplies every verdict before one canonical ACK.

### Task 4: independently review a grouped direct failure

- [ ] Apply R8 Task 4 with this Plan/driver and R9 Task 2 binding. All Task 2 and historical artifacts remain external and forbidden from the fresh review package.

### Task 5: audit and commit a successful Option-C run

- [ ] Apply R8 Task 5 with this Plan/driver and R9 Task 2 binding. Replace only its first-parent rule with exact length eight in runbook/R4/R5/R6/R7/R8/R9/audit order. Eight length-one `paths` arrays map to those files; parents are old-R3/runbook/R4/R5/R6/R7/R8/R9 respectively.

## Appendix A: exact disposable R9 tool

Extract the following Python body without fences. Exact identity: 168 lines / 7,795 bytes / SHA-256 `225ca519b0acd0cb81ca1e8dd9d3f5decff85f43c8780e485e9617d4f4081d85`. Invoke it once as `tool.py SOURCE_R8_DRIVER SPEC_REVIEW QUALITY_REVIEW OUTPUT_R9_DRIVER EXPECTED_PARENT_DEV EXPECTED_PARENT_INO`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_ID = (16777232, 303328526)
SOURCE_SIZE = 33034
SOURCE_SHA256 = "d1e808d55cc320ae607809639f33e973184d50023d2809fe237fc64810595211"
OUTPUT_SIZE = 33165
OUTPUT_SHA256 = "2229d62d58e412d7a0c44c95ca1dad1eeab1765191a2f55d2e3f5833a70fa64d"
SPEC_ID = (16777232, 303328522)
SPEC_SIZE = 2584
SPEC_SHA256 = "59a05c7b28889ae2c35045a3571e574d41769d387c5bf4f5785746293b5a9584"
QUALITY_ID = (16777232, 303328523)
QUALITY_SIZE = 1990
QUALITY_SHA256 = "511768f1c6ee2a7db2fa34984872ab27722e02bf33710902dd84e3dd0db3b960"
OLD_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r8-import-order.md"
NEW_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r9-review-marker.md"
OLD_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 8be47eab75689b584dfb978e5c8e304fcca8927c\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 8be47eab75689b584dfb978e5c8e304fcca8927c^)" = 4765fa7104f6e538af36e67a09e726fb386b3e80\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 4765fa7104f6e538af36e67a09e726fb386b3e80^)" = 507833f86949d90e8fbfbe90f8fcf749322ce19e'
)
NEW_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = 436c3c2b92fe45030b73439b9c67278c92090a7c\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 436c3c2b92fe45030b73439b9c67278c92090a7c^)" = 8be47eab75689b584dfb978e5c8e304fcca8927c\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 8be47eab75689b584dfb978e5c8e304fcca8927c^)" = 4765fa7104f6e538af36e67a09e726fb386b3e80\n'
    '  test "$(git -C "$FEATURE_ROOT" rev-parse 4765fa7104f6e538af36e67a09e726fb386b3e80^)" = 507833f86949d90e8fbfbe90f8fcf749322ce19e'
)


def identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode), info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def parent_identity(info: os.stat_result) -> tuple[int, ...]:
    return info.st_dev, info.st_ino, info.st_uid, stat.S_IMODE(info.st_mode)


def read_owned(path: Path, size: int, digest: str, dev_ino: tuple[int, int]) -> bytes:
    before = os.lstat(path)
    expected = identity(before)
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size != size or expected[:2] != dev_ino:
        raise RuntimeError("unsafe R9 input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if identity(os.fstat(fd)) != expected:
            raise RuntimeError("R9 input changed before open")
        raw = bytearray()
        while len(raw) < size:
            chunk = os.read(fd, min(65536, size - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        payload = bytes(raw)
        if len(payload) != size or os.read(fd, 1) or hashlib.sha256(payload).hexdigest() != digest or identity(os.fstat(fd)) != expected:
            raise RuntimeError("R9 input bytes changed")
    finally:
        os.close(fd)
    if identity(os.lstat(path)) != expected:
        raise RuntimeError("R9 input path changed")
    return payload


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1 or old == new:
        raise RuntimeError("R9 anchor is not unique")
    return text.replace(old, new, 1)


def build_driver(raw: bytes) -> bytes:
    text = once(raw.decode(), OLD_PLAN, NEW_PLAN)
    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)
    payload = text.encode()
    if len(payload) != OUTPUT_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_SHA256:
        raise RuntimeError("R9 driver identity differs")
    return payload


def parse_review(payload: bytes, lens: str) -> str:
    if not payload or len(payload) > 1024 * 1024 or b"\x00" in payload or b"\r" in payload or not payload.endswith(b"\n") or payload.endswith(b"\n\n"):
        return "INVALID"
    try:
        lines = payload[:-1].decode("utf-8").split("\n")
    except UnicodeDecodeError:
        return "INVALID"
    if lens not in {"spec", "quality"}:
        return "INVALID"
    prefix = lens.upper() + "_REVIEW: "
    approved = prefix + "APPROVED"
    rejected = prefix + "REJECTED"
    terminals = [line for line in lines if line.startswith(("SPEC_REVIEW: ", "QUALITY_REVIEW: "))]
    if terminals == [approved] and lines[-1] == approved:
        return "APPROVED"
    if terminals == [rejected] and lines[-1] == rejected:
        return "REJECTED"
    return "INVALID"


def write_owned(path: Path, payload: bytes, expected_dev_ino: tuple[int, int]) -> None:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("R9 output path is not canonical")
    parent = path.parent
    before = os.lstat(parent)
    expected = parent_identity(before)
    if expected[:2] != expected_dev_ino or not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o700:
        raise RuntimeError("unsafe R9 output parent")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created: tuple[int, int] | None = None
    success = False
    try:
        if parent_identity(os.fstat(parent_fd)) != expected:
            raise RuntimeError("R9 output parent changed")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            created = opened.st_dev, opened.st_ino
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise RuntimeError("short R9 write")
                view = view[count:]
            os.fsync(fd)
            final = os.fstat(fd)
            if (final.st_dev, final.st_ino) != created or final.st_uid != os.getuid() or stat.S_IMODE(final.st_mode) != 0o600 or final.st_nlink != 1 or final.st_size != len(payload):
                raise RuntimeError("R9 output identity differs")
        finally:
            os.close(fd)
        leaf = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (leaf.st_dev, leaf.st_ino) != created:
            raise RuntimeError("R9 output path changed")
        os.fsync(parent_fd)
        if parent_identity(os.lstat(parent)) != expected:
            raise RuntimeError("R9 output parent changed after create")
        success = True
    finally:
        if not success and created is not None:
            try:
                leaf = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
                if (leaf.st_dev, leaf.st_ino) == created:
                    os.unlink(path.name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit("usage: tool.py SOURCE SPEC QUALITY OUTPUT PARENT_DEV PARENT_INO")
    source, spec, quality, output = map(Path, sys.argv[1:5])
    expected_parent = int(sys.argv[5]), int(sys.argv[6])
    spec_verdict = parse_review(read_owned(spec, SPEC_SIZE, SPEC_SHA256, SPEC_ID), "spec")
    quality_verdict = parse_review(read_owned(quality, QUALITY_SIZE, QUALITY_SHA256, QUALITY_ID), "quality")
    if (spec_verdict, quality_verdict) != ("APPROVED", "APPROVED"):
        raise RuntimeError("R9 frozen review approval differs")
    driver = build_driver(read_owned(source, SOURCE_SIZE, SOURCE_SHA256, SOURCE_ID))
    write_owned(output, driver, expected_parent)
    print(f"R9_TOOL_GREEN approvals=2 sha256={OUTPUT_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable R9 harness

Extract the following Python body without fences. Exact identity: 103 lines / 5,525 bytes / SHA-256 `06056f4efc0938aa295fb0c9471396f89aa5717532f581f1b39512fa4d9aa071`. Run `harness.py TOOL_PY SOURCE_R8_DRIVER SPEC_REVIEW QUALITY_REVIEW OUTPUT_ROOT` with canonical absolute paths and an empty native mode-0700 output root.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


TOOL_SHA256 = "225ca519b0acd0cb81ca1e8dd9d3f5decff85f43c8780e485e9617d4f4081d85"
SOURCE_SHA256 = "d1e808d55cc320ae607809639f33e973184d50023d2809fe237fc64810595211"
SPEC_SHA256 = "59a05c7b28889ae2c35045a3571e574d41769d387c5bf4f5785746293b5a9584"
QUALITY_SHA256 = "511768f1c6ee2a7db2fa34984872ab27722e02bf33710902dd84e3dd0db3b960"
OUTPUT_SHA256 = "2229d62d58e412d7a0c44c95ca1dad1eeab1765191a2f55d2e3f5833a70fa64d"


def owned(path: Path, digest: str) -> bytes:
    before = os.lstat(path)
    expected = before.st_dev, before.st_ino, before.st_uid, stat.S_IMODE(before.st_mode), before.st_nlink, before.st_size, before.st_mtime_ns, before.st_ctime_ns
    if path != Path(os.path.realpath(path)) or not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1 or before.st_size > 1024 * 1024:
        raise RuntimeError("unsafe R9 harness input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        current = opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode), opened.st_nlink, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns
        if current != expected:
            raise RuntimeError("R9 harness input changed")
        raw = os.read(fd, before.st_size + 1)
        if len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("R9 harness digest differs")
    finally:
        os.close(fd)
    after = os.lstat(path)
    current = after.st_dev, after.st_ino, after.st_uid, stat.S_IMODE(after.st_mode), after.st_nlink, after.st_size, after.st_mtime_ns, after.st_ctime_ns
    if current != expected:
        raise RuntimeError("R9 harness path changed")
    return raw


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit("usage: harness.py TOOL_PY SOURCE_DRIVER SPEC QUALITY OUTPUT_ROOT")
    tool, source, spec, quality, root = map(Path, sys.argv[1:])
    tool_raw = owned(tool, TOOL_SHA256)
    source_raw = owned(source, SOURCE_SHA256)
    spec_raw = owned(spec, SPEC_SHA256)
    quality_raw = owned(quality, QUALITY_SHA256)
    compile(tool_raw, str(tool), "exec")
    namespace: dict[str, object] = {"__name__": "r9_tool_harness"}
    exec(compile(tool_raw, str(tool), "exec"), namespace)
    parse = namespace["parse_review"]
    if parse(spec_raw, "spec") != "APPROVED" or parse(quality_raw, "quality") != "APPROVED":
        raise RuntimeError("exact R8 approval was rejected")
    fixtures = (
        (b"prose E402-REJECTED quality review\nSPEC_REVIEW: APPROVED\n", "spec", "APPROVED"),
        (b"SPEC_REVIEW: REJECTED\n", "spec", "REJECTED"),
        (b"SPEC_REVIEW: APPROVED\nSPEC_REVIEW: APPROVED\n", "spec", "INVALID"),
        (b"SPEC_REVIEW: APPROVED\nSPEC_REVIEW: REJECTED\n", "spec", "INVALID"),
        (b"SPEC_REVIEW: APPROVED\ntrailing\n", "spec", "INVALID"),
        (b"`SPEC_REVIEW: APPROVED`\n", "spec", "INVALID"),
        (b"", "spec", "INVALID"),
        (b"SPEC_REVIEW: APPROVED\r\n", "spec", "INVALID"),
        (b"SPEC_REVIEW: APPROVED\x00\n", "spec", "INVALID"),
    )
    for payload, lens, expected in fixtures:
        if parse(payload, lens) != expected:
            raise RuntimeError("R9 parser fixture differs")
    info = os.lstat(root)
    if root != Path(os.path.realpath(root)) or not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700 or any(root.iterdir()):
        raise RuntimeError("unsafe R9 harness root")
    output = root / "driver.sh"
    result = subprocess.run([sys.executable, str(tool), str(source), str(spec), str(quality), str(output), str(info.st_dev), str(info.st_ino)], text=True, capture_output=True, timeout=20, check=False)
    if result.returncode or result.stdout.count("R9_TOOL_GREEN approvals=2 ") != 1:
        raise RuntimeError(f"R9 driver build failed: {result.stderr}")
    built = owned(output, OUTPUT_SHA256)
    if built != namespace["build_driver"](source_raw):
        raise RuntimeError("R9 driver bytes differ")
    subprocess.run(["/bin/bash", "-n", str(output)], timeout=10, check=True)
    driver = built
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("R9 heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r9-heredoc-{number}>", "exec")
    if driver.count(b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n') != 1:
        raise RuntimeError("R9 controller run count differs")
    swap = root / "swap"
    swap.mkdir(mode=0o700)
    allocated = os.lstat(swap)
    held = root / "held"
    os.rename(swap, held)
    os.mkdir(swap, 0o700)
    rejected = subprocess.run([sys.executable, str(tool), str(source), str(spec), str(quality), str(swap / "driver.sh"), str(allocated.st_dev), str(allocated.st_ino)], text=True, capture_output=True, timeout=20, check=False)
    if rejected.returncode == 0 or "R9_TOOL_GREEN" in rejected.stdout or (swap / "driver.sh").exists() or (held / "driver.sh").exists():
        raise RuntimeError("R9 allocation-parent replacement was accepted")
    print("R9_PLAN_HARNESS_GREEN reviews=2 prose_regression=1 parser_cases=9 driver=1 allocation_parent_red=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
