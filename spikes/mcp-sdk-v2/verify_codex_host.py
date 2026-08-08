"""Verify MCP discovery and tool calls through the local Codex app-server."""

import argparse
import json
import os
import secrets
import select
import selectors
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TOOL_NAMES = ["get_blender_status", "get_scene_summary", "describe_capabilities"]
PROTOCOL_PROBE = "get_negotiated_protocol"
HOST_TOOL_NAMES = [*TOOL_NAMES, PROTOCOL_PROBE]
HOST_PROTOCOL = "2025-06-18"
UV = "/Users/yeminjie/.local/bin/uv"
CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"
OFFICIAL_MCP = "/Users/yeminjie/blender_mcp/mcp"
BLEND_FILE = (
    "/Applications/Blender.app/Contents/Resources/5.2/scripts/startup/"
    "bl_app_templates_system/Storyboarding/startup.blend"
)
MAX_LINE_BYTES = 16 * 1024 * 1024
MAX_PENDING_BYTES = 32 * 1024 * 1024
MAX_EVENTS = 1024
MAX_EVENT_BYTES = 4 * 1024 * 1024
BLENDER_TOOLS = {
    "execute_blender_code",
    "execute_blender_code_for_cli",
    "get_blendfile_summary_datablocks",
    "get_blendfile_summary_datablocks_for_cli",
    "get_blendfile_summary_missing_files",
    "get_blendfile_summary_missing_files_for_cli",
    "get_blendfile_summary_of_linked_libraries",
    "get_blendfile_summary_of_linked_libraries_for_cli",
    "get_blendfile_summary_path_info",
    "get_blendfile_summary_path_info_for_cli",
    "get_blendfile_summary_usage_guess",
    "get_blendfile_summary_usage_guess_for_cli",
    "get_object_detail_summary",
    "get_objects_summary",
    "get_python_api_docs",
    "get_screenshot_of_area_as_image",
    "get_screenshot_of_window_as_image",
    "get_screenshot_of_window_as_json",
    "jump_to_tab_by_name",
    "jump_to_tab_by_space_type",
    "jump_to_view3d_object_by_name",
    "jump_to_view3d_object_data_by_name",
    "render_thumbnail_to_path",
    "render_viewport_to_path",
    "search_api_docs",
    "search_manual_docs",
}


