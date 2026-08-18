from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import hashlib
import time
from dataclasses import replace
from pathlib import Path, PurePath
from types import SimpleNamespace

import pytest

sys.path.insert(
    0,
    str(Path(__file__).parents[2] / "plugins/blender-mcp-installer/scripts"),
)

from blender_mcp_installer.bundle import parse_manifest
from blender_mcp_installer.bundle import StagedBundle
from blender_mcp_installer.blender_adapter import BlenderState
from blender_mcp_installer.filesystem import (
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    StagedTree,
    capture_file,
    create_deterministic_stage,
)
from blender_mcp_installer.model import TreeImage
from blender_mcp_installer.runtime import stage_runtime
from blender_mcp_installer import verification
from blender_mcp_installer.verification import (
    HostCapabilityError,
    HostCapabilities,
    OfficialMCPProbe,
    inspect_installation,
    probe_host,
    verify_live,
)
from tests.distribution.test_filesystem import (
    INSTALL_ID,
    _active,
    _present_tree,
    _receipt,
    _roots,
)
from tests.distribution.test_runtime import _bundle as _runtime_bundle
from tests.distribution.test_runtime import _profile as _runtime_profile


MANIFEST = parse_manifest(
    (
        Path(__file__).parents[2] / "plugins/blender-mcp-installer/artifacts/manifest.json"
    ).read_bytes()
)


class HostRunner:
    def __init__(self, *, json_help: bool = True) -> None:
        self.json_help = json_help
        self.calls: list[tuple[str, ...]] = []
        self.records: list[tuple[tuple[str, ...], Path, dict[str, str]]] = []

    def __call__(self, argv, *, cwd, env):
        args = tuple(map(str, argv))
        self.calls.append(args)
        self.records.append((args, cwd, dict(env)))
        if args[-1:] == ("--version",):
            values = {
                "codex": "codex-cli 0.148.0-alpha.9\n",
                "uv": "uv 0.12.2 (46ead6098 2026-08-05 aarch64-apple-darwin)\n",
                "Blender": "Blender 5.2.0 LTS\n",
                "python": "Python 3.13.13\n",
            }
            return SimpleNamespace(returncode=0, stdout=values[Path(args[0]).name], stderr="")
        if args[0] == "/usr/bin/lipo":
            return SimpleNamespace(returncode=0, stdout="arm64 x86_64\n", stderr="")
        if args[-3:] == ("mcp", "get", "--help"):
            return SimpleNamespace(
                returncode=0,
                stdout="usage: codex mcp get --json" if self.json_help else "usage",
                stderr="",
            )
        if args[-4:] == ("plugin", "marketplace", "add", "--help"):
            return SimpleNamespace(returncode=0, stdout="usage", stderr="")
        if args[-3:] == ("plugin", "add", "--help"):
            return SimpleNamespace(returncode=0, stdout="usage", stderr="")
        raise AssertionError(args)


def _executable(path: Path, name: str) -> Path:
    result = path / name
    result.write_text("#!/bin/sh\nexit 0\n")
    result.chmod(0o700)
    return result


def _probe_env(tmp_path: Path) -> dict[str, str]:
    resources = tmp_path / "resources"
    return {
        "HOME": str(tmp_path / "home"),
        "CODEX_HOME": str(tmp_path / "codex-home"),
        "BLENDER_USER_RESOURCES": str(resources),
        "BLENDER_USER_CONFIG": str(resources / "config"),
        "BLENDER_USER_EXTENSIONS": str(resources / "extensions"),
        "SECRET": "not-forwarded",
    }


def test_probe_host_uses_help_without_querying_unpublished_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = HostRunner()
    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    host = probe_host(*bins, _probe_env(tmp_path), runner=runner)

    assert host.supported
    assert host.platform_system == "Darwin" and host.platform_machine == "arm64"
    assert host.blender_version == "5.2.0"
    assert host.codex_version == "0.148.0-alpha.9"
    assert host.uv_version == "0.12.2" and host.python_version == "3.13.13"
    assert host.blender_arches == ("arm64", "x86_64")
    assert not any(call[-4:] == ("mcp", "get", "blender", "--json") for call in runner.calls)
    assert all("SECRET" not in call for call in runner.calls)
    expected_env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(tmp_path / "home"),
        "CODEX_HOME": str(tmp_path / "codex-home"),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "BLENDER_USER_RESOURCES": str(tmp_path / "resources"),
        "BLENDER_USER_CONFIG": str(tmp_path / "resources/config"),
        "BLENDER_USER_EXTENSIONS": str(tmp_path / "resources/extensions"),
    }
    expected_argv = [
        (str(bins[1]), "--version"),
        (str(bins[2]), "--version"),
        (str(bins[0]), "--version"),
        (str(bins[3]), "--version"),
        ("/usr/bin/lipo", "-archs", str(bins[0])),
        (str(bins[1]), "mcp", "get", "--help"),
        (str(bins[1]), "plugin", "marketplace", "add", "--help"),
        (str(bins[1]), "plugin", "add", "--help"),
    ]
    assert [record[0] for record in runner.records] == expected_argv
    assert [record[1] for record in runner.records] == [tmp_path] * len(expected_argv)
    assert all(record[2] == expected_env for record in runner.records)


