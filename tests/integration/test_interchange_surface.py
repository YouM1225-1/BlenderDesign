import json
import os
from pathlib import Path

import pytest

from tests.integration.asset_runtime_support import REPO, blender_script

pytestmark = [
    pytest.mark.timeout(900),
    pytest.mark.skipif(
        os.environ.get("RUN_ASSET_INTERCHANGE") != "1",
        reason="explicit two-process Blender projection test",
    ),
]


def test_actual_split_prune_texture_and_changed_import(tmp_path):
    blender = Path(os.environ["BLENDER_BIN"])
    script = REPO / "tests/fixtures/asset_interchange.py"
    for mode in ("build", "import"):
        blender_script(
            blender,
            script,
            str(tmp_path),
            mode,
            os.environ["GLTF_PACKAGE_ROOT"],
            environment_root=tmp_path / f"blender-{mode}",
        )
    result = json.loads((tmp_path / "probe-results.json").read_text())
    assert result["cube"]["source_vertices"] == 8
    assert result["cube"]["import_vertices"] == 24
    assert result["pruning"]["source_vertices"] == 12
    assert result["pruning"]["import_vertices"] == 3
    assert result["pruning"]["source_slots"] == 2
    assert result["pruning"]["import_slots"] == 1
    for case in result.values():
        assert not any(
            case["positive"][key]
            for key in ("preserved", "transformed", "loss", "ambiguous")
        )
        assert all(case["negative"].values())
        assert case["actual_transform_negative"]
        assert case["actual_material_negative"]
