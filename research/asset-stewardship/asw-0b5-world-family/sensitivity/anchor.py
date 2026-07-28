# ABOUTME: Evaluates independently composable W4 anchor residuals from transferred evidence.
# ABOUTME: Applies approved hydraulic amendments without importing generator or certifier code.

from __future__ import annotations

import math
import struct
from decimal import Decimal
from typing import Any, TypedDict

from sensitivity import composition, inputs, physics, tolerances

RENDER_FLOW = 0.5e-9
RENDER_HEAD = 0.5e-9
RENDER_LENGTH = 0.5e-9


class _Aggregate(TypedDict):
    evaluated: int
    failure: str
    ratio: float


def _binary32(value: str) -> float:
    if not isinstance(value, str) or len(value) != 8:
        raise inputs.SensitivityInputError(
            "w4-input: binary32 value differs"
        )
    decoded = float(struct.unpack(">f", bytes.fromhex(value))[0])
    if not math.isfinite(decoded):
        raise inputs.SensitivityInputError(
            "w4-input: binary32 value differs"
        )
    return decoded


def _series(segment: inputs.SegmentEvidence, identity: str) -> list[float]:
    return [
        _binary32(value)
        for value in segment.semantic["series"][identity]["values"]
    ]


def _raw(result_segment: dict[str, Any], check_id: str) -> list[float]:
    values = result_segment["residuals"][check_id].get("values")
    if not isinstance(values, list):
        raise inputs.SensitivityInputError(
            f"w4-input: {check_id} residual vector differs"
        )
    return [float(Decimal(value)) for value in values]


def _state(
    case: dict[str, Any],
    segment_id: str,
) -> tuple[dict[str, str], str]:
    selected = case["selected_pump"]
    if case["case_id"] == "G70_TRANSFER":
        selected = "pump-a" if segment_id == "segment-a" else "pump-b"
    if case["case_id"] == "G80_NO_MAINTENANCE":
        index = int(segment_id.removeprefix("checkpoint-"))
        return case["checkpoints"][index]["mechanism_state"], "pump-a"
    if selected == "none":
        return case["mechanism_state"]["pump-a"], "pump-a"
    return case["mechanism_state"][selected], selected


def _expected_inflow(
    case: dict[str, Any],
    values: dict[str, float],
    second: int,
) -> float:
    stimulus = case["inflow_stimulus"]
    if stimulus == "zero":
        return 0.0
    if stimulus == "constant-assessment":
        return values["inflow.Q_assess"]
    if stimulus != "base-pattern":
        raise inputs.SensitivityInputError(
            "w4-input: inflow stimulus differs"
        )
    points = (
        (0, values["inflow.Q_low"]),
        (5399, values["inflow.Q_low"]),
        (5400, values["inflow.Q_nominal"]),
        (10799, values["inflow.Q_nominal"]),
        (10800, values["inflow.Q_assess"]),
        (14399, values["inflow.Q_assess"]),
        (14400, values["inflow.Q_nominal"]),
        (21599, values["inflow.Q_nominal"]),
        (21600, values["inflow.Q_low"]),
        (28800, values["inflow.Q_low"]),
    )
    date_origin = 37257.0
    evaluation_seconds = ((second - 1) * 1000.0 + 1.0) / 1000.0
    evaluation = date_origin + evaluation_seconds / 86400.0
    for (left_second, left_value), (
        right_second,
        right_value,
    ) in zip(points, points[1:], strict=False):
        left = date_origin + left_second / 86400.0
        right = date_origin + right_second / 86400.0
        if evaluation <= right:
            return left_value + (
                (evaluation - left)
                * (right_value - left_value)
                / (right - left)
            )
    return points[-1][1]


def _eligible_running_indices(
    *,
    segment: inputs.SegmentEvidence,
    selected: str,
    state: dict[str, str],
    values: dict[str, float],
) -> set[int]:
    selected_key = (
        "pump_a_setting" if selected == "pump-a" else "pump_b_setting"
    )
    settings = segment.semantic["series"][selected_key]["values"]
    depth = _series(segment, "wet_well_depth_m")
    obstruction = float(Decimal(state["obstruction"]))
    clearance = float(Decimal(state["clearance-loss"]))
    result: set[int] = set()
    settling_until = -1
    for index, setting in enumerate(settings):
        prior = 0 if index == 0 else settings[index - 1]
        if setting == 1 and prior == 0:
            flow = physics.operating_point(
                values,
                depth_m=(
                    values["well.h_start"] if index == 0 else depth[index - 1]
                ),
                obstruction=obstruction,
                clearance_loss=clearance,
            )
            settling = physics.dynamic_settling(
                values,
                flow_m3_s=flow,
                depth_m=(
                    values["well.h_start"] if index == 0 else depth[index - 1]
                ),
                obstruction=obstruction,
                clearance_loss=clearance,
                report_step_s=1,
            )
            start_second = (
                0
                if index == 0
                and segment.request["case"]["control_mode"] != "automatic"
                else index + 1
            )
            settling_until = (
                start_second + int(settling["settling_time_s"]) - 1
            )
        if setting == 1 and index > settling_until:
            result.add(index)
    return result