class AppServer:
    def __init__(self, mcp_config: str | None = None, enable_2026: bool = False) -> None:
        assert Path(CODEX).is_file(), CODEX
        command = [CODEX, "app-server", "--stdio", "--strict-config"]
        if enable_2026:
            command.extend(["--enable", "mcp_2026_07_28"])
        if mcp_config is not None:
            command.extend(["-c", mcp_config])
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=False,
            bufsize=0,
        )
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self._stdin_fd = self.proc.stdin.fileno()
        self._stdout_fd = self.proc.stdout.fileno()
        os.set_blocking(self._stdin_fd, False)
        os.set_blocking(self._stdout_fd, False)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self._pending = bytearray()
        self._pending_offset = 0
        self._search_offset = 0
        self.events: list[dict[str, Any]] = []
        self._event_bytes = 0

    def _read_message(self, deadline: float) -> dict[str, Any]:
        """Read one complete JSON line without allowing a partial line to hang."""
        line_end = self._pending.find(b"\n", self._search_offset)
        while line_end < 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("app-server response timed out before a complete line")
            if not self.selector.select(remaining):
                raise TimeoutError("app-server response timed out before a complete line")
            try:
                chunk = os.read(self._stdout_fd, 65536)
            except BlockingIOError:
                continue
            if not chunk:
                raise EOFError("app-server closed stdout before a complete response")
            self._pending.extend(chunk)
            unconsumed = len(self._pending) - self._pending_offset
            if unconsumed > MAX_PENDING_BYTES:
                raise ValueError("app-server pending buffer exceeds size limit")
            line_end = self._pending.find(b"\n", self._search_offset)
            if ((line_end < 0 and unconsumed > MAX_LINE_BYTES)
                    or line_end - self._pending_offset > MAX_LINE_BYTES):
                raise ValueError("app-server response line exceeds size limit")
            if line_end < 0:
                # No newline yet: remember the searched suffix so a 16 MiB
                # partial line is scanned once per newly-read chunk, not O(n²).
                self._search_offset = len(self._pending)
        raw = bytes(self._pending[self._pending_offset:line_end])
        if len(raw) > MAX_LINE_BYTES:
            raise ValueError("app-server response line exceeds size limit")
        self._pending_offset = line_end + 1
        if self._pending_offset == len(self._pending):
            self._pending.clear()
            self._pending_offset = 0
            self._search_offset = 0
        elif self._pending_offset >= 1024 * 1024:
            del self._pending[:self._pending_offset]
            self._pending_offset = 0
            self._search_offset = 0
        else:
            # A single read may contain several responses; search the retained
            # suffix on the next call without rescanning the consumed prefix.
            self._search_offset = self._pending_offset
        message = json.loads(raw)
        if not isinstance(message, dict):
            raise TypeError(f"app-server emitted non-object JSON: {message!r}")
        return message

    def _write(self, payload: bytes, deadline: float) -> None:
        pending = memoryview(payload)
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("app-server request timed out while writing")
            try:
                written = os.write(self._stdin_fd, pending)
            except BlockingIOError:
                _, writable, _ = select.select([], [self._stdin_fd], [], remaining)
                if not writable:
                    raise TimeoutError("app-server request timed out while writing")
            else:
                pending = pending[written:]

    def request(
        self,
        request_id: int,
        method: str,
        params: dict[str, object],
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send one request under a single deadline covering write and response."""
        if timeout <= 0:
            raise TimeoutError(f"app-server request timed out: {method}")
        deadline = time.monotonic() + timeout
        request = {"id": request_id, "method": method, "params": params}
        self._write((json.dumps(request) + "\n").encode(), deadline)
        while True:
            message = self._read_message(deadline)
            actual_id = message.get("id")
            if type(actual_id) is type(request_id) and actual_id == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                result = message["result"]
                assert isinstance(result, dict), result
                return result
            self._record_event(message)

    def _record_event(self, message: dict[str, Any]) -> None:
        if len(self.events) >= MAX_EVENTS:
            raise ValueError("app-server event flood")
        event_bytes = len(json.dumps(message, ensure_ascii=False).encode("utf-8"))
        if self._event_bytes + event_bytes > MAX_EVENT_BYTES:
            raise ValueError("app-server event buffer exceeds size limit")
        self.events.append(message)
        self._event_bytes += event_bytes

    def drain_events(self, timeout: float = 0.5) -> None:
        """Boundedly settle notifications that may follow the final response."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self._record_event(self._read_message(deadline))
            except TimeoutError:
                return
            except EOFError:
                # A server that has cleanly closed stdout has no more
                # notifications to settle; EOF is the bounded terminal state
                # for this postlude, while malformed JSON and event caps still
                # fail closed through their original exceptions.
                return

    def approval_events(self) -> list[dict[str, Any]]:
        return [
            event for event in self.events
            if "approval" in str(event.get("method", "")).lower()
        ]

    def notify(self, method: str) -> None:
        self._write(
            (json.dumps({"method": method}) + "\n").encode(),
            time.monotonic() + 30.0,
        )

    def close(self) -> None:
        self.selector.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)


def start_thread(app: AppServer, client_name: str) -> str:
    app.request(
        1,
        "initialize",
        {
            "clientInfo": {"name": client_name, "version": "1.0"},
            "capabilities": {"experimentalApi": True},
        },
    )
    app.notify("initialized")
    thread = app.request(
        2,
        "thread/start",
        {"cwd": str(ROOT), "ephemeral": True, "approvalPolicy": "never"},
    )
    thread_id = thread["thread"]["id"]
    assert isinstance(thread_id, str), thread
    return thread_id


def _sdk_server_args() -> list[str]:
    return [
        "run",
        "--quiet",
        "--no-project",
        "--python",
        "3.13",
        "--with",
        "mcp==2.0.0",
        "python",
        str(Path(__file__).resolve()),
        "--serve-sdk-v2",
    ]


def _assert_tool_catalog(server: dict[str, Any], expected: set[str]) -> None:
    tools = server["tools"]
    assert set(tools) == expected, server
    for name, tool in tools.items():
        assert tool["name"] == name, tool
        assert tool["inputSchema"].get("type") == "object", tool