@pytest.mark.parametrize(
    "output,product",
    [
        ("Blender 5.2.0 stable\n", "Blender"),
        ("Blender 5.2.0 LTS extra\n", "Blender"),
        ("NotBlender 5.2.0 LTS\n", "Blender"),
        ("codex-cli 0.148.0-alpha.9 LTS\n", "codex-cli"),
        ("uv 0.12.2 LTS\n", "uv"),
        ("Python 3.13.13 LTS\n", "Python"),
        ("uv 0.12.2 (2026-08-05 aarch64-apple-darwin)\n", "uv"),
        ("uv 0.12.2 (46ead6098 aarch64-apple-darwin)\n", "uv"),
        ("uv 0.12.2 (46ead6098 2026-08-05)\n", "uv"),
        ("uv 0.12.2 (not-hex 2026-08-05 aarch64-apple-darwin)\n", "uv"),
        ("uv 0.12.2 (46ead6098 2026-8-05 aarch64-apple-darwin)\n", "uv"),
        ("uv 0.12.2 (46ead6098 2026-08-05 aarch64/apple/darwin)\n", "uv"),
        ("uv 0.12.2 (46ead6098 2026-08-05 aarch64-apple-darwin) extra\n", "uv"),
        ("codex-cli 0.12.2 (46ead6098 2026-08-05 aarch64-apple-darwin)\n", "uv"),
        ("codex-cli 0.148.0 (46ead6098 2026-08-05 aarch64-apple-darwin)\n", "codex-cli"),
        ("Python 3.13.13 (46ead6098 2026-08-05 aarch64-apple-darwin)\n", "Python"),
    ],
)
def test_version_parser_rejects_unapproved_suffixes_and_wrong_products(
    output: str, product: str
) -> None:
    with pytest.raises(InstallerError, match="host capability probe failed"):
        verification._version(output, product)


@pytest.mark.parametrize(
    "completed",
    [
        SimpleNamespace(returncode=0, stdout=b"x" * (1024 * 1024 + 1), stderr=b""),
        SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"x" * (64 * 1024 + 1)),
        SimpleNamespace(returncode=0, stdout=b"\xff", stderr=b""),
        SimpleNamespace(returncode=2, stdout=b"ok", stderr=b""),
    ],
    ids=("stdout-cap", "stderr-cap", "utf8", "nonzero"),
)
def test_injected_host_results_are_capped_and_redacted(tmp_path: Path, completed) -> None:
    with pytest.raises(InstallerError, match="host capability probe failed"):
        verification._run(lambda *args, **kwargs: completed, ("tool",), cwd=tmp_path, env={})


def test_injected_host_timeout_is_redacted(tmp_path: Path) -> None:
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("secret", 5)

    with pytest.raises(InstallerError, match="host capability probe failed") as caught:
        verification._run(timeout, ("tool",), cwd=tmp_path, env={})
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_real_host_reader_stops_at_stream_caps(tmp_path: Path, stream: str) -> None:
    descriptor = 1 if stream == "stdout" else 2
    command = (
        sys.executable,
        "-c",
        f"import os;os.write({descriptor},b'x'*{2 * 1024 * 1024})",
    )
    with pytest.raises(InstallerError, match="host capability probe failed"):
        verification._run(
            verification._default_runner,
            command,
            cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin"},
        )


def test_real_host_reader_enforces_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verification, "_HOST_TIMEOUT", 0.05)
    with pytest.raises(InstallerError, match="host capability probe failed"):
        verification._run(
            verification._default_runner,
            (sys.executable, "-c", "import time;time.sleep(1)"),
            cwd=tmp_path,
            env={"PATH": "/usr/bin:/bin"},
        )


def test_probe_host_rejects_partial_or_escaping_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    partial = _probe_env(tmp_path)
    partial.pop("BLENDER_USER_CONFIG")
    with pytest.raises(ValueError, match="all three"):
        probe_host(*bins, partial, runner=HostRunner())
    escaping = _probe_env(tmp_path)
    escaping["BLENDER_USER_CONFIG"] = str(tmp_path / "outside")
    with pytest.raises(ValueError, match="descend"):
        probe_host(*bins, escaping, runner=HostRunner())


def test_probe_host_rejects_symlinked_profile_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    (tmp_path / "actual-resources").mkdir()
    (tmp_path / "resources").symlink_to(tmp_path / "actual-resources", target_is_directory=True)
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    with pytest.raises(ValueError, match="unsafe host profile path"):
        probe_host(*bins, _probe_env(tmp_path), runner=HostRunner())


def test_probe_host_unsupported_json_retains_redacted_version_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = HostRunner(json_help=False)
    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    with pytest.raises(HostCapabilityError, match="unsupported host capabilities") as caught:
        probe_host(*bins, _probe_env(tmp_path), runner=runner)

    assert caught.value.capabilities.codex_version == "0.148.0-alpha.9"
    assert not caught.value.capabilities.codex_mcp_get_json
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "tool,version",
    [("uv", "uv 0.13.0\n"), ("Blender", "Blender 5.3.0\n"), ("python", "Python 3.14.0\n")],
)
def test_probe_host_rejects_unsupported_actual_versions_with_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, version: str
) -> None:
    runner = HostRunner()
    original = runner.__call__

    def changed(argv, *, cwd, env):
        if tuple(argv)[-1:] == ("--version",) and Path(argv[0]).name == tool:
            return SimpleNamespace(returncode=0, stdout=version, stderr="")
        return original(argv, cwd=cwd, env=env)

    bins = tuple(_executable(tmp_path, name) for name in ("Blender", "codex", "uv", "python"))
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    with pytest.raises(HostCapabilityError) as caught:
        probe_host(*bins, _probe_env(tmp_path), runner=changed)

    assert getattr(caught.value.capabilities, f"{tool.lower()}_version") == version.split()[1]


FIELDS = (
    "runtime",
    "extension_repository",
    "extension_id",
    "extension_version",
    "extension_payload_digest",
    "enablement",
    "preferences",
    "codex_policy",
    "codex_namespace",
    "codex_effective",
    "active_generation",
    "manifest_hash",
    "recorded_blender_executable",
)


def _host(roots, runner=object()) -> HostCapabilities:
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(roots.home),
        "CODEX_HOME": str(roots.codex_home),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "BLENDER_USER_RESOURCES": str(roots.blender.user_resources),
        "BLENDER_USER_CONFIG": str(roots.blender.user_config),
        "BLENDER_USER_EXTENSIONS": str(roots.blender.user_extensions),
    }
    return HostCapabilities(
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
        roots.blender.executable,
        _executable(roots.blender.executable.parent, "codex"),
        _executable(roots.blender.executable.parent, "uv"),
        _executable(roots.blender.executable.parent, "python"),
        env,
        runner,
    )


