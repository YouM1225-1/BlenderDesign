from __future__ import annotations

import json
import os
import sys
import time
import tomllib
from dataclasses import replace
from pathlib import Path, PurePath

import pytest


ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "plugins/blender-mcp-installer/scripts"))

from blender_mcp_installer import codex_adapter  # noqa: E402
from blender_mcp_installer.codex_adapter import (  # noqa: E402
    CodexRollbackContext,
    ManagedProfile,
    RollbackState,
    desired_codex_values,
    rollback_codex,
    stage_codex_config,
    verify_codex_effective,
    verify_codex_toml,
)
from blender_mcp_installer.filesystem import (  # noqa: E402
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    StagedFile,
    TargetRef,
    capture_file,
    create_deterministic_stage,
    forward_file,
)
from blender_mcp_installer.model import FileImage  # noqa: E402


TOOLS = ("one", "two", "execute_blender_code")
SECRET = "TASK4_SECRET_SENTINEL_DO_NOT_LEAK"


class CrashAt:
    def __init__(self, point: str):
        self.point = point
        self.hits: list[str] = []

    def hit(self, point: str) -> None:
        self.hits.append(point)
        if point == self.point:
            raise RuntimeError("injected crash")


class JournalCrash:
    def __init__(self, state: RollbackState):
        self.state = state
        self.persisted: list = []

    def __call__(self, result) -> None:
        if result.state is self.state:
            raise RuntimeError("journal crash")
        self.persisted.append(result)


def _profile(root: Path) -> ManagedProfile:
    resources = root / "blender/resources"
    return ManagedProfile(
        home=root / "home",
        blender_user_resources=resources,
        blender_user_config=resources / "config",
        blender_user_extensions=resources / "extensions",
        blender_path=root / "Applications/Blender.app/Contents/MacOS/Blender",
    )


def _desired(root: Path):
    return desired_codex_values(root / "runtime/bin/blender-mcp-managed", _profile(root), TOOLS)


def _open_root(path: Path) -> SafeRoot:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return SafeRoot.open(path, os.getuid(), path)


