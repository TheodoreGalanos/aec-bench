# ABOUTME: Evaluates predecessor and source-corrected C-R02/C-R03 mass identities.
# ABOUTME: Keeps exact SWMM routing correction separate from tolerance and physical checks.

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from repairs import c_r02, solver_convergence
from sensitivity import (
    anchor,
    composition,
    edge,
    inputs,
    physics,
    tolerances,
)


@dataclass(frozen=True)
class _Sample:
    budget_m3: float
    correction_m3: float
    corrected_residual_m3: float
    flow_bound_m3: float
    hard_ceiling_m3: float
    maximum_ratio: float
    method_bound_m3: float
    raw_residual_m3: float
    storage_bound_m3: float


def _area_bound(values: dict[str, float]) -> float:
    diameter = values["well.D_w"]
    return (
        math.pi / 2.0 * abs(diameter) * anchor.RENDER_LENGTH
        + math.pi / 4.0 * anchor.RENDER_LENGTH**2
    )


def _storage_identity_bound(
    values: dict[str, float],
    *,
    depth_m: float,
    volume_m3: float,
) -> float:
    area = physics.wet_well_area(values)
    area_bound = _area_bound(values)
    depth_bound = tolerances.binary32_bound(depth_m)
    return tolerances.outward_sum(
        [
            tolerances.binary32_bound(volume_m3),
            area * depth_bound,
            abs(depth_m) * area_bound,
            area_bound * depth_bound,
            tolerances.binary64_guard(volume_m3),
        ]
    )


def _solver_storage_method_bound(values: dict[str, float]) -> float:
    head_tolerance_m = float(
        Decimal(solver_convergence.HEAD_TOLERANCE_M)
    )
    area = physics.wet_well_area(values)
    area_bound = _area_bound(values)
    direct = area * head_tolerance_m
    return tolerances.outward_sum(
        [
            direct,
            area_bound * head_tolerance_m,
            tolerances.binary64_guard(direct),
        ]
    )


def _sample(
    values: dict[str, float],
    *,
    candidate_depth_m: float,
    candidate_inflow_m3_s: float,
    candidate_overflow_m3_s: float,
    candidate_pump_a_m3_s: float,
    candidate_pump_b_m3_s: float,
    correction_coarse_m3: float,
    correction_m3: float,
    candidate_volume_m3: float | None = None,
    prior_candidate_depth_m: float,
    prior_candidate_volume_m3: float | None = None,
    raw_residual_m3: float,
    reference_delta_m3: float,
    reference_inflow_m3_s: float,
    reference_pumped_m3_s: float,
) -> _Sample:
    area = physics.wet_well_area(values)
    if (
        candidate_volume_m3 is not None
        and prior_candidate_volume_m3 is not None
    ):
        storage_bound = tolerances.outward_sum(
            [
                _storage_identity_bound(
                    values,
                    depth_m=candidate_depth_m,
                    volume_m3=candidate_volume_m3,
                ),
                _storage_identity_bound(
                    values,
                    depth_m=prior_candidate_depth_m,
                    volume_m3=prior_candidate_volume_m3,
                ),
                tolerances.binary64_guard(
                    candidate_volume_m3
                    - prior_candidate_volume_m3
                ),
            ]
        )
    else:
        storage_bound = tolerances.outward_sum(
            [
                area
                * (
                    tolerances.binary32_bound(candidate_depth_m)
                    + tolerances.binary32_bound(
                        prior_candidate_depth_m
                    )
                ),
                abs(candidate_depth_m - prior_candidate_depth_m)
                * _area_bound(values),
                tolerances.binary64_guard(
                    area
                    * (candidate_depth_m - prior_candidate_depth_m)
                ),
            ]
        )
    flow_bound = tolerances.outward_sum(
        [
            tolerances.binary32_bound(candidate_inflow_m3_s),
            tolerances.binary32_bound(candidate_pump_a_m3_s),
            tolerances.binary32_bound(candidate_pump_b_m3_s),
            tolerances.binary32_bound(candidate_overflow_m3_s),
            4.0 * anchor.RENDER_FLOW,
        ]
    )
    quadrature_bound = tolerances.outward_sum(
        [
            16.0
            / 15.0
            * abs(correction_coarse_m3 - correction_m3),
            tolerances.binary64_guard(correction_m3),
        ]
    )
    method_bound = tolerances.outward_sum(
        [
            quadrature_bound,
            _solver_storage_method_bound(values),
        ]
    )
    budget = tolerances.outward_sum(
        [storage_bound, flow_bound, method_bound]
    )
    scale = max(
        abs(reference_delta_m3),
        abs(reference_inflow_m3_s),
        abs(reference_pumped_m3_s),
        area * values["observation.level_resolution"],
    )
    ceiling = 0.001 * scale
    corrected = raw_residual_m3 - correction_m3
    return _Sample(
        budget_m3=budget,
        correction_m3=correction_m3,
        corrected_residual_m3=corrected,
        flow_bound_m3=flow_bound,
        hard_ceiling_m3=ceiling,
        maximum_ratio=max(
            abs(corrected) / budget,
            budget / ceiling,
        ),
        method_bound_m3=method_bound,
        raw_residual_m3=raw_residual_m3,
        storage_bound_m3=storage_bound,
    )


