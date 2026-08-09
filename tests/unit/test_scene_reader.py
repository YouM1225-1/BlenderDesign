# tests/unit/test_scene_reader.py
import importlib
import sys
import types
from pathlib import Path

import pytest
from bridge.core import scene_hash


class _BpyWrapper:
    pass


class _NamedList(list):
    def __init__(self, items=()) -> None:
        super().__init__(items)
        self.slice_calls = 0

    def get(self, name):
        return next((item for item in self if item.name == name), None)

    def __getitem__(self, key):
        if isinstance(key, int):
            raise AssertionError("scene reader must use bounded collection slices")
        self.slice_calls += 1
        return super().__getitem__(key)


class _MeshData(_BpyWrapper):
    def __init__(self) -> None:
        self.bl_rna = types.SimpleNamespace(identifier="Mesh")
        self.vertices = [None] * 8
        self.edges = [None] * 12
        self.polygons = [None] * 6


class _CurveData(_BpyWrapper):
    bl_rna = types.SimpleNamespace(identifier="Curve")


class _CameraData(_BpyWrapper):
    bl_rna = types.SimpleNamespace(identifier="Camera")


class _LightData(_BpyWrapper):
    bl_rna = types.SimpleNamespace(identifier="Light")


_UNSET = object()


class _Object(_BpyWrapper):
    def __init__(self, name: str, x: float, obj_type: str = "MESH", data=_UNSET) -> None:
        self.name = name
        self.type = obj_type
        if data is _UNSET:
            data = {"MESH": _MeshData(), "CAMERA": _CameraData(),
                    "LIGHT": _LightData(), "CURVE": _CurveData()}.get(obj_type)
        self.data = data
        self.matrix_world = tuple(
            tuple(float(row * 4 + column) + x for column in range(4))
            for row in range(4)
        )


class _Scene(_BpyWrapper):
    def __init__(self, objects) -> None:
        self.name = "Scene"
        self.objects = _NamedList(objects)
        self.unit_settings = types.SimpleNamespace(system="METRIC", scale_length=1.0)


class _Collection(_BpyWrapper):
    def __init__(self, name: str) -> None:
        self.name = name


def _load_scene_reader(monkeypatch, object_count: int = 2, *, mixed: bool = False,
                       collection_count: int = 2):
    scene = _Scene([_Object(f"Cube{i:04d}", float(i)) for i in range(object_count)])
    if mixed:
        scene.objects.extend([
            _Object("Camera", 0.0, "CAMERA"),
            _Object("Sun", 0.0, "LIGHT"),
            _Object("Curve", 0.0, "CURVE"),
            _Object("Empty", 0.0, "EMPTY", None),
        ])
    bpy = types.ModuleType("bpy")
    bpy.app = types.SimpleNamespace(version_string="5.2.0 LTS")
    bpy.context = types.SimpleNamespace(scene=scene)
    bpy.data = types.SimpleNamespace(
        scenes=_NamedList([scene]),
        collections=_NamedList([_Collection(f"C{i:04d}")
                                for i in range(collection_count)]),
        filepath="/tmp/a.blend",
    )
    monkeypatch.setitem(sys.modules, "bpy", bpy)

    # Import the submodule without executing bridge/blender/__init__.py, whose panel/driver
    # dependencies need the full Blender runtime. Relative imports still resolve normally.
    package = types.ModuleType("bridge.blender")
    package.__path__ = [str(Path(__file__).parents[2] / "bridge" / "blender")]
    package.__package__ = "bridge.blender"
    monkeypatch.setitem(sys.modules, "bridge.blender", package)
    monkeypatch.delitem(sys.modules, "bridge.blender.scene_reader", raising=False)
    return importlib.import_module("bridge.blender.scene_reader"), scene


def _finish(steps):
    while True:
        try:
            next(steps)
        except StopIteration as done:
            return done.value


def test_snapshot_steps_hold_no_bpy_wrappers_and_generation_invalidates(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch)
    counter = module.RevisionCounter()
    steps = module.BpySceneReader(counter).snapshot_steps()

    next(steps)
    def contains_wrapper(value, seen=None):
        if isinstance(value, _BpyWrapper):
            return True
        if seen is None:
            seen = set()
        if id(value) in seen:
            return False
        seen.add(id(value))
        if isinstance(value, dict):
            return any(contains_wrapper(v, seen) for v in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(contains_wrapper(v, seen) for v in value)
        return False

    assert not any(contains_wrapper(value)
                   for value in steps.gi_frame.f_locals.values())

    counter.bump_generation()
    with pytest.raises(module.SnapshotInvalidated, match="scene changed"):
        next(steps)


def test_snapshot_steps_preserve_hash_and_optional_collections(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch)
    snapshot = _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
        include_collections=False,
    ))
    lines = [scene_hash.object_line(
        obj.name, obj.type, tuple(value for row in obj.matrix_world for value in row),
        "Mesh", (8, 12, 6),
    ) for obj in scene.objects]

    assert snapshot.scene_hash == scene_hash.digest(lines)
    assert snapshot.object_count == 2 and snapshot.mesh_count == 2
    assert snapshot.collections == ()


