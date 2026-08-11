# Official Blender MCP Modeling Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the repeatable LLM workflow and evidence mistakes found by the
official Blender MCP modeling validation, without changing product code, the pinned
official checkout, dependencies, or the frozen acceptance baseline.

**Architecture:** Add two new artifacts: one concise operational runbook and one
standard-library audit CLI. Harden the existing repository gate with exactly two lines
so it installs a non-editable package snapshot and refreshes that snapshot after vendor
generation. The runbook owns human/LLM sequencing, Blender safety, upstream mitigations,
and the gate invariant. The CLI owns only machine-verifiable evidence: a single-process
UTC/monotonic journal and dynamic catalog/audit validation. The active modeling audit
records implementation and adversarial-retest evidence; it is not another remediation
mechanism.

**Tech Stack:** Markdown, Python 3.13 standard library, JSON/NDJSON, Git, and the
existing repository checks.

## Global Constraints

- Start from baseline commit `09bf5c2` or a direct descendant containing it.
- Keep product version `0.1.0` and Blender compatibility `>=5.2`; the measured baseline
  remains Blender `5.2.0` on macOS arm64.
- Do not modify ROADMAP, Phase 0 Plan/URS/spec, historical audit/evidence/attestation,
  the modeling validation Plan/design, `docs/install.md`,
  `docs/install-official-blender-mcp.md`, its embedded copy, `pyproject.toml`,
  `uv.lock`, tests, product code, Codex config, Blender prefs, or
  `/Users/yeminjie/blender_mcp`. In `scripts/checks.sh`, add only the exact two lines
  specified by Task 1; no other gate edit is allowed.
- Do not add a dependency, pytest file, Blender transaction wrapper, process manager,
  external-checkout patch, or `process-snapshot` CLI subcommand.
- The audit CLI must not hardcode `26`; live/source/config additions approved upstream
  must pass when all normalized inputs and the audit table agree.
- `MODEL-RUN-10` is a soft lifecycle/resource diagnostic only. Do not claim the
  runbook prevents it or that a per-agent cleanup defect was causally proven.
- The historical missing verbatim hypothesis in `MODEL-RUN-11` stays missing. No task
  may invent or reconstruct it.
- Do not use `chflags` except for Task 1 Step 7's recursive sweep of the disposable
  clone's `.venv`; never use it on a real worktree or real environment. Do not set
  `PYTHONPATH` or reduce/skip the 369-test inventory. Use temporary CLI fixtures.

---

## File Structure

- `docs/use-official-blender-mcp.md` — the only durable human/LLM operational runbook;
  it owns sequencing, Blender safety, timing discipline, and upstream mitigations.
- `scripts/official_blender_mcp_audit.py` — the only durable machine helper; it owns
  secure `record` and dynamic `validate`, with standard library only.
- `scripts/checks.sh` — the existing gate hardened by exactly two added lines: force
  non-editable project installation, then refresh the package snapshot after vendor
  generation/checking.
- `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md` — the existing
  active evidence ledger; it records remediation/retest facts but adds no mechanism.
- `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md` — this
  implementation Plan; it is committed only after the pre-implementation zero-finding
  review gate.

## SDD dispatch contract

Tasks 1–5 are implementation Tasks. Each uses one fresh implementer followed by one
fresh standard `subagent-driven-development/task-reviewer-prompt.md` reviewer. That
single reviewer must return both specification and code-quality verdicts; do not create
separate spec and quality reviewers. Task 0 and the terminal/merge phases are
controller-only gates and do not get task briefs.

The controller resolves `SDD_SKILL_ROOT` from the loaded skill path and runs:

```bash
/bin/bash -euo pipefail <<'BASH'
: "${SDD_SKILL_ROOT:?set to the loaded subagent-driven-development skill directory}"
: "${TASK_N:?set implementation Task 1..5}"
case "$TASK_N" in 1|2|3|4|5) ;; *) exit 1 ;; esac
PLAN=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
RUN_DIR=.superpowers/sdd/modeling-remediation
BRIEF="$RUN_DIR/task-$TASK_N-brief.md"
REPORT="$RUN_DIR/task-$TASK_N-report.md"
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
install -d -m 700 "$RUN_DIR"
test ! -e "$BRIEF"
test ! -e "$REPORT"
"$SDD_SKILL_ROOT/scripts/task-brief" "$PLAN" "$TASK_N" "$BRIEF"
test -s "$BRIEF"
test ! -L "$BRIEF"
"$UV" run --quiet --no-project --python 3.13 python - \
  "$PLAN" "$BRIEF" "$TASK_N" <<'PY'
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

plan_path, brief_path = map(Path, sys.argv[1:3])
task_n = sys.argv[3]
plan = plan_path.read_bytes()
brief = brief_path.read_bytes()
headings = {
    "A": b"## Appendix A: Exact runbook bytes\n",
    "B1": b"## Appendix B1 \xe2\x80\x94 recorder-only complete bytes\n",
    "B2": b"## Appendix B2 \xe2\x80\x94 final complete bytes\n",
    "C": b"## Appendix C \xe2\x80\x94 complete adversarial probe\n",
    "D": b"## Appendix D: Exact no-write catalog and journal integration\n",
    "E": b"## Appendix E: Exact external-baseline capture\n",
}
required = {
    "1": ("A",),
    "2": ("B1", "C"),
    "3": ("B2", "C"),
    "4": ("A", "C", "D"),
    "5": ("A", "C", "D"),
}[task_n]
positions = {name: plan.index(heading) for name, heading in headings.items()}
if any(plan.count(heading) != 1 for heading in headings.values()):
    raise RuntimeError("expected one of every Appendix heading")
pieces = [brief]
for name in required:
    start = positions[name]
    end = min((position for position in positions.values() if position > start), default=len(plan))
    pieces.extend((b"\n", plan[start:end]))
payload = b"".join(pieces)
brief_path.write_bytes(payload)
present = tuple(
    name for name, heading in headings.items() if payload.count(heading) == 1
)
if present != required:
    raise RuntimeError(f"unexpected Appendix set: {present!r}")
if task_n == "5":
    for forbidden in (b"Controller Phase", b"merge --ff-only"):
        if forbidden in payload:
            raise RuntimeError(f"Task 5 brief leaked {forbidden!r}")
print(f"brief_sha256={hashlib.sha256(payload).hexdigest()} appendices={','.join(required)}")
PY
test -s "$BRIEF"
test ! -L "$BRIEF"
TASK_BASE="$(git rev-parse HEAD)"
printf 'task=%s\nbase=%s\nbrief=%s\nreport=%s\n' \
  "$TASK_N" "$TASK_BASE" "$BRIEF" "$REPORT"
BASH
```

The helper's third `OUTFILE` argument is mandatory; stdout redirection is forbidden.
The implementer prompt passes only the brief/report paths, one line of scene-setting,
interfaces established by earlier Tasks, and any resolved ambiguity. The brief is the
single exact-value requirements source. The implementer commits and writes `STATUS`,
`TASK_BASE`, all commits, every test command and output, self-review, and concerns to the
report. Its chat return is only status, commits, a one-line test summary, and concerns.

After each implementation or fix round, set a fresh positive `ROUND` and preserve the
original Task base (never `HEAD~1`):

```bash
/bin/bash -euo pipefail <<'BASH'
: "${SDD_SKILL_ROOT:?set the loaded skill directory}"
: "${TASK_N:?set implementation Task 1..5}"
: "${TASK_BASE:?use the base printed before implementer dispatch}"
: "${ROUND:?set a fresh positive review round}"
case "$TASK_N" in 1|2|3|4|5) ;; *) exit 1 ;; esac
case "$ROUND" in 0|*[!0-9]*|'') exit 1 ;; esac
RUN_DIR=.superpowers/sdd/modeling-remediation
BRIEF="$RUN_DIR/task-$TASK_N-brief.md"
REPORT="$RUN_DIR/task-$TASK_N-report.md"
PACKAGE="$RUN_DIR/task-$TASK_N-review-r$ROUND.diff"
REVIEW="$RUN_DIR/task-$TASK_N-review-r$ROUND.md"
test -s "$BRIEF"
test -s "$REPORT"
test ! -e "$PACKAGE"
test ! -e "$REVIEW"
TASK_HEAD="$(git rev-parse HEAD)"
"$SDD_SKILL_ROOT/scripts/review-package" "$TASK_BASE" "$TASK_HEAD" "$PACKAGE"
test -s "$PACKAGE"
PACKAGE_SHA256="$(shasum -a 256 "$PACKAGE" | awk '{print $1}')"
printf 'head=%s\npackage=%s\npackage_sha256=%s\nreview=%s\n' \
  "$TASK_HEAD" "$PACKAGE" "$PACKAGE_SHA256" "$REVIEW"
BASH
```

The reviewer receives the brief, report, package, and the Plan's Global Constraints,
not session history. Its report starts with these exact binding lines:

```text
TASK_HEAD: <40-hex>
PACKAGE_SHA256: <64-hex>
SPEC_VERDICT: PASS
QUALITY_VERDICT: APPROVED
CRITICAL: 0
IMPORTANT: 0
MINOR: 0
```

The controller safely recomputes the package binding and parses the unique ordered
leading block before marking the Task complete. A duplicate, contradictory, or unknown
reserved marker invalidates the whole report:

```bash
/bin/bash -euo pipefail <<'BASH'
: "${TASK_N:?set implementation Task 1..5}"
: "${ROUND:?set the positive review round}"
: "${TASK_HEAD:?reviewed Task HEAD required}"
case "$TASK_N" in 1|2|3|4|5) ;; *) exit 1 ;; esac
case "$ROUND" in 0|*[!0-9]*|'') exit 1 ;; esac
case "$TASK_HEAD" in *[!0-9a-f]*) exit 1 ;; esac
test "${#TASK_HEAD}" = 40
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
RUN_DIR=.superpowers/sdd/modeling-remediation
PACKAGE="$RUN_DIR/task-$TASK_N-review-r$ROUND.diff"
REVIEW="$RUN_DIR/task-$TASK_N-review-r$ROUND.md"
CURRENT_REF="$(git symbolic-ref -q HEAD)"
test "$CURRENT_REF" = refs/heads/codex/official-blender-mcp-install
test "$(git rev-parse HEAD)" = "$TASK_HEAD"
test "$(git rev-parse "$CURRENT_REF")" = "$TASK_HEAD"

"$UV" run --quiet --no-project --python 3.13 python - \
  "$PACKAGE" "$REVIEW" "$TASK_HEAD" <<'PY'
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path

RESERVED = re.compile(
    r"^(?P<key>(?:[A-Z][A-Z0-9_]*_VERDICT)|VERDICT|TASK_HEAD|REVIEWED_HEAD|"
    r"REVIEW_BASE_HEAD|PACKAGE_SHA256|CRITICAL|IMPORTANT|MINOR):"
)


def owned_regular_bytes(raw_path: str) -> bytes:
    path = Path(os.path.abspath(raw_path))
    if os.path.realpath(path) != os.fspath(path):
        raise RuntimeError(f"symlinked path component rejected: {path}")
    before = os.lstat(path)
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.getuid()
    ):
        raise RuntimeError(f"owned regular file required: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file changed while opening: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        current = os.lstat(path)
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file changed while reading: {path}")
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file path changed while reading: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def parse_report(payload: bytes, expected: list[tuple[str, str]]) -> None:
    lines = payload.decode("utf-8").splitlines()
    required = [f"{key}: {value}" for key, value in expected]
    if lines[: len(required)] != required:
        raise RuntimeError("ordered leading binding block differs")
    positions = {key: index for index, (key, _) in enumerate(expected)}
    seen: set[str] = set()
    for index, line in enumerate(lines):
        match = RESERVED.match(line)
        if match is None:
            continue
        key = match.group("key")
        if key not in positions:
            raise RuntimeError(f"unknown reserved marker: {key}")
        if key in seen:
            raise RuntimeError(f"duplicate reserved marker: {key}")
        if index != positions[key]:
            raise RuntimeError(f"reserved marker outside leading block: {key}")
        seen.add(key)
    if seen != set(positions):
        raise RuntimeError("missing reserved marker")


package = owned_regular_bytes(sys.argv[1])
review = owned_regular_bytes(sys.argv[2])
task_head = sys.argv[3]
package_sha = hashlib.sha256(package).hexdigest()
parse_report(
    review,
    [
        ("TASK_HEAD", task_head),
        ("PACKAGE_SHA256", package_sha),
        ("SPEC_VERDICT", "PASS"),
        ("QUALITY_VERDICT", "APPROVED"),
        ("CRITICAL", "0"),
        ("IMPORTANT", "0"),
        ("MINOR", "0"),
    ],
)
print(f"TASK_REVIEW_READY head={task_head} package_sha256={package_sha}")
PY
BASH
```

Every finding is fixed by the owning implementer. Its report is appended with the
covering test file, command, and output; then a new package and one new standard review
are generated. Only a clean combined verdict permits
`Task N: complete (commits <base7>..<head7>, spec pass, quality approved)` in
`.superpowers/sdd/progress.md`.

All subagent dispatches use `fork_turns="none"`. Tasks 1–3 use `gpt-5.6-terra` at
medium effort; Tasks 4–5 and combined Task, Plan, or whole-branch reviewers use
`gpt-5.6-sol` at high effort. The terminal requesting-code-review reviewer uses the
most capable available model. Every reviewer receives file paths rather than copied
session history.

---

### Task 0: Adversarially audit this plan before implementation

**Files:**
- Modify only when a finding requires correction:
  `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`

**Gate:** No implementation task may start until three fresh read-only reviewers all
approve the same Plan bytes with no Critical, Important, or Minor finding.

Use exactly these ignored review reports for round `N`:

```text
.superpowers/sdd/modeling-remediation/plan-spec-review-rN.md
.superpowers/sdd/modeling-remediation/plan-execution-review-rN.md
.superpowers/sdd/modeling-remediation/plan-ponytail-review-rN.md
```

For this self-contained post-cleanup evidence revision set `N=18`; do not reuse any
r13/r15/r16/r17 report or aborted r14 reviewer state. If r18 finds anything, use the
next unused integer for the complete corrected bytes.

Before dispatch, compute `shasum -a 256` for the Plan. Each reviewer prompt and report
must name that digest; a verdict on another digest is invalid. This is a tracked
Plan-only fix-forward revision: require the Plan to be the only tracked worktree change,
run `git diff --check`, and also run `git diff --no-index --check /dev/null "$PLAN"`,
accepting only the normal no-index difference status and empty diagnostic output.

```bash
/bin/bash -euo pipefail <<'BASH'
PLAN=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
test "$(git status --short --untracked-files=all)" = " M $PLAN"
git diff --check
set +e
NOINDEX_OUTPUT="$(git diff --no-index --check /dev/null "$PLAN" 2>&1)"
NOINDEX_EXIT=$?
set -e
test "$NOINDEX_EXIT" = 1
test -z "$NOINDEX_OUTPUT"
shasum -a 256 "$PLAN"
BASH
```

- [ ] **Step 1: Run the specification and safety review**

The reviewer must compare this Plan to the approved baseline audit, the writing-plans
requirements, AGENTS.md, and the frozen-file boundary. It must challenge CLI schemas,
failure/recovery evidence ordering, catalog dynamism, path/symlink handling, exact
commands, commit scopes, full-gate expectations, and merge safety.

- [ ] **Step 2: Run the mechanical execution/state-machine review**

The reviewer must extract every executable fence, run safe temporary probes, and
challenge task-brief boundaries, exact artifact routing, report parsing, failure
pause/resume, Python-environment rebuilding, terminal freezing, immutable reviewed
HEAD binding, first merge, clean fix-forward, and dirty fail-closed behavior.

- [ ] **Step 3: Run the Ponytail/YAGNI adversarial review**

The reviewer must look only for unnecessary code, duplicated mechanisms, speculative
features, hidden test/dependency expansion, hardcoded local assumptions, and any simpler
standard-library/native alternative. It must verify that exactly two new remediation
artifacts plus one existing-gate hardening remain justified and that `MODEL-RUN-10` did
not expand the CLI.

- [ ] **Step 4: Fix and repeat until the Plan is clean**

For every finding, edit only this Plan, run both tracked and full-file whitespace checks, compute
a new digest, use new round-specific report paths, and send the complete new bytes back
to three fresh reviewers. Repeat until all three explicitly report zero Critical, zero
Important, and zero Minor findings. Record reviewer verdicts in the three exact ignored
reports.

- [ ] **Step 5: Commit the approved Plan only**

Only then run:

```bash
git add -- docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
git diff --cached --check
git commit -m "docs: revise official MCP modeling remediation plan"
```

Expected: the Plan-only commit is clean. Task 1 is still blocked by Steps 6–7.

- [ ] **Step 6: Verify the executed r1 gate failure and restored environment**

This is a hard fail-closed evidence gate, not a rerun and not a pass. The already
executed exact repository gate reported 368 passed and 1 failed. The failing
`test_cancelled_sdk_client_reaps_its_recorded_process_group` launched
`.venv/bin/blender-codex-server` from a temporary cwd and received
`ModuleNotFoundError: No module named 'server'`. The transaction restored the original
ignored `.venv`, retained the rejected fresh environment at
`.superpowers/sdd/modeling-remediation/task0-step6-environment/rejected.venv`, and
removed the transient `original.venv` backup. The later controlled measurements support
a delayed external workspace metadata sweep that recursively set `UF_HIDDEN` on the
editable project `.pth`; CPython skipped that path hook, while uv did not reproduce the
flag mutation. The responsible process remains unknown.
Record this implementation-environment incident as `POSTPLAN-ENV-01` in prose only.
It is not one of the 24 `MODEL-*` findings and must not enter the audit CLI's literal
issue-ID fields or the runbook disposition table.

Run only this read-only state verification; do not rebuild either environment or rerun
the full gate in Task 0:

```bash
/bin/bash -euo pipefail <<'BASH'
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
FEATURE_ROOT="$(git rev-parse --show-toplevel)"
PLAN=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
VENV="$FEATURE_ROOT/.venv"
ENV_STATE="$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/task0-step6-environment"
REJECTED_VENV="$ENV_STATE/rejected.venv"
ORIGINAL_VENV="$ENV_STATE/original.venv"
EVIDENCE="$FEATURE_ROOT/.superpowers/sdd/modeling-remediation/uv-hidden-flag-research.md"
test "$(pwd -P)" = "$FEATURE_ROOT"
test "$(git branch --show-current)" = codex/official-blender-mcp-install
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git ls-files --error-unmatch "$PLAN" >/dev/null
test "$(git diff-tree --no-commit-id --name-only -r HEAD)" = "$PLAN"
test -z "${PYTHONPATH-}"
git check-ignore -q -- .venv/
git check-ignore -q -- .superpowers/sdd/modeling-remediation/task0-step6-environment/
test -d "$VENV"
test ! -L "$VENV"
test -d "$ENV_STATE"
test ! -L "$ENV_STATE"
test -d "$REJECTED_VENV"
test ! -L "$REJECTED_VENV"
test ! -e "$ORIGINAL_VENV"
test ! -L "$ORIGINAL_VENV"
test -f "$EVIDENCE"
test ! -L "$EVIDENCE"
PYTHON_31313="$("$UV" python find 3.13.13)"
case "$PYTHON_31313" in /*) ;; *) echo 'STOP: uv Python 3.13.13 absent' >&2; exit 1 ;; esac
"$PYTHON_31313" - "$FEATURE_ROOT" "$VENV" "$ENV_STATE" "$REJECTED_VENV" \
  "$EVIDENCE" <<'PY'
from pathlib import Path
import hashlib
import os
import stat
import sys

root, venv, state, rejected, evidence = map(Path, sys.argv[1:])
for path in (root, venv, state, rejected):
    if Path(os.path.realpath(path)) != path:
        raise SystemExit(f"STOP: symlinked path rejected: {path}")
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"STOP: ordinary directory required: {path}")
    if info.st_uid != os.getuid() or info.st_mode & stat.S_IWOTH:
        raise SystemExit(f"STOP: unsafe ownership/mode: {path}")
if venv.parent != root or venv.name != ".venv":
    raise SystemExit("STOP: live .venv identity differs")
if state.parent.parent.parent.parent != root:
    raise SystemExit("STOP: environment state escaped the repository")
if rejected.parent != state or rejected.name != "rejected.venv":
    raise SystemExit("STOP: rejected environment identity differs")
live = venv.lstat()
failed = rejected.lstat()
if (live.st_dev, live.st_ino) == (failed.st_dev, failed.st_ino):
    raise SystemExit("STOP: restored and rejected environments share identity")
if not hasattr(stat, "UF_HIDDEN") or not hasattr(failed, "st_flags"):
    raise SystemExit("STOP: macOS hidden-flag inspection unavailable")
pth = rejected / "lib" / "python3.13" / "site-packages" / "_editable_impl_blender_codex.pth"
entry = pth.lstat()
if stat.S_ISLNK(entry.st_mode) or not stat.S_ISREG(entry.st_mode):
    raise SystemExit("STOP: rejected editable .pth is not a regular file")
if entry.st_uid != os.getuid() or not entry.st_flags & stat.UF_HIDDEN:
    raise SystemExit("STOP: rejected editable .pth no longer carries UF_HIDDEN")
evidence_info = evidence.lstat()
if stat.S_ISLNK(evidence_info.st_mode) or not stat.S_ISREG(evidence_info.st_mode):
    raise SystemExit("STOP: regular failure evidence required")
if evidence_info.st_uid != os.getuid() or evidence_info.st_mode & stat.S_IWOTH:
    raise SystemExit("STOP: unsafe failure evidence ownership/mode")
payload = evidence.read_bytes()
if hashlib.sha256(payload).hexdigest() != (
    "ebd57eee1c24b90c4a68d71b112c2682cf879f5ca345231960071661131edbd5"
):
    raise SystemExit("STOP: Task 0 failure evidence digest differs")
for literal in (
    b"**1 failed, 368 passed**",
    b"ModuleNotFoundError: No module named 'server'",
    b"The evidence does **not** support the claim that uv 0.12.2 sets",
):
    if literal not in payload:
        raise SystemExit(f"STOP: Task 0 evidence literal absent: {literal!r}")
print(
    "TASK0_R1_FAILURE_VERIFIED passed=368 failed=1 "
    "original_restored=true rejected_hidden_pth=true"
)
PY
test -z "${PYTHONPATH-}"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
BASH
```

Expected: the one exact marker above. No command in this Step changes flags, installs a
package, mutates `.venv`, reruns pytest, or converts the failed gate into success.
Only Task 1 is authorized to harden `scripts/checks.sh`; Tasks 2–5 remain blocked until
Task 1 commits the final gate bytes and passes its post-commit full 369-test/tmp-cwd
entrypoint gate.

- [ ] **Step 7: Capture the external baseline**

Only after Step 6 verifies the failed r1 evidence and restored original environment,
run Appendix E's exact `capture` block. It creates the
ignored mode-`0700`
`.superpowers/sdd/modeling-remediation/external-baseline` directory and its one
mode-`0600` `baseline.json`. Generic unchanged `paths` contain only resolved
path/type/UID/mode/hash metadata for frozen external inputs; the mutable
`scripts/checks.sh` path is not added there. A separate `gate_provenance` object binds
the baseline feature commit's checks Git blob, old checks SHA-256
`c0798f66b9b1ac6ed7e85b772adc0cca24b6c5f69ebb5df2e1b742a7c745307e`, and retained
failure-evidence SHA-256
`ebd57eee1c24b90c4a68d71b112c2682cf879f5ca345231960071661131edbd5`.
The record also binds feature HEAD, immutable `review_base_head`,
`initial_main_anchor`, and official source HEAD/clean.

Record the Task 0 capture failure after the historical
`/private/tmp/bcx-official-mcp-modeling-20260810` run root was observed absent on
2026-08-11 as `POSTPLAN-ENV-02` in prose only. All five 2026-08-10 fixture/PNG hashes remain in this
Plan and the retained raw run report. Before Task 4, the active audit contains the two
PNG hash literals and the historical modeling/visual conclusions, but not the three
fixture hash literals; Task 4 must add the complete five-hash historical ledger. The
ledger is:

- `library_source.blend`:
  `9e34c9a96ec59a1f7ceda557dfd77c3ca3a461f929e477ae50588176a61a8f62`;
- `lamp_fixture.blend`:
  `248c0f22fd46d9b45cb93fd736a1decec94c436fcb66bf5bf2fa01843a46ff12`;
- `lamp_fixture_persisted_missing.blend`:
  `bd5ac7a7955e70c8902ac46ac753975e4b60605b6eb30cca759765d68a54b9f5`;
- `thumbnail.png`:
  `7a4799be69540a5faa24080d6d24cdfd23050ef692651d5be92881aae66f4bcb`;
- `viewport.png`:
  `1bde67e12dbb50fb7dc1a94a69b484dbcfa410e60164b484a475b2c5fdcd8e14`.

The responsible cleanup process is unknown; ordinary temporary-directory cleanup is a
supported inference, not a directly observed attribution. The exact terminal symptom was
`RuntimeError: required path missing: /private/tmp/bcx-official-mcp-modeling-20260810`.
The failed capture was not separately timed and stopped before creating
`.superpowers/sdd/modeling-remediation/external-baseline` or `baseline.json`; no partial
baseline exists. The binary files are unavailable and are not remeasured. Two same-script
Blender 5.2 recovery attempts produced different `.blend` hashes from each other and
from history: attempt 1 produced library
`71bf2b089c360a8cc74c6bb5071fe87c54fd9327e71b22a0fcf7c87a7d4a889d` and fixture
`80e300e8d9ffd02620df7568a87ecf6699c93086fc7419de413f8cc0fc5bbd3f`
(`950.192` ms process wall, `99.744` ms Blender-internal); attempt 2 produced library
`d97c8d806505a2d0ade7063644c5de0b3f30c31dc4b4f91153989de65b680ae8` and fixture
`30e34c1836486cf4418b51790ba431685de368ebc5d9444e032974170478b5aa`
(`78.753` ms Blender-internal; process wall was not separately bracketed). Reconstructed
bytes must not be substituted for the historical artifacts. `POSTPLAN-ENV-02` is not a
25th `MODEL-*` finding and must not enter the
runbook disposition table or audit-CLI issue-ID fields.

At capture both main fields equal the uniquely resolved clean main HEAD. It never prints
or stores config/preference contents or unrelated values. Any absent, symlinked,
foreign-owned, non-regular, or world-writable protected input stops the run. Tasks 4–5 pass
`EXPECTED_MAIN_ANCHOR=<initial_main_anchor>` to Appendix D.

---

### Task 1: Add the operational runbook

**Files:**
- Create: `docs/use-official-blender-mcp.md`
- Modify: `scripts/checks.sh` (exactly two added lines)

**Interfaces:**
- Consumes: the approved root-cause table in
  `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`.
- Produces: one LLM-executable procedure for safe official MCP modeling and evidence
  capture, plus a deterministic non-editable repository gate. The runbook does not
  install, patch, or invoke Blender by itself.

- [ ] **Step 1: Prove the runbook is absent and freeze scope**

Run:

```bash
/bin/bash -euo pipefail <<'BASH'
test ! -e docs/use-official-blender-mcp.md
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(shasum -a 256 scripts/checks.sh | awk '{print $1}')" = \
  c0798f66b9b1ac6ed7e85b772adc0cca24b6c5f69ebb5df2e1b742a7c745307e
test "$(rg -c '^source = \{ editable = "\." \}$' uv.lock)" = 1
test "$(git rev-parse 09bf5c2^{commit})" = \
  "$(git merge-base 09bf5c2 HEAD)"
BASH
```

Expected: exit `0`; no pre-existing file is overwritten.

- [ ] **Step 2: Write only the durable rules justified by the audit**

Create `docs/use-official-blender-mcp.md` with these concise sections:

1. **Boundary and prerequisites** — official `blender` MCP only, pinned source/SDK,
   Blender `>=5.2`, disposable factory scene, no user `.blend` open/save/overwrite.
2. **Shell and SDD discipline** — execute Bash-labelled fences with `/bin/bash`; never
   use zsh special variable `path`; pass the task-brief helper's explicit output path;
   use a run-scoped brief/report stem and assert output absence/presence; document the
   repository gate's `UV_NO_EDITABLE=1`, post-vendor forced package refresh, tmp-cwd
   entrypoint contract, prohibition on `chflags`, `PYTHONPATH`, or fewer tests, and
   `POSTPLAN-ENV-01` as prose outside the 24-row `MODEL-*` disposition map.
3. **Preflight and exact write scope** — one Blender listener, unsaved factory scene,
   exact allowed Scene/World/collection/datablock writes, target-absence checks.
4. **Locale and identity** — select built-ins by unique stable RNA `node.type`, not
   localized display name; treat `bpy.data.is_dirty` as observation, while filepath,
   sentinel, exact sets/data/parents prove identity.
5. **Transactional phase recovery** — record the raw symptom and verbatim first
   hypothesis before recovery; discard the partial unsaved GUI; wait for one listener;
   re-run complete preflight and replay once, never continue in place.
6. **Interpreter, fixture, and docs contracts** — use absolute uv-managed Python 3.13
   with the effective editable dependencies; inspect response keys before assertions;
   give intentionally missing saved images a fake user; use the source-proven Blender
   operator search form.
