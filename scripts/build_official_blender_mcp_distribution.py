from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).parents[1]
PLUGIN_SCRIPTS = ROOT / "plugins/blender-mcp-installer/scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))

from blender_mcp_installer.bundle import (  # noqa: E402
    ARTIFACTS,
    BUNDLE_VERSION,
    TOOLS,
    UPSTREAM_COMMIT,
    ReleaseManifest,
    parse_manifest,
    validate_runtime_lock,
)


INDEX = "https://pypi.org/simple"
BUILD_INPUT = ROOT / "scripts/requirements/official-blender-mcp-build.in"
BUILD_LOCK = ROOT / "scripts/requirements/official-blender-mcp-build.lock"
RUNTIME_INPUT = ROOT / "scripts/requirements/official-blender-mcp-runtime.in"
RUNTIME_LOCK = ROOT / "plugins/blender-mcp-installer/artifacts/runtime-requirements.lock"
REMOVE_ENV = {
    "BLENDER_MCP_HOST",
    "BLENDER_MCP_PORT",
    "UV_INDEX",
    "UV_INDEX_URL",
    "UV_EXTRA_INDEX_URL",
    "UV_DEFAULT_INDEX",
    "UV_FIND_LINKS",
    "UV_CONSTRAINT",
    "UV_BUILD_CONSTRAINT",
    "UV_OVERRIDE",
    "UV_NO_INDEX",
    "PIP_INDEX_URL",
    "PIP_EXTRA_INDEX_URL",
    "PIP_FIND_LINKS",
    "PIP_CONSTRAINT",
    "PIP_REQUIRE_VIRTUALENV",
    "PYTHONPATH",
    "PYTHONHOME",
    "VIRTUAL_ENV",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
    "GIT_TEMPLATE_DIR",
}


