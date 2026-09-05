"""L2 harness：真 bridge/core + Fake bpy 侧。§7.2。"""
from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Generator

from bridge.core.contracts import SceneSnapshot
from bridge.core.lifecycle import BridgeSession


class FakeSceneReader:
    def __init__(self, blender_version: str = "5.2.0", n_collections: int = 1,
                 raise_on_snapshot: Exception | None = None) -> None:
        self._v = blender_version
        self._n = n_collections
        self._raise = raise_on_snapshot

    def blender_version(self) -> str:
        return self._v

    def status_info(self):
        return (None, 1)

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        if self._raise is not None:
            raise self._raise
        collections: list[str] = []
        if include_collections:
            for i in range(self._n):
                collections.append(f"C{i:06d}")
                yield
        return SceneSnapshot(
            scene_revision=1, scene_hash="sha256:fake", scene_name="Scene",
            scene_path=None, units_system="METRIC", units_scale_length=1.0,
            object_count=0, mesh_count=0, camera_count=0, light_count=0,
            collections=tuple(collections),
        )


@contextlib.contextmanager
def live_bridge(tmp_path, **reader_kw):
    reader = FakeSceneReader(**reader_kw)
    session = BridgeSession.start(tmp_path, reader,
                                  blender_version=reader.blender_version())
    stop = threading.Event()
    paused = threading.Event()

    def pump():
        while not stop.is_set() and not session.stopped:
            if paused.is_set():
                time.sleep(0.01)
                continue
            time.sleep(session.tick(50))

    session.pause_pump = paused.set          # type: ignore[attr-defined]  # 测试挂件
    session.resume_pump = paused.clear       # type: ignore[attr-defined]

    t = threading.Thread(target=pump, daemon=True)
    t.start()
    try:
        yield session, reader, tmp_path / "run"
    finally:
        stop.set()
        session.stop()
        t.join(timeout=2)
