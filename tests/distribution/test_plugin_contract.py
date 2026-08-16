from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins/blender-mcp-installer"
SKILL = PLUGIN / "skills/install-official-blender-mcp/SKILL.md"
MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
GUIDE = ROOT / "docs/distribute-official-blender-mcp.md"


def _marked(text: str, name: str) -> str:
    begin = f"<!-- {name}_BEGIN -->"
    end = f"<!-- {name}_END -->"
    assert text.count(begin) == text.count(end) == 1
    return text.split(begin, 1)[1].split(end, 1)[0]


def _shell_block(text: str, name: str) -> str:
    marked = _marked(text, name)
    assert marked.count("```bash") == 1
    assert marked.count("```") == 2
    return marked.split("```bash", 1)[1].split("```", 1)[0].strip()


def _marketplace_validator(text: str) -> str:
    smoke = _shell_block(text, "MARKETPLACE_SMOKE")
    return smoke.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]


def test_manifest_is_skill_only_and_validator_shaped() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
    assert set(manifest) == {
        "name",
        "version",
        "description",
        "author",
        "skills",
        "interface",
    }
    assert manifest["name"] == "blender-mcp-installer"
    assert manifest["version"] == "1.0.0"
    assert manifest["skills"] == "./skills/"
    assert "mcpServers" not in manifest
    assert "apps" not in manifest
    assert set(manifest["author"]) == {"name"}
    assert set(manifest["interface"]) == {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    }