def _check(
    *,
    evaluated: int,
    failure: str,
    maximum_ratio: float,
) -> dict[str, Any]:
    return {
        "evaluated": evaluated,
        "first_failure": failure,
        "maximum_ratio": composition._text(maximum_ratio),
        "outcome": "pass" if failure == "none" else "reject",
    }


def _storage_check(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
    values: dict[str, float],
) -> tuple[int, str, float]:
    depth = _series(segment, "wet_well_depth_m")
    volume = _series(segment, "wet_well_volume_m3")
    residual = _raw(result_segment, "C-R01")
    if not len(depth) == len(volume) == len(residual):
        raise inputs.SensitivityInputError(
            "w4-input: C-R01 vector length differs"
        )
    area = physics.wet_well_area(values)
    diameter = values["well.D_w"]
    area_bound = (
        math.pi
        / 2.0
        * abs(diameter)
        * RENDER_LENGTH
        + math.pi / 4.0 * RENDER_LENGTH**2
    )
    residual_prefix = 0.0
    budget_prefix = 0.0
    maximum_ratio = 0.0
    for candidate_depth, candidate_volume, raw in zip(
        depth,
        volume,
        residual,
        strict=True,
    ):
        budget = tolerances.outward_sum(
            [
                tolerances.binary32_bound(candidate_volume),
                area * tolerances.binary32_bound(candidate_depth),
                abs(candidate_depth) * area_bound,
                area_bound
                * tolerances.binary32_bound(candidate_depth),
                tolerances.binary64_guard(candidate_volume),
            ]
        )
        residual_prefix = math.fsum([residual_prefix, raw])
        budget_prefix = math.fsum([budget_prefix, budget])
        maximum_ratio = max(
            maximum_ratio,
            abs(raw) / budget,
            abs(residual_prefix) / budget_prefix,
        )
        if abs(raw) > budget or abs(residual_prefix) > budget_prefix:
            return len(residual), "C-R01-storage-identity", maximum_ratio
    return len(residual), "none", maximum_ratio


def _simple_checks(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
    values: dict[str, float],
) -> dict[str, tuple[int, str, float]]:
    count = len(_series(segment, "wet_well_depth_m"))
    inflow = _series(segment, "wet_well_inflow_m3_s")
    inflow_residual = _raw(result_segment, "C-R04")
    inflow_ratio = 0.0
    inflow_failure = "none"
    for index, (_candidate, raw) in enumerate(
        zip(inflow, inflow_residual, strict=True),
        start=1,
    ):
        expected = _expected_inflow(
            segment.request["case"],
            values,
            index,
        )
        budget = tolerances.outward_sum(
            [
                RENDER_FLOW,
                tolerances.binary32_bound(expected),
                tolerances.binary64_guard(expected),
            ]
        )
        inflow_ratio = max(inflow_ratio, abs(raw) / budget)
        if abs(raw) > budget and inflow_failure == "none":
            inflow_failure = "C-R04-inflow"

    force = _series(segment, "force_main_flow_m3_s")
    pump_a = _series(segment, "pump_a_flow_m3_s")
    pump_b = _series(segment, "pump_b_flow_m3_s")
    pump_sum_residual = _raw(result_segment, "C-R05")
    pump_sum_ratio = 0.0
    pump_sum_failure = "none"
    for force_flow, a_flow, b_flow, raw in zip(
        force,
        pump_a,
        pump_b,
        pump_sum_residual,
        strict=True,
    ):
        budget = tolerances.outward_sum(
            [
                tolerances.binary32_bound(force_flow),
                tolerances.binary32_bound(a_flow),
                tolerances.binary32_bound(b_flow),
                tolerances.binary64_guard(force_flow),
            ]
        )
        if force_flow > 0.0 and budget > 0.001 * force_flow:
            pump_sum_failure = "C-R05-budget-ceiling"
        pump_sum_ratio = max(pump_sum_ratio, abs(raw) / budget)
        if abs(raw) > budget and pump_sum_failure == "none":
            pump_sum_failure = "C-R05-pump-sum"

    off_residual = _raw(result_segment, "C-R13")
    off_ratio = 0.0
    off_failure = "none"
    for raw in off_residual:
        budget = tolerances.outward_sum(
            [RENDER_FLOW, tolerances.binary32_bound(raw)]
        )
        off_ratio = max(off_ratio, abs(raw) / budget)
        if abs(raw) > budget and off_failure == "none":
            off_failure = "C-R13-off-flow"

    continuity = result_segment["residuals"]["C-R23"]
    continuity_value = abs(float(Decimal(continuity["signed_percent"])))
    continuity_ratio = continuity_value / 0.05
    continuity_failure = (
        "none"
        if math.isfinite(continuity_value) and continuity_value <= 0.05
        else "C-R23-engine-continuity"
    )
    return {
        "C-R04": (count, inflow_failure, inflow_ratio),
        "C-R05": (count, pump_sum_failure, pump_sum_ratio),
        "C-R13": (len(off_residual), off_failure, off_ratio),
        "C-R23": (1, continuity_failure, continuity_ratio),
    }


