# Official Blender MCP R19 MCP-Dependency Recovery Plan

## Goal and frozen admission

Adopt the already-correct two-file R15 source postimage without writing it again, pin the two declared MCP dependency files once, run the tests once, commit exactly those four paths once, construct a fresh R19 runtime, and perform one fresh complete live retest.

- Main HEAD is R18 Plan commit `f37ea8271c217d1801349c6dd19b5b40612ce64e`, parent `e559ad0042ed3a862753e5a2aa51d4737bfca519`. R18 Task2 report is dev/inode `16777232/307553361`, mode 0600/nlink1, size 4,730, SHA-256 `29d5ab38799d6e1fd7d61689c40a33cb530fdf8bd5abf750d94384db20db8f04`, unique BLOCKED because the sole integration found the existing MCP environment missing `mcp.server.fastmcp`; integration/build/gate/actual counts are `1/0/0/0`. Its spec/quality/receipt inodes `307553362/307553363/307553364` are empty mode-0600/nlink1 files with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. R18 runtime/evidence/live paths are absent and immutable; R18 is never reopened or retried.
- Upstream `/Users/yeminjie/blender_mcp` is HEAD `4309a39646e644261624bfcd2bca669b343b7621`, empty index, no untracked files, and exactly two unstaged paths. Tool postimage is 127 lines / 4,103 bytes / SHA-256 `85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26`; test postimage is 1,158 lines / 43,710 bytes / SHA-256 `a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63`; binary diff SHA-256 is `a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248`.
- Exact committed predecessor is R18 Plan `docs/superpowers/plans/2026-08-15-official-blender-mcp-r18-ruff-scope.md`, 893/63,553/SHA `27fb90d6cbaade6df16e838595dacb803763e94f9667da065a09bfda2747b215`. Exact committed R15 dependencies remain Plan `docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md`, 958/60,281/SHA `76f4ba731c95fb873cdd9beaec02bdab0bb1e488781578f145b6eb1ddb310e7c`; Appendix A replacements; Appendix E 346/14,230/SHA `ef81d9f1237873a3f8059f12066bbaedd976d67873440b39a058441ab37f16f0`; and Appendix C 126/4,629/SHA `d4e75498888c6f3c598e4547755a2e024b5c57fb4e1d4cbde1595359796ecbc0`.
- Exact base runtime inputs are R11 controller 285,409/SHA `58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27`; R14 driver 33,823/SHA `e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd`; R12 Plan Appendix B allocator 115/5,615/SHA `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`; R14 Plan Appendix C runner 115/6,019/SHA `a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9`.

## Fresh paths

- Task2 files are `.superpowers/sdd/modeling-remediation/r19-task2-report.md`, `.superpowers/sdd/modeling-remediation/r19-task2-spec-review.md`, `.superpowers/sdd/modeling-remediation/r19-task2-quality-review.md`, and `.superpowers/sdd/modeling-remediation/r19-task2-terminal-receipt.md`.
- Runtime is native-0700 `.superpowers/sdd/modeling-remediation/r19-live-runtime` with exactly `.superpowers/sdd/modeling-remediation/r19-live-runtime/r3_controller.py`, `.superpowers/sdd/modeling-remediation/r19-live-runtime/driver.sh`, `.superpowers/sdd/modeling-remediation/r19-live-runtime/r19_allocator.py`, and `.superpowers/sdd/modeling-remediation/r19-live-runtime/r19_allocator_runner.py`.
- Live paths are `.superpowers/sdd/modeling-remediation/r19-evidence/final-retest-r3/attempt-0001`, `.superpowers/sdd/modeling-remediation/task-7-r19-followup-1-brief.md`, `.superpowers/sdd/modeling-remediation/task-7-r19-followup-1-report.md`, `.superpowers/sdd/modeling-remediation/task-7-r19-followup-1-failure-review.md`, and `.superpowers/sdd/modeling-remediation/task-7-r19-followup-1-success-review.md`. Every path is absent at allocation; `.superpowers/sdd/modeling-remediation/r19-evidence/final-retest-r3/attempt-0002` is always forbidden.

## Task 1 — certify this Plan only

- Exact Appendix identities are A `101/5,521/b798a74621e7899fd50b5449f6516e8e3ef8f441336f297cfaf3106ef6c2477c`; B `154/9,285/2feef8fd253e0e65efad374e9bba3b8f0fe942af5134ab5874abd69659e5cb2f`; C `385/25,680/f6f395f361d5b95dff871004cb04234a9d14e6ce66ee1b5f8fe2813ab4837207`; D `135/9,378/0e96c26e8d1af90adcad09874c38f4821662e06f1ad332f0f0ebbbd39994ed10`; E `183/11,068/022559f2bb9a355657872c63fada950d9c94a54b01ad4be7093e39ded4fdbb34`; F `83/3,554/f410e5a3bf07824af2495f6a51d43f43903014e582393f5aad31ab4483b6a23c`.
- Extract Appendices A/B/C/D/E/F exactly, require their declared identities, and run Appendix E once in a disposable native-0700 `/private/tmp` root; Appendix E owns the sole compile pass. It statically rejects the old two-path Ruff argv, binds the frozen-import/Python-3.14 syntax gate, invokes Appendix A in `dirty` mode, exercises Appendix F only on disposable copies including successful apply, same-inode drift RED, path-replacement preservation RED, and injected second-write BLOCKED without rollback, binds the exact R18 missing-module report and an offline uv-cache MCP 1.28.1/FastMCP import, runs exact R15 E `--selfcheck`, builds with a synthetic non-parent 40-hex pin, gates under canonical Python 3.13, and requires one `R19_PLAN_HARNESS_GREEN adoption=1 dependency=1 dependency_drift_red=1 dependency_replacement_red=1 dependency_partial_blocked=1 mcp_contract=1 primitives=1 builder=1 gate=1 static=1 ruff_scope=1 syntax=1`. It does not invoke Appendix C owner, real integration, the production allocator/runner/driver, Blender, or either source test.
- Three fresh reviewers audit one frozen Plan SHA for spec/safety, execution/state, and Ponytail/YAGNI. Their final files must each contain unique exact `CRITICAL: 0`, `IMPORTANT: 0`, and `MINOR: 0`; their respective unique final lines are `SPEC_VERDICT: PASS`, `EXECUTION_VERDICT: PASS`, and `PONYTAIL_VERDICT: PASS`. Any finding including Minor requires a fresh frozen round. Commit only this Plan with parent `f37ea8271c217d1801349c6dd19b5b40612ce64e`; record the Plan commit/SHA and each final review's canonical path plus exact dev/inode/size/SHA for the Appendix-C arguments and Task3 admission. Earlier FAIL reports are never eligible.

## Task 2 — one persistent original-FD execution

