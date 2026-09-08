from __future__ import annotations

from typing import Any

import os
import re
import sys
import tempfile
from pathlib import Path

from acceptance.canonical import digest
from acceptance.contract import Contract, thaw
from acceptance.input_bundle import measure_file, read_bounded
from acceptance.primitives import AcceptanceFailure, clean_environment, run_command


def trusted_code_files(repo_root: Path) -> tuple[Path, ...]:
    paths = list((repo_root / "acceptance").rglob("*.py"))
    paths += list((repo_root / "acceptance").rglob("*.json"))
    paths += [repo_root / "scripts/asset_accept.py", repo_root / "smoke/process_registry.py"]
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise AcceptanceFailure("toolchain_mismatch", "missing or linked trusted code member")
    return tuple(sorted(paths))


def provenance(repo_root: Path) -> dict[str, Any]:
    rows = []
    for path in trusted_code_files(repo_root):
        measured = measure_file(path, 32 * 1024 * 1024, file_id="code")
        rows.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "bytes": measured.bytes,
                "sha256": measured.sha256,
            }
        )
    return {
        "id": "acceptance",
        "version": "acc-v2-" + digest("code.v2", rows),
        "files": rows,
    }


def measure_tool(tool: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    # Resolve an installed executable once, then measure it and every declared script.
    path = Path(tool["path"]).resolve(strict=True)
    measured = measure_file(path, 2 * 1024**3, file_id=tool["id"])
    if measured.sha256 != tool["sha256"]:
        raise AcceptanceFailure("toolchain_mismatch", "executable hash mismatch")
    for member in tool["files"]:
        item = measure_file(Path(member["path"]), 2 * 1024**3, file_id="dependency")
        if item.bytes != member["bytes"] or item.sha256 != member["sha256"]:
            raise AcceptanceFailure("toolchain_mismatch", "tool dependency hash mismatch")
    if tool["id"] == "acceptance":
        code = provenance(repo_root)
        required = {str(item.absolute()) for item in trusted_code_files(repo_root)}
        declared = {member["path"] for member in tool["files"]}
        if required != declared:
            raise AcceptanceFailure("toolchain_mismatch", "acceptance code closure mismatch")
        version = code["version"]
    else:
        if not os.access(path, os.X_OK):
            raise AcceptanceFailure("toolchain_mismatch", "tool is not executable")
        with tempfile.TemporaryDirectory(prefix="acceptance-version-") as temporary:
            folder = Path(temporary).resolve()
            log = folder / "version.txt"
            returncode = run_command(
                "tool-version",
                [str(path), "--version"],
                cwd=folder,
                env=clean_environment(Path(sys.executable)),
                log_path=log,
                timeout=10.0,
                max_log_bytes=8192,
            )
            if returncode != 0:
                raise AcceptanceFailure("toolchain_mismatch", "version command failed")
            lines = read_bounded(log, 8192).decode("utf-8", errors="strict").splitlines()
            if not lines:
                raise AcceptanceFailure("toolchain_mismatch", "version output empty")
            version = lines[0].strip()
        patterns = {
            "python": r"Python 3\.13\.13",
            "blender": r"Blender 5\.2\.[0-9]+(?: LTS)?",
            "node": r"v20\.20\.2",
        }
        if re.fullmatch(patterns[tool["id"]], version) is None:
            raise AcceptanceFailure(
                "toolchain_mismatch", "tool kind or supported version mismatch"
            )
    if version != tool["version"]:
        raise AcceptanceFailure("toolchain_mismatch", "observed version differs from lock")
    return {
        "id": tool["id"],
        "path": str(path),
        "bytes": measured.bytes,
        "sha256": measured.sha256,
        "version": version,
        "files": thaw(tool["files"]),
    }


def verify_tools(
    contract: Contract, required_ids: tuple[str, ...], repo_root: Path
) -> list[dict[str, Any]]:
    tools = {tool["id"]: thaw(tool) for tool in contract.raw["tools"]}
    if not set(required_ids) <= set(tools):
        raise AcceptanceFailure("toolchain_mismatch", "missing required tools")
    try:
        return [measure_tool(tools[key], repo_root) for key in sorted(tools)]
    except (OSError, ValueError, KeyError) as exc:
        raise AcceptanceFailure("toolchain_mismatch", str(exc)) from exc
