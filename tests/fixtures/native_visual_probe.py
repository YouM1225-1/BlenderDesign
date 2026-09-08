# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
import sys
import json
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.blender_scripts.native_collect import collect
from acceptance.blender_scripts.native_render import render_images, compare, PASSES, VIEWS


def validate_comparisons(records):
    expected = {
        (group, view, render_pass)
        for group in ("same", "fresh")
        for view in VIEWS
        for render_pass in PASSES
        if not (group == "same" and render_pass == "beauty")
    }
    assert len(records) == 63
    assert {(r["group"], r["view"], r["render_pass"]) for r in records} == expected
    for record in records:
        assert record["size"] == [1024, 1024]
        if record["render_pass"] != "beauty":
            assert record["different_pixels"] == 0, record
            # The known nonempty good fixture must be visible in every diagnostic view.
            assert record["left_rgb_energy"] > 0 and record["right_rgb_energy"] > 0, record


def main():
    args = sys.argv[sys.argv.index("--") + 1 :]
    root = Path(args[0])
    operation = args[1]
    if operation == "compare":
        destination = root / "comparison"
        destination.mkdir()
        records = []
        for group in ("same", "fresh"):
            for view in VIEWS:
                for render_pass in PASSES:
                    if group == "same" and render_pass == "beauty":
                        continue
                    first = (
                        root
                        / ("same_process" if group == "same" else "fresh_a")
                        / f"0-{view}-{render_pass}.png"
                    )
                    second = (
                        root
                        / ("same_process" if group == "same" else "fresh_b")
                        / f"{1 if group == 'same' else 0}-{view}-{render_pass}.png"
                    )
                    result = compare(
                        first, second, destination / f"{group}-{view}-{render_pass}.png", 1048576
                    )
                    result.update(group=group, view=view, render_pass=render_pass)
                    records.append(result)
        (root / "comparisons.json").write_text(json.dumps(records, allow_nan=False))
        validate_comparisons(records)
        print("NATIVE_27_SAME_AND_27_FRESH_DIAGNOSTIC_PAIRS_OK")
    else:
        destination = root / operation
        destination.mkdir()
        bpy.ops.wm.open_mainfile(
            filepath=str(root / "fixtures/good.blend"), load_ui=False, use_scripts=False
        )
        manifest = collect("Scene", "ViewLayer", 1)
        settings = {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
        }
        outputs = {
            f"image.{operation}.{r}.{v}.{p}": destination / f"{r}-{v}-{p}.png"
            for r in range(2 if operation == "same_process" else 1)
            for v in VIEWS
            for p in PASSES
            if not (r == 1 and p == "beauty")
        }
        report = render_images(manifest, settings, outputs, operation)
        (destination / "render.json").write_text(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
