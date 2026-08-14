# Official Blender MCP R15 Deferred Thumbnail Plan

## Goal

Fix the pinned official Blender MCP interactive thumbnail lifecycle so `render_thumbnail_to_path` reliably produces its documented 320-pixel maximum dimension, then perform one fresh complete live retest without weakening the controller's exact 320×320 contract.

## Architecture

The source change is deliberately local: keep render settings assigned until the existing deferred file checker finishes, then restore them together with `filepath`. The blocking/background path keeps the existing context-manager flow. Extend the existing Blender integration test with the dimension and restoration assertions. Commit exactly those two upstream files on parent `4309a39646e644261624bfcd2bca669b343b7621` and use the new commit as R15's sole source pin.

R15 derives a controller from exact R11 controller bytes by replacing only `SOURCE_PIN`; it derives a driver from exact R14 driver bytes by replacing only the R15 Plan/report/evidence/topology/controller bindings. A fresh allocator and runner reuse the already-reviewed R12/R14 algorithms with only fresh namespace, controller identity, allocator identity, and marker substitutions. No controller dimension assertion, scene render setting, viewport rule, shared template, unrelated render engine branch, or other tool changes.

## Frozen predecessor state

- Main repository HEAD is R14 Plan commit `deb5426a57748ae4e89e91afe0a1752e4c9fc2b0`; parent is R13 Plan commit `c0f38156cad28996cfddcabb1cf775ae84983cf5`.
- R14 Plan is 463 lines / 30,655 bytes / SHA-256 `99555c544b486a371283d58834ed88fc31f7c4eb04a872f70c293da2990a8818`; its final spec/execution/Ponytail reviews are frozen PASS.
- R14 Task2 report is dev/inode `16777232/306212022`, size 1,435, SHA-256 `65536e03f96479a1bd92135744b972e724c14ba0c9d498730df97c9724b26998`, unique `STATUS: PASS`.
- R14 runtime driver is dev/inode `16777232/306212026`, size 33,823, SHA-256 `e9342fee0dcbc504cf4f680ace8b49f3a8c8926f3fe23f9672657781cf874dcd` and must never be launched again.
- R14 live report is dev/inode `16777232/306212195`, mode 0600, size 172, SHA-256 `bc244b0ccba0443036d3bb4f8a235b5efcd938ca59e288c2eb93cec05e089c1f`, with `actual_run_count: 1` and unique `STATUS: BLOCKED`.
- The whole `.superpowers/sdd/modeling-remediation/r12-evidence` tree, its ticket, controller, 50-row journal, 23-row dispatch manifest, partial screenshots, and scratch thumbnail are immutable external history. R14 call 0023 is the only failing call; calls 1–22 passed. No R14 attempt-0002 or continuation is permitted.
- The rejected scratch PNG is a valid RGBA PNG with IHDR 480×480. It is diagnostic only and never enters R15 success evidence; its temporary path identity is not an R15 admission source.
- Exact R11 controller source is `.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py`, 285,409 bytes, SHA-256 `58c3057b8d59f8394807c3ab8a1193dadadf011c9a0230c2f69afd7cc3148d27`.
- Upstream `/Users/yeminjie/blender_mcp` is clean at `4309a39646e644261624bfcd2bca669b343b7621` before Task 2. The implementation preimage is 116 lines / 3,583 bytes / SHA-256 `51addb3134812c6aab0c29f7ab3ff136c4dfa8d8dff0f97723d32e9e57f74c4c`; the test preimage is 1,129 lines / 42,394 bytes / SHA-256 `961f8d50ab6237ffbe8fff246f03c030bc189c34e5a7cc11c87dc498c7083db0`.
- Fresh R15 runtime, reports, brief, evidence, ticket, attempt-0002, listener, owned processes, and port 9876 must all be absent at their admission boundaries.

## File map

- Main Plan: `docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md`
- Upstream implementation: `/Users/yeminjie/blender_mcp/mcp/blmcp/tools/render_thumbnail_to_path_toolcode.py`
- Upstream regression: `/Users/yeminjie/blender_mcp/tests/test_blender_mcp_with_blender.py`
- Runtime: `.superpowers/sdd/modeling-remediation/r15-live-runtime/{r3_controller.py,driver.sh,r15_allocator.py,r15_allocator_runner.py}`
- Task2 aggregate/reviews: `.superpowers/sdd/modeling-remediation/r15-task2-{report,spec-review,quality-review}.md`; `.superpowers/sdd/modeling-remediation/r15-task2-terminal-receipt.md` is preallocated mode 0600 and becomes committed mode 0400 through its retained original FD only after verified PASS
- Live evidence: `.superpowers/sdd/modeling-remediation/r15-evidence/final-retest-r3/attempt-0001`
- Live brief/report: `.superpowers/sdd/modeling-remediation/task-7-r15-followup-1-{brief,report}.md`
- Conditional live review files use the same `task-7-r15-followup-1-{failure,success}-*` prefix.

## Task 1 — Certify and commit this Plan only

