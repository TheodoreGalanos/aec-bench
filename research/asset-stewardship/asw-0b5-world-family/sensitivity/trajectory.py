# ABOUTME: Evaluates W4 depth and steady-flow trajectory checks from transferred evidence.
# ABOUTME: Builds independent fixed-grid and piecewise-curve traces without generator or certifier imports.

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from repairs import c_r02, control_edge_trajectory, solver_convergence
from sensitivity import (
    anchor,
    composition,
    edge,
    inputs,
    physics,
    tolerances,
)

RENDER_FLOW = 0.5e-9


@dataclass(frozen=True)
class _Trace:
    depths_m: tuple[float, ...]
    flows_m3_s: tuple[float, ...]
    settings: tuple[int, ...]


def _initial_depth(
    segment: inputs.SegmentEvidence,
    values: dict[str, float],
) -> float:
    if (
        segment.case_id == "G70_TRANSFER"
        and segment.segment_id == "segment-b"
    ):
        carry = segment.semantic["carry"]
        if (
            not isinstance(carry, list)
            or len(carry) != 1
            or not isinstance(carry[0], dict)
            or not isinstance(carry[0].get("value"), str)
        ):
            raise inputs.SensitivityInputError(
                "w4-input: trajectory carry differs"
            )
        return float(
            struct.unpack(">f", bytes.fromhex(carry[0]["value"]))[0]
        )
    return edge.initial_depth(segment, values)


def _state(
    segment: inputs.SegmentEvidence,
) -> tuple[float, float, str]:
    state, selected = anchor._state(
        segment.request["case"],
        segment.segment_id,
    )
    if segment.request["case"]["selected_pump"] == "none":
        selected = "none"
    return (
        float(Decimal(state["obstruction"])),
        float(Decimal(state["clearance-loss"])),
        selected,
    )


def _reference_trace(
    segment: inputs.SegmentEvidence,
    *,
    step_s: float,
    settings: tuple[int, ...] | None = None,
) -> _Trace:
    values = physics.member_values(segment.request["member"])
    case = segment.request["case"]
    obstruction, clearance, selected = _state(segment)
    depth = _initial_depth(segment, values)
    running = False
    depths: list[float] = []
    flows: list[float] = []
    trace_settings: list[int] = []
    count = len(
        segment.semantic["series"]["wet_well_depth_m"]["values"]
    )
    for index in range(count):
        if settings is None:
            if case["control_mode"] == "automatic":
                if not running and depth >= values["well.h_start"]:
                    running = True
                elif running and depth <= values["well.h_stop"]:
                    running = False
            else:
                running = selected in {"pump-a", "pump-b"}
        else:
            running = bool(settings[index])
        trace_settings.append(int(running))
        advanced = physics.rk4_advance(
            values,
            clearance_loss=clearance,
            depth_m=depth,
            duration_s=1.0,
            inflow_m3_s=edge.inflow_at(
                case,
                values,
                index + 1.0,
            ),
            obstruction=obstruction,
            running=running,
            step_s=step_s,
        )
        depths.append(advanced.depth_m)
        flows.append(advanced.flow_m3_s)
        depth = advanced.depth_m
    return _Trace(
        tuple(depths),
        tuple(flows),
        tuple(trace_settings),
    )


