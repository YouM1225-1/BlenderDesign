# Official Blender MCP R16 Adopt Exact Patch Plan

## Goal and frozen admission

Adopt the already-correct two-file R15 source postimage without writing it again, run the never-started tests once, commit it once, construct a fresh R16 runtime, and perform one fresh complete live retest.

- Main HEAD is R15 Plan commit `6e78a91d9c4fab6746262c88e7032e789a3bae1c`, parent `deb5426a57748ae4e89e91afe0a1752e4c9fc2b0`. R15 Task2 report is dev/inode `16777232/306727888`, mode 0600, size 1,230, SHA-256 `becc0aa047ecafd6b9d524817015ecb369bf145a3f41d3a0f167287fcc13bf72`, unique BLOCKED, and integration/build/gate counts are zero. Its spec/quality/receipt inodes `306727889/306727890/306727891` are empty mode-0600 files. R15 runtime/evidence/live paths are absent and immutable.
- Upstream `/Users/yeminjie/blender_mcp` is HEAD `4309a39646e644261624bfcd2bca669b343b7621`, empty index, no untracked files, and exactly two unstaged paths. Tool postimage is 127 lines / 4,103 bytes / SHA-256 `85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26`; test postimage is 1,158 lines / 43,710 bytes / SHA-256 `a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63`; binary diff SHA-256 is `a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248`.
- Exact committed R15 dependencies are Plan `docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md`, 958/60,281/SHA `76f4ba731c95fb873cdd9beaec02bdab0bb1e488781578f145b6eb1ddb310e7c`; Appendix A replacements; Appendix E 346/14,230/SHA `ef81d9f1237873a3f8059f12066bbaedd976d67873440b39a058441ab37f16f0`; and Appendix C 126/4,629/SHA `d4e75498888c6f3c598e4547755a2e024b5c57fb4e1d4cbde1595359796ecbc0`.
- Exact base runtime inputs are R11 controller 285,409/SHA `58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27`; R14 driver 33,823/SHA `e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd`; R12 Plan Appendix B allocator 115/5,615/SHA `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`; R14 Plan Appendix C runner 115/6,019/SHA `a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9`.

## Fresh paths

- Task2 files are `.superpowers/sdd/modeling-remediation/r16-task2-report.md`, `.superpowers/sdd/modeling-remediation/r16-task2-spec-review.md`, `.superpowers/sdd/modeling-remediation/r16-task2-quality-review.md`, and `.superpowers/sdd/modeling-remediation/r16-task2-terminal-receipt.md`.
- Runtime is native-0700 `.superpowers/sdd/modeling-remediation/r16-live-runtime` with exactly `.superpowers/sdd/modeling-remediation/r16-live-runtime/r3_controller.py`, `.superpowers/sdd/modeling-remediation/r16-live-runtime/driver.sh`, `.superpowers/sdd/modeling-remediation/r16-live-runtime/r16_allocator.py`, and `.superpowers/sdd/modeling-remediation/r16-live-runtime/r16_allocator_runner.py`.
- Live paths are `.superpowers/sdd/modeling-remediation/r16-evidence/final-retest-r3/attempt-0001`, `.superpowers/sdd/modeling-remediation/task-7-r16-followup-1-brief.md`, `.superpowers/sdd/modeling-remediation/task-7-r16-followup-1-report.md`, `.superpowers/sdd/modeling-remediation/task-7-r16-followup-1-failure-review.md`, and `.superpowers/sdd/modeling-remediation/task-7-r16-followup-1-success-review.md`. Every path is absent at allocation; `.superpowers/sdd/modeling-remediation/r16-evidence/final-retest-r3/attempt-0002` is always forbidden.

## Task 1 — certify this Plan only

- Exact Appendix identities are A `79/3,916/c6a8556587ae267dddf08dc4a5f95563509635c63c8e69a6092ab471d83f4ac4`; B `154/8,889/ce90c203f549c57e55f12002175a55217705ea4f1bc21de46ddabbee8d8dcb22`; C `335/20,525/cb7aa106f1bc2f8c3ae59d5704199eec558bb0f2f881e72980daa1652b0d96e8`; D `135/8,982/4c98190f2b6028a7ab41f4a3681f5f1005209408835f4d7a20089004a512c8dc`; E `93/4,894/79c099798909b7433bfd1de11c963a4937ed021f62bc324be3f6d3f30efa01ce`.
- Extract Appendices A/B/C/D/E exactly, require their declared identities, and run Appendix E once in a disposable native-0700 `/private/tmp` root; Appendix E owns the sole compile pass. It invokes Appendix A in `dirty` mode, runs exact R15 E `--selfcheck`, builds with a synthetic non-parent 40-hex pin, gates under canonical Python 3.13, and requires one `R16_PLAN_HARNESS_GREEN adoption=1 primitives=1 builder=1 gate=1 static=1`. It does not invoke Appendix C owner, R15 E real integration, allocator, runner, driver, Blender, MCP, or either source test.
- Three fresh reviewers audit one frozen Plan SHA for spec/safety, execution/state, and Ponytail/YAGNI. Their final files must each contain unique exact `CRITICAL: 0`, `IMPORTANT: 0`, and `MINOR: 0`; their respective unique final lines are `SPEC_VERDICT: PASS`, `EXECUTION_VERDICT: PASS`, and `PONYTAIL_VERDICT: PASS`. Any finding including Minor requires a fresh frozen round. Commit only this Plan with parent `6e78a91d...`; record the Plan commit/SHA and each final review's canonical path plus exact dev/inode/size/SHA for the Appendix-C arguments and Task3 admission. R1/R2 FAIL reports are never eligible.

## Task 2 — one persistent original-FD execution

