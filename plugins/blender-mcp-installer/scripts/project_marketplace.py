# ruff: noqa: E402 -- cache lease must precede installer imports
from __future__ import annotations

# BEGIN GENERATED ENTRY LEASE (from entry_lease.py; run generate_entry_preludes.py)
import atexit as _atexit
import fcntl as _fcntl
import hashlib as _hashlib
import os as _os
from pathlib import Path as _Path
import stat as _stat


def _entry_directory(path: _Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise SystemExit(75)
    fd = _os.open("/", _os.O_RDONLY | _os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = _os.open(part, _os.O_RDONLY | _os.O_DIRECTORY | _os.O_NOFOLLOW, dir_fd=fd)
            _os.close(fd)
            fd = child
        info = _os.fstat(fd)
        if info.st_uid != _os.getuid() or _stat.S_IMODE(info.st_mode) & 0o022:
            raise SystemExit(75)
        return fd
    except BaseException:
        _os.close(fd)
        raise


def _entry_lease() -> int | None:
    home = _Path(_os.environ.get("HOME", "/"))
    codex = _Path(_os.environ.get("CODEX_HOME", str(home / ".codex")))
    cache = codex / "plugins/cache/official-blender-mcp/blender-mcp-installer"
    script = _Path(__file__).absolute()
    if not script.is_relative_to(cache):
        return None
    relative = script.relative_to(cache)
    if len(relative.parts) < 2:
        raise SystemExit(75)
    version = cache / relative.parts[0]
    root_fd = _entry_directory(version)
    info = _os.fstat(root_fd)
    name = _hashlib.sha256(f"tree:{info.st_dev}:{info.st_ino}".encode()).hexdigest() + ".lock"
    usage_fd = _entry_directory(home / ".local/state/blender-mcp-installer/usage")
    lease_fd = _os.open(name, _os.O_RDWR | _os.O_NOFOLLOW, dir_fd=usage_fd)
    lease = _os.fstat(lease_fd)
    linked = _os.stat(name, dir_fd=usage_fd, follow_symlinks=False)
    if (
        not _stat.S_ISREG(lease.st_mode)
        or lease.st_uid != _os.getuid()
        or _stat.S_IMODE(lease.st_mode) != 0o600
        or lease.st_nlink != 1
        or (lease.st_dev, lease.st_ino) != (linked.st_dev, linked.st_ino)
    ):
        raise SystemExit(75)
    try:
        _fcntl.flock(lease_fd, _fcntl.LOCK_SH | _fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(75)
    check_fd = _entry_directory(version)
    after = _os.fstat(check_fd)
    if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino) or not script.is_file():
        raise SystemExit(75)
    for fd in (root_fd, usage_fd, check_fd):
        _os.close(fd)
    _atexit.register(_os.close, lease_fd)
    return lease_fd


_SCRIPT_USAGE_FD = _entry_lease()
# END GENERATED ENTRY LEASE


import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from contextlib import nullcontext
from dataclasses import replace
from uuid import UUID
from pathlib import Path
from typing import Any


from blender_mcp_installer.filesystem import InstallerError, NoOpFaultInjector, SafeRoot
from blender_mcp_installer.upgrade_cleanup import RollbackUnavailable, assert_rollback_available
from blender_mcp_installer.upgrade_discovery import (
    discover_candidates,
    read_proof,
    read_evidence,
    registration_scope,
)
from blender_mcp_installer.upgrade_handoff import (
    RuntimeInUse,
    LegacyHandoffRequired,
    begin_handoff,
    runtime_quiescence,
)
from blender_mcp_installer.upgrade_integration import (
    cancel_recovered_workflow,
    finalize_register_locked,
    profile_from_context,
)
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, mutation_locks
from blender_mcp_installer.upgrade_registration import inspect_registration
from blender_mcp_installer.upgrade_state import (
    UpgradeRoots,
    load_any_record,
    new_record,
    record_ids,
    save_record,
    update_record,
    uuid_text,
)

MARKETPLACE_NAME = "official-blender-mcp"
PLUGIN_NAME = "blender-mcp-installer"
REMOVE_MARKETPLACE = ("plugin", "marketplace", "remove", MARKETPLACE_NAME)


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _owner_directory(path: Path, uid: int, *, private: bool = False) -> None:
    current = _lstat(path)
    if current is None:
        parent = _lstat(path.parent)
        if parent is None or not stat.S_ISDIR(parent.st_mode) or parent.st_uid != uid:
            raise RuntimeError(f"unsafe parent for directory: {path}")
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
        current = path.lstat()
    if (
        not stat.S_ISDIR(current.st_mode)
        or current.st_uid != uid
        or stat.S_IMODE(current.st_mode) & 0o022
    ):
        raise RuntimeError(
            f"directory must be owned, non-symlink, and not group/world-writable: {path}"
        )
    if private:
        path.chmod(0o700)
        if stat.S_IMODE(path.lstat().st_mode) != 0o700:
            raise RuntimeError(f"directory must have mode 0700: {path}")


def _private_owner_directory(path: Path, uid: int) -> None:
    current = _lstat(path)
    if (
        current is None
        or not stat.S_ISDIR(current.st_mode)
        or current.st_uid != uid
        or stat.S_IMODE(current.st_mode) != 0o700
    ):
        raise RuntimeError(f"directory must be owned, non-symlink, and mode 0700: {path}")


def _prepare_roots(home: Path, codex_home: Path) -> tuple[Path, Path]:
    if not home.is_absolute() or not codex_home.is_absolute():
        raise RuntimeError("HOME and CODEX_HOME must be absolute")
    uid = os.getuid()
    _owner_directory(home, uid)
    for ancestor in (home / ".local", home / ".local/share", home / ".local/state"):
        _owner_directory(ancestor, uid)
    data_root = home / ".local/share/blender-mcp-installer"
    projection_parent = data_root / "marketplaces" / MARKETPLACE_NAME
    state_root = home / ".local/state/blender-mcp-installer"
    recovery_root = state_root / "marketplace-recovery"
    for private in (
        data_root,
        data_root / "marketplaces",
        projection_parent,
        state_root,
        recovery_root,
    ):
        _owner_directory(private, uid, private=True)
    _owner_directory(codex_home, uid)
    config = codex_home / "config.toml"
    config_stat = _lstat(config)
    if config_stat is not None and (
        not stat.S_ISREG(config_stat.st_mode)
        or config_stat.st_uid != uid
        or stat.S_IMODE(config_stat.st_mode) & 0o022
    ):
        raise RuntimeError("Codex config must be owned, non-symlink, and not group/world-writable")
    return projection_parent, recovery_root


def _private_git(
    private_git_dir: Path, git_safe_home: Path, *arguments: str
) -> subprocess.CompletedProcess[bytes]:
    command = [
        "/usr/bin/git",
        "--no-pager",
        "--no-replace-objects",
        f"--git-dir={private_git_dir}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={private_git_dir / 'hooks'}",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "diff.external=",
        *arguments,
    ]
    environment = {
        "HOME": str(git_safe_home),
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    return subprocess.run(command, check=True, capture_output=True, env=environment)


def _validate_private_git(private_git_dir: Path, git_safe_home: Path) -> None:
    uid = os.getuid()
    for directory in (
        private_git_dir,
        private_git_dir / "hooks",
        git_safe_home,
    ):
        _owner_directory(directory, uid)
    for empty_file in (
        private_git_dir / "config",
        private_git_dir / "info/attributes",
    ):
        value = _lstat(empty_file)
        if (
            value is None
            or not stat.S_ISREG(value.st_mode)
            or value.st_uid != uid
            or empty_file.stat().st_size
        ):
            raise RuntimeError(f"private Git boundary is invalid: {empty_file}")
    if any((private_git_dir / "hooks").iterdir()):
        raise RuntimeError("private Git hooks directory must be empty")


def _archive_projection(
    private_git_dir: Path,
    git_safe_home: Path,
    reviewed_commit: str,
    destination: Path,
) -> None:
    tree = _private_git(
        private_git_dir,
        git_safe_home,
        "ls-tree",
        "-rz",
        "-r",
        reviewed_commit,
        ".agents",
        "plugins/blender-mcp-installer",
    ).stdout
    for record in tree.rstrip(b"\0").split(b"\0"):
        if not record:
            continue
        metadata, _path = record.split(b"\t", 1)
        mode, object_type, _object_id = metadata.split(b" ", 2)
        if object_type != b"blob" or mode == b"120000":
            raise RuntimeError("marketplace projection may contain only ordinary blobs")

    git_command = [
        "/usr/bin/git",
        "--no-pager",
        "--no-replace-objects",
        f"--git-dir={private_git_dir}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={private_git_dir / 'hooks'}",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "diff.external=",
        "archive",
        "--format=tar",
        reviewed_commit,
        ".agents",
        "plugins/blender-mcp-installer",
    ]
    git_environment = {
        "HOME": str(git_safe_home),
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    git = subprocess.Popen(
        git_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=git_environment
    )
    assert git.stdout is not None
    tar = subprocess.run(
        ["/usr/bin/tar", "-x", "-C", str(destination)],
        stdin=git.stdout,
        capture_output=True,
    )
    git.stdout.close()
    git_stderr = git.stderr.read() if git.stderr is not None else b""
    git_returncode = git.wait()
    if git_returncode or tar.returncode:
        raise RuntimeError(
            f"trusted archive failed: git={git_returncode} tar={tar.returncode} "
            f"{git_stderr.decode(errors='replace')}{tar.stderr.decode(errors='replace')}"
        )


def _secure_tree(root: Path) -> None:
    uid = os.getuid()
    for path in (root, *root.rglob("*")):
        value = path.lstat()
        if stat.S_ISLNK(value.st_mode) or value.st_uid != uid:
            raise RuntimeError(f"projection contains an unsafe path: {path}")
        path.chmod(stat.S_IMODE(value.st_mode) & ~0o077)
        if stat.S_IMODE(path.lstat().st_mode) & 0o077:
            raise RuntimeError(f"projection path is not owner-only: {path}")
    root.chmod(0o700)


def _validate_secure_tree(root: Path) -> None:
    uid = os.getuid()
    _private_owner_directory(root, uid)
    for path in root.rglob("*"):
        value = path.lstat()
        if (
            stat.S_ISLNK(value.st_mode)
            or value.st_uid != uid
            or stat.S_IMODE(value.st_mode) & 0o077
        ):
            raise RuntimeError(f"projection contains an unsafe path: {path}")


def _tree_manifest(root: Path) -> list[tuple[str, str, int, str]]:
    result: list[tuple[str, str, int, str]] = []
    for path in (root, *root.rglob("*")):
        value = path.lstat()
        relative = "." if path == root else path.relative_to(root).as_posix()
        if stat.S_ISDIR(value.st_mode):
            result.append((relative, "directory", stat.S_IMODE(value.st_mode), ""))
        elif stat.S_ISREG(value.st_mode):
            result.append(
                (
                    relative,
                    "file",
                    stat.S_IMODE(value.st_mode),
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        else:
            raise RuntimeError(f"projection contains a non-ordinary path: {path}")
    return sorted(result)


def _content_manifest(root: Path) -> list[tuple[str, str, str]]:
    uid = os.getuid()
    result: list[tuple[str, str, str]] = []
    for path in (root, *root.rglob("*")):
        value = path.lstat()
        if (
            stat.S_ISLNK(value.st_mode)
            or value.st_uid != uid
            or stat.S_IMODE(value.st_mode) & 0o022
        ):
            raise RuntimeError(f"plugin cache contains an unsafe path: {path}")
        relative = "." if path == root else path.relative_to(root).as_posix()
        if stat.S_ISDIR(value.st_mode):
            result.append((relative, "directory", ""))
        elif stat.S_ISREG(value.st_mode):
            result.append((relative, "file", hashlib.sha256(path.read_bytes()).hexdigest()))
        else:
            raise RuntimeError(f"plugin cache contains a non-ordinary path: {path}")
    return sorted(result)


def _plugin_cache(projection: Path, codex_home: Path) -> Path:
    manifest_path = projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json"
    manifest = json.loads(manifest_path.read_text())
    version = manifest.get("version") if type(manifest) is dict else None
    if type(version) is not str or not re.fullmatch(r"[A-Za-z0-9.+-]+", version):
        raise RuntimeError("projected plugin version is invalid")
    return codex_home / "plugins/cache" / MARKETPLACE_NAME / PLUGIN_NAME / version


def _validate_plugin_cache(projection: Path, codex_home: Path) -> None:
    cache = _plugin_cache(projection, codex_home)
    if _lstat(cache) is None:
        raise RuntimeError("Codex did not materialize the reviewed plugin cache version")
    projected_plugin = projection / "plugins/blender-mcp-installer"
    if _content_manifest(cache) != _content_manifest(projected_plugin):
        raise RuntimeError("Codex plugin cache differs from the reviewed projection")


def _verify_checksums(root: Path, trusted_checksums: Path) -> None:
    bundle_root = root / "plugins/blender-mcp-installer/artifacts"
    materialized = bundle_root / "SHA256SUMS"
    if materialized.read_bytes() != trusted_checksums.read_bytes():
        raise RuntimeError("materialized checksum manifest differs from reviewed blob")
    subprocess.run(
        ["/usr/bin/shasum", "-a", "256", "-c", str(trusted_checksums)],
        cwd=bundle_root,
        check=True,
        capture_output=True,
    )


def _materialize(
    projection_parent: Path,
    private_git_dir: Path,
    git_safe_home: Path,
    reviewed_commit: str,
    trusted_checksums: Path,
) -> Path:
    destination = projection_parent / reviewed_commit
    stage = Path(tempfile.mkdtemp(prefix=".stage.", dir=projection_parent))
    stage.chmod(0o700)
    try:
        _archive_projection(private_git_dir, git_safe_home, reviewed_commit, stage)
        _secure_tree(stage)
        _verify_checksums(stage, trusted_checksums)
        if _lstat(destination) is not None:
            _validate_secure_tree(destination)
            if _tree_manifest(stage) != _tree_manifest(destination):
                raise RuntimeError("existing reviewed-commit projection differs")
            shutil.rmtree(stage)
        else:
            os.rename(stage, destination)
        _verify_checksums(destination, trusted_checksums)
        return destination
    except BaseException:
        if _lstat(stage) is not None:
            shutil.rmtree(stage)
        raise


def _normalize(value: Any) -> Any:
    if type(value) is dict:
        return {key: _normalize(value[key]) for key in sorted(value)}
    if type(value) is list:
        return [_normalize(item) for item in value]
    if value is None or type(value) in (bool, int, float, str):
        return value
    return str(value)


def _marketplace_snapshot(config: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    data = tomllib.loads(config.read_text()) if config.exists() else {}
    marketplaces = data.get("marketplaces", {})
    if type(marketplaces) is not dict:
        raise RuntimeError("Codex marketplaces config must be a table")
    target = marketplaces.get(MARKETPLACE_NAME)
    if target is None:
        target_record: dict[str, Any] = {"present": False}
    else:
        if type(target) is not dict:
            raise RuntimeError("target marketplace config must be a table")
        allowed = {"last_updated", "source", "source_type"}
        if not {"source", "source_type"} <= set(target) <= allowed:
            raise RuntimeError("target marketplace config has unsupported fields")
        if "last_updated" in target and type(target["last_updated"]) is not str:
            raise RuntimeError("target marketplace last_updated must be a string")
        source_type = target.get("source_type")
        source = target.get("source")
        if (
            source_type != "local"
            or type(source) is not str
            or not source.startswith("/")
            or "\n" in source
        ):
            raise RuntimeError("only a prior absolute local target can be restored")
        target_record = {
            "present": True,
            "entry": _normalize(target),
            "source_type": source_type,
            "source": source,
        }
    others = {name: value for name, value in marketplaces.items() if name != MARKETPLACE_NAME}
    canonical = json.dumps(_normalize(others), sort_keys=True, separators=(",", ":")).encode()
    return target_record, {
        "count": len(others),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _atomic_write(path: Path, data: bytes) -> None:
    _private_owner_directory(path.parent, os.getuid())
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "wb")
        descriptor = -1
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_write(path, (json.dumps(value, sort_keys=True) + "\n").encode())


def _codex(codex: Path, home: Path, codex_home: Path, *arguments: str) -> str:
    environment = os.environ.copy()
    environment.update(HOME=str(home), CODEX_HOME=str(codex_home))
    return subprocess.run(
        [str(codex), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    ).stdout


def _restore(
    codex: Path,
    home: Path,
    codex_home: Path,
    before: dict[str, Any],
    non_target_before: dict[str, Any],
) -> None:
    current, _ = _marketplace_snapshot(codex_home / "config.toml")
    if current["present"]:
        _codex(codex, home, codex_home, *REMOVE_MARKETPLACE)
    if before["present"]:
        _codex(
            codex,
            home,
            codex_home,
            "plugin",
            "marketplace",
            "add",
            before["source"],
        )
    restored, non_target_restored = _marketplace_snapshot(codex_home / "config.toml")
    restored_semantics = {
        key: restored[key] for key in ("present", "source_type", "source") if key in restored
    }
    before_semantics = {
        key: before[key] for key in ("present", "source_type", "source") if key in before
    }
    if restored_semantics != before_semantics or non_target_restored != non_target_before:
        raise RuntimeError("restored marketplace registration differs from prior state")


def _write_restore_instructions(
    recovery: Path, codex: Path, home: Path, codex_home: Path
) -> None:
    restore_lines = [
        "Read the upgrades journal before any recovery action; cleanup_pending/complete may retire local program rollback.",
        "Use project_marketplace.py restore with this recovery directory and recorded HOME/CODEX_HOME/CODEX_BIN.",
        "This operation restores only marketplace source. It does not restore the installed plugin version or cache.",
        f"CODEX_BIN: {codex}",
        f"HOME: {home}",
        f"CODEX_HOME: {codex_home}",
    ]
    _atomic_write(recovery / "RESTORE.txt", ("\n".join(restore_lines) + "\n").encode())


def _register(
    projection: Path,
    recovery_root: Path,
    codex: Path,
    home: Path,
    codex_home: Path,
    *,
    recovery_id: str,
) -> Path:
    config = codex_home / "config.toml"
    recovery: Path = recovery_root / ("registration." + uuid_text(recovery_id))
    if recovery.exists():
        _private_owner_directory(recovery, os.getuid())
        with SafeRoot.open(recovery, os.getuid(), recovery) as evidence:
            before, _ = read_proof(evidence, Path("before.json"))
            non_target_before, _ = read_proof(evidence, Path("non-target-before.json"))
        current, non_target_current = _marketplace_snapshot(config)
        if non_target_current != non_target_before:
            raise InstallerError("registration evidence conflicts with non-target changes")
        if current != before and current.get("source") != str(projection):
            raise InstallerError("target registration changed outside pending workflow")
    else:
        recovery.mkdir(mode=0o700)
        before, non_target_before = _marketplace_snapshot(config)
        _atomic_json(recovery / "before.json", before)
        _atomic_json(recovery / "non-target-before.json", non_target_before)
    _write_restore_instructions(recovery, codex, home, codex_home)

    current, _ = _marketplace_snapshot(config)
    changed = current.get("source") != str(projection)
    add_marketplace = ("plugin", "marketplace", "add", str(projection))
    add_plugin = ("plugin", "add", f"blender-mcp-installer@{MARKETPLACE_NAME}")
    try:
        if changed:
            if before["present"]:
                _codex(codex, home, codex_home, *REMOVE_MARKETPLACE)
            _codex(codex, home, codex_home, *add_marketplace)
        _codex(codex, home, codex_home, *add_plugin)
        _validate_plugin_cache(projection, codex_home)
        after, non_target_after = _marketplace_snapshot(config)
        _atomic_json(recovery / "after.json", after)
        _atomic_json(recovery / "non-target-after.json", non_target_after)
        if non_target_after != non_target_before:
            raise RuntimeError("non-target marketplace registration changed")
        if after.get("source") != str(projection):
            raise RuntimeError("target marketplace does not reference the projection")
    except BaseException as error:
        if changed:
            try:
                _restore(codex, home, codex_home, before, non_target_before)
            except BaseException as restore_error:
                raise RuntimeError(
                    f"marketplace replacement and restoration failed; evidence: {recovery}"
                ) from restore_error
        raise RuntimeError(
            f"marketplace replacement failed: {error}; evidence: {recovery}"
        ) from error
    return recovery


def _prepare(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", args.reviewed_commit):
        raise RuntimeError("reviewed commit must be 40 lowercase hex characters")
    home = Path(args.home)
    codex_home = Path(args.codex_home)
    private_git_dir = Path(args.private_git_dir)
    git_safe_home = Path(args.git_safe_home)
    trusted_checksums = Path(args.trusted_checksums)
    codex = Path(args.codex)
    if not all(
        path.is_absolute()
        for path in (
            home,
            codex_home,
            private_git_dir,
            git_safe_home,
            trusted_checksums,
            codex,
        )
    ):
        raise RuntimeError("all marketplace projection paths must be absolute")
    checksums_stat = _lstat(trusted_checksums)
    if (
        checksums_stat is None
        or not stat.S_ISREG(checksums_stat.st_mode)
        or checksums_stat.st_uid != os.getuid()
    ):
        raise RuntimeError("trusted checksum evidence must be an owned ordinary file")
    _validate_private_git(private_git_dir, git_safe_home)
    _private_git(
        private_git_dir,
        git_safe_home,
        "cat-file",
        "-e",
        f"{args.reviewed_commit}^{{commit}}",
    )
    projection_parent, _recovery_root = _prepare_roots(home, codex_home)
    roots = UpgradeRoots(home, codex_home)
    with mutation_locks(roots) as state:
        projection = _materialize(
            projection_parent,
            private_git_dir,
            git_safe_home,
            args.reviewed_commit,
            trusted_checksums,
        )
        if args.command == "upgrade":
            from blender_mcp_installer import cli

            args.expected_distribution_commit = args.reviewed_commit
            args._fault = NoOpFaultInjector()
            args.codex = Path(args.codex)
            with cli._context(args) as context:
                if (context.roots.home, context.roots.codex_home) != (roots.home, roots.codex_home):
                    raise InstallerError(
                        "full workflow roots differ from verified host environment"
                    )
                result = _run_workflow(args, state, roots, projection, context)
        else:
            result = _run_workflow(args, state, roots, projection)
    result.setdefault("marketplace", MARKETPLACE_NAME)
    result.setdefault("projection", str(projection))
    if "workflow_id" in result:
        result.setdefault(
            "recovery",
            str(roots.state / "marketplace-recovery" / ("registration." + result["workflow_id"])),
        )
    print(json.dumps(result, sort_keys=True))
    if result.get("status") == "cleanup_pending":
        raise SystemExit(3)


def _run_workflow(
    args: argparse.Namespace,
    state: SafeRoot,
    roots: UpgradeRoots,
    projection: Path,
    context: Any = None,
) -> dict[str, Any]:
    plugin = json.loads(
        (projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json").read_bytes()
    )
    bundle = json.loads(
        (projection / "plugins/blender-mcp-installer/artifacts/manifest.json").read_bytes()
    )
    desired = {
        "commit": args.reviewed_commit,
        "bundle_version": bundle["bundle_version"],
        "manifest_sha256": hashlib.sha256(
            (projection / "plugins/blender-mcp-installer/artifacts/manifest.json").read_bytes()
        ).hexdigest(),
        "plugin_version": plugin["version"],
        "projection": str(projection),
    }
    profile = None if context is None else profile_from_context(context)
    mode = "register" if context is None else "install"
    from blender_mcp_installer import cli
    from blender_mcp_installer.model import ReceiptStatus

    while True:
        inspection = None if context is None else cli._inspection(context)
        requested = getattr(args, "workflow_id", None)
        matches = []
        for identifier in record_ids(state):
            doc = load_any_record(state, roots, identifier, recover=True)
            if (
                doc is not None
                and doc["codex_home"] == str(roots.codex_home)
                and (
                    (requested is not None and doc["id"] == requested)
                    or (
                        requested is None
                        and doc["mode"] == mode
                        and doc["desired"] == desired
                        and doc["profile"] == profile
                        and doc["status"] in {"awaiting_verification", "cleanup_pending"}
                    )
                )
            ):
                if context is not None and doc["install_id"] is not None:
                    assert inspection is not None
                    try:
                        linked = cli.load_receipt(
                            context.roots.receipt(UUID(doc["install_id"])), context.roots
                        ).status
                    except (InstallerError, OSError, ValueError):
                        linked = None
                    eligible = (
                        {ReceiptStatus.INSTALLED}
                        if inspection.exact
                        else {ReceiptStatus.PREPARED, ReceiptStatus.ROLLBACK_PENDING}
                    )
                    if linked not in eligible:
                        if linked is ReceiptStatus.ROLLED_BACK:
                            cancel_recovered_workflow(state, context, doc["id"])
                        continue
                matches.append(doc)
        if len(matches) > 1 or (requested is not None and not matches):
            raise InstallerError("workflow selection is not unique")
        doc = matches[0] if matches else None
        if doc is not None and (
            doc["mode"] != mode
            or doc["desired"] != desired
            or doc["profile"] != profile
            or doc["status"] in {"complete", "cancelled"}
        ):
            raise InstallerError("workflow identity mismatch")
        try:
            inspect_registration(Path(args.codex), roots, desired)
            registration_exact = True
        except (InstallerError, subprocess.SubprocessError, OSError, ValueError):
            registration_exact = False
        if doc is None and registration_exact and (inspection is None or inspection.exact):
            migration = new_record(roots, mode, desired)
            migration["profile"] = profile
            if inspection is not None:
                if inspection.receipt_path is None:
                    raise InstallerError("exact installation lacks receipt identity")
                migration["install_id"] = str(UUID(inspection.receipt_path.stem))
            candidates, findings = discover_candidates(state, roots, migration)
            if not candidates:
                return {
                    "changed": False,
                    "no_op": True,
                    "projection": str(projection),
                    "unverified": findings,
                    "all_old_versions_removed": not findings,
                }
            doc = save_record(state, roots, None, migration)
            doc = update_record(
                state, roots, doc, registration={"id": doc["id"], "state": "prepared"}
            )
            recovery = roots.state / "marketplace-recovery" / ("registration." + doc["id"])
            recovery.mkdir(mode=0o700)
            before, others = _marketplace_snapshot(roots.codex_home / "config.toml")
            if before.get("source") != str(projection):
                raise InstallerError("registration changed during migration binding")
            for name, value in (
                ("before.json", before),
                ("after.json", before),
                ("non-target-before.json", others),
                ("non-target-after.json", others),
            ):
                _atomic_json(recovery / name, value)
            _write_restore_instructions(recovery, Path(args.codex), roots.home, roots.codex_home)
            doc = update_record(
                state, roots, doc, registration={"id": doc["id"], "state": "registered"}
            )
        barrier = (
            nullcontext(None)
            if context is None
            else runtime_quiescence(
                state,
                roots,
                context.roots.runtime,
                Path(args.codex),
                getattr(args, "handoff_id", None),
            )
        )
        install_error = None
        try:
            with barrier as handoff:
                if doc is None:
                    doc = new_record(roots, mode, desired)
                    doc["profile"] = profile
                    doc = save_record(state, roots, None, doc)
                if doc["status"] == "awaiting_verification":
                    if doc["registration"] is None or doc["registration"]["state"] != "registered":
                        doc = update_record(
                            state, roots, doc, registration={"id": doc["id"], "state": "prepared"}
                        )
                        try:
                            _register(
                                projection,
                                roots.state / "marketplace-recovery",
                                Path(args.codex),
                                roots.home,
                                roots.codex_home,
                                recovery_id=doc["id"],
                            )
                            inspected = inspect_registration(Path(args.codex), roots, desired)
                            ensure_usage_lock(state, inspected.cache.dev, inspected.cache.ino)
                        except BaseException:
                            update_record(
                                state, roots, doc, registration={"id": doc["id"], "state": "failed"}
                            )
                            raise
                        doc = update_record(
                            state, roots, doc, registration={"id": doc["id"], "state": "registered"}
                        )
                    if context is not None:
                        selected = replace(context, workflow_id=doc["id"])
                        try:
                            result = cli._changed_install_locked(
                                selected, args._fault, state, doc["id"], handoff
                            )
                        except (cli._RuntimeRecheck, RuntimeInUse, LegacyHandoffRequired):
                            raise
                        except Exception as error:
                            install_error = error
                        else:
                            return {
                                **result,
                                "workflow_id": doc["id"],
                                "projection": str(projection),
                            }
        except cli._RuntimeRecheck:
            cancel_recovered_workflow(state, context, doc["id"])
            # Retain marketplace/state locks, but reselect after releasing the old inode.
            continue
        if install_error is not None:
            cli._lifecycle_closed(selected)
            with runtime_quiescence(
                state,
                roots,
                selected.roots.runtime,
                Path(args.codex),
                getattr(args, "handoff_id", None),
            ):
                recovered = cli.recover_active(
                    selected.roots,
                    selected.source_bundle,
                    selected.blender,
                    NoOpFaultInjector(),
                    manifest_sha256=selected.manifest_sha256,
                )
                if recovered["recovered"]:
                    cancel_recovered_workflow(state, selected, doc["id"])
            raise install_error
        if context is None:
            registered_result: dict[str, Any] = finalize_register_locked(
                state, roots, doc["id"], Path(args.codex)
            )
            return registered_result
        return {
            "workflow_id": doc["id"],
            "projection": str(projection),
            "requires_blender_start": True,
            "status": doc["status"],
        }


def _finalize_registration(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    with mutation_locks(roots) as state:
        result = finalize_register_locked(state, roots, args.workflow_id, Path(args.codex))
    print(json.dumps(result, sort_keys=True))
    if result["status"] == "cleanup_pending":
        raise SystemExit(3)


def _begin_handoff(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    runtime = roots.home / ".local/share/blender-lab-mcp/runtime"
    with mutation_locks(roots) as state:
        result = begin_handoff(state, roots, runtime, Path(args.codex))
    print(json.dumps(result, sort_keys=True))


def _validate_restore_scope(
    state: SafeRoot, roots: UpgradeRoots, reference: Path, codex: Path
) -> None:
    records = [load_any_record(state, roots, identity) for identity in record_ids(state)]
    selected, _proofs = registration_scope(state, roots, reference, records)
    if selected != roots:
        raise InstallerError("registration recovery profile mismatch")
    raw, _proof = read_evidence(state, reference / "RESTORE.txt")
    bins = [
        line.removeprefix("CODEX_BIN: ")
        for line in raw.decode().splitlines()
        if line.startswith("CODEX_BIN: ")
    ]
    if bins != [str(codex)]:
        raise InstallerError("registration recovery Codex executable mismatch")


def _restore_evidence(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    recovery = Path(args.recovery)
    parent = roots.state / "marketplace-recovery"
    if recovery.parent != parent or not re.fullmatch(
        r"registration\.[A-Za-z0-9_-]+", recovery.name
    ):
        raise InstallerError("unsupported registration recovery path")
    reference_path = recovery.relative_to(roots.state)
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        fd = home.open_directory(roots.state.relative_to(roots.home))
    with SafeRoot(roots.state, os.getuid(), fd) as state:
        _validate_restore_scope(state, roots, reference_path, Path(args.codex))
        assert_rollback_available(state, roots, registration_ref=reference_path.as_posix())
    with mutation_locks(roots) as state:
        _validate_restore_scope(state, roots, reference_path, Path(args.codex))
        reference = reference_path.as_posix()
        assert_rollback_available(state, roots, registration_ref=reference)
        before, _proof = read_proof(state, recovery.relative_to(roots.state) / "before.json")
        others, _proof = read_proof(
            state, recovery.relative_to(roots.state) / "non-target-before.json"
        )
        _restore(Path(args.codex), roots.home, roots.codex_home, before, others)
    print(
        json.dumps(
            {"marketplace_source_restored": True, "plugin_version_restored": False}, sort_keys=True
        )
    )


def _verify(args: argparse.Namespace) -> None:
    roots = UpgradeRoots(Path(args.home), Path(args.codex_home))
    projection = Path(args.projection)
    _validate_secure_tree(projection)
    plugin = json.loads(
        (projection / "plugins/blender-mcp-installer/.codex-plugin/plugin.json").read_bytes()
    )
    manifest_raw = (
        projection / "plugins/blender-mcp-installer/artifacts/manifest.json"
    ).read_bytes()
    manifest = json.loads(manifest_raw)
    inspect_registration(
        Path(args.codex),
        roots,
        {
            "commit": projection.name,
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "bundle_version": manifest["bundle_version"],
            "plugin_version": plugin["version"],
            "projection": str(projection),
        },
    )
    if args.recovery is not None:
        recovery = Path(args.recovery)
        if recovery.parent != roots.state / "marketplace-recovery" or not re.fullmatch(
            r"registration\.[A-Za-z0-9_-]+", recovery.name
        ):
            raise InstallerError("unsupported registration recovery path")
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            fd = home.open_directory(roots.state.relative_to(roots.home))
        with SafeRoot(roots.state, os.getuid(), fd) as state:
            before, _proof = read_proof(
                state, recovery.relative_to(roots.state) / "non-target-before.json"
            )
        _target, current = _marketplace_snapshot(roots.codex_home / "config.toml")
        if current != before:
            raise InstallerError("non-target marketplace configuration changed")
    print(
        json.dumps(
            {
                "marketplace": MARKETPLACE_NAME,
                "projection": str(projection),
                "status": "passed",
                "read_only": True,
            },
            sort_keys=True,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "upgrade"):
        prepare = commands.add_parser(command)
        for name in (
            "private-git-dir",
            "git-safe-home",
            "reviewed-commit",
            "trusted-checksums",
            "codex",
            "home",
            "codex-home",
        ):
            prepare.add_argument("--" + name, required=True)
        prepare.add_argument("--workflow-id")
        if command == "upgrade":
            from blender_mcp_installer import cli

            prepare.add_argument("--bundle-root", required=True, type=cli._bundle_root)
            prepare.add_argument("--blender", required=True, type=cli._executable)
            prepare.add_argument("--uv", required=True, type=cli._executable)
            prepare.add_argument("--handoff-id")
            for flag in (
                "allow-extension-install",
                "allow-online-access",
                "allow-localhost-bridge",
                "approve-arbitrary-python",
            ):
                prepare.add_argument("--" + flag, required=True, action="store_true")
    verify = commands.add_parser("verify")
    for name in ("projection", "codex", "home", "codex-home"):
        verify.add_argument("--" + name, required=True)
    verify.add_argument("--recovery")
    for command in ("finalize", "begin-handoff", "restore"):
        command_parser = commands.add_parser(command)
        for name in ("codex", "home", "codex-home"):
            command_parser.add_argument("--" + name, required=True)
        if command == "finalize":
            command_parser.add_argument("--workflow-id", required=True)
        if command == "restore":
            command_parser.add_argument("--recovery", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    home = os.environ.get("HOME")
    codex_home = os.environ.get("CODEX_HOME", str(Path(home or "/") / ".codex"))
    if home != args.home or codex_home != args.codex_home:
        raise InstallerError("workflow roots differ from lease environment")
    handlers = {
        "prepare": _prepare,
        "upgrade": _prepare,
        "verify": _verify,
        "finalize": _finalize_registration,
        "begin-handoff": _begin_handoff,
        "restore": _restore_evidence,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeInUse, LegacyHandoffRequired, RollbackUnavailable) as exc:
        print(json.dumps({"error": exc.code, "reason": str(exc)}, sort_keys=True))
        raise SystemExit(1) from None
    except Exception as error:
        print(f"marketplace projection failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
