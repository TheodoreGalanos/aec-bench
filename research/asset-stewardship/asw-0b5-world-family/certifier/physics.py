# ABOUTME: Implements the certifier-owned W1 hydraulic equations, roots, curves, and trajectory calculations.
# ABOUTME: Uses only standard-library arithmetic and never imports generator, SWMM, or candidate-derived helpers.

from __future__ import annotations

import hashlib
import math
import struct
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from certifier import boundary

PI_DECIMAL = Decimal("3.141592653589793238462643383279503")
PI_FLOAT = math.pi
HEAD_QUANTUM = Decimal("0.000000001")
FLOW_QUANTUM = Decimal("0.000001")


class PhysicsError(ValueError):
    """Raised when a W1 member cannot support independent certification."""


def member_values(member: dict[str, Any]) -> dict[str, Decimal]:
    """Return exact Decimal values for every non-boolean W1 parameter."""
    values: dict[str, Decimal] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if not isinstance(value, bool):
            values[parameter["identity"]] = Decimal(str(value))
    return values


def validate_member(
    member: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Decimal]:
    """Independently enforce W1 order, units, bounds, fixed values, and composites."""
    supplied = member["parameters"]
    declared = authority["parameters"]
    if not isinstance(supplied, list) or len(supplied) != len(declared):
        raise PhysicsError("member parameter inventory differs")
    for actual, expected in zip(supplied, declared, strict=True):
        if not isinstance(actual, dict) or set(actual) != {"identity", "unit", "value"}:
            raise PhysicsError("member parameter shape differs")
        if actual["identity"] != expected["identity"] or actual["unit"] != expected["unit"]:
            raise PhysicsError("member identity, order, or unit differs")
        value = actual["value"]
        if expected["value_kind"] == "boolean":
            if not isinstance(value, bool):
                raise PhysicsError("boolean member value differs")
            if expected["fixed"] and value != expected["anchor"]:
                raise PhysicsError("fixed boolean member value differs")
            continue
        if expected["value_kind"] == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise PhysicsError("integer member value differs")
            number = Decimal(value)
        else:
            if not isinstance(value, str) or boundary.CANONICAL_DECIMAL.fullmatch(value) is None:
                raise PhysicsError("decimal member value is not canonical")
            number = Decimal(value)
        lower = Decimal(str(expected["lower"]))
        upper = Decimal(str(expected["upper"]))
        if not lower <= number <= upper:
            raise PhysicsError(f"{expected['identity']} leaves its inclusive bounds")
        if expected["fixed"] and number != Decimal(str(expected["anchor"])):
            raise PhysicsError(f"{expected['identity']} fixed value differs")
    if member["composites"] != authority["composites"]:
        raise PhysicsError("member composite inventory differs")
    values = member_values(member)
    levels = [values[f"well.{name}"] for name in ("h_stop", "h_start", "h_high", "h_overflow")]
    inflows = [values[f"inflow.{name}"] for name in ("Q_low", "Q_nominal", "Q_assess")]
    if not Decimal(0) < levels[0] < levels[1] < levels[2] < levels[3]:
        raise PhysicsError("W1 level ordering differs")
    if not Decimal(0) <= inflows[0] < inflows[1] < inflows[2]:
        raise PhysicsError("W1 inflow ordering differs")
    return values


def wet_well_area(values: dict[str, Decimal]) -> float:
    """Return cylindrical wet-well area in square metres."""
    diameter = float(values["well.D_w"])
    return PI_FLOAT * diameter * diameter / 4.0


