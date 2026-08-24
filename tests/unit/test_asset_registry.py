from acceptance import check_registry as reg
from acceptance import failure_codes as fc


def test_registry_has_37_unique_checks():
    assert len(reg.CHECKS) == 37
    assert len({c.id for c in reg.CHECKS}) == 37


def test_kind_split_matches_spec():
    counts: dict[str, int] = {}
    for c in reg.CHECKS:
        counts[c.kind] = counts.get(c.kind, 0) + 1
    assert counts == {"all": 21, "interchange": 13, "blend_native": 3}


def test_every_check_has_exactly_one_writer():
    assert all(c.writer for c in reg.CHECKS)


def test_na_set_is_complement_of_kind():
    blend = set(reg.na_check_ids("blend_native"))
    inter = set(reg.na_check_ids("interchange"))
    assert blend == {c.id for c in reg.CHECKS if c.kind == "interchange"}
    assert inter == {c.id for c in reg.CHECKS if c.kind == "blend_native"}
    assert blend & inter == set()


def test_stage_order_id_is_a_total_order():
    keys = [(c.stage, c.order, c.id) for c in reg.CHECKS]
    assert len(set(keys)) == len(keys)


def test_failure_families_are_16_and_check_failed_is_last():
    assert len(fc.FAILURE_FAMILIES) == 16
    assert fc.FAILURE_FAMILIES[-1] == "check_failed"
    assert "check_failed" not in fc.INFRA_FAMILIES
    assert len(fc.INFRA_FAMILIES) == 15


def test_family_priority_is_strictly_increasing():
    priorities = [fc.family_priority(f) for f in fc.FAILURE_FAMILIES]
    assert priorities == sorted(priorities)
    assert len(set(priorities)) == len(priorities)
