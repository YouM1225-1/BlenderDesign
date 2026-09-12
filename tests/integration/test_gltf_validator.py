import json
import os
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from acceptance import check_registry as reg, interchange_results as reducer
from acceptance.decide import Gate, aggregate, decide, decide_technical
from acceptance.glb_budget import measure_glb
from acceptance.input_bundle import measure_file
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document, write_contract
from tests.unit.interchange_support import policy

pytestmark = [
    pytest.mark.timeout(900),
    pytest.mark.skipif(
        os.environ.get("RUN_GLTF_VALIDATOR") != "1",
        reason="explicit real Node validator",
    ),
]
REPO = Path(__file__).resolve().parents[2]


def glb(path, document, binary=b""):
    raw = json.dumps(document).encode()
    raw += b" " * ((-len(raw)) % 4)
    body = struct.pack("<II", len(raw), 0x4E4F534A) + raw
    if binary:
        binary += b"\0" * ((-len(binary)) % 4)
        body += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)


def triangle():
    return {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [1, 1, 0],
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962}
        ],
        "buffers": [{"byteLength": 36}],
    }


def run_validator(root, document, binary, *, max_nodes=100):
    source = root / "input"
    source.mkdir(parents=True)
    output = root / "output"
    output.mkdir()
    asset = source / "asset.glb"
    glb(asset, document, binary)
    configured = policy(Path(os.environ["GLTF_PACKAGE_ROOT"]))
    configured["limits"]["max_nodes"] = max_nodes
    row = measure_file(asset, configured["limits"]["max_glb_bytes"], file_id="delivery.glb")
    request = {
        "schema_version": 2,
        "run_id": "fixture",
        "attempt": 1,
        "nonce": "a" * 32,
        "job_id": "glb.validator",
        "writer": "validator",
        "contract_digest": "c" * 64,
        "source_digest": "d" * 64,
        "input_root": str(source),
        "output_root": str(output),
        "inputs": [row.descriptor("asset.glb")],
        "outputs": [
            {
                "id": file_id,
                "path": name,
                "media_type": "application/json",
                "max_bytes": 64 * 1024 * 1024,
            }
            for file_id, name in (
                ("validator.report", "report.json"),
                ("validator.resources", "resources.json"),
            )
        ],
        "parameters": {"operation": "validator", "policy": configured, "native": {}},
    }
    request_path = root / "request.json"
    request_path.write_text(json.dumps(request))
    completed = subprocess.run(
        [
            os.environ["NODE_BIN"],
            str(REPO / "acceptance/node_scripts/validator_worker.mjs"),
            "--request",
            str(request_path),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return asset, output, configured


def issue_rows(report, code):
    return [row for row in report["issues"]["messages"] if row["code"] == code]


def controller_result(asset, output, configured, monkeypatch):
    budget_path = output / "budget.json"
    budget_path.write_text(json.dumps(measure_glb(asset, configured["limits"])))
    files = {
        file_id: measure_file(path, 64 * 1024 * 1024, file_id=file_id)
        for file_id, path in (
            ("delivery.glb", asset),
            ("validator.report", output / "report.json"),
            ("validator.resources", output / "resources.json"),
            ("glb.budget", budget_path),
        )
    }
    monkeypatch.setattr(reducer, "native_results", lambda contract, run: ({}, {}))
    return reducer.interchange_results(
        SimpleNamespace(raw={"interchange": configured}), SimpleNamespace(files=files)
    )


def test_real_validator_consumes_embedded_bytes_and_controller_rechecks(tmp_path, monkeypatch):
    valid_binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    valid_asset, valid_output, valid_policy = run_validator(
        tmp_path / "valid", triangle(), valid_binary
    )
    report = json.loads((valid_output / "report.json").read_text())
    assert report["issues"]["numErrors"] == 0
    assert report["issues"]["truncated"] is False
    findings, _ = controller_result(valid_asset, valid_output, valid_policy, monkeypatch)
    assert not findings["r3.validator.no_error"]
    assert not findings["r3.validator.report_complete"]
    assert not findings["r3.validator.resources_read"]

    short_asset, short_output, short_policy = run_validator(
        tmp_path / "short", triangle(), b"\0" * 32
    )
    report = json.loads((short_output / "report.json").read_text())
    rows = issue_rows(report, "BUFFER_BYTE_LENGTH_MISMATCH")
    assert rows and {row.get("pointer") for row in rows} == {"/buffers/0"}
    findings, _ = controller_result(short_asset, short_output, short_policy, monkeypatch)
    assert {
        finding.code for finding in findings["r3.validator.no_error"]
    } == {"validator_BUFFER_BYTE_LENGTH_MISMATCH"}

    _, omitted_output, _ = run_validator(tmp_path / "omitted", triangle(), b"")
    omitted = json.loads((omitted_output / "report.json").read_text())
    rows = issue_rows(omitted, "BUFFER_MISSING_GLB_DATA")
    assert rows and {row.get("pointer") for row in rows} == {"/buffers/0"}

    resources_path = valid_output / "resources.json"
    original_resources = resources_path.read_bytes()
    try:
        resources = json.loads(original_resources)
        resources["resources"] = []
        tampered_resources = json.dumps(resources).encode()
        (valid_output.parent / "tampered-resources.json").write_bytes(tampered_resources)
        resources_path.write_bytes(tampered_resources)
        with pytest.raises(AcceptanceFailure, match="resource log differs") as caught:
            controller_result(valid_asset, valid_output, valid_policy, monkeypatch)
        assert caught.value.code == "tool_output_invalid"
    finally:
        resources_path.write_bytes(original_resources)
    wrapper_result = json.loads((valid_output / "result.json").read_text())
    declared = next(
        row for row in wrapper_result["artifacts"] if row["id"] == "validator.resources"
    )
    retained = measure_file(resources_path, 64 * 1024 * 1024, file_id="validator.resources")
    assert (retained.bytes, retained.sha256) == (declared["bytes"], declared["sha256"])


def test_real_validator_reports_external_read_failure(tmp_path):
    document = triangle()
    document["buffers"][0]["uri"] = "missing.bin"
    asset, output, configured = run_validator(tmp_path / "external", document, b"")
    report = json.loads((output / "report.json").read_text())
    resources = json.loads((output / "resources.json").read_text())
    rows = issue_rows(report, "IO_ERROR")
    assert rows and {row.get("pointer") for row in rows} == {"/buffers/0/uri"}
    assert resources["external_requests"] == ["missing.bin"]
    with pytest.raises(ValueError, match="URI"):
        measure_glb(asset, configured["limits"])


def test_real_validator_truncation_blocks_controller_completion(tmp_path, monkeypatch):
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": []}],
        "nodes": [{"mesh": 9} for _ in range(12000)],
    }
    asset, output, configured = run_validator(
        tmp_path / "truncated", document, b"", max_nodes=12000
    )
    report = json.loads((output / "report.json").read_text())
    assert report["issues"]["truncated"] is True
    assert report["issues"]["numErrors"] == 10000
    rows = issue_rows(report, "UNRESOLVED_REFERENCE")
    assert rows and all(row.get("pointer", "").startswith("/nodes/") for row in rows)
    assert all(row["pointer"].endswith("/mesh") for row in rows)
    findings, _ = controller_result(asset, output, configured, monkeypatch)
    assert any(
        finding.code == "validator_UNRESOLVED_REFERENCE"
        for finding in findings["r3.validator.no_error"]
    )
    assert {
        finding.code for finding in findings["r3.validator.report_complete"]
    } == {"validator_truncated"}

    # Test-only adjudication seam: the real reducer finding is isolated inside an otherwise
    # complete CLI-shaped baseline. This is not a full CLI or real-world acceptance result.
    adjudication_root = tmp_path / "adjudication-fixture"
    adjudication_root.mkdir()
    contract = write_contract(
        adjudication_root,
        valid_document(adjudication_root, kind="interchange"),
    )
    assert len(contract.raw["checks"]) == 34
    assert set(contract.na_check_ids) == {
        "r4.reopen.dependencies_resolved",
        "r4.reopen.manifest_matches_source",
        "r4.reopen.offline_ok",
    }
    acceptance_version = next(
        tool["version"] for tool in contract.raw["tools"] if tool["id"] == "acceptance"
    )
    outcomes = [
        aggregate(
            spec.id,
            list(findings["r3.validator.report_complete"])
            if spec.id == "r3.validator.report_complete"
            else [],
            contract=contract,
            tool_id=None if spec.id in contract.na_check_ids else "acceptance",
            tool_version=None if spec.id in contract.na_check_ids else acceptance_version,
            source_truncated=False,
            terminal=None,
        )
        for spec in reg.CHECKS
    ]
    base = decide(
        contract=contract,
        outcomes=outcomes,
        actual_files={"test-seam"},
        expected_files={"test-seam"},
        achieved_grade="local-trusted",
        infra_failures=[],
    )
    expected_gate_ids = (
        "native.scope_supported",
        "native.cross_process",
        "native.reference",
        "interchange.scope_supported",
        "interchange.consumer",
    )
    gates = {gate_id: Gate(True) for gate_id in expected_gate_ids}
    verdict = decide_technical(base, expected_gate_ids=expected_gate_ids, gates=gates)
    assert sum(outcome.raw_status != "NotApplicableByContract" for outcome in outcomes) == 34
    assert sum(outcome.raw_status == "NotApplicableByContract" for outcome in outcomes) == 3
    assert len(gates) == 5 and all(gate.complete and not gate.findings for gate in gates.values())
    assert verdict.success is False
    assert verdict.failure_code == "check_failed"
    assert verdict.failed_check_ids == ("r3.validator.report_complete",)
    assert verdict.failed_gate_ids == ()
