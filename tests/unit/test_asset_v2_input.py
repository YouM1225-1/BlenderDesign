import os
import sys
from pathlib import Path

import pytest

from acceptance.input_bundle import (
    freeze_bundle,
    measure_file,
    read_bounded,
    validate_roots,
    verify_bundle,
)
from acceptance.primitives import AcceptanceFailure


def test_freeze_survives_original_edit_and_rechecks_members(tmp_path):
    original = tmp_path / "source.blend"
    original.write_bytes(b"before")
    root = tmp_path / "frozen"
    rows = freeze_bundle(
        [{"id": "asset", "path": "asset.blend", "source": str(original)}],
        root,
        max_files=1,
        max_file_bytes=32,
        max_total_bytes=32,
    )
    original.write_bytes(b"after")
    assert verify_bundle(root, rows, max_file_bytes=32)["asset"].bytes == 6
    (root / "extra").write_bytes(b"unexpected")
    with pytest.raises(AcceptanceFailure, match="file set"):
        verify_bundle(root, rows, max_file_bytes=32)


@pytest.mark.parametrize("replacement", [b"target", b"changed!"])
def test_verify_rejects_frozen_member_drift(tmp_path, replacement):
    original = tmp_path / "source.blend"
    original.write_bytes(b"before")
    root = tmp_path / "frozen"
    rows = freeze_bundle(
        [{"id": "asset", "path": "asset.blend", "source": str(original)}],
        root,
        max_files=1,
        max_file_bytes=32,
        max_total_bytes=32,
    )
    assert verify_bundle(root, rows, max_file_bytes=32)["asset"].bytes == 6

    frozen = root / "asset.blend"
    os.chmod(frozen, 0o600)
    frozen.write_bytes(replacement)
    with pytest.raises(AcceptanceFailure) as caught:
        verify_bundle(root, rows, max_file_bytes=32)

    assert caught.value.code == "hash_mismatch"
    assert original.read_bytes() == b"before"


@pytest.mark.parametrize("kind", ["symlink", "fifo", "parent_link", "too_large"])
def test_streaming_reader_rejects_unsafe_paths(tmp_path, kind):
    real = tmp_path / "real"
    real.mkdir()
    path = real / "asset"
    path.write_bytes(b"1234")
    limit = 4
    if kind == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path)
    elif kind == "parent_link":
        link = tmp_path / "folder"
        link.symlink_to(real, target_is_directory=True)
        path = link / "asset"
    else:
        limit = 3
    with pytest.raises((AcceptanceFailure, OSError)):
        measure_file(path, limit, file_id="asset")


def test_mid_read_change_does_not_return_a_digest(tmp_path, monkeypatch):
    path = tmp_path / "asset"
    path.write_bytes(b"old")
    original = os.read
    changed = False

    def race(fd, size):
        nonlocal changed
        data = original(fd, size)
        if data and not changed:
            changed = True
            path.write_bytes(b"new")
        return data

    monkeypatch.setattr(os, "read", race)
    with pytest.raises(AcceptanceFailure, match="changed"):
        measure_file(path, 32, file_id="asset")


@pytest.mark.parametrize("budget", [True, False, 0, -1, 1.0])
@pytest.mark.parametrize("name", ["max_files", "max_file_bytes", "max_total_bytes"])
def test_freeze_rejects_invalid_budgets_before_creating_root(tmp_path, name, budget):
    source = tmp_path / "source"
    source.write_bytes(b"x")
    root = tmp_path / "frozen"
    budgets = {"max_files": 1, "max_file_bytes": 1, "max_total_bytes": 1}
    budgets[name] = budget

    with pytest.raises(AcceptanceFailure) as caught:
        freeze_bundle(
            [{"id": "asset", "path": "asset", "source": str(source)}],
            root,
            **budgets,
        )

    assert caught.value.code == "contract_invalid"
    assert not root.exists()


def test_zero_remaining_total_budget_still_allows_empty_file(tmp_path):
    first = tmp_path / "first"
    empty = tmp_path / "empty"
    first.write_bytes(b"x")
    empty.write_bytes(b"")
    sources = [
        {"id": "first", "path": "first", "source": str(first)},
        {"id": "second", "path": "empty", "source": str(empty)},
    ]

    rows = freeze_bundle(
        sources,
        tmp_path / "valid",
        max_files=2,
        max_file_bytes=1,
        max_total_bytes=1,
    )
    assert [row["bytes"] for row in rows] == [1, 0]

    empty.write_bytes(b"y")
    with pytest.raises(AcceptanceFailure):
        freeze_bundle(
            sources,
            tmp_path / "too-large",
            max_files=2,
            max_file_bytes=1,
            max_total_bytes=1,
        )


def test_bounded_read_accepts_empty_file_at_zero_limit(tmp_path):
    path = tmp_path / "empty"
    path.write_bytes(b"")
    assert read_bounded(path, 0) == b""


@pytest.mark.parametrize("limit", [True, False, -1])
def test_bounded_read_rejects_invalid_limit(tmp_path, limit):
    path = tmp_path / "empty"
    path.write_bytes(b"")
    with pytest.raises(AcceptanceFailure) as caught:
        read_bounded(path, limit)
    assert caught.value.code == "contract_invalid"


def test_validate_roots_rejects_parent_spelling_before_repository_check(tmp_path):
    sibling = tmp_path / "sibling"
    repo = tmp_path / "repo"
    source = repo / "source"
    evidence = tmp_path / "evidence"
    scratch = tmp_path / "scratch"
    for path in (sibling, source, evidence, scratch):
        path.mkdir(parents=True)

    with pytest.raises(AcceptanceFailure) as caught:
        validate_roots(sibling / ".." / "repo" / "source", evidence, scratch, repo)
    assert caught.value.code == "contract_invalid"


