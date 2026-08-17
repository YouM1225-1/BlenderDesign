from __future__ import annotations

import argparse
import fcntl
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
from contextlib import contextmanager
from pathlib import Path
from typing import Any


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
        raise RuntimeError(
            "Codex config must be owned, non-symlink, and not group/world-writable"
        )
    return projection_parent, recovery_root


@contextmanager
def _codex_lock(codex_home: Path):
    lock_path = codex_home / ".blender-mcp-marketplace.lock"
    descriptor = os.open(
        lock_path,
        os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        value = os.fstat(descriptor)
        if (
            not stat.S_ISREG(value.st_mode)
            or value.st_uid != os.getuid()
            or stat.S_IMODE(value.st_mode) != 0o600
        ):
            raise RuntimeError("marketplace lock must be an owned private ordinary file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


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
        "archive", "--format=tar", reviewed_commit,
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
            result.append(
                (relative, "file", hashlib.sha256(path.read_bytes()).hexdigest())
            )
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
    others = {
        name: value for name, value in marketplaces.items() if name != MARKETPLACE_NAME
    }
    canonical = json.dumps(
        _normalize(others), sort_keys=True, separators=(",", ":")
    ).encode()
    return target_record, {
        "count": len(others),
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _atomic_write(path: Path, data: bytes) -> None:
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


def _register(
    projection: Path,
    recovery_root: Path,
    codex: Path,
    home: Path,
    codex_home: Path,
) -> Path:
    config = codex_home / "config.toml"
    recovery = Path(tempfile.mkdtemp(prefix="registration.", dir=recovery_root))
    recovery.chmod(0o700)
    before, non_target_before = _marketplace_snapshot(config)
    _atomic_json(recovery / "before.json", before)
    _atomic_json(recovery / "non-target-before.json", non_target_before)
    restore_lines = [
        f"Restore only marketplace {MARKETPLACE_NAME}; installer receipts are not required.",
        f"CODEX_BIN: {codex}",
        f"HOME: {home}",
        f"CODEX_HOME: {codex_home}",
        f"Remove the target with the recorded environment: plugin marketplace remove {MARKETPLACE_NAME}",
    ]
    if before["present"]:
        restore_lines.append(
            f"Then add the prior local source recorded in before.json: {before['source']}"
        )
    else:
        restore_lines.append(
            "before.json records that the target was previously absent; do not add it."
        )
    _atomic_write(recovery / "RESTORE.txt", ("\n".join(restore_lines) + "\n").encode())

    changed = before.get("source") != str(projection)
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
    projection_parent, recovery_root = _prepare_roots(home, codex_home)
    with _codex_lock(codex_home):
        projection = _materialize(
            projection_parent,
            private_git_dir,
            git_safe_home,
            args.reviewed_commit,
            trusted_checksums,
        )
        recovery = _register(projection, recovery_root, codex, home, codex_home)
    print(
        json.dumps(
            {
                "marketplace": MARKETPLACE_NAME,
                "projection": str(projection),
                "recovery": str(recovery),
            },
            sort_keys=True,
        )
    )


def _verify(args: argparse.Namespace) -> None:
    projection = Path(args.projection)
    recovery = Path(args.recovery)
    codex = Path(args.codex)
    home = Path(args.home)
    codex_home = Path(args.codex_home)
    _validate_secure_tree(projection)
    _private_owner_directory(recovery, os.getuid())
    _validate_plugin_cache(projection, codex_home)
    marketplaces_text = _codex(
        codex, home, codex_home, "plugin", "marketplace", "list", "--json"
    )
    marketplaces = json.loads(marketplaces_text)
    items = marketplaces.get("marketplaces") if type(marketplaces) is dict else None
    if type(items) is not list:
        raise RuntimeError("marketplace list JSON must contain a marketplaces array")
    marketplace_items = items
    matches = [
        item
        for item in items
        if type(item) is dict and item.get("name") == MARKETPLACE_NAME
    ]
    if len(matches) != 1 or matches[0].get("root") != str(projection):
        raise RuntimeError("normal marketplace list does not use the persistent projection")
    plugins_text = _codex(
        codex,
        home,
        codex_home,
        "plugin",
        "list",
        "--marketplace",
        MARKETPLACE_NAME,
        "--json",
    )
    plugins = json.loads(plugins_text)
    if type(plugins) is not dict or set(plugins) != {"installed", "available"}:
        raise RuntimeError("plugin list JSON has an unexpected schema")
    installed = plugins["installed"]
    available = plugins["available"]
    if type(installed) is not list or type(available) is not list:
        raise RuntimeError("plugin list installed and available must be arrays")
    items = installed + available
    if not all(type(item) is dict and type(item.get("name")) is str for item in items):
        raise RuntimeError("plugin list items must contain string names")
    if sum(item["name"] == PLUGIN_NAME for item in installed) != 1:
        raise RuntimeError("plugin list must contain exactly one installed target")
    non_target_items = [
        item
        for item in marketplace_items
        if type(item) is not dict or item.get("name") != MARKETPLACE_NAME
    ]
    non_target_fingerprint = hashlib.sha256(
        json.dumps(
            _normalize(non_target_items), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    _atomic_json(
        recovery / "marketplaces-after-cleanup.json",
        {
            "marketplace": MARKETPLACE_NAME,
            "non_target_count": len(non_target_items),
            "non_target_sha256": non_target_fingerprint,
            "root": str(projection),
            "status": "passed",
        },
    )
    _atomic_json(
        recovery / "plugins-after-cleanup.json",
        {
            "available_count": len(available),
            "installed_count": len(installed),
            "plugin": PLUGIN_NAME,
            "status": "passed",
        },
    )
    print(json.dumps({"marketplace": MARKETPLACE_NAME, "projection": str(projection)}))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--private-git-dir", required=True)
    prepare.add_argument("--git-safe-home", required=True)
    prepare.add_argument("--reviewed-commit", required=True)
    prepare.add_argument("--trusted-checksums", required=True)
    prepare.add_argument("--codex", required=True)
    prepare.add_argument("--home", required=True)
    prepare.add_argument("--codex-home", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--projection", required=True)
    verify.add_argument("--recovery", required=True)
    verify.add_argument("--codex", required=True)
    verify.add_argument("--home", required=True)
    verify.add_argument("--codex-home", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        _prepare(args)
    else:
        _verify(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"marketplace projection failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
