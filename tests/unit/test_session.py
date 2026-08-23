import json
import os
import stat

import pytest

from bridge.core.session import SessionAuth, write_session_file


def test_generate_token_length_and_uniqueness():
    a, b = SessionAuth.generate(), SessionAuth.generate()
    assert a != b and len(a) >= 43


def test_verify_accepts_only_exact_string():
    auth = SessionAuth("secret-token")
    assert auth.verify("secret-token") is True
    assert auth.verify("secret-tokeN") is False
    assert auth.verify(None) is False
    assert auth.verify(123) is False
    assert auth.verify(chr(0xD800)) is False


def test_write_session_file_is_0600_and_atomic(tmp_path):
    p = tmp_path / "session.json"
    write_session_file(p, {"a": 1})
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert json.loads(p.read_text()) == {"a": 1}
    write_session_file(p, {"a": 2})
    assert json.loads(p.read_text()) == {"a": 2}
    assert list(tmp_path.iterdir()) == [p]


def test_write_session_file_dir_fd_ignores_restrictive_umask(tmp_path):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    previous_umask = os.umask(0o777)
    try:
        write_session_file(tmp_path / "session.json", {"a": 1}, dir_fd=directory_fd)
    finally:
        os.umask(previous_umask)
        os.close(directory_fd)
    path = tmp_path / "session.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {"a": 1}


def test_replace_failure_removes_temporary_file(tmp_path, monkeypatch):
    import bridge.core.session as session_module

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(session_module.os, "replace", fail_replace)
    path = tmp_path / "session.json"
    with pytest.raises(OSError, match="replace failed"):
        write_session_file(path, {"a": 1})
    assert list(tmp_path.iterdir()) == []


def test_fchmod_failure_closes_file_descriptor(tmp_path, monkeypatch):
    import bridge.core.session as session_module

    def fail_fchmod(_fd, _mode):
        raise OSError("fchmod failed")

    monkeypatch.setattr(session_module.os, "fchmod", fail_fchmod)
    path = tmp_path / "session.json"
    baseline = len(os.listdir("/dev/fd"))

    for _ in range(40):
        with pytest.raises(OSError, match="fchmod failed"):
            write_session_file(path, {"a": 1})

    def fail_fdopen(*_args, **_kwargs):
        raise OSError("fdopen failed")

    monkeypatch.setattr(session_module.os, "fchmod", lambda _fd, _mode: None)
    monkeypatch.setattr(session_module.os, "fdopen", fail_fdopen)
    with pytest.raises(OSError, match="fdopen failed"):
        write_session_file(path, {"a": 1})

    assert len(os.listdir("/dev/fd")) == baseline
    assert list(tmp_path.iterdir()) == []


def test_preexisting_temporary_file_is_preserved(tmp_path, monkeypatch):
    import bridge.core.session as session_module

    path = tmp_path / "session.json"
    temporary = tmp_path / "session.json.tmp"
    temporary.write_text("foreign")
    with pytest.raises(FileExistsError):
        write_session_file(path, {"a": 1})
    assert temporary.read_text() == "foreign"
    assert not path.exists()

    temporary.unlink()

    def replace_temp_then_fail(_fd, _mode):
        temporary.unlink()
        temporary.write_text("replacement")
        raise OSError("fchmod failed")

    monkeypatch.setattr(session_module.os, "fchmod", replace_temp_then_fail)
    with pytest.raises(OSError, match="fchmod failed"):
        write_session_file(path, {"a": 1})
    assert temporary.read_text() == "replacement"
