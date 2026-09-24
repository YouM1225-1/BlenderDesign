# Installer command reference

Read the [skill entrypoint](../SKILL.md) for scope and authorization. Select the
requested operation; this file is a command reference, not a script to run top to
bottom. Trust and runner bootstraps apply to every operation. Marketplace prepare
is only for an authorized install or registration update; release checks are
only for release acceptance. Keep dependent blocks in the same fail-fast Bash
session. A new session must repeat the trust bootstrap.

## Operation recipes

Each name below identifies one fenced Bash block in this file. Execute only the
requested recipe after its prerequisites are satisfied. `register` updates the
Codex marketplace/plugin registration; it does not install or repair the Blender
extension or MCP runtime. Installer commands are not prerequisites for registration.

| Operation | Blocks in order |
|---|---|
| inspect | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `INSPECT` → `TRUST_CLEANUP` |
| register | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `PERSISTENT_MARKETPLACE` → `TRUST_CLEANUP` → `PERSISTENT_MARKETPLACE_VERIFY` |
| install | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `INSPECT` → `INSTALL` → `VERIFY` → `FINALIZE` → `TRUST_CLEANUP` → `PERSISTENT_MARKETPLACE_VERIFY` |
| verify | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `VERIFY` → `TRUST_CLEANUP` |
| finalize | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `VERIFY` → `FINALIZE` → `TRUST_CLEANUP` → `PERSISTENT_MARKETPLACE_VERIFY` |
| finalize-register | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `REGISTER_FINALIZE` → `TRUST_CLEANUP` → `PERSISTENT_MARKETPLACE_VERIFY` |
| begin-handoff | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `BEGIN_HANDOFF` → `TRUST_CLEANUP` |
| rollback | `TRUST_BOOTSTRAP` → `UV_BOOTSTRAP` → `ROLLBACK` → `TRUST_CLEANUP` |

Repair uses the install recipe with Blender closed. After install (including a
no-op), retain its receipt and trust evidence while waiting for Blender startup.
When Blender is ready, continue with `VERIFY` and `FINALIZE`, then `TRUST_CLEANUP`
and `PERSISTENT_MARKETPLACE_VERIFY`. A new shell uses the standalone finalize
recipe to reconstruct trust and runner state without repeating registration or
installation. Release acceptance may additionally insert `MARKETPLACE_SMOKE`
before cleanup; it is not part of ordinary operation recipes.

## 1. Establish the trusted distribution

Use already supplied or validated local paths where available; ask only for missing
inputs. The operator supplies `SOURCE_DISTRIBUTION_ROOT`, a reviewed 40-lowercase-hex `EXPECTED_DISTRIBUTION_COMMIT`,
absolute `BLENDER_BIN` and `PYTHON_BIN` inputs, and a validated absolute `CODEX_BIN`. Python must resolve to
3.13.13. Run this before plugin marketplace add/import or installer commands. Do not split shell sessions.

