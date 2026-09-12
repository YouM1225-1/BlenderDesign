# ruff: noqa: E402 -- Establish trusted repository imports in subprocess entrypoint.
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
from acceptance.native_results import load
from acceptance.projection import compare_projection
from acceptance.worker_protocol import read_request, write_result


def main() -> Any:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    request = read_request(parser.parse_args().request)
    inputs = {x["id"]: Path(request["input_root"]) / x["path"] for x in request["inputs"]}
    value = compare_projection(
        load(inputs["projection.source"]),
        load(inputs["projection.import"]),
        request["parameters"]["policy"],
    )
    output = next(x for x in request["outputs"] if x["id"] == "projection.matches")
    target = Path(request["output_root"]) / output["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
    write_result(request, [], {"pid": str(os.getpid())})


if __name__ == "__main__":
    main()