def test_marketplace_entry_resolves_to_intact_plugin_artifacts() -> None:
    marketplace = json.loads(MARKETPLACE.read_text())
    assert set(marketplace) == {"name", "interface", "plugins"}
    entry = marketplace["plugins"]
    assert len(entry) == 1
    assert entry[0] == {
        "name": "blender-mcp-installer",
        "source": {"source": "local", "path": "./plugins/blender-mcp-installer"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    assert (MARKETPLACE.parents[2] / entry[0]["source"]["path"]).resolve() == PLUGIN.resolve()

    sums = (PLUGIN / "artifacts/SHA256SUMS").read_text().splitlines()
    assert len(sums) == 4
    for line in sums:
        digest, filename = line.split("  ", 1)
        assert hashlib.sha256((PLUGIN / "artifacts" / filename).read_bytes()).hexdigest() == digest


def test_skill_has_valid_frontmatter_and_no_machine_paths() -> None:
    text = SKILL.read_text()
    frontmatter = text.split("---", 2)[1]
    assert "name: install-official-blender-mcp" in frontmatter
    assert "description:" in frontmatter
    for path in (SKILL, GUIDE):
        content = path.read_text()
        assert "/Users/" not in content
        assert "/home/" not in content
        assert "~/.codex" not in content


def test_trust_bootstrap_is_fail_fast_commit_derived_and_hook_free() -> None:
    block = _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP")
    required_in_order = [
        "set -euo pipefail",
        ': "${SOURCE_DISTRIBUTION_ROOT:?set source repository path}"',
        ': "${EXPECTED_DISTRIBUTION_COMMIT:?set reviewed 40-hex commit}"',
        "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY",
        "unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONINSPECT",
        "export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1",
        'test "$(git -C "$SOURCE_DISTRIBUTION_ROOT" rev-parse HEAD)" =',
        'git -C "$SOURCE_DISTRIBUTION_ROOT" diff --quiet',
        'git -C "$SOURCE_DISTRIBUTION_ROOT" diff --cached --quiet',
        "--untracked-files=all -- .agents plugins/blender-mcp-installer",
        'TRUST_PARENT="$(mktemp -d /private/tmp/blender-mcp-trust.XXXXXX)"',
        'chmod 700 "$TRUST_PARENT"',
        "worktree add --detach --no-checkout",
        'read-tree "$EXPECTED_DISTRIBUTION_COMMIT"',
        'archive --format=tar "$EXPECTED_DISTRIBUTION_COMMIT"',
        'test -z "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" symbolic-ref -q HEAD || true)"',
        'git -C "$TRUSTED_DISTRIBUTION_ROOT" show',
        'DISTRIBUTION_ROOT="$TRUSTED_DISTRIBUTION_ROOT"',
        'PLUGIN_ROOT="$DISTRIBUTION_ROOT/plugins/blender-mcp-installer"',
        'BUNDLE_ROOT="$PLUGIN_ROOT/artifacts"',
        'cmp "$TRUSTED_CHECKSUMS" "$BUNDLE_ROOT/SHA256SUMS"',
        '(cd "$BUNDLE_ROOT" && shasum -a 256 -c "$TRUSTED_CHECKSUMS")',
    ]
    positions = [block.index(fragment) for fragment in required_in_order]
    assert positions == sorted(positions)
    assert block.count('core.hooksPath="$EMPTY_HOOKS"') == 3
    assert "git checkout" not in block
    assert "python" not in block.lower().replace("pythonpath", "").replace(
        "pythonhome", ""
    ).replace("pythonuserbase", "").replace("pythonstartup", "").replace(
        "pythoninspect", ""
    ).replace("pythonbreakpoint", "").replace("pythonnousersite", "").replace("pythonsafepath", "")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _trust_fixture(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "source"
    artifact_root = repo / "plugins/blender-mcp-installer/artifacts"
    (repo / ".agents/plugins").mkdir(parents=True)
    (repo / "plugins/blender-mcp-installer/scripts").mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    (repo / ".agents/plugins/marketplace.json").write_text("{}\n")
    (repo / "plugins/blender-mcp-installer/scripts/install.py").write_text("trusted\n")
    payload = b"payload\n"
    (artifact_root / "payload").write_bytes(payload)
    (artifact_root / "SHA256SUMS").write_text(f"{hashlib.sha256(payload).hexdigest()}  payload\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD")


def _trust_env(repo: Path, commit: str, tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    hook_sentinel = tmp_path / "hook-ran"
    python_sentinel = tmp_path / "sitecustomize-ran"
    hook = repo / ".git/hooks/post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch {hook_sentinel}\n")
    hook.chmod(0o700)
    hostile_python = tmp_path / "hostile-python"
    hostile_python.mkdir()
    (hostile_python / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(python_sentinel)!r}).touch()\n"
    )
    env = os.environ.copy()
    env.update(
        SOURCE_DISTRIBUTION_ROOT=str(repo),
        EXPECTED_DISTRIBUTION_COMMIT=commit,
        BLENDER_BIN="/usr/bin/true",
        CODEX_BIN="/usr/bin/true",
        GIT_DIR=str(tmp_path / "redirected-git-dir"),
        GIT_WORK_TREE=str(tmp_path / "redirected-work-tree"),
        PYTHONPATH=str(hostile_python),
        PYTHONHOME=str(tmp_path / "redirected-python-home"),
        HOOK_SENTINEL=str(hook_sentinel),
        PYTHON_SENTINEL=str(python_sentinel),
    )
    return env, hook_sentinel, python_sentinel


def test_trust_bootstrap_executes_without_source_hooks_or_redirected_environment(
    tmp_path: Path,
) -> None:
    repo, commit = _trust_fixture(tmp_path)
    env, hook_sentinel, python_sentinel = _trust_env(repo, commit, tmp_path)
    bootstrap = _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP")
    cleanup = _shell_block(SKILL.read_text(), "TRUST_CLEANUP")
    script = "\n".join(
        (
            bootstrap,
            'printf "replaced\\n" > "$SOURCE_DISTRIBUTION_ROOT/plugins/blender-mcp-installer/scripts/install.py"',
            'test "$(cat "$PLUGIN_ROOT/scripts/install.py")" = trusted',
            'test ! -e "$HOOK_SENTINEL"',
            'test ! -e "$PYTHON_SENTINEL"',
            cleanup,
        )
    )
    subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True, text=True)
    assert not hook_sentinel.exists()
    assert not python_sentinel.exists()


