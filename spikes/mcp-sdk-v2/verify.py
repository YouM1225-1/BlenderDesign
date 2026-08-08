"""Verify legacy and modern MCP wire paths in memory and over stdio."""

import asyncio
import json
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from server import mcp

EXPECTED = {"get_blender_status", "get_scene_summary", "describe_capabilities"}
LEGACY_PROTOCOL = "2025-11-25"
MODERN_PROTOCOL = "2026-07-28"
UV = "/Users/yeminjie/.local/bin/uv"
READ_TIMEOUT_SECONDS = 10.0
TOTAL_TIMEOUT_SECONDS = 240.0  # four sessions × bounded 10 s operations + startup


async def verify(client: Client, expected_protocol: str) -> dict[str, object]:
    assert client.protocol_version == expected_protocol, client.protocol_version
    assert client.server_info is not None
    assert client.server_info.name == "BlenderDesign SDK v2 spike"
    assert client.instructions
    tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == EXPECTED, names
    for tool in tools.tools:
        assert tool.input_schema.get("type") == "object", tool
        assert tool.output_schema is not None, tool
        # Raw SDK v2 dict annotations intentionally remain open.  The
        # production adapter must close input/output schemas and reject unknown
        # arguments before SDK binding; this spike records the SDK boundary
        # instead of mistaking generated schemas for strict validation.
        assert tool.output_schema.get("additionalProperties") is True, tool
    results = {}
    for name in sorted(EXPECTED):
        result = await client.call_tool(
            name, {}, read_timeout_seconds=READ_TIMEOUT_SECONDS
        )
        assert not result.is_error, result
        assert result.structured_content is not None
        results[name] = result.structured_content
    return {"protocol": client.protocol_version, "results": results}


async def main() -> None:
    server = Path(__file__).with_name("server.py")
    params = StdioServerParameters(
        command=UV,
        args=[
            "run", "--quiet", "--no-project", "--python", "3.13",
            "--with", "mcp==2.0.0", "python", str(server),
        ],
    )
    results: dict[str, dict[str, dict[str, object]]] = {"in_memory": {}, "stdio": {}}
    for mode, protocol in (("legacy", LEGACY_PROTOCOL), ("auto", MODERN_PROTOCOL)):
        async with Client(
            mcp, mode=mode, read_timeout_seconds=READ_TIMEOUT_SECONDS
        ) as client:
            results["in_memory"][protocol] = await verify(client, protocol)
        async with Client(
            stdio_client(params), mode=mode, read_timeout_seconds=READ_TIMEOUT_SECONDS
        ) as client:
            results["stdio"][protocol] = await verify(client, protocol)

    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=TOTAL_TIMEOUT_SECONDS))
