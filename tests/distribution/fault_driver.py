from __future__ import annotations

import argparse
import sys
from pathlib import Path


_INSTALL = frozenset({"install"})
_MUTATING = frozenset({"install", "rollback"})
_APPLICABILITY: dict[str, frozenset[str]] = {
    **{
        point: _MUTATING
        for point in (
            "after_json_file_fsync",
            "after_json_rename",
            "after_json_parent_fsync",
            "after_rollback_intent",
            "after_active_restore_parent_fsync",
            "after_rollback_status",
            "after_active_restore_cleanup",
            "after_codex_semantic_stage_fsync",
            "after_codex_semantic_swap",
            "after_codex_semantic_receipt",
            "after_codex_semantic_displaced_cleanup",
            "after_codex_semantic_recovery_cleanup",
        )
    },
    **{
        point: _INSTALL
        for point in (
            "after_pending_publish",
            "after_receipt_publish",
            "after_pending_remove",
            "after_active_swap",
            "after_active_park",
            "after_active_publish",
            "after_active_parent_fsync",
            "after_bundle_stage_planned",
            "after_bundle_stage_stage",
            "after_receipt_installed",
            "after_bundle_stage_cleanup",
        )
    },
}
for _kind in ("runtime_tree", "extension_tree", "userpref_file", "codex_file"):
    for _suffix in ("planned", "stage", "swap", "park", "publish", "completed"):
        _APPLICABILITY[f"after_{_kind}_{_suffix}"] = _INSTALL
    for _suffix in ("restore_swap", "restore_move", "restore_cleanup"):
        _APPLICABILITY[f"after_{_kind}_{_suffix}"] = _MUTATING
for _point in ("after_active_restore_swap", "after_active_restore_move"):
    _APPLICABILITY[_point] = _MUTATING


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--point", required=True)
    args, cli_argv = parser.parse_known_args()
    if cli_argv[:1] == ["--"]:
        cli_argv = cli_argv[1:]
    if not cli_argv or cli_argv[0] not in {"inspect", "install", "verify", "rollback"}:
        parser.error("a valid installer command is required")
    commands = _APPLICABILITY.get(args.point)
    if commands is None:
        parser.error("unknown fault point")
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
