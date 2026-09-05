from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Iterator, Mapping, Sequence
from uuid import UUID, uuid4

from .blender_adapter import (
    BlenderAuthorizations,
    BlenderState,
    load_extension_payload,
    probe_blender_lifecycle,
    resolve_blender_paths,
    stage_blender_change,
    verify_blender_files,
)
from .bundle import (
    StagedBundle,
    VerifiedBundle,
    open_verified_bundle,
    verify_distribution_checkout,
)
from .codex_adapter import (
    CodexRollbackContext,
    ManagedCodexKeys,
    ManagedProfile,
    RollbackResult,
    RollbackState,
    desired_codex_values,
    preflight_codex_rollback,
    rollback_codex,
    stage_codex_config,
    verify_codex_effective,
    verify_codex_toml,
)
from .filesystem import (
    FaultInjector,
    InstallerError,
    InstallerLock,
    NoOpFaultInjector,
    RestoreState,
    SafeRoot,
    StagedFile,
    StagedTree,
    TargetRef,
    TreeRef,
    capture_file,
    capture_tree,
    conditional_remove_file,
    conditional_remove_tree,
    conditional_swap_file,
    create_deterministic_stage,
    forward_file,
    forward_tree,
    is_tree_cleanup_prefix,
    load_active,
    load_atomic_json_pair,
    load_pending,
    load_receipt,
    rename_excl,
    reconcile_atomic_json,
    restore_file,
    restore_tree,
    write_atomic_json,
)
from .model import (
    ActionKind,
    ActionState,
    ActiveSelector,
    BoundaryRole,
    FileImage,
    Image,
    ImageState,
    InstallRoots,
    ObjectKind,
    PendingSelector,
    Receipt,
    ReceiptAction,
    ReceiptStatus,
    ReceiptTarget,
    TargetRole,
    TreeImage,
    parse_receipt,
)
from .runtime import stage_runtime, verify_runtime
from .verification import (
    EXACT_CHECK_NAMES,
    HostCapabilities,
    InstallationInspection,
    OfficialMCPProbe,
    inspect_installation,
    probe_host,
    verify_live,
)


_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_ARTIFACT_SUFFIX = ("plugins", "blender-mcp-installer", "artifacts")
_SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class _ArgumentError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _ArgumentError


class _SelectorFault:
    def __init__(self, fault: FaultInjector, publication_point: str) -> None:
        self.fault = fault
        self.publication_point = publication_point

    def hit(self, point: str) -> None:
        self.fault.hit(point)
        if point == "after_json_parent_fsync":
            self.fault.hit(self.publication_point)


@dataclass(frozen=True)
class _Context:
    verified: VerifiedBundle
    source_bundle: StagedBundle
    manifest_sha256: str
    host: HostCapabilities
    blender: BlenderState
    roots: InstallRoots


@dataclass
class _Journal:
    root: SafeRoot
    roots: InstallRoots
    fault: FaultInjector
    receipt: Receipt
    image: FileImage

    @property
    def reference(self) -> TargetRef:
        return TargetRef(self.root, PurePath("receipts", f"{self.receipt.install_id}.json"))

    def write(self, receipt: Receipt) -> None:
        self.image = write_atomic_json(
            self.reference,
            self.image,
            receipt.to_dict(),
            receipt.install_id,
            fault=self.fault,
        )
        self.receipt = receipt

    def action(self, action: ReceiptAction) -> None:
        actions = list(self.receipt.actions)
        actions[action.ordinal] = action
        self.write(replace(self.receipt, actions=tuple(actions)))


def _executable(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("executable must be an absolute lexical path")
    try:
        info = path.lstat()
    except OSError as exc:
        raise argparse.ArgumentTypeError("executable does not exist") from exc
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
        raise argparse.ArgumentTypeError("executable must be a non-symlink executable file")
    return path


def _bundle_root(value: str) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or tuple(path.parts[-3:]) != _ARTIFACT_SUFFIX
        or not path.is_dir()
    ):
        raise argparse.ArgumentTypeError("bundle root must be the exact artifacts directory")
    return path


def _commit(value: str) -> str:
    if not _COMMIT.fullmatch(value):
        raise argparse.ArgumentTypeError("expected commit must be 40 lowercase hex characters")
    return value


def _receipt_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("receipt must be an absolute lexical path")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="install.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "install", "verify", "rollback"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--bundle-root", required=True, type=_bundle_root)
        subparser.add_argument("--expected-distribution-commit", required=True, type=_commit)
        subparser.add_argument("--blender", required=True, type=_executable)
        subparser.add_argument("--codex", required=True, type=_executable)
        subparser.add_argument("--uv", required=True, type=_executable)
        if command == "install":
            for flag in (
                "allow-extension-install",
                "allow-online-access",
                "allow-localhost-bridge",
                "approve-arbitrary-python",
            ):
                subparser.add_argument(f"--{flag}", action="store_true", required=True)
        if command in {"verify", "rollback"}:
            subparser.add_argument("--receipt", type=_receipt_path, required=command == "rollback")
    return parser


def _environment() -> dict[str, str]:
    try:
        home = os.environ["HOME"]
    except KeyError as exc:
        raise InstallerError("explicit installer profile is required") from exc
    values = {
        "HOME": home,
        "CODEX_HOME": os.environ.get("CODEX_HOME", str(Path(home) / ".codex")),
    }
    blender_names = (
        "BLENDER_USER_RESOURCES",
        "BLENDER_USER_CONFIG",
        "BLENDER_USER_EXTENSIONS",
    )
    supplied = tuple(name in os.environ for name in blender_names)
    if any(supplied) and not all(supplied):
        raise InstallerError("explicit installer profile is required")
    values.update({name: os.environ[name] for name in blender_names if name in os.environ})
    values.update(
        {
            "PATH": _SYSTEM_PATH,
            "BLENDER_MCP_HOST": "localhost",
            "BLENDER_MCP_PORT": "9876",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
        }
    )
    return values


def _resolve_python() -> Path:
    try:
        value = sys.executable
        if not isinstance(value, str):
            raise ValueError
        source = Path(value)
        if not source.is_absolute() or ".." in source.parts:
            raise ValueError
        path = _executable(str(source.resolve(strict=True)))
        if path.lstat().st_uid not in {0, os.getuid()}:
            raise ValueError
        return path
    except Exception as exc:
        raise InstallerError("local Python 3.13 probe failed") from exc


@contextmanager
def _context(args: argparse.Namespace) -> Iterator[_Context]:
    try:
        checkout = verify_distribution_checkout(
            args.bundle_root, args.expected_distribution_commit, subprocess.run
        )
        with open_verified_bundle(checkout) as verified:
            env = _environment()
            python = _resolve_python()
            paths = resolve_blender_paths(
                args.blender,
                env,
                lambda argv, *, cwd, env: subprocess.run(
                    argv,
                    cwd=cwd,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                ),
            )
            host = probe_host(args.blender, args.codex, args.uv, python, env)
            if (
                paths.version != host.blender_version
                or paths.architecture not in host.blender_arches
            ):
                raise InstallerError("Blender discovery does not match host probe")
            blender = BlenderState(
                paths.executable,
                (paths.architecture,),
                paths.executable,
                paths.architecture,
                paths.version,
                Path(env["HOME"]),
                paths.user_resources,
                paths.user_config,
                paths.user_config / "userpref.blend",
                paths.user_extensions,
                "user_default",
                paths.user_extensions / "user_default/mcp",
                None,
                None,
                False,
                False,
                None,
                None,
                None,
                None,
            )
            roots = InstallRoots.discover(
                Path(env["HOME"]),
                Path(env["CODEX_HOME"]),
                paths,
                source_distribution_root=checkout.repository_root,
                distribution_root=checkout.repository_root,
            )
            if roots.bundle_root != args.bundle_root.resolve():
                raise InstallerError("bundle root does not match derived paths")
            yield _Context(
                verified,
                StagedBundle(checkout.bundle_root, verified.manifest),
                next(
                    line[:64].decode("ascii")
                    for line in checkout.trusted_checksums.splitlines()
                    if line[66:] == b"manifest.json"
                ),
                host,
                blender,
                roots,
            )
    except InstallerError:
        raise
    except Exception as exc:
        raise InstallerError("trusted installer probe failed") from exc


def _host_facts(host: HostCapabilities, roots: InstallRoots) -> Mapping[str, object]:
    return MappingProxyType(
        {
            "home": str(roots.home),
            "codex_home": str(roots.codex_home),
            "blender_executable": str(host.blender_bin),
            "blender_architecture": roots.blender.architecture,
            "blender_version": roots.blender.version,
            "blender_user_resources": str(roots.blender.user_resources),
            "blender_user_config": str(roots.blender.user_config),
            "blender_user_extensions": str(roots.blender.user_extensions),
            "codex_version": host.codex_version,
            "uv_version": host.uv_version,
            "python_version": host.python_version,
        }
    )


def _image_hash(image: Image) -> str | None:
    return image.digest if isinstance(image, TreeImage) else image.sha256


def _target(
    role: TargetRole,
    path: Path,
    boundary: BoundaryRole,
    pre: Image,
    *,
    post: Image | None = None,
    recovery: Path | None = None,
) -> ReceiptTarget:
    return ReceiptTarget(
        role,
        path,
        boundary,
        pre,
        post,
        recovery,
        None if recovery is None else _image_hash(pre),
    )


def _replace_target(receipt: Receipt, role: TargetRole, **changes: object) -> Receipt:
    targets = tuple(
        replace(target, **changes) if target.role is role else target for target in receipt.targets
    )
    return replace(receipt, targets=targets)


def _action(
    ordinal: int,
    kind: ActionKind,
    state: ActionState,
    target: Path,
    stage: Path,
    recovery: Path | None,
    pre: Image,
    *,
    intended: Image | None = None,
    actual: Image | None = None,
    recovery_image: Image | None = None,
    rollback_intended: FileImage | None = None,
    rollback_displaced: FileImage | None = None,
) -> ReceiptAction:
    objects = {
        ActionKind.BUNDLE_STAGE: ObjectKind.BUNDLE,
        ActionKind.RUNTIME_TREE: ObjectKind.TREE,
        ActionKind.EXTENSION_TREE: ObjectKind.TREE,
        ActionKind.USERPREF_FILE: ObjectKind.FILE,
        ActionKind.CODEX_FILE: ObjectKind.CODEX,
    }
    roles = {
        ActionKind.RUNTIME_TREE: TargetRole.RUNTIME,
        ActionKind.EXTENSION_TREE: TargetRole.BLENDER_EXTENSION,
        ActionKind.USERPREF_FILE: TargetRole.BLENDER_USERPREF,
        ActionKind.CODEX_FILE: TargetRole.CODEX_CONFIG,
    }
    return ReceiptAction(
        ordinal,
        kind,
        objects[kind],
        state,
        roles.get(kind),
        target,
        stage.name,
        None if recovery is None else recovery.name,
        pre,
        intended,
        actual,
        recovery_image,
        rollback_intended,
        rollback_displaced,
    )