def _write_private(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    path.chmod(0o600)


def _read_fd(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    result = b""
    while chunk := os.read(fd, 1024 * 1024):
        result += chunk
    return result


def _stage(root: SafeRoot, basename: str = "codex.stage") -> StagedFile:
    created = create_deterministic_stage(root, basename, FileImage.absent(), NoOpFaultInjector())
    assert isinstance(created, StagedFile)
    return created


def _stage_config(
    root: SafeRoot,
    desired,
    raw: bytes | None,
    basename: str = "codex.stage",
):
    config = root.path / "config.toml"
    if raw is not None:
        _write_private(config, raw)
    current = capture_file(root, PurePath("config.toml"))
    stage = _stage(root, basename)
    live_fd = None if raw is None else os.open(config, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        change = stage_codex_config(live_fd, current, desired, Path(sys.executable), stage)
    finally:
        if live_fd is not None:
            os.close(live_fd)
    return TargetRef(root, PurePath("config.toml")), current, change


def _parsed(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text())


def _assert_owned(parsed: dict[str, object], desired) -> None:
    server = parsed["mcp_servers"]["blender"]
    assert server["command"] == desired.command
    assert server["args"] == []
    assert server["omit_tools_from"] == []
    assert server["startup_timeout_sec"] == 20.0
    assert server["tool_timeout_sec"] == 60.0
    assert server["default_tools_approval_mode"] == "approve"
    assert server["enabled_tools"] == list(TOOLS)
    assert all(server["env"].get(key) == value for key, value in desired.env.items())
    assert "disabled_tools" not in server
    assert "tools" not in server
    assert "mcp__blender" in parsed["features"]["code_mode"]["direct_only_tool_namespaces"]


def _installed(
    root: SafeRoot,
    desired,
    pre_raw: bytes | None,
):
    target, pre, change = _stage_config(root, desired, pre_raw)
    recovery = StagedFile(root, PurePath("codex.recovery"), pre)
    while (
        forward_file(target, pre, change.stage, recovery, NoOpFaultInjector()).value != "completed"
    ):
        pass
    return target, pre, change, recovery


def _rollback_context(
    root: SafeRoot,
    target: TargetRef,
    installer_post: FileImage,
    journal: list,
    persisted=None,
) -> CodexRollbackContext:
    state = None if persisted is None else persisted.state
    intended = None if persisted is None else persisted.rollback_intended
    displaced = None if persisted is None else persisted.rollback_displaced
    return CodexRollbackContext(
        target=target,
        forward_stage=StagedFile(root, PurePath("codex.stage"), installer_post),
        rollback_stage=StagedFile(
            root,
            PurePath("codex.rollback.stage"),
            FileImage.absent() if intended is None else intended,
        ),
        state=state,
        rollback_intended=intended,
        rollback_displaced=displaced,
        journal=journal.append,
    )


def test_desired_values_are_closed_and_ignore_hostile_ambient(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", "/hostile/home")
    monkeypatch.setenv("BLENDER_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("BLENDER_MCP_PORT", "1")
    monkeypatch.setenv("PYTHONPATH", f"/{SECRET}")

    desired = _desired(tmp_path)

    assert desired.command == str(tmp_path / "runtime/bin/blender-mcp-managed")
    assert desired.args == ()
    assert desired.omit_tools_from == ()
    assert desired.startup_timeout_sec == 20.0
    assert desired.tool_timeout_sec == 60.0
    assert desired.default_tools_approval_mode == "approve"
    assert desired.enabled_tools == TOOLS
    assert dict(desired.env) == {
        "HOME": str(tmp_path / "home"),
        "BLENDER_USER_RESOURCES": str(tmp_path / "blender/resources"),
        "BLENDER_USER_CONFIG": str(tmp_path / "blender/resources/config"),
        "BLENDER_USER_EXTENSIONS": str(tmp_path / "blender/resources/extensions"),
        "BLENDER_PATH": str(tmp_path / "Applications/Blender.app/Contents/MacOS/Blender"),
        "BLENDER_MCP_HOST": "localhost",
        "BLENDER_MCP_PORT": "9876",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
    assert desired.direct_only_namespace == "mcp__blender"


@pytest.mark.parametrize(
    "bad_launcher,bad_tools",
    [(Path("relative"), TOOLS), (Path("/absolute"), ("one", "one")), (Path("/absolute"), ())],
)
def test_desired_values_reject_invalid_identity(
    tmp_path: Path, bad_launcher: Path, bad_tools: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError):
        desired_codex_values(bad_launcher, _profile(tmp_path), bad_tools)


def test_stage_reads_retained_fd_preserves_comments_and_creates_no_preimage(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    original = (
        f"# top {SECRET}\n"
        'model = "gpt-5" # keep model\n\n'
        "[foreign]\n"
        'value = "keep" # keep foreign\n\n'
        "[mcp_servers.blender]\n"
        'command = "/old" # command comment\n'
        'args = ["old"]\n'
        'disabled_tools = ["old"]\n'
        'tools = { one = { approval_mode = "prompt" } }\n'
        'foreign_key = "keep" # server comment\n\n'
        "[mcp_servers.blender.env]\n"
        'TOKEN = "secret" # env comment\n'
        'BLENDER_MCP_HOST = "hostile"\n\n'
        "[features.code_mode]\n"
        'direct_only_tool_namespaces = ["mcp__other"] # namespace comment\n'
    ).encode()
    config = root.path / "config.toml"
    _write_private(config, original)
    current = capture_file(root, PurePath("config.toml"))
    live_fd = os.open(config, os.O_RDONLY | os.O_NOFOLLOW)
    os.rename(config, root.path / "renamed-away.toml")
    _write_private(config, b'[mcp_servers.blender]\ncommand = "/hostile-path"\n')
    stage = _stage(root)
    try:
        change = stage_codex_config(live_fd, current, desired, Path(sys.executable), stage)
    finally:
        os.close(live_fd)

    merged = change.stage.path.read_bytes()
    parsed = tomllib.loads(merged.decode())
    _assert_owned(parsed, desired)
    assert parsed["foreign"] == {"value": "keep"}
    assert parsed["mcp_servers"]["blender"]["foreign_key"] == "keep"
    assert parsed["mcp_servers"]["blender"]["env"]["TOKEN"] == "secret"
    assert parsed["features"]["code_mode"]["direct_only_tool_namespaces"] == [
        "mcp__other",
        "mcp__blender",
    ]
    assert b"# top" in merged
    assert b"# keep model" in merged
    assert b"# keep foreign" in merged
    assert b"# server comment" in merged
    assert b"# env comment" in merged
    assert b"# namespace comment" in merged
    assert change.post == change.stage.image == change.stage.capture()
    assert change.post.mode == 0o600
    assert change.changed is True
    assert sorted(path.name for path in root.path.iterdir()) == [
        "codex.stage",
        "config.toml",
        "renamed-away.toml",
    ]
    assert not any(
        "recovery" in path.name or "request" in path.name for path in root.path.iterdir()
    )
    verify_codex_toml(merged, desired)
    root.close()


def test_stage_absent_config_and_exact_second_merge(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    _, pre, first = _stage_config(root, desired, None)
    assert pre == FileImage.absent()
    _assert_owned(_parsed(first.stage.path), desired)
    first_raw = first.stage.path.read_bytes()

    second_root = _open_root(tmp_path / "second")
    _write_private(second_root.path / "config.toml", first_raw)
    _, _, second = _stage_config(second_root, desired, first_raw)
    assert second.stage.path.read_bytes() == first_raw
    assert second.changed is False
    root.close()
    second_root.close()


def test_parsed_verification_rejects_duplicate_managed_namespace(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    _, _, change = _stage_config(root, desired, None)
    raw = change.stage.path.read_bytes()
    owned = b'direct_only_tool_namespaces = ["mcp__blender"]'
    assert owned in raw

    with pytest.raises(InstallerError, match="Codex managed configuration mismatch"):
        verify_codex_toml(
            raw.replace(
                owned,
                b'direct_only_tool_namespaces = ["mcp__blender", "mcp__blender"]',
            ),
            desired,
        )
    root.close()


@pytest.mark.parametrize(
    "raw",
    [b"\xff", b"[mcp_servers.blender\n", b"mcp_servers = 1\n"],
)
def test_parse_and_helper_errors_are_fixed_and_redacted(tmp_path: Path, raw: bytes) -> None:
    desired = _desired(tmp_path)
    with pytest.raises(InstallerError) as caught:
        verify_codex_toml(raw + SECRET.encode(), desired)
    assert SECRET not in str(caught.value)

    root = _open_root(tmp_path / "codex")
    config = root.path / "config.toml"
    _write_private(config, raw + SECRET.encode())
    current = capture_file(root, PurePath("config.toml"))
    live_fd = os.open(config, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with pytest.raises(InstallerError) as staged:
            stage_codex_config(live_fd, current, desired, Path(sys.executable), _stage(root))
    finally:
        os.close(live_fd)
    assert str(staged.value) == "Codex configuration merge failed"
    assert SECRET not in str(staged.value)
    assert not any("request" in path.name for path in root.path.iterdir())
    root.close()


def test_stage_rejects_fd_image_mismatch_before_helper(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    config = root.path / "config.toml"
    _write_private(config, b'model = "one"\n')
    current = capture_file(root, PurePath("config.toml"))
    fd = os.open(config, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with pytest.raises(InstallerError, match="Codex configuration input changed"):
            stage_codex_config(
                fd, replace(current, sha256="a" * 64), desired, Path(sys.executable), _stage(root)
            )
    finally:
        os.close(fd)
    root.close()


def test_fd_image_rejects_mutation_during_hash(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "value.toml"
    _write_private(path, b'model = "before"\n')
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    original_hash = codex_adapter._hash_fd

    def mutate(opened: int) -> str:
        digest = original_hash(opened)
        os.ftruncate(opened, os.fstat(opened).st_size + 1)
        return digest

    monkeypatch.setattr(codex_adapter, "_hash_fd", mutate)
    try:
        with pytest.raises(InstallerError, match="Codex configuration input changed"):
            codex_adapter._fd_image(fd)
    finally:
        os.close(fd)


def test_stage_revalidates_retained_live_fd_after_helper(monkeypatch, tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    config = root.path / "config.toml"
    _write_private(config, b'model = "before"\n')
    current = capture_file(root, PurePath("config.toml"))
    live_fd = os.open(config, os.O_RDONLY | os.O_NOFOLLOW)
    original = codex_adapter._run_helper

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        _write_private(config, b'model = "changed-during-helper"\n')
        return result

    monkeypatch.setattr(codex_adapter, "_run_helper", mutate)
    try:
        with pytest.raises(InstallerError, match="Codex configuration input changed"):
            stage_codex_config(live_fd, current, desired, Path(sys.executable), _stage(root))
    finally:
        os.close(live_fd)
    root.close()


def test_stage_binds_retained_fd_to_published_path(monkeypatch, tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    stage = _stage(root)
    original = codex_adapter._invoke_helper

    def replace_stage(anchor, request, runtime_python, inherited):
        output = original(anchor, request, runtime_python, inherited)
        stage_fd = request["stage_fd"]
        os.lseek(stage_fd, 0, os.SEEK_SET)
        raw = _read_fd(stage_fd)
        os.rename(anchor.path, root.path / "displaced-stage")
        _write_private(anchor.path, raw)
        return output

    monkeypatch.setattr(codex_adapter, "_invoke_helper", replace_stage)
    with pytest.raises(InstallerError, match="Codex stage changed"):
        stage_codex_config(None, FileImage.absent(), desired, Path(sys.executable), stage)
    assert (root.path / "displaced-stage").exists()
    assert stage.path.exists()
    root.close()


def _effective_launcher(path: Path, payload: dict[str, object], marker: Path) -> None:
    source = (
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(marker)!r}).write_text(json.dumps(sys.argv[1:]))\n"
        f"print(json.dumps({payload!r}, sort_keys=True))\n"
    )
    path.write_text(source)
    path.chmod(0o700)


def test_effective_verification_runs_explicit_command_after_publication(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    target, pre, change = _stage_config(root, desired, b'model = "keep"\n')
    marker = tmp_path / "called"
    codex = tmp_path / "fake-codex"
    payload = {
        "command": desired.command,
        "args": [],
        "env": {**dict(desired.env), "FOREIGN": "keep"},
        "enabled_tools": list(desired.enabled_tools),
        "startup_timeout_sec": 20.0,
        "tool_timeout_sec": 60.0,
        "enabled": True,
    }
    _effective_launcher(codex, payload, marker)
    assert not marker.exists()
    recovery = TargetRef(root, PurePath("codex.recovery"))
    while (
        forward_file(target, pre, change.stage, recovery, NoOpFaultInjector()).value != "completed"
    ):
        pass

    state = verify_codex_effective(codex, desired, {"CODEX_HOME": str(root.path)})

    assert json.loads(marker.read_text()) == ["mcp", "get", "blender", "--json"]
    assert state.command == desired.command
    assert state.args == ()
    assert state.enabled_tools == desired.enabled_tools
    assert dict(state.env)["FOREIGN"] == "keep"
    root.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("command", "/foreign"),
        ("args", ["foreign"]),
        ("enabled_tools", ["one"]),
        ("startup_timeout_sec", 21.0),
        ("tool_timeout_sec", 61.0),
        ("env", {"HOME": "/foreign"}),
    ],
)
def test_effective_verification_rejects_changed_subset(
    tmp_path: Path, field: str, value: object
) -> None:
    desired = _desired(tmp_path)
    payload = {
        "command": desired.command,
        "args": [],
        "env": dict(desired.env),
        "enabled_tools": list(desired.enabled_tools),
        "startup_timeout_sec": 20.0,
        "tool_timeout_sec": 60.0,
    }
    payload[field] = value
    codex = tmp_path / "codex"
    _effective_launcher(codex, payload, tmp_path / "called")
    with pytest.raises(InstallerError, match="effective Codex configuration mismatch"):
        verify_codex_effective(codex, desired, {})


def test_effective_json_error_never_echoes_output(tmp_path: Path) -> None:
    desired = _desired(tmp_path)
    codex = tmp_path / "codex"
    _effective_launcher(codex, {SECRET: float("nan")}, tmp_path / "called")
    with pytest.raises(InstallerError) as caught:
        verify_codex_effective(codex, desired, {})
    assert SECRET not in str(caught.value)


def _special_codex(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n{body}\n")
    path.chmod(0o700)


@pytest.mark.parametrize(
    "body",
    [
        'import os\nos.write(1, b"x" * (17 * 1024 * 1024))',
        'import os\nwhile True: os.write(2, b"x" * 65536)',
    ],
)
def test_effective_verification_terminates_over_limit_output(tmp_path: Path, body: str) -> None:
    desired = _desired(tmp_path)
    codex = tmp_path / "codex"
    _special_codex(codex, body)
    started = time.monotonic()

    with pytest.raises(InstallerError) as caught:
        verify_codex_effective(codex, desired, {})

    assert time.monotonic() - started < 5
    assert str(caught.value) == "effective Codex verification failed"
    assert SECRET not in str(caught.value)


def test_effective_verification_has_fixed_timeout(tmp_path: Path) -> None:
    desired = _desired(tmp_path)
    codex = tmp_path / "codex"
    _special_codex(codex, "import time\ntime.sleep(60)")
    started = time.monotonic()

    with pytest.raises(InstallerError) as caught:
        verify_codex_effective(codex, desired, {})

    assert time.monotonic() - started < 5
    assert str(caught.value) == "effective Codex verification failed"


def test_exact_rollback_uses_native_transaction_and_restores_preimage(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    pre_raw = b'# original\nmodel = "keep"\n'
    target, pre, change, recovery = _installed(root, desired, pre_raw)
    journal: list = []
    context = _rollback_context(root, target, change.post, journal)

    result = rollback_codex(
        context,
        recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.restored is True
    assert target.path.read_bytes() == pre_raw
    assert capture_file(root, PurePath("codex.recovery")) == FileImage.absent()
    assert capture_file(root, PurePath("codex.stage")) == FileImage.absent()
    assert capture_file(root, PurePath("codex.rollback.stage")) == FileImage.absent()
    assert journal[-1].state is RollbackState.RESTORED
    root.close()


def test_missing_preimage_restores_config_to_absent(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    target, pre, change, recovery = _installed(root, desired, None)
    assert pre == FileImage.absent()

    result = rollback_codex(
        _rollback_context(root, target, change.post, []),
        recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.restored is True
    assert capture_file(root, PurePath("config.toml")) == FileImage.absent()
    assert capture_file(root, PurePath("codex.recovery")) == FileImage.absent()
    root.close()


def test_missing_preimage_semantic_rollback_preserves_foreign_addition(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    target, _, change, recovery = _installed(root, desired, None)
    with target.path.open("a") as stream:
        stream.write('\n[foreign_after]\nvalue = "keep"\n')
    target.path.chmod(0o600)

    result = rollback_codex(
        _rollback_context(root, target, change.post, []),
        recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.state is RollbackState.C4
    assert _parsed(target.path) == {"foreign_after": {"value": "keep"}}
    assert not recovery.path.exists()
    root.close()


def test_current_original_bytes_are_durably_already_restored(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    pre_raw = b'# original\nmodel = "before"\n'
    target, _, change, recovery = _installed(root, desired, pre_raw)
    target.path.unlink()
    os.link(recovery.path, target.path)
    journal: list = []

    result = rollback_codex(
        _rollback_context(root, target, change.post, journal),
        recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.state is RollbackState.C4
    assert target.path.read_bytes() == pre_raw
    assert [item.state for item in journal] == [
        RollbackState.C1,
        RollbackState.C2,
        RollbackState.C3,
        RollbackState.C4,
    ]
    assert not recovery.path.exists()
    root.close()


def _semantic_fixture(tmp_path: Path):
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    pre_raw = (
        f"# {SECRET}\n"
        'model = "before"\n\n'
        "[mcp_servers.blender]\n"
        'command = "/before" # restore this comment\n'
        'args = ["before"]\n'
        "startup_timeout_sec = 9.0\n"
        'foreign_pre = "keep-pre"\n\n'
        "[mcp_servers.blender.env]\n"
        'HOME = "/before/home"\n'
        'FOREIGN_PRE = "keep-pre"\n\n'
        "[features.code_mode]\n"
        'direct_only_tool_namespaces = ["mcp__pre"]\n'
    ).encode()
    target, _, change, recovery = _installed(root, desired, pre_raw)
    current = target.path.read_text()
    current += (
        '\n[foreign_after]\nvalue = "keep-after" # after comment\n'
        '\n[mcp_servers.blender.foreign_table]\nvalue = "keep-table"\n'
    )
    current = current.replace(
        'PYTHONSAFEPATH = "1"', 'PYTHONSAFEPATH = "1"\nFOREIGN_AFTER = "keep-env"'
    )
    current = current.replace(
        '"mcp__pre", "mcp__blender"',
        '"mcp__pre", "mcp__blender", "mcp__after"',
    )
    _write_private(target.path, current.encode())
    return root, desired, pre_raw, target, change, recovery


def test_semantic_rollback_preserves_foreign_additions_and_pre_nodes(tmp_path: Path) -> None:
    root, desired, _, target, change, recovery = _semantic_fixture(tmp_path)
    journal: list = []

    result = rollback_codex(
        _rollback_context(root, target, change.post, journal),
        recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    raw = target.path.read_bytes()
    parsed = tomllib.loads(raw.decode())
    server = parsed["mcp_servers"]["blender"]
    assert server["command"] == "/before"
    assert server["args"] == ["before"]
    assert server["startup_timeout_sec"] == 9.0
    assert "omit_tools_from" not in server
    assert "tool_timeout_sec" not in server
    assert "default_tools_approval_mode" not in server
    assert "enabled_tools" not in server
    assert server["foreign_pre"] == "keep-pre"
    assert server["foreign_table"] == {"value": "keep-table"}
    assert server["env"] == {
        "HOME": "/before/home",
        "FOREIGN_PRE": "keep-pre",
        "FOREIGN_AFTER": "keep-env",
    }
    assert parsed["foreign_after"] == {"value": "keep-after"}
    assert parsed["features"]["code_mode"]["direct_only_tool_namespaces"] == [
        "mcp__pre",
        "mcp__after",
    ]
    assert b"# restore this comment" in raw
    assert b"# after comment" in raw
    assert result.state is RollbackState.C4
    assert [item.state for item in journal] == [
        RollbackState.C1,
        RollbackState.C2,
        RollbackState.C3,
        RollbackState.C4,
    ]
    assert not recovery.path.exists()
    assert not (root.path / "codex.rollback.stage").exists()
    root.close()


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        ("command = ", 'command = "/foreign" # '),
        ('HOME = "', 'HOME = "/foreign'),
        ('BLENDER_MCP_HOST = "localhost"', 'BLENDER_MCP_HOST = "foreign"'),
        ('BLENDER_MCP_PORT = "9876"', 'BLENDER_MCP_PORT = "9999"'),
        ("enabled_tools = [", 'enabled_tools = ["foreign", '),
        ('default_tools_approval_mode = "approve"', 'default_tools_approval_mode = "prompt"'),
    ],
)
def test_semantic_rollback_conflicts_on_changed_owned_value(
    tmp_path: Path, needle: str, replacement: str
) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    target, _, change, recovery = _installed(root, desired, b'model = "before"\n')
    current = target.path.read_text()
    assert needle in current
    _write_private(target.path, current.replace(needle, replacement, 1).encode())
    before = {path.name: path.read_bytes() for path in root.path.iterdir() if path.is_file()}

    with pytest.raises(InstallerError, match="Codex managed key conflict") as caught:
        rollback_codex(
            _rollback_context(root, target, change.post, []),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            NoOpFaultInjector(),
        )

    assert SECRET not in str(caught.value)
    assert {
        path.name: path.read_bytes() for path in root.path.iterdir() if path.is_file()
    } == before
    assert not (root.path / "codex.rollback.stage").exists()
    root.close()


@pytest.mark.parametrize(
    "point",
    [
        "after_codex_semantic_stage_fsync",
        "after_codex_semantic_swap",
        "after_codex_semantic_receipt",
        "after_codex_semantic_displaced_cleanup",
        "after_codex_semantic_recovery_cleanup",
    ],
)
def test_every_semantic_crash_state_retries_in_fresh_process(tmp_path: Path, point: str) -> None:
    root, _, _, target, change, recovery = _semantic_fixture(tmp_path)
    journal: list = []
    fault = CrashAt(point)

    with pytest.raises(RuntimeError, match="injected crash"):
        rollback_codex(
            _rollback_context(root, target, change.post, journal),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            fault,
        )
    assert point in fault.hits
    persisted = journal[-1] if journal else None
    serialized = [] if persisted is None else json.loads(json.dumps(persisted.to_dict()))
    if persisted is not None:
        persisted = type(persisted).from_dict(serialized)

    root.close()
    reopened = _open_root(tmp_path / "codex")
    fresh_target = TargetRef(reopened, PurePath("config.toml"))
    fresh_recovery = StagedFile(reopened, PurePath("codex.recovery"), recovery.image)
    fresh_journal: list = []
    result = rollback_codex(
        _rollback_context(reopened, fresh_target, change.post, fresh_journal, persisted),
        fresh_recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.state is RollbackState.C4
    assert not fresh_recovery.path.exists()
    assert not (reopened.path / "codex.rollback.stage").exists()
    assert _parsed(fresh_target.path)["mcp_servers"]["blender"]["command"] == "/before"
    receipt_text = json.dumps([item.to_dict() for item in journal + fresh_journal])
    assert SECRET not in receipt_text
    unexpected = [
        path
        for path in reopened.path.iterdir()
        if path.name not in {"config.toml"} and path.is_file()
    ]
    assert unexpected == []
    reopened.close()


@pytest.mark.parametrize(
    "point",
    [
        "after_codex_semantic_stage_fsync",
        "after_codex_semantic_swap",
        "after_codex_semantic_receipt",
        "after_codex_semantic_displaced_cleanup",
        "after_codex_semantic_recovery_cleanup",
    ],
)
def test_absent_preimage_semantic_c0_c4_retries_in_fresh_process(
    tmp_path: Path, point: str
) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    target, pre, change, recovery = _installed(root, desired, None)
    assert pre == recovery.image == FileImage.absent()
    with target.path.open("a") as stream:
        stream.write('\n[foreign_after]\nvalue = "keep"\n')
    target.path.chmod(0o600)
    journal: list = []

    with pytest.raises(RuntimeError, match="injected crash"):
        rollback_codex(
            _rollback_context(root, target, change.post, journal),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            CrashAt(point),
        )
    persisted = journal[-1] if journal else None
    if persisted is not None:
        persisted = type(persisted).from_dict(json.loads(json.dumps(persisted.to_dict())))

    root.close()
    reopened = _open_root(tmp_path / "codex")
    fresh_target = TargetRef(reopened, PurePath("config.toml"))
    result = rollback_codex(
        _rollback_context(reopened, fresh_target, change.post, [], persisted),
        StagedFile(reopened, PurePath("codex.recovery"), FileImage.absent()),
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.state is RollbackState.C4
    assert _parsed(fresh_target.path) == {"foreign_after": {"value": "keep"}}
    assert not (reopened.path / "codex.recovery").exists()
    assert not (reopened.path / "codex.rollback.stage").exists()
    reopened.close()


def test_unlisted_semantic_state_conflicts_without_deletion(tmp_path: Path) -> None:
    root, _, _, target, change, recovery = _semantic_fixture(tmp_path)
    journal: list = []
    with pytest.raises(RuntimeError):
        rollback_codex(
            _rollback_context(root, target, change.post, journal),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            CrashAt("after_codex_semantic_stage_fsync"),
        )
    rollback_stage = root.path / "codex.rollback.stage"
    _write_private(rollback_stage, b'foreign = "changed"\n')
    before = {path.name: path.read_bytes() for path in root.path.iterdir() if path.is_file()}

    with pytest.raises(InstallerError, match="Codex rollback state conflict"):
        rollback_codex(
            _rollback_context(root, target, change.post, [], journal[-1]),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            NoOpFaultInjector(),
        )

    assert {
        path.name: path.read_bytes() for path in root.path.iterdir() if path.is_file()
    } == before
    root.close()


def test_semantic_swap_rechecks_images_at_transition(monkeypatch, tmp_path: Path) -> None:
    root, _, _, target, change, recovery = _semantic_fixture(tmp_path)
    journal: list = []
    with pytest.raises(RuntimeError, match="injected crash"):
        rollback_codex(
            _rollback_context(root, target, change.post, journal),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            CrashAt("after_codex_semantic_stage_fsync"),
        )
    stage_before = (root.path / "codex.rollback.stage").read_bytes()
    recovery_before = recovery.path.read_bytes()
    foreign = b'foreign = "changed-at-transition"\n'
    original = codex_adapter.conditional_swap_file

    def mutate(left, expected_left, right, expected_right, guards, fault):
        _write_private(left.path, foreign)
        return original(left, expected_left, right, expected_right, guards, fault)

    monkeypatch.setattr(codex_adapter, "conditional_swap_file", mutate)
    with pytest.raises(InstallerError, match="Codex rollback state conflict"):
        rollback_codex(
            _rollback_context(root, target, change.post, [], journal[-1]),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            NoOpFaultInjector(),
        )

    assert target.path.read_bytes() == foreign
    assert (root.path / "codex.rollback.stage").read_bytes() == stage_before
    assert recovery.path.read_bytes() == recovery_before
    root.close()


@pytest.mark.parametrize(
    ("point", "mutated_name"),
    [
        ("after_codex_semantic_receipt", "codex.rollback.stage"),
        ("after_codex_semantic_displaced_cleanup", "codex.recovery"),
    ],
)
def test_semantic_cleanup_rechecks_images_at_transition(
    monkeypatch, tmp_path: Path, point: str, mutated_name: str
) -> None:
    root, _, _, target, change, recovery = _semantic_fixture(tmp_path)
    journal: list = []
    with pytest.raises(RuntimeError, match="injected crash"):
        rollback_codex(
            _rollback_context(root, target, change.post, journal),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            CrashAt(point),
        )
    live_before = target.path.read_bytes()
    foreign = b'foreign = "changed-at-transition"\n'
    original = codex_adapter.conditional_remove_file

    def mutate(reference, expected, guards, fault):
        _write_private(reference.path, foreign)
        return original(reference, expected, guards, fault)

    monkeypatch.setattr(codex_adapter, "conditional_remove_file", mutate)
    with pytest.raises(InstallerError, match="Codex rollback state conflict"):
        rollback_codex(
            _rollback_context(root, target, change.post, [], journal[-1]),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            NoOpFaultInjector(),
        )

    assert target.path.read_bytes() == live_before
    assert (root.path / mutated_name).read_bytes() == foreign
    root.close()


@pytest.mark.parametrize(
    "state",
    [RollbackState.C1, RollbackState.C2, RollbackState.C3, RollbackState.C4],
)
def test_semantic_physical_prefix_before_journal_retries(
    tmp_path: Path, state: RollbackState
) -> None:
    root, _, _, target, change, recovery = _semantic_fixture(tmp_path)
    crashing = JournalCrash(state)
    context = replace(_rollback_context(root, target, change.post, []), journal=crashing)
    with pytest.raises(RuntimeError, match="journal crash"):
        rollback_codex(
            context,
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            NoOpFaultInjector(),
        )
    persisted = crashing.persisted[-1] if crashing.persisted else None

    result = rollback_codex(
        _rollback_context(root, target, change.post, [], persisted),
        recovery,
        change.post,
        change.managed_keys,
        Path(sys.executable),
        NoOpFaultInjector(),
    )

    assert result.state is RollbackState.C4
    assert result.restored is True
    assert not recovery.path.exists()
    assert not (root.path / "codex.rollback.stage").exists()
    root.close()


def test_rollback_rejects_changed_protected_preimage(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    target, _, change, recovery = _installed(root, desired, b'model = "before"\n')
    _write_private(recovery.path, b'model = "foreign"\n')
    before = {path.name: path.read_bytes() for path in root.path.iterdir() if path.is_file()}

    with pytest.raises(InstallerError, match="Codex rollback state conflict"):
        rollback_codex(
            _rollback_context(root, target, change.post, []),
            recovery,
            change.post,
            change.managed_keys,
            Path(sys.executable),
            NoOpFaultInjector(),
        )

    assert {
        path.name: path.read_bytes() for path in root.path.iterdir() if path.is_file()
    } == before
    root.close()


def test_managed_key_metadata_is_closed_and_contains_no_config_values(tmp_path: Path) -> None:
    root = _open_root(tmp_path / "codex")
    desired = _desired(tmp_path)
    _, _, change = _stage_config(root, desired, f'token = "{SECRET}"\n'.encode())
    metadata = change.managed_keys.to_dict()
    encoded = json.dumps(metadata, sort_keys=True)

    assert set(metadata) == {"server_keys", "env_keys", "forbidden_server_keys", "namespace"}
    assert "command" in metadata["server_keys"]
    assert "HOME" in metadata["env_keys"]
    assert metadata["forbidden_server_keys"] == ["disabled_tools", "tools"]
    assert metadata["namespace"] == "mcp__blender"
    assert desired.command not in encoded
    assert str(desired.env["HOME"]) not in encoded
    assert SECRET not in encoded
    root.close()
