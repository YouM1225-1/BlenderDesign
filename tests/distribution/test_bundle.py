from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer.bundle import (  # noqa: E402
    ARTIFACTS,
    TOOLS,
    open_verified_bundle,
    parse_manifest,
    validate_runtime_lock,
    verify_distribution_checkout,
)
from scripts.build_official_blender_mcp_distribution import (  # noqa: E402
    build_distribution,
)


COMMIT = "482c540395ad93a2f86b1ada1520f4fddf8ebcfa"


def manifest() -> dict[str, object]:
    artifacts = [
        {"role": role, "filename": filename, "size": 1, "sha256": "a" * 64}
        for role, filename in ARTIFACTS
    ]
    return {
        "schema_version": 2,
        "bundle_version": "1.0.0+482c540395ad",
        "platform": {"system": "Darwin", "machine": "arm64"},
        "upstream": {
            "url": "https://projects.blender.org/lab/blender_mcp.git",
            "commit": COMMIT,
        },
        "python": {"runtime_minor": "3.13", "build_tested": "3.13.13"},
        "blender": {
            "minimum": "5.2.0",
            "maximum_exclusive": "5.3.0",
            "tested": "5.2.0",
        },
        "server": {"distribution": "blender-mcp", "version": "1.0.0", "mcp_sdk": "1.28.1"},
        "extension": {"repository": "user_default", "id": "mcp", "version": "1.0.0"},
        "bridge": {"host": "localhost", "port": 9876},
        "build": {
            "source_date_epoch": 1,
            "uv": "0.12.2",
            "python": "3.13.13",
            "blender": "5.2.0",
            "codex_tested": "0.148.0-alpha.9",
            "backend": {"name": "setuptools", "version": "80.9.0"},
            "index": "https://pypi.org/simple",
        },
        "tools": list(TOOLS),
        "artifacts": artifacts,
    }


def raw(value: dict[str, object]) -> bytes:
    return json.dumps(value).encode()


@pytest.mark.parametrize("where,key", [(None, "extra"), (None, "tools"), ("server", "extra")])
def test_manifest_rejects_unknown_or_missing_keys(where: str | None, key: str) -> None:
    value = manifest()
    target = value if where is None else value[where]
    assert isinstance(target, dict)
    if key == "tools":
        target.pop(key)
    else:
        target[key] = "x"
    with pytest.raises(ValueError):
        parse_manifest(raw(value))


@pytest.mark.parametrize("size,digest", [(True, "a" * 64), (1, "A" * 64), (1, "a" * 63)])
def test_manifest_rejects_bool_sizes_and_bad_hashes(size: object, digest: str) -> None:
    value = manifest()
    value["artifacts"][0]["size"] = size
    value["artifacts"][0]["sha256"] = digest
    with pytest.raises(ValueError):
        parse_manifest(raw(value))


@pytest.mark.parametrize(
    "field,value",
    [("filename", "../wheel.whl"), ("filename", "sub/wheel.whl"), ("role", "other")],
)
def test_manifest_rejects_bad_names_roles_and_traversal(field: str, value: str) -> None:
    data = manifest()
    data["artifacts"][0][field] = value
    with pytest.raises(ValueError):
        parse_manifest(raw(data))


@pytest.mark.parametrize("mutation", ["version", "catalog", "order"])
def test_manifest_requires_fixed_versions_and_catalog(mutation: str) -> None:
    data = manifest()
    if mutation == "version":
        data["server"]["version"] = "2.0.0"
    elif mutation == "catalog":
        data["tools"] = data["tools"][:-1]
    else:
        data["artifacts"].reverse()
    with pytest.raises(ValueError):
        parse_manifest(raw(data))


def _git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True, text=True)


