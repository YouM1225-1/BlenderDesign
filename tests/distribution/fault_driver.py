from __future__ import annotations

import argparse
import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


_INSTALL = frozenset({"install"})
_MUTATING = frozenset({"install", "rollback"})
_PREIMAGES = {
    "atomic_json": frozenset({"any"}),
    "pending": frozenset({"present", "absent"}),
    "receipt": frozenset({"present", "absent"}),
    "active_selector": frozenset({"present", "absent"}),
    "bundle_stage": frozenset({"absent"}),
    "runtime_tree": frozenset({"present", "absent"}),
    "extension_tree": frozenset({"present", "absent"}),
    "userpref_file": frozenset({"present", "absent"}),
    "codex_file": frozenset({"present", "absent"}),
    "codex_semantic": frozenset({"present", "absent"}),
}


def _applicable_points(fixture_kind: str, preimage: str) -> dict[str, frozenset[str]]:
    if preimage not in _PREIMAGES[fixture_kind]:
        raise ValueError("preimage is not valid for fixture kind")
    if fixture_kind == "atomic_json":
        return {
            point: _MUTATING
            for point in ("after_json_file_fsync", "after_json_rename", "after_json_parent_fsync")
        }
    if fixture_kind == "pending":
        return {point: _INSTALL for point in ("after_pending_publish", "after_pending_remove")}
    if fixture_kind == "receipt":
        return {"after_receipt_publish": _INSTALL}
    if fixture_kind == "bundle_stage":
        return {
            point: _INSTALL
            for point in (
                "after_bundle_stage_planned",
                "after_bundle_stage_stage",
                "after_receipt_installed",
                "after_bundle_stage_cleanup",
            )
        }
    if fixture_kind == "codex_semantic":
        points = {
            point: _MUTATING
            for point in (
                "after_codex_semantic_stage_fsync",
                "after_codex_semantic_swap",
                "after_codex_semantic_receipt",
                "after_codex_semantic_displaced_cleanup",
                "after_codex_semantic_recovery_cleanup",
            )
        }
        if preimage == "absent":
            points.update(
                {
                    point: _MUTATING
                    for point in (
                        "after_json_file_fsync",
                        "after_json_rename",
                        "after_json_parent_fsync",
                    )
                }
            )
        return points
    if fixture_kind == "active_selector":
        points = {
            "after_rollback_intent": _MUTATING,
            "after_active_restore_parent_fsync": _MUTATING,
            "after_rollback_status": _MUTATING,
            "after_active_restore_cleanup": _MUTATING,
            "after_active_parent_fsync": _INSTALL,
        }
        if preimage == "present":
            points.update(
                {
                    "after_active_swap": _INSTALL,
                    "after_active_park": _INSTALL,
                    "after_active_restore_swap": _MUTATING,
                }
            )
        else:
            points.update(
                {
                    "after_active_publish": _INSTALL,
                    "after_active_restore_move": _MUTATING,
                }
            )
        return points
    points = {
        f"after_{fixture_kind}_{suffix}": _INSTALL for suffix in ("planned", "stage", "completed")
    }
    points[f"after_{fixture_kind}_restore_cleanup"] = _MUTATING
    if preimage == "present":
        points.update(
            {
                f"after_{fixture_kind}_swap": _INSTALL,
                f"after_{fixture_kind}_park": _INSTALL,
                f"after_{fixture_kind}_restore_swap": _MUTATING,
                f"after_{fixture_kind}_restore_move": _MUTATING,
            }
        )
    else:
        points.update(
            {
                f"after_{fixture_kind}_publish": _INSTALL,
                f"after_{fixture_kind}_restore_move": _MUTATING,
            }
        )
    return points


def _scenario_host(root: Path):
    from tests.distribution.fake_host import HostHarness, create_host

    host_root = root / "host"
    if not host_root.exists():
        return create_host(root)
    return HostHarness(
        host_root,
        host_root / "home",
        host_root / "codex",
        host_root / "blender/resources",
        host_root / "blender/resources/config",
        host_root / "blender/resources/extensions",
        host_root / "bundle",
        host_root / "home/.local/state/blender-mcp-installer",
        host_root / "home/.local/share/blender-lab-mcp",
        host_root / "host-state.json",
        host_root / "commands.jsonl",
        host_root / "bin/codex",
        host_root / "bin/blender",
        host_root / "bin/uv",
    )


