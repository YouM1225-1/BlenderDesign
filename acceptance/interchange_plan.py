from pathlib import Path
from typing import Any

from acceptance.contract import thaw
from acceptance.primitives import AcceptanceFailure
from acceptance.interchange_policy import validate_interchange_policy
from acceptance.native_plan import NATIVE_GATES, UNSAFE_R2, native_commands, native_jobs
from acceptance.native_policy import PASSES, VIEWS
from acceptance.plan import FileSpec, JobSpec, assemble_plan

GLB_GATES = ("interchange.scope_supported", "interchange.consumer")


def build_interchange_plan(contract: Any) -> Any:
    if contract.artifact_kind != "interchange":
        raise ValueError("interchange contract required")
    policy = thaw(contract.raw["interchange"])
    validate_interchange_policy(policy)
    package = Path(policy["package_root"])
    required = {
        str(package / name)
        for name in (
            "package.json",
            "package-lock.json",
            "node_modules/gltf-validator/package.json",
            "node_modules/gltf-validator/index.js",
            "node_modules/gltf-validator/gltf_validator.dart.js",
        )
    }
    declared = {
        row["path"]
        for tool in contract.raw["tools"]
        if tool["id"] == "node"
        for row in tool["files"]
    }
    # Core toolchain measures these exact physical, no-link paths before running jobs.
    if not required <= declared:
        raise AcceptanceFailure(
            "toolchain_mismatch", "validator package members absent from Node lock"
        )
    native = thaw(contract.raw["native"])

    def output(fid: Any, writer: Any, extension: Any = "json") -> Any:
        return FileSpec(
            fid,
            ("images/" if extension == "png" else "data/") + fid + "." + extension,
            writer,
            "image/png"
            if extension == "png"
            else "model/gltf-binary"
            if extension == "glb"
            else "application/json",
            policy["limits"]["max_glb_bytes"] if extension == "glb" else 64 * 1024 * 1024,
        )

    def job(
        jid: Any,
        writer: Any,
        tool: Any,
        checks: Any,
        inputs: Any,
        outputs: Any,
        operation: Any,
    ) -> Any:
        return JobSpec(
            jid,
            writer,
            tool,
            tuple(checks),
            tuple(inputs),
            tuple(outputs),
            {"operation": operation, "policy": policy, "native": native},
            UNSAFE_R2,
        )

    jobs = list(native_jobs(contract, include_reopen=False))
    jobs.append(
        job(
            "glb.export",
            "export_glb",
            "blender",
            ["r3.export.file_nonempty", "r3.export.source_unchanged"],
            ["asset", "native.manifest"],
            [
                output("delivery.glb", "export_glb", "glb"),
                output("projection.source", "export_glb"),
                output("export.measurements", "export_glb"),
            ],
            "export",
        )
    )
    jobs.append(
        job(
            "glb.validator",
            "validator",
            "node",
            [],
            ["delivery.glb"],
            [
                output("validator.report", "validator"),
                output("validator.resources", "validator"),
            ],
            "validator",
        )
    )
    jobs.append(
        job(
            "glb.budget",
            "glb_budget",
            "python",
            ["r3.budget.within_limits"],
            ["delivery.glb"],
            [output("glb.budget", "glb_budget")],
            "budget",
        )
    )
    all_images: list[str] = []
    for experiment, writer, operation in [
        ("projection_source", "render_views(projection-source)", "source_render"),
        ("projection_import", "reimport_probe", "import"),
    ]:
        images = [
            output(f"image.{experiment}.0.{v}.{p}", writer, "png") for v in VIEWS for p in PASSES
        ]
        all_images.extend(x.id for x in images)
        outputs = images + [output("render." + experiment, writer)]
        if operation == "import":
            outputs.append(output("projection.import", writer))
        jobs.append(
            job(
                "glb." + experiment,
                writer,
                "blender",
                ["r4.import.manifest_written"] if operation == "import" else [],
                ["delivery.glb", "glb.budget", "validator.report", "validator.resources"]
                if operation == "import"
                else ["asset", "native.manifest", "projection.source"],
                outputs,
                operation,
            )
        )
    jobs.append(
        job(
            "glb.surface_compare",
            "projection_compare",
            "python",
            [],
            ["projection.source", "projection.import"],
            [output("projection.matches", "projection_compare")],
            "projection",
        )
    )
    jobs.append(
        job(
            "glb.visual_compare",
            "glb_compare",
            "blender",
            [],
            all_images,
            [output("projection.visual", "glb_compare")]
            + [
                output(f"diff.projection.{v}.{p}", "glb_compare", "png")
                for v in VIEWS
                for p in PASSES
            ],
            "compare",
        )
    )
    return assemble_plan(contract, tuple(jobs), gate_ids=NATIVE_GATES + GLB_GATES)


def interchange_commands(blender: Path, node: Path, python: Path, repository: Path) -> Any:
    result = native_commands(blender, repository)
    prefix = (
        str(blender),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--offline-mode",
        "--python-exit-code",
        "1",
        "--python",
        str(repository / "acceptance/blender_scripts/glb_worker.py"),
        "--",
    )
    result.update(
        {
            writer: prefix
            for writer in (
                "export_glb",
                "reimport_probe",
                "render_views(projection-source)",
                "glb_compare",
            )
        }
    )
    result["validator"] = (
        str(node),
        str(repository / "acceptance/node_scripts/validator_worker.mjs"),
    )
    result["glb_budget"] = (
        str(python),
        str(repository / "acceptance/glb_budget_worker.py"),
    )
    result["projection_compare"] = (
        str(python),
        str(repository / "acceptance/projection_worker.py"),
    )
    return result
