from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins/blender-mcp-installer"
SKILL = PLUGIN / "skills/install-official-blender-mcp/SKILL.md"
MARKETPLACE = ROOT / ".agents/plugins/marketplace.json"
GUIDE = ROOT / "docs/distribute-official-blender-mcp.md"
MARKETPLACE_PROJECTOR = PLUGIN / "scripts/project_marketplace.py"


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
    assert re.fullmatch(r"1\.0\.0\+codex\.\d{14}", manifest["version"])
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
    assert marketplace["name"] == "official-blender-mcp"
    assert (
        'plugin add "blender-mcp-installer@official-blender-mcp"'
        in SKILL.read_text()
    )
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
        'OPERATOR_PATH="$PATH"',
        "PATH=/usr/bin:/bin:/usr/sbin:/sbin",
        "export PATH",
        ': "${SOURCE_DISTRIBUTION_ROOT:?set source repository path}"',
        ': "${EXPECTED_DISTRIBUTION_COMMIT:?set reviewed 40-hex commit}"',
        "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY",
        "unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONINSPECT",
        "export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1",
        'SOURCE_GIT_MARKER="$SOURCE_DISTRIBUTION_ROOT/.git"',
        'SOURCE_OBJECTS_ROOT="$(cd "$SOURCE_COMMON_GIT_DIR/objects" && pwd -P)"',
        'SOURCE_INDEX="$SOURCE_GIT_DIR/index"',
        'SOURCE_HEAD_FILE="$SOURCE_GIT_DIR/HEAD"',
        'test "$SOURCE_HEAD_COMMIT" = "$EXPECTED_DISTRIBUTION_COMMIT"',
        'TRUST_PARENT="$(mktemp -d /private/tmp/blender-mcp-trust.XXXXXX)"',
        'chmod 700 "$TRUST_PARENT"',
        'PRIVATE_GIT_DIR="$TRUST_PARENT/private.git"',
        'EMPTY_TEMPLATE="$TRUST_PARENT/empty-template"',
        'GIT_SAFE_HOME="$TRUST_PARENT/git-home"',
        "GIT_SAFE_ENV=(/usr/bin/env -i",
        "GIT_CONFIG_NOSYSTEM=1",
        "GIT_CONFIG_GLOBAL=/dev/null",
        "GIT_NO_REPLACE_OBJECTS=1",
        'init --bare --template="$EMPTY_TEMPLATE" "$PRIVATE_GIT_DIR"',
        ': > "$PRIVATE_GIT_DIR/config"',
        ': > "$PRIVATE_GIT_DIR/info/attributes"',
        'printf \'%s\\n\' "$SOURCE_OBJECTS_ROOT" > "$PRIVATE_GIT_DIR/objects/info/alternates"',
        '/bin/cp "$SOURCE_INDEX" "$PRIVATE_GIT_DIR/index"',
        'test ! -s "$PRIVATE_GIT_DIR/config"',
        'test ! -s "$PRIVATE_GIT_DIR/info/attributes"',
        'GIT_PRIVATE=("${GIT_SAFE_ENV[@]}" /usr/bin/git --no-pager --no-replace-objects',
        '--git-dir="$PRIVATE_GIT_DIR"',
        "-c core.fsmonitor=false",
        '-c core.hooksPath="$PRIVATE_GIT_DIR/hooks"',
        'GIT_SOURCE_VIEW=("${GIT_PRIVATE[@]}" --work-tree="$SOURCE_DISTRIBUTION_ROOT")',
        '"${GIT_PRIVATE[@]}" cat-file -e "$EXPECTED_DISTRIBUTION_COMMIT^{commit}"',
        '"${GIT_SOURCE_VIEW[@]}" diff --no-ext-diff --cached --quiet',
        '"${GIT_PRIVATE[@]}" read-tree "$EXPECTED_DISTRIBUTION_COMMIT"',
        '"${GIT_SOURCE_VIEW[@]}" diff --no-ext-diff --quiet',
        "--untracked-files=all -- .agents plugins/blender-mcp-installer",
        "worktree add --detach --no-checkout",
        'GIT_TRUSTED=("${GIT_SAFE_ENV[@]}" /usr/bin/git --no-pager --no-replace-objects',
        '-C "$TRUSTED_DISTRIBUTION_ROOT")',
        'archive --format=tar "$EXPECTED_DISTRIBUTION_COMMIT"',
        'test -z "$("${GIT_TRUSTED[@]}" symbolic-ref -q HEAD || true)"',
        '"${GIT_PRIVATE[@]}" cat-file blob',
        'DISTRIBUTION_ROOT="$TRUSTED_DISTRIBUTION_ROOT"',
        'PLUGIN_ROOT="$DISTRIBUTION_ROOT/plugins/blender-mcp-installer"',
        'BUNDLE_ROOT="$PLUGIN_ROOT/artifacts"',
        'cmp "$TRUSTED_CHECKSUMS" "$BUNDLE_ROOT/SHA256SUMS"',
        '(cd "$BUNDLE_ROOT" && shasum -a 256 -c "$TRUSTED_CHECKSUMS")',
    ]
    positions = [block.index(fragment) for fragment in required_in_order]
    assert positions == sorted(positions)
    assert block.count('core.hooksPath="$PRIVATE_GIT_DIR/hooks"') == 2
    assert block.count('"${GIT_PRIVATE[@]}"') >= 5
    assert block.count('"${GIT_SOURCE_VIEW[@]}"') == 3
    assert block.count('"${GIT_TRUSTED[@]}"') >= 5
    assert "GIT_CONFIG_COUNT" not in block
    assert "GIT_REPLACE_REF_BASE" not in block
    assert "$(git " not in block and "\ngit " not in block
    assert '--git-dir="$SOURCE_GIT_DIR"' not in block
    assert '-C "$SOURCE_DISTRIBUTION_ROOT"' not in block
    cleanup = _shell_block(SKILL.read_text(), "TRUST_CLEANUP")
    assert "trap - EXIT" in cleanup
    assert '"${GIT_PRIVATE[@]}" worktree remove' in cleanup
    assert "\ngit " not in cleanup
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
    (repo / "plugins/blender-mcp-installer/.codex-plugin").mkdir(parents=True)
    (repo / "plugins/blender-mcp-installer/scripts").mkdir(parents=True)
    artifact_root.mkdir(parents=True)
    (repo / ".agents/plugins/marketplace.json").write_text(
        '{"name":"official-blender-mcp","interface":{},"plugins":[]}\n'
    )
    (repo / "plugins/blender-mcp-installer/scripts/install.py").write_text("trusted\n")
    (repo / "plugins/blender-mcp-installer/.codex-plugin/plugin.json").write_text(
        '{"name":"blender-mcp-installer","version":"1.0.0+codex.fixture"}\n'
    )
    if MARKETPLACE_PROJECTOR.exists():
        shutil.copy2(
            MARKETPLACE_PROJECTOR,
            repo / "plugins/blender-mcp-installer/scripts/project_marketplace.py",
        )
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