def _curve_points(
    segment: inputs.SegmentEvidence,
    selected: str,
) -> tuple[tuple[float, float], ...]:
    role = (
        "pump-a-engine-curve"
        if selected == "pump-a"
        else "pump-b-engine-curve"
    )
    try:
        value = json.loads(segment.role_bytes[role].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise inputs.SensitivityInputError(
            f"w4-input: engine curve differs: {error}"
        ) from error
    points = value.get("points") if isinstance(value, dict) else None
    if not isinstance(points, list) or len(points) != 33:
        raise inputs.SensitivityInputError(
            "w4-input: engine curve point inventory differs"
        )
    result: list[tuple[float, float]] = []
    for point in points:
        if (
            not isinstance(point, dict)
            or set(point) != {"flow_lps", "head_m"}
        ):
            raise inputs.SensitivityInputError(
                "w4-input: engine curve point differs"
            )
        result.append(
            (
                float(Decimal(point["head_m"])),
                float(Decimal(point["flow_lps"])) / 1000.0,
            )
        )
    if any(
        later[0] <= earlier[0] or later[1] > earlier[1]
        for earlier, later in zip(result, result[1:], strict=False)
    ):
        raise inputs.SensitivityInputError(
            "w4-input: engine curve order differs"
        )
    return tuple(result)


def _piecewise_flow(
    points: tuple[tuple[float, float], ...],
    head_m: float,
) -> float:
    if not math.isfinite(head_m):
        raise inputs.SensitivityInputError(
            "w4-input: curve evaluation head is non-finite"
        )
    if head_m <= points[0][0]:
        return points[0][1]
    if head_m >= points[-1][0]:
        return points[-1][1]
    for (head_0, flow_0), (head_1, flow_1) in zip(
        points,
        points[1:],
        strict=False,
    ):
        if head_m <= head_1:
            fraction = (head_m - head_0) / (head_1 - head_0)
            return flow_0 + fraction * (flow_1 - flow_0)
    raise inputs.SensitivityInputError(
        "w4-input: curve evaluation left its support"
    )


def _piecewise_trace(
    segment: inputs.SegmentEvidence,
    *,
    settings: tuple[int, ...],
) -> _Trace:
    values = physics.member_values(segment.request["member"])
    case = segment.request["case"]
    _obstruction, _clearance, selected = _state(segment)
    depth = _initial_depth(segment, values)
    depths: list[float] = []
    flows: list[float] = []
    if selected == "none":
        points: tuple[tuple[float, float], ...] = ()
    else:
        points = _curve_points(segment, selected)
    area = physics.wet_well_area(values)
    for index, running_value in enumerate(settings):
        inflow = edge.inflow_at(case, values, index + 1.0)
        running = bool(running_value)

        def derivative(
            depth_value: float,
            *,
            step_running: bool = running,
            step_inflow: float = inflow,
        ) -> tuple[float, float]:
            if not step_running:
                return step_inflow / area, 0.0
            bounded = min(
                max(depth_value, 0.0),
                values["well.h_overflow"],
            )
            flow = _piecewise_flow(
                points,
                values["system.z_d"] - bounded,
            )
            return (step_inflow - flow) / area, flow

        k1, flow = derivative(depth)
        k2, _ = derivative(depth + k1 / 2.0)
        k3, _ = derivative(depth + k2 / 2.0)
        k4, _ = derivative(depth + k3)
        depth += (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
        if (
            not math.isfinite(depth)
            or depth < 0.0
            or depth > values["well.h_overflow"]
        ):
            raise inputs.SensitivityInputError(
                "w4-input: piecewise trajectory leaves storage"
            )
        depths.append(depth)
        flows.append(flow)
    return _Trace(tuple(depths), tuple(flows), settings)


def _selected_candidate_flow(
    segment: inputs.SegmentEvidence,
    selected: str,
) -> list[float]:
    if selected == "none":
        return [0.0] * len(
            segment.semantic["series"]["wet_well_depth_m"]["values"]
        )
    return anchor._series(
        segment,
        (
            "pump_a_flow_m3_s"
            if selected == "pump-a"
            else "pump_b_flow_m3_s"
        ),
    )


def _candidate_settings(
    segment: inputs.SegmentEvidence,
    selected: str,
) -> tuple[int, ...]:
    count = len(
        segment.semantic["series"]["wet_well_depth_m"]["values"]
    )
    if selected == "none":
        return (0,) * count
    values = segment.semantic["series"][
        "pump_a_setting"
        if selected == "pump-a"
        else "pump_b_setting"
    ]["values"]
    if (
        not isinstance(values, list)
        or len(values) != count
        or any(value not in {0, 1} for value in values)
    ):
        raise inputs.SensitivityInputError(
            "w4-input: candidate setting trace differs"
        )
    return tuple(values)


def _segment_checks(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    values = physics.member_values(segment.request["member"])
    obstruction, clearance, selected = _state(segment)
    independent_reference = _reference_trace(
        segment,
        step_s=1.0,
    )
    if segment.request["case"]["control_mode"] == "automatic":
        edge_result = edge.validate_automatic_edges(segment)
        if edge_result["outcome"] != "pass":
            raise inputs.SensitivityInputError(
                "w4-input: C-R12 must pass before trajectory edges"
            )
        validated_settings = _candidate_settings(
            segment,
            selected,
        )
    else:
        validated_settings = independent_reference.settings
    reference = _reference_trace(
        segment,
        step_s=1.0,
        settings=validated_settings,
    )
    half = _reference_trace(
        segment,
        step_s=0.5,
        settings=validated_settings,
    )
    piecewise = _piecewise_trace(
        segment,
        settings=validated_settings,
    )
    candidate_depth = anchor._series(
        segment,
        "wet_well_depth_m",
    )
    candidate_flow = _selected_candidate_flow(segment, selected)
    residual_depth = anchor._raw(result_segment, "C-R10")
    residual_flow = anchor._raw(result_segment, "C-R11")
    candidate_inflow = anchor._series(
        segment,
        "wet_well_inflow_m3_s",
    )
    candidate_overflow = anchor._series(
        segment,
        "wet_well_overflow_m3_s",
    )
    candidate_a = anchor._series(
        segment,
        "pump_a_flow_m3_s",
    )
    candidate_b = anchor._series(
        segment,
        "pump_b_flow_m3_s",
    )
    count = len(reference.depths_m)
    if not (
        len(half.depths_m)
        == len(piecewise.depths_m)
        == len(candidate_depth)
        == len(candidate_flow)
        == len(residual_depth)
        == len(residual_flow)
        == len(candidate_inflow)
        == len(candidate_overflow)
        == len(candidate_a)
        == len(candidate_b)
        == count
    ):
        raise inputs.SensitivityInputError(
            "w4-input: trajectory vector alignment differs"
        )

    area = physics.wet_well_area(values)
    hysteresis_ceiling = 0.25 * (
        values["well.h_start"] - values["well.h_stop"]
    )
    dynamic_depth = 0.0
    routing_depth_correction = 0.0
    routing_depth_method_bound = 0.0
    previous_net_flow = 0.0
    depth_ratio = 0.0
    depth_residual_sum = 0.0
    depth_budget_sum = 0.0
    depth_failure = "none"
    depth_first_evidence: dict[str, str | int] | None = None
    depth_worst_evidence: dict[str, str | int] | None = None
    previous_setting = 0
    routing_depth_corrections: list[float] = []
    routing_depth_method_bounds: list[float] = []
    settling_until = -1
    steady: set[int] = set()
    for index, setting in enumerate(reference.settings):
        depth_before = (
            _initial_depth(segment, values)
            if index == 0
            else reference.depths_m[index - 1]
        )
        if setting == 1 and previous_setting == 0:
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
            dynamic_depth = math.fsum(
                [
                    dynamic_depth,
                    float(settling["depth_allowance_m"]),
                ]
            )
            settling_until = (
                index + int(settling["settling_time_s"]) - 1
            )
            if (
                dynamic_depth > hysteresis_ceiling
                and depth_failure == "none"
            ):
                depth_failure = "C-R10-dynamic-depth-ceiling"
        if setting == 1 and index > settling_until:
            steady.add(index)
        rk4_bound = (
            16.0
            / 15.0
            * abs(reference.depths_m[index] - half.depths_m[index])
        )
        curve_bound = abs(
            reference.depths_m[index] - piecewise.depths_m[index]
        )
        current_net_flow = (
            candidate_inflow[index]
            - candidate_a[index]
            - candidate_b[index]
            - candidate_overflow[index]
        )
        routing_volume = c_r02.trapezoidal_right_end_defect(
            previous_net_flow_m3_s=previous_net_flow,
            current_net_flow_m3_s=current_net_flow,
            interval_s=1.0,
        )
        routing_depth_correction = math.fsum(
            [
                routing_depth_correction,
                routing_volume / area,
            ]
        )
        flow_method_bound = tolerances.outward_sum(
            [
                tolerances.binary32_bound(candidate_inflow[index]),
                tolerances.binary32_bound(candidate_a[index]),
                tolerances.binary32_bound(candidate_b[index]),
                tolerances.binary32_bound(
                    candidate_overflow[index]
                ),
                4.0 * RENDER_FLOW,
            ]
        )
        routing_depth_method_bound = math.fsum(
            [
                routing_depth_method_bound,
                float(
                    Decimal(
                        solver_convergence.HEAD_TOLERANCE_M
                    )
                ),
                flow_method_bound / area,
            ]
        )
        routing_depth_corrections.append(
            routing_depth_correction
        )
        routing_depth_method_bounds.append(
            routing_depth_method_bound
        )
        corrected = candidate_depth[index] - (
            reference.depths_m[index]
            + routing_depth_correction
        )
        edge_depth_correction = (
            residual_depth[index]
            - routing_depth_correction
            - corrected
        )
        budget = tolerances.outward_sum(
            [
                tolerances.binary32_bound(candidate_depth[index]),
                rk4_bound,
                curve_bound,
                dynamic_depth,
                routing_depth_method_bound,
                tolerances.binary64_guard(
                    reference.depths_m[index]
                ),
            ]
        )
        depth_residual_sum = math.fsum(
            [depth_residual_sum, corrected]
        )
        depth_budget_sum = math.fsum([depth_budget_sum, budget])
        point_ratio = abs(corrected) / budget
        integral_ratio = abs(depth_residual_sum) / depth_budget_sum
        sample_ratio = max(point_ratio, integral_ratio)
        if sample_ratio > depth_ratio:
            depth_ratio = sample_ratio
            depth_worst_evidence = {
                "budget_m": composition._text(budget),
                "case_id": segment.case_id,
                "corrected_residual_m": composition._text(
                    corrected
                ),
                "edge_correction_m": composition._text(
                    edge_depth_correction
                ),
                "integral_ratio": composition._text(
                    integral_ratio
                ),
                "point_ratio": composition._text(point_ratio),
                "second": index + 1,
                "segment_id": segment.segment_id,
            }
        if abs(corrected) > budget and depth_failure == "none":
            depth_failure = "C-R10-depth-trajectory"
            depth_first_evidence = depth_worst_evidence
        if (
            abs(depth_residual_sum) > depth_budget_sum
            and depth_failure == "none"
        ):
            depth_failure = "C-R10-depth-integral"
            depth_first_evidence = depth_worst_evidence
        previous_setting = setting
        previous_net_flow = current_net_flow

    candidate_settings = _candidate_settings(
        segment,
        selected,
    )
    candidate_steady = anchor._eligible_running_indices(
        segment=segment,
        selected=selected,
        state={
            "clearance-loss": composition._text(clearance),
            "obstruction": composition._text(obstruction),
        },
        values=values,
    ) if selected != "none" else set()
    comparison_indices = sorted(
        steady.intersection(candidate_steady)
    )
    flow_ratio = 0.0
    flow_residual_sum = 0.0
    flow_budget_sum = 0.0
    flow_failure = "none"
    flow_first_evidence: dict[str, str | int] | None = None
    flow_worst_evidence: dict[str, str | int] | None = None
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
    for index in comparison_indices:
        if candidate_settings[index] != 1:
            raise inputs.SensitivityInputError(
                "w4-input: steady candidate setting differs"
            )
        reference_flow = reference.flows_m3_s[index]
        depth_before = (
            _initial_depth(segment, values)
            if index == 0
            else reference.depths_m[index - 1]
        )
        prior_routing_depth = (
            0.0
            if index == 0
            else routing_depth_corrections[index - 1]
        )
        adjusted_reference_flow = physics.operating_point(
            values,
            depth_m=depth_before + prior_routing_depth,
            obstruction=obstruction,
            clearance_loss=clearance,
        )
        slope = physics.root_slope(
            values,
            flow_m3_s=reference_flow,
            depth_m=depth_before,
            obstruction=obstruction,
            clearance_loss=clearance,
        )
        curve_flow = tolerances.outward_divide(
            curve_head,
            slope,
        )
        rk4_flow = (
            16.0
            / 15.0
            * abs(reference_flow - half.flows_m3_s[index])
        )
        dynamic_flow = 0.001 * reference_flow
        depth_method_flow = tolerances.outward_divide(
            (
                0.0
                if index == 0
                else routing_depth_method_bounds[index - 1]
            ),
            slope,
        )
        budget = tolerances.outward_sum(
            [
                tolerances.binary32_bound(candidate_flow[index]),
                rk4_flow,
                curve_flow,
                math.ulp(reference_flow),
                dynamic_flow,
                depth_method_flow,
                tolerances.binary64_guard(reference_flow),
            ]
        )
        route_flow_correction = (
            adjusted_reference_flow - reference_flow
        )
        corrected = (
            candidate_flow[index] - adjusted_reference_flow
        )
        edge_flow_correction = (
            residual_flow[index]
            - route_flow_correction
            - corrected
        )
        flow_residual_sum = math.fsum(
            [flow_residual_sum, corrected]
        )
        flow_budget_sum = math.fsum([flow_budget_sum, budget])
        point_ratio = abs(corrected) / budget
        integral_ratio = abs(flow_residual_sum) / flow_budget_sum
        sample_ratio = max(point_ratio, integral_ratio)
        if sample_ratio > flow_ratio:
            flow_ratio = sample_ratio
            flow_worst_evidence = {
                "budget_m3_s": composition._text(budget),
                "case_id": segment.case_id,
                "corrected_residual_m3_s": composition._text(
                    corrected
                ),
                "edge_correction_m3_s": composition._text(
                    edge_flow_correction
                ),
                "integral_ratio": composition._text(
                    integral_ratio
                ),
                "point_ratio": composition._text(point_ratio),
                "second": index + 1,
                "segment_id": segment.segment_id,
            }
        if abs(corrected) > budget and flow_failure == "none":
            flow_failure = "C-R11-flow-trajectory"
            flow_first_evidence = flow_worst_evidence
        if (
            abs(flow_residual_sum) > flow_budget_sum
            and flow_failure == "none"
        ):
            flow_failure = "C-R11-flow-integral"
            flow_first_evidence = flow_worst_evidence

    return {
        "C-R10": {
            "evaluated": count,
            "first_failure": depth_failure,
            "first_failure_evidence": depth_first_evidence,
            "maximum_ratio": composition._text(depth_ratio),
            "outcome": (
                "pass" if depth_failure == "none" else "reject"
            ),
            "worst_evidence": depth_worst_evidence,
        },
        "C-R11": {
            "evaluated": len(comparison_indices),
            "first_failure": flow_failure,
            "first_failure_evidence": flow_first_evidence,
            "maximum_ratio": composition._text(flow_ratio),
            "outcome": (
                "pass" if flow_failure == "none" else "reject"
            ),
            "worst_evidence": flow_worst_evidence,
        },
    }


def evaluate_trajectory_checks(
    *,
    amendment_bytes: bytes,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
    control_edge_amendment_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> dict[str, Any]:
    """Evaluate C-R10 and C-R11 over every anchor segment."""
    c_r02.read_amendment(amendment_bytes)
    control_edge_trajectory.read_amendment(
        control_edge_amendment_bytes
    )
    solver_convergence.read_amendment(solver_convergence_bytes)
    segments = inputs.read_transfer_bundle(bundle_bytes)
    if any(
        segment.request["engine"]["settings_id"]
        != solver_convergence.ENGINE_SETTINGS_ID
        for segment in segments
    ):
        raise inputs.SensitivityInputError(
            "w4-input: trajectory correction requires settings v3"
        )
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    aggregate: dict[str, dict[str, Any]] = {
        "C-R10": {
            "evaluated": 0,
            "first_failure": "none",
            "first_failure_evidence": None,
            "maximum_ratio": 0.0,
            "worst_evidence": None,
        },
        "C-R11": {
            "evaluated": 0,
            "first_failure": "none",
            "first_failure_evidence": None,
            "maximum_ratio": 0.0,
            "worst_evidence": None,
        },
    }
    for segment in segments:
        checks = _segment_checks(
            segment,
            certifier.segment_results[
                (segment.case_id, segment.segment_id)
            ],
        )
        for check_id, check in checks.items():
            target = aggregate[check_id]
            target["evaluated"] += check["evaluated"]
            check_ratio = float(Decimal(check["maximum_ratio"]))
            if check_ratio > float(target["maximum_ratio"]):
                target["maximum_ratio"] = check_ratio
                target["worst_evidence"] = check[
                    "worst_evidence"
                ]
            if (
                target["first_failure"] == "none"
                and check["first_failure"] != "none"
            ):
                target["first_failure"] = check["first_failure"]
                target["first_failure_evidence"] = check[
                    "first_failure_evidence"
                ]
    result_checks = {
        check_id: {
            "evaluated": value["evaluated"],
            "first_failure": value["first_failure"],
            "first_failure_evidence": value[
                "first_failure_evidence"
            ],
            "maximum_ratio": composition._text(
                float(value["maximum_ratio"])
            ),
            "outcome": (
                "pass"
                if value["first_failure"] == "none"
                else "reject"
            ),
            "worst_evidence": value["worst_evidence"],
        }
        for check_id, value in aggregate.items()
    }
    failures = [
        check["first_failure"]
        for check in result_checks.values()
        if check["first_failure"] != "none"
    ]
    return {
        "authority": {
            "c_r02_amendment_sha256": c_r02.AMENDMENT_SHA256,
            "control_edge_trajectory_amendment_sha256": (
                control_edge_trajectory.AMENDMENT_SHA256
            ),
            "solver_convergence_amendment_sha256": (
                solver_convergence.AMENDMENT_SHA256
            ),
        },
        "checks": result_checks,
        "first_failure": failures[0] if failures else "none",
        "promotable": False,
        "terminal_state": (
            "trajectory-checks-reject"
            if failures
            else "trajectory-checks-pass"
        ),
    }
