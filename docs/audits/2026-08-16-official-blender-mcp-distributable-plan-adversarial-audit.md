# Official Blender MCP Distributable Plan Adversarial Audit

Date: 2026-08-16

Plan: `docs/superpowers/plans/2026-08-16-official-blender-mcp-distributable-codex-installer.md`

Frozen plan SHA-256: `fb69e31ef0445d38c2caeed277c69519f95ed19c5f067eabcd7e7733dc767d72`

Base commit: `c2b41f2f5af26eac59422fe321fe9e685a873ea9`

## Verdict

**READY FOR SUBAGENT-DRIVEN IMPLEMENTATION**

Three independent final reviewers re-read the complete revised plan. Security,
executability, and minimality/cross-Mac portability each returned READY with
zero Critical, zero Important, and zero Minor findings.

## Audit method

The first pass assigned three independent read-only reviewers to adversarially
test the original 1,775-line plan from different angles:

| Lens | Initial result |
| --- | --- |
| Specification and security | NOT READY — 8 Critical, 9 Important, 1 Minor |
| Executability, TDD, integration, and acceptance | NOT READY — 7 Critical, 9 Important, 2 Minor |
| Minimality and cross-Mac portability | NOT READY — 5 Critical, 7 Important, 4 Minor |

The controller deduplicated the findings into binding corrections, revised the
plan, and sent the complete plan through fresh re-audits. Each remaining
Critical or Important finding was adjudicated and corrected. The last closure
cycle specifically removed checkout-hook execution from both trust bootstraps,
made private trust cleanup explicit, completed selector crash reconciliation,
made Codex rollback fault injection executable, and fixed multi-record `lsof`
identity parsing.

The final reviewers verified the exact frozen SHA above and reported:

| Final lens | Critical | Important | Minor | Verdict |
| --- | ---: | ---: | ---: | --- |
| Security | 0 | 0 | 0 | READY |
| Executability and testability | 0 | 0 | 0 | READY |
| Minimality and portability | 0 | 0 | 0 | READY |

## Binding decisions retained in the frozen plan

- V1 targets macOS arm64 and Blender `>=5.2,<5.3`.
- The official upstream source remains pinned to commit
  `482c540395ad93a2f86b1ada1520f4fddf8ebcfa`; no second MCP implementation is
  introduced.
- SHA-256 supplies artifact integrity. The reviewed immutable Git
  commit/release channel is the authenticity boundary; the plan does not call
  checksums signatures.
- The runtime is network-assisted but exact-version and hash locked. V1 does
  not add a wheelhouse, daemon, generic package manager, GUI installer, or
  multi-platform abstraction.
- The Codex plugin is skill-only. It uses repository marketplace discovery and
  does not add `.mcp.json` or require a separate Codex installer.
- Four host-local consents remain independent: extension install/enable,
  Online Access, localhost bridge, and arbitrary-Python tools.
- Installation configures state but does not launch or kill Blender. The
  operator starts the selected Blender normally; verification performs the
  live listener, handshake/catalog, and read-only-tool checks.
- Filesystem mutation, receipts/selectors, crash recovery, Codex three-way
  rollback, Blender state, runtime publication, and clean-profile acceptance
  use closed schemas and deterministic, fault-injected test contracts.
- A physical second-Mac canary and independently authenticated `codex exec`
  may remain explicitly `NOT_RUN`; the local implementation gate, marketplace
  discovery, clean-profile flow, rollback, and repository gates are blocking.

## Evidence and implementation gate

- Baseline repository verification passed from a clean detached clone of the
  base commit with `./scripts/checks.sh`: Ruff, strict mypy over 22 files,
  vendor/nested gates, and 369/369 tests.
- The implementation worktree was otherwise clean before this plan and audit
  were added. The same repository gates must pass again after the plan-freeze
  commit and after implementation.
- Each of the ten plan tasks must now use a fresh implementer, runnable RED
  tests before production changes, a focused review package, an independent
  reviewer, and a clean task commit. Critical and Important review findings
  block advancement.
- After all tasks, a fresh whole-branch adversarial audit and full acceptance
  verification are required before the final submission commit.

This report records plan readiness only. It is not implementation evidence.
