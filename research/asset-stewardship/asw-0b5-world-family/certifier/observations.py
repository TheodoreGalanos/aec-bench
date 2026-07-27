# ABOUTME: Computes certifier-owned exact invariants and W3 residual observations from permitted semantic bytes.
# ABOUTME: Uses analytical W1 physics and fixed RK4 references while leaving every numerical threshold to W4.

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from certifier import candidate, physics

CONTINUITY_PATTERN = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")

SOURCE_BY_SERIES = {
    "time_s": "independent-report-grid",
    "wet_well_depth_m": "WW_B4:SMO_invert_depth",
    "wet_well_volume_m3": "WW_B4:SMO_stored_ponded_volume",
    "wet_well_inflow_m3_s": "WW_B4:SMO_lateral_inflow",
    "wet_well_overflow_m3_s": "WW_B4:SMO_flooding_losses",
    "pump_a_flow_m3_s": "L_PA:SMO_flow_rate_link",
    "pump_b_flow_m3_s": "L_PB:SMO_flow_rate_link",
    "force_main_flow_m3_s": "derived:binary32-pump-flow-sum",
    "pump_a_setting": "solver-step:L_PA:swmm_LINK_SETTING",
    "pump_b_setting": "solver-step:L_PB:swmm_LINK_SETTING",
    "wet_well_head_m": "WW_B4:SMO_hydraulic_head",
    "discharge_head_m": "derived:fixed-HGL:system.z_d",
}

NUMERICAL_IDS = tuple(f"C-R{index:02d}" for index in (*range(1, 15), 17, 18, 19, 21, 22, 23))


class ObservationError(ValueError):
    """Raised when an exact semantic or qualitative W3 invariant differs."""


def _text(value: float) -> str:
    if not math.isfinite(value):
        raise ObservationError("non-finite residual observation")
    rendered = format(value, ".17f").rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _summary(values: list[float]) -> dict[str, str | int]:
    if not values:
        return {
            "maximum_absolute": "0",
            "sample_count": 0,
            "signed_sum": "0",
        }
    return {
        "maximum_absolute": _text(max(abs(value) for value in values)),
        "sample_count": len(values),
        "signed_sum": _text(math.fsum(values)),
    }


def _decoded(semantic: dict[str, Any], identity: str) -> list[float]:
    values = semantic["series"][identity]["values"]
    return [candidate.decode_binary32(value) for value in values]


def _initial_depth(
    case: dict[str, Any],
    values: dict[str, Decimal],
    *,
    carried_depth: float | None,
) -> float:
    if carried_depth is not None:
        return carried_depth
    source = case["initial_depth_source"]
    if source == "well.h_start":
        return float(values["well.h_start"])
    if source == "well.h_stop":
        return float(values["well.h_stop"])
    raise ObservationError("unknown initial depth source")


def expected_report_inflow(
    case: dict[str, Any],
    values: dict[str, Decimal],
    second: int,
) -> float:
    """Reconstruct the rendered time series at the pinned report evaluation instant."""
    stimulus = case["inflow_stimulus"]
    if stimulus == "zero":
        return 0.0
    if stimulus == "constant-assessment":
        return float(values["inflow.Q_assess"])
    if stimulus != "base-pattern":
        raise ObservationError("unknown inflow stimulus")
    points = (
        (0, float(values["inflow.Q_low"])),
        (5399, float(values["inflow.Q_low"])),
        (5400, float(values["inflow.Q_nominal"])),
        (10799, float(values["inflow.Q_nominal"])),
        (10800, float(values["inflow.Q_assess"])),
        (14399, float(values["inflow.Q_assess"])),
        (14400, float(values["inflow.Q_nominal"])),
        (21599, float(values["inflow.Q_nominal"])),
        (21600, float(values["inflow.Q_low"])),
        (28800, float(values["inflow.Q_low"])),
    )
    if second < 1 or second > 28800:
        raise ObservationError("base-pattern report second leaves its horizon")
    date_origin = 37257.0
    evaluation_seconds = ((second - 1) * 1000.0 + 1.0) / 1000.0
    x = date_origin + evaluation_seconds / 86400.0
    for (left_second, left_value), (right_second, right_value) in zip(
        points,
        points[1:],
        strict=False,
    ):
        x1 = date_origin + left_second / 86400.0
        x2 = date_origin + right_second / 86400.0
        if x <= x2:
            return left_value + ((x - x1) * (right_value - left_value) / (x2 - x1))
    return points[-1][1]


