import os
import sys
import stat
from pathlib import Path
from uuid import UUID, uuid1, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_state import (
    UpgradeRoots,
    load_record,
    load_any_record,
    new_record,
    record_ids,
    save_record,
    state_root,
    update_record,
    validate_record,
)


class _CrashAt:
    def __init__(self, point: str) -> None:
        self.point = point

    def hit(self, point: str) -> None:
        if point == self.point:
            raise RuntimeError(point)


def _roots(tmp_path: Path) -> UpgradeRoots:
    home = tmp_path / "home"
    codex = tmp_path / "codex"
    home.mkdir(mode=0o700)
    codex.mkdir(mode=0o700)
    return UpgradeRoots(home, codex)


def _desired(roots: UpgradeRoots) -> dict[str, str]:
    return {
        "commit": "a" * 40,
        "manifest_sha256": "b" * 64,
        "bundle_version": "1.0.0",
        "plugin_version": "2",
        "projection": str(roots.projections / ("a" * 40)),
    }


def _profile(roots: UpgradeRoots) -> dict[str, str]:
    resources = roots.home / "blender" / "resources"
    return {
        "executable": str(roots.home / "blender" / "Blender"),
        "architecture": "arm64",
        "version": "4.5.0",
        "resources": str(resources),
        "config": str(resources / "config"),
        "extensions": str(resources / "extensions"),
    }


def test_state_rejects_unknown_schema_and_persists_revision(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "register", _desired(roots))
    with pytest.raises(InstallerError):
        validate_record(dict(doc, schema_version=3), roots)
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        updated = update_record(state, roots, saved, status="cancelled")
        assert updated["revision"] == 1
        assert load_record(state, roots, doc["id"]) == updated


def test_state_root_and_records_are_private(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "register", _desired(roots))
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        assert UUID(saved["id"]).version == 4
    assert stat.S_IMODE(roots.state.stat().st_mode) == 0o700
    assert stat.S_IMODE((roots.state / "upgrades").stat().st_mode) == 0o700
    assert stat.S_IMODE((roots.state / "upgrades" / f"{doc['id']}.json").stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "change",
    [
        {"home": "/foreign"},
        {"codex_home": "/foreign"},
        {"id": str(uuid1())},
        {"id": "not-a-uuid"},
        {"id": str(uuid4()).upper()},
        {"desired": {"commit": "a" * 40}},
        {"unexpected": True},
        {"desired": {"commit": "a" * 40, "manifest_sha256": "b" * 64,
                      "bundle_version": "1.0.0", "plugin_version": "2",
                      "projection": "unexpected", "extra": True}},
    ],
)
def test_validate_record_rejects_foreign_or_malformed_identity(
    tmp_path: Path, change: dict[str, object]
) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "register", _desired(roots))
    with pytest.raises(InstallerError):
        validate_record({**doc, **change}, roots)


@pytest.mark.parametrize(
    "profile_change",
    [
        {"config": "relative/config"},
        {"extensions": "../extensions"},
        {"config": "{resources}/../outside"},
        {"config": "{home}/outside"},
        {"unexpected": "/tmp/unknown"},
    ],
)
def test_validate_record_rejects_unsafe_or_unknown_profile_fields(
    tmp_path: Path, profile_change: dict[str, str]
) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "install", _desired(roots))
    profile = _profile(roots)
    profile_change = {
        key: value.format(resources=profile["resources"], home=str(roots.home))
        for key, value in profile_change.items()
    }
    profile.update(profile_change)
    with pytest.raises(InstallerError):
        validate_record({**doc, "profile": profile}, roots)


def test_save_record_rejects_revision_skip_and_illegal_transition(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "install", _desired(roots))
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        skipped = {**saved, "revision": 2, "status": "cancelled"}
        with pytest.raises(InstallerError, match="transition"):
            save_record(state, roots, saved, skipped)
        cancelled = update_record(state, roots, saved, status="cancelled")
        completed = {
            "profile": _profile(roots),
            "registration": {"id": str(uuid4()), "state": "registered"},
            "install_id": str(uuid4()),
            "verification": {"registration": "passed", "live": "passed"},
        }
        with pytest.raises(InstallerError, match="invalid upgrade transition"):
            update_record(state, roots, cancelled, status="complete", **completed)


