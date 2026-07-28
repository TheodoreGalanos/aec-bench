# ABOUTME: Composes fresh real SWMM evidence through predecessor and amended W4 rules.
# ABOUTME: Demonstrates immutable refusal plus successor hydraulic checks without threshold tuning.

import hashlib
import os
from decimal import Decimal
from pathlib import Path

import pytest
import run_w3_w5
from certifier import certification
from generator import execution, request, transfer
from lineage import receipts
from promotion import decision
from sensitivity import (
    anchor,
    catalogue,
    composition,
    family,
    inputs,
    mass,
    member_evaluation,
    relationships,
    successor,
    trajectory,
)

B5_ROOT = Path(__file__).parents[2]
RETAINED_SUCCESSOR = B5_ROOT / "results" / "v3-c-r02-refusal"


def _sensitivity_subset(
    bundle_bytes: bytes,
    *,
    case_ids: tuple[str, ...],
    probe_id: str,
) -> bytes:
    value = inputs.read_canonical_object(bundle_bytes)
    first_request = inputs.read_canonical_object(
        bytes.fromhex(
            value["replays"][0]["cases"][0]["segments"][0]["roles"][0][
                "bytes_hex"
            ]
        )
    )
    for replay in value["replays"]:
        replay["cases"] = [
            case
            for case in replay["cases"]
            if case["case_id"] in case_ids
        ]
    value.update(
        {
            "member_content_id": first_request["member"][
                "member_content_id"
            ],
            "probe_id": probe_id,
            "schema_id": "asw-0b5.certifier-sensitivity-bundle.v1",
        }
    )
    return request.canonical_json_bytes(value)


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


def test_retained_v2_generation_cannot_claim_v3_mass_rules() -> None:
    bundle_value = os.environ.get("ASW_B5_RETAINED_BUNDLE")
    result_value = os.environ.get("ASW_B5_RETAINED_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_RETAINED_BUNDLE must name retained real bundle bytes"
    assert result_value, "ASW_B5_RETAINED_CERTIFIER_RESULT must name retained W3 result bytes"

    with pytest.raises(
        inputs.SensitivityInputError,
        match="solver convergence amendment requires settings v3",
    ):
        mass.evaluate_amended_mass_checks(
            amendment_bytes=(
                B5_ROOT
                / "declarations"
                / "w4-c-r02-routing-integration-amendment.json"
            ).read_bytes(),
            bundle_bytes=Path(bundle_value).read_bytes(),
            certifier_result_bytes=Path(result_value).read_bytes(),
            solver_convergence_bytes=(
                B5_ROOT
                / "declarations"
                / "solver-convergence-amendment.json"
            ).read_bytes(),
        )


def test_fresh_v3_generation_passes_amended_trajectory_checks() -> None:
    bundle_value = os.environ.get("ASW_B5_FRESH_BUNDLE")
    result_value = os.environ.get("ASW_B5_FRESH_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_FRESH_BUNDLE must name fresh V3 bundle bytes"
    assert result_value, (
        "ASW_B5_FRESH_CERTIFIER_RESULT must name fresh V3 W3 result bytes"
    )

    result = trajectory.evaluate_trajectory_checks(
        amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "w4-c-r02-routing-integration-amendment.json"
        ).read_bytes(),
        bundle_bytes=Path(bundle_value).read_bytes(),
        certifier_result_bytes=Path(result_value).read_bytes(),
        control_edge_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "control-edge-trajectory-amendment.json"
        ).read_bytes(),
        solver_convergence_bytes=(
            B5_ROOT
            / "declarations"
            / "solver-convergence-amendment.json"
        ).read_bytes(),
    )

    assert result["terminal_state"] == "trajectory-checks-pass"
    assert result["first_failure"] == "none"
    assert result["checks"]["C-R10"]["outcome"] == "pass"
    assert result["checks"]["C-R11"]["outcome"] == "pass"


