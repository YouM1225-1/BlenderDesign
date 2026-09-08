from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def classify_upstream(
    pinned: str, remote: str, *, require_latest: bool
) -> tuple[dict[str, object], int]:
    if not re.fullmatch(r"[0-9a-f]{40}", pinned) or not re.fullmatch(
        r"[0-9a-f]{40}", remote
    ):
        raise ValueError("upstream commit must be 40 lowercase hex characters")
    current = pinned == remote
    return (
        {
            "check": "upstream_freshness",
            "pinned": pinned,
            "remote": remote,
            "status": "current" if current else "outdated",
            "required": require_latest,
        },
        int(require_latest and not current),
    )


def _unverified_report(pinned: str, status: str, require_latest: bool) -> dict[str, object]:
    return {
        "check": "upstream_freshness",
        "pinned": pinned,
        "remote": None,
        "status": status,
        "required": require_latest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-latest", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "plugins/blender-mcp-installer/scripts"))
    from blender_mcp_installer.bundle import UPSTREAM_COMMIT

    try:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "ls-remote",
                "--exit-code",
                "https://projects.blender.org/lab/blender_mcp.git",
                "refs/heads/main",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": "/var/empty",
                "LC_ALL": "C",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
            },
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
        report = _unverified_report(UPSTREAM_COMMIT, "unavailable", args.require_latest)
        code = int(args.require_latest)
    else:
        lines = result.stdout.splitlines()
        fields = lines[0].split("\t") if len(lines) == 1 else []
        if (
            len(fields) != 2
            or fields[1] != "refs/heads/main"
            or not re.fullmatch(r"[0-9a-f]{40}", fields[0])
        ):
            report = _unverified_report(
                UPSTREAM_COMMIT, "invalid_response", args.require_latest
            )
            code = int(args.require_latest)
        else:
            report, code = classify_upstream(
                UPSTREAM_COMMIT, fields[0], require_latest=args.require_latest
            )
    print(json.dumps(report, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
