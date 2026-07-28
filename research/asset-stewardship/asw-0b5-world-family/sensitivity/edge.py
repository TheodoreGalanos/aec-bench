# ABOUTME: Proves repaired C-R12 automatic control-edge windows independently.
# ABOUTME: Exposes candidate edge times only after exact shape and derived-window checks.

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sensitivity import anchor, composition, inputs, physics, tolerances


@dataclass(frozen=True)
class _Trace:
    depths_m: tuple[float, ...]
    settings: tuple[int, ...]


def initial_depth(
    segment: inputs.SegmentEvidence,
    values: dict[str, float],
) -> float:
    """Return the declared non-carry initial depth for an anchor case."""
    source = segment.request["case"]["initial_depth_source"]
    if source == "well.h_start":
        return values["well.h_start"]
    if source == "well.h_stop":
        return values["well.h_stop"]
    raise inputs.SensitivityInputError(
        "w4-input: edge initial depth source differs"
    )


def inflow_at(
    case: dict[str, Any],
    values: dict[str, float],
    time_s: float,
) -> float:
    """Reconstruct the exact declared W1 inflow stimulus at one time."""
    stimulus = case["inflow_stimulus"]
    if stimulus == "zero":
        return 0.0
    if stimulus == "constant-assessment":
        return values["inflow.Q_assess"]
    if stimulus != "base-pattern":
        raise inputs.SensitivityInputError(
            "w4-input: edge inflow stimulus differs"
        )
    points = (
        (0.0, values["inflow.Q_low"]),
        (5399.0, values["inflow.Q_low"]),
        (5400.0, values["inflow.Q_nominal"]),
        (10799.0, values["inflow.Q_nominal"]),
        (10800.0, values["inflow.Q_assess"]),
        (14399.0, values["inflow.Q_assess"]),
        (14400.0, values["inflow.Q_nominal"]),
        (21599.0, values["inflow.Q_nominal"]),
        (21600.0, values["inflow.Q_low"]),
        (28800.0, values["inflow.Q_low"]),
    )
    for (left_time, left_value), (
        right_time,
        right_value,
    ) in zip(points, points[1:], strict=False):
        if time_s <= right_time:
            return left_value + (
                (time_s - left_time)
                * (right_value - left_value)
                / (right_time - left_time)
            )
    return points[-1][1]


def _quasi_steady_trace(
    segment: inputs.SegmentEvidence,
    *,
    step_s: float,
) -> _Trace:
    values = physics.member_values(segment.request["member"])
    case = segment.request["case"]
    state, selected = anchor._state(case, segment.segment_id)
    obstruction = float(Decimal(state["obstruction"]))
    clearance = float(Decimal(state["clearance-loss"]))
    depth = initial_depth(segment, values)
    running = False
    depths: list[float] = []
    settings: list[int] = []
    count = len(
        segment.semantic["series"]["wet_well_depth_m"]["values"]
    )
    for index in range(count):
        if not running and depth >= values["well.h_start"]:
            running = True
        elif running and depth <= values["well.h_stop"]:
            running = False
        settings.append(int(running))
        depth = physics.rk4_advance(
            values,
            clearance_loss=clearance,
            depth_m=depth,
            duration_s=1.0,
            inflow_m3_s=inflow_at(case, values, index + 1.0),
            obstruction=obstruction,
            running=running,
            step_s=step_s,
        ).depth_m
        depths.append(depth)
    return _Trace(tuple(depths), tuple(settings))


def _edges(settings: tuple[int, ...] | list[int]) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    previous = 0
    for index, setting in enumerate(settings):
        if setting != previous:
            result.append(("start" if setting == 1 else "stop", index))
        previous = setting
    return result


def _edge_slope(
    values: dict[str, float],
    *,
    clearance: float,
    depth_m: float,
    inflow_m3_s: float,
    obstruction: float,
    running: bool,
) -> float:
    flow = (
        physics.operating_point(
            values,
            depth_m=depth_m,
            obstruction=obstruction,
            clearance_loss=clearance,
        )
        if running
        else 0.0
    )
    return abs(
        (inflow_m3_s - flow) / physics.wet_well_area(values)
    )


