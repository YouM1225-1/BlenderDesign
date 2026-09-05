from __future__ import annotations

import json
import os
import stat
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SANITIZED_ENV = (
    "HOME",
    "CODEX_HOME",
    "BLENDER_USER_RESOURCES",
    "BLENDER_USER_CONFIG",
    "BLENDER_USER_EXTENSIONS",
    "BLENDER_MCP_HOST",
    "BLENDER_MCP_PORT",
)


@dataclass(frozen=True)
class HostHarness:
    root: Path
    home: Path
    codex_home: Path
    resources: Path
    config: Path
    extensions: Path
    bundle: Path
    state_root: Path
    data_root: Path
    state_file: Path
    commands: Path
    codex: Path
    blender: Path
    uv: Path


def _write_launcher(path: Path, tool: str, state_file: Path, commands: Path) -> None:
    source = (
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        "import sys\n"
        f"sys.path.insert(0, {str(Path(__file__).parents[2])!r})\n"
        "from tests.distribution.fake_host import run_fake\n"
        f"raise SystemExit(run_fake({tool!r}, Path({str(state_file)!r}), "
        f"Path({str(commands)!r}), sys.argv[1:]))\n"
    )
    path.write_text(source)
    path.chmod(0o700)


def create_host(tmp_path: Path) -> HostHarness:
    root = tmp_path / "host"
    home = root / "home"
    codex_home = root / "codex"
    resources = root / "blender" / "resources"
    config = resources / "config"
    extensions = resources / "extensions"
    bundle = root / "bundle"
    state_root = home / ".local/state/blender-mcp-installer"
    data_root = home / ".local/share/blender-lab-mcp"
    bin_dir = root / "bin"
    for path in (
        root,
        home,
        codex_home,
        resources,
        config,
        extensions,
        bundle,
        state_root,
        data_root,
        bin_dir,
    ):
        path.mkdir(exist_ok=True, parents=True, mode=0o700)
        path.chmod(0o700)
    state_file = root / "host-state.json"
    commands = root / "commands.jsonl"
    manifest = json.loads(
        (
            Path(__file__).parents[2] / "plugins/blender-mcp-installer/artifacts/manifest.json"
        ).read_text()
    )
    state_file.write_text(
        json.dumps(
            {
                "running": False,
                "version": "5.2.0",
                "architecture": "arm64",
                "resources": str(resources),
                "config": str(config),
                "extensions": str(extensions),
                "repository": "user_default",
                "manifest": None,
                "preferences": {},
                "python": sys.executable,
                "tools": manifest["tools"],
            },
            sort_keys=True,
        )
        + "\n"
    )
    commands.write_text("")
    tools = {name: bin_dir / name for name in ("codex", "blender", "uv")}
    for name, path in tools.items():
        _write_launcher(path, name, state_file, commands)
    return HostHarness(
        root,
        home,
        codex_home,
        resources,
        config,
        extensions,
        bundle,
        state_root,
        data_root,
        state_file,
        commands,
        tools["codex"],
        tools["blender"],
        tools["uv"],
    )


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _save(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _record(tool: str, argv: list[str], commands: Path, mutated: list[str]) -> None:
    record = {
        "tool": tool,
        "argv": argv,
        "env": {key: os.environ[key] for key in SANITIZED_ENV if key in os.environ},
        "mutated_paths": sorted(mutated),
    }
    with commands.open("a") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def _mcp_server(catalog: list[str], commands: Path) -> int:
    for line in sys.stdin:
        request = json.loads(line)
        method = request.get("method")
        argv = [str(method)]
        if method == "tools/call":
            argv.append(str(request.get("params", {}).get("name")))
        _record("blender-mcp", argv, commands, [])
        if method == "initialize":
            result: object = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "blender-mcp", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": [{"name": name} for name in catalog]}
        elif (
            method == "tools/call"
            and request.get("params", {}).get("name") == "get_blendfile_summary_datablocks"
        ):
            summary = {
                "status": "ok",
                "result": {
                    "status": "ok",
                    "datablock_counts": {"scenes": 1, "workspaces": 1},
                    "render_engine": "BLENDER_EEVEE_NEXT",
                    "scene_name": "Scene",
                    "workspaces": ["Layout"],
                    "active_workspace": "Layout",
                },
            }
            result = {
                "_meta": None,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(summary, indent=2),
                        "annotations": None,
                        "_meta": None,
                    }
                ],
                "structuredContent": summary,
                "isError": False,
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32601, "message": "unsupported fake request"},
            }
            print(json.dumps(response), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}), flush=True)
    return 0


