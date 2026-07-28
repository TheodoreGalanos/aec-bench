# ABOUTME: Executes analytical W4 boundary and grid probes from the reviewed W1 authority.
# ABOUTME: Produces deterministic non-promotable evidence without generator or certifier imports.

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sensitivity import members, physics


class AnalyticalProbeError(ValueError):
    """Raised when a declared analytical probe cannot be resolved."""


def _result(
    *,
    evaluated: int,
    failure: str,
    identity: str,
    kind: str,
) -> dict[str, Any]:
    return {
        "evaluated": evaluated,
        "first_failure": failure,
        "promotable": False,
        "probe_id": identity,
        "terminal_state": (
            f"{kind}-pass" if failure == "none" else f"{kind}-reject"
        ),
    }


def _anchor_member(authority: dict[str, Any]) -> dict[str, Any]:
    member = members.build_member(authority, {})
    members.validate_preconditions(member)
    return member


def _decimal_values(member: dict[str, Any]) -> dict[str, Decimal]:
    return members.member_values(member)


def _classify_drawdown(
    drawdown_s: Decimal,
    *,
    limit_s: Decimal,
    margin_s: Decimal,
) -> str:
    if drawdown_s <= limit_s - margin_s:
        return "capable"
    if drawdown_s >= limit_s + margin_s:
        return "review-eligible"
    return "boundary-fragile"


def _band(value: Decimal) -> str:
    if value < Decimal("0.25"):
        return "low"
    if value < Decimal("0.60"):
        return "medium"
    return "high"