- Bind the frozen identities above, exact clean main/source repositories, and every fresh R15 absence.
- Extract Appendix B as exactly 154 lines / 8,765 bytes / SHA-256 `60f3298770237f72e842a58f7d1be723efa6353dc4184102f2f29d7f8988473a`, Appendix E as 346 lines / 14,230 bytes / SHA-256 `ef81d9f1237873a3f8059f12066bbaedd976d67873440b39a058441ab37f16f0`, Appendix D as 135 lines / 8,858 bytes / SHA-256 `17c32cc610bc57cf65ab1432193a765630300fb96a7988f5a8941c5e23f3fd63`, and Appendix C as 126 lines / 4,629 bytes / SHA-256 `d4e75498888c6f3c598e4547755a2e024b5c57fb4e1d4cbde1595359796ecbc0`. In one disposable native-0700 `/private/tmp` root, invoke Appendix B once with a synthetic non-parent 40-hex pin and the exact frozen controller/driver plus exact extracted R12 allocator/R14 runner; then invoke Appendix D once with canonical `/Users/yeminjie/.local/share/uv/python/cpython-3.13.13-macos-aarch64-none/bin/python3.13` (dev/inode `16777232/259766870`, mode 0755, size 17,439,616, SHA-256 `7fc33c67b5d5d91b3ce9ab16d2a354ad623f438c24eed3f543a57fc635aea683`) and that same pin. Require unique `R15_RUNTIME_GREEN` and `R15_RUNTIME_GATE_GREEN`. Execute Appendix E directly with `--selfcheck` and require `R15_TASK2_PRIMITIVES_GREEN fd=1 parser=1 terminal=1 process_group=1`. Apply Appendix A only to a disposable copy of the implementation and invoke Appendix C once against it; require unique `R15_DEFERRED_RESTORE_GREEN cases=3`, then cleanup. These Plan tests may not touch either repository, invoke allocator/runner/driver or a live controller, or start Blender/MCP; Appendix D owns the sole offline controller probe.
- Three fresh reviewers independently audit the same frozen Plan SHA: specification/safety, execution/state-machine, and Ponytail/YAGNI. Any finding, including Minor, requires a new Plan SHA and a complete fresh review round.
- The sole main-repository commit changes only this Plan and has parent `deb5426a57748ae4e89e91afe0a1752e4c9fc2b0`.
- Do not modify upstream source, create runtime/report/evidence, start Blender/MCP, or execute a source integration test before this commit.

## Task 2 — Fix, pin, build, review, and terminalize

- Before any upstream write, the persistent Task2 Python process extracts exact Appendix E and uses only its `allocate` function to exclusive-create the aggregate report, both empty review reports, and the terminal receipt as native-0600, single-link files, retaining their original read/write CLOEXEC FDs and allocation identities. It writes the frozen admission prefix through `write_all` and immediately fsyncs the aggregate FD. Every Task2 failure before the first `terminal` call, including patch/test/commit/build/review failure, sends exact observed facts to `terminal(..., "BLOCKED")` before remaining review/receipt FDs are frozen/closed; the receipt remains noncommitted mode 0600. A failure raised by `terminal` itself is `UNVERIFIED_TERMINAL`: close all remaining FDs, record the observed path bytes externally, stop, and never call `terminal` again. No later task owns this report and no path reopen may write it.
- Recheck upstream clean HEAD and exact preimage identities. Open no unrelated file for writing.
- In `render_thumbnail_to_path_toolcode.py`, preserve the current `obj_attrs` values and order. For the GUI/deferred branch only: snapshot each affected old attribute, assign the requested thumbnail values before `INVOKE_DEFAULT`, keep them assigned after the operator returns, and pass every old attribute plus `filepath` to the existing `_deferred_tool_check_for_file_output(..., restore_attrs=...)`. If the operator raises, restore every captured attribute immediately before returning the existing error result. The blocking/background branch continues using `_backup_attrs_and_assign_multi` and restores after the blocking render.
- Do not modify `_backup_attrs_and_assign_multi`, `_deferred_tool_check_for_file_output`, viewport rendering, engine selection, thumbnail constants, scene setup, add-on code, or any other source.
- In the existing `test_render_thumbnail_to_path`, snapshot resolution X/Y/percentage, simplify enable/subdivision, and the active engine's sample value; invoke the tool; read a 24-byte PNG header and require the original aspect ratio scaled so its longest edge is exactly 320; then query and require every snapped setting exactly restored. The interactive case proves deferred success restoration; the background case proves blocking behavior. A disposable fault-injection unit around the patched branch must prove partial-assignment and operator-error restoration without starting Blender. `struct` is already imported; add no helper or test file.
- Exact binaries are `/Applications/Blender.app/Contents/MacOS/Blender`, canonical Python `/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14` (dev/inode `16777232/211200476`, mode 0755, size 18,817,184, SHA-256 `1ba16b38d45f006e449bb51a923dae83f3c384611bcd4ee428afd044b7ed4c95`), and `/Users/yeminjie/blender_mcp/mcp/.venv/bin/blender-mcp`; the worktree Python symlink is not an executable identity. After pinned Ruff and Appendix C, Appendix E owns the single integration subprocess and its dedicated process group. Its exact argv is `/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14 /Users/yeminjie/blender_mcp/tests/test_blender_mcp_with_blender.py TestBackgroundServer.test_render_thumbnail_to_path TestInteractiveServer.test_render_thumbnail_to_path`. Its explicit environment contains `PATH=/usr/bin:/bin:/usr/sbin:/sbin:/Users/yeminjie/.local/bin`, `HOME` copied from the invoking user, `BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender`, `BLENDER_MCP=/Users/yeminjie/blender_mcp/mcp/.venv/bin/blender-mcp`, and `BLENDER_MCP_FOREGROUND=1`; the test derives `BLENDER_PATH`. After Appendix E returns, root proves ports 9876, 9877, and 9878 empty. Nonzero status, timeout, unexpected additional test, or incomplete cleanup is BLOCKED.
- Commit exactly the two changed upstream paths once. Require parent `4309a39646e644261624bfcd2bca669b343b7621`, one-parent topology, clean status, and record the new 40-hex commit as `R15_SOURCE_PIN` in the Task2 report. Never amend, reset, rebase, or add a second upstream fix commit inside R15.
- Any source/test/check/commit failure freezes the already-open Task2 report as `STATUS: BLOCKED`; no runtime, evidence, GUI, or live run follows.
- Only after the upstream commit is clean and fully bound, build and review the R15 runtime within this same Task2/report lifetime.
- From the exact R11 controller, replace exactly one full-line `SOURCE_PIN = "4309..."` anchor with `R15_SOURCE_PIN`. No other controller byte changes and its size remains 285,409 bytes. Require exact reverse reconstruction. Record controller identity/SHA; the single detailed runtime compile/Ruff/probe/static gate below owns all executable validation.
- From exact R14 driver bytes, perform exactly these logical substitutions, each from a unique full context and with exact reverse reconstruction: R14 Plan path→R15 Plan path; R14 follow-up report→R15 follow-up report; both R12 evidence attempt roots→R15 evidence attempt root; controller SHA→new controller SHA; insert the R14 Plan commit as the R15 Plan parent at the topology head. Do not alter the ten-argument schema, PTY/FD8/ACK/review/cleanup transport, scratch guard, source path, or run count.
- Derive the allocator from exact committed R12 allocator bytes (115 lines / 5,615 bytes / SHA-256 `0d08c4f4f8780a4bed8fca26d1434fa7e44cde0652fa506ac33f200c6ed5ca7c`) only by changing `PARTS` to `r15-evidence/final-retest-r3/attempt-0001`, `SOURCE_ID` and `SOURCE_SHA256` to the just-created equal-size controller, and R12 marker/diagnostics to R15. Preserve retained dir-FDs, own-inode rollback, leaf replacement protection, modes, fsyncs, and collision behavior.
- Derive the runner from exact committed R14 runner bytes (115 lines / 6,019 bytes / SHA-256 `a038f42aa4b1a6c284d91ea611b7bc0f40438aeffa05d95c99b47fa6a8efb1a9`) only by binding the runtime allocator/controller paths, both identities/hashes/sizes, and R15 marker/diagnostics. Preserve canonical Python/source/modeling-root checks, retained descriptors, exact list argv, conservative invocation count, and single subprocess call.
- Runtime parent is native 0700 and contains exactly the four native-0600 leaves. Invoke exact Appendix D once as the sole runtime gate; require its unique GREEN. No Blender/MCP/GUI/live call.
- Two fresh reviewers write only their preallocated original-FD reports. Spec and quality must both uniquely approve the exact source pin, two-file upstream diff, controller single anchor, driver substitutions, allocator/runner derivations, Task2 counts, and fresh absences.
- After reviewers finish, the persistent owner uses Appendix E `parse_approval` on the retained spec and quality FDs, then `freeze`s and closes each. Only if both exact full-line parsers approve, it calls `prepare_receipt` on the retained receipt FD and exact PASS facts; this freezes mode-0600 receipt bytes binding the predicted final report tuple but leaves the FD open. It then calls `terminal(..., "PASS")`, requires the returned tuple to equal that prediction, and calls `commit_receipt`, which revalidates the original FD/path identity and changes only that FD to mode 0400. The exact committed inode/content/mode is the acceptance token. Any exception before the terminal call records the observed facts and calls `terminal(..., "BLOCKED")`; every still-open review/receipt FD closes in `finally`. An exception from either terminal call follows `UNVERIFIED_TERMINAL`; an absent/malformed/non-0400 receipt is `PASS_WITHOUT_RECEIPT`. Both stop with no live admission and never a second write. No retry, replacement, substring verdict parser, or second writer.