def _hydraulic_checks(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
    values: dict[str, float],
) -> dict[str, tuple[int, str, float]]:
    case = segment.request["case"]
    state, selected = _state(case, segment.segment_id)
    obstruction = float(Decimal(state["obstruction"]))
    clearance = float(Decimal(state["clearance-loss"]))
    selected_flow = _series(
        segment,
        (
            "pump_a_flow_m3_s"
            if selected == "pump-a"
            else "pump_b_flow_m3_s"
        ),
    )
    settings = segment.semantic["series"][
        "pump_a_setting" if selected == "pump-a" else "pump_b_setting"
    ]["values"]
    discharge = _series(segment, "discharge_head_m")
    wet_head = _series(segment, "wet_well_head_m")
    running_indices = [
        index for index, setting in enumerate(settings) if setting == 1
    ]
    eligible = _eligible_running_indices(
        segment=segment,
        selected=selected,
        state=state,
        values=values,
    )
    c_r06_residual = _raw(result_segment, "C-R06")
    c_r07_residual = _raw(result_segment, "C-R07")
    c_r08_residual = _raw(result_segment, "C-R08")
    if not (
        len(running_indices)
        == len(c_r06_residual)
        == len(c_r07_residual)
        == len(c_r08_residual)
    ):
        raise inputs.SensitivityInputError(
            "w4-input: hydraulic residual alignment differs"
        )
    failure = {check_id: "none" for check_id in ("C-R06", "C-R07", "C-R08")}
    ratio = {check_id: 0.0 for check_id in failure}
    evaluated = {"C-R06": 0, "C-R07": 0, "C-R08": 0}
    for residual_index, index in enumerate(running_indices):
        candidate_flow = selected_flow[index]
        curve_head = tolerances.curve_head_bound(
            head_zero_m=Decimal(str(values["pump.H_0"])),
            obstruction=Decimal(str(obstruction)),
            clearance_loss=Decimal(str(clearance)),
            obstruction_coefficient=Decimal(str(values["mechanism.a_o"])),
            clearance_coefficient=Decimal(str(values["mechanism.a_c"])),
            segments=32,
        )
        pump_head = physics.pump_head(
            values,
            candidate_flow,
            obstruction,
            clearance,
        )
        head_budget = tolerances.outward_sum(
            [
                tolerances.binary32_bound(discharge[index]),
                tolerances.binary32_bound(wet_head[index]),
                curve_head,
                RENDER_HEAD,
                tolerances.binary64_guard(pump_head),
            ]
        )
        head_ceiling = 0.001 * abs(discharge[index] - wet_head[index])
        evaluated["C-R06"] += 1
        ratio["C-R06"] = max(
            ratio["C-R06"],
            abs(c_r06_residual[residual_index]) / head_budget,
        )
        if head_budget > head_ceiling:
            failure["C-R06"] = "C-R06-budget-ceiling"
        elif (
            abs(c_r06_residual[residual_index]) > head_budget
            and failure["C-R06"] == "none"
        ):
            failure["C-R06"] = "C-R06-pump-head"
        if index not in eligible:
            continue
        system_render = composition.system_render_head_bound(
            values,
            candidate_flow_m3_s=candidate_flow,
        )
        c_r07 = composition.amended_net_head_budget(
            values,
            clearance_loss=clearance,
            discharge_head_m=discharge[index],
            obstruction=obstruction,
            raw_residual_m=c_r07_residual[residual_index],
            system_render_head_m=system_render,
            wet_well_head_m=wet_head[index],
        )
        reference_flow = physics.operating_point(
            values,
            depth_m=wet_head[index],
            obstruction=obstruction,
            clearance_loss=clearance,
        )
        c_r08 = composition.amended_root_flow_budget(
            values,
            candidate_flow_m3_s=candidate_flow,
            clearance_loss=clearance,
            depth_m=wet_head[index],
            obstruction=obstruction,
            raw_residual_m3_s=c_r08_residual[residual_index],
            reference_flow_m3_s=reference_flow,
            system_render_head_m=system_render,
        )
        for check_id, check_value, allowance_key, residual_value in (
            (
                "C-R07",
                c_r07,
                "derived_allowance_m",
                c_r07_residual[residual_index],
            ),
            (
                "C-R08",
                c_r08,
                "total_allowance_m3_s",
                c_r08_residual[residual_index],
            ),
        ):
            evaluated[check_id] += 1
            allowance_value = check_value[allowance_key]
            if (
                isinstance(allowance_value, bool)
                or not isinstance(allowance_value, int | float)
            ):
                raise inputs.SensitivityInputError(
                    "w4-input: hydraulic allowance differs"
                )
            allowance = float(allowance_value)
            ratio[check_id] = max(
                ratio[check_id],
                abs(residual_value) / allowance,
            )
            if (
                check_value["first_failure"] != "none"
                and failure[check_id] == "none"
            ):
                failure[check_id] = str(check_value["first_failure"])

    c_r09 = result_segment["residuals"]["C-R09"]
    reynolds_margin = float(Decimal(c_r09["minimum_reynolds_margin"]))
    reynolds_failure = (
        "none" if reynolds_margin >= 0.0 else "C-R09-full-pipe"
    )
    c_r09_ratio = (
        0.0
        if reynolds_margin >= 0.0
        else abs(reynolds_margin) / values["system.Re_min"]
    )
    re_flow = (
        values["system.Re_min"]
        * math.pi
        * values["system.D"]
        * values["fluid.mu"]
        / (4.0 * values["fluid.rho"])
    )
    running_floor_failure = "none"
    running_floor_ratio = 0.0
    for index in sorted(eligible):
        floor_budget = tolerances.outward_sum(
            [
                RENDER_FLOW,
                tolerances.binary32_bound(selected_flow[index]),
            ]
        )
        threshold = re_flow + floor_budget
        running_floor_ratio = max(
            running_floor_ratio,
            threshold / selected_flow[index],
        )
        if selected_flow[index] < threshold:
            running_floor_failure = "C-R14-running-flow-floor"
            break
    return {
        "C-R06": (
            evaluated["C-R06"],
            failure["C-R06"],
            ratio["C-R06"],
        ),
        "C-R07": (
            evaluated["C-R07"],
            failure["C-R07"],
            ratio["C-R07"],
        ),
        "C-R08": (
            evaluated["C-R08"],
            failure["C-R08"],
            ratio["C-R08"],
        ),
        "C-R09": (
            int(c_r09["sample_count"]),
            reynolds_failure,
            c_r09_ratio,
        ),
        "C-R14": (
            len(eligible),
            running_floor_failure,
            running_floor_ratio,
        ),
    }


