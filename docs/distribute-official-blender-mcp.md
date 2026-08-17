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
bundle execution paths must come from that private worktree in the same fail-fast
shell session. Before installer execution, the bundled helper uses the same private
Git/archive/checksum boundary to create an owner-controlled, commit-addressed
persistent marketplace projection under `$HOME/.local/share/blender-mcp-installer`.
Its private mode-0700 Git admin has empty config, hooks, templates, and info
attributes, reads the validated source object database only by hash, and never loads
source repository configuration. Replacement objects and system/global config remain
disabled. Before any trust operation, the bootstrap saves the operator PATH and fixes
the active PATH to macOS system directories; the saved PATH is consulted only to
discover uv, which is then validated and replaced with its canonical regular target.

The operator supplies:

- `SOURCE_DISTRIBUTION_ROOT`: the local repository that contains the reviewed commit.
- `EXPECTED_DISTRIBUTION_COMMIT`: exactly 40 lowercase hexadecimal characters.
- `BLENDER_BIN`: the absolute selected Blender executable.
- `CODEX_BIN`: a validated absolute Codex executable.
- optionally `UV_BIN`: an absolute regular or symlinked uv executable; otherwise the
  saved operator PATH and then `$HOME/.local/bin/uv` are probed. The resolved Python
  canonicalizes uv before any installer command or host check.

The skill gives the exact persistent-marketplace, inspect, install, verify, rollback,
and private-worktree cleanup commands. Its four installer launchers use Python `-B`,
so importing the installer cannot dirty the trusted worktree with bytecode. Do not
substitute the source checkout for its trusted worktree.

## Operator workflow

1. Establish the trusted worktree, materialize the persistent marketplace projection,
   and transactionally replace only the target marketplace registration.
2. Resolve uv 0.12.2 and an already-installed local Python 3.13 without downloads.
3. Run `inspect` before mutation.
4. Apply the operator's standing default-allow policy for extension install/enable,
   Blender Allow Online Access, localhost bridge, and arbitrary-Python tools. Do not
   ask four per-install questions unless the operator has revoked a default.
5. Run `install` once with all four explicit flags. The legacy receipt key
   `all_four_collected_for_this_workflow` means all four flags were active; it does not
   mean four prompts were shown.
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

Marketplace add/plugin add/list before and after private-worktree cleanup is a local
blocking gate. Registration recovery evidence is stored separately from installer
receipts and preserves the prior target source plus non-target fingerprints. An
actual `codex exec` invocation requires an independently supplied
`DISPOSABLE_CODEX_API_KEY` and a private disposable `HOME`/`CODEX_HOME`. Never copy
normal Codex credentials. Without that credential record
`LOCAL_LLM_INVOCATION_STATUS: NOT_RUN`; this does not block the implementation gate.
The separate physical-host result starts as
`SECOND_MAC_CANARY_STATUS: NOT_RUN` until a release operator supplies another Mac.

Supported failures are transactional and receipt-backed, but the threat model does
not claim protection from an actively malicious same-UID process. Preserve receipts
and the trusted-worktree evidence through verification or rollback, then use the
skill's exact bounded cleanup sequence.