- Extract exact committed R15 Appendix E by heading/fence from the exact R15 Plan and load it with `__name__ != "__main__"`; no selfcheck runs. Its `allocate`, `write_all`, `parse_approval`, `freeze`, `terminal`, `prepare_receipt`, `commit_receipt`, and `run_integration` are the only FD/integration primitives.
- Start one persistent owner before any test or source/index write. After only the minimal committed-R15-Plan/Appendix-E bootstrap, it O_EXCL-allocates the four Task2 files with R15 E and retains all original CLOEXEC FDs. Allocation collision is the sole permitted external/no-ledger failure. Inside the terminalizing `try`, it first writes/fsyncs the allocation/count prefix; only then may it perform any remaining admission, create temporary storage, or mutate source/index. Every such exception terminalizes BLOCKED once through the retained original report FD. Appendix A `dirty` is the first source gate; Appendix A is read-only and Appendix A from R15 is never invoked.
- After original-FD admission and initial Appendix A `dirty`, invoke exact Appendix F once in `apply` mode with the frozen dependency identities `16777232:211193900` and `16777232:211193901`. Appendix F opens and retains both source FDs before validation, validates both FDs and paths against their exact owned preimages before either write, writes the complete +1-byte postimages through those original FDs, and postvalidates both FDs and paths. It has no reverse/rollback mode: any failure is terminal BLOCKED with the observed state retained, and no foreign replacement is touched. Require four exact unstaged paths and combined binary-diff SHA `1fa15dbe10ca8697de03b9371dccb414c406114d52d1c1e00801884ce7746a8f`. Bind canonical `/Users/yeminjie/.local/bin/uv` through a read-only FD and its exact identity/hash, then invoke it exactly once as `uv pip install --python /Users/yeminjie/blender_mcp/mcp/.venv/bin/python mcp[cli]==1.28.1`; do not run a separate version command, sync, lock, or update any other environment. Bind the venv Python symlink to canonical Python 3.14, the canonical `blender-mcp` entrypoint identity after install, exact distribution version 1.28.1, and successful `from mcp.server.fastmcp import FastMCP` before and after integration.
- Run pinned Ruff `0.16.2` only on the exact tool postimage. The test's line-54 `from tests.mcp_client import MCPClient` is byte-identical to the frozen `4309...` preimage and lies outside the replaced thumbnail-test method; do not add an ignore, configuration, or source edit for that inherited E402. Instead run one static syntax gate under canonical Python 3.14 using `compile(Path(TEST).read_bytes(), TEST, "exec")` and require unique `R19_TEST_SYNTAX_GREEN`. Then run exact R15 Appendix C once with canonical Python 3.14 and the canonical tool path; require unique `R15_DEFERRED_RESTORE_GREEN cases=3`.
- Exact integration argv is `/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14 /Users/yeminjie/blender_mcp/tests/test_blender_mcp_with_blender.py TestBackgroundServer.test_render_thumbnail_to_path TestInteractiveServer.test_render_thumbnail_to_path`. The Python identity is dev/inode `16777232/211200476`, native 0755/nlink1, size 18,817,184, SHA `1ba16b38d45f006e449bb51a923dae83f3c384611bcd4ee428afd044b7ed4c95`. Environment is exactly `PATH=/usr/bin:/bin:/usr/sbin:/sbin:/Users/yeminjie/.local/bin`, invoking `HOME`, `BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender`, `BLENDER_MCP=/Users/yeminjie/blender_mcp/mcp/.venv/bin/blender-mcp`, `BLENDER_MCP_FOREGROUND=1`; R15 E owns one subprocess/process group and cleanup. Require rc0, exactly `Ran 2 tests`, `OK`, and ports 9876/9877/9878 empty.
- Stage only the four paths, invoke Appendix A `staged`, and commit once with parent `4309a396...`. The owner then directly and uniquely requires one parent, exactly the four declared changed paths/blobs/diff, clean index/worktree/untracked state, and records `R19_SOURCE_PIN`; Appendix A has no postcommit mode. No amend/reset/rebase/second commit or further source write.
- Allocate/retain the native-0700 runtime parent FD. Extract exact R12 allocator and R14 runner into private native-0600 files. Invoke exact Appendix B once under canonical Python 3.13 as `builder.py R19_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER RUNTIME_ROOT`; require one `R19_RUNTIME_GREEN`. Invoke exact Appendix D once under the same canonical Python as `runtime_gate.py RUNTIME_ROOT R19_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER`; require one `R19_RUNTIME_GATE_GREEN`. Python 3.13 is `/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13`, dev/inode `16777232/259766870`, 0755/nlink1, size 17,439,616, SHA `7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683`.
- Stop nonterminal after recording source/runtime/environment identities and counts `patch=0 dependency_patch=1 uv_install=1 integration=1 builder=1 gate=1`; retain the four FDs and persistent process. Two fresh reviewers write only the preallocated review paths and uniquely end `SPEC_REVIEW: APPROVED` and `QUALITY_REVIEW: APPROVED`.
- On the sole exact `FINALIZE_REVIEWS` token, parse both reports through retained FDs, freeze/close them, prepare the receipt, append/freeze unique Task2 PASS, then descriptor-only commit receipt to mode 0400. Every exception before a terminal calls BLOCKED exactly once and leaves receipt mode 0600; a terminal exception is `UNVERIFIED_TERMINAL`, and a missing/malformed/non-0400 receipt is `PASS_WITHOUT_RECEIPT`. In either case close every remaining FD in `finally`, never reopen/write a terminal path, and never retry. Appendix C below is the exact owner state machine; its one-shot process is mandatory.

## Task 3 — sole fresh live run

- Admission binds: R19 Plan commit/SHA and exact final three Plan-review identities/zero findings; upstream parent `4309...`, exact `R19_SOURCE_PIN`, exact four-file tree and clean status; R19 Task2 report unique PASS, both Task2 approvals, matching preallocated receipt inode/content native 0400/nlink1; exact runtime parent/four leaves; frozen R18 BLOCKED/empty files/absences; all fresh live absences; empty ports/process inventory. It reopens the current MCP environment read-only and requires the venv Python symlink still resolves to the exact canonical Python 3.14 identity, the `blender-mcp` entrypoint identity exactly matches the Task2 record, distribution metadata is exactly `mcp==1.28.1`, and `from mcp.server.fastmcp import FastMCP` succeeds; every fact must equal the Task2 report before any GUI, runner, listener, ticket, or PTY action. It also binds immutable driver-input `.superpowers/sdd/modeling-remediation/task-7-brief.md` as dev/inode `16777232/295274948`, uid 501, mode 0600, nlink1, size 538,571, SHA `fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b`, exactly matching the unchanged R14/R19 driver constants.
- After that exact R19 admission, inherit the committed R18 Task3 transitions verbatim, substituting only R18 Plan/review/Task2/source/runtime/live namespaces and markers with the bound R19 values. This includes report-first original-FD fallback, one fresh GUI preflight and action-time Online Access confirmation, raw `bpy.app.tempdir`, exact R10 scratch checker once, exact R19 runner once, retained evidence/controller FDs, exact ten-argument R19 driver once in one PTY with FD8, at most one ticket/actual run, and cleanup on every terminal. The ten arguments retain the exact R18 order; no argument is reconstructed from prose.
- `.superpowers/sdd/modeling-remediation/task-7-r19-followup-1-brief.md` is a fresh root-only GUI/scratch/admission/review record and is never presented as driver input. The unchanged driver intentionally consumes only the separately bound immutable `.superpowers/sdd/modeling-remediation/task-7-brief.md`; Task3 binds both artifacts and never substitutes or confuses their roles.
- Display every fresh R19 PNG in manifest order, collect one explicit verdict per image, and send exactly one canonical ordered Option-C ACK. No predecessor image/verdict/ACK, scratch, ticket, listener, PTY, attempt, or report is reusable.

## Task 4 — terminal review and audit

- Failure is fail-closed and cannot be promoted. Success requires fresh root checks, manifest/package, independent success review, exact cleanup, and then the audit file as the sole new commit.
- Successful first-parent/path-array history has exact length 18: runbook, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, audit; parents are old-R3, runbook, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19.

## Appendix A — exact read-only adoption checker

Extract this body without fences. Invoke only as `adoption.py dirty` before tests, `adoption.py patched` after Appendix F, and `adoption.py staged` after staging. It never writes and has no postcommit mode.

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
PYPROJECT = "mcp/pyproject.toml"
REQUIREMENTS = "mcp/requirements.txt"
TEST = "tests/test_blender_mcp_with_blender.py"
TOOL_SHA = "85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26"
TEST_SHA = "a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63"
PYPROJECT_OLD_SHA = "c8c61de7677e20c8e2de79865e13252ccd8f6671dbcb8e77203bf15cd4c8b34a"
REQUIREMENTS_OLD_SHA = "c54fe57211ec3a062a0c5c842cb31a8c11d526ec9a9afb5bad175c0c335a32c5"
PYPROJECT_NEW_SHA = "bc9a4c73f171482d167addb5dc82bb6c318b256ea8df72851b10b1316bb7ba51"
REQUIREMENTS_NEW_SHA = "fe501e209528878d9074701735eb3ccd2ac3cdc78b8be9275a19a2db4d1b21ed"
DIRTY_DIFF_SHA = "a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248"
PATCHED_DIFF_SHA = "1fa15dbe10ca8697de03b9371dccb414c406114d52d1c1e00801884ce7746a8f"


