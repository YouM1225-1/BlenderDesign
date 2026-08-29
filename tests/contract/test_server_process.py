# tests/contract/test_server_process.py
"""以真子进程跑 MCP Server：stdout 每行必须是 JSON-RPC（NFR-O1）；冷启动 < 5 s（NFR-P2）。

协议合同（复审 F-04 修订）：旧协议与 2026-07-28 **走各自的 wire path**，
不共享 `_init()`、不接受静默降级。旧版测试曾对两个版本都发 legacy `initialize`
且允许任意协商版本，导致 2026-07-28 实测降级到 2025-11-25 仍然假通过；该测试已删除，当前两条路径分别精确断言各自版本。
"""
import hashlib
import json
import math
import os
import selectors
import subprocess
import sys
import time
from collections import deque

import pytest

CODEX_PROTOCOL = "2025-06-18"
LEGACY_PROTOCOL = "2025-11-25"
CURRENT_PROTOCOL = "2026-07-28"
READ_TIMEOUT_SECONDS = 10.0
MAX_STDOUT_LINE_BYTES = 16 * 1024 * 1024
MAX_STDOUT_BUFFER_BYTES = 32 * 1024 * 1024
MAX_STDOUT_MESSAGES = 1024
MAX_STDOUT_BACKLOG_BYTES = 32 * 1024 * 1024
MAX_DIAGNOSTIC_LINES = 32
MAX_DIAGNOSTIC_LINE_BYTES = 1024
ORDERED_TOOLS = [
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
FROZEN_SCHEMA_SHA256 = {
    "describe_capabilities": "958c7cb8f5978b197a4a8e8290eb8791aa0ee0e18d64039e8a7b0344e8eb290e",
    "get_blender_status": "711d51c6c7f5d0eba37c8964374f268ca09cb41371cce05be693e2f98808304c",
    "get_scene_summary": "c8301261f88d9e546c08819b7e9e0c47a5e33246945a35f894a63c00e346cb1b",
}

INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
CALL = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "describe_capabilities", "arguments": {}}}


def _reject_json_constant(value):
    raise ValueError(f"non-standard JSON constant: {value}")


def _finite_json_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json_loads(raw):
    return json.loads(
        raw, parse_constant=_reject_json_constant, parse_float=_finite_json_float,
        object_pairs_hook=_reject_duplicate_keys)


def _canonical_json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()


def _spawn(tmp_path):
    env = os.environ | {"BLENDERCODEX_ROOT": str(tmp_path)}
    p = subprocess.Popen(
        [sys.executable, "-c", "from server.mcp.adapter import main; main()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=False, bufsize=0,
    )
    os.set_blocking(p.stdout.fileno(), False)
    return p


def _stop(p):
    try:
        p.kill()
        p.wait(timeout=5)
    finally:
        for stream in (p.stdin, p.stdout, p.stderr):
            if stream is not None:
                stream.close()


def _stdio_params(tmp_path):
    from mcp import StdioServerParameters
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", "from server.mcp.adapter import main; main()"],
        env=os.environ | {"BLENDERCODEX_ROOT": str(tmp_path)},
    )


@pytest.fixture
def proc(tmp_path):
    p = _spawn(tmp_path)
    yield p
    _stop(p)


def _send(p, obj):
    p.stdin.write((json.dumps(obj) + "\n").encode())
    p.stdin.flush()


