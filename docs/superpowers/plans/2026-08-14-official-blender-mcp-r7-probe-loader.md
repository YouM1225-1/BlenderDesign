# Official Blender MCP R7 Probe-Loader Follow-up Plan

> **For agentic workers:** execute this Plan task-by-task with fresh implementer and reviewer sessions.

**Goal:** Repair only the R6 pre-ticket probe loader, prove the already-correct R6 controller can pass the official Blender CLI helper path, then perform the still-unconsumed live run.

**Architecture:** Freeze the R6 Task 2 BLOCKED terminal. Reuse the exact R6 controller. Derive one R7 probe from the committed R6 Appendix C by registering its descriptor-bound controller bytes as a real temporary Python module before `exec`, and derive one R7 driver from the exact R6 driver by changing only this Plan path and one Git-parent block. Reuse the still-absent R6 evidence/followup-4 namespaces and all R6/R4 live, Option-C, cleanup, review, and audit semantics.

**Tech Stack:** Bash 3.2+, Python 3.13 via `/Users/yeminjie/.local/bin/uv`, Git, macOS `lsof`/`ps`, Blender 5.2 LTS, official Blender MCP source at commit `4309a39646e644261624bfcd2bca669b343b7621`.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is R6 Plan commit `4765fa7104f6e538af36e67a09e726fb386b3e80`; its parent is R5 Plan commit `507833f86949d90e8fbfbe90f8fcf749322ce19e`, then R4 Plan `81752dd10be750964d72cda9036db32e0cd2baf2`, then runbook `8d05ec975a6ba7317d5e9c23963233b2f2d11832`.
- R6 Plan is `docs/superpowers/plans/2026-08-14-official-blender-mcp-r6-config-env.md`, 785 lines, 42,396 bytes, SHA-256 `e2dfa648dd93677ec4fa407e5b79445a38d6e5cfa0b557d66e800944e41d6e72`.
- R6 Task 2 report is dev/inode `16777232/302287506`, mode `0600`, nlink `1`, 1,896 bytes, SHA-256 `683c9b190cee9f26fe54f9efe784370a52c2dd19a9b5fdb0c8d97ad3cdffe531`, with unique `STATUS: BLOCKED`. Never reopen, append, replace, unlink, or use it as new evidence.
- R6 runtime is dev/inode `16777232/302287507`, mode `0700`, and has exactly three native-0600/nlink-1 leaves: `build.py` dev/inode `16777232/302287508`, 11,130 bytes, SHA `3b5da88fc20a9aaaaad9482015129f50b94cedd46753190ca3a1b93f34b8bc14`; `r3_controller.py` dev/inode `16777232/302287509`, 285,770 bytes, SHA `c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc`; `driver.sh` dev/inode `16777232/302287510`, 32,772 bytes, SHA `26e4c7a514ff7c754f96d1272b2dd5671a3c09e29f6fd6904782dc85393d882e`. Never rerun or modify the R6 builder; never launch the R6 driver.
- R6 Appendix C source body is 244 lines, 9,543 bytes, SHA-256 `4e0dba408d74369807bd37347c2554d1c0b156ff13b935569ef38b3dfe776b8f`. Its sole R6 invocation was consumed and failed before `run_blender_cli`: bare-namespace `exec` left `dataclasses` unable to resolve `sys.modules[cls.__module__]`. It did not start Blender and is never rerun unpatched.
- The old live family, its exact 16-leaf closure, followup-3 report, and prior frozen ticket count remain exactly as R6 defines them. Recheck that closure at every R6-defined boundary; keep it out of new evidence.
- `.superpowers/sdd/modeling-remediation/r6-evidence`, `task-7-followup-4-brief.md`, and `task-7-followup-4-report.md` are all absent and were never allocated. R7 explicitly inherits these unused names. Any pre-existing one is BLOCKED; create no R7 evidence namespace, old-family attempt-0002, or second attempt.
- Config, Blender executable, and official MCP source identities are exactly those frozen by R6. Port 9876 and owned Blender/controller/recorder processes are absent; host-managed Blender MCP stdio servers are out of scope and must not be signalled.
- Before this Plan-only commit, do not start Blender/MCP or create R7 runtime/evidence. After it, do not modify either Plan, runbook, config, official MCP source, tests, audit helper, R6 runtime/report, or old evidence.
- R7 authorizes exactly one corrected pre-ticket probe and exactly one later live PTY launch. A failure consumes the applicable authorization; no R7 retry exists.

