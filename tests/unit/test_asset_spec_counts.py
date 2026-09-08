from pathlib import Path
import re

from acceptance import check_registry as reg
from acceptance import failure_codes as fc

SPEC = (
    Path(__file__).resolve().parents[2]
    / "docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md"
)


def test_current_registry_table_matches_v2():
    text = SPEC.read_text()
    rows = re.findall(
        r"^\| `(r[0-5]\.[a-z_]+\.[a-z_]+)` \| ([0-9]+) \| `([^`]+)` \|$", text, re.M
    )
    assert rows == [(spec.id, str(spec.impl), spec.writer) for spec in reg.CHECKS]


def test_current_failure_family_table_is_complete():
    text = SPEC.read_text()
    rows = re.findall(r"^\| `([a-z_]+)` \| ([0-9]+) \|$", text, re.M)
    assert rows == [(name, str(index)) for index, name in enumerate(fc.FAILURE_FAMILIES)]
