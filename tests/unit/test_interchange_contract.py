from copy import deepcopy
import pytest
from acceptance import check_registry as registry
from acceptance.contract import validate_document
from acceptance.input_bundle import source_digest
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document
from tests.unit.interchange_support import policy as interchange_policy
from tests.unit.test_native_policy import policy as native_policy
from acceptance.canonical import digest
from pathlib import Path
from acceptance.interchange_plan import build_interchange_plan, interchange_commands
from acceptance.contract import load_contract
import json


def integrated_document(tmp_path, kind):
    value = valid_document(tmp_path)
    value["artifact_kind"] = kind
    value["checks"] = [
        {"id": item.id, "impl": item.impl, "order": item.order}
        for item in sorted(registry.checks_for_kind(kind), key=registry.sort_key)
    ]
    value["na_check_ids"] = list(registry.na_check_ids(kind))
    value["native"] = native_policy()
    value["interchange"] = interchange_policy(tmp_path) if kind == "interchange" else None
    ids = {
        "asset",
        "alternate",
        value["native"]["reference_manifest_id"],
        value["native"]["reference_authority"],
    }
    ids.update(value["native"]["render"]["reference_images"].values())
    rows = [
        {"id": key, "path": key + ".bin", "bytes": 1, "sha256": "a" * 64} for key in sorted(ids)
    ]
    value["input"] = {"main": "asset", "sha256": source_digest(rows), "files": rows}
    return value


@pytest.mark.parametrize("kind", ["blend_native", "interchange"])
def test_combined_contract_accepts_complete_frozen_references(tmp_path, kind):
    validate_document(integrated_document(tmp_path, kind))


@pytest.mark.parametrize("kind", ["blend_native", "interchange"])
@pytest.mark.parametrize("mutation", ["authority", "manifest", "image", "main", "invalid_policy"])
def test_combined_contract_preserves_native_binding_guards(tmp_path, kind, mutation):
    value = deepcopy(integrated_document(tmp_path, kind))
    if mutation == "authority":
        value["native"]["reference_authority"] = "unfrozen.authority"
    elif mutation == "manifest":
        value["native"]["reference_manifest_id"] = "unfrozen.manifest"
    elif mutation == "image":
        value["native"]["render"]["reference_images"]["front.beauty"] = "unfrozen.image"
    elif mutation == "main":
        value["input"]["main"] = "alternate"
    else:
        value["native"]["frame"] = True
    with pytest.raises(AcceptanceFailure) as caught:
        validate_document(value)
    assert caught.value.code == "contract_invalid"


PACKAGE_MEMBERS = (
    "package.json",
    "package-lock.json",
    "node_modules/gltf-validator/package.json",
    "node_modules/gltf-validator/index.js",
    "node_modules/gltf-validator/gltf_validator.dart.js",
)


def plan_contract(tmp_path):
    value = integrated_document(tmp_path, "interchange")
    from tests.unit.interchange_support import lock_gltf_fixture
    lock_gltf_fixture(tmp_path, value["tools"][2])
    value["tools"].append(
        dict(
            id="node",
            path="/node",
            version="v20.20.2",
            sha256="a" * 64,
            files=[dict(path=str(tmp_path / x), bytes=1, sha256="a" * 64) for x in PACKAGE_MEMBERS],
        )
    )
    value["limits"]["timeout_seconds"].update(
        {
            k: 5
            for k in interchange_commands(
                Path("/blender"), Path("/node"), Path("/python"), Path("/repo")
            )
        }
    )
    p = tmp_path / "contract.json"
    p.write_text(json.dumps(value))
    return load_contract(p, candidate_root=tmp_path / "source"), value


def test_interchange_plan_consumes_frozen_projection_and_resources(tmp_path):
    contract, _ = plan_contract(tmp_path)
    plan = build_interchange_plan(contract)
    jobs = {job.job_id: job for job in plan.jobs}
    assert "projection.source" in jobs["glb.projection_source"].input_ids
    assert "validator.resources" in jobs["glb.projection_import"].input_ids
    assert "native.reopen" not in jobs
    files = [f for j in plan.jobs for f in j.outputs]
    assert len([f for f in files if f.id.startswith("image.projection_")]) == 72
    assert len([f for f in files if f.id.startswith("diff.projection.")]) == 36


