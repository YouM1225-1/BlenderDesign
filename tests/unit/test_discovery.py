# tests/unit/test_discovery.py
import gc
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Literal, get_type_hints

import pytest
from bridge.core.lifecycle import BridgeSession
from protocol import envelope
from server.core.discovery import Discovery
from tests.unit.test_lifecycle import FakeReader


@pytest.fixture
def live(tmp_path):
    s = BridgeSession.start(tmp_path, FakeReader(), blender_version="5.2.0")
    threading.Thread(target=lambda: _pump(s), daemon=True).start()
    yield s, tmp_path / "run"
    s.stop()


def _pump(s):
    while not s.stopped:
        time.sleep(s.tick(50))


def _make_run(root: Path) -> Path:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    run = root / "run"
    run.mkdir(mode=0o700, exist_ok=True)
    run.chmod(0o700)
    return run


def _make_session_dir(run: Path, name: str) -> Path:
    directory = run / name
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def _write_private(path: Path, contents: str) -> None:
    try:
        data = json.loads(contents)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and data.get("socket_path") == "/nonexistent.sock":
        data["socket_path"] = str(path.parent / "bridge.sock")
    required = {"instance_id", "token", "pid", "socket_path",
                "blender_version", "bridge_version", "envelope_version"}
    if isinstance(data, dict) and required <= data.keys():
        socket_path = Path(data["socket_path"])
        data.setdefault("socket_external", socket_path.parent != path.parent)
        try:
            directory_stat = socket_path.parent.stat()
        except OSError:
            directory_stat = None
        try:
            socket_stat = socket_path.lstat()
        except OSError:
            socket_stat = None
        data.setdefault("socket_dev", 0 if socket_stat is None else socket_stat.st_dev)
        data.setdefault("socket_ino", 0 if socket_stat is None else socket_stat.st_ino)
        data.setdefault(
            "socket_dir_dev", 0 if directory_stat is None else directory_stat.st_dev)
        data.setdefault(
            "socket_dir_ino", 0 if directory_stat is None else directory_stat.st_ino)
        contents = json.dumps(data)
    path.write_text(contents)
    path.chmod(0o600)


def _reuse_fd_for_path(fd: int, path: Path) -> int:
    source_fd = os.open(path, os.O_RDONLY)
    if source_fd != fd:
        os.dup2(source_fd, fd)
        os.close(source_fd)
    return fd


def test_finds_live_instance(live):
    s, run = live
    d = Discovery(run)
    inst = d.instances()
    assert len(inst) == 1
    assert inst[0].state == "connected"
    assert inst[0].blender_supported is True
    assert inst[0].session["instance_id"] == s.instance_id


def test_cache_within_ttl(live):
    s, run = live
    d = Discovery(run, ttl=10.0)
    first = d.instances()
    s.stop()                                  # 会话没了……
    assert d.instances() is first             # ……但缓存内返回同一对象
    assert d.instances(force=True) == []      # force 绕过缓存