def _installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, runner=object()):
    roots = _roots(tmp_path)
    for path in (
        roots.blender.executable.parent,
        roots.blender.user_config,
        roots.blender.user_extensions,
        roots.runtime,
        roots.extension_target,
        roots.codex_config.parent,
        roots.receipts,
    ):
        path.mkdir(parents=True, exist_ok=True)
    _executable(roots.blender.executable.parent, roots.blender.executable.name)
    (roots.runtime / "content").write_text("runtime")
    (roots.extension_target / "content").write_text("extension")
    roots.userpref_target.write_text("preferences")
    roots.codex_config.write_text("managed")
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    manifest_raw = (
        Path(__file__).parents[2] / "plugins/blender-mcp-installer/artifacts/manifest.json"
    ).read_bytes()
    (bundle_root / "manifest.json").write_bytes(manifest_raw)
    (bundle_root / "mcp-1.0.0.zip").write_bytes(b"extension")
    bundle = StagedBundle(bundle_root, MANIFEST)
    receipt = _receipt(roots)
    receipt["status"] = "installed"
    receipt["bundle"] = {
        "version": MANIFEST.bundle_version,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
    }
    roots.active.write_text(json.dumps(_active(), sort_keys=True))
    receipt_path = roots.receipts / f"{INSTALL_ID}.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    roots.active.chmod(0o600)
    receipt_path.chmod(0o600)
    digest = "d" * 64
    blender = BlenderState(
        roots.blender.executable,
        ("arm64",),
        roots.blender.executable,
        "arm64",
        "5.2.0",
        roots.home,
        roots.blender.user_resources,
        roots.blender.user_config,
        roots.userpref_target,
        roots.blender.user_extensions,
        "user_default",
        roots.extension_target,
        "mcp",
        "1.0.0",
        True,
        True,
        "localhost",
        9876,
        True,
        digest,
    )
    host = _host(roots, runner)
    controls = {
        "blender": blender,
        "runtime": True,
        "blender_files": True,
        "codex_policy": True,
        "codex_namespace": True,
        "codex_effective": True,
        "runtime_profile": None,
    }
    calls: list[str] = []

    def runtime_probe(*args):
        calls.append("runtime")
        controls["runtime_profile"] = args[2]
        if not controls["runtime"]:
            raise InstallerError("runtime verification failed")
        return SimpleNamespace(
            exact=True,
            launcher_path=roots.runtime / "bin/blender-mcp-managed",
        )

    def blender_files(*args):
        calls.append("blender_files")
        if not controls["blender_files"]:
            raise InstallerError("Blender file verification failed")

    def codex_toml(*args):
        calls.append("codex_toml")
        if not controls["codex_policy"] or not controls["codex_namespace"]:
            raise InstallerError("Codex managed configuration mismatch")

    def codex_effective(*args):
        calls.append("codex_effective")
        if not controls["codex_effective"]:
            raise InstallerError("effective Codex configuration mismatch")
        return SimpleNamespace()

    monkeypatch.setattr(verification, "inspect_blender", lambda *args: controls["blender"])
    monkeypatch.setattr(verification, "verify_runtime", runtime_probe)
    monkeypatch.setattr(
        verification,
        "load_extension_payload",
        lambda path: SimpleNamespace(canonical_digest=digest),
    )
    monkeypatch.setattr(verification, "verify_blender_payload", blender_files, raising=False)
    monkeypatch.setattr(
        verification,
        "_codex_checks",
        lambda *args: (controls["codex_policy"], controls["codex_namespace"]),
    )
    monkeypatch.setattr(verification, "verify_codex_toml", codex_toml)
    monkeypatch.setattr(verification, "verify_codex_effective", codex_effective)
    return bundle, roots, blender, host, controls, calls, receipt, receipt_path


def _absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    bundle, roots, blender, host, controls, calls, _, receipt_path = _installed(
        tmp_path, monkeypatch
    )
    roots.active.unlink()
    receipt_path.unlink()
    for path in (roots.runtime / "content", roots.extension_target / "content"):
        path.unlink()
        path.parent.rmdir()
    roots.userpref_target.unlink()
    roots.codex_config.unlink()
    controls["runtime"] = False
    controls["blender_files"] = False
    controls["blender"] = replace(
        blender,
        manifest_id=None,
        manifest_version=None,
        enabled=False,
        online_access=False,
        host=None,
        port=None,
        autostart=None,
        canonical_payload_digest=None,
    )
    return bundle, roots, blender, host, controls, calls


@pytest.mark.parametrize("field", FIELDS)
def test_adapter_backed_inspection_independently_computes_every_exactness_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    bundle, roots, blender, host, controls, calls, receipt, receipt_path = _installed(
        tmp_path, monkeypatch
    )
    if field == "runtime":
        controls["runtime"] = False
    elif field.startswith("extension_") or field in {"enablement", "preferences"}:
        attribute, value = {
            "extension_repository": ("repository", "foreign"),
            "extension_id": ("manifest_id", "foreign"),
            "extension_version": ("manifest_version", "9.9.9"),
            "extension_payload_digest": ("canonical_payload_digest", "e" * 64),
            "enablement": ("enabled", False),
            "preferences": ("online_access", False),
        }[field]
        changes = {attribute: value}
        if field == "extension_repository":
            changes["extension_root"] = blender.extensions_root / "foreign/mcp"
        controls["blender"] = replace(blender, **changes)
    elif field in {"codex_policy", "codex_namespace", "codex_effective"}:
        controls[field] = False
    elif field == "active_generation":
        receipt["generation"] = 2
        receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    elif field == "manifest_hash":
        receipt["bundle"]["manifest_sha256"] = "e" * 64
        receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    elif field == "recorded_blender_executable":
        other = _executable(roots.blender.executable.parent, "OtherBlender")
        roots = replace(roots, blender=replace(roots.blender, executable=other))
        receipt["host"]["blender_executable"] = str(other)
        receipt_path.write_text(json.dumps(receipt, sort_keys=True))

    inspected = inspect_installation(bundle, roots, blender, host)

    assert not getattr(inspected, field)
    assert not inspected.exact
    assert calls[:2] == ["runtime", "blender_files"]