def test_record_ids_includes_committed_and_temp_only_records(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    committed = new_record(roots, "register", _desired(roots))
    temporary = new_record(roots, "register", _desired(roots))
    with state_root(roots) as state:
        save_record(state, roots, None, committed)
        with pytest.raises(RuntimeError, match="after_json_file_fsync"):
            save_record(
                state,
                roots,
                None,
                temporary,
                fault=_CrashAt("after_json_file_fsync"),
            )
        assert record_ids(state) == tuple(sorted((committed["id"], temporary["id"])))


def test_load_any_record_uses_record_codex_home_and_rejects_foreign_home(
    tmp_path: Path,
) -> None:
    roots = _roots(tmp_path)
    alternate = UpgradeRoots(roots.home, tmp_path / "alternate-codex")
    record = new_record(alternate, "register", _desired(alternate))
    with state_root(alternate) as alternate_state:
        save_record(alternate_state, alternate, None, record)
    with state_root(roots) as state:
        assert load_any_record(state, roots, record["id"]) == record

    foreign = UpgradeRoots(tmp_path / "foreign-home", tmp_path / "foreign-codex")
    foreign.home.mkdir(mode=0o700)
    foreign.codex_home.mkdir(mode=0o700)
    foreign_record = new_record(foreign, "register", _desired(foreign), record["id"])
    with state_root(foreign) as foreign_state:
        save_record(foreign_state, foreign, None, foreign_record)
    with state_root(roots) as state:
        target = roots.state / "upgrades" / f"{record['id']}.json"
        target.write_bytes(
            (foreign.state / "upgrades" / f"{record['id']}.json").read_bytes()
        )
        with pytest.raises(InstallerError, match="foreign or malformed shared-home"):
            load_any_record(state, roots, record["id"])


def test_load_record_requires_explicit_recovery_for_atomic_temp(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "register", _desired(roots))
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        updated = {**saved, "revision": 1, "status": "cancelled"}
        with pytest.raises(RuntimeError, match="after_json_file_fsync"):
            save_record(
                state,
                roots,
                saved,
                updated,
                fault=_CrashAt("after_json_file_fsync"),
            )
        live_path = roots.state / "upgrades" / f"{doc['id']}.json"
        temp_path = roots.state / "upgrades" / (
            f".blender-mcp-installer.{doc['id']}.{doc['id']}.json.tmp"
        )
        before = (live_path.read_bytes(), temp_path.read_bytes())
        for _ in range(2):
            with pytest.raises(InstallerError, match="needs reconciliation"):
                load_record(state, roots, doc["id"])
            assert (live_path.read_bytes(), temp_path.read_bytes()) == before
        assert load_record(state, roots, doc["id"], recover=True) == updated
        assert load_record(state, roots, doc["id"]) == updated


def _image_row(roots: UpgradeRoots, tree: Path, files: int = 200) -> dict[str, object]:
    from blender_mcp_installer.filesystem import SafeRoot, capture_file, capture_tree

    tree.mkdir(parents=True)
    for index in range(files):
        (tree / f"file-{index:04d}.py").write_text(f"value = {index}\n")
    evidence = roots.home / "evidence.json"
    evidence.write_text("{}\n")
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        image = capture_tree(home, tree.relative_to(roots.home))
        proof = capture_file(home, evidence.relative_to(roots.home))
    return {
        "key": "plugin_cache:1", "kind": "plugin_cache", "owner": str(uuid4()),
        "version": "1", "expected": image.to_dict(),
        "proofs": [{"relative": "receipts/evidence.json", "expected": proof.to_dict()}],
        "content_source": str(roots.projections / ("c" * 40) / "plugins/blender-mcp-installer"),
        "content_sha256": "d" * 64, "lease_known": True, "state": "pending", "reason": "",
    }


def _journal(roots: UpgradeRoots, identifier: str) -> Path:
    return roots.state / "upgrades" / f"{identifier}.json"


def _images(roots: UpgradeRoots) -> list[Path]:
    folder = roots.state / "upgrades" / "images"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_journal_keeps_candidate_images_outside_the_record(tmp_path: Path) -> None:
    import json

    from blender_mcp_installer.upgrade_state import encode_record

    roots = _roots(tmp_path)
    row = _image_row(roots, roots.home / "tree")
    doc = dict(new_record(roots, "register", _desired(roots)), candidates=[row])
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        second = save_record(
            state, roots, None, dict(new_record(roots, "register", _desired(roots)), candidates=[row])
        )
        raw = _journal(roots, doc["id"]).read_bytes()
        stored = json.loads(raw)
        assert len(raw) < 4096 and b"file-0150.py" not in raw
        images = _images(roots)
        assert [path.name for path in images] == [
            stored["candidates"][0]["expected"]["image_sha256"] + ".json"
        ]
        assert stat.S_IMODE(images[0].stat().st_mode) == 0o600
        assert stored == encode_record(saved)
        assert load_record(state, roots, doc["id"]) == saved
        assert load_record(state, roots, second["id"]) == second


@pytest.mark.parametrize("damage", ["missing", "tampered"])
def test_missing_or_changed_candidate_image_fails_closed(tmp_path: Path, damage: str) -> None:
    roots = _roots(tmp_path)
    row = _image_row(roots, roots.home / "tree")
    doc = dict(new_record(roots, "register", _desired(roots)), candidates=[row])
    with state_root(roots) as state:
        save_record(state, roots, None, doc)
        image, = _images(roots)
        if damage == "missing":
            image.unlink()
        else:
            image.write_text('{"state":"absent"}\n')
            image.chmod(0o600)
        with pytest.raises(InstallerError, match="candidate image"):
            load_record(state, roots, doc["id"])


def test_version_one_journal_keeps_embedded_images(tmp_path: Path) -> None:
    import json

    roots = _roots(tmp_path)
    row = _image_row(roots, roots.home / "tree")
    doc = dict(
        new_record(roots, "register", _desired(roots)), schema_version=1, candidates=[row]
    )
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        updated = update_record(state, roots, saved, status="cancelled")
        stored = json.loads(_journal(roots, doc["id"]).read_bytes())
        assert stored["schema_version"] == 1
        assert stored["candidates"][0]["expected"] == row["expected"]
        assert _images(roots) == []
        assert load_record(state, roots, doc["id"]) == updated


class _CrashAtHit:
    def __init__(self, point: str, occurrence: int) -> None:
        self.point, self.remaining = point, occurrence

    def hit(self, point: str) -> None:
        if point == self.point:
            self.remaining -= 1
            if self.remaining == 0:
                raise RuntimeError(point)


@pytest.mark.parametrize("first_write", [False, True])
@pytest.mark.parametrize("crash", ["image", "journal"])
def test_interrupted_journal_write_recovers_with_its_images(
    tmp_path: Path, crash: str, first_write: bool
) -> None:
    roots = _roots(tmp_path)
    row = _image_row(roots, roots.home / "tree")
    doc = new_record(roots, "register", _desired(roots))
    with state_root(roots) as state:
        saved = None if first_write else save_record(state, roots, None, doc)
        updated = (
            dict(doc, candidates=[row])
            if first_write
            else {**saved, "revision": 1, "candidates": [row]}
        )
        fault = _CrashAtHit("after_json_file_fsync", 1 if crash == "image" else 2)
        with pytest.raises(RuntimeError, match="after_json_file_fsync"):
            save_record(state, roots, saved, updated, fault=fault)
        if crash == "image":
            assert load_record(state, roots, doc["id"], recover=True) == saved
            save_record(state, roots, saved, updated)
            assert load_record(state, roots, doc["id"]) == updated
        else:
            assert load_record(state, roots, doc["id"], recover=True) == updated
        assert len([path for path in _images(roots) if path.suffix == ".json"]) == 1


def test_interrupted_image_copy_never_blocks_a_published_image(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    row = _image_row(roots, roots.home / "tree")
    doc = dict(new_record(roots, "register", _desired(roots)), candidates=[row])
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        image, = _images(roots)
        torn = image.with_name(f".blender-mcp-installer.{doc['id']}.{image.name}.tmp")
        torn.write_bytes(b'{"state":')
        torn.chmod(0o600)
        assert load_record(state, roots, doc["id"]) == saved
