from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import Any, Iterator
from uuid import UUID, uuid4

from blender_mcp_installer.filesystem import (
    InstallerError,
    NoOpFaultInjector,
    SafeRoot,
    TargetRef,
    capture_file,
    capture_tree,
    write_atomic_json,
)
from blender_mcp_installer.model import ImageState, TreeImage
from blender_mcp_installer.upgrade_discovery import lease_protocol
from blender_mcp_installer.upgrade_locks import ensure_usage_lock, usage_lock
from blender_mcp_installer.upgrade_registration import read_owned_bytes
from blender_mcp_installer.upgrade_state import UpgradeRoots, uuid_text


class RuntimeInUse(InstallerError):
    code = "runtime_in_use"


class LegacyHandoffRequired(InstallerError):
    code = "legacy_handoff_required"


def process_snapshot(
    roots: UpgradeRoots, runtime: Path, codex: Path
) -> tuple[dict[str, str], ...]:
    output = subprocess.run(
        ["/bin/ps", "-axo", "pid=,uid=,lstart=,command="],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout
    markers = (
        str(runtime),
        str(roots.caches),
        str(codex),
        "/Applications/ChatGPT.app/",
        "/Applications/Codex.app/",
    )
    records = []
    for line in output.splitlines():
        fields = line.strip().split(None, 7)
        if len(fields) != 8 or not fields[0].isdigit() or not fields[1].isdigit():
            raise LegacyHandoffRequired("unrecognized process inventory")
        command = fields[7]
        tokens = shlex.split(command)
        if (
            int(fields[0]) != os.getpid()
            and int(fields[1]) == os.getuid()
            and any(marker in token for token in tokens[:2] for marker in markers)
        ):
            records.append(
                {
                    "pid": fields[0],
                    "uid": fields[1],
                    "started": " ".join(fields[2:7]),
                    "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
                }
            )
    return tuple(sorted(records, key=lambda row: int(row["pid"])))


def begin_handoff(
    state: SafeRoot, roots: UpgradeRoots, runtime: Path, codex: Path
) -> dict[str, Any]:
    processes = process_snapshot(roots, runtime, codex)
    if not processes:
        raise LegacyHandoffRequired(
            "begin handoff requires positively identified supported clients"
        )
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        image = capture_tree(home, runtime.relative_to(roots.home))
    if image.state is ImageState.ABSENT:
        raise LegacyHandoffRequired("legacy runtime is absent")
    identifier = str(uuid4())
    fd = state.open_directory(PurePath("handoffs"), create=True)
    os.close(fd)
    doc = {
        "schema_version": 1,
        "id": identifier,
        "uid": os.getuid(),
        "home": str(roots.home),
        "codex_home": str(roots.codex_home),
        "runtime": str(runtime),
        "expected": image.to_dict(),
        "scope": "cooperating-managed-clients",
        "processes": list(processes),
    }
    ref = TargetRef(state, PurePath("handoffs", identifier + ".json"))
    write_atomic_json(
        ref,
        capture_file(state, ref.relative),
        doc,
        UUID(identifier),
        fault=NoOpFaultInjector(),
    )
    return {
        "handoff_id": identifier,
        "stop_required": list(processes),
        "scope": "cooperating-managed-clients",
    }


def verify_handoff(
    state: SafeRoot,
    roots: UpgradeRoots,
    runtime: Path,
    codex: Path,
    identifier: str,
    image: TreeImage,
) -> dict[str, Any]:
    identifier = uuid_text(identifier)
    raw, proof = read_owned_bytes(
        TargetRef(state, PurePath("handoffs", identifier + ".json"))
    )
    doc = json.loads(raw)
    if (
        type(doc) is not dict
        or set(doc)
        != {
            "schema_version",
            "id",
            "uid",
            "home",
            "codex_home",
            "runtime",
            "expected",
            "scope",
            "processes",
        }
        or type(doc["schema_version"]) is not int
        or doc["schema_version"] != 1
        or doc["id"] != identifier
        or doc["uid"] != os.getuid()
        or doc["home"] != str(roots.home)
        or doc["codex_home"] != str(roots.codex_home)
        or doc["runtime"] != str(runtime)
        or TreeImage.from_dict(doc["expected"]) != image
        or doc["scope"] != "cooperating-managed-clients"
        or type(doc["processes"]) is not list
        or not doc["processes"]
    ):
        raise LegacyHandoffRequired("handoff identity mismatch")
    for record in doc["processes"]:
        if (
            type(record) is not dict
            or set(record) != {"pid", "uid", "started", "command_sha256"}
            or record["uid"] != str(os.getuid())
            or not record["pid"].isdigit()
        ):
            raise LegacyHandoffRequired("invalid handoff process identity")
        try:
            os.kill(int(record["pid"]), 0)
        except ProcessLookupError:
            pass
        else:
            raise LegacyHandoffRequired("recorded process still exists or PID was reused")
    if process_snapshot(roots, runtime, codex):
        raise LegacyHandoffRequired(
            "supported clients restarted; external maintenance terminal required"
        )
    return {
        "relative": "handoffs/" + identifier + ".json",
        "expected": proof.to_dict(),
    }


@contextmanager
def runtime_quiescence(
    state: SafeRoot,
    roots: UpgradeRoots,
    runtime: Path,
    codex: Path,
    handoff_id: str | None = None,
) -> Iterator[dict[str, Any] | None]:
    with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
        image = capture_tree(home, runtime.relative_to(roots.home))
    if image.state is ImageState.ABSENT:
        yield None
        return
    proof = None
    if not lease_protocol(image):
        if handoff_id is None:
            raise LegacyHandoffRequired(
                "legacy runtime requires external maintenance handoff"
            )
        proof = verify_handoff(state, roots, runtime, codex, handoff_id, image)
        ensure_usage_lock(state, image.dev, image.ino)
    with usage_lock(state, image.dev, image.ino, exclusive=True) as acquired:
        if not acquired:
            raise RuntimeInUse("managed runtime is in use; targets unchanged")
        with SafeRoot.open(roots.home, os.getuid(), roots.home) as home:
            if capture_tree(home, runtime.relative_to(roots.home)) != image:
                raise RuntimeInUse("runtime changed before handoff")
        yield {"image": image.to_dict(), "legacy_proof": proof}
