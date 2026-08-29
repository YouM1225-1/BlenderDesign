#!/usr/bin/env python3
"""Fail-closed wrapper for the existing Phase 0 Blender smoke gates."""
from __future__ import annotations

import argparse
import datetime
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from acceptance.primitives import (
    AcceptanceFailure,
    clean_environment,
    create_private_directory,
    file_evidence,
    normalise_new_root,
    require_zero,
    run_command,
    strict_json_loads,
    write_json_exclusive,
)
from smoke.process_registry import read_private_bytes

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
DEFAULT_UV = Path.home() / ".local/bin/uv"
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
REQUIRED_PYTHON = (3, 13, 13)
GUI_REQUIRED_TRUE = (
    "timer_tick", "revision_bump", "fields", "hash_scope", "cycles_leak_free",
    "large_scene", "large_scene_budget_ok", "nfr_p1",
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--uv", type=Path, default=DEFAULT_UV)
    parser.add_argument("--large-objects", type=int, default=100_000)
    parser.add_argument("--background-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--gui-timeout-seconds", type=float, default=360.0)
    parser.add_argument("--recovery-timeout-seconds", type=float, default=180.0)
    args = parser.parse_args(argv)
    for name in (
        "background_timeout_seconds", "gui_timeout_seconds",
        "recovery_timeout_seconds",
    ):
        value = getattr(args, name)
        if not math.isfinite(value) or value < 15.0:
            parser.error(f"--{name.replace('_', '-')} must be finite and at least 15")
    if args.large_objects != 100_000:
        parser.error("--large-objects must be exactly 100000")
    return args


def _normalise_new_root(path: Path) -> Path:
    return normalise_new_root(path, ROOT)


_create_private_directory = create_private_directory


def _require_clean_worktree(env: dict[str, str]) -> None:
    completed = subprocess.run(
        ["/usr/bin/git", "-c", "core.fsmonitor=false", "status",
         "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=15.0, env=env,
    )
    if completed.stdout:
        raise AcceptanceFailure(
            "dirty_worktree", "formal Phase 0 evidence requires a clean Git worktree")


def _resolve_executable(value: Path, label: str) -> Path:
    text = str(value.expanduser())
    found = shutil.which(text) if os.sep not in text else text
    if found is None:
        raise AcceptanceFailure(f"missing_{label}", f"{label} executable not found")
    path = Path(found).resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise AcceptanceFailure(
            f"invalid_{label}", f"{label} executable is not an executable file: {path}")
    return path


def _require_python_version(actual: tuple[int, int, int] | None = None) -> None:
    version = tuple(sys.version_info[:3]) if actual is None else actual
    if version != REQUIRED_PYTHON:
        expected = ".".join(map(str, REQUIRED_PYTHON))
        found = ".".join(map(str, version))
        raise AcceptanceFailure(
            "wrong_python_patch", f"Python {expected} required; found {found}")


def _clean_environment(uv: Path) -> dict[str, str]:
    clean = clean_environment(uv)
    return clean


def _read_artifact(path: Path, mode: str, large_objects: int) -> dict[str, Any]:
    try:
        raw = read_private_bytes(
            path, time.monotonic() + 5.0, MAX_ARTIFACT_BYTES)
        value = strict_json_loads(raw)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AcceptanceFailure(
            f"{mode}_artifact_invalid", f"invalid {mode} artifact: {exc}") from exc
    if type(value) is not dict:
        raise AcceptanceFailure(
            f"{mode}_artifact_invalid", f"{mode} artifact must be a JSON object")
    artifact = value
    if (type(artifact.get("schema_version")) is not int
            or artifact["schema_version"] != 1
            or artifact.get("mode") != mode
            or artifact.get("success") is not True):
        raise AcceptanceFailure(
            f"{mode}_artifact_invalid",
            f"{mode} artifact schema, mode, or success is invalid",
        )
    if mode == "gui":
        metrics = artifact.get("large_scene_metrics")
        if (any(artifact.get(key) is not True for key in GUI_REQUIRED_TRUE)
                or artifact.get("errors") != []
                or type(metrics) is not dict
                or metrics.get("target_objects") != large_objects):
            raise AcceptanceFailure(
                "gui_artifact_invalid", "GUI required checks are incomplete or failed")
    elif type(artifact.get("provenance")) is not dict:
        raise AcceptanceFailure(
            f"{mode}_artifact_invalid", f"{mode} provenance is missing")
    if mode == "nfr" and type(artifact.get("results")) is not dict:
        raise AcceptanceFailure("nfr_artifact_invalid", "NFR results are missing")
    if mode == "recovery" and artifact.get("same_mcp_server_session") is not True:
        raise AcceptanceFailure(
            "recovery_artifact_invalid", "recovery MCP session identity was not preserved")
    return artifact


def _file_evidence(path: Path) -> dict[str, object]:
    return file_evidence(path, MAX_ARTIFACT_BYTES)


def _write_json_exclusive(path: Path, value: object) -> None:
    write_json_exclusive(path, value)


def _run_command(stage, command, *, env, log_path, timeout):
    return run_command(stage, command, cwd=ROOT, env=env, log_path=log_path, timeout=timeout)


_require_zero = require_zero


def _execute(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    _require_python_version()
    blender = _resolve_executable(args.blender, "blender")
    uv = _resolve_executable(args.uv, "uv")
    base_env = _clean_environment(uv)
    _require_clean_worktree(base_env)
    runtime = {}
    for name in ("background", "gui", "recovery"):
        path = root / f"{name}-runtime"
        _create_private_directory(path)
        runtime[name] = path
    recovery_registry = root / "recovery-processes"
    _create_private_directory(recovery_registry)

    stages: dict[str, dict[str, object]] = {}
    vendor_logs = {}
    for stage, extra in (
        ("vendor_generate", []), ("vendor_check", ["--check"]),
    ):
        log = root / f"{stage}.log"
        rc = _run_command(
            stage, [sys.executable, "scripts/vendor_protocol.py", *extra],
            env=base_env, log_path=log, timeout=args.background_timeout_seconds,
        )
        stages[stage] = {"exit_code": rc}
        vendor_logs[stage] = log
        _require_zero(stage, rc)
    _require_clean_worktree(base_env)

    background_log = root / "background.log"
    rc = _run_command(
        "background",
        [str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
         "--python", "smoke/bg_check.py"],
        env=base_env | {"BLENDERCODEX_ROOT": str(runtime["background"])},
        log_path=background_log, timeout=args.background_timeout_seconds,
    )
    stages["background"] = {"exit_code": rc}
    _require_zero("background", rc)

    gui_path, nfr_path = root / "gui.json", root / "nfr.json"
    gui_log = root / "gui.log"
    rc = _run_command(
        "gui",
        [str(blender), "--factory-startup", "--python-exit-code", "1",
         "--python", "smoke/runner.py"],
        env=base_env | {
            "BLENDERCODEX_ROOT": str(runtime["gui"]),
            "BLENDERCODEX_SMOKE_OUT": str(gui_path),
            "BLENDERCODEX_NFR_OUT": str(nfr_path),
            "BLENDERCODEX_LARGE_OBJECTS": str(args.large_objects),
        },
        log_path=gui_log, timeout=args.gui_timeout_seconds,
    )
    stages["gui"] = {"exit_code": rc}
    _require_zero("gui", rc)
    _read_artifact(gui_path, "gui", args.large_objects)
    _read_artifact(nfr_path, "nfr", args.large_objects)

    recovery_path, recovery_log = root / "recovery.json", root / "recovery.log"
    rc = _run_command(
        "recovery",
        [str(uv), "run", "--frozen", "python", "smoke/e2e.py", "recovery",
         "--root", str(runtime["recovery"]), "--output", str(recovery_path),
         "--process-registry", str(recovery_registry),
         "--timeout-seconds", str(args.recovery_timeout_seconds)],
        env=base_env, log_path=recovery_log,
        timeout=args.recovery_timeout_seconds + 30.0,
    )
    stages["recovery"] = {"exit_code": rc}
    _require_zero("recovery", rc)
    _read_artifact(recovery_path, "recovery", args.large_objects)
    if any(recovery_registry.iterdir()):
        raise AcceptanceFailure(
            "recovery_process_registry_not_empty",
            "recovery process registry is not empty after success",
        )

    return {
        "stages": stages,
        "artifacts": {
            name: _file_evidence(path)
            for name, path in (
                ("gui", gui_path), ("nfr", nfr_path), ("recovery", recovery_path)
            )
        },
        "logs": {
            name: _file_evidence(path)
            for name, path in (
                *vendor_logs.items(),
                ("background", background_log), ("gui", gui_log),
                ("recovery", recovery_log),
            )
        },
        "toolchain": {
            "python": sys.version.split()[0], "blender": str(blender), "uv": str(uv),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        root = _normalise_new_root(args.evidence_root)
    except AcceptanceFailure as exc:
        print(f"PHASE0_ACCEPTANCE_FAIL {exc.code}: {exc}", file=sys.stderr)
        return 1
    _create_private_directory(root)
    started_at = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        result = _execute(args, root)
        summary = {
            "schema_version": 1,
            "kind": "phase0_acceptance",
            "success": True,
            "started_at": started_at,
            "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
            **result,
        }
        returncode = 0
    except AcceptanceFailure as exc:
        summary = {
            "schema_version": 1,
            "kind": "phase0_acceptance",
            "success": False,
            "failure_code": exc.code,
            "error": str(exc),
            "started_at": started_at,
            "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        returncode = 1
    except Exception as exc:
        summary = {
            "schema_version": 1,
            "kind": "phase0_acceptance",
            "success": False,
            "failure_code": "runner_internal_error",
            "error": f"{type(exc).__name__}: {exc}",
            "started_at": started_at,
            "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        returncode = 1
    _write_json_exclusive(root / "summary.json", summary)
    status = "OK" if returncode == 0 else f"FAIL {summary['failure_code']}"
    print(f"PHASE0_ACCEPTANCE_{status} {root / 'summary.json'}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