class _StdoutReader:
    """Persistent per-process reader: no blocking readline and no consumed-byte loss."""
    def __init__(self, p):
        self.p = p
        os.set_blocking(p.stdout.fileno(), False)
        self.pending = bytearray()
        self.search_from = 0
        self.backlog = []
        self.backlog_bytes = 0
        self.diagnostics = deque(maxlen=MAX_DIAGNOSTIC_LINES)
        self.message_count = 0

    def _take(self, msg_id):
        for index, (obj, raw_bytes) in enumerate(self.backlog):
            actual = obj.get("id")
            if type(actual) is type(msg_id) and actual == msg_id:
                self.backlog_bytes -= raw_bytes
                return self.backlog.pop(index)[0]
        return None

    def _parse_complete_lines(self) -> None:
        start = 0
        while (line_end := self.pending.find(b"\n", self.search_from)) >= 0:
            raw = bytes(self.pending[start:line_end])
            start = line_end + 1
            self.search_from = start
            if len(raw) > MAX_STDOUT_LINE_BYTES:
                raise AssertionError("stdout line exceeds size limit")
            if self.backlog_bytes + len(raw) > MAX_STDOUT_BACKLOG_BYTES:
                raise AssertionError("stdout backlog exceeds size limit")
            self.message_count += 1
            if self.message_count > MAX_STDOUT_MESSAGES:
                raise AssertionError("stdout message flood")
            line = raw.decode("utf-8")
            self.diagnostics.append(line[:MAX_DIAGNOSTIC_LINE_BYTES])
            obj = _strict_json_loads(line)  # 解析失败 = stdout 被污染 → FAIL
            assert isinstance(obj, dict) and obj.get("jsonrpc") == "2.0"
            self.backlog.append((obj, len(raw)))
            self.backlog_bytes += len(raw)
        if start:
            del self.pending[:start]        # one compaction per read, not per line
        self.search_from = len(self.pending)  # old suffix was already searched
        if len(self.pending) > MAX_STDOUT_LINE_BYTES:
            raise AssertionError("stdout line exceeds size limit")

    def read_until(self, msg_id, deadline):
        found = self._take(msg_id)
        if found is not None:
            return found, list(self.diagnostics)
        sel = selectors.DefaultSelector()
        sel.register(self.p.stdout, selectors.EVENT_READ)
        try:
            while time.monotonic() < deadline:
                if not sel.select(timeout=max(0.0, deadline - time.monotonic())):
                    continue
                chunk = os.read(self.p.stdout.fileno(), 65536)
                if not chunk:
                    break
                self.pending.extend(chunk)
                if len(self.pending) > MAX_STDOUT_BUFFER_BYTES:
                    raise AssertionError("stdout buffer exceeds size limit")
                self._parse_complete_lines()  # parse the whole chunk before returning
                found = self._take(msg_id)
                if found is not None:
                    return found, list(self.diagnostics)
            raise AssertionError(
                f"no response id={msg_id} before deadline; "
                f"lines={list(self.diagnostics)}; "
                f"partial={bytes(self.pending[:1024])!r}; "
                f"partial_bytes={len(self.pending)}")
        finally:
            sel.unregister(self.p.stdout)
            sel.close()

    def drain_until(self, deadline):
        """Boundedly parse every trailing line; quiet timeout/clean EOF settle."""
        sel = selectors.DefaultSelector()
        sel.register(self.p.stdout, selectors.EVENT_READ)
        try:
            while time.monotonic() < deadline:
                if not sel.select(timeout=max(0.0, deadline - time.monotonic())):
                    break
                chunk = os.read(self.p.stdout.fileno(), 65536)
                if not chunk:
                    break
                self.pending.extend(chunk)
                if len(self.pending) > MAX_STDOUT_BUFFER_BYTES:
                    raise AssertionError("stdout buffer exceeds size limit")
                self._parse_complete_lines()
            if self.pending:
                raise AssertionError(
                    f"partial stdout after settle: {bytes(self.pending[:1024])!r}; "
                    f"partial_bytes={len(self.pending)}")
        finally:
            sel.unregister(self.p.stdout)
            sel.close()


def _read_until(p, msg_id, deadline):
    """Reuse one bounded reader so bytes consumed after a target response survive."""
    reader = getattr(p, "_bcx_stdout_reader", None)
    if reader is None:
        reader = _StdoutReader(p)
        p._bcx_stdout_reader = reader
    return reader.read_until(msg_id, deadline)


def _drain_stdout(p, deadline):
    reader = getattr(p, "_bcx_stdout_reader", None)
    if reader is None:
        reader = _StdoutReader(p)
        p._bcx_stdout_reader = reader
    reader.drain_until(deadline)