def _vectors(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> tuple[list[float], ...]:
    vectors = (
        anchor._series(segment, "wet_well_depth_m"),
        anchor._series(segment, "wet_well_inflow_m3_s"),
        anchor._series(segment, "wet_well_overflow_m3_s"),
        anchor._series(segment, "pump_a_flow_m3_s"),
        anchor._series(segment, "pump_b_flow_m3_s"),
        anchor._raw(result_segment, "C-R02"),
    )
    if len({len(vector) for vector in vectors}) != 1:
        raise inputs.SensitivityInputError(
            "w4-input: C-R02 vector alignment differs"
        )
    return vectors


def _prove_g00(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> tuple[int, float]:
    if (
        segment.case_id != "G00_ZERO_STATIC"
        or segment.segment_id != "single"
        or segment.request["case"]["inflow_stimulus"] != "zero"
    ):
        raise inputs.SensitivityInputError(
            "w4-input: ordered G00 C-R02 baseline differs"
        )
    values = physics.member_values(segment.request["member"])
    depth, inflow, overflow, pump_a, pump_b, raw = _vectors(
        segment,
        result_segment,
    )
    if len(raw) != 3600:
        raise inputs.SensitivityInputError(
            "w4-input: ordered G00 C-R02 sample count differs"
        )
    prior_depth = edge.initial_depth(segment, values)
    maximum_ratio = 0.0
    for candidate_values in zip(
        depth,
        inflow,
        overflow,
        pump_a,
        pump_b,
        raw,
        strict=True,
    ):
        (
            candidate_depth,
            candidate_inflow,
            candidate_overflow,
            candidate_a,
            candidate_b,
            residual,
        ) = candidate_values
        sample = _sample(
            values,
            candidate_depth_m=candidate_depth,
            candidate_inflow_m3_s=candidate_inflow,
            candidate_overflow_m3_s=candidate_overflow,
            candidate_pump_a_m3_s=candidate_a,
            candidate_pump_b_m3_s=candidate_b,
            correction_coarse_m3=0.0,
            correction_m3=0.0,
            prior_candidate_depth_m=prior_depth,
            raw_residual_m3=residual,
            reference_delta_m3=0.0,
            reference_inflow_m3_s=0.0,
            reference_pumped_m3_s=0.0,
        )
        if (
            sample.budget_m3 > sample.hard_ceiling_m3
            or abs(sample.corrected_residual_m3) > sample.budget_m3
        ):
            raise inputs.SensitivityInputError(
                "w4-input: ordered G00 C-R02 baseline rejected"
            )
        maximum_ratio = max(
            maximum_ratio,
            sample.maximum_ratio,
        )
        prior_depth = candidate_depth
    return len(raw), maximum_ratio


def _g10_first_sample(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> _Sample:
    if (
        segment.case_id != "G10_CLEAN_A_BASE"
        or segment.segment_id != "single"
        or segment.request["case"]["control_mode"] != "automatic"
    ):
        raise inputs.SensitivityInputError(
            "w4-input: ordered G10 C-R02 segment differs"
        )
    values = physics.member_values(segment.request["member"])
    case = segment.request["case"]
    state, selected = anchor._state(case, segment.segment_id)
    if (
        selected != "pump-a"
        or segment.semantic["series"]["pump_a_setting"]["values"][0]
        != 0
        or segment.semantic["series"]["pump_b_setting"]["values"][0]
        != 0
    ):
        raise inputs.SensitivityInputError(
            "w4-input: G10 first candidate setting is not off"
        )
    depth, inflow, overflow, pump_a, pump_b, raw = _vectors(
        segment,
        result_segment,
    )
    initial_depth = edge.initial_depth(segment, values)
    reference_inflow = edge.inflow_at(case, values, 1.0)
    obstruction = float(Decimal(state["obstruction"]))
    clearance = float(Decimal(state["clearance-loss"]))
    coarse = physics.rk4_advance(
        values,
        clearance_loss=clearance,
        depth_m=initial_depth,
        duration_s=1.0,
        inflow_m3_s=reference_inflow,
        obstruction=obstruction,
        running=False,
        step_s=1.0,
    )
    half = physics.rk4_advance(
        values,
        clearance_loss=clearance,
        depth_m=initial_depth,
        duration_s=1.0,
        inflow_m3_s=reference_inflow,
        obstruction=obstruction,
        running=False,
        step_s=0.5,
    )
    area = physics.wet_well_area(values)
    correction_coarse = (
        area * (coarse.depth_m - initial_depth) - reference_inflow
    )
    correction = (
        area * (half.depth_m - initial_depth) - reference_inflow
    )
    return _sample(
        values,
        candidate_depth_m=depth[0],
        candidate_inflow_m3_s=inflow[0],
        candidate_overflow_m3_s=overflow[0],
        candidate_pump_a_m3_s=pump_a[0],
        candidate_pump_b_m3_s=pump_b[0],
        correction_coarse_m3=correction_coarse,
        correction_m3=correction,
        prior_candidate_depth_m=initial_depth,
        raw_residual_m3=raw[0],
        reference_delta_m3=area
        * (half.depth_m - initial_depth),
        reference_inflow_m3_s=reference_inflow,
        reference_pumped_m3_s=0.0,
    )


def _failure_evidence(sample: _Sample) -> dict[str, str | int]:
    return {
        "budget_m3": composition._text(sample.budget_m3),
        "case_id": "G10_CLEAN_A_BASE",
        "corrected_residual_m3": composition._text(
            sample.corrected_residual_m3
        ),
        "correction_m3": composition._text(sample.correction_m3),
        "hard_ceiling_m3": composition._text(
            sample.hard_ceiling_m3
        ),
        "raw_residual_m3": composition._text(
            sample.raw_residual_m3
        ),
        "second": 1,
        "segment_id": "single",
    }


def _amended_evidence(
    *,
    budget_m3: float,
    case_id: str,
    corrected_residual_m3: float,
    correction_m3: float,
    hard_ceiling_m3: float,
    maximum_ratio: float,
    raw_residual_m3: float,
    routing_correction_m3: float,
    second: int,
    segment_id: str,
    storage_correction_m3: float,
) -> dict[str, str | int]:
    return {
        "budget_m3": composition._text(budget_m3),
        "case_id": case_id,
        "corrected_residual_m3": composition._text(
            corrected_residual_m3
        ),
        "correction_m3": composition._text(correction_m3),
        "hard_ceiling_m3": composition._text(hard_ceiling_m3),
        "maximum_ratio": composition._text(maximum_ratio),
        "raw_residual_m3": composition._text(raw_residual_m3),
        "routing_correction_m3": composition._text(
            routing_correction_m3
        ),
        "second": second,
        "segment_id": segment_id,
        "storage_correction_m3": composition._text(
            storage_correction_m3
        ),
    }


def _initial_depth(
    segment: inputs.SegmentEvidence,
    values: dict[str, float],
) -> float:
    carry = segment.semantic["carry"]
    if carry:
        return anchor._binary32(carry[0]["value"])
    return edge.initial_depth(segment, values)


def _amended_segment(
    segment: inputs.SegmentEvidence,
    result_segment: dict[str, Any],
) -> dict[str, Any]:
    values = physics.member_values(segment.request["member"])
    depth, inflow, overflow, pump_a, pump_b, raw = _vectors(
        segment,
        result_segment,
    )
    volume = anchor._series(segment, "wet_well_volume_m3")
    cumulative_raw = anchor._raw(result_segment, "C-R03")
    if len(cumulative_raw) != len(raw) or len(volume) != len(raw):
        raise inputs.SensitivityInputError(
            "w4-input: C-R03 vector alignment differs"
        )
    initial_depth = _initial_depth(segment, values)
    prior_depth = initial_depth
    prior_volume = physics.wet_well_area(values) * prior_depth
    initial_volume = prior_volume
    previous_net_flow = 0.0
    correction_prefix = 0.0
    nonstorage_budget_prefix = 0.0
    inflow_prefix = 0.0
    pumped_prefix = 0.0
    maximum_step_ratio = 0.0
    maximum_prefix_ratio = 0.0
    first_step_failure = "none"
    first_step_failure_evidence: dict[str, str | int] | None = None
    first_prefix_failure = "none"
    first_prefix_failure_evidence: dict[str, str | int] | None = None
    worst_step_evidence: dict[str, str | int] | None = None
    worst_prefix_evidence: dict[str, str | int] | None = None
    working_volume = physics.wet_well_area(values) * (
        values["well.h_start"] - values["well.h_stop"]
    )
    for index, (
        candidate_depth,
        candidate_inflow,
        candidate_overflow,
        candidate_a,
        candidate_b,
        candidate_volume,
        raw_residual,
        raw_prefix,
    ) in enumerate(
        zip(
            depth,
            inflow,
            overflow,
            pump_a,
            pump_b,
            volume,
            raw,
            cumulative_raw,
            strict=True,
        ),
        start=1,
    ):
        candidate_pumped = candidate_a + candidate_b
        candidate_net_flow = (
            candidate_inflow
            - candidate_pumped
            - candidate_overflow
        )
        routing_correction = (
            c_r02.trapezoidal_right_end_defect(
                previous_net_flow_m3_s=previous_net_flow,
                current_net_flow_m3_s=candidate_net_flow,
                interval_s=1.0,
            )
        )
        depth_delta = physics.wet_well_area(values) * (
            candidate_depth - prior_depth
        )
        volume_delta = candidate_volume - prior_volume
        storage_correction = depth_delta - volume_delta
        total_correction = math.fsum(
            [routing_correction, storage_correction]
        )
        sample = _sample(
            values,
            candidate_depth_m=candidate_depth,
            candidate_inflow_m3_s=candidate_inflow,
            candidate_overflow_m3_s=candidate_overflow,
            candidate_pump_a_m3_s=candidate_a,
            candidate_pump_b_m3_s=candidate_b,
            correction_coarse_m3=total_correction,
            correction_m3=total_correction,
            candidate_volume_m3=candidate_volume,
            prior_candidate_depth_m=prior_depth,
            prior_candidate_volume_m3=prior_volume,
            raw_residual_m3=raw_residual,
            reference_delta_m3=volume_delta,
            reference_inflow_m3_s=candidate_inflow,
            reference_pumped_m3_s=candidate_pumped,
        )
        if sample.maximum_ratio > maximum_step_ratio:
            maximum_step_ratio = sample.maximum_ratio
            worst_step_evidence = _amended_evidence(
                budget_m3=sample.budget_m3,
                case_id=segment.case_id,
                corrected_residual_m3=sample.corrected_residual_m3,
                correction_m3=total_correction,
                hard_ceiling_m3=sample.hard_ceiling_m3,
                maximum_ratio=sample.maximum_ratio,
                raw_residual_m3=raw_residual,
                routing_correction_m3=routing_correction,
                second=index,
                segment_id=segment.segment_id,
                storage_correction_m3=storage_correction,
            )
        correction_prefix = math.fsum(
            [correction_prefix, total_correction]
        )
        nonstorage_budget_prefix = math.fsum(
            [
                nonstorage_budget_prefix,
                sample.flow_bound_m3,
                sample.method_bound_m3,
            ]
        )
        storage_prefix_bound = tolerances.outward_sum(
            [
                _storage_identity_bound(
                    values,
                    depth_m=initial_depth,
                    volume_m3=initial_volume,
                ),
                _storage_identity_bound(
                    values,
                    depth_m=candidate_depth,
                    volume_m3=candidate_volume,
                ),
                tolerances.binary64_guard(
                    candidate_volume - initial_volume
                ),
            ]
        )
        budget_prefix = tolerances.outward_sum(
            [storage_prefix_bound, nonstorage_budget_prefix]
        )
        inflow_prefix = math.fsum(
            [inflow_prefix, candidate_inflow]
        )
        pumped_prefix = math.fsum(
            [pumped_prefix, candidate_pumped]
        )
        prefix_ceiling = 0.0005 * max(
            working_volume,
            abs(inflow_prefix),
            abs(pumped_prefix),
        )
        corrected_prefix = raw_prefix - correction_prefix
        prefix_ratio = max(
            abs(corrected_prefix) / budget_prefix,
            budget_prefix / prefix_ceiling,
        )
        if prefix_ratio > maximum_prefix_ratio:
            maximum_prefix_ratio = prefix_ratio
            worst_prefix_evidence = _amended_evidence(
                budget_m3=budget_prefix,
                case_id=segment.case_id,
                corrected_residual_m3=corrected_prefix,
                correction_m3=correction_prefix,
                hard_ceiling_m3=prefix_ceiling,
                maximum_ratio=prefix_ratio,
                raw_residual_m3=raw_prefix,
                routing_correction_m3=routing_correction,
                second=index,
                segment_id=segment.segment_id,
                storage_correction_m3=storage_correction,
            )
        if first_step_failure == "none":
            if sample.budget_m3 > sample.hard_ceiling_m3:
                first_step_failure = "C-R02-budget-ceiling"
            elif abs(sample.corrected_residual_m3) > sample.budget_m3:
                first_step_failure = "C-R02-corrected-residual"
            if first_step_failure != "none":
                first_step_failure_evidence = _amended_evidence(
                    budget_m3=sample.budget_m3,
                    case_id=segment.case_id,
                    corrected_residual_m3=sample.corrected_residual_m3,
                    correction_m3=total_correction,
                    hard_ceiling_m3=sample.hard_ceiling_m3,
                    maximum_ratio=sample.maximum_ratio,
                    raw_residual_m3=raw_residual,
                    routing_correction_m3=routing_correction,
                    second=index,
                    segment_id=segment.segment_id,
                    storage_correction_m3=storage_correction,
                )
        if first_prefix_failure == "none":
            if budget_prefix > prefix_ceiling:
                first_prefix_failure = "C-R03-budget-ceiling"
            elif abs(corrected_prefix) > budget_prefix:
                first_prefix_failure = "C-R03-corrected-residual"
            if first_prefix_failure != "none":
                first_prefix_failure_evidence = _amended_evidence(
                    budget_m3=budget_prefix,
                    case_id=segment.case_id,
                    corrected_residual_m3=corrected_prefix,
                    correction_m3=correction_prefix,
                    hard_ceiling_m3=prefix_ceiling,
                    maximum_ratio=prefix_ratio,
                    raw_residual_m3=raw_prefix,
                    routing_correction_m3=routing_correction,
                    second=index,
                    segment_id=segment.segment_id,
                    storage_correction_m3=storage_correction,
                )
        prior_depth = candidate_depth
        prior_volume = candidate_volume
        previous_net_flow = candidate_net_flow
    first_failure = (
        first_step_failure
        if first_step_failure != "none"
        else first_prefix_failure
    )
    return {
        "first_failure": first_failure,
        "first_failure_evidence": (
            first_step_failure_evidence
            if first_step_failure != "none"
            else first_prefix_failure_evidence
        ),
        "first_prefix_failure": first_prefix_failure,
        "first_prefix_failure_evidence": first_prefix_failure_evidence,
        "first_step_failure": first_step_failure,
        "first_step_failure_evidence": first_step_failure_evidence,
        "prefix_count": len(cumulative_raw),
        "prefix_maximum_ratio": maximum_prefix_ratio,
        "sample_count": len(raw),
        "step_maximum_ratio": maximum_step_ratio,
        "worst_prefix_evidence": worst_prefix_evidence,
        "worst_step_evidence": worst_step_evidence,
    }


def evaluate_amended_mass_checks(
    *,
    amendment_bytes: bytes,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> dict[str, Any]:
    """Evaluate C-R02 and C-R03 with the approved routing correction."""
    c_r02.read_amendment(amendment_bytes)
    solver_convergence.read_amendment(solver_convergence_bytes)
    segments = inputs.read_transfer_bundle(bundle_bytes)
    if any(
        segment.request["engine"]["settings_id"]
        != solver_convergence.ENGINE_SETTINGS_ID
        for segment in segments
    ):
        raise inputs.SensitivityInputError(
            "w4-input: solver convergence amendment requires settings v3"
        )
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    prerequisite_checks = anchor.evaluate_composable_checks(
        bundle_bytes=bundle_bytes,
        certifier_result_bytes=certifier_result_bytes,
    )
    for check_id in ("C-R01", "C-R04", "C-R05", "C-R13"):
        if prerequisite_checks["checks"][check_id]["outcome"] != "pass":
            raise inputs.SensitivityInputError(
                f"w4-input: {check_id} must pass before routing correction"
            )
    automatic_edges: list[dict[str, Any]] = []
    evaluated_segments: list[dict[str, Any]] = []
    segment_results: list[dict[str, Any]] = []
    first_step_failure = "none"
    first_step_failure_evidence: dict[str, str | int] | None = None
    first_prefix_failure = "none"
    first_prefix_failure_evidence: dict[str, str | int] | None = None
    for segment in segments:
        if segment.request["case"]["control_mode"] == "automatic":
            edge_result = edge.validate_automatic_edges(segment)
            automatic_edges.append(edge_result)
            if edge_result["outcome"] != "pass":
                raise inputs.SensitivityInputError(
                    "w4-input: automatic C-R12 edge proof rejected"
                )
        result = _amended_segment(
            segment,
            certifier.segment_results[
                (segment.case_id, segment.segment_id)
            ],
        )
        evaluated_segments.append(result)
        segment_results.append(
            {
                "case_id": segment.case_id,
                "first_prefix_failure": result["first_prefix_failure"],
                "first_step_failure": result["first_step_failure"],
                "prefix_count": result["prefix_count"],
                "sample_count": result["sample_count"],
                "segment_id": segment.segment_id,
            }
        )
        if (
            first_step_failure == "none"
            and result["first_step_failure"] != "none"
        ):
            first_step_failure = result["first_step_failure"]
            first_step_failure_evidence = result[
                "first_step_failure_evidence"
            ]
        if (
            first_prefix_failure == "none"
            and result["first_prefix_failure"] != "none"
        ):
            first_prefix_failure = result["first_prefix_failure"]
            first_prefix_failure_evidence = result[
                "first_prefix_failure_evidence"
            ]
    step_count = sum(result["sample_count"] for result in segment_results)
    prefix_count = sum(
        result["prefix_count"] for result in segment_results
    )
    maximum_step_ratio = max(
        result["step_maximum_ratio"]
        for result in evaluated_segments
    )
    maximum_prefix_ratio = max(
        result["prefix_maximum_ratio"]
        for result in evaluated_segments
    )
    first_failure = (
        first_step_failure
        if first_step_failure != "none"
        else first_prefix_failure
    )
    first_failure_evidence = (
        first_step_failure_evidence
        if first_step_failure != "none"
        else first_prefix_failure_evidence
    )
    outcome = "pass" if first_failure == "none" else "reject"
    return {
        "authority": {
            "c_r02_amendment_sha256": c_r02.AMENDMENT_SHA256,
            "routing_rule_id": (
                "asw-0b5.rule.pinned-swmm-trapezoidal-routing-correction.v1"
            ),
            "solver_convergence_amendment_sha256": (
                solver_convergence.AMENDMENT_SHA256
            ),
        },
        "checks": {
            "C-R02": {
                "first_failure": first_step_failure,
                "maximum_ratio": composition._text(
                    maximum_step_ratio
                ),
                "outcome": (
                    "reject" if first_step_failure != "none" else "pass"
                ),
                "sample_count": step_count,
            },
            "C-R03": {
                "first_failure": first_prefix_failure,
                "maximum_ratio": composition._text(
                    maximum_prefix_ratio
                ),
                "outcome": (
                    "reject"
                    if first_prefix_failure != "none"
                    else "pass"
                ),
                "prefix_count": prefix_count,
            },
            "C-R12": {
                "edge_count": sum(
                    result["edge_count"]
                    for result in automatic_edges
                ),
                "first_failure": "none",
                "maximum_ratio": composition._text(
                    max(
                        (
                            float(result["maximum_ratio"])
                            for result in automatic_edges
                        ),
                        default=0.0,
                    )
                ),
                "outcome": "pass",
            },
        },
        "first_failure": first_failure,
        "first_failure_evidence": first_failure_evidence,
        "promotable": False,
        "segments": segment_results,
        "terminal_state": (
            "mass-checks-pass"
            if outcome == "pass"
            else "mass-checks-reject"
        ),
    }


def evaluate_mass_checks(
    *,
    bundle_bytes: bytes,
    certifier_result_bytes: bytes,
) -> dict[str, Any]:
    """Stop the amended successor at its first ordered C-R02 rejection."""
    segments = inputs.read_transfer_bundle(bundle_bytes)
    certifier = inputs.read_certifier_result(
        certifier_result_bytes,
        bundle_bytes=bundle_bytes,
        segments=segments,
    )
    if len(segments) < 2:
        raise inputs.SensitivityInputError(
            "w4-input: ordered C-R02 segments are unavailable"
        )
    g00, g10 = segments[:2]
    g00_count, g00_ratio = _prove_g00(
        g00,
        certifier.segment_results[(g00.case_id, g00.segment_id)],
    )
    edge_result = edge.validate_automatic_edges(g10)
    if edge_result["outcome"] != "pass":
        raise inputs.SensitivityInputError(
            "w4-input: G10 C-R12 edge proof rejected"
        )
    sample = _g10_first_sample(
        g10,
        certifier.segment_results[(g10.case_id, g10.segment_id)],
    )
    if sample.budget_m3 > sample.hard_ceiling_m3:
        failure = "C-R02-budget-ceiling"
    elif abs(sample.corrected_residual_m3) > sample.budget_m3:
        failure = "C-R02-corrected-residual"
    else:
        raise inputs.SensitivityInputError(
            "w4-input: ordered G10 C-R02 sample did not reject"
        )
    return {
        "checks": {
            "C-R02": {
                "first_failure": failure,
                "maximum_ratio": composition._text(
                    max(g00_ratio, sample.maximum_ratio)
                ),
                "outcome": "reject",
                "sample_count": g00_count + 1,
            },
            "C-R03": {
                "evaluated": 0,
                "first_failure": (
                    "not-reached-after-c-r02-reject"
                ),
                "maximum_ratio": "0",
                "outcome": "not-reached-after-c-r02-reject",
            },
            "C-R12": edge_result,
        },
        "first_failure": failure,
        "first_failure_evidence": _failure_evidence(sample),
        "promotable": False,
        "segments": [
            {
                "case_id": g00.case_id,
                "first_failure": "none",
                "segment_id": g00.segment_id,
            },
            {
                "case_id": g10.case_id,
                "first_failure": failure,
                "segment_id": g10.segment_id,
            },
        ],
        "terminal_state": "mass-checks-reject",
    }
