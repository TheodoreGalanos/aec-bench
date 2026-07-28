# ABOUTME: Composes fresh real SWMM evidence through predecessor and amended W4 rules.
# ABOUTME: Demonstrates immutable refusal plus successor hydraulic checks without threshold tuning.

import os
from decimal import Decimal
from pathlib import Path

import run_w3_w5
from lineage import receipts
from promotion import decision
from sensitivity import anchor, catalogue, composition, inputs, mass

B5_ROOT = Path(__file__).parents[2]
RETAINED_SUCCESSOR = B5_ROOT / "results" / "v3-c-r02-refusal"


def test_retained_real_generation_passes_both_amended_hydraulic_rules() -> None:
    bundle_value = os.environ.get("ASW_B5_RETAINED_BUNDLE")
    result_value = os.environ.get("ASW_B5_RETAINED_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_RETAINED_BUNDLE must name retained real bundle bytes"
    assert result_value, "ASW_B5_RETAINED_CERTIFIER_RESULT must name retained W3 result bytes"

    result = composition.compose_amended_hydraulic_checkpoint(
        bundle_bytes=Path(bundle_value).read_bytes(),
        certifier_result_bytes=Path(result_value).read_bytes(),
    )

    assert result["terminal_state"] == "amended-hydraulic-checks-pass"
    assert result["first_failure"] == "none"
    assert result["checks"]["C-R07"]["outcome"] == "c-r07-checks-pass"
    assert result["checks"]["C-R08"]["outcome"] == "c-r08-checks-pass"
    assert result["promotable"] is False


def test_retained_real_generation_passes_composable_anchor_checks() -> None:
    bundle_value = os.environ.get("ASW_B5_RETAINED_BUNDLE")
    result_value = os.environ.get("ASW_B5_RETAINED_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_RETAINED_BUNDLE must name retained real bundle bytes"
    assert result_value, "ASW_B5_RETAINED_CERTIFIER_RESULT must name retained W3 result bytes"

    result = anchor.evaluate_composable_checks(
        bundle_bytes=Path(bundle_value).read_bytes(),
        certifier_result_bytes=Path(result_value).read_bytes(),
    )

    assert result["terminal_state"] == "composable-anchor-checks-pass"
    assert result["first_failure"] == "none"
    assert list(result["checks"]) == [
        "C-R01",
        "C-R04",
        "C-R05",
        "C-R06",
        "C-R07",
        "C-R08",
        "C-R09",
        "C-R13",
        "C-R14",
        "C-R23",
    ]
    assert all(check["outcome"] == "pass" for check in result["checks"].values())


def test_retained_real_generation_rejects_at_first_composed_mass_rule() -> None:
    bundle_value = os.environ.get("ASW_B5_RETAINED_BUNDLE")
    result_value = os.environ.get("ASW_B5_RETAINED_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_RETAINED_BUNDLE must name retained real bundle bytes"
    assert result_value, "ASW_B5_RETAINED_CERTIFIER_RESULT must name retained W3 result bytes"

    result = mass.evaluate_mass_checks(
        bundle_bytes=Path(bundle_value).read_bytes(),
        certifier_result_bytes=Path(result_value).read_bytes(),
    )

    assert result["terminal_state"] == "mass-checks-reject"
    assert result["first_failure"] == "C-R02-corrected-residual"
    assert result["checks"]["C-R12"]["outcome"] == "pass"
    assert result["checks"]["C-R12"]["edge_count"] == 44
    assert result["checks"]["C-R02"]["outcome"] == "reject"
    assert Decimal(result["checks"]["C-R02"]["maximum_ratio"]) > 1
    assert result["checks"]["C-R03"]["outcome"] == (
        "not-reached-after-c-r02-reject"
    )


def test_fresh_real_successor_reaches_c_r02_numerical_rejection(
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
    assert result["terminal_state"] == "w4-numerical-reject"
    assert result["first_failure"] == "C-R02-corrected-residual"
    assert result["promotable"] is False
    assert result["evidence"]["mass"]["checks"]["C-R12"]["outcome"] == "pass"
    assert result["evidence"]["mass"]["checks"]["C-R02"]["outcome"] == "reject"
    assert result["evidence"]["amended_hydraulics"]["checks"]["C-R07"]["outcome"] == (
        "c-r07-checks-pass"
    )
    assert result["evidence"]["amended_hydraulics"]["checks"]["C-R08"]["outcome"] == (
        "c-r08-checks-pass"
    )
    assert family["terminal_state"] == "family-member-reject"
    assert family["first_failure"] == "anchor-w4-numerical-reject"
    assert promotion["terminal_state"] == "promotion-generation-reject"
    assert promotion["manifest_content_ids"] == []
    assert promotion["package_content_ids"] == []
    assert executed["decision_summary"]["v3"] == "refused"
    assert executed["receipt_count"] == 8
    assert (compact / "decision-summary.json").read_bytes() == (
        RETAINED_SUCCESSOR / "decision-summary.json"
    ).read_bytes()
    assert result_bytes == (
        RETAINED_SUCCESSOR / "w4-composition-result.json"
    ).read_bytes()
    receipts.validate_receipt_graph(chain)
    assert b"/Users/" not in result_bytes
    assert b"/private/" not in result_bytes
