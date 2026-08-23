"""Formal Phase 0 E2E gates: 60-call NFR-P1 and real Blender kill/restart."""
from __future__ import annotations

import argparse
import asyncio
import collections
import datetime
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import secrets
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from protocol import envelope
from server.mcp.adapter import CapabilitiesResult, SceneSummaryResult, StatusResult
try:
    from smoke.process_registry import (
        ProcessRecord,
        REPLACE_MODE,
        SENTINEL_MODE,
        _unlink_private_temporary,
        cleanup_owned_process,
        cleanup_unpublished_process,
        cleanup_registry,
        finish_publication_reservation,
        new_marker,
        poll_before_deadline,
        read_private_bytes,
        read_record,
        recorded_group_is_live,
        require_private_directory,
        reserve_publication,
        retire_record,
        scan_records,
        wait_owned_process_record,
    )
except ModuleNotFoundError:  # absolute script execution puts smoke/ on sys.path
    from process_registry import (  # type: ignore[no-redef]
        ProcessRecord,
        REPLACE_MODE,
        SENTINEL_MODE,
        _unlink_private_temporary,
        cleanup_owned_process,
        cleanup_unpublished_process,
        cleanup_registry,
        finish_publication_reservation,
        new_marker,
        poll_before_deadline,
        read_private_bytes,
        read_record,
        recorded_group_is_live,
        require_private_directory,
        reserve_publication,
        retire_record,
        scan_records,
        wait_owned_process_record,
    )

ROOT = Path(__file__).resolve().parents[1]
UV = os.environ.get("UV_BIN", str(Path.home() / ".local/bin/uv"))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
RUNS = 20
P95_LIMIT_MS = 2000.0
READ_TIMEOUT_SECONDS = 30.0
WORKER_MODE = "__worker"
RECOVERY_CLEANUP_MARGIN = 15.0
RECOVERY_WORKER_TERM_GRACE = 8.0
RECOVERY_GROUP_TERM_GRACE = 3.0
RECOVERY_REGISTRY_RESERVE = 5.0
MAX_SOURCE_FILES = 512
MAX_SOURCE_FILE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_TOTAL_BYTES = 128 * 1024 * 1024
MAX_TRACKED_PATH_BYTES = 4096
MAX_GIT_LIST_BYTES = (MAX_SOURCE_FILES + 1) * (MAX_TRACKED_PATH_BYTES + 1)
MAX_SAMPLE_RESULT_BYTES = 256 * 1024
MAX_SAMPLE_TEXT_BYTES = 256 * 1024
MAX_SAMPLE_RESULTS_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_RECOVERY_READY_BYTES = 4096
MAX_AUDIT_FILES = 8
MAX_AUDIT_FILE_BYTES = 4 * 1024 * 1024
MAX_AUDIT_TOTAL_BYTES = 16 * 1024 * 1024
MAX_AUDIT_LINE_BYTES = 64 * 1024
MAX_AUDIT_ROWS = 256
MAX_RECOVERY_STATUS_ATTEMPTS = 64
MAX_FAILURE_GROUP_DEPTH = 4
MAX_FAILURE_LEAVES = 8
MAX_FAILURE_TYPE_CHARS = 64
MAX_FAILURE_MESSAGE_CHARS = 256
MAX_FAILURE_ERROR_CHARS = 2048
AUDIT_KEYS = {
    "ts", "request_id", "tool", "instance_id", "transaction_id",
    "params_digest", "ok", "duration_ms", "paths", "error",
}
EXPECTED_TOOLS = [
    "get_blender_status", "get_scene_summary", "describe_capabilities",
]
FROZEN_CATALOG_BYTES = 6389
FROZEN_CATALOG_SHA256 = "b2a833a9415363be1db0c9092f46505cb7125f978801ab57fc486448b6c842d8"
FROZEN_SCHEMA_BYTES = 5829
FROZEN_COMBINED_SCHEMA_SHA256 = "52e4b386e581976644ac4f8ef760bae334e11fcc78790ad1adc7ebf3540b3f5c"
FROZEN_INSTRUCTIONS_BYTES = 322
FROZEN_INSTRUCTIONS_SHA256 = "3810714ab9be87e9203432e446fc7ba261737153f4c85f2103a7ec983239cedb"
FROZEN_SERVER_NAME = "blender-codex"
FROZEN_SERVER_VERSION = "0.1.0"


