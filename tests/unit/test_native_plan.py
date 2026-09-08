from types import SimpleNamespace
from pathlib import Path
from acceptance.native_plan import native_jobs, native_commands, UNSAFE_R2
from acceptance.native_policy import VIEWS, PASSES


def test_native_jobs_preserve_required_images_and_unique_owners():
    platform = {
        "blender": "5.2.0 LTS",
        "build": "fbe6228777e7",
        "os": "Darwin",
        "arch": "arm64",
        "backend": "METAL",
        "vendor": "Apple M4",
        "gpu": "Metal API",
        "engines": "BLENDER_EEVEE,BLENDER_WORKBENCH",
        "view_transform": "Standard",
        "look": "None",
        "format": "PNG_RGBA8",
        "comparator": "blender-rgba-f32-v1",
    }
    policy = {
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "support_profile": "native-static-v1",
        "reference_manifest_id": "native.reference",
        "reference_authority": "trusted-native-fixture-v1",
        "geometry_limits": {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 1048576,
        },
        "render": {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
            "beauty_hard_gate": False,
            "platform": platform,
            "max_abs": {p: 0 for p in PASSES},
            "reference_images": {
                v + "." + p: "reference." + v + "." + p for v in VIEWS for p in PASSES
            },
        },
    }
    contract = SimpleNamespace(raw={"native": policy}, artifact_kind="blend_native")
    jobs = native_jobs(contract)
    files = [f for job in jobs for f in job.outputs]
    assert len([f for f in files if f.id.startswith("image.")]) == 135
    assert len([f for f in files if f.id.startswith("diff.")]) == 99
    assert len({f.id for f in files}) == len(files)
    assert len([c for job in jobs for c in job.check_ids]) == 14
    assert all(
        job.blocking_check_ids == UNSAFE_R2 for job in jobs if job.job_id != "native.inspect"
    )
    assert not any(
        "r4.reopen." in c
        for job in native_jobs(contract, include_reopen=False)
        for c in job.check_ids
    )
    assert all(f.writer == job.writer for job in jobs for f in job.outputs)


def test_commands_cannot_come_from_candidate_properties():
    commands = native_commands(
        Path("/Applications/Blender.app/Contents/MacOS/Blender"), Path("/trusted/repo")
    )
    for argv in commands.values():
        assert "--disable-autoexec" in argv and "--offline-mode" in argv
        assert argv[argv.index("--python-exit-code") + 1] == "1"
        assert argv[-1] == "--" and "--request" not in argv


def native_document(tmp_path):
    from acceptance.input_bundle import measure_file, source_digest
    from tests.unit.asset_v2_support import valid_document
    from tests.unit.test_native_policy import policy

    value = valid_document(tmp_path)
    value["native"] = policy()
    native = value["native"]
    ids = (
        native["reference_manifest_id"],
        native["reference_authority"],
        *native["render"]["reference_images"].values(),
    )
    for fid in ids:
        path = tmp_path / "source" / (fid + ".bin")
        path.write_bytes(b"frozen reference fixture")
        value["input"]["files"].append(measure_file(path, 1024, file_id=fid).descriptor(path.name))
    value["input"]["files"].sort(key=lambda row: row["id"])
    value["input"]["sha256"] = source_digest(value["input"]["files"])
    value["limits"]["timeout_seconds"].update(
        {writer: 5 for writer in native_commands(Path("/blender"), Path("/repo"))}
    )
    return value


def test_contract_accepts_only_frozen_native_reference_members(tmp_path):
    from acceptance.contract import validate_document
    from acceptance.primitives import AcceptanceFailure
    import pytest

    value = native_document(tmp_path)
    validate_document(value)
    for field in ("reference_manifest_id", "reference_authority"):
        old = value["native"][field]
        value["native"][field] = "not-frozen"
        with pytest.raises(AcceptanceFailure, match="frozen input members"):
            validate_document(value)
        value["native"][field] = old
    value["native"]["render"]["reference_images"]["front.clay"] = "not-frozen"
    with pytest.raises(AcceptanceFailure, match="frozen input members"):
        validate_document(value)


def test_single_assembled_file_plan_preserves_references_and_core_owners(tmp_path):
    from acceptance.native_plan import build_native_plan, NATIVE_GATES
    from tests.unit.asset_v2_support import write_contract

    contract = write_contract(tmp_path, native_document(tmp_path))
    plan = build_native_plan(contract)
    assert plan.gate_ids == NATIVE_GATES
    assert len(plan.files) == 268  # 242 business outputs, 24 controller/job records, run and gates.
    assert len({f.id for f in plan.files}) == len(plan.files)
    assert len({f.path for f in plan.files}) == len(plan.files)
    compare_job = plan.jobs[-1]
    frozen_images = set(contract.raw["native"]["render"]["reference_images"].values())
    assert len(frozen_images) == 36 and frozen_images <= set(compare_job.input_ids)
    assert not frozen_images & {f.id for f in plan.files}
    for job in plan.jobs:
        assert not any(f.path == "result.json" for f in job.outputs)
        assert sum(f.id == job.job_id + ".result" for f in plan.files) == 1
    for f in plan.files:
        if f.id.startswith(("image.", "diff.")):
            assert f.max_bytes == 16 * 1024 * 1024
    assert all(value == 0 for value in contract.raw["native"]["render"]["max_abs"].values())
