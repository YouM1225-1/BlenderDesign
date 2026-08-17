# Blender MCP Retina Coordinate Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make screenshot dimensions use Blender logical UI pixels consistently on Retina and non-Retina displays, even when the original PNG already fits the byte limit.

**Architecture:** Keep Blender's area/window JSON coordinates in their existing logical coordinate space and normalize screenshot PNGs into that same space. Read Blender's runtime `pixel_size` on every call, skip resampling only when the scale is at most `1.0`, and retain the existing byte-limit downscaling after HiDPI normalization.

**Tech Stack:** Python 3.10+, `unittest`, Blender 5.2 LTS, Blender `imbuf`, standard-library module fakes for deterministic 1x/2x tests.

## Global Constraints

- Begin from the exact `BACKGROUND_COMMIT` printed by `2026-08-17-blender-mcp-background-runtime-hardening.md`; do not begin from an independently fetched branch tip.
- Continue in the same isolated upstream worktree so the final `SOURCE_COMMIT` contains both background hardening and Retina normalization.
- Add no dependency and do not use macOS-only screen APIs.
- Treat `bpy.context.preferences.system.pixel_size` as the runtime source of truth; do not hard-code `2` for Retina.
- Preserve the current public MCP tool names, parameters, image return shape, byte caps, and JSON layout schema.
- A `pixel_size` at or below `1.0` must preserve the current no-resample fast path.
- A `pixel_size` above `1.0` must normalize dimensions before the byte-limit search, including when the source PNG already fits the requested byte limit.
- Clamp normalized width and height to at least one pixel.
- Test simulated `1.0`, `1.5`, and `2.0` scales without requiring a particular monitor.

---

## File Structure

- Modify `mcp/blmcp/tools/_template_image_downscale_to_size_limit.py`: make HiDPI normalization independent of file-size overflow.
- Create `tests/test_screenshot_image_scaling.py`: deterministic fake-`bpy`/fake-`imbuf` unit tests for 1x, 1.5x, and 2x behavior.
- Modify `tests/test_blender_mcp_with_blender.py`: compare returned screenshot dimensions with the logical window/area coordinate plane.
- Modify `Makefile`: register the new unit test in the standard test gate.

---

### Task 1: Reproduce the Retina early-return defect without a Retina monitor

**Files:**
- Create: `tests/test_screenshot_image_scaling.py`
- Modify: `Makefile:83-90`
- Test: `tests/test_screenshot_image_scaling.py`

**Interfaces:**
- Consumes: `_image_downscale_to_size_limit(tmpdir: str, filepath: str, size_limit_in_bytes: int, size_tolerance_in_bytes: int = 0) -> bytes`.
- Produces: deterministic fake Blender modules and regression tests covering both the fast path and fractional/integer HiDPI scales.

- [ ] **Step 1: Create the complete focused unit test**

```python
# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

__all__ = ()

from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from blmcp.tools._template_image_downscale_to_size_limit import (
    _image_downscale_to_size_limit,
)


class _FakeImage:
    def __init__(self) -> None:
        self.size = (300, 150)
        self.resize_calls: list[tuple[int, int]] = []

    def resize(self, size: tuple[int, int], method: str) -> None:
        assert method == "BILINEAR"
        self.size = size
        self.resize_calls.append(size)

    def copy(self) -> "_FakeImage":
        result = _FakeImage()
        result.size = self.size
        return result

    def free(self) -> None:
        pass


def _modules(pixel_size: float) -> tuple[dict[str, ModuleType], _FakeImage]:
    image = _FakeImage()
    bpy = ModuleType("bpy")
    bpy.context = SimpleNamespace(  # type: ignore[attr-defined]
        preferences=SimpleNamespace(
            system=SimpleNamespace(pixel_size=pixel_size),
        ),
    )
    imbuf = ModuleType("imbuf")
    imbuf.load = lambda _path: image  # type: ignore[attr-defined]

    def write(current: _FakeImage, filepath: str) -> None:
        Path(filepath).write_bytes(
            "{:d}x{:d}".format(*current.size).encode("ascii")
        )

    imbuf.write = write  # type: ignore[attr-defined]
    return {"bpy": bpy, "imbuf": imbuf}, image


class TestScreenshotImageScaling(unittest.TestCase):
    def _run(self, pixel_size: float) -> tuple[bytes, _FakeImage]:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.png"
            source.write_bytes(b"already-small")
            modules, image = _modules(pixel_size)
            with mock.patch.dict(sys.modules, modules):
                result = _image_downscale_to_size_limit(
                    tmpdir,
                    str(source),
                    size_limit_in_bytes=1024,
                )
        return result, image

    def test_one_x_small_image_keeps_fast_path(self) -> None:
        result, image = self._run(1.0)
        self.assertEqual(result, b"already-small")
        self.assertEqual(image.resize_calls, [])

    def test_two_x_small_image_is_normalized_before_early_return(self) -> None:
        result, image = self._run(2.0)
        self.assertEqual(result, b"150x75")
        self.assertEqual(image.resize_calls, [(150, 75)])

    def test_fractional_scale_uses_runtime_value(self) -> None:
        result, image = self._run(1.5)
        self.assertEqual(result, b"200x100")
        self.assertEqual(image.resize_calls, [(200, 100)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Register the test after `tests/test_blender_cli.py` in `Makefile`**

```make
	$(PYTHON) tests/test_screenshot_image_scaling.py
