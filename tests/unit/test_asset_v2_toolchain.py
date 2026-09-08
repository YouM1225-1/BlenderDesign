from __future__ import annotations

import datetime
import errno
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from acceptance import primitives
from acceptance.primitives import (
    AcceptanceFailure,
    clean_environment,
    group_exists,
    run_command,
)
from acceptance.toolchain import measure_tool, provenance, verify_tools
from tests.unit.asset_v2_support import REPO, file_lock, valid_document, write_contract


def _limits(**overrides: int) -> dict[str, int]:
    values = {
        "cpu_seconds": 2,
        "rss_bytes": 2 * 1024**3,
        "open_files": 64,
        "log_bytes": 8192,
        "file_size_bytes": 1024 * 1024,
    }
    values.update(overrides)
    return values


def _run(tmp_path: Path, program: str, **kwargs: object) -> int:
    timeout = kwargs.pop("timeout", 3.0)
    return run_command(
        "probe",
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env=clean_environment(Path(sys.executable)),
        log_path=tmp_path / "log",
        timeout=timeout,
        **kwargs,
    )


def test_full_tool_lock_and_shared_code_closure(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    measured = verify_tools(contract, ("acceptance", "python", "blender"), REPO)
    assert {m["id"] for m in measured} == {"acceptance", "python", "blender"}
    assert "smoke/process_registry.py" in {r["path"] for r in provenance(REPO)["files"]}


def test_python_cannot_impersonate_blender_even_when_hash_is_accurate(tmp_path):
    tool = valid_document(tmp_path)["tools"][2]
    tool["path"] = str(Path(sys.executable).resolve())
    tool["sha256"] = file_lock(Path(sys.executable))["sha256"]
    with pytest.raises(AcceptanceFailure, match="kind or supported version"):
        measure_tool(tool, REPO)


def test_dependency_replacement_is_not_hidden_by_same_executable(tmp_path):
    value = valid_document(tmp_path)
    script = tmp_path / "worker.py"
    script.write_text("print('first')\n")
    value["tools"][0]["files"].append(file_lock(script))
    script.write_text("print('second')\n")
    with pytest.raises(AcceptanceFailure, match="dependency"):
        measure_tool(value["tools"][0], REPO)


@pytest.mark.parametrize("code", ["tool_crashed", "evidence_truncated"])
def test_version_probe_preserves_controller_accident_family(tmp_path, monkeypatch, code):
    tool = valid_document(tmp_path)["tools"][0]

    def fail(*_args, **_kwargs):
        raise AcceptanceFailure(code, "version probe accident")

    monkeypatch.setattr("acceptance.toolchain.run_command", fail)
    with pytest.raises(AcceptanceFailure) as caught:
        measure_tool(tool, REPO)
    assert caught.value.code == code


def test_process_installs_declared_kernel_limits(tmp_path):
    program = """
import json, resource
print(json.dumps([
    resource.getrlimit(resource.RLIMIT_CPU),
    resource.getrlimit(resource.RLIMIT_NOFILE),
    resource.getrlimit(resource.RLIMIT_FSIZE),
]))
"""
    assert _run(tmp_path, program, limits=_limits()) == 0
    assert json.loads((tmp_path / "log").read_text()) == [[2, 2], [64, 64], [1048576, 1048576]]


def test_open_file_limit_is_enforced_in_child(tmp_path):
    program = f"""
import errno, os, sys
opened = []
try:
    while True:
        opened.append(open('/dev/null', 'rb'))
except OSError as exc:
    sys.exit(0 if exc.errno == {errno.EMFILE} else 2)
"""
    assert _run(tmp_path, program, limits=_limits(open_files=32)) == 0


def test_cpu_limit_terminates_busy_child_before_wall_timeout(tmp_path):
    started = time.monotonic()
    returncode = _run(
        tmp_path,
        "while True: pass",
        timeout=5.0,
        limits=_limits(cpu_seconds=1),
    )
    assert returncode != 0
    assert time.monotonic() - started < 4.0


def test_normal_rss_is_sampled_and_observed(tmp_path):
    observation = {}
    assert _run(
        tmp_path,
        "import time; time.sleep(0.25)",
        limits=_limits(),
        observation=observation,
    ) == 0
    assert observation["started"] is True
    assert isinstance(observation["pid"], int) and observation["pid"] > 0
    datetime.datetime.fromisoformat(observation["started_at"])
    assert observation["exit_code"] == 0
    sampling = observation["memory_sampling"]
    assert sampling["samples"] >= 1
    assert sampling["peak_observed_rss_bytes"] > 0
    assert not group_exists(observation["pid"])


def test_sampled_rss_excess_terminates_process_group(tmp_path):
    observation = {}
    with pytest.raises(AcceptanceFailure) as caught:
        _run(
            tmp_path,
            "import time; time.sleep(3)",
            limits=_limits(rss_bytes=1),
            observation=observation,
        )
    assert caught.value.code == "resource_limit_exceeded"
    assert observation["memory_sampling"]["samples"] >= 1
    assert observation["memory_sampling"]["peak_observed_rss_bytes"] > 1
    assert observation["exit_code"] is not None
    assert not group_exists(observation["pid"])


def test_default_file_limit_caps_log_and_classifies_truncation(tmp_path):
    with pytest.raises(AcceptanceFailure) as caught:
        _run(
            tmp_path,
            "import os; os.write(1, b'x' * 65536)",
            max_log_bytes=1024,
        )
    assert caught.value.code == "evidence_truncated"
    assert (tmp_path / "log").stat().st_size <= 1024


def test_separate_log_budget_still_classifies_truncation(tmp_path):
    with pytest.raises(AcceptanceFailure) as caught:
        _run(
            tmp_path,
            "import os; os.write(1, b'x' * 65536)",
            max_log_bytes=1024,
            limits=_limits(file_size_bytes=1024 * 1024),
        )
    assert caught.value.code == "evidence_truncated"


def test_wall_timeout_cleans_group_and_finishes_observation(tmp_path):
    observation = {}
    started = time.monotonic()
    with pytest.raises(AcceptanceFailure) as caught:
        _run(
            tmp_path,
            "import time; time.sleep(3)",
            timeout=0.1,
            limits=_limits(),
            observation=observation,
        )
    assert caught.value.code == "tool_crashed"
    assert time.monotonic() - started < 1.5
    assert observation["started"] is True
    assert observation["exit_code"] is not None
    assert "memory_sampling" in observation
    assert not group_exists(observation["pid"])


@pytest.mark.parametrize(
    "failure",
    ["acquire", "timeout", "nonzero", "decode", "parse", "oversized"],
)
def test_inventory_failures_are_controller_accidents(tmp_path, monkeypatch, failure):
    def inventory(*_args, **_kwargs):
        if failure == "acquire":
            raise FileNotFoundError("ps missing")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(["/bin/ps"], 1.0)
        if failure == "nonzero":
            raise subprocess.CalledProcessError(1, ["/bin/ps"])
        if failure == "decode":
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")
        stdout = "broken row\n" if failure == "parse" else "x" * (2 * 1024 * 1024 + 1)
        return subprocess.CompletedProcess(["/bin/ps"], 0, stdout=stdout, stderr="")

    monkeypatch.setattr(primitives.subprocess, "run", inventory)
    observation = {}
    with pytest.raises(AcceptanceFailure) as caught:
        _run(
            tmp_path,
            "import time; time.sleep(3)",
            limits=_limits(),
            observation=observation,
        )
    assert caught.value.code == "runner_internal_error"
    assert observation["exit_code"] is not None
    assert "memory_sampling" in observation
    assert not group_exists(observation["pid"])


@pytest.mark.parametrize(
    "program,limit,expected",
    [
        ("import time; time.sleep(3)", 0.1, "tool_crashed"),
        ("import os; os.write(1, b'x'*65536)", 3.0, "evidence_truncated"),
    ],
)
def test_process_limits_produce_controller_accidents(tmp_path, program, limit, expected):
    with pytest.raises(AcceptanceFailure) as caught:
        run_command(
            "probe",
            [sys.executable, "-c", program],
            cwd=tmp_path,
            env=clean_environment(Path(sys.executable)),
            log_path=tmp_path / "log",
            timeout=limit,
            max_log_bytes=1024,
        )
    assert caught.value.code == expected


@pytest.mark.parametrize("boundary", ["entry", "term"])
def test_child_exit_during_cleanup_keeps_accident_and_observations(
    tmp_path, monkeypatch, boundary,
):
    import os
    import signal

    real_stop, real_killpg = primitives.stop_group, os.killpg
    children, os_errors = [], []
    delayed = False

    def killpg(group, sig):
        nonlocal delayed
        if children and boundary != "entry" and sig == signal.SIGTERM and not delayed:
            delayed = True
            time.sleep(0.3)
        try:
            return real_killpg(group, sig)
        except OSError as exc:
            os_errors.append(exc.errno)
            raise

    def stop(process):
        children.append(process)
        if boundary == "entry":
            time.sleep(0.3)
        real_stop(process)

    monkeypatch.setattr(primitives, "stop_group", stop)
    monkeypatch.setattr(primitives.os, "killpg", killpg)
    observation = {}
    try:
        with pytest.raises(AcceptanceFailure) as caught:
            _run(tmp_path.resolve(), "import time; time.sleep(0.1)",
                 timeout=0.02, observation=observation)
        assert caught.value.code == "tool_crashed"
        assert "wall timeout" in str(caught.value)
        assert observation["exit_code"] == 0
        assert observation["memory_sampling"]["samples"] == 0
        assert children[0].poll() == 0
        assert not group_exists(observation["pid"])
        if sys.platform == "darwin" and boundary != "entry":
            assert errno.EPERM in os_errors
    finally:
        for process in children:
            process.wait(timeout=1)


def test_group_disappears_before_cleanup_signal(tmp_path, monkeypatch):
    import os
    import signal

    real_stop, real_killpg = primitives.stop_group, os.killpg
    children, os_errors = [], []

    def stop(process):
        children.append(process)
        real_stop(process)

    def killpg(group, sig):
        if children and sig == signal.SIGTERM:
            children[0].wait(timeout=1)
        try:
            return real_killpg(group, sig)
        except OSError as exc:
            os_errors.append(exc.errno)
            raise

    monkeypatch.setattr(primitives, "stop_group", stop)
    monkeypatch.setattr(primitives.os, "killpg", killpg)
    observation = {}
    try:
        with pytest.raises(AcceptanceFailure) as caught:
            _run(tmp_path.resolve(), "import time; time.sleep(0.1)",
                 timeout=0.02, observation=observation)
        assert caught.value.code == "tool_crashed"
        assert errno.ESRCH in os_errors
        assert observation["exit_code"] == 0
        assert "memory_sampling" in observation
        assert not group_exists(observation["pid"])
    finally:
        for process in children:
            process.wait(timeout=1)


@pytest.mark.parametrize("earlier_failure", [True, False])
def test_cleanup_permission_failure_is_visible_and_observation_finishes(
    tmp_path, monkeypatch, earlier_failure,
):
    import os
    import signal

    real_stop, real_killpg = primitives.stop_group, os.killpg
    children = []

    def stop(process):
        children.append(process)
        real_stop(process)

    def denied(group, sig):
        if children:
            raise PermissionError(errno.EPERM, "controlled cleanup denial")
        return real_killpg(group, sig)

    monkeypatch.setattr(primitives, "stop_group", stop)
    monkeypatch.setattr(primitives.os, "killpg", denied)
    observation = {}
    try:
        with pytest.raises(AcceptanceFailure) as caught:
            # A caller's active exception must not become this command's failure.
            try:
                raise AcceptanceFailure("unrelated_caller_failure", "outside command")
            except AcceptanceFailure:
                _run(tmp_path.resolve(),
                     "import time; time.sleep(2)" if earlier_failure else "pass",
                     timeout=0.02 if earlier_failure else 1, observation=observation)
        assert caught.value.code == (
            "tool_crashed" if earlier_failure else "runner_internal_error"
        )
        assert "cleanup" in str(caught.value)
        assert "controlled cleanup denial" in str(caught.value)
        assert isinstance(caught.value.__cause__, PermissionError)
        if earlier_failure:
            assert "wall timeout" in str(caught.value)
            assert children[0].poll() is None
        assert "exit_code" in observation
        assert "memory_sampling" in observation
    finally:
        for process in children:
            try:
                real_killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=1)


