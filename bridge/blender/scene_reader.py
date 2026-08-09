"""bpy 版 SceneReader。§3.5：主选 context.scene（SPIKE-1.3 已实测可用），回退 scenes[0]。"""
from __future__ import annotations

import hashlib
import heapq
from collections.abc import Generator

import bpy

from ..core import scene_hash
from ..core.contracts import (SceneSnapshot, SnapshotInvalidated,
                              SnapshotLimitExceeded)

MAX_SNAPSHOT_ITEMS = 1_000_000
MAX_SNAPSHOT_TEXT_BYTES = 64 * 1024 * 1024


class RevisionCounter:
    def __init__(self) -> None:
        self.value = 0
        self.generation = 0

    def bump(self) -> None:
        self.value += 1

    def bump_generation(self) -> None:
        """load_pre hook: invalidate every continuation before bpy frees old wrappers."""
        self.generation += 1
        self.value += 1


class BpySceneReader:
    def __init__(self, counter: RevisionCounter) -> None:
        self._counter = counter

    def blender_version(self) -> str:
        return bpy.app.version_string.split()[0]     # "5.2.0 LTS" → "5.2.0"

    def status_info(self) -> tuple[str | None, int]:
        return (bpy.data.filepath or None, self._counter.value)

    @staticmethod
    def _target_scene():
        return bpy.context.scene or bpy.data.scenes[0]

    @staticmethod
    def _object_line(obj) -> tuple[str, bool, bool, bool]:
        """Read one already-acquired wrapper and return only Python values."""
        obj_type = str(obj.type)
        matrix = tuple(float(v) for row in obj.matrix_world for v in row)
        data = getattr(obj, "data", None)
        if data is None:
            data_kind = ""
        else:
            data_rna = getattr(data, "bl_rna", None)
            data_kind = str(getattr(data_rna, "identifier", type(data).__name__))
        if obj_type == "MESH":
            if data is None:
                raise SnapshotInvalidated("mesh object has no data")
            counts = (len(data.vertices), len(data.edges), len(data.polygons))
        else:
            counts = ()
        line = scene_hash.object_line(str(obj.name), obj_type, matrix, data_kind, counts)
        return line, obj_type == "MESH", obj_type == "CAMERA", obj_type == "LIGHT"

    @staticmethod
    def _scene_info(scene_name: str) -> tuple[str, str | None, str, float]:
        scene = bpy.data.scenes.get(scene_name)
        if scene is None:
            raise SnapshotInvalidated("scene changed during snapshot")
        units = scene.unit_settings
        return (str(scene.name), bpy.data.filepath or None,
                str(units.system or "NONE"), float(units.scale_length))

    def _check_marker(self, revision: int, generation: int) -> None:
        if self._counter.value != revision or self._counter.generation != generation:
            raise SnapshotInvalidated("scene changed during snapshot")

    def snapshot_steps(self, *, include_collections: bool = True,
                       include_managed_objects: bool = True
                       ) -> Generator[None, None, SceneSnapshot]:
        """Cooperative snapshot: one bounded source/hash/collection batch per yield.

        bpy cannot safely move to a worker thread, so TaskQueue advances this generator on
        the main thread until its per-tick budget is consumed. Individual bpy property access
        remains an atomic, non-preemptible step; the queue records an honest cooperative bound.
        """
        scene = self._target_scene()
        scene_name = str(scene.name)
        object_count = len(scene.objects)
        if object_count > MAX_SNAPSHOT_ITEMS:
            raise SnapshotLimitExceeded("object item limit exceeded")
        del scene
        revision = self._counter.value
        generation = self._counter.generation
        chunks: list[tuple[str, ...]] = []
        object_text_bytes = 0
        n_mesh = n_cam = n_light = 0
        for start in range(0, object_count, 1024):
            self._check_marker(revision, generation)
            current_scene = bpy.data.scenes.get(scene_name)
            if current_scene is None or len(current_scene.objects) != object_count:
                raise SnapshotInvalidated("scene changed during snapshot")
            stop = min(start + 1024, object_count)
            try:
                # Blender's collection slice walks forward in C; numeric indexing
                # walks from the head and made the old implementation O(N²).
                batch = current_scene.objects[start:stop]
            except (ReferenceError, RuntimeError, TypeError) as exc:
                raise SnapshotInvalidated("scene changed during snapshot") from exc
            del current_scene
            batch_lines: list[str] = []
            obj = None
            try:
                for obj in batch:
                    line, is_mesh, is_camera, is_light = self._object_line(obj)
                    object_text_bytes += len(line.encode("utf-8"))
                    if object_text_bytes > MAX_SNAPSHOT_TEXT_BYTES:
                        raise SnapshotLimitExceeded("object text limit exceeded")
                    batch_lines.append(line)
                    n_mesh += is_mesh
                    n_cam += is_camera
                    n_light += is_light
            except SnapshotLimitExceeded:
                raise
            except (ReferenceError, RuntimeError, TypeError) as exc:
                raise SnapshotInvalidated("scene changed during snapshot") from exc
            finally:
                obj = None
                batch.clear()
            self._check_marker(revision, generation)
            batch_lines.sort()
            chunks.append(tuple(batch_lines))
            batch_lines.clear()
            yield

        # 必须与 scene_hash.digest() 用同一算法——本文件是它的分块增量版本，
        # 两者对同一场景必须产出逐字相同的摘要（见 test_scene_reader 的一致性用例）
        digest = hashlib.sha256()
        first = True
        hash_steps = 0
        for line in heapq.merge(*chunks):
            self._check_marker(revision, generation)
            if not first:
                digest.update(b"\n")
            digest.update(line.encode("utf-8"))
            first = False
            hash_steps += 1
            if hash_steps == 128:
                hash_steps = 0
                yield
        if hash_steps:
            yield

        # The hash is complete; release all per-object strings before optionally
        # materializing collection names so the two bounded working sets do not
        # overlap.  ``line`` is reset to release the last merge item as well.
        line = ""
        chunks.clear()

        collections: list[str] = []
        if include_collections:
            collection_count = len(bpy.data.collections)
            if collection_count > MAX_SNAPSHOT_ITEMS:
                raise SnapshotLimitExceeded("collection item limit exceeded")
            collection_text_bytes = 0
            for start in range(0, collection_count, 128):
                self._check_marker(revision, generation)
                if len(bpy.data.collections) != collection_count:
                    raise SnapshotInvalidated("scene changed during snapshot")
                stop = min(start + 128, collection_count)
                try:
                    batch = bpy.data.collections[start:stop]
                except (ReferenceError, RuntimeError, TypeError) as exc:
                    raise SnapshotInvalidated("scene changed during snapshot") from exc
                collection = None
                try:
                    names: list[str] = []
                    for collection in batch:
                        name = str(collection.name)
                        collection_text_bytes += len(name.encode("utf-8"))
                        if collection_text_bytes > MAX_SNAPSHOT_TEXT_BYTES:
                            raise SnapshotLimitExceeded("collection text limit exceeded")
                        names.append(name)
                    collections.extend(names)
                    names.clear()
                except SnapshotLimitExceeded:
                    raise
                except (ReferenceError, RuntimeError, TypeError) as exc:
                    raise SnapshotInvalidated("scene changed during snapshot") from exc
                finally:
                    collection = None
                    batch.clear()
                self._check_marker(revision, generation)
                yield
        self._check_marker(revision, generation)
        name, path, units_system, units_scale = self._scene_info(scene_name)
        self._check_marker(revision, generation)
        return SceneSnapshot(
            scene_revision=revision,
            scene_hash="sha256:" + digest.hexdigest(),
            scene_name=name,
            scene_path=path,
            units_system=units_system,
            units_scale_length=units_scale,
            object_count=object_count, mesh_count=n_mesh,
            camera_count=n_cam, light_count=n_light,
            collections=tuple(collections),
            managed_objects=(),  # Phase 0 恒空；flag 为未来受管对象源端裁剪预留
        )