- Extract exact committed R15 Appendix E by heading/fence from the exact R15 Plan and load it with `__name__ != "__main__"`; no selfcheck runs. Its `allocate`, `write_all`, `parse_approval`, `freeze`, `terminal`, `prepare_receipt`, `commit_receipt`, and `run_integration` are the only FD/integration primitives.
- Start one persistent owner before any test or source/index write. After only the minimal committed-R15-Plan/Appendix-E bootstrap, it O_EXCL-allocates the four Task2 files with R15 E and retains all original CLOEXEC FDs. Allocation collision is the sole permitted external/no-ledger failure. Inside the terminalizing `try`, it first writes/fsyncs the allocation/count prefix; only then may it perform any remaining admission, create temporary storage, or mutate source/index. Every such exception terminalizes BLOCKED once through the retained original report FD. Appendix A `dirty` is the first source gate; Appendix A is read-only and Appendix A from R15 is never invoked.
- Run pinned Ruff `0.16.2` on the two current paths, then exact R15 Appendix C once with canonical Python 3.14 and the canonical tool path. Require unique `R15_DEFERRED_RESTORE_GREEN cases=3`.
- Exact integration argv is `/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14 /Users/yeminjie/blender_mcp/tests/test_blender_mcp_with_blender.py TestBackgroundServer.test_render_thumbnail_to_path TestInteractiveServer.test_render_thumbnail_to_path`. The Python identity is dev/inode `16777232/211200476`, native 0755/nlink1, size 18,817,184, SHA `1ba16b38d45f006e449bb51a923dae83f3c384611bcd4ee428afd044b7ed4c95`. Environment is exactly `PATH=/usr/bin:/bin:/usr/sbin:/sbin:/Users/yeminjie/.local/bin`, invoking `HOME`, `BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender`, `BLENDER_MCP=/Users/yeminjie/blender_mcp/mcp/.venv/bin/blender-mcp`, `BLENDER_MCP_FOREGROUND=1`; R15 E owns one subprocess/process group and cleanup. Require rc0, exactly `Ran 2 tests`, `OK`, and ports 9876/9877/9878 empty.
- Stage only the two paths, invoke Appendix A `staged`, and commit once with parent `4309a396...`. Require the commit tree changes exactly those two paths to the declared postimages, one parent, clean index/worktree/untracked state, and record `R16_SOURCE_PIN`. No amend/reset/rebase/second commit or further source write.
- Allocate/retain the native-0700 runtime parent FD. Extract exact R12 allocator and R14 runner into private native-0600 files. Invoke exact Appendix B once under canonical Python 3.13 as `builder.py R16_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER RUNTIME_ROOT`; require one `R16_RUNTIME_GREEN`. Invoke exact Appendix D once under the same canonical Python as `runtime_gate.py RUNTIME_ROOT R16_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER`; require one `R16_RUNTIME_GATE_GREEN`. Python 3.13 is `/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13`, dev/inode `16777232/259766870`, 0755/nlink1, size 17,439,616, SHA `7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683`.
- Stop nonterminal after recording source/runtime identities and counts `patch=0 integration=1 builder=1 gate=1`; retain the four FDs and persistent process. Two fresh reviewers write only the preallocated review paths and uniquely end `SPEC_REVIEW: APPROVED` and `QUALITY_REVIEW: APPROVED`.
- On the sole exact `FINALIZE_REVIEWS` token, parse both reports through retained FDs, freeze/close them, prepare the receipt, append/freeze unique Task2 PASS, then descriptor-only commit receipt to mode 0400. Every exception before a terminal calls BLOCKED exactly once and leaves receipt mode 0600; a terminal exception is `UNVERIFIED_TERMINAL`, and a missing/malformed/non-0400 receipt is `PASS_WITHOUT_RECEIPT`. In either case close every remaining FD in `finally`, never reopen/write a terminal path, and never retry. Appendix C below is the exact owner state machine; its one-shot process is mandatory.

## Task 3 — sole fresh live run

- Admission binds: R16 Plan commit/SHA and exact final three Plan-review identities/zero findings; upstream parent `4309...`, exact `R16_SOURCE_PIN`, exact two-file tree and clean status; R16 Task2 report unique PASS, both Task2 approvals, matching preallocated receipt inode/content native 0400/nlink1; exact runtime parent/four leaves; frozen R15 BLOCKED/empty files/absences; all fresh live absences; empty ports/process inventory. It also binds immutable driver-input `.superpowers/sdd/modeling-remediation/task-7-brief.md` as dev/inode `16777232/295274948`, uid 501, mode 0600, nlink1, size 538,571, SHA `fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b`, exactly matching the unchanged R14/R16 driver constants.
- After that exact R16 admission, inherit the committed R15 Task3 transitions verbatim, substituting only R15 Plan/review/Task2/source/runtime/live namespaces and markers with the bound R16 values. This includes report-first original-FD fallback, one fresh GUI preflight and action-time Online Access confirmation, raw `bpy.app.tempdir`, exact R10 scratch checker once, exact R16 runner once, retained evidence/controller FDs, exact ten-argument R16 driver once in one PTY with FD8, at most one ticket/actual run, and cleanup on every terminal. The ten arguments retain the exact R15 order; no argument is reconstructed from prose.
- `.superpowers/sdd/modeling-remediation/task-7-r16-followup-1-brief.md` is a fresh root-only GUI/scratch/admission/review record and is never presented as driver input. The unchanged driver intentionally consumes only the separately bound immutable `.superpowers/sdd/modeling-remediation/task-7-brief.md`; Task3 binds both artifacts and never substitutes or confuses their roles.
- Display every fresh R16 PNG in manifest order, collect one explicit verdict per image, and send exactly one canonical ordered Option-C ACK. No predecessor image/verdict/ACK, scratch, ticket, listener, PTY, attempt, or report is reusable.

## Task 4 — terminal review and audit

- Failure is fail-closed and cannot be promoted. Success requires fresh root checks, manifest/package, independent success review, exact cleanup, and then the audit file as the sole new commit.
- Successful first-parent/path-array history has exact length 15: runbook, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, audit; parents are old-R3, runbook, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16.

## Appendix A — exact read-only adoption checker

Extract this body without fences. Invoke only as `adoption.py dirty` before tests and `adoption.py staged` after staging. It never writes.

````python
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path("/Users/yeminjie/blender_mcp")
MAIN = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install")
PIN = "4309a39646e644261624bfcd2bca669b343b7621"
R15_COMMIT = "6e78a91d9c4fab6746262c88e7032e789a3bae1c"
R15_PLAN = "docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md"
R15_PLAN_SHA = "76f4ba731c95fb873cdd9beaec02bdab0bb1e488781578f145b6eb1ddb310e7c"
TOOL = "mcp/blmcp/tools/render_thumbnail_to_path_toolcode.py"
TEST = "tests/test_blender_mcp_with_blender.py"
TOOL_SHA = "85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26"
TEST_SHA = "a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63"
DIFF_SHA = "a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248"


