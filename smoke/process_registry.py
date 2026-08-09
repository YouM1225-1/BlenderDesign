"""Private process-group records for bounded E2E cleanup."""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

MAX_RECORDS = 8
MAX_RECORD_BYTES = 4096
MARKER_RE = re.compile(r"[0-9a-f]{32}")
PUBLISH_TEMP_RE = re.compile(
    r"\.[A-Za-z0-9][A-Za-z0-9_.-]*\.json\.[1-9][0-9]*\.[0-9a-f]{8}\.tmp")
SENTINEL_MODE = "sentinel"
REPLACE_MODE = "replace"


@dataclass(frozen=True)
class ProcessRecord:
    path: Path
    pid: int
    pgid: int
    marker: str
    started_monotonic_ns: int
    device: int
    inode: int

    def evidence(self) -> dict[str, int | str]:
        return {
            "pid": self.pid,
            "pgid": self.pgid,
            "marker": self.marker,
            "started_monotonic_ns": self.started_monotonic_ns,
        }


def new_marker() -> str:
    return secrets.token_hex(16)


def reserve_publication(record_path: Path) -> tuple[Path, int, int]:
    require_private_directory(record_path.parent)
    try:
        record_path.lstat()
    except FileNotFoundError:
        pass
    else:
        raise FileExistsError(f"process record already exists: {record_path}")
    reservation = record_path.parent / (
        f".{record_path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    if PUBLISH_TEMP_RE.fullmatch(reservation.name) is None:
        raise ValueError(f"invalid process record name: {record_path.name}")
    descriptor = os.open(
        reservation, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    return reservation, opened.st_dev, opened.st_ino


def finish_publication_reservation(path: Path, device: int, inode: int) -> None:
    current = path.lstat()
    if (not stat.S_ISREG(current.st_mode) or current.st_uid != os.geteuid()
            or stat.S_IMODE(current.st_mode) != 0o600 or current.st_size != 0
            or (current.st_dev, current.st_ino) != (device, inode)):
        raise RuntimeError(f"process publication reservation changed: {path}")
    path.unlink()


def require_private_directory(path: Path) -> None:
    st = path.lstat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) != 0o700):
        raise PermissionError(f"private 0700 directory required: {path}")


def _validate_record_stat(st: os.stat_result, path: Path) -> None:
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) != 0o600
            or not 0 < st.st_size <= MAX_RECORD_BYTES):
        raise PermissionError(f"private bounded 0600 record required: {path}")


def _validate_temporary_stat(
    st: os.stat_result, path: Path, device: int, inode: int,
) -> None:
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or stat.S_IMODE(st.st_mode) != 0o600
            or (st.st_dev, st.st_ino) != (device, inode)):
        raise RuntimeError(f"private temporary identity changed: {path}")


def _unlink_private_temporary(path: Path, device: int, inode: int) -> None:
    try:
        before = path.lstat()
    except FileNotFoundError:
        return
    _validate_temporary_stat(before, path, device, inode)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(descriptor)
        _validate_temporary_stat(opened, path, device, inode)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"private temporary changed during open: {path}")
    finally:
        os.close(descriptor)
    current = path.lstat()
    _validate_temporary_stat(current, path, device, inode)
    path.unlink()


def _write_private_json(path: Path, value: object) -> None:
    require_private_directory(path.parent)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    fd: int | None = None
    identity: tuple[int, int] | None = None
    try:
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        opened = os.fstat(fd)
        identity = opened.st_dev, opened.st_ino
        os.fchmod(fd, 0o600)
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        if len(raw) > MAX_RECORD_BYTES:
            raise ValueError("process record is too large")
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short process-record write")
            view = view[written:]
        os.close(fd)
        fd = None
        os.replace(temporary, path)
    finally:
        if fd is not None:
            os.close(fd)
        if identity is not None:
            _unlink_private_temporary(temporary, *identity)


def publish_process(
    path: Path,
    marker: str,
    pid: int,
    pgid: int,
    *,
    started_monotonic_ns: int | None = None,
) -> ProcessRecord:
    if MARKER_RE.fullmatch(marker) is None:
        raise ValueError("process marker must be 32 lowercase hex characters")
    if pid <= 1 or pgid != pid:
        raise RuntimeError("record publisher is not its process-group leader")
    if os.getpgid(pid) != pgid:
        raise RuntimeError("recorded process is not the expected group leader")
    started = time.monotonic_ns() if started_monotonic_ns is None \
        else started_monotonic_ns
    _write_private_json(path, {
        "schema_version": 1,
        "pid": pid,
        "pgid": pgid,
        "marker": marker,
        "started_monotonic_ns": started,
    })
    return read_record(path, expected_marker=marker, not_before_ns=started)


