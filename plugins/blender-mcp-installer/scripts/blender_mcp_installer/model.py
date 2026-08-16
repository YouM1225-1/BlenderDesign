from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping
from uuid import UUID


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_UTC_RFC3339 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")


class ImageState(str, Enum):
    ABSENT = "absent"
    PRESENT = "present"


class BoundaryRole(str, Enum):
    DATA_ROOT = "data_root"
    STATE_ROOT = "state_root"
    CODEX_HOME = "codex_home"
    BLENDER_RESOURCES = "blender_resources"
    BLENDER_CONFIG = "blender_config"
    BLENDER_EXTENSIONS = "blender_extensions"
    TARGET_PARENT = "target_parent"


class TargetRole(str, Enum):
    RUNTIME = "runtime"
    BLENDER_EXTENSION = "blender_extension"
    BLENDER_USERPREF = "blender_userpref"
    CODEX_CONFIG = "codex_config"
    ACTIVE_SELECTOR = "active_selector"


class ReceiptStatus(str, Enum):
    PREPARED = "prepared"
    INSTALLED = "installed"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CONFLICT = "conflict"


class ActionKind(str, Enum):
    BUNDLE_STAGE = "bundle_stage"
    RUNTIME_TREE = "runtime_tree"
    EXTENSION_TREE = "extension_tree"
    USERPREF_FILE = "userpref_file"
    CODEX_FILE = "codex_file"


class ObjectKind(str, Enum):
    BUNDLE = "bundle"
    TREE = "tree"
    FILE = "file"
    CODEX = "codex"


class ActionState(str, Enum):
    PLANNED = "planned"
    STAGED = "staged"
    SWAPPED = "swapped"
    PARKED = "parked"
    PUBLISHED = "published"
    COMPLETED = "completed"
    SEMANTIC_STAGED = "semantic_staged"
    SEMANTIC_SWAPPED = "semantic_swapped"
    RESTORING = "restoring"
    RESTORED = "restored"
    CLEANED = "cleaned"


def _mapping(value: object, keys: tuple[str, ...], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(keys) or len(value) != len(keys):
        raise ValueError(f"invalid {label} schema")
    return value


def _integer(value: object, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or (positive and value <= 0) or (not positive and value < 0):
        raise ValueError(f"invalid {label}")
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"invalid {label}")
    return value


def _basename(value: object, label: str) -> str:
    name = _string(value, label)
    if (
        Path(name).name != name
        or "/" in name
        or "\\" in name
        or "\0" in name
        or name in {".", ".."}
    ):
        raise ValueError(f"invalid {label}")
    return name


def _hash(value: object, label: str) -> str:
    if type(value) is not str or not _HASH.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _optional_hash(value: object, label: str) -> str | None:
    return None if value is None else _hash(value, label)


def _uuid4(value: object, label: str) -> UUID:
    if type(value) is not str:
        raise ValueError(f"invalid {label}")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"invalid {label}") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError(f"invalid {label}")
    return parsed


