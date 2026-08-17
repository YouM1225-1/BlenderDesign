# Official Blender MCP post-install remediation audit

Date: 2026-08-17  
Verdict: **APPROVED — 0 Critical, 0 Important, 0 Minor**

## Reviewed boundaries

- Upstream Blender MCP commit:
  `98d1624b39d8e35baf1ae8ce0c1d13a2c321c9a4`.
- Distribution implementation commit:
  `501360555cb740709109b491837bf731a67567d1`.
- Default-authorization policy commit:
  `d61bc09f1789b60ff560233198b3148eed38d8a2`.
- Bundle version: `1.0.0+98d1624b39d8`.
- Codex plugin version: `1.0.0+codex.20260817043311`.
- Formal receipt:
  `/Users/yeminjie/.local/state/blender-mcp-installer/receipts/4a87a07b-e512-4f62-a0b5-ad7a61c1eeda.json`.

## Findings and disposition

1. **Large interactive responses were truncated.** The accepted Blender socket is
   non-blocking, but the old code called `sendall`, swallowed `BlockingIOError`, and
   closed the connection. A delayed-reader/4 KiB-buffer regression reproduced a
   truncated 1 MiB JSON frame. The server now retains an encoded `memoryview`, sends
   available bytes on each timer tick, and closes only after the null-delimited frame
   is complete. Deferred responses use the same queue. Blocking background mode is
   unchanged.
2. **The local Codex plugin could reuse stale version `1.0.0`.** The supported
   plugin-creator cachebuster generated `1.0.0+codex.20260817043311`; the normal Codex
   profile now has exactly that version installed and enabled.
3. **The marketplace source was a temporary path.** A disposable lifecycle probe
   installed the plugin, removed only its copied marketplace source, and then proved
   that `plugin list` still reported it installed/enabled and that the cached skill
   remained present. The normal marketplace was nevertheless moved to the current
   repository worktree to make later updates straightforward.
4. **The three post-acceptance provenance fixes lacked a final combined gate.** The
   current clean implementation passed the complete project and distribution gates.
5. **The operator requested standing authorization.** The skill now treats extension
   install/enable, Online Access, localhost bridging, and arbitrary-Python tools as a
   standing default-allow policy. It no longer asks four per-install questions, but it
   still passes all four explicit CLI flags. The CLI remains fail-closed when invoked
   without them. The legacy receipt field is documented as an active-flags marker, not
   evidence that four prompts were shown.

## Mechanical evidence

- Upstream RED: delayed reader plus 4 KiB send buffer returned a frame without the
  terminating null byte.
- Upstream GREEN: socket regression `1/1`; interactive default area screenshot and
  deferred response `2/2`; other upstream suites `1 + 7 + 53 + 41` passed.
- Real Blender 5.2.0 returned both the default area screenshot and default full-window
  screenshot as complete images after installation.
- Two fresh distribution builds were byte-identical for `SHA256SUMS`, manifest,
  wheel, extension ZIP, and runtime lock. All four checksum entries passed.
- Bundle/plugin focused tests: `85 passed`.
- Full distribution suite: `744 passed, 1 skipped`.
- Clean `scripts/checks.sh`: project `369 passed`, distribution `744 passed,
  1 skipped`, `ALL CHECKS PASSED`.
- Ruff checks, canonical mypy (`22 source files`), plugin validator, skill validator,
  and `git diff --check` passed. The optional validator path in `checks.sh` cannot use
  system Python because PyYAML is not installed; the same validator passed in an
  isolated fixed-dependency invocation, so no system package was added.
- The policy-only change passed all `31` plugin contract tests, both validators, Ruff,
  and `git diff --check`; the full runtime suite was not repeated because no runtime or
  installer code changed.
- Formal changed install returned `requires_blender_start`; after the operator started
  Blender, verification passed parsed Codex policy, effective Codex configuration,
  exact MCP handshake/catalog, and the Blender read-only call with `tool_count=26`.
  The same verification passed again after both large screenshot calls.

## Adversarial review notes

- Response writes remain non-blocking and bounded by the existing client idle timeout;
  one slow client does not block the Blender main thread.
- Immediate and deferred responses share one completion rule, avoiding a second
  partial-write path.
- The new artifact manifest is closed over the reviewed upstream commit and the
  installer rejects the previous bundle version.
- The default-allow policy uses declarative statements; the old consent prompt and
  `May the installer` question forms are contractually absent.
- No unrelated project, normal Blender profile, or `.blend` file was modified during
  the isolated build and plugin lifecycle probes.
- Repository-wide `ruff format --check` still reports the previously documented
  whole-file formatting drift in bundle/build test files. The changed lines pass Ruff;
  no unrelated bulk formatting was performed.

## External gates

- `SECOND_MAC_CANARY_STATUS: NOT_RUN` — requires a physically independent Mac and
  release operator.
- `LOCAL_LLM_INVOCATION_STATUS: NOT_RUN` — no independently supplied disposable API
  credential was provided. Normal Codex credentials were not copied.

These external gates do not invalidate this Mac's implementation and installation
acceptance; they remain explicit release-portability evidence still to be collected.
