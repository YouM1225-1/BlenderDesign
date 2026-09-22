from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from blender_mcp_installer.filesystem import (
    InstallerError,
    SafeRoot,
    TargetRef,
    capture_file,
    capture_tree,
)
from blender_mcp_installer.model import FileImage, ImageState, TreeImage
from blender_mcp_installer.upgrade_state import UpgradeRoots

MARKETPLACE = "official-blender-mcp"
PLUGIN = "blender-mcp-installer"
PLUGIN_ID = PLUGIN + "@" + MARKETPLACE


def read_owned_bytes(reference: TargetRef) -> tuple[bytes, FileImage]:
    before = capture_file(reference.root, reference.relative)
    if before.state is not ImageState.PRESENT or before.size > 32 * 1024 * 1024:
        raise InstallerError("missing or oversized identity file")
    parent_fd, name = reference.root.open_parent(reference.relative)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(32 * 1024 * 1024 + 1)
    finally:
        os.close(parent_fd)
    if (
        len(raw) != before.size
        or hashlib.sha256(raw).hexdigest() != before.sha256
        or capture_file(reference.root, reference.relative) != before
    ):
        raise InstallerError("identity file changed")
    return raw, before


def content_sha256(image: TreeImage) -> str:
    if image.state is not ImageState.PRESENT or image.mode & 0o022:
        raise InstallerError("unsafe plugin tree")
    entries = []
    for entry in image.entries:
        if entry.mode & 0o022:
            raise InstallerError("unsafe plugin tree entry")
        entries.append((entry.path, entry.kind, entry.sha256))
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def codex_json(codex: Path, roots: UpgradeRoots, *arguments: str) -> dict[str, Any]:
    env = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    env.update(HOME=str(roots.home), CODEX_HOME=str(roots.codex_home))
    result = subprocess.run(
        [str(codex), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    value = json.loads(result.stdout)
    if type(value) is not dict:
        raise InstallerError("invalid Codex registration response")
    return value


def validate_installed_payload(
    payload: dict[str, Any], desired: dict[str, str]
) -> dict[str, Any]:
    installed = payload.get("installed")
    if type(installed) is not list:
        raise InstallerError("missing installed plugin list")
    matches = [
        item
        for item in installed
        if type(item) is dict
        and (item.get("pluginId") == PLUGIN_ID or item.get("name") == PLUGIN)
    ]
    if len(matches) != 1:
        raise InstallerError("installed plugin identity is not unique")
    item = matches[0]
    expected = {
        "pluginId": PLUGIN_ID,
        "name": PLUGIN,
        "marketplaceName": MARKETPLACE,
        "version": desired["plugin_version"],
    }
    if (
        any(item.get(key) != value for key, value in expected.items())
        or item.get("installed") is not True
        or item.get("enabled") is not True
    ):
        raise InstallerError("installed plugin identity mismatch")
    source, marketplace = item.get("source"), item.get("marketplaceSource")
    if (
        type(source) is not dict
        or source.get("source") != "local"
        or source.get("path")
        != str(Path(desired["projection"]) / "plugins" / PLUGIN)
        or type(marketplace) is not dict
        or marketplace.get("sourceType") != "local"
        or marketplace.get("source") != desired["projection"]
    ):
        raise InstallerError("installed plugin source mismatch")
    return item


@dataclass(frozen=True)
class RegistrationSnapshot:
    item: dict[str, Any]
    config: FileImage
    cache: TreeImage
    projection: TreeImage


def inspect_registration(
    codex: Path, roots: UpgradeRoots, desired: dict[str, str]
) -> RegistrationSnapshot:
    projection = Path(desired["projection"])
    if projection != roots.projections / desired["commit"]:
        raise InstallerError("registration projection mismatch")
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        with SafeRoot.open(roots.codex_home, os.getuid(), roots.codex_home) as codex_root:
            cache_relative = (roots.caches / desired["plugin_version"]).relative_to(
                roots.codex_home
            )
            projection_relative = projection.relative_to(roots.home)
            config = capture_file(codex_root, PurePath("config.toml"))
            cache = capture_tree(codex_root, cache_relative)
            projection_image = capture_tree(home, projection_relative)
            source = capture_tree(home, projection_relative / "plugins" / PLUGIN)
            raw, _ = read_owned_bytes(
                TargetRef(
                    home,
                    projection_relative / "plugins" / PLUGIN / ".codex-plugin/plugin.json",
                )
            )
            manifest = json.loads(raw)
            if (
                manifest.get("name") != PLUGIN
                or manifest.get("version") != desired["plugin_version"]
            ):
                raise InstallerError("projected plugin manifest mismatch")
            if content_sha256(source) != content_sha256(cache):
                raise InstallerError("cached plugin content mismatch")
            item = validate_installed_payload(
                codex_json(
                    codex,
                    roots,
                    "plugin",
                    "list",
                    "--marketplace",
                    MARKETPLACE,
                    "--json",
                ),
                desired,
            )
            listing = codex_json(codex, roots, "plugin", "marketplace", "list", "--json")
            matches = [
                row
                for row in listing.get("marketplaces", [])
                if type(row) is dict and row.get("name") == MARKETPLACE
            ]
            if len(matches) != 1 or matches[0].get("root") != str(projection):
                raise InstallerError("marketplace source mismatch")
            if (
                capture_file(codex_root, PurePath("config.toml")) != config
                or capture_tree(codex_root, cache_relative) != cache
                or capture_tree(home, projection_relative) != projection_image
            ):
                raise InstallerError("registration changed during verification")
            return RegistrationSnapshot(item, config, cache, projection_image)
