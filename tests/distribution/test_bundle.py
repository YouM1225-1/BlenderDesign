from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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
import scripts.build_official_blender_mcp_distribution as builder  # noqa: E402


COMMIT = "98d1624b39d8e35baf1ae8ce0c1d13a2c321c9a4"


def manifest() -> dict[str, object]:
    artifacts = [
        {"role": role, "filename": filename, "size": 1, "sha256": "a" * 64}
        for role, filename in ARTIFACTS
    ]
    return {
        "schema_version": 2,
        "bundle_version": "1.0.0+98d1624b39d8",
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


@pytest.mark.parametrize("mutation", ["version", "catalog", "order", "float_port", "bool_epoch"])
def test_manifest_requires_fixed_versions_and_catalog(mutation: str) -> None:
    data = manifest()
    if mutation == "version":
        data["server"]["version"] = "2.0.0"
    elif mutation == "catalog":
        data["tools"] = data["tools"][:-1]
    elif mutation == "float_port":
        data["bridge"]["port"] = 9876.0
    elif mutation == "bool_epoch":
        data["build"]["source_date_epoch"] = True
    else:
        data["artifacts"].reverse()
    with pytest.raises(ValueError):
        parse_manifest(raw(data))


def _git(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, check=True, capture_output=capture_output, text=True
    )


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


def test_checkout_rejects_ignored_scoped_untracked_file(tmp_path: Path) -> None:
    bundle, _ = _checkout(tmp_path)
    root = bundle.parents[2]
    _git(["git", "switch", "-qc", "ignore-fixture"], root)
    (root / ".gitignore").write_text("*.ignored\n")
    _git(["git", "add", ".gitignore"], root)
    _git(["git", "commit", "-qm", "ignore fixture"], root)
    commit = _git(["git", "rev-parse", "HEAD"], root).stdout.strip()
    _git(["git", "checkout", "-q", "--detach", commit], root)
    (bundle / "hostile.ignored").write_text("ignored but executable")
    with pytest.raises(ValueError, match="dirty distribution checkout"):
        verify_distribution_checkout(bundle, commit, _git)


def test_checkout_ignores_redirected_git_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle, commit = _checkout(tmp_path)
    hostile = tmp_path / "hostile"
    hostile.mkdir()
    monkeypatch.setenv("GIT_DIR", str(hostile))
    assert verify_distribution_checkout(bundle, commit, _git).expected_commit == commit


def test_checkout_supports_real_subprocess_runner_without_console_output(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    bundle, commit = _checkout(tmp_path)

    assert verify_distribution_checkout(bundle, commit, subprocess.run).expected_commit == commit
    assert capfd.readouterr() == ("", "")


def test_checkout_ignores_hostile_path_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, commit = _checkout(tmp_path)
    hostile_bin = tmp_path / "hostile-bin"
    hostile_bin.mkdir()
    sentinel = tmp_path / "hostile-git-ran"
    fake_git = hostile_bin / "git"
    fake_git.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 97\n")
    fake_git.chmod(0o700)
    monkeypatch.setenv("PATH", f"{hostile_bin}:{os.environ['PATH']}")

    assert verify_distribution_checkout(bundle, commit, subprocess.run).expected_commit == commit
    assert not sentinel.exists()


def _rewrite_payload(bundle: Path, filename: str, content: bytes) -> None:
    (bundle / filename).write_bytes(content)
    data = json.loads((bundle / "manifest.json").read_bytes())
    artifact = next(item for item in data["artifacts"] if item["filename"] == filename)
    artifact["size"] = len(content)
    artifact["sha256"] = hashlib.sha256(content).hexdigest()
    (bundle / "manifest.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
    (bundle / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((bundle / name).read_bytes()).hexdigest()}  {name}\n"
            for name in ["manifest.json", *(name for _, name in ARTIFACTS)]
        )
    )


def test_checkout_rejects_distribution_replacement_ref(tmp_path: Path) -> None:
    bundle, reviewed = _checkout(tmp_path)
    root = bundle.parents[2]
    _git(["git", "switch", "-qc", "hostile"], root)
    _rewrite_payload(bundle, ARTIFACTS[0][1], b"hostile-wheel")
    _git(["git", "add", "."], root)
    _git(["git", "commit", "-qm", "hostile replacement"], root)
    hostile = _git(["git", "rev-parse", "HEAD"], root).stdout.strip()
    _git(["git", "replace", reviewed, hostile], root)
    _git(["git", "checkout", "-q", "--detach", reviewed], root)
    _git(["git", "reset", "-q", "--hard", reviewed], root)
    with pytest.raises(ValueError, match="dirty distribution checkout"):
        verify_distribution_checkout(bundle, reviewed, _git)


def test_checkout_clears_git_config_and_disables_external_status_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, commit = _checkout(tmp_path)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "!false")
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/hostile")
    calls: list[tuple[list[str], dict[str, str]]] = []

    def recording_runner(
        argv: list[str], *, cwd: Path, env: dict[str, str], capture_output: bool
    ) -> subprocess.CompletedProcess[str]:
        calls.append((argv, env))
        return _git(argv, cwd, env, capture_output)

    verify_distribution_checkout(bundle, commit, recording_runner)
    for argv, env in calls:
        assert argv[:2] == ["/usr/bin/git", "--no-replace-objects"]
        assert "GIT_CONFIG_COUNT" not in env
        assert "GIT_CONFIG_KEY_0" not in env
        assert "GIT_CONFIG_VALUE_0" not in env
        assert "GIT_REPLACE_REF_BASE" not in env
        assert env["GIT_NO_REPLACE_OBJECTS"] == "1"
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    status_argv = next(argv for argv, _ in calls if "status" in argv)
    assert "core.fsmonitor=false" in status_argv


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
        "demo==1 --hash=sha256:" + "a" * 64 + " -r other.lock",
        "demo==1 --hash=sha256:" + "a" * 64 + " -c constraints.lock",
        "demo==1 --hash=sha256:" + "a" * 64 + " --editable ./local",
        "demo==1 --hash=sha256:" + "a" * 64 + " ./local",
        "demo==1 --hash=sha256:" + "a" * 64 + " demo.tar.gz",
        "demo==1 --hash=sha256:" + "a" * 64 + " --only-binary :all:",
        "--index-url https://pypi.org/simple",
    ],
)
def test_runtime_lock_is_fully_pinned_and_hashed(lock: str) -> None:
    with pytest.raises(ValueError):
        validate_runtime_lock(lock.encode())


