from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping, Protocol, Sequence


UPSTREAM_COMMIT = "9e5275c124df44c4a1cbcba2451fdd8d32ad8780"
BUNDLE_VERSION = "1.0.0+" + UPSTREAM_COMMIT[:12]
TOOLS = (
    "execute_blender_code",
    "execute_blender_code_for_cli",
    "get_blendfile_summary_datablocks",
    "get_blendfile_summary_datablocks_for_cli",
    "get_blendfile_summary_missing_files",
    "get_blendfile_summary_missing_files_for_cli",
    "get_blendfile_summary_of_linked_libraries",
    "get_blendfile_summary_of_linked_libraries_for_cli",
    "get_blendfile_summary_path_info",
    "get_blendfile_summary_path_info_for_cli",
    "get_blendfile_summary_usage_guess",
    "get_blendfile_summary_usage_guess_for_cli",
    "get_object_detail_summary",
    "get_objects_summary",
    "get_python_api_docs",
    "get_screenshot_of_area_as_image",
    "get_screenshot_of_window_as_image",
    "get_screenshot_of_window_as_json",
    "jump_to_tab_by_name",
    "jump_to_tab_by_space_type",
    "jump_to_view3d_object_by_name",
    "jump_to_view3d_object_data_by_name",
    "render_thumbnail_to_path",
    "render_viewport_to_path",
    "search_api_docs",
    "search_manual_docs",
)
ARTIFACTS = (
    ("server_wheel", "blender_mcp-1.0.0-py3-none-any.whl"),
    ("blender_extension", "mcp-1.0.0.zip"),
    ("runtime_lock", "runtime-requirements.lock"),
)
CHECKSUM_FILES = ("manifest.json", *(name for _, name in ARTIFACTS))
GIT_REDIRECTS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
)
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_LOCK_STANZA = re.compile(
    rf"{_NAME}(?:\[{_NAME}(?:,{_NAME})*\])?==[A-Za-z0-9][A-Za-z0-9.!+_-]*"
    rf"(?:\s+--hash=sha256:[0-9a-f]{{64}})+\Z"
)


class Runner(Protocol):
    def __call__(
        self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str]
    ) -> object: ...


class _GitRunner(Protocol):
    def __call__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        capture_output: bool,
    ) -> object: ...


@dataclass(frozen=True)
class Artifact:
    role: str
    filename: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    bundle_version: str
    platform: Mapping[str, object]
    upstream: Mapping[str, object]
    python: Mapping[str, object]
    blender: Mapping[str, object]
    server: Mapping[str, object]
    extension: Mapping[str, object]
    bridge: Mapping[str, object]
    build: Mapping[str, object]
    tools: tuple[str, ...]
    artifacts: tuple[Artifact, ...]


@dataclass(frozen=True)
class TrustedCheckout:
    bundle_root: Path
    repository_root: Path
    expected_commit: str
    trusted_checksums: bytes