7. **Blender 5.2 and upstream mitigations** — discover/read back the render-engine enum;
   document `BLENDER_EEVEE`; cap screenshot PNG responses at 48,000 bytes; state that
   larger screenshot transport and thumbnail `_NEXT` sample logic are upstream limits,
   not locally fixed behavior.
8. **Render scratch** — canonicalize Blender's real tempdir, validate the owned final
   `blender_mcp` parent, create only that absent `0700` directory, reject symlinks and
   foreign ownership, use unique absent basenames, never overwrite, and verify PNG
   magic/ownership/hash before copying.
9. **Timing and evidence** — start the audit CLI `record` process before work, use one
   `clock_id`, pair stage/call start/end events, separate MCP/internal/residual time,
   call residual only `unattributed orchestration`, and run `validate` before claims.
10. **Soft process diagnostic and cleanup** — record before/after `ps` count/RSS and
    the unique 9876 listener; do not kill individual stdio servers mid-run; after all
    agents finish, normally exit/restart Codex Desktop if retained pairs need cleanup.

Include a short checklist mapping these rules to literal issue IDs. Say explicitly that
`MODEL-RUN-08/09/10` and `MODEL-PLAN-09` are mitigated/observed rather than repaired,
and that `MODEL-RUN-11` is prevented only for future runs.

- [ ] **Step 3: Harden the existing gate with exactly two lines**

Apply only this diff to `scripts/checks.sh`:

```patch
*** Begin Patch
*** Update File: scripts/checks.sh
@@
 export PYTHONDONTWRITEBYTECODE=1
+export UV_NO_EDITABLE=1
@@
 "$UV_BIN" run --frozen python scripts/vendor_protocol.py            # 生成
 "$UV_BIN" run --frozen python scripts/vendor_protocol.py --check    # 检查 2
+"$UV_BIN" sync --frozen --python 3.13 --reinstall-package blender-codex
 "$UV_BIN" run --frozen python scripts/nested_import_smoke.py        # 检查 3
*** End Patch
```

The first line makes every project sync/run in the gate non-editable. The second
rebuilds the installed `blender-codex` snapshot only after vendor generation and its
check, so nested import, the tmp-cwd console entrypoint, and pytest see the current
tracked sources. Do not add `chflags`, `PYTHONPATH`, a second script, or a test skip.

- [ ] **Step 4: Run the deterministic pre-commit contracts**

Run Appendix A's exact uv-Python 3.13 probe. It asserts the file is a regular
non-symlink, contains each section heading and the exact 24-ID disposition map, and
rejects false fix claims, `_NEXT` as the 5.2 engine, a 3 MB screenshot recommendation,
instructions to kill retained servers, or a gate workaround using a `chflags` command,
a `PYTHONPATH` assignment, or fewer tests. Expected: `issue_rows=24` and
`contract=ok`.

Then prove the gate change is exactly two additions and is valid Bash:

```bash
/bin/bash -euo pipefail <<'BASH'
test "$(git diff --numstat -- scripts/checks.sh)" = \
  $'2\t0\tscripts/checks.sh'
test "$(git diff --unified=0 -- scripts/checks.sh | rg '^\+[^+]')" = \
  $'+export UV_NO_EDITABLE=1\n+"$UV_BIN" sync --frozen --python 3.13 --reinstall-package blender-codex'
/bin/bash -n scripts/checks.sh
git diff --check
BASH
```

Expected: exit `0`; no full gate runs against an uncommitted tree.

- [ ] **Step 5: Commit the final two-file Task 1 bytes**

Run:

```bash
git diff --check
git add -- docs/use-official-blender-mcp.md scripts/checks.sh
git diff --cached --check
git commit -m "docs: add official MCP runbook and harden checks"
```

Expected: the commit contains exactly the new runbook and the two-line
`scripts/checks.sh` hardening; the test inventory remains 369 and the worktree is
clean.

- [ ] **Step 6: Run the clean post-commit full gate and tmp-cwd entrypoint**

Run this exact self-contained gate only after Step 5 commits the final bytes:

```bash
/bin/bash -euo pipefail <<'BASH'
FEATURE_ROOT="$(git rev-parse --show-toplevel)"
TASK1_HEAD="$(git rev-parse HEAD)"
FOCUSED_CWD=""
cleanup() {
  if [ -n "$FOCUSED_CWD" ]; then
    rmdir -- "$FOCUSED_CWD" 2>/dev/null || true
  fi
}
trap cleanup EXIT
test "$(pwd -P)" = "$FEATURE_ROOT"
test -z "${PYTHONPATH-}"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
./scripts/checks.sh
test "$(git rev-parse HEAD)" = "$TASK1_HEAD"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
FOCUSED_CWD="$(mktemp -d /private/tmp/blender-codex-task1.XXXXXX)"
test "$("$FEATURE_ROOT/.venv/bin/python" -c \
  'import os,sys; print(os.path.realpath(sys.argv[1]))' "$FOCUSED_CWD")" = \
  "$FOCUSED_CWD"
(
  cd "$FOCUSED_CWD"
  PYTHONDONTWRITEBYTECODE=1 "$FEATURE_ROOT/.venv/bin/python" -P - \
    "$FEATURE_ROOT/.venv" <<'PY'
from pathlib import Path
import site
import sys

venv = Path(sys.argv[1])
if not sys.flags.safe_path or Path(sys.prefix) != venv:
    raise SystemExit("STOP: Task 1 safe-path venv contract failed")
site_roots = [
    path for path in map(Path, site.getsitepackages()) if path.is_relative_to(venv)
]
if len(site_roots) != 1:
    raise SystemExit("STOP: expected one Task 1 site-packages directory")
site_root = site_roots[0]
if list(site_root.glob("*_editable_impl_blender_codex.pth")):
    raise SystemExit("STOP: editable project hook remains")
import server
if Path(server.__file__).resolve() != site_root / "server" / "__init__.py":
    raise SystemExit("STOP: server did not import from the installed snapshot")
print("TMP_CWD_IMPORT_GREEN module=server origin=site-packages")
PY
  PYTHONDONTWRITEBYTECODE=1 \
    "$FEATURE_ROOT/.venv/bin/blender-codex-server" </dev/null
  echo 'TMP_CWD_ENTRYPOINT_GREEN exit=0'
)
rmdir -- "$FOCUSED_CWD"
FOCUSED_CWD=""
git diff --check
test "$(git rev-parse HEAD)" = "$TASK1_HEAD"
test -z "${PYTHONPATH-}"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
printf 'TASK1_FULL_GATE_GREEN head=%s tests=369 install=noneditable\n' "$TASK1_HEAD"
BASH
```

Expected: `./scripts/checks.sh` reports all 369 tests plus Ruff, mypy, vendor,
nested-import, and `ALL CHECKS PASSED`; the tmp-cwd lane reports
`TMP_CWD_IMPORT_GREEN module=server origin=site-packages`,
`TMP_CWD_ENTRYPOINT_GREEN exit=0`; the final marker binds the
clean committed HEAD. If it fails, Task 1 remains incomplete: fix forward within Task
1's two-file scope, commit the new final bytes, rerun Steps 4 and 6 on the new clean
HEAD, and obtain the combined Task 1 review. Tasks 2–5 remain blocked until this gate is
green. In this real-worktree step, do not use `chflags`, set `PYTHONPATH`, or
reduce/skip tests. The sole `chflags` exception is the explicitly bounded disposable
clone adversary in Step 7 below.

Task 1 report raw-marker contract: after Steps 6 and 7 both pass, append exactly one
raw output line for each of `TASK1_FULL_GATE_GREEN`, `STALE_SNAPSHOT_NEGATIVE`,
`STALE_SNAPSHOT_REFRESH`, `HIDDEN_SWEEP_GREEN`, and
`TASK1_DISPOSABLE_ADVERSARY_GREEN` to `task-1-report.md`. The machine verifier selects
only complete lines beginning with a marker and requires one of each; the report may
still preserve the exact marker-bearing commands required by the general SDD contract.
Do not repeat a raw output line in prose. Those five raw lines carry the old/current
adapter SHA-256 values and the common final Task 1 HEAD.

- [ ] **Step 7: Prove stale-snapshot refresh and hidden-sweep resistance in one disposable clone**

This adversary never writes the real feature worktree, its `.venv`, main, or a ref. It
uses historical committed source rather than an artificial marker: at
`STALE_BASE=4f1913c364c995c93432bb24b1cc3c9ad1b8590f`,
`server/mcp/adapter.py` has SHA-256
`48b21860a2c8c76a5f66ee7fc41fe5ad5f7e61fba4fa17abb6f0634dc8fb0506`.
Install that old tree non-editably, detach the clone at Task 1's final HEAD, and prove
an ordinary frozen sync leaves the installed adapter stale. Then run the exact
repository gate, including all 369 tests, and prove it refreshes the installed adapter
to the current committed source. Finally apply a recursive hidden sweep only to the
disposable clone's `.venv` and repeat the safe-path external import and real console
entrypoint probes. Run:

```bash
/bin/bash -euo pipefail <<'BASH'
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
case "$UV_BIN" in /*) ;; *) echo 'STOP: UV_BIN must be absolute' >&2; exit 1 ;; esac
export GIT_NO_REPLACE_OBJECTS=1
FEATURE_ROOT="$(git rev-parse --show-toplevel)"
TASK1_HEAD="$(git rev-parse HEAD)"
STALE_BASE=4f1913c364c995c93432bb24b1cc3c9ad1b8590f
STALE_ADAPTER_SHA=48b21860a2c8c76a5f66ee7fc41fe5ad5f7e61fba4fa17abb6f0634dc8fb0506
DISPOSABLE_ROOT=""
CLONE_ROOT=""
PROBE_CWD=""

validate_and_remove() {
  root="$1"
  "$UV_BIN" run --quiet --no-project --python 3.13 python - "$root" <<'PY'
from pathlib import Path
import os
import re
import stat
import sys

root = Path(sys.argv[1])
absolute = Path(os.path.abspath(root))
if absolute != root or Path(os.path.realpath(root)) != root:
    raise SystemExit("STOP: disposable root is not canonical")
if root.parent != Path("/private/tmp") or re.fullmatch(
    r"blender-codex-task1-stale\.[A-Za-z0-9]+", root.name
) is None:
    raise SystemExit("STOP: disposable root identity differs")
info = root.lstat()
if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
    raise SystemExit("STOP: disposable root must be an ordinary directory")
if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
    raise SystemExit("STOP: disposable root must be current-UID mode 0700")
PY
  /bin/rm -rf -- "$root"
}

cleanup() {
  rc=$?
  trap - EXIT
  if [ -n "$DISPOSABLE_ROOT" ]; then
    validate_and_remove "$DISPOSABLE_ROOT"
  fi
  exit "$rc"
}
trap cleanup EXIT

test "$(pwd -P)" = "$FEATURE_ROOT"
test -z "${PYTHONPATH-}"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git cat-file -e "$STALE_BASE^{commit}"
test "$(git show "$STALE_BASE:server/mcp/adapter.py" | shasum -a 256 | awk '{print $1}')" = \
  "$STALE_ADAPTER_SHA"

DISPOSABLE_ROOT="$(mktemp -d /private/tmp/blender-codex-task1-stale.XXXXXX)"
CLONE_ROOT="$DISPOSABLE_ROOT/repo"
PROBE_CWD="$DISPOSABLE_ROOT/probe"
test ! -e "$CLONE_ROOT"
git clone --quiet --no-local --no-hardlinks "$FEATURE_ROOT" "$CLONE_ROOT"
install -d -m 700 "$PROBE_CWD"
git -C "$CLONE_ROOT" checkout --quiet --detach "$STALE_BASE"
(
  cd "$CLONE_ROOT"
  UV_NO_EDITABLE=1 "$UV_BIN" sync --frozen --python 3.13
)

installed_adapter_sha() {
  (
    cd "$PROBE_CWD"
    PYTHONDONTWRITEBYTECODE=1 "$CLONE_ROOT/.venv/bin/python" -P - \
      "$CLONE_ROOT/.venv" <<'PY'
from pathlib import Path
import hashlib
import site
import sys

venv = Path(sys.argv[1])
if not sys.flags.safe_path or Path(sys.prefix) != venv:
    raise SystemExit("STOP: disposable safe-path venv contract failed")
roots = [Path(path) for path in site.getsitepackages() if Path(path).is_relative_to(venv)]
if len(roots) != 1:
    raise SystemExit("STOP: expected one disposable site-packages directory")
import server.mcp.adapter as adapter
adapter_path = Path(adapter.__file__).resolve()
if not adapter_path.is_relative_to(roots[0]):
    raise SystemExit("STOP: adapter did not import from the disposable installed snapshot")
print(hashlib.sha256(adapter_path.read_bytes()).hexdigest())
PY
  )
}

test "$(installed_adapter_sha)" = "$STALE_ADAPTER_SHA"
git -C "$CLONE_ROOT" checkout --quiet --detach "$TASK1_HEAD"
test -z "$(git -C "$CLONE_ROOT" status --porcelain=v1 --untracked-files=all)"
CURRENT_ADAPTER_SHA="$(shasum -a 256 "$CLONE_ROOT/server/mcp/adapter.py" | awk '{print $1}')"
test "$CURRENT_ADAPTER_SHA" != "$STALE_ADAPTER_SHA"
(
  cd "$CLONE_ROOT"
  UV_NO_EDITABLE=1 "$UV_BIN" sync --frozen --python 3.13
)
test "$(installed_adapter_sha)" = "$STALE_ADAPTER_SHA"
printf 'STALE_SNAPSHOT_NEGATIVE ordinary_sync=stale adapter_sha256=%s\n' \
  "$STALE_ADAPTER_SHA"

(cd "$CLONE_ROOT" && ./scripts/checks.sh)
test "$(installed_adapter_sha)" = "$CURRENT_ADAPTER_SHA"
printf 'STALE_SNAPSHOT_REFRESH gate=pass tests=369 adapter_sha256=%s\n' \
  "$CURRENT_ADAPTER_SHA"

/usr/bin/chflags -R hidden "$CLONE_ROOT/.venv"
(
  cd "$PROBE_CWD"
  PYTHONDONTWRITEBYTECODE=1 "$CLONE_ROOT/.venv/bin/python" -P - \
    "$CLONE_ROOT/.venv" <<'PY'
from pathlib import Path
import site
import stat
import sys

venv = Path(sys.argv[1])
if not sys.flags.safe_path or Path(sys.prefix) != venv:
    raise SystemExit("STOP: hidden readback requires the disposable safe-path venv")
if not hasattr(stat, "UF_HIDDEN"):
    raise SystemExit("STOP: macOS hidden-flag inspection unavailable")
roots = [Path(path) for path in site.getsitepackages() if Path(path).is_relative_to(venv)]
if len(roots) != 1:
    raise SystemExit("STOP: expected one disposable site-packages directory")
pths = sorted(roots[0].glob("*.pth"))
if not pths:
    raise SystemExit("STOP: expected a disposable site-packages .pth")
server_path = roots[0] / "server" / "__init__.py"
entrypoint = venv / "bin" / "blender-codex-server"
for path in (venv, *pths, server_path, entrypoint):
    info = path.lstat()
    if not hasattr(info, "st_flags") or not info.st_flags & stat.UF_HIDDEN:
        raise SystemExit(f"STOP: UF_HIDDEN readback failed: {path}")
PY
)
test "$(installed_adapter_sha)" = "$CURRENT_ADAPTER_SHA"
(
  cd "$PROBE_CWD"
  PYTHONDONTWRITEBYTECODE=1 "$CLONE_ROOT/.venv/bin/blender-codex-server" </dev/null
)
printf 'HIDDEN_SWEEP_GREEN flags=verified import=safe-path entrypoint=real exit=0\n'
test "$(git -C "$CLONE_ROOT" rev-parse HEAD)" = "$TASK1_HEAD"
test -z "$(git -C "$CLONE_ROOT" status --porcelain=v1 --untracked-files=all)"

REMOVED_ROOT="$DISPOSABLE_ROOT"
validate_and_remove "$DISPOSABLE_ROOT"
DISPOSABLE_ROOT=""
test ! -e "$REMOVED_ROOT"
trap - EXIT
test "$(git rev-parse HEAD)" = "$TASK1_HEAD"
test -z "${PYTHONPATH-}"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
printf 'TASK1_DISPOSABLE_ADVERSARY_GREEN head=%s cleanup=exact\n' "$TASK1_HEAD"
BASH
```

Expected: ordinary sync reports the exact historical stale SHA; the exact gate reports
369 tests and the current source SHA; the recursive hidden sweep is read back as
`UF_HIDDEN` on the `.venv`, every site-packages `.pth`, the installed server, and the
real entrypoint before a subsequent safe-path import and real entrypoint run remain
green; the validated `/private/tmp` root is absent; the real feature HEAD/status and
`PYTHONPATH` are unchanged. Append the unique literal `HIDDEN_SWEEP_GREEN
flags=verified import=safe-path entrypoint=real exit=0` output line, the other literal
output markers, old/current adapter SHA-256 values, and final Task 1 HEAD to
`task-1-report.md`.

---

### Task 2: Add the secure long-lived recorder

**Files:**
- Create: `scripts/official_blender_mcp_audit.py`

**Interfaces:**
- `record --output PATH`: read one JSON object per stdin line in one long-lived process;
  add one generated `clock_id`, sequence, `recorded_at_utc`, and
  `time.monotonic_ns()`; append one NDJSON object per input line, then flush and fsync.
  The exact parent must be a current-UID, non-symlink `0700` directory. Create the
  output with `O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW` and mode `0600`, then verify it with
  `fstat`; existing and symlink targets fail unchanged.

- [ ] **Step 1: Run the recorder RED probe**

Write the exact ignored probe from Appendix C to the Task 2 run directory and run its
`record-red` case with uv-managed Python 3.13. Expected RED category:
`SCRIPT_ABSENT`; no repository file is written.

- [ ] **Step 2: Write the exact recorder-only bytes**

Write Appendix B1 exactly. Use only the Python standard library and do not redesign the
schema. This first commit exposes only `record`; `validate` must still be an argparse
invalid choice. The final schema is documented here so the second Task can extend it
without changing recorder behavior. Appendix B1 has only `record`; Appendix B2 has
exactly `record` and `validate`:

- final Appendix B2 has one `argparse` parser with exactly `record` and `validate`
  subcommands; recorder-only Appendix B1 has exactly `record`;
- one generated UUID `clock_id` per `record` process;
- RFC 3339 UTC strings ending in `Z` and integer monotonic nanoseconds;
- exact start input: `event_id`, `kind="start"`, `scope` (`task|stage|call`),
  `stage`, integer `attempt`, and nullable `recovery_of`; exact end input: the same
  six identity fields with `kind="end"`, plus `outcome` (`pass|fail|deviation`) and
  an `issue_ids` string array;
- exactly one original `scope="task"` pair is required; its start is the first event
  and its end is the last event, and every stage/call event occurs while that Task is
  open;
- an end may additionally carry finite nonnegative JSON number `internal_ms`; paired
  monotonic endpoints, not a caller-supplied field, are the authoritative wall time;
- a fail end additionally requires nonblank `symptom` and `first_hypothesis`;
  originals require `attempt=0` and `recovery_of=null`; a recovery start requires a
  positive attempt and `recovery_of=<failed event_id>`, whose complete fail end must
  already have been validated, flushed, and fsynced by the same recorder;
- reject unknown fields, booleans where integers or numbers are required, duplicate
  IDs, blank strings, malformed issue IDs, non-finite/negative `internal_ms`, and
  caller-supplied generated fields; `issue_ids=[]` is valid only for an ordinary
  non-recovery pass end; fail, deviation, and linked recovery ends require one or more
  literal issue IDs;
- no inferred or reconstructed values; input clock/timestamp fields are rejected;
- no Blender, MCP SDK, subprocess, process inspection, network, or repository writes.

- [ ] **Step 3: Make the recorder probes GREEN**

Run Appendix C `record-green`. It must cover a real pipe, pass and fail events, a
persisted failure before a linked recovery start, unknown/bad fields, unfinished events,
existing target, target symlink, parent symlink/mode, output mode/UID, and inode/hash
preservation on rejected paths.

Run:

```bash
UV="${UV:-$HOME/.local/bin/uv}"
"$UV" run --frozen --python 3.13 ruff check scripts/official_blender_mcp_audit.py
"$UV" run --frozen --python 3.13 mypy --strict \
  scripts/official_blender_mcp_audit.py
"$UV" run --frozen --python 3.13 python -m py_compile \
  scripts/official_blender_mcp_audit.py
git diff --check
```

Expected: `RECORD_GREEN`; Ruff, strict mypy, compile, and whitespace checks pass.

- [ ] **Step 4: Commit the recorder only**

Run:

```bash
git add -- scripts/official_blender_mcp_audit.py
git diff --cached --check
git commit -m "tools: add official Blender MCP audit recorder"
```

Expected: no test file, dependency, lockfile, or product file changes; the commit
contains exactly the script.

---

### Task 3: Add dynamic catalog, table, and journal validation

**Files:**
- Modify: `scripts/official_blender_mcp_audit.py`

**Interfaces:**
- `validate --journal PATH --audit PATH --live-catalog PATH --source-catalog PATH
  --config-catalog PATH`: consume three normalized JSON string arrays, one generic
  Tool-results table, and one completed record journal. Catalog/table equality and
  journal structure are independent evidence lanes.

- [ ] **Step 1: Run the validator RED probe**

Run Appendix C `validate-red` against the recorder-only commit. Expected: argparse
rejects `validate`; the probe reports `VALIDATOR_ABSENT` and makes no tracked change.

- [ ] **Step 2: Replace the script with the exact final bytes**

Replace the file with Appendix B2 exactly. Relative to B1, recorder behavior and error
categories must remain byte-for-byte equivalent. Validator requirements are:

- safe-open all five inputs as current-UID, non-symlink regular files and verify the
  `lstat`/`fstat` inode identity; reject unsafe inputs before parsing;
- parse unique nonblank catalogs and compare all three by dynamic `Counter`;
- parse exactly one exact seven-column table inside `## Tool results`; enforce ordinal
  `1..N`, one paired backtick Tool cell, allowed outcome, finite nonnegative wall,
  nonnegative retry, nonblank observed shape, and exact issue-cell grammar;
- validate a single clock ID, exact sequences, exactly one first/last outer Task pair,
  all stage/call events enclosed by it, start/end `scope` and identity-field equality,
  UTC and monotonic ordering, nonempty literal issue IDs for fail, deviation, and
  linked recovery ends, caller-provided fail fields, and prior failed-end linkage for
  recovery starts;
- print the fixed success/error schemas from Appendix B2. Never hardcode a count.

- [ ] **Step 3: Run the complete adversarial probe**

Run Appendix C `all-green`. It proves three-name and four-name positive inputs, plus
the exact negative category matrix for unsafe files, catalog schema/mismatch, zero or
multiple/bad tables, ordinal/outcome/wall/retry/issue errors, journal JSON/schema,
mixed clocks, sequences, pairing, time reversal, fail fields and recovery ordering.

Run Appendix C's exact B2 commands: targeted Ruff, strict mypy, uv-Python compile, and
`all-green`. Expected: `ALL_GREEN` and all three static checks pass.

- [ ] **Step 4: Commit the final validator only**

Run:

```bash
git diff --check
git add -- scripts/official_blender_mcp_audit.py
git diff --cached --check
git commit -m "tools: add official Blender MCP audit validator"
```

Expected: only the script changes; tests/dependencies/lockfiles remain unchanged.

---

### Task 4: Integrate the runbook and CLI in a disposable audit replay

**Files:**
- Modify: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`
- Create ignored through the SDD contract:
  `.superpowers/sdd/modeling-remediation/task-4-report.md`

**Interfaces:**
- Consumes: Tasks 1-3 plus the already recorded normalized live/source/config catalog
  evidence and dynamic Tool-results table.
- Produces: a fresh machine-validated journal and implementation evidence. It does not
  repeat mutating modeling or rendering.

- [ ] **Step 1: Run a no-write live integration replay**

First change only the active audit's unique heading matching
`^## [1-9][0-9]*-tool results$` to the count-neutral `## Tool results`; assert exactly
one match before replacement and do not alter the table rows. Create a private
temporary directory.

Run the precondition:

```bash
test "$(rg -c '^## [1-9][0-9]*-tool results$' \
  docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md)" = 1
```

Then apply exactly this transition-only diff with `apply_patch`; the legacy count is
not copied into the validator or runbook:

```patch
*** Begin Patch
*** Update File: docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
@@
-## 26-tool results
+## Tool results
*** End Patch
```

Run the exact uv-Python 3.13 collector in Appendix D: its live branch is the already
validated install-manual section 10.2 App Server protocol and accepts dict/list tool
shapes; its source branch extracts only functions with an `@mcp.tool` AST decorator;
its config branch reads only `mcp_servers.blender.enabled_tools` with `tomllib`. It
writes three sorted JSON string arrays and prints only their counts/equality, never
other config fields.

Start `record` through the exact FIFO/file-descriptor sequence in Appendix D before the
first integration operation. Journal paired events for catalog collection and frozen
state checks. Close the writer FD and wait for the recorder to exit successfully, so
the journal is complete. Only then run `validate` against the active audit and the three
normalized arrays. Measure that final validation with an external uv-Python 3.13
UTC/monotonic bracket; do not put validation of a journal inside the journal itself.
Run Appendix D with this literal extraction command. It executes the one committed
Appendix D Bash fence without creating a persistent helper:

```bash
/bin/bash -euo pipefail <<'BASH'
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
BRIEF=.superpowers/sdd/modeling-remediation/task-4-brief.md
export TASK_N=4
export EXPECTED_ACTIVE_AUDIT_DIRTY=1
export TASK_REPORT=.superpowers/sdd/modeling-remediation/task-4-report.md
export EXPECTED_MAIN_ANCHOR="${EXPECTED_MAIN_ANCHOR:-}"

"$UV_BIN" run --quiet --no-project --python 3.13 python - "$BRIEF" <<'PY' | /bin/bash -euo pipefail
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
heading = "## Appendix D: Exact no-write catalog and journal integration\n"
if text.count(heading) != 1:
    raise RuntimeError("expected one Appendix D heading")
section = text.split(heading, 1)[1].split(
    "\n## Appendix E: Exact external-baseline capture\n", 1
)[0]
if section.count("```bash\n") != 2:
    raise RuntimeError("expected caller-resume and integration Bash fences")
body = section.rsplit("```bash\n", 1)[1]
if body.count("\n```") != 1:
    raise RuntimeError("expected one Appendix D closing fence")
sys.stdout.write(body.split("\n```", 1)[0] + "\n")
PY
BASH
```

Expected: dynamic catalog count currently prints 26, but the validator contains no
literal 26; journal clock/event/error contracts pass.

- [ ] **Step 2: Re-run adversarial helper probes**

In temporary fixtures only, prove validate rejects:

- duplicate, missing and extra catalog/table entries;
- blank outcome/retry/issue fields;
- missing/mixed/unpaired clock events and reversed monotonic time;
- a failure followed by recovery when the symptom or first hypothesis was not first
  persisted;
- malformed issue IDs. Separately repeat the three-name and four-name positive cases.

Re-run the runbook contract probe. Confirm the helper has exactly two subcommands and
imports only standard-library modules.

- [ ] **Step 3: Update remediation evidence**

Append to the active audit under `## Adversarial audit and retest`:

- runbook/script/checks commit IDs and exact scope;
- `POSTPLAN-ENV-01` in separate prose: the Task 0 first exact-gate result as a failure
  (`368 passed, 1 failed`), the exact failing test and tmp-cwd `server` import stderr,
  and the verified rollback to the original `.venv`. State the evidence at its measured
  strength: CPython's skip of the `UF_HIDDEN` editable project `.pth` is the directly
  demonstrated failure mechanism; timing and traversal evidence support an external
  workspace metadata sweep; uv did not reproduce the flag mutation; the exact
  responsible process remains unknown. Do not attribute the sweep to a measured Codex
  process;
- `POSTPLAN-ENV-02` in separate prose: the historical temporary run root observed absent
  on 2026-08-11, with the responsible cleanup process unknown and ordinary temp cleanup
  labeled only as a supported inference; record the failed pre-write Appendix E capture
  with exact terminal symptom
  `RuntimeError: required path missing: /private/tmp/bcx-official-mcp-modeling-20260810`,
  its not-separately-timed status, and the fact that it stopped before creating the
  external-baseline directory or `baseline.json`; then record both same-script Blender
  5.2 recovery attempts and these self-contained measurements: attempt 1 library
  `71bf2b089c360a8cc74c6bb5071fe87c54fd9327e71b22a0fcf7c87a7d4a889d`, fixture
  `80e300e8d9ffd02620df7568a87ecf6699c93086fc7419de413f8cc0fc5bbd3f`,
  process wall `950.192` ms and Blender-internal `99.744` ms; attempt 2 library
  `d97c8d806505a2d0ade7063644c5de0b3f30c31dc4b4f91153989de65b680ae8`, fixture
  `30e34c1836486cf4418b51790ba431685de368ebc5d9444e032974170478b5aa`,
  Blender-internal `78.753` ms and no separately bracketed process wall. State that the
  differing regenerated hashes prove only semantic reconstruction is possible. Preserve
  this exact historical-only ledger: `library_source.blend`
  `9e34c9a96ec59a1f7ceda557dfd77c3ca3a461f929e477ae50588176a61a8f62`,
  `lamp_fixture.blend`
  `248c0f22fd46d9b45cb93fd736a1decec94c436fcb66bf5bf2fa01843a46ff12`,
  `lamp_fixture_persisted_missing.blend`
  `bd5ac7a7955e70c8902ac46ac753975e4b60605b6eb30cca759765d68a54b9f5`,
  `thumbnail.png`
  `7a4799be69540a5faa24080d6d24cdfd23050ef692651d5be92881aae66f4bcb`,
  and `viewport.png`
  `1bde67e12dbb50fb7dc1a94a69b484dbcfa410e60164b484a475b2c5fdcd8e14`;
  retain the historical visual conclusions, state `unavailable and not remeasured`, and
  do not present regenerated bytes as original evidence;
