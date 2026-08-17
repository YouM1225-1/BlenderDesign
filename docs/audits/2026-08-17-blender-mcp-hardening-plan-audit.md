# Blender MCP Hardening Plans — Adversarial Audit

Date: 2026-08-17
Scope: background Blender routing, process/result containment, Retina coordinate normalization, deterministic distribution, transactional rollout, and duplicate-process lifecycle attribution.

## Verdict

The three-plan sequence is executable and appropriately scoped after inline corrections. It is approved for implementation with two operator gates: a real interactive Retina screenshot check and an operator-confirmed production restart/installer verification. It must not be represented as a hostile-code sandbox.

Execution order is mandatory:

1. `2026-08-17-blender-mcp-background-runtime-hardening.md`
2. `2026-08-17-blender-mcp-retina-coordinate-normalization.md`
3. `2026-08-17-blender-mcp-hardening-distribution-rollout.md`

The first plan emits `BACKGROUND_COMMIT`; the second consumes it and emits the combined `SOURCE_COMMIT`; the third consumes that exact commit and emits `EXPECTED_DISTRIBUTION_COMMIT`.

## Threat and failure model

In scope:

- Accidental or malformed tool code forging stdout result markers.
- Nonzero Blender exit after emitting apparent success.
- Unbounded stdout, stderr, or JSON results.
- Timeout leaving ordinary descendants alive.
- Blender parent exit while a child keeps inherited output pipes open.
- Concurrent background requests choosing the same temporary `.blend` name.
- Snapshot creation producing `.blend1` instead of the intended path.
- Arbitrary background code accidentally saving the caller's source file.
- Trusted file-summary tools unexpectedly including unsaved live state.
- Outer MCP timeout expiring before inner Blender cleanup.
- Retina screenshots sometimes using physical pixels and sometimes logical pixels.
- A stale bundled wheel passing source-only tests.
- Two active Codex sessions being misdiagnosed as one leaking Blender add-on.

Explicitly out of scope:

- Preventing deliberately hostile Python from reading process arguments, traversing the filesystem, opening the source path explicitly, or modifying other user files.
- Authenticating the localhost arbitrary-Python bridge, per operator instruction.
- Repairing Codex host process ownership from Blender add-on code.
- Providing equivalent descendant process-group semantics on Windows; the acceptance platform is macOS arm64.

## Findings and corrections

### A1 — Critical: fast output overflow could bypass the planned cap

Original defect: the supervisor checked overflow only while `proc.poll() is None`. A process could print more than 1 MiB and exit before the polling loop observed the event, then be returned as success.

Correction: the background plan now rechecks stdout/stderr overflow events after reader completion. Its 2 MiB fast-print regression exercises the process-exited path.

Status: corrected inline.

### A2 — Critical: a child holding inherited pipes could outlive a successful Blender parent

Original defect: joining non-daemon readers after the parent exited could leave the MCP process blocked by a child that inherited stdout/stderr. The first termination sketch returned immediately when the parent had already exited, so it could not kill the remaining process group.

Correction: the plan adds a parent-exited/child-sleeping regression, makes readers daemon safety nets, detects pipes that remain open, and sends termination to the POSIX process group even after the leader exits. The process group receives SIGTERM, a two-second grace period, then SIGKILL when still present.

Status: corrected inline.

### A3 — High: snapshot tests used `eval` and live save success was incompletely checked

Original defect: planned tests parsed generated code with `eval`, and the live dirty-file branch accepted any top-level `status == "ok"` even if Blender returned `saved: false`.

Correction: tests use `ast.literal_eval`; implementation checks that the response result is a dict and `saved is True`.

Status: corrected inline.

### A4 — High: real-Blender test target named a nonexistent class

Original defect: the planned command targeted `TestBackground`, but upstream defines `TestBackgroundServer`.

Correction: all three focused integration targets now use `TestBackgroundServer`.

Status: corrected inline.

### A4b — High: a reachable live server error could silently discard unsaved state

Original defect: the first snapshot draft treated a non-`ok` or malformed live state response like an unavailable server and fell back to the on-disk file. That could execute against stale disk state while Blender was reachable and dirty.

