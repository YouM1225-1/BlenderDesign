# Official Blender MCP distributable installer

This repository packages a reviewed, LLM-driven installer for the official Blender
MCP. It targets Darwin arm64 with Blender >=5.2.0,<5.3.0, uv 0.12.2, and a local
Python 3.13. The Codex plugin is a skill-only delivery adapter, not another MCP
server; the installed managed launcher connects Codex to the official server over
local STDIO and the Blender extension over localhost:9876.

## Trust and entrypoint

EXPECTED_DISTRIBUTION_COMMIT comes from the reviewed repository or release channel,
never from `manifest.json`. SHA-256 provides integrity, not authenticity; the reviewed
immutable distribution commit is the authenticity boundary.

Before adding the repository marketplace or importing the plugin, follow the exact
`TRUST_BOOTSTRAP` block in
`plugins/blender-mcp-installer/skills/install-official-blender-mcp/SKILL.md`. It clears
Git and Python redirection variables, checks a clean scoped source tree, creates a
private detached hook-free worktree from the reviewed commit, and compares the
commit-object checksum file with the materialized artifacts. All later plugin and
bundle paths must come from that private worktree in the same fail-fast shell session.

The operator supplies:

- `SOURCE_DISTRIBUTION_ROOT`: the local repository that contains the reviewed commit.
- `EXPECTED_DISTRIBUTION_COMMIT`: exactly 40 lowercase hexadecimal characters.
- `BLENDER_BIN`: the absolute selected Blender executable.
- `CODEX_BIN`: a validated absolute Codex executable.
- optionally `UV_BIN`: an absolute uv executable; otherwise PATH and then
  `$HOME/.local/bin/uv` are probed.

The skill gives the exact marketplace, inspect, install, verify, rollback, and private
worktree cleanup commands. Do not substitute the source checkout for its trusted
worktree.

## Operator workflow

1. Establish the trusted worktree and add its repository marketplace/plugin.
2. Resolve uv 0.12.2 and an already-installed local Python 3.13 without downloads.
3. Run `inspect` before mutation.
4. Obtain four separate explicit answers: extension install/enable, Blender Allow
   Online Access, localhost bridge, and arbitrary-Python tools.
5. Run `install` once with all four flags. Consent recorded in a receipt is evidence,
   not reusable authorization.
6. For a changed install, the operator starts the selected Blender normally. The
   installer never starts or terminates it. Run `verify` only after confirmation.
7. Before repair or rollback, the operator closes Blender normally and confirms it.
   Retain the receipt and pass its absolute path to rollback.

The install is network-assisted: a changed runtime install fetches exact-version,
hash-locked wheels from PyPI. uv may update its execution cache even for read-only
inspect/verify launchers. Blender may write `.cache/compat.dat`. The installer does
not open or modify project `.blend` files.

## Delivery, credentials, and acceptance

The repository marketplace makes the operator workflow discoverable to an LLM; it
does not add `.mcp.json`, an app, a daemon, a second server, or a separate Codex
installer. The generated Codex MCP entry points at a local STDIO managed launcher.

Marketplace add/plugin add/list is a local blocking gate. An actual `codex exec`
invocation requires an independently supplied `DISPOSABLE_CODEX_API_KEY` and a
private disposable `HOME`/`CODEX_HOME`. Never copy normal Codex credentials. Without
that credential record `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN`; this does not block
the implementation gate. The separate physical-host result starts as
`SECOND_MAC_CANARY_STATUS: NOT_RUN` until a release operator supplies another Mac.

Supported failures are transactional and receipt-backed, but the threat model does
not claim protection from an actively malicious same-UID process. Preserve receipts
and the trusted-worktree evidence through verification or rollback, then use the
skill's exact bounded cleanup sequence.
