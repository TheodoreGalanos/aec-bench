# ABOUTME: Specifies deterministic W4 analytical inventory and rejected-family aggregation.
# ABOUTME: Retains every planned probe while stopping engine work after an anchor budget rejection.

from pathlib import Path

import pytest
from sensitivity import catalogue, family

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
PROBE_DECLARATION = B5_ROOT / "declarations" / "w4-probe-catalogue.json"


def test_analytical_inventory_retains_complete_probe_and_grid_plan() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    assert len(inventory["oat"]) == 68
    assert len(inventory["interactions"]) == 5
    assert [item["probe_id"] for item in inventory["boundaries"]] == [f"BND.{index:02d}" for index in range(11)]
    assert inventory["grid_cardinalities"] == {
        "flow_observation": 9,
        "intervention": 3,
        "level_observation": 9,
        "progression": 3,
        "resource": 5,
        "runtime_observation": 3,
    }
    assert len(inventory["engine_variants"]) == 7
    assert len(inventory["mutation_ids"]) == 30
    assert all(item["promotable"] is False for item in inventory["oat"])


def test_anchor_budget_rejection_freezes_family_without_running_siblings() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    result = family.freeze_family_decision(
        analytical_inventory=inventory,
        composition_result_content_id="1" * 64,
        composition_terminal_state="w4-budget-reject",
        composition_first_failure=("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling"),
    )

    assert result["terminal_state"] == "family-member-reject"
    assert result["first_failure"] == "anchor-w4-budget-reject"
    assert result["promotable"] is False
    assert result["execution"]["anchor"] == "w4-budget-reject"
    assert result["execution"]["downstream"] == ("not-executed-after-anchor-rejection")
    assert result["result_content_id"]
    assert family.family_result_bytes(result) == catalogue.canonical_json_bytes(result)


def test_successor_numerical_rejection_freezes_family_without_siblings() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    result = family.freeze_family_decision(
        analytical_inventory=inventory,
        composition_result_content_id="1" * 64,
        composition_terminal_state="w4-numerical-reject",
        composition_first_failure="C-R02-corrected-residual",
    )

    assert result["terminal_state"] == "family-member-reject"
    assert result["first_failure"] == "anchor-w4-numerical-reject"
    assert result["execution"]["anchor"] == "w4-numerical-reject"
    assert result["execution"]["ordered_stop_owner"] == (
        "C-R02-corrected-residual"
    )


def test_family_decision_refuses_non_rejection_or_bad_identity() -> None:
    inventory = family.build_analytical_inventory(
        authority_bytes=W1_DECLARATION.read_bytes(),
        probe_catalogue_bytes=PROBE_DECLARATION.read_bytes(),
    )

    with pytest.raises(family.FamilyDecisionError, match="anchor rejection"):
        family.freeze_family_decision(
            analytical_inventory=inventory,
            composition_result_content_id="1" * 64,
            composition_terminal_state="w4-checks-pass",
            composition_first_failure="none",
        )
    with pytest.raises(family.FamilyDecisionError, match="content identity"):
        family.freeze_family_decision(
            analytical_inventory=inventory,
            composition_result_content_id="bad",
            composition_terminal_state="w4-budget-reject",
            composition_first_failure=("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling"),
        )