def run_fake(tool: str, state_file: Path, commands: Path, argv: list[str]) -> int:
    state = _load(state_file)
    mutated: list[str] = []
    if tool == "codex":
        if argv == ["--version"]:
            print("codex-cli 0.149.0-alpha.4.1")
        elif argv in (
            ["mcp", "get", "--help"],
            ["plugin", "add", "--help"],
            ["plugin", "marketplace", "add", "--help"],
        ):
            suffix = " --json" if argv[:2] == ["mcp", "get"] else ""
            print("usage: codex " + " ".join(argv[:-1]) + suffix)
        elif argv == ["mcp", "get", "blender", "--json"]:
            config = Path(os.environ["CODEX_HOME"]) / "config.toml"
            parsed = tomllib.loads(config.read_text()) if config.exists() else {}
            print(json.dumps(parsed.get("mcp_servers", {}).get("blender", {}), sort_keys=True))
        else:
            _record(tool, argv, commands, mutated)
            return 2
    elif tool == "blender":
        if argv == ["--version"]:
            print(f"Blender {state['version']}")
        elif (len(argv) == 3 and argv[:2] == ["--background", "--python-expr"]) or (
            len(argv) == 4 and argv[:3] == ["--background", "--factory-startup", "--python-expr"]
        ):
            expression = argv[argv.index("--python-expr") + 1]
            if "save_userpref" in expression:
                target = Path(os.environ["BLENDER_USER_CONFIG"]) / "userpref.blend"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(state["preferences"], sort_keys=True) + "\n")
                mutated.append(str(target))
            print(json.dumps(state, sort_keys=True))
        elif (
            len(argv) == 4
            and argv[:3] == ["--command", "extension", "validate"]
            and Path(argv[-1]).is_absolute()
        ):
            print("valid")
        elif (
            len(argv) == 7
            and argv[:6]
            == [
                "--command",
                "extension",
                "install-file",
                "--repo",
                state["repository"],
                "--enable",
            ]
            and Path(argv[-1]).is_absolute()
        ):
            archive = Path(argv[-1])
            extensions = Path(os.environ.get("BLENDER_USER_EXTENSIONS", state["extensions"]))
            target = extensions / state["repository"] / "mcp"
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as extension:
                extension.extractall(target)
            state["manifest"] = str(target / "blender_manifest.toml")
            _save(state_file, state)
            mutated.extend((str(target), str(state_file)))
        else:
            _record(tool, argv, commands, mutated)
            return 2
    elif tool == "uv":
        if argv == ["--version"]:
            print("uv 0.12.2")
        elif argv == [
            "python",
            "find",
            "3.13",
            "--no-project",
            "--no-python-downloads",
            "--no-config",
        ]:
            print(state["python"])
        elif (
            len(argv) == 5
            and argv[:3] == ["venv", "--relocatable", "--python"]
            and Path(argv[3]).is_absolute()
            and Path(argv[4]).is_absolute()
        ):
            runtime = Path(argv[-1])
            (runtime / "bin").mkdir(parents=True)
            python = runtime / "bin/python"
            python.write_text(
                f"#!{sys.executable}\nimport os, sys\n"
                f"os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n"
            )
            python.chmod(stat.S_IRWXU)
            mutated.append(str(runtime))
        elif _valid_pip_install(argv):
            stage_python = Path(argv[3])
            runtime = stage_python.parent.parent
            runtime.mkdir(parents=True, exist_ok=True)
            (runtime / "fake-installed.json").write_text(
                json.dumps({"argv": argv}, sort_keys=True) + "\n"
            )
            server = runtime / "bin/blender-mcp"
            server.parent.mkdir(parents=True, exist_ok=True)
            server.write_text(
                f"#!{sys.executable}\nimport sys\nsys.path.insert(0, {str(Path(__file__).parents[2])!r})\n"
                "from tests.distribution.fake_host import _mcp_server\n"
                f"from pathlib import Path\nraise SystemExit(_mcp_server({state['tools']!r}, "
                f"Path({str(commands)!r})))\n"
            )
            server.chmod(stat.S_IRWXU)
            mutated.append(str(runtime))
        else:
            _record(tool, argv, commands, mutated)
            return 2
    else:
        _record(tool, argv, commands, mutated)
        return 2
    _record(tool, argv, commands, mutated)
    return 0


def _valid_pip_install(argv: list[str]) -> bool:
    if len(argv) < 4 or not Path(argv[3]).is_absolute() or not Path(argv[-1]).is_absolute():
        return False
    if len(argv) == 12:
        return (
            argv[:3] == ["pip", "install", "--python"]
            and argv[4:11]
            == [
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--no-deps",
                "--default-index",
                "https://pypi.org/simple",
                "-r",
            ]
            and Path(argv[-1]).name == "runtime-requirements.lock"
        )
    return (
        len(argv) == 7
        and argv[:3] == ["pip", "install", "--python"]
        and argv[4:6] == ["--no-deps", "--no-build"]
        and Path(argv[-1]).name == "blender_mcp-1.0.0-py3-none-any.whl"
    )


if __name__ == "__main__":
    raise SystemExit(run_fake(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:]))
