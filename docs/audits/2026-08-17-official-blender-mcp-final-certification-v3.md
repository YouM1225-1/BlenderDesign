# Official Blender MCP final distribution certification v3

> Historical certification for `6912a6f2f5c87ec0b0d40f7aa1a3cd5f958c4c56`.
> Superseded by `2026-08-18-official-blender-mcp-final-integration-certification.md`.
> Preserve this report as evidence; do not use its candidate as the current installer
> authorization input.

Status: **PASS**

Certification date: 2026-08-17

## Authorization boundary

- Final candidate and installer authorization input:
  `6912a6f2f5c87ec0b0d40f7aa1a3cd5f958c4c56`.
- Bundled upstream source: `887205197f35a01cabaf7fb9f18ff5cd56b40a32`.
- Plugin source version: `1.0.0+codex.20260817154200`.
- Python input: an absolute path resolving to Python `3.13.13`; its canonical target
  must be a regular executable owned by the current operator or root and must not be
  group/world-writable.
- uv: `0.12.2`.

This report is added by a separate audit-only certification commit. That commit must
have `6912a6f2f5c87ec0b0d40f7aa1a3cd5f958c4c56` as its only parent and may change only
this report plus the superseded notice in the v2 certification. The audit commit cannot
certify itself and is not an installer authorization input. Use a clean detached
checkout whose `HEAD` exactly equals the final candidate and set:

```text
EXPECTED_DISTRIBUTION_COMMIT=6912a6f2f5c87ec0b0d40f7aa1a3cd5f958c4c56
PYTHON_BIN=<absolute path resolving to the certified Python 3.13.13 executable>
```

The earlier authorization candidates `53b6488c85b77520a5abe538527b26110e4684a1`,
`5b0599a4f61ed687605bb16ef6d5fed99bed7e6b`,
`f240166030e916265f0b5796ea99274897e6cff2`, and
`2b1f1f4172602f899161e961cff35133702367fe` remain historical evidence only.
The intermediate cleanup candidate `696b13efcb1fc76b8bcc5ec205ddd499253c245d`
was rejected during review and is not an authorization input.

## Final candidate gates

- RED run with the final table-driven regression applied to parent candidate
  `696b13efcb1fc76b8bcc5ec205ddd499253c245d`: `1 failed`. Pytest stopped that
  single test item at its first scenario, so the remaining in-item scenarios were not
  executed. The first failure proved that stdout/stderr pipes were not explicitly
  closed.
- GREEN run of that same table-driven test item: `1 passed`; all eight deterministic
  cleanup scenarios executed, covering terminate/kill exit races, both bounded waits,
  non-`ProcessLookupError` OSError handling, explicit pipe closure, descriptor closure,
  and successful reap where the fake child reported completion.
- Focused GREEN run: `97 passed`, including the Codex adapter suite and the three
  previously intermittent semantic rollback cases.
- Closed fault matrix: `143 passed in 107.56s`.
- Complete distribution suite: `773 passed, 1 skipped in 168.91s`.
- Plugin contract suite: `49 passed`.
- Ruff: `All checks passed!`.
- Skill validator: `Skill is valid!`.
- Plugin validator: passed using isolated `PyYAML==6.0.3`.
- `git diff --check`: passed.
- `git show --check` for the final code candidate: passed.
- Skill size: 499 lines; skill SHA-256
  `eac302473f96d05acab15617b2d66614f13c9a2f54353b43210c0f8d4a49ccc5`.
- Plugin manifest SHA-256
  `903a034cb9cfd3c6a67e2605a3f028a9a6adbdf5f6e4e4a589ff3f325697e27f`.

The final helper cleanup preserves the existing two-second operation deadline and two
bounded 0.25-second reap waits. A terminate or kill `ProcessLookupError` means the child
won the exit race, but cleanup still performs the final bounded wait. Other OSError
failures and a second wait timeout become a redacted `InstallerError`. Both subprocess
output pipes are explicitly closed on every covered cleanup path, and deterministic
fakes verify descriptor closure and successful reap where the child reports completion.

The plugin-creator cachebuster helper changed only the source manifest version suffix.
No live marketplace projection, plugin cache, Codex configuration, or Blender state was
read or changed. No production install, reinstall, verify, rollback, Blender
launch/termination, or scene operation ran for this candidate. In particular,
`1.0.0+codex.20260817154200` is certified source metadata, not a claim that the live
plugin was updated.

## External gates

- `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN` — no disposable credential supplied.
- `SECOND_MAC_CANARY_STATUS: NOT_RUN` — requires an independent physical Mac.
