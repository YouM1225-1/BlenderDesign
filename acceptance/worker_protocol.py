from __future__ import annotations

from typing import Any, cast

import json
import os
import re
import stat
from pathlib import Path

from acceptance.canonical import CanonicalError, canonicalize
from acceptance.input_bundle import (
    measure_file,
    open_parent,
    read_bounded,
    relative_path,
    safe_open,
    valid_id,
)
from acceptance.primitives import AcceptanceFailure
from acceptance.strict_json import strict_json_loads

IDENTITY = (
    "schema_version",
    "run_id",
    "attempt",
    "nonce",
    "job_id",
    "writer",
    "contract_digest",
    "source_digest",
)
_REQUEST = set(IDENTITY) | {"input_root", "inputs", "output_root", "outputs", "parameters"}
_RESULT = set(IDENTITY) | {"checks", "artifacts", "observations"}
_MEDIA = {
    "application/json",
    "image/png",
    "model/gltf-binary",
    "application/octet-stream",
    "text/plain",
}
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def ensure(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rel(value: Any) -> str:
    try:
        return relative_path(value)
    except AcceptanceFailure as exc:
        raise ValueError(f"invalid artifact path: {exc}") from exc


def read_json(path: Path, max_bytes: int = 1048576) -> Any:
    try:
        raw = read_bounded(path, max_bytes)
        return strict_json_loads(raw.decode("utf-8"))
    except (AcceptanceFailure, OSError) as exc:
        raise ValueError(f"invalid JSON file: {exc}") from exc


def check_identity(value: Any) -> None:
    ensure(type(value) is dict and all(key in value for key in IDENTITY), "identity required")
    ensure(
        type(value["schema_version"]) is int and value["schema_version"] == 2,
        "schema must be 2",
    )
    ensure(type(value["attempt"]) is int and value["attempt"] >= 1, "attempt must be positive int")
    ensure(
        all(type(value[key]) is str and value[key] for key in ("run_id", "job_id", "writer")),
        "invalid identity strings",
    )
    ensure(
        type(value["nonce"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["nonce"]) is not None,
        "invalid nonce",
    )
    ensure(
        all(
            type(value[key]) is str and _HEX.fullmatch(value[key]) is not None
            for key in ("contract_digest", "source_digest")
        ),
        "invalid digest",
    )


def artifact(path: Path, file_id: str, relative: str, max_bytes: int) -> dict[str, Any]:
    try:
        measured = measure_file(path, max_bytes, file_id=file_id)
        return measured.descriptor(relative)
    except (AcceptanceFailure, OSError) as exc:
        raise ValueError(f"invalid artifact: {exc}") from exc


def _input_descriptor(row: Any) -> dict[str, Any]:
    ensure(
        type(row) is dict and set(row) == {"id", "path", "bytes", "sha256"},
        "invalid input descriptor",
    )
    ensure(valid_id(row["id"]), "invalid input id")
    rel(row["path"])
    ensure(type(row["bytes"]) is int and row["bytes"] >= 0, "invalid input size")
    ensure(
        type(row["sha256"]) is str and _HEX.fullmatch(row["sha256"]) is not None,
        "invalid input digest",
    )
    return cast(dict[str, Any], row)


def _output_descriptor(row: Any) -> dict[str, Any]:
    ensure(
        type(row) is dict and set(row) == {"id", "path", "media_type", "max_bytes"},
        "invalid output descriptor",
    )
    ensure(valid_id(row["id"]), "invalid output id")
    path = rel(row["path"])
    ensure(path != "result.json", "reserved result path")
    ensure(
        type(row["media_type"]) is str and row["media_type"] in _MEDIA,
        "invalid output media type",
    )
    ensure(type(row["max_bytes"]) is int and row["max_bytes"] > 0, "invalid output budget")
    return cast(dict[str, Any], row)


def _artifact_descriptor(row: Any) -> dict[str, Any]:
    ensure(
        type(row) is dict and set(row) == {"id", "path", "bytes", "sha256"},
        "closed artifact required",
    )
    ensure(valid_id(row["id"]), "invalid artifact id")
    rel(row["path"])
    ensure(
        type(row["bytes"]) is int
        and row["bytes"] >= 0
        and type(row["sha256"]) is str
        and _HEX.fullmatch(row["sha256"]) is not None,
        "bad artifact identity",
    )
    return cast(dict[str, Any], row)


def _root(value: Any) -> tuple[Path, tuple[int, int]]:
    ensure(type(value) is str and Path(value).is_absolute(), "absolute root required")
    path = Path(value)
    ensure(".." not in path.parts, "root cannot contain '..'")
    descriptor = -1
    try:
        descriptor, _ = open_parent(path / "__worker_entry__")
        info = os.fstat(descriptor)
        ensure(stat.S_ISDIR(info.st_mode), "root must be a directory")
        return path, (info.st_dev, info.st_ino)
    except (AcceptanceFailure, OSError) as exc:
        raise ValueError(f"invalid no-link root: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _check_output_parent(root: Path, relative: str) -> None:
    descriptor = -1
    try:
        descriptor, _ = open_parent(root / "__worker_entry__")
        for segment in relative.split("/")[:-1]:
            try:
                next_descriptor = os.open(
                    segment,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                return
            os.close(descriptor)
            descriptor = next_descriptor
    except (AcceptanceFailure, OSError) as exc:
        raise ValueError(f"invalid output path component: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _unique(rows: list[dict[str, Any]], label: str) -> None:
    ensure(
        len({row["id"] for row in rows}) == len(rows)
        and len({row["path"] for row in rows}) == len(rows),
        f"duplicate {label}",
    )


def read_request(path: Path) -> dict[str, Any]:
    value = read_json(path)
    ensure(type(value) is dict and set(value) == _REQUEST, "closed request required")
    check_identity(value)
    ensure(type(value["parameters"]) is dict, "parameters must be object")
    try:
        canonicalize(value["parameters"])
    except CanonicalError as exc:
        raise ValueError(f"parameters must be canonical JSON: {exc}") from exc
    ensure(type(value["inputs"]) is list and type(value["outputs"]) is list, "file lists required")
    inputs = [_input_descriptor(row) for row in value["inputs"]]
    outputs = [_output_descriptor(row) for row in value["outputs"]]
    _unique(inputs, "input")
    _unique(outputs, "output")
    input_root, input_identity = _root(value["input_root"])
    output_root, output_identity = _root(value["output_root"])
    ensure(
        input_identity != output_identity
        and input_root != output_root
        and input_root not in output_root.parents
        and output_root not in input_root.parents,
        "input/output roots overlap",
    )
    for row in inputs:
        measured = artifact(input_root / row["path"], row["id"], row["path"], row["bytes"])
        ensure(measured == row, "input identity mismatch")
    for row in outputs:
        _check_output_parent(output_root, row["path"])
    return cast(dict[str, Any], value)


def _metric_map(value: Any) -> bool:
    if type(value) is not dict:
        return False
    for key, metric in value.items():
        if type(key) is not str or not (
            metric is None or type(metric) in (str, bool, int, float)
        ):
            return False
        if type(metric) in (int, float):
            try:
                canonicalize(metric)
            except CanonicalError:
                return False
    return True


def validate_result(
    result: Any, request: dict[str, Any], check_ids: tuple[str, ...]
) -> dict[str, Any]:
    ensure(type(result) is dict and set(result) == _RESULT, "closed result required")
    check_identity(result)
    ensure(type(request) is dict and all(key in request for key in IDENTITY), "request identity required")
    ensure(all(result[key] == request[key] for key in IDENTITY), "stale or wrong result identity")
    ensure(
        type(check_ids) is tuple and all(valid_id(check_id) for check_id in check_ids),
        "controller check ids must be an exact tuple",
    )
    ensure(type(result["checks"]) is list, "checks must be a list")
    seen: list[str] = []
    for check in result["checks"]:
        ensure(
            type(check) is dict and set(check) == {"id", "findings", "metrics"},
            "closed check required",
        )
        ensure(valid_id(check["id"]), "invalid check id")
        seen.append(check["id"])
        ensure(_metric_map(check["metrics"]), "metrics must be finite scalars")
        ensure(type(check["findings"]) is list, "findings must be a list")
        for finding in check["findings"]:
            ensure(
                type(finding) is dict
                and set(finding) == {"code", "severity", "pointer", "detail"},
                "closed finding required",
            )
            ensure(
                type(finding["code"]) is str
                and bool(finding["code"])
                and type(finding["severity"]) is str
                and finding["severity"] in ("error", "warning", "info"),
                "invalid finding",
            )
            ensure(
                all(finding[key] is None or type(finding[key]) is str for key in ("pointer", "detail")),
                "invalid finding text",
            )
    ensure(
        len(set(seen)) == len(seen) and set(seen) == set(check_ids),
        "check set or writer mismatch",
    )
    ensure(type(result["artifacts"]) is list, "artifacts must be a list")
    ensure(type(request.get("outputs")) is list, "request outputs must be a list")
    expected_rows = [_output_descriptor(row) for row in request["outputs"]]
    _unique(expected_rows, "output")
    actual = [_artifact_descriptor(row) for row in result["artifacts"]]
    _unique(actual, "artifact")
    expected = {row["id"]: row for row in expected_rows}
    ensure(len(actual) == len(expected), "artifact set mismatch")
    for row in actual:
        ensure(
            row["id"] in expected and row["path"] == expected[row["id"]]["path"],
            "wrong artifact id/path",
        )
        ensure(row["bytes"] <= expected[row["id"]]["max_bytes"], "bad artifact identity")
    ensure(
        type(result["observations"]) is dict
        and all(
            type(key) is str and type(value) is str
            for key, value in result["observations"].items()
        ),
        "observations must be string map",
    )
    return cast(dict[str, Any], result)


def write_result(
    request: dict[str, Any], checks: list[dict[str, Any]], observations: dict[str, str]
) -> Path:
    ensure(type(request) is dict, "request must be an object")
    check_identity(request)
    ensure(type(request.get("outputs")) is list, "request outputs must be a list")
    root, _ = _root(request.get("output_root"))
    outputs = [_output_descriptor(row) for row in request["outputs"]]
    _unique(outputs, "output")
    result = {key: request[key] for key in IDENTITY}
    result.update(
        checks=checks,
        observations=observations,
        artifacts=[
            artifact(root / row["path"], row["id"], row["path"], row["max_bytes"])
            for row in outputs
        ],
    )
    validate_result(result, request, tuple(row["id"] for row in checks))
    path = root / "result.json"
    try:
        descriptor = safe_open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except (AcceptanceFailure, OSError) as exc:
        raise ValueError(f"cannot write result: {exc}") from exc
    return path
