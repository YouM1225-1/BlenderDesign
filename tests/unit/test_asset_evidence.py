from acceptance.contract import Contract
from acceptance.evidence import summary_document


def test_summary_document_survives_missing_contract_id():
    """终审第 6 条回归:acceptance/evidence.py 曾经裸下标 contract.raw["contract_id"]。
    summary_document() 挂在 main() 的第二个 try 块里,那个 except 分支不写 summary.json
    就返回 1——原本唯一负责"无论如何都要留下证据"的函数,能被一个缺失字段逼成零证据。

    contract_id 是 load_contract() 里唯一只做存在性校验、不做类型/内容校验的顶层
    字段,也是 Contract 上唯一没有守卫属性的字段;而 contract.raw 是一个可变 dict
    (frozen=True 只冻结字段引用,不冻结字典内容,见 test_asset_contract.py 里同形状
    的三个 *_deleted_from_raw_is_rejected 测试),所以"raw 缺了某个键"不是纯假设。
    """
    contract = Contract(
        raw={"artifact_kind": "blend_native", "required_isolation_grade": "local-trusted"},
        digest="d" * 64,
    )
    document = summary_document(
        contract=contract, verdict=None, achieved_grade="local-trusted",
        platform_key="darwin-arm64-none-none-none",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        evidence_manifest=[], runner_provenance={},
        failure_code="runner_internal_error", error="boom")
    assert document["contract_id"] is None
    # 缺失字段只影响它自己;其余字段(走已有守卫属性)照常读出。
    assert document["artifact_kind"] == "blend_native"
    assert document["required_isolation_grade"] == "local-trusted"
    assert document["failure_code"] == "runner_internal_error"