def head_closure_residuals(
    values: dict[str, Decimal],
    *,
    clearance_loss: float,
    flow_m3_s: float,
    obstruction: float,
    static_head_m: float,
) -> tuple[float, float]:
    """Return original pump/system and repaired net-head/static-HGL closures."""
    pump_head = physics.pump_head(
        values,
        flow_m3_s,
        obstruction,
        clearance_loss,
    )
    loss_head = physics.system_loss_head(values, flow_m3_s)
    pump_closure = pump_head - (static_head_m + loss_head)
    net_head_closure = static_head_m - (pump_head - loss_head)
    return pump_closure, net_head_closure


def segment_state(
    case: dict[str, Any],
    segment_id: str,
) -> tuple[dict[str, str], dict[str, str], str]:
    """Return exact Pump A/B state and selected label for one expanded segment."""
    pump_a = case["mechanism_state"]["pump-a"]
    pump_b = case["mechanism_state"]["pump-b"]
    selected = case["selected_pump"]
    if case["case_id"] == "G70_TRANSFER":
        selected = "pump-a" if segment_id == "segment-a" else "pump-b"
    elif case["case_id"] == "G80_NO_MAINTENANCE":
        index = int(segment_id.removeprefix("checkpoint-"))
        pump_a = case["checkpoints"][index]["mechanism_state"]
        selected = "pump-a"
    return pump_a, pump_b, selected


def validate_semantic_exact(
    semantic: dict[str, Any],
    request: dict[str, Any],
    *,
    expected_periods: int,
    selected_pump: str,
) -> None:
    """Enforce exact metadata, diagnostics, topology, maturity, and derived series."""
    if semantic["period_count"] != expected_periods:
        raise ObservationError("semantic period count differs")
    if semantic["authority"] != {
        "profile_id": candidate.PROFILE_ID,
        "protocol_id": candidate.PROTOCOL_ID,
        "repair_declaration_sha256": candidate.REPAIR_SHA256,
        "scope": "research-private",
    }:
        raise ObservationError("semantic authority differs")
    if semantic["engine"] != request["engine"]:
        raise ObservationError("semantic engine binding differs")
    if semantic["case_content_id"] != request["case"]["case_content_id"]:
        raise ObservationError("semantic case binding differs")
    if semantic["member_content_id"] != request["member"]["member_content_id"]:
        raise ObservationError("semantic member binding differs")
    if semantic["engine_output"] != {
        "flow_units_code": 4,
        "link_names": ["L_PA", "L_PB"],
        "node_names": ["O_HGL_A", "O_HGL_B", "WW_B4"],
        "output_api_version": 52004,
        "project_size": [0, 3, 2, 1, 0],
        "report_step_seconds": 1,
    }:
        raise ObservationError("semantic engine-output profile differs")
    if semantic["lifecycle_return_codes"] != {
        "close": 0,
        "end": 0,
        "open": 0,
        "report": 0,
        "start": 0,
        "step": 0,
    }:
        raise ObservationError("semantic lifecycle return code differs")
    diagnostics = semantic["diagnostics"]
    if not isinstance(diagnostics, dict) or set(diagnostics) != {
        "completion_marker",
        "convergence_at_all_steps",
        "errors",
        "flow_routing_continuity_error_percent",
        "steps_not_converging_percent",
        "warnings",
    }:
        raise ObservationError("semantic diagnostic shape differs")
    continuity = diagnostics["flow_routing_continuity_error_percent"]
    if (
        diagnostics["completion_marker"] is not True
        or diagnostics["convergence_at_all_steps"] is not True
        or diagnostics["errors"] != []
        or diagnostics["warnings"] != []
        or diagnostics["steps_not_converging_percent"] != "0.00"
        or not isinstance(continuity, str)
        or CONTINUITY_PATTERN.fullmatch(continuity) is None
        or not math.isfinite(float(continuity))
    ):
        raise ObservationError("semantic diagnostic outcome differs")
    for identity, source in SOURCE_BY_SERIES.items():
        if semantic["series"][identity]["source"] != source:
            raise ObservationError(f"{identity} source differs")
    settings_a = semantic["series"]["pump_a_setting"]["values"]
    settings_b = semantic["series"]["pump_b_setting"]["values"]
    if any(a and b for a, b in zip(settings_a, settings_b, strict=True)):
        raise ObservationError("simultaneous pumping is forbidden")
    mode = request["case"]["control_mode"]
    if mode != "automatic":
        expected_a = 1 if selected_pump == "pump-a" else 0
        expected_b = 1 if selected_pump == "pump-b" else 0
        if settings_a != [expected_a] * expected_periods:
            raise ObservationError("forced Pump A setting differs")
        if settings_b != [expected_b] * expected_periods:
            raise ObservationError("forced Pump B setting differs")
    trace = {"pump_a": settings_a, "pump_b": settings_b}
    if semantic["setting_trace_sha256"] != physics.curve_sha256(trace):
        raise ObservationError("setting trace identity differs")
    binary_nonnegative = (
        "wet_well_depth_m",
        "wet_well_volume_m3",
        "wet_well_inflow_m3_s",
        "wet_well_overflow_m3_s",
        "pump_a_flow_m3_s",
        "pump_b_flow_m3_s",
        "force_main_flow_m3_s",
    )
    for identity in binary_nonnegative:
        if any(value < 0.0 for value in _decoded(semantic, identity)):
            raise ObservationError(f"{identity} contains a negative value")
    pump_a = _decoded(semantic, "pump_a_flow_m3_s")
    pump_b = _decoded(semantic, "pump_b_flow_m3_s")
    force_main_hex = semantic["series"]["force_main_flow_m3_s"]["values"]
    expected_force_main = [physics.binary32_hex(a + b) for a, b in zip(pump_a, pump_b, strict=True)]
    if force_main_hex != expected_force_main:
        raise ObservationError("derived force-main series differs")
    depth_hex = semantic["series"]["wet_well_depth_m"]["values"]
    if semantic["series"]["wet_well_head_m"]["values"] != depth_hex:
        raise ObservationError("zero-invert wet-well head differs")
    discharge_hex = physics.binary32_hex(
        float(
            next(
                parameter["value"]
                for parameter in request["member"]["parameters"]
                if parameter["identity"] == "system.z_d"
            )
        )
    )
    if semantic["series"]["discharge_head_m"]["values"] != [discharge_hex] * expected_periods:
        raise ObservationError("fixed discharge HGL differs")


