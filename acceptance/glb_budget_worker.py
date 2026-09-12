# ruff: noqa: E402 -- worker entrypoint establishes the trusted repository path.
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from acceptance.glb_budget import measure_glb
from acceptance.interchange_policy import validate_interchange_policy
from acceptance.worker_protocol import read_request, write_result


def main() -> Any:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    request = read_request(parser.parse_args().request)
    policy = request["parameters"]["policy"]
    validate_interchange_policy(policy)
    entry = next(x for x in request["inputs"] if x["id"] == "delivery.glb")
    value = measure_glb(Path(request["input_root"]) / entry["path"], policy["limits"])
    output = next(x for x in request["outputs"] if x["id"] == "glb.budget")
    target = Path(request["output_root"]) / output["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
    findings = [
        {
            "code": "budget_exceeded",
            "severity": "error",
            "pointer": None,
            "detail": name,
        }
        for name in value["exceeded"]
    ]
    write_result(
        request,
        [
            {
                "id": "r3.budget.within_limits",
                "findings": findings,
                "metrics": {
                    "stored_triangles": value["stored_triangles"],
                    "rendered_triangles": value["rendered_triangles"],
                    "draw_calls": value["draw_calls"],
                },
            }
        ],
        {"pid": str(os.getpid())},
    )


if __name__ == "__main__":
    main()
