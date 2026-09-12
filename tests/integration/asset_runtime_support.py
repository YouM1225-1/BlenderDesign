from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acceptance.input_bundle import freeze_bundle, source_digest
from acceptance.native_plan import native_commands
from acceptance.native_policy import PASSES, VIEWS
from acceptance.primitives import clean_environment
from tests.unit.asset_v2_support import file_lock, valid_document

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AssetCase:
    root: Path
    contract_path: Path
    source_root: Path
    evidence_root: Path
    scratch_root: Path
    document: dict[str, Any]


def selected_blender_version(blender: Path) -> str:
    completed = subprocess.run(
        (str(blender), "--version"),
        cwd=REPO,
        env=clean_environment(Path(sys.executable)),
        text=True,
        capture_output=True,
        timeout=10,
    )
    if completed.returncode:
        raise AssertionError(completed.stdout + "\n" + completed.stderr)
    lines = completed.stdout.splitlines()
    if not lines or not lines[0].strip():
        raise AssertionError("Blender version output is empty")
    return lines[0].strip()


def blender_script(
    blender: Path,
    script: Path,
    *arguments: str,
    environment_root: Path,
) -> None:
    environment_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = clean_environment(Path(sys.executable))
    for key, name in (
        ("BLENDER_USER_CONFIG", "config"),
        ("BLENDER_USER_SCRIPTS", "scripts"),
        ("BLENDER_USER_DATAFILES", "datafiles"),
        ("TMPDIR", "tmp"),
        ("TMP", "tmp"),
        ("TEMP", "tmp"),
    ):
        directory = environment_root / name
        directory.mkdir(mode=0o700, exist_ok=True)
        environment[key] = str(directory)
    completed = subprocess.run(
        (
            str(blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--offline-mode",
            "--python-exit-code",
            "1",
            "--python",
            str(script),
            "--",
            *arguments,
        ),
        cwd=REPO,
        env=environment,
        text=True,
        capture_output=True,
        timeout=900,
    )
    if completed.returncode:
        raise AssertionError(completed.stdout + "\n" + completed.stderr)


def prepare_calibration(blender: Path, root: Path, fixture_name: str = "good") -> Path:
    root.mkdir(parents=True)
    environment_root = root / "blender-user"
    blender_script(
        blender,
        REPO / "tests/fixtures/asset_native.py",
        str(root / "fixtures"),
        environment_root=environment_root,
    )
    if fixture_name != "good":
        shutil.copyfile(root / "fixtures" / f"{fixture_name}.blend", root / "fixtures/good.blend")
        shutil.copyfile(
            root / "fixtures" / f"{fixture_name}.json", root / "fixtures/reference.json"
        )
    for experiment in ("same_process", "fresh_a", "fresh_b", "compare"):
        blender_script(
            blender,
            REPO / "tests/fixtures/native_visual_probe.py",
            str(root),
            experiment,
            environment_root=environment_root,
        )
    return root


def prepare_native_case(
    blender: Path,
    tmp_path: Path,
    fixture_name: str,
    *,
    calibration_root: Path | None = None,
) -> AssetCase:
    tmp_path.mkdir(parents=True, exist_ok=True)
    if calibration_root is None:
        calibration_root = prepare_calibration(blender, tmp_path / "calibration")
    fixture_root = tmp_path / "policy-fixture"
    fixture_root.mkdir()
    document = valid_document(fixture_root)
    candidate = tmp_path / "candidate.blend"
    shutil.copyfile(calibration_root / "fixtures" / f"{fixture_name}.blend", candidate)
    authority = tmp_path / "reference-authority.json"
    authority.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "authority": "trusted-native-fixture-v1",
                "fixture_generator_sha256": hashlib.sha256(
                    (REPO / "tests/fixtures/asset_native.py").read_bytes()
                ).hexdigest(),
                "visual_generator_sha256": hashlib.sha256(
                    (REPO / "tests/fixtures/native_visual_probe.py").read_bytes()
                ).hexdigest(),
                "calibration_comparisons_sha256": hashlib.sha256(
                    (calibration_root / "comparisons.json").read_bytes()
                ).hexdigest(),
                "production_human_approval": False,
            },
            sort_keys=True,
        )
    )
    sources = [
        {"id": "asset", "path": "asset.blend", "source": str(candidate)},
        {
            "id": "native.reference",
            "path": "reference/manifest.json",
            "source": str(calibration_root / "fixtures/reference.json"),
        },
        {
            "id": "reference.authority",
            "path": "reference/authority.json",
            "source": str(authority),
        },
    ]
    for view in VIEWS:
        for render_pass in PASSES:
            sources.append(
                {
                    "id": f"reference.{view}.{render_pass}",
                    "path": f"reference/{view}-{render_pass}.png",
                    "source": str(
                        calibration_root / "same_process" / f"0-{view}-{render_pass}.png"
                    ),
                }
            )
    source_root = tmp_path / "bundle"
    rows = freeze_bundle(
        sources,
        source_root,
        max_files=1000,
        max_file_bytes=512 * 1024 * 1024,
        max_total_bytes=2 * 1024 * 1024 * 1024,
    )
    document["input"] = {"main": "asset", "sha256": source_digest(rows), "files": rows}
    report = json.loads((calibration_root / "same_process/render.json").read_text())
    document["native"] = {
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "support_profile": "native-static-v1",
        "reference_manifest_id": "native.reference",
        "reference_authority": "reference.authority",
        "geometry_limits": {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 1048576,
        },
        "render": {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
            "beauty_hard_gate": False,
            "platform": report["platform"],
            "max_abs": {render_pass: 0 for render_pass in PASSES},
            "reference_images": {
                view + "." + render_pass: f"reference.{view}.{render_pass}"
                for view in VIEWS
                for render_pass in PASSES
            },
        },
    }
    document["tools"] = [tool for tool in document["tools"] if tool["id"] != "blender"]
    document["tools"].append(
        {
            "id": "blender",
            "path": str(blender.resolve()),
            "version": selected_blender_version(blender),
            "sha256": file_lock(blender)["sha256"],
            "files": [
                file_lock(REPO / "acceptance/blender_scripts" / name)
                for name in ("native_worker.py", "native_collect.py", "native_render.py")
            ],
        }
    )
    document["limits"].update(
        {
            "timeout_seconds": {writer: 600 for writer in native_commands(blender, REPO)},
            "cpu_seconds": 1200,
            "rss_bytes": 6 * 1024**3,
            "open_files": 256,
            "log_bytes": 16 * 1024 * 1024,
            "file_size_bytes": 512 * 1024 * 1024,
        }
    )
    document["budget"] = {
        "max_files": 1000,
        "max_file_bytes": 512 * 1024 * 1024,
        "max_total_bytes": 2 * 1024**3,
        "max_result_bytes": 4 * 1024 * 1024,
    }
    document["review"] = {
        "required": True,
        "reviewer_ids": ["fixture-reviewer"],
        "required_image_ids": [
            "image.same_process.0.front.beauty",
            "image.same_process.0.bottom.clay",
        ],
        "reason": "Test-only known fixture review; never authorizes production artwork",
    }
    case = AssetCase(
        tmp_path,
        tmp_path / "contract.json",
        source_root,
        tmp_path / "evidence",
        tmp_path / "scratch",
        document,
    )
    candidate.write_bytes(b"origin replaced after freeze; not a Blender file")
    write_case(case)
    return case


def write_case(case: AssetCase) -> None:
    case.contract_path.write_text(
        json.dumps(case.document, ensure_ascii=False, sort_keys=True, allow_nan=False)
    )


def run_case(case: AssetCase) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        (
            sys.executable,
            str(REPO / "scripts/asset_accept.py"),
            "run",
            "--contract",
            str(case.contract_path),
            "--input-root",
            str(case.source_root),
            "--evidence-root",
            str(case.evidence_root),
            "--scratch-root",
            str(case.scratch_root),
        ),
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=900,
    )
    try:
        document = json.loads(completed.stdout)
    except ValueError as exc:
        raise AssertionError(completed.stdout + "\n" + completed.stderr) from exc
    return completed.returncode, document
