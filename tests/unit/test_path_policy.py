import os

import pytest
from server.core.path_policy import PathDenied, PathPolicy, same_file


@pytest.fixture
def policy(tmp_path):
    (tmp_path / "ws").mkdir()
    return PathPolicy(roots=[tmp_path / "ws"], allowed_exts={".blend", ".json"})


def test_accepts_inside_root(policy, tmp_path):
    p = policy.resolve(str(tmp_path / "ws" / "a.blend"))
    assert p == (tmp_path / "ws" / "a.blend").resolve()


def test_rejects_dotdot_escape(policy, tmp_path):
    with pytest.raises(PathDenied):
        policy.resolve(str(tmp_path / "ws" / ".." / "outside.blend"))


def test_rejects_symlink_escape(policy, tmp_path):
    outside = tmp_path / "outside.blend"
    outside.write_text("x")
    link = tmp_path / "ws" / "link.blend"
    os.symlink(outside, link)
    with pytest.raises(PathDenied):
        policy.resolve(str(link))


def test_rejects_bad_extension(policy, tmp_path):
    with pytest.raises(PathDenied):
        policy.resolve(str(tmp_path / "ws" / "evil.py"))


def test_rejects_tilde_escape(policy):
    with pytest.raises(PathDenied):
        policy.resolve("~/outside.blend")


def test_same_file_detects_case_variant_on_case_insensitive_fs(tmp_path):
    orig = tmp_path / "Scene.blend"
    orig.write_bytes(b"ORIGINAL")
    variant = tmp_path / "scene.blend"
    if not variant.exists():
        pytest.skip("filesystem is case-sensitive")
    assert str(variant.resolve()) != str(orig.resolve())
    assert same_file(variant, orig)


def test_same_file_distinguishes_real_different_files(tmp_path):
    a = tmp_path / "a.blend"
    b = tmp_path / "b.blend"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    assert not same_file(a, b)


def test_rejects_embedded_nul_as_path_denied(policy):
    with pytest.raises(PathDenied, match="unresolvable"):
        policy.resolve("/tmp/evil\0.blend")
