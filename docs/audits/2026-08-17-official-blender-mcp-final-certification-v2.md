# Official Blender MCP final distribution certification v2

Status: **PASS**

Certification date: 2026-08-17

## Authorization boundary

- Final candidate and installer authorization input:
  `2b1f1f4172602f899161e961cff35133702367fe`.
- Bundled upstream source: `887205197f35a01cabaf7fb9f18ff5cd56b40a32`.
- Plugin version: `1.0.0+codex.20260817142503`.
- Python input: an absolute path resolving to Python `3.13.13`; its canonical target
  must be a regular executable owned by the current operator or root and must not be
  group/world-writable.
- uv: `0.12.2`.

This report is added by a separate audit-only certification commit. That commit must
have `2b1f1f4172602f899161e961cff35133702367fe` as its first parent and may change only
this report plus the superseded notice in the prior final certification. The audit
commit cannot certify itself and is not an installer authorization input. Use a clean
detached checkout whose `HEAD` exactly equals the final candidate and set:

```text
EXPECTED_DISTRIBUTION_COMMIT=2b1f1f4172602f899161e961cff35133702367fe
PYTHON_BIN=<absolute path resolving to the certified Python 3.13.13 executable>
```

The earlier authorization candidates `53b6488c85b77520a5abe538527b26110e4684a1`,
`5b0599a4f61ed687605bb16ef6d5fed99bed7e6b`, and
`f240166030e916265f0b5796ea99274897e6cff2` remain historical evidence only.

## Final candidate gates

- RED commit `90d9870` produced two expected focused failures: the owner contract was
  absent and a mismatched-owner sentinel shim executed.
- GREEN candidate `2b1f1f4172602f899161e961cff35133702367fe` rejected the shim
  before execution.
- Complete distribution suite: `772 passed, 1 skipped in 163.28s`.
- Plugin contract suite: `49 passed`; Python-bootstrap focus: `7 passed`.
- Ruff: `All checks passed!`.
- Skill validator: `Skill is valid!`.
- Plugin validator: passed using isolated `PyYAML==6.0.3`.
- `git diff --check a31d00e09556..2b1f1f4172602f899161e961cff35133702367fe`:
  passed.
- `git show --check` for the final code commit: passed.
- Skill size: 499 lines; skill SHA-256
  `eac302473f96d05acab15617b2d66614f13c9a2f54353b43210c0f8d4a49ccc5`.
- Plugin manifest SHA-256
  `af625a71434aba811194a21a16217e65cb17e3aa6ad3386d42cf8d7f248f42de`.

The bootstrap reads owner UID with `/usr/bin/stat -f %u` after canonical path/type
checks and before the first canonical-Python execution. A stat error, empty result,
non-decimal result, or owner other than the trust bootstrap's `OWNER_UID` or root (`0`)
fails closed. The version-mismatch regression uses only a private temporary 3.13.14
shim; it contains no user-specific path and cannot modify system state.

No live Codex configuration or Blender state was read or changed. No production
install, verify, rollback, Blender launch/termination, or scene operation ran for this
candidate.

## Retained operational and external evidence

The persistent marketplace and Codex-restart verification remain historical evidence
for `5b0599a4f61ed687605bb16ef6d5fed99bed7e6b`; they are not promoted as a production
apply of this v2 candidate. Their scope and fingerprints remain recorded in the prior
final certification.

- `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN` — no disposable credential supplied.
- `SECOND_MAC_CANARY_STATUS: NOT_RUN` — requires an independent physical Mac.