def test_builder_uses_two_fresh_git_archives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(["git", "init", "-q"], source)
    _git(["git", "config", "user.name", "Test"], source)
    _git(["git", "config", "user.email", "test@example.invalid"], source)
    (source / "payload").write_text("reviewed")
    _git(["git", "add", "."], source)
    _git(["git", "commit", "-qm", "fixture"], source)
    commit = _git(["git", "rev-parse", "HEAD"], source).stdout.strip()
    calls: list[list[str]] = []
    real_run = builder._run

    def fail_after_archives(argv: list[str], **kwargs: object) -> object:
        calls.append(argv)
        if sum("archive" in command for command in calls) == 2:
            raise RuntimeError("stop")
        return real_run(argv, **kwargs)

    monkeypatch.setattr(builder, "UPSTREAM_COMMIT", commit)
    monkeypatch.setattr(builder, "_run", fail_after_archives)
    with pytest.raises(RuntimeError, match="stop"):
        build_distribution(source, Path("blender"), Path("uv"), tmp_path / "out")
    assert sum("archive" in command for command in calls) == 2


def test_builder_ignores_upstream_replacement_and_source_info_attributes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "upstream"
    source.mkdir()
    _git(["git", "init", "-q", "-b", "main"], source)
    _git(["git", "config", "user.name", "Test"], source)
    _git(["git", "config", "user.email", "test@example.invalid"], source)
    (source / "payload").write_text("reviewed")
    (source / "excluded").write_text("committed exclusion")
    (source / ".gitattributes").write_text("excluded export-ignore\n")
    _git(["git", "add", "."], source)
    _git(["git", "commit", "-qm", "reviewed"], source)
    reviewed = _git(["git", "rev-parse", "HEAD"], source).stdout.strip()
    _git(["git", "switch", "-qc", "hostile"], source)
    (source / "payload").write_text("hostile")
    _git(["git", "commit", "-qam", "hostile"], source)
    hostile = _git(["git", "rev-parse", "HEAD"], source).stdout.strip()
    _git(["git", "branch", "-f", "main", reviewed], source)
    _git(["git", "replace", reviewed, hostile], source)
    (source / ".git/info/attributes").write_text("payload export-ignore\n")
    hostile_attributes = tmp_path / "hostile-attributes"
    hostile_attributes.write_text("payload export-ignore\n")
    _git(["git", "config", "core.attributesFile", str(hostile_attributes)], source)
    clean_workspace = tmp_path / "clean-workspace"
    clean_workspace.mkdir()
    monkeypatch.setattr(builder, "UPSTREAM_COMMIT", reviewed)
    clean_roots, _epoch = builder._extract_two_archives(source, clean_workspace)
    clean_trees = [
        {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        for root in clean_roots
    ]
    hostile_template = tmp_path / "hostile-template"
    (hostile_template / "info").mkdir(parents=True)
    (hostile_template / "info/attributes").write_text("payload export-ignore\n")
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(hostile_template))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.attributesFile")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(hostile_attributes))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    roots, _epoch = builder._extract_two_archives(source, workspace)
    hostile_trees = [
        {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        for root in roots
    ]
    assert hostile_trees == clean_trees
    for root in (*clean_roots, *roots):
        assert (root / "payload").read_text() == "reviewed"
        assert not (root / "excluded").exists()


def test_builder_rejects_symlinked_object_store_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git(["git", "init", "-q"], source)
    _git(["git", "config", "user.name", "Test"], source)
    _git(["git", "config", "user.email", "test@example.invalid"], source)
    (source / "payload").write_text("reviewed")
    _git(["git", "add", "."], source)
    _git(["git", "commit", "-qm", "fixture"], source)
    commit = _git(["git", "rev-parse", "HEAD"], source).stdout.strip()
    objects = source / ".git/objects"
    actual_objects = source / ".git/actual-objects"
    objects.rename(actual_objects)
    objects.symlink_to(actual_objects)
    monkeypatch.setattr(builder, "UPSTREAM_COMMIT", commit)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ValueError, match="object store root"):
        builder._extract_two_archives(source, workspace)


