from __future__ import annotations

from typing import Any

import os
import secrets
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from acceptance import check_registry as reg, failure_codes as fc
from acceptance.contract import Contract, thaw, enforce_baseline
from acceptance.decide import Finding, Verdict, aggregate, decide
from acceptance.input_bundle import BoundFile, measure_file, read_bounded, validate_roots
from acceptance.plan import RunPlan
from acceptance.primitives import (
    AcceptanceFailure,
    clean_environment,
    run_command,
    write_json_exclusive,
)
from acceptance.strict_json import strict_json_loads
from acceptance.stages import run_r0, run_r1
from acceptance.toolchain import verify_tools
from acceptance.worker_protocol import IDENTITY, validate_result

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunResult:
    findings: dict[str, list[Finding]] = field(default_factory=dict)
    infra_failures: tuple[str, ...] = ()
    files: dict[str, BoundFile] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    jobs: tuple[dict[str, Any], ...] = ()
    measurements: dict[str, Any] = field(default_factory=dict)


def _family(exc: Exception) -> str:
    code = getattr(exc, "code", "")
    if code in fc.INFRA_FAMILIES:
        return code
    if isinstance(exc, FileNotFoundError):
        return "evidence_missing"
    return "tool_output_invalid"


def _copy(source: Path, target: Path, *, file_id: str, max_bytes: int) -> BoundFile:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return measure_file(source, max_bytes, file_id=file_id, copy_to=target)


def _files_under(root: Path) -> set[str]:
    def scan_error(exc: OSError) -> None:
        raise AcceptanceFailure(_family(exc), f"cannot enumerate output directory: {exc}") from exc

    names = set()
    for current, directories, files in os.walk(root, followlinks=False, onerror=scan_error):
        if any((Path(current) / d).is_symlink() for d in directories):
            raise AcceptanceFailure("tool_output_invalid", "symlink output directory")
        for name in files:
            names.add((Path(current) / name).relative_to(root).as_posix())
    return names