def _open_live_file(reference: TargetRef, image: FileImage) -> int | None:
    if image.state is ImageState.ABSENT:
        return None
    parent, name = reference.root.open_parent(reference.relative)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    return fd


@contextmanager
def _refs(roots: InstallRoots, state: SafeRoot) -> Iterator[dict[str, TargetRef]]:
    with ExitStack() as stack:
        data = stack.enter_context(SafeRoot.open(roots.data_root, os.getuid(), roots.data_root))
        codex = stack.enter_context(SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home))
        extensions = stack.enter_context(
            SafeRoot.open(
                roots.blender.user_extensions,
                os.getuid(),
                roots.blender.user_resources,
            )
        )
        config = stack.enter_context(
            SafeRoot.open(
                roots.blender.user_config,
                os.getuid(),
                roots.blender.user_resources,
            )
        )
        yield {
            "runtime": TreeRef(data, PurePath("runtime")),
            "extension": TreeRef(extensions, PurePath("user_default", "mcp")),
            "userpref": TargetRef(config, PurePath("userpref.blend")),
            "codex": TargetRef(codex, PurePath("config.toml")),
            "active": TargetRef(state, PurePath("active.json")),
            "pending": TargetRef(state, PurePath("pending.json")),
        }


def _selector(active: ActiveSelector | None, install_id: UUID, generation: int) -> ActiveSelector:
    return ActiveSelector(1, generation, install_id, f"{install_id}.json")


def _remove_pending(
    state: SafeRoot, roots: InstallRoots, pending: PendingSelector, fault: FaultInjector
) -> None:
    reference = TargetRef(state, PurePath("pending.json"))
    image = capture_file(state, reference.relative)
    conditional_remove_file(reference, image, (), fault)
    fault.hit("after_pending_remove")


def _pending_stages_absent(roots: InstallRoots, state: SafeRoot, install_id: UUID) -> bool:
    checks: tuple[tuple[SafeRoot, PurePath, bool], ...]
    with _refs(roots, state) as refs:
        checks = (
            (state, PurePath("stages", str(install_id), "bundle"), True),
            (refs["runtime"].root, PurePath(roots.runtime_stage(install_id).name), True),
            (refs["runtime"].root, PurePath(roots.runtime_recovery(install_id).name), True),
            (
                refs["extension"].root,
                PurePath("user_default", roots.extension_stage(install_id).name),
                True,
            ),
            (
                refs["extension"].root,
                PurePath("user_default", roots.extension_recovery(install_id).name),
                True,
            ),
            (refs["userpref"].root, PurePath(roots.userpref_stage(install_id).name), False),
            (refs["userpref"].root, PurePath(roots.userpref_recovery(install_id).name), False),
            (refs["codex"].root, PurePath(roots.codex_stage(install_id).name), False),
            (refs["codex"].root, PurePath(roots.codex_recovery(install_id).name), False),
            (refs["codex"].root, PurePath(roots.codex_rollback_stage(install_id).name), False),
        )
        return all(
            (capture_tree(root, relative) if tree else capture_file(root, relative)).state
            is ImageState.ABSENT
            for root, relative, tree in checks
        )


def _validate_pending_receipt(
    receipt: Receipt,
    pending: PendingSelector,
    roots: InstallRoots,
    bundle: StagedBundle,
    manifest_sha256: str,
    state: SafeRoot,
) -> None:
    if (
        receipt.status is not ReceiptStatus.PREPARED
        or receipt.install_id != pending.install_id
        or receipt.generation != pending.generation
        or receipt.parent_install_id
        != (None if pending.previous_active is None else pending.previous_active.install_id)
        or receipt.bundle.get("version") != bundle.manifest.bundle_version
        or receipt.bundle.get("manifest_sha256") != manifest_sha256
        or pending.manifest_sha256 != manifest_sha256
        or receipt.actions
        or not _pending_stages_absent(roots, state, pending.install_id)
    ):
        raise InstallerError("selector reconciliation conflict")
    with _refs(roots, state) as refs:
        by_role = {target.role: target for target in receipt.targets}
        physical: dict[TargetRole, Image] = {
            TargetRole.RUNTIME: capture_tree(refs["runtime"].root, refs["runtime"].relative),
            TargetRole.BLENDER_EXTENSION: capture_tree(
                refs["extension"].root, refs["extension"].relative
            ),
            TargetRole.BLENDER_USERPREF: capture_file(
                refs["userpref"].root, refs["userpref"].relative
            ),
            TargetRole.CODEX_CONFIG: capture_file(refs["codex"].root, refs["codex"].relative),
        }
    if any(
        by_role[role].pre != image or by_role[role].install_post is not None
        for role, image in physical.items()
    ):
        raise InstallerError("selector reconciliation conflict")


def _settle_pending_atomic_json(
    roots: InstallRoots, manifest_sha256: str, fault: FaultInjector
) -> None:
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        prefix = ".blender-mcp-installer."
        suffix = ".pending.json.tmp"
        names = tuple(
            name
            for name in os.listdir(state.fd)
            if name.startswith(prefix) and name.endswith(suffix)
        )
        if not names:
            return
        if len(names) != 1:
            raise InstallerError("atomic JSON reconciliation conflict")
        try:
            install_id = UUID(names[0][len(prefix) : -len(suffix)])
        except ValueError as exc:
            raise InstallerError("atomic JSON reconciliation conflict") from exc
        if install_id.version != 4 or str(install_id) not in names[0]:
            raise InstallerError("atomic JSON reconciliation conflict")
        reference = TargetRef(state, PurePath("pending.json"))
        live, stale = load_atomic_json_pair(reference, install_id)
        try:
            candidate = PendingSelector.from_dict(stale)
        except (TypeError, ValueError) as exc:
            raise InstallerError("atomic JSON reconciliation conflict") from exc
        if (
            live is not None
            or candidate.install_id != install_id
            or candidate.manifest_sha256 != manifest_sha256
        ):
            raise InstallerError("atomic JSON reconciliation conflict")
        reconcile_atomic_json(
            reference,
            ((None, candidate.to_dict()),),
            install_id,
            fault=fault,
        )


def _receipt_transition(old: Receipt, new: Receipt) -> bool:
    old_value = old.to_dict()
    new_value = new.to_dict()
    if old.install_id != new.install_id:
        return False
    differences = {key for key in old_value if old_value[key] != new_value[key]}
    if differences == {"actions"}:
        if len(new.actions) == len(old.actions) + 1:
            return new.actions[:-1] == old.actions and new.actions[-1].state is ActionState.PLANNED
        if len(new.actions) != len(old.actions):
            return False
        changed = [
            (before, after)
            for before, after in zip(old.actions, new.actions, strict=True)
            if before != after
        ]
        if len(changed) != 1:
            return False
        before, after = changed[0]
        allowed = {
            ActionState.PLANNED: {ActionState.STAGED},
            ActionState.STAGED: {
                ActionState.SWAPPED,
                ActionState.PUBLISHED,
                ActionState.RESTORING,
                ActionState.RESTORED,
            },
            ActionState.SWAPPED: {ActionState.PARKED, ActionState.RESTORING},
            ActionState.PARKED: {ActionState.COMPLETED, ActionState.RESTORING},
            ActionState.PUBLISHED: {ActionState.COMPLETED, ActionState.RESTORING},
            ActionState.COMPLETED: {
                ActionState.RESTORING,
                ActionState.RESTORED,
                ActionState.SEMANTIC_STAGED,
            },
            ActionState.SEMANTIC_STAGED: {ActionState.SEMANTIC_SWAPPED},
            ActionState.SEMANTIC_SWAPPED: {ActionState.RESTORING},
            ActionState.RESTORING: {ActionState.RESTORING, ActionState.RESTORED},
        }
        if before.kind is ActionKind.BUNDLE_STAGE:
            allowed = {
                ActionState.PLANNED: {ActionState.STAGED},
                ActionState.STAGED: {ActionState.CLEANED},
            }
        if after.state not in allowed.get(before.state, set()):
            return False
        delta = {key for key, value in before.to_dict().items() if value != after.to_dict()[key]}
        exact_deltas = {
            (ActionState.PLANNED, ActionState.STAGED): {"state", "intended_post"},
            (ActionState.STAGED, ActionState.SWAPPED): {"state", "actual_post"},
            (ActionState.STAGED, ActionState.PUBLISHED): {"state", "actual_post"},
            (ActionState.SWAPPED, ActionState.PARKED): {"state", "recovery_image"},
            (ActionState.PARKED, ActionState.COMPLETED): {"state"},
            (ActionState.PUBLISHED, ActionState.COMPLETED): {"state"},
            (ActionState.COMPLETED, ActionState.SEMANTIC_STAGED): {
                "state",
                "rollback_intended",
            },
            (ActionState.SEMANTIC_STAGED, ActionState.SEMANTIC_SWAPPED): {
                "state",
                "rollback_displaced",
            },
            (ActionState.SEMANTIC_SWAPPED, ActionState.RESTORING): {"state"},
            (ActionState.RESTORING, ActionState.RESTORING): {"recovery_image"},
            (ActionState.RESTORING, ActionState.RESTORED): {"state", "recovery_image"},
            (ActionState.STAGED, ActionState.CLEANED): {"state"},
        }
        if (
            before.kind is ActionKind.CODEX_FILE
            and before.state is ActionState.RESTORING
            and after.state is ActionState.RESTORED
            and before.rollback_intended is not None
            and before.pre.state is ImageState.ABSENT
        ):
            exact_deltas[(ActionState.RESTORING, ActionState.RESTORED)] = {"state"}
        if (
            after.state in {ActionState.RESTORING, ActionState.RESTORED}
            and (
                before.state,
                after.state,
            )
            not in exact_deltas
        ):
            allowed_restore = (
                ({"state", "actual_post"}, {"state", "actual_post", "recovery_image"})
                if before.state is ActionState.STAGED
                else ({"state"}, {"state", "recovery_image"})
            )
            return delta in allowed_restore
        return delta == exact_deltas.get((before.state, after.state))
    if differences == {"targets"}:
        changed = [
            (before, after)
            for before, after in zip(old.targets, new.targets, strict=True)
            if before != after
        ]
        if len(changed) != 1 or changed[0][0].install_post is not None:
            return False
        before, after = changed[0]
        delta = {key for key, value in before.to_dict().items() if value != after.to_dict()[key]}
        return (
            after.install_post is not None
            and delta in ({"install_post"}, {"install_post", "recovery_path", "recovery_hash"})
            and (after.recovery_path is None) == (after.recovery_hash is None)
        )
    if differences == {"status", "verification"}:
        old_verification = dict(old.verification)
        new_verification = dict(new.verification)
        old_configured = old_verification.pop("configured", None)
        new_configured = new_verification.pop("configured", None)
        return (
            old.status is ReceiptStatus.PREPARED
            and new.status is ReceiptStatus.INSTALLED
            and old_configured is False
            and new_configured is True
            and old_verification == new_verification
        )
    if differences == {"status"}:
        return (old.status, new.status) in {
            (ReceiptStatus.PREPARED, ReceiptStatus.ROLLBACK_PENDING),
            (ReceiptStatus.INSTALLED, ReceiptStatus.ROLLBACK_PENDING),
            (ReceiptStatus.ROLLBACK_PENDING, ReceiptStatus.ROLLED_BACK),
        }
    return False


