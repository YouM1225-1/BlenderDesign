"""Verify the spike in memory and over stdio."""

import asyncio
import json
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from server import mcp

EXPECTED = {"get_blender_status", "get_scene_summary", "describe_capabilities"}


async def verify(client: Client) -> dict[str, object]:
    tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == EXPECTED, names
    results = {}
    for name in sorted(EXPECTED):
        result = await client.call_tool(name, {})
        assert result.structured_content is not None
        results[name] = result.structured_content
    return results


async def main() -> None:
    async with Client(mcp) as client:
        in_memory = await verify(client)

    server = Path(__file__).with_name("server.py")
    params = StdioServerParameters(
        command="/Users/yeminjie/.local/bin/uv",
        args=[
            "run", "--quiet", "--no-project", "--python", "3.13",
            "--with", "mcp==2.0.0", "python", str(server),
        ],
    )
    async with Client(stdio_client(params)) as client:
        stdio = await verify(client)

    print(json.dumps({"in_memory": in_memory, "stdio": stdio}, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
