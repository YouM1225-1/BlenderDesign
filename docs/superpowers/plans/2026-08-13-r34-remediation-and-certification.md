# R34 Remediation and Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the local pre-certification tools, repair the seven deduplicated R33 findings, obtain three reports with zero Critical/Important/Minor findings bound to one Plan identity, and create the protocol-authorized Plan-only commit.

**Architecture:** Work only in `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install`. Keep the tracked Plan untouched while hardening the ignored tools and editing `.superpowers/sdd/tools/cand.md`; publish the candidate to the tracked Plan only after all local gates pass. Freeze the Plan for each official three-lens round, and commit only after all three lenses certify the same bytes.

**Tech Stack:** Bash 3.2, Python 3.13 standard library, `/Users/yeminjie/.local/bin/uv`, Git worktrees, SHA-256, ignored `.superpowers/sdd/` coordination artifacts.

## Global Constraints

- The execution worktree is exactly `/Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install`, branch `codex/official-blender-mcp-install`, starting HEAD `59805fea5e69ccc894c5c3826cee3c48c72f4f27`.
- Before the three official reports are all `0/0/0`, do not run `git add` or `git commit`. This overrides the usual per-task commit cadence of the execution skill.
- There is exactly one Plan writer. While any official lens is running, do not modify the Plan or candidate.
- Never modify or recreate `.superpowers/sdd/modeling-remediation/final-retest-r1/invalid-journals.sha256`; its SHA-256 is `8292ac78073804687faab381181881ac7f522da1edea2dffe625626c1482c535`.
- Never modify either R1 journal; their SHA-256 values are `b6f2568116080d4936a3d753a419c771c00233a67111ed626cc2bbe169c79f0e` and `909fb6510a7ae4f115688add9d1eb0b25430ec9d4f490d16fb56b72343b24e7b`.
- Never modify `scripts/official_blender_mcp_audit.py`; it must remain 626 lines / 24168 bytes / SHA-256 `4a45f69f8aae1f72711119e9ecd4e4f6a91a3fcfe88488b737c7c154696ec3fe` and remain byte-identical to Appendix B2I.
- Never loosen symlink, UID, mode, nlink, dev, ino, or size checks. Do not kill Blender, MCP, or uv processes broadly.
- Set `PYTHONDONTWRITEBYTECODE=1` for every Python command. Mutable test fixtures, including Task 3's throwaway Plan copy, live only below newly created mode-0700 roots in `/private/tmp`. The `.superpowers/sdd/tools/cand.md` introduced by Task 4 is the durable ignored R34 work product that is later published, not a test fixture.
- Run `ALLOCATE=1` exactly once per real official round and only after the candidate has been published and all preflight checks pass. All other gate runs use `ALLOCATE=0`; allocation tests run only in private fixtures.
- Do not write to `main`. The current main HEAD is `245f2677bf0cef733693e2db9393fa497b643413`, main has an unrelated user-owned `.gitignore` modification, and `codex/official-blender-mcp-install...main` is currently `32 3`; Phase M is not part of this plan.
- The starting Plan identity is 26111 lines / 1072629 bytes / SHA-256 `d36cf53c4abf6f8681397da506e2400a7accaf9adf88e8f08f182f8159f45ffb`. Its current gate banner is `PLAN_PAYLOAD_IDENTITY_GREEN payloads=11 digest_sites=38 claims=56 identity_copies=28 readers=24 blocks=25 free_defs=133 commit_pins=17 publish_copies=4`.
- The measured Appendix C SHA-256 is `9e2f58d3bf98d9c7113d10362c4637f6a36e0a9fb389ff0b1d2c509f5806e0b3`; the `e04a3834…` value in the handoff table is stale and must not be copied into any assertion.
- The visual ACK A/B/C decision is not needed for R34. Stop after the Plan-only commit; do not start Plan Task 6, Task 7, live Blender execution, Phase R, or Phase M under this plan.
- After every task, append the change, reason, evidence, and deliberately omitted work to `.superpowers/sdd/progress.md`. The tool and report files below `.superpowers/sdd/` are ignored and must not be staged.

---

## File Structure

- Modify `.superpowers/sdd/tools/syntax.py`: recursively census and syntax-check every Markdown fence and every heredoc.
- Modify `.superpowers/sdd/tools/probes.sh`: build the five declared filesystem states, check exact outputs and return codes, exercise the RED reader lane, and propagate failure.
- Modify `.superpowers/sdd/tools/repair.py`: expose deterministic text repair and an opt-in marked-family digest regeneration mode.
- Modify `.superpowers/sdd/tools/mutate.py`: run the core mutation suite with exact expected matrices and hard-fail on absent/no-op mutations.
- Modify `.superpowers/sdd/tools/mutate2.py`: run the marked-family suite, including the two honestly disclosed family-digest-only cap escapes.
- Modify `.superpowers/sdd/tools/mutate3.py`: run delimiter and digest-splitting attacks with exact expected matrices.
- Create and then replace `.superpowers/sdd/tools/cand.md`: isolated candidate Plan; ignored, never staged.
- Modify `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`: only after the candidate passes; the only tracked file in the final commit.
- Append `.superpowers/sdd/progress.md`: durable ignored ledger.
- Create official ignored reports `plan-{spec,execution,ponytail}-review-rN.md` only through the Plan allocator.

## Success Criteria

1. Hardened syntax output proves 93 fences, 99 heredocs, 68 Bash fences, 10 Python fences, 49 Python heredocs, 41 Bash heredocs, and one Python `COLLECTOR` heredoc, with zero unclosed or invalid executable blocks; the eight `EOF` heredocs are explicitly counted as data.
2. Hardened probes execute five filesystem states, require exact positive stdout, require the exact Appendix C RED marker, test `all-green` under umasks 000/002/022/077, and exit nonzero on an injected output mutation.
3. Every mutation suite rejects missing/no-op mutations, enforces its expected RED/GREEN matrix, and returns nonzero on any deviation.
4. Task 4, Task 5, and Task 7 Appendix D extractors all return zero and emit byte-identical Appendix D integration bodies from their respective brief shapes.
5. Gate, syntax, probes, mutation suites, phrase sweeps, protected-byte checks, and `git diff --check` all pass on both candidate and published Plan.
6. Three fresh official reports contain zero Critical, zero Important, and zero Minor findings and bind the same final Plan line/byte/SHA identity at report start and end.
7. The final commit contains exactly `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`.

---

### Task 1: Make the syntax gate recursively complete

**Files:**
- Modify: `.superpowers/sdd/tools/syntax.py` (whole-file replacement)
- Test: `/private/tmp` candidates created by the verification commands below

**Interfaces:**
- Consumes: one Plan path plus explicit expected census values.
- Produces: exit 0 and one `SYNTAX_GREEN …` line only when counts, closure, Bash syntax, and Python syntax all match; otherwise exit 1 with a line-numbered diagnostic.

- [ ] **Step 1: Capture the existing undercount as RED evidence**

Run:

```bash
cd /Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install
P=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/syntax.py "$P"
```

Expected current output: `bash fences ok=68 bad=0; python blocks ok=53 bad=0`. This is RED evidence because the independently re-derived census is 93 fences and 99 heredocs.

- [ ] **Step 2: Replace `syntax.py` with this recursive implementation**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

FENCE_OPEN = re.compile(r"^ {0,3}(?P<run>`{3,})(?P<info>[^`\r\n]*)\r?\n?$")
FENCE_CLOSE = re.compile(r"^ {0,3}(?P<run>`{3,})[ \t]*\r?\n?$")
HEREDOC_OPEN = re.compile(
    r"<<(?P<dash>-?)[ \t]*(?:(?P<quote>['\"])(?P<quoted>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?P=quote)|(?P<bare>[A-Za-z_][A-Za-z0-9_]*))"
)


@dataclass(frozen=True)
class Block:
    first: int
    last: int
    language: str
    body: str


def fenced_blocks(lines: list[str]) -> tuple[list[Block], list[str]]:
    found: list[Block] = []
    errors: list[str] = []

    def walk(lo: int, hi: int, parent_limit: int | None = None) -> None:
        index = lo
        while index < hi:
            opened = FENCE_OPEN.match(lines[index])
            if opened is None:
                index += 1
                continue
            width = len(opened.group("run"))
            if parent_limit is not None and width >= parent_limit:
                index += 1
                continue
            info = opened.group("info").strip()
            language = info.split(None, 1)[0].lower() if info else ""
            closed_at = index + 1
            while closed_at < hi:
                closed = FENCE_CLOSE.match(lines[closed_at])
                if closed is not None:
                    close_width = len(closed.group("run"))
                    inside_parent = parent_limit is None or close_width < parent_limit
                    if close_width >= width and inside_parent:
                        break
                closed_at += 1
            if closed_at == hi:
                errors.append(f"unclosed {width}-tick fence at plan line {index + 1}")
                index += 1
                continue
            found.append(
                Block(index + 1, closed_at + 1, language, "".join(lines[index + 1:closed_at]))
            )
            walk(index + 1, closed_at, width)
            index = closed_at + 1

    walk(0, len(lines))
    return found, errors


def heredoc_blocks(lines: list[str]) -> tuple[list[Block], list[str]]:
    found: list[Block] = []
    errors: list[str] = []
    for index, line in enumerate(lines):
        for opened in HEREDOC_OPEN.finditer(line):
            tag = opened.group("quoted") or opened.group("bare")
            strip_tabs = opened.group("dash") == "-"
            body_first = index + 1
            if tag == "COLLECTOR":
                prior = line[:opened.start()]
                if re.search(r"<<-?['\"]?PY['\"]?", prior) is None:
                    errors.append(
                        f"COLLECTOR at plan line {index + 1} lacks preceding PY heredoc"
                    )
                    continue
                while body_first < len(lines):
                    candidate = lines[body_first].rstrip("\r\n")
                    if candidate in {"PY", "COLLECTOR"}:
                        break
                    body_first += 1
                if (
                    body_first == len(lines)
                    or lines[body_first].rstrip("\r\n") != "PY"
                ):
                    errors.append(
                        f"COLLECTOR at plan line {index + 1} has no preceding PY terminator"
                    )
                    continue
                body_first += 1
            closed_at = body_first
            while closed_at < len(lines):
                candidate = lines[closed_at].rstrip("\r\n")
                if strip_tabs:
                    candidate = candidate.lstrip("\t")
                if candidate == tag:
                    break
                closed_at += 1
            if closed_at == len(lines):
                errors.append(f"unclosed heredoc {tag} at plan line {index + 1}")
                continue
            found.append(Block(index + 1, closed_at + 1, tag, "".join(lines[body_first:closed_at])))
    return found, errors


def bash_syntax(body: str) -> str | None:
    result = subprocess.run(
        ["/bin/bash", "-n"], input=body, capture_output=True, text=True
    )
    return None if result.returncode == 0 else result.stderr.strip()


