import pytest

from acceptance.contract import Contract
from acceptance.evidence import summary_document
from acceptance.primitives import AcceptanceFailure


def test_invalid_contract_is_rejected_and_summary_survives_no_contract():
    with pytest.raises(AcceptanceFailure) as caught:
        Contract(
            raw={"artifact_kind": "blend_native", "required_isolation_grade": "local-trusted"},
            digest="d" * 64,
        )
    assert caught.value.code == "contract_invalid"

    document = summary_document(
        contract=None, verdict=None, achieved_grade="local-trusted",
        platform_key="darwin-arm64-none-none-none",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        evidence_manifest=[], runner_provenance={},
        failure_code="runner_internal_error", error="boom")
    assert document["contract_id"] is None
    assert document["artifact_kind"] is None
    assert document["required_isolation_grade"] is None
    assert document["failure_code"] == "runner_internal_error"
