from __future__ import annotations

import copy
import hashlib
import json

import pytest

from acceptance.plan import FileSpec, JobSpec, RunPlan, assemble_plan
from acceptance.primitives import AcceptanceFailure
from acceptance.worker_protocol import read_request, validate_result, write_result
from tests.unit.asset_v2_support import valid_document, write_contract


def request_fixture(tmp_path):
    inputs, outputs = tmp_path / "input", tmp_path / "output"
    inputs.mkdir()
    outputs.mkdir()
    return {
        "schema_version": 2,
        "run_id": "run-001",
        "attempt": 1,
        "nonce": "a" * 32,
        "job_id": "inspect",
        "writer": "inspector",
        "contract_digest": "b" * 64,
        "source_digest": "c" * 64,
        "input_root": str(inputs),
        "inputs": [],
        "output_root": str(outputs),
        "outputs": [],
        "parameters": {},
    }


def read_fixture(tmp_path, request):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    return read_request(path)


def input_descriptor(path, file_id="asset", relative="asset.blend"):
    raw = path.read_bytes()
    return {
        "id": file_id,
        "path": relative,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def test_result_has_no_self_reference_and_controller_owns_state(tmp_path):
    request = read_fixture(tmp_path, request_fixture(tmp_path))
    result_path = write_result(
        request, [{"id": "r2.inventory.no_nan_inf", "findings": [], "metrics": {}}], {}
    )
    result = json.loads(result_path.read_text())
    assert result["artifacts"] == []
    assert validate_result(result, request, ("r2.inventory.no_nan_inf",)) == result
    result["success"] = True
    with pytest.raises(ValueError, match="closed result"):
        validate_result(result, request, ("r2.inventory.no_nan_inf",))


@pytest.mark.parametrize(
    "change", ["nonce", "version", "check", "duplicate", "disposition", "nan", "artifact"]
)
def test_result_boundary_rejects_forgery(tmp_path, change):
    request = request_fixture(tmp_path)
    path = write_result(
        request, [{"id": "r2.inventory.no_nan_inf", "findings": [], "metrics": {}}], {}
    )
    result = json.loads(path.read_text())
    if change == "nonce":
        result["nonce"] = "d" * 32
    elif change == "version":
        result["schema_version"] = 1
    elif change == "check":
        result["checks"][0]["id"] = "r0.contract.tools_locked"
    elif change == "duplicate":
        result["checks"].append(copy.deepcopy(result["checks"][0]))
    elif change == "disposition":
        result["checks"][0]["findings"] = [
            {
                "code": "x",
                "severity": "warning",
                "pointer": None,
                "detail": None,
                "disposition": "AcceptedWarning",
            }
        ]
    elif change == "nan":
        result["checks"][0]["metrics"] = {"bad": float("nan")}
    else:
        result["artifacts"] = [
            {"id": "self", "path": "result.json", "bytes": 1, "sha256": "a" * 64}
        ]
    with pytest.raises(ValueError):
        validate_result(result, request, ("r2.inventory.no_nan_inf",))


def test_plan_derives_required_checks_and_closes_writers(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    plan = assemble_plan(contract, ())
    assert len(plan.check_ids) == 24 and len(plan.na_check_ids) == 13
    assert {f.id for f in plan.files} == {"run", "gates"}
    job = JobSpec(
        "inspect", "inspector", "blender", ("r0.contract.tools_locked",), ("asset",), (), {}
    )
    with pytest.raises(AcceptanceFailure, match="writer"):
        assemble_plan(contract, (job,))
    job = JobSpec("inspect", "inspector", "blender", (), ("missing",), (), {})
    with pytest.raises(AcceptanceFailure, match="earlier job"):
        assemble_plan(contract, (job,))


def test_plan_values_snapshot_supported_ordered_inputs(tmp_path):
    checks = ["r2.inventory.no_nan_inf"]
    inputs = ["asset"]
    outputs = []
    blocked = []
    nested = {"items": [{"name": "original"}]}
    job = JobSpec("inspect", "inspector", "blender", checks, inputs, outputs, nested, blocked)
    checks.append("r2.geometry.validate_clean")
    inputs.append("later")
    outputs.append(FileSpec("late", "late.json", "inspector", "application/json", 1))
    blocked.append("r0.contract.schema_closed")
    nested["items"][0]["name"] = "changed"
    assert job.check_ids == ("r2.inventory.no_nan_inf",)
    assert job.input_ids == ("asset",)
    assert job.outputs == ()
    assert job.blocking_check_ids == ()
    assert job.parameters["items"][0]["name"] == "original"

    contract = write_contract(tmp_path, valid_document(tmp_path))
    jobs = [job]
    gates = ["gate.review"]
    plan = assemble_plan(contract, jobs, gate_ids=gates)
    jobs.clear()
    gates.clear()
    assert plan.jobs == (job,)
    assert plan.gate_ids == ("gate.review",)


def test_direct_run_plan_snapshots_all_sequences():
    file = FileSpec("view", "view.png", "render_views(src)", "image/png", 1024)
    job = JobSpec("render", "render_views(src)", "blender", [], [], [file], {})
    jobs, files = [job], [file]
    checks, na_checks = ["r4.visual.scene_not_empty"], ["r3.export.file_nonempty"]
    tools, gates = ["blender"], ["gate.review"]
    plan = RunPlan(jobs, files, checks, na_checks, tools, gates)
    for values in (jobs, files, checks, na_checks, tools, gates):
        values.clear()
    assert plan.jobs == (job,)
    assert plan.files == (file,)
    assert plan.check_ids == ("r4.visual.scene_not_empty",)
    assert plan.na_check_ids == ("r3.export.file_nonempty",)
    assert plan.required_tools == ("blender",)
    assert plan.gate_ids == ("gate.review",)


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (lambda: FileSpec("file", "file.json", [], "application/json", 1), "writer"),
        (lambda: FileSpec("file", "file.json", "writer", 1, 1), "type/budget"),
        (lambda: JobSpec("job", "writer", [], (), (), (), {}), "tool"),
        (lambda: JobSpec("job", "writer", "python", [1], (), (), {}), "check_ids"),
        (lambda: JobSpec("job", "writer", "python", (), (), [object()], {}), "outputs"),
        (lambda: RunPlan([object()], (), (), (), ()), "jobs"),
        (lambda: RunPlan((), (), [1], (), ()), "check_ids"),
    ],
)
def test_plan_constructors_reject_malformed_elements_with_typed_failure(factory, match):
    with pytest.raises(AcceptanceFailure, match=match) as failure:
        factory()
    assert failure.value.code == "contract_invalid"


