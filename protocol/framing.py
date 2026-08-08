"""线格式：4 字节大端 uint32 长度前缀 + UTF-8 JSON 载荷。spec §3.2。"""
from __future__ import annotations

import struct

MAX_FRAME = 16 * 1024 * 1024
_HEADER = struct.Struct(">I")


class FrameError(Exception):
    pass


class FrameTooLarge(FrameError):
    pass


def encode_frame(payload: bytes) -> bytes:
    if len(payload) > MAX_FRAME:
        raise FrameTooLarge(f"frame {len(payload)} > {MAX_FRAME}")
    return _HEADER.pack(len(payload)) + payload


class FrameBuffer:
    """每连接一个。凑满「头 + length 字节」才切帧——NFR-R3 的非阻塞落法（§3.7 规则 1）。"""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self._buf += data
        frames: list[bytes] = []
        while len(self._buf) >= _HEADER.size:
            (length,) = _HEADER.unpack_from(self._buf)
            if length > MAX_FRAME:
                raise FrameTooLarge(f"declared {length} > {MAX_FRAME}")
            if len(self._buf) < _HEADER.size + length:
                break
            frames.append(bytes(self._buf[_HEADER.size : _HEADER.size + length]))
            del self._buf[: _HEADER.size + length]
        return frames

    @property
    def pending(self) -> int:
        return len(self._buf)
