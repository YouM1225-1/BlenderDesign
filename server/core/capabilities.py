"""describe_capabilities 静态应答。spec §6.3：不经 Bridge，可离线回答。"""
from __future__ import annotations

from typing import Any

from protocol import envelope
from .versions import BASELINE

SUPPORTED_TOOLS = ["get_blender_status", "get_scene_summary", "describe_capabilities"]


def describe(server_version: str, connected: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "server_version": server_version,
        "envelope_version": envelope.ENVELOPE_VERSION,
        "phase": "phase0",
        "supported_tools": SUPPORTED_TOOLS,
        "baseline_blender": dict(BASELINE),
        "ir_schema_version": None,
        "supported_operation_kinds": [],
        "connected_instances": [
            {"instance_id": c["instance_id"], "blender_version": c["blender_version"],
             "bridge_version": c["bridge_version"]}
            for c in connected
        ],
    }