- the baseline old checks SHA-256
  `c0798f66b9b1ac6ed7e85b772adc0cca24b6c5f69ebb5df2e1b742a7c745307e`,
  retained Task 0 evidence SHA-256
  `ebd57eee1c24b90c4a68d71b112c2682cf879f5ca345231960071661131edbd5`,
  Appendix D's final checks SHA-256, Task 1's gate commit/final HEAD, and exactly one
  `task1_report_sha256=<digest>` literal copied from the same Appendix D output;
- the exact two added `scripts/checks.sh` lines, vendor-before-reinstall order, and the
  self-contained 369-test/tmp-cwd entrypoint result;
- Task 1's disposable provenance: stale base
  `4f1913c364c995c93432bb24b1cc3c9ad1b8590f`, historical installed adapter SHA-256
  `48b21860a2c8c76a5f66ee7fc41fe5ad5f7e61fba4fa17abb6f0634dc8fb0506`,
  ordinary-sync stale result, exact-gate current-source SHA-256/result, recursive-hidden
  `.venv`/all `.pth`/installed-server/entrypoint `UF_HIDDEN` readback/result, safe-path
  import/result, real-entrypoint result, the unique combined hidden-sweep marker, and
  exact-root cleanup marker; also record Appendix D's no-replacement stale base/blob
  binding;
  record only retained literal output and measured facts; do not invent a timestamp,
  full console transcript, first hypothesis, or process attribution for the already
  completed Task 0 failure;
- positive and negative fixture results;
- dynamic live/source/config/table count and equality;
- journal event count/clock ID pairing and measured integration time;
- unchanged frozen-file hashes, source pin/clean state, historical-only fixture/PNG
  hashes, their unavailable/not-remeasured status, and the 369-test inventory;
- explicit statement that upstream/runtime observations remain mitigated rather than
  locally patched.

Set `Status: remediation implemented; final adversarial audit pending`.

- [ ] **Step 4: Verify and commit only the active audit**

Run:

```bash
git diff --check
git add -- docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
git diff --cached --check
git commit -m "docs: record official MCP modeling remediation"
```

Expected: the commit contains only the active audit.

---

### Task 5: Run final gates and commit the final tracked bytes

**Files:**
- Modify: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`

**Role boundary:** A fresh implementer owns every Step in this Task. It must not
dispatch reviewers, write a review verdict, or mutate any branch other than the
feature branch. Task orchestration continues outside this brief only after the
implementer has committed, written the Task report, and returned.

- [ ] **Step 1: Run focused probes before finalizing evidence**

Re-run Appendix A's runbook probe, Appendix C's `all-green` helper probe, and Appendix
D's clean lane with this literal extraction command. Leave `EXPECTED_MAIN_ANCHOR`
empty for the initial pre-integration round; a clean Phase M gate-failure round supplies
the prior reviewed HEAD.

```bash
/bin/bash -euo pipefail <<'BASH'
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
BRIEF=.superpowers/sdd/modeling-remediation/task-5-brief.md
export TASK_N=5
export EXPECTED_ACTIVE_AUDIT_DIRTY=0
export TASK_REPORT=.superpowers/sdd/modeling-remediation/task-5-report.md
export EXPECTED_MAIN_ANCHOR="${EXPECTED_MAIN_ANCHOR:-}"

"$UV_BIN" run --quiet --no-project --python 3.13 python - "$BRIEF" <<'PY' | /bin/bash -euo pipefail
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
heading = "## Appendix D: Exact no-write catalog and journal integration\n"
if text.count(heading) != 1:
    raise RuntimeError("expected one Appendix D heading")
section = text.split(heading, 1)[1].split(
    "\n## Appendix E: Exact external-baseline capture\n", 1
)[0]
if section.count("```bash\n") != 2:
    raise RuntimeError("expected caller-resume and integration Bash fences")
body = section.rsplit("```bash\n", 1)[1]
if body.count("\n```") != 1:
    raise RuntimeError("expected one Appendix D closing fence")
sys.stdout.write(body.split("\n```", 1)[0] + "\n")
PY
BASH
```

Expected: all three focused probes pass on the clean pre-finalization tree. Task 3
already ran targeted strict mypy on the helper because repository mypy intentionally
excludes `scripts`.

- [ ] **Step 2: Finalize all tracked evidence**

Update the active audit with the exact focused-probe output, current commit IDs,
external-baseline comparisons, official source pin/clean state, historical fixture/PNG
hashes explicitly labeled unavailable/not remeasured, and the prior validated unsaved
Blender state explicitly labeled historical. Do not claim
that the post-commit full gate has already run. Set `Status: remediation implementation
complete; final gate evidence is bound in the ignored Task 5 report and terminal review`.
No tracked edit follows this final audit commit.

- [ ] **Step 3: Commit only the final audit evidence**

```bash
git diff --check
git add -- docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
git diff --cached --check
git commit -m "docs: close official MCP modeling remediation"
```

Expected: the branch is clean and every tracked remediation byte is final.

- [ ] **Step 4: Run the complete pre-integration gate on the final tracked commit**

Run `export FINAL_TRACKED_HEAD="$(git rev-parse HEAD)"`, then re-run every exact focused
probe command from Step 1 followed by this repository gate:

```bash
/bin/bash -euo pipefail <<'BASH'
: "${FINAL_TRACKED_HEAD:?set to the Task 5 final-audit commit}"
TASK_REPORT=.superpowers/sdd/modeling-remediation/task-5-report.md
test "$(git rev-parse HEAD)" = "$FINAL_TRACKED_HEAD"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
./scripts/checks.sh
git diff --check
test "$(git rev-parse HEAD)" = "$FINAL_TRACKED_HEAD"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
printf 'FINAL_TRACKED_GATE_GREEN head=%s\n' "$FINAL_TRACKED_HEAD" >>"$TASK_REPORT"
BASH
```

Append every exact focused/full-gate command and its literal output to the ignored
Task report as it runs. After the final audit commit, no tracked file may be written;
the ignored Task report is the only evidence file updated. Expected: the Appendix A,
Appendix C, Appendix D, 369-test, Ruff, mypy, vendor, nested-import, whitespace, HEAD,
and cleanliness gates all pass on `FINAL_TRACKED_HEAD`.

- [ ] **Step 5: Finish the ignored Task report and return**

Write exact focused/full-gate commands and output, commit, self-review, and concerns to
`.superpowers/sdd/modeling-remediation/task-5-report.md`, then return. Orchestration
outside this brief runs the one combined per-task review from the SDD contract. Any
finding returns to the implementer; after its fix, rerun covering probes, finalize any
required tracked evidence, commit all tracked fix bytes, run the complete Step 4 gate
on the new HEAD, append the report, and repeat one combined review.

Expected: Task 5 completes only with `SPEC_VERDICT: PASS`,
`QUALITY_VERDICT: APPROVED`, and zero findings.

---

### Task 6: Controller-only numeric boundary — never dispatch

This heading exists only so the installed `task-brief` helper terminates Task 5 at a
numeric Task boundary. The SDD dispatch case permits only Tasks 1–5; do not extract,
dispatch, implement, review, or commit Task 6.

---

### Controller Phase R: Terminal whole-branch review

This is not an implementation Task and has no task brief. It starts only after Tasks
1–5 have clean combined reviews. One immutable package is reviewed by three fresh,
independent reviewers with non-duplicated lenses:

1. the required `requesting-code-review/code-reviewer.md` reviewer owns broad
   correctness, integration, test evidence, and code quality;
2. the independent adversarial reviewer owns specification/safety, evidence accuracy,
   frozen boundaries, fail-closed commands, and merge-state executability;
3. the Ponytail reviewer owns unnecessary/duplicated mechanisms, hidden dependency or
   test expansion, hardcoding, and unsupported claims.

Generate the package and handoff paths:

```bash
/bin/bash -euo pipefail <<'BASH'
: "${SDD_SKILL_ROOT:?set the loaded skill directory}"
: "${ROUND:?set the positive terminal review round}"
case "$ROUND" in 0|*[!0-9]*|'') exit 1 ;; esac
UV="${UV:-$HOME/.local/bin/uv}"
BASELINE=.superpowers/sdd/modeling-remediation/external-baseline/baseline.json
REVIEW_DIR=.superpowers/sdd/modeling-remediation/terminal-r$ROUND
test ! -e "$REVIEW_DIR"
install -d -m 700 "$REVIEW_DIR"
BASE_VALUES="$("$UV" run --quiet --no-project --python 3.13 python - \
  "$BASELINE" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle)
items = (value.get("review_base_head"), value.get("initial_main_anchor"))
if not all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{40}", item) for item in items):
    raise SystemExit("invalid review base/main anchor")
print(*items)
PY
)"
REVIEW_BASE_HEAD="${BASE_VALUES%% *}"
INITIAL_MAIN_ANCHOR="${BASE_VALUES#* }"
REVIEWED_CANDIDATE="$(git rev-parse HEAD)"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git merge-base --is-ancestor "$REVIEW_BASE_HEAD" "$REVIEWED_CANDIDATE"
PACKAGE="$REVIEW_DIR/whole-branch.diff"
"$SDD_SKILL_ROOT/scripts/review-package" \
  "$REVIEW_BASE_HEAD" "$REVIEWED_CANDIDATE" "$PACKAGE"
test -s "$PACKAGE"
PACKAGE_SHA256="$(shasum -a 256 "$PACKAGE" | awk '{print $1}')"
printf '%s\n' "$REVIEW_BASE_HEAD" >"$REVIEW_DIR/review-base-head"
printf '%s\n' "$INITIAL_MAIN_ANCHOR" >"$REVIEW_DIR/initial-main-anchor"
printf '%s\n' "$REVIEWED_CANDIDATE" >"$REVIEW_DIR/candidate-head"
printf '%s\n' "$PACKAGE_SHA256" >"$REVIEW_DIR/package-sha256"
"$UV" run --quiet --no-project --python 3.13 python - "$REVIEW_DIR" <<'PY'
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

EXPECTED = {
    "whole-branch.diff",
    "review-base-head",
    "initial-main-anchor",
    "candidate-head",
    "package-sha256",
}
path = Path(os.path.abspath(sys.argv[1]))
if os.path.realpath(path) != os.fspath(path):
    raise RuntimeError("review directory path contains a symlink")
before = os.lstat(path)
if (
    stat.S_ISLNK(before.st_mode)
    or not stat.S_ISDIR(before.st_mode)
    or before.st_uid != os.getuid()
    or stat.S_IMODE(before.st_mode) != 0o700
):
    raise RuntimeError("owned mode-0700 review directory required")
directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
files: dict[str, int] = {}
try:
    opened_dir = os.fstat(directory_fd)
    if (opened_dir.st_dev, opened_dir.st_ino) != (before.st_dev, before.st_ino):
        raise RuntimeError("review directory changed while opening")
    if set(os.listdir(directory_fd)) != EXPECTED:
        raise RuntimeError("initial review directory allowlist differs")
    for name in sorted(EXPECTED):
        before_file = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            stat.S_ISLNK(before_file.st_mode)
            or not stat.S_ISREG(before_file.st_mode)
            or before_file.st_uid != os.getuid()
            or before_file.st_nlink != 1
        ):
            raise RuntimeError(f"owned regular review file required: {name}")
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd
        )
        opened_file = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            opened_file.st_nlink != 1
            or current.st_nlink != 1
            or (opened_file.st_dev, opened_file.st_ino) !=
               (before_file.st_dev, before_file.st_ino)
            or (current.st_dev, current.st_ino) !=
               (opened_file.st_dev, opened_file.st_ino)
        ):
            os.close(descriptor)
            raise RuntimeError(f"review file changed while opening: {name}")
        files[name] = descriptor
    for name, descriptor in files.items():
        opened_file = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            opened_file.st_nlink != 1
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) !=
               (opened_file.st_dev, opened_file.st_ino)
        ):
            raise RuntimeError(f"review file changed before chmod: {name}")
        os.fchmod(descriptor, 0o600)
    if set(os.listdir(directory_fd)) != EXPECTED:
        raise RuntimeError("initial review directory changed while setting modes")
    for name, descriptor in files.items():
        opened_file = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened_file.st_mode)
            or opened_file.st_uid != os.getuid()
            or opened_file.st_nlink != 1
            or current.st_nlink != 1
            or stat.S_IMODE(opened_file.st_mode) != 0o600
            or (current.st_dev, current.st_ino) !=
               (opened_file.st_dev, opened_file.st_ino)
        ):
            raise RuntimeError(f"mode-0600 review file differs: {name}")
finally:
    for descriptor in files.values():
        os.close(descriptor)
    os.close(directory_fd)
PY
CODE_REVIEW_TEMPLATE="$SDD_SKILL_ROOT/../requesting-code-review/code-reviewer.md"
test -s "$CODE_REVIEW_TEMPLATE"
printf 'review_base_head=%s\ninitial_main_anchor=%s\nreviewed_candidate=%s\n' \
  "$REVIEW_BASE_HEAD" "$INITIAL_MAIN_ANCHOR" "$REVIEWED_CANDIDATE"
printf 'package=%s\npackage_sha256=%s\ncode_review_template=%s\n' \
  "$PACKAGE" "$PACKAGE_SHA256" "$CODE_REVIEW_TEMPLATE"
printf 'code_review=%s\nadversarial_review=%s\nponytail_review=%s\n' \
  "$REVIEW_DIR/code-review.md" "$REVIEW_DIR/adversarial-review.md" \
  "$REVIEW_DIR/ponytail-review.md"
BASH
```

Dispatch all three with `fork_turns="none"`, the strongest available model, and only
the Plan, Task 5 report, package, binding values, and lens. The requesting-code-review
reviewer uses the printed template. Each report begins with:

```text
REVIEWED_HEAD: <candidate-head>
REVIEW_BASE_HEAD: <review-base-head>
PACKAGE_SHA256: <package-sha256>
CRITICAL: 0
IMPORTANT: 0
MINOR: 0
VERDICT: APPROVED
```

These seven lines are one ordered leading binding block. Any duplicate, contradictory,
or unknown reserved verdict/count/binding marker invalidates the whole report.

Verify all reports and freeze the reviewed object. This is the only source of
`REVIEWED_HEAD` for merge:

```bash
/bin/bash -euo pipefail <<'BASH'
: "${REVIEW_DIR:?exact terminal-rN directory required}"
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
BINDINGS="$("$UV" run --quiet --no-project --python 3.13 python - \
  "$REVIEW_DIR" <<'PY'
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

BEFORE = {
    "whole-branch.diff", "review-base-head", "initial-main-anchor",
    "candidate-head", "package-sha256", "code-review.md",
    "adversarial-review.md", "ponytail-review.md",
}
AFTER = BEFORE | {"reviewed-head"}
REPORTS = ("code-review.md", "adversarial-review.md", "ponytail-review.md")
RESERVED = re.compile(
    r"^(?P<key>(?:[A-Z][A-Z0-9_]*_VERDICT)|VERDICT|TASK_HEAD|REVIEWED_HEAD|"
    r"REVIEW_BASE_HEAD|PACKAGE_SHA256|CRITICAL|IMPORTANT|MINOR):"
)
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def parse_report(payload: bytes, expected: list[tuple[str, str]]) -> None:
    lines = payload.decode("utf-8").splitlines()
    required = [f"{key}: {value}" for key, value in expected]
    if lines[: len(required)] != required:
        raise RuntimeError("ordered leading binding block differs")
    positions = {key: index for index, (key, _) in enumerate(expected)}
    seen: set[str] = set()
    for index, line in enumerate(lines):
        match = RESERVED.match(line)
        if match is None:
            continue
        key = match.group("key")
        if key not in positions:
            raise RuntimeError(f"unknown reserved marker: {key}")
        if key in seen:
            raise RuntimeError(f"duplicate reserved marker: {key}")
        if index != positions[key]:
            raise RuntimeError(f"reserved marker outside leading block: {key}")
        seen.add(key)
    if seen != set(positions):
        raise RuntimeError("missing reserved marker")


path = Path(os.path.abspath(sys.argv[1]))
if os.path.realpath(path) != os.fspath(path):
    raise RuntimeError("review directory path contains a symlink")
before_dir = os.lstat(path)
if (
    stat.S_ISLNK(before_dir.st_mode)
    or not stat.S_ISDIR(before_dir.st_mode)
    or before_dir.st_uid != os.getuid()
    or stat.S_IMODE(before_dir.st_mode) != 0o700
):
    raise RuntimeError("owned mode-0700 review directory required")
directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
files: dict[str, int] = {}
try:
    opened_dir = os.fstat(directory_fd)
    if (opened_dir.st_dev, opened_dir.st_ino) != (
        before_dir.st_dev,
        before_dir.st_ino,
    ):
        raise RuntimeError("review directory changed while opening")
    if set(os.listdir(directory_fd)) != BEFORE:
        raise RuntimeError("pre-freeze review directory allowlist differs")
    for name in sorted(BEFORE):
        before_file = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            stat.S_ISLNK(before_file.st_mode)
            or not stat.S_ISREG(before_file.st_mode)
            or before_file.st_uid != os.getuid()
            or before_file.st_nlink != 1
        ):
            raise RuntimeError(f"owned regular review file required: {name}")
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd
        )
        opened_file = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            opened_file.st_nlink != 1
            or current.st_nlink != 1
            or (opened_file.st_dev, opened_file.st_ino) !=
               (before_file.st_dev, before_file.st_ino)
            or (current.st_dev, current.st_ino) !=
               (opened_file.st_dev, opened_file.st_ino)
        ):
            os.close(descriptor)
            raise RuntimeError(f"review file changed while opening: {name}")
        files[name] = descriptor

    payloads: dict[str, bytes] = {}
    for name, descriptor in files.items():
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        payloads[name] = b"".join(chunks)
    head = payloads["candidate-head"].decode("ascii").removesuffix("\n")
    base = payloads["review-base-head"].decode("ascii").removesuffix("\n")
    main_anchor = payloads["initial-main-anchor"].decode("ascii").removesuffix("\n")
    package_sha = payloads["package-sha256"].decode("ascii").removesuffix("\n")
    if HEX40.fullmatch(head) is None or HEX40.fullmatch(base) is None:
        raise RuntimeError("invalid candidate/review base")
    if HEX40.fullmatch(main_anchor) is None or HEX64.fullmatch(package_sha) is None:
        raise RuntimeError("invalid main anchor/package digest")
    if hashlib.sha256(payloads["whole-branch.diff"]).hexdigest() != package_sha:
        raise RuntimeError("whole-branch package digest differs")
    expected = [
        ("REVIEWED_HEAD", head),
        ("REVIEW_BASE_HEAD", base),
        ("PACKAGE_SHA256", package_sha),
        ("CRITICAL", "0"),
        ("IMPORTANT", "0"),
        ("MINOR", "0"),
        ("VERDICT", "APPROVED"),
    ]
    for report in REPORTS:
        parse_report(payloads[report], expected)
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    current_ref = subprocess.run(
        ["git", "rev-parse", "refs/heads/codex/official-blender-mcp-install"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    symbolic_ref = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    ).stdout
    if (
        symbolic_ref != "refs/heads/codex/official-blender-mcp-install"
        or current_head != head
        or current_ref != head
        or status
    ):
        raise RuntimeError("reviewed candidate HEAD/ref/clean state changed")

    reviewed_fd = os.open(
        "reviewed-head",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    files["reviewed-head"] = reviewed_fd
    reviewed_info = os.fstat(reviewed_fd)
    reviewed_current = os.stat(
        "reviewed-head", dir_fd=directory_fd, follow_symlinks=False
    )
    if (
        not stat.S_ISREG(reviewed_info.st_mode)
        or reviewed_info.st_uid != os.getuid()
        or reviewed_info.st_nlink != 1
        or reviewed_current.st_nlink != 1
        or (reviewed_current.st_dev, reviewed_current.st_ino) !=
           (reviewed_info.st_dev, reviewed_info.st_ino)
    ):
        raise RuntimeError("unsafe reviewed-head before chmod")
    os.fchmod(reviewed_fd, 0o600)
    payload = (head + "\n").encode("ascii")
    view = memoryview(payload)
    while view:
        view = view[os.write(reviewed_fd, view):]
    os.fsync(reviewed_fd)
    reviewed_info = os.fstat(reviewed_fd)
    if (
        not stat.S_ISREG(reviewed_info.st_mode)
        or reviewed_info.st_uid != os.getuid()
        or reviewed_info.st_nlink != 1
    ):
        raise RuntimeError("unsafe reviewed-head")
    if set(os.listdir(directory_fd)) != AFTER:
        raise RuntimeError("final review directory allowlist differs")
    for name, descriptor in files.items():
        opened_file = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            opened_file.st_nlink != 1
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) !=
               (opened_file.st_dev, opened_file.st_ino)
        ):
            raise RuntimeError(f"review file changed before freeze: {name}")
        os.fchmod(descriptor, 0o400)
    os.fchmod(directory_fd, 0o500)
    if stat.S_IMODE(os.fstat(directory_fd).st_mode) != 0o500:
        raise RuntimeError("review directory freeze failed")
    for name, descriptor in files.items():
        opened_file = os.fstat(descriptor)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(opened_file.st_mode)
            or opened_file.st_uid != os.getuid()
            or opened_file.st_nlink != 1
            or current.st_nlink != 1
            or stat.S_IMODE(opened_file.st_mode) != 0o400
            or (current.st_dev, current.st_ino) !=
               (opened_file.st_dev, opened_file.st_ino)
        ):
            raise RuntimeError(f"frozen review file differs: {name}")
    print(head, base, main_anchor, package_sha)
finally:
    for descriptor in files.values():
        os.close(descriptor)
    os.close(directory_fd)
PY
)"
IFS=' ' read -r HEAD_SHA BASE_SHA INITIAL_MAIN_ANCHOR PACKAGE_SHA <<EOF
$BINDINGS
EOF
test "$(git rev-parse HEAD)" = "$HEAD_SHA"
test "$(git rev-parse refs/heads/codex/official-blender-mcp-install)" = "$HEAD_SHA"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test ! -w "$REVIEW_DIR"
printf 'REVIEW_STATE_READY dir=%s reviewed_head=%s review_base_head=%s\n' \
  "$REVIEW_DIR" "$HEAD_SHA" "$BASE_SHA"
BASH
```

Before accepting a terminal round, reproduce the three review-file checks in a
current-UID mode-`0700` disposable `/private/tmp` fixture. Hardlink one required
report to an external mode-`0600` file. Generation and freeze must reject it before
any `fchmod`, the external file's mode and SHA-256 must remain unchanged, and the
Phase M frozen reader must reject the same `st_nlink > 1` inode. Remove the fixture
after recording those results; never run this adversary against the real review
directory.

Any finding dispatches one fix implementer with the complete findings list. It appends
covering commands/output to Task 5's report, commits fix-forward, reruns Task 5's focused
and full gates, passes one new combined Task 5 review, and starts a new terminal round.
Old review directories are never overwritten.

---

### Controller Phase M: Fast-forward the exact reviewed object and verify `main`

This replaces Task 6 and is controller-only. Run one self-contained block from the
feature worktree. For the first merge set `EXPECTED_MAIN_ANCHOR` to the captured
`initial_main_anchor` and leave `PREVIOUS_REVIEW_DIR` unset. For a clean postmerge
fix-forward retry set `EXPECTED_MAIN_ANCHOR` to the old reviewed HEAD and
`PREVIOUS_REVIEW_DIR` to that locked old review directory.

```bash
/bin/bash -euo pipefail <<'BASH'
: "${REVIEW_DIR:?approved terminal-rN directory required}"
: "${EXPECTED_MAIN_ANCHOR:?expected current main object required}"
FEATURE_BRANCH=codex/official-blender-mcp-install
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
case "$EXPECTED_MAIN_ANCHOR" in *[!0-9a-f]*) exit 1 ;; esac
test "${#EXPECTED_MAIN_ANCHOR}" = 40
test -z "${PYTHONPATH-}"
PREVIOUS_REVIEW_DIR="${PREVIOUS_REVIEW_DIR-}"
BINDINGS="$("$UV" run --quiet --no-project --python 3.13 python - \
  "$REVIEW_DIR" "$PREVIOUS_REVIEW_DIR" <<'PY'
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path

EXPECTED = {
    "whole-branch.diff", "review-base-head", "initial-main-anchor",
    "candidate-head", "package-sha256", "code-review.md",
    "adversarial-review.md", "ponytail-review.md", "reviewed-head",
}
REPORTS = ("code-review.md", "adversarial-review.md", "ponytail-review.md")
RESERVED = re.compile(
    r"^(?P<key>(?:[A-Z][A-Z0-9_]*_VERDICT)|VERDICT|TASK_HEAD|REVIEWED_HEAD|"
    r"REVIEW_BASE_HEAD|PACKAGE_SHA256|CRITICAL|IMPORTANT|MINOR):"
)
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def parse_report(payload: bytes, expected: list[tuple[str, str]]) -> None:
    lines = payload.decode("utf-8").splitlines()
    required = [f"{key}: {value}" for key, value in expected]
    if lines[: len(required)] != required:
        raise RuntimeError("ordered leading binding block differs")
    positions = {key: index for index, (key, _) in enumerate(expected)}
    seen: set[str] = set()
    for index, line in enumerate(lines):
        match = RESERVED.match(line)
        if match is None:
            continue
        key = match.group("key")
        if key not in positions:
            raise RuntimeError(f"unknown reserved marker: {key}")
        if key in seen:
            raise RuntimeError(f"duplicate reserved marker: {key}")
        if index != positions[key]:
            raise RuntimeError(f"reserved marker outside leading block: {key}")
        seen.add(key)
    if seen != set(positions):
        raise RuntimeError("missing reserved marker")


def frozen_directory(raw_path: str) -> dict[str, bytes]:
    path = Path(os.path.abspath(raw_path))
    if os.path.realpath(path) != os.fspath(path):
        raise RuntimeError("review directory path contains a symlink")
    before_dir = os.lstat(path)
    if (
        stat.S_ISLNK(before_dir.st_mode)
        or not stat.S_ISDIR(before_dir.st_mode)
        or before_dir.st_uid != os.getuid()
        or stat.S_IMODE(before_dir.st_mode) != 0o500
    ):
        raise RuntimeError("owned frozen mode-0500 review directory required")
    directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    files: dict[str, int] = {}
    try:
        opened_dir = os.fstat(directory_fd)
        if (opened_dir.st_dev, opened_dir.st_ino) != (
            before_dir.st_dev,
            before_dir.st_ino,
        ):
            raise RuntimeError("review directory changed while opening")
        if set(os.listdir(directory_fd)) != EXPECTED:
            raise RuntimeError("frozen review directory allowlist differs")
        for name in sorted(EXPECTED):
            before_file = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if (
                stat.S_ISLNK(before_file.st_mode)
                or not stat.S_ISREG(before_file.st_mode)
                or before_file.st_uid != os.getuid()
                or before_file.st_nlink != 1
                or stat.S_IMODE(before_file.st_mode) != 0o400
            ):
                raise RuntimeError(f"owned frozen review file required: {name}")
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd
            )
            opened_file = os.fstat(descriptor)
            current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(opened_file.st_mode)
                or opened_file.st_uid != os.getuid()
                or before_file.st_nlink != 1
                or opened_file.st_nlink != 1
                or current.st_nlink != 1
                or stat.S_IMODE(opened_file.st_mode) != 0o400
                or (opened_file.st_dev, opened_file.st_ino) !=
                   (before_file.st_dev, before_file.st_ino)
                or (current.st_dev, current.st_ino) !=
                   (opened_file.st_dev, opened_file.st_ino)
            ):
                os.close(descriptor)
                raise RuntimeError(f"frozen review file changed: {name}")
            files[name] = descriptor
        result: dict[str, bytes] = {}
        for name, descriptor in files.items():
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            result[name] = b"".join(chunks)
            current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            opened_file = os.fstat(descriptor)
            if (
                current.st_nlink != 1
                or opened_file.st_nlink != 1
                or (current.st_dev, current.st_ino) !=
                   (opened_file.st_dev, opened_file.st_ino)
            ):
                raise RuntimeError(f"frozen review path changed while reading: {name}")
        if set(os.listdir(directory_fd)) != EXPECTED:
            raise RuntimeError("frozen review directory changed while reading")
        return result
    finally:
        for descriptor in files.values():
            os.close(descriptor)
        os.close(directory_fd)


