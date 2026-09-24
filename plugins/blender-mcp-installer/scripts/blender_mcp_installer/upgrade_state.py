from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Iterator
from uuid import UUID, uuid4

from blender_mcp_installer.filesystem import (
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    TargetRef,
    capture_file,
    load_atomic_json_pair,
    load_state_json,
    reconcile_atomic_json,
    write_atomic_json,
)
from blender_mcp_installer.model import FileImage, ImageState, TreeImage

VERSION = re.compile(r"[A-Za-z0-9.+-]+\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
STATUSES = {"awaiting_verification", "cleanup_pending", "complete", "cancelled"}
KINDS = {"runtime_recovery", "extension_recovery", "plugin_cache"}
ROW_STATES = {"pending", "deferred_in_use", "conflict", "removed"}
# Schema 2 stores each candidate image once, content-addressed, beside the journals.
IMAGES = PurePath("upgrades", "images")


def uuid_text(value: object) -> str:
    if type(value) is not str:
        raise InstallerError("invalid workflow UUID")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise InstallerError("invalid workflow UUID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise InstallerError("invalid workflow UUID")
    return value


def absolute(value: object) -> Path:
    if type(value) is not str:
        raise InstallerError("invalid absolute path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        raise InstallerError("invalid absolute path")
    return path


def exact(value: object, keys: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(keys.split()):
        raise InstallerError("invalid upgrade schema")
    return value


@dataclass(frozen=True)
class UpgradeRoots:
    home: Path
    codex_home: Path

    @property
    def state(self) -> Path:
        return self.home / ".local/state/blender-mcp-installer"

    @property
    def projections(self) -> Path:
        return self.home / ".local/share/blender-mcp-installer/marketplaces/official-blender-mcp"

    @property
    def caches(self) -> Path:
        return self.codex_home / "plugins/cache/official-blender-mcp/blender-mcp-installer"

    def __post_init__(self) -> None:
        absolute(str(self.home))
        absolute(str(self.codex_home))


def _validate_record(raw: object, roots: UpgradeRoots) -> dict[str, Any]:
    doc = exact(raw, "schema_version id revision mode status home codex_home desired profile "
                "registration install_id candidates findings verification retired_receipts "
                "retired_registrations")
    if type(doc["schema_version"]) is not int or doc["schema_version"] not in {1, 2}:
        raise InstallerError("unsupported upgrade schema")
    uuid_text(doc["id"])
    if type(doc["revision"]) is not int or doc["revision"] < 0:
        raise InstallerError("invalid upgrade revision")
    if doc["mode"] not in {"install", "register"} or doc["status"] not in STATUSES:
        raise InstallerError("invalid upgrade mode or status")
    if (doc["home"], doc["codex_home"]) != (str(roots.home), str(roots.codex_home)):
        raise InstallerError("upgrade host mismatch")
    wanted = exact(doc["desired"], "commit manifest_sha256 bundle_version plugin_version projection")
    if (type(wanted["commit"]) is not str or not COMMIT.fullmatch(wanted["commit"])
            or type(wanted["manifest_sha256"]) is not str
            or not HASH.fullmatch(wanted["manifest_sha256"])
            or type(wanted["bundle_version"]) is not str or not wanted["bundle_version"]
            or type(wanted["plugin_version"]) is not str
            or not VERSION.fullmatch(wanted["plugin_version"])
            or wanted["plugin_version"] in {".", ".."}):
        raise InstallerError("invalid upgrade release identity")
    if wanted["projection"] != str(roots.projections / wanted["commit"]):
        raise InstallerError("upgrade projection mismatch")
    if doc["profile"] is not None:
        profile = exact(doc["profile"], "executable architecture version resources config extensions")
        for key in ("executable", "resources", "config", "extensions"):
            absolute(profile[key])
        if not all(type(profile[key]) is str and profile[key] for key in ("architecture", "version")):
            raise InstallerError("invalid Blender identity")
        if not all(Path(profile[key]).is_relative_to(Path(profile["resources"]))
                   for key in ("config", "extensions")):
            raise InstallerError("invalid Blender profile boundary")
    if doc["registration"] is not None:
        registration = exact(doc["registration"], "id state")
        uuid_text(registration["id"])
        if registration["state"] not in {"prepared", "registered", "failed", "restored"}:
            raise InstallerError("invalid registration state")
    if doc["install_id"] is not None:
        uuid_text(doc["install_id"])
    if doc["mode"] == "register" and (doc["profile"] is not None or doc["install_id"] is not None):
        raise InstallerError("registration workflow contains Blender state")
    verification = exact(doc["verification"], "registration live")
    if any(value not in {"not_run", "passed", "failed"} for value in verification.values()):
        raise InstallerError("invalid verification state")
    if type(doc["candidates"]) is not list or type(doc["findings"]) is not list:
        raise InstallerError("invalid upgrade collections")
    seen: set[str] = set()
    for row in doc["candidates"]:
        row = exact(row, "key kind owner version expected proofs content_source content_sha256 "
                     "lease_known state reason")
        if row["kind"] not in KINDS or row["state"] not in ROW_STATES:
            raise InstallerError("invalid cleanup candidate")
        if type(row["key"]) is not str or row["key"] in seen:
            raise InstallerError("duplicate cleanup candidate")
        seen.add(row["key"])
        uuid_text(row["owner"])
        if row["kind"] == "plugin_cache":
            if (type(row["version"]) is not str or not VERSION.fullmatch(row["version"])
                    or row["version"] in {".", ".."}):
                raise InstallerError("invalid cache version")
            expected_key = "plugin_cache:" + row["version"]
        else:
            if row["version"] is not None or doc["mode"] != "install" or doc["profile"] is None:
                raise InstallerError("invalid recovery candidate")
            expected_key = row["kind"] + ":" + row["owner"]
        if row["key"] != expected_key or type(row["lease_known"]) is not bool:
            raise InstallerError("invalid candidate key")
        if type(row["reason"]) is not str:
            raise InstallerError("invalid candidate reason")
        image = TreeImage.from_dict(row["expected"])
        if image.state is not ImageState.PRESENT:
            raise InstallerError("candidate must retain its original present image")
        if type(row["proofs"]) is not list or not row["proofs"]:
            raise InstallerError("missing candidate proof")
        for proof in row["proofs"]:
            proof = exact(proof, "relative expected")
            path = PurePath(proof["relative"])
            if (path.is_absolute() or ".." in path.parts
                    or path.as_posix() != proof["relative"]
                    or not path.parts
                    or path.parts[0] not in {"receipts", "marketplace-recovery", "upgrades"}):
                raise InstallerError("invalid proof path")
            if path.parts[0] == "upgrades":
                if len(path.parts) != 2 or not path.name.endswith(".json"):
                    raise InstallerError("invalid upgrade proof path")
                uuid_text(path.name[:-5])
            if FileImage.from_dict(proof["expected"]).state is not ImageState.PRESENT:
                raise InstallerError("missing proof image")
        if row["kind"] == "plugin_cache":
            source = absolute(row["content_source"])
            if (source.name != "blender-mcp-installer" or source.parent.name != "plugins"
                    or source.parent.parent.parent != roots.projections
                    or not COMMIT.fullmatch(source.parent.parent.name)):
                raise InstallerError("invalid historical projection")
            if type(row["content_sha256"]) is not str or not HASH.fullmatch(row["content_sha256"]):
                raise InstallerError("invalid historical content hash")
        elif row["content_source"] is not None or row["content_sha256"] is not None:
            raise InstallerError("unexpected recovery content source")
    if not all(type(item) is dict and set(item) == {"path", "reason"}
               and all(type(value) is str for value in item.values()) for item in doc["findings"]):
        raise InstallerError("invalid discovery finding")
    for key in ("retired_receipts", "retired_registrations"):
        if type(doc[key]) is not list or len(doc[key]) != len(set(doc[key])):
            raise InstallerError("invalid retirement list")
        for value in doc[key]:
            if key == "retired_receipts":
                uuid_text(value)
            elif (type(value) is not str
                    or not re.fullmatch(r"marketplace-recovery/registration\.[A-Za-z0-9_-]+", value)):
                raise InstallerError("invalid retired registration reference")
    if doc["status"] in {"cleanup_pending", "complete"}:
        if verification["registration"] != "passed":
            raise InstallerError("cleanup lacks registration verification")
        if doc["mode"] == "install" and (verification["live"] != "passed"
                or doc["install_id"] is None or doc["profile"] is None):
            raise InstallerError("cleanup lacks live installation verification")
    if doc["status"] == "complete" and any(row["state"] != "removed" for row in doc["candidates"]):
        raise InstallerError("completed cleanup has remaining candidates")
    return copy.deepcopy(doc)


def validate_record(raw: object, roots: UpgradeRoots) -> dict[str, Any]:
    try:
        return _validate_record(raw, roots)
    except (TypeError, ValueError, KeyError) as exc:
        raise InstallerError("invalid upgrade schema") from exc


def new_record(roots: UpgradeRoots, mode: str, desired: dict[str, str],
               workflow_id: str | None = None) -> dict[str, Any]:
    return validate_record({
        "schema_version": 2, "id": workflow_id or str(uuid4()), "revision": 0,
        "mode": mode, "status": "awaiting_verification", "home": str(roots.home),
        "codex_home": str(roots.codex_home), "desired": desired, "profile": None,
        "registration": None, "install_id": None, "candidates": [], "findings": [],
        "verification": {"registration": "not_run", "live": "not_run"},
        "retired_receipts": [], "retired_registrations": [],
    }, roots)


def follows(old: dict[str, Any] | None, new: dict[str, Any]) -> bool:
    if old is None:
        return new["revision"] == 0 and new["status"] == "awaiting_verification"
    if new["revision"] != old["revision"] + 1:
        return False
    if any(new[key] != old[key] for key in ("schema_version", "id", "mode", "home",
                                           "codex_home", "desired")):
        return False
    allowed = {
        "awaiting_verification": {"awaiting_verification", "cleanup_pending", "cancelled"},
        "cleanup_pending": {"cleanup_pending", "complete"},
        "complete": {"complete"},
        "cancelled": {"cancelled"},
    }
    if new["status"] not in allowed[old["status"]]:
        return False
    if old["install_id"] is not None and new["install_id"] != old["install_id"]:
        return False
    if old["profile"] is not None and new["profile"] != old["profile"]:
        return False
    if old["status"] in {"cleanup_pending", "complete", "cancelled"}:
        for key in ("profile", "registration", "install_id", "retired_receipts",
                    "retired_registrations", "findings", "verification"):
            if new[key] != old[key]:
                return False
        if len(old["candidates"]) != len(new["candidates"]):
            return False
        for before, after in zip(old["candidates"], new["candidates"], strict=True):
            if any(before[key] != after[key] for key in before if key not in {"state", "reason"}):
                return False
            if before["state"] == "removed" and after["state"] != "removed":
                return False
    return True


@contextmanager
def state_root(roots: UpgradeRoots) -> Iterator[SafeRoot]:
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        relative = roots.state.relative_to(roots.home)
        fd = home.open_directory(relative, create=True)
        os.close(fd)
    with SafeRoot.open(roots.state, os.getuid(), roots.home) as state:
        fd = state.open_directory(PurePath("upgrades"), create=True)
        os.close(fd)
        yield state


def record_ids(state: SafeRoot) -> tuple[str, ...]:
    try:
        fd = state.open_directory(PurePath("upgrades"))
    except FileNotFoundError:
        return ()
    try:
        names = os.listdir(fd)
    finally:
        os.close(fd)
    result: set[str] = set()
    for name in names:
        match = re.fullmatch(r"([0-9a-f-]{36})\.json", name)
        if match:
            result.add(uuid_text(match[1]))
        match = re.fullmatch(r"\.blender-mcp-installer\.([0-9a-f-]{36})\.\1\.json\.tmp", name)
        if match:
            result.add(uuid_text(match[1]))
    return tuple(sorted(result))


def _image_bytes(image: object) -> bytes:
    # The same canonical encoding write_atomic_json publishes.
    return json.dumps(image, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def encode_record(doc: dict[str, Any]) -> dict[str, Any]:
    """Return the stored form of a journal; schema 2 references its candidate images."""
    stored = copy.deepcopy(doc)
    if stored["schema_version"] == 2:
        for row in stored["candidates"]:
            digest = hashlib.sha256(_image_bytes(row["expected"])).hexdigest()
            row["expected"] = {"image_sha256": digest}
    return stored


def _decode_record(state: SafeRoot, raw: object) -> object:
    if type(raw) is not dict or raw.get("schema_version") != 2:
        return raw
    decoded = copy.deepcopy(raw)
    rows = decoded.get("candidates")
    for row in rows if type(rows) is list else ():
        if type(row) is not dict:
            continue
        digest = exact(row.get("expected"), "image_sha256")["image_sha256"]
        if type(digest) is not str or not HASH.fullmatch(digest):
            raise InstallerError("invalid candidate image reference")
        try:
            image = load_state_json(TargetRef(state, IMAGES / (digest + ".json")))
        except (OSError, ValueError) as exc:
            raise InstallerError("candidate image is missing or changed") from exc
        if image is None or hashlib.sha256(_image_bytes(image)).hexdigest() != digest:
            raise InstallerError("candidate image is missing or changed")
        row["expected"] = image
    return decoded


def _store_images(state: SafeRoot, doc: dict[str, Any], fault: Any) -> None:
    """Durably publish every candidate image before a journal can reference it."""
    if doc["schema_version"] != 2 or not doc["candidates"]:
        return
    os.close(state.open_directory(IMAGES, create=True))
    upgrades = state.open_directory(PurePath("upgrades"))
    try:
        os.fsync(upgrades)
    finally:
        os.close(upgrades)
    for row in doc["candidates"]:
        digest = hashlib.sha256(_image_bytes(row["expected"])).hexdigest()
        ref = TargetRef(state, IMAGES / (digest + ".json"))
        current = capture_file(state, ref.relative)
        if current.state is ImageState.PRESENT:
            if current.sha256 != digest or current.mode != 0o600:
                raise InstallerError("candidate image is missing or changed")
            continue
        write_atomic_json(ref, current, row["expected"], UUID(doc["id"]), fault=fault)


def load_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str,
                *, recover: bool = False) -> dict[str, Any] | None:
    workflow_id = uuid_text(workflow_id)
    ref = TargetRef(state, PurePath("upgrades", workflow_id + ".json"))
    live, stale = load_atomic_json_pair(ref, UUID(workflow_id))
    current = None if live is None else validate_record(_decode_record(state, live), roots)
    temporary = None if stale is None else validate_record(_decode_record(state, stale), roots)
    if any(doc is not None and doc["id"] != workflow_id for doc in (current, temporary)):
        raise InstallerError("upgrade filename identity mismatch")
    if temporary is None:
        return current
    transitions = []
    if follows(current, temporary):
        transitions.append((current, temporary))
    if current is not None and follows(temporary, current):
        transitions.append((temporary, current))
    if len(transitions) != 1:
        raise InstallerError("upgrade journal recovery conflict")
    if not recover:
        raise InstallerError("upgrade journal needs reconciliation")
    old, new = transitions[0]
    stored_old = None if old is None else encode_record(old)
    reconcile_atomic_json(ref, [(stored_old, encode_record(new))], UUID(workflow_id),
                          fault=NoOpFaultInjector())
    return new


def save_record(state: SafeRoot, roots: UpgradeRoots, old: dict[str, Any] | None,
                new: dict[str, Any], fault: Any = None) -> dict[str, Any]:
    new = validate_record(new, roots)
    if not follows(old, new):
        raise InstallerError("invalid upgrade transition")
    ref = TargetRef(state, PurePath("upgrades", new["id"] + ".json"))
    actual = load_record(state, roots, new["id"])
    if actual != old:
        raise InstallerError("upgrade journal changed concurrently")
    fault = fault or NoOpFaultInjector()
    _store_images(state, new, fault)
    write_atomic_json(ref, capture_file(state, ref.relative), encode_record(new), UUID(new["id"]),
                      fault=fault)
    return new


def update_record(state: SafeRoot, roots: UpgradeRoots, old: dict[str, Any],
                  *, fault: Any = None, **changes: Any) -> dict[str, Any]:
    new = copy.deepcopy(old)
    new.update(changes)
    new["revision"] += 1
    return save_record(state, roots, old, new, fault=fault)


def load_any_record(state: SafeRoot, roots: UpgradeRoots, workflow_id: str,
                    *, recover: bool = False) -> dict[str, Any] | None:
    workflow_id = uuid_text(workflow_id)
    ref = TargetRef(state, PurePath("upgrades", workflow_id + ".json"))
    live, stale = load_atomic_json_pair(ref, UUID(workflow_id))
    seed = live if live is not None else stale
    if seed is None:
        return None
    if type(seed) is not dict or seed.get("home") != str(roots.home):
        raise InstallerError("foreign or malformed shared-home upgrade record")
    selected = UpgradeRoots(roots.home, absolute(seed.get("codex_home")))
    return load_record(state, selected, workflow_id, recover=recover)
