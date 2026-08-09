import ast
import asyncio
import hashlib
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from smoke import e2e
from smoke import process_registry


def _clear_vendor_bytecode() -> None:
    vendor_root = e2e.ROOT / "bridge/_vendor"
    for directory in vendor_root.rglob("__pycache__"):
        shutil.rmtree(directory)
    for pattern in ("*.pyc", "*.pyo"):
        for path in vendor_root.rglob(pattern):
            path.unlink()


def _row(tool, arguments, ok=True, error=None, instance_id=None, request_id=1):
    _, digest = e2e._canonical(arguments)
    return {
        "ts": "2026-08-08T00:00:00.000+00:00",
        "request_id": request_id,
        "tool": tool,
        "instance_id": instance_id,
        "transaction_id": None,
        "params_digest": digest[:16],
        "ok": ok,
        "duration_ms": 1.0,
        "paths": [],
        "error": error,
    }


def test_audit_summary_rejects_forged_or_contradictory_rows():
    arguments = {"instance_selector": "gui-1-deadbeef"}
    expected = [("get_blender_status", arguments, True, None, None)]
    valid = _row("get_blender_status", arguments)
    assert e2e._audit_summary([valid], expected)["ok_rows"] == 1

    forged = [
        valid | {"params_digest": "FORGED"},
        valid | {"error": "BRIDGE_UNAVAILABLE"},
        valid | {"tool": "totally_wrong_tool"},
        valid | {"instance_id": "unexpected"},
    ]
    for row in forged:
        with pytest.raises(AssertionError):
            e2e._audit_summary([row], expected)


@pytest.mark.asyncio
async def test_measure_call_uses_the_shared_deadline():
    class SlowClient:
        async def call_tool(self, _tool, _arguments):
            await asyncio.sleep(0.05)
            return SimpleNamespace(is_error=False, structured_content={"ok": True})

    with pytest.raises(TimeoutError):
        await e2e._measure(
            SlowClient(), "tool", {}, lambda value: value,
            time.monotonic() + 0.01,
        )


@pytest.mark.asyncio
async def test_ready_file_pid_must_match_spawned_blender(tmp_path):
    ready = tmp_path / "ready.json"
    ready.write_text(json.dumps({"instance_id": "gui-1-deadbeef", "pid": 999}))
    process = SimpleNamespace(pid=123, poll=lambda: None, returncode=None)
    with pytest.raises(ValueError, match="malformed recovery ready"):
        await e2e._wait_ready(ready, process, time.monotonic() + 1.0)


def test_private_artifact_write_preserves_exact_0600(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    output = tmp_path / "artifact.json"
    e2e._write_artifact(output, {"success": True})
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert json.loads(output.read_text()) == {"success": True}
    assert list(tmp_path.glob("*.tmp")) == []

    real_replace = e2e.os.replace
    moved = tmp_path / "original-temporary"
    replacement = {}

    def replace_temporary(source, _target):
        source = Path(source)
        source.rename(moved)
        source.write_bytes(b"replacement")
        source.chmod(0o600)
        replacement["path"] = source
        raise RuntimeError("publication failed")

    monkeypatch.setattr(e2e.os, "replace", replace_temporary)
    with pytest.raises(RuntimeError):
        e2e._write_artifact(output, {"success": False})
    assert replacement["path"].exists()
    replacement["path"].unlink()
    moved.unlink()
    monkeypatch.setattr(e2e.os, "replace", real_replace)

    monkeypatch.setattr(e2e, "MAX_ARTIFACT_BYTES", 8)
    with pytest.raises(ValueError, match="32 MiB"):
        e2e._write_artifact(output, {"success": True})


def test_live_mcp_process_record_cannot_be_retired_as_clean(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    not_before_ns = time.monotonic_ns()
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
    )
    record = tmp_path / "mcp.json"
    try:
        process_registry.publish_process(
            record, marker, process.pid, process.pid)
        with pytest.raises(RuntimeError, match="survived owner cleanup"):
            process_registry.retire_record(
                record, expected_marker=marker, not_before_ns=not_before_ns)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)
    process_registry.retire_record(
        record, expected_marker=marker, not_before_ns=not_before_ns)
    assert not record.exists()


