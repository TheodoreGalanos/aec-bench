# ABOUTME: Specifies fail-closed W4 tolerance composition over independently derived W3 references.
# ABOUTME: Locks the C-R08 hard-ceiling result without fitting a threshold to SWMM output.

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


def test_c_r08_rejection_does_not_depend_on_candidate_residual() -> None:
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
