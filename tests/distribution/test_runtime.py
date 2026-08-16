from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePath
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "plugins/blender-mcp-installer/scripts"
ARTIFACTS = ROOT / "plugins/blender-mcp-installer/artifacts"
sys.path.insert(0, str(SCRIPTS))

from blender_mcp_installer.bundle import (  # noqa: E402
    StagedBundle,
    parse_manifest,
)
from blender_mcp_installer.codex_adapter import ManagedProfile  # noqa: E402
from blender_mcp_installer import runtime as runtime_module  # noqa: E402
from blender_mcp_installer.filesystem import (  # noqa: E402
    InstallerError,
    NativeState,
    NoOpFaultInjector,
    RestoreState,
    SafeRoot,
    StagedTree,
    TreeRef,
    create_deterministic_stage,
    forward_tree,
    restore_tree,
)
from blender_mcp_installer.model import ImageState, TreeImage  # noqa: E402
from blender_mcp_installer.runtime import (  # noqa: E402
    inspect_runtime,
    stage_runtime,
    verify_runtime,
)


def _profile(root: Path) -> ManagedProfile:
    resources = root / "profile/resources"
    return ManagedProfile(
        home=root / "home",
        blender_user_resources=resources,
        blender_user_config=resources / "config",
        blender_user_extensions=resources / "extensions",
        blender_path=root / "Applications/Blender.app/Contents/MacOS/Blender",
    )


def _bundle(root: Path, *, copy: bool = False) -> StagedBundle:
    manifest = parse_manifest((ARTIFACTS / "manifest.json").read_bytes())
    if not copy:
        return StagedBundle(ARTIFACTS, manifest)
    target = root / "bundle"
    target.mkdir(mode=0o700)
    for name in (
        "manifest.json",
        "SHA256SUMS",
        "runtime-requirements.lock",
        "blender_mcp-1.0.0-py3-none-any.whl",
        "mcp-1.0.0.zip",
    ):
        (target / name).write_bytes((ARTIFACTS / name).read_bytes())
        (target / name).chmod(0o600)
    return StagedBundle(target, manifest)


def _locked(bundle: StagedBundle) -> dict[str, str]:
    result: dict[str, str] = {}
    current: list[str] = []
    for line in bundle.runtime_lock_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        current.append(stripped[:-1].rstrip() if stripped.endswith("\\") else stripped)
        if not stripped.endswith("\\"):
            name_version = " ".join(current).split()[0]
            name, version = name_version.split("==", 1)
            result[name.replace("_", "-").lower()] = version
            current = []
    result["blender-mcp"] = "1.0.0"
    return dict(sorted(result.items()))


