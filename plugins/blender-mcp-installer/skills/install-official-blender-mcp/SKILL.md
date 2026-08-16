---
name: install-official-blender-mcp
description: Inspect, install, verify, or roll back the reviewed official Blender MCP distribution on a supported Mac with four explicit operator consents.
---

# Install Official Blender MCP

Use this skill only for the reviewed repository distribution. It is a delivery adapter,
not another MCP server: the installed server is the bundled official `blender-mcp`
wheel and Codex connects through the generated local STDIO managed launcher.

## Hard boundaries

- Support exactly Darwin arm64, Blender >=5.2.0,<5.3.0, local Python 3.13,
  uv 0.12.2, and localhost:9876.
- Never import or run anything from the source checkout. SHA-256 provides integrity,
  not authenticity. The reviewed immutable distribution commit is the authenticity boundary.
- Keep the trust bootstrap, plugin add, and installer commands in one fail-fast shell
  session. A new session must repeat the bootstrap.
- Never start, terminate, or force-close Blender. Never open or modify a project
  `.blend` file.
- Do not install uv or Python. A symlinked uv executable is allowed when its supplied
  or discovered path is absolute, executable, version 0.12.2, and passes capability
  probes.
- Receipt consent evidence is audit-only and never authorization. Collect four fresh
  answers for every changed install.

## 1. Establish the trusted distribution

The operator supplies `SOURCE_DISTRIBUTION_ROOT`, a reviewed 40-lowercase-hex
`EXPECTED_DISTRIBUTION_COMMIT`, an absolute `BLENDER_BIN`, and a validated absolute
executable `CODEX_BIN`. Run this before plugin marketplace add, plugin import, or any
installer command. Do not split it across shell sessions.

<!-- TRUST_BOOTSTRAP_BEGIN -->
```bash
set -euo pipefail
: "${SOURCE_DISTRIBUTION_ROOT:?set source repository path}"
: "${EXPECTED_DISTRIBUTION_COMMIT:?set reviewed 40-hex commit}"
: "${BLENDER_BIN:?set absolute Blender executable}"
: "${CODEX_BIN:?set absolute Codex executable}"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_CEILING_DIRECTORIES
unset PYTHONPATH PYTHONHOME PYTHONUSERBASE PYTHONSTARTUP PYTHONINSPECT \
  PYTHONBREAKPOINT VIRTUAL_ENV
export PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1
case "$EXPECTED_DISTRIBUTION_COMMIT" in
  ''|*[!0-9a-f]*) echo "expected distribution commit must be 40 lowercase hex characters" >&2; exit 1 ;;
  *) ;;
esac
test "${#EXPECTED_DISTRIBUTION_COMMIT}" -eq 40
case "$BLENDER_BIN" in /*) ;; *) echo "BLENDER_BIN must be absolute" >&2; exit 1;; esac
case "$CODEX_BIN" in /*) ;; *) echo "CODEX_BIN must be absolute" >&2; exit 1;; esac
test -x "$BLENDER_BIN"
test -x "$CODEX_BIN"
test "$(git -C "$SOURCE_DISTRIBUTION_ROOT" rev-parse HEAD)" = \
  "$EXPECTED_DISTRIBUTION_COMMIT"
git -C "$SOURCE_DISTRIBUTION_ROOT" diff --quiet
git -C "$SOURCE_DISTRIBUTION_ROOT" diff --cached --quiet
test -z "$(git -C "$SOURCE_DISTRIBUTION_ROOT" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer \
  docs/distribute-official-blender-mcp.md \
  docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md \
  scripts/build_official_blender_mcp_distribution.py scripts/requirements)"
TRUST_PARENT="$(mktemp -d /private/tmp/blender-mcp-trust.XXXXXX)"
chmod 700 "$TRUST_PARENT"
TRUSTED_DISTRIBUTION_ROOT="$TRUST_PARENT/distribution"
EMPTY_HOOKS="$TRUST_PARENT/empty-hooks"
mkdir "$EMPTY_HOOKS"
chmod 700 "$EMPTY_HOOKS"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  worktree add --detach --no-checkout \
  "$TRUSTED_DISTRIBUTION_ROOT" "$EXPECTED_DISTRIBUTION_COMMIT"
chmod 700 "$TRUSTED_DISTRIBUTION_ROOT"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$TRUSTED_DISTRIBUTION_ROOT" \
  read-tree "$EXPECTED_DISTRIBUTION_COMMIT"
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  archive --format=tar "$EXPECTED_DISTRIBUTION_COMMIT" | \
  tar -x -C "$TRUSTED_DISTRIBUTION_ROOT"
test -z "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" symbolic-ref -q HEAD || true)"
test "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" rev-parse HEAD)" = \
  "$EXPECTED_DISTRIBUTION_COMMIT"
git -C "$TRUSTED_DISTRIBUTION_ROOT" diff --quiet
git -C "$TRUSTED_DISTRIBUTION_ROOT" diff --cached --quiet
test -z "$(git -C "$TRUSTED_DISTRIBUTION_ROOT" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer)"
test -d "$TRUSTED_DISTRIBUTION_ROOT/.agents"
test -d "$TRUSTED_DISTRIBUTION_ROOT/plugins/blender-mcp-installer"
TRUSTED_CHECKSUMS="$(mktemp "$TRUST_PARENT/SHA256SUMS.XXXXXX")"
chmod 600 "$TRUSTED_CHECKSUMS"
git -C "$TRUSTED_DISTRIBUTION_ROOT" show \
  "$EXPECTED_DISTRIBUTION_COMMIT:plugins/blender-mcp-installer/artifacts/SHA256SUMS" \
  > "$TRUSTED_CHECKSUMS"
DISTRIBUTION_ROOT="$TRUSTED_DISTRIBUTION_ROOT"
PLUGIN_ROOT="$DISTRIBUTION_ROOT/plugins/blender-mcp-installer"
BUNDLE_ROOT="$PLUGIN_ROOT/artifacts"
cmp "$TRUSTED_CHECKSUMS" "$BUNDLE_ROOT/SHA256SUMS"
(cd "$BUNDLE_ROOT" && shasum -a 256 -c "$TRUSTED_CHECKSUMS")
```
<!-- TRUST_BOOTSTRAP_END -->

