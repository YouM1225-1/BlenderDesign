# Official Blender MCP R6 Config-Environment Implementation Plan

> **For agentic workers:** execute this Plan task-by-task with fresh implementer and reviewer sessions.

**Goal:** Complete one fresh Blender/MCP validation run after fixing the controller's loss of the already-correct configured `BLENDER_PATH`.

**Architecture:** Freeze the entire R5 terminal. Derive one R6 controller from the frozen R3 controller by strictly validating the sole configured Blender environment key and injecting only that key into the MCP child. Derive one R6 file driver from the frozen R5 driver by rebinding the new controller, fresh evidence namespace, followup-4 report, this Plan, and one additional Git parent. Reuse the certified protocol, Option-C acknowledgement, cleanup, review, and audit semantics unchanged.

**Tech Stack:** Bash 3.2+, Python 3.13 via `/Users/yeminjie/.local/bin/uv`, Git, macOS `lsof`/`ps`, Blender 5.2 LTS, official Blender MCP source at commit `4309a39646e644261624bfcd2bca669b343b7621`.

## Frozen state and red lines

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on `codex/official-blender-mcp-install`.
- Clean base HEAD is R5 Plan commit `507833f86949d90e8fbfbe90f8fcf749322ce19e`; its parent is R4 Plan commit `81752dd10be750964d72cda9036db32e0cd2baf2`; that parent is runbook commit `8d05ec975a6ba7317d5e9c23963233b2f2d11832`.
- R5 Plan is `docs/superpowers/plans/2026-08-14-official-blender-mcp-r5-verifier-env.md`, 489 lines, 24,774 bytes, SHA-256 `053b84b7022ef1d5ecc4ce308a0b70dc84cb9f8d3addf34a45e843832b696175`.
- Frozen controller template is `.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001/r3_controller.py`, dev/inode `16777232/301445840`, mode `0600`, nlink `1`, 6,924 lines, 285,387 bytes, SHA-256 `7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a`.
- Frozen R5 driver template is `.superpowers/sdd/modeling-remediation/r5-live-driver/driver.sh`, dev/inode `16777232/301788945`, mode `0600`, nlink `1`, 806 lines, 32,620 bytes, SHA-256 `43fc40289f029d9fd763208d57914ccd9ddb359c81790662c1b1ca5fa44ede44`.
- Old family `.superpowers/sdd/modeling-remediation/final-retest-r3` is dev/inode `16777232/301445838`, mode `0700`; its terminal attempt-0001 is dev/inode `16777232/301445839`, mode `0700`, with exactly 16 frozen native-0600 leaves. Its closure is 2,884 bytes, SHA-256 `99102e9fa5a4abff4349d2584ecfd9b93932ce95c6390d9311ebd0c2c8852ba3`: for each lexically sorted basename, serialize one object with exact keys `path`, `dev`, `ino`, `uid`, `mode`, `nlink`, `size`, and `sha256`; `mode` is the strict JSON integer `384` (`0600`); use `json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"`, then concatenate all 16 rows.
- The frozen closure contains one canonical run ticket and one closed eight-row journal: call 1 passed and call 2 failed because the CLI helper resolved literal `blender`. Derive and verify `PRIOR_FROZEN_TICKET_COUNT=1` and this semantic summary from the frozen closure; do not maintain separate ticket/journal identity fields.
- Followup-3 report is dev/inode `16777232/301956493`, mode `0600`, nlink `1`, 172 bytes, SHA-256 `3a4edbc10e45236a0f644bf679c132479c2a1bb6d7dba78639bd9ec48aa960fa`, with unique current-run count one and `STATUS: BLOCKED`. Never reopen, append, replace, unlink, reuse, or include any old attempt leaf/report in new evidence.
- Config `/Users/yeminjie/.codex/config.toml` is dev/inode `16777232/294142487`, mode `0600`, nlink `1`, 9,940 bytes, SHA-256 `cac528cef67d97a3a702b5b9173721d0d8ab7c448d98e3dc5b49f6bdd932d90e`; its Blender section has the sole env pair `BLENDER_PATH = "/Applications/Blender.app/Contents/MacOS/Blender"`.
- Blender executable is dev/inode `16777232/206447352`, mode `0755`, nlink `1`, 183,237,520 bytes, SHA-256 `60ba7a9b6743f7acf101274361fa76409e382ae07cd2007ce07dea30f6b129f2`.
- Fresh family is exactly `.superpowers/sdd/modeling-remediation/r6-evidence/final-retest-r3`; fresh run is its `attempt-0001`. Both are absent before Task 3. Never create old-family attempt-0002 or any R6 second attempt.
- Port 9876 and owned Blender/controller/recorder processes are absent. Existing host-managed Blender MCP stdio servers are out of scope and must not be signalled.
- Before this Plan-only commit, do not start Blender/MCP or create R6 runtime/evidence. After it, do not modify either Plan, runbook, config, official MCP source, tests, audit helper, or old evidence.
- Any failed pre-ticket probe/guard writes current count zero and BLOCKED to the new report if its original descriptor remains available. Any failed post-ticket guard uses current count one. No R6 retry exists.