def test_trust_bootstrap_ignores_hostile_operator_path(tmp_path: Path) -> None:
    repo, commit = _trust_fixture(tmp_path)
    hostile_bin = tmp_path / "hostile-bin"
    hostile_bin.mkdir()
    sentinel = tmp_path / "hostile-tar-ran"
    hostile_tar = hostile_bin / "tar"
    hostile_tar.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 97\n")
    hostile_tar.chmod(0o700)
    env, _, _ = _trust_env(repo, commit, tmp_path)
    env["PATH"] = f"{hostile_bin}:{env['PATH']}"
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
        )
    )
    subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True, text=True)
    assert not sentinel.exists()


def test_documented_first_inspect_keeps_trusted_checkout_clean(tmp_path: Path) -> None:
    source = tmp_path / "source"
    real_uv = Path(shutil.which("uv") or Path.home() / ".local/bin/uv")
    clang = Path("/usr/bin/clang")
    for executable in (real_uv, clang):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            pytest.skip(f"required executable is unavailable: {executable}")
    codex = tmp_path / "codex"
    codex.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  --version) echo "codex-cli 0.148.0-alpha.9" ;;\n'
        '  "mcp get --help") echo "usage: codex mcp get --json" ;;\n'
        '  "plugin marketplace add --help"|"plugin add --help") echo usage ;;\n'
        '  "mcp get blender --json") echo "{}" ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n"
    )
    codex.chmod(0o700)
    blender_source = tmp_path / "fake_blender.c"
    blender = tmp_path / "Blender"
    blender_source.write_text(
        r"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "--version") == 0) {
    puts("Blender 5.2.0");
    return 0;
  }
  if (argc >= 3 && strcmp(argv[1], "--background") == 0) {
    printf("__BLENDER_MCP_INSTALLER__{\"architecture\":\"arm64\","
           "\"autostart\":null,\"binary_path\":\"%s\","
           "\"config_root\":\"%s\",\"enabled\":false,"
           "\"extensions_root\":\"%s\",\"host\":null,"
           "\"online_access\":false,\"port\":null,"
           "\"repository\":\"user_default\","
           "\"user_resources\":\"%s\",\"version\":[5,2,0]}\n",
           argv[0], getenv("BLENDER_USER_CONFIG"),
           getenv("BLENDER_USER_EXTENSIONS"), getenv("BLENDER_USER_RESOURCES"));
    return 0;
  }
  return 2;
}
"""
    )
    subprocess.run([clang, "-arch", "arm64", "-o", blender, blender_source], check=True)
    python = str(
        Path(
            subprocess.run(
                [
                    real_uv,
                    "python",
                    "find",
                    "3.13",
                    "--no-project",
                    "--no-python-downloads",
                    "--no-config",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        ).resolve()
    )
    uv = tmp_path / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'if test "$1" = --version; then\n'
        '  printf "%s\\n" "uv 0.12.2"\n'
        "  exit 0\n"
        "fi\n"
        'if test "$1" = python && test "$2" = find; then\n'
        f"  printf '%s\\n' {python!r}\n"
        "  exit 0\n"
        "fi\n"
        f'exec {str(real_uv)!r} "$@"\n'
    )
    uv.chmod(0o700)
    uv_link = tmp_path / "uv-link"
    uv_link.symlink_to(uv)
    _git(ROOT, "worktree", "add", "--detach", str(source), "HEAD")
    try:
        commit = _git(source, "rev-parse", "HEAD")
        profile = tmp_path / "profile"
        resources = profile / "blender/resources"
        for path in (
            profile,
            profile / "codex",
            resources,
            resources / "config",
            resources / "extensions",
        ):
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.chmod(0o700)
        script = "\n".join(
            (
                "{",
                _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
                "} >&2",
                _shell_block(SKILL.read_text(), "UV_BOOTSTRAP"),
                'INSPECT_OUTPUT="$(',
                _shell_block(SKILL.read_text(), "INSPECT"),
                ')"',
                'test -z "$(find "$TRUSTED_DISTRIBUTION_ROOT" -type d -name __pycache__ -print -quit)"',
                'test -z "$(find "$TRUSTED_DISTRIBUTION_ROOT" -type f \\( -name "*.pyc" -o -name "*.pyo" \\) -print -quit)"',
                'test -z "$("${GIT_TRUSTED[@]}" status --porcelain=v1 --untracked-files=all)"',
                'printf "%s\\n" "$INSPECT_OUTPUT"',
                _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
            )
        )
        env = os.environ.copy()
        env.update(
            SOURCE_DISTRIBUTION_ROOT=str(source),
            EXPECTED_DISTRIBUTION_COMMIT=commit,
            BLENDER_BIN=str(blender),
            CODEX_BIN=str(codex),
            UV_BIN=str(uv_link),
            HOME=str(profile),
            CODEX_HOME=str(profile / "codex"),
            BLENDER_USER_RESOURCES=str(resources),
            BLENDER_USER_CONFIG=str(resources / "config"),
            BLENDER_USER_EXTENSIONS=str(resources / "extensions"),
        )
        result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.endswith("\n") and len(result.stdout.splitlines()) == 1
        payload = json.loads(result.stdout)
        assert payload["command"] == "inspect"
        assert payload["host"]["uv_version"] == "0.12.2"
        assert not tuple(source.rglob("__pycache__"))
        assert not tuple(source.rglob("*.py[co]"))
        assert not _git(source, "status", "--porcelain=v1", "--untracked-files=all")
    finally:
        _git(ROOT, "worktree", "remove", "--force", str(source))


def _executable_sentinel(tmp_path: Path, name: str) -> tuple[Path, Path]:
    sentinel = tmp_path / f"{name}-ran"
    helper = tmp_path / name
    helper.write_text(f"#!/bin/sh\ntouch {sentinel}\nexit 0\n")
    helper.chmod(0o700)
    return helper, sentinel


@pytest.mark.parametrize("source", ["environment", "repository"])
def test_trust_bootstrap_never_executes_git_fsmonitor_config(tmp_path: Path, source: str) -> None:
    repo, commit = _trust_fixture(tmp_path)
    helper, sentinel = _executable_sentinel(tmp_path, f"{source}-fsmonitor")
    env, _, _ = _trust_env(repo, commit, tmp_path)
    if source == "environment":
        env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="core.fsmonitor",
            GIT_CONFIG_VALUE_0=str(helper),
        )
    else:
        _git(repo, "config", "core.fsmonitor", str(helper))
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'test ! -e "$CONFIG_SENTINEL"',
            _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
        )
    )
    env["CONFIG_SENTINEL"] = str(sentinel)
    subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True, text=True)
    assert not sentinel.exists()


def test_trust_bootstrap_ignores_source_filter_and_info_attributes(tmp_path: Path) -> None:
    repo, commit = _trust_fixture(tmp_path)
    helper, sentinel = _executable_sentinel(tmp_path, "source-filter")
    helper.write_text(f"#!/bin/sh\ntouch {sentinel}\ncat\n")
    helper.chmod(0o700)
    _git(repo, "config", "filter.evil.clean", str(helper))
    _git(repo, "config", "filter.evil.smudge", str(helper))
    _git(repo, "config", "filter.evil.required", "true")
    (repo / ".git/info/attributes").write_text(
        "plugins/blender-mcp-installer/scripts/install.py filter=evil\n"
    )
    install = repo / "plugins/blender-mcp-installer/scripts/install.py"
    stat = install.stat()
    os.utime(install, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    env, _, _ = _trust_env(repo, commit, tmp_path)
    env["CONFIG_SENTINEL"] = str(sentinel)
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'test ! -e "$CONFIG_SENTINEL"',
            _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
        )
    )
    subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True, text=True)
    assert not sentinel.exists()


def test_trust_bootstrap_rejects_tree_replace_attack_before_materialization(
    tmp_path: Path,
) -> None:
    repo, commit = _trust_fixture(tmp_path)
    reviewed_tree = _git(repo, "rev-parse", f"{commit}^{{tree}}")
    (repo / "plugins/blender-mcp-installer/scripts/install.py").write_text("MALICIOUS\n")
    _git(repo, "add", "plugins/blender-mcp-installer/scripts/install.py")
    malicious_tree = _git(repo, "write-tree")
    _git(repo, "replace", reviewed_tree, malicious_tree)
    evidence = tmp_path / "materialized-installer"
    env, _, _ = _trust_env(repo, commit, tmp_path)
    env["MATERIALIZED_EVIDENCE"] = str(evidence)
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'cat "$PLUGIN_ROOT/scripts/install.py" > "$MATERIALIZED_EVIDENCE"',
            _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not evidence.exists()


@pytest.mark.parametrize("index_flag", ["--assume-unchanged", "--skip-worktree"])
def test_trust_bootstrap_rejects_dirty_tracked_source_hidden_by_index_flag(
    tmp_path: Path, index_flag: str
) -> None:
    repo, commit = _trust_fixture(tmp_path)
    relative_install = "plugins/blender-mcp-installer/scripts/install.py"
    _git(repo, "update-index", index_flag, relative_install)
    (repo / relative_install).write_text("MALICIOUS WORKTREE\n")
    import_sentinel = tmp_path / "plugin-imported"
    materialized = tmp_path / "materialized-installer"
    env, _, _ = _trust_env(repo, commit, tmp_path)
    env.update(
        PLUGIN_IMPORT_SENTINEL=str(import_sentinel),
        MATERIALIZED_EVIDENCE=str(materialized),
    )
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'touch "$PLUGIN_IMPORT_SENTINEL"',
            'cat "$PLUGIN_ROOT/scripts/install.py" > "$MATERIALIZED_EVIDENCE"',
            _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not import_sentinel.exists()
    assert not materialized.exists()


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
        '"$CODEX_BIN" plugin marketplace add "$PERSISTENT_MARKETPLACE_ROOT"',
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
    assert 'PATH="$OPERATOR_PATH" command -v uv' in block
    assert 'test -x "$HOME/.local/bin/uv"' in block
    assert 'case "$CANDIDATE_UV" in /*)' in block
    assert 'test -x "$CANDIDATE_UV"' in block
    assert '"$CANDIDATE_UV" --version' in block
    assert '"$CANDIDATE_UV" run --help | grep -q -- "--no-sync"' in block
    assert '"$CANDIDATE_UV" run --help | grep -q -- "--no-python-downloads"' in block
    assert '"$CANDIDATE_UV" python find 3.13 --no-project' in block
    assert "--no-python-downloads --no-config" in block
    assert '"$PYTHON_BIN" -I -c' in block
    assert "resolve(strict=True)" in block
    assert 'test -f "$CANONICAL_UV"' in block
    assert 'test ! -L "$CANONICAL_UV"' in block
    assert block.count('"$CANONICAL_UV" --version') == 1
    assert block.count('"$CANONICAL_UV" run --help') == 2
    assert 'UV_BIN="$CANONICAL_UV"' in block
    assert "curl " not in block and "brew " not in block and "pip " not in block

    commands = _marked(text, "INSTALLER_COMMANDS")
    assert commands.count("run_uv_bootstrap") == 4
    assert commands.count('"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN"') == 4
    assert commands.count("--no-python-downloads --no-sync") == 4
    assert commands.count('python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts"') == 4
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


def test_skill_defaults_four_authorizations_and_keeps_lifecycle_checkpoints() -> None:
    text = SKILL.read_text()
    assert "Do not ask four per-install authorization questions" in text
    assert "standing default-allow policy" in text
    for wording in (
        "install and enable the reviewed Blender extension",
        "enable Blender Allow Online Access",
        "open the localhost:9876 bridge",
        "expose arbitrary-Python MCP tools",
    ):
        assert wording in text
    assert "Always pass all four explicit CLI flags" in text
    assert "all_four_collected_for_this_workflow" in text
    assert "Ask separately and wait for an explicit answer to each checkpoint" not in text
    assert "May the installer" not in text
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
    assert '"$UV_BIN" run --frozen pytest -q --ignore=tests/distribution' in checks
    assert '"$UV_BIN" run --frozen --with tomlkit==0.13.3' in checks
    assert "pytest tests/distribution -q" in checks
    assert 'scripts/validate_plugin.py" plugins/blender-mcp-installer' in checks


def _fake_marketplace_codex(tmp_path: Path) -> Path:
    codex = tmp_path / "codex"
    codex.write_text(
        f"#!{sys.executable}\n"
        r'''import json
import os
import shutil
import sys
import time
import tomllib
from pathlib import Path

home = Path(os.environ["CODEX_HOME"])
config = home / "config.toml"
installed = home / "installed"


def read_marketplaces():
    if not config.exists():
        return {}
    return tomllib.loads(config.read_text()).get("marketplaces", {})


def write_marketplaces(marketplaces):
    lines = []
    for name, value in marketplaces.items():
        lines.extend(
            (
                f"[marketplaces.{name}]",
                f"source_type = {json.dumps(value['source_type'])}",
                f"source = {json.dumps(value['source'])}",
                "",
            )
        )
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("\n".join(lines))


args = sys.argv[1:]
if args[:3] == ["plugin", "marketplace", "remove"]:
    marketplaces = read_marketplaces()
    if args[3] not in marketplaces:
        raise SystemExit(1)
    if args[3] == os.environ.get("FAIL_MARKETPLACE_REMOVE"):
        raise SystemExit(44)
    del marketplaces[args[3]]
    write_marketplaces(marketplaces)
elif args[:3] == ["plugin", "marketplace", "add"]:
    source = str(Path(args[3]).resolve())
    if source == os.environ.get("FAIL_MARKETPLACE_ADD"):
        raise SystemExit(42)
    time.sleep(float(os.environ.get("SLEEP_MARKETPLACE_ADD", "0")))
    manifest = json.loads(
        (Path(source) / ".agents/plugins/marketplace.json").read_text()
    )
    name = manifest["name"]
    marketplaces = read_marketplaces()
    if name in marketplaces and marketplaces[name]["source"] != source:
        raise SystemExit(2)
    marketplaces[name] = {"source_type": "local", "source": source}
    write_marketplaces(marketplaces)
elif args == ["plugin", "marketplace", "list", "--json"]:
    marketplaces = read_marketplaces()
    payload = []
    for name, value in marketplaces.items():
        root = Path(value["source"])
        if not (root / ".agents/plugins/marketplace.json").is_file():
            raise SystemExit(3)
        payload.append(
            {
                "name": name,
                "root": str(root),
                "marketplaceSource": {
                    "sourceType": value["source_type"],
                    "source": str(root),
                },
            }
        )
    print(json.dumps({"marketplaces": payload}))
elif args[:2] == ["plugin", "add"]:
    marketplace = args[2].split("@", 1)[1]
    source = read_marketplaces().get(marketplace, {}).get("source")
    if not source:
        raise SystemExit(4)
    plugin = Path(source) / "plugins/blender-mcp-installer"
    version = json.loads((plugin / ".codex-plugin/plugin.json").read_text())["version"]
    cache = home / "plugins/cache" / marketplace / "blender-mcp-installer" / version
    if os.environ.get("FAIL_PLUGIN_ADD"):
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "partial").write_text("partial")
        raise SystemExit(43)
    shutil.copytree(plugin, cache, dirs_exist_ok=True)
    installed.write_text(args[2])
elif args[:2] == ["plugin", "list"] and "--json" in args:
    marketplace = args[args.index("--marketplace") + 1]
    source = read_marketplaces().get(marketplace, {}).get("source")
    if not source or not (Path(source) / ".agents/plugins/marketplace.json").is_file():
        raise SystemExit(5)
    names = [] if not installed.exists() else [{"name": installed.read_text().split("@", 1)[0]}]
    print(json.dumps({"installed": names, "available": []}))
else:
    raise SystemExit(f"unexpected fake Codex arguments: {args!r}")
'''
    )
    codex.chmod(0o700)
    return codex


def _marketplace_source(path: Path, name: str) -> None:
    manifest = path / ".agents/plugins/marketplace.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": name, "interface": {"displayName": name}, "plugins": []})
    )


def _persistent_marketplace_env(
    tmp_path: Path,
) -> tuple[dict[str, str], Path, Path, Path, str]:
    repo, commit = _trust_fixture(tmp_path)
    home = tmp_path / "home"
    codex_home = home / ".codex"
    old_source = tmp_path / "old-source"
    other_source = tmp_path / "other-source"
    for path in (home, codex_home):
        path.mkdir(mode=0o700)
    _marketplace_source(old_source, "official-blender-mcp")
    _marketplace_source(other_source, "other")
    (codex_home / "config.toml").write_text(
        "[marketplaces.other]\n"
        'source_type = "local"\n'
        f"source = {json.dumps(str(other_source.resolve()))}\n\n"
        "[marketplaces.official-blender-mcp]\n"
        'source_type = "local"\n'
        f"source = {json.dumps(str(old_source.resolve()))}\n"
    )
    env, _, _ = _trust_env(repo, commit, tmp_path)
    env.update(
        HOME=str(home),
        CODEX_HOME=str(codex_home),
        CODEX_BIN=str(_fake_marketplace_codex(tmp_path)),
        PYTHON_BIN=sys.executable,
    )
    return env, home, codex_home, old_source, commit


def test_persistent_marketplace_contract_is_commit_bound_and_transactional() -> None:
    text = SKILL.read_text()
    block = _shell_block(text, "PERSISTENT_MARKETPLACE")
    projector = MARKETPLACE_PROJECTOR.read_text()
    required = (
        "run_uv_bootstrap",
        '"$PLUGIN_ROOT/scripts/project_marketplace.py" prepare',
        '--private-git-dir "$PRIVATE_GIT_DIR"',
        '--git-safe-home "$GIT_SAFE_HOME"',
        '--reviewed-commit "$EXPECTED_DISTRIBUTION_COMMIT"',
        '--trusted-checksums "$TRUSTED_CHECKSUMS"',
        '--codex "$CODEX_BIN"',
    )
    projector_required = (
        '".local/share/blender-mcp-installer"',
        "projection_parent / reviewed_commit",
        '"archive", "--format=tar", reviewed_commit',
        'bundle_root / "SHA256SUMS"',
        '"/usr/bin/shasum", "-a", "256", "-c"',
        '"plugin", "marketplace", "remove"',
        '"plugin", "marketplace", "add"',
        '"plugin", "add", f"blender-mcp-installer@{MARKETPLACE_NAME}"',
        "tomllib",
        "marketplace-recovery",
    )
    assert all(fragment in block for fragment in required)
    assert all(fragment in projector for fragment in projector_required)
    assert 'plugin marketplace add "$DISTRIBUTION_ROOT"' not in text
    assert text.index("<!-- TRUST_CLEANUP_BEGIN -->") < text.index(
        "<!-- PERSISTENT_MARKETPLACE_VERIFY_BEGIN -->"
    )


def test_trust_bootstrap_rejects_audit_checkout_at_a_different_head(
    tmp_path: Path,
) -> None:
    repo, reviewed_commit = _trust_fixture(tmp_path)
    (repo / "audit-only").write_text("different head\n")
    _git(repo, "add", "audit-only")
    _git(repo, "commit", "-qm", "audit head")
    env, _, _ = _trust_env(repo, reviewed_commit, tmp_path)
    result = subprocess.run(
        ["bash", "-c", _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_persistent_marketplace_survives_private_cleanup_and_lists_normally(
    tmp_path: Path,
) -> None:
    env, home, codex_home, _, commit = _persistent_marketplace_env(tmp_path)
    recorded_root = tmp_path / "persistent-root"
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'run_uv_bootstrap() { :; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
            'printf "%s\\n" "$PERSISTENT_MARKETPLACE_ROOT" > "$RECORDED_ROOT"',
            _shell_block(SKILL.read_text(), "TRUST_CLEANUP"),
            'test ! -e "$TRUST_PARENT"',
            'test -d "$PERSISTENT_MARKETPLACE_ROOT"',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE_VERIFY"),
        )
    )
    env["RECORDED_ROOT"] = str(recorded_root)
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    projection = Path(recorded_root.read_text().strip())
    assert projection == (
        home
        / ".local/share/blender-mcp-installer/marketplaces/official-blender-mcp"
        / commit
    )
    assert (projection / ".agents/plugins/marketplace.json").is_file()
    artifacts = projection / "plugins/blender-mcp-installer/artifacts"
    digest, filename = (artifacts / "SHA256SUMS").read_text().strip().split("  ")
    assert hashlib.sha256((artifacts / filename).read_bytes()).hexdigest() == digest
    for path in (
        home / ".local/share/blender-mcp-installer",
        home / ".local/share/blender-mcp-installer/marketplaces",
        home / ".local/share/blender-mcp-installer/marketplaces/official-blender-mcp",
        projection,
    ):
        assert path.stat().st_mode & 0o777 == 0o700
    assert not any(path.is_symlink() for path in projection.rglob("*"))
    assert not any(path.stat().st_mode & 0o022 for path in projection.rglob("*"))

    config = (codex_home / "config.toml").read_text()
    assert f"source = {json.dumps(str(projection))}" in config
    assert "[marketplaces.other]" in config
    recovery = home / ".local/state/blender-mcp-installer/marketplace-recovery"
    evidence = tuple(recovery.glob("registration.*/*.json"))
    assert evidence
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in evidence)
    cleanup_evidence = tuple(recovery.glob("registration.*/marketplaces-after-cleanup.json"))
    assert len(cleanup_evidence) == 1
    assert "other-source" not in cleanup_evidence[0].read_text()
    restore = tuple(recovery.glob("registration.*/RESTORE.txt"))
    assert len(restore) == 2
    assert all(f"CODEX_BIN: {env['CODEX_BIN']}" in path.read_text() for path in restore)
    assert all(f"HOME: {home}" in path.read_text() for path in restore)
    assert all(f"CODEX_HOME: {codex_home}" in path.read_text() for path in restore)
    lock = codex_home / ".blender-mcp-marketplace.lock"
    assert lock.stat().st_mode & 0o777 == 0o600
    assert not (home / ".local/state/blender-mcp-installer/receipts").exists()


@pytest.mark.parametrize("failure", ["marketplace_add", "plugin_add"])
def test_marketplace_registration_failure_restores_only_previous_target(
    tmp_path: Path, failure: str
) -> None:
    env, home, codex_home, old_source, commit = _persistent_marketplace_env(tmp_path)
    projection = (
        home
        / ".local/share/blender-mcp-installer/marketplaces/official-blender-mcp"
        / commit
    )
    if failure == "marketplace_add":
        env["FAIL_MARKETPLACE_ADD"] = str(projection)
    else:
        env["FAIL_PLUGIN_ADD"] = "1"
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'run_uv_bootstrap() { :; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    config = (codex_home / "config.toml").read_text()
    assert f"source = {json.dumps(str(old_source.resolve()))}" in config
    assert "[marketplaces.other]" in config
    recovery = home / ".local/state/blender-mcp-installer/marketplace-recovery"
    assert tuple(recovery.glob("registration.*/before.json"))


def test_persistent_marketplace_rejects_checksum_drift_before_registration(
    tmp_path: Path,
) -> None:
    env, home, codex_home, old_source, commit = _persistent_marketplace_env(tmp_path)
    projection = (
        home
        / ".local/share/blender-mcp-installer/marketplaces/official-blender-mcp"
        / commit
    )
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'printf "%064d  payload\\n" 0 > "$TRUSTED_CHECKSUMS"',
            'run_uv_bootstrap() { :; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not projection.exists()
    config = (codex_home / "config.toml").read_text()
    assert f"source = {json.dumps(str(old_source.resolve()))}" in config


def test_persistent_marketplace_always_revalidates_the_python_runner(
    tmp_path: Path,
) -> None:
    env, _, _, _, _ = _persistent_marketplace_env(tmp_path)
    hostile_sentinel = tmp_path / "hostile-python-ran"
    bootstrap_sentinel = tmp_path / "bootstrap-ran"
    hostile_python = tmp_path / "hostile-python-bin"
    hostile_python.write_text(f"#!/bin/sh\ntouch {hostile_sentinel}\nexit 97\n")
    hostile_python.chmod(0o700)
    env.update(
        PYTHON_BIN=str(hostile_python),
        VALID_PYTHON=sys.executable,
        BOOTSTRAP_SENTINEL=str(bootstrap_sentinel),
    )
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'run_uv_bootstrap() { PYTHON_BIN="$VALID_PYTHON"; touch "$BOOTSTRAP_SENTINEL"; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert bootstrap_sentinel.is_file()
    assert not hostile_sentinel.exists()


@pytest.mark.parametrize("unsafe", ["home", "codex_home", "config"])
def test_persistent_marketplace_rejects_writable_profile_paths(
    tmp_path: Path, unsafe: str
) -> None:
    env, home, codex_home, old_source, _ = _persistent_marketplace_env(tmp_path)
    target = {"home": home, "codex_home": codex_home, "config": codex_home / "config.toml"}[
        unsafe
    ]
    target.chmod(0o777 if target.is_dir() else 0o666)
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'run_uv_bootstrap() { :; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert f"source = {json.dumps(str(old_source.resolve()))}" in (
        codex_home / "config.toml"
    ).read_text()


def test_failed_restore_is_reported_and_never_claimed_success(tmp_path: Path) -> None:
    env, home, codex_home, _, _ = _persistent_marketplace_env(tmp_path)
    config = codex_home / "config.toml"
    config.write_text(config.read_text().split("[marketplaces.official-blender-mcp]", 1)[0])
    env.update(
        FAIL_PLUGIN_ADD="1",
        FAIL_MARKETPLACE_REMOVE="official-blender-mcp",
    )
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'run_uv_bootstrap() { :; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
        )
    )
    result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "replacement and restoration failed" in result.stderr
    recovery = home / ".local/state/blender-mcp-installer/marketplace-recovery"
    assert tuple(recovery.glob("registration.*/before.json"))


def test_marketplace_registration_is_serialized_per_codex_home(tmp_path: Path) -> None:
    env, _, codex_home, _, _ = _persistent_marketplace_env(tmp_path)
    env["SLEEP_MARKETPLACE_ADD"] = "0.2"
    script = "\n".join(
        (
            _shell_block(SKILL.read_text(), "TRUST_BOOTSTRAP"),
            'run_uv_bootstrap() { :; }',
            _shell_block(SKILL.read_text(), "PERSISTENT_MARKETPLACE"),
        )
    )
    processes = [
        subprocess.Popen(["bash", "-c", script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=20) + (process.returncode,) for process in processes]
    assert [result[2] for result in results] == [0, 0], results
    assert "[marketplaces.other]" in (codex_home / "config.toml").read_text()