def _settle_receipt_atomic_json(
    roots: InstallRoots,
    pending: PendingSelector,
    bundle: StagedBundle,
    manifest_sha256: str,
    state: SafeRoot,
    fault: FaultInjector,
) -> None:
    reference = TargetRef(state, PurePath("receipts", pending.receipt_basename))
    try:
        live_value, stale_value = load_atomic_json_pair(reference, pending.install_id)
    except (OSError, ValueError) as exc:
        raise InstallerError("selector reconciliation conflict") from exc
    if stale_value is None:
        return
    try:
        live = None if live_value is None else parse_receipt(live_value, roots)
        stale = parse_receipt(stale_value, roots)
    except (TypeError, ValueError) as exc:
        raise InstallerError("atomic JSON reconciliation conflict") from exc
    if live is None:
        old_value: Mapping[str, object] | None = None
        new = stale
    elif _receipt_transition(stale, live):
        old_value = stale.to_dict()
        new = live
    elif _receipt_transition(live, stale):
        old_value = live.to_dict()
        new = stale
    else:
        raise InstallerError("atomic JSON reconciliation conflict")
    _validate_pending_receipt(new, pending, roots, bundle, manifest_sha256, state)
    with _refs(roots, state) as refs:
        _preflight_rollback(roots, bundle, manifest_sha256, new, state, refs)
    reconcile_atomic_json(
        reference,
        ((old_value, new.to_dict()),),
        pending.install_id,
        fault=fault,
    )


def _settle_known_receipt_atomic_json(
    roots: InstallRoots,
    bundle: StagedBundle,
    manifest_sha256: str,
    install_id: UUID,
    state: SafeRoot,
    fault: FaultInjector,
) -> None:
    reference = TargetRef(state, PurePath("receipts", f"{install_id}.json"))
    live_value, stale_value = load_atomic_json_pair(reference, install_id)
    if stale_value is None:
        return
    try:
        live = parse_receipt(live_value, roots)
        stale = parse_receipt(stale_value, roots)
    except (TypeError, ValueError) as exc:
        raise InstallerError("atomic JSON reconciliation conflict") from exc
    if _receipt_transition(stale, live):
        old, new = stale, live
    elif _receipt_transition(live, stale):
        old, new = live, stale
    else:
        raise InstallerError("atomic JSON reconciliation conflict")
    with _refs(roots, state) as refs:
        _preflight_rollback(roots, bundle, manifest_sha256, new, state, refs)
    reconcile_atomic_json(
        reference,
        ((old.to_dict(), new.to_dict()),),
        install_id,
        fault=fault,
    )


def reconcile_selectors(
    roots: InstallRoots,
    bundle: StagedBundle,
    blender: BlenderState,
    fault: FaultInjector,
    *,
    manifest_sha256: str,
) -> None:
    del blender
    _settle_pending_atomic_json(roots, manifest_sha256, fault)
    try:
        pending = load_pending(roots.pending, roots)
    except Exception as exc:
        raise InstallerError("selector reconciliation conflict") from exc
    if pending is None:
        try:
            active = load_active(roots.active, roots)
        except Exception as exc:
            raise InstallerError("selector reconciliation conflict") from exc
        return
    new = ActiveSelector(1, pending.generation, pending.install_id, pending.receipt_basename)
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        _settle_receipt_atomic_json(roots, pending, bundle, manifest_sha256, state, fault)
        receipt_image = capture_file(state, PurePath("receipts", f"{pending.install_id}.json"))
    if receipt_image.state is ImageState.ABSENT:
        receipt = None
    else:
        try:
            receipt = load_receipt(roots.receipt(pending.install_id), roots)
        except Exception as exc:
            raise InstallerError("selector reconciliation conflict") from exc
    try:
        active = load_active(roots.active, roots)
    except Exception as exc:
        raise InstallerError("selector reconciliation conflict") from exc
    if active not in {new, pending.previous_active}:
        raise InstallerError("selector reconciliation conflict")
    if receipt is None:
        with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
            active_ref = TargetRef(state, PurePath("active.json"))
            _live, stale = load_atomic_json_pair(active_ref, pending.install_id)
            previous = TargetRef(
                state,
                PurePath("backups", str(pending.install_id), "previous-active.json"),
            )
            if (
                active != pending.previous_active
                or stale is not None
                or capture_file(state, previous.relative) != FileImage.absent()
                or pending.manifest_sha256 != manifest_sha256
                or not _pending_stages_absent(roots, state, pending.install_id)
            ):
                raise InstallerError("selector reconciliation conflict")
            _remove_pending(state, roots, pending, fault)
        return
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        _validate_pending_receipt(receipt, pending, roots, bundle, manifest_sha256, state)
        active_target = next(
            target for target in receipt.targets if target.role is TargetRole.ACTIVE_SELECTOR
        )
        active_image = capture_file(state, PurePath("active.json"))
        if not isinstance(active_target.pre, FileImage) or (
            active == pending.previous_active and active_image != active_target.pre
        ):
            raise InstallerError("selector reconciliation conflict")
        if active == new and (
            active_target.install_post is not None and active_target.install_post != active_image
        ):
            raise InstallerError("selector reconciliation conflict")
        retain = (
            None
            if pending.previous_active is None
            else TargetRef(
                state,
                PurePath("backups", str(pending.install_id), "previous-active.json"),
            )
        )
        if active == new:
            _active_value, active_stale = load_atomic_json_pair(
                TargetRef(state, PurePath("active.json")), pending.install_id
            )
            previous_image = (
                FileImage.absent() if retain is None else capture_file(state, retain.relative)
            )
            if pending.previous_active is None:
                valid_previous = (
                    active_target.pre == FileImage.absent()
                    and previous_image == FileImage.absent()
                    and active_stale is None
                )
            else:
                temp = TargetRef(
                    state,
                    PurePath(f".blender-mcp-installer.{pending.install_id}.active.json.tmp"),
                )
                temp_image = capture_file(state, temp.relative)
                valid_previous = isinstance(active_target.pre, FileImage) and (
                    previous_image == active_target.pre
                    or (
                        previous_image == FileImage.absent()
                        and temp_image == active_target.pre
                        and active_stale == pending.previous_active.to_dict()
                    )
                )
            if not valid_previous:
                raise InstallerError("selector reconciliation conflict")
        reconcile_atomic_json(
            TargetRef(state, PurePath("active.json")),
            (
                (
                    None if pending.previous_active is None else pending.previous_active.to_dict(),
                    new.to_dict(),
                ),
            ),
            pending.install_id,
            retain,
            fault=fault,
        )
    try:
        active = load_active(roots.active, roots)
    except Exception as exc:
        raise InstallerError("selector reconciliation conflict") from exc
    if active == new:
        with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
            active_target = next(
                target for target in receipt.targets if target.role is TargetRole.ACTIVE_SELECTOR
            )
            if not isinstance(active_target.pre, FileImage):
                raise InstallerError("selector reconciliation conflict")
            temp = TargetRef(
                state,
                PurePath(f".blender-mcp-installer.{pending.install_id}.active.json.tmp"),
            )
            stale = capture_file(state, temp.relative)
            retain = (
                None
                if pending.previous_active is None
                else TargetRef(
                    state,
                    PurePath("backups", str(pending.install_id), "previous-active.json"),
                )
            )
            active_ref = TargetRef(state, PurePath("active.json"))
            if stale.state is ImageState.PRESENT:
                if stale != active_target.pre or retain is None:
                    raise InstallerError("selector reconciliation conflict")
                write_atomic_json(
                    active_ref,
                    stale,
                    new.to_dict(),
                    pending.install_id,
                    retain,
                    fault=fault,
                )
            active_image = capture_file(state, active_ref.relative)
            receipt_ref = TargetRef(state, PurePath("receipts", pending.receipt_basename))
            receipt_image = capture_file(state, receipt_ref.relative)
            receipt = _replace_target(
                receipt,
                TargetRole.ACTIVE_SELECTOR,
                install_post=active_image,
                recovery_path=(
                    None
                    if pending.previous_active is None
                    else roots.previous_active(pending.install_id)
                ),
                recovery_hash=(
                    None if pending.previous_active is None else _image_hash(active_target.pre)
                ),
            )
            write_atomic_json(
                receipt_ref,
                receipt_image,
                receipt.to_dict(),
                pending.install_id,
                fault=fault,
            )
            _remove_pending(state, roots, pending, fault)
        return
    if active == pending.previous_active:
        with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
            active_ref = TargetRef(state, PurePath("active.json"))
            prior_image = capture_file(state, PurePath("active.json"))
            retain = (
                None
                if active is None
                else TargetRef(
                    state,
                    PurePath("backups", str(pending.install_id), "previous-active.json"),
                )
            )
            active_image = write_atomic_json(
                active_ref,
                prior_image,
                new.to_dict(),
                pending.install_id,
                retain,
                fault=_SelectorFault(
                    fault,
                    "after_active_publish" if active is None else "after_active_swap",
                ),
            )
            if active is not None:
                fault.hit("after_active_park")
            fault.hit("after_active_parent_fsync")
            receipt_ref = TargetRef(state, PurePath("receipts", pending.receipt_basename))
            receipt_image = capture_file(state, receipt_ref.relative)
            receipt = _replace_target(
                receipt,
                TargetRole.ACTIVE_SELECTOR,
                install_post=active_image,
                recovery_path=(
                    None if active is None else roots.previous_active(pending.install_id)
                ),
                recovery_hash=(None if active is None else _image_hash(prior_image)),
            )
            write_atomic_json(
                receipt_ref,
                receipt_image,
                receipt.to_dict(),
                pending.install_id,
                fault=fault,
            )
            _remove_pending(state, roots, pending, fault)
        return
    raise InstallerError("incomplete selector publication")