def test_exited_group_leader_with_live_child_is_not_retired_as_clean(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    not_before_ns = time.monotonic_ns()
    record = tmp_path / "orphan.json"
    code = (
        "import subprocess; from pathlib import Path; "
        "from smoke.process_registry import publish_current_process; "
        f"publish_current_process(Path({str(record)!r}), {marker!r}); "
        "subprocess.Popen(['/bin/sleep', '30'])"
    )
    leader = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    pgid = leader.pid
    leader.wait(timeout=2)
    try:
        os.killpg(pgid, 0)
        with pytest.raises(RuntimeError, match="survived owner cleanup"):
            process_registry.retire_record(
                record, expected_marker=marker, not_before_ns=not_before_ns)
        process_registry.cleanup_registry(
            tmp_path, expected_marker=marker, not_before_ns=not_before_ns,
            deadline=time.monotonic() + 2.0, term_grace=0.1, settle_grace=0.0)
        with pytest.raises(ProcessLookupError):
            os.killpg(pgid, 0)
        assert list(tmp_path.iterdir()) == []
    finally:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def test_group_id_helpers_track_child_after_leader_exit():
    code = "import subprocess; subprocess.Popen(['/bin/sleep', '30'])"
    leader = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    pgid = leader.pid
    leader.wait(timeout=2)
    try:
        assert process_registry.group_id_is_live(pgid)
        process_registry.signal_group_id(pgid, signal.SIGTERM)
        deadline = time.monotonic() + 2.0
        while process_registry.group_id_is_live(pgid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not process_registry.group_id_is_live(pgid)
    finally:
        process_registry.signal_group_id(pgid, signal.SIGKILL)


def test_poll_before_deadline_rejects_completion_observed_at_boundary(monkeypatch):
    clock = {"now": 10.0}
    calls = []

    def poll():
        calls.append(True)
        clock["now"] = 11.0
        return 0

    monkeypatch.setattr(
        process_registry.time, "monotonic", lambda: clock["now"])
    returncode, expired = process_registry.poll_before_deadline(poll, 11.0)
    assert returncode == 0 and expired is True and calls == [True]
    clock["now"] = 11.0
    returncode, expired = process_registry.poll_before_deadline(poll, 11.0)
    assert returncode is None and expired is True and calls == [True]


def test_scan_caches_valid_record_before_later_entry_hits_deadline(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    first = process_registry.ProcessRecord(
        tmp_path / "first.json", 42, 42, marker, 1, 1, 1)
    older = process_registry.ProcessRecord(
        tmp_path / "older.json", 41, 41, marker, 1, 1, 1)

    class Entries:
        def __enter__(self):
            return iter([
                SimpleNamespace(name="first.json"),
                SimpleNamespace(name="later.json"),
            ])

        def __exit__(self, *_args):
            return False

    clock = iter([0.0, 0.0, 2.0])
    monkeypatch.setattr(process_registry.os, "scandir", lambda _path: Entries())
    monkeypatch.setattr(process_registry.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(process_registry, "read_record", lambda *_args, **_kwargs: first)
    monkeypatch.setattr(process_registry, "group_is_live", lambda _record: True)
    known = {older.pgid: older}
    with pytest.raises(TimeoutError, match="scan deadline"):
        process_registry.scan_records(
            tmp_path, expected_marker=marker, not_before_ns=1,
            deadline=1.0, known_records=known)
    assert known == {older.pgid: older, first.pgid: first}


def test_scan_does_not_clear_cache_when_empty_scan_finishes_at_deadline(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    older = process_registry.ProcessRecord(
        tmp_path / "older.json", 41, 41, marker, 1, 1, 1)

    class EmptyEntries:
        def __enter__(self):
            return iter(())

        def __exit__(self, *_args):
            return False

    clock = iter([0.0, 2.0])
    monkeypatch.setattr(
        process_registry.os, "scandir", lambda _path: EmptyEntries())
    monkeypatch.setattr(process_registry.time, "monotonic", lambda: next(clock))
    known = {older.pgid: older}
    with pytest.raises(TimeoutError, match="before completion"):
        process_registry.scan_records(
            tmp_path, expected_marker=marker, not_before_ns=1,
            deadline=1.0, known_records=known)
    assert known == {older.pgid: older}


def test_scan_keeps_live_cache_if_publication_starts_after_empty_enumeration(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    older = process_registry.ProcessRecord(
        tmp_path / "older.json", 41, 41, marker, 1, 1, 1)
    temporary = tmp_path / f".new.json.{os.getpid()}.deadbeef.tmp"

    class RacingEntries:
        def __enter__(self):
            return iter(())

        def __exit__(self, *_args):
            temporary.write_bytes(b"publication started")
            return False

    monkeypatch.setattr(
        process_registry.os, "scandir", lambda _path: RacingEntries())
    monkeypatch.setattr(process_registry, "group_is_live", lambda _record: True)
    known = {older.pgid: older}
    records, publishing = process_registry.scan_records(
        tmp_path, expected_marker=marker, not_before_ns=1,
        known_records=known)
    assert publishing is False and temporary.exists()
    assert records == [older] and known == {older.pgid: older}


def test_pending_publication_merges_cache_and_clean_scan_replaces_it(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    started_ns = time.monotonic_ns()
    first_path = tmp_path / "first.json"
    process_registry._write_private_json(first_path, {
        "schema_version": 1, "pid": 41, "pgid": 41, "marker": marker,
        "started_monotonic_ns": started_ns,
    })
    live = {41, 42}
    monkeypatch.setattr(
        process_registry, "group_is_live",
        lambda record: record.pgid in live)
    known = {}
    records, publishing = process_registry.scan_records(
        tmp_path, expected_marker=marker, not_before_ns=started_ns,
        known_records=known)
    assert publishing is False and [record.pgid for record in records] == [41]
    assert set(known) == {41}

    first_path.unlink()
    temporary = tmp_path / f".pending.json.{os.getpid()}.deadbeef.tmp"
    process_registry._write_private_json(temporary, {
        "schema_version": 1, "pid": 42, "pgid": 42, "marker": marker,
        "started_monotonic_ns": started_ns,
    })
    records, publishing = process_registry.scan_records(
        tmp_path, expected_marker=marker, not_before_ns=started_ns,
        known_records=known)
    assert publishing is True and [record.pgid for record in records] == [42]
    assert set(known) == {41, 42}

    temporary.unlink()
    live.clear()
    records, publishing = process_registry.scan_records(
        tmp_path, expected_marker=marker, not_before_ns=started_ns,
        known_records=known)
    assert records == [] and publishing is False and known == {}


def test_server_params_reserves_first_publication_before_spawn(
    tmp_path, monkeypatch,
):
    runtime_root = tmp_path / "runtime"
    registry = tmp_path / "registry"
    runtime_root.mkdir(mode=0o700)
    registry.mkdir(mode=0o700)
    record = registry / "first.json"
    marker = process_registry.new_marker()
    not_before_ns = time.monotonic_ns()
    params, publication = e2e._server_params(runtime_root, record, marker)
    reservation, device, inode = publication
    assert Path(params.args[0]).name == "process_registry.py"
    assert params.args[1] == process_registry.SENTINEL_MODE
    assert params.args[2] == str(record) and params.args[6] == marker
    records, publishing = process_registry.scan_records(
        registry, expected_marker=marker, not_before_ns=time.monotonic_ns())
    assert records == [] and publishing is True and reservation.exists()
    e2e._retire_record_or_reservation(
        record, publication, expected_marker=marker,
        not_before_ns=not_before_ns)
    assert list(registry.iterdir()) == []

    def fail(*_args, **_kwargs):
        raise RuntimeError("pre-spawn failure")

    failed_record = registry / "failed.json"
    monkeypatch.setattr(e2e, "StdioServerParameters", fail)
    with pytest.raises(RuntimeError, match="pre-spawn failure"):
        e2e._server_params(runtime_root, failed_record, marker)
    monkeypatch.setattr(e2e.subprocess, "Popen", fail)
    with pytest.raises(RuntimeError, match="pre-spawn failure"):
        e2e._start_blender(
            runtime_root, tmp_path / "ready", tmp_path / "stop",
            failed_record, marker)
    assert list(registry.iterdir()) == []


def test_stdlib_bootstrap_publishes_identity_before_target_runs(tmp_path):
    tmp_path.chmod(0o700)
    record = tmp_path / "bootstrap.json"
    marker = process_registry.new_marker()
    started_ns = time.monotonic_ns()
    reservation, device, inode = process_registry.reserve_publication(record)
    process = subprocess.Popen([
        sys.executable, process_registry.__file__, process_registry.SENTINEL_MODE,
        str(record), str(reservation), str(device), str(inode), marker,
        "/bin/sleep", "0.2",
    ], start_new_session=True)
    deadline = time.monotonic() + 2.0
    while not record.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    published = process_registry.read_record(
        record, expected_marker=marker, not_before_ns=started_ns)
    assert published.pid == process.pid and published.pgid == process.pid
    process.wait(timeout=2)
    process_registry.retire_record(
        record, expected_marker=marker, not_before_ns=started_ns)
    assert list(tmp_path.iterdir()) == []


def test_known_cache_prunes_dead_records_while_publication_stays_pending(
    tmp_path, monkeypatch,
):
    marker = process_registry.new_marker()
    live = set()
    signaled = []
    monkeypatch.setattr(
        process_registry, "group_is_live", lambda record: record.pgid in live)
    monkeypatch.setattr(process_registry, "current_record", lambda record: record)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    known = {}
    for pgid in range(10, 10 + process_registry.MAX_RECORDS * 4):
        live.clear()
        live.add(pgid)
        record = process_registry.ProcessRecord(
            tmp_path / f"{pgid}.json", pgid, pgid, marker, 1, 1, pgid)
        process_registry._remember_known_record(known, record)
        assert known == {pgid: record}
    live.clear()
    known.clear()
    for pgid in range(100, 100 + process_registry.MAX_RECORDS):
        live.add(pgid)
        record = process_registry.ProcessRecord(
            tmp_path / f"{pgid}.json", pgid, pgid, marker, 1, 1, pgid)
        process_registry._remember_known_record(known, record)
    overflow = process_registry.ProcessRecord(
        tmp_path / "overflow.json", 999, 999, marker, 1, 1, 999)
    live.add(999)
    with pytest.raises(RuntimeError, match="known process record limit"):
        process_registry._remember_known_record(known, overflow)
    assert len(known) == process_registry.MAX_RECORDS and 999 not in known
    assert signaled == [(999, signal.SIGKILL)]


def test_clean_scan_kills_overflow_without_growing_known_cache(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    records_by_name = {
        f"{pgid}.json": process_registry.ProcessRecord(
            tmp_path / f"{pgid}.json", pgid, pgid, marker, 1, 1, pgid)
        for pgid in range(100, 100 + process_registry.MAX_RECORDS + 1)
    }
    known = {}

    class Entries:
        def __enter__(self):
            return iter(
                SimpleNamespace(name=name) for name in records_by_name)

        def __exit__(self, *_args):
            return False

    signaled = []
    monkeypatch.setattr(process_registry.os, "scandir", lambda _path: Entries())
    monkeypatch.setattr(
        process_registry, "read_record",
        lambda path, **_kwargs: records_by_name[path.name])
    monkeypatch.setattr(process_registry, "group_is_live", lambda _record: True)
    monkeypatch.setattr(process_registry, "current_record", lambda current: current)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    with pytest.raises(RuntimeError, match="known process record limit"):
        process_registry.scan_records(
            tmp_path, expected_marker=marker, not_before_ns=1,
            known_records=known)
    assert set(known) == set(range(100, 100 + process_registry.MAX_RECORDS))
    assert signaled == [(108, signal.SIGKILL)]


def test_reused_cached_identity_does_not_block_later_valid_records(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    reused = process_registry.ProcessRecord(
        tmp_path / "reused.json", 41, 41, marker, 1, 1, 1)
    valid = {
        "first.json": process_registry.ProcessRecord(
            tmp_path / "first.json", 42, 42, marker, 1, 1, 2),
        "second.json": process_registry.ProcessRecord(
            tmp_path / "second.json", 43, 43, marker, 1, 1, 3),
    }
    known = {41: reused}

    def liveness(record):
        if record.pgid == 41:
            raise RuntimeError("recorded PID was reused: 41")
        return True

    class Entries:
        def __enter__(self):
            return iter(SimpleNamespace(name=name) for name in valid)

        def __exit__(self, *_args):
            return False

    signaled = []
    monkeypatch.setattr(process_registry.os, "scandir", lambda _path: Entries())
    monkeypatch.setattr(
        process_registry, "read_record",
        lambda path, **_kwargs: valid[path.name])
    monkeypatch.setattr(process_registry, "group_is_live", liveness)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    with pytest.raises(RuntimeError, match="recorded PID was reused"):
        process_registry.scan_records(
            tmp_path, expected_marker=marker, not_before_ns=1,
            known_records=known)
    assert set(known) == {42, 43}
    process_registry.signal_live_records(known.values(), signal.SIGKILL)
    assert signaled == [(42, signal.SIGKILL), (43, signal.SIGKILL)]


def test_invalid_record_does_not_hide_later_valid_group(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    valid = process_registry.ProcessRecord(
        tmp_path / "valid.json", 42, 42, marker, 1, 1, 2)

    class Entries:
        def __enter__(self):
            return iter([
                SimpleNamespace(name="wrong.json"),
                SimpleNamespace(name="unknown.txt"),
                SimpleNamespace(name="valid.json"),
            ])

        def __exit__(self, *_args):
            return False

    def read(path, **_kwargs):
        if path.name == "wrong.json":
            raise ValueError("process record marker differs")
        return valid

    signaled = []
    monkeypatch.setattr(process_registry.os, "scandir", lambda _path: Entries())
    monkeypatch.setattr(process_registry, "read_record", read)
    monkeypatch.setattr(process_registry, "group_is_live", lambda _record: True)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    known = {}
    with pytest.raises(ValueError, match="marker differs"):
        process_registry.scan_records(
            tmp_path, expected_marker=marker, not_before_ns=1,
            known_records=known)
    assert known == {42: valid}
    process_registry.signal_live_records(known.values(), signal.SIGKILL)
    assert signaled == [(42, signal.SIGKILL)]


def test_cleanup_final_kills_cached_group_after_pending_publication_deadline(
    tmp_path, monkeypatch,
):
    record = process_registry.ProcessRecord(
        tmp_path / "live.json", 42, 42,
        process_registry.new_marker(), 1, 1, 1)
    calls = 0
    clock = {"now": 0.0}

    def scan(*_args, known_records, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            known_records[record.pgid] = record
            return [record], False
        assert known_records == {record.pgid: record}
        return [], True

    signaled = []
    monkeypatch.setattr(process_registry, "scan_records", scan)
    monkeypatch.setattr(
        process_registry.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        process_registry.time, "sleep",
        lambda seconds: clock.__setitem__("now", clock["now"] + seconds))
    monkeypatch.setattr(process_registry, "group_is_live", lambda _record: True)
    monkeypatch.setattr(process_registry, "current_record", lambda current: current)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    with pytest.raises(TimeoutError, match="publication exceeded"):
        process_registry.cleanup_registry(
            tmp_path, expected_marker=record.marker, not_before_ns=1,
            deadline=0.03, term_grace=0.01, settle_grace=0.0)
    assert signaled == [(42, signal.SIGTERM), (42, signal.SIGKILL)]


def test_cleanup_uses_preobserved_cache_if_deadline_expired_before_scan(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    started_ns = time.monotonic_ns()
    process = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
    path = tmp_path / "preobserved.json"
    record = process_registry.publish_process(
        path, marker, process.pid, process.pid,
        started_monotonic_ns=started_ns)
    with pytest.raises(TimeoutError, match="before start"):
        process_registry.cleanup_registry(
            tmp_path, expected_marker=marker, not_before_ns=started_ns,
            deadline=time.monotonic() - 1.0,
            known_records={record.pgid: record})
    process.wait(timeout=2)
    process_registry.retire_record(
        path, expected_marker=marker, not_before_ns=started_ns)
    assert not path.exists()


def test_cached_signal_rechecks_pid_pgid_reuse(monkeypatch, tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    path = tmp_path / "cached.json"
    process_registry._write_private_json(path, {
        "schema_version": 1, "pid": 42, "pgid": 42, "marker": marker,
        "started_monotonic_ns": time.monotonic_ns(),
    })
    record = process_registry.read_record(path, expected_marker=marker)
    signaled = []
    monkeypatch.setattr(process_registry.os, "getpgid", lambda _pid: 43)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    with pytest.raises(RuntimeError, match="recorded PID was reused"):
        process_registry.signal_live_records([record], signal.SIGKILL)
    assert signaled == []


def test_cached_signal_continues_after_another_record_is_reused(
    monkeypatch, tmp_path,
):
    marker = process_registry.new_marker()
    tmp_path.chmod(0o700)
    started_ns = time.monotonic_ns()
    reused_path = tmp_path / "reused.json"
    valid_path = tmp_path / "valid.json"
    for path, pid in ((reused_path, 41), (valid_path, 42)):
        process_registry._write_private_json(path, {
            "schema_version": 1, "pid": pid, "pgid": pid, "marker": marker,
            "started_monotonic_ns": started_ns,
        })
    reused = process_registry.read_record(reused_path, expected_marker=marker)
    valid = process_registry.read_record(valid_path, expected_marker=marker)
    signaled = []
    monkeypatch.setattr(
        process_registry.os, "getpgid", lambda pid: 99 if pid == 41 else pid)
    monkeypatch.setattr(process_registry, "group_id_is_live", lambda _pgid: True)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    with pytest.raises(RuntimeError, match="recorded PID was reused"):
        process_registry.signal_live_records([valid, reused], signal.SIGKILL)
    assert signaled == [(42, signal.SIGKILL)]


def test_runner_never_signals_replaced_cached_outer_record(tmp_path, monkeypatch):
    runner = Path(__file__).resolve().parents[2] / "smoke" / "runner.py"
    tree = ast.parse(runner.read_text())
    query = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_query_async"
    )
    bridge_calls = [
        node for node in ast.walk(query)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "call"
    ]
    assert len(bridge_calls) == 1
    assert any(
        keyword.arg == "deadline"
        and isinstance(keyword.value, ast.Name)
        and keyword.value.id == "deadline"
        for keyword in bridge_calls[0].keywords
    )
    finish = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_finish"
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_retire_nfr_helper"
        for node in ast.walk(finish)
    )
    names = {
        "_nfr_error_once", "_live_nfr_groups", "_signal_nfr_groups",
        "_nfr_helper_record", "_signal_nfr_helper",
    }
    body = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    started_ns = time.monotonic_ns()
    path = tmp_path / "nfr-helper.json"
    value = {
        "schema_version": 1, "pid": 42, "pgid": 42, "marker": marker,
        "started_monotonic_ns": started_ns,
    }
    process_registry._write_private_json(path, value)
    record = process_registry.read_record(
        path, expected_marker=marker, not_before_ns=started_ns)
    path.unlink()
    process_registry._write_private_json(path, value)
    known = {42: record}
    signaled = []
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    namespace = {
        "Path": Path,
        "RES": {"errors": []},
        "ST": {
            "nfr_process_dir": None,
            "nfr_registry_marker": marker,
            "nfr_registry_not_before_ns": started_ns,
            "nfr_registry_pending": False,
            "nfr_known_records": known,
            "nfr_error": None,
            "nfr_helper_record": path,
            "nfr_helper_identity": record,
            "nfr_proc": SimpleNamespace(pid=42, poll=lambda: None),
        },
        "current_record": process_registry.current_record,
        "read_record": process_registry.read_record,
        "scan_records": lambda *_args, **_kwargs: ([], False),
        "signal_live_records": process_registry.signal_live_records,
    }
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(module, str(runner), "exec"), namespace)
    assert namespace["_live_nfr_groups"]() == []
    assert namespace["ST"]["nfr_registry_pending"] is True
    assert namespace["ST"]["nfr_known_records"] is known
    namespace["_signal_nfr_groups"](signal.SIGKILL)
    namespace["_signal_nfr_helper"](signal.SIGKILL)
    assert signaled == []
    assert any("process record identity changed" in message
               for message in namespace["RES"]["errors"])
    namespace["signal_live_records"] = lambda *_args: (
        (_ for _ in ()).throw(RuntimeError("reused")))
    namespace["_signal_nfr_groups"](signal.SIGKILL)
    assert any("process group signal: RuntimeError: reused" in message
               for message in namespace["RES"]["errors"])


def test_nonce_mismatch_is_never_signaled(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    not_before_ns = time.monotonic_ns()
    process = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
    record = tmp_path / "wrong-marker.json"
    process_registry.publish_process(record, marker, process.pid, process.pid)
    try:
        with pytest.raises(ValueError, match="marker differs"):
            process_registry.cleanup_registry(
                tmp_path, expected_marker=process_registry.new_marker(),
                not_before_ns=not_before_ns, deadline=time.monotonic() + 0.2,
                settle_grace=0.0)
        assert process.poll() is None
    finally:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)
    process_registry.retire_record(
        record, expected_marker=marker, not_before_ns=not_before_ns)


def test_stale_record_is_never_signaled(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    not_before_ns = time.monotonic_ns()
    process = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
    record = tmp_path / "stale.json"
    process_registry.publish_process(
        record, marker, process.pid, process.pid,
        started_monotonic_ns=not_before_ns - 1)
    try:
        with pytest.raises(ValueError, match="stale process record"):
            process_registry.cleanup_registry(
                tmp_path, expected_marker=marker,
                not_before_ns=not_before_ns, deadline=time.monotonic() + 0.2,
                settle_grace=0.0)
        assert process.poll() is None
    finally:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)
    process_registry.retire_record(record, expected_marker=marker)


def test_process_record_rejects_boolean_schema_version(tmp_path):
    tmp_path.chmod(0o700)
    record = tmp_path / "bool-schema.json"
    process_registry._write_private_json(record, {
        "schema_version": True,
        "pid": 424242,
        "pgid": 424242,
        "marker": process_registry.new_marker(),
        "started_monotonic_ns": time.monotonic_ns(),
    })
    with pytest.raises(ValueError, match="malformed process record values"):
        process_registry.read_record(record)
    record.unlink()


def test_pid_pgid_reuse_is_never_signaled_or_unlinked(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    record = tmp_path / "reused.json"
    pid = 424242
    process_registry._write_private_json(record, {
        "schema_version": 1,
        "pid": pid,
        "pgid": pid,
        "marker": marker,
        "started_monotonic_ns": time.monotonic_ns(),
    })
    signaled = []
    monkeypatch.setattr(process_registry.os, "getpgid", lambda _pid: pid + 1)
    monkeypatch.setattr(process_registry, "group_id_is_live", lambda _pgid: False)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    with pytest.raises(RuntimeError, match="recorded PID was reused"):
        process_registry.cleanup_registry(
            tmp_path, expected_marker=marker,
            not_before_ns=1, deadline=time.monotonic() + 0.2,
            settle_grace=0.0)
    assert signaled == [] and record.exists()
    record.unlink()


def test_replaced_process_record_is_not_unlinked(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()

    temporary_target = tmp_path / "temporary-target.json"
    moved_temporary = tmp_path / "original-temporary"
    replacement = {}
    real_replace = process_registry.os.replace

    def replace_temporary(source, _target):
        source = Path(source)
        source.rename(moved_temporary)
        source.write_bytes(b"replacement")
        source.chmod(0o600)
        replacement["path"] = source
        raise RuntimeError("publication failed")

    monkeypatch.setattr(process_registry.os, "replace", replace_temporary)
    with pytest.raises(RuntimeError):
        process_registry._write_private_json(temporary_target, {"value": 1})
    assert replacement["path"].exists()
    replacement["path"].unlink()
    moved_temporary.unlink()
    monkeypatch.setattr(process_registry.os, "replace", real_replace)

    record = tmp_path / "replace.json"
    backup = tmp_path / "original.json"
    value = {
        "schema_version": 1,
        "pid": 424242,
        "pgid": 424242,
        "marker": marker,
        "started_monotonic_ns": time.monotonic_ns(),
    }
    process_registry._write_private_json(record, value)
    swapped = False

    def replace_before_unlink(_record):
        nonlocal swapped
        if not swapped:
            record.rename(backup)
            process_registry._write_private_json(record, value)
            swapped = True
        return False

    monkeypatch.setattr(process_registry, "group_is_live", replace_before_unlink)
    with pytest.raises(RuntimeError, match="changed before unlink"):
        process_registry.retire_record(record, expected_marker=marker)
    assert record.exists() and backup.exists()
    record.unlink()
    backup.unlink()


def test_registry_observer_never_unlinks_owner_record(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    started_ns = time.monotonic_ns()
    process = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
    path = tmp_path / "owner.json"
    process_registry.publish_process(
        path, marker, process.pid, process.pid,
        started_monotonic_ns=started_ns)
    os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=2)
    records, pending = process_registry.scan_records(
        tmp_path, expected_marker=marker, not_before_ns=started_ns,
        retire_dead=False)
    assert records == [] and pending is True and path.exists()
    process_registry.retire_record(
        path, expected_marker=marker, not_before_ns=started_ns)
    assert not path.exists()


def test_registry_observer_tolerates_owner_unlink_after_enumeration(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    path = tmp_path / "owner.json"
    path.write_bytes(b"owner will retire")
    path.chmod(0o600)

    class RetiredEntry:
        @property
        def name(self):
            path.unlink(missing_ok=True)
            return path.name

    class Entries:
        def __enter__(self):
            return iter([RetiredEntry()])

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(process_registry.os, "scandir", lambda _path: Entries())
    records, pending = process_registry.scan_records(
        tmp_path, expected_marker=process_registry.new_marker(),
        not_before_ns=1, retire_dead=False)
    assert records == [] and pending is True and not path.exists()


def test_registry_observer_tolerates_reservation_finish_after_enumeration(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    record = tmp_path / "future.json"
    reservation, device, inode = process_registry.reserve_publication(record)

    class FinishedEntry:
        name = reservation.name

        def stat(self, *, follow_symlinks):
            assert follow_symlinks is False
            process_registry.finish_publication_reservation(
                reservation, device, inode)
            raise FileNotFoundError(reservation)

    class Entries:
        def __enter__(self):
            return iter([FinishedEntry()])

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(process_registry.os, "scandir", lambda _path: Entries())
    records, pending = process_registry.scan_records(
        tmp_path, expected_marker=process_registry.new_marker(),
        not_before_ns=1, retire_dead=False)
    assert records == [] and pending is True and not reservation.exists()


def test_registry_waits_for_inflight_record_publication(tmp_path):
    tmp_path.chmod(0o700)
    marker = process_registry.new_marker()
    started_ns = time.monotonic_ns()
    temporary = tmp_path / f".late.json.{os.getpid()}.deadbeef.tmp"
    record = tmp_path / "late.json"
    temporary.write_text(json.dumps({
        "schema_version": 1,
        "pid": 99999999,
        "pgid": 99999999,
        "marker": marker,
        "started_monotonic_ns": started_ns,
    }))
    temporary.chmod(0o600)
    records, publishing = process_registry.scan_records(
        tmp_path, expected_marker=marker, not_before_ns=started_ns,
        deadline=time.monotonic() + 1.0)
    assert records == [] and publishing is True

    def publish_later():
        time.sleep(0.05)
        os.replace(temporary, record)

    publisher = threading.Thread(target=publish_later)
    publisher.start()
    process_registry.cleanup_registry(
        tmp_path, expected_marker=marker, not_before_ns=started_ns,
        deadline=time.monotonic() + 1.0, settle_grace=0.1)
    publisher.join(timeout=1)
    assert not publisher.is_alive() and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_cancelled_sdk_client_reaps_its_recorded_process_group(tmp_path):
    runtime_root = tmp_path / "runtime"
    registry = tmp_path / "registry"
    runtime_root.mkdir(mode=0o700)
    registry.mkdir(mode=0o700)
    record = registry / "cancelled.json"
    marker = process_registry.new_marker()
    not_before_ns = time.monotonic_ns()
    params, publication = e2e._server_params(runtime_root, record, marker)
    with pytest.raises(BaseExceptionGroup) as caught:
        async with e2e.Client(
            e2e.stdio_client(params),
            mode="auto",
            read_timeout_seconds=5.0,
        ):
            published = json.loads(record.read_text())
            assert published["pid"] == published["pgid"]
            assert published["marker"] == marker
            assert os.getpgid(published["pid"]) == published["pgid"]
            async with asyncio.timeout(0.01):
                await asyncio.sleep(30)
    assert caught.value.subgroup(TimeoutError) is not None
    e2e._retire_record_or_reservation(
        record, publication, expected_marker=marker,
        not_before_ns=not_before_ns)
    assert not record.exists()


@pytest.mark.asyncio
async def test_measure_records_a_digest_for_every_call(monkeypatch):
    class FastClient:
        def __init__(self):
            self.index = 0

        async def call_tool(self, _tool, _arguments):
            self.index += 1
            value = {"index": self.index, "scale": 1.0}
            return SimpleNamespace(
                is_error=False, structured_content=value,
                content=[SimpleNamespace(
                    type="text", text=json.dumps(value, indent=2))])

    monkeypatch.setattr(e2e, "RUNS", 3)
    ticks = iter([0, 1_000_000] * 3)
    monkeypatch.setattr(e2e.time, "perf_counter_ns", lambda: next(ticks))
    arguments = {"include": False}
    def validate(value):
        assert type(value) is dict and type(value.get("index")) is int
        return {"index": value["index"], "scale": float(value["scale"])}

    record = await e2e._measure(
        FastClient(), "tool", arguments, validate,
        time.monotonic() + 1.0,
    )
    assert len(record["sample_results"]) == 3
    assert all(math.isfinite(item["duration_ms"])
               for item in record["sample_results"])
    assert len({item["result_sha256"]
                for item in record["sample_results"]}) == 3
    assert all(item["text_json_equivalent"] is True
               and item["duplication_ratio"] > 1.0
               for item in record["sample_results"])
    e2e._verify_measurement_record(record, arguments, validate)
    record["arguments"] = {"include": 0}
    with pytest.raises(AssertionError, match="arguments differ"):
        e2e._verify_measurement_record(record, arguments, validate)
    record["arguments"] = arguments
    record["p95_ms"] = True
    record["max_ms"] = True
    with pytest.raises(AssertionError, match="aggregate differs"):
        e2e._verify_measurement_record(record, arguments, validate)
    record["p95_ms"] = 1.0
    record["max_ms"] = 1.0
    record["sample_results"][1]["validated_result"]["scale"] = 1
    with pytest.raises(AssertionError, match="preimage differs after validation"):
        e2e._verify_measurement_record(record, arguments, validate)
    record["sample_results"][1]["validated_result"]["scale"] = 1.0
    record["sample_results"][1]["result_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="sample digest differs"):
        e2e._verify_measurement_record(record, arguments, validate)
    record["sample_results"][1]["result_sha256"] = e2e._canonical(
        record["sample_results"][1]["validated_result"])[1]
    record["sample_results"][1]["text_content_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="TextContent digest differs"):
        e2e._verify_measurement_record(record, arguments, validate)
    with pytest.raises(ValueError, match="Out of range float values"):
        e2e._canonical({"value": float("inf")})
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        e2e._strict_json_loads('{"value": Infinity}')
    with pytest.raises(ValueError, match="non-finite JSON number"):
        e2e._strict_json_loads('{"value": 1e999}')
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        e2e._strict_json_loads('{"value": 1, "value": 2}')

    class ExtraContentClient(FastClient):
        async def call_tool(self, tool, extra_arguments):
            result = await super().call_tool(tool, extra_arguments)
            result.content.append(SimpleNamespace(type="image", data=b"x" * 100_000))
            return result

    monkeypatch.setattr(e2e, "RUNS", 1)
    ticks = iter([0, 1_000_000])
    monkeypatch.setattr(e2e.time, "perf_counter_ns", lambda: next(ticks))
    with pytest.raises(AssertionError, match="exactly one compatibility"):
        await e2e._measure(
            ExtraContentClient(), "tool", arguments, validate,
            time.monotonic() + 1.0)


@pytest.mark.asyncio
async def test_catalog_baseline_rejects_malformed_or_consistently_drifted_catalog():
    from mcp import Client
    from server.mcp.adapter import mcp as server_app

    async with Client(server_app, mode="auto") as client:
        valid_record = await e2e._catalog_baseline(
            client, time.monotonic() + 5.0)
    e2e._verify_catalog_baseline(valid_record)
    assert valid_record["server_name"] == e2e.FROZEN_SERVER_NAME
    assert valid_record["server_version"] == e2e.FROZEN_SERVER_VERSION

    record = {
        "ordered_tools": list(e2e.EXPECTED_TOOLS),
        "server_name": e2e.FROZEN_SERVER_NAME,
        "server_version": e2e.FROZEN_SERVER_VERSION,
        "next_cursor": None,
        "result_type": "complete",
        "ordered_catalog": [
            {"name": name, "inputSchema": {}, "outputSchema": {}}
            for name in e2e.EXPECTED_TOOLS[:2]
        ] + ["not-an-object"],
        "ordered_catalog_bytes": 0,
        "ordered_catalog_sha256": "0" * 64,
        "schema_bytes": 0,
        "schema_sha256": "0" * 64,
        "instructions": "x",
        "instructions_utf8_bytes": 1,
        "instructions_sha256": hashlib.sha256(b"x").hexdigest(),
        "stable_repeated_list": True,
    }
    record["next_cursor"] = "more"
    with pytest.raises(AssertionError, match="shape or order differs"):
        e2e._verify_catalog_baseline(record)
    record["next_cursor"] = None
    record["result_type"] = "input_required"
    with pytest.raises(AssertionError, match="shape or order differs"):
        e2e._verify_catalog_baseline(record)
    record["result_type"] = "complete"
    record["server_name"] = ""
    with pytest.raises(AssertionError, match="shape or order differs"):
        e2e._verify_catalog_baseline(record)
    record["server_name"] = e2e.FROZEN_SERVER_NAME
    record["server_version"] = ""
    with pytest.raises(AssertionError, match="shape or order differs"):
        e2e._verify_catalog_baseline(record)
    record["server_version"] = e2e.FROZEN_SERVER_VERSION
    with pytest.raises(AssertionError, match="ordered catalog payload differs"):
        e2e._verify_catalog_baseline(record)
    catalog = [
        {"name": name, "inputSchema": {}, "outputSchema": {}}
        for name in e2e.EXPECTED_TOOLS
    ]
    schemas = [
        {"name": item["name"], "inputSchema": item["inputSchema"],
         "outputSchema": item["outputSchema"]}
        for item in catalog
    ]
    catalog_bytes, catalog_sha = e2e._canonical(catalog)
    schema_bytes, schema_sha = e2e._canonical(schemas)
    record.update({
        "ordered_catalog": catalog,
        "ordered_catalog_bytes": catalog_bytes,
        "ordered_catalog_sha256": catalog_sha,
        "schema_bytes": schema_bytes,
        "schema_sha256": schema_sha,
    })
    with pytest.raises(AssertionError, match="differs from Task 17 freeze"):
        e2e._verify_catalog_baseline(record)


def test_sample_preimage_limit_is_global_across_three_tools(monkeypatch):
    exact = {name: {} for name in e2e.EXPECTED_TOOLS}
    assert e2e._require_exact_measurement_results(exact) == exact
    with pytest.raises(AssertionError, match="tool set differs"):
        e2e._require_exact_measurement_results({**exact, "extra": {}})
    monkeypatch.setattr(e2e, "MAX_SAMPLE_RESULTS_BYTES", 5)
    records = [
        {"sample_results": [{"result_bytes": 2}]},
        {"sample_results": [{"result_bytes": 2}]},
        {"sample_results": [{"result_bytes": 2}]},
    ]
    with pytest.raises(AssertionError, match="all measurement preimages"):
        e2e._sample_result_total(records)


def test_bridge_unavailable_requires_exact_retryable_true():
    expected = {"code": "BRIDGE_UNAVAILABLE", "retryable": True}
    assert e2e._require_bridge_unavailable(expected) == expected
    invalid = [
        {"code": "BRIDGE_UNAVAILABLE", "retryable": False},
        {"code": "BRIDGE_UNAVAILABLE", "retryable": 1},
        {"code": "BRIDGE_UNAVAILABLE", "retryable": True, "extra": None},
    ]
    for value in invalid:
        with pytest.raises(AssertionError, match="unexpected post-kill error data"):
            e2e._require_bridge_unavailable(value)


def test_bounded_subprocess_stdout_rejects_excess_output(tmp_path, monkeypatch):
    pgid_path = tmp_path / "bounded.pgid"
    script = (
        "import os,signal,subprocess,sys,time; from pathlib import Path; "
        "os.setsid() if os.getpgrp()!=os.getpid() else None; "
        f"Path({str(pgid_path)!r}).write_text(str(os.getpgrp())); "
        "subprocess.Popen([sys.executable,'-c',"
        "'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "time.sleep(30)']); "
        "os.write(1,b'x'*1024); time.sleep(30)"
    )
    real_popen = e2e.subprocess.Popen
    spawned = {}

    def capture_process(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        spawned["process"] = process
        return process

    monkeypatch.setattr(e2e.subprocess, "Popen", capture_process)
    started = time.monotonic()
    with pytest.raises(ValueError, match="subprocess output exceeds"):
        e2e._bounded_process_stdout(
            [sys.executable, "-c", script], cwd=tmp_path,
            deadline=time.monotonic() + 2.0, max_bytes=8)
    assert time.monotonic() - started < 2.0
    process = spawned["process"]
    pgid = int(pgid_path.read_text())
    try:
        assert process.returncode is not None
        with pytest.raises(ProcessLookupError):
            os.killpg(pgid, 0)
    finally:
        process_registry.signal_group_id(pgid, signal.SIGKILL)


def test_recovery_supervisor_rejects_completion_observed_after_deadline(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    registry = tmp_path / "registry"
    registry.mkdir(mode=0o700)
    output = tmp_path / "late.json"
    clock = {"now": 10.0}

    class LateProcess:
        pid = 424242
        returncode = 0

        def poll(self):
            clock["now"] = 11.0
            return self.returncode

    fake_time = SimpleNamespace(
        monotonic=lambda: clock["now"],
        monotonic_ns=lambda: int(clock["now"] * 1_000_000_000),
        sleep=lambda seconds: clock.__setitem__("now", clock["now"] + seconds),
    )
    monkeypatch.setattr(e2e, "time", fake_time)
    monkeypatch.setattr(e2e.subprocess, "Popen", lambda *_args, **_kwargs: LateProcess())
    monkeypatch.setattr(e2e, "scan_records", lambda *_args, **_kwargs: ([], False))
    monkeypatch.setattr(e2e, "cleanup_registry", lambda *_args, **_kwargs: None)
    args = SimpleNamespace(
        root=str(tmp_path), output=str(output), process_registry=str(registry),
        timeout_seconds=1.0,
    )
    assert e2e._supervise_recovery(args) == 1
    artifact = json.loads(output.read_text())
    assert artifact["worker_timed_out"] is True


def test_recovery_supervisor_does_not_signal_replaced_outer_record(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    registry = tmp_path / "registry"
    registry.mkdir(mode=0o700)
    output = tmp_path / "replaced-worker.json"
    record = registry / "recovery-worker.json"
    original = tmp_path / "original-worker.json"
    marker = process_registry.new_marker()
    signaled = []
    spawned = {}
    observed = threading.Event()
    replaced = threading.Event()
    real_popen = e2e.subprocess.Popen
    real_scan = e2e.scan_records

    def spawn(command, *args, **kwargs):
        process = real_popen(command, *args, **kwargs)
        spawned["process"] = process
        return process

    def replace_record():
        deadline = time.monotonic() + 2.0
        if not observed.wait(max(0.0, deadline - time.monotonic())):
            return
        value = json.loads(record.read_text())
        record.rename(original)
        process_registry._write_private_json(record, value)
        replaced.set()

    def scan(*args, **kwargs):
        result = real_scan(*args, **kwargs)
        if any(item.path == record for item in result[0]):
            observed.set()
        return result

    monkeypatch.setattr(e2e, "new_marker", lambda: marker)
    monkeypatch.setattr(e2e, "_recovery_worker_command", lambda *_args: [
        sys.executable, "-c",
        "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "time.sleep(30)"])
    monkeypatch.setattr(e2e.subprocess, "Popen", spawn)
    monkeypatch.setattr(e2e, "scan_records", scan)
    monkeypatch.setattr(
        process_registry, "signal_group_id",
        lambda pgid, sig: signaled.append((pgid, sig)))
    monkeypatch.setattr(e2e, "RECOVERY_CLEANUP_MARGIN", 0.5)
    monkeypatch.setattr(e2e, "RECOVERY_REGISTRY_RESERVE", 0.1)
    replacer = threading.Thread(target=replace_record)
    replacer.start()
    args = SimpleNamespace(
        root=str(tmp_path), output=str(output), process_registry=str(registry),
        timeout_seconds=0.2,
    )
    try:
        assert e2e._supervise_recovery(args) == 1
        replacer.join(timeout=2)
        assert replaced.is_set()
        assert signaled == []
        assert spawned["process"].poll() is None
    finally:
        replacer.join(timeout=2)
        process = spawned.get("process")
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        record.unlink(missing_ok=True)
        original.unlink(missing_ok=True)


def test_recovery_supervisor_reaps_child_left_by_exited_worker(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    registry = tmp_path / "registry"
    registry.mkdir(mode=0o700)
    output = tmp_path / "orphan.json"
    pgid_file = tmp_path / "worker.pgid"
    script = (
        "import os,subprocess; from pathlib import Path; "
        f"Path({str(pgid_file)!r}).write_text(str(os.getpgrp())); "
        "subprocess.Popen(['/bin/sleep', '30'])"
    )
    monkeypatch.setattr(
        e2e, "_recovery_worker_command",
        lambda _args, _marker, _not_before_ns: [sys.executable, "-c", script])
    monkeypatch.setattr(e2e, "RECOVERY_CLEANUP_MARGIN", 3.0)
    monkeypatch.setattr(e2e, "RECOVERY_WORKER_TERM_GRACE", 1.0)
    args = SimpleNamespace(
        root=str(tmp_path), output=str(output), process_registry=str(registry),
        timeout_seconds=2.0,
    )
    assert e2e._supervise_recovery(args) == 1
    pgid = int(pgid_file.read_text())
    try:
        with pytest.raises(ProcessLookupError):
            os.killpg(pgid, 0)
    finally:
        process_registry.signal_group_id(pgid, signal.SIGKILL)
    assert "survived its leader" in json.loads(output.read_text())["error"]


def test_recovery_supervisor_signal_is_safe_during_poll_and_registry_cleanup(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    original = signal.getsignal(signal.SIGTERM)

    class FakeProcess:
        pid = 424242
        returncode = 0

        def __init__(self, cancel_during_poll):
            self.cancel_during_poll = cancel_during_poll
            self.fired = False

        def poll(self):
            if self.cancel_during_poll and not self.fired:
                self.fired = True
                os.kill(os.getpid(), signal.SIGTERM)
            return self.returncode

        def wait(self, timeout):
            assert timeout >= 0
            return self.returncode

    for window in ("poll", "registry"):
        registry = tmp_path / f"registry-{window}"
        registry.mkdir(mode=0o700)
        output = tmp_path / f"cancel-{window}.json"
        def spawn(command, *_args, _window=window, **_kwargs):
            process = FakeProcess(_window == "poll")
            record = Path(command[3])
            process_registry._write_private_json(record, {
                "schema_version": 1,
                "pid": process.pid,
                "pgid": process.pid,
                "marker": command[7],
                "started_monotonic_ns": time.monotonic_ns(),
            })
            process_registry.finish_publication_reservation(
                Path(command[4]), int(command[5]), int(command[6]))
            return process

        monkeypatch.setattr(e2e.subprocess, "Popen", spawn)

        def cleanup(*_args, _window=window, **_kwargs):
            if _window == "registry":
                os.kill(os.getpid(), signal.SIGTERM)

        monkeypatch.setattr(e2e, "cleanup_registry", cleanup)
        args = SimpleNamespace(
            root=str(tmp_path), output=str(output), process_registry=str(registry),
            timeout_seconds=1.0,
        )
        assert e2e._supervise_recovery(args) == 1
        artifact = json.loads(output.read_text())
        assert artifact["worker_cancelled_signal"] == signal.SIGTERM
        assert "cancelled by signal" in artifact["error"]
        assert signal.getsignal(signal.SIGTERM) == original


def test_recovery_supervisor_reaps_resistant_worker_and_registered_group(
    tmp_path, monkeypatch,
):
    tmp_path.chmod(0o700)
    runtime = tmp_path / "runtime"
    registry = tmp_path / "registry"
    runtime.mkdir(mode=0o700)
    registry.mkdir(mode=0o700)
    output = tmp_path / "recovery.json"
    pid_file = tmp_path / "child.pid"
    resistant = (
        "import signal,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    )

    def fake_worker(_args, marker, _not_before_ns):
        record = registry / "late.json"
        reservation, device, inode = process_registry.reserve_publication(record)
        script = (
            "import signal,subprocess,sys,time; from pathlib import Path; "
            f"p=subprocess.Popen([sys.executable,{process_registry.__file__!r},"
            f"{process_registry.REPLACE_MODE!r},sys.argv[1],sys.argv[2],"
            f"sys.argv[3],sys.argv[4],sys.argv[5],sys.executable,'-c',"
            f"{resistant!r}],start_new_session=True); "
            "Path(sys.argv[6]).write_text(str(p.pid)); "
            "deadline=time.monotonic()+2; "
            "\nwhile not Path(sys.argv[1]).exists() and time.monotonic()<deadline: "
            "time.sleep(0.01)\n"
            "signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"
        )
        return [
            sys.executable, "-c", script,
            str(record), str(reservation), str(device), str(inode), marker,
            str(pid_file),
        ]

    monkeypatch.setattr(e2e, "_recovery_worker_command", fake_worker)
    monkeypatch.setattr(e2e, "RECOVERY_CLEANUP_MARGIN", 2.0)
    monkeypatch.setattr(e2e, "RECOVERY_WORKER_TERM_GRACE", 0.1)
    monkeypatch.setattr(e2e, "RECOVERY_GROUP_TERM_GRACE", 0.1)
    args = SimpleNamespace(
        root=str(runtime), output=str(output), process_registry=str(registry),
        timeout_seconds=0.2,
    )
    started = time.monotonic()
    assert e2e._supervise_recovery(args) == 1
    assert time.monotonic() - started < 4.0
    child_pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.killpg(child_pid, 0)
    assert list(registry.iterdir()) == []
    artifact = json.loads(output.read_text())
    assert artifact["success"] is False and artifact["worker_timed_out"] is True


def test_provenance_ignores_ignored_untracked_python(monkeypatch):
    ignored = e2e.ROOT / "tests/__pycache__/ignored-source.py"
    ignored.parent.mkdir(exist_ok=True)
    ignored.write_text("must not enter the source manifest")
    monkeypatch.setattr(e2e, "BLENDER", "/bin/echo")
    original_git_text = e2e._git_text
    monkeypatch.setattr(
        e2e, "_git_text",
        lambda deadline, *args, **kwargs: ""
        if args == ("status", "--porcelain=v1", "--untracked-files=all")
        else original_git_text(deadline, *args, **kwargs),
    )
    _clear_vendor_bytecode()
    try:
        provenance = e2e._current_provenance(time.monotonic() + 10.0)
    finally:
        ignored.unlink(missing_ok=True)
    assert str(ignored.relative_to(e2e.ROOT)) not in provenance["sources"]["files"]


def test_provenance_rejects_vendor_extra_or_content_drift(monkeypatch):
    vendor = e2e.ROOT / "bridge/_vendor/protocol/envelope.py"
    extra = vendor.with_suffix(".so")
    original = vendor.read_bytes()
    monkeypatch.setattr(e2e, "BLENDER", "/bin/echo")
    original_git_text = e2e._git_text
    monkeypatch.setattr(
        e2e, "_git_text",
        lambda deadline, *args, **kwargs: ""
        if args == ("status", "--porcelain=v1", "--untracked-files=all")
        else original_git_text(deadline, *args, **kwargs),
    )
    _clear_vendor_bytecode()
    try:
        extra.write_bytes(b"executable blind spot")
        with pytest.raises(AssertionError, match="vendored protocol file set"):
            e2e._current_provenance(time.monotonic() + 10.0)
        extra.unlink()
        vendor.write_bytes(original + b"\n# drift\n")
        with pytest.raises(AssertionError, match="vendored protocol content differs"):
            e2e._current_provenance(time.monotonic() + 10.0)
    finally:
        extra.unlink(missing_ok=True)
        vendor.write_bytes(original)


def test_required_provenance_input_must_be_tracked(monkeypatch):
    monkeypatch.setattr(
        e2e, "_git_bytes",
        lambda *_args, **_kwargs: b"pyproject.toml\0")
    with pytest.raises(RuntimeError, match="required provenance inputs are not tracked"):
        e2e._tracked_sources(
            time.monotonic() + 1.0, {e2e.ROOT / "uv.lock"})


def test_bounded_provenance_read_rejects_symlink_oversize_and_expired(tmp_path):
    regular = tmp_path / "regular.py"
    regular.write_bytes(b"12345")
    symlink = tmp_path / "linked.py"
    symlink.symlink_to(regular)
    with pytest.raises(ValueError, match="bounded regular"):
        e2e._read_bounded_bytes(symlink, time.monotonic() + 1.0, 16)
    with pytest.raises(ValueError, match="bounded regular"):
        e2e._read_bounded_bytes(regular, time.monotonic() + 1.0, 4)
    with pytest.raises(TimeoutError, match="deadline expired"):
        e2e._read_bounded_bytes(regular, time.monotonic() - 1.0, 16)


def test_audit_reader_rejects_fifo_and_oversize_without_blocking(
    tmp_path, monkeypatch,
):
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)
    path = logs / "server-2026-08-08.jsonl"
    os.mkfifo(path, mode=0o600)
    started = time.monotonic()
    with pytest.raises(PermissionError, match="private audit file"):
        e2e._audit_rows(tmp_path, time.monotonic() + 0.5)
    assert time.monotonic() - started < 0.5
    path.unlink()
    path.write_bytes(b"12345")
    path.chmod(0o600)
    monkeypatch.setattr(e2e, "MAX_AUDIT_FILE_BYTES", 4)
    with pytest.raises(ValueError, match="bounded regular file"):
        e2e._audit_rows(tmp_path, time.monotonic() + 0.5)


@pytest.mark.parametrize("mutation", [
    "document_drift", "gate_drift", "extra_key", "missing_key",
    "bool_schema", "bool_checked",
])
def test_provenance_rejects_approved_tuple_drift(monkeypatch, mutation):
    path = e2e.ATTESTATION_PATH
    original_bytes = path.read_bytes()
    attestation = json.loads(original_bytes)
    approved = attestation["approved_tuple"]
    if mutation == "document_drift":
        approved["urs_sha256"] = "0" * 64
    elif mutation == "gate_drift":
        approved["unit_tests"] += 1
    elif mutation == "extra_key":
        approved["unexpected"] = 1
    elif mutation == "missing_key":
        del approved["plan_sha256"]
    elif mutation == "bool_schema":
        attestation["schema_version"] = True
    else:
        approved["checked_checkboxes"] = False
    path.write_text(json.dumps(attestation))
    original_git_text = e2e._git_text

    def allow_fixture_edit(deadline, *args, **kwargs):
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return ""
        return original_git_text(deadline, *args, **kwargs)

    monkeypatch.setattr(e2e, "_git_text", allow_fixture_edit)
    monkeypatch.setattr(e2e, "BLENDER", "/bin/echo")
    _clear_vendor_bytecode()
    try:
        with pytest.raises((AssertionError, ValueError)):
            e2e._current_provenance(time.monotonic() + 10.0)
    finally:
        path.write_bytes(original_bytes)