@dataclass(frozen=True)
class FileImage:
    state: ImageState
    dev: int | None
    ino: int | None
    uid: int | None
    mode: int | None
    size: int | None
    mtime_ns: int | None
    sha256: str | None

    def __post_init__(self) -> None:
        values = (self.dev, self.ino, self.uid, self.mode, self.size, self.mtime_ns)
        if self.state is ImageState.ABSENT:
            if any(value is not None for value in (*values, self.sha256)):
                raise ValueError("absent file image has metadata")
            return
        if self.state is not ImageState.PRESENT or any(
            type(value) is not int or value < 0 for value in values
        ):
            raise ValueError("invalid present file metadata")
        _hash(self.sha256, "file image hash")

    @classmethod
    def absent(cls) -> FileImage:
        return cls(ImageState.ABSENT, None, None, None, None, None, None, None)

    @classmethod
    def from_dict(cls, value: object) -> FileImage:
        item = _mapping(
            value,
            ("state", "dev", "ino", "uid", "mode", "size", "mtime_ns", "sha256"),
            "file image",
        )
        try:
            state = ImageState(item["state"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid file image state") from exc
        return cls(
            state,
            item["dev"],
            item["ino"],
            item["uid"],
            item["mode"],
            item["size"],
            item["mtime_ns"],
            item["sha256"],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "dev": self.dev,
            "ino": self.ino,
            "uid": self.uid,
            "mode": self.mode,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class TreeEntry:
    path: str
    kind: str
    dev: int
    ino: int
    uid: int
    mode: int
    size: int
    mtime_ns: int
    sha256: str | None

    def __post_init__(self) -> None:
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ValueError("invalid tree entry path")
        if self.kind not in {"file", "dir"}:
            raise ValueError("invalid tree entry kind")
        if any(
            type(value) is not int or value < 0
            for value in (self.dev, self.ino, self.uid, self.mode, self.size, self.mtime_ns)
        ):
            raise ValueError("invalid tree entry metadata")
        if self.kind == "file":
            _hash(self.sha256, "tree entry hash")
        elif self.sha256 is not None:
            raise ValueError("directory tree entry has a file hash")

    @classmethod
    def from_dict(cls, value: object) -> TreeEntry:
        item = _mapping(
            value,
            ("path", "kind", "dev", "ino", "uid", "mode", "size", "mtime_ns", "sha256"),
            "tree entry",
        )
        return cls(
            item["path"],
            item["kind"],
            item["dev"],
            item["ino"],
            item["uid"],
            item["mode"],
            item["size"],
            item["mtime_ns"],
            item["sha256"],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "dev": self.dev,
            "ino": self.ino,
            "uid": self.uid,
            "mode": self.mode,
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class TreeImage:
    state: ImageState
    dev: int | None
    ino: int | None
    uid: int | None
    mode: int | None
    mtime_ns: int | None
    digest: str | None
    entries: tuple[TreeEntry, ...]

    def __post_init__(self) -> None:
        if type(self.entries) is not tuple or any(
            type(entry) is not TreeEntry for entry in self.entries
        ):
            raise ValueError("invalid tree entries")
        values = (self.dev, self.ino, self.uid, self.mode, self.mtime_ns)
        if self.state is ImageState.ABSENT:
            if any(value is not None for value in (*values, self.digest)) or self.entries:
                raise ValueError("absent tree image has metadata")
            return
        if self.state is not ImageState.PRESENT or any(
            type(value) is not int or value < 0 for value in values
        ):
            raise ValueError("invalid present tree metadata")
        _hash(self.digest, "tree digest")
        paths = tuple(entry.path for entry in self.entries)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("tree entries are not uniquely sorted")
        if any(entry.uid != self.uid for entry in self.entries):
            raise ValueError("tree contains a foreign-owned entry")
        encoded = json.dumps(
            [entry.to_dict() for entry in self.entries], sort_keys=True, separators=(",", ":")
        ).encode()
        if hashlib.sha256(encoded).hexdigest() != self.digest:
            raise ValueError("tree digest does not match its entries")

    @classmethod
    def absent(cls) -> TreeImage:
        return cls(ImageState.ABSENT, None, None, None, None, None, None, ())

    @classmethod
    def from_dict(cls, value: object) -> TreeImage:
        item = _mapping(
            value,
            ("state", "dev", "ino", "uid", "mode", "mtime_ns", "digest", "entries"),
            "tree image",
        )
        if type(item["entries"]) is not list:
            raise ValueError("invalid tree entries")
        try:
            state = ImageState(item["state"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid tree image state") from exc
        return cls(
            state,
            item["dev"],
            item["ino"],
            item["uid"],
            item["mode"],
            item["mtime_ns"],
            item["digest"],
            tuple(TreeEntry.from_dict(entry) for entry in item["entries"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "dev": self.dev,
            "ino": self.ino,
            "uid": self.uid,
            "mode": self.mode,
            "mtime_ns": self.mtime_ns,
            "digest": self.digest,
            "entries": [entry.to_dict() for entry in self.entries],
        }


Image = FileImage | TreeImage


@dataclass(frozen=True)
class BlenderPaths:
    executable: Path
    architecture: str
    version: str
    user_resources: Path
    user_config: Path
    user_extensions: Path

    def __post_init__(self) -> None:
        _string(self.architecture, "Blender architecture")
        _string(self.version, "Blender version")
        paths = (self.executable, self.user_resources, self.user_config, self.user_extensions)
        if not all(path.is_absolute() and ".." not in path.parts for path in paths):
            raise ValueError("Blender paths must be absolute")
        if not self.user_config.is_relative_to(
            self.user_resources
        ) or not self.user_extensions.is_relative_to(self.user_resources):
            raise ValueError("Blender config and extensions must descend from resources")


@dataclass(frozen=True)
class InstallRoots:
    source_distribution_root: Path
    distribution_root: Path
    bundle_root: Path
    home: Path
    codex_home: Path
    blender: BlenderPaths
    codex_config: Path
    data_root: Path
    runtime: Path
    state_root: Path
    lock: Path
    receipts: Path
    pending: Path
    active: Path
    extension_target: Path
    userpref_target: Path

    @classmethod
    def discover(
        cls,
        home: Path,
        codex_home: Path | None,
        blender: BlenderPaths,
        *,
        source_distribution_root: Path,
        distribution_root: Path,
    ) -> InstallRoots:
        paths = (home, source_distribution_root, distribution_root)
        if codex_home is not None:
            paths += (codex_home,)
        if any(not path.is_absolute() or ".." in path.parts for path in paths):
            raise ValueError("install roots must be absolute")
        selected_codex_home = codex_home or home / ".codex"
        data_root = home / ".local/share/blender-lab-mcp"
        state_root = home / ".local/state/blender-mcp-installer"
        return cls(
            source_distribution_root,
            distribution_root,
            distribution_root / "plugins/blender-mcp-installer/artifacts",
            home,
            selected_codex_home,
            blender,
            selected_codex_home / "config.toml",
            data_root,
            data_root / "runtime",
            state_root,
            state_root / "installer.lock",
            state_root / "receipts",
            state_root / "pending.json",
            state_root / "active.json",
            blender.user_extensions / "user_default/mcp",
            blender.user_config / "userpref.blend",
        )

    def receipt(self, install_id: UUID) -> Path:
        return self.receipts / f"{install_id}.json"

    def backups(self, install_id: UUID) -> Path:
        return self.state_root / "backups" / str(install_id)

    def previous_active(self, install_id: UUID) -> Path:
        return self.backups(install_id) / "previous-active.json"

    def bundle_stage(self, install_id: UUID) -> Path:
        return self.state_root / "stages" / str(install_id) / "bundle"

    def runtime_stage(self, install_id: UUID) -> Path:
        return self.data_root / f".blender-mcp-installer.{install_id}.runtime.stage"

    def runtime_recovery(self, install_id: UUID) -> Path:
        return self.data_root / f".blender-mcp-installer.{install_id}.runtime.recovery"

    def extension_stage(self, install_id: UUID) -> Path:
        return self.extension_target.parent / f".blender-mcp-installer.{install_id}.extension.stage"

    def extension_recovery(self, install_id: UUID) -> Path:
        return (
            self.extension_target.parent / f".blender-mcp-installer.{install_id}.extension.recovery"
        )

    def userpref_stage(self, install_id: UUID) -> Path:
        return self.userpref_target.parent / f".blender-mcp-installer.{install_id}.userpref.stage"

    def userpref_recovery(self, install_id: UUID) -> Path:
        return (
            self.userpref_target.parent / f".blender-mcp-installer.{install_id}.userpref.recovery"
        )

    def codex_stage(self, install_id: UUID) -> Path:
        return self.codex_home / f".blender-mcp-installer.{install_id}.codex.stage"

    def codex_recovery(self, install_id: UUID) -> Path:
        return self.codex_home / f".blender-mcp-installer.{install_id}.codex.recovery"

    def codex_rollback_stage(self, install_id: UUID) -> Path:
        return self.codex_home / f".blender-mcp-installer.{install_id}.codex.rollback.stage"


@dataclass(frozen=True)
class ActiveSelector:
    schema_version: int
    generation: int
    install_id: UUID
    receipt_basename: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("invalid selector schema version")
        _integer(self.generation, "selector generation", positive=True)
        if type(self.install_id) is not UUID or self.install_id.version != 4:
            raise ValueError("invalid selector install ID")
        if _basename(self.receipt_basename, "receipt basename") != f"{self.install_id}.json":
            raise ValueError("selector receipt basename does not match install ID")

    @classmethod
    def from_dict(cls, value: object) -> ActiveSelector:
        item = _mapping(
            value,
            ("schema_version", "generation", "install_id", "receipt_basename"),
            "active selector",
        )
        if type(item["schema_version"]) is not int or item["schema_version"] != 1:
            raise ValueError("invalid selector schema version")
        generation = _integer(item["generation"], "selector generation", positive=True)
        install_id = _uuid4(item["install_id"], "selector install ID")
        basename = _basename(item["receipt_basename"], "receipt basename")
        if basename != f"{install_id}.json":
            raise ValueError("selector receipt basename does not match install ID")
        return cls(1, generation, install_id, basename)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "generation": self.generation,
            "install_id": str(self.install_id),
            "receipt_basename": self.receipt_basename,
        }


@dataclass(frozen=True)
class PendingSelector:
    schema_version: int
    generation: int
    install_id: UUID
    receipt_basename: str
    manifest_sha256: str
    previous_active: ActiveSelector | None

    def __post_init__(self) -> None:
        ActiveSelector(self.schema_version, self.generation, self.install_id, self.receipt_basename)
        _hash(self.manifest_sha256, "manifest hash")
        if self.previous_active is not None and type(self.previous_active) is not ActiveSelector:
            raise ValueError("invalid previous active selector")

    @classmethod
    def from_dict(cls, value: object) -> PendingSelector:
        item = _mapping(
            value,
            (
                "schema_version",
                "generation",
                "install_id",
                "receipt_basename",
                "manifest_sha256",
                "previous_active",
            ),
            "pending selector",
        )
        active = ActiveSelector.from_dict(
            {
                key: item[key]
                for key in ("schema_version", "generation", "install_id", "receipt_basename")
            }
        )
        previous = item["previous_active"]
        if previous is not None:
            previous = ActiveSelector.from_dict(previous)
        return cls(
            1,
            active.generation,
            active.install_id,
            active.receipt_basename,
            _hash(item["manifest_sha256"], "manifest hash"),
            previous,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "generation": self.generation,
            "install_id": str(self.install_id),
            "receipt_basename": self.receipt_basename,
            "manifest_sha256": self.manifest_sha256,
            "previous_active": None
            if self.previous_active is None
            else self.previous_active.to_dict(),
        }


_ACTION_KEYS = (
    "ordinal",
    "kind",
    "object_kind",
    "state",
    "target_role",
    "target_path",
    "stage_basename",
    "recovery_basename",
    "pre",
    "intended_post",
    "actual_post",
    "recovery_image",
    "rollback_intended",
    "rollback_displaced",
)
_OBJECTS = {
    ActionKind.BUNDLE_STAGE: ObjectKind.BUNDLE,
    ActionKind.RUNTIME_TREE: ObjectKind.TREE,
    ActionKind.EXTENSION_TREE: ObjectKind.TREE,
    ActionKind.USERPREF_FILE: ObjectKind.FILE,
    ActionKind.CODEX_FILE: ObjectKind.CODEX,
}
_ROLES = {
    ActionKind.RUNTIME_TREE: TargetRole.RUNTIME,
    ActionKind.EXTENSION_TREE: TargetRole.BLENDER_EXTENSION,
    ActionKind.USERPREF_FILE: TargetRole.BLENDER_USERPREF,
    ActionKind.CODEX_FILE: TargetRole.CODEX_CONFIG,
}


def _parse_image(value: object, tree: bool) -> Image | None:
    if value is None:
        return None
    return TreeImage.from_dict(value) if tree else FileImage.from_dict(value)


@dataclass(frozen=True)
class ReceiptAction:
    ordinal: int
    kind: ActionKind
    object_kind: ObjectKind
    state: ActionState
    target_role: TargetRole | None
    target_path: Path
    stage_basename: str
    recovery_basename: str | None
    pre: Image
    intended_post: Image | None
    actual_post: Image | None
    recovery_image: Image | None
    rollback_intended: Image | None
    rollback_displaced: Image | None

    def __post_init__(self) -> None:
        _integer(self.ordinal, "action ordinal")
        if type(self.kind) is not ActionKind or type(self.object_kind) is not ObjectKind:
            raise ValueError("invalid action kind")
        if type(self.state) is not ActionState:
            raise ValueError("invalid action state")
        if self.target_role is not None and type(self.target_role) is not TargetRole:
            raise ValueError("invalid action target role")
        if (
            not isinstance(self.target_path, Path)
            or not self.target_path.is_absolute()
            or ".." in self.target_path.parts
        ):
            raise ValueError("invalid action target path")
        _basename(self.stage_basename, "action stage basename")
        if self.recovery_basename is not None:
            _basename(self.recovery_basename, "action recovery basename")
        tree = self.kind in {
            ActionKind.BUNDLE_STAGE,
            ActionKind.RUNTIME_TREE,
            ActionKind.EXTENSION_TREE,
        }
        image_type = TreeImage if tree else FileImage
        if type(self.pre) is not image_type:
            raise ValueError("invalid action preimage variant")
        for image in (
            self.intended_post,
            self.actual_post,
            self.recovery_image,
            self.rollback_intended,
            self.rollback_displaced,
        ):
            if image is not None and type(image) is not image_type:
                raise ValueError("invalid action image variant")
        for image in (
            self.intended_post,
            self.actual_post,
            self.rollback_intended,
            self.rollback_displaced,
        ):
            if image is not None and image.state is not ImageState.PRESENT:
                raise ValueError("action post/recovery images must be present")
        if (
            self.recovery_image is not None
            and self.recovery_image.state is not ImageState.PRESENT
            and self.state not in {ActionState.RESTORED, ActionState.CLEANED}
        ):
            raise ValueError("action post/recovery images must be present")
        if self.kind is ActionKind.BUNDLE_STAGE:
            if (
                self.object_kind is not ObjectKind.BUNDLE
                or self.target_role is not None
                or self.recovery_basename is not None
                or self.pre.state is not ImageState.ABSENT
            ):
                raise ValueError("invalid bundle action identity")
            if self.state not in {
                ActionState.PLANNED,
                ActionState.STAGED,
                ActionState.CLEANED,
            }:
                raise ValueError("invalid bundle action state")
            required = self.state in {ActionState.STAGED, ActionState.CLEANED}
            if (self.intended_post is not None) != required or any(
                value is not None
                for value in (
                    self.actual_post,
                    self.recovery_image,
                    self.rollback_intended,
                    self.rollback_displaced,
                )
            ):
                raise ValueError("invalid bundle action images")
            return
        if self.object_kind is not _OBJECTS[self.kind]:
            raise ValueError("action object kind mismatch")
        if self.target_role is not _ROLES[self.kind] or self.recovery_basename is None:
            raise ValueError("invalid managed action identity")
        present = self.pre.state is ImageState.PRESENT
        forward = {
            ActionState.PLANNED,
            ActionState.STAGED,
            ActionState.COMPLETED,
            ActionState.RESTORING,
            ActionState.RESTORED,
            ActionState.CLEANED,
            *((ActionState.SWAPPED, ActionState.PARKED) if present else (ActionState.PUBLISHED,)),
        }
        semantic = {ActionState.SEMANTIC_STAGED, ActionState.SEMANTIC_SWAPPED}
        if self.kind is not ActionKind.CODEX_FILE and self.state in semantic:
            raise ValueError("semantic state is Codex-only")
        if self.state not in forward | (
            semantic if self.kind is ActionKind.CODEX_FILE and present else set()
        ):
            raise ValueError("invalid action transition")
        required_intended = self.state is not ActionState.PLANNED
        required_actual = self.state not in {ActionState.PLANNED, ActionState.STAGED}
        if (self.intended_post is not None) != required_intended or (
            self.actual_post is not None
        ) != required_actual:
            raise ValueError("invalid managed action image nullability")
        if self.actual_post is not None and self.intended_post != self.actual_post:
            raise ValueError("actual postimage does not match intended postimage")
        absent = image_type.absent()
        semantic_restore = self.kind is ActionKind.CODEX_FILE and (
            self.rollback_intended is not None or self.rollback_displaced is not None
        )
        if self.state in semantic:
            valid_recovery = self.recovery_image == self.pre
        elif self.state in {ActionState.PARKED, ActionState.COMPLETED} and present:
            valid_recovery = self.recovery_image == self.pre
        elif self.state is ActionState.RESTORING and semantic_restore:
            valid_recovery = self.recovery_image == self.pre
        elif self.state is ActionState.RESTORING and present:
            valid_recovery = self.recovery_image in {None, self.actual_post}
        elif self.state is ActionState.RESTORING:
            valid_recovery = self.recovery_image == self.actual_post
        elif self.state in {ActionState.RESTORED, ActionState.CLEANED}:
            valid_recovery = self.recovery_image == absent
        else:
            valid_recovery = self.recovery_image is None
        if not valid_recovery:
            raise ValueError("invalid managed action recovery image")
        if self.state is ActionState.SEMANTIC_STAGED:
            if self.rollback_intended is None or self.rollback_displaced is not None:
                raise ValueError("invalid semantic staged images")
        elif self.state is ActionState.SEMANTIC_SWAPPED:
            if self.rollback_intended is None or self.rollback_displaced is None:
                raise ValueError("invalid semantic swapped images")
        elif self.kind is ActionKind.CODEX_FILE and self.state in {
            ActionState.RESTORING,
            ActionState.RESTORED,
        }:
            if (self.rollback_intended is None) != (self.rollback_displaced is None):
                raise ValueError("incomplete semantic rollback images")
        elif self.rollback_intended is not None or self.rollback_displaced is not None:
            raise ValueError("rollback images are semantic-only")

    def to_dict(self) -> dict[str, object]:
        def image(value: Image | None) -> object:
            return None if value is None else value.to_dict()

        return {
            "ordinal": self.ordinal,
            "kind": self.kind.value,
            "object_kind": self.object_kind.value,
            "state": self.state.value,
            "target_role": None if self.target_role is None else self.target_role.value,
            "target_path": str(self.target_path),
            "stage_basename": self.stage_basename,
            "recovery_basename": self.recovery_basename,
            "pre": image(self.pre),
            "intended_post": image(self.intended_post),
            "actual_post": image(self.actual_post),
            "recovery_image": image(self.recovery_image),
            "rollback_intended": image(self.rollback_intended),
            "rollback_displaced": image(self.rollback_displaced),
        }

    @classmethod
    def from_dict(cls, value: object) -> ReceiptAction:
        item = _mapping(value, _ACTION_KEYS, "receipt action")
        ordinal = _integer(item["ordinal"], "action ordinal")
        try:
            kind = ActionKind(item["kind"])
            object_kind = ObjectKind(item["object_kind"])
            state = ActionState(item["state"])
            target_role = None if item["target_role"] is None else TargetRole(item["target_role"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid action enum") from exc
        target_path = Path(_string(item["target_path"], "action target path"))
        stage_basename = _basename(item["stage_basename"], "action stage basename")
        recovery_basename = item["recovery_basename"]
        if recovery_basename is not None:
            recovery_basename = _basename(recovery_basename, "action recovery basename")
        tree = kind in {ActionKind.BUNDLE_STAGE, ActionKind.RUNTIME_TREE, ActionKind.EXTENSION_TREE}
        pre = _parse_image(item["pre"], tree)
        if pre is None:
            raise ValueError("action preimage is required")
        intended = _parse_image(item["intended_post"], tree)
        actual = _parse_image(item["actual_post"], tree)
        recovery = _parse_image(item["recovery_image"], tree)
        rollback_intended = _parse_image(item["rollback_intended"], False)
        rollback_displaced = _parse_image(item["rollback_displaced"], False)
        return cls(
            ordinal,
            kind,
            object_kind,
            state,
            target_role,
            target_path,
            stage_basename,
            recovery_basename,
            pre,
            intended,
            actual,
            recovery,
            rollback_intended,
            rollback_displaced,
        )


@dataclass(frozen=True)
class ReceiptTarget:
    role: TargetRole
    path: Path
    boundary_role: BoundaryRole
    pre: Image
    install_post: Image | None
    recovery_path: Path | None
    recovery_hash: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "path": str(self.path),
            "boundary_role": self.boundary_role.value,
            "pre": self.pre.to_dict(),
            "install_post": None if self.install_post is None else self.install_post.to_dict(),
            "recovery_path": None if self.recovery_path is None else str(self.recovery_path),
            "recovery_hash": self.recovery_hash,
        }

    @classmethod
    def from_dict(cls, value: object) -> ReceiptTarget:
        item = _mapping(
            value,
            (
                "role",
                "path",
                "boundary_role",
                "pre",
                "install_post",
                "recovery_path",
                "recovery_hash",
            ),
            "receipt target",
        )
        try:
            role = TargetRole(item["role"])
            boundary = BoundaryRole(item["boundary_role"])
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid target enum") from exc
        tree = role in {TargetRole.RUNTIME, TargetRole.BLENDER_EXTENSION}
        pre = _parse_image(item["pre"], tree)
        post = _parse_image(item["install_post"], tree)
        if pre is None:
            raise ValueError("target preimage is required")
        recovery_path = (
            None
            if item["recovery_path"] is None
            else Path(_string(item["recovery_path"], "target recovery path"))
        )
        recovery_hash = _optional_hash(item["recovery_hash"], "target recovery hash")
        if (recovery_path is None) != (recovery_hash is None):
            raise ValueError("target recovery path/hash mismatch")
        if recovery_path is not None:
            if pre.state is not ImageState.PRESENT:
                raise ValueError("absent target cannot have a protected preimage")
            expected_hash = pre.digest if isinstance(pre, TreeImage) else pre.sha256
            if recovery_hash != expected_hash:
                raise ValueError("target recovery hash does not match its preimage")
        return cls(
            role,
            Path(_string(item["path"], "target path")),
            boundary,
            pre,
            post,
            recovery_path,
            recovery_hash,
        )


@dataclass(frozen=True)
class Receipt:
    schema_version: int
    install_id: UUID
    generation: int
    parent_install_id: UUID | None
    status: ReceiptStatus
    created_at: str
    bundle: Mapping[str, object]
    host: Mapping[str, object]
    consent: Mapping[str, object]
    targets: tuple[ReceiptTarget, ...]
    actions: tuple[ReceiptAction, ...]
    verification: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "install_id": str(self.install_id),
            "generation": self.generation,
            "parent_install_id": (
                None if self.parent_install_id is None else str(self.parent_install_id)
            ),
            "status": self.status.value,
            "created_at": self.created_at,
            "bundle": dict(self.bundle),
            "host": dict(self.host),
            "consent": dict(self.consent),
            "targets": [target.to_dict() for target in self.targets],
            "actions": [action.to_dict() for action in self.actions],
            "verification": dict(self.verification),
        }


def parse_receipt(value: object, roots: InstallRoots) -> Receipt:
    item = _mapping(
        value,
        (
            "schema_version",
            "install_id",
            "generation",
            "parent_install_id",
            "status",
            "created_at",
            "bundle",
            "host",
            "consent",
            "targets",
            "actions",
            "verification",
        ),
        "receipt",
    )
    if type(item["schema_version"]) is not int or item["schema_version"] != 1:
        raise ValueError("invalid receipt schema version")
    install_id = _uuid4(item["install_id"], "receipt install ID")
    generation = _integer(item["generation"], "receipt generation", positive=True)
    parent = (
        None
        if item["parent_install_id"] is None
        else _uuid4(item["parent_install_id"], "parent install ID")
    )
    try:
        status = ReceiptStatus(item["status"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid receipt status") from exc
    created_at = _string(item["created_at"], "created_at")
    if not _UTC_RFC3339.fullmatch(created_at):
        raise ValueError("created_at must be UTC RFC 3339")
    try:
        parsed_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid created_at") from exc
    if (
        not created_at.endswith("Z")
        or parsed_time.utcoffset() is None
        or parsed_time.utcoffset().total_seconds() != 0
    ):
        raise ValueError("created_at must be UTC RFC 3339")
    bundle = _mapping(item["bundle"], ("version", "manifest_sha256"), "receipt bundle")
    _string(bundle["version"], "bundle version")
    _hash(bundle["manifest_sha256"], "bundle manifest hash")
    host = _mapping(
        item["host"],
        (
            "home",
            "codex_home",
            "blender_executable",
            "blender_architecture",
            "blender_version",
            "blender_user_resources",
            "blender_user_config",
            "blender_user_extensions",
            "codex_version",
            "uv_version",
            "python_version",
        ),
        "receipt host",
    )
    for key, expected in {
        "home": roots.home,
        "codex_home": roots.codex_home,
        "blender_executable": roots.blender.executable,
        "blender_user_resources": roots.blender.user_resources,
        "blender_user_config": roots.blender.user_config,
        "blender_user_extensions": roots.blender.user_extensions,
    }.items():
        if host[key] != str(expected):
            raise ValueError(f"receipt host {key} mismatch")
    for key in (
        "blender_architecture",
        "blender_version",
        "codex_version",
        "uv_version",
        "python_version",
    ):
        _string(host[key], f"receipt host {key}")
    if (
        host["blender_architecture"] != roots.blender.architecture
        or host["blender_version"] != roots.blender.version
    ):
        raise ValueError("receipt Blender identity mismatch")
    consent = _mapping(
        item["consent"], ("all_four_collected_for_this_workflow",), "receipt consent"
    )
    if consent["all_four_collected_for_this_workflow"] is not True:
        raise ValueError("invalid receipt consent marker")
    if type(item["targets"]) is not list or type(item["actions"]) is not list:
        raise ValueError("invalid receipt collections")
    targets = tuple(ReceiptTarget.from_dict(target) for target in item["targets"])
    expected_targets = (
        (TargetRole.RUNTIME, roots.runtime, BoundaryRole.DATA_ROOT),
        (TargetRole.BLENDER_EXTENSION, roots.extension_target, BoundaryRole.BLENDER_EXTENSIONS),
        (TargetRole.BLENDER_USERPREF, roots.userpref_target, BoundaryRole.BLENDER_CONFIG),
        (TargetRole.CODEX_CONFIG, roots.codex_config, BoundaryRole.CODEX_HOME),
        (TargetRole.ACTIVE_SELECTOR, roots.active, BoundaryRole.STATE_ROOT),
    )
    if (
        tuple((target.role, target.path, target.boundary_role) for target in targets)
        != expected_targets
    ):
        raise ValueError("receipt targets do not match derived paths")
    actions = tuple(ReceiptAction.from_dict(action) for action in item["actions"])
    ordinals = tuple(action.ordinal for action in actions)
    if ordinals != tuple(sorted(set(ordinals))):
        raise ValueError("receipt actions are not ordinal-sorted")
    expected_action_paths = {
        ActionKind.BUNDLE_STAGE: roots.bundle_stage(install_id),
        ActionKind.RUNTIME_TREE: roots.runtime,
        ActionKind.EXTENSION_TREE: roots.extension_target,
        ActionKind.USERPREF_FILE: roots.userpref_target,
        ActionKind.CODEX_FILE: roots.codex_config,
    }
    if any(action.target_path != expected_action_paths[action.kind] for action in actions):
        raise ValueError("receipt action path mismatch")
    expected_action_names = {
        ActionKind.BUNDLE_STAGE: ("bundle", None),
        ActionKind.RUNTIME_TREE: (
            roots.runtime_stage(install_id).name,
            roots.runtime_recovery(install_id).name,
        ),
        ActionKind.EXTENSION_TREE: (
            roots.extension_stage(install_id).name,
            roots.extension_recovery(install_id).name,
        ),
        ActionKind.USERPREF_FILE: (
            roots.userpref_stage(install_id).name,
            roots.userpref_recovery(install_id).name,
        ),
        ActionKind.CODEX_FILE: (
            roots.codex_stage(install_id).name,
            roots.codex_recovery(install_id).name,
        ),
    }
    if any(
        (action.stage_basename, action.recovery_basename) != expected_action_names[action.kind]
        for action in actions
    ):
        raise ValueError("receipt action basename mismatch")
    expected_recoveries = {
        TargetRole.RUNTIME: roots.runtime_recovery(install_id),
        TargetRole.BLENDER_EXTENSION: roots.extension_recovery(install_id),
        TargetRole.BLENDER_USERPREF: roots.userpref_recovery(install_id),
        TargetRole.CODEX_CONFIG: roots.codex_recovery(install_id),
        TargetRole.ACTIVE_SELECTOR: roots.previous_active(install_id),
    }
    if any(
        target.recovery_path is not None
        and target.recovery_path != expected_recoveries[target.role]
        for target in targets
    ):
        raise ValueError("receipt target recovery path mismatch")
    verification = _mapping(item["verification"], ("configured", "live"), "receipt verification")
    if (
        type(verification["configured"]) is not bool
        or type(verification["live"]) is not str
        or verification["live"] != "not_run"
    ):
        raise ValueError("invalid receipt verification")
    return Receipt(
        1,
        install_id,
        generation,
        parent,
        status,
        created_at,
        MappingProxyType(dict(bundle)),
        MappingProxyType(dict(host)),
        MappingProxyType(dict(consent)),
        targets,
        actions,
        MappingProxyType(dict(verification)),
    )
