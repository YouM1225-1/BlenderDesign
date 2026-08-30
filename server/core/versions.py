"""版本门禁。spec §4.4、§8.3：基线 5.2.0；Phase 0 只读放行 + 警告。"""
from __future__ import annotations

BASELINE: dict[str, str] = {"version": "5.2.0", "platform": "macos-arm64"}


def check(blender_version: str) -> tuple[bool, str | None]:
    baseline = BASELINE["version"]
    if blender_version == baseline:
        return True, None
    return False, (f"Blender {blender_version} 不是本系统钉定基线（{baseline} LTS）；"
                   f"当前 Phase 0 只读工具仍可用，但该版本未验证")