def _patch_scenario(cli, root: Path, fixture_kind: str, preimage: str, point: str) -> None:
    from blender_mcp_installer.blender_adapter import BlenderChange, BlenderState
    from blender_mcp_installer.bundle import StagedBundle, parse_manifest
    from blender_mcp_installer.filesystem import SafeRoot, capture_file, capture_tree
    from blender_mcp_installer.model import BlenderPaths, InstallRoots, ReceiptStatus
    from blender_mcp_installer.verification import HostCapabilities

    host = _scenario_host(root)
    repository = Path(__file__).resolve().parents[2]
    artifacts = repository / "plugins/blender-mcp-installer/artifacts"
    manifest = parse_manifest((artifacts / "manifest.json").read_bytes())
    paths = BlenderPaths(
        host.blender,
        "arm64",
        "5.2.0",
        host.resources,
        host.config,
        host.extensions,
    )
    roots = InstallRoots.discover(
        host.home,
        host.codex_home,
        paths,
        source_distribution_root=repository,
        distribution_root=repository,
    )
    blender = BlenderState(
        host.blender,
        ("arm64",),
        host.blender,
        "arm64",
        "5.2.0",
        host.home,
        host.resources,
        host.config,
        host.config / "userpref.blend",
        host.extensions,
        "user_default",
        host.extensions / "user_default/mcp",
        None,
        None,
        False,
        False,
        None,
        None,
        None,
        None,
    )
    env = {
        "HOME": str(host.home),
        "CODEX_HOME": str(host.codex_home),
        "BLENDER_USER_RESOURCES": str(host.resources),
        "BLENDER_USER_CONFIG": str(host.config),
        "BLENDER_USER_EXTENSIONS": str(host.extensions),
    }
    capabilities = HostCapabilities(
        "Darwin",
        "arm64",
        "0.148.0-alpha.9",
        "0.12.2",
        "5.2.0",
        "3.13.13",
        ("arm64",),
        True,
        True,
        True,
        host.blender,
        host.codex,
        host.uv,
        Path(sys.executable),
        env,
        lambda *_args, **_kwargs: None,
    )

    class Verified:
        def __init__(self) -> None:
            self.manifest = manifest

        def materialize(self, path: Path) -> StagedBundle:
            shutil.copytree(artifacts, path)
            return StagedBundle(path, manifest)

    context = cli._Context(
        Verified(),
        StagedBundle(artifacts, manifest),
        "2b799aff562693ce0b79e9df4737158b4b785e5c854e39673a289192adaf4a60",
        capabilities,
        blender,
        roots,
    )

    @contextmanager
    def fake_context(_args):
        yield context

    def inspection(_context):
        try:
            active = cli.load_active(roots.active, roots)
            receipt = (
                None
                if active is None
                else cli.load_receipt(roots.receipt(active.install_id), roots)
            )
        except Exception:
            receipt = None
        force = root / "force-change"
        forced = force.exists()
        if forced:
            force.unlink()
        exact = receipt is not None and receipt.status is ReceiptStatus.INSTALLED and not forced
        return SimpleNamespace(
            exact=exact,
            receipt_path=None if receipt is None else roots.receipt(receipt.install_id),
        )

    def fake_runtime(_bundle, _uv, _python, _profile, stage, _runner):
        import tomlkit

        (stage.path / "bin").mkdir()
        runtime_python = stage.path / "bin/python"
        shutil.copy2(Path(sys.executable).resolve(), runtime_python)
        runtime_python.chmod(0o700)
        (stage.path / "pyvenv.cfg").write_text(
            f"home = {Path(sys.base_prefix) / 'bin'}\ninclude-system-site-packages = false\n"
        )
        site = (
            stage.path
            / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        )
        site.mkdir(parents=True)
        shutil.copytree(
            Path(tomlkit.__file__).parent,
            site / "tomlkit",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (stage.path / "bin/blender-mcp-managed").write_bytes(b"launcher")
        return capture_tree(stage.root, stage.relative)

    def fake_blender(_state, _zip, work: Path, _authorizations, _runner):
        extension = work / "resources/extensions/user_default/mcp"
        extension.mkdir(parents=True)
        (extension / "blender_manifest.toml").write_bytes(b"payload")
        userpref = work / "resources/config/userpref.blend"
        userpref.parent.mkdir(parents=True)
        userpref.write_bytes(b"preferences")
        (work / "mcp-1.0.0.zip").write_bytes(b"zip")
        with SafeRoot.open(work, os.getuid(), work) as safe:
            extension_image = capture_tree(safe, Path("resources/extensions/user_default/mcp"))
            userpref_image = capture_file(safe, Path("resources/config/userpref.blend"))
        return BlenderChange(
            True,
            work,
            extension,
            userpref,
            extension_image,
            userpref_image,
            blender,
            (),
        )

    def fake_codex(_fd, _current, _desired, _runtime_python, stage):
        stage.path.write_bytes(b'foreign = "keep"\n')
        refreshed = stage.refresh()
        return SimpleNamespace(post=refreshed.image, stage=refreshed)

    cli._context = fake_context
    cli._inspection = inspection
    cli._lifecycle_closed = lambda _context: None
    cli.stage_runtime = fake_runtime
    cli.stage_blender_change = fake_blender
    if fixture_kind not in {"codex_file", "codex_semantic"}:
        cli.stage_codex_config = fake_codex
    cli.verify_runtime = lambda *_args, **_kwargs: None
    cli.inspect_blender = lambda *_args, **_kwargs: blender
    cli.verify_blender_files = lambda *_args, **_kwargs: None
    cli.load_extension_payload = lambda *_args, **_kwargs: object()
    cli.verify_codex_toml = lambda *_args, **_kwargs: None
    cli.verify_codex_effective = lambda *_args, **_kwargs: None

    marker = root / ".preimage-seeded"
    if not marker.exists() and preimage == "present":
        selected = {
            "runtime_tree": roots.runtime,
            "extension_tree": roots.extension_target,
            "userpref_file": roots.userpref_target,
            "codex_file": roots.codex_config,
            "codex_semantic": roots.codex_config,
        }.get(fixture_kind)
        if selected is not None:
            selected.parent.mkdir(parents=True, exist_ok=True)
            if fixture_kind in {"runtime_tree", "extension_tree"}:
                selected.mkdir()
                (selected / "preimage").write_bytes(b"preimage")
            else:
                selected.write_bytes(b'foreign = "SECRET-SENTINEL"\n')
        marker.write_text("seeded\n")
    semantic_marker = root / ".semantic-seeded"
    if (
        fixture_kind == "codex_semantic"
        and not semantic_marker.exists()
        and roots.codex_config.exists()
        and roots.active.exists()
    ):
        with roots.codex_config.open("a") as stream:
            stream.write('\n[foreign_after]\nsecret = "SECRET-SENTINEL"\n')
        semantic_marker.write_text("seeded\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--point", required=True)
    parser.add_argument("--fixture-kind", required=True, choices=tuple(_PREIMAGES))
    parser.add_argument("--preimage", required=True, choices=("present", "absent", "any"))
    parser.add_argument("--scenario-root", type=Path)
    parser.add_argument("--recover", action="store_true")
    args, cli_argv = parser.parse_known_args()
    if cli_argv[:1] == ["--"]:
        cli_argv = cli_argv[1:]
    if not cli_argv or cli_argv[0] not in {"inspect", "install", "verify", "rollback"}:
        parser.error("a valid installer command is required")
    try:
        points = _applicable_points(args.fixture_kind, args.preimage)
    except ValueError as exc:
        parser.error(str(exc))
    commands = points.get(args.point)
    if commands is None:
        parser.error("fault point is not applicable to this fixture")
    if cli_argv[0] not in commands and not args.recover:
        parser.error("fault point is not applicable to this command")

    root = Path(__file__).resolve().parents[2]
    scripts = root / "plugins/blender-mcp-installer/scripts"
    sys.path.insert(0, str(scripts))
    from blender_mcp_installer.cli import ExitFaultInjector, run_cli
    import blender_mcp_installer.cli as cli

    if args.scenario_root is not None:
        _patch_scenario(cli, args.scenario_root, args.fixture_kind, args.preimage, args.point)

    fault = cli.NoOpFaultInjector() if args.recover else ExitFaultInjector(args.point, 70)
    code = run_cli(cli_argv, fault=fault)
    if not args.recover and not fault.hit_requested:
        parser.error("requested fault point was not hit")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