def git(*args: str) -> bytes:
    return subprocess.check_output(["/usr/bin/git", "-C", str(ROOT), *args])


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    if sys.argv[1:] not in (["dirty"], ["staged"]):
        raise SystemExit("usage: adoption.py dirty|staged")
    mode = sys.argv[1]
    plan = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"{R15_COMMIT}:{R15_PLAN}"])
    if sha(plan) != R15_PLAN_SHA:
        raise RuntimeError("R15 Plan differs")
    section = plan.split(b"## Appendix A ", 1)[1].split(b"Appendix C is", 1)[0]
    blocks = section.split(bytes([96]) * 4 + b"python\n")[1:]
    if len(blocks) != 2:
        raise RuntimeError("R15 replacement count differs")
    tool_replacement, test_replacement = (part.split(b"\n" + bytes([96]) * 4, 1)[0] + b"\n" for part in blocks)
    tool_old = git("show", f"{PIN}:{TOOL}")
    start = tool_old.index(b"    render_args = ('INVOKE_DEFAULT',) if use_deferred else ()\n")
    end_marker = b'    return Result(status="ok", filepath=output_path)\n'
    end = tool_old.index(end_marker, start) + len(end_marker)
    if tool_old.count(end_marker, start) != 1:
        raise RuntimeError("tool boundary differs")
    tool_expected = tool_old[:start] + tool_replacement + tool_old[end:]
    test_old = git("show", f"{PIN}:{TEST}")
    start = test_old.index(b"    def test_render_thumbnail_to_path(self) -> None:\n")
    separator = b"\n\n    def "
    end = test_old.index(separator, start) + 1
    test_expected = test_old[:start] + test_replacement + test_old[end:]
    if (len(tool_expected), sha(tool_expected), len(test_expected), sha(test_expected)) != (4103, TOOL_SHA, 43710, TEST_SHA):
        raise RuntimeError("reconstructed postimage differs")
    current = ((ROOT / TOOL).read_bytes(), (ROOT / TEST).read_bytes())
    if current != (tool_expected, test_expected):
        raise RuntimeError("current postimage differs")
    if git("rev-parse", "HEAD").decode().strip() != PIN or git("ls-files", "--others", "--exclude-standard"):
        raise RuntimeError("source identity differs")
    expected_paths = [TOOL, TEST]
    if mode == "dirty":
        if git("diff", "--cached", "--binary") or sha(git("diff", "--binary")) != DIFF_SHA:
            raise RuntimeError("dirty diff differs")
        expected = "".join(f" M {path}\n" for path in expected_paths).encode()
    else:
        if git("diff", "--binary") or sha(git("diff", "--cached", "--binary")) != DIFF_SHA:
            raise RuntimeError("staged diff differs")
        if git("diff", "--cached", "--name-only").decode().splitlines() != expected_paths:
            raise RuntimeError("staged paths differ")
        expected = "".join(f"M  {path}\n" for path in expected_paths).encode()
    if git("status", "--porcelain=v1") != expected:
        raise RuntimeError("source status differs")
    print(f"R16_ADOPTION_GREEN mode={mode} tool=1 test=1 diff=1 index=1 untracked=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix E — exact offline Plan harness

Extract once and invoke as `plan_harness.py ADOPTION BUILDER OWNER GATE`. It creates only disposable private files, runs Appendix A only in current `dirty` mode, runs B then D with one synthetic pin, and never invokes the owner, R15 C/E, allocator, runner, driver, Blender, MCP, or source tests.

````python
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


MAIN = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install")
PY313 = "/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13"
SYNTHETIC_PIN = "1111111111111111111111111111111111111111"
R12 = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r12-dirfd-allocation.md")
R14 = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md")
R15 = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md")


def appendix(raw: bytes, heading: bytes, lines: int, size: int, digest: str) -> bytes:
    start = raw.index(heading)
    fence = bytes([96]) * 4
    start = raw.index(fence + b"python\n", start) + len(fence + b"python\n")
    out = raw[start:raw.index(b"\n" + fence, start) + 1]
    if out.count(b"\n") != lines or len(out) != size or hashlib.sha256(out).hexdigest() != digest:
        raise RuntimeError("base appendix differs")
    return out


def write(root_fd: int, root: Path, name: str, raw: bytes) -> Path:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
    try:
        view = memoryview(raw)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return root / name


def run(argv: list[str], marker: str) -> None:
    done = subprocess.run(argv, text=True, capture_output=True, timeout=120)
    output = done.stdout + done.stderr
    if done.returncode or output.count(marker) != 1:
        raise RuntimeError(f"offline command failed: {argv!r}: {output}")


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit("usage: plan_harness.py ADOPTION BUILDER OWNER GATE")
    print("R16_PLAN_HARNESS_BEGIN", flush=True)
    adoption, builder, owner, gate = map(Path, sys.argv[1:])
    expected = {
        adoption: (79, 3916, "c6a8556587ae267dddf08dc4a5f95563509635c63c8e69a6092ab471d83f4ac4"),
        builder: (154, 8889, "ce90c203f549c57e55f12002175a55217705ea4f1bc21de46ddabbee8d8dcb22"),
        gate: (135, 8982, "4c98190f2b6028a7ab41f4a3681f5f1005209408835f4d7a20089004a512c8dc"),
        owner: (335, 20525, "cb7aa106f1bc2f8c3ae59d5704199eec558bb0f2f881e72980daa1652b0d96e8"),
    }
    for path, (lines, size, digest) in expected.items():
        raw = path.read_bytes()
        compile(raw, str(path), "exec")
        if raw.count(b"\n") != lines or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError(f"R16 appendix differs: {path}")
    run([PY313, str(adoption), "dirty"], "R16_ADOPTION_GREEN mode=dirty ")
    tmp = Path(tempfile.mkdtemp(prefix="r16-plan-", dir="/private/tmp"))
    os.chmod(tmp, 0o700)
    root_fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        r12 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8:{R12}"])
        r14 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"deb5426a57748ae4e89e91afe0a1752e4c9fc2b0:{R14}"])
        r15 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"6e78a91d9c4fab6746262c88e7032e789a3bae1c:{R15}"])
        allocator = write(root_fd, tmp, "allocator.py", appendix(r12, b"## Appendix B:", 115, 5615, "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"))
        runner = write(root_fd, tmp, "runner.py", appendix(r14, b"## Appendix C:", 115, 6019, "a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9"))
        primitives = write(root_fd, tmp, "primitives.py", appendix(r15, b"## Appendix E ", 346, 14230, "ef81d9f1237873a3f8059f12066bbaedd976d67873440b39a058441ab37f16f0"))
        selfcheck = tmp / "selfcheck"
        os.mkdir(selfcheck, 0o700)
        run([PY313, str(primitives), "--selfcheck", str(selfcheck)], "R15_TASK2_PRIMITIVES_GREEN fd=1 parser=1 terminal=1 process_group=1")
        runtime = tmp / "runtime"
        os.mkdir(runtime, 0o700)
        old_controller = MAIN / ".superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py"
        old_driver = MAIN / ".superpowers/sdd/modeling-remediation/r14-live-runtime/driver.sh"
        run([PY313, str(builder), SYNTHETIC_PIN, str(old_controller), str(old_driver), str(allocator), str(runner), str(runtime)], "R16_RUNTIME_GREEN ")
        run([PY313, str(gate), str(runtime), SYNTHETIC_PIN, str(old_controller), str(old_driver), str(allocator), str(runner)], "R16_RUNTIME_GATE_GREEN ")
    finally:
        os.close(root_fd)
        shutil.rmtree(tmp)
    print("R16_PLAN_HARNESS_GREEN adoption=1 primitives=1 builder=1 gate=1 static=1", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix C — exact persistent Task2 owner

Extract once to private native-0700 storage. Invoke once as `task2_owner.py PLAN_COMMIT PLAN_SHA OWNER_SIZE OWNER_SHA PLAN_SPEC_REVIEW SPEC_DEV:SPEC_INO:SPEC_SIZE:SPEC_SHA PLAN_EXEC_REVIEW EXEC_DEV:EXEC_INO:EXEC_SIZE:EXEC_SHA PLAN_PONY_REVIEW PONY_DEV:PONY_INO:PONY_SIZE:PONY_SHA ADOPTION BUILDER GATE`. All file paths are canonical absolute paths; sizes, hashes, and review identities are the exact final Task1 records. After its unique phase-1 marker, send no stdin until both fresh Task2 reviews are frozen; then send exactly `FINALIZE_REVIEWS` and one newline.

````python
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


MAIN = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install")
SOURCE = Path("/Users/yeminjie/blender_mcp")
MODELING = MAIN / ".superpowers/sdd/modeling-remediation"
PLAN_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r16-adopt-patch.md")
R15_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md")
R12_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r12-dirfd-allocation.md")
R14_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md")
R15 = "6e78a91d9c4fab6746262c88e7032e789a3bae1c"
SOURCE_PARENT = "4309a39646e644261624bfcd2bca669b343b7621"
PY313 = "/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13"
PY314 = "/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14"
TOOL = "mcp/blmcp/tools/render_thumbnail_to_path_toolcode.py"
TEST = "tests/test_blender_mcp_with_blender.py"


def sh(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=repo, text=True, capture_output=True, check=check)


def body(raw: bytes, heading: bytes, lines: int, size: int, digest: str) -> bytes:
    start = raw.index(heading)
    open_fence = bytes([96]) * 4 + b"python\n"
    close_fence = b"\n" + bytes([96]) * 4
    start = raw.index(open_fence, start) + len(open_fence)
    out = raw[start:raw.index(close_fence, start) + 1]
    if out.count(b"\n") != lines or len(out) != size or hashlib.sha256(out).hexdigest() != digest:
        raise RuntimeError(f"appendix differs: {heading!r}")
    return out


def read_exact(path: Path, mode: int = 0o600, size: int | None = None, digest: str | None = None) -> tuple[bytes, tuple[int, int, int, str]]:
    if Path(os.path.realpath(path)) != path:
        raise RuntimeError(f"noncanonical file: {path}")
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1 or (size is not None and before.st_size != size):
        raise RuntimeError(f"unsafe file: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened = os.fstat(fd)
        raw = os.pread(fd, before.st_size + 1, 0)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    fields = lambda value: (value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode), value.st_nlink, value.st_size)
    if fields(before) != fields(opened) or fields(opened) != fields(after) or fields(os.lstat(path)) != fields(after) or len(raw) != before.st_size:
        raise RuntimeError(f"file replaced: {path}")
    observed = hashlib.sha256(raw).hexdigest()
    if digest is not None and observed != digest:
        raise RuntimeError(f"file hash differs: {path}")
    return raw, (opened.st_dev, opened.st_ino, len(raw), observed)


def exact_file(path: Path, mode: int = 0o600, size: int | None = None, digest: str | None = None) -> tuple[int, int, int, str]:
    return read_exact(path, mode, size, digest)[1]


def expected_identity(raw: str) -> tuple[int, int, int, str]:
    parts = raw.split(":")
    if len(parts) != 4 or not all(part.isdigit() for part in parts[:3]) or re.fullmatch(r"[0-9a-f]{64}", parts[3]) is None:
        raise RuntimeError("review identity syntax differs")
    return int(parts[0]), int(parts[1]), int(parts[2]), parts[3]


def approved_review(path: Path, expected: tuple[int, int, int, str], verdict: str) -> tuple[int, int, int, str]:
    raw, observed = read_exact(path)
    if observed != expected:
        raise RuntimeError(f"Plan review identity differs: {path}")
    raw.decode("utf-8", errors="strict")
    lines = raw.splitlines()
    for marker in (b"CRITICAL: 0", b"IMPORTANT: 0", b"MINOR: 0"):
        if lines.count(marker) != 1:
            raise RuntimeError(f"Plan review findings differ: {path}")
    expected_verdict = verdict.encode()
    if lines.count(expected_verdict) != 1 or lines[-1] != expected_verdict:
        raise RuntimeError(f"Plan review verdict differs: {path}")
    return observed


def write_private(root_fd: int, root: Path, name: str, raw: bytes) -> Path:
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
    try:
        view = memoryview(raw)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return root / name


def marker(argv: list[str], token: str, env: dict[str, str] | None = None) -> str:
    done = subprocess.run(argv, text=True, capture_output=True, timeout=900, env=env)
    output = done.stdout + done.stderr
    if done.returncode or output.count(token) != 1:
        raise RuntimeError(f"command failed: {argv!r}: {output}")
    return output


def main() -> int:
    # Minimal bootstrap only: load the already-certified allocation/terminal primitives.
    r15 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"{R15}:{R15_REL}"])
    if hashlib.sha256(r15).hexdigest() != "76f4ba731c95fb873cdd9beaec02bdab0bb1e488781578f145b6eb1ddb310e7c":
        raise RuntimeError("R15 Plan differs")
    e_raw = body(r15, b"## Appendix E ", 346, 14230, "ef81d9f1237873a3f8059f12066bbaedd976d67873440b39a058441ab37f16f0")
    ns: dict[str, object] = {"__name__": "r15_task2_primitives"}
    exec(compile(e_raw, "<r15-appendix-e>", "exec"), ns)
    allocate, write_all, parse_approval = ns["allocate"], ns["write_all"], ns["parse_approval"]
    freeze, terminal = ns["freeze"], ns["terminal"]
    prepare_receipt, commit_receipt, run_integration = ns["prepare_receipt"], ns["commit_receipt"], ns["run_integration"]

    report = MODELING / "r16-task2-report.md"
    spec = MODELING / "r16-task2-spec-review.md"
    quality = MODELING / "r16-task2-quality-review.md"
    receipt = MODELING / "r16-task2-terminal-receipt.md"
    runtime = MODELING / "r16-live-runtime"
    fds: dict[str, int] = {}
    ids: dict[str, tuple[int, ...]] = {}
    terminal_done = False
    receipt_committed = False
    integration_count = 0
    builder_count = 0
    gate_count = 0
    runtime_fd = -1
    tmp: Path | None = None
    tmp_fd = -1
    try:
        for name, path in (("report", report), ("spec", spec), ("quality", quality), ("receipt", receipt)):
            fds[name], ids[name] = allocate(path)
    except BaseException:
        for fd in fds.values():
            os.close(fd)
        raise
    try:
        allocation_prefix = (
            "".join(f"r16_task2_{name}_allocated: {identity!r}\n" for name, identity in ids.items())
            + "r16_patch_apply_count: 0\ninitial_source_integration_run_count: 0\ninitial_runtime_builder_run_count: 0\ninitial_runtime_gate_run_count: 0\n"
        ).encode()
        write_all(fds["report"], allocation_prefix)
        os.fsync(fds["report"])

        if len(sys.argv) != 14:
            raise RuntimeError("Task2 owner argv differs")
        plan_commit, plan_sha, owner_size_raw, owner_sha = sys.argv[1:5]
        review_paths = [Path(sys.argv[index]) for index in (5, 7, 9)]
        review_ids = [expected_identity(sys.argv[index]) for index in (6, 8, 10)]
        adoption, builder, gate = [Path(value) for value in sys.argv[11:14]]
        if re.fullmatch(r"[0-9a-f]{40}", plan_commit) is None or re.fullmatch(r"[0-9a-f]{64}", plan_sha) is None or not owner_size_raw.isdigit() or re.fullmatch(r"[0-9a-f]{64}", owner_sha) is None:
            raise RuntimeError("Plan identity syntax differs")
        if sh(MAIN, "/usr/bin/git", "rev-parse", "HEAD").stdout.strip() != plan_commit or sh(MAIN, "/usr/bin/git", "rev-list", "--parents", "-n", "1", "HEAD").stdout.split() != [plan_commit, R15]:
            raise RuntimeError("Plan topology differs")
        committed_plan = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"HEAD:{PLAN_REL}"])
        if hashlib.sha256(committed_plan).hexdigest() != plan_sha or (MAIN / PLAN_REL).read_bytes() != committed_plan or sh(MAIN, "/usr/bin/git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines() != [str(PLAN_REL)] or sh(MAIN, "/usr/bin/git", "status", "--porcelain=v1").stdout:
            raise RuntimeError("Plan commit differs")
        plan_reviews = [approved_review(path, identity, verdict) for path, identity, verdict in zip(review_paths, review_ids, ("SPEC_VERDICT: PASS", "EXECUTION_VERDICT: PASS", "PONYTAIL_VERDICT: PASS"))]
        exact_file(Path(__file__), 0o600, int(owner_size_raw), owner_sha)
        exact_file(adoption, 0o600, 79, "c6a8556587ae267dddf08dc4a5f95563509635c63c8e69a6092ab471d83f4ac4")
        exact_file(builder, 0o600, 8889, "ce90c203f549c57e55f12002175a55217705ea4f1bc21de46ddabbee8d8dcb22")
        exact_file(gate, 0o600, 8982, "4c98190f2b6028a7ab41f4a3681f5f1005209408835f4d7a20089004a512c8dc")
        exact_file(Path(PY313), 0o755, 17439616, "7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683")
        exact_file(Path(PY314), 0o755, 18817184, "1ba16b38d45f006e449bb51a923dae83f3c384611bcd4ee428afd044b7ed4c95")

        r15_report = MODELING / "r15-task2-report.md"
        r15_raw, r15_report_id = read_exact(r15_report)
        if r15_report_id != (16777232, 306727888, 1230, "becc0aa047ecafd6b9d524817015ecb369bf145a3f41d3a0f167287fcc13bf72") or r15_raw.splitlines().count(b"STATUS: BLOCKED") != 1:
            raise RuntimeError("R15 Task2 report differs")
        r15_empty_ids = []
        for name, inode in (("r15-task2-spec-review.md", 306727889), ("r15-task2-quality-review.md", 306727890), ("r15-task2-terminal-receipt.md", 306727891)):
            identity = exact_file(MODELING / name, 0o600, 0, hashlib.sha256(b"").hexdigest())
            if identity != (16777232, inode, 0, hashlib.sha256(b"").hexdigest()):
                raise RuntimeError(f"R15 empty artifact differs: {name}")
            r15_empty_ids.append(identity)
        base_brief_id = exact_file(MODELING / "task-7-brief.md", 0o600, 538571, "fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b")
        if base_brief_id != (16777232, 295274948, 538571, "fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b"):
            raise RuntimeError("base driver brief differs")
        absent = [
            MODELING / "r15-live-runtime",
            MODELING / "r15-evidence",
            MODELING / "task-7-r15-followup-1-brief.md",
            MODELING / "task-7-r15-followup-1-report.md",
            MODELING / "r16-live-runtime",
            MODELING / "r16-evidence",
            MODELING / "task-7-r16-followup-1-brief.md",
            MODELING / "task-7-r16-followup-1-report.md",
            MODELING / "task-7-r16-followup-1-failure-review.md",
            MODELING / "task-7-r16-followup-1-success-review.md",
        ]
        if any(path.exists() or path.is_symlink() for path in absent):
            raise RuntimeError("fresh or frozen absence differs")
        adoption_dirty = marker([PY313, str(adoption), "dirty"], "R16_ADOPTION_GREEN mode=dirty ")
        c_raw = body(r15, b"## Appendix C ", 126, 4629, "d4e75498888c6f3c598e4547755a2e024b5c57fb4e1d4cbde1595359796ecbc0")
        tmp = Path(tempfile.mkdtemp(prefix="r16-task2-", dir="/private/tmp"))
        os.chmod(tmp, 0o700)
        tmp_fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

        bindings = (
            f"r16_plan_commit: {plan_commit}\nr16_plan_sha256: {plan_sha}\n"
            + "".join(f"r16_plan_review_{path.name}: {identity!r}\n" for path, identity in zip(review_paths, plan_reviews))
            + f"r15_task2_report: {r15_report_id!r}\nr15_empty_artifacts: {r15_empty_ids!r}\n"
            + f"base_driver_brief: {base_brief_id!r}\n"
            + f"r16_dirty_adoption_marker: {adoption_dirty.strip()}\n"
            + "r16_tool_postimage_sha256: 85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26\n"
            + "r16_test_postimage_sha256: a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63\n"
            + "r16_binary_diff_sha256: a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248\n"
            + "r15_task2_status: BLOCKED\n"
        ).encode()
        write_all(fds["report"], bindings)
        os.fsync(fds["report"])
        ruff = subprocess.run(["/Users/yeminjie/.local/bin/uvx", "--quiet", "ruff@0.16.2", "check", "--no-cache", "--isolated", "--target-version", "py313", "--select", "E4,E7,E9,F", str(SOURCE / TOOL), str(SOURCE / TEST)], text=True, capture_output=True, timeout=60)
        if ruff.returncode:
            raise RuntimeError(f"source Ruff failed: {ruff.stdout}{ruff.stderr}")
        c_path = write_private(tmp_fd, tmp, "r15_fault.py", c_raw)
        marker([PY314, str(c_path), str(SOURCE / TOOL)], "R15_DEFERRED_RESTORE_GREEN cases=3")
        env = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/Users/yeminjie/.local/bin",
            "HOME": os.environ["HOME"],
            "BLENDER_BIN": "/Applications/Blender.app/Contents/MacOS/Blender",
            "BLENDER_MCP": "/Users/yeminjie/blender_mcp/mcp/.venv/bin/blender-mcp",
            "BLENDER_MCP_FOREGROUND": "1",
        }
        integration_count = 1
        rc, output = run_integration([PY314, str(SOURCE / TEST), "TestBackgroundServer.test_render_thumbnail_to_path", "TestInteractiveServer.test_render_thumbnail_to_path"], env)
        if rc or len(re.findall(r"^Ran 2 tests in ", output, re.MULTILINE)) != 1 or len(re.findall(r"^OK$", output, re.MULTILINE)) != 1:
            raise RuntimeError(f"integration result differs: {output}")
        for port in (9876, 9877, 9878):
            probe = subprocess.run(["/usr/sbin/lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], text=True, capture_output=True)
            if probe.returncode not in (0, 1) or probe.stdout:
                raise RuntimeError(f"port {port} not empty")
        sh(SOURCE, "/usr/bin/git", "add", "--", TOOL, TEST)
        marker([PY313, str(adoption), "staged"], "R16_ADOPTION_GREEN mode=staged ")
        sh(SOURCE, "/usr/bin/git", "commit", "-m", "fix(blender-mcp): preserve deferred thumbnail settings")
        source_pin = sh(SOURCE, "/usr/bin/git", "rev-parse", "HEAD").stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", source_pin) is None or sh(SOURCE, "/usr/bin/git", "rev-list", "--parents", "-n", "1", "HEAD").stdout.split() != [source_pin, SOURCE_PARENT] or sh(SOURCE, "/usr/bin/git", "status", "--porcelain=v1").stdout:
            raise RuntimeError("source commit differs")
        if sh(SOURCE, "/usr/bin/git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines() != [TOOL, TEST]:
            raise RuntimeError("source commit paths differ")
        committed_tool = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"HEAD:{TOOL}"])
        committed_test = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"HEAD:{TEST}"])
        committed_diff = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "diff", "--binary", f"{SOURCE_PARENT}..HEAD"])
        if (len(committed_tool), hashlib.sha256(committed_tool).hexdigest()) != (4103, "85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26"):
            raise RuntimeError("committed tool differs")
        if (len(committed_test), hashlib.sha256(committed_test).hexdigest()) != (43710, "a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63"):
            raise RuntimeError("committed test differs")
        if hashlib.sha256(committed_diff).hexdigest() != "a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248":
            raise RuntimeError("committed binary diff differs")

        r12 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8:{R12_REL}"])
        r14 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"deb5426a57748ae4e89e91afe0a1752e4c9fc2b0:{R14_REL}"])
        allocator = write_private(tmp_fd, tmp, "r12_allocator.py", body(r12, b"## Appendix B:", 115, 5615, "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"))
        runner = write_private(tmp_fd, tmp, "r14_runner.py", body(r14, b"## Appendix C:", 115, 6019, "a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9"))
        os.mkdir(runtime, 0o700)
        runtime_fd = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        runtime_identity = os.fstat(runtime_fd)
        old_controller = MAIN / ".superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py"
        old_driver = MAIN / ".superpowers/sdd/modeling-remediation/r14-live-runtime/driver.sh"
        builder_count = 1
        build_output = marker([PY313, str(builder), source_pin, str(old_controller), str(old_driver), str(allocator), str(runner), str(runtime)], "R16_RUNTIME_GREEN ")
        gate_count = 1
        gate_output = marker([PY313, str(gate), str(runtime), source_pin, str(old_controller), str(old_driver), str(allocator), str(runner)], "R16_RUNTIME_GATE_GREEN ")
        current_root = os.lstat(runtime)
        if (runtime_identity.st_dev, runtime_identity.st_ino, runtime_identity.st_uid, stat.S_IMODE(runtime_identity.st_mode)) != (current_root.st_dev, current_root.st_ino, current_root.st_uid, stat.S_IMODE(current_root.st_mode)):
            raise RuntimeError("runtime root replaced")
        facts = (
            f"r16_source_pin: {source_pin}\nsource_integration_run_count: 1\nruntime_builder_run_count: 1\nruntime_gate_run_count: 1\n"
            f"builder_marker: {build_output.strip()}\ngate_marker: {gate_output.strip()}\n"
            + "".join(f"runtime_{path.name}: {exact_file(path)!r}\n" for path in sorted(runtime.iterdir()))
        ).encode()
        write_all(fds["report"], facts)
        os.fsync(fds["report"])
        print(f"R16_TASK2_PHASE1_GREEN source_pin={source_pin} actual_run_count=0", flush=True)
        if sys.stdin.readline() != "FINALIZE_REVIEWS\n":
            raise RuntimeError("finalize stdin differs")
        parse_approval(fds["spec"], "SPEC")
        freeze(fds["spec"], spec, ids["spec"])
        os.close(fds.pop("spec"))
        parse_approval(fds["quality"], "QUALITY")
        freeze(fds["quality"], quality, ids["quality"])
        os.close(fds.pop("quality"))
        pass_facts = b"actual_run_count: 0\n"
        predicted = prepare_receipt(fds["receipt"], receipt, ids["receipt"], fds["report"], ids["report"], pass_facts)
        report_fd = fds.pop("report")
        try:
            observed = terminal(report_fd, report, ids["report"], pass_facts, "PASS")
            terminal_done = True
        except BaseException as terminal_error:
            print(f"UNVERIFIED_TERMINAL {terminal_error}", flush=True)
            raise
        if predicted != observed:
            raise RuntimeError("receipt prediction differs")
        commit_receipt(fds.pop("receipt"), receipt, ids["receipt"])
        receipt_committed = True
        print("R16_TASK2_TERMINAL PASS", flush=True)
        return 0
    except BaseException as error:
        if not terminal_done and "report" in fds:
            try:
                terminal(fds.pop("report"), report, ids["report"], f"failure: {type(error).__name__}: {error}\nsource_integration_run_count: {integration_count}\nruntime_builder_run_count: {builder_count}\nruntime_gate_run_count: {gate_count}\nactual_run_count: 0\n".encode(), "BLOCKED")
                terminal_done = True
            except BaseException as terminal_error:
                print(f"UNVERIFIED_TERMINAL {terminal_error}", flush=True)
        elif terminal_done and not receipt_committed:
            print(f"PASS_WITHOUT_RECEIPT {error}", flush=True)
        raise
    finally:
        for name, fd in list(fds.items()):
            try:
                path = {"spec": spec, "quality": quality, "receipt": receipt}.get(name)
                if path is not None:
                    freeze(fd, path, ids[name])
            except BaseException:
                pass
            finally:
                os.close(fd)
        if runtime_fd >= 0:
            os.close(runtime_fd)
        if tmp_fd >= 0:
            os.close(tmp_fd)
        if tmp is not None:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix D — exact matching R16 runtime gate