## Task 3 — Sole fresh live run

- Admission binds R15 Plan commit/SHA and three Plan reviews; upstream parent/new pin/two-path diff and clean status; R15 Task2 report with unique PASS and both approvals; and the preallocated terminal receipt at its exact dev/inode, native mode 0400, nlink 1, with exact report dev/inode/size/SHA fields equal to the current report. It also binds the exact runtime parent/four leaves, all frozen predecessor closures, clean main repository, absent fresh brief/report/evidence/ticket, and empty port/process inventory. An absent/malformed/mismatched/non-0400 receipt mechanically rejects `UNVERIFIED_TERMINAL` and `PASS_WITHOUT_RECEIPT` histories.
- Exclusive-create `task-7-r15-followup-1-report.md` before GUI and retain its original read/write CLOEXEC FD. Every failure after allocation is terminalized through that FD unless the descriptor-valid driver already wrote a unique terminal.
- Perform one fresh factory/add-on/listener GUI preflight. If Online Access is unchecked, obtain action-time confirmation immediately before enabling it. Record the visible factory state and fresh raw `bpy.app.tempdir`.
- Extract the exact R10 scratch checker from committed R10 Plan Appendix C (34 lines / 1,480 bytes / SHA-256 `711fae45f6b20cd9843b58d49aa59688b29815471028fc75dc93250f28e9144b`) once and invoke it once. Only after its unique `R10_SCRATCH_GREEN` create/freeze the compact brief.
- Invoke the exact R15 runner once with canonical absolute runtime allocator, runtime controller, and modeling root. Require one exact R15 allocation marker; descriptor-open and retain all fresh evidence directories/controller through terminal. No alternate allocator, wrapper, relative path, attempt-0002, or retry.
- Launch only the exact R15 driver once in one live PTY with ten bound arguments. R15 driver launch count and R15 actual run count may each become at most one; prior counts remain external history.
- The derived R15 driver retains the exact R14 FD8 transport, bounded one-line failure/visual ACK grammar, review gates, cleanup, and fallback terminal bytes by raw-reversal proof. Failure ACK uses the exact persisted event/response identity and one honest first hypothesis. Visual review uses Option C: display every fresh R15 PNG in manifest order, obtain one explicit PASS/FAIL verdict per image, and send exactly one canonical ordered ACK. No predecessor image, verdict, or ACK is reusable.
- On every terminal, bind report/evidence/source/main-repo identities, count exactly one or zero fresh ticket as appropriate, prove attempt-0002 absent, clean only exact owned PID/start/image processes, prove port empty, fsync/path-recheck/close all retained FDs, and never reopen a terminal report.

## Task 4 — Terminal review and successful audit

- A driver/controller failure, missing/ambiguous ACK, postrun validation failure, source drift, cleanup error, or lost PTY follows the inherited fail-closed review lane and cannot be promoted.
- Success requires fresh root checks, evidence manifest, package, independent success review, and all final identities. R14/R15 Task2 artifacts and all predecessor failed evidence remain external and are excluded from the fresh success package.
- Only after fresh success review PASS may the audit script be updated and committed as the sole audit-file change.
- Successful first-parent history is exact length 14 in this order: runbook, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, audit. Every `paths` array has length one; parents are respectively old-R3, runbook, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15.
- Ticket/attempt assertions are namespace-qualified: frozen R14 `r12-evidence` has exactly one ticket and no attempt-0002; before R15 live, fresh `r15-evidence` is absent; after R15 launch it has exactly one attempt-0001 ticket and no attempt-0002.

## Prohibited shortcuts