current = frozen_directory(sys.argv[1])
base = current["review-base-head"].decode("ascii").removesuffix("\n")
initial = current["initial-main-anchor"].decode("ascii").removesuffix("\n")
candidate = current["candidate-head"].decode("ascii").removesuffix("\n")
reviewed = current["reviewed-head"].decode("ascii").removesuffix("\n")
package_sha = current["package-sha256"].decode("ascii").removesuffix("\n")
if not all(HEX40.fullmatch(item) for item in (base, initial, candidate, reviewed)):
    raise RuntimeError("invalid frozen Git binding")
if candidate != reviewed or HEX64.fullmatch(package_sha) is None:
    raise RuntimeError("reviewed/candidate/package binding differs")
if hashlib.sha256(current["whole-branch.diff"]).hexdigest() != package_sha:
    raise RuntimeError("whole-branch package digest differs")
expected = [
    ("REVIEWED_HEAD", reviewed),
    ("REVIEW_BASE_HEAD", base),
    ("PACKAGE_SHA256", package_sha),
    ("CRITICAL", "0"),
    ("IMPORTANT", "0"),
    ("MINOR", "0"),
    ("VERDICT", "APPROVED"),
]
for report in REPORTS:
    parse_report(current[report], expected)
review_hashes = [hashlib.sha256(current[name]).hexdigest() for name in REPORTS]
previous = "-"
if sys.argv[2]:
    old = frozen_directory(sys.argv[2])
    previous = old["reviewed-head"].decode("ascii").removesuffix("\n")
    if HEX40.fullmatch(previous) is None:
        raise RuntimeError("invalid previous reviewed-head")
print(base, initial, reviewed, package_sha, *review_hashes, previous)
PY
)"
IFS=' ' read -r REVIEW_BASE_HEAD INITIAL_MAIN_ANCHOR REVIEWED_HEAD \
  PACKAGE_SHA256 CODE_REVIEW_SHA256 ADVERSARIAL_REVIEW_SHA256 \
  PONYTAIL_REVIEW_SHA256 PREVIOUS_REVIEWED_HEAD <<EOF
$BINDINGS
EOF
if [ "$EXPECTED_MAIN_ANCHOR" = "$INITIAL_MAIN_ANCHOR" ]; then
  test -z "$PREVIOUS_REVIEW_DIR"
  test "$PREVIOUS_REVIEWED_HEAD" = -
else
  test -n "$PREVIOUS_REVIEW_DIR"
  test "$PREVIOUS_REVIEWED_HEAD" = "$EXPECTED_MAIN_ANCHOR"
fi
FEATURE_ROOT="$(git rev-parse --show-toplevel)"
MAIN_ROOT="$(git worktree list --porcelain | awk '
  /^worktree / { root=substr($0, 10) }
  $0 == "branch refs/heads/main" { print root; found++ }
  END { if (found != 1) exit 1 }
')"
test "$(git branch --show-current)" = "$FEATURE_BRANCH"
test "$(git rev-parse HEAD)" = "$REVIEWED_HEAD"
test "$(git rev-parse refs/heads/$FEATURE_BRANCH)" = "$REVIEWED_HEAD"
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git -C "$MAIN_ROOT" branch --show-current)" = main
test -z "$(git -C "$MAIN_ROOT" status --porcelain=v1 --untracked-files=all)"
test "$(git -C "$MAIN_ROOT" rev-parse HEAD)" = "$EXPECTED_MAIN_ANCHOR"
git merge-base --is-ancestor "$REVIEW_BASE_HEAD" "$EXPECTED_MAIN_ANCHOR"
git merge-base --is-ancestor "$EXPECTED_MAIN_ANCHOR" "$REVIEWED_HEAD"
test "$EXPECTED_MAIN_ANCHOR" != "$REVIEWED_HEAD"

# Accept an absent generated environment or an owned ordinary canonical one.
MAIN_VENV="$MAIN_ROOT/.venv"
git -C "$MAIN_ROOT" check-ignore -q -- .venv/
"$UV" run --quiet --no-project --python 3.13 python - \
  "$MAIN_ROOT" "$MAIN_VENV" <<'PY'
from pathlib import Path
import os
import stat
import sys

root = Path(sys.argv[1])
venv = Path(sys.argv[2])
if Path(os.path.realpath(root)) != root or venv.parent != root or venv.name != ".venv":
    raise SystemExit("STOP: main .venv must be the canonical repository-root child")
if os.path.lexists(venv):
    info = venv.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit("STOP: existing main .venv must be an ordinary directory")
    if info.st_uid != os.getuid() or info.st_mode & stat.S_IWOTH:
        raise SystemExit("STOP: existing main .venv has unsafe ownership/mode")
PY

verify_main_venv() {
  "$MAIN_VENV/bin/python" -P - "$MAIN_ROOT" "$MAIN_VENV" <<'PY'
from pathlib import Path
import importlib.metadata
import os
import site
import stat
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
venv = Path(sys.argv[2])
if not sys.flags.safe_path:
    raise SystemExit("STOP: main snapshot verifier requires safe-path mode")
if sys.version_info[:2] != (3, 13) or Path(sys.prefix) != venv:
    raise SystemExit("STOP: main environment is not CPython 3.13")
info = venv.lstat()
if venv.parent != root or stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
    raise SystemExit("STOP: main .venv identity/type mismatch")
if info.st_uid != os.getuid():
    raise SystemExit("STOP: main .venv has foreign ownership")
site_roots = [
    path for path in map(Path, site.getsitepackages()) if path.is_relative_to(venv)
]
if len(site_roots) != 1:
    raise SystemExit("STOP: expected one main venv site-packages directory")
site_root = site_roots[0]
for path in site_root.glob("*_editable_impl_blender_codex.pth"):
    raise SystemExit(f"STOP: main editable project hook rejected: {path}")
server_init = site_root / "server" / "__init__.py"
entrypoint = venv / "bin" / "blender-codex-server"
for path in (server_init, entrypoint):
    entry = path.lstat()
    if stat.S_ISLNK(entry.st_mode) or not stat.S_ISREG(entry.st_mode):
        raise SystemExit(f"STOP: regular main snapshot file required: {path}")
    if entry.st_uid != os.getuid():
        raise SystemExit(f"STOP: foreign-owned main snapshot file rejected: {path}")
if not entrypoint.stat().st_mode & stat.S_IXUSR:
    raise SystemExit("STOP: main blender-codex-server is not executable")
import server
if Path(server.__file__).resolve() != server_init:
    raise SystemExit("STOP: main server did not import from the site-packages snapshot")
entries = [
    item
    for item in importlib.metadata.distribution("blender-codex").entry_points
    if item.group == "console_scripts" and item.name == "blender-codex-server"
]
if len(entries) != 1 or entries[0].value != "server.mcp.adapter:main":
    raise SystemExit("STOP: main blender-codex-server entrypoint snapshot differs")
with tempfile.TemporaryDirectory(
    prefix="blender-codex-main-verify-", dir="/private/tmp"
) as temporary:
    completed = subprocess.run(
        [entrypoint],
        cwd=temporary,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
if completed.returncode != 0:
    raise SystemExit("STOP: main blender-codex-server tmp-cwd execution failed")
print(
    "MAIN_VENV_GREEN python=3.13 install=noneditable "
    "server_snapshot=site-packages entrypoint=pass"
)
PY
}

# Merge the immutable reviewed object, never the moving branch name.
git -C "$MAIN_ROOT" merge --ff-only "$REVIEWED_HEAD"
test "$(git -C "$MAIN_ROOT" rev-parse HEAD)" = "$REVIEWED_HEAD"
set +e
(cd "$MAIN_ROOT" && ./scripts/checks.sh)
CHECKS_EXIT=$?
verify_main_venv
MAIN_VENV_EXIT=$?
git -C "$MAIN_ROOT" diff --check
DIFF_EXIT=$?
set -e
POST_MAIN_HEAD="$(git -C "$MAIN_ROOT" rev-parse HEAD)"
FEATURE_HEAD="$(git rev-parse HEAD)"
FEATURE_REF_HEAD="$(git rev-parse refs/heads/$FEATURE_BRANCH)"
MAIN_STATUS="$(git -C "$MAIN_ROOT" status --porcelain=v1 --untracked-files=all)"
FEATURE_STATUS="$(git status --porcelain=v1 --untracked-files=all)"
test "$POST_MAIN_HEAD" = "$REVIEWED_HEAD"
test "$FEATURE_HEAD" = "$REVIEWED_HEAD"
test "$FEATURE_REF_HEAD" = "$REVIEWED_HEAD"
REVIEW_ROUND="${REVIEW_DIR##*terminal-r}"
case "$REVIEW_ROUND" in 0|*[!0-9]*|'') exit 1 ;; esac
POSTMERGE_REPORT=.superpowers/sdd/modeling-remediation/postmerge-r$REVIEW_ROUND.txt
test ! -e "$POSTMERGE_REPORT"
test ! -L "$POSTMERGE_REPORT"
install -m 600 /dev/null "$POSTMERGE_REPORT"
RESULT=pass
if [ "$CHECKS_EXIT" != 0 ] || [ "$MAIN_VENV_EXIT" != 0 ] || \
   [ "$DIFF_EXIT" != 0 ]; then RESULT=clean_failure; fi
if [ -n "$MAIN_STATUS" ] || [ -n "$FEATURE_STATUS" ]; then RESULT=dirty_failure; fi
{
  printf 'result=%s\n' "$RESULT"
  printf 'review_dir=%s\nfeature_root=%s\nmain_root=%s\n' \
    "$REVIEW_DIR" "$FEATURE_ROOT" "$MAIN_ROOT"
  printf 'review_base_head=%s\ninitial_main_anchor=%s\n' \
    "$REVIEW_BASE_HEAD" "$INITIAL_MAIN_ANCHOR"
  printf 'expected_main_anchor=%s\nreviewed_head=%s\n' \
    "$EXPECTED_MAIN_ANCHOR" "$REVIEWED_HEAD"
  printf 'postmerge_main_head=%s\nfeature_worktree_head=%s\nfeature_ref_head=%s\n' \
    "$POST_MAIN_HEAD" "$FEATURE_HEAD" "$FEATURE_REF_HEAD"
  printf 'package_sha256=%s\ncode_review_sha256=%s\n' \
    "$PACKAGE_SHA256" "$CODE_REVIEW_SHA256"
  printf 'adversarial_review_sha256=%s\nponytail_review_sha256=%s\n' \
    "$ADVERSARIAL_REVIEW_SHA256" "$PONYTAIL_REVIEW_SHA256"
  printf 'checks_exit=%s\nmain_venv_exit=%s\ndiff_check_exit=%s\n' \
    "$CHECKS_EXIT" "$MAIN_VENV_EXIT" "$DIFF_EXIT"
  printf 'main_clean=%s\n' "$([ -z "$MAIN_STATUS" ] && echo true || echo false)"
  printf 'feature_clean=%s\n' "$([ -z "$FEATURE_STATUS" ] && echo true || echo false)"
} >"$POSTMERGE_REPORT"
if [ "$RESULT" = dirty_failure ]; then
  echo "STOP_DIRTY_WORKTREE report=$POSTMERGE_REPORT" >&2
  exit 86
fi
if [ "$RESULT" = clean_failure ]; then
  echo "POSTMERGE_CLEAN_FAILURE report=$POSTMERGE_REPORT" >&2
  exit 85
fi
printf 'POSTMERGE_GREEN reviewed_head=%s report=%s\n' \
  "$REVIEWED_HEAD" "$POSTMERGE_REPORT"
BASH
```

Expected success: `postmerge_main_head == feature_worktree_head ==
feature_ref_head == REVIEWED_HEAD`, both worktrees are clean, `checks_exit`,
`main_venv_exit`, and `diff_check_exit` are zero, and the report says `result=pass`.

On exit 85, main is clean at the old reviewed object. Preserve the original
`review_base_head`, old locked review directory, and report; do not reset/rebase/revert
main. Dispatch one fix-forward implementer, rerun owning probes and Task 5's full gate
with Appendix D `EXPECTED_MAIN_ANCHOR=<old REVIEWED_HEAD>`, pass one combined Task 5
review, generate the next whole-branch package from the original `review_base_head`,
pass all three terminal reviews, then rerun this block with the old review directory as
`PREVIOUS_REVIEW_DIR`. If main is dirty (exit 86), fail closed and ask the user; never
stash, clean, checkout, reset, revert, or continue automatically.

---

## Appendix A: Exact runbook bytes

Task 1 writes the following bytes exactly, then runs the contract probe after the
fence. The fence itself is not part of the runbook.

````markdown
# Blender Lab 官方 MCP：安全建模运行手册

状态：operational、non-normative

本仓库技术版本：`0.1.0`

本手册只规定安装完成后的建模、验证和证据流程。安装、配置、更新与回滚请使用
[`install-official-blender-mcp.md`](install-official-blender-mcp.md)，不要在此重复安装步骤。

## 1. 边界与前置条件

只使用名为 `blender` 的 Blender Lab 官方 MCP，不调用本仓库的自定义 MCP Server。

运行边界为：

- Blender `>=5.2`；`5.2.0` 是实测基线，更高版本必须重新通过本手册的运行时探测；
- 官方源码固定在
  `4309a39646e644261624bfcd2bca669b343b7621`，运行中不得更新或修改该 checkout；
- Server 继续使用 Python 3.13 和 `mcp[cli]>=1.2.0,<2`；
- `MCP_SOURCE_DIR`、`UV_BIN` 和有效 Server 参数从已验证的安装配置解析，不硬编码用户名；
- 只操作新启动的 disposable factory scene，不打开、保存或覆盖用户 `.blend`；
- 运行文件只写入当前 UID 所有、非 symlink、mode `0700` 的临时 run root。

开始前验证 checkout 的完整 commit、clean 状态和有效配置。live catalog、固定源码
catalog 与 configured catalog 必须动态、逐名相等。不得把工具数量硬编码为 `26`；
经批准更新后出现的新增工具，只有在三份 catalog 与结果表全部一致时才可接受。

## 2. Shell 与 SDD 纪律

所有标为 Bash 的 fence 都使用 `/bin/bash -euo pipefail` 执行，不把它们直接交给
默认 zsh。zsh 的 `path` 是与 `PATH` 联动的特殊参数；循环变量使用
`fixture_path` 等普通名称。

SDD 的 brief 必须使用 helper 的第三个 `OUTFILE` 参数：

```text
scripts/task-brief PLAN_FILE TASK_NUMBER OUTFILE
```

不得把 helper stdout 重定向到它管理的 brief 文件。每次执行生成唯一
`RUN_STEM`，brief 与 report 使用同一个 stem：

```bash
RUN_STEM="modeling-run-YYYYMMDD-HHMMSS-task-N"
BRIEF=".superpowers/sdd/${RUN_STEM}-brief.md"
REPORT=".superpowers/sdd/${RUN_STEM}-report.md"

test ! -e "$BRIEF"
test ! -e "$REPORT"
/bin/bash "$TASK_BRIEF_HELPER" "$PLAN_FILE" "$TASK_NUMBER" "$BRIEF"
test -s "$BRIEF"
```

dispatch 时显式传递该 `BRIEF` 和 `REPORT`。agent 完成后必须执行
`test -s "$REPORT"`；不得把旧的通用 `task-N-report.md` 当成本次报告。

仓库自身 gate 与后文官方 MCP source/config harness 是两条不同的环境边界。
`scripts/checks.sh` 必须在 `PYTHONDONTWRITEBYTECODE` 后导出 `UV_NO_EDITABLE=1`，并在
vendor generate 与 `--check` 都成功后执行：

```bash
"$UV_BIN" sync --frozen --python 3.13 --reinstall-package blender-codex
```

这样 tmp-cwd console entrypoint 与测试读取的是当次 vendor 生成后的
site-packages package snapshot，不依赖 editable `.pth`。不得用 `chflags`、
`PYTHONPATH` 或减少/跳过 369 个测试来规避 worktree 的 `UF_HIDDEN` sweep。
该实施环境事件记为 `POSTPLAN-ENV-01`，仅用 prose 记录，不加入第 11 节的 24 个
`MODEL-*` issue，也不写入 audit CLI 的 literal issue-ID 字段。

## 3. Preflight 与精确写入范围

启动 recorder 后、任何 Blender 写入前，验证：

1. `127.0.0.1:9876` 恰有一个 Blender listener，并记录 PID；
2. `bpy.data.filepath == ""`，当前是 unsaved factory scene；
3. mode、factory object exact set、active/selected 状态和 `VIEW_3D` 均符合计划；
4. 本次所有目标 collection、object、mesh、curve、material、camera、light、
   image、library 与 sentinel 均不存在；
5. fixture 和 run root 通过 `lstat`、UID、mode、普通文件/目录及 hash 检查。

计划必须逐名列出允许创建或修改的 datablock，不能只用 `Lamp_*` 一类模式表示范围。
允许的 Scene、World、camera、render 和 color-management 设置也必须逐项列出。
factory 数据和 allowlist 之外的既有对象不得修改。

每个 mutating phase 在第一次写入前重新断言：

- 所有前置 phase 的 exact object/material/data/parent set；
- 本 phase 新目标全部不存在；
- filepath、sentinel、mode、collection 和 run-root 身份仍匹配；
- 不存在意外 `.001` 名称。

最终结构验收使用 exact set、data 名称、parent chain、collection membership、
active/selected、library、missing-file 路径和明确排除 ground 后的数值 bounds。
summary 工具只能作为交叉验证，不能替代 exact assertion。

## 4. Locale 与场景身份

不要按本地化 display name 查找 Blender 内置节点。必须按稳定 RNA type 查找，并
断言唯一：

- Principled shader：`node.type == "BSDF_PRINCIPLED"`；
- World background：`node.type == "BACKGROUND"`。

由本次运行创建的名称必须使用计划中的固定 ASCII 名称。

`bpy.data.is_dirty` 只记录为 observation，不参与场景身份或 phase precondition。
场景身份由空 filepath、run sentinel、exact object/material/data set、parent chain、
collection membership 和 active/selected 状态共同证明。

## 5. Transactional phase 与恢复

每个 mutating phase 视为一次事务。发生异常时必须按以下顺序处理：

1. 立即写入失败 end event，保留原始 symptom；
2. 在任何恢复动作前写入当时的 verbatim first hypothesis，不得事后改写；
3. 记录是否已经产生 partial state；
4. 不在原 session 中删除、补写或继续；
5. 确认它仍是 unsaved disposable scene 后退出该 Blender GUI，不保存；
6. 等待旧 listener 消失，重新启动 factory scene，并验证恰有一个新 listener；
7. 完整重跑 preflight，再从 Phase 1 全量 replay 一次；
8. recovery 使用新的 event ID，设置正整数 `attempt` 并引用 `recovery_of`。

同一失败再次出现时停止盲目重试，保留两次证据并进入根因分析。不得用 `.001`
对象、局部删除或强制修改 dirty flag 掩盖 partial state。

## 6. Interpreter、fixture 与文档查询 contract

所有 source/config harness 使用解析后的绝对 `UV_BIN`、Python 3.13 和 Server
实际依赖边界：

```bash
"$UV_BIN" run --quiet --no-project --python 3.13 \
  --with 'mcp[cli]>=1.2.0,<2' \
  --with-editable "$MCP_SOURCE_DIR/mcp" \
  python -
```

命令在 `/bin/bash -euo pipefail` 下运行。执行后重新验证固定 checkout clean，
且没有生成 `uv.lock`。

断言返回字段前先读固定源码的响应 contract；官方 API 搜索结果字段是 `hits`，
不得猜测为 `results`。Cylinder operator 的已验证查询为：

```text
bpy.ops.mesh primitive_cylinder_add
```

不要发送已知返回零结果的自然语言拆分形式。

Blender 保存时可能丢弃 zero-user image。需要在保存后仍存在的受控 missing-image
fixture，保存前设置 `use_fake_user=True`，然后重新打开文件验证 image 和 missing
路径。已有 fixture 保持不变；需要恢复时创建新的 derived fixture，并只对失败工具
重试一次。

## 7. Blender 5.2 与上游限制

在 Phase 3 的其他写入前，从当前 Blender 运行时枚举 render engine，确认目标值
存在，赋值后立即读回。Blender 5.2 的实测 EEVEE 值是 `BLENDER_EEVEE`。

固定上游 thumbnail 实现仍包含旧的 `BLENDER_EEVEE_NEXT` 分支；该字符串不是
Blender 5.2 的 render-engine 值。此分支在 5.2 上不会自动降低 EEVEE samples。
调用 thumbnail 前后记录实际 engine、render samples、viewport samples 和耗时，
但不修改固定上游源码。

area 和 window screenshot 从第一次调用起都使用
`size_limit_in_bytes=48_000`。更大的 base64 response 可能被当前非阻塞 bridge
截断；48 KB 是运行规避措施，不代表上游传输问题已被仓库修复。返回值仍须验证为
非空 PNG 和合理尺寸。

## 8. Render scratch

render 前从 Blender 读取 `bpy.app.tempdir` 并先做 `realpath`。安全检查区分两类路径：

- canonical temp root 以上的系统祖先只要求正常解析为既有普通目录；不得要求它们
  属于当前 UID，也不得创建、chmod 或替换它们；
- canonical temp root 及本次使用的所有下级路径必须由当前 UID 所有，逐层
  `lstat`，不得含 symlink。

最终 scratch 固定为 canonical temp root 下的 `blender_mcp`。若它不存在，先记录
absence，再只创建这一层 mode `0700` 目录；若已存在，则必须是当前 UID 所有的
普通非 symlink 私有目录，否则停止。

每次 render 使用包含 `RUN_STEM` 和唯一随机后缀的 basename。调用前分别对官方
source target 和 run-root copy target 执行 `lstat`，两者都必须不存在；不能用
`exists()` 代替，因为 broken symlink 也必须拒绝。

调用后验证：

1. 返回路径的 `realpath` 恰等于预期 source target；
2. basename 和 canonical parent 恰好匹配；
3. source 经 `lstat` 是当前 UID 所有、非 symlink、非空的普通文件；
4. 文件头是 PNG magic；
5. 记录 source 的 `sha256`；
6. copy parent 已通过逐层 ownership/symlink 检查；
7. 使用 exclusive-create 方式复制，不覆盖既有路径；
8. copy 经同样的 `lstat`、PNG 和 ownership 检查；
9. source 与 copy 的 `sha256` 完全相等；
10. `bpy.data.filepath`、原 render filepath 和 unsaved 状态保持不变。

render 失败但留下 partial file 时，不删除或复用它；记录路径、size、magic 和 hash，
recovery 使用新的唯一 basename。

## 9. 单一时钟与证据

在读取 payload、catalog 或 Blender 状态前，启动
`scripts/official_blender_mcp_audit.py record` 的一个长生命周期进程。一个 run
只能有一个 recorder 和一个由它生成的 `clock_id`；不得为每个 event 启动新的
Python 进程。

使用私有 FIFO 保持 recorder stdin 打开：

```bash
umask 077
JOURNAL="$RUN_ROOT/events.ndjson"
EVENT_FIFO="$RUN_ROOT/events.fifo"

test ! -e "$JOURNAL"
test ! -e "$EVENT_FIFO"
mkfifo -m 600 "$EVENT_FIFO"

"$UV_BIN" run --quiet --no-project --python 3.13 \
  python scripts/official_blender_mcp_audit.py \
  record --output "$JOURNAL" <"$EVENT_FIFO" &
RECORDER_PID=$!
exec 9>"$EVENT_FIFO"
```

通过 FD 9 发送 JSON event。Task、stage 和每次 tool call 分别使用
`scope=task|stage|call`、稳定 `event_id` 及恰好一对 `start`/`end`。唯一 Task start
必须是首个 event，唯一 Task end 必须是末个 event，所有 stage/call 都位于其间。
failure end event 必须在 recovery start event 之前包含非空 `symptom`、调用者原样
提供的 `first_hypothesis` 和 literal issue IDs；deviation 与 linked recovery end 也必须
有非空 literal issue IDs。记录 `attempt`、`recovery_of`、MCP wall 和 Blender internal
time；不推测缺失值。

结束时先发送 Task end，关闭 FD，等待 recorder 正常退出，再运行 `validate`：

```bash
exec 9>&-
wait "$RECORDER_PID"

"$UV_BIN" run --quiet --no-project --python 3.13 \
  python scripts/official_blender_mcp_audit.py validate \
  --journal "$JOURNAL" \
  --audit "$AUDIT_FILE" \
  --live-catalog "$LIVE_CATALOG" \
  --source-catalog "$SOURCE_CATALOG" \
  --config-catalog "$CONFIG_CATALOG"
```

只有 validate 成功后才能报告 coverage、duration 或 recovery 结论。stage
monotonic duration 减去 MCP wall 的剩余部分只能称为
`unattributed orchestration`，不能称为 LLM time。

潜在异常阈值为：summary/docs/navigation `5,000 ms`、screenshot `10,000 ms`、
thumbnail `30,000 ms`、viewport `60,000 ms`。首次成功调用超过对应阈值时，保留
首次证据并执行一次同条件复测；render 复测必须换新 basename。未超过阈值不得仅为
“看起来慢”而重试。

## 10. Soft process diagnostic 与正常清理

Task 前后各记录一次只读 `ps` snapshot，统计与当前 Codex/App Server 相关的
uv launcher 和 `blender-mcp` child 数量及 RSS；同时记录
`127.0.0.1:9876` 的唯一 listener。snapshot 只能用于比较 count/RSS delta，
不能从进程数量反推每次 tool call 都启动了新 Server。

运行中不得逐个终止 idle stdio Server；它们没有额外监听 `9876`，且单独终止可能
破坏仍在使用的 session。等所有 agents、报告、journal 和 Git 工作都完成后，如需
清理 retained pairs，正常退出并重新启动 Codex Desktop，然后重新记录 snapshot。

`MODEL-RUN-10` 只得到 soft diagnostic 和正常 host-lifecycle 清理建议；现有证据
不足以证明 root/subagent-session 因果映射。

## 11. 问题处置清单

下表恰好覆盖 approved audit 的 24 个唯一 issue ID。Disposition 说明未来运行中的
责任边界，不改写历史证据。

| Issue ID | Disposition | 规则 |
|---|---|---|
| `MODEL-SHELL-01` | `prevented_by_runbook` | 显式 Bash，避开 zsh `path` 特殊参数 |
| `MODEL-SDD-01` | `prevented_by_runbook` | helper 第三个 `OUTFILE`，禁止 stdout 覆盖 brief |
| `MODEL-SDD-02` | `prevented_by_runbook` | run-scoped brief/report stem 与前后存在性检查 |
| `MODEL-RUN-01` | `prevented_by_runbook` | 使用唯一稳定 RNA type，不依赖本地化 display name |
| `MODEL-RUN-02` | `prevented_by_runbook` | dirty 仅观察，exact structure 证明身份 |
| `MODEL-RUN-03` | `prevented_by_audit` | 解析 exact table 和 literal issue IDs |
| `MODEL-RUN-04` | `prevented_by_audit` | 单一 recorder、同一 clock ID 和成对事件 |
| `MODEL-RUN-05` | `prevented_by_runbook` | 绝对 uv 与 Python 3.13 |
| `MODEL-RUN-06` | `prevented_by_runbook` | missing image 使用 fake user 和 derived fixture |
| `MODEL-RUN-07` | `prevented_by_runbook` | 有效 editable dependencies 与源码确认响应字段 |
| `MODEL-RUN-08` | `mitigated_only` | 48 KB screenshot cap；上游传输根因未改动 |
| `MODEL-RUN-09` | `mitigated_only` | 安全创建最终 scratch parent；上游未自动创建 |
| `MODEL-RUN-10` | `diagnostic_only` | 只记录 process delta 并正常退出 host |
| `MODEL-RUN-11` | `future_prevention_only` | 未来 failure 必须先持久化 first hypothesis；历史缺口保留 |
| `MODEL-PLAN-01` | `prevented_by_runbook` | 运行时发现并读回 `BLENDER_EEVEE` |
| `MODEL-PLAN-02` | `prevented_by_runbook` | transactional precondition、discard 和 full replay |
| `MODEL-PLAN-03` | `prevented_by_runbook` | 精确声明 Scene/World/render/datablock 写入范围 |
| `MODEL-PLAN-04` | `prevented_by_runbook` | exact sets、parents、data、bounds 与 summary 交叉验证 |
| `MODEL-PLAN-05` | `prevented_by_runbook_and_audit` | one-clock journal 与机器校验 |
| `MODEL-PLAN-06` | `prevented_by_runbook` | 使用 source-proven operator query |
| `MODEL-PLAN-07` | `prevented_by_audit` | 动态 catalog equality 和结果表 `Counter` |
| `MODEL-PLAN-08` | `prevented_by_runbook` | canonical containment、lstat、unique absent target 和 hash |
| `MODEL-PLAN-09` | `warning_only` | 记录 EEVEE/sample 兼容性，不修改固定上游 |
| `MODEL-PLAN-10` | `prevented_by_runbook_and_audit` | immediate events、阈值复测、partial artifact 保留和验证 |

`MODEL-RUN-08`、`MODEL-RUN-09` 只被规避；`MODEL-RUN-10` 只被观察；
`MODEL-PLAN-09` 只记录兼容性警告。它们都不是仓库内修复。
`MODEL-RUN-11` 只能预防未来证据缺口，不能补造已丢失的历史 hypothesis。

## 12. 完成检查

- [ ] 官方 source pin、SDK boundary、Blender version 和动态 catalog equality 通过；
- [ ] recorder 在任何工作读取前启动，Task/stage/call events 全部成对；
- [ ] 唯一 listener、factory scene、target absence 与 exact write allowlist 通过；
- [ ] locale-safe RNA、dirty observation 和 transactional recovery 规则已执行；
- [ ] fixture、docs query、48 KB screenshot 与 Blender engine contract 通过；
- [ ] render source/copy 的 absence、containment、lstat、PNG 和 hash 通过；
- [ ] exact structural assertion 与所有官方工具结果通过；
- [ ] `validate` 通过后才形成结论；
- [ ] Task 前后 process snapshot 已记录，未进行 mid-run individual termination；
- [ ] agents、reports、journal 和 Git 状态全部收口后再正常退出或重启 Codex Desktop。
````

Task 1 then runs this exact contract probe:

```bash
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import stat

