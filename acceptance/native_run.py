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
from acceptance.native_plan import NATIVE_GATES, build_native_plan, native_commands
from acceptance.native_results import native_results
from acceptance.primitives import AcceptanceFailure


def run_native(
    contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path
) -> dict[str, Any]:
    repository = Path(__file__).resolve().parents[1]
    contract = load_contract(contract_path, candidate_root=source_root)
    plan = build_native_plan(contract)
    inputs = verify_bundle(
        source_root,
        thaw(contract.raw["input"]["files"]),
        max_file_bytes=contract.raw["budget"]["max_file_bytes"],
    )
    blender = Path(next(tool["path"] for tool in contract.raw["tools"] if tool["id"] == "blender"))
    run = run_jobs(
        contract,
        plan,
        run_id=uuid4().hex,
        input_files=inputs,
        scratch_root=scratch_root,
        evidence_root=evidence_root,
        commands=native_commands(blender, repository),
    )
    try:
        findings, gates = native_results(contract, run)
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
        error = Finding("native_evidence_unverified", "error", detail=str(exc))
        findings = {}
        if "r4.visual.self_determinism" in run.findings:
            findings["r4.visual.self_determinism"] = [error]
        gates = {key: Gate(False, (error,)) for key in NATIVE_GATES}
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=contract_path,
        source_root=source_root,
        evidence_root=evidence_root,
        delivery=inputs[contract.raw["input"]["main"]],
        coordinator_findings=findings,
        gates=gates,
    )
