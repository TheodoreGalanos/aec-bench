# ABOUTME: Evaluates C-R02 only through its first ordered successor rejection.
# ABOUTME: Proves G00, repairs G10 edge evidence, and leaves later checks unreached.

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

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
    hard_ceiling_m3: float
    maximum_ratio: float
    raw_residual_m3: float


def _area_bound(values: dict[str, float]) -> float:
    diameter = values["well.D_w"]
    return (
        math.pi / 2.0 * abs(diameter) * anchor.RENDER_LENGTH
        + math.pi / 4.0 * anchor.RENDER_LENGTH**2
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
    prior_candidate_depth_m: float,
    raw_residual_m3: float,
    reference_delta_m3: float,
    reference_inflow_m3_s: float,
    reference_pumped_m3_s: float,
) -> _Sample:
    area = physics.wet_well_area(values)
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
    budget = tolerances.outward_sum(
        [storage_bound, flow_bound, quadrature_bound]
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
        hard_ceiling_m3=ceiling,
        maximum_ratio=max(
            abs(corrected) / budget,
            budget / ceiling,
        ),
        raw_residual_m3=raw_residual_m3,
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