def publish_current_process(path: Path, marker: str) -> ProcessRecord:
    return publish_process(path, marker, os.getpid(), os.getpgrp())


def read_record(
    path: Path,
    *,
    expected_marker: str | None = None,
    not_before_ns: int | None = None,
) -> ProcessRecord:
    require_private_directory(path.parent)
    before = path.lstat()
    _validate_record_stat(before, path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        _validate_record_stat(opened, path)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"process record changed during open: {path}")
        raw = os.read(fd, MAX_RECORD_BYTES + 1)
        if len(raw) != opened.st_size:
            raise ValueError(f"process record size changed during read: {path}")
    finally:
        os.close(fd)
    value = json.loads(raw)
    expected_keys = {
        "schema_version", "pid", "pgid", "marker", "started_monotonic_ns",
    }
    if type(value) is not dict or set(value) != expected_keys:
        raise ValueError(f"malformed process record keys: {path}")
    pid, pgid = value["pid"], value["pgid"]
    marker, started = value["marker"], value["started_monotonic_ns"]
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or type(pid) is not int
            or type(pgid) is not int or pid <= 1 or pgid != pid
            or type(marker) is not str or MARKER_RE.fullmatch(marker) is None
            or type(started) is not int or started <= 0
            or started > time.monotonic_ns()):
        raise ValueError(f"malformed process record values: {path}")
    if expected_marker is not None and marker != expected_marker:
        raise ValueError(f"process record marker differs: {path}")
    if not_before_ns is not None and started < not_before_ns:
        raise ValueError(f"stale process record: {path}")
    return ProcessRecord(
        path, pid, pgid, marker, started, opened.st_dev, opened.st_ino)


