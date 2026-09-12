#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from acceptance.contract import load_contract, thaw  # noqa: E402
from acceptance.controller import run_jobs  # noqa: E402
from acceptance.evidence import _write, deliver, finalize_run, finish_review  # noqa: E402
from acceptance.input_bundle import (  # noqa: E402
    freeze_bundle,
    read_bounded,
    source_digest,
    validate_roots,
    verify_bundle,
)
from acceptance.plan import assemble_plan  # noqa: E402
from acceptance.primitives import (  # noqa: E402
    AcceptanceFailure,
    create_private_directory,
    normalise_new_root,
    path_is_within,
)
from acceptance.strict_json import strict_json_loads  # noqa: E402


def dispatch_run(
    contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path
) -> dict[str, Any]:
    contract = load_contract(contract_path, candidate_root=source_root)
    if contract.artifact_kind == "interchange" and contract.raw["interchange"] is not None:
        from acceptance.interchange_run import run_interchange

        return run_interchange(contract_path, source_root, evidence_root, scratch_root)
    if contract.artifact_kind == "blend_native" and contract.raw["native"] is not None:
        from acceptance.native_run import run_native

        return run_native(contract_path, source_root, evidence_root, scratch_root)
    # M3 inserts its kind-specific adapter here; M1 never accepts worker commands from CLI JSON.
    plan = assemble_plan(contract, ())
    inputs = verify_bundle(
        source_root,
        thaw(contract.raw["input"]["files"]),
        max_file_bytes=contract.raw["budget"]["max_file_bytes"],
    )
    run = run_jobs(
        contract,
        plan,
        run_id=evidence_root.name,
        input_files=inputs,
        scratch_root=scratch_root,
        evidence_root=evidence_root,
        commands={},
    )
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=contract_path,
        source_root=source_root,
        evidence_root=evidence_root,
        delivery=inputs[contract.raw["input"]["main"]],
        coordinator_findings={},
        gates={},
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="v2 asset acceptance; v1 requires a new contract")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    for flag in ("sources", "bundle-root", "manifest"):
        freeze.add_argument("--" + flag, required=True, type=Path)
    freeze.add_argument("--max-files", type=int, default=1024)
    freeze.add_argument("--max-file-bytes", type=int, default=536870912)
    freeze.add_argument("--max-total-bytes", type=int, default=1073741824)
    run = commands.add_parser("run")
    for flag in ("contract", "input-root", "evidence-root", "scratch-root"):
        run.add_argument("--" + flag, required=True, type=Path)
    review = commands.add_parser("review")
    for flag in ("evidence-root", "delivery", "review"):
        review.add_argument("--" + flag, required=True, type=Path)
    delivery = commands.add_parser("deliver")
    for flag in ("evidence-root", "delivery", "destination"):
        delivery.add_argument("--" + flag, required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = None
    root_created = False
    try:
        if args.command == "freeze":
            source_rows = strict_json_loads(read_bounded(args.sources, 1048576).decode("utf-8"))
            bundle_root = args.bundle_root.absolute()
            manifest = args.manifest.absolute()
            if manifest == bundle_root or bundle_root in manifest.parents:
                raise AcceptanceFailure(
                    "contract_invalid", "source manifest must be outside frozen files"
                )
            if not isinstance(source_rows, list):
                raise AcceptanceFailure("contract_invalid", "freeze sources must be a list")
            rows = freeze_bundle(
                cast(list[dict[str, Any]], source_rows),
                bundle_root,
                max_files=args.max_files,
                max_file_bytes=args.max_file_bytes,
                max_total_bytes=args.max_total_bytes,
            )
            if path_is_within(manifest, bundle_root):
                raise AcceptanceFailure(
                    "contract_invalid", "source manifest must be outside frozen files"
                )
            result = {"schema_version": 2, "files": rows, "sha256": source_digest(rows)}
            _write(manifest, result)
        elif args.command == "run":
            root = normalise_new_root(args.evidence_root, ROOT)
            scratch = normalise_new_root(args.scratch_root, ROOT)
            validate_roots(args.input_root.absolute(), root, scratch, ROOT)
            create_private_directory(root)
            root_created = True
            result = dispatch_run(
                args.contract.absolute(), args.input_root.absolute(), root, scratch
            )
        elif args.command == "review":
            review = strict_json_loads(read_bounded(args.review, 1048576).decode("utf-8"))
            if not isinstance(review, dict):
                raise AcceptanceFailure("tool_output_invalid", "review must be an object")
            result = finish_review(
                args.evidence_root.absolute(), delivery_path=args.delivery.absolute(), review=review
            )
        else:
            result = deliver(
                args.evidence_root.absolute(),
                delivery_path=args.delivery.absolute(),
                destination=args.destination.absolute(),
            )
    except Exception as exc:
        code = getattr(exc, "code", "runner_internal_error")
        result = {
            "schema_version": 2,
            "state": "UNVERIFIED",
            "failure_code": code,
            "error": str(exc),
        }
        if root_created and root is not None and not (root / "summary.json").exists():
            try:
                _write(
                    root / "summary.json",
                    {
                        "schema_version": 2,
                        "kind": "asset_acceptance",
                        "success": False,
                        "failure_code": code,
                        "error": str(exc),
                        "checks": [],
                        "gates": {},
                        "failed_check_ids": [],
                        "failed_gate_ids": [],
                    },
                )
            except Exception as summary_exc:
                result["error"] = (
                    f"{result['error']}; failure summary write failed: {summary_exc}"
                )
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    if args.command in ("run", "review"):
        return 0 if result["state"] in ("SHIP", "SHIP_WITH_NOTES") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
