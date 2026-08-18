# Official Blender MCP production apply — 2026-08-18

## Authorization boundary

- Distribution code candidate: `850d6c419f1eb206451c4f68c10267242d7c24c5`
- Audit-only certification: `f54d70382dd5ff866b187131e2db799f2c68c6a7`
- Upstream source pin: `ecdff98d6387440fb10d1ad71d35db25984e38e5`
- Bundle version: `1.0.0+ecdff98d6387`
- Plugin cachebuster: `1.0.0+codex.20260818004806`

The installer authorization input was the code candidate, not the audit-only
certification commit. The later upstream report-only correction `1ee37f7` does
not change the source pin or bundled files.

## Operator gates

The operator closed every Blender process before install. Port 9876 was free.
The installer stopped after publishing the changed installation and the
operator then started Blender normally. No process was terminated or launched
by the installer workflow.

Selected host inputs:

- Blender: `/Applications/Blender.app/Contents/MacOS/Blender`
- Python: canonical CPython 3.13.13
- uv: 0.12.2
- Codex: `/Applications/ChatGPT.app/Contents/Resources/codex`
- Platform: Darwin arm64

All four standing authorization flags were passed: reviewed extension install,
Blender Online Access, localhost bridge, and arbitrary-Python MCP tools.

## Trust and installation

The private Git bootstrap verified the exact distribution commit, a clean
source/index, empty private Git configuration/hooks/attributes, and all four
artifact checksums before executing installer code. The persistent marketplace
projection is:

`/Users/yeminjie/.local/share/blender-mcp-installer/marketplaces/official-blender-mcp/850d6c419f1eb206451c4f68c10267242d7c24c5`

The target-only marketplace recovery evidence is:

`/Users/yeminjie/.local/state/blender-mcp-installer/marketplace-recovery/registration.fikrr79o`

Pre-install inspection correctly reported `exact=false`. Its detailed checks
identified the pre-existing Blender preference and payload drift without
misclassifying a whole-file user preference hash as the semantic verdict.

The changed install produced:

- Receipt: `/Users/yeminjie/.local/state/blender-mcp-installer/receipts/14cdb260-4ffb-41f6-b101-a5e2fadf1245.json`
- Receipt SHA-256: `6c5f6250bd824b853b0e0359646b185d2b31bbef13cb00e7ee1b09f16d34e336`
- Receipt mode/owner: `0600`, UID 501
- `changed=true`
- `requires_blender_start=true`

## Verification

Post-start installer verification returned:

```json
{
  "parsed_codex": true,
  "effective_codex": true,
  "mcp_catalog": true,
  "blender_read_only": true,
  "tool_count": 26
}
```

The disposable marketplace smoke test passed. Its credential-safe plugin-list
JSON had SHA-256
`bbcbf985ef51f1006019ce4da79d1920687a336ae29c1e52cb8184ad8d1bd781`.
The persistent marketplace helper then verified the registered projection and
recovery evidence after private trust cleanup.

Normal-profile checks confirmed exactly one `official-blender-mcp` marketplace,
one installed and enabled `blender-mcp-installer`, no available replacement,
and plugin version `1.0.0+codex.20260818004806`. Effective MCP configuration
uses the managed launcher, startup timeout 20 seconds, tool timeout 150 seconds,
localhost:9876, and exactly 26 enabled tools.

## Restart lifecycle

Before Codex restart, eight MCP child processes remained under app-server PID
90896. Six still mapped the recovery runtime and two mapped the new runtime.
The operator exited and restarted Codex normally.

After restart:

- Old app-server PID 90896 exited.
- Old MCP PIDs 30640, 51142, 57724, 59474, 64501, 91110, 91237, and 97789 exited.
- New app-server PID 58141 owns new MCP children.
- New MCP PIDs 61154 and 65587 map only
  `/Users/yeminjie/.local/share/blender-lab-mcp/runtime/bin/python`.
- No new MCP process maps a `.runtime.recovery` path.
- Blender PID 44020 is the sole listener on `127.0.0.1:9876`.

Current-session read-only calls passed. The Blender scene summary returned one
scene, one camera, one light, one mesh, and three objects. Window coordinates
reported `2560×1296`; the VIEW_3D area reported `4200×2306`, confirming the
per-screenshot Retina coordinate-space contract in the installed runtime.

## Cleanup and exceptions

All private trust trees, the detached source worktree, and the disposable
marketplace profile created by the successful workflow were removed after their
evidence was recorded.

An initial interactive-shell attempt failed before creating a trust tree or
running prepare/inspect/install because terminal line editing corrupted the
long bootstrap input. A second attempt completed trust and idempotent marketplace
prepare, then stopped before inspect/install when its old cache path was replaced
by the new cachebuster. Its private trust tree was removed with the skill's exact
Git worktree cleanup sequence. Neither attempt installed or rolled back runtime
content.

- `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN` — no disposable credentials supplied.
- `SECOND_MAC_CANARY_STATUS: NOT_RUN` — no independent second Mac supplied.
- Saved-file CLI smoke was not repeated against the user's unsaved scene; the
  certified upstream background/foreground/interactive real-Blender suites
  cover that path.

## Result

Production apply and post-restart acceptance: **PASS**.