def pump_head(
    values: dict[str, Decimal],
    flow_m3_s: float,
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Evaluate the analytical W1 pump head with its exact zero floor."""
    a_value = (
        1.0
        - float(values["mechanism.a_o"]) * obstruction
        - float(values["mechanism.a_c"]) * clearance_loss
    )
    b_value = (
        1.0
        + float(values["mechanism.b_o"]) * obstruction
        + float(values["mechanism.b_c"]) * clearance_loss
    )
    if a_value <= 0.0 or b_value <= 0.0:
        raise PhysicsError("pump support factors must be positive")
    ratio = flow_m3_s / float(values["pump.Q_0"])
    return max(0.0, float(values["pump.H_0"]) * (a_value - b_value * ratio * ratio))


def support_flow(
    values: dict[str, Decimal],
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Return the analytical W1 zero-head support flow."""
    a_value = (
        1.0
        - float(values["mechanism.a_o"]) * obstruction
        - float(values["mechanism.a_c"]) * clearance_loss
    )
    b_value = (
        1.0
        + float(values["mechanism.b_o"]) * obstruction
        + float(values["mechanism.b_c"]) * clearance_loss
    )
    if a_value <= 0.0 or b_value <= 0.0:
        raise PhysicsError("pump support factors must be positive")
    result = float(values["pump.Q_0"]) * math.sqrt(a_value / b_value)
    if not 0.0 < result <= float(values["pump.Q_0"]):
        raise PhysicsError("pump support leaves the W1 envelope")
    return result


def system_loss_head(values: dict[str, Decimal], flow_m3_s: float) -> float:
    """Evaluate velocity-dependent W1 system loss, with zero-flow branching first."""
    if flow_m3_s == 0.0:
        return 0.0
    diameter = float(values["system.D"])
    velocity = 4.0 * flow_m3_s / (PI_FLOAT * diameter * diameter)
    reynolds = (
        float(values["fluid.rho"])
        * velocity
        * diameter
        / float(values["fluid.mu"])
    )
    if reynolds < 4000.0:
        raise PhysicsError("positive operating flow leaves the turbulent envelope")
    friction = 0.25 / (
        math.log10(
            float(values["system.epsilon"]) / (3.7 * diameter)
            + 5.74 / reynolds**0.9
        )
        ** 2
    )
    velocity_head = velocity * velocity / (2.0 * float(values["fluid.g"]))
    return (
        friction * float(values["system.L"]) / diameter
        + float(values["system.K_minor"])
    ) * velocity_head


def reynolds_number(values: dict[str, Decimal], flow_m3_s: float) -> float:
    """Return the full-pipe Reynolds number without consulting engine output."""
    if flow_m3_s == 0.0:
        return 0.0
    diameter = float(values["system.D"])
    velocity = 4.0 * flow_m3_s / (PI_FLOAT * diameter * diameter)
    return (
        float(values["fluid.rho"])
        * velocity
        * diameter
        / float(values["fluid.mu"])
    )


def system_head(
    values: dict[str, Decimal],
    flow_m3_s: float,
    depth_m: float,
) -> float:
    """Evaluate static plus velocity-dependent W1 system head."""
    return (
        float(values["system.z_d"])
        - depth_m
        + system_loss_head(values, flow_m3_s)
    )


def operating_point(
    values: dict[str, Decimal],
    depth_m: float,
    obstruction: float,
    clearance_loss: float,
) -> float:
    """Solve the unique W1 operating point by exactly 128 bisection iterations."""
    lower = 0.0
    upper = support_flow(values, obstruction, clearance_loss)

    def residual(flow: float) -> float:
        return pump_head(
            values,
            flow,
            obstruction,
            clearance_loss,
        ) - system_head(values, flow, depth_m)

    if residual(lower) <= 0.0 or residual(upper) >= 0.0:
        raise PhysicsError("operating-point root is not strictly internal")
    for _ in range(128):
        midpoint = (lower + upper) / 2.0
        if residual(midpoint) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def capability(
    values: dict[str, Decimal],
    obstruction: float,
    clearance_loss: float,
) -> dict[str, float | bool]:
    """Evaluate the W1 capability review predicate at exact h_start."""
    flow = operating_point(
        values,
        float(values["well.h_start"]),
        obstruction,
        clearance_loss,
    )
    net_flow = flow - float(values["inflow.Q_assess"])
    working_volume = wet_well_area(values) * float(
        values["well.h_start"] - values["well.h_stop"]
    )
    drawdown = math.inf if net_flow <= 0.0 else working_volume / net_flow
    return {
        "drawdown_s": drawdown,
        "operating_flow_m3_s": flow,
        "review_predicate": (
            net_flow <= 0.0
            or drawdown > float(values["capability.t_draw_limit"])
        ),
    }


def _decimal_pump_head(
    values: dict[str, Decimal],
    flow: Decimal,
    obstruction: Decimal,
    clearance: Decimal,
) -> Decimal:
    ratio = flow / values["pump.Q_0"]
    return values["pump.H_0"] * (
        Decimal(1)
        - values["mechanism.a_o"] * obstruction
        - values["mechanism.a_c"] * clearance
        - (
            Decimal(1)
            + values["mechanism.b_o"] * obstruction
            + values["mechanism.b_c"] * clearance
        )
        * ratio
        * ratio
    )


def _decimal_loss_head(values: dict[str, Decimal], flow: Decimal) -> Decimal:
    if flow == 0:
        return Decimal(0)
    velocity = Decimal(4) * flow / (PI_DECIMAL * values["system.D"] ** 2)
    reynolds = values["fluid.rho"] * velocity * values["system.D"] / values["fluid.mu"]
    friction = Decimal("0.25") / (
        values["system.epsilon"] / (Decimal("3.7") * values["system.D"])
        + Decimal("5.74") / (reynolds ** Decimal("0.9"))
    ).log10() ** 2
    velocity_head = velocity * velocity / (Decimal(2) * values["fluid.g"])
    return (
        friction * values["system.L"] / values["system.D"]
        + values["system.K_minor"]
    ) * velocity_head


def reconstruct_curve(
    values: dict[str, Decimal],
    *,
    clearance_loss: str,
    obstruction: str,
    representation: str,
    segment_count: int = 32,
) -> dict[str, Any]:
    """Independently reconstruct exact canonical original or net-head curve bytes."""
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        obstruction_value = Decimal(obstruction)
        clearance_value = Decimal(clearance_loss)
        if representation == "asw-0b4.pump3-curve.v1":
            a_value = (
                Decimal(1)
                - values["mechanism.a_o"] * obstruction_value
                - values["mechanism.a_c"] * clearance_value
            )
            b_value = (
                Decimal(1)
                + values["mechanism.b_o"] * obstruction_value
                + values["mechanism.b_c"] * clearance_value
            )
            support = values["pump.Q_0"] * (a_value / b_value).sqrt()

            def head_for(flow: Decimal) -> Decimal:
                return values["pump.H_0"] * (
                    a_value
                    - b_value * (flow / values["pump.Q_0"]) ** 2
                )

        elif representation == "asw-0b5.net-head-pump3-curve.v1":
            lower = Decimal(0)
            upper = values["pump.Q_0"]

            def head_for(flow: Decimal) -> Decimal:
                return _decimal_pump_head(
                    values,
                    flow,
                    obstruction_value,
                    clearance_value,
                ) - _decimal_loss_head(values, flow)

            if head_for(lower) <= 0 or head_for(upper) >= 0:
                raise PhysicsError("net-head support root is not strictly internal")
            for _ in range(160):
                midpoint = (lower + upper) / 2
                if head_for(midpoint) > 0:
                    lower = midpoint
                else:
                    upper = midpoint
            support = (lower + upper) / 2
        else:
            raise PhysicsError(f"unknown curve representation {representation!r}")
        points: list[dict[str, str]] = []
        for index in range(segment_count + 1):
            flow = support * (Decimal(1) - Decimal(index) / segment_count)
            head = head_for(flow)
            if index == 0:
                head = Decimal(0)
            if index == segment_count:
                flow = Decimal(0)
            points.append(
                {
                    "flow_lps": format(
                        (flow * 1000).quantize(FLOW_QUANTUM),
                        ".6f",
                    ),
                    "head_m": format(head.quantize(HEAD_QUANTUM), ".9f"),
                }
            )
    return {
        "point_count": len(points),
        "points": points,
        "representation": representation,
    }


def curve_sha256(value: dict[str, Any]) -> str:
    """Return independent exact curve-byte identity."""
    return hashlib.sha256(boundary.canonical_json_bytes(value)).hexdigest()


def round_binary32(value: float) -> float:
    """Round one finite binary64 value to canonical IEEE-754 binary32."""
    if not math.isfinite(value):
        raise PhysicsError("binary32 value must be finite")
    try:
        rounded = float(struct.unpack(">f", struct.pack(">f", value))[0])
    except OverflowError as error:
        raise PhysicsError("binary32 value must be finite") from error
    return 0.0 if rounded == 0.0 else rounded


def binary32_hex(value: float) -> str:
    """Encode one independently rounded binary32 as lower-case big-endian hex."""
    return struct.pack(">f", round_binary32(value)).hex()


def quantize_half_up(value: Decimal, resolution: Decimal) -> Decimal:
    """Apply W3's non-negative ROUND_HALF_UP observation quantizer."""
    return resolution * (value / resolution).quantize(
        Decimal(1),
        rounding=ROUND_HALF_UP,
    )


def _hydraulic_derivative(
    values: dict[str, Decimal],
    *,
    clearance_loss: float,
    depth_m: float,
    inflow_m3_s: float,
    obstruction: float,
    running: bool,
) -> tuple[float, float]:
    area = wet_well_area(values)
    pump_flow = (
        operating_point(values, depth_m, obstruction, clearance_loss)
        if running
        else 0.0
    )
    net = inflow_m3_s - pump_flow
    overflow_depth = float(values["well.h_overflow"])
    if depth_m >= overflow_depth and net > 0.0:
        return 0.0, pump_flow
    return net / area, pump_flow


def rk4_interval(
    values: dict[str, Decimal],
    *,
    clearance_loss: float,
    depth_m: float,
    inflow_m3_s: float,
    obstruction: float,
    running: bool,
) -> tuple[float, float]:
    """Advance one exact one-second W3 RK4 interval."""

    def derivative(depth: float) -> tuple[float, float]:
        bounded = min(max(depth, 0.0), float(values["well.h_overflow"]))
        return _hydraulic_derivative(
            values,
            clearance_loss=clearance_loss,
            depth_m=bounded,
            inflow_m3_s=inflow_m3_s,
            obstruction=obstruction,
            running=running,
        )

    k1, flow1 = derivative(depth_m)
    k2, _ = derivative(depth_m + k1 / 2.0)
    k3, _ = derivative(depth_m + k2 / 2.0)
    k4, _ = derivative(depth_m + k3)
    updated = depth_m + (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if updated < 0.0 or updated > float(values["well.h_overflow"]):
        raise PhysicsError("RK4 trajectory leaves the W1 storage envelope")
    return updated, flow1