def test_job_parameters_must_be_canonical_json_and_are_deeply_frozen():
    with pytest.raises(AcceptanceFailure, match="parameters") as failure:
        JobSpec("job", "writer", "python", (), (), (), {"mutable": {1}})
    assert failure.value.code == "contract_invalid"
    with pytest.raises(AcceptanceFailure, match="parameters"):
        JobSpec("job", "writer", "python", (), (), (), {"too_large": 10**10000})
    cyclic = {}
    cyclic["self"] = cyclic
    with pytest.raises(AcceptanceFailure, match="parameters"):
        JobSpec("job", "writer", "python", (), (), (), cyclic)


@pytest.mark.parametrize(
    "change",
    [
        "bytes_bool",
        "id_list",
        "duplicate_id",
        "duplicate_path",
        "output_media",
        "output_id_list",
        "output_budget_bool",
        "output_duplicate_id",
        "output_duplicate_path",
    ],
)
def test_request_rejects_bad_descriptor_types_and_duplicates(tmp_path, change):
    request = request_fixture(tmp_path)
    asset = tmp_path / "input" / "asset.blend"
    asset.write_bytes(b"asset")
    row = input_descriptor(asset)
    request["inputs"] = [row]
    if change == "bytes_bool":
        row["bytes"] = True
    elif change == "id_list":
        row["id"] = ["asset"]
    elif change == "duplicate_id":
        request["inputs"].append({**row, "path": "other.blend"})
    elif change == "duplicate_path":
        request["inputs"].append({**row, "id": "other"})
    else:
        output = {"id": "view", "path": "view.png", "media_type": "image/png", "max_bytes": 10}
        request["outputs"] = [output]
        if change == "output_media":
            output["media_type"] = "unknown/type"
        elif change == "output_id_list":
            output["id"] = ["view"]
        elif change == "output_budget_bool":
            output["max_bytes"] = True
        elif change == "output_duplicate_id":
            request["outputs"].append({**output, "path": "other.png"})
        else:
            request["outputs"].append({**output, "id": "other"})
    with pytest.raises(ValueError):
        read_fixture(tmp_path, request)