def group_id_is_live(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Darwin can report EPERM briefly for an exited group's unreaped member.
        return True
    return True


def signal_group_id(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


def poll_before_deadline(
    poll: Callable[[], int | None], deadline: float,
) -> tuple[int | None, bool]:
    expired = time.monotonic() >= deadline
    returncode = None if expired else poll()
    return returncode, expired or time.monotonic() >= deadline


def group_is_live(record: ProcessRecord) -> bool:
    try:
        current = os.getpgid(record.pid)
    except ProcessLookupError:
        # POSIX keeps the PGID allocated while any original member survives.
        return group_id_is_live(record.pgid)
    if current != record.pgid:
        raise RuntimeError(f"recorded PID was reused: {record.pid}")
    return group_id_is_live(record.pgid)


def current_record(record: ProcessRecord) -> ProcessRecord:
    current = read_record(
        record.path, expected_marker=record.marker,
        not_before_ns=record.started_monotonic_ns)
    if current != record:
        raise RuntimeError(f"process record identity changed: {record.path}")
    return current


def recorded_group_is_live(record: ProcessRecord) -> bool:
    return group_is_live(current_record(record))


def signal_live_records(records: Iterable[ProcessRecord], sig: int) -> None:
    unique = {record.pgid: record for record in records}
    first_error: Exception | None = None
    for record in sorted(unique.values(), key=lambda item: item.pgid):
        try:
            if recorded_group_is_live(record):
                # POSIX has no atomic record-validation + killpg operation.  A
                # same-UID swap after this final check remains indistinguishable.
                signal_group_id(record.pgid, sig)
        except Exception as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise first_error


def wait_owned_process_record(
    process: subprocess.Popen[bytes],
    path: Path,
    *,
    expected_marker: str,
    not_before_ns: int,
    deadline: float,
) -> ProcessRecord:
    while True:
        try:
            record = read_record(
                path, expected_marker=expected_marker,
                not_before_ns=not_before_ns)
        except FileNotFoundError:
            process.poll()
            if process.returncode is not None:
                raise RuntimeError(
                    f"owned process exited before publishing its record: {process.pid}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("owned process record publication timed out")
            time.sleep(min(0.01, remaining))
            continue
        if record.pid != process.pid:
            raise RuntimeError(
                f"owned process record PID differs: {record.pid} != {process.pid}")
        return record


def cleanup_owned_process(
    process: subprocess.Popen[bytes],
    record: ProcessRecord,
    *,
    deadline: float,
    term_grace: float,
) -> int:
    def live() -> bool:
        process.poll()
        return recorded_group_is_live(record)

    group_live = live()
    if group_live:
        signal_live_records([record], signal.SIGTERM)
    term_deadline = min(deadline, time.monotonic() + term_grace)
    while group_live and time.monotonic() < term_deadline:
        time.sleep(min(0.05, max(0.0, term_deadline - time.monotonic())))
        group_live = live()
    if group_live:
        signal_live_records([record], signal.SIGKILL)
    while group_live:
        group_live = live()
        if not group_live:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"owned process group survived cleanup: {record.pgid}")
        time.sleep(min(0.05, remaining))
    remaining = max(0.0, deadline - time.monotonic())
    try:
        return process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"owned process leader could not be reaped: {record.pid}") from exc


def _remember_known_record(
    known_records: dict[int, ProcessRecord], record: ProcessRecord,
) -> None:
    cached_same_group = known_records.get(record.pgid)
    if cached_same_group is not None and cached_same_group != record:
        raise RuntimeError(f"process record identity changed: {record.path}")
    first_error: Exception | None = None
    for pgid, cached in tuple(known_records.items()):
        if pgid == record.pgid:
            continue
        try:
            live = group_is_live(cached)
        except RuntimeError as exc:
            del known_records[pgid]
            if first_error is None:
                first_error = exc
        except Exception as exc:
            if first_error is None:
                first_error = exc
        else:
            if not live:
                del known_records[pgid]
    if record.pgid not in known_records and len(known_records) >= MAX_RECORDS:
        limit_error = RuntimeError("known process record limit exceeded")
        try:
            signal_live_records([record], signal.SIGKILL)
        except Exception as exc:
            if first_error is None:
                first_error = exc
        if first_error is None:
            first_error = limit_error
    else:
        known_records[record.pgid] = record
    if first_error is not None:
        raise first_error


def _unlink_record(record: ProcessRecord) -> None:
    current = record.path.lstat()
    _validate_record_stat(current, record.path)
    if (current.st_dev, current.st_ino) != (record.device, record.inode):
        raise RuntimeError(f"process record changed before unlink: {record.path}")
    record.path.unlink()


def retire_record(
    path: Path,
    *,
    expected_marker: str,
    not_before_ns: int | None = None,
) -> None:
    if not path.exists():
        raise FileNotFoundError(f"required process record missing: {path}")
    record = read_record(
        path, expected_marker=expected_marker, not_before_ns=not_before_ns)
    if group_is_live(record):
        raise RuntimeError(f"process group survived owner cleanup: {record.pgid}")
    _unlink_record(record)


def scan_records(
    directory: Path,
    *,
    expected_marker: str,
    not_before_ns: int,
    deadline: float | None = None,
    known_records: dict[int, ProcessRecord] | None = None,
    retire_dead: bool = True,
) -> tuple[list[ProcessRecord], bool]:
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("process registry scan deadline expired before start")
    require_private_directory(directory)
    records: list[ProcessRecord] = []
    publishing = False
    first_error: Exception | None = None
    with os.scandir(directory) as entries:
        for entry in entries:
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("process registry scan deadline expired")
            path = directory / entry.name
            if PUBLISH_TEMP_RE.fullmatch(entry.name) is not None:
                try:
                    temporary = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    publishing = True
                    continue
                if (not stat.S_ISREG(temporary.st_mode)
                        or temporary.st_uid != os.geteuid()
                        or stat.S_IMODE(temporary.st_mode) != 0o600
                        or not 0 <= temporary.st_size <= MAX_RECORD_BYTES):
                    if first_error is None:
                        first_error = PermissionError(
                            f"invalid process-record publication temporary: {path}")
                    continue
                publishing = True
                try:
                    pending = read_record(
                        path, expected_marker=expected_marker,
                        not_before_ns=not_before_ns)
                except Exception:
                    continue
                try:
                    pending_live = group_is_live(pending)
                except Exception as exc:
                    if first_error is None:
                        first_error = exc
                    continue
                if pending_live:
                    if known_records is None:
                        records.append(pending)
                    else:
                        try:
                            _remember_known_record(known_records, pending)
                        except Exception as exc:
                            if first_error is None:
                                first_error = exc
                        if known_records.get(pending.pgid) == pending:
                            records.append(pending)
                continue
            if not entry.name.endswith(".json"):
                if first_error is None:
                    first_error = ValueError(
                        f"unexpected process registry entry: {entry.name}")
                continue
            try:
                record = read_record(
                    path, expected_marker=expected_marker,
                    not_before_ns=not_before_ns)
            except FileNotFoundError:
                publishing = True
                continue
            except Exception as exc:
                if first_error is None:
                    first_error = exc
                continue
            try:
                record_live = group_is_live(record)
            except Exception as exc:
                if first_error is None:
                    first_error = exc
                continue
            if record_live:
                if known_records is None:
                    records.append(record)
                else:
                    try:
                        _remember_known_record(known_records, record)
                    except Exception as exc:
                        if first_error is None:
                            first_error = exc
                    if known_records.get(record.pgid) == record:
                        records.append(record)
            else:
                if retire_dead:
                    if deadline is not None and time.monotonic() >= deadline:
                        raise TimeoutError("process registry deadline expired before unlink")
                    try:
                        _unlink_record(record)
                    except FileNotFoundError:
                        publishing = True
                    except Exception as exc:
                        if first_error is None:
                            first_error = exc
                else:
                    publishing = True
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("process registry scan deadline expired before completion")
    if known_records is not None:
        current = {record.pgid: record for record in records}
        for pgid, record in tuple(known_records.items()):
            if pgid in current:
                continue
            try:
                live = group_is_live(record)
            except RuntimeError as exc:
                del known_records[pgid]
                if first_error is None:
                    first_error = exc
            except Exception as exc:
                if first_error is None:
                    first_error = exc
            else:
                if not live:
                    del known_records[pgid]
                elif not publishing:
                    current[pgid] = record
        if not publishing:
            known_records.clear()
            known_records.update(current)
            records = list(current.values())
    if first_error is not None:
        raise first_error
    return records, publishing


def live_records(
    directory: Path,
    *,
    expected_marker: str,
    not_before_ns: int,
    temporary_deadline: float | None = None,
    known_records: dict[int, ProcessRecord] | None = None,
) -> list[ProcessRecord]:
    while True:
        records, publishing = scan_records(
            directory, expected_marker=expected_marker,
            not_before_ns=not_before_ns, deadline=temporary_deadline,
            known_records=known_records)
        if not publishing:
            return records
        if temporary_deadline is None:
            raise RuntimeError("process-record publication is incomplete")
        remaining = temporary_deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("process-record publication exceeded cleanup deadline")
        time.sleep(min(0.01, remaining))


def cleanup_registry(
    directory: Path,
    *,
    expected_marker: str,
    not_before_ns: int,
    deadline: float,
    term_grace: float = 3.0,
    settle_grace: float = 0.5,
    known_records: dict[int, ProcessRecord] | None = None,
) -> None:
    settle_deadline = min(deadline, time.monotonic() + settle_grace)
    known = {} if known_records is None else known_records

    def final_kill_known() -> None:
        signal_live_records(known.values(), signal.SIGKILL)

    def refresh() -> list[ProcessRecord]:
        try:
            return live_records(
                directory, expected_marker=expected_marker,
                not_before_ns=not_before_ns, temporary_deadline=deadline,
                known_records=known)
        except Exception:
            final_kill_known()
            raise

    while time.monotonic() < settle_deadline:
        refresh()
        time.sleep(min(0.05, max(0.0, settle_deadline - time.monotonic())))
    records = refresh()
    if time.monotonic() >= deadline:
        final_kill_known()
        raise TimeoutError("process registry cleanup deadline expired before TERM")
    try:
        signal_live_records(records, signal.SIGTERM)
    except Exception:
        final_kill_known()
        raise
    term_deadline = min(deadline, time.monotonic() + term_grace)
    while time.monotonic() < term_deadline:
        if not refresh():
            return
        time.sleep(min(0.05, max(0.0, term_deadline - time.monotonic())))
    records = refresh()
    if time.monotonic() >= deadline:
        final_kill_known()
        raise TimeoutError("process registry cleanup deadline expired before KILL")
    signal_live_records(records, signal.SIGKILL)
    while time.monotonic() < deadline:
        if not refresh():
            return
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    remaining = refresh()
    if remaining:
        raise RuntimeError(
            f"unreaped process groups: {[record.pgid for record in remaining]}")


def _bootstrap(argv: list[str]) -> int:
    if len(argv) < 7 or argv[0] not in (SENTINEL_MODE, REPLACE_MODE):
        raise ValueError("recorded bootstrap command is malformed")
    mode = argv[0]
    record_path, reservation = Path(argv[1]), Path(argv[2])
    device, inode, marker = int(argv[3]), int(argv[4]), argv[5]
    command = argv[6:]
    publish_current_process(record_path, marker)
    finish_publication_reservation(reservation, device, inode)
    if mode == REPLACE_MODE:
        os.execvpe(command[0], command, os.environ)
        raise AssertionError("recorded exec unexpectedly returned")

    def relay(signum: int, _frame: object) -> None:
        signal.signal(signum, signal.SIG_DFL)
        os.killpg(os.getpgrp(), signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, relay)
    child = subprocess.Popen(command)
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(_bootstrap(sys.argv[1:]))