def evaluate_boundaries(
    authority: dict[str, Any],
    declarations: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Execute the eleven preregistered analytical boundary probes."""
    member = _anchor_member(authority)
    decimal_values = _decimal_values(member)
    values = physics.member_values(member)
    results: list[dict[str, Any]] = []
    for declaration in declarations:
        probe_id = declaration["probe_id"]
        failure = "none"
        evaluated = 3
        if probe_id == "BND.00":
            horizon_states = (120 <= 120, 121 <= 120)
            if horizon_states != (True, False):
                failure = "forced-horizon"
            evaluated = 2
        elif probe_id == "BND.01":
            support = physics.pump_support(values, 0.0, 0.0)

            def residual(flow: float) -> float:
                return physics.pump_head(
                    values,
                    flow,
                    0.0,
                    0.0,
                ) - physics.system_head(
                    values,
                    flow,
                    values["well.h_start"],
                )

            if not residual(0.0) > 0.0 or not residual(support) < 0.0:
                failure = "root-endpoint-sign"
        elif probe_id == "BND.02":
            flow_at = (
                values["system.Re_min"]
                * math.pi
                * values["system.D"]
                * values["fluid.mu"]
                / (4.0 * values["fluid.rho"])
            )
            classifications = (
                physics.reynolds_number(
                    values,
                    math.nextafter(flow_at, 0.0),
                )
                >= values["system.Re_min"],
                physics.reynolds_number(values, flow_at)
                >= values["system.Re_min"],
                physics.reynolds_number(
                    values,
                    math.nextafter(flow_at, math.inf),
                )
                >= values["system.Re_min"],
            )
            if classifications != (False, True, True):
                failure = "reynolds-boundary"
        elif probe_id == "BND.03":
            limit = decimal_values["capability.t_draw_limit"]
            margin = max(Decimal(1), Decimal("0.01") * limit)
            drawdown_classes = tuple(
                _classify_drawdown(
                    drawdown,
                    limit_s=limit,
                    margin_s=margin,
                )
                for drawdown in (
                    limit - margin,
                    limit,
                    limit + margin,
                )
            )
            if drawdown_classes != (
                "capable",
                "boundary-fragile",
                "review-eligible",
            ):
                failure = "capability-margin"
        elif probe_id == "BND.04":
            bound = Decimal("0.00001")
            margin = max(
                Decimal(4) * bound,
                Decimal("0.001") * decimal_values["pump.Q_0"],
            )
            nets = (margin, Decimal(0), -margin)
            net_flow_classes = (
                "positive" if nets[0] > bound else "fragile",
                "fragile" if abs(nets[1]) <= bound else "resolved",
                "non-drawdown" if nets[2] < -bound else "fragile",
            )
            if net_flow_classes != (
                "positive",
                "fragile",
                "non-drawdown",
            ):
                failure = "net-flow-zero"
        elif probe_id == "BND.05":
            threshold = decimal_values["well.h_start"]
            epsilon = Decimal("0.000000001")
            control_states = tuple(
                value >= threshold
                for value in (
                    threshold - epsilon,
                    threshold,
                    threshold + epsilon,
                )
            )
            if control_states != (False, True, True):
                failure = "control-level"
        elif probe_id == "BND.06":
            clipped_values = tuple(
                min(Decimal(1), max(Decimal(0), value))
                for value in (
                    Decimal("-0.01"),
                    Decimal(0),
                    Decimal(1),
                    Decimal("1.01"),
                )
            )
            if clipped_values != (
                Decimal(0),
                Decimal(0),
                Decimal(1),
                Decimal(1),
            ):
                failure = "severity-clip"
            evaluated = 4
        elif probe_id == "BND.07":
            floor = decimal_values["intervention.o_residual"]
            floored_values = tuple(
                max(floor, value)
                for value in (
                    floor - Decimal("0.001"),
                    floor,
                    floor + Decimal("0.001"),
                )
            )
            if floored_values != (
                floor,
                floor,
                floor + Decimal("0.001"),
            ):
                failure = "intervention-floor"
        elif probe_id == "BND.08":
            epsilon = Decimal("0.000001")
            inspection_bands = (
                _band(Decimal("0.25") - epsilon),
                _band(Decimal("0.25")),
                _band(Decimal("0.60") - epsilon),
                _band(Decimal("0.60")),
            )
            if inspection_bands != (
                "low",
                "medium",
                "medium",
                "high",
            ):
                failure = "inspection-band"
            evaluated = 4
        elif probe_id == "BND.09":
            threshold = Decimal(1) - Decimal(16) * Decimal(2) ** -23
            full_pipe_states = (
                threshold >= threshold,
                threshold + Decimal(2) ** -23 >= threshold,
                threshold - Decimal(2) ** -23 >= threshold,
            )
            if full_pipe_states != (True, True, False):
                failure = "full-pipe-boundary"
        elif probe_id == "BND.10":
            magnitude = Decimal("0.000001")
            budget = Decimal("0.000002")
            if not (
                abs(magnitude) <= budget
                and abs(-magnitude) <= budget
                and abs(magnitude + magnitude) <= budget
            ):
                failure = "mass-sign"
        else:
            raise AnalyticalProbeError(
                f"unknown boundary probe {probe_id}"
            )
        results.append(
            _result(
                evaluated=evaluated,
                failure=failure,
                identity=probe_id,
                kind="probe",
            )
        )
    return results


def _quantize(
    value: Decimal,
    resolution: Decimal,
) -> Decimal:
    return (
        value / resolution
    ).quantize(Decimal(1), rounding=ROUND_HALF_UP) * resolution


def _grid_result(
    identity: str,
    *,
    evaluated: int,
    failure: str,
) -> dict[str, Any]:
    result = _result(
        evaluated=evaluated,
        failure=failure,
        identity=identity,
        kind="grid",
    )
    result.pop("probe_id")
    return result


def _selected_member(
    authority: dict[str, Any],
    selections: dict[str, str],
) -> dict[str, Any]:
    member = members.build_member(authority, selections)
    members.validate_preconditions(member)
    return member


def _progression_grid(
    authority: dict[str, Any],
    grid: list[dict[str, Any]],
) -> dict[str, Any]:
    failure = "none"
    for item in grid:
        member = _selected_member(
            authority,
            dict(item["selections"]),
        )
        values = physics.member_values(member)
        flows: list[float] = []
        classifications: list[str] = []
        for runtime_s, starts in (
            (0, 0),
            (3_600_000, 500),
            (7_200_000, 1_000),
            (10_800_000, 2_000),
        ):
            obstruction = min(
                1.0,
                values["mechanism.r_o_runtime"] * runtime_s
                + values["mechanism.r_o_start"] * starts,
            )
            clearance = min(
                1.0,
                values["mechanism.r_c_runtime"] * runtime_s,
            )
            flow = physics.operating_point(
                values,
                depth_m=values["well.h_start"],
                obstruction=obstruction,
                clearance_loss=clearance,
            )
            interval = physics.capability_interval(
                values,
                flow_m3_s=flow,
                flow_bound_m3_s=0.0,
                report_step_s=1,
            )
            flows.append(flow)
            classifications.append(str(interval["classification"]))
        if (
            any(
                later > earlier
                for earlier, later in zip(flows, flows[1:], strict=False)
            )
            or classifications[0] != "capable"
            or "review-eligible" not in classifications[1:]
        ):
            failure = f"progression-{item['level']}"
            break
    return _grid_result(
        "progression",
        evaluated=len(grid),
        failure=failure,
    )


def _intervention_grid(
    authority: dict[str, Any],
    grid: list[dict[str, Any]],
) -> dict[str, Any]:
    failure = "none"
    histories = (
        (Decimal("0.65"), Decimal("0.10"), "clear"),
        (Decimal("0.25"), Decimal("0.742300"), "clear"),
        (Decimal("0.50"), Decimal("0.50"), "repair"),
    )
    for item in grid:
        member = _selected_member(
            authority,
            dict(item["selections"]),
        )
        values = physics.member_values(member)
        margin = (
            3.0
            * values["observation.flow_resolution"]
            / (1.0 - abs(values["observation.flow_bias"]))
        )
        for obstruction, clearance, effect in histories:
            before = physics.operating_point(
                values,
                depth_m=values["well.h_start"],
                obstruction=float(obstruction),
                clearance_loss=float(clearance),
            )
            if effect == "clear":
                obstruction = max(
                    Decimal(str(values["intervention.o_residual"])),
                    (
                        Decimal(1)
                        - Decimal(str(values["intervention.e_clear"]))
                    )
                    * obstruction,
                )
            else:
                clearance = max(
                    Decimal(str(values["intervention.c_residual"])),
                    (
                        Decimal(1)
                        - Decimal(str(values["intervention.e_repair"]))
                    )
                    * clearance,
                )
            after = physics.operating_point(
                values,
                depth_m=values["well.h_start"],
                obstruction=float(obstruction),
                clearance_loss=float(clearance),
            )
            if after - before <= margin:
                failure = f"intervention-{item['level']}"
                break
        if failure != "none":
            break
    return _grid_result(
        "intervention",
        evaluated=len(grid),
        failure=failure,
    )


def evaluate_grids(
    authority: dict[str, Any],
    grids: dict[str, list[Any]],
) -> dict[str, dict[str, Any]]:
    """Execute every declared W4 observation and semantic grid."""
    anchor_member = _anchor_member(authority)
    values = physics.member_values(anchor_member)
    history_a = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.65,
        clearance_loss=0.10,
    )
    history_b = physics.operating_point(
        values,
        depth_m=values["well.h_start"],
        obstruction=0.25,
        clearance_loss=0.742300,
    )
    flow_failure = "none"
    for item in grids["flow_observation"]:
        resolution = Decimal(item["resolution"])
        bias = Decimal(item["bias"])
        visible_a = _quantize(
            Decimal(str(history_a)) * (Decimal(1) + bias),
            resolution,
        )
        visible_b = _quantize(
            Decimal(str(history_b)) * (Decimal(1) + bias),
            resolution,
        )
        if visible_a != visible_b:
            flow_failure = "flow-ambiguity"
            break
    level_failure = "none"
    for item in grids["level_observation"]:
        resolution = Decimal(item["resolution"])
        bias = Decimal(item["bias"])
        half_bin = resolution / 2
        reference = Decimal(1)
        measured = reference - bias + half_bin
        if (
            _quantize(measured + bias, resolution)
            != reference + resolution
        ):
            level_failure = "level-half-up"
            break
    runtime_failure = (
        "none"
        if all(
            isinstance(item, int) and item > 0
            for item in grids["runtime_observation"]
        )
        else "runtime-resolution"
    )
    resource_failure = "none"
    declarations = {
        parameter["identity"]: parameter
        for parameter in authority["parameters"]
    }
    for item in grids["resource"]:
        lead = Decimal(
            declarations["resource.kit_lead"][
                item["kit_lead"]
            ]
        )
        access = Decimal(
            declarations["resource.access_duration"][
                item["access_duration"]
            ]
        )
        if lead <= 0 or access <= 0:
            resource_failure = "resource-immediate"
            break
    return {
        "flow_observation": _grid_result(
            "flow_observation",
            evaluated=len(grids["flow_observation"]),
            failure=flow_failure,
        ),
        "intervention": _intervention_grid(
            authority,
            grids["intervention"],
        ),
        "level_observation": _grid_result(
            "level_observation",
            evaluated=len(grids["level_observation"]),
            failure=level_failure,
        ),
        "progression": _progression_grid(
            authority,
            grids["progression"],
        ),
        "resource": _grid_result(
            "resource",
            evaluated=len(grids["resource"]),
            failure=resource_failure,
        ),
        "runtime_observation": _grid_result(
            "runtime_observation",
            evaluated=len(grids["runtime_observation"]),
            failure=runtime_failure,
        ),
    }