@pytest.mark.parametrize("mutation", ["entry", "file"])
def test_object_store_copy_rejects_source_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    source = tmp_path / "objects"
    (source / "a-dir").mkdir(parents=True)
    (source / "z-file").write_bytes(b"before")
    target = tmp_path / "target"
    target.mkdir()
    real_mkdir = Path.mkdir
    mutated = False

    def mutating_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        nonlocal mutated
        real_mkdir(path, *args, **kwargs)
        if not mutated and path == target / "a-dir":
            mutated = True
            if mutation == "entry":
                (source / "late-object").write_bytes(b"late")
            else:
                (source / "z-file").write_bytes(b"after!")

    monkeypatch.setattr(Path, "mkdir", mutating_mkdir)
    with pytest.raises(ValueError, match="changed during copy"):
        builder._copy_object_store(source, target)


def test_builder_sanitizes_probe_environment() -> None:
    from scripts.build_official_blender_mcp_distribution import sanitized_environment

    env = sanitized_environment(
        {"BLENDER_MCP_HOST": "evil", "UV_INDEX_URL": "evil", "PIP_INDEX_URL": "evil"}
    )
    assert env["BLENDER_MCP_HOST"] == "localhost"
    assert env["BLENDER_MCP_PORT"] == "9876"
    assert env["UV_DEFAULT_INDEX"] == "https://pypi.org/simple"
    assert "UV_INDEX_URL" not in env and "PIP_INDEX_URL" not in env