def test_fresh_v3_successor_reaches_anchor_checks_pass() -> None:
    bundle_value = os.environ.get("ASW_B5_FRESH_BUNDLE")
    result_value = os.environ.get("ASW_B5_FRESH_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_FRESH_BUNDLE must name fresh V3 bundle bytes"
    assert result_value, (
        "ASW_B5_FRESH_CERTIFIER_RESULT must name fresh V3 W3 result bytes"
    )

    result = successor.compose_generation(
        bundle_bytes=Path(bundle_value).read_bytes(),
        c_r02_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "w4-c-r02-routing-integration-amendment.json"
        ).read_bytes(),
        certifier_result_bytes=Path(result_value).read_bytes(),
        control_edge_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "control-edge-trajectory-amendment.json"
        ).read_bytes(),
        probe_catalogue_bytes=(
            B5_ROOT / "declarations" / "w4-probe-catalogue.json"
        ).read_bytes(),
        solver_convergence_bytes=(
            B5_ROOT
            / "declarations"
            / "solver-convergence-amendment.json"
        ).read_bytes(),
    )

    assert result["terminal_state"] == "w4-checks-pass"
    assert result["first_failure"] == "none"
    assert result["evidence"]["mass"]["terminal_state"] == (
        "mass-checks-pass"
    )
    assert result["evidence"]["trajectory"]["terminal_state"] == (
        "trajectory-checks-pass"
    )
    assert result["promotable"] is False


def test_fresh_v3_generation_passes_relationship_checks() -> None:
    bundle_value = os.environ.get("ASW_B5_FRESH_BUNDLE")
    result_value = os.environ.get("ASW_B5_FRESH_CERTIFIER_RESULT")
    assert bundle_value, "ASW_B5_FRESH_BUNDLE must name fresh V3 bundle bytes"
    assert result_value, (
        "ASW_B5_FRESH_CERTIFIER_RESULT must name fresh V3 W3 result bytes"
    )

    bundle_bytes = Path(bundle_value).read_bytes()
    certifier_result_bytes = Path(result_value).read_bytes()
    amendment_bytes = (
        B5_ROOT
        / "declarations"
        / "w4-c-r02-routing-integration-amendment.json"
    ).read_bytes()
    solver_convergence_bytes = (
        B5_ROOT
        / "declarations"
        / "solver-convergence-amendment.json"
    ).read_bytes()
    mass_result = mass.evaluate_amended_mass_checks(
        amendment_bytes=amendment_bytes,
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
    )
    trajectory_result = trajectory.evaluate_trajectory_checks(
        amendment_bytes=amendment_bytes,
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
        control_edge_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "control-edge-trajectory-amendment.json"
        ).read_bytes(),
        solver_convergence_bytes=solver_convergence_bytes,
    )

    result = relationships.evaluate_relationship_checks(
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
        mass_result=mass_result,
        probe_catalogue_bytes=(
            B5_ROOT / "declarations" / "w4-probe-catalogue.json"
        ).read_bytes(),
        trajectory_result=trajectory_result,
    )

    assert result["terminal_state"] == "relationship-checks-pass", result
    assert result["first_failure"] == "none"
    assert list(result["checks"]) == [
        "C-R15",
        "C-R16",
        "C-R17",
        "C-R18",
        "C-R19",
        "C-R20",
        "C-R21",
        "C-R22",
        "C-R24",
    ]
    assert all(
        check["outcome"] == "pass"
        for check in result["checks"].values()
    )


def test_real_fixed_member_subset_reaches_applicable_w4_checks_pass() -> None:
    bundle_value = os.environ.get("ASW_B5_FRESH_BUNDLE")
    assert bundle_value, "ASW_B5_FRESH_BUNDLE must name fresh V3 bundle bytes"
    bundle_bytes = _sensitivity_subset(
        Path(bundle_value).read_bytes(),
        case_ids=(
            "G12_CLEAN_ASSESS",
            "G21_OBSTRUCTION_TRIGGER",
        ),
        probe_id="INT.real-subset",
    )
    certifier_result = certification.certify_sensitivity_bundle(
        bundle_bytes,
        (B5_ROOT / "declarations" / "w1-member-authority.json").read_bytes(),
    )

    result = member_evaluation.evaluate_member(
        c_r02_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "w4-c-r02-routing-integration-amendment.json"
        ).read_bytes(),
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certification.certification_result_bytes(
            certifier_result
        ),
        control_edge_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "control-edge-trajectory-amendment.json"
        ).read_bytes(),
        probe_catalogue_bytes=(
            B5_ROOT / "declarations" / "w4-probe-catalogue.json"
        ).read_bytes(),
        solver_convergence_bytes=(
            B5_ROOT
            / "declarations"
            / "solver-convergence-amendment.json"
        ).read_bytes(),
    )

    assert result["terminal_state"] == "w4-checks-pass", result
    assert result["first_failure"] == "none"
    assert result["evaluation_scope"] == "fixed-member-applicable-checks"
    assert result["applied_check_ids"] == [
        "C-R01",
        "C-R02",
        "C-R03",
        "C-R04",
        "C-R05",
        "C-R06",
        "C-R07",
        "C-R08",
        "C-R09",
        "C-R10",
        "C-R11",
        "C-R12",
        "C-R13",
        "C-R14",
        "C-R18",
        "C-R23",
        "C-R24",
    ]
    assert result["promotable"] is False