def test_cold_start_and_stdout_purity(tmp_path):
    t0 = time.monotonic()                    # 计时含进程启动（复审 F-12）
    p = _spawn(tmp_path)
    try:
        _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": CODEX_PROTOCOL, "capabilities": {},
                             "clientInfo": {"name": "l2", "version": "0"}}})
        resp, _ = _read_until(p, 1, t0 + 10)
        assert time.monotonic() - t0 < 5.0               # NFR-P2
        assert "允许 Codex 连接" in resp["result"].get("instructions", "")  # FR-34
        _send(p, INITIALIZED)
        _send(p, CALL)
        resp2, _ = _read_until(p, 2, time.monotonic() + 10)
        content = resp2["result"]["content"]
        assert (type(content) is list and len(content) == 1
                and content[0].get("type") == "text"
                and type(content[0].get("text")) is str)
        payload = _strict_json_loads(content[0]["text"])
        assert (_canonical_json(payload)
                == _canonical_json(resp2["result"]["structuredContent"]))
        assert payload["phase"] == "phase0"
        assert payload["ir_schema_version"] is None
        _drain_stdout(p, time.monotonic() + 0.2)
    finally:
        _stop(p)


def test_audit_request_id_matches_inbound_jsonrpc_id(tmp_path):
    p = _spawn(tmp_path)
    try:
        _send(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": CODEX_PROTOCOL, "capabilities": {},
                             "clientInfo": {"name": "l2", "version": "0"}}})
        _read_until(p, 1, time.monotonic() + 10)
        _send(p, INITIALIZED)
        _send(p, {**CALL, "id": 42})
        _read_until(p, 42, time.monotonic() + 10)
        _send(p, {**CALL, "id": "42"})
        _read_until(p, "42", time.monotonic() + 10)
        audit_path = next((tmp_path / "logs").glob("server-*.jsonl"))
        rows = [_strict_json_loads(line)
                for line in audit_path.read_text().splitlines()]
        assert rows[-2]["request_id"] == 42 and type(rows[-2]["request_id"]) is int
        assert rows[-1]["request_id"] == "42" and type(rows[-1]["request_id"]) is str
    finally:
        _stop(p)


@pytest.mark.parametrize("protocol", [CODEX_PROTOCOL, LEGACY_PROTOCOL])
def test_initialize_protocol_negotiates_exactly_requested(proc, protocol):
    # 当前 Codex 与上一代协议都走 initialize，并精确断言不被静默改写。
    _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": protocol, "capabilities": {},
                            "clientInfo": {"name": "l2", "version": "0"}}})
    resp, _ = _read_until(proc, 1, time.monotonic() + 10)
    assert resp["result"]["protocolVersion"] == protocol
    assert resp["result"]["serverInfo"]["name"] == FROZEN_SERVER_NAME
    assert resp["result"]["serverInfo"]["version"] == FROZEN_SERVER_VERSION
    _send(proc, INITIALIZED)
    _send(proc, CALL)
    valid, _ = _read_until(proc, 2, time.monotonic() + 10)
    content = valid["result"]["content"]
    assert (type(content) is list and len(content) == 1
            and content[0].get("type") == "text"
            and type(content[0].get("text")) is str)
    assert (_canonical_json(_strict_json_loads(content[0]["text"]))
            == _canonical_json(valid["result"]["structuredContent"]))
    _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "describe_capabilities",
                            "arguments": {"unexpected": 1}}})
    rejected, _ = _read_until(proc, 3, time.monotonic() + 10)
    assert rejected["error"]["code"] == -32602
    assert rejected["error"]["data"]["unknown"] == ["unexpected"]