- Do not accept 480×480, a dimension range, an artifact-reported dimension, or a scene-setting workaround.
- Do not modify or weaken controller thumbnail/viewport assertions.
- Do not reuse or mutate R14 evidence, ticket, scratch, brief, report, runtime, listener, PTY, PNG, verdict, or ACK.
- Do not add a shared abstraction, compatibility wrapper, timeout/sleep, symlink, second source fix commit, second allocator, second driver launch, attempt-0002, or retry namespace.
- Do not claim the upstream defect is fixed until the interactive integration test and one fresh complete R15 live run both prove 320×320.

## Appendix A — exact upstream patch anchors

The implementation preimage anchor begins at `render_args = ('INVOKE_DEFAULT',) if use_deferred else ()` and ends at the current final `return Result(status="ok", filepath=output_path)`. It occurs once. Replace that whole anchor with exactly:

````python
    if use_deferred:
        restore_attrs = [(rd, "filepath", orig_filepath)]
        try:
            for obj, attrs in obj_attrs:
                for attr, value in attrs.items():
                    restore_attrs.append((obj, attr, getattr(obj, attr)))
                    setattr(obj, attr, value)
            bpy.ops.render.render('INVOKE_DEFAULT', write_still=True)
        except BaseException as ex:
            for obj, attr, value in reversed(restore_attrs):
                setattr(obj, attr, value)
            if isinstance(ex, RuntimeError):
                return Result(status="error", message=str(ex))
            raise
        return _deferred_tool_check_for_file_output(
            'RENDER', output_path, restore_attrs=restore_attrs,
        )

    with _backup_attrs_and_assign_multi(*obj_attrs):
        try:
            bpy.ops.render.render(write_still=True)
        except RuntimeError as ex:
            rd.filepath = orig_filepath
            return Result(status="error", message=str(ex))

    rd.filepath = orig_filepath
    return Result(status="ok", filepath=output_path)
````

The test preimage anchor is the complete existing `test_render_thumbnail_to_path` method and occurs once. Replace it with exactly:

````python
    def test_render_thumbnail_to_path(self) -> None:
        self._set_cycles_cpu()
        settings_code = (
            "import bpy\n"
            "scene = bpy.context.scene\n"
            "rd = scene.render\n"
            "result = {\n"
            "    'resolution_x': rd.resolution_x,\n"
            "    'resolution_y': rd.resolution_y,\n"
            "    'resolution_percentage': rd.resolution_percentage,\n"
            "    'use_simplify': rd.use_simplify,\n"
            "    'simplify_subdivision_render': rd.simplify_subdivision_render,\n"
            "    'cycles_samples': scene.cycles.samples,\n"
            "}\n"
        )
        settings_before = self._test_tool("execute_blender_code", {
            "code": settings_code,
        })
        data = self._test_tool("render_thumbnail_to_path", {
            "output_path": "thumb.png",
        })
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["filepath"].endswith("thumb.png"))
        with open(data["filepath"], "rb") as handle:
            header = handle.read(24)
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        source_x = settings_before["resolution_x"]
        source_y = settings_before["resolution_y"]
        if source_x >= source_y:
            expected_size = (320, max(int(source_y * 320 / source_x), 1))
        else:
            expected_size = (max(int(source_x * 320 / source_y), 1), 320)
        self.assertEqual(struct.unpack(">II", header[16:24]), expected_size)
        settings_after = self._test_tool("execute_blender_code", {
            "code": settings_code,
        })
        self.assertEqual(settings_after, settings_before)
````

No other test change is permitted.

Appendix C is the exact disposable error harness. Run it once with canonical Python and the canonical patched tool-code path before the real integration tests. It creates no tracked file.

## Appendix B — exact one-shot runtime builder

Extract this body without fences after Task2 has a committed `R15_SOURCE_PIN`. Invoke it once as `builder.py SOURCE_PIN CONTROLLER_SOURCE DRIVER_SOURCE ALLOCATOR_SOURCE RUNNER_SOURCE OUTPUT_ROOT`. The four sources and output root are canonical absolute paths. `OUTPUT_ROOT` is newly allocated, native 0700, empty, and retained by one directory FD for the whole build.

````python
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path


OLD_PIN = "4309a39646e644261624bfcd2bca669b343b7621"
R14_COMMIT = "deb5426a57748ae4e89e91afe0a1752e4c9fc2b0"
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
        driver = replace(driver, b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md', b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md')
        driver = replace(driver, b'task-7-r14-followup-1-report.md', b'task-7-r15-followup-1-report.md')
        driver = replace(driver, b'.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001', b'.superpowers/sdd/modeling-remediation/r15-evidence/final-retest-r3/attempt-0001', 2)
        driver = replace(driver, OLD_CONTROLLER_SHA.encode(), controller_sha.encode())
        old_topology = b'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
        new_topology = f'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = {R14_COMMIT}\n  test "$(git -C "$FEATURE_ROOT" rev-parse {R14_COMMIT}^)" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'.encode()
        driver = replace(driver, old_topology, new_topology)
        create(root_fd, root, root_fields, created, "driver.sh", driver)

        allocator = allocator_source
        allocator = replace(allocator, b'SOURCE_ID = (16777232, 305390856)', f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode())
        allocator = replace(allocator, f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode(), f'SOURCE_SHA256 = "{controller_sha}"'.encode())
        allocator = replace(allocator, b'PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")', b'PARTS = ("r15-evidence", "final-retest-r3", "attempt-0001")')
        if allocator.count(b"R12") != 11:
            raise RuntimeError("allocator diagnostic anchors differ")
        allocator = allocator.replace(b"R12", b"R15")
        create(root_fd, root, root_fields, created, "r15_allocator.py", allocator)
        allocator_sha = hashlib.sha256(allocator).hexdigest()

        runner = runner_source
        runner = replace(runner, f'ALLOCATOR_SHA256 = "{OLD_ALLOCATOR_SHA}"'.encode(), f'ALLOCATOR_SHA256 = "{allocator_sha}"'.encode())
        old_source_path = b'SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")'
        runner = replace(runner, old_source_path, f'SOURCE_CONTROLLER = Path("{controller_out}")'.encode())
        runner = replace(runner, b'SOURCE_ID = (16777232, 305390856)', f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode())
        runner = replace(runner, f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode(), f'SOURCE_SHA256 = "{controller_sha}"'.encode())
        runner = replace(runner, b'R12_ALLOCATION_GREEN', b'R15_ALLOCATION_GREEN')
        if runner.count(b"R14") != 15:
            raise RuntimeError("runner diagnostic anchors differ")
        runner = runner.replace(b"R14", b"R15")
        create(root_fd, root, root_fields, created, "r15_allocator_runner.py", runner)

        print(f"R15_RUNTIME_GREEN source_pin={pin} controller_sha256={controller_sha} driver_sha256={hashlib.sha256(driver).hexdigest()} allocator_sha256={allocator_sha} runner_sha256={hashlib.sha256(runner).hexdigest()}")
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

