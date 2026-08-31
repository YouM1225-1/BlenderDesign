from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import py_compile
import shutil
import socket
import stat
import subprocess
import sys
import zipfile
from dataclasses import replace
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
    verify_blender_payload,
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
        resources = env.get("BLENDER_USER_RESOURCES", str(Path(env["HOME"]) / "normal/resources"))
        config_value = env.get("BLENDER_USER_CONFIG", str(Path(resources) / "config"))
        extensions = env.get("BLENDER_USER_EXTENSIONS", str(Path(resources) / "extensions"))
        config = Path(config_value)
        preferences = config / "userpref.blend"
        staged = preferences.exists() and b"TASK5-PREFERENCES" in preferences.read_bytes()
        return {
            "binary_path": str(self.reported_binary),
            "version": [5, 2, 0],
            "architecture": self.architecture,
            "user_resources": resources,
            "config_root": config_value,
            "extensions_root": extensions,
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
            if "py_compile.compile" in expression:
                target = Path(clean["BLENDER_USER_EXTENSIONS"]) / "user_default/mcp"
                for source in sorted(target.rglob("*.py")):
                    relative = source.relative_to(target).as_posix()
                    cache = Path(importlib.util.cache_from_source(str(source), optimization=""))
                    py_compile.compile(
                        str(source),
                        cfile=str(cache),
                        dfile=relative,
                        doraise=True,
                        optimize=0,
                        invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH,
                    )
                    cache.parent.chmod(0o755)
                    cache.chmod(0o644)
                self.mutated.append(target)
            if "save_userpref" in expression:
                target = Path(clean["BLENDER_USER_CONFIG"]) / "userpref.blend"
                before = target.read_bytes() if target.exists() else b""
                target.write_bytes(before + b"TASK5-PREFERENCES\n")
                target.chmod(0o600)
                self.mutated.append(target)
            payload = json.dumps(self._state(clean), sort_keys=True)
            if "--factory-startup" in args:
                state = self._state(clean)
                payload = json.dumps(
                    {
                        key: state[key]
                        for key in (
                            "binary_path",
                            "version",
                            "architecture",
                            "user_resources",
                            "config_root",
                            "extensions_root",
                        )
                    },
                    sort_keys=True,
                )
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
        "PYTHONDONTWRITEBYTECODE": "1",
    }


@pytest.mark.parametrize("failing_probe", [False, True])
def test_read_only_blender_probe_suppresses_bytecode_on_success_and_failure(
    tmp_path: Path, failing_probe: bool
) -> None:
    blender = _executable(tmp_path / "Blender")
    resources, env = _profile(tmp_path)
    env["PYTHONDONTWRITEBYTECODE"] = "0"
    _installed_profile(resources, env)
    extension = Path(env["BLENDER_USER_EXTENSIONS"]) / "user_default/mcp"

    class BytecodeProbeRunner(BlenderRunner):
        def __call__(self, argv, *, cwd: Path, env):
            args = tuple(map(str, argv))
            if (
                args[:2] == (str(blender), "--background")
                and dict(env).get("PYTHONDONTWRITEBYTECODE") != "1"
            ):
                source = extension / "cli.py"
                py_compile.compile(str(source), doraise=True)
            result = super().__call__(argv, cwd=cwd, env=env)
            if failing_probe and args[:2] == (str(blender), "--background"):
                return SimpleNamespace(returncode=0, stdout="invalid\n", stderr="")
            return result

    runner = BytecodeProbeRunner(
        blender,
        enabled=True,
        online_access=True,
        host="localhost",
        port=9876,
        autostart=True,
    )
    before = tuple(sorted(path.relative_to(extension) for path in extension.rglob("*")))
    if failing_probe:
        with pytest.raises(InstallerError):
            inspect_blender(blender, env, runner)
    else:
        inspect_blender(blender, env, runner)
    assert tuple(sorted(path.relative_to(extension) for path in extension.rglob("*"))) == before
    assert all(
        call_env["PYTHONDONTWRITEBYTECODE"] == "1"
        for args, _, call_env in runner.calls
        if args[0] in {"/usr/bin/lipo", str(blender)}
    )


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