def _checkout(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "checkout"
    bundle = root / "plugins/blender-mcp-installer/artifacts"
    bundle.mkdir(parents=True)
    payloads = {
        "blender_mcp-1.0.0-py3-none-any.whl": b"w",
        "mcp-1.0.0.zip": b"z",
        "runtime-requirements.lock": b"tomlkit==0.13.3 --hash=sha256:" + b"b" * 64 + b"\n",
    }
    data = manifest()
    for item in data["artifacts"]:
        content = payloads[item["filename"]]
        item["size"] = len(content)
        item["sha256"] = hashlib.sha256(content).hexdigest()
        (bundle / item["filename"]).write_bytes(content)
    manifest_raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    (bundle / "manifest.json").write_bytes(manifest_raw)
    sums = [
        f"{hashlib.sha256((bundle / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ["manifest.json", *payloads]
    ]
    (bundle / "SHA256SUMS").write_text("".join(sums))
    _git(["git", "init", "-q"], root)
    _git(["git", "config", "user.name", "Test"], root)
    _git(["git", "config", "user.email", "test@example.invalid"], root)
    _git(["git", "add", "."], root)
    _git(["git", "commit", "-qm", "fixture"], root)
    commit = _git(["git", "rev-parse", "HEAD"], root).stdout.strip()
    _git(["git", "checkout", "-q", "--detach", commit], root)
    return bundle, commit


@pytest.mark.parametrize("failure", ["attached", "wrong_commit", "tracked"])
def test_checkout_requires_detached_exact_clean_commit(tmp_path: Path, failure: str) -> None:
    bundle, commit = _checkout(tmp_path)
    if failure == "attached":
        _git(["git", "switch", "-qc", "attached"], bundle.parents[2])
    elif failure == "tracked":
        (bundle / "manifest.json").write_bytes(b"{}")
    expected = "0" * 40 if failure == "wrong_commit" else commit
    with pytest.raises(ValueError):
        verify_distribution_checkout(bundle, expected, _git)


def test_checkout_rejects_scoped_untracked_file(tmp_path: Path) -> None:
    bundle, commit = _checkout(tmp_path)
    (bundle.parent / "unexpected").write_text("x")
    with pytest.raises(ValueError):
        verify_distribution_checkout(bundle, commit, _git)


def test_checkout_ignores_redirected_git_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle, commit = _checkout(tmp_path)
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    monkeypatch.setenv("GIT_DIR", str(hostile))
    assert verify_distribution_checkout(bundle, commit, _git).expected_commit == commit


@pytest.mark.parametrize("target", ["SHA256SUMS", "blender_mcp-1.0.0-py3-none-any.whl"])
def test_payload_and_working_checksum_tamper_fails_against_commit_bytes(tmp_path: Path, target: str) -> None:
    bundle, commit = _checkout(tmp_path)
    (bundle / target).write_bytes(b"tamper")
    with pytest.raises(ValueError):
        verify_distribution_checkout(bundle, commit, _git)


def test_bundle_hashes_same_opened_files(tmp_path: Path) -> None:
    bundle, commit = _checkout(tmp_path)
    checkout = verify_distribution_checkout(bundle, commit, _git)
    with open_verified_bundle(checkout) as verified:
        assert verified.manifest.upstream["commit"] == COMMIT


@pytest.mark.parametrize("target", [name for _, name in ARTIFACTS])
def test_replace_wheel_zip_or_lock_after_verify_cannot_change_staged_copy(
    tmp_path: Path, target: str
) -> None:
    bundle, commit = _checkout(tmp_path)
    expected = (bundle / target).read_bytes()
    with open_verified_bundle(verify_distribution_checkout(bundle, commit, _git)) as verified:
        replacement = bundle / f"{target}.replacement"
        replacement.write_bytes(b"replacement")
        os.replace(replacement, bundle / target)
        staged = verified.materialize(tmp_path / "private-stage")
    assert (staged.root / target).read_bytes() == expected


@pytest.mark.parametrize(
    "lock",
    [
        "demo>=1 --hash=sha256:" + "a" * 64,
        "demo==1",
        "-r other.lock",
        "demo @ https://example.invalid/demo.whl --hash=sha256:" + "a" * 64,
        "-e ./demo --hash=sha256:" + "a" * 64,
        "./demo==1 --hash=sha256:" + "a" * 64,
    ],
)
def test_runtime_lock_is_fully_pinned_and_hashed(lock: str) -> None:
    with pytest.raises(ValueError):
        validate_runtime_lock(lock.encode())


def test_builder_uses_two_fresh_git_archives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fail_after_archives(*args: object, **kwargs: object) -> None:
        calls.append(list(args[0]))
        if sum(command[:2] == ["git", "archive"] for command in calls) == 2:
            raise RuntimeError("stop")

    monkeypatch.setattr(subprocess, "run", fail_after_archives)
    with pytest.raises(RuntimeError, match="stop"):
        build_distribution(tmp_path, Path("blender"), Path("uv"), tmp_path / "out")
    assert sum(command[:2] == ["git", "archive"] for command in calls) == 2


def test_builder_sanitizes_probe_environment() -> None:
    from scripts.build_official_blender_mcp_distribution import sanitized_environment

    env = sanitized_environment(
        {"BLENDER_MCP_HOST": "evil", "UV_INDEX_URL": "evil", "PIP_INDEX_URL": "evil"}
    )
    assert env["BLENDER_MCP_HOST"] == "localhost"
    assert env["BLENDER_MCP_PORT"] == "9876"
    assert env["UV_DEFAULT_INDEX"] == "https://pypi.org/simple"
    assert "UV_INDEX_URL" not in env and "PIP_INDEX_URL" not in env


def test_normalized_extension_is_revalidated() -> None:
    from scripts.build_official_blender_mcp_distribution import validate_extension_command

    assert validate_extension_command(Path("blender"), Path("normalized.zip"))[-1] == "normalized.zip"


def test_publish_keeps_last_good_output_on_gate_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "artifacts"
    output.mkdir()
    (output / "marker").write_text("last-good")

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("gate")

    monkeypatch.setattr(
        "scripts.build_official_blender_mcp_distribution._extract_two_archives",
        lambda source, workspace: (tmp_path, tmp_path),
    )
    monkeypatch.setattr(
        "scripts.build_official_blender_mcp_distribution._run",
        lambda *args, **kwargs: SimpleNamespace(stdout="1"),
    )
    monkeypatch.setattr("scripts.build_official_blender_mcp_distribution._build_candidate", fail)
    with pytest.raises(RuntimeError, match="gate"):
        build_distribution(tmp_path, Path("blender"), Path("uv"), output)
    assert (output / "marker").read_text() == "last-good"
