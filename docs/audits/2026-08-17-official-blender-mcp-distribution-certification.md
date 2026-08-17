# Official Blender MCP distribution certification

Status: PASS

Certification date: 2026-08-17

## Trust roots

- Certified distribution commit: `53b6488c85b77520a5abe538527b26110e4684a1`
- Bundled upstream source commit: `887205197f35a01cabaf7fb9f18ff5cd56b40a32`
- Bundle version: `1.0.0+887205197f35`
- Upstream source object repository used for the reproducibility check:
  `/Users/yeminjie/Developer/BlenderDesign/.worktrees/blender-mcp-upstream.git`
- Upstream source ref at certification:
  `refs/heads/codex/background-hardening`

The certification evidence commit that adds this report is audit-only. It is not the
distribution trust root. Installation must use a clean detached checkout of the exact
certified distribution commit above.

## Environment

- macOS arm64
- Python `3.13.13`: `.venv/bin/python`
- uv `0.12.2`: `/Users/yeminjie/.local/bin/uv`
- Blender `5.2.0 LTS`: `/Applications/Blender.app/Contents/MacOS/Blender`

No Codex or Blender production configuration was read or modified, and no installation
was performed.

## Distribution test and repository gates

Commands:

```bash
UV=/Users/yeminjie/.local/bin/uv .venv/bin/pytest -q tests/distribution
git diff --check a31d00e..HEAD
.venv/bin/ruff check \
  plugins/blender-mcp-installer/scripts \
  scripts/build_official_blender_mcp_distribution.py \
  tests/distribution
git status --short
```

Results:

- `754 passed, 1 skipped in 155.81s`; no distribution test failed.
- `git diff --check` passed.
- Ruff reported `All checks passed!`.
- The implementation worktree was clean before this report was created.

An earlier pytest invocation omitted the required `UV` environment assignment and
reported three environment-only failures (`751 passed, 1 skipped`). Re-running the
complete suite with the specified absolute `UV` value passed. No source change was made
in response.

## Artifact, manifest, permission, and security gates

Commands included:

```bash
(cd plugins/blender-mcp-installer/artifacts && shasum -a 256 -c SHA256SUMS)
.venv/bin/python -c \
  'from pathlib import Path; from scripts.build_official_blender_mcp_distribution import _validate_candidate; _validate_candidate(Path("plugins/blender-mcp-installer/artifacts"), Path("/Applications/Blender.app/Contents/MacOS/Blender"))'
stat -f '%Sp %Lp %N' plugins/blender-mcp-installer/artifacts/*
git ls-tree HEAD plugins/blender-mcp-installer/artifacts/
```

Results:

- `manifest.json`, wheel, extension ZIP, and runtime lock matched `SHA256SUMS`.
- The closed manifest parsed and bound the exact upstream commit, three artifacts, and
  the ordered 26-tool catalog.
- Blender accepted the extension archive validation command.
- All five tracked artifact files were regular mode-`0644` files in both the worktree
  and Git tree.
- Wheel and extension ZIP scans found no duplicate, absolute, traversal, backslash, drive,
  symlink, or special-file entries. All archive entries had normalized regular-file
  mode `0644` (4,444 wheel entries and 9 extension entries).
- Common private-key, AWS access-key, and GitHub-token marker scans were clean in both
  archives and tracked distribution sources.

Artifact hashes:

```text
c94a2e6d9cd61189b5bc566c33dcc77e9f658447ff0d3f73735ba64a631cbfe7  SHA256SUMS
baa03c05bc4f500f316cfa36d8bca3b8b9f9efa476cd81903ab05211f6c763ec  manifest.json
bb156c407b7b2bbb2e4f8539aac1e583063b9de5a8005c501d0199c6a0ad4f07  blender_mcp-1.0.0-py3-none-any.whl
d3ca17fb1994127e6d34f3bb8f9af540e435f323501bee106bd4c58db1a5c800  mcp-1.0.0.zip
5133f4c4ca9ab5e48c1775548ca98fe914f722dfbf236cfae7047c1c2e117423  runtime-requirements.lock
```

## Reproducibility gate

A fresh detached clone from the local reviewed upstream object repository was pinned to
`887205197f35a01cabaf7fb9f18ff5cd56b40a32`. It was clean before building. The command was:

```bash
UV=/Users/yeminjie/.local/bin/uv .venv/bin/python \
  scripts/build_official_blender_mcp_distribution.py \
  --source /private/tmp/blender-mcp-d4-cert.7XAOoe/source-local \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --uv /Users/yeminjie/.local/bin/uv \
  --output /private/tmp/blender-mcp-d4-cert.7XAOoe/rebuilt
```

The builder's two independent source archives produced byte-identical wheel and extension
payloads. It reported `tools=26` and the exact pinned toolchain. `cmp` and SHA-256 then
proved the rebuilt `SHA256SUMS`, manifest, wheel, extension ZIP, and runtime lock were all
byte-identical to the committed distribution artifacts. `_validate_candidate` accepted
the rebuilt output.

The official public remote advertised main `4309a39646e644261624bfcd2bca669b343b7621`
at certification time and did not advertise or permit a direct fetch of the reviewed
hardening commit. Therefore the reproducibility check used the retained local reviewed
source object/ref above. D5 does not fetch upstream source; it must consume only the
certified distribution commit and committed checksums. This provenance limitation must
remain visible and must not be "fixed" by substituting public main.

## Installer trust-gate acceptance and D5 input

A fresh detached worktree at the certified distribution commit passed
`verify_distribution_checkout` and `open_verified_bundle` with a clean scoped status,
trusted committed checksum bytes, bundle `1.0.0+887205197f35`, and 26 tools.

```text
EXPECTED_DISTRIBUTION_COMMIT=53b6488c85b77520a5abe538527b26110e4684a1
DISTRIBUTION_REPOSITORY=/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
UV_BIN=/Users/yeminjie/.local/bin/uv
PYTHON_BIN=/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install/.venv/bin/python
```

D5 must create or use a clean detached source checkout whose `HEAD` equals
`EXPECTED_DISTRIBUTION_COMMIT`; the branch head containing this audit-only report is not
an acceptable substitute. D4 performed no install.
