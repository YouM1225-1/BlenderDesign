import json

import pytest
from protocol import envelope, framing


def test_request_roundtrip():
    req = envelope.Request.new(token="tok", method="ping", params={}, budget_ms=250)
    payload = framing.FrameBuffer().feed(envelope.encode_request(req))[0]
    back = envelope.decode_request(payload)
    assert back == req
    assert back.v == envelope.ENVELOPE_VERSION


@pytest.mark.parametrize("budget", [True, 0, -1, 1.5, "1", 15_001, 10 ** 400])
def test_decode_request_rejects_invalid_relative_budget(budget):
    raw = json.dumps({"id": "x", "token": "t", "method": "ping", "params": {},
                      "budget_ms": budget, "v": 1}).encode()
    with pytest.raises(ValueError):
        envelope.decode_request(raw)


def test_request_defaults_missing_version_and_ignores_unknown_outer_fields():
    raw = json.dumps({"id": "x", "token": "t", "method": "ping", "params": {},
                      "future_field": "ignored"}).encode()
    request = envelope.decode_request(raw)
    assert request.v == envelope.ENVELOPE_VERSION
    assert request.id == "x" and request.params == {} and request.budget_ms is None


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b'{"v":1,"id":"x","method":"ping","params":{}}',
        b'{"v":1,"id":"x","token":"t","method":"ping","params":[]}',
        b'{"v":1,"id":1,"token":"t","method":"ping","params":{}}',
        b'{"v":true,"id":"x","token":"t","method":"ping","params":{}}',
        b'{"v":2,"id":"x","token":"t","method":"ping","params":{}}',
        b'{"v":-1,"id":"x","token":"t","method":"ping","params":{}}',
    ],
)
def test_decode_request_rejects_malformed(raw):
    with pytest.raises(ValueError):
        envelope.decode_request(raw)


@pytest.mark.parametrize("field", ["id", "token", "method"])
@pytest.mark.parametrize("value", ["\ud800", "x" * 1_025])
def test_decode_request_rejects_unencodable_or_oversized_text_fields(field, value):
    request = {"id": "x", "token": "t", "method": "ping", "params": {}, "v": 1}
    request[field] = value

    with pytest.raises(ValueError):
        envelope.decode_request(json.dumps(request).encode())


def test_decode_request_accepts_valid_unicode_scalar():
    raw = b'{"id":"\\ud83d\\ude00","token":"t","method":"ping","params":{},"v":1}'
    assert envelope.decode_request(raw).id == chr(0x1F600)


def test_decode_request_rejects_excessive_json_nesting():
    raw = (b'{"id":"x","token":"t","method":"ping","params":{"x":'
           + b"[" * 10_000 + b"0" + b"]" * 10_000 + b'},"v":1}')
    with pytest.raises(ValueError):
        envelope.decode_request(raw)


def test_decode_response_rejects_excessive_json_nesting():
    raw = (b'{"v":1,"id":"x","ok":true,"result":{"x":'
           + b"[" * 10_000 + b"0" + b"]" * 10_000 + b'}}')
    with pytest.raises(ValueError):
        envelope.decode_response(raw)


def test_decode_rejects_nonfinite_json_numbers():
    for constant in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
        request = ('{"id":"x","token":"t","method":"ping","params":{"x":'
                   + constant + '}}').encode()
        response = ('{"v":1,"id":"x","ok":true,"result":{"x":'
                    + constant + '}}').encode()
        with pytest.raises(ValueError):
            envelope.decode_request(request)
        with pytest.raises(ValueError):
            envelope.decode_response(response)


def test_encode_rejects_nonfinite_json_numbers():
    for value in (float("nan"), float("inf"), float("-inf")):
        request = envelope.Request.new(token="t", method="ping", params={"x": value})
        with pytest.raises(ValueError):
            envelope.encode_request(request)
        with pytest.raises(ValueError):
            envelope.ok_frame("id", {"x": value})


def test_ok_and_error_frames():
    ok = json.loads(framing.FrameBuffer().feed(envelope.ok_frame("id1", {"a": 1}))[0])
    assert ok == {"v": 1, "id": "id1", "ok": True, "result": {"a": 1}}
    err = json.loads(
        framing.FrameBuffer().feed(
            envelope.error_frame("id2", envelope.BRIDGE_BUSY, "full", retryable=True)
        )[0]
    )
    assert err["ok"] is False
    assert err["error"] == {"code": "BRIDGE_BUSY", "message": "full", "retryable": True}


def test_ok_frame_steps_yields_during_large_collection_encoding():
    steps = envelope.ok_frame_steps("id-steps", {"collections": [f"C{i}" for i in range(1000)]})
    yields = 0
    while True:
        try:
            next(steps)
            yields += 1
        except StopIteration as done:
            frame = done.value
            break
    decoded = json.loads(framing.FrameBuffer().feed(frame)[0])
    assert decoded["result"]["collections"][-1] == "C999"
    assert yields > 1000


def test_ok_frame_degrades_to_limit_error_when_oversized():
    huge = {"blob": "x" * (framing.MAX_FRAME + 16)}
    frame = framing.FrameBuffer().feed(envelope.ok_frame("id3", huge))[0]
    decoded = json.loads(frame)
    assert decoded["ok"] is False
    assert decoded["error"]["code"] == envelope.INTERNAL_LIMIT_EXCEEDED


def test_method_timeouts_table():
    assert envelope.METHOD_TIMEOUTS == {"ping": 2.0, "status": 2.0, "scene_summary": 15.0}
