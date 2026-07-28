# ABOUTME: Specifies predecessor and amended W4 C-R08 composition over independent W3 references.
# ABOUTME: Keeps the first refusal immutable while testing separate dynamic and numerical ceilings.

from pathlib import Path

from sensitivity import members, physics

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def _anchor_values():
    authority = members.read_w1_authority(W1_DECLARATION.read_bytes())
    return physics.member_values(members.build_member(authority, {}))


def test_c_r08_minimum_budget_exceeds_its_relative_hard_ceiling() -> None:
    from sensitivity import composition

    values = _anchor_values()
    flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )

    budget = composition.root_flow_budget_lower_bound(
        values,
        candidate_flow_m3_s=flow,
        clearance_loss=0.0,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        reference_flow_m3_s=flow,
    )

    assert budget["terms"]["dynamic_flow_m3_s"] == 0.001 * flow
    assert budget["derived_lower_bound_m3_s"] > budget["relative_hard_ceiling_m3_s"]
    assert budget["outcome"] == "w4-budget-reject"
    assert budget["first_failure"] == ("C-R08-derived-budget-lower-bound-exceeds-relative-ceiling")


def test_predecessor_c_r08_rejection_does_not_depend_on_candidate_residual() -> None:
    from sensitivity import composition

    values = _anchor_values()
    flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )

    matched = composition.root_flow_budget_lower_bound(
        values,
        candidate_flow_m3_s=flow,
        clearance_loss=0.0,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        reference_flow_m3_s=flow,
    )
    perturbed = composition.root_flow_budget_lower_bound(
        values,
        candidate_flow_m3_s=flow + 0.0001,
        clearance_loss=0.0,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        reference_flow_m3_s=flow,
    )

    assert matched["outcome"] == perturbed["outcome"] == "w4-budget-reject"
    assert matched["relative_hard_ceiling_m3_s"] == perturbed["relative_hard_ceiling_m3_s"]


def test_amended_c_r08_ceilings_dynamic_and_numerical_terms_separately() -> None:
    from sensitivity import composition

    values = _anchor_values()
    flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )

    budget = composition.amended_root_flow_budget(
        values,
        candidate_flow_m3_s=flow,
        clearance_loss=0.0,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        raw_residual_m3_s=0.0,
        reference_flow_m3_s=flow,
        system_render_head_m=0.0,
    )

    assert budget["terms"]["dynamic_flow_m3_s"] == 0.001 * flow
    assert budget["numerical_allowance_m3_s"] < budget["hard_ceiling_m3_s"]
    assert budget["dynamic_allowance_m3_s"] <= budget["hard_ceiling_m3_s"]
    assert budget["total_allowance_m3_s"] > budget["hard_ceiling_m3_s"]
    assert budget["outcome"] == "c-r08-checks-pass"
    assert budget["first_failure"] == "none"


def test_amended_c_r08_rejects_numerical_budget_before_residual() -> None:
    from sensitivity import composition

    values = _anchor_values()
    flow = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        clearance_loss=0.0,
    )

    budget = composition.amended_root_flow_budget(
        values,
        candidate_flow_m3_s=flow,
        clearance_loss=0.0,
        curve_segments=1,
        depth_m=values["well.h_start"],
        obstruction=0.0,
        raw_residual_m3_s=0.0,
        reference_flow_m3_s=flow,
        system_render_head_m=0.0,
    )

    assert budget["outcome"] == "w4-budget-reject"
    assert budget["first_failure"] == (
        "C-R08-numerical-allowance-exceeds-hard-ceiling"
    )


def test_amended_c_r07_owns_curve_and_render_terms_for_paired_closure() -> None:
    from sensitivity import composition

    values = _anchor_values()
    result = composition.amended_net_head_budget(
        values,
        clearance_loss=0.0,
        discharge_head_m=8.399999618530273,
        obstruction=0.0,
        raw_residual_m=-0.00421556151771885,
        system_render_head_m=0.0,
        wet_well_head_m=1.6193158626556396,
    )

    assert result["terms"]["curve_head_m"] > abs(
        result["raw_residual_m"]
    )
    assert result["derived_allowance_m"] < result["hard_ceiling_m"]
    assert result["outcome"] == "c-r07-checks-pass"
    assert result["first_failure"] == "none"


def test_amended_c_r07_rejects_derived_budget_before_residual() -> None:
    from sensitivity import composition

    values = _anchor_values()
    result = composition.amended_net_head_budget(
        values,
        clearance_loss=0.0,
        curve_segments=1,
        discharge_head_m=8.399999618530273,
        obstruction=0.0,
        raw_residual_m=0.0,
        system_render_head_m=0.0,
        wet_well_head_m=1.6193158626556396,
    )

    assert result["outcome"] == "w4-budget-reject"
    assert result["first_failure"] == (
        "C-R07-derived-allowance-exceeds-head-ceiling"
    )