## File map

- Create/commit: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r7-probe-loader.md`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r7-live-runtime/{build.py,probe.py,driver.sh}`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r7-task2-report.md`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r7-task2-{spec,quality}-review.md`.
- Reuse only as absent names after Task 2: `.superpowers/sdd/modeling-remediation/r6-evidence/final-retest-r3/attempt-0001` and `task-7-followup-4-{brief,report}.md`.
- Create ignored conditionally exactly as R6: `task-7-followup-4-{failure,success}-{root-checks.json,review-package.json,review.md}`.
- Modify only after certified success: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`.

### Task 1: adversarially certify and commit this Plan

- [ ] Prove every frozen identity, R6 BLOCKED report, exact three-leaf R6 runtime, old 16-leaf closure, absent unused namespaces, clean HEAD, empty port, and empty owned-process inventory.
- [ ] Extract Appendices A and B byte-for-byte and compile both in memory. Extract the R6 Appendix C body byte-for-byte from the committed R6 Plan. Run Appendix B only in a fresh native mode-0700 `/private/tmp` root under the exact Task 2 uv environment. Require its unique GREEN; it may execute the exact controller only in `--loader-only` subprocesses and must not call Blender/MCP. Require all source, loader, and parent-swap negatives RED with no rejected output.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan SHA. Each writes only through a native-0600/nlink-1 report descriptor. Any Critical, Important, or Minor burns the round; repair only this Plan and repeat all three.
- [ ] Commit only this Plan with message `docs: plan registered controller probe module`. Require parent `4765fa7104f6e538af36e67a09e726fb386b3e80`, one changed path, and clean status. Do not start Blender/MCP.

### Task 2: generate the R7 probe/driver and run the sole corrected probe

- [ ] Before allocating anything, recheck the exact old 16-leaf closure and immutable R6 Task 2 BLOCKED report. Root exclusive-creates `r7-task2-report.md` native 0600/nlink-1 and retains its original descriptor. Exclusive-create `r7-live-runtime` mode 0700. Extract Appendix A to `build.py` and R6 Appendix C to a fresh native-0600 temporary source. Generate exact `probe.py` and `driver.sh`; the runtime directory contains exactly these three native-0600/nlink-1 leaves. Recheck the old closure/R6 report immediately after generation. Do not copy or regenerate the controller.
- [ ] Require builder/probe compile, `/bin/bash -n`, seven compilable driver Python heredocs, exactly one controller `run`, no run stdin redirect, exact two-anchor driver delta, and unchanged R6 runtime/controller/config/Blender/source identities. Task 1's SHA-bound harness is the sole standalone `--loader-only` proof; Task 2 does not repeat it. Deleting or altering any patch anchor, occupying/mismatching the temporary module, mutating source bytes, or late-swapping an output parent is RED.
- [ ] Before any live evidence/followup-4 file exists, execute the exact R7 probe once in a fresh native mode-0700 `/private/tmp` mutation root, using the R6 controller and R6's exact uv command/arguments. Require the unique line `R6_BLENDER_CLI_PRETICKET_GREEN resolver=1 cli=1 config_mutations_red=3 ticket_absent=1`, clean process exit, unchanged inputs, absent family/ticket, no pyc, and no remaining Blender/controller/recorder/listener. Failure writes current count zero and unique `STATUS: BLOCKED` to the R7 Task 2 report through its original descriptor and terminates without retry.
- [ ] After all static validation, immediately before the probe, then after it, after review, and at terminal, recheck the exact old 16-leaf closure and the immutable R6 Task 2 BLOCKED report. After probe GREEN, append a nonterminal exact runtime/probe evidence prefix including `actual_run_count: 0` through the retained R7 Task 2 report descriptor and keep it open. Root preallocates native-0600/nlink-1 `r7-task2-spec-review.md` and `r7-task2-quality-review.md`; fresh reviewers may write only through their original bound descriptors and must end with unique full-line `SPEC_REVIEW: APPROVED` or `QUALITY_REVIEW: APPROVED`. A bounded root parser reads each through that original descriptor, requires its exact sole approval marker and no rejection marker, then fsyncs, fstat/hash/path-rechecks, freezes dev/ino/size/SHA, and closes it. Append both frozen review identities to the retained Task 2 report before terminal. Only after both approvals may the Task 2 writer append unique `STATUS: PASS`, fsync/close, and freeze dev/ino/size/SHA. Any build, validation, probe, parser, reviewer, identity, or approval failure instead closes every allocated review descriptor after identity-safe fsync/recheck, appends exact observed facts, `actual_run_count: 0`, and unique `STATUS: BLOCKED` through the retained original Task 2 descriptor, fsyncs/closes, freezes identity, and terminates. PASS and BLOCKED are mutually exclusive; tracked/index status remains clean.

### Task 3: perform the sole fresh live run

- [ ] Before allocating followup-4, descriptor-read the frozen R7 Task 2 report and require exactly one standalone `STATUS: PASS`, no BLOCKED, the bound runtime/probe identities, current count zero, and both Task-2-frozen review identities; bind its dev/ino/size/SHA. Descriptor-read both frozen Task 2 review reports, require their current dev/ino/size/SHA equal the values recorded in the Task 2 PASS report, and require their exact unique approval lines and no rejection. Apply R6 Task 3 exactly, substituting only this Plan/commit/SHA and the exact R7 driver path/SHA. Reuse the exact R6 controller and the still-absent `r6-evidence`/followup-4 names. Bind and freeze the R6 Task 2 BLOCKED report as external history. Carry the R7 Task 2 report/review bindings through prelaunch, failure/success root checks, and final gate, but never include any Task 2/R6 historical report or R6 runtime leaf other than the controller in new evidence/review-package closure.
- [ ] Option C remains unchanged: at `VISUAL_ACK_REQUIRED`, the implementer returns only the live PTY identity and every ordered absolute PNG path/SHA; root displays every image and the user supplies every verdict before one canonical ACK. The failed R5 run produced no visual ACK and contributes nothing.
- [ ] All R6 prelaunch, one-ticket, FD, cleanup, terminal, and old-closure checks remain mandatory. The R7 corrected probe is never rerun in Task 3; the R6 driver is never launched.

### Task 4: independently review a grouped direct failure

- [ ] Apply R6 Task 4 exactly with this Plan/commit/SHA and exact R7 driver binding added to root checks. Fresh evidence inputs remain the R6-named unused namespace only; R6 Task 2/R7 Task 2 reports and other old artifacts remain external and forbidden from the review package.

### Task 5: audit and commit a successful Option-C run

- [ ] Apply R6 Task 5 exactly with this Plan/commit/SHA and exact R7 driver binding. In its Step 3 replace only the first-parent rule with an exact length-six array in runbook/R4-Plan/R5-Plan/R6-Plan/R7-Plan/audit order. The six length-one `paths` arrays map respectively to the runbook, R4 Plan, R5 Plan, R6 Plan, this Plan, and modeling-audit paths; parent values equal old R3 Plan, runbook, R4 Plan, R5 Plan, R6 Plan, and R7 Plan commits respectively.

## Appendix A: exact R7 runtime builder

Extract the following Python body without its Markdown fences. It is exactly 275 lines, 11,795 bytes, SHA-256 `58aa75df1fa968f26fc78114544b9ba0c14ade13cc3f566f740dcf98dc244cec`. It accepts exactly `SOURCE_DRIVER SOURCE_R6_PROBE OUTPUT_DRIVER OUTPUT_PROBE`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


SOURCE_DRIVER_ID = (16777232, 302287510)
SOURCE_DRIVER_SIZE = 32772
SOURCE_DRIVER_SHA256 = "26e4c7a514ff7c754f96d1272b2dd5671a3c09e29f6fd6904782dc85393d882e"
SOURCE_PROBE_SIZE = 9543
SOURCE_PROBE_SHA256 = "4e0dba408d74369807bd37347c2554d1c0b156ff13b935569ef38b3dfe776b8f"
OUTPUT_DRIVER_SIZE = 32904
OUTPUT_DRIVER_SHA256 = "0908a0dfe458f8f9ab0e7f20ae4b07b94ec4227d6f27ecf826412da1391e36a3"
OUTPUT_PROBE_SIZE = 12013
OUTPUT_PROBE_SHA256 = "97c9619804fc741b56d1707ff92ed18fa3c4e685212edd60a6e3f7a4878a4190"
OLD_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r6-config-env.md"
NEW_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r7-probe-loader.md"
OLD_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = '
    "507833f86949d90e8fbfbe90f8fcf749322ce19e\n"
    '  test "$(git -C "$FEATURE_ROOT" rev-parse '
    '507833f86949d90e8fbfbe90f8fcf749322ce19e^)" = '
    "81752dd10be750964d72cda9036db32e0cd2baf2"
)
NEW_TOPOLOGY = (
    '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = '
    "4765fa7104f6e538af36e67a09e726fb386b3e80\n"
    '  test "$(git -C "$FEATURE_ROOT" rev-parse '
    '4765fa7104f6e538af36e67a09e726fb386b3e80^)" = '
    "507833f86949d90e8fbfbe90f8fcf749322ce19e\n"
    '  test "$(git -C "$FEATURE_ROOT" rev-parse '
    '507833f86949d90e8fbfbe90f8fcf749322ce19e^)" = '
    "81752dd10be750964d72cda9036db32e0cd2baf2"
)


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def parent_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
    )


def read_owned(path: Path, size: int, digest: str, dev_ino: tuple[int, int] | None = None) -> bytes:
    info = os.lstat(path)
    identity = file_identity(info)
    if (
        path != Path(os.path.realpath(path))
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size != size
        or (dev_ino is not None and identity[:2] != dev_ino)
    ):
        raise RuntimeError("unsafe R7 builder input")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if file_identity(opened) != identity:
            raise RuntimeError("R7 builder input changed before open")
        chunks = bytearray()
        while len(chunks) < size:
            chunk = os.read(fd, min(65536, size - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
        raw = bytes(chunks)
        if len(raw) != size or os.read(fd, 1) or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError("R7 builder input bytes differ")
        if file_identity(os.fstat(fd)) != identity:
            raise RuntimeError("R7 builder input changed during read")
    finally:
        os.close(fd)
    if file_identity(os.lstat(path)) != identity:
        raise RuntimeError("R7 builder input path changed")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1 or old == new:
        raise RuntimeError("R7 patch anchor is not unique")
    return text.replace(old, new, 1)


def build_driver(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    text = once(text, OLD_PLAN, NEW_PLAN)
    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)
    payload = text.encode("utf-8")
    if len(payload) != OUTPUT_DRIVER_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_DRIVER_SHA256:
        raise RuntimeError("R7 driver identity differs")
    return payload


def build_probe(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    text = once(text, "import hashlib\n", "import dataclasses\nimport hashlib\n")
    text = once(
        text,
        "import sys\n",
        'import sys\nimport types\n\n\nMODULE_NAME = "_r7_controller_probe_c1a35f8f"\n',
    )
    text = once(
        text,
        "def load_controller(path: Path) -> tuple[dict[str, object], tuple[int, ...]]:\n",
        "def cleanup_temporary_module(module: types.ModuleType) -> bool:\n"
        "    current = sys.modules.get(MODULE_NAME)\n"
        "    if current is module:\n"
        "        del sys.modules[MODULE_NAME]\n"
        "        return False\n"
        "    return True\n\n\n"
        "def load_controller(path: Path) -> tuple[dict[str, object], tuple[int, ...]]:\n",
    )
    text = once(
        text,
        '    namespace: dict[str, object] = {"__name__": "r6_controller_probe", "__file__": str(path)}\n'
        '    exec(compile(raw, str(path), "exec"), namespace)\n'
        "    return namespace, identity\n",
        "    if MODULE_NAME in sys.modules:\n"
        '        raise RuntimeError("temporary controller module name is occupied")\n'
        "    module = types.ModuleType(MODULE_NAME)\n"
        "    module.__file__ = str(path)\n"
        "    sys.modules[MODULE_NAME] = module\n"
        "    try:\n"
        '        exec(compile(raw, str(path), "exec"), module.__dict__)\n'
        "        namespace = module.__dict__\n"
        "    finally:\n"
        "        registration_changed = cleanup_temporary_module(module)\n"
        "    if registration_changed:\n"
        '        raise RuntimeError("temporary controller module registration changed")\n'
        "    return namespace, identity\n",
    )
    text = once(
        text,
        "def main() -> int:\n"
        "    if len(sys.argv) != 7:\n"
        '        raise SystemExit("usage: probe.py R6_CONTROLLER CONFIG BLENDER MCP_SOURCE FRESH_FAMILY MUTATION_ROOT")\n',
        "def main() -> int:\n"
        '    if len(sys.argv) == 3 and sys.argv[1] == "--loader-only":\n'
        "        namespace, _ = load_controller(Path(sys.argv[2]))\n"
        "        if MODULE_NAME in sys.modules:\n"
        '            raise RuntimeError("temporary controller module cleanup failed")\n'
        '        names = ("Context", "ProductionSpec", "ProductionSnapshot")\n'
        "        if any(not dataclasses.is_dataclass(namespace.get(name)) for name in names):\n"
        '            raise RuntimeError("controller dataclass loader proof differs")\n'
        "        sentinel = types.ModuleType(MODULE_NAME)\n"
        "        sys.modules[MODULE_NAME] = sentinel\n"
        "        try:\n"
        "            try:\n"
        "                load_controller(Path(sys.argv[2]))\n"
        "            except RuntimeError as exc:\n"
        '                if str(exc) != "temporary controller module name is occupied":\n'
        "                    raise\n"
        "            else:\n"
        '                raise RuntimeError("occupied temporary module name was accepted")\n'
        "            if sys.modules.get(MODULE_NAME) is not sentinel:\n"
        '                raise RuntimeError("occupied temporary module was changed")\n'
        "        finally:\n"
        "            if sys.modules.pop(MODULE_NAME, None) is not sentinel:\n"
        '                raise RuntimeError("occupied temporary module cleanup differed")\n'
        "        owned = types.ModuleType(MODULE_NAME)\n"
        '        foreign = types.ModuleType(MODULE_NAME + "_foreign")\n'
        "        sys.modules[MODULE_NAME] = foreign\n"
        "        try:\n"
        "            if not cleanup_temporary_module(owned) or sys.modules.get(MODULE_NAME) is not foreign:\n"
        '                raise RuntimeError("foreign temporary module was not preserved")\n'
        "        finally:\n"
        "            if sys.modules.pop(MODULE_NAME, None) is not foreign:\n"
        '                raise RuntimeError("foreign temporary module cleanup differed")\n'
        '        print("R7_REGISTERED_LOADER_GREEN dataclasses=3 cleanup=1 occupied_red=1 foreign_preserved=1")\n'
        "        return 0\n"
        "    if len(sys.argv) != 7:\n"
        '        raise SystemExit("usage: probe.py R6_CONTROLLER CONFIG BLENDER MCP_SOURCE FRESH_FAMILY MUTATION_ROOT")\n',
    )
    payload = text.encode("utf-8")
    if len(payload) != OUTPUT_PROBE_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_PROBE_SHA256:
        raise RuntimeError("R7 probe identity differs")
    return payload


def write_owned(path: Path, payload: bytes) -> tuple[int, int]:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("R7 output path is not canonical")
    parent = path.parent
    before = os.lstat(parent)
    expected_parent = parent_identity(before)
    if (
        not stat.S_ISDIR(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_uid != os.getuid()
        or stat.S_IMODE(before.st_mode) != 0o700
    ):
        raise RuntimeError("R7 output parent is unsafe")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    created: tuple[int, int] | None = None
    success = False
    try:
        if parent_identity(os.fstat(parent_fd)) != expected_parent:
            raise RuntimeError("R7 output parent changed before create")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        try:
            opened = os.fstat(fd)
            created = (opened.st_dev, opened.st_ino)
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise RuntimeError("short R7 output write")
                view = view[count:]
            os.fsync(fd)
            final = os.fstat(fd)
            if (
                (final.st_dev, final.st_ino) != created
                or final.st_uid != os.getuid()
                or stat.S_IMODE(final.st_mode) != 0o600
                or final.st_nlink != 1
                or final.st_size != len(payload)
            ):
                raise RuntimeError("R7 output identity differs")
        finally:
            os.close(fd)
        leaf = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (leaf.st_dev, leaf.st_ino) != created:
            raise RuntimeError("R7 output path changed")
        os.fsync(parent_fd)
        current_parent = os.lstat(parent)
        if parent_identity(current_parent) != expected_parent:
            raise RuntimeError("R7 output parent changed after create")
        success = True
        return created
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
    if len(sys.argv) != 5:
        raise SystemExit("usage: build.py SOURCE_DRIVER SOURCE_R6_PROBE OUTPUT_DRIVER OUTPUT_PROBE")
    source_driver, source_probe, output_driver, output_probe = map(Path, sys.argv[1:])
    driver = build_driver(read_owned(source_driver, SOURCE_DRIVER_SIZE, SOURCE_DRIVER_SHA256, SOURCE_DRIVER_ID))
    probe = build_probe(read_owned(source_probe, SOURCE_PROBE_SIZE, SOURCE_PROBE_SHA256))
    write_owned(output_driver, driver)
    write_owned(output_probe, probe)
    print(f"R7_RUNTIME_GREEN driver_sha256={OUTPUT_DRIVER_SHA256} probe_sha256={OUTPUT_PROBE_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable R7 harness

Extract the following Python body without its Markdown fences. It is exactly 220 lines, 9,114 bytes, SHA-256 `717d76f3e13fb4462e6c3c3113ca44c13b5578dcce3d6922f59aaaffca9df991`. Run `harness.py BUILD_PY SOURCE_DRIVER SOURCE_R6_PROBE OUTPUT_ROOT CONTROLLER` under R6's exact uv environment with canonical absolute paths and an empty native mode-0700 output root.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


BUILD_SHA256 = "58aa75df1fa968f26fc78114544b9ba0c14ade13cc3f566f740dcf98dc244cec"
SOURCE_DRIVER_SHA256 = "26e4c7a514ff7c754f96d1272b2dd5671a3c09e29f6fd6904782dc85393d882e"
SOURCE_PROBE_SHA256 = "4e0dba408d74369807bd37347c2554d1c0b156ff13b935569ef38b3dfe776b8f"
OUTPUT_DRIVER_SHA256 = "0908a0dfe458f8f9ab0e7f20ae4b07b94ec4227d6f27ecf826412da1391e36a3"
OUTPUT_PROBE_SHA256 = "97c9619804fc741b56d1707ff92ed18fa3c4e685212edd60a6e3f7a4878a4190"


def owned(path: Path, digest: str, limit: int = 1024 * 1024) -> bytes:
    info = os.lstat(path)
    if (
        path != Path(os.path.realpath(path))
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size > limit
    ):
        raise RuntimeError("unsafe R7 harness input")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("R7 harness input digest differs")
    return raw


def write_case(path: Path, payload: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise RuntimeError("short R7 harness write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def loader(path: Path, controller: Path, green: bool) -> None:
    result = subprocess.run(
        [sys.executable, str(path), "--loader-only", str(controller)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    count = result.stdout.count(
        "R7_REGISTERED_LOADER_GREEN dataclasses=3 cleanup=1 occupied_red=1 foreign_preserved=1"
    )
    if green and (result.returncode or count != 1):
        raise RuntimeError(f"registered loader positive failed: {result.stderr}")
    if not green and (result.returncode == 0 or count):
        raise RuntimeError("registered loader negative was accepted")


def require_red(call, label: str) -> None:
    try:
        call()
    except (OSError, RuntimeError, SyntaxError):
        return
    raise RuntimeError(f"R7 negative was accepted: {label}")


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit("usage: harness.py BUILD_PY SOURCE_DRIVER SOURCE_R6_PROBE OUTPUT_ROOT CONTROLLER")
    build, source_driver, source_probe, root, controller = map(Path, sys.argv[1:])
    build_raw = owned(build, BUILD_SHA256)
    driver_raw = owned(source_driver, SOURCE_DRIVER_SHA256)
    probe_raw = owned(source_probe, SOURCE_PROBE_SHA256)
    compile(build_raw, str(build), "exec")
    compile(probe_raw, str(source_probe), "exec")
    info = os.lstat(root)
    if (
        root != Path(os.path.realpath(root))
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
        or any(root.iterdir())
    ):
        raise RuntimeError("unsafe R7 harness output root")
    namespace: dict[str, object] = {"__name__": "r7_build_harness"}
    exec(compile(build_raw, str(build), "exec"), namespace)
    expected_driver = namespace["build_driver"](driver_raw)
    expected_probe = namespace["build_probe"](probe_raw)
    output_driver = root / "driver.sh"
    output_probe = root / "probe.py"
    result = subprocess.run(
        [sys.executable, str(build), str(source_driver), str(source_probe), str(output_driver), str(output_probe)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode or result.stdout.count("R7_RUNTIME_GREEN ") != 1:
        raise RuntimeError(f"R7 build failed: {result.stderr}")
    if owned(output_driver, OUTPUT_DRIVER_SHA256) != expected_driver:
        raise RuntimeError("R7 driver output differs")
    if owned(output_probe, OUTPUT_PROBE_SHA256) != expected_probe:
        raise RuntimeError("R7 probe output differs")
    compile(expected_probe, "<r7-probe>", "exec")
    subprocess.run(["/bin/bash", "-n", str(output_driver)], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", expected_driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("R7 driver heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r7-heredoc-{number}>", "exec")
    if expected_driver.count(b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n') != 1:
        raise RuntimeError("R7 controller run cardinality differs")
    loader(output_probe, controller, True)
    missing_registration = expected_probe.replace(b"    sys.modules[MODULE_NAME] = module\n", b"", 1)
    mismatched_name = expected_probe.replace(
        b"    module = types.ModuleType(MODULE_NAME)\n",
        b'    module = types.ModuleType(MODULE_NAME + "_wrong")\n',
        1,
    )
    missing_cleanup = expected_probe.replace(
        b"        registration_changed = cleanup_temporary_module(module)\n",
        b"        registration_changed = False\n",
        1,
    )
    foreign_delete = expected_probe.replace(
        b"    return True\n\n\ndef load_controller",
        b"    sys.modules.pop(MODULE_NAME, None)\n    return True\n\n\ndef load_controller",
        1,
    )
    if (
        missing_registration == expected_probe
        or mismatched_name == expected_probe
        or missing_cleanup == expected_probe
        or foreign_delete == expected_probe
    ):
        raise RuntimeError("R7 loader mutation did not change bytes")
    for name, payload in (
        ("missing-registration.py", missing_registration),
        ("mismatched-name.py", mismatched_name),
        ("missing-cleanup.py", missing_cleanup),
        ("foreign-delete.py", foreign_delete),
    ):
        path = root / name
        write_case(path, payload)
        loader(path, controller, False)
    builder_text = build_raw.decode("utf-8")
    mutations = (
        builder_text.replace("    text = once(text, OLD_PLAN, NEW_PLAN)\n", "    text = text\n", 1),
        builder_text.replace("    text = once(text, OLD_TOPOLOGY, NEW_TOPOLOGY)\n", "    text = text\n", 1),
        builder_text.replace('    text = once(text, "import hashlib\\n", "import dataclasses\\nimport hashlib\\n")\n', "    text = text\n", 1),
        builder_text.replace(
            'MODULE_NAME = "_r7_controller_probe_c1a35f8f"',
            'MODULE_NAME_X = "_r7_controller_probe_c1a35f8f"',
            1,
        ),
        builder_text.replace(
            '        "    if MODULE_NAME in sys.modules:\\n"\n',
            '        "    if MODULE_NAME_X in sys.modules:\\n"\n',
            1,
        ),
        builder_text.replace(
            '        "def cleanup_temporary_module(module: types.ModuleType) -> bool:\\n"\n',
            '        "def cleanup_temporary_module_X(module: types.ModuleType) -> bool:\\n"\n',
            1,
        ),
        builder_text.replace(
            '        "def main() -> int:\\n"\n        \'    if len(sys.argv) == 3',
            '        "def main_X() -> int:\\n"\n        \'    if len(sys.argv) == 3',
            1,
        ),
    )
    for number, mutated in enumerate(mutations, 1):
        if mutated == builder_text:
            raise RuntimeError(f"R7 builder mutation {number} did not change bytes")
        mutated_namespace: dict[str, object] = {"__name__": f"r7_builder_mutation_{number}"}
        exec(compile(mutated.encode(), f"<r7-builder-mutation-{number}>", "exec"), mutated_namespace)
        if number <= 2:
            require_red(lambda ns=mutated_namespace: ns["build_driver"](driver_raw), f"driver-source-{number}")
        else:
            require_red(lambda ns=mutated_namespace: ns["build_probe"](probe_raw), f"probe-source-{number}")
    swap_parent = root / "swap-parent"
    swap_parent.mkdir(mode=0o700)
    held_parent = root / "swap-parent-held"
    original_open = os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and path == "probe.py" and flags & os.O_CREAT and dir_fd is not None:
            swapped = True
            os.rename(swap_parent, held_parent)
            os.mkdir(swap_parent, 0o700)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    os.open = swapping_open
    try:
        require_red(lambda: namespace["write_owned"](swap_parent / "probe.py", expected_probe), "late-parent-swap")
    finally:
        os.open = original_open
    if not swapped or (swap_parent / "probe.py").exists() or (held_parent / "probe.py").exists():
        raise RuntimeError("R7 parent swap left rejected output")
    print(
        "R7_PLAN_HARNESS_GREEN driver=1 loader=1 source_mutations_red=7 "
        "loader_mutations_red=4 parent_swap_red=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
