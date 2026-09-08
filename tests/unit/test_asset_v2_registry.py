from acceptance import check_registry as reg


def test_v2_keeps_required_sets_and_versions_changed_semantics():
    assert len(reg.CHECKS) == 37
    assert len(reg.checks_for_kind("blend_native")) == 24
    assert len(reg.checks_for_kind("interchange")) == 34
    impl = {s.id: s.impl for s in reg.CHECKS}
    assert impl["r0.contract.tools_locked"] == 2
    assert impl["r1.input.digest_recorded"] == 2
    assert impl["r2.inventory.coverage_complete"] == 2
    assert impl["r5.evidence.hashes_match"] == 2
    assert impl["r3.validator.report_complete"] == 1