def run_jobs(
    contract: Contract,
    plan: RunPlan,
    *,
    run_id: str,
    input_files: Mapping[str, BoundFile],
    scratch_root: Path,
    evidence_root: Path,
    commands: Mapping[str, tuple[str, ...]],
) -> RunResult:
    roots = set()
    for row in contract.raw["input"]["files"]:
        if row["id"] in input_files:
            root = input_files[row["id"]].path.absolute()
            for _ in row["path"].split("/"):
                root = root.parent
            roots.add(root)
    if len(roots) != 1:
        raise AcceptanceFailure("contract_invalid", "input bindings do not share a source root")
    validate_roots(next(iter(roots)), evidence_root, scratch_root, REPO_ROOT)
    scratch_root.mkdir(mode=0o700)
    payload = evidence_root / "payload"
    payload.mkdir(mode=0o700)
    run = RunResult()
    failures = []
    records = []
    available = dict(input_files)
    expected_files = {s.id: s for s in plan.files}
    tools = {t["id"]: t for t in contract.raw["tools"]}
    try:
        run.measurements["tools"] = verify_tools(contract, plan.required_tools, REPO_ROOT)
        run.findings.update(run_r0(contract, tools_measured=run.measurements["tools"]))
        rows = contract.raw["input"]["files"]
        if set(available) != {r["id"] for r in rows}:
            raise AcceptanceFailure("expected_set_mismatch", "input binding set mismatch")
        for row in rows:
            source = available[row["id"]]
            measured = measure_file(
                source.path, contract.raw["budget"]["max_file_bytes"], file_id=source.id
            )
            if (measured.bytes, measured.sha256) != (row["bytes"], row["sha256"]):
                raise AcceptanceFailure("hash_mismatch", "input identity mismatch")
        run.findings.update(run_r1(contract, available))
        enforce_baseline(contract, available)
    except Exception as exc:
        failures.append(_family(exc))
        run.measurements["preflight_error"] = str(exc)
    for job in plan.jobs:
        record: dict[str, Any] = {
            "job_id": job.job_id,
            "writer": job.writer,
            "started": False,
            "pid": None,
            "started_at": None,
            "exit_code": None,
            "failure_code": None,
            "error": None,
            "blocked_by": [],
        }
        folder = scratch_root / job.job_id
        folder.mkdir(mode=0o700)
        inputs, outputs = folder / "input", folder / "output"
        inputs.mkdir(mode=0o700)
        outputs.mkdir(mode=0o700)
        request_path, log_path = folder / "request.json", folder / "process.log"
        try:
            blocked = [
                key
                for key in job.blocking_check_ids
                if key not in run.findings
                or any(f.severity in ("error", "warning") for f in run.findings[key])
            ]
            record["blocked_by"] = blocked
            if blocked and not failures:
                record["error"] = "not started: safety prerequisite was not satisfied"
                continue
            if failures or not set(job.input_ids) <= set(available):
                raise AcceptanceFailure(
                    "runner_internal_error", "job not started after failed prerequisite"
                )
            input_rows = []
            for file_id in job.input_ids:
                source = available[file_id]
                relative = file_id + source.path.suffix
                copied = _copy(
                    source.path, inputs / relative, file_id=file_id, max_bytes=source.bytes
                )
                if copied.sha256 != source.sha256 or copied.bytes != source.bytes:
                    raise AcceptanceFailure("hash_mismatch", "upstream input changed")
                input_rows.append(copied.descriptor(relative))
            request = {
                "schema_version": 2,
                "run_id": run_id,
                "attempt": 1,
                "nonce": secrets.token_hex(16),
                "job_id": job.job_id,
                "writer": job.writer,
                "contract_digest": contract.digest,
                "source_digest": contract.raw["input"]["sha256"],
                "input_root": str(inputs),
                "inputs": input_rows,
                "output_root": str(outputs),
                "outputs": [
                    {
                        "id": s.id,
                        "path": s.path,
                        "media_type": s.media_type,
                        "max_bytes": s.max_bytes,
                    }
                    for s in job.outputs
                ],
                "parameters": thaw(job.parameters),
            }
            write_json_exclusive(request_path, request)
            prefix = commands[job.writer]
            locked = next(t for t in run.measurements["tools"] if t["id"] == job.tool_id)
            if not prefix or str(Path(prefix[0]).resolve()) != locked["path"]:
                raise AcceptanceFailure("toolchain_mismatch", "command executable not locked")
            dependencies = {m["path"] for t in tools.values() for m in t["files"]}
            scripts = [p for p in prefix[1:] if p.endswith((".py", ".js", ".cjs", ".mjs"))]
            if any(not Path(p).is_absolute() or p not in dependencies for p in scripts):
                raise AcceptanceFailure(
                    "toolchain_mismatch", "command script outside locked closure"
                )
            env = clean_environment(Path(sys.executable))
            for key in ("BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS", "BLENDER_USER_DATAFILES"):
                directory = folder / key.lower()
                directory.mkdir(mode=0o700)
                env[key] = str(directory)
            rc = run_command(
                job.job_id,
                [locked["path"], *prefix[1:], "--request", str(request_path)],
                cwd=folder,
                env=env,
                log_path=log_path,
                timeout=contract.raw["limits"]["timeout_seconds"][job.writer],
                max_log_bytes=contract.raw["limits"]["log_bytes"],
                limits=thaw(contract.raw["limits"]),
                observation=record,
            )
            record["exit_code"] = rc
            if rc != 0:
                raise AcceptanceFailure("tool_crashed", f"worker exited {rc}")
            expected = {s.path for s in job.outputs} | {"result.json"}
            if _files_under(outputs) != expected:
                raise AcceptanceFailure("expected_set_mismatch", "worker output file set mismatch")
            result_spec = expected_files[f"{job.job_id}.result"]
            received = {
                result_spec.id: _copy(
                    outputs / "result.json",
                    payload / result_spec.path,
                    file_id=result_spec.id,
                    max_bytes=result_spec.max_bytes,
                )
            }
            result: Any = strict_json_loads(
                read_bounded(
                    received[result_spec.id].path, contract.raw["budget"]["max_result_bytes"]
                ).decode("utf-8")
            )
            if any(result.get(k) != request[k] for k in IDENTITY):
                raise AcceptanceFailure("stale_result_file", "result belongs to another attempt")
            validate_result(result, request, job.check_ids)
            reports = {r["id"]: r for r in result["artifacts"]}
            for spec in job.outputs:
                target = expected_files[spec.id]
                copied = _copy(
                    outputs / spec.path,
                    payload / target.path,
                    file_id=spec.id,
                    max_bytes=spec.max_bytes,
                )
                claimed = reports[spec.id]
                if (copied.bytes, copied.sha256) != (claimed["bytes"], claimed["sha256"]):
                    raise AcceptanceFailure(
                        "hash_mismatch", "child artifact hash was not measured honestly"
                    )
                received[spec.id] = copied
            run.files.update(received)
            available.update(received)
            for row in result["checks"]:
                run.findings[row["id"]] = [Finding(**finding) for finding in row["findings"]]
            run.results[job.job_id] = result
        except Exception as exc:
            record["failure_code"], record["error"] = _family(exc), str(exc)
            failures.append(record["failure_code"])
        finally:
            records.append(record)
            job_path = folder / "job.json"
            write_json_exclusive(job_path, record)
            for suffix, control_source in (
                ("job", job_path),
                ("request", request_path),
                ("log", log_path),
            ):
                if control_source.exists():
                    spec = expected_files[f"{job.job_id}.{suffix}"]
                    try:
                        run.files[spec.id] = _copy(
                            control_source,
                            payload / spec.path,
                            file_id=spec.id,
                            max_bytes=spec.max_bytes,
                        )
                    except Exception as exc:
                        failures.append(_family(exc))
    run.infra_failures = tuple(failures)
    run.jobs = tuple(records)
    document = {
        "schema_version": 2,
        "run_id": run_id,
        "C": contract.digest,
        "S": contract.raw["input"]["sha256"],
        "jobs": records,
        "measurements": run.measurements,
    }
    run_path = payload / "run.json"
    write_json_exclusive(run_path, document)
    run.files["run"] = measure_file(run_path, expected_files["run"].max_bytes, file_id="run")
    return run


