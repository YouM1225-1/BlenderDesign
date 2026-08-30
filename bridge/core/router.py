"""method → 响应帧。认证已由 I/O 层完成，本层假设请求可信格式已校验。"""
from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import dataclass

from ._proto import envelope
from ._proto import framing
from .contracts import SceneReader, SnapshotLimitExceeded

_diag = logging.getLogger("bcx.bridge")
# Bounded room for the response envelope and fixed-size scene metadata.
MAX_COLLECTION_WIRE_BYTES = framing.MAX_FRAME - 64 * 1024


@dataclass(frozen=True)
class BridgeMeta:
    instance_id: str
    pid: int
    bridge_version: str
    blender_version: str


class Router:
    def __init__(self, reader: SceneReader, meta: BridgeMeta) -> None:
        self._reader = reader
        self._meta = meta

    def handle(self, req: envelope.Request) -> bytes | Generator[None, None, bytes]:
        if req.method == "ping":
            return envelope.ok_frame(req.id, {
                "instance_id": self._meta.instance_id,
                "bridge_version": self._meta.bridge_version,
                "blender_version": self._meta.blender_version,
                "envelope_version": envelope.ENVELOPE_VERSION,
            })
        if req.method == "status":
            scene_path, scene_revision = self._reader.status_info()
            return envelope.ok_frame(req.id, {
                "instance_id": self._meta.instance_id, "pid": self._meta.pid,
                "mode": "gui", "blender_version": self._meta.blender_version,
                "scene_path": scene_path, "scene_revision": scene_revision,
            })
        if req.method == "scene_summary":
            include_collections = req.params.get("include_collections", True)
            include_managed = req.params.get("include_managed_objects", True)
            if not isinstance(include_collections, bool) or not isinstance(include_managed, bool):
                return envelope.error_frame(req.id, envelope.SCENE_QUERY_FAILED,
                                            "invalid scene_summary parameters")
            return self._scene_summary(req.id, include_collections, include_managed)
        return envelope.error_frame(req.id, envelope.UNKNOWN_METHOD, req.method)

    def _scene_summary(self, request_id: str, include_collections: bool,
                       include_managed_objects: bool) -> Generator[None, None, bytes]:
        try:
            snapshot = yield from self._reader.snapshot_steps(
                include_collections=include_collections,
                include_managed_objects=include_managed_objects,
            )
        except SnapshotLimitExceeded:
            _diag.warning("scene snapshot resource limit exceeded (request %s)", request_id)
            return envelope.error_frame(
                request_id, envelope.INTERNAL_LIMIT_EXCEEDED,
                "scene snapshot exceeds resource limit",
            )
        return (yield from envelope.ok_frame_steps(request_id, {
            "scene_revision": snapshot.scene_revision, "scene_hash": snapshot.scene_hash,
            "scene_name": snapshot.scene_name, "scene_path": snapshot.scene_path,
            "units": {"system": snapshot.units_system,
                      "scale_length": snapshot.units_scale_length},
            "summary": {
                "object_count": snapshot.object_count, "mesh_count": snapshot.mesh_count,
                "camera_count": snapshot.camera_count, "light_count": snapshot.light_count,
                # JSONEncoder serializes tuples as arrays; avoid a second O(N) copy here.
                "collections": (snapshot.collections if include_collections else []),
                "managed_objects": ([
                    {"stable_id": item.stable_id, "name": item.name, "type": item.type}
                    for item in snapshot.managed_objects
                ] if include_managed_objects else []),
            },
        }))