<!-- TRUST_BOOTSTRAP_BEGIN -->
```bash
set -euo pipefail
OPERATOR_PATH="$PATH"
PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
: "${SOURCE_DISTRIBUTION_ROOT:?set source repository path}"
: "${EXPECTED_DISTRIBUTION_COMMIT:?set reviewed 40-hex commit}"
: "${BLENDER_BIN:?set absolute Blender executable}"
: "${CODEX_BIN:?set absolute Codex executable}"
: "${PYTHON_BIN:?set absolute Python 3.13.13 executable}"
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
case "$PYTHON_BIN" in /*) ;; *) echo "PYTHON_BIN must be absolute" >&2; exit 1;; esac
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

This `--no-checkout` worktree uses `read-tree` plus built-in `git archive`, so source
checkout hooks and filters do not execute. Every Git operation uses a private mode-0700
admin with empty config, hooks, templates, and attributes. Its copied source index is
only for the staged check; `read-tree` rebuilds it before source comparison, so index
flags cannot hide dirt. The admin reads only validated objects by hash; source metadata,
system/global config, and replacements stay disabled. Retain the worktree and checksums
through the workflow. Never reset it to the source checkout or register it as a marketplace.

## 2. Resolve the local runner before each command

Define this function once in the trusted fail-fast shell. Call it immediately
before every inspect, install, verify, or rollback command. It may read or create
uv execution cache metadata, but `--no-python-downloads` and `--no-sync` prevent
interpreter or package installation.

<!-- UV_BOOTSTRAP_BEGIN -->
```bash
run_uv_bootstrap() {
  case "$PYTHON_BIN" in /*) ;; *) echo "PYTHON_BIN must be absolute" >&2; return 1;; esac
  CANONICAL_PYTHON="$(/bin/realpath "$PYTHON_BIN")"
  case "$CANONICAL_PYTHON" in /*) ;; *) echo "canonical Python path must be absolute" >&2; return 1;; esac
  test -f "$CANONICAL_PYTHON" && test ! -L "$CANONICAL_PYTHON" && test -x "$CANONICAL_PYTHON"
  PYTHON_OWNER="$(/usr/bin/stat -f %u "$CANONICAL_PYTHON")" || { echo "cannot read canonical Python owner" >&2; return 1; }
  case "$PYTHON_OWNER" in ''|*[!0-9]*) echo "canonical Python owner is invalid" >&2; return 1;; esac
  test "$PYTHON_OWNER" = "$OWNER_UID" || test "$PYTHON_OWNER" = 0 || { echo "canonical Python owner is not trusted" >&2; return 1; }
  PYTHON_MODE="$(/usr/bin/stat -f %Lp "$CANONICAL_PYTHON")"
  case "$PYTHON_MODE" in ''|*[!0-7]*) echo "canonical Python mode is invalid" >&2; return 1;; esac
  case "$PYTHON_MODE" in *[2367][0-7]|*[0-7][2367]) echo "canonical Python must not be group/world-writable" >&2; return 1;; esac
  "$CANONICAL_PYTHON" -I -c 'import sys; raise SystemExit(sys.version_info[:3] != (3, 13, 13))'
  PYTHON_BIN="$CANONICAL_PYTHON"
  if test -n "${UV_BIN:-}"; then
    CANDIDATE_UV="$UV_BIN"
  elif CANDIDATE_UV="$(PATH="$OPERATOR_PATH" command -v uv 2>/dev/null)"; then
    :
  elif test -x "$HOME/.local/bin/uv"; then
    CANDIDATE_UV="$HOME/.local/bin/uv"
  else
    echo "uv 0.12.2 is required; install it, then retry." >&2
    return 1
  fi
  case "$CANDIDATE_UV" in /*) ;; *) echo "UV_BIN must be absolute" >&2; return 1;; esac
  test -x "$CANDIDATE_UV"
  test "$("$CANDIDATE_UV" --version | awk '{print $2}')" = "0.12.2"
  "$CANDIDATE_UV" run --help | grep -q -- "--no-sync"
  "$CANDIDATE_UV" run --help | grep -q -- "--no-python-downloads"
  CANONICAL_UV="$("$PYTHON_BIN" -I -c \
    'import sys; from pathlib import Path; print(Path(sys.argv[1]).resolve(strict=True))' \
    "$CANDIDATE_UV")"
  case "$CANONICAL_UV" in /*) ;; *) echo "canonical uv path must be absolute" >&2; return 1;; esac
  test -f "$CANONICAL_UV" && test ! -L "$CANONICAL_UV" && test -x "$CANONICAL_UV"
  test "$("$CANONICAL_UV" --version | awk '{print $2}')" = "0.12.2"
  "$CANONICAL_UV" run --help | grep -q -- "--no-sync"
  "$CANONICAL_UV" run --help | grep -q -- "--no-python-downloads"
  UV_BIN="$CANONICAL_UV"
  ISOLATED_RUNNER='import runpy,sys; root=sys.argv[1]; script=sys.argv[2]; sys.argv=sys.argv[2:]; sys.path.insert(0,root); runpy.run_path(script,run_name="__main__")'
}
```
<!-- UV_BOOTSTRAP_END -->

## 3. Inspect and select the requested operation

Run inspect for an inspect request and before install/repair. It is read-only for
managed targets; its uv launcher has the cache caveat above. Standalone register,
verify and rollback follow their own recipes.

<!-- INSTALLER_COMMANDS_BEGIN -->
<!-- INSPECT_BEGIN -->
```bash
run_uv_bootstrap
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" inspect \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
```
<!-- INSPECT_END -->

Inspect reports the 13 inputs to `exact` in `checks`. `blender_checks` separately
reports extension-file integrity and the Online Access, host, port, and autostart
preference checks, so a managed preference drift can be diagnosed without weakening
the exact gate. The receipt's recorded Codex version is evidence only: a Codex update
alone keeps the installation exact. The effective-config check and host capability
probe run the current Codex, and the policy and namespace checks read the current
config. Blender, uv and Python versions still take part in the exact gate.

The operator has set a standing default-allow policy for these four capabilities:

1. The installer may install and enable the reviewed Blender extension.
2. The installer may enable Blender Allow Online Access. This permits Blender and
   extensions to access the network.
3. The installer may open the localhost:9876 bridge between the local MCP process
   and Blender.
4. The installer may expose arbitrary-Python MCP tools to the connected LLM.

Do not ask four per-install authorization questions. These defaults apply only to
an installation the operator requested; inspect-only does not authorize installation
or registration changes. If any default is revoked, stop the dependent install and
continue any requested read-only diagnosis. Always pass all four explicit CLI flags and run the changed install once.
The receipt key `all_four_collected_for_this_workflow` is retained for schema
compatibility and means all four authorization flags were active; it does not mean four
prompts were shown.

For a registration-only request, run this prepare block, which automatically verifies
registration and finalizes cleanup without Blender, runtime, extension, or receipt changes.
Full install/repair uses the single-process `INSTALL` upgrade block below.
Skip this block for inspect-only, verify-only, and rollback requests.
New commits are verified before target-only replacement;
mode-0600 recovery evidence is receipt-independent. The helper runs
`plugin add "blender-mcp-installer@official-blender-mcp"` only in a mode-0700
transaction CODEX_HOME, because the native command may prune older caches. It stages
only this target profile's mode-0600 config snapshot, never login/session files or
inherited credentials. The snapshot may contain sensitive configuration; it is not
logged, and successful publication removes temporary config copies. Failed stages
remain private for explicit diagnosis/recovery. Before writing a config snapshot, the
transaction records the exact native stage directory and root identity. Before a
config stage becomes visible, durable intent binds the original live config, the
verified cache, the native file inode/hash, and this transaction. A retry with
intent resumes the conditional move of that same file without rerunning native
Codex, so changing native timestamps cannot replace the pending config. When
CODEX_HOME is on another volume the move is refused with EXDEV and nothing moves; the
transaction then exclusively writes a mode-0600 `.registration.transfer` copy in
CODEX_HOME, requires its bytes to match the bound native file, appends its identity
to the intent, and only then moves it to the stage on the same volume. A failed
write removes only the copy it exclusively created. A transfer without intent, one
whose bytes, mode, or owner differ from the bound native file (for example after an
interrupted write), or later drift is preserved and rejected; the error names the
transfer path for explicit operator recovery. Before
intent exists, retries clean the recorded prior attempt before creating another,
using a persisted deletion image to resume partial cleanup. Successful publication also requires
this cleanup; missing or conflicting evidence fails closed, and unknown native
directories are never selected by a wildcard.

The verified desired cache is published first without replacing older cache paths
or inodes. Only then is the config conditionally published, preserving every
non-target TOML value (including other fields in the target plugin table). Conflicts
retain evidence and do not overwrite external changes. A crash between cache and
config publication can reuse the exact new cache; a recorded config swap resumes
through the existing conditional file primitives. A stage without verifiable intent
or publication evidence is preserved and rejected, as are stage, config, or cache
identity conflicts. Existing publication records remain recoverable. Old busy caches remain pending
until their entry leases are released and a later finalize revalidates them.
<!-- PERSISTENT_MARKETPLACE_BEGIN -->
```bash
run_uv_bootstrap
NORMAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
WORKFLOW_RC=0
if WORKFLOW_JSON="$("$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/project_marketplace.py" prepare \
  --private-git-dir "$PRIVATE_GIT_DIR" --git-safe-home "$GIT_SAFE_HOME" \
  --reviewed-commit "$EXPECTED_DISTRIBUTION_COMMIT" --trusted-checksums "$TRUSTED_CHECKSUMS" \
  --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME")"; then
  :
else
  WORKFLOW_RC=$?
  case "$WORKFLOW_RC" in 3) ;; *) exit "$WORKFLOW_RC" ;; esac
fi
"$PYTHON_BIN" -I -c 'import json,sys; d=json.loads(sys.argv[1]); assert int(sys.argv[2]) != 3 or d.get("status") == "cleanup_pending"' "$WORKFLOW_JSON" "$WORKFLOW_RC"
WORKFLOW_ID="$("$PYTHON_BIN" -I -c 'import json,sys,uuid; value=json.loads(sys.argv[1]).get("workflow_id"); print("" if value is None else str(uuid.UUID(value)))' "$WORKFLOW_JSON")"
PERSISTENT_MARKETPLACE_ROOT="$("$PYTHON_BIN" -I -c 'import json,sys; print(json.loads(sys.argv[1])["projection"])' "$WORKFLOW_JSON")"
REGISTRATION_RECOVERY_DIR="$("$PYTHON_BIN" -I -c 'import json,sys; print(json.loads(sys.argv[1]).get("recovery", ""))' "$WORKFLOW_JSON")"
MARKETPLACE_NAME="official-blender-mcp"
```
<!-- PERSISTENT_MARKETPLACE_END -->

<!-- INSTALL_BEGIN -->
```bash
run_uv_bootstrap
NORMAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
HANDOFF_ARGS=()
if test -n "${HANDOFF_ID:-}"; then HANDOFF_ARGS+=(--handoff-id "$HANDOFF_ID"); fi
WORKFLOW_RC=0
if WORKFLOW_JSON="$("$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/project_marketplace.py" upgrade \
  --private-git-dir "$PRIVATE_GIT_DIR" --git-safe-home "$GIT_SAFE_HOME" \
  --reviewed-commit "$EXPECTED_DISTRIBUTION_COMMIT" --trusted-checksums "$TRUSTED_CHECKSUMS" \
  --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME" \
  --bundle-root "$BUNDLE_ROOT" --blender "$BLENDER_BIN" --uv "$UV_BIN" \
  ${HANDOFF_ARGS[@]+"${HANDOFF_ARGS[@]}"} \
  --allow-extension-install --allow-online-access --allow-localhost-bridge --approve-arbitrary-python)"; then
  :
else
  WORKFLOW_RC=$?
  case "$WORKFLOW_RC" in 3) ;; *) exit "$WORKFLOW_RC" ;; esac
fi
"$PYTHON_BIN" -I -c 'import json,sys; d=json.loads(sys.argv[1]); assert int(sys.argv[2]) != 3 or d.get("status") == "cleanup_pending"' "$WORKFLOW_JSON" "$WORKFLOW_RC"
WORKFLOW_ID="$("$PYTHON_BIN" -I -c 'import json,sys,uuid; value=json.loads(sys.argv[1]).get("workflow_id"); print("" if value is None else str(uuid.UUID(value)))' "$WORKFLOW_JSON")"
PERSISTENT_MARKETPLACE_ROOT="$("$PYTHON_BIN" -I -c 'import json,sys; print(json.loads(sys.argv[1])["projection"])' "$WORKFLOW_JSON")"
REGISTRATION_RECOVERY_DIR="$("$PYTHON_BIN" -I -c 'import json,sys; print(json.loads(sys.argv[1]).get("recovery", ""))' "$WORKFLOW_JSON")"
MARKETPLACE_NAME="official-blender-mcp"
```
<!-- INSTALL_END -->

Keep the trusted distribution, private Git directory and checksum evidence until live
finalize finishes. When installation reports `requires_blender_start`, use current
host evidence to check readiness. If needed, ask the operator to start the selected
Blender normally. Reuse existing confirmation; do not repeat it. Run the read-only
`VERIFY` block, then automatically run `FINALIZE` under the existing authorization.

<!-- VERIFY_BEGIN -->
```bash
run_uv_bootstrap
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" verify \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN"
```
<!-- VERIFY_END -->

<!-- FINALIZE_BEGIN -->
```bash
run_uv_bootstrap
NORMAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
if test -n "$WORKFLOW_ID"; then
  FINALIZE_RC=0
  if FINALIZE_JSON="$("$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
    --no-python-downloads --no-sync \
    python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
    "$PLUGIN_ROOT/scripts/install.py" finalize \
    --bundle-root "$BUNDLE_ROOT" \
    --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
    --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
    --workflow-id "$WORKFLOW_ID")"; then
    :
  else
    FINALIZE_RC=$?
    case "$FINALIZE_RC" in 3) ;; *) exit "$FINALIZE_RC" ;; esac
  fi
  "$PYTHON_BIN" -I -c 'import json,sys; d=json.loads(sys.argv[1]); assert d["workflow_id"] == sys.argv[3]; assert int(sys.argv[2]) != 3 or d.get("status") == "cleanup_pending"' "$FINALIZE_JSON" "$FINALIZE_RC" "$WORKFLOW_ID"
  WORKFLOW_RC="$FINALIZE_RC"
  WORKFLOW_JSON="$FINALIZE_JSON"
fi
```
<!-- FINALIZE_END -->

For a finalize retry, recover `WORKFLOW_ID`, `PERSISTENT_MARKETPLACE_ROOT`, and
optional `REGISTRATION_RECOVERY_DIR` from the retained JSON of the matching original
upgrade/prepare. Validate the UUID and keep the recorded HOME/CODEX_HOME and reviewed
commit; never reuse unrelated session variables. Full finalize uses the live blocks
above. Register-only retries use this block without Blender or runtime arguments:

<!-- REGISTER_FINALIZE_BEGIN -->
```bash
run_uv_bootstrap
NORMAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
WORKFLOW_RC=0
if WORKFLOW_JSON="$("$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/project_marketplace.py" finalize \
  --workflow-id "$WORKFLOW_ID" \
  --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME")"; then
  :
else
  WORKFLOW_RC=$?
  case "$WORKFLOW_RC" in 3) ;; *) exit "$WORKFLOW_RC" ;; esac
fi
"$PYTHON_BIN" -I -c 'import json,sys,uuid; d=json.loads(sys.argv[1]); assert str(uuid.UUID(d["workflow_id"])) == sys.argv[3]; assert int(sys.argv[2]) != 3 or d.get("status") == "cleanup_pending"' "$WORKFLOW_JSON" "$WORKFLOW_RC" "$WORKFLOW_ID"
```
<!-- REGISTER_FINALIZE_END -->

For the first lease-less migration, run this reviewed entry from an external terminal:

<!-- BEGIN_HANDOFF_BEGIN -->
```bash
run_uv_bootstrap
NORMAL_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
HANDOFF_JSON="$("$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/project_marketplace.py" begin-handoff \
  --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME")"
HANDOFF_ID="$("$PYTHON_BIN" -I -c 'import json,sys,uuid; print(uuid.UUID(json.loads(sys.argv[1])["handoff_id"]))' "$HANDOFF_JSON")"
printf '%s\n' "$HANDOFF_JSON"
```
<!-- BEGIN_HANDOFF_END -->

Save the positive process identities, then have the operator exit the recorded Codex
clients and managed MCP processes normally. Pass `HANDOFF_ID` into upgrade or rollback;
never shut down user applications automatically. A prior rollback can restore a lease-less
runtime, so a repeated rollback may require a fresh begin-handoff and `--handoff-id`.
Runtime handoff does not prove old Codex tasks reloaded: old caches without cooperative
usage evidence remain pending. Runtime and extension recoveries retired before the
current host boot need no handoff, because the restart ended every process that could
still use them. A cleanup journal for a release that is no longer current completes
once a current finalize verifies all its remaining baselines absent. Current launchers
and cached entries name their lease by inode, so a reboot that renumbers the volume
device keeps them usable; a missing lease exits 75, and every exit-75 refusal prints one
fixed reason without paths on stderr. A v1-lease (`inode-v1`) runtime whose
device changed since its installed receipt is not reported in use merely because no
lease exists under the new device number; any existing lease under either number
must still be free. A v1 plugin cache first recorded after a reboot whose lease
predates that reboot stays pending until the next device renumbering.


Verification succeeds only when parsed Codex policy, effective Codex MCP config,
the exact MCP handshake/catalog, and the localhost Blender read-only summary call
all pass. A changed install may fetch exact-version, hash-locked wheels from PyPI;
the workflow is network-assisted.

## 4. Repair or roll back

Before repair or rollback, establish from current host evidence that Blender is
closed. If it is running, ask the operator to save work and close it normally.
Never start, terminate, or force-close Blender. A repair is the install
flow with the same standing default-allow policy. For rollback, retain the original receipt,
set its absolute path as `RECEIPT_PATH`, and run:

<!-- ROLLBACK_BEGIN -->
```bash
run_uv_bootstrap
HANDOFF_ARGS=()
if test -n "${HANDOFF_ID:-}"; then HANDOFF_ARGS+=(--handoff-id "$HANDOFF_ID"); fi
"$UV_BIN" run --quiet --no-project --python "$PYTHON_BIN" \
  --no-python-downloads --no-sync \
  python -I -B -c "$ISOLATED_RUNNER" "$PLUGIN_ROOT/scripts" \
  "$PLUGIN_ROOT/scripts/install.py" rollback \
  --bundle-root "$BUNDLE_ROOT" \
  --expected-distribution-commit "$EXPECTED_DISTRIBUTION_COMMIT" \
  --blender "$BLENDER_BIN" --codex "$CODEX_BIN" --uv "$UV_BIN" \
  --receipt "$RECEIPT_PATH" ${HANDOFF_ARGS[@]+"${HANDOFF_ARGS[@]}"}
```
<!-- ROLLBACK_END -->
<!-- INSTALLER_COMMANDS_END -->

Rollback verifies the receipt and current host state; the receipt path is not
authorization for a new install. Preserve receipts for audit and future rollback.
Restoring a v1-lease (`inode-v1`) runtime after a reboot renumbered the volume device
yields a runtime whose own launcher cannot start; reinstall the current release instead.

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
  "$CODEX_BIN" plugin marketplace add "$PERSISTENT_MARKETPLACE_ROOT"
MARKETPLACE_NAME="$("$PYTHON_BIN" -I -c \
  'import json,sys;print(json.load(open(sys.argv[1]))["name"])' \
  "$PERSISTENT_MARKETPLACE_ROOT/.agents/plugins/marketplace.json")"
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

If this session prepared a persistent marketplace projection, after private trust
cleanup verify both normal-profile listings read-only. Preserve journal, registration
recovery, cleanup logs, historical projections and receipts. `cleanup_pending` / exit 3
still runs explicit trust cleanup and persistent verification before returning 3;
ordinary errors fail immediately. `cleanup_reference_unproven` means legacy registration
recovery evidence blocks cleanup: keep that evidence and diagnose it manually; do not delete
or rewrite it. Later install/register/finalize retries cleanup. Otherwise
skip this block; inspect-only, verify-only, and rollback do not register a plugin.
<!-- PERSISTENT_MARKETPLACE_VERIFY_BEGIN -->
```bash
REGISTRATION_VERIFY_ARGS=()
if test -n "${REGISTRATION_RECOVERY_DIR:-}"; then
  REGISTRATION_VERIFY_ARGS+=(--recovery "$REGISTRATION_RECOVERY_DIR")
fi
PERSISTENT_SCRIPTS="$PERSISTENT_MARKETPLACE_ROOT/plugins/blender-mcp-installer/scripts"
"$PYTHON_BIN" -I -B -c "$ISOLATED_RUNNER" "$PERSISTENT_SCRIPTS" \
  "$PERSISTENT_SCRIPTS/project_marketplace.py" verify \
  --projection "$PERSISTENT_MARKETPLACE_ROOT" ${REGISTRATION_VERIFY_ARGS[@]+"${REGISTRATION_VERIFY_ARGS[@]}"} \
  --codex "$CODEX_BIN" --home "$HOME" --codex-home "$NORMAL_CODEX_HOME"
printf '%s\n' "$WORKFLOW_JSON"
if test "$WORKFLOW_RC" -eq 3; then exit 3; fi
```
<!-- PERSISTENT_MARKETPLACE_VERIFY_END -->

Record the physical-host gate separately as `SECOND_MAC_CANARY_STATUS: NOT_RUN`
until an independent release operator runs it.
