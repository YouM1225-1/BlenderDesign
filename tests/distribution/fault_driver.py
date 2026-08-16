from __future__ import annotations

import argparse
import sys
from pathlib import Path


_INSTALL = frozenset({"install"})
_MUTATING = frozenset({"install", "rollback"})
_PREIMAGES = {
    "atomic_json": frozenset({"any"}),
    "pending": frozenset({"present", "absent"}),
    "receipt": frozenset({"present", "absent"}),
    "active_selector": frozenset({"present", "absent"}),
    "bundle_stage": frozenset({"absent"}),
    "runtime_tree": frozenset({"present", "absent"}),
    "extension_tree": frozenset({"present", "absent"}),
    "userpref_file": frozenset({"present", "absent"}),
    "codex_file": frozenset({"present", "absent"}),
    "codex_semantic": frozenset({"present"}),
}


def _applicable_points(fixture_kind: str, preimage: str) -> dict[str, frozenset[str]]:
    if preimage not in _PREIMAGES[fixture_kind]:
        raise ValueError("preimage is not valid for fixture kind")
    if fixture_kind == "atomic_json":
        return {
            point: _MUTATING
            for point in ("after_json_file_fsync", "after_json_rename", "after_json_parent_fsync")
        }
    if fixture_kind == "pending":
        return {point: _INSTALL for point in ("after_pending_publish", "after_pending_remove")}
    if fixture_kind == "receipt":
        return {"after_receipt_publish": _INSTALL}
    if fixture_kind == "bundle_stage":
        return {
            point: _INSTALL
            for point in (
                "after_bundle_stage_planned",
                "after_bundle_stage_stage",
                "after_receipt_installed",
                "after_bundle_stage_cleanup",
            )
        }
    if fixture_kind == "codex_semantic":
        return {
            point: _MUTATING
            for point in (
                "after_codex_semantic_stage_fsync",
                "after_codex_semantic_swap",
                "after_codex_semantic_receipt",
                "after_codex_semantic_displaced_cleanup",
                "after_codex_semantic_recovery_cleanup",
            )
        }
    if fixture_kind == "active_selector":
        points = {
            "after_rollback_intent": _MUTATING,
            "after_active_restore_parent_fsync": _MUTATING,
            "after_rollback_status": _MUTATING,
            "after_active_restore_cleanup": _MUTATING,
            "after_active_parent_fsync": _INSTALL,
        }
        if preimage == "present":
            points.update(
                {
                    "after_active_swap": _INSTALL,
                    "after_active_park": _INSTALL,
                    "after_active_restore_swap": _MUTATING,
                }
            )
        else:
            points.update(
                {
                    "after_active_publish": _INSTALL,
                    "after_active_restore_move": _MUTATING,
                }
            )
        return points
    points = {
        f"after_{fixture_kind}_{suffix}": _INSTALL for suffix in ("planned", "stage", "completed")
    }
    points[f"after_{fixture_kind}_restore_cleanup"] = _MUTATING
    if preimage == "present":
        points.update(
            {
                f"after_{fixture_kind}_swap": _INSTALL,
                f"after_{fixture_kind}_park": _INSTALL,
                f"after_{fixture_kind}_restore_swap": _MUTATING,
            }
        )
    else:
        points.update(
            {
                f"after_{fixture_kind}_publish": _INSTALL,
                f"after_{fixture_kind}_restore_move": _MUTATING,
            }
        )
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--point", required=True)
    parser.add_argument("--fixture-kind", required=True, choices=tuple(_PREIMAGES))
    parser.add_argument("--preimage", required=True, choices=("present", "absent", "any"))
    args, cli_argv = parser.parse_known_args()
    if cli_argv[:1] == ["--"]:
        cli_argv = cli_argv[1:]
    if not cli_argv or cli_argv[0] not in {"inspect", "install", "verify", "rollback"}:
        parser.error("a valid installer command is required")
    try:
        points = _applicable_points(args.fixture_kind, args.preimage)
    except ValueError as exc:
        parser.error(str(exc))
    commands = points.get(args.point)
    if commands is None:
        parser.error("fault point is not applicable to this fixture")
    if cli_argv[0] not in commands:
        parser.error("fault point is not applicable to this command")

    root = Path(__file__).resolve().parents[2]
    scripts = root / "plugins/blender-mcp-installer/scripts"
    sys.path.insert(0, str(scripts))
    from blender_mcp_installer.cli import ExitFaultInjector, run_cli

    fault = ExitFaultInjector(args.point, 70)
    code = run_cli(cli_argv, fault=fault)
    if not fault.hit_requested:
        parser.error("requested fault point was not hit")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
