import pytest

from acceptance.canonical import CanonicalError, canonicalize, digest


def test_key_order_is_normalised():
    assert canonicalize({"b": 1, "a": 2}) == canonicalize({"a": 2, "b": 1})
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_integer_and_float_with_same_value_serialise_identically():
    assert canonicalize({"x": 1}) == canonicalize({"x": 1.0}) == b'{"x":1}'


def test_negative_zero_is_normalised_to_zero():
    assert canonicalize({"x": -0.0}) == b'{"x":0}'


def test_unicode_must_be_nfc():
    # 必须用转义字面量:直接粘贴的两个 e-acute 在编辑器或文件写入时会被归一化成
    # 同一串,那样这条测试会静默失效(本计划初稿就踩过这个坑)。
    composed = "\u00e9"        # 单码点
    decomposed = "e\u0301"     # e + combining acute,两码点
    assert composed != decomposed
    assert canonicalize({"k": composed}) == '{"k":"\u00e9"}'.encode("utf-8")
    with pytest.raises(CanonicalError):
        canonicalize({"k": decomposed})


def test_non_finite_numbers_are_rejected():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalError):
            canonicalize({"x": bad})


def test_empty_containers_round_trip():
    assert canonicalize({"a": {}, "b": []}) == b'{"a":{},"b":[]}'


def test_array_order_is_preserved():
    assert canonicalize([2, 1]) == b"[2,1]"


def test_digest_is_domain_separated():
    value = {"a": 1}
    assert digest("contract", value) != digest("manifest", value)
    assert len(digest("contract", value)) == 64


def test_digest_is_stable_across_key_order():
    assert digest("contract", {"a": 1, "b": 2}) == digest("contract", {"b": 2, "a": 1})


@pytest.mark.parametrize(("value", "expected"), [
    (1e-5, "0.00001"),      # 规范 §6 的默认几何容差
    (1e-6, "0.000001"),     # 规范 §4.2 的量化步长
    (1e-7, "1e-7"),
    (1e-8, "1e-8"),
    (1.5e-7, "1.5e-7"),
    (1e21, "1e+21"),
    (123456789012345678901.0, "123456789012345680000"),
    (0.5, "0.5"),
    (100.0, "100"),
    (6.02e23, "6.02e+23"),
])
def test_numbers_match_ecmascript_tostring(value, expected):
    """基准值取自 node 的 String(x);CPython 的 repr 在前五条上与之分歧。"""
    assert canonicalize({"x": value}) == f'{{"x":{expected}}}'.encode()


def test_control_characters_use_short_escapes():
    assert canonicalize({"k": "\b\f"}) == b'{"k":"\\b\\f"}'


def test_digest_is_stable_across_processes(tmp_path):
    """规范 §2.5.1 要求跨进程复算一致 —— 同进程重算证明不了这一点。"""
    import subprocess
    import sys

    script = tmp_path / "recompute.py"
    script.write_text(
        "from acceptance.canonical import digest\n"
        "print(digest('contract', {'a': [1, 1.0, -0.0], 'b': '\\u00e9'}))\n",
        encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(script)], check=True, capture_output=True, text=True)
    here = digest("contract", {"a": [1, 1.0, -0.0], "b": "\u00e9"})
    assert completed.stdout.strip() == here


def test_digest_has_the_frozen_domain_prefix():
    import hashlib
    expected = hashlib.sha256(b"bcx.digest.v1.contract." + b'{"a":1}').hexdigest()
    assert digest("contract", {"a": 1}) == expected
