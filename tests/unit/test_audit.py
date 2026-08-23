import datetime
import fcntl
import hashlib
import json
import multiprocessing
import os
import stat
import threading
import time
import tracemalloc
from pathlib import Path

import pytest
from server.core.audit import AuditLog


def _record_split_in_process(logs: str, index: int, start) -> None:
    """Spawn-safe helper: make one logical record use two physical writes."""
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen

    class SplitWriter:
        def __init__(self, fd, mode, encoding):
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._inner.close()

        def write(self, value):
            midpoint = len(value) // 2
            self._inner.write(value[:midpoint])
            self._inner.flush()
            time.sleep(0.005)
            self._inner.write(value[midpoint:])

    audit_module.os.fdopen = SplitWriter
    start.wait()
    AuditLog(Path(logs)).record(
        f"process-tool-{index}", f"process-request-{index}",
        ok=True, duration_ms=1.0)


def _hold_file_lock(path: str, ready, release) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        ready.set()
        release.wait()
    finally:
        os.close(fd)


def test_record_appends_jsonl_with_digest_not_raw_params(tmp_path):
    log = AuditLog(tmp_path / "logs")
    params = {"instance_id": "gui-1-aa"}
    log.record("get_scene_summary", "req1", ok=True, duration_ms=12.5,
               instance_id="gui-1-aa", params=params)
    files = list((tmp_path / "logs").glob("server-*.jsonl"))
    assert len(files) == 1
    assert stat.S_IMODE(files[0].stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "logs").stat().st_mode) == 0o700
    row = json.loads(files[0].read_text().splitlines()[0])
    assert set(row) == {"ts", "request_id", "tool", "instance_id",
                        "transaction_id", "params_digest", "ok", "duration_ms",
                        "paths", "error"}
    assert row["tool"] == "get_scene_summary"
    assert row["transaction_id"] is None          # Phase 0 占位（§5.2）
    assert row["paths"] == []
    assert "gui-1-aa" not in json.dumps(row.get("params_digest"))
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    assert row["params_digest"] == hashlib.sha256(canonical).hexdigest()[:16]


