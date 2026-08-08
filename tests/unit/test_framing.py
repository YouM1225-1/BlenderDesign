import pytest
import struct
from protocol.framing import MAX_FRAME, FrameBuffer, FrameTooLarge, encode_frame


def test_encode_prepends_big_endian_length():
    assert encode_frame(b"abc") == b"\x00\x00\x00\x03abc"


def test_encode_rejects_oversize():
    with pytest.raises(FrameTooLarge):
        encode_frame(b"x" * (MAX_FRAME + 1))


def test_feed_accumulates_partial_reads():
    buf = FrameBuffer()
    frame = encode_frame(b"hello")
    assert buf.feed(frame[:3]) == []          # 连长度头都不完整
    assert buf.feed(frame[3:6]) == []         # 头齐了、载荷不齐
    assert buf.feed(frame[6:]) == [b"hello"]  # 凑满出帧
    assert buf.pending == 0


def test_feed_splits_coalesced_frames():
    buf = FrameBuffer()
    data = encode_frame(b"a") + encode_frame(b"bb") + encode_frame(b"c")[:2]
    assert buf.feed(data) == [b"a", b"bb"]
    assert buf.pending == 2                   # 残留半个头


def test_feed_rejects_oversize_header_without_buffering():
    buf = FrameBuffer()
    with pytest.raises(FrameTooLarge):
        buf.feed(struct.pack(">I", MAX_FRAME + 1))


def test_five_mib_roundtrip():
    payload = b"y" * (5 * 1024 * 1024)       # URS 验收：5 MiB 无截断
    buf = FrameBuffer()
    out = []
    encoded = encode_frame(payload)
    for i in range(0, len(encoded), 65536):   # 模拟 64KiB 分片到达
        out += buf.feed(encoded[i : i + 65536])
    assert out == [payload]
