from __future__ import annotations
from pathlib import Path
from acceptance.check_registry import CHECKS
from acceptance.contract import Contract, thaw
from acceptance.plan import FileSpec, JobSpec, RunPlan, assemble_plan
from acceptance.native_policy import validate_native_policy, VIEWS, PASSES

NATIVE_GATES = ("native.scope_supported", "native.cross_process", "native.reference")
UNSAFE_R2 = (
    "r2.inventory.coverage_complete",
    "r2.inventory.no_nan_inf",
    "r2.geometry.validate_clean",
    "r2.geometry.manifest_written",
    "r2.source.digest_stable",
)


def native_jobs(contract: Contract, *, include_reopen: bool = True) -> tuple[JobSpec, ...]:
    policy = thaw(contract.raw["native"])
    validate_native_policy(policy)

    def output(fid: str, writer: str, image: bool = False) -> FileSpec:
        return FileSpec(
            fid,
            ("images/" if image else "data/") + fid + (".png" if image else ".json"),
            writer,
            "image/png" if image else "application/json",
            16 * 1024 * 1024 if image else 64 * 1024 * 1024,
        )

    def job(
        job_id: str,
        writer: str,
        operation: str,
        inputs: tuple[str, ...],
        outputs: tuple[FileSpec, ...],
        experiment: str = "none",
    ) -> JobSpec:
        return JobSpec(
            job_id,
            writer,
            "blender",
            tuple(c.id for c in CHECKS if c.writer == writer),
            inputs,
            outputs,
            {"operation": operation, "policy": policy, "experiment": experiment},
            () if operation == "inspect" else UNSAFE_R2,
        )

    jobs = [
        job(
            "native.inspect",
            "inspector",
            "inspect",
            ("asset",),
            (output("native.manifest", "inspector"), output("native.dependencies", "inspector")),
        )
    ]
    if include_reopen:
        jobs.append(
            job(
                "native.reopen",
                "reopen_probe",
                "reopen",
                ("asset", "native.manifest"),
                (
                    output("native.reopened", "reopen_probe"),
                    output("native.reopen_dependencies", "reopen_probe"),
                ),
            )
        )
    image_ids: list[str] = []
    for experiment, writer in (
        ("same_process", "render_views(src)"),
        ("fresh_a", "render_views(src-fresh-a)"),
        ("fresh_b", "render_views(src-fresh-b)"),
    ):
        images = tuple(
            output(f"image.{experiment}.{r}.{view}.{render_pass}", writer, True)
            for r in range(2 if experiment == "same_process" else 1)
            for view in VIEWS
            for render_pass in PASSES
            if not (r == 1 and render_pass == "beauty")
        )
        image_ids.extend(x.id for x in images)
        jobs.append(
            job(
                "native.render." + experiment,
                writer,
                "render",
                ("asset", "native.manifest"),
                images + (output("render." + experiment, writer),),
                experiment,
            )
        )
    diffs = tuple(
        output(f"diff.{group}.{view}.{render_pass}", "native_compare", True)
        for group in ("same", "fresh", "reference")
        for view in VIEWS
        for render_pass in PASSES
        if not (group == "same" and render_pass == "beauty")
    )
    comparison_inputs = (
        tuple(image_ids)
        + ("native.manifest", policy["reference_manifest_id"])
        + tuple(policy["render"]["reference_images"][v + "." + p] for v in VIEWS for p in PASSES)
    )
    jobs.append(
        job(
            "native.compare",
            "native_compare",
            "compare",
            comparison_inputs,
            diffs + (output("native.comparisons", "native_compare"),),
        )
    )
    return tuple(jobs)


def build_native_plan(contract: Contract) -> RunPlan:
    if contract.artifact_kind != "blend_native":
        raise ValueError("native entrypoint requires blend_native")
    return assemble_plan(contract, native_jobs(contract), gate_ids=NATIVE_GATES)


def native_commands(blender: Path, repository: Path) -> dict[str, tuple[str, ...]]:
    prefix = (
        str(blender),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--offline-mode",
        "--python-exit-code",
        "1",
        "--python",
        str(repository / "acceptance/blender_scripts/native_worker.py"),
        "--",
    )
    return {
        writer: prefix
        for writer in (
            "inspector",
            "reopen_probe",
            "render_views(src)",
            "render_views(src-fresh-a)",
            "render_views(src-fresh-b)",
            "native_compare",
        )
    }
