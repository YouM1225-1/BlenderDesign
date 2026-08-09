"""SDK v2 MCP adapter for the Phase 0 read-only Blender channel."""
from __future__ import annotations

import contextvars
import threading
import time
from collections.abc import Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS
from pydantic import BaseModel, ConfigDict

from protocol import envelope
from server.core import config
from server.core.audit import AUDIT_LOCK_TIMEOUT, AuditLog
from server.core.bridge_client import BridgeError
from server.core.capabilities import describe
from server.core.discovery import Discovery, Instance

SERVER_VERSION = "0.1.0"
OVERALL_BUDGET = 3.0
SCENE_SUMMARY_BUDGET = 15.0
GUIDANCE = ("未发现可用的 Blender 实例。请在 Blender 的 3D 视口按 N 打开侧栏 → 「Codex」页签 → "
            "点击「允许 Codex 连接」，然后重试。")
INSTRUCTIONS = ("Blender 只读控制通道（Phase 0）。调用任何工具前先 get_blender_status；若无实例，"
                "引导用户在 Blender 3D 视口按 N → 「Codex」页签 → 点击「允许 Codex 连接」。"
                "本 Server 无写工具，不要尝试让 Blender 执行代码。"
                "describe_capabilities 可在 Blender 离线时回答。")
_ACTIVE_DEADLINE: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "bcx_request_deadline", default=None)
_STATUS_AGGREGATION_LOCK = threading.Lock()
_STATUS_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bcx-status")
_SCENE_SUMMARY_ADMISSION = threading.BoundedSemaphore(2)

_TOOL_ARGUMENTS = {
    "get_blender_status": frozenset({"instance_selector"}),
    "get_scene_summary": frozenset({"instance_id", "include_collections", "include_managed_objects"}),
    "describe_capabilities": frozenset({"include_instances"}),
}
_TOOL_TYPES: dict[str, dict[str, tuple[type[Any], ...]]] = {
    "get_blender_status": {"instance_selector": (str, type(None))},
    "get_scene_summary": {"instance_id": (str,), "include_collections": (bool,),
                          "include_managed_objects": (bool,)},
    "describe_capabilities": {"include_instances": (bool,)},
}


def _deadline(budget: float) -> float:
    return _ACTIVE_DEADLINE.get() or time.monotonic() + budget