def test_adapter_backed_exact_inspection_binds_receipt_and_all_authorities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, controls, calls, _, receipt_path = _installed(
        tmp_path, monkeypatch
    )

    inspected = inspect_installation(bundle, roots, blender, host)

    assert inspected.exact and inspected.receipt_path == receipt_path
    assert inspected.managed_targets == (
        roots.runtime,
        roots.extension_target,
        roots.userpref_target,
        roots.codex_config,
        roots.active,
        receipt_path,
    )
    assert len(inspected.managed_images) == 6
    assert calls == ["runtime", "blender_files", "codex_toml", "codex_effective"]
    assert controls["runtime_profile"].home == roots.home
    assert controls["runtime_profile"].blender_path == roots.blender.executable


def test_unrelated_userpref_rewrite_does_not_change_semantic_exactness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, receipt, receipt_path = _installed(
        tmp_path, monkeypatch
    )
    with SafeRoot.open(
        roots.blender.user_config, os.getuid(), roots.blender.user_config
    ) as config:
        recorded = capture_file(config, PurePath("userpref.blend"))
    next(target for target in receipt["targets"] if target["role"] == "blender_userpref")[
        "install_post"
    ] = recorded.to_dict()
    receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    roots.userpref_target.write_bytes(
        roots.userpref_target.read_bytes() + b"\nunrelated-preference-rewrite"
    )

    inspected = inspect_installation(bundle, roots, blender, host)

    assert recorded.sha256 not in inspected.managed_images[2]
    assert inspected.exact and inspected.preferences


def test_online_access_drift_does_not_poison_unrelated_blender_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, controls, _, _, _ = _installed(tmp_path, monkeypatch)
    controls["blender"] = replace(blender, online_access=False)

    inspected = inspect_installation(bundle, roots, blender, host)

    assert not inspected.exact and not inspected.preferences
    assert all(
        (
            inspected.extension_repository,
            inspected.extension_id,
            inspected.extension_version,
            inspected.extension_payload_digest,
            inspected.enablement,
        )
    )


def test_extension_file_drift_still_makes_inspection_inexact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, controls, _, _, _ = _installed(tmp_path, monkeypatch)
    controls["blender_files"] = False

    inspected = inspect_installation(bundle, roots, blender, host)

    assert not inspected.extension_files
    assert not inspected.extension_payload_digest
    assert not inspected.exact


@pytest.mark.parametrize(
    ("changes", "failed_check", "failed_preference"),
    [
        (
            {"repository": "foreign"},
            "extension_repository",
            None,
        ),
        ({"enabled": False}, "enablement", None),
        ({"online_access": False}, "preferences", "online_access"),
        ({"host": "foreign"}, "preferences", "host"),
        ({"port": 1}, "preferences", "port"),
        ({"autostart": False}, "preferences", "autostart"),
    ],
)
def test_blender_semantic_drift_only_marks_its_own_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    failed_check: str,
    failed_preference: str | None,
) -> None:
    bundle, roots, blender, host, controls, _, _, _ = _installed(tmp_path, monkeypatch)
    changes = dict(changes)
    if "repository" in changes:
        changes["extension_root"] = blender.extensions_root / "foreign/mcp"
    controls["blender"] = replace(blender, **changes)

    inspected = inspect_installation(bundle, roots, blender, host)

    failed = {name for name in verification.EXACT_CHECK_NAMES if not getattr(inspected, name)}
    assert failed == {failed_check}
    assert inspected.extension_files
    failed_preferences = {
        name for name, exact in inspected.preference_checks.items() if not exact
    }
    assert failed_preferences == ({failed_preference} if failed_preference else set())


def test_installed_inspection_passes_recorded_extension_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, receipt, receipt_path = _installed(tmp_path, monkeypatch)
    recorded = _present_tree()
    next(target for target in receipt["targets"] if target["role"] == "blender_extension")[
        "install_post"
    ] = recorded
    receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    seen: list[object] = []
    monkeypatch.setattr(
        verification,
        "verify_blender_payload",
        lambda _state, _payload, provenance=None: seen.append(provenance),
    )

    inspected = inspect_installation(bundle, roots, blender, host)

    assert inspected.exact
    assert seen == [TreeImage.from_dict(recorded)]


def test_clean_host_inspection_is_prepublication_safe_and_first_install_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, calls = _absent(tmp_path, monkeypatch)
    monkeypatch.setattr(
        verification,
        "verify_codex_effective",
        lambda *args: (_ for _ in ()).throw(AssertionError("prepublication query")),
    )

    inspected = inspect_installation(bundle, roots, blender, host)

    assert not inspected.exact
    assert inspected.active_install_id is None and inspected.receipt_path is None
    assert inspected.managed_targets == (
        roots.runtime,
        roots.extension_target,
        roots.userpref_target,
        roots.codex_config,
        roots.active,
    )
    assert len(inspected.managed_images) == 5
    assert calls == ["runtime", "blender_files"]
    assert {
        "exact": inspected.exact,
        "managed_target_count": len(inspected.managed_targets),
        "active_install_id": inspected.active_install_id,
    } == {"exact": False, "managed_target_count": 5, "active_install_id": None}


def test_absent_active_checks_managed_remnants_without_effective_codex_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, calls, _, receipt_path = _installed(tmp_path, monkeypatch)
    roots.active.unlink()
    receipt_path.unlink()
    monkeypatch.setattr(
        verification,
        "verify_codex_effective",
        lambda *args: (_ for _ in ()).throw(AssertionError("prepublication query")),
    )

    inspected = inspect_installation(bundle, roots, blender, host)

    assert not inspected.exact and inspected.active_install_id is None
    assert calls == ["runtime", "blender_files", "codex_toml"]


