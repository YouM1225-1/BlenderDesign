"""Synchronous Unix-socket client for the local Blender bridge."""
from __future__ import annotations

import errno
import selectors
import socket
import time
from collections.abc import Callable
from typing import Any

from protocol import envelope, framing

CANCELLATION_POLL_INTERVAL = 0.05


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
             timeout: float | None = None, *,
             deadline: float | None = None,
             check_cancelled: Callable[[], None] | None = None) -> dict[str, Any]:
        budget = envelope.METHOD_TIMEOUTS.get(method, 2.0) if timeout is None else timeout
        relative_deadline = time.monotonic() + budget
        deadline = (relative_deadline if deadline is None
                    else min(relative_deadline, deadline))
        self._check_deadline(deadline)
        if check_cancelled is not None:
            check_cancelled()

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                self._connect(client, deadline, check_cancelled)
                self._check_deadline(deadline)
                request = envelope.Request.new(
                    self._token, method, params if params is not None else {},
                    budget_ms=self._remaining_budget_ms(deadline),
                )
                frame = envelope.encode_request(request)
                self._check_deadline(deadline)
                self._send(client, frame, deadline, check_cancelled)
                self._check_deadline(deadline)
                payload = self._receive(client, deadline, check_cancelled)
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

    @staticmethod
    def _remaining_budget_ms(deadline: float) -> int:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BridgeError(envelope.BRIDGE_TIMEOUT, "request timed out", retryable=True)
        return min(envelope.MAX_REQUEST_BUDGET_MS,
                   max(1, int(remaining * 1000)))

    @classmethod
    def _set_deadline(cls, client: socket.socket, deadline: float,
                      poll: bool = False) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BridgeError(envelope.BRIDGE_TIMEOUT, "request timed out", retryable=True)
        client.settimeout(min(remaining, CANCELLATION_POLL_INTERVAL) if poll else remaining)

    def _connect(self, client: socket.socket, deadline: float,
                 check_cancelled: Callable[[], None] | None) -> None:
        client.setblocking(False)
        while True:
            if check_cancelled is not None:
                check_cancelled()
            self._check_deadline(deadline)
            try:
                client.connect(self._socket_path)
                return
            except BlockingIOError as exc:
                if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # A full AF_UNIX backlog has not started connecting (Linux).
                    time.sleep(min(CANCELLATION_POLL_INTERVAL,
                                   max(0.0, deadline - time.monotonic())))
                    continue
                if exc.errno != errno.EINPROGRESS:
                    raise
            with selectors.DefaultSelector() as selector:
                selector.register(client, selectors.EVENT_WRITE)
                while True:
                    if check_cancelled is not None:
                        check_cancelled()
                    self._check_deadline(deadline)
                    remaining = max(0.0, deadline - time.monotonic())
                    if selector.select(min(remaining, CANCELLATION_POLL_INTERVAL)):
                        error = client.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                        if error:
                            raise OSError(error, "bridge connection failed")
                        return

    @classmethod
    def _send(cls, client: socket.socket, frame: bytes, deadline: float,
              check_cancelled: Callable[[], None] | None) -> None:
        pending = memoryview(frame)
        while pending:
            if check_cancelled is not None:
                check_cancelled()
            cls._set_deadline(client, deadline, poll=check_cancelled is not None)
            try:
                sent = client.send(pending)
            except socket.timeout:
                cls._check_deadline(deadline)
                continue
            if not sent:
                raise BridgeError(envelope.BRIDGE_UNAVAILABLE, "bridge unavailable", retryable=True)
            pending = pending[sent:]

    @classmethod
    def _receive(cls, client: socket.socket, deadline: float,
                 check_cancelled: Callable[[], None] | None = None) -> bytes:
        buffer = framing.FrameBuffer()
        while True:
            if check_cancelled is not None:
                check_cancelled()
            cls._set_deadline(client, deadline, poll=check_cancelled is not None)
            try:
                data = client.recv(65536)
            except socket.timeout:
                cls._check_deadline(deadline)
                continue
            if check_cancelled is not None:
                check_cancelled()
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