## Appendix E — exact Task2 FD and integration primitives

Extract once into the persistent Task2 Python process. These are the only Task2 report allocator, review parser, terminal writer, and integration subprocess functions.

````python
from __future__ import annotations

import hashlib
import os
import signal
import stat
import subprocess
import time
from pathlib import Path


MAX_REPORT = 64 * 1024


def fields(value: os.stat_result) -> tuple[int, ...]:
    return value.st_dev, value.st_ino, value.st_uid, stat.S_IMODE(value.st_mode), value.st_nlink


def allocate(path: Path) -> tuple[int, tuple[int, ...]]:
    parent = path.parent
    if Path(os.path.realpath(parent)) != parent:
        raise RuntimeError("noncanonical report parent")
    parent_info = os.lstat(parent)
    if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid() or stat.S_IMODE(parent_info.st_mode) != 0o700:
        raise RuntimeError("unsafe report parent")
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    fd = -1
    identity: tuple[int, ...] | None = None
    try:
        if fields(os.fstat(parent_fd))[:4] != fields(parent_info)[:4]:
            raise RuntimeError("report parent replaced")
        fd = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent_fd)
        info = os.fstat(fd)
        identity = fields(info)
        os.fsync(parent_fd)
        current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size != 0 or fields(current) != identity or fields(os.fstat(parent_fd))[:4] != fields(parent_info)[:4]:
            raise RuntimeError("unsafe report allocation")
        return fd, identity
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if identity is not None:
            try:
                current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                if (current.st_dev, current.st_ino) == identity[:2]:
                    os.unlink(path.name, dir_fd=parent_fd)
                    os.fsync(parent_fd)
        raise
    finally:
        os.close(parent_fd)


def read_fd(fd: int) -> bytes:
    info = os.fstat(fd)
    if info.st_size > MAX_REPORT:
        raise RuntimeError("report too large")
    raw = os.pread(fd, info.st_size + 1, 0)
    if len(raw) != info.st_size:
        raise RuntimeError("report read differs")
    return raw


def write_all(fd: int, payload: bytes) -> None:
    if b"\x00" in payload or b"\r" in payload:
        raise RuntimeError("unsafe report payload")
    while payload:
        count = os.write(fd, payload)
        if count <= 0:
            raise RuntimeError("short report write")
        payload = payload[count:]


def parse_approval(fd: int, lens: str) -> bytes:
    raw = read_fd(fd)
    raw.decode("utf-8", errors="strict")
    if not raw.endswith(b"\n") or b"\r" in raw or b"\x00" in raw:
        raise RuntimeError("review encoding differs")
    lines = raw[:-1].split(b"\n")
    approved = f"{lens}_REVIEW: APPROVED".encode()
    rejected = f"{lens}_REVIEW: REJECTED".encode()
    if lines.count(approved) != 1 or lines.count(rejected) != 0 or lines[-1] != approved:
        raise RuntimeError(f"{lens} approval differs")
    return raw


def freeze(fd: int, path: Path, allocated: tuple[int, ...]) -> tuple[int, int, int, str]:
    os.fsync(fd)
    info = os.fstat(fd)
    if fields(info) != allocated or fields(os.lstat(path)) != allocated:
        raise RuntimeError("report identity differs")
    raw = read_fd(fd)
    return info.st_dev, info.st_ino, info.st_size, hashlib.sha256(raw).hexdigest()


def terminal_payload(current: bytes, facts: bytes, status: str) -> bytes:
    if status not in {"PASS", "BLOCKED"}:
        raise RuntimeError("terminal status differs")
    if b"\nSTATUS: " in b"\n" + current:
        raise RuntimeError("report already terminal")
    if (current and not current.endswith(b"\n")) or not facts.endswith(b"\n") or any(line.startswith(b"STATUS: ") for line in facts.splitlines()):
        raise RuntimeError("report prefix differs")
    payload = facts + f"STATUS: {status}\n".encode()
    if len(current) + len(payload) > MAX_REPORT:
        raise RuntimeError("terminal report too large")
    return payload


def terminal(fd: int, path: Path, allocated: tuple[int, ...], facts: bytes, status: str) -> tuple[int, int, int, str]:
    try:
        payload = terminal_payload(read_fd(fd), facts, status)
        os.lseek(fd, 0, os.SEEK_END)
        write_all(fd, payload)
        return freeze(fd, path, allocated)
    finally:
        os.close(fd)


def prepare_receipt(fd: int, path: Path, allocated: tuple[int, ...], report_fd: int, report_allocated: tuple[int, ...], facts: bytes) -> tuple[int, int, int, str]:
    current = read_fd(report_fd)
    report_raw = current + terminal_payload(current, facts, "PASS")
    report = report_allocated[0], report_allocated[1], len(report_raw), hashlib.sha256(report_raw).hexdigest()
    payload = (
        f"report_dev: {report[0]}\n"
        f"report_ino: {report[1]}\n"
        f"report_size: {report[2]}\n"
        f"report_sha256: {report[3]}\n"
        f"receipt_dev: {allocated[0]}\n"
        f"receipt_ino: {allocated[1]}\n"
        "STATUS: PASS\n"
    ).encode()
    write_all(fd, payload)
    freeze(fd, path, allocated)
    return report


