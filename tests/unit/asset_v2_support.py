from __future__ import annotations

import json
import sys
from pathlib import Path

from acceptance import check_registry as reg
from acceptance.canonical import digest
from acceptance.contract import load_contract
from acceptance.input_bundle import measure_file, source_digest

REPO = Path(__file__).resolve().parents[2]


def file_lock(path):
    measured = measure_file(path.resolve(), 2 * 1024**3, file_id="lock")
    return {"path": str(path.absolute()), "bytes": measured.bytes, "sha256": measured.sha256}


def trusted_code_files(repo_root):
    # Fixture owns its expected code lock before the production toolchain task exists.
    return tuple(
        sorted(
            list((repo_root / "acceptance").rglob("*.py"))
            + list((repo_root / "acceptance").rglob("*.json"))
            + [repo_root / "scripts/asset_accept.py", repo_root / "smoke/process_registry.py"]
        )
    )


def provenance(repo_root):
    rows = [
        {
            "path": p.relative_to(repo_root).as_posix(),
            "bytes": item["bytes"],
            "sha256": item["sha256"],
        }
        for p in trusted_code_files(repo_root)
        for item in (file_lock(p),)
    ]
    return {"version": "acc-v2-" + digest("code.v2", rows)}


def valid_document(tmp_path, kind="blend_native", *, asset_bytes=None):
    source_root = tmp_path / "source"
    source_root.mkdir(exist_ok=True)
    asset = source_root / "asset.blend"
    asset.write_bytes(
        b"fixture source bytes; this is not a Blender asset"
        if asset_bytes is None
        else asset_bytes
    )
    descriptor = measure_file(asset, 1024, file_id="asset").descriptor("asset.blend")
    fake_blender = tmp_path / "fixture-blender"
    fake_blender.write_text(f"#!{sys.executable}\nprint('Blender 5.2.0 LTS')\n")
    fake_blender.chmod(0o700)

    def tool(key, path, version, files):
        return {
            "id": key,
            "path": str(path),
            "version": version,
            "sha256": file_lock(path)["sha256"],
            "files": files,
        }

    return {
        "schema_version": 2,
        "contract_id": "fixture-001",
        "artifact_kind": kind,
        "profile": "static_render",
        "required_isolation_grade": "local-trusted",
        "input": {"main": "asset", "sha256": source_digest([descriptor]), "files": [descriptor]},
        "checks": [
            {"id": s.id, "impl": s.impl, "order": s.order}
            for s in sorted(reg.checks_for_kind(kind), key=reg.sort_key)
        ],
        "na_check_ids": list(reg.na_check_ids(kind)),
        "warning_allowlist": [],
        "tools": [
            tool("python", Path(sys.executable).resolve(), "Python 3.13.13", []),
            tool(
                "acceptance",
                REPO / "scripts/asset_accept.py",
                provenance(REPO)["version"],
                [file_lock(p) for p in trusted_code_files(REPO)],
            ),
            tool("blender", fake_blender, "Blender 5.2.0 LTS", []),
        ],
        "limits": {
            "timeout_seconds": {"inspector": 5, "reopen_probe": 5, "render_views(src)": 5},
            "cpu_seconds": 10,
            "rss_bytes": 2 * 1024**3,
            "open_files": 128,
            "log_bytes": 8192,
            "file_size_bytes": 1024 * 1024,
        },
        "budget": {
            "max_files": 1000,
            "max_file_bytes": 2 * 1024 * 1024,
            "max_total_bytes": 16 * 1024 * 1024,
            "max_result_bytes": 1024 * 1024,
        },
        "native": None,
        "interchange": None,
        "review": {
            "required": False,
            "reviewer_ids": [],
            "required_image_ids": [],
            "reason": "unit fixture only; not production asset approval",
        },
        "policy_baseline": None,
    }


def write_contract(tmp_path, value):
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return load_contract(path, candidate_root=tmp_path / "source")