def _inspection(context: _Context) -> InstallationInspection:
    return inspect_installation(context.source_bundle, context.roots, context.blender, context.host)


def inspect(args: argparse.Namespace) -> dict[str, object]:
    with _context(args) as context:
        inspection = _inspection(context)
        checks = {name: getattr(inspection, name) for name in EXACT_CHECK_NAMES}
        return {
            "command": "inspect",
            "exact": inspection.exact,
            "checks": checks,
            "blender_checks": {
                "extension_files": inspection.extension_files,
                **inspection.preference_checks,
            },
            "host": {
                "platform": context.host.platform_system,
                "machine": context.host.platform_machine,
                "blender_version": context.host.blender_version,
                "codex_version": context.host.codex_version,
                "uv_version": context.host.uv_version,
                "python_version": context.host.python_version,
            },
            "managed_target_count": len(inspection.managed_targets),
            "active_install_id": inspection.active_install_id,
        }


def _lifecycle_closed(context: _Context) -> None:
    lifecycle = probe_blender_lifecycle(context.host.blender_bin, context.host.runner)
    if lifecycle.matching_selected_pids or not lifecycle.port_free:
        raise InstallerError("selected Blender must be closed and localhost port 9876 free")


def _ensure_mutation_roots(roots: InstallRoots) -> None:
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        for relative in (
            PurePath(".local", "state", "blender-mcp-installer"),
            PurePath(".local", "share", "blender-lab-mcp"),
        ):
            fd = home.open_directory(relative, create=True)
            os.close(fd)


def _publish_action(
    journal: _Journal,
    action: ReceiptAction,
    target: TargetRef,
    stage: StagedFile | StagedTree,
    recovery: TargetRef,
) -> ReceiptAction:
    tree = isinstance(stage, StagedTree)
    forward = forward_tree if tree else forward_file
    while action.state is not ActionState.COMPLETED:
        result = forward(target, action.pre, stage, recovery, journal.fault)
        state = ActionState(result.value)
        recovery_image: Image | None = None
        if (
            state in {ActionState.PARKED, ActionState.COMPLETED}
            and action.pre.state is ImageState.PRESENT
        ):
            recovery_image = action.pre
        action = replace(
            action,
            state=state,
            actual_post=action.intended_post,
            recovery_image=recovery_image,
        )
        journal.action(action)
        suffix = {
            ActionState.SWAPPED: "swap",
            ActionState.PARKED: "park",
            ActionState.PUBLISHED: "publish",
        }.get(state, state.value)
        journal.fault.hit(f"after_{action.kind.value}_{suffix}")
    return action


def _install_receipt(
    context: _Context,
    state: SafeRoot,
    refs: dict[str, TargetRef],
    active: ActiveSelector | None,
    install_id: UUID,
    generation: int,
) -> Receipt:
    runtime_pre = capture_tree(refs["runtime"].root, refs["runtime"].relative)
    extension_pre = capture_tree(refs["extension"].root, refs["extension"].relative)
    userpref_pre = capture_file(refs["userpref"].root, refs["userpref"].relative)
    codex_pre = capture_file(refs["codex"].root, refs["codex"].relative)
    active_pre = capture_file(state, PurePath("active.json"))
    return Receipt(
        1,
        install_id,
        generation,
        None if active is None else active.install_id,
        ReceiptStatus.PREPARED,
        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        MappingProxyType(
            {
                "version": context.verified.manifest.bundle_version,
                "manifest_sha256": context.manifest_sha256,
            }
        ),
        _host_facts(context.host, context.roots),
        MappingProxyType({"all_four_collected_for_this_workflow": True}),
        (
            _target(TargetRole.RUNTIME, context.roots.runtime, BoundaryRole.DATA_ROOT, runtime_pre),
            _target(
                TargetRole.BLENDER_EXTENSION,
                context.roots.extension_target,
                BoundaryRole.BLENDER_EXTENSIONS,
                extension_pre,
            ),
            _target(
                TargetRole.BLENDER_USERPREF,
                context.roots.userpref_target,
                BoundaryRole.BLENDER_CONFIG,
                userpref_pre,
            ),
            _target(
                TargetRole.CODEX_CONFIG,
                context.roots.codex_config,
                BoundaryRole.CODEX_HOME,
                codex_pre,
            ),
            _target(
                TargetRole.ACTIVE_SELECTOR,
                context.roots.active,
                BoundaryRole.STATE_ROOT,
                active_pre,
            ),
        ),
        (),
        MappingProxyType({"configured": False, "live": "not_run"}),
    )


def _planned(
    journal: _Journal,
    kind: ActionKind,
    target: Path,
    stage: Path,
    recovery: Path | None,
    pre: Image,
) -> ReceiptAction:
    action = _action(
        len(journal.receipt.actions),
        kind,
        ActionState.PLANNED,
        target,
        stage,
        recovery,
        pre,
    )
    journal.write(replace(journal.receipt, actions=(*journal.receipt.actions, action)))
    journal.fault.hit(f"after_{kind.value}_planned")
    return action


def _stage_blender_actions(
    context: _Context,
    journal: _Journal,
    state: SafeRoot,
    refs: dict[str, TargetRef],
    staged_bundle: StagedBundle,
) -> tuple[ReceiptAction, ReceiptAction]:
    roots = context.roots
    extension_pre = next(
        t.pre for t in journal.receipt.targets if t.role is TargetRole.BLENDER_EXTENSION
    )
    userpref_pre = next(
        t.pre for t in journal.receipt.targets if t.role is TargetRole.BLENDER_USERPREF
    )
    extension_action = _planned(
        journal,
        ActionKind.EXTENSION_TREE,
        roots.extension_target,
        roots.extension_stage(journal.receipt.install_id),
        roots.extension_recovery(journal.receipt.install_id),
        extension_pre,
    )
    userpref_action = _planned(
        journal,
        ActionKind.USERPREF_FILE,
        roots.userpref_target,
        roots.userpref_stage(journal.receipt.install_id),
        roots.userpref_recovery(journal.receipt.install_id),
        userpref_pre,
    )
    work = roots.state_root / "stages" / str(journal.receipt.install_id) / "blender-work"
    change = stage_blender_change(
        context.blender,
        staged_bundle.extension_path,
        work,
        BlenderAuthorizations(True, True, True, True),
        context.host.runner,
    )
    with ExitStack() as stack:
        extension_source = stack.enter_context(
            SafeRoot.open(work / "resources/extensions/user_default", os.getuid(), work)
        )
        userpref_source = stack.enter_context(
            SafeRoot.open(work / "resources/config", os.getuid(), work)
        )
        extension_stage_root = stack.enter_context(
            SafeRoot.open(
                roots.extension_target.parent,
                os.getuid(),
                roots.blender.user_resources,
            )
        )
        userpref_stage_root = refs["userpref"].root
        rename_excl(
            extension_source,
            "mcp",
            extension_stage_root,
            roots.extension_stage(journal.receipt.install_id).name,
            journal.fault,
        )
        rename_excl(
            userpref_source,
            "userpref.blend",
            userpref_stage_root,
            roots.userpref_stage(journal.receipt.install_id).name,
            journal.fault,
        )
    with SafeRoot.open(work.parent, os.getuid(), roots.state_root) as parent:
        work_ref = TreeRef(parent, PurePath(work.name))
        conditional_remove_tree(work_ref, work_ref.capture(), (), NoOpFaultInjector())
    extension_stage = StagedTree(
        refs["extension"].root,
        PurePath("user_default", roots.extension_stage(journal.receipt.install_id).name),
        change.extension_image,
    )
    userpref_stage = StagedFile(
        refs["userpref"].root,
        PurePath(roots.userpref_stage(journal.receipt.install_id).name),
        change.userpref_image,
    )
    extension_action = replace(
        extension_action, state=ActionState.STAGED, intended_post=change.extension_image
    )
    journal.action(extension_action)
    userpref_action = replace(
        userpref_action, state=ActionState.STAGED, intended_post=change.userpref_image
    )
    journal.action(userpref_action)
    journal.fault.hit("after_extension_tree_stage")
    journal.fault.hit("after_userpref_file_stage")
    extension_action = _publish_action(
        journal,
        extension_action,
        refs["extension"],
        extension_stage,
        TreeRef(
            refs["extension"].root,
            PurePath("user_default", roots.extension_recovery(journal.receipt.install_id).name),
        ),
    )
    userpref_action = _publish_action(
        journal,
        userpref_action,
        refs["userpref"],
        userpref_stage,
        TargetRef(
            refs["userpref"].root,
            PurePath(roots.userpref_recovery(journal.receipt.install_id).name),
        ),
    )
    return extension_action, userpref_action


def _cleanup_bundle(journal: _Journal, state: SafeRoot) -> None:
    actions = [a for a in journal.receipt.actions if a.kind is ActionKind.BUNDLE_STAGE]
    if not actions:
        return
    action = actions[0]
    if action.state is ActionState.CLEANED:
        reference = TreeRef(state, PurePath("stages", str(journal.receipt.install_id), "bundle"))
        if reference.capture() != TreeImage.absent():
            raise InstallerError("bundle stage recovery conflict")
        return
    if action.state is not ActionState.STAGED or not isinstance(action.intended_post, TreeImage):
        raise InstallerError("bundle stage recovery conflict")
    reference = TreeRef(state, PurePath("stages", str(journal.receipt.install_id), "bundle"))
    conditional_remove_tree(reference, action.intended_post, (), journal.fault)
    journal.action(replace(action, state=ActionState.CLEANED))
    journal.fault.hit("after_bundle_stage_cleanup")