def test_absent_inspection_detects_managed_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, controls, _ = _absent(tmp_path, monkeypatch)

    def mutate(*args):
        roots.codex_config.write_text("appeared")
        return controls["blender"]

    monkeypatch.setattr(verification, "inspect_blender", mutate)
    with pytest.raises(InstallerError, match="managed targets changed during inspection"):
        inspect_installation(bundle, roots, blender, host)


def test_absent_inspection_detects_active_appearance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, controls, _ = _absent(tmp_path, monkeypatch)

    def mutate(*args):
        roots.active.write_text(json.dumps(_active()))
        roots.active.chmod(0o600)
        return controls["blender"]

    monkeypatch.setattr(verification, "inspect_blender", mutate)
    with pytest.raises(InstallerError, match="managed targets changed during inspection"):
        inspect_installation(bundle, roots, blender, host)


def test_installed_inspection_detects_active_disappearing_during_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, _, _ = _installed(tmp_path, monkeypatch)
    original = verification._active_receipt_path

    def disappear(current_roots):
        result = original(current_roots)
        roots.active.unlink()
        return result

    monkeypatch.setattr(verification, "_active_receipt_path", disappear)
    with pytest.raises(InstallerError, match="managed targets changed during inspection"):
        inspect_installation(bundle, roots, blender, host)


def test_malformed_active_fails_closed_after_before_and_after_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, _, _ = _installed(tmp_path, monkeypatch)
    roots.active.write_text("{")
    snapshots = 0
    original = verification._snapshot

    def counted(paths):
        nonlocal snapshots
        snapshots += 1
        return original(paths)

    monkeypatch.setattr(verification, "_snapshot", counted)
    with pytest.raises(InstallerError, match="active installation inspection failed"):
        inspect_installation(bundle, roots, blender, host)
    assert snapshots == 2


def test_absent_inspection_takes_after_snapshot_on_authoritative_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _ = _absent(tmp_path, monkeypatch)
    snapshots = 0
    original = verification._snapshot

    def counted(paths):
        nonlocal snapshots
        snapshots += 1
        return original(paths)

    monkeypatch.setattr(verification, "_snapshot", counted)
    monkeypatch.setattr(
        verification,
        "inspect_blender",
        lambda *args: (_ for _ in ()).throw(ValueError("secret")),
    )
    with pytest.raises(InstallerError, match="Blender inspection failed"):
        inspect_installation(bundle, roots, blender, host)
    assert snapshots == 2


def test_inspection_always_takes_after_image_when_fresh_probe_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, _, _ = _installed(tmp_path, monkeypatch)
    original_snapshot = verification._snapshot
    snapshots = 0
    target_counts = []

    def counted(paths):
        nonlocal snapshots
        snapshots += 1
        target_counts.append(len(paths))
        return original_snapshot(paths)

    monkeypatch.setattr(verification, "_snapshot", counted)
    monkeypatch.setattr(
        verification,
        "inspect_blender",
        lambda *args: (_ for _ in ()).throw(ValueError("secret")),
    )

    with pytest.raises(InstallerError, match="Blender inspection failed") as caught:
        inspect_installation(bundle, roots, blender, host)
    assert snapshots == 3 and target_counts == [5, 6, 6]
    assert "secret" not in str(caught.value)


def test_current_profile_cross_bind_is_required_for_runtime_and_recorded_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, _, _ = _installed(tmp_path, monkeypatch)
    hostile_env = dict(host.env)
    hostile_env["BLENDER_USER_CONFIG"] = str(tmp_path / "foreign-config")

    inspected = inspect_installation(bundle, roots, blender, replace(host, env=hostile_env))

    assert not inspected.runtime
    assert not inspected.recorded_blender_executable


def test_discovered_default_profile_matches_when_override_variables_are_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, _, _, _, _ = _installed(tmp_path, monkeypatch)
    omitted = {key: value for key, value in host.env.items() if not key.startswith("BLENDER_USER_")}

    inspected = inspect_installation(bundle, roots, blender, replace(host, env=omitted))

    assert inspected.runtime
    assert inspected.recorded_blender_executable


def test_live_blender_probe_is_inside_managed_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, roots, blender, host, controls, _ = _absent(tmp_path, monkeypatch)
    events: list[str] = []
    original_snapshot = verification._snapshot

    def snapshot(paths):
        events.append("snapshot")
        return original_snapshot(paths)

    def live_probe(*_args):
        events.append("live")
        return controls["blender"]

    monkeypatch.setattr(verification, "_snapshot", snapshot)
    monkeypatch.setattr(verification, "inspect_blender", live_probe)

    inspect_installation(bundle, roots, blender, host)

    assert events == ["snapshot", "live", "snapshot"]


class LifecycleRunner:
    def __init__(self, blender: Path, *, listener: str = "selected") -> None:
        self.blender = blender
        self.listener = listener

    def __call__(self, argv, *, cwd, env):
        args = tuple(argv)
        selected = self.blender
        foreign = _executable(self.blender.parent, "Foreign")
        selected_stat = selected.stat()
        foreign_stat = foreign.stat()
        executable = selected if self.listener == "selected" else foreign
        info = selected_stat if self.listener == "selected" else foreign_stat
        if args == ("/usr/bin/pgrep", "-x", "Blender"):
            pids = "10\n" if self.listener != "missing" else ""
            return SimpleNamespace(returncode=0 if pids else 1, stdout=pids, stderr="")
        if args == ("/usr/sbin/lsof", "-nP", "-iTCP:9876", "-sTCP:LISTEN", "-FpcfDinu"):
            if self.listener == "missing":
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            listener = f"p10\ncBlender\nu{os.getuid()}\nf12\nn127.0.0.1:9876\n"
            if self.listener == "ambiguous":
                listener += f"p11\ncBlender\nu{os.getuid()}\nf13\nn127.0.0.1:9876\n"
            return SimpleNamespace(returncode=0, stdout=listener, stderr="")
        if args[:4] == ("/usr/sbin/lsof", "-a", "-p", args[3]):
            raw = (
                f"p10\ncBlender\nu{os.getuid()}\n"
                f"ftxt\nD{info.st_dev}\ni{info.st_ino}\nn{executable}\n"
            )
            return SimpleNamespace(returncode=0, stdout=raw, stderr="")
        raise AssertionError(args)


