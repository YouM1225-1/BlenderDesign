"""Bump the installer cachebuster; --check rejects changes without a newer version."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "plugins/blender-mcp-installer"
MANIFEST = f"{PLUGIN}/.codex-plugin/plugin.json"
PREFIX = "1.0.0+codex."
STAMP_FORMAT = "%Y%m%d%H%M%S"


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
    ).strip()


def timestamp(version: str) -> datetime:
    if not re.fullmatch(r"1\.0\.0\+codex\.\d{14}", version):
        raise ValueError(f"invalid installer version: {version}")
    return datetime.strptime(version[len(PREFIX):], STAMP_FORMAT).replace(tzinfo=timezone.utc)


def changed(base: str, staged: bool) -> bool:
    options = ["--cached"] if staged else []
    return bool(
        git("diff", "--no-ext-diff", "--name-only", "-z", *options, base, "--", PLUGIN)
        or (not staged and git("ls-files", "--others", "--exclude-standard", "--", PLUGIN))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument("--staged", action="store_true", help="use the Git index for pre-commit")
    parser.add_argument("--merge", action="store_true", help="reserve a fresh merge commit version")
    args = parser.parse_args()
    if args.merge and not args.staged:
        parser.error("--merge requires --staged")
    path = ROOT / MANIFEST
    manifest = json.loads(git("show", f":{MANIFEST}") if args.staged else path.read_text())
    if manifest["name"] != "blender-mcp-installer":
        raise ValueError("unexpected installer plugin name")
    current = timestamp(manifest["version"])
    bases = ["HEAD"]
    if not changed("HEAD", args.staged):
        if args.staged:
            return 0
        # A clean checkout must still catch a commit made with the hook bypassed.
        latest = git("log", "-1", "--format=%H", "--", PLUGIN)
        parents = git("rev-list", "--parents", "-n", "1", latest).split()
        if len(parents) == 1:
            if git("rev-parse", "--is-shallow-repository") == "true":
                raise ValueError("installer version check needs history; fetch the missing commits")
            return 0
        bases = parents[1:]
    else:
        merge_head = ROOT / git("rev-parse", "--git-path", "MERGE_HEAD")
        if merge_head.exists():
            bases.extend(merge_head.read_text().split())
    previous = max(
        timestamp(json.loads(git("show", f"{base}:{MANIFEST}"))["version"]) for base in bases
    )
    if args.merge:
        # Git invokes pre-merge-commit before writing MERGE_HEAD.
        previous = max(previous, current)
    if current > previous:
        print(f"installer version ok: {manifest['version']}")
        return 0
    if args.check:
        raise ValueError(
            "installer changed without a newer version; run python3 scripts/update_installer_version.py"
        )
    if args.staged and git("diff", "--no-ext-diff", "--name-only", "--", MANIFEST):
        raise ValueError("plugin.json has unstaged edits; stage or stash them before committing")
    next_stamp = max(datetime.now(timezone.utc), previous + timedelta(seconds=1))
    manifest["version"] = PREFIX + next_stamp.strftime(STAMP_FORMAT)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    if args.staged:
        git("add", "--", MANIFEST)
    print(f"updated installer version: {manifest['version']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