def _changed_install(context: _Context, fault: FaultInjector) -> dict[str, object]:
    roots = context.roots
    _ensure_mutation_roots(roots)
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        with InstallerLock.acquire(state):
            reconcile_selectors(
                roots,
                context.source_bundle,
                context.blender,
                fault,
                manifest_sha256=context.manifest_sha256,
            )
            inspection = _inspection(context)
            if not inspection.exact:
                _lifecycle_closed(context)
            recovery = recover_active(
                roots,
                context.source_bundle,
                context.blender,
                fault,
                manifest_sha256=context.manifest_sha256,
            )
            if not inspection.exact and recovery["recovered"]:
                inspection = _inspection(context)
            context = replace(
                context, blender=getattr(inspection, "blender_state", context.blender)
            )
            if inspection.exact:
                assert inspection.receipt_path is not None
                return {
                    "command": "install",
                    "changed": False,
                    "no_op": True,
                    "bundle_version": context.verified.manifest.bundle_version,
                    "receipt": str(inspection.receipt_path),
                    "requires_blender_start": True,
                }
            active = load_active(roots.active, roots)
            generation = 1 if active is None else active.generation + 1
            install_id = uuid4()
            for relative in (
                PurePath("receipts"),
                PurePath("backups", str(install_id)),
                PurePath("stages", str(install_id)),
            ):
                fd = state.open_directory(relative, create=True)
                os.close(fd)
            with _refs(roots, state) as refs:
                receipt = _install_receipt(context, state, refs, active, install_id, generation)
                pending = PendingSelector(
                    1,
                    generation,
                    install_id,
                    f"{install_id}.json",
                    context.manifest_sha256,
                    active,
                )
                pending_image = write_atomic_json(
                    refs["pending"],
                    capture_file(state, PurePath("pending.json")),
                    pending.to_dict(),
                    install_id,
                    fault=fault,
                )
                del pending_image
                fault.hit("after_pending_publish")
                journal = _Journal(
                    state,
                    roots,
                    fault,
                    receipt,
                    FileImage.absent(),
                )
                journal.write(receipt)
                fault.hit("after_receipt_publish")
                new_active = _selector(active, install_id, generation)
                prior_image = capture_file(state, PurePath("active.json"))
                retain = (
                    None
                    if active is None
                    else TargetRef(
                        state,
                        PurePath("backups", str(install_id), "previous-active.json"),
                    )
                )
                active_image = write_atomic_json(
                    refs["active"],
                    prior_image,
                    new_active.to_dict(),
                    install_id,
                    retain,
                    fault=_SelectorFault(
                        fault,
                        "after_active_publish" if active is None else "after_active_swap",
                    ),
                )
                if active is not None:
                    fault.hit("after_active_park")
                fault.hit("after_active_parent_fsync")
                receipt = _replace_target(
                    journal.receipt,
                    TargetRole.ACTIVE_SELECTOR,
                    install_post=active_image,
                    recovery_path=None if active is None else roots.previous_active(install_id),
                    recovery_hash=None if active is None else _image_hash(prior_image),
                )
                journal.write(receipt)
                _remove_pending(state, roots, pending, fault)
                bundle_action = _planned(
                    journal,
                    ActionKind.BUNDLE_STAGE,
                    roots.bundle_stage(install_id),
                    roots.bundle_stage(install_id),
                    None,
                    TreeImage.absent(),
                )
                staged_bundle = context.verified.materialize(roots.bundle_stage(install_id))
                bundle_image = capture_tree(state, PurePath("stages", str(install_id), "bundle"))
                bundle_action = replace(
                    bundle_action, state=ActionState.STAGED, intended_post=bundle_image
                )
                journal.action(bundle_action)
                fault.hit("after_bundle_stage_stage")

                runtime_pre = next(
                    target.pre
                    for target in journal.receipt.targets
                    if target.role is TargetRole.RUNTIME
                )
                runtime_action = _planned(
                    journal,
                    ActionKind.RUNTIME_TREE,
                    roots.runtime,
                    roots.runtime_stage(install_id),
                    roots.runtime_recovery(install_id),
                    runtime_pre,
                )
                runtime_stage = create_deterministic_stage(
                    refs["runtime"].root,
                    roots.runtime_stage(install_id).name,
                    TreeImage.absent(),
                    fault,
                )
                assert isinstance(runtime_stage, StagedTree)
                profile = ManagedProfile(
                    roots.home,
                    roots.blender.user_resources,
                    roots.blender.user_config,
                    roots.blender.user_extensions,
                    roots.blender.executable,
                )
                try:
                    runtime_post = stage_runtime(
                        staged_bundle,
                        context.host.uv_bin,
                        context.host.python_bin,
                        profile,
                        runtime_stage,
                        context.host.runner,
                    )
                except Exception as exc:
                    runtime_post = runtime_stage.capture()
                    if runtime_post.state is not ImageState.PRESENT or (
                        runtime_post.dev,
                        runtime_post.ino,
                        runtime_post.uid,
                        runtime_post.mode,
                    ) != (
                        runtime_stage.image.dev,
                        runtime_stage.image.ino,
                        runtime_stage.image.uid,
                        runtime_stage.image.mode,
                    ):
                        raise InstallerError("runtime stage identity changed") from exc
                    runtime_action = replace(
                        runtime_action,
                        state=ActionState.STAGED,
                        intended_post=runtime_post,
                    )
                    journal.action(runtime_action)
                    raise
                runtime_stage = runtime_stage.with_image(runtime_post)
                runtime_action = replace(
                    runtime_action, state=ActionState.STAGED, intended_post=runtime_post
                )
                journal.action(runtime_action)
                fault.hit("after_runtime_tree_stage")
                runtime_action = _publish_action(
                    journal,
                    runtime_action,
                    refs["runtime"],
                    runtime_stage,
                    TreeRef(
                        refs["runtime"].root,
                        PurePath(roots.runtime_recovery(install_id).name),
                    ),
                )
                journal.write(
                    _replace_target(
                        journal.receipt,
                        TargetRole.RUNTIME,
                        install_post=runtime_post,
                        recovery_path=(
                            roots.runtime_recovery(install_id)
                            if runtime_pre.state is ImageState.PRESENT
                            else None
                        ),
                        recovery_hash=(
                            _image_hash(runtime_pre)
                            if runtime_pre.state is ImageState.PRESENT
                            else None
                        ),
                    )
                )

                extension_action, userpref_action = _stage_blender_actions(
                    context, journal, state, refs, staged_bundle
                )
                for role, action, recovery in (
                    (
                        TargetRole.BLENDER_EXTENSION,
                        extension_action,
                        roots.extension_recovery(install_id),
                    ),
                    (
                        TargetRole.BLENDER_USERPREF,
                        userpref_action,
                        roots.userpref_recovery(install_id),
                    ),
                ):
                    journal.write(
                        _replace_target(
                            journal.receipt,
                            role,
                            install_post=action.actual_post,
                            recovery_path=(
                                recovery if action.pre.state is ImageState.PRESENT else None
                            ),
                            recovery_hash=(
                                _image_hash(action.pre)
                                if action.pre.state is ImageState.PRESENT
                                else None
                            ),
                        )
                    )

                codex_pre = next(
                    target.pre
                    for target in journal.receipt.targets
                    if target.role is TargetRole.CODEX_CONFIG
                )
                codex_action = _planned(
                    journal,
                    ActionKind.CODEX_FILE,
                    roots.codex_config,
                    roots.codex_stage(install_id),
                    roots.codex_recovery(install_id),
                    codex_pre,
                )
                codex_stage = create_deterministic_stage(
                    refs["codex"].root,
                    roots.codex_stage(install_id).name,
                    FileImage.absent(),
                    fault,
                )
                assert isinstance(codex_stage, StagedFile)
                desired = desired_codex_values(
                    roots.runtime / "bin/blender-mcp-managed",
                    profile,
                    context.verified.manifest.tools,
                )
                live_fd = _open_live_file(refs["codex"], codex_pre)
                try:
                    codex_change = stage_codex_config(
                        live_fd,
                        codex_pre,
                        desired,
                        roots.runtime / "bin/python",
                        codex_stage,
                    )
                finally:
                    if live_fd is not None:
                        os.close(live_fd)
                codex_action = replace(
                    codex_action,
                    state=ActionState.STAGED,
                    intended_post=codex_change.post,
                )
                journal.action(codex_action)
                fault.hit("after_codex_file_stage")
                codex_action = _publish_action(
                    journal,
                    codex_action,
                    refs["codex"],
                    codex_change.stage,
                    TargetRef(
                        refs["codex"].root,
                        PurePath(roots.codex_recovery(install_id).name),
                    ),
                )
                journal.write(
                    _replace_target(
                        journal.receipt,
                        TargetRole.CODEX_CONFIG,
                        install_post=codex_action.actual_post,
                        recovery_path=(
                            roots.codex_recovery(install_id)
                            if codex_pre.state is ImageState.PRESENT
                            else None
                        ),
                        recovery_hash=(
                            _image_hash(codex_pre)
                            if codex_pre.state is ImageState.PRESENT
                            else None
                        ),
                    )
                )

                verify_runtime(
                    refs["runtime"], staged_bundle.manifest, profile, context.host.runner
                )
                fresh_blender = getattr(_inspection(context), "blender_state", context.blender)
                if not isinstance(extension_action.actual_post, TreeImage):
                    raise InstallerError("invalid extension postimage")
                verify_blender_files(
                    fresh_blender,
                    load_extension_payload(staged_bundle.extension_path),
                    extension_action.actual_post,
                )
                verify_codex_toml(roots.codex_config.read_bytes(), desired)
                verify_codex_effective(context.host.codex_bin, desired, context.host.env)
                journal.write(
                    replace(
                        journal.receipt,
                        status=ReceiptStatus.INSTALLED,
                        verification=MappingProxyType({"configured": True, "live": "not_run"}),
                    )
                )
                fault.hit("after_receipt_installed")
                _cleanup_bundle(journal, state)
                return {
                    "command": "install",
                    "changed": True,
                    "no_op": False,
                    "bundle_version": staged_bundle.manifest.bundle_version,
                    "receipt": str(roots.receipt(install_id)),
                    "requires_blender_start": True,
                }


