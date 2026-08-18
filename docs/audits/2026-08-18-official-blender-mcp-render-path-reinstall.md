# Official Blender MCP render-path reinstall audit

Date: 2026-08-18 (Asia/Shanghai)

## Authorized inputs

- Distribution candidate: `36c3eba10e9ed7f1459b06e29fe157f6f52b7dca`
- Reviewed upstream source: `6498c372e7d88d2accea800d4d187c310c520474`
- Plugin version: `1.0.0+codex.20260818022238`
- Python: `3.13.13`
- uv: `0.12.2`
- Blender: `5.2`

The upstream change documents and tests the render-tool contract: caller paths are
reduced to a basename and output is written inside Blender MCP's private scratch
directory. The distribution was rebuilt from that exact upstream source.

## Build and test evidence

Two independent builds produced byte-identical artifact sets. The aggregate
artifact-set SHA-256 was
`933d0fa0abada647e253a00e371d398f2498e46917044db87067cede902a90b6`.

Artifact SHA-256 values:

- `SHA256SUMS`: `68db49172a04b7342b9f17d14961e0c19b47b6640c9d07614bce344097237dd9`
- Wheel: `95d763faf0fa25c52bcba64f600cbaf7aa5f9f879115b284247d64208267ef25`
- Manifest: `f7b9e5ff8b1e51dde824f566e3d6c4f976956b05ac5ef5aeaf9d508ea08c7217`
- Blender extension ZIP: `90c2331e088c9f35b75dcd39b8d1bf5639d02da4e4e0b04a0620e07b1d499496`
- Runtime lock: `5133f4c4ca9ab5e48c1775548ca98fe914f722dfbf236cfae7047c1c2e117423`

Validation results:

- Distribution suite: 800 passed, 1 skipped. The only skip was the test that
  requires TCP port 9876 to be free while the user's Blender owned that port.
- Focused bundle and plugin tests: 114 passed.
- Artifact checksums: 4 of 4 passed.
- Plugin and installer-skill validators passed.
- Ruff, MyPy, compilation, and diff checks passed in their documented scopes.

## Controlled production reinstall

The user closed Blender before installation. Port 9876 was confirmed free. A first
bootstrap attempt stopped before inspect or install because an extracted skill
block was empty; its failure trap removed the private trust directory and made no
production change.

A new fail-fast session then completed the reviewed workflow:

1. Privately bootstrapped the exact distribution commit and verified all four
   artifact checksums.
2. Prepared the persistent marketplace projection at
   `/Users/yeminjie/.local/share/blender-mcp-installer/marketplaces/official-blender-mcp/36c3eba10e9ed7f1459b06e29fe157f6f52b7dca`.
3. Inspected the existing installation and installed the candidate.
4. Created receipt
   `/Users/yeminjie/.local/state/blender-mcp-installer/receipts/836936ca-72b6-45f6-af9e-5d241cf545ad.json`
   with SHA-256
   `bde11f86c76e8d6c95ab8f581690d4489d343d2c3dc5d38a877fe581a7ff5814`.
5. Preserved marketplace recovery evidence at
   `/Users/yeminjie/.local/state/blender-mcp-installer/marketplace-recovery/registration.uktrrxap`.

The user then started Blender normally. The same trusted session completed
production verification:

- Parsed Codex configuration: true.
- Effective Codex configuration: true.
- MCP catalog: true.
- Blender read-only probe: true.
- Tool count: 26.
- Managed MCP tool timeout: 150 seconds.
- Blender PID 10843 was the sole listener on `127.0.0.1:9876`.
- The installed plugin was enabled at version
  `1.0.0+codex.20260818022238` and pointed to the persistent projection above.

The disposable marketplace smoke profile was removed after it passed. Private
trust roots created by this reinstall were removed. No arbitrary Python execution,
scene mutation, or scene save was used for verification.

## External gates

- Local LLM verification: not run; no credentials or endpoint were supplied.
- Second-Mac verification: not run; no second machine was in scope.

