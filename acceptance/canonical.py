"""规范 §2.5.1:RFC 8785 JSON Canonicalization Scheme + 四条项目内规则。"""
from __future__ import annotations

import hashlib
import math
import unicodedata

_DIGEST_PREFIX = "bcx.digest.v1."


class CanonicalError(ValueError):
    """输入不满足规范化前置条件(非 NFC、非有限数、未知类型)。"""


def _check_string(value: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalError(f"string is not NFC-normalised: {value!r}")
    return value


def _number(value: float | int) -> str:
    """ECMAScript `Number::toString`(RFC 8785 §3.2.2.3 引用的算法)。

    **不能用 `repr`**:CPython 与 ES 在多处分歧,且分歧恰好落在本方案实际使用的
    量级上——`1e-5`(规范 §6 的默认几何容差)`repr` 得 `1e-05` 而 ES 得 `0.00001`;
    `1e-6`(规范 §4.2 的量化步长)`repr` 得 `1e-06` 而 ES 得 `0.000001`。
    下面按 ES 规范逐条实现;`repr` 只用来取"最短往返十进制数字串",这一点二者一致。
    """
    if isinstance(value, bool):
        raise CanonicalError("bool must be handled before number")
    if isinstance(value, int):
        try:
            binary64 = float(value)
        except OverflowError as exc:
            raise CanonicalError("integer is outside finite binary64") from exc
        if not math.isfinite(binary64) or int(binary64) != value:
            raise CanonicalError(f"integer is not exactly representable as binary64: {value!r}")
        return _number(binary64)
    if not math.isfinite(value):
        raise CanonicalError(f"non-finite number: {value!r}")
    if value == 0.0:
        return "0"                      # 同时覆盖 -0.0
    if value < 0:
        return "-" + _number(-value)

    text = repr(value)
    mantissa, _, exponent = text.partition("e")
    exp = int(exponent) if exponent else 0
    int_part, _, frac_part = mantissa.partition(".")
    combined = int_part + frac_part
    stripped = combined.lstrip("0")
    leading = len(combined) - len(stripped)
    # n:使 value == 0.digits x 10**n 成立的十进制指数(ES 规范中的 n)
    n_exp = len(int_part) + exp - leading
    digits = stripped.rstrip("0") or "0"
    k = len(digits)

    if k <= n_exp <= 21:
        return digits + "0" * (n_exp - k)
    if 0 < n_exp <= 21:
        return digits[:n_exp] + "." + digits[n_exp:]
    if -6 < n_exp <= 0:
        return "0." + "0" * (-n_exp) + digits
    power = n_exp - 1
    sign = "+" if power >= 0 else "-"
    head = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{head}e{sign}{abs(power)}"


def _escape(value: str) -> str:
    out = ['"']
    for char in value:
        if char == '"':
            out.append('\\"')
        elif char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif char == "\b":
            out.append("\\b")
        elif char == "\f":
            out.append("\\f")
        elif ord(char) < 0x20:
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def _emit(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _escape(_check_string(value))
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_emit(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = [k for k in value]
        if any(not isinstance(k, str) for k in keys):
            raise CanonicalError("object keys must be strings")
        if len(set(keys)) != len(keys):
            raise CanonicalError("duplicate object key")
        ordered = sorted(keys, key=lambda k: _check_string(k).encode("utf-16-be"))
        body = ",".join(f"{_escape(k)}:{_emit(value[k])}" for k in ordered)
        return "{" + body + "}"
    raise CanonicalError(f"unsupported type: {type(value).__name__}")


def canonicalize(value: object) -> bytes:
    # NFC 检查(_check_string)对孤立代理项(如 JSON 转义 `\ud800`)是空操作——它不是
    # 一个有分解映射的码点,规范化前后相等。真正炸开的地方是编码:UTF-8/UTF-16 的严格
    # 编码器都拒绝孤立代理项(_emit 里给字典键排序用的 `.encode("utf-16-be")`,以及本
    # 函数的 `.encode("utf-8")`)。UnicodeEncodeError 是 ValueError 的子类但不是
    # CanonicalError,必须在这里转换,否则会作为裸异常穿透调用方的
    # `except CanonicalError`(见 contract.py:load_contract)。
    try:
        return _emit(value).encode("utf-8")
    except UnicodeError as exc:
        raise CanonicalError(f"value is not representable in UTF-8: {exc}") from exc


def digest(kind: str, value: object) -> str:
    payload = (_DIGEST_PREFIX + kind + ".").encode("ascii") + canonicalize(value)
    return hashlib.sha256(payload).hexdigest()
