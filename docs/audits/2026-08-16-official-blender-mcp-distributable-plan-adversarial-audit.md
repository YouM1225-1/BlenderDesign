# Official Blender MCP Distributable Plan Adversarial Audit

Date: 2026-08-16

Plan: `docs/superpowers/plans/2026-08-16-official-blender-mcp-distributable-codex-installer.md`

Current plan SHA-256: `1d4ee2c51f0d41ac1eab7d01f898e2169280a5cb03a2c0b3625cfa7aec46a518`

Initial frozen plan SHA-256: `fb69e31ef0445d38c2caeed277c69519f95ed19c5f067eabcd7e7733dc767d72`

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

The final reviewers verified the exact initial frozen SHA above and reported:

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

## Task 1 executable-command amendment

Task 1 implementation and independent review exposed two documentation-only
command errors in the initially frozen plan:

- uv 0.12.2 rejects the redundant combination of `--only-binary :all:` and
  `--no-build`. The plan now uses `--require-hashes --only-binary :all:
  --no-deps`; source distributions and dependency expansion remain forbidden.
- The checksum file intentionally contains basenames, so `shasum -c` must run
  from the artifact directory. The plan now uses an artifact-directory
  subshell and still verifies the same commit-bound checksum bytes.

The two-line amendment produced SHA-256
`3f5c697fa91d7cf6fd612b6f6f0c6d37460b78a26f292e2b241e35a775a3b56a`. Three targeted fresh
reviews—security/specification, executability, and minimality/portability—each
returned READY with 0 Critical, 0 Important, and 0 Minor findings. The
amendment aligns the plan with the reviewed Task 1 implementation and does not
broaden the locked-build or trust boundary.

## Task 2 interface amendment

Task 2 implementation and independent review exposed two stale interfaces in
the prior plan revision:

- `InstallRoots.discover` now requires explicit keyword-only
  `source_distribution_root` and `distribution_root` inputs and exposes those
  paths plus the exact derived `bundle_root`. This completes the literal
  Derived Paths table without turning receipt strings into path authority.
- The isolated fault driver now requires a closed `--fixture-kind` and
  `--preimage` descriptor alongside `--point`, validates the exact Task 8
  applicability matrix before CLI import, and keeps present/absent swap and
  publish variants mutually exclusive. The Task 10 crash example supplies
  `extension_tree` and `absent` explicitly.

The amendment produced the current SHA above. Three targeted reviews—security
and specification, executability, and minimality/portability—each returned
READY with 0 Critical, 0 Important, and 0 Minor findings. The security review
mechanically matched all 17 valid fixture variants and 85 point mappings to the
Task 8 matrix and confirmed the implementation at `e65d446` matches the plan.

## Task 3 transaction-table amendment

Task 3 implementation and repeated independent review tightened several stale
transaction descriptions in the prior plan revision:

- Every reverse path now quarantines the installer postimage at deterministic
  recovery path `R`; present-preimage recovery includes the explicit `RS`
  restore-staged row before completing the restore.
- `RESTORING` accepts the postimage at either `S` or `R`, while terminal
  rollback rows require absent recovery and keep the semantic state closed.
- Cleanup is specified as a retryable deletion prefix, and every completed
  crash prefix redrives the required parent-directory `fsync` operations.
- Filesystem names reject embedded NUL bytes before reaching native rename
  calls.
- The present-preimage `S -> R` quarantine transition has the explicit
  `after_KIND_restore_move` failpoint used by the closed Task 8 matrix.

The amendment and its narrow fault-matrix regression test at `1ab52cde`
produced the current SHA above. Three targeted fresh reviews—security and
specification, executability, and minimality/portability—each returned READY
with 0 Critical, 0 Important, and 0 Minor findings. The security review
mechanically matched all 17 valid fixture variants and all 89 point mappings
to the Task 8 matrix and confirmed there is no direct deletion of staged
postimages during rollback.

## Task 4 Codex semantic-rollback amendment

Task 4 implementation and three independent review passes exposed a closed-
schema mismatch for semantic rollback when the original Codex config was
absent but the user later added foreign configuration:

- `codex_file` now permits the same C1-C4 semantic receipt rows for present
  and absent preimages, with C1-C3 `recovery_image=pre`, C4 recovery absent,
  `rollback_intended` present throughout, and `rollback_displaced` present
  from C2 onward.
- Present and absent forward/recovery prose now distinguishes the protected
  recovery object from an absent deterministic recovery reference.
- Task 4 exposes `CodexRollbackContext`; Task 8 owns the synchronous complete-
  receipt callback and the exact bidirectional mapping between C1-C4 and
  receipt action states.
- Task 8's closed semantic failpoint matrix covers present and absent
  preimages and explicitly owns the corresponding `fault_driver.py` update.

The reviewed Task 4 implementation ends at `107b7d9`. The amendment produced
the current SHA above. Three targeted reviews—security/specification,
executability/testability, and minimality/portability—each returned READY with
0 Critical, 0 Important, and 0 Minor findings.

## Task 5 Darwin discovery and staging amendment

Task 5's implementation and live disposable probes corrected stale assumptions
about Darwin lifecycle evidence and made its staging boundary explicit:

- Listener `lsof` evidence is exactly one `p/c/u` process header plus one
  `f/n` socket record; device/inode identity comes from the PID's separate
  strict `txt` query.
- The first `txt` record identifies the process executable. Later nonmatching
  images are allowed, while later exact selected identities remain ambiguous.
- Staging requires a retained current-UID-owned parent, fd-relative/no-follow
  installer writes, parent fsync, and recaptured Blender-produced outputs.
- ZIP indexing rejects noncanonical aliases and accepts only normalized file
  `0644` and directory `0755` entries before any runner call.

The reviewed implementation ends at `7203316`. The amendment produced the
current SHA above. Under the simplified process requested by the user, one
combined adversarial security/specification/executability/minimality review
returned READY with 0 Critical and 0 Important findings.