def git(*args: str) -> bytes:
    return subprocess.check_output(["/usr/bin/git", "-C", str(ROOT), *args])


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def postimages() -> dict[str, bytes]:
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
    tool = tool_old[:start] + tool_replacement + tool_old[end:]
    test_old = git("show", f"{PIN}:{TEST}")
    start = test_old.index(b"    def test_render_thumbnail_to_path(self) -> None:\n")
    end = test_old.index(b"\n\n    def ", start) + 1
    test = test_old[:start] + test_replacement + test_old[end:]
    pyproject_old = git("show", f"{PIN}:{PYPROJECT}")
    requirements_old = git("show", f"{PIN}:{REQUIREMENTS}")
    if (len(tool), sha(tool), len(test), sha(test), len(pyproject_old), sha(pyproject_old), len(requirements_old), sha(requirements_old)) != (4103, TOOL_SHA, 43710, TEST_SHA, 1724, PYPROJECT_OLD_SHA, 192, REQUIREMENTS_OLD_SHA):
        raise RuntimeError("reconstructed pre/postimages differ")
    if pyproject_old.count(b"mcp[cli]>=1.2.0") != 1 or requirements_old.count(b"mcp[cli]>=1.2.0") != 1:
        raise RuntimeError("dependency anchors differ")
    pyproject = pyproject_old.replace(b"mcp[cli]>=1.2.0", b"mcp[cli]==1.28.1")
    requirements = requirements_old.replace(b"mcp[cli]>=1.2.0", b"mcp[cli]==1.28.1")
    if (len(pyproject), sha(pyproject), len(requirements), sha(requirements)) != (1725, PYPROJECT_NEW_SHA, 193, REQUIREMENTS_NEW_SHA):
        raise RuntimeError("dependency postimages differ")
    return {TOOL: tool, PYPROJECT: pyproject, REQUIREMENTS: requirements, TEST: test}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"dirty", "patched", "staged"}:
        raise SystemExit("usage: adoption.py dirty|patched|staged")
    mode = sys.argv[1]
    expected = postimages()
    current = {path: (ROOT / path).read_bytes() for path in expected}
    if mode == "dirty":
        expected[PYPROJECT] = git("show", f"{PIN}:{PYPROJECT}")
        expected[REQUIREMENTS] = git("show", f"{PIN}:{REQUIREMENTS}")
    if current != expected or git("ls-files", "--others", "--exclude-standard"):
        raise RuntimeError("current source postimages differ")
    paths = [TOOL, PYPROJECT, REQUIREMENTS, TEST]
    if git("rev-parse", "HEAD").decode().strip() != PIN:
        raise RuntimeError("source parent differs")
    if mode == "dirty":
        if git("diff", "--cached", "--binary") or sha(git("diff", "--binary")) != DIRTY_DIFF_SHA:
            raise RuntimeError("dirty diff differs")
        status = f" M {TOOL}\n M {TEST}\n".encode()
    elif mode == "patched":
        if git("diff", "--cached", "--binary") or sha(git("diff", "--binary")) != PATCHED_DIFF_SHA:
            raise RuntimeError("patched diff differs")
        status = "".join(f" M {path}\n" for path in paths).encode()
    else:
        if git("diff", "--binary") or sha(git("diff", "--cached", "--binary")) != PATCHED_DIFF_SHA or git("diff", "--cached", "--name-only").decode().splitlines() != paths:
            raise RuntimeError("staged diff differs")
        status = "".join(f"M  {path}\n" for path in paths).encode()
    if git("status", "--porcelain=v1") != status:
        raise RuntimeError("source status differs")
    print(f"R19_ADOPTION_GREEN mode={mode} files=4 diff=1 index=1 untracked=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix F — exact two-file dependency patch

Invoke once in Task2 as `dependency_patch.py apply /Users/yeminjie/blender_mcp/mcp/pyproject.toml 16777232:211193900 /Users/yeminjie/blender_mcp/mcp/requirements.txt 16777232:211193901`. It opens both leaves read-write without following links and retains both FDs, validates both complete preimages before either write, writes the complete +1-byte postimages through those FDs, and validates both complete postimages and path identities. There is no reverse or rollback mode; a failure preserves the observed owned/foreign state for the terminal report.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path
from typing import Callable


OLD = b"mcp[cli]>=1.2.0"
NEW = b"mcp[cli]==1.28.1"
SPECS: dict[str, tuple[int, str, int, str]] = {
    "pyproject.toml": (1724, "c8c61de7677e20c8e2de79865e13252ccd8f6671dbcb8e77203bf15cd4c8b34a", 1725, "bc9a4c73f171482d167addb5dc82bb6c318b256ea8df72851b10b1316bb7ba51"),
    "requirements.txt": (192, "c54fe57211ec3a062a0c5c842cb31a8c11d526ec9a9afb5bad175c0c335a32c5", 193, "fe501e209528878d9074701735eb3ccd2ac3cdc78b8be9275a19a2db4d1b21ed"),
}


def identity(raw: str) -> tuple[int, int]:
    if re.fullmatch(r"[0-9]+:[0-9]+", raw) is None:
        raise RuntimeError("dependency identity syntax differs")
    return tuple(map(int, raw.split(":")))  # type: ignore[return-value]


def fields(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode), value.st_nlink, value.st_size


def validate(fd: int, path: Path, expected_id: tuple[int, int], size: int, digest: str) -> bytes:
    opened = os.fstat(fd)
    current = os.lstat(path)
    expected = (*expected_id, os.getuid(), 0o644, 1, size)
    if not stat.S_ISREG(opened.st_mode) or fields(opened) != expected or fields(current) != expected:
        raise RuntimeError(f"dependency identity differs: {path}")
    raw = os.pread(fd, size + 1, 0)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError(f"dependency content differs: {path}")
    return raw


def apply(paths: list[Path], expected_ids: list[tuple[int, int]], writer: Callable[[int, bytes | memoryview, int], int] = os.pwrite) -> None:
    if [path.name for path in paths] != ["pyproject.toml", "requirements.txt"] or len(expected_ids) != 2:
        raise RuntimeError("dependency inputs differ")
    if any(Path(os.path.realpath(path)) != path for path in paths):
        raise RuntimeError("noncanonical dependency path")
    fds: list[int] = []
    try:
        for path in paths:
            fds.append(os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC))
        replacements: list[bytes] = []
        for fd, path, expected_id in zip(fds, paths, expected_ids):
            old_size, old_sha, _, _ = SPECS[path.name]
            raw = validate(fd, path, expected_id, old_size, old_sha)
            replacements.append(raw.replace(OLD, NEW))
        for fd, replacement in zip(fds, replacements):
            offset = 0
            while offset < len(replacement):
                count = writer(fd, memoryview(replacement)[offset:], offset)
                if count <= 0:
                    raise RuntimeError("short dependency write")
                offset += count
            os.ftruncate(fd, len(replacement))
            os.fsync(fd)
        for fd, path, expected_id in zip(fds, paths, expected_ids):
            _, _, new_size, new_sha = SPECS[path.name]
            validate(fd, path, expected_id, new_size, new_sha)
    finally:
        for fd in fds:
            os.close(fd)


