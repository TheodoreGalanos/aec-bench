# ABOUTME: Specifies W4 outward arithmetic, representation bounds, curve budgets, and result precedence.
# ABOUTME: Locks formula-derived allowances without using candidate output to choose a threshold.

import math
from decimal import Decimal

import pytest
from sensitivity import tolerances


def test_binary32_and_binary64_bounds_match_preregistered_formulas() -> None:
    assert tolerances.binary32_bound(1.0) == 2.0**-24
    assert tolerances.binary32_bound(0.0) == 2.0**-150
    assert tolerances.binary32_bound(0.5) == 2.0**-25
    assert tolerances.binary64_guard(1.0) == 32.0 * math.ulp(1.0)


def test_outward_arithmetic_never_rounds_inward() -> None:
    values = [2.0**-53, 2.0**-53, 0.1]

    result = tolerances.outward_sum(values)

    assert result >= math.fsum(values)
    assert result > 0.1
    assert tolerances.outward_divide(0.0191, 0.001) >= 19.1


def test_curve_head_budget_uses_exact_w1_quadratic_form() -> None:
    result = tolerances.curve_head_bound(
        head_zero_m=Decimal("18.5"),
        obstruction=Decimal("0"),
        clearance_loss=Decimal("0"),
        obstruction_coefficient=Decimal("0.08"),
        clearance_coefficient=Decimal("0.18"),
        segments=32,
    )

    assert result == pytest.approx(0.0045166015625)
    assert (
        tolerances.curve_head_bound(
            head_zero_m=Decimal("18.5"),
            obstruction=Decimal("0"),
            clearance_loss=Decimal("0"),
            obstruction_coefficient=Decimal("0.08"),
            clearance_coefficient=Decimal("0.18"),
            segments=64,
        )
        < result
    )


def test_formula_derived_edge_window_uses_depth_budget_and_independent_slope() -> None:
    result = tolerances.edge_time_window(
        depth_terms_m=[0.001, 0.0009],
        report_step_s=1,
        slope_after_m_s=0.001,
        slope_before_m_s=0.001,
    )

    assert result["depth_budget_m"] >= 0.0019
    assert result["minimum_slope_m_s"] == 0.001
    assert result["window_s"] == 2
    assert result["minimum_report_intervals"] == 1


@pytest.mark.parametrize(
    ("checks", "expected"),
    [
        ([{"terminal_state": "w4-checks-pass"}], "w4-checks-pass"),
        (
            [
                {"terminal_state": "w4-checks-pass"},
                {"terminal_state": "w4-numerical-reject"},
            ],
            "w4-numerical-reject",
        ),
        (
            [
                {"terminal_state": "w4-replay-reject"},
                {"terminal_state": "w4-budget-reject"},
            ],
            "w4-budget-reject",
        ),
    ],
)
def test_generation_state_uses_preregistered_precedence(
    checks: list[dict[str, str]],
    expected: str,
) -> None:
    assert tolerances.generation_state(checks) == expected