def verify_sdk_v2(enable_2026: bool = True) -> None:
    args = _sdk_server_args()
    mcp_config = (
        'mcp_servers={sdk_v2_spike={'
        f'command="{UV}",'
        f'args={json.dumps(args, separators=(",", ":"))},'
        f'enabled_tools={json.dumps(HOST_TOOL_NAMES, separators=(",", ":"))},'
        'required=true,startup_timeout_sec=20,tool_timeout_sec=10}}'
    )
    app = AppServer(mcp_config=mcp_config, enable_2026=enable_2026)
    try:
        thread_id = start_thread(app, "BlenderDesign SDK v2 verifier")
        effective = app.request(3, "config/read", {})["config"]["mcp_servers"]["sdk_v2_spike"]
        assert effective["command"] == UV, effective
        assert effective["args"] == args, effective
        assert effective["enabled_tools"] == HOST_TOOL_NAMES, effective
        assert effective["required"] is True, effective
        assert "default_tools_approval_mode" not in effective, effective

        features = app.request(4, "experimentalFeature/list", {})["data"]
        feature = next(item for item in features if item["name"] == "mcp_2026_07_28")
        assert feature["enabled"] is enable_2026, feature

        status = app.request(
            5,
            "mcpServerStatus/list",
            {"threadId": thread_id, "detail": "toolsAndAuthOnly"},
        )
        server = next(item for item in status["data"] if item["name"] == "sdk_v2_spike")
        assert server["serverInfo"]["name"] == "BlenderDesign SDK v2 spike", server
        _assert_tool_catalog(server, set(HOST_TOOL_NAMES))

        results: dict[str, object] = {}
        for request_id, tool in enumerate(HOST_TOOL_NAMES, start=10):
            response = app.request(
                request_id,
                "mcpServer/tool/call",
                {"server": "sdk_v2_spike", "tool": tool, "arguments": {}, "threadId": thread_id},
            )
            assert not response.get("isError"), response
            results[tool] = response["structuredContent"]
        protocol = results[PROTOCOL_PROBE]
        assert isinstance(protocol, dict)
        assert protocol["protocol_version"] == HOST_PROTOCOL, protocol
        print(
            json.dumps(
                {
                    "feature_enabled": feature["enabled"],
                    "host_protocol": protocol["protocol_version"],
                    "results": results,
                    "tools": sorted(server["tools"]),
                },
                sort_keys=True,
            )
        )
    finally:
        app.close()