```

- [ ] **Step 3: Run the regression test before changing production code**

```bash
PYTHONPATH=mcp python tests/test_screenshot_image_scaling.py -v
```

Expected: the `1.0` test passes; the `1.5` and `2.0` tests fail because the current size-based early return bypasses `pixel_size` normalization.

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_screenshot_image_scaling.py Makefile
git commit -m "test: expose Retina screenshot scale mismatch"
```

---

### Task 2: Normalize HiDPI before applying the byte-limit fast path

**Files:**
- Modify: `mcp/blmcp/tools/_template_image_downscale_to_size_limit.py:20-48`
- Test: `tests/test_screenshot_image_scaling.py`

**Interfaces:**
- Consumes: Task 1 simulated runtime scale tests.
- Produces: the existing `_image_downscale_to_size_limit(...) -> bytes` contract with display-independent logical dimensions.

- [ ] **Step 1: Replace the current unconditional file-size early return and HiDPI block with this exact ordering**

```python
    source_fits = os.path.getsize(filepath) <= size_limit_in_bytes

    from bpy import context  # pylint: disable=import-error,no-name-in-module

    pixel_size = float(context.preferences.system.pixel_size)
    if pixel_size <= 1.0 and source_fits:
        with open(filepath, "rb") as fh:
            return fh.read()

    import imbuf  # type: ignore[import-not-found]  # pylint: disable=import-error,no-name-in-module

    filepath_out = os.path.join(tmpdir, "downscaled.png")
    im = imbuf.load(filepath)

    if pixel_size > 1.0:
        width, height = im.size
        im.resize(
            (
                max(1, round(width / pixel_size)),
                max(1, round(height / pixel_size)),
            ),
            method="BILINEAR",
        )
```

Delete the old early-return block, the duplicate `from bpy import context`, and the old `if pixel_size > 1.0` resize block. Leave `_write_and_read()`, the initial normalized encode, and the existing byte-limit search unchanged.

- [ ] **Step 2: Run the deterministic scale tests**

```bash
PYTHONPATH=mcp python tests/test_screenshot_image_scaling.py -v
```

Expected: all three tests pass; `1.0` returns the original bytes, while `1.5` and `2.0` return the fake normalized encodes.

- [ ] **Step 3: Run source checks for the changed template and test**

```bash
ruff check mcp/blmcp/tools/_template_image_downscale_to_size_limit.py \
  tests/test_screenshot_image_scaling.py
python -m mypy --exclude 'data/api/examples/' \
  mcp/blmcp/tools/_template_image_downscale_to_size_limit.py
```

Expected: both commands report no errors.

- [ ] **Step 4: Commit the normalization**

```bash
git add mcp/blmcp/tools/_template_image_downscale_to_size_limit.py \
  tests/test_screenshot_image_scaling.py
git commit -m "fix: normalize screenshots to logical UI pixels"
```

