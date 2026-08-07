"""Verify the official MCP CLI path with an explicit Blender executable."""

import asyncio
import importlib.metadata
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BLEND_FILE = (
    "/Applications/Blender.app/Contents/Resources/5.2/scripts/startup/"
    "bl_app_templates_system/Storyboarding/startup.blend"
)


async def main() -> None:
    env = os.environ.copy()
    env["BLENDER_PATH"] = "/Applications/Blender.app/Contents/MacOS/Blender"
    params = StdioServerParameters(
        command="/Users/yeminjie/.local/bin/uv",
        args=[
            "run",
            "--quiet",
            "--no-project",
            "--with",
            "mcp[cli]>=1.2.0,<2",
            "--with-editable",
            "/Users/yeminjie/blender_mcp/mcp",
            "blender-mcp",
        ],
        env=env,
    )
    calls = {
        "get_blendfile_summary_path_info_for_cli": {"blend_file": BLEND_FILE},
        "get_blendfile_summary_datablocks_for_cli": {"blend_file": BLEND_FILE},
        "execute_blender_code_for_cli": {
            "blend_file": BLEND_FILE,
            "code": "import bpy\nresult={'version': bpy.app.version_string, 'object_count': len(bpy.data.objects)}",
        },
    }
    results = {}
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        for name, arguments in calls.items():
            response = await session.call_tool(name, arguments)
            assert not response.isError, response.content
            payload = json.loads(response.content[0].text)
            assert payload.get("status", "ok") == "ok", payload
            results[name] = payload
    print(json.dumps({
        "environment": {"mcp_sdk": importlib.metadata.version("mcp")},
        "results": results,
    }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
