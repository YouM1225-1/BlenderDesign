"""Synchronous Unix-socket client for the local Blender bridge."""
from __future__ import annotations

import socket
import time
from typing import Any

from protocol import envelope, framing


class BridgeError(Exception):
    def __init__(self, code: str, detail: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.retryable = retryable


class BridgeClient:
    def __init__(self, session: dict[str, Any]) -> None:
        self._socket_path = session["socket_path"]
        self._token = session["token"]

    def call(self, method: str, params: dict[str, Any] | None = None,
             timeout: float | None = None) -> dict[str, Any]:
        budget = envelope.METHOD_TIMEOUTS.get(method, 2.0) if timeout is None else timeout
        deadline = time.monotonic() + budget
        self._check_deadline(deadline)
        request = envelope.Request.new(self._token, method, params if params is not None else {})
        frame = envelope.encode_request(request)
        self._check_deadline(deadline)

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                self._set_deadline(client, deadline)
                client.connect(self._socket_path)
                self._check_deadline(deadline)
                self._set_deadline(client, deadline)
                client.sendall(frame)
                self._check_deadline(deadline)
                payload = self._receive(client, deadline)
        except (socket.timeout, TimeoutError) as exc:
            raise BridgeError(envelope.BRIDGE_TIMEOUT, "request timed out", retryable=True) from exc
        except OSError as exc:
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "bridge unavailable", retryable=True) from exc

        try:
            response = envelope.decode_response(payload)
        except ValueError as exc:
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed response", retryable=True) from exc
        self._check_deadline(deadline)
        return self._response_result(response, request.id)

    @staticmethod
    def _check_deadline(deadline: float) -> None:
        if time.monotonic() >= deadline:
            raise BridgeError(envelope.BRIDGE_TIMEOUT, "request timed out", retryable=True)

    @classmethod
    def _set_deadline(cls, client: socket.socket, deadline: float) -> None:
        cls._check_deadline(deadline)
        client.settimeout(deadline - time.monotonic())

    @classmethod
    def _receive(cls, client: socket.socket, deadline: float) -> bytes:
        buffer = framing.FrameBuffer()
        while True:
            cls._set_deadline(client, deadline)
            data = client.recv(65536)
            cls._check_deadline(deadline)
            if not data:
                raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "bridge unavailable", retryable=True)
            try:
                frames = buffer.feed(data)
            except framing.FrameError as exc:
                raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed response", retryable=True) from exc
            cls._check_deadline(deadline)
            if frames:
                return frames[0]

    @staticmethod
    def _response_result(response: dict[str, Any], request_id: str) -> dict[str, Any]:
        version = response.get("v")
        if type(version) is int and version != envelope.ENVELOPE_VERSION:
            raise BridgeError(envelope.ENVELOPE_VERSION_MISMATCH, "envelope version mismatch")
        if (type(version) is not int or version != envelope.ENVELOPE_VERSION
                or type(response.get("id")) is not str or response["id"] != request_id
                or type(response.get("ok")) is not bool):
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed response", retryable=True)
        if response["ok"]:
            result = response.get("result")
            if set(response) != {"v", "id", "ok", "result"} or type(result) is not dict:
                raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed response", retryable=True)
            return result
        error = response.get("error")
        if (set(response) != {"v", "id", "ok", "error"} or type(error) is not dict
                or type(error.get("code")) is not str
                or type(error.get("message")) is not str
                or type(error.get("retryable")) is not bool):
            raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "malformed response", retryable=True)
        raise BridgeError(error["code"], error["message"], retryable=error["retryable"])
