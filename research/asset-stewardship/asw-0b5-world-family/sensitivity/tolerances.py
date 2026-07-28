# ABOUTME: Implements W4-owned outward numerical bounds and generation-state precedence.
# ABOUTME: Contains no candidate-fitted constants, generator calls, certifier helpers, or promotion decisions.

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

GENERATION_STATES = (
    "w4-input-reject",
    "w4-exact-reject",
    "w4-budget-reject",
    "w4-numerical-reject",
    "w4-qualitative-reject",
    "w4-boundary-fragile",
    "w4-replay-reject",
    "w4-checks-pass",
    "w4-internal-error",
)


class ToleranceError(ValueError):
    """Raised when a W4 bound cannot be constructed outward and finitely."""


def _finite_nonnegative(value: float, name: str) -> float:
    if not math.isfinite(value) or value < 0.0:
        raise ToleranceError(f"{name} must be finite and non-negative")
    return value


def binary32_bound(value: float) -> float:
    """Return the preregistered half-ULP representation bound."""
    if not math.isfinite(value):
        raise ToleranceError("binary32 value must be finite")
    magnitude = abs(value)
    if magnitude == 0.0 or magnitude < 2.0**-126:
        return 2.0**-150
    exponent = math.floor(math.log2(magnitude))
    return 2.0 ** (exponent - 24)


def binary64_guard(value: float) -> float:
    """Return the fixed 32-ULP direct-expression guard at unit scale."""
    if not math.isfinite(value):
        raise ToleranceError("binary64 scale must be finite")
    return 32.0 * math.ulp(max(abs(value), 1.0))


def outward_sum(values: list[float]) -> float:
    """Sum finite non-negative terms and round once toward positive infinity."""
    checked = [_finite_nonnegative(value, f"term-{index}") for index, value in enumerate(values)]
    result = math.fsum(checked)
    if not math.isfinite(result):
        raise ToleranceError("outward sum is non-finite")
    if result == 0.0:
        return 0.0
    return math.nextafter(result, math.inf)


def outward_divide(numerator: float, denominator: float) -> float:
    """Divide positive finite terms and round toward positive infinity."""
    _finite_nonnegative(numerator, "numerator")
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise ToleranceError("denominator must be finite and positive")
    result = numerator / denominator
    if not math.isfinite(result):
        raise ToleranceError("outward quotient is non-finite")
    if result == 0.0:
        return 0.0
    return math.nextafter(result, math.inf)


def curve_head_bound(
    *,
    head_zero_m: Decimal,
    obstruction: Decimal,
    clearance_loss: Decimal,
    obstruction_coefficient: Decimal,
    clearance_coefficient: Decimal,
    segments: int,
) -> float:
    """Return H0*A/(4*N^2) for the declared quadratic pump curve."""
    if segments <= 0:
        raise ToleranceError("curve segment count must be positive")
    factor = Decimal(1) - obstruction_coefficient * obstruction - clearance_coefficient * clearance_loss
    if factor <= 0:
        raise ToleranceError("curve support factor must be positive")
    result = head_zero_m * factor / (Decimal(4) * segments * segments)
    return float(result)


def edge_time_window(
    *,
    depth_terms_m: list[float],
    report_step_s: int,
    slope_after_m_s: float,
    slope_before_m_s: float,
) -> dict[str, int | float]:
    """Convert the repaired outward edge-depth uncertainty to report-grid time."""
    if report_step_s <= 0:
        raise ToleranceError("report step must be positive")
    slopes = [slope for slope in (slope_before_m_s, slope_after_m_s) if math.isfinite(slope) and slope > 0.0]
    if not slopes:
        raise ToleranceError("edge requires a positive independent slope")
    depth_budget = outward_sum(depth_terms_m)
    minimum_slope = min(slopes)
    time_budget = outward_divide(depth_budget, minimum_slope)
    intervals = max(1, math.ceil(time_budget / report_step_s))
    return {
        "depth_budget_m": depth_budget,
        "minimum_report_intervals": 1,
        "minimum_slope_m_s": minimum_slope,
        "time_budget_s": time_budget,
        "window_s": intervals * report_step_s,
    }


def generation_state(checks: list[dict[str, Any]]) -> str:
    """Return the first preregistered terminal state represented by checks."""
    states = [check.get("terminal_state") for check in checks]
    if any(state == "w4-internal-error" for state in states):
        return "w4-internal-error"
    for state in GENERATION_STATES[:-1]:
        if state in states:
            return state
    raise ToleranceError("no recognized generation state")