Correction: only `ConnectionError` permits disk fallback. A reachable server returning an error or malformed state now raises, and a regression asserts that background snapshot creation is not attempted.

Status: corrected inline.

### A5 — High: the prior Retina fast path was dimensionally inconsistent

Root cause: `_image_downscale_to_size_limit()` returned the original PNG before reading `context.preferences.system.pixel_size` whenever the file already fit the byte limit. A small Retina screenshot therefore remained in physical pixels, while a larger screenshot was converted to logical pixels. JSON area/window coordinates remained logical, so consumers saw a conditional 2x mismatch.

Correction: the Retina plan reads runtime `pixel_size` before the fast-path decision, skips resampling only at scales at or below 1.0, tests 1.0/1.5/2.0 with fake Blender modules, and compares real screenshot bounds with JSON logical bounds.

Status: corrected by a separate plan to preserve subsystem boundaries.

### A6 — High: current timeout ordering is invalid

Observed state: Codex outer `tool_timeout_sec` is 60 seconds, background Blender is 120 seconds, and the live socket was 300 seconds. The host can abandon work before either inner layer cleans up.

Correction: live and background inner deadlines become 120 seconds; process termination gets a two-second grace period; managed Codex outer timeout becomes 150 seconds. The 28-second remaining margin covers normal startup, serialization, and MCP response overhead.

Status: corrected across upstream and distribution plans.

### A7 — High: source fixes alone could leave the released wheel vulnerable

Original risk: distribution tests could pass against source while the committed wheel remained pinned to the old upstream commit.

Correction: the rollout creates a wheel-content test that opens the actual committed wheel and verifies result-file protocol, output caps, POSIX session start, private snapshots, direct disk summaries, Retina ordering, and both 120-second inner timeouts. The deterministic builder then atomically replaces the artifact set and checksum manifest.

Status: corrected inline.

### A8 — Medium: bundle version and upstream pin were duplicated

Original risk: the same 12-character version suffix appeared independently in manifest parser, builder, and tests, allowing drift during a pin update.

Correction: `BUNDLE_VERSION` derives from the single production `UPSTREAM_COMMIT`; builder and tests import it.

Status: corrected inline.

### A9 — Medium: numbered snapshots were race-prone and pre-creating the file was unsafe

Observed behavior: concurrent numbered-path selection returned the same `_mcp_0001` path. Conversely, pre-creating an empty `.blend` target made Blender create `.blend1`.

Correction: each job receives a unique temporary directory, while the `.blend` target itself remains nonexistent until Blender saves it. Cleanup is scoped to that job directory.

Status: covered by concurrency and existence assertions.

### A10 — Medium: “read-only” was conflating disk inspection and live synchronization

Observed behavior: synchronizing dirty state through `save_as_mainfile(copy=True)` runs `save_pre` and `save_post`, so it can cause external handler side effects even though the source `.blend` is not replaced.

Correction: the five trusted `_for_cli` summary tools inspect the exact on-disk file and never contact the live add-on. Only arbitrary CLI execution creates a private snapshot; dirty-live snapshot creation explicitly documents save-handler side effects and retains a destructive annotation.

Status: corrected in routing and documentation.

### A10b — Medium: the preferred split existed as an idea but not as agent routing policy

Original gap: changing tool implementations does not make an MCP client choose them correctly. Without startup guidance, an agent could still use live execution for disk-only reads or background execution for UI-dependent/current-scene work.

Correction: the upstream plan adds and tests explicit server instructions: `_for_cli` summaries are the default for supplied saved files, `execute_blender_code_for_cli` is for disposable batch work, live tools are for unsaved/UI state, and live arbitrary code is reserved for modifying the current open scene.

Status: corrected inline without adding an automatic router or new tool abstraction.

### A11 — Medium: result files stop accidental marker spoofing, not hostile code

Residual risk: code can deliberately inspect its process environment/arguments or filesystem and attempt to discover or corrupt the result path. It can also explicitly reopen the original source path if it knows it.

Disposition: accepted by scope. The plans describe the result file and private snapshot as reliability/integrity containment, never as hostile-code isolation.

Status: accepted residual risk.

### A12 — Medium: duplicate service processes were assigned to the wrong owner