def test_created_runtime_root_chmod_is_identity_bound(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / "runtime"
    original = tmp_path / "runtime-original"
    real_chmod = disc_mod.os.chmod
    real_open = disc_mod.os.open
    swapped = False

    def swap_root():
        nonlocal swapped
        swapped = True
        root.rename(original)
        root.mkdir(mode=0o755)
        real_chmod(root, 0o755)

    def swapping_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if Path(path) == root and dir_fd is None and not swapped:
            swap_root()
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if Path(path) == root and dir_fd is None and not swapped:
            swap_root()
        return fd

    monkeypatch.setattr(disc_mod.os, "chmod", swapping_chmod)
    monkeypatch.setattr(disc_mod.os, "open", swapping_open)
    previous_umask = os.umask(0o777)
    try:
        with pytest.raises(PermissionError, match="private directory"):
            Discovery(root / "run")
    finally:
        os.umask(previous_umask)
    assert swapped is True
    assert (root.stat().st_mode & 0o777) == 0o755
    assert (original.stat().st_mode & 0o777) == 0o700


def test_created_run_chmod_is_identity_bound(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    run = root / "run"
    original = root / "run-original"
    real_chmod = disc_mod.os.chmod
    real_open = disc_mod.os.open
    swapped = False

    def swap_run():
        nonlocal swapped
        swapped = True
        run.rename(original)
        run.mkdir(mode=0o755)
        real_chmod(run, 0o755)

    def swapping_chmod(path, mode, *, dir_fd=None, follow_symlinks=True):
        if path == run.name and dir_fd is not None and not swapped:
            swap_run()
        return real_chmod(path, mode, dir_fd=dir_fd,
                          follow_symlinks=follow_symlinks)

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if path == run.name and dir_fd is not None and not swapped:
            swap_run()
        return fd

    monkeypatch.setattr(disc_mod.os, "chmod", swapping_chmod)
    monkeypatch.setattr(disc_mod.os, "open", swapping_open)
    previous_umask = os.umask(0o777)
    try:
        with pytest.raises(PermissionError, match="private directory"):
            Discovery(run)
    finally:
        os.umask(previous_umask)
    assert swapped is True
    assert (run.stat().st_mode & 0o777) == 0o755
    assert (original.stat().st_mode & 0o777) == 0o700


def test_rejects_preexisting_wide_run_without_chmod(tmp_path):
    tmp_path.chmod(0o700)
    run = tmp_path / "run"
    run.mkdir(mode=0o755)
    run.chmod(0o755)
    with pytest.raises(PermissionError, match="private directory"):
        Discovery(run)
    assert (run.stat().st_mode & 0o777) == 0o755


def test_rejects_run_directory_owned_by_other_uid(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    tmp_path.chmod(0o700)
    run = tmp_path / "run"
    run.mkdir(mode=0o700)
    run.chmod(0o700)
    real_stat = disc_mod.os.stat
    foreign_uid = os.geteuid() + 1

    def foreign_run_stat(name, *args, **kwargs):
        result = real_stat(name, *args, **kwargs)
        if name == run.name and kwargs.get("dir_fd") is not None:
            values = list(result)
            values[4] = foreign_uid
            return os.stat_result(values)
        return result

    monkeypatch.setattr(disc_mod.os, "stat", foreign_run_stat)
    with pytest.raises(PermissionError, match="private directory"):
        Discovery(run)
    assert real_stat(run).st_mode & 0o777 == 0o700


def test_replaced_run_path_is_not_scanned(tmp_path):
    run = _make_run(tmp_path)
    discovery = Discovery(run)
    original = tmp_path / "run-original"
    outside = tmp_path / "outside"
    run.rename(original)
    outside.mkdir(mode=0o700)
    outside.chmod(0o700)
    outside_run = _make_session_dir(outside, f"gui-{os.getpid()}-deadbeef")
    _write_private(outside_run / "session.json", json.dumps({
        "instance_id": outside_run.name, "token": "outside", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    run.symlink_to(outside, target_is_directory=True)
    assert discovery.instances(force=True) == []
    assert discovery.last_scan.reasons == ["run boundary"]


def test_scandir_error_is_reported_as_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    discovery = disc_mod.Discovery(_make_run(tmp_path))

    def fail_scandir(_fd):
        raise OSError("injected scandir failure")

    monkeypatch.setattr(disc_mod.os, "scandir", fail_scandir)
    assert discovery.instances(force=True) == []
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count == 1
    assert discovery.last_scan.reasons == ["enumeration error"]


def test_expired_scan_deadline_performs_no_run_io(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    discovery = disc_mod.Discovery(_make_run(tmp_path))

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("expired scan attempted run I/O")

    monkeypatch.setattr(disc_mod.os, "open", forbidden_open)
    instances, stats = discovery.instances_with_stats(
        force=True, deadline=time.monotonic() - 1.0)
    assert instances == []
    assert stats.partial is True
    assert stats.reasons == ["discovery lock deadline"]


@pytest.mark.parametrize("explicit_deadline", [False, True])
def test_discovery_lock_wait_respects_absolute_deadline(
        tmp_path, monkeypatch, explicit_deadline):
    import server.core.discovery as disc_mod

    monkeypatch.setattr(disc_mod, "SCAN_DEADLINE", 0.05)
    discovery = disc_mod.Discovery(_make_run(tmp_path))
    entered = threading.Event()
    release = threading.Event()

    def hold_lock():
        with discovery._lock:
            entered.set()
            assert release.wait(1.0)

    worker = threading.Thread(target=hold_lock)
    worker.start()
    assert entered.wait(1.0)
    started = time.monotonic()
    try:
        instances, stats = discovery.instances_with_stats(
            force=True, deadline=(started + 0.05 if explicit_deadline else None))
    finally:
        release.set()
        worker.join(timeout=1.0)
    assert time.monotonic() - started < 0.5
    assert instances == []
    assert stats.partial is True
    assert stats.reasons == ["discovery lock deadline"]


def test_invalidate_is_nonblocking_while_scan_lock_is_held(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    monkeypatch.setattr(disc_mod, "SCAN_DEADLINE", 0.05)
    discovery = disc_mod.Discovery(_make_run(tmp_path))
    discovery._cache = [object()]
    discovery._cached_at = discovery._clock()
    entered = threading.Event()
    release = threading.Event()

    def hold_lock():
        with discovery._lock:
            entered.set()
            assert release.wait(1.0)

    worker = threading.Thread(target=hold_lock)
    worker.start()
    assert entered.wait(1.0)
    started = time.monotonic()
    try:
        for _ in range(10_000):
            assert discovery.invalidate(deadline=started + 0.001) is True
        assert discovery._invalidations.qsize() == 1
    finally:
        release.set()
        worker.join(timeout=1.0)
    assert time.monotonic() - started < 0.05
    scans = 0

    def fresh_scan(deadline=None):
        nonlocal scans
        scans += 1
        discovery.last_scan = disc_mod.ScanStats()
        return []

    monkeypatch.setattr(discovery, "_scan", fresh_scan)
    assert discovery.instances() == []
    assert scans == 1
    assert discovery._cache == []


def test_invalidate_during_scan_does_not_publish_stale_cache(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    discovery = disc_mod.Discovery(_make_run(tmp_path))
    entered = threading.Event()
    release = threading.Event()
    sentinel = object()

    def slow_scan(deadline=None):
        entered.set()
        assert release.wait(1.0)
        discovery.last_scan = disc_mod.ScanStats()
        return [sentinel]

    monkeypatch.setattr(discovery, "_scan", slow_scan)
    worker = threading.Thread(target=lambda: discovery.instances(force=True))
    worker.start()
    assert entered.wait(1.0)
    assert discovery.invalidate(deadline=time.monotonic() + 0.001) is True
    release.set()
    worker.join(timeout=1.0)
    assert not worker.is_alive()
    assert discovery._cache is None

    scans = 0

    def fresh_scan(deadline=None):
        nonlocal scans
        scans += 1
        discovery.last_scan = disc_mod.ScanStats()
        return []

    monkeypatch.setattr(discovery, "_scan", fresh_scan)
    assert discovery.instances() == []
    assert scans == 1


@pytest.mark.parametrize("wide_target", ["directory", "file"])
def test_rejects_wide_session_artifacts(tmp_path, wide_target):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    session_file = directory / "session.json"
    _write_private(session_file, json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    (directory if wide_target == "directory" else session_file).chmod(
        0o755 if wide_target == "directory" else 0o644)
    assert Discovery(run).instances() == []
    assert directory.exists()


@pytest.mark.parametrize("name,pid", [
    ("gui-1-nothex00", 1),
    ("gui-1-deadbeef", 2),
    ("gui-0-deadbeef", 0),
])
def test_instance_id_embeds_exact_positive_pid(tmp_path, name, pid):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, name)
    _write_private(directory / "session.json", json.dumps({
        "instance_id": name, "token": "t", "pid": pid,
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    assert Discovery(run).instances() == []
    assert directory.exists()


def test_arbitrary_external_socket_path_is_never_probed(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(directory / "session.json", json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/tmp/unrelated-bcx.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    def forbidden_client(_session):
        raise AssertionError("arbitrary socket path reached BridgeClient")

    monkeypatch.setattr(disc_mod, "BridgeClient", forbidden_client)
    assert disc_mod.Discovery(run).instances() == []


def test_dead_pid_and_connect_fail_cleans_dir(tmp_path):
    run = _make_run(tmp_path)
    dead_pid = 2 ** 22 - 3
    dead = _make_session_dir(run, f"gui-{dead_pid}-deadbeef")
    _write_private(dead / "session.json", json.dumps({
        "instance_id": dead.name, "token": "t", "pid": dead_pid,  # 不存在的 pid
        "socket_path": str(dead / "bridge.sock"), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    assert Discovery(run).instances() == []
    assert not dead.exists()                  # 双条件成立 → 清理（§5.1）


@pytest.mark.parametrize("swap_stage", ["before_cleanup", "after_cleanup_validation"])
def test_internal_socket_replacement_during_stale_cleanup_is_preserved(
        monkeypatch, swap_stage):
    # 反例：A 通过 probe 后，清理窗口内换入同路径的 B；B 不得被误删。
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="bcx-") as root:
        run = _make_run(Path(root))
        dead_pid = 2 ** 22 - 3
        dead = _make_session_dir(run, f"gui-{dead_pid}-deadbeef")
        socket_path = dead / "bridge.sock"
        original = socket.socket(socket.AF_UNIX)
        original.bind(str(socket_path))
        socket_path.chmod(0o600)
        _write_private(dead / "session.json", json.dumps({
            "instance_id": dead.name, "token": "t", "pid": dead_pid,
            "socket_path": str(socket_path), "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
        replacement = socket.socket(socket.AF_UNIX)
        swapped = False

        def swap_socket():
            nonlocal swapped
            swapped = True
            original.close()
            socket_path.unlink()
            replacement.bind(str(socket_path))
            socket_path.chmod(0o600)

        if swap_stage == "before_cleanup":
            real_state = Discovery._socket_identity_state

            def swap_after_validation(session, deadline):
                state = real_state(session, deadline)
                if state == "ok" and not swapped:
                    swap_socket()
                return state

            monkeypatch.setattr(
                Discovery, "_socket_identity_state", staticmethod(swap_after_validation))
        else:
            real_cleanup = Discovery._remove_external_socket

            def swap_after_cleanup_validation(directory, session, deadline):
                complete = real_cleanup(directory, session, deadline)
                if complete and not swapped:
                    swap_socket()
                return complete

            monkeypatch.setattr(
                Discovery, "_remove_external_socket",
                staticmethod(swap_after_cleanup_validation))
        try:
            discovery = Discovery(run)
            assert discovery.instances(force=True) == []
            assert swapped is True
            assert socket_path.exists()
            assert discovery.last_scan.partial is True
            assert "cleanup incomplete" in discovery.last_scan.reasons
        finally:
            original.close()
            replacement.close()
            socket_path.unlink(missing_ok=True)


def test_corrupt_session_uses_monotonic_grace_and_restart_resets_it(
        tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    broken = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(broken / "session.json", "{corrupt")
    now = [0.0]
    monkeypatch.setattr(disc_mod.time, "time", lambda: 10 ** 12)
    Discovery(run, clock=lambda: now[0]).instances()
    assert broken.exists()  # wall-clock jump cannot authorize cleanup

    now[0] = 61.0
    restarted = Discovery(run, clock=lambda: now[0])
    restarted.instances()
    assert broken.exists()  # process restart conservatively restarts first-seen grace
    now[0] = 122.0
    restarted.instances(force=True)
    assert not broken.exists()


def test_deeply_nested_session_json_is_isolated(tmp_path):
    run = _make_run(tmp_path)
    broken = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    session_file = broken / "session.json"
    session_file.write_text('{"x":' + "[" * 10_000 + "0" + "]" * 10_000 + "}")
    session_file.chmod(0o600)

    assert Discovery(run).instances() == []
    assert broken.exists()  # fresh malformed metadata remains inside the grace period


def test_session_identity_replacement_restarts_monotonic_grace(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    now = [0.0]

    def write_mismatched(target):
        _write_private(target / "session.json", json.dumps({
            "instance_id": f"gui-{os.getpid()}-feedface",
            "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))

    write_mismatched(directory)
    discovery = Discovery(run, clock=lambda: now[0])
    assert discovery.instances() == []
    now[0] = 59.0
    directory.rename(run / "original-session")
    replacement = _make_session_dir(run, directory.name)
    write_mismatched(replacement)
    discovery.instances(force=True)
    now[0] = 61.0
    discovery.instances(force=True)
    assert replacement.exists()
    now[0] = 120.0
    discovery.instances(force=True)
    assert not replacement.exists()


def test_expired_cleanup_deadline_preserves_evidence(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(directory / "session.json", "{}")
    st = directory.stat(follow_symlinks=False)
    assert Discovery._remove_session_dir(
        directory, (st.st_dev, st.st_ino), time.monotonic() - 1.0) is False
    assert (directory / "session.json").exists()


def test_expired_cleanup_is_retried_by_a_later_scan(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    session_file = directory / "session.json"
    _write_private(session_file, "{}")
    identity = directory.stat().st_dev, directory.stat().st_ino
    assert Discovery._remove_session_dir(
        directory, identity, time.monotonic() - 1.0) is False
    assert session_file.exists()

    now = [0.0]
    discovery = Discovery(run, clock=lambda: now[0])
    assert discovery.instances(force=True) == []
    assert directory.exists()
    now[0] = 61.0
    assert discovery.instances(force=True) == []
    assert not directory.exists()


def test_cleanup_rechecks_deadline_after_child_stat(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    session_file = directory / "session.json"
    _write_private(session_file, "{}")
    identity = directory.stat().st_dev, directory.stat().st_ino
    real_stat = disc_mod.os.stat

    def slow_child_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if path == "session.json" and kwargs.get("dir_fd") is not None:
            time.sleep(0.08)
        return result

    monkeypatch.setattr(disc_mod.os, "stat", slow_child_stat)
    assert disc_mod.Discovery._remove_session_dir(
        directory, identity, time.monotonic() + 0.05) is False
    assert session_file.exists()


def test_cleanup_can_be_partial_and_preserves_unknown_children(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(directory / "session.json", "{}")
    (directory / "unknown.txt").write_text("preserve")
    st = directory.stat(follow_symlinks=False)
    assert Discovery._remove_session_dir(
        directory, (st.st_dev, st.st_ino), time.monotonic() + 1.0) is False
    assert not (directory / "session.json").exists()
    assert (directory / "unknown.txt").read_text() == "preserve"


def test_corrupt_session_incomplete_cleanup_is_reported_as_partial(tmp_path):
    run = _make_run(tmp_path)
    directory = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(directory / "session.json", "{}")
    (directory / "unknown.txt").write_text("preserve")
    now = [0.0]
    discovery = Discovery(run, clock=lambda: now[0])
    assert discovery.instances() == []
    now[0] = 61.0
    assert discovery.instances() == []
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count >= 1
    assert "cleanup incomplete" in discovery.last_scan.reasons
    assert (directory / "unknown.txt").read_text() == "preserve"


def test_external_cleanup_can_be_partial_with_unknown_child(tmp_path):
    instance_id = f"gui-{os.getpid()}-{tmp_path.stat().st_ino & 0xffffffff:08x}"
    session_dir = tmp_path / ("long-" * 30) / instance_id
    fallback = Discovery._fallback_dir(instance_id)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    unknown = fallback / "unknown.txt"
    unknown.write_text("preserve")
    directory_stat, socket_stat = fallback.stat(), socket_path.stat()
    session = {
        "socket_path": str(socket_path), "socket_external": True,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": directory_stat.st_dev,
        "socket_dir_ino": directory_stat.st_ino,
    }
    try:
        assert Discovery._remove_external_socket(
            session_dir, session, time.monotonic() + 1.0) is False
        assert not socket_path.exists()
        assert unknown.read_text() == "preserve"
        assert fallback.exists()
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)
        unknown.unlink(missing_ok=True)
        fallback.rmdir()


def test_crashed_fallback_session_cleans_external_socket(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / ("x" * 90)
    session = BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    socket_path = session.socket_path
    fallback = socket_path.parent
    session.stopped = True
    session._wake()
    session._join_io()
    session._close_all_conns()
    session._close_listener()
    monkeypatch.setattr(disc_mod.os, "kill",
                        lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()))

    assert Discovery(root / "run").instances() == []
    assert not session.session_dir.exists()
    assert not socket_path.exists()
    assert not fallback.exists()


def test_corrupt_cross_runtime_session_preserves_untrusted_fallback(
        tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / ("y" * 90)
    run = _make_run(root / "runtime-a")
    other_run = _make_run(root / "runtime-b")
    suffix = f"{tmp_path.stat().st_ino & 0xffffffff:08x}"
    directory = _make_session_dir(run, f"gui-99999999-{suffix}")
    other_directory = _make_session_dir(other_run, directory.name)
    fallback = Discovery._fallback_dir(directory.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    socket_path = fallback / "bridge.sock"
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(socket_path))
    sock.close()
    socket_path.chmod(0o600)
    now = [0.0]
    monkeypatch.setattr(disc_mod.time, "time", lambda: 10 ** 12)
    try:
        discovery = Discovery(run, clock=lambda: now[0])
        assert discovery.instances() == []
        assert directory.exists() and socket_path.exists() and fallback.exists()
        now[0] = 61.0
        assert discovery.instances(force=True) == []
        assert not directory.exists()
        assert other_directory.exists()
        assert socket_path.exists() and fallback.exists()
    finally:
        socket_path.unlink(missing_ok=True)
        if fallback.exists():
            fallback.rmdir()


def test_fallback_identity_mismatch_preserves_replacement_and_session(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    root = tmp_path / ("z" * 90)
    session = BridgeSession.start(root, FakeReader(), blender_version="5.2.0")
    fallback = session.socket_path.parent
    original = fallback.with_name(fallback.name + "-original")
    session.stopped = True
    session._wake()
    session._join_io()
    session._close_all_conns()
    session._close_listener()
    monkeypatch.setattr(disc_mod.os, "kill",
                        lambda _pid, _signal: (_ for _ in ()).throw(ProcessLookupError()))
    fallback.rename(original)
    fallback.mkdir(mode=0o700)
    replacement = socket.socket(socket.AF_UNIX)
    replacement.bind(str(fallback / "bridge.sock"))
    replacement.close()
    try:
        assert Discovery(root / "run").instances() == []
        assert session.session_dir.exists()
        assert (fallback / "bridge.sock").exists()
    finally:
        for directory in (fallback, original, session.session_dir):
            if directory.exists():
                for child in directory.iterdir():
                    child.unlink(missing_ok=True)
                directory.rmdir()


def test_version_warning_for_non_baseline(live, tmp_path):
    s, run = live
    sj = run / s.instance_id / "session.json"
    data = json.loads(sj.read_text())
    data["blender_version"] = "4.5.3"
    sj.write_text(json.dumps(data))
    inst = Discovery(run).instances()[0]
    assert inst.blender_supported is False
    assert "4.5.3" in inst.version_warning


def test_scan_respects_total_deadline_with_hanging_candidates(tmp_path, monkeypatch):
    # audit F-03：16 个挂起候选（listen 不 accept：连接成功但永无响应）。
    # 旧实现 8 并发 × 每探测 2s 分两批 → 实测 4.0s；总 deadline 后必须 < 3.2s
    import server.core.discovery as disc_mod

    executors = []
    real_executor = disc_mod.ThreadPoolExecutor

    class RecordingExecutor(real_executor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            executors.append(self)

    monkeypatch.setattr(disc_mod, "ThreadPoolExecutor", RecordingExecutor)
    run = _make_run(tmp_path)
    listeners: list[tuple[socket.socket, Path]] = []
    for i in range(16):
        d = _make_session_dir(run, f"gui-{os.getpid()}-{i:08x}")
        fallback = Discovery._fallback_dir(d.name)
        assert fallback is not None
        fallback.mkdir(mode=0o700)
        fallback.chmod(0o700)
        sock_path = fallback / "bridge.sock"
        hang = socket.socket(socket.AF_UNIX)
        hang.bind(str(sock_path))
        hang.listen(1)
        sock_path.chmod(0o600)
        dir_stat, socket_stat = fallback.stat(), sock_path.stat()
        listeners.append((hang, fallback))
        _write_private(d / "session.json", json.dumps({
            "instance_id": d.name, "token": "t", "pid": os.getpid(),
            "socket_path": str(sock_path), "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1,
            "socket_external": True,
            "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
            "socket_dir_dev": dir_stat.st_dev, "socket_dir_ino": dir_stat.st_ino,
        }))
    try:
        t0 = time.monotonic()
        insts = Discovery(run).instances()
        elapsed = time.monotonic() - t0
        assert elapsed < 3.2
        assert len(insts) == 16
        assert all(i.state == "disconnected" for i in insts)
        assert all((run / i.session["instance_id"]).exists() for i in insts)  # 绝不误删
        assert executors and all(
            not thread.is_alive() for executor in executors for thread in executor._threads)
    finally:
        for hang, fallback in listeners:
            hang.close()
            (fallback / "bridge.sock").unlink(missing_ok=True)
            fallback.rmdir()


def test_completed_probe_deadline_is_reported_as_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(directory / "session.json", json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    def deadline(*_args, **_kwargs):
        raise disc_mod._ProbeDeadline

    monkeypatch.setattr(disc_mod.Discovery, "_probe", deadline)
    discovery = disc_mod.Discovery(run)
    instances = discovery.instances()
    assert len(instances) == 1 and instances[0].state == "disconnected"
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count == 1
    assert discovery.last_scan.reasons == ["probe deadline"]


def test_probe_rechecks_deadline_between_socket_metadata_reads(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    directory = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    socket_path = directory / "bridge.sock"
    socket_path.touch()
    socket_path.chmod(0o600)
    directory_stat, socket_stat = directory.stat(), socket_path.stat()
    session = {
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1,
        "socket_external": False,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": directory_stat.st_dev,
        "socket_dir_ino": directory_stat.st_ino,
    }
    discovery = disc_mod.Discovery(run)
    now = [0.0]
    calls = []
    real_lstat = Path.lstat

    def advancing_lstat(path):
        calls.append(path)
        result = real_lstat(path)
        now[0] = 2.0
        return result

    monkeypatch.setattr(disc_mod.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(Path, "lstat", advancing_lstat)
    with pytest.raises(disc_mod._ProbeDeadline):
        discovery._probe(session, deadline=1.0)
    assert calls == [directory]


def test_scan_phase_itself_is_inside_deadline(tmp_path, monkeypatch):
    # 真正攻击 scandir.__next__：旧 sorted(iterdir()) 会先物化 400 项（约 4s），
    # 新实现每次 next 前检查绝对 deadline，约 2.5s 止损。
    import server.core.discovery as disc_mod
    run = _make_run(tmp_path)
    for i in range(400):
        d = _make_session_dir(run, f"gui-{os.getpid()}-{i:08x}")
        _write_private(d / "session.json", json.dumps({
            "instance_id": d.name, "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
    real_scandir = os.scandir

    class SlowScandir:
        def __init__(self, path):
            self._inner = real_scandir(path)

        def __next__(self):
            time.sleep(0.010)
            return next(self._inner)

        def close(self):
            self._inner.close()

    monkeypatch.setattr(disc_mod.os, "scandir", SlowScandir)
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1000)
    t0 = time.monotonic()
    d = Discovery(run)
    d.instances()
    elapsed = time.monotonic() - t0
    assert elapsed < 3.2, f"扫描阶段逃逸预算：{elapsed:.3f}s"
    assert d.last_scan.partial and d.last_scan.skipped_count > 0


def test_oversized_session_file_skipped(tmp_path):
    run = _make_run(tmp_path)
    d = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(d / "session.json", "x" * (65 * 1024))
    assert Discovery(run).instances() == []


def test_fifo_session_file_never_blocks(tmp_path):
    run = _make_run(tmp_path)
    d = _make_session_dir(run, "gui-1-deadbeef")
    os.mkfifo(d / "session.json")
    t0 = time.monotonic()
    assert Discovery(run).instances() == []
    assert time.monotonic() - t0 < 0.5


def test_session_read_is_bound_to_opened_fd(tmp_path, monkeypatch):
    # open 后把路径换成 FIFO；实现必须继续读已打开的常规文件 fd，不能重新按路径打开。
    import server.core.discovery as disc_mod
    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    sj = d / "session.json"
    _write_private(sj, json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    real_open = os.open
    swapped = False

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if path == "session.json" and dir_fd is not None and not swapped:
            swapped = True
            os.replace(sj, d / "session.original")
            os.mkfifo(sj)
        return fd

    monkeypatch.setattr(disc_mod.os, "open", swapping_open)
    inst = Discovery(run).instances()
    assert swapped and len(inst) == 1 and inst[0].session["instance_id"] == d.name


def test_session_read_replacement_marks_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(d / "session.json", json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))
    real_read = os.read
    swapped = False

    def replace_before_read(fd, size):
        nonlocal swapped
        if not swapped:
            swapped = True
            d.rename(run / "old-session")
            d.mkdir(mode=0o700)
            d.chmod(0o700)
            raise ValueError("injected session read failure")
        return real_read(fd, size)

    monkeypatch.setattr(disc_mod.os, "read", replace_before_read)
    discovery = disc_mod.Discovery(run)
    assert discovery.instances(force=True) == []
    assert swapped
    assert discovery.last_scan.partial is True
    assert "session identity replaced" in discovery.last_scan.reasons


def test_parent_directory_swap_cannot_redirect_session_read(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    inside = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    outside.chmod(0o700)
    for directory, token in ((inside, "inside"), (outside, "outside")):
        _write_private(directory / "session.json", json.dumps({
            "instance_id": inside.name, "token": token, "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))

    real_open = os.open
    swapped = False

    def swap_after_dir_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if Path(path) == inside and dir_fd is None and not swapped:
            swapped = True
            inside.rename(run / "original-dir")
            os.symlink(outside, inside)
        return fd

    monkeypatch.setattr(disc_mod.os, "open", swap_after_dir_open)
    instances = disc_mod.Discovery(run).instances()

    assert swapped
    assert [item.session["token"] for item in instances] == ["inside"]


def test_dead_probe_cleanup_does_not_delete_replacement_directory(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    original = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    _write_private(original / "session.json", json.dumps({
        "instance_id": original.name, "token": "t", "pid": os.getpid(),
        "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    def replace_then_report_dead(self, session, deadline):
        original.rename(run / "old-directory")
        original.mkdir()
        (original / "replacement.txt").write_text("must survive")
        return None

    monkeypatch.setattr(disc_mod.Discovery, "_probe", replace_then_report_dead)
    discovery = disc_mod.Discovery(run)
    assert discovery.instances() == []
    assert discovery.last_scan.partial is True
    assert discovery.last_scan.skipped_count >= 1
    assert "cleanup incomplete" in discovery.last_scan.reasons
    assert (original / "replacement.txt").read_text() == "must survive"


def test_valid_json_with_missing_session_fields_isolated(tmp_path):
    run = _make_run(tmp_path)
    d = _make_session_dir(run, "gui-1-deadbeef")
    _write_private(d / "session.json", "{}")
    assert Discovery(run).instances() == []


def test_invalid_socket_identity_is_preserved_before_probe(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    def forbidden_client(_session):
        raise AssertionError("invalid socket identity reached BridgeClient")

    monkeypatch.setattr(disc_mod, "BridgeClient", forbidden_client)
    for index, identity_fields in enumerate(({}, {"socket_dev": 1})):
        directory = _make_session_dir(run, f"gui-{os.getpid()}-{index:08x}")
        session_file = directory / "session.json"
        session_file.write_text(json.dumps({
            "instance_id": directory.name, "token": "t", "pid": os.getpid(),
            "socket_path": str(directory / "bridge.sock"),
            "blender_version": "5.2.0", "bridge_version": "0.1.0",
            "envelope_version": 1, "socket_external": False,
            **identity_fields,
        }))
        session_file.chmod(0o600)
        instances, stats = disc_mod.Discovery(run).instances_with_stats()
        assert instances == []
        assert stats.partial is True
        assert stats.reasons == ["socket identity invalid"]
        assert directory.exists() and session_file.exists()


def test_runtime_socket_identity_mismatch_is_partial_and_preserved(tmp_path):
    run = _make_run(tmp_path)
    suffix = f"{tmp_path.stat().st_ino & 0xffffffff:08x}"
    directory = _make_session_dir(run, f"gui-{os.getpid()}-{suffix}")
    fallback = Discovery._fallback_dir(directory.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    directory_stat, socket_stat = fallback.stat(), socket_path.lstat()
    session_file = directory / "session.json"
    _write_private(session_file, json.dumps({
        "instance_id": directory.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1,
        "socket_external": True,
        "socket_dev": socket_stat.st_dev, "socket_ino": socket_stat.st_ino,
        "socket_dir_dev": directory_stat.st_dev,
        "socket_dir_ino": directory_stat.st_ino,
    }))
    listener.close()
    socket_path.unlink()
    replacement = socket.socket(socket.AF_UNIX)
    replacement.bind(str(socket_path))
    socket_path.chmod(0o600)
    try:
        instances, stats = Discovery(run).instances_with_stats(force=True)
        assert instances == []
        assert stats.partial is True and stats.skipped_count == 1
        assert stats.reasons == ["identity mismatch"]
        assert directory.exists() and session_file.exists() and socket_path.exists()
    finally:
        replacement.close()
        socket_path.unlink(missing_ok=True)
        fallback.rmdir()


def test_busy_probe_is_reported_without_cleanup(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod
    from server.core.bridge_client import BridgeError

    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    fallback = disc_mod.Discovery._fallback_dir(d.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    _write_private(d / "session.json", json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    seen_deadlines = []

    class BusyClient:
        def __init__(self, session):
            pass

        def call(self, method, params=None, timeout=None, *, deadline=None):
            seen_deadlines.append(deadline)
            raise BridgeError("BRIDGE_BUSY", "queue full", retryable=True)

    def dead_pid(_pid, _signal):
        raise ProcessLookupError

    monkeypatch.setattr(disc_mod, "BridgeClient", BusyClient)
    monkeypatch.setattr(disc_mod.os, "kill", dead_pid)
    try:
        requested_deadline = time.monotonic() + 1.0
        inst = Discovery(run).instances(deadline=requested_deadline)
        assert len(inst) == 1 and inst[0].state == "busy" and inst[0].client is not None
        assert seen_deadlines == [requested_deadline]
        assert get_type_hints(disc_mod.Instance)["state"] == Literal[
            "connected", "disconnected", "busy"]
        assert d.exists()
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)
        fallback.rmdir()


@pytest.mark.parametrize("response_kind", ["bool_version", "instance_mismatch"])
def test_ping_identity_and_envelope_version_are_authoritative(
        tmp_path, monkeypatch, response_kind):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    d = _make_session_dir(run, f"gui-{os.getpid()}-deadbeef")
    fallback = disc_mod.Discovery._fallback_dir(d.name)
    assert fallback is not None
    fallback.mkdir(mode=0o700)
    fallback.chmod(0o700)
    socket_path = fallback / "bridge.sock"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    _write_private(d / "session.json", json.dumps({
        "instance_id": d.name, "token": "t", "pid": os.getpid(),
        "socket_path": str(socket_path), "blender_version": "5.2.0",
        "bridge_version": "0.1.0", "envelope_version": 1}))

    class PingClient:
        def __init__(self, session):
            self._session = session

        def call(self, method, params=None, timeout=None, *, deadline=None):
            return {
                "instance_id": ("gui-1-feedface" if response_kind == "instance_mismatch"
                                else self._session["instance_id"]),
                "envelope_version": (True if response_kind == "bool_version"
                                     else envelope.ENVELOPE_VERSION),
            }

    monkeypatch.setattr(disc_mod, "BridgeClient", PingClient)
    try:
        discovery = disc_mod.Discovery(run)
        instances = discovery.instances()
        if response_kind == "bool_version":
            assert len(instances) == 1
            assert instances[0].envelope_mismatch is True
            assert instances[0].state == "disconnected"
        else:
            assert instances == []
            assert d.exists() and socket_path.exists()
            assert discovery.last_scan.partial is True
            assert discovery.last_scan.reasons == ["identity mismatch"]
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)
        fallback.rmdir()


def test_enumeration_windows_eventually_reach_later_live_instance(live, monkeypatch):
    import server.core.discovery as disc_mod
    s, run = live
    for suffix in ("00000000", "00000001"):
        name = f"gui-1-{suffix}"
        d = _make_session_dir(run, name)
        _write_private(d / "session.json", json.dumps({
            "instance_id": name, "token": "t", "pid": 1,
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
    real_scandir = os.scandir

    class OrderedScandir:
        def __init__(self, path):
            self._inner = real_scandir(path)
            self._entries = iter(sorted(list(self._inner), key=lambda e: e.name))
            self.next_calls = 0

        def __next__(self):
            self.next_calls += 1
            return next(self._entries)

        def close(self):
            self._inner.close()

    monkeypatch.setattr(disc_mod.os, "scandir", OrderedScandir)
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 2)
    d = Discovery(run)
    first = d.instances(force=True)
    assert d._scan_iter.next_calls <= 2
    assert d.last_scan.partial and d.last_scan.skipped_count >= 1
    assert all(i.session["instance_id"] != s.instance_id for i in first)
    second = d.instances(force=True)
    assert any(i.session["instance_id"] == s.instance_id and i.state == "connected"
               for i in second)


def test_abandoned_partial_enumeration_closes_run_fd(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    _make_session_dir(run, "gui-1-00000000")
    _make_session_dir(run, "gui-1-00000001")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)

    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    assert discovery._scan_iter is not None
    scan_fd = discovery._scan_fd
    assert scan_fd is not None

    del discovery
    gc.collect()
    with pytest.raises(OSError):
        os.fstat(scan_fd)


def test_replaced_run_during_preflight_discards_cursor(
        tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    for suffix in ("00000000", "00000001", "00000002"):
        _make_session_dir(run, f"gui-1-{suffix}")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 2)
    monkeypatch.setattr(disc_mod, "MAX_CANDIDATES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    assert discovery._scan_iter is not None
    assert discovery._candidate_backlog
    scan_fd = discovery._scan_fd
    assert scan_fd is not None

    original_open = disc_mod.Discovery._open_run_dir
    swapped = False

    def swap_during_preflight(self, deadline=None):
        nonlocal swapped
        fd = original_open(self, deadline)
        if not swapped:
            swapped = True
            run.rename(tmp_path / "run-original")
            run.mkdir(mode=0o700)
            run.chmod(0o700)
            _make_session_dir(run, "gui-1-feedface")
        return fd

    # The hook fires after the preflight open, before cursor validation.  It
    # does not claim to cover a race after the final identity check; that
    # same-identity POSIX TOCTOU boundary is documented in the implementation.
    monkeypatch.setattr(disc_mod.Discovery, "_open_run_dir", swap_during_preflight)
    assert discovery.instances(force=True) == []
    assert swapped
    assert discovery.last_scan.partial is True
    assert "run cursor replaced" in discovery.last_scan.reasons
    assert discovery._scan_iter is None
    assert discovery._candidate_backlog == []
    with pytest.raises(OSError):
        os.fstat(scan_fd)  # the still-owned original cursor fd was not leaked


def test_closed_scan_cursor_is_dropped(
        tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    for suffix in ("00000000", "00000001", "00000002"):
        _make_session_dir(run, f"gui-1-{suffix}")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 2)
    monkeypatch.setattr(disc_mod, "MAX_CANDIDATES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    assert discovery._candidate_backlog
    scan_fd = discovery._scan_fd
    assert scan_fd is not None
    os.close(scan_fd)  # simulate an externally closed/reused descriptor
    assert discovery.instances(force=True) == []
    assert discovery.last_scan.partial is True
    assert "run cursor closed" in discovery.last_scan.reasons
    assert discovery._scan_fd is None and discovery._scan_iter is None
    assert discovery._candidate_backlog == []


def test_identity_different_reused_scan_fd_is_not_closed(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    for suffix in ("00000000", "00000001", "00000002"):
        _make_session_dir(run, f"gui-1-{suffix}")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 2)
    monkeypatch.setattr(disc_mod, "MAX_CANDIDATES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    assert discovery._candidate_backlog
    scan_fd = discovery._scan_fd
    assert scan_fd is not None

    os.close(scan_fd)
    unrelated_path = tmp_path / "unrelated"
    unrelated_path.write_bytes(b"owned elsewhere")
    unrelated_fd = _reuse_fd_for_path(scan_fd, unrelated_path)
    try:
        assert discovery.instances(force=True) == []
        assert discovery.last_scan.partial is True
        assert "run cursor replaced" in discovery.last_scan.reasons
        assert discovery._candidate_backlog == []
        assert os.read(unrelated_fd, 5) == b"owned"  # no collateral close
    finally:
        os.close(unrelated_fd)


def test_cursor_cleanup_deadline_does_not_close_reused_foreign_fd(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    _make_session_dir(run, "gui-1-00000000")
    _make_session_dir(run, "gui-1-00000001")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    scan_fd = discovery._scan_fd
    assert scan_fd is not None
    os.close(scan_fd)
    unrelated_path = tmp_path / "unrelated-deadline"
    unrelated_path.write_bytes(b"foreign")
    unrelated_fd = _reuse_fd_for_path(scan_fd, unrelated_path)
    try:
        stats = disc_mod.ScanStats()
        assert discovery._validate_scan_cursor(time.monotonic() - 1.0, stats) is False
        assert os.read(unrelated_fd, 7) == b"foreign"
    finally:
        os.close(unrelated_fd)


def test_discovery_destructor_does_not_close_reused_foreign_fd(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod

    run = _make_run(tmp_path)
    _make_session_dir(run, "gui-1-00000000")
    _make_session_dir(run, "gui-1-00000001")
    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 1)
    discovery = disc_mod.Discovery(run)
    discovery.instances(force=True)
    scan_fd = discovery._scan_fd
    assert scan_fd is not None
    os.close(scan_fd)
    unrelated_path = tmp_path / "unrelated-destructor"
    unrelated_path.write_bytes(b"foreign")
    unrelated_fd = _reuse_fd_for_path(scan_fd, unrelated_path)
    del discovery
    gc.collect()
    try:
        assert os.read(unrelated_fd, 7) == b"foreign"
    finally:
        os.close(unrelated_fd)


def test_candidate_backlog_eventually_reaches_older_live_instance(live):
    # 同一枚举窗口里，16 个较新但 pid 存活的断连实例不得永久饿死第 17 个活实例。
    s, run = live
    live_dir = run / s.instance_id
    os.utime(live_dir, (1, 1))
    for i in range(16):
        name = f"gui-{os.getpid()}-{i:08x}"
        d = _make_session_dir(run, name)
        _write_private(d / "session.json", json.dumps({
            "instance_id": name, "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))
        os.utime(d, (100 + i, 100 + i))

    discovery = Discovery(run)
    first = discovery.instances(force=True)
    assert len(first) == 16
    assert all(i.session["instance_id"] != s.instance_id for i in first)
    assert discovery.last_scan.partial and discovery.last_scan.skipped_count >= 1

    second = discovery.instances(force=True)
    assert any(i.session["instance_id"] == s.instance_id and i.state == "connected"
               for i in second)


def test_backlog_reports_unenumerated_tail_as_partial(tmp_path, monkeypatch):
    import server.core.discovery as disc_mod
    run = _make_run(tmp_path)
    for i in range(18):
        d = _make_session_dir(run, f"gui-{os.getpid()}-{i:08x}")
        _write_private(d / "session.json", json.dumps({
            "instance_id": d.name, "token": "t", "pid": os.getpid(),
            "socket_path": "/nonexistent.sock", "blender_version": "5.2.0",
            "bridge_version": "0.1.0", "envelope_version": 1}))

    monkeypatch.setattr(disc_mod, "MAX_SCAN_ENTRIES", 17)
    discovery = Discovery(run)
    discovery.instances(force=True)  # 16 probed, 1 in backlog, >=1 not enumerated
    assert discovery.last_scan.partial
    discovery.instances(force=True)  # backlog <= candidate cap; unenumerated tail remains
    assert discovery.last_scan.partial and discovery.last_scan.skipped_count >= 1
