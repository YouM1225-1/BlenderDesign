"""Exercise actual worker branches; only Blender collection/render/open are substitutes."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from acceptance.input_bundle import measure_file
from acceptance.worker_protocol import read_request
from tests.unit.test_native_checks import sample
from tests.unit.test_native_policy import policy


@pytest.fixture
def worker(monkeypatch):
    bpy = SimpleNamespace(
        app=SimpleNamespace(
            online_access=False, version_string="5.2.0 LTS", build_hash=b"fbe6228777e7"
        ),
        ops=SimpleNamespace(wm=SimpleNamespace(open_mainfile=lambda **kwargs: None)),
    )
    monkeypatch.setitem(sys.modules, "bpy", bpy)
    monkeypatch.setitem(
        sys.modules,
        "acceptance.blender_scripts.native_collect",
        SimpleNamespace(collect=lambda *a, **kw: sample()),
    )
    monkeypatch.setitem(
        sys.modules,
        "acceptance.blender_scripts.native_render",
        SimpleNamespace(render_images=None, compare=None),
    )
    path = Path(__file__).resolve().parents[2] / "acceptance/blender_scripts/native_worker.py"
    spec = importlib.util.spec_from_file_location("task5_test_worker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_file(tmp_path, operation="reopen"):
    # Physical local spelling: macOS /var temporary aliases must not bypass no-link checks.
    root = tmp_path.resolve()
    inputs, outputs = root / "input", root / "output"
    inputs.mkdir()
    outputs.mkdir()
    asset = inputs / "asset.blend"
    asset.write_bytes(b"GOOD")
    manifest = inputs / "native.manifest.json"
    manifest.write_text(json.dumps(sample()))
    request = dict(
        schema_version=2,
        run_id="native-regression",
        attempt=1,
        nonce="a" * 32,
        job_id="native." + operation,
        writer="reopen_probe" if operation == "reopen" else "inspector",
        contract_digest="b" * 64,
        source_digest="c" * 64,
        input_root=str(inputs),
        output_root=str(outputs),
        inputs=[
            measure_file(p, 100000, file_id=fid).descriptor(p.name)
            for fid, p in (("asset", asset), ("native.manifest", manifest))
        ],
        outputs=[
            dict(id=fid, path=fid + ".json", media_type="application/json", max_bytes=100000)
            for fid in (
                ("native.reopened", "native.reopen_dependencies")
                if operation == "reopen"
                else ("native.manifest", "native.dependencies")
            )
        ],
        parameters=dict(operation=operation, experiment="none", policy=policy()),
    )
    path = root / "request.json"
    path.write_text(json.dumps(request))
    return path, asset, outputs


def test_actual_worker_reopen_opens_distinct_exact_frozen_member(worker, tmp_path, monkeypatch):
    path, asset, outputs = request_file(tmp_path)
    request = read_request(path)
    opened = []

    def open_file(**kwargs):
        fresh = Path(kwargs["filepath"])
        opened.append((fresh, fresh.read_bytes()))
        assert kwargs == dict(filepath=str(fresh), load_ui=False, use_scripts=False)

    monkeypatch.setattr(worker.bpy.ops.wm, "open_mainfile", open_file)
    checks = worker.work(request)
    assert len(opened) == 1 and opened[0][0] != asset
    assert opened[0][1] == b"GOOD" and not opened[0][0].exists()
    assert all(not row["findings"] for row in checks)
    report = json.loads((outputs / "native.reopen_dependencies.json").read_text())
    expected = request["inputs"][0]
    assert report["input_sha256"] == report["reopened_sha256"] == expected["sha256"]
    assert report["input_bytes"] == report["reopened_bytes"] == expected["bytes"]
    assert report["input_sha256"] != request["source_digest"]


def test_replacement_after_read_request_prevents_open_and_result(worker, tmp_path, monkeypatch):
    path, asset, outputs = request_file(tmp_path)

    def replaced_request(value):
        validated = read_request(value)
        asset.write_bytes(b"EVIL")  # Same length; descriptors retain original frozen identity.
        return validated

    opened = []
    monkeypatch.setattr(worker, "read_request", replaced_request)
    monkeypatch.setattr(worker.bpy.ops.wm, "open_mainfile", lambda **kw: opened.append(kw))
    monkeypatch.setattr(sys, "argv", ["blender", "--", "--request", str(path)])
    with pytest.raises(ValueError, match="frozen asset"):
        worker.main()
    assert not opened and not list(outputs.iterdir())


@pytest.mark.parametrize("operation", ["inspect", "reopen"])
def test_post_copy_drift_remains_failed_evidence(worker, tmp_path, monkeypatch, operation):
    path, asset, outputs = request_file(tmp_path, operation)
    fresh_paths = []
    monkeypatch.setattr(
        worker.bpy.ops.wm, "open_mainfile", lambda **kw: fresh_paths.append(Path(kw["filepath"]))
    )

    def collect(*args, **kwargs):
        fresh_paths[0].chmod(0o600)
        fresh_paths[0].write_bytes(b"EVIL")
        return sample()

    monkeypatch.setattr(worker, "collect", collect)
    checks = worker.work(read_request(path))
    check_id = "r4.reopen.offline_ok" if operation == "reopen" else "r2.source.digest_stable"
    assert next(row for row in checks if row["id"] == check_id)["findings"]
    assert asset.read_bytes() == b"GOOD"


@pytest.mark.parametrize("defect", ["nan", "invalid_face"])
def test_invalid_source_geometry_is_inspector_evidence(worker, tmp_path, monkeypatch, defect):
    path, _, outputs = request_file(tmp_path, "inspect")
    manifest = sample()
    if defect == "nan":
        manifest["meshes"]["Body"]["authored"]["vertices"][0][0] = None
        manifest["invalid_numbers"] = [
            {"path": ["meshes", "Body", "authored", "vertices", 0, 0], "value": "nan"}
        ]
        check_id = "r2.inventory.no_nan_inf"
    else:
        manifest["meshes"]["Body"]["authored"]["validate_corrected"] = True
        check_id = "r2.geometry.validate_clean"
    monkeypatch.setattr(worker, "collect", lambda *a, **kw: manifest)
    checks = worker.work(read_request(path))
    assert next(row for row in checks if row["id"] == check_id)["findings"]
    assert json.loads((outputs / "native.manifest.json").read_text()) == manifest


def test_main_binds_result_identity_and_excludes_own_result(worker, tmp_path, monkeypatch):
    from acceptance.worker_protocol import IDENTITY

    path, _, outputs = request_file(tmp_path)
    request = read_request(path)
    monkeypatch.setattr(sys, "argv", ["blender", "--", "--request", str(path)])
    worker.main()
    result = json.loads((outputs / "result.json").read_text())
    assert {key: result[key] for key in IDENTITY} == {key: request[key] for key in IDENTITY}
    assert {row["id"] for row in result["artifacts"]} == {row["id"] for row in request["outputs"]}
    assert all(row["path"] != "result.json" for row in result["artifacts"])
    assert result["observations"]["blender"] == "5.2.0 LTS"


def test_original_drift_after_copy_prevents_blender_open(worker, tmp_path, monkeypatch):
    path, asset, outputs = request_file(tmp_path)
    request = read_request(path)
    measured = worker.measure_file

    def copy_then_drift(*args, **kwargs):
        result = measured(*args, **kwargs)
        if kwargs.get("copy_to"):
            asset.write_bytes(b"EVIL")
        return result

    opened = []
    monkeypatch.setattr(worker, "measure_file", copy_then_drift)
    monkeypatch.setattr(worker.bpy.ops.wm, "open_mainfile", lambda **kw: opened.append(kw))
    with pytest.raises(ValueError, match="frozen asset"):
        worker.work(request)
    assert not opened and not list(outputs.iterdir())


@pytest.mark.parametrize("drift", [False, True])
def test_render_preserves_signature_and_frozen_post_operation_identity(
    worker, tmp_path, monkeypatch, drift
):
    path, _, outputs = request_file(tmp_path)
    request = read_request(path)
    request["parameters"].update(operation="render", experiment="fresh_a")
    request["outputs"] = [dict(id="render.fresh_a", path="render.json")]
    fresh_paths = []
    monkeypatch.setattr(
        worker.bpy.ops.wm, "open_mainfile", lambda **kw: fresh_paths.append(Path(kw["filepath"]))
    )

    def render(manifest, settings, files, experiment):
        assert manifest == sample() and settings == policy()["render"]
        assert files == {"render.fresh_a": outputs / "render.json"} and experiment == "fresh_a"
        if drift:
            fresh_paths[0].chmod(0o600)
            fresh_paths[0].write_bytes(b"EVIL")
        return {"schema_version": 2, "platform": settings["platform"], "images": []}

    monkeypatch.setattr(worker, "render_images", render)
    if drift:
        with pytest.raises(ValueError, match="frozen asset"):
            worker.work(request)
        assert not list(outputs.iterdir())
    else:
        assert worker.work(request) == []
        report = json.loads((outputs / "render.json").read_text())
        assert (
            report["source_digest_before"]
            == report["source_digest_after"]
            == request["inputs"][0]["sha256"]
        )


def test_compare_routes_all_pairs_to_frozen_reference_ids(worker, tmp_path, monkeypatch):
    from acceptance.native_plan import native_jobs
    from acceptance.native_policy import VIEWS, PASSES

    root = tmp_path.resolve()
    inputs, outputs = root / "input", root / "output"
    inputs.mkdir()
    outputs.mkdir()
    job = native_jobs(SimpleNamespace(raw={"native": policy()}))[-1]
    for fid in ("native.manifest", "native.reference"):
        (inputs / fid).write_text(json.dumps(sample()))
    request = dict(
        parameters=dict(operation="compare", experiment="none", policy=policy()),
        input_root=str(inputs),
        output_root=str(outputs),
        inputs=[dict(id=fid, path=fid) for fid in job.input_ids],
        outputs=[dict(id=f.id, path=f.path) for f in job.outputs],
    )
    measured = []

    def compare(left, right, diff, max_pixels):
        assert max_pixels == policy()["geometry_limits"]["max_image_pixels"]
        measured.append((left.name, right.name, diff.name))
        return {"different_pixels": 0}

    monkeypatch.setattr(worker, "compare", compare)
    assert worker.work(request) == []
    result_path = next(outputs / f.path for f in job.outputs if f.id == "native.comparisons")
    report = json.loads(result_path.read_text())
    assert len(report["comparisons"]) == len(measured) == 99
    assert not report["reference_findings"] and not report["geometry_findings"]
    expected = set()
    for view in VIEWS:
        for render_pass in PASSES:
            suffix = f"{view}.{render_pass}"
            expected.add(
                (
                    f"image.fresh_a.0.{suffix}",
                    f"image.fresh_b.0.{suffix}",
                    f"diff.fresh.{suffix}.png",
                )
            )
            expected.add(
                (
                    f"image.same_process.0.{suffix}",
                    policy()["render"]["reference_images"][suffix],
                    f"diff.reference.{suffix}.png",
                )
            )
            if render_pass != "beauty":
                expected.add(
                    (
                        f"image.same_process.0.{suffix}",
                        f"image.same_process.1.{suffix}",
                        f"diff.same.{suffix}.png",
                    )
                )
    assert set(measured) == expected