def unproduced_files(plan: RunPlan, run: RunResult) -> dict[str, dict[str, Any]]:
    # Only controller-owned, deliberate safety blocks permit absent job products.
    blocked = {
        r["job_id"]: r
        for r in run.jobs
        if not r["started"] and r["blocked_by"] and r["failure_code"] is None
    }
    rows = {}
    for job in plan.jobs:
        if job.job_id not in blocked:
            continue
        ids = {s.id for s in job.outputs} | {
            f"{job.job_id}.{suffix}" for suffix in ("request", "log", "result")
        }
        for spec in plan.files:
            if spec.id in ids:
                rows[spec.id] = {
                    "id": spec.id,
                    "path": spec.path,
                    "job_id": job.job_id,
                    "blocked_by": blocked[job.job_id]["blocked_by"],
                }
    return rows


def collect_verdict(
    contract: Contract,
    plan: RunPlan,
    run: RunResult,
    *,
    coordinator_findings: Mapping[str, list[Finding]],
) -> Verdict:
    specs = {s.id: s for s in reg.CHECKS}
    collected = {key: list(value) for key, value in run.findings.items()}
    for check_id, findings in coordinator_findings.items():
        if check_id not in plan.check_ids:
            raise AcceptanceFailure("tool_output_invalid", "unknown or N/A coordinator check")
        if specs[check_id].writer != "coordinator" and check_id not in collected:
            raise AcceptanceFailure("tool_output_invalid", "cannot fabricate missing worker check")
        collected.setdefault(check_id, []).extend(findings)
    versions = {t["id"]: t["version"] for t in contract.raw["tools"]}
    owner = {check_id: job for job in plan.jobs for check_id in job.check_ids}
    outcomes = []
    for spec in reg.CHECKS:
        na = spec.id in plan.na_check_ids
        job = owner.get(spec.id)
        tool_id = None if na else (job.tool_id if job else "acceptance")
        outcomes.append(
            aggregate(
                spec.id,
                collected.get(spec.id, []),
                contract=contract,
                tool_id=tool_id,
                tool_version=None if na else versions[tool_id],
                source_truncated=False,
                terminal=None if na or spec.id in collected else "NotTested",
            )
        )
    return decide(
        contract=contract,
        outcomes=outcomes,
        actual_files=set(run.files),
        expected_files={s.id for s in plan.files} - set(unproduced_files(plan, run)),
        achieved_grade="local-trusted",
        infra_failures=list(run.infra_failures),
    )