---

### Task 3: Verify screenshot and JSON coordinate planes in real Blender

**Files:**
- Modify: `tests/test_blender_mcp_with_blender.py:537-570`
- Test: `tests/test_blender_mcp_with_blender.py`

**Interfaces:**
- Consumes: normalized window/area PNGs from Task 2 and the existing `get_screenshot_of_window_as_json` response.
- Produces: integration evidence that image dimensions never exceed their corresponding logical coordinate bounds.

- [ ] **Step 1: Add a helper that extracts PNG dimensions from returned image content**

```python
    def _returned_image_size(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> tuple[int, int] | None:
        content = self._call_tool_screenshot(name, arguments)
        if not self._interactive:
            return None
        image_data = content[0].get("data", "")
        assert isinstance(image_data, str)
        return self._image_size(image_data)
```

- [ ] **Step 2: Add window and area coordinate-plane tests to `_TestServerMixin`**

```python
    def test_window_screenshot_uses_json_coordinate_plane(self) -> None:
        image_size = self._returned_image_size("get_screenshot_of_window_as_image")
        if not self._interactive:
            return
        layout = self._test_tool("get_screenshot_of_window_as_json")
        assert image_size is not None
        self.assertLessEqual(image_size[0], layout["window_width"])
        self.assertLessEqual(image_size[1], layout["window_height"])

    def test_area_screenshot_uses_json_coordinate_plane(self) -> None:
        image_size = self._returned_image_size(
            "get_screenshot_of_area_as_image",
            {"area_ui_type": "VIEW_3D"},
        )
        if not self._interactive:
            return
        layout = self._test_tool("get_screenshot_of_window_as_json")
        view_3d = max(
            (area for area in layout["areas"] if area["type"] == "VIEW_3D"),
            key=lambda area: area["width"] * area["height"],
        )
        assert image_size is not None
        self.assertLessEqual(image_size[0], view_3d["width"])
        self.assertLessEqual(image_size[1], view_3d["height"])
```

- [ ] **Step 3: Run the two interactive tests in a normal macOS Blender window**

```bash
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender \
BLENDER_MCP_FOREGROUND=1 \
PYTHONPATH=mcp \
python tests/test_blender_mcp_with_blender.py \
  TestInteractiveServer.test_window_screenshot_uses_json_coordinate_plane \
  TestInteractiveServer.test_area_screenshot_uses_json_coordinate_plane
```

Expected: both tests pass on a Retina display. Repeat with Blender on a non-Retina display when available; the same assertions pass without a special configuration flag.

- [ ] **Step 4: Run the full upstream gates**

```bash
make test PYTHON=python
make check_all PYTHON=python
git diff --check
```

Expected: all tests and static checks pass; `git diff --check` prints nothing.

- [ ] **Step 5: Commit integration coverage**

```bash
git add tests/test_blender_mcp_with_blender.py
git commit -m "test: verify screenshot coordinate normalization"
```

- [ ] **Step 6: Record the exact combined source commit**

```bash
SOURCE_COMMIT=$(git rev-parse HEAD)
test "$(printf '%s' "$SOURCE_COMMIT" | wc -c | tr -d ' ')" = 40
git status --short
printf 'SOURCE_COMMIT=%s\n' "$SOURCE_COMMIT"
```

Expected: the worktree is clean and one exact 40-character `SOURCE_COMMIT` is printed. Pass it unchanged to `2026-08-17-blender-mcp-hardening-distribution-rollout.md`.

---

## Plan Self-Review

- Spec coverage: the small-file early return, 1x, fractional scale, 2x, lower-bound clamping, byte-limit ordering, logical JSON coordinates, real Blender, and non-Retina behavior each map to an explicit test or implementation step.
- Placeholder scan: the only future value is the exact `SOURCE_COMMIT` calculated from the completed upstream worktree and validated before distribution use.
- Type consistency: the public screenshot and JSON schemas do not change; `_image_downscale_to_size_limit(...) -> bytes` retains its existing signature.
- Scope boundary: this plan changes raster normalization only; it does not introduce OS-level mouse coordinates or assume a fixed Retina factor.
