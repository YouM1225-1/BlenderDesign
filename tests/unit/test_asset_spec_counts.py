"""防止规范文档的计数与其表格脱节(连续三轮回归的根因)。"""
import re
from pathlib import Path

import pytest

from acceptance import check_registry as reg
from acceptance import failure_codes as fc

SPEC = (Path(__file__).resolve().parents[2]
        / "docs" / "acceptance" / "blender_mcp_skill_acceptance_optimized_v3_8.md")


@pytest.fixture(scope="module")
def spec_text() -> str:
    if not SPEC.exists():
        pytest.fail(f"spec document not present: {SPEC.name}")
    return SPEC.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    return text.split(start)[1].split(end)[0]


def test_registry_table_matches_code(spec_text):
    table = _section(spec_text, "### 7.1 Check registry", "### 7.1.1")
    ids = re.findall(r"^\| `(r[0-5]\.[a-z_]+\.[a-z_]+)` \|", table, re.M)
    assert ids == [c.id for c in reg.CHECKS]


def test_failure_family_table_matches_code(spec_text):
    table = _section(spec_text, "### 7.2 Failure-code", "### 7.3")
    families = re.findall(r"^\| `([a-z_]+)` \| (?:infra|\*\*asset\*\*) \|", table, re.M)
    assert families == list(fc.FAILURE_FAMILIES)


def test_fixture_counts_in_prose_match_the_table(spec_text):
    table = _section(spec_text, "### 8.3 夹具表", "### 8.4")
    rows = [r for r in table.splitlines() if r.startswith("| `")]
    l0 = [r for r in rows if "| L0 |" in r]
    l1 = [r for r in rows if "| L1 |" in r]
    kinds = {k: sum(1 for r in l0 if f"| {k} |" in r)
             for k in ("synthetic", "handcrafted", "generator")}
    claimed = re.search(
        r"L0 计 (\d+) 项\((\d+) synthetic \+ (\d+) handcrafted \+ (\d+) generator\)"
        r",L1 计 (\d+) 项", table)
    assert claimed is not None, "prose count sentence not found"
    assert [int(g) for g in claimed.groups()] == [
        len(l0), kinds["synthetic"], kinds["handcrafted"], kinds["generator"], len(l1)]


def test_every_family_has_at_least_one_fixture(spec_text):
    table = _section(spec_text, "### 8.3 夹具表", "### 8.4")
    lines = table.splitlines()
    # Find header row and locate "expected" column
    header_idx = None
    expected_col = None
    for i, line in enumerate(lines):
        if "expected" in line and line.startswith("|"):
            header_idx = i
            cells = [c.strip() for c in line.split("|")]
            for j, cell in enumerate(cells):
                if "expected" in cell:
                    expected_col = j
                    break
            break
    assert header_idx is not None and expected_col is not None, "expected column not found in table"

    rows = [r for r in lines if r.startswith("| `")]
    covered: set[str] = set()
    for row in rows:
        cells = [c.strip() for c in row.split("|")]
        expected = cells[expected_col] if len(cells) > expected_col else ""
        covered |= {f for f in fc.FAILURE_FAMILIES if f"`{f}`" in expected}
    assert set(fc.FAILURE_FAMILIES) - covered == set()
