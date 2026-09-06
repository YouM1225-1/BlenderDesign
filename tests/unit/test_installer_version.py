from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "scripts/update_installer_version.py"
PLUGIN = Path("plugins/blender-mcp-installer")
MANIFEST = PLUGIN / ".codex-plugin/plugin.json"
ORIGINAL_VERSION = "1.0.0+codex.20260905081939"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / SCRIPT), *args], cwd=repo, capture_output=True, text=True
    )


def version(repo: Path) -> str:
    return json.loads((repo / MANIFEST).read_text())["version"]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Version Test")
    git(tmp_path, "config", "user.email", "version@example.invalid")
    git(tmp_path, "config", "commit.gpgsign", "false")
    git(tmp_path, "config", "core.fileMode", "true")
    git(tmp_path, "config", "core.hooksPath", ".githooks")
    for path in (SCRIPT, ".githooks/pre-commit", ".githooks/pre-merge-commit", str(MANIFEST)):
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, destination)
    manifest = json.loads((tmp_path / MANIFEST).read_text())
    manifest["version"] = ORIGINAL_VERSION
    (tmp_path / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    (tmp_path / PLUGIN / "installer.py").write_text("original\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "initial")
    return tmp_path


@pytest.mark.parametrize("change", ["edit", "add", "delete", "rename", "mode", "metadata"])
def test_requires_bump_and_updates_only_once(repo: Path, change: str) -> None:
    target = repo / PLUGIN / "installer.py"
    if change == "edit":
        target.write_text("changed\n")
    elif change == "add":
        (target.parent / "new.bin").write_bytes(b"\x00\xff")
    elif change == "delete":
        target.unlink()
    elif change == "rename":
        target.rename(target.with_name("renamed.py"))
    elif change == "mode":
        target.chmod(0o755)
    else:
        manifest = json.loads((repo / MANIFEST).read_text())
        manifest["description"] = "Changed metadata"
        (repo / MANIFEST).write_text(json.dumps(manifest))
    assert run(repo, "--check").returncode == 1
    assert version(repo) == ORIGINAL_VERSION
    assert run(repo).returncode == 0
    updated = version(repo)
    assert updated > ORIGINAL_VERSION
    assert run(repo, "--check").returncode == 0
    assert run(repo).returncode == 0
    assert version(repo) == updated


def test_unrelated_changes_do_not_bump(repo: Path) -> None:
    (repo / "notes.txt").write_text("outside the plugin\n")
    assert run(repo).returncode == 0
    assert run(repo, "--check").returncode == 0
    assert version(repo) == ORIGINAL_VERSION


def test_detects_bypassed_hook_even_after_unrelated_commit(repo: Path) -> None:
    (repo / PLUGIN / "installer.py").write_text("changed\n")
    git(repo, "add", ".")
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "missed bump")
    (repo / "notes.txt").write_text("unrelated\n")
    git(repo, "add", "notes.txt")
    git(repo, "commit", "-qm", "unrelated")
    assert run(repo, "--check").returncode == 1
    assert run(repo).returncode == 0
    assert run(repo, "--check").returncode == 0


def test_commit_hook_bumps_index_and_preserves_unstaged_content(repo: Path) -> None:
    target = repo / PLUGIN / "installer.py"
    previous = ORIGINAL_VERSION
    for number in range(2):
        target.write_text(f"staged {number}\n")
        git(repo, "add", str(PLUGIN / "installer.py"))
        target.write_text("unstaged\n")
        git(repo, "commit", "-qm", "installer update")
        assert version(repo) > previous
        previous = version(repo)
        assert json.loads(git(repo, "show", f"HEAD:{MANIFEST}"))["version"] == previous
        assert git(repo, "show", f"HEAD:{PLUGIN}/installer.py") == f"staged {number}"
        assert target.read_text() == "unstaged\n"
        assert git(repo, "diff", "--cached", "--name-only") == ""
    git(repo, "restore", str(PLUGIN / "installer.py"))
    assert run(repo, "--check").returncode == 0
    assert run(repo).returncode == 0
    assert version(repo) == previous


def test_partial_manifest_is_not_overwritten_or_staged(repo: Path) -> None:
    (repo / PLUGIN / "installer.py").write_text("changed\n")
    git(repo, "add", str(PLUGIN / "installer.py"))
    manifest = repo / MANIFEST
    pending = manifest.read_text().replace("Install and verify", "Unstaged description")
    manifest.write_text(pending)
    before = git(repo, "diff", "--cached")
    result = run(repo, "--staged")
    assert result.returncode == 1
    assert "unstaged" in result.stderr
    assert manifest.read_text() == pending
    assert git(repo, "diff", "--cached") == before


def test_clock_rollback_still_increases_the_version(repo: Path) -> None:
    manifest = repo / MANIFEST
    future_version = "1.0.0+codex.20990101000000"
    manifest.write_text(manifest.read_text().replace(ORIGINAL_VERSION, future_version))
    git(repo, "add", str(MANIFEST))
    git(repo, "commit", "-qm", "future timestamp")
    (repo / PLUGIN / "installer.py").write_text("changed\n")
    git(repo, "add", str(PLUGIN / "installer.py"))
    assert run(repo, "--check", "--staged").returncode == 1
    assert run(repo, "--staged").returncode == 0
    assert version(repo) == "1.0.0+codex.20990101000001"
    assert run(repo, "--check", "--staged").returncode == 0


@pytest.mark.parametrize("bypass_hook", [False, True])
def test_merge_must_exceed_both_parent_versions(repo: Path, bypass_hook: bool) -> None:
    main_branch = git(repo, "branch", "--show-current")
    git(repo, "checkout", "-qb", "installer-branch")
    (repo / PLUGIN / "new.py").write_text("branch change\n")
    manifest = repo / MANIFEST
    branch_version = "1.0.0+codex.20990101000000"
    manifest.write_text(manifest.read_text().replace(ORIGINAL_VERSION, branch_version))
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "branch update")
    git(repo, "checkout", "-q", main_branch)
    (repo / PLUGIN / "installer.py").write_text("main change\n")
    git(repo, "add", ".")
    git(repo, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "imported change")
    options = ["-c", "core.hooksPath=/dev/null"] if bypass_hook else []
    git(repo, *options, "merge", "--no-ff", "-qm", "merge installer", "installer-branch")
    if bypass_hook:
        assert version(repo) == branch_version
        assert run(repo, "--check").returncode == 1
        assert run(repo).returncode == 0
    assert version(repo) == "1.0.0+codex.20990101000001"
    assert run(repo, "--check").returncode == 0


def test_shallow_history_fails_closed(repo: Path, tmp_path: Path) -> None:
    shallow = tmp_path / "shallow"
    git(repo, "clone", "-q", "--depth=1", repo.as_uri(), str(shallow))
    result = run(shallow, "--check")
    assert result.returncode == 1
    assert "history" in result.stderr


@pytest.mark.parametrize("invalid", ["invalid", "1.0.0+codex.20261305081939"])
def test_invalid_version_fails_without_writing(repo: Path, invalid: str) -> None:
    manifest = repo / MANIFEST
    manifest.write_text(manifest.read_text().replace(ORIGINAL_VERSION, invalid))
    assert run(repo, "--check").returncode == 1
    assert run(repo).returncode == 1
    assert version(repo) == invalid