def test_object_line_uses_data_rna_identifier_and_handles_empty_data(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch)
    curve = _Object("Curve", 0.0)
    curve.type = "CURVE"
    curve.data = _CurveData()
    line, is_mesh, is_camera, is_light = module.BpySceneReader._object_line(curve)
    assert line.split("\t")[3] == "Curve"
    assert (is_mesh, is_camera, is_light) == (False, False, False)

    empty = _Object("Empty", 0.0)
    empty.type = "EMPTY"
    empty.data = None
    empty_line, *_ = module.BpySceneReader._object_line(empty)
    assert empty_line.split("\t")[3] == ""


def test_snapshot_counts_and_exact_data_kinds_for_mixed_scene(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch, object_count=1025, mixed=True,
                                       collection_count=130)
    reader = module.BpySceneReader(module.RevisionCounter())
    steps = reader.snapshot_steps(include_collections=True)
    yielded = 0
    while True:
        try:
            next(steps)
        except StopIteration as done:
            snapshot = done.value
            break
        yielded += 1
        frame_locals = steps.gi_frame.f_locals
        assert all(not _contains_wrapper(value) for value in frame_locals.values())
        if "collection_text_bytes" in frame_locals:
            assert frame_locals["chunks"] == []  # object strings freed before collections

    assert yielded >= 4  # object source, hash, and 130-item collection batches
    assert (snapshot.object_count, snapshot.mesh_count,
            snapshot.camera_count, snapshot.light_count) == (1029, 1025, 1, 1)
    expected_kinds = {"MESH": "Mesh", "CAMERA": "Camera", "LIGHT": "Light",
                      "CURVE": "Curve", "EMPTY": ""}
    lines = []
    for obj in scene.objects:
        line, *_ = reader._object_line(obj)
        assert line.split("\t")[3] == expected_kinds[obj.type]
        lines.append(line)
    assert snapshot.scene_hash == scene_hash.digest(lines)


def _contains_wrapper(value, seen=None):
    if isinstance(value, _BpyWrapper):
        return True
    if seen is None:
        seen = set()
    if id(value) in seen:
        return False
    seen.add(id(value))
    if isinstance(value, dict):
        return any(_contains_wrapper(v, seen) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_wrapper(v, seen) for v in value)
    return False


def test_chunked_hash_matches_digest_across_multiple_sort_chunks(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch, object_count=2050)
    snapshot = _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
        include_collections=False,
    ))
    lines = [scene_hash.object_line(
        obj.name, obj.type, tuple(value for row in obj.matrix_world for value in row),
        "Mesh", (8, 12, 6),
    ) for obj in scene.objects]

    assert snapshot.scene_hash == scene_hash.digest(lines)


def test_scene_info_race_invalidates_before_snapshot_publish(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch)
    counter = module.RevisionCounter()
    reader = module.BpySceneReader(counter)
    original = module.BpySceneReader._scene_info

    def bump_before_return(scene_name):
        result = original(scene_name)
        counter.bump()
        return result

    monkeypatch.setattr(module.BpySceneReader, "_scene_info",
                        staticmethod(bump_before_return))
    with pytest.raises(module.SnapshotInvalidated, match="scene changed"):
        _finish(reader.snapshot_steps(include_collections=False))


def test_snapshot_reader_rejects_object_text_before_unbounded_growth(monkeypatch):
    module, scene = _load_scene_reader(monkeypatch, object_count=2)
    assert module.MAX_SNAPSHOT_ITEMS == 1_000_000
    assert module.MAX_SNAPSHOT_TEXT_BYTES == 64 * 1024 * 1024

    monkeypatch.setattr(module, "MAX_SNAPSHOT_TEXT_BYTES", 1)
    with pytest.raises(module.SnapshotLimitExceeded, match="object text"):
        _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
            include_collections=False))
    assert scene.objects.slice_calls == 1

    module, scene = _load_scene_reader(monkeypatch, object_count=2)
    monkeypatch.setattr(module, "MAX_SNAPSHOT_ITEMS", 1)
    with pytest.raises(module.SnapshotLimitExceeded, match="object item"):
        _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
            include_collections=False))
    assert scene.objects.slice_calls == 0


def test_snapshot_reader_caps_collection_items_and_skips_unrequested_source(monkeypatch):
    module, _scene = _load_scene_reader(monkeypatch, object_count=0,
                                       collection_count=2)
    collections = module.bpy.data.collections
    monkeypatch.setattr(module, "MAX_SNAPSHOT_ITEMS", 1)
    with pytest.raises(module.SnapshotLimitExceeded, match="collection item"):
        _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps())
    assert collections.slice_calls == 0

    snapshot = _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps(
        include_collections=False))
    assert snapshot.collections == ()
    assert collections.slice_calls == 0

    module, _scene = _load_scene_reader(monkeypatch, object_count=0,
                                       collection_count=2)
    collections = module.bpy.data.collections
    monkeypatch.setattr(module, "MAX_SNAPSHOT_TEXT_BYTES", 1)
    with pytest.raises(module.SnapshotLimitExceeded, match="collection text"):
        _finish(module.BpySceneReader(module.RevisionCounter()).snapshot_steps())
    assert collections.slice_calls == 1
