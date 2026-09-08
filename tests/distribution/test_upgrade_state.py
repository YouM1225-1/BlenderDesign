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
        validate_record(dict(doc, schema_version=2), roots)
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