def test_validate_roots_rejects_parent_spelling_before_overlap_check(tmp_path):
    sibling = tmp_path / "sibling"
    shared = tmp_path / "shared"
    scratch = tmp_path / "scratch"
    repo = tmp_path / "repo"
    for path in (sibling, shared, scratch, repo):
        path.mkdir()

    with pytest.raises(AcceptanceFailure) as caught:
        validate_roots(shared, sibling / ".." / "shared", scratch, repo)
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("case", ["inside_repo", "overlap"])
def test_validate_roots_rejects_direct_repository_and_root_overlap(tmp_path, case):
    repo = tmp_path / "repo"
    source = tmp_path / "source"
    evidence = tmp_path / "evidence"
    scratch = tmp_path / "scratch"
    for path in (repo, source, evidence, scratch):
        path.mkdir()
    if case == "inside_repo":
        source = repo / "source"
        source.mkdir()
    else:
        evidence = source / "evidence"
        evidence.mkdir()

    with pytest.raises(AcceptanceFailure) as caught:
        validate_roots(source, evidence, scratch, repo)
    assert caught.value.code == "contract_invalid"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS /tmp is a symlink alias")
def test_validate_roots_rejects_tmp_symlink_alias(tmp_path):
    evidence = tmp_path / "evidence"
    scratch = tmp_path / "scratch"
    repo = tmp_path / "repo"
    for path in (evidence, scratch, repo):
        path.mkdir()
    with pytest.raises((AcceptanceFailure, OSError)):
        validate_roots(Path("/tmp"), evidence, scratch, repo)


def test_freeze_fails_on_zero_progress_write_and_retains_attempt(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.write_bytes(b"content")
    root = tmp_path / "frozen"
    original_write = os.write
    first_write = True

    def stalled_write(fd, data):
        nonlocal first_write
        if first_write:
            first_write = False
            return 0
        return original_write(fd, data)

    monkeypatch.setattr(os, "write", stalled_write)
    rows = None
    with pytest.raises(AcceptanceFailure, match="progress"):
        rows = freeze_bundle(
            [{"id": "asset", "path": "asset", "source": str(source)}],
            root,
            max_files=1,
            max_file_bytes=32,
            max_total_bytes=32,
        )

    assert rows is None
    assert source.read_bytes() == b"content"
    assert root.is_dir()
    assert (root / "asset").exists()


def test_verify_bundle_does_not_suppress_traversal_errors(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.write_bytes(b"content")
    root = tmp_path / "frozen"
    rows = freeze_bundle(
        [{"id": "asset", "path": "asset", "source": str(source)}],
        root,
        max_files=1,
        max_file_bytes=32,
        max_total_bytes=32,
    )
    extra = root / "extra"
    extra.mkdir()
    original_scandir = os.scandir

    def failing_scandir(path):
        if Path(path) == extra:
            raise PermissionError("synthetic traversal failure")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", failing_scandir)
    with pytest.raises(PermissionError, match="synthetic traversal failure"):
        verify_bundle(root, rows, max_file_bytes=32)


@pytest.mark.parametrize(("name", "alias"), [("Input", "input"), ("é", "e\u0301")])
@pytest.mark.parametrize("relation", ["equal", "child", "parent", "prospective_equal"])
def test_validate_roots_rejects_physical_alias_overlap(tmp_path, name, alias, relation):
    root, other = tmp_path / name, tmp_path / alias
    root.mkdir()
    if not other.exists() or not root.samefile(other):
        pytest.skip("test filesystem does not support this directory alias")
    repo, scratch = tmp_path / "repo", tmp_path / "scratch"
    repo.mkdir()
    scratch.mkdir()
    if relation == "prospective_equal":
        left, right = root / "new", other / "new"
    elif relation == "equal":
        left, right = root, other
    else:
        left, right = root, other / "child"
        right.mkdir()
        if relation == "parent":
            left, right = right, left
    with pytest.raises(AcceptanceFailure, match="overlap") as caught:
        validate_roots(left, right, scratch, repo)
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize(("name", "alias"), [("Repo", "repo"), ("é", "e\u0301")])
@pytest.mark.parametrize("exists", [False, True])
def test_validate_roots_rejects_physical_repository_alias(tmp_path, name, alias, exists):
    repo, other = tmp_path / name, tmp_path / alias
    repo.mkdir()
    if not other.exists() or not repo.samefile(other):
        pytest.skip("test filesystem does not support this directory alias")
    source, scratch = tmp_path / "source", tmp_path / "scratch"
    source.mkdir()
    scratch.mkdir()
    evidence = other / "evidence"
    if exists:
        evidence.mkdir()
    with pytest.raises(AcceptanceFailure, match="inside repository") as caught:
        validate_roots(source, evidence, scratch, repo)
    assert caught.value.code == "contract_invalid"


@pytest.mark.parametrize("exists", [False, True])
def test_validate_roots_accepts_disjoint_nfd_and_prospective_roots(tmp_path, exists):
    repo = tmp_path / "repo"
    repo.mkdir()
    roots = [tmp_path / name for name in ("e\u0301-source", "evidence", "scratch")]
    if exists:
        for root in roots:
            root.mkdir()
    validate_roots(*roots, repo)
    assert all(root.exists() == exists for root in roots)
