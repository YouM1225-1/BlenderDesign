"""Three-tool MCP SDK v2 compatibility spike; not production code."""

import platform

from mcp.server import MCPServer

mcp = MCPServer(
    "BlenderDesign SDK v2 spike",
    instructions="Read-only compatibility spike. It never connects to Blender or writes project files.",
)


@mcp.tool()
def get_blender_status() -> dict[str, object]:
    """Return a static status payload for protocol verification."""
    return {
        "state": "spike",
        "connected": False,
        "sdk_target": "2.0.0",
        "python": platform.python_version(),
    }


@mcp.tool()
def get_scene_summary() -> dict[str, object]:
    """Return a deterministic empty-scene summary."""
    return {
        "scene_name": "SDK v2 Spike",
        "scene_hash": "sha256:spike",
        "summary": {"object_count": 0},
    }


@mcp.tool()
def describe_capabilities() -> dict[str, object]:
    """Describe only the capabilities exercised by this spike."""
    return {
        "protocol_target": "2026-07-28",
        "tools": ["get_blender_status", "get_scene_summary", "describe_capabilities"],
    }


if __name__ == "__main__":
    mcp.run()