def validate_automatic_edges(
    segment: inputs.SegmentEvidence,
) -> dict[str, Any]:
    """Prove C-R12 before candidate edge times enter mass correction."""
    case = segment.request["case"]
    if case["control_mode"] != "automatic":
        raise inputs.SensitivityInputError(
            "w4-input: C-R12 requires an automatic case"
        )
    values = physics.member_values(segment.request["member"])
    state, selected = anchor._state(case, segment.segment_id)
    obstruction = float(Decimal(state["obstruction"]))
    clearance = float(Decimal(state["clearance-loss"]))
    candidate_settings = segment.semantic["series"][
        "pump_a_setting" if selected == "pump-a" else "pump_b_setting"
    ]["values"]
    candidate_edges = _edges(candidate_settings)
    reference_1 = _quasi_steady_trace(segment, step_s=1.0)
    reference_half = _quasi_steady_trace(segment, step_s=0.5)
    reference_edges = _edges(reference_half.settings)
    if [kind for kind, _ in candidate_edges] != [
        kind for kind, _ in reference_edges
    ]:
        return {
            "edge_count": len(candidate_edges),
            "first_failure": "C-R12-edge-shape",
            "maximum_ratio": "inf",
            "outcome": "reject",
        }
    area = physics.wet_well_area(values)
    candidate_depths = anchor._series(segment, "wet_well_depth_m")
    dynamic_prefix = 0.0
    curve_prefix = 0.0
    maximum_ratio = 0.0
    next_edge = 0
    first_depth = initial_depth(segment, values)
    for index, running in enumerate(reference_half.settings):
        depth_before = (
            first_depth
            if index == 0
            else reference_half.depths_m[index - 1]
        )
        if running:
            flow = physics.operating_point(
                values,
                depth_m=depth_before,
                obstruction=obstruction,
                clearance_loss=clearance,
            )
            curve_head = tolerances.curve_head_bound(
                head_zero_m=Decimal(str(values["pump.H_0"])),
                obstruction=Decimal(str(obstruction)),
                clearance_loss=Decimal(str(clearance)),
                obstruction_coefficient=Decimal(
                    str(values["mechanism.a_o"])
                ),
                clearance_coefficient=Decimal(
                    str(values["mechanism.a_c"])
                ),
                segments=32,
            )
            slope = physics.root_slope(
                values,
                flow_m3_s=flow,
                depth_m=depth_before,
                obstruction=obstruction,
                clearance_loss=clearance,
            )
            curve_prefix = math.fsum(
                [
                    curve_prefix,
                    tolerances.outward_divide(curve_head, slope) / area,
                ]
            )
        while (
            next_edge < len(reference_edges)
            and reference_edges[next_edge][1] == index
        ):
            kind, reference_index = reference_edges[next_edge]
            _, candidate_index = candidate_edges[next_edge]
            if kind == "start":
                flow = physics.operating_point(
                    values,
                    depth_m=depth_before,
                    obstruction=obstruction,
                    clearance_loss=clearance,
                )
                settling = physics.dynamic_settling(
                    values,
                    flow_m3_s=flow,
                    depth_m=depth_before,
                    obstruction=obstruction,
                    clearance_loss=clearance,
                    report_step_s=1,
                )
                dynamic_prefix = math.fsum(
                    [
                        dynamic_prefix,
                        float(settling["depth_allowance_m"]),
                    ]
                )
                if (
                    dynamic_prefix
                    > 0.25
                    * (
                        values["well.h_start"]
                        - values["well.h_stop"]
                    )
                ):
                    return {
                        "edge_count": len(candidate_edges),
                        "first_failure": (
                            "C-R12-dynamic-depth-prefix-ceiling"
                        ),
                        "maximum_ratio": "inf",
                        "outcome": "reject",
                    }
            candidate_depth = candidate_depths[candidate_index]
            reference_depth = reference_half.depths_m[reference_index]
            rk4_bound = (
                16.0
                / 15.0
                * abs(
                    reference_1.depths_m[reference_index]
                    - reference_depth
                )
            )
            prior_running = (
                False
                if reference_index == 0
                else bool(reference_half.settings[reference_index - 1])
            )
            inflow = inflow_at(
                case,
                values,
                reference_index + 1.0,
            )
            before_slope = _edge_slope(
                values,
                clearance=clearance,
                depth_m=depth_before,
                inflow_m3_s=inflow,
                obstruction=obstruction,
                running=prior_running,
            )
            after_slope = _edge_slope(
                values,
                clearance=clearance,
                depth_m=depth_before,
                inflow_m3_s=inflow,
                obstruction=obstruction,
                running=bool(reference_half.settings[reference_index]),
            )
            window = tolerances.edge_time_window(
                depth_terms_m=[
                    tolerances.binary32_bound(candidate_depth)
                    + anchor.RENDER_LENGTH,
                    rk4_bound,
                    curve_prefix,
                    dynamic_prefix,
                    tolerances.binary64_guard(reference_depth),
                ],
                report_step_s=1,
                slope_after_m_s=after_slope,
                slope_before_m_s=before_slope,
            )
            difference = abs(candidate_index - reference_index)
            ratio = difference / float(window["window_s"])
            maximum_ratio = max(maximum_ratio, ratio)
            if difference > int(window["window_s"]):
                return {
                    "edge_count": len(candidate_edges),
                    "first_failure": "C-R12-edge-window",
                    "maximum_ratio": composition._text(maximum_ratio),
                    "outcome": "reject",
                }
            next_edge += 1
    return {
        "edge_count": len(candidate_edges),
        "first_failure": "none",
        "maximum_ratio": composition._text(maximum_ratio),
        "outcome": "pass",
    }
