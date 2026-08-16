from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path, PurePath
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer import blender_adapter  # noqa: E402
from blender_mcp_installer.blender_adapter import (  # noqa: E402
    BlenderAuthorizations,
    compare_extension_tree,
    inspect_blender,
    load_extension_payload,
    prepare_extension_for_restore,
    probe_blender_lifecycle,
    resolve_blender_paths,
    stage_blender_change,
    verify_blender_files,
)
from blender_mcp_installer.filesystem import (  # noqa: E402
    InstallerError,
    SafeRoot,
    TreeRef,
)


EXTENSION_ZIP = ROOT / "plugins/blender-mcp-installer/artifacts/mcp-1.0.0.zip"


def _private(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o700)
    return path


def _profile(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    home = _private(tmp_path / "non-default-home")
    resources = _private(tmp_path / "profiles/custom/resources")
    config = _private(resources / "configuration")
    extensions = _private(resources / "extension-store")
    return resources, {
        "HOME": str(home),
        "BLENDER_USER_RESOURCES": str(resources),
        "BLENDER_USER_CONFIG": str(config),
        "BLENDER_USER_EXTENSIONS": str(extensions),
        "BLENDER_MCP_HOST": "hostile.example",
        "BLENDER_MCP_PORT": "1",
        "PYTHONPATH": "/hostile/python",
    }


class BlenderRunner:
    def __init__(
        self,
        blender: Path,
        *,
        architecture: str = "arm64",
        arches: str = "arm64\n",
        reported_binary: Path | None = None,
        repository: str = "user_default",
        enabled: bool = False,
        online_access: bool = False,
        host: str | None = None,
        port: int | None = None,
        autostart: bool | None = None,
    ):
        self.blender = blender
        self.architecture = architecture
        self.arches = arches
        self.reported_binary = reported_binary or blender
        self.repository = repository
        self.enabled = enabled
        self.online_access = online_access
        self.host = host
        self.port = port
        self.autostart = autostart
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []
        self.mutated: list[Path] = []

    def _state(self, env: dict[str, str]) -> dict[str, object]:
        config = Path(env["BLENDER_USER_CONFIG"])
        preferences = config / "userpref.blend"
        staged = preferences.exists() and b"TASK5-PREFERENCES" in preferences.read_bytes()
        return {
            "binary_path": str(self.reported_binary),
            "version": [5, 2, 0],
            "architecture": self.architecture,
            "user_resources": env["BLENDER_USER_RESOURCES"],
            "config_root": env["BLENDER_USER_CONFIG"],
            "extensions_root": env["BLENDER_USER_EXTENSIONS"],
            "repository": self.repository,
            "enabled": True if staged else self.enabled,
            "online_access": True if staged else self.online_access,
            "host": "localhost" if staged else self.host,
            "port": 9876 if staged else self.port,
            "autostart": True if staged else self.autostart,
        }

    def __call__(self, argv, *, cwd: Path, env):
        args = tuple(str(value) for value in argv)
        clean = dict(env)
        self.calls.append((args, cwd, clean))
        if args[:2] == ("/usr/bin/lipo", "-archs"):
            return SimpleNamespace(returncode=0, stdout=self.arches, stderr="")
        if args[:3] == (str(self.blender), "--command", "extension"):
            if args[3] == "validate":
                return SimpleNamespace(returncode=0, stdout="valid\n", stderr="")
            assert args[3:7] == ("install-file", "--repo", "user_default", "--enable")
            target = Path(clean["BLENDER_USER_EXTENSIONS"]) / "user_default/mcp"
            target.mkdir(parents=True)
            with zipfile.ZipFile(args[7]) as archive:
                archive.extractall(target)
            for file in target.rglob("*"):
                if file.is_file():
                    file.chmod(0o644)
            self.mutated.append(target)
            return SimpleNamespace(returncode=0, stdout="installed\n", stderr="")
        if args[:2] == (str(self.blender), "--background"):
            expression = args[-1]
            if "save_userpref" in expression:
                target = Path(clean["BLENDER_USER_CONFIG"]) / "userpref.blend"
                before = target.read_bytes() if target.exists() else b""
                target.write_bytes(before + b"TASK5-PREFERENCES\n")
                target.chmod(0o600)
                self.mutated.append(target)
            payload = json.dumps(self._state(clean), sort_keys=True)
            return SimpleNamespace(
                returncode=0,
                stdout=f"Blender log\n__BLENDER_MCP_INSTALLER__{payload}\n",
                stderr="",
            )
        raise AssertionError(args)


def _installed_profile(resources: Path, env: dict[str, str]) -> None:
    target = Path(env["BLENDER_USER_EXTENSIONS"]) / "user_default/mcp"
    target.mkdir(parents=True)
    with zipfile.ZipFile(EXTENSION_ZIP) as archive:
        archive.extractall(target)
    for file in target.rglob("*"):
        if file.is_file():
            file.chmod(0o644)
    (Path(env["BLENDER_USER_CONFIG"]) / "userpref.blend").write_bytes(b"preferences")
    del resources


def _tree_ref(path: Path) -> tuple[SafeRoot, TreeRef]:
    root = SafeRoot.open(path.parent, os.getuid(), path.parent)
    return root, TreeRef(root, PurePath(path.name))


def test_inspect_uses_one_expression_and_exact_allowlisted_profile(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Applications/Custom Blender.app/Contents/MacOS/Blender")
    resources, env = _profile(tmp_path)
    _installed_profile(resources, env)
    runner = BlenderRunner(
        blender,
        enabled=True,
        online_access=True,
        host="localhost",
        port=9876,
        autostart=True,
    )

    state = inspect_blender(blender, env, runner)

    assert state.executable == blender
    assert state.executable_arches == ("arm64",)
    assert state.reported_binary == blender
    assert state.reported_architecture == "arm64"
    assert state.version == "5.2.0"
    assert state.user_resources == resources
    assert state.config_root == Path(env["BLENDER_USER_CONFIG"])
    assert state.extensions_root == Path(env["BLENDER_USER_EXTENSIONS"])
    assert state.userpref == state.config_root / "userpref.blend"
    assert state.extension_root == state.extensions_root / "user_default/mcp"
    assert (state.manifest_id, state.manifest_version) == ("mcp", "1.0.0")
    assert (state.enabled, state.online_access, state.host, state.port, state.autostart) == (
        True,
        True,
        "localhost",
        9876,
        True,
    )
    expected = load_extension_payload(EXTENSION_ZIP)
    assert state.canonical_payload_digest == expected.canonical_digest
    blender_calls = [call for call in runner.calls if call[0][0] == str(blender)]
    assert len(blender_calls) == 1
    argv, cwd, call_env = blender_calls[0]
    assert argv[:3] == (str(blender), "--background", "--python-expr")
    assert cwd == blender.parent
    assert call_env == {
        "HOME": env["HOME"],
        "BLENDER_USER_RESOURCES": env["BLENDER_USER_RESOURCES"],
        "BLENDER_USER_CONFIG": env["BLENDER_USER_CONFIG"],
        "BLENDER_USER_EXTENSIONS": env["BLENDER_USER_EXTENSIONS"],
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PATH": f"{blender.parent}:/usr/bin:/bin:/usr/sbin:/sbin",
    }


@pytest.mark.parametrize("failure", ["missing_resources", "config_escape", "reported_escape"])
def test_profile_discovery_rejects_missing_root_or_resource_escape(
    tmp_path: Path, failure: str
) -> None:
    blender = _executable(tmp_path / "Blender")
    resources, env = _profile(tmp_path)
    runner = BlenderRunner(blender)
    if failure == "missing_resources":
        env.pop("BLENDER_USER_RESOURCES")
    elif failure == "config_escape":
        env["BLENDER_USER_CONFIG"] = str(tmp_path / "outside")
    else:
        runner = BlenderRunner(blender)
        original = runner._state

        def escaped(call_env):
            state = original(call_env)
            state["extensions_root"] = str(tmp_path / "outside")
            return state

        runner._state = escaped
    with pytest.raises((ValueError, InstallerError)):
        resolve_blender_paths(blender, env, runner)


@pytest.mark.parametrize("failure", ["symlink", "not_executable", "non_arm64", "reported_binary"])
def test_executable_identity_is_non_symlink_executable_arm64(tmp_path: Path, failure: str) -> None:
    real = _executable(tmp_path / "real/Blender")
    blender = real
    resources, env = _profile(tmp_path)
    runner = BlenderRunner(blender)
    if failure == "symlink":
        blender = tmp_path / "Blender"
        blender.symlink_to(real)
        runner = BlenderRunner(blender)
    elif failure == "not_executable":
        real.chmod(0o600)
    elif failure == "non_arm64":
        runner.arches = "x86_64\n"
    else:
        runner.reported_binary = _executable(tmp_path / "other/Blender")
    with pytest.raises((ValueError, InstallerError)):
        inspect_blender(blender, env, runner)


def test_symlinked_reported_resource_component_is_rejected(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    resources, env = _profile(tmp_path)
    config = Path(env["BLENDER_USER_CONFIG"])
    config.rmdir()
    config.symlink_to(_private(tmp_path / "other-config"), target_is_directory=True)
    with pytest.raises((ValueError, InstallerError)):
        inspect_blender(blender, env, BlenderRunner(blender))
    assert resources.exists()


@pytest.mark.parametrize("failure", ["traversal", "wrong_id", "wrong_version"])
def test_extension_zip_rejects_unsafe_entry_or_wrong_manifest_before_staging(
    tmp_path: Path, failure: str
) -> None:
    archive = tmp_path / "bad.zip"
    manifest = 'id = "mcp"\nversion = "1.0.0"\n'
    if failure == "wrong_id":
        manifest = manifest.replace('id = "mcp"', 'id = "other"')
    elif failure == "wrong_version":
        manifest = manifest.replace('version = "1.0.0"', 'version = "2.0.0"')
    with zipfile.ZipFile(archive, "w") as target:
        item = zipfile.ZipInfo("blender_manifest.toml")
        item.create_system = 3
        item.external_attr = 0o100644 << 16
        target.writestr(item, manifest)
        if failure == "traversal":
            hostile = zipfile.ZipInfo("../outside.py")
            hostile.create_system = 3
            hostile.external_attr = 0o100644 << 16
            target.writestr(hostile, "x")
    with pytest.raises(ValueError):
        load_extension_payload(archive)


def test_payload_policy_detects_missing_changed_and_foreign_extra(tmp_path: Path) -> None:
    expected = load_extension_payload(EXTENSION_ZIP)
    target = tmp_path / "mcp"
    target.mkdir()
    with zipfile.ZipFile(EXTENSION_ZIP) as archive:
        archive.extractall(target)
    for file in target.rglob("*"):
        if file.is_file():
            file.chmod(0o644)
    root, reference = _tree_ref(target)
    try:
        assert compare_extension_tree(expected, reference).exact
        missing = target / "cli.py"
        saved = missing.read_bytes()
        missing.unlink()
        comparison = compare_extension_tree(expected, reference)
        assert comparison.missing == ("cli.py",)
        missing.write_bytes(saved)
        missing.chmod(0o644)
        (target / "capture_output.py").write_text("changed")
        comparison = compare_extension_tree(expected, reference)
        assert comparison.changed == ("capture_output.py",)
        with zipfile.ZipFile(EXTENSION_ZIP) as archive:
            (target / "capture_output.py").write_bytes(archive.read("capture_output.py"))
        (target / "capture_output.py").chmod(0o644)
        (target / "foreign.txt").write_text("foreign")
        comparison = compare_extension_tree(expected, reference)
        assert comparison.foreign == ("foreign.txt",)
    finally:
        root.close()


def test_only_source_mapped_current_uid_pyc_is_disposable_and_removed_fd_relatively(
    tmp_path: Path,
) -> None:
    expected = load_extension_payload(EXTENSION_ZIP)
    target = tmp_path / "mcp"
    target.mkdir()
    with zipfile.ZipFile(EXTENSION_ZIP) as archive:
        archive.extractall(target)
    for file in target.rglob("*"):
        if file.is_file():
            file.chmod(0o644)
    subprocess.run(
        [sys.executable, "-I", "-c", "import sys;sys.path.insert(0,'.');import capture_output"],
        cwd=target,
        check=True,
    )
    cache = target / "__pycache__"
    pyc = next(cache.glob("capture_output.*.pyc"))
    root, reference = _tree_ref(target)
    try:
        comparison = compare_extension_tree(expected, reference)
        assert comparison.exact
        assert comparison.disposable_pyc == (f"__pycache__/{pyc.name}",)
        image = prepare_extension_for_restore(comparison)
        assert not cache.exists()
        assert image.state.value == "present"
        assert compare_extension_tree(expected, reference).exact
    finally:
        root.close()


@pytest.mark.parametrize(
    "extra",
    ["__pycache__/foreign.cpython-313.pyc", "nested/cache.pyc", "__pycache__/cli.txt"],
)
def test_unmapped_or_malformed_cache_extra_conflicts(tmp_path: Path, extra: str) -> None:
    expected = load_extension_payload(EXTENSION_ZIP)
    target = tmp_path / "mcp"
    target.mkdir()
    with zipfile.ZipFile(EXTENSION_ZIP) as archive:
        archive.extractall(target)
    for file in target.rglob("*"):
        if file.is_file():
            file.chmod(0o644)
    path = target / extra
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"extra")
    root, reference = _tree_ref(target)
    try:
        assert not compare_extension_tree(expected, reference).exact
    finally:
        root.close()


def test_staging_empty_profile_mutates_only_private_stage_and_sets_exact_preferences(
    tmp_path: Path,
) -> None:
    blender = _executable(tmp_path / "Applications/Blender.app/Contents/MacOS/Blender")
    resources, env = _profile(tmp_path)
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    before = sorted(path.relative_to(resources) for path in resources.rglob("*"))
    stage = tmp_path / "transaction/private-blender"

    change = stage_blender_change(
        state,
        EXTENSION_ZIP,
        stage,
        BlenderAuthorizations(True, True, True, True),
        runner,
    )

    assert change.changed
    assert change.extension_path == stage / "resources/extensions/user_default/mcp"
    assert change.userpref_path == stage / "resources/config/userpref.blend"
    assert change.extension_image.state.value == "present"
    assert change.userpref_image.state.value == "present"
    assert change.staged_state.enabled
    assert change.staged_state.online_access
    assert change.staged_state.host == "localhost"
    assert change.staged_state.port == 9876
    assert change.staged_state.autostart
    assert sorted(path.relative_to(resources) for path in resources.rglob("*")) == before
    assert all(path.is_relative_to(stage) for path in runner.mutated)
    mutating = [
        call
        for call in runner.calls
        if "validate" in call[0] or "install-file" in call[0] or "save_userpref" in call[0][-1]
    ]
    assert [call[0][3] if call[0][1] == "--command" else "preferences" for call in mutating] == [
        "validate",
        "install-file",
        "preferences",
    ]
    for _, _, call_env in runner.calls[-4:]:
        assert call_env["BLENDER_MCP_HOST"] == "localhost"
        assert call_env["BLENDER_MCP_PORT"] == "9876"
        assert "PYTHONPATH" not in call_env


def test_staging_copies_existing_userpref_but_absent_profile_starts_without_copy(
    tmp_path: Path,
) -> None:
    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    userpref = Path(env["BLENDER_USER_CONFIG"]) / "userpref.blend"
    userpref.write_bytes(b"KEEP-EXISTING-PREFERENCES\n")
    userpref.chmod(0o600)
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    change = stage_blender_change(
        state,
        EXTENSION_ZIP,
        tmp_path / "with-preimage",
        BlenderAuthorizations(True, True, True, True),
        runner,
    )
    assert change.userpref_path.read_bytes().startswith(b"KEEP-EXISTING-PREFERENCES")
    userpref.unlink()
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    change = stage_blender_change(
        state,
        EXTENSION_ZIP,
        tmp_path / "absent-preimage",
        BlenderAuthorizations(True, True, True, True),
        runner,
    )
    assert change.userpref_path.read_bytes() == b"TASK5-PREFERENCES\n"


def test_exact_state_is_noop_and_missing_consent_precedes_stage_creation(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    resources, env = _profile(tmp_path)
    _installed_profile(resources, env)
    runner = BlenderRunner(
        blender,
        enabled=True,
        online_access=True,
        host="localhost",
        port=9876,
        autostart=True,
    )
    state = inspect_blender(blender, env, runner)
    before = len(runner.calls)
    stage = tmp_path / "must-not-exist"
    change = stage_blender_change(
        state,
        EXTENSION_ZIP,
        stage,
        BlenderAuthorizations(True, True, True, True),
        runner,
    )
    assert not change.changed
    assert not stage.exists()
    assert len(runner.calls) == before
    with pytest.raises(ValueError, match="authorizations"):
        stage_blender_change(
            state,
            EXTENSION_ZIP,
            tmp_path / "unauthorized",
            BlenderAuthorizations(True, False, True, True),
            runner,
        )
    assert not (tmp_path / "unauthorized").exists()


def test_wrong_manifest_and_preferences_fail_file_verification(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    resources, env = _profile(tmp_path)
    _installed_profile(resources, env)
    runner = BlenderRunner(
        blender, enabled=True, online_access=True, host="localhost", port=9876, autostart=True
    )
    state = inspect_blender(blender, env, runner)
    verify_blender_files(state, load_extension_payload(EXTENSION_ZIP))
    manifest = state.extension_root / "blender_manifest.toml"
    manifest.write_text(manifest.read_text().replace('version = "1.0.0"', 'version = "9.9.9"'))
    with pytest.raises(InstallerError):
        verify_blender_files(state, load_extension_payload(EXTENSION_ZIP))


def _lsof(
    pid: int,
    executable: Path,
    *,
    uid: int | None = None,
    dev: int | None = None,
    ino: int | None = None,
    dyld: bool = False,
) -> str:
    info = executable.stat()
    records = []
    if dyld:
        records.append("ftxt\nD1\ni1\nn/usr/lib/dyld\n")
    records.append(
        f"ftxt\nD{info.st_dev if dev is None else dev}\ni{info.st_ino if ino is None else ino}\nn{executable}\n"
    )
    return f"p{pid}\ncBlender\nu{os.getuid() if uid is None else uid}\n" + "".join(records)


def _listener(pid: int, *, uid: int | None = None) -> str:
    return (
        f"p{pid}\ncBlender\nu{os.getuid() if uid is None else uid}\n"
        "f12u\nD1\ni2\nnTCP 127.0.0.1:9876 (LISTEN)\n"
    )


class LifecycleRunner:
    def __init__(self, pgrep: str, txt: dict[int, str], listener: str = "", listener_code: int = 1):
        self.pgrep = pgrep
        self.txt = txt
        self.listener = listener
        self.listener_code = listener_code
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv, *, cwd: Path, env):
        args = tuple(str(value) for value in argv)
        self.calls.append(args)
        assert cwd == Path("/")
        assert dict(env) == {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        if args == ("/usr/bin/pgrep", "-x", "Blender"):
            return SimpleNamespace(returncode=0 if self.pgrep else 1, stdout=self.pgrep, stderr="")
        if args[:4] == ("/usr/sbin/lsof", "-a", "-p", args[3]):
            return SimpleNamespace(returncode=0, stdout=self.txt[int(args[3])], stderr="")
        if args == ("/usr/sbin/lsof", "-nP", "-iTCP:9876", "-sTCP:LISTEN", "-FpcfDinu"):
            return SimpleNamespace(returncode=self.listener_code, stdout=self.listener, stderr="")
        raise AssertionError(args)


def test_lifecycle_matches_selected_process_with_dyld_and_selected_listener(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    runner = LifecycleRunner(
        "101\n102\n",
        {
            101: _lsof(101, blender, dyld=True),
            102: _lsof(102, _executable(tmp_path / "other/Blender")),
        },
        _listener(101),
        0,
    )
    state = probe_blender_lifecycle(blender, runner)
    assert state.matching_selected_pids == (101,)
    assert state.listener_pid == 101
    assert state.listener_executable == blender
    assert not state.port_free
    assert all(call[0] in {"/usr/bin/pgrep", "/usr/sbin/lsof"} for call in runner.calls)


def test_lifecycle_reports_free_port_and_foreign_listener_identity(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    foreign = _executable(tmp_path / "foreign/Blender")
    free = probe_blender_lifecycle(blender, LifecycleRunner("", {}))
    assert free.matching_selected_pids == ()
    assert free.listener_pid is None and free.listener_executable is None and free.port_free
    runner = LifecycleRunner("", {77: _lsof(77, foreign)}, _listener(77), 0)
    occupied = probe_blender_lifecycle(blender, runner)
    assert occupied.listener_pid == 77
    assert occupied.listener_executable == foreign
    assert not occupied.port_free


@pytest.mark.parametrize(
    "pgrep,txt,listener,listener_code",
    [
        ("not-a-pid\n", {}, "", 1),
        ("10\n", {10: "p10\ncBlender\nu501\nftxt\nD1\ni2\n"}, "", 1),
        ("10\n", {10: "p10\ncBlender\nu501\nu501\nftxt\nD1\ni2\nn/x/Blender\n"}, "", 1),
        ("", {10: ""}, _listener(10) + _listener(11), 0),
    ],
)
def test_lifecycle_rejects_malformed_duplicate_or_ambiguous_records(
    tmp_path: Path, pgrep: str, txt: dict[int, str], listener: str, listener_code: int
) -> None:
    blender = _executable(tmp_path / "Blender")
    runner = LifecycleRunner(pgrep, txt, listener, listener_code)
    with pytest.raises(InstallerError):
        probe_blender_lifecycle(blender, runner)


@pytest.mark.parametrize("failure", ["wrong_uid", "same_path_wrong_inode", "multiple_executables"])
def test_lifecycle_fails_closed_on_selected_executable_identity_ambiguity(
    tmp_path: Path, failure: str
) -> None:
    blender = _executable(tmp_path / "Blender")
    output = _lsof(10, blender)
    if failure == "wrong_uid":
        output = _lsof(10, blender, uid=os.getuid() + 1)
    elif failure == "same_path_wrong_inode":
        output = _lsof(10, blender, ino=blender.stat().st_ino + 1)
    else:
        info = blender.stat()
        output += f"ftxt\nD{info.st_dev}\ni{info.st_ino}\nn{blender}\n"
    with pytest.raises(InstallerError):
        probe_blender_lifecycle(blender, LifecycleRunner("10\n", {10: output}))


@pytest.mark.skipif(sys.platform != "darwin", reason="disposable lsof parser probe is Darwin-only")
def test_disposable_live_process_lsof_output_is_accepted_by_strict_parser() -> None:
    completed = subprocess.run(
        ["/usr/sbin/lsof", "-a", "-p", str(os.getpid()), "-d", "txt", "-FpcfDinu"],
        check=True,
        capture_output=True,
        text=True,
    )
    processes = blender_adapter._parse_lsof_processes(completed.stdout)
    assert len(processes) == 1
    assert processes[0].pid == os.getpid()
    assert processes[0].uid == os.getuid()
    assert processes[0].files
