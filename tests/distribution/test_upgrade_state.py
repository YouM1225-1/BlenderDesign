import sys
import stat
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.filesystem import InstallerError
from blender_mcp_installer.upgrade_state import (
    UpgradeRoots,
    load_record,
    new_record,
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
        {"id": "not-a-uuid"},
        {"desired": {"commit": "a" * 40}},
    ],
)
def test_validate_record_rejects_foreign_or_malformed_identity(
    tmp_path: Path, change: dict[str, object]
) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "register", _desired(roots))
    with pytest.raises(InstallerError):
        validate_record({**doc, **change}, roots)


def test_save_record_rejects_revision_skip_and_illegal_transition(tmp_path: Path) -> None:
    roots = _roots(tmp_path)
    doc = new_record(roots, "register", _desired(roots))
    with state_root(roots) as state:
        saved = save_record(state, roots, None, doc)
        skipped = {**saved, "revision": 2, "status": "cancelled"}
        with pytest.raises(InstallerError, match="transition"):
            save_record(state, roots, saved, skipped)
        cancelled = update_record(state, roots, saved, status="cancelled")
        with pytest.raises(InstallerError, match="cleanup lacks registration verification"):
            update_record(state, roots, cancelled, status="complete")


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
        with pytest.raises(InstallerError, match="needs reconciliation"):
            load_record(state, roots, doc["id"])
        assert load_record(state, roots, doc["id"], recover=True) == updated
        assert load_record(state, roots, doc["id"]) == updated