class Session:
    def __init__(
        self, tools=MANIFEST.tools, *, fail: str | None = None, initialize_result=None
    ) -> None:
        self.tools = tools
        self.fail = fail
        self.initialize_result = initialize_result
        self.calls: list[tuple[str, object]] = []

    def initialize(self):
        self.calls.append(("initialize", None))
        if self.fail == "initialize":
            raise ValueError("secret protocol failure")
        return (
            self.initialize_result
            if self.initialize_result is not None
            else {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
            }
        )

    def list_tools(self):
        self.calls.append(("list_tools", None))
        if self.fail == "list":
            raise ValueError("secret list failure")
        return self.tools

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self.fail == "call":
            raise ValueError("secret call failure")
        if self.fail == "call_result":
            return {"isError": True, "content": [{"type": "text", "text": "secret"}]}
        return {"content": [{"type": "text", "text": "{}"}]}


def _observed_initialize():
    return {
        "protocolVersion": "2025-11-25",
        "capabilities": {
            "completions": None,
            "experimental": {},
            "logging": None,
            "prompts": {"listChanged": False},
            "resources": {"listChanged": False, "subscribe": False},
            "tasks": None,
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": "blender-mcp",
            "version": "1.28.1",
            "icons": None,
            "title": None,
            "websiteUrl": None,
        },
        "_meta": None,
        "instructions": "Blender MCP server instructions",
    }


class Handle:
    def __init__(self, client: Session, *, fail: str | None = None) -> None:
        self.client = client
        self.fail = fail
        self.opened = False
        self.closed = self.terminated = self.waited = False

    def open_client(self):
        self.opened = True
        if self.fail in {"stdout", "stderr", "client"}:
            raise ValueError(f"secret {self.fail} failure")
        return self.client

    def close(self):
        self.closed = True
        if self.fail == "close" or self.client.fail == "close":
            raise ValueError("secret close failure")

    def terminate(self):
        self.terminated = True
        if self.fail == "terminate" or self.client.fail == "terminate":
            raise ValueError("secret terminate failure")

    def wait(self, timeout):
        self.waited = timeout
        if self.fail == "wait" or self.client.fail == "wait":
            raise subprocess.TimeoutExpired("secret", timeout)


class MCPProbe:
    def __init__(self, handle: Handle, *, fail_spawn: bool = False) -> None:
        self.handle = handle
        self.fail_spawn = fail_spawn
        self.command = None
        self.env = None

    def spawn(self, command, *, env):
        self.command = tuple(command)
        self.env = dict(env)
        if self.fail_spawn:
            raise ValueError("atomic spawn failure")
        return self.handle


class _ProbeProcess:
    def __init__(self, output: bytes, *, running: bool = False) -> None:
        self.output = output
        self.running = running
        self.terminated = False
        self.waited: float | None = None
        self.stdout = None
        self.stderr = None

    def communicate(self, timeout: float):
        self.waited = timeout
        self.running = False
        return self.output, b"secret helper stderr"

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.terminated = True
        self.running = False

    def wait(self, timeout: float):
        self.waited = timeout
        self.running = False
        return 0

    def kill(self):
        self.running = False


def test_official_probe_uses_runtime_python_and_returns_closed_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_python = _executable(tmp_path, "python")
    server = _executable(tmp_path, "blender-mcp-managed")
    payload = {
        "initialize": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
        },
        "tools": list(MANIFEST.tools),
        "call": {"content": [{"type": "text", "text": "{}"}]},
    }
    process = _ProbeProcess(json.dumps(payload).encode())
    seen: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def popen(argv, **kwargs):
        seen.append((tuple(argv), dict(kwargs)))
        return process

    monkeypatch.setattr(verification.subprocess, "Popen", popen)
    handle = OfficialMCPProbe(runtime_python).spawn(
        (str(server),), env={"HOME": str(tmp_path), "SECRET": "not serialized"}
    )
    client = handle.open_client()
    assert client.initialize() == payload["initialize"]
    assert tuple(client.list_tools()) == MANIFEST.tools
    assert client.call_tool("get_blendfile_summary_datablocks", {}) == payload["call"]
    assert seen[0][0][:4] == (str(runtime_python), "-I", "-B", "-c")
    assert seen[0][1]["stdin"] is subprocess.DEVNULL
    assert "SECRET" not in seen[0][0][2]
    handle.close()
    handle.terminate()
    assert handle.wait(2.0) == 0


def test_official_probe_keeps_locked_runtime_tree_and_marker_exact(tmp_path: Path) -> None:
    bundle = _runtime_bundle(tmp_path)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    with SafeRoot.open(data, os.getuid(), data) as root:
        created = create_deterministic_stage(
            root, "runtime.stage", TreeImage.absent(), NoOpFaultInjector()
        )
        assert isinstance(created, StagedTree)

        def run(argv, *, cwd: Path, env):
            return subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)

        image = stage_runtime(
            bundle,
            Path(os.environ["UV"]).resolve(strict=True),
            Path(sys.executable).resolve(strict=True),
            _runtime_profile(tmp_path),
            created,
            run,
        )
        stage = created.with_image(image)
        marker = stage.path / ".blender-mcp-runtime.json"
        marker_raw = marker.read_bytes()

        def bytecode_paths():
            return tuple(
                path.relative_to(stage.path)
                for path in stage.path.rglob("*")
                if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
            )

        bytecode_before = bytecode_paths()
        handle = OfficialMCPProbe(stage.path / "bin/python").spawn(
            (str(stage.path / "bin/blender-mcp-managed"),),
            env={"HOME": str(tmp_path / "hostile-home"), "PYTHONDONTWRITEBYTECODE": "0"},
        )
        try:
            client = handle.open_client()
            initialized = client.initialize()
            assert verification._valid_initialize(initialized, bundle.manifest)
            assert tuple(client.list_tools()) == bundle.manifest.tools
            assert type(client.call_tool("get_blendfile_summary_datablocks", {})) is dict
        finally:
            handle.close()
            handle.terminate()
            assert handle.wait(2.0) == 0

        assert stage.capture() == image
        assert marker.read_bytes() == marker_raw
        assert bytecode_paths() == bytecode_before