Extract this 135-line body without fences. Invoke once under the canonical Python 3.13 exactly as specified in Task2.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


OLD_PIN = "4309a39646e644261624bfcd2bca669b343b7621"
OLD_CONTROLLER_SHA = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"
OLD_DRIVER_SHA = "e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd"
OLD_ALLOCATOR_SHA = "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"
OLD_RUNNER_SHA = "a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9"
R15_COMMIT = "6e78a91d9c4fab6746262c88e7032e789a3bae1c"


def owned(path: Path, mode: int, digest: str | None = None) -> tuple[bytes, os.stat_result]:
    if Path(os.path.realpath(path)) != path:
        raise RuntimeError(f"noncanonical gate input: {path}")
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() or stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1:
        raise RuntimeError(f"unsafe gate input: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        raw = os.read(fd, before.st_size + 1)
    finally:
        os.close(fd)
    if (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, before.st_size) or len(raw) != before.st_size or os.lstat(path).st_ino != opened.st_ino:
        raise RuntimeError(f"gate input replaced: {path}")
    if digest is not None and hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError(f"gate input hash differs: {path}")
    return raw, opened


def one(raw: bytes, old: bytes, new: bytes, count: int = 1) -> bytes:
    if raw.count(old) != count or raw.count(new) != 0:
        raise RuntimeError("gate reversal anchor differs")
    return raw.replace(old, new)


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit("usage: runtime_gate.py RUNTIME_ROOT R16_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER")
    root = Path(sys.argv[1])
    expected_pin = sys.argv[2]
    if re.fullmatch(r"[0-9a-f]{40}", expected_pin) is None or expected_pin == OLD_PIN:
        raise RuntimeError("expected source pin differs")
    old_controller_path, old_driver_path, old_allocator_path, old_runner_path = map(Path, sys.argv[3:])
    root_info = os.lstat(root)
    if Path(os.path.realpath(root)) != root or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700:
        raise RuntimeError("unsafe runtime root")
    names = sorted(path.name for path in root.iterdir())
    if names != ["driver.sh", "r16_allocator.py", "r16_allocator_runner.py", "r3_controller.py"]:
        raise RuntimeError("runtime leaves differ")
    controller, controller_info = owned(root / "r3_controller.py", 0o600)
    driver, _ = owned(root / "driver.sh", 0o600)
    allocator, _ = owned(root / "r16_allocator.py", 0o600)
    runner, _ = owned(root / "r16_allocator_runner.py", 0o600)
    old_controller, _ = owned(old_controller_path, 0o600, OLD_CONTROLLER_SHA)
    old_driver, _ = owned(old_driver_path, 0o600, OLD_DRIVER_SHA)
    old_allocator, _ = owned(old_allocator_path, 0o600, OLD_ALLOCATOR_SHA)
    old_runner, _ = owned(old_runner_path, 0o600, OLD_RUNNER_SHA)
    pin_match = re.search(rb'^SOURCE_PIN = "([0-9a-f]{40})"$', controller, re.MULTILINE)
    if pin_match is None or pin_match.group(1).decode() != expected_pin:
        raise RuntimeError("new source pin differs")
    restored_controller = one(controller, pin_match.group(0) + b"\n", f'SOURCE_PIN = "{OLD_PIN}"\n'.encode())
    if restored_controller != old_controller:
        raise RuntimeError("controller reversal differs")
    controller_sha = hashlib.sha256(controller).hexdigest()

    restored_driver = driver
    restored_driver = one(restored_driver, b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r16-adopt-patch.md', b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md')
    restored_driver = one(restored_driver, b'task-7-r16-followup-1-report.md', b'task-7-r14-followup-1-report.md')
    restored_driver = one(restored_driver, b'.superpowers/sdd/modeling-remediation/r16-evidence/final-retest-r3/attempt-0001', b'.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001', 2)
    restored_driver = one(restored_driver, controller_sha.encode(), OLD_CONTROLLER_SHA.encode())
    new_topology = f'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = {R15_COMMIT}\n  test "$(git -C "$FEATURE_ROOT" rev-parse {R15_COMMIT}^)" = deb5426a57748ae4e89e91afe0a1752e4c9fc2b0\n  test "$(git -C "$FEATURE_ROOT" rev-parse deb5426a57748ae4e89e91afe0a1752e4c9fc2b0^)" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'.encode()
    old_topology = b'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
    restored_driver = one(restored_driver, new_topology, old_topology)
    if restored_driver != old_driver:
        raise RuntimeError("driver reversal differs")

    restored_allocator = allocator
    restored_allocator = one(restored_allocator, f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode(), b'SOURCE_ID = (16777232, 305390856)')
    restored_allocator = one(restored_allocator, f'SOURCE_SHA256 = "{controller_sha}"'.encode(), f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode())
    restored_allocator = one(restored_allocator, b'PARTS = ("r16-evidence", "final-retest-r3", "attempt-0001")', b'PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")')
    if restored_allocator.count(b"R16") != 11:
        raise RuntimeError("allocator diagnostic count differs")
    restored_allocator = restored_allocator.replace(b"R16", b"R12")
    if restored_allocator != old_allocator:
        raise RuntimeError("allocator reversal differs")

    allocator_sha = hashlib.sha256(allocator).hexdigest()
    restored_runner = runner
    restored_runner = one(restored_runner, f'ALLOCATOR_SHA256 = "{allocator_sha}"'.encode(), f'ALLOCATOR_SHA256 = "{OLD_ALLOCATOR_SHA}"'.encode())
    restored_runner = one(restored_runner, f'SOURCE_CONTROLLER = Path("{root / "r3_controller.py"}")'.encode(), b'SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")')
    restored_runner = one(restored_runner, f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode(), b'SOURCE_ID = (16777232, 305390856)')
    restored_runner = one(restored_runner, f'SOURCE_SHA256 = "{controller_sha}"'.encode(), f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode())
    restored_runner = one(restored_runner, b'R16_ALLOCATION_GREEN', b'R12_ALLOCATION_GREEN')
    if restored_runner.count(b"R16") != 15:
        raise RuntimeError("runner diagnostic count differs")
    restored_runner = restored_runner.replace(b"R16", b"R14")
    if restored_runner != old_runner:
        raise RuntimeError("runner reversal differs")

    for raw, path in ((controller, root / "r3_controller.py"), (allocator, root / "r16_allocator.py"), (runner, root / "r16_allocator_runner.py")):
        compile(raw, str(path), "exec")
    ruff = subprocess.run(["/Users/yeminjie/.local/bin/uvx", "--quiet", "ruff@0.16.2", "check", "--no-cache", "--isolated", "--target-version", "py313", "--select", "E4,E7,E9,F", str(root / "r3_controller.py"), str(root / "r16_allocator.py"), str(root / "r16_allocator_runner.py")], text=True, capture_output=True, timeout=60)
    if ruff.returncode:
        raise RuntimeError(f"runtime Ruff failed: {ruff.stdout}{ruff.stderr}")
    probe = subprocess.run([sys.executable, str(root / "r3_controller.py"), "probe"], text=True, capture_output=True, timeout=30, env={**os.environ, "TMPDIR": "/private/tmp", "PYTHONDONTWRITEBYTECODE": "1"})
    if probe.returncode or probe.stdout.count("R3_FAILURE_DIAGNOSTICS_GREEN ") != 1 or probe.stdout.count("R3_PROTOCOL_R20_1_GREEN ") != 1:
        raise RuntimeError(f"controller probe failed: {probe.stdout}{probe.stderr}")
    subprocess.run(["/bin/bash", "-n", str(root / "driver.sh")], timeout=10, check=True)
    heredocs = re.findall(rb"<<'PY'\n(.*?)\nPY(?:\n|$)", driver, re.DOTALL)
    if len(heredocs) != 7:
        raise RuntimeError("driver heredoc count differs")
    for number, body in enumerate(heredocs, 1):
        compile(body, f"<r16-heredoc-{number}>", "exec")
    anchor = b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n'
    if driver.count(anchor) != 1:
        raise RuntimeError("driver run count differs")
    start = driver.index(anchor)
    command = driver[start:driver.index(b" || R3_RUN_EXIT=$?", start)]
    if b"<" in command:
        raise RuntimeError("driver stdin redirect differs")
    print("R16_RUNTIME_GATE_GREEN controller=1 driver=1 allocator_equivalent=1 runner_equivalent=1 probe=1 static=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B — exact direct R16 runtime builder

Extract this 154-line body without fences. Invoke once as specified in Task2. It is the exact R15 Appendix B algorithm with only the declared R16 literals and three-line topology.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path


OLD_PIN = "4309a39646e644261624bfcd2bca669b343b7621"
R15_COMMIT = "6e78a91d9c4fab6746262c88e7032e789a3bae1c"
OLD_CONTROLLER_SHA = "58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27"
OLD_DRIVER_SHA = "e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd"
OLD_ALLOCATOR_SHA = "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"
OLD_RUNNER_SHA = "a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9"


def read_owned(path: Path, size: int, digest: str) -> bytes:
    if Path(os.path.realpath(path)) != path:
        raise RuntimeError(f"noncanonical source: {path}")
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size != size:
        raise RuntimeError(f"unsafe source: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        raw = b""
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            raw += block
        after = os.fstat(fd)
    finally:
        os.close(fd)
    fields = lambda value: (value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode), value.st_nlink, value.st_size)
    if fields(info) != fields(opened) or fields(opened) != fields(after) or fields(os.lstat(path)) != fields(after) or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError(f"source differs: {path}")
    return raw


def replace(raw: bytes, old: bytes, new: bytes, count: int = 1) -> bytes:
    if old == new or raw.count(old) != count or raw.count(new) != 0:
        raise RuntimeError("replacement anchor differs")
    return raw.replace(old, new)


def create(root_fd: int, root: Path, root_fields: tuple[int, ...], created: list[tuple[str, int, int]], name: str, raw: bytes) -> tuple[Path, os.stat_result]:
    fields = lambda value: (value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode))
    if fields(os.fstat(root_fd)) != root_fields or fields(os.lstat(root)) != root_fields:
        raise RuntimeError("runtime root replaced")
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
    opened = os.fstat(fd)
    created.append((name, opened.st_dev, opened.st_ino))
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RuntimeError("short runtime write")
            view = view[written:]
        os.fsync(fd)
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size != len(raw):
            raise RuntimeError("runtime leaf differs")
    finally:
        os.close(fd)
    os.fsync(root_fd)
    path = root / name
    leaf = os.lstat(path)
    if (leaf.st_dev, leaf.st_ino) != (info.st_dev, info.st_ino) or fields(os.fstat(root_fd)) != root_fields or fields(os.lstat(root)) != root_fields:
        raise RuntimeError("runtime leaf replaced")
    return path, info


def main() -> int:
    if len(sys.argv) != 7:
        raise SystemExit("usage: builder.py SOURCE_PIN CONTROLLER DRIVER ALLOCATOR RUNNER OUTPUT_ROOT")
    pin = sys.argv[1]
    if re.fullmatch(r"[0-9a-f]{40}", pin) is None:
        raise RuntimeError("commit identity differs")
    controller_path, driver_path, allocator_path, runner_path, root = map(Path, sys.argv[2:])
    if Path(os.path.realpath(root)) != root:
        raise RuntimeError("noncanonical runtime root")
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700 or any(root.iterdir()):
        raise RuntimeError("unsafe runtime root")
    root_fields = (root_info.st_dev, root_info.st_ino, root_info.st_uid, stat.S_IMODE(root_info.st_mode))
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    if (lambda value: (value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode)))(os.fstat(root_fd)) != root_fields:
        os.close(root_fd)
        raise RuntimeError("runtime root identity differs")
    created: list[tuple[str, int, int]] = []
    try:
        controller_source = read_owned(controller_path, 285409, OLD_CONTROLLER_SHA)
        driver_source = read_owned(driver_path, 33823, OLD_DRIVER_SHA)
        allocator_source = read_owned(allocator_path, 5615, OLD_ALLOCATOR_SHA)
        runner_source = read_owned(runner_path, 6019, OLD_RUNNER_SHA)

        controller = replace(controller_source, f'SOURCE_PIN = "{OLD_PIN}"\n'.encode(), f'SOURCE_PIN = "{pin}"\n'.encode())
        controller_out, controller_info = create(root_fd, root, root_fields, created, "r3_controller.py", controller)
        controller_sha = hashlib.sha256(controller).hexdigest()

        driver = driver_source
        driver = replace(driver, b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md', b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r16-adopt-patch.md')
        driver = replace(driver, b'task-7-r14-followup-1-report.md', b'task-7-r16-followup-1-report.md')
        driver = replace(driver, b'.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001', b'.superpowers/sdd/modeling-remediation/r16-evidence/final-retest-r3/attempt-0001', 2)
        driver = replace(driver, OLD_CONTROLLER_SHA.encode(), controller_sha.encode())
        old_topology = b'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
        new_topology = f'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = {R15_COMMIT}\n  test "$(git -C "$FEATURE_ROOT" rev-parse {R15_COMMIT}^)" = deb5426a57748ae4e89e91afe0a1752e4c9fc2b0\n  test "$(git -C "$FEATURE_ROOT" rev-parse deb5426a57748ae4e89e91afe0a1752e4c9fc2b0^)" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'.encode()
        driver = replace(driver, old_topology, new_topology)
        create(root_fd, root, root_fields, created, "driver.sh", driver)

        allocator = allocator_source
        allocator = replace(allocator, b'SOURCE_ID = (16777232, 305390856)', f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode())
        allocator = replace(allocator, f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode(), f'SOURCE_SHA256 = "{controller_sha}"'.encode())
        allocator = replace(allocator, b'PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")', b'PARTS = ("r16-evidence", "final-retest-r3", "attempt-0001")')
        if allocator.count(b"R12") != 11:
            raise RuntimeError("allocator diagnostic anchors differ")
        allocator = allocator.replace(b"R12", b"R16")
        create(root_fd, root, root_fields, created, "r16_allocator.py", allocator)
        allocator_sha = hashlib.sha256(allocator).hexdigest()

        runner = runner_source
        runner = replace(runner, f'ALLOCATOR_SHA256 = "{OLD_ALLOCATOR_SHA}"'.encode(), f'ALLOCATOR_SHA256 = "{allocator_sha}"'.encode())
        old_source_path = b'SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")'
        runner = replace(runner, old_source_path, f'SOURCE_CONTROLLER = Path("{controller_out}")'.encode())
        runner = replace(runner, b'SOURCE_ID = (16777232, 305390856)', f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode())
        runner = replace(runner, f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode(), f'SOURCE_SHA256 = "{controller_sha}"'.encode())
        runner = replace(runner, b'R12_ALLOCATION_GREEN', b'R16_ALLOCATION_GREEN')
        if runner.count(b"R14") != 15:
            raise RuntimeError("runner diagnostic anchors differ")
        runner = runner.replace(b"R14", b"R16")
        create(root_fd, root, root_fields, created, "r16_allocator_runner.py", runner)

        print(f"R16_RUNTIME_GREEN source_pin={pin} controller_sha256={controller_sha} driver_sha256={hashlib.sha256(driver).hexdigest()} allocator_sha256={allocator_sha} runner_sha256={hashlib.sha256(runner).hexdigest()}")
        return 0
    except BaseException:
        for name, dev, ino in reversed(created):
            try:
                current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if (current.st_dev, current.st_ino) == (dev, ino):
                os.unlink(name, dir_fd=root_fd)
        os.fsync(root_fd)
        raise
    finally:
        os.close(root_fd)


if __name__ == "__main__":
    raise SystemExit(main())
````