def verify_blender_policy(include_render_tools: bool = False) -> None:
    app = AppServer()
    try:
        thread_id = start_thread(app, "BlenderDesign Blender policy verifier")
        config = app.request(3, "config/read", {})["config"]
        effective = config["mcp_servers"]["blender"]
        expected_args = [
            "run",
            "--quiet",
            "--no-project",
            "--with",
            "mcp[cli]>=1.2.0,<2",
            "--with-editable",
            OFFICIAL_MCP,
            "blender-mcp",
        ]
        assert effective["command"] == UV, effective
        assert effective["args"] == expected_args, effective
        assert effective["default_tools_approval_mode"] == "approve", effective
        assert effective["enabled"] is True, effective
        assert effective["env"]["BLENDER_PATH"] == "/Applications/Blender.app/Contents/MacOS/Blender"
        assert set(effective["enabled_tools"]) == BLENDER_TOOLS, effective
        assert effective["omit_tools_from"] == [], effective
        assert config["features"]["code_mode"]["direct_only_tool_namespaces"] == [
            "mcp__blender"
        ], config["features"]
        for forbidden in ("disabled_tools", "tools"):
            assert forbidden not in effective, effective

        status = app.request(
            4,
            "mcpServerStatus/list",
            {"threadId": thread_id, "detail": "toolsAndAuthOnly"},
        )
        server = next(item for item in status["data"] if item["name"] == "blender")
        assert server["serverInfo"]["name"] == "blender-mcp", server
        _assert_tool_catalog(server, BLENDER_TOOLS)
        prefix = f"bcx-host-verify-{os.getpid()}-{secrets.token_hex(4)}"
        generated: list[Path] = []
        initial = app.request(
            10,
            "mcpServer/tool/call",
            {
                "server": "blender",
                "tool": "execute_blender_code",
                "arguments": {"code": (
                    "import bpy\n"
                    "obj=bpy.context.view_layer.objects.active\n"
                    "result={'probe':'ok','workspace':bpy.context.workspace.name,"
                    "'active':obj.name if obj else None,"
                    "'data_name':obj.data.name if obj and obj.data else None}"
                )},
                "threadId": thread_id,
            },
            timeout=60,
        )
        assert not initial.get("isError"), initial
        state = initial["structuredContent"]["result"]
        assert state["probe"] == "ok", initial
        assert all(isinstance(state[key], str)
                   for key in ("workspace", "active", "data_name")), state
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
            "get_blendfile_summary_of_linked_libraries_for_cli": {"blend_file": BLEND_FILE},
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
            "jump_to_tab_by_space_type": {"space_type": "VIEW_3D", "allow_edits": False},
            "jump_to_view3d_object_by_name": {"name": state["active"], "allow_edits": False},
            "jump_to_view3d_object_data_by_name": {
                "name": state["data_name"], "allow_edits": False},
            "search_api_docs": {"query": "bpy app version", "max_results": 3},
            "search_manual_docs": {"query": "render image", "max_results": 3},
        }
        if include_render_tools:
            calls.update({
                "render_thumbnail_to_path": {"output_path": f"/{prefix}-thumbnail.png"},
                "render_viewport_to_path": {"output_path": f"/{prefix}-viewport.png"},
            })
        expected_called = BLENDER_TOOLS if include_render_tools else BLENDER_TOOLS - {
            "render_thumbnail_to_path", "render_viewport_to_path",
        }
        assert set(calls) | {"execute_blender_code"} == expected_called
        call_results: dict[str, dict[str, Any]] = {"execute_blender_code": initial}
        try:
            for request_id, (tool, arguments) in enumerate(calls.items(), start=11):
                timeout = 180 if tool.endswith("_for_cli") or tool.startswith("render_") else 60
                response = app.request(
                    request_id,
                    "mcpServer/tool/call",
                    {
                        "server": "blender",
                        "tool": tool,
                        "arguments": arguments,
                        "threadId": thread_id,
                    },
                    timeout=timeout,
                )
                assert not response.get("isError"), response
                if tool.startswith("render_"):
                    output = Path(response["structuredContent"]["result"]["filepath"])
                    assert output.parent.name == "blender_mcp", response
                    assert output.name.startswith(prefix) and output.is_file(), response
                    assert output.stat().st_size > 0, response
                    generated.append(output)
                call_results[tool] = response
        finally:
            for output in generated:
                if output.is_file() and output.parent.name == "blender_mcp" \
                        and output.name.startswith(prefix):
                    output.unlink()
        assert set(call_results) == expected_called
        app.drain_events()
        approval_events = app.approval_events()
        assert approval_events == [], approval_events
        print(
            json.dumps(
                {
                    "approval_mode": effective["default_tools_approval_mode"],
                    "approval_events": len(approval_events),
                    "direct_only_tool_namespaces": config["features"]["code_mode"][
                        "direct_only_tool_namespaces"
                    ],
                    "filters": {
                        "enabled_tools": sorted(effective["enabled_tools"]),
                        "omit_tools_from": effective["omit_tools_from"],
                    },
                    "functional_call_count": len(call_results),
                    "functional_tools": sorted(call_results),
                    "skipped_tools": sorted(BLENDER_TOOLS - set(call_results)),
                    "tools": sorted(server["tools"]),
                },
                sort_keys=True,
            )
        )
    finally:
        app.close()


def serve_sdk_v2() -> None:
    from mcp.server.mcpserver import Context
    from server import mcp

    @mcp.tool()
    def get_negotiated_protocol(ctx: Context) -> dict[str, object]:
        return {"protocol_version": ctx.protocol_version}

    mcp.run()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configured-blender", action="store_true")
    parser.add_argument(
        "--include-render-tools", action="store_true",
        help="also call both deferred GUI render tools (may expose upstream Blender races)",
    )
    parser.add_argument("--legacy-codex", action="store_true")
    parser.add_argument("--serve-sdk-v2", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve_sdk_v2:
        serve_sdk_v2()
    elif args.configured_blender:
        verify_blender_policy(include_render_tools=args.include_render_tools)
    else:
        verify_sdk_v2(enable_2026=not args.legacy_codex)


if __name__ == "__main__":
    main()