class RuntimeRunner:
    def __init__(self, bundle: StagedBundle):
        self.bundle = bundle
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []

    def __call__(self, argv, *, cwd: Path, env):
        args = tuple(str(value) for value in argv)
        clean = dict(env)
        self.calls.append((args, cwd, clean))
        if len(args) == 6 and args[1:4] == ("venv", "--relocatable", "--python"):
            stage = Path(args[5])
            (stage / "bin").mkdir(exist_ok=True)
            python = stage / "bin/python"
            python.write_text(f'#!/bin/sh\nexec {sys.executable!s} "$@"\n')
            python.chmod(0o700)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[1:4] == ("pip", "install", "--python"):
            if Path(args[-1]).name == self.bundle.wheel_path.name:
                server = Path(args[4]).with_name("blender-mcp")
                probe = server.with_name("server-probe.py")
                module = server.parent.parent / "lib/python3.13/site-packages/blmcp/__init__.py"
                module.parent.mkdir(parents=True)
                module.write_text("# fake official module\n")
                tool = module.parent / "tools/changed.py"
                tool.parent.mkdir()
                tool.write_text("# fake official tool\n")
                dependency = module.parent.parent / "mcp/dependency.py"
                dependency.parent.mkdir()
                dependency.write_text("# fake locked dependency\n")
                probe.write_text(
                    "import json, pathlib, sys\n"
                    "raw = pathlib.Path(sys.argv[1]).with_name('observed-env').read_bytes()\n"
                    "env = dict(item.decode().split('=', 1) for item in raw.split(b'\\0') if item)\n"
                    "print(json.dumps({'argv': sys.argv[2:], 'env': env, "
                    "'entrypoint': sys.argv[1]}, sort_keys=True))\n"
                )
                server.write_text(
                    "#!/bin/sh\n"
                    "exec_dir=${0%/*}\n"
                    '/usr/bin/env -0 > "$exec_dir/observed-env"\n'
                    f'exec {sys.executable!s} "$exec_dir/server-probe.py" "$0" "$@"\n'
                )
                server.chmod(0o700)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if len(args) == 4 and args[1:3] == ("-I", "-c"):
            runtime = Path(args[0]).parent.parent
            payload = {
                "python_version": "3.13.13",
                "distributions": _locked(self.bundle),
                "entry_point": "blender-mcp = blmcp:main",
                "entry_point_path": str(runtime / "bin/blender-mcp"),
                "module_path": str(runtime / "lib/python3.13/site-packages/blmcp/__init__.py"),
                "tools": list(self.bundle.manifest.tools),
            }
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        raise AssertionError(args)


class BundleSwapRunner(RuntimeRunner):
    def __init__(self, bundle: StagedBundle, role: str, after_call: int, mutation: str):
        super().__init__(bundle)
        self.role = role
        self.after_call = after_call
        self.mutation = mutation
        self.swapped = False

    def __call__(self, argv, *, cwd: Path, env):
        result = super().__call__(argv, cwd=cwd, env=env)
        if len(self.calls) - 1 == self.after_call:
            path = self.bundle.runtime_lock_path if self.role == "lock" else self.bundle.wheel_path
            if self.mutation == "replace":
                original = path.with_name(path.name + ".opened-original")
                path.rename(original)
            path.write_bytes(b"replacement-with-expected-fake-metadata")
            path.chmod(0o600)
            self.swapped = True
        return result


class StageRootSwapRunner(RuntimeRunner):
    def __init__(self, bundle: StagedBundle, after_call: int | None):
        super().__init__(bundle)
        self.after_call = after_call
        self.replacement: Path | None = None

    def replace(self, runtime: Path) -> None:
        displaced = runtime.with_name(runtime.name + ".opened-original")
        runtime.rename(displaced)
        shutil.copytree(displaced, runtime)
        sentinel = runtime / "replacement-sentinel"
        sentinel.write_bytes(b"preserve-replacement")
        sentinel.chmod(0o600)
        for name in (
            self.bundle.runtime_lock_path.name,
            self.bundle.wheel_path.name,
        ):
            path = runtime / name
            if path.exists():
                path.write_bytes(b"replacement-private-input")
                path.chmod(0o600)
        self.replacement = runtime

    def __call__(self, argv, *, cwd: Path, env):
        result = super().__call__(argv, cwd=cwd, env=env)
        if len(self.calls) - 1 == self.after_call:
            args = self.calls[-1][0]
            runtime = Path(args[5]) if self.after_call == 0 else Path(args[4]).parent.parent
            self.replace(runtime)
        return result


def _stage(tmp_path: Path, bundle: StagedBundle):
    root_path = tmp_path / "data"
    root_path.mkdir(mode=0o700, parents=True)
    root = SafeRoot.open(root_path, os.getuid(), root_path)
    created = create_deterministic_stage(
        root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
    )
    assert isinstance(created, StagedTree)
    runner = RuntimeRunner(bundle)
    image = stage_runtime(
        bundle,
        Path("/opt/uv").absolute(),
        Path(sys.executable),
        _profile(tmp_path),
        created,
        runner,
    )
    return root, created.with_image(image), runner


