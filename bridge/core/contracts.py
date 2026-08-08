"""core 与 bpy 世界之间的唯一边界。禁止 import bpy。spec §3.4。"""
from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ManagedObject:
    stable_id: str
    name: str
    type: str


@dataclass(frozen=True)
class SceneSnapshot:
    scene_revision: int
    scene_hash: str
    scene_name: str
    scene_path: str | None
    units_system: str
    units_scale_length: float
    object_count: int
    mesh_count: int
    camera_count: int
    light_count: int
    collections: tuple[str, ...]
    managed_objects: tuple[ManagedObject, ...] = ()


class SceneReader(Protocol):
    def blender_version(self) -> str: ...
    def status_info(self) -> tuple[str | None, int]: ...
    def snapshot_steps(
        self, *, include_collections: bool = True, include_managed_objects: bool = True
    ) -> Generator[None, None, SceneSnapshot]: ...


class SnapshotInvalidated(RuntimeError):
    """The scene changed or reloaded while a cooperative snapshot was in progress."""


class SnapshotLimitExceeded(RuntimeError):
    """The bounded reader working-set admission limit was exceeded."""


class Clock(Protocol):
    def monotonic(self) -> float: ...
