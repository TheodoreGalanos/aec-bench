# ABOUTME: Independently evaluates W1 hydraulics and W4 numerical-reference quantities.
# ABOUTME: Owns roots, slopes, RK4 estimates, settling bounds, and capability margins for W4.

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

GRAVITY_SCALE = 1.0
HYDRAULIC_RESIDUAL = 0.001
MAX_START_DEPTH_ALLOWANCE_M = 0.010068986195609708


class SensitivityPhysicsError(ValueError):
    """Raised when an independent W4 physical calculation is unresolved."""


@dataclass(frozen=True)
class Rk4State:
    """Depth and initial-step operating flow after one fixed-grid advance."""

    depth_m: float
    flow_m3_s: float


def member_values(member: dict[str, Any]) -> dict[str, float]:
    """Return finite non-boolean W1 member values as independent binary64 inputs."""
    values: dict[str, float] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if isinstance(value, bool):
            continue
        number = float(Decimal(str(value)))
        if not math.isfinite(number):
            raise SensitivityPhysicsError("member value is non-finite")
        values[parameter["identity"]] = number
    return values


def wet_well_area(values: dict[str, float]) -> float:
    """Return the exact cylindrical-area expression evaluated in binary64."""
    diameter = values["well.D_w"]
    area = math.pi * diameter * diameter / 4.0
    if not math.isfinite(area) or area <= 0.0:
        raise SensitivityPhysicsError("wet-well area is not positive and finite")
    return area