def test_locked_install_uses_single_supported_uv_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def record(argv: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(argv)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(builder, "_run", record)
    builder._install_lock(Path("uv"), Path("python"), tmp_path / "runtime.lock")
    assert len(calls) == 1
    assert "--no-build" not in calls[0]
    assert "--require-hashes" in calls[0]
    assert calls[0][calls[0].index("--only-binary") + 1] == ":all:"
    assert "--no-deps" in calls[0]


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
        lambda source, workspace: ((tmp_path, tmp_path), 1),
    )
    monkeypatch.setattr(
        "scripts.build_official_blender_mcp_distribution._run",
        lambda *args, **kwargs: SimpleNamespace(stdout="1"),
    )
    monkeypatch.setattr("scripts.build_official_blender_mcp_distribution._build_candidate", fail)
    with pytest.raises(RuntimeError, match="gate"):
        build_distribution(tmp_path, Path("blender"), Path("uv"), output)
    assert (output / "marker").read_text() == "last-good"


def test_tampered_manifest_cannot_replace_last_good_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_bundle = ROOT / "plugins/blender-mcp-installer/artifacts"
    output = tmp_path / "artifacts"
    shutil.copytree(source_bundle, output)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}

    def tampered_candidate(
        source_roots: tuple[Path, Path],
        blender_bin: Path,
        uv_bin: Path,
        candidate: Path,
        workspace: Path,
        epoch: int,
    ) -> object:
        shutil.copytree(output, candidate)
        data = json.loads((candidate / "manifest.json").read_bytes())
        data["artifacts"][0]["size"] += 1
        data["artifacts"][0]["sha256"] = "a" * 64
        (candidate / "manifest.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
        (candidate / "SHA256SUMS").write_text(builder._write_checksum_text(candidate))
        return builder._validate_candidate(candidate, Path("blender"))

    monkeypatch.setattr(
        builder, "_extract_two_archives", lambda source, workspace: ((output, output), 1)
    )
    monkeypatch.setattr(builder, "_run", lambda *args, **kwargs: SimpleNamespace(stdout="1"))
    monkeypatch.setattr(builder, "_build_candidate", tampered_candidate)
    with pytest.raises(ValueError, match="manifest artifact"):
        builder.build_distribution(Path("source"), Path("blender"), Path("uv"), output)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir()}
    assert after == before


def test_candidate_is_fsynced_before_first_publication_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "artifacts"
    output.mkdir()
    (output / "last-good").write_text("old")
    required: set[int] = set()
    synced: set[int] = set()
    candidate_root: list[Path] = []

    def build_candidate(*args: object) -> object:
        candidate = args[3]
        assert isinstance(candidate, Path)
        candidate.mkdir()
        (candidate / "one").write_text("1")
        (candidate / "two").write_text("2")
        candidate_root.append(candidate)
        required.update(path.stat().st_ino for path in candidate.iterdir())
        required.add(candidate.stat().st_ino)
        return object()

    real_fsync = os.fsync
    real_rename = os.rename

    def record_fsync(fd: int) -> None:
        synced.add(os.fstat(fd).st_ino)
        real_fsync(fd)

    def checked_rename(source: Path, target: Path) -> None:
        assert candidate_root
        assert required <= synced
        real_rename(source, target)

    monkeypatch.setattr(builder, "_extract_two_archives", lambda source, workspace: ((output, output), 1))
    monkeypatch.setattr(builder, "_build_candidate", build_candidate)
    monkeypatch.setattr(os, "fsync", record_fsync)
    monkeypatch.setattr(os, "rename", checked_rename)
    builder.build_distribution(Path("source"), Path("blender"), Path("uv"), output)