@pytest.mark.parametrize("mutation", ["dirty_script", "scoped_untracked", "checksum_tamper"])
def test_trust_bootstrap_rejects_dirty_or_tampered_source_before_import(
    tmp_path: Path, mutation: str
) -> None:
    repo, commit = _trust_fixture(tmp_path)
    marker = tmp_path / "imported"
    install = repo / "plugins/blender-mcp-installer/scripts/install.py"
    if mutation == "dirty_script":
        install.write_text(f"touch {marker}\n")
    elif mutation == "scoped_untracked":
        (install.parent / "untracked.py").write_text(f"touch {marker}\n")
    else:
        artifact_root = repo / "plugins/blender-mcp-installer/artifacts"
        payload = b"tampered\n"
        (artifact_root / "payload").write_bytes(payload)
        (artifact_root / "SHA256SUMS").write_text(
            f"{hashlib.sha256(payload).hexdigest()}  payload\n"
        )
    env, _, _ = _trust_env(repo, commit, tmp_path)
    result = subprocess.run(
        ["bash", "-c", _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not marker.exists()


def test_disposable_marketplace_smoke_is_isolated_and_schema_checked() -> None:
    text = SKILL.read_text()
    smoke = _shell_block(text, "MARKETPLACE_SMOKE")
    for fragment in (
        'SMOKE_HOME="$(mktemp -d /private/tmp/blender-mcp-marketplace.XXXXXX)"',
        'SMOKE_CODEX_HOME="$SMOKE_HOME/.codex"',
        'chmod 700 "$SMOKE_HOME"',
        'chmod 700 "$SMOKE_CODEX_HOME"',
        'HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH"',
        '"$CODEX_BIN" plugin marketplace add "$DISTRIBUTION_ROOT"',
        '"$CODEX_BIN" plugin add "blender-mcp-installer@$MARKETPLACE_NAME"',
        '"$CODEX_BIN" plugin list --marketplace "$MARKETPLACE_NAME" --json',
        '"$PYTHON_BIN" -I -c "$MARKETPLACE_LIST_CHECK"',
    ):
        assert fragment in smoke
    assert "DISPOSABLE_CODEX_API_KEY" not in smoke


@pytest.mark.parametrize(
    "payload,message",
    [
        ([], "top-level object"),
        ({"installed": []}, "exactly installed and available"),
        ({"installed": [], "available": [], "extra": []}, "exactly installed and available"),
        ({"installed": {}, "available": []}, "installed must be an array"),
        ({"installed": [], "available": {}}, "available must be an array"),
        ({"installed": [1], "available": []}, "items must be objects with string names"),
        ({"installed": [], "available": []}, "exactly one installed blender-mcp-installer"),
        (
            {
                "installed": [
                    {"name": "blender-mcp-installer"},
                    {"name": "blender-mcp-installer"},
                ],
                "available": [],
            },
            "exactly one installed blender-mcp-installer",
        ),
    ],
)
def test_marketplace_list_validator_fails_actionably(
    tmp_path: Path, payload: object, message: str
) -> None:
    listing = tmp_path / "plugins.json"
    listing.write_text(json.dumps(payload))
    validator = _marketplace_validator(SKILL.read_text())
    result = subprocess.run(
        [sys.executable, "-I", "-c", validator, str(listing)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert message in result.stderr


def test_marketplace_list_validator_accepts_one_installed_plugin(tmp_path: Path) -> None:
    listing = tmp_path / "plugins.json"
    listing.write_text(
        json.dumps(
            {
                "installed": [{"name": "blender-mcp-installer"}],
                "available": [{"name": "other-plugin"}],
            }
        )
    )
    validator = _marketplace_validator(SKILL.read_text())
    subprocess.run(
        [sys.executable, "-I", "-c", validator, str(listing)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_uv_bootstrap_is_local_only_and_repeated_before_every_command() -> None:
    text = SKILL.read_text()
    block = _shell_block(text, "UV_BOOTSTRAP")
    assert 'if test -n "${UV_BIN:-}"' in block
    assert "command -v uv" in block
    assert 'test -x "$HOME/.local/bin/uv"' in block
    assert 'case "$CANDIDATE_UV" in /*)' in block
    assert 'test -x "$CANDIDATE_UV"' in block
    assert '"$CANDIDATE_UV" --version' in block
    assert '"$CANDIDATE_UV" run --help | grep -q -- "--no-sync"' in block
    assert '"$CANDIDATE_UV" run --help | grep -q -- "--no-python-downloads"' in block
    assert '"$CANDIDATE_UV" python find 3.13 --no-project' in block
    assert "--no-python-downloads --no-config" in block
    assert '"$PYTHON_BIN" -I -c' in block
    assert "curl " not in block and "brew " not in block and "pip " not in block

    commands = _marked(text, "INSTALLER_COMMANDS")
    assert commands.count("run_uv_bootstrap") == 4
    assert commands.count('"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN"') == 4
    assert commands.count("--no-python-downloads --no-sync") == 4
    assert commands.count('python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts"') == 4
    assert commands.count('"$PLUGIN_ROOT/scripts/install.py"') == 4


def test_installer_commands_use_exact_real_parser_arguments_and_consents() -> None:
    commands = _marked(SKILL.read_text(), "INSTALLER_COMMANDS")
    common = (
        '--bundle-root "$BUNDLE_ROOT"',
        '--expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT"',
        '--blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"',
    )
    for command in ("inspect", "install", "verify", "rollback"):
        block = _shell_block(commands, command.upper())
        assert f'"$PLUGIN_ROOT/scripts/install.py" {command}' in block
        assert all(argument in block for argument in common)
    install = _shell_block(commands, "INSTALL")
    for flag in (
        "--allow-extension-install",
        "--allow-online-access",
        "--allow-localhost-bridge",
        "--approve-arbitrary-python",
    ):
        assert install.count(flag) == 1
    assert '--receipt "$RECEIPT_PATH"' in _shell_block(commands, "ROLLBACK")
    assert "--receipt" not in install


def test_skill_requires_four_fresh_answers_and_operator_lifecycle_checkpoints() -> None:
    text = SKILL.read_text()
    assert "Ask separately and wait for an explicit answer to each checkpoint" in text
    for wording in (
        "install and enable the reviewed Blender extension",
        "enable Blender Allow Online Access",
        "open the localhost:9876 bridge",
        "expose arbitrary-Python MCP tools",
    ):
        assert wording in text
    assert "Receipt consent evidence is audit-only and never authorization" in text
    assert "Start the selected Blender normally, then confirm it is running" in text
    assert "Close Blender normally and confirm it is closed before repair or rollback" in text
    assert "Never start, terminate, or force-close Blender" in text


def test_docs_state_security_side_effects_delivery_and_canary_limits() -> None:
    skill = SKILL.read_text()
    guide = GUIDE.read_text()
    combined = skill + guide
    for wording in (
        "SHA-256 provides integrity, not authenticity",
        "reviewed immutable distribution commit is the authenticity boundary",
        "network-assisted",
        "exact-version, hash-locked wheels",
        "uv execution cache",
        ".cache/compat.dat",
        "receipt",
        "Darwin arm64",
        "Blender >=5.2.0,<5.3.0",
        "local STDIO",
        "delivery adapter",
        "not another MCP server",
        "LOCAL_LLM_INVOCATION_STATUS: NOT_RUN",
        "SECOND_MAC_CANARY_STATUS: NOT_RUN",
        "DISPOSABLE_CODEX_API_KEY",
        "Never copy normal Codex credentials",
    ):
        assert wording in combined
    assert "EXPECTED_DISTRIBUTION_COMMIT" in guide
    assert "manifest.json" in guide
    assert (
        "EXPECTED_DISTRIBUTION_COMMIT comes from the reviewed repository or release channel"
        in guide
    )


def test_docs_index_and_repository_checks_include_plugin_contract() -> None:
    assert (
        "[Official Blender MCP distributable installer](distribute-official-blender-mcp.md)"
        in (ROOT / "docs/README.md").read_text()
    )
    checks = (ROOT / "scripts/checks.sh").read_text()
    assert '"$UV_BIN" run --frozen pytest -q' in checks
    assert 'scripts/validate_plugin.py" plugins/blender-mcp-installer' in checks