def main() -> int:
    if len(sys.argv) != 6 or sys.argv[1] != "apply":
        raise SystemExit("usage: dependency_patch.py apply PYPROJECT PYPROJECT_DEV:INO REQUIREMENTS REQUIREMENTS_DEV:INO")
    paths = [Path(sys.argv[2]), Path(sys.argv[4])]
    apply(paths, [identity(sys.argv[3]), identity(sys.argv[5])])
    print("R19_DEPENDENCY_PATCH_GREEN mode=apply files=2 descriptor_bound=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix E — exact offline Plan harness

Extract once and invoke as `plan_harness.py ADOPTION BUILDER OWNER GATE DEPENDENCY_PATCH`. It creates only disposable private files, runs Appendix A only in current `dirty` mode, exercises F success and three exact failure states on copies, checks the frozen failure and cached replacement import contracts, and runs B then D with one synthetic pin. It never invokes the owner, real integration, production allocator/runner/driver, Blender, or source tests.

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
SOURCE = Path("/Users/yeminjie/blender_mcp")
PY313 = "/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13"
PY314 = "/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14"
UV = "/Users/yeminjie/.local/bin/uv"
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


def red(argv: list[str]) -> None:
    done = subprocess.run(argv, text=True, capture_output=True, timeout=120)
    if done.returncode == 0 or "R19_DEPENDENCY_PATCH_GREEN" in done.stdout + done.stderr:
        raise RuntimeError(f"offline negative was not RED: {argv!r}")


def pair(root: Path, name: str, pyproject_raw: bytes, requirements_raw: bytes) -> tuple[Path, Path]:
    target = root / name
    os.mkdir(target, 0o700)
    paths = target / "pyproject.toml", target / "requirements.txt"
    for path, raw in zip(paths, (pyproject_raw, requirements_raw)):
        path.write_bytes(raw)
        os.chmod(path, 0o644)
    return paths


def idarg(path: Path) -> str:
    info = os.lstat(path)
    return f"{info.st_dev}:{info.st_ino}"


def main() -> int:
    if len(sys.argv) != 6:
        raise SystemExit("usage: plan_harness.py ADOPTION BUILDER OWNER GATE DEPENDENCY_PATCH")
    print("R19_PLAN_HARNESS_BEGIN", flush=True)
    adoption, builder, owner, gate, dependency_patch = map(Path, sys.argv[1:])
    expected = {
        adoption: (101, 5521, "b798a74621e7899fd50b5449f6516e8e3ef8f441336f297cfaf3106ef6c2477c"),
        builder: (154, 9285, "2feef8fd253e0e65efad374e9bba3b8f0fe942af5134ab5874abd69659e5cb2f"),
        gate: (135, 9378, "0e96c26e8d1af90adcad09874c38f4821662e06f1ad332f0f0ebbbd39994ed10"),
        owner: (385, 25680, "f6f395f361d5b95dff871004cb04234a9d14e6ce66ee1b5f8fe2813ab4837207"),
        dependency_patch: (83, 3554, "f410e5a3bf07824af2495f6a51d43f43903014e582393f5aad31ab4483b6a23c"),
    }
    checked = {}
    for path, (lines, size, digest) in expected.items():
        raw = path.read_bytes()
        compile(raw, str(path), "exec")
        if raw.count(b"\n") != lines or len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError(f"R19 appendix differs: {path}")
        checked[path] = raw
    owner_raw = checked[owner]
    if owner_raw.count(b"str(SOURCE / TOOL), str(SOURCE / TEST)") != 0 or owner_raw.count(b'"E4,E7,E9,F", str(SOURCE / TOOL)]') != 1 or owner_raw.count(b"frozen_import = b\"from tests.mcp_client import MCPClient\"") != 1 or owner_raw.count(b"R19_TEST_SYNTAX_GREEN") != 2 or owner_raw.count(b'[UV, "--version"]') != 0 or owner_raw.count(b'"R19_DEPENDENCY_PATCH_GREEN mode=apply files=2 descriptor_bound=1"') != 1 or owner_raw.count(b'"postcommit"') != 0:
        raise RuntimeError("R19 Ruff/syntax owner anchors differ")
    run([PY313, str(adoption), "dirty"], "R19_ADOPTION_GREEN mode=dirty ")
    tmp = Path(tempfile.mkdtemp(prefix="r19-plan-", dir="/private/tmp"))
    os.chmod(tmp, 0o700)
    root_fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        r12 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"76e9ac3fb38a3b630e8fe150b6043ea6cd08d0f8:{R12}"])
        r14 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"deb5426a57748ae4e89e91afe0a1752e4c9fc2b0:{R14}"])
        r15 = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"6e78a91d9c4fab6746262c88e7032e789a3bae1c:{R15}"])
        allocator = write(root_fd, tmp, "allocator.py", appendix(r12, b"## Appendix B:", 115, 5615, "0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c"))
        runner = write(root_fd, tmp, "runner.py", appendix(r14, b"## Appendix C:", 115, 6019, "a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9"))
        primitives = write(root_fd, tmp, "primitives.py", appendix(r15, b"## Appendix E ", 346, 14230, "ef81d9f1237873a3f8059f12066bbaedd976d67873440b39a058441ab37f16f0"))
        pyproject_raw = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", "4309a39646e644261624bfcd2bca669b343b7621:mcp/pyproject.toml"])
        requirements_raw = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", "4309a39646e644261624bfcd2bca669b343b7621:mcp/requirements.txt"])
        success = pair(tmp, "dependency-success", pyproject_raw, requirements_raw)
        run([PY313, str(dependency_patch), "apply", str(success[0]), idarg(success[0]), str(success[1]), idarg(success[1])], "R19_DEPENDENCY_PATCH_GREEN mode=apply files=2 descriptor_bound=1")

        drift = pair(tmp, "dependency-drift", pyproject_raw, requirements_raw)
        drift_ids = idarg(drift[0]), idarg(drift[1])
        drifted = pyproject_raw.replace(b"mcp[cli]>=1.2.0", b"mcp[cli]>=1.2.1")
        drift[0].write_bytes(drifted)
        red([PY313, str(dependency_patch), "apply", str(drift[0]), drift_ids[0], str(drift[1]), drift_ids[1]])
        if drift[0].read_bytes() != drifted or drift[1].read_bytes() != requirements_raw:
            raise RuntimeError("same-inode drift RED changed a dependency")

        dependency_ns: dict[str, object] = {"__name__": "r19_dependency_patch"}
        exec(compile(checked[dependency_patch], str(dependency_patch), "exec"), dependency_ns)
        replacement = pair(tmp, "dependency-replacement", pyproject_raw, requirements_raw)
        replacement_ids = [(os.lstat(path).st_dev, os.lstat(path).st_ino) for path in replacement]
        held = replacement[1].with_name("requirements-original.txt")
        swapped = False
        def replace_path(fd: int, raw: bytes | memoryview, offset: int) -> int:
            nonlocal swapped
            if not swapped:
                os.replace(replacement[1], held)
                replacement[1].write_bytes(requirements_raw)
                os.chmod(replacement[1], 0o644)
                swapped = True
            return os.pwrite(fd, raw, offset)
        try:
            dependency_ns["apply"](list(replacement), replacement_ids, replace_path)  # type: ignore[operator]
        except RuntimeError as error:
            if "dependency identity differs" not in str(error):
                raise
        else:
            raise RuntimeError("path replacement was not RED")
        if replacement[1].read_bytes() != requirements_raw or hashlib.sha256(held.read_bytes()).hexdigest() != "fe501e209528878d9074701735eb3ccd2ac3cdc78b8be9275a19a2db4d1b21ed":
            raise RuntimeError("path replacement RED touched foreign content or lost owned output")

        partial = pair(tmp, "dependency-partial", pyproject_raw, requirements_raw)
        partial_ids = [(os.lstat(path).st_dev, os.lstat(path).st_ino) for path in partial]
        first_fd: int | None = None
        def fail_second(fd: int, raw: bytes | memoryview, offset: int) -> int:
            nonlocal first_fd
            if first_fd is None:
                first_fd = fd
            if fd != first_fd:
                raise OSError("injected second dependency failure")
            return os.pwrite(fd, raw, offset)
        try:
            dependency_ns["apply"](list(partial), partial_ids, fail_second)  # type: ignore[operator]
        except OSError as error:
            if str(error) != "injected second dependency failure":
                raise
        else:
            raise RuntimeError("partial second dependency failure was not BLOCKED")
        if hashlib.sha256(partial[0].read_bytes()).hexdigest() != "bc9a4c73f171482d167addb5dc82bb6c318b256ea8df72851b10b1316bb7ba51" or partial[1].read_bytes() != requirements_raw:
            raise RuntimeError("partial second failure state differs")
        r18_report = (MAIN / ".superpowers/sdd/modeling-remediation/r18-task2-report.md").read_bytes()
        if hashlib.sha256(r18_report).hexdigest() != "29d5ab38799d6e1fd7d61689c40a33cb530fdf8bd5abf750d94384db20db8f04" or r18_report.count(b"ModuleNotFoundError: No module named 'mcp.server.fastmcp'") != 2:
            raise RuntimeError("R18 MCP2 failure contract differs")
        run([UV, "run", "--offline", "--no-project", "--python", PY314, "--with", "mcp[cli]==1.28.1", "python", "-c", "import importlib.metadata as m; from mcp.server.fastmcp import FastMCP; assert m.version('mcp') == '1.28.1'; print('R19_MCP_CACHE_GREEN version=1.28.1 fastmcp=1')"], "R19_MCP_CACHE_GREEN version=1.28.1 fastmcp=1")
        selfcheck = tmp / "selfcheck"
        os.mkdir(selfcheck, 0o700)
        run([PY313, str(primitives), "--selfcheck", str(selfcheck)], "R15_TASK2_PRIMITIVES_GREEN fd=1 parser=1 terminal=1 process_group=1")
        runtime = tmp / "runtime"
        os.mkdir(runtime, 0o700)
        old_controller = MAIN / ".superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py"
        old_driver = MAIN / ".superpowers/sdd/modeling-remediation/r14-live-runtime/driver.sh"
        run([PY313, str(builder), SYNTHETIC_PIN, str(old_controller), str(old_driver), str(allocator), str(runner), str(runtime)], "R19_RUNTIME_GREEN ")
        run([PY313, str(gate), str(runtime), SYNTHETIC_PIN, str(old_controller), str(old_driver), str(allocator), str(runner)], "R19_RUNTIME_GATE_GREEN ")
    finally:
        os.close(root_fd)
        shutil.rmtree(tmp)
    print("R19_PLAN_HARNESS_GREEN adoption=1 dependency=1 dependency_drift_red=1 dependency_replacement_red=1 dependency_partial_blocked=1 mcp_contract=1 primitives=1 builder=1 gate=1 static=1 ruff_scope=1 syntax=1", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix C — exact persistent Task2 owner

Extract once to private native-0700 storage. Invoke once as `task2_owner.py PLAN_COMMIT PLAN_SHA OWNER_SIZE OWNER_SHA PLAN_SPEC_REVIEW SPEC_DEV:SPEC_INO:SPEC_SIZE:SPEC_SHA PLAN_EXEC_REVIEW EXEC_DEV:EXEC_INO:EXEC_SIZE:EXEC_SHA PLAN_PONY_REVIEW PONY_DEV:PONY_INO:PONY_SIZE:PONY_SHA ADOPTION BUILDER GATE DEPENDENCY_PATCH`. All file paths are canonical absolute paths; sizes, hashes, and review identities are the exact final Task1 records. After its unique phase-1 marker, send no stdin until both fresh Task2 reviews are frozen; then send exactly `FINALIZE_REVIEWS` and one newline.

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
PLAN_REL = Path("docs/superpowers/plans/2026-08-15-official-blender-mcp-r19-mcp-dependency.md")
R18_REL = Path("docs/superpowers/plans/2026-08-15-official-blender-mcp-r18-ruff-scope.md")
R15_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md")
R12_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r12-dirfd-allocation.md")
R14_REL = Path("docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md")
R18 = "f37ea8271c217d1801349c6dd19b5b40612ce64e"
R15 = "6e78a91d9c4fab6746262c88e7032e789a3bae1c"
SOURCE_PARENT = "4309a39646e644261624bfcd2bca669b343b7621"
PY313 = "/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13"
PY314 = "/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14"
TOOL = "mcp/blmcp/tools/render_thumbnail_to_path_toolcode.py"
PYPROJECT = "mcp/pyproject.toml"
REQUIREMENTS = "mcp/requirements.txt"
TEST = "tests/test_blender_mcp_with_blender.py"
UV = "/Users/yeminjie/.local/bin/uv"
VENV_PY = "/Users/yeminjie/blender_mcp/mcp/.venv/bin/python"
VENV_EXE = "/Users/yeminjie/blender_mcp/mcp/.venv/bin/blender-mcp"


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

    report = MODELING / "r19-task2-report.md"
    spec = MODELING / "r19-task2-spec-review.md"
    quality = MODELING / "r19-task2-quality-review.md"
    receipt = MODELING / "r19-task2-terminal-receipt.md"
    runtime = MODELING / "r19-live-runtime"
    fds: dict[str, int] = {}
    ids: dict[str, tuple[int, ...]] = {}
    terminal_done = False
    receipt_committed = False
    dependency_patch_count = 0
    uv_install_count = 0
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
            "".join(f"r19_task2_{name}_allocated: {identity!r}\n" for name, identity in ids.items())
            + "r19_patch_apply_count: 0\ninitial_dependency_patch_run_count: 0\ninitial_uv_install_run_count: 0\ninitial_source_integration_run_count: 0\ninitial_runtime_builder_run_count: 0\ninitial_runtime_gate_run_count: 0\n"
        ).encode()
        write_all(fds["report"], allocation_prefix)
        os.fsync(fds["report"])

        if len(sys.argv) != 15:
            raise RuntimeError("Task2 owner argv differs")
        plan_commit, plan_sha, owner_size_raw, owner_sha = sys.argv[1:5]
        review_paths = [Path(sys.argv[index]) for index in (5, 7, 9)]
        review_ids = [expected_identity(sys.argv[index]) for index in (6, 8, 10)]
        adoption, builder, gate, dependency_patch = [Path(value) for value in sys.argv[11:15]]
        if re.fullmatch(r"[0-9a-f]{40}", plan_commit) is None or re.fullmatch(r"[0-9a-f]{64}", plan_sha) is None or not owner_size_raw.isdigit() or re.fullmatch(r"[0-9a-f]{64}", owner_sha) is None:
            raise RuntimeError("Plan identity syntax differs")
        if sh(MAIN, "/usr/bin/git", "rev-parse", "HEAD").stdout.strip() != plan_commit or sh(MAIN, "/usr/bin/git", "rev-list", "--parents", "-n", "1", "HEAD").stdout.split() != [plan_commit, R18]:
            raise RuntimeError("Plan topology differs")
        committed_plan = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"HEAD:{PLAN_REL}"])
        if hashlib.sha256(committed_plan).hexdigest() != plan_sha or (MAIN / PLAN_REL).read_bytes() != committed_plan or sh(MAIN, "/usr/bin/git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines() != [str(PLAN_REL)] or sh(MAIN, "/usr/bin/git", "status", "--porcelain=v1").stdout:
            raise RuntimeError("Plan commit differs")
        plan_reviews = [approved_review(path, identity, verdict) for path, identity, verdict in zip(review_paths, review_ids, ("SPEC_VERDICT: PASS", "EXECUTION_VERDICT: PASS", "PONYTAIL_VERDICT: PASS"))]
        r18_plan = subprocess.check_output(["/usr/bin/git", "-C", str(MAIN), "show", f"{R18}:{R18_REL}"])
        if (r18_plan.count(b"\n"), len(r18_plan), hashlib.sha256(r18_plan).hexdigest()) != (893, 63553, "27fb90d6cbaade6df16e838595dacb803763e94f9667da065a09bfda2747b215"):
            raise RuntimeError("R18 Plan differs")
        exact_file(Path(__file__), 0o600, int(owner_size_raw), owner_sha)
        exact_file(adoption, 0o600, 5521, "b798a74621e7899fd50b5449f6516e8e3ef8f441336f297cfaf3106ef6c2477c")
        exact_file(builder, 0o600, 9285, "2feef8fd253e0e65efad374e9bba3b8f0fe942af5134ab5874abd69659e5cb2f")
        exact_file(gate, 0o600, 9378, "0e96c26e8d1af90adcad09874c38f4821662e06f1ad332f0f0ebbbd39994ed10")
        exact_file(dependency_patch, 0o600, 3554, "f410e5a3bf07824af2495f6a51d43f43903014e582393f5aad31ab4483b6a23c")
        uv_id = exact_file(Path(UV), 0o755, 40085920, "1fb9a1083a299ec9dee6d44af22959741b808e1ae308c13c9afb5c330d48279a")
        exact_file(Path(PY313), 0o755, 17439616, "7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683")
        py314_id = exact_file(Path(PY314), 0o755, 18817184, "1ba16b38d45f006e449bb51a923dae83f3c384611bcd4ee428afd044b7ed4c95")

        r18_report = MODELING / "r18-task2-report.md"
        r18_raw, r18_report_id = read_exact(r18_report)
        if r18_report_id != (16777232, 307553361, 4730, "29d5ab38799d6e1fd7d61689c40a33cb530fdf8bd5abf750d94384db20db8f04") or r18_raw.splitlines().count(b"STATUS: BLOCKED") != 1:
            raise RuntimeError("R18 Task2 report differs")
        r18_empty_ids = []
        for name, inode in (("r18-task2-spec-review.md", 307553362), ("r18-task2-quality-review.md", 307553363), ("r18-task2-terminal-receipt.md", 307553364)):
            identity = exact_file(MODELING / name, 0o600, 0, hashlib.sha256(b"").hexdigest())
            if identity != (16777232, inode, 0, hashlib.sha256(b"").hexdigest()):
                raise RuntimeError(f"R18 empty artifact differs: {name}")
            r18_empty_ids.append(identity)
        base_brief_id = exact_file(MODELING / "task-7-brief.md", 0o600, 538571, "fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b")
        if base_brief_id != (16777232, 295274948, 538571, "fd27537dc55d460403f1bdb6d2af5300820df08ecb722d204e017d3fa3f9ba6b"):
            raise RuntimeError("base driver brief differs")
        absent = [
            MODELING / "r18-live-runtime",
            MODELING / "r18-evidence",
            MODELING / "task-7-r18-followup-1-brief.md",
            MODELING / "task-7-r18-followup-1-report.md",
            MODELING / "task-7-r18-followup-1-failure-review.md",
            MODELING / "task-7-r18-followup-1-success-review.md",
            MODELING / "r19-live-runtime",
            MODELING / "r19-evidence",
            MODELING / "task-7-r19-followup-1-brief.md",
            MODELING / "task-7-r19-followup-1-report.md",
            MODELING / "task-7-r19-followup-1-failure-review.md",
            MODELING / "task-7-r19-followup-1-success-review.md",
        ]
        if any(path.exists() or path.is_symlink() for path in absent):
            raise RuntimeError("fresh or frozen absence differs")
        adoption_dirty = marker([PY313, str(adoption), "dirty"], "R19_ADOPTION_GREEN mode=dirty ")
        c_raw = body(r15, b"## Appendix C ", 126, 4629, "d4e75498888c6f3c598e4547755a2e024b5c57fb4e1d4cbde1595359796ecbc0")
        tmp = Path(tempfile.mkdtemp(prefix="r19-task2-", dir="/private/tmp"))
        os.chmod(tmp, 0o700)
        tmp_fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

        bindings = (
            f"r19_plan_commit: {plan_commit}\nr19_plan_sha256: {plan_sha}\n"
            + "".join(f"r19_plan_review_{path.name}: {identity!r}\n" for path, identity in zip(review_paths, plan_reviews))
            + f"r18_task2_report: {r18_report_id!r}\nr18_empty_artifacts: {r18_empty_ids!r}\n"
            + f"base_driver_brief: {base_brief_id!r}\n"
            + f"r19_dirty_adoption_marker: {adoption_dirty.strip()}\n"
            + "r19_tool_postimage_sha256: 85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26\n"
            + "r19_test_postimage_sha256: a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63\n"
            + "r19_binary_diff_sha256: a499937290390411db62ed7b1a6a3757357ff627feeca7a08cf9ccd7dd40d248\n"
            + "r18_task2_status: BLOCKED\n"
        ).encode()
        write_all(fds["report"], bindings)
        os.fsync(fds["report"])
        dependency_ids = ((16777232, 211193900), (16777232, 211193901))
        dependency_patch_count = 1
        marker(
            [PY313, str(dependency_patch), "apply", str(SOURCE / PYPROJECT), ":".join(map(str, dependency_ids[0])), str(SOURCE / REQUIREMENTS), ":".join(map(str, dependency_ids[1]))],
            "R19_DEPENDENCY_PATCH_GREEN mode=apply files=2 descriptor_bound=1",
        )
        marker([PY313, str(adoption), "patched"], "R19_ADOPTION_GREEN mode=patched ")
        uv_install_count = 1
        installed = subprocess.run([UV, "pip", "install", "--python", VENV_PY, "mcp[cli]==1.28.1"], text=True, capture_output=True, timeout=900)
        if installed.returncode:
            raise RuntimeError(f"uv install failed: {installed.stdout}{installed.stderr}")
        if exact_file(Path(UV), 0o755, 40085920, "1fb9a1083a299ec9dee6d44af22959741b808e1ae308c13c9afb5c330d48279a") != uv_id:
            raise RuntimeError("uv executable changed during install")
        venv_link = os.lstat(VENV_PY)
        venv_link_fields = (venv_link.st_dev, venv_link.st_ino, venv_link.st_uid, stat.S_IMODE(venv_link.st_mode), venv_link.st_nlink, venv_link.st_size)
        if not stat.S_ISLNK(venv_link.st_mode) or Path(os.path.realpath(VENV_PY)) != Path(PY314):
            raise RuntimeError("venv Python link differs")
        entry_id = exact_file(Path(VENV_EXE), 0o755)
        env_marker = marker([VENV_PY, "-c", "import importlib.metadata as m; from mcp.server.fastmcp import FastMCP; assert m.version('mcp') == '1.28.1'; print('R19_MCP_ENV_GREEN version=1.28.1 fastmcp=1')"], "R19_MCP_ENV_GREEN version=1.28.1 fastmcp=1")
        environment_facts = f"r19_uv: {uv_id!r}\nr19_dependency_identities: {dependency_ids!r}\nr19_python314: {py314_id!r}\nr19_venv_python_link: {venv_link_fields!r}\nr19_blender_mcp_entrypoint: {entry_id!r}\nr19_mcp_marker: {env_marker.strip()}\n".encode()
        write_all(fds["report"], environment_facts)
        os.fsync(fds["report"])
        test_preimage = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"{SOURCE_PARENT}:{TEST}"])
        frozen_import = b"from tests.mcp_client import MCPClient"
        if test_preimage.splitlines()[53] != frozen_import or (SOURCE / TEST).read_bytes().splitlines()[53] != frozen_import:
            raise RuntimeError("frozen test import differs")
        ruff = subprocess.run(["/Users/yeminjie/.local/bin/uvx", "--quiet", "ruff@0.16.2", "check", "--no-cache", "--isolated", "--target-version", "py313", "--select", "E4,E7,E9,F", str(SOURCE / TOOL)], text=True, capture_output=True, timeout=60)
        if ruff.returncode:
            raise RuntimeError(f"source Ruff failed: {ruff.stdout}{ruff.stderr}")
        marker([PY314, "-c", "import sys; from pathlib import Path; compile(Path(sys.argv[1]).read_bytes(), sys.argv[1], 'exec'); print('R19_TEST_SYNTAX_GREEN')", str(SOURCE / TEST)], "R19_TEST_SYNTAX_GREEN")
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
        if exact_file(Path(VENV_EXE), 0o755) != entry_id or (lambda value: (value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode), value.st_nlink, value.st_size))(os.lstat(VENV_PY)) != venv_link_fields:
            raise RuntimeError("MCP environment changed during integration")
        marker([VENV_PY, "-c", "import importlib.metadata as m; from mcp.server.fastmcp import FastMCP; assert m.version('mcp') == '1.28.1'; print('R19_MCP_ENV_GREEN version=1.28.1 fastmcp=1')"], "R19_MCP_ENV_GREEN version=1.28.1 fastmcp=1")
        sh(SOURCE, "/usr/bin/git", "add", "--", TOOL, PYPROJECT, REQUIREMENTS, TEST)
        marker([PY313, str(adoption), "staged"], "R19_ADOPTION_GREEN mode=staged ")
        sh(SOURCE, "/usr/bin/git", "commit", "-m", "fix(blender-mcp): pin MCP and preserve thumbnail settings")
        source_pin = sh(SOURCE, "/usr/bin/git", "rev-parse", "HEAD").stdout.strip()
        if re.fullmatch(r"[0-9a-f]{40}", source_pin) is None or sh(SOURCE, "/usr/bin/git", "rev-list", "--parents", "-n", "1", "HEAD").stdout.split() != [source_pin, SOURCE_PARENT] or sh(SOURCE, "/usr/bin/git", "status", "--porcelain=v1").stdout:
            raise RuntimeError("source commit differs")
        if sh(SOURCE, "/usr/bin/git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines() != [TOOL, PYPROJECT, REQUIREMENTS, TEST]:
            raise RuntimeError("source commit paths differ")
        committed_tool = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"HEAD:{TOOL}"])
        committed_pyproject = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"HEAD:{PYPROJECT}"])
        committed_requirements = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"HEAD:{REQUIREMENTS}"])
        committed_test = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "show", f"HEAD:{TEST}"])
        committed_diff = subprocess.check_output(["/usr/bin/git", "-C", str(SOURCE), "diff", "--binary", f"{SOURCE_PARENT}..HEAD"])
        if (len(committed_tool), hashlib.sha256(committed_tool).hexdigest()) != (4103, "85b1c57accf3427ca43259ea2f5b50d9a4fc95b1741096cb5e7050b052678f26"):
            raise RuntimeError("committed tool differs")
        if (len(committed_test), hashlib.sha256(committed_test).hexdigest()) != (43710, "a8912677324da140d707e604b7e4ed6dc28b0ff4dacbb0ae8cc24ba8e6f05c63"):
            raise RuntimeError("committed test differs")
        if (len(committed_pyproject), hashlib.sha256(committed_pyproject).hexdigest(), len(committed_requirements), hashlib.sha256(committed_requirements).hexdigest()) != (1725, "bc9a4c73f171482d167addb5dc82bb6c318b256ea8df72851b10b1316bb7ba51", 193, "fe501e209528878d9074701735eb3ccd2ac3cdc78b8be9275a19a2db4d1b21ed"):
            raise RuntimeError("committed dependencies differ")
        if hashlib.sha256(committed_diff).hexdigest() != "1fa15dbe10ca8697de03b9371dccb414c406114d52d1c1e00801884ce7746a8f":
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
        build_output = marker([PY313, str(builder), source_pin, str(old_controller), str(old_driver), str(allocator), str(runner), str(runtime)], "R19_RUNTIME_GREEN ")
        gate_count = 1
        gate_output = marker([PY313, str(gate), str(runtime), source_pin, str(old_controller), str(old_driver), str(allocator), str(runner)], "R19_RUNTIME_GATE_GREEN ")
        current_root = os.lstat(runtime)
        if (runtime_identity.st_dev, runtime_identity.st_ino, runtime_identity.st_uid, stat.S_IMODE(runtime_identity.st_mode)) != (current_root.st_dev, current_root.st_ino, current_root.st_uid, stat.S_IMODE(current_root.st_mode)):
            raise RuntimeError("runtime root replaced")
        facts = (
            f"r19_source_pin: {source_pin}\ndependency_patch_run_count: 1\nuv_install_run_count: 1\nsource_integration_run_count: 1\nruntime_builder_run_count: 1\nruntime_gate_run_count: 1\n"
            f"builder_marker: {build_output.strip()}\ngate_marker: {gate_output.strip()}\n"
            + "".join(f"runtime_{path.name}: {exact_file(path)!r}\n" for path in sorted(runtime.iterdir()))
        ).encode()
        write_all(fds["report"], facts)
        os.fsync(fds["report"])
        print(f"R19_TASK2_PHASE1_GREEN source_pin={source_pin} actual_run_count=0", flush=True)
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
        print("R19_TASK2_TERMINAL PASS", flush=True)
        return 0
    except BaseException as error:
        if not terminal_done and "report" in fds:
            try:
                terminal(fds.pop("report"), report, ids["report"], f"failure: {type(error).__name__}: {error}\ndependency_patch_run_count: {dependency_patch_count}\nuv_install_run_count: {uv_install_count}\nsource_integration_run_count: {integration_count}\nruntime_builder_run_count: {builder_count}\nruntime_gate_run_count: {gate_count}\nactual_run_count: 0\n".encode(), "BLOCKED")
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

