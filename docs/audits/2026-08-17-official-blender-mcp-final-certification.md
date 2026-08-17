# Official Blender MCP final distribution certification

Status: **PASS**

Certification date: 2026-08-17

## Authorization boundary

- Final candidate and installer authorization input:
  `f240166030e916265f0b5796ea99274897e6cff2`.
- Bundled upstream source: `887205197f35a01cabaf7fb9f18ff5cd56b40a32`.
- Plugin version: `1.0.0+codex.20260817141107`.
- Python input: absolute path resolving to the regular, executable,
  non-group/world-writable Python `3.13.13` target.
- uv: `0.12.2`.

This report is added by a separate audit-only certification commit. That commit must
have `f240166030e916265f0b5796ea99274897e6cff2` as its first parent and may change only
this report plus the superseded notice in the historical D4 certification. The
certification commit cannot certify itself and is not an installer authorization input.
Use a clean detached checkout whose `HEAD` is exactly the final candidate above and set:

```text
EXPECTED_DISTRIBUTION_COMMIT=f240166030e916265f0b5796ea99274897e6cff2
PYTHON_BIN=<absolute path resolving to the certified Python 3.13.13 executable>
```

The old D4 trust root `53b6488c85b77520a5abe538527b26110e4684a1` and the
post-install remediation root `5b0599a4f61ed687605bb16ef6d5fed99bed7e6b` remain
historical evidence. Neither supersedes this final candidate.

## Final candidate gates

The clean candidate tree passed:

- `771 passed, 1 skipped` in the complete `tests/distribution` suite.
- `48 passed` in the focused plugin contract suite.
- Ruff on installer scripts, the distribution builder, and distribution tests.
- Skill and plugin validators using isolated `PyYAML==6.0.3`.
- `git diff --check a31d00e09556..f240166030e916265f0b5796ea99274897e6cff2`.
- `git show --check` for the final code commit.
- Skill size: 499 lines; skill SHA-256
  `dbd8bb47a6225160e5c9530104bbcc47461dbbcb3e8595ab0fdcd7f20ee7eb0a`.
- Plugin manifest SHA-256
  `77cd44e63c98032a4efc556fc89cf93fa760a20af8fd21213709c1b180cc1dda`.

The Python bootstrap regression first failed six focused cases. The final contract now
requires an explicit absolute `PYTHON_BIN`, canonicalizes accepted symlinks with
`realpath`, rejects a missing/relative/unsafe target and any version other than
3.13.13, and reuses the canonical path across cwd changes and fresh shells. All four
installer launchers still pass the same canonical path through uv's explicit
`--python` argument. No live configuration was read or changed, and no production
install or rollback ran for this final candidate.

## Prior operational evidence retained without promotion

Before the final Python-contract change, commit
`5b0599a4f61ed687605bb16ef6d5fed99bed7e6b` passed `766 passed, 1 skipped` plus both
validators and Ruff. Its persistent marketplace application report is retained at:

```text
/Users/yeminjie/Developer/BlenderDesign/.superpowers/sdd/d5-marketplace-apply-report.md
SHA-256 3b2996f4ca02658497f317bfb4ecd0771238952719c7f809b5c5ca89256e8965
```

After Codex restart, the same historical candidate passed installer `verify` with
`parsed_codex=true`, `effective_codex=true`, `mcp_catalog=true`,
`blender_read_only=true`, and `tool_count=26`; old MCP/app-server processes were gone,
the persistent projection/cache matched, and receipt/runtime/launcher/config hashes
were unchanged. The corrected report is retained at:

```text
/Users/yeminjie/Developer/BlenderDesign/.superpowers/sdd/d5-postrestart-verify-report.md
SHA-256 a57aebaf591adf611f9ac85efb8922b998093bdb571dfed325127d2c444836df
```

That report correctly records the installed skill as 499 lines. Cache comparison means
path/type/content equality; it separately verifies that projection and cache directory
and regular-file permissions are non-group/world-writable. It does not claim exact
mode equality.

These operational results demonstrate the persistent-registration and restart lifecycle
at the immediately preceding candidate. They are not represented as a production apply
of `f240166030e916265f0b5796ea99274897e6cff2`; this final task intentionally performed
no production install, rollback, or live-config read.

## External gates

- `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN` — no disposable credential supplied.
- `SECOND_MAC_CANARY_STATUS: NOT_RUN` — requires an independent physical Mac.
