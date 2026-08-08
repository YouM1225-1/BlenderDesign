import json
import logging
from collections.abc import Generator

from bridge.core.contracts import SceneSnapshot, SnapshotLimitExceeded
from bridge.core.router import BridgeMeta, Router
from protocol import envelope, framing


class FakeReader:
    def blender_version(self) -> str:
        return "5.2.0"

    def status_info(self):
        return ("/tmp/a.blend", 7)

    def snapshot_steps(
        self,
        *,
        include_collections: bool = True,
        include_managed_objects: bool = True,
    ) -> Generator[None, None, SceneSnapshot]:
        if False:
            yield
        return SceneSnapshot(
            scene_revision=7,
            scene_hash="sha256:abc",
            scene_name="Scene",
            scene_path="/tmp/a.blend",
            units_system="METRIC",
            units_scale_length=1.0,
            object_count=3,
            mesh_count=1,
            camera_count=1,
            light_count=1,
            collections=(("Collection",) if include_collections else ()),
        )


META = BridgeMeta(
    instance_id="gui-1-aa", pid=1, bridge_version="0.1.0", blender_version="5.2.0"
)


def call(
    method: str, params: dict | None = None, reader: FakeReader | None = None
) -> dict:
    router = Router(reader or FakeReader(), META)
    result = router.handle(envelope.Request.new("t", method, params or {}))
    if isinstance(result, bytes):
        frame = result
    else:
        while True:
            try:
                next(result)
            except StopIteration as done:
                frame = done.value
                break
    return json.loads(framing.FrameBuffer().feed(frame)[0])


def test_ping_carries_identity_and_envelope_version():
    result = call("ping")["result"]
    assert result == {
        "instance_id": "gui-1-aa",
        "bridge_version": "0.1.0",
        "blender_version": "5.2.0",
        "envelope_version": 1,
    }


def test_status_is_lightweight_shape():
    result = call("status")["result"]
    assert result == {
        "instance_id": "gui-1-aa",
        "pid": 1,
        "mode": "gui",
        "blender_version": "5.2.0",
        "scene_path": "/tmp/a.blend",
        "scene_revision": 7,
    }


def test_scene_summary_matches_spec_shape():
    result = call("scene_summary")["result"]
    assert result["scene_hash"] == "sha256:abc"
    assert result["scene_name"] == "Scene"
    assert result["units"] == {"system": "METRIC", "scale_length": 1.0}
    assert result["summary"]["object_count"] == 3
    assert result["summary"]["managed_objects"] == []


def test_scene_summary_flags_reach_reader_and_crop_at_source():
    class RecordingReader(FakeReader):
        seen: tuple[bool, bool] | None = None

        def snapshot_steps(
            self,
            *,
            include_collections: bool = True,
            include_managed_objects: bool = True,
        ) -> Generator[None, None, SceneSnapshot]:
            self.seen = (include_collections, include_managed_objects)
            return (yield from super().snapshot_steps(
                include_collections=include_collections,
                include_managed_objects=include_managed_objects,
            ))

    reader = RecordingReader()
    result = call(
        "scene_summary",
        {"include_collections": False, "include_managed_objects": False},
        reader,
    )
    assert reader.seen == (False, False)
    assert result["result"]["summary"]["collections"] == []
    assert result["result"]["summary"]["managed_objects"] == []


def test_scene_summary_resource_limit_is_structured(caplog):
    class LimitedReader(FakeReader):
        def snapshot_steps(
            self,
            *,
            include_collections: bool = True,
            include_managed_objects: bool = True,
        ) -> Generator[None, None, SceneSnapshot]:
            if False:
                yield
            raise SnapshotLimitExceeded("test limit")

    with caplog.at_level(logging.WARNING, logger="bcx.bridge"):
        result = call("scene_summary", reader=LimitedReader())
    assert result["ok"] is False
    assert result["error"]["code"] == envelope.INTERNAL_LIMIT_EXCEEDED
    assert any("resource limit exceeded" in record.message for record in caplog.records)


def test_unknown_method():
    body = call("nope")
    assert body["ok"] is False
    assert body["error"]["code"] == envelope.UNKNOWN_METHOD
