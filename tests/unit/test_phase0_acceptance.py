import ast
import json
import time
from pathlib import Path

import pytest

from scripts import run_phase0_acceptance as acceptance
from scripts import vendor_protocol
from smoke import e2e


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _gui_artifact(success: bool) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "gui",
        "success": success,
        "timer_tick": True,
        "revision_bump": True,
        "fields": True,
        "hash_scope": True,
        "cycles_leak_free": True,
        "large_scene": True,
        "large_scene_budget_ok": True,
        "large_scene_metrics": {"target_objects": 100_000},
        "nfr_p1": success,
        "nfr_p1_metrics": {},
        "errors": [] if success else ["fixture failure"],
    }


def _formal_artifact(mode: str) -> dict[str, object]:
    artifact: dict[str, object] = {
        "schema_version": 1,
        "mode": mode,
        "success": True,
        "provenance": {},
        "results": {},
    }
    if mode == "recovery":
        artifact["same_mcp_server_session"] = True
    return artifact


def _write_log(path: Path, stage: str) -> None:
    path.write_text(stage, encoding="utf-8")
    path.chmod(0o600)


def _write_executable(path: Path, output: str = "") -> Path:
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' {output!r}\n", encoding="utf-8")
    path.chmod(0o700)
    return path.resolve()


