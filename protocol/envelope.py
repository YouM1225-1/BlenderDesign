"""请求/响应信封 + 错误码 + method 超时表。spec §3.3、§4.2。只准相对导入。"""
from __future__ import annotations

import json
import logging
import math
import uuid
from collections.abc import Generator
from dataclasses import asdict, dataclass
from typing import Any, NoReturn

from . import framing

_log = logging.getLogger("bcx.protocol")

ENVELOPE_VERSION = 1
MAX_REQUEST_TEXT_BYTES = 1024

METHOD_TIMEOUTS: dict[str, float] = {"ping": 2.0, "status": 2.0, "scene_summary": 15.0}

UNKNOWN_METHOD = "UNKNOWN_METHOD"
BRIDGE_BUSY = "BRIDGE_BUSY"
SCENE_QUERY_FAILED = "SCENE_QUERY_FAILED"
INTERNAL_LIMIT_EXCEEDED = "INTERNAL_LIMIT_EXCEEDED"
ENVELOPE_VERSION_MISMATCH = "ENVELOPE_VERSION_MISMATCH"
INSTANCE_NOT_FOUND = "INSTANCE_NOT_FOUND"
BRIDGE_UNAVAILABLE = "BRIDGE_UNAVAILABLE"
BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"


@dataclass(frozen=True)
class Request:
    id: str
    token: str
    method: str
    params: dict[str, Any]
    v: int = ENVELOPE_VERSION

    @classmethod
    def new(cls, token: str, method: str, params: dict[str, Any]) -> "Request":
        return cls(id=str(uuid.uuid4()), token=token, method=method, params=params)


def encode_request(req: Request) -> bytes:
    return framing.encode_frame(
        json.dumps(asdict(req), ensure_ascii=False, allow_nan=False).encode("utf-8"))


def _valid_text_field(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return len(value.encode("utf-8")) <= MAX_REQUEST_TEXT_BYTES
    except UnicodeEncodeError:
        return False


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON constant: {value}")


def _parse_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite JSON number")
    return result


def _load_json(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"), parse_constant=_reject_constant,
                          parse_float=_parse_float)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as e:
        raise ValueError(f"bad JSON payload: {e}") from e


def decode_request(payload: bytes) -> Request:
    raw = _load_json(payload)
    if not isinstance(raw, dict):
        raise ValueError("request must be an object")
    try:
        req = Request(
            id=raw["id"], token=raw["token"], method=raw["method"],
            params=raw["params"], v=raw.get("v", ENVELOPE_VERSION),
        )
    except KeyError as e:
        raise ValueError(f"missing field {e}") from e
    if not (_valid_text_field(req.id) and _valid_text_field(req.token)
            and _valid_text_field(req.method) and isinstance(req.params, dict)
            and type(req.v) is int and req.v == ENVELOPE_VERSION):
        raise ValueError("field type mismatch")
    return req


def error_frame(request_id: str, code: str, message: str, retryable: bool = False) -> bytes:
    body = {"v": ENVELOPE_VERSION, "id": request_id, "ok": False,
            "error": {"code": code, "message": message, "retryable": retryable}}
    return framing.encode_frame(
        json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"))


def ok_frame_steps(request_id: str,
                   result: dict[str, Any]) -> Generator[None, None, bytes]:
    """Cooperatively JSON-encode a success frame, yielding between encoder pieces."""
    body = {"v": ENVELOPE_VERSION, "id": request_id, "ok": True, "result": result}
    payload = bytearray()
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False)
    for piece in encoder.iterencode(body):
        encoded = piece.encode("utf-8")
        if len(payload) + len(encoded) > framing.MAX_FRAME:
            _log.warning("response exceeds frame limit (request %s)", request_id)
            return error_frame(request_id, INTERNAL_LIMIT_EXCEEDED,
                               f"response exceeds {framing.MAX_FRAME} bytes")
        payload.extend(encoded)
        yield
    return framing.encode_frame(bytes(payload))


def ok_frame(request_id: str, result: dict[str, Any]) -> bytes:
    """Synchronous convenience for small ping/status responses and existing callers."""
    steps = ok_frame_steps(request_id, result)
    while True:
        try:
            next(steps)
        except StopIteration as done:
            if not isinstance(done.value, bytes):
                raise TypeError("ok_frame_steps must return bytes")
            return done.value


def decode_response(payload: bytes) -> dict[str, Any]:
    raw = _load_json(payload)
    if not isinstance(raw, dict) or "ok" not in raw:
        raise ValueError("bad response")
    return raw