def test_huge_params_use_fixed_bounded_digest_without_full_dumps(
        tmp_path, monkeypatch):
    import server.core.audit as audit_module

    params = {"items": ["sensitive"] * 1_000_000}
    real_dumps = audit_module.json.dumps

    def reject_whole_params(value, *args, **kwargs):
        if value is params:
            raise AssertionError("whole params were materialized")
        return real_dumps(value, *args, **kwargs)

    monkeypatch.setattr(audit_module.json, "dumps", reject_whole_params)
    log = AuditLog(tmp_path / "logs")
    started = time.monotonic()
    log.record("tool", "request", ok=True, duration_ms=1.0, params=params,
               deadline=started + 1.0)
    assert time.monotonic() - started < 0.5
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    row = json.loads(path.read_text())
    assert row["params_digest"] == audit_module.PARAMS_TRUNCATED_DIGEST
    assert path.stat().st_size <= audit_module.MAX_AUDIT_LINE_BYTES
    assert "sensitive" not in path.read_text()

    aggregate = {f"aggregate-secret-{index:05d}": "" for index in range(4_096)}
    huge_secret = "huge-secret-" + "x" * (  # pragma: allowlist secret
        audit_module.MAX_AUDIT_PARAMS_BYTES * 128
    )
    huge_key = {huge_secret: None}
    huge_value = {"value": huge_secret}
    invalid_unicode = {"value": "invalid-secret-\ud800"}
    multibyte_text_over = {
        "": "界" * (audit_module.MAX_AUDIT_PARAMS_BYTES // 3 + 1)}
    real_iterencode = audit_module.json.JSONEncoder.iterencode

    def reject_aggregate_encoder(self, value, *args, **kwargs):
        if value is aggregate or any(value is blocked for blocked in
                                     (huge_key, huge_value, invalid_unicode,
                                      multibyte_text_over)):
            raise AssertionError("rejected params reached encoder/sort path")
        return real_iterencode(self, value, *args, **kwargs)

    monkeypatch.setattr(audit_module.json.JSONEncoder, "iterencode",
                        reject_aggregate_encoder)
    started = time.monotonic()
    log.record("tool", "aggregate", ok=True, duration_ms=1.0,
               params=aggregate, deadline=started + 1.0)
    assert time.monotonic() - started < 0.5
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[-1]["params_digest"] == audit_module.PARAMS_TRUNCATED_DIGEST
    assert "aggregate-secret" not in path.read_text()

    peaks = []
    tracemalloc.start()
    try:
        for request_id, value in (("huge-key", huge_key),
                                  ("huge-value", huge_value)):
            tracemalloc.reset_peak()
            log.record("tool", request_id, ok=True, duration_ms=1.0, params=value,
                       deadline=time.monotonic() + 1.0)
            peaks.append(tracemalloc.get_traced_memory()[1])
    finally:
        tracemalloc.stop()
    assert max(peaks) < audit_module.MAX_AUDIT_PARAMS_BYTES * 4

    boundary_chars = (audit_module.MAX_AUDIT_PARAMS_BYTES - 8) // 3
    multibyte_boundary = {"k": "界" * boundary_chars}
    multibyte_over = {"k": "界" * (boundary_chars + 1)}
    boundary_canonical = json.dumps(
        multibyte_boundary, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()
    assert len(boundary_canonical) <= audit_module.MAX_AUDIT_PARAMS_BYTES
    assert len(json.dumps(multibyte_over, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode()) \
        > audit_module.MAX_AUDIT_PARAMS_BYTES
    log.record("tool", "multibyte-boundary", ok=True, duration_ms=1.0,
               params=multibyte_boundary)
    log.record("tool", "multibyte-over", ok=True, duration_ms=1.0,
               params=multibyte_over)
    log.record("tool", "multibyte-text-over", ok=True, duration_ms=1.0,
               params=multibyte_text_over)
    log.record("tool", "invalid-unicode", ok=True, duration_ms=1.0,
               params=invalid_unicode)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["params_digest"] for row in rows[-6:]] == [
        audit_module.PARAMS_TRUNCATED_DIGEST,
        audit_module.PARAMS_TRUNCATED_DIGEST,
        hashlib.sha256(boundary_canonical).hexdigest()[:16],
        audit_module.PARAMS_TRUNCATED_DIGEST,
        audit_module.PARAMS_TRUNCATED_DIGEST,
        audit_module.PARAMS_UNENCODABLE_DIGEST,
    ]
    text = path.read_text()
    assert "huge-secret" not in text
    assert "invalid-secret" not in text


def test_deep_and_unencodable_params_use_bounded_sentinel(tmp_path):
    import server.core.audit as audit_module

    deep = {"secret": "must-not-leak"}  # pragma: allowlist secret
    for _ in range(audit_module.MAX_AUDIT_PARAMS_DEPTH + 1_000):
        deep = {"x": deep}
    log = AuditLog(tmp_path / "logs")
    log.record("tool", "deep", ok=True, duration_ms=1.0, params=deep)
    log.record("tool", "object", ok=True, duration_ms=1.0,
               params={"value": object()})
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    text = path.read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert [row["params_digest"] for row in rows] == [
        audit_module.PARAMS_UNENCODABLE_DIGEST,
        audit_module.PARAMS_UNENCODABLE_DIGEST,
    ]
    assert "must-not-leak" not in text


def test_unbounded_audit_fields_fail_closed_before_file_creation(tmp_path):
    import server.core.audit as audit_module

    log = AuditLog(tmp_path / "logs")
    cases = [
        (("x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1), "request"), {}),
        (("tool", "x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)), {}),
        (("tool", 1 << (audit_module.MAX_AUDIT_REQUEST_ID_BITS + 1)), {}),
        (("tool", True), {}),
        (("tool", "request"),
         {"instance_id": "x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)}),
        (("tool", "request"),
         {"error": "x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)}),
        (("tool", "request"),
         {"paths": ["x"] * (audit_module.MAX_AUDIT_PATHS + 1)}),
        (("tool", "request"),
         {"paths": ["x" * (audit_module.MAX_AUDIT_FIELD_BYTES + 1)]}),
    ]
    for args, kwargs in cases:
        with pytest.raises(ValueError):
            log.record(*args, ok=True, duration_ms=1.0, **kwargs)
    assert list((tmp_path / "logs").iterdir()) == []


def test_created_directories_and_file_ignore_restrictive_umask(tmp_path):
    logs = tmp_path / "runtime" / "logs"
    previous_umask = os.umask(0o777)
    try:
        log = AuditLog(logs)
        log.record("tool", "request", ok=True, duration_ms=1.0)
    finally:
        os.umask(previous_umask)
    path = next(logs.glob("server-*.jsonl"))
    assert stat.S_IMODE(logs.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(logs.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_two_records_two_lines(tmp_path):
    log = AuditLog(tmp_path / "logs")
    log.record("a", "r1", ok=True, duration_ms=1.0)
    log.record("b", "r2", ok=False, duration_ms=2.0, error="BRIDGE_UNAVAILABLE")
    f = next((tmp_path / "logs").glob("server-*.jsonl"))
    lines = [json.loads(x) for x in f.read_text().splitlines()]
    assert [r["tool"] for r in lines] == ["a", "b"]
    assert lines[1]["error"] == "BRIDGE_UNAVAILABLE"


def test_rejects_wide_runtime_root_without_chmod(tmp_path):
    root = tmp_path / "wide-runtime"
    root.mkdir(mode=0o755)
    root.chmod(0o755)
    with pytest.raises(PermissionError, match="private directory"):
        AuditLog(root / "logs")
    assert stat.S_IMODE(root.stat().st_mode) == 0o755


def test_rejects_logs_directory_owned_by_other_uid(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    logs = tmp_path / "runtime" / "logs"
    logs.mkdir(parents=True, mode=0o700)
    logs.parent.chmod(0o700)
    logs.chmod(0o700)
    real_stat = audit_module.os.stat
    foreign_uid = os.geteuid() + 1

    def foreign_logs_stat(path, *, dir_fd=None, follow_symlinks=True):
        result = real_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if path == logs.name and dir_fd is not None:
            values = list(result)
            values[4] = foreign_uid
            return os.stat_result(values)
        return result

    monkeypatch.setattr(audit_module.os, "stat", foreign_logs_stat)
    with pytest.raises(PermissionError, match="private directory"):
        AuditLog(logs)


def test_rejects_preexisting_wide_audit_file(tmp_path):
    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    path.write_text("foreign\n")
    path.chmod(0o644)
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert path.read_text() == "foreign\n"
    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_fifo_audit_file_never_blocks(tmp_path):
    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    os.mkfifo(path, mode=0o600)
    started = time.monotonic()
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert time.monotonic() - started < 0.5


def test_device_audit_fd_is_rejected_before_write(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    path.write_text("foreign\n")
    path.chmod(0o600)
    real_open = audit_module.os.open

    def swap_open_to_device(name, flags, mode=0o777, *, dir_fd=None):
        if (name == path.name and dir_fd is not None
                and not flags & os.O_EXCL):
            return real_open("/dev/null", os.O_WRONLY | os.O_NONBLOCK)
        return real_open(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(audit_module.os, "open", swap_open_to_device)
    monkeypatch.setattr(audit_module.fcntl, "flock", lambda _fd, _flags: None)
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert path.read_text() == "foreign\n"


def test_symlink_audit_file_is_preserved(tmp_path):
    log = AuditLog(tmp_path / "logs")
    now = datetime.datetime.now(datetime.UTC)
    path = tmp_path / "logs" / f"server-{now:%Y-%m-%d}.jsonl"
    target = tmp_path / "foreign.jsonl"
    target.write_text("foreign\n")
    target.chmod(0o600)
    path.symlink_to(target)
    with pytest.raises(PermissionError, match="private audit file"):
        log.record("tool", "request", ok=True, duration_ms=1.0)
    assert path.is_symlink() and target.read_text() == "foreign\n"


def test_concurrent_first_initialization_is_race_safe_with_restrictive_umask(
        tmp_path, monkeypatch):
    import server.core.audit as audit_module

    logs = tmp_path / "first-logs"
    start = threading.Barrier(16)
    chmod_entered = threading.Event()
    release_chmod = threading.Event()
    errors = []
    real_chmod = audit_module.os.chmod
    real_fchmod = audit_module.os.fchmod
    real_umask = audit_module.os.umask
    umask_calls = []
    directory_fchmod_calls = []

    def delayed_first_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if mode == 0o700 and not chmod_entered.is_set():
            chmod_entered.set()
            assert release_chmod.wait(1.0)
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    def track_directory_fchmod(fd, mode):
        if mode == 0o700:
            directory_fchmod_calls.append(fd)
        return real_fchmod(fd, mode)

    monkeypatch.setattr(audit_module.os, "chmod", delayed_first_chmod)
    monkeypatch.setattr(audit_module.os, "fchmod", track_directory_fchmod)

    def reject_audit_umask(mode):
        umask_calls.append(mode)
        raise AssertionError("AuditLog changed the process umask")

    previous_umask = real_umask(0o777)
    monkeypatch.setattr(audit_module.os, "umask", reject_audit_umask)

    def initialize():
        try:
            start.wait()
            AuditLog(logs)
        except BaseException as exc:
            errors.append(exc)

    try:
        workers = [threading.Thread(target=initialize) for _ in range(16)]
        for worker in workers:
            worker.start()
        assert chmod_entered.wait(1.0)
        unrelated = tmp_path / "unrelated.txt"
        unrelated_fd = os.open(unrelated, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                               0o666)
        os.close(unrelated_fd)
        assert stat.S_IMODE(unrelated.stat().st_mode) == 0
        time.sleep(0.02)
        release_chmod.set()
        for worker in workers:
            worker.join(timeout=2.0)
    finally:
        release_chmod.set()
        real_umask(previous_umask)
    assert all(not worker.is_alive() for worker in workers)
    assert errors == []
    assert umask_calls == []

    monkeypatch.setattr(audit_module.os, "chmod", real_chmod)
    monkeypatch.setattr(audit_module.os, "fchmod", real_fchmod)
    real_stat = audit_module.os.stat

    def assert_first_status_replacement_rejected(label, replacement_mode):
        attack_runtime = tmp_path / f"attack-runtime-{label}"
        attack_runtime.mkdir(mode=0o700)
        attack_runtime.chmod(0o700)
        attack_logs = attack_runtime / "logs"
        original = tmp_path / f"created-original-{label}"
        replacement = tmp_path / f"replacement-{label}"
        replacement.mkdir(mode=0o700)
        replacement.chmod(0o700)
        swapped = False

        def replace_created_before_first_status(
                name, *, dir_fd=None, follow_symlinks=True):
            nonlocal swapped
            if name == attack_logs.name and dir_fd is not None and not swapped:
                try:
                    real_stat(attack_logs, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    swapped = True
                    attack_logs.chmod(0o700)
                    attack_logs.rename(original)
                    replacement.rename(attack_logs)
                    attack_logs.chmod(replacement_mode)
            return real_stat(name, dir_fd=dir_fd,
                             follow_symlinks=follow_symlinks)

        monkeypatch.setattr(audit_module.os, "stat",
                            replace_created_before_first_status)
        previous_umask = real_umask(0o777)
        rejected = False
        try:
            try:
                AuditLog(attack_logs)
            except PermissionError as exc:
                assert "private directory" in str(exc)
                rejected = True
        finally:
            real_umask(previous_umask)
            monkeypatch.setattr(audit_module.os, "stat", real_stat)
        assert swapped
        observed_mode = stat.S_IMODE(real_stat(attack_logs).st_mode)
        attack_logs.chmod(0o700)
        if original.exists():
            original.chmod(0o700)
        return swapped, observed_mode, rejected

    replacement_results = [
        assert_first_status_replacement_rejected("0500", 0o500),
        assert_first_status_replacement_rejected("0700", 0o700),
    ]
    assert (directory_fchmod_calls, replacement_results) == (
        [], [(True, 0o500, True), (True, 0o700, True)])


def test_concurrent_first_file_creation_waits_for_fchmod(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    logs = tmp_path / "logs"
    first, second = AuditLog(logs), AuditLog(logs)
    fchmod_entered = threading.Event()
    release_fchmod = threading.Event()
    errors = []
    real_fchmod = audit_module.os.fchmod

    def delayed_first_fchmod(fd, mode):
        if mode == 0o600 and not fchmod_entered.is_set():
            fchmod_entered.set()
            assert release_fchmod.wait(1.0)
        return real_fchmod(fd, mode)

    monkeypatch.setattr(audit_module.os, "fchmod", delayed_first_fchmod)

    def record(log, request_id):
        try:
            log.record("tool", request_id, ok=True, duration_ms=1.0)
        except BaseException as exc:
            errors.append(exc)

    previous_umask = os.umask(0o777)
    try:
        worker_a = threading.Thread(target=record, args=(first, "a"))
        worker_a.start()
        assert fchmod_entered.wait(1.0)
        worker_b = threading.Thread(target=record, args=(second, "b"))
        worker_b.start()
        time.sleep(0.02)
        release_fchmod.set()
        worker_a.join(timeout=2.0)
        worker_b.join(timeout=2.0)
    finally:
        release_fchmod.set()
        os.umask(previous_umask)
    assert not worker_a.is_alive() and not worker_b.is_alive()
    assert errors == []
    path = next(logs.glob("server-*.jsonl"))
    assert len(path.read_text().splitlines()) == 2


def test_record_rejects_replaced_log_directory(tmp_path):
    logs = tmp_path / "logs"
    log = AuditLog(logs)
    original = tmp_path / "logs-original"
    logs.rename(original)
    logs.mkdir(mode=0o700)
    logs.chmod(0o700)
    try:
        with pytest.raises(PermissionError, match="private directory"):
            log.record("tool", "request", ok=True, duration_ms=1.0)
        assert list(logs.iterdir()) == []
    finally:
        logs.rmdir()
        original.rmdir()

    runtime = tmp_path / "runtime"
    runtime_logs = runtime / "logs"
    parent_log = AuditLog(runtime_logs)
    original_runtime = tmp_path / "runtime-original"
    runtime.rename(original_runtime)
    runtime.symlink_to(original_runtime, target_is_directory=True)
    try:
        with pytest.raises(PermissionError, match="private directory"):
            parent_log.record("tool", "symlink-parent", ok=True, duration_ms=1.0)
        assert list((original_runtime / "logs").iterdir()) == []
    finally:
        runtime.unlink()
        original_runtime.rename(runtime)

    runtime.rename(original_runtime)
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    (original_runtime / "logs").rename(runtime_logs)
    try:
        with pytest.raises(PermissionError, match="private directory"):
            parent_log.record("tool", "replaced-parent", ok=True, duration_ms=1.0)
        assert list(runtime_logs.iterdir()) == []
    finally:
        runtime_logs.rename(original_runtime / "logs")
        runtime.rmdir()
        original_runtime.rename(runtime)


def test_request_deadline_bounds_external_file_lock(tmp_path):
    log = AuditLog(tmp_path / "logs")
    log.record("first", "request-1", ok=True, duration_ms=1.0)
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    holder = context.Process(target=_hold_file_lock,
                             args=(str(path), ready, release))
    holder.start()
    assert ready.wait(2.0)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match="audit log lock timeout"):
            log.record("second", "request-2", ok=True, duration_ms=1.0,
                       deadline=started + 0.05)
        assert time.monotonic() - started < 0.3
    finally:
        release.set()
        holder.join(timeout=2.0)
    assert holder.exitcode == 0


def test_request_deadline_is_checked_between_serialization_steps(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    log = AuditLog(tmp_path / "logs")
    real_dumps = audit_module.json.dumps
    calls = []

    def slow_dumps(*args, **kwargs):
        calls.append(True)
        time.sleep(0.03)
        return real_dumps(*args, **kwargs)

    monkeypatch.setattr(audit_module.json, "dumps", slow_dumps)
    with pytest.raises(TimeoutError, match="audit deadline expired"):
        log.record("tool", "request", ok=True, duration_ms=1.0,
                   deadline=time.monotonic() + 0.01)
    assert len(calls) == 1
    assert list((tmp_path / "logs").iterdir()) == []

    monkeypatch.setattr(audit_module.json, "dumps", real_dumps)
    open_log = AuditLog(tmp_path / "open-logs")
    real_open = audit_module.os.open
    real_fchmod = audit_module.os.fchmod
    fchmod_calls = []

    def slow_file_open(name, flags, mode=0o777, *, dir_fd=None):
        fd = real_open(name, flags, mode, dir_fd=dir_fd)
        if isinstance(name, str) and name.startswith("server-"):
            time.sleep(0.03)
        return fd

    def track_fchmod(fd, mode):
        fchmod_calls.append((fd, mode))
        return real_fchmod(fd, mode)

    monkeypatch.setattr(audit_module.os, "open", slow_file_open)
    monkeypatch.setattr(audit_module.os, "fchmod", track_fchmod)
    with pytest.raises(TimeoutError, match="audit deadline expired"):
        open_log.record("tool", "slow-open", ok=True, duration_ms=1.0,
                        deadline=time.monotonic() + 0.01)
    assert fchmod_calls == []
    assert next((tmp_path / "open-logs").glob("server-*.jsonl")).read_bytes() == b""

    monkeypatch.setattr(audit_module.os, "open", real_open)
    chmod_log = AuditLog(tmp_path / "chmod-logs")

    def slow_file_fchmod(fd, mode):
        result = real_fchmod(fd, mode)
        if mode == 0o600:
            time.sleep(0.03)
        return result

    monkeypatch.setattr(audit_module.os, "fchmod", slow_file_fchmod)
    with pytest.raises(TimeoutError, match="audit deadline expired"):
        chmod_log.record("tool", "slow-fchmod", ok=True, duration_ms=1.0,
                         deadline=time.monotonic() + 0.01)
    assert next((tmp_path / "chmod-logs").glob("server-*.jsonl")).read_bytes() == b""


@pytest.mark.parametrize("slow_phase", ["write", "flush", "close"])
def test_request_deadline_is_checked_after_file_io(tmp_path, monkeypatch, slow_phase):
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen

    class SlowWriter:
        def __init__(self, fd, mode, encoding):
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            if slow_phase == "flush":
                time.sleep(0.03)
                self._inner.flush()
            if slow_phase == "close":
                time.sleep(0.03)
            self._inner.close()

        def write(self, value):
            if slow_phase == "write":
                time.sleep(0.03)
            return self._inner.write(value)

    monkeypatch.setattr(audit_module.os, "fdopen", SlowWriter)
    log = AuditLog(tmp_path / "logs")
    with pytest.raises(TimeoutError, match="audit deadline expired"):
        log.record("tool", "request", ok=True, duration_ms=1.0,
                   deadline=time.monotonic() + 0.01)


def test_fdopen_close_failure_does_not_close_reused_foreign_fd(tmp_path, monkeypatch):
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen
    foreign_path = tmp_path / "foreign.txt"
    foreign_path.write_bytes(b"")
    state = {"fd": None}

    def replace_with_foreign(fd):
        replacement = os.open(foreign_path, os.O_WRONLY | os.O_APPEND)
        if replacement != fd:
            os.dup2(replacement, fd)
            os.close(replacement)
        state["fd"] = fd

    class ConstructorCloseThenReuse:
        def __init__(self, fd, mode, encoding):
            real_fdopen(fd, mode, encoding=encoding).close()
            replace_with_foreign(fd)
            raise OSError("injected constructor failure")

    monkeypatch.setattr(audit_module.os, "fdopen", ConstructorCloseThenReuse)
    log = AuditLog(tmp_path / "logs")
    with pytest.raises(OSError, match="constructor failure"):
        log.record("tool", "constructor", ok=True, duration_ms=1.0)
    assert state["fd"] is not None
    try:
        os.write(state["fd"], b"constructor")
    finally:
        os.close(state["fd"])
    state["fd"] = None

    class CloseThenReuse:
        def __init__(self, fd, mode, encoding):
            self._fd = fd
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def write(self, value):
            return self._inner.write(value)

        def __exit__(self, *_args):
            self._inner.close()
            replace_with_foreign(self._fd)
            raise OSError("injected close failure")

    monkeypatch.setattr(audit_module.os, "fdopen", CloseThenReuse)
    with pytest.raises(OSError, match="close failure"):
        log.record("tool", "context-exit", ok=True, duration_ms=1.0)
    assert state["fd"] is not None
    try:
        os.write(state["fd"], b"foreign")
    finally:
        os.close(state["fd"])


def test_concurrent_records_remain_complete_jsonl_lines(tmp_path, monkeypatch):
    """Force each TextIO write into two syscalls to expose record interleaving."""
    import server.core.audit as audit_module

    real_fdopen = audit_module.os.fdopen

    class SplitWriter:
        def __init__(self, fd, mode, encoding):
            self._inner = real_fdopen(fd, mode, encoding=encoding)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self._inner.close()

        def write(self, value):
            midpoint = len(value) // 2
            self._inner.write(value[:midpoint])
            self._inner.flush()
            time.sleep(0.005)
            self._inner.write(value[midpoint:])

    monkeypatch.setattr(audit_module.os, "fdopen", SplitWriter)
    log = AuditLog(tmp_path / "logs")
    start = threading.Barrier(12)

    def record(index):
        start.wait()
        log.record(f"tool-{index}", f"request-{index}", ok=True, duration_ms=1.0)

    workers = [threading.Thread(target=record, args=(index,)) for index in range(12)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=2.0)

    assert all(not worker.is_alive() for worker in workers)
    path = next((tmp_path / "logs").glob("server-*.jsonl"))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert {row["tool"] for row in rows} == {f"tool-{index}" for index in range(12)}

    # Separate MCP host processes have separate AuditLog/thread locks, so the same
    # split-write attack must also be serialized by the file lock.
    process_logs = tmp_path / "process-logs"
    context = multiprocessing.get_context("spawn")
    process_start = context.Barrier(8)
    processes = [context.Process(target=_record_split_in_process,
                                 args=(str(process_logs), index, process_start))
                 for index in range(8)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=3.0)

    assert all(process.exitcode == 0 for process in processes)
    process_path = next(process_logs.glob("server-*.jsonl"))
    process_rows = [json.loads(line) for line in process_path.read_text().splitlines()]
    assert {row["tool"] for row in process_rows} == {
        f"process-tool-{index}" for index in range(8)
    }
