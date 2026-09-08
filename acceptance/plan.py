from __future__ import annotations

from typing import Any, cast

from collections.abc import Mapping
from dataclasses import dataclass

from acceptance import check_registry as reg
from acceptance.canonical import CanonicalError, canonicalize
from acceptance.contract import Contract, freeze, require, thaw
from acceptance.input_bundle import relative_path, valid_id
from acceptance.primitives import AcceptanceFailure

_MEDIA = {
    "application/json",
    "image/png",
    "model/gltf-binary",
    "application/octet-stream",
    "text/plain",
}


def _strings(value: Any, name: str) -> tuple[str, ...]:
    require(type(value) in (list, tuple), f"{name} must be an ordered sequence")
    result = tuple(value)
    require(all(valid_id(item) for item in result), f"{name} must contain valid string ids")
    return cast(tuple[str, ...], result)


def _objects(value: Any, item_type: type[Any], name: str) -> tuple[Any, ...]:
    require(type(value) in (list, tuple), f"{name} must be an ordered sequence")
    result = tuple(value)
    require(all(type(item) is item_type for item in result), f"{name} has invalid elements")
    return result


@dataclass(frozen=True, slots=True)
class FileSpec:
    id: str
    path: str
    writer: str
    media_type: str
    max_bytes: int

    def __post_init__(self) -> None:
        require(valid_id(self.id), "invalid file id")
        relative_path(self.path)
        require(type(self.writer) is str and bool(self.writer), "invalid file writer")
        require(
            type(self.media_type) is str
            and self.media_type in _MEDIA
            and type(self.max_bytes) is int
            and self.max_bytes > 0,
            "invalid file type/budget",
        )


@dataclass(frozen=True, slots=True)
class JobSpec:
    job_id: str
    writer: str
    tool_id: str
    check_ids: tuple[str, ...]
    input_ids: tuple[str, ...]
    outputs: tuple[FileSpec, ...]
    parameters: Mapping[str, Any]
    blocking_check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require(
            valid_id(self.job_id) and type(self.writer) is str and bool(self.writer),
            "invalid job identity",
        )
        require(
            type(self.tool_id) is str and self.tool_id in {"python", "blender", "node"},
            "unsupported job tool",
        )
        object.__setattr__(self, "check_ids", _strings(self.check_ids, "check_ids"))
        object.__setattr__(self, "input_ids", _strings(self.input_ids, "input_ids"))
        object.__setattr__(
            self, "outputs", cast(tuple[FileSpec, ...], _objects(self.outputs, FileSpec, "outputs"))
        )
        object.__setattr__(
            self,
            "blocking_check_ids",
            _strings(self.blocking_check_ids, "blocking_check_ids"),
        )
        require(isinstance(self.parameters, Mapping), "parameters must be mapping")
        try:
            parameters = thaw(self.parameters)
            canonicalize(parameters)
            frozen_parameters = freeze(parameters)
        except (CanonicalError, TypeError, RecursionError) as exc:
            raise AcceptanceFailure("contract_invalid", f"parameters must be canonical JSON: {exc}") from exc
        object.__setattr__(self, "parameters", frozen_parameters)


@dataclass(frozen=True, slots=True)
class RunPlan:
    jobs: tuple[JobSpec, ...]
    files: tuple[FileSpec, ...]
    check_ids: tuple[str, ...]
    na_check_ids: tuple[str, ...]
    required_tools: tuple[str, ...]
    gate_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "jobs", cast(tuple[JobSpec, ...], _objects(self.jobs, JobSpec, "jobs"))
        )
        object.__setattr__(
            self, "files", cast(tuple[FileSpec, ...], _objects(self.files, FileSpec, "files"))
        )
        for name in ("check_ids", "na_check_ids", "required_tools", "gate_ids"):
            object.__setattr__(self, name, _strings(getattr(self, name), name))


def assemble_plan(
    contract: Contract, jobs: tuple[JobSpec, ...], *, gate_ids: tuple[str, ...] = ()
) -> RunPlan:
    require(type(contract) is Contract, "contract must be a frozen Contract")
    jobs = cast(tuple[JobSpec, ...], _objects(jobs, JobSpec, "jobs"))
    gate_ids = _strings(gate_ids, "gate_ids")
    specs = {spec.id: spec for spec in reg.checks_for_kind(contract.artifact_kind)}
    known_inputs = {row["id"] for row in contract.raw["input"]["files"]}
    claimed: set[str] = set()
    job_ids: set[str] = set()
    budget = contract.raw["budget"]
    require(len(set(gate_ids)) == len(gate_ids), "invalid gate set")
    files = [
        FileSpec(key, f"{key}.json", "coordinator", "application/json", budget["max_result_bytes"])
        for key in ("run", "gates")
    ]
    for job in jobs:
        require(job.job_id not in job_ids, "duplicate job")
        job_ids.add(job.job_id)
        require(job.writer != "coordinator", "subprocess cannot claim coordinator writer")
        require(
            job.writer in contract.raw["limits"]["timeout_seconds"],
            "missing writer wall timeout",
        )
        require(
            len(set(job.input_ids)) == len(job.input_ids) and set(job.input_ids) <= known_inputs,
            "input must come from frozen source or an earlier job",
        )
        require(set(job.blocking_check_ids) <= claimed, "blocking check must precede this job")
        for check_id in job.check_ids:
            require(
                check_id in specs
                and specs[check_id].writer == job.writer
                and check_id not in claimed,
                "unknown, duplicate or wrong-writer check",
            )
            claimed.add(check_id)
        for output in job.outputs:
            require(
                output.writer == job.writer and output.path != "result.json",
                "wrong writer or reserved result path",
            )
            require(output.id not in known_inputs, "output cannot overwrite source or earlier output")
            known_inputs.add(output.id)
            files.append(
                FileSpec(
                    output.id,
                    f"{job.job_id}/{output.path}",
                    output.writer,
                    output.media_type,
                    output.max_bytes,
                )
            )
        for suffix, name, owner, media, limit in (
            ("result", "result.json", job.writer, "application/json", budget["max_result_bytes"]),
            (
                "request",
                "request.json",
                "coordinator",
                "application/json",
                budget["max_result_bytes"],
            ),
            ("job", "job.json", "coordinator", "application/json", budget["max_result_bytes"]),
            (
                "log",
                "process.log",
                "coordinator",
                "text/plain",
                contract.raw["limits"]["log_bytes"],
            ),
        ):
            files.append(
                FileSpec(f"{job.job_id}.{suffix}", f"{job.job_id}/{name}", owner, media, limit)
            )
    require(
        len({spec.id for spec in files}) == len(files)
        and len({spec.path for spec in files}) == len(files),
        "duplicate planned file id/path",
    )
    require(len(files) <= budget["max_files"], "file plan exceeds count budget")
    require(
        set(contract.raw["review"]["required_image_ids"])
        <= {file.id for file in files if file.media_type == "image/png"},
        "required review image is not in file plan",
    )
    required = {"python", "acceptance", "blender"} | {job.tool_id for job in jobs}
    require(required <= {tool["id"] for tool in contract.raw["tools"]}, "missing planned tool")
    return RunPlan(
        jobs,
        tuple(files),
        tuple(specs),
        tuple(contract.na_check_ids),
        tuple(sorted(required)),
        gate_ids,
    )