def commit_receipt(fd: int, path: Path, allocated: tuple[int, ...]) -> str:
    try:
        if fields(os.fstat(fd)) != allocated or fields(os.lstat(path)) != allocated:
            raise RuntimeError("receipt identity differs")
        os.fchmod(fd, 0o400)
        os.fsync(fd)
        committed = allocated[0], allocated[1], allocated[2], 0o400, allocated[4]
        info = os.fstat(fd)
        if fields(info) != committed or fields(os.lstat(path)) != committed:
            raise RuntimeError("receipt commit differs")
        raw = read_fd(fd)
        return hashlib.sha256(raw).hexdigest()
    finally:
        os.close(fd)


def stop_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise RuntimeError("integration process group survived SIGKILL")


def run_integration(argv: list[str], env: dict[str, str], timeout: float = 900) -> tuple[int, str]:
    executable = Path(argv[0])
    if Path(os.path.realpath(executable)) != executable:
        raise RuntimeError("integration executable differs")
    executable_info = os.lstat(executable)
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, start_new_session=True)
    output = ""
    problem: BaseException | None = None
    try:
        current = os.lstat(executable)
        if os.getpgid(process.pid) != process.pid or (current.st_dev, current.st_ino) != (executable_info.st_dev, executable_info.st_ino):
            raise RuntimeError("integration process identity differs")
        output, _ = process.communicate(timeout=timeout)
    except BaseException as error:
        problem = error
    cleanup: list[BaseException] = []
    try:
        running = process.poll() is None
    except BaseException as error:
        cleanup.append(error)
        running = True
    if running:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except BaseException as error:
            if not isinstance(error, ProcessLookupError):
                cleanup.append(error)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except BaseException as error:
                if not isinstance(error, ProcessLookupError):
                    cleanup.append(error)
            try:
                process.wait(timeout=10)
            except BaseException as error:
                cleanup.append(error)
        except BaseException as error:
            cleanup.append(error)
    try:
        stop_group(process.pid)
    except BaseException as error:
        cleanup.append(error)
    try:
        if process.stdout is not None:
            process.stdout.close()
    except BaseException as error:
        cleanup.append(error)
    if cleanup:
        raise RuntimeError("integration cleanup failed") from cleanup[0]
    if problem is not None:
        raise problem
    return process.returncode, output


def selfcheck(root: Path) -> None:
    review = root / "review.md"
    review_fd, review_id = allocate(review)
    write_all(review_fd, b"prose E402-REJECTED\nSPEC_REVIEW: APPROVED\n")
    parse_approval(review_fd, "SPEC")
    freeze(review_fd, review, review_id)
    os.close(review_fd)
    try:
        allocate(review)
    except FileExistsError:
        pass
    else:
        raise RuntimeError("allocation collision accepted")
    duplicate = root / "duplicate.md"
    duplicate_fd, _ = allocate(duplicate)
    write_all(duplicate_fd, b"SPEC_REVIEW: APPROVED\nSPEC_REVIEW: APPROVED\n")
    try:
        parse_approval(duplicate_fd, "SPEC")
    except RuntimeError:
        pass
    else:
        raise RuntimeError("duplicate approval accepted")
    os.close(duplicate_fd)
    report = root / "report.md"
    report_fd, report_id = allocate(report)
    receipt = root / "receipt.md"
    receipt_fd, receipt_id = allocate(receipt)
    report_expected = prepare_receipt(receipt_fd, receipt, receipt_id, report_fd, report_id, b"fact: green\n")
    report_result = terminal(report_fd, report, report_id, b"fact: green\n", "PASS")
    if report_result != report_expected:
        raise RuntimeError("terminal prediction differs")
    receipt_result = commit_receipt(receipt_fd, receipt, receipt_id)
    expected_receipt = f"report_dev: {report_result[0]}\nreport_ino: {report_result[1]}\nreport_size: {report_result[2]}\nreport_sha256: {report_result[3]}\nreceipt_dev: {receipt_id[0]}\nreceipt_ino: {receipt_id[1]}\nSTATUS: PASS\n".encode()
    if receipt.read_bytes() != expected_receipt or stat.S_IMODE(os.lstat(receipt).st_mode) != 0o400 or receipt_result != hashlib.sha256(expected_receipt).hexdigest():
        raise RuntimeError("terminal receipt differs")
    replaced_report = root / "replaced-report.md"
    replaced_report_fd, replaced_report_id = allocate(replaced_report)
    replaced_receipt = root / "replaced-receipt.md"
    replaced_backup = root / "replaced-receipt.backup"
    replaced_receipt_fd, replaced_receipt_id = allocate(replaced_receipt)
    prepare_receipt(replaced_receipt_fd, replaced_receipt, replaced_receipt_id, replaced_report_fd, replaced_report_id, b"fact: green\n")
    os.rename(replaced_receipt, replaced_backup)
    foreign_fd, foreign_id = allocate(replaced_receipt)
    write_all(foreign_fd, b"foreign\n")
    freeze(foreign_fd, replaced_receipt, foreign_id)
    os.close(foreign_fd)
    try:
        commit_receipt(replaced_receipt_fd, replaced_receipt, replaced_receipt_id)
    except RuntimeError as error:
        if str(error) != "receipt identity differs":
            raise
    else:
        raise RuntimeError("replaced receipt accepted")
    if fields(os.lstat(replaced_receipt)) != foreign_id or replaced_receipt.read_bytes() != b"foreign\n" or fields(os.lstat(replaced_backup)) != replaced_receipt_id:
        raise RuntimeError("replaced receipt changed")
    malformed = root / "malformed.md"
    malformed_fd, malformed_id = allocate(malformed)
    try:
        terminal(malformed_fd, malformed, malformed_id, b"STATUS: PASS\n", "PASS")
    except RuntimeError:
        pass
    else:
        raise RuntimeError("injected terminal accepted")
    try:
        os.fstat(malformed_fd)
    except OSError:
        pass
    else:
        raise RuntimeError("failed terminal FD remained open")
    if malformed.read_bytes():
        raise RuntimeError("failed terminal wrote bytes")
    unverified_receipt = root / "unverified-receipt.md"
    unverified_receipt_fd, unverified_receipt_id = allocate(unverified_receipt)
    prepare_receipt(unverified_receipt_fd, unverified_receipt, unverified_receipt_id, replaced_report_fd, replaced_report_id, b"fact: written\n")
    try:
        terminal(replaced_report_fd, review, replaced_report_id, b"fact: written\n", "PASS")
    except RuntimeError as error:
        if str(error) != "report identity differs":
            raise
    else:
        raise RuntimeError("post-append failure was swallowed")
    try:
        os.fstat(replaced_report_fd)
    except OSError:
        pass
    else:
        raise RuntimeError("unverified terminal FD remained open")
    os.close(unverified_receipt_fd)
    if not replaced_report.read_bytes().endswith(b"STATUS: PASS\n") or fields(os.lstat(unverified_receipt)) != unverified_receipt_id:
        raise RuntimeError("unverified terminal boundary differs")
    argv = ["/Users/yeminjie/.local/share/uv/python/cpython-3.14.7-macos-aarch64-none/bin/python3.14", "-c", "import time; time.sleep(0.05); print(123)"]
    status, output = run_integration(argv, dict(os.environ))
    if status or output != "123\n":
        raise RuntimeError("process-group selfcheck differs")
    timeout_argv = [argv[0], "-c", "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"]
    try:
        run_integration(timeout_argv, dict(os.environ), timeout=0.1)
    except subprocess.TimeoutExpired:
        pass
    else:
        raise RuntimeError("integration timeout was accepted")