def install(args: argparse.Namespace) -> dict[str, object]:
    fault = getattr(args, "_fault", NoOpFaultInjector())
    with _context(args) as context:
        try:
            return _changed_install(context, fault)
        except Exception as exc:
            _lifecycle_closed(context)
            try:
                _ensure_mutation_roots(context.roots)
                with SafeRoot.open(
                    context.roots.state_root,
                    os.getuid(),
                    context.roots.state_root,
                ) as state:
                    with InstallerLock.acquire(state):
                        recover_active(
                            context.roots,
                            context.source_bundle,
                            context.blender,
                            NoOpFaultInjector(),
                            manifest_sha256=context.manifest_sha256,
                        )
            except Exception as recovery_exc:
                raise InstallerError("installation recovery failed") from recovery_exc
            if isinstance(exc, InstallerError):
                raise exc
            raise InstallerError("installation failed") from exc


def _restore_action(
    journal: _Journal,
    action: ReceiptAction,
    target: TargetRef,
    stage: StagedFile | StagedTree,
    recovery: TargetRef,
) -> ReceiptAction:
    tree = isinstance(stage, StagedTree)
    absent: Image = TreeImage.absent() if tree else FileImage.absent()
    if action.state is ActionState.PLANNED:
        capture = capture_tree if tree else capture_file
        if (
            capture(target.root, target.relative) == action.pre
            and capture(stage.root, stage.relative) == absent
            and capture(recovery.root, recovery.relative) == absent
        ):
            return action
        raise InstallerError("recovery action state conflict")
    post = action.actual_post or action.intended_post
    if post is None:
        raise InstallerError("recovery action is incomplete")
    restore = restore_tree if tree else restore_file
    while action.state is not ActionState.RESTORED:
        previous_state = action.state
        result = restore(
            target,
            action.pre,
            post,
            stage,
            recovery,
            journal.fault,
        )
        if result is RestoreState.RESTORED:
            recovery_image: Image = TreeImage.absent() if tree else FileImage.absent()
            action = replace(
                action,
                state=ActionState.RESTORED,
                actual_post=post,
                recovery_image=recovery_image,
            )
            journal.action(action)
            journal.fault.hit(f"after_{action.kind.value}_restore_cleanup")
            return action
        captured = (
            capture_tree(recovery.root, recovery.relative)
            if tree
            else capture_file(recovery.root, recovery.relative)
        )
        recovery_image = (
            None
            if (action.pre.state is ImageState.PRESENT and captured.state is ImageState.ABSENT)
            else captured
        )
        action = replace(
            action,
            state=ActionState.RESTORING,
            actual_post=post,
            recovery_image=recovery_image,
        )
        journal.action(action)
        suffix = (
            "restore_swap"
            if action.pre.state is ImageState.PRESENT
            and previous_state is not ActionState.RESTORING
            else "restore_move"
        )
        journal.fault.hit(f"after_{action.kind.value}_{suffix}")
    return action


def _codex_state(action: ReceiptAction) -> RollbackState | None:
    if action.state is ActionState.SEMANTIC_STAGED:
        return RollbackState.C1
    if action.state is ActionState.SEMANTIC_SWAPPED:
        return RollbackState.C2
    if action.rollback_intended is not None and action.state is ActionState.RESTORING:
        return RollbackState.C3
    if action.rollback_intended is not None and action.state is ActionState.RESTORED:
        return RollbackState.C4
    if action.state is ActionState.RESTORING:
        return RollbackState.RESTORING
    if action.state is ActionState.RESTORED:
        return RollbackState.RESTORED
    return None


def _restore_codex(
    journal: _Journal,
    action: ReceiptAction,
    target: TargetRef,
    stage: StagedFile,
    recovery: StagedFile,
    rollback_stage: StagedFile,
    desired,
    runtime_python: Path,
) -> ReceiptAction:
    if not isinstance(action.actual_post, FileImage):
        raise InstallerError("Codex recovery action is incomplete")

    def callback(result: RollbackResult) -> None:
        nonlocal action
        states = {
            RollbackState.C1: ActionState.SEMANTIC_STAGED,
            RollbackState.C2: ActionState.SEMANTIC_SWAPPED,
            RollbackState.C3: ActionState.RESTORING,
            RollbackState.C4: ActionState.RESTORED,
            RollbackState.RESTORING: ActionState.RESTORING,
            RollbackState.RESTORED: ActionState.RESTORED,
        }
        recovery_image: FileImage | None = result.recovery
        if result.state is RollbackState.RESTORING and action.pre.state is ImageState.PRESENT:
            recovery_image = None if result.recovery.state is ImageState.ABSENT else result.recovery
        action = replace(
            action,
            state=states[result.state],
            recovery_image=recovery_image,
            rollback_intended=result.rollback_intended,
            rollback_displaced=result.rollback_displaced,
        )
        journal.action(action)

    context = CodexRollbackContext(
        target,
        stage,
        rollback_stage,
        _codex_state(action),
        action.rollback_intended,
        action.rollback_displaced,
        callback,
    )
    rollback_codex(
        context,
        recovery,
        action.actual_post,
        ManagedCodexKeys(desired),
        runtime_python,
        journal.fault,
    )
    return action


def _restore_selector(journal: _Journal, state: SafeRoot) -> None:
    target_data = next(
        target for target in journal.receipt.targets if target.role is TargetRole.ACTIVE_SELECTOR
    )
    if not isinstance(target_data.pre, FileImage) or not isinstance(
        target_data.install_post, FileImage
    ):
        raise InstallerError("active selector recovery conflict")
    target = TargetRef(state, PurePath("active.json"))
    recovery = TargetRef(
        state,
        PurePath("backups", str(journal.receipt.install_id), "previous-active.json"),
    )
    active_image = capture_file(state, target.relative)
    recovery_image = capture_file(state, recovery.relative)
    if target_data.pre.state is ImageState.PRESENT:
        if (active_image, recovery_image) == (
            target_data.install_post,
            target_data.pre,
        ):
            conditional_swap_file(
                target,
                target_data.install_post,
                recovery,
                target_data.pre,
                (),
                journal.fault,
            )
            journal.fault.hit("after_active_restore_swap")
        elif (active_image, recovery_image) != (
            target_data.pre,
            target_data.install_post,
        ):
            raise InstallerError("active selector recovery conflict")
    else:
        if (active_image, recovery_image) == (
            target_data.install_post,
            FileImage.absent(),
        ):
            recovery_fd, recovery_name = state.open_parent(recovery.relative)
            recovery_parent = SafeRoot(recovery.path.parent, state.owner_uid, recovery_fd)
            try:
                rename_excl(
                    state,
                    "active.json",
                    recovery_parent,
                    recovery_name,
                    journal.fault,
                )
            finally:
                recovery_parent.close()
            journal.fault.hit("after_active_restore_move")
        elif (active_image, recovery_image) != (
            FileImage.absent(),
            target_data.install_post,
        ):
            raise InstallerError("active selector recovery conflict")
    journal.fault.hit("after_active_restore_parent_fsync")


def _cleanup_restored_selector(journal: _Journal, state: SafeRoot) -> None:
    target_data = next(
        target for target in journal.receipt.targets if target.role is TargetRole.ACTIVE_SELECTOR
    )
    if not isinstance(target_data.pre, FileImage) or not isinstance(
        target_data.install_post, FileImage
    ):
        raise InstallerError("active selector recovery conflict")
    active = TargetRef(state, PurePath("active.json"))
    recovery = TargetRef(
        state,
        PurePath("backups", str(journal.receipt.install_id), "previous-active.json"),
    )
    recovery_image = capture_file(state, recovery.relative)
    if recovery_image == target_data.install_post:
        conditional_remove_file(
            recovery,
            target_data.install_post,
            ((active, target_data.pre),),
            journal.fault,
        )
    elif recovery_image != FileImage.absent():
        raise InstallerError("active selector recovery conflict")
    journal.fault.hit("after_active_restore_cleanup")


def _action_references(
    action: ReceiptAction,
    roots: InstallRoots,
    refs: Mapping[str, TargetRef],
    install_id: UUID,
) -> tuple[TargetRef, TargetRef, TargetRef]:
    if action.kind is ActionKind.RUNTIME_TREE:
        return (
            refs["runtime"],
            TreeRef(refs["runtime"].root, PurePath(roots.runtime_stage(install_id).name)),
            TreeRef(refs["runtime"].root, PurePath(roots.runtime_recovery(install_id).name)),
        )
    if action.kind is ActionKind.EXTENSION_TREE:
        return (
            refs["extension"],
            TreeRef(
                refs["extension"].root,
                PurePath("user_default", roots.extension_stage(install_id).name),
            ),
            TreeRef(
                refs["extension"].root,
                PurePath("user_default", roots.extension_recovery(install_id).name),
            ),
        )
    key = "codex" if action.kind is ActionKind.CODEX_FILE else "userpref"
    stage_path = (
        roots.codex_stage(install_id)
        if action.kind is ActionKind.CODEX_FILE
        else roots.userpref_stage(install_id)
    )
    recovery_path = (
        roots.codex_recovery(install_id)
        if action.kind is ActionKind.CODEX_FILE
        else roots.userpref_recovery(install_id)
    )
    return (
        refs[key],
        TargetRef(refs[key].root, PurePath(stage_path.name)),
        TargetRef(refs[key].root, PurePath(recovery_path.name)),
    )


def _native_rollback_tuple_valid(
    action: ReceiptAction, target: Image, stage: Image, recovery: Image
) -> bool:
    absent: Image = TreeImage.absent() if isinstance(action.pre, TreeImage) else FileImage.absent()
    if action.state is ActionState.PLANNED:
        return (target, stage, recovery) == (action.pre, absent, absent)
    post = action.actual_post or action.intended_post
    if post is None:
        return False
    if action.pre.state is ImageState.PRESENT:
        exact = {
            (action.pre, absent, absent),
            (action.pre, post, absent),
            (post, action.pre, absent),
            (post, absent, action.pre),
            (action.pre, absent, post),
        }
    else:
        exact = {
            (absent, absent, absent),
            (absent, post, absent),
            (post, absent, absent),
            (absent, absent, post),
        }
    if (target, stage, recovery) in exact:
        return True
    return (
        isinstance(recovery, TreeImage)
        and isinstance(post, TreeImage)
        and target == action.pre
        and stage == absent
        and is_tree_cleanup_prefix(recovery, post)
    )