def sanitized_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    for key in tuple(env):
        if (
            key in REMOVE_ENV
            or key.startswith(("UV_", "PIP_", "GIT_CONFIG_"))
            or key
            in {
                "GIT_REPLACE_REF_BASE",
                "GIT_ATTR_NOSYSTEM",
                "GIT_EXTERNAL_DIFF",
                "GIT_DIFF_OPTS",
            }
        ):
            env.pop(key)
    env.update(
        {
            "BLENDER_MCP_HOST": "localhost",
            "BLENDER_MCP_PORT": "9876",
            "UV_DEFAULT_INDEX": INDEX,
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    return env


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=sanitized_environment() if env is None else env,
        check=False,
        capture_output=capture_output,
        text=True,
    )
    if getattr(completed, "returncode", 0) != 0:
        stderr = getattr(completed, "stderr", "") or ""
        raise RuntimeError(f"command failed ({' '.join(argv)}): {stderr.strip()}")
    return completed


def validate_extension_command(blender_bin: Path, normalized_zip: Path) -> list[str]:
    return [str(blender_bin), "--command", "extension", "validate", str(normalized_zip)]


def _git_command(*arguments: str) -> list[str]:
    return [
        "git",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.attributesFile=/dev/null",
        *arguments,
    ]


def _source_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_uid,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _copy_object_directory(
    source_fd: int, target: Path, relative: PurePosixPath = PurePosixPath()
) -> None:
    before = os.fstat(source_fd)
    names = tuple(sorted(os.listdir(source_fd)))
    entries = [
        (name, os.stat(name, dir_fd=source_fd, follow_symlinks=False)) for name in names
    ]
    for name, metadata in entries:
        child_relative = relative / name
        if child_relative.as_posix() in {"info/alternates", "info/http-alternates"}:
            raise ValueError("upstream Git alternates are not allowed")
        destination = target / name
        if stat.S_ISDIR(metadata.st_mode):
            destination.mkdir(exist_ok=True)
            child_fd = os.open(
                name,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=source_fd,
            )
            try:
                if _source_identity(os.fstat(child_fd)) != _source_identity(metadata):
                    raise ValueError(f"source object store changed during copy: {child_relative}")
                _copy_object_directory(child_fd, destination, child_relative)
            finally:
                os.close(child_fd)
            after_child = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
            if _source_identity(after_child) != _source_identity(metadata):
                raise ValueError(f"source object store changed during copy: {child_relative}")
        elif stat.S_ISREG(metadata.st_mode):
            source_file_fd = os.open(
                name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=source_fd
            )
            target_fd = -1
            try:
                opened = os.fstat(source_file_fd)
                if _source_identity(opened) != _source_identity(metadata):
                    raise ValueError(f"source object store changed during copy: {child_relative}")
                target_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                copied = 0
                while chunk := os.read(source_file_fd, 1024 * 1024):
                    view = memoryview(chunk)
                    while view:
                        view = view[os.write(target_fd, view) :]
                    copied += len(chunk)
                after_file = os.fstat(source_file_fd)
                if (
                    _source_identity(after_file) != _source_identity(opened)
                    or copied != opened.st_size
                ):
                    raise ValueError(f"source object store changed during copy: {child_relative}")
            finally:
                if target_fd >= 0:
                    os.close(target_fd)
                os.close(source_file_fd)
        else:
            raise ValueError(f"unsafe upstream Git object-store entry: {child_relative}")
    after = os.fstat(source_fd)
    if _source_identity(after) != _source_identity(before) or tuple(sorted(os.listdir(source_fd))) != names:
        raise ValueError(f"source object store changed during copy: {relative or '.'}")


def _copy_object_store(source: Path, target: Path) -> None:
    try:
        root_metadata = source.lstat()
    except OSError as exc:
        raise ValueError("upstream Git object store root is missing") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("upstream Git object store root must be a real directory")
    source_fd = os.open(
        source, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        if _source_identity(os.fstat(source_fd)) != _source_identity(root_metadata):
            raise ValueError("source object store changed during copy: root")
        _copy_object_directory(source_fd, target)
        if _source_identity(os.fstat(source_fd)) != _source_identity(root_metadata):
            raise ValueError("source object store changed during copy: root")
    finally:
        os.close(source_fd)


def _extract_two_archives(source: Path, workspace: Path) -> tuple[tuple[Path, Path], int]:
    archives = (workspace / "source-1.tar", workspace / "source-2.tar")
    roots = (workspace / "source-1", workspace / "source-2")
    isolated = workspace / "source.git"
    env = sanitized_environment()
    common_dir = _run(
        _git_command("rev-parse", "--git-common-dir"), cwd=source, env=env
    ).stdout.strip()
    common_path = Path(common_dir)
    if not common_path.is_absolute():
        common_path = source / common_path
    source_objects = common_path / "objects"
    empty_template = workspace / "empty-template"
    empty_template.mkdir(mode=0o700)
    os.chmod(empty_template, 0o700)
    _run(
        _git_command(
            "init", "--bare", f"--template={empty_template}", str(isolated)
        ),
        env=env,
    )
    _copy_object_store(source_objects, isolated / "objects")
    for archive in archives:
        _run(
            _git_command(
                f"--git-dir={isolated}",
                "archive",
                "--format=tar",
                "-o",
                str(archive),
                UPSTREAM_COMMIT,
            ),
            env=env,
        )
    epoch_text = _run(
        _git_command(
            f"--git-dir={isolated}", "show", "-s", "--format=%ct", UPSTREAM_COMMIT
        ),
        env=env,
    ).stdout.strip()
    if not epoch_text.isdigit() or int(epoch_text) <= 0:
        raise ValueError("invalid source commit timestamp")
    for archive, root in zip(archives, roots, strict=True):
        root.mkdir()
        with tarfile.open(archive) as source_tar:
            source_tar.extractall(root, filter="data")
    return roots, int(epoch_text)


def _compile_lock(
    uv_bin: Path,
    source: Path,
    output: Path,
    python_version: str,
) -> None:
    _run(
        [
            str(uv_bin),
            "pip",
            "compile",
            str(source),
            "--output-file",
            str(output),
            "--python-version",
            python_version,
            "--python-platform",
            "aarch64-apple-darwin",
            "--only-binary",
            ":all:",
            "--generate-hashes",
            "--no-header",
            "--no-annotate",
            "--no-sources",
            "--exclude-newer",
            "2026-08-16T00:00:00Z",
            "--default-index",
            INDEX,
        ]
    )


def _verify_locks(uv_bin: Path, workspace: Path) -> None:
    workspace.mkdir()
    generated_build = workspace / "official-blender-mcp-build.lock"
    generated_runtime = workspace / "runtime-requirements.lock"
    _compile_lock(uv_bin, BUILD_INPUT, generated_build, "3.13.13")
    _compile_lock(uv_bin, RUNTIME_INPUT, generated_runtime, "3.13")
    if generated_build.read_bytes() != BUILD_LOCK.read_bytes():
        raise ValueError("committed build lock is stale")
    runtime = RUNTIME_LOCK.read_bytes()
    if generated_runtime.read_bytes() != runtime:
        raise ValueError("committed runtime lock is stale")
    validate_runtime_lock(runtime)


def _create_venv(uv_bin: Path, path: Path) -> Path:
    _run(
        [str(uv_bin), "venv", "--python", "3.13.13", "--no-python-downloads", str(path)]
    )
    return path / "bin/python"


def _install_lock(uv_bin: Path, python: Path, lock: Path) -> None:
    _run(
        [
            str(uv_bin),
            "pip",
            "install",
            "--python",
            str(python),
            "--require-hashes",
            "--only-binary",
            ":all:",
            "--no-deps",
            "--default-index",
            INDEX,
            "-r",
            str(lock),
        ]
    )


def _safe_zip_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or "\\" in name
        or path.parts[0].endswith(":")
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe ZIP entry: {name}")
    return path


def _normalize_zip(source: Path, target: Path, epoch: int) -> None:
    timestamp = datetime.fromtimestamp(max(epoch, 315532800), UTC)
    date_time = (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second // 2 * 2)
    entries: list[tuple[str, bytes, bool]] = []
    with zipfile.ZipFile(source) as archive:
        for item in archive.infolist():
            _safe_zip_name(item.filename)
            mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or stat.S_ISLNK(mode):
                raise ValueError(f"unsafe ZIP entry type: {item.filename}")
            is_dir = item.is_dir()
            entries.append((item.filename, b"" if is_dir else archive.read(item), is_dir))
    names = [name for name, _, _ in entries]
    if len(names) != len(set(names)):
        raise ValueError("duplicate ZIP entry")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content, is_dir in sorted(entries):
            info = zipfile.ZipInfo(name, date_time)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED if is_dir else zipfile.ZIP_DEFLATED
            info.external_attr = ((stat.S_IFDIR | 0o755) if is_dir else (stat.S_IFREG | 0o644)) << 16
            archive.writestr(info, content)


def _validate_source_metadata(source: Path) -> None:
    try:
        project = tomllib.loads((source / "pyproject.toml").read_text()).get("project")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("unexpected source metadata") from exc
    if type(project) is not dict or project.get("dependencies") != [
        "docutils",
        "mcp[cli]>=1.28.1,<3",
        "pyyaml",
    ]:
        raise ValueError("unexpected source metadata")


def _build_payloads(
    source: Path,
    blender_bin: Path,
    python: Path,
    output: Path,
    epoch: int,
) -> None:
    _validate_source_metadata(source / "mcp")
    raw = output.parent / f"{output.name}-raw"
    raw.mkdir()
    build_env = sanitized_environment()
    build_env["SOURCE_DATE_EPOCH"] = str(epoch)
    _run(
        [str(python), "-m", "build", "--wheel", "--no-isolation", "--outdir", str(raw)],
        cwd=source / "mcp",
        env=build_env,
    )
    wheels = list(raw.glob("*.whl"))
    if len(wheels) != 1 or wheels[0].name != ARTIFACTS[0][1]:
        raise ValueError("unexpected wheel output")
    raw_extension = raw / ARTIFACTS[1][1]
    _run(
        [
            str(blender_bin),
            "--command",
            "extension",
            "build",
            "--source-dir",
            str(source / "addon/blender_mcp_addon"),
            "--output-filepath",
            str(raw_extension),
        ],
        env=build_env,
    )
    output.mkdir()
    _normalize_zip(wheels[0], output / ARTIFACTS[0][1], epoch)
    _normalize_zip(raw_extension, output / ARTIFACTS[1][1], epoch)
    _run(validate_extension_command(blender_bin, output / ARTIFACTS[1][1]), env=build_env)
    shutil.rmtree(raw)


def _validate_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("wheel metadata is missing or duplicated")
        metadata = archive.read(metadata_names[0]).decode()
        dist_info = metadata_names[0].removesuffix("METADATA")
        wheel_metadata = archive.read(f"{dist_info}WHEEL").decode()
        entry_points = archive.read(f"{dist_info}entry_points.txt").decode()
    fields: dict[str, list[str]] = {}
    for line in metadata.splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields.setdefault(key, []).append(value)
    if (
        fields.get("Name") != ["blender-mcp"]
        or fields.get("Version") != ["1.0.0"]
        or fields.get("Requires-Python") != [">=3.10"]
        or fields.get("Requires-Dist")
        != ["docutils", "mcp[cli]<3,>=1.28.1", "pyyaml"]
        or "Root-Is-Purelib: true\n" not in wheel_metadata
        or "Tag: py3-none-any\n" not in wheel_metadata
        or entry_points != "[console_scripts]\nblender-mcp = blmcp:main\n"
    ):
        raise ValueError("unexpected wheel metadata")


def _validate_extension(extension: Path) -> None:
    with zipfile.ZipFile(extension) as archive:
        names = archive.namelist()
        manifests = [name for name in names if name == "blender_manifest.toml"]
        if manifests != ["blender_manifest.toml"]:
            raise ValueError("extension manifest is missing or nested")
        manifest = tomllib.loads(archive.read(manifests[0]).decode())
    if manifest.get("id") != "mcp" or manifest.get("version") != "1.0.0":
        raise ValueError("unexpected extension metadata")


def _probe_versions(uv_bin: Path, blender_bin: Path, python: Path) -> None:
    if _run([str(uv_bin), "--version"]).stdout.split()[1] != "0.12.2":
        raise ValueError("uv version is not 0.12.2")
    if not _run([str(blender_bin), "--version"]).stdout.startswith("Blender 5.2.0 LTS"):
        raise ValueError("Blender version is not 5.2.0 LTS")
    probe = "import importlib.metadata as m, json, platform; print(json.dumps([platform.python_version(), m.version('setuptools')]))"
    if json.loads(_run([str(python), "-I", "-c", probe]).stdout) != ["3.13.13", "80.9.0"]:
        raise ValueError("Python or setuptools build version is unexpected")


def _discover_catalog(uv_bin: Path, wheel: Path, workspace: Path) -> tuple[str, ...]:
    workspace.mkdir()
    python = _create_venv(uv_bin, workspace / "runtime")
    _install_lock(uv_bin, python, RUNTIME_LOCK)
    _run([str(uv_bin), "pip", "install", "--python", str(python), "--no-deps", str(wheel)])
    probe = """
import asyncio, importlib, json, pkgutil
import blmcp.tools as package
from mcp.server.fastmcp import FastMCP
server = FastMCP("catalog")
for _, name, _ in pkgutil.iter_modules(package.__path__):
    if not name.endswith("_toolcode") and not name.startswith("_template_"):
        module = importlib.import_module(f"blmcp.tools.{name}")
        if hasattr(module, "register"):
            module.register(server)
print(json.dumps([tool.name for tool in asyncio.run(server.list_tools())]))
"""
    result = _run([str(python), "-I", "-c", probe])
    return tuple(json.loads(result.stdout.splitlines()[-1]))


def _manifest(epoch: int, output: Path) -> ReleaseManifest:
    artifacts = []
    for role, filename in ARTIFACTS:
        content = (output / filename).read_bytes()
        artifacts.append(
            {
                "role": role,
                "filename": filename,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    value = {
        "schema_version": 2,
        "bundle_version": BUNDLE_VERSION,
        "platform": {"system": "Darwin", "machine": "arm64"},
        "upstream": {
            "url": "https://projects.blender.org/lab/blender_mcp.git",
            "commit": UPSTREAM_COMMIT,
        },
        "python": {"runtime_minor": "3.13", "build_tested": "3.13.13"},
        "blender": {"minimum": "5.2.0", "maximum_exclusive": "5.3.0", "tested": "5.2.0"},
        "server": {"distribution": "blender-mcp", "version": "1.0.0", "mcp_sdk": "1.28.1"},
        "extension": {"repository": "user_default", "id": "mcp", "version": "1.0.0"},
        "bridge": {"host": "localhost", "port": 9876},
        "build": {
            "source_date_epoch": epoch,
            "uv": "0.12.2",
            "python": "3.13.13",
            "blender": "5.2.0",
            "codex_tested": "0.148.0-alpha.9",
            "backend": {"name": "setuptools", "version": "80.9.0"},
            "index": INDEX,
        },
        "tools": list(TOOLS),
        "artifacts": artifacts,
    }
    raw = json.dumps(value, sort_keys=False, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
    (output / "manifest.json").write_bytes(raw)
    return parse_manifest(raw)


def _write_checksums(output: Path) -> None:
    names = ("manifest.json", *(filename for _, filename in ARTIFACTS))
    content = "".join(
        f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}\n" for name in names
    )
    (output / "SHA256SUMS").write_text(content, encoding="ascii")


def _validate_candidate(output: Path, blender_bin: Path) -> ReleaseManifest:
    if {path.name for path in output.iterdir()} != {
        "manifest.json",
        "SHA256SUMS",
        *(filename for _, filename in ARTIFACTS),
    }:
        raise ValueError("candidate has missing or extra files")
    manifest = parse_manifest((output / "manifest.json").read_bytes())
    for artifact in manifest.artifacts:
        content = (output / artifact.filename).read_bytes()
        if len(content) != artifact.size or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise ValueError(f"manifest artifact mismatch: {artifact.filename}")
    validate_runtime_lock((output / ARTIFACTS[2][1]).read_bytes())
    _validate_wheel(output / ARTIFACTS[0][1])
    _validate_extension(output / ARTIFACTS[1][1])
    _run(validate_extension_command(blender_bin, output / ARTIFACTS[1][1]))
    expected_lines = _write_checksum_text(output)
    if (output / "SHA256SUMS").read_text(encoding="ascii") != expected_lines:
        raise ValueError("candidate checksum file is invalid")
    return manifest


def _write_checksum_text(output: Path) -> str:
    return "".join(
        f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}\n"
        for name in ("manifest.json", *(filename for _, filename in ARTIFACTS))
    )


def _build_candidate(
    source_roots: tuple[Path, Path],
    blender_bin: Path,
    uv_bin: Path,
    candidate: Path,
    workspace: Path,
    epoch: int,
) -> ReleaseManifest:
    _verify_locks(uv_bin, workspace / "lock-check")
    build_python = _create_venv(uv_bin, workspace / "build-runtime")
    _install_lock(uv_bin, build_python, BUILD_LOCK)
    _probe_versions(uv_bin, blender_bin, build_python)
    first = workspace / "first"
    second = workspace / "second"
    _build_payloads(source_roots[0], blender_bin, build_python, first, epoch)
    _build_payloads(source_roots[1], blender_bin, build_python, second, epoch)
    for _, filename in ARTIFACTS[:2]:
        if (first / filename).read_bytes() != (second / filename).read_bytes():
            raise ValueError(f"non-reproducible payload: {filename}")
    candidate.mkdir()
    for _, filename in ARTIFACTS[:2]:
        shutil.copyfile(first / filename, candidate / filename)
    shutil.copyfile(RUNTIME_LOCK, candidate / ARTIFACTS[2][1])
    _validate_wheel(candidate / ARTIFACTS[0][1])
    _validate_extension(candidate / ARTIFACTS[1][1])
    catalog = _discover_catalog(uv_bin, candidate / ARTIFACTS[0][1], workspace / "catalog")
    if catalog != TOOLS:
        raise ValueError(f"unexpected tool catalog: {catalog}")
    _manifest(epoch, candidate)
    _write_checksums(candidate)
    return _validate_candidate(candidate, blender_bin)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_candidate(path: Path) -> None:
    for entry in sorted(path.iterdir()):
        metadata = entry.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"candidate entry is not a regular file: {entry.name}")
        fd = os.open(entry, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            if _source_identity(os.fstat(fd)) != _source_identity(metadata):
                raise ValueError(f"candidate changed before fsync: {entry.name}")
            os.fsync(fd)
            if _source_identity(os.fstat(fd)) != _source_identity(metadata):
                raise ValueError(f"candidate changed during fsync: {entry.name}")
        finally:
            os.close(fd)
    _fsync_directory(path)


def build_distribution(
    source: Path, blender_bin: Path, uv_bin: Path, output_dir: Path
) -> ReleaseManifest:
    output_dir = output_dir.absolute()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    candidate = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.candidate.", dir=output_dir.parent)
    )
    candidate.rmdir()
    try:
        with tempfile.TemporaryDirectory(prefix="blender-mcp-build.", dir="/private/tmp") as temp:
            workspace = Path(temp)
            source_roots, epoch = _extract_two_archives(source, workspace)
            manifest = _build_candidate(
                source_roots, blender_bin, uv_bin, candidate, workspace, epoch
            )
        _fsync_candidate(candidate)
        recovery = output_dir.parent / f".{output_dir.name}.recovery.{uuid.uuid4().hex}"
        had_output = output_dir.exists()
        if had_output:
            os.rename(output_dir, recovery)
        try:
            os.rename(candidate, output_dir)
            _fsync_directory(output_dir.parent)
        except Exception:
            if output_dir.exists():
                os.rename(output_dir, candidate)
            if had_output and recovery.exists():
                os.rename(recovery, output_dir)
            _fsync_directory(output_dir.parent)
            raise
        if recovery.exists():
            shutil.rmtree(recovery)
            _fsync_directory(output_dir.parent)
        print("tools=26")
        print("uv=0.12.2 python=3.13.13 blender=5.2.0 setuptools=80.9.0")
        return manifest
    except Exception:
        if candidate.exists():
            shutil.rmtree(candidate)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--uv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_distribution(args.source, args.blender, args.uv, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
