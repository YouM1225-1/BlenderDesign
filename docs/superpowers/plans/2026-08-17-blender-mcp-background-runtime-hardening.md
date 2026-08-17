# Blender MCP Background Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Blender MCP background execution fail closed on forged results, terminate ordinary descendant processes, bound output, validate input files, and prevent accidental writes to the source `.blend`.

**Architecture:** Keep trusted file-summary tools simple: they inspect the exact on-disk file supplied by the caller and never synchronize through the live Blender process. Route arbitrary background Python through a disposable snapshot whose path is different from the source, supervise Blender as a process group, and receive the final result through a bounded result file rather than stdout markers. This is fault containment for trusted local automation, not a security sandbox for hostile Python.

**Tech Stack:** Python 3.10+, `unittest`, Blender 5.2 LTS, MCP/FastMCP 1.28.1, standard-library subprocess/threading/tempfile primitives.

## Global Constraints

- Start from official upstream `https://projects.blender.org/lab/blender_mcp.git` commit `4309a39646e644261624bfcd2bca669b343b7621`.
- Make upstream changes in an isolated Git worktree created at execution time with `superpowers:using-git-worktrees`.
- Add no runtime dependency.
- Preserve the existing MCP tool names and required arguments.
- Keep `execute_blender_code_for_cli` marked destructive.
- File-summary `_for_cli` tools inspect disk state only and must not call the live Blender add-on.
- Arbitrary background code always opens a disposable snapshot, never the caller's source path.
- A dirty live-file snapshot may invoke Blender `save_pre` and `save_post`; document this and do not describe it as read-only.
- Cap stdout at `1 MiB`, stderr at `1 MiB`, and the JSON result envelope at `10 MiB`.
- Use a `120` second internal Blender timeout and a `2` second termination grace period.
- Process-group termination is fault containment only; deliberately hostile Python remains out of scope.
- The result file is an integrity boundary against accidental stdout spoofing, not against code that deliberately discovers and rewrites its own process arguments or open files.
- Preserve Blender 5.2 LTS, Python 3.13.13, and macOS arm64 as the distribution acceptance platform.

---

## File Structure

- Modify `mcp/blmcp/tools_helpers/blender_cli.py`: path validation, bounded process supervisor, result-file protocol, private snapshot context.
- Modify `mcp/blmcp/tools_helpers/connection.py`: align the live socket timeout with the background timeout.
- Modify `mcp/blmcp/tools/execute_blender_code.py`: route arbitrary CLI execution through a private snapshot and document the boundary.
- Modify `mcp/blmcp/tools/get_blendfile_summary_datablocks.py`: inspect the supplied disk file directly.
- Modify `mcp/blmcp/tools/get_blendfile_summary_missing_files.py`: inspect the supplied disk file directly.
- Modify `mcp/blmcp/tools/get_blendfile_summary_of_linked_libraries.py`: inspect the supplied disk file directly.
- Modify `mcp/blmcp/tools/get_blendfile_summary_path_info.py`: inspect the supplied disk file directly.
- Modify `mcp/blmcp/tools/get_blendfile_summary_usage_guess.py`: inspect the supplied disk file directly.
- Create `tests/test_blender_cli.py`: fast fake-Blender regression and adversarial tests.
- Modify `tests/test_blender_mcp_with_blender.py`: real-Blender source-isolation and relative-resource tests.
- Modify `mcp/blmcp/data/prompts.yml`: make disk reads and disposable batch work prefer background tools while current-scene/UI work remains live.
- Modify `tests/test_mcp_server.py`: freeze the routing guidance in server startup instructions.
- Modify `Makefile`: include the new unit test in `make test`.
- Regenerate `readme_tools.rst`: publish exact disk/snapshot semantics.

---

### Task 1: Add path-validation and result-protocol regression tests

**Files:**
- Create: `tests/test_blender_cli.py`
- Modify: `Makefile:83-90`

**Interfaces:**
- Consumes: existing `run_blender_cli(blend_file: str, code: str, timeout: float = 120.0) -> dict[str, object]`.
- Produces: reusable `_fake_blender()` test fixture and failing tests for `_validate_blend_file()` and the dedicated result protocol.

- [ ] **Step 1: Create the test module with a fake Blender executable**