def _preflight_rollback(
    roots: InstallRoots,
    bundle: StagedBundle,
    manifest_sha256: str,
    receipt: Receipt,
    state: SafeRoot,
    refs: Mapping[str, TargetRef],
) -> None:
    if (
        receipt.bundle.get("version") != bundle.manifest.bundle_version
        or receipt.bundle.get("manifest_sha256") != manifest_sha256
    ):
        raise InstallerError("rollback preflight conflict")
    kinds = [action.kind for action in receipt.actions]
    ordered = [
        ActionKind.BUNDLE_STAGE,
        ActionKind.RUNTIME_TREE,
        ActionKind.EXTENSION_TREE,
        ActionKind.USERPREF_FILE,
        ActionKind.CODEX_FILE,
    ]
    if kinds != ordered[: len(kinds)] or (
        receipt.status is ReceiptStatus.INSTALLED and kinds != ordered
    ):
        raise InstallerError("rollback preflight conflict")
    by_role = {target.role: target for target in receipt.targets}
    profile = ManagedProfile(
        roots.home,
        roots.blender.user_resources,
        roots.blender.user_config,
        roots.blender.user_extensions,
        roots.blender.executable,
    )
    desired = desired_codex_values(
        roots.runtime / "bin/blender-mcp-managed", profile, bundle.manifest.tools
    )
    runtime_evidence: tuple[ReceiptAction, tuple[Image, Image, Image]] | None = None
    for action in receipt.actions:
        if action.kind is ActionKind.BUNDLE_STAGE:
            bundle_image = capture_tree(
                state, PurePath("stages", str(receipt.install_id), "bundle")
            )
            valid = (
                (action.state is ActionState.PLANNED and bundle_image == TreeImage.absent())
                or (
                    action.state is ActionState.STAGED
                    and isinstance(action.intended_post, TreeImage)
                    and bundle_image in {action.intended_post, TreeImage.absent()}
                )
                or (action.state is ActionState.CLEANED and bundle_image == TreeImage.absent())
            )
            if not valid:
                raise InstallerError("rollback preflight conflict")
            continue
        target_ref, stage_ref, recovery_ref = _action_references(
            action, roots, refs, receipt.install_id
        )
        tree = action.kind in {ActionKind.RUNTIME_TREE, ActionKind.EXTENSION_TREE}
        capture = capture_tree if tree else capture_file
        physical = (
            capture(target_ref.root, target_ref.relative),
            capture(stage_ref.root, stage_ref.relative),
            capture(recovery_ref.root, recovery_ref.relative),
        )
        if action.kind is ActionKind.RUNTIME_TREE:
            runtime_evidence = (action, physical)
        recorded = by_role[action.target_role]
        post = action.actual_post or action.intended_post
        if recorded.pre != action.pre or (
            recorded.install_post is not None and recorded.install_post != post
        ):
            raise InstallerError("rollback preflight conflict")
        if recorded.recovery_hash is not None and recorded.recovery_hash != _image_hash(action.pre):
            raise InstallerError("rollback preflight conflict")
        semantic_codex = action.kind is ActionKind.CODEX_FILE and (
            action.state is ActionState.COMPLETED or action.rollback_intended is not None
        )
        if semantic_codex:
            if not isinstance(action.actual_post, FileImage):
                raise InstallerError("rollback preflight conflict")
            rollback_stage = capture_file(
                refs["codex"].root, PurePath(roots.codex_rollback_stage(receipt.install_id).name)
            )
            try:
                preflight_codex_rollback(
                    CodexRollbackContext(
                        refs["codex"],
                        StagedFile(
                            refs["codex"].root,
                            PurePath(roots.codex_stage(receipt.install_id).name),
                            action.actual_post,
                        ),
                        StagedFile(
                            refs["codex"].root,
                            PurePath(roots.codex_rollback_stage(receipt.install_id).name),
                            rollback_stage,
                        ),
                        _codex_state(action),
                        action.rollback_intended,
                        action.rollback_displaced,
                        lambda _result: None,
                    ),
                    StagedFile(
                        refs["codex"].root,
                        PurePath(roots.codex_recovery(receipt.install_id).name),
                        action.pre,
                    ),
                    action.actual_post,
                    ManagedCodexKeys(desired),
                    roots.runtime / "bin/python",
                )
            except (InstallerError, ValueError):
                raise InstallerError("rollback preflight conflict")
            continue
        elif not _native_rollback_tuple_valid(action, *physical):
            raise InstallerError("rollback preflight conflict")
    if runtime_evidence is not None:
        runtime_action, before = runtime_evidence
        target_ref, stage_ref, recovery_ref = _action_references(
            runtime_action, roots, refs, receipt.install_id
        )
        after = tuple(
            capture_tree(reference.root, reference.relative)
            for reference in (target_ref, stage_ref, recovery_ref)
        )
        if after != before:
            raise InstallerError("rollback preflight conflict")
    selector = by_role[TargetRole.ACTIVE_SELECTOR]
    if not isinstance(selector.pre, FileImage):
        raise InstallerError("rollback preflight conflict")
    active_image = capture_file(state, PurePath("active.json"))
    recovery_image = capture_file(
        state,
        PurePath("backups", str(receipt.install_id), "previous-active.json"),
    )
    if selector.install_post is None:
        if (active_image, recovery_image) != (selector.pre, FileImage.absent()):
            raise InstallerError("rollback preflight conflict")
        return
    if not isinstance(selector.install_post, FileImage):
        raise InstallerError("rollback preflight conflict")
    before = (
        selector.install_post,
        selector.pre if selector.pre.state is ImageState.PRESENT else FileImage.absent(),
    )
    reversed_row = (selector.pre, selector.install_post)
    terminal = (selector.pre, FileImage.absent())
    allowed = {before, reversed_row}
    if receipt.status is ReceiptStatus.ROLLED_BACK:
        allowed.add(terminal)
    if (active_image, recovery_image) not in allowed:
        raise InstallerError("rollback preflight conflict")


def _rollback_receipt(
    roots: InstallRoots,
    bundle: StagedBundle,
    blender: BlenderState,
    receipt: Receipt,
    fault: FaultInjector,
    *,
    manifest_sha256: str,
) -> Receipt:
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        with _refs(roots, state) as refs:
            _preflight_rollback(roots, bundle, manifest_sha256, receipt, state, refs)
            journal = _Journal(
                state,
                roots,
                fault,
                receipt,
                capture_file(state, PurePath("receipts", f"{receipt.install_id}.json")),
            )
            if receipt.status is not ReceiptStatus.ROLLBACK_PENDING:
                journal.write(replace(receipt, status=ReceiptStatus.ROLLBACK_PENDING))
                fault.hit("after_rollback_intent")
            bundle_actions = [
                action
                for action in journal.receipt.actions
                if action.kind is ActionKind.BUNDLE_STAGE
            ]
            if bundle_actions and bundle_actions[0].state is ActionState.STAGED:
                _cleanup_bundle(journal, state)
            profile = ManagedProfile(
                roots.home,
                roots.blender.user_resources,
                roots.blender.user_config,
                roots.blender.user_extensions,
                roots.blender.executable,
            )
            desired = desired_codex_values(
                roots.runtime / "bin/blender-mcp-managed", profile, bundle.manifest.tools
            )
            for action in reversed(journal.receipt.actions):
                if action.kind is ActionKind.BUNDLE_STAGE:
                    continue
                install_id = receipt.install_id
                if action.kind is ActionKind.CODEX_FILE:
                    stage = StagedFile(
                        refs["codex"].root,
                        PurePath(roots.codex_stage(install_id).name),
                        action.actual_post or action.intended_post or FileImage.absent(),
                    )
                    recovery = StagedFile(
                        refs["codex"].root,
                        PurePath(roots.codex_recovery(install_id).name),
                        action.pre,
                    )
                    if (
                        action.state is ActionState.COMPLETED
                        or action.rollback_intended is not None
                    ):
                        action = _restore_codex(
                            journal,
                            action,
                            refs["codex"],
                            stage,
                            recovery,
                            StagedFile(
                                refs["codex"].root,
                                PurePath(roots.codex_rollback_stage(install_id).name),
                                capture_file(
                                    refs["codex"].root,
                                    PurePath(roots.codex_rollback_stage(install_id).name),
                                ),
                            ),
                            desired,
                            roots.runtime / "bin/python",
                        )
                    else:
                        action = _restore_action(journal, action, refs["codex"], stage, recovery)
                elif action.kind is ActionKind.RUNTIME_TREE:
                    action = _restore_action(
                        journal,
                        action,
                        refs["runtime"],
                        StagedTree(
                            refs["runtime"].root,
                            PurePath(roots.runtime_stage(install_id).name),
                            action.actual_post,
                        ),
                        TreeRef(
                            refs["runtime"].root,
                            PurePath(roots.runtime_recovery(install_id).name),
                        ),
                    )
                elif action.kind is ActionKind.EXTENSION_TREE:
                    stage = StagedTree(
                        refs["extension"].root,
                        PurePath("user_default", roots.extension_stage(install_id).name),
                        action.actual_post,
                    )
                    recovery = TreeRef(
                        refs["extension"].root,
                        PurePath("user_default", roots.extension_recovery(install_id).name),
                    )
                    action = _restore_action(
                        journal,
                        action,
                        refs["extension"],
                        stage,
                        recovery,
                    )
                else:
                    action = _restore_action(
                        journal,
                        action,
                        refs["userpref"],
                        StagedFile(
                            refs["userpref"].root,
                            PurePath(roots.userpref_stage(install_id).name),
                            action.actual_post,
                        ),
                        TargetRef(
                            refs["userpref"].root,
                            PurePath(roots.userpref_recovery(install_id).name),
                        ),
                    )
            _restore_selector(journal, state)
            journal.write(replace(journal.receipt, status=ReceiptStatus.ROLLED_BACK))
            fault.hit("after_rollback_status")
            _cleanup_restored_selector(journal, state)
            return journal.receipt