def test_request_accepts_exact_descriptors_and_worker_measures_outputs(tmp_path):
    request = request_fixture(tmp_path)
    asset = tmp_path / "input" / "asset.blend"
    asset.write_bytes(b"asset")
    request["inputs"] = [input_descriptor(asset)]
    request["outputs"] = [
        {"id": "view", "path": "view.png", "media_type": "image/png", "max_bytes": 10}
    ]
    request = read_fixture(tmp_path, request)
    (tmp_path / "output" / "view.png").write_bytes(b"png")
    result = json.loads(write_result(request, [], {}).read_text())
    assert result["artifacts"] == [
        {
            "id": "view",
            "path": "view.png",
            "bytes": 3,
            "sha256": hashlib.sha256(b"png").hexdigest(),
        }
    ]


def test_runtime_paths_and_result_text_need_not_be_nfc(tmp_path):
    combined = "e\u0301"
    root = tmp_path / combined
    root.mkdir()
    request = read_fixture(root, request_fixture(root))
    result = json.loads(write_result(request, [], {"text": combined}).read_text())
    assert validate_result(result, request, ()) == result
    assert result["observations"] == {"text": combined}


def test_request_rejects_link_roots_and_overlapping_roots(tmp_path):
    request = request_fixture(tmp_path)
    linked_root = tmp_path / "linked-output"
    linked_root.symlink_to(tmp_path / "output", target_is_directory=True)
    request["output_root"] = str(linked_root)
    with pytest.raises(ValueError):
        read_fixture(tmp_path, request)

    (tmp_path / "second").mkdir()
    request = request_fixture(tmp_path / "second")
    child = tmp_path / "second" / "input" / "child"
    child.mkdir()
    request["output_root"] = str(child)
    with pytest.raises(ValueError, match="overlap"):
        read_fixture(tmp_path / "second", request)


def test_request_rejects_symlink_in_input_or_output_path(tmp_path):
    request = request_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "asset.blend").write_bytes(b"asset")
    (tmp_path / "input" / "linked").symlink_to(outside, target_is_directory=True)
    request["inputs"] = [
        input_descriptor(outside / "asset.blend", relative="linked/asset.blend")
    ]
    with pytest.raises(ValueError):
        read_fixture(tmp_path, request)

    request["inputs"] = []
    (tmp_path / "output" / "linked").symlink_to(outside, target_is_directory=True)
    request["outputs"] = [
        {"id": "view", "path": "linked/view.png", "media_type": "image/png", "max_bytes": 10}
    ]
    with pytest.raises(ValueError):
        read_fixture(tmp_path, request)


@pytest.mark.parametrize("number", [10**10000, 2**53 + 1], ids=("overflow", "inexact"))
def test_result_rejects_numbers_outside_canonical_domain_as_value_error(tmp_path, number):
    request = request_fixture(tmp_path)
    result = {key: request[key] for key in (
        "schema_version",
        "run_id",
        "attempt",
        "nonce",
        "job_id",
        "writer",
        "contract_digest",
        "source_digest",
    )}
    result.update(
        checks=[{"id": "r2.inventory.no_nan_inf", "findings": [], "metrics": {"bad": number}}],
        artifacts=[],
        observations={},
    )
    with pytest.raises(ValueError, match="finite scalars"):
        validate_result(result, request, ("r2.inventory.no_nan_inf",))


def test_assemble_plan_rejects_malformed_job_before_attribute_access(tmp_path):
    contract = write_contract(tmp_path, valid_document(tmp_path))
    with pytest.raises(AcceptanceFailure, match="jobs") as failure:
        assemble_plan(contract, [object()])
    assert failure.value.code == "contract_invalid"


@pytest.mark.parametrize(("name", "alias"), [("Input", "input"), ("é", "e\u0301")])
@pytest.mark.parametrize("relation", ["equal", "child", "parent"])
def test_request_rejects_physical_root_alias_overlap(tmp_path, name, alias, relation):
    request = request_fixture(tmp_path)
    root = tmp_path / name
    root.mkdir(exist_ok=True)
    other = tmp_path / alias
    if not other.exists() or not root.samefile(other):
        pytest.skip("test filesystem does not support this directory alias")
    child = other / "child"
    child.mkdir()
    left, right = (root, other) if relation == "equal" else (root, child)
    if relation == "parent":
        left, right = right, left
    request.update(input_root=str(left), output_root=str(right))
    with pytest.raises(ValueError, match="overlap"):
        read_fixture(tmp_path, request)