if __name__ == "__main__":
    if len(os.sys.argv) != 3 or os.sys.argv[1] != "--selfcheck":
        raise SystemExit("usage: task2_primitives.py --selfcheck ROOT")
    selfcheck(Path(os.sys.argv[2]))
    print("R15_TASK2_PRIMITIVES_GREEN fd=1 parser=1 terminal=1 process_group=1")
````

## Appendix D — exact runtime equivalence gate

Invoke once with canonical Python 3.13 as `runtime_gate.py RUNTIME_ROOT R15_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER`. Exact reverse equality transfers the already-certified R12 allocator and R14 runner negative matrices; the gate does not invoke either one.

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
R14_COMMIT = "deb5426a57748ae4e89e91afe0a1752e4c9fc2b0"


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
        raise SystemExit("usage: runtime_gate.py RUNTIME_ROOT R15_SOURCE_PIN OLD_CONTROLLER OLD_DRIVER OLD_ALLOCATOR OLD_RUNNER")
    root = Path(sys.argv[1])
    expected_pin = sys.argv[2]
    if re.fullmatch(r"[0-9a-f]{40}", expected_pin) is None or expected_pin == OLD_PIN:
        raise RuntimeError("expected source pin differs")
    old_controller_path, old_driver_path, old_allocator_path, old_runner_path = map(Path, sys.argv[3:])
    root_info = os.lstat(root)
    if Path(os.path.realpath(root)) != root or not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != os.getuid() or stat.S_IMODE(root_info.st_mode) != 0o700:
        raise RuntimeError("unsafe runtime root")
    names = sorted(path.name for path in root.iterdir())
    if names != ["driver.sh", "r15_allocator.py", "r15_allocator_runner.py", "r3_controller.py"]:
        raise RuntimeError("runtime leaves differ")
    controller, controller_info = owned(root / "r3_controller.py", 0o600)
    driver, _ = owned(root / "driver.sh", 0o600)
    allocator, _ = owned(root / "r15_allocator.py", 0o600)
    runner, _ = owned(root / "r15_allocator_runner.py", 0o600)
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
    restored_driver = one(restored_driver, b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r15-deferred-thumbnail.md', b'docs/superpowers/plans/2026-08-14-official-blender-mcp-r14-allocator-args.md')
    restored_driver = one(restored_driver, b'task-7-r15-followup-1-report.md', b'task-7-r14-followup-1-report.md')
    restored_driver = one(restored_driver, b'.superpowers/sdd/modeling-remediation/r15-evidence/final-retest-r3/attempt-0001', b'.superpowers/sdd/modeling-remediation/r12-evidence/final-retest-r3/attempt-0001', 2)
    restored_driver = one(restored_driver, controller_sha.encode(), OLD_CONTROLLER_SHA.encode())
    new_topology = f'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = {R14_COMMIT}\n  test "$(git -C "$FEATURE_ROOT" rev-parse {R14_COMMIT}^)" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'.encode()
    old_topology = b'  test "$(git -C "$FEATURE_ROOT" rev-parse "$R3_PLAN_COMMIT^")" = c0f38156cad28996cfddcabb1cf775ae84983cf5\n'
    restored_driver = one(restored_driver, new_topology, old_topology)
    if restored_driver != old_driver:
        raise RuntimeError("driver reversal differs")

    restored_allocator = allocator
    restored_allocator = one(restored_allocator, f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode(), b'SOURCE_ID = (16777232, 305390856)')
    restored_allocator = one(restored_allocator, f'SOURCE_SHA256 = "{controller_sha}"'.encode(), f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode())
    restored_allocator = one(restored_allocator, b'PARTS = ("r15-evidence", "final-retest-r3", "attempt-0001")', b'PARTS = ("r12-evidence", "final-retest-r3", "attempt-0001")')
    if restored_allocator.count(b"R15") != 11:
        raise RuntimeError("allocator diagnostic count differs")
    restored_allocator = restored_allocator.replace(b"R15", b"R12")
    if restored_allocator != old_allocator:
        raise RuntimeError("allocator reversal differs")

    allocator_sha = hashlib.sha256(allocator).hexdigest()
    restored_runner = runner
    restored_runner = one(restored_runner, f'ALLOCATOR_SHA256 = "{allocator_sha}"'.encode(), f'ALLOCATOR_SHA256 = "{OLD_ALLOCATOR_SHA}"'.encode())
    restored_runner = one(restored_runner, f'SOURCE_CONTROLLER = Path("{root / "r3_controller.py"}")'.encode(), b'SOURCE_CONTROLLER = Path("/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.superpowers/sdd/modeling-remediation/r11-live-runtime/r3_controller.py")')
    restored_runner = one(restored_runner, f'SOURCE_ID = ({controller_info.st_dev}, {controller_info.st_ino})'.encode(), b'SOURCE_ID = (16777232, 305390856)')
    restored_runner = one(restored_runner, f'SOURCE_SHA256 = "{controller_sha}"'.encode(), f'SOURCE_SHA256 = "{OLD_CONTROLLER_SHA}"'.encode())
    restored_runner = one(restored_runner, b'R15_ALLOCATION_GREEN', b'R12_ALLOCATION_GREEN')
    if restored_runner.count(b"R15") != 15:
        raise RuntimeError("runner diagnostic count differs")
    restored_runner = restored_runner.replace(b"R15", b"R14")
    if restored_runner != old_runner:
        raise RuntimeError("runner reversal differs")

    for raw, path in ((controller, root / "r3_controller.py"), (allocator, root / "r15_allocator.py"), (runner, root / "r15_allocator_runner.py")):
        compile(raw, str(path), "exec")
    ruff = subprocess.run(["/Users/yeminjie/.local/bin/uvx", "--quiet", "ruff@0.16.2", "check", "--no-cache", "--isolated", "--target-version", "py313", "--select", "E4,E7,E9,F", str(root / "r3_controller.py"), str(root / "r15_allocator.py"), str(root / "r15_allocator_runner.py")], text=True, capture_output=True, timeout=60)
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
        compile(body, f"<r15-heredoc-{number}>", "exec")
    anchor = b'"$ATTEMPT_ROOT/r3_controller.py" run \\\n'
    if driver.count(anchor) != 1:
        raise RuntimeError("driver run count differs")
    start = driver.index(anchor)
    command = driver[start:driver.index(b" || R3_RUN_EXIT=$?", start)]
    if b"<" in command:
        raise RuntimeError("driver stdin redirect differs")
    print("R15_RUNTIME_GATE_GREEN controller=1 driver=1 allocator_equivalent=1 runner_equivalent=1 probe=1 static=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## Appendix C — exact disposable deferred-restore regression

Invoke once as `python3.14 fault_harness.py PATCHED_TOOLCODE`. `PATCHED_TOOLCODE` must be the canonical absolute implementation path with the post-patch identity already bound through a no-follow descriptor. This script imports no Blender package and starts no process.

````python
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path


class Values:
    def __init__(self, **values: object) -> None:
        object.__setattr__(self, "_fail_once", None)
        for key, value in values.items():
            object.__setattr__(self, key, value)

    def fail_once(self, name: str) -> None:
        object.__setattr__(self, "_fail_once", name)

    def __setattr__(self, name: str, value: object) -> None:
        if object.__getattribute__(self, "_fail_once") == name:
            object.__setattr__(self, "_fail_once", None)
            raise ValueError("injected assignment failure")
        object.__setattr__(self, name, value)


def state(render: Values, cycles: Values) -> tuple[object, ...]:
    return (
        render.filepath,
        render.resolution_x,
        render.resolution_y,
        render.resolution_percentage,
        render.use_simplify,
        render.simplify_subdivision_render,
        cycles.samples,
    )


def run_case(module: types.ModuleType, mode: str) -> None:
    render = Values(
        filepath="old.png",
        resolution_x=640,
        resolution_y=640,
        resolution_percentage=75,
        use_simplify=False,
        simplify_subdivision_render=2,
        engine="CYCLES",
    )
    cycles = Values(samples=64)
    before = state(render, cycles)
    deferred_calls: list[list[tuple[object, str, object]]] = []

    def deferred(_job: str, output: str, restore_attrs: list[tuple[object, str, object]] | None = None):
        if restore_attrs is None:
            raise RuntimeError("missing restore attributes")
        deferred_calls.append(restore_attrs)

        def finish() -> dict[str, object]:
            for obj, attr, value in reversed(restore_attrs):
                setattr(obj, attr, value)
            return {"status": "ok", "filepath": output}

        return finish

    class RenderOperator:
        def render(self, *_args: object, **_kwargs: object) -> None:
            if mode == "render_error":
                raise RuntimeError("injected render failure")

    fake_bpy = types.SimpleNamespace(
        app=types.SimpleNamespace(background=False, tempdir="/tmp/r15-fault"),
        context=types.SimpleNamespace(scene=types.SimpleNamespace(render=render, cycles=cycles, eevee=Values())),
        ops=types.SimpleNamespace(render=RenderOperator()),
    )
    module._deferred_tool_check_for_file_output = deferred
    sys.modules["bpy"] = fake_bpy
    if mode == "assign_error":
        render.fail_once("resolution_y")
        try:
            module.main(module.Params("thumb.png"))
        except ValueError as error:
            if str(error) != "injected assignment failure":
                raise
        else:
            raise RuntimeError("assignment failure was swallowed")
        if state(render, cycles) != before or deferred_calls:
            raise RuntimeError("assignment rollback differs")
        return
    result = module.main(module.Params("thumb.png"))
    if mode == "render_error":
        if result.status != "error" or result.message != "injected render failure" or state(render, cycles) != before or deferred_calls:
            raise RuntimeError("render rollback differs")
        return
    expected_assigned = ("/tmp/r15-fault/blender_mcp/thumb.png", 320, 320, 100, True, 1, 16)
    if not callable(result) or state(render, cycles) != expected_assigned or len(deferred_calls) != 1:
        raise RuntimeError("deferred assignment differs")
    finished = result()
    if finished.get("status") != "ok" or state(render, cycles) != before:
        raise RuntimeError("deferred restoration differs")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fault_harness.py PATCHED_TOOLCODE")
    path = Path(sys.argv[1])
    if Path(os.path.realpath(path)) != path:
        raise RuntimeError("tool-code path differs")
    name = "_r15_thumbnail_fault_harness"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None or name in sys.modules:
        raise RuntimeError("module loader differs")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        for mode in ("assign_error", "render_error", "deferred"):
            run_case(module, mode)
    finally:
        if sys.modules.get(name) is module:
            del sys.modules[name]
        sys.modules.pop("bpy", None)
    print("R15_DEFERRED_RESTORE_GREEN cases=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````
