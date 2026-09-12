from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from acceptance.contract import load_contract, thaw
from acceptance.controller import run_jobs
from acceptance.decide import Finding, Gate
from acceptance.evidence import finalize_run
from acceptance.input_bundle import verify_bundle
from acceptance.interchange_plan import (
    GLB_GATES,
    build_interchange_plan,
    interchange_commands,
)
from acceptance.interchange_results import interchange_results
from acceptance.native_plan import NATIVE_GATES
from acceptance.primitives import AcceptanceFailure


def run_interchange(
    contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path
) -> dict[str, Any]:
    repository = Path(__file__).resolve().parents[1]
    contract = load_contract(contract_path, candidate_root=source_root)
    plan = build_interchange_plan(contract)
    inputs = verify_bundle(
        source_root,
        thaw(contract.raw["input"]["files"]),
        max_file_bytes=contract.raw["budget"]["max_file_bytes"],
    )
    tools = {x["id"]: Path(x["path"]) for x in contract.raw["tools"]}
    run = run_jobs(
        contract,
        plan,
        run_id=uuid4().hex,
        input_files=inputs,
        scratch_root=scratch_root,
        evidence_root=evidence_root,
        commands=interchange_commands(tools["blender"], tools["node"], tools["python"], repository),
    )
    try:
        (findings, gates) = interchange_results(contract, run)
    except (
        AcceptanceFailure,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OSError,
        StopIteration,
    ) as exc:
        code = exc.code if isinstance(exc, AcceptanceFailure) else "tool_output_invalid"
        run = replace(run, infra_failures=run.infra_failures + (code,))
        error = Finding("interchange_evidence_unverified", "error", detail=str(exc))
        findings = {}
        gates = {key: Gate(False, (error,)) for key in NATIVE_GATES + GLB_GATES}
    delivery = run.files.get("delivery.glb")
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=contract_path,
        source_root=source_root,
        evidence_root=evidence_root,
        delivery=delivery,
        coordinator_findings=findings,
        gates=gates,
    )