def test_stage_uses_hash_binary_only_commands_and_closed_environment(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    root, stage, runner = _stage(tmp_path, bundle)
    try:
        assert stage.image.state is ImageState.PRESENT
        assert len(runner.calls) == 4
        venv, lock, wheel, probe = runner.calls
        assert venv[0] == (
            "/opt/uv",
            "venv",
            "--relocatable",
            "--python",
            str(Path(sys.executable)),
            str(stage.path),
        )
        assert lock[0] == (
            "/opt/uv",
            "pip",
            "install",
            "--python",
            str(stage.path / "bin/python"),
            "--require-hashes",
            "--only-binary",
            ":all:",
            "--no-deps",
            "--default-index",
            "https://pypi.org/simple",
            "-r",
            str(stage.path / bundle.runtime_lock_path.name),
        )
        assert wheel[0] == (
            "/opt/uv",
            "pip",
            "install",
            "--python",
            str(stage.path / "bin/python"),
            "--no-deps",
            "--no-build",
            str(stage.path / bundle.wheel_path.name),
        )
        assert not (stage.path / bundle.runtime_lock_path.name).exists()
        assert not (stage.path / bundle.wheel_path.name).exists()
        assert probe[0][0] == str(stage.path / "bin/python")
        for index, (_argv, _cwd, env) in enumerate(runner.calls):
            if index == 2:
                assert "UV_REQUIRE_HASHES" not in env
            else:
                assert env["UV_REQUIRE_HASHES"] == "1"
            assert env["UV_NO_BUILD"] == "1"
            assert env["UV_DEFAULT_INDEX"] == "https://pypi.org/simple"
            assert env["BLENDER_MCP_HOST"] == "localhost"
            assert env["BLENDER_MCP_PORT"] == "9876"
            assert not any(key.startswith("PIP_") for key in env)
            assert "UV_INDEX" not in env and "UV_INDEX_URL" not in env
    finally:
        root.close()


def test_stage_rejects_changed_lock_before_runner_or_stage_mutation(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, copy=True)
    bundle.runtime_lock_path.write_text("tomlkit==0.13.3 --hash=sha256:" + "0" * 64 + "\n")
    root_path = tmp_path / "data"
    root_path.mkdir(mode=0o700)
    with SafeRoot.open(root_path, os.getuid(), root_path) as root:
        stage = create_deterministic_stage(
            root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(stage, StagedTree)
        runner = RuntimeRunner(bundle)
        with pytest.raises(InstallerError, match="bundle artifact changed"):
            stage_runtime(
                bundle,
                Path("/opt/uv").absolute(),
                Path(sys.executable),
                _profile(tmp_path),
                stage,
                runner,
            )
        assert runner.calls == []
        assert stage.capture().entries == ()


def test_inspect_and_verify_record_exact_runtime_and_noop_is_read_only(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    root, stage, runner = _stage(tmp_path, bundle)
    try:
        before = len(runner.calls)
        state = inspect_runtime(TreeRef(root, stage.relative), bundle.manifest)
        assert state.exact
        assert state.python_version == "3.13.13"
        assert state.distributions == _locked(bundle)
        assert state.blender_mcp_version == "1.0.0"
        assert state.mcp_version == "1.28.1"
        assert state.tomlkit_version == "0.13.3"
        assert state.entry_point == "blender-mcp = blmcp:main"
        assert state.entry_point_path == stage.path / "bin/blender-mcp"
        assert state.module_path.is_relative_to(stage.path)
        assert state.tools == bundle.manifest.tools
        assert len(runner.calls) == before
        verified = verify_runtime(
            TreeRef(root, stage.relative), bundle.manifest, _profile(tmp_path), runner
        )
        assert verified.exact
        assert verified.tree == state.tree
        assert len(runner.calls) == before + 1
        inspect_runtime(TreeRef(root, stage.relative), bundle.manifest)
        assert len(runner.calls) == before + 1
    finally:
        root.close()


def test_actual_launcher_discards_hostile_parent_and_selects_managed_identity(
    tmp_path: Path,
) -> None:
    bundle = _bundle(tmp_path)
    root, stage, _runner = _stage(tmp_path, bundle)
    try:
        hostile = dict(os.environ)
        hostile.update(
            {
                "HOME": "/hostile/home",
                "PATH": str(tmp_path / "hostile/bin"),
                "LANG": "HOSTILE",
                "LC_ALL": "HOSTILE",
                "TMPDIR": "/hostile/tmp",
                "PYTHONPATH": "/hostile/python",
                "PYTHONHOME": "/hostile/python-home",
                "PYTHONUSERBASE": "/hostile/user-base",
                "PYTHONSTARTUP": "/hostile/startup",
                "PYTHONINSPECT": "1",
                "VIRTUAL_ENV": "/hostile/venv",
                "UV_INDEX": "https://hostile.invalid/simple",
                "PIP_INDEX_URL": "https://hostile.invalid/simple",
                "BLENDER_MCP_HOST": "hostile.invalid",
                "BLENDER_MCP_PORT": "1",
                "BLENDER_USER_RESOURCES": "/hostile/resources",
                "BLENDER_OTHER": "hostile",
            }
        )
        completed = subprocess.run(
            [stage.path / "bin/blender-mcp-managed", "one", "two"],
            env=hostile,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        profile = _profile(tmp_path)
        assert payload["argv"] == ["one", "two"]
        assert payload["entrypoint"] == str(stage.path / "bin/blender-mcp")
        shell_env = payload["env"]
        assert shell_env.pop("SHLVL") == "1"
        assert shell_env.pop("_") == "/usr/bin/env"
        assert Path(shell_env.pop("PWD")).is_absolute()
        assert shell_env == {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(profile.home),
            "BLENDER_USER_RESOURCES": str(profile.blender_user_resources),
            "BLENDER_USER_CONFIG": str(profile.blender_user_config),
            "BLENDER_USER_EXTENSIONS": str(profile.blender_user_extensions),
            "BLENDER_PATH": str(profile.blender_path),
            "BLENDER_MCP_HOST": "localhost",
            "BLENDER_MCP_PORT": "9876",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
        }
    finally:
        root.close()


def test_absent_and_altered_runtime_are_not_exact(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    with SafeRoot.open(data, os.getuid(), data) as root:
        absent = inspect_runtime(TreeRef(root, PurePath("runtime")), bundle.manifest)
        assert absent.tree == TreeImage.absent()
        assert not absent.exact
    root, stage, _runner = _stage(tmp_path / "changed", bundle)
    try:
        (stage.path / "bin/blender-mcp-managed").write_text("changed\n")
        assert not inspect_runtime(TreeRef(root, stage.relative), bundle.manifest).exact
    finally:
        root.close()


@pytest.mark.parametrize(
    "relative,mode",
    [
        ("bin/python", 0o700),
        ("lib/python3.13/site-packages/blmcp/tools/changed.py", 0o600),
        ("lib/python3.13/site-packages/mcp/dependency.py", 0o600),
        ("extra-unmanaged-code.py", 0o600),
    ],
)
def test_complete_runtime_content_is_bound_before_execution(
    tmp_path: Path, relative: str, mode: int
) -> None:
    bundle = _bundle(tmp_path)
    root, stage, runner = _stage(tmp_path, bundle)
    try:
        target = stage.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"changed-after-staging")
        target.chmod(mode)
        before = len(runner.calls)
        assert not inspect_runtime(TreeRef(root, stage.relative), bundle.manifest).exact
        with pytest.raises(InstallerError, match="runtime verification failed"):
            verify_runtime(
                TreeRef(root, stage.relative), bundle.manifest, _profile(tmp_path), runner
            )
        assert len(runner.calls) == before
    finally:
        root.close()


@pytest.mark.parametrize("mutation", ["duplicate", "trailing", "reformatted", "mode"])
def test_marker_requires_exact_canonical_private_bytes_before_execution(
    tmp_path: Path, mutation: str
) -> None:
    bundle = _bundle(tmp_path)
    root, stage, runner = _stage(tmp_path, bundle)
    try:
        marker = stage.path / ".blender-mcp-runtime.json"
        raw = marker.read_bytes()
        if mutation == "duplicate":
            marker.write_bytes(raw.replace(b"{", b'{"schema_version":1,', 1))
        elif mutation == "trailing":
            marker.write_bytes(raw + b" ")
        elif mutation == "reformatted":
            marker.write_text(json.dumps(json.loads(raw), indent=2) + "\n")
        else:
            marker.chmod(0o666)
        before = len(runner.calls)
        assert not inspect_runtime(TreeRef(root, stage.relative), bundle.manifest).exact
        with pytest.raises(InstallerError, match="runtime verification failed"):
            verify_runtime(
                TreeRef(root, stage.relative), bundle.manifest, _profile(tmp_path), runner
            )
        assert len(runner.calls) == before
    finally:
        root.close()


@pytest.mark.parametrize("boundary", ["venv", "lock", "wheel", "cleanup"])
def test_stage_root_remains_fd_bound_at_every_consumption_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    bundle = _bundle(tmp_path)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    with SafeRoot.open(data, os.getuid(), data) as root:
        created = create_deterministic_stage(
            root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(created, StagedTree)
        after_call = {"venv": 0, "lock": 1, "wheel": 2, "cleanup": None}[boundary]
        runner = StageRootSwapRunner(bundle, after_call)
        if boundary == "cleanup":
            remove = runtime_module._remove_private_inputs

            def replace_before_cleanup(stage_fd, inputs):
                if runner.replacement is None:
                    runner.replace(created.path)
                remove(stage_fd, inputs)

            monkeypatch.setattr(runtime_module, "_remove_private_inputs", replace_before_cleanup)
        with pytest.raises(InstallerError, match="runtime stage identity changed"):
            stage_runtime(
                bundle,
                Path("/opt/uv").absolute(),
                Path(sys.executable),
                _profile(tmp_path),
                created,
                runner,
            )
        assert runner.replacement is not None
        assert (runner.replacement / "replacement-sentinel").read_bytes() == (
            b"preserve-replacement"
        )
        if boundary != "venv":
            assert (runner.replacement / bundle.runtime_lock_path.name).exists()
            assert (runner.replacement / bundle.wheel_path.name).exists()
        assert not any(
            len(argv) == 4 and argv[1:3] == ("-I", "-c") for argv, _cwd, _env in runner.calls
        )


@pytest.mark.parametrize("role", ["lock", "wheel"])
@pytest.mark.parametrize("after_call", [0, 1, 2])
@pytest.mark.parametrize("mutation", ["replace", "rewrite"])
def test_bundle_inputs_remain_fd_bound_at_every_runner_boundary(
    tmp_path: Path, role: str, after_call: int, mutation: str
) -> None:
    bundle = _bundle(tmp_path, copy=True)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    with SafeRoot.open(data, os.getuid(), data) as root:
        created = create_deterministic_stage(
            root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(created, StagedTree)
        runner = BundleSwapRunner(bundle, role, after_call, mutation)
        with pytest.raises(InstallerError, match="runtime installer input changed"):
            stage_runtime(
                bundle,
                Path("/opt/uv").absolute(),
                Path(sys.executable),
                _profile(tmp_path),
                created,
                runner,
            )
        assert runner.swapped
        assert not any(
            len(argv) == 4 and argv[1:3] == ("-I", "-c") for argv, _cwd, _env in runner.calls
        )


def test_runtime_tree_uses_task3_forward_and_reverse_states(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    root, staged, _runner = _stage(tmp_path, bundle)
    target = TreeRef(root, PurePath("runtime"))
    recovery = TreeRef(root, PurePath("runtime.recovery"))
    try:
        pre = target.capture()
        assert (
            forward_tree(target, pre, staged, recovery, NoOpFaultInjector())
            is NativeState.PUBLISHED
        )
        assert (
            forward_tree(target, pre, staged, recovery, NoOpFaultInjector())
            is NativeState.COMPLETED
        )
        installed = target.capture()
        assert installed == staged.image
        forward_stage = StagedTree(root, staged.relative, staged.image)
        assert (
            restore_tree(
                target,
                pre,
                installed,
                forward_stage,
                recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORING
        )
        assert (
            restore_tree(
                target,
                pre,
                installed,
                forward_stage,
                recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORED
        )
        assert target.capture() == TreeImage.absent()
    finally:
        root.close()


def test_present_runtime_retains_preimage_and_fresh_process_restores_p2(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    data = tmp_path / "data"
    runtime = data / "runtime"
    runtime.mkdir(mode=0o700, parents=True)
    (runtime / "old").write_bytes(b"retained-preimage")
    (runtime / "old").chmod(0o600)
    root = SafeRoot.open(data, os.getuid(), data)
    pre = TreeRef(root, PurePath("runtime")).capture()
    created = create_deterministic_stage(
        root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
    )
    assert isinstance(created, StagedTree)
    runner = RuntimeRunner(bundle)
    post = stage_runtime(
        bundle,
        Path("/opt/uv").absolute(),
        Path(sys.executable),
        _profile(tmp_path),
        created,
        runner,
    )
    staged = created.with_image(post)
    target = TreeRef(root, PurePath("runtime"))
    recovery = TreeRef(root, PurePath("runtime.recovery"))
    assert forward_tree(target, pre, staged, recovery, NoOpFaultInjector()) is NativeState.SWAPPED
    assert forward_tree(target, pre, staged, recovery, NoOpFaultInjector()) is NativeState.PARKED
    assert forward_tree(target, pre, staged, recovery, NoOpFaultInjector()) is NativeState.COMPLETED
    assert recovery.capture() == pre
    root.close()

    with SafeRoot.open(data, os.getuid(), data) as reopened:
        fresh_target = TreeRef(reopened, PurePath("runtime"))
        fresh_stage = StagedTree(reopened, PurePath("runtime.stage"), post)
        fresh_recovery = TreeRef(reopened, PurePath("runtime.recovery"))
        assert (
            restore_tree(
                fresh_target,
                pre,
                post,
                fresh_stage,
                fresh_recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORING
        )
        assert (
            restore_tree(
                fresh_target,
                pre,
                post,
                fresh_stage,
                fresh_recovery,
                NoOpFaultInjector(),
            )
            is RestoreState.RESTORED
        )
        assert fresh_target.capture() == pre
        assert (runtime / "old").read_bytes() == b"retained-preimage"


def test_foreign_installed_runtime_edit_conflicts_without_deletion(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    root, staged, _runner = _stage(tmp_path, bundle)
    target = TreeRef(root, PurePath("runtime"))
    recovery = TreeRef(root, PurePath("runtime.recovery"))
    try:
        pre = target.capture()
        post = staged.image
        assert (
            forward_tree(target, pre, staged, recovery, NoOpFaultInjector())
            is NativeState.PUBLISHED
        )
        foreign = target.path / "foreign"
        foreign.write_bytes(b"foreign-edit")
        foreign.chmod(0o600)
        with pytest.raises(InstallerError, match="transaction state conflict"):
            restore_tree(target, pre, post, staged, recovery, NoOpFaultInjector())
        assert foreign.read_bytes() == b"foreign-edit"
    finally:
        root.close()


def test_deterministic_stage_collision_fails_without_uv_calls(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    with SafeRoot.open(data, os.getuid(), data) as root:
        create_deterministic_stage(root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector())
        with pytest.raises(InstallerError, match="deterministic stage already exists"):
            create_deterministic_stage(
                root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
            )