path = Path("docs/use-official-blender-mcp.md")
info = path.lstat()
assert stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode)
text = path.read_text(encoding="utf-8")
assert text.endswith("\n")

headings = [
    "## 1. 边界与前置条件",
    "## 2. Shell 与 SDD 纪律",
    "## 3. Preflight 与精确写入范围",
    "## 4. Locale 与场景身份",
    "## 5. Transactional phase 与恢复",
    "## 6. Interpreter、fixture 与文档查询 contract",
    "## 7. Blender 5.2 与上游限制",
    "## 8. Render scratch",
    "## 9. 单一时钟与证据",
    "## 10. Soft process diagnostic 与正常清理",
    "## 11. 问题处置清单",
    "## 12. 完成检查",
]
for heading in headings:
    assert text.count(heading + "\n") == 1, heading

required = [
    "Blender `>=5.2`",
    "4309a39646e644261624bfcd2bca669b343b7621",
    "mcp[cli]>=1.2.0,<2",
    "不得把工具数量硬编码为 `26`",
    "/bin/bash -euo pipefail",
    "scripts/task-brief PLAN_FILE TASK_NUMBER OUTFILE",
    "RUN_STEM",
    "UV_NO_EDITABLE=1",
    '"$UV_BIN" sync --frozen --python 3.13 --reinstall-package blender-codex',
    "site-packages package snapshot",
    "369 个测试",
    "POSTPLAN-ENV-01",
    "`chflags`",
    "`PYTHONPATH`",
    'node.type == "BSDF_PRINCIPLED"',
    'node.type == "BACKGROUND"',
    "bpy.data.is_dirty",
    "use_fake_user=True",
    "bpy.ops.mesh primitive_cylinder_add",
    "`hits`",
    "`BLENDER_EEVEE`",
    "size_limit_in_bytes=48_000",
    "bpy.app.tempdir",
    "`lstat`",
    "`sha256`",
    "`clock_id`",
    "`unattributed orchestration`",
    "Codex Desktop",
]
for literal in required:
    assert literal in text, literal

expected = {
    "MODEL-SHELL-01": "prevented_by_runbook",
    "MODEL-SDD-01": "prevented_by_runbook",
    "MODEL-SDD-02": "prevented_by_runbook",
    "MODEL-RUN-01": "prevented_by_runbook",
    "MODEL-RUN-02": "prevented_by_runbook",
    "MODEL-RUN-03": "prevented_by_audit",
    "MODEL-RUN-04": "prevented_by_audit",
    "MODEL-RUN-05": "prevented_by_runbook",
    "MODEL-RUN-06": "prevented_by_runbook",
    "MODEL-RUN-07": "prevented_by_runbook",
    "MODEL-RUN-08": "mitigated_only",
    "MODEL-RUN-09": "mitigated_only",
    "MODEL-RUN-10": "diagnostic_only",
    "MODEL-RUN-11": "future_prevention_only",
    "MODEL-PLAN-01": "prevented_by_runbook",
    "MODEL-PLAN-02": "prevented_by_runbook",
    "MODEL-PLAN-03": "prevented_by_runbook",
    "MODEL-PLAN-04": "prevented_by_runbook",
    "MODEL-PLAN-05": "prevented_by_runbook_and_audit",
    "MODEL-PLAN-06": "prevented_by_runbook",
    "MODEL-PLAN-07": "prevented_by_audit",
    "MODEL-PLAN-08": "prevented_by_runbook",
    "MODEL-PLAN-09": "warning_only",
    "MODEL-PLAN-10": "prevented_by_runbook_and_audit",
}
issue_section = text.split("## 11. 问题处置清单\n", 1)[1]
issue_section = issue_section.split("\n## 12. 完成检查\n", 1)[0]
pattern = re.compile(
    r"^\|\s*`(?P<issue>MODEL-(?:SHELL|SDD|RUN|PLAN)-\d{2})`\s*"
    r"\|\s*`(?P<disposition>[a-z_]+)`\s*\|"
)
rows = []
for line in issue_section.splitlines():
    match = pattern.match(line)
    if match:
        rows.append((match.group("issue"), match.group("disposition")))
assert len(rows) == 24
assert Counter(issue for issue, _ in rows) == Counter(expected.keys())
assert dict(rows) == expected
all_ids = set(re.findall(r"MODEL-(?:SHELL|SDD|RUN|PLAN)-\d{2}", text))
assert all_ids == set(expected)
assert text.count("BLENDER_EEVEE_NEXT") == 1
for forbidden in [
    "git clone", "codex mcp add", "3 MB", "3MB", "pkill", "killall",
    "pytest -k", "--ignore=tests",
]:
    assert forbidden not in text, forbidden
for forbidden_pattern in [
    r"(?i)\bfix(?:es|ed|ing)?\s+`?MODEL-RUN-10",
    r"(?i)\bprevent(?:s|ed|ing)?\s+`?MODEL-RUN-10",
    r"(?:修复|解决|预防)\s*`?MODEL-RUN-10",
    r"(?i)\bkill\s+-",
    r"(?m)^\s*chflags\b",
    r"(?m)^\s*(?:export\s+)?PYTHONPATH\s*=",
]:
    assert re.search(forbidden_pattern, text) is None, forbidden_pattern
print({"headings": len(headings), "issue_rows": len(rows), "contract": "ok"})
PY
```

Expected: `{'headings': 12, 'issue_rows': 24, 'contract': 'ok'}`.

## Appendix B1 — recorder-only complete bytes

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NoReturn, TextIO, cast

ISSUE_RE = re.compile(r"MODEL-(?:SHELL|SDD|RUN|PLAN)-\d{2}")


class AuditError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AuditError("USAGE", message)


def json_value(text: str, label: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise AuditError("JSON", f"{label}: duplicate key {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> NoReturn:
        raise AuditError("JSON", f"{label}: invalid constant {value}")

    try:
        value: object = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (ValueError, RecursionError) as exc:
        raise AuditError("JSON", f"{label}: invalid JSON") from exc
    return value


def json_object(text: str, label: str) -> dict[str, object]:
    value = json_value(text, label)
    if not isinstance(value, dict):
        raise AuditError("SCHEMA", f"{label}: expected object")
    return cast(dict[str, object], value)


def text_field(event: dict[str, object], key: str) -> str:
    value = event[key]
    if not isinstance(value, str) or not value or value != value.strip():
        raise AuditError("SCHEMA", f"{key}: expected nonblank trimmed string")
    return value


def int_field(event: dict[str, object], key: str) -> int:
    value = event[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuditError("SCHEMA", f"{key}: expected integer")
    return value


def issues(event: dict[str, object]) -> tuple[str, ...]:
    value = event["issue_ids"]
    if not isinstance(value, list):
        raise AuditError("SCHEMA", "issue_ids: expected array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or ISSUE_RE.fullmatch(item) is None:
            raise AuditError("SCHEMA", "issue_ids: invalid issue ID")
        result.append(item)
    if len(result) != len(set(result)):
        raise AuditError("SCHEMA", "issue_ids: duplicate issue ID")
    return tuple(result)


def internal_ms(event: dict[str, object]) -> None:
    if "internal_ms" not in event:
        return
    value = event["internal_ms"]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AuditError("SCHEMA", "internal_ms: expected JSON number")
    if value < 0 or (isinstance(value, float) and (value != value or value == float("inf"))):
        raise AuditError("SCHEMA", "internal_ms: expected finite nonnegative number")


def validate_event(event: dict[str, object]) -> None:
    identity = {"event_id", "kind", "scope", "stage", "attempt", "recovery_of"}
    kind = event.get("kind")
    if kind == "start":
        required = identity
        allowed = required
    elif kind == "end":
        required = identity | {"outcome", "issue_ids"}
        allowed = required | {"symptom", "first_hypothesis", "internal_ms"}
    else:
        raise AuditError("SCHEMA", "kind: expected start or end")

    missing = required - set(event)
    unknown = set(event) - allowed
    if missing:
        raise AuditError("SCHEMA", f"missing: {','.join(sorted(missing))}")
    if unknown:
        raise AuditError("SCHEMA", f"unknown: {','.join(sorted(unknown))}")

    event_id = text_field(event, "event_id")
    scope = text_field(event, "scope")
    if scope not in {"task", "stage", "call"}:
        raise AuditError("SCHEMA", "scope: expected task, stage, or call")
    text_field(event, "stage")
    attempt = int_field(event, "attempt")
    if attempt < 0:
        raise AuditError("SCHEMA", "attempt: expected nonnegative integer")

    recovery = event["recovery_of"]
    if recovery is not None:
        if not isinstance(recovery, str) or not recovery or recovery != recovery.strip():
            raise AuditError("SCHEMA", "recovery_of: expected null or nonblank string")
        if recovery == event_id:
            raise AuditError("SCHEMA", "recovery_of cannot reference itself")
    if recovery is None and attempt != 0:
        raise AuditError("SCHEMA", "original event must use attempt 0")
    if recovery is not None and attempt == 0:
        raise AuditError("SCHEMA", "recovery event must use positive attempt")

    if kind == "start":
        return

    outcome = text_field(event, "outcome")
    if outcome not in {"pass", "fail", "deviation"}:
        raise AuditError("SCHEMA", "outcome: expected pass, fail, or deviation")
    event_issues = issues(event)
    if (outcome in {"fail", "deviation"} or recovery is not None) and not event_issues:
        raise AuditError("SCHEMA", "fail, deviation, or recovery requires issue_ids")
    internal_ms(event)

    has_symptom = "symptom" in event
    has_hypothesis = "first_hypothesis" in event
    if outcome == "fail":
        if not has_symptom or not has_hypothesis:
            raise AuditError("SCHEMA", "failed end requires symptom and first_hypothesis")
        text_field(event, "symptom")
        text_field(event, "first_hypothesis")
    elif has_symptom or has_hypothesis:
        raise AuditError("SCHEMA", "non-failed end cannot have error fields")


def check_next(
    event: dict[str, object],
    opened: dict[str, dict[str, object]],
    completed: dict[str, dict[str, object]],
) -> None:
    event_id = text_field(event, "event_id")
    scope = text_field(event, "scope")
    task_open = any(item["scope"] == "task" for item in opened.values())
    if event["kind"] == "start":
        if event_id in opened or event_id in completed:
            raise AuditError("JOURNAL", "duplicate event_id")
        if scope == "task":
            if opened or completed:
                raise AuditError("JOURNAL", "task start must be the first event")
        elif not task_open:
            raise AuditError("JOURNAL", "non-task event must be inside task envelope")
        recovery = event["recovery_of"]
        if recovery is not None:
            failed = completed.get(cast(str, recovery))
            if failed is None:
                raise AuditError("JOURNAL", "recovery must follow a completed failure")
            if failed["outcome"] != "fail":
                raise AuditError("JOURNAL", "recovery_of must reference failure")
            if int_field(event, "attempt") != int_field(failed, "attempt") + 1:
                raise AuditError("JOURNAL", "recovery attempt must increment")
        return

    start = opened.get(event_id)
    if start is None:
        raise AuditError("JOURNAL", "end has no preceding start")
    if scope == "task" and len(opened) != 1:
        raise AuditError("JOURNAL", "task end must follow all enclosed events")
    if any(
        event[key] != start[key]
        for key in ("scope", "stage", "attempt", "recovery_of")
    ):
        raise AuditError("JOURNAL", "start/end identity fields differ")
    recovery = start["recovery_of"]
    if recovery is not None and issues(event) != issues(completed[cast(str, recovery)]):
        raise AuditError("JOURNAL", "recovery end issue_ids differ from failure")


def accept_next(
    event: dict[str, object],
    opened: dict[str, dict[str, object]],
    completed: dict[str, dict[str, object]],
) -> None:
    event_id = text_field(event, "event_id")
    if event["kind"] == "start":
        opened[event_id] = event
    else:
        del opened[event_id]
        completed[event_id] = event


def new_output(raw_path: str) -> TextIO:
    if not raw_path or "\x00" in raw_path or raw_path.endswith(os.sep):
        raise AuditError("OUTPUT", "invalid output path")
    path = os.path.abspath(raw_path)
    parent, name = os.path.split(path)
    if os.path.realpath(parent) != parent:
        raise AuditError("OUTPUT", "output parent path contains a symlink")
    if not name or name in {".", ".."}:
        raise AuditError("OUTPUT", "invalid output basename")

    try:
        before = os.lstat(parent)
    except OSError as exc:
        raise AuditError("OUTPUT", "output parent unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or before.st_uid != os.getuid()
        or stat.S_IMODE(before.st_mode) != 0o700
    ):
        raise AuditError("OUTPUT", "parent must be owned, non-symlink, mode 0700")

    parent_fd = -1
    output_fd = -1
    try:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        after = os.fstat(parent_fd)
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or after.st_uid != os.getuid()
            or not stat.S_ISDIR(after.st_mode)
            or stat.S_IMODE(after.st_mode) != 0o700
        ):
            raise AuditError("OUTPUT", "output parent changed")
        output_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        os.fchmod(output_fd, 0o600)
        info = os.fstat(output_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise AuditError("OUTPUT", "new output failed safety checks")
        handle = cast(
            TextIO,
            open(output_fd, "w", encoding="utf-8", newline="\n", closefd=True),
        )
        output_fd = -1
        return handle
    except AuditError:
        raise
    except OSError as exc:
        raise AuditError("OUTPUT", "target must be new and non-symlink") from exc
    finally:
        if output_fd >= 0:
            os.close(output_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def record(output: str) -> dict[str, object]:
    clock_id = str(uuid.uuid4())
    opened: dict[str, dict[str, object]] = {}
    completed: dict[str, dict[str, object]] = {}
    count = 0
    previous_utc: datetime | None = None
    previous_monotonic: int | None = None

    with new_output(output) as handle:
        for line_number, line in enumerate(sys.stdin, 1):
            if not line.strip():
                raise AuditError("SCHEMA", f"line {line_number}: blank")
            event = json_object(line, f"line {line_number}")
            validate_event(event)
            check_next(event, opened, completed)
            now = datetime.now(timezone.utc)
            monotonic_ns = time.monotonic_ns()
            if previous_utc is not None and now <= previous_utc:
                raise AuditError("CLOCK", "UTC clock did not advance")
            if previous_monotonic is not None and monotonic_ns <= previous_monotonic:
                raise AuditError("CLOCK", "monotonic clock did not advance")

            count += 1
            payload = dict(event)
            payload.update(
                {
                    "clock_id": clock_id,
                    "recorded_at_utc": now.isoformat(timespec="microseconds").replace(
                        "+00:00", "Z"
                    ),
                    "monotonic_ns": monotonic_ns,
                    "sequence": count,
                }
            )
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            accept_next(event, opened, completed)
            previous_utc = now
            previous_monotonic = monotonic_ns

    if count == 0:
        raise AuditError("JOURNAL", "no events recorded")
    if opened:
        raise AuditError("JOURNAL", "recording ended with unpaired starts")
    if sum(item["scope"] == "task" for item in completed.values()) != 1:
        raise AuditError("JOURNAL", "expected exactly one task envelope")
    return {"status": "ok", "clock_id": clock_id, "events": count}


def parser() -> Parser:
    result = Parser()
    subcommands = result.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("record")
    command.add_argument("--output", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        result = record(cast(str, args.output))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except AuditError as exc:
        print(f"ERROR[{exc.category}]: {str(exc).replace(chr(10), ' ')}", file=sys.stderr)
        return 1
    except OSError:
        print("ERROR[IO]: operating-system I/O failure", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

## Appendix B2 — final complete bytes

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
import uuid
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NoReturn, TextIO, cast

ISSUE_RE = re.compile(r"MODEL-(?:SHELL|SDD|RUN|PLAN)-\d{2}")
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z")
WALL_RE = re.compile(r"(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
TOOL_HEADING = "## Tool results"
TABLE_HEADER = (
    "| Ordinal | Tool | Outcome | Wall ms | Observed shape | Retry count | Issue ID |"
)
TABLE_SEPARATOR = "|---:|---|---|---:|---|---:|---|"
GENERATED = {"clock_id", "recorded_at_utc", "monotonic_ns", "sequence"}


class AuditError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AuditError("USAGE", message)


def json_value(text: str, label: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise AuditError("JSON", f"{label}: duplicate key {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> NoReturn:
        raise AuditError("JSON", f"{label}: invalid constant {value}")

    try:
        value: object = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (ValueError, RecursionError) as exc:
        raise AuditError("JSON", f"{label}: invalid JSON") from exc
    return value


def json_object(text: str, label: str) -> dict[str, object]:
    value = json_value(text, label)
    if not isinstance(value, dict):
        raise AuditError("SCHEMA", f"{label}: expected object")
    return cast(dict[str, object], value)


def text_field(event: dict[str, object], key: str) -> str:
    value = event[key]
    if not isinstance(value, str) or not value or value != value.strip():
        raise AuditError("SCHEMA", f"{key}: expected nonblank trimmed string")
    return value


def int_field(event: dict[str, object], key: str) -> int:
    value = event[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuditError("SCHEMA", f"{key}: expected integer")
    return value


def issues(event: dict[str, object]) -> tuple[str, ...]:
    value = event["issue_ids"]
    if not isinstance(value, list):
        raise AuditError("SCHEMA", "issue_ids: expected array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or ISSUE_RE.fullmatch(item) is None:
            raise AuditError("SCHEMA", "issue_ids: invalid issue ID")
        result.append(item)
    if len(result) != len(set(result)):
        raise AuditError("SCHEMA", "issue_ids: duplicate issue ID")
    return tuple(result)


def internal_ms(event: dict[str, object]) -> None:
    if "internal_ms" not in event:
        return
    value = event["internal_ms"]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AuditError("SCHEMA", "internal_ms: expected JSON number")
    if value < 0 or (isinstance(value, float) and (value != value or value == float("inf"))):
        raise AuditError("SCHEMA", "internal_ms: expected finite nonnegative number")


def validate_event(event: dict[str, object]) -> None:
    identity = {"event_id", "kind", "scope", "stage", "attempt", "recovery_of"}
    kind = event.get("kind")
    if kind == "start":
        required = identity
        allowed = required
    elif kind == "end":
        required = identity | {"outcome", "issue_ids"}
        allowed = required | {"symptom", "first_hypothesis", "internal_ms"}
    else:
        raise AuditError("SCHEMA", "kind: expected start or end")

    missing = required - set(event)
    unknown = set(event) - allowed
    if missing:
        raise AuditError("SCHEMA", f"missing: {','.join(sorted(missing))}")
    if unknown:
        raise AuditError("SCHEMA", f"unknown: {','.join(sorted(unknown))}")

    event_id = text_field(event, "event_id")
    scope = text_field(event, "scope")
    if scope not in {"task", "stage", "call"}:
        raise AuditError("SCHEMA", "scope: expected task, stage, or call")
    text_field(event, "stage")
    attempt = int_field(event, "attempt")
    if attempt < 0:
        raise AuditError("SCHEMA", "attempt: expected nonnegative integer")

    recovery = event["recovery_of"]
    if recovery is not None:
        if not isinstance(recovery, str) or not recovery or recovery != recovery.strip():
            raise AuditError("SCHEMA", "recovery_of: expected null or nonblank string")
        if recovery == event_id:
            raise AuditError("SCHEMA", "recovery_of cannot reference itself")
    if recovery is None and attempt != 0:
        raise AuditError("SCHEMA", "original event must use attempt 0")
    if recovery is not None and attempt == 0:
        raise AuditError("SCHEMA", "recovery event must use positive attempt")

    if kind == "start":
        return

    outcome = text_field(event, "outcome")
    if outcome not in {"pass", "fail", "deviation"}:
        raise AuditError("SCHEMA", "outcome: expected pass, fail, or deviation")
    event_issues = issues(event)
    if (outcome in {"fail", "deviation"} or recovery is not None) and not event_issues:
        raise AuditError("SCHEMA", "fail, deviation, or recovery requires issue_ids")
    internal_ms(event)

    has_symptom = "symptom" in event
    has_hypothesis = "first_hypothesis" in event
    if outcome == "fail":
        if not has_symptom or not has_hypothesis:
            raise AuditError("SCHEMA", "failed end requires symptom and first_hypothesis")
        text_field(event, "symptom")
        text_field(event, "first_hypothesis")
    elif has_symptom or has_hypothesis:
        raise AuditError("SCHEMA", "non-failed end cannot have error fields")


def check_next(
    event: dict[str, object],
    opened: dict[str, dict[str, object]],
    completed: dict[str, dict[str, object]],
) -> None:
    event_id = text_field(event, "event_id")
    scope = text_field(event, "scope")
    task_open = any(item["scope"] == "task" for item in opened.values())
    if event["kind"] == "start":
        if event_id in opened or event_id in completed:
            raise AuditError("JOURNAL", "duplicate event_id")
        if scope == "task":
            if opened or completed:
                raise AuditError("JOURNAL", "task start must be the first event")
        elif not task_open:
            raise AuditError("JOURNAL", "non-task event must be inside task envelope")
        recovery = event["recovery_of"]
        if recovery is not None:
            failed = completed.get(cast(str, recovery))
            if failed is None:
                raise AuditError("JOURNAL", "recovery must follow a completed failure")
            if failed["outcome"] != "fail":
                raise AuditError("JOURNAL", "recovery_of must reference failure")
            if int_field(event, "attempt") != int_field(failed, "attempt") + 1:
                raise AuditError("JOURNAL", "recovery attempt must increment")
        return

    start = opened.get(event_id)
    if start is None:
        raise AuditError("JOURNAL", "end has no preceding start")
    if scope == "task" and len(opened) != 1:
        raise AuditError("JOURNAL", "task end must follow all enclosed events")
    if any(
        event[key] != start[key]
        for key in ("scope", "stage", "attempt", "recovery_of")
    ):
        raise AuditError("JOURNAL", "start/end identity fields differ")
    recovery = start["recovery_of"]
    if recovery is not None and issues(event) != issues(completed[cast(str, recovery)]):
        raise AuditError("JOURNAL", "recovery end issue_ids differ from failure")


def accept_next(
    event: dict[str, object],
    opened: dict[str, dict[str, object]],
    completed: dict[str, dict[str, object]],
) -> None:
    event_id = text_field(event, "event_id")
    if event["kind"] == "start":
        opened[event_id] = event
    else:
        del opened[event_id]
        completed[event_id] = event


def new_output(raw_path: str) -> TextIO:
    if not raw_path or "\x00" in raw_path or raw_path.endswith(os.sep):
        raise AuditError("OUTPUT", "invalid output path")
    path = os.path.abspath(raw_path)
    parent, name = os.path.split(path)
    if os.path.realpath(parent) != parent:
        raise AuditError("OUTPUT", "output parent path contains a symlink")
    if not name or name in {".", ".."}:
        raise AuditError("OUTPUT", "invalid output basename")

    try:
        before = os.lstat(parent)
    except OSError as exc:
        raise AuditError("OUTPUT", "output parent unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or before.st_uid != os.getuid()
        or stat.S_IMODE(before.st_mode) != 0o700
    ):
        raise AuditError("OUTPUT", "parent must be owned, non-symlink, mode 0700")

    parent_fd = -1
    output_fd = -1
    try:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        after = os.fstat(parent_fd)
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or after.st_uid != os.getuid()
            or not stat.S_ISDIR(after.st_mode)
            or stat.S_IMODE(after.st_mode) != 0o700
        ):
            raise AuditError("OUTPUT", "output parent changed")
        output_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        os.fchmod(output_fd, 0o600)
        info = os.fstat(output_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise AuditError("OUTPUT", "new output failed safety checks")
        handle = cast(
            TextIO,
            open(output_fd, "w", encoding="utf-8", newline="\n", closefd=True),
        )
        output_fd = -1
        return handle
    except AuditError:
        raise
    except OSError as exc:
        raise AuditError("OUTPUT", "target must be new and non-symlink") from exc
    finally:
        if output_fd >= 0:
            os.close(output_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def record(output: str) -> dict[str, object]:
    clock_id = str(uuid.uuid4())
    opened: dict[str, dict[str, object]] = {}
    completed: dict[str, dict[str, object]] = {}
    count = 0
    previous_utc: datetime | None = None
    previous_monotonic: int | None = None

    with new_output(output) as handle:
        for line_number, line in enumerate(sys.stdin, 1):
            if not line.strip():
                raise AuditError("SCHEMA", f"line {line_number}: blank")
            event = json_object(line, f"line {line_number}")
            validate_event(event)
            check_next(event, opened, completed)
            now = datetime.now(timezone.utc)
            monotonic_ns = time.monotonic_ns()
            if previous_utc is not None and now <= previous_utc:
                raise AuditError("CLOCK", "UTC clock did not advance")
            if previous_monotonic is not None and monotonic_ns <= previous_monotonic:
                raise AuditError("CLOCK", "monotonic clock did not advance")

            count += 1
            payload = dict(event)
            payload.update(
                {
                    "clock_id": clock_id,
                    "recorded_at_utc": now.isoformat(timespec="microseconds").replace(
                        "+00:00", "Z"
                    ),
                    "monotonic_ns": monotonic_ns,
                    "sequence": count,
                }
            )
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            accept_next(event, opened, completed)
            previous_utc = now
            previous_monotonic = monotonic_ns

    if count == 0:
        raise AuditError("JOURNAL", "no events recorded")
    if opened:
        raise AuditError("JOURNAL", "recording ended with unpaired starts")
    if sum(item["scope"] == "task" for item in completed.values()) != 1:
        raise AuditError("JOURNAL", "expected exactly one task envelope")
    return {"status": "ok", "clock_id": clock_id, "events": count}


def read_owned_regular(raw_path: str, label: str) -> str:
    try:
        before = os.lstat(raw_path)
    except OSError as exc:
        raise AuditError("INPUT", f"{label}: unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.getuid()
    ):
        raise AuditError("INPUT", f"{label}: expected owned non-symlink regular file")

    fd = -1
    try:
        fd = os.open(raw_path, os.O_RDONLY | os.O_NOFOLLOW)
        after = os.fstat(fd)
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or after.st_uid != os.getuid()
            or not stat.S_ISREG(after.st_mode)
        ):
            raise AuditError("INPUT", f"{label}: changed while opening")
        with open(fd, "rb", closefd=True) as handle:
            fd = -1
            payload = handle.read()
    except AuditError:
        raise
    except OSError as exc:
        raise AuditError("INPUT", f"{label}: unsafe open failed") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("INPUT", f"{label}: expected UTF-8") from exc


def catalog(text: str, label: str) -> Counter[str]:
    value = json_value(text, label)
    if not isinstance(value, list) or not value:
        raise AuditError("CATALOG", f"{label}: expected nonempty array")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item != item.strip():
            raise AuditError("CATALOG", f"{label}: invalid name")
        names.append(item)
    if len(names) != len(set(names)):
        raise AuditError("CATALOG", f"{label}: duplicate name")
    return Counter(names)


def code_cell(cell: str, label: str) -> str:
    if (
        len(cell) < 3
        or cell[0] != "`"
        or cell[-1] != "`"
        or "`" in cell[1:-1]
        or not cell[1:-1]
        or cell[1:-1] != cell[1:-1].strip()
    ):
        raise AuditError("TABLE", f"{label}: invalid code cell")
    return cell[1:-1]


def table_issues(cell: str) -> tuple[str, ...]:
    if cell == "none":
        return ()
    result: list[str] = []
    for part in cell.split(";"):
        issue = code_cell(part.strip(), "issue")
        if ISSUE_RE.fullmatch(issue) is None:
            raise AuditError("TABLE", "issue: invalid ID")
        result.append(issue)
    if len(result) != len(set(result)):
        raise AuditError("TABLE", "issue: duplicate ID")
    return tuple(result)


