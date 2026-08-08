"""Verify all 26 official Blender MCP tools against CLI and a connected GUI."""

import asyncio
import importlib.metadata
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BLEND_FILE = (
    "/Applications/Blender.app/Contents/Resources/5.2/scripts/startup/"
    "bl_app_templates_system/Storyboarding/startup.blend"
)
OFFICIAL_TOOLS = {
    "execute_blender_code", "execute_blender_code_for_cli",
    "get_blendfile_summary_datablocks", "get_blendfile_summary_datablocks_for_cli",
    "get_blendfile_summary_missing_files", "get_blendfile_summary_missing_files_for_cli",
    "get_blendfile_summary_of_linked_libraries",
    "get_blendfile_summary_of_linked_libraries_for_cli",
    "get_blendfile_summary_path_info", "get_blendfile_summary_path_info_for_cli",
    "get_blendfile_summary_usage_guess", "get_blendfile_summary_usage_guess_for_cli",
    "get_object_detail_summary", "get_objects_summary", "get_python_api_docs",
    "get_screenshot_of_area_as_image", "get_screenshot_of_window_as_image",
    "get_screenshot_of_window_as_json", "jump_to_tab_by_name",
    "jump_to_tab_by_space_type", "jump_to_view3d_object_by_name",
    "jump_to_view3d_object_data_by_name", "render_thumbnail_to_path",
    "render_viewport_to_path", "search_api_docs", "search_manual_docs",
}


def _text_payload(response: Any) -> dict[str, Any] | None:
    for item in response.content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            payload = json.loads(text)
            assert isinstance(payload, dict), payload
            return payload
    return None


def _validate_response(name: str, response: Any) -> tuple[dict[str, Any] | None, list[str]]:
    assert not response.isError, (name, response.content)
    kinds = [str(getattr(item, "type", type(item).__name__)) for item in response.content]
    assert kinds, name
    if "image" in kinds:
        assert any(getattr(item, "data", "") for item in response.content), name
        return None, kinds
    payload = _text_payload(response)
    assert payload, (name, response.content)
    if "status" in payload:
        assert payload["status"] == "ok", (name, payload)
    return payload, kinds


async def main() -> None:
    env = os.environ.copy()
    env["BLENDER_PATH"] = "/Applications/Blender.app/Contents/MacOS/Blender"
    params = StdioServerParameters(
        command="/Users/yeminjie/.local/bin/uv",
        args=[
            "run", "--quiet", "--no-project", "--with", "mcp[cli]>=1.2.0,<2",
            "--with-editable", "/Users/yeminjie/blender_mcp/mcp", "blender-mcp",
        ],
        env=env,
    )
    prefix = f"bcx-verify-{os.getpid()}-{secrets.token_hex(4)}"
    generated: list[Path] = []
    results: dict[str, dict[str, Any]] = {}
    try:
        async with asyncio.timeout(600):
            async with (
                stdio_client(params) as (read, write),
                ClientSession(
                    read, write, read_timeout_seconds=timedelta(seconds=30)
                ) as session,
            ):
                await session.initialize()
                listed = await session.list_tools()
                assert {tool.name for tool in listed.tools} == OFFICIAL_TOOLS

                probe = await session.call_tool(
                    "execute_blender_code",
                    {"code": (
                        "import bpy\n"
                        "obj=bpy.context.view_layer.objects.active\n"
                        "result={'probe':'ok','workspace':bpy.context.workspace.name,"
                        "'active':obj.name if obj else None,"
                        "'data_name':obj.data.name if obj and obj.data else None}"
                    )},
                    read_timeout_seconds=timedelta(seconds=60),
                )
                payload, kinds = _validate_response("execute_blender_code", probe)
                assert payload is not None and payload["result"]["probe"] == "ok"
                state = payload["result"]
                assert all(isinstance(state[key], str)
                           for key in ("workspace", "active", "data_name"))
                results["execute_blender_code"] = {"content_types": kinds}

                calls = {
                    "execute_blender_code_for_cli": {
                        "blend_file": BLEND_FILE,
                        "code": ("import bpy\nresult={'version': bpy.app.version_string, "
                                 "'object_count': len(bpy.data.objects)}"),
                    },
                    "get_blendfile_summary_datablocks": {},
                    "get_blendfile_summary_datablocks_for_cli": {"blend_file": BLEND_FILE},
                    "get_blendfile_summary_missing_files": {},
                    "get_blendfile_summary_missing_files_for_cli": {"blend_file": BLEND_FILE},
                    "get_blendfile_summary_of_linked_libraries": {},
                    "get_blendfile_summary_of_linked_libraries_for_cli": {
                        "blend_file": BLEND_FILE},
                    "get_blendfile_summary_path_info": {},
                    "get_blendfile_summary_path_info_for_cli": {"blend_file": BLEND_FILE},
                    "get_blendfile_summary_usage_guess": {},
                    "get_blendfile_summary_usage_guess_for_cli": {"blend_file": BLEND_FILE},
                    "get_object_detail_summary": {"name": state["active"]},
                    "get_objects_summary": {},
                    "get_python_api_docs": {"identifier": "bpy.app"},
                    "get_screenshot_of_area_as_image": {
                        "area_ui_type": "VIEW_3D", "size_limit_in_bytes": 262_144},
                    "get_screenshot_of_window_as_image": {"size_limit_in_bytes": 262_144},
                    "get_screenshot_of_window_as_json": {},
                    "jump_to_tab_by_name": {"name": state["workspace"]},
                    "jump_to_tab_by_space_type": {
                        "space_type": "VIEW_3D", "allow_edits": False},
                    "jump_to_view3d_object_by_name": {
                        "name": state["active"], "allow_edits": False},
                    "jump_to_view3d_object_data_by_name": {
                        "name": state["data_name"], "allow_edits": False},
                    "render_thumbnail_to_path": {"output_path": f"/{prefix}-thumbnail.png"},
                    "render_viewport_to_path": {"output_path": f"/{prefix}-viewport.png"},
                    "search_api_docs": {"query": "bpy app version", "max_results": 3},
                    "search_manual_docs": {"query": "render image", "max_results": 3},
                }
                assert set(calls) | {"execute_blender_code"} == OFFICIAL_TOOLS
                for name, arguments in calls.items():
                    timeout = 180 if name.endswith("_for_cli") or name.startswith("render_") else 60
                    response = await session.call_tool(
                        name, arguments, read_timeout_seconds=timedelta(seconds=timeout)
                    )
                    payload, kinds = _validate_response(name, response)
                    if name == "execute_blender_code_for_cli":
                        assert payload is not None
                        assert isinstance(payload.get("object_count"), int)
                        assert isinstance(payload.get("version"), str)
                    if name.startswith("render_"):
                        assert payload is not None
                        output = Path(payload["result"]["filepath"])
                        assert output.parent.name == "blender_mcp"
                        assert output.name.startswith(prefix) and output.is_file()
                        assert output.stat().st_size > 0
                        generated.append(output)
                    results[name] = {"content_types": kinds}
    finally:
        for output in generated:
            if output.is_file() and output.parent.name == "blender_mcp" \
                    and output.name.startswith(prefix):
                output.unlink()

    assert len(results) == len(OFFICIAL_TOOLS)
    print(json.dumps({
        "environment": {"mcp_sdk": importlib.metadata.version("mcp")},
        "functional_call_count": len(results),
        "functional_tools": sorted(results),
        "registered_tool_count": len(OFFICIAL_TOOLS),
        "results": results,
    }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
