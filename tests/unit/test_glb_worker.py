"""Production work() order with only Blender operations/capture/render replaced."""

import importlib.util
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext

import pytest
from acceptance.glb_budget import measure_glb
from acceptance.input_bundle import measure_file
from acceptance.native_results import load
from acceptance.worker_protocol import read_request
from tests.fixtures.interchange_png import make_glb
from tests.unit.interchange_support import policy, projection
from tests.unit.test_native_policy import policy as native_policy


@pytest.fixture
def worker(monkeypatch):
    opened = []
    obj = SimpleNamespace(type="MESH", name="Asset", keys=lambda: [])

    class Objects(dict):
        def __iter__(self):
            return iter(self.values())

    scene = SimpleNamespace(
        objects=Objects(Asset=obj), view_layers={"ViewLayer": None}, frame_set=lambda _: None
    )
    bpy = SimpleNamespace(
        ops=SimpleNamespace(
            wm=SimpleNamespace(
                read_factory_settings=lambda **kw: None,
                open_mainfile=lambda **kw: opened.append(kw),
            ),
            import_scene=SimpleNamespace(gltf=lambda **kw: opened.append(kw)),
        ),
        context=SimpleNamespace(scene=scene, window=SimpleNamespace(scene=scene, view_layer=None)),
        data=SimpleNamespace(scenes={"Scene": scene}),
    )

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(
        sys.modules,
        "acceptance.blender_scripts.native_worker",
        SimpleNamespace(
            read_json=load,
            write_json=write,
            sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "acceptance.blender_scripts.native_render",
        SimpleNamespace(render_images=lambda *a, **kw: {}, compare=None),
    )
    monkeypatch.setitem(
        sys.modules,
        "acceptance.blender_scripts.projection_capture",
        SimpleNamespace(
            capture=lambda *a, **kw: projection(),
            render_manifest=lambda *a: {},
            projected_surface=lambda objects, *a: nullcontext(objects),
        ),
    )
    path = Path(__file__).resolve().parents[2] / "acceptance/blender_scripts/glb_worker.py"
    spec = importlib.util.spec_from_file_location("glb_test_worker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.opened = opened
    return module


def request_file(tmp_path, operation="import", pixels=16):
    root = tmp_path.resolve()
    inputs = root / "inputs"
    outputs = root / "outputs"
    inputs.mkdir()
    outputs.mkdir()
    policy_value = policy(root)
    policy_value["limits"]["max_texture_pixels"] = 512
    asset = inputs / ("asset.glb" if operation == "import" else "asset.blend")
    asset.write_bytes(make_glb(pixels) if operation == "import" else b"GOOD")
    fid = "delivery.glb" if operation == "import" else "asset"
    values = {fid: asset}
    if operation == "import":
        budget = measure_glb(asset, policy_value["limits"])
        rows = [
            {
                "pointer": "/buffers/0",
                "storage": "glb",
                "byteLength": json.loads(
                    asset.read_bytes()[
                        20 : 20 + int.from_bytes(asset.read_bytes()[12:16], "little")
                    ]
                )["buffers"][0]["byteLength"],
            },
            {
                "pointer": "/images/0",
                "storage": "buffer-view",
                "mimeType": "image/png",
                "image": {
                    "width": pixels,
                    "height": pixels,
                    "bits": 8,
                    "format": "rgba",
                    "primaries": "srgb",
                    "transfer": "srgb",
                },
            },
        ]
        report = {"issues": {"numErrors": 0, "truncated": False}, "info": {"resources": rows}}
        resources = dict(
            schema_version=2,
            input_sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),
            input_bytes=asset.stat().st_size,
            external_requests=[],
            resources=rows,
        )
        data = {"glb.budget": budget, "validator.report": report, "validator.resources": resources}
        out_ids = ("projection.import", "render.projection_import")
    else:
        data = {
            "native.manifest": {"occurrences": [{"source": ["OBJECT", "Asset"]}]},
            "projection.source": projection(),
        }
        out_ids = ("render.projection_source",)
    for key, value in data.items():
        path = inputs / (key + ".json")
        path.write_text(json.dumps(value))
        values[key] = path
    request = dict(
        schema_version=2,
        run_id="test-glb",
        attempt=1,
        nonce="a" * 32,
        job_id="glb.test",
        writer="reimport_probe",
        contract_digest="c" * 64,
        source_digest="d" * 64,
        input_root=str(inputs),
        output_root=str(outputs),
        inputs=[
            measure_file(path, 1000000, file_id=key).descriptor(path.name)
            for key, path in values.items()
        ],
        outputs=[
            dict(id=key, path=key + ".json", media_type="application/json", max_bytes=1000000)
            for key in out_ids
        ],
        parameters=dict(operation=operation, policy=policy_value, native=native_policy()),
    )
    path = root / "request.json"
    path.write_text(json.dumps(request))
    return path, asset, outputs


@pytest.mark.parametrize("operation", ["import", "source_render", "export"])
def test_exact_descriptor_replacement_before_open_is_blocked(worker, tmp_path, operation):
    path, asset, outputs = request_file(tmp_path, operation)
    request = read_request(path)
    asset.write_bytes(b"X" * asset.stat().st_size)
    with pytest.raises(ValueError, match="frozen"):
        worker.work(request)
    assert not worker.opened and not list(outputs.iterdir())


@pytest.mark.parametrize("operation", ["import", "source_render"])
def test_exact_descriptor_after_render_is_still_required(worker, tmp_path, monkeypatch, operation):
    path, asset, outputs = request_file(tmp_path, operation)

    def render(*a, **kw):
        asset.write_bytes(b"X" * asset.stat().st_size)
        return {}

    monkeypatch.setattr(worker, "render_images", render)
    with pytest.raises(ValueError, match="frozen"):
        worker.work(read_request(path))
    assert len(worker.opened) == 1
    assert not (
        outputs
        / (
            "render.projection_import.json"
            if operation == "import"
            else "render.projection_source.json"
        )
    ).exists()


def test_valid_small_png_imports_exact_job_copy_without_another_copy(worker, tmp_path):
    path, asset, outputs = request_file(tmp_path)
    checks = worker.work(read_request(path))
    assert len(worker.opened) == 1 and worker.opened[0]["filepath"] == str(asset)
    assert checks[0]["id"] == "r4.import.manifest_written" and not checks[0]["findings"]


def test_valid_byte_bounded_png_above_pixel_cap_never_reaches_importer(worker, tmp_path):
    path, asset, outputs = request_file(tmp_path, pixels=64)
    request = read_request(path)
    assert not measure_glb(asset, request["parameters"]["policy"]["limits"])["exceeded"]
    with pytest.raises(ValueError, match="resource"):
        worker.work(request)
    assert not worker.opened and not list(outputs.iterdir())


def test_source_render_rejects_received_projection_mismatch(worker, tmp_path):
    path, asset, outputs = request_file(tmp_path, "source_render")
    proj = asset.parent / "projection.source.json"
    data = json.loads(proj.read_text())
    data["objects"][0]["vertices"] += 1
    proj.write_text(json.dumps(data))
    # A received valid descriptor of different projection must still fail exact source reconstruction.
    request = json.loads(path.read_text())
    request["inputs"] = [
        measure_file(Path(request["input_root"]) / r["path"], 1000000, file_id=r["id"]).descriptor(
            r["path"]
        )
        for r in request["inputs"]
    ]
    path.write_text(json.dumps(request))
    with pytest.raises(ValueError, match="projection"):
        worker.work(read_request(path))
    assert not list(outputs.iterdir())


@pytest.mark.parametrize(
    "mutation",
    [
        "hash",
        "bytes",
        "external",
        "pointer",
        "duplicate",
        "error",
        "truncated",
        "extension",
        "budget",
    ],
)
def test_resource_and_validation_safety_precedes_import(worker, tmp_path, mutation):
    path, asset, outputs = request_file(tmp_path)
    request = read_request(path)
    resources_path = asset.parent / "validator.resources.json"
    report_path = asset.parent / "validator.report.json"
    budget_path = asset.parent / "glb.budget.json"
    resources = json.loads(resources_path.read_text())
    report = json.loads(report_path.read_text())
    budget = json.loads(budget_path.read_text())
    if mutation == "hash":
        resources["input_sha256"] = "f" * 64
    elif mutation == "bytes":
        resources["input_bytes"] += 1
    elif mutation == "external":
        resources["external_requests"] = ["https://external.invalid/image.png"]
    elif mutation == "pointer":
        resources["resources"].pop()
    elif mutation == "duplicate":
        resources["resources"].append(resources["resources"][0])
    elif mutation == "error":
        report["issues"]["numErrors"] = 1
    elif mutation == "truncated":
        report["issues"]["truncated"] = True
    elif mutation == "extension":
        budget["extensions"] = ["KHR_unknown"]
    elif mutation == "budget":
        budget["exceeded"] = ["stored_triangles"]
    report["info"]["resources"] = resources["resources"]
    resources_path.write_text(json.dumps(resources))
    report_path.write_text(json.dumps(report))
    budget_path.write_text(json.dumps(budget))
    from acceptance.primitives import AcceptanceFailure

    with pytest.raises((ValueError, AcceptanceFailure)):
        worker.work(request)
    assert not worker.opened and not list(outputs.iterdir())
