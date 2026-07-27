# ABOUTME: Composes a fresh real SWMM generation and isolated W3 result through W4.
# ABOUTME: Demonstrates the preregistered C-R08 budget rejection without threshold tuning.

import os
from decimal import Decimal
from pathlib import Path

import run_w3_w5
from lineage import receipts
from promotion import decision
from sensitivity import catalogue, inputs


def test_fresh_real_generation_reaches_preregistered_w4_budget_rejection(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, "ASW_B5_ENGINE_RECEIPT must name the real B5 engine receipt"
    executed = run_w3_w5.execute(
        engine_receipt=Path(receipt_value),
        output_root=tmp_path / "w3-w5",
    )
    compact = executed["compact_root"]
    result_bytes = (compact / "w4-composition-result.json").read_bytes()
    result = inputs.read_canonical_object(result_bytes)
    family = inputs.read_canonical_object((compact / "family-decision.json").read_bytes())
    promotion = decision.read_promotion_decision((compact / "promotion-decision.json").read_bytes())
    receipt_index = inputs.read_canonical_object((compact / "receipt-index.json").read_bytes())
    chain = tuple(
        receipts.read_receipt((compact / item["relative_path"]).read_bytes()) for item in receipt_index["receipts"]
    )

    assert catalogue.canonical_json_bytes(result) == result_bytes
    assert result["terminal_state"] == "w4-budget-reject"
    assert result["first_failure"] == ("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling")
    assert result["promotable"] is False
    assert result["evidence"]["case_id"] in {
        "G10_CLEAN_A_BASE",
        "G11_CLEAN_B_BASE",
        "G12_CLEAN_ASSESS",
    }
    assert Decimal(result["evidence"]["budget"]["derived_lower_bound_m3_s"]) > Decimal(
        result["evidence"]["budget"]["hard_ceiling_m3_s"]
    )
    assert family["terminal_state"] == "family-member-reject"
    assert promotion["terminal_state"] == "promotion-generation-reject"
    assert promotion["manifest_content_ids"] == []
    assert promotion["package_content_ids"] == []
    assert executed["decision_summary"]["v3"] == "refused"
    assert executed["receipt_count"] == 8
    receipts.validate_receipt_graph(chain)
    assert b"/Users/" not in result_bytes
    assert b"/private/" not in result_bytes