@pytest.mark.parametrize("missing", PACKAGE_MEMBERS + ("alternate_root",))
def test_plan_rejects_unlocked_actual_validator_package(tmp_path, missing):
    contract, value = plan_contract(tmp_path)
    if missing == "alternate_root":
        value["interchange"]["package_root"] = str(tmp_path / "other")
    else:
        value["tools"][-1]["files"] = [
            f for f in value["tools"][-1]["files"] if f["path"] != str(tmp_path / missing)
        ]
    contract = type(contract)(value, digest("contract.v2", value))
    with pytest.raises(AcceptanceFailure) as caught:
        build_interchange_plan(contract)
    assert caught.value.code == "toolchain_mismatch"


@pytest.mark.parametrize("mutation", ["one", "all", "new", "drift", "symlink", "cache_symlink"])
@pytest.mark.parametrize("boundary", ["plan", "measure"])
def test_gltf_content_closure_at_public_boundaries(tmp_path, mutation, boundary):
    from acceptance.toolchain import measure_tool
    from tests.unit.asset_v2_support import REPO
    contract, value = plan_contract(tmp_path)
    blender = value["tools"][2]
    root = Path(blender["path"]).parents[1] / "Resources/5.2/scripts/addons_core/io_scene_gltf2"
    if mutation in ("one", "all"):
        blender["files"] = [f for f in blender["files"] if not (
            root in Path(f["path"]).parents and (mutation == "all" or Path(f["path"]).name == "importer.py"))]
    elif mutation == "new":
        (root / "new.py").write_text("new unbound execution member")
    elif mutation == "drift":
        (root / "importer.py").write_text("changed contents")
    else:
        link = root / ("__pycache__" if mutation == "cache_symlink" else "linked.py")
        link.symlink_to(tmp_path, target_is_directory=mutation == "cache_symlink")
    contract = type(contract)(value, digest("contract.v2", value))
    with pytest.raises(AcceptanceFailure) as caught:
        if boundary == "plan":
            build_interchange_plan(contract)
        else:
            measure_tool(blender, REPO, require_blender_gltf=True)
    assert caught.value.code == "toolchain_mismatch"


@pytest.mark.parametrize("boundary", ["plan", "r0"])
def test_interchange_requires_closure_even_without_any_gltf_hint(tmp_path, boundary):
    from acceptance.contract import thaw
    from acceptance.stages import run_r0
    contract, value = plan_contract(tmp_path)
    value["tools"][2]["files"] = []
    contract = type(contract)(value, digest("contract.v2", value))
    if boundary == "plan":
        with pytest.raises(AcceptanceFailure, match="closure"):
            build_interchange_plan(contract)
    else:
        measured = [
            {
                "id": tool["id"],
                "path": tool["path"],
                "sha256": tool["sha256"],
                "version": tool["version"],
                "files": thaw(tool["files"]),
            }
            for tool in value["tools"]
        ]
        result = run_r0(contract, tools_measured=measured)
        assert "closure" in result["r0.contract.tools_locked"][0].detail


@pytest.mark.parametrize("problem", ["missing_directory", "enumeration_error", "nonregular"])
def test_gltf_closure_scan_fails_closed(tmp_path, monkeypatch, problem):
    import os
    import shutil
    from acceptance import toolchain
    from tests.unit.asset_v2_support import REPO
    _, value = plan_contract(tmp_path)
    blender = value["tools"][2]
    root = Path(blender["path"]).parents[1] / "Resources/5.2/scripts/addons_core/io_scene_gltf2"
    if problem == "missing_directory":
        shutil.rmtree(root)
    elif problem == "nonregular":
        os.mkfifo(root / "unexpected.pipe")
    else:
        def fail(_root, *, followlinks, onerror):
            onerror(PermissionError("controlled glTF enumeration failure"))
            return iter(())
        monkeypatch.setattr(toolchain.os, "walk", fail)
    with pytest.raises(AcceptanceFailure) as caught:
        toolchain.measure_tool(blender, REPO, require_blender_gltf=True)
    assert caught.value.code == "toolchain_mismatch"