This `--no-checkout` worktree is materialized with `read-tree` plus built-in
`git archive`, so source checkout hooks and working-tree filters do not execute.
Keep the private worktree and checksum file until the workflow is complete; they
are evidence and all later paths derive from them. Never reset `DISTRIBUTION_ROOT`
to the source checkout.

Add the repository marketplace and plugin from this trusted tree in the same shell:

```bash
"$CODEX_BIN" plugin marketplace add "$DISTRIBUTION_ROOT"
"$CODEX_BIN" plugin add "blender-mcp-installer@personal"
```

If the marketplace reports a different name, read the top-level `name` from the
trusted `.agents/plugins/marketplace.json` without importing repository Python and
use that exact name. Do not proceed from an untrusted or dirty checkout.

## 2. Resolve the local runner before each command

Define this function once in the trusted fail-fast shell. Call it immediately
before every inspect, install, verify, or rollback command. It may read or create
uv execution cache metadata, but `--no-python-downloads` and `--no-sync` prevent
interpreter or package installation.

<!-- UV_BOOTSTRAP_BEGIN -->
```bash
run_uv_bootstrap() {
  if test -n "${UV_BIN:-}"; then
    CANDIDATE_UV="$UV_BIN"
  elif command -v uv >/dev/null 2>&1; then
    CANDIDATE_UV="$(command -v uv)"
  elif test -x "$HOME/.local/bin/uv"; then
    CANDIDATE_UV="$HOME/.local/bin/uv"
  else
    echo "uv 0.12.2 and a local Python 3.13 are required; install them, then retry." >&2
    return 1
  fi
  case "$CANDIDATE_UV" in /*) ;; *) echo "UV_BIN must be absolute" >&2; return 1;; esac
  test -x "$CANDIDATE_UV"
  test "$("$CANDIDATE_UV" --version | awk '{print $2}')" = "0.12.2"
  "$CANDIDATE_UV" run --help | grep -q -- "--no-sync"
  "$CANDIDATE_UV" run --help | grep -q -- "--no-python-downloads"
  PYTHON_BIN="$("$CANDIDATE_UV" python find 3.13 --no-project \
    --no-python-downloads --no-config)"
  test -x "$PYTHON_BIN"
  "$PYTHON_BIN" -I -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 13))'
  UV_BIN="$CANDIDATE_UV"
  ISOLATED_RUNNER='import runpy,sys; root=sys.argv[1]; script=sys.argv[2]; sys.argv=sys.argv[2:]; sys.path.insert(0,root); runpy.run_path(script,run_name="__main__")'
}
```
<!-- UV_BOOTSTRAP_END -->

## 3. Inspect, consent, and install

Run inspect first. It is read-only for managed targets; its uv launcher has the
cache caveat above.

<!-- INSTALLER_COMMANDS_BEGIN -->
<!-- INSPECT_BEGIN -->
```bash
run_uv_bootstrap
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" inspect \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
```
<!-- INSPECT_END -->

Ask separately and wait for an explicit answer to each checkpoint:

1. May the installer install and enable the reviewed Blender extension?
2. May the installer enable Blender Allow Online Access? This permits Blender and
   extensions to access the network.
3. May the installer open the localhost:9876 bridge between the local MCP process
   and Blender?
4. May the installer expose arbitrary-Python MCP tools to the connected LLM?

Do not combine the questions or infer an answer. If any answer is absent or no,
stop without running install. Receipt consent evidence is audit-only and never authorization.
After four explicit yes answers, run the changed install once:

<!-- INSTALL_BEGIN -->
```bash
run_uv_bootstrap
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" install \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --allow-extension-install --allow-online-access \
  --allow-localhost-bridge --approve-arbitrary-python
```
<!-- INSTALL_END -->

For a changed install, stop when it reports `requires_blender_start`. Tell the
operator: Start the selected Blender normally, then confirm it is running. Only
after confirmation run verify:

<!-- VERIFY_BEGIN -->
```bash
run_uv_bootstrap
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" verify \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
```
<!-- VERIFY_END -->

Verification succeeds only when parsed Codex policy, effective Codex MCP config,
the exact MCP handshake/catalog, and the localhost Blender read-only summary call
all pass. A changed install may fetch exact-version, hash-locked wheels from PyPI;
the workflow is network-assisted.

## 4. Repair or roll back

Tell the operator: Close Blender normally and confirm it is closed before repair or rollback.
Never start, terminate, or force-close Blender. A repair is the install
flow with four newly collected consents. For rollback, retain the original receipt,
set its absolute path as `RECEIPT_PATH`, and run:

<!-- ROLLBACK_BEGIN -->
```bash
run_uv_bootstrap
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" rollback \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --receipt "$RECEIPT_PATH"
```
<!-- ROLLBACK_END -->
<!-- INSTALLER_COMMANDS_END -->

Rollback verifies the receipt and current host state; the receipt path is not
authorization for a new install. Preserve receipts for audit and future rollback.

## 5. Cleanup and external acceptance status

For a release gate, verify marketplace discovery without touching the normal profile.
Keep this unauthenticated; plugin discovery does not require an API key. Resolve the
local runner first, then run:

<!-- MARKETPLACE_SMOKE_BEGIN -->
```bash
run_uv_bootstrap
SMOKE_HOME="$(mktemp -d /private/tmp/blender-mcp-marketplace.XXXXXX)"
chmod 700 "$SMOKE_HOME"
SMOKE_CODEX_HOME="$SMOKE_HOME/.codex"
mkdir "$SMOKE_CODEX_HOME"
chmod 700 "$SMOKE_CODEX_HOME"
test -d "$SMOKE_CODEX_HOME" || { echo "disposable CODEX_HOME is missing" >&2; exit 1; }
SMOKE_PATH="$(dirname "$UV_BIN"):/usr/bin:/bin:/usr/sbin:/sbin"
MARKETPLACE_LIST_CHECK="$(cat <<'PY'
import json, sys

p = json.load(open(sys.argv[1]))
assert type(p) is dict, "plugin list JSON must be a top-level object"
assert set(p) == {"installed", "available"}, "plugin list JSON must contain exactly installed and available"
assert type(p["installed"]) is list, "plugin list installed must be an array"
assert type(p["available"]) is list, "plugin list available must be an array"
items = p["installed"] + p["available"]
assert all(type(x) is dict and type(x.get("name")) is str for x in items), "plugin list items must be objects with string names"
assert sum(x["name"] == "blender-mcp-installer" for x in p["installed"]) == 1, "plugin list must contain exactly one installed blender-mcp-installer"
PY
)"
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" plugin marketplace add "$DISTRIBUTION_ROOT"
MARKETPLACE_NAME="$("$PYTHON_BIN" -I -c \
  'import json,sys;print(json.load(open(sys.argv[1]))["name"])' \
  "$DISTRIBUTION_ROOT/.agents/plugins/marketplace.json")"
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" plugin add "blender-mcp-installer@$MARKETPLACE_NAME"
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" plugin list --marketplace "$MARKETPLACE_NAME" --json \
  > "$SMOKE_HOME/plugins.json"
"$PYTHON_BIN" -I -c "$MARKETPLACE_LIST_CHECK" "$SMOKE_HOME/plugins.json"
```
<!-- MARKETPLACE_SMOKE_END -->

If uv,
`CODEX_HOME`, or the JSON schema is unavailable, stop with the displayed failure;
do not fall back to the normal profile. Retain the disposable profile as evidence
until the gate is recorded.

Without independently supplied disposable credentials, record
`LOCAL_LLM_INVOCATION_STATUS: NOT_RUN`. If `DISPOSABLE_CODEX_API_KEY` is supplied,
authenticate and invoke only the disposable profile:

```bash
printf '%s' "$DISPOSABLE_CODEX_API_KEY" | \
  HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" login --with-api-key
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" login status
HOME="$SMOKE_HOME" CODEX_HOME="$SMOKE_CODEX_HOME" PATH="$SMOKE_PATH" \
  "$CODEX_BIN" exec --sandbox read-only --skip-git-repo-check \
  "Invoke install-official-blender-mcp in inspect-only mode. Do not install."
```

Never copy normal Codex credentials. Scan logs and evidence for the credential
sentinel before retaining them.

After evidence is retained elsewhere and no more installer command will run, remove
only the private trust objects in this order:

<!-- TRUST_CLEANUP_BEGIN -->
```bash
git -c core.hooksPath="$EMPTY_HOOKS" -C "$SOURCE_DISTRIBUTION_ROOT" \
  worktree remove "$TRUSTED_DISTRIBUTION_ROOT"
rm "$TRUSTED_CHECKSUMS"
rmdir "$EMPTY_HOOKS"
rmdir "$TRUST_PARENT"
```
<!-- TRUST_CLEANUP_END -->

Record the physical-host gate separately as `SECOND_MAC_CANARY_STATUS: NOT_RUN`
until an independent release operator runs it.