```python
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

__all__ = ()

import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

_REPO_DIR = Path(__file__).resolve().parents[1]
_MCP_DIR = _REPO_DIR / "mcp"
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

from blmcp.tools_helpers.blender_cli import run_blender_cli


class TestBlenderCli(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        self.blend = self.root / "scene.blend"
        self.blend.write_bytes(b"BLENDER")
        self.fake_blender = self.root / "fake_blender"
        self.fake_blender.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "index = sys.argv.index('--python-expr')\n"
            "exec(sys.argv[index + 1], {'__name__': '__main__'})\n",
            encoding="utf-8",
        )
        self.fake_blender.chmod(
            self.fake_blender.stat().st_mode | stat.S_IXUSR
        )
        self.env = mock.patch.dict(
            os.environ,
            {"BLENDER_PATH": str(self.fake_blender)},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_rejects_empty_missing_directory_and_non_blend_paths(self) -> None:
        directory = self.root / "folder"
        directory.mkdir()
        text = self.root / "scene.txt"
        text.write_text("not a blend", encoding="utf-8")
        for value, message in (
            ("", "blend_file must not be empty"),
            (str(self.root / "missing.blend"), "does not exist"),
            (str(directory), "is not a file"),
            (str(text), "must end with .blend"),
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, message):
                    run_blender_cli(value, "result = {}")

    def test_stdout_result_marker_cannot_spoof_result(self) -> None:
        result = run_blender_cli(
            str(self.blend),
            "print('__BLMCP_RESULT__{\"spoofed\": true}')\n"
            "result = {'real': True}",
        )
        self.assertEqual(result, {"real": True})

    def test_nonzero_exit_cannot_return_forged_success(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exited with status 7"):
            run_blender_cli(
                str(self.blend),
                "import os\n"
                "print('__BLMCP_RESULT__{\"spoofed\": true}', flush=True)\n"
                "os._exit(7)",
            )

    def test_python_exception_is_reported_from_result_envelope(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Blender error: broken"):
            run_blender_cli(str(self.blend), "raise ValueError('broken')")

    def test_json_encoding_error_is_reported_from_result_envelope(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Blender error: keys must be"):
            run_blender_cli(str(self.blend), "result = {(1, 2): 'value'}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Register the test in `Makefile`**

Insert this line after `tests/test_tool_listing.py` in the `test` target:

```make
	$(PYTHON) tests/test_blender_cli.py
```

- [ ] **Step 3: Run the focused tests and confirm the attack still succeeds before implementation**

Run:

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
```

Expected: the invalid-path cases and both spoofing cases fail against the current stdout-marker implementation.

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_blender_cli.py Makefile
git commit -m "test: expose background CLI protocol failures"
```

---

### Task 2: Replace stdout markers with a validated result envelope

**Files:**
- Modify: `mcp/blmcp/tools_helpers/blender_cli.py:9-95`
- Test: `tests/test_blender_cli.py`

**Interfaces:**
- Consumes: Task 1 tests.
- Produces: `_validate_blend_file(blend_file: str) -> str`, `_wrapper_code(code: str, result_path: str) -> str`, and a result-file-based `run_blender_cli()`.

- [ ] **Step 1: Replace marker constants with bounded-result constants and path validation**

```python
_CLI_TIMEOUT = 120.0
_MAX_RESULT_BYTES = 10 * 1024 * 1024


def _validate_blend_file(blend_file: str) -> str:
    if not blend_file.strip():
        raise ValueError("blend_file must not be empty")
    path = os.path.realpath(os.path.abspath(os.path.expanduser(blend_file)))
    if not os.path.exists(path):
        raise ValueError("blend_file does not exist: {:s}".format(path))
    if not os.path.isfile(path):
        raise ValueError("blend_file is not a file: {:s}".format(path))
    if not path.lower().endswith(".blend"):
        raise ValueError("blend_file must end with .blend: {:s}".format(path))
    return path
```

- [ ] **Step 2: Add the complete wrapper generator**

```python
def _wrapper_code(code: str, result_path: str) -> str:
    return (
        "import json, os\n"
        "try:\n"
        "    _ns = {'result': {}}\n"
        "    exec(" + repr(code) + ", _ns)\n"
        "    _result = _ns['result']\n"
        "    if not isinstance(_result, dict):\n"
        "        raise TypeError('The `result` variable must be a dict, not ' + "
        "type(_result).__name__)\n"
        "    _encoded = json.dumps({'ok': True, 'result': _result}, "
        "default=repr).encode('utf-8')\n"
        "except Exception as _ex:\n"
        "    _encoded = json.dumps({'ok': False, 'error': str(_ex)}).encode('utf-8')\n"
        "if len(_encoded) > " + str(_MAX_RESULT_BYTES) + ":\n"
        "    _encoded = json.dumps({'ok': False, 'error': "
        "'Result exceeds " + str(_MAX_RESULT_BYTES) + " byte limit'}).encode('utf-8')\n"
        "with open(" + repr(result_path) + ", 'xb') as _fh:\n"
        "    _fh.write(_encoded)\n"
        "    _fh.flush()\n"
        "    os.fsync(_fh.fileno())\n"
    )
