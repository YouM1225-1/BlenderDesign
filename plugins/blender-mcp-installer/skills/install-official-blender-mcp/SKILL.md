---
name: install-official-blender-mcp
description: Inspect, install, verify, repair, or roll back the reviewed official Blender MCP distribution on a supported Mac. Use for distribution setup and installation health, not scene modeling or general repository development.
---

# Install Official Blender MCP

This skill is a delivery adapter, not another MCP server. Codex uses the bundled
official wheel through its managed launcher. Complete the requested operation;
an inspection request does not authorize installation or marketplace changes.

## Scope and essential constraints

- Supported baseline: Darwin arm64, Blender >=5.2.0,<5.3.0, local Python 3.13.13,
  uv 0.12.2, localhost:9876. The bundled manifest and installer validate it.
- SHA-256 provides integrity, not authenticity. The reviewed immutable distribution
  commit is the authenticity boundary. Obtain the expected commit independently
  of the archive and adjacent checksums; never execute the source checkout.
- Use the private trusted worktree for installer execution and a commit-addressed
  persistent projection for marketplace registration. Do not register the worktree.
- Never start, terminate, or force-close Blender or open/modify project `.blend`
  files through this installer. Do not install uv or Python. A validated absolute
  symlink to either runner is supported.
- For an installation the operator requested, the standing default-allow policy
  covers extension install/enable, Blender Online Access, the localhost bridge,
  and arbitrary-Python tools. Always pass all four explicit CLI flags. Reuse existing
  authorization; a revoked default blocks the dependent install, not read-only work.

## Choose the operation

Read the applicable sections of [the command reference](references/workflow.md).
Use the exact fenced blocks: they are exercised by distribution tests. Run trust
bootstrap and define the runner once per fail-fast Bash session; call
`run_uv_bootstrap` before each installer command. Keep that session and its trust
objects alive through the selected operation, then run the bounded cleanup.

- **Inspect:** trust + runner + `INSPECT` + cleanup. No marketplace registration.
- **Install/repair:** inspect first, apply existing authorization, prepare the
  persistent marketplace, then run `INSTALL` once. Preserve the receipt. Verify
  when the operator has started Blender normally; repair requires Blender closed.
- **Verify:** trust + runner + `VERIFY` + cleanup. A running selected Blender is
  required; inspect its state or reuse current user confirmation instead of asking
  for the same confirmation again. Verification does not update registration.
- **Rollback:** trust + runner + `ROLLBACK` with the original absolute receipt path,
  then cleanup. Establish that Blender is closed; ask the operator to save and close
  it only if needed. The receipt does not authorize a new install.

For ordinary inspect/verify/rollback, skip marketplace preparation and release
smoke checks. If prerequisites or trust checks fail, report the specific failure
and continue independent diagnosis where possible. Do not retry an uncertain write
until receipt and host state establish what happened.

## Completion

Report the operation, verified result, receipt/evidence location, and any required
operator action. An install awaiting Blender startup is not verified. Release-only
checks and their `NOT_RUN` statuses are in the command reference; missing disposable
credentials or a second Mac do not block ordinary installation. Never copy normal
Codex credentials to a test profile.