def test_official_probe_malformed_output_is_redacted_and_cleanup_is_owned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = _ProbeProcess(b"not-json", running=True)
    monkeypatch.setattr(verification.subprocess, "Popen", lambda *_a, **_k: process)
    handle = OfficialMCPProbe(_executable(tmp_path, "python")).spawn(
        (str(_executable(tmp_path, "server")),), env={"HOME": str(tmp_path)}
    )
    with pytest.raises(InstallerError, match="official MCP probe failed") as caught:
        handle.open_client().initialize()
    assert "not-json" not in str(caught.value)
    handle.close()
    handle.terminate()
    handle.wait(2.0)
    assert process.waited is not None


def test_official_probe_closes_pipe_and_kills_real_stubborn_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = _executable(tmp_path, "server")
    monkeypatch.setattr(verification, "_MCP_HELPER", "import time; time.sleep(60)")
    monkeypatch.setattr(verification, "_WAIT_TIMEOUT", 0.05)
    handle = OfficialMCPProbe(Path(sys.executable).resolve()).spawn(
        (str(server),), env={"HOME": str(tmp_path)}
    )
    process = handle.process
    assert process.stdout is not None and not process.stdout.closed

    started = time.monotonic()
    handle.terminate()
    handle.close()

    assert time.monotonic() - started < 2
    assert process.poll() is not None
    assert process.stdout.closed


def _live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    *,
    listener: str = "selected",
    handle_fail: str | None = None,
    fail_spawn: bool = False,
):
    selected = _roots(tmp_path).blender.executable
    runner = LifecycleRunner(selected, listener=listener)
    bundle, roots, blender, host, _, _, _, _ = _installed(tmp_path, monkeypatch, runner=runner)
    inspection = inspect_installation(bundle, roots, blender, host)
    handle = Handle(session, fail=handle_fail)
    probe = MCPProbe(handle, fail_spawn=fail_spawn)
    hostile = {
        "HOME": str(tmp_path / "hostile-home"),
        "PYTHONPATH": "hostile-python",
        "BLENDER_MCP_HOST": "foreign.invalid",
        "BLENDER_MCP_PORT": "1",
        "BLENDER_USER_RESOURCES": str(tmp_path / "foreign-profile"),
    }
    return bundle, inspection, probe, handle, hostile


def test_live_uses_hostile_parent_exact_catalog_and_only_read_only_no_arg_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)

    result = verify_live(
        bundle,
        inspection,
        inspection.runtime_command,
        inspection.host.codex_bin,
        hostile,
        probe,
    )

    assert result.parsed_codex and result.effective_codex
    assert result.mcp_catalog and result.blender_read_only and result.tool_count == 26
    assert probe.command == inspection.runtime_command and probe.env == hostile
    assert session.calls == [
        ("initialize", None),
        ("list_tools", None),
        ("get_blendfile_summary_datablocks", {}),
    ]
    assert handle.closed and handle.terminated and handle.waited == 2.0