class ToolFailure(Exception):
    def __init__(self, code: str, detail: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.retryable = retryable


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InstanceRow(ClosedModel):
    instance_id: str
    pid: int
    mode: Literal["gui"]
    bridge_state: Literal["connected", "disconnected", "busy"]
    blender_version: str
    blender_supported: bool
    version_warning: str | None
    scene_path: str | None
    scene_revision: int | None


class StatusResult(ClosedModel):
    ok: bool
    guidance: str | None
    partial: bool
    skipped_count: int
    instances: list[InstanceRow]


class UnitsResult(ClosedModel):
    system: Literal["NONE", "METRIC", "IMPERIAL"]
    scale_length: float


class ManagedObjectResult(ClosedModel):
    stable_id: str
    name: str
    type: str


class SummaryResult(ClosedModel):
    object_count: int
    mesh_count: int
    camera_count: int
    light_count: int
    collections: list[str]
    managed_objects: list[ManagedObjectResult]


class SceneSummaryResult(ClosedModel):
    instance_id: str
    scene_name: str
    scene_revision: int
    scene_hash: str
    scene_path: str | None
    version_warning: str | None
    units: UnitsResult
    summary: SummaryResult


class BaselineResult(ClosedModel):
    version: str
    platform: str


class ConnectedInstanceResult(ClosedModel):
    instance_id: str
    blender_version: str
    bridge_version: str


class CapabilitiesResult(ClosedModel):
    server_version: str
    envelope_version: int
    phase: Literal["phase0"]
    supported_tools: list[str]
    baseline_blender: BaselineResult
    ir_schema_version: str | None
    supported_operation_kinds: list[str]
    connected_instances: list[ConnectedInstanceResult]
    instances_partial: bool
    instances_skipped_count: int


_deps_cache: tuple[Discovery, AuditLog] | None = None


def _deps() -> tuple[Discovery, AuditLog]:
    global _deps_cache
    if _deps_cache is None:
        _deps_cache = Discovery(config.run_dir()), AuditLog(config.logs_dir())
    return _deps_cache


def _row(instance: Instance) -> dict[str, Any]:
    session = instance.session
    return {"instance_id": session["instance_id"], "pid": session.get("pid", -1), "mode": "gui",
            "bridge_state": instance.state, "blender_version": session.get("blender_version", "?"),
            "blender_supported": instance.blender_supported,
            "version_warning": instance.version_warning, "scene_path": None, "scene_revision": None}


def status_impl(discovery: Discovery, instance_selector: str | None = None) -> dict[str, Any]:
    deadline = _deadline(OVERALL_BUDGET)
    discovered, stats = discovery.instances_with_stats(deadline=deadline)
    instances = [item for item in discovered if instance_selector is None
                 or item.session["instance_id"] == instance_selector]
    partial, skipped = stats.partial, stats.skipped_count
    live = [item for item in instances if item.client is not None]
    results: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    invalidate = False
    acquired = bool(live) and deadline > time.monotonic() and _STATUS_AGGREGATION_LOCK.acquire(
        timeout=max(0.0, deadline - time.monotonic()))
    if live and not acquired:
        partial, skipped = True, skipped + len(live)
    if acquired:
        def call_status(item: Instance) -> dict[str, Any]:
            timeout = min(envelope.METHOD_TIMEOUTS["status"], deadline - time.monotonic())
            if timeout <= 0:
                raise BridgeError(envelope.BRIDGE_TIMEOUT, "status", retryable=True)
            assert item.client is not None
            result = item.client.call("status", None, timeout, deadline=deadline)
            if (type(result) is not dict or type(result.get("instance_id")) is not str
                    or result["instance_id"] != item.session["instance_id"]
                    or type(result.get("scene_revision")) is not int
                    or "scene_path" not in result
                    or type(result.get("scene_path")) not in (str, type(None))):
                raise ValueError("malformed status result")
            return result

        futures: dict[Future[dict[str, Any]], Instance] = {}
        try:
            for index, item in enumerate(live):
                if time.monotonic() >= deadline:
                    partial, skipped = True, skipped + len(live) - index
                    break
                futures[_STATUS_EXECUTOR.submit(call_status, item)] = item
            complete = 0
            try:
                for future in as_completed(futures, timeout=max(0.0, deadline - time.monotonic())):
                    complete += 1
                    item = futures[future]
                    try:
                        results[item.session["instance_id"]] = future.result()
                    except BridgeError as exc:
                        failures[item.session["instance_id"]] = exc.code
                        invalidate |= exc.code != envelope.BRIDGE_BUSY
                    except Exception:
                        failures[item.session["instance_id"]] = envelope.BRIDGE_UNAVAILABLE
                        invalidate = True
            except TimeoutError:
                partial, skipped, invalidate = True, skipped + len(futures) - complete, True
        finally:
            for future in futures:
                future.cancel()
            _STATUS_AGGREGATION_LOCK.release()
    if invalidate and not discovery.invalidate(deadline=deadline):
        partial, skipped = True, skipped + 1
    rows = []
    for item in instances:
        row = _row(item)
        result = results.get(row["instance_id"])
        if result is not None:
            row.update(bridge_state="connected", scene_path=result["scene_path"],
                       scene_revision=result["scene_revision"])
        elif failures.get(row["instance_id"]) == envelope.BRIDGE_BUSY:
            row["bridge_state"] = "busy"
        elif row["instance_id"] in failures or (item.client is not None and item.state != "busy"):
            row["bridge_state"] = "disconnected"
        rows.append(row)
    connected = any(row["bridge_state"] == "connected" for row in rows)
    return {"ok": True, "guidance": None if connected else GUIDANCE, "partial": partial,
            "skipped_count": skipped, "instances": rows}


def scene_summary_impl(discovery: Discovery, instance_id: str, include_collections: bool = True,
                       include_managed_objects: bool = True) -> dict[str, Any]:
    deadline = _deadline(SCENE_SUMMARY_BUDGET)
    instance, stats = discovery.find_with_stats(instance_id, deadline=deadline)
    if instance is None:
        if stats.partial:
            raise ToolFailure(envelope.BRIDGE_UNAVAILABLE, "discovery incomplete", True)
        raise ToolFailure("INSTANCE_NOT_FOUND", instance_id)
    if instance.envelope_mismatch:
        raise ToolFailure(envelope.ENVELOPE_VERSION_MISMATCH, instance.version_warning or "")
    if instance.client is None:
        raise ToolFailure(envelope.BRIDGE_UNAVAILABLE, "bridge disconnected", True)
    try:
        result = instance.client.call("scene_summary", {
            "include_collections": include_collections, "include_managed_objects": include_managed_objects,
        }, timeout=max(0.0, deadline - time.monotonic()), deadline=deadline)
    except BridgeError as exc:
        discovery.invalidate(deadline=deadline)
        raise ToolFailure(exc.code, str(exc), exc.retryable) from exc
    if type(result) is not dict or type(result.get("summary")) is not dict:
        raise ValueError("malformed scene_summary result")
    summary = dict(result["summary"])
    if not include_collections:
        summary["collections"] = []
    if not include_managed_objects:
        summary["managed_objects"] = []
    return {"instance_id": instance_id, "scene_name": result["scene_name"],
            "scene_revision": result["scene_revision"], "scene_hash": result["scene_hash"],
            "scene_path": result.get("scene_path"), "version_warning": instance.version_warning,
            "units": result["units"], "summary": summary}


def capabilities_impl(discovery: Discovery, include_instances: bool = False) -> dict[str, Any]:
    connected: list[dict[str, Any]] = []
    partial = False
    skipped = 0
    if include_instances:
        instances, stats = discovery.instances_with_stats(deadline=_deadline(OVERALL_BUDGET))
        connected = [item.session for item in instances if item.client is not None]
        partial, skipped = stats.partial, stats.skipped_count
    result = describe(SERVER_VERSION, connected)
    result.update(instances_partial=partial, instances_skipped_count=skipped)
    return result


async def _audit_and_validate_tool_call(ctx: ServerRequestContext[Any, Any],
                                        call_next: CallNext) -> HandlerResult:
    if ctx.method != "tools/call" or ctx.params is None:
        return await call_next(ctx)
    name = ctx.params.get("name")
    arguments = ctx.params.get("arguments", {})
    tool = name if isinstance(name, str) else "<invalid>"
    safe_args = dict(arguments) if isinstance(arguments, Mapping) else {}
    started = time.monotonic()
    token = _ACTIVE_DEADLINE.set(started + (SCENE_SUMMARY_BUDGET if tool == "get_scene_summary"
                                             else OVERALL_BUDGET))
    try:
        audit = _deps()[1]
    except Exception as exc:
        _ACTIVE_DEADLINE.reset(token)
        raise MCPError(-32000, "audit unavailable",
                       {"code": "AUDIT_UNAVAILABLE", "retryable": True}) from exc
    error: str | None = None
    admitted = False
    try:
        allowed = _TOOL_ARGUMENTS.get(tool)
        if allowed is not None and isinstance(arguments, Mapping):
            unknown = sorted(set(arguments) - allowed)
            if unknown:
                raise MCPError(INVALID_PARAMS, "unknown arguments",
                               {"tool": tool, "unknown": unknown})
            for argument, expected in _TOOL_TYPES[tool].items():
                if argument in arguments and type(arguments[argument]) not in expected:
                    raise MCPError(INVALID_PARAMS, "invalid type",
                                   {"tool": tool, "argument": argument})
        if tool == "get_scene_summary":
            admitted = _SCENE_SUMMARY_ADMISSION.acquire(blocking=False)
            if not admitted:
                raise MCPError(-32000, "scene summary capacity exhausted",
                               {"code": envelope.BRIDGE_BUSY, "retryable": True})
        result = await call_next(ctx)
        if getattr(result, "is_error", False) or (isinstance(result, Mapping)
                                                    and result.get("isError") is True):
            error = "TOOL_ERROR"
        return result
    except BaseException as exc:
        data = getattr(exc, "data", None)
        code = data.get("code") if isinstance(data, Mapping) else None
        error = code if isinstance(code, str) else str(getattr(exc, "code", type(exc).__name__))
        raise
    finally:
        try:
            audit.record(tool, ctx.request_id if ctx.request_id is not None else "<missing>",
                         ok=error is None, duration_ms=(time.monotonic() - started) * 1000,
                         instance_id=safe_args.get("instance_id") if isinstance(
                             safe_args.get("instance_id"), str) else None,
                         params=safe_args, error=error,
                         deadline=time.monotonic() + AUDIT_LOCK_TIMEOUT)
        except Exception as exc:
            raise MCPError(-32000, "audit unavailable",
                           {"code": "AUDIT_UNAVAILABLE", "retryable": True}) from exc
        finally:
            if admitted:
                _SCENE_SUMMARY_ADMISSION.release()
            _ACTIVE_DEADLINE.reset(token)


mcp = MCPServer("blender-codex", version=SERVER_VERSION, instructions=INSTRUCTIONS,
                middleware=[_audit_and_validate_tool_call])


@mcp.tool()
def get_blender_status(instance_selector: str | None = None) -> StatusResult:
    """列出 Blender 实例、Bridge 连接状态与场景概况。无实例时返回引导文案。"""
    return StatusResult.model_validate(status_impl(_deps()[0], instance_selector))


@mcp.tool()
def get_scene_summary(instance_id: str, include_collections: bool = True,
                      include_managed_objects: bool = True) -> SceneSummaryResult:
    """返回指定实例的场景摘要：对象统计、单位、scene_hash 与受管对象清单。"""
    discovery = _deps()[0]
    try:
        return SceneSummaryResult.model_validate(scene_summary_impl(
            discovery, instance_id, include_collections, include_managed_objects))
    except ToolFailure as exc:
        raise MCPError(-32000, str(exc), {"code": exc.code, "retryable": exc.retryable}) from exc
    except (KeyError, TypeError, ValueError) as exc:
        discovery.invalidate(deadline=time.monotonic())
        raise MCPError(-32000, "malformed scene_summary result",
                       {"code": envelope.BRIDGE_UNAVAILABLE, "retryable": True}) from exc


@mcp.tool()
def describe_capabilities(include_instances: bool = False) -> CapabilitiesResult:
    """返回本 Server 能力：支持的工具、IR 版本、Blender 基线。默认不连 Bridge。"""
    return CapabilitiesResult.model_validate(capabilities_impl(_deps()[0], include_instances))


def _close_input_schemas() -> None:
    for tool in mcp._tool_manager._tools.values():  # noqa: SLF001
        if isinstance(tool.parameters, dict):
            tool.parameters["additionalProperties"] = False


_close_input_schemas()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