def evaluate_composable_checks(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
) -> dict[str, Any]:
    """Evaluate the complete anchor checks not requiring mass or trajectory correction."""
    segments = inputs.read_transfer_bundle(bundle_bytes)
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    ordered_ids = (
        "C-R01",
        "C-R04",
        "C-R05",
        "C-R06",
        "C-R07",
        "C-R08",
        "C-R09",
        "C-R13",
        "C-R14",
        "C-R23",
    )
    aggregate: dict[str, _Aggregate] = {
        check_id: {"evaluated": 0, "failure": "none", "ratio": 0.0}
        for check_id in ordered_ids
    }
    for segment in segments:
        result_segment = certifier.segment_results[
            (segment.case_id, segment.segment_id)
        ]
        values = physics.member_values(segment.request["member"])
        storage = _storage_check(segment, result_segment, values)
        checks = {
            "C-R01": storage,
            **_simple_checks(segment, result_segment, values),
            **_hydraulic_checks(segment, result_segment, values),
        }
        for check_id, (evaluated, failure, ratio) in checks.items():
            target = aggregate[check_id]
            target["evaluated"] += evaluated
            target["ratio"] = max(target["ratio"], ratio)
            if target["failure"] == "none" and failure != "none":
                target["failure"] = failure
    result_checks = {
        check_id: _check(
            evaluated=int(aggregate[check_id]["evaluated"]),
            failure=str(aggregate[check_id]["failure"]),
            maximum_ratio=float(aggregate[check_id]["ratio"]),
        )
        for check_id in ordered_ids
    }
    failures = [
        check["first_failure"]
        for check in result_checks.values()
        if check["first_failure"] != "none"
    ]
    return {
        "checks": result_checks,
        "first_failure": failures[0] if failures else "none",
        "promotable": False,
        "terminal_state": (
            "composable-anchor-checks-reject"
            if failures
            else "composable-anchor-checks-pass"
        ),
    }
