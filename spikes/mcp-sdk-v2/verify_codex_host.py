"""Verify MCP discovery and tool calls through the local Codex app-server."""

from __future__ import annotations

import argparse
import json
import selectors
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOL_NAMES = ["get_blender_status", "get_scene_summary", "describe_capabilities"]
BLENDER_TOOLS = {
    "get_objects_summary",
    "get_object_detail_summary",
    "get_blendfile_summary_datablocks",
    "get_blendfile_summary_missing_files",
    "get_blendfile_summary_of_linked_libraries",
    "get_blendfile_summary_path_info",
    "get_blendfile_summary_usage_guess",
    "get_python_api_docs",
    "search_api_docs",
    "search_manual_docs",
}


class AppServer:
    def __init__(self, mcp_config: str | None = None, enable_2026: bool = False) -> None:
        codex = shutil.which("codex")
        assert codex is not None
        command = [codex, "app-server", "--stdio", "--strict-config"]
        if enable_2026:
            command.extend(["--enable", "mcp_2026_07_28"])
        if mcp_config is not None:
            command.extend(["-c", mcp_config])
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)

    def request(self, request_id: int, method: str, params: dict[str, object]) -> dict[str, object]:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if not self.selector.select(deadline - time.monotonic()):
                break
            assert self.proc.stdout is not None
            message = json.loads(self.proc.stdout.readline())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]
        raise TimeoutError(f"app-server request timed out: {method}")

    def notify(self, method: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"method": method}) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        self.proc.terminate()
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
    return thread["thread"]["id"]


def verify_sdk_v2(enable_2026: bool = True) -> None:
    server = ROOT / "server.py"
    mcp_config = (
        'mcp_servers={sdk_v2_spike={'
        'command="/Users/yeminjie/.local/bin/uv",'
        'args=["run","--quiet","--no-project","--python","3.13","--with","mcp==2.0.0",'
        f'"python","{server}"],'
        'enabled_tools=["get_blender_status","get_scene_summary","describe_capabilities"],'
        'required=true,startup_timeout_sec=20,tool_timeout_sec=10}}'
    )
    app = AppServer(mcp_config=mcp_config, enable_2026=enable_2026)
    try:
        thread_id = start_thread(app, "BlenderDesign SDK v2 verifier")
        status = app.request(
            3,
            "mcpServerStatus/list",
            {"threadId": thread_id, "detail": "toolsAndAuthOnly"},
        )
        server = next(item for item in status["data"] if item["name"] == "sdk_v2_spike")
        assert set(server["tools"]) == set(TOOL_NAMES), server

        results = {}
        for request_id, tool in enumerate(TOOL_NAMES, start=10):
            response = app.request(
                request_id,
                "mcpServer/tool/call",
                {"server": "sdk_v2_spike", "tool": tool, "arguments": {}, "threadId": thread_id},
            )
            assert not response.get("isError"), response
            results[tool] = response["structuredContent"]
        print(json.dumps({"tools": sorted(server["tools"]), "results": results}, sort_keys=True))
    finally:
        app.close()


def verify_blender_policy() -> None:
    app = AppServer()
    try:
        thread_id = start_thread(app, "BlenderDesign Blender policy verifier")
        status = app.request(
            3,
            "mcpServerStatus/list",
            {"threadId": thread_id, "detail": "toolsAndAuthOnly"},
        )
        server = next(item for item in status["data"] if item["name"] == "blender")
        assert set(server["tools"]) == BLENDER_TOOLS, server
        response = app.request(
            10,
            "mcpServer/tool/call",
            {
                "server": "blender",
                "tool": "get_blendfile_summary_path_info",
                "arguments": {},
                "threadId": thread_id,
            },
        )
        assert not response.get("isError"), response
        print(json.dumps({"tools": sorted(server["tools"]), "path_info": response}, sort_keys=True))
    finally:
        app.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configured-blender", action="store_true")
    parser.add_argument("--legacy-codex", action="store_true")
    args = parser.parse_args()
    if args.configured_blender:
        verify_blender_policy()
    else:
        verify_sdk_v2(enable_2026=not args.legacy_codex)


if __name__ == "__main__":
    main()
