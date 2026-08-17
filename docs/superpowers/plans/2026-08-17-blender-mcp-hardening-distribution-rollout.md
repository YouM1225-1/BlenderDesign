# Blender MCP Hardening Distribution Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the audited upstream background/Retina fixes into the official Blender MCP distribution, configure a valid outer timeout, prove the wheel contents, and roll it out with verifiable rollback state.

**Architecture:** Treat the final upstream Git commit as build input and the distribution Git commit as the installation trust root. Derive the bundle version from the pinned upstream commit, inspect the built wheel for the required hardening, keep the MCP host timeout above all inner deadlines, and use the existing transactional installer for staging, verification, and rollback.

**Tech Stack:** Python 3.13.13, pytest, Blender 5.2.0, `uv` 0.12.2, deterministic wheel/ZIP builder, transactional official Blender MCP installer, macOS arm64.

## Global Constraints

- Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install` on branch `codex/official-blender-mcp-install`.
- Begin from clean distribution commit `a31d00e`; stop if that worktree has unrelated modifications.
- Consume the exact 40-character `SOURCE_COMMIT` produced by `2026-08-17-blender-mcp-retina-coordinate-normalization.md`.
- The upstream source worktree must be clean and `git rev-parse HEAD` must equal `SOURCE_COMMIT` before building.
- Keep the internal background and live deadlines at `120.0` seconds; set Codex `tool_timeout_sec` to `150.0` seconds.
- Keep `startup_timeout_sec` at `20.0` seconds.
- Preserve all 26 MCP tool names and the four default-enabled authorization flags.
- Preserve Blender 5.2.0, Python 3.13.13, MCP SDK 1.28.1, localhost port 9876, and macOS arm64.
- Build from the pinned Git object, not the source worktree's uncommitted files or movable branch name.
- The built wheel must not contain stdout result markers and must contain the result-file protocol, process-group start, output caps, private snapshots, and runtime Retina scaling.
- Installation remains network-assisted for exact hash-locked wheels and must retain the existing transactional receipt/rollback model.
- Never modify the currently installed runtime directly; only the installer may publish it.
- Never force-close Blender or Codex. Operator-confirmed normal restart is an acceptance step, not an automated mutation.
- Duplicate `blender-mcp` processes are acceptable only when their parent processes belong to distinct active Codex execution sessions; Blender plugin code must not be changed to mask host lifecycle behavior.

---

## File Structure

- Modify `plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py`: derive `BUNDLE_VERSION` from the single upstream commit pin.
- Modify `scripts/build_official_blender_mcp_distribution.py`: use the derived bundle version in generated manifests.
- Modify `tests/distribution/test_bundle.py`: consume the production pin/version constants instead of duplicated literals.
- Modify `plugins/blender-mcp-installer/scripts/blender_mcp_installer/codex_adapter.py`: set the managed outer tool timeout to 150 seconds.
- Modify `tests/distribution/test_codex_adapter.py`: enforce the new exact timeout and drift rejection.
- Create `tests/distribution/test_bundled_runtime_hardening.py`: inspect the wheel payload and manifest for the audited runtime properties.
- Regenerate `plugins/blender-mcp-installer/artifacts/*`: deterministic wheel, extension ZIP, lock, manifest, and hashes.

---

### Task 1: Remove duplicated bundle-version literals

**Files:**
- Modify: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py:14-18,187-194`
- Modify: `scripts/build_official_blender_mcp_distribution.py:21-30,510-520`
- Modify: `tests/distribution/test_bundle.py:14-45`
- Test: `tests/distribution/test_bundle.py`

**Interfaces:**
- Consumes: current `UPSTREAM_COMMIT: str` pin.
- Produces: `BUNDLE_VERSION: str`, exactly `"1.0.0+" + UPSTREAM_COMMIT[:12]`, shared by manifest parsing, building, and tests.

- [ ] **Step 1: Add a failing assertion that the public bundle version derives from the pin**

Add `BUNDLE_VERSION` and `UPSTREAM_COMMIT` to the existing bundle import, then add:

```python
def test_bundle_version_is_derived_from_upstream_commit() -> None:
    assert len(UPSTREAM_COMMIT) == 40
    assert BUNDLE_VERSION == "1.0.0+" + UPSTREAM_COMMIT[:12]
```

- [ ] **Step 2: Run the focused test before implementation**

```bash
.venv/bin/pytest -q \
  tests/distribution/test_bundle.py::test_bundle_version_is_derived_from_upstream_commit
```

Expected: collection fails because `BUNDLE_VERSION` does not exist.

- [ ] **Step 3: Define and use the derived constant in `bundle.py`**

Immediately after `UPSTREAM_COMMIT`, add:

```python
BUNDLE_VERSION = "1.0.0+" + UPSTREAM_COMMIT[:12]
```

Replace the fixed manifest check with:

```python
    if top["bundle_version"] != BUNDLE_VERSION:
        raise ValueError("invalid bundle_version")
```

- [ ] **Step 4: Import and use the same constant in the build script**

The import block must include:

```python
from blender_mcp_installer.bundle import (
    ARTIFACTS,
    BUNDLE_VERSION,
    TOOLS,
    UPSTREAM_COMMIT,
    ReleaseManifest,
    parse_manifest,
    validate_runtime_lock,
)
```

The generated manifest field must be:

```python
        "bundle_version": BUNDLE_VERSION,
```

- [ ] **Step 5: Make the test fixture consume production constants**

Use this import and fixture assignment:

```python
from blender_mcp_installer.bundle import (  # noqa: E402
    ARTIFACTS,
    BUNDLE_VERSION,
    TOOLS,
    UPSTREAM_COMMIT,
    open_verified_bundle,
    parse_manifest,
    validate_runtime_lock,
    verify_distribution_checkout,
)

COMMIT = UPSTREAM_COMMIT
```

Set the fixture field to:

```python
        "bundle_version": BUNDLE_VERSION,
```

- [ ] **Step 6: Run bundle tests and commit**

```bash
.venv/bin/pytest -q tests/distribution/test_bundle.py
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py \
  scripts/build_official_blender_mcp_distribution.py \
  tests/distribution/test_bundle.py
git commit -m "refactor: derive Blender MCP bundle version from source pin"
```

Expected: all bundle tests pass.

---

### Task 2: Put the MCP host deadline outside the inner Blender deadlines

**Files:**
- Modify: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/codex_adapter.py:100-115,337-355`
- Modify: `tests/distribution/test_codex_adapter.py:150-690`
- Test: `tests/distribution/test_codex_adapter.py`

**Interfaces:**
- Consumes: upstream live and background timeout `120.0` seconds plus termination grace `2.0` seconds.
- Produces: `_TOOL_TIMEOUT_SEC = 150.0` used by managed-value validation and desired configuration.

- [ ] **Step 1: Change one expected timeout to expose the invalid current policy**

In `test_desired_values_are_closed_and_ignore_hostile_ambient`, change its assertion to:

```python
    assert desired.tool_timeout_sec == 150.0
```

- [ ] **Step 2: Run the focused test before implementation**

```bash
.venv/bin/pytest -q \
  tests/distribution/test_codex_adapter.py::test_desired_values_are_closed_and_ignore_hostile_ambient
```

Expected: FAIL showing `60.0 == 150.0` is false.

- [ ] **Step 3: Add one production constant and use it at both enforcement points**

Add near the other module constants:

```python
_TOOL_TIMEOUT_SEC = 150.0
```

The `ManagedCodexValues.__post_init__` timeout check must be:

```python
        if (
            type(self.startup_timeout_sec) is not float
            or self.startup_timeout_sec != 20.0
            or type(self.tool_timeout_sec) is not float
            or self.tool_timeout_sec != _TOOL_TIMEOUT_SEC
            or self.default_tools_approval_mode != "approve"
        ):
            raise ValueError("managed Codex timeout/approval policy is fixed")
```

The desired value constructor must use:

```python
        startup_timeout_sec=20.0,
        tool_timeout_sec=_TOOL_TIMEOUT_SEC,
```

- [ ] **Step 4: Update every exact managed timeout expectation and drift input**

Apply this complete semantic mapping only in `tests/distribution/test_codex_adapter.py`:

```text
managed/expected tool_timeout_sec: 60.0 -> 150.0
deliberately drifting tool_timeout_sec: 61.0 -> 151.0
```

Verify the result with:

```bash
rg -n 'tool_timeout_sec.*(60\.0|61\.0)' \
  tests/distribution/test_codex_adapter.py
```

Expected: no output. Values testing omission of `tool_timeout_sec` remain unchanged.

- [ ] **Step 5: Run adapter tests and commit**

```bash
.venv/bin/pytest -q tests/distribution/test_codex_adapter.py
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/codex_adapter.py \
  tests/distribution/test_codex_adapter.py
git commit -m "fix: allow Blender jobs to finish before MCP timeout"
```

Expected: all Codex adapter tests pass, including drift, rollback, and omission cases.

---

### Task 3: Add a wheel-content acceptance gate

**Files:**
- Create: `tests/distribution/test_bundled_runtime_hardening.py`
- Test: `tests/distribution/test_bundled_runtime_hardening.py`

**Interfaces:**
- Consumes: committed server wheel and manifest under `plugins/blender-mcp-installer/artifacts`.
- Produces: release-gate evidence for result integrity, process containment, snapshot routing, direct disk summaries, Retina scaling, timeout ordering, and exact upstream provenance.

- [ ] **Step 1: Create the complete wheel-inspection test**

```python
from __future__ import annotations

import json
from pathlib import Path
import sys
from zipfile import ZipFile


ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins/blender-mcp-installer"
ARTIFACTS = PLUGIN / "artifacts"
sys.path.insert(0, str(PLUGIN / "scripts"))

from blender_mcp_installer.bundle import (  # noqa: E402
    BUNDLE_VERSION,
    UPSTREAM_COMMIT,
)


def _wheel_source(name: str) -> str:
    wheel = ARTIFACTS / "blender_mcp-1.0.0-py3-none-any.whl"
    with ZipFile(wheel) as archive:
        return archive.read(name).decode("utf-8")


def test_manifest_matches_reviewed_upstream_pin() -> None:
    manifest = json.loads((ARTIFACTS / "manifest.json").read_text())
    assert manifest["upstream"]["commit"] == UPSTREAM_COMMIT
    assert manifest["bundle_version"] == BUNDLE_VERSION


def test_wheel_uses_bounded_result_file_and_process_group() -> None:
    source = _wheel_source("blmcp/tools_helpers/blender_cli.py")
    assert "_RESULT_PREFIX" not in source
    assert "_ERROR_PREFIX" not in source
    for token in (
        "_MAX_RESULT_BYTES = 10 * 1024 * 1024",
        "_MAX_STDOUT_BYTES = 1024 * 1024",
        "_MAX_STDERR_BYTES = 1024 * 1024",
        "start_new_session=(os.name == \"posix\")",
        "private_blend_for_cli",
        "TemporaryDirectory(prefix=\".blmcp-job-\"",
    ):
        assert token in source


def test_arbitrary_cli_uses_private_snapshot() -> None:
    source = _wheel_source("blmcp/tools/execute_blender_code.py")
    assert "with private_blend_for_cli(blend_file) as private_path:" in source
    assert "not a sandbox for hostile Python" in source


def test_summary_cli_tools_read_disk_directly() -> None:
    names = (
        "get_blendfile_summary_datablocks.py",
        "get_blendfile_summary_missing_files.py",
        "get_blendfile_summary_of_linked_libraries.py",
        "get_blendfile_summary_path_info.py",
        "get_blendfile_summary_usage_guess.py",
    )
    for name in names:
        source = _wheel_source("blmcp/tools/" + name)
        assert "synced_blend_for_cli" not in source
        assert "return run_blender_cli(blend_file," in source


def test_retina_scale_precedes_small_file_return() -> None:
    source = _wheel_source(
        "blmcp/tools/_template_image_downscale_to_size_limit.py"
    )
    scale = source.index("pixel_size = float(")
    fast_return = source.index("if pixel_size <= 1.0 and source_fits:")
    assert scale < fast_return
    assert "max(1, round(width / pixel_size))" in source
    assert "max(1, round(height / pixel_size))" in source


def test_inner_timeouts_are_120_seconds() -> None:
    cli = _wheel_source("blmcp/tools_helpers/blender_cli.py")
    connection = _wheel_source("blmcp/tools_helpers/connection.py")
    assert "_CLI_TIMEOUT = 120.0" in cli
    assert "_TIMEOUT = 120.0" in connection
```

- [ ] **Step 2: Run the gate against the old committed artifact**

```bash
.venv/bin/pytest -q tests/distribution/test_bundled_runtime_hardening.py
```

Expected: failures show the old wheel still has stdout markers, numbered synchronization, old Retina ordering, and a 300-second live timeout. The provenance test passes because the old manifest is still internally consistent with the old production pin.

- [ ] **Step 3: Commit the red artifact gate**

```bash
git add tests/distribution/test_bundled_runtime_hardening.py
git commit -m "test: gate bundled Blender MCP hardening"
```

---

### Task 4: Pin and reproducibly build the audited upstream commit

**Files:**
- Modify: `plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py:14`
- Regenerate: `plugins/blender-mcp-installer/artifacts/blender_mcp-1.0.0-py3-none-any.whl`
- Regenerate: `plugins/blender-mcp-installer/artifacts/mcp-1.0.0.zip`
- Regenerate: `plugins/blender-mcp-installer/artifacts/runtime-requirements.lock`
- Regenerate: `plugins/blender-mcp-installer/artifacts/manifest.json`
- Regenerate: `plugins/blender-mcp-installer/artifacts/SHA256SUMS`
- Test: `tests/distribution/test_bundle.py`
- Test: `tests/distribution/test_bundled_runtime_hardening.py`

**Interfaces:**
- Consumes: exact `SOURCE_COMMIT`, clean upstream worktree, deterministic builder.
- Produces: a self-consistent committed artifact bundle whose manifest, bundle version, wheel, and checksums identify that exact source commit.

- [ ] **Step 1: Validate the upstream input before editing the distribution pin**

```bash
test "$(printf '%s' "$SOURCE_COMMIT" | wc -c | tr -d ' ')" = 40
printf '%s' "$SOURCE_COMMIT" | grep -Eq '^[0-9a-f]{40}$'
test "$(git -C "$UPSTREAM_SOURCE" rev-parse HEAD)" = "$SOURCE_COMMIT"
test -z "$(git -C "$UPSTREAM_SOURCE" status --short)"
git -C "$UPSTREAM_SOURCE" merge-base --is-ancestor \
  4309a39646e644261624bfcd2bca669b343b7621 "$SOURCE_COMMIT"
UV_BIN=${UV_BIN:-"$HOME/.local/bin/uv"}
test -x "$UV_BIN"
test "$("$UV_BIN" --version | awk '{print $2}')" = "0.12.2"
```

Expected: every command exits 0. `UPSTREAM_SOURCE` is the same upstream worktree used by the first two plans, not a newly fetched branch tip.

- [ ] **Step 2: Replace the single `UPSTREAM_COMMIT` literal using `apply_patch`**

Pass this patch through a shell so the already validated `$SOURCE_COMMIT` is expanded into the quoted Python string:

```bash
apply_patch <<PATCH
*** Begin Patch
*** Update File: plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py
@@
-UPSTREAM_COMMIT = "3800c17797dda55d87ae655182001ad94cc11b8b"
+UPSTREAM_COMMIT = "$SOURCE_COMMIT"
 BUNDLE_VERSION = "1.0.0+" + UPSTREAM_COMMIT[:12]
*** End Patch
PATCH
```

Expected: `UPSTREAM_COMMIT` contains the exact 40-character lowercase hexadecimal value verified in Step 1.

- [ ] **Step 3: Update test provenance through the imported production constant**

No new commit literal is added to tests. Confirm:

```bash
rg -n '3800c17797dda55d87ae655182001ad94cc11b8b|1\.0\.0\+3800c17797dd' \
  plugins/blender-mcp-installer/scripts \
  scripts/build_official_blender_mcp_distribution.py \
  tests/distribution
```

Expected: no output.

- [ ] **Step 4: Run unit tests that do not require the rebuilt artifact**

```bash
.venv/bin/pytest -q \
  tests/distribution/test_bundle.py::test_bundle_version_is_derived_from_upstream_commit \
  tests/distribution/test_codex_adapter.py
```

Expected: the formula test and adapter suite pass; full bundle and artifact gates remain deferred because changing the pin intentionally makes the old committed manifest invalid until the next step.

- [ ] **Step 5: Atomically regenerate the committed artifact directory**

```bash
.venv/bin/python scripts/build_official_blender_mcp_distribution.py \
  --source "$UPSTREAM_SOURCE" \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --uv "$UV_BIN" \
  --output plugins/blender-mcp-installer/artifacts
```

Expected: the builder prints `tools=26` and the exact toolchain line; its two independent source archives and artifact builds compare equal before the directory is atomically published.

- [ ] **Step 6: Verify manifest provenance and every committed checksum**

```bash
.venv/bin/python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("plugins/blender-mcp-installer/artifacts")
manifest = json.loads((root / "manifest.json").read_text())
assert len(manifest["upstream"]["commit"]) == 40
assert manifest["bundle_version"] == "1.0.0+" + manifest["upstream"]["commit"][:12]
for line in (root / "SHA256SUMS").read_text().splitlines():
    digest, name = line.split("  ", 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
print(manifest["upstream"]["commit"])
print(manifest["bundle_version"])
PY
```

Expected: the two printed values correspond exactly to `$SOURCE_COMMIT`; no assertion fails.

- [ ] **Step 7: Run the wheel gate and commit source plus generated artifacts**

```bash
.venv/bin/pytest -q tests/distribution/test_bundled_runtime_hardening.py
git add plugins/blender-mcp-installer/scripts/blender_mcp_installer/bundle.py \
  plugins/blender-mcp-installer/artifacts
git commit -m "build: bundle hardened official Blender MCP runtime"
```

Expected: all artifact hardening tests pass.

---

### Task 5: Certify the complete distribution before installation

**Files:**
- Verify: all files changed since `a31d00e`
- Test: `tests/distribution/`

**Interfaces:**
- Consumes: Tasks 1-4 commits and regenerated artifacts.
- Produces: one clean exact `EXPECTED_DISTRIBUTION_COMMIT` accepted by the transactional installer.

- [ ] **Step 1: Run every distribution test**

```bash
.venv/bin/pytest -q tests/distribution
```

Expected: all tests pass, including bundle integrity, Codex adapter, runtime, verification, plugin contract, and wheel-content hardening.

- [ ] **Step 2: Run repository hygiene and source checks**

```bash
git diff --check a31d00e..HEAD
.venv/bin/ruff check \
  plugins/blender-mcp-installer/scripts \
  scripts/build_official_blender_mcp_distribution.py \
  tests/distribution
git status --short
```

Expected: no diff whitespace errors, no ruff errors, and a clean worktree.

- [ ] **Step 3: Record and validate the exact distribution trust root**

```bash
EXPECTED_DISTRIBUTION_COMMIT=$(git rev-parse HEAD)
test "$(printf '%s' "$EXPECTED_DISTRIBUTION_COMMIT" | wc -c | tr -d ' ')" = 40
git cat-file -e "$EXPECTED_DISTRIBUTION_COMMIT^{commit}"
printf 'EXPECTED_DISTRIBUTION_COMMIT=%s\n' "$EXPECTED_DISTRIBUTION_COMMIT"
```

Expected: one exact 40-character commit is printed and resolves locally as a commit object.

---

### Task 6: Stage, verify, roll back, and then perform the production rollout

**Files:**
- Consume: `plugins/blender-mcp-installer/scripts/install.py`
- Consume: `plugins/blender-mcp-installer/artifacts/`
- Create outside repository: isolated test profile and transactional receipts created by the installer.
- Modify outside repository after operator confirmation: managed runtime, Blender extension/preferences, and Codex MCP configuration.

**Interfaces:**
- Consumes: clean `EXPECTED_DISTRIBUTION_COMMIT` and all four standing authorization flags.
- Produces: successful isolated install/verify/rollback evidence, then a production receipt that can restore the previous state.

- [ ] **Step 1: Create task-specific isolated roots without changing the current profile**

```bash
TEST_PROFILE_ROOT=$(mktemp -d /private/tmp/blender-mcp-profile.XXXXXX)
TEST_CODEX_ROOT="$TEST_PROFILE_ROOT/codex"
TEST_RESOURCES_ROOT="$TEST_PROFILE_ROOT/blender-resources"
mkdir -p "$TEST_CODEX_ROOT" "$TEST_RESOURCES_ROOT/config" \
  "$TEST_RESOURCES_ROOT/extensions"
PLUGIN_ROOT="$PWD/plugins/blender-mcp-installer"
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
CODEX_BIN=$(command -v codex)
UV_BIN=${UV_BIN:-"$HOME/.local/bin/uv"}
PYTHON_BIN="$PWD/.venv/bin/python"
ISOLATED_RUNNER='import runpy,sys; root=sys.argv[1]; script=sys.argv[2]; sys.argv=sys.argv[2:]; sys.path.insert(0,root); runpy.run_path(script,run_name="__main__")'
test -x "$UV_BIN" && test -x "$PYTHON_BIN"
test "$("$UV_BIN" --version | awk '{print $2}')" = "0.12.2"
test "$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')" = "3.13.13"
```

Expected: every executable variable names an existing executable and every profile path descends from `TEST_PROFILE_ROOT`.

- [ ] **Step 2: Inspect the isolated target**

```bash
env HOME="$TEST_PROFILE_ROOT" CODEX_HOME="$TEST_CODEX_ROOT" \
  BLENDER_USER_RESOURCES="$TEST_RESOURCES_ROOT" \
  BLENDER_USER_CONFIG="$TEST_RESOURCES_ROOT/config" \
  BLENDER_USER_EXTENSIONS="$TEST_RESOURCES_ROOT/extensions" \
  "$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" \
  "$PLUGIN_ROOT/scripts" "$PLUGIN_ROOT/scripts/install.py" inspect \
  --bundle-root "$PLUGIN_ROOT/artifacts" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
```

Expected: inspection succeeds without modifying the normal user profile.

- [ ] **Step 3: Install into the isolated target with all four explicit flags**

```bash
env HOME="$TEST_PROFILE_ROOT" CODEX_HOME="$TEST_CODEX_ROOT" \
  BLENDER_USER_RESOURCES="$TEST_RESOURCES_ROOT" \
  BLENDER_USER_CONFIG="$TEST_RESOURCES_ROOT/config" \
  BLENDER_USER_EXTENSIONS="$TEST_RESOURCES_ROOT/extensions" \
  "$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" \
  "$PLUGIN_ROOT/scripts" "$PLUGIN_ROOT/scripts/install.py" install \
  --bundle-root "$PLUGIN_ROOT/artifacts" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access \
  --allow-localhost-bridge --approve-arbitrary-python
```

Expected: changed installation reports `requires_blender_start` and prints/records an absolute receipt path. Do not point production Blender or Codex at this isolated profile.

- [ ] **Step 4: Validate the isolated receipt and rollback mechanically**

Set `ISOLATED_RECEIPT` to the absolute receipt path returned by Step 3, validate that it is inside `TEST_PROFILE_ROOT/.local/state/blender-mcp-installer/receipts`, then run:

```bash
case "$ISOLATED_RECEIPT" in
  "$TEST_PROFILE_ROOT"/.local/state/blender-mcp-installer/receipts/*.json) ;;
  *) exit 1 ;;
esac

env HOME="$TEST_PROFILE_ROOT" CODEX_HOME="$TEST_CODEX_ROOT" \
  BLENDER_USER_RESOURCES="$TEST_RESOURCES_ROOT" \
  BLENDER_USER_CONFIG="$TEST_RESOURCES_ROOT/config" \
  BLENDER_USER_EXTENSIONS="$TEST_RESOURCES_ROOT/extensions" \
  "$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" \
  "$PLUGIN_ROOT/scripts" "$PLUGIN_ROOT/scripts/install.py" rollback \
  --bundle-root "$PLUGIN_ROOT/artifacts" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --receipt "$ISOLATED_RECEIPT"
```

Expected: rollback succeeds and removes/restores only isolated-profile targets recorded in the receipt.

- [ ] **Step 5: Use the reviewed installer skill for the real profile**

Invoke `blender-mcp-installer:install-official-blender-mcp` from the clean distribution worktree and supply the exact `EXPECTED_DISTRIBUTION_COMMIT`. Accept its inspect/install/verify sequence with all four default-enabled flags. Stop at `requires_blender_start`, start Blender normally after operator confirmation, then run its verify phase.

Expected: verification confirms parsed Codex policy, effective MCP configuration, exact 26-tool handshake/catalog, localhost read-only summary, and the new production receipt. Keep that receipt for rollback.

- [ ] **Step 6: Verify the managed timeout and bundled runtime after restart**

```bash
rg -n 'tool_timeout_sec = 150|tool_timeout_sec = 150\.0' \
  "$HOME/.codex/config.toml"
ps -axo pid=,ppid=,etime=,command= | rg 'blender-mcp|codex' | rg -v 'rg '
```

Expected: the managed Blender MCP server has a 150-second tool timeout. Each `blender-mcp` process is attributable through its parent PID to one active Codex execution session.

- [ ] **Step 7: Validate host lifecycle without patching the Blender plugin**

Record the PID and parent PID for the extra Codex session, close that extra Codex task/window normally, wait up to 15 seconds while keeping the primary task open, then rerun:

```bash
ps -axo pid=,ppid=,etime=,command= | rg 'blender-mcp|codex' | rg -v 'rg '
```

Expected: the child `blender-mcp` process belonging to the closed session exits and the primary session's process remains. If the closed session's child persists, preserve the PID/PPID snapshots and file the defect against the Codex MCP-host lifecycle; do not add Blender add-on shutdown code because the add-on did not create that process.

- [ ] **Step 8: Run live smoke calls after Blender and Codex are both restarted**

Call, through the installed MCP server:

```text
get_blendfile_summary_path_info
get_blendfile_summary_path_info_for_cli
get_screenshot_of_window_as_json
get_screenshot_of_window_as_image
execute_blender_code_for_cli with code: import bpy; result = {"version": bpy.app.version_string}
```

Expected: live summary sees current in-memory state; CLI summary reads the on-disk file; screenshot dimensions do not exceed JSON logical dimensions; background execution returns the Blender version from a private snapshot and leaves the source hash unchanged.

---

## Plan Self-Review

- Spec coverage: source pinning, bundle-version consistency, 150/120 timeout ordering, wheel content, reproducibility, all 26 tools, Retina behavior, private snapshots, direct disk summaries, isolated rollback, production verification, and duplicate-process attribution each map to a task.
- Placeholder scan: the two future values are exact Git outputs (`SOURCE_COMMIT` and `EXPECTED_DISTRIBUTION_COMMIT`), both validated as 40-character lowercase commit IDs before use.
- Type consistency: `BUNDLE_VERSION` is a `str`; the public manifest schema and `ManagedCodexValues.tool_timeout_sec: float` remain unchanged.
- Trust boundary: the upstream commit identifies runtime content; the committed distribution checksum set and exact distribution commit authorize installation.
- Lifecycle boundary: the plan tests Codex parent/child ownership and routes a persistent orphan to the correct host component instead of adding an ineffective Blender plugin workaround.