def test_path_discovery_is_factory_startup_and_omits_live_profile(
    tmp_path: Path,
) -> None:
    blender = _executable(tmp_path / "Blender")
    home = _private(tmp_path / "home")
    runner = BlenderRunner(blender)

    paths = resolve_blender_paths(blender, {"HOME": str(home)}, runner)

    assert paths.user_resources == home / "normal/resources"
    blender_call = next(call for call in runner.calls if call[0][0] == str(blender))
    assert blender_call[0][:3] == (str(blender), "--background", "--factory-startup")
    assert blender_call[2] == {
        "HOME": str(home),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PATH": f"{blender.parent}:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


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


def _zip_entry(name: str, raw: bytes | str, mode: int) -> tuple[zipfile.ZipInfo, bytes | str]:
    item = zipfile.ZipInfo(name)
    item.create_system = 3
    item.external_attr = mode << 16
    return item, raw


@pytest.mark.parametrize(
    "case",
    [
        "dot_component",
        "repeated_separator",
        "exact_duplicate",
        "alias_duplicate",
        "symlink",
        "special",
        "setuid",
        "world_writable",
        "executable_file",
        "wrong_directory_mode",
    ],
)
@pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")
def test_noncanonical_or_nonexact_zip_entry_is_rejected_before_runner_or_stage(
    tmp_path: Path, case: str
) -> None:
    archive = tmp_path / f"{case}.zip"
    entries = [
        _zip_entry("blender_manifest.toml", 'id = "mcp"\nversion = "1.0.0"\n', stat.S_IFREG | 0o644)
    ]
    if case == "dot_component":
        entries.append(_zip_entry("pkg/./x.py", "x", stat.S_IFREG | 0o644))
    elif case == "repeated_separator":
        entries.append(_zip_entry("pkg//x.py", "x", stat.S_IFREG | 0o644))
    elif case == "exact_duplicate":
        entries.extend(
            [
                _zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o644),
                _zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o644),
            ]
        )
    elif case == "alias_duplicate":
        entries.extend(
            [
                _zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o644),
                _zip_entry("pkg/./x.py", "x", stat.S_IFREG | 0o644),
            ]
        )
    elif case == "symlink":
        entries.append(_zip_entry("pkg/x.py", "target", stat.S_IFLNK | 0o777))
    elif case == "special":
        entries.append(_zip_entry("pkg/x.py", "x", stat.S_IFIFO | 0o644))
    elif case == "setuid":
        entries.append(_zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o4644))
    elif case == "world_writable":
        entries.append(_zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o666))
    elif case == "executable_file":
        entries.append(_zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o755))
    else:
        entries.append(_zip_entry("pkg/", b"", stat.S_IFDIR | 0o700))
    with zipfile.ZipFile(archive, "w") as target:
        for item, raw in entries:
            target.writestr(item, raw)

    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    runner.calls.clear()
    stage = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        stage_blender_change(
            state,
            archive,
            stage,
            BlenderAuthorizations(True, True, True, True),
            runner,
        )
    assert runner.calls == []
    assert not stage.exists()


def test_extension_zip_rejects_bounded_expansion(tmp_path: Path, monkeypatch) -> None:
    archive = tmp_path / "expanded.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as target:
        item, raw = _zip_entry(
            "blender_manifest.toml",
            b'id = "mcp"\nversion = "1.0.0"\n' + b" " * 1024,
            stat.S_IFREG | 0o644,
        )
        target.writestr(item, raw)
    monkeypatch.setattr(blender_adapter, "_MAX_ARCHIVE", 512)
    with pytest.raises(ValueError):
        load_extension_payload(archive)


