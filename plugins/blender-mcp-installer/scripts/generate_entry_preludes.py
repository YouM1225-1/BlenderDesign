"""Inline entry_lease.py into both entry scripts; --check reports drift without writing."""
from __future__ import annotations

import argparse
from pathlib import Path

BEGIN = "# BEGIN GENERATED ENTRY LEASE (from entry_lease.py; run generate_entry_preludes.py)\n"
END = "# END GENERATED ENTRY LEASE\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    source = (scripts / "entry_lease.py").read_text()
    drifted = False
    for name in ("install.py", "project_marketplace.py"):
        path = scripts / name
        current = path.read_text()
        if current.count(BEGIN) != 1 or current.count(END) != 1:
            raise ValueError(f"{name}: expected one marked entry lease block")
        before, remainder = current.split(BEGIN)
        _generated, after = remainder.split(END)
        expected = before + BEGIN + source + END + after
        if current != expected:
            if args.check:
                print(f"entry lease drift: {name}; run {Path(__file__).name}")
                drifted = True
            else:
                path.write_text(expected)
                print(f"generated entry lease: {name}")
    return int(drifted)


if __name__ == "__main__":
    raise SystemExit(main())