def pump_support(
    values: dict[str, float],
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Return the positive zero-head support of the W1 quadratic pump curve."""
    numerator = 1.0 - values["mechanism.a_o"] * obstruction - values["mechanism.a_c"] * clearance_loss
    denominator = 1.0 + values["mechanism.b_o"] * obstruction + values["mechanism.b_c"] * clearance_loss
    if numerator <= 0.0 or denominator <= 0.0:
        raise SensitivityPhysicsError("pump support factors are not positive")
    result = values["pump.Q_0"] * math.sqrt(numerator / denominator)
    if not math.isfinite(result) or not 0.0 < result <= values["pump.Q_0"]:
        raise SensitivityPhysicsError("pump support leaves the declared envelope")
    return result


def pump_head(
    values: dict[str, float],
    flow_m3_s: float,
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Evaluate the unfloored W1 head inside the declared pump support."""
    numerator = 1.0 - values["mechanism.a_o"] * obstruction - values["mechanism.a_c"] * clearance_loss
    denominator = 1.0 + values["mechanism.b_o"] * obstruction + values["mechanism.b_c"] * clearance_loss
    ratio = flow_m3_s / values["pump.Q_0"]
    result = values["pump.H_0"] * (numerator - denominator * ratio * ratio)
    if not math.isfinite(result):
        raise SensitivityPhysicsError("pump-head evaluation is non-finite")
    return max(0.0, result)


def reynolds_number(values: dict[str, float], flow_m3_s: float) -> float:
    """Evaluate the W1 full-pipe Reynolds number."""
    if flow_m3_s == 0.0:
        return 0.0
    diameter = values["system.D"]
    velocity = 4.0 * flow_m3_s / (math.pi * diameter * diameter)
    result = values["fluid.rho"] * velocity * diameter / values["fluid.mu"]
    if not math.isfinite(result) or result <= 0.0:
        raise SensitivityPhysicsError("Reynolds number is not positive and finite")
    return result


def system_loss_head(values: dict[str, float], flow_m3_s: float) -> float:
    """Evaluate the W1 Swamee-Jain full-pipe loss expression."""
    if flow_m3_s == 0.0:
        return 0.0
    reynolds = reynolds_number(values, flow_m3_s)
    if reynolds < values["system.Re_min"]:
        raise SensitivityPhysicsError("flow leaves the turbulent envelope")
    diameter = values["system.D"]
    velocity = 4.0 * flow_m3_s / (math.pi * diameter * diameter)
    friction = 0.25 / math.log10(values["system.epsilon"] / (3.7 * diameter) + 5.74 / reynolds**0.9) ** 2
    result = (
        (friction * values["system.L"] / diameter + values["system.K_minor"])
        * velocity
        * velocity
        / (2.0 * values["fluid.g"])
    )
    if not math.isfinite(result) or result < 0.0:
        raise SensitivityPhysicsError("system-loss evaluation is unresolved")
    return result


def system_head(
    values: dict[str, float],
    flow_m3_s: float,
    depth_m: float,
) -> float:
    """Return fixed static lift plus the independent full-pipe loss."""
    return (
        values["system.z_d"]
        - depth_m
        + system_loss_head(
            values,
            flow_m3_s,
        )
    )


def operating_point(
    values: dict[str, float],
    *,
    depth_m: float,
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Solve the strict interior analytical operating point with 128 bisections."""
    lower = 0.0
    upper = pump_support(values, obstruction, clearance_loss)

    def residual(flow: float) -> float:
        return pump_head(
            values,
            flow,
            obstruction,
            clearance_loss,
        ) - system_head(values, flow, depth_m)

    if residual(lower) <= 0.0 or residual(upper) >= 0.0:
        raise SensitivityPhysicsError("operating-point root is not strictly internal")
    for _ in range(128):
        midpoint = (lower + upper) / 2.0
        if residual(midpoint) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    result = (lower + upper) / 2.0
    if not math.isfinite(result) or not lower <= result <= upper:
        raise SensitivityPhysicsError("operating-point bisection is unresolved")
    return result


def root_slope(
    values: dict[str, float],
    *,
    flow_m3_s: float,
    depth_m: float,
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Evaluate the absolute local slope of pump head minus system head."""
    support = pump_support(values, obstruction, clearance_loss)
    step = max(math.ulp(flow_m3_s) * 64.0, support * 1.0e-7)
    lower = max(flow_m3_s - step, math.nextafter(0.0, math.inf))
    upper = min(flow_m3_s + step, math.nextafter(support, 0.0))
    if not lower < upper:
        raise SensitivityPhysicsError("root-slope bracket is unresolved")

    def residual(flow: float) -> float:
        return pump_head(
            values,
            flow,
            obstruction,
            clearance_loss,
        ) - system_head(values, flow, depth_m)

    signed = (residual(upper) - residual(lower)) / (upper - lower)
    result = abs(signed)
    if not math.isfinite(result) or result <= 0.0 or signed >= 0.0:
        raise SensitivityPhysicsError("root slope is non-finite or sign-inconsistent")
    return result


def _derivative(
    values: dict[str, float],
    *,
    clearance_loss: float,
    depth_m: float,
    inflow_m3_s: float,
    obstruction: float,
    running: bool,
) -> tuple[float, float]:
    bounded_depth = min(max(depth_m, 0.0), values["well.h_overflow"])
    flow = (
        operating_point(
            values,
            depth_m=bounded_depth,
            obstruction=obstruction,
            clearance_loss=clearance_loss,
        )
        if running
        else 0.0
    )
    net = inflow_m3_s - flow
    if bounded_depth >= values["well.h_overflow"] and net > 0.0:
        return 0.0, flow
    return net / wet_well_area(values), flow


def _rk4_step(
    values: dict[str, float],
    *,
    clearance_loss: float,
    depth_m: float,
    inflow_m3_s: float,
    obstruction: float,
    running: bool,
    step_s: float,
) -> Rk4State:
    def derivative(depth: float) -> tuple[float, float]:
        return _derivative(
            values,
            clearance_loss=clearance_loss,
            depth_m=depth,
            inflow_m3_s=inflow_m3_s,
            obstruction=obstruction,
            running=running,
        )

    k1, flow = derivative(depth_m)
    k2, _ = derivative(depth_m + step_s * k1 / 2.0)
    k3, _ = derivative(depth_m + step_s * k2 / 2.0)
    k4, _ = derivative(depth_m + step_s * k3)
    updated = depth_m + step_s * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if not math.isfinite(updated) or updated < 0.0 or updated > values["well.h_overflow"]:
        raise SensitivityPhysicsError("RK4 trajectory leaves the storage envelope")
    return Rk4State(updated, flow)


def rk4_advance(
    values: dict[str, float],
    *,
    clearance_loss: float,
    depth_m: float,
    duration_s: float,
    inflow_m3_s: float,
    obstruction: float,
    running: bool,
    step_s: float,
) -> Rk4State:
    """Advance an exact duration on a fixed RK4 grid without candidate anchoring."""
    if not math.isfinite(duration_s) or not math.isfinite(step_s) or duration_s <= 0.0 or step_s <= 0.0:
        raise SensitivityPhysicsError("RK4 duration and step must be positive")
    count = round(duration_s / step_s)
    if count <= 0 or not math.isclose(
        count * step_s,
        duration_s,
        rel_tol=0.0,
        abs_tol=math.ulp(duration_s) * 4.0,
    ):
        raise SensitivityPhysicsError("RK4 step does not divide duration")
    current = depth_m
    first_flow = 0.0
    for index in range(count):
        state = _rk4_step(
            values,
            clearance_loss=clearance_loss,
            depth_m=current,
            inflow_m3_s=inflow_m3_s,
            obstruction=obstruction,
            running=running,
            step_s=step_s,
        )
        if index == 0:
            first_flow = state.flow_m3_s
        current = state.depth_m
    return Rk4State(current, first_flow)


def dynamic_settling(
    values: dict[str, float],
    *,
    flow_m3_s: float,
    depth_m: float,
    obstruction: float,
    clearance_loss: float,
    report_step_s: int,
) -> dict[str, float | int]:
    """Return the preregistered first-order hydraulic settling allowances."""
    if report_step_s <= 0:
        raise SensitivityPhysicsError("report step must be positive")
    slope = root_slope(
        values,
        flow_m3_s=flow_m3_s,
        depth_m=depth_m,
        obstruction=obstruction,
        clearance_loss=clearance_loss,
    )
    pipe_area = math.pi * values["system.D"] ** 2 / 4.0
    time_constant = values["system.L"] / (values["fluid.g"] * pipe_area * slope) * GRAVITY_SCALE
    if not math.isfinite(time_constant) or time_constant <= 0.0:
        raise SensitivityPhysicsError("hydraulic time constant is unresolved")
    settling_time = math.ceil(-math.log(HYDRAULIC_RESIDUAL) * time_constant / report_step_s) * report_step_s
    depth_allowance = flow_m3_s * time_constant / wet_well_area(values)
    if depth_allowance > MAX_START_DEPTH_ALLOWANCE_M:
        raise SensitivityPhysicsError("per-start dynamic depth allowance exceeds ceiling")
    return {
        "depth_allowance_m": depth_allowance,
        "flow_allowance_m3_s": HYDRAULIC_RESIDUAL * flow_m3_s,
        "settling_time_s": settling_time,
        "time_constant_s": time_constant,
    }


def capability_interval(
    values: dict[str, float],
    *,
    flow_m3_s: float,
    flow_bound_m3_s: float,
    report_step_s: int,
) -> dict[str, float | str]:
    """Classify W4 capability with outward flow and the exact time margin."""
    if not math.isfinite(flow_bound_m3_s) or flow_bound_m3_s < 0.0:
        raise SensitivityPhysicsError("capability flow bound is invalid")
    low_net = flow_m3_s - flow_bound_m3_s - values["inflow.Q_assess"]
    high_net = flow_m3_s + flow_bound_m3_s - values["inflow.Q_assess"]
    working_volume = wet_well_area(values) * (values["well.h_start"] - values["well.h_stop"])
    draw_low = math.inf if high_net <= 0.0 else working_volume / high_net
    draw_high = math.inf if low_net <= 0.0 else working_volume / low_net
    limit = values["capability.t_draw_limit"]
    margin = max(float(report_step_s), 0.01 * limit)
    if draw_high <= limit - margin:
        classification = "capable"
    elif draw_low >= limit + margin:
        classification = "review-eligible"
    else:
        classification = "boundary-fragile"
    return {
        "classification": classification,
        "drawdown_high_s": draw_high,
        "drawdown_low_s": draw_low,
        "margin_s": margin,
        "net_flow_high_m3_s": high_net,
        "net_flow_low_m3_s": low_net,
    }
