import subprocess
from pathlib import Path

from acceptance import check_registry as reg
from acceptance.interchange_plan import interchange_commands
from tests.integration.asset_runtime_support import (
    REPO,
    prepare_native_case,
    write_case,
)
from tests.unit.asset_v2_support import file_lock
from tests.unit.interchange_support import policy


def prepare_interchange_case(
    blender: Path,
    node: Path,
    python: Path,
    package_root: Path,
    root: Path,
    fixture_name="good",
    *,
    calibration_root=None,
):
    case = prepare_native_case(blender, root, fixture_name, calibration_root=calibration_root)
    doc = case.document
    doc["artifact_kind"] = "interchange"
    doc["checks"] = [
        {"id": s.id, "impl": s.impl, "order": s.order}
        for s in sorted(reg.checks_for_kind("interchange"), key=reg.sort_key)
    ]
    doc["na_check_ids"] = list(reg.na_check_ids("interchange"))
    doc["interchange"] = policy(package_root)
    doc["tools"].append(
        {
            "id": "node",
            "path": str(node.resolve()),
            "version": subprocess.check_output([str(node), "--version"], text=True).strip(),
            "sha256": file_lock(node)["sha256"],
            "files": [
                file_lock(p)
                for p in [
                    REPO / "acceptance/node_scripts/validator_worker.mjs",
                    package_root / "package.json",
                    package_root / "package-lock.json",
                    package_root / "node_modules/gltf-validator/package.json",
                    package_root / "node_modules/gltf-validator/index.js",
                    package_root / "node_modules/gltf-validator/gltf_validator.dart.js",
                ]
            ],
        }
    )
    gltf_root = blender.resolve().parents[1] / "Resources/5.2/scripts/addons_core/io_scene_gltf2"
    if not (gltf_root / "__init__.py").is_file():
        raise ValueError("locked Blender glTF module not found")
    for tool in doc["tools"]:
        if tool["id"] == "blender":
            tool["files"] += [
                file_lock(REPO / "acceptance/blender_scripts" / name)
                for name in ("glb_worker.py", "projection_capture.py")
            ] + [file_lock(path) for path in sorted(gltf_root.rglob("*.py"))]
        if tool["id"] == "python":
            tool["files"] += [
                file_lock(REPO / "acceptance" / name)
                for name in ("glb_budget_worker.py", "projection_worker.py")
            ]
    doc["limits"]["timeout_seconds"] = {
        key: 600 for key in interchange_commands(blender, node, python, REPO)
    }
    doc["review"]["required_image_ids"] += [
        "image.projection_source.0.front.beauty",
        "image.projection_import.0.front.beauty",
        "image.projection_source.0.bottom.silhouette",
        "image.projection_import.0.bottom.silhouette",
    ]
    write_case(case)
    return case
