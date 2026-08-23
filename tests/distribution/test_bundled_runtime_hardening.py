from __future__ import annotations

import json
from pathlib import Path
import sys
from zipfile import ZipFile


ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins/blender-mcp-installer"
ARTIFACTS = PLUGIN / "artifacts"
sys.path.insert(0, str(PLUGIN / "scripts"))

from blender_mcp_installer.bundle import (  # noqa: E402
    BUNDLE_VERSION,
    DOWNSTREAM_PATCHES,
    PATCH_README_SHA256,
    PATCHED_SOURCE_SHA256,
    UPSTREAM_COMMIT,
)


def _wheel_source(name: str) -> str:
    wheel = ARTIFACTS / "blender_mcp-1.0.0-py3-none-any.whl"
    with ZipFile(wheel) as archive:
        return archive.read(name).decode("utf-8")


def _extension_source(name: str) -> str:
    extension = ARTIFACTS / "mcp-1.0.0.zip"
    with ZipFile(extension) as archive:
        return archive.read(name).decode("utf-8")


def test_manifest_matches_reviewed_upstream_pin() -> None:
    manifest = json.loads((ARTIFACTS / "manifest.json").read_text())
    assert manifest["upstream"]["commit"] == UPSTREAM_COMMIT
    assert manifest["bundle_version"] == BUNDLE_VERSION
    assert manifest["downstream"] == {
        "source_tree_sha256": PATCHED_SOURCE_SHA256,
        "readme_sha256": PATCH_README_SHA256,
        "patches": [
            {"filename": filename, "sha256": digest, "summary": summary}
            for filename, digest, summary in DOWNSTREAM_PATCHES
        ],
    }


def test_wheel_uses_bounded_result_file_and_process_group() -> None:
    source = _wheel_source("blmcp/tools_helpers/blender_cli.py")
    assert "_RESULT_PREFIX" not in source
    assert "_ERROR_PREFIX" not in source
    for token in (
        "_MAX_RESULT_BYTES = 10 * 1024 * 1024",
        "_MAX_STDOUT_BYTES = 1024 * 1024",
        "_MAX_STDERR_BYTES = 1024 * 1024",
        'start_new_session=(os.name == "posix")',
        "private_blend_for_cli",
        'TemporaryDirectory(prefix=".blmcp-job-"',
    ):
        assert token in source


def test_arbitrary_cli_uses_private_snapshot() -> None:
    source = _wheel_source("blmcp/tools/execute_blender_code.py")
    assert "deadline = time.monotonic() + _CLI_TIMEOUT" in source
    assert "with private_blend_for_cli(blend_file, deadline=deadline) as private_path:" in source
    assert "run_blender_cli(private_path, code, deadline=deadline)" in source
    assert "not a sandbox for hostile Python" in source


def test_private_snapshot_binds_live_file_identity_and_state() -> None:
    source = _wheel_source("blmcp/tools_helpers/blender_cli.py")
    for token in (
        "source_stat.st_ctime_ns",
        'os.path.samefile(str(state["filepath"]), source)',
        "use_live_snapshot",
        "verify_clean_snapshot",
        "Live blend-file changed before snapshot",
    ):
        assert token in source


def test_wheel_has_one_mcp_version_compatibility_boundary() -> None:
    source = _wheel_source("blmcp/mcp_compat.py")
    assert 'importlib.import_module("mcp.server.mcpserver")' in source
    assert 'importlib.import_module("mcp.server.fastmcp")' in source
    assert "MCPServer" in source and "FastMCP" in source
    assert "model_validate" in source


def test_summary_cli_tools_read_disk_directly() -> None:
    names = (
        "get_blendfile_summary_datablocks.py",
        "get_blendfile_summary_missing_files.py",
        "get_blendfile_summary_of_linked_libraries.py",
        "get_blendfile_summary_path_info.py",
        "get_blendfile_summary_usage_guess.py",
    )
    for name in names:
        source = _wheel_source("blmcp/tools/" + name)
        assert "synced_blend_for_cli" not in source
        assert "return run_blender_cli(blend_file," in source


def test_retina_scale_precedes_small_file_return() -> None:
    source = _wheel_source("blmcp/tools/_template_image_downscale_to_size_limit.py")
    scale = source.index("coordinate_size = (")
    fast_return = source.index("if im.size == coordinate_size and source_fits:")
    assert scale < fast_return
    assert "max(1, coordinate_size[0])" in source
    assert "max(1, coordinate_size[1])" in source
    assert "im.resize(\n            coordinate_size," in source
    assert "pixel_size" not in source
    for token in ("width // 2", "height // 2", "width / 2", "height / 2"):
        assert token not in source


def test_inner_timeouts_are_120_seconds() -> None:
    cli = _wheel_source("blmcp/tools_helpers/blender_cli.py")
    connection = _wheel_source("blmcp/tools_helpers/connection.py")
    assert "_CLI_TIMEOUT = 120.0" in cli
    assert "_TIMEOUT = 120.0" in connection


def test_upstream_screenshot_envelope_fix_is_retained() -> None:
    for name in (
        "get_screenshot_of_area_as_image_toolcode.py",
        "get_screenshot_of_window_as_image_toolcode.py",
    ):
        source = _wheel_source("blmcp/tools/" + name)
        assert "# Subtract 2048 for 2 KiB headroom for JSON envelope." in source
        assert "((1_048_576 - 2048) * 3) // 4" in source


def test_interactive_extension_has_bounded_fair_nonblocking_transport() -> None:
    source = _extension_source("mcp_to_blender_server.py")
    for token in (
        "_MAX_CLIENTS = 16",
        "_ACCEPT_BUDGET_PER_POLL = _LISTEN_BACKLOG",
        "_SEND_BUDGET_PER_POLL = 256 * 1024",
        "def _flush_client_response(",
        "response_offset",
        "connection_count",
        "_MAX_RESPONSE_BYTES = 10 * 1024 * 1024",
        "Response exceeds {:d} byte limit",
    ):
        assert token in source

    capture = _extension_source("capture_output.py")
    assert "_MAX_CAPTURE_CHARS = 1024 * 1024" in capture
    assert "[output truncated at {:d} characters]" in capture

    connection = _wheel_source("blmcp/tools_helpers/connection.py")
    assert "_MAX_RESPONSE_BYTES = 10 * 1024 * 1024" in connection
    assert "missing the null-byte delimiter" in connection
