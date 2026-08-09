"""复制 protocol/ → bridge/_vendor/protocol/；--check 校验逐文件 sha256 一致（§9 检查 2）。"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "protocol"
DST = ROOT / "bridge" / "_vendor" / "protocol"


def _digest(d: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.glob("*.py"))}


def main() -> int:
    if "--check" in sys.argv:
        if not DST.exists():
            print("vendor missing: run scripts/vendor_protocol.py first")
            return 1
        src, dst = _digest(SRC), _digest(DST)
        if src != dst:
            print(f"vendor drift: {sorted(set(src) ^ set(dst)) or 'content differs'}")
            return 1
        print("vendor ok")
        return 0
    DST.parent.mkdir(parents=True, exist_ok=True)
    (DST.parent / "__init__.py").write_text("")
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"vendored {len(list(DST.glob('*.py')))} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