@pytest.mark.parametrize("target_index", range(6))
def test_live_rejects_each_stale_managed_image_before_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_index: int
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    target = inspection.managed_targets[target_index]
    if target.is_dir():
        (target / "tampered").write_text("after-inspection")
    else:
        target.write_text(target.read_text() + "\n")

    with pytest.raises(InstallerError, match="stale installation inspection"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command is None
    assert not handle.opened


@pytest.mark.parametrize("change", ["omitted", "extra", "reordered"])
def test_live_rejects_noncanonical_managed_target_tuple(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    paths = inspection.managed_targets
    forged = {
        "omitted": paths[:-1],
        "extra": (*paths, tmp_path / "foreign"),
        "reordered": tuple(reversed(paths)),
    }[change]

    with pytest.raises(InstallerError, match="invalid installation inspection"):
        verify_live(
            bundle,
            replace(inspection, managed_targets=forged),
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command is None and not handle.opened


def test_live_accepts_exact_observed_initialize_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session(initialize_result=_observed_initialize())
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)

    result = verify_live(
        bundle,
        inspection,
        inspection.runtime_command,
        inspection.host.codex_bin,
        hostile,
        probe,
    )

    assert result.tool_count == 26
    assert handle.closed and handle.terminated and handle.waited == 2.0


_MISSING = object()


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("_meta",), _MISSING),
        (("extra",), True),
        (("_meta",), {}),
        (("instructions",), None),
        (("instructions",), True),
        (("protocolVersion",), "2025-06-18"),
        (("capabilities", "tools"), _MISSING),
        (("capabilities", "extra"), None),
        (("capabilities", "completions"), False),
        (("capabilities", "experimental"), []),
        (("capabilities", "prompts", "listChanged"), 0),
        (("capabilities", "resources", "subscribe"), True),
        (("capabilities", "tasks"), {}),
        (("capabilities", "tools", "listChanged"), None),
        (("serverInfo", "title"), _MISSING),
        (("serverInfo", "extra"), None),
        (("serverInfo", "name"), "foreign"),
        (("serverInfo", "version"), "999"),
        (("serverInfo", "icons"), []),
        (("serverInfo", "title"), ""),
        (("serverInfo", "websiteUrl"), False),
    ],
)
def test_live_rejects_any_observed_initialize_schema_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    replacement,
) -> None:
    initialize = _observed_initialize()
    target = initialize
    for key in path[:-1]:
        target = target[key]
    if replacement is _MISSING:
        target.pop(path[-1])
    else:
        target[path[-1]] = replacement
    bundle, inspection, probe, handle, hostile = _live(
        tmp_path, monkeypatch, Session(initialize_result=initialize)
    )

    with pytest.raises(InstallerError, match="MCP handshake failed"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert handle.closed and handle.terminated and handle.waited == 2.0


@pytest.mark.parametrize(
    "initialize_result",
    [
        {},
        {
            "protocolVersion": "wrong",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
        },
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
        },
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": []},
            "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
        },
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "foreign", "version": "1.0.0"},
        },
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blender-mcp", "version": "999"},
        },
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
            "extra": True,
        },
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
        },
    ],
    ids=(
        "missing",
        "protocol",
        "capability",
        "capability-type",
        "name",
        "version",
        "extra",
        "mixed",
    ),
)
def test_live_rejects_malformed_or_wrong_initialize_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initialize_result
) -> None:
    session = Session(initialize_result=initialize_result)
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)

    with pytest.raises(InstallerError, match="MCP handshake failed"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert handle.closed and handle.terminated and handle.waited == 2.0


@pytest.mark.parametrize("listener", ["missing", "foreign", "ambiguous"])
def test_live_rejects_listener_not_uniquely_owned_by_selected_blender(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, listener: str
) -> None:
    session = Session()
    bundle, inspection, probe, _, hostile = _live(tmp_path, monkeypatch, session, listener=listener)
    with pytest.raises(InstallerError, match="selected Blender listener verification failed"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert not session.calls


@pytest.mark.parametrize(
    "tools",
    [
        MANIFEST.tools[:-1],
        (*MANIFEST.tools, "extra"),
        tuple(reversed(MANIFEST.tools)),
        (*MANIFEST.tools[:-1], MANIFEST.tools[0]),
    ],
    ids=("missing", "extra", "reordered", "duplicate"),
)
def test_live_rejects_any_catalog_difference_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tools
) -> None:
    session = Session(tools)
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    with pytest.raises(InstallerError, match="MCP catalog verification failed"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert handle.closed and handle.terminated and handle.waited == 2.0
    assert all("execute" not in call[0] for call in session.calls)


@pytest.mark.parametrize(
    "failure,error",
    [
        ("initialize", "MCP handshake failed"),
        ("list", "MCP catalog verification failed"),
        ("call", "Blender read-only verification failed"),
        ("call_result", "Blender read-only verification failed"),
        ("close", "MCP cleanup failed"),
        ("terminate", "MCP cleanup failed"),
        ("wait", "MCP cleanup failed"),
    ],
)
def test_live_redacts_failures_and_always_closes_terminates_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, error: str
) -> None:
    session = Session(fail=failure)
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    with pytest.raises(InstallerError, match=error) as caught:
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert "secret" not in str(caught.value)
    assert handle.closed and handle.terminated and handle.waited == 2.0


@pytest.mark.parametrize("failure", ["stdout", "stderr", "client"])
def test_owned_handle_cleans_every_post_spawn_transport_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(
        tmp_path, monkeypatch, session, handle_fail=failure
    )

    with pytest.raises(InstallerError, match="MCP handshake failed") as caught:
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert "secret" not in str(caught.value)
    assert handle.opened and handle.closed and handle.terminated and handle.waited == 2.0


def test_atomic_spawn_failure_has_no_unowned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(
        tmp_path, monkeypatch, session, fail_spawn=True
    )

    with pytest.raises(InstallerError, match="MCP spawn failed"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command == inspection.runtime_command
    assert not handle.opened and not handle.closed and not handle.terminated and not handle.waited


def test_cleanup_failure_supersedes_operation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session(fail="initialize")
    bundle, inspection, probe, handle, hostile = _live(
        tmp_path, monkeypatch, session, handle_fail="close"
    )

    with pytest.raises(InstallerError, match="MCP cleanup failed"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert handle.closed and handle.terminated and handle.waited == 2.0


def test_live_uses_fresh_authoritative_inspection_not_caller_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    fresh = replace(inspection, runtime=False)
    monkeypatch.setattr(verification, "inspect_installation", lambda *args: fresh)

    with pytest.raises(InstallerError, match="installation inspection is not exact"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command is None and not handle.opened


def test_live_rejects_fresh_snapshot_divergence_before_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    fresh = replace(
        inspection,
        managed_images=("changed", *inspection.managed_images[1:]),
    )
    monkeypatch.setattr(verification, "inspect_installation", lambda *args: fresh)

    with pytest.raises(InstallerError, match="stale installation inspection"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command is None and not handle.opened


def test_live_detects_managed_target_change_after_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    original_close = handle.close

    def mutating_close():
        original_close()
        inspection.roots.userpref_target.write_text("changed-during-cleanup")

    monkeypatch.setattr(handle, "close", mutating_close)
    with pytest.raises(InstallerError, match="managed targets changed during verification"):
        verify_live(
            bundle,
            inspection,
            inspection.runtime_command,
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert handle.closed and handle.terminated and handle.waited == 2.0


def test_live_rejects_unconfigured_command_before_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    bundle, inspection, probe, handle, hostile = _live(tmp_path, monkeypatch, session)
    with pytest.raises(InstallerError, match="managed runtime command mismatch"):
        verify_live(
            bundle,
            inspection,
            (sys.executable, "-c", "print('foreign')"),
            inspection.host.codex_bin,
            hostile,
            probe,
        )
    assert probe.command is None
    assert not handle.opened


def test_fixed_catalog_is_exactly_ordered_and_has_single_safe_probe() -> None:
    assert len(MANIFEST.tools) == 26
    assert MANIFEST.tools[2] == "get_blendfile_summary_datablocks"
    forbidden = ("execute", "render", "screenshot", "_for_cli")
    assert not any(part in "get_blendfile_summary_datablocks" for part in forbidden)
    assert json.loads(json.dumps(list(MANIFEST.tools))) == list(MANIFEST.tools)