def tool_table(text: str) -> Counter[str]:
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if line == TOOL_HEADING]
    if len(headings) != 1:
        raise AuditError("TABLE", "expected one exact Tool results heading")
    if lines.count(TABLE_HEADER) != 1:
        raise AuditError("TABLE", "expected one exact seven-column header")
    section_start = headings[0] + 1
    section_end = next(
        (
            index
            for index in range(section_start, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    headers = [
        index
        for index in range(section_start, section_end)
        if lines[index] == TABLE_HEADER
    ]
    if len(headers) != 1:
        raise AuditError("TABLE", "header is outside Tool results section")
    header = headers[0]
    if header + 1 >= section_end or lines[header + 1] != TABLE_SEPARATOR:
        raise AuditError("TABLE", "invalid separator")
    if any(line.startswith("|") for line in lines[section_start:header]):
        raise AuditError("TABLE", "unexpected table before tool table")

    tools: list[str] = []
    expected = 1
    cursor = header + 2
    while cursor < section_end and lines[cursor].startswith("|"):
        line = lines[cursor]
        if not line.endswith("|"):
            raise AuditError("TABLE", "row lacks final separator")
        cells = [part.strip() for part in line[1:-1].split("|")]
        if len(cells) != 7 or any(not cell for cell in cells):
            raise AuditError("TABLE", "row must contain seven nonblank cells")
        ordinal, tool_cell, outcome, wall_cell, shape, retry_cell, issue_cell = cells
        if not ordinal.isdecimal() or ordinal != str(expected):
            raise AuditError("TABLE", "ordinals must be canonical 1..N")
        tool = code_cell(tool_cell, "tool")
        if outcome not in {"pass", "pass_with_recovery", "pass_with_deviation"}:
            raise AuditError("TABLE", "invalid outcome")
        if WALL_RE.fullmatch(wall_cell) is None or float(wall_cell) == float("inf"):
            raise AuditError("TABLE", "wall time must be finite and nonnegative")
        if not shape:
            raise AuditError("TABLE", "blank observed shape")
        if not retry_cell.isdecimal() or retry_cell != str(int(retry_cell)):
            raise AuditError("TABLE", "invalid retry count")
        retry = int(retry_cell)
        row_issues = table_issues(issue_cell)
        if outcome == "pass_with_recovery":
            if retry < 1 or not row_issues:
                raise AuditError("TABLE", "recovery requires retry and issue ID")
        elif retry != 0:
            raise AuditError("TABLE", "non-recovery retry must be zero")
        if outcome == "pass_with_deviation" and not row_issues:
            raise AuditError("TABLE", "deviation requires issue ID")
        tools.append(tool)
        expected += 1
        cursor += 1

    if not tools:
        raise AuditError("TABLE", "tool table has no rows")
    if any(line.startswith("|") for line in lines[cursor:section_end]):
        raise AuditError("TABLE", "multiple tables in Tool results section")
    if len(tools) != len(set(tools)):
        raise AuditError("TABLE", "duplicate tool row")
    return Counter(tools)


def recorded_event(
    obj: dict[str, object],
) -> tuple[dict[str, object], str, datetime, int, int]:
    missing = GENERATED - set(obj)
    if missing:
        raise AuditError("SCHEMA", f"missing generated: {','.join(sorted(missing))}")
    client = {key: value for key, value in obj.items() if key not in GENERATED}
    validate_event(client)
    clock_id = text_field(obj, "clock_id")
    try:
        parsed = uuid.UUID(clock_id)
    except ValueError as exc:
        raise AuditError("CLOCK", "clock_id: invalid UUID") from exc
    if str(parsed) != clock_id or parsed.version != 4:
        raise AuditError("CLOCK", "clock_id: expected canonical UUID4")
    utc_text = text_field(obj, "recorded_at_utc")
    if UTC_RE.fullmatch(utc_text) is None:
        raise AuditError("CLOCK", "recorded_at_utc: invalid format")
    try:
        utc = datetime.strptime(utc_text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise AuditError("CLOCK", "recorded_at_utc: invalid value") from exc
    monotonic_ns = int_field(obj, "monotonic_ns")
    sequence = int_field(obj, "sequence")
    if monotonic_ns < 0 or sequence < 1:
        raise AuditError("CLOCK", "invalid monotonic_ns or sequence")
    return client, clock_id, utc, monotonic_ns, sequence


def journal(text: str) -> tuple[int, str]:
    lines = text.splitlines()
    if not lines:
        raise AuditError("JOURNAL", "journal is empty")
    opened: dict[str, dict[str, object]] = {}
    completed: dict[str, dict[str, object]] = {}
    starts: dict[str, tuple[datetime, int]] = {}
    clock_id: str | None = None
    previous_utc: datetime | None = None
    previous_monotonic: int | None = None
    for expected, line in enumerate(lines, 1):
        if not line.strip():
            raise AuditError("JOURNAL", "blank journal line")
        event, current_clock, utc, monotonic_ns, sequence = recorded_event(
            json_object(line, f"journal line {expected}")
        )
        if sequence != expected:
            raise AuditError("JOURNAL", "sequence differs from line order")
        if clock_id is None:
            clock_id = current_clock
        elif current_clock != clock_id:
            raise AuditError("CLOCK", "mixed clock IDs")
        if previous_utc is not None and utc <= previous_utc:
            raise AuditError("CLOCK", "UTC timestamps are not increasing")
        if previous_monotonic is not None and monotonic_ns <= previous_monotonic:
            raise AuditError("CLOCK", "monotonic timestamps are not increasing")
        check_next(event, opened, completed)
        event_id = text_field(event, "event_id")
        if event["kind"] == "start":
            starts[event_id] = (utc, monotonic_ns)
        else:
            start_utc, start_monotonic = starts[event_id]
            if utc <= start_utc or monotonic_ns <= start_monotonic:
                raise AuditError("CLOCK", "nonpositive event duration")
        accept_next(event, opened, completed)
        previous_utc = utc
        previous_monotonic = monotonic_ns
    if opened:
        raise AuditError("JOURNAL", "unpaired start")
    assert clock_id is not None
    return len(lines), clock_id


def validate(args: argparse.Namespace) -> dict[str, object]:
    journal_text = read_owned_regular(cast(str, args.journal), "journal")
    audit_text = read_owned_regular(cast(str, args.audit), "audit")
    live = catalog(
        read_owned_regular(cast(str, args.live_catalog), "live catalog"), "live catalog"
    )
    source = catalog(
        read_owned_regular(cast(str, args.source_catalog), "source catalog"),
        "source catalog",
    )
    config = catalog(
        read_owned_regular(cast(str, args.config_catalog), "config catalog"),
        "config catalog",
    )
    if live != source or live != config:
        raise AuditError("CATALOG", "catalog counters differ")
    table = tool_table(audit_text)
    if table != live:
        raise AuditError("TABLE", "tool table differs from catalogs")
    events, clock_id = journal(journal_text)
    return {
        "status": "ok",
        "catalog_count": sum(live.values()),
        "tool_rows": sum(table.values()),
        "clock_id": clock_id,
        "events": events,
    }


def parser() -> Parser:
    result = Parser()
    subcommands = result.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("record")
    command.add_argument("--output", required=True)
    command = subcommands.add_parser("validate")
    command.add_argument("--journal", required=True)
    command.add_argument("--audit", required=True)
    command.add_argument("--live-catalog", required=True)
    command.add_argument("--source-catalog", required=True)
    command.add_argument("--config-catalog", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "record":
            result = record(cast(str, args.output))
        else:
            result = validate(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except AuditError as exc:
        print(f"ERROR[{exc.category}]: {str(exc).replace(chr(10), ' ')}", file=sys.stderr)
        return 1
    except OSError:
        print("ERROR[IO]: operating-system I/O failure", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

## Appendix C — complete adversarial probe

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ERROR_RE = re.compile(r"ERROR\[([A-Z]+)\]: [^\n]+\n?\Z")
HEADER = "| Ordinal | Tool | Outcome | Wall ms | Observed shape | Retry count | Issue ID |"
SEPARATOR = "|---:|---|---|---:|---|---:|---|"


def base_events() -> list[dict[str, Any]]:
    return [
        {
            "event_id": "task",
            "kind": "start",
            "scope": "task",
            "stage": "remediation-integration",
            "attempt": 0,
            "recovery_of": None,
        },
        {
            "event_id": "failed",
            "kind": "start",
            "scope": "call",
            "stage": "catalog-call",
            "attempt": 0,
            "recovery_of": None,
        },
        {
            "event_id": "failed",
            "kind": "end",
            "scope": "call",
            "stage": "catalog-call",
            "attempt": 0,
            "recovery_of": None,
            "outcome": "fail",
            "issue_ids": ["MODEL-RUN-01"],
            "symptom": "caller-observed protocol symptom",
            "first_hypothesis": "caller-provided first hypothesis",
            "internal_ms": 1.25,
        },
        {
            "event_id": "recovery",
            "kind": "start",
            "scope": "call",
            "stage": "catalog-call-recovery",
            "attempt": 1,
            "recovery_of": "failed",
        },
        {
            "event_id": "recovery",
            "kind": "end",
            "scope": "call",
            "stage": "catalog-call-recovery",
            "attempt": 1,
            "recovery_of": "failed",
            "outcome": "pass",
            "issue_ids": ["MODEL-RUN-01"],
            "internal_ms": 0,
        },
        {
            "event_id": "clean",
            "kind": "start",
            "scope": "stage",
            "stage": "frozen-state",
            "attempt": 0,
            "recovery_of": None,
        },
        {
            "event_id": "clean",
            "kind": "end",
            "scope": "stage",
            "stage": "frozen-state",
            "attempt": 0,
            "recovery_of": None,
            "outcome": "deviation",
            "issue_ids": ["MODEL-PLAN-10"],
        },
        {
            "event_id": "task",
            "kind": "end",
            "scope": "task",
            "stage": "remediation-integration",
            "attempt": 0,
            "recovery_of": None,
            "outcome": "pass",
            "issue_ids": [],
        },
    ]


def encode(events: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in events).encode()


class Probe:
    def __init__(self, script: Path) -> None:
        self.script = script.resolve()
        raw_root = tempfile.mkdtemp(prefix="official-mcp-audit-")
        self.root = Path(os.path.realpath(raw_root))
        self.root.chmod(0o700)
        self.case_number = 0

    def close(self) -> None:
        shutil.rmtree(self.root)

    def command(self, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def error(
        self,
        category: str,
        *args: str,
        stdin: bytes | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        result = self.command(*args, stdin=stdin)
        assert result.returncode == 1, (category, result.returncode, result.stdout, result.stderr)
        stderr = result.stderr.decode()
        match = ERROR_RE.fullmatch(stderr)
        assert match is not None, stderr
        assert match.group(1) == category, stderr
        assert result.stdout == b"", result.stdout
        return result

    def record_error(
        self,
        category: str,
        events: list[dict[str, Any]] | None = None,
        raw: bytes | None = None,
    ) -> Path:
        self.case_number += 1
        target = self.root / f"bad-record-{self.case_number}.ndjson"
        self.error(
            category,
            "record",
            "--output",
            str(target),
            stdin=raw if raw is not None else encode(events or []),
        )
        return target

    def valid_record(self) -> tuple[Path, dict[str, Any]]:
        target = self.root / "journal.ndjson"
        result = self.command("record", "--output", str(target), stdin=encode(base_events()))
        assert result.returncode == 0, result.stderr
        assert result.stderr == b""
        output = json.loads(result.stdout)
        assert set(output) == {"status", "clock_id", "events"}
        assert output["status"] == "ok" and output["events"] == 8
        uuid.UUID(output["clock_id"])
        info = target.lstat()
        assert stat.S_ISREG(info.st_mode)
        assert info.st_uid == os.getuid()
        assert stat.S_IMODE(info.st_mode) == 0o600
        rows = [json.loads(line) for line in target.read_text().splitlines()]
        assert [row["sequence"] for row in rows] == list(range(1, 9))
        assert len({row["clock_id"] for row in rows}) == 1
        assert [row["scope"] for row in rows].count("task") == 2
        assert rows[0]["scope"] == rows[-1]["scope"] == "task"
        return target, output

    def record_green(self) -> Path:
        journal, _ = self.valid_record()
        before = (journal.lstat().st_ino, hashlib.sha256(journal.read_bytes()).hexdigest())

        self.error("OUTPUT", "record", "--output", str(journal), stdin=encode(base_events()))
        assert before == (journal.lstat().st_ino, hashlib.sha256(journal.read_bytes()).hexdigest())

        link = self.root / "journal-link.ndjson"
        link.symlink_to(journal)
        link_before = link.lstat()
        self.error("OUTPUT", "record", "--output", str(link), stdin=encode(base_events()))
        assert stat.S_ISLNK(link.lstat().st_mode)
        assert link.lstat().st_ino == link_before.st_ino
        assert before == (journal.lstat().st_ino, hashlib.sha256(journal.read_bytes()).hexdigest())

        mode_parent = self.root / "mode-parent"
        mode_parent.mkdir(mode=0o755)
        mode_parent.chmod(0o755)
        self.error(
            "OUTPUT",
            "record",
            "--output",
            str(mode_parent / "journal.ndjson"),
            stdin=encode(base_events()),
        )

        real_parent = self.root / "real-parent"
        real_parent.mkdir(mode=0o700)
        alias_parent = self.root / "alias-parent"
        alias_parent.symlink_to(real_parent, target_is_directory=True)
        self.error(
            "OUTPUT",
            "record",
            "--output",
            str(alias_parent / "journal.ndjson"),
            stdin=encode(base_events()),
        )

        task_start = base_events()[0]
        failed_start = base_events()[1]
        failed_end = base_events()[2]
        recovery_start = base_events()[3]
        recovery_end = base_events()[4]
        deviation_end = base_events()[6]
        task_end = base_events()[7]
        cases: list[tuple[str, list[dict[str, Any]] | None, bytes | None]] = []
        item = copy.deepcopy(task_start)
        item["unknown"] = 1
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["clock_id"] = str(uuid.uuid4())
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["attempt"] = True
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["attempt"] = -1
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["stage"] = " "
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["scope"] = "operation"
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item.pop("scope")
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["recovery_of"] = 7
        cases.append(("SCHEMA", [item], None))
        item = copy.deepcopy(task_start)
        item["internal_ms"] = 1
        cases.append(("SCHEMA", [item], None))
        cases.append(("JOURNAL", [copy.deepcopy(failed_end)], None))
        cases.append(("JOURNAL", [copy.deepcopy(task_start)], None))
        duplicate_task = copy.deepcopy(task_start)
        duplicate_task["event_id"] = "task-2"
        cases.append(("JOURNAL", [task_start, duplicate_task], None))
        cases.append(("JOURNAL", [copy.deepcopy(recovery_start)], None))

        passing = copy.deepcopy(base_events())
        passing[2]["outcome"] = "pass"
        passing[2].pop("symptom")
        passing[2].pop("first_hypothesis")
        cases.append(("JOURNAL", passing[:4], None))
        wrong_attempt = copy.deepcopy(base_events())
        wrong_attempt[3]["attempt"] = 2
        cases.append(("JOURNAL", wrong_attempt[:4], None))
        mismatch = copy.deepcopy(base_events())
        mismatch[2]["stage"] = "other"
        cases.append(("JOURNAL", mismatch[:3], None))
        mismatch = copy.deepcopy(base_events())
        mismatch[2]["scope"] = "stage"
        cases.append(("JOURNAL", mismatch[:3], None))
        mismatch = copy.deepcopy(base_events())
        mismatch[4]["issue_ids"] = ["MODEL-RUN-02"]
        cases.append(("JOURNAL", mismatch[:5], None))
        item = copy.deepcopy(failed_end)
        item["issue_ids"] = ["BAD-01"]
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(failed_end)
        item["issue_ids"] = ["MODEL-RUN-01", "MODEL-RUN-01"]
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(failed_end)
        item["issue_ids"] = []
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(failed_end)
        item.pop("symptom")
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(failed_end)
        item.pop("first_hypothesis")
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(failed_end)
        item["first_hypothesis"] = ""
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(failed_end)
        item["outcome"] = "pass"
        cases.append(("SCHEMA", [task_start, failed_start, item], None))
        item = copy.deepcopy(recovery_end)
        item["issue_ids"] = []
        cases.append(("SCHEMA", base_events()[:4] + [item], None))
        item = copy.deepcopy(deviation_end)
        item["issue_ids"] = []
        cases.append(("SCHEMA", base_events()[:6] + [item], None))
        item = copy.deepcopy(recovery_end)
        item["internal_ms"] = True
        cases.append(("SCHEMA", base_events()[:4] + [item], None))
        item = copy.deepcopy(recovery_end)
        item["internal_ms"] = -0.1
        cases.append(("SCHEMA", base_events()[:4] + [item], None))
        item = copy.deepcopy(recovery_end)
        item["internal_ms"] = 1e999
        cases.append(("JSON", base_events()[:4] + [item], None))
        cases.append(("JOURNAL", base_events()[1:3], None))
        cases.append(("JOURNAL", [task_start, failed_start, task_end], None))
        cases.append(("JOURNAL", [task_start, task_end, failed_start], None))
        cases.append(
            (
                "JSON",
                None,
                b'{"event_id":"x","kind":"end","scope":"task","stage":"x",'
                b'"attempt":0,"recovery_of":null,"outcome":"pass",'
                b'"issue_ids":[],"internal_ms":NaN}\n',
            )
        )
        huge_integer = (
            b'{"event_id":"x","kind":"start","scope":"task","stage":"x",'
            b'"attempt":' + b"9" * 5000 + b',"recovery_of":null}\n'
        )
        cases.append(("JSON", None, huge_integer))
        cases.append(("JSON", None, b"[" * 10000 + b"0" + b"]" * 10000 + b"\n"))
        cases.append(("SCHEMA", None, b"\n"))
        for category, events, raw in cases:
            self.record_error(category, events, raw)
        return journal

    def write_catalogs(self, names: list[str]) -> dict[str, Path]:
        result: dict[str, Path] = {}
        payload = json.dumps(names, separators=(",", ":")) + "\n"
        for label in ("live", "source", "config"):
            path = self.root / f"{label}.json"
            path.write_text(payload)
            result[label] = path
        return result

    def audit_text(self, names: list[str]) -> str:
        rows = ["## Tool results", "", HEADER, SEPARATOR]
        rows.extend(
            f"| {index} | `{name}` | pass | {index}.0 | synthetic | 0 | none |"
            for index, name in enumerate(names, 1)
        )
        return "\n".join(rows) + "\n"

    def validate_command(
        self,
        journal: Path,
        audit: Path,
        catalogs: dict[str, Path],
    ) -> tuple[str, ...]:
        return (
            "validate",
            "--journal",
            str(journal),
            "--audit",
            str(audit),
            "--live-catalog",
            str(catalogs["live"]),
            "--source-catalog",
            str(catalogs["source"]),
            "--config-catalog",
            str(catalogs["config"]),
        )

    def validator_error(
        self,
        category: str,
        journal: Path,
        audit: Path,
        catalogs: dict[str, Path],
    ) -> None:
        self.error(category, *self.validate_command(journal, audit, catalogs))

    def write_journal(self, base: Path, name: str, rows: list[dict[str, Any]]) -> Path:
        path = self.root / name
        path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        return path

    def retime(self, rows: list[dict[str, Any]]) -> None:
        base = datetime(2026, 8, 10, tzinfo=timezone.utc)
        for index, row in enumerate(rows, 1):
            row["sequence"] = index
            row["monotonic_ns"] = index * 1000
            row["recorded_at_utc"] = (
                (base + timedelta(microseconds=index))
                .isoformat(timespec="microseconds")
                .replace("+00:00", "Z")
            )

    def all_green(self) -> None:
        journal = self.record_green()
        names = ["tool_a", "tool_b", "tool_c"]
        catalogs = self.write_catalogs(names)
        audit = self.root / "audit.md"
        audit.write_text(self.audit_text(names))
        args = self.validate_command(journal, audit, catalogs)
        result = self.command(*args)
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert set(output) == {"status", "catalog_count", "tool_rows", "clock_id", "events"}
        assert output["status"] == "ok"
        assert output["catalog_count"] == output["tool_rows"] == 3
        assert output["events"] == 8

        names.append("tool_d")
        catalogs = self.write_catalogs(names)
        audit.write_text(self.audit_text(names))
        result = self.command(*self.validate_command(journal, audit, catalogs))
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert output["catalog_count"] == output["tool_rows"] == 4

        link = self.root / "input-link"
        link.symlink_to(journal)
        self.validator_error("INPUT", link, audit, catalogs)
        fifo = self.root / "input-fifo"
        os.mkfifo(fifo, 0o600)
        self.validator_error("INPUT", fifo, audit, catalogs)
        self.validator_error("INPUT", self.root, audit, catalogs)
        foreign = next(
            Path(path)
            for path in ("/etc/hosts", "/etc/passwd")
            if Path(path).exists() and Path(path).lstat().st_uid != os.getuid()
        )
        self.validator_error("INPUT", foreign, audit, catalogs)

        def catalog_case(value: object, category: str = "CATALOG") -> None:
            catalogs["live"].write_text(json.dumps(value) + "\n")
            self.validator_error(category, journal, audit, catalogs)
            self.write_catalogs(names)

        catalog_case({})
        catalog_case([])
        catalog_case(["tool_a", ""])
        catalog_case(["tool_a", "tool_a"])
        catalogs["source"].write_text(json.dumps(names[:-1]))
        self.validator_error("CATALOG", journal, audit, catalogs)
        self.write_catalogs(names)
        catalogs["config"].write_text(json.dumps(names + ["tool_e"]))
        self.validator_error("CATALOG", journal, audit, catalogs)
        self.write_catalogs(names)
        catalogs["live"].write_text("{bad")
        self.validator_error("JSON", journal, audit, catalogs)
        catalogs = self.write_catalogs(names)
        catalogs["live"].write_text("[" + "9" * 5000 + "]\n")
        self.validator_error("JSON", journal, audit, catalogs)
        catalogs = self.write_catalogs(names)
        catalogs["live"].write_text("[" * 10000 + "0" + "]" * 10000 + "\n")
        self.validator_error("JSON", journal, audit, catalogs)
        catalogs = self.write_catalogs(names)

        good_audit = self.audit_text(names)
        table_cases = [
            good_audit.replace("## Tool results", "## Wrong"),
            good_audit + "\n## Tool results\n",
            good_audit.replace(HEADER, "| Wrong |"),
            good_audit.replace(SEPARATOR, "|---|"),
            good_audit.replace("| 1 | `tool_a`", "| 2 | `tool_a`", 1),
            good_audit.replace("| 1 | `tool_a`", "| 1 | `tool_b`", 1),
            good_audit.replace("| 1 | `tool_a`", "| 1 | `tool_e`", 1),
            good_audit.replace("| pass | 1.0", "| fail | 1.0", 1),
            good_audit.replace("| pass | 1.0", "| pass | NaN", 1),
            good_audit.replace("| pass | 1.0", "| pass | Inf", 1),
            good_audit.replace("| pass | 1.0", "| pass | -1", 1),
            good_audit.replace("| 0 | none |", "| -1 | none |", 1),
            good_audit.replace("| synthetic |", "|  |", 1),
            good_audit.replace("| none |", "| MODEL-RUN-01 |", 1),
            good_audit.replace("| none |", "| `BAD-01` |", 1),
            good_audit.replace("| none |", "| `MODEL-RUN-01`; `MODEL-RUN-01` |", 1),
            "## Tool results\n\n" + HEADER + "\n" + SEPARATOR + "\n",
            good_audit + "| x | y | z | q | r | s | t |\n",
        ]
        for index, value in enumerate(table_cases):
            bad_audit = self.root / f"bad-table-{index}.md"
            bad_audit.write_text(value)
            self.validator_error("TABLE", journal, bad_audit, catalogs)
        missing_audit = self.root / "missing-tool.md"
        missing_audit.write_text(self.audit_text(names[:-1]))
        self.validator_error("TABLE", journal, missing_audit, catalogs)
        extra_audit = self.root / "extra-tool.md"
        extra_audit.write_text(self.audit_text(names + ["tool_e"]))
        self.validator_error("TABLE", journal, extra_audit, catalogs)

        original = [json.loads(line) for line in journal.read_text().splitlines()]

        def journal_case(
            name: str,
            rows: list[dict[str, Any]] | None,
            category: str,
            raw: str | None = None,
        ) -> None:
            path = self.root / f"bad-journal-{name}.ndjson"
            if raw is None:
                assert rows is not None
                self.write_journal(journal, path.name, rows)
            else:
                path.write_text(raw)
            self.validator_error(category, path, audit, catalogs)

        journal_case("empty", [], "JOURNAL", "")
        journal_case("json", None, "JSON", "{bad\n")
        rows = copy.deepcopy(original)
        rows[0]["unknown"] = 1
        journal_case("unknown", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[0].pop("clock_id")
        journal_case("missing-generated", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[0]["sequence"] = True
        journal_case("bool-sequence", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[0]["monotonic_ns"] = True
        journal_case("bool-monotonic", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[1]["clock_id"] = str(uuid.uuid4())
        journal_case("mixed-clock", rows, "CLOCK")
        rows = copy.deepcopy(original)
        rows[1]["sequence"] = 9
        journal_case("sequence", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[1]["recorded_at_utc"] = rows[0]["recorded_at_utc"]
        journal_case("utc-order", rows, "CLOCK")
        rows = copy.deepcopy(original)
        rows[1]["monotonic_ns"] = rows[0]["monotonic_ns"]
        journal_case("mono-order", rows, "CLOCK")
        rows = copy.deepcopy(original[:-1])
        journal_case("unpaired", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[1]["stage"] = "other"
        journal_case("identity", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[2]["scope"] = "stage"
        journal_case("scope-identity", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[1]["scope"] = "operation"
        journal_case("scope-value", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[1].pop("scope")
        journal_case("scope-missing", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[2].pop("symptom")
        journal_case("symptom", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[2].pop("first_hypothesis")
        journal_case("hypothesis", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[2]["first_hypothesis"] = ""
        journal_case("blank-hypothesis", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[2]["issue_ids"] = []
        journal_case("failure-empty-issues", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[4]["issue_ids"] = []
        journal_case("recovery-empty-issues", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[6]["issue_ids"] = []
        journal_case("deviation-empty-issues", rows, "SCHEMA")
        rows = copy.deepcopy(original)
        rows[4]["issue_ids"] = ["MODEL-RUN-02"]
        journal_case("recovery-issues", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[3]["attempt"] = rows[4]["attempt"] = 2
        journal_case("recovery-attempt", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[3]["recovery_of"] = rows[4]["recovery_of"] = "clean"
        rows = rows[:3] + rows[5:7] + rows[3:5] + rows[7:]
        self.retime(rows)
        journal_case("recovery-pass", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows = [rows[0], rows[1], rows[3], rows[2], *rows[4:]]
        self.retime(rows)
        journal_case("recovery-before", rows, "JOURNAL")
        rows = copy.deepcopy(original[1:-1])
        self.retime(rows)
        journal_case("task-missing", rows, "JOURNAL")
        rows = copy.deepcopy([original[0], original[-1], original[0], original[-1]])
        rows[2]["event_id"] = rows[3]["event_id"] = "task-2"
        self.retime(rows)
        journal_case("task-duplicate", rows, "JOURNAL")
        rows = copy.deepcopy([original[0], original[1], original[-1]])
        self.retime(rows)
        journal_case("task-premature-end", rows, "JOURNAL")
        rows = copy.deepcopy([original[0], original[-1], original[5], original[6]])
        self.retime(rows)
        journal_case("task-non-enclosing", rows, "JOURNAL")
        rows = copy.deepcopy(original)
        rows[0]["clock_id"] = "bad"
        journal_case("bad-clock", rows, "CLOCK")
        rows = copy.deepcopy(original)
        rows[4]["internal_ms"] = -1
        journal_case("internal-negative", rows, "SCHEMA")
        raw = journal.read_text().replace('"internal_ms":0', '"internal_ms":NaN', 1)
        journal_case("internal-nan", None, "JSON", raw)
        journal_case("huge-integer", None, "JSON", "[" + "9" * 5000 + "]\n")
        journal_case("deep-json", None, "JSON", "[" * 10000 + "0" + "]" * 10000 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("record-red", "record-green", "validate-red", "all-green"))
    parser.add_argument("--script", required=True, type=Path)
    args = parser.parse_args()

    if args.mode == "record-red":
        assert not args.script.exists()
        print("SCRIPT_ABSENT")
        return 0

    probe = Probe(args.script)
    try:
        if args.mode == "record-green":
            probe.record_green()
            print("RECORD_GREEN")
        elif args.mode == "validate-red":
            result = probe.error("USAGE", "validate")
            assert b"invalid choice" in result.stderr
            print("VALIDATOR_ABSENT")
        else:
            probe.all_green()
            print("ALL_GREEN")
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Exact commands and expected output

All Python execution uses the uv-managed Python 3.13 interpreter. The three commands
below are mutually exclusive filesystem states and are run only at the named Task
transition.

### Before Task 2 creates the script

```bash
/bin/bash -euo pipefail <<'BASH'
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo "UV must be absolute" >&2; exit 1 ;; esac
PROBE=.superpowers/sdd/modeling-remediation/appendix-c-probe.py
SCRIPT=scripts/official_blender_mcp_audit.py
test -s "$PROBE"
test ! -e "$SCRIPT"
"$UV" run --quiet --no-project --python 3.13 python "$PROBE" \
  record-red --script "$SCRIPT"
# exact stdout: SCRIPT_ABSENT
BASH
```

### After Task 2 writes Appendix B1

```bash
/bin/bash -euo pipefail <<'BASH'
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo "UV must be absolute" >&2; exit 1 ;; esac
PROBE=.superpowers/sdd/modeling-remediation/appendix-c-probe.py
SCRIPT=scripts/official_blender_mcp_audit.py
test -s "$PROBE"
test -f "$SCRIPT"
test ! -L "$SCRIPT"
"$UV" run --frozen --python 3.13 ruff check "$SCRIPT"
"$UV" run --frozen --python 3.13 mypy --strict "$SCRIPT"
"$UV" run --quiet --no-project --python 3.13 python -m py_compile "$SCRIPT"
"$UV" run --quiet --no-project --python 3.13 python "$PROBE" \
  record-green --script "$SCRIPT"
# exact stdout: RECORD_GREEN
"$UV" run --quiet --no-project --python 3.13 python "$PROBE" \
  validate-red --script "$SCRIPT"
# exact stdout: VALIDATOR_ABSENT
BASH
```

### After Task 3 replaces the script with Appendix B2

```bash
/bin/bash -euo pipefail <<'BASH'
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo "UV must be absolute" >&2; exit 1 ;; esac
PROBE=.superpowers/sdd/modeling-remediation/appendix-c-probe.py
SCRIPT=scripts/official_blender_mcp_audit.py
test -s "$PROBE"
test -f "$SCRIPT"
test ! -L "$SCRIPT"
"$UV" run --frozen --python 3.13 ruff check "$SCRIPT"
"$UV" run --frozen --python 3.13 mypy --strict "$SCRIPT"
"$UV" run --quiet --no-project --python 3.13 python -m py_compile "$SCRIPT"
"$UV" run --quiet --no-project --python 3.13 python "$PROBE" \
  all-green --script "$SCRIPT"
# exact stdout: ALL_GREEN
BASH
```

The probe asserts every negative invocation exits exactly `1`, writes no stdout, and
emits one stderr line matching `ERROR[EXPECTED_CATEGORY]: ...`. It also validates
three-name and four-name positives, exact success-key sets, real stdin pipes, output
mode/UID, inode/hash preservation, parent path symlinks, unsafe validator inputs,
catalog/table adversaries, journal clock/order/pair/recovery failures, and
Task-envelope, issue-ID, extreme-JSON, and `internal_ms` positive, boolean, negative,
infinite, and NaN cases.

## Appendix D: Exact no-write catalog and journal integration

Task 4 and Task 5 use a new private run root for every invocation. Set
`EXPECTED_ACTIVE_AUDIT_DIRTY=1` in Task 4 after changing only the active audit heading;
set it to `0` for the clean Task 5 replay. `TASK_N` and `TASK_REPORT` bind those lanes.
Before initial Phase M, leave `EXPECTED_MAIN_ANCHOR` empty so Appendix E's initial
anchor is used. After a clean Phase M gate failure, set it to the exact prior reviewed
HEAD for the next fix-forward round; the review package base does not move.

The recorder starts before the first App Server, effective-config, on-disk config,
source, external-baseline, audit, or Git-scope integration read. Bootstrap
operations needed solely to create the private directory/FIFO and start the
repository-owned recorder are not integration reads.

The live collector implements install-manual section 10.2 exactly:
`initialize`, `config/read(includeLayers=false)`, and
`mcpServerStatus/list(detail=toolsAndAuthOnly)`. It accepts both the dict and
list-of-tool-dicts live tool shapes. Source collection recognizes only function
definitions carrying an exact `@mcp.tool` decorator. The effective `config/read`
`mcp_servers.blender.enabled_tools` and the on-disk TOML
`mcp_servers.blender.enabled_tools` are independently extracted and must equal the
live and source catalogs. The config catalog file contains the effective set.

Each catalog contains only a sorted JSON string array. The run root is current-UID,
ordinary, non-symlink mode `0700`; catalogs, stderr captures, completed journal, and
validation timing are current-UID, ordinary, non-symlink mode `0600` files. Required
existing mutable paths reject missing targets, symlinks, foreign UID, and
world-writable mode.

Success closes every call, stage, and Task event, closes FD 9, waits for recorder EOF,
then validates. On a stage failure, the command writes the bounded exact stderr bytes
to the private `failure.json`, prints its resume FIFO, and blocks in the implementer's
still-live command session. The same implementer/caller keeps that session pending,
inspects the record, forms its immediate verbatim first hypothesis, appends this exact
compact line to its ignored Task report, writes the JSON object to the resume FIFO,
and then resumes/polls the original session:

```text
failure_ack={"first_hypothesis":"CALLER'S VERBATIM FIRST HYPOTHESIS","raw_stderr_sha256":"64 lowercase hex digits from failure.json"}
```

While the original command session remains pending, the same implementer/caller runs
this exact block in a second shell, setting only its own immediate hypothesis and the
three paths printed by the pending session:

```bash
/bin/bash -euo pipefail <<'BASH'
: "${UV_BIN:?reuse the absolute uv path from the pending command}"
: "${FAILURE_RECORD:?set to the printed failure.json path}"
: "${RESUME_FIFO:?set to the printed resume FIFO path}"
: "${TASK_REPORT:?set to this Task's ignored report path}"
: "${FIRST_HYPOTHESIS:?set the caller's immediate verbatim first hypothesis}"
CALLER_ACK="$(
  "$UV_BIN" run --quiet --no-project --python 3.13 python - \
    "$FAILURE_RECORD" "$TASK_REPORT" "$FIRST_HYPOTHESIS" <<'PY'
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

failure_path, report_path, hypothesis = sys.argv[1:]
if not hypothesis or hypothesis != hypothesis.strip():
    raise RuntimeError("first hypothesis must be nonblank verbatim text")
failure = json.loads(Path(failure_path).read_bytes())
stderr = base64.b64decode(failure["raw_stderr_b64"], validate=True)
digest = hashlib.sha256(stderr).hexdigest()
if digest != failure["raw_stderr_sha256"] or len(stderr) != failure["raw_stderr_bytes"]:
    raise RuntimeError("failure record does not match its raw stderr")
ack = {"first_hypothesis": hypothesis, "raw_stderr_sha256": digest}
ack_json = json.dumps(ack, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
payload = ("failure_ack=" + ack_json + "\n").encode("utf-8")
report = Path(report_path)
parent = os.path.abspath(report.parent)
if os.path.realpath(parent) != parent:
    raise RuntimeError("Task report parent contains a symlink")
flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
fd = os.open(report, flags, 0o600)
try:
    os.fchmod(fd, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        raise RuntimeError("unsafe Task report")
    view = memoryview(payload)
    while view:
        view = view[os.write(fd, view):]
    os.fsync(fd)
finally:
    os.close(fd)
print(ack_json)
PY
)"
printf '%s\n' "$CALLER_ACK" >"$RESUME_FIFO"
BASH
```

The FIFO acknowledgement is the JSON object after `failure_ack=` plus one newline. The
running command verifies that the report changed and contains exactly one identical
line, uses only that caller-provided hypothesis, closes the failed call/stage/Task
journal, and exits nonzero. It never creates a fallback hypothesis. Only after the
implementer observes that exit may it fix/retry by starting the complete Appendix D
command again with a new run root, recorder, clock, Task envelope, and `attempt=0`;
no cross-clock `recovery_of` is invented. Normal orchestration does not resume until
the implementer has completed, reported, and returned.

```bash
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
CODEX_BIN="${CODEX_BIN:-/Applications/ChatGPT.app/Contents/Resources/codex}"
CODEX_CONFIG="${CODEX_CONFIG:-${CODEX_HOME:-$HOME/.codex}/config.toml}"
AUDIT_FILE="docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md"
AUDIT_SCRIPT="scripts/official_blender_mcp_audit.py"
EXTERNAL_BASELINE=".superpowers/sdd/modeling-remediation/external-baseline/baseline.json"
BASE_COMMIT="09bf5c2089fe27b8dcdaa9af8115ec4d151359c3"
EXPECTED_ACTIVE_AUDIT_DIRTY="${EXPECTED_ACTIVE_AUDIT_DIRTY:-1}"
TASK_N="${TASK_N:?set to 4 or 5}"
TASK_REPORT="${TASK_REPORT:?set the ignored Task report path}"
EXPECTED_MAIN_ANCHOR="${EXPECTED_MAIN_ANCHOR:-}"
REPO_CWD="$(pwd -P)"
export GIT_NO_REPLACE_OBJECTS=1

case "$TASK_N:$EXPECTED_ACTIVE_AUDIT_DIRTY" in
  4:1|5:0) ;;
  *) echo "STOP: Task 4 requires dirty=1 and Task 5 requires dirty=0" >&2; exit 1 ;;
esac
case "$TASK_REPORT" in
  .superpowers/sdd/modeling-remediation/task-4-report.md|.superpowers/sdd/modeling-remediation/task-5-report.md) ;;
  *) echo "STOP: unexpected Task report path" >&2; exit 1 ;;
esac
for resolved_path in "$UV_BIN" "$CODEX_BIN" "$CODEX_CONFIG" "$REPO_CWD"; do
  case "$resolved_path" in
    /*) ;;
    *) echo "STOP: required path is not absolute: $resolved_path" >&2; exit 1 ;;
  esac
done

export UV_BIN CODEX_BIN CODEX_CONFIG AUDIT_FILE AUDIT_SCRIPT EXTERNAL_BASELINE
export BASE_COMMIT EXPECTED_ACTIVE_AUDIT_DIRTY TASK_N TASK_REPORT
export EXPECTED_MAIN_ANCHOR REPO_CWD
umask 077

RUN_ROOT="$(
  "$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
import os
import stat
import tempfile

temp_base = os.path.realpath(tempfile.gettempdir())
base_info = os.lstat(temp_base)
assert stat.S_ISDIR(base_info.st_mode) and not stat.S_ISLNK(base_info.st_mode)
root = tempfile.mkdtemp(prefix="official-blender-mcp-remediation-", dir=temp_base)
absolute = os.path.abspath(root)
resolved = os.path.realpath(absolute)
assert absolute == resolved
info = os.lstat(absolute)
assert stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
assert info.st_uid == os.getuid()
assert stat.S_IMODE(info.st_mode) == 0o700
print(absolute)
PY
)"
export RUN_ROOT

JOURNAL="$RUN_ROOT/events.ndjson"
EVENT_FIFO="$RUN_ROOT/events.fifo"
RESUME_FIFO="$RUN_ROOT/resume.fifo"
FAILURE_RECORD="$RUN_ROOT/failure.json"
LIVE_CATALOG="$RUN_ROOT/live-catalog.json"
SOURCE_CATALOG="$RUN_ROOT/source-catalog.json"
CONFIG_CATALOG="$RUN_ROOT/config-catalog.json"
COLLECT_STDERR="$RUN_ROOT/catalog-collector.stderr"
FROZEN_STDERR="$RUN_ROOT/external-frozen-state.stderr"
VALIDATE_TIMING="$RUN_ROOT/validate-timing.json"
export JOURNAL EVENT_FIFO RESUME_FIFO FAILURE_RECORD LIVE_CATALOG SOURCE_CATALOG
export CONFIG_CATALOG COLLECT_STDERR FROZEN_STDERR VALIDATE_TIMING

"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
import os
import stat

root = os.environ["RUN_ROOT"]
info = os.lstat(root)
assert stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
assert info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700
for variable in ("EVENT_FIFO", "RESUME_FIFO"):
    fifo = os.environ[variable]
    try:
        os.lstat(fifo)
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError(f"FIFO target already exists: {fifo}")
    os.mkfifo(fifo, 0o600)
    info = os.lstat(fifo)
    assert stat.S_ISFIFO(info.st_mode) and not stat.S_ISLNK(info.st_mode)
    assert info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600
PY

RECORDER_PID=""
RECORDER_FD_OPEN=0
cleanup_recorder() {
  if [ "$RECORDER_FD_OPEN" = 1 ]; then
    exec 9>&-
    RECORDER_FD_OPEN=0
  fi
  if [ -n "$RECORDER_PID" ]; then
    wait "$RECORDER_PID" || true
    RECORDER_PID=""
  fi
}
trap cleanup_recorder EXIT

"$UV_BIN" run --quiet --no-project --python 3.13 \
  python "$AUDIT_SCRIPT" record --output "$JOURNAL" <"$EVENT_FIFO" &
RECORDER_PID=$!
exec 9>"$EVENT_FIFO"
RECORDER_FD_OPEN=1

if [ -e "$TASK_REPORT" ]; then
  REPORT_BEFORE_SHA="$(shasum -a 256 "$TASK_REPORT" | awk '{print $1}')"
else
  REPORT_BEFORE_SHA="-"
fi
export REPORT_BEFORE_SHA
printf 'run_root=%s\nfailure_record=%s\nresume_fifo=%s\ntask_report=%s\n' \
  "$RUN_ROOT" "$FAILURE_RECORD" "$RESUME_FIFO" "$TASK_REPORT"

finish_failed_stage() {
  failed_call=$1
  failed_stage_event=$2
  failed_stage=$3
  failed_exit=$4
  failed_stderr=$5
  failed_issues=$6

  FAILURE_SHA="$({
    "$UV_BIN" run --quiet --no-project --python 3.13 python - \
      "$FAILURE_RECORD" "$failed_call" "$failed_stage_event" "$failed_stage" \
      "$failed_exit" "$failed_stderr" "$failed_issues" <<'PY'
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

output, call_id, stage_id, stage, raw_exit, stderr_path, raw_issues = sys.argv[1:]
stderr = Path(stderr_path).read_bytes()
if len(stderr) > 2_000_000:
    raise RuntimeError("stderr capture exceeds 2000000-byte bound")
issues = json.loads(raw_issues)
if not isinstance(issues, list) or not issues:
    raise RuntimeError("failure issue IDs must be nonempty")
digest = hashlib.sha256(stderr).hexdigest()
record = {
    "call_event_id": call_id,
    "exit_code": int(raw_exit),
    "raw_stderr_b64": base64.b64encode(stderr).decode("ascii"),
    "raw_stderr_bytes": len(stderr),
    "raw_stderr_sha256": digest,
    "stage": stage,
    "stage_event_id": stage_id,
}
payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
fd = os.open(output, flags, 0o600)
try:
    os.fchmod(fd, 0o600)
    view = memoryview(payload)
    while view:
        view = view[os.write(fd, view):]
    os.fsync(fd)
    opened = os.fstat(fd)
finally:
    os.close(fd)
final = os.lstat(output)
if (
    stat.S_ISLNK(final.st_mode)
    or not stat.S_ISREG(final.st_mode)
    or final.st_uid != os.getuid()
    or stat.S_IMODE(final.st_mode) != 0o600
    or (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino)
):
    raise RuntimeError("unsafe failure record")
print(digest)
PY
  })"
  export FAILURE_SHA

  printf '%s\n' \
    "CALLER_ACTION_REQUIRED: keep this session pending and read $FAILURE_RECORD" \
    "CALLER_ACTION_REQUIRED: append the exact failure_ack to $TASK_REPORT before writing $RESUME_FIFO" \
    >&2
  IFS= read -r CALLER_ACK <"$RESUME_FIFO"
  export CALLER_ACK

  "$UV_BIN" run --quiet --no-project --python 3.13 python - \
    "$FAILURE_RECORD" "$TASK_REPORT" "$REPORT_BEFORE_SHA" "$failed_issues" <<'PY' >&9
from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

failure_path, report_path, before_sha, raw_issues = sys.argv[1:]


def owned_regular(path: Path) -> bytes:
    absolute = os.path.abspath(path)
    if os.path.realpath(absolute) != absolute:
        raise RuntimeError(f"symlinked path component rejected: {path}")
    before = os.lstat(path)
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"owned regular file required: {path}")
    if before.st_uid != os.getuid() or before.st_mode & stat.S_IWOTH:
        raise RuntimeError(f"unsafe file ownership/mode: {path}")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file changed while opening: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(fd)
        current = os.lstat(path)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file changed while reading: {path}")
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file path changed while reading: {path}")
        return b"".join(chunks)
    finally:
        os.close(fd)


failure = json.loads(owned_regular(Path(failure_path)))
stderr = base64.b64decode(failure["raw_stderr_b64"], validate=True)
digest = hashlib.sha256(stderr).hexdigest()
if digest != failure["raw_stderr_sha256"] or digest != os.environ["FAILURE_SHA"]:
    raise RuntimeError("raw stderr digest mismatch")
if len(stderr) != failure["raw_stderr_bytes"]:
    raise RuntimeError("raw stderr length mismatch")

ack = json.loads(os.environ["CALLER_ACK"])
if set(ack) != {"first_hypothesis", "raw_stderr_sha256"}:
    raise RuntimeError("caller ack has wrong fields")
hypothesis = ack["first_hypothesis"]
if not isinstance(hypothesis, str) or not hypothesis or hypothesis != hypothesis.strip():
    raise RuntimeError("caller must provide a verbatim nonblank first_hypothesis")
if ack["raw_stderr_sha256"] != digest:
    raise RuntimeError("caller ack names the wrong failure")

report = owned_regular(Path(report_path))
report_sha = hashlib.sha256(report).hexdigest()
if report_sha == before_sha:
    raise RuntimeError("Task report was not written after the failure")
ack_line = "failure_ack=" + json.dumps(
    ack, ensure_ascii=False, sort_keys=True, separators=(",", ":")
)
if report.splitlines().count(ack_line.encode("utf-8")) != 1:
    raise RuntimeError("Task report must contain exactly one exact caller failure_ack line")

issues = json.loads(raw_issues)
symptom = (
    f"exit={failure['exit_code']};raw_stderr_bytes={failure['raw_stderr_bytes']};"
    f"raw_stderr_sha256={digest};raw_stderr_b64={failure['raw_stderr_b64']}"
)
common = {
    "attempt": 0,
    "first_hypothesis": hypothesis,
    "kind": "end",
    "outcome": "fail",
    "recovery_of": None,
    "symptom": symptom,
}
events = [
    {**common, "event_id": failure["call_event_id"], "scope": "call",
     "stage": failure["stage"], "issue_ids": issues},
    {**common, "event_id": failure["stage_event_id"], "scope": "stage",
     "stage": failure["stage"], "issue_ids": issues},
    {**common, "event_id": "remediation-integration", "scope": "task",
     "stage": "remediation-integration",
     "issue_ids": sorted(set(issues) | {"MODEL-PLAN-10"})},
]
for event in events:
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
PY

  exec 9>&-
  RECORDER_FD_OPEN=0
  recorder_exit=0
  wait "$RECORDER_PID" || recorder_exit=$?
  RECORDER_PID=""
  trap - EXIT
  if [ "$recorder_exit" != 0 ]; then
    echo "STOP: recorder rejected the paired failure journal: $recorder_exit" >&2
    exit "$recorder_exit"
  fi
  exit "$failed_exit"
}

printf '%s\n' \
  '{"event_id":"remediation-integration","kind":"start","scope":"task","stage":"remediation-integration","attempt":0,"recovery_of":null}' \
  '{"event_id":"catalog-stage","kind":"start","scope":"stage","stage":"catalog-collection","attempt":0,"recovery_of":null}' \
  '{"event_id":"catalog-call","kind":"start","scope":"call","stage":"catalog-collection","attempt":0,"recovery_of":null}' \
  >&9

set +e
"$UV_BIN" run --quiet --no-project --python 3.13 python - \
  2>"$COLLECT_STDERR" <<'PY'
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import selectors
import stat
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any

UID = os.getuid()
MAX_RESPONSE_BYTES = 1_048_576


class AppServerProtocolError(Exception):
    def __init__(self, method: str, error: Any, raw_response: bytes) -> None:
        super().__init__(method)
        self.method = method
        self.error = error
        self.raw_response = raw_response


def canonical(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    resolved = Path(os.path.realpath(absolute))
    if absolute != resolved:
        raise RuntimeError(f"unsafe symlinked path component: {absolute}")
    return resolved


def safe_directory(path: Path, *, private: bool = False) -> Path:
    path = canonical(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required directory missing: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"ordinary directory required: {path}")
    if info.st_uid != UID:
        raise RuntimeError(f"foreign UID rejected: {path}")
    if info.st_mode & stat.S_IWOTH:
        raise RuntimeError(f"world-writable directory rejected: {path}")
    if private and stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError(f"mode 0700 required: {path}")
    return path


def safe_file_bytes(path: Path) -> bytes:
    path = canonical(path)
    try:
        before = os.lstat(path)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required file missing: {path}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"ordinary file required: {path}")
    if before.st_uid != UID:
        raise RuntimeError(f"foreign UID rejected: {path}")
    if before.st_mode & stat.S_IWOTH:
        raise RuntimeError(f"world-writable file rejected: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"lstat/fstat identity changed: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file identity changed while reading: {path}")
        current = os.lstat(path)
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file path changed while reading: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def safe_executable(path: Path) -> Path:
    path = canonical(path)
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"ordinary executable required: {path}")
    if info.st_uid != UID:
        raise RuntimeError(f"foreign UID executable rejected: {path}")
    if info.st_mode & stat.S_IWOTH or not os.access(path, os.X_OK):
        raise RuntimeError(f"unsafe executable mode: {path}")
    return path


def normalize(names: Any, label: str) -> list[str]:
    if not isinstance(names, list) or not names:
        raise RuntimeError(f"{label}: nonempty string array required")
    if not all(isinstance(name, str) and name and name.strip() == name for name in names):
        raise RuntimeError(f"{label}: nonblank strings required")
    if len(names) != len(set(names)):
        raise RuntimeError(f"{label}: duplicate tool name")
    return sorted(names)


def write_catalog(path: Path, names: list[str]) -> None:
    run_root = safe_directory(Path(os.environ["RUN_ROOT"]), private=True)
    if path.parent != run_root:
        raise RuntimeError("catalog must be a direct child of the run root")
    try:
        os.lstat(path)
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError(f"catalog target already exists: {path}")
    payload = (json.dumps(names, separators=(",", ":")) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            view = view[os.write(descriptor, view):]
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final = os.lstat(path)
    if not stat.S_ISREG(final.st_mode) or stat.S_ISLNK(final.st_mode):
        raise RuntimeError(f"unsafe catalog type: {path}")
    if final.st_uid != UID or stat.S_IMODE(final.st_mode) != 0o600:
        raise RuntimeError(f"unsafe catalog ownership/mode: {path}")
    if (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino):
        raise RuntimeError(f"catalog identity changed: {path}")


run_root = safe_directory(Path(os.environ["RUN_ROOT"]), private=True)
repo_cwd = safe_directory(Path(os.environ["REPO_CWD"]))
codex_bin = safe_executable(Path(os.environ["CODEX_BIN"]))

proc = subprocess.Popen(
    [os.fspath(codex_bin), "app-server", "--stdio"],
    cwd=repo_cwd,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    bufsize=0,
)
if proc.stdin is None or proc.stdout is None:
    raise RuntimeError("App Server stdio unavailable")
selector = selectors.DefaultSelector()
selector.register(proc.stdout, selectors.EVENT_READ)


def request(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    payload = (
        json.dumps({"id": request_id, "method": method, "params": params}) + "\n"
    ).encode("utf-8")
    proc.stdin.write(payload)
    proc.stdin.flush()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for key, _ in selector.select(timeout=0.5):
            line = key.fileobj.readline(MAX_RESPONSE_BYTES + 1)
            if not line:
                raise RuntimeError(f"App Server closed during {method}")
            if len(line) > MAX_RESPONSE_BYTES or not line.endswith(b"\n"):
                raise RuntimeError(f"App Server response exceeded bound during {method}")
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise AppServerProtocolError(method, message["error"], line)
            result = message.get("result")
            if not isinstance(result, dict):
                raise RuntimeError(f"App Server result must be an object: {method}")
            return result
    raise TimeoutError(method)


protocol_failure: AppServerProtocolError | None = None
try:
    request(1, "initialize", {
        "clientInfo": {"name": "blender-mcp-remediation-verifier", "version": "1"}
    })
    effective_response = request(2, "config/read", {
        "cwd": os.fspath(repo_cwd), "includeLayers": False
    })
    cursor: str | None = None
    seen_cursors: set[str] = set()
    blender_server: dict[str, Any] | None = None
    request_id = 3
    while True:
        status = request(request_id, "mcpServerStatus/list", {
            "cursor": cursor,
            "limit": 100,
            "threadId": None,
            "detail": "toolsAndAuthOnly",
        })
        request_id += 1
        data = status.get("data")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise RuntimeError("server status data must be a list of objects")
        for item in data:
            name = item.get("name")
            if not isinstance(name, str) or not name:
                raise RuntimeError("server status name must be nonblank")
            if name == "blender":
                if blender_server is not None:
                    raise RuntimeError("duplicate blender server across status pages")
                blender_server = item
        next_cursor = status.get("nextCursor")
        if next_cursor is None:
            break
        if (
            not isinstance(next_cursor, str)
            or not next_cursor
            or next_cursor != next_cursor.strip()
        ):
            raise RuntimeError("invalid mcpServerStatus/list nextCursor")
        if next_cursor in seen_cursors:
            raise RuntimeError("mcpServerStatus/list cursor loop")
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    effective_config = effective_response.get("config")
    if not isinstance(effective_config, dict):
        raise RuntimeError("effective config object missing")
    effective_servers = effective_config.get("mcp_servers")
    if not isinstance(effective_servers, dict):
        raise RuntimeError("effective mcp_servers object missing")
    effective_blender = effective_servers.get("blender")
    if not isinstance(effective_blender, dict):
        raise RuntimeError("effective blender server missing")
    effective = normalize(effective_blender.get("enabled_tools"), "effective config")

    if blender_server is None:
        raise RuntimeError("exactly one blender server status required")
    raw_tools = blender_server.get("tools")
    if isinstance(raw_tools, dict):
        live_raw: list[Any] = list(raw_tools)
    elif isinstance(raw_tools, list):
        live_raw = []
        for tool in raw_tools:
            if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
                raise RuntimeError("invalid list-form live tool")
            live_raw.append(tool["name"])
    else:
        raise RuntimeError("live tools must be dict or list")
    live = normalize(live_raw, "live")
except AppServerProtocolError as exc:
    protocol_failure = exc
finally:
    selector.close()
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

if protocol_failure is not None:
    raw_response = protocol_failure.raw_response
    print(json.dumps({
        "category": "APP_SERVER_PROTOCOL_ERROR",
        "error": protocol_failure.error,
        "method": protocol_failure.method,
        "raw_response_b64": base64.b64encode(raw_response).decode("ascii"),
        "raw_response_bytes": len(raw_response),
        "raw_response_sha256": hashlib.sha256(raw_response).hexdigest(),
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")), file=sys.stderr)
    raise SystemExit(70)

disk_config = tomllib.loads(
    safe_file_bytes(Path(os.environ["CODEX_CONFIG"])).decode("utf-8")
)
disk_servers = disk_config.get("mcp_servers")
if not isinstance(disk_servers, dict):
    raise RuntimeError("on-disk mcp_servers object missing")
disk_blender = disk_servers.get("blender")
if not isinstance(disk_blender, dict):
    raise RuntimeError("on-disk blender server missing")
on_disk = normalize(disk_blender.get("enabled_tools"), "on-disk config")

arguments = disk_blender.get("args")
if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
    raise RuntimeError("configured args must be strings")
indices = [index for index, item in enumerate(arguments) if item == "--with-editable"]
if len(indices) != 1 or indices[0] + 1 >= len(arguments):
    raise RuntimeError("exactly one configured --with-editable path required")
editable_root = safe_directory(Path(arguments[indices[0] + 1]))
if editable_root.name != "mcp":
    raise RuntimeError("configured editable target must be mcp")
source_package = safe_directory(editable_root / "blmcp")

source_names: list[str] = []
for directory, directory_names, file_names in os.walk(source_package, followlinks=False):
    directory_path = safe_directory(Path(directory))
    for directory_name in list(directory_names):
        safe_directory(directory_path / directory_name)
    for file_name in file_names:
        if not file_name.endswith(".py"):
            continue
        source_path = directory_path / file_name
        tree = ast.parse(
            safe_file_bytes(source_path).decode("utf-8"),
            filename=os.fspath(source_path),
        )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if not (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "mcp"
                    and target.attr == "tool"
                ):
                    continue
                tool_name = node.name
                if isinstance(decorator, ast.Call):
                    for keyword in decorator.keywords:
                        if keyword.arg != "name":
                            continue
                        if not (
                            isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)
                            and keyword.value.value
                        ):
                            raise RuntimeError(f"nonliteral @mcp.tool name: {source_path}")
                        tool_name = keyword.value.value
                source_names.append(tool_name)
                break
source = normalize(source_names, "source")

if not (live == source == effective == on_disk):
    raise RuntimeError("live/source/effective/on-disk catalog mismatch")

write_catalog(Path(os.environ["LIVE_CATALOG"]), live)
write_catalog(Path(os.environ["SOURCE_CATALOG"]), source)
write_catalog(Path(os.environ["CONFIG_CATALOG"]), effective)
print(json.dumps({
    "live_count": len(live),
    "source_count": len(source),
    "effective_config_count": len(effective),
    "on_disk_config_count": len(on_disk),
    "equal": True,
}, sort_keys=True))
PY
COLLECT_EXIT=$?
set -e

if [ "$COLLECT_EXIT" != 0 ]; then
  finish_failed_stage \
    catalog-call catalog-stage catalog-collection "$COLLECT_EXIT" "$COLLECT_STDERR" \
    '["MODEL-PLAN-07"]'
fi

printf '%s\n' \
  '{"event_id":"catalog-call","kind":"end","scope":"call","stage":"catalog-collection","attempt":0,"recovery_of":null,"outcome":"pass","issue_ids":["MODEL-PLAN-07"]}' \
  '{"event_id":"catalog-stage","kind":"end","scope":"stage","stage":"catalog-collection","attempt":0,"recovery_of":null,"outcome":"pass","issue_ids":["MODEL-PLAN-07"]}' \
  '{"event_id":"frozen-stage","kind":"start","scope":"stage","stage":"external-frozen-state","attempt":0,"recovery_of":null}' \
  '{"event_id":"frozen-call","kind":"start","scope":"call","stage":"external-frozen-state","attempt":0,"recovery_of":null}' \
  >&9

set +e
"$UV_BIN" run --quiet --no-project --python 3.13 python - \
  2>"$FROZEN_STDERR" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

UID = os.getuid()
ACTIVE_AUDIT = "docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md"
STALE_BASE = "4f1913c364c995c93432bb24b1cc3c9ad1b8590f"
ALLOWED_TRACKED = {
    "docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md",
    "docs/use-official-blender-mcp.md",
    "scripts/checks.sh",
    "scripts/official_blender_mcp_audit.py",
    ACTIVE_AUDIT,
}
REQUIRED_TRACKED = {
    "docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md",
    "docs/use-official-blender-mcp.md",
    "scripts/checks.sh",
    "scripts/official_blender_mcp_audit.py",
}


def canonical(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    resolved = Path(os.path.realpath(absolute))
    if absolute != resolved:
        raise RuntimeError(f"unsafe symlinked path component: {absolute}")
    return resolved


def safe_bytes(path: Path) -> tuple[os.stat_result, bytes]:
    path = canonical(path)
    try:
        before = os.lstat(path)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required file missing: {path}") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"ordinary file required: {path}")
    if before.st_uid != UID:
        raise RuntimeError(f"foreign UID rejected: {path}")
    if before.st_mode & stat.S_IWOTH:
        raise RuntimeError(f"world-writable file rejected: {path}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"lstat/fstat identity changed: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        current = os.lstat(path)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file identity changed while reading: {path}")
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file path changed while reading: {path}")
        return before, b"".join(chunks)
    finally:
        os.close(descriptor)


def measure(path: Path, expected_type: str) -> dict[str, Any]:
    path = canonical(path)
    if expected_type == "file":
        info, content = safe_bytes(path)
        digest: str | None = hashlib.sha256(content).hexdigest()
    elif expected_type == "directory":
        try:
            info = os.lstat(path)
        except FileNotFoundError as exc:
            raise RuntimeError(f"required directory missing: {path}") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeError(f"ordinary directory required: {path}")
        if info.st_uid != UID:
            raise RuntimeError(f"foreign UID rejected: {path}")
        if info.st_mode & stat.S_IWOTH:
            raise RuntimeError(f"world-writable directory rejected: {path}")
        digest = None
    else:
        raise RuntimeError(f"unknown path type: {expected_type}")
    return {
        "resolved_path": os.fspath(path),
        "type": expected_type,
        "uid": info.st_uid,
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "sha256": digest,
    }


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", os.fspath(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.rstrip("\r\n")


def git_z(root: Path, *arguments: str) -> list[str]:
    completed = subprocess.run(
        ["git", "-C", os.fspath(root), *arguments],
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def git_blob(root: Path, object_id: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", os.fspath(root), "cat-file", "blob", object_id],
        check=True,
        capture_output=True,
    )
    return completed.stdout


_, baseline_bytes = safe_bytes(Path(os.environ["EXTERNAL_BASELINE"]))
baseline = json.loads(baseline_bytes)
if not isinstance(baseline, dict) or not isinstance(baseline.get("paths"), dict):
    raise RuntimeError("invalid external baseline")
paths = baseline["paths"]
for label, expected in paths.items():
    if not isinstance(label, str) or not isinstance(expected, dict):
        raise RuntimeError("invalid external baseline path entry")
    actual = measure(Path(expected["resolved_path"]), expected["type"])
    if actual != expected:
        raise RuntimeError(f"external path changed: {label}")

feature_root = Path(paths["feature_root"]["resolved_path"])
main_root = Path(paths["main_root"]["resolved_path"])
source_root = Path(paths["source_root"]["resolved_path"])
baseline_feature = baseline["feature_head"]
current_feature = git(feature_root, "rev-parse", "HEAD")
provenance = baseline.get("gate_provenance")
if not isinstance(provenance, dict) or set(provenance) != {
    "old_checks_blob", "old_checks_sha256", "retained_evidence_sha256"
}:
    raise RuntimeError("invalid gate provenance baseline")
old_checks_blob = git(feature_root, "rev-parse", f"{baseline_feature}:scripts/checks.sh")
if old_checks_blob != provenance["old_checks_blob"]:
    raise RuntimeError("baseline checks Git blob differs")
if hashlib.sha256(git_blob(feature_root, old_checks_blob)).hexdigest() != provenance[
    "old_checks_sha256"
]:
    raise RuntimeError("baseline checks SHA-256 differs")
_, final_checks_bytes = safe_bytes(feature_root / "scripts" / "checks.sh")
final_checks_sha256 = hashlib.sha256(final_checks_bytes).hexdigest()
if final_checks_sha256 == provenance["old_checks_sha256"]:
    raise RuntimeError("final checks bytes were not changed")
task1_report_path = (
    feature_root / ".superpowers/sdd/modeling-remediation/task-1-report.md"
)
_, task1_report_bytes = safe_bytes(task1_report_path)
task1_report_sha256 = hashlib.sha256(task1_report_bytes).hexdigest()
task1_report_text = task1_report_bytes.decode("utf-8")
marker_patterns = {
    "TASK1_FULL_GATE_GREEN": re.compile(
        r"TASK1_FULL_GATE_GREEN head=(?P<head>[0-9a-f]{40}) "
        r"tests=369 install=noneditable"
    ),
    "STALE_SNAPSHOT_NEGATIVE": re.compile(
        r"STALE_SNAPSHOT_NEGATIVE ordinary_sync=stale "
        r"adapter_sha256=(?P<adapter>[0-9a-f]{64})"
    ),
    "STALE_SNAPSHOT_REFRESH": re.compile(
        r"STALE_SNAPSHOT_REFRESH gate=pass tests=369 "
        r"adapter_sha256=(?P<adapter>[0-9a-f]{64})"
    ),
    "HIDDEN_SWEEP_GREEN": re.compile(
        r"HIDDEN_SWEEP_GREEN flags=verified "
        r"import=safe-path entrypoint=real exit=0"
    ),
    "TASK1_DISPOSABLE_ADVERSARY_GREEN": re.compile(
        r"TASK1_DISPOSABLE_ADVERSARY_GREEN head=(?P<head>[0-9a-f]{40}) "
        r"cleanup=exact"
    ),
}
marker_matches: dict[str, re.Match[str]] = {}
task1_report_lines = task1_report_text.splitlines()
for marker, pattern in marker_patterns.items():
    candidates = [line for line in task1_report_lines if line.startswith(marker)]
    if len(candidates) != 1:
        raise RuntimeError(f"Task 1 report must contain one raw {marker} output line")
    match = pattern.fullmatch(candidates[0])
    if match is None:
        raise RuntimeError(f"Task 1 report has malformed {marker} output")
    marker_matches[marker] = match
task1_head = marker_matches["TASK1_FULL_GATE_GREEN"].group("head")
if marker_matches["TASK1_DISPOSABLE_ADVERSARY_GREEN"].group("head") != task1_head:
    raise RuntimeError("Task 1 report markers name different Task 1 HEADs")
historical_adapter_sha256 = marker_matches["STALE_SNAPSHOT_NEGATIVE"].group(
    "adapter"
)
if historical_adapter_sha256 != (
    "48b21860a2c8c76a5f66ee7fc41fe5ad5f7e61fba4fa17abb6f0634dc8fb0506"
):
    raise RuntimeError("Task 1 report historical adapter SHA-256 differs")
git(feature_root, "cat-file", "-e", f"{STALE_BASE}^{{commit}}")
historical_adapter_blob = git(
    feature_root, "rev-parse", f"{STALE_BASE}:server/mcp/adapter.py"
)
if hashlib.sha256(git_blob(feature_root, historical_adapter_blob)).hexdigest() != (
    historical_adapter_sha256
):
    raise RuntimeError("Task 1 historical adapter SHA-256 differs from its Git blob")
current_adapter_sha256 = marker_matches["STALE_SNAPSHOT_REFRESH"].group("adapter")
if current_adapter_sha256 == historical_adapter_sha256:
    raise RuntimeError("Task 1 report refreshed adapter remained stale")
subprocess.run(
    ["git", "-C", os.fspath(feature_root), "merge-base", "--is-ancestor",
     baseline_feature, task1_head],
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "-C", os.fspath(feature_root), "merge-base", "--is-ancestor",
     task1_head, current_feature],
    check=True,
    capture_output=True,
)
task1_adapter_blob = git(
    feature_root, "rev-parse", f"{task1_head}:server/mcp/adapter.py"
)
if hashlib.sha256(git_blob(feature_root, task1_adapter_blob)).hexdigest() != (
    current_adapter_sha256
):
    raise RuntimeError("Task 1 refreshed adapter SHA-256 differs from its Git blob")
task1_checks_blob = git(
    feature_root, "rev-parse", f"{task1_head}:scripts/checks.sh"
)
if git_blob(feature_root, task1_checks_blob) != final_checks_bytes:
    raise RuntimeError("Task 1 checks Git blob differs from final checks bytes")
_, retained_evidence = safe_bytes(
    feature_root / ".superpowers/sdd/modeling-remediation/uv-hidden-flag-research.md"
)
retained_evidence_sha256 = hashlib.sha256(retained_evidence).hexdigest()
if retained_evidence_sha256 != provenance["retained_evidence_sha256"]:
    raise RuntimeError("retained failure evidence SHA-256 differs")
subprocess.run(
    ["git", "-C", os.fspath(feature_root), "merge-base", "--is-ancestor",
     baseline_feature, current_feature],
    check=True,
    capture_output=True,
)
review_base = baseline.get("review_base_head")
initial_main_anchor = baseline.get("initial_main_anchor")
if not isinstance(review_base, str) or not isinstance(initial_main_anchor, str):
    raise RuntimeError("external baseline Git anchors missing")
if review_base != initial_main_anchor:
    raise RuntimeError("initial main anchor must equal the immutable review base")
requested_anchor = os.environ.get("EXPECTED_MAIN_ANCHOR", "")
expected_main_anchor = requested_anchor or initial_main_anchor
if re.fullmatch(r"[0-9a-f]{40}", expected_main_anchor) is None:
    raise RuntimeError("expected main anchor must be a full lowercase SHA")
subprocess.run(
    ["git", "-C", os.fspath(main_root), "cat-file", "-e",
     f"{expected_main_anchor}^{{commit}}"],
    check=True,
    capture_output=True,
)
current_main = git(main_root, "rev-parse", "HEAD")
if current_main != expected_main_anchor:
    raise RuntimeError("main HEAD differs from this round's fixed anchor")
main_clean = git(main_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
if not main_clean:
    raise RuntimeError("main worktree must remain clean")
subprocess.run(
    ["git", "-C", os.fspath(feature_root), "merge-base", "--is-ancestor",
     review_base, expected_main_anchor],
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "-C", os.fspath(feature_root), "merge-base", "--is-ancestor",
     expected_main_anchor, current_feature],
    check=True,
    capture_output=True,
)
current_source = git(source_root, "rev-parse", "HEAD")
source_clean = git(source_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
if current_source != baseline["source_head"] or not source_clean:
    raise RuntimeError("official source state changed")

base_commit = os.environ["BASE_COMMIT"]
subprocess.run(
    ["git", "-C", os.fspath(feature_root), "merge-base", "--is-ancestor",
     base_commit, current_feature],
    check=True,
    capture_output=True,
)
changed = set(git_z(
    feature_root, "diff", "--name-only", "--no-renames", "-z",
    f"{base_commit}..{current_feature}", "--",
))
if not REQUIRED_TRACKED <= changed:
    raise RuntimeError("required remediation paths are absent from the tracked delta")
if not changed <= ALLOWED_TRACKED:
    raise RuntimeError("net tracked path outside the remediation allowlist")

history_changed: set[str] = set()
commits = git(
    feature_root, "rev-list", "--reverse", f"{base_commit}..{current_feature}"
).splitlines()
for commit in commits:
    fields = git(feature_root, "rev-list", "--parents", "-n", "1", commit).split()
    if len(fields) < 2 or fields[0] != commit:
        raise RuntimeError("remediation commit lacks a parent")
    history_changed.update(git_z(
        feature_root, "diff", "--name-only", "--no-renames", "-z",
        fields[1], commit, "--",
    ))
if not history_changed <= ALLOWED_TRACKED:
    raise RuntimeError("a remediation commit touched a path outside the allowlist")

status_lines = git(
    feature_root, "status", "--porcelain=v1", "--untracked-files=all"
).splitlines()
expected_dirty = os.environ["EXPECTED_ACTIVE_AUDIT_DIRTY"] == "1"
expected_status = [f" M {ACTIVE_AUDIT}"] if expected_dirty else []
if status_lines != expected_status:
    raise RuntimeError("working tree differs from the expected active-audit-only state")
if not expected_dirty:
    _, active_audit_bytes = safe_bytes(feature_root / ACTIVE_AUDIT)
    task1_digest_prefix = b"task1_report_sha256="
    task1_digest_literal = (
        f"task1_report_sha256={task1_report_sha256}".encode("ascii")
    )
    if (
        active_audit_bytes.count(task1_digest_prefix) != 1
        or active_audit_bytes.count(task1_digest_literal) != 1
    ):
        raise RuntimeError("active audit must contain the unique Task 1 report digest")

print(json.dumps({
    "external_paths_equal": True,
    "baseline_feature_head": baseline_feature,
    "current_feature_head": current_feature,
    "review_base_head": review_base,
    "old_checks_blob": old_checks_blob,
    "old_checks_sha256": provenance["old_checks_sha256"],
    "final_checks_sha256": final_checks_sha256,
    "retained_evidence_sha256": retained_evidence_sha256,
    "task1_report_sha256": task1_report_sha256,
    "task1_head": task1_head,
    "task1_stale_base": STALE_BASE,
    "task1_historical_adapter_blob": historical_adapter_blob,
    "task1_historical_adapter_sha256": historical_adapter_sha256,
    "task1_current_adapter_sha256": current_adapter_sha256,
    "expected_main_anchor": expected_main_anchor,
    "main_head": current_main,
    "main_clean": main_clean,
    "source_head": current_source,
    "source_clean": source_clean,
    "net_tracked_scope_count": len(changed),
    "history_tracked_scope_count": len(history_changed),
    "active_audit_dirty": expected_dirty,
}, sort_keys=True))
PY
FROZEN_EXIT=$?
set -e

if [ "$FROZEN_EXIT" != 0 ]; then
  finish_failed_stage \
    frozen-call frozen-stage external-frozen-state "$FROZEN_EXIT" "$FROZEN_STDERR" \
    '["MODEL-PLAN-10"]'
fi

printf '%s\n' \
  '{"event_id":"frozen-call","kind":"end","scope":"call","stage":"external-frozen-state","attempt":0,"recovery_of":null,"outcome":"pass","issue_ids":["MODEL-PLAN-10"]}' \
  '{"event_id":"frozen-stage","kind":"end","scope":"stage","stage":"external-frozen-state","attempt":0,"recovery_of":null,"outcome":"pass","issue_ids":["MODEL-PLAN-10"]}' \
  '{"event_id":"remediation-integration","kind":"end","scope":"task","stage":"remediation-integration","attempt":0,"recovery_of":null,"outcome":"pass","issue_ids":["MODEL-PLAN-05","MODEL-PLAN-07","MODEL-PLAN-10"]}' \
  >&9

exec 9>&-
RECORDER_FD_OPEN=0
wait "$RECORDER_PID"
RECORDER_PID=""
trap - EXIT

# Validate only after recorder EOF, exit, flush, and fsync. These clocks are external
# to the journal being validated and come from one uv-managed Python 3.13 process.
"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

UID = os.getuid()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def private_file(path: Path) -> None:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"ordinary file required: {path}")
    if info.st_uid != UID or stat.S_IMODE(info.st_mode) != 0o600:
        raise RuntimeError(f"current-UID mode-0600 file required: {path}")


root = Path(os.environ["RUN_ROOT"])
root_info = os.lstat(root)
if (
    stat.S_ISLNK(root_info.st_mode)
    or not stat.S_ISDIR(root_info.st_mode)
    or root_info.st_uid != UID
    or stat.S_IMODE(root_info.st_mode) != 0o700
):
    raise RuntimeError("private mode-0700 run root required")
for variable in ["JOURNAL", "LIVE_CATALOG", "SOURCE_CATALOG", "CONFIG_CATALOG"]:
    private_file(Path(os.environ[variable]))

utc_start = utc_now()
monotonic_start = time.monotonic_ns()
completed = subprocess.run(
    [
        sys.executable,
        os.environ["AUDIT_SCRIPT"],
        "validate",
        "--journal", os.environ["JOURNAL"],
        "--audit", os.environ["AUDIT_FILE"],
        "--live-catalog", os.environ["LIVE_CATALOG"],
        "--source-catalog", os.environ["SOURCE_CATALOG"],
        "--config-catalog", os.environ["CONFIG_CATALOG"],
    ],
    capture_output=True,
    text=True,
)
monotonic_end = time.monotonic_ns()
utc_end = utc_now()
if completed.returncode != 0:
    sys.stderr.write(completed.stderr)
    raise SystemExit(completed.returncode)
validation = json.loads(completed.stdout)
duration_ms = (monotonic_end - monotonic_start) / 1_000_000
if not math.isfinite(duration_ms) or duration_ms < 0:
    raise RuntimeError("invalid validation duration")
record = {
    "utc_start": utc_start,
    "utc_end": utc_end,
    "monotonic_start_ns": monotonic_start,
    "monotonic_end_ns": monotonic_end,
    "duration_ms": duration_ms,
    "validation": validation,
}

output = Path(os.environ["VALIDATE_TIMING"])
try:
    os.lstat(output)
except FileNotFoundError:
    pass
else:
    raise RuntimeError("validation timing target already exists")
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
descriptor = os.open(output, flags, 0o600)
payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
try:
    os.fchmod(descriptor, 0o600)
    view = memoryview(payload)
    while view:
        view = view[os.write(descriptor, view):]
    os.fsync(descriptor)
finally:
    os.close(descriptor)
private_file(output)
print(json.dumps({"run_root": os.fspath(root), **record}, sort_keys=True))
PY
```

Expected:

- live/source/effective-config/on-disk-config catalogs are dynamically equal;
- the three catalog files are sorted JSON string arrays and the config file contains
  the effective set;
- success produces one first/last Task envelope with nested catalog/frozen stage and
  call pairs;
- either stage failure preserves the exact bounded stderr bytes; the same
  implementer/caller keeps the command session pending, writes the matching raw-error
  digest and immediate verbatim first hypothesis to the ignored Task report, signals
  the resume FIFO, then observes call/stage/Task closure and a nonzero exit; no default,
  reconstruction, sanitization, or cross-run recovery link is created;
- the external paths, source pin/clean state, fixed round main anchor,
  immutable original review base, main cleanliness, and feature ancestry remain valid;
- the ignored Task 1 report has exactly one of each raw freshness/sweep marker, common
  Task 1 HEADs, replacement-disabled Git-bound old/current adapter and final-checks
  bytes, and a reported SHA-256; Task 5 additionally requires the tracked active audit
  to contain that exact `task1_report_sha256=<digest>` literal once;
- both the net delta and every individual commit since `09bf5c2` belong to the exact
  five-path remediation allowlist, so modify-then-revert cannot hide a frozen write;
- Task 4 has exactly the active audit as an unstaged modification; Task 5 is clean;
- validation starts only after recorder EOF/exit and has an external same-process
  UTC/monotonic bracket;
- no Blender mutation, render, navigation, save, config write, preference write,
  source write, or tracked repository write occurs.

## Appendix E: Exact external-baseline capture

### E1. Task 0 capture

Run this after the approved Plan-only commit and before Task 1. The output is ignored.
It reads the Codex config only to validate TOML and resolve the configured
`--with-editable` checkout; config and Blender preference contents are never printed.
It locates `main` by parsing `git worktree list --porcelain` and requires exactly one
worktree whose branch is `refs/heads/main`. Historical modeling artifacts are not
external baseline inputs: their temporary root was observed absent after date rollover
with the cleanup process unknown, independent Blender saves are not byte-deterministic,
and the retained hashes are historical-only.

```bash
/bin/bash -euo pipefail <<'BASH'
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"
CODEX_CONFIG="${CODEX_CONFIG:-${CODEX_HOME:-$HOME/.codex}/config.toml}"
BLENDER_USERPREF="${BLENDER_USERPREF:-$HOME/Library/Application Support/Blender/5.2/config/userpref.blend}"

for resolved_path in "$UV_BIN" "$CODEX_CONFIG" "$BLENDER_USERPREF"; do
  case "$resolved_path" in
    /*) ;;
    *) echo "STOP: required path is not absolute: $resolved_path" >&2; exit 1 ;;
  esac
done
export CODEX_CONFIG BLENDER_USERPREF

"$UV_BIN" run --quiet --no-project --python 3.13 python - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tomllib
from pathlib import Path
from typing import Any

UID = os.getuid()
PINNED_SOURCE = "4309a39646e644261624bfcd2bca669b343b7621"
OLD_CHECKS_SHA256 = "c0798f66b9b1ac6ed7e85b772adc0cca24b6c5f69ebb5df2e1b742a7c745307e"
RETAINED_EVIDENCE_SHA256 = "ebd57eee1c24b90c4a68d71b112c2682cf879f5ca345231960071661131edbd5"
def canonical(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    resolved = Path(os.path.realpath(absolute))
    if absolute != resolved:
        raise RuntimeError(f"unsafe symlinked path component: {absolute}")
    return resolved


def checked(path: Path, expected: str) -> tuple[Path, os.stat_result]:
    path = canonical(path)
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise RuntimeError(f"required path missing: {path}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise RuntimeError(f"symlink rejected: {path}")
    if info.st_uid != UID:
        raise RuntimeError(f"foreign UID rejected: {path}")
    if info.st_mode & stat.S_IWOTH:
        raise RuntimeError(f"world-writable path rejected: {path}")
    if expected == "file" and not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"regular file required: {path}")
    if expected == "directory" and not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"directory required: {path}")
    return path, info


def directory(path: Path) -> Path:
    return checked(path, "directory")[0]


def file_bytes(path: Path) -> tuple[Path, os.stat_result, bytes]:
    path, before = checked(path, "file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"lstat/fstat identity changed: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        current = os.lstat(path)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file identity changed while reading: {path}")
        if (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"file path changed while reading: {path}")
        return path, before, b"".join(chunks)
    finally:
        os.close(descriptor)


def metadata(path: Path, expected: str, content: bytes | None = None) -> dict[str, Any]:
    path, info = checked(path, expected)
    return {
        "resolved_path": os.fspath(path),
        "type": expected,
        "uid": info.st_uid,
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "sha256": None if content is None else hashlib.sha256(content).hexdigest(),
    }


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", os.fspath(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def parse_worktrees(raw: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in [*raw.splitlines(), ""]:
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, separator, value = line.partition(" ")
        current[key] = value if separator else ""
    return entries


def write_json(path: Path, value: object) -> None:
    parent = directory(path.parent)
    target = parent / path.name
    try:
        os.lstat(target)
    except FileNotFoundError:
        pass
    else:
        raise RuntimeError(f"output target already exists: {target}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            view = view[os.write(descriptor, view):]
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final = os.lstat(target)
    if not stat.S_ISREG(final.st_mode) or stat.S_ISLNK(final.st_mode):
        raise RuntimeError("unsafe baseline output type")
    if final.st_uid != UID or stat.S_IMODE(final.st_mode) != 0o600:
        raise RuntimeError("unsafe baseline output ownership/mode")
    if (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino):
        raise RuntimeError("baseline output identity changed")


feature_root = directory(Path(git(Path.cwd(), "rev-parse", "--show-toplevel")))
feature_head = git(feature_root, "rev-parse", "HEAD")
if git(feature_root, "branch", "--show-current") != "codex/official-blender-mcp-install":
    raise RuntimeError("unexpected feature branch")
if git(feature_root, "status", "--porcelain=v1", "--untracked-files=all"):
    raise RuntimeError("feature worktree must be clean before baseline capture")
checks_path, _, checks_content = file_bytes(feature_root / "scripts" / "checks.sh")
old_checks_sha256 = hashlib.sha256(checks_content).hexdigest()
if old_checks_sha256 != OLD_CHECKS_SHA256:
    raise RuntimeError("old checks SHA-256 differs")
old_checks_blob = git(feature_root, "rev-parse", f"{feature_head}:scripts/checks.sh")
if git(feature_root, "hash-object", os.fspath(checks_path)) != old_checks_blob:
    raise RuntimeError("old checks worktree bytes differ from the committed Git blob")
evidence_path = (
    feature_root / ".superpowers/sdd/modeling-remediation/uv-hidden-flag-research.md"
)
_, _, evidence_content = file_bytes(evidence_path)
retained_evidence_sha256 = hashlib.sha256(evidence_content).hexdigest()
if retained_evidence_sha256 != RETAINED_EVIDENCE_SHA256:
    raise RuntimeError("retained failure evidence SHA-256 differs")
worktrees = parse_worktrees(git(feature_root, "worktree", "list", "--porcelain"))
main_entries = [entry for entry in worktrees if entry.get("branch") == "refs/heads/main"]
if len(main_entries) != 1:
    raise RuntimeError("exactly one main worktree required")
main_root = directory(Path(main_entries[0]["worktree"]))
initial_main_anchor = git(main_root, "rev-parse", "HEAD")
review_base_head = initial_main_anchor
if initial_main_anchor != main_entries[0].get("HEAD"):
    raise RuntimeError("main worktree HEAD changed during discovery")
if git(main_root, "status", "--porcelain=v1", "--untracked-files=all"):
    raise RuntimeError("main worktree must be clean before baseline capture")

config_path, _, config_content = file_bytes(Path(os.environ["CODEX_CONFIG"]))
directory(config_path.parent)
config = tomllib.loads(config_content.decode("utf-8"))
server = config["mcp_servers"]["blender"]
arguments = server["args"]
if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
    raise RuntimeError("invalid blender args")
indices = [index for index, item in enumerate(arguments) if item == "--with-editable"]
if len(indices) != 1 or indices[0] + 1 >= len(arguments):
    raise RuntimeError("exactly one configured --with-editable path required")
editable_root = directory(Path(arguments[indices[0] + 1]))
if editable_root.name != "mcp":
    raise RuntimeError("configured editable target must be mcp")
source_root = directory(editable_root.parent)

preference_path, _, preference_content = file_bytes(Path(os.environ["BLENDER_USERPREF"]))
directory(preference_path.parent)

source_head = git(source_root, "rev-parse", "HEAD")
source_clean = git(source_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
if source_head != PINNED_SOURCE or not source_clean:
    raise RuntimeError("official source pin/clean contract failed")

sdd_root = directory(feature_root / ".superpowers" / "sdd")
remediation_root = sdd_root / "modeling-remediation"
try:
    os.lstat(remediation_root)
except FileNotFoundError:
    os.mkdir(remediation_root, 0o700)
else:
    directory(remediation_root)
baseline_root = remediation_root / "external-baseline"
try:
    os.lstat(baseline_root)
except FileNotFoundError:
    os.mkdir(baseline_root, 0o700)
else:
    raise RuntimeError("external baseline directory must be absent")
baseline_root = directory(baseline_root)
if stat.S_IMODE(os.lstat(baseline_root).st_mode) != 0o700:
    raise RuntimeError("external baseline directory must be mode 0700")

record = {
    "paths": {
        "feature_root": metadata(feature_root, "directory"),
        "main_root": metadata(main_root, "directory"),
        "codex_config": metadata(config_path, "file", config_content),
        "blender_userpref": metadata(preference_path, "file", preference_content),
        "source_root": metadata(source_root, "directory"),
    },
    "feature_head": feature_head,
    "gate_provenance": {
        "old_checks_blob": old_checks_blob,
        "old_checks_sha256": old_checks_sha256,
        "retained_evidence_sha256": retained_evidence_sha256,
    },
    "review_base_head": review_base_head,
    "initial_main_anchor": initial_main_anchor,
    "source_head": source_head,
    "source_clean": source_clean,
}
output = baseline_root / "baseline.json"
write_json(output, record)
print(json.dumps(record, sort_keys=True))
print(f"baseline_file={output}")
PY
BASH
```

Expected: exactly one main worktree is found; `review_base_head` and
`initial_main_anchor` both equal its captured clean HEAD; source pin/clean matches; the
private baseline directory is mode `0700`; `baseline.json` is a
current-UID regular non-symlink mode-`0600` file; stdout contains only resolved
path/type/UID/mode/SHA metadata, feature/main HEAD, source HEAD/clean,
the committed old-checks blob/SHA-256, retained-evidence SHA-256, and the baseline path.
The mutable checks path is not added to generic unchanged `paths`. Config and
preference contents are absent. Historical fixture/PNG files are not read, and their
previously recorded hashes are not described as current comparisons.