def test_cleanup_kills_live_descendant_after_leader_exit(tmp_path):
    import os
    import signal

    folder = tmp_path.resolve()
    observation = {}
    program = """
import os, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c',
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); '
    'open("ready", "w").close(); time.sleep(3)'])
while not os.path.exists('ready'):
    time.sleep(0.005)
print(child.pid, flush=True)
"""
    try:
        with pytest.raises(AcceptanceFailure) as caught:
            _run(folder, program, observation=observation)
        assert caught.value.code == "tool_crashed"
        assert "process group leak" in str(caught.value)
        assert observation["exit_code"] == 0
        assert not group_exists(observation["pid"])
        descendant = int((folder / "log").read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(descendant, 0)
    finally:
        if "pid" in observation:
            try:
                os.killpg(observation["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize("declared_limits", [None, _limits()])
def test_file_limit_respects_lower_inherited_hard_limit(tmp_path, declared_limits):
    folder = tmp_path.resolve()
    program = f"""
import json, resource, sys
from pathlib import Path
from acceptance.primitives import clean_environment, run_command
resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))
folder = Path({str(folder)!r})
observation = {{}}
rc = run_command('inherited-limit', [sys.executable, '-c',
    'import json,resource; print(json.dumps(resource.getrlimit(resource.RLIMIT_FSIZE)))'],
    cwd=folder, env=clean_environment(Path(sys.executable)),
    log_path=folder / 'inner.log', timeout=2, max_log_bytes=8192,
    limits={declared_limits!r}, observation=observation)
assert rc == 0
assert json.loads((folder / 'inner.log').read_text()) == [4096, 4096]
assert observation['exit_code'] == 0
print('inherited FSIZE 4096 applied')
"""
    report = subprocess.run(
        [sys.executable, "-c", program], cwd=REPO,
        capture_output=True, text=True, timeout=5,
    )
    assert report.returncode == 0, report.stderr
    assert report.stdout.strip() == "inherited FSIZE 4096 applied"
