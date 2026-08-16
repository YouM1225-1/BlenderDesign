from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "plugins/blender-mcp-installer/scripts"
sys.path[:] = [str(SCRIPTS), *sys.path]

from blender_mcp_installer.cli import ExitFaultInjector, run_cli  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--point", required=True)
    parser.add_argument("--applicable-point", action="append", default=[])
    args, cli_argv = parser.parse_known_args()
    if args.point not in args.applicable_point:
        parser.error("fault point is not applicable to this fixture")
    fault = ExitFaultInjector(args.point, 70)
    code = run_cli(cli_argv, fault=fault)
    if not fault.hit_requested:
        parser.error("requested fault point was not hit")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