def test_real_non_anchor_member_uses_relations_not_anchor_witness_classes(
    tmp_path: Path,
) -> None:
    receipt_value = os.environ.get("ASW_B5_ENGINE_RECEIPT")
    assert receipt_value, (
        "ASW_B5_ENGINE_RECEIPT must name the real B5 engine receipt"
    )
    authority_bytes = (
        B5_ROOT / "declarations" / "w1-member-authority.json"
    ).read_bytes()
    probe_bytes = (
        B5_ROOT / "declarations" / "w4-probe-catalogue.json"
    ).read_bytes()
    inventory = family.build_amended_analytical_inventory(
        authority_bytes=authority_bytes,
        probe_catalogue_bytes=probe_bytes,
        selection_amendment_bytes=(
            B5_ROOT
            / "declarations"
            / "family-member-selection-amendment.json"
        ).read_bytes(),
    )
    member_probe = next(
        probe
        for probe in inventory["interactions"]
        if probe["probe_id"] == "INT.01.hydraulic-supporting"
    )
    case_ids = tuple(member_probe["case_ids"])
    generated = execution.execute_member_cases(
        authority_bytes=authority_bytes,
        catalogue_bytes=(
            B5_ROOT / "declarations" / "w2-case-catalogue.json"
        ).read_bytes(),
        case_ids=case_ids,
        member=member_probe["member"],
        receipt_path=Path(receipt_value),
        repair_bytes=(
            B5_ROOT
            / "declarations"
            / "w2-w4-engine-mapping-repair.json"
        ).read_bytes(),
        solver_convergence_bytes=(
            B5_ROOT
            / "declarations"
            / "solver-convergence-amendment.json"
        ).read_bytes(),
        workspace=tmp_path / "non-anchor-engine-runs",
    )
    bundle_bytes = transfer.build_sensitivity_bundle(
        generated,
        case_ids=case_ids,
        probe_id=member_probe["probe_id"],
    )

    result = certification.certify_sensitivity_bundle(
        bundle_bytes,
        authority_bytes,
    )

    assert result["terminal_state"] == "quantitative-pending-w4", result
    assert result["first_failing_stage"] == "w4-tolerance-required"
    assert all(
        check["outcome"] == "satisfied"
        for check in result["checks"]
    )


def test_real_predecessor_rule_reaches_c_r02_numerical_rejection(
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
    retained_summary_bytes = (
        RETAINED_SUCCESSOR / "decision-summary.json"
    ).read_bytes()
    retained_result_bytes = (
        RETAINED_SUCCESSOR / "w4-composition-result.json"
    ).read_bytes()
    assert hashlib.sha256(retained_summary_bytes).hexdigest() == (
        "cca138f1d64cd82284ae740085bda0bbcd775d1399e0df3cd34433c891519b01"
    )
    assert hashlib.sha256(retained_result_bytes).hexdigest() == (
        "f2286ebccca4f198148214b448cb0dae20474c97300ea7af565ed2fc519a263d"
    )
    assert (
        compact / "decision-summary.json"
    ).read_bytes() != retained_summary_bytes
    assert result_bytes != retained_result_bytes
    receipts.validate_receipt_graph(chain)
    assert b"/Users/" not in result_bytes
    assert b"/private/" not in result_bytes