def _server_params(
    runtime_root: Path, process_record: Path, registry_marker: str,
) -> tuple[StdioServerParameters, tuple[Path, int, int]]:
    reservation, device, inode = reserve_publication(process_record)
    try:
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                str(Path(__file__).with_name("process_registry.py")), SENTINEL_MODE,
                str(process_record), str(reservation), str(device), str(inode),
                registry_marker, UV,
                "--directory", str(ROOT), "run", "--frozen", "blender-codex-server",
            ],
            env=os.environ | {
                "BLENDERCODEX_ROOT": str(runtime_root),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
    except BaseException:
        finish_publication_reservation(reservation, device, inode)
        raise
    return params, (reservation, device, inode)


def _retire_record_or_reservation(
    process_record: Path,
    publication: tuple[Path, int, int],
    *,
    expected_marker: str,
    not_before_ns: int,
) -> None:
    try:
        process_record.lstat()
    except FileNotFoundError:
        finish_publication_reservation(*publication)
    else:
        retire_record(
            process_record, expected_marker=expected_marker,
            not_before_ns=not_before_ns)


def _canonical(value: object) -> tuple[int, str]:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return len(raw), hashlib.sha256(raw).hexdigest()


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json_loads(raw: str | bytes) -> object:
    return cast(object, json.loads(
        raw, parse_constant=_reject_json_constant, parse_float=_finite_json_float,
        object_pairs_hook=_reject_duplicate_keys))


def _exact_json_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        left_dict = cast(dict[object, object], left)
        right_dict = cast(dict[object, object], right)
        return (set(left_dict) == set(right_dict)
                and all(_exact_json_equal(left_dict[key], right_dict[key])
                        for key in left_dict))
    if type(left) is list:
        left_list = cast(list[object], left)
        right_list = cast(list[object], right)
        return (len(left_list) == len(right_list)
                and all(_exact_json_equal(a, b)
                        for a, b in zip(left_list, right_list, strict=True)))
    return type(left) in (str, int, float, bool, type(None)) and left == right


def _sha256_file(
    path: Path,
    *,
    deadline: float | None = None,
    max_bytes: int = MAX_ARTIFACT_BYTES,
) -> str:
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes
            or before.st_size < 0):
        raise ValueError(f"bounded regular file required: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    digest = hashlib.sha256()
    total = 0
    try:
        opened = os.fstat(fd)
        if ((opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or not stat.S_ISREG(opened.st_mode) or opened.st_size > max_bytes):
            raise RuntimeError(f"source identity changed during open: {path}")
        while total < opened.st_size:
            if deadline is not None:
                _remaining(deadline)
            chunk = os.read(fd, min(1024 * 1024, opened.st_size - total))
            if not chunk:
                raise ValueError(f"source truncated during read: {path}")
            digest.update(chunk)
            total += len(chunk)
        if deadline is not None:
            _remaining(deadline)
    finally:
        os.close(fd)
    return digest.hexdigest()


def _require_private_directory(path: Path) -> None:
    require_private_directory(path)


def _write_private_json(output: Path, value: object) -> None:
    _require_private_directory(output.parent)
    raw = (json.dumps(
        value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("formal artifact exceeds the 32 MiB limit")
    temporary = output.parent / (
        f".{output.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    fd: int | None = None
    identity: tuple[int, int] | None = None
    try:
        fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        opened = os.fstat(fd)
        identity = opened.st_dev, opened.st_ino
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(raw)
        os.replace(temporary, output)
    finally:
        if fd is not None:
            os.close(fd)
        if identity is not None:
            _unlink_private_temporary(temporary, *identity)


def _write_artifact(output: Path, artifact: dict[str, Any]) -> None:
    _write_private_json(output, artifact)


def _bounded_process_stdout(
    command: list[str], *, cwd: Path, deadline: float, max_bytes: int,
) -> bytes:
    if max_bytes < 0:
        raise ValueError("negative subprocess output limit")
    with tempfile.TemporaryDirectory(prefix="bcx-bounded-process-") as temporary:
        registry = Path(temporary)
        registry.chmod(0o700)
        marker = new_marker()
        not_before_ns = time.monotonic_ns()
        record_path = registry / "owned.json"
        publication = reserve_publication(record_path)
        reservation, device, inode = publication
        wrapped = [
            sys.executable, str(Path(__file__).with_name("process_registry.py")),
            REPLACE_MODE, str(record_path), str(reservation), str(device),
            str(inode), marker, *command,
        ]
        cleanup_reserve = min(1.0, _remaining(deadline) / 2.0)
        work_deadline = deadline - cleanup_reserve
        try:
            process = subprocess.Popen(
                wrapped, cwd=cwd, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True)
        except BaseException:
            finish_publication_reservation(*publication)
            raise
        record: ProcessRecord | None = None
        try:
            if process.stdout is None:
                raise RuntimeError("bounded subprocess stdout pipe missing")
            record = wait_owned_process_record(
                process, record_path, expected_marker=marker,
                not_before_ns=not_before_ns, deadline=work_deadline)
            descriptor = process.stdout.fileno()
            os.set_blocking(descriptor, False)
            selector = selectors.DefaultSelector()
            selector.register(descriptor, selectors.EVENT_READ)
            chunks: list[bytes] = []
            total = 0
            try:
                while True:
                    events = selector.select(min(1.0, _remaining(work_deadline)))
                    if not events:
                        continue
                    chunk = os.read(
                        descriptor, min(64 * 1024, max_bytes - total + 1))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(
                            "bounded subprocess output exceeds its limit")
                returncode = process.wait(timeout=_remaining(work_deadline))
                _remaining(work_deadline)
                if returncode != 0:
                    raise subprocess.CalledProcessError(returncode, command)
                return b"".join(chunks)
            finally:
                selector.close()
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if record is None:
                cleanup_unpublished_process(
                    process, deadline=deadline,
                    term_grace=min(0.25, cleanup_reserve / 2.0))
                _retire_record_or_reservation(
                    record_path, publication, expected_marker=marker,
                    not_before_ns=not_before_ns)
            else:
                cleanup_owned_process(
                    process, record, deadline=deadline, term_grace=0.25)
                retire_record(
                    record_path, expected_marker=marker,
                    not_before_ns=not_before_ns)


def _git_bytes(
    deadline: float, *args: str, max_bytes: int = MAX_SOURCE_FILE_BYTES,
) -> bytes:
    return _bounded_process_stdout(
        ["git", *args], cwd=ROOT, deadline=deadline, max_bytes=max_bytes)


def _git_text(
    deadline: float, *args: str, max_bytes: int = MAX_SOURCE_FILE_BYTES,
) -> str:
    return _git_bytes(deadline, *args, max_bytes=max_bytes).decode().strip()


def _read_bounded_bytes(path: Path, deadline: float, max_bytes: int) -> bytes:
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes
            or before.st_size < 0):
        raise ValueError(f"bounded regular file required: {path}")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    chunks = []
    total = 0
    try:
        opened = os.fstat(fd)
        if ((opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or not stat.S_ISREG(opened.st_mode) or opened.st_size > max_bytes):
            raise RuntimeError(f"file identity changed during open: {path}")
        while total < opened.st_size:
            _remaining(deadline)
            chunk = os.read(fd, min(1024 * 1024, opened.st_size - total))
            if not chunk:
                raise ValueError(f"file truncated during read: {path}")
            chunks.append(chunk)
            total += len(chunk)
        _remaining(deadline)
    finally:
        os.close(fd)
    return b"".join(chunks)


def _read_private_json(path: Path, deadline: float, max_bytes: int) -> object:
    raw = read_private_bytes(path, deadline, max_bytes)
    value = _strict_json_loads(raw)
    _remaining(deadline)
    return value


def _bounded_directory_names(
    path: Path, deadline: float, max_entries: int,
) -> set[str]:
    before = path.lstat()
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError(f"bounded regular directory required: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if ((opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or not stat.S_ISDIR(opened.st_mode)):
            raise RuntimeError(f"directory identity changed during open: {path}")
        names = set()
        with os.scandir(descriptor) as entries:
            for entry in entries:
                _remaining(deadline)
                names.add(entry.name)
                if len(names) > max_entries:
                    raise RuntimeError(f"directory entry limit exceeded: {path}")
        return names
    finally:
        os.close(descriptor)


def _tracked_sources(deadline: float, required: set[Path]) -> set[Path]:
    scopes = [
        "protocol", "bridge", "server", "smoke", "scripts", "tests",
        "pyproject.toml", "uv.lock",
    ]
    raw = _git_bytes(
        deadline, "ls-files", "-z", "--", *scopes,
        max_bytes=MAX_GIT_LIST_BYTES)
    if raw and not raw.endswith(b"\0"):
        raise ValueError("tracked source list is not NUL terminated")
    items = [] if not raw else raw[:-1].split(b"\0")
    if len(items) > MAX_SOURCE_FILES:
        raise RuntimeError("tracked source path-count limit exceeded")
    files = set(required)
    if len(files) > MAX_SOURCE_FILES:
        raise RuntimeError("required source file-count limit exceeded")
    tracked: set[Path] = set()
    for item in items:
        if not item or len(item) > MAX_TRACKED_PATH_BYTES:
            raise ValueError("invalid bounded tracked source path")
        relative = Path(item.decode())
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid tracked source path: {relative}")
        path = ROOT / relative
        tracked.add(path)
        if path.suffix in (".py", ".sh", ".toml") or path in required:
            files.add(path)
    missing_required = sorted(str(path.relative_to(ROOT)) for path in required - tracked)
    if missing_required:
        raise RuntimeError(f"required provenance inputs are not tracked: {missing_required}")

    protocol_files = {
        path.name: path for path in files
        if path.parent == ROOT / "protocol" and path.suffix == ".py"
    }
    vendor_root = ROOT / "bridge/_vendor"
    vendor_protocol = vendor_root / "protocol"
    vendor_init = vendor_root / "__init__.py"
    if (not stat.S_ISDIR(vendor_root.lstat().st_mode)
            or not stat.S_ISDIR(vendor_protocol.lstat().st_mode)
            or not stat.S_ISREG(vendor_init.lstat().st_mode)
            or vendor_init.lstat().st_size != 0):
        raise FileNotFoundError("generated vendored protocol is missing")
    if _bounded_directory_names(vendor_root, deadline, 8) != {"__init__.py", "protocol"}:
        raise AssertionError("vendored root contains an unexpected entry")
    if _bounded_directory_names(
            vendor_protocol, deadline, len(protocol_files) + 1) != set(protocol_files):
        raise AssertionError("vendored protocol file set differs from protocol/")
    vendor_files = {name: vendor_protocol / name for name in protocol_files}
    for name, source in protocol_files.items():
        vendor = vendor_files[name]
        vendor_stat = vendor.lstat()
        if not stat.S_ISREG(vendor_stat.st_mode):
            raise ValueError(f"vendored protocol source is not regular: {vendor}")
        if (_sha256_file(source, deadline=deadline, max_bytes=MAX_SOURCE_FILE_BYTES)
                != _sha256_file(
                    vendor, deadline=deadline, max_bytes=MAX_SOURCE_FILE_BYTES)):
            raise AssertionError(f"vendored protocol content differs: {name}")
    files.add(vendor_init)
    files.update(vendor_files.values())
    if len(files) > MAX_SOURCE_FILES:
        raise RuntimeError("source manifest file-count limit exceeded")
    return files


def _current_provenance(deadline: float) -> dict[str, Any]:
    _remaining(deadline)
    git_status = _git_text(
        deadline, "status", "--porcelain=v1", "--untracked-files=all")
    if git_status:
        raise RuntimeError("formal evidence requires a clean Git worktree")

    required = {ROOT / "pyproject.toml", ROOT / "uv.lock"}
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"provenance inputs missing: {missing}")
    files = _tracked_sources(deadline, required)
    source_files = {}
    total_bytes = 0
    for path in sorted(files):
        raw = _read_bounded_bytes(path, deadline, MAX_SOURCE_FILE_BYTES)
        total_bytes += len(raw)
        if total_bytes > MAX_SOURCE_TOTAL_BYTES:
            raise RuntimeError("source manifest total-byte limit exceeded")
        source_files[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    _, manifest_sha = _canonical(source_files)

    blender_version = subprocess.run(
        [BLENDER, "--version"], check=True, text=True,
        timeout=min(10.0, _remaining(deadline)),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ).stdout.strip()
    _remaining(deadline)
    return {
        "schema_version": 1,
        "git": {
            "head": _git_text(deadline, "rev-parse", "HEAD"),
            "tree": _git_text(deadline, "rev-parse", "HEAD^{tree}"),
            "dirty": False,
            "status_sha256": hashlib.sha256(b"").hexdigest(),
            "status_lines": 0,
        },
        "sources": {
            "files": source_files,
            "file_count": len(source_files),
            "total_bytes": total_bytes,
            "manifest_sha256": manifest_sha,
            "uv_lock_sha256": source_files["uv.lock"],
        },
        "blender": {
            "executable": BLENDER,
            "version_output": blender_version,
            "version_output_sha256": hashlib.sha256(
                blender_version.encode()).hexdigest(),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "mcp_sdk": importlib.metadata.version("mcp"),
        },
        "commands": {
            "mcp_server": [UV, "--directory", str(ROOT), "run", "--frozen",
                           "blender-codex-server"],
            "blender_recovery": [BLENDER, "--factory-startup", "--python-exit-code",
                                 "1", "--python", "smoke/runner.py"],
        },
    }

def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("formal E2E deadline expired")
    return remaining


async def _call_tool(
    client: Client, tool: str, arguments: dict[str, object], deadline: float,
):
    _remaining(deadline)
    async with asyncio.timeout(_remaining(deadline)):
        result = await client.call_tool(tool, arguments)
    _remaining(deadline)
    return result


async def _catalog_baseline(client: Client, deadline: float) -> dict[str, Any]:
    _remaining(deadline)
    async with asyncio.timeout(_remaining(deadline)):
        first = await client.list_tools()
        second = await client.list_tools()
    _remaining(deadline)
    if (first.next_cursor is not None or second.next_cursor is not None
            or first.result_type != "complete"
            or second.result_type != "complete"):
        raise AssertionError("tools/list must be one complete page")
    server_info = client.server_info
    if (server_info is None or server_info.name != FROZEN_SERVER_NAME
            or server_info.version != FROZEN_SERVER_VERSION):
        raise AssertionError("wire server version differs from freeze")
    catalog = [tool.model_dump(
        mode="json", by_alias=True, exclude_none=False) for tool in first.tools]
    repeated = [tool.model_dump(
        mode="json", by_alias=True, exclude_none=False) for tool in second.tools]
    ordered_tools = [item.get("name") for item in catalog]
    if (ordered_tools != EXPECTED_TOOLS
            or not _exact_json_equal(catalog, repeated)):
        raise AssertionError("tools/list catalog or order is not deterministic")
    schemas = [
        {"name": item["name"], "inputSchema": item["inputSchema"],
         "outputSchema": item["outputSchema"]}
        for item in catalog
    ]
    catalog_bytes, catalog_sha = _canonical(catalog)
    schema_bytes, schema_sha = _canonical(schemas)
    instructions = client.instructions
    if type(instructions) is not str or not instructions:
        raise AssertionError("server instructions missing from catalog baseline")
    raw_instructions = instructions.encode("utf-8")
    return {
        "ordered_tools": ordered_tools,
        "server_name": server_info.name,
        "server_version": server_info.version,
        "next_cursor": None,
        "result_type": "complete",
        "ordered_catalog": catalog,
        "ordered_catalog_bytes": catalog_bytes,
        "ordered_catalog_sha256": catalog_sha,
        "schema_bytes": schema_bytes,
        "schema_sha256": schema_sha,
        "instructions": instructions,
        "instructions_utf8_bytes": len(raw_instructions),
        "instructions_sha256": hashlib.sha256(raw_instructions).hexdigest(),
        "stable_repeated_list": True,
    }


def _verify_catalog_baseline(record: dict[str, Any]) -> None:
    expected_keys = {
        "ordered_tools", "server_name", "server_version", "next_cursor", "result_type",
        "ordered_catalog", "ordered_catalog_bytes",
        "ordered_catalog_sha256", "schema_bytes", "schema_sha256",
        "instructions", "instructions_utf8_bytes", "instructions_sha256",
        "stable_repeated_list",
    }
    if (set(record) != expected_keys or record["ordered_tools"] != EXPECTED_TOOLS
            or record["server_name"] != FROZEN_SERVER_NAME
            or record["server_version"] != FROZEN_SERVER_VERSION
            or record["next_cursor"] is not None
            or record["result_type"] != "complete"
            or record["stable_repeated_list"] is not True):
        raise AssertionError("catalog baseline shape or order differs")
    catalog = record["ordered_catalog"]
    if (type(catalog) is not list or len(catalog) != len(EXPECTED_TOOLS)
            or any(type(item) is not dict for item in catalog)
            or [item.get("name") for item in catalog] != EXPECTED_TOOLS
            or any("inputSchema" not in item or "outputSchema" not in item
                   for item in catalog)):
        raise AssertionError("ordered catalog payload differs")
    catalog_bytes, catalog_sha = _canonical(catalog)
    schemas = [
        {"name": item["name"], "inputSchema": item["inputSchema"],
         "outputSchema": item["outputSchema"]}
        for item in catalog
    ]
    schema_bytes, schema_sha = _canonical(schemas)
    instructions = record["instructions"]
    if type(instructions) is not str or not instructions:
        raise AssertionError("catalog instructions missing")
    raw_instructions = instructions.encode("utf-8")
    if (record["ordered_catalog_bytes"] != catalog_bytes
            or record["ordered_catalog_sha256"] != catalog_sha
            or record["schema_bytes"] != schema_bytes
            or record["schema_sha256"] != schema_sha
            or record["instructions_utf8_bytes"] != len(raw_instructions)
            or record["instructions_sha256"]
            != hashlib.sha256(raw_instructions).hexdigest()):
        raise AssertionError("catalog baseline digest differs")
    if (catalog_bytes != FROZEN_CATALOG_BYTES
            or catalog_sha != FROZEN_CATALOG_SHA256
            or schema_bytes != FROZEN_SCHEMA_BYTES
            or schema_sha != FROZEN_COMBINED_SCHEMA_SHA256
            or len(raw_instructions) != FROZEN_INSTRUCTIONS_BYTES
            or hashlib.sha256(raw_instructions).hexdigest()
            != FROZEN_INSTRUCTIONS_SHA256):
        raise AssertionError("catalog baseline differs from Task 17 freeze")


def _compat_text_metrics(
    result: object,
    validated: dict[str, Any],
    validate: Callable[[object], dict[str, Any]],
) -> dict[str, Any]:
    content = getattr(result, "content", None)
    if (type(content) is not list or len(content) != 1
            or getattr(content[0], "type", None) != "text"
            or type(getattr(content[0], "text", None)) is not str):
        raise AssertionError("exactly one compatibility TextContent is required")
    text = content[0].text
    raw_text = _bounded_text_content(text)
    try:
        text_value = _strict_json_loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AssertionError("compatibility TextContent is not JSON") from exc
    text_validated = validate(text_value)
    if (not _exact_json_equal(text_value, text_validated)
            or not _exact_json_equal(text_validated, validated)):
        raise AssertionError("TextContent and structuredContent differ")
    structured_bytes, _structured_sha = _canonical(validated)
    return {
        "text_content": text,
        "text_content_bytes": len(raw_text),
        "text_content_sha256": hashlib.sha256(raw_text).hexdigest(),
        "text_json_equivalent": True,
        "duplication_ratio": round(
            (structured_bytes + len(raw_text)) / structured_bytes, 6),
    }


def _bounded_text_content(text: str) -> bytes:
    # UTF-8 needs at most four bytes per code point, so this bounds the encode
    # allocation before the exact byte limit is checked.
    if len(text) > MAX_SAMPLE_TEXT_BYTES:
        raise ValueError("compatibility TextContent character limit exceeded")
    raw = text.encode("utf-8")
    if len(raw) > MAX_SAMPLE_TEXT_BYTES:
        raise ValueError("compatibility TextContent byte limit exceeded")
    return raw


def _audit_rows(runtime_root: Path, deadline: float) -> list[dict[str, Any]]:
    logs = runtime_root / "logs"
    try:
        logs_stat = logs.lstat()
    except FileNotFoundError:
        return []
    if (not stat.S_ISDIR(logs_stat.st_mode) or logs_stat.st_uid != os.geteuid()
            or stat.S_IMODE(logs_stat.st_mode) != 0o700):
        raise PermissionError(f"private audit directory required: {logs}")
    names = _bounded_directory_names(logs, deadline, MAX_AUDIT_FILES)
    if any(re.fullmatch(r"server-[0-9]{4}-[0-9]{2}-[0-9]{2}\.jsonl", name) is None
           for name in names):
        raise ValueError("audit directory contains an unexpected entry")
    rows: list[dict[str, Any]] = []
    total_bytes = 0
    for name in sorted(names):
        path = logs / name
        file_stat = path.lstat()
        if (not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != os.geteuid()
                or stat.S_IMODE(file_stat.st_mode) != 0o600):
            raise PermissionError(f"private audit file required: {path}")
        raw = _read_bounded_bytes(path, deadline, MAX_AUDIT_FILE_BYTES)
        total_bytes += len(raw)
        if total_bytes > MAX_AUDIT_TOTAL_BYTES:
            raise ValueError("audit bundle exceeds the total byte limit")
        if raw and not raw.endswith(b"\n"):
            raise ValueError(f"audit file has a partial final row: {path}")
        for line in raw.splitlines():
            if len(line) > MAX_AUDIT_LINE_BYTES:
                raise ValueError(f"audit row exceeds its byte limit: {path}")
            row = _strict_json_loads(line)
            if type(row) is not dict:
                raise ValueError(f"audit row is not an object: {path}")
            rows.append(row)
            if len(rows) > MAX_AUDIT_ROWS:
                raise ValueError("audit bundle exceeds the row limit")
    return rows


def _audit_summary(
    rows: list[dict[str, Any]],
    expected: list[tuple[str, dict[str, object], bool, str | None, str | None]],
) -> dict[str, Any]:
    if len(rows) != len(expected):
        raise AssertionError(f"audit row count differs: {len(rows)} != {len(expected)}")
    request_ids = [row.get("request_id") for row in rows]
    if any(value == "<missing>" or type(value) not in (str, int) for value in request_ids):
        raise AssertionError("audit request id missing or malformed")
    if len({(type(value).__name__, value) for value in request_ids}) != len(request_ids):
        raise AssertionError("audit request ids are not unique")
    for index, (row, event) in enumerate(zip(rows, expected, strict=True)):
        tool, arguments, ok, error, instance_id = event
        _, argument_sha = _canonical(arguments)
        if (set(row) != AUDIT_KEYS or row.get("tool") != tool
                or row.get("params_digest") != argument_sha[:16]
                or row.get("ok") is not ok or row.get("error") != error
                or row.get("instance_id") != instance_id
                or row.get("transaction_id") is not None or row.get("paths") != []
                or type(row.get("ts")) is not str
                or type(row.get("duration_ms")) not in (int, float)
                or not math.isfinite(row["duration_ms"])
                or row["duration_ms"] < 0):
            raise AssertionError(f"audit row {index} differs: {row!r} != {event!r}")
    counts = collections.Counter(row["tool"] for row in rows)
    return {
        "rows": len(rows),
        "unique_request_ids": len(request_ids),
        "tool_counts": dict(sorted(counts.items())),
        "ok_rows": sum(row["ok"] is True for row in rows),
        "error_codes": sorted(
            str(row["error"]) for row in rows if row["error"] is not None),
    }


def _validate_status(value: object, instance_id: str) -> dict[str, Any]:
    model = StatusResult.model_validate(value)
    if not model.ok or model.partial or model.skipped_count != 0:
        raise AssertionError(f"status is partial: {model!r}")
    matches = [row for row in model.instances if row.instance_id == instance_id]
    if (len(model.instances) != 1 or len(matches) != 1
            or matches[0].bridge_state != "connected"):
        raise AssertionError(f"connected instance missing: {model!r}")
    return model.model_dump(mode="json")


def _validate_scene(value: object, instance_id: str) -> dict[str, Any]:
    model = SceneSummaryResult.model_validate(value)
    summary = model.summary
    if (model.instance_id != instance_id or summary.object_count != 100_000
            or summary.mesh_count != 100_000 or summary.camera_count != 0
            or summary.light_count != 0 or summary.collections != []
            or summary.managed_objects != []):
        raise AssertionError(f"100k scene result differs: {model!r}")
    return model.model_dump(mode="json")


def _validate_capabilities(value: object) -> dict[str, Any]:
    model = CapabilitiesResult.model_validate(value)
    if (model.phase != "phase0" or model.connected_instances != []
            or model.instances_partial or model.instances_skipped_count != 0
            or model.supported_tools != [
                "get_blender_status", "get_scene_summary", "describe_capabilities"]):
        raise AssertionError(f"offline capabilities result differs: {model!r}")
    return model.model_dump(mode="json")


def _require_bridge_unavailable(data: object) -> dict[str, object]:
    if (type(data) is not dict
            or set(data) != {"code", "retryable"}
            or type(data["code"]) is not str
            or data["code"] != envelope.BRIDGE_UNAVAILABLE
            or type(data["retryable"]) is not bool
            or data["retryable"] is not True):
        raise AssertionError(f"unexpected post-kill error data: {data!r}")
    return {"code": data["code"], "retryable": data["retryable"]}


async def _measure(
    client: Client,
    tool: str,
    arguments: dict[str, object],
    validate: Callable[[object], dict[str, Any]],
    deadline: float,
) -> dict[str, Any]:
    samples = []
    sample_results = []
    representative: dict[str, Any] | None = None
    for _index in range(RUNS):
        _remaining(deadline)
        started = time.perf_counter_ns()
        result = await _call_tool(client, tool, arguments, deadline)
        if result.is_error or result.structured_content is None:
            raise RuntimeError(f"{tool} returned an error or no structuredContent")
        representative = validate(result.structured_content)
        _remaining(deadline)
        duration_ms = round((time.perf_counter_ns() - started) / 1_000_000, 6)
        samples.append(duration_ms)
        result_bytes, result_sha = _canonical(representative)
        if result_bytes > MAX_SAMPLE_RESULT_BYTES:
            raise ValueError(f"{tool} sample result exceeds the 256 KiB limit")
        sample_results.append({
            "duration_ms": duration_ms,
            "result_bytes": result_bytes,
            "result_sha256": result_sha,
            "validated_result": representative,
            **_compat_text_metrics(result, representative, validate),
        })
    ordered = sorted(samples)
    p95_ms = ordered[math.ceil(0.95 * len(ordered)) - 1]
    argument_bytes, argument_sha = _canonical(arguments)
    result_bytes, result_sha = _canonical(representative)
    return {
        "arguments": arguments,
        "arguments_bytes": argument_bytes,
        "arguments_sha256": argument_sha,
        "samples_ms": samples,
        "sample_results": sample_results,
        "p95_method": "nearest_rank",
        "p95_ms": p95_ms,
        "max_ms": ordered[-1],
        "validated": True,
        "representative_result": representative,
        "representative_result_bytes": result_bytes,
        "representative_result_sha256": result_sha,
    }


def _sample_result_total(records: list[dict[str, Any]]) -> int:
    sizes = [
        item["result_bytes"]
        for record in records
        for item in record["sample_results"]
    ]
    if any(type(size) is not int or size < 0 for size in sizes):
        raise AssertionError("measurement sample byte count is invalid")
    total = sum(sizes)
    if total > MAX_SAMPLE_RESULTS_BYTES:
        raise AssertionError("all measurement preimages exceed the 16 MiB limit")
    return total


def _sample_text_total(records: list[dict[str, Any]]) -> int:
    sizes = [
        item["text_content_bytes"]
        for record in records
        for item in record["sample_results"]
    ]
    if any(type(size) is not int or size < 0 for size in sizes):
        raise AssertionError("measurement TextContent byte count is invalid")
    return sum(sizes)


def _verify_measurement_record(
    record: dict[str, Any],
    arguments: dict[str, object],
    validate: Callable[[object], dict[str, Any]],
) -> None:
    expected_keys = {
        "arguments", "arguments_bytes", "arguments_sha256", "samples_ms",
        "sample_results", "p95_method", "p95_ms", "max_ms", "validated",
        "representative_result", "representative_result_bytes",
        "representative_result_sha256",
    }
    if (set(record) != expected_keys
            or not _exact_json_equal(record["arguments"], arguments)):
        raise AssertionError("measurement record keys or arguments differ")
    record_argument_bytes, record_argument_sha = _canonical(record["arguments"])
    argument_bytes, argument_sha = _canonical(arguments)
    if (record["arguments_bytes"] != record_argument_bytes
            or record["arguments_sha256"] != record_argument_sha
            or (record_argument_bytes, record_argument_sha)
            != (argument_bytes, argument_sha)
            or record["p95_method"] != "nearest_rank"
            or record["validated"] is not True):
        raise AssertionError("measurement record metadata differs")
    samples = record["samples_ms"]
    results = record["sample_results"]
    if len(samples) != len(results) != RUNS or len(samples) != RUNS:
        raise AssertionError("measurement sample count differs")
    for duration, item in zip(samples, results, strict=True):
        if (type(duration) not in (int, float) or not math.isfinite(duration)
                or duration < 0 or set(item) != {
                    "duration_ms", "result_bytes", "result_sha256", "validated_result",
                    "text_content", "text_content_bytes", "text_content_sha256",
                    "text_json_equivalent", "duplication_ratio",
                } or item["duration_ms"] != duration):
            raise AssertionError("measurement sample shape differs")
        raw_validated = item["validated_result"]
        validated = validate(raw_validated)
        if not _exact_json_equal(raw_validated, validated):
            raise AssertionError("measurement sample preimage differs after validation")
        result_bytes, result_sha = _canonical(raw_validated)
        if (result_bytes > MAX_SAMPLE_RESULT_BYTES
                or item["result_bytes"] != result_bytes
                or item["result_sha256"] != result_sha):
            raise AssertionError("measurement sample digest differs")
        text = item["text_content"]
        if type(text) is not str:
            raise AssertionError("measurement TextContent differs")
        try:
            raw_text = _bounded_text_content(text)
        except ValueError as exc:
            raise AssertionError(str(exc)) from exc
        try:
            text_value = _strict_json_loads(text)
            text_validated = validate(text_value)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AssertionError("measurement TextContent differs") from exc
        expected_ratio = round(
            (result_bytes + len(raw_text)) / result_bytes, 6)
        if (not _exact_json_equal(text_value, text_validated)
                or not _exact_json_equal(text_validated, validated)
                or item["text_json_equivalent"] is not True
                or item["text_content_bytes"] != len(raw_text)
                or item["text_content_sha256"]
                != hashlib.sha256(raw_text).hexdigest()
                or type(item["duplication_ratio"]) not in (int, float)
                or not math.isfinite(item["duplication_ratio"])
                or item["duplication_ratio"] != expected_ratio):
            raise AssertionError("measurement TextContent digest differs")
    ordered = sorted(samples)
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    aggregates = (record["p95_ms"], record["max_ms"])
    if (any(type(value) not in (int, float)
            or not math.isfinite(value) or value < 0 for value in aggregates)
            or record["p95_ms"] != p95 or record["max_ms"] != ordered[-1]):
        raise AssertionError("measurement aggregate differs")
    raw_representative = record["representative_result"]
    representative = validate(raw_representative)
    if not _exact_json_equal(raw_representative, representative):
        raise AssertionError("measurement representative preimage differs after validation")
    representative_bytes, representative_sha = _canonical(raw_representative)
    if (not _exact_json_equal(
                raw_representative, results[-1]["validated_result"])
            or record["representative_result_bytes"] != representative_bytes
            or record["representative_result_sha256"] != representative_sha):
        raise AssertionError("measurement representative result differs")


async def _run_nfr(
    runtime_root: Path, offline_root: Path, instance_id: str,
    process_registry: Path, registry_marker: str,
    registry_not_before_ns: int, deadline: float,
) -> dict[str, Any]:
    live_before = len(_audit_rows(runtime_root, deadline))
    if live_before != 0:
        raise AssertionError(f"formal NFR root already contains {live_before} audit rows")
    status_args = {"instance_selector": instance_id}
    scene_args = {
        "instance_id": instance_id,
        "include_collections": False,
        "include_managed_objects": False,
    }
    live_record = process_registry / "nfr-live.json"
    live_params, live_publication = _server_params(
        runtime_root, live_record, registry_marker)
    try:
        async with Client(
            stdio_client(live_params), mode="auto",
            read_timeout_seconds=min(READ_TIMEOUT_SECONDS, _remaining(deadline)),
        ) as client:
            read_record(
                live_record, expected_marker=registry_marker,
                not_before_ns=registry_not_before_ns)
            protocol_version = str(client.session.protocol_version)
            live_catalog = await _catalog_baseline(client, deadline)
            status = await _measure(
                client, "get_blender_status", status_args,
                lambda value: _validate_status(value, instance_id), deadline,
            )
            scene = await _measure(
                client, "get_scene_summary", scene_args,
                lambda value: _validate_scene(value, instance_id), deadline,
            )
    finally:
        _retire_record_or_reservation(
            live_record, live_publication, expected_marker=registry_marker,
            not_before_ns=registry_not_before_ns)
    _remaining(deadline)
    live_rows = _audit_rows(runtime_root, deadline)[live_before:]
    live_audit = _audit_summary(
        live_rows,
        ([
            ("get_blender_status", status_args, True, None, None)
            for _index in range(RUNS)
        ] + [
            ("get_scene_summary", scene_args, True, None, instance_id)
            for _index in range(RUNS)
        ]),
    )
    if live_audit["ok_rows"] != RUNS * 2:
        raise AssertionError(f"live audit contains failures: {live_audit!r}")
    _remaining(deadline)

    _require_private_directory(offline_root)
    if any(offline_root.iterdir()):
        raise FileExistsError("formal offline root must start empty")
    capabilities_args = {"include_instances": False}
    offline_record = process_registry / "nfr-offline.json"
    offline_params, offline_publication = _server_params(
        offline_root, offline_record, registry_marker)
    try:
        async with Client(
            stdio_client(offline_params), mode="auto",
            read_timeout_seconds=min(READ_TIMEOUT_SECONDS, _remaining(deadline)),
        ) as client:
            read_record(
                offline_record, expected_marker=registry_marker,
                not_before_ns=registry_not_before_ns)
            offline_protocol = str(client.session.protocol_version)
            offline_catalog = await _catalog_baseline(client, deadline)
            capabilities = await _measure(
                client, "describe_capabilities", capabilities_args,
                _validate_capabilities, deadline,
            )
    finally:
        _retire_record_or_reservation(
            offline_record, offline_publication, expected_marker=registry_marker,
            not_before_ns=registry_not_before_ns)
    _remaining(deadline)
    offline_audit = _audit_summary(
        _audit_rows(offline_root, deadline), [
            ("describe_capabilities", capabilities_args, True, None, None)
            for _index in range(RUNS)
        ])
    if offline_audit["ok_rows"] != RUNS:
        raise AssertionError(f"offline audit contains failures: {offline_audit!r}")
    _remaining(deadline)

    results = {
        "get_blender_status": status,
        "get_scene_summary": scene,
        "describe_capabilities": capabilities,
    }
    if not _exact_json_equal(live_catalog, offline_catalog):
        raise AssertionError("live/offline ordered catalog baseline differs")
    _verify_catalog_baseline(live_catalog)
    _verify_catalog_baseline(offline_catalog)
    _verify_measurement_record(
        status, status_args, lambda value: _validate_status(value, instance_id)
    )
    _verify_measurement_record(
        scene, scene_args, lambda value: _validate_scene(value, instance_id)
    )
    _verify_measurement_record(capabilities, capabilities_args, _validate_capabilities)
    sample_result_bytes = _sample_result_total(list(results.values()))
    sample_text_bytes = _sample_text_total(list(results.values()))
    failures = [
        name for name, record in results.items()
        if len(record["samples_ms"]) != RUNS or record["p95_ms"] >= P95_LIMIT_MS
    ]
    return {
        "success": failures == [],
        "protocol_versions": {"live": protocol_version, "offline": offline_protocol},
        "instance_id": instance_id,
        "sample_count": sum(len(record["samples_ms"]) for record in results.values()),
        "sample_result_bytes": sample_result_bytes,
        "sample_text_content_bytes": sample_text_bytes,
        "sample_dual_content_payload_bytes": sample_result_bytes + sample_text_bytes,
        "p95_limit_ms": P95_LIMIT_MS,
        "failed_tools": failures,
        "catalog": live_catalog,
        "audit": {"live": live_audit, "offline": offline_audit},
        "results": results,
    }


def _start_blender(
    runtime_root: Path,
    ready: Path,
    stop: Path,
    process_record: Path,
    registry_marker: str,
) -> tuple[subprocess.Popen[bytes], tuple[Path, int, int]]:
    reservation, device, inode = reserve_publication(process_record)
    env = os.environ | {
        "BLENDERCODEX_ROOT": str(runtime_root),
        "BLENDERCODEX_RECOVERY_READY": str(ready),
        "BLENDERCODEX_RECOVERY_STOP": str(stop),
    }
    try:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("process_registry.py")),
             REPLACE_MODE,
             str(process_record), str(reservation), str(device), str(inode),
             registry_marker,
             BLENDER, "--factory-startup", "--python-exit-code", "1",
             "--python", "smoke/runner.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except BaseException:
        finish_publication_reservation(reservation, device, inode)
        raise
    return process, (reservation, device, inode)


async def _wait_process(process: subprocess.Popen[bytes], deadline: float) -> int:
    while process.poll() is None:
        if _remaining(deadline) <= 0:
            raise TimeoutError(f"process {process.pid} did not exit")
        await asyncio.sleep(min(0.05, _remaining(deadline)))
    return process.returncode


async def _wait_ready(
    path: Path, process: subprocess.Popen[bytes], deadline: float,
) -> dict[str, Any]:
    while True:
        _remaining(deadline)
        if process.poll() is not None:
            raise RuntimeError(f"Blender exited before ready: {process.returncode}")
        try:
            ready = _read_private_json(
                path, deadline, MAX_RECOVERY_READY_BYTES)
        except FileNotFoundError:
            await asyncio.sleep(min(0.05, _remaining(deadline)))
            continue
        if (type(ready) is dict
                and set(ready) == {"instance_id", "pid"}
                and type(ready["instance_id"]) is str
                and type(ready["pid"]) is int
                and ready["pid"] == process.pid):
            return cast(dict[str, Any], ready)
        raise ValueError(f"malformed recovery ready file: {ready!r}")


def _signal_process_group(process: subprocess.Popen[bytes], sig: int) -> None:
    if process.poll() is not None:
        return
    if os.getpgid(process.pid) != process.pid:
        raise RuntimeError(f"process {process.pid} is not its group leader")
    os.killpg(process.pid, sig)


async def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    _signal_process_group(process, signal.SIGTERM)
    try:
        await _wait_process(process, time.monotonic() + 2.0)
    except TimeoutError:
        _signal_process_group(process, signal.SIGKILL)
        await _wait_process(process, time.monotonic() + 2.0)


async def _run_recovery(
    runtime_root: Path, process_registry: Path, registry_marker: str,
    registry_not_before_ns: int, deadline: float,
) -> dict[str, Any]:
    first: subprocess.Popen[bytes] | None = None
    second: subprocess.Popen[bytes] | None = None
    first_publication: tuple[Path, int, int] | None = None
    second_publication: tuple[Path, int, int] | None = None
    mcp_record = process_registry / "recovery.json"
    first_record = process_registry / "recovery-blender-first.json"
    second_record = process_registry / "recovery-blender-second.json"
    with tempfile.TemporaryDirectory(prefix="bcx-recovery-control-") as temporary:
        control = Path(temporary)
        control.chmod(0o700)
        first_ready, second_ready = control / "first.json", control / "second.json"
        first_stop, second_stop = control / "first.stop", control / "second.stop"
        try:
            first, first_publication = _start_blender(
                runtime_root, first_ready, first_stop,
                first_record, registry_marker)
            initial = await _wait_ready(
                first_ready, first, min(deadline, time.monotonic() + 30.0))
            initial_id = initial["instance_id"]
            audit_before = len(_audit_rows(runtime_root, deadline))
            if audit_before != 0:
                raise AssertionError(
                    f"formal recovery root already contains {audit_before} audit rows")
            initial_args = {"instance_selector": initial_id}
            post_kill_args = {
                "instance_id": initial_id,
                "include_collections": False,
                "include_managed_objects": False,
            }
            restart_attempts = 0
            unavailable_error: dict[str, object] | None = None
            mcp_params, mcp_publication = _server_params(
                runtime_root, mcp_record, registry_marker)
            try:
                async with Client(
                    stdio_client(mcp_params), mode="auto",
                    read_timeout_seconds=min(READ_TIMEOUT_SECONDS, _remaining(deadline)),
                ) as client:
                    mcp_before = read_record(
                        mcp_record, expected_marker=registry_marker,
                        not_before_ns=registry_not_before_ns).evidence()
                    initial_status = await _call_tool(
                        client, "get_blender_status", initial_args, deadline)
                    if initial_status.is_error or initial_status.structured_content is None:
                        raise AssertionError("initial status returned an MCP error")
                    initial_result = _validate_status(
                        initial_status.structured_content, initial_id)

                    _signal_process_group(first, signal.SIGKILL)
                    first_exit = await _wait_process(
                        first, min(deadline, time.monotonic() + 10.0))
                    if first_exit != -signal.SIGKILL:
                        raise AssertionError(
                            f"Blender did not exit from SIGKILL: {first_exit}")
                    try:
                        await _call_tool(
                            client, "get_scene_summary", post_kill_args, deadline)
                    except MCPError as exc:
                        unavailable_error = _require_bridge_unavailable(exc.data)
                    else:
                        raise AssertionError(
                            "post-kill scene summary unexpectedly succeeded")
                    mcp_after_kill = read_record(
                        mcp_record, expected_marker=registry_marker,
                        not_before_ns=registry_not_before_ns).evidence()
                    if mcp_after_kill != mcp_before:
                        raise AssertionError("MCP process identity changed after Blender kill")

                    second, second_publication = _start_blender(
                        runtime_root, second_ready, second_stop,
                        second_record, registry_marker)
                    restarted = await _wait_ready(
                        second_ready, second, min(deadline, time.monotonic() + 30.0))
                    restarted_id = restarted["instance_id"]
                    if restarted_id == initial_id:
                        raise AssertionError(
                            "Blender restart reused the previous instance id")
                    restarted_args = {"instance_selector": restarted_id}
                    while True:
                        _remaining(deadline)
                        if restart_attempts >= MAX_RECOVERY_STATUS_ATTEMPTS:
                            raise RuntimeError("recovery status attempt limit exceeded")
                        restart_attempts += 1
                        status = await _call_tool(
                            client, "get_blender_status", restarted_args, deadline)
                        if status.is_error or status.structured_content is None:
                            raise AssertionError("restart status returned an MCP error")
                        try:
                            restarted_result = _validate_status(
                                status.structured_content, restarted_id)
                        except AssertionError:
                            await asyncio.sleep(min(0.1, _remaining(deadline)))
                            continue
                        _remaining(deadline)
                        break

                    second_stop.touch()
                    second_exit = await _wait_process(
                        second, min(deadline, time.monotonic() + 15.0))
                    if second_exit != 0:
                        raise AssertionError(f"restarted Blender exited {second_exit}")
                    mcp_after_restart = read_record(
                        mcp_record, expected_marker=registry_marker,
                        not_before_ns=registry_not_before_ns).evidence()
                    if mcp_after_restart != mcp_before:
                        raise AssertionError("MCP process identity changed after Blender restart")
            finally:
                _retire_record_or_reservation(
                    mcp_record, mcp_publication, expected_marker=registry_marker,
                    not_before_ns=registry_not_before_ns)
            audit_rows = _audit_rows(runtime_root, deadline)[audit_before:]
            recovery_audit = _audit_summary(
                audit_rows,
                [
                    ("get_blender_status", initial_args, True, None, None),
                    ("get_scene_summary", post_kill_args, False,
                     envelope.BRIDGE_UNAVAILABLE, initial_id),
                ] + [
                    ("get_blender_status", restarted_args, True, None, None)
                    for _index in range(restart_attempts)
                ],
            )
            _remaining(deadline)
            if unavailable_error is None:
                raise AssertionError("post-kill retryable error evidence missing")
            return {
                "success": True,
                "same_mcp_server_session": (
                    mcp_before == mcp_after_kill == mcp_after_restart),
                "mcp_server_identity_before_kill": mcp_before,
                "mcp_server_identity_after_kill": mcp_after_kill,
                "mcp_server_identity_after_restart": mcp_after_restart,
                "initial_instance_id": initial_id,
                "restarted_instance_id": restarted_id,
                "initial_pid": first.pid,
                "restarted_pid": second.pid,
                "first_exit_code": first_exit,
                "second_exit_code": second_exit,
                "bridge_unavailable_error": unavailable_error,
                "initial_status": initial_result,
                "restarted_status": restarted_result,
                "restart_status_attempts": restart_attempts,
                "audit_rows": len(audit_rows),
                "audit": recovery_audit,
            }
        finally:
            if first is not None:
                await _stop_process(first)
                assert first_publication is not None
                _retire_record_or_reservation(
                    first_record, first_publication,
                    expected_marker=registry_marker,
                    not_before_ns=registry_not_before_ns)
            if second is not None:
                await _stop_process(second)
                assert second_publication is not None
                _retire_record_or_reservation(
                    second_record, second_publication,
                    expected_marker=registry_marker,
                    not_before_ns=registry_not_before_ns)


async def _run(
    args: argparse.Namespace, process_registry: Path, deadline: float,
) -> dict[str, Any]:
    runtime_root = Path(args.root)
    if not runtime_root.is_dir():
        raise FileNotFoundError(f"runtime root does not exist: {runtime_root}")
    if args.mode == "nfr":
        return await _run_nfr(
            runtime_root, Path(args.offline_root).resolve(), args.instance,
            process_registry, args.registry_marker,
            args.registry_not_before_ns, deadline)
    return await _run_recovery(
        runtime_root, process_registry, args.registry_marker,
        args.registry_not_before_ns, deadline)


async def _run_bounded(args: argparse.Namespace) -> dict[str, Any]:
    process_registry = Path(args.process_registry).resolve()
    _require_private_directory(process_registry)
    if any(process_registry.iterdir()):
        raise FileExistsError("MCP process registry must start empty")
    deadline = args.deadline
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("formal E2E task missing")
    installed = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, task.cancel)
        except NotImplementedError:  # pragma: no cover - macOS supports this
            continue
        installed.append(sig)
    try:
        async with asyncio.timeout(_remaining(deadline)):
            result = await _run(args, process_registry, deadline)
        _remaining(deadline)
        if any(process_registry.iterdir()):
            raise RuntimeError("MCP process registry is not empty after success")
        return result
    finally:
        for sig in installed:
            loop.remove_signal_handler(sig)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("nfr", "recovery"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--instance")
    parser.add_argument("--offline-root")
    parser.add_argument("--process-registry", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    parser.add_argument("--registry-marker")
    parser.add_argument("--registry-not-before-ns", type=int)
    args = parser.parse_args(argv)
    if args.mode == "nfr" and not args.instance:
        parser.error("nfr mode requires --instance")
    if args.mode == "nfr" and not args.offline_root:
        parser.error("nfr mode requires --offline-root")
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds < 15:
        parser.error("--timeout-seconds must be finite and at least 15")
    return args


def _bounded_failure_error(exc: BaseException) -> str:
    parts: list[str] = []
    total = 0
    visited = 0
    full = False

    def add(name: object, message: str) -> None:
        nonlocal total, full
        if type(name) is not str:
            name = "Exception"
        name = re.sub(r"[^A-Za-z0-9_.]", "_", name[:MAX_FAILURE_TYPE_CHARS]) \
            or "Exception"
        message = message[:MAX_FAILURE_MESSAGE_CHARS]
        part = f"{name}: {message}"
        if total + len(part) + (2 if parts else 0) > MAX_FAILURE_ERROR_CHARS:
            full = True
            return
        parts.append(part)
        total += len(part) + (2 if len(parts) > 1 else 0)
        full = total >= MAX_FAILURE_ERROR_CHARS

    def visit(value: BaseException, depth: int) -> None:
        nonlocal visited
        if full or visited >= MAX_FAILURE_LEAVES:
            return
        if isinstance(value, BaseExceptionGroup):
            if depth >= MAX_FAILURE_GROUP_DEPTH:
                visited += 1
                add("ExceptionGroup", "nested exception depth limit")
                return
            for child in value.exceptions:
                visit(child, depth + 1)
                if full or visited >= MAX_FAILURE_LEAVES:
                    return
            return
        visited += 1
        try:
            name = type(value).__name__
        except BaseException:
            name = "Exception"
        args = BaseException.args.__get__(value, BaseException)
        message = args[0] if type(args) is tuple and len(args) == 1 \
            and type(args[0]) is str \
            else "message omitted"
        add(name, message)

    visit(exc, 0)
    if not parts:
        return "failure diagnostics unavailable"[:MAX_FAILURE_ERROR_CHARS]
    return "; ".join(parts)


def _worker_main(args: argparse.Namespace) -> int:
    if (type(args.registry_marker) is not str
            or re.fullmatch(r"[0-9a-f]{32}", args.registry_marker) is None
            or type(args.registry_not_before_ns) is not int
            or args.registry_not_before_ns <= 0):
        raise ValueError("worker requires a valid registry marker and start time")
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "mode": args.mode,
        "started_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "mcp_sdk": importlib.metadata.version("mcp"),
        },
        "success": False,
    }
    args.deadline = time.monotonic() + args.timeout_seconds
    try:
        artifact["provenance"] = _current_provenance(args.deadline)
        artifact.update(asyncio.run(_run_bounded(args)))
    except asyncio.CancelledError:
        artifact["error"] = "CancelledError: termination requested"
    except BaseExceptionGroup as exc:
        artifact["error"] = _bounded_failure_error(exc)
    except Exception as exc:
        artifact["error"] = _bounded_failure_error(exc)
    artifact["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()
    _write_artifact(Path(args.output), artifact)
    return 0 if artifact["success"] else 1


def _recovery_worker_command(
    args: argparse.Namespace, marker: str, not_before_ns: int,
) -> list[str]:
    return [
        sys.executable, str(Path(__file__).resolve()), WORKER_MODE, "recovery",
        "--root", args.root, "--output", args.output,
        "--process-registry", args.process_registry,
        "--timeout-seconds", str(args.timeout_seconds),
        "--registry-marker", marker,
        "--registry-not-before-ns", str(not_before_ns),
    ]


def _supervise_recovery(args: argparse.Namespace) -> int:
    registry = Path(args.process_registry).resolve()
    _require_private_directory(registry)
    if any(registry.iterdir()):
        raise FileExistsError("recovery process registry must start empty")
    marker = new_marker()
    not_before_ns = time.monotonic_ns()
    started = time.monotonic()
    worker_deadline = started + args.timeout_seconds
    cleanup_deadline = worker_deadline + RECOVERY_CLEANUP_MARGIN
    registry_reserve = min(
        RECOVERY_REGISTRY_RESERVE, RECOVERY_CLEANUP_MARGIN / 3.0)
    command = _recovery_worker_command(args, marker, not_before_ns)
    outer_temporary = tempfile.TemporaryDirectory(
        prefix="bcx-recovery-supervisor-")
    outer_registry = Path(outer_temporary.name)
    outer_registry.chmod(0o700)
    worker_record = outer_registry / "recovery-worker.json"
    process: subprocess.Popen[bytes] | None = None
    publication: tuple[Path, int, int] | None = None
    returncode: int | None = None
    supervisor_error: str | None = None
    timed_out = False
    cancelled_signal: int | None = None
    previous_handlers: dict[int, Any] = {}
    known_records: dict[int, ProcessRecord] = {}
    known_outer_records: dict[int, ProcessRecord] = {}

    def cancel(signum: int, _frame: object) -> None:
        nonlocal cancelled_signal
        if cancelled_signal is None:
            cancelled_signal = signum

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, cancel)
        if cancelled_signal is None:
            publication = reserve_publication(worker_record)
            reservation, device, inode = publication
            wrapped = [
                sys.executable,
                str(Path(__file__).with_name("process_registry.py")),
                REPLACE_MODE,
                str(worker_record), str(reservation), str(device), str(inode),
                marker, *command,
            ]
            try:
                process = subprocess.Popen(wrapped, start_new_session=True)
            except BaseException:
                finish_publication_reservation(*publication)
                raise
        while process is not None:
            scan_records(
                outer_registry, expected_marker=marker,
                not_before_ns=not_before_ns, deadline=cleanup_deadline,
                known_records=known_outer_records, retire_dead=False)
            scan_records(
                registry, expected_marker=marker,
                not_before_ns=not_before_ns, deadline=cleanup_deadline,
                known_records=known_records,
                retire_dead=False)
            if cancelled_signal is not None:
                supervisor_error = (
                    f"recovery supervisor cancelled by signal {cancelled_signal}")
                break
            polled, deadline_expired = poll_before_deadline(
                process.poll, worker_deadline)
            if cancelled_signal is not None:
                supervisor_error = (
                    f"recovery supervisor cancelled by signal {cancelled_signal}")
                break
            if deadline_expired:
                timed_out = True
                supervisor_error = "recovery worker exceeded its absolute deadline"
                returncode = polled
                break
            if polled is not None:
                returncode = polled
                break
            time.sleep(min(0.05, max(0.0, worker_deadline - time.monotonic())))
        if process is None and cancelled_signal is not None:
            supervisor_error = f"recovery supervisor cancelled by signal {cancelled_signal}"
    except Exception as exc:
        detail = f"worker supervision failed: {type(exc).__name__}: {exc}"
        supervisor_error = (
            detail if supervisor_error is None else f"{supervisor_error}; {detail}")
    finally:
        if process is not None:
            try:
                worker_cleanup_deadline = cleanup_deadline - registry_reserve
                record = known_outer_records.get(process.pid)
                if record is None:
                    cleanup_started = time.monotonic()
                    cleanup_remaining = max(
                        0.0, worker_cleanup_deadline - cleanup_started)
                    publication_deadline = cleanup_started + min(
                        0.1, cleanup_remaining / 2.0)
                    try:
                        record = wait_owned_process_record(
                            process, worker_record, expected_marker=marker,
                            not_before_ns=not_before_ns,
                            deadline=publication_deadline)
                    except Exception:
                        returncode = cleanup_unpublished_process(
                            process, deadline=worker_cleanup_deadline,
                            term_grace=min(0.25, cleanup_remaining / 2.0))
                        if publication is None:
                            raise RuntimeError(
                                "recovery worker publication identity missing")
                        _retire_record_or_reservation(
                            worker_record, publication,
                            expected_marker=marker,
                            not_before_ns=not_before_ns)
                        raise
                if record.path != worker_record:
                    raise RuntimeError("recovery worker record path differs")
                if process.poll() is not None and recorded_group_is_live(record):
                    if supervisor_error is None:
                        supervisor_error = "recovery worker group survived its leader"
                returncode = cleanup_owned_process(
                    process, record, deadline=worker_cleanup_deadline,
                    term_grace=RECOVERY_WORKER_TERM_GRACE)
                retire_record(
                    worker_record, expected_marker=marker,
                    not_before_ns=not_before_ns)
            except Exception as exc:
                detail = f"worker cleanup failed: {type(exc).__name__}: {exc}"
                supervisor_error = (
                    detail if supervisor_error is None
                    else f"{supervisor_error}; {detail}")
        try:
            cleanup_registry(
                registry, expected_marker=marker, not_before_ns=not_before_ns,
                deadline=cleanup_deadline, term_grace=RECOVERY_GROUP_TERM_GRACE,
                known_records=known_records)
        except Exception as exc:
            detail = f"registry cleanup failed: {type(exc).__name__}: {exc}"
            supervisor_error = (
                detail if supervisor_error is None else f"{supervisor_error}; {detail}")
        finally:
            for signum, previous in previous_handlers.items():
                signal.signal(signum, previous)
            outer_temporary.cleanup()
            if cancelled_signal is not None and supervisor_error is None:
                supervisor_error = (
                    f"recovery supervisor cancelled by signal {cancelled_signal}")
    if supervisor_error is not None:
        output = Path(args.output)
        _write_artifact(output, {
            "schema_version": 1,
            "mode": "recovery",
            "success": False,
            "worker_timed_out": timed_out,
            "worker_cancelled_signal": cancelled_signal,
            "worker_returncode": returncode,
            "error": f"supervisor failed: {supervisor_error}",
            "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        })
        return 1
    return 1 if returncode is None else returncode


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == WORKER_MODE:
        raise SystemExit(_worker_main(_parse_args(sys.argv[2:])))
    args = _parse_args(sys.argv[1:])
    if args.mode == "recovery":
        raise SystemExit(_supervise_recovery(args))
    if args.registry_marker is None or args.registry_not_before_ns is None:
        raise ValueError("nfr mode requires runner-provided registry identity")
    raise SystemExit(_worker_main(args))


if __name__ == "__main__":
    main()
