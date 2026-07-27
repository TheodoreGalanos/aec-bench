# ABOUTME: Materializes the W1 combined pump equation as deterministic 33-point W2 PUMP3 curves.
# ABOUTME: Owns generator-side Decimal arithmetic, endpoint treatment, quantization, and curve-byte identity only.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from generator.request import canonical_json_bytes

HEAD_QUANTUM = Decimal("0.000000001")
FLOW_QUANTUM = Decimal("0.000001")
PI = Decimal("3.141592653589793238462643383279503")
ORIGINAL_CURVE_REPRESENTATION = "asw-0b4.pump3-curve.v1"
NET_HEAD_CURVE_REPRESENTATION = "asw-0b5.net-head-pump3-curve.v1"


class CurveMaterializationError(ValueError):
    """Raised when a W1 state cannot produce the exact W2 curve form."""


@dataclass(frozen=True)
class CurvePoint:
    """One quantized PUMP3 point in SWMM head-flow order."""

    head_m: Decimal
    flow_lps: Decimal


def _values(member: dict[str, Any]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if isinstance(value, bool):
            continue
        result[parameter["identity"]] = Decimal(value) if isinstance(value, str) else Decimal(value)
    return result


def materialize(
    member: dict[str, Any],
    *,
    obstruction: str,
    clearance_loss: str,
) -> tuple[CurvePoint, ...]:
    """Compile one fixed pump state to the W2 32-segment reference curve."""
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        values = _values(member)
        o = Decimal(obstruction)
        c = Decimal(clearance_loss)
        if not Decimal(0) <= o <= Decimal(1) or not Decimal(0) <= c <= Decimal(1):
            raise CurveMaterializationError("severity must remain inside [0, 1]")
        a_value = Decimal(1) - values["mechanism.a_o"] * o - values["mechanism.a_c"] * c
        b_value = Decimal(1) + values["mechanism.b_o"] * o + values["mechanism.b_c"] * c
        if a_value <= 0 or b_value <= 0:
            raise CurveMaterializationError("curve support factors must be positive")
        support = values["pump.Q_0"] * (a_value / b_value).sqrt()
        points: list[CurvePoint] = []
        for index in range(33):
            flow = support * (Decimal(1) - Decimal(index) / 32)
            head = values["pump.H_0"] * (
                a_value - b_value * (flow / values["pump.Q_0"]) ** 2
            )
            if index == 0:
                head = Decimal(0)
            if index == 32:
                flow = Decimal(0)
            points.append(
                CurvePoint(
                    head_m=head.quantize(HEAD_QUANTUM),
                    flow_lps=(flow * 1000).quantize(FLOW_QUANTUM),
                )
            )
    if len(points) != 33:
        raise CurveMaterializationError("curve point count differs")
    if any(
        left.head_m >= right.head_m
        for left, right in zip(points, points[1:], strict=False)
    ):
        raise CurveMaterializationError("quantized curve heads are not strictly increasing")
    if any(
        left.flow_lps < right.flow_lps
        for left, right in zip(points, points[1:], strict=False)
    ):
        raise CurveMaterializationError("quantized curve flows increase")
    return tuple(points)


def _pump_head(
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


def _system_loss_head(values: dict[str, Decimal], flow: Decimal) -> Decimal:
    if flow == 0:
        return Decimal(0)
    velocity = Decimal(4) * flow / (PI * values["system.D"] ** 2)
    reynolds = values["fluid.rho"] * velocity * values["system.D"] / values["fluid.mu"]
    friction = Decimal("0.25") / (
        values["system.epsilon"] / (Decimal("3.7") * values["system.D"])
        + Decimal("5.74") / (reynolds ** Decimal("0.9"))
    ).log10() ** 2
    velocity_head = velocity * velocity / (Decimal(2) * values["fluid.g"])
    return (
        friction * (values["system.L"] / values["system.D"])
        + values["system.K_minor"]
    ) * velocity_head


def materialize_net_head(
    member: dict[str, Any],
    *,
    obstruction: str,
    clearance_loss: str,
    segment_count: int = 32,
) -> tuple[CurvePoint, ...]:
    """Compile the repaired engine-only net-head curve from the W1 equations."""
    if segment_count <= 0:
        raise CurveMaterializationError("segment count must be positive")
    with localcontext() as context:
        context.prec = 34
        context.rounding = ROUND_HALF_EVEN
        values = _values(member)
        obstruction_value = Decimal(obstruction)
        clearance_value = Decimal(clearance_loss)
        if (
            not Decimal(0) <= obstruction_value <= Decimal(1)
            or not Decimal(0) <= clearance_value <= Decimal(1)
        ):
            raise CurveMaterializationError("severity must remain inside [0, 1]")

        def residual(flow: Decimal) -> Decimal:
            return _pump_head(
                values,
                flow,
                obstruction_value,
                clearance_value,
            ) - _system_loss_head(values, flow)

        lower = Decimal(0)
        upper = values["pump.Q_0"]
        if residual(lower) <= 0 or residual(upper) >= 0:
            raise CurveMaterializationError("net-head support root is not strictly internal")
        for _ in range(160):
            midpoint = (lower + upper) / 2
            if residual(midpoint) > 0:
                lower = midpoint
            else:
                upper = midpoint
        support = (lower + upper) / 2
        points: list[CurvePoint] = []
        for index in range(segment_count + 1):
            flow = support * (Decimal(1) - Decimal(index) / segment_count)
            head = residual(flow)
            if index == 0:
                head = Decimal(0)
            if index == segment_count:
                flow = Decimal(0)
            points.append(
                CurvePoint(
                    head_m=head.quantize(HEAD_QUANTUM),
                    flow_lps=(flow * 1000).quantize(FLOW_QUANTUM),
                )
            )
    if len(points) != segment_count + 1:
        raise CurveMaterializationError("curve point count differs")
    if any(
        left.head_m >= right.head_m
        for left, right in zip(points, points[1:], strict=False)
    ):
        raise CurveMaterializationError("quantized net-head curve is not strictly increasing")
    if any(
        left.flow_lps < right.flow_lps
        for left, right in zip(points, points[1:], strict=False)
    ):
        raise CurveMaterializationError("quantized net-head curve flows increase")
    return tuple(points)


def _canonical_curve_bytes(
    points: tuple[CurvePoint, ...],
    representation: str,
) -> bytes:
    payload = {
        "point_count": len(points),
        "points": [
            {
                "flow_lps": format(point.flow_lps, ".6f"),
                "head_m": format(point.head_m, ".9f"),
            }
            for point in points
        ],
        "representation": representation,
    }
    return canonical_json_bytes(payload)


def canonical_curve_bytes(points: tuple[CurvePoint, ...]) -> bytes:
    """Return the path-free canonical original-pump-curve bytes."""
    return _canonical_curve_bytes(points, ORIGINAL_CURVE_REPRESENTATION)


def canonical_net_head_curve_bytes(points: tuple[CurvePoint, ...]) -> bytes:
    """Return the path-free canonical repaired engine-curve bytes."""
    return _canonical_curve_bytes(points, NET_HEAD_CURVE_REPRESENTATION)


def curve_sha256(points: tuple[CurvePoint, ...]) -> str:
    """Return the SHA-256 of canonical original-pump-curve bytes."""
    return hashlib.sha256(canonical_curve_bytes(points)).hexdigest()


def net_head_curve_sha256(points: tuple[CurvePoint, ...]) -> str:
    """Return the SHA-256 of canonical repaired engine-curve bytes."""
    return hashlib.sha256(canonical_net_head_curve_bytes(points)).hexdigest()