def test_directory_entries_use_canonical_zero_size_in_tree_digest(tmp_path: Path) -> None:
    archive = tmp_path / "directory.zip"
    with zipfile.ZipFile(archive, "w") as target:
        for item, raw in (
            _zip_entry(
                "blender_manifest.toml",
                'id = "mcp"\nversion = "1.0.0"\n',
                stat.S_IFREG | 0o644,
            ),
            _zip_entry("pkg/", b"", stat.S_IFDIR | 0o755),
            _zip_entry("pkg/x.py", "x", stat.S_IFREG | 0o644),
        ):
            target.writestr(item, raw)
    payload = load_extension_payload(archive)
    target = tmp_path / "mcp"
    target.mkdir()
    with zipfile.ZipFile(archive) as source:
        source.extractall(target)
    (target / "blender_manifest.toml").chmod(0o644)
    (target / "pkg").chmod(0o755)
    (target / "pkg/x.py").chmod(0o644)
    root, reference = _tree_ref(target)
    try:
        image = reference.capture()
        assert compare_extension_tree(payload, reference).exact
        assert blender_adapter._tree_payload_digest(image) == payload.canonical_digest
    finally:
        root.close()


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


def test_unrecorded_source_mapped_current_uid_pyc_is_foreign_and_untouched(
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
    cache = target / "__pycache__"
    cache.mkdir()
    pyc = cache / "cli.cpython-313.pyc"
    pyc.write_bytes(b"arbitrary foreign bytes")
    pyc.chmod(0o644)
    root, reference = _tree_ref(target)
    try:
        comparison = compare_extension_tree(expected, reference)
        before = reference.capture()
        assert not comparison.exact
        assert comparison.disposable_pyc == ()
        assert comparison.foreign == ("__pycache__", f"__pycache__/{pyc.name}")
        with pytest.raises(InstallerError):
            prepare_extension_for_restore(comparison, before)
        assert reference.capture() == before
        assert pyc.read_bytes() == b"arbitrary foreign bytes"
    finally:
        root.close()


def test_stage_deterministically_compiles_complete_pyc_provenance_and_rejects_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    state = inspect_blender(blender, env, BlenderRunner(blender))
    payload = load_extension_payload(EXTENSION_ZIP)
    changes = []
    runners = []
    for name in ("stage-a", "stage-b"):
        runner = BlenderRunner(blender)
        changes.append(
            stage_blender_change(
                state,
                EXTENSION_ZIP,
                tmp_path / name,
                BlenderAuthorizations(True, True, True, True),
                runner,
            )
        )
        runners.append(runner)
    source_paths = {entry.path for entry in payload.entries if entry.path.endswith(".py")}
    pyc_images = []
    for change, runner in zip(changes, runners, strict=True):
        pyc = tuple(
            entry for entry in change.extension_image.entries if entry.path.endswith(".pyc")
        )
        assert len(pyc) == len(source_paths)
        assert all(blender_adapter._mapped_pyc(entry.path, source_paths) for entry in pyc)
        assert "__pycache__" in {entry.path for entry in change.extension_image.entries}
        compile_calls = [
            call
            for call in runner.calls
            if call[0][:2] == (str(blender), "--background") and "py_compile.compile" in call[0][-1]
        ]
        assert len(compile_calls) == 1
        expression = compile_calls[0][0][-1]
        assert all(f"import {PurePath(source).stem}" not in expression for source in source_paths)
        assert compile_calls[0][2]["PYTHONDONTWRITEBYTECODE"] == "1"
        root, reference = _tree_ref(change.extension_path)
        try:
            comparison = compare_extension_tree(payload, reference, change.extension_image)
            assert comparison.exact
            assert comparison.disposable_pyc == tuple(sorted(entry.path for entry in pyc))
            assert prepare_extension_for_restore(comparison, change.extension_image) == (
                change.extension_image
            )
        finally:
            root.close()
        pyc_images.append({entry.path: (entry.mode, entry.size, entry.sha256) for entry in pyc})
    assert pyc_images[0] == pyc_images[1]

    change = changes[0]
    payload_paths = {entry.path for entry in payload.entries}
    extra_paths = {
        entry.path for entry in change.extension_image.entries if entry.path not in payload_paths
    }

    def recorded_image(entries):
        encoded = json.dumps(
            [entry.to_dict() for entry in entries],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return replace(
            change.extension_image,
            uid=entries[0].uid,
            entries=entries,
            digest=hashlib.sha256(encoded).hexdigest(),
        )

    restarted_entries = tuple(
        replace(
            entry,
            dev=entry.dev + 1,
            ino=entry.ino + 1,
            mtime_ns=entry.mtime_ns + 1,
        )
        if entry.path not in payload_paths
        else entry
        for entry in change.extension_image.entries
    )
    restarted_provenance = recorded_image(restarted_entries)
    root, reference = _tree_ref(change.extension_path)
    try:
        comparison = compare_extension_tree(payload, reference, restarted_provenance)
        assert not comparison.exact
        assert set(comparison.changed) == extra_paths
        assert comparison.disposable_pyc == ()
        assert comparison.disposable_dirs == ()
        verify_blender_payload(change.staged_state, payload, restarted_provenance)
        with pytest.raises(InstallerError):
            prepare_extension_for_restore(comparison, restarted_provenance)
    finally:
        root.close()

    recorded_pyc = next(
        entry for entry in change.extension_image.entries if entry.path.endswith(".pyc")
    )
    stable_drifts = (
        {"size": recorded_pyc.size + 1},
        {"sha256": "0" * 64},
        {"mode": 0o600},
        {"kind": "dir", "sha256": None},
    )
    for drift in stable_drifts:
        entries = tuple(
            replace(entry, **drift) if entry.path == recorded_pyc.path else entry
            for entry in change.extension_image.entries
        )
        with pytest.raises(InstallerError):
            verify_blender_payload(change.staged_state, payload, recorded_image(entries))
    foreign_owned = tuple(
        replace(entry, uid=entry.uid + 1) for entry in change.extension_image.entries
    )
    with pytest.raises(InstallerError):
        verify_blender_payload(change.staged_state, payload, recorded_image(foreign_owned))

    recorded_uid = changes[0].extension_image.uid
    assert recorded_uid is not None
    root, reference = _tree_ref(changes[0].extension_path)
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(os, "getuid", lambda: recorded_uid + 1)
            with pytest.raises(ValueError, match="invalid extension pyc provenance"):
                compare_extension_tree(payload, reference, changes[0].extension_image)
    finally:
        root.close()

    foreign = change.extension_path / "__pycache__/cli.cpython-999.pyc"
    foreign.write_bytes(b"foreign")
    foreign.chmod(0o644)
    root, reference = _tree_ref(change.extension_path)
    try:
        comparison = compare_extension_tree(payload, reference, change.extension_image)
        before = reference.capture()
        assert not comparison.exact
        assert comparison.foreign == ("__pycache__/cli.cpython-999.pyc",)
        with pytest.raises(InstallerError):
            prepare_extension_for_restore(comparison, change.extension_image)
        assert reference.capture() == before
        assert foreign.read_bytes() == b"foreign"
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


def test_executable_ancestor_swap_is_rejected_before_blender_runs(tmp_path: Path) -> None:
    selected_dir = _private(tmp_path / "selected")
    blender = _executable(selected_dir / "Blender")
    hostile = _executable(tmp_path / "hostile/Blender")
    parked = tmp_path / "parked"
    _, env = _profile(tmp_path)

    class SwappingRunner(BlenderRunner):
        def __call__(self, argv, *, cwd: Path, env):
            result = super().__call__(argv, cwd=cwd, env=env)
            if tuple(map(str, argv))[:2] == ("/usr/bin/lipo", "-archs"):
                selected_dir.rename(parked)
                selected_dir.symlink_to(hostile.parent, target_is_directory=True)
            return result

    runner = SwappingRunner(blender)
    with pytest.raises((ValueError, InstallerError)):
        inspect_blender(blender, env, runner)
    assert [call[0][0] for call in runner.calls] == ["/usr/bin/lipo"]


def test_source_ancestor_swap_cannot_redirect_payload_read(tmp_path: Path, monkeypatch) -> None:
    source_dir = _private(tmp_path / "source")
    archive = source_dir / "mcp.zip"
    archive.write_bytes(EXTENSION_ZIP.read_bytes())
    archive.chmod(0o600)
    expected = load_extension_payload(archive).canonical_digest
    hostile_dir = _private(tmp_path / "hostile")
    hostile = hostile_dir / "mcp.zip"
    with zipfile.ZipFile(hostile, "w") as target:
        for item, raw in (
            _zip_entry(
                "blender_manifest.toml",
                'id = "mcp"\nversion = "1.0.0"\n',
                stat.S_IFREG | 0o644,
            ),
            _zip_entry("different.py", "hostile", stat.S_IFREG | 0o644),
        ):
            target.writestr(item, raw)
    hostile.chmod(0o600)
    parked = tmp_path / "parked-source"
    original = blender_adapter._component_safe

    def swap_after_validation(path: Path, *, allow_missing: bool) -> None:
        original(path, allow_missing=allow_missing)
        if path == archive:
            source_dir.rename(parked)
            source_dir.symlink_to(hostile_dir, target_is_directory=True)

    monkeypatch.setattr(blender_adapter, "_component_safe", swap_after_validation)
    assert load_extension_payload(archive).canonical_digest == expected


def test_stage_ancestor_swap_is_rejected_before_writes_escape(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    stage = tmp_path / "transaction/stage"
    parked = tmp_path / "parked-stage"
    outside = _private(tmp_path / "outside")

    class SwappingRunner(BlenderRunner):
        def __call__(self, argv, *, cwd: Path, env):
            result = super().__call__(argv, cwd=cwd, env=env)
            args = tuple(map(str, argv))
            if args[:4] == (str(blender), "--command", "extension", "validate"):
                stage.rename(parked)
                stage.symlink_to(outside, target_is_directory=True)
            return result

    runner = SwappingRunner(blender)
    state = inspect_blender(blender, env, runner)
    runner.calls.clear()
    with pytest.raises((ValueError, InstallerError)):
        stage_blender_change(
            state,
            EXTENSION_ZIP,
            stage,
            BlenderAuthorizations(True, True, True, True),
            runner,
        )
    assert list(outside.iterdir()) == []
    assert [call[0][3] for call in runner.calls] == ["validate"]


def test_foreign_owned_stage_parent_fails_before_creation_or_runner(
    tmp_path: Path, monkeypatch
) -> None:
    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    runner.calls.clear()
    parent = _private(tmp_path / "foreign-parent")
    stage = parent / "stage"
    real_open_directory = blender_adapter._open_directory_fd
    real_fstat = os.fstat
    created = False

    def open_directory(path: Path, *, create_private: bool = False) -> int:
        if path == parent:
            return os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        return real_open_directory(path, create_private=create_private)

    def foreign_fstat(fd: int):
        info = real_fstat(fd)
        if (info.st_dev, info.st_ino) == (parent.stat().st_dev, parent.stat().st_ino):
            values = list(info)
            values[4] = os.getuid() + 1
            return os.stat_result(values)
        return info

    def reject_create(parent_fd: int, name: str) -> int:
        nonlocal created
        created = True
        raise AssertionError((parent_fd, name))

    monkeypatch.setattr(blender_adapter, "_open_directory_fd", open_directory)
    monkeypatch.setattr(blender_adapter.os, "fstat", foreign_fstat)
    monkeypatch.setattr(blender_adapter, "_create_private_directory", reject_create)
    with pytest.raises((ValueError, InstallerError)):
        stage_blender_change(
            state,
            EXTENSION_ZIP,
            stage,
            BlenderAuthorizations(True, True, True, True),
            runner,
        )
    assert not created
    assert not stage.exists()
    assert runner.calls == []


@pytest.mark.parametrize("parent_kind", ["existing", "created"])
def test_current_owned_existing_or_created_stage_parent_succeeds(
    tmp_path: Path, parent_kind: str
) -> None:
    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    parent = tmp_path / "owned" / "nested"
    if parent_kind == "existing":
        _private(parent)
    else:
        _private(parent.parent)
    change = stage_blender_change(
        state,
        EXTENSION_ZIP,
        parent / "stage",
        BlenderAuthorizations(True, True, True, True),
        runner,
    )
    assert change.extension_path == parent / "stage/resources/extensions/user_default/mcp"


@pytest.mark.parametrize("failure", ["fstat", "child_fsync", "parent_fsync"])
def test_open_directory_closes_new_child_fd_on_validation_or_fsync_failure(
    tmp_path: Path, monkeypatch, failure: str
) -> None:
    parent = _private(tmp_path / "fd-parent")
    target = parent / ("existing" if failure == "fstat" else "created")
    if failure == "fstat":
        _private(target)
    before = len(os.listdir("/dev/fd"))
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    real_fsync = os.fsync
    tracked: set[int] = set()
    target_child: int | None = None
    child_synced = False

    def tracking_open(*args, **kwargs) -> int:
        nonlocal target_child
        fd = real_open(*args, **kwargs)
        tracked.add(fd)
        if args[0] == target.name and kwargs.get("dir_fd") is not None:
            target_child = fd
        return fd

    def tracking_close(fd: int) -> None:
        tracked.discard(fd)
        real_close(fd)

    def failing_fstat(fd: int):
        if failure == "fstat" and fd == target_child:
            raise OSError("injected child fstat failure")
        return real_fstat(fd)

    def failing_fsync(fd: int) -> None:
        nonlocal child_synced
        if failure == "child_fsync" and fd == target_child:
            raise OSError("injected child fsync failure")
        if failure == "parent_fsync" and child_synced and fd != target_child:
            raise OSError("injected parent fsync failure")
        real_fsync(fd)
        if fd == target_child:
            child_synced = True

    monkeypatch.setattr(blender_adapter.os, "open", tracking_open)
    monkeypatch.setattr(blender_adapter.os, "close", tracking_close)
    monkeypatch.setattr(blender_adapter.os, "fstat", failing_fstat)
    monkeypatch.setattr(blender_adapter.os, "fsync", failing_fsync)
    try:
        with pytest.raises(OSError):
            blender_adapter._open_directory_fd(target, create_private=failure != "fstat")
        assert tracked == set()
        assert len(os.listdir("/dev/fd")) == before
    finally:
        for fd in tuple(tracked):
            real_close(fd)
            tracked.discard(fd)


def test_staged_blender_outputs_and_created_parents_are_fsynced(
    tmp_path: Path, monkeypatch
) -> None:
    blender = _executable(tmp_path / "Blender")
    _, env = _profile(tmp_path)
    stage_parent = _private(tmp_path / "transactions")
    stage = stage_parent / "stage"
    runner = BlenderRunner(blender)
    state = inspect_blender(blender, env, runner)
    synced: set[tuple[int, int]] = set()
    real_fsync = os.fsync

    def recording_fsync(fd: int) -> None:
        info = os.fstat(fd)
        synced.add((info.st_dev, info.st_ino))
        real_fsync(fd)

    monkeypatch.setattr(blender_adapter.os, "fsync", recording_fsync)
    change = stage_blender_change(
        state,
        EXTENSION_ZIP,
        stage,
        BlenderAuthorizations(True, True, True, True),
        runner,
    )
    required = [stage_parent, stage, stage / "resources", stage / "resources/config"]
    required.extend([stage / "resources/extensions", stage / "mcp-1.0.0.zip"])
    required.extend(path for path in change.extension_path.rglob("*"))
    required.extend([change.extension_path, change.userpref_path])
    assert {(path.stat().st_dev, path.stat().st_ino) for path in required} <= synced
    assert stat.S_IMODE(stage.stat().st_mode) == 0o700
    assert stat.S_IMODE((stage / "resources/config").stat().st_mode) == 0o700
    assert stat.S_IMODE((stage / "mcp-1.0.0.zip").stat().st_mode) == 0o600


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


def test_exact_state_is_staged_for_changed_install_and_missing_consent_precedes_stage_creation(
    tmp_path: Path,
) -> None:
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
    stage = tmp_path / "exact-restage"
    live_root, live_extension = _tree_ref(state.extension_root)
    try:
        extension_before = live_extension.capture()
        userpref_before = state.userpref.read_bytes()
        change = stage_blender_change(
            state,
            EXTENSION_ZIP,
            stage,
            BlenderAuthorizations(True, True, True, True),
            runner,
        )
        assert live_extension.capture() == extension_before
        assert state.userpref.read_bytes() == userpref_before
    finally:
        live_root.close()
    assert change.extension_path == stage / "resources/extensions/user_default/mcp"
    assert change.userpref_path == stage / "resources/config/userpref.blend"
    payload = load_extension_payload(EXTENSION_ZIP)
    verify_blender_files(change.staged_state, payload, change.extension_image)
    stage_root, staged_extension = _tree_ref(change.extension_path)
    try:
        assert staged_extension.capture() == change.extension_image
        assert compare_extension_tree(payload, staged_extension, change.extension_image).exact
    finally:
        stage_root.close()
    assert len(runner.calls) > before
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


@pytest.mark.parametrize(
    "drift",
    [
        {"repository": "foreign"},
        {"enabled": False},
        {"online_access": False},
        {"host": "foreign"},
        {"port": 1},
        {"autostart": False},
    ],
)
def test_payload_verification_is_independent_from_managed_state(
    tmp_path: Path, drift: dict[str, object]
) -> None:
    blender = _executable(tmp_path / "Blender")
    resources, env = _profile(tmp_path)
    _installed_profile(resources, env)
    state = inspect_blender(
        blender,
        env,
        BlenderRunner(
            blender,
            enabled=True,
            online_access=True,
            host="localhost",
            port=9876,
            autostart=True,
        ),
    )
    drift = dict(drift)
    if "repository" in drift:
        foreign = state.extensions_root / str(drift["repository"]) / "mcp"
        shutil.copytree(state.extension_root, foreign)
        drift["extension_root"] = foreign
    state = replace(state, **drift)
    payload = load_extension_payload(EXTENSION_ZIP)

    verify_blender_payload(state, payload)
    with pytest.raises(InstallerError):
        verify_blender_files(state, payload)


def _lsof(
    pid: int,
    executable: Path,
    *,
    uid: int | None = None,
    dev: int | None = None,
    ino: int | None = None,
    dyld: bool = False,
    command: str | None = None,
) -> str:
    info = executable.stat()
    records = [
        f"ftxt\nD{info.st_dev if dev is None else dev}\ni{info.st_ino if ino is None else ino}\nn{executable}\n"
    ]
    if dyld:
        records.append("ftxt\nD1\ni1\nn/usr/lib/dyld\n")
    return (
        f"p{pid}\nc{executable.name if command is None else command}\n"
        f"u{os.getuid() if uid is None else uid}\n" + "".join(records)
    )


def _listener(pid: int, *, uid: int | None = None) -> str:
    return f"p{pid}\ncBlender\nu{os.getuid() if uid is None else uid}\nf12\nn127.0.0.1:9876\n"


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


def _txt_record(path: Path, *, dev: int | None = None, ino: int | None = None) -> str:
    info = path.stat()
    return (
        f"ftxt\nD{info.st_dev if dev is None else dev}\n"
        f"i{info.st_ino if ino is None else ino}\nn{path}\n"
    )


def test_lifecycle_reports_free_port_and_foreign_listener_identity(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "Blender")
    foreign = _executable(tmp_path / "foreign/Python")
    free = probe_blender_lifecycle(blender, LifecycleRunner("", {}))
    assert free.matching_selected_pids == ()
    assert free.listener_pid is None and free.listener_executable is None and free.port_free
    runner = LifecycleRunner("", {77: _lsof(77, foreign)}, _listener(77), 0)
    occupied = probe_blender_lifecycle(blender, runner)
    assert occupied.listener_pid == 77
    assert occupied.listener_executable == foreign
    assert not occupied.port_free


def test_selected_main_ignores_later_same_basename_nonmatch(tmp_path: Path) -> None:
    blender = _executable(tmp_path / "selected/Blender")
    output = _lsof(10, blender) + "ftxt\nD1\ni1\nn/nonexistent/Blender\n"
    state = probe_blender_lifecycle(blender, LifecycleRunner("10\n", {10: output}))
    assert state.matching_selected_pids == (10,)


@pytest.mark.parametrize("case", ["selected_duplicate", "selected_later"])
def test_selected_exact_identity_in_later_txt_record_is_ambiguous(
    tmp_path: Path, case: str
) -> None:
    blender = _executable(tmp_path / "selected/Blender")
    if case == "selected_duplicate":
        output = _lsof(10, blender) + _txt_record(blender)
    else:
        other = _executable(tmp_path / "other/Blender")
        output = _lsof(10, other) + _txt_record(blender)
    with pytest.raises(InstallerError):
        probe_blender_lifecycle(blender, LifecycleRunner("10\n", {10: output}))


@pytest.mark.parametrize("case", ["renamed_selected", "unrelated_blender"])
def test_nonmatching_main_is_not_selected_by_basename_or_inode(tmp_path: Path, case: str) -> None:
    blender = _executable(tmp_path / "selected/ChosenExecutable")
    if case == "renamed_selected":
        executable = tmp_path / "renamed/Blender"
        executable.parent.mkdir()
        os.link(blender, executable)
    else:
        executable = _executable(tmp_path / "other/Blender")
    output = _lsof(10, executable, command="Blender")
    state = probe_blender_lifecycle(blender, LifecycleRunner("10\n", {10: output}))
    assert state.matching_selected_pids == ()


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


@pytest.mark.parametrize(
    "raw",
    [
        "p10\ncBlender\nu501\nf12\n",
        "p10\ncBlender\nu501\nf12\nn*:9876\nn*:9876\n",
        "p10\ncBlender\nu501\nf12\nD1\nn*:9876\n",
        "p10\ncBlender\nu501\nf12\nxunknown\nn*:9876\n",
        "p10\ncBlender\nu501\nf12\nf13\nn*:9876\n",
        "p10\ncBlender\nu501\nf12\nn*:9876\nf12\nn*:9876\n",
    ],
)
def test_listener_parser_rejects_malformed_duplicate_and_unknown_fields(raw: str) -> None:
    with pytest.raises(InstallerError):
        blender_adapter._parse_lsof_listener(raw)


@pytest.mark.parametrize(
    "raw,accepted",
    [
        (f"p10\ncBlender\nu{os.getuid()}\n", False),
        (_listener(10), True),
        (_listener(10) + "f13\nn[::1]:9876\n", False),
        (_listener(10) + _listener(11), False),
    ],
)
def test_listener_parser_requires_exactly_one_process_and_one_socket(
    raw: str, accepted: bool
) -> None:
    if accepted:
        processes = blender_adapter._parse_lsof_listener(raw)
        assert len(processes) == 1
        assert len(processes[0].files) == 1
    else:
        with pytest.raises(InstallerError):
            blender_adapter._parse_lsof_listener(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "p10\ncBlender\nu501\nftxt\nD1\ni2\n",
        "p10\ncBlender\nu501\nftxt\nD1\ni2\nn/x/Blender\nn/x/Blender\n",
        "p10\ncBlender\nu501\nftxt\nD1\ni2\nxunknown\nn/x/Blender\n",
        "p10\ncBlender\nu501\nftxt\nD1\ni2\nfmem\nn/x/Blender\n",
    ],
)
def test_txt_parser_rejects_malformed_duplicate_and_unknown_fields(raw: str) -> None:
    with pytest.raises(InstallerError):
        blender_adapter._parse_lsof_txt(raw)


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
    processes = blender_adapter._parse_lsof_txt(completed.stdout)
    assert len(processes) == 1
    assert processes[0].pid == os.getpid()
    assert processes[0].uid == os.getuid()
    assert processes[0].files
    main = processes[0].files[0]
    assert os.path.samefile(main.path, sys.executable)
    main_info = Path(main.path).stat()
    assert (main.device, main.inode) == (main_info.st_dev, main_info.st_ino)


@pytest.mark.skipif(sys.platform != "darwin", reason="disposable lsof parser probe is Darwin-only")
def test_disposable_live_listener_exact_command_is_accepted_by_strict_parser() -> None:
    listener = socket.socket()
    try:
        try:
            listener.bind(("127.0.0.1", 9876))
        except OSError:
            pytest.skip("TCP port 9876 is already occupied")
        listener.listen()
        completed = subprocess.run(
            [
                "/usr/sbin/lsof",
                "-nP",
                "-iTCP:9876",
                "-sTCP:LISTEN",
                "-FpcfDinu",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        processes = blender_adapter._parse_lsof_listener(completed.stdout)
        assert len(processes) == 1
        assert processes[0].pid == os.getpid()
        assert processes[0].uid == os.getuid()
        assert len(processes[0].files) == 1
        assert processes[0].files[0].path.endswith(":9876")
    finally:
        listener.close()
