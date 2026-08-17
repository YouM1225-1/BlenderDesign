#!/usr/bin/env python3
"""Regression checks for the locally patched official Blender MCP runtime."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace


RUNTIME_ROOT = Path.home() / ".local/share/blender-lab-mcp/runtime"
SITE_PACKAGES = next((RUNTIME_ROOT / "lib").glob("python*/site-packages"))
TOOLS = SITE_PACKAGES / "blmcp/tools"
ADDON = (
    Path.home()
    / "Library/Application Support/Blender/5.2/extensions/user_default/mcp"
)


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def install_fake_bpy(*, pixel_size: float = 1.0) -> ModuleType:
    bpy = ModuleType("bpy")
    width, height = 1280, 720
    physical_width = round(width * pixel_size)
    physical_height = round(height * pixel_size)
    area = SimpleNamespace(
        type="VIEW_3D",
        ui_type="VIEW_3D",
        x=0,
        y=0,
        width=physical_width,
        height=physical_height,
        spaces=SimpleNamespace(active=None),
        regions=[],
    )
    screen = SimpleNamespace(name="Layout", areas=[area])
    workspace = SimpleNamespace(name="Layout", screens=[screen])
    window = SimpleNamespace(
        width=width,
        height=height,
        screen=screen,
        workspace=workspace,
    )
    bpy.app = SimpleNamespace(background=False)
    bpy.context = SimpleNamespace(
        window=window,
        screen=screen,
        scene=SimpleNamespace(name="Scene"),
        preferences=SimpleNamespace(system=SimpleNamespace(pixel_size=pixel_size)),
        active_object=None,
        selected_objects=[],
        mode="OBJECT",
    )
    sys.modules["bpy"] = bpy
    return bpy


def test_retina_coordinates() -> None:
    module = load("window_json_toolcode_test", TOOLS / "get_screenshot_of_window_as_json_toolcode.py")
    for scale in (1.0, 2.0):
        install_fake_bpy(pixel_size=scale)
        result = module.main(None)
        assert result.window_width == round(1280 * scale)
        assert result.window_height == round(720 * scale)
        assert result.pixel_size == scale
        assert result.coordinate_units == "physical_pixels"
        assert result.areas[0]["width"] <= result.window_width
        assert result.areas[0]["height"] <= result.window_height


def test_nested_api_docs() -> None:
    sys.path.insert(0, str(SITE_PACKAGES))
    from blmcp.tools import get_python_api_docs

    class FakeMCP:
        function = None

        def tool(self, **_kwargs):
            def decorator(function):
                self.function = function
                return function

            return decorator

    mcp = FakeMCP()
    get_python_api_docs.register(mcp)
    result = mcp.function("bpy.types.Scene.frame_current")
    assert result["kind"] == "definition"
    assert result["found"] is True
    assert "frame_current" in result["content"]


def test_ui_type_workspace_match() -> None:
    bpy = install_fake_bpy()
    area = bpy.context.screen.areas[0]
    area.type = "NODE_EDITOR"
    area.ui_type = "ShaderNodeTree"

    def enum(*values: str) -> list[SimpleNamespace]:
        return [SimpleNamespace(identifier=value) for value in values]

    bpy.types = SimpleNamespace(
        Area=SimpleNamespace(
            bl_rna=SimpleNamespace(
                properties={
                    "type": SimpleNamespace(enum_items=enum("VIEW_3D", "NODE_EDITOR")),
                    "ui_type": SimpleNamespace(enum_items=enum("VIEW_3D", "ShaderNodeTree")),
                }
            )
        )
    )
    bpy.data = SimpleNamespace(workspaces=[bpy.context.window.workspace])
    module = load("jump_space_toolcode_test", TOOLS / "jump_to_tab_by_space_type_toolcode.py")
    result = module.main(module.Params("ShaderNodeTree", False))
    assert result.status == "ok"
    assert result.workspace == "Layout"


def test_requested_render_path() -> None:
    bpy = install_fake_bpy()
    bpy.app.background = True
    render = SimpleNamespace(filepath="original.png")
    bpy.context.scene.render = render
    bpy.path = SimpleNamespace(abspath=lambda value: value)

    with tempfile.TemporaryDirectory() as directory:
        requested = str(Path(directory) / "requested.png")

        def render_still(*_args, write_still: bool) -> None:
            assert write_still is True
            Path(render.filepath).touch()

        bpy.ops = SimpleNamespace(render=SimpleNamespace(render=render_still))
        module = load("render_path_toolcode_test", TOOLS / "render_viewport_to_path_toolcode.py")
        result = module.main(module.Params(requested))
        assert result.status == "ok"
        assert result.filepath == requested
        assert Path(requested).is_file()
        assert render.filepath == "original.png"

    thumbnail_source = (TOOLS / "render_thumbnail_to_path_toolcode.py").read_text()
    viewport_source = (TOOLS / "render_viewport_to_path_toolcode.py").read_text()
    assert "bpy.app.tempdir" not in thumbnail_source + viewport_source
    assert 'rd.engine == "BLENDER_EEVEE"' in thumbnail_source


def test_output_limits() -> None:
    capture = load("capture_output_test", ADDON / "capture_output.py")
    capture._CAPTURE_MAX_CHARS = 8
    forwarded = io.StringIO()
    tee = capture._Tee(forwarded)
    assert tee.write("0123456789") == 10
    assert forwarded.getvalue() == "0123456789"
    assert tee.getvalue() == "01234567" + capture._TRUNCATED_MARKER

    connection_source = (SITE_PACKAGES / "blmcp/tools_helpers/connection.py").read_text()
    server_source = (ADDON / "mcp_to_blender_server.py").read_text()
    assert "_MAX_RESPONSE_BYTES = 10 * 1024 * 1024" in connection_source
    assert "_MAX_RESPONSE_BYTES = 10 * 1024 * 1024" in server_source


def main() -> None:
    tests = (
        test_retina_coordinates,
        test_nested_api_docs,
        test_ui_type_workspace_match,
        test_requested_render_path,
        test_output_limits,
    )
    for test in tests:
        test()
        print("PASS", test.__name__)


if __name__ == "__main__":
    main()
