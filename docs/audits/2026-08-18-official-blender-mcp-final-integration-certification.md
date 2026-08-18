# Official Blender MCP final integration certification

Status: **PASS**

Certification date: 2026-08-18

## Authorization and audit boundary

- Final code candidate and installer authorization input:
  `850d6c419f1eb206451c4f68c10267242d7c24c5`.
- Bundled audited upstream source:
  `ecdff98d6387440fb10d1ad71d35db25984e38e5`.
- Bundle version: `1.0.0+ecdff98d6387`.
- Plugin source version: `1.0.0+codex.20260818004806`.
- Certified Python: `3.13.13`; uv: `0.12.2`; Blender build/validation CLI:
  `5.2.0 LTS`; setuptools: `80.9.0`.

This report is added by a separate audit-only commit. That commit has
`850d6c419f1eb206451c4f68c10267242d7c24c5` as its only parent and changes only
this report plus the superseded notice in the historical v3 certification. The audit
commit cannot certify itself and is not an installer authorization input. Use a clean
detached checkout whose `HEAD` exactly equals the code candidate and set:

```text
EXPECTED_DISTRIBUTION_COMMIT=850d6c419f1eb206451c4f68c10267242d7c24c5
PYTHON_BIN=<absolute path resolving to the certified Python 3.13.13 executable>
```

All earlier distribution candidates and certification commits are historical evidence
only. The 2026-08-17 v3 authorization candidate is explicitly superseded.

## Scope A dependency contract

Scope A supports MCP SDK versions `1.28.1 <= version < 3` in upstream and independent
wheel installations. At minimum, both MCP `1.28.1` and `2.0.0` are exercised. One
compatibility boundary, `blmcp.mcp_compat`, preserves the same 26-tool wire names,
descriptions, input schemas, and annotations across the tested versions.

The upstream source declaration is frozen byte-for-byte as:

```text
mcp[cli]>=1.28.1,<3
```

setuptools `80.9.0` deterministically serializes that semantically identical requirement
in wheel `METADATA` as:

```text
mcp[cli]<3,>=1.28.1
```

The builder rejects every other source spelling and every other wheel spelling; it does
not use an unordered or existence-only dependency check. The supported installer remains
reproducible by retaining an exact, hash-locked `mcp==1.28.1` runtime lock. That installer
pin does not narrow the upstream or independently installed wheel contract.

## Audited upstream evidence

The retained upstream audit at `ecdff98d6387440fb10d1ad71d35db25984e38e5` records:

- Python `3.10.20` and `3.13.14`, each with MCP `1.28.1` and `2.0.0`:
  4 metadata tests and 43 server tests passed in every matrix cell.
- The two MCP versions produced byte-identical 18,831-byte canonical tool metadata;
  all 26 tools carried annotations.
- Both MCP environments passed the complete 179-test non-Blender suite.
- Real Blender 5.2 background: 44/44; foreground: 44/44; interactive: 45/45.
- Real-Blender tests used dynamically reserved ports and cleaned only their owned PIDs.
  The user's Blender PID 76193 and localhost port 9876 listener remained untouched.
- Ruff, MyPy, Vulture, Pylint, license, ASCII, and namespace gates passed with the
  upstream repository's pinned toolchain.

The snapshot repair preserves the live Blender lexical filepath namespace, binds device,
inode, size, mtime, ctime, and dirty state across phases, uses a background copy for a
stable clean live file, and fails closed on state transitions or deadline expiry.

## Reproducible distribution build

A fresh clean detached clone was created from the local reviewed bare upstream object
store and pinned exactly to `ecdff98d6387440fb10d1ad71d35db25984e38e5`. Two formal
builder runs succeeded. Each run independently created and compared two Git archives and
two payload builds before publication. The five outputs from the two formal runs were
byte-identical.

The wheel contained 4,440 upstream package source/data files and the extension contained
9 upstream source files; every corresponding archive member was byte-identical to the
detached source. Archive scans rejected duplicate, absolute, traversal, backslash,
drive-qualified, symlink, and special entries. Files were mode `0644`, directory entries
were mode `0755`, all five top-level artifacts were regular mode-`0644` files, and secret
marker scans passed. The manifest, checksum file, 26-tool catalog, exact runtime lock,
extension validation, and source/wheel metadata gates passed.

Reproducible artifact SHA-256 values:

```text
708475ca7710d152d37afe0d65564e6d370e37431b9e47cfd7c94a9f8e9a6614  SHA256SUMS
36a48761cf4e845892eb73bd5d1a2ffbed7fc184199aa2def8f655f443b77971  manifest.json
f878622a8e06fec15f00ade57ceeb0a2d498103b5ed9b499e8cff0cd36c11b33  blender_mcp-1.0.0-py3-none-any.whl
6da5dc0297777af3b2faad793916d36b42f62fd47756c30d820e936903bced0d  mcp-1.0.0.zip
5133f4c4ca9ab5e48c1775548ca98fe914f722dfbf236cfae7047c1c2e117423  runtime-requirements.lock
```

## Installer integration evidence

The installer diagnosis corrected the original attribution: whole-file
`userpref.blend` receipt drift does not feed `exact`; the observed failure was the
managed `online_access=false` semantic. Inspect now reports all 13 exact inputs plus
extension-file and four preference subchecks. Managed drift remains fail-closed, payload
corruption still makes the installation inexact, and exact pre/post file images remain
unchanged for rollback and stale-snapshot protection.

The independent SafeRoot repair stops treating directory mtime as open-object identity
while still binding type, device, inode, owner, and mode. Tree snapshot stability checks
continue to include mtime. Before final artifact integration, this installer candidate
passed 791 tests with one guarded port-9876 skip. The final integrated candidate passed:

- complete distribution: 800 passed, 1 skipped in 166.89 seconds;
- closed fault matrix: 143 passed, 44 deselected in 105.12 seconds;
- plugin contract: 49 passed in 12.27 seconds;
- Ruff: all checks passed;
- MyPy: no issues in 22 source files;
- built-in compilation: 12 distribution/installer sources;
- plugin validator and Skill validator: passed;
- `git diff --check` and candidate `git show --check`: passed.

The sole skip is the explicit disposable listener probe because localhost port 9876 was
already occupied by the user's Blender. It is not a failed installer assertion.

Skill SHA-256:
`fc17556b2720c441b1714a69f42daf99b22351b2037bec7beaa5db01a1f1bd0f`
(504 lines). Plugin manifest SHA-256:
`a11dc98375b3e4ad67cd2f540d56ea1015aa0879095b3c17a744204c8c5fe9e0`.

## Operational boundaries and residual gates

The plugin-creator cachebuster helper ran exactly once after code, Skill, and artifacts
were final. It changed only the plugin source version suffix. No marketplace file was
hand-edited and no live plugin reinstall was performed.

This integration did not install, repair, verify, or roll back the production profile;
did not connect to or mutate a live Blender scene; and did not start or terminate the
user's Blender. The builder used Blender's non-scene extension build/validate CLI only.

- `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN` — no disposable credential supplied.
- `SECOND_MAC_CANARY_STATUS: NOT_RUN` — requires an independent physical Mac.