## Appendix D — exact matching R19 runtime gate

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
R18_COMMIT = "f37ea8271c217d1801349c6dd19b5b40612ce64e"


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
        raise SystemExit("usage: runtime_gate.py RUNTIME_ROOT R19_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER")
    root = Path(sys.argv[1])
    expected_pin = sys.argv[2]
    if re.fullmatch(r"[0-9a-f]{40}", expected_pin) is None or expected_pin == OLD_PIN:
        raise RuntimeError("expected source pin differs")
    old_controller_path, old_driver_path, old_allocator_path, old_runner_path = map(Path, sys.argv[3:])
    root_info = os.lstat(root)
    if Path(os.path.realpath(root)) != root or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700:
        raise RuntimeError("unsafe runtime root")
    names = sorted(path.name for path in root.iterdir())
    if names != ["driver.sh", "r19_allocator.py", "r19_allocator_runner.py", "r3_controller.py"]:
        raise RuntimeError("runtime leaves differ")
    controller, controller_info = owned(root / "r3_controller.py", 0o600)
    driver, _ = owned(root / "driver.sh", 0o600)
    allocator, _ = owned(root / "r19_allocator.py", 0o600)
    runner, _ = owned(root / "r19_allocator_runner.py", 0o600)
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
    restored_driver = one(restored_driver, b'docs/superpowers/plans/2026-08-15-official-blender-mcp-r19-mcp-dependency.md', b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md')
    restored_driver = one(restored_driver, b'task-7-r19-followup-1-report.md', b'task-7-r14-followup-1-report.md')
    restored_driver = one(restored_driver, b'.superpowers/sdd/modeling-remediation/r19-evidence/final-retest-r3/attempt-0001', b'.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001', 2)
    restored_driver = one(restored_driver, controller_sha.encode(), OLD_CONTROLLER_SHA.encode())
    new_topology = f'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = {R18_COMMIT}\n  test "$(git -C "$FEATURE_ROOT" rev-parse {R18_COMMIT}^)" = e559ad0042ed3a862753e5a2aa51d4737bfca519\n  test "$(git -C "$FEATURE_ROOT" rev-parse e559ad0042ed3a862753e5a2aa51d4737bfca519^)" = 47503f7378b167cd7b8125c42ad8a384c69ff95e\n  test "$(git -C "$FEATURE_ROOT" rev-parse 47503f7378b167cd7b8125c42ad8a384c69ff95e^)" = 6e78a91d9c4fab6746262c88e7032e789a3bae1c\n  test "$(git -C "$FEATURE_ROOT" rev-parse 6e78a91d9c4fab6746262c88e7032e789a3bae1c^)" = deb5426a57748ae4e89e91afe0a1752e4c9fc2b0\n  test "$(git -C "$FEATURE_ROOT" rev-parse deb5426a57748ae4e89e91afe0a1752e4c9fc2b0^)" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'.encode()
    old_topology = b'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
    restored_driver = one(restored_driver, new_topology, old_topology)
    if restored_driver != old_driver:
        raise RuntimeError("driver reversal differs")

    restored_allocator = allocator
    restored_allocator = one(restored_allocator, f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode(), b'SOURCE_ID = (16777232, 305390856)')
    restored_allocator = one(restored_allocator, f'SOURCE_SHA256 = "{controller_sha}"'.encode(), f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode())
    restored_allocator = one(restored_allocator, b'PARTS = ("r19-evidence", "final-retest-r3", "attempt-0001")', b'PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")')
    if restored_allocator.count(b"R19") != 11:
        raise RuntimeError("allocator diagnostic count differs")
    restored_allocator = restored_allocator.replace(b"R19", b"R12")
    if restored_allocator != old_allocator:
        raise RuntimeError("allocator reversal differs")

    allocator_sha = hashlib.sha256(allocator).hexdigest()
    restored_runner = runner
    restored_runner = one(restored_runner, f'ALLOCATOR_SHA256 = "{allocator_sha}"'.encode(), f'ALLOCATOR_SHA256 = "{OLD_ALLOCATOR_SHA}"'.encode())
    restored_runner = one(restored_runner, f'SOURCE_CONTROLLER = Path("{root / "r3_controller.py"}")'.encode(), b'SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")')
    restored_runner = one(restored_runner, f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode(), b'SOURCE_ID = (16777232, 305390856)')
    restored_runner = one(restored_runner, f'SOURCE_SHA256 = "{controller_sha}"'.encode(), f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode())
    restored_runner = one(restored_runner, b'R19_ALLOCATION_GREEN', b'R12_ALLOCATION_GREEN')
    if restored_runner.count(b"R19") != 15:
        raise RuntimeError("runner diagnostic count differs")
    restored_runner = restored_runner.replace(b"R19", b"R14")
    if restored_runner != old_runner:
        raise RuntimeError("runner reversal differs")

    for raw, path in ((controller, root / "r3_controller.py"), (allocator, root / "r19_allocator.py"), (runner, root / "r19_allocator_runner.py")):
        compile(raw, str(path), "exec")
    ruff = subprocess.run(["/Users/yeminjie/.local/bin/uvx", "--quiet", "ruff@0.16.2", "check", "--no-cache", "--isolated", "--target-version", "py313", "--select", "E4,E7,E9,F", str(root / "r3_controller.py"), str(root / "r19_allocator.py"), str(root / "r19_allocator_runner.py")], text=True, capture_output=True, timeout=60)
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
        compile(body, f"<r19-heredoc-{number}>", "exec")
    anchor = b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n'
    if driver.count(anchor) != 1:
        raise RuntimeError("driver run count differs")
    start = driver.index(anchor)
    command = driver[start:driver.index(b" || R3_RUN_EXIT=$?", start)]
    if b"<" in command:
        raise RuntimeError("driver stdin redirect differs")
    print("R19_RUNTIME_GATE_GREEN controller=1 driver=1 allocator_equivalent=1 runner_equivalent=1 probe=1 static=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix B — exact direct R19 runtime builder

Extract this 154-line body without fences. Invoke once as specified in Task2. It is the exact R15 Appendix B algorithm with only the declared R19 literals and six-line topology.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path


OLD_PIN = "4309a39646e644261624bfcd2bca669b343b7621"
R18_COMMIT = "f37ea8271c217d1801349c6dd19b5b40612ce64e"
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
        driver = replace(driver, b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md', b'docs/superpowers/plans/2026-08-15-official-blender-mcp-r19-mcp-dependency.md')
        driver = replace(driver, b'task-7-r14-followup-1-report.md', b'task-7-r19-followup-1-report.md')
        driver = replace(driver, b'.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001', b'.superpowers/sdd/modeling-remediation/r19-evidence/final-retest-r3/attempt-0001', 2)
        driver = replace(driver, OLD_CONTROLLER_SHA.encode(), controller_sha.encode())
        old_topology = b'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
        new_topology = f'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = {R18_COMMIT}\n  test "$(git -C "$FEATURE_ROOT" rev-parse {R18_COMMIT}^)" = e559ad0042ed3a862753e5a2aa51d4737bfca519\n  test "$(git -C "$FEATURE_ROOT" rev-parse e559ad0042ed3a862753e5a2aa51d4737bfca519^)" = 47503f7378b167cd7b8125c42ad8a384c69ff95e\n  test "$(git -C "$FEATURE_ROOT" rev-parse 47503f7378b167cd7b8125c42ad8a384c69ff95e^)" = 6e78a91d9c4fab6746262c88e7032e789a3bae1c\n  test "$(git -C "$FEATURE_ROOT" rev-parse 6e78a91d9c4fab6746262c88e7032e789a3bae1c^)" = deb5426a57748ae4e89e91afe0a1752e4c9fc2b0\n  test "$(git -C "$FEATURE_ROOT" rev-parse deb5426a57748ae4e89e91afe0a1752e4c9fc2b0^)" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'.encode()
        driver = replace(driver, old_topology, new_topology)
        create(root_fd, root, root_fields, created, "driver.sh", driver)

        allocator = allocator_source
        allocator = replace(allocator, b'SOURCE_ID = (16777232, 305390856)', f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode())
        allocator = replace(allocator, f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode(), f'SOURCE_SHA256 = "{controller_sha}"'.encode())
        allocator = replace(allocator, b'PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")', b'PARTS = ("r19-evidence", "final-retest-r3", "attempt-0001")')
        if allocator.count(b"R12") != 11:
            raise RuntimeError("allocator diagnostic anchors differ")
        allocator = allocator.replace(b"R12", b"R19")
        create(root_fd, root, root_fields, created, "r19_allocator.py", allocator)
        allocator_sha = hashlib.sha256(allocator).hexdigest()

        runner = runner_source
        runner = replace(runner, f'ALLOCATOR_SHA256 = "{OLD_ALLOCATOR_SHA}"'.encode(), f'ALLOCATOR_SHA256 = "{allocator_sha}"'.encode())
        old_source_path = b'SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")'
        runner = replace(runner, old_source_path, f'SOURCE_CONTROLLER = Path("{controller_out}")'.encode())
        runner = replace(runner, b'SOURCE_ID = (16777232, 305390856)', f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode())
        runner = replace(runner, f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode(), f'SOURCE_SHA256 = "{controller_sha}"'.encode())
        runner = replace(runner, b'R12_ALLOCATION_GREEN', b'R19_ALLOCATION_GREEN')
        if runner.count(b"R14") != 15:
            raise RuntimeError("runner diagnostic anchors differ")
        runner = runner.replace(b"R14", b"R19")
        create(root_fd, root, root_fields, created, "r19_allocator_runner.py", runner)

        print(f"R19_RUNTIME_GREEN source_pin={pin} controller_sha256={controller_sha} driver_sha256={hashlib.sha256(driver).hexdigest()} allocator_sha256={allocator_sha} runner_sha256={hashlib.sha256(runner).hexdigest()}")
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