def test_blender_exit_zero_artifact_fail_is_not_accepted(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    blender = _write_executable(tmp_path / "blender")
    uv = _write_executable(tmp_path / "uv")
    calls = []

    def fake_run(stage, _command, *, env, log_path, timeout):
        calls.append((stage, env, log_path, timeout))
        _write_log(log_path, stage)
        if stage == "gui":
            _write_json(root / "gui.json", _gui_artifact(False))
            _write_json(root / "nfr.json", _formal_artifact("nfr"))
        return 0

    monkeypatch.setattr(acceptance, "_run_command", fake_run)
    monkeypatch.setattr(acceptance, "_require_clean_worktree", lambda _env: None)
    assert acceptance.main([
        "--evidence-root", str(root), "--blender", str(blender), "--uv", str(uv),
    ]) == 1
    assert [call[0] for call in calls] == [
        "vendor_generate", "vendor_check", "background", "gui",
    ]
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["success"] is False
    assert summary["failure_code"] == "gui_artifact_invalid"


def test_reused_evidence_root_is_rejected_without_touching_it(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    root.mkdir(mode=0o700)
    marker = root / "old-report.json"
    marker.write_text("old", encoding="utf-8")

    def unexpected_run(*_args, **_kwargs):
        pytest.fail("no process may start for a reused evidence root")

    monkeypatch.setattr(acceptance, "_run_command", unexpected_run)
    assert acceptance.main(["--evidence-root", str(root)]) == 1
    assert marker.read_text(encoding="utf-8") == "old"
    assert sorted(path.name for path in root.iterdir()) == ["old-report.json"]


def test_success_requires_all_three_artifacts_and_writes_hashes(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    blender = _write_executable(tmp_path / "blender")
    uv = _write_executable(tmp_path / "uv")
    calls = []

    def fake_run(stage, _command, *, env, log_path, timeout):
        calls.append(stage)
        _write_log(log_path, stage)
        if stage == "gui":
            _write_json(root / "gui.json", _gui_artifact(True))
            _write_json(root / "nfr.json", _formal_artifact("nfr"))
        elif stage == "recovery":
            _write_json(root / "recovery.json", _formal_artifact("recovery"))
        return 0

    monkeypatch.setattr(acceptance, "_run_command", fake_run)
    monkeypatch.setattr(acceptance, "_require_clean_worktree", lambda _env: None)
    assert acceptance.main([
        "--evidence-root", str(root), "--blender", str(blender), "--uv", str(uv),
    ]) == 0
    assert calls == [
        "vendor_generate", "vendor_check", "background", "gui", "recovery",
    ]
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["success"] is True
    assert set(summary["artifacts"]) == {"gui", "nfr", "recovery"}
    assert all(len(item["sha256"]) == 64 for item in summary["artifacts"].values())


@pytest.mark.parametrize("fixture_name", ["blender-one", "blender-two"])
def test_selected_blender_and_private_stage_environment_reach_all_smokes(
    tmp_path, monkeypatch, fixture_name,
):
    root = tmp_path / "evidence"
    blender = _write_executable(tmp_path / fixture_name, fixture_name)
    uv = _write_executable(tmp_path / "uv")
    calls = {}

    def fake_run(stage, command, *, env, log_path, timeout):
        calls[stage] = (command, env)
        _write_log(log_path, stage)
        if stage == "gui":
            _write_json(root / "gui.json", _gui_artifact(True))
            _write_json(root / "nfr.json", _formal_artifact("nfr"))
        elif stage == "recovery":
            _write_json(root / "recovery.json", _formal_artifact("recovery"))
        return 0

    monkeypatch.setattr(acceptance, "_run_command", fake_run)
    monkeypatch.setattr(acceptance, "_require_clean_worktree", lambda _env: None)
    assert acceptance.main([
        "--evidence-root", str(root), "--blender", str(blender), "--uv", str(uv),
    ]) == 0

    assert str(blender) != str(acceptance.DEFAULT_BLENDER)
    assert calls["background"][0][0] == str(blender)
    assert calls["gui"][0][0] == str(blender)
    recovery_command = calls["recovery"][0]
    assert recovery_command[recovery_command.index("--blender") + 1] == str(blender)

    user_keys = {
        "BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS",
        "BLENDER_USER_EXTENSIONS", "BLENDER_USER_DATAFILES",
        "BLENDER_USER_RESOURCES",
    }
    stage_paths = []
    for stage in ("background", "gui", "recovery"):
        env = calls[stage][1]
        paths = {key: Path(env[key]) for key in user_keys}
        assert len(set(paths.values())) == len(user_keys)
        assert env["TMPDIR"] == env["TMP"] == env["TEMP"]
        paths["TMPDIR"] = Path(env["TMPDIR"])
        assert all(root in path.parents for path in paths.values())
        assert all(path.is_dir() and path.stat().st_mode & 0o777 == 0o700
                   for path in paths.values())
        stage_paths.append(set(paths.values()))
    assert len(set().union(*stage_paths)) == sum(len(paths) for paths in stage_paths)


def test_non_executable_blender_fails_before_process_spawn(tmp_path, monkeypatch):
    root = tmp_path / "evidence"
    blender = tmp_path / "not-executable"
    blender.write_text("fixture", encoding="utf-8")
    blender.chmod(0o600)
    uv = _write_executable(tmp_path / "uv")
    monkeypatch.setattr(
        acceptance, "_run_command",
        lambda *_args, **_kwargs: pytest.fail("no process may start"),
    )

    assert acceptance.main([
        "--evidence-root", str(root), "--blender", str(blender), "--uv", str(uv),
    ]) == 1
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["failure_code"] == "invalid_blender"


def test_gui_runner_publishes_success_in_its_artifact():
    runner = Path(__file__).resolve().parents[2] / "smoke" / "runner.py"
    tree = ast.parse(runner.read_text(encoding="utf-8"))
    finish = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_finish"
    )
    assignments = [
        node for node in ast.walk(finish)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "RES"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "success"
            for target in node.targets
        )
    ]
    assert assignments


def test_large_scene_contract_is_exactly_100000_objects(tmp_path):
    with pytest.raises(SystemExit):
        acceptance._parse_args([
            "--evidence-root", str(tmp_path / "evidence"),
            "--large-objects", "100001",
        ])


def test_child_environment_drops_python_blender_and_uv_injection(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/hostile")
    monkeypatch.setenv("BLENDERCODEX_SMOKE_OUT", "/hostile/smoke.json")
    monkeypatch.setenv("BLENDER_USER_SCRIPTS", "/hostile/scripts")
    monkeypatch.setenv("GIT_DIR", "/hostile/repository")
    monkeypatch.setenv("UV_PROJECT", "/hostile/project")
    monkeypatch.setenv("VIRTUAL_ENV", "/hostile/venv")
    clean = acceptance._clean_environment(Path("/trusted/uv"))
    assert clean["UV_BIN"] == "/trusted/uv"
    assert clean["PYTHONDONTWRITEBYTECODE"] == "1"
    assert clean["GIT_CONFIG_NOSYSTEM"] == "1"
    assert clean["GIT_CONFIG_GLOBAL"] == "/dev/null"
    assert clean["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert not any(
        key in clean
        for key in (
            "PYTHONPATH", "BLENDERCODEX_SMOKE_OUT", "BLENDER_USER_SCRIPTS",
            "GIT_DIR", "UV_PROJECT", "VIRTUAL_ENV",
        )
    )
    assert clean["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"


def test_wrong_python_patch_is_rejected():
    with pytest.raises(acceptance.AcceptanceFailure) as caught:
        acceptance._require_python_version((3, 13, 14))
    assert caught.value.code == "wrong_python_patch"


def test_background_smoke_disables_bytecode_before_project_imports():
    background = Path(__file__).resolve().parents[2] / "smoke" / "bg_check.py"
    tree = ast.parse(background.read_text(encoding="utf-8"))
    guard = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "sys"
            and target.attr == "dont_write_bytecode"
            for target in node.targets
        )
    )
    project_imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and (node.module or "").split(".", 1)[0] in {"bridge", "server"}
    ]
    assert project_imports
    assert all(guard.lineno < node.lineno for node in project_imports)


def test_vendor_generation_removes_stale_root_entries(tmp_path, monkeypatch):
    source = tmp_path / "protocol"
    destination = tmp_path / "bridge" / "_vendor" / "protocol"
    source.mkdir()
    (source / "__init__.py").write_text("", encoding="utf-8")
    destination.mkdir(parents=True)
    stale = destination.parent / "__pycache__"
    stale.mkdir()
    (stale / "old.pyc").write_bytes(b"old")
    monkeypatch.setattr(vendor_protocol, "SRC", source)
    monkeypatch.setattr(vendor_protocol, "DST", destination)
    monkeypatch.setattr(vendor_protocol.sys, "argv", ["vendor_protocol.py"])
    assert vendor_protocol.main() == 0
    assert {path.name for path in destination.parent.iterdir()} == {
        "__init__.py", "protocol",
    }


def test_formal_provenance_uses_absolute_system_git(monkeypatch):
    seen = []

    def fake_bounded(command, **_kwargs):
        seen.append(command)
        return b""

    monkeypatch.setattr(e2e, "_bounded_process_stdout", fake_bounded)
    assert e2e._git_bytes(time.monotonic() + 1.0, "status") == b""
    assert seen == [["/usr/bin/git", "-c", "core.fsmonitor=false", "status"]]