@dataclass(frozen=True)
class StagedBundle:
    root: Path
    manifest: ReleaseManifest

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def wheel_path(self) -> Path:
        return self.root / ARTIFACTS[0][1]

    @property
    def extension_path(self) -> Path:
        return self.root / ARTIFACTS[1][1]

    @property
    def runtime_lock_path(self) -> Path:
        return self.root / ARTIFACTS[2][1]


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _keys(value: object, expected: tuple[str, ...], label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(expected) or len(value) != len(expected):
        raise ValueError(f"invalid {label} keys")
    return value


def _fixed(value: object, expected: dict[str, object], label: str) -> dict[str, object]:
    parsed = _keys(value, tuple(expected), label)
    if any(type(parsed[key]) is not type(fixed) or parsed[key] != fixed for key, fixed in expected.items()):
        raise ValueError(f"invalid {label}")
    return parsed


def parse_manifest(raw: bytes) -> ReleaseManifest:
    try:
        data = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid manifest JSON") from exc
    top = _keys(
        data,
        (
            "schema_version",
            "bundle_version",
            "platform",
            "upstream",
            "python",
            "blender",
            "server",
            "extension",
            "bridge",
            "build",
            "tools",
            "artifacts",
        ),
        "manifest",
    )
    if type(top["schema_version"]) is not int or top["schema_version"] != 2:
        raise ValueError("invalid schema_version")
    if top["bundle_version"] != BUNDLE_VERSION:
        raise ValueError("invalid bundle_version")
    platform = _fixed(top["platform"], {"system": "Darwin", "machine": "arm64"}, "platform")
    upstream = _fixed(
        top["upstream"],
        {
            "url": "https://projects.blender.org/lab/blender_mcp.git",
            "commit": UPSTREAM_COMMIT,
        },
        "upstream",
    )
    python = _fixed(
        top["python"], {"runtime_minor": "3.13", "build_tested": "3.13.13"}, "python"
    )
    blender = _fixed(
        top["blender"],
        {"minimum": "5.2.0", "maximum_exclusive": "5.3.0", "tested": "5.2.0"},
        "blender",
    )
    server = _fixed(
        top["server"],
        {"distribution": "blender-mcp", "version": "1.0.0", "mcp_sdk": "1.28.1"},
        "server",
    )
    extension = _fixed(
        top["extension"],
        {"repository": "user_default", "id": "mcp", "version": "1.0.0"},
        "extension",
    )
    bridge = _fixed(top["bridge"], {"host": "localhost", "port": 9876}, "bridge")
    build = _keys(
        top["build"],
        ("source_date_epoch", "uv", "python", "blender", "codex_tested", "backend", "index"),
        "build",
    )
    if type(build["source_date_epoch"]) is not int or build["source_date_epoch"] <= 0:
        raise ValueError("invalid source_date_epoch")
    fixed_build = {
        "uv": "0.12.2",
        "python": "3.13.13",
        "blender": "5.2.0",
        "codex_tested": "0.148.0-alpha.9",
        "index": "https://pypi.org/simple",
    }
    if any(build[key] != value for key, value in fixed_build.items()):
        raise ValueError("invalid build versions")
    _fixed(build["backend"], {"name": "setuptools", "version": "80.9.0"}, "backend")
    if type(top["tools"]) is not list or tuple(top["tools"]) != TOOLS:
        raise ValueError("invalid tool catalog")
    raw_artifacts = top["artifacts"]
    if type(raw_artifacts) is not list or len(raw_artifacts) != len(ARTIFACTS):
        raise ValueError("invalid artifacts")
    artifacts: list[Artifact] = []
    names: set[str] = set()
    roles: set[str] = set()
    for raw_artifact, expected in zip(raw_artifacts, ARTIFACTS, strict=True):
        item = _keys(raw_artifact, ("role", "filename", "size", "sha256"), "artifact")
        role, filename = item["role"], item["filename"]
        if (role, filename) != expected or role in roles or filename in names:
            raise ValueError("invalid artifact role or filename")
        if (
            type(filename) is not str
            or Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
            or filename in {".", ".."}
        ):
            raise ValueError("unsafe artifact filename")
        size, digest = item["size"], item["sha256"]
        if type(size) is not int or size <= 0:
            raise ValueError("invalid artifact size")
        if type(digest) is not str or not _HEX.fullmatch(digest):
            raise ValueError("invalid artifact hash")
        roles.add(role)
        names.add(filename)
        artifacts.append(Artifact(role, filename, size, digest))
    return ReleaseManifest(
        2,
        top["bundle_version"],
        platform,
        upstream,
        python,
        blender,
        server,
        extension,
        bridge,
        build,
        TOOLS,
        tuple(artifacts),
    )


def validate_runtime_lock(raw: bytes) -> None:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("runtime lock is not UTF-8") from exc
    stanzas: list[str] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if current:
                raise ValueError("invalid requirement continuation")
            continue
        continued = stripped.endswith("\\")
        segment = stripped[:-1].rstrip() if continued else stripped
        if "\\" in segment:
            raise ValueError("invalid requirement continuation")
        current.append(segment)
        if not continued:
            stanzas.append(" ".join(current))
            current = []
    if current or not stanzas:
        raise ValueError("invalid requirement continuation")
    for stanza in stanzas:
        if not _LOCK_STANZA.fullmatch(stanza):
            raise ValueError("runtime requirement is not an exact hashed pin")


def _bytes(output: object) -> bytes:
    if isinstance(output, bytes):
        return output
    if isinstance(output, str):
        return output.encode()
    raise ValueError("runner returned invalid output")


def _git(runner: _GitRunner, argv: list[str], root: Path, env: Mapping[str, str]) -> bytes:
    argv = [
        "/usr/bin/git",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.attributesFile=/dev/null",
        *argv[1:],
    ]
    try:
        completed = runner(argv, cwd=root, env=env, capture_output=True)
    except Exception as exc:
        raise ValueError(f"git command failed: {' '.join(argv)}") from exc
    if getattr(completed, "returncode", 0) != 0:
        raise ValueError(f"git command failed: {' '.join(argv)}")
    return _bytes(getattr(completed, "stdout", b""))


def _read_stable(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink < 1:
            raise ValueError(f"not a regular file: {path.name}")
        chunks: list[bytes] = []
        offset = 0
        while chunk := os.pread(fd, min(1024 * 1024, before.st_size - offset + 1), offset):
            chunks.append(chunk)
            offset += len(chunk)
            if offset > before.st_size:
                break
        data = b"".join(chunks)
        after = os.fstat(fd)
        if len(data) != before.st_size or _identity(before) != _identity(after):
            raise ValueError(f"file changed while reading: {path.name}")
        return data
    finally:
        os.close(fd)


def _identity(stat: os.stat_result) -> tuple[int, ...]:
    return (
        stat.st_dev,
        stat.st_ino,
        stat.st_uid,
        stat.st_mode,
        stat.st_size,
        stat.st_mtime_ns,
    )


def _parse_checksums(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("invalid SHA256SUMS") from exc
    if len(lines) != len(CHECKSUM_FILES):
        raise ValueError("invalid SHA256SUMS file count")
    result: dict[str, str] = {}
    for line, name in zip(lines, CHECKSUM_FILES, strict=True):
        if len(line) != 66 + len(name) or line[64:66] != "  " or line[66:] != name:
            raise ValueError("invalid SHA256SUMS ordering")
        digest = line[:64]
        if not _HEX.fullmatch(digest):
            raise ValueError("invalid SHA256SUMS hash")
        result[name] = digest
    return result


def verify_distribution_checkout(
    bundle_root: Path, expected_commit: str, runner: _GitRunner
) -> TrustedCheckout:
    bundle_root = bundle_root.resolve()
    if not _COMMIT.fullmatch(expected_commit):
        raise ValueError("expected commit must be 40 lowercase hex characters")
    env = dict(os.environ)
    for key in tuple(env):
        if key in GIT_REDIRECTS or key.startswith("GIT_CONFIG_") or key in {
            "GIT_REPLACE_REF_BASE",
            "GIT_ATTR_NOSYSTEM",
            "GIT_EXTERNAL_DIFF",
            "GIT_DIFF_OPTS",
        }:
            env.pop(key)
    env.update(
        {
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    repository_root = Path(
        _git(runner, ["git", "rev-parse", "--show-toplevel"], bundle_root, env).decode().strip()
    ).resolve()
    expected_bundle = repository_root / "plugins/blender-mcp-installer/artifacts"
    if bundle_root != expected_bundle:
        raise ValueError("bundle root is not the committed artifact directory")
    head = _git(runner, ["git", "rev-parse", "HEAD"], repository_root, env).decode().strip()
    branch = _git(runner, ["git", "rev-parse", "--abbrev-ref", "HEAD"], repository_root, env).decode().strip()
    if head != expected_commit or branch != "HEAD":
        raise ValueError("checkout is not detached at the expected commit")
    status = _git(
        runner,
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignored=matching",
        ],
        repository_root,
        env,
    ).decode()
    scoped_dirs = (".agents/", "plugins/blender-mcp-installer/", "scripts/requirements/")
    scoped_files = (
        "docs/distribute-official-blender-mcp.md",
        "scripts/build_official_blender_mcp_distribution.py",
    )
    for line in status.splitlines():
        code, path = line[:2], line[3:].strip('"')
        if code not in {"??", "!!"} or path in scoped_files or path.startswith(scoped_dirs):
            raise ValueError(f"dirty distribution checkout: {path}")
    committed_path = "plugins/blender-mcp-installer/artifacts/SHA256SUMS"
    trusted = _git(
        runner, ["git", "show", f"{expected_commit}:{committed_path}"], repository_root, env
    )
    _parse_checksums(trusted)
    if _read_stable(bundle_root / "SHA256SUMS") != trusted:
        raise ValueError("working SHA256SUMS differs from reviewed commit")
    checksums = _parse_checksums(trusted)
    for name, expected_hash in checksums.items():
        if hashlib.sha256(_read_stable(bundle_root / name)).hexdigest() != expected_hash:
            raise ValueError(f"artifact checksum mismatch: {name}")
    return TrustedCheckout(bundle_root, repository_root, expected_commit, trusted)


class VerifiedBundle:
    def __init__(
        self,
        checkout: TrustedCheckout,
        manifest: ReleaseManifest,
        files: dict[str, tuple[int, os.stat_result]],
    ) -> None:
        self.checkout = checkout
        self.manifest = manifest
        self._files = files

    def materialize(self, private_bundle_stage: Path) -> StagedBundle:
        private_bundle_stage.mkdir(mode=0o700, parents=False, exist_ok=False)
        try:
            for name in ("SHA256SUMS", *CHECKSUM_FILES):
                source_fd, source_stat = self._files[name]
                target = private_bundle_stage / name
                target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                digest = hashlib.sha256()
                copied = 0
                try:
                    while chunk := os.pread(source_fd, 1024 * 1024, copied):
                        view = memoryview(chunk)
                        while view:
                            view = view[os.write(target_fd, view) :]
                        digest.update(chunk)
                        copied += len(chunk)
                    os.fsync(target_fd)
                finally:
                    os.close(target_fd)
                after = os.fstat(source_fd)
                if _identity(source_stat) != _identity(after) or copied != source_stat.st_size:
                    raise ValueError(f"source changed during materialization: {name}")
                expected = hashlib.sha256(os.pread(source_fd, source_stat.st_size, 0)).hexdigest()
                if digest.hexdigest() != expected:
                    raise ValueError(f"staged copy differs from opened source: {name}")
            directory_fd = os.open(private_bundle_stage, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            return StagedBundle(private_bundle_stage, self.manifest)
        except Exception:
            for child in private_bundle_stage.iterdir():
                child.unlink()
            private_bundle_stage.rmdir()
            raise


@contextmanager
def open_verified_bundle(checkout: TrustedCheckout) -> Iterator[VerifiedBundle]:
    expected_names = {"SHA256SUMS", *CHECKSUM_FILES}
    if {entry.name for entry in checkout.bundle_root.iterdir()} != expected_names:
        raise ValueError("bundle contains missing or extra files")
    files: dict[str, tuple[int, os.stat_result]] = {}
    try:
        for name in ("SHA256SUMS", *CHECKSUM_FILES):
            fd = os.open(checkout.bundle_root / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            file_stat = os.fstat(fd)
            if not stat.S_ISREG(file_stat.st_mode):
                os.close(fd)
                raise ValueError(f"not a regular bundle file: {name}")
            files[name] = (fd, file_stat)
        checksum_raw = os.pread(files["SHA256SUMS"][0], files["SHA256SUMS"][1].st_size, 0)
        if checksum_raw != checkout.trusted_checksums:
            raise ValueError("opened SHA256SUMS differs from reviewed commit")
        checksums = _parse_checksums(checksum_raw)
        opened: dict[str, bytes] = {}
        for name in CHECKSUM_FILES:
            fd, file_stat = files[name]
            content = os.pread(fd, file_stat.st_size, 0)
            if len(content) != file_stat.st_size or hashlib.sha256(content).hexdigest() != checksums[name]:
                raise ValueError(f"opened artifact checksum mismatch: {name}")
            opened[name] = content
        manifest = parse_manifest(opened["manifest.json"])
        for artifact in manifest.artifacts:
            if len(opened[artifact.filename]) != artifact.size:
                raise ValueError(f"manifest size mismatch: {artifact.filename}")
            if hashlib.sha256(opened[artifact.filename]).hexdigest() != artifact.sha256:
                raise ValueError(f"manifest checksum mismatch: {artifact.filename}")
        validate_runtime_lock(opened[ARTIFACTS[2][1]])
        yield VerifiedBundle(checkout, manifest, files)
    finally:
        for fd, _file_stat in files.values():
            os.close(fd)