## File map

- Create/commit: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r6-config-env.md`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/r6-live-runtime/{build.py,r3_controller.py,driver.sh}`.
- Create ignored/bound: `.superpowers/sdd/modeling-remediation/task-7-followup-4-{brief,report}.md`.
- Create ignored/bound after GUI preflight: `.superpowers/sdd/modeling-remediation/r6-evidence/final-retest-r3/attempt-0001`.
- Create ignored conditionally: `task-7-followup-4-{failure,success}-{root-checks.json,review-package.json,review.md}` under `.superpowers/sdd/modeling-remediation/`.
- Modify only after certified success: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`.

### Task 1: adversarially certify and commit this Plan

- [ ] Prove every frozen path/identity/SHA, exact old 16-leaf closure, old terminal/report, absent fresh family, clean HEAD, empty port, and no owned processes. Treat old artifacts as read-only.
- [ ] Extract Appendices A, B, and C by their headings byte-for-byte and compile all three in memory. Run only Appendix B during Plan certification, in a fresh native mode-0700 `/private/tmp` root. Require its unique GREEN line and every declared mutation/parent-swap negative RED with no rejected output; Appendix C may not start Blender before the Plan-only commit.
- [ ] Dispatch fresh spec/safety, execution/state-machine, and Ponytail/YAGNI lenses against one frozen Plan SHA. Each writes only through a preallocated native-0600/nlink-1 report descriptor. Any Critical, Important, or Minor burns the round; repair only this Plan and repeat all three.
- [ ] Commit only this Plan with message `docs: plan configured Blender CLI environment`. Require parent `507833f86949d90e8fbfbe90f8fcf749322ce19e`, one changed path, and clean status. Do not start Blender/MCP.

### Task 2: generate and prove the R6 controller and driver

- [ ] Exclusive-create `.superpowers/sdd/modeling-remediation/r6-live-runtime` mode 0700. Extract Appendix A exactly to `build.py`, compile in memory, and create no pyc. Generate the exact controller and driver identities declared by Appendix A; the directory then contains exactly those three native-0600/nlink-1 leaves.
- [ ] Require new controller compile, exact Ruff command from R4, existing controller probe GREEN, `/bin/bash -n`, seven compilable driver Python heredocs, exactly one controller `run`, no run stdin redirect, and exact source/config/Blender identities. Deleting either controller change, changing/adding a config env key, changing the Blender path, changing any of the six driver anchors, or late-swapping an output parent is RED.
- [ ] Before any ticket/evidence root exists, use the descriptor-bound patched controller bytes, its `production_config()`, and the exact final MCP child environment to run the official `blmcp.tools_helpers.blender_cli.run_blender_cli("--factory-startup", ...)` in a native mode-0700 `/private/tmp` root. Require resolver path `/Applications/Blender.app/Contents/MacOS/Blender`, the helper's exact return `{"version":[5,2,0],"filepath":""}`, unchanged controller/config/source/Blender identities, and fresh ticket/family still absent. This is the only pre-ticket background Blender probe.
- [ ] Dispatch fresh Task 2 spec and quality reviewers. Both must approve; tracked/index status remains clean and no listener/controller/recorder process remains.

### Task 3: perform the sole fresh live run

- [ ] Root exclusive-creates followup-4 report native 0600/nlink-1 and compact brief, retaining the report's original descriptor through every GUI/prelaunch step. Bind this Plan commit/SHA; R5/R4/runbook commits and SHAs; R6 runtime identities; config/Blender identities; the immutable old-family closure and followup-3 report; new report identity; closure-derived `PRIOR_FROZEN_TICKET_COUNT=1`; `CURRENT_RUN_LIMIT=1`; absent fresh family/ticket; and empty owned-process inventory. The brief points to this Plan and bound R4 Tasks 3 through 5, copying no prose.
- [ ] Apply only R4 Task 3 Step 2's Computer Use GUI actions and binding checks. R6 explicitly supersedes R4's empty-report preflight-failure rule: on GUI preflight failure, clean only the exactly bound new Blender/listener, prove port 9876 empty, append `prior_frozen_ticket_count: 1`, `actual_run_count: 0`, cleanup facts, and unique `STATUS: BLOCKED` through the retained original report descriptor, fsync/close it, and terminate without creating the fresh family. Online Access remains under the user's explicit authorization.
- [ ] Only after GUI preflight PASS, recheck the exact old 16-leaf closure, then exclusive-create `r6-evidence`, its `final-retest-r3`, and `attempt-0001` as native mode 0700. Copy the exact R6 controller as the sole native-0600/nlink-1 leaf using descriptor-bound O_EXCL I/O. Recheck runtime/config/Blender/Plan/repo identities. Any failure before PTY launch cleans only the bound new Blender/listener by PID/start/image, proves port 9876 empty, appends `prior_frozen_ticket_count: 1`, `actual_run_count: 0`, cleanup facts, and unique `STATUS: BLOCKED` through the retained original report descriptor, fsyncs/closes it, and terminates; never replace the PTY or report writer.
- [ ] Immediately before launch require the retained report still has its original empty identity, then close that allocator descriptor. Use the ten arguments in R4 Task 3 Step 3 order and launch exactly once with R4 Step 4 argv, substituting R6 driver, Plan commit/SHA, followup-4 report dev/ino, and the bound fresh scratch/listener. No prompt, paste, source, stdin redirect, prequeued ACK, or second launch. After launch, early guard/PTY/FD loss follows R4's terminal-absence fail-closed rule; no replacement writer opens the report.
- [ ] Apply R4 Task 3 Steps 5 through 7 exactly. Option C remains: at `VISUAL_ACK_REQUIRED`, the implementer returns only live PTY identity plus all ordered absolute PNG paths/SHA; root displays every image and the user explicitly supplies every verdict before one canonical ACK. Old run produced no visual ACK and contributes nothing. On every terminal, root rechecks the old 16-leaf closure and records the result externally without adding old inputs to new evidence.

### Task 4: independently review a grouped direct failure

- [ ] Apply R4 Task 4 exactly with these substitutions only: current Plan/commit/SHA and R6 controller SHA; fresh R6 attempt root only; followup-4 report; `task-7-followup-4-failure-{root-checks.json,review-package.json,review.md}`. Old-family leaves/report are forbidden from package inputs. Current ticket count must be one and old frozen ticket count remains external history only. Root rechecks the old 16-leaf closure before dispatch and after terminal review.

### Task 5: audit and commit a successful Option-C run

- [ ] Apply R4 Task 5 exactly with these substitutions only: current Plan/commit/SHA and R6 controller SHA; fresh R6 evidence closure only; followup-4 report; `task-7-followup-4-success-{root-checks.json,review-package.json,review.md}`. Root rechecks the old 16-leaf closure before dispatch, after review, and after the final clean gate.
- [ ] In R4 Task 5 Step 3 replace only the first-parent rule with an exact length-five array in runbook/R4-Plan/R5-Plan/R6-Plan/audit order. Its five length-one `paths` arrays map respectively to the runbook, R4 Plan, R5 Plan, this Plan, and modeling-audit paths; parent values equal old R3 Plan, runbook, R4 Plan, R5 Plan, and R6 Plan commits respectively.

## Appendix A: exact R6 runtime builder

Extract the following Python body without its Markdown fences. It is exactly 270 lines, 11,130 bytes, SHA-256 `3b5da88fc20a9aaaaad9482015129f50b94cedd46753190ca3a1b93f34b8bc14`. It accepts exactly `SOURCE_CONTROLLER SOURCE_DRIVER OUTPUT_CONTROLLER OUTPUT_DRIVER`.

````python
from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


CONTROLLER_SIZE = 285387
CONTROLLER_SHA256 = "7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a"
CONTROLLER_DEV_INO = (16777232, 301445840)
DRIVER_SIZE = 32620
DRIVER_SHA256 = "43fc40289f029d9fd763208d57914ccd9ddb359c81790662c1b1ca5fa44ede44"
DRIVER_DEV_INO = (16777232, 301788945)
OUTPUT_CONTROLLER_SIZE = 285770
OUTPUT_CONTROLLER_SHA256 = "c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc"
OUTPUT_DRIVER_SIZE = 32772
OUTPUT_DRIVER_SHA256 = "26e4c7a514ff7c754f96d1272b2dd5671a3c09e29f6fd6904782dc85393d882e"
R5_PLAN_COMMIT = "507833f86949d90e8fbfbe90f8fcf749322ce19e"
R4_PLAN_COMMIT = "81752dd10be750964d72cda9036db32e0cd2baf2"


def leaf_id(value: os.stat_result) -> tuple[int, ...]:
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


def parent_id(value: os.stat_result) -> tuple[int, ...]:
    return value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode)


def read_owned(path: Path, size: int, digest: str, dev_ino: tuple[int, int]) -> bytes:
    if path != Path(os.path.realpath(path)):
        raise RuntimeError("source path is not canonical")
    parent = path.parent
    parent_info = os.lstat(parent)
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or stat.S_ISLNK(parent_info.st_mode)
        or parent_info.st_uid != os.getuid()
        or stat.S_IMODE(parent_info.st_mode) != 0o700
    ):
        raise RuntimeError("source parent is unsafe")
    expected_parent = parent_id(parent_info)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if parent_id(os.fstat(parent_fd)) != expected_parent:
            raise RuntimeError("source parent changed")
        before = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size != size
            or (before.st_dev, before.st_ino) != dev_ino
        ):
            raise RuntimeError("source identity differs")
        expected = leaf_id(before)
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            if leaf_id(os.fstat(fd)) != expected:
                raise RuntimeError("source changed before open")
            chunks = bytearray()
            while len(chunks) < size:
                chunk = os.read(fd, min(65536, size - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            raw = bytes(chunks)
            if len(raw) != size or os.read(fd, 1):
                raise RuntimeError("source bounded read differs")
            if leaf_id(os.fstat(fd)) != expected:
                raise RuntimeError("source changed during read")
        finally:
            os.close(fd)
        if (
            leaf_id(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)) != expected
            or parent_id(os.fstat(parent_fd)) != expected_parent
            or parent_id(os.lstat(parent)) != expected_parent
        ):
            raise RuntimeError("source path changed")
    finally:
        os.close(parent_fd)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("source digest differs")
    return raw


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"patch anchor count differs: {old!r}")
    return text.replace(old, new)


def build_controller(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    text = once(
        text,
        '    production_safe_executable(Path(os.path.abspath(command)), "configured server")\n'
        "    return section, names, source_mcp",
        '    production_safe_executable(Path(os.path.abspath(command)), "configured server")\n'
        '    env = section.get("env")\n'
        '    blender_path = "/Applications/Blender.app/Contents/MacOS/Blender"\n'
        '    if env != {"BLENDER_PATH": blender_path}:\n'
        '        raise R2Error("CONFIG", "configured Blender environment differs")\n'
        '    production_safe_executable(Path(blender_path), "configured Blender")\n'
        "    return section, names, source_mcp",
    )
    text = once(
        text,
        '        params = StdioServerParameters(\n'
        '            command=section["command"],\n'
        '            args=section["args"],\n'
        "            env=production_child_env(),\n"
        "        )",
        "        mcp_env = production_child_env()\n"
        '        mcp_env["BLENDER_PATH"] = section["env"]["BLENDER_PATH"]\n'
        "        params = StdioServerParameters(\n"
        '            command=section["command"],\n'
        '            args=section["args"],\n'
        "            env=mcp_env,\n"
        "        )",
    )
    payload = text.encode("utf-8")
    if len(payload) != OUTPUT_CONTROLLER_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_CONTROLLER_SHA256:
        raise RuntimeError("patched controller identity differs")
    return payload


def build_driver(raw: bytes) -> bytes:
    text = raw.decode("utf-8")
    text = once(
        text,
        "/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/"
        ".superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001",
        "/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/"
        ".superpowers/sdd/modeling-remediation/r6-evidence/final-retest-r3/attempt-0001",
    )
    text = once(
        text,
        "$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001",
        "$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/r6-evidence/final-retest-r3/attempt-0001",
    )
    text = once(text, "task-7-followup-3-report.md", "task-7-followup-4-report.md")
    text = once(
        text,
        "docs/superpowers/plans/2026-08-14-official-blender-mcp-r5-verifier-env.md",
        "docs/superpowers/plans/2026-08-14-official-blender-mcp-r6-config-env.md",
    )
    text = once(
        text,
        "CONTROLLER_SHA256=7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a",
        f"CONTROLLER_SHA256={OUTPUT_CONTROLLER_SHA256}",
    )
    text = once(
        text,
        '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = '
        f"{R4_PLAN_COMMIT}\n"
        f'  test "$(git -C "$FEATURE_ROOT" rev-parse {R4_PLAN_COMMIT}^)" = "$R3_RUNBOOK_COMMIT"',
        '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = '
        f"{R5_PLAN_COMMIT}\n"
        f'  test "$(git -C "$FEATURE_ROOT" rev-parse {R5_PLAN_COMMIT}^)" = {R4_PLAN_COMMIT}\n'
        f'  test "$(git -C "$FEATURE_ROOT" rev-parse {R4_PLAN_COMMIT}^)" = "$R3_RUNBOOK_COMMIT"',
    )
    payload = text.encode("utf-8")
    if len(payload) != OUTPUT_DRIVER_SIZE or hashlib.sha256(payload).hexdigest() != OUTPUT_DRIVER_SHA256:
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
    expected_parent = parent_id(info)
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if parent_id(os.fstat(parent_fd)) != expected_parent:
            raise RuntimeError("output parent changed")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
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
                    leaf_id(current) != leaf_id(final)
                    or final.st_uid != os.getuid()
                    or stat.S_IMODE(final.st_mode) != 0o600
                    or final.st_nlink != 1
                    or final.st_size != len(payload)
                    or parent_id(os.fstat(parent_fd)) != expected_parent
                    or parent_id(os.lstat(parent)) != expected_parent
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


def remove_exact(path: Path, expected: os.stat_result) -> None:
    try:
        current = os.lstat(path)
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
        raise RuntimeError("refusing to remove changed output")
    os.unlink(path)


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: build.py SOURCE_CONTROLLER SOURCE_DRIVER OUTPUT_CONTROLLER OUTPUT_DRIVER")
    source_controller, source_driver, output_controller, output_driver = map(Path, sys.argv[1:])
    controller = build_controller(read_owned(source_controller, CONTROLLER_SIZE, CONTROLLER_SHA256, CONTROLLER_DEV_INO))
    driver = build_driver(read_owned(source_driver, DRIVER_SIZE, DRIVER_SHA256, DRIVER_DEV_INO))
    controller_info = write_owned(output_controller, controller)
    try:
        driver_info = write_owned(output_driver, driver)
    except BaseException:
        remove_exact(output_controller, controller_info)
        raise
    print(
        f"R6_RUNTIME_GREEN controller_lines={len(controller.splitlines())} "
        f"controller_bytes={len(controller)} controller_sha256={hashlib.sha256(controller).hexdigest()} "
        f"driver_lines={len(driver.splitlines())} driver_bytes={len(driver)} "
        f"driver_sha256={hashlib.sha256(driver).hexdigest()} "
        f"controller_ino={controller_info.st_ino} driver_ino={driver_info.st_ino}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix C: exact pre-ticket Blender CLI probe

Extract the following Python body without its Markdown fences. It is exactly 244 lines, 9,543 bytes, SHA-256 `4e0dba408d74369807bd37347c2554d1c0b156ff13b935569ef38b3dfe776b8f`. Run it only in Task 2, under `/Users/yeminjie/.local/bin/uv run --quiet --no-project --python 3.13 --with 'mcp[cli]>=1.2.0,<2' --with-editable /Users/yeminjie/blender_mcp/mcp python`, with arguments `R6_CONTROLLER CONFIG BLENDER MCP_SOURCE FRESH_FAMILY MUTATION_ROOT`. `MUTATION_ROOT` must be a fresh native mode-0700 `/private/tmp` directory; `FRESH_FAMILY` must still be absent.

````python
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path

from blmcp.tools_helpers.blender_cli import _get_blender_path, run_blender_cli


CONFIG_ID = (16777232, 294142487, 501, 0o600, 1, 9940)
CONFIG_SHA256 = "cac528cef67d97a3a702b5b9173721d0d8ab7c448d98e3dc5b49f6bdd932d90e"
BLENDER_ID = (16777232, 206447352, 501, 0o755, 1, 183237520)
BLENDER_SHA256 = "60ba7a9b6743f7acf101274361fa76409e382ae07cd2007ce07dea30f6b129f2"
MCP_HEAD = "4309a39646e644261624bfcd2bca669b343b7621"
BLENDER_PATH = "/Applications/Blender.app/Contents/MacOS/Blender"
CONTROLLER_SIZE = 285770
CONTROLLER_SHA256 = "c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc"


def snapshot(path: Path, expected: tuple[int, ...], digest: str) -> tuple[int, ...]:
    info = os.lstat(path)
    observed = (
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
        info.st_nlink,
        info.st_size,
    )
    if path != Path(os.path.realpath(path)) or observed != expected or not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"unsafe probe input: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (info.st_dev, info.st_ino, info.st_size):
            raise RuntimeError(f"probe input changed before open: {path}")
        hasher = hashlib.sha256()
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError(f"short probe read: {path}")
            hasher.update(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1) or hasher.hexdigest() != digest:
            raise RuntimeError(f"probe input digest differs: {path}")
        final = os.fstat(fd)
        if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ):
            raise RuntimeError(f"probe input changed during read: {path}")
    finally:
        os.close(fd)
    current = os.lstat(path)
    if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns, current.st_ctime_ns) != (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    ):
        raise RuntimeError(f"probe input path changed: {path}")
    return observed


def git(source: Path) -> tuple[str, str]:
    head = subprocess.run(
        ["/usr/bin/git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["/usr/bin/git", "-C", str(source), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        capture_output=True,
        timeout=10,
        check=True,
    ).stdout
    if head != MCP_HEAD or status:
        raise RuntimeError("official MCP source differs")
    return head, status


def load_controller(path: Path) -> tuple[dict[str, object], tuple[int, ...]]:
    info = os.lstat(path)
    identity = (
        info.st_dev,
        info.st_ino,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )
    if (
        path != Path(os.path.realpath(path))
        or not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size != CONTROLLER_SIZE
    ):
        raise RuntimeError("unsafe R6 controller")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino, opened.st_size) != (info.st_dev, info.st_ino, info.st_size):
            raise RuntimeError("R6 controller changed before open")
        chunks = bytearray()
        while len(chunks) < CONTROLLER_SIZE:
            chunk = os.read(fd, min(65536, CONTROLLER_SIZE - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
        raw = bytes(chunks)
        if len(raw) != CONTROLLER_SIZE or os.read(fd, 1):
            raise RuntimeError("R6 controller bounded read differs")
        if hashlib.sha256(raw).hexdigest() != CONTROLLER_SHA256:
            raise RuntimeError("R6 controller digest differs")
        final = os.fstat(fd)
        if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        ):
            raise RuntimeError("R6 controller changed during read")
    finally:
        os.close(fd)
    current = os.lstat(path)
    if (
        current.st_dev,
        current.st_ino,
        current.st_uid,
        stat.S_IMODE(current.st_mode),
        current.st_nlink,
        current.st_size,
        current.st_mtime_ns,
        current.st_ctime_ns,
    ) != identity:
        raise RuntimeError("R6 controller path changed")
    namespace: dict[str, object] = {"__name__": "r6_controller_probe", "__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace, identity


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit("usage: probe.py R6_CONTROLLER CONFIG BLENDER MCP_SOURCE FRESH_FAMILY MUTATION_ROOT")
    controller, config, blender, source, fresh_family, mutation_root = map(Path, sys.argv[1:])
    if fresh_family.exists() or fresh_family.is_symlink():
        raise RuntimeError("fresh family already exists")
    root_info = os.lstat(mutation_root)
    if (
        mutation_root != Path(os.path.realpath(mutation_root))
        or not stat.S_ISDIR(root_info.st_mode)
        or stat.S_ISLNK(root_info.st_mode)
        or root_info.st_uid != os.getuid()
        or stat.S_IMODE(root_info.st_mode) != 0o700
        or any(mutation_root.iterdir())
    ):
        raise RuntimeError("mutation root is unsafe")
    before_config = snapshot(config, CONFIG_ID, CONFIG_SHA256)
    before_blender = snapshot(blender, BLENDER_ID, BLENDER_SHA256)
    before_git = git(source)
    namespace, before_controller = load_controller(controller)
    section, _, parsed_source = namespace["production_config"](config)
    if parsed_source != source or section.get("env") != {"BLENDER_PATH": BLENDER_PATH}:
        raise RuntimeError("parsed configured Blender environment differs")
    env = namespace["production_child_env"]()
    env["BLENDER_PATH"] = section["env"]["BLENDER_PATH"]
    original_env = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        if _get_blender_path() != BLENDER_PATH:
            raise RuntimeError("official helper resolved a different Blender path")
        result = run_blender_cli(
            "--factory-startup",
            'import bpy; result = {"version": list(bpy.app.version), "filepath": bpy.data.filepath}',
        )
    finally:
        os.environ.clear()
        os.environ.update(original_env)
    if result != {"version": [5, 2, 0], "filepath": ""}:
        raise RuntimeError(f"official Blender CLI result differs: {result!r}")
    config_bytes = config.read_bytes()
    mutations = (
        config_bytes.replace(b"BLENDER_PATH =", b"BLENDER_PATH_X =", 1),
        config_bytes.replace(BLENDER_PATH.encode(), b"/bin/false", 1),
        config_bytes.replace(
            (f'BLENDER_PATH = "{BLENDER_PATH}"\n').encode(),
            (f'BLENDER_PATH = "{BLENDER_PATH}"\nEXTRA = "forbidden"\n').encode(),
            1,
        ),
    )
    for number, payload in enumerate(mutations, 1):
        path = mutation_root / f"config-{number}.toml"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise RuntimeError("short mutation write")
                view = view[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            namespace["production_config"](path)
        except Exception:
            pass
        else:
            raise RuntimeError(f"config mutation {number} was accepted")
    if snapshot(config, CONFIG_ID, CONFIG_SHA256) != before_config:
        raise RuntimeError("config changed across probe")
    if snapshot(blender, BLENDER_ID, BLENDER_SHA256) != before_blender:
        raise RuntimeError("Blender changed across probe")
    if git(source) != before_git:
        raise RuntimeError("official MCP source changed across probe")
    after_controller = snapshot(controller, before_controller[:6], CONTROLLER_SHA256)
    after_info = os.lstat(controller)
    if after_controller != before_controller[:6] or (after_info.st_mtime_ns, after_info.st_ctime_ns) != before_controller[6:]:
        raise RuntimeError("R6 controller changed across probe")
    if fresh_family.exists() or fresh_family.is_symlink():
        raise RuntimeError("probe created fresh evidence family")
    print("R6_BLENDER_CLI_PRETICKET_GREEN resolver=1 cli=1 config_mutations_red=3 ticket_absent=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B: exact disposable R6 harness

Extract the following Python body without its Markdown fences. It is exactly 184 lines, 8,187 bytes, SHA-256 `da3450b7d12d89bc332b0cee1dc1ad3e0433614dee0921a4f9dbc1e506e31ea1`. Run `harness.py BUILD_PY SOURCE_CONTROLLER SOURCE_DRIVER OUTPUT_ROOT` with canonical absolute paths and an empty native mode-0700 output root.

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


BUILD_SHA256 = "3b5da88fc20a9aaaaad9482015129f50b94cedd46753190ca3a1b93f34b8bc14"
CONTROLLER_SHA256 = "7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a"
DRIVER_SHA256 = "43fc40289f029d9fd763208d57914ccd9ddb359c81790662c1b1ca5fa44ede44"
OUTPUT_CONTROLLER_SHA256 = "c1a35f8f3e9c28429d4deb7f40315edd0f3c54a4cc620a8ee6ca96e5cc251cbc"
OUTPUT_DRIVER_SHA256 = "26e4c7a514ff7c754f96d1272b2dd5671a3c09e29f6fd6904782dc85393d882e"


def owned(path: Path, expected_sha: str) -> bytes:
    info = os.lstat(path)
    if (
        path != Path(os.path.realpath(path))
        or not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
        or info.st_size > 8 * 1024 * 1024
    ):
        raise RuntimeError("unsafe harness input")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError("harness input digest differs")
    return raw


def controller_shape(payload: bytes) -> None:
    ast.parse(payload)
    text = payload.decode("utf-8")
    config = (
        '    env = section.get("env")\n'
        '    blender_path = "/Applications/Blender.app/Contents/MacOS/Blender"\n'
        '    if env != {"BLENDER_PATH": blender_path}:\n'
        '        raise R2Error("CONFIG", "configured Blender environment differs")\n'
        '    production_safe_executable(Path(blender_path), "configured Blender")\n'
    )
    injection = (
        '        mcp_env = production_child_env()\n'
        '        mcp_env["BLENDER_PATH"] = section["env"]["BLENDER_PATH"]\n'
        '        params = StdioServerParameters(\n'
        '            command=section["command"],\n'
        '            args=section["args"],\n'
        '            env=mcp_env,\n'
        '        )\n'
    )
    if text.count(config) != 1 or text.count(injection) != 1:
        raise RuntimeError("configured Blender bridge shape differs")


def require_red(call, label: str) -> None:
    try:
        call()
    except (OSError, RuntimeError, SyntaxError):
        return
    raise RuntimeError(f"negative was accepted: {label}")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: harness.py BUILD_PY SOURCE_CONTROLLER SOURCE_DRIVER OUTPUT_ROOT")
    build, source_controller, source_driver, root = map(Path, sys.argv[1:])
    build_raw = owned(build, BUILD_SHA256)
    compile(build_raw, str(build), "exec")
    controller_raw = owned(source_controller, CONTROLLER_SHA256)
    driver_raw = owned(source_driver, DRIVER_SHA256)
    info = os.lstat(root)
    if (
        root != Path(os.path.realpath(root))
        or not stat.S_ISDIR(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
        or any(root.iterdir())
    ):
        raise RuntimeError("unsafe harness output root")
    namespace = {"__name__": "r6_build"}
    exec(compile(build_raw, str(build), "exec"), namespace)
    controller = namespace["build_controller"](controller_raw)
    driver = namespace["build_driver"](driver_raw)
    controller_shape(controller)
    output_controller = root / "r3_controller.py"
    output_driver = root / "driver.sh"
    result = subprocess.run(
        [sys.executable, str(build), str(source_controller), str(source_driver), str(output_controller), str(output_driver)],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    if result.returncode or result.stdout.count("R6_RUNTIME_GREEN ") != 1:
        raise RuntimeError(f"R6 build failed: {result.stderr}")
    if owned(output_controller, OUTPUT_CONTROLLER_SHA256) != controller:
        raise RuntimeError("controller output differs")
    if owned(output_driver, OUTPUT_DRIVER_SHA256) != driver:
        raise RuntimeError("driver output differs")
    compile(controller, "<r6-controller>", "exec")
    subprocess.run(["/bin/bash", "-n", str(output_driver)], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("driver heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r6-heredoc-{number}>", "exec")
    if driver.count(b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n') != 1:
        raise RuntimeError("controller run cardinality differs")
    controller_negatives = (
        controller.replace(b'        mcp_env["BLENDER_PATH"] = section["env"]["BLENDER_PATH"]\n', b"", 1),
        controller.replace(b'"BLENDER_PATH": blender_path', b'"BLENDER_PATH_X": blender_path', 1),
        controller.replace(b"/Applications/Blender.app/Contents/MacOS/Blender", b"/bin/false", 1),
        controller.replace(
            b'if env != {"BLENDER_PATH": blender_path}:',
            b'if env.get("BLENDER_PATH") != blender_path:',
            1,
        ),
    )
    for number, mutated in enumerate(controller_negatives, 1):
        require_red(lambda value=mutated: controller_shape(value), f"controller-{number}")
    source_controller_text = controller_raw.decode()
    source_driver_text = driver_raw.decode()
    controller_anchors = (
        '    production_safe_executable(Path(os.path.abspath(command)), "configured server")\n    return section, names, source_mcp',
        '        params = StdioServerParameters(\n            command=section["command"],\n            args=section["args"],\n            env=production_child_env(),\n        )',
    )
    driver_anchors = (
        "/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/"
        ".superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001",
        "$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/final-retest-r3/attempt-0001",
        "task-7-followup-3-report.md",
        "docs/superpowers/plans/2026-08-14-official-blender-mcp-r5-verifier-env.md",
        "CONTROLLER_SHA256=7d6e3f07c95995eaca562c8ff95b3bb2f47fbe41a5265582a6f6cf15bbd4101a",
        '  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = '
        '81752dd10be750964d72cda9036db32e0cd2baf2\n'
        '  test "$(git -C "$FEATURE_ROOT" rev-parse '
        '81752dd10be750964d72cda9036db32e0cd2baf2^)" = "$R3_RUNBOOK_COMMIT"',
    )
    for number, anchor in enumerate(controller_anchors, 1):
        mutated = source_controller_text.replace(anchor, f"R6_CONTROLLER_MUTATION_{number}", 1).encode()
        require_red(lambda value=mutated: namespace["build_controller"](value), f"source-controller-{number}")
    for number, anchor in enumerate(driver_anchors, 1):
        mutated = source_driver_text.replace(anchor, f"R6_DRIVER_MUTATION_{number}", 1).encode()
        require_red(lambda value=mutated: namespace["build_driver"](value), f"source-driver-{number}")
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
        require_red(
            lambda: namespace["write_owned"](swap_parent / "probe.py", controller),
            "late-parent-swap",
        )
    finally:
        os.open = original_open
    if not swapped or (swap_parent / "probe.py").exists() or (held_parent / "probe.py").exists():
        raise RuntimeError("late parent swap left rejected output")
    print(
        "R6_BUILD_HARNESS_GREEN controller=1 driver=1 syntax=1 heredocs=7 "
        "source_mutations_red=8 controller_mutations_red=4 parent_swap_red=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
