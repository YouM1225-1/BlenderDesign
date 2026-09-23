import json
import struct
from pathlib import Path

from acceptance.interchange_policy import PRESET


def policy(package_root: Path) -> dict:
    return {
        "profile": "glb-static-surface-v1",
        "preset": dict(PRESET),
        "package_root": str(package_root),
        "validator_version": "2.0.0-dev.3.10",
        "limits": {
            "max_glb_bytes": 8 * 1024 * 1024,
            "max_json_bytes": 1024 * 1024,
            "max_nodes": 100,
            "max_meshes": 100,
            "max_stored_triangles": 1000,
            "max_rendered_triangles": 2000,
            "max_draw_calls": 100,
            "max_texture_pixels": 1024 * 1024,
            "max_matches": 2000000,
            "max_projection_triangles": 4096,
        },
        "tolerances": {
            k: {"abs": 1e-5, "rel": 1e-6}
            for k in ("geometry", "normal", "uv", "material")
        },
        "reference_scale": 4.0,
        "allowed_extensions": [],
        "losses": {
            "collections": "omit",
            "modifiers": "bake",
            "unused_vertices": "prune",
            "unused_material_slots": "prune",
            "unused_uv_layers": "preserve",
        },
        "consumer": None,
    }


def projection():
    tri = {
        "corners": [
            {"position": p, "normal": [0.0, 0.0, 1.0], "uv": [[p[0], p[1]]]}
            for p in [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        ],
        "material": {
            "pbr": {
                "base_color": [0.2, 0.4, 0.8, 1.0],
                "metallic": 0.0,
                "roughness": 0.5,
                "alpha": 1.0,
                "emission": [0.0, 0.0, 0.0],
            },
            "texture": None,
            "double_sided": True,
        },
    }
    return {
        "schema_version": 2,
        "scale_length": 1,
        "objects": [
            {
                "id": ["OBJECT", "Asset"],
                "matrix": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "vertices": 12,
                "slots": 2,
                "custom": {"name": "kept"},
                "triangles": [tri],
            }
        ],
    }


def clean(report):
    return not any(report[k] for k in ("preserved", "transformed", "loss", "ambiguous"))


def make_budget_fixture(path, nodes):
    data = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": list(range(nodes))}],
        "nodes": [{"mesh": 0} for _ in range(nodes)],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"count": 3, "componentType": 5126, "type": "VEC3"}],
    }
    raw = json.dumps(data).encode()
    raw += b" " * ((-len(raw)) % 4)
    path.write_bytes(
        struct.pack("<4sIIII", b"glTF", 2, 20 + len(raw), len(raw), 0x4E4F534A) + raw
    )


def lock_gltf_fixture(tmp_path, tool):
    from tests.unit.asset_v2_support import REPO, file_lock
    executable = tmp_path / "Blender.app/Contents/MacOS/Blender"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(Path(tool["path"]).read_bytes())
    executable.chmod(0o700)
    root = executable.parents[1] / "Resources/5.2/scripts/addons_core/io_scene_gltf2"
    root.mkdir(parents=True)
    for name in ("__init__.py", "importer.py", "libdraco.dylib"):
        (root / name).write_bytes(b"fixture module bytes")
    tool["path"] = str(executable)
    tool["sha256"] = file_lock(executable)["sha256"]
    tool["files"] += [file_lock(p) for p in sorted(root.iterdir())]
    tool["files"].append(file_lock(REPO / "acceptance/blender_scripts/glb_worker.py"))
    return root