```

- [ ] **Step 3: Change `run_blender_cli()` to use a private result directory and verify exit status before parsing**

```python
def run_blender_cli(
    blend_file: str,
    code: str,
    timeout: float = _CLI_TIMEOUT,
) -> dict[str, object]:
    blender = _get_blender_path()
    validated_blend = _validate_blend_file(blend_file)
    with tempfile.TemporaryDirectory(prefix="blmcp-result-") as result_dir:
        result_path = os.path.join(result_dir, "result.json")
        wrapper = _wrapper_code(code, result_path)
        try:
            proc = subprocess.run(
                [blender, "--background", validated_blend, "--python-expr", wrapper],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as ex:
            raise RuntimeError(
                "Blender CLI timed out after {:.0f}s".format(timeout)
            ) from ex
        except FileNotFoundError as ex:
            raise RuntimeError(
                "Blender executable not found at '{:s}'. "
                "Set BLENDER_PATH to the correct path.".format(blender)
            ) from ex
        if proc.returncode != 0:
            raise RuntimeError(
                "Blender CLI exited with status {:d}: {:s}".format(
                    proc.returncode, proc.stderr[-4096:]
                )
            )
        if not os.path.isfile(result_path):
            raise RuntimeError("Blender CLI exited without a result envelope")
        if os.path.getsize(result_path) > _MAX_RESULT_BYTES:
            raise RuntimeError(
                "Blender result exceeds {:d} byte limit".format(_MAX_RESULT_BYTES)
            )
        with open(result_path, encoding="utf-8") as fh:
            envelope = json.load(fh)
        if (
            isinstance(envelope, dict)
            and set(envelope) == {"ok", "error"}
            and envelope.get("ok") is False
            and isinstance(envelope.get("error"), str)
        ):
            raise RuntimeError("Blender error: {:s}".format(envelope["error"]))
        if (
            not isinstance(envelope, dict)
            or set(envelope) != {"ok", "result"}
            or envelope.get("ok") is not True
        ):
            raise RuntimeError("Invalid Blender result envelope")
        result = envelope["result"]
        if not isinstance(result, dict):
            raise RuntimeError("Blender result is not a dictionary")
        return result
```

Add `import tempfile` at the top of the module and delete `_RESULT_PREFIX` and `_ERROR_PREFIX`.

- [ ] **Step 4: Run the focused tests**

Run:

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
```

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit the result protocol**

```bash
git add mcp/blmcp/tools_helpers/blender_cli.py tests/test_blender_cli.py
git commit -m "fix: validate background Blender results"
```

---

### Task 3: Add bounded output and process-group termination

**Files:**
- Modify: `mcp/blmcp/tools_helpers/blender_cli.py:14-110`
- Test: `tests/test_blender_cli.py`

**Interfaces:**
- Consumes: Task 2 `_wrapper_code()` and result envelope.
- Produces: `_run_process(argv: list[str], timeout: float) -> _ProcessResult` with bounded stdout/stderr and ordinary descendant cleanup.

- [ ] **Step 1: Add failing tests for timeout descendants and output overflow**

Add these imports and tests to `tests/test_blender_cli.py`:

```python
import signal
import time


    @unittest.skipUnless(os.name == "posix", "process-group test is POSIX-only")
    def test_timeout_terminates_ordinary_descendants(self) -> None:
        pid_path = self.root / "child.pid"
        with self.assertRaisesRegex(RuntimeError, "timed out after 1s"):
            run_blender_cli(
                str(self.blend),
                "import pathlib, subprocess, time\n"
                "child = subprocess.Popen(['/bin/sleep', '5'])\n"
                "pathlib.Path(" + repr(str(pid_path)) + ").write_text(str(child.pid))\n"
                "time.sleep(10)\nresult = {}",
                timeout=1.0,
            )
        child_pid = int(pid_path.read_text(encoding="utf-8"))
        for _index in range(40):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            os.kill(child_pid, signal.SIGTERM)
            self.fail("ordinary child survived Blender process-group timeout")

    def test_stdout_limit_terminates_background_job(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "stdout exceeds 1048576 byte limit"):
            run_blender_cli(
                str(self.blend),
                "print('x' * (2 * 1024 * 1024), flush=True)\nresult = {}",
            )

    def test_result_limit_returns_bounded_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Result exceeds 10485760 byte limit"):
            run_blender_cli(
                str(self.blend),
                "result = {'payload': 'x' * (11 * 1024 * 1024)}",
            )

    @unittest.skipUnless(os.name == "posix", "process-group test is POSIX-only")
    def test_exited_parent_does_not_leave_pipe_holding_child(self) -> None:
        pid_path = self.root / "orphan.pid"
        started = time.monotonic()
        result = run_blender_cli(
            str(self.blend),
            "import pathlib, subprocess\n"
            "child = subprocess.Popen(['/bin/sleep', '5'])\n"
            "pathlib.Path(" + repr(str(pid_path)) + ").write_text(str(child.pid))\n"
            "result = {'finished': True}",
        )
        self.assertEqual(result, {"finished": True})
        self.assertLess(time.monotonic() - started, 3.0)
        child_pid = int(pid_path.read_text(encoding="utf-8"))
        for _index in range(40):
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            os.kill(child_pid, signal.SIGTERM)
            self.fail("pipe-holding child survived Blender exit")
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
```

Expected: the descendant and stdout-cap tests fail against `subprocess.run(capture_output=True)`.

- [ ] **Step 3: Add the process result type and bounded reader**

```python
from collections.abc import Generator
from typing import BinaryIO, NamedTuple
import signal
import threading
import time

_MAX_STDOUT_BYTES = 1024 * 1024
_MAX_STDERR_BYTES = 1024 * 1024
_TERMINATE_GRACE_SECONDS = 2.0
_READ_CHUNK_BYTES = 64 * 1024


class _ProcessResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def _drain_stream(
    stream: BinaryIO,
    limit: int,
    chunks: list[bytes],
    overflow: threading.Event,
) -> None:
    total = 0
    while chunk := stream.read(_READ_CHUNK_BYTES):
        remaining = limit - total
        if remaining > 0:
            chunks.append(chunk[:remaining])
        total += len(chunk)
        if total > limit:
            overflow.set()
```

- [ ] **Step 4: Add complete process-group termination and supervision**

```python
def _terminate_process_group(proc: "subprocess.Popen[bytes]") -> None:
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        if proc.poll() is None:
            try:
                proc.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        deadline = time.monotonic() + _TERMINATE_GRACE_SECONDS
        while time.monotonic() < deadline:
            try:
                os.killpg(proc.pid, 0)
            except ProcessLookupError:
                if proc.poll() is None:
                    proc.wait()
                return
            time.sleep(0.02)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if proc.poll() is None:
            proc.wait()
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _run_process(argv: list[str], timeout: float) -> _ProcessResult:
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name == "posix"),
        )
    except FileNotFoundError as ex:
        raise RuntimeError(
            "Blender executable not found at '{:s}'. "
            "Set BLENDER_PATH to the correct path.".format(argv[0])
        ) from ex
    assert proc.stdout is not None
    assert proc.stderr is not None
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_overflow = threading.Event()
    stderr_overflow = threading.Event()
    readers = (
        threading.Thread(
            target=_drain_stream,
            args=(proc.stdout, _MAX_STDOUT_BYTES, stdout_chunks, stdout_overflow),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_stream,
            args=(proc.stderr, _MAX_STDERR_BYTES, stderr_chunks, stderr_overflow),
            daemon=True,
        ),
    )
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    failure: str | None = None
    terminated = False
    while proc.poll() is None:
        if stdout_overflow.is_set():
            failure = "stdout exceeds {:d} byte limit".format(_MAX_STDOUT_BYTES)
            break
        if stderr_overflow.is_set():
            failure = "stderr exceeds {:d} byte limit".format(_MAX_STDERR_BYTES)
            break
        if time.monotonic() >= deadline:
            failure = "Blender CLI timed out after {:.0f}s".format(timeout)
            break
        time.sleep(0.02)
    if failure is not None:
        _terminate_process_group(proc)
        terminated = True
    for reader in readers:
        reader.join(timeout=0.1)
    if any(reader.is_alive() for reader in readers):
        _terminate_process_group(proc)
        terminated = True
        for reader in readers:
            reader.join(timeout=_TERMINATE_GRACE_SECONDS)
        if any(reader.is_alive() for reader in readers):
            raise RuntimeError("Blender output reader did not terminate")
    if failure is None and stdout_overflow.is_set():
        failure = "stdout exceeds {:d} byte limit".format(_MAX_STDOUT_BYTES)
    if failure is None and stderr_overflow.is_set():
        failure = "stderr exceeds {:d} byte limit".format(_MAX_STDERR_BYTES)
    if failure is not None and not terminated:
        _terminate_process_group(proc)
    stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
    if failure is not None:
        raise RuntimeError(failure)
    assert proc.returncode is not None
    return _ProcessResult(proc.returncode, stdout, stderr)
```

- [ ] **Step 5: Make `run_blender_cli()` call `_run_process()`**

Replace the `subprocess.run()` block with:

```python
        proc = _run_process(
            [blender, "--background", validated_blend, "--python-expr", wrapper],
            timeout,
        )
```

Keep the Task 2 return-code and result-envelope checks unchanged.

- [ ] **Step 6: Run focused tests and static checks**

Run:

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
ruff check mcp/blmcp/tools_helpers/blender_cli.py tests/test_blender_cli.py
python -m mypy --exclude 'data/api/examples/' mcp/blmcp/tools_helpers/blender_cli.py
```

Expected: all tests pass and both static checks report no errors.

- [ ] **Step 7: Commit process supervision**

```bash
git add mcp/blmcp/tools_helpers/blender_cli.py tests/test_blender_cli.py
git commit -m "fix: bound and terminate background Blender jobs"
```

---

### Task 4: Separate trusted disk reads from arbitrary private-snapshot execution

**Files:**
- Modify: `mcp/blmcp/tools_helpers/blender_cli.py:9-190`
- Modify: `mcp/blmcp/tools/execute_blender_code.py:11-55`
- Modify: `mcp/blmcp/tools/get_blendfile_summary_datablocks.py:16-48`
- Modify: `mcp/blmcp/tools/get_blendfile_summary_missing_files.py:16-49`
- Modify: `mcp/blmcp/tools/get_blendfile_summary_of_linked_libraries.py:16-48`
- Modify: `mcp/blmcp/tools/get_blendfile_summary_path_info.py:16-48`
- Modify: `mcp/blmcp/tools/get_blendfile_summary_usage_guess.py:16-48`
- Test: `tests/test_blender_cli.py`

**Interfaces:**
- Consumes: bounded `run_blender_cli()` from Task 3 and `send_code()`.
- Produces: `private_blend_for_cli(blend_file: str) -> Generator[str, None, None]`; trusted summary tools call `run_blender_cli()` directly.

- [ ] **Step 1: Add private-snapshot tests**

Add imports and tests:

```python
import ast
from concurrent.futures import ThreadPoolExecutor
from blmcp.tools_helpers.blender_cli import private_blend_for_cli


    def test_private_snapshots_are_unique_and_cleaned(self) -> None:
        def use_snapshot() -> tuple[str, bool]:
            with private_blend_for_cli(str(self.blend)) as private:
                return private, Path(private).is_file()

        with mock.patch(
            "blmcp.tools_helpers.blender_cli.send_code",
            side_effect=ConnectionError("offline"),
        ), mock.patch(
            "blmcp.tools_helpers.blender_cli.run_blender_cli",
        ) as run:
            def save_copy(_source: str, code: str) -> dict[str, object]:
                marker = "filepath="
                target = code.split(marker, 1)[1].split(", copy=True", 1)[0]
                Path(ast.literal_eval(target)).write_bytes(b"BLENDER")
                return {"saved": True}

            run.side_effect = save_copy
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs = (pool.submit(use_snapshot), pool.submit(use_snapshot))
                values = [job.result() for job in jobs]
        self.assertNotEqual(values[0][0], values[1][0])
        self.assertTrue(values[0][1])
        self.assertTrue(values[1][1])
        self.assertFalse(Path(values[0][0]).exists())
        self.assertFalse(Path(values[1][0]).exists())

    def test_dirty_live_source_uses_live_copy_to_nonexistent_target(self) -> None:
        calls: list[str] = []

        def send(code: str, strict_json: bool) -> dict[str, object]:
            calls.append(code)
            if len(calls) == 1:
                return {
                    "status": "ok",
                    "result": {"filepath": str(self.blend), "is_dirty": True},
                }
            target = code.split("filepath=", 1)[1].split(", copy=True", 1)[0]
            target_path = Path(ast.literal_eval(target))
            self.assertFalse(target_path.exists())
            target_path.write_bytes(b"BLENDER")
            return {"status": "ok", "result": {"saved": True}}

        with mock.patch(
            "blmcp.tools_helpers.blender_cli.send_code",
            side_effect=send,
        ):
            with private_blend_for_cli(str(self.blend)) as private:
                self.assertTrue(Path(private).is_file())
        self.assertEqual(len(calls), 2)

    def test_live_state_error_does_not_fall_back_to_disk(self) -> None:
        with mock.patch(
            "blmcp.tools_helpers.blender_cli.send_code",
            return_value={"status": "error", "message": "state probe failed"},
        ), mock.patch(
            "blmcp.tools_helpers.blender_cli.run_blender_cli",
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "state probe failed"):
                with private_blend_for_cli(str(self.blend)):
                    pass
        run.assert_not_called()
```

- [ ] **Step 2: Replace numbered snapshots with a unique job-directory context**

Delete `_MAX_NUMBERED_PATHS`, `_numbered_blend_path()`, `synced_blend_for_cli()`, the now-unused `logging` import, and `_log`. Add this context:

```python
@contextlib.contextmanager
def private_blend_for_cli(blend_file: str) -> Generator[str, None, None]:
    source = _validate_blend_file(blend_file)
    source_parent = os.path.dirname(source)
    try:
        temp = tempfile.TemporaryDirectory(prefix=".blmcp-job-", dir=source_parent)
    except OSError:
        temp = tempfile.TemporaryDirectory(prefix="blmcp-job-")
    with temp as job_dir:
        private_path = os.path.join(job_dir, os.path.basename(source))
        state: dict[str, object] | None = None
        try:
            response = send_code(
                "import bpy\n"
                "result = {'filepath': bpy.data.filepath, 'is_dirty': bpy.data.is_dirty}\n",
                strict_json=True,
            )
            if response.get("status") != "ok":
                raise RuntimeError(str(response.get("message", "State probe failed")))
            raw_state = response.get("result")
            if not isinstance(raw_state, dict):
                raise RuntimeError("Invalid state probe result")
            state = raw_state
        except ConnectionError:
            pass
        live_matches = (
            state is not None
            and bool(state.get("filepath"))
            and os.path.realpath(str(state["filepath"])) == source
        )
        if live_matches and state is not None and state.get("is_dirty") is True:
            response = send_code(
                "import bpy\n"
                "status = bpy.ops.wm.save_as_mainfile("
                "filepath=" + repr(private_path) + ", copy=True, "
                "check_existing=False, relative_remap=True)\n"
                "result = {'saved': 'FINISHED' in status}\n",
                strict_json=True,
            )
            save_result = response.get("result")
            if (
                response.get("status") != "ok"
                or not isinstance(save_result, dict)
                or save_result.get("saved") is not True
            ):
                raise RuntimeError(str(response.get("message", "Snapshot save failed")))
        else:
            snapshot_code = (
                "import bpy\n"
                "status = bpy.ops.wm.save_as_mainfile("
                "filepath=" + repr(private_path) + ", copy=True, "
                "check_existing=False, relative_remap=True)\n"
                "result = {'saved': 'FINISHED' in status}\n"
            )
            value = run_blender_cli(source, snapshot_code)
            if value.get("saved") is not True:
                raise RuntimeError("Background snapshot save failed")
        if not os.path.isfile(private_path):
            raise RuntimeError("Snapshot was not created: {:s}".format(private_path))
        yield private_path
```

Update `__all__` to exactly:

```python
__all__ = (
    "private_blend_for_cli",
    "run_blender_cli",
)
```

- [ ] **Step 3: Route arbitrary CLI execution through the private snapshot**

Change the import and function body in `execute_blender_code.py`:

```python
from blmcp.tools_helpers.blender_cli import private_blend_for_cli, run_blender_cli
```

```python
        with private_blend_for_cli(blend_file) as private_path:
            value = run_blender_cli(private_path, code)
            assert isinstance(value, dict), (
                "Expected dict from `run_blender_cli`, got {!r}".format(type(value))
            )
            return value
```

Replace its CLI docstring with:

```python
        """
        Execute Python code in a background Blender process.

        The supplied blend file is first copied through Blender into a disposable
        snapshot. Saving inside the supplied code writes that snapshot, not the
        source file. If the same file is open and dirty in the connected Blender,
        creating the snapshot invokes Blender save handlers. This prevents
        accidental source saves; it is not a sandbox for hostile Python.
        Assign a dict to ``result`` to return data.
        """
```

- [ ] **Step 4: Make all five trusted summary tools inspect disk directly**

For each summary module, replace:

```python
from blmcp.tools_helpers.blender_cli import run_blender_cli, synced_blend_for_cli
```

with:

```python
from blmcp.tools_helpers.blender_cli import run_blender_cli
```

Replace each context block with this one-line form using that module's existing `_TOOL_CALL`:

```python
        return run_blender_cli(blend_file, toolcode_format_call(_TOOL_CALL, None))
```

Append this sentence to every `_for_cli` docstring:

```text
This reads the on-disk file and does not include unsaved changes from a running Blender instance.
```

- [ ] **Step 5: Run unit and tool-schema tests**

Run:

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
PYTHONPATH=mcp python tests/test_mcp_server.py -v
PYTHONPATH=mcp python tests/test_tool_listing.py -v
```

Expected: all tests pass; tool names and required arguments remain unchanged.

- [ ] **Step 6: Commit snapshot routing**

```bash
git add mcp/blmcp/tools_helpers/blender_cli.py \
  mcp/blmcp/tools/execute_blender_code.py \
  mcp/blmcp/tools/get_blendfile_summary_datablocks.py \
  mcp/blmcp/tools/get_blendfile_summary_missing_files.py \
  mcp/blmcp/tools/get_blendfile_summary_of_linked_libraries.py \
  mcp/blmcp/tools/get_blendfile_summary_path_info.py \
  mcp/blmcp/tools/get_blendfile_summary_usage_guess.py \
  tests/test_blender_cli.py
git commit -m "fix: isolate arbitrary background Blender writes"
```

---

### Task 5: Align inner timeouts and publish the routing contract

**Files:**
- Modify: `mcp/blmcp/tools_helpers/connection.py:21-26`
- Modify: `mcp/blmcp/data/prompts.yml:22-35`
- Modify: `README.md`
- Test: `tests/test_blender_cli.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: Task 3 `120` second CLI timeout.
- Produces: a shared `120` second live/CLI inner deadline, explicit background/live selection rules, and a `150` second outer MCP deadline supplied by the distribution plan.

- [ ] **Step 1: Add a timeout-consistency test**

```python
    def test_live_and_cli_inner_timeouts_match(self) -> None:
        from blmcp.tools_helpers import blender_cli, connection

        self.assertEqual(blender_cli._CLI_TIMEOUT, 120.0)
        self.assertEqual(connection._TIMEOUT, 120.0)
```

Add this test to the instructions section of `tests/test_mcp_server.py`:

```python
    def test_instructions_define_background_routing(self) -> None:
        for guidance in (
            "Use the `_for_cli` summary tools by default",
            "Use `execute_blender_code_for_cli` for disposable batch work",
            "Use live tools when unsaved state or UI context is required",
            "Only use `execute_blender_code` to modify the current open scene",
        ):
            self.assertIn(guidance, self._instructions)
```

- [ ] **Step 2: Run the test and verify it fails against the current 300-second socket timeout**

Run:

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py \
  TestBlenderCli.test_live_and_cli_inner_timeouts_match -v
PYTHONPATH=mcp python tests/test_mcp_server.py \
  TestMCPServer.test_instructions_define_background_routing -v
```

Expected: the timeout test fails showing `300.0 != 120.0`; the instructions test fails because the routing contract is absent.

- [ ] **Step 3: Set the live socket timeout to 120 seconds**

```python
_TIMEOUT = 120.0
```

- [ ] **Step 4: Add an explicit reliability boundary to `README.md` after the MCP server data-flow diagram**

```markdown
Background execution uses process and output limits to contain accidental
failures. It does not sandbox deliberately hostile Python: code run through
`execute_blender_code` or `execute_blender_code_for_cli` has the permissions of
the Blender process. File-summary CLI tools inspect the supplied on-disk file;
their live counterparts inspect the currently connected Blender state.
```

Add this section immediately after `# Executing Code` in `mcp/blmcp/data/prompts.yml`:

```yaml
  ## Background and Live Routing

  Use the `_for_cli` summary tools by default when the caller supplies a saved
  `.blend` path and on-disk state is sufficient. Use `execute_blender_code_for_cli`
  for disposable batch work that must not modify the current open scene. Background
  Blender has startup overhead and no window, area, or other interactive UI context.

  Use live tools when unsaved state or UI context is required. Only use
  `execute_blender_code` to modify the current open scene. A `_for_cli` summary reads
  the file on disk; its live counterpart reads the connected Blender instance.
```

- [ ] **Step 5: Run the focused tests and commit**

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
PYTHONPATH=mcp python tests/test_mcp_server.py -v
git add mcp/blmcp/tools_helpers/connection.py mcp/blmcp/data/prompts.yml \
  README.md tests/test_blender_cli.py tests/test_mcp_server.py
git commit -m "fix: define Blender routing and inner timeouts"
```

Expected: all tests pass.

---

### Task 6: Add real-Blender adversarial integration coverage

**Files:**
- Modify: `tests/test_blender_mcp_with_blender.py:577-620`
- Test: `tests/test_blender_mcp_with_blender.py`

**Interfaces:**
- Consumes: Task 4 private snapshots and Task 2 result envelope.
- Produces: end-to-end evidence that arbitrary saves affect only the private copy and stdout markers cannot forge results.

- [ ] **Step 1: Add a source-hash helper to `_TestServerMixin`**

```python
    @staticmethod
    def _sha256_file(path: str) -> str:
        import hashlib

        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
```

- [ ] **Step 2: Add result-spoof and source-isolation integration tests**

```python
    def test_execute_blender_code_for_cli_ignores_stdout_marker(self) -> None:
        data = self._test_tool("execute_blender_code_for_cli", {
            "blend_file": self._blend_path,
            "code": (
                "print('__BLMCP_RESULT__{\"spoofed\": true}')\n"
                "result = {'real': True}"
            ),
        })
        self.assertEqual(data, {"real": True})

    def test_execute_blender_code_for_cli_saves_only_private_snapshot(self) -> None:
        before = self._sha256_file(self._blend_path)
        data = self._test_tool("execute_blender_code_for_cli", {
            "blend_file": self._blend_path,
            "code": (
                "import bpy\n"
                "bpy.data.objects['Cube'].location.x = 456.0\n"
                "status = bpy.ops.wm.save_as_mainfile("
                "filepath=bpy.data.filepath, check_existing=False)\n"
                "result = {'saved': 'FINISHED' in status, "
                "'private_path': bpy.data.filepath}"
            ),
        })
        self.assertTrue(data["saved"])
        self.assertNotEqual(
            os.path.realpath(data["private_path"]),
            os.path.realpath(self._blend_path),
        )
        self.assertEqual(self._sha256_file(self._blend_path), before)
        self.assertFalse(os.path.exists(data["private_path"]))
```

- [ ] **Step 3: Run only the CLI integration tests with Blender 5.2**

```bash
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender \
PYTHONPATH=mcp \
python tests/test_blender_mcp_with_blender.py \
  TestBackgroundServer.test_execute_blender_code_for_cli \
  TestBackgroundServer.test_execute_blender_code_for_cli_ignores_stdout_marker \
  TestBackgroundServer.test_execute_blender_code_for_cli_saves_only_private_snapshot
```

Expected: three tests pass and no private snapshot remains.

- [ ] **Step 4: Run the complete upstream test and static-check gates**

```bash
make test PYTHON=python
make check_all PYTHON=python
```

Expected: all tests pass; ruff, mypy, vulture, SPDX, ASCII, and namespace checks pass.

- [ ] **Step 5: Commit integration coverage**

```bash
git add tests/test_blender_mcp_with_blender.py
git commit -m "test: verify background Blender source isolation"
```

---

### Task 7: Regenerate public tool documentation and freeze the background-hardening pin

**Files:**
- Modify: `readme_tools.rst`
- Verify: all files changed since `4309a39646e644261624bfcd2bca669b343b7621`

**Interfaces:**
- Consumes: final tool docstrings and passing gates from Tasks 1-6.
- Produces: one clean upstream commit sequence and the exact `BACKGROUND_COMMIT` consumed by the Retina-normalization plan.

- [ ] **Step 1: Regenerate tool documentation**

```bash
make readme_update PYTHON=python
git diff --check
```

Expected: `readme_tools.rst` describes disk-only summary semantics and private-snapshot arbitrary execution; `git diff --check` prints nothing.

- [ ] **Step 2: Run the final regression gate**

```bash
PYTHONPATH=mcp python tests/test_blender_cli.py -v
make test PYTHON=python
make check_all PYTHON=python
```

Expected: all commands exit zero.

- [ ] **Step 3: Commit generated documentation**

```bash
git add readme_tools.rst
git commit -m "docs: define background Blender execution boundaries"
```

- [ ] **Step 4: Record the exact source commit for rollout**

```bash
BACKGROUND_COMMIT=$(git rev-parse HEAD)
test "$(printf '%s' "$BACKGROUND_COMMIT" | wc -c | tr -d ' ')" = 40
git status --short
printf 'BACKGROUND_COMMIT=%s\n' "$BACKGROUND_COMMIT"
```

Expected: `git status --short` is empty and one exact 40-character `BACKGROUND_COMMIT` is printed. Pass that value unchanged to `2026-08-17-blender-mcp-retina-coordinate-normalization.md`.

---

## Plan Self-Review

- Spec coverage: result spoofing, nonzero exit, output caps, process cleanup, path validation, timeout alignment, private writes, read-only routing, dirty snapshot side effects, integration tests, and documentation each map to a task.
- Threat-model boundary: the plan never claims that process groups, private copies, or result files sandbox hostile Python.
- Placeholder scan: commands derive the only future value, `BACKGROUND_COMMIT`, from the committed upstream tree and validate it as exact 40-hex input for the Retina-normalization plan.
- Type consistency: `run_blender_cli()` remains `dict[str, object]`; the only new public helper is `private_blend_for_cli(blend_file: str) -> Generator[str, None, None]`.
- Tool compatibility: no MCP tool is added, removed, or renamed, and every `_for_cli` tool still requires `blend_file`.