Root cause analysis: two `blender-mcp` processes appearing alongside two complete sets of other MCP services indicates two Codex execution sessions, not a Blender add-on spawning MCP server processes.

Correction: rollout records PID/PPID ownership, closes only the extra Codex task/window normally, and verifies that its child exits while the primary remains. Persistence after session closure is filed against the Codex MCP host lifecycle; no Blender plugin shutdown workaround is added.

Status: correct component boundary; production observation still required.

### A13 — Low: the first isolated-installer command was not actually runnable under `python -I`

Observed during audit: invoking `scripts/install.py` directly with isolated mode raised `ModuleNotFoundError` because the sibling installer package was intentionally absent from `sys.path`. The current shell also does not expose `uv` through `PATH` even though the reviewed 0.12.2 binary exists at the standard local path.

Correction: the rollout now uses the installer skill's minimal `runpy` isolated runner, validates the existing `.venv` Python as 3.13.13, resolves/validates `uv` 0.12.2 explicitly, and passes the canonical paths to the installer. The isolated runner was smoke-tested with `install.py --help`.

Status: corrected and command-level verified.

## Gate matrix

| Property | Failing evidence before fix | Passing gate after fix |
|---|---|---|
| Stdout spoof | forged `__BLMCP_RESULT__` accepted | real result file value returned |
| Exit integrity | marker plus `os._exit(7)` accepted | nonzero exit always raises |
| Output bounds | 11 MiB accepted | 1 MiB stdout/stderr and 10 MiB result enforced |
| Fast overflow | exit raced polling | post-reader overflow recheck raises |
| Descendants | timeout left `/bin/sleep` | process group gone after grace |
| Inherited pipes | successful parent could hang readers | pipe-holding child terminated, call finishes |
| Snapshot uniqueness | two calls chose `_mcp_0001` | unique job directories and cleanup |
| Source isolation | arbitrary save could replace source | source hash unchanged; private path removed |
| Summary semantics | disk and unsaved live state conflated | `_for_cli` reads disk; live tool reads memory |
| Timeout ordering | 60 outer / 120 CLI / 300 live | 150 outer / 120 inner / 2 cleanup grace |
| Retina units | small 2x PNG skipped normalization | runtime 1.0/1.5/2.0 tests plus JSON bounds |
| Artifact freshness | old wheel could remain committed | wheel-content gate reads actual artifact |
| Rollback | production-only discovery | isolated install/rollback before real rollout |
| Process ownership | two sessions called plugin leak | PID/PPID and session-close acceptance test |

## Remaining operator gates

1. Run the interactive screenshot tests in a normal macOS Blender window on the available Retina display. A non-Retina hardware repetition is useful but not release-blocking because the 1.0 path is deterministically simulated and preserves the original bytes.
2. Before the real install, confirm the distribution worktree is clean and retain the exact 40-character `EXPECTED_DISTRIBUTION_COMMIT`.
3. Let the reviewed installer create the production receipt; keep it until the new runtime has passed live smoke calls.
4. Restart Blender and Codex normally when the installer requests it; do not automate force termination.
5. Record PID/PPID snapshots before and after closing the extra Codex session. Escalate a persistent orphan to the host lifecycle, not the Blender add-on.

## Plan-quality audit

- Scope: split into three plans because runtime supervision, raster coordinate normalization, and signed distribution rollout are independently reviewable subsystems.
- TDD: every behavior change begins with a focused failing test; generated artifacts have their own red/green gate.
- Exactness: file paths, signatures, code bodies, commands, expected results, commit boundaries, and value handoffs are explicit.
- Type consistency: `run_blender_cli() -> dict[str, object]`, `private_blend_for_cli() -> Generator[str, None, None]`, screenshot return schemas, and `ManagedCodexValues.tool_timeout_sec: float` remain consistent across plans.
- No speculative abstraction: standard-library process/tempfile primitives and one derived bundle-version constant replace the vulnerable paths.
- Rollback: source changes are isolated in an upstream worktree; distribution changes remain on the existing distribution branch; production mutation uses the already-reviewed transactional installer and receipt.

Final audit decision: proceed in the fixed order above. Stop rollout if any source gate, wheel-content gate, checksum gate, isolated rollback, or installer verification fails.
