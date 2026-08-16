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
case "$SOURCE_DISTRIBUTION_ROOT" in /*) ;; *) echo "source repository path must be absolute" >&2; exit 1;; esac
SOURCE_DISTRIBUTION_ROOT="$(cd "$SOURCE_DISTRIBUTION_ROOT" && pwd -P)"
OWNER_UID="$(id -u)"
test "$(/usr/bin/stat -f %u "$SOURCE_DISTRIBUTION_ROOT")" = "$OWNER_UID"
SOURCE_GIT_MARKER="$SOURCE_DISTRIBUTION_ROOT/.git"
if test -d "$SOURCE_GIT_MARKER" && test ! -L "$SOURCE_GIT_MARKER"; then
  SOURCE_GIT_DIR="$(cd "$SOURCE_GIT_MARKER" && pwd -P)"
elif test -f "$SOURCE_GIT_MARKER" && test ! -L "$SOURCE_GIT_MARKER"; then
  IFS= read -r SOURCE_GIT_LINE < "$SOURCE_GIT_MARKER"
  case "$SOURCE_GIT_LINE" in
    'gitdir: '*) SOURCE_GIT_CANDIDATE="${SOURCE_GIT_LINE#gitdir: }" ;;
    *) echo "source .git file is invalid" >&2; exit 1 ;;
  esac
  case "$SOURCE_GIT_CANDIDATE" in
    /*) ;;
    *) SOURCE_GIT_CANDIDATE="$SOURCE_DISTRIBUTION_ROOT/$SOURCE_GIT_CANDIDATE" ;;
  esac
  SOURCE_GIT_DIR="$(cd "$SOURCE_GIT_CANDIDATE" && pwd -P)"
else
  echo "source repository Git admin is invalid" >&2
  exit 1
fi
test ! -L "$SOURCE_GIT_DIR"
test "$(/usr/bin/stat -f %u "$SOURCE_GIT_DIR")" = "$OWNER_UID"
if test -f "$SOURCE_GIT_DIR/commondir" && test ! -L "$SOURCE_GIT_DIR/commondir"; then
  IFS= read -r SOURCE_COMMON_CANDIDATE < "$SOURCE_GIT_DIR/commondir"
  case "$SOURCE_COMMON_CANDIDATE" in
    /*) ;;
    *) SOURCE_COMMON_CANDIDATE="$SOURCE_GIT_DIR/$SOURCE_COMMON_CANDIDATE" ;;
  esac
  SOURCE_COMMON_GIT_DIR="$(cd "$SOURCE_COMMON_CANDIDATE" && pwd -P)"
else
  SOURCE_COMMON_GIT_DIR="$SOURCE_GIT_DIR"
fi
test ! -L "$SOURCE_COMMON_GIT_DIR"
test "$(/usr/bin/stat -f %u "$SOURCE_COMMON_GIT_DIR")" = "$OWNER_UID"
SOURCE_OBJECTS_ROOT="$(cd "$SOURCE_COMMON_GIT_DIR/objects" && pwd -P)"
test -d "$SOURCE_OBJECTS_ROOT" && test ! -L "$SOURCE_OBJECTS_ROOT"
test "$(/usr/bin/stat -f %u "$SOURCE_OBJECTS_ROOT")" = "$OWNER_UID"
SOURCE_INDEX="$SOURCE_GIT_DIR/index"
SOURCE_HEAD_FILE="$SOURCE_GIT_DIR/HEAD"
test -f "$SOURCE_INDEX" && test ! -L "$SOURCE_INDEX"
test -f "$SOURCE_HEAD_FILE" && test ! -L "$SOURCE_HEAD_FILE"
test "$(/usr/bin/stat -f %u "$SOURCE_INDEX")" = "$OWNER_UID"
test "$(/usr/bin/stat -f %u "$SOURCE_HEAD_FILE")" = "$OWNER_UID"
IFS= read -r SOURCE_HEAD_VALUE < "$SOURCE_HEAD_FILE"
case "$SOURCE_HEAD_VALUE" in
  'ref: refs/'*)
    SOURCE_HEAD_REF="${SOURCE_HEAD_VALUE#ref: }"
    case "$SOURCE_HEAD_REF" in *..*|*//*|*\\*) echo "source HEAD ref is invalid" >&2; exit 1;; esac
    SOURCE_HEAD_COMMIT=""
    for SOURCE_REF_ROOT in "$SOURCE_GIT_DIR" "$SOURCE_COMMON_GIT_DIR"; do
      SOURCE_REF_FILE="$SOURCE_REF_ROOT/$SOURCE_HEAD_REF"
      if test -f "$SOURCE_REF_FILE" && test ! -L "$SOURCE_REF_FILE"; then
        IFS= read -r SOURCE_HEAD_COMMIT < "$SOURCE_REF_FILE"
        break
      fi
    done
    if test -z "$SOURCE_HEAD_COMMIT"; then
      SOURCE_PACKED_REFS="$SOURCE_COMMON_GIT_DIR/packed-refs"
      test -f "$SOURCE_PACKED_REFS" && test ! -L "$SOURCE_PACKED_REFS"
      SOURCE_HEAD_COMMIT="$(/usr/bin/awk -v ref="$SOURCE_HEAD_REF" '$2 == ref { print $1 }' "$SOURCE_PACKED_REFS")"
    fi
    ;;
  *) SOURCE_HEAD_COMMIT="$SOURCE_HEAD_VALUE" ;;
esac
case "$SOURCE_HEAD_COMMIT" in ''|*[!0-9a-f]*) echo "source HEAD commit is invalid" >&2; exit 1;; esac
test "${#SOURCE_HEAD_COMMIT}" -eq 40
test "$SOURCE_HEAD_COMMIT" = "$EXPECTED_DISTRIBUTION_COMMIT"
TRUST_PARENT="$(mktemp -d /private/tmp/blender-mcp-trust.XXXXXX)"
chmod 700 "$TRUST_PARENT"
TRUSTED_DISTRIBUTION_ROOT="$TRUST_PARENT/distribution"
PRIVATE_GIT_DIR="$TRUST_PARENT/private.git"
EMPTY_TEMPLATE="$TRUST_PARENT/empty-template"
GIT_SAFE_HOME="$TRUST_PARENT/git-home"
mkdir "$EMPTY_TEMPLATE" "$GIT_SAFE_HOME"
chmod 700 "$EMPTY_TEMPLATE" "$GIT_SAFE_HOME"
TRUSTED_CHECKSUMS=""
GIT_SAFE_ENV=(/usr/bin/env -i
  HOME="$GIT_SAFE_HOME" PATH=/usr/bin:/bin LC_ALL=C
  GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_NO_REPLACE_OBJECTS=1)
"${GIT_SAFE_ENV[@]}" /usr/bin/git --no-replace-objects \
  init --bare --template="$EMPTY_TEMPLATE" "$PRIVATE_GIT_DIR" >/dev/null 2>&1
mkdir "$PRIVATE_GIT_DIR/info" "$PRIVATE_GIT_DIR/hooks"
: > "$PRIVATE_GIT_DIR/config"
: > "$PRIVATE_GIT_DIR/info/attributes"
printf '%s\n' "$EXPECTED_DISTRIBUTION_COMMIT" > "$PRIVATE_GIT_DIR/HEAD"
printf '%s\n' "$SOURCE_OBJECTS_ROOT" > "$PRIVATE_GIT_DIR/objects/info/alternates"
/bin/cp "$SOURCE_INDEX" "$PRIVATE_GIT_DIR/index"
chmod 600 "$PRIVATE_GIT_DIR/config" "$PRIVATE_GIT_DIR/info/attributes" \
  "$PRIVATE_GIT_DIR/HEAD" "$PRIVATE_GIT_DIR/objects/info/alternates" \
  "$PRIVATE_GIT_DIR/index"
test ! -s "$PRIVATE_GIT_DIR/config"
test ! -s "$PRIVATE_GIT_DIR/info/attributes"
test -z "$(find "$PRIVATE_GIT_DIR/hooks" "$EMPTY_TEMPLATE" -mindepth 1 -print -quit)"
GIT_PRIVATE=("${GIT_SAFE_ENV[@]}" /usr/bin/git --no-pager --no-replace-objects
  --git-dir="$PRIVATE_GIT_DIR"
  -c core.fsmonitor=false -c core.hooksPath="$PRIVATE_GIT_DIR/hooks"
  -c core.attributesFile=/dev/null -c diff.external=)
GIT_SOURCE_VIEW=("${GIT_PRIVATE[@]}" --work-tree="$SOURCE_DISTRIBUTION_ROOT")
cleanup_trust_on_exit() {
  cleanup_rc=$?
  trap - EXIT
  if test -e "$TRUSTED_DISTRIBUTION_ROOT/.git"; then
    "${GIT_PRIVATE[@]}" worktree remove --force \
      "$TRUSTED_DISTRIBUTION_ROOT" >/dev/null 2>&1 || true
  else
    rmdir "$TRUSTED_DISTRIBUTION_ROOT" >/dev/null 2>&1 || true
  fi
  test -z "$TRUSTED_CHECKSUMS" || rm -f "$TRUSTED_CHECKSUMS"
  test "$PRIVATE_GIT_DIR" = "$TRUST_PARENT/private.git" || exit 1
  rm -R "$PRIVATE_GIT_DIR" "$EMPTY_TEMPLATE" "$GIT_SAFE_HOME" >/dev/null 2>&1 || true
  rmdir "$TRUST_PARENT" >/dev/null 2>&1 || true
  exit "$cleanup_rc"
}
trap cleanup_trust_on_exit EXIT
"${GIT_PRIVATE[@]}" cat-file -e "$EXPECTED_DISTRIBUTION_COMMIT^{commit}"
"${GIT_SOURCE_VIEW[@]}" diff --no-ext-diff --cached --quiet \
  "$EXPECTED_DISTRIBUTION_COMMIT"
"${GIT_PRIVATE[@]}" read-tree "$EXPECTED_DISTRIBUTION_COMMIT"
"${GIT_SOURCE_VIEW[@]}" diff --no-ext-diff --quiet
test -z "$("${GIT_SOURCE_VIEW[@]}" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer \
  docs/distribute-official-blender-mcp.md \
  docs/audits/2026-08-16-official-blender-mcp-distribution-acceptance.md \
  scripts/build_official_blender_mcp_distribution.py scripts/requirements)"
"${GIT_PRIVATE[@]}" \
  worktree add --detach --no-checkout \
  "$TRUSTED_DISTRIBUTION_ROOT" "$EXPECTED_DISTRIBUTION_COMMIT"
chmod 700 "$TRUSTED_DISTRIBUTION_ROOT"
test ! -s "$PRIVATE_GIT_DIR/config"
test ! -s "$PRIVATE_GIT_DIR/info/attributes"
test -z "$(find "$PRIVATE_GIT_DIR/hooks" "$EMPTY_TEMPLATE" -mindepth 1 -print -quit)"
GIT_TRUSTED=("${GIT_SAFE_ENV[@]}" /usr/bin/git --no-pager --no-replace-objects
  -c core.fsmonitor=false -c core.hooksPath="$PRIVATE_GIT_DIR/hooks"
  -c core.attributesFile=/dev/null -c diff.external=
  -C "$TRUSTED_DISTRIBUTION_ROOT")
"${GIT_TRUSTED[@]}" read-tree "$EXPECTED_DISTRIBUTION_COMMIT"
"${GIT_PRIVATE[@]}" \
  archive --format=tar "$EXPECTED_DISTRIBUTION_COMMIT" | \
  tar -x -C "$TRUSTED_DISTRIBUTION_ROOT"
test -z "$("${GIT_TRUSTED[@]}" symbolic-ref -q HEAD || true)"
test "$("${GIT_TRUSTED[@]}" rev-parse HEAD)" = \
  "$EXPECTED_DISTRIBUTION_COMMIT"
"${GIT_TRUSTED[@]}" diff --no-ext-diff --quiet
"${GIT_TRUSTED[@]}" diff --no-ext-diff --cached --quiet
test -z "$("${GIT_TRUSTED[@]}" status --porcelain=v1 \
  --untracked-files=all -- .agents plugins/blender-mcp-installer)"
test -d "$TRUSTED_DISTRIBUTION_ROOT/.agents"
test -d "$TRUSTED_DISTRIBUTION_ROOT/plugins/blender-mcp-installer"
TRUSTED_CHECKSUMS="$(mktemp "$TRUST_PARENT/SHA256SUMS.XXXXXX")"
chmod 600 "$TRUSTED_CHECKSUMS"
"${GIT_PRIVATE[@]}" cat-file blob \
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
Every Git object, index, worktree, and archive operation uses a private mode-0700 Git
admin with empty config, hooks, templates, and info attributes. The copied source
index is used only for the staged-vs-reviewed check; `read-tree` then rebuilds it from
the reviewed commit before any source-worktree comparison, so mutable source index
flags cannot hide dirty files. The private admin reads only the validated source
object database by hash. Source repository config/info metadata is never loaded;
system/global config and replacement objects are disabled.
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
trap - EXIT
"${GIT_PRIVATE[@]}" worktree remove "$TRUSTED_DISTRIBUTION_ROOT"
rm "$TRUSTED_CHECKSUMS"
test "$PRIVATE_GIT_DIR" = "$TRUST_PARENT/private.git"
rm -R "$PRIVATE_GIT_DIR" "$EMPTY_TEMPLATE" "$GIT_SAFE_HOME"
rmdir "$TRUST_PARENT"
```
<!-- TRUST_CLEANUP_END -->

Record the physical-host gate separately as `SECOND_MAC_CANARY_STATUS: NOT_RUN`
until an independent release operator runs it.