def python_syntax(body: str, line: int) -> str | None:
    try:
        compile(body, f"plan:{line}", "exec")
    except SyntaxError as error:
        return str(error)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-fences", type=int, required=True)
    parser.add_argument("--expect-heredocs", type=int, required=True)
    parser.add_argument("--expect-bash", type=int, required=True)
    parser.add_argument("--expect-python-fences", type=int, required=True)
    parser.add_argument("--expect-py-heredocs", type=int, required=True)
    parser.add_argument("--expect-bash-heredocs", type=int, required=True)
    parser.add_argument("--expect-collector", type=int, required=True)
    parser.add_argument("--expect-data", type=int, required=True)
    args = parser.parse_args()
    lines = args.plan.read_text(encoding="utf-8").splitlines(keepends=True)
    fences, errors = fenced_blocks(lines)
    heredocs, heredoc_errors = heredoc_blocks(lines)
    errors.extend(heredoc_errors)
    fence_counts = collections.Counter(block.language for block in fences)
    heredoc_counts = collections.Counter(block.language for block in heredocs)
    expected = {
        "fences": (len(fences), args.expect_fences),
        "heredocs": (len(heredocs), args.expect_heredocs),
        "bash fences": (fence_counts["bash"], args.expect_bash),
        "python fences": (fence_counts["python"], args.expect_python_fences),
        "PY heredocs": (heredoc_counts["PY"], args.expect_py_heredocs),
        "BASH heredocs": (heredoc_counts["BASH"], args.expect_bash_heredocs),
        "COLLECTOR heredocs": (heredoc_counts["COLLECTOR"], args.expect_collector),
        "EOF data heredocs": (heredoc_counts["EOF"], args.expect_data),
    }
    for label, (measured, declared) in expected.items():
        if measured != declared:
            errors.append(f"{label} census differs: measured {measured}, expected {declared}")
    for block in fences:
        if block.language == "bash":
            failure = bash_syntax(block.body)
            if failure is not None:
                errors.append(f"Bash fence at plan line {block.first}: {failure}")
        elif block.language == "python":
            failure = python_syntax(block.body, block.first + 1)
            if failure is not None:
                errors.append(f"Python fence at plan line {block.first}: {failure}")
    for block in heredocs:
        if block.language == "BASH":
            failure = bash_syntax(block.body)
            if failure is not None:
                errors.append(f"BASH heredoc at plan line {block.first}: {failure}")
        elif block.language in {"PY", "COLLECTOR"}:
            failure = python_syntax(block.body, block.first + 1)
            if failure is not None:
                errors.append(f"{block.language} heredoc at plan line {block.first}: {failure}")
    if errors:
        for error in errors:
            print(f"SYNTAX_RED {error}", file=sys.stderr)
        return 1
    data = heredoc_counts["EOF"]
    print(
        f"SYNTAX_GREEN fences={len(fences)} bash={fence_counts['bash']} "
        f"python_fences={fence_counts['python']} heredocs={len(heredocs)} "
        f"py={heredoc_counts['PY']} collector={heredoc_counts['COLLECTOR']} "
        f"bash_heredocs={heredoc_counts['BASH']} data={data}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run the complete census**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/syntax.py "$P" \
  --expect-fences 93 --expect-heredocs 99 --expect-bash 68 \
  --expect-python-fences 10 --expect-py-heredocs 49 --expect-bash-heredocs 41 \
  --expect-collector 1 --expect-data 8
```

Expected exactly:

```text
SYNTAX_GREEN fences=93 bash=68 python_fences=10 heredocs=99 py=49 collector=1 bash_heredocs=41 data=8
```

- [ ] **Step 4: Prove nested invalid syntax and unclosed heredocs are RED**

Run this self-contained harness:

````bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$P" \
  .superpowers/sdd/tools/syntax.py <<'PY'
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

base = Path(sys.argv[1]).read_text(encoding="utf-8")
checker = Path(sys.argv[2]).resolve()
mutations = {
    "nested-bash": (
        "\n````markdown\n```bash\nif then\n```\n````\n",
        (95, 99, 69, 10, 49, 41, 1, 8),
        "Bash fence at plan line",
    ),
    "nested-python": (
        "\n````markdown\n```python\ndef broken(:\n```\n````\n",
        (95, 99, 68, 11, 49, 41, 1, 8),
        "Python fence at plan line",
    ),
    "unclosed-heredoc": (
        "\n```bash\n/bin/bash <<'PY'\nprint('never closed')\n```\n",
        (94, 99, 69, 10, 49, 41, 1, 8),
        "unclosed heredoc PY",
    ),
}
with tempfile.TemporaryDirectory(prefix="syntax-negative.", dir="/private/tmp") as raw:
    root = Path(raw)
    os.chmod(root, 0o700)
    for name, (suffix, counts, needle) in mutations.items():
        changed = base + suffix
        assert changed != base
        candidate = root / f"{name}.md"
        candidate.write_text(changed, encoding="utf-8")
        fences, heredocs, bash, python_fences, py_heredocs, bash_heredocs, collector, data = counts
        command = [
            sys.executable, "-P", str(checker), str(candidate),
            "--expect-fences", str(fences), "--expect-heredocs", str(heredocs),
            "--expect-bash", str(bash), "--expect-python-fences", str(python_fences),
            "--expect-py-heredocs", str(py_heredocs),
            "--expect-bash-heredocs", str(bash_heredocs),
            "--expect-collector", str(collector), "--expect-data", str(data),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode != 0, (name, result.stdout, result.stderr)
        assert "SYNTAX_RED" in result.stderr, (name, result.stderr)
        assert needle in result.stderr, (name, needle, result.stderr)
        print(f"SYNTAX_NEGATIVE_GREEN {name} rc={result.returncode}")

    renamed = base.replace("8<<'COLLECTOR'", "8<<'DATA'", 1).replace("\nCOLLECTOR\n", "\nDATA\n", 1)
    assert renamed != base and renamed.count("8<<'DATA'") == 1
    candidate = root / "collector-renamed.md"
    candidate.write_text(renamed, encoding="utf-8")
    common = [
        sys.executable, "-P", str(checker), str(candidate),
        "--expect-fences", "93", "--expect-heredocs", "99", "--expect-bash", "68",
        "--expect-python-fences", "10", "--expect-py-heredocs", "49",
        "--expect-bash-heredocs", "41", "--expect-collector", "1", "--expect-data", "8",
    ]
    result = subprocess.run(
        common, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode != 0 and "COLLECTOR heredocs census differs" in result.stderr
    print(f"SYNTAX_NEGATIVE_GREEN collector-renamed rc={result.returncode}")

    command = "8<<'COLLECTOR'"
    assert base.count(command) == 1
    command_at = base.index(command)
    collector_first = base.index("\nPY\n", command_at) + len("\nPY\n")
    collector_last = base.index("\nCOLLECTOR\n", collector_first)
    collector_body = base[collector_first:collector_last]
    future = "from __future__ import annotations\n"
    assert collector_body.count(future) == 1
    broken_body = collector_body.replace(future, "def broken(:\n", 1)
    broken = base[:collector_first] + broken_body + base[collector_last:]
    assert broken != base
    candidate = root / "collector-invalid.md"
    candidate.write_text(broken, encoding="utf-8")
    common[3] = str(candidate)
    result = subprocess.run(
        common, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode != 0 and "COLLECTOR heredoc at plan line" in result.stderr
    print(f"SYNTAX_NEGATIVE_GREEN collector-invalid rc={result.returncode}")

    terminator = base.index("\nPY\n", command_at)
    missing = base[:terminator] + "\n" + base[terminator + len("\nPY\n"):]
    assert missing != base
    candidate = root / "collector-preceding-py-unclosed.md"
    candidate.write_text(missing, encoding="utf-8")
    common[3] = str(candidate)
    result = subprocess.run(
        common, capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode != 0
    assert "COLLECTOR at plan line" in result.stderr
    assert "has no preceding PY terminator" in result.stderr
    print(f"SYNTAX_NEGATIVE_GREEN collector-preceding-py-unclosed rc={result.returncode}")
PY
````

Expected: six `SYNTAX_NEGATIVE_GREEN …` lines. Count mismatches are acceptable additional RED reasons in this negative harness; each injected syntax/closure error must also appear in stderr.

- [ ] **Step 5: Record the ignored-tool checkpoint**

Append one line to `.superpowers/sdd/progress.md` containing the new `syntax.py` SHA-256, the exact GREEN line, the six RED return codes, and `not committed: pre-certification protocol forbids commits`.

---

### Task 2: Make probe acceptance exact and failure-propagating

**Files:**
- Modify: `.superpowers/sdd/tools/probes.sh` (whole-file replacement)
- Test: `/private/tmp` candidates created by the verification commands below

**Interfaces:**
- Consumes: a candidate Plan containing B1, B2I, B2, C0, and C payloads.
- Produces: exact checks for five filesystem states and ten invocations; exit 0 only when all declared transitions match.

- [ ] **Step 1: Preserve the existing false-success evidence**

The existing script ends with `rm -rf "$ROOT"` and never aggregates mode failures. Record that its current overall rc is 0 even though it treats `record-red` and `validate-red` as raw failing modes against the wrong payload state.

- [ ] **Step 2: Replace `probes.sh` with this stateful runner**

```bash
#!/bin/bash
set -euo pipefail
CAND="${1:?candidate Plan required}"
case "$CAND" in /*) ;; *) CAND="$PWD/$CAND" ;; esac
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
cd "$ROOT"
PYTHONDONTWRITEBYTECODE=1 "$UV" run --quiet --no-project --python 3.13 python -P - "$CAND" <<'PY'
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Case:
    label: str
    probe: str
    mode: str
    payload: str | None
    umask: int
    returncode: int
    stdout: str
    stderr_marker: str | None = None


text = Path(sys.argv[1]).read_text(encoding="utf-8")
ticks = chr(96) * 3
heads = {match.group(1): match.start() for match in re.finditer(r"(?m)^## Appendix ([0-9A-Z]+)\b", text)}
payloads: dict[str, str] = {}
for key in ("B1", "B2I", "B2", "C0", "C"):
    opener, closer = ticks + "python\n", "\n" + ticks + "\n"
    start = text.index(opener, heads[key]) + len(opener)
    payloads[key] = text[start:text.index(closer, start) + 1]

red_marker = "READER_BOUND_MISSING: oversize live catalog accepted with returncode 0"
cases = [
    Case("c0-absent", "C0", "record-red", None, 0o022, 0, "SCRIPT_ABSENT\n"),
    Case("c0-b1-record", "C0", "record-green", "B1", 0o022, 0, "RECORD_GREEN\n"),
    Case("c0-b1-validate", "C0", "validate-red", "B1", 0o022, 0, "VALIDATOR_ABSENT\n"),
    Case("c0-b2i-full", "C0", "all-green", "B2I", 0o022, 0, "ALL_GREEN\n"),
    Case("c-b2i-reader-red", "C", "reader-green", "B2I", 0o022, 1, "", red_marker),
    Case("c-b2-reader", "C", "reader-green", "B2", 0o022, 0, "READER_GREEN\n"),
]
for mask in (0o000, 0o002, 0o022, 0o077):
    cases.append(Case(f"c-b2-full-{mask:03o}", "C", "all-green", "B2", mask, 0, "ALL_GREEN\n"))

with tempfile.TemporaryDirectory(prefix="plan-probes.", dir="/private/tmp") as raw:
    root = Path(raw)
    os.chmod(root, 0o700)
    for key, payload in payloads.items():
        (root / f"{key}.py").write_text(payload, encoding="utf-8")
    for case in cases:
        script = root / "script.py"
        script.unlink(missing_ok=True)
        if case.payload is not None:
            script.write_text(payloads[case.payload], encoding="utf-8")
            os.chmod(script, 0o644)
        result = subprocess.run(
            [sys.executable, "-P", str(root / f"{case.probe}.py"), case.mode, "--script", str(script)],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            preexec_fn=lambda mask=case.umask: os.umask(mask),
        )
        failures: list[str] = []
        if result.returncode != case.returncode:
            failures.append(f"rc={result.returncode}, expected {case.returncode}")
        if result.stdout != case.stdout:
            failures.append(f"stdout={result.stdout!r}, expected {case.stdout!r}")
        if case.stderr_marker is None:
            if result.stderr:
                failures.append(f"unexpected stderr={result.stderr!r}")
        elif result.stderr.count(case.stderr_marker) != 1:
            failures.append(f"stderr marker count={result.stderr.count(case.stderr_marker)}, expected 1")
        if failures:
            raise SystemExit(f"PROBE_RED {case.label}: {'; '.join(failures)}")
        print(f"PROBE_CASE_GREEN {case.label} rc={result.returncode} umask={case.umask:03o}")
print("PLAN_PROBES_GREEN cases=10 states=5 umasks=4 expected_red=1")
PY
```

- [ ] **Step 3: Run the real candidate states**

Run: `PYTHONDONTWRITEBYTECODE=1 .superpowers/sdd/tools/probes.sh "$P"`

Expected: ten `PROBE_CASE_GREEN` lines followed by exactly `PLAN_PROBES_GREEN cases=10 states=5 umasks=4 expected_red=1`, exit 0.

- [ ] **Step 4: Prove output drift and missing RED discrimination fail the runner**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$P" \
  .superpowers/sdd/tools/probes.sh <<'PY'
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

base = Path(sys.argv[1]).read_text(encoding="utf-8")
runner = Path(sys.argv[2]).resolve()
changes = {
    "c0-output": ("C0", 'print("SCRIPT_ABSENT")', 'print("SCRIPT_ABSENT_WRONG")'),
    "c-red-marker": (
        "C",
        "READER_BOUND_MISSING: oversize live catalog accepted with returncode ",
        "READER_BOUND_WRONG: oversize live catalog accepted with returncode ",
    ),
}
heads = {
    match.group(1): match.start()
    for match in __import__("re").finditer(r"(?m)^## Appendix ([0-9A-Z]+)\b", base)
}
ticks = chr(96) * 3
with tempfile.TemporaryDirectory(prefix="probe-negative.", dir="/private/tmp") as raw:
    root = Path(raw)
    os.chmod(root, 0o700)
    for name, (appendix, old, new) in changes.items():
        opener, closer = ticks + "python\n", "\n" + ticks + "\n"
        start = base.index(opener, heads[appendix]) + len(opener)
        end = base.index(closer, start) + 1
        payload = base[start:end]
        assert payload.count(old) == 1, (name, payload.count(old))
        changed = base[:start] + payload.replace(old, new) + base[end:]
        assert changed != base
        candidate = root / f"{name}.md"
        candidate.write_text(changed, encoding="utf-8")
        result = subprocess.run(
            [str(runner), str(candidate)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode != 0, (name, result.stdout, result.stderr)
        assert "PROBE_RED" in result.stdout + result.stderr, (name, result.stdout, result.stderr)
        print(f"PROBE_NEGATIVE_GREEN {name} rc={result.returncode}")
PY
```

Expected: two `PROBE_NEGATIVE_GREEN …` lines.

- [ ] **Step 5: Record the ignored-tool checkpoint**

Append the `probes.sh` SHA-256, baseline summary, two adversarial rc values, and the pre-certification no-commit reason to `.superpowers/sdd/progress.md`.

---

### Task 3: Make mutation tests impossible to skip or misclassify

**Files:**
- Modify: `.superpowers/sdd/tools/repair.py`
- Modify: `.superpowers/sdd/tools/mutate.py`
- Modify: `.superpowers/sdd/tools/mutate2.py`
- Modify: `.superpowers/sdd/tools/mutate3.py`
- Test: throwaway current-Plan copy below a newly created mode-0700 `/private/tmp` root

**Interfaces:**
- `repair.repair_text(text: str, *, body: bool, families: bool) -> str` repairs marked-family declarations first when requested, then gate self-hash, then the masked whole-Plan digest.
- `mutate.run_suite(suite: str, candidate: Path) -> int` enforces exact outcome matrices and exits nonzero on an absent target, non-unique target, no-op mutation, repair failure that was not expected RED, or unexpected gate color.
- `mutate2.py` calls suite `families`; `mutate3.py` calls suite `delimiters`.

- [ ] **Step 1: Capture the current false-GREEN tool behavior**

Run the three existing scripts from a private copy of the tools with the Plan copied to `cand.md`. Record that `mutate.py` prints `SKIP` for `m5`, `m6`, and `m9` yet exits 0, and that all scripts print matrices without asserting them.

- [ ] **Step 2: Refactor `repair.py` with an opt-in family repair**

Implement these exact rules:

```python
BLOCK_BEGIN = re.compile(r"(?m)^# ([A-Z][A-Z0-9_]*)_BEGIN$")
BLOCK_END = re.compile(r"(?m)^# ([A-Z][A-Z0-9_]*)_END$")
MARKED_ENTRY = re.compile(
    r'(?m)^    "([A-Z][A-Z0-9_]*)": \(([0-9]+), "([0-9a-f]{64})"\),$'
)
```

`repair_text` must use the same body definition as the Plan gate: split with `text.splitlines()`, pair each `# NAME_BEGIN` with its matching `# NAME_END`, and hash `chr(10).join(lines[first + 1:last])`. For each declared family, assert marker balance, exact declared copy count, and byte-identical copies. With `families=True`, replace the old digest only when that old digest occurs exactly once. Then recompute the gate self-hash and masked `PLAN_BODY_DIGEST` in that order. With `families=False`, preserve current `iterate.sh` behavior. The CLI remains `repair.py PLAN [--families]`.

Replace the file with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

TICKS = chr(96) * 3
GATE_OPEN = "<!-- PLAN_IDENTITY" + "_GATE_BEGIN -->\n" + TICKS + "bash\n"
GATE_CLOSE = "\n" + TICKS + "\n<!-- PLAN_IDENTITY" + "_GATE_END -->"
BODY_DECL = re.compile(r"(?m)^(PLAN_BODY_DIGEST )([0-9a-f]{64})$")
MARKED_ENTRY = re.compile(
    r'(?m)^    "([A-Z][A-Z0-9_]*)": \(([0-9]+), "([0-9a-f]{64})"\),$'
)


def measured_families(text: str) -> dict[str, tuple[int, str]]:
    table_start = text.index("MARKED_BLOCKS = {\n")
    table_end = text.index("\n}\n", table_start) + 2
    table = text[table_start:table_end]
    declared = {
        name: (int(count), digest)
        for name, count, digest in MARKED_ENTRY.findall(table)
    }
    if not declared:
        raise RuntimeError("MARKED_BLOCKS table is empty")
    lines = text.splitlines()
    open_blocks: dict[str, list[int]] = {}
    bodies: dict[str, list[str]] = {}
    begin = re.compile(r"^# ([A-Z][A-Z0-9_]*)_BEGIN$")
    end = re.compile(r"^# ([A-Z][A-Z0-9_]*)_END$")
    for number, line in enumerate(lines):
        opened = begin.match(line)
        if opened is not None:
            open_blocks.setdefault(opened.group(1), []).append(number)
            continue
        closed = end.match(line)
        if closed is None:
            continue
        starts = open_blocks.get(closed.group(1))
        if not starts:
            raise RuntimeError(f"unmatched family close: {closed.group(1)}")
        first = starts.pop()
        bodies.setdefault(closed.group(1), []).append(chr(10).join(lines[first + 1:number]))
    dangling = sorted(name for name, starts in open_blocks.items() if starts)
    if dangling:
        raise RuntimeError(f"unclosed family markers: {dangling}")
    if set(bodies) != set(declared):
        raise RuntimeError(
            f"family names differ: measured={sorted(bodies)} declared={sorted(declared)}"
        )
    measured: dict[str, tuple[int, str]] = {}
    for name, copies in bodies.items():
        digests = {hashlib.sha256(body.encode("utf-8")).hexdigest() for body in copies}
        if len(digests) != 1:
            raise RuntimeError(f"family copies differ: {name}")
        count, digest = len(copies), digests.pop()
        if count != declared[name][0]:
            raise RuntimeError(
                f"family copy count differs: {name}: measured={count} declared={declared[name][0]}"
            )
        measured[name] = (count, digest)
    return measured


def repair_text(text: str, *, body: bool, families: bool) -> str:
    if families:
        measured = measured_families(text)
        table_start = text.index("MARKED_BLOCKS = {\n")
        table_end = text.index("\n}\n", table_start) + 2
        table = text[table_start:table_end]

        def replace_entry(found: re.Match[str]) -> str:
            name, count, old = found.groups()
            new = measured[name][1]
            if old != new and text.count(old) != 1:
                raise RuntimeError(f"family digest occurrence is not unique: {name}")
            return f'    "{name}": ({count}, "{new}"),'

        text = text[:table_start] + MARKED_ENTRY.sub(replace_entry, table) + text[table_end:]
    if text.count(GATE_OPEN) != 1 or text.count(GATE_CLOSE) != 1:
        raise RuntimeError("gate markers are not unique")
    start = text.index(GATE_OPEN) + len(GATE_OPEN)
    gate = text[start:text.index(GATE_CLOSE, start) + 1]
    gate_sha = hashlib.sha256(gate.encode("utf-8")).hexdigest()
    found = re.search(r"test \"\$GATE_SHA256\" = '([0-9a-f]{64})'", text)
    if found is None:
        raise RuntimeError("Step 5 gate hash declaration is absent")
    old_gate = found.group(1)
    if old_gate != gate_sha:
        if text.count(old_gate) != 2:
            raise RuntimeError(f"gate hash occurs {text.count(old_gate)} times, expected 2")
        text = text.replace(old_gate, gate_sha)
    if body:
        declarations = list(BODY_DECL.finditer(text))
        if len(declarations) != 1:
            raise RuntimeError(f"PLAN_BODY_DIGEST count={len(declarations)}, expected 1")
        masked = BODY_DECL.sub(lambda item: item.group(1) + "0" * 64, text)
        digest = hashlib.sha256(masked.encode("utf-8")).hexdigest()
        text = BODY_DECL.sub(lambda item: item.group(1) + digest, text)
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--families", action="store_true")
    args = parser.parse_args()
    original = args.plan.read_text(encoding="utf-8")
    repaired = repair_text(original, body=True, families=args.families)
    args.plan.write_text(repaired, encoding="utf-8")
    print(
        f"triple: {len(repaired.splitlines())} lines / {len(repaired.encode('utf-8'))} bytes / "
        f"{hashlib.sha256(repaired.encode('utf-8')).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Replace line-number mutations with unique semantic anchors**

Use only these mutation helpers:

```python
def replace_unique(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"mutation target count={count}, expected 1: {old[:80]}")
    changed = text.replace(old, new)
    if changed == text:
        raise RuntimeError("mutation changed nothing")
    return changed


def replace_in_family(text: str, name: str, old: str, new: str) -> str:
    begin = f"# {name}_BEGIN\n"
    end = f"# {name}_END"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError(f"family markers are not unique: {name}")
    first = text.index(begin) + len(begin)
    last = text.index(end, first)
    body = text[first:last]
    if body.count(old) != 1:
        raise RuntimeError(f"family target count={body.count(old)}, expected 1: {name}")
    changed = text[:first] + body.replace(old, new) + text[last:]
    if changed == text:
        raise RuntimeError("mutation changed nothing")
    return changed
```

Do not retain any positional line range. Each non-control case must execute `assert mutated != base` before repair or gate execution.

- [ ] **Step 4: Encode the exact core matrix in `mutate.py`**

The core suite runs `stale` (no repair) and `body` (`repair_text(body=True, families=False)`) and enforces:

| case | unique mutation | stale | body |
|---|---|---:|---:|
| free signature | `write_owned` default `0o600` → `0o666` | RED | RED |
| CamelCase definition | insert `def Sneaky` immediately before the unique `write_owned` signature | RED | RED |
| async definition | insert `async def sneaky` at the same unique anchor | RED | RED |
| exempt reader body | the unique `read_limited` open loses `\| os.O_NOFOLLOW` | RED | RED |
| declared family table | insert a `NONEXISTENT` entry after the unique `MARKED_BLOCKS = {` | RED | RED |
| shell residue | unique `2>"$FROZEN_STDERR"` → `2>>"$FROZEN_STDERR"` | RED | GREEN |
| control | unchanged bytes | GREEN | GREEN |

The two GREEN-in-body results are deliberate controls for the Plan's disclosed whole-body-digest residue class; any other GREEN is failure.

- [ ] **Step 5: Encode the exact marked-family matrix in `mutate2.py`**

The family suite runs `stale`, `body`, and `families` (`repair_text(body=True, families=True)`) and enforces:

| case | family mutation | stale | body | families |
|---|---|---:|---:|---:|
| ack leaf token | first unique `\| os.O_NOFOLLOW` removed | RED | RED | RED |
| ack empty floor | unique `or before.st_size <= 0` removed | RED | RED | RED |
| ack helper cap | unique `before.st_size > limit` → `before.st_size > limit * 4096` | RED | RED | RED |
| ack literal cap | unique `final_info.st_size > 64_000_000` → `… > 64_000_000_000` | RED | RED | GREEN |
| snapshot empty floor | unique `or before.st_size <= 0` removed | RED | RED | RED |
| snapshot literal cap | unique `before.st_size > 64_000_000` → `… > 64_000_000_000` | RED | RED | GREEN |
| control | unchanged bytes | GREEN | GREEN | GREEN |

The two GREEN `families` cells are mandatory evidence for the accurately disclosed family-digest-only cap escapes; treating them as RED is also a test failure.

- [ ] **Step 6: Encode the exact delimiter/digest matrix in `mutate3.py`**

Run the same three modes and enforce RED/RED/RED for: a decoy `# FAILURE_ACK_APPEND_READER_BEGIN` inserted inside that family; a comment-separated split at the unique line containing only the first R1 journal digest; and a comment-separated split at the unique `MANIFEST_SHA256 = "8292…"` line. The unchanged control is GREEN/GREEN/GREEN. Preserve the syntactically valid split spellings from the current `mutate3.py`.

- [ ] **Step 7: Make result enforcement executable**

For every case and mode, write the repaired mutation below a `TemporaryDirectory(prefix="plan-mutation.", dir="/private/tmp")`, call `rungate.sh`, classify solely from return code, and compare with the table. Print one row per case and finish with exactly one of:

```text
MUTATION_GREEN suite=core cases=7
MUTATION_GREEN suite=families cases=7
MUTATION_GREEN suite=delimiters cases=4
```

Any target error or matrix mismatch must be printed as `MUTATION_RED …` on stderr and return 1. A preparation/repair exception is a tool failure, not evidence that the gate rejected a mutation; the sole exception is `ack-decoy` in `families` mode, whose duplicate delimiter deliberately makes family digest regeneration impossible and is declared in `allowed_prepare_red`. `SKIP`, `NOOP`, and a zero exit after either word are forbidden.

Use this complete `mutate.py` implementation; `mutate2.py` and `mutate3.py` are the wrappers shown after it:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from repair import repair_text  # noqa: E402

Color = str
Mutation = Callable[[str], str]


@dataclass(frozen=True)
class Case:
    name: str
    apply: Mutation
    expected: dict[str, Color]
    allowed_prepare_red: frozenset[str] = frozenset()


def replace_unique(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"mutation target count={count}, expected 1: {old[:80]}")
    changed = text.replace(old, new)
    if changed == text:
        raise RuntimeError("mutation changed nothing")
    return changed


def replace_in_family(text: str, name: str, old: str, new: str) -> str:
    begin = f"# {name}_BEGIN\n"
    end = f"# {name}_END"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError(f"family markers are not unique: {name}")
    first = text.index(begin) + len(begin)
    last = text.index(end, first)
    body = text[first:last]
    if body.count(old) != 1:
        raise RuntimeError(f"family target count={body.count(old)}, expected 1: {name}")
    changed = text[:first] + body.replace(old, new) + text[last:]
    if changed == text:
        raise RuntimeError("mutation changed nothing")
    return changed


def core_cases() -> list[Case]:
    signature = "def write_owned(path: Path, payload: bytes, mode: int = 0o600) -> None:"
    matrix = {"stale": "RED", "body": "RED"}
    return [
        Case("free-signature", lambda text: replace_unique(text, signature, signature.replace("0o600", "0o666")), matrix),
        Case("camel-definition", lambda text: replace_unique(text, signature, "def Sneaky(path):\n    return path\n\n\n" + signature), matrix),
        Case("async-definition", lambda text: replace_unique(text, signature, "async def sneaky(path):\n    return path\n\n\n" + signature), matrix),
        Case(
            "exempt-reader",
            lambda text: replace_unique(
                text,
                "descriptor = os.open(safe_parent(path), os.O_RDONLY | os.O_NOFOLLOW)",
                "descriptor = os.open(safe_parent(path), os.O_RDONLY)",
            ),
            matrix,
        ),
        Case(
            "family-table",
            lambda text: replace_unique(
                text,
                "MARKED_BLOCKS = {\n",
                'MARKED_BLOCKS = {\n    "NONEXISTENT": (1, "' + "0" * 64 + '"),\n',
            ),
            matrix,
        ),
        Case(
            "shell-residue",
            lambda text: replace_unique(text, '2>"$FROZEN_STDERR"', '2>>"$FROZEN_STDERR"'),
            {"stale": "RED", "body": "GREEN"},
        ),
        Case("control", lambda text: text, {"stale": "GREEN", "body": "GREEN"}),
    ]


def family_cases() -> list[Case]:
    red = {"stale": "RED", "body": "RED", "families": "RED"}
    disclosed = {"stale": "RED", "body": "RED", "families": "GREEN"}
    green = {"stale": "GREEN", "body": "GREEN", "families": "GREEN"}
    ack = "FAILURE_ACK_APPEND_READER"
    snap = "TASK_REPORT_SNAPSHOT_READER"
    return [
        Case(
            "ack-leaf-token",
            lambda text: replace_in_family(
                text, ack,
                "leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd",
                "leaf, os.O_RDONLY, dir_fd=parent_fd",
            ),
            red,
        ),
        Case(
            "ack-empty-floor",
            lambda text: replace_in_family(text, ack, "or before.st_size <= 0", "or before.st_size < 0"),
            red,
        ),
        Case(
            "ack-helper-cap",
            lambda text: replace_in_family(text, ack, "before.st_size > limit", "before.st_size > limit * 4096"),
            red,
        ),
        Case(
            "ack-literal-cap",
            lambda text: replace_in_family(
                text, ack,
                "final_info.st_size > 64_000_000",
                "final_info.st_size > 64_000_000_000",
            ),
            disclosed,
        ),
        Case(
            "snapshot-empty-floor",
            lambda text: replace_in_family(text, snap, "or before.st_size <= 0", "or before.st_size < 0"),
            red,
        ),
        Case(
            "snapshot-literal-cap",
            lambda text: replace_in_family(
                text, snap,
                "before.st_size > 64_000_000",
                "before.st_size > 64_000_000_000",
            ),
            disclosed,
        ),
        Case("control", lambda text: text, green),
    ]


def delimiter_cases() -> list[Case]:
    red = {"stale": "RED", "body": "RED", "families": "RED"}
    green = {"stale": "GREEN", "body": "GREEN", "families": "GREEN"}
    ack_begin = "# FAILURE_ACK_APPEND_READER_BEGIN\n"
    journal = '        "b6f2568116080d4936a3d753a419c771c00233a67111ed626cc2bbe169c79f0e",'
    journal_split = (
        '        ("dead568116080d4936a3d753a419c771"  # census filler\n'
        '         "c00233a67111ed626cc2bbe169c79f0e"),  # '
        'b6f2568116080d4936a3d753a419c771c00233a67111ed626cc2bbe169c79f0e'
    )
    manifest = '\nMANIFEST_SHA256 = "8292ac78073804687faab381181881ac7f522da1edea2dffe625626c1482c535"'
    manifest_split = (
        '\nMANIFEST_SHA256 = ("dead" "ac78073804687faab381181881ac7f5"  # census filler\n'
        '                   "22da1edea2dffe625626c1482c535")  # '
        '8292ac78073804687faab381181881ac7f522da1edea2dffe625626c1482c535'
    )
    return [
        Case(
            "ack-decoy",
            lambda text: replace_unique(text, ack_begin, ack_begin + ack_begin),
            red,
            frozenset({"families"}),
        ),
        Case("journal-comment-split", lambda text: replace_unique(text, journal, journal_split), red),
        Case("manifest-comment-split", lambda text: replace_unique(text, manifest, manifest_split), red),
        Case("control", lambda text: text, green),
    ]


def prepared(text: str, mode: str) -> str:
    if mode == "stale":
        return text
    if mode == "body":
        return repair_text(text, body=True, families=False)
    if mode == "families":
        return repair_text(text, body=True, families=True)
    raise RuntimeError(f"unknown mode: {mode}")


def run_suite(suite: str, candidate: Path) -> int:
    factories = {"core": core_cases, "families": family_cases, "delimiters": delimiter_cases}
    cases = factories[suite]()
    base = candidate.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="plan-mutation.", dir="/private/tmp") as raw:
        root = Path(raw)
        os.chmod(root, 0o700)
        for case in cases:
            try:
                mutated = case.apply(base)
                if case.name != "control" and mutated == base:
                    raise RuntimeError("mutation changed nothing")
            except Exception as error:
                print(f"MUTATION_RED suite={suite} case={case.name} apply={error}", file=sys.stderr)
                return 1
            for mode, expected in case.expected.items():
                try:
                    run_text = prepared(mutated, mode)
                except Exception as error:
                    if mode not in case.allowed_prepare_red:
                        print(
                            f"MUTATION_RED suite={suite} case={case.name} mode={mode} "
                            f"preparation_failed={error}",
                            file=sys.stderr,
                        )
                        return 1
                    measured = "RED"
                    message = [f"explicitly allowed non-regenerable mutation: {error}"]
                else:
                    try:
                        run = root / f"{case.name}-{mode}.md"
                        run.write_text(run_text, encoding="utf-8")
                        result = subprocess.run(
                            [str(HERE / "rungate.sh"), str(run)],
                            capture_output=True,
                            text=True,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                        )
                    except Exception as error:
                        print(
                            f"MUTATION_RED suite={suite} case={case.name} mode={mode} "
                            f"execution_failed={error}",
                            file=sys.stderr,
                        )
                        return 1
                    measured = "GREEN" if result.returncode == 0 else "RED"
                    message = (result.stdout + result.stderr).strip().splitlines()[-1:]
                if measured != expected:
                    print(
                        f"MUTATION_RED suite={suite} case={case.name} mode={mode} "
                        f"measured={measured} expected={expected} message={message}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"MUTATION_CASE_GREEN {suite} {case.name} {mode}={measured}")
    print(f"MUTATION_GREEN suite={suite} cases={len(cases)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", nargs="?", type=Path, default=HERE / "cand.md")
    parser.add_argument("--suite", choices=("core", "families", "delimiters"), default="core")
    args = parser.parse_args()
    return run_suite(args.suite, args.candidate)


if __name__ == "__main__":
    raise SystemExit(main())
```

`mutate2.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mutate import run_suite  # noqa: E402
candidate = Path(sys.argv[1]) if len(sys.argv) == 2 else HERE / "cand.md"
raise SystemExit(run_suite("families", candidate))
```

`mutate3.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mutate import run_suite  # noqa: E402
candidate = Path(sys.argv[1]) if len(sys.argv) == 2 else HERE / "cand.md"
raise SystemExit(run_suite("delimiters", candidate))
```

- [ ] **Step 8: Verify all suites and the anti-no-op guard**

Run:

```bash
/bin/bash -euo pipefail <<'BASH'
P=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
ROOT="$(mktemp -d /private/tmp/mutation-baseline.XXXXXX)"
chmod 700 "$ROOT"
cleanup() {
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$ROOT" <<'PY'
import shutil
import sys
from pathlib import Path
root = Path(sys.argv[1])
assert root.parent == Path("/private/tmp") and root.name.startswith("mutation-baseline.")
shutil.rmtree(root)
PY
}
trap cleanup EXIT
CAND="$ROOT/cand.md"
cp "$P" "$CAND"
chmod 600 "$CAND"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/mutate.py "$CAND"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/mutate2.py "$CAND"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/mutate3.py "$CAND"
trap - EXIT
cleanup
BASH
```

Expected: the three exact `MUTATION_GREEN` summaries and rc 0. Then run this anti-no-op harness:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$P" \
  .superpowers/sdd/tools/mutate.py <<'PY'
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
from pathlib import Path

base = Path(sys.argv[1]).read_text(encoding="utf-8")
runner = Path(sys.argv[2]).resolve()
anchor = "def write_owned(path: Path, payload: bytes, mode: int = 0o600) -> None:"
assert base.count(anchor) == 1
changed = base.replace(anchor, anchor.replace("write_owned", "write_owned_missing"))
assert changed != base
with tempfile.TemporaryDirectory(prefix="mutation-noop.", dir="/private/tmp") as raw:
    root = Path(raw)
    os.chmod(root, 0o700)
    candidate = root / "candidate.md"
    candidate.write_text(changed, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-P", str(runner), str(candidate)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "mutation target count=0, expected 1" in result.stderr, result.stderr
    print("MUTATION_NOOP_GUARD_GREEN rc=1")
PY
```

Finally prove that the one allowed preparation exception cannot swallow a later file-write failure:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$P" \
  .superpowers/sdd/tools <<'PY'
from __future__ import annotations
import contextlib
import io
import sys
from pathlib import Path

candidate = Path(sys.argv[1])
tools = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(tools))
import mutate

original_prepared = mutate.prepared
original_write_text = Path.write_text

def pass_allowed_preparation(text: str, mode: str) -> str:
    if mode == "families" and text.count("# FAILURE_ACK_APPEND_READER_BEGIN\n") == 2:
        return original_prepared(text, "body")
    return original_prepared(text, mode)

def fail_allowed_case(path: Path, *args, **kwargs):
    if path.name == "ack-decoy-families.md":
        raise OSError("injected write failure")
    return original_write_text(path, *args, **kwargs)

mutate.prepared = pass_allowed_preparation
Path.write_text = fail_allowed_case
stderr = io.StringIO()
with contextlib.redirect_stderr(stderr):
    result = mutate.run_suite("delimiters", candidate)
diagnostic = stderr.getvalue()
assert result == 1, (result, diagnostic)
assert "execution_failed=injected write failure" in diagnostic, diagnostic
assert "explicitly allowed non-regenerable mutation" not in diagnostic, diagnostic
print("MUTATION_EXECUTION_FAILURE_GREEN rc=1")
PY
```

- [ ] **Step 9: Record the ignored-tool checkpoint**

Append all four tool SHA-256 values, the three suite summaries, the anti-no-op rc, the injected execution-failure rc, the two disclosed family-cap GREEN controls, and the no-commit reason to `.superpowers/sdd/progress.md`.

---

### Task 4: Apply the seven R34 corrections to an isolated candidate

**Files:**
- Create/replace: `.superpowers/sdd/tools/cand.md`
- Read only: `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`
- Test: hardened tools plus the extraction harness in Task 5

**Interfaces:**
- Consumes: starting Plan identity `26111 / 1072629 / d36cf53c…` and the seven deduplicated R33 findings.
- Produces: one candidate with C-1, I-1, and M-1 through M-5 corrected; no protected payload changes.

- [ ] **Step 1: Refresh the candidate from the tracked Plan**

Run:

```bash
cp docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md \
  .superpowers/sdd/tools/cand.md
chmod 600 .superpowers/sdd/tools/cand.md
```

Expected candidate SHA-256 before patch: `d36cf53c4abf6f8681397da506e2400a7accaf9adf88e8f08f182f8159f45ffb`.

- [ ] **Step 2: Apply one exact-string patch pass with uniqueness assertions**

The patch program must assert a count of exactly 1 in the intended scope for every replacement. The Task 7 block is shared byte-for-byte by Tasks 4 and 5, so scope that replacement to the unique Task 7 fence; all other replacements are unique Plan-wide.

1. In the Task 7 extraction fence only, replace the eight-line Task 4/5 premise and rejecting E/F guard with:

```python
# A Task 7 brief carries `required` = ("A", "C", "D", "F"), so Appendix F follows the D
# section and Appendix E is never routed here. The D section therefore ends at the next
# Appendix heading, not at the end of the brief, and the two fence counts below hold the
# slice that remains.
section = text.split(heading, 1)[1]
if "\n## Appendix E" in section or section.count("\n## Appendix F") != 1:
    raise RuntimeError("a Task 7 brief carries Appendix F after Appendix D and no E")
section = section.split("\n## Appendix F", 1)[0]
```

2. Replace the dangling line `while recording audit evidence, then clean \`0\`. \`TASK_N\` and \`TASK_REPORT\` bind lanes.` with `` `TASK_N` and `TASK_REPORT` bind lanes. ``.
3. Replace `Task 5 and Task 7` plus the continuation `clean lane are clean;` with `Task 5 and Task 7 are clean;`.
4. Replace `one full extra copy of the identity-binding reader algorithm` with `two full copies of the identity-binding reader algorithm`.
5. Replace `Tasks 4–5 pass` with `Tasks 4, 5 and 7 pass` at the `EXPECTED_MAIN_ANCHOR` paragraph.
6. Rewrite the module-reader prose and code comment so they state all three exact facts: only `FAILURE_ACK_APPEND_READER` shares `before.st_size > limit`; that helper cap is already checked by the free-reader loop; the snapshot `64_000_000` cap and ack `final_info.st_size > 64_000_000` cap are the two family-digest-only escapes.

For item 6, use this exact gate comment:

```python
# Both module-level identity-binding programs are held to the READER_TOKENS control set
# and to the empty-file floor -- both spell `or before.st_size <= 0` exactly. Neither is
# held to `READER_CAP` here: `TASK_REPORT_SNAPSHOT_READER` spells its cap
# `before.st_size > 64_000_000` rather than `> limit`, so requiring it reddens the
# unmutated Plan, and the ack program's `> limit` cap already reaches the free-reader
# loop below through `bounded_owned_bytes`. Widening either `64_000_000` cap is caught
# by the family digest above and by nothing here, which is the one control this
# dimension does not carry.
```

Use this prose replacement:

```text
two full copies of the identity-binding reader algorithm already lived there. Both are
additionally held to the reader control tokens and to the empty-file floor. The module-
family loop applies no byte-cap token: only the failure-ack program shares the Appendix
D/E `before.st_size > limit` spelling, and that helper cap is already checked by the
free-reader loop. The snapshot program's `64_000_000` cap and the failure-ack program's
`final_info.st_size > 64_000_000` cap remain family-digest-only. The five
```

Run this exact patch program:

````bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - .superpowers/sdd/tools/cand.md <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
task7_start_anchor = "BRIEF=.superpowers/sdd/modeling-remediation/task-7-brief.md\n"
task7_end_anchor = "\nValidation now consumes\n"
assert text.count(task7_start_anchor) == 1, text.count(task7_start_anchor)
task7_start = text.index(task7_start_anchor)
task7_end = text.index(task7_end_anchor, task7_start)
task7 = text[task7_start:task7_end]
task7_old = '''# Appendix D is the last section a Task 4/5 brief carries -- `required` is
# ("A0", "C0", "D") and Appendix E is never routed here -- so everything after the D
# heading is the D section. The old second `split` named an Appendix E heading that
# occurs zero times in any real brief and therefore never cut anything; the invariant
# it was standing in for is stated here and enforced by the two fence counts below.
section = text.split(heading, 1)[1]
if "\\n## Appendix E" in section or "\\n## Appendix F" in section:
    raise RuntimeError("a section after Appendix D reached this brief")'''
task7_new = '''# A Task 7 brief carries `required` = ("A", "C", "D", "F"), so Appendix F follows the D
# section and Appendix E is never routed here. The D section therefore ends at the next
# Appendix heading, not at the end of the brief, and the two fence counts below hold the
# slice that remains.
section = text.split(heading, 1)[1]
if "\\n## Appendix E" in section or section.count("\\n## Appendix F") != 1:
    raise RuntimeError("a Task 7 brief carries Appendix F after Appendix D and no E")
section = section.split("\\n## Appendix F", 1)[0]'''
assert task7.count(task7_old) == 1, task7.count(task7_old)
changed_task7 = task7.replace(task7_old, task7_new)
assert changed_task7 != task7
text = text[:task7_start] + changed_task7 + text[task7_end:]
print("PATCH_GREEN C1-M2-task7-slice count=1")

patches = [
    (
        "I1-dangling-lane",
        'while recording audit evidence, then clean `0`. `TASK_N` and `TASK_REPORT` bind lanes.',
        '`TASK_N` and `TASK_REPORT` bind lanes.',
    ),
    (
        "M1-clean-lane",
        '''- Task 4 has exactly the active audit modified; Task 5 and Task 7
  clean lane are clean;''',
        '- Task 4 has exactly the active audit modified; Task 5 and Task 7 are clean;',
    ),
    (
        "M3-prose-cap",
        '''  two full copies of the identity-binding reader algorithm already lived there; both are
  additionally held to the reader control tokens and to the empty-file floor, though not
  to the byte-cap spelling, which they do not share. The five''',
        '''  two full copies of the identity-binding reader algorithm already lived there. Both are
  additionally held to the reader control tokens and to the empty-file floor. The module-
  family loop applies no byte-cap token: only the failure-ack program shares the Appendix
  D/E `before.st_size > limit` spelling, and that helper cap is already checked by the
  free-reader loop. The snapshot program's `64_000_000` cap and the failure-ack program's
  `final_info.st_size > 64_000_000` cap remain family-digest-only. The five''',
    ),
    (
        "M3-comment-cap",
        '''# Both module-level identity-binding programs are held to the READER_TOKENS control set
# and to the empty-file floor -- both spell `or before.st_size <= 0` exactly. They are
# not held to `READER_CAP`: these programs bound their reads differently from the
# Appendix D/E readers, so requiring that spelling reddens the unmutated Plan. Widening
# one of their byte caps is therefore caught by the family digest above and by nothing
# in this loop, which is the one control this dimension does not carry.''',
        '''# Both module-level identity-binding programs are held to the READER_TOKENS control set
# and to the empty-file floor -- both spell `or before.st_size <= 0` exactly. Neither is
# held to `READER_CAP` here: `TASK_REPORT_SNAPSHOT_READER` spells its cap
# `before.st_size > 64_000_000` rather than `> limit`, so requiring it reddens the
# unmutated Plan, and the ack program's `> limit` cap already reaches the free-reader
# loop below through `bounded_owned_bytes`. Widening either `64_000_000` cap is caught
# by the family digest above and by nothing here, which is the one control this
# dimension does not carry.''',
    ),
    (
        "M4-copy-count",
        "# walks function bodies -- and one full extra copy of the identity-binding reader algorithm",
        "# walks function bodies -- and two full copies of the identity-binding reader algorithm",
    ),
    (
        "M5-callers",
        '''stops the run. Tasks 4–5 pass
`EXPECTED_MAIN_ANCHOR`''',
        '''stops the run. Tasks 4, 5 and 7 pass
`EXPECTED_MAIN_ANCHOR`''',
    ),
]
for label, old, new in patches:
    count = text.count(old)
    assert count == 1, (label, count)
    changed = text.replace(old, new)
    assert changed != text, label
    text = changed
    print(f"PATCH_GREEN {label} count=1")
path.write_text(text, encoding="utf-8")
PY
````

Expected: seven `PATCH_GREEN … count=1` lines. The unchanged Task 4 and Task 5 copies still contain the old Task 4/5 premise, so the Plan-wide old-block count falls from 3 to 2 rather than to 0.

- [ ] **Step 3: Repair self-referential declarations iteratively**

Run `.superpowers/sdd/tools/iterate.sh` once. With the exact seven replacements above it must produce `26115 lines / 1072907 bytes / bfd25054e853a74ec0b0777c048c790edc7ae0b2b2a2ce2c70da43302e05e3b4`, and `rungate.sh` must return 0 with the exact unchanged banner. If either value differs, stop and audit the replacement counts; do not chase a different gate declaration mechanically.

- [ ] **Step 4: Mechanically sweep every stale phrase class**

Require zero hits for:

```text
while recording audit evidence
clean lane are clean
one full extra copy
Tasks 4–5 pass
these programs bound their reads differently
which they do not share
```

Within the Task 7 fence span, require zero hits for `Task 4/5` and `("A0", "C0", "D")`. Require the new Task 7 guard, `two full copies`, `Tasks 4, 5 and 7 pass`, and both literal `64_000_000` escape descriptions exactly once at their intended sites.

- [ ] **Step 5: Record the candidate identity and no-op exclusions**

Append the final candidate line/byte/SHA triple, all replacement counts (each exactly 1), gate banner, phrase-sweep results, and `tracked Plan not yet touched` to `.superpowers/sdd/progress.md`.

---

### Task 5: Prove the candidate, publish it, and prove the published bytes again

**Files:**
- Read: `.superpowers/sdd/tools/cand.md`
- Modify: `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`
- Read only: all protected files named in Global Constraints

**Interfaces:**
- Consumes: Task 4 candidate and hardened Task 1–3 tools.
- Produces: tracked Plan byte-identical to the accepted candidate, with a recorded post-copy identity.

- [ ] **Step 1: Run the four mandatory local acceptance classes on the candidate**

Run, in order:

```bash
C=.superpowers/sdd/tools/cand.md
PYTHONDONTWRITEBYTECODE=1 .superpowers/sdd/tools/rungate.sh "$C"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/syntax.py "$C" \
  --expect-fences 93 --expect-heredocs 99 --expect-bash 68 \
  --expect-python-fences 10 --expect-py-heredocs 49 --expect-bash-heredocs 41 \
  --expect-collector 1 --expect-data 8
PYTHONDONTWRITEBYTECODE=1 .superpowers/sdd/tools/probes.sh "$C"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/mutate.py "$C"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/mutate2.py "$C"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P .superpowers/sdd/tools/mutate3.py "$C"
```

Expected: gate rc 0 with the exact banner, the exact syntax GREEN line, the exact probe GREEN summary, and all three exact mutation GREEN summaries.

- [ ] **Step 2: Drive the Task 4/5/7 Appendix D extraction shapes**

Use a private Python harness that:

- extracts Appendix D from its heading up to Appendix E;
- appends Appendix F for the Task 7 brief only;
- locates each Task 4/5/7 extraction heredoc by the unique `Task N brief digest differs from controller allocation` anchor;
- writes each brief mode 0600, passes its real SHA/dev/ino to the extracted Python, and runs with `PYTHONDONTWRITEBYTECODE=1`;
- asserts all three return codes are 0;
- asserts the three stdout byte strings are identical;
- asserts the Task 7 pre-slice contains exactly one Appendix F, the post-slice contains exactly two Bash fences, and no Appendix E;
- prints `TASK457_EXTRACTION_GREEN bytes=<measured> sha256=<measured>`.

Any synthetic brief or extracted program must be byte-derived from the candidate; do not paste a second copy of the extraction implementation into the harness.

Run this implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$C" <<'PY'
from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
heads = {match.group(1): match.start() for match in re.finditer(r"(?m)^## Appendix ([0-9A-Z]+)\b", text)}
appendix_d = text[heads["D"]:heads["E"]]
appendix_f = text[heads["F"]:]
programs: dict[int, str] = {}
for task in (4, 5, 7):
    scope_text = f"BRIEF=.superpowers/sdd/modeling-remediation/task-{task}-brief.md\n"
    assert text.count(scope_text) == 1, (task, text.count(scope_text))
    scope = text.index(scope_text)
    anchor_text = f'raise RuntimeError("Task {task} brief digest differs from controller allocation")'
    anchor = text.index(anchor_text, scope)
    opener = text.rfind("<<'PY'", scope, anchor)
    assert opener >= scope, task
    start = text.index("\n", opener) + 1
    end = text.index("\nPY\n", anchor)
    program = text[start:end] + "\n"
    assert anchor_text in program, task
    programs[task] = program

outputs: dict[int, bytes] = {}
with tempfile.TemporaryDirectory(prefix="task457-extract.", dir="/private/tmp") as raw:
    root = Path(raw)
    os.chmod(root, 0o700)
    for task in (4, 5, 7):
        brief_text = appendix_d if task in (4, 5) else appendix_d + appendix_f
        section = brief_text.split("## Appendix D: Exact no-write catalog and journal integration\n", 1)[1]
        if task == 7:
            assert "\n## Appendix E" not in section
            assert section.count("\n## Appendix F") == 1
            section = section.split("\n## Appendix F", 1)[0]
        assert section.count("```bash\n") == 2, (task, section.count("```bash\n"))
        brief = root / f"task-{task}-brief.md"
        brief.write_text(brief_text, encoding="utf-8")
        os.chmod(brief, 0o600)
        info = os.stat(brief, follow_symlinks=False)
        assert stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
        program = root / f"task-{task}-extract.py"
        program.write_text(programs[task], encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable, "-P", str(program), str(brief),
                hashlib.sha256(brief.read_bytes()).hexdigest(), str(info.st_dev), str(info.st_ino),
            ],
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode == 0, (task, result.stderr.decode("utf-8", "replace"))
        assert result.stderr == b"", (task, result.stderr)
        outputs[task] = result.stdout
    assert outputs[4] == outputs[5] == outputs[7]
    digest = hashlib.sha256(outputs[4]).hexdigest()
    print(f"TASK457_EXTRACTION_GREEN bytes={len(outputs[4])} sha256={digest}")
PY
```

- [ ] **Step 3: Verify payload and protected identities**

Run this self-contained read-only harness:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - "$C" <<'PY'
from __future__ import annotations
import hashlib
import re
import sys
from pathlib import Path

plan = Path(sys.argv[1]).read_text(encoding="utf-8")
ticks = chr(96)
f3, f4 = ticks * 3, ticks * 4
expected = {
    "A0": (322, 16202, "81f7216f1f1f454276c177804f26aa9260ab41a1bc5e71e2015a91781aa4c50b"),
    "A": (425, 21493, "39b2665064ee8e1be72bb73318a60a46b467c01da636eed4dab5c05945c6d610"),
    "B1": (353, 13149, "f66cf823a0c399ec310c676e200a582834590cbb195978f9f37584da5e1080ff"),
    "B2I": (626, 24168, "4a45f69f8aae1f72711119e9ecd4e4f6a91a3fcfe88488b737c7c154696ec3fe"),
    "B2": (773, 29338, "a67525432beca49a09c14b3ce266c46109900344cb4f2515f23fccd9a3de530d"),
    "C0": (655, 26314, "ea39caf013cdbfccfdd7987ef588fcce8ed509b7b5db62af86b445cd460f7383"),
    "C": (937, 36994, "9e2f58d3bf98d9c7113d10362c4637f6a36e0a9fb389ff0b1d2c509f5806e0b3"),
    "R2_FIXTURE_SETUP": (57, 2288, "b94433e1aea2d8087a0ebd4596a4cb2d19c04955086abcbf8ee388a989cd8681"),
    "R2_MODEL_BODY": (368, 14604, "534f38477d968d8ae4262340b1f172d51cba25e206c86a6a41976071aa638034"),
    "R2_CLI_BODY": (33, 944, "c358ad5ec7f30c8bdf7d7fae28ef1f71682d118b2b6dd462ac5ee522a7e241d2"),
    "R2_CONTROLLER": (6193, 254319, "cc325e471aa0d1a0349deade58d0f7517575c35d901fb99f00ee1cc4de7f640a"),
}
heads = {m.group(1): m.start() for m in re.finditer(r"(?m)^## Appendix ([0-9A-Z]+)\b", plan)}
payloads: dict[str, bytes] = {}
for key, fence, language in (
    ("A0", f4, "markdown"), ("A", f4, "markdown"),
    ("B1", f3, "python"), ("B2I", f3, "python"), ("B2", f3, "python"),
    ("C0", f3, "python"), ("C", f3, "python"),
):
    opener, closer = fence + language + "\n", "\n" + fence + "\n"
    start = plan.index(opener, heads[key]) + len(opener)
    payloads[key] = plan[start:plan.index(closer, start) + 1].encode("utf-8")
for key, fence in (
    ("R2_FIXTURE_SETUP", f3), ("R2_MODEL_BODY", f3),
    ("R2_CLI_BODY", f3), ("R2_CONTROLLER", f4),
):
    opener = f"<!-- {key}_BEGIN -->\n{fence}python\n"
    closer = f"\n{fence}\n<!-- {key}_END -->"
    start = plan.index(opener) + len(opener)
    payloads[key] = plan[start:plan.index(closer, start) + 1].encode("utf-8")
for key, payload in payloads.items():
    measured = (len(payload.splitlines()), len(payload), hashlib.sha256(payload).hexdigest())
    assert measured == expected[key], (key, measured, expected[key])
assert payloads["B2I"] == Path("scripts/official_blender_mcp_audit.py").read_bytes()
assert payloads["R2_CONTROLLER"] == Path(
    ".superpowers/sdd/modeling-remediation/r20-production-controller.py"
).read_bytes()
protected = {
    ".superpowers/sdd/modeling-remediation/final-retest-r1/invalid-journals.sha256":
        "8292ac78073804687faab381181881ac7f522da1edea2dffe625626c1482c535",
    ".superpowers/sdd/modeling-remediation/final-retest-r1/journal-attempt1.ndjson":
        "b6f2568116080d4936a3d753a419c771c00233a67111ed626cc2bbe169c79f0e",
    ".superpowers/sdd/modeling-remediation/final-retest-r1/journal-attempt2.ndjson":
        "909fb6510a7ae4f115688add9d1eb0b25430ec9d4f490d16fb56b72343b24e7b",
}
for name, digest in protected.items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
print("PROTECTED_IDENTITIES_GREEN payloads=11 cmp=2 protected=3")
PY
```

Expected exactly `PROTECTED_IDENTITIES_GREEN payloads=11 cmp=2 protected=3`.

- [ ] **Step 4: Publish only after every candidate check is GREEN**

Run:

```bash
/bin/bash -euo pipefail <<'BASH'
P=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
test "$(git status --porcelain=v1 --untracked-files=no)" = " M $P"
cmp -s .superpowers/sdd/tools/cand.md "$P" || \
  cp .superpowers/sdd/tools/cand.md "$P"
chmod 644 "$P"
cmp -s .superpowers/sdd/tools/cand.md "$P"
wc -l -c "$P"
shasum -a 256 "$P"
test "$(git status --porcelain=v1 --untracked-files=no)" = " M $P"
BASH
```

Expected: `cmp` rc 0 and Git status contains exactly one tracked modification, the Plan.

- [ ] **Step 5: Repeat all acceptance on the tracked Plan**

Repeat Steps 1–3 with `C="$P"`, then run `git diff --check -- "$P"`. Require the same identities and GREEN summaries. Append the post-copy evidence and `B2I/R2_CONTROLLER/P6/R1 byte identities unchanged` to `.superpowers/sdd/progress.md`.

---

### Task 6: Obtain official zero-finding certification

**Files:**
- Create through allocator: `.superpowers/sdd/modeling-remediation/plan-{spec,execution,ponytail}-review-rN.md`
- Append: `.superpowers/sdd/progress.md`
- Do not modify while lenses run: tracked Plan and candidate

**Interfaces:**
- Consumes: the published Plan triple from Task 5.
- Produces: three mode-0600 reports with 0 Critical / 0 Important / 0 Minor, all bound to the same Plan identity.

- [ ] **Step 1: Perform the one-time live allocation for the next round**

Before allocation require Git status has only the Plan and all Task 5 checks remain GREEN. The allocator itself derives and reserves the next monotonic number; the initial expected number is 34, while any burned-round retry must be greater than the previous round. Extract and execute the allocator below, setting `ALLOCATE=1` only for that execution.

Run exactly:

```bash
/bin/bash -euo pipefail <<'BASH'
P=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
ALLOC_ROOT="$(mktemp -d /private/tmp/r34-allocation.XXXXXX)"
chmod 700 "$ALLOC_ROOT"
GATE="$ALLOC_ROOT/gate.sh"
cleanup() {
  PYTHONDONTWRITEBYTECODE=1 "$UV" run --quiet --no-project --python 3.13 \
    python -P - "$ALLOC_ROOT" <<'PY'
import shutil
import sys
from pathlib import Path
root = Path(sys.argv[1])
assert root.parent == Path("/private/tmp") and root.name.startswith("r34-allocation.")
shutil.rmtree(root)
PY
}
trap cleanup EXIT
PYTHONDONTWRITEBYTECODE=1 "$UV" run --quiet --no-project --python 3.13 \
  python -P - "$P" "$GATE" <<'PY'
import sys
from pathlib import Path
ticks = chr(96) * 3
opened = "<!-- PLAN_IDENTITY" + "_GATE_BEGIN -->\n" + ticks + "bash\n"
closed = "\n" + ticks + "\n<!-- PLAN_IDENTITY" + "_GATE_END -->"
text = Path(sys.argv[1]).read_text(encoding="utf-8")
assert text.count(opened) == 1 and text.count(closed) == 1
start = text.index(opened) + len(opened)
Path(sys.argv[2]).write_text(text[start:text.index(closed, start) + 1], encoding="utf-8")
PY
PYTHONDONTWRITEBYTECODE=1 "$UV" run --quiet --no-project --python 3.13 \
  python -P - "$P" "$GATE" <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

plan_path = Path(sys.argv[1])
gate = Path(sys.argv[2])
room = Path(".superpowers/sdd/modeling-remediation")
tools = Path(".superpowers/sdd/tools")
room_fd = os.open(room, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    room_info = os.fstat(room_fd)
    assert (
        stat.S_ISDIR(room_info.st_mode)
        and room_info.st_uid == os.getuid()
        and stat.S_IMODE(room_info.st_mode) == 0o700
    ), room_info
    result = subprocess.run(
        ["/bin/bash", str(gate)],
        capture_output=True,
        text=True,
        env={**os.environ, "ALLOCATE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    rounds = [
        int(match.group(1))
        for line in result.stdout.splitlines()
        if (match := re.fullmatch(r"PLAN_REVIEW_ROUND_ALLOCATED n=([0-9]+) lenses=3", line))
    ]
    if len(rounds) != 1:
        raise RuntimeError(f"allocation round line count={len(rounds)}, expected 1")
    round_number = rounds[0]
    identities: dict[str, dict[str, int | str]] = {}
    for lens in ("spec", "execution", "ponytail"):
        name = f"plan-{lens}-review-r{round_number}.md"
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=room_fd)
        try:
            opened = os.fstat(descriptor)
            final = os.stat(name, dir_fd=room_fd, follow_symlinks=False)
        finally:
            os.close(descriptor)
        assert (
            stat.S_ISREG(opened.st_mode)
            and opened.st_uid == os.getuid()
            and stat.S_IMODE(opened.st_mode) == 0o600
            and opened.st_nlink == 1
            and opened.st_size == 0
            and (final.st_dev, final.st_ino) == (opened.st_dev, opened.st_ino)
        ), (lens, opened, final)
        identities[lens] = {
            "path": str(room / name), "dev": opened.st_dev, "ino": opened.st_ino,
            "uid": opened.st_uid, "mode": 0o600, "nlink": 1, "size": 0,
        }
finally:
    os.close(room_fd)

plan = plan_path.read_bytes()
triple = (
    f"{len(plan.splitlines())} lines / {len(plan)} bytes / sha256 "
    f"{hashlib.sha256(plan).hexdigest()}"
)
manifest = {
    "round": round_number,
    "plan_path": str(plan_path),
    "plan_triple": triple,
    "reports": identities,
}
encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
manifest_name = f"r{round_number}-report-identities.json"
tools_fd = os.open(tools, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    descriptor = os.open(
        manifest_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=tools_fd,
    )
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(encoded)
        while view:
            view = view[os.write(descriptor, view):]
        os.fsync(descriptor)
        manifest_info = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    manifest_final = os.stat(manifest_name, dir_fd=tools_fd, follow_symlinks=False)
finally:
    os.close(tools_fd)
assert (
    stat.S_ISREG(manifest_info.st_mode)
    and manifest_info.st_uid == os.getuid()
    and stat.S_IMODE(manifest_info.st_mode) == 0o600
    and manifest_info.st_nlink == 1
    and manifest_info.st_size == len(encoded)
    and (manifest_final.st_dev, manifest_final.st_ino)
        == (manifest_info.st_dev, manifest_info.st_ino)
)
print(f"ROUND={round_number}")
print(f"REPORT_MANIFEST_SHA256={hashlib.sha256(encoded).hexdigest()}")
print(f"REPORT_MANIFEST_DEV={manifest_info.st_dev}")
print(f"REPORT_MANIFEST_INO={manifest_info.st_ino}")
print(f"REPORT_MANIFEST_UID={manifest_info.st_uid}")
print("REPORT_MANIFEST_MODE=0600")
print(f"REPORT_MANIFEST_NLINK={manifest_info.st_nlink}")
print(f"REPORT_MANIFEST_SIZE={manifest_info.st_size}")
PY
trap - EXIT
cleanup
BASH
```

Expected on the initial pass: the unchanged gate banner, `PLAN_REVIEW_ROUND_ALLOCATED n=34 lenses=3`, `ROUND=34`, and the seven `REPORT_MANIFEST_*` binding lines. On a retry, the allocated and printed number must be the next monotonic number, not 34. Preserve the exact eight assignment values printed by this transaction; they are the external trust root consumed by Steps 2–3 and Task 7. Require three new empty mode-0600 files, one new mode-0600 identity manifest, and no other live-room change.

- [ ] **Step 2: Freeze the Plan and dispatch three fresh lenses concurrently**

Each prompt must contain all six required groups from handoff section 6: exact Plan path and binding triple with start/end remeasurement; the preallocated report path and exclusive-write constraint; lens remit; its own R33 findings plus the R34 response; all ten hard constraints plus fixture-only allocation, candidate-reextracted gate, and mandatory non-no-op mutation assertions; exact report format and zero-finding certification rule.

The lenses are:

- `spec`: complete requirements, prose/code consistency, safety, identity declarations, and responses to R33 spec findings;
- `execution`: recursive syntax, executable fences, exact five-state probes, Task 4/5/7 extraction, allocator fixture, mutations, and ordering;
- `ponytail`: unnecessary complexity, duplicated mechanisms, stale prose, simpler safe alternatives, and responses to R33 ponytail findings.

Do not edit Plan or candidate until all three agents have finished and remeasured their binding inputs.

Create the three complete prompt files with the allocated `ROUND` from Step 1:

```bash
ROUND="${ROUND:?set ROUND to the number printed by Step 1}"
REPORT_MANIFEST_SHA256="${REPORT_MANIFEST_SHA256:?copy the exact Step 1 value}"
REPORT_MANIFEST_DEV="${REPORT_MANIFEST_DEV:?copy the exact Step 1 value}"
REPORT_MANIFEST_INO="${REPORT_MANIFEST_INO:?copy the exact Step 1 value}"
REPORT_MANIFEST_UID="${REPORT_MANIFEST_UID:?copy the exact Step 1 value}"
REPORT_MANIFEST_MODE="${REPORT_MANIFEST_MODE:?copy the exact Step 1 value}"
REPORT_MANIFEST_NLINK="${REPORT_MANIFEST_NLINK:?copy the exact Step 1 value}"
REPORT_MANIFEST_SIZE="${REPORT_MANIFEST_SIZE:?copy the exact Step 1 value}"
export ROUND REPORT_MANIFEST_SHA256 REPORT_MANIFEST_DEV REPORT_MANIFEST_INO
export REPORT_MANIFEST_UID REPORT_MANIFEST_MODE REPORT_MANIFEST_NLINK REPORT_MANIFEST_SIZE
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P - <<'PY'
from __future__ import annotations
import hashlib
import json
import os
import stat
from pathlib import Path

round_number = int(os.environ["ROUND"])
plan_path = Path("docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md")
payload = plan_path.read_bytes()
triple = f"{len(payload.splitlines())} lines / {len(payload)} bytes / sha256 {hashlib.sha256(payload).hexdigest()}"
manifest_path = Path(f".superpowers/sdd/tools/r{round_number}-report-identities.json")
before = os.lstat(manifest_path)
descriptor = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW)
try:
    opened = os.fstat(descriptor)
    encoded = os.read(descriptor, 65_537)
finally:
    os.close(descriptor)
after = os.lstat(manifest_path)
expected_identity = (
    int(os.environ["REPORT_MANIFEST_DEV"]),
    int(os.environ["REPORT_MANIFEST_INO"]),
    int(os.environ["REPORT_MANIFEST_UID"]),
    int(os.environ["REPORT_MANIFEST_MODE"], 8),
    int(os.environ["REPORT_MANIFEST_NLINK"]),
    int(os.environ["REPORT_MANIFEST_SIZE"]),
)
measured_identity = (
    opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode),
    opened.st_nlink, opened.st_size,
)
assert measured_identity == expected_identity, (measured_identity, expected_identity)
assert (after.st_dev, after.st_ino, after.st_size) == (
    opened.st_dev, opened.st_ino, opened.st_size,
)
assert len(encoded) == opened.st_size and len(encoded) <= 65_536
assert hashlib.sha256(encoded).hexdigest() == os.environ["REPORT_MANIFEST_SHA256"]
manifest = json.loads(encoded)
assert manifest["round"] == round_number
assert manifest["plan_path"] == str(plan_path)
assert manifest["plan_triple"] == triple
identities = manifest["reports"]
assert set(identities) == {"spec", "execution", "ponytail"}
common = f"""Subject: {plan_path}
Binding identity: {triple}
Worktree: /Users/yeminjie/Developer/BlenderDesign/.worktrees/official-blender-mcp-install
Report binding: REPORT_BINDING

Measure the subject at review start and review end. If either triple differs from the binding
identity, stop without certifying. You are read-only except for your one preallocated report.
Write only REPORT_PATH, which already exists, is empty and mode 0600. Do not create, unlink,
rename, replace, or path-truncate your report or any other report; do not modify any
Plan/candidate/protected file. Build the complete report as UTF-8 bytes in memory. Open your
report once with os.O_WRONLY | os.O_NOFOLLOW and without O_CREAT or O_TRUNC. Before writing,
require fstat and lstat to equal REPORT_BINDING and require regular file, own UID, mode 0600,
nlink 1 and size 0. On that same descriptor call ftruncate(0), write all bytes, fsync, then
require fstat and lstat still have the bound dev/ino/UID/mode/nlink and the exact payload size.

Hard constraints:
1. No git add or git commit before all three reports are 0/0/0.
2. There is one Plan writer; while the three lenses run the Plan is frozen.
3. Do not modify or recreate the P6 manifest; expected sha256 8292ac78073804687faab381181881ac7f522da1edea2dffe625626c1482c535.
4. Do not modify either R1 journal; expected sha256 b6f2568116080d4936a3d753a419c771c00233a67111ed626cc2bbe169c79f0e and 909fb6510a7ae4f115688add9d1eb0b25430ec9d4f490d16fb56b72343b24e7b.
5. Do not modify scripts/official_blender_mcp_audit.py; it must remain byte-identical to B2I sha256 4a45f69f8aae1f72711119e9ecd4e4f6a91a3fcfe88488b737c7c154696ec3fe.
6. Do not loosen symlink/UID/mode/nlink/dev/ino/size checks.
7. Do not broadly kill Blender, MCP or uv processes.
8. Set PYTHONDONTWRITEBYTECODE=1; mutable fixtures live only in your new mode-0700 /private/tmp root.
9. Never run ALLOCATE=1 against the live room. Any allocator test is fixture-only. Re-extract the gate from the reviewed candidate for every gate run.
10. Do not write main.
Every mutation must assert its target is present and unique and assert mutated != base before judging a color. A preparation/repair exception is not a gate RED unless the exact mutation is explicitly proving that regeneration is impossible.

Report format:
- a title, then exact standalone lines `Lens: LENS` and `Report path: REPORT_PATH`
- exact standalone line `Binding start: {triple}`
- exact standalone verdict lines `Critical: N`, `Important: N`, `Minor: N`
- each finding with Plan line, consequence, mechanical evidence and exact fix direction
- each prior R33 finding with CLOSED or OPEN and evidence
- checks performed and checks not performed
- exact standalone line `Binding end: {triple}` after remeasurement
- exact standalone `CERTIFIED` only when all three counts are zero and both identities equal the binding identity
"""
lenses = {
    "spec": """Remit: requirements completeness, safety, prose/code consistency, identity declarations and operator contract.
R33 findings to re-verify:
- I-1 dangling Appendix D fragment kept the deleted dirty-then-clean Task 7 lane.
  R34 response: the fragment is replaced by the complete sentence `TASK_N` and `TASK_REPORT` bind lanes.
- I-2 Task 7 copied the Task 4/5 Appendix-D-is-last guard and rejected every real A/C/D/F brief.
  R34 response: Task 7 now requires exactly one Appendix F, rejects Appendix E, slices before F, then retains the two D fence checks.
- M-1 Expected prose said `Task 5 and Task 7 clean lane are clean`.
  R34 response: it now says Task 5 and Task 7 are clean.
Independently sweep for partial prose repairs; do not accept these responses without measurement.
""",
    "execution": """Remit: recursive fence/heredoc syntax, executable commands, exact five-state probes, Task 4/5/7 extraction, allocator fixture behavior, mutation discrimination and ordering.
R33 findings to re-verify:
- C-1 Task 7 rejected Appendix F and counted eight Bash fences rather than the two in D.
  R34 response: the Task 7 extractor scopes D before counting and a byte-derived harness must yield the same 105067-byte body for Tasks 4/5/7.
- I-1 the dangling lowercase `while recording audit evidence` fragment contradicted the executable lane table.
  R34 response: the fragment is gone and lane prose names the single 7:0 invocation.
- M-1 the Task 7 comment still documented Task 4/5 required=(A0,C0,D).
  R34 response: the comment documents required=(A,C,D,F) and its exact guard.
Run a recursive census (expected 93 fences and 99 heredocs), exact filesystem-state probes, and non-no-op mutations; do not rely on tail-only output.
""",
    "ponytail": """Remit: unnecessary complexity, duplicated mechanisms, stale prose, hardcoded assumptions and simpler safe standard-library alternatives. Preserve required self-contained Task fences.
R33 findings to re-verify:
- C-1 Task 7 reused a false Task 4/5 premise. R34 response: one scoped Task 7 slice guard replaces it.
- M-1 READER_CAP prose falsely said neither module reader shared the Appendix D/E cap and counted one escape. R34 response: it names the shared ack helper cap and the two literal-cap family-digest-only escapes.
- M-2 comment said one full extra reader copy. R34 response: two full copies.
- M-3 EXPECTED_MAIN_ANCHOR callers said Tasks 4-5. R34 response: Tasks 4, 5 and 7.
Verify every response and search for twins; do not propose factoring the three self-contained Task extraction fences through an unavailable cross-reference.
""",
}
for lens, remit in lenses.items():
    report = Path(f".superpowers/sdd/modeling-remediation/plan-{lens}-review-r{round_number}.md")
    binding = identities[lens]
    binding_text = (
        f"dev={binding['dev']} ino={binding['ino']} uid={binding['uid']} "
        f"mode=0600 nlink=1 size=0"
    )
    prompt = (
        common.replace("REPORT_PATH", str(report))
        .replace("REPORT_BINDING", binding_text)
        .replace("LENS", lens)
        + "\n" + remit
    )
    out = Path(f".superpowers/sdd/tools/r{round_number}-{lens}-prompt.md")
    out.write_text(prompt, encoding="utf-8")
    print(f"PROMPT_READY {lens} {out} report={report}")
print(f"REPORT_IDENTITIES_READY {manifest_path}")
PY
```

Dispatch each lens with the complete contents of its generated prompt file and no contradictory extra instruction. The prompt files are ignored coordination artifacts; do not stage them.

- [ ] **Step 3: Adjudicate the round without averaging findings**

Create ignored `.superpowers/sdd/tools/certify-reports.py` with this fail-closed implementation:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path

LENSES = ("spec", "execution", "ponytail")
LIMIT = 1_048_576


def triple(path: Path) -> str:
    payload = path.read_bytes()
    return (
        f"{len(payload.splitlines())} lines / {len(payload)} bytes / sha256 "
        f"{hashlib.sha256(payload).hexdigest()}"
    )


def read_owned(
    path: Path,
    *,
    require_empty: bool,
    expected: dict[str, object] | None = None,
    expected_size: int | None = None,
) -> bytes:
    before = os.lstat(path)
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.getuid()
        or stat.S_IMODE(before.st_mode) != 0o600
        or before.st_nlink != 1
        or before.st_size > LIMIT
        or (require_empty and before.st_size != 0)
        or (not require_empty and before.st_size <= 0)
        or (expected_size is not None and before.st_size != expected_size)
    ):
        raise RuntimeError(f"unsafe report artifact: {path}")
    if expected is not None:
        bound = (
            int(expected["dev"]), int(expected["ino"]), int(expected["uid"]),
            int(expected["mode"]), int(expected["nlink"]),
        )
        declared = (
            before.st_dev, before.st_ino, before.st_uid,
            stat.S_IMODE(before.st_mode), before.st_nlink,
        )
        if declared != bound:
            raise RuntimeError(f"preallocated report identity differs: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise RuntimeError(f"report changed before read: {path}")
        chunks: list[bytes] = []
        remaining = LIMIT + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > LIMIT:
            raise RuntimeError(f"report exceeds bound: {path}")
    finally:
        os.close(descriptor)
    after = os.lstat(path)
    if (
        (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_uid != before.st_uid
        or stat.S_IMODE(after.st_mode) != 0o600
        or after.st_nlink != 1
        or after.st_size != len(payload)
    ):
        raise RuntimeError(f"report changed during read: {path}")
    return payload


def require_unique(lines: list[str], value: str, label: str) -> None:
    count = lines.count(value)
    if count != 1:
        raise RuntimeError(f"{label} count={count}, expected 1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("round", type=int)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("manifest_sha256")
    parser.add_argument("manifest_dev", type=int)
    parser.add_argument("manifest_ino", type=int)
    parser.add_argument("manifest_uid", type=int)
    parser.add_argument("manifest_mode", type=lambda value: int(value, 8))
    parser.add_argument("manifest_nlink", type=int)
    parser.add_argument("manifest_size", type=int)
    args = parser.parse_args()
    manifest_expected = {
        "dev": args.manifest_dev, "ino": args.manifest_ino, "uid": args.manifest_uid,
        "mode": args.manifest_mode, "nlink": args.manifest_nlink,
    }
    manifest_payload = read_owned(
        args.manifest,
        require_empty=False,
        expected=manifest_expected,
        expected_size=args.manifest_size,
    )
    if hashlib.sha256(manifest_payload).hexdigest() != args.manifest_sha256:
        raise RuntimeError("report identity manifest digest differs")
    manifest = json.loads(manifest_payload)
    current = triple(args.plan)
    if manifest.get("round") != args.round:
        raise RuntimeError("report identity manifest round differs")
    if manifest.get("plan_path") != str(args.plan):
        raise RuntimeError("report identity manifest Plan path differs")
    if manifest.get("plan_triple") != current:
        raise RuntimeError("Plan identity differs from allocated review identity")
    reports = manifest.get("reports")
    if not isinstance(reports, dict) or set(reports) != set(LENSES):
        raise RuntimeError("report identity manifest lens set differs")
    for lens in LENSES:
        path = Path(
            f".superpowers/sdd/modeling-remediation/plan-{lens}-review-r{args.round}.md"
        )
        expected = reports[lens]
        if not isinstance(expected, dict) or expected.get("path") != str(path):
            raise RuntimeError(f"report path binding differs: {lens}")
        payload = read_owned(path, require_empty=False, expected=expected)
        try:
            lines = payload.decode("utf-8").splitlines()
        except UnicodeDecodeError as error:
            raise RuntimeError(f"report is not UTF-8: {path}") from error
        require_unique(lines, f"Lens: {lens}", f"{lens} lens")
        require_unique(lines, f"Report path: {path}", f"{lens} path")
        require_unique(lines, f"Binding start: {current}", f"{lens} start binding")
        require_unique(lines, f"Binding end: {current}", f"{lens} end binding")
        for severity in ("Critical", "Important", "Minor"):
            declared = [line for line in lines if re.fullmatch(rf"{severity}: [0-9]+", line)]
            if declared != [f"{severity}: 0"]:
                raise RuntimeError(f"{lens} {severity} verdict differs: {declared}")
        require_unique(lines, "CERTIFIED", f"{lens} certification")
    digest = current.rsplit(" ", 1)[1]
    print(
        f"PLAN_REVIEW_CERTIFICATION_GREEN round={args.round} reports=3 "
        f"sha256={digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

After all three agents stop, run:

```bash
ROUND="${ROUND:?set ROUND to the dispatched round}"
: "${REPORT_MANIFEST_SHA256:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_DEV:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_INO:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_UID:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_MODE:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_NLINK:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_SIZE:?use the exact certified allocation value}"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P \
  .superpowers/sdd/tools/certify-reports.py \
  docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md \
  "$ROUND" ".superpowers/sdd/tools/r${ROUND}-report-identities.json" \
  "$REPORT_MANIFEST_SHA256" "$REPORT_MANIFEST_DEV" "$REPORT_MANIFEST_INO" \
  "$REPORT_MANIFEST_UID" "$REPORT_MANIFEST_MODE" \
  "$REPORT_MANIFEST_NLINK" "$REPORT_MANIFEST_SIZE"
```

The sole success line is `PLAN_REVIEW_CERTIFICATION_GREEN round=<ROUND> reports=3 sha256=<current Plan SHA-256>`. An empty report, unsafe or replaced report inode, wrong round/path/lens, missing or nonzero verdict, missing certification, binding drift, or disagreement with the current Plan must exit nonzero.

Any finding burns the round. After all agents have stopped, copy the current tracked Plan to a fresh `cand.md`; for each validated new finding, record the report's exact old bytes and the corrected new bytes in `.superpowers/sdd/progress.md`, assert the old bytes occur exactly once in the intended task/family scope, apply the replacement, and assert the candidate changed. Do **not** rerun Task 4's seven fixed R33 replacements: their old anchors are intentionally gone. Run `repair.py` on the new candidate, require `rungate.sh` GREEN, sweep every old/new phrase named by the new finding, record the new triple, then run all Task 5 checks and publish. If a correction intentionally changes fence or heredoc counts, first rederive the complete counts with the recursive walker and update every explicit syntax census argument consistently; otherwise the fixed 93/99/68/10/49/41/1/8 census remains mandatory. Allocate the next monotonic round exactly once with Step 1 and dispatch three fresh lenses. Never reuse or overwrite a report path or its identity manifest.

- [ ] **Step 4: Record certification evidence**

When one round is fully clean, append its round number, the exact seven externally printed `REPORT_MANIFEST_*` values, all three report paths, their report SHA-256 values, the shared Plan triple, and `Plan frozen for complete lens interval` to `.superpowers/sdd/progress.md`. Task 7 must consume those recorded binding values unchanged; it must not rederive them from the manifest path.

---

### Task 7: Create the protocol-authorized Plan-only commit

**Files:**
- Stage/commit only: `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`
- Read only: the three clean official reports and protected files

**Interfaces:**
- Consumes: Task 6 certification bound to the current unchanged Plan.
- Produces: one commit whose tree delta contains exactly the Plan.

- [ ] **Step 1: Recheck the certification binding immediately before staging**

First run the exact same fail-closed parser used to earn certification:

```bash
ROUND="${ROUND:?set ROUND to the certified round}"
P=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
: "${REPORT_MANIFEST_SHA256:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_DEV:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_INO:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_UID:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_MODE:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_NLINK:?use the exact certified allocation value}"
: "${REPORT_MANIFEST_SIZE:?use the exact certified allocation value}"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3 -P \
  .superpowers/sdd/tools/certify-reports.py \
  "$P" "$ROUND" ".superpowers/sdd/tools/r${ROUND}-report-identities.json" \
  "$REPORT_MANIFEST_SHA256" "$REPORT_MANIFEST_DEV" "$REPORT_MANIFEST_INO" \
  "$REPORT_MANIFEST_UID" "$REPORT_MANIFEST_MODE" \
  "$REPORT_MANIFEST_NLINK" "$REPORT_MANIFEST_SIZE"
```

Require the unique `PLAN_REVIEW_CERTIFICATION_GREEN` line for the current Plan. Then repeat every Task 5 candidate/published acceptance command against `C="$P"`: gate with `ALLOCATE=0`, syntax including collector/data counts, probes, three mutation suites, Task 4/5/7 extraction, all eleven payload and three protected-file identities, and `git diff --check`. Require `git status --porcelain=v1 --untracked-files=no` to equal exactly ` M docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`.

- [ ] **Step 2: Execute the Plan's own updated Step 5 commit fence verbatim**

Extract the Bash fence immediately following the unique heading `- [ ] **Step 5: Commit the approved Plan only**` from the current approved Plan and execute those bytes with the required environment:

```bash
/bin/bash -euo pipefail <<'BASH'
P=docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md
UV="${UV:-$HOME/.local/bin/uv}"
case "$UV" in /*) ;; *) echo 'STOP: UV must be absolute' >&2; exit 1 ;; esac
ROOT="$(mktemp -d /private/tmp/plan-commit.XXXXXX)"
chmod 700 "$ROOT"
FENCE="$ROOT/commit.sh"
cleanup() {
  PYTHONDONTWRITEBYTECODE=1 "$UV" run --quiet --no-project --python 3.13 \
    python -P - "$ROOT" <<'PY'
import shutil
import sys
from pathlib import Path
root = Path(sys.argv[1])
assert root.parent == Path("/private/tmp") and root.name.startswith("plan-commit.")
shutil.rmtree(root)
PY
}
trap cleanup EXIT
PYTHONDONTWRITEBYTECODE=1 "$UV" run --quiet --no-project --python 3.13 \
  python -P - "$P" "$FENCE" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text(encoding="utf-8")
heading = "- [ ] **Step 5: Commit the approved Plan only**\n"
assert text.count(heading) == 1
after = text.index(heading) + len(heading)
opener = "```bash\n"
start = text.index(opener, after) + len(opener)
end = text.index("\n```", start)
assert "git commit -m \"docs: revise official MCP modeling remediation plan\"" in text[start:end]
Path(sys.argv[2]).write_text(text[start:end] + "\n", encoding="utf-8")
PY
export PYTHONDONTWRITEBYTECODE=1
/bin/bash -euo pipefail "$FENCE"
trap - EXIT
cleanup
BASH
```

Do not copy the old `GATE_SHA256` literal from R33; the approved Plan contains the current value. Exporting `PYTHONDONTWRITEBYTECODE=1` before executing the fence binds all nested uv/Python commands in the extracted bytes.

Expected commit message: `docs: revise official MCP modeling remediation plan`.

- [ ] **Step 3: Verify the commit scope and stop at the plan boundary**

Run:

```bash
git show --stat --oneline --decorate HEAD
git diff-tree --no-commit-id --name-only -r HEAD
git status --short --branch
```

Expected changed-path output is exactly `docs/superpowers/plans/2026-08-10-official-blender-mcp-modeling-remediation.md`; tracked status is clean. Append the commit SHA and final gate banner to `.superpowers/sdd/progress.md`. Do not start Task 6/7 of the modeling Plan or Phase R/M.

---

## Post-Plan Decision Gate

The next implementation plan must start only after the user selects visual ACK option A, B, or C:

- A: make it falsifiable against observable pixels;
- B: explicitly downgrade it to a non-evidentiary process checkpoint;
- C: require the user to confirm each PNG.

That later plan must also reconcile the `32 3` feature/main divergence and the user-owned main `.gitignore` change before any `--ff-only` Phase M command. Neither issue is authorized for mutation here.