@pytest.mark.asyncio
async def test_current_protocol_via_sdk_client(tmp_path, monkeypatch):
    # 新协议走真实 stdio，且精确证明 discover 成功、没有 initialize fallback。
    monkeypatch.setenv("BLENDERCODEX_ROOT", str(tmp_path))
    from mcp import Client
    from mcp.client.stdio import stdio_client
    from mcp.shared.exceptions import MCPError

    async with Client(stdio_client(_stdio_params(tmp_path)), mode="auto",
                      read_timeout_seconds=READ_TIMEOUT_SECONDS) as client:
        assert client.session.protocol_version == CURRENT_PROTOCOL
        assert client.session.discover_result is not None
        assert client.session.initialize_result is None
        assert client.server_info is not None
        assert client.server_info.name == FROZEN_SERVER_NAME
        assert client.server_info.version == FROZEN_SERVER_VERSION
        assert client.instructions is not None
        assert "允许 Codex 连接" in client.instructions
        tools = await client.list_tools()
        repeated = await client.list_tools()
        assert [tool.name for tool in tools.tools] == ORDERED_TOOLS
        assert (tools.next_cursor is None and repeated.next_cursor is None
                and tools.result_type == "complete"
                and repeated.result_type == "complete")
        assert (_canonical_json(tools.model_dump(mode="json", by_alias=True))
                == _canonical_json(
                    repeated.model_dump(mode="json", by_alias=True)))
        catalog = [tool.model_dump(
            mode="json", by_alias=True, exclude_none=False) for tool in tools.tools]
        raw_catalog = json.dumps(
            catalog, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()
        assert len(raw_catalog) == FROZEN_CATALOG_BYTES
        assert hashlib.sha256(raw_catalog).hexdigest() == FROZEN_CATALOG_SHA256
        schemas = [
            {"name": item["name"], "inputSchema": item["inputSchema"],
             "outputSchema": item["outputSchema"]}
            for item in catalog
        ]
        raw_schemas = json.dumps(
            schemas, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()
        assert len(raw_schemas) == FROZEN_SCHEMA_BYTES
        assert (hashlib.sha256(raw_schemas).hexdigest()
                == FROZEN_COMBINED_SCHEMA_SHA256)
        raw_instructions = client.instructions.encode()
        assert len(raw_instructions) == FROZEN_INSTRUCTIONS_BYTES
        assert hashlib.sha256(raw_instructions).hexdigest() == FROZEN_INSTRUCTIONS_SHA256
        result = await client.call_tool("describe_capabilities", {})
        assert result.structured_content is not None
        assert result.structured_content["phase"] == "phase0"
        assert (type(result.content) is list and len(result.content) == 1
                and getattr(result.content[0], "type", None) == "text"
                and type(getattr(result.content[0], "text", None)) is str)
        assert (_canonical_json(_strict_json_loads(result.content[0].text))
                == _canonical_json(result.structured_content))
        with pytest.raises(MCPError) as exc:
            await client.call_tool("describe_capabilities", {"unexpected": 1})
        assert exc.value.code == -32602
        assert exc.value.data["unknown"] == ["unexpected"]


@pytest.mark.asyncio
async def test_tools_declare_closed_schemas(tmp_path, monkeypatch):
    # 规范原始 $defs/$ref、完整 ordered catalog 与 instructions；任一漂移都失败。
    assert _canonical_json({"value": 1}) != _canonical_json({"value": True})
    with pytest.raises(ValueError, match="non-finite JSON number"):
        _strict_json_loads('{"value": 1e999}')
    monkeypatch.setenv("BLENDERCODEX_ROOT", str(tmp_path))
    from mcp import Client
    from server.mcp.adapter import mcp as server_app

    async with Client(server_app, read_timeout_seconds=READ_TIMEOUT_SECONDS) as client:
        first = await client.list_tools()
        second = await client.list_tools()
        tools = first.tools
        assert [tool.name for tool in tools] == ORDERED_TOOLS
        assert (first.next_cursor is None and second.next_cursor is None
                and first.result_type == "complete"
                and second.result_type == "complete")
        assert (_canonical_json(first.model_dump(mode="json", by_alias=True))
                == _canonical_json(second.model_dump(mode="json", by_alias=True)))
        catalog = [tool.model_dump(
            mode="json", by_alias=True, exclude_none=False) for tool in tools]
        raw_catalog = json.dumps(
            catalog, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()
        assert len(raw_catalog) == FROZEN_CATALOG_BYTES
        assert hashlib.sha256(raw_catalog).hexdigest() == FROZEN_CATALOG_SHA256
        schemas = [
            {"name": item["name"], "inputSchema": item["inputSchema"],
             "outputSchema": item["outputSchema"]}
            for item in catalog
        ]
        raw_schemas = json.dumps(
            schemas, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode()
        assert len(raw_schemas) == FROZEN_SCHEMA_BYTES
        assert (hashlib.sha256(raw_schemas).hexdigest()
                == FROZEN_COMBINED_SCHEMA_SHA256)
        assert client.instructions is not None
        raw_instructions = client.instructions.encode()
        assert len(raw_instructions) == FROZEN_INSTRUCTIONS_BYTES
        assert hashlib.sha256(raw_instructions).hexdigest() == FROZEN_INSTRUCTIONS_SHA256
        for tool in tools:
            payload = {"inputSchema": tool.input_schema,
                       "outputSchema": tool.output_schema}
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            assert digest == FROZEN_SCHEMA_SHA256[tool.name], \
                f"{tool.name} schema drift:\n{json.dumps(payload, indent=2, sort_keys=True)}"


@pytest.mark.asyncio
async def test_stdio_mcp_to_fake_bridge_roundtrip(tmp_path):
    from mcp import Client
    from mcp.client.stdio import stdio_client
    from tests.contract.fake_bridge import live_bridge

    with live_bridge(tmp_path) as (session, _reader, _run):
        async with Client(stdio_client(_stdio_params(tmp_path)), mode="auto",
                          read_timeout_seconds=READ_TIMEOUT_SECONDS) as client:
            status = await client.call_tool("get_blender_status", {})
            assert status.structured_content["instances"][0]["instance_id"] == session.instance_id
            summary = await client.call_tool(
                "get_scene_summary", {"instance_id": session.instance_id})
            assert summary.structured_content["scene_hash"] == "sha256:fake"
            assert summary.structured_content["scene_name"] == "Scene"


def test_read_until_preserves_same_chunk_backlog_and_matches_id_type_exactly():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"id\":true}\\n"
         "{\"jsonrpc\":\"2.0\",\"id\":1}\\n"
         "{\"jsonrpc\":\"2.0\",\"id\":2}\\n'); "
         "sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        first, _ = _read_until(p, 1, time.monotonic() + 1.0)
        second, _ = _read_until(p, 2, time.monotonic() + 1.0)
        assert type(first["id"]) is int and first["id"] == 1
        assert type(second["id"]) is int and second["id"] == 2
    finally:
        _stop(p)


def test_stdout_pollution_after_target_in_same_chunk_is_not_hidden():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"id\":1}\\nNOT-JSON\\n'); "
         "sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(json.JSONDecodeError):
            _read_until(p, 1, time.monotonic() + 1.0)
    finally:
        _stop(p)


def test_delayed_stdout_pollution_after_target_is_not_hidden():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"id\":1}\\n'); "
         "sys.stdout.flush(); time.sleep(0.1); "
         "sys.stdout.write('NOT-JSON\\n'); sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        _read_until(p, 1, time.monotonic() + 1.0)
        with pytest.raises(json.JSONDecodeError):
            _drain_stdout(p, time.monotonic() + 1.0)
    finally:
        _stop(p)


def test_partial_stdout_line_cannot_escape_deadline():
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.stdout.buffer.write(b'{'); sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    t0 = time.monotonic()
    try:
        with pytest.raises(AssertionError, match="partial"):
            _read_until(p, 1, t0 + 0.2)
        assert time.monotonic() - t0 < 1.0
    finally:
        _stop(p)


def test_unterminated_stdout_line_is_size_bounded(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "MAX_STDOUT_LINE_BYTES", 64)
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.stdout.buffer.write(b'x'*65); "
         "sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(AssertionError, match="size limit"):
            _read_until(p, 1, time.monotonic() + 1.0)
    finally:
        _stop(p)


def test_stdout_message_flood_is_bounded(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "MAX_STDOUT_MESSAGES", 8)
    p = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; "
         "[sys.stdout.write('{\\\"jsonrpc\\\":\\\"2.0\\\",\\\"method\\\":\\\"n\\\"}\\n') "
         "for _ in range(9)]; sys.stdout.flush(); time.sleep(5)"],
        stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        with pytest.raises(AssertionError, match="message flood"):
            _read_until(p, 1, time.monotonic() + 1.0)
    finally:
        _stop(p)