def segment_observations(
    *,
    request: dict[str, Any],
    semantic: dict[str, Any],
    values: dict[str, Decimal],
    segment_id: str,
    carried_depth: float | None,
) -> dict[str, Any]:
    """Compute threshold-free W3 observations for one semantic segment."""
    case = request["case"]
    pump_a_state, pump_b_state, selected = segment_state(case, segment_id)
    expected_periods = 60 if case["case_id"] == "G70_TRANSFER" else case["horizon_s"]
    validate_semantic_exact(
        semantic,
        request,
        expected_periods=expected_periods,
        selected_pump=selected,
    )
    depth = _decoded(semantic, "wet_well_depth_m")
    volume = _decoded(semantic, "wet_well_volume_m3")
    inflow = _decoded(semantic, "wet_well_inflow_m3_s")
    overflow = _decoded(semantic, "wet_well_overflow_m3_s")
    pump_a = _decoded(semantic, "pump_a_flow_m3_s")
    pump_b = _decoded(semantic, "pump_b_flow_m3_s")
    force_main = _decoded(semantic, "force_main_flow_m3_s")
    wet_head = _decoded(semantic, "wet_well_head_m")
    discharge_head = _decoded(semantic, "discharge_head_m")
    settings_a = semantic["series"]["pump_a_setting"]["values"]
    settings_b = semantic["series"]["pump_b_setting"]["values"]
    initial_depth = _initial_depth(case, values, carried_depth=carried_depth)
    area = physics.wet_well_area(values)
    prior_depth = initial_depth
    mass: list[float] = []
    volume_identity: list[float] = []
    expected_inflow: list[float] = []
    pump_sum: list[float] = []
    pump_head: list[float] = []
    system_head: list[float] = []
    root_flow: list[float] = []
    reynolds_margin: list[float] = []
    off_flow: list[float] = []
    on_flow: list[float] = []
    for index in range(expected_periods):
        expected_rate = expected_report_inflow(case, values, index + 1)
        expected_inflow.append(inflow[index] - expected_rate)
        pumped = pump_a[index] + pump_b[index]
        pump_sum.append(force_main[index] - pumped)
        volume_identity.append(volume[index] - area * depth[index])
        mass.append(area * (depth[index] - prior_depth) - (inflow[index] - pumped - overflow[index]))
        prior_depth = depth[index]
        for flow, setting, state in (
            (pump_a[index], settings_a[index], pump_a_state),
            (pump_b[index], settings_b[index], pump_b_state),
        ):
            if setting == 0:
                off_flow.append(flow)
                continue
            on_flow.append(flow)
            obstruction = float(state["obstruction"])
            clearance = float(state["clearance-loss"])
            static_head = discharge_head[index] - wet_head[index]
            pump_closure, net_head_closure = head_closure_residuals(
                values,
                clearance_loss=clearance,
                flow_m3_s=flow,
                obstruction=obstruction,
                static_head_m=static_head,
            )
            pump_head.append(pump_closure)
            system_head.append(net_head_closure)
            root_flow.append(
                flow
                - physics.operating_point(
                    values,
                    depth[index],
                    obstruction,
                    clearance,
                )
            )
            reynolds_margin.append(physics.reynolds_number(values, flow) - float(values["system.Re_min"]))
    reference_depth = initial_depth
    reference_running = False
    reference_depth_residual: list[float] = []
    reference_flow_residual: list[float] = []
    control_edge_residual: list[float] = []
    for index in range(expected_periods):
        if case["control_mode"] == "automatic":
            if not reference_running and reference_depth >= float(values["well.h_start"]):
                reference_running = True
            elif reference_running and reference_depth <= float(values["well.h_stop"]):
                reference_running = False
        else:
            reference_running = selected in {"pump-a", "pump-b"}
        expected_setting_a = int(reference_running and selected == "pump-a")
        expected_setting_b = int(reference_running and selected == "pump-b")
        control_edge_residual.append(
            float(abs(settings_a[index] - expected_setting_a) + abs(settings_b[index] - expected_setting_b))
        )
        active_state = pump_a_state if selected == "pump-a" else pump_b_state
        reference_depth, reference_flow = physics.rk4_interval(
            values,
            clearance_loss=float(active_state["clearance-loss"]),
            depth_m=reference_depth,
            inflow_m3_s=expected_report_inflow(case, values, index + 1),
            obstruction=float(active_state["obstruction"]),
            running=reference_running,
        )
        candidate_flow = pump_a[index] if selected == "pump-a" else pump_b[index]
        reference_depth_residual.append(depth[index] - reference_depth)
        reference_flow_residual.append(candidate_flow - reference_flow)
    cumulative_mass: list[float] = []
    running_total = 0.0
    for item in mass:
        running_total += item
        cumulative_mass.append(running_total)
    continuity = float(semantic["diagnostics"]["flow_routing_continuity_error_percent"])
    return {
        "C-R01": _summary(volume_identity),
        "C-R02": _summary(mass),
        "C-R03": _summary(cumulative_mass),
        "C-R04": _summary(expected_inflow),
        "C-R05": _summary(pump_sum),
        "C-R06": _summary(pump_head),
        "C-R07": _summary(system_head),
        "C-R08": _summary(root_flow),
        "C-R09": {
            "minimum_reynolds_margin": (_text(min(reynolds_margin)) if reynolds_margin else "0"),
            "sample_count": len(reynolds_margin),
        },
        "C-R10": _summary(reference_depth_residual),
        "C-R11": _summary(reference_flow_residual),
        "C-R12": _summary(control_edge_residual),
        "C-R13": _summary(off_flow),
        "C-R14": {
            "minimum_running_flow": _text(min(on_flow)) if on_flow else "0",
            "sample_count": len(on_flow),
        },
        "C-R23": {
            "absolute_percent": _text(abs(continuity)),
            "signed_percent": _text(continuity),
        },
    }