def _discover_reversed_selector_receipt(
    roots: InstallRoots,
    bundle: StagedBundle,
    manifest_sha256: str,
    state: SafeRoot,
    fault: FaultInjector,
    expected_install_id: UUID | None = None,
) -> Receipt | None:
    try:
        receipts_fd = state.open_directory(PurePath("receipts"))
    except FileNotFoundError:
        return None
    try:
        names = tuple(sorted(os.listdir(receipts_fd)))
    finally:
        os.close(receipts_fd)
    candidates: list[Receipt] = []
    active_image = capture_file(state, PurePath("active.json"))
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            install_id = UUID(name[:-5])
        except ValueError:
            continue
        if install_id.version != 4 or name != f"{install_id}.json":
            continue
        receipt = load_receipt(roots.receipt(install_id), roots)
        if receipt.status not in {
            ReceiptStatus.ROLLBACK_PENDING,
            ReceiptStatus.ROLLED_BACK,
        }:
            continue
        target = next(item for item in receipt.targets if item.role is TargetRole.ACTIVE_SELECTOR)
        if not isinstance(target.pre, FileImage) or not isinstance(target.install_post, FileImage):
            raise InstallerError("active selector recovery conflict")
        recovery = TargetRef(
            state,
            PurePath("backups", str(install_id), "previous-active.json"),
        )
        recovery_image = capture_file(state, recovery.relative)
        if (active_image, recovery_image) != (target.pre, target.install_post):
            continue
        value, stale = load_atomic_json_pair(recovery, install_id)
        if stale is not None:
            raise InstallerError("active selector recovery conflict")
        try:
            selector = ActiveSelector.from_dict(value)
        except (TypeError, ValueError) as exc:
            raise InstallerError("active selector recovery conflict") from exc
        if selector != ActiveSelector(1, receipt.generation, install_id, name):
            raise InstallerError("active selector recovery conflict")
        candidates.append(receipt)
    if len(candidates) > 1:
        raise InstallerError("active selector recovery conflict")
    if not candidates:
        return None
    candidate = candidates[0]
    if expected_install_id is not None and candidate.install_id != expected_install_id:
        raise InstallerError("active selector recovery conflict")
    _settle_known_receipt_atomic_json(
        roots, bundle, manifest_sha256, candidate.install_id, state, fault
    )
    return load_receipt(roots.receipt(candidate.install_id), roots)


def recover_active(
    roots: InstallRoots,
    bundle: StagedBundle,
    blender: BlenderState,
    fault: FaultInjector,
    *,
    manifest_sha256: str,
    expected_install_id: UUID | None = None,
) -> dict[str, object]:
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        reversed_receipt = _discover_reversed_selector_receipt(
            roots, bundle, manifest_sha256, state, fault, expected_install_id
        )
        if reversed_receipt is not None:
            if reversed_receipt.status is ReceiptStatus.ROLLED_BACK:
                journal = _Journal(
                    state,
                    roots,
                    fault,
                    reversed_receipt,
                    capture_file(
                        state,
                        PurePath("receipts", f"{reversed_receipt.install_id}.json"),
                    ),
                )
                _cleanup_restored_selector(journal, state)
                return {"recovered": True, "status": "rolled_back"}
            rolled = _rollback_receipt(
                roots,
                bundle,
                blender,
                reversed_receipt,
                fault,
                manifest_sha256=manifest_sha256,
            )
            return {"recovered": True, "status": rolled.status.value}
    try:
        active = load_active(roots.active, roots)
    except FileNotFoundError:
        active = None
    if active is None:
        return {"recovered": False}
    if expected_install_id is not None and active.install_id != expected_install_id:
        raise InstallerError("active selector recovery conflict")
    with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
        _settle_known_receipt_atomic_json(
            roots, bundle, manifest_sha256, active.install_id, state, fault
        )
    receipt = load_receipt(roots.receipt(active.install_id), roots)
    if receipt.status is ReceiptStatus.INSTALLED:
        bundle_actions = [
            action for action in receipt.actions if action.kind is ActionKind.BUNDLE_STAGE
        ]
        if bundle_actions:
            changed = bundle_actions[0].state is ActionState.STAGED
            with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
                journal = _Journal(
                    state,
                    roots,
                    fault,
                    receipt,
                    capture_file(state, PurePath("receipts", f"{receipt.install_id}.json")),
                )
                _cleanup_bundle(journal, state)
            return {"recovered": changed, "status": "installed"}
        return {"recovered": False, "status": "installed"}
    if receipt.status not in {ReceiptStatus.PREPARED, ReceiptStatus.ROLLBACK_PENDING}:
        return {"recovered": False, "status": receipt.status.value}
    rolled = _rollback_receipt(
        roots,
        bundle,
        blender,
        receipt,
        fault,
        manifest_sha256=manifest_sha256,
    )
    return {"recovered": True, "status": rolled.status.value}


def verify(args: argparse.Namespace) -> dict[str, object]:
    with _context(args) as context:
        try:
            with SafeRoot.open(
                context.roots.state_root, os.getuid(), context.roots.state_root
            ) as state:
                with InstallerLock.acquire(state, create=False):
                    result = verify_live(
                        context.source_bundle,
                        context.roots,
                        context.blender,
                        context.host,
                        args.receipt,
                        context.host.env,
                        OfficialMCPProbe(context.roots.runtime / "bin/python"),
                    )
        except (OSError, ValueError) as exc:
            raise InstallerError("verification lock unavailable") from exc
        return {
            "command": "verify",
            "receipt": str(result.receipt_path),
            "parsed_codex": result.parsed_codex,
            "effective_codex": result.effective_codex,
            "mcp_catalog": result.mcp_catalog,
            "blender_read_only": result.blender_read_only,
            "tool_count": result.tool_count,
        }


def rollback(args: argparse.Namespace) -> dict[str, object]:
    fault = getattr(args, "_fault", NoOpFaultInjector())
    with _context(args) as context:
        roots = context.roots
        with SafeRoot.open(roots.state_root, os.getuid(), roots.state_root) as state:
            with InstallerLock.acquire(state):
                requested = load_receipt(args.receipt, roots)
                if args.receipt != roots.receipt(requested.install_id):
                    raise InstallerError("rollback receipt path is invalid")
                if requested.status not in {
                    ReceiptStatus.INSTALLED,
                    ReceiptStatus.PREPARED,
                    ReceiptStatus.ROLLBACK_PENDING,
                    ReceiptStatus.ROLLED_BACK,
                }:
                    raise InstallerError("rollback receipt status is invalid")
                active = load_active(roots.active, roots)
                pending = load_pending(roots.pending, roots)
                selector = next(
                    target
                    for target in requested.targets
                    if target.role is TargetRole.ACTIVE_SELECTOR
                )
                active_image = capture_file(state, PurePath("active.json"))
                previous_image = capture_file(
                    state,
                    PurePath("backups", str(requested.install_id), "previous-active.json"),
                )
                direct_authority = (
                    active is not None
                    and active.install_id == requested.install_id
                    and active.receipt_basename == args.receipt.name
                )
                reversed_authority = (
                    isinstance(selector.pre, FileImage)
                    and isinstance(selector.install_post, FileImage)
                    and (active_image, previous_image) == (selector.pre, selector.install_post)
                )
                if requested.status is not ReceiptStatus.ROLLED_BACK and (
                    not (direct_authority or reversed_authority)
                    or (pending is not None and pending.install_id != requested.install_id)
                ):
                    raise InstallerError("rollback receipt is not active")
                _lifecycle_closed(context)
                with _refs(roots, state) as refs:
                    _preflight_rollback(
                        roots,
                        context.source_bundle,
                        context.manifest_sha256,
                        requested,
                        state,
                        refs,
                    )
                if (
                    requested.status is ReceiptStatus.ROLLED_BACK
                    and previous_image == FileImage.absent()
                ):
                    roles = [
                        action.target_role.value
                        for action in requested.actions
                        if action.target_role is not None
                    ]
                    return {
                        "command": "rollback",
                        "receipt": str(args.receipt),
                        "status": "rolled_back",
                        "restored_roles": roles,
                    }
                reconcile_selectors(
                    roots,
                    context.source_bundle,
                    context.blender,
                    fault,
                    manifest_sha256=context.manifest_sha256,
                )
                recover_active(
                    roots,
                    context.source_bundle,
                    context.blender,
                    fault,
                    manifest_sha256=context.manifest_sha256,
                    expected_install_id=requested.install_id,
                )
                requested = load_receipt(args.receipt, roots)
                if requested.status is ReceiptStatus.ROLLED_BACK:
                    roles = [
                        action.target_role.value
                        for action in requested.actions
                        if action.target_role is not None
                    ]
                    return {
                        "command": "rollback",
                        "receipt": str(args.receipt),
                        "status": "rolled_back",
                        "restored_roles": roles,
                    }
                active = load_active(roots.active, roots)
                if active is None or args.receipt != roots.receipt(active.install_id):
                    raise InstallerError("rollback receipt is not active")
                receipt = requested
                rolled = _rollback_receipt(
                    roots,
                    context.source_bundle,
                    context.blender,
                    receipt,
                    fault,
                    manifest_sha256=context.manifest_sha256,
                )
                roles = [
                    action.target_role.value
                    for action in rolled.actions
                    if action.target_role is not None
                ]
                return {
                    "command": "rollback",
                    "receipt": str(args.receipt),
                    "status": "rolled_back",
                    "restored_roles": roles,
                }


def run_cli(argv: Sequence[str], fault: FaultInjector) -> int:
    try:
        args = _parser().parse_args(tuple(argv))
    except _ArgumentError:
        print(json.dumps({"error": "invalid arguments"}, sort_keys=True, separators=(",", ":")))
        return 2
    except SystemExit as exc:
        return int(exc.code)
    args._fault = fault
    handler = {"inspect": inspect, "install": install, "verify": verify, "rollback": rollback}[
        args.command
    ]
    try:
        result = handler(args)
    except InstallerError:
        print(json.dumps({"error": "installer error"}, sort_keys=True, separators=(",", ":")))
        return 1
    except SystemExit:
        raise
    except Exception:
        print(
            json.dumps({"error": "internal installer error"}, sort_keys=True, separators=(",", ":"))
        )
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(sys.argv[1:] if argv is None else argv, NoOpFaultInjector())
